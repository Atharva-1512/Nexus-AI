"""
NEXUS AI — Option Chain Parser (Module 5)

Converts raw NSE option chain API JSON into structured OptionStrike objects.

NSE API endpoint: https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY
Response structure:
  {
    "records": {
      "data": [ { "strikePrice": 24000, "expiryDate": "28-Jul-2026", "CE": {...}, "PE": {...} } ],
      "expiryDates": ["28-Jul-2026", "05-Aug-2026", ...],
      "underlyingValue": 24350.55,
      "timestamp": "25-Jul-2026 15:30:00"
    }
  }

Also handles synthetic chain generation for testing (no live NSE needed).
"""

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

import requests

from .models import ChainSnapshot, OptionStrike, OIBuildType

logger = logging.getLogger(__name__)

_NSE_CHAIN_URL  = "https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
_NSE_EXPIRY_FMT = "%d-%b-%Y"   # e.g. "28-Jul-2026"

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":           "application/json, */*",
    "Accept-Language":  "en-US,en;q=0.9",
    "Referer":          "https://www.nseindia.com",
    "Connection":       "keep-alive",
}


class OptionChainParser:
    """
    Fetches and parses the live NSE option chain.

    Usage:
        parser = OptionChainParser()
        snapshot = parser.fetch("NIFTY")           # Live from NSE
        snapshot = parser.fetch("NIFTY", expiry=date(2026, 7, 28))
    """

    def __init__(self):
        self._session        = requests.Session()
        self._session.headers.update(_NSE_HEADERS)
        self._session_ready  = False

    def _ensure_nse_session(self) -> None:
        """NSE requires a prior GET to / to set cookies before the API call."""
        if not self._session_ready:
            try:
                self._session.get("https://www.nseindia.com", timeout=10)
                self._session_ready = True
                logger.debug("NSE session initialized")
            except Exception as e:
                logger.warning(f"NSE session init failed: {e}")

    def fetch_raw(self, symbol: str = "NIFTY") -> Optional[dict]:
        """
        Fetch raw JSON from NSE option chain API.

        Returns:
            Raw JSON dict, or None on failure
        """
        self._ensure_nse_session()
        url = _NSE_CHAIN_URL.format(symbol=symbol.upper())
        try:
            resp = self._session.get(url, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error(f"NSE option chain fetch failed [{symbol}]: {e}")
            return None

    def parse(
        self,
        raw_data:   dict,
        symbol:     str = "NIFTY",
        expiry:     Optional[date] = None,
        lot_size:   int = 75,
    ) -> Optional[ChainSnapshot]:
        """
        Parse raw NSE JSON → ChainSnapshot.

        Args:
            raw_data:   Raw API response dict
            symbol:     Underlying symbol name
            expiry:     Filter to this expiry (None = nearest/current expiry)
            lot_size:   Contract lot size (NIFTY=75, BANKNIFTY=15)

        Returns:
            ChainSnapshot or None if parse fails
        """
        try:
            records     = raw_data.get("records", {})
            spot_price  = float(records.get("underlyingValue", 0))
            raw_data_list = records.get("data", [])
            expiry_dates  = records.get("expiryDates", [])

            if not raw_data_list or spot_price == 0:
                logger.warning(f"Empty/invalid option chain data for {symbol}")
                return None

            # Determine target expiry
            target_expiry = expiry or self._nearest_expiry(expiry_dates)
            if target_expiry is None:
                return None

            target_expiry_str = target_expiry.strftime(_NSE_EXPIRY_FMT).upper()

            # Parse timestamp
            ts_str = records.get("timestamp", "")
            try:
                ts = datetime.strptime(ts_str, "%d-%b-%Y %H:%M:%S")
            except Exception:
                ts = datetime.utcnow()

            # Build OptionStrike objects
            strikes: list[OptionStrike] = []
            for row in raw_data_list:
                row_expiry = row.get("expiryDate", "").upper()
                if row_expiry != target_expiry_str:
                    continue

                strike_price = float(row.get("strikePrice", 0))
                if strike_price <= 0:
                    continue

                ce = row.get("CE", {}) or {}
                pe = row.get("PE", {}) or {}

                opt = OptionStrike(
                    strike       = strike_price,
                    expiry       = target_expiry,
                    # Call fields
                    call_oi          = int(ce.get("openInterest",         0) or 0),
                    call_oi_change   = int(ce.get("changeinOpenInterest", 0) or 0),
                    call_volume      = int(ce.get("totalTradedVolume",     0) or 0),
                    call_iv          = float(ce.get("impliedVolatility",   0) or 0),
                    call_ltp         = float(ce.get("lastPrice",           0) or 0),
                    call_bid         = float(ce.get("bidprice",            0) or 0),
                    call_ask         = float(ce.get("askPrice",            0) or 0),
                    # Put fields
                    put_oi           = int(pe.get("openInterest",          0) or 0),
                    put_oi_change    = int(pe.get("changeinOpenInterest",  0) or 0),
                    put_volume       = int(pe.get("totalTradedVolume",     0) or 0),
                    put_iv           = float(pe.get("impliedVolatility",   0) or 0),
                    put_ltp          = float(pe.get("lastPrice",           0) or 0),
                    put_bid          = float(pe.get("bidprice",            0) or 0),
                    put_ask          = float(pe.get("askPrice",            0) or 0),
                )

                # Derived fields
                opt.total_oi = opt.call_oi + opt.put_oi
                opt.pcr_oi   = round(opt.put_oi / opt.call_oi, 4) if opt.call_oi else 0.0
                opt.iv_skew  = round(opt.put_iv - opt.call_iv, 4)
                opt.oi_build_call = _classify_oi_build(opt.call_ltp, opt.call_oi_change)
                opt.oi_build_put  = _classify_oi_build(opt.put_ltp,  opt.put_oi_change)

                strikes.append(opt)

            if not strikes:
                logger.warning(f"No strikes found for expiry {target_expiry_str}")
                return None

            strikes.sort(key=lambda s: s.strike)

            # Find ATM strike (closest to spot)
            atm = min(strikes, key=lambda s: abs(s.strike - spot_price))

            snapshot = ChainSnapshot(
                underlying       = symbol,
                spot_price       = spot_price,
                expiry           = target_expiry,
                timestamp        = ts,
                strikes          = strikes,
                lot_size         = lot_size,
                total_call_oi    = sum(s.call_oi   for s in strikes),
                total_put_oi     = sum(s.put_oi    for s in strikes),
                total_call_volume= sum(s.call_volume for s in strikes),
                total_put_volume = sum(s.put_volume  for s in strikes),
                atm_strike       = atm.strike,
                atm_call_iv      = atm.call_iv,
                atm_put_iv       = atm.put_iv,
            )

            # PCR aggregates
            snapshot.pcr_oi = (
                round(snapshot.total_put_oi / snapshot.total_call_oi, 4)
                if snapshot.total_call_oi else 0.0
            )
            snapshot.pcr_volume = (
                round(snapshot.total_put_volume / snapshot.total_call_volume, 4)
                if snapshot.total_call_volume else 0.0
            )

            logger.info(
                f"Parsed option chain [{symbol} {target_expiry}]: "
                f"{len(strikes)} strikes, spot={spot_price}, ATM={atm.strike}, "
                f"PCR={snapshot.pcr_oi:.2f}"
            )
            return snapshot

        except Exception as e:
            logger.error(f"Option chain parse error: {e}", exc_info=True)
            return None

    def fetch(
        self,
        symbol:     str = "NIFTY",
        expiry:     Optional[date] = None,
        lot_size:   int = 75,
    ) -> Optional[ChainSnapshot]:
        """Convenience: fetch + parse in one call."""
        raw = self.fetch_raw(symbol)
        if raw is None:
            return None
        return self.parse(raw, symbol=symbol, expiry=expiry, lot_size=lot_size)

    @staticmethod
    def _nearest_expiry(expiry_dates: list[str]) -> Optional[date]:
        """Returns the nearest (current week) expiry from a list of date strings."""
        today = date.today()
        parsed = []
        for ds in expiry_dates:
            try:
                d = datetime.strptime(ds, _NSE_EXPIRY_FMT).date()
                if d >= today:
                    parsed.append(d)
            except Exception:
                continue
        return min(parsed) if parsed else None


# ─── Synthetic Chain Generator (for testing without live NSE) ─────────────────

def build_synthetic_chain(
    spot:       float = 24350.0,
    expiry:     Optional[date] = None,
    symbol:     str = "NIFTY",
    lot_size:   int = 75,
    num_strikes: int = 20,
    atm_iv:     float = 14.0,
    lot_interval: float = 50.0,
) -> ChainSnapshot:
    """
    Generate a realistic synthetic option chain for testing.

    Uses Black-Scholes to compute fair option prices and IVs.
    Generates a realistic OI distribution with more OI at round numbers.

    Args:
        spot:           Underlying spot price
        expiry:         Expiry date (defaults to next Tuesday)
        num_strikes:    Number of strikes above and below ATM
        atm_iv:         ATM implied volatility (%)
        lot_interval:   Strike spacing

    Returns:
        ChainSnapshot with realistic synthetic data
    """
    import math
    from datetime import timedelta

    if expiry is None:
        # Default to next Tuesday
        today = date.today()
        days  = (1 - today.weekday()) % 7 or 7
        expiry = today + timedelta(days=days)

    # Round spot to nearest strike
    atm_strike = round(spot / lot_interval) * lot_interval
    tte_years  = max((expiry - date.today()).days / 365.0, 1 / 365)
    r          = 0.065   # Risk-free rate (India 10Y ~6.5%)
    atm_iv_dec = atm_iv / 100.0

    strikes: list[OptionStrike] = []

    for i in range(-num_strikes, num_strikes + 1):
        k = atm_strike + i * lot_interval
        if k <= 0:
            continue

        moneyness = k / spot

        # IV Skew: put IV is higher for lower strikes (typical negative skew)
        # Call IV rises slightly for higher strikes
        if moneyness < 1.0:   # OTM puts → higher IV (smirk)
            skew_adj = (1.0 - moneyness) * 8.0
            call_iv  = max(atm_iv - abs(i) * 0.3, atm_iv * 0.8)
            put_iv   = atm_iv + skew_adj + abs(i) * 0.4
        else:                  # OTM calls → slightly lower IV
            call_iv  = max(atm_iv - abs(i) * 0.5, atm_iv * 0.7)
            put_iv   = max(atm_iv + abs(i) * 0.2, atm_iv)

        call_iv_dec = call_iv / 100.0
        put_iv_dec  = put_iv  / 100.0

        # Black-Scholes prices (simplified)
        call_ltp = _bs_call(spot, k, tte_years, r, call_iv_dec)
        put_ltp  = _bs_put( spot, k, tte_years, r, put_iv_dec)

        # Realistic OI distribution: peaks near ATM, declines further out
        oi_weight = math.exp(-0.5 * (i / 5) ** 2)  # Gaussian around ATM
        call_oi   = max(100, int(500_000 * oi_weight * (1 + 0.2 * (i > 0))))
        put_oi    = max(100, int(500_000 * oi_weight * (1 + 0.2 * (i < 0))))

        # OI changes (simulate build-up near ATM)
        call_oi_chg = int(call_oi * 0.05 * (1 if i >= 0 else -0.5))
        put_oi_chg  = int(put_oi  * 0.05 * (1 if i <= 0 else -0.5))

        # Gamma (higher near ATM)
        gamma = math.exp(-0.5 * (i / 3) ** 2) * 0.001

        opt = OptionStrike(
            strike          = k,
            expiry          = expiry,
            call_oi         = call_oi,
            call_oi_change  = call_oi_chg,
            call_volume     = int(call_oi * 0.3),
            call_iv         = round(call_iv, 2),
            call_ltp        = round(call_ltp, 2),
            call_gamma      = round(gamma, 6),
            call_delta      = round(max(0, min(1, 0.5 - i * 0.05)), 4),
            put_oi          = put_oi,
            put_oi_change   = put_oi_chg,
            put_volume      = int(put_oi * 0.25),
            put_iv          = round(put_iv, 2),
            put_ltp         = round(put_ltp, 2),
            put_gamma       = round(gamma, 6),
            put_delta       = round(max(-1, min(0, -0.5 - i * 0.05)), 4),
        )
        opt.total_oi   = opt.call_oi + opt.put_oi
        opt.pcr_oi     = round(opt.put_oi / opt.call_oi, 4) if opt.call_oi else 0.0
        opt.iv_skew    = round(opt.put_iv - opt.call_iv, 4)
        opt.oi_build_call = OIBuildType.LONG_BUILDUP if call_oi_chg > 0 else OIBuildType.SHORT_BUILDUP
        opt.oi_build_put  = OIBuildType.LONG_BUILDUP if put_oi_chg  > 0 else OIBuildType.SHORT_BUILDUP

        strikes.append(opt)

    total_call_oi  = sum(s.call_oi    for s in strikes)
    total_put_oi   = sum(s.put_oi     for s in strikes)
    total_call_vol = sum(s.call_volume for s in strikes)
    total_put_vol  = sum(s.put_volume  for s in strikes)
    atm_strike_obj = min(strikes, key=lambda s: abs(s.strike - spot))

    return ChainSnapshot(
        underlying       = symbol,
        spot_price       = spot,
        expiry           = expiry,
        timestamp        = datetime.now(timezone.utc),
        strikes          = strikes,
        lot_size         = lot_size,
        total_call_oi    = total_call_oi,
        total_put_oi     = total_put_oi,
        total_call_volume= total_call_vol,
        total_put_volume = total_put_vol,
        pcr_oi           = round(total_put_oi / total_call_oi, 4) if total_call_oi else 0,
        pcr_volume       = round(total_put_vol / total_call_vol, 4) if total_call_vol else 0,
        atm_strike       = atm_strike_obj.strike,
        atm_call_iv      = atm_strike_obj.call_iv,
        atm_put_iv       = atm_strike_obj.put_iv,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _classify_oi_build(ltp_change: float, oi_change: int) -> OIBuildType:
    """Classify OI build-up type from price and OI changes."""
    if oi_change > 0 and ltp_change >= 0:
        return OIBuildType.LONG_BUILDUP
    elif oi_change < 0 and ltp_change < 0:
        return OIBuildType.LONG_UNWINDING
    elif oi_change > 0 and ltp_change < 0:
        return OIBuildType.SHORT_BUILDUP
    elif oi_change < 0 and ltp_change >= 0:
        return OIBuildType.SHORT_COVERING
    return OIBuildType.NEUTRAL


def _bs_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes call price."""
    import math
    if T <= 0 or sigma <= 0:
        return max(0.0, S - K)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return round(S * _N(d1) - K * math.exp(-r * T) * _N(d2), 2)


def _bs_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes put price."""
    import math
    if T <= 0 or sigma <= 0:
        return max(0.0, K - S)
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return round(K * math.exp(-r * T) * _N(-d2) - S * _N(-d1), 2)


def _N(x: float) -> float:
    """Standard normal CDF."""
    import math
    return (1.0 + math.erf(x / math.sqrt(2))) / 2.0
