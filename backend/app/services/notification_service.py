"""In-app notifications plus transactional email for booking, payment and account events."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.community import Notification
from app.models.user import User
from app.services.email_service import queue_email


def send_in_app_notification(
    db: Session, user_id: int, title: str, message: str, notification_type: str,
    action_link: Optional[str] = None, commit: bool = True,
) -> Notification:
    """Dispatches a persistent notification to the user's notification center."""
    notif = Notification(user_id=user_id, title=title, message=message,
                         notification_type=notification_type, action_link=action_link, is_read=False)
    db.add(notif)
    if commit:
        db.commit()
        db.refresh(notif)
    return notif


def _fmt_time(dt: datetime) -> str:
    from app.services.geo import IST, as_utc
    return as_utc(dt).astimezone(IST).strftime("%d %b %Y, %I:%M %p IST")


# template -> (subject, body). Bodies never contain passwords, card data or payment secrets.
_TEMPLATES: Dict[str, tuple] = {
    "email_verification": ("Verify your ChargeCircle email",
        "Hi {name},\n\nConfirm your email address using this link (valid {hours} hours):\n{link}\n\nIf you did not create an account, ignore this email."),
    "password_reset": ("Reset your ChargeCircle password",
        "Hi {name},\n\nUse this link to choose a new password (valid {minutes} minutes):\n{link}\n\nIf you did not request this, ignore this email; your password is unchanged."),
    "password_changed": ("Security alert: your ChargeCircle password was changed",
        "Hi {name},\n\nYour password was just changed. If this was not you, reset it immediately at {link} and contact support."),
    "booking_requested_host": ("New booking at {listing}",
        "Hi {name},\n\n{driver} reserved '{listing}' for {start} to {end} (ref {ref}). It becomes confirmed once payment is verified."),
    "booking_confirmed_driver": ("Booking confirmed: {ref}",
        "Hi {name},\n\nYour booking {ref} at '{listing}' on {start} is confirmed and paid. The exact address and access notes are now visible in your booking: {link}"),
    "booking_confirmed_host": ("Booking paid: {ref}",
        "Hi {name},\n\nBooking {ref} at '{listing}' ({start} to {end}) has been paid and confirmed."),
    "booking_cancelled": ("Booking cancelled: {ref}",
        "Hi {name},\n\nBooking {ref} at '{listing}' ({start}) was cancelled. {refund_line}"),
    "payment_failed": ("Payment did not complete for {ref}",
        "Hi {name},\n\nThe payment for booking {ref} did not complete, so the booking is not confirmed. You can retry until the hold expires: {link}"),
    "refund_processed": ("Refund update for {ref}",
        "Hi {name},\n\nA refund of INR {amount} for booking {ref} is {state}. Banks can take several business days to show it."),
    "booking_reminder": ("Reminder: charging session {when}",
        "Hi {name},\n\nYour booking {ref} at '{listing}' starts {start}. Details: {link}"),
}


def send_event_email(db: Session, user: User, template: str, ctx: Dict, dedupe_key: Optional[str] = None):
    subject_t, body_t = _TEMPLATES[template]
    data = {"name": user.full_name, **ctx}
    try:
        return queue_email(db, user_id=user.id, to_email=user.email, template=template,
                           subject=subject_t.format(**data), body=body_t.format(**data), dedupe_key=dedupe_key)
    except Exception:  # never break the caller
        return None


def booking_ctx(booking) -> Dict:
    return {
        "ref": booking.booking_reference,
        "listing": booking.listing.title,
        "driver": booking.driver.full_name,
        "start": _fmt_time(booking.start_time),
        "end": _fmt_time(booking.end_time),
        "link": f"{settings.FRONTEND_URL}/bookings/{booking.id}",
    }


def send_due_reminders(db: Session, now: Optional[datetime] = None) -> int:
    """Emails drivers and hosts about confirmed bookings starting within 24h. Safe to run repeatedly."""
    from app.models.enums import BookingStatus
    from app.models.marketplace import Booking
    from app.services.geo import as_utc
    now = now or datetime.now(timezone.utc)
    horizon = now + timedelta(hours=24)
    sent = 0
    for b in db.query(Booking).filter(Booking.status == BookingStatus.CONFIRMED.value,
                                       Booking.start_time > now, Booking.start_time <= horizon).all():
        ctx = {**booking_ctx(b), "when": "within 24 hours"}
        for user in (b.driver, b.listing.host):
            if send_event_email(db, user, "booking_reminder", ctx, dedupe_key=f"reminder24:{b.id}:{user.id}"):
                sent += 1
    return sent
