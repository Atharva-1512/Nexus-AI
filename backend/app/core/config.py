"""
NEXUS AI — Application Configuration
Centralised settings management using Pydantic v2 BaseSettings.
All values loaded from environment variables / .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings.
    Environment variables override defaults.
    Prefix: none (direct mapping)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "NEXUS AI"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change_this_to_a_long_random_secret_key_minimum_32_chars"

    # ── Backend ───────────────────────────────────────────────────────────────
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    BACKEND_RELOAD: bool = True
    BACKEND_WORKERS: int = 1
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Accept CORS_ORIGINS as comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "nexus_ai"
    POSTGRES_USER: str = "nexus"
    POSTGRES_PASSWORD: str = "nexus_password"
    DATABASE_URL: str = "postgresql+asyncpg://nexus:nexus_password@localhost:5432/nexus_ai"

    # ── MongoDB ───────────────────────────────────────────────────────────────
    MONGO_URL: str = "mongodb://nexus:nexus_password@localhost:27017/nexus_ai?authSource=admin"
    MONGO_DB: str = "nexus_ai"

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300

    # ── Kafka ─────────────────────────────────────────────────────────────────
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_TOPIC_MARKET_DATA: str = "nexus.market.data"
    KAFKA_TOPIC_OPTION_CHAIN: str = "nexus.option.chain"
    KAFKA_TOPIC_SIGNALS: str = "nexus.signals"
    KAFKA_TOPIC_ALERTS: str = "nexus.alerts"
    KAFKA_TOPIC_NEWS: str = "nexus.news"

    # ── Free Data Providers ───────────────────────────────────────────────────
    YFINANCE_CACHE_DIR: str = "./data/cache/yfinance"
    NSE_BASE_URL: str = "https://www.nseindia.com"
    NSE_REQUEST_DELAY: float = 1.0

    # Optional free API keys
    NEWS_API_KEY: str = ""
    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USER_AGENT: str = "nexus-ai/0.1.0"
    FRED_API_KEY: str = ""

    # ── Alert Engine ──────────────────────────────────────────────────────────
    ALERT_SOUND_ENABLED: bool = True
    ALERT_DESKTOP_ENABLED: bool = True
    ALERT_MIN_CONFIDENCE: int = 70
    ALERT_QUIET_HOURS_START: str = "21:00"
    ALERT_QUIET_HOURS_END: str = "09:00"

    # ── Trading Config ────────────────────────────────────────────────────────
    PAPER_TRADING_MODE: bool = True          # NEVER disable without explicit intent
    MIN_CONFIDENCE_THRESHOLD: int = 65
    HIGH_CONFIDENCE_THRESHOLD: int = 80
    NIFTY_LOT_SIZE: int = 75
    MAX_DAILY_LOSS_PCT: float = 2.0
    DEFAULT_CAPITAL: float = 100_000.0       # INR

    # ── ML / Model Config ─────────────────────────────────────────────────────
    MODEL_REGISTRY_PATH: str = "./ml/registry"
    FEATURE_STORE_PATH: str = "./data/feature_store"
    LOOKBACK_BARS: int = 100
    PREDICTION_HORIZON: int = 5
    RETRAIN_INTERVAL_HOURS: int = 24

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return cached Settings singleton.
    Use this in dependency injection:
        settings: Settings = Depends(get_settings)
    """
    return Settings()


# ── Module-level singleton ─────────────────────────────────────────────────────
settings: Settings = get_settings()
