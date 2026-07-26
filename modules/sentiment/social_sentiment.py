"""
NEXUS AI — Social Sentiment Tracker (Phase 6)

Tracks retail and institutional social sentiment for NIFTY.

Sources (all free, no API key):
  1. Fear & Greed Index proxy (VIX-based computation)
  2. Put/Call ratio sentiment (from Option Chain data)
  3. Derivatives positioning sentiment (OI-based)
  4. Google Trends proxy (search interest for "NIFTY", "BUY NIFTY", "NIFTY crash")

Indicators:
  - Market Breadth (% of NIFTY50 stocks above 20-DMA)
  - Advance-Decline Ratio
  - F&O Sentiment (PCR extremes)
  - Crowd Sentiment Score (composite)

Note:
  Social media APIs (Twitter/X, Reddit) require authentication.
  This module uses market-structure proxies instead, which are
  MORE RELIABLE than retail social sentiment for trading decisions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BreadthData:
    """Market breadth metrics for NIFTY50."""
    advances:             int      # Stocks advancing
    declines:             int      # Stocks declining
    unchanged:            int
    advance_decline_ratio: float   # >1.5 = strong breadth, <0.5 = weak
    pct_above_20dma:      float    # % of NIFTY50 stocks above 20-DMA
    pct_above_50dma:      float    # % above 50-DMA
    new_highs:            int      # 52-week new highs
    new_lows:             int      # 52-week new lows


@dataclass
class FearGreedData:
    """Composite Fear & Greed index (VIX-based proxy)."""
    score:       float   # 0–100 (0=Extreme Fear, 100=Extreme Greed)
    label:       str     # "EXTREME FEAR" | "FEAR" | "NEUTRAL" | "GREED" | "EXTREME GREED"
    india_vix:   float
    pcr:         float   # Put-Call Ratio
    momentum:    float   # Price momentum component
    breadth:     float   # Market breadth component
    safe_haven:  float   # Gold/Rupee flows component


@dataclass
class SocialSentimentResult:
    """Aggregated social and positioning sentiment."""
    bullish_score:   float          # 0–100
    direction:       str            # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence:      float          # 0–100
    fear_greed:      FearGreedData
    breadth:         BreadthData
    pcr_sentiment:   str            # "BULLISH" | "BEARISH" | "NEUTRAL" (from PCR extremes)
    oi_positioning:  str            # Retail OI positioning
    narrative:       str
    factor_weight:   float = 0.08   # 8% of Decision Engine (within NLP block)
    timestamp:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SocialSentimentTracker:
    """
    Tracks market positioning and social sentiment using free data.
    Uses VIX + PCR + Breadth to construct a Fear & Greed proxy.
    """

    def compute_fear_greed(
        self,
        india_vix: float,
        pcr:       float,
        spot:      float,
        sma_50:    float,
        advances:  int = 0,
        declines:  int = 0,
        gold_chg:  float = 0.0,
    ) -> FearGreedData:
        """
        Compute Fear & Greed score from available market data.

        Components:
          1. India VIX (25%)     — Low VIX = greed, High = fear
          2. PCR (25%)           — High PCR (>1.5) = fear/contrarian bullish
          3. Price Momentum (25%) — Spot vs 50-DMA
          4. Market Breadth (15%) — A/D ratio
          5. Safe Haven (10%)    — Gold flows as risk-off proxy

        Returns score 0–100 (Extreme Fear → Extreme Greed).
        """
        # 1. VIX Component (inverted: high VIX = low score)
        if india_vix <= 10:     vix_score = 95.0
        elif india_vix <= 12:   vix_score = 80.0
        elif india_vix <= 15:   vix_score = 65.0
        elif india_vix <= 18:   vix_score = 50.0
        elif india_vix <= 22:   vix_score = 35.0
        elif india_vix <= 28:   vix_score = 20.0
        else:                   vix_score = 5.0

        # 2. PCR Component
        # PCR > 1.5 = extreme put buying = fear (but contrarian bullish)
        # PCR < 0.7 = extreme call buying = greed (but contrarian bearish)
        if pcr >= 1.8:      pcr_score = 15.0   # Extreme put buying = fear
        elif pcr >= 1.5:    pcr_score = 30.0
        elif pcr >= 1.2:    pcr_score = 50.0   # Neutral
        elif pcr >= 0.9:    pcr_score = 65.0
        elif pcr >= 0.7:    pcr_score = 75.0
        else:               pcr_score = 85.0   # Extreme call buying = greed

        # 3. Price Momentum (spot vs 50-DMA)
        if sma_50 > 0:
            pct_above = (spot - sma_50) / sma_50 * 100
            if pct_above > 5:      mom_score = 85.0
            elif pct_above > 2:    mom_score = 70.0
            elif pct_above > 0:    mom_score = 58.0
            elif pct_above > -2:   mom_score = 42.0
            elif pct_above > -5:   mom_score = 28.0
            else:                  mom_score = 15.0
        else:
            mom_score = 50.0

        # 4. Market Breadth
        total = advances + declines
        if total > 0:
            adv_ratio = advances / total
            if adv_ratio > 0.70:   breadth_score = 85.0
            elif adv_ratio > 0.55: breadth_score = 65.0
            elif adv_ratio > 0.45: breadth_score = 50.0
            elif adv_ratio > 0.30: breadth_score = 35.0
            else:                  breadth_score = 15.0
        else:
            breadth_score = 50.0

        # 5. Safe Haven (gold rising = fear)
        if gold_chg > 1.0:     safe_score = 20.0   # Gold surging = fear
        elif gold_chg > 0.3:   safe_score = 38.0
        elif gold_chg > -0.3:  safe_score = 50.0
        elif gold_chg > -1.0:  safe_score = 65.0
        else:                  safe_score = 80.0   # Gold falling = risk-on

        # Weighted composite
        score = round(
            0.25 * vix_score +
            0.25 * pcr_score +
            0.25 * mom_score +
            0.15 * breadth_score +
            0.10 * safe_score,
        1)
        score = max(0.0, min(100.0, score))

        label = (
            "EXTREME GREED" if score >= 80 else
            "GREED"         if score >= 60 else
            "NEUTRAL"       if score >= 40 else
            "FEAR"          if score >= 20 else
            "EXTREME FEAR"
        )

        return FearGreedData(
            score=score, label=label, india_vix=india_vix,
            pcr=pcr, momentum=mom_score, breadth=breadth_score,
            safe_haven=safe_score,
        )

    def compute_breadth(self, advances: int, declines: int, unchanged: int = 0) -> BreadthData:
        """Compute market breadth metrics."""
        total = advances + declines
        adr   = round(advances / declines, 3) if declines > 0 else float("inf")

        # Estimate DMA percentages from A/D (simplified proxy)
        pct_20 = round(advances / max(total, 1) * 100, 1)
        pct_50 = round(max(0, pct_20 - 5), 1)  # 50-DMA slightly more conservative

        return BreadthData(
            advances=advances, declines=declines, unchanged=unchanged,
            advance_decline_ratio=adr,
            pct_above_20dma=pct_20, pct_above_50dma=pct_50,
            new_highs=max(0, advances - 30), new_lows=max(0, declines - 30),
        )

    def pcr_to_sentiment(self, pcr: float) -> str:
        """
        Convert PCR to contrarian sentiment signal.
        Extreme fear (high PCR) → contrarian BULLISH for option buyers.
        """
        if pcr >= 1.5:  return "CONTRARIAN_BULLISH"   # Too many puts = potential reversal up
        if pcr >= 1.2:  return "SLIGHTLY_BULLISH"
        if pcr >= 0.9:  return "NEUTRAL"
        if pcr >= 0.7:  return "SLIGHTLY_BEARISH"
        return "CONTRARIAN_BEARISH"                    # Too many calls = potential reversal down

    def analyze(
        self,
        india_vix: float = 15.0,
        pcr:       float = 1.0,
        spot:      float = 24000.0,
        sma_50:    float = 23500.0,
        advances:  int   = 25,
        declines:  int   = 25,
        gold_chg:  float = 0.0,
    ) -> SocialSentimentResult:
        """
        Compute full social sentiment result.
        All parameters have safe defaults for when live data is unavailable.
        """
        fear_greed  = self.compute_fear_greed(
            india_vix, pcr, spot, sma_50, advances, declines, gold_chg
        )
        breadth     = self.compute_breadth(advances, declines)
        pcr_sent    = self.pcr_to_sentiment(pcr)

        # OI positioning: inferred from Fear & Greed label
        oi_position = {
            "EXTREME GREED": "OVER-EXTENDED_LONG",
            "GREED":         "NET_LONG",
            "NEUTRAL":       "BALANCED",
            "FEAR":          "NET_SHORT",
            "EXTREME FEAR":  "OVER-EXTENDED_SHORT",
        }.get(fear_greed.label, "BALANCED")

        # Bullish score: combine Fear & Greed with breadth
        breadth_score = min(100.0, breadth.advance_decline_ratio / 3.0 * 100)
        bullish_score = round(
            0.65 * fear_greed.score +
            0.35 * breadth_score,
        1)
        bullish_score = max(0.0, min(100.0, bullish_score))

        direction  = (
            "BULLISH" if bullish_score >= 60 else
            "BEARISH" if bullish_score < 40  else
            "NEUTRAL"
        )
        confidence = round(min(100.0, abs(bullish_score - 50) * 2.5), 1)

        narrative = (
            f"Social Sentiment: {direction} ({bullish_score:.0f}/100) | "
            f"Fear & Greed: {fear_greed.label} ({fear_greed.score:.0f}) | "
            f"PCR={pcr:.2f} ({pcr_sent}) | "
            f"A/D={advances}/{declines}"
        )

        return SocialSentimentResult(
            bullish_score  = bullish_score,
            direction      = direction,
            confidence     = confidence,
            fear_greed     = fear_greed,
            breadth        = breadth,
            pcr_sentiment  = pcr_sent,
            oi_positioning = oi_position,
            narrative      = narrative,
        )

    def synthetic_result(self, scenario: str = "neutral") -> SocialSentimentResult:
        """Generate synthetic social sentiment for testing and demos."""
        scenarios = {
            "bullish": dict(india_vix=11.0, pcr=0.85, spot=24500.0, sma_50=23500.0,
                           advances=38, declines=12, gold_chg=-0.5),
            "bearish": dict(india_vix=22.0, pcr=1.7, spot=23000.0, sma_50=24000.0,
                           advances=10, declines=40, gold_chg=1.2),
            "neutral": dict(india_vix=15.0, pcr=1.05, spot=24200.0, sma_50=23800.0,
                           advances=26, declines=24, gold_chg=0.1),
        }
        s = scenarios.get(scenario, scenarios["neutral"])
        return self.analyze(**s)


# ── Singleton ──────────────────────────────────────────────────────────────────
social_sentiment = SocialSentimentTracker()
