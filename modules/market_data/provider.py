"""
NEXUS AI — Abstract Data Provider Interface (Module 1)

All concrete market data providers (yfinance, NSE, Upstox, Zerodha, etc.)
MUST implement this interface. This ensures the rest of the system never
depends on a specific vendor — swap providers without changing business logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pandas as pd


# ─── Data Transfer Objects ────────────────────────────────────────────────────

@dataclass
class Quote:
    """A single real-time or delayed price quote."""
    symbol: str
    last_price: float
    change: float
    change_pct: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_qty: Optional[int] = None
    ask_qty: Optional[int] = None


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume bar."""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    interval: str = "1d"        # 1m, 5m, 15m, 30m, 1h, 1d


@dataclass
class OptionData:
    """A single option contract's data."""
    symbol: str
    expiry: datetime
    strike: float
    option_type: str            # 'CE' or 'PE'
    last_price: float
    open_interest: int
    oi_change: int
    volume: int
    iv: Optional[float] = None  # Implied Volatility
    bid: Optional[float] = None
    ask: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None


@dataclass
class OptionChain:
    """Full option chain snapshot for one underlying + expiry."""
    underlying: str
    spot_price: float
    expiry: datetime
    calls: list[OptionData] = field(default_factory=list)
    puts: list[OptionData] = field(default_factory=list)
    pcr: Optional[float] = None
    max_pain: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


# ─── Abstract Provider ────────────────────────────────────────────────────────

class DataProvider(ABC):
    """
    Abstract base class for all market data providers.

    Concrete implementations:
    - YFinanceProvider   : yfinance (free, no API key, historical + delayed)
    - NSEProvider        : NSE India direct (free, option chain, FII/DII)

    Future (paid, plug-in ready):
    - ZerodhaProvider    : Kite Connect
    - UpstoxProvider     : Upstox API v2
    - AngelOneProvider   : SmartAPI
    """

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Fetch the latest quote for a symbol."""
        ...

    @abstractmethod
    async def get_ohlcv(
        self,
        symbol: str,
        interval: str = "1d",
        period: str = "1mo",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV bars as a pandas DataFrame.

        DataFrame columns: [open, high, low, close, volume]
        Index: DatetimeIndex (timezone-aware, Asia/Kolkata)
        """
        ...

    @abstractmethod
    async def get_option_chain(
        self, underlying: str, expiry: Optional[datetime] = None
    ) -> OptionChain:
        """Fetch the full option chain for an underlying."""
        ...

    @abstractmethod
    async def get_vix(self) -> float:
        """Fetch the current India VIX value."""
        ...

    async def get_multiple_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """
        Fetch quotes for multiple symbols.
        Default: sequential calls. Providers can override for batch efficiency.
        """
        results = {}
        for symbol in symbols:
            try:
                results[symbol] = await self.get_quote(symbol)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Failed to fetch quote for {symbol}: {e}"
                )
        return results

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"
