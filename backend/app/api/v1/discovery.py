from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User, Vehicle
from app.schemas.station import (
    ProviderMeta, PublicStationOut, StationDetailOut, StationFilterParams, StationSearchOut,
)
from app.services.auth_service import get_optional_user
from app.services.charger_service import get_public_stations, get_station_details
from app.services.geocoding_service import GeocodingUnavailable, geocode_city
from app.services.provider_sync import sync_area

router = APIRouter(prefix="/discovery", tags=["Public Charger Discovery"])


def _vehicle_for(db: Session, user: Optional[User], vehicle_id: Optional[int]) -> Optional[Vehicle]:
    if vehicle_id is None:
        return None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in to use a saved vehicle")
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.user_id == user.id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    return v


def _search(db, user, **q):
    vehicle = _vehicle_for(db, user, q.pop("vehicle_id"))
    params = StationFilterParams(**q)
    if params.latitude is not None and params.longitude is not None:
        meta = sync_area(db, params.latitude, params.longitude, params.radius_km)
    else:
        meta = {"status": "disabled" if not settings.USE_LIVE_CHARGER_FEED else "invalid_location",
                "message": "Provide a location to include live provider data. Showing local and sample data."}
    return get_public_stations(db, params, vehicle), meta


@router.get("/geocode")
async def geocode_location(
    city: str = Query(..., min_length=2, max_length=100),
):
    """Resolve a city/place name to coordinates (India only) for use with /search and /stations."""
    try:
        result = await geocode_city(city)
    except GeocodingUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location lookup is temporarily unavailable. Please try again shortly.",
        )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not find '{city}' in India. Check the spelling or try another location.",
        )

    return result


@router.get("/search", response_model=StationSearchOut)
def search_stations_with_provider_status(
    latitude: Optional[float] = Query(None, ge=-90, le=90), longitude: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(25.0, ge=1.0, le=200.0), city: Optional[str] = Query(None),
    query: Optional[str] = Query(None, max_length=100), connector_type: Optional[str] = Query(None),
    current_type: Optional[str] = Query(None), min_power_kw: Optional[float] = Query(None, ge=0),
    max_price_per_kwh: Optional[float] = Query(None, ge=0), operational_only: Optional[bool] = Query(None),
    vehicle_id: Optional[int] = Query(None), compatible_only: Optional[bool] = Query(None),
    db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user),
):
    """Station search plus an explicit statement of where the data came from (live / cached / unavailable / sample-only)."""
    stations, meta = _search(db, user, latitude=latitude, longitude=longitude, radius_km=radius_km, city=city,
                             query=query, connector_type=connector_type, current_type=current_type,
                             min_power_kw=min_power_kw, max_price_per_kwh=max_price_per_kwh,
                             operational_only=operational_only, vehicle_id=vehicle_id, compatible_only=compatible_only)
    return StationSearchOut(stations=stations, provider=ProviderMeta(
        **{k: v for k, v in meta.items() if k in ProviderMeta.model_fields}))


@router.get("/stations", response_model=List[PublicStationOut])
def search_public_stations(
    response: Response,
    latitude: Optional[float] = Query(None, ge=-90, le=90), longitude: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: float = Query(25.0, ge=1.0, le=200.0), city: Optional[str] = Query(None),
    query: Optional[str] = Query(None, max_length=100), connector_type: Optional[str] = Query(None),
    current_type: Optional[str] = Query(None), min_power_kw: Optional[float] = Query(None, ge=0),
    max_price_per_kwh: Optional[float] = Query(None, ge=0), operational_only: Optional[bool] = Query(None),
    vehicle_id: Optional[int] = Query(None), compatible_only: Optional[bool] = Query(None),
    db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user),
):
    """Backwards-compatible list endpoint; the provider status is reported in the X-Provider-Status header."""
    stations, meta = _search(db, user, latitude=latitude, longitude=longitude, radius_km=radius_km, city=city,
                             query=query, connector_type=connector_type, current_type=current_type,
                             min_power_kw=min_power_kw, max_price_per_kwh=max_price_per_kwh,
                             operational_only=operational_only, vehicle_id=vehicle_id, compatible_only=compatible_only)
    response.headers["X-Provider-Status"] = meta["status"]
    return stations


@router.get("/stations/{station_id}", response_model=StationDetailOut)
def get_station_by_id(station_id: int, vehicle_id: Optional[int] = Query(None), db: Session = Depends(get_db),
                      user: Optional[User] = Depends(get_optional_user)):
    details = get_station_details(db, station_id, _vehicle_for(db, user, vehicle_id))
    if not details:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public charging station not found")
    return details