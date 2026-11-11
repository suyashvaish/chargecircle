from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.marketplace import HomeChargerListing
from app.models.station import ChargingStation
from app.models.user import User
from app.services import routing
from app.services.auth_service import get_optional_user
from app.services.geo import approximate_coords, valid_coordinates
from app.services.marketplace_service import can_view_exact_location

router = APIRouter(prefix="/navigation", tags=["Navigation"])


def _links(dest, origin=None, origin_text=None):
    d = f"{dest[0]},{dest[1]}"
    g = f"https://www.google.com/maps/dir/?api=1&destination={quote(d)}&travelmode=driving"
    a = f"https://maps.apple.com/?daddr={quote(d)}&dirflg=d"
    o = f"{origin[0]},{origin[1]}" if origin else (origin_text or None)
    if o:
        g += f"&origin={quote(o)}"
        a += f"&saddr={quote(o)}"
    return {"google_maps": g, "apple_maps": a}


@router.get("/route")
def route(
    target_type: str = Query(..., pattern="^(station|listing)$"), target_id: int = Query(...),
    origin_lat: Optional[float] = Query(None, ge=-90, le=90), origin_lon: Optional[float] = Query(None, ge=-180, le=180),
    origin_text: Optional[str] = Query(None, max_length=200),
    db: Session = Depends(get_db), viewer: Optional[User] = Depends(get_optional_user),
):
    """
    Destination coordinates always come from the stored record. Home chargers navigate to an approximate pin
    until the viewer holds an eligible booking (decided here on the server).
    """
    if target_type == "station":
        s = db.query(ChargingStation).filter(ChargingStation.id == target_id, ChargingStation.is_active == True).first()  # noqa: E712
        if not s:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
        dest, approx, name = (s.latitude, s.longitude), False, s.name
    else:
        l = db.query(HomeChargerListing).filter(HomeChargerListing.id == target_id).first()
        if not l or (l.status != "approved" and not (viewer and (viewer.id == l.host_id or viewer.has_role("admin")))):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
        exact = can_view_exact_location(db, viewer, l)
        dest = (l.latitude, l.longitude) if exact else approximate_coords(l.id, l.latitude, l.longitude)
        approx, name = not exact, l.title
    if not valid_coordinates(*dest):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "This charger has no valid coordinates, so navigation is unavailable.")
    origin = (origin_lat, origin_lon) if origin_lat is not None and origin_lon is not None else None
    result = {"destination": {"name": name, "latitude": dest[0], "longitude": dest[1], "is_approximate": approx},
              "links": _links(dest, origin, origin_text), "route": None,
              "note": ("Navigation goes to an approximate pin. The exact address is shared once your booking is confirmed." if approx else None),
              "in_app_turn_by_turn": False}
    if origin:
        result["route"] = routing.get_route(origin, dest)
    elif origin_text:
        result["route"] = {"available": False, "reason": "text_origin", "message": "A route preview needs coordinates. Open the link to navigate from the address you entered."}
    return result
