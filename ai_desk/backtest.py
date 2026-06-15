"""
backtest.py  --  does the desk's signal actually work?
=====================================================

Talk is cheap. This module replays the desk's technical signal across history
and measures whether it would have made money -- the single most credible thing
you can show: *"my AI's recommendations are calibrated against real returns."*

Method (a simple, honest walk-forward test):
  * Step through history in non-overlapping `horizon`-day windows.
  * At each window start, compute the signal using ONLY data available then
    (no look-ahead -- a classic backtesting mistake we explicitly avoid).
  * Measure the realised forward return of each window.
  * Report the hit-rate of BUY signals and compare a signal-following strategy
    against simple buy-and-hold.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import compute_indicators
from .agents import technical_signal


@dataclass
class BacktestResult:
    n_windows: int
    n_buy_signals: int
    hit_rate: float | None        # % of BUY windows with positive forward return
    avg_return_buy: float | None  # avg forward return after a BUY signal
    avg_return_market: float      # avg forward return across all windows (baseline)
    strategy_return: float        # cumulative return following the signal (long/cash)
    buyhold_return: float         # cumulative buy-and-hold over the same span
    notes: list[str] = field(default_factory=list)


def run_backtest(prices: pd.Series, settings) -> BacktestResult:
    p = prices.dropna().reset_index(drop=True)
    h = settings.horizon_days
    start = 55  # need ~50 days of history for the moving averages

    if len(p) < start + 2 * h:
        return BacktestResult(0, 0, None, None, 0.0, 0.0, 0.0,
                              ["Not enough history for a meaningful backtest."])

    fwd_returns, signals = [], []
    for i in range(start, len(p) - h, h):     # non-overlapping windows, no look-ahead
        ind = compute_indicators(p.iloc[: i + 1])
        sig, _, _ = technical_signal(ind)
        fwd = p.iloc[i + h] / p.iloc[i] - 1.0
        signals.append(sig)
        fwd_returns.append(fwd)

    signals = np.array(signals)
    fwd_returns = np.array(fwd_returns)

    buy_mask = signals == "BUY"
    n_buy = int(buy_mask.sum())

    hit_rate = float((fwd_returns[buy_mask] > 0).mean()) if n_buy else None
    avg_buy = float(fwd_returns[buy_mask].mean()) if n_buy else None
    avg_market = float(fwd_returns.mean())

    # Long-only strategy: take the forward return when BUY, otherwise sit in cash.
    position = np.where(buy_mask, 1.0, 0.0)
    strat_factors = 1.0 + position * fwd_returns
    strategy_return = float(np.prod(strat_factors) - 1.0)

    # Buy-and-hold over the same span.
    buyhold_return = float(p.iloc[start + len(signals) * h] / p.iloc[start] - 1.0) \
        if start + len(signals) * h < len(p) else float(p.iloc[-1] / p.iloc[start] - 1.0)

    notes = []
    if n_buy == 0:
        notes.append("No BUY signals were generated in this period.")

    return BacktestResult(
        n_windows=len(signals),
        n_buy_signals=n_buy,
        hit_rate=hit_rate,
        avg_return_buy=avg_buy,
        avg_return_market=avg_market,
        strategy_return=strategy_return,
        buyhold_return=buyhold_return,
        notes=notes,
    )
