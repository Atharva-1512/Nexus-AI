"""
NEXUS AI — Macro Regime Classifier (Phase 5)

Classifies the current macro environment into one of 6 regimes:
  RISK_ON       — Globally bullish, FII buying, VIX low, rupee stable
  RISK_OFF      — VIX elevated, FII selling, dollar rising
  STAGFLATIONARY — Crude high, growth slowing
  RATE_RISING   — US yields climbing, EM outflows
  RATE_FALLING  — US yields declining, EM inflows
  SIDEWAYS      — No dominant macro theme

Regime determines position sizing and strategy bias:
  RISK_ON:      Allow full position, prefer momentum
  RISK_OFF:     Reduce size 50%, prefer hedged positions
  STAGFLATIONARY: Avoid CE, prefer put spreads
  RATE_RISING:  Cautious on rate-sensitive sectors
  SIDEWAYS:     Range strategies, avoid breakout trades
"""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Optional

from .macro_engine import MacroSnapshot


class MacroRegime(str, Enum):
    RISK_ON          = "RISK_ON"
    RISK_OFF         = "RISK_OFF"
    STAGFLATIONARY   = "STAGFLATIONARY"
    RATE_RISING      = "RATE_RISING"
    RATE_FALLING     = "RATE_FALLING"
    SIDEWAYS         = "SIDEWAYS"


REGIME_DESCRIPTIONS = {
    MacroRegime.RISK_ON:        "Risk-On: Global markets up, VIX low, FII buying → max allocation",
    MacroRegime.RISK_OFF:       "Risk-Off: VIX elevated, FII selling → reduce size 50%",
    MacroRegime.STAGFLATIONARY: "Stagflationary: High crude + slow growth → avoid calls, prefer put spreads",
    MacroRegime.RATE_RISING:    "Rate Rising: US yields climbing → EM outflows, be cautious",
    MacroRegime.RATE_FALLING:   "Rate Falling: US yields declining → EM inflows supportive",
    MacroRegime.SIDEWAYS:       "Sideways: No dominant macro theme → range-bound strategies",
}

REGIME_SIZE_MULTIPLIER = {
    MacroRegime.RISK_ON:        1.00,
    MacroRegime.RISK_OFF:       0.50,
    MacroRegime.STAGFLATIONARY: 0.60,
    MacroRegime.RATE_RISING:    0.75,
    MacroRegime.RATE_FALLING:   0.90,
    MacroRegime.SIDEWAYS:       0.80,
}


@dataclass
class RegimeAnalysis:
    regime:             MacroRegime
    confidence:         float     # 0–100
    size_multiplier:    float     # How much to scale position size
    description:        str
    triggers:           list[str] # What triggered this regime classification
    bias:               str       # "BULLISH" | "BEARISH" | "NEUTRAL"


class MacroRegimeClassifier:
    """
    Rule-based macro regime classifier.
    Uses the MacroSnapshot to determine the current macro environment.
    """

    def classify(self, snap: MacroSnapshot) -> RegimeAnalysis:
        """
        Classify macro regime from snapshot.
        Uses a priority-based rule system (RISK_OFF is highest priority).
        """
        triggers:  list[str] = []
        scores:    dict[MacroRegime, float] = {r: 0.0 for r in MacroRegime}

        # ── RISK_OFF triggers ────────────────────────────────────────────────
        if snap.india_vix > 20:
            scores[MacroRegime.RISK_OFF] += 30
            triggers.append(f"India VIX={snap.india_vix:.1f} > 20")
        if snap.us_vix > 20:
            scores[MacroRegime.RISK_OFF] += 15
            triggers.append(f"US VIX={snap.us_vix:.1f} > 20")
        if snap.fii_net_crore < -1500:
            scores[MacroRegime.RISK_OFF] += 25
            triggers.append(f"FII heavy sell ₹{snap.fii_net_crore:.0f} Cr")
        if snap.usdinr_chg_pct > 0.4:
            scores[MacroRegime.RISK_OFF] += 15
            triggers.append(f"INR weakening {snap.usdinr_chg_pct:+.2f}%")
        if snap.global_bias < 35:
            scores[MacroRegime.RISK_OFF] += 20
            triggers.append(f"Global markets bearish (bias={snap.global_bias:.0f})")

        # ── STAGFLATIONARY triggers ──────────────────────────────────────────
        if snap.crude_chg_pct > 2.0:
            scores[MacroRegime.STAGFLATIONARY] += 30
            triggers.append(f"Crude surging {snap.crude_chg_pct:+.1f}%")
        if snap.crude_wti > 90 and snap.global_bias < 55:
            scores[MacroRegime.STAGFLATIONARY] += 20
            triggers.append(f"Crude={snap.crude_wti:.0f}+ with weak global markets")
        if snap.usdinr_chg_pct > 0.3 and snap.crude_chg_pct > 1.0:
            scores[MacroRegime.STAGFLATIONARY] += 15
            triggers.append("Double pressure: weak rupee + rising crude")

        # ── RATE_RISING triggers ─────────────────────────────────────────────
        if snap.us_10y_yield > 4.8:
            scores[MacroRegime.RATE_RISING] += 25
            triggers.append(f"US 10Y yield={snap.us_10y_yield:.2f}% > 4.8%")
        if snap.us_10y_chg > 3.0:
            scores[MacroRegime.RATE_RISING] += 20
            triggers.append(f"US yields rising {snap.us_10y_chg:+.1f} bps")
        if snap.dxy_chg_pct > 0.5:
            scores[MacroRegime.RATE_RISING] += 15
            triggers.append(f"Dollar strengthening {snap.dxy_chg_pct:+.2f}%")

        # ── RATE_FALLING triggers ────────────────────────────────────────────
        if snap.us_10y_yield < 4.0:
            scores[MacroRegime.RATE_FALLING] += 25
            triggers.append(f"US 10Y yield={snap.us_10y_yield:.2f}% < 4.0%")
        if snap.us_10y_chg < -3.0:
            scores[MacroRegime.RATE_FALLING] += 20
            triggers.append(f"US yields falling {snap.us_10y_chg:+.1f} bps")
        if snap.dxy_chg_pct < -0.5:
            scores[MacroRegime.RATE_FALLING] += 10
            triggers.append(f"Dollar weakening {snap.dxy_chg_pct:+.2f}%")

        # ── RISK_ON triggers ─────────────────────────────────────────────────
        if snap.india_vix < 12:
            scores[MacroRegime.RISK_ON] += 20
            triggers.append(f"India VIX={snap.india_vix:.1f} < 12 (calm)")
        if snap.fii_net_crore > 1000:
            scores[MacroRegime.RISK_ON] += 25
            triggers.append(f"FII net buy ₹{snap.fii_net_crore:.0f} Cr")
        if snap.global_bias > 65:
            scores[MacroRegime.RISK_ON] += 20
            triggers.append(f"Global markets bullish (bias={snap.global_bias:.0f})")
        if snap.usdinr_chg_pct < -0.2:
            scores[MacroRegime.RISK_ON] += 10
            triggers.append(f"INR strengthening {snap.usdinr_chg_pct:+.2f}%")
        if snap.crude_chg_pct < -1.0:
            scores[MacroRegime.RISK_ON] += 10
            triggers.append(f"Crude falling {snap.crude_chg_pct:+.1f}%")

        # ── SIDEWAYS default ────────────────────────────────────────────────
        max_score = max(scores.values())
        if max_score < 20:
            scores[MacroRegime.SIDEWAYS] = 30
            triggers.append("No dominant macro theme detected")

        # Determine winner
        regime    = max(scores, key=scores.__getitem__)
        confidence = min(100.0, round(scores[regime], 1))

        # Bias
        if regime in (MacroRegime.RISK_ON, MacroRegime.RATE_FALLING):
            bias = "BULLISH"
        elif regime in (MacroRegime.RISK_OFF, MacroRegime.STAGFLATIONARY, MacroRegime.RATE_RISING):
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return RegimeAnalysis(
            regime           = regime,
            confidence       = confidence,
            size_multiplier  = REGIME_SIZE_MULTIPLIER[regime],
            description      = REGIME_DESCRIPTIONS[regime],
            triggers         = triggers[:5],   # Top 5 triggers
            bias             = bias,
        )
