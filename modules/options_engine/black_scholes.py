"""
NEXUS AI — Black-Scholes Options Pricer (Module 3)

Analytical closed-form solution for European option pricing.
The fastest and most commonly used model for first approximations.

Assumptions:
- Constant volatility (log-normal price distribution)
- European exercise only (suitable for NIFTY index options)
- No dividends (or continuous dividend yield)
- Constant risk-free rate

References:
- Black, F. & Scholes, M. (1973). The Pricing of Options and Corporate Liabilities.
- Merton, R. (1973). Theory of Rational Option Pricing.
"""

import math
import logging
from scipy.stats import norm

from .models import OptionSpec, OptionType, PricingResult, Greeks

logger = logging.getLogger(__name__)

# Standard normal CDF and PDF
_N  = norm.cdf
_n  = norm.pdf


class BlackScholesPricer:
    """
    Black-Scholes-Merton option pricing engine.

    Provides:
    - Theoretical option price
    - Complete first-order Greeks (Delta, Gamma, Theta, Vega, Rho)
    - Second-order Greeks (Vomma, Vanna, Charm, Color, Speed, Zomma, Ultima)
    - Implied Volatility solver (Newton-Raphson)
    """

    @staticmethod
    def _d1_d2(spec: OptionSpec) -> tuple[float, float]:
        """Compute d1 and d2 — the core Black-Scholes intermediaries."""
        S  = spec.underlying_price
        K  = spec.strike_price
        T  = max(spec.time_to_expiry, 1e-9)   # Prevent division by zero
        r  = spec.risk_free_rate
        q  = spec.dividend_yield
        σ  = max(spec.implied_volatility, 1e-9)

        d1 = (math.log(S / K) + (r - q + 0.5 * σ ** 2) * T) / (σ * math.sqrt(T))
        d2 = d1 - σ * math.sqrt(T)
        return d1, d2

    def price(self, spec: OptionSpec) -> PricingResult:
        """
        Calculate the theoretical option price using Black-Scholes.

        Args:
            spec: Full option specification

        Returns:
            PricingResult with price and all Greeks
        """
        S  = spec.underlying_price
        K  = spec.strike_price
        T  = max(spec.time_to_expiry, 1e-9)
        r  = spec.risk_free_rate
        q  = spec.dividend_yield
        σ  = max(spec.implied_volatility, 1e-9)

        d1, d2 = self._d1_d2(spec)

        discount     = math.exp(-r * T)
        fwd_discount = math.exp(-q * T)

        # ── Option Price ────────────────────────────────────────────────────
        if spec.option_type == OptionType.CALL:
            price = S * fwd_discount * _N(d1) - K * discount * _N(d2)
        else:
            price = K * discount * _N(-d2) - S * fwd_discount * _N(-d1)

        # ── Greeks ──────────────────────────────────────────────────────────
        phi  = _n(d1)                          # Standard normal PDF at d1
        sqrt_T = math.sqrt(T)

        # Delta
        if spec.option_type == OptionType.CALL:
            delta = fwd_discount * _N(d1)
        else:
            delta = -fwd_discount * _N(-d1)

        # Gamma (same for call and put)
        gamma = fwd_discount * phi / (S * σ * sqrt_T)

        # Theta (per calendar day, not per year)
        if spec.option_type == OptionType.CALL:
            theta = (
                -S * fwd_discount * phi * σ / (2 * sqrt_T)
                - r * K * discount * _N(d2)
                + q * S * fwd_discount * _N(d1)
            ) / 365.0
        else:
            theta = (
                -S * fwd_discount * phi * σ / (2 * sqrt_T)
                + r * K * discount * _N(-d2)
                - q * S * fwd_discount * _N(-d1)
            ) / 365.0

        # Vega (per 1% change in IV)
        vega = S * fwd_discount * phi * sqrt_T / 100.0

        # Rho (per 1% change in risk-free rate)
        if spec.option_type == OptionType.CALL:
            rho = K * T * discount * _N(d2) / 100.0
        else:
            rho = -K * T * discount * _N(-d2) / 100.0

        # ── Second-Order Greeks ─────────────────────────────────────────────
        vomma  = vega * d1 * d2 / σ
        vanna  = -fwd_discount * phi * d2 / σ
        charm  = (
            -fwd_discount * phi * (
                2 * (r - q) * T - d2 * σ * sqrt_T
            ) / (2 * T * σ * sqrt_T)
        )
        color  = (
            -fwd_discount * phi / (2 * S * T * σ * sqrt_T)
            * (2 * q * T + 1 + d1 * (2 * (r - q) * T - d2 * σ * sqrt_T) / (σ * sqrt_T))
        )
        speed  = -gamma / S * (d1 / (σ * sqrt_T) + 1)
        zomma  = gamma * (d1 * d2 - 1) / σ
        ultima = (
            -vega / (σ ** 2)
            * (d1 * d2 * (1 - d1 * d2) + d1 ** 2 + d2 ** 2)
        )

        greeks = Greeks(
            delta=round(delta, 6),
            gamma=round(gamma, 6),
            theta=round(theta, 6),
            vega=round(vega, 6),
            rho=round(rho, 6),
            vomma=round(vomma, 6),
            vanna=round(vanna, 6),
            charm=round(charm, 6),
            color=round(color, 6),
            speed=round(speed, 6),
            zomma=round(zomma, 6),
            ultima=round(ultima, 6),
        )

        logger.debug(
            f"BS Price: {spec.option_type.value} K={K} T={T:.4f}y "
            f"σ={σ:.1%} → Price={price:.2f} Δ={delta:.4f}"
        )

        return PricingResult(
            spec=spec,
            model="black_scholes",
            theoretical_price=round(max(price, 0.0), 2),
            intrinsic_value=0.0,   # Set in __post_init__
            extrinsic_value=0.0,
            time_value=0.0,
            greeks=greeks,
        )

    def implied_volatility(
        self,
        market_price: float,
        spec: OptionSpec,
        tolerance: float = 1e-6,
        max_iterations: int = 100,
    ) -> float:
        """
        Newton-Raphson IV solver.

        Finds the IV that makes BS price = market price.

        Args:
            market_price  : Observed market price of the option
            spec          : Option spec (IV field is initial guess, will be overwritten)
            tolerance     : Convergence tolerance
            max_iterations: Maximum Newton-Raphson iterations

        Returns:
            Implied volatility (annual, decimal). Returns NaN on failure.
        """
        # Initial guess using Brenner-Subrahmanyam approximation
        S, K, T = spec.underlying_price, spec.strike_price, spec.time_to_expiry
        σ = math.sqrt(2 * math.pi / T) * market_price / S  # Initial estimate

        for _ in range(max_iterations):
            spec_trial = OptionSpec(
                underlying_price=S,
                strike_price=K,
                time_to_expiry=T,
                risk_free_rate=spec.risk_free_rate,
                implied_volatility=σ,
                option_type=spec.option_type,
                dividend_yield=spec.dividend_yield,
            )
            result = self.price(spec_trial)
            diff = result.theoretical_price - market_price

            if abs(diff) < tolerance:
                return round(σ, 6)

            # Newton step: σ_new = σ - f(σ) / f'(σ)
            # f'(σ) = vega * 100 (since vega is per 1%)
            vega_raw = result.greeks.vega * 100.0
            if abs(vega_raw) < 1e-10:
                break
            σ = σ - diff / vega_raw
            σ = max(0.001, min(σ, 10.0))   # Clamp to reasonable bounds

        logger.warning(f"IV solver did not converge for market_price={market_price}")
        return float("nan")
