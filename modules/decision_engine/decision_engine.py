"""
NEXUS AI — Master Decision Engine (Phase 7)

The central intelligence layer that aggregates signals from all modules
into a single, explainable trading recommendation for NIFTY 50 options.

=============================================================================
SIGNAL WEIGHTS (total = 100%)
=============================================================================
  Option Chain Intelligence  → 30%  (PCR, OI, Max Pain, GEX, IV Skew)
  Technical Analysis         → 20%  (RSI, MACD, EMA, Supertrend, PA, VWAP)
  Macro Intelligence         → 15%  (Global indices, FII, VIX, USD/INR, Crude)
  Sentiment / NLP            → 12%  (News + Fear & Greed + Breadth)
  Greeks & IV Analysis       → 14%  (Delta, Gamma, Theta, IV percentile)
  ML Prediction              →  9%  (LSTM/TFT model, if available)

=============================================================================
OUTPUT
=============================================================================
  Recommendation:  BUY_CALL | BUY_PUT | AVOID | WAIT
  Confidence:      0–100%
  Strike:          Nearest ATM / OTM strike
  Expiry:          Next Tuesday (NIFTY weekly expiry)
  Entry:           Suggested entry price range
  Target:          1R, 2R, 3R targets
  Stop Loss:       Max loss level
  Risk/Reward:     Computed R:R ratio
  Explainability:  Per-factor scores + weights for dashboard
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class Recommendation(str, Enum):
    BUY_CALL = "BUY_CALL"
    BUY_PUT  = "BUY_PUT"
    AVOID    = "AVOID"
    WAIT     = "WAIT"


class ConfidenceLevel(str, Enum):
    VERY_HIGH = "VERY_HIGH"   # 85–100%
    HIGH      = "HIGH"        # 70–84%
    MODERATE  = "MODERATE"    # 55–69%
    LOW       = "LOW"         # 40–54%
    VERY_LOW  = "VERY_LOW"    # 0–39%


@dataclass
class FactorContribution:
    """Detailed contribution of each signal factor to the final score."""
    name:          str
    weight:        float    # Declared weight (0–1)
    raw_score:     float    # Module's 0–100 bullish score
    weighted_score: float   # raw_score × weight
    direction:     str      # BULLISH | BEARISH | NEUTRAL
    available:     bool     # Was real data available?
    evidence:      list[str]  # Key evidence points for explainability


@dataclass
class OptionRecommendation:
    """Specific option trade recommendation."""
    action:         str     # BUY_CALL | BUY_PUT | AVOID | WAIT
    strike:         float   # Suggested strike price
    expiry:         str     # "YYYY-MM-DD" (next Tuesday)
    option_type:    str     # "CE" | "PE"
    entry_low:      float   # Entry range lower bound
    entry_high:     float   # Entry range upper bound
    target_1r:      float   # 1:1 R:R target
    target_2r:      float   # 1:2 R:R target
    stop_loss:      float   # Max acceptable loss price
    risk_reward:    float   # R:R ratio
    lot_size:       int     # NIFTY lot size (75 currently)
    max_lots:       int     # Suggested max lots for 1% capital risk
    premium_est:    float   # Estimated option premium


@dataclass
class DecisionEngineOutput:
    """
    Complete output of the NEXUS Decision Engine.
    This is the top-level response sent to the frontend dashboard.
    """
    # Core signal
    recommendation:   Recommendation
    confidence:       float           # 0–100
    confidence_level: ConfidenceLevel
    bullish_score:    float           # 0–100 (50 = neutral)
    direction:        str             # BULLISH | BEARISH | NEUTRAL

    # Factor breakdown (for Explainability Dashboard)
    factors:          list[FactorContribution]
    factor_weights:   dict            # name → weight (for chart)
    factor_scores:    dict            # name → weighted_score (for chart)

    # Option trade recommendation
    trade:            Optional[OptionRecommendation]

    # Regime context
    macro_regime:     str
    size_multiplier:  float           # From macro regime classifier

    # Narrative
    narrative:        str
    reasoning:        list[str]       # Bullet points for UI

    # Metadata
    spot_price:       float
    timestamp:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    data_freshness:   str = "LIVE"    # LIVE | CACHED | SYNTHETIC


# ─── Signal Weight Registry ────────────────────────────────────────────────────

SIGNAL_WEIGHTS = {
    "option_chain":  0.30,
    "technical":     0.20,
    "macro":         0.15,
    "sentiment":     0.12,
    "greeks":        0.14,
    "ml_prediction": 0.09,
}


# ─── Option Helpers ────────────────────────────────────────────────────────────

NIFTY_LOT_SIZE = 75


def next_tuesday(from_dt: Optional[datetime] = None) -> str:
    """Return the date of the next NIFTY weekly expiry (Tuesday)."""
    dt = from_dt or datetime.now(timezone.utc)
    # 0=Mon, 1=Tue, …, 6=Sun
    days_until = (1 - dt.weekday()) % 7
    if days_until == 0:
        days_until = 7   # If today is Tuesday, next Tuesday
    expiry = dt + timedelta(days=days_until)
    return expiry.strftime("%Y-%m-%d")


def nearest_strike(spot: float, interval: float = 50.0) -> float:
    """Round spot to nearest NIFTY strike interval (50 points)."""
    return round(round(spot / interval) * interval, 0)


def otm_strike(spot: float, direction: str, interval: float = 50.0, steps: int = 1) -> float:
    """Return OTM strike in the direction of the trade."""
    atm = nearest_strike(spot, interval)
    if direction == "CE":   # OTM call = above spot
        return atm + interval * steps
    else:                   # OTM put = below spot
        return atm - interval * steps


class DecisionEngine:
    """
    NEXUS AI Master Decision Engine.

    Combines all analysis modules into a single trading recommendation.
    Each module provides a 0–100 bullish score; the engine applies
    declared weights and thresholds to produce the final call.
    """

    # ─── Thresholds ─────────────────────────────────────────────────────────
    BUY_CALL_THRESHOLD  = 65.0   # Score >= 65 → BUY CALL
    BUY_PUT_THRESHOLD   = 35.0   # Score <= 35 → BUY PUT
    AVOID_CONFIDENCE    = 45.0   # Confidence < 45 → AVOID
    MIN_SCORE_TO_TRADE  = 3      # At least 3 factors must agree

    def compute(
        self,
        spot: float,

        # Module scores (0–100 bullish). Pass None if module unavailable.
        option_chain_score:  Optional[float] = None,
        option_chain_evidence: Optional[list[str]] = None,

        technical_score:     Optional[float] = None,
        technical_evidence:  Optional[list[str]] = None,

        macro_score:         Optional[float] = None,
        macro_evidence:      Optional[list[str]] = None,
        macro_regime:        str = "SIDEWAYS",
        size_multiplier:     float = 0.80,

        sentiment_score:     Optional[float] = None,
        sentiment_evidence:  Optional[list[str]] = None,

        greeks_score:        Optional[float] = None,
        greeks_evidence:     Optional[list[str]] = None,

        ml_score:            Optional[float] = None,
        ml_evidence:         Optional[list[str]] = None,

        data_freshness:      str = "LIVE",
    ) -> DecisionEngineOutput:
        """
        Run the decision engine with all available scores.

        Missing scores default to 50.0 (neutral) with available=False.
        """
        # ── Build factor contributions ────────────────────────────────────
        raw_factors = [
            ("option_chain",  option_chain_score,  option_chain_evidence  or []),
            ("technical",     technical_score,     technical_evidence     or []),
            ("macro",         macro_score,         macro_evidence         or []),
            ("sentiment",     sentiment_score,     sentiment_evidence     or []),
            ("greeks",        greeks_score,        greeks_evidence        or []),
            ("ml_prediction", ml_score,            ml_evidence            or []),
        ]

        factors: list[FactorContribution] = []
        total_weight  = 0.0
        weighted_sum  = 0.0

        for name, score, evidence in raw_factors:
            weight    = SIGNAL_WEIGHTS[name]
            available = score is not None
            score     = score if score is not None else 50.0   # Neutral default
            score     = max(0.0, min(100.0, score))

            w_score   = weight * score
            direction = (
                "BULLISH" if score >= 60 else
                "BEARISH" if score < 40  else
                "NEUTRAL"
            )

            factors.append(FactorContribution(
                name=name, weight=weight, raw_score=round(score, 1),
                weighted_score=round(w_score, 2),
                direction=direction, available=available, evidence=evidence,
            ))
            weighted_sum  += w_score
            total_weight  += weight

        # ── Composite bullish score ──────────────────────────────────────
        bullish_score = round(weighted_sum / total_weight, 1) if total_weight > 0 else 50.0
        bullish_score = max(0.0, min(100.0, bullish_score))

        # ── Agreement count ──────────────────────────────────────────────
        bullish_factors = sum(1 for f in factors if f.direction == "BULLISH")
        bearish_factors = sum(1 for f in factors if f.direction == "BEARISH")

        # ── Confidence calculation ───────────────────────────────────────
        # Base: how far from neutral (50)
        signal_strength = abs(bullish_score - 50.0) * 2.0   # 0–100

        # Agreement bonus: more factors agreeing = higher confidence
        agree_count  = max(bullish_factors, bearish_factors)
        agree_bonus  = agree_count * 5.0   # Up to 30 points

        # Availability penalty: missing data reduces confidence
        missing      = sum(1 for f in factors if not f.available)
        avail_penalty = missing * 6.0

        confidence = round(
            min(100.0, max(0.0, signal_strength + agree_bonus - avail_penalty)),
        1)

        # ── Recommendation ────────────────────────────────────────────────
        recommendation = self._recommend(bullish_score, confidence, bullish_factors, bearish_factors)
        direction      = self._score_to_direction(bullish_score)
        conf_level     = self._confidence_level(confidence)

        # ── Option trade details ──────────────────────────────────────────
        trade = None
        if recommendation in (Recommendation.BUY_CALL, Recommendation.BUY_PUT):
            trade = self._build_trade(recommendation, spot, bullish_score, size_multiplier)

        # ── Narrative ─────────────────────────────────────────────────────
        narrative, reasoning = self._build_narrative(
            recommendation, bullish_score, confidence,
            bullish_factors, bearish_factors, factors, macro_regime,
        )

        # ── Factor dicts for charts ───────────────────────────────────────
        factor_weights = {f.name: f.weight for f in factors}
        factor_scores  = {f.name: f.raw_score for f in factors}

        return DecisionEngineOutput(
            recommendation   = recommendation,
            confidence       = confidence,
            confidence_level = conf_level,
            bullish_score    = bullish_score,
            direction        = direction,
            factors          = factors,
            factor_weights   = factor_weights,
            factor_scores    = factor_scores,
            trade            = trade,
            macro_regime     = macro_regime,
            size_multiplier  = size_multiplier,
            narrative        = narrative,
            reasoning        = reasoning,
            spot_price       = spot,
            data_freshness   = data_freshness,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _recommend(
        self,
        score: float, confidence: float,
        bull_count: int, bear_count: int,
    ) -> Recommendation:
        """Apply threshold logic to produce final recommendation."""
        # Low confidence → AVOID
        if confidence < self.AVOID_CONFIDENCE:
            return Recommendation.AVOID

        # Requires majority factor agreement
        if score >= self.BUY_CALL_THRESHOLD and bull_count >= self.MIN_SCORE_TO_TRADE:
            return Recommendation.BUY_CALL
        if score <= self.BUY_PUT_THRESHOLD and bear_count >= self.MIN_SCORE_TO_TRADE:
            return Recommendation.BUY_PUT

        # Borderline: wait for clearer signal
        if 35 < score < 65:
            return Recommendation.WAIT

        return Recommendation.AVOID

    @staticmethod
    def _score_to_direction(score: float) -> str:
        if score >= 65:  return "BULLISH"
        if score <= 35:  return "BEARISH"
        return "NEUTRAL"

    @staticmethod
    def _confidence_level(confidence: float) -> ConfidenceLevel:
        if confidence >= 85:  return ConfidenceLevel.VERY_HIGH
        if confidence >= 70:  return ConfidenceLevel.HIGH
        if confidence >= 55:  return ConfidenceLevel.MODERATE
        if confidence >= 40:  return ConfidenceLevel.LOW
        return ConfidenceLevel.VERY_LOW

    def _build_trade(
        self,
        rec: Recommendation,
        spot: float,
        score: float,
        size_mult: float,
    ) -> OptionRecommendation:
        """Construct a concrete option trade suggestion."""
        is_call      = rec == Recommendation.BUY_CALL
        opt_type     = "CE" if is_call else "PE"
        atm          = nearest_strike(spot)
        strike       = otm_strike(spot, opt_type, steps=1)
        expiry       = next_tuesday()

        # Premium estimate: rough approximation (ATM ≈ 1% of spot for weekly)
        premium_est  = round(spot * 0.008 * (1 + abs(score - 50) / 100), 0)

        # Stop loss: 50% of premium
        sl  = round(premium_est * 0.50, 0)
        # Targets
        t1  = round(premium_est * 1.5, 0)   # 1R
        t2  = round(premium_est * 2.0, 0)   # 2R
        rr  = round((t1 - premium_est) / max(1, premium_est - sl), 2)

        # Position sizing: 1% capital risk → premium × lot × n_lots
        # Assume 10L capital; 1% = 10000 risk per trade
        risk_per_lot = (premium_est - sl) * NIFTY_LOT_SIZE
        raw_lots     = max(1, int(10000 / max(1, risk_per_lot)))
        max_lots     = max(1, int(raw_lots * size_mult))   # Always at least 1 lot

        return OptionRecommendation(
            action       = rec.value,
            strike       = strike,
            expiry       = expiry,
            option_type  = opt_type,
            entry_low    = premium_est * 0.95,
            entry_high   = premium_est * 1.05,
            target_1r    = t1,
            target_2r    = t2,
            stop_loss    = sl,
            risk_reward  = rr,
            lot_size     = NIFTY_LOT_SIZE,
            max_lots     = max_lots,
            premium_est  = premium_est,
        )

    def _build_narrative(
        self,
        rec: Recommendation,
        score: float,
        confidence: float,
        bull: int,
        bear: int,
        factors: list[FactorContribution],
        regime: str,
    ) -> tuple[str, list[str]]:
        """Build human-readable narrative and bullet-point reasoning."""
        action_str = {
            Recommendation.BUY_CALL: "🟢 BUY CALL",
            Recommendation.BUY_PUT:  "🔴 BUY PUT",
            Recommendation.AVOID:    "⚪ AVOID",
            Recommendation.WAIT:     "🟡 WAIT",
        }[rec]

        narrative = (
            f"{action_str} | Confidence: {confidence:.0f}% | "
            f"Score: {score:.0f}/100 | Regime: {regime}"
        )

        reasoning = [
            f"Composite bullish score: {score:.0f}/100 "
            f"({'above' if score > 50 else 'below'} neutral)",
            f"{bull} of 6 factors are BULLISH, {bear} are BEARISH",
            f"Macro regime: {regime} (size multiplier: {self._regime_label(regime)})",
        ]

        # Add top factor evidence
        sorted_f = sorted(factors, key=lambda f: abs(f.raw_score - 50), reverse=True)
        for f in sorted_f[:3]:
            icon = "🟢" if f.direction == "BULLISH" else "🔴" if f.direction == "BEARISH" else "⚪"
            avail = "" if f.available else " [synthetic]"
            reasoning.append(
                f"{icon} {f.name.replace('_',' ').title()}: {f.raw_score:.0f}/100 "
                f"({f.direction}){avail}"
            )

        if rec == Recommendation.AVOID:
            reasoning.append(f"⚠ Confidence too low ({confidence:.0f}%) — stay flat")
        elif rec == Recommendation.WAIT:
            reasoning.append("🕒 Signal not strong enough — wait for confirmation")

        return narrative, reasoning

    @staticmethod
    def _regime_label(regime: str) -> str:
        labels = {
            "RISK_ON":        "100%",
            "RATE_FALLING":   "90%",
            "SIDEWAYS":       "80%",
            "RATE_RISING":    "75%",
            "STAGFLATIONARY": "60%",
            "RISK_OFF":       "50%",
        }
        return labels.get(regime, "80%")


# ── Singleton ──────────────────────────────────────────────────────────────────
decision_engine = DecisionEngine()
