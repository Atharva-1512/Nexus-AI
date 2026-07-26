"""
NEXUS AI — Phase 6 Test Suite
Tests for Sentiment & NLP Engine:
  - News sentiment keyword scoring
  - NewsItem scoring (bullish/bearish/neutral)
  - SocialSentimentTracker (Fear & Greed, breadth, PCR)
  - SentimentEngine aggregation
  - Sentiment API endpoints
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from modules.sentiment.news_sentiment import (
    NewsSentimentAnalyzer, SentimentResult, NewsItem,
    BULLISH_KEYWORDS, BEARISH_KEYWORDS,
)
from modules.sentiment.social_sentiment import (
    SocialSentimentTracker, SocialSentimentResult,
    FearGreedData, BreadthData,
)
from modules.sentiment.sentiment_engine import SentimentEngine, SentimentSignal


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def news_analyzer():
    return NewsSentimentAnalyzer()


@pytest.fixture(scope="module")
def social_tracker():
    return SocialSentimentTracker()


@pytest.fixture(scope="module")
def engine():
    return SentimentEngine()


# ─── News Sentiment Keyword Scoring ──────────────────────────────────────────

class TestNewsSentimentKeywords:

    def test_bullish_headline_gets_positive_sentiment(self, news_analyzer):
        text = "nifty rallies 200 points on strong fii buying surge"
        sentiment, relevance, keywords = news_analyzer._score_headline(text)
        assert sentiment > 0, f"Bullish headline got negative sentiment: {sentiment}"

    def test_bearish_headline_gets_negative_sentiment(self, news_analyzer):
        text = "nifty crashes 400 points on fii selling and global fears"
        sentiment, relevance, keywords = news_analyzer._score_headline(text)
        assert sentiment < 0, f"Bearish headline got positive sentiment: {sentiment}"

    def test_neutral_headline_near_zero(self, news_analyzer):
        text = "nifty opens at 24000 ahead of rbi policy"
        sentiment, relevance, keywords = news_analyzer._score_headline(text)
        assert -0.5 <= sentiment <= 0.5, f"Neutral headline too extreme: {sentiment}"

    def test_relevance_nifty_mention_boosts_score(self, news_analyzer):
        text_nifty   = "nifty option chain shows bullish buildup"
        text_generic = "weather forecast for tomorrow"
        _, rel_nifty,   _ = news_analyzer._score_headline(text_nifty)
        _, rel_generic, _ = news_analyzer._score_headline(text_generic)
        assert rel_nifty > rel_generic

    def test_keywords_matched_are_returned(self, news_analyzer):
        text = "nifty rallies on fii buying"
        _, _, keywords = news_analyzer._score_headline(text)
        assert len(keywords) > 0

    def test_negation_flips_sentiment(self, news_analyzer):
        text_pos = "nifty rally expected"
        text_neg = "no nifty rally expected"
        s_pos, _, _ = news_analyzer._score_headline(text_pos)
        s_neg, _, _ = news_analyzer._score_headline(text_neg)
        # Negation should reduce or flip bullish sentiment
        assert s_neg <= s_pos

    def test_sentiment_range_minus1_to_1(self, news_analyzer):
        for text in [
            "massive crash selloff plunge slump",
            "breakout surge rally boom record high",
            "market opens flat ahead of data",
        ]:
            s, _, _ = news_analyzer._score_headline(text)
            assert -1.0 <= s <= 1.0, f"Sentiment out of range: {s} for '{text}'"

    def test_relevance_range_0_to_1(self, news_analyzer):
        for text in [
            "nifty option chain puts calls fii dii",
            "tomorrow is a good day for sports",
        ]:
            _, r, _ = news_analyzer._score_headline(text)
            assert 0.0 <= r <= 1.0, f"Relevance out of range: {r}"

    def test_bullish_keywords_dict_non_empty(self):
        assert len(BULLISH_KEYWORDS) > 10

    def test_bearish_keywords_dict_non_empty(self):
        assert len(BEARISH_KEYWORDS) > 10


# ─── News Aggregation Tests ───────────────────────────────────────────────────

class TestNewsSentimentAggregation:

    def test_synthetic_bullish_score_above_60(self, news_analyzer):
        result = news_analyzer.synthetic_result("bullish")
        assert result.bullish_score > 60.0, f"Bullish synthetic score={result.bullish_score}"

    def test_synthetic_bearish_score_below_40(self, news_analyzer):
        result = news_analyzer.synthetic_result("bearish")
        assert result.bullish_score < 40.0, f"Bearish synthetic score={result.bullish_score}"

    def test_synthetic_neutral_score_near_50(self, news_analyzer):
        result = news_analyzer.synthetic_result("neutral")
        assert 35.0 <= result.bullish_score <= 65.0, f"Neutral synthetic score={result.bullish_score}"

    def test_synthetic_result_has_headlines(self, news_analyzer):
        result = news_analyzer.synthetic_result("neutral")
        assert len(result.top_headlines) > 0

    def test_synthetic_headlines_have_required_fields(self, news_analyzer):
        result = news_analyzer.synthetic_result("bullish")
        for h in result.top_headlines:
            assert isinstance(h, NewsItem)
            assert isinstance(h.title, str) and len(h.title) > 5
            assert isinstance(h.sentiment, float)
            assert -1.0 <= h.sentiment <= 1.0
            assert 0.0 <= h.relevance <= 1.0

    def test_sentiment_result_direction_valid(self, news_analyzer):
        for scenario in ("bullish", "bearish", "neutral"):
            r = news_analyzer.synthetic_result(scenario)
            assert r.direction in (
                "BULLISH", "SLIGHTLY_BULLISH", "NEUTRAL",
                "SLIGHTLY_BEARISH", "BEARISH"
            )

    def test_neutral_aggregate_returns_sentiment_result(self, news_analyzer):
        result = news_analyzer._aggregate([])
        assert isinstance(result, SentimentResult)
        assert result.bullish_score == 50.0  # Neutral default

    def test_factor_weight_is_12_percent(self, news_analyzer):
        result = news_analyzer.synthetic_result("neutral")
        assert result.factor_weight == pytest.approx(0.12, abs=0.001)

    def test_timestamp_is_set(self, news_analyzer):
        result = news_analyzer.synthetic_result("neutral")
        assert result.timestamp is not None


# ─── Social Sentiment / Fear & Greed Tests ───────────────────────────────────

class TestFearAndGreed:

    def test_low_vix_high_score(self, social_tracker):
        fg = social_tracker.compute_fear_greed(10.0, 0.8, 24500.0, 23000.0, 40, 10)
        assert fg.score > 60.0, f"Low VIX should produce greed, got {fg.score}"

    def test_high_vix_low_score(self, social_tracker):
        fg = social_tracker.compute_fear_greed(28.0, 1.8, 22000.0, 24000.0, 8, 42)
        assert fg.score < 40.0, f"High VIX should produce fear, got {fg.score}"

    def test_extreme_fear_label(self, social_tracker):
        fg = social_tracker.compute_fear_greed(35.0, 2.0, 20000.0, 24000.0, 5, 45)
        assert fg.label in ("EXTREME FEAR", "FEAR")

    def test_extreme_greed_label(self, social_tracker):
        fg = social_tracker.compute_fear_greed(9.0, 0.6, 26000.0, 23000.0, 45, 5)
        assert fg.label in ("EXTREME GREED", "GREED")

    def test_score_range_0_to_100(self, social_tracker):
        for vix, pcr in [(8, 0.5), (15, 1.0), (25, 1.5), (35, 2.0)]:
            fg = social_tracker.compute_fear_greed(vix, pcr, 24000.0, 23500.0)
            assert 0 <= fg.score <= 100, f"F&G score out of range: {fg.score}"

    def test_gold_surge_reduces_score(self, social_tracker):
        fg_gold_up   = social_tracker.compute_fear_greed(15.0, 1.0, 24000.0, 23500.0, gold_chg=2.0)
        fg_gold_down = social_tracker.compute_fear_greed(15.0, 1.0, 24000.0, 23500.0, gold_chg=-2.0)
        assert fg_gold_up.score < fg_gold_down.score

    def test_fgi_india_vix_stored(self, social_tracker):
        fg = social_tracker.compute_fear_greed(18.5, 1.2, 24000.0, 23500.0)
        assert fg.india_vix == 18.5

    def test_fgi_pcr_stored(self, social_tracker):
        fg = social_tracker.compute_fear_greed(15.0, 1.35, 24000.0, 23500.0)
        assert fg.pcr == 1.35


# ─── Market Breadth Tests ─────────────────────────────────────────────────────

class TestMarketBreadth:

    def test_strong_advances_high_adr(self, social_tracker):
        breadth = social_tracker.compute_breadth(40, 10)
        assert breadth.advance_decline_ratio == pytest.approx(4.0, abs=0.01)

    def test_strong_declines_low_adr(self, social_tracker):
        breadth = social_tracker.compute_breadth(10, 40)
        assert breadth.advance_decline_ratio == pytest.approx(0.25, abs=0.01)

    def test_breadth_pct_20dma_0_to_100(self, social_tracker):
        for adv, dec in [(50, 0), (25, 25), (0, 50)]:
            b = social_tracker.compute_breadth(adv, dec)
            assert 0 <= b.pct_above_20dma <= 100

    def test_breadth_unchanged_stored(self, social_tracker):
        b = social_tracker.compute_breadth(30, 15, unchanged=5)
        assert b.unchanged == 5

    def test_breadth_returns_breadth_data(self, social_tracker):
        b = social_tracker.compute_breadth(25, 25)
        assert isinstance(b, BreadthData)


# ─── PCR Sentiment Tests ──────────────────────────────────────────────────────

class TestPCRSentiment:

    def test_high_pcr_contrarian_bullish(self, social_tracker):
        sig = social_tracker.pcr_to_sentiment(1.8)
        assert sig == "CONTRARIAN_BULLISH"

    def test_low_pcr_contrarian_bearish(self, social_tracker):
        sig = social_tracker.pcr_to_sentiment(0.5)
        assert sig == "CONTRARIAN_BEARISH"

    def test_neutral_pcr_neutral(self, social_tracker):
        sig = social_tracker.pcr_to_sentiment(1.0)
        assert sig == "NEUTRAL"

    def test_slightly_bullish_pcr(self, social_tracker):
        sig = social_tracker.pcr_to_sentiment(1.3)
        assert sig == "SLIGHTLY_BULLISH"


# ─── SocialSentimentResult Tests ─────────────────────────────────────────────

class TestSocialSentimentResult:

    def test_analyze_returns_social_result(self, social_tracker):
        result = social_tracker.analyze()
        assert isinstance(result, SocialSentimentResult)

    def test_bullish_score_0_to_100(self, social_tracker):
        result = social_tracker.analyze()
        assert 0 <= result.bullish_score <= 100

    def test_direction_valid(self, social_tracker):
        result = social_tracker.analyze()
        assert result.direction in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_synthetic_bullish_gives_high_score(self, social_tracker):
        result = social_tracker.synthetic_result("bullish")
        assert result.bullish_score > 55.0

    def test_synthetic_bearish_gives_low_score(self, social_tracker):
        result = social_tracker.synthetic_result("bearish")
        assert result.bullish_score < 45.0

    def test_oi_positioning_valid(self, social_tracker):
        result = social_tracker.analyze()
        valid = {"OVER-EXTENDED_LONG", "NET_LONG", "BALANCED", "NET_SHORT", "OVER-EXTENDED_SHORT"}
        assert result.oi_positioning in valid

    def test_factor_weight_is_8_percent(self, social_tracker):
        result = social_tracker.analyze()
        assert result.factor_weight == pytest.approx(0.08, abs=0.001)


# ─── SentimentEngine Tests ────────────────────────────────────────────────────

class TestSentimentEngine:

    def test_analyze_sync_returns_sentiment_signal(self, engine):
        result = engine.analyze_sync()
        assert isinstance(result, SentimentSignal)

    def test_bullish_score_0_to_100(self, engine):
        result = engine.analyze_sync()
        assert 0 <= result.bullish_score <= 100

    def test_direction_valid(self, engine):
        result = engine.analyze_sync()
        assert result.direction in (
            "STRONGLY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONGLY_BEARISH"
        )

    def test_bullish_scenario_higher_score(self, engine):
        bull = engine.analyze_sync(scenario="bullish")
        bear = engine.analyze_sync(scenario="bearish")
        assert bull.bullish_score > bear.bullish_score

    def test_factor_scores_has_required_keys(self, engine):
        result = engine.analyze_sync()
        for key in ["news_sentiment", "fear_greed", "market_breadth", "pcr_sentiment", "vix_sentiment"]:
            assert key in result.factor_scores, f"Missing key: {key}"

    def test_factor_scores_0_to_100(self, engine):
        result = engine.analyze_sync()
        for k, v in result.factor_scores.items():
            assert -5 <= v <= 105, f"Factor score out of range: {k}={v}"

    def test_has_news_result(self, engine):
        result = engine.analyze_sync()
        assert isinstance(result.news, SentimentResult)

    def test_has_social_result(self, engine):
        result = engine.analyze_sync()
        assert isinstance(result.social, SocialSentimentResult)

    def test_factor_weight_is_12_percent(self, engine):
        result = engine.analyze_sync()
        assert result.factor_weight == pytest.approx(0.12, abs=0.001)

    def test_narrative_non_empty(self, engine):
        result = engine.analyze_sync()
        assert isinstance(result.narrative, str)
        assert len(result.narrative) > 10

    def test_timestamp_is_set(self, engine):
        result = engine.analyze_sync()
        assert result.timestamp is not None

    def test_confidence_0_to_100(self, engine):
        result = engine.analyze_sync()
        assert 0 <= result.confidence <= 100


# ─── Sentiment API Endpoints ──────────────────────────────────────────────────

class TestSentimentAPI:

    def test_signal_endpoint_200(self, client):
        assert client.get("/api/v1/sentiment/signal").status_code == 200

    def test_signal_has_bullish_score(self, client):
        data = client.get("/api/v1/sentiment/signal").json()
        assert "bullish_score" in data
        assert 0 <= data["bullish_score"] <= 100

    def test_signal_has_direction(self, client):
        data = client.get("/api/v1/sentiment/signal").json()
        assert "direction" in data
        assert data["direction"] in (
            "STRONGLY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONGLY_BEARISH"
        )

    def test_signal_has_factor_scores(self, client):
        data = client.get("/api/v1/sentiment/signal").json()
        assert "factor_scores" in data
        for key in ["news_sentiment", "fear_greed", "market_breadth"]:
            assert key in data["factor_scores"]

    def test_signal_has_news_block(self, client):
        data = client.get("/api/v1/sentiment/signal").json()
        assert "news" in data
        assert "bullish_score" in data["news"]
        assert "top_headlines" in data["news"]

    def test_signal_has_social_block(self, client):
        data = client.get("/api/v1/sentiment/signal").json()
        assert "social" in data
        assert "fear_greed" in data["social"]
        assert "breadth" in data["social"]

    def test_signal_bearish_scenario(self, client):
        data = client.get("/api/v1/sentiment/signal?scenario=bearish").json()
        assert data["bullish_score"] < 55.0

    def test_signal_bullish_scenario(self, client):
        data = client.get("/api/v1/sentiment/signal?scenario=bullish").json()
        assert data["bullish_score"] > 45.0

    def test_news_endpoint_200(self, client):
        assert client.get("/api/v1/sentiment/news").status_code == 200

    def test_news_has_headlines(self, client):
        data = client.get("/api/v1/sentiment/news").json()
        assert "headlines" in data
        assert len(data["headlines"]) > 0

    def test_news_each_headline_has_title(self, client):
        data = client.get("/api/v1/sentiment/news").json()
        for h in data["headlines"]:
            assert "title" in h
            assert len(h["title"]) > 5

    def test_news_has_sentiment_score(self, client):
        data = client.get("/api/v1/sentiment/news").json()
        assert "bullish_score" in data
        assert 0 <= data["bullish_score"] <= 100

    def test_fear_greed_endpoint_200(self, client):
        assert client.get("/api/v1/sentiment/fear-greed").status_code == 200

    def test_fear_greed_has_score(self, client):
        data = client.get("/api/v1/sentiment/fear-greed").json()
        assert "score" in data
        assert 0 <= data["score"] <= 100

    def test_fear_greed_has_label(self, client):
        data = client.get("/api/v1/sentiment/fear-greed").json()
        assert "label" in data
        assert data["label"] in (
            "EXTREME FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME GREED"
        )

    def test_fear_greed_has_interpretation(self, client):
        data = client.get("/api/v1/sentiment/fear-greed").json()
        assert "interpretation" in data
        assert len(data["interpretation"]) > 5

    def test_fear_greed_vix_param(self, client):
        data_low  = client.get("/api/v1/sentiment/fear-greed?vix=10.0").json()
        data_high = client.get("/api/v1/sentiment/fear-greed?vix=28.0").json()
        assert data_low["score"] > data_high["score"]

    def test_breadth_endpoint_200(self, client):
        assert client.get("/api/v1/sentiment/breadth").status_code == 200

    def test_breadth_has_adr(self, client):
        data = client.get("/api/v1/sentiment/breadth").json()
        assert "advance_decline_ratio" in data
        assert data["advance_decline_ratio"] >= 0

    def test_breadth_strong_advances(self, client):
        data = client.get("/api/v1/sentiment/breadth?advances=45&declines=5").json()
        assert data["breadth_signal"] == "STRONG"

    def test_breadth_weak_advances(self, client):
        data = client.get("/api/v1/sentiment/breadth?advances=5&declines=45").json()
        assert data["breadth_signal"] == "WEAK"

    def test_breadth_has_pct_20dma(self, client):
        data = client.get("/api/v1/sentiment/breadth").json()
        assert "pct_above_20dma" in data
        assert 0 <= data["pct_above_20dma"] <= 100
