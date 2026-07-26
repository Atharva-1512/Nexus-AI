"""
NEXUS AI — Phase 5 Test Suite
Tests for Macro Intelligence Engine:
  - MacroSnapshot data structure
  - MacroEngine signal scoring
  - MacroRegimeClassifier (all 6 regimes)
  - Macro API endpoints
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from modules.macro.macro_engine import MacroEngine, MacroSnapshot, GlobalIndexSnapshot
from modules.macro.regime_classifier import (
    MacroRegimeClassifier, MacroRegime, RegimeAnalysis,
    REGIME_DESCRIPTIONS, REGIME_SIZE_MULTIPLIER,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def engine():
    return MacroEngine()


@pytest.fixture(scope="module")
def classifier():
    return MacroRegimeClassifier()


# ─── MacroEngine Synthetic Scenarios ─────────────────────────────────────────

class TestMacroEngineSynthetic:

    def test_neutral_snapshot_returns_macrosnapshot(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        assert isinstance(snap, MacroSnapshot)

    def test_bullish_snapshot_higher_global_bias(self, engine):
        bull = engine.synthetic_snapshot("bullish")
        neut = engine.synthetic_snapshot("neutral")
        assert bull.global_bias > neut.global_bias

    def test_bearish_snapshot_lower_global_bias(self, engine):
        bear = engine.synthetic_snapshot("bearish")
        neut = engine.synthetic_snapshot("neutral")
        assert bear.global_bias < neut.global_bias

    def test_snapshot_has_indices(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        assert isinstance(snap.indices, list)
        assert len(snap.indices) > 0

    def test_each_index_has_required_fields(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        for idx in snap.indices:
            assert isinstance(idx, GlobalIndexSnapshot)
            assert idx.name != ""
            assert idx.signal in ("BULLISH", "BEARISH", "NEUTRAL", "SLIGHTLY_BULLISH", "SLIGHTLY_BEARISH")

    def test_usdinr_is_realistic(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        assert 70.0 <= snap.usdinr <= 90.0, f"USD/INR={snap.usdinr} seems unrealistic"

    def test_india_vix_is_positive(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        assert snap.india_vix > 0

    def test_combined_score_0_to_100(self, engine):
        for scenario in ("bullish", "neutral", "bearish"):
            snap = engine.synthetic_snapshot(scenario)
            assert 0 <= snap.combined_score <= 100, f"combined_score out of range in {scenario}"

    def test_macro_risk_0_to_100(self, engine):
        for scenario in ("bullish", "neutral", "bearish"):
            snap = engine.synthetic_snapshot(scenario)
            assert 0 <= snap.macro_risk <= 100

    def test_bearish_has_higher_macro_risk(self, engine):
        bear = engine.synthetic_snapshot("bearish")
        bull = engine.synthetic_snapshot("bullish")
        assert bear.macro_risk > bull.macro_risk

    def test_bullish_has_higher_combined_score(self, engine):
        bull = engine.synthetic_snapshot("bullish")
        bear = engine.synthetic_snapshot("bearish")
        assert bull.combined_score > bear.combined_score

    def test_fii_bullish_is_positive(self, engine):
        bull = engine.synthetic_snapshot("bullish")
        assert bull.fii_net_crore > 0

    def test_fii_bearish_is_negative(self, engine):
        bear = engine.synthetic_snapshot("bearish")
        assert bear.fii_net_crore < 0

    def test_narrative_is_non_empty_string(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        assert isinstance(snap.narrative, str)
        assert len(snap.narrative) > 10

    def test_timestamp_is_set(self, engine):
        snap = engine.synthetic_snapshot("neutral")
        assert snap.timestamp is not None


# ─── MacroEngine Signal Scoring ───────────────────────────────────────────────

class TestMacroEngineScoring:

    def test_chg_to_signal_strongly_up(self, engine):
        assert engine._chg_to_signal(1.5) == "BULLISH"

    def test_chg_to_signal_slightly_up(self, engine):
        assert engine._chg_to_signal(0.2) == "SLIGHTLY_BULLISH"

    def test_chg_to_signal_flat(self, engine):
        assert engine._chg_to_signal(0.0) == "NEUTRAL"

    def test_chg_to_signal_slightly_down(self, engine):
        assert engine._chg_to_signal(-0.2) == "SLIGHTLY_BEARISH"

    def test_chg_to_signal_strongly_down(self, engine):
        assert engine._chg_to_signal(-1.0) == "BEARISH"

    def test_signal_to_score_bullish_above_50(self, engine):
        score = engine._signal_to_score("BULLISH", 1.0)
        assert score > 50.0

    def test_signal_to_score_bearish_below_50(self, engine):
        score = engine._signal_to_score("BEARISH", -1.0)
        assert score < 50.0

    def test_signal_to_score_neutral_at_50(self, engine):
        score = engine._signal_to_score("NEUTRAL", 0.0)
        assert score == 50.0

    def test_macro_risk_high_vix_increases_risk(self, engine):
        risk_high = engine._compute_macro_risk(0.0, 0.0, 25.0, 0.0, 4.5, 0.0)
        risk_low  = engine._compute_macro_risk(0.0, 0.0, 10.0, 0.0, 4.5, 0.0)
        assert risk_high > risk_low

    def test_macro_risk_fii_buying_reduces_risk(self, engine):
        risk_buy  = engine._compute_macro_risk(0.0, 0.0, 15.0, 0.0, 4.5, 2000.0)
        risk_sell = engine._compute_macro_risk(0.0, 0.0, 15.0, 0.0, 4.5, -2000.0)
        assert risk_buy < risk_sell

    def test_macro_risk_crude_surge_increases_risk(self, engine):
        risk_up  = engine._compute_macro_risk(0.0, 3.0, 15.0, 0.0, 4.5, 0.0)
        risk_flat = engine._compute_macro_risk(0.0, 0.0, 15.0, 0.0, 4.5, 0.0)
        assert risk_up > risk_flat

    def test_macro_risk_weak_rupee_increases_risk(self, engine):
        risk_weak   = engine._compute_macro_risk(0.5, 0.0, 15.0, 0.0, 4.5, 0.0)
        risk_strong = engine._compute_macro_risk(-0.5, 0.0, 15.0, 0.0, 4.5, 0.0)
        assert risk_weak > risk_strong


# ─── MacroRegimeClassifier Tests ─────────────────────────────────────────────

class TestMacroRegimeClassifier:

    def _make_snap(self, **kwargs) -> MacroSnapshot:
        """Build a MacroSnapshot with overridable defaults."""
        from modules.macro.macro_engine import MacroEngine
        e    = MacroEngine()
        snap = e.synthetic_snapshot("neutral")
        for k, v in kwargs.items():
            object.__setattr__(snap, k, v)
        return snap

    def test_classify_returns_regime_analysis(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap = MacroEngine().synthetic_snapshot("neutral")
        result = classifier.classify(snap)
        assert isinstance(result, RegimeAnalysis)

    def test_regime_is_valid_macro_regime(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap   = MacroEngine().synthetic_snapshot("neutral")
        result = classifier.classify(snap)
        assert result.regime in set(MacroRegime)

    def test_confidence_0_to_100(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap   = MacroEngine().synthetic_snapshot("neutral")
        result = classifier.classify(snap)
        assert 0 <= result.confidence <= 100

    def test_bias_is_valid(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap   = MacroEngine().synthetic_snapshot("neutral")
        result = classifier.classify(snap)
        assert result.bias in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_risk_off_triggered_by_high_vix(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap   = MacroEngine().synthetic_snapshot("bearish")
        # Force extreme VIX
        import dataclasses
        snap = dataclasses.replace(snap, india_vix=25.0, fii_net_crore=-2000.0, global_bias=28.0)
        result = classifier.classify(snap)
        assert result.regime == MacroRegime.RISK_OFF
        assert result.bias == "BEARISH"

    def test_risk_on_triggered_by_low_vix_fii_buying(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        import dataclasses
        snap = MacroEngine().synthetic_snapshot("bullish")
        snap = dataclasses.replace(snap, india_vix=10.0, fii_net_crore=2000.0, global_bias=70.0)
        result = classifier.classify(snap)
        assert result.regime == MacroRegime.RISK_ON
        assert result.bias == "BULLISH"

    def test_stagflationary_triggered_by_crude_surge(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        import dataclasses
        snap = MacroEngine().synthetic_snapshot("neutral")
        snap = dataclasses.replace(snap, crude_chg_pct=3.0, crude_wti=95.0, global_bias=42.0)
        result = classifier.classify(snap)
        assert result.regime == MacroRegime.STAGFLATIONARY
        assert result.bias == "BEARISH"

    def test_rate_rising_triggered_by_high_yields(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        import dataclasses
        snap = MacroEngine().synthetic_snapshot("neutral")
        snap = dataclasses.replace(snap, us_10y_yield=5.1, us_10y_chg=8.0, dxy_chg_pct=0.7)
        result = classifier.classify(snap)
        assert result.regime == MacroRegime.RATE_RISING

    def test_size_multiplier_risk_on_is_1(self):
        assert REGIME_SIZE_MULTIPLIER[MacroRegime.RISK_ON] == 1.00

    def test_size_multiplier_risk_off_is_half(self):
        assert REGIME_SIZE_MULTIPLIER[MacroRegime.RISK_OFF] == 0.50

    def test_all_regimes_have_description(self):
        for regime in MacroRegime:
            assert regime in REGIME_DESCRIPTIONS
            assert len(REGIME_DESCRIPTIONS[regime]) > 10

    def test_triggers_are_list_of_strings(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap   = MacroEngine().synthetic_snapshot("bearish")
        result = classifier.classify(snap)
        assert isinstance(result.triggers, list)
        for t in result.triggers:
            assert isinstance(t, str)

    def test_description_is_non_empty(self, classifier):
        from modules.macro.macro_engine import MacroEngine
        snap   = MacroEngine().synthetic_snapshot("neutral")
        result = classifier.classify(snap)
        assert isinstance(result.description, str)
        assert len(result.description) > 5


# ─── Macro API Endpoints ─────────────────────────────────────────────────────

class TestMacroAPI:

    def test_snapshot_endpoint_200(self, client):
        assert client.get("/api/v1/macro/snapshot").status_code == 200

    def test_snapshot_has_global_bias(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "global_bias" in data
        assert 0 <= data["global_bias"] <= 100

    def test_snapshot_has_combined_score(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "combined_score" in data
        assert 0 <= data["combined_score"] <= 100

    def test_snapshot_has_usdinr(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "usdinr" in data
        assert data["usdinr"] > 0

    def test_snapshot_has_india_vix(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "india_vix" in data
        assert data["india_vix"] > 0

    def test_snapshot_has_indices_list(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "indices" in data
        assert isinstance(data["indices"], list)
        assert len(data["indices"]) > 0

    def test_snapshot_has_fii_fields(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "fii_net_crore" in data
        assert "dii_net_crore" in data

    def test_snapshot_has_narrative(self, client):
        data = client.get("/api/v1/macro/snapshot").json()
        assert "narrative" in data
        assert len(data["narrative"]) > 5

    def test_regime_endpoint_200(self, client):
        assert client.get("/api/v1/macro/regime").status_code == 200

    def test_regime_has_regime_field(self, client):
        data = client.get("/api/v1/macro/regime").json()
        assert "regime" in data
        assert data["regime"] in [r.value for r in MacroRegime]

    def test_regime_has_bias(self, client):
        data = client.get("/api/v1/macro/regime").json()
        assert "bias" in data
        assert data["bias"] in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_regime_has_size_multiplier(self, client):
        data = client.get("/api/v1/macro/regime").json()
        assert "size_multiplier" in data
        assert 0 < data["size_multiplier"] <= 1.0

    def test_regime_has_description(self, client):
        data = client.get("/api/v1/macro/regime").json()
        assert "description" in data
        assert len(data["description"]) > 5

    def test_regime_has_triggers(self, client):
        data = client.get("/api/v1/macro/regime").json()
        assert "triggers" in data
        assert isinstance(data["triggers"], list)

    def test_indices_endpoint_200(self, client):
        assert client.get("/api/v1/macro/indices").status_code == 200

    def test_indices_has_global_bias(self, client):
        data = client.get("/api/v1/macro/indices").json()
        assert "global_bias" in data

    def test_indices_has_list(self, client):
        data = client.get("/api/v1/macro/indices").json()
        assert "indices" in data
        assert len(data["indices"]) > 0

    def test_indices_each_has_signal(self, client):
        data = client.get("/api/v1/macro/indices").json()
        for idx in data["indices"]:
            assert "signal" in idx

    def test_currencies_endpoint_200(self, client):
        assert client.get("/api/v1/macro/currencies").status_code == 200

    def test_currencies_has_usdinr(self, client):
        data = client.get("/api/v1/macro/currencies").json()
        assert "usdinr" in data
        assert data["usdinr"] > 0

    def test_currencies_has_crude(self, client):
        data = client.get("/api/v1/macro/currencies").json()
        assert "crude_wti" in data
        assert data["crude_wti"] > 0

    def test_currencies_has_signal(self, client):
        data = client.get("/api/v1/macro/currencies").json()
        assert "usdinr_signal" in data
        assert data["usdinr_signal"] in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_vix_endpoint_200(self, client):
        assert client.get("/api/v1/macro/vix").status_code == 200

    def test_vix_has_india_vix(self, client):
        data = client.get("/api/v1/macro/vix").json()
        assert "india_vix" in data
        assert data["india_vix"] > 0

    def test_vix_has_signal(self, client):
        data = client.get("/api/v1/macro/vix").json()
        assert "vix_signal" in data
        assert data["vix_signal"] in ("EXTREME_FEAR", "FEAR", "ELEVATED", "NORMAL", "COMPLACENT")

    def test_vix_has_us_10y(self, client):
        data = client.get("/api/v1/macro/vix").json()
        assert "us_10y_yield" in data
        assert data["us_10y_yield"] > 0

    def test_vix_has_rate_signal(self, client):
        data = client.get("/api/v1/macro/vix").json()
        assert "rate_signal" in data
        assert data["rate_signal"] in ("HAWKISH", "DOVISH", "NEUTRAL")
