# B6 Sprint Summary

Research-only narrow validation sprint for top breadth, gated macro, dollar-strength, and signal-quality candidates. No production/dashboard/allocation/R5/R6/live-trading files were changed.

## Commands Run

```bash
.venv/bin/python -m py_compile scripts/run_b6_unified_signal_validation.py scripts/run_b6_breadth_decomposition.py scripts/run_b6_gated_macro_decomposition.py
.venv/bin/python scripts/run_b6_unified_signal_validation.py
.venv/bin/python scripts/run_b6_breadth_decomposition.py
.venv/bin/python scripts/run_b6_gated_macro_decomposition.py
git status --short
git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv
```

## Robust Enough For Controlled Portfolio Pass-Through

_No rows._

## Best Offense Gate / Filter Candidates

| signal_name | category | intended_use | 2020_plus_avg_ic | calm_trend_avg_ic | stressed_panic_avg_ic | portfolio_usefulness_score |
| --- | --- | --- | --- | --- | --- | --- |
| r2_commodity_regime__recovery_only | gated_macro | macro_gate | 0.0993 | 0.2611 | 0.0301 | 6.6719 |
| bm_etf_above_50d_ma | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4817 |
| bm_etf_positive_13w_mom | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4395 |
| bm_etf_above_200d_ma | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4144 |
| bm_etf_positive_26w_mom | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4086 |
| bm_sector_positive_26w_mom | sector_breadth | offense_gate | 0.1200 | 0.1233 | 0.0801 | 6.2637 |
| bm_sector_above_200d_ma | sector_breadth | offense_gate | 0.1188 | 0.1233 | 0.0745 | 6.2238 |
| bm_sector_above_50d_ma | sector_breadth | offense_gate | 0.1187 | 0.1220 | 0.0649 | 6.1912 |
| bm_quality_breadth_confirmation | signal_quality | offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.1395 |
| r2_financial_conditions__recovery_only | gated_macro | macro_gate | 0.1973 | 0.0873 | 0.0417 | 6.1346 |

## Stress / Deterioration Warnings

- The cleanest stress/filter candidates are gated VIX term structure, gated credit spread, and dollar-strength 4w/blended.
- Breadth deterioration and thrust diagnostics remain useful for monitoring, but not robust enough for direct pass-through in this form.

## Too Redundant

| signal_name | max_abs_redundancy_existing | most_redundant_existing_signal |
| --- | --- | --- |
| bm_quality_signal_agreement | 0.8855 | moving_average_distance |

## Too Dangerous / Rejected

_No rows._

## Is Breadth Still The Strongest Frontier?

Yes. ETF and sector breadth remain the clearest frontier because they are interpretable, available from existing data, weekly-compatible, broadly positive in holdout, and less dependent on fragile macro gates.

## R5 Or Portfolio Pass-Through First?

Run a controlled portfolio pass-through test before R5 ensemble work. B6 is a signal validation sprint; the next step should test whether the best breadth and gate/filter candidates survive realistic portfolio plumbing without promotion.

## Exact Next Recommended Sprint

Run B7: controlled portfolio pass-through sandbox for the top B6 candidates only, with no production promotion. Compare alpha-style breadth additions versus offense-gate/risk-filter usage, isolate turnover/cost impact, and require state-level improvement before any R5 ensemble sprint.

## Production Safety

Production/dashboard safety must be confirmed by the final diff command. This summary is research-only and does not intentionally touch production/dashboard/public files.
