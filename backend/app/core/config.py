import logging
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("chargecircle.config")

# Development-only placeholders. They are refused outright when ENVIRONMENT=production
# (see Settings.production_problems / validate_for_runtime).
_DEV_SECRET_KEY = "dev-only-insecure-secret-change-me-0123456789abcdef"
_DEV_ADMIN_PASSWORD = "AdminSecurePassword123!"


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"  # development | test | staging | production
    DEBUG: bool = False
    APP_NAME: str = "ChargeCircle"
    APP_VERSION: str = "1.1.0"

    # Base URLs
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./chargecircle.db"
    AUTO_CREATE_TABLES: bool = False  # dev convenience only; production uses Alembic migrations

    # Security
    SECRET_KEY: str = _DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    EMAIL_VERIFY_EXPIRE_HOURS: int = 48

    # Seed-only admin provisioning (scripts/seed_data.py). Never used at runtime.
    ADMIN_EMAIL: str = "admin@chargecircle.in"
    ADMIN_PASSWORD: str = _DEV_ADMIN_PASSWORD
    ADMIN_NAME: str = "ChargeCircle Platform Admin"

    # Mapping / routing
    MAPPING_PROVIDER: str = "leaflet"
    MAPBOX_ACCESS_TOKEN: Optional[str] = None
    GOOGLE_MAPS_API_KEY: Optional[str] = None
    ROUTING_PROVIDER: str = "none"  # none | openrouteservice
    ORS_API_KEY: Optional[str] = None
    ORS_BASE_URL: str = "https://api.openrouteservice.org"
    ROUTING_TIMEOUT_SECONDS: float = 8.0

    # Public charger data provider (Open Charge Map)
    OCM_API_KEY: Optional[str] = None
    OCM_BASE_URL: str = "https://api.openchargemap.io/v3/poi/"
    USE_LIVE_CHARGER_FEED: bool = False
    OCM_MAX_RADIUS_KM: float = 50.0
    OCM_MAX_RESULTS: int = 50
    OCM_TIMEOUT_SECONDS: float = 8.0
    OCM_CACHE_TTL_SECONDS: int = 900          # successful fetch for same area is reused for 15 min
    OCM_ERROR_BACKOFF_SECONDS: int = 120      # do not hammer a failing provider
    DEDUPE_RADIUS_METERS: float = 75.0

    # Payments. PAYMENT_MODE: "razorpay" (real API) | "mock" (local development only)
    PAYMENT_MODE: str = "mock"
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_API_BASE: str = "https://api.razorpay.com/v1"
    PLATFORM_FEE_PERCENTAGE: float = 10.0
    BOOKING_HOLD_MINUTES: int = 15
    FREE_CANCELLATION_HOURS: float = 2.0

    # Listings
    AUTO_APPROVE_LISTINGS: bool = False  # development convenience only
    LOCATION_FUZZ_MIN_METERS: float = 300.0
    LOCATION_FUZZ_MAX_METERS: float = 500.0

    # Storage
    STORAGE_BACKEND: str = "local"
    LOCAL_UPLOAD_DIR: str = "./uploads"

    # Email. EMAIL_BACKEND: smtp | console (development: prints full emails) | disabled (metadata only)
    EMAIL_BACKEND: str = "console"
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: float = 10.0
    EMAIL_FROM: str = "support@chargecircle.in"
    EMAIL_SEND_SYNC: bool = False  # tests/dev: send inside the request instead of a worker thread

    # Reliability & trust engine
    REPORT_FRESHNESS_HALF_LIFE_HOURS: int = 72
    MAX_UNVERIFIED_REPORTS_PER_DAY: int = 5
    CONFIDENCE_THRESHOLD_OPERATIONAL: float = 0.70
    CONFIDENCE_THRESHOLD_UNAVAILABLE: float = 0.35

    # CORS (comma separated). Never "*" in production.
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def mock_payments_allowed(self) -> bool:
        return self.PAYMENT_MODE == "mock" and not self.is_production

    @property
    def live_feed_enabled(self) -> bool:
        return bool(self.USE_LIVE_CHARGER_FEED and self.OCM_API_KEY)

    def production_problems(self) -> List[str]:
        """Return everything that makes the current configuration unsafe for production."""
        problems: List[str] = []
        if self.SECRET_KEY == _DEV_SECRET_KEY or len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be a unique random value of at least 32 characters")
        if self.DEBUG:
            problems.append("DEBUG must be false")
        if "*" in self.cors_origins_list or not self.cors_origins_list:
            problems.append("CORS_ORIGINS must list explicit trusted origins (no '*')")
        if self.PAYMENT_MODE != "razorpay":
            problems.append("PAYMENT_MODE must be 'razorpay' (mock payments are development-only)")
        else:
            for name in ("RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET"):
                if not getattr(self, name):
                    problems.append(f"{name} is required when PAYMENT_MODE=razorpay")
        if self.DATABASE_URL.startswith("sqlite"):
            problems.append("DATABASE_URL must point at PostgreSQL (SQLite is development-only)")
        if self.EMAIL_BACKEND != "smtp" or not (self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD):
            problems.append("EMAIL_BACKEND=smtp with SMTP_HOST/SMTP_USER/SMTP_PASSWORD is required")
        if self.AUTO_APPROVE_LISTINGS:
            problems.append("AUTO_APPROVE_LISTINGS must be false")
        if self.AUTO_CREATE_TABLES:
            problems.append("AUTO_CREATE_TABLES must be false (use `alembic upgrade head`)")
        if self.FRONTEND_URL.startswith("http://localhost"):
            problems.append("FRONTEND_URL must be the public https URL (used in emailed links)")
        return problems

    def validate_for_runtime(self) -> None:
        if self.is_production:
            problems = self.production_problems()
            if problems:
                raise RuntimeError(
                    "Refusing to start in production with unsafe configuration:\n - " + "\n - ".join(problems)
                )
        elif self.SECRET_KEY == _DEV_SECRET_KEY:
            logger.warning("Using the development SECRET_KEY. Never deploy with it.")

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=True,
    )


settings = Settings()
