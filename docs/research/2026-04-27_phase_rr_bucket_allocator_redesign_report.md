# Phase RR - Bucket Allocator Redesign

## Commands Executed
- `python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_rr_bucket_allocator_redesign.py`
- `python3 -u scripts/phase_rr_bucket_allocator_redesign.py`
- `python3 scripts/research_committee_report.py improved_phaserr_combined_bucket_allocator --quick`

## Files Created / Modified
- Created `scripts/phase_rr_bucket_allocator_redesign.py`
- Modified `scripts/build_improvement_artifacts.py`
- Created diagnostics in `data/research/phase_rr_bucket_allocator/`
- Created candidate summaries in `data/05_layer3_portfolio_construction/phase_rr_*.csv`
- Created version artifacts for:
  - `improved_phaserr_good_state_bucket_participation`
  - `improved_phaserr_recovery_bucket_repair`
  - `improved_phaserr_combined_bucket_allocator`
- Created committee report:
  - `reports/research_committee/improved_phaserr_combined_bucket_allocator_audit.md`

## Sleeve Bucket Classification
- `offense`: `dual_momentum_topn`, `cta_trend_long_only`, `composite_selective_signals`
- `defense`: `taa_10m_sma`
- `composite`: `composite_regime_conditioned`
- `cash`: `cash::BIL`

Evidence from the live production stack supported this split:
- `composite_regime_conditioned` carried the highest average sleeve weight at `25.43%` and remained the main hidden-cash sleeve.
- `taa_10m_sma` helped in `calm_trend`, `neutral_healthy_proxy`, `neutral_mixed`, and `recovery_fragile`, but hurt in `stressed_panic`.
- `composite_selective_signals` remained the clearest recovery-confirmed offender, with negative state Sharpe there.

## Current Bucket Exposure By State
- `calm_trend`: offense `48.61%`, defense `16.95%`, composite `31.10%`, bucket cash `3.35%`, ETF BIL `6.85%`
- `neutral_healthy_proxy`: offense `42.54%`, defense `15.05%`, composite `27.48%`, bucket cash `14.92%`, ETF BIL `21.31%`
- `recovery_confirmed`: offense `42.72%`, defense `17.79%`, composite `33.11%`, bucket cash `6.38%`, ETF BIL `12.57%`
- `recovery_fragile`: offense `45.84%`, defense `13.91%`, composite `27.90%`, bucket cash `12.35%`, ETF BIL `21.82%`
- `stressed_panic`: offense `24.19%`, defense `7.62%`, composite `17.26%`, bucket cash `50.93%`, ETF BIL `60.74%`

## Main Bucket Bottlenecks
- `calm_trend`: production still trails SPY badly even with low bucket cash; the problem is sleeve mix quality and composite drag, not just top-level overlay cash.
- `neutral_healthy_proxy`: production still carries too much composite plus hidden sleeve cash while SPY/offense participation remains modest.
- `recovery_confirmed`: too much weight stays in `composite_regime_conditioned` and `composite_selective_signals` instead of the stronger recovery sleeves.
- `recovery_fragile`: rerisking improves, but composite/cash drag is still too high during the handoff.
- `stressed_panic`: current cash/defense posture still looks like the right guardrail and should not be loosened casually.

## Candidates Tested
- `improved_phaserr_good_state_bucket_participation`
- `improved_phaserr_recovery_bucket_repair`
- `improved_phaserr_combined_bucket_allocator`

All three kept:
- production `phase2b_mode=regime_confidence_boost`
- production overlay path `lighter_both_targeted_narrow_plus_confirmed`
- stressed-panic protection unchanged

The redesign acted at the sleeve-allocation layer:
- move a bounded amount of weight out of the composite bucket in the target states
- rebalance offense toward the empirically stronger sleeves within that state
- avoid a blunt SPY-only beta add

## Candidate Metrics Table
| Candidate | Ann Return | Sharpe | Max DD | CVaR 5% | Turnover | Avg BIL | Avg SPY | Avg Offense | Avg Defense |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| production | 6.9737% | 0.8953 | -13.98% | -2.6181% | 5.62% | 28.39% | 7.08% | 47.50% | 24.11% |
| QQ best reference | 7.0493% | 0.8989 | -14.01% | -2.6376% | 5.76% | 27.68% | 7.14% | 47.81% | 24.51% |
| RR1 good-state bucket | 6.9833% | 0.8909 | -14.32% | -2.6425% | 5.56% | 28.10% | 7.18% | 47.73% | 24.17% |
| RR2 recovery bucket | 7.0116% | 0.8936 | -14.08% | -2.6376% | 5.72% | 28.22% | 7.21% | 47.88% | 23.90% |
| RR3 combined bucket | 7.0686% | 0.8949 | -14.38% | -2.6575% | 5.65% | 27.84% | 7.34% | 48.15% | 24.01% |

## State-By-State Impact
Best candidate: `improved_phaserr_combined_bucket_allocator`

vs production:
- `calm_trend`: ann return `-0.04pp`, Sharpe `-0.006`
- `neutral_healthy_proxy`: ann return `+0.18pp`, Sharpe `-0.004`
- `neutral_mixed`: ann return `+0.13pp`, Sharpe `+0.006`
- `recovery_confirmed`: ann return `+0.34pp`, Sharpe `+0.032`
- `recovery_fragile`: ann return `+0.62pp`, Sharpe `+0.088`
- `stressed_panic`: ann return `-0.03pp`, Sharpe `-0.016`

Interpretation:
- RR did solve the intended state bottlenecks directionally.
- The combined candidate was strongest where the audit said it should be strongest: `recovery_confirmed` and `recovery_fragile`.
- The redesign gave back too much in `calm_trend` and `stressed_panic`, so the whole-portfolio Sharpe still failed to improve.

## Hidden Beta / Hidden Cash Check
- RR3 reduced average BIL by `0.55pp` vs production.
- RR3 increased average SPY by only `0.26pp` vs production.
- RR3 increased average offense by `0.65pp` vs production.
- RR3 reduced average composite-bucket sleeve weight by `2.93pp`.

Conclusion:
- The RR lift was not just a hidden SPY/beta bump.
- The redesign truly shifted sleeve architecture away from the composite bucket and into offense.
- That shift was still not efficient enough on a full risk-adjusted basis.

## Best Candidate
- `improved_phaserr_combined_bucket_allocator`

Why it won internally:
- best annual return of the RR set: `7.0686%`
- strongest bottleneck-state repair
- smallest gap vs the QQ best reference on return

Why it still failed the RR quick screen:
- Sharpe delta vs production was `-0.0003`, below the required `+0.005`
- max drawdown worsened by `0.40pp`
- CVaR worsened by `0.039pp`

## Quick Committee Verdict
- Verdict from `reports/research_committee/improved_phaserr_combined_bucket_allocator_audit.md`:
  - `KEEP AS SHADOW (research reference)`

Committee interpretation:
- competitive enough to keep as research
- not strong enough to challenge production
- production pin unchanged
- shadow pin unchanged

## Layer 5/6 Status
- Skipped quick Layer 5/6 follow-ups.

Reason:
- RR did not clear its own Sharpe gate.
- The candidate improved the intended states but did not provide a clearly better whole-portfolio risk-adjusted result.
- This did not look like a serious promotion finalist.

## Final Decision
**KEEP AS SHADOW**

- Production pin remains `improved_phase2b_regime_confidence_boost`
- Shadow pin remains `improved_phase2b_combo_abc`
- No automatic promotion

## Should Bucket Allocator Redesign Continue?
Yes, but not in this exact soft-tilt form.

What RR established:
- the broader bucket frontier is directionally correct
- explicit recovery bucket repair helped more than the narrow MM-QQ cash heuristics
- the project bottleneck really has moved up to sleeve-architecture / allocator design

What RR did not establish:
- a bounded tilt-on-top-of-HRP bucket redesign is enough to produce a clear Sharpe win

## Recommended Next Phase If RR Fails
Move to a more explicit allocator architecture rather than another narrow heuristic:
- test an in-allocator dual-bucket or multi-bucket structure with explicit state-conditioned bucket budgets and tighter composite ceilings
- keep stressed-panic cash/defense rules hard
- stop iterating on tiny sleeve-internal cash tweaks as the main frontier
