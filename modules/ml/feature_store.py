"""
NEXUS AI — Feature Store (Phase 8)

Builds a 100+ feature vector from all analysis modules for ML models.
STRICTLY time-indexed to avoid any look-ahead bias.

Feature Categories:
  1. Price & Returns (15 features)     — lag returns, log returns, price ratios
  2. Momentum Indicators (20 features) — RSI, MACD, Stochastic, ROC, MFI, CCI
  3. Trend Indicators (15 features)    — EMA cross, ADX, Supertrend, VWAP deviation
  4. Volatility Features (12 features) — ATR, Bollinger, historical vol, VIX
  5. Volume Features (8 features)      — OBV, volume ratio, VWAP vol
  6. Option Chain Features (12 features) — PCR, OI skew, Max Pain distance, IV
  7. Macro Features (10 features)      — USD/INR, Crude, DXY, FII, US 10Y
  8. Sentiment Features (8 features)   — News score, Fear & Greed, Breadth
  9. Calendar Features (8 features)    — Day of week, DTE, expiry effect, gap effect

Total: ~108 features
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """A single row of the feature store (one timestamp)."""
    timestamp:  datetime
    symbol:     str
    features:   dict[str, float]   # All numeric features
    target:     Optional[float]    # 0=Bearish, 1=Bullish (None for live)
    raw_close:  float              # For inverse transform

    @property
    def as_array(self) -> np.ndarray:
        """Return features as a sorted numpy array (deterministic order)."""
        return np.array([self.features[k] for k in sorted(self.features.keys())], dtype=np.float32)

    @property
    def feature_names(self) -> list[str]:
        return sorted(self.features.keys())


class FeatureStore:
    """
    Builds the full feature matrix from OHLCV + module outputs.
    All features use ONLY past data at each timestamp (no leakage).
    """

    # ─── Feature Group Builders ────────────────────────────────────────────────

    def compute_price_features(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """
        Price & Return features (15 features).
        Uses only lagged/historical data — no future values.
        """
        close = df["close"].astype(float)
        feats = {}

        # Log returns (t-1, t-2, t-3, t-5, t-10)
        for lag in [1, 2, 3, 5, 10]:
            feats[f"log_ret_{lag}"] = np.log(close / close.shift(lag)).fillna(0)

        # Cumulative returns
        feats["cum_ret_5"]  = close.pct_change(5).fillna(0)
        feats["cum_ret_10"] = close.pct_change(10).fillna(0)
        feats["cum_ret_20"] = close.pct_change(20).fillna(0)

        # High-Low range ratio
        feats["hl_ratio"]   = ((df["high"] - df["low"]) / close.clip(lower=1)).fillna(0)

        # Open-to-Close return (body)
        feats["oc_return"]  = ((close - df["open"]) / df["open"].clip(lower=1)).fillna(0)

        # Price vs 20-period SMA
        sma20 = close.rolling(20).mean()
        feats["price_vs_sma20"] = ((close - sma20) / sma20.clip(lower=1)).fillna(0)

        # Price vs 50-period SMA
        sma50 = close.rolling(50).mean()
        feats["price_vs_sma50"] = ((close - sma50) / sma50.clip(lower=1)).fillna(0)

        # 52-week high/low percentile (using available window)
        roll252 = close.rolling(252, min_periods=20)
        feats["pct_from_52w_high"] = ((close - roll252.max()) / roll252.max().clip(lower=1)).fillna(0)
        feats["pct_from_52w_low"]  = ((close - roll252.min()) / roll252.min().clip(lower=1)).fillna(0)

        return feats

    def compute_momentum_features(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """Momentum indicator features (20 features)."""
        from modules.technical.indicators import (
            rsi, macd, stochastic, cci, mfi,
        )
        close  = df["close"].astype(float)
        volume = df["volume"].astype(float).fillna(0)
        feats  = {}

        # RSI at different periods
        feats["rsi_14"]  = rsi(close, 14).fillna(50)
        feats["rsi_7"]   = rsi(close, 7).fillna(50)
        feats["rsi_21"]  = rsi(close, 21).fillna(50)

        # RSI divergence from 50 (overbought/oversold)
        feats["rsi_dist_from_50"] = (rsi(close, 14).fillna(50) - 50).abs()

        # MACD
        macd_df = macd(close)
        feats["macd_hist"]      = macd_df["histogram"].fillna(0)
        feats["macd_line"]      = macd_df["macd"].fillna(0)
        feats["macd_signal"]    = macd_df["signal"].fillna(0)
        # MACD histogram change (momentum of momentum)
        feats["macd_hist_chg"]  = macd_df["histogram"].diff().fillna(0)

        # Stochastic
        stoch = stochastic(df)
        feats["stoch_k"]  = stoch["k"].fillna(50)
        feats["stoch_d"]  = stoch["d"].fillna(50)
        feats["stoch_kd"] = (stoch["k"] - stoch["d"]).fillna(0)

        # Rate of change
        feats["roc_5"]  = close.pct_change(5).fillna(0) * 100
        feats["roc_10"] = close.pct_change(10).fillna(0) * 100
        feats["roc_20"] = close.pct_change(20).fillna(0) * 100

        # Williams %R proxy (from stochastic)
        feats["willr_14"] = (100 - feats["stoch_k"])

        # CCI
        feats["cci_20"] = cci(df).fillna(0)

        # MFI
        feats["mfi_14"] = mfi(df).fillna(50)

        # Price momentum (vs 10-period EMA)
        from modules.technical.indicators import ema as _ema
        feats["mom_ema10"] = (close - _ema(close, 10)).fillna(0)

        return feats

    def compute_trend_features(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """Trend indicator features (15 features)."""
        from modules.technical.indicators import (
            ema as _ema, sma as _sma, adx, supertrend, vwap as _vwap,
        )
        close  = df["close"].astype(float)
        feats  = {}

        # EMA crosses
        ema9   = _ema(close, 9)
        ema21  = _ema(close, 21)
        ema50  = _ema(close, 50)
        ema200 = _ema(close, 200)

        feats["ema9_vs_ema21"]  = (ema9 - ema21).fillna(0)
        feats["ema21_vs_ema50"] = (ema21 - ema50).fillna(0)
        feats["ema50_vs_ema200"]= (ema50 - ema200).fillna(0)

        # EMA cross signals (-1/0/1)
        feats["ema_cross_9_21"] = pd.Series(
            np.where(ema9 > ema21, 1.0, np.where(ema9 < ema21, -1.0, 0.0)),
            index=df.index,
        ).fillna(0)

        # ADX
        adx_df = adx(df)
        feats["adx_14"]     = adx_df["adx"].fillna(0)
        feats["adx_di_pos"] = adx_df["plus_di"].fillna(0)
        feats["adx_di_neg"] = adx_df["minus_di"].fillna(0)
        feats["adx_di_diff"]= (adx_df["plus_di"] - adx_df["minus_di"]).fillna(0)

        # Supertrend direction
        st = supertrend(df)
        # Supertrend: direction column values are 1/-1, map to 1.0/0.0/-1.0
        feats["supertrend_dir"] = st["direction"].fillna(0).astype(float)

        # VWAP deviation
        vwap_s = _vwap(df).fillna(close)
        feats["price_vs_vwap"] = ((close - vwap_s) / vwap_s.clip(lower=1)).fillna(0)

        # SMA slope (trend angle proxy)
        sma20 = _sma(close, 20)
        feats["sma20_slope"] = sma20.diff(3).fillna(0) / close.clip(lower=1)
        sma50_s = _sma(close, 50)
        feats["sma50_slope"] = sma50_s.diff(5).fillna(0) / close.clip(lower=1)

        # Higher High / Higher Low count (rolling 5 bars)
        feats["hh_hl_score"] = self._hh_hl_rolling(df, window=5)

        return feats

    def compute_volatility_features(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """Volatility features (12 features)."""
        from modules.technical.indicators import atr, bollinger_bands
        close  = df["close"].astype(float)
        feats  = {}

        # ATR (normalized by price)
        atr14 = atr(df, 14).fillna(0)
        feats["atr_14"]     = atr14
        feats["atr_pct"]    = (atr14 / close.clip(lower=1)).fillna(0)

        # ATR ratio (short vs long volatility)
        atr7  = atr(df, 7).fillna(0)
        atr21 = atr(df, 21).fillna(0)
        feats["atr_ratio"] = (atr7 / atr21.clip(lower=0.001)).fillna(1.0)

        # Bollinger Band features
        bb = bollinger_bands(close, 20)
        feats["bb_width"]  = ((bb["upper"] - bb["lower"]) / bb["middle"].clip(lower=1)).fillna(0)
        feats["bb_pct_b"]  = ((close - bb["lower"]) / (bb["upper"] - bb["lower"]).clip(lower=0.001)).fillna(0.5)
        feats["bb_squeeze"] = (feats["bb_width"] < feats["bb_width"].rolling(20).quantile(0.25)).astype(float).fillna(0)

        # Historical volatility (rolling std of log returns)
        log_ret = np.log(close / close.shift(1)).fillna(0)
        feats["hist_vol_10"] = log_ret.rolling(10).std().fillna(0) * np.sqrt(252)
        feats["hist_vol_20"] = log_ret.rolling(20).std().fillna(0) * np.sqrt(252)
        feats["hist_vol_ratio"] = (
            feats["hist_vol_10"] / feats["hist_vol_20"].clip(lower=0.001)
        ).fillna(1.0)

        # Garman-Klass volatility (uses OHLC)
        hl = np.log(df["high"] / df["low"].clip(lower=0.001))
        co = np.log(close / df["open"].clip(lower=0.001))
        feats["gk_vol"] = (
            (0.5 * hl**2 - (2*np.log(2)-1) * co**2)
            .rolling(10).mean().apply(lambda x: max(0, x)**0.5)
            .fillna(0)
        )

        # Vol regime (expanding vs contracting)
        feats["vol_expansion"] = (
            (feats["hist_vol_10"] > feats["hist_vol_20"]).astype(float)
        )

        return feats

    def compute_volume_features(self, df: pd.DataFrame) -> dict[str, pd.Series]:
        """Volume features (8 features)."""
        from modules.technical.indicators import obv as _obv
        close  = df["close"].astype(float)
        volume = df["volume"].astype(float).fillna(0)
        feats  = {}

        # OBV
        obv_s = _obv(df).fillna(0)
        feats["obv"]           = obv_s
        feats["obv_slope"]     = obv_s.diff(5).fillna(0)

        # Volume ratio (vs rolling average)
        vol_avg20 = volume.rolling(20).mean().fillna(volume.mean())
        feats["vol_ratio"]     = (volume / vol_avg20.clip(lower=1)).fillna(1.0)

        # Volume trend
        feats["vol_trend"]     = (volume.rolling(5).mean() / volume.rolling(20).mean().clip(lower=1)).fillna(1.0)

        # Price × Volume (force index proxy)
        feats["force_index"]   = (close.diff(1) * volume).fillna(0) / (close.abs().clip(lower=1))

        # High volume up/down bias
        feats["vol_up_bias"]   = (
            (volume * np.sign(close.diff(1))).rolling(10).sum().fillna(0)
        )

        # Volume spike (> 2x average)
        feats["vol_spike"]     = (feats["vol_ratio"] > 2.0).astype(float)

        # On-balance volume momentum
        feats["obv_rsi"]       = (
            pd.Series(self._rsi_of_series(obv_s, 10), index=df.index).fillna(50)
        )

        return feats

    # ─── External Feature Injection ───────────────────────────────────────────

    @staticmethod
    def option_chain_features(
        pcr: float = 1.0,
        oi_skew: float = 0.0,
        max_pain_diff_pct: float = 0.0,
        iv_rank: float = 50.0,
        iv_percentile: float = 50.0,
        gex: float = 0.0,
        atm_iv: float = 15.0,
        call_oi: float = 0.0,
        put_oi: float = 0.0,
        total_oi: float = 0.0,
        iv_skew: float = 0.0,
        iv_term_slope: float = 0.0,
    ) -> dict[str, float]:
        """
        Option chain features (12 features).
        These are injected per-bar from the option chain engine.
        """
        return {
            "pcr":               pcr,
            "pcr_vs_1":          pcr - 1.0,          # Deviation from neutral
            "oi_skew":           oi_skew,
            "max_pain_diff_pct": max_pain_diff_pct,
            "iv_rank":           iv_rank,
            "iv_percentile":     iv_percentile,
            "gex_norm":          min(1.0, max(-1.0, gex / 1e9)) if gex != 0 else 0.0,
            "atm_iv":            atm_iv,
            "call_put_oi_ratio": call_oi / max(1, put_oi),
            "oi_concentration":  total_oi / max(1, call_oi + put_oi),
            "iv_skew":           iv_skew,
            "iv_term_slope":     iv_term_slope,
        }

    @staticmethod
    def macro_features(
        usdinr_chg: float = 0.0,
        crude_chg:  float = 0.0,
        dxy_chg:    float = 0.0,
        gold_chg:   float = 0.0,
        fii_net:    float = 0.0,
        india_vix:  float = 15.0,
        us_10y:     float = 4.5,
        global_bias: float = 50.0,
        macro_risk:  float = 50.0,
        regime_score: float = 0.5,
    ) -> dict[str, float]:
        """Macro features (10 features)."""
        return {
            "macro_usdinr_chg":   usdinr_chg,
            "macro_crude_chg":    crude_chg,
            "macro_dxy_chg":      dxy_chg,
            "macro_gold_chg":     gold_chg,
            "macro_fii_net_norm": min(1.0, max(-1.0, fii_net / 3000.0)),  # Normalize to -1..1
            "macro_india_vix":    india_vix,
            "macro_us_10y":       us_10y,
            "macro_global_bias":  global_bias / 100.0,  # 0..1
            "macro_risk":         macro_risk / 100.0,
            "macro_regime_score": regime_score,
        }

    @staticmethod
    def sentiment_features(
        news_score:    float = 50.0,
        fear_greed:    float = 50.0,
        breadth_score: float = 50.0,
        pcr_sentiment: float = 0.0,   # -1 to +1
        vix_sentiment: float = 0.0,
        advances:      int = 25,
        declines:      int = 25,
        momentum_sent: float = 0.0,
    ) -> dict[str, float]:
        """Sentiment features (8 features)."""
        total = advances + declines
        return {
            "sent_news":       news_score / 100.0,
            "sent_fear_greed": fear_greed / 100.0,
            "sent_breadth":    breadth_score / 100.0,
            "sent_pcr":        pcr_sentiment,
            "sent_vix":        vix_sentiment,
            "sent_adr":        advances / max(1, total),
            "sent_momentum":   momentum_sent,
            "sent_composite":  (news_score + fear_greed + breadth_score) / 300.0,
        }

    @staticmethod
    def calendar_features(dt: datetime, dte: int = 5) -> dict[str, float]:
        """
        Calendar/time features (8 features).
        Captures expiry effects, day-of-week seasonality, etc.
        """
        dow      = dt.weekday()   # 0=Mon, 1=Tue (EXPIRY)
        is_expiry_day   = float(dow == 1)   # Tuesday
        near_expiry     = float(dte <= 2)
        pre_expiry      = float(2 < dte <= 5)

        return {
            "cal_day_of_week":    dow / 4.0,          # Normalize 0-1
            "cal_is_monday":      float(dow == 0),
            "cal_is_tuesday":     is_expiry_day,
            "cal_dte":            min(dte, 10) / 10.0,  # Days to expiry
            "cal_near_expiry":    near_expiry,
            "cal_pre_expiry":     pre_expiry,
            "cal_is_month_end":   float(dt.day >= 25),
            "cal_hour_norm":      dt.hour / 23.0 if dt.hour else 0.375,  # 9AM=~0.375
        }

    # ─── Full Feature Vector Builder ──────────────────────────────────────────

    def build(
        self,
        df: pd.DataFrame,
        option_chain_rows: Optional[list[dict]] = None,
        macro_rows:        Optional[list[dict]] = None,
        sentiment_rows:    Optional[list[dict]] = None,
        target_horizon:    int = 1,  # Bars ahead for label (0=no label)
    ) -> pd.DataFrame:
        """
        Build the complete feature matrix for a DataFrame of OHLCV bars.

        Args:
            df:                 OHLCV DataFrame (indexed by datetime)
            option_chain_rows:  List of dicts per bar for option chain features
            macro_rows:         List of dicts per bar for macro features
            sentiment_rows:     List of dicts per bar for sentiment features
            target_horizon:     Bars ahead for binary target (1=next bar)

        Returns:
            DataFrame with one row per bar and 100+ feature columns.
            NaN rows at the start (warm-up period) are dropped.
        """
        logger.info(f"FeatureStore: building features for {len(df)} bars")

        all_feats = {}
        all_feats.update(self.compute_price_features(df))
        all_feats.update(self.compute_momentum_features(df))
        all_feats.update(self.compute_trend_features(df))
        all_feats.update(self.compute_volatility_features(df))
        all_feats.update(self.compute_volume_features(df))

        feat_df = pd.DataFrame(all_feats, index=df.index)

        # Inject external features (per bar)
        n = len(df)
        for i, (ts, _) in enumerate(df.iterrows()):
            oc   = option_chain_rows[i] if option_chain_rows and i < len(option_chain_rows) else {}
            mac  = macro_rows[i]        if macro_rows        and i < len(macro_rows)        else {}
            sent = sentiment_rows[i]    if sentiment_rows    and i < len(sentiment_rows)    else {}
            cal  = self.calendar_features(ts if isinstance(ts, datetime) else datetime.now(timezone.utc))

            for k, v in self.option_chain_features(**oc).items():
                feat_df.loc[ts, k] = v
            for k, v in self.macro_features(**mac).items():
                feat_df.loc[ts, k] = v
            for k, v in self.sentiment_features(**sent).items():
                feat_df.loc[ts, k] = v
            for k, v in cal.items():
                feat_df.loc[ts, k] = v

        # Binary target: 1 if close[t+horizon] > close[t], else 0
        if target_horizon > 0:
            close = df["close"].astype(float)
            feat_df["target"] = (close.shift(-target_horizon) > close).astype(float)
            # Drop last `horizon` rows where target is NaN (no future data)
            feat_df = feat_df.iloc[:-target_horizon]

        # Drop warm-up rows (NaN from rolling windows)
        feat_df = feat_df.dropna(thresh=int(len(feat_df.columns) * 0.7))
        feat_df = feat_df.fillna(0.0)

        logger.info(f"FeatureStore: produced {len(feat_df)} rows × {len(feat_df.columns)} features")
        return feat_df

    # ─── Helper Methods ────────────────────────────────────────────────────────

    @staticmethod
    def _hh_hl_rolling(df: pd.DataFrame, window: int = 5) -> pd.Series:
        """Score higher-high / higher-low pattern (-1 to +1)."""
        high  = df["high"].astype(float)
        low   = df["low"].astype(float)
        score = pd.Series(0.0, index=df.index)
        for i in range(window, len(df)):
            sl   = slice(i - window, i)
            hh   = int(high.iloc[i] > high.iloc[sl].max())
            hl   = int(low.iloc[i]  > low.iloc[sl].min())
            lh   = int(high.iloc[i] < high.iloc[sl].max())
            ll   = int(low.iloc[i]  < low.iloc[sl].min())
            score.iloc[i] = (hh + hl - lh - ll) / 2.0
        return score

    @staticmethod
    def _rsi_of_series(series: pd.Series, period: int = 10) -> np.ndarray:
        """Compute RSI of any series."""
        delta  = series.diff().fillna(0)
        gain   = delta.clip(lower=0).rolling(period).mean()
        loss   = (-delta.clip(upper=0)).rolling(period).mean()
        rs     = gain / loss.clip(lower=1e-9)
        rsi    = 100 - (100 / (1 + rs))
        return rsi.fillna(50).values

    def feature_names(self, df: pd.DataFrame) -> list[str]:
        """Return the sorted list of all feature names (without target)."""
        feat_df = self.build(df, target_horizon=0)
        return sorted([c for c in feat_df.columns if c != "target"])


# ── Singleton ────────────────────────────────────────────────────────────────
feature_store = FeatureStore()
