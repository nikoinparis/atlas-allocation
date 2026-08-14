# R3 State-Conditional Signal Report

Research-only signal IC by market state. Signals are validated using existing tradable columns or one-period-lagged R2 tradable values, then compared with forward ETF returns by horizon.

- Output CSV: `data/02_layer1_signals/signal_state_conditional_ic.csv`
- State/horizon rows: 825
- Skipped/partial signal loads: 0

## Which signals help calm_trend?

| signal_name | signal_source | horizon_weeks | mean_ic | ic_tstat_nw | hit_rate | n_dates |
| --- | --- | --- | --- | --- | --- | --- |
| moving_average_distance | existing | 13 | 0.1473 | 3.6812 | 0.6508 | 295 |
| multi_mom_equal | existing | 13 | 0.1425 | 3.5004 | 0.6159 | 289 |
| trend_clarity_momentum | existing | 13 | 0.1375 | 3.2434 | 0.6436 | 289 |
| multi_mom_invvol | existing | 13 | 0.1361 | 3.3838 | 0.6167 | 287 |
| xsmom_global | existing | 13 | 0.1358 | 3.1284 | 0.6090 | 289 |
| r2_vix_term_structure | R2 | 13 | 0.1308 | 2.6976 | 0.6777 | 273 |
| breadth_confirmed_momentum | existing | 13 | 0.1267 | 3.6535 | 0.6576 | 295 |
| r2_credit_spread | R2 | 13 | 0.1175 | 2.1299 | 0.6447 | 273 |
| r2_financial_conditions | R2 | 13 | 0.1129 | 2.0815 | 0.6585 | 287 |
| r2_vix_term_structure | R2 | 8 | 0.1094 | 2.5333 | 0.6557 | 273 |
| tsmom_vol_scaled | existing | 13 | 0.1004 | 2.9981 | 0.6540 | 289 |
| r2_vix_term_structure | R2 | 4 | 0.0865 | 2.3484 | 0.5824 | 273 |
| xsmom_global | existing | 8 | 0.0855 | 2.0324 | 0.5779 | 289 |
| contained_recovery_quality | existing | 13 | 0.0852 | 2.4155 | 0.5831 | 295 |
| trend_clarity_momentum | existing | 8 | 0.0837 | 2.0306 | 0.5952 | 289 |

## Which signals help neutral_mixed?

| signal_name | signal_source | horizon_weeks | mean_ic | ic_tstat_nw | hit_rate | n_dates |
| --- | --- | --- | --- | --- | --- | --- |
| r2_financial_conditions | R2 | 8 | 0.1304 | 3.0756 | 0.6265 | 431 |
| r2_financial_conditions | R2 | 13 | 0.1237 | 2.6440 | 0.6197 | 426 |
| multi_mom_equal | existing | 2 | 0.0928 | 3.9866 | 0.6054 | 446 |
| xsmom_global | existing | 2 | 0.0880 | 3.5443 | 0.5987 | 446 |
| r2_financial_conditions | R2 | 4 | 0.0867 | 2.4922 | 0.5829 | 434 |
| multi_mom_invvol | existing | 2 | 0.0862 | 3.7219 | 0.6024 | 425 |
| moving_average_distance | existing | 2 | 0.0789 | 3.3210 | 0.5910 | 467 |
| moving_average_distance | existing | 8 | 0.0786 | 2.1775 | 0.5909 | 462 |
| moving_average_distance | existing | 13 | 0.0757 | 2.0880 | 0.5624 | 457 |
| multi_mom_equal | existing | 1 | 0.0748 | 4.0793 | 0.5538 | 446 |

## Which signals help recovery_fragile?

| signal_name | signal_source | horizon_weeks | mean_ic | ic_tstat_nw | hit_rate | n_dates |
| --- | --- | --- | --- | --- | --- | --- |
| r2_dollar_strength | R2 | 13 | 0.2183 | 3.3331 | 0.8605 | 43 |
| residual_momentum | existing | 8 | 0.1651 | 3.4450 | 0.6939 | 49 |
| r2_financial_conditions | R2 | 8 | 0.1636 | 1.7469 | 0.6327 | 49 |
| contained_recovery_quality | existing | 13 | 0.1613 | 3.0462 | 0.6939 | 49 |
| r2_dollar_strength | R2 | 8 | 0.1413 | 2.2800 | 0.6512 | 43 |
| residual_momentum | existing | 13 | 0.1401 | 2.1150 | 0.6327 | 49 |
| r2_commodity_regime | R2 | 13 | 0.1346 | 2.4090 | 0.6818 | 44 |
| r2_vix_term_structure | R2 | 4 | 0.1271 | 1.6189 | 0.5581 | 43 |
| contained_recovery_quality | existing | 8 | 0.1244 | 1.8916 | 0.5714 | 49 |
| r2_vix_term_structure | R2 | 13 | 0.1197 | 1.6003 | 0.6279 | 43 |

## Which signals help recovery_confirmed?

| signal_name | signal_source | horizon_weeks | mean_ic | ic_tstat_nw | hit_rate | n_dates |
| --- | --- | --- | --- | --- | --- | --- |
| moving_average_distance | existing | 8 | 0.3166 | 4.6637 | 0.7442 | 43 |
| multi_mom_equal | existing | 8 | 0.3123 | 5.6038 | 0.7674 | 43 |
| r2_dollar_strength | R2 | 13 | 0.3077 | 4.1313 | 0.8500 | 40 |
| multi_mom_invvol | existing | 8 | 0.2936 | 4.8856 | 0.7209 | 43 |
| multi_mom_equal | existing | 13 | 0.2806 | 3.7658 | 0.7674 | 43 |
| moving_average_distance | existing | 13 | 0.2741 | 3.2077 | 0.7209 | 43 |
| breadth_confirmed_momentum | existing | 8 | 0.2634 | 4.8884 | 0.7442 | 43 |
| moving_average_distance | existing | 4 | 0.2631 | 6.0758 | 0.7674 | 43 |
| residual_momentum | existing | 8 | 0.2610 | 4.1001 | 0.7907 | 43 |
| multi_mom_equal | existing | 4 | 0.2596 | 5.9230 | 0.7442 | 43 |

## Best stressed_panic defensive signals

| signal_name | signal_source | horizon_weeks | mean_ic | ic_tstat_nw | hit_rate | n_dates |
| --- | --- | --- | --- | --- | --- | --- |
| macro_risk_score | existing | 13 | 0.1246 | 2.0524 | 0.6211 | 227 |
| google_fear_regime | existing | 13 | 0.1112 | 1.7614 | 0.6106 | 226 |
| vix_term_structure_regime | existing | 8 | 0.0904 | 1.8676 | 0.5670 | 224 |
| macro_risk_score | existing | 8 | 0.0852 | 1.4418 | 0.5639 | 227 |
| macro_risk_score | existing | 4 | 0.0780 | 1.5684 | 0.5658 | 228 |
| vix_term_structure_regime | existing | 2 | 0.0761 | 2.2237 | 0.5689 | 225 |
| vix_term_structure_regime | existing | 13 | 0.0756 | 1.4013 | 0.5714 | 224 |
| vix_term_structure_regime | existing | 4 | 0.0742 | 1.7056 | 0.5733 | 225 |
| macro_risk_score | existing | 2 | 0.0715 | 1.9477 | 0.5789 | 228 |
| google_fear_regime | existing | 8 | 0.0541 | 0.8705 | 0.5265 | 226 |

## Which signals hurt stressed_panic?

| signal_name | signal_source | horizon_weeks | mean_ic | ic_tstat_nw | hit_rate | n_dates |
| --- | --- | --- | --- | --- | --- | --- |
| r2_vix_term_structure | R2 | 13 | -0.2333 | -5.1310 | 0.2651 | 166 |
| r2_vix_term_structure | R2 | 8 | -0.1916 | -3.6861 | 0.3193 | 166 |
| bab_proxy | existing | 13 | -0.1633 | -2.2905 | 0.3568 | 227 |
| r2_cross_asset_divergence | R2 | 13 | -0.1464 | -2.1770 | 0.3690 | 187 |
| r2_cross_asset_divergence | R2 | 8 | -0.1320 | -2.1505 | 0.4011 | 187 |
| r2_vix_term_structure | R2 | 4 | -0.1316 | -2.4857 | 0.3952 | 167 |
| quality_proxy | existing | 13 | -0.1243 | -2.1286 | 0.4009 | 227 |
| bab_proxy | existing | 8 | -0.1140 | -1.6279 | 0.4141 | 227 |
| r2_credit_spread | R2 | 8 | -0.1106 | -1.7905 | 0.4118 | 187 |
| contained_recovery_quality | existing | 13 | -0.1060 | -2.1287 | 0.3612 | 227 |
| r2_volume_divergence | R2 | 13 | -0.0981 | -2.0084 | 0.3833 | 227 |
| quality_proxy | existing | 8 | -0.0968 | -1.8007 | 0.4537 | 227 |
| breadth_confirmed_momentum | existing | 13 | -0.0935 | -1.7319 | 0.4097 | 227 |
| r2_vix_term_structure | R2 | 2 | -0.0928 | -2.1179 | 0.3952 | 167 |
| r2_commodity_regime | R2 | 13 | -0.0890 | -2.3200 | 0.3935 | 216 |

## Which signals appear regime-specific?

| signal_name | horizon_weeks | calm_trend | neutral_mixed | recovery_confirmed | recovery_fragile | stressed_panic | state_ic_range | positive_state_count |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r2_vix_term_structure | 13 | 0.1308 | 0.0312 | 0.2270 | 0.1197 | -0.2333 | 0.4604 | 4 |
| vix_term_structure_regime | 8 | -0.0536 | 0.0122 | -0.3125 | -0.0643 | 0.0904 | 0.4029 | 2 |
| r2_yield_curve | 13 | -0.1676 | 0.0023 | 0.2203 | -0.0246 | -0.0652 | 0.3880 | 2 |
| r2_vix_term_structure | 8 | 0.1094 | 0.0294 | 0.1940 | 0.0144 | -0.1916 | 0.3857 | 4 |
| vix_term_structure_regime | 13 | -0.0742 | 0.0129 | -0.2909 | -0.0365 | 0.0756 | 0.3665 | 2 |
| multi_mom_equal | 8 | 0.0723 | 0.0647 | 0.3123 | 0.1040 | -0.0498 | 0.3621 | 4 |
| moving_average_distance | 8 | 0.0702 | 0.0786 | 0.3166 | 0.0366 | -0.0435 | 0.3601 | 4 |
| multi_mom_equal | 13 | 0.1425 | 0.0568 | 0.2806 | 0.1056 | -0.0768 | 0.3574 | 4 |
| macro_risk_score | 13 | -0.1441 | -0.0443 | -0.2157 | -0.0554 | 0.1246 | 0.3403 | 1 |
| multi_mom_invvol | 8 | 0.0720 | 0.0585 | 0.2936 | 0.0816 | -0.0462 | 0.3398 | 4 |
| r2_dollar_strength | 13 | 0.0574 | 0.0205 | 0.3077 | 0.2183 | -0.0317 | 0.3395 | 4 |
| r2_commodity_regime | 13 | -0.0294 | 0.0149 | 0.2476 | 0.1346 | -0.0890 | 0.3366 | 3 |
| breadth_confirmed_momentum | 8 | 0.0569 | 0.0480 | 0.2634 | 0.0794 | -0.0730 | 0.3364 | 4 |
| moving_average_distance | 13 | 0.1473 | 0.0757 | 0.2741 | 0.0624 | -0.0614 | 0.3355 | 4 |
| google_fear_regime | 13 | -0.0515 | -0.1152 | -0.2210 | -0.0101 | 0.1112 | 0.3322 | 1 |

## Bottleneck read

The evidence points more to signal quality and regime fit than missing data; most state/horizon cells have enough dates for directional read-through.

## Sample-size warnings

_No rows._

## Skipped or partial items

_No rows._

## Warnings and limitations

- None.

## Research-only confirmation

R3 wrote only `signal_state_conditional_ic.csv` and this report. It did not modify production pins, dashboard/public files, production portfolio artifacts, or live trading/execution logic.
