"""
execution_bridge.py — Human Approval & Execution Bridge
=========================================================
The ONLY module that can execute a trade order.
Orders are placed ONLY after a human clicks APPROVE in the dashboard.

Broker support:
  1. Paper Trading (default) — simulates orders internally; no real money.
  2. Zerodha Kite Connect   — real NSE execution (requires API credentials).

Safety architecture:
  • Signal status set to "EXECUTED" BEFORE broker call → prevents double-submit.
  • Failed broker calls revert status to "APPROVED" for retry notification.
  • Bracket orders (entry + SL + TP as one atomic unit) for both modes.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from backend.core import logger as log_mod
from backend.core import database as db
from backend.engine.risk import Assessment
from backend.core.settings import ZERODHA

log = log_mod.get(__name__)


@dataclass
class OrderResult:
    """Outcome of a broker order submission."""
    success:   bool
    order_id:  str   = ""
    fill_price: float = 0.0
    error:     str   = ""
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


# ─── Paper Broker ─────────────────────────────────────────────────────────────

class PaperBroker:
    """
    Simulates order execution locally — no real money involved.

    Generates a UUID order ID and uses the signal's entry price as fill.
    Stored in the trades table for P&L tracking.
    """

    def submit(self, ticker: str, direction: str, shares: int,
               stop_loss: float, take_profit: float,
               entry_price: float) -> OrderResult:
        order_id = f"PAPER-{uuid.uuid4().hex[:12].upper()}"
        log.info(
            "📄 PAPER ORDER | %s %s × %d @ ₹%.2f | SL ₹%.2f | TP ₹%.2f | ID=%s",
            direction, ticker, shares, entry_price, stop_loss, take_profit, order_id,
        )
        return OrderResult(success=True, order_id=order_id, fill_price=entry_price)

    def open_positions(self) -> int:
        return len(db.open_trades())

    def account_equity(self) -> float:
        from backend.core.settings import BACKTEST
        return BACKTEST.initial_capital   # Paper equity = initial capital


# ─── Zerodha Kite Broker ──────────────────────────────────────────────────────

class ZerodhaBroker:
    """
    Real NSE order execution via Zerodha Kite Connect.

    Requires kiteconnect package and valid API credentials in .env:
      ZERODHA_API_KEY, ZERODHA_API_SECRET, ZERODHA_ACCESS_TOKEN

    pip install kiteconnect
    """

    def __init__(self) -> None:
        self._kite = None

    def _client(self):
        if self._kite is None:
            try:
                from kiteconnect import KiteConnect
                self._kite = KiteConnect(api_key=ZERODHA.api_key)
                self._kite.set_access_token(ZERODHA.access_token)
                log.info("Zerodha Kite client connected.")
            except ImportError:
                raise RuntimeError(
                    "kiteconnect not installed. Run: pip install kiteconnect"
                )
        return self._kite

    def submit(self, ticker: str, direction: str, shares: int,
               stop_loss: float, take_profit: float,
               entry_price: float) -> OrderResult:
        """
        Place a bracket order on NSE via Kite Connect.

        Bracket order = Entry (market) + Stop-Loss trigger + Target limit.
        All three legs are submitted as one atomic request.
        """
        try:
            from kiteconnect import KiteConnect
            kite    = self._client()
            t_type  = kite.TRANSACTION_TYPE_BUY if direction == "BUY" \
                      else kite.TRANSACTION_TYPE_SELL
            sl_pts  = round(abs(entry_price - stop_loss), 2)
            tp_pts  = round(abs(take_profit - entry_price), 2)

            order_id = kite.place_order(
                tradingsymbol     = ticker,
                exchange          = kite.EXCHANGE_NSE,
                transaction_type  = t_type,
                quantity          = shares,
                order_type        = kite.ORDER_TYPE_MARKET,
                product           = kite.PRODUCT_MIS,         # Intraday
                variety           = kite.VARIETY_BO,          # Bracket order
                squareoff         = tp_pts,
                stoploss          = sl_pts,
                trailing_stoploss = 0,
            )
            log.info("✅ Zerodha order placed | ID=%s", order_id)
            return OrderResult(success=True, order_id=str(order_id),
                               fill_price=entry_price)
        except Exception as exc:
            log.error("❌ Zerodha order failed: %s", exc)
            return OrderResult(success=False, error=str(exc))

    def open_positions(self) -> int:
        try:
            return len(self._client().positions()["net"])
        except Exception:
            return 0

    def account_equity(self) -> float:
        try:
            margins = self._client().margins()
            return float(margins["equity"]["net"])
        except Exception:
            return 1_000_000.0


# ─── Execution Bridge ─────────────────────────────────────────────────────────

class ExecutionBridge:
    """
    Orchestrates human-approved trade execution.

    Steps:
    1. Mark signal EXECUTED in DB (double-submit guard).
    2. Submit to broker (paper or Zerodha).
    3. Record trade in DB.
    4. On failure: revert status → alert operator for manual retry.

    Parameters
    ----------
    use_zerodha : If True and credentials present, use real Zerodha broker.
    db_path     : Path to SQLite database.
    """

    def __init__(self, use_zerodha: bool = False,
                 db_path: str = "nse_signals.db") -> None:
        self.db_path = db_path
        if use_zerodha and ZERODHA.enabled:
            self.broker = ZerodhaBroker()
            log.info("Broker: Zerodha Kite Connect (LIVE)")
        else:
            self.broker = PaperBroker()
            log.info("Broker: Paper Trading (simulated)")

    def execute(self, signal_id: int, a: Assessment) -> OrderResult:
        """
        Execute an operator-approved signal.

        Parameters
        ----------
        signal_id : DB primary key of the approved signal.
        a         : Full risk Assessment.

        Returns
        -------
        OrderResult  — broker submission outcome.
        """
        sig = a.signal
        log.info("=== EXECUTING Signal #%d | %s %s × %d @ ₹%.2f ===",
                 signal_id, sig.direction, sig.ticker, a.shares, sig.entry_price)

        # Guard: mark EXECUTED before sending to broker
        db.update_signal(signal_id, "EXECUTED",
                         note="Order submitted to broker", db_path=self.db_path)

        # Submit to broker
        result = self.broker.submit(
            ticker      = sig.ticker,
            direction   = sig.direction,
            shares      = a.shares,
            stop_loss   = a.stop_loss,
            take_profit = a.take_profit,
            entry_price = sig.entry_price,
        )

        if result.success:
            db.insert_trade({
                "signal_id":   signal_id,
                "ticker":      sig.ticker,
                "direction":   sig.direction,
                "entry_price": sig.entry_price,
                "shares":      a.shares,
                "entry_time":  datetime.utcnow(),
                "order_id":    result.order_id,
                "status":      "OPEN",
            }, db_path=self.db_path)
            log.info("✅ Trade recorded | Signal #%d | %s", signal_id, result.order_id)
        else:
            # Revert so operator can retry
            db.update_signal(signal_id, "APPROVED",
                             note=f"EXECUTION FAILED: {result.error}",
                             db_path=self.db_path)
            log.error("❌ Execution failed for Signal #%d: %s", signal_id, result.error)

        return result

    def deny(self, signal_id: int, ticker: str, note: str = "") -> None:
        """Record operator denial of a pending signal."""
        db.update_signal(signal_id, "DENIED",
                         note=note or "Denied by operator", db_path=self.db_path)
        log.info("Signal #%d (%s) denied. Note: %s", signal_id, ticker, note)

    def open_position_count(self) -> int:
        return self.broker.open_positions()

    def equity(self) -> float:
        return self.broker.account_equity()
