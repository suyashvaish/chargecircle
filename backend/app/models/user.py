from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import ConnectorType, UserRoleType


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone_number = Column(String(30), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    profile = relationship("UserProfile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    vehicles = relationship("Vehicle", back_populates="user", cascade="all, delete-orphan")
    home_listings = relationship("HomeChargerListing", back_populates="host")
    bookings = relationship("Booking", foreign_keys="Booking.driver_id", back_populates="driver")
    payments = relationship("Payment", back_populates="user")
    reports = relationship("ChargerReport", back_populates="user")
    reviews = relationship("Review", back_populates="driver")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")

    def has_role(self, role_name: str) -> bool:
        return any(r.role_name == role_name for r in self.roles)


class UserRole(Base):
    __tablename__ = "user_roles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role_name = Column(String(50), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="roles")

    __table_args__ = (
        UniqueConstraint("user_id", "role_name", name="uq_user_role"),
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    bio = Column(Text, nullable=True)
    preferred_city = Column(String(100), default="Bengaluru", nullable=True)
    preferred_language = Column(String(20), default="en", nullable=True)
    emergency_contact = Column(String(50), nullable=True)
    address_line = Column(String(255), nullable=True)
    tax_id_masked = Column(String(50), nullable=True)

    user = relationship("User", back_populates="profile")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    make = Column(String(100), nullable=False)  # e.g., Tata, MG, Mahindra, Hyundai, Ather, Ola
    model = Column(String(100), nullable=False)  # e.g., Nexon EV, ZS EV, XUV400, Ioniq 5, 450X, S1 Pro
    year = Column(Integer, nullable=False, default=2024)
    trim = Column(String(100), nullable=True)
    # NULL means "unknown" - specifications are never assumed.
    battery_capacity_kwh = Column(Float, nullable=True)
    max_ac_charging_kw = Column(Float, nullable=True)
    max_dc_charging_kw = Column(Float, nullable=True)
    charging_preferences = Column(Text, nullable=True)
    license_plate = Column(String(30), nullable=True)
    is_primary = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="vehicles")
    connectors = relationship("VehicleConnector", back_populates="vehicle", cascade="all, delete-orphan")


class VehicleConnector(Base):
    __tablename__ = "vehicle_connectors"

    id = Column(Integer, primary_key=True, index=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, index=True)
    connector_type = Column(String(50), nullable=False)

    vehicle = relationship("Vehicle", back_populates="connectors")

    __table_args__ = (
        UniqueConstraint("vehicle_id", "connector_type", name="uq_vehicle_connector"),
    )


class AuthToken(Base):
    """One-time tokens for email verification and password reset. Only the SHA-256 hash is stored."""
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose = Column(String(30), nullable=False, index=True)  # email_verify | password_reset
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
