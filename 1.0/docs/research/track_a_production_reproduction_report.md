# Track A Production Reproduction Report

## Official Candidate

- Production candidate: `improved_frontier_phase5_fragility_guard`
- Registry verified: `True`
- Pipeline: Wrapper-based production pipeline: saved GGG ETF weights -> Frontier Phase 5 offense-budget post-processor -> canonical one-way-turnover/10 bps cost path.
- Official holdout start: `2024-04-19`

## Exact Reproduction

- Weight max absolute error: `9.931e-17`
- Return/path max absolute error: `4.441e-16`
- Net return correlation: `1.000000000000`
- Exact reproduction tolerance: `1e-12`
- Reproduction passed: `True`

## Metric Convention Note

- Canonical Sharpe uses CAGR divided by sample annualized volatility (`ddof=1`).
- Some older helper code used population volatility (`ddof=0`), which slightly raises Sharpe for the same return series.

## Old vs Canonical Metrics

| metric | canonical | registry_summary | legacy_population_vol_formula | canonical_minus_registry | canonical_minus_legacy |
| --- | --- | --- | --- | --- | --- |
| ann_return | 0.07134169432 | 0.07134169432 | 0.07134169432 | -8.049116929e-16 | 0 |
| ann_vol | 0.07523466355 | 0.07523466355 | 0.07520076642 | -2.359223927e-16 | 3.389712429e-05 |
| sharpe | 0.9482556438 | 0.9482556438 | 0.9486830748 | -8.770761895e-15 | -0.0004274310083 |
| max_drawdown | -0.1160345789 | -0.1160345789 | -0.1160345789 | 2.220446049e-16 | 0 |
| cvar_5 | -0.02494792886 | -0.02494792886 | -0.02494792886 | -2.081668171e-17 | 0 |
| calmar | 0.6148313289 | 0.6148313289 |  | -6.439293543e-15 |  |
| avg_weekly_turnover | 0.06738780266 | 0.06738780266 | 0.06738780266 | -2.775557562e-17 | -2.775557562e-17 |
| holdout_ann_return | 0.1790929966 | 0.1790929966 | 0.1790929966 | -6.661338148e-16 | 0 |
| holdout_ann_vol | 0.08220610257 | 0.08220610257 | 0.08180992627 | -1.526556659e-16 | 0.0003961762942 |
| holdout_sharpe | 2.178585179 | 2.178585179 | 2.18913529 | -1.33226763e-15 | -0.01055011099 |
| holdout_max_drawdown | -0.07285258949 | -0.07285258949 | -0.07285258949 | 3.885780586e-16 | 0 |
| holdout_cvar_5 | -0.02300079828 | -0.02300079828 | -0.02300079828 | -2.081668171e-17 | 0 |

## Cost Sensitivity

| cost_multiplier | cost_bps_per_one_way_turnover | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | avg_weekly_turnover | annualized_turnover | annualized_cost | total_cost |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 10 | 0.07134169432 | 0.07523466355 | 0.9482556438 | -0.1160345789 | -0.02494792886 | 0.06738780266 | 3.504165738 | 0.003501008832 | 0.07473307315 |
| 2 | 20 | 0.06760219773 | 0.07523211873 | 0.8985816015 | -0.1160692953 | -0.02504028716 | 0.06738780266 | 3.504165738 | 0.007002017664 | 0.1494661463 |
| 3 | 30 | 0.06387482901 | 0.07523802524 | 0.8489700362 | -0.1161040112 | -0.02513264546 | 0.06738780266 | 3.504165738 | 0.0105030265 | 0.2241992194 |

## Artifacts

- `data/research/track_a_production_hardening/production_reproduction_report.json`
- `data/research/track_a_production_hardening/production_reproduction_metrics_comparison.csv`
- `data/research/track_a_production_hardening/production_cost_sensitivity.csv`
- `data/research/track_a_production_hardening/production_reproduction_return_diffs.csv`
