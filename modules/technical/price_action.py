"""
NEXUS AI — Price Action Analyzer (Module 6)

Detects candlestick patterns and trend structure from OHLCV data.

Patterns Detected:
  Single-bar: Doji, Hammer, Inverted Hammer, Shooting Star, Marubozu
  Two-bar:    Bullish/Bearish Engulfing, Harami, Piercing, Dark Cloud
  Three-bar:  Morning Star, Evening Star, Three White Soldiers, Three Black Crows

Trend Structure:
  - Swing High / Swing Low identification
  - Higher Highs / Higher Lows = Uptrend
  - Lower Highs / Lower Lows = Downtrend
  - Mixed = Ranging/Sideways
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class TrendDirection(str, Enum):
    UPTREND   = "UPTREND"
    DOWNTREND = "DOWNTREND"
    SIDEWAYS  = "SIDEWAYS"
    UNKNOWN   = "UNKNOWN"


class PatternType(str, Enum):
    # Bullish patterns
    HAMMER              = "HAMMER"
    INVERTED_HAMMER     = "INVERTED_HAMMER"
    BULLISH_ENGULFING   = "BULLISH_ENGULFING"
    BULLISH_HARAMI      = "BULLISH_HARAMI"
    MORNING_STAR        = "MORNING_STAR"
    PIERCING_LINE       = "PIERCING_LINE"
    THREE_WHITE_SOLDIERS = "THREE_WHITE_SOLDIERS"
    BULLISH_MARUBOZU    = "BULLISH_MARUBOZU"
    DRAGONFLY_DOJI      = "DRAGONFLY_DOJI"
    # Bearish patterns
    SHOOTING_STAR       = "SHOOTING_STAR"
    HANGING_MAN         = "HANGING_MAN"
    BEARISH_ENGULFING   = "BEARISH_ENGULFING"
    BEARISH_HARAMI      = "BEARISH_HARAMI"
    EVENING_STAR        = "EVENING_STAR"
    DARK_CLOUD_COVER    = "DARK_CLOUD_COVER"
    THREE_BLACK_CROWS   = "THREE_BLACK_CROWS"
    BEARISH_MARUBOZU    = "BEARISH_MARUBOZU"
    GRAVESTONE_DOJI     = "GRAVESTONE_DOJI"
    # Neutral patterns
    DOJI                = "DOJI"
    SPINNING_TOP        = "SPINNING_TOP"


@dataclass
class CandlePattern:
    pattern_type: PatternType
    bar_index:    int
    direction:    str   # "BULLISH" | "BEARISH" | "NEUTRAL"
    strength:     str   # "STRONG" | "MODERATE" | "WEAK"
    description:  str


@dataclass
class TrendAnalysis:
    direction:          TrendDirection
    strength:           str             # "STRONG" | "MODERATE" | "WEAK"
    swing_highs:        list[float]
    swing_lows:         list[float]
    higher_highs:       bool
    higher_lows:        bool
    lower_highs:        bool
    lower_lows:         bool
    consecutive_bars:   int             # Bars in current trend
    slope_pct:          float           # % slope of recent trend
    narrative:          str


class PriceActionAnalyzer:
    """Detects candlestick patterns and trend structure."""

    def __init__(self, body_threshold: float = 0.1, doji_threshold: float = 0.05):
        """
        Args:
            body_threshold: Min body-to-range ratio for non-doji candles
            doji_threshold: Max body-to-range ratio for doji candles
        """
        self.body_thresh = body_threshold
        self.doji_thresh = doji_threshold

    # ─── Pattern Detection ────────────────────────────────────────────────────

    def detect_patterns(self, df: pd.DataFrame, lookback: int = 5) -> list[CandlePattern]:
        """
        Detect all candlestick patterns in the last `lookback` bars.

        Args:
            df:       OHLCV DataFrame
            lookback: How many recent bars to check

        Returns:
            List of CandlePattern objects (most recent first)
        """
        patterns: list[CandlePattern] = []
        n = len(df)
        if n < 3:
            return patterns

        start = max(0, n - lookback)
        for i in range(start, n):
            o, h, l, c = df["open"].iloc[i], df["high"].iloc[i], df["low"].iloc[i], df["close"].iloc[i]
            body  = abs(c - o)
            rng   = h - l
            if rng == 0:
                continue
            body_ratio = body / rng
            upper_wick = h - max(o, c)
            lower_wick = min(o, c) - l

            # ── Single-bar patterns ──────────────────────────────────────────
            if body_ratio <= self.doji_thresh:
                if lower_wick > 2 * upper_wick:
                    patterns.append(CandlePattern(PatternType.DRAGONFLY_DOJI, i, "BULLISH", "MODERATE",
                        "Dragonfly Doji: long lower wick = buying support"))
                elif upper_wick > 2 * lower_wick:
                    patterns.append(CandlePattern(PatternType.GRAVESTONE_DOJI, i, "BEARISH", "MODERATE",
                        "Gravestone Doji: long upper wick = rejection at high"))
                else:
                    patterns.append(CandlePattern(PatternType.DOJI, i, "NEUTRAL", "WEAK",
                        "Doji: indecision, trend reversal possible"))

            elif lower_wick > 2 * body and upper_wick < body * 0.5:
                direction = "BULLISH"
                ptype = PatternType.HAMMER if c > o else PatternType.HANGING_MAN
                patterns.append(CandlePattern(ptype, i, direction, "STRONG",
                    f"{'Hammer' if ptype==PatternType.HAMMER else 'Hanging Man'}: strong lower wick reversal"))

            elif upper_wick > 2 * body and lower_wick < body * 0.5:
                direction = "BEARISH"
                ptype = PatternType.SHOOTING_STAR if c < o else PatternType.INVERTED_HAMMER
                patterns.append(CandlePattern(ptype, i, direction, "STRONG",
                    f"{'Shooting Star' if ptype==PatternType.SHOOTING_STAR else 'Inverted Hammer'}: rejection at high"))

            elif body_ratio > 0.8 and lower_wick < body * 0.1 and upper_wick < body * 0.1:
                if c > o:
                    patterns.append(CandlePattern(PatternType.BULLISH_MARUBOZU, i, "BULLISH", "STRONG",
                        "Bullish Marubozu: pure buying pressure"))
                else:
                    patterns.append(CandlePattern(PatternType.BEARISH_MARUBOZU, i, "BEARISH", "STRONG",
                        "Bearish Marubozu: pure selling pressure"))

            # ── Two-bar patterns ─────────────────────────────────────────────
            if i >= 1:
                po, ph, pl, pc = (df["open"].iloc[i-1], df["high"].iloc[i-1],
                                  df["low"].iloc[i-1], df["close"].iloc[i-1])
                prev_body = abs(pc - po)

                # Bullish Engulfing
                if pc < po and c > o and c > po and o < pc and prev_body > 0:
                    patterns.append(CandlePattern(PatternType.BULLISH_ENGULFING, i, "BULLISH", "STRONG",
                        "Bullish Engulfing: current candle fully covers prior bearish bar"))

                # Bearish Engulfing
                elif pc > po and c < o and c < po and o > pc and prev_body > 0:
                    patterns.append(CandlePattern(PatternType.BEARISH_ENGULFING, i, "BEARISH", "STRONG",
                        "Bearish Engulfing: current candle fully covers prior bullish bar"))

                # Piercing Line (bullish reversal)
                elif pc < po and c > o and c > (po + pc) / 2 and o < pc:
                    patterns.append(CandlePattern(PatternType.PIERCING_LINE, i, "BULLISH", "MODERATE",
                        "Piercing Line: bullish candle pierces > 50% of prior bearish bar"))

                # Dark Cloud Cover (bearish reversal)
                elif pc > po and c < o and c < (po + pc) / 2 and o > pc:
                    patterns.append(CandlePattern(PatternType.DARK_CLOUD_COVER, i, "BEARISH", "MODERATE",
                        "Dark Cloud Cover: bearish candle cuts > 50% into prior bullish bar"))

            # ── Three-bar patterns ───────────────────────────────────────────
            if i >= 2:
                o1, h1, l1, c1 = (df["open"].iloc[i-2], df["high"].iloc[i-2],
                                   df["low"].iloc[i-2], df["close"].iloc[i-2])
                o2, h2, l2, c2 = (df["open"].iloc[i-1], df["high"].iloc[i-1],
                                   df["low"].iloc[i-1], df["close"].iloc[i-1])

                # Morning Star
                if (c1 < o1 and                               # bar-2: bearish
                    abs(c2 - o2) / (h2 - l2 + 1e-9) < 0.3 and  # bar-1: small body
                    c > o and c > (c1 + o1) / 2):            # bar0: bullish, closes above bar-2 midpoint
                    patterns.append(CandlePattern(PatternType.MORNING_STAR, i, "BULLISH", "STRONG",
                        "Morning Star: 3-bar bullish reversal pattern"))

                # Evening Star
                elif (c1 > o1 and
                      abs(c2 - o2) / (h2 - l2 + 1e-9) < 0.3 and
                      c < o and c < (c1 + o1) / 2):
                    patterns.append(CandlePattern(PatternType.EVENING_STAR, i, "BEARISH", "STRONG",
                        "Evening Star: 3-bar bearish reversal pattern"))

                # Three White Soldiers
                elif c > o and c2 > o2 and c1 > o1 and c > c2 > c1:
                    patterns.append(CandlePattern(PatternType.THREE_WHITE_SOLDIERS, i, "BULLISH", "STRONG",
                        "Three White Soldiers: 3 consecutive strong bullish bars"))

                # Three Black Crows
                elif c < o and c2 < o2 and c1 < o1 and c < c2 < c1:
                    patterns.append(CandlePattern(PatternType.THREE_BLACK_CROWS, i, "BEARISH", "STRONG",
                        "Three Black Crows: 3 consecutive strong bearish bars"))

        return sorted(patterns, key=lambda p: p.bar_index, reverse=True)

    # ─── Trend Analysis ───────────────────────────────────────────────────────

    def analyze_trend(self, df: pd.DataFrame, swing_lookback: int = 5) -> TrendAnalysis:
        """
        Analyze trend structure using swing highs and lows.

        Args:
            df:             OHLCV DataFrame (need ≥ 20 bars)
            swing_lookback: Bars on each side to confirm a swing point

        Returns:
            TrendAnalysis with direction, structure, and narrative
        """
        if len(df) < 10:
            return TrendAnalysis(TrendDirection.UNKNOWN, "WEAK", [], [], False, False, False, False, 0, 0.0, "Insufficient data")

        highs = df["high"].values
        lows  = df["low"].values
        close = df["close"].values
        n     = len(df)
        lb    = min(swing_lookback, n // 3)

        swing_highs: list[float] = []
        swing_lows:  list[float] = []

        for i in range(lb, n - lb):
            if all(highs[i] >= highs[i-j] for j in range(1, lb+1)) and \
               all(highs[i] >= highs[i+j] for j in range(1, lb+1)):
                swing_highs.append(float(highs[i]))
            if all(lows[i] <= lows[i-j] for j in range(1, lb+1)) and \
               all(lows[i] <= lows[i+j] for j in range(1, lb+1)):
                swing_lows.append(float(lows[i]))

        # Structure analysis
        hh = len(swing_highs) >= 2 and swing_highs[-1] > swing_highs[-2]
        hl = len(swing_lows)  >= 2 and swing_lows[-1]  > swing_lows[-2]
        lh = len(swing_highs) >= 2 and swing_highs[-1] < swing_highs[-2]
        ll = len(swing_lows)  >= 2 and swing_lows[-1]  < swing_lows[-2]

        if hh and hl:
            direction = TrendDirection.UPTREND
            strength  = "STRONG"
        elif lh and ll:
            direction = TrendDirection.DOWNTREND
            strength  = "STRONG"
        elif hh or hl:
            direction = TrendDirection.UPTREND
            strength  = "MODERATE"
        elif lh or ll:
            direction = TrendDirection.DOWNTREND
            strength  = "MODERATE"
        else:
            direction = TrendDirection.SIDEWAYS
            strength  = "WEAK"

        # Consecutive bars in trend direction
        consecutive = 0
        if len(close) >= 2:
            is_up = close[-1] > close[-2]
            for i in range(n-1, 0, -1):
                if (close[i] > close[i-1]) == is_up:
                    consecutive += 1
                else:
                    break

        # Slope (% change over last 10 bars)
        slope_pct = 0.0
        if n >= 10 and close[-10] > 0:
            slope_pct = round((close[-1] - close[-10]) / close[-10] * 100, 2)

        narrative = (
            f"{direction.value} ({strength}): "
            f"{'HH+HL ' if hh and hl else 'LH+LL ' if lh and ll else ''}"
            f"slope={slope_pct:+.1f}% over 10 bars, "
            f"{consecutive} consecutive {'up' if consecutive and close[-1] > close[-2] else 'down'} bars"
        )

        return TrendAnalysis(
            direction=direction, strength=strength,
            swing_highs=swing_highs[-5:], swing_lows=swing_lows[-5:],
            higher_highs=hh, higher_lows=hl,
            lower_highs=lh, lower_lows=ll,
            consecutive_bars=consecutive, slope_pct=slope_pct, narrative=narrative,
        )

    def latest_pattern_signal(self, patterns: list[CandlePattern]) -> str:
        """Summarize the most recent strong pattern into a signal direction."""
        if not patterns:
            return "NEUTRAL"
        strong = [p for p in patterns if p.strength == "STRONG"]
        if strong:
            return strong[0].direction
        return patterns[0].direction if patterns else "NEUTRAL"
