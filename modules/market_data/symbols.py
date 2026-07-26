"""
NEXUS AI — Symbol Registry (Module 1)

Central registry for all traded symbols, their Yahoo Finance tickers,
sector classifications, and metadata.

Covers:
- NIFTY 50 constituents (50 stocks)
- NIFTY sector indices (13 indices)
- Global indices (9 major markets)
- Macro instruments (Crude, Gold, DXY, USDINR, Bond Yields)
- Crypto (BTC, ETH)
"""

from dataclasses import dataclass, field
from enum import Enum


class AssetClass(str, Enum):
    EQUITY_INDEX   = "equity_index"
    EQUITY_STOCK   = "equity_stock"
    VOLATILITY     = "volatility"
    COMMODITY      = "commodity"
    FX             = "fx"
    FIXED_INCOME   = "fixed_income"
    CRYPTO         = "crypto"
    GLOBAL_INDEX   = "global_index"


class Sector(str, Enum):
    FINANCIAL      = "Financial Services"
    IT             = "Information Technology"
    OIL_GAS        = "Oil & Gas"
    FMCG           = "FMCG"
    AUTO           = "Automobile"
    METALS         = "Metals"
    PHARMA         = "Pharmaceuticals"
    TELECOM        = "Telecom"
    INFRA          = "Infrastructure"
    ENERGY         = "Energy"
    HEALTHCARE     = "Healthcare"
    CEMENT         = "Cement"
    CONSUMER       = "Consumer Goods"
    REALTY         = "Realty"
    DIVERSIFIED    = "Diversified"
    UNKNOWN        = "Unknown"


@dataclass
class SymbolInfo:
    """Complete metadata for a tradeable instrument."""
    nexus_id:       str           # NEXUS internal ID (e.g. "RELIANCE")
    yf_ticker:      str           # Yahoo Finance ticker (e.g. "RELIANCE.NS")
    display_name:   str           # Human-readable name
    asset_class:    AssetClass
    sector:         Sector = Sector.UNKNOWN
    nse_symbol:     str = ""      # NSE trading symbol
    is_nifty50:     bool = False  # Member of NIFTY 50 index
    lot_size:       int = 1       # Derivatives lot size
    exchange:       str = "NSE"


# ─── NIFTY 50 Index ───────────────────────────────────────────────────────────
NIFTY_INDEX = SymbolInfo(
    nexus_id="NIFTY", yf_ticker="^NSEI",
    display_name="NIFTY 50",
    asset_class=AssetClass.EQUITY_INDEX,
    nse_symbol="NIFTY", lot_size=75,
)

BANKNIFTY_INDEX = SymbolInfo(
    nexus_id="BANKNIFTY", yf_ticker="^NSEBANK",
    display_name="NIFTY Bank",
    asset_class=AssetClass.EQUITY_INDEX,
    nse_symbol="BANKNIFTY", lot_size=15,
)

INDIA_VIX = SymbolInfo(
    nexus_id="VIX", yf_ticker="^INDIAVIX",
    display_name="India VIX",
    asset_class=AssetClass.VOLATILITY,
    nse_symbol="INDIAVIX",
)

# ─── NIFTY 50 Constituents ────────────────────────────────────────────────────
NIFTY50_STOCKS: list[SymbolInfo] = [
    SymbolInfo("RELIANCE",   "RELIANCE.NS",   "Reliance Industries",       AssetClass.EQUITY_STOCK, Sector.OIL_GAS,     "RELIANCE",   True, 250),
    SymbolInfo("TCS",        "TCS.NS",        "Tata Consultancy Services", AssetClass.EQUITY_STOCK, Sector.IT,          "TCS",        True, 150),
    SymbolInfo("HDFCBANK",   "HDFCBANK.NS",   "HDFC Bank",                 AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "HDFCBANK",   True, 550),
    SymbolInfo("INFY",       "INFY.NS",       "Infosys",                   AssetClass.EQUITY_STOCK, Sector.IT,          "INFY",       True, 400),
    SymbolInfo("ICICIBANK",  "ICICIBANK.NS",  "ICICI Bank",                AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "ICICIBANK",  True, 700),
    SymbolInfo("HINDUNILVR", "HINDUNILVR.NS", "Hindustan Unilever",        AssetClass.EQUITY_STOCK, Sector.FMCG,        "HINDUNILVR", True, 300),
    SymbolInfo("ITC",        "ITC.NS",        "ITC Limited",               AssetClass.EQUITY_STOCK, Sector.FMCG,        "ITC",        True, 3200),
    SymbolInfo("SBIN",       "SBIN.NS",       "State Bank of India",       AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "SBIN",       True, 1500),
    SymbolInfo("BAJFINANCE", "BAJFINANCE.NS", "Bajaj Finance",             AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "BAJFINANCE", True, 125),
    SymbolInfo("BHARTIARTL", "BHARTIARTL.NS", "Bharti Airtel",             AssetClass.EQUITY_STOCK, Sector.TELECOM,     "BHARTIARTL", True, 950),
    SymbolInfo("KOTAKBANK",  "KOTAKBANK.NS",  "Kotak Mahindra Bank",       AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "KOTAKBANK",  True, 400),
    SymbolInfo("LT",         "LT.NS",         "Larsen & Toubro",           AssetClass.EQUITY_STOCK, Sector.INFRA,       "LT",         True, 450),
    SymbolInfo("HCLTECH",    "HCLTECH.NS",    "HCL Technologies",          AssetClass.EQUITY_STOCK, Sector.IT,          "HCLTECH",    True, 700),
    SymbolInfo("AXISBANK",   "AXISBANK.NS",   "Axis Bank",                 AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "AXISBANK",   True, 1200),
    SymbolInfo("ASIANPAINT", "ASIANPAINT.NS", "Asian Paints",              AssetClass.EQUITY_STOCK, Sector.CONSUMER,    "ASIANPAINT", True, 200),
    SymbolInfo("MARUTI",     "MARUTI.NS",     "Maruti Suzuki",             AssetClass.EQUITY_STOCK, Sector.AUTO,        "MARUTI",     True, 100),
    SymbolInfo("TITAN",      "TITAN.NS",      "Titan Company",             AssetClass.EQUITY_STOCK, Sector.CONSUMER,    "TITAN",      True, 375),
    SymbolInfo("WIPRO",      "WIPRO.NS",      "Wipro",                     AssetClass.EQUITY_STOCK, Sector.IT,          "WIPRO",      True, 1500),
    SymbolInfo("SUNPHARMA",  "SUNPHARMA.NS",  "Sun Pharmaceutical",        AssetClass.EQUITY_STOCK, Sector.PHARMA,      "SUNPHARMA",  True, 700),
    SymbolInfo("ULTRACEMCO", "ULTRACEMCO.NS", "UltraTech Cement",          AssetClass.EQUITY_STOCK, Sector.CEMENT,      "ULTRACEMCO", True, 100),
    SymbolInfo("BAJAJFINSV", "BAJAJFINSV.NS", "Bajaj Finserv",             AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "BAJAJFINSV", True, 500),
    SymbolInfo("ONGC",       "ONGC.NS",       "ONGC",                      AssetClass.EQUITY_STOCK, Sector.OIL_GAS,     "ONGC",       True, 1925),
    SymbolInfo("NTPC",       "NTPC.NS",       "NTPC",                      AssetClass.EQUITY_STOCK, Sector.ENERGY,      "NTPC",       True, 2875),
    SymbolInfo("POWERGRID",  "POWERGRID.NS",  "Power Grid Corporation",    AssetClass.EQUITY_STOCK, Sector.ENERGY,      "POWERGRID",  True, 2750),
    SymbolInfo("M&M",        "M&M.NS",        "Mahindra & Mahindra",       AssetClass.EQUITY_STOCK, Sector.AUTO,        "M&M",        True, 700),
    SymbolInfo("ADANIENT",   "ADANIENT.NS",   "Adani Enterprises",         AssetClass.EQUITY_STOCK, Sector.DIVERSIFIED, "ADANIENT",   True, 500),
    SymbolInfo("ADANIPORTS", "ADANIPORTS.NS", "Adani Ports & SEZ",         AssetClass.EQUITY_STOCK, Sector.INFRA,       "ADANIPORTS", True, 625),
    SymbolInfo("COALINDIA",  "COALINDIA.NS",  "Coal India",                AssetClass.EQUITY_STOCK, Sector.ENERGY,      "COALINDIA",  True, 4200),
    SymbolInfo("JSWSTEEL",   "JSWSTEEL.NS",   "JSW Steel",                 AssetClass.EQUITY_STOCK, Sector.METALS,      "JSWSTEEL",   True, 600),
    SymbolInfo("TATASTEEL",  "TATASTEEL.NS",  "Tata Steel",                AssetClass.EQUITY_STOCK, Sector.METALS,      "TATASTEEL",  True, 5500),
    SymbolInfo("INDUSINDBK", "INDUSINDBK.NS", "IndusInd Bank",             AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "INDUSINDBK", True, 500),
    SymbolInfo("TATAMOTORS", "TATAMOTORS.NS", "Tata Motors",               AssetClass.EQUITY_STOCK, Sector.AUTO,        "TATAMOTORS", True, 2750),
    SymbolInfo("TECHM",      "TECHM.NS",      "Tech Mahindra",             AssetClass.EQUITY_STOCK, Sector.IT,          "TECHM",      True, 600),
    SymbolInfo("GRASIM",     "GRASIM.NS",     "Grasim Industries",         AssetClass.EQUITY_STOCK, Sector.DIVERSIFIED, "GRASIM",     True, 250),
    SymbolInfo("BPCL",       "BPCL.NS",       "Bharat Petroleum",          AssetClass.EQUITY_STOCK, Sector.OIL_GAS,     "BPCL",       True, 1800),
    SymbolInfo("CIPLA",      "CIPLA.NS",      "Cipla",                     AssetClass.EQUITY_STOCK, Sector.PHARMA,      "CIPLA",      True, 650),
    SymbolInfo("EICHERMOT",  "EICHERMOT.NS",  "Eicher Motors",             AssetClass.EQUITY_STOCK, Sector.AUTO,        "EICHERMOT",  True, 200),
    SymbolInfo("DRREDDY",    "DRREDDY.NS",    "Dr. Reddy's Laboratories",  AssetClass.EQUITY_STOCK, Sector.PHARMA,      "DRREDDY",    True, 250),
    SymbolInfo("APOLLOHOSP", "APOLLOHOSP.NS", "Apollo Hospitals",          AssetClass.EQUITY_STOCK, Sector.HEALTHCARE,  "APOLLOHOSP", True, 250),
    SymbolInfo("HINDALCO",   "HINDALCO.NS",   "Hindalco Industries",       AssetClass.EQUITY_STOCK, Sector.METALS,      "HINDALCO",   True, 2750),
    SymbolInfo("TATACONSUM", "TATACONSUM.NS", "Tata Consumer Products",    AssetClass.EQUITY_STOCK, Sector.FMCG,        "TATACONSUM", True, 1100),
    SymbolInfo("DIVISLAB",   "DIVISLAB.NS",   "Divi's Laboratories",       AssetClass.EQUITY_STOCK, Sector.PHARMA,      "DIVISLAB",   True, 300),
    SymbolInfo("BRITANNIA",  "BRITANNIA.NS",  "Britannia Industries",      AssetClass.EQUITY_STOCK, Sector.FMCG,        "BRITANNIA",  True, 200),
    SymbolInfo("BAJAJ-AUTO", "BAJAJ-AUTO.NS", "Bajaj Auto",                AssetClass.EQUITY_STOCK, Sector.AUTO,        "BAJAJ-AUTO", True, 250),
    SymbolInfo("HEROMOTOCO", "HEROMOTOCO.NS", "Hero MotoCorp",             AssetClass.EQUITY_STOCK, Sector.AUTO,        "HEROMOTOCO", True, 300),
    SymbolInfo("SHREECEM",   "SHREECEM.NS",   "Shree Cement",              AssetClass.EQUITY_STOCK, Sector.CEMENT,      "SHREECEM",   True,  50),
    SymbolInfo("NESTLEIND",  "NESTLEIND.NS",  "Nestle India",              AssetClass.EQUITY_STOCK, Sector.FMCG,        "NESTLEIND",  True, 150),
    SymbolInfo("SBILIFE",    "SBILIFE.NS",    "SBI Life Insurance",        AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "SBILIFE",    True, 750),
    SymbolInfo("HDFCLIFE",   "HDFCLIFE.NS",   "HDFC Life Insurance",       AssetClass.EQUITY_STOCK, Sector.FINANCIAL,   "HDFCLIFE",   True, 1100),
    SymbolInfo("UPL",        "UPL.NS",        "UPL Limited",               AssetClass.EQUITY_STOCK, Sector.UNKNOWN,     "UPL",        True, 1300),
]

# ─── Sector Indices ───────────────────────────────────────────────────────────
SECTOR_INDICES: list[SymbolInfo] = [
    SymbolInfo("NIFTYIT",      "^CNXIT",     "NIFTY IT",           AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYBANK",    "^NSEBANK",   "NIFTY Bank",         AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYPHARMA",  "^CNXPHARMA", "NIFTY Pharma",       AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYFMCG",    "^CNXFMCG",   "NIFTY FMCG",         AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYAUTO",    "^CNXAUTO",   "NIFTY Auto",         AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYMETAL",   "^CNXMETAL",  "NIFTY Metal",        AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYENERGY",  "^CNXENERGY", "NIFTY Energy",       AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYINFRA",   "^CNXINFRA",  "NIFTY Infrastructure", AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYREALTY",  "^CNXREALTY", "NIFTY Realty",       AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYMIDCAP",  "^CNXMIDCAP", "NIFTY Midcap 50",    AssetClass.EQUITY_INDEX),
    SymbolInfo("NIFTYSMALL",   "^CNXSC",     "NIFTY Smallcap 100", AssetClass.EQUITY_INDEX),
    SymbolInfo("SENSEX",       "^BSESN",     "BSE SENSEX",         AssetClass.EQUITY_INDEX),
    SymbolInfo("GIFTNIFTY",    "NIFTY.NS",   "GIFT NIFTY",         AssetClass.EQUITY_INDEX),
]

# ─── Global Markets ───────────────────────────────────────────────────────────
GLOBAL_INDICES: list[SymbolInfo] = [
    SymbolInfo("SP500",     "^GSPC",     "S&P 500",       AssetClass.GLOBAL_INDEX, exchange="NYSE"),
    SymbolInfo("NASDAQ",    "^IXIC",     "NASDAQ",        AssetClass.GLOBAL_INDEX, exchange="NASDAQ"),
    SymbolInfo("DOWJONES",  "^DJI",      "Dow Jones",     AssetClass.GLOBAL_INDEX, exchange="NYSE"),
    SymbolInfo("FTSE",      "^FTSE",     "FTSE 100",      AssetClass.GLOBAL_INDEX, exchange="LSE"),
    SymbolInfo("DAX",       "^GDAXI",    "DAX",           AssetClass.GLOBAL_INDEX, exchange="XETRA"),
    SymbolInfo("NIKKEI",    "^N225",     "Nikkei 225",    AssetClass.GLOBAL_INDEX, exchange="TSE"),
    SymbolInfo("HANGSENG",  "^HSI",      "Hang Seng",     AssetClass.GLOBAL_INDEX, exchange="HKEX"),
    SymbolInfo("GLOBALVIX", "^VIX",      "CBOE VIX",      AssetClass.VOLATILITY,   exchange="CBOE"),
    SymbolInfo("SGX",       "ES=F",      "S&P 500 Future",AssetClass.GLOBAL_INDEX, exchange="SGX"),
]

# ─── Macro Instruments ────────────────────────────────────────────────────────
MACRO_INSTRUMENTS: list[SymbolInfo] = [
    SymbolInfo("CRUDE_OIL",    "CL=F",      "Crude Oil (WTI)",   AssetClass.COMMODITY),
    SymbolInfo("BRENT_CRUDE",  "BZ=F",      "Brent Crude",       AssetClass.COMMODITY),
    SymbolInfo("NATURAL_GAS",  "NG=F",      "Natural Gas",       AssetClass.COMMODITY),
    SymbolInfo("GOLD",         "GC=F",      "Gold",              AssetClass.COMMODITY),
    SymbolInfo("SILVER",       "SI=F",      "Silver",            AssetClass.COMMODITY),
    SymbolInfo("DXY",          "DX-Y.NYB",  "US Dollar Index",   AssetClass.FX),
    SymbolInfo("USDINR",       "USDINR=X",  "USD/INR",           AssetClass.FX),
    SymbolInfo("EURUSD",       "EURUSD=X",  "EUR/USD",           AssetClass.FX),
    SymbolInfo("US_10Y",       "^TNX",      "US 10Y Bond Yield", AssetClass.FIXED_INCOME),
    SymbolInfo("US_2Y",        "^IRX",      "US 2Y Bond Yield",  AssetClass.FIXED_INCOME),
    SymbolInfo("BITCOIN",      "BTC-USD",   "Bitcoin",           AssetClass.CRYPTO),
    SymbolInfo("ETHEREUM",     "ETH-USD",   "Ethereum",          AssetClass.CRYPTO),
]


# ─── Symbol Registry ──────────────────────────────────────────────────────────

class SymbolRegistry:
    """
    Central lookup service for all symbols.
    Provides O(1) lookup by NEXUS ID or Yahoo Finance ticker.
    """

    def __init__(self):
        self._by_nexus_id:  dict[str, SymbolInfo] = {}
        self._by_yf_ticker: dict[str, SymbolInfo] = {}

        all_symbols = (
            [NIFTY_INDEX, BANKNIFTY_INDEX, INDIA_VIX]
            + NIFTY50_STOCKS
            + SECTOR_INDICES
            + GLOBAL_INDICES
            + MACRO_INSTRUMENTS
        )
        for sym in all_symbols:
            self._by_nexus_id[sym.nexus_id.upper()]   = sym
            self._by_yf_ticker[sym.yf_ticker.upper()]  = sym

    def get(self, nexus_id: str) -> SymbolInfo | None:
        return self._by_nexus_id.get(nexus_id.upper())

    def get_by_yf(self, ticker: str) -> SymbolInfo | None:
        return self._by_yf_ticker.get(ticker.upper())

    def nifty50_tickers(self) -> list[str]:
        """Return Yahoo Finance tickers for all NIFTY 50 constituents."""
        return [s.yf_ticker for s in NIFTY50_STOCKS]

    def nifty50_nexus_ids(self) -> list[str]:
        """Return NEXUS IDs for all NIFTY 50 constituents."""
        return [s.nexus_id for s in NIFTY50_STOCKS]

    def all_symbols(self) -> list[SymbolInfo]:
        return list(self._by_nexus_id.values())


# ── Singleton registry ─────────────────────────────────────────────────────────
registry = SymbolRegistry()
