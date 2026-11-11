"""Geographic and time helpers shared by discovery, marketplace and navigation."""
import hashlib
import hmac
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings

IST = ZoneInfo("Asia/Kolkata")
EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (straight-line) distance in km. This is NOT a road distance."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2)
    return EARTH_RADIUS_KM * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def as_utc(dt: datetime) -> datetime:
    """Normalises naive datetimes (SQLite returns them naive) to aware UTC."""
    if dt is None:
        return dt
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def valid_coordinates(lat, lon) -> bool:
    return (isinstance(lat, (int, float)) and isinstance(lon, (int, float))
            and -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0 and not (lat == 0 and lon == 0))


def approximate_coords(listing_id: int, lat: float, lon: float) -> tuple:
    """
    Privacy-preserving public pin for a home charger.

    The true point is moved by a stable, secret-keyed offset of LOCATION_FUZZ_MIN..MAX metres in a
    direction nobody without SECRET_KEY can recover, so repeated requests cannot be averaged out.
    """
    digest = hmac.new(settings.SECRET_KEY.encode(), f"loc:{listing_id}".encode(), hashlib.sha256).digest()
    angle = (int.from_bytes(digest[:4], "big") / 0xFFFFFFFF) * 2.0 * math.pi
    frac = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    metres = settings.LOCATION_FUZZ_MIN_METERS + frac * (
        settings.LOCATION_FUZZ_MAX_METERS - settings.LOCATION_FUZZ_MIN_METERS)
    dlat = (metres * math.cos(angle)) / 111_320.0
    dlon = (metres * math.sin(angle)) / (111_320.0 * max(math.cos(math.radians(lat)), 0.01))
    return round(lat + dlat, 5), round(lon + dlon, 5)
