from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.marketplace import HomeChargerListing
from app.models.station import ChargingStation
from app.models.user import User
from app.api.v1.pricing import EstimateRequest, pick_connector, resolve_energy
from app.core.config import settings
from app.services import compatibility as compat
from app.services import routing
from app.services.auth_service import get_optional_user
from app.services.charger_service import get_public_stations
from app.services.geo import approximate_coords, haversine_km
from app.services.marketplace_service import can_view_exact_location
from app.services.pricing import estimate_home_cost, estimate_station_cost
from app.schemas.station import StationFilterParams
from app.services.provider_sync import sync_area

router = APIRouter(prefix="/compare", tags=["Price Comparison"])


@router.get("")
def compare(
    latitude: float = Query(..., ge=-90, le=90), longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(15.0, ge=1, le=100), energy_kwh: Optional[float] = Query(None, gt=0, le=500),
    vehicle_id: Optional[int] = Query(None), from_soc_percent: Optional[float] = Query(None, ge=0, le=100),
    to_soc_percent: Optional[float] = Query(None, ge=0, le=100), hours: Optional[float] = Query(None, gt=0, le=24),
    include: str = Query("both", pattern="^(both|stations|homes)$"), limit: int = Query(20, ge=1, le=40),
    db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user),
):
    """
    Side-by-side comparison of public stations and home chargers for the same energy need.
    Straight-line distance is reported separately from road distance, which exists only if a routing service is configured.
    """
    req = EstimateRequest(target_type="station", target_id=0, energy_kwh=energy_kwh, vehicle_id=vehicle_id,
                          from_soc_percent=from_soc_percent, to_soc_percent=to_soc_percent)
    vehicle, energy, energy_note = resolve_energy(db, user, req)
    cands: List[Dict[str, Any]] = []
    provider_meta = None

    if include in ("both", "stations"):
        provider_meta = sync_area(db, latitude, longitude, radius_km)
        params = StationFilterParams(latitude=latitude, longitude=longitude, radius_km=radius_km)
        for s in get_public_stations(db, params, vehicle):
            st = db.query(ChargingStation).filter(ChargingStation.id == s.id).first()
            conn = pick_connector(st, vehicle, None)
            comp = s.compatibility.model_dump() if s.compatibility else None
            if conn is None:
                continue
            eff = compat.evaluate_connector(vehicle, conn.connector_type, conn.current_type, conn.power_kw)["effective_power_kw"] if vehicle else None
            est = estimate_station_cost(st, conn, energy, effective_power_kw=eff)
            cands.append({
                "kind": "station", "id": st.id, "name": st.name, "operator": st.operator_name, "address": st.address,
                "latitude": st.latitude, "longitude": st.longitude, "is_approximate_location": False,
                "distance_straight_km": s.distance_km, "access_type": st.access_type,
                "access_note": "Membership required" if st.membership_required else ("Pay at location" if st.pay_at_location else None),
                "connector": f"{conn.connector_type} ({conn.power_kw:g} kW {conn.current_type})" if conn.power_kw else f"{conn.connector_type} ({conn.current_type})",
                "rated_power_kw": conn.power_kw, "effective_power_kw": eff, "compatibility": comp,
                "estimate": est, "data_origin": s.data_origin, "data_freshness": {
                    "price_updated_at": conn.price_updated_at, "station_synced_at": st.last_synced_at},
                "availability": {"status": s.current_status, "confidence": s.confidence_score,
                                 "note": "Based on community reports and provider notes; not live connector availability."},
                "booking_conditions": None, "link": f"/public-chargers/{st.id}"})

    if include in ("both", "homes"):
        for item in db.query(HomeChargerListing).filter(HomeChargerListing.status == "approved").all():
            exact = can_view_exact_location(db, user, item)
            alat, alon = (item.latitude, item.longitude) if exact else approximate_coords(item.id, item.latitude, item.longitude)
            dist = round(haversine_km(latitude, longitude, alat, alon), 1)
            if dist > radius_km:
                continue
            class _C:
                connector_type, current_type, power_kw, cable_attached = item.connector_type, item.current_type, item.power_kw, item.is_cable_attached
            comp = compat.evaluate_charger(vehicle, [_C]) if vehicle else None
            hrs = hours or max(item.minimum_booking_hours, energy / item.power_kw)
            est = estimate_home_cost(item, energy, hrs)
            if not hours:
                est["assumptions"].append(f"Booked time assumed at {hrs:.2f} h.")
            cands.append({
                "kind": "home", "id": item.id, "name": item.title, "operator": "Home host", "address": f"{item.locality}, {item.city}",
                "latitude": alat, "longitude": alon, "is_approximate_location": not exact,
                "distance_straight_km": dist, "access_type": "private (booking required)", "access_note": "Exact address shared after booking is confirmed",
                "connector": f"{item.connector_type} ({item.power_kw:g} kW {item.current_type})", "rated_power_kw": item.power_kw,
                "effective_power_kw": comp["effective_power_kw"] if comp else None, "compatibility": comp, "estimate": est,
                "data_origin": "host", "data_freshness": {"price_updated_at": item.updated_at, "station_synced_at": None},
                "availability": {"status": "Bookable by time slot", "confidence": None, "note": "Slots are checked when you book."},
                "booking_conditions": {"minimum_hours": item.minimum_booking_hours, "cancellation_policy": item.cancellation_policy,
                                       "instant_booking": item.instant_booking},
                "link": f"/marketplace/{item.id}"})

    if vehicle is not None:
        cands = [c for c in cands if not c["compatibility"] or c["compatibility"]["status"] != "incompatible"] + \
                [c for c in cands if c["compatibility"] and c["compatibility"]["status"] == "incompatible"]

    # Road distance only from a configured routing service.
    cands = cands[: 4 * limit]
    cands.sort(key=lambda c: c["distance_straight_km"] if c["distance_straight_km"] is not None else 9999)
    cands = cands[: max(limit, 1) * 2]
    matrix = routing.get_matrix((latitude, longitude), [(c["latitude"], c["longitude"]) for c in cands])
    for i, c in enumerate(cands):
        c["road_distance_km"] = matrix[i]["road_distance_km"] if matrix else None
        c["travel_minutes"] = matrix[i]["travel_minutes"] if matrix else None

    def rank(c):
        e = c["estimate"]
        comp_bad = c["compatibility"] and c["compatibility"]["status"] == "incompatible"
        return (1 if comp_bad else 0, 0 if e["is_complete"] else 1, e["total_known"] if e["is_complete"] else (c["distance_straight_km"] or 9999))
    cands.sort(key=rank)
    cands = cands[:limit]
    cheapest = next((c for c in cands if c["estimate"]["is_complete"] and not (c["compatibility"] and c["compatibility"]["status"] == "incompatible")), None)
    for c in cands:
        c["is_lowest_estimated_total"] = bool(cheapest and c["kind"] == cheapest["kind"] and c["id"] == cheapest["id"])
        c["price_label"] = ("Confirmed host price" if c["estimate"]["price_confidence"] == "confirmed"
                            else "Estimate (all listed fees known)" if c["estimate"]["is_complete"]
                            else "Partial estimate: unknown fees excluded" if c["estimate"]["price_confidence"] == "partial"
                            else "Price unavailable")
    return {
        "currency": "INR", "energy_kwh": energy, "energy_note": energy_note,
        "routing": {"road_distance_available": bool(matrix), "message": None if matrix else "Road distance and travel time are not shown because no routing service is configured. Distances are straight-line."},
        "provider": provider_meta, "lowest_estimated_total_id": ({"kind": cheapest["kind"], "id": cheapest["id"]} if cheapest else None),
        "note": "Only options whose prices are fully known can be marked lowest. Unknown prices are never assumed.",
        "candidates": cands}
