"""
NEXUS AI — Macro Intelligence Service Layer (Phase 5)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MacroService:
    """Service layer for macro intelligence endpoints."""

    def __init__(self):
        self._engine = None
        self._classifier = None

    def _get_engine(self):
        if self._engine is None:
            from modules.macro.macro_engine import macro_engine
            self._engine = macro_engine
        return self._engine

    def _get_classifier(self):
        if self._classifier is None:
            from modules.macro.regime_classifier import MacroRegimeClassifier
            self._classifier = MacroRegimeClassifier()
        return self._classifier

    def _snap_to_dict(self, snap) -> dict:
        """Convert MacroSnapshot to JSON-safe dict."""
        return {
            "global_bias":    snap.global_bias,
            "macro_risk":     snap.macro_risk,
            "combined_score": snap.combined_score,
            "narrative":      snap.narrative,
            "usdinr":         snap.usdinr,
            "usdinr_chg_pct": snap.usdinr_chg_pct,
            "dxy":            snap.dxy,
            "dxy_chg_pct":    snap.dxy_chg_pct,
            "crude_wti":      snap.crude_wti,
            "crude_chg_pct":  snap.crude_chg_pct,
            "gold":           snap.gold,
            "gold_chg_pct":   snap.gold_chg_pct,
            "india_vix":      snap.india_vix,
            "us_vix":         snap.us_vix,
            "us_10y_yield":   snap.us_10y_yield,
            "us_10y_chg":     snap.us_10y_chg,
            "fii_net_crore":  snap.fii_net_crore,
            "dii_net_crore":  snap.dii_net_crore,
            "indices": [
                {
                    "symbol":     idx.symbol,
                    "name":       idx.name,
                    "price":      idx.price,
                    "change_pct": idx.change_pct,
                    "region":     idx.region,
                    "signal":     idx.signal,
                    "weight":     idx.weight,
                }
                for idx in snap.indices
            ],
            "timestamp": snap.timestamp.isoformat() if snap.timestamp else None,
        }

    async def get_snapshot(self, use_live: bool = False) -> dict:
        """Get full macro snapshot. Falls back to synthetic when live data unavailable."""
        try:
            engine = self._get_engine()
            if use_live:
                snap = engine.fetch_all()
            else:
                snap = engine.synthetic_snapshot("neutral")
            return self._snap_to_dict(snap)
        except Exception as e:
            logger.error(f"get_snapshot failed: {e}")
            engine = self._get_engine()
            snap   = engine.synthetic_snapshot("neutral")
            return self._snap_to_dict(snap)

    async def get_regime(self, use_live: bool = False) -> dict:
        """Get current macro regime classification."""
        try:
            engine     = self._get_engine()
            classifier = self._get_classifier()
            if use_live:
                snap = engine.fetch_all()
            else:
                snap = engine.synthetic_snapshot("neutral")
            regime = classifier.classify(snap)
            return {
                "regime":          regime.regime.value,
                "confidence":      regime.confidence,
                "size_multiplier": regime.size_multiplier,
                "description":     regime.description,
                "triggers":        regime.triggers,
                "bias":            regime.bias,
            }
        except Exception as e:
            logger.error(f"get_regime failed: {e}")
            return {"error": str(e)}

    async def get_global_indices(self, use_live: bool = False) -> dict:
        """Get global index prices and signals."""
        try:
            engine = self._get_engine()
            if use_live:
                snap = engine.fetch_all()
            else:
                snap = engine.synthetic_snapshot("neutral")
            return {
                "global_bias": snap.global_bias,
                "indices": [
                    {
                        "symbol":     idx.symbol,
                        "name":       idx.name,
                        "price":      idx.price,
                        "change_pct": idx.change_pct,
                        "region":     idx.region,
                        "signal":     idx.signal,
                        "weight":     f"{idx.weight*100:.0f}%",
                    }
                    for idx in snap.indices
                ],
            }
        except Exception as e:
            logger.error(f"get_global_indices failed: {e}")
            return {"error": str(e)}

    async def get_currencies(self, use_live: bool = False) -> dict:
        """Get currency and commodity rates."""
        try:
            engine = self._get_engine()
            snap   = engine.synthetic_snapshot("neutral") if not use_live else engine.fetch_all()
            return {
                "usdinr":         snap.usdinr,
                "usdinr_chg_pct": snap.usdinr_chg_pct,
                "usdinr_signal":  "BEARISH" if snap.usdinr_chg_pct > 0.2 else "BULLISH" if snap.usdinr_chg_pct < -0.2 else "NEUTRAL",
                "dxy":            snap.dxy,
                "dxy_chg_pct":    snap.dxy_chg_pct,
                "crude_wti":      snap.crude_wti,
                "crude_chg_pct":  snap.crude_chg_pct,
                "crude_signal":   "BEARISH" if snap.crude_chg_pct > 1.0 else "BULLISH" if snap.crude_chg_pct < -1.0 else "NEUTRAL",
                "gold":           snap.gold,
                "gold_chg_pct":   snap.gold_chg_pct,
            }
        except Exception as e:
            logger.error(f"get_currencies failed: {e}")
            return {"error": str(e)}

    async def get_vix(self, use_live: bool = False) -> dict:
        """Get VIX and rate data."""
        try:
            engine = self._get_engine()
            snap   = engine.synthetic_snapshot("neutral") if not use_live else engine.fetch_all()
            vix_signal = (
                "EXTREME_FEAR" if snap.india_vix > 25 else
                "FEAR" if snap.india_vix > 20 else
                "ELEVATED" if snap.india_vix > 15 else
                "NORMAL" if snap.india_vix > 12 else
                "COMPLACENT"
            )
            return {
                "india_vix":      snap.india_vix,
                "us_vix":         snap.us_vix,
                "vix_signal":     vix_signal,
                "us_10y_yield":   snap.us_10y_yield,
                "us_10y_chg":     snap.us_10y_chg,
                "rate_signal":    "HAWKISH" if snap.us_10y_yield > 4.7 else "DOVISH" if snap.us_10y_yield < 4.0 else "NEUTRAL",
            }
        except Exception as e:
            logger.error(f"get_vix failed: {e}")
            return {"error": str(e)}


_svc: Optional[MacroService] = None

def get_macro_service() -> MacroService:
    global _svc
    if _svc is None:
        _svc = MacroService()
    return _svc
