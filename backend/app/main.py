import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.db.session import Base, engine, SessionLocal


class JsonFormatter(logging.Formatter):
    """Structured logs. Messages must never include secrets, tokens or payment details."""
    def format(self, record: logging.LogRecord) -> str:
        payload = {"ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"), "level": record.levelname,
                   "logger": record.name, "msg": record.getMessage()}
        for k in ("request_id", "method", "path", "status", "duration_ms"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if settings.ENVIRONMENT != "development" else logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)


_configure_logging()
logger = logging.getLogger("chargecircle")
settings.validate_for_runtime()  # refuses to boot in production with unsafe configuration

os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)

# Development convenience only. Production schemas are managed by `alembic upgrade head`.
if settings.AUTO_CREATE_TABLES and not settings.is_production:
    Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="ChargeCircle - India's EV Charging Discovery, Home Charging Marketplace & Reliability Platform",
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# CORS: only explicitly configured origins, in every environment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error", extra={"request_id": rid, "method": request.method, "path": request.url.path})
        raise
    response.headers["X-Request-ID"] = rid
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path != "/health":
        logger.info("request", extra={"request_id": rid, "method": request.method, "path": request.url.path,
                                      "status": response.status_code, "duration_ms": round((time.perf_counter() - start) * 1000)})
    return response


if os.path.exists(settings.LOCAL_UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=settings.LOCAL_UPLOAD_DIR), name="uploads")

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["System"])
def health_check():
    """Liveness probe: the process is up. Use /health/ready to verify dependencies."""
    return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION, "environment": settings.ENVIRONMENT}


@app.get("/health/ready", tags=["System"])
def readiness_check():
    """Readiness probe: actually queries the database. Reports configuration presence, never values."""
    db_ok = True
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        logger.exception("readiness: database check failed")
        db_ok = False
    body = {
        "status": "ready" if db_ok else "unavailable", "database": "ok" if db_ok else "unreachable",
        "payment_mode": settings.PAYMENT_MODE, "payment_credentials_configured": bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET),
        "webhook_secret_configured": bool(settings.RAZORPAY_WEBHOOK_SECRET), "email_backend": settings.EMAIL_BACKEND,
        "live_station_feed": "enabled" if settings.live_feed_enabled else "disabled_or_unconfigured",
        "routing": settings.ROUTING_PROVIDER,
    }
    return JSONResponse(status_code=200 if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE, content=body)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global structured error handler. Details are never returned unless DEBUG is on (never in production)."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error",
                 "message": str(exc) if (settings.DEBUG and not settings.is_production) else "An unexpected error occurred. Please try again later."},
    )
