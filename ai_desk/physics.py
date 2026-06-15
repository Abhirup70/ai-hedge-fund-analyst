"""
physics.py  --  the Monte Carlo forecasting engine
==================================================

This is the "physics" heart of the project.

A stock price is modelled as a particle undergoing *Brownian motion* -- the
exact same random-walk physics Einstein used in 1905 to describe pollen grains
jiggling in water. In finance this model is called **Geometric Brownian Motion
(GBM)**:

        dS = mu * S dt  +  sigma * S dW

    where   S      = stock price
            mu     = drift (average return)
            sigma  = volatility (size of random kicks)
            dW     = a Wiener process (the random "kick" each instant)

Fun fact for your write-up: the famous Black-Scholes option-pricing equation
that comes out of this model is mathematically the **heat / diffusion equation**
from physics. Finance and thermodynamics share the same math.

Instead of solving the equation analytically, we *simulate* thousands of
possible futures (Monte Carlo) and read the probabilities straight off the
distribution of outcomes. That gives us:
  * the probability the trade is profitable
  * the expected return
  * Value-at-Risk (VaR) and Conditional VaR -- the size of bad outcomes
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Forecast:
    """Results of the Monte Carlo simulation."""

    horizon_days: int
    paths: np.ndarray            # shape (n_paths, horizon+1): simulated price paths
    expected_price: float
    expected_return: float       # mean return over the horizon
    prob_profit: float           # P(price_end > price_now)
    var: float                   # 5% Value-at-Risk (loss as a positive fraction)
    cvar: float                  # mean loss in the worst 5% of cases
    annual_vol: float
    percentiles: dict            # {10: price, 25: price, 50:..., 75:..., 90:...}


def estimate_parameters(prices: pd.Series) -> tuple[float, float]:
    """Estimate daily drift (mu) and daily volatility (sigma) from history."""
    log_returns = np.log(prices / prices.shift(1)).dropna()
    mu = float(log_returns.mean())
    sigma = float(log_returns.std())
    return mu, sigma


def run_monte_carlo(prices: pd.Series, settings) -> Forecast:
    """Simulate `settings.mc_paths` future price paths via GBM."""
    rng = np.random.default_rng(settings.seed)

    mu, sigma = estimate_parameters(prices)
    s0 = float(prices.iloc[-1])
    h = settings.horizon_days
    n = settings.mc_paths

    # Daily log-return shocks for every path and every day.
    #   shock = (mu - 0.5*sigma^2)  +  sigma * Z        (Z ~ standard normal)
    # The -0.5*sigma^2 term is the Ito correction that keeps the average right.
    z = rng.standard_normal(size=(n, h))
    daily = (mu - 0.5 * sigma**2) + sigma * z

    # Cumulative log-returns -> price paths, prepending the starting price.
    log_paths = np.cumsum(daily, axis=1)
    price_paths = s0 * np.exp(log_paths)
    paths = np.hstack([np.full((n, 1), s0), price_paths])  # (n, h+1)

    end_prices = paths[:, -1]
    returns = end_prices / s0 - 1.0

    expected_return = float(returns.mean())
    prob_profit = float((end_prices > s0).mean())

    # Value-at-Risk: the loss you would NOT exceed with 95% confidence.
    var_return = float(np.quantile(returns, settings.var_confidence))  # e.g. 5th pct
    var = max(0.0, -var_return)
    tail = returns[returns <= var_return]
    cvar = float(-tail.mean()) if tail.size else var

    pcts = {p: float(np.quantile(end_prices, p / 100)) for p in (10, 25, 50, 75, 90)}

    return Forecast(
        horizon_days=h,
        paths=paths,
        expected_price=float(end_prices.mean()),
        expected_return=expected_return,
        prob_profit=prob_profit,
        var=var,
        cvar=cvar,
        annual_vol=float(sigma * np.sqrt(252)),
        percentiles=pcts,
    )
