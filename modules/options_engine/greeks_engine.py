"""
NEXUS AI — Greeks Engine (Module 4)

Centralised service for computing all Greeks from live option chain data.
Wraps the Black-Scholes pricer and will add Heston/SABR in Phase 3.
"""

import logging
from typing import Optional

from .black_scholes import BlackScholesPricer
from .models import Greeks, OptionSpec, OptionType, PricingResult

logger = logging.getLogger(__name__)


class GreeksEngine:
    """
    Computes and stores Greeks for individual options and full option chains.

    Uses Black-Scholes as the default engine.
    Phase 3 will add Heston and SABR as alternative engines.
    """

    def __init__(self, risk_free_rate: float = 0.065):
        """
        Args:
            risk_free_rate: RBI repo rate as decimal (default 6.5%)
        """
        self.risk_free_rate = risk_free_rate
        self._bs = BlackScholesPricer()

    def compute(
        self,
        underlying_price: float,
        strike: float,
        time_to_expiry: float,
        iv: float,
        option_type: str,          # "CE" or "PE"
        dividend_yield: float = 0.0,
    ) -> PricingResult:
        """
        Compute full Greeks for a single option contract.

        Args:
            underlying_price: NIFTY spot price
            strike          : Strike price
            time_to_expiry  : Time to expiry in years
            iv              : Implied volatility (decimal, e.g. 0.15 for 15%)
            option_type     : "CE" (call) or "PE" (put)
            dividend_yield  : Continuous dividend yield (typically 0 for NIFTY)

        Returns:
            PricingResult with theoretical price and all 12 Greeks
        """
        spec = OptionSpec(
            underlying_price=underlying_price,
            strike_price=strike,
            time_to_expiry=max(time_to_expiry, 1 / (365 * 24)),  # min 1 hour
            risk_free_rate=self.risk_free_rate,
            implied_volatility=max(iv, 0.01),
            option_type=OptionType.CALL if option_type.upper() == "CE" else OptionType.PUT,
            dividend_yield=dividend_yield,
        )
        return self._bs.price(spec)

    def bulk_compute(
        self,
        underlying_price: float,
        strikes: list[float],
        time_to_expiry: float,
        ivs: list[float],
        option_type: str,
    ) -> list[PricingResult]:
        """
        Compute Greeks for a list of strikes (e.g. an option chain).

        Args:
            underlying_price: NIFTY spot
            strikes         : List of strike prices
            time_to_expiry  : Single time to expiry (same for all)
            ivs             : Per-strike IVs (must match length of strikes)
            option_type     : "CE" or "PE"

        Returns:
            List of PricingResult objects in same order as strikes
        """
        assert len(strikes) == len(ivs), "strikes and ivs must have same length"

        results = []
        for strike, iv in zip(strikes, ivs):
            try:
                result = self.compute(
                    underlying_price=underlying_price,
                    strike=strike,
                    time_to_expiry=time_to_expiry,
                    iv=iv,
                    option_type=option_type,
                )
                results.append(result)
            except Exception as e:
                logger.warning(
                    f"Greeks computation failed for K={strike}, IV={iv:.2%}: {e}"
                )
                results.append(None)

        return results

    def get_atm_strike(self, spot: float, strikes: list[float]) -> float:
        """Returns the ATM (At-The-Money) strike closest to spot."""
        return min(strikes, key=lambda k: abs(k - spot))

    def classify_moneyness(
        self, spot: float, strike: float, option_type: str
    ) -> str:
        """
        Classify option as ATM / ITM / OTM.

        Returns:
            "ATM" | "ITM" | "OTM"
        """
        pct_diff = (strike - spot) / spot

        if abs(pct_diff) <= 0.005:  # ±0.5%
            return "ATM"

        if option_type.upper() == "CE":
            return "ITM" if pct_diff < 0 else "OTM"
        else:
            return "ITM" if pct_diff > 0 else "OTM"
