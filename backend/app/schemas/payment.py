from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class PaymentInitiateRequest(BaseModel):
    booking_id: int
    idempotency_key: str = Field(..., min_length=8, max_length=128, description="Unique client key to prevent double charging")


class PaymentInitiateResponse(BaseModel):
    payment_reference: str
    booking_reference: str
    amount: float
    currency: str = "INR"
    razorpay_order_id: str
    razorpay_key_id: Optional[str] = None  # public key id (never the secret); None in mock mode
    mode: str = "razorpay"                 # razorpay | mock (development only)
    amount_paise: int = 0
    booking_id: int
    user_email: str
    user_name: str


class PaymentVerifyRequest(BaseModel):
    payment_reference: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentOut(BaseModel):
    id: int
    payment_reference: str
    booking_id: int
    user_id: int
    amount: float
    currency: str
    status: str
    provider: str
    provider_order_id: Optional[str] = None
    provider_payment_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RefundRequest(BaseModel):
    booking_id: int
    reason: str = Field(..., min_length=3, max_length=255)


class RefundOut(BaseModel):
    id: int
    payment_id: int
    booking_id: int
    amount: float
    reason: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CancelOut(BaseModel):
    booking_id: int
    booking_status: str
    refund: Optional[RefundOut] = None
    refund_amount: float = 0.0
    message: str


class SandboxSimulateRequest(BaseModel):
    payment_reference: str


class SandboxSimulateOut(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    notice: str = "Development mock only - no money moved."


class HostEarningOut(BaseModel):
    id: int
    host_id: int
    booking_id: int
    gross_amount: float
    platform_fee: float
    net_earnings: float
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class PayoutOut(BaseModel):
    id: int
    host_id: int
    amount: float
    status: str
    payout_reference: str
    bank_account_masked: str
    created_at: datetime

    class Config:
        from_attributes = True
