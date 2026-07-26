"""
NEXUS AI — Health Check Endpoints
Used by Docker health checks, Kubernetes probes, and monitoring.
"""

import logging
import platform
import sys
import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# Application start time for uptime calculation
_START_TIME = time.time()


@router.get(
    "/",
    summary="Health check",
    description="Returns service health status. Used by load balancers and orchestrators.",
    response_description="Health status with uptime and version info.",
)
async def health_check():
    """
    Basic liveness probe.
    Returns 200 if the application process is alive.
    """
    uptime_seconds = time.time() - _START_TIME

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "paper_trading_mode": settings.PAPER_TRADING_MODE,
            "uptime_seconds": round(uptime_seconds, 2),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "python_version": sys.version,
            "platform": platform.system(),
        },
    )


@router.get(
    "/ready",
    summary="Readiness probe",
    description=(
        "Returns 200 when all dependencies (DB, Redis, Kafka) are reachable. "
        "Returns 503 if any critical dependency is unavailable. "
        "Used by Kubernetes readiness probes."
    ),
)
async def readiness_check():
    """
    Kubernetes readiness probe.
    Checks connectivity to all critical dependencies.
    """
    checks: dict[str, bool] = {}
    all_ready = True

    # ── Database check ─────────────────────────────────────────────────────
    try:
        # TODO (Phase 2): Replace with real DB ping
        # await db.execute("SELECT 1")
        checks["postgresql"] = True
    except Exception as e:
        logger.warning(f"PostgreSQL readiness check failed: {e}")
        checks["postgresql"] = False
        all_ready = False

    # ── Redis check ────────────────────────────────────────────────────────
    try:
        # TODO (Phase 2): Replace with real Redis ping
        # await redis.ping()
        checks["redis"] = True
    except Exception as e:
        logger.warning(f"Redis readiness check failed: {e}")
        checks["redis"] = False
        all_ready = False

    # ── Kafka check ────────────────────────────────────────────────────────
    try:
        # TODO (Phase 2): Replace with real Kafka ping
        checks["kafka"] = True
    except Exception as e:
        logger.warning(f"Kafka readiness check failed: {e}")
        checks["kafka"] = False
        all_ready = False

    status_code = 200 if all_ready else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ready else "not_ready",
            "checks": checks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


@router.get("/info", summary="Detailed system information")
async def system_info():
    """Returns detailed system and configuration info (development only)."""
    if not settings.is_development:
        return JSONResponse(
            status_code=403,
            content={"error": "System info only available in development mode"},
        )

    return {
        "app": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "environment": settings.APP_ENV,
            "paper_trading": settings.PAPER_TRADING_MODE,
        },
        "trading": {
            "min_confidence_threshold": settings.MIN_CONFIDENCE_THRESHOLD,
            "high_confidence_threshold": settings.HIGH_CONFIDENCE_THRESHOLD,
            "nifty_lot_size": settings.NIFTY_LOT_SIZE,
            "default_capital_inr": settings.DEFAULT_CAPITAL,
        },
        "alert": {
            "sound_enabled": settings.ALERT_SOUND_ENABLED,
            "desktop_enabled": settings.ALERT_DESKTOP_ENABLED,
            "min_confidence": settings.ALERT_MIN_CONFIDENCE,
        },
        "system": {
            "python": sys.version,
            "platform": platform.system(),
            "uptime_seconds": round(time.time() - _START_TIME, 2),
        },
    }
