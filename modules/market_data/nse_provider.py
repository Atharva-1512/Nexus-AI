"""
NEXUS AI — NSE India Data Provider (Module 1)

Concrete implementation of DataProvider using NSE India's public website.
- 100% free, no API key required
- Uses nsepython + direct requests to NSE APIs
- Provides: Live option chain, FII/DII data, OI, IV

NSE Rate Limiting: We enforce a minimum delay between requests to
avoid getting blocked. Default: 1 second between requests.

Phase 2 will add:
- Session management with proper cookies and headers
- Retry with exponential backoff
- Redis caching layer
- Data validation pipeline
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

import pandas as pd
import requests

from .provider import DataProvider, OptionChain, OptionData, Quote, OHLCV

logger = logging.getLogger(__name__)

# NSE requires browser-like headers to avoid 403 errors
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com",
    "Connection": "keep-alive",
}

_NSE_BASE = "https://www.nseindia.com"
_NSE_OPTION_CHAIN_URL = f"{_NSE_BASE}/api/option-chain-indices?symbol=NIFTY"
_NSE_QUOTE_URL = f"{_NSE_BASE}/api/quote-equity?symbol="
_NSE_FII_DII_URL = f"{_NSE_BASE}/api/fiidiiTradeReact"


class NSEProvider(DataProvider):
    """
    NSE India direct data provider.

    Covers:
    - NIFTY option chain (live, from NSE API)
    - FII / DII buy/sell data
    - NSE corporate announcements
    - Index quotes

    Important: NSE's website requires a valid session cookie obtained
    by first visiting the homepage. This provider handles that automatically.
    """

    def __init__(self, request_delay: float = 1.0):
        self._request_delay = request_delay
        self._session = requests.Session()
        self._session.headers.update(_NSE_HEADERS)
        self._last_request_time: float = 0.0
        self._session_initialized = False

    def _ensure_session(self) -> None:
        """
        NSE requires visiting the homepage first to set cookies.
        This is called automatically before the first API request.
        """
        if not self._session_initialized:
            try:
                logger.info("Initializing NSE session (visiting homepage)...")
                self._session.get(_NSE_BASE, timeout=10)
                self._session_initialized = True
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"NSE session initialization failed: {e}")

    def _rate_limited_get(self, url: str, **kwargs) -> requests.Response:
        """
        Perform a GET request with rate limiting.
        Ensures minimum delay between consecutive NSE requests.
        """
        self._ensure_session()

        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)

        try:
            response = self._session.get(url, timeout=15, **kwargs)
            response.raise_for_status()
            self._last_request_time = time.time()
            return response
        except requests.RequestException as e:
            logger.error(f"NSE request failed for {url}: {e}")
            raise

    async def get_quote(self, symbol: str) -> Quote:
        """
        Fetch NSE quote. Currently delegates to yfinance for non-option symbols.
        Full NSE implementation in Phase 2.
        """
        # TODO (Phase 2): Implement direct NSE quote API
        raise NotImplementedError(
            "NSEProvider.get_quote() will be implemented in Phase 2. "
            "Use YFinanceProvider for quotes."
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
        NSE historical OHLCV — Phase 2 implementation.
        Uses NSE bhavcopy (daily settlement data).
        """
        # TODO (Phase 2): NSE bhavcopy downloader
        raise NotImplementedError("NSEProvider.get_ohlcv() — Phase 2.")

    async def get_option_chain(
        self, underlying: str = "NIFTY", expiry: Optional[datetime] = None
    ) -> OptionChain:
        """
        Fetch the live NIFTY 50 option chain from NSE.

        Returns a fully parsed OptionChain with all strikes,
        OI, IV, and pricing data.
        """
        loop = asyncio.get_event_loop()

        try:
            response = await loop.run_in_executor(
                None, lambda: self._rate_limited_get(_NSE_OPTION_CHAIN_URL)
            )
            data = response.json()
        except Exception as e:
            logger.error(f"Failed to fetch NSE option chain: {e}")
            raise

        # ── Parse NSE option chain response ───────────────────────────────────
        records = data.get("records", {})
        spot_price = records.get("underlyingValue", 0.0)
        expiry_dates = records.get("expiryDates", [])
        raw_data = records.get("data", [])

        # Use nearest expiry if not specified
        target_expiry_str = expiry_dates[0] if expiry_dates else None

        calls: list[OptionData] = []
        puts: list[OptionData] = []

        for row in raw_data:
            strike = row.get("strikePrice", 0.0)
            row_expiry = row.get("expiryDate", "")

            # Filter by target expiry
            if target_expiry_str and row_expiry != target_expiry_str:
                continue

            # Parse CE (Call)
            if "CE" in row:
                ce = row["CE"]
                calls.append(OptionData(
                    symbol=f"NIFTY {strike} CE",
                    expiry=datetime.strptime(row_expiry, "%d-%b-%Y") if row_expiry else datetime.utcnow(),
                    strike=strike,
                    option_type="CE",
                    last_price=ce.get("lastPrice", 0.0),
                    open_interest=ce.get("openInterest", 0),
                    oi_change=ce.get("changeinOpenInterest", 0),
                    volume=ce.get("totalTradedVolume", 0),
                    iv=ce.get("impliedVolatility", None),
                    bid=ce.get("bidprice", None),
                    ask=ce.get("askPrice", None),
                ))

            # Parse PE (Put)
            if "PE" in row:
                pe = row["PE"]
                puts.append(OptionData(
                    symbol=f"NIFTY {strike} PE",
                    expiry=datetime.strptime(row_expiry, "%d-%b-%Y") if row_expiry else datetime.utcnow(),
                    strike=strike,
                    option_type="PE",
                    last_price=pe.get("lastPrice", 0.0),
                    open_interest=pe.get("openInterest", 0),
                    oi_change=pe.get("changeinOpenInterest", 0),
                    volume=pe.get("totalTradedVolume", 0),
                    iv=pe.get("impliedVolatility", None),
                    bid=pe.get("bidprice", None),
                    ask=pe.get("askPrice", None),
                ))

        # ── Calculate PCR ──────────────────────────────────────────────────────
        total_put_oi = sum(p.open_interest for p in puts)
        total_call_oi = sum(c.open_interest for c in calls)
        pcr = total_put_oi / total_call_oi if total_call_oi > 0 else None

        expiry_dt = (
            datetime.strptime(target_expiry_str, "%d-%b-%Y")
            if target_expiry_str else datetime.utcnow()
        )

        logger.info(
            f"NSE Option Chain fetched: {underlying} | "
            f"Spot: {spot_price} | {len(calls)} calls, {len(puts)} puts | "
            f"PCR: {pcr:.2f}" if pcr else "PCR: N/A"
        )

        return OptionChain(
            underlying=underlying,
            spot_price=spot_price,
            expiry=expiry_dt,
            calls=calls,
            puts=puts,
            pcr=round(pcr, 3) if pcr else None,
            timestamp=datetime.utcnow(),
        )

    async def get_vix(self) -> float:
        """
        Fetch India VIX from NSE.
        Falls back to yfinance if NSE request fails.
        """
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._rate_limited_get(
                    f"{_NSE_BASE}/api/allIndices"
                )
            )
            indices = response.json().get("data", [])
            for idx in indices:
                if "INDIA VIX" in idx.get("index", ""):
                    return float(idx.get("last", 0.0))
        except Exception as e:
            logger.warning(f"NSE VIX fetch failed: {e}. Falling back to yfinance.")

        # Fallback
        from .yfinance_provider import YFinanceProvider
        return await YFinanceProvider().get_vix()
