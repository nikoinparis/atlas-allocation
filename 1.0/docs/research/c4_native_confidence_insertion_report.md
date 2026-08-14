# C4 Native Confidence Insertion Report

Research-only allocator-native confidence insertion test using exact GGG return alignment and cost plumbing.

## Variants Tested

| variant | insertion_point |
| --- | --- |
| c4_regime_multiplier_confidence_offset | regime_multiplier_offset |
| c4_offensive_sleeve_budget_offset | offensive_sleeve_budget_offset |
| c4_transition_aware_rerisk_timing | rerisk_timing_offset |
| c4_deterioration_aware_derisk_timing | derisk_timing_offset |
| c4_combined_conservative_confidence_modifier | combined_native_offsets |
| c4_final_bounded_safety_check | final_post_allocation_modifier |

## Metrics

| variant | insertion_point | ann_return | ann_vol | sharpe | max_drawdown | cvar_5 | avg_turnover | avg_BIL | avg_SPY | avg_offense | holdout_2020_sharpe | stressed_panic_sharpe | acceptance_verdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c4_deterioration_aware_derisk_timing | derisk_timing_offset | 0.0707 | 0.0752 | 0.9410 | -0.1160 | -0.0250 | 0.0648 | 0.2765 | 0.0587 | 0.4063 | 1.0906 | 0.4805 | research-only |
| c4_final_bounded_safety_check | final_post_allocation_modifier | 0.0718 | 0.0763 | 0.9405 | -0.1166 | -0.0254 | 0.0631 | 0.2646 | 0.0606 | 0.4180 | 1.0834 | 0.4779 | promising |
| c4_regime_multiplier_confidence_offset | regime_multiplier_offset | 0.0716 | 0.0763 | 0.9390 | -0.1174 | -0.0254 | 0.0635 | 0.2652 | 0.0605 | 0.4179 | 1.0805 | 0.4730 | promising |
| c4_combined_conservative_confidence_modifier | combined_native_offsets | 0.0714 | 0.0762 | 0.9375 | -0.1158 | -0.0254 | 0.0632 | 0.2670 | 0.0604 | 0.4167 | 1.0860 | 0.4788 | promising |
| c4_transition_aware_rerisk_timing | rerisk_timing_offset | 0.0714 | 0.0762 | 0.9371 | -0.1177 | -0.0254 | 0.0623 | 0.2663 | 0.0603 | 0.4166 | 1.0839 | 0.4816 | promising |
| exact_ggg | benchmark_exact_ggg | 0.0714 | 0.0762 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 0.2666 | 0.0603 | 0.4162 | 1.0839 | 0.4817 | benchmark |
| c4_offensive_sleeve_budget_offset | offensive_sleeve_budget_offset | 0.0715 | 0.0764 | 0.9356 | -0.1180 | -0.0255 | 0.0628 | 0.2651 | 0.0605 | 0.4182 | 1.0789 | 0.4758 | promising |
| phase2b_pinned | benchmark_phase2b | 0.0689 | 0.0779 | 0.8848 | -0.1398 | -0.0262 | 0.0562 | 0.2839 | 0.0708 | 0.4283 | 0.9376 | 0.4978 | benchmark |

## Best Variant

| variant | insertion_point | ann_return | sharpe | delta_vs_exact_ggg_sharpe | max_drawdown | cvar_5 | stressed_panic_sharpe | acceptance_verdict | acceptance_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c4_deterioration_aware_derisk_timing | derisk_timing_offset | 0.0707 | 0.9410 | 0.0044 | -0.1160 | -0.0250 | 0.4805 | research-only | no accepted risk-adjusted improvement |

## State Detail

| variant | market_state | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover |
| --- | --- | --- | --- | --- | --- | --- |
| c4_combined_conservative_confidence_modifier | calm_trend | 0.0411 | 0.5161 | -0.1407 | -0.0271 | 0.0663 |
| c4_combined_conservative_confidence_modifier | neutral_mixed | 0.1123 | 1.4637 | -0.0921 | -0.0247 | 0.0604 |
| c4_combined_conservative_confidence_modifier | recovery_confirmed | 0.0266 | 0.3582 | -0.0539 | -0.0223 | 0.0868 |
| c4_combined_conservative_confidence_modifier | recovery_fragile | 0.0662 | 1.1428 | -0.0324 | -0.0172 | 0.1040 |
| c4_combined_conservative_confidence_modifier | stressed_panic | 0.0352 | 0.4788 | -0.1207 | -0.0229 | 0.0519 |
| c4_deterioration_aware_derisk_timing | calm_trend | 0.0405 | 0.5202 | -0.1371 | -0.0264 | 0.0694 |
| c4_deterioration_aware_derisk_timing | neutral_mixed | 0.1108 | 1.4706 | -0.0924 | -0.0242 | 0.0617 |
| c4_deterioration_aware_derisk_timing | recovery_confirmed | 0.0288 | 0.3949 | -0.0532 | -0.0218 | 0.0860 |
| c4_deterioration_aware_derisk_timing | recovery_fragile | 0.0639 | 1.1167 | -0.0326 | -0.0172 | 0.1039 |
| c4_deterioration_aware_derisk_timing | stressed_panic | 0.0357 | 0.4805 | -0.1217 | -0.0231 | 0.0529 |
| c4_final_bounded_safety_check | calm_trend | 0.0412 | 0.5174 | -0.1400 | -0.0271 | 0.0658 |
| c4_final_bounded_safety_check | neutral_mixed | 0.1132 | 1.4668 | -0.0923 | -0.0248 | 0.0603 |
| c4_final_bounded_safety_check | recovery_confirmed | 0.0266 | 0.3556 | -0.0546 | -0.0223 | 0.0870 |
| c4_final_bounded_safety_check | recovery_fragile | 0.0668 | 1.1500 | -0.0324 | -0.0172 | 0.1047 |
| c4_final_bounded_safety_check | stressed_panic | 0.0349 | 0.4779 | -0.1208 | -0.0228 | 0.0521 |
| c4_offensive_sleeve_budget_offset | calm_trend | 0.0407 | 0.5096 | -0.1410 | -0.0272 | 0.0658 |
| c4_offensive_sleeve_budget_offset | neutral_mixed | 0.1128 | 1.4652 | -0.0924 | -0.0248 | 0.0599 |
| c4_offensive_sleeve_budget_offset | recovery_confirmed | 0.0263 | 0.3532 | -0.0544 | -0.0223 | 0.0870 |
| c4_offensive_sleeve_budget_offset | recovery_fragile | 0.0665 | 1.1479 | -0.0324 | -0.0172 | 0.1038 |
| c4_offensive_sleeve_budget_offset | stressed_panic | 0.0351 | 0.4758 | -0.1216 | -0.0230 | 0.0518 |
| c4_regime_multiplier_confidence_offset | calm_trend | 0.0411 | 0.5158 | -0.1405 | -0.0271 | 0.0660 |
| c4_regime_multiplier_confidence_offset | neutral_mixed | 0.1131 | 1.4674 | -0.0925 | -0.0248 | 0.0608 |
| c4_regime_multiplier_confidence_offset | recovery_confirmed | 0.0265 | 0.3551 | -0.0545 | -0.0223 | 0.0872 |
| c4_regime_multiplier_confidence_offset | recovery_fragile | 0.0666 | 1.1478 | -0.0324 | -0.0172 | 0.1062 |
| c4_regime_multiplier_confidence_offset | stressed_panic | 0.0345 | 0.4730 | -0.1216 | -0.0228 | 0.0524 |
| c4_transition_aware_rerisk_timing | calm_trend | 0.0408 | 0.5136 | -0.1395 | -0.0270 | 0.0654 |
| c4_transition_aware_rerisk_timing | neutral_mixed | 0.1122 | 1.4640 | -0.0912 | -0.0247 | 0.0593 |
| c4_transition_aware_rerisk_timing | recovery_confirmed | 0.0268 | 0.3621 | -0.0536 | -0.0221 | 0.0872 |
| c4_transition_aware_rerisk_timing | recovery_fragile | 0.0666 | 1.1511 | -0.0322 | -0.0172 | 0.1035 |
| c4_transition_aware_rerisk_timing | stressed_panic | 0.0358 | 0.4816 | -0.1216 | -0.0231 | 0.0514 |
| exact_ggg | calm_trend | 0.0409 | 0.5145 | -0.1393 | -0.0270 | 0.0650 |
| exact_ggg | neutral_mixed | 0.1121 | 1.4630 | -0.0912 | -0.0247 | 0.0587 |
| exact_ggg | recovery_confirmed | 0.0257 | 0.3482 | -0.0538 | -0.0221 | 0.0858 |
| exact_ggg | recovery_fragile | 0.0667 | 1.1540 | -0.0322 | -0.0171 | 0.1021 |
| exact_ggg | stressed_panic | 0.0358 | 0.4817 | -0.1216 | -0.0231 | 0.0513 |
| phase2b_pinned | calm_trend | 0.0356 | 0.3849 | -0.1647 | -0.0312 | 0.0622 |
| phase2b_pinned | neutral_mixed | 0.1104 | 1.4637 | -0.0897 | -0.0239 | 0.0517 |
| phase2b_pinned | recovery_confirmed | 0.0261 | 0.3891 | -0.0497 | -0.0203 | 0.0577 |
| phase2b_pinned | recovery_fragile | 0.0697 | 1.3305 | -0.0309 | -0.0148 | 0.0952 |
| phase2b_pinned | stressed_panic | 0.0337 | 0.4978 | -0.1208 | -0.0207 | 0.0496 |

## Interpretation

- Exact GGG baseline row present: yes.
- Variants passing the strict C5 acceptance gate: 5.
- Improvements are treated as research evidence only and are not production promotions.

## Warnings

- None.
