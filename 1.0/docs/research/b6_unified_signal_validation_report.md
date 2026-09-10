# B6 Unified Signal Validation Report

Research-only unified validation of selected breadth, gated macro, dollar-strength, and signal-quality candidates. All panels use one-week-lagged tradable signals; gated signals use one-week-lagged gates.

- Validation CSV: `data/02_layer1_signals/b6_unified_signal_validation.csv`
- State detail CSV: `data/02_layer1_signals/b6_state_validation_detail.csv`
- Candidates validated: 22

## Verdict Summary

| verdict | count |
| --- | --- |
| promising-if-gated | 19 |
| research-only | 2 |
| candidate-pass-but-redundant | 1 |

## Top Candidates By 2020+ Holdout IC

| signal_name | category | verdict | avg_full_ic | 2016_plus_avg_ic | 2020_plus_avg_ic | 2022_bear_rate_shock_avg_ic | calm_trend_avg_ic | stressed_panic_avg_ic | max_abs_redundancy_existing | stress_safety_flags |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r2_financial_conditions__recovery_only | gated_macro | research-only | 0.0750 | 0.0642 | 0.1973 |  | 0.0873 | 0.0417 | 0.0401 | sample_size_too_small |
| bm_etf_above_50d_ma | breadth | promising-if-gated | 0.1182 | 0.1440 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2121 | 2022_ic_negative |
| bm_etf_positive_13w_mom | breadth | promising-if-gated | 0.1213 | 0.1440 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2542 | 2022_ic_negative |
| bm_etf_positive_26w_mom | breadth | promising-if-gated | 0.1196 | 0.1440 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2851 | 2022_ic_negative |
| bm_etf_above_200d_ma | breadth | promising-if-gated | 0.1207 | 0.1440 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2794 | 2022_ic_negative |
| bm_quality_breadth_confirmation | signal_quality | promising-if-gated | 0.1213 | 0.1440 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2542 | 2022_ic_negative |
| bm_risk_on_participation | breadth | promising-if-gated | 0.1209 | 0.1400 | 0.1201 | -0.0979 | 0.1260 | 0.0438 | 0.2767 | 2022_ic_negative |
| bm_sector_positive_26w_mom | sector_breadth | promising-if-gated | 0.1201 | 0.1407 | 0.1200 | -0.0383 | 0.1233 | 0.0801 | 0.3102 | 2022_ic_negative |
| bm_sector_above_200d_ma | sector_breadth | promising-if-gated | 0.1205 | 0.1400 | 0.1188 | -0.0383 | 0.1233 | 0.0745 | 0.3073 | 2022_ic_negative |
| bm_sector_above_50d_ma | sector_breadth | promising-if-gated | 0.1150 | 0.1392 | 0.1187 | -0.0542 | 0.1220 | 0.0649 | 0.2172 | 2022_ic_negative |
| bm_sector_positive_13w_mom | sector_breadth | promising-if-gated | 0.1169 | 0.1348 | 0.1113 | -0.0586 | 0.1233 | 0.0523 | 0.2732 | 2022_ic_negative |
| r2_commodity_regime__recovery_only | gated_macro | research-only | 0.0937 | 0.0890 | 0.0993 |  | 0.2611 | 0.0301 | 0.0599 | sample_size_too_small |
| r2_credit_spread__calm_trend_only | gated_macro | promising-if-gated | 0.0769 | 0.1230 | 0.0916 |  | 0.0581 |  | 0.1615 |  |
| r2_vix_term_structure__calm_trend_only | gated_macro | promising-if-gated | 0.0721 | 0.1158 | 0.0705 |  | 0.0738 |  | 0.1729 |  |
| bm_quality_risk_on_confirmation__no_stressed_panic | signal_quality | promising-if-gated | 0.0251 | 0.0458 | 0.0678 | -0.1099 | 0.0506 | 0.0513 | 0.1671 | 2022_ic_negative |
| r2_credit_spread__vix_below_past_median | gated_macro | promising-if-gated | 0.0773 | 0.0904 | 0.0662 | -0.1382 | 0.0642 | 0.0252 | 0.2236 | 2022_ic_negative |
| r2_vix_term_structure__no_stressed_panic | gated_macro | promising-if-gated | 0.0536 | 0.0513 | 0.0546 | -0.0862 | 0.0857 | 0.0880 | 0.1308 | 2022_ic_negative |
| bm_quality_signal_agreement | signal_quality | candidate-pass-but-redundant | 0.0590 | 0.0419 | 0.0456 | 0.0356 | 0.0737 | -0.0190 | 0.8855 | redundancy_gt_0.60_existing |
| bm_quality_signal_dispersion | signal_quality | promising-if-gated | 0.0180 | 0.0331 | 0.0272 | 0.0351 | 0.0191 | -0.0052 | 0.0145 |  |
| bm_dollar_strength_4w | dollar_strength | promising-if-gated | 0.0143 | 0.0251 | 0.0221 | 0.0390 | 0.0147 | 0.0159 | 0.0165 |  |

## Redundancy Watch

| signal_name | verdict | max_abs_redundancy_existing | most_redundant_existing_signal | rolling_104w_redundancy_median | rolling_104w_redundancy_max | rolling_104w_redundancy_recent |
| --- | --- | --- | --- | --- | --- | --- |
| bm_quality_signal_agreement | candidate-pass-but-redundant | 0.8855 | moving_average_distance | 0.8902 | 0.9071 | 0.8959 |
| bm_sector_positive_26w_mom | promising-if-gated | 0.3102 | multi_mom_equal | 0.2687 | 0.6393 | 0.3747 |
| bm_sector_above_200d_ma | promising-if-gated | 0.3073 | multi_mom_equal | 0.2727 | 0.6393 | 0.3747 |
| bm_etf_positive_26w_mom | promising-if-gated | 0.2851 | multi_mom_equal | 0.2848 | 0.6393 | 0.3689 |
| bm_etf_above_200d_ma | promising-if-gated | 0.2794 | multi_mom_equal | 0.2848 | 0.6393 | 0.3689 |
| bm_risk_on_participation | promising-if-gated | 0.2767 | multi_mom_invvol | 0.3326 | 0.6371 | 0.3798 |
| bm_sector_positive_13w_mom | promising-if-gated | 0.2732 | multi_mom_invvol | 0.2716 | 0.6379 | 0.3534 |
| bm_quality_breadth_confirmation | promising-if-gated | 0.2542 | multi_mom_equal | 0.2848 | 0.6393 | 0.3689 |
| bm_etf_positive_13w_mom | promising-if-gated | 0.2542 | multi_mom_equal | 0.2848 | 0.6393 | 0.3689 |
| r2_credit_spread__vix_below_past_median | promising-if-gated | 0.2236 | multi_mom_equal | 0.3652 | 0.5509 | 0.4337 |
| bm_sector_above_50d_ma | promising-if-gated | 0.2172 | multi_mom_equal | 0.2612 | 0.6320 | 0.3783 |
| bm_etf_above_50d_ma | promising-if-gated | 0.2121 | multi_mom_equal | 0.2848 | 0.6393 | 0.3689 |
| r2_vix_term_structure__calm_trend_only | promising-if-gated | 0.1729 | multi_mom_invvol | 0.3923 | 0.4861 | 0.3560 |
| bm_quality_risk_on_confirmation__no_stressed_panic | promising-if-gated | 0.1671 | multi_mom_invvol | 0.2290 | 0.4909 | 0.1683 |
| r2_credit_spread__calm_trend_only | promising-if-gated | 0.1615 | xsmom_global | 0.3691 | 0.4822 | 0.2391 |
| r2_vix_term_structure__no_stressed_panic | promising-if-gated | 0.1308 | multi_mom_equal | 0.1893 | 0.3987 | 0.0990 |
| bm_dollar_strength_blended | promising-if-gated | 0.0775 | breadth_confirmed_momentum | 0.1177 | 0.3210 | 0.0699 |
| bm_dollar_strength_13w | promising-if-gated | 0.0613 | breadth_confirmed_momentum | 0.1112 | 0.2735 | 0.0491 |
| r2_commodity_regime__recovery_only | research-only | 0.0599 | breadth_confirmed_momentum | 0.2241 | 0.2504 | 0.2019 |
| r2_financial_conditions__recovery_only | research-only | 0.0401 | breadth_confirmed_momentum | 0.1780 | 0.2421 | 0.1796 |

## State Detail Highlights

| signal_name | market_state | horizon_weeks | mean_ic | ic_tstat_nw | n_dates |
| --- | --- | --- | --- | --- | --- |
| r2_commodity_regime__recovery_only | calm_trend | 2 | 0.6662 |  | 1 |
| r2_commodity_regime__recovery_only | calm_trend | 4 | 0.5414 |  | 1 |
| r2_vix_term_structure__calm_trend_only | recovery_confirmed | 2 | 0.4729 |  | 1 |
| r2_credit_spread__calm_trend_only | recovery_confirmed | 2 | 0.4729 |  | 1 |
| r2_vix_term_structure__calm_trend_only | recovery_confirmed | 4 | 0.4191 |  | 1 |
| r2_credit_spread__calm_trend_only | recovery_confirmed | 4 | 0.4191 |  | 1 |
| r2_vix_term_structure__calm_trend_only | recovery_confirmed | 1 | 0.3996 |  | 1 |
| r2_credit_spread__calm_trend_only | recovery_confirmed | 1 | 0.3996 |  | 1 |
| r2_financial_conditions__recovery_only | calm_trend | 4 | 0.3756 | 27.3411 | 3 |
| r2_commodity_regime__recovery_only | calm_trend | 1 | 0.3592 |  | 1 |
| r2_credit_spread__calm_trend_only | recovery_confirmed | 13 | 0.3578 |  | 1 |
| r2_vix_term_structure__calm_trend_only | recovery_confirmed | 13 | 0.3578 |  | 1 |
| r2_credit_spread__calm_trend_only | recovery_confirmed | 8 | 0.3084 |  | 1 |
| r2_vix_term_structure__calm_trend_only | recovery_confirmed | 8 | 0.3084 |  | 1 |
| bm_dollar_strength_blended | recovery_confirmed | 13 | 0.3080 | 4.1276 | 40 |
| bm_quality_signal_agreement | recovery_confirmed | 8 | 0.2750 | 4.8858 | 43 |
| bm_quality_risk_on_confirmation__no_stressed_panic | recovery_confirmed | 8 | 0.2725 | 3.2217 | 34 |
| bm_dollar_strength_blended | recovery_confirmed | 8 | 0.2565 | 3.3432 | 40 |
| bm_risk_on_participation | recovery_fragile | 4 | 0.2563 | 4.0156 | 48 |
| bm_etf_positive_26w_mom | recovery_fragile | 4 | 0.2562 | 4.0979 | 49 |

## Warnings

- None.
