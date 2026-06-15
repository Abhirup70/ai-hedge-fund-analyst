"""
config.py
=========
One place for every tunable knob in the system. Keeping configuration
separate from logic is a small habit that senior engineers look for.
"""

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Claude model tiers (only used when AI mode is ON).
# We deliberately use a CHEAP, fast model for the many analyst calls and a
# POWERFUL model only for the single final decision. This "right model for the
# job" pattern keeps cost low -- a real cost-engineering signal for your CV.
# ---------------------------------------------------------------------------
ANALYST_MODEL = "claude-haiku-4-5-20251001"   # fast + cheap, used by analysts
PORTFOLIO_MODEL = "claude-opus-4-8"           # strongest model, final verdict only


@dataclass
class Settings:
    """All numeric parameters for a research run."""

    # --- Forecasting horizon ---
    horizon_days: int = 21          # ~1 trading month look-ahead / holding period
    history_days: int = 400         # how much price history to analyse

    # --- Monte Carlo physics engine ---
    mc_paths: int = 20_000          # number of simulated future price paths
    var_confidence: float = 0.05    # 5% Value-at-Risk (worst-5% outcome)

    # --- Risk manager veto thresholds ---
    risk_max_annual_vol: float = 0.60   # veto a BUY if annualised volatility > 60%
    risk_max_var: float = 0.18          # veto a BUY if 5% VaR loss > 18% over horizon

    # --- Debate ---
    debate_rounds: int = 1          # critique rounds among analysts (AI mode only)

    # --- Reproducibility ---
    seed: int = 42

    # --- Backtest ---
    backtest_points: int = 12       # how many historical dates to test the signal on


# Agent voting weights used by the Portfolio Manager when combining opinions.
# They sum to 1.0. Fundamentals are weighted highest, sentiment lowest.
AGENT_WEIGHTS = {
    "Fundamental Analyst": 0.40,
    "Technical Analyst": 0.35,
    "Sentiment Analyst": 0.25,
}
