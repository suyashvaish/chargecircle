from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import OperationalStatus, ReportCategory


def utc_now():
    return datetime.now(timezone.utc)


class ChargerReport(Base):
    __tablename__ = "charger_reports"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("charging_stations.id", ondelete="CASCADE"), nullable=True, index=True)
    home_listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id = Column(Integer, ForeignKey("charging_sessions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    category = Column(String(50), nullable=False, default=ReportCategory.WORKING_NORMALLY.value)
    description = Column(Text, nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Evidence levels:
    # 1: Unverified report by community member
    # 2: Session-supported report (linked to paid booking/charging session)
    # 3: Trusted operational evidence (operator telemetry / verified hardware)
    evidence_level = Column(Integer, nullable=False, default=1)
    
    is_verified = Column(Boolean, default=False, nullable=False)
    moderation_status = Column(String(50), default="published", nullable=False)  # published, under_review, rejected
    moderation_notes = Column(Text, nullable=True)
    moderated_by_id = Column(Integer, nullable=True)
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)

    station = relationship("ChargingStation", back_populates="reports", foreign_keys=[station_id])
    home_listing = relationship("HomeChargerListing", back_populates="reports", foreign_keys=[home_listing_id])
    user = relationship("User", back_populates="reports")
    evidence_items = relationship("ReportEvidence", back_populates="report", cascade="all, delete-orphan")


class ReportEvidence(Base):
    __tablename__ = "report_evidence"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("charger_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type = Column(String(50), nullable=False)  # meter_photo, receipt, charging_app_screenshot, vehicle_telemetry
    file_url = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    report = relationship("ChargerReport", back_populates="evidence_items")


class ChargerStatusSnapshot(Base):
    """
    Cached aggregated operational status calculated by the Reliability Scoring Engine.
    Computes time-decayed evidence weights, conflict detection, and confidence levels.
    """
    __tablename__ = "charger_status_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    station_id = Column(Integer, ForeignKey("charging_stations.id", ondelete="CASCADE"), nullable=True, index=True)
    home_listing_id = Column(Integer, ForeignKey("home_charger_listings.id", ondelete="CASCADE"), nullable=True, index=True)
    
    operational_status = Column(String(100), nullable=False, default=OperationalStatus.UNKNOWN.value)
    confidence_score = Column(Float, nullable=False, default=0.5)  # 0.00 to 1.00
    evidence_summary = Column(String(255), nullable=False, default="Initial baseline")
    
    total_reports_evaluated = Column(Integer, default=0, nullable=False)
    positive_weight = Column(Float, default=0.0, nullable=False)
    negative_weight = Column(Float, default=0.0, nullable=False)
    
    last_reported_at = Column(DateTime(timezone=True), nullable=True)
    calculated_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    station = relationship("ChargingStation", back_populates="status_snapshots", foreign_keys=[station_id])
    home_listing = relationship("HomeChargerListing", back_populates="status_snapshots", foreign_keys=[home_listing_id])
