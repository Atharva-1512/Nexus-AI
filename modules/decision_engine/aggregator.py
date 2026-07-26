"""
NEXUS AI — Signal Aggregator (Phase 7)

Wires all analysis modules into the Decision Engine.
This is the master coordinator that:
  1. Fetches data from each analysis module
  2. Converts each module's output to a 0-100 bullish score + evidence
  3. Passes everything to the DecisionEngine to compute the recommendation
"""

from __future__ import annotations

import logging
from typing import Optional

from .decision_engine import DecisionEngine, DecisionEngineOutput, decision_engine

logger = logging.getLogger(__name__)


class SignalAggregator:
    """
    Coordinates all analysis modules and feeds them into the Decision Engine.
    Falls back to synthetic/neutral data when live data is unavailable.
    """

    def __init__(self):
        self._engine = decision_engine

    async def run(
        self,
        spot: float = 24000.0,
        scenario: str = "neutral",
        use_live: bool = False,
    ) -> DecisionEngineOutput:
        """
        Run a full analysis cycle.

        Args:
            spot:     Current NIFTY spot price
            scenario: "bullish" | "bearish" | "neutral" for synthetic mode
            use_live: Attempt live data fetches (slower but real)
        """
        # ── Option Chain ───────────────────────────────────────────────────
        oc_score, oc_evidence, pcr, vix = await self._get_option_chain_score(spot, scenario)

        # ── Technical Analysis ─────────────────────────────────────────────
        tech_score, tech_evidence, sma50 = await self._get_technical_score(scenario)

        # ── Macro Intelligence ─────────────────────────────────────────────
        macro_score, macro_evidence, macro_regime, size_mult = await self._get_macro_score(scenario)

        # ── Sentiment ──────────────────────────────────────────────────────
        sent_score, sent_evidence = await self._get_sentiment_score(scenario, vix, pcr)

        # ── Greeks (from option chain PCR and IV) ──────────────────────────
        greeks_score, greeks_evidence = self._get_greeks_score(scenario, pcr, vix)

        # ── ML Prediction (Phase 8 placeholder) ───────────────────────────
        ml_score, ml_evidence = None, ["ML model not yet available (Phase 8)"]

        # ── Decision Engine ────────────────────────────────────────────────
        return self._engine.compute(
            spot               = spot,
            option_chain_score = oc_score,    option_chain_evidence = oc_evidence,
            technical_score    = tech_score,  technical_evidence    = tech_evidence,
            macro_score        = macro_score, macro_evidence        = macro_evidence,
            macro_regime       = macro_regime, size_multiplier      = size_mult,
            sentiment_score    = sent_score,  sentiment_evidence    = sent_evidence,
            greeks_score       = greeks_score, greeks_evidence      = greeks_evidence,
            ml_score           = ml_score,     ml_evidence          = ml_evidence,
        )

    # ─── Module Score Extractors ─────────────────────────────────────────────

    async def _get_option_chain_score(
        self, spot: float, scenario: str
    ) -> tuple[float, list[str], float, float]:
        """Get option chain score. Returns (score, evidence, pcr, vix)."""
        try:
            from modules.option_chain.chain_engine import chain_engine
            oc = await chain_engine.analyze(spot)
            score    = oc.bullish_score
            evidence = [
                f"PCR={oc.pcr_signal.pcr:.2f} → {oc.pcr_signal.sentiment}",
                f"Max Pain: ₹{oc.max_pain:.0f} (spot diff {oc.max_pain - spot:+.0f})",
                f"PCR signal: {oc.pcr_signal.interpretation[:60]}",
            ]
            pcr = float(oc.pcr_signal.pcr)
            vix = 15.0  # Option chain doesn't have VIX; use default
            return score, evidence, pcr, vix
        except Exception as e:
            logger.warning(f"Option chain unavailable: {e}. Using synthetic.")
            return self._synthetic_oc_score(scenario)

    async def _get_technical_score(
        self, scenario: str
    ) -> tuple[float, list[str], float]:
        """Get technical analysis score. Returns (score, evidence, sma50)."""
        try:
            from modules.technical.tech_engine import tech_engine
            from app.services.technical_service import _make_df
            df     = _make_df(100, trend="up" if scenario == "bullish" else
                                        "down" if scenario == "bearish" else "flat")
            signal = tech_engine.analyze_df(df)
            score  = signal.bullish_score
            evidence = [
                f"Direction: {signal.direction} (confidence {signal.confidence:.0f}%)",
                f"Trend: {signal.trend.direction.value} ({signal.trend.strength:.0f}%)",
                signal.narrative[:80] if signal.narrative else "Technical analysis complete",
            ]
            # Estimate SMA50 from dataframe
            sma50 = float(df["close"].rolling(50).mean().iloc[-1])
            return score, evidence, sma50
        except Exception as e:
            logger.warning(f"Technical analysis unavailable: {e}. Using synthetic.")
            return self._synthetic_tech_score(scenario)

    async def _get_macro_score(
        self, scenario: str
    ) -> tuple[float, list[str], str, float]:
        """Get macro score. Returns (score, evidence, regime, size_mult)."""
        try:
            from modules.macro.macro_engine import macro_engine
            from modules.macro.regime_classifier import MacroRegimeClassifier
            snap      = macro_engine.synthetic_snapshot(scenario)
            classifier = MacroRegimeClassifier()
            regime_obj = classifier.classify(snap)
            score     = snap.combined_score
            evidence  = [
                f"Global bias: {snap.global_bias:.0f}/100",
                f"Macro risk: {snap.macro_risk:.0f}/100",
                f"Regime: {regime_obj.regime.value} ({regime_obj.bias})",
                f"USD/INR: {snap.usdinr:.2f} ({snap.usdinr_chg_pct:+.2f}%)",
                f"Crude: ${snap.crude_wti:.0f} ({snap.crude_chg_pct:+.1f}%)",
            ]
            return score, evidence, regime_obj.regime.value, regime_obj.size_multiplier
        except Exception as e:
            logger.warning(f"Macro unavailable: {e}. Using synthetic.")
            return self._synthetic_macro_score(scenario)

    async def _get_sentiment_score(
        self, scenario: str, vix: float, pcr: float
    ) -> tuple[float, list[str]]:
        """Get sentiment score."""
        try:
            from modules.sentiment.sentiment_engine import sentiment_engine
            sig = sentiment_engine.analyze_sync(india_vix=vix, pcr=pcr, scenario=scenario)
            evidence = [
                f"News: {sig.news.direction} ({sig.news.bullish_score:.0f}/100)",
                f"Fear & Greed: {sig.social.fear_greed.label} ({sig.social.fear_greed.score:.0f})",
                f"PCR: {pcr:.2f} ({sig.social.pcr_sentiment})",
            ]
            return sig.bullish_score, evidence
        except Exception as e:
            logger.warning(f"Sentiment unavailable: {e}. Using synthetic.")
            return self._synthetic_sentiment_score(scenario)

    def _get_greeks_score(
        self, scenario: str, pcr: float, vix: float
    ) -> tuple[float, list[str]]:
        """
        Compute Greeks score from PCR and VIX (Phase 7 approximation).
        Full Greeks analysis (Phase 8) will use Black-Scholes engine.
        """
        # IV regime: high VIX → buy puts is expensive → prefer directional clarity
        if vix < 12:      iv_score = 75.0   # Low IV = cheap options = good time to buy
        elif vix < 15:    iv_score = 65.0
        elif vix < 18:    iv_score = 55.0
        elif vix < 22:    iv_score = 42.0
        else:             iv_score = 30.0   # High IV = expensive options

        # PCR influence on Greeks
        if pcr > 1.3:   pcr_greek = 60.0   # High put OI = potential bounce
        elif pcr < 0.8: pcr_greek = 40.0   # High call OI = potential cap
        else:           pcr_greek = 50.0

        score = round(0.6 * iv_score + 0.4 * pcr_greek, 1)

        if scenario == "bullish":
            score = min(100.0, score + 10)
        elif scenario == "bearish":
            score = max(0.0, score - 10)

        evidence = [
            f"India VIX={vix:.1f} → {'low' if vix < 15 else 'elevated'} option premiums",
            f"IV score: {iv_score:.0f} | PCR Greek: {pcr_greek:.0f}",
            f"Implied environment: {'CHEAP' if vix < 15 else 'EXPENSIVE'} options",
        ]
        return round(score, 1), evidence

    # ─── Synthetic Fallbacks ───────────────────────────────────────────────────

    @staticmethod
    def _synthetic_oc_score(scenario: str) -> tuple[float, list[str], float, float]:
        data = {
            "bullish": (72.0, 0.82, 12.5,
                        ["PCR=0.82 → Bullish", "Strong CE OI buildup at 24500", "Max Pain: 24200"]),
            "bearish": (28.0, 1.65, 21.0,
                        ["PCR=1.65 → Bearish", "Heavy PE OI buildup at 23500", "Max Pain: 23800"]),
            "neutral": (52.0, 1.05, 15.0,
                        ["PCR=1.05 → Neutral", "Balanced OI distribution", "Max Pain: 24000"]),
        }
        d = data.get(scenario, data["neutral"])
        return d[0], d[3], d[1], d[2]

    @staticmethod
    def _synthetic_tech_score(scenario: str) -> tuple[float, list[str], float]:
        data = {
            "bullish": (68.0, ["RSI=65 (bullish zone)", "MACD cross above signal", "EMA9 > EMA21"], 23500.0),
            "bearish": (32.0, ["RSI=38 (bearish zone)", "MACD below signal", "EMA9 < EMA21"], 24500.0),
            "neutral": (51.0, ["RSI=52 (neutral)", "MACD flat", "Price near VWAP"], 24000.0),
        }
        d = data.get(scenario, data["neutral"])
        return d[0], d[1], d[2]

    @staticmethod
    def _synthetic_macro_score(scenario: str) -> tuple[float, list[str], str, float]:
        data = {
            "bullish": (68.0, ["FII buying ₹1500Cr", "Crude -1.2%", "INR stable"], "RISK_ON",  1.00),
            "bearish": (32.0, ["FII selling ₹2000Cr", "Crude +2.5%", "INR weak"], "RISK_OFF", 0.50),
            "neutral": (52.0, ["FII flat", "Crude +0.3%", "INR flat"],             "SIDEWAYS", 0.80),
        }
        d = data.get(scenario, data["neutral"])
        return d[0], d[1], d[2], d[3]

    @staticmethod
    def _synthetic_sentiment_score(scenario: str) -> tuple[float, list[str]]:
        data = {
            "bullish": (70.0, ["News: BULLISH", "Fear & Greed: GREED (70)", "PCR=0.82 (SLIGHTLY_BEARISH)"]),
            "bearish": (30.0, ["News: BEARISH", "Fear & Greed: FEAR (28)", "PCR=1.65 (CONTRARIAN_BULLISH)"]),
            "neutral": (51.0, ["News: NEUTRAL", "Fear & Greed: NEUTRAL (50)", "PCR=1.05 (NEUTRAL)"]),
        }
        d = data.get(scenario, data["neutral"])
        return d[0], d[1]


# ── Singleton ───────────────────────────────────────────────────────────────────
aggregator = SignalAggregator()
