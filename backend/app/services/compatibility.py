"""Vehicle <-> charger compatibility based only on specifications the user has actually saved."""
import re
from typing import Dict, Iterable, List, Optional

_ALIASES = {
    "ccs2": "CCS2", "ccstype2": "CCS2", "ccscombotype2": "CCS2", "iec621963configurationff": "CCS2",
    "iec621962type2": "Type 2", "ccscombo2": "CCS2", "type2combo": "CCS2", "iec62196type2combo": "CCS2",
    "type2": "Type 2", "mennekes": "Type 2", "iec62196type2": "Type 2", "type2socket": "Type 2",
    "type2tethered": "Type 2", "type2socketonly": "Type 2",
    "gbt": "GB/T", "gb/t": "GB/T", "chademo": "CHAdeMO",
    "bharatac001": "Bharat AC-001", "bharatdc001": "Bharat DC-001",
    "16a3pinsocket": "16A 3-Pin Socket", "3pinsocket": "16A 3-Pin Socket",
    "type1": "Type 1", "j1772": "Type 1", "type1j1772": "Type 1",
}


def normalize_connector(name: Optional[str]) -> Optional[str]:
    """Maps a free-text connector name to a canonical type, or None if it is not recognised."""
    if not name:
        return None
    key = re.sub(r"[^a-z0-9/]", "", name.lower())
    key2 = key.replace("/", "")
    return _ALIASES.get(key) or _ALIASES.get(key2)


def vehicle_connector_set(vehicle) -> set:
    return {normalize_connector(c.connector_type) or c.connector_type for c in (vehicle.connectors or [])}


def evaluate_connector(vehicle, connector_type: str, current_type: str, power_kw: Optional[float],
                       cable_attached: Optional[bool] = None) -> Dict:
    reasons: List[str] = []
    norm = normalize_connector(connector_type)
    supported = vehicle_connector_set(vehicle)
    status = "compatible"

    if not supported:
        status = "unconfirmed"
        reasons.append("Your vehicle profile has no connector types saved, so connector compatibility cannot be confirmed.")
    elif norm is None:
        status = "unconfirmed"
        reasons.append(f"The connector '{connector_type}' is not a recognised standard, so compatibility cannot be confirmed.")
    elif norm not in supported:
        if norm == "Type 2" and "CCS2" in supported and (current_type or "").upper() == "AC":
            status = "unconfirmed"
            reasons.append("A Type 2 AC plug normally fits a CCS2 inlet, but your profile does not list Type 2 AC charging. Add it to confirm.")
        else:
            status = "incompatible"
            reasons.append(f"This charger offers {norm}; your vehicle profile lists {', '.join(sorted(supported))}.")
    else:
        reasons.append(f"{norm} is listed as supported by your vehicle.")

    limit = vehicle.max_dc_charging_kw if (current_type or "").upper() == "DC" else vehicle.max_ac_charging_kw
    effective = None
    power_note = None
    if power_kw is not None:
        if limit is None:
            power_note = "Your vehicle's maximum charging power for this current type is unknown, so the achievable rate cannot be confirmed."
        elif limit < power_kw:
            effective = limit
            power_note = f"Limited to {limit:g} kW by your vehicle (charger offers up to {power_kw:g} kW)."
        else:
            effective = power_kw
            power_note = f"Charger limit of {power_kw:g} kW applies (your vehicle accepts up to {limit:g} kW)."
    if cable_attached is False:
        reasons.append("No cable is attached at this charger; you must bring a compatible cable.")
    return {"status": status, "reasons": reasons, "effective_power_kw": effective, "power_note": power_note,
            "connector_type": connector_type}


def evaluate_charger(vehicle, connectors: Iterable) -> Dict:
    """connectors: objects with connector_type, current_type, power_kw (+ optional cable_attached)."""
    results = [evaluate_connector(vehicle, c.connector_type, c.current_type, c.power_kw,
                                  getattr(c, "cable_attached", None)) for c in connectors]
    if not results:
        return {"status": "unconfirmed", "reasons": ["No connector information is available for this charger."],
                "effective_power_kw": None, "power_note": None, "connectors": []}
    order = {"compatible": 0, "unconfirmed": 1, "incompatible": 2}
    best = sorted(results, key=lambda r: (order[r["status"]], -(r["effective_power_kw"] or 0)))[0]
    return {**best, "connectors": results}
