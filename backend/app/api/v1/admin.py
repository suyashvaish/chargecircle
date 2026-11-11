from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.community import AuditLog, Dispute
from app.models.reliability import ChargerReport
from app.models.station import ChargerConnector
from app.services.audit import audit
from app.services.marketplace_service import build_listing_out
from app.models.enums import ListingStatus
from app.models.marketplace import HomeChargerListing
from app.models.user import User
from app.schemas.community import AdminStatsOut
from app.schemas.reliability import ModerationActionCreate, ResolveDisputeRequest
from app.schemas.marketplace import HomeListingOut
from app.services.admin_service import execute_moderation_action, get_platform_admin_metrics, resolve_dispute
from app.services.auth_service import get_current_active_admin

router = APIRouter(prefix="/admin", tags=["Administration & Platform Governance"])


@router.get("/metrics", response_model=AdminStatsOut)
def get_metrics(
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Calculates live platform KPIs from real database entities."""
    return get_platform_admin_metrics(db)


@router.get("/pending-listings", response_model=List[HomeListingOut])
def list_pending_verifications(
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Lists home charging listings awaiting administrator safety/identity approval (admins see exact addresses)."""
    listings = db.query(HomeChargerListing).filter(
        HomeChargerListing.status == ListingStatus.PENDING_VERIFICATION.value
    ).all()
    return [build_listing_out(item, exact=True, with_street=True) for item in listings]


@router.get("/reports")
def list_reports(status_filter: str = Query("under_review", alias="status"), limit: int = Query(50, ge=1, le=200),
                 admin: User = Depends(get_current_active_admin), db: Session = Depends(get_db)):
    """Moderation queue of user reports (information, pricing, suspicious-listing and safety reports)."""
    rows = db.query(ChargerReport).filter(ChargerReport.moderation_status == status_filter
                                          ).order_by(ChargerReport.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "station_id": r.station_id, "home_listing_id": r.home_listing_id, "category": r.category,
             "description": r.description, "evidence_level": r.evidence_level, "is_verified": r.is_verified,
             "moderation_status": r.moderation_status, "moderation_notes": r.moderation_notes,
             "reporter_id": r.user_id, "booking_id": r.booking_id, "created_at": r.created_at.isoformat(),
             "evidence": [{"type": e.evidence_type, "url": e.file_url} for e in r.evidence_items]} for r in rows]


@router.get("/disputes")
def list_disputes(status_filter: str = Query("open", alias="status"), limit: int = Query(50, ge=1, le=200),
                  admin: User = Depends(get_current_active_admin), db: Session = Depends(get_db)):
    rows = db.query(Dispute).filter(Dispute.status == status_filter).order_by(Dispute.created_at.desc()).limit(limit).all()
    return [{"id": d.id, "booking_id": d.booking_id, "booking_reference": d.booking.booking_reference,
             "filed_by_id": d.filed_by_id, "against_id": d.against_id, "category": d.category, "reason": d.reason,
             "evidence_url": d.evidence_url, "status": d.status, "amount_paid": d.booking.total_amount,
             "payment_status": d.booking.payment.status if d.booking.payment else None,
             "created_at": d.created_at.isoformat()} for d in rows]


@router.post("/disputes/{dispute_id}/resolve")
def resolve_dispute_endpoint(dispute_id: int, data: ResolveDisputeRequest,
                             admin: User = Depends(get_current_active_admin), db: Session = Depends(get_db)):
    """Resolve, dismiss, escalate, or resolve-with-full-refund. Every decision is audited."""
    d = resolve_dispute(db, admin.id, dispute_id, data.decision, data.notes)
    return {"id": d.id, "status": d.status}


@router.post("/stations/connectors/{connector_id}/verify-price")
def verify_connector_price(connector_id: int, admin: User = Depends(get_current_active_admin), db: Session = Depends(get_db)):
    """Marks a price as verified. Only an operator-sourced price can be verified; provider/sample/user prices cannot."""
    conn = db.query(ChargerConnector).filter(ChargerConnector.id == connector_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.price_source != "operator" or conn.pricing_per_kwh is None:
        raise HTTPException(status_code=400, detail="Only an operator-provided price can be marked verified")
    conn.price_verified = True
    audit(db, admin.id, "PRICE_VERIFIED", "ChargerConnector", conn.id)
    db.commit()
    return {"status": "verified"}


@router.post("/moderation")
def perform_moderation(
    data: ModerationActionCreate,
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Executes a binding administrative action and logs to the audit ledger."""
    execute_moderation_action(db, admin.id, data)
    return {"status": "success", "action": data.action, "target": data.target_type}


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_active_admin),
    db: Session = Depends(get_db)
):
    """Retrieves immutable security and governance audit logs."""
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "resource_type": l.resource_type,
            "resource_id": l.resource_id,
            "details_json": l.details_json,
            "created_at": l.created_at.isoformat()
        }
        for l in logs
    ]
