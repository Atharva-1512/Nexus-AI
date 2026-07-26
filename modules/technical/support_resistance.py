"""
NEXUS AI — Support & Resistance Detector (Module 6)

Price-based S/R using:
  1. Pivot Points (standard + Fibonacci)
  2. Swing Highs/Lows (rolling window)
  3. Round-number levels (psychological)
  4. Previous Day High/Low/Close (PDH/PDL/PDC)

Pivot Points are intraday reference levels derived from prior session data.
Standard pivots are widely watched by institutional desks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PivotLevels:
    """Standard and Fibonacci pivot point levels."""
    pp:    float    # Pivot Point
    r1:    float    # Resistance 1
    r2:    float    # Resistance 2
    r3:    float    # Resistance 3
    s1:    float    # Support 1
    s2:    float    # Support 2
    s3:    float    # Support 3
    # Fibonacci pivots
    fib_r1: float
    fib_r2: float
    fib_r3: float
    fib_s1: float
    fib_s2: float
    fib_s3: float
    # Previous session
    prev_high:  float
    prev_low:   float
    prev_close: float


@dataclass
class SRLevel:
    price:       float
    level_type:  str    # "RESISTANCE" | "SUPPORT"
    source:      str    # "PIVOT" | "SWING" | "ROUND" | "PREV_SESSION"
    strength:    str    # "STRONG" | "MODERATE" | "WEAK"
    touches:     int    # How many times price has tested this level
    distance_pct: float


class SupportResistanceAnalyzer:
    """Computes all S/R levels from price data."""

    def compute_pivots(self, df: pd.DataFrame) -> Optional[PivotLevels]:
        """
        Compute pivot points using the previous session's H/L/C.

        For daily data: uses the last completed bar as prior session.
        For intraday: uses the prior day's H/L/C.
        """
        if len(df) < 2:
            return None

        # Use prior session (second-to-last bar for daily)
        ph = float(df["high"].iloc[-2])
        pl = float(df["low"].iloc[-2])
        pc = float(df["close"].iloc[-2])
        rng = ph - pl

        # Standard Pivots
        pp = round((ph + pl + pc) / 3, 2)
        r1 = round(2 * pp - pl, 2)
        s1 = round(2 * pp - ph, 2)
        r2 = round(pp + rng, 2)
        s2 = round(pp - rng, 2)
        r3 = round(ph + 2 * (pp - pl), 2)
        s3 = round(pl - 2 * (ph - pp), 2)

        # Fibonacci Pivots (Camarilla variant)
        fib_r1 = round(pp + 0.382 * rng, 2)
        fib_r2 = round(pp + 0.618 * rng, 2)
        fib_r3 = round(pp + 1.000 * rng, 2)
        fib_s1 = round(pp - 0.382 * rng, 2)
        fib_s2 = round(pp - 0.618 * rng, 2)
        fib_s3 = round(pp - 1.000 * rng, 2)

        return PivotLevels(
            pp=pp, r1=r1, r2=r2, r3=r3, s1=s1, s2=s2, s3=s3,
            fib_r1=fib_r1, fib_r2=fib_r2, fib_r3=fib_r3,
            fib_s1=fib_s1, fib_s2=fib_s2, fib_s3=fib_s3,
            prev_high=ph, prev_low=pl, prev_close=pc,
        )

    def compute_swing_sr(
        self,
        df:       pd.DataFrame,
        spot:     float,
        window:   int = 5,
        n_levels: int = 3,
    ) -> tuple[list[SRLevel], list[SRLevel]]:
        """
        Identify S/R from recent swing highs and lows.

        Returns (support_levels, resistance_levels), each sorted by proximity.
        """
        h = df["high"].values
        l = df["low"].values
        n = len(df)

        swing_highs: list[float] = []
        swing_lows:  list[float] = []

        for i in range(window, n - window):
            if all(h[i] >= h[i-j] for j in range(1, window+1)) and \
               all(h[i] >= h[i+j] for j in range(1, window+1)):
                swing_highs.append(float(h[i]))
            if all(l[i] <= l[i-j] for j in range(1, window+1)) and \
               all(l[i] <= l[i+j] for j in range(1, window+1)):
                swing_lows.append(float(l[i]))

        supports    = []
        resistances = []

        # Count touches (proximity within 0.1% of level)
        for sh in sorted(set(swing_highs)):
            if sh > spot:
                dist = round((sh - spot) / spot * 100, 2)
                touches = sum(1 for x in swing_highs if abs(x - sh) / sh < 0.001)
                resistances.append(SRLevel(
                    price=round(sh, 2), level_type="RESISTANCE", source="SWING",
                    strength="STRONG" if touches >= 3 else "MODERATE" if touches >= 2 else "WEAK",
                    touches=touches, distance_pct=dist,
                ))

        for sl in sorted(set(swing_lows), reverse=True):
            if sl < spot:
                dist = round((spot - sl) / spot * 100, 2)
                touches = sum(1 for x in swing_lows if abs(x - sl) / sl < 0.001)
                supports.append(SRLevel(
                    price=round(sl, 2), level_type="SUPPORT", source="SWING",
                    strength="STRONG" if touches >= 3 else "MODERATE" if touches >= 2 else "WEAK",
                    touches=touches, distance_pct=dist,
                ))

        return (
            sorted(supports,    key=lambda x: x.distance_pct)[:n_levels],
            sorted(resistances, key=lambda x: x.distance_pct)[:n_levels],
        )

    def round_number_levels(
        self, spot: float, interval: float = 100.0, n: int = 3
    ) -> tuple[list[float], list[float]]:
        """
        Identify psychological round-number levels near spot.

        For NIFTY: every 100 pts is a key psychological level.
        Returns (supports, resistances).
        """
        base    = round(spot / interval) * interval
        supports    = sorted([base - interval * i for i in range(1, n+1)], reverse=True)
        resistances = sorted([base + interval * i for i in range(1, n+1)])
        return supports, resistances

    def all_levels(
        self,
        df:    pd.DataFrame,
        spot:  float,
        n:     int = 3,
    ) -> dict:
        """
        Compute and return all S/R levels as a unified dict.
        """
        pivots            = self.compute_pivots(df)
        swing_sup, swing_res = self.compute_swing_sr(df, spot, n_levels=n)
        round_sup, round_res = self.round_number_levels(spot, interval=100.0, n=2)

        return {
            "spot": spot,
            "pivots": {
                "pp": pivots.pp if pivots else None,
                "r1": pivots.r1 if pivots else None,
                "r2": pivots.r2 if pivots else None,
                "r3": pivots.r3 if pivots else None,
                "s1": pivots.s1 if pivots else None,
                "s2": pivots.s2 if pivots else None,
                "s3": pivots.s3 if pivots else None,
                "fib_r1": pivots.fib_r1 if pivots else None,
                "fib_r2": pivots.fib_r2 if pivots else None,
                "fib_s1": pivots.fib_s1 if pivots else None,
                "fib_s2": pivots.fib_s2 if pivots else None,
                "prev_high":  pivots.prev_high  if pivots else None,
                "prev_low":   pivots.prev_low   if pivots else None,
                "prev_close": pivots.prev_close if pivots else None,
            },
            "swing_supports":    [{"price": s.price, "strength": s.strength, "touches": s.touches} for s in swing_sup],
            "swing_resistances": [{"price": r.price, "strength": r.strength, "touches": r.touches} for r in swing_res],
            "round_supports":    round_sup,
            "round_resistances": round_res,
        }
