# Phase WW — Focused Recovery-Overlay Rescue Sprint

## 1. Commands executed

```bash
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_ww_recovery_overlay_rescue.py
python3 -u scripts/phase_ww_recovery_overlay_rescue.py
python3 scripts/research_committee_report.py improved_phaseww_confirmed_only_lighter_both --quick
python3 scripts/backtest_realism_audit.py improved_phaseww_confirmed_only_lighter_both --quick
python3 scripts/allocator_benchmark_audit.py improved_phaseww_confirmed_only_lighter_both --quick
```

## 2. Files created / modified

- Modified: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/build_improvement_artifacts.py)
- Created: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_ww_recovery_overlay_rescue.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/phase_ww_recovery_overlay_rescue.py)
- Updated journey log: [/Users/nicholasturangan/Documents/Portfolio Optimizer/docs/research/project_journey.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/project_journey.md)

Primary outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_lighter_both_excess_cash_by_state.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_lighter_both_excess_cash_by_state.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_guardrail_activation_by_state.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_guardrail_activation_by_state.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_overlay_branch_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_overlay_branch_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_vv_tt_production_comparison.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_vv_tt_production_comparison.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_candidate_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_ww_recovery_overlay_rescue/phase_ww_candidate_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_ww_candidate_metrics_full.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ww_candidate_metrics_full.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_ww_state_summary.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ww_state_summary.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_ww_selection_table.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ww_selection_table.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_ww_protocol.json](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_ww_protocol.json)

Quick audit outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phaseww_confirmed_only_lighter_both_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phaseww_confirmed_only_lighter_both_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phaseww_confirmed_only_lighter_both_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phaseww_confirmed_only_lighter_both_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phaseww_confirmed_only_lighter_both_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phaseww_confirmed_only_lighter_both_allocator_benchmark.md)

## 3. Branch-level diagnosis

Phase WW tested the branch directly rather than adding another post-branch cap. The overlay rewrite moved inside `lighter_both_regime_relief` and used state-conditioned intended cash budgets plus real guardrails. The point was to answer a specific question:

Can the recovery overlay stop re-adding cash after the allocator has already made a better recovery bucket decision?

The answer was mixed:

- `lighter_both_regime_relief` is still the dominant recovery cash source.
- `target_vol` remains rare in the targeted states.
- `panic/stress` is a real guardrail in `stressed_panic`, but it is not the explanation for most recovery-state cash.
- Direct rewrites reduced **excess** recovery cash relative to the intended budget, but most variants still failed to improve the stricter recovery overlay-absorption metric versus production.

## 4. Exact lighter_both excess cash by state

Production:

- `recovery_confirmed`
  - intended cash: `0.00%`
  - post-overlay cash: `6.38%`
  - final ETF cash/BIL: `12.57%`
  - excess cash not explained by guardrails: `6.38pp`
- `recovery_fragile`
  - intended cash: `0.00%`
  - post-overlay cash: `12.35%`
  - final ETF cash/BIL: `21.82%`
  - excess cash not explained by guardrails: `12.35pp`
- `neutral_healthy_proxy`
  - intended cash: `10.92%`
  - post-overlay cash: `14.92%`
  - final ETF cash/BIL: `21.31%`
  - excess cash not explained by guardrails: `4.00pp`

TT1:

- `recovery_confirmed`
  - intended cash: `6.00%`
  - post-overlay cash: `6.53%`
  - excess cash not explained by guardrails: `1.59pp`
- `recovery_fragile`
  - intended cash: `10.00%`
  - post-overlay cash: `12.75%`
  - excess cash not explained by guardrails: `7.50pp`

VV best:

- `recovery_confirmed`
  - intended cash: `6.00%`
  - post-overlay cash: `6.37%`
  - excess cash not explained by guardrails: `0.88pp`
- `recovery_fragile`
  - intended cash: `10.00%`
  - post-overlay cash: `12.71%`
  - excess cash not explained by guardrails: `7.09pp`

WW best (`improved_phaseww_confirmed_only_lighter_both`):

- `recovery_confirmed`
  - intended cash: `4.50%`
  - post-overlay cash: `5.99%`
  - excess cash not explained by guardrails: `2.07pp`
  - overlay absorption reduction vs production: `+0.39pp`
- `recovery_fragile`
  - intended cash: production-like
  - post-overlay cash: `12.67%`
  - excess cash not explained by guardrails: `12.50pp`
  - overlay absorption reduction vs production: `-0.32pp`

Interpretation:

- `recovery_confirmed` was salvageable.
- `recovery_fragile` remained the structural blocker.
- The branch can improve one side of recovery without breaking panic defense, but it still cannot solve the whole recovery overlay problem cleanly.

## 5. Target-vol and panic guardrail activation

- `target_vol` remained very rare:
  - `recovery_confirmed`: `0%` active weeks
  - `recovery_fragile`: about `2.04%` active weeks
  - `neutral_healthy_proxy`: about `0.34%` active weeks
- `panic/stress` guardrail was the right explanation in `stressed_panic`, not in recovery.

This means most recovery cash remained leftover regime-relief cash, not true target-vol or panic cash.

## 6. Candidate family tested

Main candidates:

- `improved_phaseww_recovery_budget_native_lighter_both`
- `improved_phaseww_split_recovery_lighter_both`
- `improved_phaseww_vv_direct_lighter_both_rewrite`

Rescue variants were created because all 3 main candidates failed narrowly but did improve either return, Sharpe, or excess-cash behavior, so one last disciplined pass was justified:

- `improved_phaseww_confirmed_only_lighter_both`
- `improved_phaseww_fragile_defense_lighter_both`
- `improved_phaseww_vv_shadow_polish`

## 7. Candidate metrics table

| Candidate | Family | Full ann return | Full Sharpe | Max DD | CVaR 5% | Avg BIL | Avg SPY | Delta ann vs prod | Delta Sharpe vs prod | Delta Sharpe vs VV | Result |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `improved_phaseww_recovery_budget_native_lighter_both` | main | 7.0320% | 0.8976 | -14.08% | -2.63% | 28.69% | 7.27% | +0.06pp | +0.0023 | -0.0025 | Reject |
| `improved_phaseww_split_recovery_lighter_both` | main | 7.0296% | 0.8972 | -14.08% | -2.63% | 28.71% | 7.27% | +0.06pp | +0.0019 | -0.0028 | Reject |
| `improved_phaseww_vv_direct_lighter_both_rewrite` | main | 6.9064% | 0.8982 | -14.08% | -2.57% | 30.09% | 7.10% | -0.07pp | +0.0030 | -0.0018 | Reject |
| `improved_phaseww_confirmed_only_lighter_both` | rescue | 7.0669% | 0.8996 | -14.08% | -2.64% | 28.31% | 7.31% | +0.09pp | +0.0043 | -0.0005 | Reject |
| `improved_phaseww_fragile_defense_lighter_both` | rescue | 7.0272% | 0.8972 | -14.08% | -2.63% | 28.75% | 7.26% | +0.05pp | +0.0019 | -0.0028 | Reject |
| `improved_phaseww_vv_shadow_polish` | rescue | 6.8981% | 0.8981 | -14.08% | -2.57% | 30.18% | 7.09% | -0.08pp | +0.0028 | -0.0019 | Reject |

## 8. State-by-state impact

Best candidate: `improved_phaseww_confirmed_only_lighter_both`

- `recovery_confirmed`: ann return delta vs production `+0.62pp`, Sharpe delta `+0.0695`
- `recovery_fragile`: ann return delta vs production `+0.90pp`, Sharpe delta `+0.1418`
- `neutral_healthy_proxy`: ann return delta vs production `+0.22pp`, Sharpe delta `+0.0178`
- `calm_trend`: ann return delta vs production `-0.07pp`, Sharpe delta `-0.0101`
- `stressed_panic`: ann return delta vs production `-0.04pp`, Sharpe delta `-0.0094`

## 9. Comparison vs production, TT1, UU best, and VV best

Versus production, WW best was competitive:

- ann return: `7.0669%` vs `6.9737%`
- Sharpe: `0.8996` vs `0.8953`
- avg BIL: `28.31%` vs `28.39%`
- avg SPY: `7.31%` vs `7.08%`

Versus TT1:

- ann return improved modestly
- Sharpe improved modestly
- recovery-state gains were preserved

Versus UU best:

- ann return improved modestly
- Sharpe improved modestly

Versus VV best:

- ann return was slightly lower
- Sharpe was slightly lower
- the WW rescue solved the specific recovery-absorption problem a little better than VV, but VV remained the stronger overall recent challenger

## 10. Overlay absorption reduction by state

This is the decisive Phase WW result.

Main candidates:

- all 3 reduced **excess** recovery cash
- all 3 still made targeted recovery overlay absorption worse than production on average

Best rescue candidate (`improved_phaseww_confirmed_only_lighter_both`):

- targeted mean overlay-absorption reduction vs production: `+0.04pp`
- targeted mean excess-cash reduction vs production: `+2.08pp`
- `recovery_confirmed`: positive overlay-absorption reduction
- `recovery_fragile`: still negative overlay-absorption reduction

So WW did find a variant that finally made the targeted mean recovery overlay-absorption statistic slightly positive, but only by conceding that `recovery_fragile` still had to stay close to production.

## 11. Hidden beta / hidden cash check

WW best did not look like a hidden beta shortcut:

- avg SPY rose only `+0.23pp` vs production
- avg BIL was slightly lower than production
- avg composite bucket stayed below production
- returns did not come from forcing a broad SPY hack

## 12. Stressed-panic protection check

WW best preserved stressed-panic well enough for a shadow-level candidate:

- ann return delta vs production: about `-0.04pp`
- Sharpe delta vs production: about `-0.009`
- avg BIL in stressed-panic remained about `60.77%`

## 13. Recovery-fragile protection check

Portfolio-level `recovery_fragile` performance remained improved for WW best:

- ann return delta vs production: `+0.90pp`
- Sharpe delta vs production: `+0.1418`

But the overlay-stage mechanism did **not** really get solved there. The branch still needed to leave `recovery_fragile` close to production-like overlay behavior to avoid damaging the full portfolio.

## 14. Target-vol guardrail check

- no evidence of unsafe target-vol override
- recovery target-vol weeks remained rare
- WW only changed cash where target-vol was not the real active blocker

## 15. Best candidate

Best candidate: `improved_phaseww_confirmed_only_lighter_both`

Why it won:

- strongest full-window rescue profile
- only WW candidate that made targeted mean recovery overlay absorption slightly positive
- preserved stressed-panic reasonably well

Why it still failed:

- Sharpe delta vs production was only about `+0.0043`, still below `+0.005`
- Sharpe still did not improve versus VV best

## 16. Quick committee verdict

Committee verdict:

- `KEEP AS SHADOW (research reference)`

Reference:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phaseww_confirmed_only_lighter_both_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phaseww_confirmed_only_lighter_both_audit.md)

## 17. Whether Layer 5/6 quick audits ran

They ran.

- Layer 5 realism: candidate survives doubled-cost scenario
- Layer 6 allocator benchmark: complexity still `NO / MARGINAL`

References:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phaseww_confirmed_only_lighter_both_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phaseww_confirmed_only_lighter_both_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phaseww_confirmed_only_lighter_both_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phaseww_confirmed_only_lighter_both_allocator_benchmark.md)

## 18. Whether any rescue variants were created and why

Yes.

Rescue variants were created because all 3 main candidates failed narrowly and the failure reason was clear:

- they were improving return or excess cash
- but they were still not fixing `recovery_fragile` overlay absorption cleanly enough

The rescue family tested whether the branch could be salvaged by:

- isolating the rewrite to `recovery_confirmed`
- keeping more defense in `recovery_fragile`
- or making only a minimal VV-style polish

That rescue pass was worth doing. It improved the diagnosis, even though it did not produce a production-ready candidate.

## 19. Final decision

**Final decision: BRANCH EXHAUSTED**

More precisely:

- no WW candidate clears the strict production gate
- the best rescue still trails VV on Sharpe
- the branch can improve `recovery_confirmed`, but it does not solve `recovery_fragile` cleanly enough

## 20. Whether recovery-overlay rescue should continue

No, not as another narrow `lighter_both` rewrite family.

Phase WW did the disciplined last pass:

- 3 main branch-native recovery rewrites
- 3 rescue variants after the main family failed narrowly
- all through the production pipeline
- with target-vol and stressed-panic guardrails preserved

That is enough evidence to stop iterating on this narrow branch.

## 21. Recommended next phase if this fails

Move up one level to a broader overlay/allocator unification path:

- replace the independent recovery `lighter_both_regime_relief` cash engine with a simpler overlay architecture where:
  - the allocator chooses risky/cash once,
  - the overlay only enforces true target-vol and panic/stress guardrails,
  - recovery-state regime relief no longer creates a second quasi-independent cash budget.

In short:

- stop doing narrow recovery-overlay rescue
- move to a broader overlay simplification / overlay removal-or-unification phase
- treat VV as the strongest recent full-metric challenger
- treat WW as the phase that exhausted the direct recovery-branch rewrite hypothesis
