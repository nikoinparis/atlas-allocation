# Phase SS - Explicit Bucket Allocator

## Commands Executed
- `python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_ss_explicit_bucket_allocator.py`
- `python3 -u scripts/phase_ss_explicit_bucket_allocator.py`
- `python3 scripts/research_committee_report.py improved_phasess_recovery_explicit_bucket --quick`
- `python3 scripts/backtest_realism_audit.py improved_phasess_recovery_explicit_bucket --quick`
- `python3 scripts/allocator_benchmark_audit.py improved_phasess_recovery_explicit_bucket --quick`

## Files Created / Modified
- Created `scripts/phase_ss_explicit_bucket_allocator.py`
- Modified `scripts/build_improvement_artifacts.py`
- Created diagnostics in `data/research/phase_ss_explicit_bucket_allocator/`
- Created candidate summaries in `data/05_layer3_portfolio_construction/phase_ss_*.csv`
- Created committee / realism / allocator-benchmark reports for `improved_phasess_recovery_explicit_bucket`
- Updated `docs/research/project_journey.md`

## Current Bucket Weights By State
- `calm_trend`: offense `48.61%`, defense `16.95%`, composite `31.10%`, cash `3.35%`
- `neutral_healthy_proxy`: offense `42.54%`, defense `15.05%`, composite `27.48%`, cash `14.92%`
- `neutral_mixed`: offense `34.55%`, defense `11.15%`, composite `21.13%`, cash `33.17%`
- `recovery_confirmed`: offense `42.72%`, defense `17.79%`, composite `33.11%`, cash `6.38%`
- `recovery_fragile`: offense `45.84%`, defense `13.91%`, composite `27.90%`, cash `12.35%`
- `stressed_panic`: offense `24.19%`, defense `7.62%`, composite `17.26%`, cash `50.93%`

## Target Bucket Budget Table
This phase moved from soft tilts to explicit state-conditioned bucket budgets applied before final sleeve allocation.

- `calm_trend`: offense `56%`, defense `19%`, composite max `25%`, cash floor `5%`
- `neutral_healthy_proxy`: offense `50%`, defense `18%`, composite max `23%`, cash floor `9%`
- `recovery_confirmed`: offense `51%`, defense `20%`, composite max `24%`, cash floor `7%`
- `recovery_fragile`: offense `47%`, defense `19%`, composite max `23%`, cash floor `11%`
- `stressed_panic`: offense `24%`, defense `8%`, composite `17%`, cash `51%`

Design rules:
- preserve stressed-panic defense/cash posture
- reduce composite drag in good and recovery states
- reallocate within existing sleeve buckets using production-style proportions where possible
- avoid direct SPY injection outside existing sleeves

## Bucket Gaps By State
Largest production gaps versus the explicit target budgets:

- `calm_trend`: offense `-7.39pp`, composite `+6.10pp`
- `neutral_healthy_proxy`: offense `-7.46pp`, composite `+4.48pp`, cash `+5.92pp`
- `recovery_confirmed`: offense `-8.28pp`, composite `+9.11pp`
- `recovery_fragile`: defense `-5.09pp`, composite `+4.90pp`, cash `+1.35pp`
- `stressed_panic`: already close to target; no reason to loosen casually

Interpretation:
- the main problem was still too much composite weight in favorable and recovery states
- neutral-healthy also carried too much cash relative to the target posture
- stressed-panic looked like a guardrail state, not a participation state

## Candidates Tested
- `improved_phasess_recovery_explicit_bucket`
- `improved_phasess_good_state_explicit_bucket`
- `improved_phasess_combined_explicit_bucket`

Candidate logic:
- SS1 applied hard bucket budgets only in `recovery_confirmed` and `recovery_fragile`
- SS2 applied hard bucket budgets only in `calm_trend` and `neutral_healthy_proxy`
- SS3 combined the safe recovery + good-state budget logic with the same stressed-panic guardrail

All three kept:
- production `phase2b_mode=regime_confidence_boost`
- existing production pipeline and ETF construction path
- no Phase CC `refined_state`
- no `defensive_overlay_hint`

## Candidate Metrics Table
| Candidate | Ann Return | Sharpe | Max DD | CVaR 5% | Turnover | Avg BIL | Avg SPY | Avg Offense | Avg Defense |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| production | 6.9737% | 0.8953 | -13.98% | -2.6181% | 5.62% | 28.39% | 7.08% | 47.50% | 24.11% |
| RR best reference | 7.0686% | 0.8949 | -14.38% | -2.6575% | 5.65% | 27.84% | 7.34% | 48.15% | 24.01% |
| SS1 recovery explicit bucket | 7.0585% | 0.8977 | -14.08% | -2.6434% | 5.74% | 28.13% | 7.28% | 47.99% | 23.88% |
| SS2 good-state explicit bucket | 7.0189% | 0.8851 | -14.52% | -2.6638% | 5.66% | 27.77% | 7.49% | 50.22% | 23.58% |
| SS3 combined explicit bucket | 7.1187% | 0.8926 | -15.32% | -2.6769% | 5.58% | 27.63% | 7.66% | 48.38% | 23.99% |

## State-By-State Impact
Best candidate: `improved_phasess_recovery_explicit_bucket`

vs production:
- `calm_trend`: ann return `-0.07pp`, Sharpe `-0.010`
- `neutral_healthy_proxy`: ann return `+0.21pp`, Sharpe `+0.011`
- `recovery_confirmed`: ann return `+0.48pp`, Sharpe `+0.052`
- `recovery_fragile`: ann return `+0.72pp`, Sharpe `+0.120`
- `stressed_panic`: ann return `-0.01pp`, Sharpe `-0.004`

Interpretation:
- SS1 clearly improved the intended bottleneck states
- unlike RR, SS1 also improved full-window Sharpe versus production
- the main giveback was still a small calm-trend softness
- stressed-panic remained essentially intact

## Hidden Beta / Hidden Cash Check
For `improved_phasess_recovery_explicit_bucket` vs production:
- avg BIL changed from `28.39%` to `28.13%` (`-0.26pp`)
- avg SPY changed from `7.08%` to `7.28%` (`+0.20pp`)
- avg offense changed from `47.50%` to `47.99%` (`+0.49pp`)
- avg bucket composite changed from `25.43%` to `24.29%` (`-1.14pp`)

Conclusion:
- the lift was not just a hidden beta add
- the architecture genuinely shifted weight away from the composite bucket
- the candidate did not need a large SPY increase to improve recovery behavior

## Stressed-Panic Protection Check
- state budget preserved stressed-panic production-like cash/defense
- state ann return delta vs production: `-0.01pp`
- state Sharpe delta vs production: `-0.004`
- avg state BIL remained effectively unchanged at about `60.76%`

Conclusion:
- stressed-panic guardrails were preserved well enough for a research-quality continuation

## Recovery-Fragile Protection Check
- state ann return improved by `+0.72pp`
- state Sharpe improved by `+0.120`
- avg state SPY rose only modestly from `6.23%` to `6.83%`
- avg state BIL remained near production at about `21.80%`

Conclusion:
- the recovery-specific architecture worked where it was supposed to work
- the improvement was not just a blunt risk-on swing

## Best Candidate
- `improved_phasess_recovery_explicit_bucket`

Why it won internally:
- best Sharpe of the SS set: `0.8977`
- best balance between recovery repair and stressed-panic preservation
- better whole-portfolio risk-adjusted result than RR

Why it still failed the strict screen:
- Sharpe delta vs production was only `+0.0024`, below the required `+0.005`

## Quick Committee Verdict
- `KEEP AS SHADOW (research reference)`

Committee interpretation:
- candidate is competitive and clearly useful as a research reference
- candidate improved return and holdout Sharpe without obvious hidden-beta abuse
- candidate still does not challenge production strongly enough for promotion

## Layer 5/6 Status
Quick Layer 5/6 audits ran because the committee verdict was `KEEP AS SHADOW` and the portfolio improvement was genuine.

Realism:
- doubled-cost scenario still showed positive ann-return delta
- 1-week rebalance delay still showed positive ann-return delta
- verdict: candidate survives doubled-cost scenario

Allocator benchmark:
- candidate beat production on annual return and Sharpe
- candidate beat equal-weight and inverse-vol on both return and Sharpe
- candidate still did not clearly beat the best simple internal HRP baseline on Sharpe
- verdict: extra complexity is still `NO / MARGINAL` for production promotion

## Final Decision
**KEEP AS SHADOW**

- Production pin remains `improved_phase2b_regime_confidence_boost`
- Shadow pin remains `improved_phase2b_combo_abc`
- No automatic promotion

## Should Explicit Bucket Architecture Continue?
Yes.

What Phase SS established:
- explicit bucket budgets are stronger than the soft RR tilt architecture
- recovery-state budget control is a real improvement lever
- the project bottleneck has moved to true allocator architecture, not small sleeve cash heuristics

What Phase SS did not establish:
- this first explicit-bucket implementation is enough to clear the promotion bar
- the current downstream overlay / ETF translation stack is neutral enough to fully preserve the bucket gains

## Recommended Next Phase If SS Fails
Move to a stricter in-allocator bucket design:
- a true two-stage allocator with explicit risky-budget vs cash-budget coordination
- harder state-conditioned composite ceilings
- explicit bucket-level coordination with downstream overlay cash so the bucket gains are not partially absorbed later

In other words:
- keep working on the bucket-allocator frontier
- stop going back to narrow `composite_regime_conditioned` cash-tier tweaks as the main path
