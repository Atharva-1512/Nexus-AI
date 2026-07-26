"""
NEXUS AI — News Sentiment Analyzer (Phase 6)

Fetches financial news from free sources and scores sentiment:

Sources (all free, no API key):
  1. Google News RSS      — General market news
  2. MoneyControl RSS     — India-specific news
  3. Economic Times RSS   — Indian financial news
  4. NSE Announcements    — Corporate announcements

Sentiment Scoring:
  - VADER lexicon (rule-based, no model needed)
  - Financial keyword boosting (NIFTY-specific terms)
  - Entity extraction (is the headline about NIFTY/markets?)
  - Recency weighting (newer news = higher weight)

Output: SentimentScore (bullish 0–100) contributing 12% to Decision Engine
"""

from __future__ import annotations

import re
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from email import utils as email_utils

logger = logging.getLogger(__name__)

# ─── Financial Keyword Dictionaries ──────────────────────────────────────────

BULLISH_KEYWORDS = {
    # Strong bullish (weight 2.0)
    "breakout": 2.0, "surge": 2.0, "rally": 2.0, "soar": 2.0, "jump": 2.0,
    "skyrocket": 2.0, "boom": 2.0, "record high": 2.0, "all time high": 2.0,
    "bull run": 2.0, "fii buying": 2.0, "strong buy": 2.0, "upgrade": 1.8,
    # Moderate bullish (weight 1.5)
    "rise": 1.5, "gain": 1.5, "positive": 1.5, "bullish": 1.5, "uptrend": 1.5,
    "recovery": 1.5, "rebound": 1.5, "bounce": 1.5, "outperform": 1.5,
    "beat": 1.5, "exceed": 1.5, "growth": 1.5, "profit": 1.5, "earnings beat": 1.5,
    # Mild bullish (weight 1.0)
    "green": 1.0, "up": 1.0, "higher": 1.0, "optimism": 1.0, "support": 1.0,
    "inflow": 1.0, "demand": 1.0, "buying": 1.0, "accumulation": 1.0,
}

BEARISH_KEYWORDS = {
    # Strong bearish (weight 2.0)
    "crash": 2.0, "collapse": 2.0, "plunge": 2.0, "slump": 2.0, "selloff": 2.0,
    "sell off": 2.0, "freefall": 2.0, "bear market": 2.0, "circuit breaker": 2.0,
    "recession": 2.0, "fii selling": 2.0, "downgrade": 1.8, "cut": 1.5,
    # Moderate bearish (weight 1.5)
    "fall": 1.5, "decline": 1.5, "drop": 1.5, "bearish": 1.5, "downtrend": 1.5,
    "loss": 1.5, "miss": 1.5, "disappoint": 1.5, "underperform": 1.5,
    "concern": 1.5, "worry": 1.5, "fear": 1.5, "risk": 1.2, "outflow": 1.5,
    # Mild bearish (weight 1.0)
    "red": 1.0, "down": 1.0, "lower": 1.0, "weak": 1.0, "pressure": 1.0,
    "selling": 1.0, "distribution": 1.0, "caution": 1.0,
}

# Keywords that indicate the article is NIFTY/market relevant
MARKET_KEYWORDS = {
    "nifty", "sensex", "nse", "bse", "market", "stock", "share",
    "equity", "index", "fii", "dii", "rbi", "sebi", "option",
    "futures", "derivative", "trading", "investor", "rally",
}

NIFTY_BOOST_KEYWORDS = {
    "nifty", "nifty 50", "nifty50", "bank nifty", "index option",
    "nse", "option chain", "call option", "put option",
}

# Feed URLs (public RSS, no authentication)
RSS_FEEDS = [
    {
        "name": "Economic Times Markets",
        "url": "https://economictimes.indiatimes.com/markets/stocks/rss.cms",
        "weight": 1.5,
        "region": "INDIA",
    },
    {
        "name": "Economic Times Economy",
        "url": "https://economictimes.indiatimes.com/economy/rss.cms",
        "weight": 1.2,
        "region": "INDIA",
    },
    {
        "name": "MoneyControl News",
        "url": "https://www.moneycontrol.com/rss/latestnews.xml",
        "weight": 1.3,
        "region": "INDIA",
    },
    {
        "name": "Business Standard Markets",
        "url": "https://www.business-standard.com/rss/markets-106.rss",
        "weight": 1.2,
        "region": "INDIA",
    },
    {
        "name": "Reuters Business",
        "url": "https://feeds.reuters.com/reuters/businessNews",
        "weight": 1.0,
        "region": "GLOBAL",
    },
]


@dataclass
class NewsItem:
    """A single news headline with sentiment score."""
    title:        str
    source:       str
    url:          str
    published:    datetime
    sentiment:    float      # -1.0 to 1.0 (negative = bearish, positive = bullish)
    relevance:    float      # 0.0 to 1.0 (how relevant to NIFTY/markets)
    keywords:     list[str]  # Matching keywords found
    age_hours:    float      # Hours since publication


@dataclass
class SentimentResult:
    """Aggregated sentiment result for the Decision Engine."""
    bullish_score:    float          # 0–100
    sentiment_raw:    float          # -1 to +1
    direction:        str            # "BULLISH" | "BEARISH" | "NEUTRAL"
    confidence:       float          # 0–100
    article_count:    int
    relevant_count:   int
    top_headlines:    list[NewsItem]
    factor_weight:    float = 0.12   # 12% of Decision Engine
    narrative:        str = ""
    timestamp:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NewsSentimentAnalyzer:
    """
    Fetches news and computes sentiment score for NEXUS Decision Engine.
    Uses pure Python keyword-based scoring (no ML model, no API key).
    """

    def __init__(self, cache_ttl_seconds: int = 300, max_age_hours: int = 6):
        self._cache:       dict = {}
        self._cache_ttl    = cache_ttl_seconds
        self._max_age_hrs  = max_age_hours

    # ─── RSS Fetch ────────────────────────────────────────────────────────────

    def fetch_rss(self, url: str, source_name: str, weight: float = 1.0) -> list[NewsItem]:
        """
        Fetch and parse an RSS feed.
        Returns list of NewsItem with sentiment scored.
        """
        try:
            import urllib.request
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (NEXUS-AI/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
            return self._parse_rss(raw, source_name, weight)
        except Exception as e:
            logger.debug(f"RSS fetch failed [{source_name}]: {e}")
            return []

    def _parse_rss(self, xml: str, source: str, weight: float) -> list[NewsItem]:
        """Parse RSS XML and extract items."""
        items: list[NewsItem] = []
        # Simple regex-based parser (avoids heavy dependencies)
        title_re   = re.compile(r"<title[^>]*><!\[CDATA\[(.*?)\]\]></title>|<title[^>]*>(.*?)</title>", re.DOTALL)
        link_re    = re.compile(r"<link[^>]*>(.*?)</link>", re.DOTALL)
        pubdate_re = re.compile(r"<pubDate[^>]*>(.*?)</pubDate>", re.DOTALL)

        # Split into items
        item_chunks = re.split(r"<item>", xml)[1:]

        for chunk in item_chunks[:30]:  # Max 30 items per feed
            try:
                t_match = title_re.search(chunk)
                title   = (t_match.group(1) or t_match.group(2) or "").strip() if t_match else ""
                if not title or len(title) < 10:
                    continue

                # Clean HTML entities
                title = re.sub(r"<[^>]+>", "", title)
                title = title.replace("&amp;", "&").replace("&quot;", '"').replace("&#39;", "'")

                link   = ""
                l_m    = link_re.search(chunk)
                if l_m:
                    link = l_m.group(1).strip()

                # Parse publication date
                published = datetime.now(timezone.utc)
                p_m       = pubdate_re.search(chunk)
                if p_m:
                    try:
                        ts = email_utils.parsedate_to_datetime(p_m.group(1).strip())
                        published = ts.astimezone(timezone.utc)
                    except Exception:
                        pass

                age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
                if age_hours > self._max_age_hrs:
                    continue  # Skip stale news

                sentiment, relevance, keywords = self._score_headline(title.lower())

                items.append(NewsItem(
                    title=title, source=source, url=link,
                    published=published, sentiment=sentiment,
                    relevance=relevance, keywords=keywords,
                    age_hours=round(age_hours, 2),
                ))
            except Exception:
                continue

        return items

    # ─── Sentiment Scoring ────────────────────────────────────────────────────

    def _score_headline(self, text: str) -> tuple[float, float, list[str]]:
        """
        Score headline sentiment using financial keyword dictionary.

        Returns:
            sentiment: -1.0 to +1.0 (negative = bearish)
            relevance: 0.0 to +1.0 (market relevance)
            keywords:  matched keywords
        """
        bull_score = 0.0
        bear_score = 0.0
        matched_kw: list[str] = []

        for kw, w in BULLISH_KEYWORDS.items():
            if kw in text:
                bull_score += w
                matched_kw.append(kw)

        for kw, w in BEARISH_KEYWORDS.items():
            if kw in text:
                bear_score += w
                matched_kw.append(kw)

        # Negation detection (simple: "not rally" → flip)
        negation_patterns = ["not ", "no ", "no longer ", "failed to "]
        for neg in negation_patterns:
            if neg in text:
                bull_score, bear_score = bear_score * 0.5, bull_score * 0.5
                break

        # Normalize to -1 to +1
        total = bull_score + bear_score
        if total == 0:
            sentiment = 0.0
        else:
            sentiment = round((bull_score - bear_score) / (total + 1e-9), 4)

        # Relevance score: how many market keywords match?
        market_hits = sum(1 for kw in MARKET_KEYWORDS if kw in text)
        nifty_hits  = sum(1 for kw in NIFTY_BOOST_KEYWORDS if kw in text)
        relevance   = round(min(1.0, market_hits * 0.1 + nifty_hits * 0.25), 3)

        return sentiment, relevance, matched_kw[:5]

    # ─── Aggregate ────────────────────────────────────────────────────────────

    def analyze(self, feeds: Optional[list[dict]] = None) -> SentimentResult:
        """
        Fetch all RSS feeds and aggregate into a SentimentResult.
        Falls back to neutral if no news is available.
        """
        if feeds is None:
            feeds = RSS_FEEDS

        all_items: list[NewsItem] = []
        for feed in feeds:
            items = self.fetch_rss(feed["url"], feed["name"], feed.get("weight", 1.0))
            all_items.extend(items)

        return self._aggregate(all_items)

    def _aggregate(self, items: list[NewsItem]) -> SentimentResult:
        """Aggregate news items into a sentiment score."""
        if not items:
            return self._neutral_result("No news available")

        # Filter relevant items
        relevant = [i for i in items if i.relevance >= 0.1]
        if not relevant:
            relevant = items  # Use all if nothing is relevant

        # Weighted sentiment: weight by relevance × recency
        total_weight  = 0.0
        weighted_sent = 0.0

        for item in relevant:
            # Recency weight: exponential decay over max_age_hours
            recency_w = max(0.1, 1.0 - (item.age_hours / self._max_age_hrs) * 0.8)
            w         = item.relevance * recency_w + 0.1  # Min weight 0.1
            weighted_sent += item.sentiment * w
            total_weight  += w

        sentiment_raw = weighted_sent / total_weight if total_weight > 0 else 0.0
        sentiment_raw = max(-1.0, min(1.0, sentiment_raw))

        # Convert to 0–100 bullish score
        bullish_score = round((sentiment_raw + 1.0) / 2.0 * 100, 1)

        # Direction
        if bullish_score >= 62:    direction = "BULLISH"
        elif bullish_score >= 55:  direction = "SLIGHTLY_BULLISH"
        elif bullish_score >= 45:  direction = "NEUTRAL"
        elif bullish_score >= 38:  direction = "SLIGHTLY_BEARISH"
        else:                      direction = "BEARISH"

        # Confidence: higher with more relevant articles and clearer signal
        confidence = min(100.0, round(
            len(relevant) * 3 +            # More articles = more confident
            abs(sentiment_raw) * 40,       # Stronger signal = more confident
        1))

        # Top headlines (most relevant, most recent)
        top = sorted(relevant, key=lambda x: -(x.relevance * 2 + (1 / (x.age_hours + 0.1))))[:5]

        narrative = self._build_narrative(direction, bullish_score, sentiment_raw, len(items), len(relevant), top)

        return SentimentResult(
            bullish_score  = bullish_score,
            sentiment_raw  = round(sentiment_raw, 4),
            direction      = direction,
            confidence     = confidence,
            article_count  = len(items),
            relevant_count = len(relevant),
            top_headlines  = top,
            narrative      = narrative,
            timestamp      = datetime.now(timezone.utc),
        )

    @staticmethod
    def _build_narrative(
        direction: str, score: float, raw: float,
        total: int, relevant: int, top: list[NewsItem],
    ) -> str:
        parts = [f"Sentiment: {direction} ({score:.0f}/100)"]
        parts.append(f"{relevant}/{total} articles market-relevant")
        if top:
            parts.append(f"Top: \"{top[0].title[:80]}\"")
        return " | ".join(parts)

    def _neutral_result(self, reason: str = "") -> SentimentResult:
        return SentimentResult(
            bullish_score=50.0, sentiment_raw=0.0,
            direction="NEUTRAL", confidence=0.0,
            article_count=0, relevant_count=0,
            top_headlines=[], narrative=f"Neutral: {reason}",
        )

    def synthetic_result(self, scenario: str = "neutral") -> SentimentResult:
        """
        Generate a synthetic SentimentResult for testing and demos.
        scenario: "bullish" | "bearish" | "neutral"
        """
        scenarios = {
            "bullish": dict(
                score=72.0, raw=0.44, direction="BULLISH", confidence=78.0,
                headlines=[
                    "NIFTY rallies 200 points on strong FII inflows; bulls target 25000",
                    "RBI holds rates, market cheers accommodative stance",
                    "IT sector surges as US tech stocks climb; NIFTY outperforms",
                    "FII net buyers for 5th consecutive session; confidence high",
                    "India GDP beats estimates; Sensex hits record high",
                ]
            ),
            "bearish": dict(
                score=28.0, raw=-0.44, direction="BEARISH", confidence=75.0,
                headlines=[
                    "NIFTY slides 350 points on rising crude, weak global cues",
                    "FII selling accelerates; market falls for 3rd session",
                    "US inflation data shocks markets; risk-off mood grips Dalal Street",
                    "India VIX spikes to 22; traders brace for more volatility",
                    "RBI signals rate hike concern; banking stocks under pressure",
                ]
            ),
            "neutral": dict(
                score=51.0, raw=0.02, direction="NEUTRAL", confidence=40.0,
                headlines=[
                    "NIFTY trades flat amid mixed global cues; supports intact",
                    "Markets consolidate; investors await Q2 results",
                    "FII flows mixed; DII buying provides cushion to markets",
                ]
            ),
        }

        s = scenarios.get(scenario, scenarios["neutral"])
        now = datetime.now(timezone.utc)
        headlines = [
            NewsItem(
                title=h, source="Synthetic", url="",
                published=now - timedelta(minutes=30 * (i + 1)),
                sentiment=s["raw"] + (0.05 * (2 - i)) * (1 if s["raw"] > 0 else -1),
                relevance=min(1.0, 0.9 - i * 0.1),
                keywords=["nifty", "market"],
                age_hours=(i + 1) * 0.5,
            )
            for i, h in enumerate(s["headlines"])
        ]

        return SentimentResult(
            bullish_score  = s["score"],
            sentiment_raw  = s["raw"],
            direction      = s["direction"],
            confidence     = s["confidence"],
            article_count  = len(headlines),
            relevant_count = len(headlines),
            top_headlines  = headlines,
            narrative      = f"Sentiment: {s['direction']} ({s['score']:.0f}/100) | {len(headlines)} market-relevant articles",
            factor_weight  = 0.12,
            timestamp      = now,
        )


# ── Module singleton ───────────────────────────────────────────────────────────
news_sentiment = NewsSentimentAnalyzer()
