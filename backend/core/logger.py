"""logger.py — Dual-sink logger (Rich console + rotating file)."""
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional
from rich.logging import RichHandler

_ready = False

def setup(log_file: str = "nse_system.log") -> None:
    global _ready
    if _ready: return
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    # Console
    root.addHandler(RichHandler(level=logging.INFO, rich_tracebacks=True,
                                show_path=False, markup=True,
                                log_time_format="%H:%M:%S"))
    # File
    fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"))
    root.addHandler(fh)
    for lib in ("yfinance", "urllib3", "httpx", "asyncio", "nsepython"):
        logging.getLogger(lib).setLevel(logging.WARNING)
    _ready = True

def get(name: Optional[str] = None) -> logging.Logger:
    setup()
    return logging.getLogger(name or "nse_system")
