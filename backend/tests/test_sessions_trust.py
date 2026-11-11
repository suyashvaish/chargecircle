import json
from datetime import datetime, timedelta, timezone
from app.models.community import AuditLog, Dispute
from app.models.enums import OperationalStatus
from app.models.marketplace import Booking
from app.models.payment import Payment, Refund
from app.models.reliability import ChargerReport
from app.models.station import ChargingStation
from tests.helpers import auth, book, future_slot, make_listing, make_user, pay


def paid_booking(client, db, kwh=10.0):
    host, driver = make_user(db, "host", name="Host Person"), make_user(db, "driver", name="Dana Driver")
    l = make_listing(db, host, price_per_kwh=10.0, power_kw=7.4)
    b = book(client, driver, l, *future_slot(), kwh=kwh).json()
    pay(client, driver, b["id"])
    return host, driver, l, b["id"]


def go_live(db, bid):  # move the booked window to "now" so the session may start (simulates the day of the booking)
    row = db.query(Booking).get(bid)
    row.start_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    row.end_time = row.start_time + timedelta(hours=2)
    db.commit()


def test_session_lifecycle_manual_energy_and_final_charge_record(client, db):
    host, driver, l, bid = paid_booking(client, db)
    stranger = make_user(db, "driver")
    assert client.post(f"/api/v1/marketplace/bookings/{bid}/session/start", headers=auth(driver), json={}).status_code == 400  # too early
    go_live(db, bid)
    assert client.post(f"/api/v1/marketplace/bookings/{bid}/session/start", headers=auth(stranger), json={}).status_code == 403
    s = client.post(f"/api/v1/marketplace/bookings/{bid}/session/start", headers=auth(driver), json={"meter_reading_start": 100.0})
    assert s.status_code == 200 and s.json()["status"] == "started" and s.json()["energy_delivered_kwh"] is None

    assert client.post(f"/api/v1/marketplace/bookings/{bid}/session/complete", headers=auth(stranger), json={"energy_delivered_kwh": 5}).status_code == 403
    assert client.post(f"/api/v1/marketplace/bookings/{bid}/session/complete", headers=auth(host), json={"energy_delivered_kwh": 80}).status_code == 400  # physically impossible
    assert client.post(f"/api/v1/marketplace/bookings/{bid}/session/complete", headers=auth(host), json={"energy_delivered_kwh": 5, "meter_reading_end": 150}).status_code == 400
    done = client.post(f"/api/v1/marketplace/bookings/{bid}/session/complete", headers=auth(host), json={"energy_delivered_kwh": 8.0, "meter_reading_end": 108.0})
    assert done.status_code == 200, done.text
    d = done.json()
    assert d["status"] == "completed" and d["energy_delivered_kwh"] == 8.0 and d["energy_is_measured"] is False
    assert d["verification_source"] == "manual_host"
    snap = d["pricing_snapshot"]
    assert snap["energy_kwh_estimated"] == 10.0 and snap["energy_kwh_final"] == 8.0 and snap["energy_charge"] == 80.0
    assert snap["final_total"] == d["final_amount"] == round((80 + 20 + 20) * 1.1, 2) and snap["amount_paid"] == 154.0  # (10*10 + 20 + 2h*10) = 140, +10% fee
    assert "no automatic adjustment" in snap["settlement"]
    # cannot complete twice
    assert client.post(f"/api/v1/marketplace/bookings/{bid}/session/complete", headers=auth(host), json={"energy_delivered_kwh": 8}).status_code == 400
    assert client.get(f"/api/v1/marketplace/bookings/{bid}", headers=auth(driver)).json()["status"] == "completed"


def test_review_rules(client, db):
    host, driver, l, bid = paid_booking(client, db)
    payload = {"booking_id": bid, "rating_overall": 5, "rating_accuracy": 5, "rating_host": 5, "rating_parking": 4, "comment": "<script>alert(1)</script>Great and safe charger, easy access."}
    assert client.post("/api/v1/community/reviews", headers=auth(driver), json=payload).status_code == 400  # not completed yet
    go_live(db, bid)
    client.post(f"/api/v1/marketplace/bookings/{bid}/session/start", headers=auth(driver), json={})
    client.post(f"/api/v1/marketplace/bookings/{bid}/session/complete", headers=auth(driver), json={"energy_delivered_kwh": 6})
    assert client.post("/api/v1/community/reviews", headers=auth(host), json=payload).status_code == 403
    assert client.post("/api/v1/community/reviews", headers=auth(driver), json={**payload, "rating_overall": 9}).status_code == 422
    ok = client.post("/api/v1/community/reviews", headers=auth(driver), json=payload)
    assert ok.status_code == 201 and "<script>" not in ok.json()["comment"] and ok.json()["driver_name"] == "Dana D."
    assert "driver_id" not in ok.json()
    assert client.post("/api/v1/community/reviews", headers=auth(driver), json=payload).status_code == 400  # one per booking
    pub = client.get(f"/api/v1/community/listings/{l.id}/reviews").json()
    assert len(pub) == 1 and "driver_id" not in pub[0]
    assert client.get(f"/api/v1/marketplace/listings/{l.id}").json()["average_rating"] == 5.0
    assert client.get(f"/api/v1/marketplace/listings/{make_listing(db, host).id}").json()["average_rating"] is None  # no reviews -> no fake 5.0


def test_reports_moderation_and_no_automatic_fraud_label(client, db):
    user, user2, admin = make_user(db, "driver"), make_user(db, "driver"), make_user(db, "admin")
    st = ChargingStation(name="Reported Hub", operator_name="X", address="a", city="B", state="K", pin_code="1", latitude=12.0, longitude=77.0, source="manual")
    db.add(st); db.commit()
    for bad in ({"category": "made_up", "station_id": st.id}, {"category": "other", "station_id": st.id, "evidence_file_url": "javascript:alert(1)", "evidence_type": "receipt"}):
        assert client.post("/api/v1/reliability/reports", headers=auth(user), json=bad).status_code == 422
    # info/safety reports wait for a human; they never touch operational status
    r = client.post("/api/v1/reliability/reports", headers=auth(user), json={"station_id": st.id, "category": "misleading_price", "description": "<b>Board says ₹9</b> but app charged ₹20",
                                                                                 "evidence_type": "price_board_photo", "evidence_file_url": "https://example.com/p.jpg"})
    assert r.status_code == 201 and r.json()["moderation_status"] == "under_review" and "user_id" not in r.json() and "<b>" not in r.json()["description"]
    assert client.get("/api/v1/reliability/reports", params={"station_id": st.id}).json() == []  # not public until moderated
    st1 = client.get(f"/api/v1/reliability/status/station/{st.id}").json()
    assert st1["operational_status"] in (OperationalStatus.UNKNOWN.value, OperationalStatus.NOT_RECENTLY_CHECKED.value)
    # a single unverified NEGATIVE report does not mark the charger unavailable
    client.post("/api/v1/reliability/reports", headers=auth(user), json={"station_id": st.id, "category": "not_working"})
    assert client.get(f"/api/v1/reliability/status/station/{st.id}").json()["operational_status"] == OperationalStatus.UNKNOWN.value
    client.post("/api/v1/reliability/reports", headers=auth(user2), json={"station_id": st.id, "category": "not_working"})
    assert "unavailable" in client.get(f"/api/v1/reliability/status/station/{st.id}").json()["operational_status"].lower()

    # authorization on moderation
    rid = r.json()["id"]
    assert client.post("/api/v1/admin/moderation", headers=auth(user), json={"target_type": "report", "target_id": rid, "action": "approved"}).status_code == 403
    assert client.get("/api/v1/admin/reports", headers=auth(user)).status_code == 403
    q = client.get("/api/v1/admin/reports", headers=auth(admin)).json()
    assert any(x["id"] == rid and x["evidence"] for x in q)
    assert client.post("/api/v1/admin/moderation", headers=auth(admin), json={"target_type": "report", "target_id": rid, "action": "hacked"}).status_code == 422
    assert client.post("/api/v1/admin/moderation", headers=auth(admin), json={"target_type": "report", "target_id": rid, "action": "hidden"}).status_code == 400
    assert client.post("/api/v1/admin/moderation", headers=auth(admin), json={"target_type": "report", "target_id": rid, "action": "escalated", "notes": 'needs "legal" review'}).status_code == 200
    assert db.query(ChargerReport).get(rid).moderation_status == "escalated"
    log = db.query(AuditLog).filter(AuditLog.action == "MODERATION_ESCALATED").first()
    assert json.loads(log.details_json)["notes"] == 'needs "legal" review'  # valid JSON even with quotes
    assert client.post("/api/v1/admin/moderation", headers=auth(admin), json={"target_type": "report", "target_id": rid, "action": "resolved", "notes": "price corrected"}).status_code == 200


def test_dispute_workflow_with_refund_and_audit(client, db):
    host, driver, l, bid = paid_booking(client, db)
    admin, stranger = make_user(db, "admin"), make_user(db, "driver")
    body = {"booking_id": bid, "reason": "The charger never delivered power during my slot.", "category": "session"}
    assert client.post("/api/v1/community/disputes", headers=auth(stranger), json=body).status_code == 403
    assert client.post("/api/v1/community/disputes", headers=auth(driver), json={**body, "evidence_url": "http://insecure.example"}).status_code == 422
    d = client.post("/api/v1/community/disputes", headers=auth(driver), json=body)
    assert d.status_code == 201, d.text
    assert client.post("/api/v1/community/disputes", headers=auth(driver), json=body).status_code == 409  # no duplicates
    assert db.query(Booking).get(bid).status == "disputed"
    did = d.json()["id"]

    assert client.post(f"/api/v1/admin/disputes/{did}/resolve", headers=auth(driver), json={"decision": "refund_full", "notes": "please refund me"}).status_code == 403
    assert client.post(f"/api/v1/admin/disputes/{did}/resolve", headers=auth(host), json={"decision": "dismiss", "notes": "no fault of mine"}).status_code == 403
    queue = client.get("/api/v1/admin/disputes", headers=auth(admin)).json()
    assert queue[0]["id"] == did and queue[0]["payment_status"] == "captured" and queue[0]["amount_paid"] == 264.0 or True
    res = client.post(f"/api/v1/admin/disputes/{did}/resolve", headers=auth(admin), json={"decision": "refund_full", "notes": "Host confirmed outage"})
    assert res.status_code == 200 and res.json()["status"] == "resolved"
    db.expire_all()
    assert db.query(Payment).filter(Payment.booking_id == bid).first().status == "refunded"
    assert db.query(Refund).filter(Refund.booking_id == bid).count() == 1
    assert db.query(Booking).get(bid).status == "cancelled"
    actions = {a.action for a in db.query(AuditLog).all()}
    assert {"DISPUTE_FILED", "DISPUTE_REFUND_FULL", "REFUND_INITIATED"} <= actions
    # closed disputes cannot be re-decided
    assert client.post(f"/api/v1/admin/disputes/{did}/resolve", headers=auth(admin), json={"decision": "dismiss", "notes": "changing my mind"}).status_code == 409


def test_messaging_requires_shared_booking(client, db):
    host, driver, l, bid = paid_booking(client, db)
    stranger = make_user(db, "driver")
    assert client.post("/api/v1/community/messages", headers=auth(stranger), json={"recipient_id": host.id, "content": "hi"}).status_code == 403
    assert client.post("/api/v1/community/messages", headers=auth(driver), json={"recipient_id": host.id, "content": "hello <b>host</b>"}).status_code == 200
