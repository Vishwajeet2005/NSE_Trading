"""
settings.py — NSE Semi-Autonomous Trading System Configuration
==============================================================
All credentials and parameters are plain Python constants.
Edit this file directly — no .env files, no environment variables.

QUICK SETUP CHECKLIST
---------------------
1. Zerodha Kite:    Fill ZERODHA_* below (leave blank for paper trading)
2. Telegram alerts: Fill TELEGRAM_* below (leave blank to disable)
3. Risk params:     Review RiskConfig — defaults are conservative
4. Watchlist:       Edit NSE_WATCHLIST to your preferred stocks
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Final

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 1 — CREDENTIALS  (edit these directly)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Zerodha Kite Connect ──────────────────────────────────────────────────────
# Credentials are now managed dynamically via the UI and stored in .credentials.json.
# (You can still set fallback values here if needed)
ZERODHA_API_KEY     = ""
ZERODHA_API_SECRET  = ""
ZERODHA_ACCESS_TOKEN = ""

# ── Telegram Bot ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN  = ""
TELEGRAM_CHAT_ID    = ""

# ── Groq AI ───────────────────────────────────────────────────────────────────
GROQ_API_KEY   = ""

import os
try:
    import keyring
except ImportError:
    keyring = None

SERVICE_NAME = "nse_trading_system"

def get_secret(key: str) -> str:
    val = os.getenv(key)
    if val: return val
    if keyring:
        try:
            return keyring.get_password(SERVICE_NAME, key) or ""
        except Exception:
            return ""
    return ""

def load_credentials() -> dict:
    return {
        "ZERODHA_API_KEY": get_secret("ZERODHA_API_KEY"),
        "ZERODHA_API_SECRET": get_secret("ZERODHA_API_SECRET"),
        "ZERODHA_ACCESS_TOKEN": get_secret("ZERODHA_ACCESS_TOKEN"),
        "TELEGRAM_BOT_TOKEN": get_secret("TELEGRAM_BOT_TOKEN"),
        "TELEGRAM_CHAT_ID": get_secret("TELEGRAM_CHAT_ID"),
        "GROQ_API_KEY": get_secret("GROQ_API_KEY"),
    }

def save_credentials(creds: dict):
    for k, v in creds.items():
        if v:
            keyring.set_password(SERVICE_NAME, k, v)
        else:
            try:
                keyring.delete_password(SERVICE_NAME, k)
            except keyring.errors.PasswordDeleteError:
                pass

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 2 — NSE WATCHLIST  (edit to your preferred stocks)
# ═══════════════════════════════════════════════════════════════════════════════

NSE_WATCHLIST: Final[list[str]] = [
    # Large-cap NIFTY 50 stocks — symbols exactly as on NSE website
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "ITC", "KOTAKBANK",
    "LT", "AXISBANK", "WIPRO", "BAJFINANCE", "MARUTI",
    "SUNPHARMA", "TITAN", "ASIANPAINT", "NESTLEIND", "ULTRACEMCO",
    # Crypto and Fuels
    "BTC-USD", "ETH-USD", "CL=F", "NG=F",
]

# Realistic NSE base prices (₹) used by the offline simulator
# Update periodically to stay close to current market prices
NSE_BASE_PRICES: Final[dict[str, float]] = {
    "RELIANCE":  2950.0,  "TCS":       3800.0,  "HDFCBANK":  1720.0,
    "INFY":      1580.0,  "ICICIBANK": 1340.0,  "HINDUNILVR":2400.0,
    "SBIN":       820.0,  "BHARTIARTL":1850.0,  "ITC":        430.0,
    "KOTAKBANK": 1990.0,  "LT":        3600.0,  "AXISBANK":  1180.0,
    "WIPRO":      480.0,  "BAJFINANCE":9100.0,  "MARUTI":   11500.0,
    "SUNPHARMA": 1750.0,  "TITAN":     3300.0,  "ASIANPAINT":2700.0,
    "NESTLEIND": 2350.0,  "ULTRACEMCO":10200.0,
    "BTC-USD": 90000.0,   "ETH-USD": 3000.0,
    "CL=F": 75.0,         "NG=F": 3.0,
}

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 3 — RISK PARAMETERS  (hardcoded guardrails — review carefully)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class RiskConfig:
    """
    Immutable risk rules enforced on every signal.
    All percentages are fractions: 0.01 = 1%.
    """
    max_risk_per_trade_pct: float = 0.01    # Never risk > 1% of equity per trade
    stop_loss_pct:          float = 0.02    # Exit at -2% from entry
    take_profit_pct:        float = 0.06    # Exit at +6% from entry
    atr_stop_multiplier:    float = 1.5     # ATR-based stop = entry ± ATR×1.5
    max_open_positions:     int   = 5       # Maximum simultaneous positions
    min_cash_reserve_pct:   float = 0.20    # Always keep ≥20% cash un-deployed
    max_position_size_pct:  float = 0.10    # Single position ≤10% of equity
    min_signal_confidence:  int   = 60      # Minimum score out of 100 to act

    @property
    def risk_reward_ratio(self) -> float:
        return self.take_profit_pct / self.stop_loss_pct   # Must be ≥ 2.0

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 4 — STRATEGY / INDICATOR PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class StrategyConfig:
    """Technical indicator periods and thresholds."""
    # Exponential Moving Averages
    ema_fast_period:   int   = 9
    ema_slow_period:   int   = 21
    ema_trend_period:  int   = 50

    # RSI
    rsi_period:        int   = 14
    rsi_oversold:      int   = 30
    rsi_overbought:    int   = 70
    rsi_neutral_low:   int   = 40
    rsi_neutral_high:  int   = 60

    # MACD
    macd_fast:         int   = 12
    macd_slow:         int   = 26
    macd_signal:       int   = 9

    # ATR & Bollinger Bands
    atr_period:        int   = 14
    bb_period:         int   = 20
    bb_std_dev:        float = 2.0

    # Volume filter
    volume_multiplier: float = 1.2    # Require volume > 1.2× 20-day average

    # Minimum candles before any signal is generated
    min_candles:       int   = 60

    # Data fetch parameters
    live_period:       str   = "6mo"  # For live scanner
    historical_period: str   = "5y"   # For backtesting
    interval:          str   = "1d"   # Daily candles

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 5 — BACKTESTING PARAMETERS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BacktestConfig:
    initial_capital:    float = 1_000_000.0  # ₹10 lakh starting capital
    commission_pct:     float = 0.0003       # 0.03% per leg (Zerodha flat fee)
    stt_pct:            float = 0.001        # 0.1% STT on sell leg
    slippage_pct:       float = 0.0005       # 0.05% estimated slippage
    benchmark:          str   = "NIFTY50"
    historical_period:  str   = "5y"
    interval:           str   = "1d"

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 6 — SYSTEM / OPERATIONAL SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SystemConfig:
    log_file:             str = "nse_system.log"
    db_path:              str = "nse_signals.db"
    dashboard_port:       int = 8501
    scanner_interval_min: int = 60           # Minutes between live scans
    currency_symbol:      str = "₹"
    market_timezone:      str = "Asia/Kolkata"
    market_open_hour:     int = 9
    market_open_minute:   int = 15
    market_close_hour:    int = 15
    market_close_minute:  int = 30

# ═══════════════════════════════════════════════════════════════════════════════
#  ▶  SECTION 7 — DERIVED CONFIG OBJECTS  (do not edit below this line)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ZerodhaConfig:
    api_key:      str  = ZERODHA_API_KEY
    api_secret:   str  = ZERODHA_API_SECRET
    access_token: str  = ZERODHA_ACCESS_TOKEN
    enabled:      bool = bool(ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN)

@dataclass
class TelegramConfig:
    bot_token: str  = TELEGRAM_BOT_TOKEN
    chat_id:   str  = TELEGRAM_CHAT_ID
    enabled:   bool = bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)

@dataclass
class GroqConfig:
    api_key: str = GROQ_API_KEY

# Singleton instances imported throughout the codebase
ZERODHA  = ZerodhaConfig()
TELEGRAM = TelegramConfig()
GROQ     = GroqConfig()
RISK     = RiskConfig()
STRATEGY = StrategyConfig()
BACKTEST = BacktestConfig()
SYSTEM   = SystemConfig()

def refresh_credentials():
    creds = load_credentials()
    ZERODHA.api_key = creds.get("ZERODHA_API_KEY", ZERODHA_API_KEY)
    ZERODHA.api_secret = creds.get("ZERODHA_API_SECRET", ZERODHA_API_SECRET)
    ZERODHA.access_token = creds.get("ZERODHA_ACCESS_TOKEN", ZERODHA_ACCESS_TOKEN)
    ZERODHA.enabled = bool(ZERODHA.api_key and ZERODHA.access_token)
    
    TELEGRAM.bot_token = creds.get("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN)
    TELEGRAM.chat_id = creds.get("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID)
    TELEGRAM.enabled = bool(TELEGRAM.bot_token and TELEGRAM.chat_id)
    
    GROQ.api_key = creds.get("GROQ_API_KEY", GROQ_API_KEY)

# Load at startup
refresh_credentials()
