"""Payment orders, verification, webhooks, cancellation and refunds with consistent booking/payment state."""
import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import BookingStatus, PaymentStatus, UserRoleType
from app.models.marketplace import Booking, ChargingSession
from app.models.payment import HostEarning, Payment, PaymentEvent, Refund
from app.models.user import User
from app.schemas.payment import PaymentInitiateRequest, PaymentInitiateResponse, PaymentVerifyRequest
from app.services import razorpay_client as rz
from app.services.audit import audit
from app.services.geo import as_utc
from app.services.marketplace_service import (
    booking_ctx, confirm_booking_payment, expire_stale_holds, slot_conflict,
)
from app.services.notification_service import send_event_email, send_in_app_notification


def _paise(amount: float) -> int:
    return int(round(amount * 100))


def _provider():
    try:
        return rz.get_provider()
    except rz.ProviderNotConfigured as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))


def _response(payment: Payment, booking: Booking, provider) -> PaymentInitiateResponse:
    return PaymentInitiateResponse(
        payment_reference=payment.payment_reference, booking_reference=booking.booking_reference,
        amount=payment.amount, currency=payment.currency, razorpay_order_id=payment.provider_order_id,
        razorpay_key_id=None if provider.is_mock else settings.RAZORPAY_KEY_ID,
        mode="mock" if provider.is_mock else "razorpay", amount_paise=_paise(payment.amount),
        booking_id=booking.id, user_email=booking.driver.email, user_name=booking.driver.full_name)


# ------------------------------------------------------------------ initiate

def initiate_booking_payment(db: Session, request: PaymentInitiateRequest, current_user_id: int) -> PaymentInitiateResponse:
    """Creates (or returns) the provider order for a booking. The amount always comes from the stored booking."""
    expire_stale_holds(db)
    booking = db.query(Booking).filter(Booking.id == request.booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    if booking.driver_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized booking access")
    if booking.status != BookingStatus.AWAITING_PAYMENT.value:
        detail = ("The payment window for this booking expired. Please book the slot again."
                  if booking.cancellation_reason == "payment_hold_expired"
                  else f"Booking is not awaiting payment (current status: {booking.status})")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
    provider = _provider()

    payment = db.query(Payment).filter(Payment.booking_id == booking.id).first()
    same_key = db.query(Payment).filter(Payment.idempotency_key == request.idempotency_key).first()
    if same_key and same_key.booking_id != booking.id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency key already used for another booking")
    if payment:
        if payment.status == PaymentStatus.CAPTURED.value:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking is already paid")
        if payment.status in (PaymentStatus.CREATED.value, PaymentStatus.AUTHORIZED.value) and payment.provider_order_id \
                and payment.is_mock == provider.is_mock:
            return _response(payment, booking, provider)  # one open order per booking
    ref = payment.payment_reference if payment else f"CC-PAY-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    try:
        order = provider.create_order(_paise(booking.total_amount), booking.booking_reference,
                                      {"booking_id": str(booking.id), "payment_reference": ref})
    except rz.ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not create the payment order: {exc}")
    if not payment:
        payment = Payment(payment_reference=ref, booking_id=booking.id, user_id=booking.driver_id, provider="razorpay")
        db.add(payment)
    payment.amount, payment.currency = booking.total_amount, "INR"
    payment.status = PaymentStatus.CREATED.value
    payment.provider_order_id, payment.provider_payment_id, payment.provider_signature = order["id"], None, None
    payment.idempotency_key, payment.failure_reason, payment.is_mock = request.idempotency_key, None, provider.is_mock
    audit(db, current_user_id, "PAYMENT_ORDER_CREATED", "Payment", ref, {"booking_id": booking.id, "mock": provider.is_mock})
    db.commit()
    db.refresh(payment)
    return _response(payment, booking, provider)


# ------------------------------------------------------------------ capture (shared by verify + webhook)

def _record_host_earning(db: Session, booking: Booking) -> None:
    if not db.query(HostEarning).filter(HostEarning.booking_id == booking.id).first():
        db.add(HostEarning(host_id=booking.listing.host_id, booking_id=booking.id, gross_amount=booking.total_amount,
                           platform_fee=booking.platform_fee, net_earnings=booking.host_earnings_amount, status="available"))


def mark_payment_captured(db: Session, payment: Payment, provider_payment_id: str, source: str) -> Payment:
    """Idempotent. Confirms the booking if the slot is still ours; otherwise captures then refunds automatically."""
    payment = db.query(Payment).filter(Payment.id == payment.id).with_for_update().first()
    if payment.status in (PaymentStatus.CAPTURED.value, PaymentStatus.REFUNDED.value):
        return payment
    booking = payment.booking
    payment.status = PaymentStatus.CAPTURED.value
    payment.provider_payment_id = provider_payment_id
    payment.failure_reason = None
    payment.updated_at = datetime.now(timezone.utc)
    audit(db, payment.user_id, "PAYMENT_CAPTURED", "Payment", payment.id, {"source": source, "amount": payment.amount})

    recoverable = booking.status == BookingStatus.AWAITING_PAYMENT.value or (
        booking.status == BookingStatus.CANCELLED.value and booking.cancellation_reason == "payment_hold_expired")
    if recoverable and not slot_conflict(db, booking.listing_id, as_utc(booking.start_time), as_utc(booking.end_time), booking.id) \
            and as_utc(booking.end_time) > datetime.now(timezone.utc):
        _record_host_earning(db, booking)
        db.commit()
        confirm_booking_payment(db, booking)
    else:
        db.commit()
        _issue_refund(db, payment, payment.amount, "Automatic refund: the booking could no longer be honoured", None)
        db.commit()
        send_event_email(db, booking.driver, "refund_processed",
                         {"ref": booking.booking_reference, "amount": f"{payment.amount:.2f}", "state": "being processed"},
                         dedupe_key=f"auto_refund:{payment.id}")
    db.refresh(payment)
    return payment


def verify_and_capture_payment(db: Session, data: PaymentVerifyRequest, current_user_id: int) -> Payment:
    payment = db.query(Payment).filter(Payment.payment_reference == data.payment_reference).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment record not found")
    if payment.user_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized payment verification")
    if payment.status in (PaymentStatus.CAPTURED.value, PaymentStatus.REFUNDED.value):
        return payment
    if data.razorpay_order_id != payment.provider_order_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order does not match this payment")
    provider = _provider()
    if payment.is_mock != provider.is_mock:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment mode mismatch")
    if not rz.verify_checkout_signature(data.razorpay_order_id, data.razorpay_payment_id, data.razorpay_signature,
                                        provider.checkout_secret):
        audit(db, current_user_id, "PAYMENT_SIGNATURE_REJECTED", "Payment", payment.id, commit=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payment verification failed: invalid transaction signature")
    if not provider.is_mock:  # confirm with the provider itself: order, amount, and captured state
        try:
            remote = provider.fetch_payment(data.razorpay_payment_id)
            if remote.get("status") == "authorized":
                remote = provider.capture_payment(data.razorpay_payment_id, _paise(payment.amount))
        except rz.ProviderError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Could not confirm the payment with the provider: {exc}")
        if (remote.get("order_id") not in (None, payment.provider_order_id)
                or remote.get("amount") not in (None, _paise(payment.amount)) or remote.get("status") != "captured"):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The provider does not report this payment as completed")
    return mark_payment_captured(db, payment, data.razorpay_payment_id, "checkout_verify")


def simulate_mock_payment(db: Session, payment_reference: str, user_id: int) -> Dict[str, str]:
    """Development only: produces a correctly signed mock payment so the normal /verify path is exercised."""
    if not settings.mock_payments_allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    payment = db.query(Payment).filter(Payment.payment_reference == payment_reference).first()
    if not payment or payment.user_id != user_id or not payment.is_mock:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    provider = rz.MockProvider()
    pid, sig = provider.simulate_payment(payment.provider_order_id)
    return {"razorpay_order_id": payment.provider_order_id, "razorpay_payment_id": pid, "razorpay_signature": sig}


# ------------------------------------------------------------------ webhook

def handle_webhook(db: Session, raw_body: bytes, signature: Optional[str], event_id: Optional[str]) -> Dict[str, str]:
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook secret is not configured")
    if not signature or not rz.verify_webhook_signature(raw_body, signature, secret):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw_body)
        event = payload["event"]
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Malformed webhook payload")
    eid = event_id or hashlib.sha256(raw_body).hexdigest()
    if db.query(PaymentEvent).filter(PaymentEvent.provider_event_id == eid).first():
        return {"status": "duplicate"}

    entity = (((payload.get("payload") or {}).get("payment") or {}).get("entity")) or {}
    order_entity = (((payload.get("payload") or {}).get("order") or {}).get("entity")) or {}
    order_id = entity.get("order_id") or order_entity.get("id")
    payment = db.query(Payment).filter(Payment.provider_order_id == order_id).first() if order_id else None
    outcome, pay_id = "ignored", payment.id if payment else None
    try:
        if event in ("payment.captured", "order.paid") and payment:
            if entity.get("amount") not in (None, _paise(payment.amount)):
                outcome = "rejected"  # amount mismatch is never trusted
                audit(db, payment.user_id, "WEBHOOK_AMOUNT_MISMATCH", "Payment", payment.id)
            else:
                mark_payment_captured(db, payment, entity.get("id") or payment.provider_payment_id or "unknown", "webhook")
                outcome = "processed"
        elif event == "payment.failed" and payment and payment.status == PaymentStatus.CREATED.value:
            payment.status = PaymentStatus.FAILED.value
            payment.failure_reason = (entity.get("error_description") or "payment failed")[:250]
            audit(db, payment.user_id, "PAYMENT_FAILED", "Payment", payment.id)
            db.commit()
            b = payment.booking
            send_event_email(db, b.driver, "payment_failed", booking_ctx(b), dedupe_key=f"payment_failed:{payment.id}:{eid}")
            outcome = "processed"
        elif event in ("refund.processed", "refund.failed"):
            rid = (((payload.get("payload") or {}).get("refund") or {}).get("entity") or {}).get("id")
            refund = db.query(Refund).filter(Refund.provider_refund_id == rid).first() if rid else None
            if refund:
                pay_id = refund.payment_id
                if event == "refund.processed":
                    refund.status = "processed"
                    refund.payment.status = PaymentStatus.REFUNDED.value
                    send_event_email(db, refund.payment.booking.driver, "refund_processed",
                                     {"ref": refund.payment.booking.booking_reference, "amount": f"{refund.amount:.2f}", "state": "processed"},
                                     dedupe_key=f"refund_processed:{refund.id}")
                else:
                    refund.status, refund.failure_reason = "failed", "provider reported refund failure"
                audit(db, None, f"WEBHOOK_{event.upper().replace('.', '_')}", "Refund", refund.id)
                outcome = "processed"
        db.add(PaymentEvent(provider_event_id=eid, event_type=event, payment_id=pay_id, outcome=outcome))
        db.commit()
    except IntegrityError:
        db.rollback()
        return {"status": "duplicate"}
    return {"status": outcome}


# ------------------------------------------------------------------ refunds and cancellation

def _issue_refund(db: Session, payment: Payment, amount: float, reason: str, actor_id: Optional[int]) -> Refund:
    """Starts a provider refund. Raises HTTPException(502) before any state change if the provider call fails."""
    existing = db.query(Refund).filter(Refund.payment_id == payment.id, Refund.status.in_(["initiated", "processed"])).first()
    if existing:
        return existing
    provider = _provider()
    try:
        resp = provider.refund_payment(payment.provider_payment_id, _paise(amount),
                                       {"booking_id": str(payment.booking_id), "reason": reason[:100]})
    except rz.ProviderError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"The refund could not be started: {exc}. Nothing was changed; please try again.")
    done = resp.get("status") == "processed"
    refund = Refund(payment_id=payment.id, booking_id=payment.booking_id, amount=round(amount, 2), reason=reason[:255],
                    status="processed" if done else "initiated", provider_refund_id=resp.get("id"), initiated_by_id=actor_id)
    db.add(refund)
    if done and abs(amount - payment.amount) < 0.01:
        payment.status = PaymentStatus.REFUNDED.value
    db.flush()
    audit(db, actor_id, "REFUND_INITIATED", "Refund", refund.id, {"amount": refund.amount, "status": refund.status, "reason": reason[:100]})
    return refund


def cancel_booking(db: Session, booking_id: int, reason: str, actor: User) -> Dict[str, Any]:
    """
    Cancels a booking and applies the refund policy:
      - host or admin cancels  -> full refund
      - driver cancels >= FREE_CANCELLATION_HOURS before start -> full refund; later -> no refund
    """
    expire_stale_holds(db)
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    is_driver, is_host = booking.driver_id == actor.id, booking.listing.host_id == actor.id
    is_admin = actor.has_role(UserRoleType.ADMIN.value)
    if not (is_driver or is_host or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized booking access")
    if booking.status not in (BookingStatus.AWAITING_PAYMENT.value, BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"A booking that is {booking.status.replace('_', ' ')} cannot be cancelled. Open a dispute instead.")
    now = datetime.now(timezone.utc)
    hours_before = (as_utc(booking.start_time) - now).total_seconds() / 3600.0
    full = (not is_driver) or hours_before >= settings.FREE_CANCELLATION_HOURS
    payment = booking.payment
    paid = payment is not None and payment.status == PaymentStatus.CAPTURED.value

    refund = None
    if paid and full:
        refund = _issue_refund(db, payment, payment.amount, reason, actor.id)
    booking.status = BookingStatus.CANCELLED.value
    booking.cancellation_reason, booking.cancelled_by_id, booking.cancelled_at = reason[:255], actor.id, now
    booking.payment_hold_expires_at = None
    if booking.session:
        booking.session.status = "cancelled"
    if paid and full:
        earning = db.query(HostEarning).filter(HostEarning.booking_id == booking.id).first()
        if earning:
            earning.status = "reversed"
    audit(db, actor.id, "BOOKING_CANCELLED", "Booking", booking.id,
          {"by": "driver" if is_driver else ("host" if is_host else "admin"), "refunded": bool(refund), "hours_before_start": round(hours_before, 1)})
    db.commit()

    if paid and not full:
        refund_line = f"Because it was cancelled less than {settings.FREE_CANCELLATION_HOURS:g} hours before the start, no refund applies under the cancellation policy."
    elif refund:
        refund_line = f"A refund of INR {refund.amount:.2f} has been started."
    else:
        refund_line = "No payment had been completed, so nothing was charged."
    ctx = {**booking_ctx(booking), "refund_line": refund_line}
    for user in {booking.driver, booking.listing.host}:
        send_event_email(db, user, "booking_cancelled", ctx, dedupe_key=f"booking_cancelled:{booking.id}:{user.id}")
        send_in_app_notification(db, user.id, "Booking cancelled", f"Booking {booking.booking_reference} was cancelled. {refund_line}",
                                 "booking_cancelled", f"/bookings/{booking.id}")
    if refund:
        db.refresh(refund)
    return {"booking_id": booking.id, "booking_status": booking.status, "refund": refund,
            "refund_amount": refund.amount if refund else 0.0, "message": refund_line}


def admin_refund_for_dispute(db: Session, booking: Booking, admin_id: int, reason: str) -> Optional[Refund]:
    """Full refund of a captured payment decided by an administrator while resolving a dispute."""
    payment = booking.payment
    if not payment or payment.status != PaymentStatus.CAPTURED.value:
        return None
    refund = _issue_refund(db, payment, payment.amount, reason, admin_id)
    earning = db.query(HostEarning).filter(HostEarning.booking_id == booking.id).first()
    if earning:
        earning.status = "reversed"
    return refund
