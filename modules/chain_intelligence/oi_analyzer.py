"""
NEXUS AI — OI Analyzer (Module 5)

Analyzes Open Interest patterns to identify:
  1. OI build-up type (long build-up, short covering, etc.)
  2. OI concentration zones (walls)
  3. OI change trends (accumulation vs distribution)
  4. Overall OI-based market sentiment

OI Build-up Classification:
  Price ↑ + OI ↑  → LONG_BUILDUP    (fresh longs)   → Bullish
  Price ↓ + OI ↓  → LONG_UNWINDING  (longs exiting)  → Bearish
  Price ↓ + OI ↑  → SHORT_BUILDUP   (fresh shorts)   → Bearish
  Price ↑ + OI ↓  → SHORT_COVERING  (shorts exit)    → Bullish
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .models import (
    ChainSnapshot, ChainSignalDirection,
    OIBuildType, SupportResistanceLevel
)

logger = logging.getLogger(__name__)


@dataclass
class OIAnalysisResult:
    """Result of open interest analysis."""
    call_oi_signal:    str    # Dominant OI build type for calls (e.g. "SHORT_BUILDUP")
    put_oi_signal:     str    # Dominant OI build type for puts
    net_sentiment:     ChainSignalDirection
    top_call_oi:       list[dict]   # Top-5 strikes by call OI
    top_put_oi:        list[dict]   # Top-5 strikes by put OI
    oi_change_leader:  str          # "CALLS" or "PUTS" — which side saw more OI change
    narrative:         str
    bullish_score:     float        # 0–100


class OIAnalyzer:
    """Analyzes Open Interest patterns across the chain."""

    def analyze(self, chain: ChainSnapshot) -> OIAnalysisResult:
        strikes = chain.strikes
        if not strikes:
            return OIAnalysisResult(
                call_oi_signal="NEUTRAL", put_oi_signal="NEUTRAL",
                net_sentiment=ChainSignalDirection.NEUTRAL,
                top_call_oi=[], top_put_oi=[],
                oi_change_leader="NEITHER", narrative="No data", bullish_score=50.0,
            )

        # Aggregate OI build types for calls and puts
        call_build_counts: dict[str, int] = {}
        put_build_counts:  dict[str, int] = {}

        for s in strikes:
            cb = s.oi_build_call.value
            pb = s.oi_build_put.value
            call_build_counts[cb] = call_build_counts.get(cb, 0) + 1
            put_build_counts[pb]  = put_build_counts.get(pb,  0) + 1

        call_dominant = max(call_build_counts, key=call_build_counts.get)
        put_dominant  = max(put_build_counts,  key=put_build_counts.get)

        # OI change totals
        total_call_oi_chg = sum(abs(s.call_oi_change) for s in strikes)
        total_put_oi_chg  = sum(abs(s.put_oi_change)  for s in strikes)
        oi_change_leader  = "CALLS" if total_call_oi_chg > total_put_oi_chg else "PUTS"

        # Bullish score from build types
        bullish_score = self._compute_bullish_score(call_dominant, put_dominant)

        # Overall sentiment
        sentiment = self._map_score_to_sentiment(bullish_score)

        # Top OI strikes
        top_calls = sorted(strikes, key=lambda s: s.call_oi, reverse=True)[:5]
        top_puts  = sorted(strikes, key=lambda s: s.put_oi,  reverse=True)[:5]

        narrative = self._build_narrative(
            call_dominant, put_dominant, bullish_score,
            oi_change_leader, chain.spot_price
        )

        return OIAnalysisResult(
            call_oi_signal   = call_dominant,
            put_oi_signal    = put_dominant,
            net_sentiment    = sentiment,
            top_call_oi      = [{"strike": s.strike, "call_oi": s.call_oi, "oi_change": s.call_oi_change} for s in top_calls],
            top_put_oi       = [{"strike": s.strike, "put_oi":  s.put_oi,  "oi_change": s.put_oi_change}  for s in top_puts],
            oi_change_leader = oi_change_leader,
            narrative        = narrative,
            bullish_score    = round(bullish_score, 1),
        )

    def _compute_bullish_score(self, call_build: str, put_build: str) -> float:
        """Score 0-100: 100=strongly bullish, 0=strongly bearish."""
        call_map = {
            "LONG_BUILDUP":   -15,   # New call longs = bearish (call OI ↑ = resistance)
            "LONG_UNWINDING":  15,   # Call longs exiting = bullish
            "SHORT_BUILDUP":   15,   # Call shorting = covered calls / bearish for calls but bullish for index if by writers
            "SHORT_COVERING": -15,
            "NEUTRAL":          0,
        }
        put_map = {
            "LONG_BUILDUP":   -20,   # New put buying = hedging / bearish
            "LONG_UNWINDING":  20,   # Put longs unwinding = bullish
            "SHORT_BUILDUP":   20,   # Put shorting = bullish (writers expect market to hold)
            "SHORT_COVERING": -20,
            "NEUTRAL":          0,
        }
        score = 50.0 + call_map.get(call_build, 0) + put_map.get(put_build, 0)
        return max(0.0, min(100.0, score))

    def _map_score_to_sentiment(self, score: float) -> ChainSignalDirection:
        if score >= 75:   return ChainSignalDirection.STRONGLY_BULLISH
        if score >= 60:   return ChainSignalDirection.BULLISH
        if score >= 40:   return ChainSignalDirection.NEUTRAL
        if score >= 25:   return ChainSignalDirection.BEARISH
        return ChainSignalDirection.STRONGLY_BEARISH

    def _build_narrative(
        self,
        call_build: str,
        put_build:  str,
        score:      float,
        oi_leader:  str,
        spot:       float,
    ) -> str:
        parts = []

        build_labels = {
            "LONG_BUILDUP":   "Long Build-up",
            "LONG_UNWINDING": "Long Unwinding",
            "SHORT_BUILDUP":  "Short Build-up",
            "SHORT_COVERING": "Short Covering",
            "NEUTRAL":        "Neutral",
        }
        parts.append(f"Calls: {build_labels.get(call_build, call_build)}")
        parts.append(f"Puts: {build_labels.get(put_build, put_build)}")

        if score >= 60:
            parts.append("OI positioning is BULLISH")
        elif score <= 40:
            parts.append("OI positioning is BEARISH")
        else:
            parts.append("OI positioning is NEUTRAL")

        parts.append(f"Dominant OI change in {oi_leader}")
        return "; ".join(parts)


class SupportResistanceDetector:
    """
    Identifies support and resistance levels from OI data.

    Key levels:
    - Call OI Wall (above spot) = Resistance: call writers defend this
    - Put OI Wall  (below spot) = Support: put writers defend this
    - OI concentration bands provide zones, not single levels
    """

    def detect(
        self,
        chain:      ChainSnapshot,
        n_levels:   int = 3,
    ) -> tuple[list[SupportResistanceLevel], list[SupportResistanceLevel]]:
        """
        Returns (support_levels, resistance_levels), each sorted by strength.

        Args:
            chain:    ChainSnapshot
            n_levels: Max levels to return in each direction

        Returns:
            (supports, resistances) — SupportResistanceLevel lists
        """
        spot = chain.spot_price
        above = sorted(
            [s for s in chain.strikes if s.strike > spot],
            key=lambda s: s.call_oi, reverse=True
        )
        below = sorted(
            [s for s in chain.strikes if s.strike <= spot],
            key=lambda s: s.put_oi, reverse=True
        )

        resistances = [
            SupportResistanceLevel(
                strike      = s.strike,
                level_type  = "RESISTANCE",
                oi_at_level = s.call_oi,
                strength    = self._classify_strength(s.call_oi, chain.total_call_oi),
                distance_pct= round((s.strike - spot) / spot * 100, 2),
            )
            for s in above[:n_levels]
        ]

        supports = [
            SupportResistanceLevel(
                strike      = s.strike,
                level_type  = "SUPPORT",
                oi_at_level = s.put_oi,
                strength    = self._classify_strength(s.put_oi, chain.total_put_oi),
                distance_pct= round((spot - s.strike) / spot * 100, 2),
            )
            for s in below[:n_levels]
        ]

        return supports, resistances

    @staticmethod
    def _classify_strength(oi: int, total_oi: int) -> str:
        if total_oi == 0:
            return "WEAK"
        pct = oi / total_oi
        if pct >= 0.15:   return "STRONG"
        if pct >= 0.07:   return "MODERATE"
        return "WEAK"
