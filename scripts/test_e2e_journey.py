"""
End-to-end journeys against the real FastAPI app (in-process, temporary SQLite database, mock payments,
mocked Open Charge Map / routing / email transports). Nothing external is contacted.

    cd backend && python ../scripts/test_e2e_journey.py

Prints PASS/FAIL per step and exits non-zero on any failure.
"""
import json, os, sys, tempfile, uuid
from datetime import datetime, time, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
_tmp = tempfile.mkdtemp()
os.environ.update(DATABASE_URL=f"sqlite:///{_tmp}/e2e.db", ENVIRONMENT="test", LOCAL_UPLOAD_DIR=f"{_tmp}/uploads")

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import UserRoleType  # noqa: E402
from app.models.marketplace import Booking  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402
from app.services import email_service, provider_sync  # noqa: E402
from app.services.geo import IST  # noqa: E402
from app.services.razorpay_client import compute_signature  # noqa: E402

settings.EMAIL_SEND_SYNC, settings.EMAIL_BACKEND, settings.PAYMENT_MODE = True, "disabled", "mock"
settings.AUTO_APPROVE_LISTINGS = False  # journeys must not depend on a developer .env
settings.RAZORPAY_WEBHOOK_SECRET, settings.USE_LIVE_CHARGER_FEED, settings.OCM_API_KEY = "whsec_e2e", True, "e2e-key"
Base.metadata.create_all(bind=engine)
import logging  # noqa: E402
logging.disable(logging.CRITICAL)  # keep the journey output readable

outbox = []
email_service._deliver = lambda to, subject, body: outbox.append((to, subject, body))
OCM = [{"ID": 9001, "AddressInfo": {"Title": "E2E Fast Hub", "Town": "Bengaluru", "StateOrProvince": "Karnataka", "Postcode": "560001", "Latitude": 12.975, "Longitude": 77.60},
        "OperatorInfo": {"Title": "E2E Power"}, "UsageType": {"Title": "Public"}, "UsageCost": "₹20/kWh",
        "Connections": [{"ConnectionType": {"Title": "CCS (Type 2)"}, "PowerKW": 60, "CurrentType": {"Title": "DC"}}]}]
provider_sync._transport = httpx.MockTransport(lambda r: httpx.Response(200, json=OCM))

c = TestClient(app)
results = []


def step(name, ok, detail=""):
    ok = bool(ok)
    results.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' - ' + str(detail)) if detail and not ok else ''}")


def mk(role, name):
    with SessionLocal() as db:
        u = User(email=f"{role}_{uuid.uuid4().hex[:6]}@example.com", hashed_password=hash_password("E2ePassw0rd!x"), full_name=name, is_active=True, is_verified=True)
        db.add(u); db.flush(); db.add(UserRole(user_id=u.id, role_name=getattr(UserRoleType, role.upper()).value)); db.commit()
        return u.id, {"Authorization": f"Bearer {create_access_token(u.id)}"}


host_id, H = mk("host", "Hema Host")
drv_id, D = mk("driver", "Dev Driver")
adm_id, A = mk("admin", "Ada Admin")

# 1. Registration + email verification + login (real endpoints)
r = c.post("/api/v1/auth/register", json={"email": "journey@example.com", "password": "Journey123!pass", "full_name": "Jo Urney", "phone_number": "+91 98000 00000", "role": "driver"})
step("register driver", r.status_code == 201, r.text)
tok = next(b for (_, s, b) in outbox if "Verify" in s).split("token=")[1].split()[0]
step("verify email via emailed link", c.post("/api/v1/auth/verify-email", json={"token": tok}).status_code == 200)
step("login", c.post("/api/v1/auth/login", json={"email": "journey@example.com", "password": "Journey123!pass"}).status_code == 200)

# 2. Public discovery with live provider (mocked), cache, provenance
s1 = c.get("/api/v1/discovery/search", params={"latitude": 12.97, "longitude": 77.59, "radius_km": 10}).json()
st = next((x for x in s1["stations"] if x["external_id"] == "9001"), None)
step("provider data stored and labelled", bool(st) and st["data_origin"] == "provider" and s1["provider"]["status"] == "live")
s2 = c.get("/api/v1/discovery/search", params={"latitude": 12.97, "longitude": 77.59, "radius_km": 10}).json()
step("repeat search served from cache", s2["provider"]["status"] == "cached")
step("provider price kept, other fees unknown", st["price_summary"] == "From ₹20.00/kWh" and st["parking_fee"] is None)

# 3. Estimator, vehicle compatibility, navigation
v = c.post("/api/v1/users/vehicles", headers=D, json={"make": "Tata", "model": "Nexon EV", "battery_capacity_kwh": 40.5, "max_dc_charging_kw": 50, "connector_types": ["CCS2"]})
step("save vehicle with only known specs", v.status_code == 201 and v.json()["max_ac_charging_kw"] is None)
est = c.post("/api/v1/pricing/estimate", headers=D, json={"target_type": "station", "target_id": st["id"], "vehicle_id": v.json()["id"], "from_soc_percent": 20, "to_soc_percent": 80}).json()
step("estimate shows working and exclusions", est["energy_kwh"] == 24.3 and est["total_known"] == 486.0 and est["is_complete"] is False and est["excluded"])
comp = c.get(f"/api/v1/discovery/stations/{st['id']}", headers=D, params={"vehicle_id": v.json()["id"]}).json()["compatibility"]
step("compatibility from saved specs", comp["status"] == "compatible" and comp["effective_power_kw"] == 50)
nav = c.get("/api/v1/navigation/route", params={"target_type": "station", "target_id": st["id"], "origin_lat": 12.9, "origin_lon": 77.5}).json()
step("navigation links + no invented distance", "destination=12.975%2C77.6" in nav["links"]["google_maps"] and nav["route"]["available"] is False)

# 4. Host lists charger -> admin approval -> hidden exact location
lst = c.post("/api/v1/marketplace/listings", headers=H, json={"title": "E2E Home Wallbox", "description": "Covered driveway with 7.4 kW charger.", "address_street": "7 Private Road", "locality": "Indiranagar", "city": "Bengaluru",
             "pin_code": "560038", "latitude": 12.9784, "longitude": 77.6408, "connector_type": "Type 2", "power_kw": 7.4, "price_per_kwh": 12, "safety_confirmed": True, "earthing_verified": True})
lid = lst.json()["id"]
step("new listing awaits admin approval", lst.status_code == 201 and lst.json()["status"] == "pending_verification", lst.text)
step("admin approves listing", c.post("/api/v1/admin/moderation", headers=A, json={"target_type": "listing", "target_id": lid, "action": "approved", "notes": "docs checked"}).status_code == 200)
pub = c.get(f"/api/v1/marketplace/listings/{lid}")
step("public view hides street and exact coordinates", "7 Private Road" not in pub.text and pub.json()["exact_latitude"] is None and pub.json()["latitude"] != 12.9784)

# 5. Book -> pay (verified) -> address unlocked
d0 = (datetime.now(IST) + timedelta(days=3)).date()
start = datetime.combine(d0, time(10, 0), tzinfo=IST).astimezone(timezone.utc)
b = c.post("/api/v1/marketplace/bookings", headers=D, json={"listing_id": lid, "start_time": start.isoformat(), "end_time": (start + timedelta(hours=2)).isoformat(), "estimated_kwh": 12}).json()
step("booking priced by server, awaiting payment", b["status"] == "awaiting_payment" and b["total_amount"] > 0)
step("overlapping booking rejected", c.post("/api/v1/marketplace/bookings", headers=A, json={"listing_id": lid, "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat(), "estimated_kwh": 5}).status_code == 409)
init = c.post("/api/v1/payments/initiate", headers=D, json={"booking_id": b["id"], "idempotency_key": uuid.uuid4().hex}).json()
bad = c.post("/api/v1/payments/verify", headers=D, json={"payment_reference": init["payment_reference"], "razorpay_order_id": init["razorpay_order_id"], "razorpay_payment_id": "pay_x", "razorpay_signature": "sandbox_valid_signature"})
step("forged signature rejected, booking still unpaid", bad.status_code == 400 and c.get(f"/api/v1/marketplace/bookings/{b['id']}", headers=D).json()["status"] == "awaiting_payment")
sim = c.post("/api/v1/payments/sandbox/simulate", headers=D, json={"payment_reference": init["payment_reference"]}).json()
ok = c.post("/api/v1/payments/verify", headers=D, json={"payment_reference": init["payment_reference"], **sim})
step("verified payment confirms booking", ok.status_code == 200 and c.get(f"/api/v1/marketplace/bookings/{b['id']}", headers=D).json()["status"] == "confirmed")
mine = c.get(f"/api/v1/marketplace/bookings/{b['id']}", headers=D).json()
step("exact address now released to booked driver only", mine["full_address"].startswith("7 Private Road") and "7 Private Road" not in c.get(f"/api/v1/marketplace/listings/{lid}").text)
body = json.dumps({"event": "payment.captured", "payload": {"payment": {"entity": {"id": sim["razorpay_payment_id"], "order_id": init["razorpay_order_id"], "amount": int(round(b["total_amount"] * 100))}}}}).encode()
hdr = {"X-Razorpay-Signature": compute_signature("whsec_e2e", body), "X-Razorpay-Event-Id": "evt_e2e_1", "Content-Type": "application/json"}
step("webhook replay is idempotent", c.post("/api/v1/payments/webhook", content=body, headers=hdr).json()["status"] == "processed" and c.post("/api/v1/payments/webhook", content=body, headers=hdr).json()["status"] == "duplicate")
step("confirmation emails sent once", sum(1 for (_, s, _b) in outbox if s.startswith("Booking confirmed")) == 1)

# 6. Session (time shifted to 'now' directly in the DB: a real booking can only start at its booked time)
with SessionLocal() as db:
    row = db.get(Booking, b["id"]); row.start_time = datetime.now(timezone.utc) - timedelta(minutes=5); row.end_time = row.start_time + timedelta(hours=2); db.commit()
step("start session", c.post(f"/api/v1/marketplace/bookings/{b['id']}/session/start", headers=D, json={"meter_reading_start": 50}).status_code == 200)
step("stranger cannot complete session", c.post(f"/api/v1/marketplace/bookings/{b['id']}/session/complete", headers=A, json={"energy_delivered_kwh": 5}).status_code == 403)
done = c.post(f"/api/v1/marketplace/bookings/{b['id']}/session/complete", headers=H, json={"energy_delivered_kwh": 11.5, "meter_reading_end": 61.5}).json()
step("energy recorded as manual, not measured", done["energy_is_measured"] is False and done["verification_source"] == "manual_host" and done["pricing_snapshot"]["energy_kwh_final"] == 11.5)

# 7. Review, dispute, admin refund
rv = c.post("/api/v1/community/reviews", headers=D, json={"booking_id": b["id"], "rating_overall": 4, "rating_accuracy": 4, "rating_host": 5, "rating_parking": 4, "comment": "Smooth session, host was helpful."})
step("review after completed booking", rv.status_code == 201 and c.post("/api/v1/community/reviews", headers=D, json=rv.request.content and json.loads(rv.request.content)).status_code == 400)
dp = c.post("/api/v1/community/disputes", headers=D, json={"booking_id": b["id"], "reason": "The final charge looks higher than the meter showed.", "category": "payment"})
step("dispute filed", dp.status_code == 201)
res = c.post(f"/api/v1/admin/disputes/{dp.json()['id']}/resolve", headers=A, json={"decision": "refund_full", "notes": "Meter evidence reviewed"})
step("admin resolves with audited full refund", res.status_code == 200 and c.get(f"/api/v1/marketplace/bookings/{b['id']}", headers=D).json()["payment_status"] == "refunded")
logs = c.get("/api/v1/admin/audit-logs?limit=50", headers=A).json()
step("audit trail records moderation and refund", {"DISPUTE_REFUND_FULL", "REFUND_INITIATED"} <= {l["action"] for l in logs})

# 8. Trust: reports
rep = c.post("/api/v1/reliability/reports", headers=D, json={"station_id": st["id"], "category": "misleading_price", "description": "App price differs from the board."})
step("pricing report waits for moderation", rep.status_code == 201 and rep.json()["moderation_status"] == "under_review")

# 9. Password reset
c.post("/api/v1/auth/password-reset/request", json={"email": "journey@example.com"})
rt = next(b for (_, s, b) in reversed(outbox) if "Reset" in s).split("token=")[1].split("&")[0]
step("password reset completes", c.post("/api/v1/auth/password-reset/confirm", json={"email": "journey@example.com", "reset_token": rt, "new_password": "BrandNew123!pass"}).status_code == 200
     and c.post("/api/v1/auth/login", json={"email": "journey@example.com", "password": "BrandNew123!pass"}).status_code == 200)

print(f"\n{sum(results)}/{len(results)} steps passed")
sys.exit(0 if all(results) else 1)
