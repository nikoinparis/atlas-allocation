# B8 Bounded Refinement Report

Research-only bounded deployment refinement. Variants are post-hoc transformations of saved GGG weights.

- Output directory: `data/research/b8_bounded_refinement`
- Best variant: `b8_market_quality_composite_mild`

## Variant Metrics

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | full_avg_turnover | delta_sharpe_vs_ggg_dashboard | b8_verdict | b8_verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| b8_market_quality_composite_mild | market_quality_composite | 0.0577 | 0.7686 | -0.1252 | -0.0257 | 0.1328 | -0.1680 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp |
| b8_recovery_safe_sector_gate | recovery_safe_gate | 0.0586 | 0.7683 | -0.1282 | -0.0262 | 0.1263 | -0.1683 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |
| b8_market_quality_composite_medium | market_quality_composite | 0.0574 | 0.7681 | -0.1245 | -0.0255 | 0.1350 | -0.1685 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp |
| b8_soft_etf_breadth_95_103 | soft_scaler | 0.0588 | 0.7665 | -0.1287 | -0.0263 | 0.1256 | -0.1701 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |
| b8_sector_soft_95_103 | sector_breadth_only | 0.0589 | 0.7662 | -0.1288 | -0.0264 | 0.1260 | -0.1704 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |
| b8_calm_neutral_confirmation | calm_only_confirmation | 0.0583 | 0.7659 | -0.1282 | -0.0261 | 0.1258 | -0.1707 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |
| b8_asymmetric_breadth_gate | asymmetric_breadth_gate | 0.0584 | 0.7653 | -0.1282 | -0.0262 | 0.1251 | -0.1713 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |
| b8_soft_etf_breadth_90_105 | soft_scaler | 0.0588 | 0.7651 | -0.1291 | -0.0264 | 0.1270 | -0.1715 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |
| b8_sector_soft_90_105 | sector_breadth_only | 0.0590 | 0.7646 | -0.1291 | -0.0264 | 0.1278 | -0.1720 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp; CVaR worse than GGG by more than 0.05pp |

## State Summary

| variant | market_state | ann_return | sharpe | max_drawdown | cvar_5 |
| --- | --- | --- | --- | --- | --- |
| b8_asymmetric_breadth_gate | calm_trend | 0.0795 | 1.0350 | -0.0893 | -0.0251 |
| b8_asymmetric_breadth_gate | neutral_mixed | 0.0486 | 0.6199 | -0.1136 | -0.0271 |
| b8_asymmetric_breadth_gate | recovery_confirmed | 0.1901 | 3.8873 | -0.0256 | -0.0098 |
| b8_asymmetric_breadth_gate | recovery_fragile | 0.1616 | 3.0915 | -0.0139 | -0.0109 |
| b8_asymmetric_breadth_gate | stressed_panic | 0.0090 | 0.1136 | -0.1231 | -0.0273 |
| b8_calm_neutral_confirmation | calm_trend | 0.0789 | 1.0288 | -0.0893 | -0.0251 |
| b8_calm_neutral_confirmation | neutral_mixed | 0.0488 | 0.6255 | -0.1121 | -0.0270 |
| b8_calm_neutral_confirmation | recovery_confirmed | 0.1901 | 3.8873 | -0.0256 | -0.0098 |
| b8_calm_neutral_confirmation | recovery_fragile | 0.1616 | 3.0915 | -0.0139 | -0.0109 |
| b8_calm_neutral_confirmation | stressed_panic | 0.0088 | 0.1114 | -0.1231 | -0.0273 |
| b8_market_quality_composite_medium | calm_trend | 0.0764 | 1.0212 | -0.0887 | -0.0244 |
| b8_market_quality_composite_medium | neutral_mixed | 0.0486 | 0.6368 | -0.1113 | -0.0263 |
| b8_market_quality_composite_medium | recovery_confirmed | 0.1878 | 3.8362 | -0.0259 | -0.0100 |
| b8_market_quality_composite_medium | recovery_fragile | 0.1593 | 3.0919 | -0.0139 | -0.0105 |
| b8_market_quality_composite_medium | stressed_panic | 0.0088 | 0.1117 | -0.1231 | -0.0271 |
| b8_market_quality_composite_mild | calm_trend | 0.0771 | 1.0243 | -0.0888 | -0.0245 |
| b8_market_quality_composite_mild | neutral_mixed | 0.0488 | 0.6356 | -0.1118 | -0.0264 |
| b8_market_quality_composite_mild | recovery_confirmed | 0.1882 | 3.8444 | -0.0259 | -0.0100 |
| b8_market_quality_composite_mild | recovery_fragile | 0.1597 | 3.0912 | -0.0139 | -0.0106 |
| b8_market_quality_composite_mild | stressed_panic | 0.0088 | 0.1127 | -0.1231 | -0.0272 |
| b8_recovery_safe_sector_gate | calm_trend | 0.0792 | 1.0316 | -0.0893 | -0.0251 |
| b8_recovery_safe_sector_gate | neutral_mixed | 0.0491 | 0.6267 | -0.1126 | -0.0271 |
| b8_recovery_safe_sector_gate | recovery_confirmed | 0.1911 | 3.8905 | -0.0256 | -0.0099 |
| b8_recovery_safe_sector_gate | recovery_fragile | 0.1616 | 3.0847 | -0.0139 | -0.0109 |
| b8_recovery_safe_sector_gate | stressed_panic | 0.0091 | 0.1156 | -0.1231 | -0.0273 |
| b8_sector_soft_90_105 | calm_trend | 0.0800 | 1.0311 | -0.0891 | -0.0253 |
| b8_sector_soft_90_105 | neutral_mixed | 0.0493 | 0.6202 | -0.1136 | -0.0274 |
| b8_sector_soft_90_105 | recovery_confirmed | 0.1925 | 3.9075 | -0.0256 | -0.0099 |
| b8_sector_soft_90_105 | recovery_fragile | 0.1618 | 3.0808 | -0.0139 | -0.0111 |
| b8_sector_soft_90_105 | stressed_panic | 0.0090 | 0.1135 | -0.1231 | -0.0275 |
| b8_sector_soft_95_103 | calm_trend | 0.0799 | 1.0335 | -0.0893 | -0.0252 |
| b8_sector_soft_95_103 | neutral_mixed | 0.0493 | 0.6225 | -0.1138 | -0.0273 |
| b8_sector_soft_95_103 | recovery_confirmed | 0.1916 | 3.9016 | -0.0256 | -0.0098 |
| b8_sector_soft_95_103 | recovery_fragile | 0.1617 | 3.0862 | -0.0139 | -0.0110 |
| b8_sector_soft_95_103 | stressed_panic | 0.0091 | 0.1144 | -0.1231 | -0.0275 |
| b8_soft_etf_breadth_90_105 | calm_trend | 0.0798 | 1.0301 | -0.0891 | -0.0253 |
| b8_soft_etf_breadth_90_105 | neutral_mixed | 0.0491 | 0.6202 | -0.1139 | -0.0273 |
| b8_soft_etf_breadth_90_105 | recovery_confirmed | 0.1927 | 3.8906 | -0.0261 | -0.0101 |
| b8_soft_etf_breadth_90_105 | recovery_fragile | 0.1634 | 3.1025 | -0.0139 | -0.0110 |
| b8_soft_etf_breadth_90_105 | stressed_panic | 0.0088 | 0.1118 | -0.1231 | -0.0274 |

## Warnings

- None.
