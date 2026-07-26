"""
NEXUS AI — Max Pain Calculator (Module 5)

Max Pain Theory:
  On expiry day, the underlying tends to close near the strike price
  where the MAXIMUM number of option buyers lose money
  (i.e., where option sellers / writers gain the most).

Algorithm:
  For each candidate strike K:
    total_pain(K) = Σ [max(0, K - Ci) × call_OI_i]    (call buyers lose if spot < strike)
                 + Σ [max(0, Pi - K) × put_OI_i]     (put buyers lose if spot > strike)
  Max Pain = strike with MINIMUM total_pain
  (buyers lose most → writers gain most)

Important notes:
  - Max Pain is most reliable within 2–3 days of expiry
  - Max Pain effect weakens for monthly expiries
  - It is a gravitational level, not a hard target
  - Works best when there's high OI concentration
"""

import logging
from typing import Optional

from .models import ChainSnapshot, MaxPainResult

logger = logging.getLogger(__name__)


class MaxPainCalculator:
    """
    Computes Max Pain for a given option chain.

    Usage:
        calc = MaxPainCalculator()
        result = calc.calculate(chain)
        print(result.max_pain_strike, result.distance_from_spot)
    """

    def calculate(self, chain: ChainSnapshot) -> MaxPainResult:
        """
        Compute Max Pain for the given chain snapshot.

        Args:
            chain: ChainSnapshot with populated call_oi and put_oi per strike

        Returns:
            MaxPainResult with pain table and signal
        """
        strikes = sorted(chain.strikes, key=lambda s: s.strike)
        if not strikes:
            return MaxPainResult(
                max_pain_strike=chain.spot_price,
                pain_table={},
                distance_from_spot=0.0,
                distance_pct=0.0,
                signal="UNKNOWN",
            )

        strike_prices = [s.strike for s in strikes]
        pain_table: dict[float, float] = {}

        for candidate in strike_prices:
            total_pain = 0.0
            for s in strikes:
                # Call buyers lose when spot (candidate) < strike
                # i.e., call is OTM — call buyer paid premium but option expires worthless
                call_pain = max(0.0, s.strike - candidate) * s.call_oi

                # Put buyers lose when spot (candidate) > strike
                # i.e., put is OTM
                put_pain  = max(0.0, candidate - s.strike) * s.put_oi

                total_pain += call_pain + put_pain

            pain_table[candidate] = round(total_pain, 0)

        # Max Pain = strike with MINIMUM total pain (buyers lose the most)
        max_pain_strike = min(pain_table, key=pain_table.get)

        distance        = round(max_pain_strike - chain.spot_price, 2)
        distance_pct    = round(distance / chain.spot_price * 100, 3)

        if distance > chain.spot_price * 0.002:
            signal = "ABOVE_SPOT"   # Max pain above → gentle upward pull
        elif distance < -chain.spot_price * 0.002:
            signal = "BELOW_SPOT"   # Max pain below → gentle downward pull
        else:
            signal = "AT_SPOT"      # Max pain at spot → balanced

        # Annotate each OptionStrike with its pain contribution
        for s in strikes:
            s.pain_call  = pain_table.get(s.strike, 0.0)
            s.pain_put   = pain_table.get(s.strike, 0.0)
            s.total_pain = s.pain_call + s.pain_put

        logger.info(
            f"Max Pain [{chain.underlying} {chain.expiry}]: "
            f"strike={max_pain_strike}, spot={chain.spot_price}, "
            f"distance={distance:+.0f} pts ({distance_pct:+.2f}%)"
        )

        return MaxPainResult(
            max_pain_strike  = max_pain_strike,
            pain_table       = pain_table,
            distance_from_spot = distance,
            distance_pct     = distance_pct,
            signal           = signal,
        )

    def max_pain_reliability(self, chain: ChainSnapshot) -> dict:
        """
        Assess how reliable the Max Pain signal is for this expiry.

        Reliability factors:
        - Days to expiry (< 3 days → high reliability)
        - OI concentration (higher = more reliable)
        - Total OI vs historical average

        Returns:
            Dict with reliability score (0–100) and reasoning
        """
        dte = chain.days_to_expiry

        # DTE component: most reliable in last 3 days
        if dte == 0:
            dte_score = 100
        elif dte <= 1:
            dte_score = 85
        elif dte <= 2:
            dte_score = 70
        elif dte <= 5:
            dte_score = 50
        else:
            dte_score = 25

        # OI concentration: higher Herfindahl index = more concentrated
        total_oi = chain.total_call_oi + chain.total_put_oi
        if total_oi > 0:
            oi_shares = [
                (s.total_oi / total_oi) ** 2
                for s in chain.strikes
                if s.total_oi > 0
            ]
            hhi = sum(oi_shares)
            conc_score = min(100, hhi * 1000)
        else:
            conc_score = 0

        reliability = int(0.7 * dte_score + 0.3 * conc_score)

        if reliability >= 70:
            label = "HIGH"
        elif reliability >= 40:
            label = "MODERATE"
        else:
            label = "LOW"

        return {
            "reliability_score": reliability,
            "reliability":       label,
            "days_to_expiry":    dte,
            "dte_score":         dte_score,
            "concentration_score": round(conc_score, 1),
            "note": "Max Pain most reliable within 3 days of expiry",
        }
