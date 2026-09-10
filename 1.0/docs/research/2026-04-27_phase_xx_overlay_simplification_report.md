# Phase XX — Overlay Simplification / Allocator-Overlay Unification

## 1. Commands executed

```bash
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_xx_overlay_simplification.py
python3 -u scripts/phase_xx_overlay_simplification.py
python3 scripts/research_committee_report.py improved_phasexx_conservative_hybrid_overlay --quick
python3 scripts/backtest_realism_audit.py improved_phasexx_conservative_hybrid_overlay --quick
python3 scripts/allocator_benchmark_audit.py improved_phasexx_conservative_hybrid_overlay --quick
```

## 2. Files created / modified

- Modified: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/build_improvement_artifacts.py)
- Created: [/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_xx_overlay_simplification.py](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/scripts/phase_xx_overlay_simplification.py)
- Updated journey log: [/Users/nicholasturangan/Documents/Portfolio Optimizer/docs/research/project_journey.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/docs/research/project_journey.md)

Primary outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_cash_decision_duplication_by_state.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_cash_decision_duplication_by_state.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_guardrail_vs_regime_relief_cash.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_guardrail_vs_regime_relief_cash.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_overlay_simplification_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_overlay_simplification_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_candidate_diagnostics.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/research/phase_xx_overlay_simplification/phase_xx_candidate_diagnostics.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_xx_candidate_metrics_full.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_xx_candidate_metrics_full.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_xx_state_summary.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_xx_state_summary.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_xx_selection_table.csv](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_xx_selection_table.csv)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_xx_protocol.json](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/data/05_layer3_portfolio_construction/phase_xx_protocol.json)

Quick audit outputs:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phasexx_conservative_hybrid_overlay_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phasexx_conservative_hybrid_overlay_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phasexx_conservative_hybrid_overlay_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phasexx_conservative_hybrid_overlay_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phasexx_conservative_hybrid_overlay_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phasexx_conservative_hybrid_overlay_allocator_benchmark.md)

## 3. Duplicated cash-decision diagnosis

Phase XX tested the broader architecture hypothesis directly:

- allocator/bucket logic chooses the risky/cash budget once
- overlay should only enforce true guardrails
- recovery regime relief should not create a second quasi-independent cash budget afterward

The diagnosis confirmed the duplication problem is real.

Production:

- `recovery_confirmed`
  - intended cash: `0.00%`
  - post-overlay cash: `6.38%`
  - final ETF cash/BIL: `12.57%`
  - duplicated cash over intended: `6.38pp`
- `recovery_fragile`
  - intended cash: `0.00%`
  - post-overlay cash: `12.35%`
  - final ETF cash/BIL: `21.82%`
  - duplicated cash over intended: `12.35pp`
- `neutral_healthy_proxy`
  - intended cash: `10.92%`
  - post-overlay cash: `14.92%`
  - final ETF cash/BIL: `21.31%`
  - duplicated cash over intended: `4.00pp`

VV best:

- `recovery_confirmed`: duplicated cash `1.59pp`
- `recovery_fragile`: duplicated cash `7.50pp`
- `neutral_healthy_proxy`: duplicated cash `9.88pp`

WW best:

- `recovery_confirmed`: duplicated cash `2.10pp`
- `recovery_fragile`: duplicated cash `12.67pp`
- `neutral_healthy_proxy`: duplicated cash `4.71pp`

So the duplicated-cash story is not just a Phase WW artifact. It is still present even in the stronger recent challengers, just in different states and magnitudes.

## 4. Guardrail cash vs regime-relief cash

The main conclusion stayed consistent with TT / UU / VV / WW:

- `target_vol` was still rare in the targeted states
- `panic/stress` guardrail correctly explained stressed-panic cash
- most recovery cash was still better described as **regime-relief cash**, not true guardrail cash

For the best XX candidate (`improved_phasexx_conservative_hybrid_overlay`):

- `recovery_confirmed`
  - duplicated cash over intended: `1.76pp`
  - regime-relief cash: `1.76pp`
  - guardrail cash added: `4.52pp`
  - target-vol active share: `0.00%`
- `recovery_fragile`
  - duplicated cash over intended: `6.98pp`
  - regime-relief cash: `6.98pp`
  - guardrail cash added: `5.76pp`
  - target-vol active share: `2.04%`
- `neutral_healthy_proxy`
  - duplicated cash over intended: `9.96pp`
  - regime-relief cash: `9.96pp`
  - guardrail cash added: `5.23pp`

Interpretation:

- XX did reduce duplicated recovery cash meaningfully.
- But it did not fully remove the second cash engine.
- `recovery_fragile` is still the state where the simplification remains incomplete.

## 5. Candidate family tested

- `improved_phasexx_guardrail_only_overlay`
- `improved_phasexx_guardrail_overlay_fragile_floor`
- `improved_phasexx_recovery_neutral_overlay_simplified`
- `improved_phasexx_conservative_hybrid_overlay`

The family was intentionally narrow:

- no new sleeves
- no ML
- no post-hoc ETF reconstruction
- no broad search

All changes stayed inside the existing production pipeline and centered on removing duplicated cash creation from the overlay.

## 6. Candidate metrics table

| Candidate | Full ann return | Full Sharpe | Max DD | CVaR 5% | Avg BIL | Avg SPY | Delta ann vs prod | Delta Sharpe vs prod | Delta Sharpe vs VV | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `improved_phasexx_guardrail_only_overlay` | 7.0289% | 0.8975 | -14.08% | -2.63% | 28.74% | 7.26% | +0.06pp | +0.0022 | -0.0025 | Reject |
| `improved_phasexx_guardrail_overlay_fragile_floor` | 7.0228% | 0.8971 | -14.08% | -2.63% | 28.82% | 7.26% | +0.05pp | +0.0019 | -0.0029 | Reject |
| `improved_phasexx_recovery_neutral_overlay_simplified` | 6.8775% | 0.8977 | -14.08% | -2.56% | 30.41% | 7.06% | -0.10pp | +0.0024 | -0.0024 | Reject |
| `improved_phasexx_conservative_hybrid_overlay` | 7.0865% | 0.8999 | -14.08% | -2.64% | 28.17% | 7.34% | +0.11pp | +0.0047 | -0.0001 | Reject |

## 7. State-by-state impact

Best candidate: `improved_phasexx_conservative_hybrid_overlay`

- `recovery_confirmed`: ann return delta vs production `+0.60pp`, Sharpe delta `+0.0666`
- `recovery_fragile`: ann return delta vs production `+0.91pp`, Sharpe delta `+0.1440`
- `neutral_healthy_proxy`: ann return delta vs production `+0.28pp`, Sharpe delta `+0.0174`
- `calm_trend`: ann return delta vs production `-0.07pp`, Sharpe delta `-0.0103`
- `stressed_panic`: ann return delta vs production `-0.03pp`, Sharpe delta `-0.0091`

So the simplification candidate did preserve the same broad pattern as VV and WW:

- recovery states better
- neutral healthy better
- calm and panic slightly worse

## 8. Comparison vs production, VV best, and WW best

Versus production, XX best was a real improvement:

- ann return: `7.0865%` vs `6.9737%`
- Sharpe: `0.8999` vs `0.8953`
- avg BIL: `28.17%` vs `28.39%`
- avg SPY: `7.34%` vs `7.08%`

Versus WW best:

- ann return slightly higher
- Sharpe slightly higher
- duplicated recovery cash reduced more cleanly

Versus VV best:

- almost tied on full metrics
- ann return lower by only about `0.00pp`
- Sharpe lower by only about `0.0001`
- duplicated recovery cash reduced more than VV

That is the key XX result:

- the simplification idea improved the **mechanism**
- but it still did not beat the strongest recent challenger on final Sharpe

## 9. Duplicated cash reduction by state

Best candidate (`improved_phasexx_conservative_hybrid_overlay`):

- targeted mean duplicated-cash reduction vs production: `+4.99pp`
- targeted mean overlay-absorption reduction vs production: `-0.14pp`

By state:

- `recovery_confirmed`
  - duplicated cash reduction vs production: `+4.62pp`
  - overlay absorption reduction vs production: `+0.10pp`
- `recovery_fragile`
  - duplicated cash reduction vs production: `+5.37pp`
  - overlay absorption reduction vs production: `-0.39pp`

Interpretation:

- Phase XX genuinely reduced the duplicated cash problem.
- But it still could not fully convert that into better recovery overlay absorption in `recovery_fragile`.
- That is why the branch improved architecture clarity more than it improved the exact promotion metric.

## 10. Hidden beta / hidden cash check

XX best did not look like a hidden-beta shortcut:

- avg SPY rose only `+0.26pp` vs production
- avg BIL fell `-0.23pp`
- avg offense rose `+0.56pp`
- avg composite bucket stayed below production

This was a real allocator/overlay architecture change, not a blunt SPY injection.

## 11. Stressed-panic protection check

XX best preserved stressed-panic reasonably well:

- ann return delta vs production: about `-0.03pp`
- Sharpe delta vs production: about `-0.0091`
- avg BIL in stressed-panic: about `60.74%`

So the simplification did not break the project’s panic-defense posture.

## 12. Recovery-fragile protection check

At the portfolio level, `recovery_fragile` remained improved:

- ann return delta vs production: `+0.91pp`
- Sharpe delta vs production: `+0.1440`

But at the mechanism level, `recovery_fragile` is still the bottleneck:

- duplicated cash was reduced
- overlay absorption versus production was still slightly worse

That means simplification helped, but it still did not fully solve the same stubborn fragile-recovery problem that WW exposed.

## 13. Target-vol guardrail check

- no evidence of unsafe target-vol override
- target-vol remained rare in the targeted states
- the simplified candidates preserved the intended role of target-vol as a true guardrail, not a broad participation blocker

## 14. Best candidate

Best candidate: `improved_phasexx_conservative_hybrid_overlay`

Why it won:

- strongest full annual return and full Sharpe in the XX family
- best balance of duplicated-cash reduction and portfolio preservation
- slightly better than WW best on full metrics
- essentially tied VV on headline full metrics

Why it still failed:

- Sharpe delta vs production was only about `+0.0047`, still below `+0.005`
- it did not improve Sharpe vs VV best
- duplicated recovery cash fell, but recovery overlay absorption did not turn convincingly positive

## 15. Quick committee verdict

Committee verdict:

- `KEEP AS SHADOW (research reference)`

Reference:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phasexx_conservative_hybrid_overlay_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/research_committee/improved_phasexx_conservative_hybrid_overlay_audit.md)

## 16. Whether Layer 5/6 quick audits ran

They ran.

- Layer 5 realism: candidate survives doubled-cost scenario
- Layer 6 allocator benchmark: extra complexity still `NO / MARGINAL`

References:
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phasexx_conservative_hybrid_overlay_realism_audit.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/backtest_realism/improved_phasexx_conservative_hybrid_overlay_realism_audit.md)
- [/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phasexx_conservative_hybrid_overlay_allocator_benchmark.md](/Users/nicholasturangan/Documents/Portfolio%20Optimizer/reports/allocator_benchmark/improved_phasexx_conservative_hybrid_overlay_allocator_benchmark.md)

## 17. Final decision

**Final decision: BRANCH EXHAUSTED**

The best candidate remains shadow-worthy, but the architectural conclusion is that this overlay simplification branch did not clear the gate and did not beat VV best on final Sharpe.

## 18. Whether overlay simplification should continue

No, not as another variant of this same overlay-unification idea.

Phase XX was the right broader test after WW:

- it reduced duplicated cash directly
- it kept the production pipeline intact
- it preserved guardrails
- and it came very close to the strongest recent challenger

But even that broader test still did not produce a clean winner.

## 19. Recommended next phase if this fails

Move away from the overlay frontier and up to a new architecture frontier:

- treat VV as the strongest recent full-metric challenger
- stop iterating on recovery overlay cash logic
- redesign the sleeve/allocator stack so the composite sleeve and overlay are no longer both trying to do state-conditioned defense

The next credible frontier is a broader sleeve-architecture simplification or decomposition phase, likely centered on:

- breaking `composite_regime_conditioned` into more explicit offense/defense sleeves or
- replacing hidden sleeve-level cash behavior with cleaner explicit allocator-level bucket participation

In short:

- overlay simplification helped, but not enough
- the overlay branch is now exhausted
- the next step should move higher into sleeve architecture or an even simpler allocator stack rather than more overlay surgery
