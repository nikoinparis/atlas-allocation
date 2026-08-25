# Recent-return alpha and risk-scaling search v1

## Objective

Increase the most recent years' return while preserving a high Sharpe ratio and
an explicit drawdown budget. This program does not treat a selected trailing
year as an expected future return, and it does not authorize live trading.

## External research basis

- Daniel and Moskowitz, *Momentum Crashes*: momentum losses cluster in panic,
  high-volatility rebound states, motivating explicit crash and volatility
  controls: https://www.nber.org/papers/w20439
- Moreira and Muir, *Volatility-Managed Portfolios*: scaling exposure inversely
  with lagged volatility can improve factor Sharpe when expected return does not
  rise proportionately with volatility: https://papers.ssrn.com/abstract=2773438
- Blitz, Huij, and Martens, *Residual Momentum*: issuer-specific residual
  momentum may contain cleaner risk-adjusted information than total-return
  momentum: https://papers.ssrn.com/abstract=2319861
- George and Hwang's 52-week-high mechanism was treated cautiously because a
  recent international re-evaluation finds limited incremental explanatory
  power outside the original U.S. result:
  https://academic.oup.com/rof/article/29/1/241/7772889

These papers motivate candidate mechanisms only. They do not validate this
project's implementation or its simulated results.

## Experiment 1 — Bounded causal risk scaling

Twelve rules were frozen before evaluation: an unchanged control, three fixed
exposures, three inverse-volatility rules, two trend-confirmed volatility rules,
a momentum-crash guard, a drawdown throttle, and a combined trend/drawdown rule.
Exposure was capped at 1.5x, financing was charged at 6% annually and stressed
at 10%, underlying paths were tested at 50/100/200 bps, and challenger
bootstrap probabilities received a Bonferroni adjustment.

The volatility-managed and drawdown-managed rules reduced return and Sharpe.
Fixed 1.25x and 1.35x passed every overlay-level gate. The weekly 1.35x result
was 185.77% trailing-year CAGR, 3.046 Sharpe, -11.82% drawdown, 56.22% full CAGR,
and 153.49% severe-cost/financing recent CAGR. This was not accepted as a final
result because weekly endpoints can hide intrawweek losses and the source
strategy had not passed its joint issuer-dependence gate.

## Experiment 2 — Price-confirmed fundamental membership

Nine delayed price-confirmation challengers added 10%, 20%, or 30% residual
momentum, trend quality, or their equal combination to the frozen fundamental
scores. The construction retained twenty-name component breadths, the existing
generic sector limits, one full price-observation delay, issuer removals,
execution delays, severe costs, endpoint perturbation, rolling windows, and
Bonferroni-adjusted bootstraps.

Every challenger failed. The strongest, `trend_10`, reduced recent CAGR from
124.20% to 111.86%, Sharpe from 3.103 to 2.876, full CAGR from 42.74% to 38.49%,
and the worst five-issuer result to 86.87%. This branch is closed without
post-result tuning.

## Experiment 3 — Exact-daily reconstruction

The frozen 26-name sector-aware ensemble was rebuilt from its saved stock and
strategy targets using exact daily adjusted closes. Four securities without
validated daily histories were held as cash under the existing base missing-
company policy; no ticker substitution or price fabrication was allowed.

| Exposure | Daily trailing-year CAGR | Sharpe | Maximum drawdown |
| --- | ---: | ---: | ---: |
| 1.00x | 118.79% | 2.643 | -17.94% |
| 1.25x | 157.93% | 2.605 | -22.59% |
| 1.35x | 174.97% | 2.594 | -24.43% |

At 1.25x, one- and two-session delays retained 152.49% and 152.46% CAGR. At
1.35x they retained 168.71% and 168.67%. The maximum daily-versus-weekly
reconciliation difference was 2.77%, inside the frozen 3% audit tolerance.

## Decision

The 1.25x and 1.35x paths are saved as **research-only return amplifiers**. They
demonstrate that the existing alpha path can mechanically clear 150% after
financing while retaining a high retrospective Sharpe, but they do not create
independent alpha and they magnify every source-strategy error. The 1.35x path
is the return leader; the 1.25x path is the better risk trade-off.

Neither is a promoted replacement because the underlying 124.20% strategy
still fails the joint issuer and adjusted-bootstrap evidence required for
promotion. The next genuine-alpha stage remains the frozen broad-universe
tournament after its coverage gate opens, followed by an exact-daily audit and
forward evidence for any winner.

## Experiment 4 — Fragility-aware accelerator and independent industry residuals

A frozen 40-candidate tournament tested whether the existing alpha could be
improved by conditioning a residualized accelerator on lagged issuer, sector,
breadth, and volatility fragility. It also tested a genuinely separate family
that combined industry-residual momentum with point-in-time SEC acceleration.

The return leader, `alpha30_1.35x`, reached 186.90% trailing-52-week CAGR,
3.206 Sharpe, and -15.06% drawdown. At 200-bps costs it returned 142.28%; its
worst delayed-execution and conservative five-issuer results were 159.63% and
162.32%. The result did not pass: rolling 26-week outperformance was only
47.02%, and its familywise-adjusted bootstrap probability was 83.68% rather
than the required 95%.

The independent industry-residual family topped out at 71.20% recent CAGR and
failed the five-issuer test. It is rejected. The 186.90% candidate is retained
as the strongest fragile diagnostic, with no replacement authority and no live
trading.

## Experiment 5 — Broad quant mathematics v3

The open broad-data gate enabled a 96-candidate, pre-result sealed tournament
using causal monthly decisions, robust residual momentum, quality interactions,
purged nonlinear ridge, inverse-volatility sizing, covariance shrinkage,
volatility targeting, deflated Sharpe, and CSCV overfitting analysis.

The best broad candidate returned 123.33% recently with 1.590 Sharpe and
-43.66% drawdown. Delayed execution reduced it to 23.99%, and removal of the
five largest contributors reduced it to -10.31%. Every candidate was rejected.

## Experiment 6 — Mathematical exposure ceiling

A separate 22-rule study applied fixed exposure, lagged volatility targeting,
fractional Kelly, and fragility-tier sizing to the 186.90% source path. Fixed
1.50x returned 217.11%, fixed 1.65x returned 249.96%, and fixed 2.00x returned
337.83% over the recent year. A volatility-controlled rule returned 220.60%
with 3.213 Sharpe and -15.45% recent drawdown.

These results show that leverage can mechanically clear 200% and 300% on the
observed path. They do not establish new alpha. No rule passed the combined
familywise, deflated-Sharpe, and probability-of-overfitting gates, so all are
retained only as fragile research diagnostics.

## Experiment 7 — Cash-only separation and exact-daily reconciliation

The `alpha30` source was explicitly separated from its financing overlays. On
the already-frozen weekly source path through August 7, 2026, the 1.00x
cash-only version returned 125.73% over the trailing 52 weeks with 3.286 Sharpe
and -11.12% maximum drawdown. A hypothetical $10,000 became $22,572.98. It uses
no borrowed capital and pays zero financing; ordinary underlying strategy
costs remain.

An exact-daily reconstruction was also frozen and executed for 1.00x, fixed
1.50x, volatility-controlled 1.75x, and fixed 2.00x paths. The first version
correctly failed reconciliation after exposing an omitted balancing-cash leg.
The corrected second version removed that accounting error, but 124 archived
stock identities still lacked validated daily histories and were held as cash.
Its maximum daily-to-weekly discrepancy was 15.27%, above the frozen 4% limit.
Those daily figures are therefore incomplete diagnostics and are not eligible
for dashboard promotion or strategy replacement.

The financing-free weekly metric is the trustworthy comparison currently
available. The leveraged 217%-338% figures remain exposure overlays, not proof
that the underlying strategy itself earns those returns without additional
capital at risk.
## Cross-component overlap budget

Forced separation between the cash-conversion and balance-quality cohorts did
not improve the incumbent. The best robustness-oriented construction returned
122.37% recent CAGR with 3.078 Sharpe and -8.71% drawdown, versus the exact
124.20% control, while its five-issuer removal case reached only 109.21%.
Because it failed the frozen return, issuer, temporal, and adjusted-bootstrap
gates, it is retained only as a diagnostic. The 1.25x and 1.35x daily research
amplifiers were not applied to this weaker base.
