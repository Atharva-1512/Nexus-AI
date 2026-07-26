"""
NEXUS AI — FII/DII Flow Tracker (Module 1)

Fetches and parses Foreign Institutional Investor (FII) and
Domestic Institutional Investor (DII) daily buy/sell data from NSE India.

FII/DII flows are a key macro signal:
  - FII net buying  → Bullish (foreign money flowing in)
  - FII net selling → Bearish (foreign money flowing out)
  - DII buying into FII selling → Support / floor signal

Data source: NSE India website (free, no API key)
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_NSE_FII_DII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*",
    "Referer": "https://www.nseindia.com",
}


@dataclass
class FIIDIIFlow:
    """FII and DII cash market flow for a single trading day."""
    date:        date
    # FII
    fii_buy:     float    # INR Crores
    fii_sell:    float
    fii_net:     float    # Positive = net buying
    # DII
    dii_buy:     float
    dii_sell:    float
    dii_net:     float    # Positive = net buying
    # Combined
    total_net:   float    # FII net + DII net

    @property
    def is_fii_buying(self) -> bool:
        return self.fii_net > 0

    @property
    def is_bullish(self) -> bool:
        """True if both FII and DII are net buyers."""
        return self.fii_net > 0 and self.dii_net > 0

    @property
    def signal_strength(self) -> str:
        """Returns a human-readable signal from FII/DII flows."""
        if self.fii_net > 1000:
            return "STRONG_BUY"
        elif self.fii_net > 200:
            return "BUY"
        elif self.fii_net < -1000:
            return "STRONG_SELL"
        elif self.fii_net < -200:
            return "SELL"
        else:
            return "NEUTRAL"

    def to_dict(self) -> dict:
        return {
            "date":         self.date.isoformat(),
            "fii_buy":      self.fii_buy,
            "fii_sell":     self.fii_sell,
            "fii_net":      self.fii_net,
            "dii_buy":      self.dii_buy,
            "dii_sell":     self.dii_sell,
            "dii_net":      self.dii_net,
            "total_net":    self.total_net,
            "signal":       self.signal_strength,
            "is_fii_buying": self.is_fii_buying,
        }


class FIIDIITracker:
    """
    Fetches and caches FII/DII institutional flow data from NSE India.

    Data is available after market close (~16:30 IST) for that trading day.
    Updates once per trading day, so cache TTL can be 30 minutes.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update(_NSE_HEADERS)
        self._session_ready = False

    def _ensure_session(self) -> None:
        if not self._session_ready:
            try:
                self._session.get("https://www.nseindia.com", timeout=10)
                self._session_ready = True
            except Exception as e:
                logger.warning(f"NSE session init failed for FII/DII tracker: {e}")

    def fetch_latest(self) -> Optional[FIIDIIFlow]:
        """
        Fetch the most recent FII/DII data from NSE.

        Returns:
            FIIDIIFlow for the latest available trading day,
            or None if data is unavailable.
        """
        self._ensure_session()

        try:
            response = self._session.get(_NSE_FII_DII_URL, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"FII/DII fetch failed: {e}")
            return None

        # NSE returns a list; first entry is the most recent
        records = data if isinstance(data, list) else data.get("data", [])
        if not records:
            logger.warning("FII/DII API returned empty data")
            return None

        return self._parse_record(records[0])

    def fetch_history(self, days: int = 30) -> list[FIIDIIFlow]:
        """
        Fetch the last N days of FII/DII data.

        Args:
            days: Number of trading days to fetch

        Returns:
            List of FIIDIIFlow, most recent first
        """
        self._ensure_session()

        try:
            response = self._session.get(_NSE_FII_DII_URL, timeout=15)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            logger.error(f"FII/DII history fetch failed: {e}")
            return []

        records = data if isinstance(data, list) else data.get("data", [])
        result  = []

        for record in records[:days]:
            parsed = self._parse_record(record)
            if parsed:
                result.append(parsed)

        return result

    def _parse_record(self, record: dict) -> Optional[FIIDIIFlow]:
        """Parse a single NSE FII/DII API record."""
        try:
            # NSE field names vary — try multiple possible keys
            def safe_float(val) -> float:
                if val is None or val == "-" or val == "":
                    return 0.0
                return float(str(val).replace(",", "").strip())

            date_str = record.get("date", record.get("Date", ""))
            trade_date = (
                datetime.strptime(date_str, "%d-%b-%Y").date()
                if date_str else date.today()
            )

            fii_buy  = safe_float(record.get("fiiBuyValue",  record.get("FII_BUY",  0)))
            fii_sell = safe_float(record.get("fiiSellValue", record.get("FII_SELL", 0)))
            dii_buy  = safe_float(record.get("diiBuyValue",  record.get("DII_BUY",  0)))
            dii_sell = safe_float(record.get("diiSellValue", record.get("DII_SELL", 0)))

            fii_net  = fii_buy  - fii_sell
            dii_net  = dii_buy  - dii_sell

            return FIIDIIFlow(
                date=trade_date,
                fii_buy=round(fii_buy,  2),
                fii_sell=round(fii_sell, 2),
                fii_net=round(fii_net,  2),
                dii_buy=round(dii_buy,  2),
                dii_sell=round(dii_sell, 2),
                dii_net=round(dii_net,  2),
                total_net=round(fii_net + dii_net, 2),
            )
        except Exception as e:
            logger.warning(f"Failed to parse FII/DII record {record}: {e}")
            return None

    def get_rolling_signal(self, flows: list[FIIDIIFlow], window: int = 5) -> dict:
        """
        Compute rolling FII/DII signal over the last N days.

        Args:
            flows:  List of FIIDIIFlow (most recent first)
            window: Number of days for the rolling window

        Returns:
            Dict with rolling net, signal direction, and momentum
        """
        if not flows:
            return {"signal": "UNKNOWN", "fii_rolling_net": 0, "dii_rolling_net": 0}

        recent = flows[:window]
        fii_rolling = sum(f.fii_net for f in recent)
        dii_rolling = sum(f.dii_net for f in recent)
        total_rolling = fii_rolling + dii_rolling

        if fii_rolling > 2000:
            signal = "STRONG_BUY"
        elif fii_rolling > 500:
            signal = "BUY"
        elif fii_rolling < -2000:
            signal = "STRONG_SELL"
        elif fii_rolling < -500:
            signal = "SELL"
        else:
            signal = "NEUTRAL"

        return {
            "signal":           signal,
            "fii_rolling_net":  round(fii_rolling, 2),
            "dii_rolling_net":  round(dii_rolling, 2),
            "total_rolling_net":round(total_rolling, 2),
            "window_days":      len(recent),
            "latest_date":      recent[0].date.isoformat() if recent else None,
        }
