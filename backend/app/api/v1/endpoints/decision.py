"""
NEXUS AI — Master Decision Engine REST API (Phase 7)

Endpoints:
  GET /api/v1/decision/recommend   — Full trading recommendation
  GET /api/v1/decision/factors     — Factor breakdown (explainability)
  GET /api/v1/decision/trade       — Trade details only
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.services.decision_service import DecisionService, get_decision_service

logger = logging.getLogger(__name__)
router = APIRouter()
DecDep = Annotated[DecisionService, Depends(get_decision_service)]


@router.get("/recommend", summary="Full NIFTY option recommendation")
async def get_recommendation(
    svc:      DecDep,
    spot:     float = Query(default=24000.0, description="Current NIFTY spot price"),
    scenario: str   = Query(default="neutral", description="'bullish'|'bearish'|'neutral'"),
):
    return await svc.get_recommendation(spot=spot, scenario=scenario)


@router.get("/factors", summary="Factor breakdown for explainability")
async def get_factors(
    svc:      DecDep,
    spot:     float = Query(default=24000.0),
    scenario: str   = Query(default="neutral"),
):
    return await svc.get_factors(spot=spot, scenario=scenario)


@router.get("/trade", summary="Specific option trade details")
async def get_trade(
    svc:      DecDep,
    spot:     float = Query(default=24000.0),
    scenario: str   = Query(default="neutral"),
):
    return await svc.get_trade(spot=spot, scenario=scenario)
