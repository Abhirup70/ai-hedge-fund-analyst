"""
data.py
=======
Fetches everything the desk needs about a stock:
  * daily closing prices (price history)
  * fundamentals (P/E, margins, growth, ...)
  * recent news headlines

It tries to pull REAL data from Yahoo Finance (free, no key). If the network
is down or yfinance is not installed, it falls back to a realistic SYNTHETIC
stock simulated with the same Brownian-motion math the physics engine uses --
so the project ALWAYS runs, anywhere, with zero dependencies on the outside
world.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class MarketData:
    """A tidy container for all data about one stock."""

    ticker: str
    prices: pd.Series                 # daily closing prices, indexed by date
    current_price: float
    fundamentals: dict                # P/E, margins, growth, etc.
    news: list[str] = field(default_factory=list)
    source: str = "synthetic"         # "yahoo" or "synthetic"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def get_market_data(ticker: str, settings) -> MarketData:
    """Return MarketData for `ticker`, real if possible, synthetic otherwise."""
    try:
        return _fetch_from_yahoo(ticker, settings)
    except Exception as exc:  # network down, bad ticker, yfinance missing, etc.
        print(f"  (!) Live data unavailable ({type(exc).__name__}); "
              f"using a realistic synthetic stock instead.")
        return _make_synthetic(ticker, settings)


# ---------------------------------------------------------------------------
# Real data via Yahoo Finance
# ---------------------------------------------------------------------------
def _fetch_from_yahoo(ticker: str, settings) -> MarketData:
    import yfinance as yf  # imported lazily so offline mode needs no install

    tk = yf.Ticker(ticker)
    hist = tk.history(period=f"{settings.history_days}d", auto_adjust=True)
    if hist is None or hist.empty:
        raise ValueError(f"No price history returned for '{ticker}'")

    prices = hist["Close"].dropna()
    if len(prices) < 60:
        raise ValueError("Not enough price history to analyse")

    # Fundamentals -- .info can be flaky, so guard each field.
    info = {}
    try:
        info = tk.info or {}
    except Exception:
        info = {}

    fundamentals = {
        "name": info.get("shortName", ticker),
        "sector": info.get("sector", "Unknown"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "profit_margin": info.get("profitMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "debt_to_equity": info.get("debtToEquity"),
        "market_cap": info.get("marketCap"),
    }

    # Recent news headlines (optional).
    news: list[str] = []
    try:
        for item in (tk.news or [])[:8]:
            title = item.get("title") or item.get("content", {}).get("title")
            if title:
                news.append(title)
    except Exception:
        news = []

    return MarketData(
        ticker=ticker.upper(),
        prices=prices,
        current_price=float(prices.iloc[-1]),
        fundamentals=fundamentals,
        news=news,
        source="yahoo",
    )


# ---------------------------------------------------------------------------
# Synthetic fallback -- a believable stock generated with Geometric Brownian
# Motion (the same physics used by the Monte Carlo engine).
# ---------------------------------------------------------------------------
def _make_synthetic(ticker: str, settings) -> MarketData:
    # Seed off the ticker so the same symbol always yields the same fake stock.
    rng = np.random.default_rng(abs(hash(ticker)) % (2**32))

    n = settings.history_days
    start_price = rng.uniform(40, 400)
    mu = rng.uniform(-0.0003, 0.0009)     # daily drift
    sigma = rng.uniform(0.012, 0.035)     # daily volatility

    # GBM: each day's log-return = (mu - 0.5*sigma^2) + sigma * Z
    shocks = (mu - 0.5 * sigma**2) + sigma * rng.standard_normal(n)
    path = start_price * np.exp(np.cumsum(shocks))

    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=n)
    prices = pd.Series(path, index=dates, name="Close")

    fundamentals = {
        "name": f"{ticker.upper()} (Synthetic Corp)",
        "sector": "Simulated",
        "trailing_pe": float(rng.uniform(8, 45)),
        "forward_pe": float(rng.uniform(8, 40)),
        "profit_margin": float(rng.uniform(-0.05, 0.30)),
        "revenue_growth": float(rng.uniform(-0.10, 0.35)),
        "debt_to_equity": float(rng.uniform(10, 180)),
        "market_cap": float(rng.uniform(1e9, 2e12)),
    }

    return MarketData(
        ticker=ticker.upper(),
        prices=prices,
        current_price=float(prices.iloc[-1]),
        fundamentals=fundamentals,
        news=[],  # no synthetic headlines; sentiment agent will use price action
        source="synthetic",
    )


# ---------------------------------------------------------------------------
# Technical indicators -- classic signals computed from the price series.
# Each returns plain numbers so both the rule-based agents and the LLM agents
# can reason over them.
# ---------------------------------------------------------------------------
def compute_indicators(prices: pd.Series) -> dict:
    """Compute moving averages, RSI, momentum and volatility."""
    p = prices.dropna()
    close = float(p.iloc[-1])

    sma20 = float(p.rolling(20).mean().iloc[-1])
    sma50 = float(p.rolling(50).mean().iloc[-1])

    # 1-month (~21 trading day) price momentum
    momentum = float(p.iloc[-1] / p.iloc[-21] - 1) if len(p) > 21 else 0.0

    # Annualised volatility from daily log returns (252 trading days/year)
    log_ret = np.log(p / p.shift(1)).dropna()
    annual_vol = float(log_ret.std() * np.sqrt(252))

    # 52-week range position (0 = at low, 1 = at high)
    window = p.tail(252)
    lo, hi = float(window.min()), float(window.max())
    range_pos = (close - lo) / (hi - lo) if hi > lo else 0.5

    return {
        "close": close,
        "sma20": sma20,
        "sma50": sma50,
        "trend_up": sma20 > sma50 and close > sma50,
        "rsi": _rsi(p),
        "momentum_1m": momentum,
        "annual_vol": annual_vol,
        "range_pos": range_pos,
    }


def _rsi(prices: pd.Series, period: int = 14) -> float:
    """Relative Strength Index (Wilder). 0-100; <30 oversold, >70 overbought."""
    delta = prices.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else 50.0
