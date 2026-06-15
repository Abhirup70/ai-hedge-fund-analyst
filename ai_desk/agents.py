"""
agents.py  --  the research team
================================

Five specialists, each modelled as an "agent" with a single job:

  1. Fundamental Analyst  -- is the business cheap / growing / profitable?
  2. Technical Analyst    -- what is the price chart telling us?
  3. Sentiment Analyst    -- what is the mood in the news / price action?
  4. Risk Manager         -- is this too dangerous? (can VETO a BUY)
  5. Portfolio Manager    -- weighs everyone and makes the final call.

Every agent works in BOTH modes through one shared interface:
  * OFFLINE -> a transparent, deterministic rule (`_analyze_offline`)
  * AI      -> ask a Claude model to reason (`system_prompt` + `user_prompt`)

Design choice worth highlighting on your CV: the Risk Manager's veto is a
HARD-CODED guardrail computed from numbers -- the language model cannot talk
its way past it. Separating "creative reasoning" from "non-negotiable safety
rules" is exactly how production AI systems are built.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .config import AGENT_WEIGHTS, ANALYST_MODEL, PORTFOLIO_MODEL


# ---------------------------------------------------------------------------
# Shared data structures
# ---------------------------------------------------------------------------
@dataclass
class AgentView:
    agent: str
    signal: str                       # "BUY" | "HOLD" | "SELL"
    confidence: float                 # 0.0 - 1.0
    rationale: list[str] = field(default_factory=list)
    veto: bool = False                # only the Risk Manager sets this


@dataclass
class FinalDecision:
    signal: str
    confidence: float
    position_size_pct: float          # suggested % of portfolio to allocate
    thesis: str
    key_points: list[str] = field(default_factory=list)
    risk_vetoed: bool = False


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
_VOTE = {"BUY": 1.0, "HOLD": 0.0, "SELL": -1.0}


def _norm_signal(s) -> str:
    s = str(s or "").upper()
    return s if s in _VOTE else "HOLD"


def _score_to_signal(score: float, band: float = 0.15) -> str:
    if score > band:
        return "BUY"
    if score < -band:
        return "SELL"
    return "HOLD"


def _parse_json(raw: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response."""
    try:
        return json.loads(raw)
    except Exception:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    return {}


_JSON_RULE = (
    'Respond with ONLY a JSON object, no prose, in exactly this shape:\n'
    '{"signal": "BUY" | "HOLD" | "SELL", "confidence": 0.0-1.0, '
    '"rationale": ["short reason", "short reason", "short reason"]}'
)


# ---------------------------------------------------------------------------
# Reusable technical rule (shared by the agent AND the backtester)
# ---------------------------------------------------------------------------
def technical_signal(ind: dict) -> tuple[str, float, list[str]]:
    """Turn technical indicators into a (signal, confidence, reasons) triple."""
    score = 0.0
    reasons = []

    if ind["trend_up"]:
        score += 1
        reasons.append(f"Uptrend: price above 50-day average ({ind['sma50']:.2f}).")
    else:
        score -= 1
        reasons.append("Downtrend: price below its 50-day average.")

    rsi = ind["rsi"]
    if rsi < 30:
        score += 1
        reasons.append(f"RSI {rsi:.0f} -> oversold, bounce likely.")
    elif rsi > 70:
        score -= 1
        reasons.append(f"RSI {rsi:.0f} -> overbought, pullback risk.")
    else:
        reasons.append(f"RSI {rsi:.0f} -> neutral.")

    mom = ind["momentum_1m"]
    if mom > 0.02:
        score += 1
        reasons.append(f"Positive 1-month momentum (+{mom*100:.1f}%).")
    elif mom < -0.02:
        score -= 1
        reasons.append(f"Negative 1-month momentum ({mom*100:.1f}%).")

    signal = _score_to_signal(score, band=0.5)
    confidence = min(0.9, 0.35 + abs(score) / 4)
    return signal, confidence, reasons


# ---------------------------------------------------------------------------
# Base agent
# ---------------------------------------------------------------------------
class Agent:
    name = "Agent"
    role = "generic analyst"
    model = ANALYST_MODEL

    def analyze(self, ctx: dict, llm) -> AgentView:
        if llm.is_enabled:
            try:
                return self._analyze_ai(ctx, llm)
            except Exception as exc:
                view = self._analyze_offline(ctx)
                view.rationale.append(f"(AI call failed: {type(exc).__name__}; used rule-based logic)")
                return view
        return self._analyze_offline(ctx)

    # --- AI path (generic, driven by each agent's prompts) ---
    def _analyze_ai(self, ctx: dict, llm) -> AgentView:
        prompt = self.user_prompt(ctx)
        # During a debate round, show the agent its colleagues' opinions so it
        # can defend or revise its view -- this is the "agents arguing" loop.
        peers = ctx.get("peer_views")
        if peers:
            prompt += ("\n\nYour colleagues currently think:\n" + peers +
                       "\nReconsider and give your (possibly revised) view.")
        raw = llm.ask(
            self.model,
            system=self.system_prompt(),
            prompt=prompt + "\n\n" + _JSON_RULE,
        )
        data = _parse_json(raw)
        return AgentView(
            agent=self.name,
            signal=_norm_signal(data.get("signal")),
            confidence=float(data.get("confidence", 0.5) or 0.5),
            rationale=[str(r) for r in (data.get("rationale") or [])][:4] or [raw[:160]],
        )

    # --- subclasses override these ---
    def system_prompt(self) -> str:
        return f"You are a {self.role} on an investment desk. Be concise and decisive."

    def user_prompt(self, ctx: dict) -> str:
        raise NotImplementedError

    def _analyze_offline(self, ctx: dict) -> AgentView:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# 1. Fundamental Analyst
# ---------------------------------------------------------------------------
class FundamentalAnalyst(Agent):
    name = "Fundamental Analyst"
    role = "fundamental equity analyst focused on valuation, growth and profitability"

    def user_prompt(self, ctx):
        f = ctx["md"].fundamentals
        return (
            f"Company: {f.get('name')} (sector: {f.get('sector')}).\n"
            f"Trailing P/E: {f.get('trailing_pe')}\n"
            f"Forward P/E: {f.get('forward_pe')}\n"
            f"Profit margin: {f.get('profit_margin')}\n"
            f"Revenue growth: {f.get('revenue_growth')}\n"
            f"Debt/Equity: {f.get('debt_to_equity')}\n"
            "Judge whether the business is attractively valued, growing and profitable."
        )

    def _analyze_offline(self, ctx):
        f = ctx["md"].fundamentals
        score = 0.0
        reasons = []

        pe = f.get("trailing_pe") or f.get("forward_pe")
        if pe:
            if pe < 15:
                score += 1; reasons.append(f"Cheap valuation (P/E {pe:.1f}).")
            elif pe > 40:
                score -= 1; reasons.append(f"Expensive valuation (P/E {pe:.1f}).")
            else:
                reasons.append(f"Fair valuation (P/E {pe:.1f}).")
        else:
            reasons.append("Valuation data unavailable.")

        g = f.get("revenue_growth")
        if g is not None:
            if g > 0.10:
                score += 1; reasons.append(f"Strong revenue growth ({g*100:.0f}%).")
            elif g < 0:
                score -= 1; reasons.append(f"Revenue shrinking ({g*100:.0f}%).")

        m = f.get("profit_margin")
        if m is not None:
            if m > 0.15:
                score += 1; reasons.append(f"Healthy margins ({m*100:.0f}%).")
            elif m < 0:
                score -= 1; reasons.append("Unprofitable (negative margin).")

        return AgentView(
            self.name,
            _score_to_signal(score, band=0.5),
            min(0.9, 0.35 + abs(score) / 3),
            reasons,
        )


# ---------------------------------------------------------------------------
# 2. Technical Analyst
# ---------------------------------------------------------------------------
class TechnicalAnalyst(Agent):
    name = "Technical Analyst"
    role = "technical analyst reading price trends, momentum and RSI"

    def user_prompt(self, ctx):
        i = ctx["indicators"]
        return (
            f"Price: {i['close']:.2f}\n"
            f"20-day avg: {i['sma20']:.2f}, 50-day avg: {i['sma50']:.2f}\n"
            f"RSI(14): {i['rsi']:.0f}\n"
            f"1-month momentum: {i['momentum_1m']*100:.1f}%\n"
            f"52-week range position: {i['range_pos']*100:.0f}%\n"
            "Read the chart and give a trading signal."
        )

    def _analyze_offline(self, ctx):
        signal, conf, reasons = technical_signal(ctx["indicators"])
        return AgentView(self.name, signal, conf, reasons)


# ---------------------------------------------------------------------------
# 3. Sentiment Analyst
# ---------------------------------------------------------------------------
_POS_WORDS = {"beat", "beats", "surge", "soar", "record", "growth", "upgrade",
              "bullish", "profit", "strong", "wins", "rally", "gains", "boost"}
_NEG_WORDS = {"miss", "misses", "plunge", "fall", "drop", "lawsuit", "downgrade",
              "bearish", "loss", "weak", "cuts", "slump", "fraud", "probe", "warning"}


class SentimentAnalyst(Agent):
    name = "Sentiment Analyst"
    role = "market sentiment analyst gauging mood from news headlines and price action"

    def user_prompt(self, ctx):
        news = ctx["md"].news
        headlines = "\n".join(f"- {h}" for h in news) if news else "(no recent headlines available)"
        return (
            f"Recent headlines:\n{headlines}\n\n"
            f"Recent 1-month price move: {ctx['indicators']['momentum_1m']*100:.1f}%\n"
            "Assess the overall market sentiment toward this stock."
        )

    def _analyze_offline(self, ctx):
        news = ctx["md"].news
        reasons = []
        if news:
            pos = neg = 0
            for h in news:
                words = set(re.findall(r"[a-z]+", h.lower()))
                pos += len(words & _POS_WORDS)
                neg += len(words & _NEG_WORDS)
            net = pos - neg
            reasons.append(f"Headline tone: {pos} positive vs {neg} negative cues.")
            score = max(-1, min(1, net))
        else:
            # No headlines -> use short-term price action as a sentiment proxy.
            mom = ctx["indicators"]["momentum_1m"]
            score = 1 if mom > 0.03 else (-1 if mom < -0.03 else 0)
            reasons.append("No headlines; inferring mood from recent price action.")

        return AgentView(
            self.name,
            _score_to_signal(score, band=0.5),
            0.55 if score else 0.4,
            reasons,
        )


# ---------------------------------------------------------------------------
# 4. Risk Manager  (deterministic veto -- the LLM cannot override it)
# ---------------------------------------------------------------------------
class RiskManager(Agent):
    name = "Risk Manager"
    role = "risk manager protecting capital"

    def analyze(self, ctx: dict, llm) -> AgentView:
        """Risk is always computed from hard numbers; the veto is non-negotiable."""
        fc = ctx["forecast"]
        s = ctx["settings"]
        reasons = []
        veto = False

        if fc.annual_vol > s.risk_max_annual_vol:
            veto = True
            reasons.append(
                f"Volatility {fc.annual_vol*100:.0f}% exceeds limit "
                f"{s.risk_max_annual_vol*100:.0f}% -> VETO on new BUY.")
        else:
            reasons.append(f"Volatility {fc.annual_vol*100:.0f}% within limits.")

        if fc.var > s.risk_max_var:
            veto = True
            reasons.append(
                f"5% Value-at-Risk {fc.var*100:.0f}% exceeds limit "
                f"{s.risk_max_var*100:.0f}% -> VETO on new BUY.")
        else:
            reasons.append(f"5% VaR {fc.var*100:.0f}% acceptable.")

        reasons.append(f"Worst-case (CVaR) loss ~{fc.cvar*100:.0f}% over the horizon.")

        # Optional: let Claude add a one-line narrative, but it cannot change the veto.
        if llm.is_enabled:
            try:
                note = llm.ask(
                    self.model,
                    system="You are a blunt risk manager. One sentence only.",
                    prompt=(f"Volatility {fc.annual_vol*100:.0f}%, 5% VaR {fc.var*100:.0f}%, "
                            f"CVaR {fc.cvar*100:.0f}%. Give a one-sentence risk verdict."),
                    max_tokens=80,
                )
                if note:
                    reasons.append(note)
            except Exception:
                pass

        return AgentView(
            self.name,
            "SELL" if veto else "HOLD",
            0.9 if veto else 0.5,
            reasons,
            veto=veto,
        )


# ---------------------------------------------------------------------------
# 5. Portfolio Manager  -- weighs the team and makes the final call
# ---------------------------------------------------------------------------
class PortfolioManager:
    name = "Portfolio Manager"
    model = PORTFOLIO_MODEL

    def decide(self, ctx: dict, views: list[AgentView], risk: AgentView, llm) -> FinalDecision:
        # 1) Deterministic weighted vote of the three analysts.
        weighted = 0.0
        for v in views:
            w = AGENT_WEIGHTS.get(v.agent, 0.0)
            weighted += _VOTE[v.signal] * v.confidence * w
        # Normalise to [-1, 1] (weights sum to 1, confidence <= 1).
        net = weighted

        # 2) Tilt by the Monte Carlo physics engine.
        fc = ctx["forecast"]
        net += (fc.prob_profit - 0.5) * 0.6   # >50% chance of profit nudges bullish

        signal = _score_to_signal(net, band=0.12)

        # 3) Enforce the Risk Manager's hard veto.
        risk_vetoed = False
        if risk.veto and signal == "BUY":
            signal = "HOLD"
            risk_vetoed = True

        confidence = min(0.95, 0.4 + abs(net))

        # 4) Position sizing: scale by conviction, shrink when volatile.
        if signal == "BUY":
            size = confidence * (1 - min(1.0, fc.annual_vol)) * 100
            position = round(min(25.0, max(2.0, size)), 1)
        else:
            position = 0.0

        # 5) Narrative thesis (AI writes it if available; otherwise templated).
        key_points = [f"{v.agent}: {v.signal} ({v.confidence*100:.0f}%)" for v in views]
        key_points.append(
            f"Monte Carlo: {fc.prob_profit*100:.0f}% chance of profit, "
            f"expected {fc.expected_return*100:+.1f}% over {fc.horizon_days} days.")
        if risk_vetoed:
            key_points.append("Risk Manager VETOED the BUY -> downgraded to HOLD.")

        thesis = self._thesis(ctx, signal, position, fc, views, risk, risk_vetoed, llm)

        return FinalDecision(signal, confidence, position, thesis, key_points, risk_vetoed)

    def _thesis(self, ctx, signal, position, fc, views, risk, vetoed, llm) -> str:
        if llm.is_enabled:
            try:
                summary = "\n".join(
                    f"- {v.agent}: {v.signal} ({v.confidence*100:.0f}%) :: "
                    f"{'; '.join(v.rationale[:2])}" for v in views)
                prompt = (
                    f"Ticker {ctx['md'].ticker}. Final signal already decided: {signal} "
                    f"(suggested {position:.1f}% position).\n"
                    f"Analyst opinions:\n{summary}\n"
                    f"Risk Manager: {'VETO active. ' if risk.veto else ''}"
                    f"{'; '.join(risk.rationale[:2])}\n"
                    f"Monte Carlo: {fc.prob_profit*100:.0f}% profit probability, "
                    f"expected {fc.expected_return*100:+.1f}%, 5% VaR {fc.var*100:.0f}%.\n"
                    "Write a crisp 3-4 sentence investment thesis explaining the call.")
                txt = llm.ask(self.model, "You are a portfolio manager writing a clear thesis.",
                              prompt, max_tokens=400)
                if txt:
                    return txt
            except Exception:
                pass

        # Offline templated thesis.
        verb = {"BUY": "initiate a long position in", "SELL": "avoid / reduce",
                "HOLD": "stay neutral on"}[signal]
        extra = (" The Risk Manager's veto capped this at HOLD despite a bullish lean."
                 if vetoed else "")
        return (
            f"We {verb} {ctx['md'].ticker}. The analyst team leans {signal.lower()}, "
            f"and the Monte Carlo engine puts the probability of profit at "
            f"{fc.prob_profit*100:.0f}% with an expected {fc.expected_return*100:+.1f}% "
            f"return over {fc.horizon_days} trading days (5% VaR {fc.var*100:.0f}%)."
            f"{extra} Suggested allocation: {position:.1f}% of the portfolio."
        )


def analyst_team() -> list[Agent]:
    """The three opinion-forming analysts (Risk + Portfolio handled separately)."""
    return [FundamentalAnalyst(), TechnicalAnalyst(), SentimentAnalyst()]
