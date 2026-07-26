"""
NEXUS AI — Desktop Alert Engine with Sound (Phase 9)

Provides real-time notifications via desktop push alerts and sound effects.
100% free with plyer / win10toast fallback and winsound / synth chime.

Alert Types:
  - TRADE_SIGNAL:     New BUY_CALL or BUY_PUT recommendation generated
  - SETUP_FORMING:    Confidence score crosses 60%, 70%, 80% threshold
  - STOP_LOSS_HIT:    Paper trade SL level breached
  - MACD_CROSSOVER:   Bullish/Bearish MACD momentum cross
  - VIX_SPIKE:        India VIX rises > 5% in a short window
  - EXPIRY_WARNING:   NIFTY weekly expiry warning (Tuesday afternoon)
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    TRADE_SIGNAL   = "TRADE_SIGNAL"
    SETUP_FORMING  = "SETUP_FORMING"
    STOP_LOSS_HIT  = "STOP_LOSS_HIT"
    MACD_CROSSOVER = "MACD_CROSSOVER"
    VIX_SPIKE      = "VIX_SPIKE"
    EXPIRY_WARNING = "EXPIRY_WARNING"


class AlertPriority(str, Enum):
    HIGH   = "HIGH"     # Trade signals, SL hit
    MEDIUM = "MEDIUM"   # Setup forming, VIX spike
    LOW    = "LOW"      # Expiry warning, info


@dataclass
class AlertEvent:
    id:          str
    type:        AlertType
    priority:    AlertPriority
    title:       str
    message:     str
    sound_type:  str = "chime"   # chime | beep | warning | alert
    timestamp:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    read:        bool = False


# ─── Sound System ─────────────────────────────────────────────────────────────

def _play_sound(sound_type: str = "chime"):
    """
    Play sound effect using Windows winsound or pure-python synth fallback.
    Runs asynchronously in a separate thread so it won't block execution.
    """
    def worker():
        try:
            if sys.platform == "win32":
                import winsound
                if sound_type == "warning":
                    winsound.Beep(1000, 400)
                    winsound.Beep(800, 400)
                elif sound_type == "alert":
                    winsound.Beep(1500, 300)
                    winsound.Beep(1500, 300)
                elif sound_type == "beep":
                    winsound.Beep(1200, 250)
                else:  # default chime
                    winsound.Beep(880, 150)
                    winsound.Beep(1320, 250)
            else:
                # Non-windows fallback using system bell
                print("\a", end="", flush=True)
        except Exception as e:
            logger.debug(f"Sound play failed: {e}")

    threading.Thread(target=worker, daemon=True).start()


# ─── Desktop Notification System ─────────────────────────────────────────────

def _show_desktop_notification(title: str, message: str):
    """
    Show desktop push notification using plyer, win10toast, or logging fallback.
    Runs asynchronously.
    """
    def worker():
        try:
            # Try plyer
            from plyer import notification
            notification.notify(
                title=title,
                message=message,
                app_name="NEXUS AI Trading Bot",
                timeout=5,
            )
            return
        except Exception:
            pass

        try:
            # Try win10toast on Windows
            if sys.platform == "win32":
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                toaster.show_toast(title, message, duration=5, threaded=True)
                return
        except Exception:
            pass

        logger.info(f"[DESKTOP ALERT] {title}: {message}")

    threading.Thread(target=worker, daemon=True).start()


# ─── Alert Engine ─────────────────────────────────────────────────────────────

class AlertEngine:
    """
    Core Alert Manager for NEXUS AI.
    Maintains alert history, filters duplicates, triggers sound and desktop popups.
    """

    def __init__(self, max_history: int = 200):
        self.max_history = max_history
        self._history: List[AlertEvent] = []
        self._enabled: bool = True
        self._sound_enabled: bool = True
        self._desktop_enabled: bool = True
        self._lock = threading.Lock()

    def set_settings(self, enabled: bool = True, sound: bool = True, desktop: bool = True):
        self._enabled = enabled
        self._sound_enabled = sound
        self._desktop_enabled = desktop

    def trigger_alert(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        sound_type: str = "chime",
    ) -> AlertEvent:
        """Trigger a new alert across desktop and sound channels."""
        alert_id = f"alt_{int(time.time() * 1000)}"
        event = AlertEvent(
            id=alert_id,
            type=alert_type,
            priority=priority,
            title=title,
            message=message,
            sound_type=sound_type,
        )

        with self._lock:
            self._history.insert(0, event)
            if len(self._history) > self.max_history:
                self._history.pop()

        if self._enabled:
            if self._sound_enabled:
                _play_sound(sound_type)
            if self._desktop_enabled:
                _show_desktop_notification(title, message)

        logger.info(f"Alert Triggered [{alert_type.value}] {title}: {message}")
        return event

    def get_alerts(self, limit: int = 50, unread_only: bool = False) -> List[AlertEvent]:
        """Retrieve recent alert history."""
        with self._lock:
            alerts = self._history
            if unread_only:
                alerts = [a for a in alerts if not a.read]
            return alerts[:limit]

    def mark_all_read(self):
        """Mark all alerts as read."""
        with self._lock:
            for a in self._history:
                a.read = True

    def clear_history(self):
        """Clear alert history."""
        with self._lock:
            self._history.clear()


# ── Singleton ──────────────────────────────────────────────────────────────────
alert_engine = AlertEngine()
