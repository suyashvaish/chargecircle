from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User, UserProfile, Vehicle, VehicleConnector
from app.schemas.auth import UserOut
from app.schemas.user import ProfileUpdate, VehicleCreate, VehicleOut
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/users", tags=["User Profiles & Vehicles"])


@router.put("/profile", response_model=UserOut)
def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Updates user bio, name, and contact details."""
    if data.full_name:
        current_user.full_name = data.full_name.strip()
    if data.phone_number:
        current_user.phone_number = data.phone_number.strip()
    
    if not current_user.profile:
        current_user.profile = UserProfile(user_id=current_user.id)

    if data.bio is not None:
        current_user.profile.bio = data.bio
    if data.preferred_city is not None:
        current_user.profile.preferred_city = data.preferred_city
    if data.emergency_contact is not None:
        current_user.profile.emergency_contact = data.emergency_contact
    if data.address_line is not None:
        current_user.profile.address_line = data.address_line

    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/vehicles", response_model=List[VehicleOut])
def get_my_vehicles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists configured electric vehicles for the current user."""
    return db.query(Vehicle).filter(Vehicle.user_id == current_user.id).all()


@router.post("/vehicles", response_model=VehicleOut, status_code=status.HTTP_201_CREATED)
def add_vehicle(
    data: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Adds a new EV and its supported connector standards."""
    vehicle = Vehicle(
        user_id=current_user.id,
        make=data.make.strip(),
        model=data.model.strip(),
        year=data.year,
        trim=data.trim,
        battery_capacity_kwh=data.battery_capacity_kwh,
        max_ac_charging_kw=data.max_ac_charging_kw,
        max_dc_charging_kw=data.max_dc_charging_kw,
        charging_preferences=data.charging_preferences,
        license_plate=data.license_plate,
        is_primary=data.is_primary
    )
    db.add(vehicle)
    db.flush()

    for conn_type in dict.fromkeys(c.strip() for c in data.connector_types if c.strip()):
        db.add(VehicleConnector(vehicle_id=vehicle.id, connector_type=conn_type))

    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.put("/vehicles/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, data: VehicleCreate, current_user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    """Replaces a saved vehicle's details (including connector list)."""
    v = db.query(Vehicle).filter(Vehicle.id == vehicle_id, Vehicle.user_id == current_user.id).first()
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    for f in ("make", "model", "year", "trim", "battery_capacity_kwh", "max_ac_charging_kw", "max_dc_charging_kw",
              "license_plate", "charging_preferences", "is_primary"):
        setattr(v, f, getattr(data, f))
    v.make, v.model = data.make.strip(), data.model.strip()
    for c in list(v.connectors):
        db.delete(c)
    db.flush()
    for conn_type in dict.fromkeys(c.strip() for c in data.connector_types if c.strip()):
        db.add(VehicleConnector(vehicle_id=v.id, connector_type=conn_type))
    db.commit()
    db.refresh(v)
    return v


@router.delete("/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vehicle(
    vehicle_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deletes a configured vehicle."""
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.user_id == current_user.id
    ).first()
    if not vehicle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
    db.delete(vehicle)
    db.commit()
    return None
