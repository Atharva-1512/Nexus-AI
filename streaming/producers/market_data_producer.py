"""
NEXUS AI — Market Data Kafka Producer (Streaming Layer)

Publishes real-time market data events to Kafka topics.
Consumers (ML engine, alert engine, frontend WebSocket) subscribe to these topics.

Topics published:
- nexus.market.data      — NIFTY quotes, global indices
- nexus.option.chain     — Option chain snapshots
- nexus.signals          — AI trade signals
- nexus.alerts           — Alert events

Design:
- Falls back gracefully if Kafka is unavailable
- All messages are JSON-serialized
- Each message includes a schema version for forward compatibility
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"


def _build_message(topic: str, payload: Any, event_type: str) -> str:
    """Wrap any payload in the NEXUS message envelope."""
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "event_type":     event_type,
        "topic":          topic,
        "timestamp":      datetime.utcnow().isoformat() + "Z",
        "payload":        payload,
    }
    return json.dumps(envelope, default=str)


class MarketDataProducer:
    """
    Async Kafka producer for market data events.

    Falls back to a no-op if Kafka is unavailable (non-fatal).
    In development, messages are logged at DEBUG level instead.
    """

    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self._bootstrap_servers = bootstrap_servers
        self._producer          = None
        self._available         = False

    async def start(self) -> bool:
        """Connect to Kafka. Returns True on success, False if unavailable."""
        try:
            from aiokafka import AIOKafkaProducer
            self._producer = AIOKafkaProducer(
                bootstrap_servers = self._bootstrap_servers,
                value_serializer  = lambda v: v.encode("utf-8"),
                compression_type  = "gzip",
                request_timeout_ms = 5000,
            )
            await self._producer.start()
            self._available = True
            logger.info(f"Kafka producer connected: {self._bootstrap_servers}")
            return True
        except Exception as e:
            logger.warning(
                f"Kafka unavailable ({e}). "
                "Market data will not be streamed to Kafka topics. "
                "All other functionality continues normally."
            )
            self._available = False
            return False

    async def stop(self) -> None:
        """Gracefully close the Kafka producer."""
        if self._producer and self._available:
            try:
                await self._producer.stop()
            except Exception:
                pass

    async def _publish(self, topic: str, message: str, key: str | None = None) -> bool:
        """
        Publish a message to a Kafka topic.

        Args:
            topic:   Kafka topic name
            message: JSON string payload
            key:     Optional partition key

        Returns:
            True on success, False on failure
        """
        if not self._available or self._producer is None:
            logger.debug(f"[KAFKA-NOOP] {topic}: {message[:120]}...")
            return False

        try:
            key_bytes = key.encode("utf-8") if key else None
            await self._producer.send_and_wait(
                topic,
                value = message,
                key   = key_bytes,
            )
            return True
        except Exception as e:
            logger.debug(f"Kafka publish failed for topic '{topic}': {e}")
            return False

    # ── Topic-specific publishers ─────────────────────────────────────────────

    async def publish_quote(self, symbol: str, quote_data: dict) -> bool:
        """Publish a price quote to nexus.market.data."""
        from app.core.config import settings
        msg = _build_message(
            topic      = settings.KAFKA_TOPIC_MARKET_DATA,
            payload    = quote_data,
            event_type = "QUOTE",
        )
        return await self._publish(
            settings.KAFKA_TOPIC_MARKET_DATA,
            msg,
            key = symbol,
        )

    async def publish_option_chain(self, chain_data: dict) -> bool:
        """Publish an option chain snapshot to nexus.option.chain."""
        from app.core.config import settings
        msg = _build_message(
            topic      = settings.KAFKA_TOPIC_OPTION_CHAIN,
            payload    = chain_data,
            event_type = "OPTION_CHAIN_SNAPSHOT",
        )
        return await self._publish(
            settings.KAFKA_TOPIC_OPTION_CHAIN,
            msg,
            key = chain_data.get("underlying", "NIFTY"),
        )

    async def publish_signal(self, signal_data: dict) -> bool:
        """Publish an AI trade signal to nexus.signals."""
        from app.core.config import settings
        msg = _build_message(
            topic      = settings.KAFKA_TOPIC_SIGNALS,
            payload    = signal_data,
            event_type = "TRADE_SIGNAL",
        )
        return await self._publish(settings.KAFKA_TOPIC_SIGNALS, msg)

    async def publish_alert(self, alert_data: dict) -> bool:
        """Publish an alert event to nexus.alerts."""
        from app.core.config import settings
        msg = _build_message(
            topic      = settings.KAFKA_TOPIC_ALERTS,
            payload    = alert_data,
            event_type = alert_data.get("type", "ALERT"),
        )
        return await self._publish(settings.KAFKA_TOPIC_ALERTS, msg)

    @property
    def is_connected(self) -> bool:
        return self._available


# ── Module-level singleton ─────────────────────────────────────────────────────
market_producer = MarketDataProducer()
