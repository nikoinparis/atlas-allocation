# Deployment Architecture Stabilization Summary

## Answers

1. Does the wrapper reproduce exact GGG? `True`.
2. Safe checkpoints for future research: `regime_multipliers`, `offense_budget`, `cash_bil_budget`, `transition_rerisk_smoothing`, `derisk_smoothing`, `volatility_risk_overlay`, and `final_etf_lookthrough_weights` for comparison only.
3. Dangerous checkpoints: `raw_sleeve_targets`, `defense_budget`, and `cost_turnover_calculation` without a deeper allocator hook.
4. Architecture-valid rules: offense_eligibility, breadth_confirmation, transition_quality_rerisk, deterioration_acceleration, dollar_pressure, macro_stress, combined_conservative.
5. Use future rules at offense, regime/overlay, transition, and de-risk checkpoints before any ensemble work.
6. Stable enough for frontier research: `True`.
7. Exact next sprint: allocator-native transition-quality/re-risk model using this wrapper and no-write allocator checkpoint logs.
8. Production/dashboard files changed: no scripts in this sprint write those paths.

## Safe Checkpoints

| checkpoint | source_stage | available | rows | cols |
| --- | --- | --- | --- | --- |
| regime_multipliers | post_state_tilt_sleeve_weights | True | 1110 | 7 |
| offense_budget | post_layer3_expression_sleeve_weights | True | 1110 | 7 |
| cash_bil_budget | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 |
| transition_rerisk_smoothing | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 |
| derisk_smoothing | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 |
| volatility_risk_overlay | post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 |
| final_etf_lookthrough_weights | final_etf_weights | True | 1110 | 35 |

## Dangerous Checkpoints

| checkpoint | source_stage | available | rows | cols |
| --- | --- | --- | --- | --- |
| raw_sleeve_targets | raw_hrp_sleeve_weights | True | 1110 | 7 |
| defense_budget | post_layer3_expression_sleeve_weights | True | 1110 | 7 |
| cost_turnover_calculation | final_etf_weights | True | 1110 | 35 |

## Rule Results

| variant | rule | checkpoint | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | stressed_panic_sharpe | architecture_valid | architecture_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dollar_pressure_at_offense_budget | dollar_pressure | offense_budget | 0.0712 | 0.9430 | -0.1146 | -0.0251 | 0.0630 | 0.4885 | True | Architecture-valid. |
| combined_conservative_at_overlay | combined_conservative | volatility_risk_overlay | 0.0715 | 0.9385 | -0.1172 | -0.0254 | 0.0626 | 0.4755 | True | Architecture-valid. |
| breadth_confirmation_at_regime_multiplier | breadth_confirmation | regime_multipliers | 0.0708 | 0.9373 | -0.1163 | -0.0252 | 0.0639 | 0.4752 | True | Architecture-valid. |
| deterioration_acceleration_at_derisk | deterioration_acceleration | derisk_smoothing | 0.0709 | 0.9371 | -0.1144 | -0.0252 | 0.0631 | 0.4807 | True | Architecture-valid. |
| no_modifier_baseline | none | none | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 0.4817 | True | Exact no-modifier baseline. |
| transition_quality_rerisk_at_smoothing | transition_quality_rerisk | transition_rerisk_smoothing | 0.0716 | 0.9363 | -0.1181 | -0.0255 | 0.0624 | 0.4816 | True | Architecture-valid. |
| macro_stress_at_regime_multiplier | macro_stress | regime_multipliers | 0.0704 | 0.9351 | -0.1107 | -0.0251 | 0.0639 | 0.4863 | True | Architecture-valid. |
| offense_eligibility_at_offense_budget | offense_eligibility | offense_budget | 0.0708 | 0.9351 | -0.1147 | -0.0252 | 0.0623 | 0.4836 | True | Architecture-valid. |

## Invalid Rules

_No rows._

## Warnings

- None.
