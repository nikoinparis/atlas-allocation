# Path 1 Deployment Location Report

Research-only deployment-location test. All variants use saved GGG weights as the reference and exact GGG return plumbing.

## Stage Exposure Diagnostics

| stage | rows | avg_cash | avg_offense | avg_defense | avg_total |
| --- | --- | --- | --- | --- | --- |
| raw_hrp_sleeve_weights | 1110 | 0.0694 | 0.3860 | 0.5446 | 1.0000 |
| post_state_tilt_sleeve_weights | 1110 | 0.0694 | 0.4094 | 0.5212 | 1.0000 |
| post_layer3_expression_sleeve_weights | 1110 | 0.0694 | 0.4094 | 0.5212 | 1.0000 |
| post_overlay_pre_lookthrough_sleeve_weights | 1110 | 0.2254 | 0.3424 | 0.4322 | 1.0000 |
| final_sleeve_weights | 1110 | 0.2254 | 0.3424 | 0.4322 | 1.0000 |
| final_etf_weights | 1110 | 0.2666 | 0.4162 | 0.5447 | 1.0000 |

## Variant Results

| variant | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | delta_sharpe_vs_exact_ggg | promising |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dollar_pressure_location_proxy | 0.0713 | 0.9382 | -0.1177 | -0.0253 | 0.0621 | 0.0016 | True |
| exact_ggg_reference | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 0.0000 | nan |
| regime_aware_scaling | 0.0712 | 0.9363 | -0.1177 | -0.0253 | 0.0627 | -0.0002 | True |
| defense_preserving_scaling | 0.0711 | 0.9355 | -0.1177 | -0.0253 | 0.0628 | -0.0011 | True |
| post_hoc_weight_scaling | 0.0717 | 0.9348 | -0.1185 | -0.0255 | 0.0635 | -0.0018 | True |
| offense_only_scaling | 0.0710 | 0.9342 | -0.1177 | -0.0253 | 0.0627 | -0.0024 | True |
| volatility_target_aware_scaling | 0.0711 | 0.9336 | -0.1182 | -0.0254 | 0.0632 | -0.0030 | True |
| sleeve_level_scaling_proxy | 0.0712 | 0.9329 | -0.1182 | -0.0254 | 0.0635 | -0.0037 | True |
| pre_overlay_proxy | 0.0710 | 0.9321 | -0.1182 | -0.0254 | 0.0636 | -0.0045 | True |

## Best Non-Reference Locations

| variant | deployment_location | ann_return | sharpe | delta_sharpe_vs_exact_ggg | delta_max_drawdown_vs_exact_ggg | delta_cvar_5_vs_exact_ggg |
| --- | --- | --- | --- | --- | --- | --- |
| dollar_pressure_location_proxy | dollar pressure location proxy | 0.0713 | 0.9382 | 0.0016 | 0.0001 | 0.0001 |
| regime_aware_scaling | regime aware scaling | 0.0712 | 0.9363 | -0.0002 | -0.0000 | 0.0001 |
| defense_preserving_scaling | defense preserving scaling | 0.0711 | 0.9355 | -0.0011 | -0.0000 | 0.0001 |
| post_hoc_weight_scaling | post hoc weight scaling | 0.0717 | 0.9348 | -0.0018 | -0.0007 | -0.0002 |
| offense_only_scaling | offense only scaling | 0.0710 | 0.9342 | -0.0024 | 0.0000 | 0.0000 |

## Interpretation

- Deployment location matters because post-overlay final-weight scaling is not equivalent to changing confidence before regime, target-vol, and recovery/neutral budget rules.
- The test is still a proxy: it does not rerun HRP or the production overlay engine, so pre-overlay and sleeve-level rows should be read as location diagnostics rather than production candidates.
- Exact GGG plumbing makes the comparison cleaner than B7/B8: remaining failures are deployment architecture failures, not return-alignment artifacts.

## Warnings

- None.
