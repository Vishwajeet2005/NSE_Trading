"""
notification.py — Multi-channel Notification Service
======================================================
Delivers signal alerts via:
  1. Rich console  (always active — colourised terminal table)
  2. Telegram bot  (optional — requires .env credentials)

Telegram messages include full trade details in MarkdownV2 format.
Console uses Rich tables for a clean operator-friendly display.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import requests
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from backend.core import logger as log_mod
from backend.engine.risk import Assessment
from backend.core.settings import SYSTEM, TELEGRAM

log     = log_mod.get(__name__)
console = Console()

_API_TIMEOUT = 10


# ─── Telegram ─────────────────────────────────────────────────────────────────

class TelegramNotifier:
    """Sends formatted Telegram messages via Bot API."""

    def __init__(self) -> None:
        self.enabled  = TELEGRAM.enabled
        self._api     = f"https://api.telegram.org/bot{TELEGRAM.bot_token}"
        self._chat_id = TELEGRAM.chat_id
        if not self.enabled:
            log.warning("Telegram disabled — add TELEGRAM_BOT_TOKEN to .env")

    def _post(self, payload: dict) -> bool:
        if not self.enabled:
            return False
        try:
            r = requests.post(f"{self._api}/sendMessage",
                              json=payload, timeout=_API_TIMEOUT)
            r.raise_for_status()
            return r.json().get("ok", False)
        except requests.RequestException as exc:
            log.error("Telegram send failed: %s", exc)
            return False

    def _escape(self, text: str) -> str:
        """Escape special chars for Telegram MarkdownV2."""
        for ch in r"_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    def send_signal(self, a: Assessment, signal_id: int) -> bool:
        sig   = a.signal
        emoji = "🟢" if sig.direction == "BUY" else "🔴"
        sl_pct = abs(sig.entry_price - a.stop_loss) / sig.entry_price * 100
        tp_pct = abs(a.take_profit - sig.entry_price) / sig.entry_price * 100
        ts     = datetime.utcnow().strftime("%d %b %Y %H:%M UTC")

        # Build reasons text (first 4)
        reasons = "\n".join(f"  • {self._escape(r)}" for r in sig.reasons[:4])

        msg = (
            f"{emoji} *SIGNAL \\#{signal_id}* — `{sig.ticker}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 Direction: `{sig.direction}`\n"
            f"💰 Entry: `₹{sig.entry_price:,.2f}`\n"
            f"🛑 Stop Loss: `₹{a.stop_loss:,.2f}` \\(\\-{sl_pct:.1f}%\\)\n"
            f"🎯 Target: `₹{a.take_profit:,.2f}` \\(\\+{tp_pct:.1f}%\\)\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📦 Shares: `{a.shares}`\n"
            f"💵 Value: `₹{a.position_value:,.0f}`\n"
            f"⚠️  Risk: `₹{a.risk_inr:,.0f}`\n"
            f"📈 Reward: `₹{a.reward_inr:,.0f}`\n"
            f"⚖️  R:R: `1:{a.rr_ratio:.1f}`\n"
            f"🎯 Score: `{sig.confidence}/100`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{reasons}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"⏰ `{ts}`\n"
            f"👉 Dashboard: `http://localhost:{SYSTEM.dashboard_port}`"
        )
        return self._post({"chat_id": self._chat_id, "text": msg,
                           "parse_mode": "MarkdownV2",
                           "disable_web_page_preview": True})

    def send_execution(self, ticker: str, direction: str, shares: int,
                       price: float, order_id: str, signal_id: int) -> bool:
        emoji = "✅" if direction == "BUY" else "🔻"
        msg = (
            f"{emoji} *ORDER EXECUTED* \\#{signal_id}\n"
            f"📌 `{ticker}` — {direction}\n"
            f"📦 {shares} shares @ ₹{self._escape(f'{price:,.2f}')}\n"
            f"🔑 Order: `{order_id}`\n"
            f"⏰ `{datetime.utcnow().strftime('%d %b %H:%M UTC')}`"
        )
        return self._post({"chat_id": self._chat_id, "text": msg,
                           "parse_mode": "MarkdownV2"})

    def send_denial(self, signal_id: int, ticker: str, note: str = "") -> bool:
        msg = (
            f"🚫 *Signal \\#{signal_id} DENIED* — `{ticker}`\n"
            f"Note: {self._escape(note or 'No reason given')}"
        )
        return self._post({"chat_id": self._chat_id, "text": msg,
                           "parse_mode": "MarkdownV2"})


# ─── Rich Console ─────────────────────────────────────────────────────────────

class ConsoleNotifier:
    """Rich-formatted terminal output for signal alerts and scan summaries."""

    @staticmethod
    def show_signal(a: Assessment, signal_id: int) -> None:
        sig   = a.signal
        clr   = "bright_green" if sig.direction == "BUY" else "bright_red"
        emoji = "🟢" if sig.direction == "BUY" else "🔴"
        sl_pct = abs(sig.entry_price - a.stop_loss) / sig.entry_price * 100
        tp_pct = abs(a.take_profit - sig.entry_price) / sig.entry_price * 100

        t = Table(
            title=f"{emoji} Signal #{signal_id} — {sig.ticker}",
            title_style=f"bold {clr}",
            box=box.ROUNDED, show_header=True,
            header_style="bold cyan", expand=True,
        )
        t.add_column("Parameter",  style="bold white", width=22)
        t.add_column("Value",      style="bright_white", width=28)
        t.add_column("Parameter",  style="bold white", width=22)
        t.add_column("Value",      style="bright_white", width=28)

        def r(p1, v1, p2="", v2=""):
            t.add_row(p1, v1, p2, v2)

        r("Direction",   f"[{clr}]{sig.direction}[/{clr}]",
          "Confidence",  f"{sig.confidence}/100")
        r("Entry Price", f"₹{sig.entry_price:>12,.2f}",
          "Shares",      str(a.shares))
        r("Stop Loss",
          f"[bright_red]₹{a.stop_loss:>12,.2f}[/bright_red] (-{sl_pct:.1f}%)",
          "Position Value", f"₹{a.position_value:>12,.0f}")
        r("Take Profit",
          f"[bright_green]₹{a.take_profit:>12,.2f}[/bright_green] (+{tp_pct:.1f}%)",
          "Max Risk ₹",  f"₹{a.risk_inr:>12,.0f}")
        r("R:R Ratio",   f"1:{a.rr_ratio:.1f}",
          "Max Reward ₹", f"₹{a.reward_inr:>12,.0f}")
        r("RSI",         f"{sig.current_rsi:.1f}",
          "ATR",         f"₹{sig.current_atr:.2f}")

        console.print(t)
        console.print(Panel("\n".join(sig.reasons),
                            title="[bold yellow]Signal Breakdown[/bold yellow]",
                            border_style="yellow"))
        console.print(f"\n[bold cyan]👉 Approve/Deny at http://localhost:{SYSTEM.dashboard_port}[/bold cyan]\n")

    @staticmethod
    def show_scan_summary(results: dict[str, str], equity: float) -> None:
        t = Table(title="📡 NSE Scan Summary", box=box.SIMPLE_HEAVY,
                  header_style="bold cyan", show_header=True)
        t.add_column("Ticker",  style="bold", width=14)
        t.add_column("Signal",  width=12)
        t.add_column("Status",  width=20)

        for ticker, direction in sorted(results.items()):
            if direction == "BUY":
                t.add_row(ticker, "[bright_green]🟢 BUY[/bright_green]",
                          "[bright_green]Alert sent[/bright_green]")
            elif direction == "SELL":
                t.add_row(ticker, "[bright_red]🔴 SELL[/bright_red]",
                          "[bright_red]Alert sent[/bright_red]")
            elif direction == "BLOCKED":
                t.add_row(ticker, "[yellow]⚠ BLOCKED[/yellow]",
                          "[yellow]Risk rejected[/yellow]")
            else:
                t.add_row(ticker, "[dim]⚪ NONE[/dim]", "[dim]No action[/dim]")

        console.print(t)
        console.print(f"[dim]Account equity: ₹{equity:,.0f}[/dim]")


# ─── Unified facade ───────────────────────────────────────────────────────────

class NotificationService:
    """Sends to all configured channels simultaneously."""

    def __init__(self, console_output: bool = True) -> None:
        self.tg  = TelegramNotifier()
        self.con = console_output

    def notify_signal(self, a: Assessment, signal_id: int) -> None:
        if self.con:
            ConsoleNotifier.show_signal(a, signal_id)
        self.tg.send_signal(a, signal_id)

    def notify_execution(self, ticker: str, direction: str,
                         shares: int, price: float,
                         order_id: str, signal_id: int) -> None:
        log.info("Executed: %s %s × %d @ ₹%.2f | order=%s",
                 direction, ticker, shares, price, order_id)
        self.tg.send_execution(ticker, direction, shares, price, order_id, signal_id)

    def notify_denial(self, signal_id: int, ticker: str, note: str = "") -> None:
        log.info("Signal #%d (%s) denied. Note: %s", signal_id, ticker, note)
        self.tg.send_denial(signal_id, ticker, note)
