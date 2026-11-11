from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ChargerConnectorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    connector_type: str
    current_type: str
    power_kw: Optional[float] = None
    # All price fields are None when unknown ("Price unavailable"); nothing is defaulted.
    pricing_per_kwh: Optional[float] = None
    session_fee: Optional[float] = None
    time_fee_per_min: Optional[float] = None
    idle_fee_per_min: Optional[float] = None
    taxes_included: Optional[bool] = None
    price_source: Optional[str] = None
    price_source_label: Optional[str] = None
    price_updated_at: Optional[datetime] = None
    price_verified: bool = False
    price_status: str = "unavailable"


class ChargingPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    point_identifier: str
    status: str
    last_status_update: datetime
    connectors: List[ChargerConnectorOut] = []


class StatusSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    operational_status: str
    confidence_score: float
    evidence_summary: str
    total_reports_evaluated: int
    last_reported_at: Optional[datetime] = None
    calculated_at: datetime


class CompatibilityOut(BaseModel):
    status: str  # compatible | unconfirmed | incompatible
    reasons: List[str] = []
    effective_power_kw: Optional[float] = None
    power_note: Optional[str] = None


class PublicStationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: Optional[str] = None
    name: str
    operator_name: str
    address: str
    locality: Optional[str] = None
    city: str
    state: str
    pin_code: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None  # straight-line distance, NOT road distance
    access_type: str
    operating_hours: str
    is_open_24_7: bool
    parking_fee: Optional[float] = None  # INR/hour, None = unknown
    is_sample: bool
    data_source: str
    data_origin: str = "manual"  # provider | sample | manual
    source_url: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    provider_last_verified_at: Optional[datetime] = None
    provider_status: Optional[str] = None
    usage_cost_text: Optional[str] = None
    membership_required: Optional[bool] = None
    pay_at_location: Optional[bool] = None
    price_summary: str = "Price unavailable"
    price_status: str = "unavailable"
    min_price_per_kwh: Optional[float] = None
    connectors_summary: List[str] = []
    max_power_kw: Optional[float] = None
    current_status: Optional[str] = "Unknown"
    confidence_score: Optional[float] = 0.5
    last_verified_at: Optional[datetime] = None
    compatibility: Optional[CompatibilityOut] = None
    created_at: datetime


class StationDetailOut(PublicStationOut):
    general_notes: Optional[str] = None
    points: List[ChargingPointOut] = []
    status_snapshot: Optional[StatusSnapshotOut] = None
    attribution: Optional[str] = None


class ProviderMeta(BaseModel):
    provider: str = "Open Charge Map"
    status: str
    message: str = ""
    fetched_at: Optional[datetime] = None
    radius_km_used: Optional[float] = None
    radius_limited: bool = False
    count: int = 0


class StationSearchOut(BaseModel):
    stations: List[PublicStationOut]
    provider: ProviderMeta


class StationFilterParams(BaseModel):
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_km: float = Field(default=25.0, ge=1.0, le=200.0)
    city: Optional[str] = None
    query: Optional[str] = None
    connector_type: Optional[str] = None
    current_type: Optional[str] = None  # AC or DC
    min_power_kw: Optional[float] = None
    open_now: Optional[bool] = None
    max_price_per_kwh: Optional[float] = None
    operational_only: Optional[bool] = None
    vehicle_id: Optional[int] = None
    compatible_only: Optional[bool] = None
