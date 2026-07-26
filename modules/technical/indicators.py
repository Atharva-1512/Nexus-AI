"""
NEXUS AI — Technical Indicators (Module 6)

Pure-Python implementations of all core technical indicators.
No TA-Lib dependency — uses only pandas + numpy for portability.

Indicators implemented:
  - SMA / EMA (any period)
  - RSI (Wilder's smoothing)
  - MACD (12/26/9 EMA)
  - Bollinger Bands (20, ±2σ)
  - ATR (Average True Range)
  - Stochastic Oscillator (%K / %D)
  - VWAP (Volume-Weighted Average Price)
  - OBV (On-Balance Volume)
  - ADX (Average Directional Index)
  - Supertrend

All functions accept a pandas DataFrame with columns:
  open, high, low, close, volume (lowercase)
and return a new DataFrame or Series with computed values.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd


# ─── Moving Averages ──────────────────────────────────────────────────────────

def sma(close: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average (Wilder-style adjust=False)."""
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def wma(close: pd.Series, period: int) -> pd.Series:
    """Weighted Moving Average (linearly weighted)."""
    weights = np.arange(1, period + 1, dtype=float)
    return close.rolling(window=period, min_periods=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


def hma(close: pd.Series, period: int) -> pd.Series:
    """Hull Moving Average: reduces lag vs SMA."""
    half = period // 2
    sqrt_period = int(math.sqrt(period))
    raw = 2 * wma(close, half) - wma(close, period)
    return wma(raw, sqrt_period)


# ─── RSI ──────────────────────────────────────────────────────────────────────

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI using Wilder's Smoothed Moving Average.

    Returns:
        RSI values (0–100)
        > 70 = overbought, < 30 = oversold
    """
    delta  = close.diff()
    gain   = delta.clip(lower=0)
    loss   = (-delta).clip(lower=0)
    avg_g  = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_l  = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs     = avg_g / avg_l.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def rsi_signal(rsi_value: float) -> str:
    """Classify RSI value into a trading signal."""
    if rsi_value >= 80:   return "EXTREMELY_OVERBOUGHT"
    if rsi_value >= 70:   return "OVERBOUGHT"
    if rsi_value >= 60:   return "BULLISH"
    if rsi_value >= 40:   return "NEUTRAL"
    if rsi_value >= 30:   return "BEARISH"
    if rsi_value >= 20:   return "OVERSOLD"
    return "EXTREMELY_OVERSOLD"


# ─── MACD ─────────────────────────────────────────────────────────────────────

def macd(
    close:      pd.Series,
    fast:       int = 12,
    slow:       int = 26,
    signal_p:   int = 9,
) -> pd.DataFrame:
    """
    MACD with Signal Line and Histogram.

    Returns DataFrame with columns: macd, signal, histogram
    Bullish: MACD > Signal (and histogram turning positive)
    Bearish: MACD < Signal (and histogram turning negative)
    """
    fast_ema   = ema(close, fast)
    slow_ema   = ema(close, slow)
    macd_line  = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=signal_p, adjust=False, min_periods=signal_p).mean()
    histogram  = macd_line - signal_line
    return pd.DataFrame({
        "macd":      macd_line,
        "signal":    signal_line,
        "histogram": histogram,
    })


def macd_crossover_signal(macd_df: pd.DataFrame) -> str:
    """
    Detect the most recent MACD crossover type.
    Returns: BULLISH_CROSS | BEARISH_CROSS | BULLISH | BEARISH | NEUTRAL
    """
    if len(macd_df) < 2:
        return "NEUTRAL"
    prev = macd_df.iloc[-2]
    curr = macd_df.iloc[-1]

    # Fresh crossover (most significant)
    if prev["macd"] < prev["signal"] and curr["macd"] > curr["signal"]:
        return "BULLISH_CROSS"
    if prev["macd"] > prev["signal"] and curr["macd"] < curr["signal"]:
        return "BEARISH_CROSS"
    # Direction without fresh cross
    if curr["macd"] > curr["signal"] and curr["histogram"] > 0:
        return "BULLISH"
    if curr["macd"] < curr["signal"] and curr["histogram"] < 0:
        return "BEARISH"
    return "NEUTRAL"


# ─── Bollinger Bands ──────────────────────────────────────────────────────────

def bollinger_bands(
    close:   pd.Series,
    period:  int   = 20,
    std_dev: float = 2.0,
) -> pd.DataFrame:
    """
    Bollinger Bands.

    Returns DataFrame: upper, middle, lower, bandwidth, %B
    Bandwidth: (upper - lower) / middle × 100
    %B:        (close - lower) / (upper - lower)  [0 = at lower, 1 = at upper]
    """
    middle = sma(close, period)
    std    = close.rolling(window=period, min_periods=period).std()
    upper  = middle + std_dev * std
    lower  = middle - std_dev * std
    bw     = (upper - lower) / middle * 100
    pct_b  = (close - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame({
        "upper":     upper,
        "middle":    middle,
        "lower":     lower,
        "bandwidth": bw,
        "pct_b":     pct_b,
    })


def bb_signal(bb_row: pd.Series, close_val: float) -> str:
    """Classify current price position within Bollinger Bands."""
    if pd.isna(bb_row["upper"]):
        return "INSUFFICIENT_DATA"
    pct_b = bb_row.get("pct_b", float("nan"))
    bw    = bb_row.get("bandwidth", float("nan"))

    # Squeeze: very tight bands → breakout imminent
    if not pd.isna(bw) and bw < 2.0:
        return "SQUEEZE"
    if not pd.isna(pct_b):
        if pct_b > 1.0:   return "UPPER_BREAKOUT"
        if pct_b > 0.8:   return "NEAR_UPPER"
        if pct_b < 0.0:   return "LOWER_BREAKOUT"
        if pct_b < 0.2:   return "NEAR_LOWER"
    return "NEUTRAL"


# ─── ATR ──────────────────────────────────────────────────────────────────────

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Average True Range (Wilder smoothing).

    True Range = max(H-L, |H-prev_C|, |L-prev_C|)
    """
    h   = df["high"]
    l   = df["low"]
    pc  = df["close"].shift(1)
    tr  = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()


# ─── Stochastic Oscillator ────────────────────────────────────────────────────

def stochastic(
    df:     pd.DataFrame,
    k_period: int = 14,
    d_period: int = 3,
    smooth_k: int = 3,
) -> pd.DataFrame:
    """
    Stochastic Oscillator (%K and %D).

    %K = (close - lowest_low) / (highest_high - lowest_low) × 100
    %D = SMA(%K, d_period)
    """
    low_min  = df["low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["high"].rolling(window=k_period, min_periods=k_period).max()
    raw_k    = 100 * (df["close"] - low_min) / (high_max - low_min).replace(0, np.nan)
    pct_k    = sma(raw_k, smooth_k)
    pct_d    = sma(pct_k, d_period)
    return pd.DataFrame({"k": pct_k, "d": pct_d})


# ─── VWAP ────────────────────────────────────────────────────────────────────

def vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume-Weighted Average Price (session VWAP — resets each day).

    For intraday data only. On daily data, returns a rolling VWAP proxy.
    """
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    cum_tp_vol    = (typical_price * df["volume"]).cumsum()
    cum_vol       = df["volume"].cumsum()
    return cum_tp_vol / cum_vol.replace(0, np.nan)


def vwap_signal(close: float, vwap_val: float) -> str:
    """Signal based on price position relative to VWAP."""
    if pd.isna(vwap_val) or vwap_val == 0:
        return "NEUTRAL"
    pct_diff = (close - vwap_val) / vwap_val * 100
    if pct_diff > 0.5:    return "BULLISH"    # Price well above VWAP
    if pct_diff > 0.0:    return "SLIGHTLY_BULLISH"
    if pct_diff < -0.5:   return "BEARISH"
    if pct_diff < 0.0:    return "SLIGHTLY_BEARISH"
    return "AT_VWAP"


# ─── OBV ─────────────────────────────────────────────────────────────────────

def obv(df: pd.DataFrame) -> pd.Series:
    """
    On-Balance Volume. Cumulative volume where:
    - Price up day: add volume
    - Price down day: subtract volume
    """
    direction = np.sign(df["close"].diff())
    return (direction * df["volume"]).cumsum()


def obv_trend(obv_series: pd.Series, period: int = 10) -> str:
    """Detect OBV trend direction over the last N bars."""
    if len(obv_series) < period:
        return "INSUFFICIENT_DATA"
    slope = obv_series.iloc[-1] - obv_series.iloc[-period]
    if slope > 0:   return "RISING"
    if slope < 0:   return "FALLING"
    return "FLAT"


# ─── ADX ─────────────────────────────────────────────────────────────────────

def adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Average Directional Index.

    Returns DataFrame: adx, plus_di, minus_di
    ADX > 25 = strong trend
    ADX > 40 = very strong trend
    ADX < 20 = weak/no trend
    +DI > -DI = bullish trend
    -DI > +DI = bearish trend
    """
    h  = df["high"]
    l  = df["low"]
    pc = df["close"].shift(1)

    tr   = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    up   = h.diff()
    dn   = (-l.diff())
    plus_dm  = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)

    atr_s   = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    plus_di_s  = 100 * pd.Series(plus_dm,  index=df.index).ewm(
        alpha=1/period, adjust=False, min_periods=period).mean() / atr_s
    minus_di_s = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1/period, adjust=False, min_periods=period).mean() / atr_s

    dx  = 100 * (plus_di_s - minus_di_s).abs() / (plus_di_s + minus_di_s).replace(0, np.nan)
    adx_s = dx.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

    return pd.DataFrame({
        "adx":      adx_s,
        "plus_di":  plus_di_s,
        "minus_di": minus_di_s,
    })


# ─── Supertrend ───────────────────────────────────────────────────────────────

def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """
    Supertrend indicator.

    Returns DataFrame: supertrend, direction (1=bullish, -1=bearish), is_bullish
    """
    atr_s = atr(df, period)
    hl2   = (df["high"] + df["low"]) / 2
    upper = hl2 + multiplier * atr_s
    lower = hl2 - multiplier * atr_s

    supertrend_vals = pd.Series(index=df.index, dtype=float)
    direction       = pd.Series(index=df.index, dtype=float)  # float to allow NaN for early bars
    close           = df["close"]

    for i in range(1, len(df)):
        idx      = df.index[i]
        prev_idx = df.index[i - 1]

        # Upper band
        up_curr  = upper.iloc[i]
        up_prev  = supertrend_vals.get(prev_idx, up_curr)
        if close.iloc[i - 1] > up_prev:
            upper_val = min(up_curr, up_prev)
        else:
            upper_val = up_curr

        # Lower band
        lo_curr  = lower.iloc[i]
        lo_prev  = supertrend_vals.get(prev_idx, lo_curr)
        if close.iloc[i - 1] < lo_prev:
            lower_val = max(lo_curr, lo_prev)
        else:
            lower_val = lo_curr

        prev_dir = direction.get(prev_idx, 1)
        if prev_dir == -1 and close.iloc[i] > upper_val:
            direction[idx] = 1
        elif prev_dir == 1 and close.iloc[i] < lower_val:
            direction[idx] = -1
        else:
            direction[idx] = prev_dir

        supertrend_vals[idx] = lower_val if direction[idx] == 1 else upper_val

    return pd.DataFrame({
        "supertrend": supertrend_vals,
        "direction":  direction,
        "is_bullish": direction == 1,
    })


# ─── Compute All Indicators ───────────────────────────────────────────────────

def compute_all(df: pd.DataFrame) -> dict:
    """
    Compute all indicators on a OHLCV DataFrame.

    Returns a dict of the latest values for the Decision Engine.
    """
    if len(df) < 30:
        return {"error": "Insufficient data (need ≥ 30 bars)"}

    # Sanitize: fill NaN volumes with 0, drop rows where close is NaN
    df = df.copy()
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
    df = df.dropna(subset=["close", "high", "low", "open"])
    if len(df) < 30:
        return {"error": "Insufficient data after NaN cleanup"}

    close = df["close"]
    last  = len(df) - 1

    # Moving averages
    ema9   = ema(close, 9)
    ema21  = ema(close, 21)
    ema50  = ema(close, 50) if len(df) >= 50 else pd.Series(dtype=float)
    sma200 = sma(close, 200) if len(df) >= 200 else pd.Series(dtype=float)

    # RSI
    rsi14  = rsi(close, 14)
    rsi_val = round(float(rsi14.iloc[-1]), 2) if not rsi14.empty else None

    # MACD
    macd_df   = macd(close)
    macd_sig  = macd_crossover_signal(macd_df)

    # Bollinger Bands
    bb       = bollinger_bands(close, 20)
    bb_sig   = bb_signal(bb.iloc[-1], float(close.iloc[-1]))

    # ATR
    atr_val  = round(float(atr(df, 14).iloc[-1]), 2) if len(df) >= 14 else None

    # Stochastic
    stoch    = stochastic(df)
    stoch_k  = round(float(stoch["k"].iloc[-1]), 2) if not stoch.empty else None
    stoch_d  = round(float(stoch["d"].iloc[-1]), 2) if not stoch.empty else None

    # VWAP
    vwap_s   = vwap(df)
    vwap_val = round(float(vwap_s.iloc[-1]), 2) if not vwap_s.empty else None
    vwap_sig = vwap_signal(float(close.iloc[-1]), vwap_val or 0)

    # OBV
    obv_s     = obv(df)
    obv_trend_sig = obv_trend(obv_s)

    # ADX
    adx_df    = adx(df)
    adx_val   = round(float(adx_df["adx"].iloc[-1]),      2) if not adx_df.empty else None
    plus_di   = round(float(adx_df["plus_di"].iloc[-1]),  2) if not adx_df.empty else None
    minus_di  = round(float(adx_df["minus_di"].iloc[-1]), 2) if not adx_df.empty else None

    # Supertrend
    st_df      = supertrend(df)
    st_dir_raw = st_df["direction"].dropna()
    st_dir     = int(st_dir_raw.iloc[-1]) if not st_dir_raw.empty else 1
    st_bull_s  = st_df["is_bullish"].dropna()
    st_bull    = bool(st_bull_s.iloc[-1]) if not st_bull_s.empty else True

    close_val = float(close.iloc[-1])

    return {
        "close":         close_val,
        "ema9":          round(float(ema9.iloc[-1]),  2) if not ema9.empty  else None,
        "ema21":         round(float(ema21.iloc[-1]), 2) if not ema21.empty else None,
        "ema50":         round(float(ema50.iloc[-1]), 2) if not ema50.empty else None,
        "sma200":        round(float(sma200.iloc[-1]), 2) if not sma200.empty else None,
        "ema9_21_cross": "BULLISH" if (not ema9.empty and not ema21.empty
                         and float(ema9.iloc[-1]) > float(ema21.iloc[-1])) else "BEARISH",
        "rsi":           rsi_val,
        "rsi_signal":    rsi_signal(rsi_val) if rsi_val else "NEUTRAL",
        "macd":          round(float(macd_df["macd"].iloc[-1]), 4),
        "macd_signal":   round(float(macd_df["signal"].iloc[-1]), 4),
        "macd_histogram":round(float(macd_df["histogram"].iloc[-1]), 4),
        "macd_crossover":macd_sig,
        "bb_upper":      round(float(bb["upper"].iloc[-1]), 2),
        "bb_middle":     round(float(bb["middle"].iloc[-1]), 2),
        "bb_lower":      round(float(bb["lower"].iloc[-1]), 2),
        "bb_bandwidth":  round(float(bb["bandwidth"].iloc[-1]), 2),
        "bb_pct_b":      round(float(bb["pct_b"].iloc[-1]), 4),
        "bb_signal":     bb_sig,
        "atr":           atr_val,
        "stoch_k":       stoch_k,
        "stoch_d":       stoch_d,
        "stoch_signal":  "OVERBOUGHT" if (stoch_k or 0) > 80 else "OVERSOLD" if (stoch_k or 100) < 20 else "NEUTRAL",
        "vwap":          vwap_val,
        "vwap_signal":   vwap_sig,
        "obv_trend":     obv_trend_sig,
        "adx":           adx_val,
        "plus_di":       plus_di,
        "minus_di":      minus_di,
        "adx_trend":     "STRONG" if (adx_val or 0) > 25 else "WEAK",
        "supertrend_direction": "BULLISH" if st_bull else "BEARISH",
        "supertrend_value":     round(float(st_df["supertrend"].iloc[-1]), 2),
    }


# ─── Additional Indicators (Phase 8 Feature Store) ────────────────────────────

def sma(close: pd.Series, period: int = 20) -> pd.Series:
    """Simple Moving Average."""
    return close.rolling(period).mean()


def cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    Commodity Channel Index.
    CCI = (Typical Price - SMA(TP, n)) / (0.015 × Mean Absolute Deviation)
    """
    tp  = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3.0
    sma_tp = tp.rolling(period).mean()
    mad    = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    return (tp - sma_tp) / (0.015 * mad.clip(lower=1e-9))


def mfi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Money Flow Index (volume-weighted RSI).
    MFI = 100 - 100 / (1 + Positive Money Flow / Negative Money Flow)
    """
    tp   = (df["high"].astype(float) + df["low"].astype(float) + df["close"].astype(float)) / 3.0
    vol  = df["volume"].astype(float).fillna(0)
    mf   = tp * vol

    pos_mf = pd.Series(np.where(tp > tp.shift(1), mf, 0.0), index=df.index)
    neg_mf = pd.Series(np.where(tp < tp.shift(1), mf, 0.0), index=df.index)

    pos_sum = pos_mf.rolling(period).sum()
    neg_sum = neg_mf.rolling(period).sum()

    mfr = pos_sum / neg_sum.clip(lower=1e-9)
    return 100 - (100 / (1 + mfr))
