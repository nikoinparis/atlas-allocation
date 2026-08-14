# Track A Production Hardening Report

## 1. Official Production Candidate Verified

-   Official production candidate: `improved_frontier_phase5_fragility_guard`
-   Registry current pin: `improved_frontier_phase5_fragility_guard`
-   Registry production candidate: `improved_frontier_phase5_fragility_guard`
-   Registry status: `PROMOTED_TO_PRODUCTION`

## 2. Files Changed

-   `scripts/production_config.py`
-   `scripts/production_metrics.py`
-   `scripts/production_costs.py`
-   `scripts/production_allocator.py`
-   `scripts/reproduce_production_candidate.py`
-   `scripts/run_track_a_validation_governance.py`
-   `scripts/verify_dashboard_packaging.py`
-   `scripts/run_track_a_verification_suite.py`
-   `scripts/test_production_metrics_costs.py`
-   `scripts/test_production_pipeline_equivalence.py`
-   `scripts/path1_path3_research_utils.py`
-   `scripts/build_production_candidate_dashboard_bundle.py`
-   `package.json`
-   `README.md`
-   `CLAUDE.md`
-   `src/components/executive-summary.tsx`
-   `src/components/dashboard-shell.tsx`
-   `docs/research/track_a_production_hardening.md`
-   `docs/research/track_a_production_reproduction_report.md`
-   `docs/research/track_a_validation_governance_report.md`
-   `docs/research/track_a_dashboard_packaging_verification.md`
-   `docs/research/track_a_production_hardening_final_report.md`

## 3. Canonical Metrics Module Created/Updated

-   `scripts/production_metrics.py` defines CAGR, arithmetic annual return, sample-volatility Sharpe, Sortino, drawdown, Calmar, weekly VaR/CVaR, hit rate, turnover/cost summaries, exposures, holdout metrics, and rolling-origin summaries.
-   `scripts/path1_path3_research_utils.py` now delegates its production metric helpers to the canonical module.

## 4. Canonical Cost/Turnover Module Created/Updated

-   `scripts/production_costs.py` defines one-way turnover, full L1 turnover, cost conversion, next-week return convention, production path recomputation, and 1x/2x/3x cost sensitivity helpers.
-   Canonical cost is `one_way_turnover * cost_bps / 10000`, with production default `10 bps`.

## 5. Production Reproduction Results

-   Exact reproduction passed: `True`
-   Weight max absolute error: `9.931e-17`
-   Path max absolute error: `4.441e-16`
-   Net return correlation vs saved: `1.000000000000`

## 6. Old vs New Metric Comparison

| metric | canonical | registry_summary | legacy_population_vol_formula | canonical_minus_registry | canonical_minus_legacy |
|----|----|----|----|----|----|
| ann_return | 0.07134169432 | 0.07134169432 | 0.07134169432 | -8.049116929e-16 | 0 |
| ann_vol | 0.07523466355 | 0.07523466355 | 0.07520076642 | -2.359223927e-16 | 3.389712429e-05 |
| sharpe | 0.9482556438 | 0.9482556438 | 0.9486830748 | -8.770761895e-15 | -0.0004274310083 |
| max_drawdown | -0.1160345789 | -0.1160345789 | -0.1160345789 | 2.220446049e-16 | 0 |
| cvar_5 | -0.02494792886 | -0.02494792886 | -0.02494792886 | -2.081668171e-17 | 0 |
| avg_weekly_turnover | 0.06738780266 | 0.06738780266 | 0.06738780266 | -2.775557562e-17 | -2.775557562e-17 |
| holdout_sharpe | 2.178585179 | 2.178585179 | 2.18913529 | -1.33226763e-15 | -0.01055011099 |

## 7. Cost Sensitivity Results

| cost_multiplier | cost_bps_per_one_way_turnover | ann_return | sharpe | max_drawdown | cvar_5 | annualized_cost |
|----|----|----|----|----|----|----|
| 1 | 10 | 0.07134169432 | 0.9482556438 | -0.1160345789 | -0.02494792886 | 0.003501008832 |
| 2 | 20 | 0.06760219773 | 0.8985816015 | -0.1160692953 | -0.02504028716 | 0.007002017664 |
| 3 | 30 | 0.06387482901 | 0.8489700362 | -0.1161040112 | -0.02513264546 | 0.0105030265 |

## 8. Wrapper/Native Equivalence Result

-   The current production system is wrapper-based, not native.
-   `scripts/production_allocator.py` formalizes the wrapper as a first-class production component.
-   `scripts/test_production_pipeline_equivalence.py` compares the formal component against the legacy artifact-generation modifier and the stored production artifacts.

## 9. Validation Governance Updates

-   Experiment registry snapshot written with artifact classes and promotion statuses.
-   Gate status counts: `{'PASS': 7, 'WARN': 2}`
-   Candidates rejected for promotion by overfit-risk audit status: `311`

## 10. Dashboard Packaging Updates

-   Dashboard bundle verification passed: `True`
-   `npm run refresh:data` now runs `scripts/build_production_candidate_dashboard_bundle.py`.
-   Active README/UI references now point to compact dashboard bundles rather than the retired monolithic dashboard data file.

## 11. Documentation Updates

-   `docs/research/track_a_production_hardening.md` documents the production candidate, wrapper pipeline, data/timing assumptions, cost/turnover convention, metrics convention, holdout date, validation gates, limitations, and Track A scope.
-   `CLAUDE.md` now points future agents at the canonical Track A modules and scripts.

## 12. Tests Run And Results

| name | passed | returncode | command |
|----|----|----|----|
| canonical_metrics_cost_tests | True | 0 | /Users/nicholasturangan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/test_production_metrics_costs.py |
| wrapper_equivalence_tests | True | 0 | /Users/nicholasturangan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/test_production_pipeline_equivalence.py |
| production_reproduction | True | 0 | /Users/nicholasturangan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/reproduce_production_candidate.py |
| validation_governance | True | 0 | /Users/nicholasturangan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/run_track_a_validation_governance.py |
| dashboard_bundle_build | True | 0 | /Users/nicholasturangan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/build_production_candidate_dashboard_bundle.py |
| dashboard_packaging_verify | True | 0 | /Users/nicholasturangan/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/verify_dashboard_packaging.py |
| typescript_typecheck | True | 0 | npm run typecheck |
| next_production_build | True | 0 | npm run build |

## 13. Remaining Known Issues

-   The production strategy is still a wrapper/post-processor; a fully native allocator rebuild remains out of scope.
-   The sleeve-weight artifact remains a proxy because the production behavior is applied at final ETF weights.
-   The holdout has been repeatedly inspected across the research history and should not be treated as pristine.
-   The statistical validation audit found broad overfit risk; Track A reduces false confidence but does not prove a persistent alpha edge.
-   Historical research documents still mention old pins and old dashboard files as history; active runtime/docs now use compact production-candidate bundles.

## 14. Final Verdict

-   Production candidate reproducible: `True`
-   Metrics consistent: `True`
-   Costs consistent: `True`
-   Dashboard consistent: `True`
-   Ready for Track B research: `True`

Track A verdict: the conservative production artifact is now reproducible, auditable, registry-driven, and governed by explicit warnings. Future research should compare against this production pin without promoting new candidates automatically.
