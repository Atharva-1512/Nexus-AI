"""
NEXUS AI — Pytest Configuration
Shared fixtures and test configuration for all backend tests.
"""

import sys
import os
import pytest

# ── Ensure modules are importable from backend/ ───────────────────────────────
# Add project root to sys.path so 'modules' package is findable
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Also add backend/ itself
_BACKEND_DIR = os.path.abspath(os.path.dirname(__file__) + "/..")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)


# ── Environment setup for tests ───────────────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("PAPER_TRADING_MODE", "true")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://nexus:nexus@localhost:5432/nexus_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(scope="session", autouse=True)
def ensure_paper_trading():
    """
    Critical safety check: paper trading must ALWAYS be enabled in tests.
    This fixture fails the entire test session if paper trading is disabled.
    """
    from app.core.config import settings
    assert settings.PAPER_TRADING_MODE is True, (
        "CRITICAL: PAPER_TRADING_MODE is False. "
        "Tests must never run against live trading settings."
    )
    yield
