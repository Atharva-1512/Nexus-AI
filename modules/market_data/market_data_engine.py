"""
NEXUS AI — Market Data Engine Orchestrator (Module 1)

Central orchestrator that:
1. Polls live data on a configurable schedule
2. Routes requests through the cache layer
3. Validates all incoming data
4. Publishes to Kafka topics
5. Writes OHLCV to TimescaleDB
6. Exposes a clean async API for all other modules

Supports two data providers:
- YFinanceProvider  : historical OHLCV + delayed quotes (no key needed)
- NSEProvider       : live option chain + FII/DII (no key needed)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from .cache_manager    import (
    CacheManager, cache,
    quote_key, ohlcv_key, option_chain_key,
    vix_key, fii_dii_key, market_status_key, global_index_key,
    TTL_LIVE_QUOTE, TTL_OPTION_CHAIN, TTL_OHLCV_INTRADAY,
    TTL_OHLCV_DAILY, TTL_VIX, TTL_FII_DII, TTL_MARKET_STATUS,
    TTL_GLOBAL_INDICES,
)
from .data_validator   import OHLCVValidator, QuoteValidator
from .fii_dii_tracker  import FIIDIITracker, FIIDIIFlow
from .market_hours     import is_market_open, market_status_summary, next_expiry_date
from .nse_provider     import NSEProvider
from .provider         import DataProvider, OptionChain, Quote
from .symbols          import (
    NIFTY_INDEX, BANKNIFTY_INDEX, INDIA_VIX,
    NIFTY50_STOCKS, SECTOR_INDICES, GLOBAL_INDICES, MACRO_INSTRUMENTS,
    registry,
)
from .yfinance_provider import YFinanceProvider

logger = logging.getLogger(__name__)


class MarketDataEngine:
    """
    Central market data orchestrator for NEXUS AI.

    Usage:
        engine = MarketDataEngine()
        await engine.start()

        # Get live NIFTY quote (cached 15s)
        quote = await engine.get_nifty_quote()

        # Get full option chain (cached 60s)
        chain = await engine.get_option_chain()

        # Get OHLCV bars
        df = await engine.get_ohlcv("NIFTY", interval="5m", period="1d")
    """

    def __init__(
        self,
        cache_manager:  CacheManager | None = None,
        yf_provider:    YFinanceProvider | None = None,
        nse_provider:   NSEProvider | None = None,
        fii_tracker:    FIIDIITracker | None = None,
    ):
        self._cache      = cache_manager or cache
        self._yf         = yf_provider   or YFinanceProvider()
        self._nse        = nse_provider  or NSEProvider()
        self._fii_tracker = fii_tracker  or FIIDIITracker()
        self._validator  = OHLCVValidator()
        self._running    = False
        self._poll_task: asyncio.Task | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize the engine: connect cache, start background polling."""
        logger.info("MarketDataEngine starting...")
        await self._cache.connect()
        self._running = True
        # Start background polling (during market hours only)
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("MarketDataEngine started.")

    async def stop(self) -> None:
        """Gracefully stop polling."""
        self._running = False
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
        logger.info("MarketDataEngine stopped.")

    async def _poll_loop(self) -> None:
        """
        Background polling loop.
        Refreshes live data every 60 seconds during market hours.
        Sleeps longer when market is closed.
        """
        while self._running:
            try:
                if is_market_open():
                    await self._refresh_live_data()
                    await asyncio.sleep(5)
                else:
                    # Refresh global markets and quotes every 5 seconds
                    await self._refresh_global_indices()
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Polling loop error: {e}", exc_info=True)
                await asyncio.sleep(5)


    async def _refresh_live_data(self) -> None:
        """Refresh all live data in parallel during market hours."""
        logger.debug("Refreshing live market data...")
        await asyncio.gather(
            self._refresh_nifty_quote(),
            self._refresh_vix(),
            self._refresh_option_chain(),
            self._refresh_global_indices(),
            return_exceptions=True,
        )

    async def _refresh_nifty_quote(self) -> None:
        try:
            quote = await self._yf.get_quote("NIFTY")
            await self._cache.set(quote_key("NIFTY"), quote.__dict__ if hasattr(quote, '__dict__') else vars(quote), TTL_LIVE_QUOTE)
        except Exception as e:
            logger.debug(f"NIFTY quote refresh failed: {e}")

    async def _refresh_vix(self) -> None:
        try:
            vix = await self._nse.get_vix()
            await self._cache.set(vix_key(), {"value": vix, "ts": datetime.utcnow().isoformat()}, TTL_VIX)
        except Exception as e:
            logger.debug(f"VIX refresh failed: {e}")

    async def _refresh_option_chain(self) -> None:
        try:
            chain = await self._nse.get_option_chain()
            serialized = _serialize_option_chain(chain)
            await self._cache.set(option_chain_key("NIFTY"), serialized, TTL_OPTION_CHAIN)
        except Exception as e:
            logger.debug(f"Option chain refresh failed: {e}")

    async def _refresh_global_indices(self) -> None:
        symbols = ["SP500", "NASDAQ", "GIFTNIFTY", "GLOBALVIX"]
        tasks = [self._yf.get_quote(s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for sym, result in zip(symbols, results):
            if not isinstance(result, Exception):
                try:
                    data = {"last_price": result.last_price, "change_pct": result.change_pct, "ts": datetime.utcnow().isoformat()}
                    await self._cache.set(global_index_key(sym), data, TTL_GLOBAL_INDICES)
                except Exception:
                    pass

    # ── Public API ───────────────────────────────────────────────────────────

    async def get_nifty_quote(self) -> dict:
        """Get NIFTY 50 live quote (cached 15 sec)."""
        return await self._cache.get_or_fetch(
            key     = quote_key("NIFTY"),
            fetcher = lambda: self._yf.get_quote("NIFTY"),
            ttl     = TTL_LIVE_QUOTE,
        ) or {"symbol": "NIFTY", "last_price": 0, "error": "Unavailable"}

    async def get_banknifty_quote(self) -> dict:
        """Get NIFTY Bank live quote (cached 15 sec)."""
        return await self._cache.get_or_fetch(
            key     = quote_key("BANKNIFTY"),
            fetcher = lambda: self._yf.get_quote("BANKNIFTY"),
            ttl     = TTL_LIVE_QUOTE,
        ) or {"symbol": "BANKNIFTY", "last_price": 0}

    async def get_vix(self) -> dict:
        """Get India VIX (cached 30 sec)."""
        cached = await self._cache.get(vix_key())
        if cached:
            return cached
        vix_value = await self._nse.get_vix()
        result = {"value": vix_value, "ts": datetime.utcnow().isoformat()}
        await self._cache.set(vix_key(), result, TTL_VIX)
        return result

    async def get_option_chain(self, expiry: Optional[str] = None) -> dict:
        """Get NIFTY option chain (cached 60 sec)."""
        key = option_chain_key("NIFTY", expiry or "current")
        cached = await self._cache.get(key)
        if cached:
            return cached
        chain = await self._nse.get_option_chain()
        serialized = _serialize_option_chain(chain)
        await self._cache.set(key, serialized, TTL_OPTION_CHAIN)
        return serialized

    async def get_ohlcv(
        self,
        symbol:   str = "NIFTY",
        interval: str = "1d",
        period:   str = "3mo",
    ) -> pd.DataFrame:
        """
        Get OHLCV bars for any symbol.

        The returned DataFrame is validated and cleaned.
        Cached: 60s for intraday, 1h for daily.

        Args:
            symbol:   NEXUS symbol ID (e.g. "NIFTY", "RELIANCE", "SP500")
            interval: Bar interval ("1m", "5m", "15m", "1h", "1d")
            period:   Lookback period ("1d", "5d", "1mo", "3mo", "6mo", "1y")

        Returns:
            Validated pd.DataFrame with columns [open, high, low, close, volume]
        """
        cache_key = ohlcv_key(symbol, interval, period)
        ttl = TTL_OHLCV_INTRADAY if "m" in interval or "h" in interval else TTL_OHLCV_DAILY

        # Cache stores the DataFrame as JSON records — reconstruct on hit
        cached_json = await self._cache.get(cache_key)
        if cached_json:
            try:
                df = pd.DataFrame(cached_json["records"])
                df.index = pd.to_datetime(cached_json["index"])
                return df
            except Exception:
                pass

        # Fetch from yfinance
        df = await self._yf.get_ohlcv(symbol, interval=interval, period=period)

        if df.empty:
            logger.warning(f"Empty OHLCV for {symbol} {interval}/{period}")
            return df

        # Validate
        validation = self._validator.validate(df, symbol=symbol)
        if validation.cleaned_data is not None:
            df = validation.cleaned_data

        if validation.issues:
            for issue in validation.issues:
                logger.log(
                    logging.WARNING if issue.severity.value != "INFO" else logging.DEBUG,
                    f"OHLCV [{symbol}] {issue.severity}: {issue.message}"
                )

        # Cache as JSON
        try:
            await self._cache.set(cache_key, {
                "records": df.to_dict(orient="records"),
                "index":   [str(i) for i in df.index],
            }, ttl)
        except Exception:
            pass

        return df

    async def get_multiple_quotes(self, symbols: list[str]) -> dict[str, dict]:
        """Fetch quotes for multiple symbols in parallel."""
        tasks = {s: self._yf.get_quote(s) for s in symbols}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        output = {}
        for sym, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                output[sym] = {"symbol": sym, "error": str(result)}
            else:
                output[sym] = vars(result) if hasattr(result, '__dict__') else result
        return output

    async def get_global_markets(self) -> dict[str, dict]:
        """Get all global market indices in parallel."""
        global_symbols = ["SP500", "NASDAQ", "DOWJONES", "FTSE", "DAX",
                          "NIKKEI", "HANGSENG", "GLOBALVIX", "GIFTNIFTY",
                          "BITCOIN", "USDINR", "CRUDE_OIL", "GOLD"]
        return await self.get_multiple_quotes(global_symbols)

    async def get_fii_dii(self) -> dict:
        """Get FII/DII institutional flow data (cached 30 min)."""
        from datetime import date as date_type
        today_str = date_type.today().isoformat()
        key = fii_dii_key(today_str)

        cached = await self._cache.get(key)
        if cached:
            return cached

        flow = await asyncio.get_event_loop().run_in_executor(
            None, self._fii_tracker.fetch_latest
        )
        result = flow.to_dict() if flow else {"error": "FII/DII data unavailable"}
        await self._cache.set(key, result, TTL_FII_DII)
        return result

    async def get_market_status(self) -> dict:
        """Get current market session status (cached 10 sec)."""
        return await self._cache.get_or_fetch(
            key     = market_status_key(),
            fetcher = lambda: asyncio.coroutine(lambda: market_status_summary())(),
            ttl     = TTL_MARKET_STATUS,
        ) or market_status_summary()

    async def get_nifty50_snapshot(self) -> list[dict]:
        """
        Get a quick quote snapshot for all NIFTY 50 stocks.
        Fetched in parallel batches of 10.
        """
        symbols = [s.nexus_id for s in NIFTY50_STOCKS]
        batch_size = 10
        results = []

        for i in range(0, len(symbols), batch_size):
            batch = symbols[i : i + batch_size]
            batch_results = await self.get_multiple_quotes(batch)
            results.extend(batch_results.values())
            await asyncio.sleep(0.5)  # Polite delay

        return results


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _serialize_option_chain(chain: OptionChain) -> dict:
    """Convert OptionChain dataclass to JSON-serializable dict."""
    return {
        "underlying":  chain.underlying,
        "spot_price":  chain.spot_price,
        "expiry":      chain.expiry.isoformat() if chain.expiry else None,
        "pcr":         chain.pcr,
        "max_pain":    chain.max_pain,
        "timestamp":   chain.timestamp.isoformat(),
        "calls": [vars(c) for c in chain.calls],
        "puts":  [vars(p) for p in chain.puts],
        "call_count":  len(chain.calls),
        "put_count":   len(chain.puts),
    }


# ─── Module-level singleton ───────────────────────────────────────────────────
market_engine = MarketDataEngine()
