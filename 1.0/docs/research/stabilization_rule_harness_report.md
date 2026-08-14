# Stabilization Rule Harness Report

Research-only standardized test suite over the no-write checkpoint wrapper and deployment rule library.

## Exact Baseline Check

| net_return_corr_vs_saved | net_return_max_abs_error | turnover_max_abs_error | cost_max_abs_error | weeks_compared |
| --- | --- | --- | --- | --- |
| 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1110.0000 |

## Harness Results

| variant | rule | checkpoint | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | avg_turnover | avg_BIL | avg_offense | holdout_2020_sharpe | y2022_sharpe | stressed_panic_sharpe | architecture_valid |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dollar_pressure_at_offense_budget | dollar_pressure | offense_budget | 0.0712 | 0.0755 | 0.9430 | -0.1146 | -0.0251 | 0.0630 | 0.2718 | 0.4110 | 1.0934 | -0.1971 | 0.4885 | True |
| combined_conservative_at_overlay | combined_conservative | volatility_risk_overlay | 0.0715 | 0.0762 | 0.9385 | -0.1172 | -0.0254 | 0.0626 | 0.2663 | 0.4169 | 1.0825 | -0.2098 | 0.4755 | True |
| breadth_confirmation_at_regime_multiplier | breadth_confirmation | regime_multipliers | 0.0708 | 0.0755 | 0.9373 | -0.1163 | -0.0252 | 0.0639 | 0.2731 | 0.4130 | 1.0758 | -0.2014 | 0.4752 | True |
| deterioration_acceleration_at_derisk | deterioration_acceleration | derisk_smoothing | 0.0709 | 0.0756 | 0.9371 | -0.1144 | -0.0252 | 0.0631 | 0.2710 | 0.4143 | 1.0886 | -0.2149 | 0.4807 | True |
| no_modifier_baseline | none | none | 0.0714 | 0.0762 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 0.2666 | 0.4162 | 1.0839 | -0.2133 | 0.4817 | True |
| transition_quality_rerisk_at_smoothing | transition_quality_rerisk | transition_rerisk_smoothing | 0.0716 | 0.0765 | 0.9363 | -0.1181 | -0.0255 | 0.0624 | 0.2643 | 0.4190 | 1.0801 | -0.2131 | 0.4816 | True |
| macro_stress_at_regime_multiplier | macro_stress | regime_multipliers | 0.0704 | 0.0752 | 0.9351 | -0.1107 | -0.0251 | 0.0639 | 0.2734 | 0.4127 | 1.1009 | -0.2133 | 0.4863 | True |
| offense_eligibility_at_offense_budget | offense_eligibility | offense_budget | 0.0708 | 0.0757 | 0.9351 | -0.1147 | -0.0252 | 0.0623 | 0.2708 | 0.4120 | 1.0907 | -0.2084 | 0.4836 | True |

## State Summary

| variant | market_state | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover |
| --- | --- | --- | --- | --- | --- | --- |
| breadth_confirmation_at_regime_multiplier | calm_trend | 0.0403 | 0.5076 | -0.1401 | -0.0271 | 0.0676 |
| breadth_confirmation_at_regime_multiplier | neutral_mixed | 0.1119 | 1.4737 | -0.0908 | -0.0244 | 0.0609 |
| breadth_confirmation_at_regime_multiplier | recovery_confirmed | 0.0258 | 0.3467 | -0.0541 | -0.0222 | 0.0892 |
| breadth_confirmation_at_regime_multiplier | recovery_fragile | 0.0655 | 1.1394 | -0.0317 | -0.0170 | 0.1092 |
| breadth_confirmation_at_regime_multiplier | stressed_panic | 0.0344 | 0.4752 | -0.1199 | -0.0226 | 0.0511 |
| combined_conservative_at_overlay | calm_trend | 0.0411 | 0.5158 | -0.1398 | -0.0271 | 0.0653 |
| combined_conservative_at_overlay | neutral_mixed | 0.1126 | 1.4663 | -0.0919 | -0.0247 | 0.0597 |
| combined_conservative_at_overlay | recovery_confirmed | 0.0261 | 0.3510 | -0.0543 | -0.0222 | 0.0865 |
| combined_conservative_at_overlay | recovery_fragile | 0.0670 | 1.1583 | -0.0319 | -0.0171 | 0.1040 |
| combined_conservative_at_overlay | stressed_panic | 0.0348 | 0.4755 | -0.1212 | -0.0229 | 0.0518 |
| deterioration_acceleration_at_derisk | calm_trend | 0.0407 | 0.5133 | -0.1394 | -0.0270 | 0.0656 |
| deterioration_acceleration_at_derisk | neutral_mixed | 0.1115 | 1.4616 | -0.0912 | -0.0246 | 0.0597 |
| deterioration_acceleration_at_derisk | recovery_confirmed | 0.0253 | 0.3426 | -0.0538 | -0.0221 | 0.0865 |
| deterioration_acceleration_at_derisk | recovery_fragile | 0.0675 | 1.1739 | -0.0313 | -0.0169 | 0.1055 |
| deterioration_acceleration_at_derisk | stressed_panic | 0.0347 | 0.4807 | -0.1184 | -0.0225 | 0.0537 |
| dollar_pressure_at_offense_budget | calm_trend | 0.0408 | 0.5195 | -0.1378 | -0.0266 | 0.0668 |
| dollar_pressure_at_offense_budget | neutral_mixed | 0.1115 | 1.4668 | -0.0918 | -0.0245 | 0.0600 |
| dollar_pressure_at_offense_budget | recovery_confirmed | 0.0276 | 0.3763 | -0.0538 | -0.0219 | 0.0862 |
| dollar_pressure_at_offense_budget | recovery_fragile | 0.0668 | 1.1581 | -0.0319 | -0.0171 | 0.1024 |
| dollar_pressure_at_offense_budget | stressed_panic | 0.0360 | 0.4885 | -0.1199 | -0.0228 | 0.0517 |
| macro_stress_at_regime_multiplier | calm_trend | 0.0407 | 0.5137 | -0.1402 | -0.0269 | 0.0669 |
| macro_stress_at_regime_multiplier | neutral_mixed | 0.1104 | 1.4542 | -0.0908 | -0.0245 | 0.0614 |
| macro_stress_at_regime_multiplier | recovery_confirmed | 0.0255 | 0.3461 | -0.0532 | -0.0221 | 0.0864 |
| macro_stress_at_regime_multiplier | recovery_fragile | 0.0662 | 1.1572 | -0.0316 | -0.0168 | 0.1054 |
| macro_stress_at_regime_multiplier | stressed_panic | 0.0348 | 0.4863 | -0.1154 | -0.0223 | 0.0524 |
| no_modifier_baseline | calm_trend | 0.0409 | 0.5145 | -0.1393 | -0.0270 | 0.0650 |
| no_modifier_baseline | neutral_mixed | 0.1121 | 1.4630 | -0.0912 | -0.0247 | 0.0587 |
| no_modifier_baseline | recovery_confirmed | 0.0257 | 0.3482 | -0.0538 | -0.0221 | 0.0858 |
| no_modifier_baseline | recovery_fragile | 0.0667 | 1.1540 | -0.0322 | -0.0171 | 0.1021 |
| no_modifier_baseline | stressed_panic | 0.0358 | 0.4817 | -0.1216 | -0.0231 | 0.0513 |
| offense_eligibility_at_offense_budget | calm_trend | 0.0406 | 0.5122 | -0.1403 | -0.0269 | 0.0661 |
| offense_eligibility_at_offense_budget | neutral_mixed | 0.1112 | 1.4610 | -0.0912 | -0.0246 | 0.0593 |
| offense_eligibility_at_offense_budget | recovery_confirmed | 0.0259 | 0.3526 | -0.0538 | -0.0220 | 0.0857 |
| offense_eligibility_at_offense_budget | recovery_fragile | 0.0651 | 1.1328 | -0.0323 | -0.0171 | 0.1019 |
| offense_eligibility_at_offense_budget | stressed_panic | 0.0354 | 0.4836 | -0.1197 | -0.0228 | 0.0511 |
| transition_quality_rerisk_at_smoothing | calm_trend | 0.0408 | 0.5117 | -0.1400 | -0.0271 | 0.0653 |
| transition_quality_rerisk_at_smoothing | neutral_mixed | 0.1127 | 1.4639 | -0.0916 | -0.0248 | 0.0594 |
| transition_quality_rerisk_at_smoothing | recovery_confirmed | 0.0263 | 0.3530 | -0.0542 | -0.0223 | 0.0866 |
| transition_quality_rerisk_at_smoothing | recovery_fragile | 0.0665 | 1.1467 | -0.0324 | -0.0172 | 0.1036 |
| transition_quality_rerisk_at_smoothing | stressed_panic | 0.0358 | 0.4816 | -0.1216 | -0.0231 | 0.0515 |

## Modifier Logs

| variant | modifier | checkpoint | modifier_min | modifier_mean | modifier_max | avg_abs_weight_change | max_abs_weight_change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| offense_eligibility_at_offense_budget | offense_eligibility | offense_budget | 0.9700 | 0.9857 | 1.0000 | 0.0085 | 0.0551 |
| breadth_confirmation_at_regime_multiplier | breadth_confirmation | regime_multipliers | 0.9600 | 0.9897 | 1.0100 | 0.0209 | 0.0800 |
| transition_quality_rerisk_at_smoothing | transition_quality_rerisk | transition_rerisk_smoothing | 0.9850 | 1.0063 | 1.0150 | 0.0059 | 0.0268 |
| deterioration_acceleration_at_derisk | deterioration_acceleration | derisk_smoothing | 0.9300 | 0.9919 | 1.0000 | 0.0089 | 0.1400 |
| dollar_pressure_at_offense_budget | dollar_pressure | offense_budget | 0.9500 | 0.9870 | 1.0000 | 0.0104 | 0.0904 |
| macro_stress_at_regime_multiplier | macro_stress | regime_multipliers | 0.9400 | 0.9904 | 1.0000 | 0.0137 | 0.1200 |
| combined_conservative_at_overlay | combined_conservative | volatility_risk_overlay | 0.9569 | 0.9998 | 1.0161 | 0.0111 | 0.0768 |

## Warnings

- None.
