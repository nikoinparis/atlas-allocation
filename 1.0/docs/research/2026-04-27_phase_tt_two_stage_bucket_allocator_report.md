# Phase TT - Two-Stage Bucket Allocator

## Commands Executed
- `python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_tt_two_stage_bucket_allocator.py`
- `python3 -u scripts/phase_tt_two_stage_bucket_allocator.py`
- `python3 scripts/research_committee_report.py improved_phasett_recovery_two_stage_bucket --quick`
- `python3 scripts/backtest_realism_audit.py improved_phasett_recovery_two_stage_bucket --quick`
- `python3 scripts/allocator_benchmark_audit.py improved_phasett_recovery_two_stage_bucket --quick`

## Files Created / Modified
- Created `scripts/phase_tt_two_stage_bucket_allocator.py`
- Modified `scripts/build_improvement_artifacts.py`
- Created diagnostics in `data/research/phase_tt_two_stage_bucket_allocator/`
- Created candidate summaries in `data/05_layer3_portfolio_construction/phase_tt_*.csv`
- Created TT checkpoint tables in `data/research/allocator_checkpoints/` for all 3 TT candidates
- Created committee / realism / allocator-benchmark reports for `improved_phasett_recovery_two_stage_bucket`
- Updated `docs/research/project_journey.md`

## Current Risky / Cash Budget By State
Production baseline from the saved checkpoints:

- `calm_trend`: Stage-1 risky `97.29%`, post-overlay risky `96.65%`, final ETF risky `93.15%`
- `neutral_healthy_proxy`: Stage-1 risky `89.08%`, post-overlay risky `85.08%`, final ETF risky `78.69%`
- `neutral_mixed`: Stage-1 risky `82.50%`, post-overlay risky `66.83%`, final ETF risky `61.40%`
- `recovery_confirmed`: Stage-1 risky `100.00%`, post-overlay risky `93.62%`, final ETF risky `87.43%`
- `recovery_fragile`: Stage-1 risky `100.00%`, post-overlay risky `87.65%`, final ETF risky `78.18%`
- `stressed_panic`: Stage-1 risky `99.13%`, post-overlay risky `49.07%`, final ETF risky `39.26%`

Interpretation:
- the recovery states really are the cleanest Stage-1 opportunity because they begin at full risky sleeve budget
- the biggest downstream budget loss still arrives after the overlay step and then again after ETF lookthrough
- `stressed_panic` remains a hard guardrail state and should stay that way

## Post-Overlay Budget Absorption
Production absorption by state:

- `recovery_confirmed`: overlay absorption `6.38pp`, lookthrough absorption `6.18pp`, total absorption `12.57pp`
- `recovery_fragile`: overlay absorption `12.35pp`, lookthrough absorption `9.47pp`, total absorption `21.82pp`
- `neutral_healthy_proxy`: overlay absorption `4.00pp`, lookthrough absorption `6.38pp`, total absorption `10.39pp`

What TT changed:
- TT1 and TT3 improved **total** absorption in the targeted recovery states mainly by reducing lookthrough loss
- but they did **not** reduce **overlay-stage** absorption versus production
- TT1 targeted-state mean overlay-absorption reduction vs production: `-0.27pp`
- TT1 targeted-state mean total-absorption reduction vs production: `+0.99pp`

That is the key Phase TT finding:
- the stricter two-stage architecture helped final participation somewhat
- but the overlay path still reclaimed at least as much risky budget as before in the targeted recovery states

## Candidate Metrics Table
| Candidate | Ann Return | Sharpe | Max DD | CVaR 5% | Turnover | Avg BIL | Avg SPY | Avg Offense | Avg Defense |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| production | 6.9737% | 0.8953 | -13.98% | -2.6181% | 5.62% | 28.39% | 7.08% | 47.50% | 24.11% |
| SS1 reference | 7.0585% | 0.8977 | -14.08% | -2.6434% | 5.74% | 28.13% | 7.28% | 47.99% | 23.88% |
| TT1 recovery two-stage | 7.0621% | 0.8993 | -14.08% | -2.6355% | 5.77% | 28.36% | 7.31% | 47.91% | 23.73% |
| TT2 recovery + neutral two-stage | 7.1359% | 0.8975 | -14.08% | -2.6725% | 5.75% | 27.76% | 7.58% | 48.55% | 23.69% |
| TT3 SS1 + overlay coordinated | 7.0223% | 0.8966 | -14.08% | -2.6317% | 5.74% | 28.42% | 7.24% | 47.77% | 23.80% |

## State-By-State Impact
Best candidate: `improved_phasett_recovery_two_stage_bucket`

vs production:
- `recovery_confirmed`: ann return `+0.59pp`, Sharpe `+0.067`
- `recovery_fragile`: ann return `+0.89pp`, Sharpe `+0.141`
- `neutral_healthy_proxy`: ann return `+0.22pp`, Sharpe `+0.017`
- `calm_trend`: ann return `-0.07pp`, Sharpe `-0.010`
- `stressed_panic`: ann return `-0.04pp`, Sharpe `-0.009`

Interpretation:
- TT1 improved the intended recovery bottleneck states more than SS1
- the tradeoff was still the same small giveback in `calm_trend` plus a tiny additional giveback in `stressed_panic`
- the portfolio-level Sharpe improved to `0.8993`, but not enough to clear the required `+0.005` Sharpe gate

## Downstream Overlay Absorption Reduction
This was the main TT test.

Results:
- TT1 targeted overlay-absorption reduction vs production: `-0.27pp`
- TT2 targeted overlay-absorption reduction vs production: `-0.01pp`
- TT3 targeted overlay-absorption reduction vs production: `-0.24pp`

So all 3 TT candidates failed the strict architectural objective:
- none reduced overlay-stage absorption in the targeted states
- some reduced **total** absorption by helping later lookthrough, but that is not the same thing

This matters because TT was supposed to prove that Stage 1 and the downstream cash path were finally coordinated. The evidence says they were **not** yet coordinated tightly enough.

## Hidden Beta / Hidden Cash Check
For TT1 vs production:
- avg BIL changed from `28.39%` to `28.36%` (`-0.04pp`)
- avg SPY changed from `7.08%` to `7.31%` (`+0.22pp`)
- avg offense changed from `47.50%` to `47.91%` (`+0.41pp`)
- avg composite bucket changed from `25.43%` to `23.93%` (`-1.50pp`)

Conclusion:
- TT1 was not just a hidden-SPY or hidden-beta bump
- it really did move weight away from the composite bucket
- but the overlay-stage cash clawback still prevented that cleaner architecture from fully surviving downstream

## Stressed-Panic Protection Check
- `stressed_panic` ann return delta vs production: `-0.04pp`
- `stressed_panic` Sharpe delta vs production: `-0.009`
- avg state BIL stayed near production at about `60.78%`

Conclusion:
- stressed-panic protection remained broadly intact
- TT did not break the guardrail state, which is important

## Recovery-Fragile Protection Check
- `recovery_fragile` ann return delta vs production: `+0.89pp`
- `recovery_fragile` Sharpe delta vs production: `+0.141`
- final ETF risky budget improved slightly from `78.18%` to `78.42%`

Conclusion:
- the recovery-fragile objective worked
- the problem was not the recovery-state architecture itself
- the problem was that the architecture still did not stop enough overlay-stage cash from being reintroduced

## Best Candidate
- `improved_phasett_recovery_two_stage_bucket`

Why it won internally:
- best full-window Sharpe of the TT set: `0.8993`
- best balance between recovery-state gains and stressed-panic preservation
- best holdout Sharpe of the TT set: `2.0001`

Why it still failed the strict screen:
- Sharpe delta vs production was only `+0.0040`, below the required `+0.005`
- downstream overlay absorption was not reduced in the targeted states

## Quick Committee Verdict
- `KEEP AS SHADOW (research reference)`

Committee interpretation:
- candidate is competitive and genuinely better on several risk-adjusted axes
- candidate improved holdout Sharpe and recovery-state behavior
- candidate still does not challenge production strongly enough for promotion

## Layer 5/6 Status
Quick Layer 5/6 audits ran because the committee verdict was `KEEP AS SHADOW` and the portfolio improvement was real.

Realism:
- doubled-cost scenario still showed positive ann-return delta
- 1-week rebalance delay still showed positive ann-return delta
- verdict: candidate survives doubled-cost scenario

Allocator benchmark:
- candidate beat production on annual return and Sharpe
- candidate beat equal-weight and inverse-vol on both return and Sharpe
- candidate still did not clearly beat the best simple internal HRP baseline on Sharpe
- verdict: extra complexity remains `NO / MARGINAL` for production promotion

## Final Decision
**KEEP AS SHADOW**

- Production pin remains `improved_phase2b_regime_confidence_boost`
- Shadow pin remains `improved_phase2b_combo_abc`
- No automatic promotion

## Should Two-Stage Bucket Architecture Continue?
Yes, but only if the next step modifies the overlay architecture more directly.

What Phase TT established:
- stricter two-stage budgets improved recovery states more than SS
- the broader allocator-architecture frontier is still the right frontier
- simply tightening the upstream bucket design is not enough if the downstream overlay still re-adds comparable cash

What Phase TT did not establish:
- true Stage-1 / Stage-2 / overlay coordination
- a production-ready Sharpe improvement

## Recommended Next Phase If TT Fails
Move to a direct overlay-architecture redesign rather than another upstream bucket reshuffle:
- explicitly replace the incumbent recovery-state overlay cash clawback with a budget-preserving overlay rule
- make the risky-budget decision first-class inside `apply_overlays_custom`, not an after-the-fact floor layered on top of the incumbent regime relief
- keep the TT recovery bucket structure as the upstream reference, but stop expecting upstream sleeve budgets alone to solve the downstream cash re-add problem
