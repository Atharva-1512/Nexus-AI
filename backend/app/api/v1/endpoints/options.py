"""
NEXUS AI — Options Chain REST API Endpoints (Phase 3)

Provides the full option chain intelligence via REST:
  GET /api/v1/options/chain            → Full option chain with OI, IV, Greeks
  GET /api/v1/options/pcr              → Put-Call Ratio analysis
  GET /api/v1/options/max-pain         → Max Pain level and reliability
  GET /api/v1/options/gex              → Gamma Exposure profile and flip level
  GET /api/v1/options/iv-skew          → IV skew metrics and table
  GET /api/v1/options/oi-analysis      → OI build-up / unwinding analysis
  GET /api/v1/options/signal           → FULL ChainSignal (all analytics combined)
  GET /api/v1/options/support-resistance → OI-based S/R levels
  GET /api/v1/options/key-strikes      → ATM, Max Pain, Call Wall, Put Wall, GEX Flip
"""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.services.options_service import OptionsService, get_options_service

logger = logging.getLogger(__name__)
router = APIRouter()

OptionsDep = Annotated[OptionsService, Depends(get_options_service)]


@router.get("/chain", summary="NIFTY option chain")
async def get_option_chain(
    svc:      OptionsDep,
    symbol:   str = Query(default="NIFTY"),
    expiry:   Optional[str] = Query(default=None),
    near_atm: int = Query(default=0, ge=0),
):
    return await svc.get_chain(symbol=symbol, expiry=expiry, near_atm=near_atm)


@router.get("/pcr", summary="Put-Call Ratio analysis")
async def get_pcr(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_pcr(symbol=symbol, expiry=expiry)


@router.get("/max-pain", summary="Max Pain level")
async def get_max_pain(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_max_pain(symbol=symbol, expiry=expiry)


@router.get("/gex", summary="Gamma Exposure profile")
async def get_gex(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_gex(symbol=symbol, expiry=expiry)


@router.get("/iv-skew", summary="Implied Volatility skew")
async def get_iv_skew(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_iv_skew(symbol=symbol, expiry=expiry)


@router.get("/oi-analysis", summary="OI build-up analysis")
async def get_oi_analysis(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_oi_analysis(symbol=symbol, expiry=expiry)


@router.get("/support-resistance", summary="OI-based S/R levels")
async def get_support_resistance(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
    n:      int = Query(default=3, ge=1, le=10),
):
    return await svc.get_support_resistance(symbol=symbol, expiry=expiry, n=n)


@router.get("/key-strikes", summary="Key price levels summary")
async def get_key_strikes(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_key_strikes(symbol=symbol, expiry=expiry)


@router.get("/signal", summary="Full chain intelligence signal")
async def get_chain_signal(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
    expiry: Optional[str] = Query(default=None),
):
    return await svc.get_chain_signal(symbol=symbol, expiry=expiry)


@router.get("/expiries", summary="Available expiry dates")
async def get_expiries(
    svc:    OptionsDep,
    symbol: str = Query(default="NIFTY"),
):
    return await svc.get_expiries(symbol=symbol)
