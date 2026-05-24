"""database.py — SQLite persistence for signals and trades."""
from __future__ import annotations
import os
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Generator, Optional

from sqlalchemy import (Column, DateTime, Float, Integer, MetaData,
                        String, Table, Text, create_engine)
from sqlalchemy.engine import Connection, Engine
from backend.core import logger as log_mod

log = log_mod.get(__name__)
_engine: Optional[Engine] = None

def get_engine(db_path: str = "nse_signals.db") -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
    return _engine

@contextmanager
def conn(db_path: str = "nse_signals.db") -> Generator[Connection, None, None]:
    with get_engine(db_path).begin() as c:
        yield c

metadata = MetaData()

signals_tbl = Table("signals", metadata,
    Column("id",               Integer, primary_key=True, autoincrement=True),
    Column("created_at",       DateTime, default=datetime.utcnow),
    Column("ticker",           String(20)),
    Column("direction",        String(4)),
    Column("entry_price",      Float),
    Column("stop_loss",        Float),
    Column("take_profit",      Float),
    Column("position_size",    Integer),
    Column("position_value",   Float),
    Column("confidence_score", Integer),
    Column("signal_reasons",   Text),
    Column("status",           String(12), default="PENDING"),
    Column("reviewed_at",      DateTime, nullable=True),
    Column("reviewer_note",    Text, nullable=True),
)

trades_tbl = Table("trades", metadata,
    Column("id",              Integer, primary_key=True, autoincrement=True),
    Column("signal_id",       Integer),
    Column("ticker",          String(20)),
    Column("direction",       String(4)),
    Column("entry_price",     Float),
    Column("exit_price",      Float, nullable=True),
    Column("shares",          Integer),
    Column("entry_time",      DateTime),
    Column("exit_time",       DateTime, nullable=True),
    Column("pnl_inr",         Float, nullable=True),
    Column("pnl_pct",         Float, nullable=True),
    Column("exit_reason",     String(20), nullable=True),
    Column("order_id",        String(60), nullable=True),
    Column("status",          String(10), default="OPEN"),
)

def init(db_path: str = "nse_signals.db") -> None:
    metadata.create_all(get_engine(db_path))
    log.info("Database ready at %s", db_path)

def insert_signal(data: dict[str, Any], db_path: str = "nse_signals.db") -> int:
    with conn(db_path) as c:
        r = c.execute(signals_tbl.insert().values(**data))
        sid = r.inserted_primary_key[0]
    log.info("Signal #%d saved → %s %s @ ₹%.2f", sid, data["direction"], data["ticker"], data["entry_price"])
    return sid

def update_signal(sid: int, status: str, note: str = "", db_path: str = "nse_signals.db") -> None:
    with conn(db_path) as c:
        c.execute(signals_tbl.update()
                  .where(signals_tbl.c.id == sid)
                  .values(status=status, reviewed_at=datetime.utcnow(), reviewer_note=note))
    log.info("Signal #%d → %s", sid, status)

def pending_signals(db_path: str = "nse_signals.db") -> list[dict]:
    with conn(db_path) as c:
        rows = c.execute(signals_tbl.select()
                         .where(signals_tbl.c.status == "PENDING")
                         .order_by(signals_tbl.c.created_at.desc())).fetchall()
    return [dict(r._mapping) for r in rows]

def recent_signals(limit: int = 100, db_path: str = "nse_signals.db") -> list[dict]:
    with conn(db_path) as c:
        rows = c.execute(signals_tbl.select()
                         .order_by(signals_tbl.c.created_at.desc())
                         .limit(limit)).fetchall()
    return [dict(r._mapping) for r in rows]

def insert_trade(data: dict[str, Any], db_path: str = "nse_signals.db") -> int:
    with conn(db_path) as c:
        r = c.execute(trades_tbl.insert().values(**data))
        return r.inserted_primary_key[0]

def open_trades(db_path: str = "nse_signals.db") -> list[dict]:
    with conn(db_path) as c:
        rows = c.execute(trades_tbl.select().where(trades_tbl.c.status == "OPEN")).fetchall()
    return [dict(r._mapping) for r in rows]
