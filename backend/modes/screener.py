"""
screener.py — NSE Near-Signal Screener & Indicator Dashboard
=============================================================
More powerful than the basic scanner: it shows EVERY ticker's
current indicator state, not just confirmed signals.

Features
--------
• Near-Signal alerts  — tickers within 10 pts of firing a BUY/SELL
• Sector heatmap      — momentum score per sector (Rich colour table)
• Indicator snapshot  — EMA/RSI/MACD/ATR/Volume for every ticker
• Overbought/Oversold watchlist — tickers at RSI extremes
• Volume spike alerts — tickers trading >2× average volume today

Near-Signal Score Logic
-----------------------
Each BUY condition that is TRUE adds its weight.
If score ≥ 50 (but < 60 threshold) → "⚡ Near BUY"
If score ≥ 60 → confirmed BUY signal (handled by scanner)

Run:
  python screener.py              # full screen, all tickers
  python screener.py --ticker RELIANCE TCS INFY  # specific tickers
  python screener.py --sector tech   # sector filter
"""
from __future__ import annotations

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from backend.core import logger as log_mod
from backend.engine.data import fetch_historical, fetch_live_quote
from backend.core.settings import NSE_WATCHLIST, RISK, STRATEGY
from backend.engine.strategy import IndicatorEngine, SignalGenerator, Signal

log     = log_mod.get(__name__)
console = Console()

# ─── NSE Sector mapping ──────────────────────────────────────────────────────

SECTORS: dict[str, list[str]] = {
    "Technology":  ["TCS", "INFY", "WIPRO"],
    "Banking":     ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK"],
    "Energy":      ["RELIANCE"],
    "Telecom":     ["BHARTIARTL"],
    "FMCG":        ["HINDUNILVR", "ITC", "NESTLEIND"],
    "Auto":        ["MARUTI"],
    "Finance":     ["BAJFINANCE"],
    "Infra":       ["LT", "ULTRACEMCO"],
    "Consumer":    ["TITAN", "ASIANPAINT"],
    "Pharma":      ["SUNPHARMA"],
}

# Reverse map: ticker → sector
TICKER_SECTOR = {t: s for s, tickers in SECTORS.items() for t in tickers}

# ─── Screener result ─────────────────────────────────────────────────────────

class ScreenerRow:
    """Holds all computed values for one ticker in a screen pass."""

    __slots__ = (
        "ticker", "sector", "price", "change_pct",
        "ema_fast", "ema_slow", "ema_trend",
        "rsi", "macd_hist", "atr", "vol_ratio",
        "bb_pct",          # 0 = at lower BB, 1 = at upper BB
        "buy_score", "sell_score",
        "direction",       # confirmed signal or near-signal label
        "alert_level",     # "SIGNAL" / "NEAR" / "WATCH" / "NEUTRAL"
    )

    def __init__(self, ticker: str, price: float, change_pct: float,
                 indicators: dict, buy_score: int, sell_score: int,
                 direction: str) -> None:
        self.ticker      = ticker
        self.sector      = TICKER_SECTOR.get(ticker, "Other")
        self.price       = price
        self.change_pct  = change_pct
        self.ema_fast    = indicators.get("ema_fast", 0.0)
        self.ema_slow    = indicators.get("ema_slow", 0.0)
        self.ema_trend   = indicators.get("ema_trend", 0.0)
        self.rsi         = indicators.get("rsi", 50.0)
        self.macd_hist   = indicators.get("macd_hist", 0.0)
        self.atr         = indicators.get("atr", 0.0)
        self.vol_ratio   = indicators.get("vol_ratio", 1.0)
        self.bb_pct      = indicators.get("bb_pct", 0.5)
        self.buy_score   = buy_score
        self.sell_score  = sell_score
        self.direction   = direction

        # Alert level
        if direction in ("BUY", "SELL"):
            self.alert_level = "SIGNAL"
        elif buy_score >= 50 or sell_score >= 50:
            self.alert_level = "NEAR"
        elif self.rsi < 35 or self.rsi > 68 or self.vol_ratio > 2.0:
            self.alert_level = "WATCH"
        else:
            self.alert_level = "NEUTRAL"


# ─── Core screener engine ────────────────────────────────────────────────────

class Screener:
    """
    Runs a comprehensive indicator scan on every ticker.

    Unlike the scanner (which only reports confirmed signals), the screener
    reports ALL tickers with their full indicator state so you can see
    which ones are approaching signal conditions.
    """

    def __init__(self) -> None:
        self._ie  = IndicatorEngine()
        self._gen = SignalGenerator()

    def _score_ticker(self, ticker: str) -> Optional[ScreenerRow]:
        """
        Compute indicator snapshot and buy/sell scores for one ticker.

        Returns None on fetch / compute error.
        """
        try:
            ohlcv = fetch_historical(
                ticker, period=STRATEGY.live_period, interval=STRATEGY.interval)
            df    = self._ie.compute(ohlcv)
            row   = df.iloc[-1]

            # Extract latest indicator values
            price     = float(row["Close"])
            ema_fast  = float(row["ema_fast"])
            ema_slow  = float(row["ema_slow"])
            ema_trend = float(row["ema_trend"])
            rsi       = float(row["rsi"]) if not pd.isna(row["rsi"]) else 50.0
            macd_hist = float(row["macd_hist"]) if not pd.isna(row["macd_hist"]) else 0.0
            atr       = float(row["atr"]) if not pd.isna(row["atr"]) else 0.0
            vol_ratio = float(row["vol_ratio"]) if not pd.isna(row["vol_ratio"]) else 1.0

            # Bollinger %B: where is price relative to the BB range?
            bb_pct = 0.5
            if not (pd.isna(row["bb_lower"]) or pd.isna(row["bb_upper"])):
                rng    = row["bb_upper"] - row["bb_lower"]
                bb_pct = float((row["Close"] - row["bb_lower"]) / rng) if rng > 0 else 0.5

            # Compute scores via the strategy engine's internal logic
            sig = self._gen.analyse(ticker, ohlcv)

            # Also compute raw buy/sell scores independently (for near-signal)
            # Re-compute using internal methods (we need the actual scores)
            b_score, _ = self._gen._buy_score(df, -1)
            s_score, _ = self._gen._sell_score(df, -1)

            # Price change vs previous close
            prev     = float(df.iloc[-2]["Close"]) if len(df) > 1 else price
            chg_pct  = (price - prev) / prev * 100

            indics = dict(
                ema_fast=ema_fast, ema_slow=ema_slow, ema_trend=ema_trend,
                rsi=rsi, macd_hist=macd_hist, atr=atr,
                vol_ratio=vol_ratio, bb_pct=bb_pct,
            )

            direction = sig.direction  # "BUY" / "SELL" / "NONE"
            return ScreenerRow(ticker, price, chg_pct, indics,
                               b_score, s_score, direction)

        except Exception as exc:
            log.warning("[%s] Screener error: %s", ticker, exc)
            return None

    def run(self, tickers: list[str]) -> list[ScreenerRow]:
        """
        Screen all tickers and return sorted ScreenerRow list.

        Sort order: SIGNAL first, then NEAR, then WATCH, then NEUTRAL.
        Within each group: by buy_score descending.
        """
        results: list[ScreenerRow] = []
        order = {"SIGNAL": 0, "NEAR": 1, "WATCH": 2, "NEUTRAL": 3}

        with Progress(
            SpinnerColumn(),
            TextColumn("[cyan]Screening {task.description}…"),
            console=console, transient=True,
        ) as prog:
            task = prog.add_task("tickers", total=len(tickers))
            for ticker in tickers:
                prog.update(task, description=ticker)
                row = self._score_ticker(ticker)
                if row:
                    results.append(row)
                prog.advance(task)

        results.sort(key=lambda r: (order.get(r.alert_level, 9), -r.buy_score))
        return results


# ─── Rich display functions ──────────────────────────────────────────────────

def _rsi_colour(rsi: float) -> str:
    if rsi < 30:  return "bright_cyan"
    if rsi < 40:  return "cyan"
    if rsi > 70:  return "bright_red"
    if rsi > 60:  return "yellow"
    return "white"

def _pct_str(val: float, suffix: str = "%") -> str:
    col = "bright_green" if val >= 0 else "bright_red"
    return f"[{col}]{val:+.2f}{suffix}[/{col}]"

def _score_bar(score: int, threshold: int = RISK.min_signal_confidence) -> str:
    filled = int(score / 10)
    bar    = "█" * filled + "░" * (10 - filled)
    col    = "bright_green" if score >= threshold else ("yellow" if score >= 50 else "dim white")
    return f"[{col}]{bar}[/{col}] {score}"

def _alert_badge(level: str) -> str:
    badges = {
        "SIGNAL":  "[bold bright_green]🚨 SIGNAL [/bold bright_green]",
        "NEAR":    "[bold yellow]⚡ NEAR   [/bold yellow]",
        "WATCH":   "[bold cyan]👁  WATCH  [/bold cyan]",
        "NEUTRAL": "[dim]  ──       [/dim]",
    }
    return badges.get(level, level)


def print_indicator_table(rows: list[ScreenerRow]) -> None:
    """Full indicator snapshot table — all tickers."""
    t = Table(
        title=f"📊 NSE Indicator Snapshot  —  {datetime.now().strftime('%d %b %Y %H:%M IST')}",
        box=box.SIMPLE_HEAVY, header_style="bold cyan",
        show_header=True, expand=True,
    )

    cols = [
        ("Alert",    10), ("Ticker",   10), ("Sector",   12),
        ("Price ₹",  12), ("Chg%",      8), ("RSI",      8),
        ("EMA9>21",   8), ("MACD▲",     8), ("Vol×",     7),
        ("BB%",       7), ("ATR ₹",     9),
        ("Buy Score", 14), ("Sell Score",14),
    ]
    for name, width in cols:
        t.add_column(name, width=width, no_wrap=True)

    for r in rows:
        ema_ok    = "✅" if r.ema_fast > r.ema_slow else "❌"
        macd_ok   = "✅" if r.macd_hist > 0 else "🔴"
        vol_clr   = "bright_green" if r.vol_ratio >= STRATEGY.volume_multiplier else "dim white"
        bb_str    = f"{r.bb_pct*100:.0f}%"
        bb_clr    = "bright_cyan" if r.bb_pct < 0.25 else ("bright_red" if r.bb_pct > 0.80 else "white")
        price_str = f"₹{r.price:>10,.2f}"

        t.add_row(
            _alert_badge(r.alert_level),
            f"[bold]{r.ticker}[/bold]",
            f"[dim]{r.sector}[/dim]",
            price_str,
            _pct_str(r.change_pct),
            f"[{_rsi_colour(r.rsi)}]{r.rsi:.1f}[/{_rsi_colour(r.rsi)}]",
            ema_ok, macd_ok,
            f"[{vol_clr}]{r.vol_ratio:.2f}×[/{vol_clr}]",
            f"[{bb_clr}]{bb_str}[/{bb_clr}]",
            f"₹{r.atr:.2f}",
            _score_bar(r.buy_score),
            _score_bar(r.sell_score),
        )

    console.print(t)


def print_near_signals(rows: list[ScreenerRow]) -> None:
    """Highlight near-signal tickers prominently."""
    near = [r for r in rows if r.alert_level in ("SIGNAL", "NEAR")]
    if not near:
        console.print("\n[dim]No near-signal tickers at this time.[/dim]\n")
        return

    t = Table(
        title="⚡ Near-Signal & Active Alerts",
        box=box.ROUNDED, header_style="bold yellow",
    )
    t.add_column("Alert",  width=12)
    t.add_column("Ticker", width=12, style="bold")
    t.add_column("Dir",    width=8)
    t.add_column("Price ₹",width=13)
    t.add_column("Buy Score",  width=16)
    t.add_column("Sell Score", width=16)
    t.add_column("RSI",    width=8)
    t.add_column("Missing Conditions", width=35)

    for r in near:
        if r.direction == "BUY":
            dir_str = "[bright_green]🟢 BUY[/bright_green]"
        elif r.direction == "SELL":
            dir_str = "[bright_red]🔴 SELL[/bright_red]"
        else:
            dir_str = "[yellow]⚡ NEAR[/yellow]"

        # What's stopping a full signal?
        missing = []
        if r.ema_fast <= r.ema_slow:
            missing.append("EMA cross")
        if not (STRATEGY.rsi_neutral_low <= r.rsi <= STRATEGY.rsi_overbought):
            missing.append(f"RSI {r.rsi:.0f}")
        if r.vol_ratio < STRATEGY.volume_multiplier:
            missing.append(f"Vol {r.vol_ratio:.1f}×")
        if r.macd_hist <= 0:
            missing.append("MACD")
        if r.price <= r.ema_trend:
            missing.append("Trend EMA")
        missing_str = ", ".join(missing[:3]) if missing else "—"

        t.add_row(
            _alert_badge(r.alert_level),
            r.ticker,
            dir_str,
            f"₹{r.price:>10,.2f}",
            _score_bar(r.buy_score),
            _score_bar(r.sell_score),
            f"[{_rsi_colour(r.rsi)}]{r.rsi:.1f}[/{_rsi_colour(r.rsi)}]",
            f"[dim]{missing_str}[/dim]",
        )

    console.print(t)


def print_sector_heatmap(rows: list[ScreenerRow]) -> None:
    """Sector-level momentum summary."""
    sector_stats: dict[str, dict] = {}
    for r in rows:
        s = r.sector
        if s not in sector_stats:
            sector_stats[s] = {"scores": [], "rsies": [], "changes": [], "signals": 0}
        sector_stats[s]["scores"].append(r.buy_score)
        sector_stats[s]["rsies"].append(r.rsi)
        sector_stats[s]["changes"].append(r.change_pct)
        if r.alert_level == "SIGNAL":
            sector_stats[s]["signals"] += 1

    t = Table(title="🌡️  Sector Momentum Heatmap", box=box.ROUNDED,
              header_style="bold cyan")
    t.add_column("Sector",       width=14, style="bold")
    t.add_column("Tickers",      width=8)
    t.add_column("Avg Buy Score",width=16)
    t.add_column("Avg RSI",      width=10)
    t.add_column("Avg Chg%",     width=10)
    t.add_column("Signals",      width=10)
    t.add_column("Momentum",     width=14)

    sorted_sectors = sorted(
        sector_stats.items(),
        key=lambda x: np.mean(x[1]["scores"]), reverse=True,
    )
    for sector, stats in sorted_sectors:
        avg_score  = np.mean(stats["scores"])
        avg_rsi    = np.mean(stats["rsies"])
        avg_chg    = np.mean(stats["changes"])
        n_tickers  = len(stats["scores"])
        n_signals  = stats["signals"]

        if avg_score >= 60:   momentum, m_clr = "🔥 HOT",    "bright_red"
        elif avg_score >= 45: momentum, m_clr = "📈 RISING",  "bright_green"
        elif avg_score >= 30: momentum, m_clr = "↔  NEUTRAL", "yellow"
        else:                 momentum, m_clr = "📉 WEAK",    "dim white"

        t.add_row(
            sector,
            str(n_tickers),
            _score_bar(int(avg_score)),
            f"[{_rsi_colour(avg_rsi)}]{avg_rsi:.1f}[/{_rsi_colour(avg_rsi)}]",
            _pct_str(avg_chg),
            f"[bright_green]{n_signals}[/bright_green]" if n_signals else "[dim]0[/dim]",
            f"[{m_clr}]{momentum}[/{m_clr}]",
        )

    console.print(t)


def print_rsi_extremes(rows: list[ScreenerRow]) -> None:
    """Show tickers at RSI extremes (potential reversals)."""
    oversold   = [r for r in rows if r.rsi < 35]
    overbought = [r for r in rows if r.rsi > 68]

    if not oversold and not overbought:
        return

    t = Table(title="📡 RSI Extremes (Potential Reversal Zones)",
              box=box.SIMPLE, header_style="bold cyan")
    t.add_column("Zone",   width=14)
    t.add_column("Ticker", width=12, style="bold")
    t.add_column("Price ₹",width=13)
    t.add_column("RSI",    width=8)
    t.add_column("Chg%",   width=8)
    t.add_column("Volume", width=8)

    for r in sorted(oversold, key=lambda x: x.rsi):
        t.add_row("[bright_cyan]🔵 OVERSOLD[/bright_cyan]", r.ticker,
                  f"₹{r.price:>10,.2f}",
                  f"[bright_cyan]{r.rsi:.1f}[/bright_cyan]",
                  _pct_str(r.change_pct),
                  f"[dim]{r.vol_ratio:.2f}×[/dim]")

    for r in sorted(overbought, key=lambda x: x.rsi, reverse=True):
        t.add_row("[bright_red]🔴 OVERBOUGHT[/bright_red]", r.ticker,
                  f"₹{r.price:>10,.2f}",
                  f"[bright_red]{r.rsi:.1f}[/bright_red]",
                  _pct_str(r.change_pct),
                  f"[dim]{r.vol_ratio:.2f}×[/dim]")

    console.print(t)


def print_volume_spikes(rows: list[ScreenerRow]) -> None:
    """Highlight tickers with unusual volume (>1.8× average)."""
    spikes = [r for r in rows if r.vol_ratio >= 1.8]
    if not spikes:
        return

    t = Table(title="📊 Volume Spikes  (≥ 1.8× average)",
              box=box.SIMPLE, header_style="bold cyan")
    t.add_column("Ticker",  width=12, style="bold")
    t.add_column("Price ₹", width=13)
    t.add_column("Volume ×",width=10)
    t.add_column("Chg%",    width=8)
    t.add_column("RSI",     width=8)
    t.add_column("Signal",  width=10)

    for r in sorted(spikes, key=lambda x: x.vol_ratio, reverse=True):
        sig_str = (f"[bright_green]BUY[/bright_green]"  if r.direction == "BUY" else
                   f"[bright_red]SELL[/bright_red]"     if r.direction == "SELL" else
                   "[dim]none[/dim]")
        t.add_row(
            r.ticker,
            f"₹{r.price:>10,.2f}",
            f"[bright_yellow]{r.vol_ratio:.2f}×[/bright_yellow]",
            _pct_str(r.change_pct),
            f"[{_rsi_colour(r.rsi)}]{r.rsi:.1f}[/{_rsi_colour(r.rsi)}]",
            sig_str,
        )

    console.print(t)


# ─── Main runner ─────────────────────────────────────────────────────────────

def run_screen(tickers: list[str]) -> None:
    console.rule("[bold cyan]NSE SCREENER[/bold cyan]")
    screener = Screener()

    console.print(f"\n[dim]Scanning {len(tickers)} tickers…[/dim]")
    rows = screener.run(tickers)

    console.print()
    print_near_signals(rows)
    print_rsi_extremes(rows)
    print_volume_spikes(rows)
    print_sector_heatmap(rows)
    print_indicator_table(rows)

    # Summary line
    signals = sum(1 for r in rows if r.alert_level == "SIGNAL")
    near    = sum(1 for r in rows if r.alert_level == "NEAR")
    console.print(
        f"\n[bold]Screen complete:[/bold] "
        f"[bright_green]{signals} SIGNAL(s)[/bright_green]  "
        f"[yellow]{near} NEAR[/yellow]  "
        f"[dim]{len(rows) - signals - near} neutral[/dim]\n"
    )


# ─── CLI ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="NSE Indicator Screener")
    p.add_argument("--ticker",  nargs="+", type=str,
                   help="Specific tickers to screen (default: full watchlist)")
    p.add_argument("--sector",  type=str,
                   help="Filter by sector name (e.g. Banking, Technology)")
    args = p.parse_args()

    if args.ticker:
        tickers = [t.upper() for t in args.ticker]
    elif args.sector:
        tickers = SECTORS.get(args.sector.title(), NSE_WATCHLIST)
    else:
        tickers = NSE_WATCHLIST

    run_screen(tickers)
