from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.models.enums import ReportCategory
from app.services.text import sanitize_text

REPORT_CATEGORIES = {c.value for c in ReportCategory}
EVIDENCE_TYPES = {"meter_photo", "receipt", "charging_app_screenshot", "price_board_photo", "other"}


class ReportEvidenceOut(BaseModel):
    id: int
    evidence_type: str
    file_url: str
    description: Optional[str] = None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ReportCreate(BaseModel):
    station_id: Optional[int] = None
    home_listing_id: Optional[int] = None
    booking_id: Optional[int] = None  # If provided, elevates to Evidence Level 2 if verified payment exists
    category: str = Field(..., description="working_normally, not_working, occupied, damaged_equipment, etc.")
    description: Optional[str] = Field(default=None, max_length=2000)
    evidence_type: Optional[str] = None  # meter_photo, receipt, charging_app_screenshot
    evidence_file_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("category")
    @classmethod
    def _category(cls, v):
        if v not in REPORT_CATEGORIES:
            raise ValueError(f"category must be one of: {', '.join(sorted(REPORT_CATEGORIES))}")
        return v

    @field_validator("description", mode="after")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 2000) if v else v

    @field_validator("evidence_type")
    @classmethod
    def _etype(cls, v):
        if v is not None and v not in EVIDENCE_TYPES:
            raise ValueError("unsupported evidence_type")
        return v

    @field_validator("evidence_file_url")
    @classmethod
    def _url(cls, v):
        if v and not v.lower().startswith("https://"):
            raise ValueError("Evidence links must use https://")
        return v


class ReportOut(BaseModel):
    id: int
    station_id: Optional[int] = None
    home_listing_id: Optional[int] = None
    category: str
    description: Optional[str] = None
    evidence_level: int
    is_verified: bool
    moderation_status: str
    created_at: datetime
    evidence_items: List[ReportEvidenceOut] = []

    class Config:
        from_attributes = True


class ReliabilityScoreBreakdown(BaseModel):
    operational_status: str
    confidence_score: float  # 0.0 to 1.0
    evidence_summary: str
    total_reports_evaluated: int
    positive_weight: float
    negative_weight: float
    last_reported_at: Optional[datetime] = None
    calculated_at: datetime


class ModerationActionCreate(BaseModel):
    target_type: str = Field(..., pattern="^(report|listing|review|dispute)$")
    target_id: int
    action: str = Field(..., pattern="^(approved|rejected|suspended|dismissed|resolved|escalated|hidden|restored)$")
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("notes", mode="after")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 2000) if v else v


class ResolveDisputeRequest(BaseModel):
    decision: str = Field(..., pattern="^(refund_full|resolve_no_refund|dismiss|escalate)$")
    notes: str = Field(..., min_length=5, max_length=2000)

    @field_validator("notes", mode="after")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, 2000)
