"""Price display, cost estimation and the shared home-charger price calculation."""
from datetime import datetime
from typing import Dict, List, Optional

from app.core.config import settings

CURRENCY = "INR"
SOURCE_LABELS = {
    "operator": "Operator-provided",
    "provider": "Provider-supplied (Open Charge Map)",
    "user_reported": "User-reported",
    "sample": "Sample dataset (not a real price)",
}


def _r(x: float) -> float:
    return round(x + 1e-9, 2)


def connector_price(conn) -> Dict:
    """Public price information for one connector. Unknown stays None; 'verified' only if flagged by an admin/operator."""
    known = [conn.pricing_per_kwh is not None, conn.session_fee is not None, conn.time_fee_per_min is not None]
    if conn.pricing_per_kwh is None and not any(known):
        status = "unavailable"
    elif conn.pricing_per_kwh is None:
        status = "partial"
    elif all(known):
        status = "complete"
    else:
        status = "partial"
    src = conn.price_source
    return {
        "price_status": status,
        "price_per_kwh": conn.pricing_per_kwh,
        "session_fee": conn.session_fee,
        "time_fee_per_min": conn.time_fee_per_min,
        "idle_fee_per_min": conn.idle_fee_per_min,
        "taxes_included": conn.taxes_included,
        "price_source": src,
        "price_source_label": SOURCE_LABELS.get(src) if src else None,
        "price_updated_at": conn.price_updated_at,
        "price_verified": bool(conn.price_verified and src == "operator"),
    }


def station_price_summary(station) -> Dict:
    prices = [c.pricing_per_kwh for p in station.points for c in p.connectors if c.pricing_per_kwh is not None]
    if prices:
        label = f"From ₹{min(prices):.2f}/kWh"
        status = "known"
    elif station.usage_cost_text:
        label = "Price unavailable (provider note only)"
        status = "text_only"
    else:
        label = "Price unavailable"
        status = "unavailable"
    return {"price_summary": label, "price_status": status, "min_price_per_kwh": min(prices) if prices else None}


def compute_home_booking_price(listing, estimated_kwh: float, hours: float) -> Dict:
    """Single source of truth for home-charger pricing (used by estimator, comparison and booking creation)."""
    total_hours = max(hours, listing.minimum_booking_hours)
    charging = _r(estimated_kwh * listing.price_per_kwh)
    session = _r(listing.session_fee)
    parking = _r(total_hours * listing.parking_fee_per_hour)
    subtotal = _r(charging + session + parking)
    platform_fee = _r(subtotal * (settings.PLATFORM_FEE_PERCENTAGE / 100.0))
    return {"total_hours": round(total_hours, 2), "charging_cost": charging, "session_cost": session,
            "parking_cost": parking, "subtotal": subtotal, "platform_fee": platform_fee,
            "total": _r(subtotal + platform_fee), "host_earnings": subtotal}


def energy_from_vehicle(vehicle, from_soc: float, to_soc: float) -> Optional[float]:
    if vehicle is None or vehicle.battery_capacity_kwh is None or to_soc <= from_soc:
        return None
    return _r(vehicle.battery_capacity_kwh * (to_soc - from_soc) / 100.0)


def estimate_duration_minutes(energy_kwh: float, power_kw: Optional[float]) -> Optional[float]:
    if not power_kw or power_kw <= 0:
        return None
    return _r(energy_kwh / power_kw * 60.0)


def estimate_station_cost(station, connector, energy_kwh: float, *, duration_minutes: Optional[float] = None,
                          idle_minutes: float = 0.0, parking_hours: Optional[float] = None,
                          effective_power_kw: Optional[float] = None) -> Dict:
    lines: List[Dict] = []
    excluded: List[str] = []
    assumptions: List[str] = [
        f"Energy requested: {energy_kwh:g} kWh (kWh is energy; kW is charging power).",
        "This is an estimate, not an operator invoice. The operator's final charge governs.",
    ]

    def add(label, amount, basis):
        lines.append({"label": label, "amount": amount, "basis": basis, "known": amount is not None})

    if connector.pricing_per_kwh is not None:
        add("Energy", _r(energy_kwh * connector.pricing_per_kwh), f"{energy_kwh:g} kWh × ₹{connector.pricing_per_kwh:.2f}/kWh")
    else:
        add("Energy", None, "Energy price unavailable")
        excluded.append("Energy charge (price unavailable)")

    if connector.session_fee is not None:
        add("Session / connection fee", _r(connector.session_fee), "Flat fee per session")
    else:
        add("Session / connection fee", None, "Unknown")
        excluded.append("Session or connection fee (unknown)")

    power = effective_power_kw or connector.power_kw
    dur = duration_minutes
    if dur is None and power:
        dur = estimate_duration_minutes(energy_kwh, power)
        if dur is not None and (connector.time_fee_per_min is not None or station.parking_fee is not None):
            assumptions.append(f"Charging time assumed at {dur:g} min, i.e. constant {power:g} kW. Real sessions slow down as the battery fills.")
    if connector.time_fee_per_min is not None:
        if dur is not None:
            add("Time-based fee", _r(dur * connector.time_fee_per_min), f"{dur:g} min × ₹{connector.time_fee_per_min:.2f}/min")
        else:
            add("Time-based fee", None, "Duration unknown")
            excluded.append("Time-based fee (duration unknown)")
    else:
        add("Time-based fee", None, "Unknown")
        excluded.append("Time-based fee (unknown)")

    if station.parking_fee is not None:
        hrs = parking_hours if parking_hours is not None else ((dur or 0) / 60.0)
        add("Parking", _r(hrs * station.parking_fee), f"{hrs:.2f} h × ₹{station.parking_fee:.2f}/h")
    else:
        add("Parking", None, "Unknown")
        excluded.append("Parking charges (unknown)")

    if connector.idle_fee_per_min is not None:
        if idle_minutes > 0:
            add("Idle fee", _r(idle_minutes * connector.idle_fee_per_min), f"{idle_minutes:g} min × ₹{connector.idle_fee_per_min:.2f}/min")
        else:
            add("Idle fee", 0.0, f"Not charged unless you stay plugged in after charging (₹{connector.idle_fee_per_min:.2f}/min)")
            assumptions.append("No idle time assumed.")
    else:
        excluded.append("Idle fees (unknown)")

    if connector.taxes_included is True:
        assumptions.append("The listed prices are stated to include taxes.")
    elif connector.taxes_included is False:
        excluded.append("Taxes (listed prices exclude them)")
    else:
        excluded.append("Taxes (not stated whether included)")

    known_total = _r(sum(l["amount"] for l in lines if l["amount"] is not None))
    core_known = (connector.pricing_per_kwh is not None and connector.session_fee is not None
                  and connector.time_fee_per_min is not None and station.parking_fee is not None)
    return {
        "kind": "estimate", "currency": CURRENCY, "energy_kwh": energy_kwh, "lines": lines,
        "total_known": known_total,
        "is_complete": bool(core_known),
        "price_confidence": ("complete" if core_known else ("partial" if connector.pricing_per_kwh is not None else "unknown")),
        "excluded": excluded, "assumptions": assumptions,
        "price_source": connector.price_source, "price_source_label": SOURCE_LABELS.get(connector.price_source),
        "price_updated_at": connector.price_updated_at,
        "price_verified": bool(connector.price_verified and connector.price_source == "operator"),
    }


def estimate_home_cost(listing, energy_kwh: float, hours: float) -> Dict:
    p = compute_home_booking_price(listing, energy_kwh, hours)
    lines = [
        {"label": "Energy", "amount": p["charging_cost"], "basis": f"{energy_kwh:g} kWh × ₹{listing.price_per_kwh:.2f}/kWh", "known": True},
        {"label": "Host session fee", "amount": p["session_cost"], "basis": "Flat fee per booking", "known": True},
        {"label": "Parking", "amount": p["parking_cost"], "basis": f"{p['total_hours']:g} h × ₹{listing.parking_fee_per_hour:.2f}/h", "known": True},
        {"label": f"ChargeCircle service fee ({settings.PLATFORM_FEE_PERCENTAGE:g}%)", "amount": p["platform_fee"], "basis": "On the subtotal", "known": True},
    ]
    return {
        "kind": "estimate", "currency": CURRENCY, "energy_kwh": energy_kwh, "lines": lines,
        "total_known": p["total"], "is_complete": True, "price_confidence": "confirmed",
        "excluded": [],
        "assumptions": [
            f"Energy requested: {energy_kwh:g} kWh. The booking is priced on this estimate; the final charge is recalculated from the energy actually recorded for the session.",
            f"Billed time is at least the host's minimum of {listing.minimum_booking_hours:g} h.",
        ],
        "price_source": "operator", "price_source_label": "Host-set price (agreed at booking)",
        "price_updated_at": getattr(listing, "updated_at", None), "price_verified": False,
    }
