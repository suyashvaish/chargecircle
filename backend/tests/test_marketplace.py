from datetime import datetime, timedelta, timezone
from app.models.marketplace import Booking
from app.services.geo import approximate_coords, haversine_km
from tests.helpers import auth, book, future_slot, make_listing, make_user, pay


def test_listing_privacy_overlap_and_availability(client, db):
    host, driver, stranger = make_user(db, "host"), make_user(db, "driver"), make_user(db, "driver")
    listing = make_listing(db, host)

    # Public view: no street, no exact coordinates, approximate pin 300-500 m away
    pub = client.get(f"/api/v1/marketplace/listings/{listing.id}")
    assert pub.status_code == 200
    d = pub.json()
    assert d["address_street"] is None and d["exact_latitude"] is None and d["parking_access_instructions"] is None
    assert d["location_is_approximate"] is True
    off_m = haversine_km(12.9344, 77.6285, d["latitude"], d["longitude"]) * 1000
    assert 250 <= off_m <= 550, off_m
    assert "12 Secret Lane" not in pub.text and "4455" not in pub.text
    browse = client.get("/api/v1/marketplace/listings")
    assert "12 Secret Lane" not in browse.text and '"latitude":12.9344' not in browse.text.replace(" ", "")

    start, end = future_slot()
    r = book(client, driver, listing, start, end)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["status"] == "awaiting_payment" and b["full_address"] is None and b["exact_latitude"] is None
    assert b["payment_hold_expires_at"] is not None

    # Overlap -> 409, adjacent slot allowed
    assert book(client, stranger, listing, start + timedelta(minutes=30), end + timedelta(minutes=30)).status_code == 409
    assert book(client, stranger, listing, end, end + timedelta(hours=1)).status_code == 201

    # Past start, bad window, own listing
    assert book(client, driver, listing, datetime.now(timezone.utc) - timedelta(days=1), datetime.now(timezone.utc) - timedelta(hours=20)).status_code == 400
    assert book(client, host, listing, *future_slot(days=4)).status_code == 400

    # Another user cannot read the booking
    assert client.get(f"/api/v1/marketplace/bookings/{b['id']}", headers=auth(stranger)).status_code == 404


def test_outside_availability_and_exceptions_rejected(client, db):
    host, driver = make_user(db, "host"), make_user(db, "driver")
    listing = make_listing(db, host, all_day=False)  # 08:00-22:00 IST
    start, end = future_slot(hour_ist=23, hours=1)
    r = book(client, driver, listing, start, end)
    assert r.status_code == 400 and "availability" in r.json()["detail"]
    ok_start, ok_end = future_slot(hour_ist=10)
    assert book(client, driver, listing, ok_start, ok_end).status_code == 201


def test_address_revealed_only_after_confirmation_and_only_to_parties(client, db):
    host, driver, other = make_user(db, "host"), make_user(db, "driver"), make_user(db, "driver")
    listing = make_listing(db, host)
    start, end = future_slot()
    bid = book(client, driver, listing, start, end).json()["id"]

    # Before payment: no exact data for anyone but the host
    assert client.get(f"/api/v1/marketplace/listings/{listing.id}", headers=auth(driver)).json()["address_street"] is None
    pay(client, driver, bid)

    detail = client.get(f"/api/v1/marketplace/listings/{listing.id}", headers=auth(driver)).json()
    assert detail["address_street"] == "12 Secret Lane" and detail["location_is_approximate"] is False
    assert detail["exact_latitude"] == 12.9344
    # A different user, anonymous callers and guessed ids learn nothing
    assert client.get(f"/api/v1/marketplace/listings/{listing.id}", headers=auth(other)).json()["address_street"] is None
    assert client.get(f"/api/v1/marketplace/listings/{listing.id}").json()["exact_latitude"] is None
    assert client.get(f"/api/v1/marketplace/bookings/{bid}", headers=auth(other)).status_code == 404
    mine = client.get(f"/api/v1/marketplace/bookings/{bid}", headers=auth(driver)).json()
    assert mine["full_address"].startswith("12 Secret Lane") and mine["exact_latitude"] == 12.9344
    # Navigation endpoint obeys the same rule
    nav_other = client.get("/api/v1/navigation/route", params={"target_type": "listing", "target_id": listing.id}, headers=auth(other)).json()
    nav_driver = client.get("/api/v1/navigation/route", params={"target_type": "listing", "target_id": listing.id}, headers=auth(driver)).json()
    assert nav_other["destination"]["is_approximate"] is True and nav_other["destination"]["latitude"] != 12.9344
    assert nav_driver["destination"]["is_approximate"] is False and nav_driver["destination"]["latitude"] == 12.9344


def test_unpaid_hold_expires_and_frees_slot(client, db):
    host, d1, d2 = make_user(db, "host"), make_user(db, "driver"), make_user(db, "driver")
    listing = make_listing(db, host)
    start, end = future_slot()
    b1 = book(client, d1, listing, start, end).json()
    row = db.query(Booking).get(b1["id"])
    row.payment_hold_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert book(client, d2, listing, start, end).status_code == 201  # expired hold no longer blocks
    init = client.post("/api/v1/payments/initiate", headers=auth(d1), json={"booking_id": b1["id"], "idempotency_key": "k" * 12})
    assert init.status_code == 400 and "expired" in init.json()["detail"]
