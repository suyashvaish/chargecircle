from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.reliability import ChargerReport
from app.models.user import User
from app.schemas.reliability import ReliabilityScoreBreakdown, ReportCreate, ReportOut
from app.services.auth_service import get_current_user
from app.services.reliability_service import (
    calculate_and_update_charger_status,
    submit_charger_report,
)

router = APIRouter(prefix="/reliability", tags=["Charger Trust & Reliability System"])


@router.post("/reports", response_model=ReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    data: ReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Priority 3: Submits an operational report.
    Free community reports receive Level 1 weight;
    Reports backed by a paid booking/session elevate to Level 2.
    Operator/hardware integration provides Level 3.
    """
    return submit_charger_report(db, current_user, data)


@router.get("/reports", response_model=List[ReportOut])
def get_reports(
    station_id: Optional[int] = Query(None),
    home_listing_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieves moderation-approved operational reports for a charger."""
    query = db.query(ChargerReport).filter(ChargerReport.moderation_status == "published")
    if station_id:
        query = query.filter(ChargerReport.station_id == station_id)
    if home_listing_id:
        query = query.filter(ChargerReport.home_listing_id == home_listing_id)
    return query.order_by(ChargerReport.created_at.desc()).limit(50).all()


@router.get("/status/{target_type}/{target_id}", response_model=ReliabilityScoreBreakdown)
def get_charger_status(
    target_type: str,  # "station" or "listing"
    target_id: int,
    db: Session = Depends(get_db)
):
    """Returns the calculated status, confidence score, and explainable evidence breakdown."""
    if target_type == "station":
        return calculate_and_update_charger_status(db, station_id=target_id)
    elif target_type in ["listing", "home_listing"]:
        return calculate_and_update_charger_status(db, home_listing_id=target_id)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="target_type must be 'station' or 'listing'"
        )
