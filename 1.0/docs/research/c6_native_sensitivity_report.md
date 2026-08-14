# C6 Native Sensitivity Report

Small one-at-a-time sensitivity checks for the top three C4 variants. This is not a broad parameter search.

## Sensitivity Summary

| variant | scenarios | sharpe_median | sharpe_min | sharpe_max | holdout_2020_sharpe_min | stressed_panic_sharpe_min | max_drawdown_min | cvar_5_min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c4_combined_conservative_confidence_modifier | 8 | 0.9375 | 0.9368 | 0.9388 | 1.0853 | 0.4787 | -0.1158 | -0.0255 |
| c4_final_bounded_safety_check | 8 | 0.9405 | 0.9393 | 0.9405 | 1.0834 | 0.4779 | -0.1168 | -0.0255 |
| c4_regime_multiplier_confidence_offset | 8 | 0.9389 | 0.9370 | 0.9399 | 1.0803 | 0.4728 | -0.1177 | -0.0255 |

## Scenario Detail

| variant | scenario | max_offense_increase | max_offense_reduction | transition_boost | deterioration_cut | ann_return | sharpe | max_drawdown | cvar_5 | holdout_2020_sharpe | stressed_panic_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c4_combined_conservative_confidence_modifier | max_inc_0pct | 0.0000 | 0.0700 | mild | medium | 0.0711 | 0.9388 | -0.1158 | -0.0252 | 1.0866 | 0.4790 |
| c4_combined_conservative_confidence_modifier | max_inc_2pct | 0.0200 | 0.0700 | mild | medium | 0.0713 | 0.9378 | -0.1158 | -0.0253 | 1.0863 | 0.4789 |
| c4_combined_conservative_confidence_modifier | max_red_3pct | 0.0300 | 0.0300 | mild | mild | 0.0715 | 0.9375 | -0.1158 | -0.0254 | 1.0865 | 0.4817 |
| c4_combined_conservative_confidence_modifier | base | 0.0300 | 0.0700 | mild | medium | 0.0714 | 0.9375 | -0.1158 | -0.0254 | 1.0860 | 0.4788 |
| c4_combined_conservative_confidence_modifier | transition_medium | 0.0300 | 0.0700 | medium | medium | 0.0714 | 0.9375 | -0.1158 | -0.0254 | 1.0860 | 0.4788 |
| c4_combined_conservative_confidence_modifier | deterioration_mild | 0.0300 | 0.0700 | mild | mild | 0.0714 | 0.9375 | -0.1158 | -0.0254 | 1.0860 | 0.4788 |
| c4_combined_conservative_confidence_modifier | max_red_5pct | 0.0300 | 0.0500 | mild | medium | 0.0714 | 0.9374 | -0.1158 | -0.0254 | 1.0862 | 0.4803 |
| c4_combined_conservative_confidence_modifier | max_inc_5pct | 0.0500 | 0.0700 | mild | medium | 0.0716 | 0.9368 | -0.1158 | -0.0255 | 1.0853 | 0.4787 |
| c4_final_bounded_safety_check | base | 0.0300 | 0.0700 | mild | medium | 0.0718 | 0.9405 | -0.1166 | -0.0254 | 1.0834 | 0.4779 |
| c4_final_bounded_safety_check | max_inc_5pct | 0.0500 | 0.0700 | mild | medium | 0.0718 | 0.9405 | -0.1166 | -0.0254 | 1.0834 | 0.4779 |
| c4_final_bounded_safety_check | max_red_5pct | 0.0300 | 0.0500 | mild | medium | 0.0718 | 0.9405 | -0.1166 | -0.0254 | 1.0834 | 0.4779 |
| c4_final_bounded_safety_check | transition_medium | 0.0300 | 0.0700 | medium | medium | 0.0718 | 0.9405 | -0.1166 | -0.0254 | 1.0834 | 0.4779 |
| c4_final_bounded_safety_check | deterioration_mild | 0.0300 | 0.0700 | mild | mild | 0.0718 | 0.9405 | -0.1166 | -0.0254 | 1.0834 | 0.4779 |
| c4_final_bounded_safety_check | max_red_3pct | 0.0300 | 0.0300 | mild | mild | 0.0719 | 0.9403 | -0.1166 | -0.0255 | 1.0841 | 0.4803 |
| c4_final_bounded_safety_check | max_inc_2pct | 0.0200 | 0.0700 | mild | medium | 0.0716 | 0.9400 | -0.1167 | -0.0254 | 1.0836 | 0.4780 |
| c4_final_bounded_safety_check | max_inc_0pct | 0.0000 | 0.0700 | mild | medium | 0.0712 | 0.9393 | -0.1168 | -0.0253 | 1.0838 | 0.4782 |
| c4_regime_multiplier_confidence_offset | max_inc_5pct | 0.0500 | 0.0700 | mild | medium | 0.0720 | 0.9399 | -0.1172 | -0.0255 | 1.0803 | 0.4728 |
| c4_regime_multiplier_confidence_offset | base | 0.0300 | 0.0700 | mild | medium | 0.0716 | 0.9390 | -0.1174 | -0.0254 | 1.0805 | 0.4730 |
| c4_regime_multiplier_confidence_offset | transition_medium | 0.0300 | 0.0700 | medium | medium | 0.0716 | 0.9390 | -0.1174 | -0.0254 | 1.0805 | 0.4730 |
| c4_regime_multiplier_confidence_offset | deterioration_mild | 0.0300 | 0.0700 | mild | mild | 0.0716 | 0.9390 | -0.1174 | -0.0254 | 1.0805 | 0.4730 |
| c4_regime_multiplier_confidence_offset | max_red_5pct | 0.0300 | 0.0500 | mild | medium | 0.0717 | 0.9389 | -0.1174 | -0.0255 | 1.0815 | 0.4755 |
| c4_regime_multiplier_confidence_offset | max_red_3pct | 0.0300 | 0.0300 | mild | mild | 0.0718 | 0.9388 | -0.1174 | -0.0255 | 1.0824 | 0.4779 |
| c4_regime_multiplier_confidence_offset | max_inc_2pct | 0.0200 | 0.0700 | mild | medium | 0.0714 | 0.9385 | -0.1175 | -0.0254 | 1.0806 | 0.4731 |
| c4_regime_multiplier_confidence_offset | max_inc_0pct | 0.0000 | 0.0700 | mild | medium | 0.0710 | 0.9370 | -0.1177 | -0.0253 | 1.0807 | 0.4733 |

## Warnings

- None.
