# Research brief: fresh eyes on the whole portfolio, then test everything one by one

Paste everything below the line into a new Claude Code chat opened in this repository
(`/Users/nicholasturangan/Projects/Portfolio Optimizer`).

---

I want you to find an investment strategy, or a combination of strategies, that beats everything I
currently run: profitable, realistic, and something I can run myself as an individual. Be creative and
try new things. Use recent research papers, strategies that banks and hedge funds use and an individual
can copy, new technology, and Goldman Sachs' open-source `gs-quant` library. Mixing several unrelated
strategies into one portfolio counts. So does inventing our own. Then test every idea properly, one at a
time.

Work in five phases, in this order. Do not skip ahead.

## Phase 1 — Fresh eyes: look at my portfolio as if you knew nothing about it

`CLAUDE.md` loads automatically in this folder. Follow its **rules** (testing discipline, honesty), but
for this phase set aside its **conclusions**. Do NOT open `2.0/PROJECT_HISTORY.md`,
`2.0/docs/RESEARCH_QUEUE.md` or any research doc yet. I want your independent view first, the way a new
senior quant would see it on day one.

Read only these facts:

**What I run today (forward clocks: live, untouched weekly records, each needing 52 weeks before any
verdict):**
- `static_spy_gld_shy_v1`: equal thirds SPY / GLD / SHY. This is the **benchmark to beat**.
- `trend_sleeve_8020_v1`: 80% of that mix plus 20% DBMF (a managed-futures ETF).
- `spy_riser_5050_v1`: 50% SPY plus 50% a "steady riser" book (top 20 US stocks by 52-week slope × R²,
  held a year). Higher return, deeper drawdowns: a chosen risk, not an edge.
- `covariance_minimum_variance_v1`, `breadth_confirmed_trend_return_ceiling_v3`,
  `past_only_consensus_selector_return_v1`, `return_first_60_40_blend_v1`: ETF allocation books.
- Stock clocks: `equal_weight_benchmark_v1`, `valuation_earnings_yield_v1`, `sue_quarterly_v1`
  (post-earnings drift), `residual_tie_agnostic_companion_v1`.
- `avoid_hot_leader_ties_v1`: a quarterly "avoid" list of small firms that just announced ties to
  hot stocks.
- Each clock's status is in `2.0/evidence/forward_<name>/status.json`; the protocols are in
  `2.0/config/forward/`.

**My constraints:**
- An individual investor, long-only. I do not borrow or short in my own account. Funds that use futures
  internally (like DBMF) are acceptable.
- Free data first. Anything paid needs my explicit approval before you spend.
- Nothing trades live; everything is research and forward recording.

**Data on disk (`2.0/data/`):**
- Daily and weekly US stock prices 2011-2026 for about 2,800 issuers.
- SEC filings and XBRL fundamentals, 8-K results dates for all issuers, insider and 13F data.
- ETF prices, Fama-French factors, and OSAP published anomaly returns (CRSP-based, so survivorship-free).
- Weekly futures, Hoberg-Phillips product networks, USASpending contracts, GDELT, Wikipedia views.
- **Big caveat:** the stock price panel holds mostly survivors. Only 44.6% of the 2012 SEC filer roster
  has prices, so delisted, acquired and failed companies are largely missing. Any backtest of small or
  volatile stocks is flattered unless you correct for this.

**Phase 1 output:** your honest first impression of this portfolio, where it is weak, and a long list
(at least 20) of candidate improvements and new strategies. Think broadly:
- risk premia and how they are combined;
- event-driven and structural trades;
- options or volatility done safely for an individual;
- carry, trend, seasonality;
- portfolio construction, rebalancing, tax and cost efficiency;
- alternative data;
- machine learning;
- strategies from banks and hedge funds that an individual can actually replicate;
- combinations of unrelated return streams.

Write it to `2.0/docs/FRESH_EYES_REVIEW_V2.md` before moving on.

## Phase 2 — Research: what is new and what is usable

- **Look up recent research** (2023-2026 especially): SSRN, arXiv q-fin, NBER, the top finance
  journals, and practitioner research (AQR, Man Group, Robeco, Alpha Architect, Quantpedia, Research
  Affiliates). For each paper you use, say whether you **read** it this session or are **recalling** it.
  Prefer papers whose effect survived after publication and out of sample.
- **gs-quant** (`github.com/goldmansachs/gs-quant`): clone or read it and work out concretely what an
  individual can use **without** Goldman Marquee credentials, which are institutional. Look at its
  timeseries analytics, backtesting engine, risk, portfolio and pricing tools. List what works offline,
  what needs an API key, and whether any of it improves our testing or construction. Do not claim a
  feature works until you have run it.
- **New technology:** tools and methods that could genuinely improve the portfolio or the testing, such
  as better optimisers, regime or volatility models, faster or more honest backtesting, and data sources.

Add the good findings to the Phase 1 list.

## Phase 3 — Check against what has already been tried

Now read `CLAUDE.md` in full, the **Closed** table at the bottom of `2.0/docs/RESEARCH_QUEUE.md`,
`2.0/docs/SENIOR_QUANT_REVIEW_V1.md`, and search `2.0/PROJECT_HISTORY.md` for each of your ideas.
About 375 research steps exist. Many ideas have been tested and killed, and some are blocked on data.

For every idea, write one line:
- **new**, or
- **already tried (step N, verdict)**, or
- **tried, but your version is genuinely different because...**

Drop the repeats unless you have a real new angle; say why. Then rank the survivors by expected value,
data availability (free versus paid) and effort. Put every surviving idea into the research queue with
a tier, its data and its blocker.

## Phase 4 — Design the combination

I specifically want to know whether **mixing several unrelated strategies** beats any single one.
Design how the survivors would be combined: weights by risk, correlation targets and crisis behaviour.
Use the project's measured correlation and effective-number-of-bets numbers, then check whether the
combination improves on the benchmark to beat (`static_spy_gld_shy_v1`). Say plainly if the honest
answer is that the best realistic improvement is construction, costs and diversification rather than a
new signal.

## Phase 5 — Test everything, one by one

Go through the ranked list one idea at a time. For each:

1. **Pre-register** it in `2.0/config/` before touching any return data: hypothesis, sign, windows,
   costs, trials and a pass/fail rule. Commit the registry first.
2. **Prove the test is correct** before reading the result:
   - Run a positive control, so you know the signal or data does what you think.
   - Run a prefix or look-ahead check where relevant.
   - Run a survivorship check: calibrate against OSAP or another survivorship-free source where you can.
3. **Measure honestly:**
   - Report full metrics: CAGR, Sharpe, max drawdown, volatility, beta, turnover.
   - Use costs of 0/10/50/100 bps.
   - Split by regime: 2012-19, 2020, 2021-22, 2023-26.
   - Compare against SPY and against `static_spy_gld_shy`.
   - Run leave-top-names-out.
   - Correct for multiple testing, counting the project's cumulative searches.
4. **Record** each result in `2.0/PROJECT_HISTORY.md` (next step number, dated, failures included) and
   move it to the queue's Closed table.
5. **If something passes:** freeze it as a new forward clock (protocol in `2.0/config/forward/`, a
   recorder, and a dry run that reproduces an existing clock's numbers before it goes live) and add it
   to the Friday cycle. Historical tests alone never make a strategy "ready".

After each test, tell me in plain words what it was for and what it found, before the tables.

## Rules that protect what already works

- **Never break the Friday cycle** (`2.0/scripts/run_full_friday_cycle_v1.py`, run by launchd at 00:00
  and 12:00 UTC). It needs the Podman VM `portfolio-optimizer-sandbox`.
  - Every clock records once per window, from Friday 21:00 UTC to the next Friday 21:00 UTC.
  - A missed week can never be backfilled.
  - Dry-run any change to the cycle before committing it.
- **Never edit a frozen protocol** in `2.0/config/forward/`; version it instead.
- **The Friday job pushes this branch to `origin/main`.** The checkout must always contain
  `origin/main`, or the job refuses to run.
- **Yahoo throttles** (HTTP 429). Keep bulk downloads polite and never run them during the Friday
  window's first hours. The cycle refuses a price download under 95% of normal size.
- **SEC requests:**
  - Use the project's anonymous agent for EDGAR full-text search and `data.sec.gov`.
  - SEC Archives need a contact agent, which is in the gitignored `2.0/config/local/sec_user_agent.txt`.
  - Never put my email anywhere else, and never commit it.
- **Pending housekeeping, do not resolve it yourself:** the working copy has an uncommitted rewrite of
  `2.0/docs/RESEARCH_QUEUE.md` that I have not confirmed. Ask me before committing or reverting it,
  and commit queue updates only if I approve.
- No purchases and no account sign-ups on my behalf: tell me what would help and why. No live trading.

## What success looks like

Be creative, but be honest. 375 steps have produced no promoted strategy, and the most common failure
here is an idea that works in one market mood (2020, 2023-25) and fails in others. A session that tests
ten ideas properly and kills nine is a good session. If one survives, that is the result I want.

End with:
1. a short ranked summary of what you tested and what survived, with the numbers;
2. your honest recommendation for my portfolio;
3. a short list of what you need from me.
