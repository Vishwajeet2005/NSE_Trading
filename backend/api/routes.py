"""
api.py — FastAPI backend — ENHANCED with all-stock endpoints
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.core import database as db
from backend.engine.data import fetch_live_quote, fetch_historical
from backend.execution.bridge import ExecutionBridge
from backend.core.notification import NotificationService
from backend.engine.risk import Assessment
from backend.core.settings import NSE_WATCHLIST, load_credentials, save_credentials, refresh_credentials, GROQ
import requests
from backend.engine.strategy import Signal, SignalGenerator
from backend.core import logger as log_mod

log = log_mod.get(__name__)

app = FastAPI(title="NSE Trading System API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init()
bridge = ExecutionBridge()
notifier = NotificationService(console_output=False)
_gen = SignalGenerator()


def _rebuild_assessment(row: dict) -> Assessment:
    sig = Signal(
        ticker      = row["ticker"],
        timestamp   = row["created_at"] if isinstance(row["created_at"], datetime)
                      else datetime.fromisoformat(str(row["created_at"])),
        direction   = row["direction"],
        entry_price = row["entry_price"],
        current_rsi = 50.0,
        current_atr = 0.0,
        confidence  = row["confidence_score"],
        reasons     = json.loads(row.get("signal_reasons", "[]")),
    )
    risk_per_share = abs(row["entry_price"] - row["stop_loss"])
    shares = row["position_size"]
    return Assessment(
        signal=sig, approved=True,
        stop_loss=row["stop_loss"],
        take_profit=row["take_profit"],
        shares=shares,
        position_value=row["position_value"],
        risk_inr=round(risk_per_share * shares, 2),
        reward_inr=round(abs(row["take_profit"] - row["entry_price"]) * shares, 2),
        rr_ratio=round(abs(row["take_profit"] - row["entry_price"]) / max(risk_per_share, 0.001), 2),
        equity=0.0,
    )


# ── Existing endpoints ────────────────────────────────────────────────────────

@app.get("/api/signals/pending")
def get_pending_signals() -> List[Dict[str, Any]]:
    return db.pending_signals()

@app.get("/api/signals/history")
def get_signal_history() -> List[Dict[str, Any]]:
    return db.recent_signals(100)

@app.get("/api/portfolio/open")
def get_open_positions() -> List[Dict[str, Any]]:
    return db.open_trades()

@app.get("/api/watchlist")
def get_watchlist() -> List[str]:
    return NSE_WATCHLIST

@app.get("/api/live-quotes")
def get_live_quotes() -> Dict[str, Any]:
    quotes = {}
    for ticker in NSE_WATCHLIST:
        q = fetch_live_quote(ticker)
        if q:
            quotes[ticker] = q
    return quotes

# ── NEW: Any-stock endpoints ───────────────────────────────────────────────────

@app.get("/api/stock/{ticker}/quote")
def get_stock_quote(ticker: str) -> Dict[str, Any]:
    """Get live quote for ANY NSE ticker."""
    ticker = ticker.upper()
    q = fetch_live_quote(ticker)
    if not q:
        raise HTTPException(status_code=404, detail=f"Could not fetch data for {ticker}")
    q["ticker"] = ticker
    return q

@app.get("/api/stock/{ticker}/history")
def get_stock_history(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    """Get OHLCV history for ANY NSE ticker. Returns chart-ready data."""
    ticker = ticker.upper()
    try:
        df = fetch_historical(ticker, period=period, interval="1d")
        rows = []
        for idx, row in df.tail(180).iterrows():
            rows.append({
                "date": str(idx)[:10],
                "open":   round(float(row["Open"]), 2),
                "high":   round(float(row["High"]), 2),
                "low":    round(float(row["Low"]), 2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return {"ticker": ticker, "period": period, "candles": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ticker}/analysis")
def get_stock_analysis(ticker: str) -> Dict[str, Any]:
    """Run strategy engine analysis on any NSE ticker."""
    ticker = ticker.upper()
    try:
        df = fetch_historical(ticker, period="6mo", interval="1d")
        sig = _gen.analyse(ticker, df)
        return {
            "ticker":      ticker,
            "direction":   sig.direction,
            "confidence":  sig.confidence,
            "entry_price": sig.entry_price,
            "rsi":         round(sig.current_rsi, 2),
            "atr":         round(sig.current_atr, 2),
            "reasons":     sig.reasons,
            "indicators":  sig.indicators,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stock/{ticker}/news")
def get_stock_news(ticker: str) -> List[Dict[str, Any]]:
    """Fetch recent news for a specific ticker."""
    yf_sym = ticker if ("-" in ticker or "=" in ticker) else f"{ticker.upper()}.NS"
    try:
        news_data = yf.Ticker(yf_sym).news
        parsed_news = []
        for n in news_data:
            if isinstance(n, dict):
                content = n.get("content", n)
                title = content.get("title", "")
                
                provider = content.get("provider", {})
                publisher = provider.get("displayName", "Unknown") if isinstance(provider, dict) else "Unknown"
                
                link_obj = content.get("clickThroughUrl", content.get("link", {}))
                link = link_obj.get("url", "") if isinstance(link_obj, dict) else (link_obj if isinstance(link_obj, str) else "")
                
                # Try to get providerPublishTime (unix), fallback to pubDate string
                time_val = content.get("providerPublishTime", 0)
                if not time_val and "pubDate" in content:
                    time_val = content["pubDate"]
                    
                parsed_news.append({
                    "title": title,
                    "publisher": publisher,
                    "link": link,
                    "time": time_val
                })
        return parsed_news
    except Exception as e:
        log.error(f"Failed to fetch news for {yf_sym}: {e}")
        return []

@app.get("/api/market/overview")
def get_market_overview() -> Dict[str, Any]:
    """Summary stats across the watchlist."""
    quotes = {}
    buys = sells = neutral = 0
    for ticker in NSE_WATCHLIST:
        q = fetch_live_quote(ticker)
        if q:
            quotes[ticker] = q
    gainers = sorted(
        [(t, q["change_pct"]) for t, q in quotes.items()],
        key=lambda x: x[1], reverse=True
    )
    return {
        "timestamp":    datetime.utcnow().isoformat(),
        "total_stocks": len(NSE_WATCHLIST),
        "gainers":      gainers[:5],
        "losers":       gainers[-5:],
        "quotes":       quotes,
    }

class DenyRequest(BaseModel):
    note: str = ""

@app.post("/api/signals/{signal_id}/approve")
def approve_signal(signal_id: int):
    signals = db.pending_signals()
    sig = next((s for s in signals if s["id"] == signal_id), None)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    assessment = _rebuild_assessment(sig)
    result = bridge.execute(signal_id, assessment)
    if result.success:
        notifier.notify_execution(sig["ticker"], sig["direction"], sig["position_size"],
                                  sig["entry_price"], result.order_id, signal_id)
        return {"success": True, "order_id": result.order_id}
    raise HTTPException(status_code=400, detail=result.error)

@app.post("/api/signals/{signal_id}/deny")
def deny_signal(signal_id: int, req: DenyRequest):
    signals = db.pending_signals()
    sig = next((s for s in signals if s["id"] == signal_id), None)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    bridge.deny(signal_id, sig["ticker"], req.note)
    notifier.notify_denial(signal_id, sig["ticker"], req.note)
    return {"success": True}

@app.get("/api/credentials")
def get_credentials() -> Dict[str, Any]:
    creds = load_credentials()
    # Return masked credentials or just presence flags to avoid exposing secrets
    return {
        "zerodha_configured": bool(creds.get("ZERODHA_API_KEY") and creds.get("ZERODHA_ACCESS_TOKEN")),
        "telegram_configured": bool(creds.get("TELEGRAM_BOT_TOKEN") and creds.get("TELEGRAM_CHAT_ID")),
        "groq_configured": bool(creds.get("GROQ_API_KEY"))
    }

class CredentialsRequest(BaseModel):
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    ZERODHA_ACCESS_TOKEN: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    GROQ_API_KEY: str = ""

@app.post("/api/credentials")
def update_credentials(req: CredentialsRequest):
    # Only update provided fields (non-empty) or overwrite all?
    # Usually we want to overwrite with what's provided. If a field is empty, maybe keep existing?
    # We will merge it.
    creds = load_credentials()
    if req.ZERODHA_API_KEY: creds["ZERODHA_API_KEY"] = req.ZERODHA_API_KEY
    if req.ZERODHA_API_SECRET: creds["ZERODHA_API_SECRET"] = req.ZERODHA_API_SECRET
    if req.ZERODHA_ACCESS_TOKEN: creds["ZERODHA_ACCESS_TOKEN"] = req.ZERODHA_ACCESS_TOKEN
    if req.TELEGRAM_BOT_TOKEN: creds["TELEGRAM_BOT_TOKEN"] = req.TELEGRAM_BOT_TOKEN
    if req.TELEGRAM_CHAT_ID: creds["TELEGRAM_CHAT_ID"] = req.TELEGRAM_CHAT_ID
    if req.GROQ_API_KEY: creds["GROQ_API_KEY"] = req.GROQ_API_KEY
    
    save_credentials(creds)
    refresh_credentials()
    return {"success": True}

import yfinance as yf
from backend.ml.predict import generate_prediction

@app.post("/api/ml/predict")
def ml_predict(body: Dict[str, Any]):
    try:
        stock = body.get("stock")
        if stock:
            yf_sym = stock if ("-" in stock or "=" in stock) else f"{stock}.NS"
            try:
                news_data = yf.Ticker(yf_sym).news
                news_titles = []
                for n in news_data:
                    if isinstance(n, dict):
                        content = n.get("content", n)
                        title = content.get("title", "")
                        if title:
                            news_titles.append(title)
                body["news"] = news_titles[:5]
            except Exception as e:
                log.error(f"Failed to fetch news for {yf_sym}: {e}")
                body["news"] = []
        
        prediction = generate_prediction(body)
        return prediction
    except Exception as e:
        log.error("ML Prediction failed: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))

# ==============================================================================
# STATIC FRONTEND SERVING (For Production/Render)
# ==============================================================================
frontend_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str):
        if not full_path.startswith("api/"):
            index_path = os.path.join(frontend_dist, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Not Found")



