"""
NEXUS AI — V1 API Router
Aggregates all v1 endpoint routers into a single mountable router.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import health, market, options, ml, signals, alerts, technical, macro, sentiment, decision, explainability

api_router = APIRouter()

# ── Core ──────────────────────────────────────────────────────────────────────
api_router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)

# ── Market Data (Module 1) ─────────────────────────────────────────────────────
api_router.include_router(
    market.router,
    prefix="/market",
    tags=["Market Data"],
)

# ── Options Intelligence (Modules 3–5) ────────────────────────────────────────
api_router.include_router(
    options.router,
    prefix="/options",
    tags=["Options"],
)

# ── Technical Analysis (Phase 4) ──────────────────────────────────────────────
api_router.include_router(
    technical.router,
    prefix="/technical",
    tags=["Technical Analysis"],
)

# ── Macro Intelligence (Phase 5) ──────────────────────────────────────────────
api_router.include_router(
    macro.router,
    prefix="/macro",
    tags=["Macro Intelligence"],
)

# ── Sentiment Intelligence (Phase 6) ──────────────────────────────────────────
api_router.include_router(
    sentiment.router,
    prefix="/sentiment",
    tags=["Sentiment Intelligence"],
)

# ── Decision Engine (Phase 7) ────────────────────────────────────────────────────
api_router.include_router(
    decision.router,
    prefix="/decision",
    tags=["Decision Engine"],
)

# ── ML Pipelines (Phase 8) ──────────────────────────────────────────────────
api_router.include_router(
    ml.router,
    prefix="/ml",
    tags=["ML Pipelines"],
)

# ── AI Signals / Decision Engine (Modules 22–23) ──────────────────────────────
api_router.include_router(
    signals.router,
    prefix="/signals",
    tags=["AI Signals"],
)

# ── Alert Engine (Module 24) ──────────────────────────────────────────────────
api_router.include_router(
    alerts.router,
    prefix="/alerts",
    tags=["Alerts"],
)

# ── Explainability Dashboard (Phase 10) ───────────────────────────────────────
api_router.include_router(
    explainability.router,
    prefix="/explainability",
    tags=["Explainability"],
)

