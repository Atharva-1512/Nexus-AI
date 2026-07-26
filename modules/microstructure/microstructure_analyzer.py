"""
NEXUS AI — Microstructure Analyzer (Module 2)

Analyzes order book and trade tape data to extract:
- Spread classification (tight/normal/wide)
- Order flow toxicity (informed vs noise trading)
- Market depth pressure
- FIFO queue position estimation
- Liquidity score
- Execution quality metrics

Used by the Decision Engine to assess trade execution conditions.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Optional

from .order_book import OrderBook, TimeAndSales, Trade, OrderSide

logger = logging.getLogger(__name__)


@dataclass
class SpreadClassification:
    spread_abs:      float
    spread_pct:      float
    classification:  str    # "TIGHT" | "NORMAL" | "WIDE" | "ILLIQUID"
    is_tradeable:    bool


@dataclass
class MicrostructureSignal:
    """
    Aggregated microstructure signal for the Decision Engine.

    A positive score suggests buyers are in control (bullish microstructure).
    A negative score suggests sellers are in control (bearish microstructure).
    """
    symbol:           str
    timestamp:        datetime
    score:            float           # -1.0 (bearish) to +1.0 (bullish)
    order_imbalance:  Optional[float] # From order book
    delta:            Optional[int]   # Buy vol - sell vol
    spread_pct:       Optional[float]
    liquidity_score:  float           # 0–1 (1 = highly liquid)
    is_liquid:        bool
    narrative:        str             # Human-readable summary


class MicrostructureAnalyzer:
    """
    Derives trading signals from Level 2 order book and Time & Sales.

    For NIFTY options, key microstructure signals:
    - Tight spread + high bid qty → support
    - Widening spread → caution (low liquidity)
    - Large buy delta on T&S → call buyers active
    - Order book imbalance > 0.3 → directional pressure
    """

    def __init__(
        self,
        tight_spread_threshold: float = 0.1,  # % spread considered tight
        wide_spread_threshold:  float = 0.5,  # % spread considered wide
        min_liquidity_depth:    int   = 1000, # Min bid+ask qty for liquid market
    ):
        self.tight_threshold = tight_spread_threshold
        self.wide_threshold  = wide_spread_threshold
        self.min_depth       = min_liquidity_depth

    def classify_spread(self, book: OrderBook) -> SpreadClassification:
        """
        Classify the current bid-ask spread.

        Returns:
            SpreadClassification with category and tradability flag
        """
        spread_pct = book.spread_pct or 0.0
        spread_abs = book.spread or 0.0

        if spread_pct == 0.0:
            classification = "ILLIQUID"
            tradeable = False
        elif spread_pct <= self.tight_threshold:
            classification = "TIGHT"
            tradeable = True
        elif spread_pct <= self.wide_threshold:
            classification = "NORMAL"
            tradeable = True
        else:
            classification = "WIDE"
            tradeable = spread_pct < 2.0  # > 2% spread is untradeable

        return SpreadClassification(
            spread_abs=spread_abs,
            spread_pct=spread_pct,
            classification=classification,
            is_tradeable=tradeable,
        )

    def compute_liquidity_score(self, book: OrderBook) -> float:
        """
        Compute a 0–1 liquidity score for the instrument.

        Factors:
        - Total depth (bid + ask qty)
        - Spread tightness
        - Number of price levels

        Returns:
            0.0 (illiquid) to 1.0 (highly liquid)
        """
        total_depth = book.total_bid_qty + book.total_ask_qty
        spread_pct  = book.spread_pct or 9.9

        # Depth component (0–0.5)
        depth_score = min(total_depth / (self.min_depth * 10), 0.5)

        # Spread component (0–0.5): tighter spread = higher score
        spread_score = max(0, 0.5 - spread_pct * 0.5)

        return round(min(1.0, depth_score + spread_score), 3)

    def analyze_order_flow(self, tape: TimeAndSales) -> dict:
        """
        Analyze recent order flow from Time & Sales.

        Returns:
            Dict with flow direction, strength, and classification
        """
        if not tape.trades:
            return {"direction": "UNKNOWN", "strength": 0.0, "delta": 0}

        total_volume = tape.buy_volume + tape.sell_volume
        delta        = tape.delta

        if total_volume == 0:
            return {"direction": "UNKNOWN", "strength": 0.0, "delta": 0}

        imbalance = delta / total_volume  # -1 to +1

        if imbalance > 0.3:
            direction = "BUYING"
            strength  = min(1.0, imbalance)
        elif imbalance < -0.3:
            direction = "SELLING"
            strength  = min(1.0, abs(imbalance))
        else:
            direction = "NEUTRAL"
            strength  = 0.0

        # Large trade detection (whale activity)
        avg_trade_size = total_volume / max(len(tape.trades), 1)
        large_trades   = [t for t in tape.trades if t.quantity > avg_trade_size * 3]
        large_buy      = sum(t.quantity for t in large_trades if t.side == OrderSide.BUY)
        large_sell     = sum(t.quantity for t in large_trades if t.side == OrderSide.SELL)

        return {
            "direction":          direction,
            "strength":           round(strength, 3),
            "delta":              delta,
            "buy_volume":         tape.buy_volume,
            "sell_volume":        tape.sell_volume,
            "imbalance":          round(imbalance, 4),
            "vwap":               tape.vwap,
            "large_buy_qty":      large_buy,
            "large_sell_qty":     large_sell,
            "whale_bias":         "BUY" if large_buy > large_sell else "SELL" if large_sell > large_buy else "NEUTRAL",
        }

    def generate_signal(
        self,
        book: OrderBook,
        tape: Optional[TimeAndSales] = None,
    ) -> MicrostructureSignal:
        """
        Generate a consolidated microstructure signal.

        Combines order book imbalance and trade flow analysis
        into a single directional score.

        Args:
            book: Current order book snapshot
            tape: Recent Time & Sales (optional)

        Returns:
            MicrostructureSignal with score -1 to +1
        """
        spread_cls     = self.classify_spread(book)
        liquidity_score = self.compute_liquidity_score(book)
        imbalance      = book.order_imbalance or 0.0

        # Start with order book imbalance contribution (50% weight)
        score = imbalance * 0.5

        # Add T&S flow contribution (50% weight)
        flow_delta = 0.0
        flow_info  = {}
        if tape and tape.trades:
            flow_info  = self.analyze_order_flow(tape)
            total_vol  = tape.buy_volume + tape.sell_volume
            flow_delta = (tape.delta / max(total_vol, 1)) * 0.5
            score     += flow_delta

        # Penalise wide spread (unreliable signal when illiquid)
        if spread_cls.classification == "WIDE":
            score *= 0.5
        elif spread_cls.classification == "ILLIQUID":
            score = 0.0

        score = max(-1.0, min(1.0, round(score, 4)))

        # Narrative
        parts = []
        if imbalance > 0.2:
            parts.append(f"Order book bid-heavy ({imbalance:+.2f} imbalance)")
        elif imbalance < -0.2:
            parts.append(f"Order book ask-heavy ({imbalance:+.2f} imbalance)")

        if flow_info.get("direction") == "BUYING":
            parts.append(f"Buy flow dominant (delta: +{flow_info.get('delta', 0)})")
        elif flow_info.get("direction") == "SELLING":
            parts.append(f"Sell flow dominant (delta: {flow_info.get('delta', 0)})")

        if not spread_cls.is_tradeable:
            parts.append(f"Wide spread ({spread_cls.spread_pct:.2f}%) — avoid entry")

        narrative = "; ".join(parts) if parts else "Microstructure neutral"

        return MicrostructureSignal(
            symbol          = book.symbol,
            timestamp       = book.timestamp,
            score           = score,
            order_imbalance = imbalance,
            delta           = tape.delta if tape else None,
            spread_pct      = spread_cls.spread_pct,
            liquidity_score = liquidity_score,
            is_liquid       = spread_cls.is_tradeable and liquidity_score > 0.3,
            narrative       = narrative,
        )

    def estimate_market_impact(
        self,
        book:       OrderBook,
        order_size: int,
        side:       str = "BUY",
    ) -> dict:
        """
        Estimate market impact for executing a given order size.

        Walks the order book to compute average fill price.

        Args:
            book:       Current order book
            order_size: Number of lots to execute
            side:       "BUY" (hits asks) or "SELL" (hits bids)

        Returns:
            Dict with avg_fill_price, slippage_pct, levels_consumed
        """
        levels  = book.asks if side == "BUY" else book.bids
        remaining = order_size
        total_cost = 0.0
        levels_consumed = 0

        for level in levels:
            if remaining <= 0:
                break
            fill_qty   = min(remaining, level.quantity)
            total_cost += fill_qty * level.price
            remaining  -= fill_qty
            levels_consumed += 1

        if order_size == remaining:
            return {"error": "Insufficient liquidity in order book"}

        filled_qty  = order_size - remaining
        avg_price   = total_cost / filled_qty if filled_qty > 0 else 0
        ref_price   = book.best_ask if side == "BUY" else book.best_bid
        slippage    = ((avg_price - ref_price) / ref_price * 100) if ref_price else 0

        return {
            "avg_fill_price":    round(avg_price, 2),
            "slippage_pct":      round(abs(slippage), 4),
            "filled_qty":        filled_qty,
            "unfilled_qty":      remaining,
            "levels_consumed":   levels_consumed,
            "fully_filled":      remaining == 0,
        }
