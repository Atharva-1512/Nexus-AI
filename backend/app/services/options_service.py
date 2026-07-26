"""
NEXUS AI — Options Service Layer (Phase 3)

Business logic between API endpoints and ChainEngine.
Handles caching, error isolation, and response serialization.
"""

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class OptionsService:
    """Service layer for option chain intelligence."""

    def __init__(self):
        self._engine = None

    def _get_engine(self):
        if self._engine is None:
            from modules.chain_intelligence.chain_engine import chain_engine
            self._engine = chain_engine
        return self._engine

    def _parse_expiry(self, expiry_str: Optional[str]) -> Optional[date]:
        if not expiry_str:
            return None
        try:
            return date.fromisoformat(expiry_str)
        except ValueError:
            raise ValueError(f"Invalid expiry date format: '{expiry_str}'. Use YYYY-MM-DD.")

    async def _get_chain(self, symbol: str, expiry: Optional[str] = None):
        """Fetch and return cached chain snapshot."""
        from modules.chain_intelligence.option_chain_parser import build_synthetic_chain
        expiry_date = self._parse_expiry(expiry)
        engine = self._get_engine()
        # Try live NSE first; fall back to synthetic for dev/testing
        chain = engine._parser.fetch(symbol=symbol, expiry=expiry_date, lot_size=engine.lot_size)
        if chain is None:
            logger.warning(f"NSE unavailable — using synthetic chain for {symbol}")
            chain = build_synthetic_chain(expiry=expiry_date)
        return chain

    async def get_chain(
        self, symbol: str = "NIFTY",
        expiry: Optional[str] = None,
        near_atm: int = 0,
    ) -> dict:
        try:
            chain = await self._get_chain(symbol, expiry)
            strikes = chain.strikes_near_atm(near_atm) if near_atm > 0 else chain.strikes
            return {
                "underlying":    chain.underlying,
                "spot_price":    chain.spot_price,
                "expiry":        chain.expiry.isoformat(),
                "atm_strike":    chain.atm_strike,
                "atm_iv":        chain.atm_iv,
                "pcr_oi":        chain.pcr_oi,
                "pcr_volume":    chain.pcr_volume,
                "total_call_oi": chain.total_call_oi,
                "total_put_oi":  chain.total_put_oi,
                "days_to_expiry":chain.days_to_expiry,
                "expiry_day":    "Tuesday (NIFTY weekly)",
                "timestamp":     chain.timestamp.isoformat(),
                "strikes":       [s.to_dict() for s in strikes],
                "strike_count":  len(strikes),
            }
        except Exception as e:
            logger.error(f"get_chain failed: {e}")
            return {"error": str(e)}

    async def get_pcr(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            result = engine._pcr.analyze(chain)
            concentration = engine._pcr.get_oi_concentration(chain)
            return {
                "symbol":        symbol,
                "expiry":        chain.expiry.isoformat(),
                "spot":          chain.spot_price,
                "pcr_oi":        result.pcr_oi,
                "pcr_volume":    result.pcr_volume,
                "signal":        result.signal.value,
                "bullish_pct":   result.bullish_pct,
                "narrative":     result.narrative,
                "call_oi_wall":  result.call_oi_wall,
                "put_oi_wall":   result.put_oi_wall,
                "oi_concentration": concentration,
                "thresholds": {
                    "strongly_bullish": ">= 1.5",
                    "bullish":          ">= 1.2",
                    "neutral":          "0.8 – 1.2",
                    "bearish":          "< 0.8",
                    "strongly_bearish": "< 0.5",
                },
            }
        except Exception as e:
            logger.error(f"get_pcr failed: {e}")
            return {"error": str(e)}

    async def get_max_pain(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            result = engine._max_pain.calculate(chain)
            reliability = engine._max_pain.max_pain_reliability(chain)
            return {
                "symbol":               symbol,
                "expiry":               chain.expiry.isoformat(),
                "spot":                 chain.spot_price,
                "max_pain_strike":      result.max_pain_strike,
                "distance_from_spot":   result.distance_from_spot,
                "distance_pct":         result.distance_pct,
                "signal":               result.signal,
                "reliability":          reliability,
                "pain_table":           {str(k): v for k, v in result.pain_table.items()},
                "expiry_day":           "Tuesday (NIFTY weekly)",
            }
        except Exception as e:
            logger.error(f"get_max_pain failed: {e}")
            return {"error": str(e)}

    async def get_gex(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            result = engine._gex.calculate(chain)
            profile = engine._gex.net_gex_profile(chain)
            return {
                "symbol":        symbol,
                "expiry":        chain.expiry.isoformat(),
                "spot":          chain.spot_price,
                "total_gex":     result.total_gex,
                "call_gex":      result.call_gex,
                "put_gex":       result.put_gex,
                "regime":        result.regime,
                "gex_flip_level":result.gex_flip_level,
                "narrative":     result.narrative,
                "gex_profile":   profile,
            }
        except Exception as e:
            logger.error(f"get_gex failed: {e}")
            return {"error": str(e)}

    async def get_iv_skew(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            result = engine._iv_skew.analyze(chain)
            return {
                "symbol":          symbol,
                "expiry":          chain.expiry.isoformat(),
                "spot":            chain.spot_price,
                "atm_iv":          result.atm_iv,
                "skew_25d":        result.skew_25d,
                "skew_direction":  result.skew_direction,
                "risk_reversal":   result.risk_reversal,
                "narrative":       result.narrative,
                "iv_by_strike":    {str(k): v for k, v in result.iv_by_strike.items()},
            }
        except Exception as e:
            logger.error(f"get_iv_skew failed: {e}")
            return {"error": str(e)}

    async def get_oi_analysis(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            result = engine._oi.analyze(chain)
            return {
                "symbol":          symbol,
                "expiry":          chain.expiry.isoformat(),
                "spot":            chain.spot_price,
                "call_oi_signal":  result.call_oi_signal,
                "put_oi_signal":   result.put_oi_signal,
                "net_sentiment":   result.net_sentiment.value,
                "bullish_score":   result.bullish_score,
                "oi_change_leader":result.oi_change_leader,
                "narrative":       result.narrative,
                "top_call_oi":     result.top_call_oi,
                "top_put_oi":      result.top_put_oi,
            }
        except Exception as e:
            logger.error(f"get_oi_analysis failed: {e}")
            return {"error": str(e)}

    async def get_support_resistance(
        self, symbol: str = "NIFTY", expiry: Optional[str] = None, n: int = 3
    ) -> dict:
        try:
            chain = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            supports, resistances = engine._sr.detect(chain, n_levels=n)
            return {
                "symbol":       symbol,
                "spot":         chain.spot_price,
                "expiry":       chain.expiry.isoformat(),
                "support_levels": [
                    {
                        "strike":       s.strike,
                        "oi_at_level":  s.oi_at_level,
                        "strength":     s.strength,
                        "distance_pct": s.distance_pct,
                    }
                    for s in supports
                ],
                "resistance_levels": [
                    {
                        "strike":       r.strike,
                        "oi_at_level":  r.oi_at_level,
                        "strength":     r.strength,
                        "distance_pct": r.distance_pct,
                    }
                    for r in resistances
                ],
            }
        except Exception as e:
            logger.error(f"get_support_resistance failed: {e}")
            return {"error": str(e)}

    async def get_key_strikes(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            pcr    = engine._pcr.analyze(chain)
            pain   = engine._max_pain.calculate(chain)
            gex    = engine._gex.calculate(chain)
            return {
                "symbol":    symbol,
                "expiry":    chain.expiry.isoformat(),
                "expiry_day":"Tuesday (NIFTY weekly)",
                "levels": {
                    "spot":       chain.spot_price,
                    "atm":        chain.atm_strike,
                    "max_pain":   pain.max_pain_strike,
                    "call_wall":  pcr.call_oi_wall,
                    "put_wall":   pcr.put_oi_wall,
                    "gex_flip":   gex.gex_flip_level,
                },
                "distances_from_spot": {
                    "to_max_pain_pts":  pain.distance_from_spot,
                    "to_call_wall_pts": round(pcr.call_oi_wall - chain.spot_price, 0) if pcr.call_oi_wall else None,
                    "to_put_wall_pts":  round(chain.spot_price - pcr.put_oi_wall, 0) if pcr.put_oi_wall else None,
                    "to_gex_flip_pts":  round(gex.gex_flip_level - chain.spot_price, 0) if gex.gex_flip_level else None,
                },
            }
        except Exception as e:
            logger.error(f"get_key_strikes failed: {e}")
            return {"error": str(e)}

    async def get_chain_signal(self, symbol: str = "NIFTY", expiry: Optional[str] = None) -> dict:
        try:
            chain  = await self._get_chain(symbol, expiry)
            engine = self._get_engine()
            signal = engine.analyze(chain)
            return {
                "symbol":     symbol,
                "expiry":     chain.expiry.isoformat(),
                "expiry_day": "Tuesday (NIFTY weekly)",
                "spot":       chain.spot_price,
                "signal": {
                    "direction":      signal.direction.value,
                    "confidence":     signal.confidence,
                    "factor_weight":  f"{signal.factor_weight*100:.0f}% of Decision Engine",
                    "narrative":      signal.narrative,
                },
                "key_strikes":   signal.key_strikes,
                "pcr": {
                    "pcr_oi":      signal.pcr.pcr_oi,
                    "pcr_volume":  signal.pcr.pcr_volume,
                    "signal":      signal.pcr.signal.value,
                    "call_wall":   signal.pcr.call_oi_wall,
                    "put_wall":    signal.pcr.put_oi_wall,
                    "weight":      "30%",
                },
                "oi": {
                    "call_signal": signal.pcr.signal.value,
                    "weight":      "25%",
                },
                "gex": {
                    "total_gex":   signal.gex.total_gex,
                    "regime":      signal.gex.regime,
                    "flip_level":  signal.gex.gex_flip_level,
                    "weight":      "20%",
                },
                "max_pain": {
                    "strike":      signal.max_pain.max_pain_strike,
                    "distance":    signal.max_pain.distance_from_spot,
                    "signal":      signal.max_pain.signal,
                    "weight":      "15%",
                },
                "iv_skew": {
                    "atm_iv":      signal.iv_skew.atm_iv,
                    "skew_25d":    signal.iv_skew.skew_25d,
                    "direction":   signal.iv_skew.skew_direction,
                    "weight":      "10%",
                },
                "support_levels": [
                    {"strike": s.strike, "strength": s.strength, "distance_pct": s.distance_pct}
                    for s in signal.support_levels
                ],
                "resistance_levels": [
                    {"strike": r.strike, "strength": r.strength, "distance_pct": r.distance_pct}
                    for r in signal.resistance_levels
                ],
                "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
            }
        except Exception as e:
            logger.error(f"get_chain_signal failed: {e}")
            return {"error": str(e)}

    async def get_expiries(self, symbol: str = "NIFTY") -> dict:
        try:
            engine = self._get_engine()
            raw = engine._parser.fetch_raw(symbol)
            if raw:
                expiries = raw.get("records", {}).get("expiryDates", [])
            else:
                from modules.market_data.market_hours import next_expiry_date
                from datetime import timedelta
                today = date.today()
                expiries = []
                cursor = today
                for _ in range(8):
                    expiry = next_expiry_date(cursor, symbol)
                    expiries.append(expiry.isoformat())
                    cursor = expiry + timedelta(days=1)
            return {
                "symbol":   symbol,
                "expiries": expiries,
                "note":     "NIFTY weekly expiry = Tuesday. Monthly expiry = last Tuesday of month.",
            }
        except Exception as e:
            logger.error(f"get_expiries failed: {e}")
            return {"error": str(e)}


# ── Singleton ─────────────────────────────────────────────────────────────────
_svc: Optional[OptionsService] = None

def get_options_service() -> OptionsService:
    global _svc
    if _svc is None:
        _svc = OptionsService()
    return _svc
