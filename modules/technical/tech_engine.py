"""
NEXUS AI — Technical Analysis Engine (Module 6 — Master Orchestrator)

Combines all technical signals into a single weighted score:
  RSI          → 20%  (momentum)
  MACD         → 20%  (trend momentum)
  EMA Cross    → 15%  (trend direction)
  Supertrend   → 15%  (trend regime)
  Price Action → 15%  (candlestick patterns)
  VWAP         → 10%  (intraday bias)
  ADX          → 5%   (trend strength filter)

This module contributes 20% to the NEXUS Decision Engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import numpy as np
import pandas as pd

from .indicators       import compute_all, rsi, macd, ema, atr
from .price_action     import PriceActionAnalyzer, TrendAnalysis, TrendDirection, CandlePattern
from .support_resistance import SupportResistanceAnalyzer

logger = logging.getLogger(__name__)

# Internal sub-weights (must sum to 1.0)
_WEIGHTS = {
    "rsi":           0.20,
    "macd":          0.20,
    "ema_cross":     0.15,
    "supertrend":    0.15,
    "price_action":  0.15,
    "vwap":          0.10,
    "adx":           0.05,
}


@dataclass
class TechSignal:
    """
    Output of the Technical Analysis Engine.
    Feeds into the NEXUS Decision Engine with 20% weight.
    """
    direction:          str           # BULLISH | BEARISH | NEUTRAL | STRONGLY_*
    confidence:         float         # 0–100
    bullish_score:      float         # 0–100 internal score
    indicators:         dict          # Raw computed indicator values
    trend:              TrendAnalysis
    patterns:           list[CandlePattern]
    support_resistance: dict
    factor_scores:      dict          # Per-factor breakdown for Explainability
    narrative:          str
    factor_weight:      float = 0.20  # 20% of Decision Engine
    timestamp:          Optional[datetime] = None


class TechEngine:
    """
    Master Technical Analysis Orchestrator.

    Fetches OHLCV data for NIFTY, computes all technical indicators,
    detects patterns, identifies S/R levels, and produces a single
    directional TechSignal.

    Usage:
        engine = TechEngine()
        signal = await engine.analyze("NIFTY", interval="15m", period="5d")
    """

    def __init__(self):
        self._pa  = PriceActionAnalyzer()
        self._sr  = SupportResistanceAnalyzer()

    def analyze_df(self, df: pd.DataFrame) -> TechSignal:
        """
        Run full technical analysis on a pre-loaded OHLCV DataFrame.

        Args:
            df: OHLCV DataFrame with columns: open, high, low, close, volume

        Returns:
            TechSignal with aggregated directional bias
        """
        if len(df) < 30:
            return self._insufficient_data_signal()

        # ── Compute all indicators ──────────────────────────────────────────
        ind = compute_all(df)
        if "error" in ind:
            return self._insufficient_data_signal()

        spot = float(df["close"].iloc[-1])

        # ── Price action ────────────────────────────────────────────────────
        patterns   = self._pa.detect_patterns(df, lookback=5)
        trend      = self._pa.analyze_trend(df)
        pattern_sig = self._pa.latest_pattern_signal(patterns)

        # ── S/R levels ──────────────────────────────────────────────────────
        sr_levels  = self._sr.all_levels(df, spot)

        # ── Per-factor bullish scores ────────────────────────────────────────
        factor_scores = self._compute_factor_scores(ind, trend, pattern_sig)

        # ── Weighted aggregate ──────────────────────────────────────────────
        bullish_score = sum(_WEIGHTS[k] * v for k, v in factor_scores.items())
        bullish_score = round(max(0.0, min(100.0, bullish_score)), 2)

        # ── Direction and confidence ─────────────────────────────────────────
        direction  = self._score_to_direction(bullish_score)
        confidence = round(min(100.0, abs(bullish_score - 50) * 2), 1)

        narrative = self._build_narrative(direction, bullish_score, ind, trend, patterns)

        return TechSignal(
            direction          = direction,
            confidence         = confidence,
            bullish_score      = bullish_score,
            indicators         = ind,
            trend              = trend,
            patterns           = patterns,
            support_resistance = sr_levels,
            factor_scores      = factor_scores,
            narrative          = narrative,
            timestamp          = datetime.now(timezone.utc),
        )

    async def analyze(
        self,
        symbol:   str = "NIFTY",
        interval: str = "15m",
        period:   str = "5d",
    ) -> TechSignal:
        """
        Fetch OHLCV data and run technical analysis.

        Falls back to 1d/3mo data if intraday is unavailable.
        """
        try:
            from modules.market_data.market_data_engine import market_engine
            df = await market_engine.get_ohlcv(symbol, interval=interval, period=period)
            if df is None or df.empty or len(df) < 30:
                # Fallback to daily data
                df = await market_engine.get_ohlcv(symbol, interval="1d", period="3mo")
            if df is None or df.empty:
                return self._insufficient_data_signal()
            return self.analyze_df(df)
        except Exception as e:
            logger.error(f"TechEngine.analyze failed [{symbol}]: {e}")
            return self._insufficient_data_signal()

    # ─── Factor Score Computation ─────────────────────────────────────────────

    def _compute_factor_scores(
        self,
        ind:         dict,
        trend:       TrendAnalysis,
        pattern_sig: str,
    ) -> dict:
        """Convert each indicator to a 0–100 bullish score."""
        scores = {}

        # RSI (0–100)
        rsi_val = ind.get("rsi") or 50.0
        if rsi_val >= 70:
            scores["rsi"] = 75.0   # Overbought but momentum strong — bullish
        elif rsi_val >= 55:
            scores["rsi"] = 65.0
        elif rsi_val >= 45:
            scores["rsi"] = 50.0
        elif rsi_val >= 30:
            scores["rsi"] = 35.0
        else:
            scores["rsi"] = 20.0   # Oversold — bearish momentum

        # MACD
        macd_cross = ind.get("macd_crossover", "NEUTRAL")
        if macd_cross   == "BULLISH_CROSS":  scores["macd"] = 80.0
        elif macd_cross == "BULLISH":        scores["macd"] = 65.0
        elif macd_cross == "NEUTRAL":        scores["macd"] = 50.0
        elif macd_cross == "BEARISH":        scores["macd"] = 35.0
        else:                                scores["macd"] = 20.0   # BEARISH_CROSS

        # EMA Cross (9 vs 21)
        ema_cross = ind.get("ema9_21_cross", "BEARISH")
        scores["ema_cross"] = 70.0 if ema_cross == "BULLISH" else 30.0

        # Supertrend
        st_dir = ind.get("supertrend_direction", "BEARISH")
        scores["supertrend"] = 72.0 if st_dir == "BULLISH" else 28.0

        # Price Action (candlestick patterns)
        if pattern_sig   == "BULLISH":  scores["price_action"] = 70.0
        elif pattern_sig == "BEARISH":  scores["price_action"] = 30.0
        else:                           scores["price_action"] = 50.0

        # Combine with trend direction
        if trend.direction == TrendDirection.UPTREND:
            scores["price_action"] = min(90.0, scores["price_action"] + 10.0)
        elif trend.direction == TrendDirection.DOWNTREND:
            scores["price_action"] = max(10.0, scores["price_action"] - 10.0)

        # VWAP
        vwap_sig = ind.get("vwap_signal", "NEUTRAL")
        if vwap_sig   == "BULLISH":          scores["vwap"] = 72.0
        elif vwap_sig == "SLIGHTLY_BULLISH": scores["vwap"] = 60.0
        elif vwap_sig == "AT_VWAP":          scores["vwap"] = 50.0
        elif vwap_sig == "SLIGHTLY_BEARISH": scores["vwap"] = 40.0
        else:                                scores["vwap"] = 28.0   # BEARISH

        # ADX (trend strength — modulate other scores)
        adx_val = ind.get("adx") or 15.0
        plus_di  = ind.get("plus_di") or 20.0
        minus_di = ind.get("minus_di") or 20.0
        if adx_val > 25:
            adx_score = 65.0 if plus_di > minus_di else 35.0
        else:
            adx_score = 50.0   # Weak trend → neutral ADX contribution
        scores["adx"] = adx_score

        return {k: round(v, 1) for k, v in scores.items()}

    @staticmethod
    def _score_to_direction(score: float) -> str:
        if score >= 75:  return "STRONGLY_BULLISH"
        if score >= 60:  return "BULLISH"
        if score >= 40:  return "NEUTRAL"
        if score >= 25:  return "BEARISH"
        return "STRONGLY_BEARISH"

    @staticmethod
    def _build_narrative(
        direction: str, score: float, ind: dict,
        trend: TrendAnalysis, patterns: list[CandlePattern],
    ) -> str:
        parts = [f"Tech Signal: {direction} (score {score:.0f}/100)"]
        parts.append(f"RSI={ind.get('rsi', '?'):.1f} ({ind.get('rsi_signal', '')})")
        parts.append(f"MACD={ind.get('macd_crossover', '')}")
        parts.append(f"Supertrend={ind.get('supertrend_direction', '')}")
        parts.append(f"Trend={trend.direction.value} ({trend.strength})")
        if patterns:
            best = patterns[0]
            parts.append(f"Pattern={best.pattern_type.value} ({best.direction})")
        return " | ".join(parts)

    @staticmethod
    def _insufficient_data_signal() -> TechSignal:
        from .price_action import TrendAnalysis, TrendDirection
        return TechSignal(
            direction="NEUTRAL", confidence=0.0, bullish_score=50.0,
            indicators={"error": "Insufficient data"},
            trend=TrendAnalysis(TrendDirection.UNKNOWN, "WEAK", [], [], False, False, False, False, 0, 0.0, "No data"),
            patterns=[], support_resistance={}, factor_scores={},
            narrative="Insufficient data for technical analysis",
            timestamp=datetime.now(timezone.utc),
        )


# ── Module-level singleton ─────────────────────────────────────────────────────
tech_engine = TechEngine()
