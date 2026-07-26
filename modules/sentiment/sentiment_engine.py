"""
NEXUS AI — Sentiment Engine Master Orchestrator (Phase 6)

Combines News Sentiment + Social Sentiment into a single
Sentiment Signal that feeds into the NEXUS Decision Engine.

Weights within Sentiment block:
  News Sentiment   → 60% (headlines, RSS feeds)
  Social Sentiment → 40% (Fear & Greed, PCR, Breadth)

Combined Sentiment contributes 12% to Decision Engine.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .news_sentiment   import NewsSentimentAnalyzer, SentimentResult, news_sentiment
from .social_sentiment import SocialSentimentTracker, SocialSentimentResult, social_sentiment

logger = logging.getLogger(__name__)

_NEWS_WEIGHT   = 0.60
_SOCIAL_WEIGHT = 0.40


@dataclass
class SentimentSignal:
    """
    Combined Sentiment Signal for the NEXUS Decision Engine.
    This is the top-level output of Phase 6.
    """
    bullish_score:   float           # 0–100
    direction:       str             # STRONGLY_BULLISH | BULLISH | NEUTRAL | BEARISH | STRONGLY_BEARISH
    confidence:      float           # 0–100
    news:            SentimentResult
    social:          SocialSentimentResult
    factor_scores:   dict            # For Explainability Dashboard
    factor_weight:   float = 0.12    # 12% of Decision Engine
    narrative:       str   = ""
    timestamp:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SentimentEngine:
    """
    Master Sentiment Orchestrator.
    Fetches news + social sentiment and produces a single SentimentSignal.
    """

    def __init__(self):
        self._news   = news_sentiment
        self._social = social_sentiment

    async def analyze(
        self,
        india_vix:  float = 15.0,
        pcr:        float = 1.0,
        spot:       float = 24000.0,
        sma_50:     float = 23500.0,
        advances:   int   = 25,
        declines:   int   = 25,
        gold_chg:   float = 0.0,
        use_live_news: bool = False,
    ) -> SentimentSignal:
        """
        Run full sentiment analysis.

        Args:
            india_vix:     Current India VIX level
            pcr:           Put-Call Ratio from option chain
            spot:          NIFTY spot price
            sma_50:        NIFTY 50-day SMA
            advances:      Number of advancing NIFTY50 stocks
            declines:      Number of declining NIFTY50 stocks
            gold_chg:      Gold 1-day % change
            use_live_news: Fetch live RSS feeds (may be slow)

        Returns:
            SentimentSignal with combined score
        """
        # ── News sentiment ───────────────────────────────────────────────────
        if use_live_news:
            try:
                news_result = self._news.analyze()
                if news_result.article_count == 0:
                    news_result = self._news.synthetic_result("neutral")
            except Exception as e:
                logger.warning(f"Live news fetch failed: {e}. Using synthetic.")
                news_result = self._news.synthetic_result("neutral")
        else:
            news_result = self._news.synthetic_result("neutral")

        # ── Social sentiment ─────────────────────────────────────────────────
        social_result = self._social.analyze(
            india_vix=india_vix, pcr=pcr, spot=spot,
            sma_50=sma_50, advances=advances, declines=declines,
            gold_chg=gold_chg,
        )

        # ── Weighted aggregate ───────────────────────────────────────────────
        bullish_score = round(
            _NEWS_WEIGHT   * news_result.bullish_score +
            _SOCIAL_WEIGHT * social_result.bullish_score,
        1)
        bullish_score = max(0.0, min(100.0, bullish_score))

        direction  = self._score_to_direction(bullish_score)
        confidence = round(
            _NEWS_WEIGHT   * news_result.confidence +
            _SOCIAL_WEIGHT * social_result.confidence,
        1)

        factor_scores = {
            "news_sentiment":   round(news_result.bullish_score, 1),
            "fear_greed":       round(social_result.fear_greed.score, 1),
            "market_breadth":   round(social_result.fear_greed.breadth, 1),
            "pcr_sentiment":    round(social_result.fear_greed.score, 1),
            "vix_sentiment":    round(100 - social_result.fear_greed.india_vix * 3, 1),
        }

        narrative = (
            f"Sentiment: {direction} ({bullish_score:.0f}/100) | "
            f"News: {news_result.direction} ({news_result.bullish_score:.0f}) | "
            f"Fear&Greed: {social_result.fear_greed.label} ({social_result.fear_greed.score:.0f}) | "
            f"PCR={pcr:.2f}"
        )

        return SentimentSignal(
            bullish_score  = bullish_score,
            direction      = direction,
            confidence     = confidence,
            news           = news_result,
            social         = social_result,
            factor_scores  = factor_scores,
            narrative      = narrative,
            timestamp      = datetime.now(timezone.utc),
        )

    def analyze_sync(
        self,
        india_vix: float = 15.0, pcr: float = 1.0,
        spot: float = 24000.0, sma_50: float = 23500.0,
        advances: int = 25, declines: int = 25,
        gold_chg: float = 0.0, scenario: str = "neutral",
    ) -> SentimentSignal:
        """
        Synchronous analyze using synthetic data (for testing/fallback).
        scenario: "bullish" | "bearish" | "neutral"
        """
        news_result   = self._news.synthetic_result(scenario)
        social_result = self._social.synthetic_result(scenario)

        bullish_score = round(
            _NEWS_WEIGHT   * news_result.bullish_score +
            _SOCIAL_WEIGHT * social_result.bullish_score,
        1)

        direction = self._score_to_direction(bullish_score)
        confidence = round(
            _NEWS_WEIGHT * news_result.confidence +
            _SOCIAL_WEIGHT * social_result.confidence, 1,
        )

        factor_scores = {
            "news_sentiment": round(news_result.bullish_score, 1),
            "fear_greed":     round(social_result.fear_greed.score, 1),
            "market_breadth": round(social_result.fear_greed.breadth, 1),
            "pcr_sentiment":  round(social_result.fear_greed.score, 1),
            "vix_sentiment":  round(max(0, 100 - social_result.fear_greed.india_vix * 3), 1),
        }

        return SentimentSignal(
            bullish_score  = bullish_score,
            direction      = direction,
            confidence     = confidence,
            news           = news_result,
            social         = social_result,
            factor_scores  = factor_scores,
            narrative      = (
                f"Sentiment: {direction} ({bullish_score:.0f}/100) | "
                f"News: {news_result.direction} | "
                f"Fear&Greed: {social_result.fear_greed.label}"
            ),
        )

    @staticmethod
    def _score_to_direction(score: float) -> str:
        if score >= 75:  return "STRONGLY_BULLISH"
        if score >= 60:  return "BULLISH"
        if score >= 40:  return "NEUTRAL"
        if score >= 25:  return "BEARISH"
        return "STRONGLY_BEARISH"


# ── Module singleton ───────────────────────────────────────────────────────────
sentiment_engine = SentimentEngine()
