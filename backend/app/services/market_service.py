"""
NEXUS AI — Market Data Service (Backend)

Service layer between the API endpoints and the Market Data Engine.
Handles dependency injection, error handling, and response formatting.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MarketService:
    """
    Async service class for all market data operations.
    Used by FastAPI endpoints via dependency injection.
    """

    def __init__(self):
        # Lazy import to avoid circular deps and allow testing without full engine
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from modules.market_data.market_data_engine import market_engine
            self._engine = market_engine
        return self._engine

    async def get_nifty_quote(self) -> dict:
        """Get NIFTY 50 live quote."""
        try:
            engine = self._get_engine()
            return await engine.get_nifty_quote()
        except Exception as e:
            logger.error(f"MarketService.get_nifty_quote failed: {e}")
            return {"symbol": "NIFTY", "error": str(e), "last_price": None}

    async def get_market_overview(self) -> dict:
        """
        Get a full market overview including:
        - NIFTY + BANKNIFTY quotes
        - India VIX
        - FII/DII flows
        - Market session status
        - Key global indices
        """
        engine = self._get_engine()

        nifty_task     = engine.get_nifty_quote()
        banknifty_task = engine.get_banknifty_quote()
        vix_task       = engine.get_vix()
        fii_task       = engine.get_fii_dii()
        status_task    = engine.get_market_status()
        globals_task   = engine.get_multiple_quotes(
            ["SP500", "NASDAQ", "GIFTNIFTY", "GLOBALVIX", "USDINR", "CRUDE_OIL", "GOLD"]
        )

        results = await asyncio.gather(
            nifty_task, banknifty_task, vix_task, fii_task, status_task, globals_task,
            return_exceptions=True,
        )

        def safe(r, default=None):
            return r if not isinstance(r, Exception) else (default or {"error": str(r)})

        return {
            "nifty":         safe(results[0]),
            "banknifty":     safe(results[1]),
            "vix":           safe(results[2]),
            "fii_dii":       safe(results[3]),
            "market_status": safe(results[4]),
            "global":        safe(results[5], {}),
            "generated_at":  datetime.utcnow().isoformat() + "Z",
        }

    async def get_ohlcv(
        self,
        symbol:   str,
        interval: str = "1d",
        period:   str = "3mo",
    ) -> dict:
        """Get OHLCV candlestick data as JSON-serializable dict."""
        try:
            engine = self._get_engine()
            df = await engine.get_ohlcv(symbol, interval=interval, period=period)

            if df.empty:
                return {"symbol": symbol, "bars": [], "count": 0}

            bars = []
            for ts, row in df.iterrows():
                bars.append({
                    "t":  str(ts),
                    "o":  round(float(row["open"]),  2),
                    "h":  round(float(row["high"]),  2),
                    "l":  round(float(row["low"]),   2),
                    "c":  round(float(row["close"]), 2),
                    "v":  int(row["volume"]),
                })

            return {
                "symbol":   symbol,
                "interval": interval,
                "period":   period,
                "count":    len(bars),
                "bars":     bars,
            }
        except Exception as e:
            logger.error(f"MarketService.get_ohlcv failed [{symbol}]: {e}")
            return {"symbol": symbol, "error": str(e), "bars": []}

    async def get_option_chain(self, expiry: Optional[str] = None) -> dict:
        """Get NIFTY option chain with PCR and basic analytics."""
        try:
            engine = self._get_engine()
            return await engine.get_option_chain(expiry)
        except Exception as e:
            logger.error(f"MarketService.get_option_chain failed: {e}")
            return {"error": str(e)}

    async def get_global_markets(self) -> dict:
        """Get all global market indices snapshot."""
        try:
            engine = self._get_engine()
            return await engine.get_global_markets()
        except Exception as e:
            logger.error(f"MarketService.get_global_markets failed: {e}")
            return {"error": str(e)}

    async def get_fii_dii(self) -> dict:
        """Get FII/DII institutional flow data."""
        try:
            engine = self._get_engine()
            return await engine.get_fii_dii()
        except Exception as e:
            logger.error(f"MarketService.get_fii_dii failed: {e}")
            return {"error": str(e)}

    async def get_nifty50_snapshot(self) -> dict:
        """Get all 50 NIFTY constituent stock quotes."""
        try:
            engine = self._get_engine()
            stocks = await engine.get_nifty50_snapshot()
            return {"stocks": stocks, "count": len(stocks)}
        except Exception as e:
            logger.error(f"MarketService.get_nifty50_snapshot failed: {e}")
            return {"error": str(e), "stocks": []}

    async def get_market_status(self) -> dict:
        """Get current NSE market session status."""
        try:
            from modules.market_data.market_hours import market_status_summary
            return market_status_summary()
        except Exception as e:
            return {"error": str(e)}


# ── Dependency injection helper ────────────────────────────────────────────────
_service_instance: Optional[MarketService] = None


def get_market_service() -> MarketService:
    """FastAPI dependency: returns singleton MarketService."""
    global _service_instance
    if _service_instance is None:
        _service_instance = MarketService()
    return _service_instance
