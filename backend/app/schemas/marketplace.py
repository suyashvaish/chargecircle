from datetime import datetime, time
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.services.text import sanitize_text
from app.schemas.station import CompatibilityOut


class ListingPhotoOut(BaseModel):
    id: int
    photo_url: str
    caption: Optional[str] = None
    is_cover: bool

    class Config:
        from_attributes = True


class AvailabilityScheduleCreate(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6, description="0=Mon, 6=Sun")
    start_time: str = Field(..., example="08:00:00")
    end_time: str = Field(..., example="22:00:00")
    is_active: bool = True


class AvailabilityScheduleOut(BaseModel):
    id: int
    day_of_week: int
    start_time: time
    end_time: time
    is_active: bool

    class Config:
        from_attributes = True


class HomeListingCreate(BaseModel):
    title: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=10, max_length=4000)
    address_street: str = Field(..., max_length=255)
    locality: str = Field(..., max_length=150)
    city: str = Field(..., max_length=100)
    state: str = Field(default="Karnataka", max_length=100)
    pin_code: str = Field(..., max_length=20)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    # Deprecated: exact addresses and coordinates are ALWAYS withheld until a booking reaches the eligible state.
    is_address_hidden_until_booked: bool = True

    @field_validator("title", "description", "address_street", "locality", "city", "state", "parking_access_instructions",
                     check_fields=False, mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 4000) if isinstance(v, str) else v
    
    property_type: str = "residential_house"
    equipment_type: str = "dedicated_wallbox"
    connector_type: str = "Type 2"
    current_type: str = "AC"
    power_kw: float = Field(default=7.4, gt=0, le=350)
    is_cable_attached: bool = True
    has_dedicated_meter: bool = True
    has_cctv_surveillance: bool = False
    has_covered_parking: bool = True
    
    safety_confirmed: bool = True
    earthing_verified: bool = True
    rcbo_installed: bool = True
    
    price_per_kwh: float = Field(default=12.0, gt=0, le=500)
    session_fee: float = Field(default=20.0, ge=0, le=5000)
    parking_fee_per_hour: float = Field(default=10.0, ge=0, le=5000)
    minimum_booking_hours: float = Field(default=1.0, ge=0.5)
    
    instant_booking: bool = False
    parking_access_instructions: Optional[str] = None
    cancellation_policy: str = "Free cancellation up to 2 hours before booking"


class HomeListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price_per_kwh: Optional[float] = None
    session_fee: Optional[float] = None
    parking_fee_per_hour: Optional[float] = None
    instant_booking: Optional[bool] = None
    parking_access_instructions: Optional[str] = None
    is_address_hidden_until_booked: Optional[bool] = None


class HostSummaryOut(BaseModel):
    id: int
    full_name: str
    is_verified: bool
    avatar_url: Optional[str] = None
    rating: float = 5.0
    review_count: int = 0

    class Config:
        from_attributes = True


class HomeListingOut(BaseModel):
    id: int
    host_id: int
    title: str
    description: str
    locality: str
    city: str
    state: str
    pin_code: str
    latitude: float
    longitude: float
    distance_km: Optional[float] = None
    
    property_type: str
    equipment_type: str
    connector_type: str
    current_type: str
    power_kw: float
    is_cable_attached: bool
    has_covered_parking: bool
    
    price_per_kwh: float
    session_fee: float
    parking_fee_per_hour: float
    minimum_booking_hours: float
    
    status: str
    instant_booking: bool
    safety_confirmed: bool
    earthing_verified: bool
    
    # Public pin is APPROXIMATE (offset) unless the viewer is authorized; see location_is_approximate.
    location_is_approximate: bool = True
    # Publicized or masked address based on booking authorization
    display_address: str
    cover_photo_url: Optional[str] = None
    average_rating: Optional[float] = None  # None when there are no reviews yet
    total_reviews: int = 0
    created_at: datetime
    compatibility: Optional[CompatibilityOut] = None

    class Config:
        from_attributes = True


class HomeListingDetailOut(HomeListingOut):
    address_street: Optional[str] = None  # Full address only returned if authorized driver or host
    exact_latitude: Optional[float] = None   # only for the host, an admin, or a driver with an eligible booking
    exact_longitude: Optional[float] = None
    parking_access_instructions: Optional[str] = None
    cancellation_policy: str
    photos: List[ListingPhotoOut] = []
    schedules: List[AvailabilityScheduleOut] = []
    host: Optional[HostSummaryOut] = None


class BookingCreate(BaseModel):
    listing_id: int
    vehicle_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    estimated_kwh: float = Field(default=15.0, gt=0, le=500)


class BookingOut(BaseModel):
    id: int
    booking_reference: str
    driver_id: int
    listing_id: int
    vehicle_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    total_hours: float
    estimated_kwh: float
    rate_per_kwh: float
    session_fee: float
    parking_fee: float
    subtotal_amount: float
    platform_fee: float
    total_amount: float
    host_earnings_amount: float
    status: str
    cancellation_reason: Optional[str] = None
    arrival_instructions_revealed: bool
    full_address: Optional[str] = None
    parking_access_instructions: Optional[str] = None
    exact_latitude: Optional[float] = None
    exact_longitude: Optional[float] = None
    approx_latitude: Optional[float] = None
    approx_longitude: Optional[float] = None
    listing_title: Optional[str] = None
    payment_hold_expires_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    payment_status: Optional[str] = None
    created_at: datetime
    listing: Optional[HomeListingOut] = None

    class Config:
        from_attributes = True


class ChargingSessionOut(BaseModel):
    id: int
    booking_id: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    energy_delivered_kwh: Optional[float] = None
    peak_power_kw: float
    meter_reading_start: Optional[float] = None
    meter_reading_end: Optional[float] = None
    status: str
    verification_source: str
    energy_is_measured: bool = False
    final_amount: Optional[float] = None
    pricing_snapshot: Optional[dict] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChargingSessionStart(BaseModel):
    meter_reading_start: Optional[float] = Field(default=None, ge=0)


class ChargingSessionComplete(BaseModel):
    energy_delivered_kwh: float = Field(..., gt=0, le=1000)
    meter_reading_end: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=1000)


class CancelRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)
