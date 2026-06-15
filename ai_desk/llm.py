"""
llm.py  --  the flip switch between OFFLINE and AI mode
======================================================

This thin wrapper is the single place that talks to Claude. Everything else in
the codebase just asks `llm.is_enabled` and calls `llm.ask(...)`; it never
needs to know whether a real model answered or whether we are offline.

OFFLINE mode (default): `is_enabled` is False. The agents fall back to their
own deterministic, rule-based reasoning -- 100% free, no account, no network.

AI mode: set the environment variable ANTHROPIC_API_KEY (or pass --ai with a
key configured) and `is_enabled` becomes True. The agents then ask real Claude
models to reason for them.
"""

from __future__ import annotations

import os


class LLM:
    def __init__(self, want_ai: bool = False):
        self.is_enabled = False
        self.client = None
        self._reason = "offline mode requested"

        if not want_ai:
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._reason = "ANTHROPIC_API_KEY not set -- staying in offline mode"
            return

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
            self.is_enabled = True
            self._reason = "AI mode active (Claude)"
        except ImportError:
            self._reason = "`anthropic` package not installed -- run: pip install anthropic"

    @property
    def status(self) -> str:
        return self._reason

    def ask(self, model: str, system: str, prompt: str, max_tokens: int = 700) -> str:
        """Send a single message to Claude and return the text response.

        Raises if called while offline -- callers must check `is_enabled` first.
        """
        if not self.is_enabled:
            raise RuntimeError("LLM.ask() called while in offline mode")

        resp = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        # Concatenate any text blocks in the response.
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()
