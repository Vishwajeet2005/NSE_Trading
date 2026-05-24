#!/usr/bin/env bash
echo "Starting NSE Trading System..."
# Start backend
uvicorn api:app --port 8000 &
BACKEND_PID=$!
echo "Backend started (PID $BACKEND_PID) → http://localhost:8000"

# Start scanner in background
python main.py --mode scanner --interval 30 --no-gate &
SCANNER_PID=$!
echo "Scanner started (PID $SCANNER_PID)"

echo ""
echo "NSE Terminal ready!"
echo "  Backend API : http://localhost:8000/docs"
echo "  Dashboard   : run  python main.py --mode dashboard"
echo ""
echo "Press Ctrl+C to stop"
wait $BACKEND_PID
