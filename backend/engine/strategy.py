"""
strategy_engine.py — Quantitative Strategy Engine (NSE)
========================================================
Computes EMA / RSI / MACD / Bollinger Bands / ATR / Volume indicators
and produces boolean BUY / SELL signals with a 0-100 confidence score.

BUY fires when score ≥ 60:
  [20] Price > EMA-50 (uptrend filter)
  [20] EMA-9 crossed above EMA-21 within 3 candles
  [15] RSI(14) between 40-70 AND rising
  [20] MACD line crossed above signal within 3 candles
  [15] Volume > 1.2× 20-day average
  [10] Price near lower Bollinger Band (mean-reversion zone)

SELL fires when score ≥ 60:
  [30] EMA-9 crossed below EMA-21
  [30] RSI > 70 (overbought)
  [25] MACD bear crossover
  [15] Price < EMA-50 (downtrend)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import pandas_ta as ta


from backend.core import logger as log_mod
from backend.core.settings import RISK, STRATEGY

log = log_mod.get(__name__)

# ── Confidence weights ────────────────────────────────────────────────────────
_BUY_W  = dict(trend=20, ema_cross=20, rsi=15, macd=20, volume=15, bb=10)
_SELL_W = dict(ema_cross=30, rsi_ob=30, macd=25, trend=15)


# ─── Output dataclass ─────────────────────────────────────────────────────────

@dataclass
class Signal:
    """
    Structured output from the Strategy Engine.

    Attributes
    ----------
    ticker          : NSE symbol
    timestamp       : UTC time of generation
    direction       : "BUY" | "SELL" | "NONE"
    entry_price     : Last close price in ₹
    current_rsi     : RSI value on the signal candle
    current_atr     : ATR value for stop placement
    confidence      : 0-100 score
    reasons         : Human-readable list of condition outcomes
    indicators      : Dict of raw indicator values for logging/display
    """
    ticker:     str
    timestamp:  datetime
    direction:  str
    entry_price: float
    current_rsi: float
    current_atr: float
    confidence: int
    reasons:    list[str] = field(default_factory=list)
    indicators: dict      = field(default_factory=dict)

    @property
    def has_signal(self) -> bool:
        return self.direction in ("BUY", "SELL")

    def to_dict(self) -> dict:
        return dict(ticker=self.ticker, timestamp=self.timestamp.isoformat(),
                    direction=self.direction, entry_price=self.entry_price,
                    rsi=round(self.current_rsi, 2), atr=round(self.current_atr, 4),
                    confidence=self.confidence, reasons=self.reasons)


# ─── Indicator Engine ─────────────────────────────────────────────────────────

class IndicatorEngine:
    """Augments an OHLCV DataFrame with all required technical indicators."""

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add indicator columns to df and return the augmented DataFrame.

        Raises ValueError if fewer than min_candles rows are available.
        """
        if len(df) < STRATEGY.min_candles:
            raise ValueError(f"Need {STRATEGY.min_candles} candles, got {len(df)}")

        df = df.copy()

        # ── EMAs ─────────────────────────────────────────────────────────────
        df["ema_fast"]  = ta.ema(df["Close"], length=STRATEGY.ema_fast_period)
        df["ema_slow"]  = ta.ema(df["Close"], length=STRATEGY.ema_slow_period)
        df["ema_trend"] = ta.ema(df["Close"], length=STRATEGY.ema_trend_period)

        df["ema_bull_cross"] = (
            (df["ema_fast"] > df["ema_slow"]) &
            (df["ema_fast"].shift(1) <= df["ema_slow"].shift(1))
        ).astype(int)
        df["ema_bear_cross"] = (
            (df["ema_fast"] < df["ema_slow"]) &
            (df["ema_fast"].shift(1) >= df["ema_slow"].shift(1))
        ).astype(int)

        # ── RSI ───────────────────────────────────────────────────────────────
        df["rsi"]        = ta.rsi(df["Close"], length=STRATEGY.rsi_period)
        df["rsi_rising"] = (df["rsi"] > df["rsi"].shift(1)).astype(int)

        # ── MACD ──────────────────────────────────────────────────────────────
        macd = ta.macd(df["Close"], fast=STRATEGY.macd_fast,
                       slow=STRATEGY.macd_slow, signal=STRATEGY.macd_signal)
        if macd is not None and not macd.empty:
            df["macd_line"]   = macd.iloc[:, 0]
            df["macd_signal"] = macd.iloc[:, 2]
            df["macd_hist"]   = macd.iloc[:, 1]
        else:
            df["macd_line"] = df["macd_signal"] = df["macd_hist"] = np.nan

        df["macd_bull"] = (
            (df["macd_line"] > df["macd_signal"]) &
            (df["macd_line"].shift(1) <= df["macd_signal"].shift(1))
        ).astype(int)
        df["macd_bear"] = (
            (df["macd_line"] < df["macd_signal"]) &
            (df["macd_line"].shift(1) >= df["macd_signal"].shift(1))
        ).astype(int)

        # ── ATR ───────────────────────────────────────────────────────────────
        df["atr"] = ta.atr(df["High"], df["Low"], df["Close"],
                           length=STRATEGY.atr_period)

        # ── Bollinger Bands (BBL=lower, BBM=mid, BBU=upper) ──────────────────
        bb = ta.bbands(df["Close"], length=STRATEGY.bb_period, std=STRATEGY.bb_std_dev)
        if bb is not None and not bb.empty:
            df["bb_lower"] = bb.iloc[:, 0]
            df["bb_mid"]   = bb.iloc[:, 1]
            df["bb_upper"] = bb.iloc[:, 2]
        else:
            df["bb_lower"] = df["bb_mid"] = df["bb_upper"] = np.nan

        # ── Volume ratio ──────────────────────────────────────────────────────
        df["vol_ma20"]  = df["Volume"].rolling(20).mean()
        df["vol_ratio"] = df["Volume"] / df["vol_ma20"]

        # Drop warm-up NaNs
        required = ["ema_fast", "ema_slow", "ema_trend", "rsi", "macd_line", "atr"]
        return df.dropna(subset=required)


# ─── Signal Generator ─────────────────────────────────────────────────────────

class SignalGenerator:
    """
    Evaluates indicator conditions and produces a Signal for a given ticker.

    Usage
    -----
    gen = SignalGenerator()
    signal = gen.analyse("RELIANCE", ohlcv_df)
    """

    def __init__(self) -> None:
        self._ie = IndicatorEngine()

    # ── Private evaluators ────────────────────────────────────────────────────

    def _buy_score(self, df: pd.DataFrame, idx: int) -> tuple[int, list[str]]:
        row   = df.iloc[idx]
        score = 0
        reasons: list[str] = []

        # 1. Price above trend EMA
        if row["Close"] > row["ema_trend"]:
            score += _BUY_W["trend"]
            reasons.append(f"✅ Price ₹{row['Close']:.2f} > EMA{STRATEGY.ema_trend_period} ₹{row['ema_trend']:.2f} (uptrend)")
        else:
            reasons.append(f"❌ Price below EMA{STRATEGY.ema_trend_period} — no uptrend")

        # 2. EMA bull crossover (recent 3 candles)
        if df["ema_bull_cross"].iloc[max(0, idx-2): idx+1].any():
            score += _BUY_W["ema_cross"]
            reasons.append(f"✅ EMA{STRATEGY.ema_fast_period} crossed above EMA{STRATEGY.ema_slow_period} (bull crossover)")
        else:
            reasons.append(f"❌ No recent EMA bull crossover")

        # 3. RSI in buy zone and rising
        rsi_ok = STRATEGY.rsi_neutral_low <= row["rsi"] <= STRATEGY.rsi_overbought
        if rsi_ok and row["rsi_rising"]:
            score += _BUY_W["rsi"]
            reasons.append(f"✅ RSI {row['rsi']:.1f} in zone [{STRATEGY.rsi_neutral_low}-{STRATEGY.rsi_overbought}] and rising")
        else:
            reasons.append(f"❌ RSI {row['rsi']:.1f} — not in buy zone or falling")

        # 4. MACD bull crossover (recent 3 candles)
        if df["macd_bull"].iloc[max(0, idx-2): idx+1].any():
            score += _BUY_W["macd"]
            reasons.append(f"✅ MACD bull crossover — momentum confirmed")
        else:
            reasons.append(f"❌ No MACD bull crossover")

        # 5. Volume confirmation
        if row["vol_ratio"] >= STRATEGY.volume_multiplier:
            score += _BUY_W["volume"]
            reasons.append(f"✅ Volume {row['vol_ratio']:.2f}× avg (≥{STRATEGY.volume_multiplier}× needed)")
        else:
            reasons.append(f"❌ Volume {row['vol_ratio']:.2f}× avg — insufficient")

        # 6. Near lower Bollinger Band
        if not (pd.isna(row["bb_lower"]) or pd.isna(row["bb_mid"])):
            rng = row["bb_mid"] - row["bb_lower"]
            if rng > 0 and (row["Close"] - row["bb_lower"]) / rng < 0.35:
                score += _BUY_W["bb"]
                reasons.append(f"✅ Price near lower BB ₹{row['bb_lower']:.2f} — mean-reversion entry")
            else:
                reasons.append(f"❌ Price not near lower Bollinger Band")

        return score, reasons

    def _sell_score(self, df: pd.DataFrame, idx: int) -> tuple[int, list[str]]:
        row   = df.iloc[idx]
        score = 0
        reasons: list[str] = []

        if df["ema_bear_cross"].iloc[max(0, idx-2): idx+1].any():
            score += _SELL_W["ema_cross"]
            reasons.append(f"🔴 EMA{STRATEGY.ema_fast_period} crossed below EMA{STRATEGY.ema_slow_period} (bear crossover)")

        if row["rsi"] > STRATEGY.rsi_overbought:
            score += _SELL_W["rsi_ob"]
            reasons.append(f"🔴 RSI {row['rsi']:.1f} — overbought (>{STRATEGY.rsi_overbought})")

        if df["macd_bear"].iloc[max(0, idx-2): idx+1].any():
            score += _SELL_W["macd"]
            reasons.append(f"🔴 MACD bear crossover — momentum reversing")

        if row["Close"] < row["ema_trend"]:
            score += _SELL_W["trend"]
            reasons.append(f"🔴 Price ₹{row['Close']:.2f} below EMA{STRATEGY.ema_trend_period} ₹{row['ema_trend']:.2f}")

        return score, reasons

    # ── Public API ────────────────────────────────────────────────────────────

    def analyse(self, ticker: str, ohlcv: pd.DataFrame) -> Signal:
        """
        Run full analysis on the most recent candle of ohlcv.

        Parameters
        ----------
        ticker : NSE symbol
        ohlcv  : Clean OHLCV DataFrame from data_ingestion

        Returns
        -------
        Signal dataclass
        """
        log.info("[%s] Analysing…", ticker)
        df  = self._ie.compute(ohlcv)
        row = df.iloc[-1]

        entry  = float(row["Close"])
        rsi    = float(row["rsi"])   if not pd.isna(row["rsi"])  else 50.0
        atr    = float(row["atr"])   if not pd.isna(row["atr"])  else 0.0
        indics = dict(
            ema_fast   = round(float(row["ema_fast"]), 2),
            ema_slow   = round(float(row["ema_slow"]), 2),
            ema_trend  = round(float(row["ema_trend"]), 2),
            rsi        = round(rsi, 2),
            macd_line  = round(float(row["macd_line"]), 4),
            macd_sig   = round(float(row["macd_signal"]), 4),
            atr        = round(atr, 2),
            vol_ratio  = round(float(row["vol_ratio"]), 3),
            bb_lower   = round(float(row["bb_lower"]), 2),
            bb_upper   = round(float(row["bb_upper"]), 2),
        )

        # BUY check first
        b_score, b_reasons = self._buy_score(df, -1)
        if b_score >= RISK.min_signal_confidence:
            log.info("[%s] 🟢 BUY | confidence=%d | ₹%.2f", ticker, b_score, entry)
            return Signal(ticker, datetime.utcnow(), "BUY", entry, rsi, atr,
                          b_score, b_reasons, indics)

        # SELL check
        s_score, s_reasons = self._sell_score(df, -1)
        if s_score >= RISK.min_signal_confidence:
            log.info("[%s] 🔴 SELL | confidence=%d | ₹%.2f", ticker, s_score, entry)
            return Signal(ticker, datetime.utcnow(), "SELL", entry, rsi, atr,
                          s_score, s_reasons, indics)

        log.info("[%s] ⚪ NONE | B:%d S:%d | RSI:%.1f", ticker, b_score, s_score, rsi)
        return Signal(ticker, datetime.utcnow(), "NONE", entry, rsi, atr,
                      max(b_score, s_score), b_reasons, indics)

    def historical_signals(self, ticker: str, ohlcv: pd.DataFrame) -> pd.DataFrame:
        """
        Label every row with buy_signal / sell_signal booleans.
        Used by the backtesting engine.
        """
        log.info("[%s] Generating historical signals on %d rows…", ticker, len(ohlcv))
        df = self._ie.compute(ohlcv)

        buy_sigs, sell_sigs, b_scores, s_scores = [], [], [], []
        for i in range(len(df)):
            if i < STRATEGY.min_candles:
                buy_sigs.append(False); sell_sigs.append(False)
                b_scores.append(0); s_scores.append(0)
                continue
            bs, _ = self._buy_score(df, i)
            ss, _ = self._sell_score(df, i)
            if bs >= RISK.min_signal_confidence:
                buy_sigs.append(True); sell_sigs.append(False)
            elif ss >= RISK.min_signal_confidence:
                buy_sigs.append(False); sell_sigs.append(True)
            else:
                buy_sigs.append(False); sell_sigs.append(False)
            b_scores.append(bs); s_scores.append(ss)

        df["buy_signal"]  = buy_sigs
        df["sell_signal"] = sell_sigs
        df["buy_score"]   = b_scores
        df["sell_score"]  = s_scores
        log.info("[%s] Signals — BUY:%d  SELL:%d", ticker,
                 sum(buy_sigs), sum(sell_sigs))
        return df

