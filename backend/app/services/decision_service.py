"""
NEXUS AI — Decision Engine Service Layer (Phase 7)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DecisionService:
    """Service layer for the master decision engine."""

    def __init__(self):
        self._agg = None

    def _get_aggregator(self):
        if self._agg is None:
            from modules.decision_engine.aggregator import aggregator
            self._agg = aggregator
        return self._agg

    def _output_to_dict(self, out) -> dict:
        """Convert DecisionEngineOutput to JSON-safe dict."""
        trade = None
        if out.trade:
            trade = {
                "action":       out.trade.action,
                "strike":       out.trade.strike,
                "expiry":       out.trade.expiry,
                "option_type":  out.trade.option_type,
                "entry_low":    out.trade.entry_low,
                "entry_high":   out.trade.entry_high,
                "target_1r":    out.trade.target_1r,
                "target_2r":    out.trade.target_2r,
                "stop_loss":    out.trade.stop_loss,
                "risk_reward":  out.trade.risk_reward,
                "lot_size":     out.trade.lot_size,
                "max_lots":     out.trade.max_lots,
                "premium_est":  out.trade.premium_est,
            }

        return {
            "recommendation":   out.recommendation.value,
            "confidence":       out.confidence,
            "confidence_level": out.confidence_level.value,
            "bullish_score":    out.bullish_score,
            "direction":        out.direction,
            "macro_regime":     out.macro_regime,
            "size_multiplier":  out.size_multiplier,
            "narrative":        out.narrative,
            "reasoning":        out.reasoning,
            "spot_price":       out.spot_price,
            "data_freshness":   out.data_freshness,
            "trade":            trade,
            "factors": [
                {
                    "name":           f.name,
                    "weight":         f.weight,
                    "weight_pct":     f"{f.weight*100:.0f}%",
                    "raw_score":      f.raw_score,
                    "weighted_score": f.weighted_score,
                    "direction":      f.direction,
                    "available":      f.available,
                    "evidence":       f.evidence,
                }
                for f in out.factors
            ],
            "factor_weights": out.factor_weights,
            "factor_scores":  out.factor_scores,
            "generated_at":   out.timestamp.isoformat() if out.timestamp else None,
        }

    async def get_recommendation(
        self, spot: float = 24000.0, scenario: str = "neutral"
    ) -> dict:
        """Get full trading recommendation."""
        try:
            agg = self._get_aggregator()
            out = await agg.run(spot=spot, scenario=scenario)
            return self._output_to_dict(out)
        except Exception as e:
            logger.error(f"get_recommendation failed: {e}")
            return {"error": str(e)}

    async def get_factors(self, spot: float = 24000.0, scenario: str = "neutral") -> dict:
        """Get factor breakdown only (lighter call)."""
        try:
            agg = self._get_aggregator()
            out = await agg.run(spot=spot, scenario=scenario)
            return {
                "bullish_score":  out.bullish_score,
                "direction":      out.direction,
                "factors": [
                    {
                        "name":       f.name,
                        "weight_pct": f"{f.weight*100:.0f}%",
                        "score":      f.raw_score,
                        "direction":  f.direction,
                        "evidence":   f.evidence[:2],
                    }
                    for f in out.factors
                ],
            }
        except Exception as e:
            logger.error(f"get_factors failed: {e}")
            return {"error": str(e)}

    async def get_trade(self, spot: float = 24000.0, scenario: str = "neutral") -> dict:
        """Get trade details only."""
        try:
            agg = self._get_aggregator()
            out = await agg.run(spot=spot, scenario=scenario)
            if out.trade:
                trade_dict = {
                    "action":       out.trade.action,
                    "strike":       out.trade.strike,
                    "expiry":       out.trade.expiry,
                    "option_type":  out.trade.option_type,
                    "entry_low":    out.trade.entry_low,
                    "entry_high":   out.trade.entry_high,
                    "target_1r":    out.trade.target_1r,
                    "target_2r":    out.trade.target_2r,
                    "stop_loss":    out.trade.stop_loss,
                    "risk_reward":  out.trade.risk_reward,
                    "lot_size":     out.trade.lot_size,
                    "max_lots":     out.trade.max_lots,
                    "premium_est":  out.trade.premium_est,
                    "recommendation": out.recommendation.value,
                    "confidence":     out.confidence,
                }
                return trade_dict
            return {"action": out.recommendation.value, "trade": None, "reason": "No trade recommended"}
        except Exception as e:
            logger.error(f"get_trade failed: {e}")
            return {"error": str(e)}


_svc: Optional[DecisionService] = None

def get_decision_service() -> DecisionService:
    global _svc
    if _svc is None:
        _svc = DecisionService()
    return _svc
