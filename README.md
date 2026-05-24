# 📈 NSE Trading System & AI Terminal

![NSE Trading Dashboard](https://img.shields.io/badge/Status-Active-success) ![Python](https://img.shields.io/badge/Python-3.12%2B-blue) ![React](https://img.shields.io/badge/React-Vite-61DAFB) ![FastAPI](https://img.shields.io/badge/FastAPI-009688)

🚀 **Live Demo:** [https://nse-trading-system-6117.onrender.com](https://nse-trading-system-6117.onrender.com)

A semi-autonomous, full-stack trading terminal designed for the **National Stock Exchange (NSE) of India**. The system blends rule-based technical analysis with an artificial intelligence engine (Random Forest + NLP Sentiment Analysis) to provide actionable trading signals, automated background scanning, and real-time Telegram alerts.

**Description:** AI trading terminal — Random Forest + NLP sentiment + Telegram alerts for NSE

**Topics:** trading, nse, machine-learning, fastapi, python, india, fintech

---

## ✨ Key Features

- **Semi-Autonomous Scanning:** A background job scheduler scans a custom watchlist of NSE stocks every 30 minutes during market hours.
- **AI-Powered Predictions:** Uses a trained Machine Learning model (Random Forest) trained on 15 years of historical data to predict market movement directions.
- **NLP Sentiment Analysis:** Dynamically fetches the latest news headlines from Yahoo Finance and uses VADER sentiment analysis to adjust trade confidence in real-time.
- **Beautiful Web Terminal:** A sleek, dark-mode React frontend (powered by Vite) that displays interactive candlestick charts, live technical indicators (RSI, ATR, MACD), and recent catalysts.
- **Telegram Integration:** Get instant buy/sell signals delivered straight to your phone via a Telegram bot.
- **Human-in-the-loop Execution:** Zero black boxes. The system proposes trades and waits for your final approval via the terminal dashboard.

---

## 🏗️ Architecture

The system is split into two primary components, served seamlessly via a single unified web service:

1. **Backend (Python / FastAPI):**
   - Handles data ingestion via `yfinance` and `nsepython`.
   - Runs the `APScheduler` background task to continuously scan for signals.
   - Hosts the `/api/ml/predict` endpoint for running the Random Forest classifier and fetching NLP sentiment.
   - Manages a local SQLite database (`nse_signals.db`) for tracking active and pending signals.

2. **Frontend (React.js / Vite):**
   - Built with modern React and Vanilla CSS (Glassmorphism design).
   - Communicates with the FastAPI backend.
   - In production, it is statically built and served directly by the FastAPI web server.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- Node.js 18+

### 1. Setup Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start the background scanner and API
python main.py --mode start
# OR simply run the start script
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

### 2. Setup Frontend
```bash
cd frontend
npm install
npm run dev
```
Navigate to `http://localhost:5173` to access the trading terminal.

---

## ☁️ Deployment (Render.com)

This application is configured for 1-click deployment on Render as a **Single Web Service**.

1. Connect this repository to a new Render Web Service using the **Blueprint** (`render.yaml`).
2. Add the following Environment Variables in the Render Dashboard:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token.
   - `TELEGRAM_CHAT_ID`: Your personal Telegram Chat ID.
3. Render will automatically execute `build.sh` to compile the React frontend and install Python dependencies.
4. The service will spin up on `0.0.0.0:$PORT` and serve both the API and the web interface!

---

## ⚠️ Disclaimer

This software is for **educational and research purposes only**. The AI predictions and technical signals do not constitute financial advice. Always perform your own due diligence and risk management before executing live trades in the stock market.
