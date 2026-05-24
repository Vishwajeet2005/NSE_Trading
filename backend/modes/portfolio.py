"""
portfolio.py — Paper Portfolio P&L Tracker
==========================================
Tracks all paper trades in the SQLite database and computes:

  • Real-time P&L for every open position (vs live/simulated price)
  • Closed trade history with entry/exit/pnl breakdown
  • Cumulative equity curve from initial capital
  • Per-ticker win/loss statistics
  • Daily P&L summary
  • Risk metrics: current drawdown, total deployed capital, free cash

All amounts in Indian Rupees (₹).

Run:
  python portfolio.py              # full portfolio report
  python portfolio.py --open       # open positions only
  python portfolio.py --history    # closed trades only
  python portfolio.py --equity     # ASCII equity curve in terminal
"""
from __future__ import annotations

import argparse
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date
from typing import Optional

import numpy as np
import pandas as pd
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

from backend.core import database as db
from backend.core import logger as log_mod
from backend.engine.data import fetch_live_quote
from backend.core.settings import BACKTEST, SYSTEM

log     = log_mod.get(__name__)
console = Console()


# ─── Portfolio Snapshot ───────────────────────────────────────────────────────

class Portfolio:
    """
    Computes a complete portfolio snapshot from the SQLite database.

    Parameters
    ----------
    db_path       : Path to NSE signals database
    initial_capital : Starting capital in ₹ (from settings)
    """

    def __init__(
        self,
        db_path:         str   = SYSTEM.db_path,
        initial_capital: float = BACKTEST.initial_capital,
    ) -> None:
        self.db_path         = db_path
        self.initial_capital = initial_capital
        db.init(db_path)

    # ── Data loaders ─────────────────────────────────────────────────────────

    def _open_trades(self) -> list[dict]:
        return db.open_trades(self.db_path)

    def _all_trades(self) -> list[dict]:
        with db.conn(self.db_path) as c:
            rows = c.execute(db.trades_tbl.select()
                             .order_by(db.trades_tbl.c.entry_time)).fetchall()
        return [dict(r._mapping) for r in rows]

    def _closed_trades(self) -> list[dict]:
        with db.conn(self.db_path) as c:
            rows = c.execute(
                db.trades_tbl.select()
                .where(db.trades_tbl.c.status == "CLOSED")
                .order_by(db.trades_tbl.c.exit_time.desc())
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Live P&L for open positions ───────────────────────────────────────────

    def enrich_open(self, trades: list[dict]) -> list[dict]:
        """
        Add live_price, unrealised_pnl, unrealised_pct to each open trade.
        Uses live quote if available, falls back to simulated price.
        """
        enriched = []
        for t in trades:
            try:
                q     = fetch_live_quote(t["ticker"])
                live  = q["price"]
            except Exception:
                live  = t["entry_price"]

            entry      = t["entry_price"]
            shares     = t["shares"]
            direction  = t["direction"]

            if direction == "BUY":
                unreal_inr = (live - entry) * shares
            else:
                unreal_inr = (entry - live) * shares

            unreal_pct = unreal_inr / (entry * shares) * 100 if entry and shares else 0.0
            cost_basis = entry * shares

            enriched.append({
                **t,
                "live_price":     round(live, 2),
                "unrealised_pnl": round(unreal_inr, 2),
                "unrealised_pct": round(unreal_pct, 3),
                "cost_basis":     round(cost_basis, 2),
                "market_value":   round(live * shares, 2),
            })
        return enriched

    # ── Equity curve ──────────────────────────────────────────────────────────

    def equity_curve(self) -> pd.Series:
        """
        Build a daily equity series from initial capital + cumulative closed P&L.

        Returns a pd.Series indexed by date, starting from first trade date.
        """
        closed = self._closed_trades()
        if not closed:
            return pd.Series(
                [self.initial_capital],
                index=[pd.Timestamp(datetime.today().date())],
                name="Equity (₹)",
            )

        # Build event list: (date, pnl)
        events = []
        for t in closed:
            if t.get("exit_time") and t.get("pnl_inr") is not None:
                d = pd.Timestamp(t["exit_time"]).date()
                events.append((d, float(t["pnl_inr"])))

        if not events:
            return pd.Series(
                [self.initial_capital],
                index=[pd.Timestamp(datetime.today().date())],
                name="Equity (₹)",
            )

        df_ev = pd.DataFrame(events, columns=["date", "pnl"])
        df_ev = df_ev.groupby("date")["pnl"].sum().reset_index()
        df_ev = df_ev.sort_values("date")

        # Fill daily gaps
        date_range = pd.date_range(df_ev["date"].min(), datetime.today().date(), freq="B")
        df_ev = df_ev.set_index("date").reindex(date_range, fill_value=0.0)

        equity = self.initial_capital + df_ev["pnl"].cumsum()
        equity.name = "Equity (₹)"
        return equity

    # ── Summary metrics ───────────────────────────────────────────────────────

    def summary(self) -> dict:
        """Return a dict of portfolio-level summary metrics."""
        open_t   = self.enrich_open(self._open_trades())
        closed_t = self._closed_trades()
        all_t    = self._all_trades()

        # Realised P&L from closed trades
        realised = sum(
            float(t.get("pnl_inr") or 0) for t in closed_t
        )
        # Unrealised P&L from open positions
        unrealised = sum(t["unrealised_pnl"] for t in open_t)

        # Deployed capital
        deployed   = sum(t["cost_basis"] for t in open_t)
        free_cash  = self.initial_capital + realised - deployed

        # Win stats from closed trades
        winners = [t for t in closed_t if (t.get("pnl_inr") or 0) > 0]
        losers  = [t for t in closed_t if (t.get("pnl_inr") or 0) <= 0]
        win_rate  = len(winners) / max(len(closed_t), 1) * 100
        gross_win = sum(float(t["pnl_inr"]) for t in winners)
        gross_los = abs(sum(float(t["pnl_inr"]) for t in losers))
        pf        = gross_win / gross_los if gross_los > 0 else float("inf")

        # Equity curve metrics
        eq = self.equity_curve()
        if len(eq) > 1:
            peak = eq.cummax()
            dd   = ((eq - peak) / peak * 100).min()
        else:
            dd = 0.0

        return dict(
            initial_capital   = self.initial_capital,
            realised_pnl      = round(realised, 2),
            unrealised_pnl    = round(unrealised, 2),
            total_pnl         = round(realised + unrealised, 2),
            total_pnl_pct     = round((realised + unrealised) / self.initial_capital * 100, 3),
            free_cash         = round(free_cash, 2),
            deployed_capital  = round(deployed, 2),
            open_positions    = len(open_t),
            closed_trades     = len(closed_t),
            total_trades      = len(all_t),
            win_rate          = round(win_rate, 1),
            profit_factor     = round(pf, 2),
            max_drawdown_pct  = round(abs(float(dd)), 2),
            gross_profit      = round(gross_win, 2),
            gross_loss        = round(gross_los, 2),
        )


# ─── Display helpers ─────────────────────────────────────────────────────────

def _pnl_str(val: float, suffix: str = "") -> str:
    col = "bright_green" if val >= 0 else "bright_red"
    return f"[{col}]{val:+,.2f}{suffix}[/{col}]"

def _pct_str(val: float) -> str:
    col = "bright_green" if val >= 0 else "bright_red"
    return f"[{col}]{val:+.2f}%[/{col}]"

def _ascii_equity_curve(eq: pd.Series, width: int = 60, height: int = 16) -> str:
    """Render the equity curve as an ASCII sparkline in the terminal."""
    if len(eq) < 2:
        return "[dim]Not enough data for equity curve.[/dim]"

    vals   = eq.values.astype(float)
    lo, hi = vals.min(), vals.max()
    span   = hi - lo if hi != lo else 1.0

    # Normalise to [0, height-1]
    scaled = ((vals - lo) / span * (height - 1)).astype(int)

    # Build grid
    grid = [[" "] * width for _ in range(height)]
    step = max(1, len(vals) // width)
    x_vals = vals[::step][:width]
    x_sc   = ((x_vals - lo) / span * (height - 1)).astype(int)

    for xi, yi in enumerate(x_sc):
        if xi < width:
            row = height - 1 - yi
            grid[row][xi] = "█"

    # Build string
    lines = []
    for i, row in enumerate(grid):
        # Y-axis label on right edge
        if i == 0:
            label = f"₹{hi:>11,.0f}"
        elif i == height // 2:
            mid   = (hi + lo) / 2
            label = f"₹{mid:>11,.0f}"
        elif i == height - 1:
            label = f"₹{lo:>11,.0f}"
        else:
            label = " " * 13
        lines.append("│" + "".join(row) + f" {label}")

    # X-axis
    lines.append("└" + "─" * width)
    start_d = str(eq.index[0])[:10]
    end_d   = str(eq.index[-1])[:10]
    lines.append(f"  {start_d}" + " " * (width - 22) + f"{end_d}")

    return "\n".join(lines)


# ─── Report printers ─────────────────────────────────────────────────────────

def print_portfolio_summary(pf: Portfolio) -> None:
    s    = pf.summary()
    pnl  = s["total_pnl"]
    pnl_pct = s["total_pnl_pct"]
    clr  = "bright_green" if pnl >= 0 else "bright_red"

    # ── Top KPI panels ────────────────────────────────────────────────────────
    def kpi(title: str, value: str) -> Panel:
        return Panel(f"[bold]{value}[/bold]", title=f"[dim]{title}[/dim]",
                     border_style="cyan", expand=True)

    console.print(Columns([
        kpi("💰 Total P&L",
            f"[{clr}]₹{pnl:>+,.2f} ({pnl_pct:+.2f}%)[/{clr}]"),
        kpi("✅ Realised",
            f"[{'bright_green' if s['realised_pnl']>=0 else 'bright_red'}]"
            f"₹{s['realised_pnl']:>+,.2f}[/{'bright_green' if s['realised_pnl']>=0 else 'bright_red'}]"),
        kpi("⏳ Unrealised",
            f"[{'bright_green' if s['unrealised_pnl']>=0 else 'bright_red'}]"
            f"₹{s['unrealised_pnl']:>+,.2f}[/{'bright_green' if s['unrealised_pnl']>=0 else 'bright_red'}]"),
        kpi("💵 Free Cash",    f"₹{s['free_cash']:>,.2f}"),
        kpi("📦 Deployed",     f"₹{s['deployed_capital']:>,.2f}"),
    ], equal=True))

    # ── Stats table ───────────────────────────────────────────────────────────
    t = Table(title="📊 Portfolio Statistics", box=box.ROUNDED,
              header_style="bold cyan", show_header=True, expand=False)
    t.add_column("Metric",   style="bold white", width=26)
    t.add_column("Value",    style="bright_white", width=22)
    t.add_column("Metric",   style="bold white", width=26)
    t.add_column("Value",    style="bright_white", width=22)

    def row(m1, v1, m2="", v2=""):
        t.add_row(m1, v1, m2, v2)

    row("Initial Capital",    f"₹{s['initial_capital']:>,.2f}",
        "Total Trades",       str(s["total_trades"]))
    row("Gross Profit",
        f"[bright_green]₹{s['gross_profit']:>,.2f}[/bright_green]",
        "Gross Loss",
        f"[bright_red]₹{s['gross_loss']:>,.2f}[/bright_red]")
    row("Profit Factor",
        f"[{'bright_green' if s['profit_factor']>=1.5 else 'yellow'}]{s['profit_factor']:.2f}"
        f"[/{'bright_green' if s['profit_factor']>=1.5 else 'yellow'}]",
        "Win Rate",
        f"[bright_green]{s['win_rate']:.1f}%[/bright_green] "
        f"({s['closed_trades']} closed)")
    row("Max Drawdown",
        f"[bright_red]{s['max_drawdown_pct']:.2f}%[/bright_red]",
        "Open Positions",
        f"{s['open_positions']}")
    console.print(t)


def print_open_positions(pf: Portfolio) -> None:
    open_t = pf.enrich_open(pf._open_trades())
    if not open_t:
        console.print("[dim]No open positions.[/dim]")
        return

    t = Table(title=f"💼 Open Positions  ({len(open_t)})",
              box=box.ROUNDED, header_style="bold cyan", expand=True)
    t.add_column("Ticker",    width=12, style="bold")
    t.add_column("Dir",       width=6)
    t.add_column("Shares",    width=8)
    t.add_column("Entry ₹",   width=13)
    t.add_column("Live ₹",    width=13)
    t.add_column("Cost ₹",    width=14)
    t.add_column("Mkt Val ₹", width=14)
    t.add_column("Unreal P&L",width=15)
    t.add_column("P&L %",     width=10)
    t.add_column("Entry Date",width=13)

    for tr in open_t:
        clr   = "bright_green" if tr["unrealised_pnl"] >= 0 else "bright_red"
        d_clr = "bright_green" if tr["direction"] == "BUY" else "bright_red"
        t.add_row(
            tr["ticker"],
            f"[{d_clr}]{tr['direction']}[/{d_clr}]",
            str(tr["shares"]),
            f"₹{tr['entry_price']:>10,.2f}",
            f"₹{tr['live_price']:>10,.2f}",
            f"₹{tr['cost_basis']:>11,.2f}",
            f"₹{tr['market_value']:>11,.2f}",
            f"[{clr}]₹{tr['unrealised_pnl']:>+10,.2f}[/{clr}]",
            f"[{clr}]{tr['unrealised_pct']:>+.2f}%[/{clr}]",
            str(tr.get("entry_time", ""))[:10],
        )

    console.print(t)


def print_closed_trades(pf: Portfolio, limit: int = 30) -> None:
    closed = pf._closed_trades()[:limit]
    if not closed:
        console.print("[dim]No closed trades yet.[/dim]")
        return

    t = Table(title=f"📋 Closed Trades  (last {min(limit, len(closed))})",
              box=box.SIMPLE_HEAVY, header_style="bold cyan", expand=True)
    t.add_column("Ticker",    width=12, style="bold")
    t.add_column("Dir",       width=6)
    t.add_column("Shares",    width=8)
    t.add_column("Entry ₹",   width=13)
    t.add_column("Exit ₹",    width=13)
    t.add_column("P&L ₹",     width=14)
    t.add_column("P&L %",     width=10)
    t.add_column("Exit Reason",width=14)
    t.add_column("Entry Date", width=13)
    t.add_column("Exit Date",  width=13)

    for tr in closed:
        pnl  = float(tr.get("pnl_inr") or 0)
        pnl_pct = float(tr.get("pnl_pct") or 0)
        clr  = "bright_green" if pnl >= 0 else "bright_red"
        d_clr = "bright_green" if tr["direction"] == "BUY" else "bright_red"
        t.add_row(
            tr["ticker"],
            f"[{d_clr}]{tr['direction']}[/{d_clr}]",
            str(tr["shares"]),
            f"₹{tr['entry_price']:>10,.2f}",
            f"₹{float(tr.get('exit_price') or 0):>10,.2f}",
            f"[{clr}]₹{pnl:>+10,.2f}[/{clr}]",
            f"[{clr}]{pnl_pct:>+.2f}%[/{clr}]",
            str(tr.get("exit_reason", "—")),
            str(tr.get("entry_time", ""))[:10],
            str(tr.get("exit_time", ""))[:10],
        )

    console.print(t)


def print_ticker_breakdown(pf: Portfolio) -> None:
    """Per-ticker win/loss breakdown for closed trades."""
    closed = pf._closed_trades()
    if not closed:
        return

    by_ticker: dict[str, dict] = {}
    for tr in closed:
        tk  = tr["ticker"]
        pnl = float(tr.get("pnl_inr") or 0)
        if tk not in by_ticker:
            by_ticker[tk] = {"trades": 0, "wins": 0, "pnl": 0.0}
        by_ticker[tk]["trades"] += 1
        by_ticker[tk]["pnl"]    += pnl
        if pnl > 0:
            by_ticker[tk]["wins"] += 1

    t = Table(title="📈 Per-Ticker Performance", box=box.ROUNDED,
              header_style="bold cyan")
    t.add_column("Ticker",    width=14, style="bold")
    t.add_column("Trades",    width=8)
    t.add_column("Win Rate",  width=10)
    t.add_column("Total P&L", width=16)
    t.add_column("Bar",       width=20)

    sorted_tickers = sorted(by_ticker.items(), key=lambda x: x[1]["pnl"], reverse=True)
    max_abs_pnl = max(abs(v["pnl"]) for _, v in sorted_tickers) or 1.0

    for ticker, stats in sorted_tickers:
        pnl      = stats["pnl"]
        win_rate = stats["wins"] / max(stats["trades"], 1) * 100
        clr      = "bright_green" if pnl >= 0 else "bright_red"
        bar_len  = int(abs(pnl) / max_abs_pnl * 18)
        bar      = ("█" * bar_len).ljust(18)
        t.add_row(
            ticker,
            str(stats["trades"]),
            f"{win_rate:.0f}%",
            f"[{clr}]₹{pnl:>+,.2f}[/{clr}]",
            f"[{clr}]{bar}[/{clr}]",
        )
    console.print(t)


def print_equity_curve(pf: Portfolio) -> None:
    """Print an ASCII equity curve in the terminal."""
    eq = pf.equity_curve()
    console.print(Panel(
        _ascii_equity_curve(eq, width=70, height=18),
        title="[bold cyan]📈 Equity Curve[/bold cyan]",
        subtitle=f"[dim]₹{BACKTEST.initial_capital:,.0f} → ₹{float(eq.iloc[-1]):,.0f}[/dim]",
        border_style="cyan",
    ))


def print_daily_pnl(pf: Portfolio, days: int = 10) -> None:
    """Show P&L by day for the last N days."""
    closed = pf._closed_trades()
    if not closed:
        return

    daily: dict[str, float] = {}
    for tr in closed:
        if tr.get("exit_time") and tr.get("pnl_inr") is not None:
            d   = str(tr["exit_time"])[:10]
            daily[d] = daily.get(d, 0.0) + float(tr["pnl_inr"])

    if not daily:
        return

    t = Table(title=f"📅 Daily P&L  (last {days} trading days)",
              box=box.SIMPLE, header_style="bold cyan")
    t.add_column("Date",       width=14)
    t.add_column("P&L ₹",      width=16)
    t.add_column("Cumulative ₹",width=18)
    t.add_column("Sparkline",  width=24)

    sorted_days = sorted(daily.keys(), reverse=True)[:days]
    cum   = pf.initial_capital + sum(
        v for k, v in daily.items() if k not in sorted_days
    )
    daily_vals = [daily.get(d, 0) for d in sorted_days]
    mx = max(abs(v) for v in daily_vals) or 1.0

    for i, d in enumerate(sorted_days):
        pnl_d  = daily.get(d, 0.0)
        cum   += pnl_d
        clr    = "bright_green" if pnl_d >= 0 else "bright_red"
        blen   = int(abs(pnl_d) / mx * 20)
        bar    = ("▇" * blen).ljust(20)
        t.add_row(
            d,
            f"[{clr}]₹{pnl_d:>+,.2f}[/{clr}]",
            f"₹{cum:>,.2f}",
            f"[{clr}]{bar}[/{clr}]",
        )
    console.print(t)


# ─── CLI entry point ─────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="NSE Paper Portfolio P&L Tracker")
    p.add_argument("--open",    action="store_true", help="Show open positions only")
    p.add_argument("--history", action="store_true", help="Show closed trades only")
    p.add_argument("--equity",  action="store_true", help="Show ASCII equity curve")
    p.add_argument("--daily",   action="store_true", help="Show daily P&L breakdown")
    p.add_argument("--all",     action="store_true", help="Show everything (default)")
    args = p.parse_args()

    pf   = Portfolio()
    show_all = not any([args.open, args.history, args.equity, args.daily])

    console.rule("[bold cyan]NSE PAPER PORTFOLIO  —  "
                 f"{datetime.now().strftime('%d %b %Y  %H:%M IST')}[/bold cyan]")

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


if __name__ == "__main__":
    main()
