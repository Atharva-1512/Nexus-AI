"""
NEXUS AI — Put-Call Ratio Analyzer (Module 5)

PCR is one of the most reliable contrarian indicators for NIFTY options.

Interpretation:
  PCR > 1.5  → Extremely Bullish (excessive put buying = contrarian buy signal)
  PCR > 1.2  → Bullish
  PCR 0.8–1.2 → Neutral
  PCR < 0.8  → Bearish
  PCR < 0.5  → Extremely Bearish (excessive call buying = contrarian sell signal)

PCR by OI is more reliable than PCR by Volume for trend identification.
PCR by Volume is a short-term momentum indicator.

Key signals:
  - PCR rising with market falling → Smart money selling puts = bullish divergence
  - PCR falling with market rising → Smart money selling calls = bearish divergence
  - PCR at extremes (>1.5 or <0.5) → Mean reversion likely

OI Walls (Max OI strikes):
  - Highest Call OI strike = Key Resistance (call writers defending this level)
  - Highest Put OI strike = Key Support (put writers defending this level)
"""

import logging
from dataclasses import dataclass
from typing import Optional

from .models import ChainSnapshot, ChainSignalDirection, PCRAnalysis, OptionStrike

logger = logging.getLogger(__name__)

# PCR thresholds
_EXTREMELY_BULLISH = 1.5
_BULLISH           = 1.2
_BEARISH           = 0.8
_EXTREMELY_BEARISH = 0.5


class PCRAnalyzer:
    """
    Computes and interprets Put-Call Ratio from a ChainSnapshot.

    Provides:
    - PCR by OI (primary signal)
    - PCR by Volume (momentum signal)
    - OI-weighted PCR (emphasises strikes with high OI)
    - Call Wall and Put Wall identification
    - Bullish% score (0–100)
    """

    def analyze(self, chain: ChainSnapshot) -> PCRAnalysis:
        """
        Full PCR analysis on a ChainSnapshot.

        Returns:
            PCRAnalysis with signal, narrative, and key levels
        """
        pcr_oi     = chain.pcr_oi
        pcr_vol    = chain.pcr_volume

        # Find OI walls
        call_wall = self._find_call_wall(chain)
        put_wall  = self._find_put_wall(chain)

        # Classify signal
        signal, bullish_pct = self._classify(pcr_oi)

        # Build narrative
        narrative = self._build_narrative(
            pcr_oi, pcr_vol, signal, call_wall, put_wall, chain.spot_price
        )

        return PCRAnalysis(
            pcr_oi       = round(pcr_oi, 3),
            pcr_volume   = round(pcr_vol, 3),
            signal       = signal,
            narrative    = narrative,
            bullish_pct  = bullish_pct,
            call_oi_wall = call_wall,
            put_oi_wall  = put_wall,
        )

    def _classify(self, pcr: float) -> tuple[ChainSignalDirection, float]:
        """Map PCR value to signal direction and bullish percentage."""
        if pcr >= _EXTREMELY_BULLISH:
            return ChainSignalDirection.STRONGLY_BULLISH, 90.0
        elif pcr >= _BULLISH:
            return ChainSignalDirection.BULLISH, 70.0
        elif pcr >= _BEARISH:
            return ChainSignalDirection.NEUTRAL, 50.0
        elif pcr >= _EXTREMELY_BEARISH:
            return ChainSignalDirection.BEARISH, 30.0
        else:
            return ChainSignalDirection.STRONGLY_BEARISH, 10.0

    def _find_call_wall(self, chain: ChainSnapshot) -> float:
        """Strike with the highest Call OI above the spot price."""
        candidates = [
            s for s in chain.strikes
            if s.strike >= chain.spot_price and s.call_oi > 0
        ]
        if not candidates:
            return 0.0
        return max(candidates, key=lambda s: s.call_oi).strike

    def _find_put_wall(self, chain: ChainSnapshot) -> float:
        """Strike with the highest Put OI below the spot price."""
        candidates = [
            s for s in chain.strikes
            if s.strike <= chain.spot_price and s.put_oi > 0
        ]
        if not candidates:
            return 0.0
        return max(candidates, key=lambda s: s.put_oi).strike

    def _build_narrative(
        self,
        pcr_oi:    float,
        pcr_vol:   float,
        signal:    ChainSignalDirection,
        call_wall: float,
        put_wall:  float,
        spot:      float,
    ) -> str:
        parts = [f"PCR(OI)={pcr_oi:.2f}"]

        if signal == ChainSignalDirection.STRONGLY_BULLISH:
            parts.append("excessive put buying → contrarian BUY signal")
        elif signal == ChainSignalDirection.BULLISH:
            parts.append("put-heavy OI → bullish bias")
        elif signal == ChainSignalDirection.NEUTRAL:
            parts.append("balanced OI → no directional bias")
        elif signal == ChainSignalDirection.BEARISH:
            parts.append("call-heavy OI → bearish bias")
        else:
            parts.append("excessive call buying → contrarian SELL signal")

        if call_wall and spot:
            dist = round(call_wall - spot, 0)
            parts.append(f"Call Wall {call_wall:.0f} (+{dist:.0f} pts = resistance)")
        if put_wall and spot:
            dist = round(spot - put_wall, 0)
            parts.append(f"Put Wall {put_wall:.0f} (-{dist:.0f} pts = support)")

        return "; ".join(parts)

    def get_oi_concentration(
        self,
        chain: ChainSnapshot,
        n_strikes: int = 5,
    ) -> dict:
        """
        Returns the top-N strikes by OI for calls and puts separately.
        Useful for identifying key hedging levels.
        """
        sorted_calls = sorted(chain.strikes, key=lambda s: s.call_oi, reverse=True)
        sorted_puts  = sorted(chain.strikes, key=lambda s: s.put_oi,  reverse=True)

        return {
            "top_call_oi_strikes": [
                {"strike": s.strike, "call_oi": s.call_oi}
                for s in sorted_calls[:n_strikes]
            ],
            "top_put_oi_strikes":  [
                {"strike": s.strike, "put_oi": s.put_oi}
                for s in sorted_puts[:n_strikes]
            ],
        }

    def pcr_history_signal(self, pcr_values: list[float]) -> dict:
        """
        Analyze trend in PCR over time.
        Rising PCR with stable/falling price → accumulation signal.
        """
        if len(pcr_values) < 2:
            return {"trend": "INSUFFICIENT_DATA"}

        trend  = pcr_values[-1] - pcr_values[0]
        change = (pcr_values[-1] - pcr_values[-2]) / max(pcr_values[-2], 0.01)

        return {
            "current_pcr": round(pcr_values[-1], 3),
            "trend":        "RISING" if trend > 0.05 else "FALLING" if trend < -0.05 else "FLAT",
            "session_change_pct": round(change * 100, 2),
            "signal":       "ACCUMULATION" if trend > 0.1 else "DISTRIBUTION" if trend < -0.1 else "NEUTRAL",
        }
