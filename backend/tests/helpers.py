import uuid
from datetime import date, datetime, time, timedelta, timezone

from app.core.security import create_access_token, hash_password
from app.models.enums import ListingStatus, UserRoleType
from app.models.marketplace import AvailabilitySchedule, HomeChargerListing
from app.models.user import User, UserRole
from app.services.geo import IST


def make_user(db, role="driver", name="Test User", email=None, password="Passw0rd!test"):
    u = User(email=email or f"{role}_{uuid.uuid4().hex[:8]}@example.com", hashed_password=hash_password(password),
             full_name=name, is_active=True)
    db.add(u)
    db.flush()
    db.add(UserRole(user_id=u.id, role_name=getattr(UserRoleType, role.upper()).value))
    db.commit()
    return u


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def make_listing(db, host, all_day=True, **kw):
    data = dict(host_id=host.id, title="Test Wallbox", description="A tidy home charger.", address_street="12 Secret Lane",
                locality="Koramangala", city="Bengaluru", state="Karnataka", pin_code="560034", latitude=12.9344,
                longitude=77.6285, connector_type="Type 2", current_type="AC", power_kw=7.4, price_per_kwh=10.0,
                session_fee=20.0, parking_fee_per_hour=10.0, minimum_booking_hours=1.0, status=ListingStatus.APPROVED.value,
                safety_confirmed=True, parking_access_instructions="Gate code 4455")
    data.update(kw)
    l = HomeChargerListing(**data)
    db.add(l)
    db.flush()
    for d in range(7):
        db.add(AvailabilitySchedule(listing_id=l.id, day_of_week=d, start_time=time(0, 0) if all_day else time(8, 0),
                                    end_time=time(23, 59, 59) if all_day else time(22, 0), is_active=True))
    db.commit()
    return l


def future_slot(days=2, hour_ist=10, hours=2):
    d = (datetime.now(IST) + timedelta(days=days)).date()
    start = datetime.combine(d, time(hour_ist, 0), tzinfo=IST).astimezone(timezone.utc)
    return start, start + timedelta(hours=hours)


def book(client, driver, listing, start, end, kwh=15.0):
    return client.post("/api/v1/marketplace/bookings", headers=auth(driver), json={
        "listing_id": listing.id, "start_time": start.isoformat(), "end_time": end.isoformat(), "estimated_kwh": kwh})


def pay(client, driver, booking_id):
    """Full mock-payment round trip through the real /initiate -> /verify code path."""
    init = client.post("/api/v1/payments/initiate", headers=auth(driver),
                       json={"booking_id": booking_id, "idempotency_key": uuid.uuid4().hex})
    assert init.status_code == 200, init.text
    d = init.json()
    sim = client.post("/api/v1/payments/sandbox/simulate", headers=auth(driver), json={"payment_reference": d["payment_reference"]})
    assert sim.status_code == 200, sim.text
    ver = client.post("/api/v1/payments/verify", headers=auth(driver), json={"payment_reference": d["payment_reference"], **sim.json()})
    return d, sim.json(), ver
