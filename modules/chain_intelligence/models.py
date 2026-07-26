"""
NEXUS AI — Option Chain Intelligence — Data Models (Module 5)

Core dataclasses for the entire option chain pipeline.
All other chain modules consume/produce these types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional


# ─── Enums ────────────────────────────────────────────────────────────────────

class OptionType(str, Enum):
    CALL = "CE"
    PUT  = "PE"


class OIBuildType(str, Enum):
    """Classifies price + OI change combinations."""
    LONG_BUILDUP    = "LONG_BUILDUP"      # Price ↑ + OI ↑  → fresh longs added
    LONG_UNWINDING  = "LONG_UNWINDING"    # Price ↓ + OI ↓  → longs exiting
    SHORT_BUILDUP   = "SHORT_BUILDUP"     # Price ↓ + OI ↑  → fresh shorts added
    SHORT_COVERING  = "SHORT_COVERING"    # Price ↑ + OI ↓  → shorts covering
    NEUTRAL         = "NEUTRAL"           # No significant change


class ChainSignalDirection(str, Enum):
    BULLISH         = "BULLISH"
    BEARISH         = "BEARISH"
    NEUTRAL         = "NEUTRAL"
    STRONGLY_BULLISH = "STRONGLY_BULLISH"
    STRONGLY_BEARISH = "STRONGLY_BEARISH"


# ─── Per-Strike Data ──────────────────────────────────────────────────────────

@dataclass
class OptionStrike:
    """
    Full data for one strike price in the option chain.
    Contains both CE (Call) and PE (Put) data.
    """
    strike:             float
    expiry:             date

    # Call (CE) fields
    call_oi:            int   = 0
    call_oi_change:     int   = 0
    call_volume:        int   = 0
    call_iv:            float = 0.0    # Implied Volatility (%)
    call_ltp:           float = 0.0    # Last Traded Price
    call_bid:           float = 0.0
    call_ask:           float = 0.0
    call_delta:         float = 0.0
    call_gamma:         float = 0.0
    call_theta:         float = 0.0
    call_vega:          float = 0.0

    # Put (PE) fields
    put_oi:             int   = 0
    put_oi_change:      int   = 0
    put_volume:         int   = 0
    put_iv:             float = 0.0
    put_ltp:            float = 0.0
    put_bid:            float = 0.0
    put_ask:            float = 0.0
    put_delta:          float = 0.0
    put_gamma:          float = 0.0
    put_theta:          float = 0.0
    put_vega:           float = 0.0

    # Derived (computed by chain engine)
    pcr_oi:             float = 0.0    # put_oi / call_oi
    total_oi:           int   = 0      # call_oi + put_oi
    iv_skew:            float = 0.0    # put_iv - call_iv
    gex_call:           float = 0.0    # Gamma Exposure from calls
    gex_put:            float = 0.0    # Gamma Exposure from puts
    net_gex:            float = 0.0    # gex_call - gex_put
    oi_build_call:      OIBuildType = OIBuildType.NEUTRAL
    oi_build_put:       OIBuildType = OIBuildType.NEUTRAL
    pain_call:          float = 0.0    # Max Pain contribution from calls
    pain_put:           float = 0.0    # Max Pain contribution from puts
    total_pain:         float = 0.0

    @property
    def is_atm(self, spot: float = 0.0) -> bool:
        """Returns True if this is the ATM strike (requires context)."""
        return False  # Set externally

    def to_dict(self) -> dict:
        return {
            "strike":           self.strike,
            "expiry":           self.expiry.isoformat(),
            "call_oi":          self.call_oi,
            "call_oi_change":   self.call_oi_change,
            "call_volume":      self.call_volume,
            "call_iv":          self.call_iv,
            "call_ltp":         self.call_ltp,
            "put_oi":           self.put_oi,
            "put_oi_change":    self.put_oi_change,
            "put_volume":       self.put_volume,
            "put_iv":           self.put_iv,
            "put_ltp":          self.put_ltp,
            "pcr_oi":           round(self.pcr_oi, 4),
            "total_oi":         self.total_oi,
            "iv_skew":          round(self.iv_skew, 4),
            "net_gex":          round(self.net_gex, 2),
            "oi_build_call":    self.oi_build_call.value,
            "oi_build_put":     self.oi_build_put.value,
            "total_pain":       round(self.total_pain, 2),
        }


# ─── Full Chain Snapshot ──────────────────────────────────────────────────────

@dataclass
class ChainSnapshot:
    """
    Complete option chain snapshot for a single expiry.
    This is the main object passed through the Phase 3 analytics pipeline.
    """
    underlying:         str             # "NIFTY"
    spot_price:         float
    expiry:             date
    timestamp:          datetime
    strikes:            list[OptionStrike] = field(default_factory=list)
    lot_size:           int = 75        # NIFTY lot size

    # Aggregates (computed by chain engine)
    total_call_oi:      int   = 0
    total_put_oi:       int   = 0
    total_call_volume:  int   = 0
    total_put_volume:   int   = 0
    pcr_oi:             float = 0.0
    pcr_volume:         float = 0.0
    max_pain:           float = 0.0
    atm_strike:         float = 0.0
    atm_call_iv:        float = 0.0
    atm_put_iv:         float = 0.0
    total_gex:          float = 0.0
    gex_flip_level:     Optional[float] = None

    @property
    def atm_iv(self) -> float:
        """Average of ATM call and put IV."""
        if self.atm_call_iv and self.atm_put_iv:
            return round((self.atm_call_iv + self.atm_put_iv) / 2, 2)
        return self.atm_call_iv or self.atm_put_iv

    @property
    def days_to_expiry(self) -> int:
        return max(0, (self.expiry - datetime.now(timezone.utc).date()).days)

    @property
    def strike_list(self) -> list[float]:
        return sorted(s.strike for s in self.strikes)

    def get_strike(self, strike: float) -> Optional[OptionStrike]:
        for s in self.strikes:
            if s.strike == strike:
                return s
        return None

    def strikes_near_atm(self, n: int = 10) -> list[OptionStrike]:
        """Return N strikes above and below ATM."""
        all_strikes = sorted(self.strikes, key=lambda s: s.strike)
        atm_idx = min(
            range(len(all_strikes)),
            key=lambda i: abs(all_strikes[i].strike - self.spot_price)
        )
        lo = max(0, atm_idx - n)
        hi = min(len(all_strikes), atm_idx + n + 1)
        return all_strikes[lo:hi]


# ─── Analytics Results ─────────────────────────────────────────────────────────

@dataclass
class PCRAnalysis:
    pcr_oi:         float
    pcr_volume:     float
    signal:         ChainSignalDirection
    narrative:      str
    bullish_pct:    float   # 0–100: how bullish the PCR is
    call_oi_wall:   float   # Strike with highest call OI (resistance)
    put_oi_wall:    float   # Strike with highest put OI (support)


@dataclass
class MaxPainResult:
    max_pain_strike:    float
    pain_table:         dict[float, float]   # strike → total pain
    distance_from_spot: float   # Max pain - spot (positive = above spot)
    distance_pct:       float   # As % of spot
    signal:             str     # "ABOVE_SPOT" | "BELOW_SPOT" | "AT_SPOT"


@dataclass
class GEXResult:
    total_gex:          float
    gex_by_strike:      dict[float, float]   # strike → net GEX
    gex_flip_level:     Optional[float]      # Strike where GEX changes sign
    regime:             str    # "POSITIVE_GEX" | "NEGATIVE_GEX"
    narrative:          str
    call_gex:           float
    put_gex:            float


@dataclass
class IVSkewResult:
    atm_iv:             float
    skew_25d:           float   # 25-delta Put IV - 25-delta Call IV
    skew_direction:     str     # "PUT_SKEW" | "CALL_SKEW" | "FLAT"
    iv_by_strike:       dict[float, dict]  # strike → {call_iv, put_iv, skew}
    risk_reversal:      float   # Simplified risk reversal proxy
    narrative:          str


@dataclass
class SupportResistanceLevel:
    strike:         float
    level_type:     str    # "SUPPORT" | "RESISTANCE"
    oi_at_level:    int
    strength:       str    # "STRONG" | "MODERATE" | "WEAK"
    distance_pct:   float  # % from current spot


@dataclass
class ChainSignal:
    """
    Final aggregated signal from the entire Option Chain Intelligence module.
    This feeds directly into the Decision Engine.
    """
    direction:          ChainSignalDirection
    confidence:         float           # 0–100
    pcr:                PCRAnalysis
    max_pain:           MaxPainResult
    gex:                GEXResult
    iv_skew:            IVSkewResult
    support_levels:     list[SupportResistanceLevel]
    resistance_levels:  list[SupportResistanceLevel]
    key_strikes:        dict            # atm, max_pain, call_wall, put_wall, gex_flip
    narrative:          str
    factor_weight:      float = 0.21   # 21% weight in the Decision Engine
    timestamp:          Optional[datetime] = None
