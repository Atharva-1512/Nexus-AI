"""
NEXUS AI — Phase 7 Test Suite
Tests for the Master Decision Engine:
  - DecisionEngine core logic (thresholds, confidence, recommendation)
  - OptionRecommendation (strike, expiry, R:R)
  - SignalAggregator (runs full pipeline with synthetic data)
  - Decision API endpoints (/recommend, /factors, /trade)
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from modules.decision_engine.decision_engine import (
    DecisionEngine, DecisionEngineOutput, Recommendation, ConfidenceLevel,
    FactorContribution, SIGNAL_WEIGHTS, NIFTY_LOT_SIZE,
    next_tuesday, nearest_strike, decision_engine,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def engine():
    return DecisionEngine()


# ─── Utility Function Tests ────────────────────────────────────────────────────

class TestUtilityFunctions:

    def test_next_tuesday_returns_string(self):
        result = next_tuesday()
        assert isinstance(result, str)
        assert len(result) == 10  # YYYY-MM-DD

    def test_next_tuesday_is_tuesday(self):
        from datetime import datetime
        result = next_tuesday()
        dt = datetime.strptime(result, "%Y-%m-%d")
        assert dt.weekday() == 1, f"Expected Tuesday (1), got {dt.weekday()}"

    def test_nearest_strike_rounds_to_50(self):
        assert nearest_strike(24025.0) == 24000.0
        assert nearest_strike(24030.0) == 24050.0
        assert nearest_strike(24075.0) == 24100.0

    def test_nearest_strike_custom_interval(self):
        assert nearest_strike(24100.0, interval=100.0) == 24100.0

    def test_signal_weights_sum_to_1(self):
        total = sum(SIGNAL_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}"

    def test_signal_weights_has_6_factors(self):
        assert len(SIGNAL_WEIGHTS) == 6

    def test_nifty_lot_size_is_75(self):
        assert NIFTY_LOT_SIZE == 75


# ─── Decision Engine Core Tests ────────────────────────────────────────────────

class TestDecisionEngineCore:

    def test_compute_returns_output(self, engine):
        out = engine.compute(spot=24000.0)
        assert isinstance(out, DecisionEngineOutput)

    def test_recommendation_is_valid_enum(self, engine):
        out = engine.compute(spot=24000.0)
        assert out.recommendation in set(Recommendation)

    def test_confidence_0_to_100(self, engine):
        out = engine.compute(spot=24000.0)
        assert 0 <= out.confidence <= 100

    def test_bullish_score_0_to_100(self, engine):
        out = engine.compute(spot=24000.0)
        assert 0 <= out.bullish_score <= 100

    def test_strong_bullish_scores_recommend_call(self, engine):
        out = engine.compute(
            spot               = 24000.0,
            option_chain_score = 78.0, option_chain_evidence=["PCR bullish"],
            technical_score    = 72.0, technical_evidence=["RSI > 60"],
            macro_score        = 70.0, macro_evidence=["FII buying"],
            sentiment_score    = 68.0, sentiment_evidence=["News bullish"],
            greeks_score       = 65.0, greeks_evidence=["Low IV"],
            ml_score           = 66.0, ml_evidence=["LSTM bullish"],
        )
        assert out.recommendation == Recommendation.BUY_CALL
        assert out.direction == "BULLISH"

    def test_strong_bearish_scores_recommend_put(self, engine):
        out = engine.compute(
            spot               = 24000.0,
            option_chain_score = 22.0, option_chain_evidence=["PCR bearish"],
            technical_score    = 28.0, technical_evidence=["RSI < 40"],
            macro_score        = 25.0, macro_evidence=["FII selling"],
            sentiment_score    = 30.0, sentiment_evidence=["News bearish"],
            greeks_score       = 28.0, greeks_evidence=["High IV"],
            ml_score           = 25.0, ml_evidence=["LSTM bearish"],
        )
        assert out.recommendation == Recommendation.BUY_PUT
        assert out.direction == "BEARISH"

    def test_mixed_signals_avoid_or_wait(self, engine):
        out = engine.compute(
            spot               = 24000.0,
            option_chain_score = 55.0,
            technical_score    = 48.0,
            macro_score        = 52.0,
            sentiment_score    = 49.0,
        )
        assert out.recommendation in (Recommendation.AVOID, Recommendation.WAIT)

    def test_neutral_scores_return_neutral_direction(self, engine):
        out = engine.compute(
            spot=24000.0,
            option_chain_score=50.0, technical_score=50.0,
            macro_score=50.0, sentiment_score=50.0,
        )
        assert out.direction == "NEUTRAL"

    def test_factors_list_has_6_items(self, engine):
        out = engine.compute(spot=24000.0)
        assert len(out.factors) == 6

    def test_factor_weights_sum_to_1(self, engine):
        out = engine.compute(spot=24000.0)
        total = sum(f.weight for f in out.factors)
        assert abs(total - 1.0) < 0.001

    def test_each_factor_has_required_fields(self, engine):
        out = engine.compute(spot=24000.0)
        for f in out.factors:
            assert isinstance(f, FactorContribution)
            assert f.name in SIGNAL_WEIGHTS
            assert 0 <= f.raw_score <= 100
            assert f.direction in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_missing_score_defaults_to_neutral(self, engine):
        out = engine.compute(spot=24000.0, option_chain_score=None)
        oc = next(f for f in out.factors if f.name == "option_chain")
        assert oc.available == False
        assert oc.raw_score == 50.0

    def test_available_flag_set_when_score_provided(self, engine):
        out = engine.compute(spot=24000.0, technical_score=70.0)
        tech = next(f for f in out.factors if f.name == "technical")
        assert tech.available == True

    def test_spot_price_stored(self, engine):
        out = engine.compute(spot=24350.5)
        assert out.spot_price == 24350.5

    def test_macro_regime_stored(self, engine):
        out = engine.compute(spot=24000.0, macro_regime="RISK_ON")
        assert out.macro_regime == "RISK_ON"

    def test_size_multiplier_stored(self, engine):
        out = engine.compute(spot=24000.0, size_multiplier=0.50)
        assert out.size_multiplier == 0.50

    def test_confidence_level_valid(self, engine):
        out = engine.compute(spot=24000.0)
        assert out.confidence_level in set(ConfidenceLevel)

    def test_narrative_non_empty(self, engine):
        out = engine.compute(spot=24000.0)
        assert isinstance(out.narrative, str) and len(out.narrative) > 10

    def test_reasoning_is_list(self, engine):
        out = engine.compute(spot=24000.0)
        assert isinstance(out.reasoning, list)
        assert len(out.reasoning) >= 3

    def test_timestamp_set(self, engine):
        out = engine.compute(spot=24000.0)
        assert out.timestamp is not None

    def test_factor_scores_dict_has_all_keys(self, engine):
        out = engine.compute(spot=24000.0)
        for key in SIGNAL_WEIGHTS:
            assert key in out.factor_scores

    def test_factor_weights_dict_correct(self, engine):
        out = engine.compute(spot=24000.0)
        assert abs(out.factor_weights["option_chain"] - 0.30) < 0.001
        assert abs(out.factor_weights["technical"] - 0.20) < 0.001


# ─── OptionRecommendation Tests ────────────────────────────────────────────────

class TestOptionRecommendation:

    def _make_call_rec(self, engine):
        return engine.compute(
            spot=24000.0,
            option_chain_score=78.0, option_chain_evidence=["Bullish OI"],
            technical_score=72.0, technical_evidence=["RSI 65"],
            macro_score=70.0, macro_evidence=["FII buy"],
            sentiment_score=68.0, sentiment_evidence=["News pos"],
            greeks_score=65.0, greeks_evidence=["Low IV"],
            ml_score=67.0, ml_evidence=["LSTM up"],
        )

    def test_call_rec_has_trade(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade is not None

    def test_call_option_type_is_ce(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.option_type == "CE"

    def test_expiry_is_tuesday(self, engine):
        out = self._make_call_rec(engine)
        from datetime import datetime
        dt = datetime.strptime(out.trade.expiry, "%Y-%m-%d")
        assert dt.weekday() == 1

    def test_strike_is_multiple_of_50(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.strike % 50 == 0

    def test_target_1r_above_entry(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.target_1r > out.trade.premium_est

    def test_target_2r_above_target_1r(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.target_2r >= out.trade.target_1r

    def test_stop_loss_below_entry(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.stop_loss < out.trade.premium_est

    def test_risk_reward_positive(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.risk_reward > 0

    def test_lot_size_is_75(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.lot_size == 75

    def test_max_lots_positive(self, engine):
        out = self._make_call_rec(engine)
        assert out.trade.max_lots >= 1

    def test_avoid_has_no_trade(self, engine):
        out = engine.compute(
            spot=24000.0,
            option_chain_score=50.0, technical_score=50.0,
            macro_score=50.0, sentiment_score=50.0,
        )
        # Neutral signals should result in no trade
        if out.recommendation in (Recommendation.AVOID, Recommendation.WAIT):
            assert out.trade is None


# ─── Confidence Level Tests ────────────────────────────────────────────────────

class TestConfidenceLevels:

    def test_very_high_confidence(self, engine):
        out = engine.compute(
            spot=24000.0,
            option_chain_score=80.0, technical_score=78.0,
            macro_score=75.0, sentiment_score=72.0,
            greeks_score=70.0, ml_score=68.0,
        )
        assert out.confidence_level in (ConfidenceLevel.VERY_HIGH, ConfidenceLevel.HIGH)

    def test_very_low_confidence_no_data(self, engine):
        out = engine.compute(spot=24000.0)  # All None → all neutral
        # Low signal strength should produce AVOID or WAIT
        assert out.recommendation in (Recommendation.AVOID, Recommendation.WAIT)


# ─── Signal Aggregator Tests ───────────────────────────────────────────────────

class TestSignalAggregator:

    @pytest.fixture(scope="class")
    def agg(self):
        from modules.decision_engine.aggregator import SignalAggregator
        return SignalAggregator()

    @pytest.mark.asyncio
    async def test_run_returns_output(self, agg):
        out = await agg.run(spot=24000.0, scenario="neutral")
        assert isinstance(out, DecisionEngineOutput)

    @pytest.mark.asyncio
    async def test_bullish_scenario_gives_higher_score(self, agg):
        bull = await agg.run(spot=24000.0, scenario="bullish")
        bear = await agg.run(spot=24000.0, scenario="bearish")
        assert bull.bullish_score > bear.bullish_score

    @pytest.mark.asyncio
    async def test_bullish_scenario_recommends_call_or_wait(self, agg):
        out = await agg.run(spot=24000.0, scenario="bullish")
        assert out.recommendation in (
            Recommendation.BUY_CALL, Recommendation.WAIT, Recommendation.AVOID
        )

    @pytest.mark.asyncio
    async def test_bearish_scenario_recommends_put_or_wait(self, agg):
        out = await agg.run(spot=24000.0, scenario="bearish")
        assert out.recommendation in (
            Recommendation.BUY_PUT, Recommendation.WAIT, Recommendation.AVOID
        )

    @pytest.mark.asyncio
    async def test_run_all_factors_present(self, agg):
        out = await agg.run(spot=24000.0, scenario="neutral")
        names = {f.name for f in out.factors}
        assert "option_chain" in names
        assert "technical" in names
        assert "macro" in names
        assert "sentiment" in names


# ─── Decision API Endpoint Tests ───────────────────────────────────────────────

class TestDecisionAPI:

    def test_recommend_endpoint_200(self, client):
        assert client.get("/api/v1/decision/recommend").status_code == 200

    def test_recommend_has_recommendation(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "recommendation" in data
        assert data["recommendation"] in ("BUY_CALL", "BUY_PUT", "AVOID", "WAIT")

    def test_recommend_has_confidence(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "confidence" in data
        assert 0 <= data["confidence"] <= 100

    def test_recommend_has_bullish_score(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "bullish_score" in data
        assert 0 <= data["bullish_score"] <= 100

    def test_recommend_has_direction(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "direction" in data
        assert data["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_recommend_has_factors(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "factors" in data
        assert len(data["factors"]) == 6

    def test_recommend_each_factor_has_evidence(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        for f in data["factors"]:
            assert "evidence" in f
            assert isinstance(f["evidence"], list)

    def test_recommend_has_macro_regime(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "macro_regime" in data

    def test_recommend_has_reasoning(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "reasoning" in data
        assert isinstance(data["reasoning"], list)

    def test_recommend_bullish_scenario(self, client):
        data = client.get("/api/v1/decision/recommend?scenario=bullish&spot=24000").json()
        assert data["bullish_score"] > 50.0

    def test_recommend_bearish_scenario(self, client):
        data = client.get("/api/v1/decision/recommend?scenario=bearish&spot=24000").json()
        assert data["bullish_score"] < 50.0

    def test_factors_endpoint_200(self, client):
        assert client.get("/api/v1/decision/factors").status_code == 200

    def test_factors_has_bullish_score(self, client):
        data = client.get("/api/v1/decision/factors").json()
        assert "bullish_score" in data

    def test_factors_has_direction(self, client):
        data = client.get("/api/v1/decision/factors").json()
        assert "direction" in data

    def test_factors_list_present(self, client):
        data = client.get("/api/v1/decision/factors").json()
        assert "factors" in data
        assert len(data["factors"]) == 6

    def test_trade_endpoint_200(self, client):
        assert client.get("/api/v1/decision/trade").status_code == 200

    def test_trade_bullish_has_action(self, client):
        data = client.get("/api/v1/decision/trade?scenario=bullish&spot=24000").json()
        assert "action" in data

    def test_trade_bullish_action_valid(self, client):
        data = client.get("/api/v1/decision/trade?scenario=bullish&spot=24000").json()
        assert data["action"] in ("BUY_CALL", "BUY_PUT", "AVOID", "WAIT")

    def test_trade_has_generated_at(self, client):
        data = client.get("/api/v1/decision/recommend").json()
        assert "generated_at" in data
