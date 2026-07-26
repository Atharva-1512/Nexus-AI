"""
NEXUS AI — Explainability & Interpretability Engine (Phase 10)

Generates feature importance, factor waterfall metrics, SHAP/LIME proxy values,
and human-readable explainability narratives as requested by the user.

Output Breakdown:
- Overall Recommendation & Confidence
- Factor Waterfall Weights (PCR, OI, News, FII, Indicators, Greeks)
- Key Drivers (Positive & Negative reasons)
- SHAP / Feature impact scores
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class FactorWeight:
    factor_name: str
    weight_pct: float         # e.g., 18.0 for 18%
    score: float              # 0 to 100
    impact: str               # "BULLISH" | "BEARISH" | "NEUTRAL"
    shap_value: float         # Simulated SHAP value (-1.0 to +1.0)


@dataclass
class ExplainabilityReport:
    recommendation: str
    confidence: float
    summary_reason: str
    bullish_reasons: List[str]
    bearish_reasons: List[str]
    factor_breakdown: List[FactorWeight]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ExplainabilityEngine:
    """
    Computes explainability metrics, waterfall weights, and SHAP feature impacts.
    """

    def generate_report(
        self,
        recommendation: str = "BUY_CALL",
        confidence: float = 91.0,
        factor_scores: Optional[Dict[str, float]] = None,
    ) -> ExplainabilityReport:
        """
        Build full explainability report.
        Default factor weights requested: PCR (18%), OI (21%), News (12%), FII (15%), Indicators (20%), Greeks (14%).
        """
        if factor_scores is None:
            factor_scores = {
                "PCR": 78.0,
                "OI": 85.0,
                "News": 70.0,
                "FII": 80.0,
                "Indicators": 75.0,
                "Greeks": 72.0,
            }

        weights_map = {
            "PCR": 18.0,
            "OI": 21.0,
            "News": 12.0,
            "FII": 15.0,
            "Indicators": 20.0,
            "Greeks": 14.0,
        }

        breakdown: List[FactorWeight] = []
        bullish_reasons = []
        bearish_reasons = []

        for name, weight in weights_map.items():
            score = factor_scores.get(name, 50.0)
            impact = "BULLISH" if score >= 60 else "BEARISH" if score <= 40 else "NEUTRAL"
            shap_val = (score - 50.0) / 50.0  # Normalized to [-1.0, 1.0]

            breakdown.append(
                FactorWeight(
                    factor_name=name,
                    weight_pct=weight,
                    score=score,
                    impact=impact,
                    shap_value=round(shap_val, 3),
                )
            )

            if impact == "BULLISH":
                bullish_reasons.append(f"{name} ↑ ({score:.0f}/100)")
            elif impact == "BEARISH":
                bearish_reasons.append(f"{name} ↓ ({score:.0f}/100)")

        summary = f"{recommendation} with {confidence:.0f}% confidence supported by {len(bullish_reasons)} bullish factors."

        return ExplainabilityReport(
            recommendation=recommendation,
            confidence=confidence,
            summary_reason=summary,
            bullish_reasons=bullish_reasons,
            bearish_reasons=bearish_reasons,
            factor_breakdown=breakdown,
        )


# ── Singleton ──────────────────────────────────────────────────────────────────
explainability_engine = ExplainabilityEngine()
