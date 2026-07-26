"""
NEXUS AI — Alert Engine Service Layer (Phase 9)
"""
import logging
from typing import Optional, List, Dict
from modules.alerts.alert_engine import alert_engine, AlertType, AlertPriority

logger = logging.getLogger(__name__)


class AlertService:
    """Service layer for alert management endpoints."""

    def __init__(self):
        self._engine = alert_engine

    def trigger_test_alert(self, title: str = "Test Alert", message: str = "NEXUS AI Alert Engine test successful!") -> Dict:
        event = self._engine.trigger_alert(
            alert_type=AlertType.SETUP_FORMING,
            title=title,
            message=message,
            priority=AlertPriority.MEDIUM,
            sound_type="chime",
        )
        return {
            "status": "success",
            "alert": {
                "id": event.id,
                "type": event.type.value,
                "title": event.title,
                "message": event.message,
                "timestamp": event.timestamp.isoformat(),
            }
        }

    def get_recent_alerts(self, limit: int = 50, unread_only: bool = False) -> Dict:
        alerts = self._engine.get_alerts(limit=limit, unread_only=unread_only)
        return {
            "count": len(alerts),
            "alerts": [
                {
                    "id": a.id,
                    "type": a.type.value,
                    "priority": a.priority.value,
                    "title": a.title,
                    "message": a.message,
                    "sound_type": a.sound_type,
                    "timestamp": a.timestamp.isoformat(),
                    "read": a.read,
                }
                for a in alerts
            ]
        }

    def update_settings(self, enabled: bool = True, sound: bool = True, desktop: bool = True) -> Dict:
        self._engine.set_settings(enabled=enabled, sound=sound, desktop=desktop)
        return {
            "status": "updated",
            "settings": {
                "enabled": enabled,
                "sound": sound,
                "desktop": desktop,
            }
        }

    def mark_all_read(self) -> Dict:
        self._engine.mark_all_read()
        return {"status": "success", "message": "All alerts marked as read"}

    def clear_all(self) -> Dict:
        self._engine.clear_history()
        return {"status": "success", "message": "Alert history cleared"}


_svc: Optional[AlertService] = None

def get_alert_service() -> AlertService:
    global _svc
    if _svc is None:
        _svc = AlertService()
    return _svc
