from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import CurrentType, PointStatus


def utc_now():
    return datetime.now(timezone.utc)


class ChargingStation(Base):
    __tablename__ = "charging_stations"
    __table_args__ = (UniqueConstraint("external_provider", "external_id", name="uq_station_provider_external"),)

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), index=True, nullable=True)  # provider identifier, e.g. OCM POI id
    name = Column(String(255), nullable=False, index=True)
    operator_name = Column(String(150), nullable=False, default="Independent Operator")
    address = Column(String(500), nullable=False)
    locality = Column(String(150), nullable=True)
    city = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False, default="Karnataka")
    pin_code = Column(String(20), nullable=False, index=True)
    latitude = Column(Float, nullable=False, index=True)
    longitude = Column(Float, nullable=False, index=True)
    
    access_type = Column(String(50), nullable=False, default="public")  # public, semi-public, restricted
    operating_hours = Column(String(200), nullable=False, default="24/7 Open")
    is_open_24_7 = Column(Boolean, default=True, nullable=False)
    parking_fee = Column(Float, nullable=True)  # INR per hour; NULL means unknown (never assume 0)
    general_notes = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_sample = Column(Boolean, default=False, nullable=False)  # Explicit flag per master prompt
    data_source = Column(String(100), nullable=False, default="Manually entered")
    # Provenance: manual | sample | open_charge_map
    source = Column(String(30), nullable=False, default="manual", index=True)
    external_provider = Column(String(30), nullable=True)
    source_url = Column(String(500), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    provider_last_verified_at = Column(DateTime(timezone=True), nullable=True)
    provider_status = Column(String(100), nullable=True)  # provider's own (non-live) status label
    usage_cost_text = Column(String(500), nullable=True)  # raw provider/operator pricing text, shown verbatim
    membership_required = Column(Boolean, nullable=True)
    pay_at_location = Column(Boolean, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # Relationships
    points = relationship("ChargingPoint", back_populates="station", cascade="all, delete-orphan")
    reports = relationship("ChargerReport", back_populates="station", foreign_keys="ChargerReport.station_id")
    status_snapshots = relationship("ChargerStatusSnapshot", back_populates="station", foreign_keys="ChargerStatusSnapshot.station_id")
    favorites = relationship("Favorite", back_populates="station", foreign_keys="Favorite.station_id")


class ChargingPoint(Base):
    __tablename__ = "charging_points"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("charging_stations.id", ondelete="CASCADE"), nullable=False, index=True)
    point_identifier = Column(String(50), nullable=False, default="Point 1")  # e.g., "Bay A", "Gun 1"
    status = Column(String(50), nullable=False, default=PointStatus.AVAILABLE.value)
    last_status_update = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    station = relationship("ChargingStation", back_populates="points")
    connectors = relationship("ChargerConnector", back_populates="point", cascade="all, delete-orphan")


class ChargerConnector(Base):
    __tablename__ = "charger_connectors"

    id = Column(Integer, primary_key=True, index=True)
    point_id = Column(Integer, ForeignKey("charging_points.id", ondelete="CASCADE"), nullable=False, index=True)
    connector_type = Column(String(50), nullable=False)  # CCS2, Type 2, GB/T, CHAdeMO
    current_type = Column(String(10), nullable=False, default=CurrentType.DC.value)  # AC or DC
    power_kw = Column(Float, nullable=True)  # kW (power, not energy); NULL when the provider does not say
    # All price fields are INR and NULL when unknown. Unknown is never replaced by an assumed value.
    pricing_per_kwh = Column(Float, nullable=True)   # INR per kWh (energy)
    session_fee = Column(Float, nullable=True)       # one-off connection/session fee
    time_fee_per_min = Column(Float, nullable=True)  # time-based charging fee
    idle_fee_per_min = Column(Float, nullable=True)  # fee after charging completes
    taxes_included = Column(Boolean, nullable=True)  # NULL = unknown
    price_source = Column(String(30), nullable=True)  # operator | provider | user_reported | sample
    price_updated_at = Column(DateTime(timezone=True), nullable=True)
    price_verified = Column(Boolean, nullable=False, default=False)  # only set by an admin/operator action

    point = relationship("ChargingPoint", back_populates="connectors")
