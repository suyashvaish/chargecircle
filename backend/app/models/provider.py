from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer, String
from app.db.session import Base


def utc_now():
    return datetime.now(timezone.utc)


class ProviderSearchCache(Base):
    """Remembers when an area was last fetched from an external station provider (success or failure)."""
    __tablename__ = "provider_search_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String(120), unique=True, nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False)  # ok | error | rate_limited
    result_count = Column(Integer, nullable=False, default=0)
    error = Column(String(255), nullable=True)
    fetched_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
