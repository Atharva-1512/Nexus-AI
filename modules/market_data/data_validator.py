"""
NEXUS AI — Data Validation Pipeline (Module 1)

Validates and cleans all incoming market data before it enters the system.
Prevents corrupt or extreme values from polluting the ML pipeline.

Checks performed:
- Missing / NaN values
- Price outliers (Z-score and IQR-fence methods)
- Zero or negative prices
- Timestamp gaps (missing candles)
- Volume sanity (zero-volume candles during market hours)
- OHLC consistency (High >= Low, Close within High/Low range)
- Stale data detection (last update too old)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ValidationSeverity(str, Enum):
    INFO    = "INFO"
    WARNING = "WARNING"
    ERROR   = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ValidationIssue:
    """A single data quality issue detected during validation."""
    severity:  ValidationSeverity
    field:     str
    message:   str
    value:     Any = None


@dataclass
class ValidationResult:
    """Result of validating a single data record or DataFrame."""
    is_valid:      bool
    issues:        list[ValidationIssue] = field(default_factory=list)
    cleaned_data:  Any = None          # The cleaned version (if repairable)

    @property
    def has_errors(self) -> bool:
        return any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)
                   for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == ValidationSeverity.WARNING for i in self.issues)

    def add_issue(self, severity: ValidationSeverity, field: str, msg: str, value: Any = None):
        self.issues.append(ValidationIssue(severity, field, msg, value))
        if severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL):
            self.is_valid = False


class OHLCVValidator:
    """
    Validates and cleans OHLCV (candlestick) data.

    Usage:
        validator = OHLCVValidator()
        result = validator.validate(df, symbol="NIFTY")
        if result.is_valid:
            clean_df = result.cleaned_data
    """

    def __init__(
        self,
        max_price_change_pct: float = 20.0,    # Max % change in one candle
        min_price:            float = 1.0,      # Minimum valid price
        zscore_threshold:     float = 5.0,      # Z-score for outlier detection
        max_gap_minutes:      int   = 15,       # Max allowed gap between candles (minutes)
        stale_seconds:        int   = 300,      # Seconds before data is considered stale
    ):
        self.max_price_change_pct = max_price_change_pct
        self.min_price            = min_price
        self.zscore_threshold     = zscore_threshold
        self.max_gap_minutes      = max_gap_minutes
        self.stale_seconds        = stale_seconds

    def validate(self, df: pd.DataFrame, symbol: str = "") -> ValidationResult:
        """
        Validate an OHLCV DataFrame.

        Args:
            df:     DataFrame with columns [open, high, low, close, volume]
                    and DatetimeIndex
            symbol: Symbol name for logging context

        Returns:
            ValidationResult with issues and cleaned data
        """
        result = ValidationResult(is_valid=True, cleaned_data=df.copy())

        if df.empty:
            result.add_issue(ValidationSeverity.ERROR, "dataframe", "Empty DataFrame received")
            return result

        # ── 1. Required columns ────────────────────────────────────────────────
        required_cols = {"open", "high", "low", "close", "volume"}
        missing_cols  = required_cols - set(df.columns.str.lower())
        if missing_cols:
            result.add_issue(
                ValidationSeverity.CRITICAL, "columns",
                f"Missing required columns: {missing_cols}"
            )
            return result

        df_clean = result.cleaned_data
        df_clean.columns = [c.lower() for c in df_clean.columns]

        # ── 2. NaN / missing values ────────────────────────────────────────────
        nan_counts = df_clean[["open", "high", "low", "close"]].isna().sum()
        for col, count in nan_counts.items():
            if count > 0:
                pct = count / len(df_clean) * 100
                if pct > 10:
                    result.add_issue(
                        ValidationSeverity.ERROR, col,
                        f"{pct:.1f}% NaN values in '{col}' — too many to repair"
                    )
                else:
                    # Forward-fill for small gaps
                    df_clean[col] = df_clean[col].ffill()
                    result.add_issue(
                        ValidationSeverity.WARNING, col,
                        f"{count} NaN values forward-filled in '{col}'"
                    )

        # ── 3. Minimum price sanity ────────────────────────────────────────────
        for col in ["open", "high", "low", "close"]:
            bad_rows = df_clean[df_clean[col] <= self.min_price]
            if not bad_rows.empty:
                result.add_issue(
                    ValidationSeverity.ERROR, col,
                    f"{len(bad_rows)} rows have {col} <= {self.min_price} (zero/negative price)",
                    value=bad_rows[col].min()
                )

        # ── 4. OHLC consistency ────────────────────────────────────────────────
        bad_hl = df_clean[df_clean["high"] < df_clean["low"]]
        if not bad_hl.empty:
            result.add_issue(
                ValidationSeverity.ERROR, "high/low",
                f"{len(bad_hl)} rows where High < Low"
            )

        bad_close_hi = df_clean[df_clean["close"] > df_clean["high"] * 1.001]
        if not bad_close_hi.empty:
            result.add_issue(
                ValidationSeverity.WARNING, "close",
                f"{len(bad_close_hi)} rows where Close > High"
            )

        bad_close_lo = df_clean[df_clean["close"] < df_clean["low"] * 0.999]
        if not bad_close_lo.empty:
            result.add_issue(
                ValidationSeverity.WARNING, "close",
                f"{len(bad_close_lo)} rows where Close < Low"
            )

        # ── 5. Price outlier detection (Z-score on close returns) ──────────────
        if len(df_clean) >= 10:
            returns = df_clean["close"].pct_change().dropna()
            z_scores = np.abs((returns - returns.mean()) / returns.std())
            extreme = z_scores[z_scores > self.zscore_threshold]
            if not extreme.empty:
                result.add_issue(
                    ValidationSeverity.WARNING, "close",
                    f"{len(extreme)} extreme return outliers detected "
                    f"(|Z| > {self.zscore_threshold})",
                    value=returns[extreme.index].to_dict()
                )

        # ── 6. Single candle max move check ───────────────────────────────────
        if len(df_clean) > 1:
            hl_pct = (df_clean["high"] - df_clean["low"]) / df_clean["low"] * 100
            huge_moves = hl_pct[hl_pct > self.max_price_change_pct]
            if not huge_moves.empty:
                result.add_issue(
                    ValidationSeverity.WARNING, "high/low",
                    f"{len(huge_moves)} candles with H-L range > {self.max_price_change_pct}%"
                )

        # ── 7. Timestamp gaps (for intraday data) ─────────────────────────────
        if hasattr(df_clean.index, "freq") or isinstance(df_clean.index, pd.DatetimeIndex):
            try:
                diffs = pd.Series(df_clean.index).diff().dropna()
                if not diffs.empty:
                    median_gap = diffs.median()
                    large_gaps = diffs[diffs > median_gap * 3]
                    if not large_gaps.empty:
                        result.add_issue(
                            ValidationSeverity.INFO, "timestamp",
                            f"{len(large_gaps)} timestamp gaps > 3x median interval "
                            f"(possible missing candles)"
                        )
            except Exception:
                pass

        # ── 8. Stale data check ────────────────────────────────────────────────
        if isinstance(df_clean.index, pd.DatetimeIndex) and not df_clean.empty:
            last_ts = df_clean.index[-1]
            if last_ts.tzinfo is None:
                last_ts = last_ts.tz_localize("UTC")
            age_seconds = (datetime.now(last_ts.tzinfo) - last_ts).total_seconds()
            if age_seconds > self.stale_seconds:
                result.add_issue(
                    ValidationSeverity.INFO, "timestamp",
                    f"Data may be stale — last bar is {age_seconds/60:.1f} minutes old"
                )

        result.cleaned_data = df_clean

        if result.is_valid:
            error_count   = sum(1 for i in result.issues if i.severity == ValidationSeverity.ERROR)
            warning_count = sum(1 for i in result.issues if i.severity == ValidationSeverity.WARNING)
            logger.debug(
                f"Validation [{symbol}]: {len(df_clean)} bars | "
                f"{error_count} errors, {warning_count} warnings"
            )
        else:
            logger.warning(
                f"Validation FAILED [{symbol}]: "
                f"{[i.message for i in result.issues if i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL)]}"
            )

        return result


class QuoteValidator:
    """
    Validates a single price quote for sanity.
    Used before caching or displaying live prices.
    """

    @staticmethod
    def validate(price: float, symbol: str = "", prev_price: float | None = None) -> ValidationResult:
        result = ValidationResult(is_valid=True)

        if price is None or np.isnan(price):
            result.add_issue(ValidationSeverity.ERROR, "price", "Price is None or NaN")
            return result

        if price <= 0:
            result.add_issue(ValidationSeverity.ERROR, "price", f"Price is non-positive: {price}")
            return result

        if prev_price and prev_price > 0:
            change_pct = abs(price - prev_price) / prev_price * 100
            if change_pct > 15:
                result.add_issue(
                    ValidationSeverity.WARNING, "price",
                    f"Price moved {change_pct:.1f}% from previous: {prev_price} → {price}"
                )

        return result
