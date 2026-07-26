"""
NEXUS AI — Alert Engine REST API Endpoints (Phase 9)

Endpoints:
  GET  /api/v1/alerts/history   — Get recent alerts feed
  POST /api/v1/alerts/test      — Trigger a test desktop alert + sound
  POST /api/v1/alerts/settings  — Configure sound & desktop notification toggles
  POST /api/v1/alerts/read-all  — Mark all alerts as read
  DELETE /api/v1/alerts/clear  — Clear alert history
"""
import logging
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Query
from app.services.alert_service import AlertService, get_alert_service

logger = logging.getLogger(__name__)
router = APIRouter()
AlertDep = Annotated[AlertService, Depends(get_alert_service)]


@router.get("/history", summary="Get alert history")
@router.get("/", summary="Get recent alerts (alias)")
async def get_history(
    svc: AlertDep,
    limit: int = Query(default=50, ge=1, le=200),
    unread_only: bool = Query(default=False),
):
    return svc.get_recent_alerts(limit=limit, unread_only=unread_only)


@router.post("/test", summary="Trigger test desktop notification with sound")
async def trigger_test_alert(
    svc: AlertDep,
    title: str = Query(default="NEXUS AI Alert"),
    message: str = Query(default="Test notification with audio alert"),
):
    return svc.trigger_test_alert(title=title, message=message)


@router.post("/settings", summary="Update alert notification settings")
async def update_settings(
    svc: AlertDep,
    enabled: bool = Query(default=True),
    sound: bool = Query(default=True),
    desktop: bool = Query(default=True),
):
    return svc.update_settings(enabled=enabled, sound=sound, desktop=desktop)


@router.post("/read-all", summary="Mark all alerts as read")
async def mark_all_read(svc: AlertDep):
    return svc.mark_all_read()


@router.delete("/clear", summary="Clear alert history")
async def clear_alerts(svc: AlertDep):
    return svc.clear_all()
