# Stabilization Exact GGG Baseline

Research-only baseline lock for future deployment experiments.

- Official research baseline: `improved_phaseggg_confirmed_only_robust_offense`.
- Return alignment: `weekly_prices.pct_change().shift(-1)` on the allocation decision-date index.
- Weight timing: saved final ETF weights are applied to the next weekly return on the same decision date.
- Turnover method: one-way turnover `0.5 * sum(abs(diff(final_etf_weights)))`.
- Cost method: one-way turnover times `10.0` bps.
- State labels: `data/04_layer2b_risk_regime_engine/market_state_history.csv`.
- Future research must use this baseline because B7/B8 proved that return alignment and turnover conventions can dominate small signal edges.

## Exact Benchmark Metrics

| ann_return | ann_vol | sharpe | max_drawdown | calmar | cvar_5 | avg_turnover | cost_drag | avg_BIL | avg_SPY | avg_offense | avg_defense |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.0714 | 0.0762 | 0.9366 | -0.1177 | 0.6063 | -0.0254 | 0.0618 | 0.0686 | 0.2666 | 0.0603 | 0.4162 | 0.5447 |

## Exact Match Check

| net_return_corr_vs_saved | net_return_max_abs_error | turnover_max_abs_error | cost_max_abs_error | weeks_compared |
| --- | --- | --- | --- | --- |
| 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1110.0000 |

## Checkpoint Availability

| checkpoint | source_stage | available | rows | cols | safe_for_frontier_research | dangerous_without_allocator_hook |
| --- | --- | --- | --- | --- | --- | --- |
| raw_sleeve_targets | raw_hrp_sleeve_weights | True | 1110 | 7 | False | True |
| regime_multipliers | post_state_tilt_sleeve_weights | True | 1110 | 7 | True | False |
| offense_budget | post_layer3_expression_sleeve_weights | True | 1110 | 7 | True | False |
| defense_budget | post_layer3_expression_sleeve_weights | True | 1110 | 7 | False | True |
| cash_bil_budget | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 | True | False |
| transition_rerisk_smoothing | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 | True | False |
| derisk_smoothing | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 | True | False |
| volatility_risk_overlay | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 | True | False |
| final_etf_lookthrough_weights | final_etf_weights | True | 1110 | 35 | True | False |
| cost_turnover_calculation | final_etf_weights | True | 1110 | 35 | False | True |

## Warnings

- None.
