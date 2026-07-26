"""
NEXUS AI — Technical Analysis Service Layer (Phase 4)
"""
import logging
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


def _make_df(n: int = 100, trend: str = "up") -> pd.DataFrame:
    """Generate a synthetic OHLCV DataFrame for testing."""
    import numpy as np
    base = 24000.0
    closes = [base]
    for i in range(n - 1):
        if trend == "up":
            closes.append(closes[-1] + np.random.normal(20, 30))
        elif trend == "down":
            closes.append(closes[-1] + np.random.normal(-20, 30))
        else:
            closes.append(closes[-1] + np.random.normal(0, 30))
    closes = [max(100.0, c) for c in closes]
    opens  = [c * np.random.uniform(0.998, 1.002) for c in closes]
    highs  = [max(o, c) * np.random.uniform(1.0, 1.005) for o, c in zip(opens, closes)]
    lows   = [min(o, c) * np.random.uniform(0.995, 1.0) for o, c in zip(opens, closes)]
    vols   = [int(np.random.uniform(1_000_000, 5_000_000)) for _ in range(n)]
    import pandas as pd
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": vols})


class TechnicalService:
    """Service layer for technical analysis endpoints."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from modules.technical.tech_engine import tech_engine
            self._engine = tech_engine
        return self._engine

    async def _load_df(
        self, symbol: str, interval: str = "1d", period: str = "3mo"
    ) -> Optional[pd.DataFrame]:
        try:
            from modules.market_data.market_data_engine import market_engine
            df = await market_engine.get_ohlcv(symbol, interval=interval, period=period)
            if df is not None and not df.empty and len(df) >= 30:
                # Ensure volume is numeric and NaN-safe
                df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
                return df
        except Exception:
            pass
        logger.warning(f"Using synthetic data for {symbol}")
        df = _make_df(100, "up")
        df["volume"] = df["volume"].fillna(0).astype(int)
        return df

    async def get_signal(self, symbol: str = "NIFTY", interval: str = "1d", period: str = "3mo") -> dict:
        try:
            df     = await self._load_df(symbol, interval, period)
            engine = self._get_engine()
            signal = engine.analyze_df(df)
            return {
                "symbol":       symbol,
                "interval":     interval,
                "direction":    signal.direction,
                "confidence":   signal.confidence,
                "bullish_score":signal.bullish_score,
                "factor_scores":signal.factor_scores,
                "factor_weight":f"{signal.factor_weight*100:.0f}% of Decision Engine",
                "narrative":    signal.narrative,
                "trend": {
                    "direction":        signal.trend.direction.value,
                    "strength":         signal.trend.strength,
                    "slope_pct":        signal.trend.slope_pct,
                    "consecutive_bars": signal.trend.consecutive_bars,
                    "higher_highs":     signal.trend.higher_highs,
                    "higher_lows":      signal.trend.higher_lows,
                },
                "patterns": [
                    {"type": p.pattern_type.value, "direction": p.direction, "strength": p.strength, "desc": p.description}
                    for p in signal.patterns[:5]
                ],
                "generated_at": signal.timestamp.isoformat() if signal.timestamp else None,
            }
        except Exception as e:
            logger.error(f"get_signal failed: {e}")
            return {"error": str(e)}

    async def get_indicators(self, symbol: str = "NIFTY", interval: str = "1d", period: str = "3mo") -> dict:
        try:
            df  = await self._load_df(symbol, interval, period)
            from modules.technical.indicators import compute_all
            ind = compute_all(df)
            return {"symbol": symbol, "interval": interval, "indicators": ind}
        except Exception as e:
            logger.error(f"get_indicators failed: {e}")
            return {"error": str(e)}

    async def get_patterns(self, symbol: str = "NIFTY", interval: str = "1d", period: str = "3mo") -> dict:
        try:
            df      = await self._load_df(symbol, interval, period)
            engine  = self._get_engine()
            patterns = engine._pa.detect_patterns(df, lookback=10)
            return {
                "symbol":   symbol,
                "interval": interval,
                "patterns": [
                    {"type": p.pattern_type.value, "bar_index": p.bar_index,
                     "direction": p.direction, "strength": p.strength, "desc": p.description}
                    for p in patterns
                ],
                "count": len(patterns),
                "dominant_signal": engine._pa.latest_pattern_signal(patterns),
            }
        except Exception as e:
            logger.error(f"get_patterns failed: {e}")
            return {"error": str(e)}

    async def get_trend(self, symbol: str = "NIFTY", interval: str = "1d", period: str = "3mo") -> dict:
        try:
            df     = await self._load_df(symbol, interval, period)
            engine = self._get_engine()
            trend  = engine._pa.analyze_trend(df)
            return {
                "symbol":           symbol,
                "interval":         interval,
                "direction":        trend.direction.value,
                "strength":         trend.strength,
                "slope_pct":        trend.slope_pct,
                "consecutive_bars": trend.consecutive_bars,
                "higher_highs":     trend.higher_highs,
                "higher_lows":      trend.higher_lows,
                "lower_highs":      trend.lower_highs,
                "lower_lows":       trend.lower_lows,
                "swing_highs":      trend.swing_highs,
                "swing_lows":       trend.swing_lows,
                "narrative":        trend.narrative,
            }
        except Exception as e:
            logger.error(f"get_trend failed: {e}")
            return {"error": str(e)}

    async def get_support_resistance(self, symbol: str = "NIFTY", interval: str = "1d", period: str = "3mo") -> dict:
        try:
            df     = await self._load_df(symbol, interval, period)
            spot   = float(df["close"].iloc[-1])
            engine = self._get_engine()
            sr     = engine._sr.all_levels(df, spot)
            return {"symbol": symbol, **sr}
        except Exception as e:
            logger.error(f"get_support_resistance failed: {e}")
            return {"error": str(e)}

    async def get_ohlcv_with_indicators(self, symbol: str = "NIFTY", interval: str = "1d", period: str = "3mo") -> dict:
        try:
            df  = await self._load_df(symbol, interval, period)
            from modules.technical.indicators import (
                ema as _ema, rsi as _rsi, macd as _macd,
                bollinger_bands as _bb, vwap as _vwap, atr as _atr
            )
            close  = df["close"]
            ema9   = _ema(close, 9)
            ema21  = _ema(close, 21)
            rsi14  = _rsi(close, 14)
            macd_df = _macd(close)
            bb_df   = _bb(close, 20)
            vwap_s  = _vwap(df)
            atr14   = _atr(df, 14)

            bars = []
            for i, (idx, row) in enumerate(df.iterrows()):
                bars.append({
                    "t":  str(idx),
                    "o":  round(float(row["open"]),  2),
                    "h":  round(float(row["high"]),  2),
                    "l":  round(float(row["low"]),   2),
                    "c":  round(float(row["close"]), 2),
                    "v":  int(row["volume"]) if not pd.isna(row["volume"]) else 0,
                    "ema9":  round(float(ema9.iloc[i]), 2) if not pd.isna(ema9.iloc[i]) else None,
                    "ema21": round(float(ema21.iloc[i]), 2) if not pd.isna(ema21.iloc[i]) else None,
                    "rsi":   round(float(rsi14.iloc[i]), 2) if not pd.isna(rsi14.iloc[i]) else None,
                    "macd":  round(float(macd_df["macd"].iloc[i]), 4) if not pd.isna(macd_df["macd"].iloc[i]) else None,
                    "bb_upper": round(float(bb_df["upper"].iloc[i]), 2) if not pd.isna(bb_df["upper"].iloc[i]) else None,
                    "bb_lower": round(float(bb_df["lower"].iloc[i]), 2) if not pd.isna(bb_df["lower"].iloc[i]) else None,
                    "vwap": round(float(vwap_s.iloc[i]), 2) if not pd.isna(vwap_s.iloc[i]) else None,
                    "atr":  round(float(atr14.iloc[i]), 2) if not pd.isna(atr14.iloc[i]) else None,
                })
            return {"symbol": symbol, "interval": interval, "count": len(bars), "bars": bars}
        except Exception as e:
            logger.error(f"get_ohlcv_with_indicators failed: {e}")
            return {"error": str(e)}


_svc: Optional[TechnicalService] = None

def get_technical_service() -> TechnicalService:
    global _svc
    if _svc is None:
        _svc = TechnicalService()
    return _svc
