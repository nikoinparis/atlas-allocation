# Breadth + Macro Priority Rankings

Research-only B5 ranking of tested breadth, state-gated macro, signal-quality, and dollar-strength features. Recommendations are not production promotions.

- Priority table: `data/02_layer1_signals/breadth_macro_priority_table.csv`
- Rows ranked: 74

## Top 10 Immediate Next-Test Candidates

| signal_name | source_phase | recommendation | full_ic | holdout_ic | calm_trend_usefulness | stressed_panic_danger | priority_score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bm_etf_above_50d_ma | breadth | candidate-pass | 0.1182 | 0.1258 | 0.1236 | -0.0833 | 4.8454 |
| bm_quality_breadth_confirmation | signal_quality | candidate-pass | 0.1213 | 0.1258 | 0.1236 | -0.0833 | 4.8340 |
| bm_etf_positive_13w_mom | breadth | candidate-pass | 0.1213 | 0.1258 | 0.1236 | -0.0833 | 4.8340 |
| bm_etf_above_200d_ma | breadth | candidate-pass | 0.1208 | 0.1258 | 0.1236 | -0.0833 | 4.8040 |
| bm_etf_positive_26w_mom | breadth | candidate-pass | 0.1198 | 0.1258 | 0.1236 | -0.0833 | 4.7884 |
| bm_risk_on_participation | breadth | candidate-pass | 0.1209 | 0.1201 | 0.1263 | -0.0436 | 4.7447 |
| bm_sector_above_50d_ma | breadth | candidate-pass | 0.1150 | 0.1187 | 0.1223 | -0.0647 | 4.6921 |
| bm_sector_positive_26w_mom | breadth | candidate-pass | 0.1202 | 0.1200 | 0.1236 | -0.0796 | 4.6813 |
| bm_sector_above_200d_ma | breadth | candidate-pass | 0.1206 | 0.1188 | 0.1236 | -0.0741 | 4.6694 |
| bm_sector_positive_13w_mom | breadth | candidate-pass | 0.1169 | 0.1113 | 0.1236 | -0.0521 | 4.5547 |

## Top 10 Promising Conditional Signals

| signal_name | source_phase | recommendation | full_ic | holdout_ic | calm_trend_usefulness | stressed_panic_danger | priority_score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r2_commodity_regime__recovery_only | state_gated_macro | promising-if-gated | 0.0937 | 0.0993 | 0.2611 | -0.0301 | 5.4562 |
| r2_financial_conditions__recovery_only | state_gated_macro | promising-if-gated | 0.0750 | 0.1973 | 0.0873 | -0.0417 | 5.3681 |
| r2_credit_spread__vix_below_past_median | state_gated_macro | promising-if-gated | 0.0773 | 0.0662 | 0.0642 | -0.0252 | 3.0570 |
| r2_financial_conditions__calm_or_breadth_no_stress | state_gated_macro | promising-if-gated | 0.0791 | 0.0527 | 0.0703 | -0.0254 | 2.9368 |
| r2_financial_conditions__no_stressed_panic | state_gated_macro | promising-if-gated | 0.0791 | 0.0527 | 0.0703 | -0.0254 | 2.9368 |
| r2_vix_term_structure__calm_or_breadth_no_stress | state_gated_macro | promising-if-gated | 0.0536 | 0.0546 | 0.0857 | -0.0880 | 2.9107 |
| r2_vix_term_structure__no_stressed_panic | state_gated_macro | promising-if-gated | 0.0536 | 0.0546 | 0.0857 | -0.0880 | 2.9107 |
| r2_vix_term_structure__vix_below_past_median | state_gated_macro | promising-if-gated | 0.0635 | 0.0492 | 0.0819 | 0.0240 | 2.6043 |
| r2_financial_conditions__breadth_confirms | state_gated_macro | promising-if-gated | 0.0602 | 0.0428 | 0.0703 | 0.0286 | 2.3030 |
| r2_credit_spread__no_stressed_panic | state_gated_macro | promising-if-gated | 0.0449 | 0.0371 | 0.0619 | -0.0200 | 2.2619 |

## Top Breadth Ideas

| signal_name | recommendation | full_ic | holdout_ic | calm_trend_usefulness | stressed_panic_danger | priority_score |
| --- | --- | --- | --- | --- | --- | --- |
| bm_etf_above_50d_ma | candidate-pass | 0.1182 | 0.1258 | 0.1236 | -0.0833 | 4.8454 |
| bm_etf_positive_13w_mom | candidate-pass | 0.1213 | 0.1258 | 0.1236 | -0.0833 | 4.8340 |
| bm_etf_above_200d_ma | candidate-pass | 0.1208 | 0.1258 | 0.1236 | -0.0833 | 4.8040 |
| bm_etf_positive_26w_mom | candidate-pass | 0.1198 | 0.1258 | 0.1236 | -0.0833 | 4.7884 |
| bm_risk_on_participation | candidate-pass | 0.1209 | 0.1201 | 0.1263 | -0.0436 | 4.7447 |
| bm_sector_above_50d_ma | candidate-pass | 0.1150 | 0.1187 | 0.1223 | -0.0647 | 4.6921 |
| bm_sector_positive_26w_mom | candidate-pass | 0.1202 | 0.1200 | 0.1236 | -0.0796 | 4.6813 |
| bm_sector_above_200d_ma | candidate-pass | 0.1206 | 0.1188 | 0.1236 | -0.0741 | 4.6694 |
| bm_sector_positive_13w_mom | candidate-pass | 0.1169 | 0.1113 | 0.1236 | -0.0521 | 4.5547 |
| bm_risk_on_minus_defensive_participation | reject | 0.0081 | 0.0254 | 0.0506 | 0.0407 | 1.2750 |

## PIT-Data Future Ideas

- No PIT-dependent signal was implemented in this sprint. True constituent breadth, new-high/new-low breadth, advance/decline lines, and sector valuation breadth remain future paid/PIT candidates from the prior discovery backlog.

## Reject / Avoid

| signal_name | source_phase | recommendation | full_ic | holdout_ic | stressed_panic_danger | priority_score | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bm_quality_deterioration_warning | signal_quality | reject | -0.1181 | -0.1258 | 0.0833 | -4.0827 | full IC not positive; holdout IC not positive; stressed_panic damage |
| r2_cross_asset_divergence__vix_below_past_median | state_gated_macro | reject | 0.0056 | -0.0888 | 0.1893 | -2.0739 | holdout IC not positive; stressed_panic damage remains |
| r2_credit_spread__recovery_only | state_gated_macro | reject | -0.0179 | -0.0202 | 0.2261 | -1.6484 | insufficient observations; full IC not positive; holdout IC not positive; stressed_panic damage remains |
| r2_yield_curve__vix_below_past_median | state_gated_macro | reject | -0.0518 | -0.0288 | -0.0135 | -1.0286 | full IC not positive; holdout IC not positive |
| r2_vix_term_structure__recovery_only | state_gated_macro | reject | 0.0411 | 0.0807 | 0.3744 | -1.0266 | insufficient observations; stressed_panic damage remains |
| r2_yield_curve__calm_or_breadth_no_stress | state_gated_macro | reject | -0.0347 | 0.0522 | 0.1545 | -0.9382 | full IC not positive; stressed_panic damage remains |
| r2_yield_curve__no_stressed_panic | state_gated_macro | reject | -0.0347 | 0.0522 | 0.1545 | -0.9382 | full IC not positive; stressed_panic damage remains |
| r2_commodity_regime__vix_below_past_median | state_gated_macro | reject | 0.0057 | -0.0365 | 0.0886 | -0.7234 | holdout IC not positive; stressed_panic damage remains |
| r2_yield_curve__calm_trend_only | state_gated_macro | reject | -0.0885 | -0.0057 |  | -0.6295 | full IC not positive; holdout IC not positive |
| r2_cross_asset_divergence__unconditional | state_gated_macro | reject | -0.0077 | -0.0382 | 0.1038 | -0.6278 | full IC not positive; holdout IC not positive; stressed_panic damage remains |
