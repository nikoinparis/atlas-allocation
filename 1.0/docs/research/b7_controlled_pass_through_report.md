# B7 Controlled Pass-Through Report

Research-only post-hoc sandbox using saved GGG ETF weights. No production allocation logic was modified.

- Output directory: `data/research/b7_pass_through`
- Benchmark mismatch: registry keeps Phase2B as current production/rollback while GGG is pending dashboard production candidate; B7 compares against both.

## Variants Tested

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | full_avg_turnover | delta_sharpe_vs_ggg_dashboard | b7_verdict | b7_verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| b7_sector_breadth_gate | sector_breadth_gate | 0.0585 | 0.7742 | -0.1212 | -0.0259 | 0.1264 | -0.1624 | research-only | Sharpe worsened vs GGG |
| b7_combined_conservative_gate | combined | 0.0572 | 0.7713 | -0.1152 | -0.0255 | 0.1351 | -0.1653 | research-only | Sharpe worsened vs GGG |
| b7_dollar_pressure_blended_mild | dollar_filter | 0.0587 | 0.7712 | -0.1270 | -0.0261 | 0.1247 | -0.1654 | research-only | Sharpe worsened vs GGG; max drawdown worsened vs GGG |
| b7_dollar_pressure_4w_mild | dollar_filter | 0.0586 | 0.7695 | -0.1270 | -0.0261 | 0.1262 | -0.1671 | research-only | Sharpe worsened vs GGG; max drawdown worsened vs GGG |
| b7_macro_stress_filter_mild | macro_filter | 0.0570 | 0.7692 | -0.1173 | -0.0254 | 0.1312 | -0.1674 | research-only | Sharpe worsened vs GGG |
| b7_macro_stress_filter_medium | macro_filter | 0.0561 | 0.7683 | -0.1124 | -0.0251 | 0.1360 | -0.1683 | research-only | Sharpe worsened vs GGG |
| b7_breadth_gate_50d | breadth_gate | 0.0574 | 0.7669 | -0.1212 | -0.0258 | 0.1303 | -0.1697 | research-only | Sharpe worsened vs GGG |
| b7_breadth_scaler_composite | breadth_scaler | 0.0590 | 0.7658 | -0.1250 | -0.0265 | 0.1304 | -0.1708 | research-only | Sharpe worsened vs GGG; max drawdown worsened vs GGG; CVaR worsened vs GGG |
| b7_risk_on_participation_gate | risk_on_gate | 0.0577 | 0.7655 | -0.1212 | -0.0259 | 0.1286 | -0.1710 | research-only | Sharpe worsened vs GGG |
| b7_breadth_gate_13w | breadth_gate | 0.0575 | 0.7636 | -0.1212 | -0.0259 | 0.1282 | -0.1730 | research-only | Sharpe worsened vs GGG |

## State Summary

| variant | market_state | ann_return | sharpe | max_drawdown | cvar_5 |
| --- | --- | --- | --- | --- | --- |
| b7_breadth_gate_13w | calm_trend | 0.0778 | 1.0162 | -0.0881 | -0.0251 |
| b7_breadth_gate_13w | neutral_mixed | 0.0478 | 0.6155 | -0.1124 | -0.0270 |
| b7_breadth_gate_13w | recovery_confirmed | 0.1873 | 3.8661 | -0.0256 | -0.0098 |
| b7_breadth_gate_13w | recovery_fragile | 0.1574 | 3.0221 | -0.0139 | -0.0109 |
| b7_breadth_gate_13w | stressed_panic | 0.0096 | 0.1259 | -0.1160 | -0.0262 |
| b7_breadth_gate_50d | calm_trend | 0.0763 | 1.0027 | -0.0894 | -0.0251 |
| b7_breadth_gate_50d | neutral_mixed | 0.0481 | 0.6248 | -0.1124 | -0.0267 |
| b7_breadth_gate_50d | recovery_confirmed | 0.1844 | 3.8543 | -0.0256 | -0.0098 |
| b7_breadth_gate_50d | recovery_fragile | 0.1583 | 3.0547 | -0.0139 | -0.0109 |
| b7_breadth_gate_50d | stressed_panic | 0.0106 | 0.1394 | -0.1160 | -0.0262 |
| b7_breadth_scaler_composite | calm_trend | 0.0800 | 1.0237 | -0.0884 | -0.0255 |
| b7_breadth_scaler_composite | neutral_mixed | 0.0492 | 0.6145 | -0.1132 | -0.0277 |
| b7_breadth_scaler_composite | recovery_confirmed | 0.1938 | 3.8939 | -0.0264 | -0.0102 |
| b7_breadth_scaler_composite | recovery_fragile | 0.1627 | 3.0866 | -0.0139 | -0.0111 |
| b7_breadth_scaler_composite | stressed_panic | 0.0092 | 0.1190 | -0.1178 | -0.0267 |
| b7_combined_conservative_gate | calm_trend | 0.0777 | 1.0199 | -0.0880 | -0.0250 |
| b7_combined_conservative_gate | neutral_mixed | 0.0470 | 0.6133 | -0.1099 | -0.0264 |
| b7_combined_conservative_gate | recovery_confirmed | 0.1841 | 3.8659 | -0.0256 | -0.0095 |
| b7_combined_conservative_gate | recovery_fragile | 0.1554 | 3.0406 | -0.0139 | -0.0105 |
| b7_combined_conservative_gate | stressed_panic | 0.0109 | 0.1482 | -0.1136 | -0.0253 |
| b7_dollar_pressure_4w_mild | calm_trend | 0.0789 | 1.0329 | -0.0887 | -0.0249 |
| b7_dollar_pressure_4w_mild | neutral_mixed | 0.0495 | 0.6325 | -0.1145 | -0.0270 |
| b7_dollar_pressure_4w_mild | recovery_confirmed | 0.1874 | 3.8749 | -0.0256 | -0.0098 |
| b7_dollar_pressure_4w_mild | recovery_fragile | 0.1599 | 3.0684 | -0.0139 | -0.0109 |
| b7_dollar_pressure_4w_mild | stressed_panic | 0.0092 | 0.1173 | -0.1231 | -0.0274 |
| b7_dollar_pressure_blended_mild | calm_trend | 0.0794 | 1.0405 | -0.0887 | -0.0249 |
| b7_dollar_pressure_blended_mild | neutral_mixed | 0.0492 | 0.6278 | -0.1144 | -0.0270 |
| b7_dollar_pressure_blended_mild | recovery_confirmed | 0.1883 | 3.8747 | -0.0256 | -0.0098 |
| b7_dollar_pressure_blended_mild | recovery_fragile | 0.1600 | 3.0732 | -0.0139 | -0.0109 |
| b7_dollar_pressure_blended_mild | stressed_panic | 0.0097 | 0.1231 | -0.1231 | -0.0273 |

## Interpretation

- Best variant by B7 screen: `b7_sector_breadth_gate`.
- Beat GGG on Sharpe: False.
- Variants are post-hoc weight transformations and should be treated as plumbing tests only.

## Warnings

- Registry mismatch confirmed: Phase2B remains current production/rollback pin while GGG is pending dashboard production candidate. B7 compares against both.
