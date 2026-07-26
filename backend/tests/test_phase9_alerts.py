"""
NEXUS AI — Phase 9 Test Suite
Tests for Alert Engine:
  - Sound and Desktop notification triggering
  - Alert history management & priority filtering
  - Alert API Endpoints
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from modules.alerts.alert_engine import (
    AlertEngine, AlertEvent, AlertType, AlertPriority,
    alert_engine, _play_sound, _show_desktop_notification
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def engine():
    e = AlertEngine()
    e.set_settings(enabled=True, sound=False, desktop=False) # disable real sounds in tests
    return e


# ─── Core Alert Engine Tests ──────────────────────────────────────────────────

class TestAlertEngineCore:

    def test_trigger_alert_creates_event(self, engine):
        event = engine.trigger_alert(
            alert_type=AlertType.TRADE_SIGNAL,
            title="BUY CALL Signal",
            message="NIFTY 24000 CE",
            priority=AlertPriority.HIGH,
        )
        assert isinstance(event, AlertEvent)
        assert event.title == "BUY CALL Signal"
        assert event.type == AlertType.TRADE_SIGNAL
        assert event.priority == AlertPriority.HIGH

    def test_alert_history_order(self, engine):
        engine.trigger_alert(AlertType.SETUP_FORMING, "First", "Msg 1")
        engine.trigger_alert(AlertType.STOP_LOSS_HIT, "Second", "Msg 2")
        alerts = engine.get_alerts()
        assert len(alerts) == 2
        assert alerts[0].title == "Second"  # Latest first

    def test_mark_all_read(self, engine):
        engine.trigger_alert(AlertType.VIX_SPIKE, "VIX Spike", "VIX +5%")
        assert engine.get_alerts(unread_only=True)[0].read == False
        engine.mark_all_read()
        assert len(engine.get_alerts(unread_only=True)) == 0

    def test_clear_history(self, engine):
        engine.trigger_alert(AlertType.EXPIRY_WARNING, "Expiry", "Tuesday")
        assert len(engine.get_alerts()) == 1
        engine.clear_history()
        assert len(engine.get_alerts()) == 0

    def test_sound_and_desktop_async_triggers(self):
        # Ensure async helper functions execute without throwing
        _play_sound("chime")
        _show_desktop_notification("Test Title", "Test Body")


# ─── Alert API Endpoint Tests ──────────────────────────────────────────────────

class TestAlertAPI:

    def test_get_alert_history_200(self, client):
        resp = client.get("/api/v1/alerts/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "alerts" in data

    def test_trigger_test_alert_endpoint(self, client):
        resp = client.post("/api/v1/alerts/test?title=API Test&message=Hello Alert")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["alert"]["title"] == "API Test"

    def test_update_settings_endpoint(self, client):
        resp = client.post("/api/v1/alerts/settings?enabled=true&sound=true&desktop=false")
        assert resp.status_code == 200
        data = resp.json()
        assert data["settings"]["desktop"] == False

    def test_read_all_endpoint(self, client):
        resp = client.post("/api/v1/alerts/read-all")
        assert resp.status_code == 200

    def test_clear_endpoint(self, client):
        resp = client.delete("/api/v1/alerts/clear")
        assert resp.status_code == 200
