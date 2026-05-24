"""
dashboard.py — NSE Human Approval Dashboard (Streamlit)
=========================================================
The only interface through which a human can APPROVE or DENY trade signals.
The system never executes orders automatically.

Launch:
    streamlit run dashboard.py
    # or via:
    python main.py --mode dashboard

Tabs:
  ⏳ Pending   — Cards per signal with APPROVE / DENY buttons
  📋 History   — Filterable table of all signals
  💼 Positions — Open paper / live trades
  📊 Analytics — Equity curve and win/loss breakdown
"""
from __future__ import annotations

import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backend.core import database as db
from backend.execution.bridge import ExecutionBridge
from backend.core.notification import NotificationService
from backend.engine.risk import Assessment, RiskManager
from backend.core.settings import RISK, SYSTEM, NSE_WATCHLIST
from backend.engine.strategy import Signal
from backend.core import logger as log_mod

log = log_mod.get(__name__)

# ─── Page config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="NSE Signal Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .stApp { background-color: #0d1117; color: #e6edf3; }
  .signal-card { background: #161b22; border-radius: 10px; padding: 18px;
                 margin: 8px 0; border-left: 4px solid #444; }
  .buy-card  { border-left-color: #3fb950 !important; }
  .sell-card { border-left-color: #f85149 !important; }
  div[data-testid="metric-container"] { background:#21262d; border-radius:8px;
                                         padding:12px; }
</style>
""", unsafe_allow_html=True)


# ─── Cached services ──────────────────────────────────────────────────────────

@st.cache_resource
def get_bridge() -> ExecutionBridge:
    db.init()
    return ExecutionBridge()

@st.cache_resource
def get_notifier() -> NotificationService:
    return NotificationService(console_output=False)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _rebuild_assessment(row: dict) -> Assessment:
    """Reconstruct an Assessment from a DB signal row for execution."""
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
    shares         = row["position_size"]
    return Assessment(
        signal        = sig, approved=True,
        stop_loss     = row["stop_loss"],
        take_profit   = row["take_profit"],
        shares        = shares,
        position_value= row["position_value"],
        risk_inr      = round(risk_per_share * shares, 2),
        reward_inr    = round(abs(row["take_profit"] - row["entry_price"]) * shares, 2),
        rr_ratio      = round(abs(row["take_profit"] - row["entry_price"])
                              / max(risk_per_share, 0.001), 2),
        equity        = 0.0,
    )


def _badge(text: str, colour: str) -> str:
    return f'<span style="color:{colour}; font-weight:700;">{text}</span>'


# ─── Sidebar ─────────────────────────────────────────────────────────────────

def sidebar() -> None:
    with st.sidebar:
        st.markdown("## 📈 NSE Signal Dashboard")
        st.markdown("---")

        refresh = st.selectbox("Auto-refresh", ["Off","30s","60s","5min"], index=1)
        if refresh != "Off":
            secs = {"30s":30,"60s":60,"5min":300}[refresh]
            st.markdown(f'<meta http-equiv="refresh" content="{secs}">',
                        unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### ⚙️ Risk Rules")
        st.metric("Stop Loss",      f"{RISK.stop_loss_pct*100:.1f}%")
        st.metric("Take Profit",    f"{RISK.take_profit_pct*100:.1f}%")
        st.metric("Risk / Trade",   f"{RISK.max_risk_per_trade_pct*100:.1f}% of equity")
        st.metric("Max Positions",  str(RISK.max_open_positions))
        st.metric("Min Confidence", f"{RISK.min_signal_confidence}/100")
        st.metric("Min R:R",        "1:2.0")
        st.markdown("---")
        st.markdown("### 📋 Watchlist")
        st.text("\n".join(NSE_WATCHLIST))
        st.markdown("---")
        st.warning("⚠️ Orders execute ONLY after you click **APPROVE**.")
        st.caption(f"NSE System | {datetime.utcnow().strftime('%H:%M UTC')}")


# ─── Pending signals tab ─────────────────────────────────────────────────────

def tab_pending() -> None:
    pending = db.pending_signals()
    if not pending:
        st.info("✅ No pending signals. The scanner will alert you when opportunities arise.")
        return

    st.markdown(f"### {len(pending)} Signal(s) Awaiting Your Decision")
    bridge   = get_bridge()
    notifier = get_notifier()

    for sig in pending:
        sid       = sig["id"]
        ticker    = sig["ticker"]
        direction = sig["direction"]
        entry     = sig["entry_price"]
        sl        = sig["stop_loss"]
        tp        = sig["take_profit"]
        sl_pct    = abs(entry - sl) / entry * 100
        tp_pct    = abs(tp - entry) / entry * 100
        rr        = tp_pct / sl_pct if sl_pct else 0
        clr       = "#3fb950" if direction == "BUY" else "#f85149"
        emoji     = "🟢" if direction == "BUY" else "🔴"
        reasons   = json.loads(sig.get("signal_reasons", "[]"))
        created   = str(sig["created_at"])[:16]

        st.markdown(f'<div class="signal-card {"buy-card" if direction=="BUY" else "sell-card"}">',
                    unsafe_allow_html=True)

        # Header
        hc1, hc2, hc3 = st.columns([3, 2, 2])
        with hc1:
            st.markdown(f'<h3 style="color:{clr}">{emoji} {ticker}</h3>', unsafe_allow_html=True)
            st.caption(f"Signal #{sid} · Generated {created} UTC")
        with hc2:
            st.metric("Direction", direction)
        with hc3:
            st.metric("Confidence", f"{sig['confidence_score']}/100")

        st.markdown("---")

        # Price metrics
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Entry Price",   f"₹{entry:,.2f}")
        c2.metric("Stop Loss",     f"₹{sl:,.2f}", delta=f"-{sl_pct:.1f}%",  delta_color="inverse")
        c3.metric("Take Profit",   f"₹{tp:,.2f}", delta=f"+{tp_pct:.1f}%")
        c4.metric("R:R Ratio",     f"1:{rr:.1f}")
        c5.metric("Position ₹",   f"₹{sig['position_value']:,.0f}")

        # Position metrics
        risk_inr   = abs(entry - sl) * sig["position_size"]
        reward_inr = abs(tp - entry) * sig["position_size"]
        d1, d2, d3 = st.columns(3)
        d1.metric("Shares",       str(sig["position_size"]))
        d2.metric("Max Risk ₹",  f"₹{risk_inr:,.0f}")
        d3.metric("Max Reward ₹",f"₹{reward_inr:,.0f}")

        with st.expander("📋 Full Signal Analysis"):
            for r in reasons:
                st.markdown(f"- {r}")

        st.markdown("")

        # Approve / Deny controls
        col_ap, col_dn, col_nt = st.columns([1, 1, 2])
        with col_ap:
            if st.button(f"✅  APPROVE  #{sid}", key=f"ap_{sid}",
                         type="primary", use_container_width=True):
                with st.spinner(f"Submitting order for {ticker}…"):
                    try:
                        a      = _rebuild_assessment(sig)
                        result = bridge.execute(sid, a)
                        if result.success:
                            notifier.notify_execution(
                                ticker, direction, sig["position_size"],
                                entry, result.order_id, sid)
                            st.success(f"✅ Order placed! ID: `{result.order_id}`")
                            log.info("Dashboard: Signal #%d APPROVED by operator", sid)
                        else:
                            st.error(f"❌ Order failed: {result.error}")
                    except Exception as exc:
                        st.error(f"Error: {exc}")
                st.rerun()

        with col_dn:
            if st.button(f"🚫  DENY  #{sid}", key=f"dn_{sid}",
                         use_container_width=True):
                st.session_state[f"deny_{sid}"] = True

        if st.session_state.get(f"deny_{sid}"):
            with col_nt:
                note = st.text_input("Reason (optional):", key=f"note_{sid}",
                                     placeholder="e.g. Earnings risk, sector weak…")
            cc, cx = st.columns(2)
            with cc:
                if st.button(f"Confirm Deny #{sid}", key=f"cfd_{sid}"):
                    bridge.deny(sid, ticker, note)
                    notifier.notify_denial(sid, ticker, note)
                    st.session_state.pop(f"deny_{sid}", None)
                    log.info("Dashboard: Signal #%d DENIED by operator", sid)
                    st.rerun()
            with cx:
                if st.button(f"Cancel #{sid}", key=f"can_{sid}"):
                    st.session_state.pop(f"deny_{sid}", None)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("---")


# ─── History tab ─────────────────────────────────────────────────────────────

def tab_history() -> None:
    signals = db.recent_signals(200)
    if not signals:
        st.info("No signals yet. Run the scanner to generate signals.")
        return

    df = pd.DataFrame(signals)

    f1, f2, f3 = st.columns(3)
    statuses = st.multiselect("Status", ["PENDING","APPROVED","DENIED","EXECUTED"],
                               default=["PENDING","APPROVED","DENIED","EXECUTED"],
                               key="hist_status")
    directions = st.multiselect("Direction", ["BUY","SELL"], default=["BUY","SELL"],
                                 key="hist_dir")
    tickers_avail = sorted(df["ticker"].unique().tolist())
    sel_tickers   = st.multiselect("Ticker", tickers_avail, default=[], key="hist_tick")

    mask = df["status"].isin(statuses) & df["direction"].isin(directions)
    if sel_tickers:
        mask &= df["ticker"].isin(sel_tickers)
    df = df[mask].copy()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", len(df))
    m2.metric("BUY",  len(df[df["direction"]=="BUY"]))
    m3.metric("SELL", len(df[df["direction"]=="SELL"]))
    m4.metric("Executed", len(df[df["status"]=="EXECUTED"]))

    cols = ["id","created_at","ticker","direction","entry_price",
            "stop_loss","take_profit","position_size","confidence_score","status"]
    st.dataframe(
        df[[c for c in cols if c in df.columns]].rename(columns={
            "id":"#","created_at":"Time","ticker":"Ticker","direction":"Dir",
            "entry_price":"Entry ₹","stop_loss":"SL ₹","take_profit":"TP ₹",
            "position_size":"Shares","confidence_score":"Score","status":"Status",
        }),
        use_container_width=True, hide_index=True,
        column_config={
            "Entry ₹": st.column_config.NumberColumn(format="₹%.2f"),
            "SL ₹":    st.column_config.NumberColumn(format="₹%.2f"),
            "TP ₹":    st.column_config.NumberColumn(format="₹%.2f"),
            "Score":   st.column_config.ProgressColumn(min_value=0, max_value=100,
                                                        format="%d"),
        },
    )


# ─── Positions tab ───────────────────────────────────────────────────────────

def tab_positions() -> None:
    trades = db.open_trades()
    if not trades:
        st.info("No open positions. Approved signals will appear here after execution.")
        return

    st.markdown(f"### {len(trades)} Open Position(s)")
    df = pd.DataFrame(trades)
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.info("ℹ️ Paper orders are tracked here. Zerodha bracket orders are managed on the broker side.", icon="ℹ️")


# ─── Analytics tab ───────────────────────────────────────────────────────────

def tab_analytics() -> None:
    signals = db.recent_signals(500)
    if len(signals) < 2:
        st.info("Run more scans to see analytics.")
        return

    df = pd.DataFrame(signals)
    df["created_at"] = pd.to_datetime(df["created_at"])

    # Signal direction pie
    dir_counts = df["direction"].value_counts()
    col1, col2 = st.columns(2)
    with col1:
        fig_pie = go.Figure(data=[go.Pie(
            labels=dir_counts.index, values=dir_counts.values,
            marker_colors=["#3fb950","#f85149","#8b949e"],
            hole=0.4,
        )])
        fig_pie.update_layout(title="Signal Direction Mix",
                              paper_bgcolor="#0d1117", font_color="#e6edf3")
        st.plotly_chart(fig_pie, use_container_width=True)

    # Confidence score histogram
    with col2:
        fig_hist = go.Figure(data=[go.Histogram(
            x=df["confidence_score"], nbinsx=10,
            marker_color="#1f6feb",
        )])
        fig_hist.update_layout(title="Confidence Score Distribution",
                               xaxis_title="Score", yaxis_title="Count",
                               paper_bgcolor="#0d1117", font_color="#e6edf3",
                               plot_bgcolor="#161b22")
        st.plotly_chart(fig_hist, use_container_width=True)

    # Timeline
    df_day = df.groupby(df["created_at"].dt.date).size().reset_index(name="count")
    fig_tl = go.Figure(data=[go.Bar(
        x=df_day["created_at"], y=df_day["count"],
        marker_color="#1f6feb",
    )])
    fig_tl.update_layout(title="Signals Per Day", xaxis_title="Date",
                          yaxis_title="Count", paper_bgcolor="#0d1117",
                          font_color="#e6edf3", plot_bgcolor="#161b22")
    st.plotly_chart(fig_tl, use_container_width=True)

    # Status breakdown
    status_counts = df["status"].value_counts()
    fig_st = go.Figure(data=[go.Bar(
        x=status_counts.index, y=status_counts.values,
        marker_color=["#f0a500","#3fb950","#f85149","#58a6ff"][:len(status_counts)],
    )])
    fig_st.update_layout(title="Signal Status Breakdown",
                          paper_bgcolor="#0d1117", font_color="#e6edf3",
                          plot_bgcolor="#161b22")
    st.plotly_chart(fig_st, use_container_width=True)


# ─── Main app ─────────────────────────────────────────────────────────────────

def main() -> None:
    db.init()
    sidebar()

    st.title("📈 NSE Semi-Autonomous Signal Dashboard")
    st.caption(
        "All signals require **manual human approval** before execution. "
        "The system **never trades automatically**. Paper trading mode by default."
    )

    # KPI row
    all_sigs = db.recent_signals(100)
    pending  = sum(1 for s in all_sigs if s["status"] == "PENDING")
    executed = sum(1 for s in all_sigs if s["status"] == "EXECUTED")
    open_pos = len(db.open_trades())

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("⏳ Pending Review", pending)
    k2.metric("✅ Executed (recent)", executed)
    k3.metric("📂 Open Positions", open_pos)
    k4.metric("🔍 Watchlist", len(NSE_WATCHLIST))
    st.markdown("---")

    t1, t2, t3, t4 = st.tabs([
        f"⏳ Pending ({pending})",
        "📋 Signal History",
        "💼 Open Positions",
        "📊 Analytics",
    ])
    with t1: tab_pending()
    with t2: tab_history()
    with t3: tab_positions()
    with t4: tab_analytics()


if __name__ == "__main__":
    main()
