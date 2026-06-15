"""
orchestrator.py  --  runs the whole desk
=========================================

This is the conductor. It walks through the research pipeline in order and
returns one tidy `DeskResult` that the report layer turns into output:

    data -> indicators -> Monte Carlo -> analysts -> (debate) -> risk -> decision -> backtest
"""

from __future__ import annotations

from dataclasses import dataclass

from .data import MarketData, get_market_data, compute_indicators
from .physics import Forecast, run_monte_carlo
from .agents import (AgentView, FinalDecision, RiskManager, PortfolioManager,
                     analyst_team)
from .backtest import BacktestResult, run_backtest


@dataclass
class DeskResult:
    md: MarketData
    indicators: dict
    forecast: Forecast
    views: list[AgentView]
    risk: AgentView
    decision: FinalDecision
    backtest: BacktestResult
    ai_mode: bool


def run_desk(ticker: str, settings, llm, log=print) -> DeskResult:
    log(f"[1/6] Fetching market data for {ticker.upper()} ...")
    md = get_market_data(ticker, settings)
    log(f"      source: {md.source} | price: {md.current_price:,.2f}")

    ind = compute_indicators(md.prices)

    log("[2/6] Running Monte Carlo physics engine "
        f"({settings.mc_paths:,} simulated futures) ...")
    fc = run_monte_carlo(md.prices, settings)

    ctx = {"md": md, "indicators": ind, "forecast": fc, "settings": settings}

    log("[3/6] Analysts forming independent opinions ...")
    team = analyst_team()
    views = [a.analyze(ctx, llm) for a in team]

    # Debate rounds only happen in AI mode (offline agents are deterministic,
    # so re-running them would not change anything).
    if llm.is_enabled and settings.debate_rounds > 0:
        for r in range(settings.debate_rounds):
            log(f"      debate round {r + 1}: analysts critique each other ...")
            ctx["peer_views"] = "\n".join(
                f"- {v.agent}: {v.signal} -- "
                f"{v.rationale[0] if v.rationale else 'no comment'}" for v in views)
            views = [a.analyze(ctx, llm) for a in team]
        ctx.pop("peer_views", None)

    log("[4/6] Risk Manager reviewing (hard veto rules) ...")
    risk = RiskManager().analyze(ctx, llm)

    log("[5/6] Portfolio Manager making the final call ...")
    decision = PortfolioManager().decide(ctx, views, risk, llm)

    log("[6/6] Backtesting the signal against real history ...")
    bt = run_backtest(md.prices, settings)

    return DeskResult(md, ind, fc, views, risk, decision, bt, llm.is_enabled)
