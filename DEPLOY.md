# NSE Trading Terminal — Deployment Guide

## Quick Start (Development)

### 1. Backend — Run FastAPI
```bash
# Replace your project's api.py with api_enhanced.py
cp api_enhanced.py api.py

# Install dependencies
pip install -r requirements.txt

# Start the backend
uvicorn api:app --port 8000 --reload
```

### 2. Frontend — React App
```bash
# Create React app
npx create-react-app nse-terminal
cd nse-terminal

# Install dependencies
npm install recharts lucide-react

# Replace src/App.js with NSETradingTerminal.jsx contents
# Set default export as App in src/App.js

# Start dev server
npm start
```

### 3. Production Build
```bash
cd nse-terminal
npm run build
# Serve the build/ folder with nginx or any static host
```

---

## Docker Deployment (Full Stack)

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./nse_signals.db:/app/nse_signals.db
  
  scanner:
    build: .
    command: python main.py --mode scanner --no-gate
    depends_on:
      - backend
    volumes:
      - ./nse_signals.db:/app/nse_signals.db
```

---

## For Real Trading (Zerodha)

1. Edit `settings.py`:
```python
ZERODHA_API_KEY     = "your_api_key"
ZERODHA_API_SECRET  = "your_secret"
ZERODHA_ACCESS_TOKEN = "daily_token"  # Regenerate every morning
```

2. Enable Zerodha in `execution_bridge.py`:
```python
bridge = ExecutionBridge(use_zerodha=True)  # Change use_zerodha to True
```

3. Run scanner + backend:
```bash
python main.py --mode web &
python main.py --mode scanner --interval 30
```

---

## Frontend Environment Variable

In production, set the backend URL:
```js
// At top of NSETradingTerminal.jsx
const BACKEND = process.env.REACT_APP_BACKEND_URL || "http://localhost:8000";
```

---

## Key Features

| Feature | Status |
|---|---|
| 300+ NSE stocks database | ✅ Built-in |
| Persistent bookmarks | ✅ window.storage |
| Live prices (backend) | ✅ via nsepython/yfinance |
| Offline simulation | ✅ GBM engine |
| AI predictions | ✅ Claude API |
| Signal approve/deny | ✅ REST API |
| Technical indicators | ✅ RSI, MACD, EMA, BB |
| Price charts | ✅ Recharts |
| Sector/index filter | ✅ Built-in |
