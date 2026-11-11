import pytest
from datetime import datetime, timedelta, timezone
from app.core.config import Settings, settings
from app.models.community import EmailLog
from app.models.user import AuthToken, User
from app.core.security import verify_password
from app.services import email_service
from app.services.notification_service import send_due_reminders
from tests.helpers import auth, book, future_slot, make_listing, make_user, pay


@pytest.fixture
def outbox(monkeypatch):
    sent = []
    monkeypatch.setattr(email_service, "_deliver", lambda to, subject, body: sent.append((to, subject, body)))
    return sent


def _token_from(outbox, kind):
    body = next(b for (_, s, b) in reversed(outbox) if kind in s.lower())
    link = next(w for w in body.split() if "token=" in w)
    return link.split("token=")[1].split("&")[0]


def test_password_reset_end_to_end_single_use(client, db, outbox):
    u = make_user(db, "driver", email="reset_me@example.com", password="OldPassw0rd!")
    unknown = client.post("/api/v1/auth/password-reset/request", json={"email": "nobody@example.com"})
    known = client.post("/api/v1/auth/password-reset/request", json={"email": "reset_me@example.com"})
    assert unknown.status_code == known.status_code == 200 and unknown.json() == known.json()  # no account enumeration
    assert len(outbox) == 1 and outbox[0][0] == "reset_me@example.com"
    token = _token_from(outbox, "reset")
    assert db.query(AuthToken).filter(AuthToken.token_hash == token).first() is None  # only the hash is stored

    bad = {"email": "reset_me@example.com", "reset_token": "nope", "new_password": "NewPassw0rd!x"}
    assert client.post("/api/v1/auth/password-reset/confirm", json=bad).status_code == 400
    assert client.post("/api/v1/auth/password-reset/confirm", json={**bad, "reset_token": token, "email": "other@example.com"}).status_code == 400
    ok = client.post("/api/v1/auth/password-reset/confirm", json={**bad, "reset_token": token})
    assert ok.status_code == 200
    db.refresh(u)
    assert verify_password("NewPassw0rd!x", u.hashed_password) and not verify_password("OldPassw0rd!", u.hashed_password)
    assert client.post("/api/v1/auth/login", json={"email": "reset_me@example.com", "password": "NewPassw0rd!x"}).status_code == 200
    assert client.post("/api/v1/auth/password-reset/confirm", json={**bad, "reset_token": token}).status_code == 400  # single use
    assert any("password was changed" in s for (_, s, _b) in outbox)  # security alert


def test_expired_reset_token_and_rate_limit(client, db, outbox):
    make_user(db, "driver", email="exp@example.com")
    client.post("/api/v1/auth/password-reset/request", json={"email": "exp@example.com"})
    token = _token_from(outbox, "reset")
    row = db.query(AuthToken).filter(AuthToken.purpose == "password_reset").first()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post("/api/v1/auth/password-reset/confirm", json={"email": "exp@example.com", "reset_token": token, "new_password": "BrandNewPass1!"}).status_code == 400
    for _ in range(5):
        client.post("/api/v1/auth/password-reset/request", json={"email": "exp@example.com"})
    assert len([1 for (_, s, _b) in outbox if "reset" in s.lower()]) <= 3


def test_email_verification_on_register(client, db, outbox):
    r = client.post("/api/v1/auth/register", json={"email": "newbie@example.com", "password": "Newbie123!pass", "full_name": "New Bie", "phone_number": "+91 90000 00000", "role": "driver"})
    assert r.status_code == 201
    token = _token_from(outbox, "verify")
    assert db.query(User).filter(User.email == "newbie@example.com").first().is_verified is False
    assert client.post("/api/v1/auth/verify-email", json={"token": "garbage"}).status_code == 400
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 200
    assert db.query(User).filter(User.email == "newbie@example.com").first().is_verified is True
    assert client.post("/api/v1/auth/verify-email", json={"token": token}).status_code == 400


def test_booking_emails_sent_once_and_without_secrets(client, db, outbox):
    host, driver = make_user(db, "host"), make_user(db, "driver")
    l = make_listing(db, host)
    b = book(client, driver, l, *future_slot()).json()
    d, sim, ver = pay(client, driver, b["id"])
    subjects = [(to, s) for (to, s, _b) in outbox]
    assert (host.email, f"New booking at {l.title}") in subjects
    assert sum(1 for to, s in subjects if s.startswith("Booking confirmed")) == 1 and any(to == host.email and s.startswith("Booking paid") for to, s in subjects)
    n = len(outbox)
    client.post("/api/v1/payments/verify", headers=auth(driver), json={"payment_reference": d["payment_reference"], **sim})  # retry
    assert len(outbox) == n  # retries send nothing new
    blob = " ".join(b for (_, _s, b) in outbox)
    assert "Passw0rd" not in blob and sim["razorpay_signature"] not in blob
    logs = db.query(EmailLog).all()
    assert logs and all(not hasattr(x, "body") for x in logs) and all(x.status in ("sent", "skipped") for x in logs)


def test_reminders_are_deduplicated(client, db, outbox):
    host, driver = make_user(db, "host"), make_user(db, "driver")
    l = make_listing(db, host)
    b = book(client, driver, l, *future_slot()).json()
    pay(client, driver, b["id"])
    from app.models.marketplace import Booking
    row = db.query(Booking).get(b["id"])
    row.start_time = datetime.now(timezone.utc) + timedelta(hours=5); row.end_time = row.start_time + timedelta(hours=2); db.commit()
    before = len(outbox)
    assert send_due_reminders(db) == 2 and len(outbox) == before + 2
    assert send_due_reminders(db) == 0 and len(outbox) == before + 2


def test_email_failure_is_logged_not_raised(client, db, monkeypatch):
    def boom(*a, **k):
        raise email_service.EmailDeliveryError("SMTPAuthenticationError")
    monkeypatch.setattr(email_service, "_deliver", boom)
    r = client.post("/api/v1/auth/register", json={"email": "fail@example.com", "password": "Newbie123!pass", "full_name": "Fail Mail", "phone_number": "+91 90000 00001", "role": "driver"})
    assert r.status_code == 201  # registration succeeds even though email could not be delivered
    log = db.query(EmailLog).filter(EmailLog.to_email == "fail@example.com").first()
    assert log.status == "failed" and log.error == "SMTPAuthenticationError"


def test_production_refuses_unsafe_configuration():
    base = dict(_env_file=None)
    unsafe = Settings(ENVIRONMENT="production", **base)
    problems = " | ".join(unsafe.production_problems())
    for needle in ("SECRET_KEY", "PAYMENT_MODE", "PostgreSQL", "smtp", "FRONTEND_URL"):
        assert needle in problems or needle.lower() in problems.lower(), needle
    assert any("CORS" in p for p in Settings(ENVIRONMENT="production", CORS_ORIGINS="*", **base).production_problems())
    with pytest.raises(RuntimeError):
        unsafe.validate_for_runtime()
    safe = Settings(ENVIRONMENT="production", SECRET_KEY="x" * 48, DATABASE_URL="postgresql+psycopg2://u:p@db/cc", CORS_ORIGINS="https://app.example.in",
                    PAYMENT_MODE="razorpay", RAZORPAY_KEY_ID="rzp_live_x", RAZORPAY_KEY_SECRET="s", RAZORPAY_WEBHOOK_SECRET="w", EMAIL_BACKEND="smtp",
                    SMTP_HOST="smtp.example.in", SMTP_USER="u", SMTP_PASSWORD="p", FRONTEND_URL="https://app.example.in", **base)
    assert safe.production_problems() == [] and safe.mock_payments_allowed is False
    assert Settings(ENVIRONMENT="production", PAYMENT_MODE="mock", **base).mock_payments_allowed is False
    assert "*" not in safe.cors_origins_list


def test_cors_is_not_wildcard_and_health(client):
    r = client.options("/api/v1/discovery/stations", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") != "*" and "evil.example" not in (r.headers.get("access-control-allow-origin") or "")
    assert client.get("/health").json()["status"] == "healthy"
    ready = client.get("/health/ready")
    assert ready.status_code == 200 and ready.json()["database"] == "ok" and "secret" not in ready.text.lower().replace("webhook_secret_configured", "")
