# Dollar Strength Deep Dive Report

Research-only B4 diagnostic of UUP momentum windows. This is an explanatory validation exercise, not a production deployment.

- Deep dive CSV: `data/02_layer1_signals/dollar_strength_deep_dive.csv`
- Variants tested: 5

## Variant Results

| signal_name | verdict | avg_full_mean_ic | avg_holdout_mean_ic | calm_trend_mean_ic | stressed_panic_mean_ic | max_redundancy_vs_strong | redundancy_drift | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm_dollar_strength_4w | candidate-pass | 0.0145 | 0.0221 | 0.0146 | 0.0161 | 0.0165 | 0.0068 | Positive full/holdout IC and no large stressed_panic damage. |
| bm_dollar_strength_8w | candidate-pass | 0.0241 | 0.0005 | 0.0150 | 0.0642 | 0.0203 | -0.0227 | Positive full/holdout IC and no large stressed_panic damage. |
| bm_dollar_strength_13w | candidate-pass | 0.0065 | 0.0081 | 0.0155 | 0.0214 | 0.0613 | -0.0916 | Positive full/holdout IC and no large stressed_panic damage. |
| bm_dollar_strength_26w | reject | 0.0090 | -0.0014 | 0.0096 | -0.0143 | 0.1195 | -0.1141 | holdout IC not positive |
| bm_dollar_strength_blended | candidate-pass | 0.0189 | 0.0197 | 0.0131 | 0.0273 | 0.0775 | -0.1091 | Positive full/holdout IC and no large stressed_panic damage. |

## Cross-Asset Relationship Diagnostics

| signal_name | corr_with_future_4w_commodities_return | corr_with_future_4w_em_return | corr_with_future_4w_bonds_return | corr_with_future_4w_spy_return | corr_with_future_4w_risk_on_return | corr_with_future_4w_breadth_change | corr_with_future_4w_drawdown_change |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bm_dollar_strength_4w | -0.0873 | -0.0808 | 0.0406 | -0.0384 | -0.0481 |  |  |
| bm_dollar_strength_8w | -0.0985 | -0.0703 | 0.0404 | -0.0239 | -0.0524 |  |  |
| bm_dollar_strength_13w | -0.1084 | -0.0671 | 0.0347 | -0.0691 | -0.0838 |  |  |
| bm_dollar_strength_26w | -0.1386 | -0.0725 | 0.0189 | -0.1142 | -0.1350 |  |  |
| bm_dollar_strength_blended | -0.1365 | -0.0919 | 0.0300 | -0.0889 | -0.1122 |  |  |

## Interpretation

- Dollar strength is treated as a cross-asset pressure signal: positive UUP momentum generally loads positively on UUP/cash-like exposure and negatively on EM, commodities, and risk assets.
- A robust dollar signal should not only pass average IC tests; it should also avoid becoming a hidden stressed_panic amplifier.
- Window comparisons are diagnostic only. No window is optimized or promoted here.

## Warnings

- None.
