from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import BookingStatus, CurrentType, EquipmentType, ListingStatus, PropertyType


def utc_now():
    return datetime.now(timezone.utc)


class HomeChargerListing(Base):
    __tablename__ = "home_charger_listings"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    # Location
    address_street = Column(String(255), nullable=False)
    locality = Column(String(150), nullable=False, index=True)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False, default="Karnataka")
    pin_code = Column(String(20), nullable=False, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    is_address_hidden_until_booked = Column(Boolean, default=True, nullable=False)
    
    # Property & Equipment Specs
    property_type = Column(String(50), nullable=False, default=PropertyType.RESIDENTIAL_HOUSE.value)
    equipment_type = Column(String(50), nullable=False, default=EquipmentType.DEDICATED_WALLBOX.value)
    connector_type = Column(String(50), nullable=False)  # Type 2, CCS2, 16A 3-Pin Socket
    current_type = Column(String(10), nullable=False, default=CurrentType.AC.value)
    power_kw = Column(Float, nullable=False, default=7.4)  # e.g., 7.4 kW or 3.3 kW
    is_cable_attached = Column(Boolean, default=True, nullable=False)
    has_dedicated_meter = Column(Boolean, default=True, nullable=False)
    has_cctv_surveillance = Column(Boolean, default=False, nullable=False)
    has_covered_parking = Column(Boolean, default=True, nullable=False)
    
    # Safety confirmation
    safety_confirmed = Column(Boolean, default=False, nullable=False)
    earthing_verified = Column(Boolean, default=False, nullable=False)
    rcbo_installed = Column(Boolean, default=False, nullable=False)
    
    # Pricing Breakdown (INR)
    price_per_kwh = Column(Float, nullable=False, default=12.0)
    session_fee = Column(Float, nullable=False, default=20.0)
    parking_fee_per_hour = Column(Float, nullable=False, default=10.0)
    minimum_booking_hours = Column(Float, nullable=False, default=1.0)
    
    # Status and Settings
    status = Column(String(50), nullable=False, default=ListingStatus.PENDING_VERIFICATION.value)
    instant_booking = Column(Boolean, default=False, nullable=False)
    parking_access_instructions = Column(Text, nullable=True)
    cancellation_policy = Column(String(100), default="Free cancellation up to 2 hours before booking", nullable=False)
    
    @property
    def display_address(self) -> str:
        return f"{self.locality}, {self.city}, {self.pin_code}"

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    host = relationship("User", back_populates="home_listings")
    photos = relationship("ListingPhoto", back_populates="listing", cascade="all, delete-orphan")
    schedules = relationship("AvailabilitySchedule", back_populates="listing", cascade="all, delete-orphan")
    exceptions = relationship("AvailabilityException", back_populates="listing", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="listing")
    verification_records = relationship("HostVerificationRecord", back_populates="listing", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="listing")
    reports = relationship("ChargerReport", back_populates="home_listing", foreign_keys="ChargerReport.home_listing_id")
    status_snapshots = relationship("ChargerStatusSnapshot", back_populates="home_listing", foreign_keys="ChargerStatusSnapshot.home_listing_id")
    favorites = relationship("Favorite", back_populates="home_listing", foreign_keys="Favorite.home_listing_id")


class HostVerificationRecord(Base):
    __tablename__ = "host_verification_records"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=True, index=True)
    document_type = Column(String(100), nullable=False)  # electricity_bill, identity_proof, equipment_photo
    document_masked_id = Column(String(100), nullable=True)
    verification_status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected
    reviewer_notes = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    listing = relationship("HomeChargerListing", back_populates="verification_records")


class ListingPhoto(Base):
    __tablename__ = "listing_photos"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    photo_url = Column(String(500), nullable=False)
    caption = Column(String(200), nullable=True)
    is_cover = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    listing = relationship("HomeChargerListing", back_populates="photos")


class AvailabilitySchedule(Base):
    __tablename__ = "availability_schedules"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    start_time = Column(Time, nullable=False)      # e.g., 08:00:00
    end_time = Column(Time, nullable=False)        # e.g., 22:00:00
    is_active = Column(Boolean, default=True, nullable=False)

    listing = relationship("HomeChargerListing", back_populates="schedules")


class AvailabilityException(Base):
    __tablename__ = "availability_exceptions"

    id = Column(Integer, primary_key=True, index=True)
    listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    exception_date = Column(DateTime(timezone=True), nullable=False)
    is_unavailable = Column(Boolean, default=True, nullable=False)
    reason = Column(String(255), nullable=True)

    listing = relationship("HomeChargerListing", back_populates="exceptions")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_reference = Column(String(64), unique=True, index=True, nullable=False)
    driver_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=False, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    total_hours = Column(Float, nullable=False)
    estimated_kwh = Column(Float, nullable=False, default=15.0)
    
    # Financial breakdown
    rate_per_kwh = Column(Float, nullable=False)
    session_fee = Column(Float, nullable=False, default=0.0)
    parking_fee = Column(Float, nullable=False, default=0.0)
    subtotal_amount = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)  # ChargeCircle service fee
    total_amount = Column(Float, nullable=False)  # Driver pays this
    host_earnings_amount = Column(Float, nullable=False)  # Host receives this
    
    status = Column(String(50), nullable=False, default=BookingStatus.PENDING.value, index=True)
    cancellation_reason = Column(String(255), nullable=True)
    cancelled_by_id = Column(Integer, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    payment_hold_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    arrival_instructions_revealed = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    driver = relationship("User", foreign_keys=[driver_id], back_populates="bookings")
    listing = relationship("HomeChargerListing", back_populates="bookings")
    vehicle = relationship("Vehicle")
    payment = relationship("Payment", uselist=False, back_populates="booking")
    session = relationship("ChargingSession", uselist=False, back_populates="booking")
    disputes = relationship("Dispute", back_populates="booking")
    review = relationship("Review", uselist=False, back_populates="booking")


class ChargingSession(Base):
    __tablename__ = "charging_sessions"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    energy_delivered_kwh = Column(Float, nullable=False, default=0.0)
    peak_power_kw = Column(Float, nullable=False, default=0.0)
    meter_reading_start = Column(Float, nullable=True)
    meter_reading_end = Column(Float, nullable=True)
    
    # scheduled -> started -> completed | cancelled | disputed
    status = Column(String(50), nullable=False, default="scheduled")
    # How the energy figure was obtained: none | manual_host | manual_driver | meter_photo | telemetry
    # Only "telemetry" comes from a trusted measurement integration; the others are manual entries.
    verification_source = Column(String(100), nullable=False, default="none")
    energy_is_measured = Column(Boolean, nullable=False, default=False)
    energy_entered_by_id = Column(Integer, nullable=True)
    energy_entered_at = Column(DateTime(timezone=True), nullable=True)
    final_amount = Column(Float, nullable=True)         # recalculated charge from final energy
    pricing_snapshot_json = Column(Text, nullable=True)  # price/energy/fee calculation record
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    booking = relationship("Booking", back_populates="session")
