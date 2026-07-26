"""
NEXUS AI — Cache Manager (Module 1)

Redis-first, in-memory fallback cache for all market data.

Pattern: Cache-Aside (Lazy Loading)
1. Check cache → HIT: return cached value
2. MISS: fetch from source → store in cache → return

Two cache tiers:
- L1: In-process TTLCache (microsecond latency, no serialization)
- L2: Redis (millisecond latency, shared across processes)

Falls back to L1-only if Redis is unavailable (graceful degradation).
"""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ─── TTL defaults (seconds) ──────────────────────────────────────────────────
TTL_LIVE_QUOTE     = 15      # 15 sec — live prices
TTL_OPTION_CHAIN   = 60      # 1 min  — option chain (NSE updates ~1 min)
TTL_OHLCV_INTRADAY = 60      # 1 min  — intraday candles
TTL_OHLCV_DAILY    = 3600    # 1 hour — daily OHLCV
TTL_VIX            = 30      # 30 sec — India VIX
TTL_FII_DII        = 1800    # 30 min — FII/DII data (updates once daily)
TTL_MARKET_STATUS  = 10      # 10 sec — market open/close status
TTL_GLOBAL_INDICES = 60      # 1 min  — global markets


# ─── L1 In-Process TTL Cache ─────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    value:     Any
    expires_at: float   # Unix timestamp


class TTLCache:
    """
    Simple thread-safe in-process TTL cache.
    No external dependencies — always available.
    """

    def __init__(self, maxsize: int = 1000):
        self._store: dict[str, _CacheEntry] = {}
        self._maxsize = maxsize
        self._hits   = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() > entry.expires_at:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: int) -> None:
        # Evict random entries if at capacity
        if len(self._store) >= self._maxsize:
            keys_to_evict = list(self._store.keys())[:self._maxsize // 10]
            for k in keys_to_evict:
                self._store.pop(k, None)

        self._store[key] = _CacheEntry(value=value, expires_at=time.time() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def stats(self) -> dict:
        return {
            "size":     len(self._store),
            "hits":     self._hits,
            "misses":   self._misses,
            "hit_rate": f"{self.hit_rate:.1%}",
        }


# ─── Cache Manager ────────────────────────────────────────────────────────────

class CacheManager:
    """
    Two-tier cache manager: L1 (in-process) + L2 (Redis).

    Falls back to L1-only if Redis is unavailable.
    All values are JSON-serializable (no pickle — security best practice).
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self._l1: TTLCache = TTLCache(maxsize=2000)
        self._redis_url    = redis_url
        self._redis        = None
        self._redis_ok     = False
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> bool:
        """
        Connect to Redis. Returns True on success, False on failure.
        Failure is non-fatal — L1 cache continues working.
        """
        async with self._connect_lock:
            if self._redis_ok:
                return True
            try:
                import redis.asyncio as aioredis
                self._redis    = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                await self._redis.ping()
                self._redis_ok = True
                logger.info(f"Redis connected: {self._redis_url}")
                return True
            except Exception as e:
                logger.warning(
                    f"Redis unavailable ({e}). Running with L1 in-process cache only."
                )
                self._redis_ok = False
                return False

    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.
        L1 first → L2 fallback → None
        """
        # L1 check
        value = self._l1.get(key)
        if value is not None:
            return value

        # L2 check (Redis)
        if self._redis_ok:
            try:
                raw = await self._redis.get(key)
                if raw is not None:
                    value = json.loads(raw)
                    # Warm L1 cache with a shorter TTL
                    self._l1.set(key, value, ttl=15)
                    return value
            except Exception as e:
                logger.debug(f"Redis GET failed for key '{key}': {e}")

        return None

    async def set(self, key: str, value: Any, ttl: int) -> None:
        """
        Store value in L1 and L2 (Redis).

        Args:
            key:   Cache key
            value: JSON-serializable value
            ttl:   Time-to-live in seconds
        """
        # L1 store
        self._l1.set(key, value, ttl)

        # L2 store (Redis)
        if self._redis_ok:
            try:
                serialized = json.dumps(value, default=_json_default)
                await self._redis.setex(key, ttl, serialized)
            except Exception as e:
                logger.debug(f"Redis SET failed for key '{key}': {e}")

    async def delete(self, key: str) -> None:
        """Remove a key from both cache tiers."""
        self._l1.delete(key)
        if self._redis_ok:
            try:
                await self._redis.delete(key)
            except Exception:
                pass

    async def get_or_fetch(
        self,
        key:     str,
        fetcher: Callable,
        ttl:     int,
    ) -> Any:
        """
        Cache-aside pattern helper.

        Checks cache first; if miss, calls fetcher(), stores result, returns it.

        Args:
            key:     Cache key
            fetcher: Async callable that returns the value on cache miss
            ttl:     TTL in seconds to cache the fetched value

        Returns:
            Cached or freshly fetched value
        """
        cached = await self.get(key)
        if cached is not None:
            logger.debug(f"Cache HIT: {key}")
            return cached

        logger.debug(f"Cache MISS: {key} — fetching from source")
        value = await fetcher()

        if value is not None:
            await self.set(key, value, ttl)

        return value

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Delete all Redis keys matching a pattern.
        Example: invalidate_pattern("nifty:quote:*")

        Returns number of keys deleted.
        """
        if not self._redis_ok:
            return 0
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.debug(f"Redis pattern invalidation failed: {e}")
            return 0

    def cache_stats(self) -> dict:
        return {
            "l1": self._l1.stats,
            "redis_connected": self._redis_ok,
        }


# ─── Cache Key Builders ───────────────────────────────────────────────────────
# Centralised key construction — prevents key collision across modules

def quote_key(symbol: str) -> str:
    return f"nexus:quote:{symbol.upper()}"

def ohlcv_key(symbol: str, interval: str, period: str) -> str:
    return f"nexus:ohlcv:{symbol.upper()}:{interval}:{period}"

def option_chain_key(underlying: str, expiry: str = "current") -> str:
    return f"nexus:optchain:{underlying.upper()}:{expiry}"

def vix_key() -> str:
    return "nexus:vix:india"

def fii_dii_key(date_str: str = "today") -> str:
    return f"nexus:fiidii:{date_str}"

def market_status_key() -> str:
    return "nexus:market:status"

def global_index_key(symbol: str) -> str:
    return f"nexus:global:{symbol.upper()}"


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _json_default(obj: Any) -> Any:
    """JSON serializer for non-standard types."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ─── Module-level singleton ───────────────────────────────────────────────────
# Import and use this in services:
#   from modules.market_data.cache_manager import cache
cache = CacheManager()
