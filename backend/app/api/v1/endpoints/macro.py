"""
NEXUS AI — Macro Intelligence REST API Endpoints (Phase 5)

Endpoints:
  GET /api/v1/macro/snapshot        — Full macro snapshot
  GET /api/v1/macro/regime          — Current macro regime classification
  GET /api/v1/macro/indices         — Global index prices and signals
  GET /api/v1/macro/currencies      — Currency and commodity rates
  GET /api/v1/macro/vix             — VIX and rate data
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.services.macro_service import MacroService, get_macro_service

logger = logging.getLogger(__name__)
router = APIRouter()
MacroDep = Annotated[MacroService, Depends(get_macro_service)]

_LIVE_DESC = "Set true to fetch live data (may be slow). Default: use cached/synthetic."


@router.get("/snapshot", summary="Full macro snapshot")
async def get_snapshot(svc: MacroDep, live: bool = Query(default=False, description=_LIVE_DESC)):
    return await svc.get_snapshot(use_live=live)


@router.get("/regime", summary="Current macro regime classification")
async def get_regime(svc: MacroDep, live: bool = Query(default=False, description=_LIVE_DESC)):
    return await svc.get_regime(use_live=live)


@router.get("/indices", summary="Global index prices and signals")
async def get_global_indices(svc: MacroDep, live: bool = Query(default=False, description=_LIVE_DESC)):
    return await svc.get_global_indices(use_live=live)


@router.get("/currencies", summary="Currency and commodity rates")
async def get_currencies(svc: MacroDep, live: bool = Query(default=False, description=_LIVE_DESC)):
    return await svc.get_currencies(use_live=live)


@router.get("/vix", summary="VIX levels and US rate data")
async def get_vix(svc: MacroDep, live: bool = Query(default=False, description=_LIVE_DESC)):
    return await svc.get_vix(use_live=live)
