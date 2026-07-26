"""
NEXUS AI — Market Hours Engine (Module 1)

Determines if Indian markets are open, handles IST timezone,
market sessions, holidays, and expiry schedules.

NSE Trading Hours:
- Pre-market:  09:00–09:15 IST
- Regular:     09:15–15:30 IST
- Post-market: 15:40–16:00 IST
- Closed:      Saturday, Sunday, NSE holidays
"""

from datetime import date, datetime, time, timedelta
from enum import Enum
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


class MarketSession(str, Enum):
    PRE_OPEN   = "PRE_OPEN"    # 09:00–09:15
    OPEN       = "OPEN"        # 09:15–15:30
    POST_CLOSE = "POST_CLOSE"  # 15:30–16:00
    CLOSED     = "CLOSED"      # Outside hours or holiday


# ─── NSE Holiday Calendar 2025–2026 ───────────────────────────────────────────
# Source: NSE official holiday list
NSE_HOLIDAYS_2025: set[date] = {
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 3, 31),   # Id-ul-Fitr (Ramadan Eid)
    date(2025, 4, 10),   # Shri Ram Navami
    date(2025, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 1),    # Maharashtra Day
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Gandhi Jayanti
    date(2025, 10, 2),   # Dussehra
    date(2025, 10, 24),  # Diwali - Laxmi Puja
    date(2025, 10, 25),  # Diwali - Balipratipada
    date(2025, 11, 5),   # Prakash Gurpurb Sri Guru Nanak Dev Ji
    date(2025, 12, 25),  # Christmas
}

NSE_HOLIDAYS_2026: set[date] = {
    date(2026, 1, 26),   # Republic Day
    date(2026, 2, 17),   # Mahashivratri (tentative)
    date(2026, 3, 20),   # Holi (tentative)
    date(2026, 4, 3),    # Good Friday (tentative)
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 8, 15),   # Independence Day
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 11, 14),  # Diwali (tentative)
    date(2026, 12, 25),  # Christmas
}

NSE_HOLIDAYS: set[date] = NSE_HOLIDAYS_2025 | NSE_HOLIDAYS_2026

# NSE market session times (in IST)
_PRE_OPEN_START  = time(9,  0)
_MARKET_OPEN     = time(9, 15)
_MARKET_CLOSE    = time(15, 30)
_POST_CLOSE_END  = time(16,  0)

# Weekly expiry: Tuesday (weekday index 1) — effective from Sep 19, 2024
# NSE moved NIFTY 50 weekly expiry from Thursday to Tuesday (Sep 2024)
# BANKNIFTY remains on Wednesday (weekday index 2)
_NIFTY_WEEKLY_EXPIRY_DAY  = 1   # Tuesday
_BANKNIFTY_EXPIRY_DAY     = 2   # Wednesday
_FINNIFTY_EXPIRY_DAY      = 2   # Wednesday


def now_ist() -> datetime:
    """Current datetime in IST timezone."""
    return datetime.now(IST)


def today_ist() -> date:
    """Current date in IST timezone."""
    return now_ist().date()


def get_market_session(dt: datetime | None = None) -> MarketSession:
    """
    Determine the current (or given) NSE market session.

    Args:
        dt: Datetime to check. Defaults to now (IST).

    Returns:
        MarketSession enum value
    """
    if dt is None:
        dt = now_ist()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)

    dt_ist = dt.astimezone(IST)
    current_date = dt_ist.date()
    current_time = dt_ist.time()

    # Weekend check
    if current_date.weekday() >= 5:  # Saturday=5, Sunday=6
        return MarketSession.CLOSED

    # Holiday check
    if current_date in NSE_HOLIDAYS:
        return MarketSession.CLOSED

    # Session determination
    if _PRE_OPEN_START <= current_time < _MARKET_OPEN:
        return MarketSession.PRE_OPEN
    elif _MARKET_OPEN <= current_time < _MARKET_CLOSE:
        return MarketSession.OPEN
    elif _MARKET_CLOSE <= current_time < _POST_CLOSE_END:
        return MarketSession.POST_CLOSE
    else:
        return MarketSession.CLOSED


def is_market_open(dt: datetime | None = None) -> bool:
    """Returns True if NSE is in regular trading session."""
    return get_market_session(dt) == MarketSession.OPEN


def is_trading_day(check_date: date | None = None) -> bool:
    """Returns True if the given date is an NSE trading day."""
    if check_date is None:
        check_date = today_ist()
    return (
        check_date.weekday() < 5
        and check_date not in NSE_HOLIDAYS
    )


def minutes_to_close(dt: datetime | None = None) -> int:
    """
    Returns minutes remaining until market close.
    Returns 0 if market is already closed.
    """
    if dt is None:
        dt = now_ist()
    dt_ist = dt.astimezone(IST)
    close_today = datetime(
        dt_ist.year, dt_ist.month, dt_ist.day,
        _MARKET_CLOSE.hour, _MARKET_CLOSE.minute,
        tzinfo=IST
    )
    remaining = (close_today - dt_ist).total_seconds() / 60
    return max(0, int(remaining))


def is_expiry_day(check_date: date | None = None, index: str = "NIFTY") -> bool:
    """
    Returns True if the given date is a weekly expiry day.

    NIFTY 50  : Tuesday (moved from Thursday on Sep 19, 2024)
    BANKNIFTY : Wednesday
    FINNIFTY  : Wednesday
    """
    if check_date is None:
        check_date = today_ist()

    expiry_weekday = (
        _BANKNIFTY_EXPIRY_DAY
        if index.upper() in ("BANKNIFTY", "FINNIFTY")
        else _NIFTY_WEEKLY_EXPIRY_DAY
    )

    if check_date.weekday() == expiry_weekday:
        return check_date not in NSE_HOLIDAYS

    # If the expiry weekday is a holiday, expiry shifts to the previous trading day
    if check_date.weekday() == (expiry_weekday - 1):  # day before expiry
        next_day = check_date + timedelta(days=1)
        return next_day in NSE_HOLIDAYS

    return False


def next_expiry_date(from_date: date | None = None, index: str = "NIFTY") -> date:
    """
    Returns the next weekly expiry date for the given index.

    NIFTY 50  : Tuesday  (effective Sep 19, 2024)
    BANKNIFTY : Wednesday
    FINNIFTY  : Wednesday

    If the expiry day is a holiday, shifts to the previous trading day.
    """
    if from_date is None:
        from_date = today_ist()

    expiry_weekday = (
        _BANKNIFTY_EXPIRY_DAY
        if index.upper() in ("BANKNIFTY", "FINNIFTY")
        else _NIFTY_WEEKLY_EXPIRY_DAY
    )

    # Find next occurrence of expiry_weekday
    days_ahead = expiry_weekday - from_date.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    expiry = from_date + timedelta(days=days_ahead)

    # Shift back to previous trading day if expiry is a holiday
    while expiry in NSE_HOLIDAYS or expiry.weekday() >= 5:
        expiry -= timedelta(days=1)

    return expiry


def time_to_expiry_years(expiry: date, from_dt: datetime | None = None) -> float:
    """
    Calculate time to expiry in years, accounting for trading hours.
    Uses actual calendar time (not trading time) for simplicity.

    Args:
        expiry   : Expiry date
        from_dt  : Reference datetime (default: now IST)

    Returns:
        Time to expiry in years (decimal). Minimum: 1 hour.
    """
    if from_dt is None:
        from_dt = now_ist()

    # Options expire at 15:30 IST on expiry day
    expiry_dt = datetime(
        expiry.year, expiry.month, expiry.day, 15, 30, tzinfo=IST
    )

    if from_dt.tzinfo is None:
        from_dt = from_dt.replace(tzinfo=IST)

    delta_seconds = (expiry_dt - from_dt).total_seconds()
    delta_years   = max(delta_seconds / (365.25 * 24 * 3600), 1 / (365 * 24))
    return delta_years


def market_status_summary() -> dict:
    """Returns a comprehensive market status dictionary."""
    now = now_ist()
    session = get_market_session(now)
    expiry_today = is_expiry_day(now.date())
    next_expiry  = next_expiry_date(now.date())
    mins_to_close = minutes_to_close(now) if session == MarketSession.OPEN else 0

    return {
        "session":              session.value,
        "is_open":              session == MarketSession.OPEN,
        "is_trading_day":       is_trading_day(now.date()),
        "is_expiry_day":        expiry_today,
        "ist_time":             now.strftime("%H:%M:%S"),
        "ist_date":             now.date().isoformat(),
        "minutes_to_close":     mins_to_close,
        "next_nifty_expiry":    next_expiry_date(now.date(), "NIFTY").isoformat(),
        "next_banknifty_expiry": next_expiry_date(now.date(), "BANKNIFTY").isoformat(),
        "days_to_next_expiry":  (next_expiry_date(now.date()) - now.date()).days,
        "nifty_expiry_day":     "Tuesday",
        "banknifty_expiry_day": "Wednesday",
    }
