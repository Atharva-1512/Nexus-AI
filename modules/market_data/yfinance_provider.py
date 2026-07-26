"""
NEXUS AI — YFinance Data Provider (Module 1)

Concrete implementation of DataProvider using Yahoo Finance (yfinance).
- 100% free, no API key required
- Provides: Historical OHLCV, semi-live delayed quotes
- Covers: NIFTY, global indices, macro instruments, crypto

Phase 2 will add:
- Retry logic with exponential backoff
- Response caching (Redis)
- Rate limiting
- Data validation and outlier detection
"""

import asyncio
import logging
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd
import yfinance as yf

from .provider import DataProvider, OHLCV, OptionChain, Quote

logger = logging.getLogger(__name__)


# ─── Symbol Mapping ───────────────────────────────────────────────────────────
# Maps NEXUS internal symbols to Yahoo Finance ticker symbols

SYMBOL_MAP: dict[str, str] = {
    # NIFTY
    "NIFTY":        "^NSEI",
    "NIFTY_FUTURE": "^NSEI",       # TODO: futures-specific ticker
    "BANKNIFTY":    "^NSEBANK",
    "VIX":          "^INDIAVIX",

    # Global Indices
    "SP500":        "^GSPC",
    "NASDAQ":       "^IXIC",
    "DOWJONES":     "^DJI",
    "FTSE":         "^FTSE",
    "DAX":          "^GDAXI",
    "NIKKEI":       "^N225",
    "HANGSENG":     "^HSI",
    "GIFTNIFTY":    "NIFTY.NS",

    # Macro
    "CRUDE_OIL":    "CL=F",
    "NATURAL_GAS":  "NG=F",
    "GOLD":         "GC=F",
    "SILVER":       "SI=F",
    "DXY":          "DX-Y.NYB",
    "USDINR":       "USDINR=X",
    "US_10Y_YIELD": "^TNX",

    # Crypto
    "BITCOIN":      "BTC-USD",
    "ETHEREUM":     "ETH-USD",
}


class YFinanceProvider(DataProvider):
    """
    Yahoo Finance data provider — free, no API key, globally available.

    Limitations (inherent to yfinance):
    - Quotes are delayed ~15 minutes for NSE
    - No tick data
    - No real-time option chain for Indian markets
    - Rate limiting may apply under heavy load

    Use NSEProvider for live NSE option chain data.
    """

    def _resolve_symbol(self, symbol: str) -> str:
        """Map NEXUS symbol to Yahoo Finance ticker."""
        return SYMBOL_MAP.get(symbol.upper(), symbol)

    @lru_cache(maxsize=50)
    def _get_ticker(self, yf_symbol: str) -> yf.Ticker:
        """Cache yfinance Ticker objects to avoid redundant HTTP sessions."""
        return yf.Ticker(yf_symbol)

    async def get_quote(self, symbol: str) -> Quote:
        """
        Fetch a delayed quote via yfinance.
        Runs in a thread pool executor to avoid blocking the async event loop.
        """
        yf_symbol = self._resolve_symbol(symbol)
        ticker = self._get_ticker(yf_symbol)

        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: ticker.fast_info)

        last_price = getattr(info, "last_price", 0.0) or 0.0
        prev_close = getattr(info, "previous_close", last_price) or last_price
        change = last_price - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        logger.debug(f"Quote fetched: {symbol} ({yf_symbol}) @ {last_price}")

        return Quote(
            symbol=symbol,
            last_price=last_price,
            change=round(change, 2),
            change_pct=round(change_pct, 2),
            open=getattr(info, "open", last_price) or last_price,
            high=getattr(info, "day_high", last_price) or last_price,
            low=getattr(info, "day_low", last_price) or last_price,
            close=prev_close,
            volume=getattr(info, "three_month_average_volume", 0) or 0,
            timestamp=datetime.utcnow(),
        )

    async def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "1mo",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars as a pandas DataFrame.

        Args:
            symbol  : NEXUS symbol or Yahoo Finance ticker
            interval: Bar interval (1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo)
            period  : Lookback period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max)
            start   : Explicit start date (overrides period)
            end     : Explicit end date

        Returns:
            pd.DataFrame with columns: [open, high, low, close, volume]
            Index: DatetimeIndex
        """
        yf_symbol = self._resolve_symbol(symbol)
        ticker = self._get_ticker(yf_symbol)

        loop = asyncio.get_event_loop()

        kwargs = {"interval": interval, "auto_adjust": True, "progress": False}
        if start:
            kwargs["start"] = start
            if end:
                kwargs["end"] = end
        else:
            kwargs["period"] = period

        df = await loop.run_in_executor(None, lambda: ticker.history(**kwargs))

        if df.empty:
            logger.warning(f"No OHLCV data returned for {symbol} ({yf_symbol})")
            return pd.DataFrame()

        # Standardise column names to lowercase
        df.columns = [c.lower() for c in df.columns]
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index.name = "timestamp"

        logger.info(f"OHLCV fetched: {symbol} | {len(df)} bars | {interval}")
        return df

    async def get_option_chain(
        self, underlying: str, expiry: Optional[datetime] = None
    ) -> OptionChain:
        """
        yfinance does not provide Indian NSE option chains.
        Use NSEProvider for live NIFTY option chain.
        This method is provided for completeness / US market usage.
        """
        raise NotImplementedError(
            "YFinanceProvider does not support NSE option chains. "
            "Use NSEProvider.get_option_chain() instead."
        )

    async def get_vix(self) -> float:
        """Fetch India VIX via yfinance (^INDIAVIX)."""
        try:
            quote = await self.get_quote("VIX")
            return quote.last_price
        except Exception as e:
            logger.error(f"Failed to fetch India VIX: {e}")
            return 0.0
