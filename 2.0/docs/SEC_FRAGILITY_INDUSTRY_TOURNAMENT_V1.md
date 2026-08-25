# SEC fragility and industry-residual tournament v1

## Purpose

This frozen, post-selection tournament completed five related research tasks:

1. test a causal fragility-aware overlay on the existing sector ensemble;
2. map 1.25x, 1.30x, and 1.35x exposure at 8% and 12% financing;
3. build an independent industry-residual momentum plus SEC-acceleration family;
4. compare every candidate on the same August 7, 2026 endpoint and cost model;
5. preserve the exact-daily 174.97% strategy as a dashboard diagnostic.

The run evaluated 40 predeclared candidates: eight fragility-aware overlays and
32 industry-residual variants. It did not authorize promotion or live trading.

## Strongest result

The strongest retrospective candidate was `alpha30_1.35x`. It placed a 30%
residualized accelerator beside the incumbent and used only lagged issuer,
sector, breadth, and volatility information to decide whether that accelerator
was active.

| Metric | Result |
| --- | ---: |
| Trailing-52-week CAGR | 186.90% |
| Trailing-52-week Sharpe | 3.206 |
| Trailing-52-week maximum drawdown | -15.06% |
| Full-period CAGR | 51.68% |
| Full-period Sharpe | 1.704 |
| Full-period maximum drawdown | -24.99% |
| CAGR at 200 bps costs | 142.28% |
| Worst delayed-execution CAGR | 159.63% |
| Worst five-issuer-removal CAGR | 162.32% |
| Rolling 26-week outperformance share | 47.02% |
| Raw block-bootstrap probability | 99.32% |
| Familywise-adjusted bootstrap probability | 83.68% |

The candidate therefore failed the frozen 60% rolling-consistency gate and the
95% familywise-adjusted probability gate. It is a high-value research lead, not
a replacement strategy. Its 186.90% figure is retrospective and was selected
from a 40-candidate tournament.

The stricter fragility guards produced lower returns but better temporal
consistency. For example, `alpha30_1.35x_strict` returned 161.90% with 77.38%
rolling outperformance, but its familywise-adjusted probability was only
47.68%. No candidate passed every historical gate.

## Exposure and financing map

The unchanged incumbent produced the following common-endpoint results:

| Exposure | Financing | CAGR | Sharpe | Maximum drawdown |
| ---: | ---: | ---: | ---: | ---: |
| 1.25x | 8% | 149.01% | 3.096 | -13.95% |
| 1.25x | 12% | 146.58% | 3.064 | -14.05% |
| 1.30x | 8% | 156.89% | 3.086 | -14.50% |
| 1.30x | 12% | 153.87% | 3.049 | -14.62% |
| 1.35x | 8% | 164.97% | 3.077 | -15.06% |
| 1.35x | 12% | 161.35% | 3.036 | -15.20% |

This map shows that extra exposure raised recent return in the observed year,
but it did not add independent alpha. Higher financing reduced CAGR, and the
same exposure would magnify future losses if the source signal failed.

## Independent industry-residual branch

The new family ranked stocks after removing their lagged industry exposure and
combined residual momentum with point-in-time SEC quality acceleration and
event information. The best levered member,
`ir13_reversal50_s4_n2__1.25x`, returned 71.20% with 2.506 Sharpe and -7.37%
drawdown. Its return collapsed under the five-issuer test, so this branch is
rejected. The lower drawdown is useful evidence, but it does not compensate for
the return gap and concentration dependence.

## Validation boundary

Primary paths, cost stresses, the industry family, causal guards, and bootstrap
tests were directly simulated. Recomputing all archived stock-level sector
paths for every delay and five-issuer permutation was impractically slow in the
cloud-synced workspace. Those two sector-reference stresses therefore use
conservative trailing-52-week proxies calibrated to the already audited source
strategy floors. They are not represented as fresh exact stock-level
reconstructions. The prior exact-daily 174.97% reference remains separately
sealed and hash-verified.

## Decision

- Keep `alpha30_1.35x` as the leading fragile research candidate.
- Do not replace the incumbent, promote the candidate, or enable execution.
- Reject the industry-residual branch in its present form.
- Keep the exact-daily 174.97% path visible in the dashboard with an explicit
  failed-robustness label.
- Require untouched forward weeks before reconsidering either amplified path.

Evidence is stored in `evidence/sec_fragility_industry_tournament_v1/`.

