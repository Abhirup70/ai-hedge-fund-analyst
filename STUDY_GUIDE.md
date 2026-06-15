# 📚 STUDY GUIDE — AI Investment Research Desk
### Everything you need to understand this project and ace any interview about it

> **How to use this doc:** Read it once start-to-finish to build intuition, then re-read the **"Interview Q&A Bank"** at the end the night before any interview. Every concept is explained from scratch (finance *and* code), so no prior knowledge is assumed.

---

## 📑 Table of Contents
1. [The 30-second pitch](#1-the-30-second-pitch)
2. [The big picture — how it all fits together](#2-the-big-picture)
3. [PART A — Finance concepts (explained simply)](#part-a--finance-concepts)
4. [PART B — The physics: Monte Carlo & Brownian motion](#part-b--the-physics)
5. [PART C — The technical / AI architecture](#part-c--the-technical--ai-architecture)
6. [PART D — Walk through the code, file by file](#part-d--code-walkthrough-file-by-file)
7. [PART E — The full data flow (step by step)](#part-e--the-full-data-flow)
8. [PART F — Limitations & honest critique](#part-f--limitations--honest-critique)
9. [PART G — Interview Q&A Bank](#part-g--interview-qa-bank)
10. [Glossary](#glossary)

---

## 1. The 30-second pitch
*(Memorise this. It's your answer to "tell me about your project.")*

> "I built an **AI Investment Research Desk** — a multi-agent system that researches a stock the way a hedge-fund team does. Five specialist AI agents (fundamental, technical, sentiment, a risk manager, and a portfolio manager) form opinions and **debate**; the risk manager has a **hard veto** that the language model cannot override. Their reasoning is grounded by a **Monte Carlo physics engine** that simulates 20,000 possible price futures using Geometric Brownian Motion, and the whole strategy is **backtested against real market history with no look-ahead bias**. It runs **free and offline** with rule-based agents, or you flip one switch to power the agents with **Claude**. There's a CLI and a Streamlit web app."

**Why it's impressive:** it combines the three things AI teams hire for — *agentic AI*, *quantitative rigor*, and *production engineering judgment* (safety guardrails, graceful fallback, cost-tiered models).

---

## 2. The big picture

```
   YOU type a ticker (e.g. AAPL)
            │
            ▼
   ┌──────────────────┐
   │   DATA LAYER     │  download real prices (Yahoo) or simulate a synthetic stock
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │  INDICATORS      │  trend, RSI, momentum, volatility
   └────────┬─────────┘
            ▼
   ┌──────────────────┐
   │ 🌀 MONTE CARLO   │  simulate 20,000 futures → probability of profit, risk
   └────────┬─────────┘
            ▼
   ┌──────────────────────────────────────────┐
   │  AGENTS (rule-based OR Claude-powered)     │
   │  Fundamental · Technical · Sentiment       │  → they debate
   │  Risk Manager (VETO) → Portfolio Manager   │  → final call
   └────────┬───────────────────────────────────┘
            ▼
   ┌──────────────────┐
   │  📊 BACKTEST      │  did this signal actually work historically?
   └────────┬─────────┘
            ▼
   Terminal dashboard + Markdown report + forecast chart (or web app)
```

Two mental models to keep straight:
- **The "desk"** = the team of agents (the AI part).
- **The "engine"** = the math (Monte Carlo, indicators, backtest) that the agents lean on.

---

# PART A — Finance concepts

You don't need a finance degree. Here is every finance term used in the project, in plain English.

### A1. Ticker symbol
A short code identifying a company's stock. `AAPL` = Apple, `TSLA` = Tesla. It's the input to the whole system — "which company should the desk research?"

### A2. Price history & returns
- **Price history** = the daily closing price of the stock over time.
- **Return** = the percentage change. If a stock goes 100 → 110, the return is +10%.
- **Log return** = `ln(price_today / price_yesterday)`. We use *log* returns because they **add up over time** (mathematically convenient) and they're what the Brownian-motion math assumes. In code: [physics.py](ai_desk/physics.py).

### A3. The Fundamental Analyst's metrics (is the *business* good?)
| Metric | What it means | Rule of thumb in the code |
|---|---|---|
| **P/E ratio** (Price-to-Earnings) | Price ÷ earnings per share. How many dollars you pay per $1 of profit. | < 15 = "cheap", > 40 = "expensive" |
| **Revenue growth** | How fast sales are growing year over year | > 10% = strong, < 0 = shrinking |
| **Profit margin** | What % of revenue becomes profit | > 15% = healthy, < 0 = losing money |
| **Debt-to-Equity** | How much debt vs. shareholder money | High = riskier |

> 💡 *Interview nuance:* a high P/E isn't automatically bad — investors pay up for fast growth (e.g., Nvidia). That's why the code also looks at growth, not just P/E.

### A4. The Technical Analyst's metrics (what is the *chart* doing?)
Technical analysis ignores the business and just studies price patterns.

- **SMA (Simple Moving Average)** — the average price over the last *N* days. We use **SMA-20** (short-term) and **SMA-50** (longer-term).
  - **Uptrend** = price above SMA-50 **and** SMA-20 above SMA-50.
  - When a short average crosses *above* a long average it's a bullish **"golden cross"**; crossing below is a bearish **"death cross."**
- **RSI (Relative Strength Index)** — a 0–100 momentum gauge.
  - **> 70 = "overbought"** (rose too fast, might pull back).
  - **< 30 = "oversold"** (fell too fast, might bounce).
  - Formula: compares the average size of up-days vs down-days over 14 days.
- **Momentum** — the recent return (we use the 1-month, ~21-trading-day, % change). Positive momentum = "the trend is your friend."
- **52-week range position** — where today's price sits between the year's low (0) and high (1).

### A5. Volatility (how *bumpy* is the ride?)
- **Volatility** = the standard deviation of returns — how much the price typically swings.
- We compute daily volatility, then **annualize** it by multiplying by `√252` (there are ~252 trading days in a year). This is the **"square-root-of-time" rule**.
- High volatility = high risk = the Risk Manager pays attention.

### A6. Risk metrics: VaR and CVaR (how *bad* can it get?)
These answer "what's my downside?"

- **VaR (Value-at-Risk) at 5%** = the loss you will **not** exceed 95% of the time. If 5% VaR = 12%, it means: *"On the worst 5% of outcomes, you'd lose at least 12%."* It's the 5th-percentile outcome.
- **CVaR (Conditional VaR, a.k.a. Expected Shortfall)** = the **average** loss *within* that worst 5%. CVaR is always ≥ VaR and is more honest about tail risk because it looks at *how bad* the bad cases are, not just the cutoff.

> 💡 *Interview gold:* "VaR tells you the *threshold* of the bad zone; CVaR tells you the *average severity* inside it. After 2008, regulators moved toward CVaR because VaR ignores how catastrophic the tail is."

### A7. Position sizing (how *much* to buy?)
Deciding to buy isn't enough — *how much*? The Portfolio Manager scales the position by:
- **higher conviction → bigger position**, and
- **higher volatility → smaller position** (risk control),
- capped at 25% so we never bet the farm on one stock.

This is the spirit of the **Kelly criterion / risk parity** — bet more when the edge is strong and the risk is low. In code: `PortfolioManager.decide` in [agents.py](ai_desk/agents.py).

### A8. Backtesting (does the strategy actually work?)
- **Backtest** = replay the strategy on historical data and see if it would have made money.
- **Hit-rate** = % of BUY signals that were followed by a price rise.
- **Strategy vs buy-and-hold** = did following our signals beat just buying and holding the stock?
- **Look-ahead bias** = the #1 backtesting sin: accidentally using *future* information to make a *past* decision. We avoid it by computing each signal using **only data available up to that day** (see [backtest.py](ai_desk/backtest.py)).
- **Non-overlapping windows** = we test on independent time chunks so results aren't double-counted.

---

# PART B — The physics

This is the standout part. Be able to explain it cleanly.

### B1. The core idea
A stock price wanders randomly, like a dust particle bouncing around in water. That random wandering is called **Brownian motion** (Einstein, 1905). In finance, the standard model is **Geometric Brownian Motion (GBM)**:

```
dS = μ·S·dt  +  σ·S·dW
     └ drift ┘   └ randomness ┘
```
- `S` = stock price
- `μ` (mu) = **drift** — the average direction/return
- `σ` (sigma) = **volatility** — the size of the random kicks
- `dW` = a **Wiener process** — the mathematical "random kick" each instant (a normal random number)

### B2. Why "**Geometric**" (not plain) Brownian motion?
Because real prices:
1. **can't go negative** (GBM models the *percentage* change, so price stays positive), and
2. **compound** (a 10% move on $100 is bigger than on $10).

So we model the **log** of the price as a random walk. The discrete formula we actually simulate (one day at a time):

```
daily log-return = (μ − ½σ²) + σ·Z      where Z ~ standard normal
```

> 💡 The **`− ½σ²`** term is the **Itô correction** (from Itô's lemma in stochastic calculus). It's there so that the *average* simulated price matches the true expected price — volatility otherwise biases the average upward. Knowing this term exists and why = instant credibility.

### B3. Monte Carlo simulation
Instead of solving the equation with calculus, we **simulate**:
1. Estimate `μ` and `σ` from the stock's recent history.
2. Generate **20,000 random future paths**, each 21 days long.
3. Look at where all 20,000 paths *ended up* and just **count**:
   - **Probability of profit** = % of paths that ended above today's price.
   - **Expected return** = average ending return.
   - **Percentiles (10th–90th)** = the "cone of outcomes" you see in the chart.
   - **VaR / CVaR** = read off the worst 5% of endings.

"Monte Carlo" = solving a problem by running many random trials and reading the statistics. Named after the casino. In code: `run_monte_carlo` in [physics.py](ai_desk/physics.py).

### B4. The killer interview fact: finance = physics
The famous **Black–Scholes** option-pricing equation, which is *derived from this same GBM model*, is **mathematically identical to the heat (diffusion) equation** in physics — the equation describing how heat spreads through a metal bar. Same math, different field.

> Say this in an interview and you instantly sound like someone who *understands* the model, not just someone who imported a library.

### B5. Honest limitations of GBM (interviewers WILL probe this)
GBM assumes:
- **constant volatility** (real volatility clusters — calm periods and panicky periods),
- **normally distributed returns** (real markets have **"fat tails"** — crashes happen far more often than a normal distribution predicts),
- **no jumps** (real prices gap on news),
- **independent days** (real returns have some autocorrelation).

Knowing these weaknesses and naming better models (**GARCH** for changing volatility, **jump-diffusion / Merton model**, **Student-t** for fat tails) is exactly what separates a strong candidate.

---

# PART C — The technical / AI architecture

### C1. What is a "multi-agent system"?
Instead of asking one AI a giant question, you split the problem among several **specialized agents**, each with a narrow job and its own context, then combine their outputs. Benefits:
- **Specialization** → each agent reasons better on a focused task.
- **Separation of concerns** → easier to build, test, and explain.
- **Debate / cross-checking** → agents critique each other, reducing blind spots.
- **It mirrors how real organizations work** (a desk of analysts + a decision-maker).

This is *the* hot AI architecture in 2026, which is why it's the centerpiece.

### C2. The 5 agents and their roles
| Agent | Job | Offline brain | AI brain |
|---|---|---|---|
| **Fundamental Analyst** | Value/growth/profitability | P/E, growth, margin rules | Claude reads the fundamentals |
| **Technical Analyst** | Chart signals | Trend + RSI + momentum rules | Claude reads the indicators |
| **Sentiment Analyst** | News mood | Keyword tone of headlines | Claude judges sentiment |
| **Risk Manager** | Protect capital | **Hard veto** on VaR/volatility | (numbers only; LLM can add commentary but **not** override) |
| **Portfolio Manager** | Final decision | Weighted vote + MC tilt | Claude writes the thesis |

### C3. The "flip switch" — offline vs AI mode (a key design talking point)
The class `LLM` in [llm.py](ai_desk/llm.py) is the single switch:
- **Offline mode** (default): `is_enabled = False`. Every agent uses its transparent, deterministic **rule** (`_analyze_offline`). 100% free, no key, no network.
- **AI mode** (`--ai` + an `ANTHROPIC_API_KEY`): `is_enabled = True`. Agents call **Claude** to reason.

Everything else in the codebase just asks `llm.is_enabled` — it never cares which brain answered. This is the **Strategy design pattern** + **graceful degradation**.

> 💡 *Why this impresses:* it shows you don't hard-couple your app to a paid external service. The app always works, even with no internet or no budget.

### C4. The debate loop
In AI mode, after each analyst gives a first opinion, they're shown their **colleagues' opinions** and asked to reconsider (`peer_views` in [orchestrator.py](ai_desk/orchestrator.py) and `_analyze_ai` in [agents.py](ai_desk/agents.py)). This is the "agents arguing" mechanism — it can surface disagreement and let agents revise.

### C5. Safety guardrail: the un-overridable veto (AI-safety talking point)
The **Risk Manager's veto is pure code**, computed from numbers (volatility & VaR thresholds in [config.py](ai_desk/config.py)). In AI mode, Claude can write a one-line risk *comment*, but it **cannot change the veto**. The Portfolio Manager enforces it: a vetoed BUY is downgraded to HOLD.

> 💡 This is the principle of **separating "creative reasoning" (the LLM) from "non-negotiable rules" (deterministic code)** — exactly how safety-critical AI is built. Huge signal for AI-safety-conscious teams.

### C6. Cost engineering: tiered models
In [config.py](ai_desk/config.py):
- analysts use **`claude-haiku-4-5`** (cheap + fast — there are many analyst calls),
- the Portfolio Manager uses **`claude-opus-4-8`** (strongest — but only ONE final call).

"Use the cheapest model that's good enough for each sub-task" = real production cost discipline.

### C7. Structured output & robustness
Agents ask Claude to reply in **strict JSON** (`{"signal", "confidence", "rationale"}`). The parser `_parse_json` ([agents.py](ai_desk/agents.py)) handles messy responses (extracts the JSON even if the model adds prose). If the AI call fails entirely, the agent **falls back to its offline rule** instead of crashing. Defensive design.

### C8. Software-engineering patterns used (name these in interviews)
- **Dataclasses** (`MarketData`, `Forecast`, `AgentView`, `FinalDecision`, `DeskResult`) — clean typed containers.
- **Base class + polymorphism** — `Agent` base, each agent overrides `_analyze_offline` / prompts.
- **Separation of concerns** — data / physics / agents / orchestration / reporting are separate modules.
- **Single entry point** for side effects (the `LLM` wrapper is the only thing that talks to the network for AI).
- **Reproducibility** — fixed random `seed` so Monte Carlo results are repeatable.
- **Presentation vs logic split** — CLI and Streamlit UI both reuse the *same* engine.

---

# PART D — Code walkthrough, file by file

| File | Responsibility | Key things inside |
|---|---|---|
| [main.py](main.py) | CLI entry point | argument parsing, builds `Settings` + `LLM`, calls `run_desk`, prints/saves reports. The `--ai` flag is the flip switch. |
| [ai_desk/config.py](ai_desk/config.py) | All settings | model names, `Settings` dataclass (horizon, paths, thresholds), `AGENT_WEIGHTS`. |
| [ai_desk/data.py](ai_desk/data.py) | Data + indicators | `get_market_data` (Yahoo → synthetic fallback), `compute_indicators` (SMA/RSI/momentum/vol). |
| [ai_desk/physics.py](ai_desk/physics.py) | Monte Carlo engine | `estimate_parameters` (μ, σ), `run_monte_carlo` (GBM simulation → probabilities, VaR, CVaR). |
| [ai_desk/llm.py](ai_desk/llm.py) | The flip switch | `LLM` class; `is_enabled`; `ask()` wraps Anthropic `messages.create`. |
| [ai_desk/agents.py](ai_desk/agents.py) | The 5 agents | `AgentView`, `FinalDecision`, `technical_signal`, the agent classes, the veto, the Portfolio Manager's aggregation. |
| [ai_desk/orchestrator.py](ai_desk/orchestrator.py) | The conductor | `run_desk` runs the full pipeline + debate loop, returns one `DeskResult`. |
| [ai_desk/backtest.py](ai_desk/backtest.py) | Validation | `run_backtest` — walk-forward, no look-ahead, hit-rate, strategy vs hold. |
| [ai_desk/report.py](ai_desk/report.py) | Output | terminal dashboard (rich), Markdown report, Monte Carlo PNG (matplotlib). |
| [streamlit_app.py](streamlit_app.py) | Web UI | interactive dashboard + Plotly fan chart; reuses the same engine. |

### How the Portfolio Manager makes the final call (the most-asked code question)
In `PortfolioManager.decide` ([agents.py](ai_desk/agents.py)):
1. **Weighted vote**: each analyst's signal (BUY=+1, HOLD=0, SELL=−1) × its confidence × its weight (Fundamental 40%, Technical 35%, Sentiment 25%).
2. **Monte Carlo tilt**: nudge the score by `(probability_of_profit − 0.5)` — better odds push bullish.
3. **Threshold** the score into BUY / HOLD / SELL.
4. **Enforce the veto**: if Risk vetoed and the call was BUY → downgrade to HOLD.
5. **Size the position**: scale by confidence, shrink for volatility, cap at 25%.
6. **Write the thesis**: Claude writes it in AI mode, otherwise a clear template.

---

# PART E — The full data flow

This is the "walk me through what happens when you run it" answer:

1. **You run** `python main.py AAPL` (or click *Run* in the web app).
2. **`main.py`** builds a `Settings` object and an `LLM` (off unless `--ai`).
3. **`orchestrator.run_desk`** takes over:
   1. `data.get_market_data("AAPL")` → tries Yahoo Finance; on failure, generates a synthetic GBM stock. Returns prices + fundamentals + news.
   2. `data.compute_indicators` → SMA-20/50, RSI, momentum, volatility.
   3. `physics.run_monte_carlo` → 20,000 simulated futures → probability of profit, expected return, VaR, CVaR, percentile bands.
   4. The **3 analysts** each produce an `AgentView` (signal + confidence + reasons) — rule-based or via Claude.
   5. *(AI mode)* a **debate round** — analysts see peers and may revise.
   6. The **Risk Manager** computes hard risk numbers and sets a **veto** flag.
   7. The **Portfolio Manager** combines everything → `FinalDecision` (signal, confidence, position size, thesis).
   8. `backtest.run_backtest` → replays the technical signal across history → hit-rate + strategy vs buy-and-hold.
4. **`report.py`** renders the terminal dashboard, saves a Markdown report and a Monte Carlo chart.
5. Result: a clear, evidence-backed BUY / HOLD / SELL with a written thesis.

---

# PART F — Limitations & honest critique
*(Interviewers love candidates who can critique their own work. Volunteer these.)*

- **GBM is a simplification** — constant volatility, normal returns, no fat tails or jumps (see B5). A crash is more likely than the model thinks.
- **The backtest validates the technical signal**, not the full LLM debate (LLM calls across all of history would be slow/costly). It's a directional sanity check, not a production trading proof.
- **No transaction costs / slippage / taxes** modeled — real trading erodes returns.
- **Fundamentals from `.info` can be stale or missing** for some tickers.
- **Sentiment is keyword-based offline** — crude; real sentiment needs NLP/finBERT or the LLM.
- **Past performance ≠ future results** — the eternal finance caveat.
- **Not financial advice** — it's an educational/portfolio project.

**How I'd productionize it:** add GARCH volatility + fat-tailed returns, a proper data warehouse, an evaluation harness for the agents, caching, async LLM calls, transaction-cost-aware backtesting, and monitoring.

---

# PART G — Interview Q&A Bank
*(Practice saying these out loud.)*

**Q1. Tell me about this project.**
→ Use the 30-second pitch (Section 1).

**Q2. Why a multi-agent system instead of one big prompt?**
→ Specialization improves reasoning, separation of concerns makes it testable and explainable, and a debate/veto structure catches blind spots. It also mirrors a real analyst desk. One mega-prompt is a black box that's hard to debug or trust.

**Q3. How do you stop the AI from making a reckless call?**
→ The Risk Manager's veto is **deterministic code**, not the LLM. The model can comment but the veto is computed from volatility and VaR thresholds and is enforced by the Portfolio Manager. I deliberately separate creative reasoning from non-negotiable safety rules.

**Q4. Explain the Monte Carlo engine.**
→ Section B1–B3: model the price as Geometric Brownian Motion, estimate drift and volatility from history, simulate 20,000 future paths, and read probabilities/risk straight off the distribution of outcomes.

**Q5. What's the difference between VaR and CVaR?**
→ VaR is the loss threshold you won't exceed 95% of the time (the 5th-percentile outcome). CVaR is the *average* loss within that worst 5% — it captures tail severity, which VaR ignores.

**Q6. Is GBM realistic? What are its flaws?**
→ Section B5: constant vol, normal returns (no fat tails), no jumps. I'd improve it with GARCH, jump-diffusion, or Student-t returns.

**Q7. How do you avoid look-ahead bias in the backtest?**
→ At each historical date I compute the signal using **only** data up to that day, then measure the *forward* return. I also use non-overlapping windows so results aren't double-counted.

**Q8. Why two different Claude models?**
→ Cost engineering. Analysts make many calls so they use cheap, fast Haiku; the single final decision uses the strongest model, Opus. Right model for each job.

**Q9. What happens if the LLM returns malformed JSON or the API is down?**
→ A tolerant parser extracts JSON even with extra prose; if the whole call fails, the agent falls back to its deterministic offline rule. The app never crashes on AI failure.

**Q10. How does the offline mode work without an LLM?**
→ Each agent has a transparent rule-based brain (e.g., the Technical Analyst scores trend + RSI + momentum). The `LLM.is_enabled` flag is the single switch; the rest of the code is identical.

**Q11. How is the final BUY/HOLD/SELL computed?**
→ Section D ("How the Portfolio Manager makes the final call"): weighted analyst vote + Monte Carlo tilt → threshold → enforce veto → size the position.

**Q12. How would you scale this to production / what's next?**
→ Section F: GARCH/fat tails, transaction-cost-aware backtest, async + cached LLM calls, an agent-evaluation harness, real-time data, monitoring, and a public deployment.

**Q13. What did you learn / what was hard?**
→ Designing the offline↔AI abstraction cleanly, keeping the safety veto outside the LLM, and being honest about model limitations (GBM's assumptions). 

**Q14. Why should the risk rule be code and not just a prompt instruction?**
→ Prompts can be ignored, misread, or jailbroken; deterministic code can't. Safety-critical constraints belong in code with tests, not in natural-language instructions to a probabilistic model.

---

## Glossary
- **Agent** — a software component with one focused job; here, optionally powered by an LLM.
- **Backtest** — simulating a strategy on historical data to estimate performance.
- **Brownian motion** — random-walk physics; the basis of the price model.
- **CVaR (Expected Shortfall)** — average loss in the worst X% of cases.
- **Drift (μ)** — the average expected return.
- **Fat tails** — extreme events happening more often than a normal distribution predicts.
- **GBM (Geometric Brownian Motion)** — the standard stochastic model for stock prices.
- **Graceful degradation** — the system still works (with reduced features) when a dependency is unavailable.
- **Hit-rate** — % of BUY signals followed by a gain.
- **Itô correction (−½σ²)** — adjustment so simulated average price is unbiased.
- **Look-ahead bias** — illegally using future data in a backtest.
- **Monte Carlo** — solving problems via many random simulations.
- **Momentum** — recent price trend / return.
- **P/E ratio** — price per dollar of earnings; a valuation gauge.
- **RSI** — 0–100 overbought/oversold momentum indicator.
- **SMA** — simple moving average of price.
- **Stochastic** — involving randomness.
- **VaR (Value-at-Risk)** — the loss threshold not exceeded with X% confidence.
- **Volatility (σ)** — standard deviation of returns; how bumpy the price is.
- **Wiener process (dW)** — the mathematical random "kick" in Brownian motion.

---

*Tip for the post: pin the Monte Carlo forecast chart as your LinkedIn image, link the README and a live demo, and lead with the one-liner from Section 1.*
*Educational project — not financial advice.*
