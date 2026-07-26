"""
NEXUS AI — Backend Application Entry Point
FastAPI application factory with all middleware, routes, and lifecycle handlers.
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.router import api_router

# ─── Logging ──────────────────────────────────────────────────────────────────
setup_logging()
logger = logging.getLogger(__name__)


# ─── Application Lifespan ─────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Async context manager for application startup and shutdown events.
    Resources initialized here are available for the lifetime of the app.
    """
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("🚀 NEXUS AI Backend starting up...")
    logger.info(f"   Environment : {settings.APP_ENV}")
    logger.info(f"   Version     : {settings.APP_VERSION}")
    logger.info(f"   Paper Mode  : {settings.PAPER_TRADING_MODE}")

    # TODO (Phase 2): Initialize database connections
    # TODO (Phase 2): Initialize Redis connection pool
    # TODO (Phase 2): Initialize Kafka producers
    # TODO (Phase 7): Initialize NLP model cache

    logger.info("✅ NEXUS AI Backend ready.")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("🛑 NEXUS AI Backend shutting down...")
    # TODO: Graceful shutdown of connections
    logger.info("👋 Shutdown complete.")


# ─── Application Factory ──────────────────────────────────────────────────────
def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "NEXUS AI — NIFTY Expert eXecution & Understanding System. "
            "Institutional-grade AI-powered trading intelligence platform "
            "for NIFTY 50 option trade decision support."
        ),
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    # ── Request Timing Middleware ──────────────────────────────────────────────
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        return response

    # ── Global Exception Handler ───────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.method} {request.url}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc) if settings.APP_ENV == "development" else None,
            },
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    return app


# ─── ASGI Application ─────────────────────────────────────────────────────────
app = create_app()
