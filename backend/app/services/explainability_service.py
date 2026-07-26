"""
NEXUS AI — Explainability Service Layer (Phase 10)
"""
import logging
from typing import Optional, Dict
from modules.explainability.explainability_engine import explainability_engine

logger = logging.getLogger(__name__)


class ExplainabilityService:
    """Service layer for explainability endpoints."""

    def __init__(self):
        self._engine = explainability_engine

    def get_explainability(
        self,
        recommendation: str = "BUY_CALL",
        confidence: float = 91.0,
    ) -> Dict:
        report = self._engine.generate_report(
            recommendation=recommendation,
            confidence=confidence,
        )
        return {
            "recommendation": report.recommendation,
            "confidence": report.confidence,
            "summary": report.summary_reason,
            "bullish_reasons": report.bullish_reasons,
            "bearish_reasons": report.bearish_reasons,
            "factor_weights": [
                {
                    "factor": f.factor_name,
                    "weight_pct": f.weight_pct,
                    "score": f.score,
                    "impact": f.impact,
                    "shap_value": f.shap_value,
                }
                for f in report.factor_breakdown
            ],
            "generated_at": report.timestamp.isoformat(),
        }


_svc: Optional[ExplainabilityService] = None

def get_explainability_service() -> ExplainabilityService:
    global _svc
    if _svc is None:
        _svc = ExplainabilityService()
    return _svc
