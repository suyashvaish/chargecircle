from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.community import AuditLog, Dispute, ModerationAction, Review
from app.services.audit import audit
from app.services.notification_service import send_in_app_notification
from app.models.enums import BookingStatus, ListingStatus, UserRoleType
from app.models.marketplace import Booking, HomeChargerListing
from app.models.payment import Payment
from app.models.reliability import ChargerReport
from app.models.station import ChargingStation
from app.models.user import User, UserRole
from app.schemas.community import AdminStatsOut
from app.schemas.reliability import ModerationActionCreate


def get_platform_admin_metrics(db: Session) -> AdminStatsOut:
    """Calculates live platform KPIs directly from persistent database records."""
    total_users = db.query(func.count(User.id)).scalar() or 0
    total_drivers = db.query(func.count(UserRole.id)).filter(UserRole.role_name == UserRoleType.DRIVER.value).scalar() or 0
    total_hosts = db.query(func.count(UserRole.id)).filter(UserRole.role_name == UserRoleType.HOST.value).scalar() or 0
    total_public_stations = db.query(func.count(ChargingStation.id)).scalar() or 0
    total_home_listings = db.query(func.count(HomeChargerListing.id)).scalar() or 0
    
    pending_verifications = db.query(func.count(HomeChargerListing.id)).filter(
        HomeChargerListing.status == ListingStatus.PENDING_VERIFICATION.value
    ).scalar() or 0
    
    total_bookings = db.query(func.count(Booking.id)).scalar() or 0
    confirmed_bookings = db.query(func.count(Booking.id)).filter(
        Booking.status.in_([BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value, BookingStatus.COMPLETED.value])
    ).scalar() or 0
    
    revenue_stats = db.query(
        func.coalesce(func.sum(Booking.total_amount), 0.0),
        func.coalesce(func.sum(Booking.platform_fee), 0.0)
    ).filter(
        Booking.status.in_([BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value, BookingStatus.COMPLETED.value])
    ).first()
    
    total_gross = round(float(revenue_stats[0]), 2) if revenue_stats else 0.0
    total_fees = round(float(revenue_stats[1]), 2) if revenue_stats else 0.0
    
    pending_reports = db.query(func.count(ChargerReport.id)).filter(
        ChargerReport.moderation_status == "under_review"
    ).scalar() or 0
    
    open_disputes = db.query(func.count(Dispute.id)).filter(
        Dispute.status == "open"
    ).scalar() or 0

    return AdminStatsOut(
        total_users=total_users,
        total_drivers=total_drivers,
        total_hosts=total_hosts,
        total_public_stations=total_public_stations,
        total_home_listings=total_home_listings,
        pending_host_verifications=pending_verifications,
        total_bookings=total_bookings,
        confirmed_bookings=confirmed_bookings,
        total_gross_revenue=total_gross,
        total_platform_fees=total_fees,
        pending_reports_moderation=pending_reports,
        open_disputes=open_disputes
    )


_ALLOWED = {
    "listing": {"approved", "rejected", "suspended"},
    "report": {"approved", "rejected", "dismissed", "resolved", "escalated"},
    "review": {"hidden", "restored"},
    "dispute": {"resolved", "dismissed", "escalated"},
}


def execute_moderation_action(
    db: Session, admin_id: int, data: ModerationActionCreate
) -> ModerationAction:
    """Executes and audits an administrative decision. Unknown targets/actions are rejected."""
    if data.action not in _ALLOWED.get(data.target_type, set()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"'{data.action}' is not a valid action for {data.target_type}")
    now = datetime.now(timezone.utc)
    recalc = None
    if data.target_type == "listing":
        target = db.query(HomeChargerListing).filter(HomeChargerListing.id == data.target_id).first()
        if target:
            target.status = {"approved": ListingStatus.APPROVED.value, "rejected": ListingStatus.REJECTED.value,
                             "suspended": ListingStatus.SUSPENDED.value}[data.action]
    elif data.target_type == "report":
        target = db.query(ChargerReport).filter(ChargerReport.id == data.target_id).first()
        if target:
            target.moderation_status = {"approved": "published", "rejected": "rejected", "dismissed": "rejected",
                                        "resolved": "resolved", "escalated": "escalated"}[data.action]
            target.moderation_notes, target.moderated_by_id, target.moderated_at = data.notes, admin_id, now
            recalc = (target.station_id, target.home_listing_id)
    elif data.target_type == "review":
        target = db.query(Review).filter(Review.id == data.target_id).first()
        if target:
            target.moderation_status = "hidden" if data.action == "hidden" else "published"
            target.is_moderated = True
    elif data.target_type == "dispute":
        target = db.query(Dispute).filter(Dispute.id == data.target_id).first()
        if target:
            if target.status in ("resolved", "dismissed"):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This dispute is already closed")
            target.status = {"resolved": "resolved", "dismissed": "dismissed", "escalated": "escalated"}[data.action]
            target.resolution_notes = data.notes
            if data.action != "escalated":
                _close_dispute(db, target, admin_id)
    else:
        target = None
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{data.target_type} not found")

    mod = ModerationAction(admin_id=admin_id, target_type=data.target_type, target_id=data.target_id,
                           action=data.action, notes=data.notes)
    db.add(mod)
    audit(db, admin_id, f"MODERATION_{data.action.upper()}", data.target_type.capitalize(), data.target_id,
          {"action": data.action, "notes": data.notes})
    db.commit()
    if recalc and (recalc[0] or recalc[1]):
        from app.services.reliability_service import calculate_and_update_charger_status
        calculate_and_update_charger_status(db, station_id=recalc[0], home_listing_id=recalc[1])
    db.refresh(mod)
    return mod


def _close_dispute(db: Session, dispute: Dispute, admin_id: int) -> None:
    dispute.resolved_by_id, dispute.resolved_at = admin_id, datetime.now(timezone.utc)
    booking = dispute.booking
    if booking.status == BookingStatus.DISPUTED.value:
        booking.status = dispute.prior_booking_status or BookingStatus.COMPLETED.value
        if booking.session and booking.session.status == "disputed":
            booking.session.status = dispute.prior_session_status or "completed"


def resolve_dispute(db: Session, admin_id: int, dispute_id: int, decision: str, notes: str):
    """Resolves a dispute, optionally issuing a full refund. Fully audited."""
    from app.services.payment_service import admin_refund_for_dispute
    dispute = db.query(Dispute).filter(Dispute.id == dispute_id).first()
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    if dispute.status in ("resolved", "dismissed"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This dispute is already closed")
    if decision == "escalate":
        dispute.status, dispute.resolution_notes = "escalated", notes
    else:
        refund = None
        if decision == "refund_full":
            refund = admin_refund_for_dispute(db, dispute.booking, admin_id, f"Dispute #{dispute.id}: {notes}"[:255])
            if refund is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="There is no captured payment to refund for this booking")
            dispute.booking.status = BookingStatus.CANCELLED.value
            dispute.booking.cancellation_reason = f"dispute_refund:{dispute.id}"
            if dispute.booking.session:
                dispute.booking.session.status = "cancelled"
            dispute.prior_booking_status = BookingStatus.CANCELLED.value
        dispute.status = "dismissed" if decision == "dismiss" else "resolved"
        dispute.resolution_notes = notes
        _close_dispute(db, dispute, admin_id)
        send_in_app_notification(db, dispute.filed_by_id, "Dispute update", f"Your dispute on booking {dispute.booking.booking_reference} was {dispute.status}.",
                                 "dispute_resolved", f"/bookings/{dispute.booking_id}", commit=False)
    db.add(ModerationAction(admin_id=admin_id, target_type="dispute", target_id=dispute.id, action=decision, notes=notes))
    audit(db, admin_id, f"DISPUTE_{decision.upper()}", "Dispute", dispute.id, {"decision": decision, "notes": notes})
    db.commit()
    db.refresh(dispute)
    return dispute
