# Phase VV — First-Class Budget-Aware Overlay Architecture

## 1. Commands executed

```bash
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_vv_budget_aware_overlay_architecture.py
python3 -u scripts/phase_vv_budget_aware_overlay_architecture.py
python3 scripts/research_committee_report.py improved_phasevv_recovery_neutral_budget_aware_overlay --quick
python3 scripts/backtest_realism_audit.py improved_phasevv_recovery_neutral_budget_aware_overlay --quick
python3 scripts/allocator_benchmark_audit.py improved_phasevv_recovery_neutral_budget_aware_overlay --quick
```

## 2. Files created / modified

- Modified: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/build_improvement_artifacts.py)
- Created: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_vv_budget_aware_overlay_architecture.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/phase_vv_budget_aware_overlay_architecture.py)
- Updated journey log: [/Users/nicholasturangan/Documents/Portfolio Optimizer/docs/research/project_journey.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/project_journey.md)

Primary Phase VV outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_overlay_budget_gap_by_state.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_overlay_budget_gap_by_state.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_overlay_branch_budget_gap.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_overlay_branch_budget_gap.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_target_vol_guardrail_cases.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_target_vol_guardrail_cases.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_candidate_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_vv_budget_aware_overlay/phase_vv_candidate_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_vv_candidate_metrics_full.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_vv_candidate_metrics_full.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_vv_state_summary.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_vv_state_summary.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_vv_selection_table.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_vv_selection_table.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_vv_protocol.json](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_vv_protocol.json)

Quick audit outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phasevv_recovery_neutral_budget_aware_overlay_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phasevv_recovery_neutral_budget_aware_overlay_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phasevv_recovery_neutral_budget_aware_overlay_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phasevv_recovery_neutral_budget_aware_overlay_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phasevv_recovery_neutral_budget_aware_overlay_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phasevv_recovery_neutral_budget_aware_overlay_allocator_benchmark.md)

## 3. Overlay budget gap diagnosis

Phase VV changed the overlay architecture one level deeper than UU. The core change was that recovery-state budget preservation no longer clipped itself against `target_vol_multiplier` unless target-vol was the true active binding source. That was the main structural change Phase UU still lacked.

This did improve the **budget-gap** problem:

- `recovery_confirmed`
  - TT1 intended cash `6.00%`, post-overlay cash `6.53%`, gap `+0.53pp`
  - UU-best intended cash `5.20%`, post-overlay cash `6.23%`, gap `+1.03pp`
  - VV-best intended cash `6.00%`, post-overlay cash `6.37%`, gap `+0.37pp`
- `recovery_fragile`
  - TT1 intended cash `10.00%`, post-overlay cash `12.75%`, gap `+2.75pp`
  - UU-best intended cash `11.20%`, post-overlay cash `12.69%`, gap `+1.49pp`
  - VV-best intended cash `10.00%`, post-overlay cash `12.71%`, gap `+2.71pp`
- `neutral_healthy_proxy`
  - production intended cash `10.92%`, post-overlay cash `14.92%`, gap `+4.00pp`
  - TT1 intended cash `10.92%`, post-overlay cash `15.70%`, gap `+4.78pp`
  - UU-best intended cash `10.92%`, post-overlay cash `15.65%`, gap `+4.73pp`
  - VV-best intended cash `13.50%`, post-overlay cash `15.18%`, gap `+1.68pp`

So VV did what it was designed to do on one axis: it narrowed the gap between intended cash and post-overlay cash, especially in `recovery_confirmed` and `neutral_healthy_proxy`.

## 4. Which overlay branches violated intended recovery budgets

The same culprit stayed in control:

- `lighter_both_regime_relief` was still the main branch associated with post-overlay cash in:
  - `neutral_healthy_proxy`
  - `recovery_confirmed`
  - `recovery_fragile`
  - `stressed_panic`

Production, TT1, UU-best, and all VV candidates still pointed to that same family in the recovery states. Phase VV improved the budget-gap outcome under that branch, but it did not replace the branch or make it subordinate enough to the intended recovery overlay budget.

That is why the phase is a meaningful architectural step but not yet a solved overlay redesign.

## 5. Target-vol guardrail cases

Target-vol remained a **rare** guardrail in the states Phase VV cared about.

For the best VV candidate:

- `neutral_healthy_proxy`: `1` target-vol guardrail week, about `0.34%` of state weeks
- `recovery_fragile`: `1` target-vol guardrail week, about `2.04%` of state weeks
- `recovery_confirmed`: `0` target-vol guardrail weeks

Interpretation:

- target-vol was still not the dominant recovery-state blocker
- the dominant blocker remained the recovery-side `lighter_both_regime_relief` cash path
- there was no evidence of a large unsafe target-vol override wave

The saved guardrail-case file is still useful, but its VV-specific override columns are sparse because the candidate only encountered a very small number of target-vol-active recovery or neutral weeks.

## 6. Candidate metrics table

| Candidate | Full ann return | Full Sharpe | Max DD | CVaR 5% | Avg turnover | Avg BIL | Avg SPY | Delta ann vs prod | Delta Sharpe vs prod | Delta Sharpe vs UU | Quick screen |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `improved_phasevv_recovery_budget_aware_overlay` | 7.0617% | 0.8993 | -14.08% | -2.64% | 5.77% | 28.36% | 7.31% | +0.09pp | +0.0040 | -0.0001 | Reject |
| `improved_phasevv_recovery_overlay_tolerance_band` | 7.0617% | 0.8993 | -14.08% | -2.64% | 5.77% | 28.36% | 7.31% | +0.09pp | +0.0040 | -0.0001 | Reject |
| `improved_phasevv_recovery_neutral_budget_aware_overlay` | 7.0872% | 0.9000 | -14.08% | -2.64% | 5.77% | 28.17% | 7.34% | +0.11pp | +0.0048 | +0.0006 | Reject |

Why all three still failed the phase screen:

- none cleared the strict `+0.005` Sharpe delta vs production on exact phase metrics
- VV1 and VV2 also failed the "must improve vs UU best" Sharpe test
- none reduced **targeted recovery overlay absorption vs production**

The best candidate won because it had the strongest full return/Sharpe profile and the strongest neutral-healthy participation improvement, not because it solved the recovery overlay-stage problem.

## 7. State-by-state impact

Best candidate: `improved_phasevv_recovery_neutral_budget_aware_overlay`

- `recovery_confirmed`: annual return delta vs production `+0.60pp`, Sharpe delta `+0.0668`
- `recovery_fragile`: annual return delta vs production `+0.90pp`, Sharpe delta `+0.1413`
- `neutral_healthy_proxy`: annual return delta vs production `+0.22pp`, Sharpe delta `+0.0175`
- `calm_trend`: annual return delta vs production `-0.07pp`, Sharpe delta `-0.0103`
- `stressed_panic`: annual return delta vs production `-0.04pp`, Sharpe delta `-0.0093`

Relative to TT1:

- annual return delta vs TT1: `+0.03pp`
- Sharpe delta vs TT1: `+0.0008`

Relative to UU-best:

- annual return delta vs UU-best: `+0.02pp`
- Sharpe delta vs UU-best: `+0.0006`

So VV-best did become the strongest recent research challenger on full metrics, but only by a very small margin.

## 8. Overlay absorption reduction by state

This is the decisive negative result.

For `improved_phasevv_recovery_neutral_budget_aware_overlay`:

- vs production
  - `recovery_confirmed`: `+0.01pp`
  - `recovery_fragile`: `-0.36pp`
  - targeted mean recovery reduction: `-0.17pp`
- vs TT1
  - `recovery_confirmed`: `+0.16pp`
  - `recovery_fragile`: `+0.04pp`
  - targeted mean recovery reduction: `+0.10pp`
- vs UU-best
  - `recovery_confirmed`: `-0.14pp`
  - `recovery_fragile`: `-0.02pp`
  - targeted mean recovery reduction: `-0.08pp`

Interpretation:

- VV improved overlay behavior relative to TT1
- VV **did not** improve targeted recovery overlay absorption relative to production
- VV also did not beat UU-best on the targeted recovery overlay-stage metric

That is why the selection table rejected it even though the portfolio-level return and Sharpe were slightly better.

## 9. Comparison vs TT1 and UU best

Phase VV was better than TT1 and UU-best on **headline** full-window metrics:

- vs TT1: small improvement in both annual return and Sharpe
- vs UU-best: small improvement in both annual return and Sharpe

But Phase VV was **not** better on the exact mechanism it was supposed to fix:

- it did not lower targeted recovery overlay absorption vs production
- it did not beat UU-best on that targeted recovery overlay metric either

This means the improvement path is real, but it is now increasingly detached from the original "fix overlay-stage clawback directly" hypothesis.

## 10. Hidden beta / hidden cash check

VV-best did not look like a hidden-beta shortcut.

- avg SPY rose only `+0.26pp` vs production
- avg BIL fell `-0.23pp`
- avg offense rose `+0.56pp`
- avg composite bucket fell `-1.48pp`

That is consistent with a genuine architecture change rather than a blunt SPY drift.

## 11. Stressed-panic protection check

Stressed-panic remained broadly intact:

- annual return delta vs production: about `-0.04pp`
- Sharpe delta vs production: about `-0.0093`
- avg BIL in stressed-panic remained about `60.74%`

This remains acceptable as a guardrail outcome. Phase VV did not break the panic-defense posture.

## 12. Recovery-fragile protection check

Recovery-fragile remained improved at the portfolio level:

- annual return delta vs production: `+0.90pp`
- Sharpe delta vs production: `+0.1413`
- avg BIL fell slightly vs production

So the candidate still helped the recovery-fragile state in returns and Sharpe. The problem is narrower: the overlay-stage absorption inside that state still did not improve enough versus production.

## 13. Target-vol guardrail check

Target-vol remained a minority edge case in the targeted states.

- it appeared only rarely in `neutral_healthy_proxy` and `recovery_fragile`
- it was absent in `recovery_confirmed`
- there was no broad evidence that VV was overriding target-vol in a reckless way

So Phase VV did preserve the high-level target-vol guardrail intent.

## 14. Best candidate

Best candidate: `improved_phasevv_recovery_neutral_budget_aware_overlay`

Why it won:

- strongest full annual return and Sharpe
- best improvement versus TT1 and UU-best on headline metrics
- strongest neutral-healthy budget-gap compression
- still preserved stressed-panic reasonably well

Why it still failed the phase objective:

- exact Sharpe delta vs production stayed below the strict `+0.005` screen in the phase script
- targeted recovery overlay absorption vs production remained negative on average

## 15. Quick committee verdict

Committee verdict:

- `KEEP AS SHADOW (research reference)`

Reference:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phasevv_recovery_neutral_budget_aware_overlay_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phasevv_recovery_neutral_budget_aware_overlay_audit.md)

Important nuance:

- the committee report rounds the full Sharpe delta to about `+0.005`
- the stricter phase script used the exact value, about `+0.0048`, and still rejected the candidate

So the correct project interpretation is:

- the candidate is strong enough to remain a shadow research reference
- it is not strong enough to claim the phase fully solved the overlay problem

## 16. Whether Layer 5/6 quick audits ran

They ran.

Layer 5 realism:

- verdict: `candidate survives doubled-cost scenario`

Layer 6 allocator benchmark:

- verdict: extra complexity still `NO / MARGINAL`
- candidate beat production on annual return and Sharpe
- but still did not clearly beat the best simple internal benchmark by enough to justify production complexity

References:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phasevv_recovery_neutral_budget_aware_overlay_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phasevv_recovery_neutral_budget_aware_overlay_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phasevv_recovery_neutral_budget_aware_overlay_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phasevv_recovery_neutral_budget_aware_overlay_allocator_benchmark.md)

## 17. Final decision

**KEEP AS SHADOW**

- Production pin remains `improved_phase2b_regime_confidence_boost`
- Shadow pin remains `improved_phase2b_combo_abc`
- No automatic promotion

## 18. Whether budget-aware overlay architecture should continue

Yes, but only if the next step is deeper.

Phase VV shows that first-class budget-aware overlay design is a better direction than narrow cash-cap patches:

- it improved headline metrics again
- it compressed the intended-budget gap more cleanly than TT1 or UU

But it also showed that **budget-gap improvement is not the same thing as overlay-absorption improvement**. The current `lighter_both_regime_relief` branch can still convert a narrower budget gap into a similar recovery-stage absorption profile versus production.

So this frontier should continue only if the next phase rewrites the recovery overlay branch more fundamentally, not if it just adds another tolerance tweak.

## 19. Recommended next phase if this fails

Move to a deeper `lighter_both` overlay-architecture rewrite.

The next phase should stop treating budget awareness as a post-branch correction and instead make `lighter_both_regime_relief` itself compute from:

- intended state cash budget
- true target-vol guardrail activation
- stressed-panic preservation
- recovery-state participation priority

In other words: Phase VV suggests the next move is not "more budget caps." It is to replace the recovery `lighter_both` decision rule itself so the branch becomes a genuine budget-aware overlay, not a mostly-independent cash-creation layer with a budget correction attached afterward.
