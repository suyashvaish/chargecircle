from typing import List
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.payment import HostEarning, Payment
from app.models.user import User
from app.schemas.payment import (
    CancelOut, HostEarningOut, PaymentInitiateRequest, PaymentInitiateResponse, PaymentOut, PaymentVerifyRequest,
    RefundRequest, SandboxSimulateOut, SandboxSimulateRequest,
)
from app.services.auth_service import get_current_user
from app.services.payment_service import (
    cancel_booking, handle_webhook, initiate_booking_payment, simulate_mock_payment, verify_and_capture_payment,
)

router = APIRouter(prefix="/payments", tags=["Payments, Refunds & Host Settlement"])


@router.post("/initiate", response_model=PaymentInitiateResponse)
def initiate_payment(data: PaymentInitiateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Creates the payment order on the backend. The amount is read from the booking, never from the client."""
    return initiate_booking_payment(db, data, current_user.id)


@router.post("/verify", response_model=PaymentOut)
def verify_payment(data: PaymentVerifyRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Server-side HMAC-SHA256 verification (plus provider confirmation in real mode)."""
    return verify_and_capture_payment(db, data, current_user.id)


@router.post("/sandbox/simulate", response_model=SandboxSimulateOut)
def sandbox_simulate(data: SandboxSimulateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """DEVELOPMENT ONLY (404 unless PAYMENT_MODE=mock and ENVIRONMENT != production)."""
    return simulate_mock_payment(db, data.payment_reference, current_user.id)


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    x_razorpay_event_id: str = Header(None, alias="X-Razorpay-Event-Id"),
    db: Session = Depends(get_db),
):
    """Authenticated (HMAC of the raw body) and idempotent (unique event id) provider webhook."""
    body = await request.body()
    return handle_webhook(db, body, x_razorpay_signature, x_razorpay_event_id)


@router.post("/refund", response_model=CancelOut)
def request_refund(data: RefundRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Cancels the booking and refunds according to policy. Only the driver, the host, or an admin may call it."""
    return cancel_booking(db, data.booking_id, data.reason, current_user)


@router.get("/earnings", response_model=List[HostEarningOut])
def get_host_earnings(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(HostEarning).filter(HostEarning.host_id == current_user.id).order_by(HostEarning.created_at.desc()).all()
