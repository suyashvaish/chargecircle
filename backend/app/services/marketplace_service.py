import json
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.community import AuditLog, Notification
from app.models.enums import BookingStatus, ListingStatus, UserRoleType
from app.models.marketplace import (
    AvailabilityException, AvailabilitySchedule, Booking, ChargingSession, HomeChargerListing,
    HostVerificationRecord, ListingPhoto,
)
from app.models.user import User, Vehicle
from app.schemas.marketplace import (
    BookingCreate, ChargingSessionComplete, ChargingSessionOut, ChargingSessionStart, HomeListingCreate,
    HomeListingDetailOut, HomeListingOut, HostSummaryOut,
)
from app.services import compatibility as compat
from app.services.audit import audit
from app.services.charger_service import calculate_haversine
from app.services.geo import IST, approximate_coords, as_utc
from app.services.notification_service import booking_ctx, send_event_email, send_in_app_notification
from app.services.pricing import compute_home_booking_price

# Booking states in which the precise address / coordinates may be released to the driver.
REVEAL_STATUSES = (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value, BookingStatus.COMPLETED.value)
COMPLETED_REVEAL_WINDOW = timedelta(hours=48)
SLOT_BLOCKING = (BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value)


# ------------------------------------------------------------------ location privacy

def booking_reveals_address(b: Booking, now: Optional[datetime] = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if b.status in (BookingStatus.CONFIRMED.value, BookingStatus.IN_PROGRESS.value):
        return True
    if b.status == BookingStatus.COMPLETED.value:
        return now <= as_utc(b.end_time) + COMPLETED_REVEAL_WINDOW
    return False


def can_view_exact_location(db: Session, viewer: Optional[User], listing: HomeChargerListing) -> bool:
    """Server-side authorization for exact address/coordinates: host, admin, or a driver with an eligible booking."""
    if viewer is None:
        return False
    if viewer.id == listing.host_id or viewer.has_role(UserRoleType.ADMIN.value):
        return True
    bookings = db.query(Booking).filter(Booking.listing_id == listing.id, Booking.driver_id == viewer.id,
                                        Booking.status.in_(REVEAL_STATUSES)).all()
    return any(booking_reveals_address(b) for b in bookings)


def _avg(item: HomeChargerListing) -> Optional[float]:
    rs = [r.rating_overall for r in item.reviews if getattr(r, "moderation_status", "published") == "published"]
    return round(sum(rs) / len(rs), 1) if rs else None


def build_listing_out(item: HomeChargerListing, *, exact: bool, dist_km: Optional[float] = None,
                      with_street: bool = False, vehicle: Optional[Vehicle] = None) -> HomeListingOut:
    lat, lon = (item.latitude, item.longitude) if exact else approximate_coords(item.id, item.latitude, item.longitude)
    display = f"{item.locality}, {item.city}, {item.pin_code}"
    if exact and with_street:
        display = f"{item.address_street}, {display}"
    cover = next((p.photo_url for p in item.photos if p.is_cover), None) or (item.photos[0].photo_url if item.photos else None)
    reviews = [r for r in item.reviews if getattr(r, "moderation_status", "published") == "published"]
    out = HomeListingOut(
        id=item.id, host_id=item.host_id, title=item.title, description=item.description, locality=item.locality,
        city=item.city, state=item.state, pin_code=item.pin_code, latitude=lat, longitude=lon,
        location_is_approximate=not exact, distance_km=dist_km, property_type=item.property_type,
        equipment_type=item.equipment_type, connector_type=item.connector_type, current_type=item.current_type,
        power_kw=item.power_kw, is_cable_attached=item.is_cable_attached, has_covered_parking=item.has_covered_parking,
        price_per_kwh=item.price_per_kwh, session_fee=item.session_fee, parking_fee_per_hour=item.parking_fee_per_hour,
        minimum_booking_hours=item.minimum_booking_hours, status=item.status, instant_booking=item.instant_booking,
        safety_confirmed=item.safety_confirmed, earthing_verified=item.earthing_verified, display_address=display,
        cover_photo_url=cover, average_rating=_avg(item), total_reviews=len(reviews), created_at=item.created_at)
    if vehicle is not None:
        class _C:  # adapter for the compatibility module
            connector_type, current_type, power_kw, cable_attached = (
                item.connector_type, item.current_type, item.power_kw, item.is_cable_attached)
        out.compatibility = compat.evaluate_charger(vehicle, [_C])
    return out


# ------------------------------------------------------------------ listings

def create_home_listing(db: Session, host: User, data: HomeListingCreate) -> HomeChargerListing:
    """Creates a new home charging facility listing in pending verification state."""
    if not host.has_role(UserRoleType.HOST.value):
        from app.models.user import UserRole
        db.add(UserRole(user_id=host.id, role_name=UserRoleType.HOST.value))

    auto = settings.AUTO_APPROVE_LISTINGS and not settings.is_production
    listing = HomeChargerListing(
        host_id=host.id, title=data.title.strip(), description=data.description.strip(),
        address_street=data.address_street.strip(), locality=data.locality.strip(), city=data.city.strip(),
        state=data.state.strip(), pin_code=data.pin_code.strip(), latitude=data.latitude, longitude=data.longitude,
        is_address_hidden_until_booked=True,  # enforced regardless of the submitted value
        property_type=data.property_type, equipment_type=data.equipment_type, connector_type=data.connector_type,
        current_type=data.current_type, power_kw=data.power_kw, is_cable_attached=data.is_cable_attached,
        has_dedicated_meter=data.has_dedicated_meter, has_cctv_surveillance=data.has_cctv_surveillance,
        has_covered_parking=data.has_covered_parking, safety_confirmed=data.safety_confirmed,
        earthing_verified=data.earthing_verified, rcbo_installed=data.rcbo_installed, price_per_kwh=data.price_per_kwh,
        session_fee=data.session_fee, parking_fee_per_hour=data.parking_fee_per_hour,
        minimum_booking_hours=data.minimum_booking_hours,
        status=ListingStatus.APPROVED.value if auto else ListingStatus.PENDING_VERIFICATION.value,
        instant_booking=data.instant_booking, parking_access_instructions=data.parking_access_instructions,
        cancellation_policy=data.cancellation_policy)
    db.add(listing)
    db.flush()
    db.add(ListingPhoto(listing_id=listing.id,
                        photo_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=800&q=80",
                        caption="Home Wallbox Charger", is_cover=True))
    for day in range(7):
        db.add(AvailabilitySchedule(listing_id=listing.id, day_of_week=day, start_time=time(8, 0), end_time=time(22, 0), is_active=True))
    db.add(HostVerificationRecord(host_id=host.id, listing_id=listing.id, document_type="safety_declaration",
                                  verification_status="approved" if auto else "pending",
                                  reviewer_notes="Self-attested electrical earthing and safety checklist."))
    audit(db, host.id, "CREATE_HOME_LISTING", "HomeChargerListing", listing.id)
    db.commit()
    db.refresh(listing)
    return listing


def get_marketplace_listings(db: Session, latitude: Optional[float] = None, longitude: Optional[float] = None,
                             radius_km: float = 30.0, city: Optional[str] = None, connector_type: Optional[str] = None,
                             max_price: Optional[float] = None, viewer: Optional[User] = None,
                             vehicle: Optional[Vehicle] = None, compatible_only: bool = False) -> List[HomeListingOut]:
    """Approved listings with APPROXIMATE public coordinates. Distances use the approximate pin (rounded to 0.1 km)."""
    query = db.query(HomeChargerListing).filter(HomeChargerListing.status == ListingStatus.APPROVED.value)
    if city:
        query = query.filter(HomeChargerListing.city.ilike(f"%{city.strip()}%"))
    if connector_type:
        query = query.filter(HomeChargerListing.connector_type.ilike(f"%{connector_type.strip()}%"))
    if max_price:
        query = query.filter(HomeChargerListing.price_per_kwh <= max_price)

    results: List[HomeListingOut] = []
    for item in query.all():
        exact = can_view_exact_location(db, viewer, item) if viewer else False
        alat, alon = (item.latitude, item.longitude) if exact else approximate_coords(item.id, item.latitude, item.longitude)
        dist_km = None
        if latitude is not None and longitude is not None:
            dist_km = round(calculate_haversine(latitude, longitude, alat, alon), 1)
            if dist_km > radius_km:
                continue
        out = build_listing_out(item, exact=exact, dist_km=dist_km, vehicle=vehicle)
        if compatible_only and vehicle is not None and out.compatibility and out.compatibility.status == "incompatible":
            continue
        results.append(out)
    if latitude is not None and longitude is not None:
        results.sort(key=lambda x: x.distance_km if x.distance_km is not None else 99999)
    return results


def get_home_listing_detail(db: Session, listing_id: int, viewer: Optional[User] = None,
                            vehicle: Optional[Vehicle] = None) -> Optional[HomeListingDetailOut]:
    item = db.query(HomeChargerListing).filter(HomeChargerListing.id == listing_id).first()
    if not item:
        return None
    exact = can_view_exact_location(db, viewer, item)
    # Non-approved listings are visible only to their host or an admin.
    if item.status != ListingStatus.APPROVED.value and not (
            viewer and (viewer.id == item.host_id or viewer.has_role(UserRoleType.ADMIN.value))):
        return None
    base = build_listing_out(item, exact=exact, with_street=True, vehicle=vehicle)
    host_summary = None
    if item.host:
        host_summary = HostSummaryOut(id=item.host.id, full_name=item.host.full_name.split(" ")[0],
                                      is_verified=item.host.is_verified, avatar_url=item.host.avatar_url,
                                      rating=base.average_rating or 0.0, review_count=base.total_reviews)
    return HomeListingDetailOut(
        **base.model_dump(), address_street=item.address_street if exact else None,
        parking_access_instructions=item.parking_access_instructions if exact else None,
        exact_latitude=item.latitude if exact else None, exact_longitude=item.longitude if exact else None,
        cancellation_policy=item.cancellation_policy, photos=item.photos, schedules=item.schedules, host=host_summary)


# ------------------------------------------------------------------ booking

def expire_stale_holds(db: Session) -> int:
    """Releases slots held by unpaid bookings whose payment window has passed."""
    now = datetime.now(timezone.utc)
    stale = db.query(Booking).filter(Booking.status == BookingStatus.AWAITING_PAYMENT.value,
                                     Booking.payment_hold_expires_at.isnot(None),
                                     Booking.payment_hold_expires_at < now).all()
    for b in stale:
        b.status = BookingStatus.CANCELLED.value
        b.cancellation_reason = "payment_hold_expired"
        b.cancelled_at = now
    if stale:
        db.commit()
    return len(stale)


def _lock_listing(db: Session, listing_id: int) -> None:
    """Serialises concurrent reservations of one listing (row lock on PostgreSQL, write lock on SQLite)."""
    db.execute(text("UPDATE home_charger_listings SET id = id WHERE id = :i"), {"i": listing_id})


def slot_conflict(db: Session, listing_id: int, start: datetime, end: datetime,
                  exclude_booking_id: Optional[int] = None) -> Optional[Booking]:
    now = datetime.now(timezone.utc)
    q = db.query(Booking).filter(
        Booking.listing_id == listing_id,
        or_(Booking.status.in_(SLOT_BLOCKING),
            and_(Booking.status == BookingStatus.AWAITING_PAYMENT.value,
                 or_(Booking.payment_hold_expires_at.is_(None), Booking.payment_hold_expires_at > now))),
        Booking.start_time < end, Booking.end_time > start)
    if exclude_booking_id:
        q = q.filter(Booking.id != exclude_booking_id)
    return q.first()


def check_within_availability(listing: HomeChargerListing, start: datetime, end: datetime) -> Optional[str]:
    """Returns a human reason if the window is outside the host's published availability (times are IST)."""
    s_loc, e_loc = start.astimezone(IST), end.astimezone(IST)
    if not [s for s in listing.schedules if s.is_active]:
        return "The host has not published any availability for this charger."
    blocked = {as_utc(x.exception_date).astimezone(IST).date() for x in listing.exceptions if x.is_unavailable}
    cur = s_loc
    while cur < e_loc:
        midnight = datetime.combine(cur.date() + timedelta(days=1), time(0, 0), tzinfo=IST)
        seg_end = min(e_loc, midnight)
        if cur.date() in blocked:
            return f"The host is unavailable on {cur.date().strftime('%d %b %Y')}."
        end_t = seg_end.time() if seg_end != midnight else time(23, 59, 59)
        ok = any(sc.is_active and sc.day_of_week == cur.date().weekday() and sc.start_time <= cur.time() and end_t <= sc.end_time
                 for sc in listing.schedules)
        if not ok:
            return "The requested time is outside the host's published availability."
        cur = seg_end
    return None


def create_booking_reservation(db: Session, driver: User, data: BookingCreate) -> Booking:
    """
    Reserves a slot. The listing row is locked first so two simultaneous requests cannot both pass the overlap check.
    Prices are computed on the server from the listing; client prices are never accepted.
    """
    start, end = as_utc(data.start_time), as_utc(data.end_time)
    now = datetime.now(timezone.utc)
    if start >= end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End time must be after start time")
    if start < now - timedelta(minutes=5):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The start time is in the past")
    if end - start > timedelta(hours=24):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A single booking cannot exceed 24 hours")

    listing = db.query(HomeChargerListing).filter(HomeChargerListing.id == data.listing_id).first()
    if not listing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charger listing not found")
    if listing.status != ListingStatus.APPROVED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This charging facility is not currently open for bookings")
    if listing.host_id == driver.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hosts cannot book their own charger")
    if data.vehicle_id is not None and not db.query(Vehicle).filter(Vehicle.id == data.vehicle_id, Vehicle.user_id == driver.id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    reason = check_within_availability(listing, start, end)
    if reason:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=reason)

    expire_stale_holds(db)
    _lock_listing(db, listing.id)
    if slot_conflict(db, listing.id, start, end):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="This charging time slot is already reserved. Please select another time.")

    price = compute_home_booking_price(listing, data.estimated_kwh, (end - start).total_seconds() / 3600.0)
    ref_id = f"CC-BK-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    booking = Booking(
        booking_reference=ref_id, driver_id=driver.id, listing_id=listing.id, vehicle_id=data.vehicle_id,
        start_time=start, end_time=end, total_hours=price["total_hours"], estimated_kwh=data.estimated_kwh,
        rate_per_kwh=listing.price_per_kwh, session_fee=price["session_cost"], parking_fee=price["parking_cost"],
        subtotal_amount=price["subtotal"], platform_fee=price["platform_fee"], total_amount=price["total"],
        host_earnings_amount=price["host_earnings"], status=BookingStatus.AWAITING_PAYMENT.value,
        payment_hold_expires_at=now + timedelta(minutes=settings.BOOKING_HOLD_MINUTES),
        arrival_instructions_revealed=False)
    db.add(booking)
    try:
        db.flush()
    except IntegrityError:  # PostgreSQL exclusion constraint: defence in depth against a double booking
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This charging time slot is already reserved. Please select another time.")
    send_in_app_notification(db, listing.host_id, "New Booking Reserved",
                             f"{driver.full_name.split(' ')[0]} reserved {listing.title} for {booking.start_time.strftime('%d %b, %H:%M')} UTC. It is confirmed once payment is verified.",
                             "booking_reserved", "/host/dashboard", commit=False)
    audit(db, driver.id, "BOOKING_CREATED", "Booking", booking.id, {"ref": ref_id, "amount": price["total"]})
    db.commit()
    db.refresh(booking)
    send_event_email(db, listing.host, "booking_requested_host", booking_ctx(booking), dedupe_key=f"booking_requested:{booking.id}")
    return booking


def confirm_booking_payment(db: Session, booking: Booking) -> Booking:
    """Transitions the booking to CONFIRMED. Call only after payment capture has been verified server-side."""
    booking.status = BookingStatus.CONFIRMED.value
    booking.arrival_instructions_revealed = True
    booking.payment_hold_expires_at = None
    booking.cancellation_reason = None
    booking.cancelled_at = None
    if not db.query(ChargingSession).filter(ChargingSession.booking_id == booking.id).first():
        db.add(ChargingSession(booking_id=booking.id, status="scheduled", verification_source="none"))
    send_in_app_notification(db, booking.driver_id, "Booking Confirmed!",
                             f"Your booking {booking.booking_reference} is confirmed. The exact address is now unlocked.",
                             "booking_confirmed", f"/bookings/{booking.id}", commit=False)
    send_in_app_notification(db, booking.listing.host_id, "Payment Received for Booking",
                             f"Booking {booking.booking_reference} has been paid and confirmed.", "payment_received",
                             "/host/dashboard", commit=False)
    db.commit()
    db.refresh(booking)
    ctx = booking_ctx(booking)
    send_event_email(db, booking.driver, "booking_confirmed_driver", ctx, dedupe_key=f"booking_confirmed:{booking.id}:driver")
    send_event_email(db, booking.listing.host, "booking_confirmed_host", ctx, dedupe_key=f"booking_confirmed:{booking.id}:host")
    return booking


# ------------------------------------------------------------------ booking output

def build_booking_out(db: Session, b: Booking, viewer: User):
    from app.schemas.marketplace import BookingOut
    reveal = booking_reveals_address(b) and (viewer.id == b.driver_id or viewer.id == b.listing.host_id
                                             or viewer.has_role(UserRoleType.ADMIN.value))
    is_host_or_admin = viewer.id == b.listing.host_id or viewer.has_role(UserRoleType.ADMIN.value)
    full = f"{b.listing.address_street}, {b.listing.locality}, {b.listing.city}" if (reveal or is_host_or_admin) else None
    alat, alon = approximate_coords(b.listing.id, b.listing.latitude, b.listing.longitude)
    return BookingOut(
        id=b.id, booking_reference=b.booking_reference, driver_id=b.driver_id, listing_id=b.listing_id,
        vehicle_id=b.vehicle_id, start_time=b.start_time, end_time=b.end_time, total_hours=b.total_hours,
        estimated_kwh=b.estimated_kwh, rate_per_kwh=b.rate_per_kwh, session_fee=b.session_fee, parking_fee=b.parking_fee,
        subtotal_amount=b.subtotal_amount, platform_fee=b.platform_fee, total_amount=b.total_amount,
        host_earnings_amount=b.host_earnings_amount, status=b.status, cancellation_reason=b.cancellation_reason,
        arrival_instructions_revealed=b.arrival_instructions_revealed and reveal, full_address=full,
        parking_access_instructions=b.listing.parking_access_instructions if (reveal or is_host_or_admin) else None,
        exact_latitude=b.listing.latitude if (reveal or is_host_or_admin) else None,
        exact_longitude=b.listing.longitude if (reveal or is_host_or_admin) else None,
        approx_latitude=alat, approx_longitude=alon, listing_title=b.listing.title,
        payment_hold_expires_at=b.payment_hold_expires_at, cancelled_at=b.cancelled_at,
        payment_status=b.payment.status if b.payment else None, created_at=b.created_at)


# ------------------------------------------------------------------ charging sessions

def session_out(s: ChargingSession) -> ChargingSessionOut:
    snap = None
    if s.pricing_snapshot_json:
        try:
            snap = json.loads(s.pricing_snapshot_json)
        except ValueError:
            snap = None
    return ChargingSessionOut(
        id=s.id, booking_id=s.booking_id, started_at=s.started_at, ended_at=s.ended_at,
        energy_delivered_kwh=s.energy_delivered_kwh if s.energy_entered_at else None,  # None until someone records it
        peak_power_kw=s.peak_power_kw,
        meter_reading_start=s.meter_reading_start, meter_reading_end=s.meter_reading_end, status=s.status,
        verification_source=s.verification_source, energy_is_measured=s.energy_is_measured,
        final_amount=s.final_amount, pricing_snapshot=snap, notes=s.notes, created_at=s.created_at)


def _party_or_403(booking: Booking, user: User) -> str:
    if user.id == booking.listing.host_id:
        return "host"
    if user.id == booking.driver_id:
        return "driver"
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized booking access")


def start_session(db: Session, booking_id: int, user: User, data: ChargingSessionStart) -> ChargingSession:
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    _party_or_403(booking, user)
    if booking.status != BookingStatus.CONFIRMED.value or not booking.payment or booking.payment.status != "captured":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only a paid, confirmed booking can start a session")
    now = datetime.now(timezone.utc)
    if now < as_utc(booking.start_time) - timedelta(minutes=30):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The session cannot start more than 30 minutes before the booked time")
    if now > as_utc(booking.end_time):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The booked time has already ended")
    session = db.query(ChargingSession).filter(ChargingSession.booking_id == booking.id).first()
    if not session:
        session = ChargingSession(booking_id=booking.id)
        db.add(session)
    session.started_at = now
    session.status = "started"
    session.meter_reading_start = data.meter_reading_start
    booking.status = BookingStatus.IN_PROGRESS.value
    audit(db, user.id, "SESSION_STARTED", "Booking", booking.id)
    db.commit()
    db.refresh(session)
    return session


def complete_session(db: Session, booking_id: int, user: User, data: ChargingSessionComplete) -> ChargingSession:
    """
    Completes a session with a MANUALLY entered energy figure (clearly recorded as not measured by hardware),
    then records the recalculated charge. No money moves automatically from this recalculation.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    role = _party_or_403(booking, user)
    session = db.query(ChargingSession).filter(ChargingSession.booking_id == booking.id).first()
    if booking.status != BookingStatus.IN_PROGRESS.value or not session or session.status != "started":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Charging session is not in progress")

    max_kwh = booking.listing.power_kw * max(booking.total_hours, 0.5) * 1.15
    if data.energy_delivered_kwh > max_kwh:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"{data.energy_delivered_kwh:g} kWh is more than this charger ({booking.listing.power_kw:g} kW) can deliver in the booked time")
    if data.meter_reading_end is not None and session.meter_reading_start is not None:
        if data.meter_reading_end < session.meter_reading_start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="End meter reading is below the start reading")
        if abs((data.meter_reading_end - session.meter_reading_start) - data.energy_delivered_kwh) > 0.2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Energy does not match the difference between the meter readings")

    now = datetime.now(timezone.utc)
    kwh = round(data.energy_delivered_kwh, 3)
    charging = round(kwh * booking.rate_per_kwh + 1e-9, 2)
    subtotal = round(charging + booking.session_fee + booking.parking_fee + 1e-9, 2)
    ratio = booking.platform_fee / booking.subtotal_amount if booking.subtotal_amount else 0.0
    fee = round(subtotal * ratio + 1e-9, 2)
    final_total = round(subtotal + fee, 2)
    snapshot = {
        "energy_source": f"manual_{role}", "energy_is_measured": False, "energy_kwh_final": kwh,
        "energy_kwh_estimated": booking.estimated_kwh, "rate_per_kwh": booking.rate_per_kwh,
        "session_fee": booking.session_fee, "parking_fee": booking.parking_fee, "energy_charge": charging,
        "subtotal": subtotal, "platform_fee": fee, "final_total": final_total, "amount_paid": booking.total_amount,
        "difference_vs_paid": round(final_total - booking.total_amount, 2),
        "settlement": "recorded_only: no automatic adjustment is made to the amount already paid",
        "currency": "INR"}
    session.ended_at = now
    session.energy_delivered_kwh = kwh
    session.meter_reading_end = data.meter_reading_end
    session.status = "completed"
    session.verification_source = f"manual_{role}"
    session.energy_is_measured = False
    session.energy_entered_by_id, session.energy_entered_at = user.id, now
    session.final_amount, session.pricing_snapshot_json = final_total, json.dumps(snapshot)
    session.notes = data.notes
    booking.status = BookingStatus.COMPLETED.value
    audit(db, user.id, "SESSION_COMPLETED", "Booking", booking.id, {"kwh": kwh, "source": f"manual_{role}", "final_total": final_total})
    db.commit()
    db.refresh(session)
    return session
