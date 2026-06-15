"""
report.py  --  turn a DeskResult into something beautiful
=========================================================

Three outputs:
  1. A rich, colourful terminal dashboard (great for screenshots / demos).
  2. A saved Markdown report in outputs/ (great to attach on LinkedIn / GitHub).
  3. A Monte Carlo "fan chart" PNG showing the cone of possible futures.
"""

from __future__ import annotations

import os

import numpy as np

SIGNAL_COLOR = {"BUY": "bold green", "SELL": "bold red", "HOLD": "bold yellow"}
SIGNAL_EMOJI = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}


# ---------------------------------------------------------------------------
# 1. Terminal dashboard
# ---------------------------------------------------------------------------
def render_terminal(result) -> None:
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich import box
    except ImportError:
        _render_plain(result)
        return

    console = Console()
    d = result.decision
    fc = result.forecast
    md = result.md

    mode = "🤖 AI mode (Claude)" if result.ai_mode else "🆓 Offline mode (rule-based)"
    color = SIGNAL_COLOR.get(d.signal, "white")

    console.print()
    console.rule(f"[bold cyan]AI Investment Research Desk[/]  ·  {md.fundamentals.get('name', md.ticker)}")
    console.print(f"[dim]Ticker {md.ticker} · data: {md.source} · {mode}[/]\n")

    # Verdict panel
    verdict = (f"[{color}]{SIGNAL_EMOJI.get(d.signal,'')} {d.signal}[/]   "
               f"confidence {d.confidence*100:.0f}%   ·   "
               f"suggested position {d.position_size_pct:.1f}%")
    console.print(Panel(verdict, title="FINAL VERDICT", border_style=color, box=box.HEAVY))

    # Analyst opinions table
    t = Table(title="Analyst Team", box=box.SIMPLE_HEAVY, expand=True)
    t.add_column("Agent", style="cyan", no_wrap=True)
    t.add_column("Call", justify="center")
    t.add_column("Conf", justify="right")
    t.add_column("Reasoning")
    for v in result.views:
        c = SIGNAL_COLOR.get(v.signal, "white")
        t.add_row(v.agent, f"[{c}]{v.signal}[/]", f"{v.confidence*100:.0f}%",
                  " ".join(v.rationale[:2]))
    rv = result.risk
    risk_style = "bold red" if rv.veto else "yellow"
    t.add_row("Risk Manager",
              f"[{risk_style}]{'VETO' if rv.veto else 'OK'}[/]",
              f"{rv.confidence*100:.0f}%",
              " ".join(rv.rationale[:2]))
    console.print(t)

    # Monte Carlo physics panel
    mc = (f"Probability of profit: [bold]{fc.prob_profit*100:.0f}%[/]\n"
          f"Expected return ({fc.horizon_days}d): "
          f"[bold]{fc.expected_return*100:+.1f}%[/]\n"
          f"Expected price: {fc.expected_price:,.2f}  "
          f"(now {md.current_price:,.2f})\n"
          f"Range (10th–90th pct): {fc.percentiles[10]:,.2f} – {fc.percentiles[90]:,.2f}\n"
          f"5% Value-at-Risk: [red]-{fc.var*100:.1f}%[/]   "
          f"Worst-case (CVaR): [red]-{fc.cvar*100:.1f}%[/]\n"
          f"Annualised volatility: {fc.annual_vol*100:.0f}%")
    console.print(Panel(mc, title="🌀 Monte Carlo Physics Engine", border_style="magenta"))

    # Backtest panel
    bt = result.backtest
    if bt.hit_rate is not None:
        bt_text = (f"BUY-signal hit-rate: [bold]{bt.hit_rate*100:.0f}%[/] "
                   f"({bt.n_buy_signals} of {bt.n_windows} windows)\n"
                   f"Avg return after BUY: {bt.avg_return_buy*100:+.1f}%  "
                   f"vs market {bt.avg_return_market*100:+.1f}%\n"
                   f"Strategy vs buy-and-hold: "
                   f"{bt.strategy_return*100:+.1f}% vs {bt.buyhold_return*100:+.1f}%")
    else:
        bt_text = "Not enough BUY signals / history for calibration.\n" + \
                  " ".join(bt.notes)
    console.print(Panel(bt_text, title="📊 Backtest / Calibration", border_style="blue"))

    # Thesis
    console.print(Panel(d.thesis, title="💡 Investment Thesis (Portfolio Manager)",
                        border_style="green"))
    console.print()


def _render_plain(result) -> None:
    """Fallback if `rich` is not installed."""
    d = result.decision
    print("\n=== AI INVESTMENT RESEARCH DESK ===")
    print(f"{result.md.ticker}: {d.signal} (confidence {d.confidence*100:.0f}%, "
          f"position {d.position_size_pct:.1f}%)")
    for v in result.views:
        print(f"  - {v.agent}: {v.signal} ({v.confidence*100:.0f}%)")
    print(f"  - Risk Manager: {'VETO' if result.risk.veto else 'OK'}")
    print(f"\nThesis: {d.thesis}\n")


# ---------------------------------------------------------------------------
# 2. Markdown report
# ---------------------------------------------------------------------------
def save_markdown(result, out_dir: str = "outputs") -> str:
    os.makedirs(out_dir, exist_ok=True)
    d, fc, md, bt = result.decision, result.forecast, result.md, result.backtest
    path = os.path.join(out_dir, f"{md.ticker}_report.md")

    lines = [
        f"# AI Investment Research Desk — {md.fundamentals.get('name', md.ticker)} ({md.ticker})",
        "",
        f"*Mode: {'AI (Claude)' if result.ai_mode else 'Offline (rule-based)'} · "
        f"Data source: {md.source} · Current price: {md.current_price:,.2f}*",
        "",
        f"## 🏁 Final Verdict: **{d.signal}**",
        f"- Confidence: **{d.confidence*100:.0f}%**",
        f"- Suggested position size: **{d.position_size_pct:.1f}%** of portfolio",
        "",
        "## 👥 Analyst Team",
        "| Agent | Call | Confidence | Reasoning |",
        "|---|---|---|---|",
    ]
    for v in result.views:
        lines.append(f"| {v.agent} | {v.signal} | {v.confidence*100:.0f}% | "
                     f"{'; '.join(v.rationale[:3])} |")
    rv = result.risk
    lines.append(f"| Risk Manager | {'VETO' if rv.veto else 'OK'} | "
                 f"{rv.confidence*100:.0f}% | {'; '.join(rv.rationale[:3])} |")

    lines += [
        "",
        "## 🌀 Monte Carlo Physics Engine",
        f"- Probability of profit: **{fc.prob_profit*100:.0f}%**",
        f"- Expected return ({fc.horizon_days} days): **{fc.expected_return*100:+.1f}%**",
        f"- Expected price: {fc.expected_price:,.2f}",
        f"- 10th–90th percentile range: {fc.percentiles[10]:,.2f} – {fc.percentiles[90]:,.2f}",
        f"- 5% Value-at-Risk: **-{fc.var*100:.1f}%**, CVaR: **-{fc.cvar*100:.1f}%**",
        f"- Annualised volatility: {fc.annual_vol*100:.0f}%",
        "",
        "## 📊 Backtest / Calibration",
    ]
    if bt.hit_rate is not None:
        lines += [
            f"- BUY-signal hit-rate: **{bt.hit_rate*100:.0f}%** "
            f"({bt.n_buy_signals}/{bt.n_windows} windows)",
            f"- Avg return after BUY: {bt.avg_return_buy*100:+.1f}% "
            f"(market baseline {bt.avg_return_market*100:+.1f}%)",
            f"- Signal strategy vs buy-and-hold: "
            f"{bt.strategy_return*100:+.1f}% vs {bt.buyhold_return*100:+.1f}%",
        ]
    else:
        lines.append("- " + " ".join(bt.notes))

    lines += ["", "## 💡 Investment Thesis", d.thesis, "",
              "---", "*Generated by the AI Investment Research Desk. "
              "For education only — not financial advice.*"]

    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path


# ---------------------------------------------------------------------------
# 3. Monte Carlo fan chart
# ---------------------------------------------------------------------------
def save_chart(result, out_dir: str = "outputs") -> str | None:
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless backend; no display needed
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    os.makedirs(out_dir, exist_ok=True)
    md, fc = result.md, result.forecast
    path = os.path.join(out_dir, f"{md.ticker}_forecast.png")

    # Recent history (last ~120 trading days) on negative x-axis.
    hist = md.prices.tail(120).to_numpy()
    hist_x = np.arange(-len(hist) + 1, 1)

    # Forward percentile bands from the simulated paths.
    paths = fc.paths  # (n_paths, horizon+1)
    fwd_x = np.arange(0, fc.horizon_days + 1)
    p10 = np.percentile(paths, 10, axis=0)
    p25 = np.percentile(paths, 25, axis=0)
    p50 = np.percentile(paths, 50, axis=0)
    p75 = np.percentile(paths, 75, axis=0)
    p90 = np.percentile(paths, 90, axis=0)

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(hist_x, hist, color="#1f77b4", lw=1.8, label="History")
    ax.fill_between(fwd_x, p10, p90, color="#ff7f0e", alpha=0.18, label="10–90% outcomes")
    ax.fill_between(fwd_x, p25, p75, color="#ff7f0e", alpha=0.32, label="25–75% outcomes")
    ax.plot(fwd_x, p50, color="#d62728", lw=2, ls="--", label="Median forecast")
    ax.axvline(0, color="gray", lw=0.8, ls=":")

    d = result.decision
    ax.set_title(f"{md.ticker} — Monte Carlo {fc.horizon_days}-day forecast  "
                 f"|  Verdict: {d.signal} ({d.confidence*100:.0f}%)",
                 fontsize=13, fontweight="bold")
    ax.set_xlabel("Trading days (0 = today)")
    ax.set_ylabel("Price")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
