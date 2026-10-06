# Independent review, 2026-10-07: pre-registration

Written and committed before any return in this review was computed. The reviewer has read
CLAUDE.md, the research queue (Closed table first), and Steps 289–337. ETF prices were
downloaded from Yahoo (free) but no return has been computed from them.

## What this review is allowed to do

Re-check existing verdicts, and run a short list of declared comparisons. **No signal search.**
Nothing here can promote a strategy.

## Reproductions (not searches; no trial count added)

R1. **Beta-matched alpha, headline book.** `sec-residual-controlled-1x-v1` weekly net returns
from `dashboard/public/return-first-dashboard.json`, regressed on SPY weekly returns with a
past-only 52-week beta, my own code, not `run_beta_matched_benchmark_v1.py`. Split at
2025-04-04. Expectation if Step 332 is right: alpha negative before the break.

R2. **Date alignment.** Correlate each book's weekly return with SPY at lags −1, 0, +1. The
highest correlation must be at lag 0, or the dashboard's date conventions are misaligned
(Step 291's bug class).

R3. **Cost grid.** Every dashboard book at 0/10/50/100 bps one-way, rebuilt from the records'
`grossReturn` and `turnover`. Check whether any book records zero cost despite turnover.

R4. **Concentration.** For the headline book, the share of cumulative return from the best 5
and 10 weeks, and the result with them removed. (Name-level leave-one-out needs per-holding
prices and is done only if the holdings records allow it.)

R5. **Static SPY/GLD/SHY equal-thirds**, monthly rebalance, 2005-01 to 2026-09, at 0/10/50/100
bps, with CAGR, Sharpe (excess of BIL/T-bill, and raw), max drawdown, and windows 2005–2026,
2008–2009, 2020, 2022, 2023–2026. Reconcile Step 321 (Sharpe 0.78, maxDD −20.9%) with Step 335
(Sharpe 1.00, maxDD −18.9%).

R6. **Monotonicity power.** Simulate a signal with a known true IC of 0.03 on a 300-name
cross-section at 14 and 39 decisions, and measure how often the project's monotonicity statistic
reads within ±0.17 of zero. Tests Step 296's claim that monotonicity "would show at any sample
size". No market data used.

## Declared comparison set for deployment (4 trials, all reported, none selected on return)

Passive, long-only, unlevered, monthly rebalance, 2005-01 to 2026-09:
1. SPY 100%
2. SPY/IEF 60/40
3. SPY/GLD/SHY equal thirds
4. VT-proxy global equity 60 / IEF 20 / GLD 20 (VT proxied by SPY+EFA 60/40 before 2008-06)

The point is the risk/return trade-off an investor chooses between, not which one "won".
No alpha claim will be made from this set. Trials this review: 4 (on top of the 13 + 10 already
spent on static blends in Steps 321 and 334).
