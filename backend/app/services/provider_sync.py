"""Open Charge Map integration: fetch, normalise, de-duplicate, store and cache public charger data."""
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.provider import ProviderSearchCache
from app.models.station import ChargerConnector, ChargingPoint, ChargingStation
from app.services.compatibility import normalize_connector
from app.services.geo import as_utc, haversine_km, valid_coordinates

logger = logging.getLogger("chargecircle.provider")
PROVIDER = "open_charge_map"
_transport: Optional[httpx.BaseTransport] = None  # tests inject httpx.MockTransport here

_DC_ONLY = {"CCS2", "CHAdeMO", "Bharat DC-001"}
_AC_ONLY = {"Type 2", "Type 1", "Bharat AC-001", "16A 3-Pin Socket"}
# Only an unambiguous "<number> per kWh" statement is turned into a number; everything else stays text.
_PRICE_RE = re.compile(r"^\s*(?:₹|rs\.?|inr)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:/|per)\s*kwh\s*\.?\s*$", re.IGNORECASE)


# ---- fetching -------------------------------------------------------------------------------

def fetch_pois(lat: float, lon: float, radius_km: float) -> Dict[str, Any]:
    """Returns {"status": ok|timeout|rate_limited|unavailable|malformed, "pois": [...], "retry_after": int|None}."""
    params = {"latitude": lat, "longitude": lon, "distance": radius_km, "distanceunit": "KM",
              "countrycode": "IN", "maxresults": settings.OCM_MAX_RESULTS, "compact": "false", "verbose": "false"}
    try:
        with httpx.Client(timeout=settings.OCM_TIMEOUT_SECONDS, transport=_transport) as client:
            resp = client.get(settings.OCM_BASE_URL, params=params, headers={"X-API-Key": settings.OCM_API_KEY or ""})
    except httpx.TimeoutException:
        return {"status": "timeout", "pois": []}
    except httpx.HTTPError:
        return {"status": "unavailable", "pois": []}
    if resp.status_code == 429:
        try:
            ra = int(resp.headers.get("Retry-After", ""))
        except ValueError:
            ra = None
        return {"status": "rate_limited", "pois": [], "retry_after": ra}
    if resp.status_code in (401, 403):
        return {"status": "unavailable", "pois": [], "detail": "provider rejected the API key"}
    if resp.status_code != 200:
        return {"status": "unavailable", "pois": []}
    try:
        data = resp.json()
    except ValueError:
        return {"status": "malformed", "pois": []}
    if not isinstance(data, list):
        return {"status": "malformed", "pois": []}
    return {"status": "ok", "pois": data}


# ---- normalising ----------------------------------------------------------------------------

def _parse_dt(value) -> Optional[datetime]:
    if not value or not isinstance(value, str):
        return None
    try:
        return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def normalize_poi(poi: Any) -> Optional[Dict[str, Any]]:
    """Maps an OCM POI to the internal station format. Returns None for unusable records. Never invents data."""
    if not isinstance(poi, dict) or poi.get("ID") is None:
        return None
    addr = poi.get("AddressInfo")
    if not isinstance(addr, dict):
        return None
    lat, lon = addr.get("Latitude"), addr.get("Longitude")
    if not valid_coordinates(lat, lon):
        return None
    usage = poi.get("UsageType") or {}
    if usage.get("IsMembershipRequired") or usage.get("IsAccessKeyRequired"):
        access = "semi-public"
    elif usage:
        access = "public"
    else:
        access = "unknown"
    cost_text = (poi.get("UsageCost") or "").strip()[:500] or None
    m = _PRICE_RE.match(cost_text) if cost_text else None

    connectors: List[Dict[str, Any]] = []
    for c in poi.get("Connections") or []:
        if not isinstance(c, dict):
            continue
        ct = c.get("ConnectionType") or {}
        raw = ct.get("FormalName") or ct.get("Title") or ""
        ctype = normalize_connector(raw) or normalize_connector(ct.get("Title")) or (ct.get("Title") or "Unknown")
        cur_title = ((c.get("CurrentType") or {}).get("Title") or "").upper()
        if "DC" in cur_title:
            cur = "DC"
        elif "AC" in cur_title:
            cur = "AC"
        elif ctype in _DC_ONLY:
            cur = "DC"
        elif ctype in _AC_ONLY:
            cur = "AC"
        else:
            cur = "UNKNOWN"
        kw = c.get("PowerKW")
        connectors.append({"connector_type": ctype, "current_type": cur,
                           "power_kw": float(kw) if isinstance(kw, (int, float)) and kw > 0 else None,
                           "quantity": c.get("Quantity") if isinstance(c.get("Quantity"), int) else None})
    town = addr.get("Town") or addr.get("StateOrProvince") or "Unknown"
    return {
        "external_id": str(poi["ID"]),
        "name": (addr.get("Title") or "Unnamed charging location")[:255],
        "operator_name": ((poi.get("OperatorInfo") or {}).get("Title") or "Unknown operator")[:150],
        "address": (", ".join(x for x in [addr.get("AddressLine1"), addr.get("AddressLine2")] if x) or town)[:500],
        "locality": addr.get("Town"), "city": town[:100],
        "state": (addr.get("StateOrProvince") or "Unknown")[:100],
        "pin_code": (addr.get("Postcode") or "Unknown")[:20],
        "latitude": float(lat), "longitude": float(lon), "access_type": access,
        "membership_required": usage.get("IsMembershipRequired") if usage else None,
        "pay_at_location": usage.get("IsPayAtLocation") if usage else None,
        "usage_cost_text": cost_text, "price_per_kwh": float(m.group(1)) if m else None,
        "provider_status": ((poi.get("StatusType") or {}).get("Title")),
        "provider_last_verified_at": _parse_dt(poi.get("DateLastVerified")) or _parse_dt(poi.get("DateLastStatusUpdate")),
        "source_url": f"https://openchargemap.org/site/poi/details/{poi['ID']}",
        "connectors": connectors,
    }


# ---- de-duplication -------------------------------------------------------------------------

def _tokens(text: str) -> set:
    return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}


def names_similar(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.4


def is_probable_duplicate(lat1, lon1, name1, op1, lat2, lon2, name2, op2) -> bool:
    """Same physical place: within DEDUPE_RADIUS_METERS and either a similar name or the same operator."""
    if haversine_km(lat1, lon1, lat2, lon2) * 1000.0 > settings.DEDUPE_RADIUS_METERS:
        return False
    same_op = bool(op1 and op2 and op1.strip().lower() == op2.strip().lower() and "unknown" not in op1.lower())
    return names_similar(name1, name2) or same_op


def _find_local_duplicate(db: Session, n: Dict[str, Any]) -> Optional[ChargingStation]:
    """Matches against hand-entered local stations (never against sample rows or other provider rows)."""
    dlat = settings.DEDUPE_RADIUS_METERS / 111_320.0 * 1.5
    cands = db.query(ChargingStation).filter(
        ChargingStation.source == "manual",
        ChargingStation.latitude.between(n["latitude"] - dlat, n["latitude"] + dlat),
        ChargingStation.longitude.between(n["longitude"] - dlat * 2, n["longitude"] + dlat * 2)).all()
    for s in cands:
        if is_probable_duplicate(n["latitude"], n["longitude"], n["name"], n["operator_name"],
                                 s.latitude, s.longitude, s.name, s.operator_name):
            return s
    return None


# ---- storing --------------------------------------------------------------------------------

def _upsert(db: Session, n: Dict[str, Any], now: datetime) -> str:
    st = db.query(ChargingStation).filter(ChargingStation.external_provider == PROVIDER,
                                          ChargingStation.external_id == n["external_id"]).first()
    verified_prices: Dict[tuple, ChargerConnector] = {}
    if st is None:
        if _find_local_duplicate(db, n):
            return "deduplicated"
        st = ChargingStation(external_provider=PROVIDER, external_id=n["external_id"], created_at=now,
                             source="open_charge_map", is_sample=False)
        db.add(st)
        outcome = "created"
    else:
        outcome = "updated"
        for pt in st.points:
            for c in pt.connectors:
                if c.price_verified:
                    verified_prices[(c.connector_type, c.current_type, c.power_kw)] = c
        for pt in list(st.points):
            db.delete(pt)
        db.flush()
    st.name, st.operator_name, st.address = n["name"], n["operator_name"], n["address"]
    st.locality, st.city, st.state, st.pin_code = n["locality"], n["city"], n["state"], n["pin_code"]
    st.latitude, st.longitude, st.access_type = n["latitude"], n["longitude"], n["access_type"]
    st.membership_required, st.pay_at_location = n["membership_required"], n["pay_at_location"]
    st.usage_cost_text, st.provider_status = n["usage_cost_text"], n["provider_status"]
    st.provider_last_verified_at, st.source_url = n["provider_last_verified_at"], n["source_url"]
    st.data_source, st.source, st.last_synced_at, st.is_active = "Open Charge Map", "open_charge_map", now, True
    st.operating_hours = st.operating_hours or "Not stated by provider"
    st.is_open_24_7 = bool(st.is_open_24_7) if st.operating_hours == "24/7 Open" else False
    st.parking_fee = None
    db.flush()
    pt = ChargingPoint(station_id=st.id, point_identifier="Provider listing", status="unknown", last_status_update=now)
    db.add(pt)
    db.flush()
    for c in n["connectors"]:
        prior = verified_prices.get((c["connector_type"], c["current_type"], c["power_kw"]))
        conn = ChargerConnector(point_id=pt.id, connector_type=c["connector_type"], current_type=c["current_type"],
                                power_kw=c["power_kw"])
        if prior is not None:  # never overwrite an admin/operator-verified price with provider data
            for f in ("pricing_per_kwh", "session_fee", "time_fee_per_min", "idle_fee_per_min", "taxes_included",
                      "price_source", "price_updated_at", "price_verified"):
                setattr(conn, f, getattr(prior, f))
        elif n["price_per_kwh"] is not None:
            conn.pricing_per_kwh, conn.price_source, conn.price_updated_at = n["price_per_kwh"], "provider", now
        db.add(conn)
    return outcome


def _cache_key(lat: float, lon: float, radius_km: float) -> str:
    bucket = int(math.ceil(radius_km / 10.0) * 10)
    return f"{PROVIDER}:{round(lat, 2)}:{round(lon, 2)}:{bucket}"


def sync_area(db: Session, lat: float, lon: float, radius_km: float) -> Dict[str, Any]:
    """
    Ensures provider data for an area is stored locally, calling the provider only when needed.
    Returns metadata for the UI: status = live | cached | disabled | not_configured | timeout | rate_limited
    | unavailable | malformed | invalid_location.
    """
    meta: Dict[str, Any] = {"provider": "Open Charge Map", "status": "disabled", "fetched_at": None,
                            "radius_km_used": None, "radius_limited": False, "message": "", "count": 0}
    if not settings.USE_LIVE_CHARGER_FEED:
        meta["message"] = "The live station feed is switched off. Results are limited to local and sample data."
        return meta
    if not settings.OCM_API_KEY:
        meta.update(status="not_configured", message="No Open Charge Map API key is configured, so only local and sample data are shown.")
        return meta
    if not valid_coordinates(lat, lon):
        meta.update(status="invalid_location", message="A valid search location is required to query the live feed.")
        return meta

    used = min(radius_km, settings.OCM_MAX_RADIUS_KM)
    meta["radius_km_used"], meta["radius_limited"] = used, radius_km > used
    key = _cache_key(lat, lon, used)
    now = datetime.now(timezone.utc)
    entry = db.query(ProviderSearchCache).filter(ProviderSearchCache.cache_key == key).first()
    if entry:
        age = (now - as_utc(entry.fetched_at)).total_seconds()
        if entry.status == "ok" and age < settings.OCM_CACHE_TTL_SECONDS:
            meta.update(status="cached", fetched_at=as_utc(entry.fetched_at), count=entry.result_count,
                        message=f"Showing stored Open Charge Map data fetched {int(age // 60)} min ago (not a live status).")
            return meta
        if entry.status != "ok":
            backoff = settings.OCM_ERROR_BACKOFF_SECONDS
            m = re.search(r"retry_after=(\d+)", entry.error or "")
            if m:
                backoff = max(backoff, int(m.group(1)))
            if age < backoff:
                meta.update(status=entry.status if entry.status == "rate_limited" else "unavailable",
                            fetched_at=as_utc(entry.fetched_at),
                            message="The live station provider is temporarily unavailable. Showing previously stored, local and sample data.")
                return meta

    result = fetch_pois(lat, lon, used)
    if entry is None:
        entry = ProviderSearchCache(cache_key=key, provider=PROVIDER, status="error", result_count=0)
        db.add(entry)
    entry.fetched_at = now
    if result["status"] != "ok":
        entry.status = "rate_limited" if result["status"] == "rate_limited" else "error"
        entry.error = result["status"] + (f" retry_after={result['retry_after']}" if result.get("retry_after") else "")
        db.commit()
        messages = {
            "timeout": "The live station provider timed out.",
            "rate_limited": "The live station provider is rate-limiting requests.",
            "malformed": "The live station provider returned data we could not read.",
            "unavailable": "The live station provider is unavailable.",
        }
        meta.update(status=result["status"], message=messages.get(result["status"], "The provider is unavailable.")
                    + " Showing previously stored, local and sample data.")
        return meta

    counts = {"created": 0, "updated": 0, "deduplicated": 0, "skipped": 0}
    for poi in result["pois"]:
        n = normalize_poi(poi)
        if n is None:
            counts["skipped"] += 1
            continue
        try:
            with db.begin_nested():  # a bad record rolls back only itself
                counts[_upsert(db, n, now)] += 1
        except Exception:
            logger.exception("failed to store provider record")
            counts["skipped"] += 1
    entry.status, entry.error, entry.result_count, entry.fetched_at = "ok", None, len(result["pois"]), now
    db.commit()
    meta.update(status="live", fetched_at=now, count=len(result["pois"]), counts=counts,
                message="Station details were just fetched from Open Charge Map. Provider data is community-maintained and does not include live connector availability.")
    return meta
