from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.services.text import sanitize_text


class ReviewCreate(BaseModel):
    booking_id: int
    rating_overall: float = Field(..., ge=1.0, le=5.0)
    rating_accuracy: float = Field(..., ge=1.0, le=5.0)
    rating_host: float = Field(..., ge=1.0, le=5.0)
    rating_parking: float = Field(..., ge=1.0, le=5.0)
    comment: str = Field(..., min_length=10, max_length=2000)

    @field_validator("comment", mode="after")
    @classmethod
    def _clean_comment(cls, v):
        v = sanitize_text(v, 2000)
        if len(v) < 10:
            raise ValueError("Comment must contain at least 10 characters of text")
        return v


class ReviewHostResponse(BaseModel):
    response: str = Field(..., min_length=5, max_length=2000)

    @field_validator("response", mode="after")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 2000)


class ReviewOut(BaseModel):
    id: int
    booking_id: int
    driver_name: Optional[str] = "EV Driver"
    listing_id: int
    rating_overall: float
    rating_accuracy: float
    rating_host: float
    rating_parking: float
    comment: str
    host_response: Optional[str] = None
    host_responded_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FavoriteCreate(BaseModel):
    station_id: Optional[int] = None
    home_listing_id: Optional[int] = None


class FavoriteOut(BaseModel):
    id: int
    user_id: int
    station_id: Optional[int] = None
    home_listing_id: Optional[int] = None
    title: Optional[str] = None
    address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    recipient_id: int
    booking_id: Optional[int] = None
    content: str = Field(..., min_length=1, max_length=2000)

    @field_validator("content", mode="after")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 2000)


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: Optional[str] = None
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationOut(BaseModel):
    id: int
    booking_id: Optional[int] = None
    other_participant_id: int
    other_participant_name: str
    last_message: Optional[str] = None
    last_message_at: datetime
    unread_count: int = 0

    class Config:
        from_attributes = True


class NotificationOut(BaseModel):
    id: int
    user_id: int
    title: str
    message: str
    notification_type: str
    action_link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class DisputeCreate(BaseModel):
    booking_id: int
    reason: str = Field(..., min_length=15, max_length=3000)
    category: str = Field(default="other", pattern="^(payment|session|host_conduct|other)$")
    evidence_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("reason", mode="after")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 3000)

    @field_validator("evidence_url", mode="after")
    @classmethod
    def _https(cls, v):
        if v and not v.lower().startswith("https://"):
            raise ValueError("Evidence links must use https://")
        return v


class DisputeOut(BaseModel):
    id: int
    booking_id: int
    filed_by_id: int
    against_id: int
    reason: str
    status: str
    category: str = "other"
    evidence_url: Optional[str] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AdminStatsOut(BaseModel):
    total_users: int
    total_drivers: int
    total_hosts: int
    total_public_stations: int
    total_home_listings: int
    pending_host_verifications: int
    total_bookings: int
    confirmed_bookings: int
    total_gross_revenue: float
    total_platform_fees: float
    pending_reports_moderation: int
    open_disputes: int
