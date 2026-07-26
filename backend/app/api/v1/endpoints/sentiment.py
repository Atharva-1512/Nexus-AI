"""
NEXUS AI — Sentiment Intelligence REST API Endpoints (Phase 6)

Endpoints:
  GET /api/v1/sentiment/signal      — Full combined sentiment signal
  GET /api/v1/sentiment/news        — News headlines + sentiment scores
  GET /api/v1/sentiment/fear-greed  — Fear & Greed index
  GET /api/v1/sentiment/breadth     — Market breadth (A/D ratio, DMA %)
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.services.sentiment_service import SentimentService, get_sentiment_service

logger = logging.getLogger(__name__)
router = APIRouter()
SentDep = Annotated[SentimentService, Depends(get_sentiment_service)]

_SCENARIO_DESC = "Market scenario: 'neutral' (default), 'bullish', 'bearish'"


@router.get("/signal", summary="Full sentiment signal (news + social)")
async def get_signal(
    svc:      SentDep,
    scenario: str   = Query(default="neutral", description=_SCENARIO_DESC),
    vix:      float = Query(default=15.0, description="India VIX level"),
    pcr:      float = Query(default=1.0,  description="Put-Call Ratio"),
):
    return await svc.get_signal(scenario=scenario, india_vix=vix, pcr=pcr)


@router.get("/news", summary="News headlines with sentiment scores")
async def get_news(
    svc:      SentDep,
    scenario: str = Query(default="neutral", description=_SCENARIO_DESC),
):
    return await svc.get_news(scenario=scenario)


@router.get("/fear-greed", summary="Fear & Greed index")
async def get_fear_greed(
    svc:      SentDep,
    vix:      float = Query(default=15.0,   description="India VIX"),
    pcr:      float = Query(default=1.0,    description="Put-Call Ratio"),
    spot:     float = Query(default=24000.0,description="NIFTY spot price"),
    sma50:    float = Query(default=23500.0,description="NIFTY 50-DMA"),
    advances: int   = Query(default=25,     description="Advancing stocks"),
    declines: int   = Query(default=25,     description="Declining stocks"),
    gold_chg: float = Query(default=0.0,    description="Gold 1-day % change"),
):
    return await svc.get_fear_greed(
        india_vix=vix, pcr=pcr, spot=spot, sma_50=sma50,
        advances=advances, declines=declines, gold_chg=gold_chg,
    )


@router.get("/breadth", summary="Market breadth (Advance-Decline)")
async def get_breadth(
    svc:       SentDep,
    advances:  int = Query(default=25, description="Advancing NIFTY50 stocks"),
    declines:  int = Query(default=25, description="Declining NIFTY50 stocks"),
    unchanged: int = Query(default=0,  description="Unchanged stocks"),
):
    return await svc.get_breadth(advances=advances, declines=declines, unchanged=unchanged)
