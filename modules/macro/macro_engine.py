"""
NEXUS AI — Macro Intelligence Engine (Phase 5)

Tracks macroeconomic and global market signals that drive NIFTY sentiment:

Global Indices (pre-market bias):
  SGX Nifty/Gift Nifty  → Best predictor of NIFTY opening gap
  Dow Jones, S&P 500    → US market direction
  NASDAQ                → Risk-on/risk-off
  Nikkei 225, Hang Seng → Asian session mood
  DAX                   → European bias

Macro Instruments:
  USD/INR               → Rupee strength (inverse: weak INR = FII outflows = bearish NIFTY)
  Crude Oil (WTI/Brent) → High oil = import cost pressure = bearish (India is net importer)
  Gold                  → Risk-off gauge
  VIX (India + US)      → Fear index
  US 10Y Treasury Yield → Rate sensitivity, DXY proxy

FII/DII Flow:
  FII Net Buy > 0       → Bullish
  FII Net Sell          → Bearish
  DII buying on FII sell → Cushion signal

Signals computed:
  - Global Bias Score (0–100): Aggregated global market sentiment
  - Macro Risk Score (0–100): Macro headwind/tailwind
  - Combined Macro Signal: Contributes 12% to Decision Engine
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class GlobalIndexSnapshot:
    """Single global index data point."""
    symbol:      str
    name:        str
    price:       float
    change_pct:  float   # 1-day % change
    region:      str     # "US" | "ASIA" | "EUROPE" | "INDIA"
    weight:      float   # Weight in global bias score
    signal:      str     # "BULLISH" | "BEARISH" | "NEUTRAL"


@dataclass
class MacroSnapshot:
    """Snapshot of all macro instruments."""
    # Indices
    indices:        list[GlobalIndexSnapshot]

    # Currencies
    usdinr:         float   # USD/INR spot rate
    usdinr_chg_pct: float   # 1-day change
    dxy:            float   # Dollar Index
    dxy_chg_pct:    float

    # Commodities
    crude_wti:      float
    crude_chg_pct:  float
    gold:           float
    gold_chg_pct:   float

    # Volatility
    india_vix:      float
    us_vix:         float

    # US Rates
    us_10y_yield:   float
    us_10y_chg:     float   # Absolute change in bps

    # FII/DII (cached from FII tracker)
    fii_net_crore:  float   # Positive = net buy
    dii_net_crore:  float

    # Signals computed
    global_bias:    float   # 0–100 bullish score from indices
    macro_risk:     float   # 0–100 (higher = more risk/headwinds)
    combined_score: float   # 0–100 overall macro signal
    narrative:      str
    timestamp:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MacroEngine:
    """
    Fetches and analyzes global macro signals.
    Contributes 12% to the NEXUS Decision Engine.

    Data sources (all free, no API key):
      - yfinance: All index prices, currencies, commodities, VIX
      - NSE: India VIX
      - Custom FII tracker (from Phase 2)

    NIFTY-specific weightings:
      Gift Nifty / SGX    → 25%  (most direct predictor)
      US markets          → 20%  (S&P + NASDAQ combined)
      Asian markets       → 15%  (Nikkei + Hang Seng)
      USD/INR             → 15%  (rupee sensitivity)
      Crude Oil           → 10%  (India = net importer)
      India VIX           → 10%  (local fear gauge)
      Gold / DXY          →  5%  (risk-off proxy)
    """

    GLOBAL_INDICES = [
        # symbol, name, region, weight
        ("^NSEI",    "NIFTY 50",       "INDIA",  0.00),  # Reference only
        ("NIFTY_GN", "Gift Nifty",     "INDIA",  0.25),  # Synthetic/NSE futures proxy
        ("^GSPC",    "S&P 500",        "US",     0.12),
        ("^IXIC",    "NASDAQ",         "US",     0.08),
        ("^DJI",     "Dow Jones",      "US",     0.04),
        ("^N225",    "Nikkei 225",     "ASIA",   0.08),
        ("^HSI",     "Hang Seng",      "ASIA",   0.07),
        ("^GDAXI",   "DAX",            "EUROPE", 0.06),
        ("^FTSE",    "FTSE 100",       "EUROPE", 0.04),
    ]

    MACRO_SYMBOLS = {
        "usdinr":      "USDINR=X",
        "dxy":         "DX-Y.NYB",
        "crude_wti":   "CL=F",
        "crude_brent": "BZ=F",
        "gold":        "GC=F",
        "us_vix":      "^VIX",
        "india_vix":   "^INDIAVIX",
        "us_10y":      "^TNX",
    }

    def __init__(self, cache_ttl_seconds: int = 180):
        self._cache: dict[str, tuple[float, datetime]] = {}
        self._cache_ttl = cache_ttl_seconds

    def fetch_price(self, symbol: str) -> tuple[float, float]:
        """
        Fetch latest price and 1-day % change for a symbol via yfinance.
        Returns (price, change_pct). Falls back to (0.0, 0.0) on failure.
        """
        # Check cache
        if symbol in self._cache:
            val, ts = self._cache[symbol]
            if datetime.now(timezone.utc) - ts < timedelta(seconds=self._cache_ttl):
                return val

        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist   = ticker.history(period="2d", interval="1d")
            if hist.empty or len(hist) < 2:
                return 0.0, 0.0
            price_now  = float(hist["Close"].iloc[-1])
            price_prev = float(hist["Close"].iloc[-2])
            chg_pct    = (price_now - price_prev) / price_prev * 100 if price_prev else 0.0
            result     = (price_now, round(chg_pct, 3))
            self._cache[symbol] = (result, datetime.now(timezone.utc))
            return result
        except Exception as e:
            logger.warning(f"fetch_price failed [{symbol}]: {e}")
            return 0.0, 0.0

    def fetch_all(self) -> MacroSnapshot:
        """
        Fetch all macro data and return a MacroSnapshot.
        Gracefully handles failures with neutral defaults.
        """
        logger.info("MacroEngine: fetching all global signals...")

        # ── Global Indices ──────────────────────────────────────────────────
        indices: list[GlobalIndexSnapshot] = []
        total_weight = 0.0
        weighted_bias = 0.0

        for yf_sym, name, region, weight in self.GLOBAL_INDICES:
            if yf_sym == "NIFTY_GN":
                # Gift Nifty proxy: use NIFTY futures if available
                price, chg = self.fetch_price("NIFTYFUT.NS")
                if price == 0.0:
                    price, chg = self.fetch_price("^NSEI")
            else:
                price, chg = self.fetch_price(yf_sym)

            signal = self._chg_to_signal(chg)
            snap   = GlobalIndexSnapshot(
                symbol=yf_sym, name=name, price=price,
                change_pct=round(chg, 3), region=region,
                weight=weight, signal=signal,
            )
            indices.append(snap)

            if weight > 0 and price > 0:
                bias_score  = self._signal_to_score(signal, chg)
                weighted_bias += weight * bias_score
                total_weight  += weight

        global_bias = round(weighted_bias / total_weight, 1) if total_weight > 0 else 50.0

        # ── Currencies ──────────────────────────────────────────────────────
        usdinr, usdinr_chg = self.fetch_price("USDINR=X")
        dxy,    dxy_chg    = self.fetch_price("DX-Y.NYB")

        # ── Commodities ─────────────────────────────────────────────────────
        crude, crude_chg   = self.fetch_price("CL=F")
        gold,  gold_chg    = self.fetch_price("GC=F")

        # ── Volatility ──────────────────────────────────────────────────────
        india_vix, _ = self.fetch_price("^INDIAVIX")
        us_vix,    _ = self.fetch_price("^VIX")

        # ── US Rates ────────────────────────────────────────────────────────
        us_10y, us_10y_chg = self.fetch_price("^TNX")

        # ── FII/DII ─────────────────────────────────────────────────────────
        fii_net, dii_net = self._get_fii_dii()

        # ── Macro Risk Score ─────────────────────────────────────────────────
        macro_risk = self._compute_macro_risk(
            usdinr_chg=usdinr_chg, crude_chg=crude_chg,
            india_vix=india_vix, dxy_chg=dxy_chg,
            us_10y=us_10y, fii_net=fii_net,
        )

        # ── Combined Score ───────────────────────────────────────────────────
        # Global bias (60%) + Macro risk inverse (40%)
        combined = round(0.60 * global_bias + 0.40 * (100 - macro_risk), 1)

        narrative = self._build_narrative(
            global_bias, macro_risk, combined,
            usdinr_chg, crude_chg, india_vix, fii_net,
        )

        logger.info(f"MacroEngine: global_bias={global_bias}, macro_risk={macro_risk}, combined={combined}")

        return MacroSnapshot(
            indices        = indices,
            usdinr         = round(usdinr, 4),
            usdinr_chg_pct = round(usdinr_chg, 3),
            dxy            = round(dxy, 3),
            dxy_chg_pct    = round(dxy_chg, 3),
            crude_wti      = round(crude, 2),
            crude_chg_pct  = round(crude_chg, 3),
            gold           = round(gold, 2),
            gold_chg_pct   = round(gold_chg, 3),
            india_vix      = round(india_vix, 2),
            us_vix         = round(us_vix, 2),
            us_10y_yield   = round(us_10y, 3),
            us_10y_chg     = round(us_10y_chg, 3),
            fii_net_crore  = round(fii_net, 2),
            dii_net_crore  = round(dii_net, 2),
            global_bias    = global_bias,
            macro_risk     = macro_risk,
            combined_score = combined,
            narrative      = narrative,
        )

    # ─── Signal Scoring ───────────────────────────────────────────────────────

    @staticmethod
    def _chg_to_signal(chg_pct: float) -> str:
        if chg_pct >= 0.5:    return "BULLISH"
        if chg_pct >= 0.1:    return "SLIGHTLY_BULLISH"
        if chg_pct <= -0.5:   return "BEARISH"
        if chg_pct <= -0.1:   return "SLIGHTLY_BEARISH"
        return "NEUTRAL"

    @staticmethod
    def _signal_to_score(signal: str, chg_pct: float) -> float:
        """Convert index signal to 0–100 bullish score."""
        if signal == "BULLISH":          return min(80.0, 60.0 + chg_pct * 5)
        if signal == "SLIGHTLY_BULLISH": return 58.0
        if signal == "NEUTRAL":          return 50.0
        if signal == "SLIGHTLY_BEARISH": return 42.0
        return max(20.0, 40.0 + chg_pct * 5)   # BEARISH

    def _compute_macro_risk(
        self,
        usdinr_chg: float, crude_chg: float,
        india_vix: float, dxy_chg: float,
        us_10y: float, fii_net: float,
    ) -> float:
        """
        Compute macro risk score (0 = no risk, 100 = extreme risk).
        Higher score = more bearish macro environment for NIFTY.
        """
        risk = 50.0   # Neutral baseline

        # USD/INR: rising rupee weakness = bearish (FII sell INR)
        if usdinr_chg > 0.3:    risk += 8.0
        elif usdinr_chg > 0.1:  risk += 3.0
        elif usdinr_chg < -0.3: risk -= 6.0

        # Crude: rising crude = bearish for India (import cost)
        if crude_chg > 2.0:    risk += 8.0
        elif crude_chg > 0.5:  risk += 3.0
        elif crude_chg < -2.0: risk -= 6.0

        # India VIX: elevated VIX = bearish
        if india_vix > 20:     risk += 10.0
        elif india_vix > 15:   risk += 4.0
        elif india_vix < 12:   risk -= 5.0

        # DXY: rising dollar = EM outflows = bearish
        if dxy_chg > 0.5:     risk += 6.0
        elif dxy_chg < -0.5:  risk -= 4.0

        # US 10Y: very high yields = risk-off
        if us_10y > 4.8:      risk += 6.0
        elif us_10y > 4.5:    risk += 2.0
        elif us_10y < 4.0:    risk -= 3.0

        # FII flow: buying = bullish = lower risk
        if fii_net > 1000:    risk -= 8.0
        elif fii_net > 0:     risk -= 3.0
        elif fii_net < -1000: risk += 8.0
        elif fii_net < 0:     risk += 3.0

        return round(max(0.0, min(100.0, risk)), 1)

    @staticmethod
    def _build_narrative(
        global_bias: float, macro_risk: float, combined: float,
        usdinr_chg: float, crude_chg: float,
        india_vix: float, fii_net: float,
    ) -> str:
        parts = [f"Macro Signal: {combined:.0f}/100"]
        parts.append(f"Global Bias={global_bias:.0f} | Macro Risk={macro_risk:.0f}")

        if usdinr_chg > 0.2:
            parts.append(f"INR weakening ({usdinr_chg:+.2f}%) → bearish")
        elif usdinr_chg < -0.2:
            parts.append(f"INR strengthening ({usdinr_chg:+.2f}%) → bullish")

        if crude_chg > 1.0:
            parts.append(f"Crude +{crude_chg:.1f}% → import cost pressure")
        elif crude_chg < -1.0:
            parts.append(f"Crude {crude_chg:.1f}% → cost relief")

        if india_vix > 18:
            parts.append(f"India VIX={india_vix:.1f} → elevated fear")
        elif india_vix < 12:
            parts.append(f"India VIX={india_vix:.1f} → complacency")

        if fii_net > 0:
            parts.append(f"FII net buy ₹{fii_net:.0f} Cr → supportive")
        elif fii_net < 0:
            parts.append(f"FII net sell ₹{abs(fii_net):.0f} Cr → pressure")

        return "; ".join(parts)

    def _get_fii_dii(self) -> tuple[float, float]:
        """Get latest FII/DII net flow from the Phase 2 tracker."""
        try:
            from modules.market_data.fii_tracker import fii_dii_tracker
            summary = fii_dii_tracker.get_latest_summary()
            if summary:
                return (
                    float(summary.get("fii_net_crore", 0.0)),
                    float(summary.get("dii_net_crore", 0.0)),
                )
        except Exception:
            pass
        # Return neutral defaults when tracker unavailable
        return 0.0, 0.0

    def synthetic_snapshot(self, scenario: str = "neutral") -> MacroSnapshot:
        """
        Generate a synthetic MacroSnapshot for testing and demos.

        Args:
            scenario: "bullish" | "bearish" | "neutral"
        """
        scenarios = {
            "bullish": dict(
                usdinr=83.20, usdinr_chg=-0.15,
                crude=78.0,   crude_chg=-1.2,
                india_vix=12.5, us_vix=14.0,
                us_10y=4.2, us_10y_chg=-2.0,
                fii_net=1500.0, dii_net=300.0,
                global_bias=68.0, macro_risk=30.0,
            ),
            "bearish": dict(
                usdinr=84.50, usdinr_chg=0.40,
                crude=92.0,   crude_chg=2.5,
                india_vix=22.0, us_vix=22.0,
                us_10y=5.0, us_10y_chg=5.0,
                fii_net=-2000.0, dii_net=800.0,
                global_bias=32.0, macro_risk=72.0,
            ),
            "neutral": dict(
                usdinr=83.80, usdinr_chg=0.05,
                crude=82.0,   crude_chg=0.3,
                india_vix=15.0, us_vix=17.0,
                us_10y=4.5, us_10y_chg=0.0,
                fii_net=200.0, dii_net=100.0,
                global_bias=52.0, macro_risk=48.0,
            ),
        }

        s = scenarios.get(scenario, scenarios["neutral"])
        combined = round(0.60 * s["global_bias"] + 0.40 * (100 - s["macro_risk"]), 1)

        # Synthetic indices
        idx_data = {
            "bullish": [(2, 0.8), (1.5, 0.9), (-0.3, 0.2)],
            "bearish": [(-1.2, -0.6), (-0.9, -0.5), (0.2, 0.1)],
            "neutral": [(0.1, 0.2), (-0.1, 0.1), (0.0, 0.0)],
        }.get(scenario, [(0.0, 0.0), (0.0, 0.0), (0.0, 0.0)])

        indices = [
            GlobalIndexSnapshot("^NSEI", "NIFTY 50", 24350.0, 0.3, "INDIA", 0.0, "SLIGHTLY_BULLISH"),
            GlobalIndexSnapshot("^GSPC", "S&P 500", 5400.0, idx_data[0][0], "US", 0.12, self._chg_to_signal(idx_data[0][0])),
            GlobalIndexSnapshot("^N225", "Nikkei 225", 38000.0, idx_data[1][0], "ASIA", 0.08, self._chg_to_signal(idx_data[1][0])),
            GlobalIndexSnapshot("^GDAXI", "DAX", 18000.0, idx_data[2][0], "EUROPE", 0.06, self._chg_to_signal(idx_data[2][0])),
        ]

        narrative = self._build_narrative(
            s["global_bias"], s["macro_risk"], combined,
            s["usdinr_chg"], s["crude_chg"],
            s["india_vix"], s["fii_net"],
        )

        return MacroSnapshot(
            indices=indices,
            usdinr=s["usdinr"], usdinr_chg_pct=s["usdinr_chg"],
            dxy=103.5, dxy_chg_pct=-0.1,
            crude_wti=s["crude"], crude_chg_pct=s["crude_chg"],
            gold=2350.0, gold_chg_pct=0.2,
            india_vix=s["india_vix"], us_vix=s["us_vix"],
            us_10y_yield=s["us_10y"], us_10y_chg=s["us_10y_chg"],
            fii_net_crore=s["fii_net"], dii_net_crore=s["dii_net"],
            global_bias=s["global_bias"], macro_risk=s["macro_risk"],
            combined_score=combined, narrative=narrative,
        )


# ── Singleton ─────────────────────────────────────────────────────────────────
macro_engine = MacroEngine()
