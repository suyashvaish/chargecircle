import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional  # noqa: F401
import httpx
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.enums import CurrentType, OperationalStatus
from app.models.reliability import ChargerStatusSnapshot
from app.models.station import ChargerConnector, ChargingPoint, ChargingStation
from app.schemas.station import PublicStationOut, StationDetailOut, StationFilterParams
from app.services import compatibility as compat
from app.services.pricing import SOURCE_LABELS, connector_price, station_price_summary
from app.services.provider_sync import is_probable_duplicate


def calculate_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two coordinates in kilometers."""
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class OpenChargeMapAdapter:
    """Adapter for retrieving live charging data from Open Charge Map API."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.OCM_API_KEY
        self.base_url = base_url or settings.OCM_BASE_URL

    async def fetch_live_poi(
        self, latitude: float, longitude: float, distance_km: float = 25.0
    ) -> List[Dict[str, Any]]:
        if not self.api_key:
            return []
        
        params = {
            "key": self.api_key,
            "latitude": latitude,
            "longitude": longitude,
            "distance": distance_km,
            "distanceunit": "KM",
            "countrycode": "IN",
            "maxresults": 50,
            "compact": True,
            "verbose": False
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.base_url, params=params)
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            return []
        return []


def _origin(station: ChargingStation) -> str:
    if station.source == "open_charge_map":
        return "provider"
    return "sample" if station.is_sample else "manual"


def _connector_out(conn: ChargerConnector) -> Dict[str, Any]:
    return {"id": conn.id, "connector_type": conn.connector_type, "current_type": conn.current_type,
            "power_kw": conn.power_kw, **connector_price(conn)}


def _build_station(db: Session, station: ChargingStation, dist_km: Optional[float], vehicle=None) -> Dict[str, Any]:
    connectors_summary: List[str] = []
    max_power = 0.0
    all_conns: List[ChargerConnector] = []
    for pt in station.points:
        for conn in pt.connectors:
            all_conns.append(conn)
            c_str = (f"{conn.connector_type} ({conn.power_kw:g}kW {conn.current_type})" if conn.power_kw
                     else f"{conn.connector_type} (power not stated, {conn.current_type})")
            if c_str not in connectors_summary:
                connectors_summary.append(c_str)
            if conn.power_kw and conn.power_kw > max_power:
                max_power = conn.power_kw
    snap = db.query(ChargerStatusSnapshot).filter(ChargerStatusSnapshot.station_id == station.id
                                                  ).order_by(ChargerStatusSnapshot.calculated_at.desc()).first()
    data = dict(
        id=station.id, external_id=station.external_id, name=station.name, operator_name=station.operator_name,
        address=station.address, locality=station.locality, city=station.city, state=station.state,
        pin_code=station.pin_code, latitude=station.latitude, longitude=station.longitude,
        distance_km=round(dist_km, 1) if dist_km is not None else None, access_type=station.access_type,
        operating_hours=station.operating_hours, is_open_24_7=station.is_open_24_7, parking_fee=station.parking_fee,
        is_sample=station.is_sample, data_source=station.data_source, data_origin=_origin(station),
        source_url=station.source_url, last_synced_at=station.last_synced_at,
        provider_last_verified_at=station.provider_last_verified_at, provider_status=station.provider_status,
        usage_cost_text=station.usage_cost_text, membership_required=station.membership_required,
        pay_at_location=station.pay_at_location, connectors_summary=connectors_summary,
        max_power_kw=max_power if max_power > 0 else None,
        current_status=snap.operational_status if snap else OperationalStatus.UNKNOWN.value,
        confidence_score=snap.confidence_score if snap else 0.5,
        last_verified_at=snap.last_reported_at if snap else None, created_at=station.created_at,
        **station_price_summary(station),
    )
    if vehicle is not None:
        data["compatibility"] = compat.evaluate_charger(vehicle, all_conns)
    return data, snap


def get_public_stations(db: Session, params: StationFilterParams, vehicle=None) -> List[PublicStationOut]:
    """
    Discovers nearby public EV charging stations from the local store (which includes any provider data
    already synced). Sample/manual/provider origin is always reported; nothing is presented as live status.
    """
    query = db.query(ChargingStation).filter(ChargingStation.is_active == True)  # noqa: E712
    if params.city:
        query = query.filter(ChargingStation.city.ilike(f"%{params.city.strip()}%"))
    if params.query:
        term = f"%{params.query.strip()}%"
        query = query.filter((ChargingStation.name.ilike(term)) | (ChargingStation.address.ilike(term)) |
                             (ChargingStation.locality.ilike(term)) | (ChargingStation.pin_code.ilike(term)) |
                             (ChargingStation.operator_name.ilike(term)))
    has_loc = params.latitude is not None and params.longitude is not None
    if has_loc:  # bounding box pre-filter, then exact great-circle check
        dlat = params.radius_km / 111.0
        dlon = params.radius_km / (111.0 * max(math.cos(math.radians(params.latitude)), 0.01))
        query = query.filter(ChargingStation.latitude.between(params.latitude - dlat, params.latitude + dlat),
                             ChargingStation.longitude.between(params.longitude - dlon, params.longitude + dlon))

    results: List[PublicStationOut] = []
    for station in query.all():
        dist_km = calculate_haversine(params.latitude, params.longitude, station.latitude, station.longitude) if has_loc else None
        if dist_km is not None and dist_km > params.radius_km:
            continue
        conns = [c for pt in station.points for c in pt.connectors]
        if params.connector_type and not any(params.connector_type.lower() in c.connector_type.lower() for c in conns):
            continue
        if params.current_type and not any(params.current_type.upper() == c.current_type.upper() for c in conns):
            continue
        if params.min_power_kw is not None and not any((c.power_kw or 0) >= params.min_power_kw for c in conns):
            continue
        if params.max_price_per_kwh is not None and not any(
                c.pricing_per_kwh is not None and c.pricing_per_kwh <= params.max_price_per_kwh for c in conns):
            continue  # unknown prices never satisfy a price ceiling
        data, snap = _build_station(db, station, dist_km, vehicle)
        if params.operational_only and data["current_status"] == OperationalStatus.REPORTED_UNAVAILABLE.value:
            continue
        if params.compatible_only and vehicle is not None and data["compatibility"]["status"] == "incompatible":
            continue
        results.append(PublicStationOut(**data))

    # Response-level de-duplication: when a provider record and a sample record describe the same place, prefer the provider record.
    keep: List[PublicStationOut] = []
    for s in sorted(results, key=lambda x: 0 if x.data_origin == "provider" else (1 if x.data_origin == "manual" else 2)):
        if any(k.id != s.id and is_probable_duplicate(k.latitude, k.longitude, k.name, k.operator_name,
                                                      s.latitude, s.longitude, s.name, s.operator_name) for k in keep):
            continue
        keep.append(s)
    if has_loc:
        keep.sort(key=lambda s: s.distance_km if s.distance_km is not None else 99999)
    return keep


def get_station_details(db: Session, station_id: int, vehicle=None) -> Optional[StationDetailOut]:
    station = db.query(ChargingStation).filter(ChargingStation.id == station_id).first()
    if not station:
        return None
    data, snap = _build_station(db, station, None, vehicle)
    points = []
    for pt in station.points:
        points.append({"id": pt.id, "point_identifier": pt.point_identifier, "status": pt.status,
                       "last_status_update": pt.last_status_update,
                       "connectors": [_connector_out(c) for c in pt.connectors]})
    attribution = ("Station data © Open Charge Map contributors (openchargemap.org). Community-maintained; "
                   "it does not include live connector availability." if station.source == "open_charge_map" else None)
    return StationDetailOut(**data, general_notes=station.general_notes, points=points,
                            status_snapshot=snap, attribution=attribution)
