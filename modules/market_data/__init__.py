"""
NEXUS AI — Market Data Engine (Module 1)

Responsibilities:
- Ingest NIFTY Spot, Futures, Option Chain
- India VIX, Sector Indices, Constituent Stocks
- Historical OHLC (daily, minute candles)
- Live OHLC via polling (free providers)
- Tick data handler

Data Providers (all free, no API key required):
- yfinance         : Historical + semi-live quotes
- nsepython        : NSE India option chain and FII/DII data
- pandas-datareader: Additional free sources (FRED, Stooq)
- requests + BS4   : NSE/BSE direct page scraping

Phase 2 will implement all concrete providers.
"""

from .provider import DataProvider
from .yfinance_provider import YFinanceProvider
from .nse_provider import NSEProvider

__all__ = [
    "DataProvider",
    "YFinanceProvider",
    "NSEProvider",
]
