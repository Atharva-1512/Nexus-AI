"""
NEXUS AI — AI Signal / Decision Engine Endpoints (Phase 1 Skeleton)
Full implementation in Phase 10 (Decision Engine + Explainability).
"""

from typing import Literal, Optional
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

router = APIRouter()


# ─── Response Schemas ─────────────────────────────────────────────────────────

class FactorWeight(BaseModel):
    """Individual factor contribution to the final signal."""
    factor: str
    value: str            # Human-readable current value, e.g. "PCR: 1.23 ↑"
    weight_pct: float     # % contribution to confidence
    direction: Literal["bullish", "bearish", "neutral"]
    narrative: str        # e.g. "PCR rising — more puts than calls, bullish bias"


class TradeRecommendation(BaseModel):
    """Full AI trade recommendation with explainability."""
    signal: Literal["BUY_CALL", "BUY_PUT", "NO_TRADE"]
    confidence: float                          # 0–100
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    risk_reward: Optional[float] = None
    holding_time_minutes: Optional[int] = None
    expected_return_pct: Optional[float] = None
    expected_risk_pct: Optional[float] = None

    # Explainability
    factor_weights: list[FactorWeight] = Field(default_factory=list)
    composite_reasoning: str = ""
    contradictions: list[str] = Field(default_factory=list)  # e.g. "VIX elevated"
    regime: str = "UNKNOWN"                    # Market regime

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get(
    "/latest",
    summary="Get latest AI trade signal",
    response_description="Most recent trade recommendation from the Decision Engine.",
)
async def get_latest_signal():
    """
    Returns the latest AI-generated trade signal for NIFTY options.

    Phase 10 implementation will combine signals from all 22 modules
    and return a SHAP-explained recommendation.

    Current Phase 1: Returns a mock response to validate the schema.
    """
    # ── Mock response for Phase 1 ─────────────────────────────────────────────
    # This will be replaced with real Decision Engine output in Phase 10
    mock = TradeRecommendation(
        signal="BUY_CALL",
        confidence=87.0,
        entry_price=215.0,
        stop_loss=170.0,
        target_1=290.0,
        target_2=360.0,
        risk_reward=2.1,
        holding_time_minutes=90,
        expected_return_pct=8.5,
        expected_risk_pct=4.0,
        factor_weights=[
            FactorWeight(factor="PCR", value="PCR: 1.31 ↑", weight_pct=18.0,
                         direction="bullish", narrative="PCR rising — call sellers covering, bullish sentiment"),
            FactorWeight(factor="OI Build-up", value="OI +2.1M at 24500CE", weight_pct=21.0,
                         direction="bullish", narrative="Strong call OI build-up at 24500 — resistance defined"),
            FactorWeight(factor="News Sentiment", value="Positive 72%", weight_pct=12.0,
                         direction="bullish", narrative="3 high-impact bullish news items in last 2 hours"),
            FactorWeight(factor="FII Flow", value="FII: +₹1,240Cr", weight_pct=15.0,
                         direction="bullish", narrative="FII net buyers — institutional conviction"),
            FactorWeight(factor="Indicators", value="RSI 63, MACD cross, ST Green", weight_pct=20.0,
                         direction="bullish", narrative="RSI in bullish zone, MACD crossed positive, SuperTrend green"),
            FactorWeight(factor="Greeks", value="Delta 0.47, GEX +ve", weight_pct=14.0,
                         direction="bullish", narrative="Positive gamma exposure — dealers long gamma, market support"),
        ],
        composite_reasoning=(
            "Strong multi-factor bullish confluence detected. "
            "Institutional flow (FII), options positioning (PCR, GEX), "
            "and technical indicators all aligned bullish. "
            "Entry near VWAP support with 2.1:1 risk-reward."
        ),
        contradictions=["India VIX at 14.2 — slightly elevated, position size reduced by 15%"],
        regime="TRENDING_BULLISH",
    )

    return mock


@router.get("/history", summary="Get signal history")
async def get_signal_history(limit: int = 20):
    """
    Returns the last N trade signals.
    Phase 10: Fetches from PostgreSQL signal history table.
    """
    return JSONResponse(
        content={
            "status": "Phase 10 — Not yet implemented",
            "description": "Will return historical signals with outcomes for journaling.",
        }
    )


@router.get("/explainability/{signal_id}", summary="Get full explainability for a signal")
async def get_signal_explainability(signal_id: str):
    """
    Returns SHAP values and full factor breakdown for a specific signal.
    Phase 10: Returns SHAP waterfall chart data and per-feature contributions.
    """
    return JSONResponse(
        content={
            "signal_id": signal_id,
            "status": "Phase 10 — Not yet implemented",
            "description": "Will return SHAP values, factor weights, and confidence timeline.",
        }
    )
