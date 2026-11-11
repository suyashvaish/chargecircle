from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.db.session import Base
from app.models.enums import PaymentStatus


def utc_now():
    return datetime.now(timezone.utc)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_reference = Column(String(64), unique=True, index=True, nullable=False)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="INR", nullable=False)
    status = Column(String(50), nullable=False, default=PaymentStatus.CREATED.value, index=True)
    
    provider = Column(String(50), default="razorpay", nullable=False)
    provider_order_id = Column(String(100), unique=True, index=True, nullable=True)
    provider_payment_id = Column(String(100), unique=True, index=True, nullable=True)
    provider_signature = Column(String(255), nullable=True)
    idempotency_key = Column(String(128), unique=True, index=True, nullable=False)
    failure_reason = Column(String(255), nullable=True)
    is_mock = Column(Boolean, nullable=False, default=False)  # created by the development-only mock provider
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    booking = relationship("Booking", back_populates="payment")
    user = relationship("User", back_populates="payments")
    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="processed")  # initiated, processed, failed
    provider_refund_id = Column(String(100), nullable=True, unique=True)
    initiated_by_id = Column(Integer, nullable=True)
    failure_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    payment = relationship("Payment", back_populates="refunds")


class HostEarning(Base):
    __tablename__ = "host_earnings"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    gross_amount = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    net_earnings = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="accrued")  # accrued, available, paid_out
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class Payout(Base):
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True, index=True)
    host_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    status = Column(String(50), nullable=False, default="initiated")  # initiated, processed, failed
    payout_reference = Column(String(64), unique=True, nullable=False)
    bank_account_masked = Column(String(50), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class PaymentEvent(Base):
    """Processed provider webhook events; the unique event id makes webhook handling idempotent."""
    __tablename__ = "payment_events"

    id = Column(Integer, primary_key=True, index=True)
    provider_event_id = Column(String(128), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True)
    outcome = Column(String(50), nullable=False, default="processed")  # processed | ignored | rejected
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
