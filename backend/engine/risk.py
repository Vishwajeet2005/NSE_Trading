"""
risk_management.py — Risk Management Module (NSE / INR)
========================================================
Every signal must pass through this module before notification.

Checks (in order):
  1. Direction is BUY or SELL (not NONE)
  2. Confidence ≥ min_signal_confidence
  3. Position sizing produces ≥ 1 share
  4. Open positions < max_open_positions
  5. Position value respects cash-reserve floor
  6. Stop-loss is logically on the right side of entry
  7. Actual R:R ≥ 2.0 for this specific trade

Position Sizing (fixed-fractional)
------------------------------------
  risk_per_share = |entry − stop_loss|
  max_risk_inr     = equity × 1%
  raw_shares     = max_risk_inr / risk_per_share
  shares         = min(raw_shares, equity × 10% / entry)

Stop uses tighter of: fixed-pct OR ATR-based level.
All amounts denominated in Indian Rupees (₹).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.core import logger as log_mod
from backend.core.settings import RISK
from backend.engine.strategy import Signal

log = log_mod.get(__name__)


@dataclass
class Assessment:
    """
    Result of risk evaluation for one signal.

    Attributes
    ----------
    signal          : Original Signal from StrategyEngine
    approved        : False → signal must be discarded
    rejection       : Reason string when approved=False
    stop_loss       : Computed stop-loss price (₹)
    take_profit     : Computed take-profit price (₹)
    shares          : Number of whole shares
    position_value  : Total position cost (₹)
    risk_inr        : Max loss if stop-loss hits (₹)
    reward_inr      : Max gain if take-profit hits (₹)
    rr_ratio        : reward / risk
    equity          : Account equity used for sizing (₹)
    """
    signal:         Signal
    approved:       bool
    rejection:      str   = ""
    stop_loss:      float = 0.0
    take_profit:    float = 0.0
    shares:         int   = 0
    position_value: float = 0.0
    risk_inr:       float = 0.0
    reward_inr:     float = 0.0
    rr_ratio:       float = 0.0
    equity:         float = 0.0

    def summary(self) -> str:
        if not self.approved:
            return f"[BLOCKED] {self.signal.ticker} — {self.rejection}"
        sym = RISK  # just to reference the module
        return (
            f"[APPROVED] {self.signal.ticker} | {self.signal.direction} "
            f"{self.shares} sh @ ₹{self.signal.entry_price:.2f} | "
            f"SL ₹{self.stop_loss:.2f} | TP ₹{self.take_profit:.2f} | "
            f"R:R 1:{self.rr_ratio:.1f} | Risk ₹{self.risk_inr:,.0f}"
        )


class RiskManager:
    """
    Applies all hardcoded NSE risk rules to a Signal.

    Example
    -------
    rm = RiskManager()
    a  = rm.assess(signal, equity=1_000_000, open_positions=1)
    if a.approved:
        notify_operator(a)
    """

    # ── Stop / TP calculation ─────────────────────────────────────────────────

    def _stops(self, entry: float, atr: float, direction: str) -> tuple[float, float]:
        """
        Compute stop-loss and take-profit prices.

        Uses the tighter of fixed-percentage or ATR-based stop.
        Returns (stop_loss_price, take_profit_price).
        """
        mult = RISK.atr_stop_multiplier
        if direction == "BUY":
            pct_sl = entry * (1 - RISK.stop_loss_pct)
            atr_sl = entry - atr * mult if atr > 0 else pct_sl
            sl     = max(pct_sl, atr_sl)          # tighter (higher) for long

            pct_tp = entry * (1 + RISK.take_profit_pct)
            atr_tp = entry + atr * mult * 3 if atr > 0 else pct_tp
            tp     = min(pct_tp, atr_tp)          # conservative (lower)
        else:
            pct_sl = entry * (1 + RISK.stop_loss_pct)
            atr_sl = entry + atr * mult if atr > 0 else pct_sl
            sl     = min(pct_sl, atr_sl)          # tighter (lower) for short

            pct_tp = entry * (1 - RISK.take_profit_pct)
            atr_tp = entry - atr * mult * 3 if atr > 0 else pct_tp
            tp     = max(pct_tp, atr_tp)

        return round(sl, 2), round(tp, 2)

    # ── Position sizing ───────────────────────────────────────────────────────

    def _size(self, entry: float, sl: float, equity: float) -> tuple[int, float]:
        """
        Return (whole_shares, total_position_value_₹).

        Formula:  shares = (equity × risk%) / |entry − sl|
        Capped at equity × position_cap% / entry.
        """
        risk_per_share = abs(entry - sl)
        if risk_per_share < 0.01:
            return 0, 0.0
        budget  = equity * RISK.max_risk_per_trade_pct
        raw     = budget / risk_per_share
        cap     = (equity * RISK.max_position_size_pct) / entry
        shares  = int(min(raw, cap))
        return shares, round(shares * entry, 2)

    # ── Hard-rule validator ───────────────────────────────────────────────────

    def _hard_rules(
        self,
        sig: Signal,
        sl: float, tp: float,
        shares: int, pos_val: float,
        equity: float, open_pos: int,
    ) -> Optional[str]:
        """Return rejection reason string, or None if all rules pass."""
        if sig.confidence < RISK.min_signal_confidence:
            return f"Confidence {sig.confidence} < threshold {RISK.min_signal_confidence}"

        if shares < 1:
            return "Position size = 0 shares (equity too small or stop too tight)"

        if open_pos >= RISK.max_open_positions:
            return f"Max open positions ({RISK.max_open_positions}) already reached"

        if pos_val > equity * (1 - RISK.min_cash_reserve_pct):
            return (f"Position ₹{pos_val:,.0f} breaches "
                    f"{RISK.min_cash_reserve_pct*100:.0f}% cash reserve")

        if sig.direction == "BUY"  and sl >= sig.entry_price:
            return f"Stop ₹{sl:.2f} is above entry ₹{sig.entry_price:.2f}"
        if sig.direction == "SELL" and sl <= sig.entry_price:
            return f"Stop ₹{sl:.2f} is below entry ₹{sig.entry_price:.2f}"

        risk   = abs(sig.entry_price - sl) * shares
        reward = abs(tp - sig.entry_price) * shares
        rr     = reward / risk if risk > 0 else 0.0
        if rr < 2.0:
            return f"R:R {rr:.2f} < minimum 2.0 (Risk ₹{risk:,.0f} / Reward ₹{reward:,.0f})"

        return None

    # ── Public entry point ────────────────────────────────────────────────────

    def assess(
        self,
        signal: Signal,
        equity: float,
        open_positions: int = 0,
    ) -> Assessment:
        """
        Apply all risk rules to signal and return an Assessment.

        Parameters
        ----------
        signal         : Signal from StrategyEngine
        equity         : Current account equity in ₹
        open_positions : Number of currently open positions

        Returns
        -------
        Assessment   (approved=True means show to operator; False = discard)
        """
        log.info("[%s] Risk check → %s | confidence=%d | ₹%.2f",
                 signal.ticker, signal.direction, signal.confidence, signal.entry_price)

        if not signal.has_signal:
            return Assessment(signal=signal, approved=False, equity=equity,
                              rejection="Direction is NONE — not tradeable")

        sl, tp     = self._stops(signal.entry_price, signal.current_atr, signal.direction)
        shares, pv = self._size(signal.entry_price, sl, equity)
        rejection  = self._hard_rules(signal, sl, tp, shares, pv, equity, open_positions)

        if rejection:
            log.warning("[%s] BLOCKED: %s", signal.ticker, rejection)
            return Assessment(signal=signal, approved=False, rejection=rejection,
                              stop_loss=sl, take_profit=tp, shares=shares,
                              position_value=pv, equity=equity)

        risk_inr   = abs(signal.entry_price - sl) * shares
        reward_inr = abs(tp - signal.entry_price) * shares
        rr       = round(reward_inr / risk_inr, 2) if risk_inr > 0 else 0.0

        a = Assessment(signal=signal, approved=True,
                       stop_loss=sl, take_profit=tp,
                       shares=shares, position_value=round(pv, 2),
                       risk_inr=round(risk_inr, 2), reward_inr=round(reward_inr, 2),
                       rr_ratio=rr, equity=equity)
        log.info("[%s] %s", signal.ticker, a.summary())
        return a
