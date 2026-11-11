import json
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.community import AuditLog
from app.models.enums import BookingStatus, OperationalStatus, PaymentStatus, ReportCategory
from app.models.marketplace import Booking, ChargingSession
from app.models.payment import Payment
from app.models.reliability import ChargerReport, ChargerStatusSnapshot, ReportEvidence
from app.models.user import User
from app.schemas.reliability import ReliabilityScoreBreakdown, ReportCreate


OPERATIONAL_CATEGORIES = {
    ReportCategory.WORKING_NORMALLY.value, ReportCategory.NOT_WORKING.value, ReportCategory.OCCUPIED.value,
    ReportCategory.DAMAGED_EQUIPMENT.value, ReportCategory.PAYMENT_TERMINAL_FAILURE.value,
    ReportCategory.CONNECTOR_UNAVAILABLE.value, ReportCategory.CLOSED_STATION.value,
}


def submit_charger_report(
    db: Session, user: User, data: ReportCreate
) -> ChargerReport:
    """
    Submits a community charger operational report.
    Evaluates evidence tier (Level 1, Level 2, or Level 3) without requiring payment.
    Applies anti-fraud rate limits and duplicate suppression.
    """
    if not data.station_id and not data.home_listing_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either station_id or home_listing_id must be provided"
        )

    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    one_hour_ago = now - timedelta(hours=1)

    # 1. Anti-Fraud Rate Limiting: Max unverified reports per day
    recent_user_reports = db.query(ChargerReport).filter(
        ChargerReport.user_id == user.id,
        ChargerReport.created_at >= one_day_ago
    ).count()

    if recent_user_reports >= settings.MAX_UNVERIFIED_REPORTS_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily report limit reached. Please try again tomorrow."
        )

    # 2. Duplicate Detection: Check if user submitted identical category for this charger within 1 hour
    duplicate_query = db.query(ChargerReport).filter(
        ChargerReport.user_id == user.id,
        ChargerReport.category == data.category,
        ChargerReport.created_at >= one_hour_ago
    )
    if data.station_id:
        duplicate_query = duplicate_query.filter(ChargerReport.station_id == data.station_id)
    if data.home_listing_id:
        duplicate_query = duplicate_query.filter(ChargerReport.home_listing_id == data.home_listing_id)

    if duplicate_query.first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A similar report for this charger was recently submitted from your account."
        )

    # 3. Determine Evidence Level
    evidence_level = 1  # Baseline Level 1: Unverified community report
    is_verified = False

    # Check for Level 2: Linked to completed booking with verified payment
    if data.booking_id:
        booking = db.query(Booking).filter(
            Booking.id == data.booking_id,
            Booking.driver_id == user.id
        ).first()

        if booking:
            payment = db.query(Payment).filter(
                Payment.booking_id == booking.id,
                Payment.status == PaymentStatus.CAPTURED.value
            ).first()

            # Critical Rule: Verified payment + platform booking elevates report credibility
            # but is recorded as session-supported evidence, not blind hardware truth.
            if payment:
                evidence_level = 2
                is_verified = True

    # Level 3 is reserved for verified operator telemetry / hardware integration or admin confirmations
    if user.has_role("operator") or user.has_role("admin"):
        evidence_level = 3
        is_verified = True

    # Operational categories feed the reliability engine. Information/safety categories go to human moderation
    # first and never change a charger's operational status or label anyone fraudulent on their own.
    operational = data.category in OPERATIONAL_CATEGORIES
    if data.booking_id and not db.query(Booking).filter(Booking.id == data.booking_id, Booking.driver_id == user.id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if data.home_listing_id and data.category == "incorrect_location":
        pass

    # Persist Report
    report = ChargerReport(
        booking_id=data.booking_id,
        station_id=data.station_id,
        home_listing_id=data.home_listing_id,
        user_id=user.id,
        session_id=None,
        category=data.category,
        description=data.description,
        evidence_level=evidence_level,
        is_verified=is_verified,
        moderation_status="published" if operational else "under_review"
    )
    db.add(report)
    db.flush()

    # Add supporting evidence item if provided
    if data.evidence_file_url and data.evidence_type:
        db.add(ReportEvidence(
            report_id=report.id,
            evidence_type=data.evidence_type,
            file_url=data.evidence_file_url,
            description="Submitted user evidence photo/receipt"
        ))

    db.add(AuditLog(
        user_id=user.id,
        action="REPORT_SUBMITTED",
        resource_type="ChargerReport",
        resource_id=str(report.id),
        details_json=json.dumps({"category": data.category, "evidence_level": evidence_level, "operational": operational})
    ))

    db.commit()
    db.refresh(report)

    if operational:
        calculate_and_update_charger_status(
            db, station_id=data.station_id, home_listing_id=data.home_listing_id
        )

    return report


def calculate_and_update_charger_status(
    db: Session,
    station_id: Optional[int] = None,
    home_listing_id: Optional[int] = None
) -> ReliabilityScoreBreakdown:
    """
    Core Reliability Scoring Engine.
    Aggregates reports with:
      - Exponential time decay (freshness half-life = 72 hours).
      - Evidence level weighting (Level 1 = 1x, Level 2 = 3x, Level 3 = 5x).
      - Diminishing marginal weight for repeated reports from identical user.
      - Transparent conflict resolution.
    """
    now = datetime.now(timezone.utc)
    window_cutoff = now - timedelta(days=14)  # Consider reports within past 14 days

    query = db.query(ChargerReport).filter(
        ChargerReport.moderation_status == "published",
        ChargerReport.created_at >= window_cutoff
    )
    if station_id:
        query = query.filter(ChargerReport.station_id == station_id)
    elif home_listing_id:
        query = query.filter(ChargerReport.home_listing_id == home_listing_id)
    else:
        raise ValueError("Must specify either station_id or home_listing_id")

    reports = query.order_by(ChargerReport.created_at.desc()).all()

    if not reports:
        snapshot = ChargerStatusSnapshot(
            station_id=station_id,
            home_listing_id=home_listing_id,
            operational_status=OperationalStatus.NOT_RECENTLY_CHECKED.value,
            confidence_score=0.5,
            evidence_summary="No recent community reports recorded.",
            total_reports_evaluated=0,
            positive_weight=0.0,
            negative_weight=0.0,
            last_reported_at=None,
            calculated_at=now
        )
        db.add(snapshot)
        db.commit()
        return ReliabilityScoreBreakdown(
            operational_status=snapshot.operational_status,
            confidence_score=snapshot.confidence_score,
            evidence_summary=snapshot.evidence_summary,
            total_reports_evaluated=0,
            positive_weight=0.0,
            negative_weight=0.0,
            last_reported_at=None,
            calculated_at=now
        )

    half_life_hours = float(settings.REPORT_FRESHNESS_HALF_LIFE_HOURS)
    total_pos_weight = 0.0
    total_neg_weight = 0.0
    user_report_counts: Dict[int, int] = {}
    most_recent_report_time = reports[0].created_at
    level_3_seen = False

    for rep in reports:
        # Diminishing marginal weight for same reporter to prevent astroturfing
        u_count = user_report_counts.get(rep.user_id, 0) + 1
        user_report_counts[rep.user_id] = u_count
        user_independence_factor = 1.0 / math.sqrt(u_count)

        # Evidence multiplier
        evidence_multiplier = 1.0
        if rep.evidence_level == 2:
            evidence_multiplier = 3.0
        elif rep.evidence_level >= 3:
            evidence_multiplier = 5.0
            level_3_seen = True

        # Time decay calculation: 0.5 ** (age_hours / half_life)
        # Ensure timezone-aware subtraction
        rep_created = rep.created_at
        if rep_created.tzinfo is None:
            rep_created = rep_created.replace(tzinfo=timezone.utc)
        age_hours = max((now - rep_created).total_seconds() / 3600.0, 0.0)
        decay = 0.5 ** (age_hours / half_life_hours)

        effective_weight = decay * evidence_multiplier * user_independence_factor

        # Classify as positive or negative operational signal
        if rep.category in [ReportCategory.WORKING_NORMALLY.value]:
            total_pos_weight += effective_weight
        elif rep.category in [
            ReportCategory.NOT_WORKING.value,
            ReportCategory.DAMAGED_EQUIPMENT.value,
            ReportCategory.CLOSED_STATION.value,
            ReportCategory.CONNECTOR_UNAVAILABLE.value,
            ReportCategory.PAYMENT_TERMINAL_FAILURE.value
        ]:
            total_neg_weight += effective_weight
        # OCCUPIED is a transient status and does not decrease overall hardware reliability weight

    total_weight = total_pos_weight + total_neg_weight
    distinct_reporters = len({r.user_id for r in reports})
    strong_evidence = any(r.evidence_level >= 2 for r in reports)
    
    # Status Determination Logic
    if total_weight == 0.0:
        status_result = OperationalStatus.UNKNOWN.value
        confidence = 0.5
        summary = "Reports inconclusive"
    elif distinct_reporters < 2 and not strong_evidence and total_neg_weight > total_pos_weight:
        # One unverified negative report is a signal, not a verdict.
        status_result = OperationalStatus.UNKNOWN.value
        confidence = 0.5
        summary = "Only one unverified report; not enough to change this charger's status"
    else:
        pos_ratio = total_pos_weight / total_weight

        # Check for conflict: both positive and negative weights are significant
        if total_pos_weight >= 1.0 and total_neg_weight >= 1.0 and (0.35 <= pos_ratio <= 0.65):
            status_result = OperationalStatus.CONFLICTING_REPORTS.value
            confidence = 0.5
            summary = f"Conflicting driver reports ({len(reports)} reports evaluated)"
        elif pos_ratio >= settings.CONFIDENCE_THRESHOLD_OPERATIONAL:
            if level_3_seen or total_pos_weight >= 2.5:
                status_result = OperationalStatus.CONFIRMED_OPERATIONAL.value
                confidence = min(0.95, round(0.70 + (pos_ratio * 0.25), 2))
                summary = "Supported by multiple independent or session-verified reports"
            else:
                status_result = OperationalStatus.LIKELY_OPERATIONAL.value
                confidence = round(0.50 + (pos_ratio * 0.30), 2)
                summary = "Recent community reports indicate working normally"
        elif pos_ratio <= settings.CONFIDENCE_THRESHOLD_UNAVAILABLE:
            status_result = OperationalStatus.REPORTED_UNAVAILABLE.value
            confidence = min(0.95, round(0.70 + ((1.0 - pos_ratio) * 0.25), 2))
            summary = "Recent reports indicate charger is out of service or faulty"
        else:
            status_result = OperationalStatus.UNKNOWN.value
            confidence = 0.5
            summary = "Operational state is uncertain"

    # Persist or update snapshot
    existing_snapshot = db.query(ChargerStatusSnapshot).filter(
        ChargerStatusSnapshot.station_id == station_id if station_id else ChargerStatusSnapshot.home_listing_id == home_listing_id
    ).first()

    if existing_snapshot:
        existing_snapshot.operational_status = status_result
        existing_snapshot.confidence_score = confidence
        existing_snapshot.evidence_summary = summary
        existing_snapshot.total_reports_evaluated = len(reports)
        existing_snapshot.positive_weight = round(total_pos_weight, 2)
        existing_snapshot.negative_weight = round(total_neg_weight, 2)
        existing_snapshot.last_reported_at = most_recent_report_time
        existing_snapshot.calculated_at = now
    else:
        new_snapshot = ChargerStatusSnapshot(
            station_id=station_id,
            home_listing_id=home_listing_id,
            operational_status=status_result,
            confidence_score=confidence,
            evidence_summary=summary,
            total_reports_evaluated=len(reports),
            positive_weight=round(total_pos_weight, 2),
            negative_weight=round(total_neg_weight, 2),
            last_reported_at=most_recent_report_time,
            calculated_at=now
        )
        db.add(new_snapshot)

    db.commit()

    return ReliabilityScoreBreakdown(
        operational_status=status_result,
        confidence_score=confidence,
        evidence_summary=summary,
        total_reports_evaluated=len(reports),
        positive_weight=round(total_pos_weight, 2),
        negative_weight=round(total_neg_weight, 2),
        last_reported_at=most_recent_report_time,
        calculated_at=now
    )
