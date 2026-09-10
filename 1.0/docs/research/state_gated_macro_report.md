# State-Gated Macro Report

Research-only B2 tests of simple one-week-lagged activation gates on existing R2 macro/VIX/credit signal panels.

- Results CSV: `data/02_layer1_signals/state_gated_macro_results.csv`
- State detail CSV: `data/02_layer1_signals/state_gated_macro_state_detail.csv`
- Rows tested: 49

## Best Gated Rows

| base_signal | gate_name | verdict | avg_full_mean_ic | avg_holdout_mean_ic | calm_trend_mean_ic | stressed_panic_mean_ic | stressed_panic_improvement | gate_active_share | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r2_credit_spread | calm_trend_only | candidate-pass | 0.0769 | 0.0916 | 0.0581 |  |  | 0.2658 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_vix_term_structure | calm_trend_only | candidate-pass | 0.0721 | 0.0705 | 0.0738 |  |  | 0.2658 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_dollar_strength | breadth_confirms | candidate-pass | 0.0334 | 0.0447 | 0.0293 | 0.0257 | 0.0097 | 0.9811 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_dollar_strength | unconditional | candidate-pass | 0.0314 | 0.0388 | 0.0293 | 0.0161 | 0.0000 | 0.9991 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_dollar_strength | calm_trend_only | candidate-pass | 0.0324 | 0.0388 | 0.0246 |  |  | 0.2658 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_commodity_regime | no_stressed_panic | candidate-pass | 0.0133 | 0.0101 | -0.0241 | 0.0574 | 0.0968 | 0.7928 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_commodity_regime | calm_or_breadth_no_stress | candidate-pass | 0.0133 | 0.0101 | -0.0241 | 0.0574 | 0.0968 | 0.7811 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_financial_conditions | calm_trend_only | candidate-pass | 0.0766 | 0.0080 | 0.0656 |  |  | 0.2658 | Positive full/holdout IC and no large stressed_panic damage under this gate. |
| r2_financial_conditions | recovery_only | promising-if-gated | 0.0750 | 0.1973 | 0.0873 | 0.0417 | 0.0777 | 0.0829 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_dollar_strength | recovery_only | promising-if-gated | 0.1369 | 0.1347 | 0.2407 | -0.1397 | -0.1558 | 0.0829 | insufficient observations; stressed_panic damage remains |
| r2_commodity_regime | recovery_only | promising-if-gated | 0.0937 | 0.0993 | 0.2611 | 0.0301 | 0.0694 | 0.0829 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_credit_spread | vix_below_past_median | promising-if-gated | 0.0773 | 0.0662 | 0.0642 | 0.0252 | 0.1033 | 0.4865 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_vix_term_structure | no_stressed_panic | promising-if-gated | 0.0536 | 0.0546 | 0.0857 | 0.0880 | 0.2275 | 0.7928 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_vix_term_structure | calm_or_breadth_no_stress | promising-if-gated | 0.0536 | 0.0546 | 0.0857 | 0.0880 | 0.2275 | 0.7811 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_financial_conditions | no_stressed_panic | promising-if-gated | 0.0791 | 0.0527 | 0.0703 | 0.0254 | 0.0614 | 0.7928 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_financial_conditions | calm_or_breadth_no_stress | promising-if-gated | 0.0791 | 0.0527 | 0.0703 | 0.0254 | 0.0614 | 0.7811 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_vix_term_structure | vix_below_past_median | promising-if-gated | 0.0635 | 0.0492 | 0.0819 | -0.0240 | 0.1155 | 0.4865 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_financial_conditions | breadth_confirms | promising-if-gated | 0.0602 | 0.0428 | 0.0703 | -0.0286 | 0.0074 | 0.9811 | stressed_panic damage remains |
| r2_credit_spread | no_stressed_panic | promising-if-gated | 0.0449 | 0.0371 | 0.0619 | 0.0200 | 0.0981 | 0.7928 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |
| r2_credit_spread | calm_or_breadth_no_stress | promising-if-gated | 0.0449 | 0.0371 | 0.0619 | 0.0200 | 0.0981 | 0.7811 | Gate improved stressed_panic behavior while retaining positive holdout/calm evidence. |

## Gates That Improved Stressed Panic Behavior

| base_signal | gate_name | avg_holdout_mean_ic | calm_trend_mean_ic | stressed_panic_mean_ic | base_unconditional_stressed_panic_mean_ic | stressed_panic_improvement | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r2_vix_term_structure | calm_or_breadth_no_stress | 0.0546 | 0.0857 | 0.0880 | -0.1395 | 0.2275 | promising-if-gated |
| r2_vix_term_structure | no_stressed_panic | 0.0546 | 0.0857 | 0.0880 | -0.1395 | 0.2275 | promising-if-gated |
| r2_dollar_strength | vix_below_past_median | 0.0151 | 0.0274 | 0.1644 | 0.0161 | 0.1483 | promising-if-gated |
| r2_financial_conditions | vix_below_past_median | 0.0052 | 0.0686 | 0.0964 | -0.0360 | 0.1324 | promising-if-gated |
| r2_vix_term_structure | vix_below_past_median | 0.0492 | 0.0819 | -0.0240 | -0.1395 | 0.1155 | promising-if-gated |
| r2_credit_spread | vix_below_past_median | 0.0662 | 0.0642 | 0.0252 | -0.0781 | 0.1033 | promising-if-gated |
| r2_credit_spread | no_stressed_panic | 0.0371 | 0.0619 | 0.0200 | -0.0781 | 0.0981 | promising-if-gated |
| r2_credit_spread | calm_or_breadth_no_stress | 0.0371 | 0.0619 | 0.0200 | -0.0781 | 0.0981 | promising-if-gated |
| r2_commodity_regime | calm_or_breadth_no_stress | 0.0101 | -0.0241 | 0.0574 | -0.0394 | 0.0968 | candidate-pass |
| r2_commodity_regime | no_stressed_panic | 0.0101 | -0.0241 | 0.0574 | -0.0394 | 0.0968 | candidate-pass |
| r2_financial_conditions | recovery_only | 0.1973 | 0.0873 | 0.0417 | -0.0360 | 0.0777 | promising-if-gated |
| r2_commodity_regime | recovery_only | 0.0993 | 0.2611 | 0.0301 | -0.0394 | 0.0694 | promising-if-gated |
| r2_financial_conditions | calm_or_breadth_no_stress | 0.0527 | 0.0703 | 0.0254 | -0.0360 | 0.0614 | promising-if-gated |
| r2_financial_conditions | no_stressed_panic | 0.0527 | 0.0703 | 0.0254 | -0.0360 | 0.0614 | promising-if-gated |
| r2_yield_curve | vix_below_past_median | -0.0288 | -0.1280 | 0.0135 | -0.0231 | 0.0366 | reject |

## Remaining Dangerous Rows

| base_signal | gate_name | stressed_panic_mean_ic | avg_holdout_mean_ic | calm_trend_mean_ic | verdict | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- |
| r2_vix_term_structure | recovery_only | -0.3744 | 0.0807 | 0.0162 | research-only | insufficient observations; stressed_panic damage remains |
| r2_cross_asset_divergence | recovery_only | -0.3744 | 0.1361 | -0.0162 | research-only | insufficient observations; stressed_panic damage remains |
| r2_yield_curve | recovery_only | -0.3431 | 0.1912 | -0.0765 | research-only | insufficient observations; stressed_panic damage remains |
| r2_credit_spread | recovery_only | -0.2261 | -0.0202 | 0.0162 | reject | insufficient observations; full IC not positive; holdout IC not positive; stressed_panic damage remains |
| r2_cross_asset_divergence | vix_below_past_median | -0.1893 | -0.0888 | 0.0152 | research-only | holdout IC not positive; stressed_panic damage remains |
| r2_yield_curve | no_stressed_panic | -0.1545 | 0.0522 | -0.0940 | research-only | full IC not positive; stressed_panic damage remains |
| r2_yield_curve | calm_or_breadth_no_stress | -0.1545 | 0.0522 | -0.0940 | research-only | full IC not positive; stressed_panic damage remains |
| r2_vix_term_structure | breadth_confirms | -0.1452 | 0.0055 | 0.0857 | promising-if-gated | stressed_panic damage remains |
| r2_dollar_strength | recovery_only | -0.1397 | 0.1347 | 0.2407 | promising-if-gated | insufficient observations; stressed_panic damage remains |
| r2_vix_term_structure | unconditional | -0.1395 | 0.0051 | 0.0857 | promising-if-gated | stressed_panic damage remains |
| r2_cross_asset_divergence | calm_or_breadth_no_stress | -0.1161 | -0.0044 | 0.0185 | research-only | holdout IC not positive; stressed_panic damage remains |
| r2_cross_asset_divergence | no_stressed_panic | -0.1161 | -0.0044 | 0.0185 | research-only | holdout IC not positive; stressed_panic damage remains |
| r2_cross_asset_divergence | unconditional | -0.1038 | -0.0382 | 0.0185 | reject | full IC not positive; holdout IC not positive; stressed_panic damage remains |
| r2_cross_asset_divergence | breadth_confirms | -0.1016 | -0.0355 | 0.0185 | reject | full IC not positive; holdout IC not positive; stressed_panic damage remains |
| r2_credit_spread | breadth_confirms | -0.0915 | 0.0110 | 0.0619 | promising-if-gated | stressed_panic damage remains |

## Warnings

- macro_weekly.csv contains only Date; no raw macro series were available to rebuild macro signals. B2 used existing R2 macro/VIX/credit signal panels only.
