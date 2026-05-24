"""
data_ingestion.py — NSE Data Ingestion Layer
============================================
Priority chain for fetching OHLCV data:
  1. nsepython  — real NSE website session (live quotes)
  2. yfinance   — Yahoo Finance with .NS suffix (historical + live)
  3. Simulator  — Realistic NSE price simulation (fallback / demo mode)

The simulator uses a seeded random walk calibrated to each ticker's real
price range so backtests and scanner demos are meaningful even offline.
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from backend.core import logger as log_mod
from backend.core.settings import NSE_BASE_PRICES, NSE_WATCHLIST, STRATEGY, SYSTEM

log = log_mod.get(__name__)

_REQ_COLS = ("Open", "High", "Low", "Close", "Volume")
_DELAY    = 0.4   # seconds between requests


# ─── Validator ────────────────────────────────────────────────────────────────

def _validate(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Clean and validate an OHLCV DataFrame."""
    if df is None or df.empty:
        raise ValueError(f"[{ticker}] Empty DataFrame")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    missing = [c for c in _REQ_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"[{ticker}] Missing columns: {missing}")

    df = df.dropna(subset=list(_REQ_COLS), how="all")
    df = df[df["Volume"] > 0]
    df = df.ffill().bfill()

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df = df.sort_index()

    if len(df) < STRATEGY.min_candles:
        raise ValueError(f"[{ticker}] Only {len(df)} candles (need {STRATEGY.min_candles})")

    return df[list(_REQ_COLS)]


# ─── NSE Simulator (seeded, realistic) ───────────────────────────────────────

def _simulate_ohlcv(
    ticker: str,
    n_days: int = 365,
    end_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Generate realistic NSE OHLCV data using a seeded GBM (Geometric Brownian Motion).

    Each ticker gets a unique, deterministic seed derived from its name so
    the same ticker always produces the same historical series.

    Parameters
    ----------
    ticker:    NSE symbol (e.g. "RELIANCE")
    n_days:    Number of trading days to generate.
    end_date:  Last date of the series (defaults to today).

    Returns
    -------
    pd.DataFrame with DatetimeIndex and OHLCV columns.
    """
    # Deterministic seed per ticker — same data on every run
    seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % (2**31)
    rng  = np.random.default_rng(seed)

    base  = NSE_BASE_PRICES.get(ticker, 1000.0)
    drift = 0.0003     # ~7.5% annual drift
    vol   = 0.015      # ~24% annual volatility (typical large-cap NSE)

    end   = end_date or datetime.today()
    dates = pd.bdate_range(end=end, periods=n_days + 1)  # +1 buffer for bdate alignment
    n_actual = len(dates)  # actual business days generated

    # GBM simulation
    returns = rng.normal(drift, vol, n_actual)
    # Inject a few realistic trend segments
    trend_start = n_actual // 3
    returns[trend_start : trend_start + 40] += 0.003   # Bull run
    returns[trend_start + 60 : trend_start + 80] -= 0.004  # Correction

    prices = base * np.cumprod(1 + returns)

    # Build OHLCV
    intraday_range = np.abs(rng.normal(0, vol * 0.6, n_actual))
    high   = prices * (1 + intraday_range)
    low    = prices * (1 - intraday_range)
    open_  = np.roll(prices, 1);  open_[0] = base
    # Volume: mean ~5M for large caps, with Monday effect
    base_vol  = NSE_BASE_PRICES.get(ticker, 1000.0) * 2000
    volume    = rng.integers(int(base_vol * 0.5), int(base_vol * 1.8), n_actual).astype(float)
    # Spike volume on trend days
    volume[trend_start : trend_start + 40] *= 1.6

    df = pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": prices, "Volume": volume},
        index=dates,
    )
    log.debug("[%s] Simulated %d candles (₹%.0f → ₹%.0f)", ticker, n_days, prices[0], prices[-1])
    return df


# ─── nsepython Live Quote ─────────────────────────────────────────────────────

def _fetch_nsepython_quote(ticker: str) -> Optional[dict]:
    """
    Fetch a real-time quote from NSE via nsepython session.

    Returns dict with price/open/high/low/volume or None on failure.
    """
    # Non-NSE tickers (crypto, commodities) don't work with nsefetch
    if "-" in ticker or "=" in ticker:
        return None

    try:
        from nsepython import nsefetch
        url  = f"https://www.nseindia.com/api/quote-equity?symbol={ticker}"
        data = nsefetch(url)
        if not data:
            return None
        pi = data.get("priceInfo", {})
        lp = pi.get("lastPrice") or pi.get("close")
        if not lp:
            return None
        idhl = pi.get("intraDayHighLow", {})
        return {
            "price":      float(lp),
            "open":       float(pi.get("open", lp)),
            "high":       float(idhl.get("max", lp)),
            "low":        float(idhl.get("min", lp)),
            "prev_close": float(pi.get("previousClose", lp)),
            "change_pct": float(pi.get("pChange", 0.0)),
            "source":     "nsepython_live",
        }
    except Exception as exc:
        log.debug("[%s] nsepython quote failed: %s", ticker, exc)
        return None


# ─── nsepython Historical ─────────────────────────────────────────────────────

def _fetch_nsepython_history(ticker: str, days: int = 365) -> Optional[pd.DataFrame]:
    """Fetch historical OHLCV from NSE Bhavcopy via nsepython."""
    try:
        from nsepython import equity_history
        end   = datetime.today().strftime("%d-%m-%Y")
        start = (datetime.today() - timedelta(days=days)).strftime("%d-%m-%Y")
        df    = equity_history(ticker, "EQ", start, end)
        if df is None or df.empty:
            return None

        # Standardise column names from NSE bhavcopy format
        col_map = {
            "CH_TIMESTAMP": "Date",
            "CH_OPENING_PRICE": "Open", "CH_TRADE_HIGH_PRICE": "High",
            "CH_TRADE_LOW_PRICE": "Low", "CH_CLOSING_PRICE": "Close",
            "CH_TOT_TRADED_QTY": "Volume",
            # alternate names
            "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume", "date": "Date",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")

        log.debug("[%s] nsepython history: %d rows", ticker, len(df))
        return _validate(df, ticker)

    except Exception as exc:
        log.debug("[%s] nsepython history failed: %s", ticker, exc)
        return None


# ─── yfinance Fallback ────────────────────────────────────────────────────────

def _fetch_yfinance(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    """Fetch OHLCV from Yahoo Finance using the .NS suffix."""
    try:
        import yfinance as yf
        yf_sym = ticker if ("-" in ticker or "=" in ticker) else f"{ticker}.NS"
        df     = yf.Ticker(yf_sym).history(
            period=period, interval=interval,
            auto_adjust=True, actions=False, timeout=12,
        )
        if df is None or df.empty:
            return None
        log.info("[%s] yfinance: %d rows", ticker, len(df))
        return _validate(df, ticker)
    except Exception as exc:
        log.debug("[%s] yfinance failed: %s", ticker, exc)
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def fetch_historical(
    ticker: str,
    period: str = STRATEGY.live_period,
    interval: str = STRATEGY.interval,
    force_simulate: bool = False,
) -> pd.DataFrame:
    """
    Fetch historical OHLCV for a single NSE ticker.

    Tries (in order): nsepython → yfinance .NS → simulation.
    Always returns a valid DataFrame — never raises for the caller.

    Parameters
    ----------
    ticker:         NSE symbol without suffix (e.g. "RELIANCE")
    period:         Lookback string for yfinance (e.g. "6mo", "5y")
    interval:       Candle interval (e.g. "1d")
    force_simulate: Skip live sources and use simulator directly.

    Returns
    -------
    pd.DataFrame  OHLCV with DatetimeIndex.
    """
    # Map period string to approx days for simulator/nsepython
    period_days = {
        "1mo": 30, "3mo": 90, "6mo": 180,
        "1y": 365, "2y": 730, "5y": 1825,
    }
    n_days = period_days.get(period, 365)

    if not force_simulate:
        # 1. nsepython
        df = _fetch_nsepython_history(ticker, days=n_days)
        if df is not None:
            log.info("[%s] Source: NSE API | %d candles", ticker, len(df))
            time.sleep(_DELAY)
            return df

        # 2. yfinance .NS
        df = _fetch_yfinance(ticker, period=period, interval=interval)
        if df is not None:
            log.info("[%s] Source: Yahoo Finance | %d candles", ticker, len(df))
            time.sleep(_DELAY)
            return df

    # 3. Simulator (always succeeds)
    log.info("[%s] Source: NSE Simulator (demo/offline mode) | %d days", ticker, n_days)
    df = _simulate_ohlcv(ticker, n_days=n_days)
    return _validate(df, ticker)


def fetch_live_quote(ticker: str) -> dict:
    """
    Fetch a real-time price snapshot for an NSE ticker.

    Returns
    -------
    dict  Keys: price, open, high, low, prev_close, change_pct, source.
    """
    # 1. nsepython live
    q = _fetch_nsepython_quote(ticker)
    if q:
        log.info("[%s] Live quote: ₹%.2f (%.2f%%) [NSE]", ticker, q["price"], q["change_pct"])
        return q

    # 2. yfinance fast_info
    try:
        import yfinance as yf
        yf_sym = ticker if ("-" in ticker or "=" in ticker) else f"{ticker}.NS"
        fi = yf.Ticker(yf_sym).fast_info
        price = float(fi.last_price or 0)
        prev  = float(fi.previous_close or price)
        if price > 0:
            pct = (price - prev) / prev * 100 if prev else 0
            log.info("[%s] Live quote: ₹%.2f (%.2f%%) [Yahoo]", ticker, price, pct)
            return {"price": price, "open": float(fi.open or price),
                    "high": float(fi.day_high or price), "low": float(fi.day_low or price),
                    "prev_close": prev, "change_pct": round(pct, 2), "source": "yfinance"}
    except Exception:
        pass

    # 3. Simulate last-close from recent simulated data
    df = _simulate_ohlcv(ticker, n_days=5)
    price = float(df["Close"].iloc[-1])
    prev  = float(df["Close"].iloc[-2])
    pct   = (price - prev) / prev * 100
    log.info("[%s] Simulated quote: ₹%.2f (%.2f%%)", ticker, price, pct)
    return {"price": price, "open": float(df["Open"].iloc[-1]),
            "high": float(df["High"].iloc[-1]), "low": float(df["Low"].iloc[-1]),
            "prev_close": prev, "change_pct": round(pct, 2), "source": "simulator"}


def fetch_batch(
    tickers: list[str],
    period: str = STRATEGY.live_period,
    interval: str = STRATEGY.interval,
) -> dict[str, pd.DataFrame]:
    """Fetch historical data for multiple tickers; skip failures."""
    results: dict[str, pd.DataFrame] = {}
    total = len(tickers)
    for i, t in enumerate(tickers, 1):
        log.info("[%d/%d] Fetching %s…", i, total, t)
        try:
            results[t] = fetch_historical(t, period=period, interval=interval)
        except Exception as exc:
            log.warning("Skip %s: %s", t, exc)
    log.info("Batch complete: %d/%d tickers", len(results), total)
    return results


def nifty50_index_data(n_days: int = 365) -> pd.DataFrame:
    """
    Return NIFTY 50 index OHLCV for benchmark comparisons.
    Uses ^NSEI via yfinance, falls back to simulated index series.
    """
    try:
        import yfinance as yf
        df = yf.Ticker("^NSEI").history(period="5y", auto_adjust=True, actions=False, timeout=10)
        if not df.empty:
            return _validate(df, "NIFTY50")
    except Exception:
        pass

    # Simulate NIFTY50: realistic range 17000–25000
    seed = int(hashlib.md5(b"NIFTY50").hexdigest(), 16) % (2**31)
    rng  = np.random.default_rng(seed)
    dates   = pd.bdate_range(end=datetime.today(), periods=n_days)
    returns = rng.normal(0.0003, 0.010, n_days)
    prices  = 21000 * np.cumprod(1 + returns)
    volume  = rng.integers(200_000_000, 600_000_000, n_days).astype(float)
    df = pd.DataFrame({
        "Open": np.roll(prices, 1), "High": prices * 1.005,
        "Low": prices * 0.995, "Close": prices, "Volume": volume,
    }, index=dates)
    df["Open"].iloc[0] = 21000.0
    return df
