"""
NEXUS AI — Technical Analysis REST API Endpoints (Phase 4)

Endpoints:
  GET /api/v1/technical/signal          — Full TechSignal (all indicators combined)
  GET /api/v1/technical/indicators      — Raw indicator values
  GET /api/v1/technical/patterns        — Detected candlestick patterns
  GET /api/v1/technical/trend           — Trend direction and structure
  GET /api/v1/technical/support-resistance — Pivot points + swing S/R
  GET /api/v1/technical/chart           — OHLCV bars with indicator overlays
"""
import logging
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.services.technical_service import TechnicalService, get_technical_service

logger = logging.getLogger(__name__)
router = APIRouter()
TechDep = Annotated[TechnicalService, Depends(get_technical_service)]

_INTERVAL_DESC = "Bar interval: 1m, 5m, 15m, 30m, 1h, 1d"
_PERIOD_DESC   = "Lookback period: 1d, 5d, 1mo, 3mo, 6mo, 1y"


@router.get("/signal", summary="Full technical analysis signal")
async def get_signal(
    svc:      TechDep,
    symbol:   str = Query(default="NIFTY"),
    interval: str = Query(default="1d", description=_INTERVAL_DESC),
    period:   str = Query(default="3mo", description=_PERIOD_DESC),
):
    return await svc.get_signal(symbol=symbol, interval=interval, period=period)


@router.get("/indicators", summary="Raw indicator values")
async def get_indicators(
    svc:      TechDep,
    symbol:   str = Query(default="NIFTY"),
    interval: str = Query(default="1d"),
    period:   str = Query(default="3mo"),
):
    return await svc.get_indicators(symbol=symbol, interval=interval, period=period)


@router.get("/patterns", summary="Candlestick pattern detection")
async def get_patterns(
    svc:      TechDep,
    symbol:   str = Query(default="NIFTY"),
    interval: str = Query(default="1d"),
    period:   str = Query(default="3mo"),
):
    return await svc.get_patterns(symbol=symbol, interval=interval, period=period)


@router.get("/trend", summary="Trend direction and structure")
async def get_trend(
    svc:      TechDep,
    symbol:   str = Query(default="NIFTY"),
    interval: str = Query(default="1d"),
    period:   str = Query(default="3mo"),
):
    return await svc.get_trend(symbol=symbol, interval=interval, period=period)


@router.get("/support-resistance", summary="Pivot points and S/R levels")
async def get_support_resistance(
    svc:      TechDep,
    symbol:   str = Query(default="NIFTY"),
    interval: str = Query(default="1d"),
    period:   str = Query(default="3mo"),
):
    return await svc.get_support_resistance(symbol=symbol, interval=interval, period=period)


@router.get("/chart", summary="OHLCV bars with indicator overlays")
async def get_chart_data(
    svc:      TechDep,
    symbol:   str = Query(default="NIFTY"),
    interval: str = Query(default="1d"),
    period:   str = Query(default="3mo"),
):
    return await svc.get_ohlcv_with_indicators(symbol=symbol, interval=interval, period=period)
