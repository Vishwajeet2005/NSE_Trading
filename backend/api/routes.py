"""
api.py — FastAPI backend — Refactored for Security & Stability
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yfinance as yf

from backend.core import database as db
from backend.engine.data import fetch_live_quote, fetch_historical
from backend.execution.bridge import ExecutionBridge
from backend.core.notification import NotificationService
from backend.core.settings import NSE_WATCHLIST, load_credentials, save_credentials, refresh_credentials
from backend.engine.strategy import Signal, SignalGenerator
from backend.core import logger as log_mod
from backend.ml.predict import generate_prediction

log = log_mod.get(__name__)

app = FastAPI(title="NSE Trading System API")

# SECURITY FIX: Restrict CORS to specific origins in production, allow localhost for dev.
ALLOWED_ORIGINS = [
    "http://localhost:5173", 
    "http://localhost:8000",
    "https://nse-trading-system-6117.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"], # Block PUT/DELETE if unused
    allow_headers=["*"],
)

db.init()
bridge = ExecutionBridge()
notifier = NotificationService(console_output=False)
_gen = SignalGenerator()

# SECURITY FIX: Implement basic API Key protection for sensitive routes
API_KEY_NAME = "X-API-KEY"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_api_key(api_key_header: str = Security(api_key_header)):
    # In a real app, store this in an env var. We use a fallback for local dev.
    expected_key = os.getenv("APP_ADMIN_KEY", "dev-secret-key")
    if api_key_header != expected_key:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return api_key_header

def validate_ticker(ticker: str) -> str:
    """SECURITY FIX: Prevent injection by strictly validating ticker format."""
    ticker = ticker.upper()
    if not re.match(r"^[A-Z0-9\-\=]+$", ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker format")
    return ticker

def _rebuild_assessment(row: dict) -> Any:
    # BUG FIX: Safely handle null/empty signal_reasons from the database
    raw_reasons = row.get("signal_reasons")
    reasons = []
    if raw_reasons:
        try:
            reasons = json.loads(raw_reasons)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse signal reasons for ID {row.get('id')}")
            
    sig = Signal(
        ticker      = row["ticker"],
        timestamp   = row["created_at"] if isinstance(row["created_at"], datetime)
                      else datetime.fromisoformat(str(row["created_at"])),
        direction   = row["direction"],
        entry_price = row["entry_price"],
        current_rsi = 50.0,
        current_atr = 0.0,
        confidence  = row["confidence_score"],
        reasons     = reasons,
    )
    risk_per_share = abs(row["entry_price"] - row["stop_loss"])
    shares = row["position_size"]
    from backend.engine.risk import Assessment
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

# ── Read-Only Endpoints (Public) ──────────────────────────────────────────────

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

@app.get("/api/stock/{ticker}/quote")
def get_stock_quote(ticker: str) -> Dict[str, Any]:
    ticker = validate_ticker(ticker)
    q = fetch_live_quote(ticker)
    if not q:
        raise HTTPException(status_code=404, detail=f"Could not fetch data for {ticker}")
    q["ticker"] = ticker
    return q

@app.get("/api/stock/{ticker}/history")
def get_stock_history(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    ticker = validate_ticker(ticker)
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
                "volume": int(row["Volume"]) if not pd.isna(row["Volume"]) else 0,
            })
        return {"ticker": ticker, "period": period, "candles": rows}
    except Exception as e:
        log.error("Error fetching historical data: %s", str(e))
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/api/stock/{ticker}/analysis")
def get_stock_analysis(ticker: str) -> Dict[str, Any]:
    ticker = validate_ticker(ticker)
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
        log.error("Error running stock analysis: %s", str(e))
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

@app.get("/api/market/overview")
def get_market_overview() -> Dict[str, Any]:
    quotes = {}
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

@app.get("/api/stock/{ticker}/news")
def get_stock_news(ticker: str) -> List[Dict[str, Any]]:
    ticker = validate_ticker(ticker)
    yf_sym = ticker if ("-" in ticker or "=" in ticker) else f"{ticker}.NS"
    try:
        news_data = yf.Ticker(yf_sym).news
        parsed_news = []
        for n in news_data:
            if isinstance(n, dict):
                content = n.get("content")
                if not isinstance(content, dict):
                    content = n 
                
                title = content.get("title", "") if isinstance(content, dict) else ""
                
                provider = content.get("provider", {}) if isinstance(content, dict) else {}
                publisher = provider.get("displayName", "Unknown") if isinstance(provider, dict) else "Unknown"
                
                if title:
                    parsed_news.append({
                        "title": title,
                        "publisher": publisher,
                        "link": content.get("clickThroughUrl", "") if isinstance(content, dict) else "",
                        "time": content.get("providerPublishTime", 0) if isinstance(content, dict) else 0
                    })
        return parsed_news
    except Exception as e:
        log.error(f"Failed to fetch news for {yf_sym}: {e}")
        return []

@app.get("/api/credentials")
def get_credentials() -> Dict[str, Any]:
    creds = load_credentials()
    return {
        "zerodha_configured": bool(creds.get("ZERODHA_API_KEY") and creds.get("ZERODHA_ACCESS_TOKEN")),
        "telegram_configured": bool(creds.get("TELEGRAM_BOT_TOKEN") and creds.get("TELEGRAM_CHAT_ID")),
        "groq_configured": bool(creds.get("GROQ_API_KEY"))
    }

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
                        title = content.get("title", "") if isinstance(content, dict) else ""
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
        raise HTTPException(status_code=500, detail="An internal server error occurred.")

# ── Protected Endpoints (Requires API Key) ────────────────────────────────────

class DenyRequest(BaseModel):
    note: str = ""

@app.post("/api/signals/{signal_id}/approve", dependencies=[Depends(verify_api_key)])
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

@app.post("/api/signals/{signal_id}/deny", dependencies=[Depends(verify_api_key)])
def deny_signal(signal_id: int, req: DenyRequest):
    signals = db.pending_signals()
    sig = next((s for s in signals if s["id"] == signal_id), None)
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    bridge.deny(signal_id, sig["ticker"], req.note)
    notifier.notify_denial(signal_id, sig["ticker"], req.note)
    return {"success": True}

class CredentialsRequest(BaseModel):
    ZERODHA_API_KEY: str = ""
    ZERODHA_API_SECRET: str = ""
    ZERODHA_ACCESS_TOKEN: str = ""
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    GROQ_API_KEY: str = ""

@app.post("/api/credentials", dependencies=[Depends(verify_api_key)])
def update_credentials(req: CredentialsRequest):
    creds = load_credentials()
    for field, value in req.dict().items():
        if value: 
            creds[field] = value
    save_credentials(creds)
    refresh_credentials()
    return {"success": True}

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
