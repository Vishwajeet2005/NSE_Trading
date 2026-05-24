"""
scanner.py — Live NSE Watchlist Scanner
=========================================
Scans every ticker in NSE_WATCHLIST on a configurable schedule.
Only runs during NSE market hours (9:15 AM – 3:30 PM IST, Mon–Fri).

For each ticker:
  1. Fetch latest OHLCV (nsepython → yfinance → simulator)
  2. Run StrategyEngine → get Signal
  3. Run RiskManager   → get Assessment
  4. If approved: persist to DB + notify operator
  5. Awaits human APPROVE/DENY in dashboard

Run standalone:
  python scanner.py               # scheduled every 60 min
  python scanner.py --once        # single pass and exit
  python scanner.py --no-gate     # ignore market hours (testing)
  python scanner.py --interval 30 # every 30 minutes
"""
from __future__ import annotations

import argparse
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger

from backend.core import database as db
from backend.core import logger as log_mod
from backend.engine.data import fetch_historical, fetch_live_quote
from backend.execution.bridge import PaperBroker
from backend.core.notification import ConsoleNotifier, NotificationService
from backend.engine.risk import RiskManager
from backend.core.settings import NSE_WATCHLIST, RISK, STRATEGY, SYSTEM
from backend.engine.strategy import SignalGenerator

log = log_mod.get(__name__)
IST = pytz.timezone(SYSTEM.market_timezone)


# ─── Market-hours gate ────────────────────────────────────────────────────────

def market_is_open() -> bool:
    """Return True only during NSE trading session (IST Mon–Fri 9:15–15:30)."""
    now = datetime.now(IST)
    if now.weekday() >= 5:  # Saturday / Sunday
        return False
    open_  = now.replace(hour=SYSTEM.market_open_hour,
                          minute=SYSTEM.market_open_minute, second=0, microsecond=0)
    close  = now.replace(hour=SYSTEM.market_close_hour,
                          minute=SYSTEM.market_close_minute, second=0, microsecond=0)
    return open_ <= now <= close


# ─── Core scanner ─────────────────────────────────────────────────────────────

class LiveScanner:
    """
    Orchestrates a full watchlist scan pass.

    Parameters
    ----------
    watchlist         : NSE symbols to scan (no .NS suffix)
    require_market    : Skip scans when NSE is closed
    db_path           : SQLite database path
    """

    def __init__(
        self,
        watchlist: list[str] | None = None,
        require_market: bool = True,
        db_path: str = "nse_signals.db",
    ) -> None:
        self.watchlist      = watchlist or NSE_WATCHLIST
        self.require_market = require_market
        self.db_path        = db_path
        self._gen           = SignalGenerator()
        self._rm            = RiskManager()
        self._notifier      = NotificationService()
        self._broker        = PaperBroker()
        log.info("LiveScanner ready | %d tickers | market_gate=%s",
                 len(self.watchlist), require_market)

    def _scan_one(self, ticker: str, equity: float, open_pos: int) -> str:
        """
        Analyse one ticker and return its signal direction string.

        Returns
        -------
        "BUY" | "SELL" | "BLOCKED" | "NONE" | "ERROR"
        """
        try:
            # Fetch OHLCV
            ohlcv  = fetch_historical(
                ticker, period=STRATEGY.live_period, interval=STRATEGY.interval)

            # Strategy signal
            signal = self._gen.analyse(ticker, ohlcv)
            if not signal.has_signal:
                return "NONE"

            # Risk assessment
            assessment = self._rm.assess(signal, equity, open_pos)
            if not assessment.approved:
                log.info("[%s] BLOCKED: %s", ticker, assessment.rejection)
                return "BLOCKED"

            # Persist signal
            signal_id = db.insert_signal({
                "created_at":      datetime.utcnow(),
                "ticker":          ticker,
                "direction":       signal.direction,
                "entry_price":     signal.entry_price,
                "stop_loss":       assessment.stop_loss,
                "take_profit":     assessment.take_profit,
                "position_size":   assessment.shares,
                "position_value":  assessment.position_value,
                "confidence_score": signal.confidence,
                "signal_reasons":  json.dumps(signal.reasons),
                "status":          "PENDING",
            }, db_path=self.db_path)

            # Notify operator
            self._notifier.notify_signal(assessment, signal_id)
            return signal.direction

        except Exception as exc:
            log.error("[%s] Scan error: %s", ticker, exc, exc_info=True)
            return "ERROR"

    def run_pass(self) -> dict[str, str]:
        """
        Execute a complete scan over all watchlist tickers.

        Returns
        -------
        dict[ticker → direction_string]
        """
        ts = datetime.now(IST).strftime("%d %b %Y %H:%M IST")
        log.info("=" * 55)
        log.info("SCAN PASS  —  %s  |  %d tickers", ts, len(self.watchlist))
        log.info("=" * 55)

        if self.require_market and not market_is_open():
            log.info("NSE market is CLOSED — scan skipped. Use --no-gate to override.")
            return {}

        equity   = self._broker.account_equity()
        open_pos = len(db.open_trades(db_path=self.db_path))
        log.info("Account equity: ₹%s | Open positions: %d/%d",
                 f"{equity:,.0f}", open_pos, RISK.max_open_positions)

        results: dict[str, str] = {}
        for ticker in self.watchlist:
            direction = self._scan_one(ticker, equity, open_pos)
            results[ticker] = direction
            if direction in ("BUY", "SELL"):
                open_pos += 1  # pessimistic counter

        buys   = sum(1 for d in results.values() if d == "BUY")
        sells  = sum(1 for d in results.values() if d == "SELL")
        log.info("Scan done | BUY=%d SELL=%d BLOCKED=%d NONE=%d ERR=%d",
                 buys, sells,
                 sum(1 for d in results.values() if d == "BLOCKED"),
                 sum(1 for d in results.values() if d == "NONE"),
                 sum(1 for d in results.values() if d == "ERROR"))

        ConsoleNotifier.show_scan_summary(results, equity)
        return results


# ─── Scheduler ────────────────────────────────────────────────────────────────

def start_scanner(
    interval_min: int = SYSTEM.scanner_interval_min,
    watchlist: list[str] | None = None,
    require_market: bool = True,
    db_path: str = "nse_signals.db",
    run_now: bool = True,
) -> None:
    """
    Start the live scanner with APScheduler (blocks calling thread).

    Parameters
    ----------
    interval_min    : Minutes between scan passes
    watchlist       : Tickers to scan (defaults to NSE_WATCHLIST)
    require_market  : Respect NSE market hours
    db_path         : SQLite path
    run_now         : Run one pass immediately before scheduling
    """
    db.init(db_path)
    scanner = LiveScanner(watchlist, require_market, db_path)

    if run_now:
        log.info("Running immediate scan on startup…")
        scanner.run_pass()

    sched = BlockingScheduler(timezone=IST)
    sched.add_job(
        func=scanner.run_pass,
        trigger=IntervalTrigger(minutes=interval_min),
        id="nse_scan",
        name="NSE Watchlist Scan",
        replace_existing=True,
        max_instances=1,
    )
    log.info("Scheduler running | interval=%d min | next scan in ~%d min",
             interval_min, interval_min)
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scanner stopped.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="NSE Live Watchlist Scanner")
    p.add_argument("--interval", type=int, default=SYSTEM.scanner_interval_min,
                   help="Scan interval in minutes")
    p.add_argument("--no-gate",  action="store_true",
                   help="Ignore NSE market-hours check (for testing)")
    p.add_argument("--once",     action="store_true",
                   help="Run one scan pass and exit")
    args = p.parse_args()

    if args.once:
        db.init()
        LiveScanner(require_market=not args.no_gate).run_pass()
    else:
        start_scanner(
            interval_min=args.interval,
            require_market=not args.no_gate,
        )
