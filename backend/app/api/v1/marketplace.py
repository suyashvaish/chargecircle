from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.marketplace import Booking, HomeChargerListing
from app.models.user import User, Vehicle
from app.schemas.marketplace import (
    BookingCreate, BookingOut, CancelRequest, ChargingSessionComplete, ChargingSessionOut, ChargingSessionStart,
    HomeListingCreate, HomeListingDetailOut, HomeListingOut,
)
from app.schemas.payment import CancelOut
from app.services.auth_service import get_current_user, get_optional_user
from app.services.marketplace_service import (
    build_booking_out, build_listing_out, complete_session, create_booking_reservation, create_home_listing,
    expire_stale_holds, get_home_listing_detail, get_marketplace_listings, session_out, start_session,
)
from app.services.payment_service import cancel_booking

router = APIRouter(prefix="/marketplace", tags=["Home Charging Marketplace"])


def _vehicle(db: Session, user: Optional[User], vehicle_id: Optional[int]) -> Optional[Vehicle]:
    if vehicle_id is None:
        return None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to use a saved vehicle")
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.user_id == user.id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return v


@router.post("/listings", response_model=HomeListingDetailOut, status_code=status.HTTP_201_CREATED)
def create_listing(data: HomeListingCreate, host: User = Depends(get_current_user), db: Session = Depends(get_db)):
    listing = create_home_listing(db, host, data)
    return get_home_listing_detail(db, listing.id, viewer=host)


@router.get("/listings", response_model=List[HomeListingOut])
def browse_listings(
    latitude: Optional[float] = Query(None, ge=-90, le=90), longitude: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(30.0, ge=1.0, le=200.0), city: Optional[str] = Query(None),
    connector_type: Optional[str] = Query(None), max_price: Optional[float] = Query(None, ge=0),
    vehicle_id: Optional[int] = Query(None), compatible_only: Optional[bool] = Query(None),
    db: Session = Depends(get_db), viewer: Optional[User] = Depends(get_optional_user),
):
    """Public browse. Coordinates and distances are approximate; precise locations are never in this response."""
    return get_marketplace_listings(db, latitude=latitude, longitude=longitude, radius_km=radius_km, city=city,
                                    connector_type=connector_type, max_price=max_price, viewer=viewer,
                                    vehicle=_vehicle(db, viewer, vehicle_id), compatible_only=bool(compatible_only))


@router.get("/listings/{listing_id}", response_model=HomeListingDetailOut)
def get_listing(listing_id: int, vehicle_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                viewer: Optional[User] = Depends(get_optional_user)):
    detail = get_home_listing_detail(db, listing_id, viewer, _vehicle(db, viewer, vehicle_id))
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return detail


@router.get("/my-listings", response_model=List[HomeListingOut])
def get_my_listings(host: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.query(HomeChargerListing).filter(HomeChargerListing.host_id == host.id).all()
    return [build_listing_out(i, exact=True, with_street=True) for i in items]


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def reserve_booking(data: BookingCreate, driver: User = Depends(get_current_user), db: Session = Depends(get_db)):
    booking = create_booking_reservation(db, driver, data)
    return build_booking_out(db, booking, driver)


@router.get("/bookings", response_model=List[BookingOut])
def get_user_bookings(role: Optional[str] = Query(None, description="Filter as 'driver' or 'host'"),
                      current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expire_stale_holds(db)
    if role == "host":
        rows = db.query(Booking).join(HomeChargerListing).filter(HomeChargerListing.host_id == current_user.id
                                                                 ).order_by(Booking.created_at.desc()).all()
    else:
        rows = db.query(Booking).filter(Booking.driver_id == current_user.id).order_by(Booking.created_at.desc()).all()
    return [build_booking_out(db, b, current_user) for b in rows]


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking_by_id(booking_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    expire_stale_holds(db)
    b = db.query(Booking).filter(Booking.id == booking_id).first()
    # 404 (not 403) for strangers so booking ids cannot be probed.
    if not b or not (b.driver_id == current_user.id or b.listing.host_id == current_user.id
                     or current_user.has_role("admin")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return build_booking_out(db, b, current_user)


@router.post("/bookings/{booking_id}/cancel", response_model=CancelOut)
def cancel(booking_id: int, data: CancelRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Driver/host/admin cancellation with the documented refund policy."""
    return cancel_booking(db, booking_id, data.reason, current_user)


@router.get("/bookings/{booking_id}/session", response_model=Optional[ChargingSessionOut])
def get_session(booking_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    b = db.query(Booking).filter(Booking.id == booking_id).first()
    if not b or not (b.driver_id == current_user.id or b.listing.host_id == current_user.id or current_user.has_role("admin")):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
    return session_out(b.session) if b.session else None


@router.post("/bookings/{booking_id}/session/start", response_model=ChargingSessionOut)
def start_charging_session(booking_id: int, data: ChargingSessionStart, current_user: User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    return session_out(start_session(db, booking_id, current_user, data))


@router.post("/bookings/{booking_id}/session/complete", response_model=ChargingSessionOut)
def complete_charging_session(booking_id: int, data: ChargingSessionComplete, current_user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """Records a MANUALLY entered energy figure (never presented as hardware-measured)."""
    return session_out(complete_session(db, booking_id, current_user, data))
