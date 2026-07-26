"""
NEXUS AI — Explainability Dashboard REST API Endpoints (Phase 10)

Endpoints:
  GET /api/v1/explainability/report  — Factor weights, SHAP values, and key reasons
"""
import logging
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from app.services.explainability_service import ExplainabilityService, get_explainability_service

logger = logging.getLogger(__name__)
router = APIRouter()
ExpDep = Annotated[ExplainabilityService, Depends(get_explainability_service)]


@router.get("/report", summary="Get explainability report with factor weights and SHAP values")
async def get_report(
    svc: ExpDep,
    recommendation: str = Query(default="BUY_CALL"),
    confidence: float = Query(default=91.0),
):
    return svc.get_explainability(recommendation=recommendation, confidence=confidence)
