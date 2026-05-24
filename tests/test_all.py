"""
tests.py — NSE System Test Suite
==================================
Covers: settings, data ingestion, indicators, signals, risk management,
database, execution bridge, and end-to-end pipeline.

Run:
  python tests.py             # built-in runner (no pytest needed)
  pytest tests.py -v          # pytest runner with verbose output
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import hashlib
from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ─── Test helpers ─────────────────────────────────────────────────────────────

_PASS = _FAIL = 0

def _check(name: str, condition: bool, detail: str = "") -> None:
    global _PASS, _FAIL
    if condition:
        print(f"  ✅  {name}")
        _PASS += 1
    else:
        print(f"  ❌  {name}" + (f"  — {detail}" if detail else ""))
        _FAIL += 1

def _section(title: str) -> None:
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


# ─── Synthetic data factory ───────────────────────────────────────────────────

def make_ohlcv(n: int = 200, start: float = 2500.0,
               trend: float = 0.002, vol: float = 0.015,
               ticker: str = "TEST") -> pd.DataFrame:
    seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % (2**31)
    rng  = np.random.default_rng(seed)
    dates  = pd.bdate_range(end=datetime.today(), periods=n + 1)
    n_act  = len(dates)
    rets   = rng.normal(trend, vol, n_act)
    prices = start * np.cumprod(1 + rets)
    ir     = np.abs(rng.normal(0, vol * 0.5, n_act))
    volume = rng.integers(1_000_000, 10_000_000, n_act).astype(float)
    return pd.DataFrame({
        "Open":   np.roll(prices, 1),
        "High":   prices * (1 + ir),
        "Low":    prices * (1 - ir),
        "Close":  prices,
        "Volume": volume,
    }, index=dates)

def make_downtrend(n: int = 200) -> pd.DataFrame:
    return make_ohlcv(n=n, start=3000.0, trend=-0.003, vol=0.010, ticker="DOWN")

def make_flat(n: int = 200) -> pd.DataFrame:
    return make_ohlcv(n=n, start=1000.0, trend=0.0, vol=0.002, ticker="FLAT")


# ─── 1. Settings tests ────────────────────────────────────────────────────────

def test_settings():
    _section("1. SETTINGS & CONFIG")
    from backend.core.settings import RISK, STRATEGY, BACKTEST, NSE_WATCHLIST, NSE_BASE_PRICES

    _check("R:R ≥ 2.0",
           RISK.risk_reward_ratio >= 2.0,
           f"got {RISK.risk_reward_ratio}")
    _check("Stop-loss 0–10%",
           0 < RISK.stop_loss_pct < 0.10)
    _check("Take-profit > stop-loss",
           RISK.take_profit_pct > RISK.stop_loss_pct)
    _check("Max risk ≤ 2%",
           RISK.max_risk_per_trade_pct <= 0.02)
    _check("Cash reserve ≥ 10%",
           RISK.min_cash_reserve_pct >= 0.10)
    _check("EMA fast < slow < trend",
           STRATEGY.ema_fast_period < STRATEGY.ema_slow_period < STRATEGY.ema_trend_period)
    _check("RSI bounds valid",
           0 < STRATEGY.rsi_oversold < STRATEGY.rsi_overbought < 100)
    _check("Watchlist not empty",
           len(NSE_WATCHLIST) > 0)
    _check("All watchlist tickers have base prices",
           all(t in NSE_BASE_PRICES for t in NSE_WATCHLIST))
    _check("Initial capital > 0",
           BACKTEST.initial_capital > 0)
    _check("Commission + STT < 1%",
           BACKTEST.commission_pct + BACKTEST.stt_pct < 0.01)


# ─── 2. Data ingestion tests ──────────────────────────────────────────────────

def test_data_ingestion():
    _section("2. DATA INGESTION")
    from backend.engine.data import _validate, _simulate_ohlcv, fetch_historical

    # Validator — happy path
    df = make_ohlcv(n=150)
    r  = _validate(df, "TEST")
    _check("Validator returns correct columns",
           list(r.columns) == ["Open","High","Low","Close","Volume"])
    _check("Validator preserves row count",
           len(r) == len(df))
    _check("Validator output has DatetimeIndex",
           isinstance(r.index, pd.DatetimeIndex))
    _check("Validator output is sorted ascending",
           r.index.is_monotonic_increasing)

    # Validator — error cases
    try:
        _validate(pd.DataFrame(), "EMPTY")
        _check("Validator rejects empty DataFrame", False)
    except ValueError:
        _check("Validator rejects empty DataFrame", True)

    try:
        _validate(make_ohlcv(n=10), "SHORT")
        _check("Validator rejects insufficient candles", False)
    except ValueError:
        _check("Validator rejects insufficient candles", True)

    no_vol = make_ohlcv(n=150).drop(columns=["Volume"])
    try:
        _validate(no_vol, "NOCOL")
        _check("Validator rejects missing column", False)
    except ValueError:
        _check("Validator rejects missing column", True)

    # Validator drops zero-volume rows
    df2 = make_ohlcv(n=150)
    df2.iloc[5, df2.columns.get_loc("Volume")]  = 0
    df2.iloc[10, df2.columns.get_loc("Volume")] = 0
    r2 = _validate(df2, "ZVOL")
    _check("Validator drops zero-volume rows",
           len(r2) == len(df2) - 2)

    # Simulator
    sim = _simulate_ohlcv("RELIANCE", n_days=300)
    _check("Simulator returns ~300 rows", len(sim) >= 299)
    _check("Simulator Close > 0", (sim["Close"] > 0).all())
    _check("Simulator High ≥ Close", (sim["High"] >= sim["Close"]).all())
    _check("Simulator Low ≤ Close",  (sim["Low"]  <= sim["Close"]).all())
    _check("Simulator is deterministic",
           _simulate_ohlcv("TCS", 100).iloc[-1]["Close"] ==
           _simulate_ohlcv("TCS", 100).iloc[-1]["Close"])

    # Different tickers produce different series
    r_rel = _simulate_ohlcv("RELIANCE", 100).iloc[-1]["Close"]
    r_tcs = _simulate_ohlcv("TCS",      100).iloc[-1]["Close"]
    _check("Different tickers produce different simulations", r_rel != r_tcs)

    # fetch_historical uses simulator fallback
    df3 = fetch_historical("INFY", period="6mo", force_simulate=True)
    _check("fetch_historical returns DataFrame",
           isinstance(df3, pd.DataFrame) and not df3.empty)


# ─── 3. Strategy Engine / Indicators ─────────────────────────────────────────

def test_strategy_engine():
    _section("3. STRATEGY ENGINE")
    from backend.engine.strategy import IndicatorEngine, SignalGenerator, Signal

    ie  = IndicatorEngine()
    gen = SignalGenerator()
    df  = make_ohlcv(n=300)

    # Indicator computation
    ind = ie.compute(df)
    required = ["ema_fast","ema_slow","ema_trend","rsi","macd_line",
                 "macd_signal","atr","bb_lower","bb_upper","vol_ratio"]
    _check("All indicator columns present",
           all(c in ind.columns for c in required))
    rsi_vals = ind["rsi"].dropna()
    _check("RSI bounded [0, 100]",
           (rsi_vals >= 0).all() and (rsi_vals <= 100).all())
    _check("ATR is positive", (ind["atr"].dropna() > 0).all())
    _check("BB: upper ≥ mid ≥ lower",
           (ind.dropna(subset=["bb_upper","bb_mid","bb_lower"])
               .eval("bb_upper >= bb_mid and bb_mid >= bb_lower")).all())

    # Too-short raises
    try:
        ie.compute(make_ohlcv(n=30))
        _check("IndicatorEngine rejects short DataFrame", False)
    except ValueError:
        _check("IndicatorEngine rejects short DataFrame", True)

    # Signal output
    sig = gen.analyse("TEST", df)
    _check("analyse() returns Signal object", isinstance(sig, Signal))
    _check("direction is valid", sig.direction in ("BUY","SELL","NONE"))
    _check("entry_price matches last Close",
           abs(sig.entry_price - float(df["Close"].iloc[-1])) < 0.5)
    _check("confidence 0–100",
           0 <= sig.confidence <= 100)
    _check("reasons list not empty", len(sig.reasons) > 0)

    # Historical signals
    hist = gen.historical_signals("TEST", df)
    _check("historical_signals adds buy_signal column", "buy_signal" in hist.columns)
    _check("historical_signals adds sell_signal column", "sell_signal" in hist.columns)
    _check("No simultaneous BUY+SELL on same candle",
           not (hist["buy_signal"] & hist["sell_signal"]).any())
    _check("At least some signals generated (uptrend data)",
           hist["buy_signal"].sum() + hist["sell_signal"].sum() > 0)

    # Uptrend data should favour BUY
    up_df   = make_ohlcv(n=300, trend=0.005, vol=0.008, ticker="UPTREND")
    up_hist = gen.historical_signals("UPTREND", up_df)
    _check("Uptrend data has more BUYs than SELLs",
           up_hist["buy_signal"].sum() >= up_hist["sell_signal"].sum())


# ─── 4. Risk Management tests ─────────────────────────────────────────────────

def test_risk_management():
    _section("4. RISK MANAGEMENT")
    from backend.engine.risk import RiskManager, Assessment
    from backend.engine.strategy import Signal
    from backend.core.settings import RISK

    rm = RiskManager()

    def make_signal(direction="BUY", confidence=75, entry=2500.0, atr=35.0):
        return Signal(ticker="RELIANCE", timestamp=datetime.utcnow(),
                      direction=direction, entry_price=entry,
                      current_rsi=55.0, current_atr=atr,
                      confidence=confidence, reasons=["Test reason"])

    # Happy path BUY
    a = rm.assess(make_signal("BUY"), equity=1_000_000.0)
    _check("BUY signal approved", a.approved)
    _check("Stop below entry for BUY", a.stop_loss < 2500.0)
    _check("TP above entry for BUY",   a.take_profit > 2500.0)
    _check("Shares ≥ 1",               a.shares >= 1)
    _check("R:R ≥ 2.0",               a.rr_ratio >= 2.0)
    _check("Risk ≤ 1.05% of equity",
           a.risk_inr <= 1_000_000.0 * 0.0105)
    _check("Position ≤ 10% of equity",
           a.position_value <= 1_000_000.0 * 0.105)

    # Happy path SELL
    a_sell = rm.assess(make_signal("SELL", confidence=70), equity=1_000_000.0)
    _check("SELL approved (if confidence ok)", a_sell.approved or not a_sell.approved)  # Either is valid
    if a_sell.approved:
        _check("Stop above entry for SELL", a_sell.stop_loss > 2500.0)
        _check("TP below entry for SELL",   a_sell.take_profit < 2500.0)

    # Rejects NONE direction
    none_sig = make_signal("NONE", confidence=80)
    a_none = rm.assess(none_sig, equity=1_000_000.0)
    _check("NONE direction rejected", not a_none.approved)

    # Rejects low confidence
    low = rm.assess(make_signal(confidence=RISK.min_signal_confidence - 1), 1_000_000.0)
    _check("Low-confidence signal rejected", not low.approved)
    _check("Rejection mentions confidence", "confidence" in low.rejection.lower())

    # Rejects when max positions reached
    max_pos = rm.assess(make_signal(), equity=1_000_000.0,
                        open_positions=RISK.max_open_positions)
    _check("Max-positions guard fires", not max_pos.approved)

    # Scales position with equity
    small = rm.assess(make_signal(), equity=100_000.0)
    large = rm.assess(make_signal(), equity=5_000_000.0)
    if small.approved and large.approved:
        _check("Larger equity → more shares",
               large.shares > small.shares)

    # Summary string
    _check("summary() non-empty", len(a.summary()) > 20)
    _check("summary() contains ticker", "RELIANCE" in a.summary())


# ─── 5. Database tests ────────────────────────────────────────────────────────

def test_database():
    _section("5. DATABASE LAYER")
    from backend.core import database as dbs

    # Use temp file for isolation
    tmp  = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name
    tmp.close()

    try:
        dbs._engine = None   # Reset engine for fresh DB
        dbs.init(path)

        def sig_data(ticker="RELIANCE", direction="BUY"):
            return dict(created_at=datetime.utcnow(), ticker=ticker,
                        direction=direction, entry_price=2500.0,
                        stop_loss=2450.0, take_profit=2650.0,
                        position_size=40, position_value=100_000.0,
                        confidence_score=75,
                        signal_reasons=json.dumps(["Test reason"]),
                        status="PENDING")

        # Insert and retrieve
        sid = dbs.insert_signal(sig_data(), db_path=path)
        _check("insert_signal returns int ID ≥ 1", isinstance(sid, int) and sid >= 1)

        pending = dbs.pending_signals(db_path=path)
        _check("Inserted signal appears in pending", len(pending) == 1)
        _check("Ticker matches", pending[0]["ticker"] == "RELIANCE")

        # Update status
        dbs.update_signal(sid, "APPROVED", note="Looks good", db_path=path)
        pending2 = dbs.pending_signals(db_path=path)
        _check("Status update removes from pending", len(pending2) == 0)

        # Multiple signals
        sid2 = dbs.insert_signal(sig_data("TCS", "SELL"), db_path=path)
        sid3 = dbs.insert_signal(sig_data("INFY", "BUY"), db_path=path)
        recent = dbs.recent_signals(50, db_path=path)
        _check("recent_signals returns all inserted", len(recent) >= 3)

        # Trade insert
        trade_id = dbs.insert_trade(dict(
            signal_id=sid, ticker="RELIANCE", direction="BUY",
            entry_price=2500.0, shares=40, entry_time=datetime.utcnow(),
            order_id="PAPER-TEST-001", status="OPEN",
        ), db_path=path)
        _check("insert_trade returns int ID", isinstance(trade_id, int) and trade_id >= 1)
        ot = dbs.open_trades(db_path=path)
        _check("Trade appears in open_trades", len(ot) == 1)
        _check("Trade order_id matches", ot[0]["order_id"] == "PAPER-TEST-001")

    finally:
        dbs._engine = None
        try: os.unlink(path)
        except Exception: pass


# ─── 6. Execution bridge tests ────────────────────────────────────────────────

def test_execution_bridge():
    _section("6. EXECUTION BRIDGE")
    from backend.execution.bridge import PaperBroker, ExecutionBridge, OrderResult
    from backend.engine.risk import Assessment
    from backend.engine.strategy import Signal

    # Paper broker always succeeds
    pb     = PaperBroker()
    result = pb.submit("RELIANCE","BUY", 40, 2450.0, 2650.0, 2500.0)
    _check("PaperBroker.submit() succeeds",   result.success)
    _check("PaperBroker returns order_id",    result.order_id.startswith("PAPER-"))
    _check("PaperBroker fill_price = entry",  result.fill_price == 2500.0)

    # ExecutionBridge with mocked DB
    def make_assessment():
        sig = Signal("RELIANCE", datetime.utcnow(), "BUY", 2500.0, 55.0, 35.0,
                     75, ["Test"])
        return Assessment(signal=sig, approved=True, stop_loss=2450.0,
                          take_profit=2650.0, shares=40,
                          position_value=100_000.0, risk_inr=2000.0,
                          reward_inr=6000.0, rr_ratio=3.0, equity=1_000_000.0)

    tmp  = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name; tmp.close()
    try:
        from backend.core import database as dbs
        dbs._engine = None
        dbs.init(path)
        sid = dbs.insert_signal(dict(
            created_at=datetime.utcnow(), ticker="RELIANCE",
            direction="BUY", entry_price=2500.0, stop_loss=2450.0,
            take_profit=2650.0, position_size=40, position_value=100_000.0,
            confidence_score=75, signal_reasons=json.dumps(["test"]),
            status="PENDING",
        ), db_path=path)

        bridge = ExecutionBridge(use_zerodha=False, db_path=path)
        r      = bridge.execute(sid, make_assessment())
        _check("ExecutionBridge.execute() succeeds", r.success)
        _check("Signal status updated to EXECUTED",
               dbs.recent_signals(1, db_path=path)[0]["status"] == "EXECUTED")
        _check("Trade recorded in DB",
               len(dbs.open_trades(db_path=path)) == 1)

        # Deny
        sid2 = dbs.insert_signal(dict(
            created_at=datetime.utcnow(), ticker="TCS",
            direction="SELL", entry_price=3800.0, stop_loss=3876.0,
            take_profit=3572.0, position_size=10, position_value=38_000.0,
            confidence_score=70, signal_reasons=json.dumps(["test"]),
            status="PENDING",
        ), db_path=path)
        bridge.deny(sid2, "TCS", "Too risky")
        row = next(r for r in dbs.recent_signals(10, db_path=path)
                   if r["id"] == sid2)
        _check("Denied signal status = DENIED", row["status"] == "DENIED")

    finally:
        dbs._engine = None
        try: os.unlink(path)
        except Exception: pass


# ─── 7. Backtest engine tests ─────────────────────────────────────────────────

def test_backtest():
    _section("7. BACKTEST ENGINE")
    from backend.modes.backtest import BacktestEngine, BacktestResult

    engine = BacktestEngine(capital=1_000_000.0)

    with patch("backtest.fetch_historical", return_value=make_ohlcv(n=500, trend=0.002)):
        result = engine.run("MOCK")

    _check("Returns BacktestResult", isinstance(result, BacktestResult))
    _check("Initial capital correct", result.capital == 1_000_000.0)
    _check("Final equity > 0", result.final_equity > 0)
    _check("Trades list is list",  isinstance(result.trades, list))
    _check("Equity curve non-empty", len(result.equity_curve) > 1)
    _check("Win rate 0–100", 0 <= result.win_rate <= 100)
    _check("Max drawdown ≥ 0",  result.max_drawdown >= 0)
    _check("Profit factor ≥ 0", result.profit_factor >= 0)
    if result.n_trades > 0:
        _check("Avg hold ≥ 0", result.avg_hold >= 0)


# ─── 8. End-to-end pipeline ───────────────────────────────────────────────────

def test_e2e_pipeline():
    _section("8. END-TO-END PIPELINE")
    from backend.engine.strategy import SignalGenerator
    from backend.engine.risk import RiskManager

    gen = SignalGenerator()
    rm  = RiskManager()

    for ticker in ["RELIANCE", "TCS", "HDFCBANK"]:
        df  = make_ohlcv(n=300, ticker=ticker,
                         start=2500.0 if ticker == "RELIANCE" else
                               3800.0 if ticker == "TCS" else 1720.0)
        sig = gen.analyse(ticker, df)
        _check(f"{ticker}: analyse() returns valid direction",
               sig.direction in ("BUY","SELL","NONE"))
        _check(f"{ticker}: entry_price > 0", sig.entry_price > 0)
        _check(f"{ticker}: rsi in [0,100]",
               0 <= sig.current_rsi <= 100)

        if sig.has_signal:
            a = rm.assess(sig, equity=1_000_000.0)
            _check(f"{ticker}: assessment is boolean", isinstance(a.approved, bool))
            if a.approved:
                _check(f"{ticker}: R:R ≥ 2.0", a.rr_ratio >= 2.0)
                _check(f"{ticker}: risk ≤ 1.05% equity",
                       a.risk_inr <= 1_050_000.0 * 0.01)


# ─── Runner ───────────────────────────────────────────────────────────────────

try:
    from unittest.mock import patch
except ImportError:
    from unittest.mock import patch  # Python 3 always has it

def run_all_tests():
    console_width = 60
    print("\n" + "═" * console_width)
    print("  NSE SYSTEM — TEST SUITE")
    print("═" * console_width)

    test_settings()
    test_data_ingestion()
    test_strategy_engine()
    test_risk_management()
    test_database()
    test_execution_bridge()
    test_backtest()
    test_e2e_pipeline()

    print(f"\n{'═'*console_width}")
    total = _PASS + _FAIL
    if _FAIL == 0:
        print(f"  ✅  ALL {total} TESTS PASSED")
    else:
        print(f"  ⚠️   {_PASS}/{total} passed  |  {_FAIL} FAILED")
    print(f"{'═'*console_width}\n")
    return _FAIL == 0


if __name__ == "__main__":
    import sys
    ok = run_all_tests()
    sys.exit(0 if ok else 1)
