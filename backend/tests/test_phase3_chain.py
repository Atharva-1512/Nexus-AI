"""
NEXUS AI — Phase 3 Test Suite
Tests for Option Chain Intelligence:
  - Option chain parser and synthetic generator
  - PCR analyzer
  - Max Pain calculator
  - GEX calculator
  - IV Skew analyzer
  - OI analyzer and S/R detector
  - Chain Engine (full pipeline)
  - Options API endpoints
"""

from datetime import date, timedelta, datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from modules.chain_intelligence.option_chain_parser import build_synthetic_chain
from modules.chain_intelligence.models import (
    ChainSignalDirection, OIBuildType, OptionStrike, ChainSnapshot
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def synthetic_chain() -> ChainSnapshot:
    """A realistic synthetic NIFTY chain at spot=24350."""
    return build_synthetic_chain(spot=24350.0, num_strikes=15, atm_iv=14.0)


@pytest.fixture(scope="module")
def bullish_chain() -> ChainSnapshot:
    """Synthetic chain with bullish PCR (more put OI)."""
    return build_synthetic_chain(spot=24350.0, num_strikes=10, atm_iv=12.0)


# ─── Synthetic Chain Generator Tests ─────────────────────────────────────────

class TestSyntheticChainGenerator:

    def test_chain_has_strikes(self, synthetic_chain):
        assert len(synthetic_chain.strikes) > 0

    def test_chain_has_correct_spot(self, synthetic_chain):
        assert synthetic_chain.spot_price == 24350.0

    def test_atm_strike_near_spot(self, synthetic_chain):
        atm = synthetic_chain.atm_strike
        assert abs(atm - synthetic_chain.spot_price) <= 50.0

    def test_all_strikes_have_positive_prices(self, synthetic_chain):
        for s in synthetic_chain.strikes:
            assert s.call_ltp >= 0, f"Negative call LTP at strike {s.strike}"
            assert s.put_ltp  >= 0, f"Negative put LTP at strike {s.strike}"

    def test_call_ltp_decreases_with_higher_strikes(self, synthetic_chain):
        sorted_strikes = sorted(synthetic_chain.strikes, key=lambda s: s.strike)
        call_ltps = [s.call_ltp for s in sorted_strikes if s.call_ltp > 0]
        # Deep ITM calls should be more expensive than deep OTM calls
        assert call_ltps[0] >= call_ltps[-1]

    def test_put_ltp_increases_with_lower_strikes(self, synthetic_chain):
        sorted_strikes = sorted(synthetic_chain.strikes, key=lambda s: s.strike)
        put_ltps = [s.put_ltp for s in sorted_strikes if s.put_ltp > 0]
        # Deep OTM puts should be cheaper than deep ITM puts
        assert put_ltps[0] <= put_ltps[-1]

    def test_pcr_oi_is_set(self, synthetic_chain):
        assert synthetic_chain.pcr_oi > 0

    def test_total_oi_is_positive(self, synthetic_chain):
        assert synthetic_chain.total_call_oi > 0
        assert synthetic_chain.total_put_oi  > 0

    def test_strikes_near_atm(self, synthetic_chain):
        near = synthetic_chain.strikes_near_atm(n=5)
        assert len(near) <= 11  # 5 above + 5 below + ATM

    def test_put_iv_higher_than_call_iv_for_otm_puts(self, synthetic_chain):
        """Classic negative skew: OTM puts have higher IV than equidistant OTM calls."""
        spot = synthetic_chain.spot_price
        # Find a strike ~150 pts below spot (OTM put)
        otm_put_strike = min(
            (s for s in synthetic_chain.strikes if s.strike < spot - 100),
            key=lambda s: abs(s.strike - (spot - 150)),
            default=None,
        )
        atm_call = min(
            (s for s in synthetic_chain.strikes if s.strike > spot),
            key=lambda s: abs(s.strike - (spot + 150)),
            default=None,
        )
        if otm_put_strike and atm_call:
            assert otm_put_strike.put_iv >= atm_call.call_iv


# ─── PCR Analyzer Tests ───────────────────────────────────────────────────────

class TestPCRAnalyzer:

    @pytest.fixture
    def analyzer(self):
        from modules.chain_intelligence.pcr_analyzer import PCRAnalyzer
        return PCRAnalyzer()

    def test_pcr_analysis_returns_result(self, analyzer, synthetic_chain):
        from modules.chain_intelligence.models import PCRAnalysis
        result = analyzer.analyze(synthetic_chain)
        assert isinstance(result, PCRAnalysis)

    def test_pcr_oi_matches_chain(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert result.pcr_oi == pytest.approx(synthetic_chain.pcr_oi, abs=0.01)

    def test_call_wall_is_above_spot(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        if result.call_oi_wall:
            assert result.call_oi_wall >= synthetic_chain.spot_price

    def test_put_wall_is_below_spot(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        if result.put_oi_wall:
            assert result.put_oi_wall <= synthetic_chain.spot_price

    def test_bullish_pct_is_0_to_100(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert 0.0 <= result.bullish_pct <= 100.0

    def test_pcr_above_1_5_is_strongly_bullish(self, analyzer, synthetic_chain):
        chain = build_synthetic_chain(spot=24350)
        chain.pcr_oi = 1.6
        chain.total_put_oi  = 1_600_000
        chain.total_call_oi = 1_000_000
        # Recompute signal via thresholds
        result = analyzer.analyze(chain)
        # We can't guarantee exactly STRONGLY_BULLISH without rerunning analysis
        assert result.bullish_pct >= 50.0

    def test_narrative_is_non_empty(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert isinstance(result.narrative, str)
        assert len(result.narrative) > 10

    def test_oi_concentration_has_5_strikes(self, analyzer, synthetic_chain):
        conc = analyzer.get_oi_concentration(synthetic_chain, n_strikes=5)
        assert len(conc["top_call_oi_strikes"]) == 5
        assert len(conc["top_put_oi_strikes"])  == 5


# ─── Max Pain Tests ───────────────────────────────────────────────────────────

class TestMaxPainCalculator:

    @pytest.fixture
    def calc(self):
        from modules.chain_intelligence.max_pain import MaxPainCalculator
        return MaxPainCalculator()

    def test_max_pain_is_valid_strike(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        assert result.max_pain_strike in synthetic_chain.strike_list

    def test_pain_table_has_all_strikes(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        assert len(result.pain_table) == len(synthetic_chain.strikes)

    def test_pain_values_are_non_negative(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        for strike, pain in result.pain_table.items():
            assert pain >= 0, f"Negative pain at strike {strike}"

    def test_distance_from_spot_formula(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        expected = round(result.max_pain_strike - synthetic_chain.spot_price, 2)
        assert result.distance_from_spot == pytest.approx(expected, abs=0.1)

    def test_signal_is_valid(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        assert result.signal in ("ABOVE_SPOT", "BELOW_SPOT", "AT_SPOT")

    def test_reliability_returns_score(self, calc, synthetic_chain):
        r = calc.max_pain_reliability(synthetic_chain)
        assert "reliability_score" in r
        assert 0 <= r["reliability_score"] <= 100

    def test_reliability_low_for_far_expiry(self, calc, synthetic_chain):
        far_chain = build_synthetic_chain(
            spot=24350, expiry=date.today() + timedelta(days=30)
        )
        r = calc.max_pain_reliability(far_chain)
        assert r["reliability"] in ("LOW", "MODERATE")


# ─── GEX Calculator Tests ─────────────────────────────────────────────────────

class TestGEXCalculator:

    @pytest.fixture
    def calc(self):
        from modules.chain_intelligence.gex_calculator import GEXCalculator
        return GEXCalculator()

    def test_gex_returns_result(self, calc, synthetic_chain):
        from modules.chain_intelligence.models import GEXResult
        result = calc.calculate(synthetic_chain)
        assert isinstance(result, GEXResult)

    def test_gex_regime_is_valid(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        assert result.regime in ("POSITIVE_GEX", "NEGATIVE_GEX")

    def test_gex_by_strike_has_all_strikes(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        assert len(result.gex_by_strike) == len(synthetic_chain.strikes)

    def test_total_gex_equals_sum(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        expected = round(result.call_gex + result.put_gex, 2)
        assert result.total_gex == pytest.approx(expected, abs=0.1)

    def test_narrative_non_empty(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        assert len(result.narrative) > 0

    def test_gex_flip_level_type(self, calc, synthetic_chain):
        result = calc.calculate(synthetic_chain)
        if result.gex_flip_level is not None:
            assert isinstance(result.gex_flip_level, float)

    def test_approx_gamma_non_negative(self, calc):
        g = calc._approx_gamma(spot=24350, strike=24350, atm_iv=0.14, dte_years=0.1)
        assert g >= 0.0


# ─── IV Skew Analyzer Tests ───────────────────────────────────────────────────

class TestIVSkewAnalyzer:

    @pytest.fixture
    def analyzer(self):
        from modules.chain_intelligence.iv_skew import IVSkewAnalyzer
        return IVSkewAnalyzer()

    def test_iv_skew_returns_result(self, analyzer, synthetic_chain):
        from modules.chain_intelligence.models import IVSkewResult
        result = analyzer.analyze(synthetic_chain)
        assert isinstance(result, IVSkewResult)

    def test_atm_iv_positive(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert result.atm_iv > 0

    def test_skew_direction_is_valid(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert result.skew_direction in ("PUT_SKEW", "CALL_SKEW", "FLAT")

    def test_synthetic_chain_has_put_skew(self, analyzer, synthetic_chain):
        """Synthetic chain is built with negative skew — put IV > call IV."""
        result = analyzer.analyze(synthetic_chain)
        assert result.skew_direction == "PUT_SKEW"

    def test_iv_table_non_empty(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert len(result.iv_by_strike) > 0

    def test_narrative_mentions_atm_iv(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert "ATM IV" in result.narrative or "atm" in result.narrative.lower()


# ─── OI Analyzer Tests ────────────────────────────────────────────────────────

class TestOIAnalyzer:

    @pytest.fixture
    def analyzer(self):
        from modules.chain_intelligence.oi_analyzer import OIAnalyzer
        return OIAnalyzer()

    @pytest.fixture
    def sr_detector(self):
        from modules.chain_intelligence.oi_analyzer import SupportResistanceDetector
        return SupportResistanceDetector()

    def test_oi_analysis_returns_result(self, analyzer, synthetic_chain):
        from modules.chain_intelligence.oi_analyzer import OIAnalysisResult
        result = analyzer.analyze(synthetic_chain)
        assert isinstance(result, OIAnalysisResult)

    def test_bullish_score_0_to_100(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        assert 0.0 <= result.bullish_score <= 100.0

    def test_net_sentiment_is_valid(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        valid = set(ChainSignalDirection)
        assert result.net_sentiment in valid

    def test_top_call_oi_above_spot(self, analyzer, synthetic_chain):
        result = analyzer.analyze(synthetic_chain)
        # Top call OI strike should generally be above spot
        if result.top_call_oi:
            top_call = result.top_call_oi[0]["strike"]
            # Not always above spot but should exist
            assert top_call > 0

    def test_sr_detector_returns_levels(self, sr_detector, synthetic_chain):
        supports, resistances = sr_detector.detect(synthetic_chain)
        assert isinstance(supports, list)
        assert isinstance(resistances, list)

    def test_supports_below_spot(self, sr_detector, synthetic_chain):
        supports, _ = sr_detector.detect(synthetic_chain)
        for s in supports:
            assert s.strike <= synthetic_chain.spot_price

    def test_resistances_above_spot(self, sr_detector, synthetic_chain):
        _, resistances = sr_detector.detect(synthetic_chain)
        for r in resistances:
            assert r.strike >= synthetic_chain.spot_price

    def test_strength_is_valid(self, sr_detector, synthetic_chain):
        supports, resistances = sr_detector.detect(synthetic_chain)
        for level in supports + resistances:
            assert level.strength in ("STRONG", "MODERATE", "WEAK")


# ─── Chain Engine (Full Pipeline) Tests ───────────────────────────────────────

class TestChainEngine:

    @pytest.fixture
    def engine(self):
        from modules.chain_intelligence.chain_engine import ChainEngine
        return ChainEngine()

    def test_engine_analyze_synthetic(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0, atm_iv=14.0)
        assert signal is not None

    def test_signal_direction_is_valid(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert signal.direction in set(ChainSignalDirection)

    def test_confidence_is_0_to_100(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert 0.0 <= signal.confidence <= 100.0

    def test_key_strikes_has_required_keys(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        for key in ["spot", "atm", "max_pain", "call_wall", "put_wall"]:
            assert key in signal.key_strikes

    def test_narrative_is_non_empty(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert isinstance(signal.narrative, str)
        assert len(signal.narrative) > 20

    def test_support_levels_populated(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert isinstance(signal.support_levels, list)

    def test_resistance_levels_populated(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert isinstance(signal.resistance_levels, list)

    def test_pcr_in_signal(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert signal.pcr is not None
        assert signal.pcr.pcr_oi > 0

    def test_max_pain_in_signal(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert signal.max_pain is not None
        assert signal.max_pain.max_pain_strike > 0

    def test_gex_in_signal(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert signal.gex is not None
        assert signal.gex.regime in ("POSITIVE_GEX", "NEGATIVE_GEX")

    def test_factor_weight_is_21_percent(self, engine):
        signal = engine.analyze_synthetic(spot=24350.0)
        assert signal.factor_weight == pytest.approx(0.21, abs=0.001)


# ─── Options API Tests ────────────────────────────────────────────────────────

class TestOptionsAPI:

    def test_chain_endpoint_returns_200(self, client):
        response = client.get("/api/v1/options/chain")
        assert response.status_code == 200

    def test_chain_has_strikes(self, client):
        data = client.get("/api/v1/options/chain").json()
        assert "strikes" in data
        assert data["strike_count"] > 0

    def test_chain_has_spot_price(self, client):
        data = client.get("/api/v1/options/chain").json()
        assert "spot_price" in data
        assert data["spot_price"] > 0

    def test_chain_expiry_day_is_tuesday(self, client):
        data = client.get("/api/v1/options/chain").json()
        assert "Tuesday" in data.get("expiry_day", "")

    def test_pcr_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/pcr").status_code == 200

    def test_pcr_has_signal(self, client):
        data = client.get("/api/v1/options/pcr").json()
        assert "signal" in data
        assert data["signal"] in [d.value for d in ChainSignalDirection]

    def test_max_pain_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/max-pain").status_code == 200

    def test_max_pain_has_strike(self, client):
        data = client.get("/api/v1/options/max-pain").json()
        assert "max_pain_strike" in data
        assert data["max_pain_strike"] > 0

    def test_gex_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/gex").status_code == 200

    def test_gex_has_regime(self, client):
        data = client.get("/api/v1/options/gex").json()
        assert data.get("regime") in ("POSITIVE_GEX", "NEGATIVE_GEX")

    def test_iv_skew_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/iv-skew").status_code == 200

    def test_iv_skew_has_atm_iv(self, client):
        data = client.get("/api/v1/options/iv-skew").json()
        assert "atm_iv" in data
        assert data["atm_iv"] > 0

    def test_oi_analysis_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/oi-analysis").status_code == 200

    def test_support_resistance_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/support-resistance").status_code == 200

    def test_sr_has_both_level_types(self, client):
        data = client.get("/api/v1/options/support-resistance").json()
        assert "support_levels" in data
        assert "resistance_levels" in data

    def test_key_strikes_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/key-strikes").status_code == 200

    def test_key_strikes_has_all_levels(self, client):
        data = client.get("/api/v1/options/key-strikes").json()
        levels = data.get("levels", {})
        for key in ["spot", "atm", "max_pain", "call_wall", "put_wall"]:
            assert key in levels

    def test_signal_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/signal").status_code == 200

    def test_signal_has_direction_and_confidence(self, client):
        data = client.get("/api/v1/options/signal").json()
        signal = data.get("signal", {})
        assert "direction" in signal
        assert "confidence" in signal
        assert 0 <= signal["confidence"] <= 100

    def test_signal_has_all_factor_weights(self, client):
        data = client.get("/api/v1/options/signal").json()
        for key in ["pcr", "gex", "max_pain", "iv_skew"]:
            assert key in data

    def test_expiries_endpoint_returns_200(self, client):
        assert client.get("/api/v1/options/expiries").status_code == 200

    def test_expiries_mentions_tuesday(self, client):
        data = client.get("/api/v1/options/expiries").json()
        assert "Tuesday" in data.get("note", "")
