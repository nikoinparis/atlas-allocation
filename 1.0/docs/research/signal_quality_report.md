# Signal Quality Report

Research-only B3 build of signal environment and trend-quality features. Feature CSVs are lagged by one week before validation.

- Combined feature CSV: `data/02_layer1_signals/signal_quality_features.csv`
- Validation CSV: `data/02_layer1_signals/signal_quality_feature_validation.csv`
- Features built: 6

## Feature Validation

| signal_name | category | verdict | avg_full_mean_ic | avg_holdout_mean_ic | calm_trend_mean_ic | stressed_panic_mean_ic | max_redundancy_vs_strong | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm_quality_signal_agreement | signal quality | promising-if-gated | 0.0590 | 0.0456 | 0.0737 | -0.0187 | 0.8855 | very high redundancy with existing strong signals |
| bm_quality_signal_dispersion | signal quality | candidate-pass | 0.0180 | 0.0271 | 0.0190 | -0.0053 | 0.0146 | Positive full/holdout IC and no large stressed_panic damage. |
| bm_quality_trend_efficiency | trend quality | research-only | 0.0118 | -0.0023 | 0.0405 | -0.0496 | 0.6277 | holdout IC not positive; stressed_panic damage |
| bm_quality_breadth_confirmation | signal environment | candidate-pass | 0.1213 | 0.1258 | 0.1236 | 0.0833 | 0.2542 | Positive full/holdout IC and no large stressed_panic damage. |
| bm_quality_risk_on_confirmation | signal environment | promising-if-gated | 0.0081 | 0.0254 | 0.0506 | -0.0407 | 0.1852 | stressed_panic damage |
| bm_quality_deterioration_warning | signal environment | reject | -0.1181 | -0.1258 | -0.1236 | -0.0833 | 0.1936 | full IC not positive; holdout IC not positive; stressed_panic damage |

## Best Calm Trend Features

| signal_name | calm_trend_mean_ic | avg_holdout_mean_ic | verdict |
| --- | --- | --- | --- |
| bm_quality_breadth_confirmation | 0.1236 | 0.1258 | candidate-pass |
| bm_quality_signal_agreement | 0.0737 | 0.0456 | promising-if-gated |
| bm_quality_risk_on_confirmation | 0.0506 | 0.0254 | promising-if-gated |
| bm_quality_trend_efficiency | 0.0405 | -0.0023 | research-only |
| bm_quality_signal_dispersion | 0.0190 | 0.0271 | candidate-pass |
| bm_quality_deterioration_warning | -0.1236 | -0.1258 | reject |

## Deterioration And Disagreement Notes

- `bm_quality_deterioration_warning` is signed so lower/negative readings represent weakening participation, credit pressure, equity weakness, or correlation stress.
- `bm_quality_signal_dispersion` is signed so higher values indicate lower disagreement among strong signals.
- These are features for future gating/ranking research, not portfolio rules.

## Warnings

- None.
