# Phase III — Production Candidate Review for GGG1

Date: 2026-04-27
Author: research stream

## A. Mission

Make a production decision on `improved_phaseggg_confirmed_only_robust_offense`
(GGG1), not another strategy search. Comparator set:

- production pin: `improved_phase2b_regime_confidence_boost`
- official shadow pin: `improved_phase2b_combo_abc`
- primary architecture reference: `improved_phaseggg_confirmed_only_robust_offense`
- secondary architecture reference: `improved_phaseeee_smoothed_near_exclude_dual`

No overlay surgery, hidden BIL tweaks, ML, Phase CC refined-state input, broad
search, or ETF reconstruction was used.

## B. Commands executed

```
python scripts/phase_iii_production_candidate_review.py
python3 scripts/phase_iii_production_candidate_review.py
python3 scripts/research_committee_report.py improved_phaseggg_confirmed_only_robust_offense
python3 scripts/backtest_realism_audit.py improved_phaseggg_confirmed_only_robust_offense
python3 scripts/allocator_benchmark_audit.py improved_phaseggg_confirmed_only_robust_offense
python3 scripts/robustness_simulation_audit.py improved_phaseggg_confirmed_only_robust_offense
```

`python` was not available on PATH; `python3` was used for the successful runs.

## C. Files created / modified

Created:
- `scripts/phase_iii_production_candidate_review.py`
- `data/research/phase_iii_production_candidate_review/phase_iii_final_metric_comparison.csv`
- `data/research/phase_iii_production_candidate_review/phase_iii_state_by_state_comparison.csv`
- `data/research/phase_iii_production_candidate_review/phase_iii_rolling_metric_comparison.csv`
- `data/research/phase_iii_production_candidate_review/phase_iii_cost_delay_sensitivity.csv`
- `data/research/phase_iii_production_candidate_review/phase_iii_exposure_comparison.csv`
- `data/research/phase_iii_production_candidate_review/phase_iii_drawdown_tail_diagnostics.csv`
- `data/research/phase_iii_production_candidate_review/phase_iii_promotion_checklist.csv`
- `data/05_layer3_portfolio_construction/phase_iii_protocol.json`
- `reports/backtest_realism/improved_phaseggg_confirmed_only_robust_offense_simulation_audit.md`
- `data/research/backtest_realism/improved_phaseggg_confirmed_only_robust_offense_block_bootstrap_summary.csv`

Refreshed full audit outputs:
- `reports/research_committee/improved_phaseggg_confirmed_only_robust_offense_audit.md`
- `reports/backtest_realism/improved_phaseggg_confirmed_only_robust_offense_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseggg_confirmed_only_robust_offense_allocator_benchmark.md`

Modified:
- `docs/research/project_journey.md`

## D. Validation Summary

GGG1 passes the Phase III promotion checklist: **18 / 18 checks passed**.

Full-window versus production:

| metric | GGG1 | production | delta |
|---|---:|---:|---:|
| annual return | 7.14% | 6.89% | +0.246pp |
| Sharpe | 0.9366 | 0.8848 | +0.0518 |
| max drawdown | -11.77% | -13.98% | +2.20pp |
| CVaR-5% | -2.54% | -2.62% | +0.08pp |
| holdout annual return | 14.65% | 12.43% | +2.22pp |
| holdout Sharpe | 1.8224 | 1.6249 | +0.1975 |
| avg BIL | 26.66% | 28.39% | -1.73pp |
| avg SPY | 6.03% | 7.08% | -1.06pp |
| turnover ratio | 1.0998x | 1.0000x | under 1.10x cap |

Versus official shadow `improved_phase2b_combo_abc`, GGG1 improves annual
return by +0.280pp, Sharpe by +0.0526, max drawdown by +1.90pp, CVaR by
+0.071pp, holdout Sharpe by +0.1947, and lowers SPY by -1.05pp.

Versus EEE1, GGG1 is essentially a strict refinement: +0.0109pp annual return,
+0.0013 Sharpe, same max drawdown, same CVaR, +0.0026 holdout Sharpe. The only
meaningful change is the intended recovery_confirmed recipe repair.

## E. State-by-State Results

Annual-return deltas versus production:

| state | GGG1 ann return | production ann return | delta |
|---|---:|---:|---:|
| recovery_confirmed | 2.57% | 2.61% | -0.04pp |
| recovery_fragile | 6.67% | 6.97% | -0.31pp |
| stressed_panic | 3.58% | 3.37% | +0.21pp |
| calm_trend | 4.09% | 3.56% | +0.53pp |
| neutral_mixed | 11.21% | 11.04% | +0.17pp |

No state shows unacceptable degradation. The small recovery_fragile deficit is
inherited from EEE1 and not introduced by GGG1; GGG1 versus EEE1 is effectively
flat in that state.

## F. Rolling / Holdout / Concentration

Rolling 156-week summary:
- GGG1 rolling Sharpe mean: 0.8754 vs production 0.8364.
- Rolling Sharpe delta versus production: +0.0390 mean; positive in 63.9% of rolling windows.
- Rolling annual-return delta versus production: +0.1327pp mean.
- Rolling drawdown mean improves by +0.1716pp.

Split metrics:
- train first 60% Sharpe: GGG1 0.8710 vs production 0.8665.
- validation next 20% Sharpe: GGG1 0.7386 vs production 0.6032.
- test last 20% Sharpe: GGG1 1.3768 vs production 1.3078.
- holdout last 156 weeks Sharpe: GGG1 1.8224 vs production 1.6249.

The improvement is stronger in the second half and holdout, but not a single
isolated week effect. Excess return versus production is +4.39% cumulative over
the full window, +7.12% in the second half, and +6.09% in the holdout.

## G. Cost / Delay Robustness

From the full realism audit:

| scenario | GGG1 ann return | production ann return | delta |
|---|---:|---:|---:|
| 5bp baseline | 6.39% | 6.12% | +0.270pp |
| 10bp doubled cost | 6.22% | 5.97% | +0.254pp |
| 1-week rebalance delay | 5.46% | 5.10% | +0.362pp |

Verdict: GGG1 survives doubled-cost and 1-week delay scenarios.

## H. Drawdown / Tail Diagnostics

| metric | GGG1 | production |
|---|---:|---:|
| max drawdown | -11.77% | -13.98% |
| longest drawdown | 78 weeks | 79 weeks |
| time underwater | 71.7% | 73.2% |
| CVaR-5% | -2.54% | -2.62% |
| worst 4w | -12.08% | -14.49% |
| worst 13w | -7.91% | -10.50% |
| worst 26w | -8.06% | -10.56% |

Worst single week is worse for GGG1 (-6.83% vs -5.68%), but multi-week tails,
full CVaR, max drawdown, and drawdown duration improve.

## I. Exposure / Hidden Beta / Turnover / Implementation

GGG1 is not hidden beta:
- avg SPY: 6.03% vs production 7.08% (-1.06pp)
- avg BIL: 26.66% vs production 28.39% (-1.73pp)

Turnover is borderline but within policy:
- GGG1 avg weekly L1 turnover: 0.1236
- production avg weekly L1 turnover: 0.1124
- ratio: 1.0998x, under the 1.10x cap

Implementation is causal and production-pipeline clean. GGG1 uses the saved
production construction pipeline and state-conditional component panels already
validated in Phase GGG. No post-hoc ETF reconstruction was used.

## J. Full Audit Verdicts

Research committee:
- `KEEP AS SHADOW`
- 0 blocking risk flags.
- The committee still applies the internal +0.30pp annual-return production
  gate; GGG1 reaches +0.246pp.

Backtest realism:
- Candidate survives doubled-cost scenario.
- 5bp, 10bp, and 1-week delay deltas remain positive.

Allocator benchmark:
- Candidate beats production on annualised return and Sharpe.
- Candidate clearly beats the best simple baseline on Sharpe.
- Allocator-side bar passed.

Robustness simulation:
- Point estimates beat production: annual return 7.14% vs 6.89%, Sharpe 0.937
  vs 0.885.
- Bootstrap annual-return confidence intervals overlap, so the statistical
  audit does not claim distributional separation.

## K. Optional Polish Candidate

No polish candidate was created. GGG1 already sits at 1.0998x turnover, barely
inside the 1.10x cap. A tiny speed/deadband change could reduce turnover, but it
would risk weakening the exact recovery_confirmed repair Phase III is reviewing.
No obvious safe polish dominated GGG1.

## L. Final Recommendation

**PROMOTE TO PRODUCTION CANDIDATE.**

Reason: GGG1 beats production on Sharpe by a meaningful margin, improves annual
return, max drawdown, CVaR, holdout return, holdout Sharpe, multi-week tail
windows, and allocator benchmark results, survives doubled cost and 1-week
delay, lowers SPY exposure, keeps turnover under the 1.10x cap, has no
unacceptable state degradation, and is production-pipeline clean.

This is not an automatic pin change. Pin changes still require human packaging
and deployment review. The next step should be packaging/deployment review for
GGG1 as a production candidate, not another research phase.
