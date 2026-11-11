import json
import uuid
from app.core.config import settings
from app.models.marketplace import Booking
from app.models.payment import HostEarning, Payment, PaymentEvent, Refund
from app.services.razorpay_client import compute_signature
from tests.helpers import auth, book, future_slot, make_listing, make_user, pay


def _booking(client, db, kwh=20.0):
    host, driver = make_user(db, "host"), make_user(db, "driver")
    listing = make_listing(db, host, price_per_kwh=10.0)
    start, end = future_slot()
    b = book(client, driver, listing, start, end, kwh).json()
    return host, driver, listing, b


def test_payment_flow_server_priced_idempotent_and_confirms(client, db):
    host, driver, listing, b = _booking(client, db)
    assert b["total_amount"] == 264.0  # 20*10 + 20 + 2*10 = 240 ; +10% = 264

    key = uuid.uuid4().hex
    init = client.post("/api/v1/payments/initiate", headers=auth(driver), json={"booking_id": b["id"], "idempotency_key": key}).json()
    assert init["amount"] == 264.0 and init["amount_paise"] == 26400 and init["mode"] == "mock"
    again = client.post("/api/v1/payments/initiate", headers=auth(driver), json={"booking_id": b["id"], "idempotency_key": key}).json()
    assert again["payment_reference"] == init["payment_reference"] and again["razorpay_order_id"] == init["razorpay_order_id"]

    # Booking is NOT confirmed merely because an order exists
    assert client.get(f"/api/v1/marketplace/bookings/{b['id']}", headers=auth(driver)).json()["status"] == "awaiting_payment"

    sim = client.post("/api/v1/payments/sandbox/simulate", headers=auth(driver), json={"payment_reference": init["payment_reference"]}).json()
    ver = client.post("/api/v1/payments/verify", headers=auth(driver), json={"payment_reference": init["payment_reference"], **sim})
    assert ver.status_code == 200 and ver.json()["status"] == "captured"
    ver2 = client.post("/api/v1/payments/verify", headers=auth(driver), json={"payment_reference": init["payment_reference"], **sim})
    assert ver2.status_code == 200  # idempotent
    row = db.query(Booking).get(b["id"])
    db.refresh(row)
    assert row.status == "confirmed"
    earnings = db.query(HostEarning).filter(HostEarning.booking_id == b["id"]).all()
    assert len(earnings) == 1 and earnings[0].net_earnings == 240.0


def test_forged_or_mismatched_payment_proofs_are_rejected(client, db):
    host, driver, listing, b = _booking(client, db)
    other = make_user(db, "driver")
    init = client.post("/api/v1/payments/initiate", headers=auth(driver), json={"booking_id": b["id"], "idempotency_key": uuid.uuid4().hex}).json()
    ref, oid = init["payment_reference"], init["razorpay_order_id"]
    # The old documented bypass must not work anymore
    for sig in ("sandbox_valid_signature", "mock_sandbox_sig", "", "00" * 32):
        r = client.post("/api/v1/payments/verify", headers=auth(driver), json={
            "payment_reference": ref, "razorpay_order_id": oid, "razorpay_payment_id": "pay_x", "razorpay_signature": sig})
        assert r.status_code == 400, sig
    # Wrong order id
    sim = client.post("/api/v1/payments/sandbox/simulate", headers=auth(driver), json={"payment_reference": ref}).json()
    bad = {**sim, "razorpay_order_id": "order_other"}
    assert client.post("/api/v1/payments/verify", headers=auth(driver), json={"payment_reference": ref, **bad}).status_code == 400
    # Someone else cannot verify or simulate for this payment
    assert client.post("/api/v1/payments/verify", headers=auth(other), json={"payment_reference": ref, **sim}).status_code == 403
    assert client.post("/api/v1/payments/sandbox/simulate", headers=auth(other), json={"payment_reference": ref}).status_code == 404
    db.expire_all()
    assert db.query(Booking).get(b["id"]).status == "awaiting_payment"
    assert db.query(Payment).filter(Payment.payment_reference == ref).first().status == "created"


def test_mock_provider_unavailable_in_production_mode(client, db, monkeypatch):
    host, driver, listing, b = _booking(client, db)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    r = client.post("/api/v1/payments/initiate", headers=auth(driver), json={"booking_id": b["id"], "idempotency_key": uuid.uuid4().hex})
    assert r.status_code == 503
    assert client.post("/api/v1/payments/sandbox/simulate", headers=auth(driver), json={"payment_reference": "x"}).status_code == 404


def _hook(client, secret, body, event_id):
    raw = json.dumps(body).encode()
    return client.post("/api/v1/payments/webhook", content=raw, headers={
        "X-Razorpay-Signature": compute_signature(secret, raw), "X-Razorpay-Event-Id": event_id, "Content-Type": "application/json"})


def test_webhook_authentic_idempotent_and_amount_checked(client, db):
    host, driver, listing, b = _booking(client, db)
    init = client.post("/api/v1/payments/initiate", headers=auth(driver), json={"booking_id": b["id"], "idempotency_key": uuid.uuid4().hex}).json()
    body = {"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_wh1", "order_id": init["razorpay_order_id"], "amount": 26400}}}}

    raw = json.dumps(body).encode()
    assert client.post("/api/v1/payments/webhook", content=raw, headers={"X-Razorpay-Signature": "mock_sandbox_sig"}).status_code == 400
    assert client.post("/api/v1/payments/webhook", content=raw).status_code == 400
    assert client.post("/api/v1/payments/webhook", content=raw, headers={"X-Razorpay-Signature": compute_signature("wrong", raw)}).status_code == 400

    # Tampered amount is never trusted
    tampered = {"event": "payment.captured", "payload": {"payment": {"entity": {"id": "pay_wh0", "order_id": init["razorpay_order_id"], "amount": 100}}}}
    assert _hook(client, settings.RAZORPAY_WEBHOOK_SECRET, tampered, "evt_t").json()["status"] == "rejected"
    db.expire_all()
    assert db.query(Booking).get(b["id"]).status == "awaiting_payment"

    r1 = _hook(client, settings.RAZORPAY_WEBHOOK_SECRET, body, "evt_1")
    assert r1.status_code == 200 and r1.json()["status"] == "processed"
    r2 = _hook(client, settings.RAZORPAY_WEBHOOK_SECRET, body, "evt_1")
    assert r2.json()["status"] == "duplicate"
    r3 = _hook(client, settings.RAZORPAY_WEBHOOK_SECRET, body, "evt_2")  # different event, same payment: no double effects
    assert r3.status_code == 200
    db.expire_all()
    assert db.query(Booking).get(b["id"]).status == "confirmed"
    assert db.query(HostEarning).filter(HostEarning.booking_id == b["id"]).count() == 1
    assert db.query(PaymentEvent).filter(PaymentEvent.provider_event_id == "evt_1").count() == 1


def test_failed_payment_does_not_confirm_and_allows_retry(client, db):
    host, driver, listing, b = _booking(client, db)
    init = client.post("/api/v1/payments/initiate", headers=auth(driver), json={"booking_id": b["id"], "idempotency_key": uuid.uuid4().hex}).json()
    body = {"event": "payment.failed", "payload": {"payment": {"entity": {"id": "pay_f", "order_id": init["razorpay_order_id"], "error_description": "card declined"}}}}
    assert _hook(client, settings.RAZORPAY_WEBHOOK_SECRET, body, "evt_fail").status_code == 200
    db.expire_all()
    assert db.query(Booking).get(b["id"]).status == "awaiting_payment"
    assert db.query(Payment).filter(Payment.booking_id == b["id"]).first().status == "failed"
    d, sim, ver = pay(client, driver, b["id"])  # retry on the same booking works (new order)
    assert ver.status_code == 200 and ver.json()["status"] == "captured"


def test_cancellation_refund_policy_and_authorization(client, db):
    host, driver, listing, b = _booking(client, db)
    stranger = make_user(db, "driver")
    pay(client, driver, b["id"])
    # strangers cannot cancel/refund
    assert client.post(f"/api/v1/marketplace/bookings/{b['id']}/cancel", headers=auth(stranger), json={"reason": "no reason"}).status_code == 403
    assert client.post("/api/v1/payments/refund", headers=auth(stranger), json={"booking_id": b["id"], "reason": "free money"}).status_code == 403
    # driver cancels >2h before start -> full refund
    r = client.post(f"/api/v1/marketplace/bookings/{b['id']}/cancel", headers=auth(driver), json={"reason": "plans changed"})
    assert r.status_code == 200, r.text
    assert r.json()["refund_amount"] == 264.0 and r.json()["booking_status"] == "cancelled"
    db.expire_all()
    assert db.query(Payment).filter(Payment.booking_id == b["id"]).first().status == "refunded"
    assert db.query(HostEarning).filter(HostEarning.booking_id == b["id"]).first().status == "reversed"
    assert db.query(Refund).filter(Refund.booking_id == b["id"]).count() == 1
    # cancelling again is refused, no second refund
    assert client.post(f"/api/v1/marketplace/bookings/{b['id']}/cancel", headers=auth(driver), json={"reason": "again please"}).status_code == 400
    assert db.query(Refund).filter(Refund.booking_id == b["id"]).count() == 1
    # slot is free again
    assert book(client, make_user(db, "driver"), listing, *future_slot()).status_code == 201


def test_late_driver_cancellation_gets_no_refund_but_host_cancellation_does(client, db):
    from datetime import datetime, timedelta, timezone
    host, driver, listing, b = _booking(client, db)
    pay(client, driver, b["id"])
    row = db.query(Booking).get(b["id"])
    row.start_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    row.end_time = row.start_time + timedelta(hours=2)
    db.commit()
    late = client.post(f"/api/v1/marketplace/bookings/{b['id']}/cancel", headers=auth(driver), json={"reason": "running late"})
    assert late.status_code == 200 and late.json()["refund_amount"] == 0.0
    # a host cancelling a different paid booking always refunds in full
    host2, driver2, listing2, b2 = _booking(client, db)
    pay(client, driver2, b2["id"])
    row2 = db.query(Booking).get(b2["id"])
    row2.start_time = datetime.now(timezone.utc) + timedelta(minutes=45)
    row2.end_time = row2.start_time + timedelta(hours=2)
    db.commit()
    hr = client.post(f"/api/v1/marketplace/bookings/{b2['id']}/cancel", headers=auth(host2), json={"reason": "emergency"})
    assert hr.json()["refund_amount"] == 264.0
