"""
NEXUS AI — ML Pipeline REST API Endpoints (Phase 8)

Endpoints:
  GET  /api/v1/ml/prediction   — Get latest direction prediction (0-100 score)
  GET  /api/v1/ml/features     — Get feature matrix summary
  POST /api/v1/ml/train        — Train model on historical data
  GET  /api/v1/ml/model-info   — Model metadata and status
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.services.ml_service import MLService, get_ml_service

logger = logging.getLogger(__name__)
router = APIRouter()
MLDep = Annotated[MLService, Depends(get_ml_service)]


@router.get("/prediction", summary="ML model direction prediction")
async def get_prediction(
    svc:    MLDep,
    symbol: str = Query(default="NIFTY"),
    n_bars: int = Query(default=150, ge=100, description="Historical bars to use"),
):
    return await svc.get_prediction(symbol=symbol, n_bars=n_bars)


@router.get("/features", summary="Feature matrix summary")
async def get_features(
    svc:    MLDep,
    symbol: str = Query(default="NIFTY"),
    n_bars: int = Query(default=150, ge=100),
):
    return await svc.get_features(symbol=symbol, n_bars=n_bars)


@router.post("/train", summary="Train ML model on historical data")
async def train_model(
    svc:    MLDep,
    n_bars: int = Query(default=500, ge=200, description="Training bars (min 200)"),
    trend:  str = Query(default="up", description="'up'|'down'|'flat'"),
):
    return await svc.train_model(n_bars=n_bars, trend=trend)


@router.get("/model-info", summary="Model metadata and architecture")
async def get_model_info(svc: MLDep):
    return await svc.get_model_info()
