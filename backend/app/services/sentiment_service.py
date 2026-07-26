"""
NEXUS AI — Sentiment Intelligence Service Layer (Phase 6)
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SentimentService:
    """Service layer for sentiment intelligence endpoints."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from modules.sentiment.sentiment_engine import sentiment_engine
            self._engine = sentiment_engine
        return self._engine

    async def get_signal(
        self,
        scenario: str = "neutral",
        india_vix: float = 15.0,
        pcr: float = 1.0,
    ) -> dict:
        """Get full sentiment signal."""
        try:
            engine = self._get_engine()
            sig    = engine.analyze_sync(
                india_vix=india_vix, pcr=pcr, scenario=scenario
            )
            return {
                "bullish_score":  sig.bullish_score,
                "direction":      sig.direction,
                "confidence":     sig.confidence,
                "factor_scores":  sig.factor_scores,
                "factor_weight":  f"{sig.factor_weight*100:.0f}% of Decision Engine",
                "narrative":      sig.narrative,
                "news": {
                    "bullish_score":  sig.news.bullish_score,
                    "direction":      sig.news.direction,
                    "article_count":  sig.news.article_count,
                    "relevant_count": sig.news.relevant_count,
                    "top_headlines":  [
                        {"title": h.title, "source": h.source, "age_hours": h.age_hours,
                         "sentiment": h.sentiment, "relevance": h.relevance}
                        for h in sig.news.top_headlines[:5]
                    ],
                },
                "social": {
                    "bullish_score":  sig.social.bullish_score,
                    "direction":      sig.social.direction,
                    "oi_positioning": sig.social.oi_positioning,
                    "pcr_sentiment":  sig.social.pcr_sentiment,
                    "fear_greed": {
                        "score":     sig.social.fear_greed.score,
                        "label":     sig.social.fear_greed.label,
                        "india_vix": sig.social.fear_greed.india_vix,
                        "pcr":       sig.social.fear_greed.pcr,
                    },
                    "breadth": {
                        "advances":            sig.social.breadth.advances,
                        "declines":            sig.social.breadth.declines,
                        "advance_decline_ratio": sig.social.breadth.advance_decline_ratio,
                        "pct_above_20dma":     sig.social.breadth.pct_above_20dma,
                    },
                },
                "generated_at": sig.timestamp.isoformat() if sig.timestamp else None,
            }
        except Exception as e:
            logger.error(f"get_signal failed: {e}")
            return {"error": str(e)}

    async def get_news(self, scenario: str = "neutral") -> dict:
        """Get news sentiment with headlines."""
        try:
            engine = self._get_engine()
            news   = engine._news.synthetic_result(scenario)
            return {
                "bullish_score":  news.bullish_score,
                "direction":      news.direction,
                "confidence":     news.confidence,
                "article_count":  news.article_count,
                "relevant_count": news.relevant_count,
                "sentiment_raw":  news.sentiment_raw,
                "headlines": [
                    {
                        "title":     h.title,
                        "source":    h.source,
                        "sentiment": round(h.sentiment, 4),
                        "relevance": h.relevance,
                        "age_hours": h.age_hours,
                        "keywords":  h.keywords,
                    }
                    for h in news.top_headlines
                ],
            }
        except Exception as e:
            logger.error(f"get_news failed: {e}")
            return {"error": str(e)}

    async def get_fear_greed(
        self,
        india_vix: float = 15.0,
        pcr: float = 1.0,
        spot: float = 24000.0,
        sma_50: float = 23500.0,
        advances: int = 25,
        declines: int = 25,
        gold_chg: float = 0.0,
    ) -> dict:
        """Get Fear & Greed index."""
        try:
            engine = self._get_engine()
            fg     = engine._social.compute_fear_greed(
                india_vix, pcr, spot, sma_50, advances, declines, gold_chg
            )
            return {
                "score":      fg.score,
                "label":      fg.label,
                "india_vix":  fg.india_vix,
                "pcr":        fg.pcr,
                "components": {
                    "momentum":   fg.momentum,
                    "breadth":    fg.breadth,
                    "safe_haven": fg.safe_haven,
                },
                "interpretation": (
                    "Markets in EXTREME GREED — consider caution" if fg.score >= 80 else
                    "Markets in GREED — slight overextension" if fg.score >= 60 else
                    "Markets NEUTRAL — balanced positioning" if fg.score >= 40 else
                    "Markets in FEAR — potential buying opportunity" if fg.score >= 20 else
                    "Markets in EXTREME FEAR — contrarian buy signal"
                ),
            }
        except Exception as e:
            logger.error(f"get_fear_greed failed: {e}")
            return {"error": str(e)}

    async def get_breadth(self, advances: int = 25, declines: int = 25, unchanged: int = 0) -> dict:
        """Get market breadth metrics."""
        try:
            engine  = self._get_engine()
            breadth = engine._social.compute_breadth(advances, declines, unchanged)
            return {
                "advances":             breadth.advances,
                "declines":             breadth.declines,
                "unchanged":            breadth.unchanged,
                "advance_decline_ratio": breadth.advance_decline_ratio,
                "pct_above_20dma":      breadth.pct_above_20dma,
                "pct_above_50dma":      breadth.pct_above_50dma,
                "new_highs":            breadth.new_highs,
                "new_lows":             breadth.new_lows,
                "breadth_signal": (
                    "STRONG" if breadth.advance_decline_ratio > 1.5 else
                    "MODERATE" if breadth.advance_decline_ratio > 1.0 else
                    "WEAK"
                ),
            }
        except Exception as e:
            logger.error(f"get_breadth failed: {e}")
            return {"error": str(e)}


_svc: Optional[SentimentService] = None

def get_sentiment_service() -> SentimentService:
    global _svc
    if _svc is None:
        _svc = SentimentService()
    return _svc
