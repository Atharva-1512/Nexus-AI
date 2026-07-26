"""
NEXUS AI — Chain Intelligence Engine (Module 5 — Master Orchestrator)

The Chain Engine coordinates all option chain analytics:
  1. Parses raw NSE option chain → ChainSnapshot
  2. Runs all analyzers (PCR, Max Pain, GEX, IV Skew, OI, S/R)
  3. Aggregates results into a single ChainSignal
  4. The ChainSignal feeds the Decision Engine with a 21% weighted score

Output signal:
  ChainSignal.direction   → BULLISH / BEARISH / NEUTRAL / STRONGLY_*
  ChainSignal.confidence  → 0–100 (how strong the combined signal is)
  ChainSignal.key_strikes → ATM, Max Pain, Call Wall, Put Wall, GEX Flip

Weights within the Chain Engine:
  PCR     → 30%
  OI      → 25%
  GEX     → 20%
  Max Pain→ 15%
  IV Skew → 10%
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from .gex_calculator           import GEXCalculator
from .iv_skew                  import IVSkewAnalyzer
from .max_pain                 import MaxPainCalculator
from .models                   import (
    ChainSignal, ChainSignalDirection, ChainSnapshot,
    IVSkewResult, MaxPainResult, PCRAnalysis, GEXResult,
)
from .oi_analyzer               import OIAnalyzer, SupportResistanceDetector
from .option_chain_parser       import OptionChainParser, build_synthetic_chain
from .pcr_analyzer              import PCRAnalyzer

logger = logging.getLogger(__name__)

# Internal signal weights (must sum to 1.0)
_WEIGHTS = {
    "pcr":      0.30,
    "oi":       0.25,
    "gex":      0.20,
    "max_pain": 0.15,
    "iv_skew":  0.10,
}


class ChainEngine:
    """
    Master orchestrator for all Option Chain Intelligence.

    Usage:
        engine = ChainEngine()

        # With live NSE data:
        signal = await engine.run("NIFTY")

        # With pre-fetched snapshot:
        signal = engine.analyze(chain_snapshot)
    """

    def __init__(self, lot_size: int = 75):
        self.lot_size   = lot_size
        self._parser    = OptionChainParser()
        self._pcr       = PCRAnalyzer()
        self._max_pain  = MaxPainCalculator()
        self._gex       = GEXCalculator()
        self._iv_skew   = IVSkewAnalyzer()
        self._oi        = OIAnalyzer()
        self._sr        = SupportResistanceDetector()

    def analyze(self, chain: ChainSnapshot) -> ChainSignal:
        """
        Run the full analytics pipeline on an already-parsed ChainSnapshot.

        Args:
            chain: Populated ChainSnapshot

        Returns:
            ChainSignal — complete option chain intelligence output
        """
        # ── Run all analyzers ──────────────────────────────────────────────────
        pcr_result  = self._pcr.analyze(chain)
        pain_result = self._max_pain.calculate(chain)
        gex_result  = self._gex.calculate(chain)
        iv_result   = self._iv_skew.analyze(chain)
        oi_result   = self._oi.analyze(chain)
        supports, resistances = self._sr.detect(chain)

        # ── Aggregate bullish score ────────────────────────────────────────────
        bullish_score = self._aggregate_score(
            pcr_result, pain_result, gex_result, iv_result, oi_result, chain
        )

        # ── Map score to direction ─────────────────────────────────────────────
        direction = self._score_to_direction(bullish_score)

        # ── Confidence = distance from 50 (neutral), scaled to 100 ────────────
        confidence = round(min(100.0, abs(bullish_score - 50) * 2), 1)

        # ── Key strikes summary ────────────────────────────────────────────────
        key_strikes = {
            "spot":      chain.spot_price,
            "atm":       chain.atm_strike,
            "max_pain":  pain_result.max_pain_strike,
            "call_wall": pcr_result.call_oi_wall,
            "put_wall":  pcr_result.put_oi_wall,
            "gex_flip":  gex_result.gex_flip_level,
        }

        # ── Narrative ──────────────────────────────────────────────────────────
        narrative = self._build_narrative(
            direction, bullish_score, pcr_result, pain_result,
            gex_result, oi_result, chain
        )

        logger.info(
            f"ChainEngine [{chain.underlying} {chain.expiry}]: "
            f"score={bullish_score:.1f}, direction={direction.value}, "
            f"confidence={confidence:.0f}%"
        )

        return ChainSignal(
            direction         = direction,
            confidence        = confidence,
            pcr               = pcr_result,
            max_pain          = pain_result,
            gex               = gex_result,
            iv_skew           = iv_result,
            support_levels    = supports,
            resistance_levels = resistances,
            key_strikes       = key_strikes,
            narrative         = narrative,
            timestamp         = datetime.now(timezone.utc),
        )

    def analyze_synthetic(
        self,
        spot:     float = 24350.0,
        expiry:   Optional[date] = None,
        atm_iv:   float = 14.0,
    ) -> ChainSignal:
        """
        Run full analysis on a synthetic chain. Useful for testing/demos.
        """
        chain = build_synthetic_chain(
            spot     = spot,
            expiry   = expiry,
            lot_size = self.lot_size,
            atm_iv   = atm_iv,
        )
        return self.analyze(chain)

    def fetch_and_analyze(
        self,
        symbol: str = "NIFTY",
        expiry: Optional[date] = None,
    ) -> Optional[ChainSignal]:
        """
        Fetch live NSE chain + run full analysis.

        Falls back to synthetic chain if NSE is unavailable.
        """
        chain = self._parser.fetch(symbol=symbol, expiry=expiry, lot_size=self.lot_size)
        if chain is None:
            logger.warning("NSE chain unavailable — using synthetic chain for demo")
            chain = build_synthetic_chain(lot_size=self.lot_size)
        return self.analyze(chain)

    # ─── Score Aggregation ────────────────────────────────────────────────────

    def _aggregate_score(
        self,
        pcr:      PCRAnalysis,
        pain:     MaxPainResult,
        gex:      GEXResult,
        iv:       IVSkewResult,
        oi:       "OIAnalysisResult",
        chain:    ChainSnapshot,
    ) -> float:
        """
        Weighted average of bullish scores from each analyzer.
        Returns 0–100 where 50 = neutral.
        """
        scores = {}

        # PCR score (0–100)
        scores["pcr"] = pcr.bullish_pct

        # OI score (0–100)
        scores["oi"] = oi.bullish_score

        # GEX score (0–100)
        # Positive GEX → range-bound → neutral/slight bullish
        # Negative GEX → trending → amplifies existing direction
        if gex.regime == "POSITIVE_GEX":
            scores["gex"] = 50.0  # Neutral/stabilising
        else:
            # In negative GEX, look at which direction chain is leaning
            scores["gex"] = 35.0  # Slightly bearish (volatility expansion = uncertainty)

        # Max Pain score (0–100)
        if pain.signal == "ABOVE_SPOT":
            scores["max_pain"] = 60.0   # Max pain above → gentle bullish pull
        elif pain.signal == "BELOW_SPOT":
            scores["max_pain"] = 40.0   # Max pain below → gentle bearish pull
        else:
            scores["max_pain"] = 50.0

        # IV Skew score (0–100)
        # Steep put skew → fear → bearish
        # Flat / reverse skew → complacency → slightly bullish
        if iv.skew_25d > 5.0:
            scores["iv_skew"] = 35.0    # High put premium → bearish fear
        elif iv.skew_25d > 2.0:
            scores["iv_skew"] = 45.0    # Normal skew
        elif iv.skew_25d < 0.0:
            scores["iv_skew"] = 65.0    # Call skew → bullish squeeze
        else:
            scores["iv_skew"] = 52.0    # Flat → neutral/slight bullish

        # Weighted sum
        total = sum(_WEIGHTS[k] * scores[k] for k in scores)
        return round(total, 2)

    @staticmethod
    def _score_to_direction(score: float) -> ChainSignalDirection:
        if score >= 72:   return ChainSignalDirection.STRONGLY_BULLISH
        if score >= 58:   return ChainSignalDirection.BULLISH
        if score >= 42:   return ChainSignalDirection.NEUTRAL
        if score >= 28:   return ChainSignalDirection.BEARISH
        return ChainSignalDirection.STRONGLY_BEARISH

    @staticmethod
    def _build_narrative(
        direction:  ChainSignalDirection,
        score:      float,
        pcr:        PCRAnalysis,
        pain:       MaxPainResult,
        gex:        GEXResult,
        oi:         "OIAnalysisResult",
        chain:      ChainSnapshot,
    ) -> str:
        lines = [
            f"Chain Signal: {direction.value} (score {score:.0f}/100)",
            f"PCR(OI)={pcr.pcr_oi:.2f} → {pcr.signal.value}",
            f"Max Pain={pain.max_pain_strike:.0f} ({pain.distance_from_spot:+.0f} pts from spot)",
            f"GEX={chain.total_gex:.2f} Cr → {gex.regime}",
            f"OI: {oi.narrative}",
        ]
        if chain.gex_flip_level:
            lines.append(f"GEX Flip Level: {chain.gex_flip_level:.0f}")
        return " | ".join(lines)


# ── Module-level singleton ─────────────────────────────────────────────────────
chain_engine = ChainEngine()
