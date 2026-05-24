#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
#  NSE Trading System — One-Command Setup Script
#  Run:  bash setup.sh
# ─────────────────────────────────────────────────────────────────
set -e

BOLD="\033[1m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"
CYAN="\033[0;36m"; RED="\033[0;31m"; RESET="\033[0m"

info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
success() { echo -e "${GREEN}[OK]${RESET}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }

echo -e "${BOLD}${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║   NSE Semi-Autonomous Trading System  —  Setup       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${RESET}"

# ── 1. Python version check ───────────────────────────────────────
info "Checking Python version…"
PY=$(python --version 2>&1 | grep -oP '\d+\.\d+')
MAJOR=$(echo "$PY" | cut -d. -f1)
MINOR=$(echo "$PY" | cut -d. -f2)
if [ "$MAJOR" -lt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 10 ]; }; then
    error "Python 3.10+ required. Found: $PY"
fi
success "Python $PY ✓"

# ── 2. Virtual environment ────────────────────────────────────────
if [ ! -d ".venv" ]; then
    info "Creating virtual environment in .venv/ …"
    python -m venv .venv
    success "Virtual environment created"
else
    info "Virtual environment already exists (.venv/)"
fi

# Activate
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
success "Virtual environment activated"

# ── 3. Upgrade pip ────────────────────────────────────────────────
info "Upgrading pip…"
python -m pip install --upgrade pip -q
success "pip upgraded"

# ── 4. Install dependencies ───────────────────────────────────────
info "Installing dependencies from requirements.txt…"
pip install -r requirements.txt -q
success "All dependencies installed"

# ── 5. Initialise database ────────────────────────────────────────
info "Initialising SQLite database…"
python main.py --init-db
success "Database ready (nse_signals.db)"

# ── 6. Run test suite ─────────────────────────────────────────────
info "Running test suite…"
if python tests/test_all.py; then
    success "All tests passed"
else
    warn "Some tests failed — check output above"
fi

# ── 7. Done ───────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}Setup complete!${RESET}"
echo ""
echo -e "${BOLD}Next steps:${RESET}"
echo -e "  1. Edit  ${CYAN}settings.py${RESET}  to add credentials (Zerodha, Telegram)"
echo -e "  2. Review watchlist and risk parameters in  ${CYAN}settings.py${RESET}"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" || "$OSTYPE" == "win32" ]]; then
    echo -e "  3. Activate venv:  ${YELLOW}.venv\\Scripts\\activate${RESET}  (Windows)"
else
    echo -e "  3. Activate venv:  ${YELLOW}source .venv/bin/activate${RESET}  (Unix/Mac)"
fi
echo ""
echo -e "${BOLD}Run the system:${RESET}"
echo -e "  ${YELLOW}python main.py${RESET}                         # Full system"
echo -e "  ${YELLOW}python main.py --mode demo${RESET}             # Demo (no market gate)"
echo -e "  ${YELLOW}python main.py --mode backtest --ticker RELIANCE${RESET}"
echo -e "  ${YELLOW}python main.py --mode screen${RESET}           # Indicator screener"
echo -e "  ${YELLOW}python main.py --mode portfolio${RESET}        # P&L tracker"
echo -e "  ${YELLOW}python tests/test_all.py${RESET}               # 91 tests"
echo ""
