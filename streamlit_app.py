"""
streamlit_app.py  --  the web UI for the AI Investment Research Desk
===================================================================

A clickable dashboard wrapped around the same `ai_desk` engine used by the CLI.
Nothing about the analysis logic changes -- this file is purely presentation.

Run it:
    .venv/bin/streamlit run streamlit_app.py

Then open the URL it prints (default http://localhost:8501).

This file is named `streamlit_app.py` on purpose: that is the entry point
Streamlit Community Cloud looks for, so the app can be deployed to a free public
URL later (a great link to drop on LinkedIn).
"""

from __future__ import annotations

import os

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from ai_desk.config import Settings
from ai_desk.llm import LLM
from ai_desk.orchestrator import run_desk

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Investment Research Desk",
    page_icon="🏦",
    layout="wide",
)

SIGNAL_STYLE = {
    "BUY": ("🟢", "#16a34a"),
    "HOLD": ("🟡", "#ca8a04"),
    "SELL": ("🔴", "#dc2626"),
}


# ---------------------------------------------------------------------------
# Interactive Monte Carlo fan chart (Plotly)
# ---------------------------------------------------------------------------
def fan_chart(result) -> go.Figure:
    md, fc = result.md, result.forecast

    hist = md.prices.tail(120)
    hist_x = list(range(-len(hist) + 1, 1))

    paths = fc.paths
    fwd_x = list(range(0, fc.horizon_days + 1))
    p10 = np.percentile(paths, 10, axis=0)
    p25 = np.percentile(paths, 25, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p75 = np.percentile(paths, 75, axis=0)
    p90 = np.percentile(paths, 90, axis=0)

    fig = go.Figure()

    # 10-90% band
    fig.add_trace(go.Scatter(
        x=fwd_x + fwd_x[::-1], y=list(p90) + list(p10[::-1]),
        fill="toself", fillcolor="rgba(255,127,14,0.15)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", name="10–90% range"))

    # 25-75% band
    fig.add_trace(go.Scatter(
        x=fwd_x + fwd_x[::-1], y=list(p75) + list(p25[::-1]),
        fill="toself", fillcolor="rgba(255,127,14,0.30)",
        line=dict(color="rgba(0,0,0,0)"), hoverinfo="skip", name="25–75% range"))

    # History + median forecast
    fig.add_trace(go.Scatter(x=hist_x, y=hist.to_numpy(), name="History",
                             line=dict(color="#2563eb", width=2)))
    fig.add_trace(go.Scatter(x=fwd_x, y=p50, name="Median forecast",
                             line=dict(color="#dc2626", width=2, dash="dash")))

    fig.add_vline(x=0, line_width=1, line_dash="dot", line_color="gray")
    fig.update_layout(
        title=f"{md.ticker} — Monte Carlo {fc.horizon_days}-day forecast "
              f"({len(paths):,} simulated futures)",
        xaxis_title="Trading days (0 = today)",
        yaxis_title="Price",
        height=460, margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar -- controls
# ---------------------------------------------------------------------------
st.sidebar.title("🏦 Research Desk")
st.sidebar.caption("Multi-agent AI stock analyst")

ticker = st.sidebar.text_input("Ticker symbol", value="AAPL").strip().upper()
horizon = st.sidebar.slider("Forecast horizon (trading days)", 5, 90, 21)
paths = st.sidebar.select_slider(
    "Monte Carlo paths", options=[5_000, 10_000, 20_000, 50_000], value=20_000)

st.sidebar.divider()
ai_mode = st.sidebar.toggle("🤖 AI mode (Claude)", value=False,
                            help="Off = free offline rule-based agents. "
                                 "On = real Claude reasoning + debate.")
api_key = ""
if ai_mode:
    api_key = st.sidebar.text_input(
        "Anthropic API key", type="password",
        help="Used only for this session, never stored or logged.")
    if not api_key:
        st.sidebar.warning("Enter a key, or it falls back to free offline mode.")

run = st.sidebar.button("🚀 Run analysis", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.caption("⚠️ Educational project — not financial advice.")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("🏦 AI Investment Research Desk")
st.markdown(
    "A team of specialist **AI agents** debate a stock, a **risk manager** can "
    "veto, and a **Monte Carlo physics engine** forecasts the odds — then it "
    "**backtests its own calls** against real market history."
)

if not run:
    st.info("👈 Pick a ticker and click **Run analysis** to begin. "
            "Try `AAPL`, `TSLA`, `NVDA`, `MSFT`…")
    st.stop()


# ---------------------------------------------------------------------------
# Run the desk
# ---------------------------------------------------------------------------
if api_key:
    os.environ["ANTHROPIC_API_KEY"] = api_key

settings = Settings()
settings.horizon_days = horizon
settings.mc_paths = paths

llm = LLM(want_ai=ai_mode)

with st.status(f"Running the desk on {ticker}…", expanded=True) as status:
    result = run_desk(ticker, settings, llm, log=lambda m: status.write(m))
    status.update(label=f"Analysis complete for {ticker}", state="complete")

d = result.decision
fc = result.forecast
md = result.md
emoji, color = SIGNAL_STYLE.get(d.signal, ("", "#333"))
mode_label = "🤖 AI mode (Claude)" if result.ai_mode else "🆓 Offline mode (rule-based)"

st.caption(f"**{md.fundamentals.get('name', md.ticker)}** · data: {md.source} · {mode_label}")

# --- Verdict banner ---
st.markdown(
    f"""
    <div style="background:{color}1a;border:2px solid {color};border-radius:12px;
                padding:18px 24px;margin:6px 0 18px 0;">
      <span style="font-size:34px;font-weight:800;color:{color};">
        {emoji} {d.signal}
      </span>
      <span style="font-size:18px;color:#444;margin-left:18px;">
        confidence <b>{d.confidence*100:.0f}%</b> &nbsp;·&nbsp;
        suggested position <b>{d.position_size_pct:.1f}%</b>
      </span>
    </div>
    """,
    unsafe_allow_html=True,
)

# --- Key metrics ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Probability of profit", f"{fc.prob_profit*100:.0f}%")
c2.metric(f"Expected return ({fc.horizon_days}d)", f"{fc.expected_return*100:+.1f}%")
c3.metric("5% Value-at-Risk", f"-{fc.var*100:.1f}%")
c4.metric("Annualised volatility", f"{fc.annual_vol*100:.0f}%")

# --- Chart + thesis ---
left, right = st.columns([2, 1])
with left:
    st.plotly_chart(fan_chart(result), use_container_width=True)
with right:
    st.subheader("💡 Thesis")
    st.write(d.thesis)

# --- Agent opinions ---
st.subheader("👥 Analyst team")
cols = st.columns(len(result.views))
for col, v in zip(cols, result.views):
    e, c = SIGNAL_STYLE.get(v.signal, ("", "#333"))
    with col:
        st.markdown(f"**{v.agent}**")
        st.markdown(f"<span style='font-size:22px;color:{c};font-weight:700;'>"
                    f"{e} {v.signal}</span>  ·  {v.confidence*100:.0f}%",
                    unsafe_allow_html=True)
        for r in v.rationale[:3]:
            st.caption(f"• {r}")

rv = result.risk
with st.container(border=True):
    st.markdown(f"🛡️ **Risk Manager** — "
                f"{'🔴 **VETO**' if rv.veto else '🟢 OK'}")
    st.caption(" ".join(rv.rationale[:3]))

# --- Backtest ---
st.subheader("📊 Backtest / calibration")
bt = result.backtest
if bt.hit_rate is not None:
    b1, b2, b3 = st.columns(3)
    b1.metric("BUY-signal hit-rate", f"{bt.hit_rate*100:.0f}%",
              help=f"{bt.n_buy_signals} of {bt.n_windows} historical windows")
    b2.metric("Avg return after BUY", f"{bt.avg_return_buy*100:+.1f}%",
              delta=f"{(bt.avg_return_buy - bt.avg_return_market)*100:+.1f}% vs market")
    b3.metric("Strategy vs buy-and-hold",
              f"{bt.strategy_return*100:+.1f}%",
              delta=f"{(bt.strategy_return - bt.buyhold_return)*100:+.1f}% vs hold")
else:
    st.write(" ".join(bt.notes))

st.caption("Backtest uses only data available at each point in time (no look-ahead bias).")
