"""
NEXUS AI — Market Data API Endpoints (Module 1 — Phase 2 Full Implementation)

Replaces the Phase 1 stubs with fully functional endpoints backed by:
- MarketService (business logic)
- MarketDataEngine (data orchestration)
- NSEProvider + YFinanceProvider (free data, no API key)
- Redis cache layer (15s–1h TTL per data type)
"""

import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app.services.market_service import MarketService, get_market_service

logger = logging.getLogger(__name__)
router = APIRouter()

# Type alias for DI
MarketDep = Annotated[MarketService, Depends(get_market_service)]


# ─── Market Status ─────────────────────────────────────────────────────────────

@router.get(
    "/status",
    summary="NSE market session status",
    description=(
        "Returns current NSE trading session (OPEN/CLOSED/PRE_OPEN/POST_CLOSE), "
        "IST time, whether today is an expiry day, and minutes until close."
    ),
)
async def get_market_status(svc: MarketDep):
    """Real-time NSE market session status — no caching needed (computed locally)."""
    return await svc.get_market_status()


# ─── NIFTY Quote ───────────────────────────────────────────────────────────────

@router.get(
    "/nifty/quote",
    summary="NIFTY 50 live quote",
    description=(
        "Returns the latest NIFTY 50 spot price, change, %change, day high/low. "
        "Cached for 15 seconds. Data source: Yahoo Finance (free, ~15 min delayed)."
    ),
)
async def get_nifty_quote(svc: MarketDep):
    return await svc.get_nifty_quote()


@router.get(
    "/banknifty/quote",
    summary="NIFTY Bank live quote",
)
async def get_banknifty_quote(svc: MarketDep):
    engine = svc._get_engine()
    return await engine.get_banknifty_quote()


# ─── India VIX ─────────────────────────────────────────────────────────────────

@router.get(
    "/vix",
    summary="India VIX",
    description=(
        "Returns India VIX (volatility index). "
        "VIX > 20 indicates elevated market fear. "
        "Cached 30 seconds. Source: NSE / Yahoo Finance."
    ),
)
async def get_india_vix(svc: MarketDep):
    engine = svc._get_engine()
    return await engine.get_vix()


# ─── Market Overview ───────────────────────────────────────────────────────────

@router.get(
    "/overview",
    summary="Full market overview",
    description=(
        "Single endpoint returning: NIFTY + BANKNIFTY quotes, India VIX, "
        "FII/DII flows, market session status, and key global indices. "
        "All data fetched in parallel. Perfect for dashboard home page."
    ),
)
async def get_market_overview(svc: MarketDep):
    return await svc.get_market_overview()


# ─── OHLCV / Candlestick Data ──────────────────────────────────────────────────

@router.get(
    "/ohlcv/{symbol}",
    summary="OHLCV candlestick data",
    description=(
        "Historical OHLCV bars for any symbol. "
        "Supports NIFTY, BANKNIFTY, NIFTY 50 stocks, global indices, and macro instruments. "
        "Cached 60s for intraday, 1h for daily."
    ),
)
async def get_ohlcv(
    symbol:   str,
    svc:      MarketDep,
    interval: str = Query(
        default="1d",
        description="Bar interval: 1m, 5m, 15m, 30m, 1h, 1d, 1wk, 1mo",
        pattern="^(1m|2m|5m|15m|30m|60m|1h|1d|5d|1wk|1mo|3mo)$",
    ),
    period: str = Query(
        default="3mo",
        description="Lookback period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y",
        pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|max)$",
    ),
):
    """
    Returns OHLCV data for any NEXUS symbol.

    Supported symbols: NIFTY, BANKNIFTY, RELIANCE, TCS, SP500, CRUDE_OIL,
    GOLD, USDINR, VIX, BITCOIN, and 80+ more. See /market/symbols for full list.
    """
    return await svc.get_ohlcv(symbol.upper(), interval=interval, period=period)


# ─── FII / DII Data ────────────────────────────────────────────────────────────

@router.get(
    "/fii-dii",
    summary="FII/DII institutional flow",
    description=(
        "Foreign (FII) and Domestic (DII) institutional investor buy/sell data. "
        "Updated once per trading day after market close. "
        "Key bullish signal: FII net positive. Source: NSE India (free)."
    ),
)
async def get_fii_dii(svc: MarketDep):
    return await svc.get_fii_dii()


# ─── Global Markets ────────────────────────────────────────────────────────────

@router.get(
    "/global",
    summary="Global market indices",
    description=(
        "Returns quotes for S&P 500, NASDAQ, Dow Jones, FTSE, DAX, Nikkei, "
        "Hang Seng, GIFT NIFTY, CBOE VIX, Bitcoin, Ethereum, Crude Oil, Gold, "
        "DXY, and USD/INR. All fetched in parallel. Cached 60 seconds."
    ),
)
async def get_global_markets(svc: MarketDep):
    return await svc.get_global_markets()


# ─── NIFTY 50 Constituents ─────────────────────────────────────────────────────

@router.get(
    "/nifty50/snapshot",
    summary="NIFTY 50 constituent stocks snapshot",
    description="Quote snapshot for all 50 NIFTY constituent stocks.",
)
async def get_nifty50_snapshot(svc: MarketDep):
    return await svc.get_nifty50_snapshot()


# ─── Symbol Registry ───────────────────────────────────────────────────────────

@router.get(
    "/symbols",
    summary="List all supported symbols",
    description="Returns the full NEXUS symbol registry with Yahoo Finance tickers and metadata.",
)
async def list_symbols(
    asset_class: Optional[str] = Query(default=None, description="Filter by asset class"),
    nifty50_only: bool = Query(default=False, description="Only NIFTY 50 stocks"),
):
    from modules.market_data.symbols import registry, NIFTY50_STOCKS

    if nifty50_only:
        symbols = NIFTY50_STOCKS
    else:
        symbols = registry.all_symbols()

    result = []
    for s in symbols:
        if asset_class and s.asset_class.value != asset_class:
            continue
        result.append({
            "nexus_id":     s.nexus_id,
            "yf_ticker":    s.yf_ticker,
            "display_name": s.display_name,
            "asset_class":  s.asset_class.value,
            "sector":       s.sector.value,
            "is_nifty50":   s.is_nifty50,
            "lot_size":     s.lot_size,
            "exchange":     s.exchange,
        })

    return {"symbols": result, "count": len(result)}


# ─── Market Breadth ────────────────────────────────────────────────────────────

@router.get(
    "/breadth",
    summary="NIFTY market breadth",
    description=(
        "Returns advance/decline ratio, % stocks above 20-day MA, "
        "and sector heat map for the NIFTY 50. "
        "Useful for gauging broad market participation."
    ),
)
async def get_market_breadth(svc: MarketDep):
    # TODO (Phase 5): Full breadth calculation with rolling MAs
    return JSONResponse(content={
        "status": "Phase 5 implementation",
        "description": "Will return advance/decline ratio, MA breadth, sector heat.",
    })


# ─── Historical Volatility ─────────────────────────────────────────────────────

@router.get(
    "/volatility/{symbol}",
    summary="Historical volatility",
    description="Returns 10, 20, and 30-day historical volatility (annualised).",
)
async def get_historical_volatility(symbol: str, svc: MarketDep):
    import numpy as np

    try:
        data = await svc.get_ohlcv(symbol.upper(), interval="1d", period="3mo")
        bars = data.get("bars", [])

        if len(bars) < 21:
            raise HTTPException(status_code=422, detail="Insufficient data for HV calculation")

        closes = [b["c"] for b in bars]
        log_returns = [
            np.log(closes[i] / closes[i - 1])
            for i in range(1, len(closes))
        ]

        def hv(n: int) -> float:
            if len(log_returns) < n:
                return 0.0
            return round(float(np.std(log_returns[-n:]) * np.sqrt(252) * 100), 2)

        return {
            "symbol": symbol.upper(),
            "hv_10":  hv(10),
            "hv_20":  hv(20),
            "hv_30":  hv(30),
            "unit":   "% annualised",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HV calculation failed for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
