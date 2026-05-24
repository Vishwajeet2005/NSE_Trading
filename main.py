"""
main.py — NSE Semi-Autonomous Trading System
=============================================
Single entry point. All modes via CLI.

  python main.py                            full system (scanner + dashboard)
  python main.py --mode demo               one scan + dashboard, no gate
  python main.py --mode scan-once          single scan, exit
  python main.py --mode scanner            scheduled scanner only
  python main.py --mode dashboard          Streamlit dashboard only
  python main.py --mode backtest           backtest RELIANCE (default)
  python main.py --mode backtest --ticker TCS
  python main.py --mode backtest --all     all 20 watchlist tickers
  python main.py --mode screen             full indicator screener
  python main.py --mode screen --ticker INFY TCS
  python main.py --mode portfolio          paper portfolio P&L report
  python main.py --mode portfolio --equity equity curve in terminal
  python main.py --init-db                 initialise DB and exit
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import os
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from backend.core import logger as log_mod
from backend.core import database as db
from backend.core.settings import BACKTEST, NSE_WATCHLIST, SYSTEM

log     = log_mod.get(__name__)
console = Console()

# ─── Banner ──────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║      NSE SEMI-AUTONOMOUS TRADING SYSTEM  v1.0                ║
║      Rule-Based · Human-in-the-Loop · Zero Black Boxes       ║
╠══════════════════════════════════════════════════════════════╣
║  Exchange   :  National Stock Exchange of India (NSE)        ║
║  Currency   :  Indian Rupee (₹)                              ║
║  Data       :  nsepython  →  yfinance .NS  →  Simulator      ║
║  Broker     :  Paper Trading (default) │ Zerodha Kite        ║
║  Execution  :  HUMAN APPROVAL REQUIRED before any order      ║
╠══════════════════════════════════════════════════════════════╣
║  Config:  Edit  settings.py  to set credentials & risk       ║
╚══════════════════════════════════════════════════════════════╝
"""

def print_banner() -> None:
    console.print(Panel(
        Text(BANNER, style="bold cyan", justify="center"),
        border_style="cyan", expand=False,
    ))

def print_modes() -> None:
    t = Table(title="Available Modes", box=box.SIMPLE_HEAVY,
              header_style="bold cyan", show_header=True)
    t.add_column("Mode",        style="bold yellow", width=14)
    t.add_column("Command",     style="bright_white", width=40)
    t.add_column("Description", style="dim",          width=36)
    rows = [
        ("full",      "python main.py",                          "Scanner + Dashboard (default)"),
        ("demo",      "python main.py --mode demo",              "One scan + Dashboard, no market gate"),
        ("scan-once", "python main.py --mode scan-once",         "Single scan pass and exit"),
        ("scanner",   "python main.py --mode scanner",           "Scheduled scanner only"),
        ("dashboard", "python main.py --mode dashboard",         "Streamlit dashboard only"),
        ("backtest",  "python main.py --mode backtest --ticker RELIANCE", "Backtest one ticker"),
        ("backtest",  "python main.py --mode backtest --all",    "Backtest all 20 tickers"),
        ("screen",    "python main.py --mode screen",            "Full indicator screener"),
        ("portfolio", "python main.py --mode portfolio",         "Paper P&L tracker"),
        ("tests",     "python tests.py",                         "Run 91-test suite"),
    ]
    for mode, cmd, desc in rows:
        t.add_row(mode, cmd, desc)
    console.print(t)

# ─── Mode runners ─────────────────────────────────────────────────────────────

def run_web() -> None:
    log.info("Launching Web App (FastAPI + React)")
    api_cmd = [sys.executable, "-m", "uvicorn", "backend.api.routes:app", "--port", "8000"]
    api_proc = subprocess.Popen(api_cmd, cwd=os.path.dirname(__file__))
    
    frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
    npm_cmd = ["npm", "run", "dev"]
    shell = os.name == "nt"
    ui_proc = subprocess.Popen(npm_cmd, cwd=frontend_dir, shell=shell)
    
    try:
        api_proc.wait()
        ui_proc.wait()
    except KeyboardInterrupt:
        api_proc.terminate()
        ui_proc.terminate()

def run_dashboard() -> None:
    log.info("Launching Streamlit dashboard → http://127.0.0.1:%d", SYSTEM.dashboard_port)
    cmd = [
        sys.executable, "-m", "streamlit", "run",
        os.path.join(os.path.dirname(__file__), "dashboard.py"),
        "--server.port",             str(SYSTEM.dashboard_port),
        "--server.address",          "127.0.0.1",
        "--server.headless",         "true",
        "--browser.gatherUsageStats","false",
    ]
    subprocess.run(cmd, check=False)


def run_scanner(interval: int = SYSTEM.scanner_interval_min,
                require_market: bool = True) -> None:
    from backend.modes.scanner import start_scanner
    start_scanner(interval_min=interval, require_market=require_market)


def run_scan_once(require_market: bool = False) -> None:
    db.init()
    from backend.modes.scanner import LiveScanner
    LiveScanner(require_market=require_market).run_pass()


def run_backtest(ticker: str | None, all_tickers: bool, capital: float) -> None:
    from backend.modes.backtest import BacktestEngine, nifty_benchmark, print_report
    tickers = NSE_WATCHLIST if all_tickers else (
        [ticker.upper()] if ticker else ["RELIANCE"]
    )
    engine  = BacktestEngine(capital=capital)
    bench   = nifty_benchmark(capital)
    results = []

    for t in tickers:
        try:
            r = engine.run(t)
            print_report(r, bench if t == tickers[0] else None)
            results.append(r)
        except Exception as exc:
            log.error("Backtest failed for %s: %s", t, exc)

    # Multi-ticker summary table
    if len(results) > 1:
        st = Table(title="📊 Watchlist Backtest Summary",
                   box=box.ROUNDED, header_style="bold cyan")
        for col in ["Ticker","Trades","Win%","Net P&L","P.Factor","MaxDD%","Sharpe"]:
            st.add_column(col, width=14)
        for r in results:
            c = "bright_green" if r.net_pnl_inr >= 0 else "bright_red"
            st.add_row(
                r.ticker, str(r.n_trades),
                f"{r.win_rate:.1f}%",
                f"[{c}]{r.net_pnl_pct:+.2f}%[/{c}]",
                f"{r.profit_factor:.2f}",
                f"{r.max_drawdown:.2f}%",
                f"{r.sharpe:.3f}",
            )
        console.print(st)


def run_screen(tickers: list[str] | None = None) -> None:
    from backend.modes.screener import run_screen as _screen
    _screen(tickers or NSE_WATCHLIST)


def run_portfolio(args: argparse.Namespace) -> None:
    from backend.modes.portfolio import Portfolio
    from backend.modes.portfolio import (print_portfolio_summary, print_open_positions,
                           print_closed_trades, print_ticker_breakdown,
                           print_equity_curve, print_daily_pnl)
    pf = Portfolio()

    show_all = not any([args.open, args.history, args.equity, args.daily])
    console.rule("[bold cyan]NSE PAPER PORTFOLIO — "
                 f"{__import__('datetime').datetime.now().strftime('%d %b %Y %H:%M IST')}[/bold cyan]")

    if show_all or args.open:
        print_portfolio_summary(pf)
        console.print()
        print_open_positions(pf)
        console.print()
    if show_all or args.history:
        print_closed_trades(pf)
        console.print()
        print_ticker_breakdown(pf)
        console.print()
    if show_all or args.daily:
        print_daily_pnl(pf)
        console.print()
    if show_all or args.equity:
        print_equity_curve(pf)


def run_demo() -> None:
    log.info("DEMO MODE — market-hours gate disabled")
    db.init()
    t = threading.Thread(
        target=run_scan_once,
        kwargs={"require_market": False},
        daemon=True, name="DemoScan",
    )
    t.start()
    t.join(timeout=180)
    log.info("Demo scan done. Launching dashboard…")
    run_dashboard()


def run_full(interval: int = SYSTEM.scanner_interval_min,
             require_market: bool = True) -> None:
    db.init()
    scanner_thread = threading.Thread(
        target=run_scanner,
        kwargs={"interval": interval, "require_market": require_market},
        daemon=True, name="ScannerThread",
    )
    scanner_thread.start()
    log.info("Scanner thread started. Launching dashboard in 3s…")
    time.sleep(3)
    run_dashboard()
    log.info("Dashboard closed — shutting down.")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="NSE Semi-Autonomous Stock Analysis System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--mode",
        choices=["full","demo","dashboard","web","scanner","scan-once",
                 "backtest","screen","portfolio"],
        default="full",
        help="Operational mode (default: full)",
    )
    # Backtest options
    p.add_argument("--ticker",   nargs="+", type=str, default=None,
                   help="NSE symbol(s) for backtest or screen")
    p.add_argument("--all",      action="store_true",
                   help="Backtest all watchlist tickers")
    p.add_argument("--capital",  type=float, default=BACKTEST.initial_capital,
                   help=f"Starting capital ₹ (default {BACKTEST.initial_capital:,.0f})")
    # Scanner options
    p.add_argument("--interval", type=int, default=SYSTEM.scanner_interval_min,
                   help="Scanner interval in minutes")
    p.add_argument("--no-gate",  action="store_true",
                   help="Disable NSE market-hours check")
    # Portfolio options
    p.add_argument("--open",     action="store_true", help="Show open positions")
    p.add_argument("--history",  action="store_true", help="Show closed trades")
    p.add_argument("--equity",   action="store_true", help="Show ASCII equity curve")
    p.add_argument("--daily",    action="store_true", help="Show daily P&L")
    # System
    p.add_argument("--init-db",  action="store_true", help="Initialise DB and exit")
    return p


def main() -> None:
    print_banner()
    args    = build_parser().parse_args()
    req_mkt = not args.no_gate

    db.init()

    if args.init_db:
        log.info("Database initialised at %s", SYSTEM.db_path)
        return

    if args.mode == "full":
        run_full(args.interval, req_mkt)
    elif args.mode == "demo":
        run_demo()
    elif args.mode == "dashboard":
        run_dashboard()
    elif args.mode == "web":
        run_web()
    elif args.mode == "scanner":
        run_scanner(args.interval, req_mkt)
    elif args.mode == "scan-once":
        run_scan_once(require_market=False)
    elif args.mode == "backtest":
        first_ticker = args.ticker[0] if args.ticker else None
        run_backtest(first_ticker, args.all, args.capital)
    elif args.mode == "screen":
        tickers = [t.upper() for t in args.ticker] if args.ticker else None
        run_screen(tickers)
    elif args.mode == "portfolio":
        run_portfolio(args)

    if args.mode not in ("full","demo","dashboard","web","scanner"):
        console.print()
        print_modes()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Shutdown requested (Ctrl+C).")
    except Exception as exc:
        log.critical("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)
