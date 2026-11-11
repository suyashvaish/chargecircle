from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class VehicleConnectorBase(BaseModel):
    connector_type: str


class VehicleConnectorOut(VehicleConnectorBase):
    id: int

    class Config:
        from_attributes = True


class VehicleCreate(BaseModel):
    make: str = Field(..., example="Tata")
    model: str = Field(..., example="Nexon EV Max")
    year: int = Field(default=2024, ge=2015, le=2027)
    trim: Optional[str] = "Empowered+"
    # Leave a specification empty when it is not known; nothing is assumed on your behalf.
    battery_capacity_kwh: Optional[float] = Field(default=None, gt=0, le=400)
    max_ac_charging_kw: Optional[float] = Field(default=None, gt=0, le=50)
    max_dc_charging_kw: Optional[float] = Field(default=None, gt=0, le=600)
    license_plate: Optional[str] = Field(default=None, max_length=20)
    connector_types: List[str] = Field(default_factory=list, max_length=6)
    charging_preferences: Optional[str] = Field(default=None, max_length=500)
    is_primary: bool = True


class VehicleOut(BaseModel):
    id: int
    user_id: int
    make: str
    model: str
    year: int
    trim: Optional[str] = None
    battery_capacity_kwh: Optional[float] = None
    max_ac_charging_kw: Optional[float] = None
    max_dc_charging_kw: Optional[float] = None
    license_plate: Optional[str] = None
    charging_preferences: Optional[str] = None
    is_primary: bool
    connectors: List[VehicleConnectorOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    bio: Optional[str] = None
    preferred_city: Optional[str] = None
    emergency_contact: Optional[str] = None
    address_line: Optional[str] = None
