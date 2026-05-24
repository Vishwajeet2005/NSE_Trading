"""
backtest.py — NSE Historical Backtesting Engine
================================================
Simulates the strategy against up to 5 years of NSE daily data.

Simulation rules (anti-look-ahead):
  • Entry at NEXT candle's Open price (signal fires on close of candle N,
    order fills at open of candle N+1).
  • Stop-loss checked against intraday Low; take-profit against High.
  • TP wins if both hit on same candle.
  • Costs: Zerodha-style brokerage (0.03%) + STT (0.1%) + slippage (0.05%).
  • One position per ticker at a time.

Metrics reported:
  Net P&L (₹ and %), Win Rate, Profit Factor, Max Drawdown,
  Sharpe Ratio, Avg Win/Loss, Avg Hold Days.
  Compared against NIFTY 50 buy-and-hold benchmark.

Run:
  python backtest.py --ticker RELIANCE
  python backtest.py --all
  python backtest.py --ticker TCS --capital 500000
"""
from __future__ import annotations

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from backend.core import logger as log_mod
from backend.engine.data import fetch_historical, nifty50_index_data
from backend.core.settings import BACKTEST, RISK, NSE_WATCHLIST
from backend.engine.strategy import SignalGenerator

log     = log_mod.get(__name__)
console = Console()


# ─── Trade record ─────────────────────────────────────────────────────────────

@dataclass
class Trade:
    ticker:      str
    entry_date:  datetime
    entry_price: float
    exit_date:   Optional[datetime]
    exit_price:  float
    shares:      int
    exit_reason: str    # TAKE_PROFIT | STOP_LOSS | SELL_SIGNAL | EOD_CLOSE
    pnl_inr:     float
    pnl_pct:     float
    hold_days:   int


# ─── Result container ─────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    ticker:        str
    capital:       float
    final_equity:  float
    trades:        list[Trade]  = field(default_factory=list)
    equity_curve:  list[float]  = field(default_factory=list)

    # ── Computed metrics ──────────────────────────────────────────────────────
    @property
    def n_trades(self)    -> int:   return len(self.trades)
    @property
    def winners(self)     -> list:  return [t for t in self.trades if t.pnl_inr > 0]
    @property
    def losers(self)      -> list:  return [t for t in self.trades if t.pnl_inr <= 0]
    @property
    def win_rate(self)    -> float:
        return len(self.winners) / max(self.n_trades, 1) * 100
    @property
    def gross_profit(self)-> float: return sum(t.pnl_inr for t in self.winners)
    @property
    def gross_loss(self)  -> float: return abs(sum(t.pnl_inr for t in self.losers))
    @property
    def profit_factor(self)-> float:
        return round(self.gross_profit / self.gross_loss, 2) if self.gross_loss else float("inf")
    @property
    def net_pnl_inr(self) -> float: return self.final_equity - self.capital
    @property
    def net_pnl_pct(self) -> float: return self.net_pnl_inr / self.capital * 100
    @property
    def avg_win(self)     -> float:
        return self.gross_profit / max(len(self.winners), 1)
    @property
    def avg_loss(self)    -> float:
        return self.gross_loss / max(len(self.losers), 1)
    @property
    def avg_hold(self)    -> float:
        return sum(t.hold_days for t in self.trades) / max(self.n_trades, 1)
    @property
    def max_drawdown(self)-> float:
        if len(self.equity_curve) < 2: return 0.0
        eq  = np.array(self.equity_curve)
        pk  = np.maximum.accumulate(eq)
        dd  = (eq - pk) / pk * 100
        return float(abs(dd.min()))
    @property
    def sharpe(self)      -> float:
        """Annualised Sharpe (RF=7% G-Sec). Uses only active-trade days."""
        if len(self.equity_curve) < 2: return 0.0
        eq     = np.array(self.equity_curve)
        ret    = np.diff(eq) / eq[:-1]
        active = ret[ret != 0]          # ignore flat no-position days
        if len(active) < 2 or active.std() == 0: return 0.0
        return float(np.sqrt(252) * (active.mean() - 0.07/252) / active.std())


# ─── Engine ───────────────────────────────────────────────────────────────────

class BacktestEngine:
    """
    Sequential row-by-row backtesting engine.

    Parameters
    ----------
    capital      : Starting capital in ₹
    commission   : Brokerage per leg (fraction)
    stt          : Securities Transaction Tax (fraction, applied on sell leg)
    slippage     : Per-leg slippage estimate (fraction)
    """

    def __init__(
        self,
        capital:    float = BACKTEST.initial_capital,
        commission: float = BACKTEST.commission_pct,
        stt:        float = BACKTEST.stt_pct,
        slippage:   float = BACKTEST.slippage_pct,
    ) -> None:
        self.capital    = capital
        self.commission = commission
        self.stt        = stt
        self.slippage   = slippage
        self._gen       = SignalGenerator()

    def _entry_cost(self, price: float) -> float:
        return price * (1 + self.slippage + self.commission)

    def _exit_cost(self, price: float) -> float:
        # STT applies on sell leg for delivery; MIS trades exempt — included anyway
        return price * (1 - self.slippage - self.commission - self.stt)

    def run(self, ticker: str) -> BacktestResult:
        """Run full backtest for one NSE ticker. Returns BacktestResult."""
        log.info("Backtesting %s…", ticker)
        ohlcv = fetch_historical(ticker, period=BACKTEST.historical_period,
                                 interval=BACKTEST.interval)
        df    = self._gen.historical_signals(ticker, ohlcv)

        equity        = self.capital
        pos_open      = False
        entry_price   = exit_price = 0.0
        entry_date    = None
        shares        = 0
        sl = tp       = 0.0
        trades:       list[Trade]  = []
        eq_curve:     list[float]  = [equity]

        for i in range(len(df) - 1):
            row      = df.iloc[i]
            next_row = df.iloc[i + 1]
            date     = df.index[i]

            # ── Check exit for open position ──────────────────────────────────
            if pos_open:
                hi, lo = float(row["High"]), float(row["Low"])
                exit_price_raw = None
                reason         = ""

                if hi >= tp:
                    exit_price_raw, reason = tp, "TAKE_PROFIT"
                elif lo <= sl:
                    exit_price_raw, reason = sl, "STOP_LOSS"
                elif bool(row["sell_signal"]):
                    exit_price_raw, reason = float(row["Close"]), "SELL_SIGNAL"

                if exit_price_raw is not None:
                    net_exit = self._exit_cost(exit_price_raw)
                    pnl_inr  = (net_exit - entry_price) * shares
                    pnl_pct  = (net_exit - entry_price) / entry_price * 100
                    equity  += pnl_inr
                    hold     = (date - entry_date).days if entry_date else 0

                    trades.append(Trade(
                        ticker=ticker, entry_date=entry_date,
                        entry_price=entry_price, exit_date=date,
                        exit_price=round(net_exit, 2), shares=shares,
                        exit_reason=reason,
                        pnl_inr=round(pnl_inr, 2), pnl_pct=round(pnl_pct, 3),
                        hold_days=hold,
                    ))
                    log.debug("[%s] %s | ₹%+.0f (%.2f%%)", ticker, reason, pnl_inr, pnl_pct)
                    pos_open = False
                    shares = sl = tp = 0

            # ── Check entry ───────────────────────────────────────────────────
            if not pos_open and bool(row["buy_signal"]):
                raw_entry  = float(next_row["Open"])
                net_entry  = self._entry_cost(raw_entry)
                sl_price   = net_entry * (1 - RISK.stop_loss_pct)
                tp_price   = net_entry * (1 + RISK.take_profit_pct)
                risk_share = net_entry - sl_price

                if risk_share > 0:
                    budget = equity * RISK.max_risk_per_trade_pct
                    cap    = equity * RISK.max_position_size_pct / net_entry
                    sh     = int(min(budget / risk_share, cap))

                    if sh >= 1 and sh * net_entry <= equity * (1 - RISK.min_cash_reserve_pct):
                        entry_price = net_entry
                        sl, tp      = sl_price, tp_price
                        shares      = sh
                        entry_date  = df.index[i + 1]
                        pos_open    = True
                        log.debug("[%s] ENTRY ₹%.2f | SL ₹%.2f | TP ₹%.2f | %d sh",
                                  ticker, entry_price, sl, tp, shares)

            eq_curve.append(equity)

        # Close any open position at last close
        if pos_open:
            last = float(df.iloc[-1]["Close"])
            net  = self._exit_cost(last)
            pnl  = (net - entry_price) * shares
            equity += pnl
            trades.append(Trade(
                ticker=ticker, entry_date=entry_date,
                entry_price=entry_price, exit_date=df.index[-1],
                exit_price=round(net, 2), shares=shares,
                exit_reason="EOD_CLOSE",
                pnl_inr=round(pnl, 2), pnl_pct=round((net - entry_price) / entry_price * 100, 3),
                hold_days=(df.index[-1] - entry_date).days if entry_date else 0,
            ))

        return BacktestResult(ticker=ticker, capital=self.capital,
                              final_equity=round(equity, 2),
                              trades=trades, equity_curve=eq_curve)


# ─── Benchmark ────────────────────────────────────────────────────────────────

def nifty_benchmark(capital: float) -> dict:
    """Return NIFTY 50 buy-and-hold metrics for the same period."""
    try:
        df      = nifty50_index_data(n_days=1825)
        shares  = int(capital / float(df["Close"].iloc[0]))
        eq      = (df["Close"] * shares).values
        final   = float(df["Close"].iloc[-1]) * shares
        ret     = np.diff(eq) / eq[:-1]
        pk      = np.maximum.accumulate(eq)
        dd      = (eq - pk) / pk * 100
        sharpe  = float(np.sqrt(252) * (ret.mean() - 0.07/252) / ret.std()) if ret.std() else 0
        return dict(
            name="NIFTY 50 B&H",
            final_equity=round(final, 2),
            net_pnl_inr =round(final - capital, 2),
            net_pnl_pct =round((final - capital) / capital * 100, 2),
            max_drawdown=round(float(abs(dd.min())), 2),
            sharpe      =round(sharpe, 3),
        )
    except Exception as exc:
        log.warning("Benchmark error: %s", exc)
        return {}


# ─── Report printer ───────────────────────────────────────────────────────────

def print_report(result: BacktestResult, bench: Optional[dict] = None) -> None:
    clr = "bright_green" if result.net_pnl_inr >= 0 else "bright_red"

    t = Table(title=f"📊 Backtest — {result.ticker}",
              box=box.ROUNDED, header_style="bold cyan", show_header=True, expand=True)
    t.add_column("Metric",   style="bold white", width=26)
    t.add_column("Strategy", width=26)
    if bench:
        t.add_column(bench.get("name", "Benchmark"), width=26)

    def row(m, sv, bv=""):
        if bench: t.add_row(m, sv, bv)
        else:     t.add_row(m, sv)

    row("Initial Capital",
        f"₹{result.capital:>14,.2f}",
        f"₹{result.capital:>14,.2f}" if bench else "")
    row("Final Equity",
        f"[{clr}]₹{result.final_equity:>14,.2f}[/{clr}]",
        f"₹{bench.get('final_equity',0):>14,.2f}" if bench else "")
    row("Net P&L",
        f"[{clr}]₹{result.net_pnl_inr:>+14,.2f}  ({result.net_pnl_pct:+.2f}%)[/{clr}]",
        f"₹{bench.get('net_pnl_inr',0):>+,.2f} ({bench.get('net_pnl_pct',0):+.2f}%)" if bench else "")
    row("Total Trades",   str(result.n_trades))
    row("Win Rate",
        f"[bright_green]{result.win_rate:.1f}%[/bright_green] "
        f"({len(result.winners)}W / {len(result.losers)}L)")
    row("Profit Factor",  f"{result.profit_factor:.2f}")
    row("Max Drawdown",
        f"[bright_red]{result.max_drawdown:.2f}%[/bright_red]",
        f"[bright_red]{bench.get('max_drawdown',0):.2f}%[/bright_red]" if bench else "")
    row("Sharpe Ratio",
        f"{result.sharpe:.3f}",
        f"{bench.get('sharpe',0):.3f}" if bench else "")
    row("Avg Win / Loss",
        f"[bright_green]+₹{result.avg_win:,.0f}[/bright_green] / "
        f"[bright_red]-₹{result.avg_loss:,.0f}[/bright_red]")
    row("Avg Hold (days)", f"{result.avg_hold:.1f}")
    console.print(t)

    # Last 10 trades
    if result.trades:
        tt = Table(title="📋 Last 10 Trades", box=box.SIMPLE_HEAVY,
                   header_style="bold cyan")
        for col in ["Entry Date","Exit Date","Entry ₹","Exit ₹","Shares","P&L ₹","P&L %","Reason","Days"]:
            tt.add_column(col, width=12)
        for tr in result.trades[-10:]:
            c = "bright_green" if tr.pnl_inr > 0 else "bright_red"
            tt.add_row(
                str(tr.entry_date)[:10] if tr.entry_date else "—",
                str(tr.exit_date)[:10]  if tr.exit_date  else "—",
                f"₹{tr.entry_price:,.2f}", f"₹{tr.exit_price:,.2f}",
                str(tr.shares),
                f"[{c}]₹{tr.pnl_inr:>+,.0f}[/{c}]",
                f"[{c}]{tr.pnl_pct:>+.2f}%[/{c}]",
                tr.exit_reason, str(tr.hold_days),
            )
        console.print(tt)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="NSE Strategy Backtester")
    p.add_argument("--ticker",  type=str, help="Single NSE symbol (e.g. RELIANCE)")
    p.add_argument("--all",     action="store_true", help="Run all watchlist tickers")
    p.add_argument("--capital", type=float, default=BACKTEST.initial_capital,
                   help=f"Starting capital ₹ (default {BACKTEST.initial_capital:,.0f})")
    args = p.parse_args()

    tickers = NSE_WATCHLIST if args.all else ([args.ticker.upper()] if args.ticker else ["RELIANCE"])
    engine  = BacktestEngine(capital=args.capital)
    bench   = nifty_benchmark(args.capital)
    results = []

    for t in tickers:
        try:
            r = engine.run(t)
            print_report(r, bench if t == tickers[0] else None)
            results.append(r)
        except Exception as exc:
            log.error("Backtest failed for %s: %s", t, exc)

    if len(results) > 1:
        st = Table(title="📊 Multi-Ticker Summary", box=box.ROUNDED,
                   header_style="bold cyan")
        for col in ["Ticker","Trades","Win%","Net P&L","P.Factor","MaxDD","Sharpe"]:
            st.add_column(col, width=12)
        for r in results:
            c = "bright_green" if r.net_pnl_inr >= 0 else "bright_red"
            st.add_row(
                r.ticker, str(r.n_trades),
                f"{r.win_rate:.1f}%",
                f"[{c}]{r.net_pnl_pct:+.1f}%[/{c}]",
                f"{r.profit_factor:.2f}",
                f"{r.max_drawdown:.1f}%",
                f"{r.sharpe:.2f}",
            )
        console.print(st)


if __name__ == "__main__":
    main()
