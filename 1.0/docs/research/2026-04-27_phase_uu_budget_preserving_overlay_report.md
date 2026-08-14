# Phase UU — Budget-Preserving Overlay Redesign

## 1. Commands executed

```bash
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_uu_budget_preserving_overlay.py
python3 -u scripts/phase_uu_budget_preserving_overlay.py
python3 scripts/research_committee_report.py improved_phaseuu_tt1_budget_aware_lighter_both --quick
python3 scripts/backtest_realism_audit.py improved_phaseuu_tt1_budget_aware_lighter_both --quick
python3 scripts/allocator_benchmark_audit.py improved_phaseuu_tt1_budget_aware_lighter_both --quick
```

## 2. Files created / modified

- Modified: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/build_improvement_artifacts.py)
- Created: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_uu_budget_preserving_overlay.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/phase_uu_budget_preserving_overlay.py)
- Updated journey log: [/Users/nicholasturangan/Documents/Portfolio Optimizer/docs/research/project_journey.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/project_journey.md)

Primary Phase UU outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_overlay_absorption_by_state.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_overlay_absorption_by_state.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_overlay_branch_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_overlay_branch_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_tt1_vs_production_absorption.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_tt1_vs_production_absorption.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_candidate_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_uu_budget_preserving_overlay/phase_uu_candidate_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_uu_candidate_metrics_full.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_uu_candidate_metrics_full.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_uu_state_summary.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_uu_state_summary.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_uu_selection_table.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_uu_selection_table.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_uu_protocol.json](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_uu_protocol.json)

Quick audit outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phaseuu_tt1_budget_aware_lighter_both_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phaseuu_tt1_budget_aware_lighter_both_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phaseuu_tt1_budget_aware_lighter_both_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phaseuu_tt1_budget_aware_lighter_both_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phaseuu_tt1_budget_aware_lighter_both_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phaseuu_tt1_budget_aware_lighter_both_allocator_benchmark.md)

## 3. Overlay absorption diagnosis

Phase TT had already shown that upstream bucket architecture was working, but the downstream overlay stage was still reclaiming risky budget in recovery states. Phase UU tested whether a recovery-aware overlay redesign could preserve TT1's upstream budget decision.

The diagnosis remained consistent:

- The main recovery-state overlay cash source was still `lighter_both_regime_relief`.
- `target_vol` was not the dominant driver in the targeted recovery states.
- The overlay stage, not the HRP or state-tilt stage, remained the place where recovery-state risky budget was being partially clawed back.

For the best UU candidate (`improved_phaseuu_tt1_budget_aware_lighter_both`):

- `recovery_confirmed`
  - stage-1 risky budget: `100.00%`
  - post-overlay risky budget: `93.77%`
  - final ETF risky budget: `89.45%`
  - overlay cash added: `6.23%`
  - overlay absorption reduction vs production: `+0.15pp`
  - total absorption reduction vs production: `+2.02pp`
- `recovery_fragile`
  - stage-1 risky budget: `100.00%`
  - post-overlay risky budget: `87.31%`
  - final ETF risky budget: `78.47%`
  - overlay cash added: `12.69%`
  - overlay absorption reduction vs production: `-0.34pp`
  - total absorption reduction vs production: `+0.29pp`

Interpretation: UU improved total downstream absorption mostly through later-stage effects, but it did not solve the actual overlay-stage clawback problem. That is why the quick screen still rejected all three candidates even though the best one improved return and Sharpe.

## 4. Which overlay branch re-adds cash

The branch diagnostics were clear:

- In `recovery_confirmed`, `recovery_fragile`, `neutral_healthy_proxy`, and `neutral_mixed`, the inferred cash source remained `lighter_both_regime_relief`.
- `stressed_panic` also used the same family, but that behavior still looked appropriate as a guardrail and was left untouched.
- There was no evidence that `target_vol` binding was the main blocker in the recovery states Phase UU targeted.

So the practical conclusion is that the next redesign should go directly at the recovery-state `lighter_both` / regime-relief cash architecture, rather than continuing to tweak upstream budgets and hoping the overlay path will respect them.

## 5. Candidate metrics table

| Candidate | Full ann return | Full Sharpe | Max DD | CVaR 5% | Avg turnover | Avg BIL | Avg SPY | Delta ann vs prod | Delta Sharpe vs prod | Delta Sharpe vs TT1 | Quick screen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `improved_phaseuu_tt1_overlay_preserved_recovery` | 7.0637% | 0.8994 | -14.08% | -2.64% | 5.77% | 28.34% | 7.31% | +0.09pp | +0.0041 | +0.0001 | Reject |
| `improved_phaseuu_recovery_overlay_cash_cap` | 7.0617% | 0.8993 | -14.08% | -2.64% | 5.77% | 28.36% | 7.31% | +0.09pp | +0.0040 | -0.0000 | Reject |
| `improved_phaseuu_tt1_budget_aware_lighter_both` | 7.0647% | 0.8994 | -14.08% | -2.64% | 5.77% | 28.33% | 7.31% | +0.09pp | +0.0041 | +0.0001 | Reject |

Why all three were rejected:

- Sharpe improvement vs production stayed below the required `+0.005`.
- Overlay absorption was not reduced on average across the targeted recovery states.
- UU2 also failed the stricter "Sharpe must improve vs TT1" check.

## 6. State-by-state impact

Best candidate: `improved_phaseuu_tt1_budget_aware_lighter_both`

- `recovery_confirmed`: annual return delta vs production `+0.60pp`, Sharpe delta `+0.0668`
- `recovery_fragile`: annual return delta vs production `+0.90pp`, Sharpe delta `+0.1413`
- `neutral_healthy_proxy`: annual return delta vs production `+0.22pp`, Sharpe delta `+0.0175`
- `calm_trend`: annual return delta vs production `-0.07pp`, Sharpe delta `-0.0103`
- `stressed_panic`: annual return delta vs production `-0.04pp`, Sharpe delta `-0.0093`

Relative to TT1, the best UU candidate was only a small incremental lift:

- full annual return delta vs TT1: `+0.00pp`
- full Sharpe delta vs TT1: `+0.0001`
- `recovery_confirmed` improved a bit more
- `recovery_fragile` improved a bit more
- `stressed_panic` stayed effectively unchanged

## 7. Overlay absorption reduction by state

For `improved_phaseuu_tt1_budget_aware_lighter_both`:

- vs production
  - `recovery_confirmed`: `+0.15pp`
  - `recovery_fragile`: `-0.34pp`
  - targeted mean: `-0.09pp`
- vs TT1
  - `recovery_confirmed`: `+0.30pp`
  - `recovery_fragile`: `+0.06pp`
  - targeted mean: `+0.18pp`

This is the key Phase UU result.

UU did improve overlay absorption relative to TT1, but TT1 itself was already worse than production on the targeted overlay-stage measure. So UU helped the challenger, but still did not beat the production overlay behavior on the stage the phase was explicitly trying to fix.

## 8. TT1 comparison

Compared with `improved_phasett_recovery_two_stage_bucket`, the best UU candidate:

- annual return: `7.0647%` vs `7.0621%`
- Sharpe: `0.8994` vs `0.8993`
- avg BIL: `28.33%` vs `28.36%`
- avg SPY: `7.31%` vs `7.31%`
- composite bucket delta vs production: `-1.49pp` vs `-1.50pp`
- offense bucket delta vs production: `+0.65pp` vs `+0.63pp`

So the Phase UU redesign was real, but very small. It mainly refined TT1 rather than opening a new performance regime.

## 9. Hidden beta / hidden cash check

The best UU candidate did not look like a hidden-beta hack.

- avg SPY only rose from production by `+0.23pp`
- avg BIL fell by only `-0.07pp`
- avg offense rose by `+0.43pp`
- avg composite bucket fell by `-1.49pp`

The gain profile came from slightly better recovery-state participation and slightly less composite drag, not from a large unreported beta jump.

## 10. Stressed-panic protection check

Stressed behavior stayed broadly intact:

- stressed-panic annual return delta vs production: `-0.04pp`
- stressed-panic Sharpe delta vs production: `-0.0093`
- avg BIL in stressed-panic stayed about `60.78%`, very close to production

This passes the qualitative guardrail. Phase UU did not break the panic-defense engine.

## 11. Recovery-fragile protection check

Recovery-fragile still improved meaningfully:

- annual return delta vs production: `+0.90pp`
- Sharpe delta vs production: `+0.1413`
- avg BIL fell from `21.82%` in production to `21.53%`
- avg SPY rose from `6.23%` to `7.29%`

So the recovery-fragile state itself benefited. The failure was specifically that the overlay-stage absorption metric did not improve enough versus production.

## 12. Best candidate

Best candidate: `improved_phaseuu_tt1_budget_aware_lighter_both`

Why it won the UU set:

- best full annual return
- best full Sharpe
- slightly best Sharpe delta vs TT1
- slightly lower BIL than the other UU variants
- best total recovery-state profile overall

Why it still did not clear the bar:

- Sharpe delta vs production was `+0.0041`, below the required `+0.005`
- targeted overlay absorption reduction vs production was `-0.09pp`

## 13. Quick committee verdict

Research committee verdict:

- `KEEP AS SHADOW (research reference)`

Reference:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phaseuu_tt1_budget_aware_lighter_both_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phaseuu_tt1_budget_aware_lighter_both_audit.md)

Committee interpretation:

- holdout behavior was good
- risk caps were fine
- the candidate remained competitive enough to keep as a research reference
- but it still did not pass the stronger promotion bar

## 14. Whether Layer 5/6 quick audits ran

They ran.

Layer 5 realism:

- verdict: `candidate survives doubled-cost scenario`
- the small edge persisted under doubled half-spread and 1-week rebalance delay

Layer 6 allocator benchmark:

- verdict: extra complexity still looked `NO / MARGINAL`
- candidate beat production on annual return and Sharpe
- but it did not clearly beat the best simple internal benchmark (`hrp_internal`) on Sharpe

References:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phaseuu_tt1_budget_aware_lighter_both_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phaseuu_tt1_budget_aware_lighter_both_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phaseuu_tt1_budget_aware_lighter_both_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phaseuu_tt1_budget_aware_lighter_both_allocator_benchmark.md)

## 15. Final decision

**KEEP AS SHADOW**

- Production pin remains `improved_phase2b_regime_confidence_boost`
- Shadow pin remains `improved_phase2b_combo_abc`
- No automatic promotion

## 16. Whether budget-preserving overlay redesign should continue

Yes, but not in this narrow form.

Phase UU exhausted the simple recovery-state cash-cap / lighter-both-preservation variants that could be tested without a larger architectural change. The evidence now says:

- upstream risky-budget design is good enough to matter
- small overlay tweaks can preserve a little more of it
- but the downstream overlay path is still structurally separate enough that small caps and buffers are not enough

So this path should continue only as a **broader overlay-architecture redesign**, not as another small threshold patch.

## 17. Recommended next phase if this fails

Move to a direct overlay-architecture redesign inside `apply_overlays_custom`.

The next phase should make the overlay explicitly aware of the upstream risky/cash budget as a first-class constraint, especially in `recovery_confirmed` and `recovery_fragile`, rather than allowing `lighter_both_regime_relief` to behave like an almost-independent cash-creation layer after the allocator has already made a state-conditioned recovery budget decision.
