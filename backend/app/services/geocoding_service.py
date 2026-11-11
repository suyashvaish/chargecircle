
import asyncio
import logging
import time
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

# Nominatim's usage policy requires a User-Agent that identifies your app.
# Replace this with your real application contact before production.
USER_AGENT = "ChargeCircle/1.0 (location lookup)"

# Nominatim allows at most 1 request per second.
MIN_INTERVAL_SECONDS = 1.1

CACHE_TTL_SECONDS = 24 * 60 * 60
CACHE_MAX_ENTRIES = 1000


class GeocodingUnavailable(Exception):
    """The geocoding provider failed (network error, timeout, rate limit, bad response)."""


# key -> (expires_at, result or None). Failures are never cached.
_cache: dict[str, tuple[float, Optional[dict]]] = {}
_rate_lock = asyncio.Lock()
_last_request_at = 0.0


async def geocode_city(city: str) -> Optional[dict]:
    """
    Resolve an Indian city/locality into coordinates.

    Returns None when the location genuinely cannot be found.
    Raises GeocodingUnavailable when the provider itself fails,
    so callers can tell "not found" apart from "service down".
    """
    global _last_request_at

    city = " ".join(city.split())
    if not city or len(city) > 100:
        return None

    key = city.casefold()
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return dict(cached[1]) if cached[1] else None

    params = {
        "q": city,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "in",
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en",
    }

    async with _rate_lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.get(NOMINATIM_URL, params=params, headers=headers)
                response.raise_for_status()
                results = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Geocoding provider failed for %r: %s", city, exc)
            raise GeocodingUnavailable from exc
        finally:
            _last_request_at = time.monotonic()

    result: Optional[dict] = None
    if results:
        try:
            first = results[0]
            result = {
                "city": city,
                "display_name": first.get("display_name"),
                "latitude": float(first["lat"]),
                "longitude": float(first["lon"]),
            }
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            logger.warning("Unexpected geocoding response for %r: %s", city, exc)
            raise GeocodingUnavailable from exc

    if len(_cache) >= CACHE_MAX_ENTRIES:
        _cache.pop(next(iter(_cache)))  # evict oldest entry
    _cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, result)

    return dict(result) if result else None