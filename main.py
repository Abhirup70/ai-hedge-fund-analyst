#!/usr/bin/env python3
"""
AI Investment Research Desk -- command-line entry point
======================================================

Examples
--------
    python main.py AAPL                 # free offline analysis of Apple
    python main.py TSLA --horizon 42    # 42-trading-day forecast horizon
    python main.py NVDA --ai            # flip on AI mode (needs ANTHROPIC_API_KEY)

The flip switch is `--ai`. Without it, everything runs free and offline.
"""

import argparse

from ai_desk.config import Settings
from ai_desk.llm import LLM
from ai_desk.orchestrator import run_desk
from ai_desk.report import render_terminal, save_markdown, save_chart


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AI Investment Research Desk -- a multi-agent stock analyst.")
    parser.add_argument("ticker", nargs="?", default="AAPL",
                        help="stock ticker symbol (default: AAPL)")
    parser.add_argument("--ai", action="store_true",
                        help="enable AI mode (Claude). Requires ANTHROPIC_API_KEY.")
    parser.add_argument("--horizon", type=int,
                        help="forecast horizon in trading days (default 21)")
    parser.add_argument("--paths", type=int,
                        help="number of Monte Carlo paths (default 20000)")
    parser.add_argument("--no-chart", action="store_true",
                        help="skip generating the forecast PNG")
    args = parser.parse_args()

    # Load a local .env file if one exists (so ANTHROPIC_API_KEY can live there).
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    settings = Settings()
    if args.horizon:
        settings.horizon_days = args.horizon
    if args.paths:
        settings.mc_paths = args.paths

    llm = LLM(want_ai=args.ai)
    print(f"\n>>> Mode: {llm.status}")
    if args.ai and not llm.is_enabled:
        print(">>> Tip: set ANTHROPIC_API_KEY (and `pip install anthropic`) to use Claude.\n")

    result = run_desk(args.ticker, settings, llm)

    render_terminal(result)

    md_path = save_markdown(result)
    print(f"📝 Markdown report saved -> {md_path}")

    if not args.no_chart:
        chart = save_chart(result)
        if chart:
            print(f"📈 Forecast chart saved   -> {chart}")

    print("\n[reminder] Educational project — not financial advice.\n")


if __name__ == "__main__":
    main()
