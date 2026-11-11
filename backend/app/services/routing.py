"""Optional road routing via OpenRouteService. Without a configured key nothing is invented."""
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import settings
from app.services.geo import valid_coordinates

_transport: Optional[httpx.BaseTransport] = None  # tests inject a mock transport


def routing_available() -> bool:
    return settings.ROUTING_PROVIDER == "openrouteservice" and bool(settings.ORS_API_KEY)


def _post(path: str, payload: dict) -> Optional[dict]:
    try:
        with httpx.Client(timeout=settings.ROUTING_TIMEOUT_SECONDS, transport=_transport) as client:
            resp = client.post(f"{settings.ORS_BASE_URL.rstrip('/')}{path}", json=payload,
                               headers={"Authorization": settings.ORS_API_KEY, "Accept": "application/json"})
        if resp.status_code != 200:
            return None
        return resp.json()
    except (httpx.HTTPError, ValueError):
        return None


def get_route(origin: Tuple[float, float], dest: Tuple[float, float]) -> Dict:
    """origin/dest are (lat, lon). Distance and time are returned only if the routing service returned them."""
    if not (valid_coordinates(*origin) and valid_coordinates(*dest)):
        return {"available": False, "reason": "invalid_coordinates", "message": "Valid origin and destination coordinates are required."}
    if not routing_available():
        return {"available": False, "reason": "not_configured",
                "message": "Road distance and travel time are unavailable because no routing service is configured. Use the navigation links to get live directions."}
    data = _post("/v2/directions/driving-car/geojson", {"coordinates": [[origin[1], origin[0]], [dest[1], dest[0]]]})
    try:
        feat = data["features"][0]
        summary = feat["properties"]["summary"]
        coords = feat["geometry"]["coordinates"]
        return {"available": True, "provider": "OpenRouteService",
                "distance_km": round(summary["distance"] / 1000.0, 1),
                "duration_min": round(summary["duration"] / 60.0),
                "geometry": [[c[1], c[0]] for c in coords][:2000]}
    except (TypeError, KeyError, IndexError):
        return {"available": False, "reason": "provider_error",
                "message": "The routing service did not return a usable route. Use the navigation links instead."}


def get_matrix(origin: Tuple[float, float], dests: List[Tuple[float, float]]) -> Optional[List[Dict]]:
    """Road distance/time from one origin to many destinations, or None if unavailable."""
    if not routing_available() or not dests or not valid_coordinates(*origin):
        return None
    locations = [[origin[1], origin[0]]] + [[d[1], d[0]] for d in dests]
    data = _post("/v2/matrix/driving-car", {"locations": locations, "sources": [0], "metrics": ["distance", "duration"]})
    try:
        dist, dur = data["distances"][0][1:], data["durations"][0][1:]
        if len(dist) != len(dests):
            return None
        return [{"road_distance_km": None if d is None else round(d / 1000.0, 1),
                 "travel_minutes": None if t is None else round(t / 60.0)} for d, t in zip(dist, dur)]
    except (TypeError, KeyError, IndexError):
        return None
