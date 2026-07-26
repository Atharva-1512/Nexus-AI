"""
NEXUS AI — Order Book & Market Microstructure Data Models (Module 2)

Represents the full Level 2 order book:
- Best bid / ask (BBO)
- Market depth (multiple price levels)
- Spread analysis
- Order flow metrics
- Time & Sales (trade tape)

For NIFTY options, NSE provides up to 5 levels of market depth.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class OrderSide(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT  = "LIMIT"
    IOC    = "IOC"     # Immediate or Cancel
    STOP   = "STOP"


@dataclass
class PriceLevel:
    """A single price level in the order book (bid or ask)."""
    price:    float
    quantity: int
    orders:   int = 1   # Number of orders at this price (if available)


@dataclass
class OrderBook:
    """
    Level 2 order book snapshot for a single instrument.

    NSE provides 5 levels of bid/ask depth.
    """
    symbol:    str
    timestamp: datetime
    bids:      list[PriceLevel] = field(default_factory=list)  # Descending: best bid first
    asks:      list[PriceLevel] = field(default_factory=list)  # Ascending: best ask first
    last_price: Optional[float] = None
    volume:    int = 0

    # ── Derived properties ────────────────────────────────────────────────────

    @property
    def best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    @property
    def spread(self) -> Optional[float]:
        """Absolute bid-ask spread."""
        if self.best_bid and self.best_ask:
            return round(self.best_ask - self.best_bid, 2)
        return None

    @property
    def spread_pct(self) -> Optional[float]:
        """Spread as % of mid-price."""
        if self.best_bid and self.best_ask:
            mid = self.mid_price
            return round((self.best_ask - self.best_bid) / mid * 100, 4) if mid else None
        return None

    @property
    def mid_price(self) -> Optional[float]:
        if self.best_bid and self.best_ask:
            return round((self.best_bid + self.best_ask) / 2, 2)
        return None

    @property
    def total_bid_qty(self) -> int:
        return sum(level.quantity for level in self.bids)

    @property
    def total_ask_qty(self) -> int:
        return sum(level.quantity for level in self.asks)

    @property
    def order_imbalance(self) -> Optional[float]:
        """
        Order book imbalance: (bid_qty - ask_qty) / (bid_qty + ask_qty)
        Range: -1 (strong sell pressure) to +1 (strong buy pressure)
        """
        total_bid = self.total_bid_qty
        total_ask = self.total_ask_qty
        total = total_bid + total_ask
        if total == 0:
            return None
        return round((total_bid - total_ask) / total, 4)

    @property
    def depth_5_bid(self) -> float:
        """Total quantity in top 5 bid levels."""
        return sum(level.quantity for level in self.bids[:5])

    @property
    def depth_5_ask(self) -> float:
        """Total quantity in top 5 ask levels."""
        return sum(level.quantity for level in self.asks[:5])

    def to_dict(self) -> dict:
        return {
            "symbol":           self.symbol,
            "timestamp":        self.timestamp.isoformat(),
            "best_bid":         self.best_bid,
            "best_ask":         self.best_ask,
            "spread":           self.spread,
            "spread_pct":       self.spread_pct,
            "mid_price":        self.mid_price,
            "order_imbalance":  self.order_imbalance,
            "total_bid_qty":    self.total_bid_qty,
            "total_ask_qty":    self.total_ask_qty,
            "depth_5_bid":      self.depth_5_bid,
            "depth_5_ask":      self.depth_5_ask,
            "last_price":       self.last_price,
            "volume":           self.volume,
            "bids":             [{"price": b.price, "qty": b.quantity} for b in self.bids],
            "asks":             [{"price": a.price, "qty": a.quantity} for a in self.asks],
        }


@dataclass
class Trade:
    """A single executed trade from the Time & Sales tape."""
    symbol:    str
    timestamp: datetime
    price:     float
    quantity:  int
    side:      OrderSide         # BUY or SELL (inferred from tick direction)
    trade_id:  Optional[str] = None


@dataclass
class TimeAndSales:
    """
    Time & Sales (trade tape) for a single instrument.
    Contains the last N executed trades.
    """
    symbol:  str
    trades:  list[Trade] = field(default_factory=list)
    max_size: int = 500   # Rolling window size

    def add_trade(self, trade: Trade) -> None:
        self.trades.insert(0, trade)
        if len(self.trades) > self.max_size:
            self.trades.pop()

    @property
    def buy_volume(self) -> int:
        return sum(t.quantity for t in self.trades if t.side == OrderSide.BUY)

    @property
    def sell_volume(self) -> int:
        return sum(t.quantity for t in self.trades if t.side == OrderSide.SELL)

    @property
    def delta(self) -> int:
        """Buy volume minus sell volume (positive = buyers in control)."""
        return self.buy_volume - self.sell_volume

    @property
    def cumulative_delta(self) -> list[int]:
        """Running cumulative delta over all trades (oldest first)."""
        cd = 0
        result = []
        for trade in reversed(self.trades):
            cd += trade.quantity if trade.side == OrderSide.BUY else -trade.quantity
            result.append(cd)
        return result

    @property
    def vwap(self) -> Optional[float]:
        """Volume-weighted average price of all trades in tape."""
        total_volume = sum(t.quantity for t in self.trades)
        if total_volume == 0:
            return None
        total_value = sum(t.price * t.quantity for t in self.trades)
        return round(total_value / total_volume, 2)

    def to_dict(self) -> dict:
        return {
            "symbol":           self.symbol,
            "trade_count":      len(self.trades),
            "buy_volume":       self.buy_volume,
            "sell_volume":      self.sell_volume,
            "delta":            self.delta,
            "vwap":             self.vwap,
            "recent_trades":    [
                {
                    "price": t.price,
                    "qty":   t.quantity,
                    "side":  t.side.value,
                    "ts":    t.timestamp.isoformat(),
                }
                for t in self.trades[:20]   # Last 20 trades
            ],
        }
