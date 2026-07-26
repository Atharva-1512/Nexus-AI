"""
NEXUS AI — Backend Test Suite (Phase 1)
Tests for health endpoints, config loading, and BS pricing model.
"""

import pytest
import math
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from modules.options_engine.black_scholes import BlackScholesPricer
from modules.options_engine.models import OptionSpec, OptionType


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    """Synchronous test client for FastAPI application."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def bs_pricer():
    return BlackScholesPricer()


@pytest.fixture
def call_spec():
    """ATM NIFTY call option with known approximate price."""
    return OptionSpec(
        underlying_price=24_000.0,
        strike_price=24_000.0,
        time_to_expiry=7 / 365,    # 7 days to expiry
        risk_free_rate=0.065,
        implied_volatility=0.15,    # 15% IV
        option_type=OptionType.CALL,
    )


@pytest.fixture
def put_spec():
    return OptionSpec(
        underlying_price=24_000.0,
        strike_price=24_000.0,
        time_to_expiry=7 / 365,
        risk_free_rate=0.065,
        implied_volatility=0.15,
        option_type=OptionType.PUT,
    )


# ─── Health Endpoint Tests ─────────────────────────────────────────────────────

class TestHealthEndpoints:

    def test_health_returns_200(self, client):
        response = client.get("/api/v1/health/")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, client):
        data = client.get("/api/v1/health/").json()
        assert data["status"] == "healthy"

    def test_health_returns_correct_version(self, client):
        data = client.get("/api/v1/health/").json()
        assert data["version"] == settings.APP_VERSION

    def test_health_paper_trading_mode_is_true(self, client):
        """Safety: paper trading must be enabled by default."""
        data = client.get("/api/v1/health/").json()
        assert data["paper_trading_mode"] is True

    def test_readiness_returns_200(self, client):
        response = client.get("/api/v1/health/ready")
        # In Phase 1, all dependency checks are mocked as True
        assert response.status_code == 200

    def test_health_info_available_in_dev(self, client):
        """System info endpoint available in development mode."""
        response = client.get("/api/v1/health/info")
        if settings.is_development:
            assert response.status_code == 200
        else:
            assert response.status_code == 403


# ─── Signal Endpoint Tests ─────────────────────────────────────────────────────

class TestSignalEndpoints:

    def test_latest_signal_returns_200(self, client):
        response = client.get("/api/v1/signals/latest")
        assert response.status_code == 200

    def test_latest_signal_has_required_fields(self, client):
        data = client.get("/api/v1/signals/latest").json()
        assert "signal" in data
        assert "confidence" in data
        assert "factor_weights" in data

    def test_signal_is_valid_type(self, client):
        data = client.get("/api/v1/signals/latest").json()
        assert data["signal"] in ("BUY_CALL", "BUY_PUT", "NO_TRADE")

    def test_confidence_is_between_0_and_100(self, client):
        data = client.get("/api/v1/signals/latest").json()
        assert 0 <= data["confidence"] <= 100

    def test_factor_weights_sum_to_100(self, client):
        data = client.get("/api/v1/signals/latest").json()
        if data["factor_weights"]:
            total = sum(fw["weight_pct"] for fw in data["factor_weights"])
            assert abs(total - 100.0) < 1.0, f"Factor weights sum to {total}, expected ~100"


# ─── Alert Endpoint Tests ──────────────────────────────────────────────────────

class TestAlertEndpoints:

    def test_alerts_returns_200(self, client):
        response = client.get("/api/v1/alerts/")
        assert response.status_code == 200

    def test_alert_settings_returns_200(self, client):
        response = client.get("/api/v1/alerts/settings")
        assert response.status_code == 200

    def test_alert_settings_has_sound_enabled(self, client):
        data = client.get("/api/v1/alerts/settings").json()
        assert "sound_enabled" in data


# ─── Black-Scholes Pricer Tests ────────────────────────────────────────────────

class TestBlackScholesPricer:
    """
    Tests against known analytical values.
    Reference: Haug (2006) — The Complete Guide to Option Pricing Formulas.
    """

    def test_atm_call_price_is_positive(self, bs_pricer, call_spec):
        result = bs_pricer.price(call_spec)
        assert result.theoretical_price > 0

    def test_atm_put_price_is_positive(self, bs_pricer, put_spec):
        result = bs_pricer.price(put_spec)
        assert result.theoretical_price > 0

    def test_put_call_parity(self, bs_pricer, call_spec, put_spec):
        """
        Put-Call Parity: C - P = S·e^(-qT) - K·e^(-rT)
        Must hold for European options under BS.
        """
        C = bs_pricer.price(call_spec).theoretical_price
        P = bs_pricer.price(put_spec).theoretical_price
        S = call_spec.underlying_price
        K = call_spec.strike_price
        T = call_spec.time_to_expiry
        r = call_spec.risk_free_rate
        q = call_spec.dividend_yield

        lhs = C - P
        rhs = S * math.exp(-q * T) - K * math.exp(-r * T)
        assert abs(lhs - rhs) < 0.01, f"Put-Call Parity violated: LHS={lhs:.4f}, RHS={rhs:.4f}"

    def test_call_delta_between_0_and_1(self, bs_pricer, call_spec):
        result = bs_pricer.price(call_spec)
        assert 0 <= result.greeks.delta <= 1.0

    def test_put_delta_between_minus1_and_0(self, bs_pricer, put_spec):
        result = bs_pricer.price(put_spec)
        assert -1.0 <= result.greeks.delta <= 0.0

    def test_gamma_is_positive(self, bs_pricer, call_spec):
        result = bs_pricer.price(call_spec)
        assert result.greeks.gamma > 0

    def test_theta_is_negative(self, bs_pricer, call_spec):
        """Options lose value over time — theta must be negative."""
        result = bs_pricer.price(call_spec)
        assert result.greeks.theta < 0

    def test_vega_is_positive(self, bs_pricer, call_spec):
        """Options gain value with higher IV — vega must be positive."""
        result = bs_pricer.price(call_spec)
        assert result.greeks.vega > 0

    def test_atm_delta_near_half(self, bs_pricer, call_spec):
        """ATM call delta is approximately 0.5."""
        result = bs_pricer.price(call_spec)
        assert 0.45 <= result.greeks.delta <= 0.55

    def test_deep_itm_call_delta_near_1(self, bs_pricer):
        """Deep ITM call delta approaches 1."""
        spec = OptionSpec(
            underlying_price=24_000.0,
            strike_price=20_000.0,    # Deep ITM
            time_to_expiry=7 / 365,
            risk_free_rate=0.065,
            implied_volatility=0.15,
            option_type=OptionType.CALL,
        )
        result = bs_pricer.price(spec)
        assert result.greeks.delta > 0.90

    def test_deep_otm_call_delta_near_0(self, bs_pricer):
        """Deep OTM call delta approaches 0."""
        spec = OptionSpec(
            underlying_price=24_000.0,
            strike_price=28_000.0,    # Deep OTM
            time_to_expiry=7 / 365,
            risk_free_rate=0.065,
            implied_volatility=0.15,
            option_type=OptionType.CALL,
        )
        result = bs_pricer.price(spec)
        assert result.greeks.delta < 0.05

    def test_iv_solver_roundtrip(self, bs_pricer, call_spec):
        """
        Roundtrip test: price → market price → IV solve → reprice.
        Recovered IV should match original within 0.1%.
        """
        original_result = bs_pricer.price(call_spec)
        market_price = original_result.theoretical_price

        recovered_iv = bs_pricer.implied_volatility(
            market_price=market_price,
            spec=call_spec,
        )

        assert abs(recovered_iv - call_spec.implied_volatility) < 0.001, (
            f"IV roundtrip failed: original={call_spec.implied_volatility:.4f}, "
            f"recovered={recovered_iv:.4f}"
        )

    def test_price_increases_with_higher_iv(self, bs_pricer, call_spec):
        """Higher IV → higher option price."""
        from dataclasses import replace
        low_iv_spec  = replace(call_spec, implied_volatility=0.10)
        high_iv_spec = replace(call_spec, implied_volatility=0.30)
        low_price  = bs_pricer.price(low_iv_spec).theoretical_price
        high_price = bs_pricer.price(high_iv_spec).theoretical_price
        assert high_price > low_price

    def test_price_increases_with_more_time(self, bs_pricer, call_spec):
        """More time to expiry → higher option price."""
        from dataclasses import replace
        short_spec = replace(call_spec, time_to_expiry=1 / 365)
        long_spec  = replace(call_spec, time_to_expiry=30 / 365)
        short_price = bs_pricer.price(short_spec).theoretical_price
        long_price  = bs_pricer.price(long_spec).theoretical_price
        assert long_price > short_price

    def test_pricing_result_model_name(self, bs_pricer, call_spec):
        result = bs_pricer.price(call_spec)
        assert result.model == "black_scholes"

    def test_all_greeks_are_computed(self, bs_pricer, call_spec):
        """Verify all 12 Greeks are present and not NaN."""
        result = bs_pricer.price(call_spec)
        g = result.greeks
        for field_name in ["delta", "gamma", "theta", "vega", "rho",
                           "vomma", "vanna", "charm", "color", "speed",
                           "zomma", "ultima"]:
            value = getattr(g, field_name)
            assert not math.isnan(value), f"Greek '{field_name}' is NaN"
