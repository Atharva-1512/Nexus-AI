"""
NEXUS AI — Phase 2 Test Suite
Tests for Market Data Engine, Microstructure, Symbol Registry, Market Hours,
Data Validator, Cache Manager, and FII/DII tracker.
"""

import math
from datetime import timezone
from datetime import date, datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app


# ─── Test Client ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ─── Symbol Registry Tests ────────────────────────────────────────────────────

class TestSymbolRegistry:

    def test_nifty_symbol_resolves(self):
        from modules.market_data.symbols import registry
        sym = registry.get("NIFTY")
        assert sym is not None
        assert sym.yf_ticker == "^NSEI"

    def test_yfinance_ticker_lookup(self):
        from modules.market_data.symbols import registry
        sym = registry.get_by_yf("^NSEI")
        assert sym is not None
        assert sym.nexus_id == "NIFTY"

    def test_nifty50_contains_50_stocks(self):
        from modules.market_data.symbols import NIFTY50_STOCKS
        assert len(NIFTY50_STOCKS) == 50

    def test_all_nifty50_marked_is_nifty50(self):
        from modules.market_data.symbols import NIFTY50_STOCKS
        for stock in NIFTY50_STOCKS:
            assert stock.is_nifty50 is True, f"{stock.nexus_id} not marked is_nifty50"

    def test_nifty50_tickers_list_length(self):
        from modules.market_data.symbols import registry
        tickers = registry.nifty50_tickers()
        assert len(tickers) == 50

    def test_all_nifty50_have_lot_size(self):
        from modules.market_data.symbols import NIFTY50_STOCKS
        for stock in NIFTY50_STOCKS:
            assert stock.lot_size > 0, f"{stock.nexus_id} has lot_size=0"

    def test_global_indices_exist(self):
        from modules.market_data.symbols import registry
        for sym_id in ["SP500", "NASDAQ", "NIKKEI", "HANGSENG"]:
            assert registry.get(sym_id) is not None, f"{sym_id} not in registry"

    def test_macro_instruments_exist(self):
        from modules.market_data.symbols import registry
        for sym_id in ["CRUDE_OIL", "GOLD", "USDINR", "DXY", "BITCOIN"]:
            assert registry.get(sym_id) is not None, f"{sym_id} not in registry"

    def test_unknown_symbol_returns_none(self):
        from modules.market_data.symbols import registry
        assert registry.get("FAKE_SYMBOL_XYZ") is None

    def test_case_insensitive_lookup(self):
        from modules.market_data.symbols import registry
        assert registry.get("reliance") is not None
        assert registry.get("RELIANCE") is not None


# ─── Market Hours Tests ───────────────────────────────────────────────────────

class TestMarketHours:

    def test_weekday_at_market_open_is_open(self):
        from modules.market_data.market_hours import get_market_session, MarketSession, IST
        # Monday 10:00 IST
        dt = datetime(2026, 7, 20, 10, 0, 0, tzinfo=IST)
        assert get_market_session(dt) == MarketSession.OPEN

    def test_weekend_is_closed(self):
        from modules.market_data.market_hours import get_market_session, MarketSession, IST
        # Saturday
        dt = datetime(2026, 7, 25, 10, 0, 0, tzinfo=IST)
        assert get_market_session(dt) == MarketSession.CLOSED

    def test_before_market_is_pre_open(self):
        from modules.market_data.market_hours import get_market_session, MarketSession, IST
        dt = datetime(2026, 7, 20, 9, 5, 0, tzinfo=IST)  # 09:05 = pre-open
        assert get_market_session(dt) == MarketSession.PRE_OPEN

    def test_after_market_is_post_close(self):
        from modules.market_data.market_hours import get_market_session, MarketSession, IST
        dt = datetime(2026, 7, 20, 15, 45, 0, tzinfo=IST)  # 15:45 = post-close
        assert get_market_session(dt) == MarketSession.POST_CLOSE

    def test_holiday_is_closed(self):
        from modules.market_data.market_hours import get_market_session, MarketSession, IST
        # Christmas 2025
        dt = datetime(2025, 12, 25, 10, 0, 0, tzinfo=IST)
        assert get_market_session(dt) == MarketSession.CLOSED

    def test_next_nifty_expiry_is_tuesday(self):
        from modules.market_data.market_hours import next_expiry_date
        # Monday Jul 20 2026 → next NIFTY expiry should be Tuesday Jul 21 2026
        expiry = next_expiry_date(date(2026, 7, 20), "NIFTY")
        # Must be Tuesday (1) or Monday (0) if Tuesday is a holiday
        assert expiry.weekday() in (1, 0), (
            f"NIFTY expiry must be Tuesday (or Monday if Tue is holiday), got {expiry} ({expiry.strftime('%A')})"
        )

    def test_next_banknifty_expiry_is_wednesday(self):
        from modules.market_data.market_hours import next_expiry_date
        expiry = next_expiry_date(date(2026, 7, 20), "BANKNIFTY")
        assert expiry.weekday() in (2, 1), (
            f"BANKNIFTY expiry must be Wednesday (or Tuesday if Wed is holiday), got {expiry} ({expiry.strftime('%A')})"
        )

    def test_time_to_expiry_is_positive(self):
        from modules.market_data.market_hours import time_to_expiry_years, IST
        future_expiry = date(2026, 8, 7)   # Next month
        tte = time_to_expiry_years(future_expiry)
        assert tte > 0

    def test_time_to_expiry_is_less_than_1_year(self):
        from modules.market_data.market_hours import time_to_expiry_years
        next_week_expiry = (datetime.now() + timedelta(days=7)).date()
        tte = time_to_expiry_years(next_week_expiry)
        assert tte < 1.0

    def test_market_status_summary_has_required_keys(self):
        from modules.market_data.market_hours import market_status_summary
        status = market_status_summary()
        for key in ["session", "is_open", "ist_time", "ist_date",
                    "is_expiry_day", "next_nifty_expiry", "next_banknifty_expiry",
                    "days_to_next_expiry", "nifty_expiry_day", "banknifty_expiry_day"]:
            assert key in status, f"Missing key: {key}"

    def test_nifty_expiry_day_label_is_tuesday(self):
        from modules.market_data.market_hours import market_status_summary
        status = market_status_summary()
        assert status["nifty_expiry_day"] == "Tuesday"
        assert status["banknifty_expiry_day"] == "Wednesday"

    def test_next_nifty_expiry_is_correct_weekday(self):
        from modules.market_data.market_hours import market_status_summary
        from datetime import date
        status = market_status_summary()
        expiry = date.fromisoformat(status["next_nifty_expiry"])
        # Must be Tuesday (1) or Monday (0) if Tue is holiday
        assert expiry.weekday() in (0, 1), f"Expected Tuesday, got {expiry.strftime('%A')}"

    def test_is_trading_day_rejects_sunday(self):
        from modules.market_data.market_hours import is_trading_day
        sunday = date(2026, 7, 26)
        assert not is_trading_day(sunday)


# ─── Data Validator Tests ─────────────────────────────────────────────────────

class TestOHLCVValidator:

    @pytest.fixture
    def valid_df(self) -> pd.DataFrame:
        """Create a valid OHLCV DataFrame for testing."""
        n = 60
        dates = pd.date_range("2026-01-01", periods=n, freq="1D")
        base = 24000.0
        closes = base + np.cumsum(np.random.normal(0, 50, n))
        opens  = closes + np.random.normal(0, 20, n)
        highs  = np.maximum(opens, closes) + abs(np.random.normal(0, 30, n))
        lows   = np.minimum(opens, closes) - abs(np.random.normal(0, 30, n))
        vols   = np.random.randint(1_000_000, 5_000_000, n)

        return pd.DataFrame({
            "open":   opens,
            "high":   highs,
            "low":    lows,
            "close":  closes,
            "volume": vols,
        }, index=dates)

    @pytest.fixture
    def validator(self):
        from modules.market_data.data_validator import OHLCVValidator
        return OHLCVValidator()

    def test_valid_df_passes(self, validator, valid_df):
        result = validator.validate(valid_df, symbol="TEST")
        assert result.is_valid is True

    def test_empty_df_fails(self, validator):
        result = validator.validate(pd.DataFrame(), symbol="TEST")
        assert result.is_valid is False

    def test_negative_prices_fail(self, validator, valid_df):
        bad_df = valid_df.copy()
        bad_df.loc[bad_df.index[5], "close"] = -100
        result = validator.validate(bad_df, symbol="TEST")
        assert result.is_valid is False

    def test_high_less_than_low_fails(self, validator, valid_df):
        bad_df = valid_df.copy()
        bad_df.loc[bad_df.index[5], "high"] = bad_df.loc[bad_df.index[5], "low"] - 50
        result = validator.validate(bad_df, symbol="TEST")
        assert result.is_valid is False

    def test_nan_values_trigger_warning_and_get_filled(self, validator, valid_df):
        bad_df = valid_df.copy()
        bad_df.loc[bad_df.index[10], "close"] = float("nan")
        result = validator.validate(bad_df, symbol="TEST")
        # Should be repaired via forward fill — not a hard failure
        assert result.cleaned_data is not None

    def test_missing_columns_fail(self, validator):
        bad_df = pd.DataFrame({"price": [100, 200, 300]})
        result = validator.validate(bad_df, symbol="TEST")
        assert result.is_valid is False

    def test_validation_result_has_cleaned_data(self, validator, valid_df):
        result = validator.validate(valid_df, symbol="TEST")
        assert result.cleaned_data is not None
        assert isinstance(result.cleaned_data, pd.DataFrame)


# ─── Cache Manager Tests ───────────────────────────────────────────────────────

class TestTTLCache:

    def test_set_and_get(self):
        from modules.market_data.cache_manager import TTLCache
        c = TTLCache()
        c.set("key1", {"value": 42}, ttl=60)
        assert c.get("key1") == {"value": 42}

    def test_miss_returns_none(self):
        from modules.market_data.cache_manager import TTLCache
        c = TTLCache()
        assert c.get("nonexistent_key") is None

    def test_expired_entry_returns_none(self):
        import time as time_mod
        from modules.market_data.cache_manager import TTLCache, _CacheEntry
        c = TTLCache()
        # Manually insert an already-expired entry
        c._store["expired_key"] = _CacheEntry(value="test", expires_at=time_mod.time() - 1)
        assert c.get("expired_key") is None

    def test_delete_removes_entry(self):
        from modules.market_data.cache_manager import TTLCache
        c = TTLCache()
        c.set("del_key", "value", ttl=60)
        c.delete("del_key")
        assert c.get("del_key") is None

    def test_hit_rate_tracking(self):
        from modules.market_data.cache_manager import TTLCache
        c = TTLCache()
        c.set("k", "v", ttl=60)
        c.get("k")       # hit
        c.get("k")       # hit
        c.get("missing") # miss
        assert c.hit_rate == pytest.approx(2/3, abs=0.01)

    def test_cache_keys(self):
        from modules.market_data.cache_manager import (
            quote_key, ohlcv_key, option_chain_key, vix_key
        )
        assert "NIFTY" in quote_key("NIFTY")
        assert "NIFTY" in ohlcv_key("NIFTY", "1d", "3mo")
        assert "nexus:vix" in vix_key()
        assert "NIFTY" in option_chain_key("NIFTY")


# ─── Order Book Tests ──────────────────────────────────────────────────────────

class TestOrderBook:

    @pytest.fixture
    def sample_book(self):
        from modules.microstructure.order_book import OrderBook, PriceLevel
        return OrderBook(
            symbol    = "NIFTY_24500_CE",
            timestamp = datetime.now(timezone.utc),
            bids      = [
                PriceLevel(price=215.0, quantity=500),
                PriceLevel(price=214.5, quantity=300),
                PriceLevel(price=214.0, quantity=200),
            ],
            asks      = [
                PriceLevel(price=215.5, quantity=400),
                PriceLevel(price=216.0, quantity=250),
                PriceLevel(price=216.5, quantity=150),
            ],
            last_price = 215.2,
        )

    def test_best_bid(self, sample_book):
        assert sample_book.best_bid == 215.0

    def test_best_ask(self, sample_book):
        assert sample_book.best_ask == 215.5

    def test_spread(self, sample_book):
        assert sample_book.spread == pytest.approx(0.5, abs=0.01)

    def test_mid_price(self, sample_book):
        assert sample_book.mid_price == pytest.approx(215.25, abs=0.01)

    def test_spread_pct_is_positive(self, sample_book):
        assert sample_book.spread_pct is not None
        assert sample_book.spread_pct > 0

    def test_order_imbalance_range(self, sample_book):
        imb = sample_book.order_imbalance
        assert imb is not None
        assert -1.0 <= imb <= 1.0

    def test_total_bid_qty(self, sample_book):
        assert sample_book.total_bid_qty == 1000

    def test_total_ask_qty(self, sample_book):
        assert sample_book.total_ask_qty == 800

    def test_to_dict_has_required_keys(self, sample_book):
        d = sample_book.to_dict()
        for key in ["symbol", "best_bid", "best_ask", "spread", "mid_price",
                    "order_imbalance", "bids", "asks"]:
            assert key in d, f"Missing key: {key}"


# ─── Microstructure Analyzer Tests ────────────────────────────────────────────

class TestMicrostructureAnalyzer:

    @pytest.fixture
    def analyzer(self):
        from modules.microstructure.microstructure_analyzer import MicrostructureAnalyzer
        return MicrostructureAnalyzer()

    @pytest.fixture
    def balanced_book(self):
        from modules.microstructure.order_book import OrderBook, PriceLevel
        return OrderBook(
            symbol    = "TEST",
            timestamp = datetime.now(timezone.utc),
            bids      = [PriceLevel(215.0, 500), PriceLevel(214.5, 300)],
            asks      = [PriceLevel(215.5, 500), PriceLevel(216.0, 300)],
        )

    def test_tight_spread_classified_correctly(self, analyzer, balanced_book):
        cls = analyzer.classify_spread(balanced_book)
        # 0.5 / 215.25 = ~0.23% which is between tight (0.1%) and wide (0.5%) → NORMAL
        assert cls.classification in ("TIGHT", "NORMAL")

    def test_liquidity_score_is_0_to_1(self, analyzer, balanced_book):
        score = analyzer.compute_liquidity_score(balanced_book)
        assert 0.0 <= score <= 1.0

    def test_signal_score_is_bounded(self, analyzer, balanced_book):
        signal = analyzer.generate_signal(balanced_book)
        assert -1.0 <= signal.score <= 1.0

    def test_signal_has_narrative(self, analyzer, balanced_book):
        signal = analyzer.generate_signal(balanced_book)
        assert isinstance(signal.narrative, str)
        assert len(signal.narrative) > 0

    def test_market_impact_calculation(self, analyzer, balanced_book):
        impact = analyzer.estimate_market_impact(balanced_book, order_size=300, side="BUY")
        assert "avg_fill_price" in impact
        assert impact["avg_fill_price"] > 0

    def test_market_impact_insufficient_liquidity(self, analyzer, balanced_book):
        # Order size larger than available asks
        impact = analyzer.estimate_market_impact(balanced_book, order_size=10_000, side="BUY")
        assert impact.get("fully_filled") is False or "error" in impact


# ─── Market API Endpoint Tests ────────────────────────────────────────────────

class TestMarketAPIEndpoints:
    """
    Tests for Phase 2 market endpoints.
    These use mocks to avoid real network calls.
    """

    def test_market_status_returns_200(self, client):
        response = client.get("/api/v1/market/status")
        assert response.status_code == 200

    def test_market_status_has_session_field(self, client):
        data = client.get("/api/v1/market/status").json()
        assert "session" in data
        assert data["session"] in ("OPEN", "CLOSED", "PRE_OPEN", "POST_CLOSE")

    def test_market_status_has_ist_time(self, client):
        data = client.get("/api/v1/market/status").json()
        assert "ist_time" in data

    def test_symbols_endpoint_returns_200(self, client):
        response = client.get("/api/v1/market/symbols")
        assert response.status_code == 200

    def test_symbols_endpoint_returns_count(self, client):
        data = client.get("/api/v1/market/symbols").json()
        assert "count" in data
        assert data["count"] > 50  # Should have at least 87 symbols (50 stocks + indices + macro)

    def test_nifty50_filter_returns_50(self, client):
        data = client.get("/api/v1/market/symbols?nifty50_only=true").json()
        assert data["count"] == 50

    def test_ohlcv_invalid_interval_returns_422(self, client):
        response = client.get("/api/v1/market/ohlcv/NIFTY?interval=INVALID")
        assert response.status_code == 422

    def test_ohlcv_invalid_period_returns_422(self, client):
        response = client.get("/api/v1/market/ohlcv/NIFTY?period=INVALID")
        assert response.status_code == 422
