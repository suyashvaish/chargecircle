from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.marketplace import HomeChargerListing
from app.models.station import ChargerConnector, ChargingStation
from app.models.user import User, Vehicle
from app.services import compatibility as compat
from app.services.auth_service import get_optional_user
from app.services.pricing import energy_from_vehicle, estimate_home_cost, estimate_station_cost

router = APIRouter(prefix="/pricing", tags=["Price Transparency & Cost Estimator"])


class EstimateRequest(BaseModel):
    target_type: str = Field(..., pattern="^(station|listing)$")
    target_id: int
    connector_id: Optional[int] = None
    energy_kwh: Optional[float] = Field(default=None, gt=0, le=500)   # kWh = energy
    vehicle_id: Optional[int] = None
    from_soc_percent: Optional[float] = Field(default=None, ge=0, le=100)
    to_soc_percent: Optional[float] = Field(default=None, ge=0, le=100)
    duration_minutes: Optional[float] = Field(default=None, gt=0, le=1440)
    idle_minutes: float = Field(default=0.0, ge=0, le=1440)
    parking_hours: Optional[float] = Field(default=None, ge=0, le=24)
    hours: Optional[float] = Field(default=None, gt=0, le=24)  # home chargers: booked hours

    @model_validator(mode="after")
    def _need_energy(self):
        if self.energy_kwh is None and not (self.vehicle_id and self.from_soc_percent is not None and self.to_soc_percent is not None):
            raise ValueError("Provide energy_kwh, or a vehicle with from/to state of charge")
        return self


def resolve_energy(db: Session, user: Optional[User], req: EstimateRequest):
    vehicle = None
    if req.vehicle_id is not None:
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to use a saved vehicle")
        vehicle = db.query(Vehicle).filter(Vehicle.id == req.vehicle_id, Vehicle.user_id == user.id).first()
        if not vehicle:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Vehicle not found")
    energy, note = req.energy_kwh, None
    if energy is None:
        energy = energy_from_vehicle(vehicle, req.from_soc_percent, req.to_soc_percent)
        if energy is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail="Cannot derive energy: the vehicle's battery capacity is unknown or the state-of-charge range is empty. Enter kWh directly.")
        note = (f"Energy derived from {vehicle.battery_capacity_kwh:g} kWh battery × "
                f"{req.from_soc_percent:g}%→{req.to_soc_percent:g}%. Charging losses are not modelled.")
    return vehicle, energy, note


def pick_connector(station: ChargingStation, vehicle, connector_id: Optional[int]) -> Optional[ChargerConnector]:
    conns = [c for p in station.points for c in p.connectors]
    if connector_id is not None:
        return next((c for c in conns if c.id == connector_id), None)
    if vehicle is not None:
        ok = [c for c in conns if compat.evaluate_connector(vehicle, c.connector_type, c.current_type, c.power_kw)["status"] != "incompatible"]
        conns = ok or conns
    priced = [c for c in conns if c.pricing_per_kwh is not None]
    return min(priced, key=lambda c: c.pricing_per_kwh) if priced else (conns[0] if conns else None)


@router.post("/estimate")
def estimate(req: EstimateRequest, db: Session = Depends(get_db), user: Optional[User] = Depends(get_optional_user)):
    """Transparent cost estimate with its calculation, assumptions and exclusions. Never an operator invoice."""
    vehicle, energy, note = resolve_energy(db, user, req)
    if req.target_type == "listing":
        listing = db.query(HomeChargerListing).filter(HomeChargerListing.id == req.target_id,
                                                      HomeChargerListing.status == "approved").first()
        if not listing:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Listing not found")
        hours = req.hours or max(listing.minimum_booking_hours, energy / listing.power_kw)
        out = estimate_home_cost(listing, energy, hours)
        if not req.hours:
            out["assumptions"].append(f"Booked time assumed at {hours:.2f} h (energy ÷ {listing.power_kw:g} kW charger power, or the host's minimum).")
    else:
        station = db.query(ChargingStation).filter(ChargingStation.id == req.target_id).first()
        if not station:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Station not found")
        conn = pick_connector(station, vehicle, req.connector_id)
        if conn is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "No matching connector for this station")
        eff = None
        if vehicle is not None:
            eff = compat.evaluate_connector(vehicle, conn.connector_type, conn.current_type, conn.power_kw)["effective_power_kw"]
        out = estimate_station_cost(station, conn, energy, duration_minutes=req.duration_minutes,
                                    idle_minutes=req.idle_minutes, parking_hours=req.parking_hours, effective_power_kw=eff)
        out["connector_id"] = conn.id
        out["connector_label"] = f"{conn.connector_type} ({conn.power_kw:g} kW {conn.current_type})" if conn.power_kw else f"{conn.connector_type} ({conn.current_type})"
        if station.source == "sample" or station.is_sample:
            out["assumptions"].append("This station is part of the sample dataset; its prices are illustrative, not real tariffs.")
    if note:
        out["assumptions"].insert(0, note)
    return out
