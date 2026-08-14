# Options Convexity Overlay — v2 Research Plan

> **Standalone research experiment.** This is **not** Track A/B/C/D and is **not**
> a production strategy. It does not modify, import, or change any production
> allocation logic. It only *reads* existing artifacts and writes new `*_v2_*`
> outputs to `data/research/options_convexity/`. The v1 outputs are preserved
> unchanged as the honest rejected baseline. Nothing here is promoted.

## 1. Why v2

v1 bought options when the **ETF allocation** system was bullish. That was the
wrong trigger: ETF signals answer *"should I hold more of this ETF?"*, but an
option only pays if the underlying moves **enough, soon enough** to beat the
premium, time decay and implied vol. v1 was REJECTED — CAGR ~flat, Sharpe and
drawdown and CVaR all worse, and the result leaned on one lucky winner.

v2 keeps v1 intact and adds an **options-specific** signal engine plus parameter
sweeps. The hypothesis:

> Call spreads add value only in **rare acceleration / recovery regimes** where
> the expected forward move clears the spread's breakeven and implied vol is not
> expensive — not merely because the ETF strategy is bullish.

v2 is **more selective and more options-aware** than v1, not a looser version.

## 2. Reads (read-only)

Same production artifacts as v1: baseline weights & net returns for the pin
`improved_frontier_phase5_fragility_guard`, the market-state history, and weekly
prices. v1's `baseline_vs_options_equity.csv` is read to report v1 as a reference.

## 3. Eligible underlyings

`SPY`, `QQQ`, `IWM`, `TLT`, `GLD`.

## 4. Options-specific signal features (all causal / lagged 1 week)

Multi-horizon returns (4w/8w/12w); 4-week trend acceleration; 13w MA slope;
distance from the 40w MA; breakout score (z-score vs short MA); drawdown-recovery
score (position in trailing 52w range); volatility percentile; realized vol vs
trailing median; a defensive→risk-on transition flag; a credit-improvement flag
(HYG/LQD); an **expected forward return proxy** (trailing 12w drift projected
over the option horizon); the **required breakeven move** of the priced spread;
and the **expected-move surplus** = expected move − breakeven.

## 5. Entry logic

Do **not** enter merely because momentum is positive. Require (depending on
ablation level): bullish context, positive trend acceleration, broad multi-
horizon momentum, **expected-move surplus > safety margin**, vol not expensive,
recovery/transition confirmation, premium cap respected, and no entry right after
a volatility spike (unless a panic-rebound sub-study is explicitly tested).

## 6. Sweeps (diagnostics over hand-tuning)

- **DTE buckets:** 21–45, 45–75, 75–100, 100–150.
- **Structures:** (1) call spread 3–7% / 10–20% OTM [default preferred], (2) ATM→10% spread, (3) delta-targeted spread (~0.40 / ~0.20 delta), (4) naked long call 5% OTM (**comparison only**).
- **Entry-filter ablation (cumulative):** L1 bullish → L2 +acceleration → L3 +breakeven → L4 +IV/richness → L5 +re-risking transition.

Call spreads are the default preferred structure (lower premium + theta bleed).

## 7. Sizing

Default premium budget **0.5%–2%** (default 1%, smaller than v1). **Hard cap 3%**
total. Funded by reducing the matching ETF; **no leverage**.

## 8. Cost model (conservative)

IV markup ×1.05, 5% entry slippage, plus a 5% bid/ask half-spread proxy on the
debit. Held to expiry, cash-settled at intrinsic (no time value captured — a
conservative exit assumption). All bias results **against** the overlay.

## 9. Metrics

CAGR, annualized return, annualized vol, net Sharpe, Sortino, max drawdown,
Calmar, CVaR 5%, options hit rate, average / median / worst / best option trade
return, **Sharpe excluding best trade**, total premium spent per year,
activations per year, average DTE, average moneyness, incremental return,
incremental drawdown, and turnover/cost impact — for baseline, v1, and every v2
variant.

## 10. Validation gates

(1) Sharpe improves vs ETF baseline; (2) max drawdown not materially worse;
(3) CVaR not materially worse; (4) not driven by one best trade; (5) Sharpe
ex-best retains the edge; (6) activates rarely but meaningfully; (7) train **and**
holdout both reasonable; (8) costs included; (9) no look-ahead; (10) proxy
documented; (11) the best variant is **not** chosen by overfitting (the MAIN
config is pre-registered; sweeps are descriptive only).

## 11. Pre-registered MAIN config

`spread_3_7_10_20` · DTE `45–75` · ablation **L5** · budget **1%**. Promotion
decisions use THIS config, decided before seeing sweep results, so a good sweep
cell cannot be cherry-picked.

## 12. Verdicts

Default **RESEARCH-ONLY**. **CANDIDATE FOR FURTHER TESTING** only if *all* gates
pass. **REJECT** if core gates clearly fail. If the edge is one-trade-driven, the
verdict can never be CANDIDATE. No automatic promotion under any outcome.
