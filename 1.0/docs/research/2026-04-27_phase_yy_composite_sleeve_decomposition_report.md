# Phase YY — Composite Sleeve Decomposition / Sleeve-Architecture Simplification

## 1. Commands Executed

- `python3 -m py_compile /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_yy_composite_sleeve_decomposition.py`
- `python3 -u /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_yy_composite_sleeve_decomposition.py`
- `python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/research_committee_report.py improved_phaseyy_conservative_decomposition --quick`
- `python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/backtest_realism_audit.py improved_phaseyy_conservative_decomposition --quick`
- `python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/allocator_benchmark_audit.py improved_phaseyy_conservative_decomposition --quick`

## 2. Files Created / Modified

- Created `/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/phase_yy_composite_sleeve_decomposition.py`
- Modified `/Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py`
- Created diagnostics in `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_yy_composite_sleeve_decomposition/`
- Created candidate outputs in `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/`
- Created this report: `/Users/nicholasturangan/Documents/Portfolio Optimizer/docs/research/2026-04-27_phase_yy_composite_sleeve_decomposition_report.md`

## 3. Decomposition Method

`composite_regime_conditioned` was decomposed causally from its actual ETF positions, not from a post-hoc return fit.

- `composite_regime_offense_component`
  - normalized from `SPY, QQQ, IWM, EFA, VEA, VWO, EWJ, VNQ, PDBC, DBA`
- `composite_regime_defense_component`
  - normalized from `HYG, LQD, GLD, TLT`
- `composite_regime_cash_component`
  - explicit `BIL`

When an offense or defense sub-book was absent on a given week, that synthetic sleeve fell back to `BIL` for that week. Candidate portfolio returns were still generated through the canonical production construction path, not by manually patching ETF weights.

## 4. Component Weights By State

From `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_yy_composite_sleeve_decomposition/phase_yy_composite_component_weights_by_state.csv`:

- `calm_trend`: offense `53.51%`, defense `35.08%`, cash `11.42%`
- `neutral_healthy_proxy`: offense `37.95%`, defense `39.14%`, cash `22.91%`
- `recovery_confirmed`: offense `31.08%`, defense `50.40%`, cash `18.52%`
- `recovery_fragile`: offense `28.06%`, defense `47.96%`, cash `23.98%`
- `stressed_panic`: offense `15.99%`, defense `30.21%`, cash `53.80%`

The key diagnosis is that the composite sleeve is not just hiding cash. In the recovery states it is also hiding a large non-BIL defensive book, especially in `recovery_confirmed` and `recovery_fragile`.

## 5. Component Returns By State

Approximate component return diagnostics from `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_yy_composite_sleeve_decomposition/phase_yy_composite_component_returns_by_state.csv`:

- `recovery_confirmed`
  - offense component: ann return `28.50%`, Sharpe `2.52`
  - defense component: ann return `12.99%`, Sharpe `1.75`
  - cash component: ann return `1.54%`
- `recovery_fragile`
  - offense component: ann return `35.98%`, Sharpe `3.31`
  - defense component: ann return `9.31%`, Sharpe `1.15`
  - cash component: ann return `1.24%`
- `neutral_healthy_proxy`
  - offense component: ann return `24.36%`, Sharpe `1.75`
  - defense component: ann return `11.67%`, Sharpe `1.43`
- `stressed_panic`
  - offense component: ann return `-13.08%`, Sharpe `-0.54`
  - defense component: ann return `6.90%`, Sharpe `0.49`
  - cash component: ann return `1.49%`

This is the new architecture signal: the offense component is clearly valuable in recovery states, but the original composite sleeve was bundling it together with a large explicit defense and cash book.

## 6. Component Correlations

From `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_yy_composite_sleeve_decomposition/phase_yy_composite_component_correlations.csv`:

- offense component: corr with SPY `0.670`, corr with production `-0.058`, corr with BIL `-0.066`
- defense component: corr with SPY `0.298`, corr with production `-0.005`, corr with BIL `0.003`
- cash component: corr with BIL `1.000`

The decomposition is real. These are not cosmetic aliases of the same sleeve.

## 7. Candidate Family Tested

- `improved_phaseyy_composite_cash_explicit`
  - raw decomposition test with allocator cash explicit and cleaner XX-style overlay
- `improved_phaseyy_composite_offense_defense_split`
  - decomposition plus TT-style bucket budgets
- `improved_phaseyy_decomposition_vv_reference`
  - decomposition plus the stronger VV overlay reference
- `improved_phaseyy_conservative_decomposition`
  - safety-first variant with tighter fragile/stress handling

## 8. Candidate Metrics Table

From `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_yy_candidate_metrics_full.csv`:

| candidate | ann return | Sharpe | max DD | CVaR 5% | avg BIL | avg SPY |
|---|---:|---:|---:|---:|---:|---:|
| production | 6.9737% | 0.8953 | -13.98% | -2.6181% | 28.39% | 7.08% |
| `improved_phaseyy_composite_cash_explicit` | 6.9236% | 0.9339 | -11.73% | -2.4493% | 26.33% | 5.92% |
| `improved_phaseyy_composite_offense_defense_split` | 7.0130% | 0.9368 | -11.75% | -2.4785% | 26.53% | 6.10% |
| `improved_phaseyy_decomposition_vv_reference` | 7.0127% | 0.9368 | -11.75% | -2.4784% | 26.53% | 6.10% |
| `improved_phaseyy_conservative_decomposition` | 7.0407% | 0.9369 | -11.75% | -2.4973% | 26.52% | 6.03% |

All four candidates improved full-window Sharpe materially versus production and also beat the Phase VV reference on Sharpe. That is the strongest positive result of this phase.

## 9. State-By-State Impact

Best candidate: `improved_phaseyy_conservative_decomposition`

From `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/05_layer3_portfolio_construction/phase_yy_state_summary.csv`:

- `calm_trend`: ann return delta vs production `+0.58pp`, Sharpe delta `+0.147`
- `neutral_healthy_proxy`: ann return delta `-0.00pp`, Sharpe delta `-0.005`
- `recovery_confirmed`: ann return delta `-1.04pp`, Sharpe delta `-0.168`
- `recovery_fragile`: ann return delta `-1.08pp`, Sharpe delta `-0.301`
- `stressed_panic`: ann return delta `+0.24pp`, Sharpe delta `-0.012`

This is why the strict phase screen rejected the entire family. The decomposition improved the total portfolio, but it did it by getting safer and cleaner outside the bottleneck states while still over-defending `recovery_fragile` and `recovery_confirmed`.

## 10. Comparison Vs Production, VV Best, And XX Best

Best candidate `improved_phaseyy_conservative_decomposition`:

- vs production
  - ann return `+0.07pp`
  - Sharpe `+0.0417`
  - max drawdown better by `+2.23pp`
  - CVaR better by `+0.12pp`
- vs `improved_phasevv_recovery_neutral_budget_aware_overlay`
  - ann return `-0.05pp`
  - Sharpe `+0.0369`
  - avg BIL `-1.64pp`
  - avg SPY `-1.31pp`
- vs `improved_phasexx_conservative_hybrid_overlay`
  - ann return `-0.05pp`
  - Sharpe `+0.0370`

So Phase YY beat the strongest overlay-era references on full-window Sharpe without using hidden beta.

## 11. Hidden Beta / Hidden Cash Check

- avg SPY fell from production `7.08%` to `6.03%`
- avg BIL fell from production `28.39%` to `26.52%`
- avg offense fell modestly
- avg explicit defense rose

This was not a hidden-SPY hack. The candidate got better mostly by replacing hidden composite cash with explicit sleeves and by lowering total volatility.

## 12. Stressed-Panic Protection Check

`stressed_panic` was broadly preserved.

- ann return delta vs production: `+0.24pp`
- Sharpe delta vs production: `-0.012`
- avg BIL remained high at `53.13%`

This is acceptable for a shadow reference and supports staying on this frontier.

## 13. Recovery-Fragile Protection Check

This is the blocking problem.

- `recovery_fragile` ann return delta vs production: `-1.08pp`
- `recovery_fragile` Sharpe delta vs production: `-0.301`

The decomposition exposed the hidden structure correctly, but the allocator then leaned too heavily into the explicit defense component in `recovery_fragile`. That is a clearer, better-defined problem than the old overlay cash clawback problem, but it is still a real failure under the strict phase rules.

## 14. Whether Duplicated Cash / Defense Behavior Was Reduced

Yes on hidden cash. No on explicit recovery defense balance.

From `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_yy_composite_sleeve_decomposition/phase_yy_candidate_diagnostics.csv` for the best candidate:

- targeted mean hidden-cash reduction across `neutral_healthy_proxy`, `recovery_confirmed`, and `recovery_fragile`: `+4.58pp`
- state hidden-cash reduction vs production:
  - `neutral_healthy_proxy`: `+3.54pp`
  - `recovery_confirmed`: `+5.07pp`
  - `recovery_fragile`: `+5.11pp`

But the hidden composite defense became explicit allocator-visible defense. That is architecturally cleaner, yet still too large in `recovery_fragile`.

## 15. Best Candidate

`improved_phaseyy_conservative_decomposition`

It was the strongest full-window risk-adjusted result and the strongest allocator-benchmark result of the candidate family.

## 16. Quick Committee Verdict

From `/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/research_committee/improved_phaseyy_conservative_decomposition_audit.md`:

- **Verdict: KEEP AS SHADOW**

Committee view was more favorable than the strict phase screen because the full-window and holdout headline metrics are strong.

## 17. Whether Layer 5 / 6 Quick Audits Ran

Yes.

- Realism quick audit: `/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/backtest_realism/improved_phaseyy_conservative_decomposition_realism_audit.md`
  - verdict: candidate survives doubled-cost scenario
- Allocator benchmark quick audit: `/Users/nicholasturangan/Documents/Portfolio Optimizer/reports/allocator_benchmark/improved_phaseyy_conservative_decomposition_allocator_benchmark.md`
  - verdict: allocator-side bar passed

## 18. Final Decision

**KEEP AS SHADOW**

The strict Phase YY screen rejected all four candidates because `recovery_fragile` worsened materially. So this is not a production challenger. But the best candidate is still a legitimate shadow/reference candidate because:

- annual return and Sharpe improved vs production
- it beat VV and XX on full-window Sharpe
- it survived quick realism
- it passed the allocator benchmark
- it preserved stressed-panic reasonably well

## 19. Whether Composite Decomposition Should Continue

Yes.

This branch is **not exhausted**. Unlike the overlay branch, Phase YY produced a clear new architectural signal:

- hidden composite cash really can be reduced
- Sharpe improved materially
- the remaining failure is no longer vague overlay absorption
- it is now a specific allocator problem: too much explicit defense allocation to the decomposed composite family in `recovery_fragile` and `recovery_confirmed`

That is a much healthier frontier.

## 20. Recommended Next Phase If This Fails

Do **not** go back to overlay surgery.

The next phase should be a **decomposed-component allocator rebudgeting** phase:

- keep the composite sleeve decomposed
- explicitly cap `composite_regime_defense_component` in `recovery_fragile` and `recovery_confirmed`
- rebalance the decomposed family toward `composite_regime_offense_component` only where the state evidence supports it
- preserve stressed-panic use of the explicit defense and cash components

The right next frontier is now allocator control over the decomposed composite family, not more hidden-cash cleanup.
