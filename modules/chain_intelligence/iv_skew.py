"""
NEXUS AI — IV Skew Analyzer (Module 5)

IV Skew measures the difference in implied volatility between OTM puts
and OTM calls at the same delta (or equidistant strikes).

For NIFTY index options, put IV is almost ALWAYS higher than call IV
(negative skew / "smirk") because:
  1. Funds buy puts for portfolio protection
  2. Call selling is a common income strategy
  3. Market crashes faster than it rises ("tail risk premium")

Key metrics computed:
  - ATM IV             : Current market fear level (reference)
  - IV Skew (25-delta) : Put IV - Call IV at ~25 delta strikes
  - Skew slope         : Rate of change of IV per strike
  - Risk Reversal      : 25d Put IV - 25d Call IV (market standard)
  - Skew steepening    → Increasing downside fear → bearish
  - Skew flattening    → Decreasing downside fear → bullish setup
  - IV Smile           : Both wings elevated (straddle buying)

Interpretation:
  Skew > 5%    → Significant put premium, market nervous
  Skew 2–5%   → Normal put skew, healthy market
  Skew < 2%   → Low skew, complacent market (watch for reversal)
  Negative skew (call IV > put IV) → Extremely rare, suggests squeeze setup
"""

import logging
import math
from typing import Optional

from .models import ChainSnapshot, IVSkewResult

logger = logging.getLogger(__name__)


class IVSkewAnalyzer:
    """
    Analyzes the IV smile/skew from option chain data.

    Computes:
    - ATM IV
    - 25-delta approximate skew
    - Strike-by-strike IV table
    - Risk reversal proxy
    - Skew steepness and direction
    """

    def analyze(self, chain: ChainSnapshot) -> IVSkewResult:
        """
        Full IV skew analysis.

        Args:
            chain: ChainSnapshot with IV values per strike

        Returns:
            IVSkewResult with skew metrics and narrative
        """
        atm_iv = chain.atm_iv
        if atm_iv <= 0:
            atm_iv = self._estimate_atm_iv(chain)

        # Build IV table: all strikes with non-zero IV
        iv_table = self._build_iv_table(chain)

        # 25-delta skew: find strikes closest to 25-delta
        skew_25d, call_25d_iv, put_25d_iv = self._compute_25d_skew(chain)

        # Risk reversal (simple: OTM put IV - OTM call IV, equidistant from ATM)
        rr = self._compute_risk_reversal(chain, wing_offset=2)

        # Classify skew direction
        if skew_25d > 5.0:
            direction = "PUT_SKEW"
            narrative_part = f"steep put skew ({skew_25d:.1f}%) → elevated downside fear"
        elif skew_25d > 1.5:
            direction = "PUT_SKEW"
            narrative_part = f"normal put skew ({skew_25d:.1f}%) → healthy market"
        elif skew_25d < -1.0:
            direction = "CALL_SKEW"
            narrative_part = f"rare call skew ({skew_25d:.1f}%) → squeeze/bullish signal"
        else:
            direction = "FLAT"
            narrative_part = f"flat skew ({skew_25d:.1f}%) → complacency or balanced positioning"

        # Skew steepness
        slope = self._compute_skew_slope(chain)
        if abs(slope) > 0.3:
            slope_desc = f"steep slope ({slope:+.2f}% per strike)"
        else:
            slope_desc = f"moderate slope ({slope:+.2f}% per strike)"

        narrative = (
            f"ATM IV={atm_iv:.1f}%; {narrative_part}; "
            f"Risk Reversal={rr:+.2f}%; {slope_desc}"
        )

        logger.info(f"IV Skew [{chain.underlying}]: ATM={atm_iv:.1f}%, 25d skew={skew_25d:.2f}%")

        return IVSkewResult(
            atm_iv          = round(atm_iv, 2),
            skew_25d        = round(skew_25d, 3),
            skew_direction  = direction,
            iv_by_strike    = iv_table,
            risk_reversal   = round(rr, 3),
            narrative       = narrative,
        )

    def _build_iv_table(self, chain: ChainSnapshot) -> dict[float, dict]:
        """Build per-strike IV table for charting."""
        table = {}
        for s in chain.strikes:
            if s.call_iv > 0 or s.put_iv > 0:
                table[s.strike] = {
                    "call_iv":  round(s.call_iv, 2),
                    "put_iv":   round(s.put_iv, 2),
                    "skew":     round(s.put_iv - s.call_iv, 2),
                    "avg_iv":   round((s.call_iv + s.put_iv) / 2, 2)
                                if s.call_iv and s.put_iv else round(s.call_iv or s.put_iv, 2),
                }
        return table

    def _compute_25d_skew(self, chain: ChainSnapshot) -> tuple[float, float, float]:
        """
        Compute skew at approximately 25-delta strikes.

        Uses delta values if available, otherwise falls back to
        selecting strikes ≈2 intervals from ATM.
        """
        # Try delta-based selection
        call_25d = self._find_strike_by_delta(chain, target_delta=0.25, option_type="call")
        put_25d  = self._find_strike_by_delta(chain, target_delta=-0.25, option_type="put")

        call_iv = call_25d.call_iv if call_25d and call_25d.call_iv > 0 else 0.0
        put_iv  = put_25d.put_iv   if put_25d  and put_25d.put_iv  > 0 else 0.0

        if call_iv and put_iv:
            return round(put_iv - call_iv, 3), call_iv, put_iv

        # Fallback: equidistant strikes ±2 intervals from ATM
        return self._compute_risk_reversal(chain, wing_offset=2), call_iv, put_iv

    def _find_strike_by_delta(self, chain, target_delta: float, option_type: str):
        """Find the strike closest to a target delta value."""
        best = None
        best_dist = float("inf")
        for s in chain.strikes:
            delta = s.call_delta if option_type == "call" else s.put_delta
            if delta == 0.0:
                continue
            dist = abs(delta - target_delta)
            if dist < best_dist:
                best_dist = dist
                best = s
        return best

    def _compute_risk_reversal(self, chain: ChainSnapshot, wing_offset: int = 2) -> float:
        """
        Simple risk reversal: OTM put IV - OTM call IV at equidistant strikes.

        wing_offset: Number of strikes above/below ATM to use.
        """
        strikes_sorted = sorted(chain.strikes, key=lambda s: s.strike)
        atm_idx = min(
            range(len(strikes_sorted)),
            key=lambda i: abs(strikes_sorted[i].strike - chain.spot_price)
        )
        otm_call_idx = min(atm_idx + wing_offset, len(strikes_sorted) - 1)
        otm_put_idx  = max(atm_idx - wing_offset, 0)

        otm_call_iv = strikes_sorted[otm_call_idx].call_iv
        otm_put_iv  = strikes_sorted[otm_put_idx].put_iv

        if otm_call_iv and otm_put_iv:
            return round(otm_put_iv - otm_call_iv, 3)
        return 0.0

    def _compute_skew_slope(self, chain: ChainSnapshot) -> float:
        """
        Compute the slope of the IV curve (IV per 100-pt strike move).
        Positive slope → IV rises as strike falls (put skew = normal).
        """
        iv_points = [
            (s.strike, s.put_iv if s.strike < chain.spot_price else s.call_iv)
            for s in chain.strikes
            if (s.put_iv > 0 or s.call_iv > 0)
        ]
        if len(iv_points) < 3:
            return 0.0

        # Simple linear regression
        n     = len(iv_points)
        x_arr = [p[0] for p in iv_points]
        y_arr = [p[1] for p in iv_points]
        x_mean = sum(x_arr) / n
        y_mean = sum(y_arr) / n
        denom  = sum((x - x_mean)**2 for x in x_arr)
        if denom == 0:
            return 0.0
        slope = sum((x_arr[i] - x_mean) * (y_arr[i] - y_mean) for i in range(n)) / denom
        # Convert to IV change per 100 points
        return round(slope * 100, 4)

    def _estimate_atm_iv(self, chain: ChainSnapshot) -> float:
        """Estimate ATM IV if not set by averaging nearby strikes."""
        nearby = chain.strikes_near_atm(n=3)
        ivs    = []
        for s in nearby:
            if s.call_iv > 0: ivs.append(s.call_iv)
            if s.put_iv  > 0: ivs.append(s.put_iv)
        return round(sum(ivs) / len(ivs), 2) if ivs else 14.0
