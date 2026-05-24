# 📈 NSE Semi-Autonomous Trading System

> **Rule-Based · Human-in-the-Loop · Zero Black Boxes · No .env Files**

A production-grade, fully modular stock analysis and trade recommendation system built exclusively for the **National Stock Exchange of India (NSE)**. The system analyses 20 NIFTY 50 stocks using classical technical indicators, generates BUY/SELL signals with a confidence score, and presents them to the human operator for approval — **it never executes a trade automatically**.

All amounts are in **Indian Rupees (₹)**. All times are **IST (Asia/Kolkata)**. Default mode is **paper trading** — no real money is touched unless you explicitly connect Zerodha Kite and approve an order.

---

## Table of Contents

1. [Architecture](#architecture)
2. [File Structure](#file-structure)
3. [Quick Start](#quick-start)
4. [Configuration Guide](#configuration-guide)
5. [How the Signal Logic Works](#how-the-signal-logic-works)
6. [Risk Management Rules](#risk-management-rules)
7. [All Commands](#all-commands)
8. [Dashboard Guide](#dashboard-guide)
9. [Screener Guide](#screener-guide)
10. [Backtesting Guide](#backtesting-guide)
11. [Portfolio Tracker](#portfolio-tracker)
12. [Live Data Sources](#live-data-sources)
13. [Broker Integration](#broker-integration)
14. [Telegram Notifications](#telegram-notifications)
15. [Test Suite](#test-suite)
16. [Troubleshooting](#troubleshooting)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    SYSTEM PIPELINE                                    │
│                                                                      │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────┐  │
│  │   MODULE 1      │   │    MODULE 2       │   │    MODULE 3      │  │
│  │ Data Ingestion  │──▶│ Strategy Engine   │──▶│ Risk Management  │  │
│  │                 │   │                   │   │                  │  │
│  │ nsepython       │   │ EMA 9/21/50       │   │ Stop-Loss  -2%   │  │
│  │ yfinance .NS    │   │ RSI(14)           │   │ Take-Profit +6%  │  │
│  │ GBM Simulator  │   │ MACD(12,26,9)     │   │ 1% Risk/Trade    │  │
│  │                 │   │ Bollinger Bands   │   │ Max 5 positions  │  │
│  │ Validates &     │   │ ATR(14)           │   │ 20% Cash reserve │  │
│  │ cleans OHLCV    │   │ Volume ratio      │   │ Min R:R  1:3     │  │
│  └─────────────────┘   │                   │   └────────┬─────────┘  │
│                        │ Confidence 0-100  │            │            │
│                        └──────────────────┘            │            │
│                                                         ▼            │
│                                              ┌──────────────────┐    │
│                                              │    MODULE 4      │    │
│                                              │ Human Approval   │    │
│                                              │ & Execution      │    │
│                                              │                  │    │
│                                              │  📊 Dashboard    │    │
│                                              │  📱 Telegram     │    │
│                                              │  🖥  Console     │    │
│                                              │                  │    │
│                                              │ [APPROVE] [DENY] │    │
│                                              │       │          │    │
│                                              │  Zerodha / Paper │    │
│                                              │  Bracket Order   │    │
│                                              └──────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### The Four Core Modules

| Module | File | Responsibility |
|---|---|---|
| **Data Ingestion** | `data_ingestion.py` | Fetch & validate NSE OHLCV. Priority: nsepython → yfinance `.NS` → GBM simulator |
| **Strategy Engine** | `strategy_engine.py` | Compute all indicators, evaluate 6 BUY + 4 SELL conditions, produce confidence score |
| **Risk Management** | `risk_management.py` | Enforce stop-loss, take-profit, position sizing, 7 hard guardrails |
| **Approval Bridge** | `execution_bridge.py` | Execute ONLY on human APPROVE click. Paper trading or Zerodha Kite bracket orders |

---

## File Structure

```
nse_system/
│
├── main.py              ← Single entry point. All modes via --mode flag.
├── settings.py          ← ALL credentials & config. Edit this file directly.
│
├── data_ingestion.py    ← NSE OHLCV fetching with 3-tier fallback
├── strategy_engine.py   ← Technical indicators + BUY/SELL signal logic
├── risk_management.py   ← Position sizing + hardcoded risk guardrails
├── execution_bridge.py  ← Broker integration (Paper + Zerodha Kite)
├── notification.py      ← Telegram bot + Rich console alerts
│
├── scanner.py           ← Scheduled watchlist scanner (IST market hours)
├── screener.py          ← Near-signal screener + sector heatmap
├── backtest.py          ← 5-year historical simulation engine
├── portfolio.py         ← Paper P&L tracker with ASCII equity curve
├── dashboard.py         ← Streamlit APPROVE/DENY web UI
│
├── database.py          ← SQLite signals + trades persistence
├── logger.py            ← Dual-sink logger (Rich console + rotating file)
│
├── tests.py             ← 91-test suite (no pytest needed)
├── setup.sh             ← One-command installer
└── requirements.txt     ← All Python dependencies
```

> **No subdirectories. No packages. No imports across folders.**
> Every file imports its siblings directly — `import settings`, `import database`, etc.

---

## Quick Start

### Prerequisites

- Python **3.10 or higher**
- Internet connection (for pip install)
- No API keys required to run in demo/paper mode

### Option A — Automated setup (recommended)

```bash
cd nse_system
bash setup.sh
```

This script will:
1. Check Python version
2. Create a `.venv` virtual environment
3. Install all dependencies
4. Initialise the SQLite database
5. Run the 91-test suite to verify everything works

### Option B — Manual setup

```bash
cd nse_system

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialise database
python main.py --init-db

# Verify installation
python tests.py
```

### Run immediately (Web UI Mode - Recommended)

```bash
source .venv/bin/activate
python main.py --mode web
```

This launches the FastAPI backend and the new Vite React frontend. Open **http://localhost:5173** in your browser.

### Run in Demo Mode (Streamlit Dashboard)

```bash
source .venv/bin/activate
python main.py --mode demo
```

This runs a full scan of all 20 NSE tickers (no market-hours gate) then opens the legacy Streamlit dashboard at **http://localhost:8501**.

---

## Configuration Guide

**All credentials are now securely managed via the Web UI.**

### Step 1 — Add API Credentials

1. Start the web application: `python main.py --mode web`
2. Open **http://localhost:5173**
3. Click the **Settings ⚙️** icon in the top right header.
4. Enter your keys (Zerodha, Telegram, Anthropic).
5. Click **Save Credentials**.
   
Keys are instantly applied to the running backend and saved securely to `.credentials.json` (which is git-ignored).

*Note: You can still use the legacy method by setting fallback values directly in `settings.py`, but using the UI is highly recommended for security.*

### Step 3 — Customise your watchlist

```python
# settings.py — SECTION 2

NSE_WATCHLIST = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    # add or remove any NSE symbols here
    "ZOMATO", "ADANIENT", "BAJAJFINSV",
]

# Also update base prices for accurate simulation:
NSE_BASE_PRICES = {
    "ZOMATO":    200.0,
    "ADANIENT":  2400.0,
    ...
}
```

Use the exact NSE symbol as shown on the NSE website (no `.NS` suffix needed — the system adds it automatically for Yahoo Finance).

### Step 4 — Review risk parameters

```python
# settings.py — SECTION 3

@dataclass(frozen=True)
class RiskConfig:
    max_risk_per_trade_pct: float = 0.01    # 1% of equity per trade
    stop_loss_pct:          float = 0.02    # Exit at -2% from entry
    take_profit_pct:        float = 0.06    # Exit at +6% from entry
    max_open_positions:     int   = 5       # Max simultaneous positions
    min_cash_reserve_pct:   float = 0.20    # Keep ≥20% cash always
    max_position_size_pct:  float = 0.10    # Single position ≤10% of equity
    min_signal_confidence:  int   = 60      # Score out of 100
```

> ⚠️ These are **frozen dataclasses** — they cannot be changed at runtime. Edit `settings.py` and restart.

### Step 5 — Set starting capital for backtests

```python
# settings.py — SECTION 5

@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 1_000_000.0   # ₹10 lakh default
```

---

## How the Signal Logic Works

The strategy engine uses **six independent BUY conditions**, each contributing a weight to a total confidence score out of 100. A signal fires only when the combined score reaches the minimum threshold (default: 60).

### BUY Signal Conditions

| # | Condition | Weight | Rule |
|---|---|---|---|
| 1 | **Trend Filter** | 20 | `Close > EMA(50)` — only trade in the direction of the trend |
| 2 | **EMA Crossover** | 20 | `EMA(9)` crossed above `EMA(21)` within the last 3 candles |
| 3 | **RSI Zone** | 15 | `RSI(14)` between 40–70 **and** rising (not extreme, not falling) |
| 4 | **MACD Signal** | 20 | MACD line crossed above signal line within the last 3 candles |
| 5 | **Volume Confirm** | 15 | Current volume > **1.2×** its 20-day average (institutional activity) |
| 6 | **Bollinger Entry** | 10 | Price is in the lower 35% of the BB range (mean-reversion zone) |

**Maximum possible BUY score: 100**
**Minimum to trigger: 60** (configurable via `min_signal_confidence` in `settings.py`)

### SELL Signal Conditions

| # | Condition | Weight | Rule |
|---|---|---|---|
| 1 | **EMA Bear Cross** | 30 | `EMA(9)` crossed below `EMA(21)` |
| 2 | **RSI Overbought** | 30 | `RSI(14) > 70` |
| 3 | **MACD Bear Cross** | 25 | MACD line crossed below signal line |
| 4 | **Below Trend** | 15 | Price dropped below `EMA(50)` |

### Confidence Score Example

```
RELIANCE BUY scan result:

  ✅ Price ₹2,950 > EMA(50) ₹2,820              +20
  ✅ EMA(9) crossed above EMA(21) 2 days ago    +20
  ✅ RSI 55.3 — in zone [40-70] and rising      +15
  ❌ No recent MACD bull crossover               +0
  ✅ Volume 1.45× average                       +15
  ❌ Price not near lower Bollinger Band          +0
                                            ─────────
  Total Score: 70 / 100  →  ✅ BUY SIGNAL FIRES
```

---

## Risk Management Rules

Every signal passes through **7 mandatory checks** before reaching the operator. Any failed check silently discards the signal.

### Position Sizing Formula

```
risk_per_share  = |entry_price − stop_loss_price|
max_risk_₹      = account_equity × 1%
raw_shares      = max_risk_₹ / risk_per_share
capped_shares   = min(raw_shares, equity × 10% / entry_price)
final_shares    = floor(capped_shares)
```

### Example Calculation

```
Account equity  : ₹10,00,000
Entry price     : ₹2,950  (RELIANCE)
Stop-loss       : ₹2,891  (−2% from entry)
Risk per share  : ₹59

Max risk ₹      : ₹10,000   (1% of ₹10,00,000)
Raw shares      : 169        (₹10,000 / ₹59)
Position cap    : 33         (₹1,00,000 / ₹2,950 = 10% cap)
Final shares    : 33

Position value  : ₹97,350   (33 × ₹2,950)
Max loss        : ₹1,947     (33 × ₹59)
Max gain        : ₹5,841     (33 × ₹177 = 6% target)
R:R ratio       : 1:3.0
```

### The 7 Hard Guardrails

| # | Rule | Rejects When |
|---|---|---|
| 1 | Minimum confidence | Score < 60 |
| 2 | Minimum position | Calculated shares = 0 |
| 3 | Max positions | 5 or more positions already open |
| 4 | Cash reserve | Deployment would leave < 20% cash |
| 5 | Logic check | Stop-loss is on the wrong side of entry |
| 6 | R:R minimum | Reward/Risk ratio < 2.0 |
| 7 | Direction check | Signal direction is NONE |

---

## All Commands

```bash
# ── Setup ─────────────────────────────────────────────────────────
bash setup.sh                              # One-command setup
python main.py --init-db                   # Initialise database only

# ── Full System ───────────────────────────────────────────────────
python main.py --mode web                  # Launch FastAPI + Vite React UI (Recommended)
python main.py                             # Scanner + Streamlit Dashboard
python main.py --mode full                 # Same as above
python main.py --mode demo                 # One scan + Streamlit Dashboard, no IST gate
python main.py --no-gate                   # Disable market-hours check

# ── Scanner ───────────────────────────────────────────────────────
python main.py --mode scan-once            # One scan pass and exit
python main.py --mode scanner              # Scheduled scanner (every 60 min)
python main.py --mode scanner --interval 30  # Scan every 30 minutes
python main.py --mode scanner --no-gate    # Scan outside market hours

# ── Dashboard ─────────────────────────────────────────────────────
python main.py --mode dashboard            # Open Streamlit UI only
# Then visit: http://localhost:8501

# ── Backtesting ───────────────────────────────────────────────────
python main.py --mode backtest                         # RELIANCE (default)
python main.py --mode backtest --ticker TCS            # Single ticker
python main.py --mode backtest --ticker HDFCBANK       # Any NSE symbol
python main.py --mode backtest --all                   # All 20 watchlist tickers
python main.py --mode backtest --all --capital 500000  # Custom capital ₹5 lakh

# ── Screener ──────────────────────────────────────────────────────
python main.py --mode screen               # Full watchlist indicator screen
python main.py --mode screen --ticker INFY TCS WIPRO  # Specific tickers
python screener.py --sector Banking        # Filter by sector
python screener.py --sector Technology

# ── Portfolio Tracker ─────────────────────────────────────────────
python main.py --mode portfolio            # Full P&L report
python main.py --mode portfolio --open     # Open positions only
python main.py --mode portfolio --history  # Closed trades only
python main.py --mode portfolio --equity   # ASCII equity curve
python main.py --mode portfolio --daily    # Daily P&L breakdown

# ── Tests ─────────────────────────────────────────────────────────
python tests.py                            # All 91 tests (no pytest needed)
pytest tests.py -v                         # Verbose pytest output
```

---

## Dashboard Guide

Launch the dashboard:

```bash
python main.py --mode dashboard
# or
python main.py --mode demo    # runs a scan first, then opens dashboard
```

Open **http://localhost:8501** in your browser.

### ⏳ Pending Signals Tab

Every pending signal gets a card showing:

```
🟢 Signal #12 — BAJFINANCE
────────────────────────────────────────
Direction     : BUY          Confidence : 80/100
Entry Price   : ₹9,142.50    Shares     : 10
Stop Loss     : ₹8,959.65    Position ₹ : ₹91,425
Take Profit   : ₹9,691.05    Max Risk ₹ : ₹1,828
R:R Ratio     : 1:3.0        Max Reward : ₹5,485
────────────────────────────────────────
Signal Reasons (click to expand):
  ✅ Price ₹9,142 > EMA(50) ₹8,950
  ✅ EMA(9) crossed above EMA(21) — bull crossover
  ✅ RSI 58.4 in zone [40-70] and rising
  ✅ Volume 1.67× average
  ❌ No MACD bull crossover
  ❌ Price not near lower Bollinger Band

[✅ APPROVE #12]   [🚫 DENY #12]
```

**APPROVE** → immediately submits a bracket order to the broker (paper or Zerodha). The order includes entry + stop-loss + take-profit as one atomic unit.

**DENY** → prompts for an optional reason (e.g. "Earnings risk tomorrow"), marks signal as denied, notifies via Telegram.

### 📋 Signal History Tab

Filterable table of all signals. Filter by status (PENDING / APPROVED / DENIED / EXECUTED), direction, and ticker.

### 💼 Open Positions Tab

All currently open trades with entry price, live price, unrealised P&L.

### 📊 Analytics Tab

Signal direction mix, confidence score histogram, signals-per-day timeline, status breakdown.

---

## Screener Guide

The screener shows every ticker's full indicator state — not just confirmed signals — so you can see what is approaching a signal condition.

```bash
python main.py --mode screen
```

### Output Sections

**⚡ Near-Signal Alerts** — tickers with buy score 50–59 (just below the 60 threshold), and what conditions are still missing.

```
⚡ Near-Signal & Active Alerts
┌──────────┬──────────┬─────┬───────────┬────────────┬──────────────────────────┐
│ Alert    │ Ticker   │ Dir │ Price ₹   │ Buy Score  │ Missing Conditions       │
├──────────┼──────────┼─────┼───────────┼────────────┼──────────────────────────┤
│ ⚡ NEAR  │ HINDUNILVR│ —  │ ₹3,512.00 │ █████░░░░░ │ MACD, Vol 0.9×           │
│ ⚡ NEAR  │ KOTAKBANK │ —  │ ₹2,045.00 │ ████░░░░░░ │ EMA cross, Trend EMA     │
└──────────┴──────────┴─────┴───────────┴────────────┴──────────────────────────┘
```

**📡 RSI Extremes** — tickers at RSI < 35 (oversold, potential BUY reversal) or RSI > 68 (overbought, potential SELL).

**📊 Volume Spikes** — tickers trading > 1.8× their average volume.

**🌡️ Sector Heatmap** — momentum summary per sector.

```
🌡️ Sector Momentum Heatmap
┌─────────────┬─────────┬───────────────┬─────────┬─────────┬──────────────┐
│ Sector      │ Tickers │ Avg Buy Score │ Avg RSI │ Avg Chg │ Momentum     │
├─────────────┼─────────┼───────────────┼─────────┼─────────┼──────────────┤
│ Finance     │ 2       │ ████████░░ 45 │ 58.2    │ +0.42%  │ 📈 RISING    │
│ Banking     │ 5       │ ███░░░░░░░ 30 │ 51.4    │ +0.18%  │ ↔  NEUTRAL   │
│ Technology  │ 3       │ ██░░░░░░░░ 18 │ 43.6    │ -0.22%  │ 📉 WEAK      │
└─────────────┴─────────┴───────────────┴─────────┴─────────┴──────────────┘
```

**📊 Full Indicator Table** — every ticker with EMA relationship, MACD direction, volume ratio, BB position, ATR, and buy/sell score bars.

---

## Backtesting Guide

```bash
python main.py --mode backtest --ticker RELIANCE
```

### Simulation Rules

| Rule | Detail |
|---|---|
| Entry | Next candle's **Open** price (prevents look-ahead bias) |
| Stop-Loss | Checked against intraday **Low** |
| Take-Profit | Checked against intraday **High** |
| Tie-break | Take-profit wins if both hit on same candle |
| Brokerage | 0.03% per leg (Zerodha flat fee model) |
| STT | 0.1% Securities Transaction Tax on sell leg |
| Slippage | 0.05% per leg |
| Position sizing | Same fixed-fractional formula as live system |
| Capital | ₹10,00,000 default (change with `--capital`) |

### Sample Output

```
📊 Backtest — BAJFINANCE
┌─────────────────────────┬──────────────────────────┬──────────────────────────┐
│ Metric                  │ Strategy                 │ NIFTY 50 B&H             │
├─────────────────────────┼──────────────────────────┼──────────────────────────┤
│ Initial Capital         │ ₹  1,000,000.00          │ ₹  1,000,000.00          │
│ Final Equity            │ ₹  1,021,425.56          │ ₹    749,372.79          │
│ Net P&L                 │ ₹    +21,425 (+2.14%)    │ ₹-250,627 (-25.06%)      │
│ Total Trades            │ 30                       │                          │
│ Win Rate                │ 36.7% (11W / 19L)        │                          │
│ Profit Factor           │ 1.55                     │                          │
│ Max Drawdown            │ 1.01%                    │ 45.25%                   │
│ Sharpe Ratio            │ 1.924                    │ -0.616                   │
│ Avg Win / Loss          │ +₹5,460 / -₹2,033        │                          │
│ Avg Hold (days)         │ 8.2                      │                          │
└─────────────────────────┴──────────────────────────┴──────────────────────────┘
```

> The Sharpe ratio is computed only on active-trade days (days when equity actually moved), not flat no-position days, to avoid distortion.

### Multi-Ticker Summary

```bash
python main.py --mode backtest --all --capital 1000000
```

```
📊 Watchlist Backtest Summary
┌──────────────┬────────┬───────┬────────────┬──────────┬────────┬────────┐
│ Ticker       │ Trades │ Win%  │ Net P&L    │ P.Factor │ MaxDD% │ Sharpe │
├──────────────┼────────┼───────┼────────────┼──────────┼────────┼────────┤
│ BAJFINANCE   │ 30     │ 36.7% │ +2.14%     │ 1.55     │ 1.01%  │ 1.924  │
│ RELIANCE     │ 22     │ 40.9% │ +1.87%     │ 1.42     │ 0.89%  │ 1.651  │
│ TCS          │ 18     │ 38.9% │ +0.94%     │ 1.21     │ 1.23%  │ 0.872  │
│ ...          │ ...    │ ...   │ ...        │ ...      │ ...    │ ...    │
└──────────────┴────────┴───────┴────────────┴──────────┴────────┴────────┘
```

---

## Portfolio Tracker

```bash
python main.py --mode portfolio
```

### KPI Panels

```
╭─ 💰 Total P&L ──────╮ ╭─ ✅ Realised ──╮ ╭─ ⏳ Unrealised ─╮ ╭─ 💵 Free Cash ──╮
│  ₹+12,450 (+1.25%)  │ │  ₹+8,200       │ │  ₹+4,250        │ │  ₹7,82,550      │
╰─────────────────────╯ ╰────────────────╯ ╰─────────────────╯ ╰─────────────────╯
```

### ASCII Equity Curve

```
📈 Equity Curve
│████████████████████████████████████████████████████████████   ₹ 10,21,425
│███████████████████████████████████████████████████████
│██████████████████████████████████████████████████
│████████████████████████████████████████████
│██████████████████████████████████                             ₹  9,98,200
│███████████████████████████████
│████████████████████████
│███████████████████████
│██████████████████████                                         ₹  9,85,000
└──────────────────────────────────────────────────────────────
  2023-01-02                                          2025-05-22
```

---

## Live Data Sources

The system tries three sources in order for every ticker:

### Priority 1 — nsepython (NSE website)

Uses the official NSE website's API via a session-based client. Most accurate, direct from the exchange. Requires internet and an active NSE session.

```python
from nsepython import nsefetch
data = nsefetch("https://www.nseindia.com/api/quote-equity?symbol=RELIANCE")
```

### Priority 2 — yfinance with `.NS` suffix

Yahoo Finance pulls NSE data using the `.NS` suffix (e.g., `RELIANCE.NS`). Reliable for historical data, occasionally delayed for live prices.

```python
import yfinance as yf
df = yf.Ticker("RELIANCE.NS").history(period="6mo", interval="1d")
```

### Priority 3 — GBM Simulator (offline fallback)

When neither of the above sources is reachable (no internet, API down, rate-limited), the system generates **realistic synthetic NSE data** using Geometric Brownian Motion. Each ticker has a hardcoded base price in `settings.py` and a deterministic seed so the same ticker always produces the same historical series. This means the system always runs, even completely offline — useful for demos, development, and testing.

```
[RELIANCE] Source: NSE Simulator (demo/offline mode) | 180 days
[TCS]      Source: NSE Simulator (demo/offline mode) | 180 days
```

> **No data source failures will crash the system.** The simulator is always the last resort.

---

## Broker Integration

### Default — Paper Trading

No setup needed. All orders are simulated with a UUID order ID and stored in the SQLite database. Use this to validate the system's behaviour before connecting real money.

```
📄 PAPER ORDER | BUY RELIANCE × 33 @ ₹2,950.00 | SL ₹2,891.00 | TP ₹3,127.00 | ID=PAPER-A3F2B1C4D5E6
```

### Live — Zerodha Kite Connect

1. Create an account at [zerodha.com](https://zerodha.com)
2. Subscribe to Kite Connect at [kite.trade](https://kite.trade) (₹2,000/month)
3. Get your API key and secret from the developer console
4. Generate an access token daily after market open (Zerodha tokens expire daily)

```python
# settings.py
ZERODHA_API_KEY      = "abc123xyz"
ZERODHA_API_SECRET   = "def456uvw"
ZERODHA_ACCESS_TOKEN = "ghi789rst"   # regenerate daily
```

The system places **bracket orders** — a single API call that atomically creates:
- Entry order (market)
- Stop-loss trigger order
- Take-profit limit order

The stop-loss and take-profit legs are OCO (One Cancels Other): whichever triggers first automatically cancels the other. Zerodha manages this on their side.

> ⚠️ **Paper trading is the default.** Zerodha executes only when `ZERODHA_API_KEY` is non-empty in `settings.py` AND you explicitly enable it in `execution_bridge.py` by setting `use_zerodha=True`.

---

## Telegram Notifications

### Setup

1. Open Telegram → search for **@BotFather** → start a chat
2. Send `/newbot` → follow the prompts → copy the **API token**
3. Start a conversation with your new bot (send it any message)
4. Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. In the JSON response, find `"chat": {"id": 123456789}` — copy that number

```python
# settings.py
TELEGRAM_BOT_TOKEN = "7412345678:AAFxyz..."
TELEGRAM_CHAT_ID   = "123456789"
```

### What You Receive

**On new BUY signal:**
```
🟢 SIGNAL #12 — BAJFINANCE
━━━━━━━━━━━━━━━━━━
📊 Direction:   BUY
💰 Entry:       ₹9,142.50
🛑 Stop Loss:   ₹8,959.65 (-2.0%)
🎯 Target:      ₹9,691.05 (+6.0%)
━━━━━━━━━━━━━━━━━━
📦 Shares:      10
💵 Value:       ₹91,425
⚠️  Risk:       ₹1,828
📈 Reward:      ₹5,485
⚖️  R:R:        1:3.0
🎯 Score:       80/100
━━━━━━━━━━━━━━━━━━
👉 Dashboard: http://localhost:8501
```

**On order executed:** Confirmation with broker order ID.

**On signal denied:** Denial confirmation with your reason note.

---

## Test Suite

```bash
python tests.py
```

**91 tests across 8 modules:**

| Section | Tests | Covers |
|---|---|---|
| 1. Settings | 11 | Risk params within safe bounds, watchlist valid |
| 2. Data Ingestion | 11 | Validator, simulator, fetch fallback |
| 3. Strategy Engine | 12 | Indicators, RSI bounds, signal output types |
| 4. Risk Management | 12 | Position sizing, all 7 guardrails |
| 5. Database | 7 | Insert, update, retrieve, trade recording |
| 6. Execution Bridge | 6 | Paper broker, execute, deny, failure recovery |
| 7. Backtest Engine | 9 | Returns valid metrics, equity curve |
| 8. End-to-End | 9 | Full pipeline for RELIANCE, TCS, HDFCBANK |

No external dependencies needed to run tests — uses Python's built-in `unittest.mock`.

---

## Troubleshooting

### "yfinance returns empty data / HTTP 403"

This is normal. Yahoo Finance rate-limits aggressively, especially from cloud/sandbox environments. The system automatically falls back to the GBM simulator. In production on your own machine this issue is much less common.

**Fix:** The system handles this automatically — no action needed.

### "NSE market is CLOSED — scan skipped"

The scanner respects NSE trading hours (9:15 AM – 3:30 PM IST, Monday–Friday). Outside those hours, scans are skipped by default.

**Fix:** Use `--no-gate` flag to override:
```bash
python main.py --mode scan-once --no-gate
python main.py --mode demo        # demo mode never checks market hours
```

### "Streamlit not found"

```bash
pip install streamlit
```

### "ModuleNotFoundError: No module named 'pandas_ta'"

```bash
pip install pandas-ta==0.3.14b0
```

### "Access token expired" (Zerodha)

Zerodha access tokens expire every day at midnight. You need to regenerate one each morning before trading hours.

**Temporary fix:**
```python
# Update settings.py each morning:
ZERODHA_ACCESS_TOKEN = "new_token_here"
```

**Automated fix:** Set up a daily cron job using the Kite Connect login flow to auto-regenerate the token.

### "Telegram messages not sending"

1. Confirm the bot token and chat ID are correct in `settings.py`
2. Make sure you started a conversation with your bot on Telegram first
3. Check that `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` are both non-empty

### Signals never fire during scan

Possible reasons:
- The simulated data for today doesn't happen to produce crossing conditions (expected sometimes — no signal is a valid output)
- The minimum confidence threshold (60) is set too high — try lowering to 50 in `settings.py`
- Run the screener to see near-signal tickers: `python main.py --mode screen`

### Port 8501 already in use

```bash
python main.py --mode dashboard   # uses 8501 by default
# or change the port in settings.py:
# dashboard_port: int = 8502
```

---

## Disclaimer

> This software is for **educational and research purposes only**. It does not constitute financial advice, investment advice, or a solicitation to trade. Past backtest performance does not guarantee future results. All trading involves risk of loss. The authors and contributors accept no responsibility for any financial losses incurred through the use of this software. Always paper-trade extensively before considering any live deployment. Consult a SEBI-registered investment advisor before making real investment decisions.
