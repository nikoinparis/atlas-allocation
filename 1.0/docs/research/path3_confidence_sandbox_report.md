# Path 3 Confidence-Aware Sandbox Report

Research-only light sandbox using exact GGG return plumbing. The variants are bounded confidence modifiers, not allocator rewrites or R5 ensembles.

## Confidence Sandbox Results

| variant | family | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | delta_sharpe_vs_exact_ggg | promising_vs_exact_ggg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| p3_combined_confidence_modifier | confidence_sandbox | 0.0715 | 0.9395 | -0.1181 | -0.0253 | 0.0635 | 0.0029 | True |
| exact_ggg_reference | benchmark | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 0.0000 | True |
| p3_asymmetric_rerisking | confidence_sandbox | 0.0716 | 0.9365 | -0.1182 | -0.0255 | 0.0626 | -0.0001 | True |
| p3_confidence_offense_eligibility_mild | confidence_sandbox | 0.0713 | 0.9364 | -0.1177 | -0.0253 | 0.0625 | -0.0002 | True |
| p3_transition_aware_gating | confidence_sandbox | 0.0714 | 0.9364 | -0.1177 | -0.0254 | 0.0622 | -0.0002 | True |
| p3_confidence_bounded_scaling | confidence_sandbox | 0.0716 | 0.9360 | -0.1183 | -0.0255 | 0.0627 | -0.0006 | True |
| p3_deterioration_suppression | confidence_sandbox | 0.0711 | 0.9349 | -0.1177 | -0.0253 | 0.0628 | -0.0017 | True |
| phase2b_recomputed_reference | benchmark | 0.0689 | 0.8848 | -0.1398 | -0.0262 | 0.0562 | -0.0518 | False |

## Best Confidence Variant

| variant | ann_return | sharpe | max_drawdown | cvar_5 | holdout_2020_sharpe | shock_2022_sharpe | stressed_panic_sharpe | promising_vs_exact_ggg |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| p3_combined_confidence_modifier | 0.0715 | 0.9395 | -0.1181 | -0.0253 | 1.0803 | -0.2193 | 0.4809 | True |

## Prior B7/B8 Context

B7 best rows:

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 |
| --- | --- | --- | --- | --- | --- |
| b7_sector_breadth_gate | sector_breadth_gate | 0.0585 | 0.7742 | -0.1212 | -0.0259 |
| b7_combined_conservative_gate | combined | 0.0572 | 0.7713 | -0.1152 | -0.0255 |
| b7_dollar_pressure_blended_mild | dollar_filter | 0.0587 | 0.7712 | -0.1270 | -0.0261 |

B8 best rows:

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 |
| --- | --- | --- | --- | --- | --- |
| b8_market_quality_composite_mild | market_quality_composite | 0.0577 | 0.7686 | -0.1252 | -0.0257 |
| b8_recovery_safe_sector_gate | recovery_safe_gate | 0.0586 | 0.7683 | -0.1282 | -0.0262 |
| b8_market_quality_composite_medium | market_quality_composite | 0.0574 | 0.7681 | -0.1245 | -0.0255 |

## Interpretation

- Confidence-aware deployment is more coherent than naive breadth pass-through because it acts on eligibility and transition quality.
- A variant is only research-promising if it preserves GGG risk metrics under exact plumbing; no row is promoted by this script.
- If confidence variants still fail, the next sprint should move deeper into allocator-native overlay sequencing rather than adding more raw signals.

## Warnings

- None.
