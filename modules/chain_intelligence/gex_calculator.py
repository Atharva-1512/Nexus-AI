"""
NEXUS AI — Gamma Exposure (GEX) Calculator (Module 5)

GEX measures the total gamma held by market makers (dealers),
scaled by OI and spot price. It reveals the HEDGING PRESSURE dealers
exert on the market — which strongly affects intraday volatility.

Formula (per strike):
    GEX_call = +Gamma × Call_OI × Lot_Size × Spot²
    GEX_put  = -Gamma × Put_OI  × Lot_Size × Spot²
    Net_GEX  = GEX_call + GEX_put

Why it matters:
    Positive GEX  → Dealers are net LONG gamma.
                    They hedge by SELLING into rallies, BUYING into dips.
                    Effect: Price-dampening. Low-volatility, range-bound market.

    Negative GEX  → Dealers are net SHORT gamma.
                    They hedge by BUYING into rallies, SELLING into dips.
                    Effect: Price-amplifying. Trending, volatile market.

    GEX Flip Level → Strike where total GEX crosses zero.
                     Breaking the GEX flip = volatility expansion signal.

In practice for NIFTY:
    - Total positive GEX → expect chop/range
    - Total negative GEX → expect trending moves
    - NIFTY near GEX flip = key inflection zone
"""

import logging
import math
from typing import Optional

from .models import ChainSnapshot, GEXResult

logger = logging.getLogger(__name__)


class GEXCalculator:
    """
    Computes Gamma Exposure from the option chain.

    If per-strike gamma values are missing (common for NSE data),
    falls back to a Black-Scholes approximation of gamma.

    Usage:
        calc = GEXCalculator()
        result = calc.calculate(chain)
        print(result.total_gex, result.regime, result.gex_flip_level)
    """

    def calculate(self, chain: ChainSnapshot) -> GEXResult:
        """
        Compute GEX for every strike and aggregate.

        Args:
            chain: ChainSnapshot with OI and gamma data per strike

        Returns:
            GEXResult with per-strike GEX, total GEX, flip level, and regime
        """
        spot     = chain.spot_price
        lot_size = chain.lot_size
        gex_by_strike: dict[float, float] = {}
        total_call_gex = 0.0
        total_put_gex  = 0.0

        for s in chain.strikes:
            # Use provided gamma; fall back to BS approximation if zero
            gamma = s.call_gamma if s.call_gamma > 0 else self._approx_gamma(
                spot=spot, strike=s.strike,
                atm_iv=chain.atm_call_iv / 100.0,
                dte_years=max(chain.days_to_expiry / 365.0, 1 / 365),
            )

            # GEX in rupee-crore equivalent (divide by 1e7 for readability)
            call_gex = +gamma * s.call_oi * lot_size * spot ** 2 / 1e7
            put_gex  = -gamma * s.put_oi  * lot_size * spot ** 2 / 1e7

            net_gex  = call_gex + put_gex
            gex_by_strike[s.strike] = round(net_gex, 4)

            # Write back to strike object for downstream use
            s.gex_call = round(call_gex, 4)
            s.gex_put  = round(put_gex, 4)
            s.net_gex  = round(net_gex, 4)

            total_call_gex += call_gex
            total_put_gex  += put_gex

        total_gex = total_call_gex + total_put_gex

        # Find GEX flip level (zero-crossing)
        gex_flip = self._find_flip_level(gex_by_strike, spot)

        # Update ChainSnapshot
        chain.total_gex      = round(total_gex, 4)
        chain.gex_flip_level = gex_flip

        regime    = "POSITIVE_GEX" if total_gex >= 0 else "NEGATIVE_GEX"
        narrative = self._build_narrative(total_gex, regime, gex_flip, spot)

        logger.info(
            f"GEX [{chain.underlying}]: total={total_gex:.2f} Cr, "
            f"regime={regime}, flip={gex_flip}"
        )

        return GEXResult(
            total_gex      = round(total_gex, 4),
            gex_by_strike  = gex_by_strike,
            gex_flip_level = gex_flip,
            regime         = regime,
            narrative      = narrative,
            call_gex       = round(total_call_gex, 4),
            put_gex        = round(total_put_gex, 4),
        )

    @staticmethod
    def _approx_gamma(
        spot: float, strike: float, atm_iv: float, dte_years: float
    ) -> float:
        """
        Black-Scholes gamma approximation.
        Used when per-strike gamma is not available from NSE data.
        """
        if atm_iv <= 0 or dte_years <= 0:
            return 0.0
        try:
            r   = 0.065
            d1  = (math.log(spot / strike) + (r + 0.5 * atm_iv**2) * dte_years) / (
                atm_iv * math.sqrt(dte_years)
            )
            phi = math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi)   # PDF
            gamma = phi / (spot * atm_iv * math.sqrt(dte_years))
            return max(0.0, gamma)
        except (ValueError, ZeroDivisionError):
            return 0.0

    @staticmethod
    def _find_flip_level(
        gex_by_strike: dict[float, float], spot: float
    ) -> Optional[float]:
        """
        Find the strike where cumulative GEX crosses zero.

        Works by summing GEX from highest to lowest strike and
        finding the zero-crossing point.
        """
        strikes_sorted = sorted(gex_by_strike.keys(), reverse=True)
        if not strikes_sorted:
            return None

        cum_gex = 0.0
        prev_strike = None
        for k in strikes_sorted:
            prev_gex    = cum_gex
            cum_gex    += gex_by_strike[k]
            if prev_strike is not None and prev_gex * cum_gex < 0:
                # Zero-crossing detected between prev_strike and k
                # Linear interpolation
                if abs(cum_gex - prev_gex) > 0:
                    flip = prev_strike + (k - prev_strike) * (
                        -prev_gex / (cum_gex - prev_gex)
                    )
                    return round(flip, 2)
            prev_strike = k

        return None

    @staticmethod
    def _build_narrative(
        total_gex: float, regime: str, flip: Optional[float], spot: float
    ) -> str:
        parts = []

        if regime == "POSITIVE_GEX":
            parts.append(
                f"Total GEX +{total_gex:.1f} Cr → dealers LONG gamma → "
                "expect range-bound, low-volatility price action"
            )
        else:
            parts.append(
                f"Total GEX {total_gex:.1f} Cr → dealers SHORT gamma → "
                "expect trending, volatile price action"
            )

        if flip and spot:
            dist = round(flip - spot, 0)
            direction = "above" if dist > 0 else "below"
            parts.append(
                f"GEX Flip at {flip:.0f} ({dist:+.0f} pts {direction} spot) — "
                "break of flip = volatility expansion"
            )

        return "; ".join(parts)

    def net_gex_profile(self, chain: ChainSnapshot) -> list[dict]:
        """
        Return sorted GEX profile for charting (strike vs net GEX).
        Positive bars = call GEX dominates (dampening).
        Negative bars = put GEX dominates (amplifying).
        """
        return sorted(
            [
                {
                    "strike":   s.strike,
                    "net_gex":  s.net_gex,
                    "call_gex": s.gex_call,
                    "put_gex":  s.gex_put,
                }
                for s in chain.strikes
            ],
            key=lambda x: x["strike"],
        )
