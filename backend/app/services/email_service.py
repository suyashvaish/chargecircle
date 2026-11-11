"""Transactional email with a configurable backend, delivery logging and de-duplication."""
import logging
import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Dict, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.community import EmailLog

logger = logging.getLogger("chargecircle.email")
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email")


class EmailDeliveryError(Exception):
    pass


def _deliver(to_email: str, subject: str, body: str) -> None:
    backend = settings.EMAIL_BACKEND
    if backend == "smtp":
        if not (settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD):
            raise EmailDeliveryError("SMTP is not configured (SMTP_HOST/SMTP_USER/SMTP_PASSWORD)")
        msg = EmailMessage()
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body)
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT_SECONDS) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls(context=ssl.create_default_context())
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailDeliveryError(f"{type(exc).__name__}") from exc
    elif backend == "console":
        if settings.is_production:
            raise EmailDeliveryError("console email backend is not allowed in production")
        print(f"\n--- EMAIL (console backend, development only) ---\nTo: {to_email}\nSubject: {subject}\n\n{body}\n---", flush=True)
    elif backend == "disabled":
        logger.info("email disabled: would send '%s'", subject)
    else:
        raise EmailDeliveryError(f"unknown EMAIL_BACKEND '{backend}'")


def _send_log(log_id: int, subject: str, body: str, db: Optional[Session] = None) -> None:
    own = db is None
    session = db or SessionLocal()
    try:
        log = session.query(EmailLog).filter(EmailLog.id == log_id).first()
        if not log:
            return
        try:
            _deliver(log.to_email, subject, body)
            log.status = "sent" if settings.EMAIL_BACKEND != "disabled" else "skipped"
            log.sent_at = datetime.now(timezone.utc)
            log.error = None
        except EmailDeliveryError as exc:
            log.status = "failed"
            log.error = str(exc)[:250]
            logger.warning("email delivery failed (template=%s): %s", log.template, exc)
        session.commit()
    finally:
        if own:
            session.close()


def queue_email(db: Session, *, user_id: Optional[int], to_email: str, template: str, subject: str,
                body: str, dedupe_key: Optional[str] = None) -> Optional[EmailLog]:
    """
    Records and dispatches an email. Retried webhooks/jobs with the same dedupe_key send nothing twice.
    Never raises: a delivery problem must not break the business operation that triggered it.
    """
    if dedupe_key:
        if db.query(EmailLog).filter(EmailLog.dedupe_key == dedupe_key).first():
            return None
    log = EmailLog(user_id=user_id, to_email=to_email, template=template, dedupe_key=dedupe_key, status="queued")
    db.add(log)
    try:
        db.commit()
    except IntegrityError:  # concurrent duplicate
        db.rollback()
        return None
    db.refresh(log)
    try:
        if settings.EMAIL_SEND_SYNC:
            _send_log(log.id, subject, body, db=db)
        else:
            _executor.submit(_send_log, log.id, subject, body)
    except Exception:  # pragma: no cover - defensive
        logger.exception("could not dispatch email")
    return log
