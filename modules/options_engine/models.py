"""
NEXUS AI — Options Data Models (Module 3)

Shared Pydantic + dataclass models for the entire options engine.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional



class OptionType(str, Enum):
    CALL = "CE"
    PUT  = "PE"


class ExerciseStyle(str, Enum):
    EUROPEAN = "european"   # NIFTY options are European
    AMERICAN = "american"


@dataclass
class OptionSpec:
    """
    Full specification of an option contract for pricing.

    All prices in INR. Time in years.
    """
    underlying_price: float      # Current NIFTY spot price
    strike_price: float          # Option strike price
    time_to_expiry: float        # In years (e.g. 7 days = 7/365 = 0.0192)
    risk_free_rate: float        # Annual, decimal (e.g. 0.065 for 6.5%)
    implied_volatility: float    # Annual, decimal (e.g. 0.15 for 15%)
    option_type: OptionType      # CE or PE
    exercise_style: ExerciseStyle = ExerciseStyle.EUROPEAN
    dividend_yield: float = 0.0  # For index options, typically 0


@dataclass
class Greeks:
    """Complete first and second-order Greeks."""
    # First-order
    delta: float = 0.0    # dV/dS  — price sensitivity to underlying
    gamma: float = 0.0    # d²V/dS² — delta sensitivity to underlying
    theta: float = 0.0    # dV/dt  — time decay (per day)
    vega:  float = 0.0    # dV/dσ  — IV sensitivity (per 1% IV move)
    rho:   float = 0.0    # dV/dr  — rate sensitivity

    # Second-order (volatility surface)
    vomma:  float = 0.0   # d²V/dσ² — vega convexity
    vanna:  float = 0.0   # d²V/(dS·dσ) — delta/vega cross
    charm:  float = 0.0   # d²V/(dS·dt) — delta decay
    color:  float = 0.0   # d³V/(dS²·dt) — gamma decay
    speed:  float = 0.0   # d³V/dS³ — gamma curvature
    zomma:  float = 0.0   # d³V/(dS²·dσ) — gamma/vega cross
    ultima: float = 0.0   # d³V/dσ³ — vomma/vega sensitivity


@dataclass
class PricingResult:
    """Result from any options pricing model."""
    spec: OptionSpec
    model: str                   # e.g. "black_scholes", "heston"
    theoretical_price: float
    intrinsic_value: float
    extrinsic_value: float
    time_value: float
    greeks: Optional[Greeks] = None
    priced_at: datetime = None

    def __post_init__(self):
        if self.priced_at is None:
            self.priced_at = datetime.now(timezone.utc)
        self.intrinsic_value = max(
            0.0,
            (self.spec.underlying_price - self.spec.strike_price)
            if self.spec.option_type == OptionType.CALL
            else (self.spec.strike_price - self.spec.underlying_price)
        )
        self.extrinsic_value = max(0.0, self.theoretical_price - self.intrinsic_value)
        self.time_value = self.extrinsic_value
