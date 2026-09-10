# 2026-04-27 Phase QQ — Composite Cash-Reason Score Redesign

## Commands Executed
```
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_qq_composite_cash_reason_score.py
python scripts/phase_qq_composite_cash_reason_score.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/research_committee_report.py improved_phaseqq_pp_combined_score_filtered --quick
```

## Files Created / Modified
- Script: `scripts/phase_qq_composite_cash_reason_score.py`
- Builder variants: `scripts/build_improvement_artifacts.py`
- Diagnostics: `data/research/phase_qq_composite_cash_reason_score/`
- Candidate outputs: `data/05_layer3_portfolio_construction/phase_qq_*`
- Report: `docs/research/2026-04-27_phase_qq_composite_cash_reason_score_report.md`

## How The 25% BIL Tier Works
- The favorable-state cash fallback still appears as a discrete `25% BIL` sleeve tier rather than a small normalization residual. The stressed `65% BIL` tier is separate and was left untouched in this phase.
- Phase QQ treats the favorable `25%` tier as a set of inferred cash-defense reasons rather than one universal fallback.

## Cash Reason Categories Identified
- The reason labels are **inferred**, not exact internal saved trigger flags.
- Categories used: `signal_failed`, `no_asset_passed_filter`, `regime_uncertain`, `volatility_high`, `breadth_or_trend_weak`, `residual_normalization_cash`, `defensive_fallback`, `unknown`.

## Reason Frequency By State
```
                state             reason_category  n_weeks  state_total  share_of_state_favorable_25_bil_weeks
           calm_trend                     unknown       75          126                                 0.5952
           calm_trend residual_normalization_cash       18          126                                 0.1429
           calm_trend             volatility_high       13          126                                 0.1032
           calm_trend               signal_failed       12          126                                 0.0952
           calm_trend       breadth_or_trend_weak        8          126                                 0.0635
neutral_healthy_proxy             volatility_high       73          187                                 0.3904
neutral_healthy_proxy                     unknown       33          187                                 0.1765
neutral_healthy_proxy       breadth_or_trend_weak       30          187                                 0.1604
neutral_healthy_proxy            regime_uncertain       24          187                                 0.1283
neutral_healthy_proxy               signal_failed       17          187                                 0.0909
neutral_healthy_proxy          defensive_fallback       10          187                                 0.0535
   recovery_confirmed             volatility_high       30           30                                 1.0000
     recovery_fragile             volatility_high       31           34                                 0.9118
     recovery_fragile          defensive_fallback        3           34                                 0.0882
```

## Reason Forward-Outcome Diagnostics
```
            reason_category  n_weeks  share_of_total_favorable_25_bil_weeks  avg_composite_forward_4w_return  avg_composite_forward_13w_return  avg_production_forward_4w_return  avg_production_forward_13w_return  avg_SPY_forward_4w_return  avg_SPY_forward_13w_return  prob_stressed_panic_within_next_4w  prob_prod_drawdown_worsen_next_4w
            volatility_high      147                                 0.3899                           0.0088                            0.0254                            0.0072                             0.0249                     0.0131                      0.0377                              0.0476                             0.6667
                    unknown      108                                 0.2865                           0.0024                            0.0102                            0.0035                             0.0114                     0.0082                      0.0245                              0.0833                             0.7037
      breadth_or_trend_weak       38                                 0.1008                           0.0104                            0.0240                            0.0099                             0.0225                     0.0092                      0.0126                              0.0789                             0.6579
              signal_failed       29                                 0.0769                           0.0043                            0.0233                            0.0029                             0.0132                     0.0071                      0.0373                              0.0000                             0.3448
           regime_uncertain       24                                 0.0637                           0.0092                            0.0316                            0.0079                             0.0309                     0.0282                      0.0748                              0.0000                             0.7917
residual_normalization_cash       18                                 0.0477                           0.0066                            0.0326                            0.0043                             0.0307                     0.0166                      0.0476                              0.0000                             0.8889
         defensive_fallback       13                                 0.0345                          -0.0057                            0.0052                           -0.0039                             0.0094                     0.0038                      0.0434                              0.0000                             0.8462
```

## Reason Feature Profile
```
            reason_category  n_weeks  avg_volatility_pressure  avg_breadth_sma_43  avg_breadth_13w_mom  avg_breadth_change_4w  avg_drawdown_pressure  avg_correlation_pressure  avg_market_trend_positive  avg_risk_regime_score  avg_recent_stress_26w  avg_transition_good_state_prob  avg_transition_non_stress_prob  avg_transition_persistence_prob
            volatility_high      147                   0.0376              0.7983               0.7731                 0.0680                -0.0251                    0.0961                     1.0000                -0.0196                 0.7415                          0.4010                          0.9573                           0.7053
                    unknown      108                  -0.0080              0.8128               0.7077                 0.0040                -0.0193                   -0.9894                     1.0000                -0.5258                 0.0000                          0.6358                          0.9855                           0.8264
      breadth_or_trend_weak       38                  -0.2818              0.6353               0.4455                -0.1466                -0.0381                   -0.5701                     1.0000                -0.4434                 0.0000                          0.2728                          0.9587                           0.8320
              signal_failed       29                  -0.4227              0.7414               0.6847                 0.0172                -0.0098                   -0.5354                     1.0000                -0.3198                 0.0000                          0.2882                          0.9830                           0.8721
           regime_uncertain       24                   0.1896              0.8304               0.7798                -0.0119                -0.0055                   -0.5857                     1.0000                -0.3175                 0.0000                          0.1536                          0.9244                           0.7708
residual_normalization_cash       18                  -0.4996              0.9008               0.8730                 0.1151                -0.0013                   -1.2686                     1.0000                -0.8395                 0.0000                          0.8552                          1.0000                           0.8530
         defensive_fallback       13                  -0.1512              0.6703               0.5934                -0.0055                -0.0685                    1.0164                     1.0000                 0.1702                 0.9231                          0.2195                          0.9314                           0.7405
```

## Cash-Defense Score Definition
- Score uses only current / past features: volatility pressure, drawdown pressure, correlation pressure, recent stress, breadth weakness, trend weakness, and regime-transition uncertainty.
- Inferred reason labels are used only as small causal adjustments, not as future labels.
- Higher score means BIL is more likely useful defense; lower score means BIL is more likely drag.

## Cash-Defense Score Thresholds
```json
{
  "low_defense_threshold": 0.3318559556786704,
  "high_defense_threshold": 0.6709141274238228,
  "bucket_method": "33/67 percentile split on favorable-state 25% BIL weeks",
  "reason_thresholds": {
    "corr_high": 0.6407003982224198,
    "corr_mid": -0.1675629589272404,
    "stress_high": 1.0,
    "stress_mid": 0.0,
    "drawdown_bad": -0.09413192718533303,
    "drawdown_mid": -0.0228334913312633,
    "breadth43_low": 0.5714285714285714,
    "breadth43_high": 0.7857142857142857,
    "breadth13_low": 0.5,
    "breadth13_high": 0.7857142857142857,
    "breadth4_low": -0.0714285714285714,
    "breadth4_high": 0.0714285714285714,
    "good_low": 0.08427304756312387,
    "good_high": 0.5696138996139,
    "nonstress_low": 0.9294871794871796,
    "nonstress_high": 1.0,
    "persist_low": 0.8012820512820513
  }
}
```

## Does The Score Separate Dangerous Vs Benign BIL Weeks?
- **No** based on the high-vs-low bucket comparison of forward returns and forward stress / drawdown worsening probabilities.
- In practice, `high_defense` weeks did **not** show clearly worse forward sleeve outcomes than `low_defense` weeks, and `medium_defense` was actually the strongest forward bucket. That is the main reason this phase does not clear the hypothesis cleanly.

## Cash-Defense Bucket Forward Outcomes
```
cash_defense_bucket  n_weeks  avg_composite_forward_4w_return  avg_composite_forward_13w_return  avg_production_forward_4w_return  avg_production_forward_13w_return  prob_stressed_panic_within_next_4w  prob_prod_drawdown_worsen_next_4w
       high_defense      119                           0.0070                            0.0171                            0.0058                             0.0179                              0.0252                             0.7143
        low_defense      119                           0.0032                            0.0159                            0.0033                             0.0150                              0.0420                             0.6807
     medium_defense      139                           0.0080                            0.0282                            0.0075                             0.0261                              0.0791                             0.6403
```

## Fallback Mixes Tested
```
cash_defense_bucket               mix_name  n_weeks  avg_approx_forward_4w_return  avg_approx_forward_13w_return  prob_stressed_panic_within_next_4w  prob_prod_drawdown_worsen_next_4w  avg_replacement_fraction_of_25_bil
       high_defense       PP_best_fallback      119                        0.0059                         0.0164                              0.0252                             0.7143                              0.5000
       high_defense active_sleeve_redeploy      119                        0.0070                         0.0163                              0.0252                             0.7143                              0.4500
       high_defense     balanced_defensive      119                        0.0061                         0.0159                              0.0252                             0.7143                              0.4000
       high_defense               keep_BIL      119                        0.0062                         0.0146                              0.0252                             0.7143                              0.0000
       high_defense      partial_bond_gold      119                        0.0061                         0.0155                              0.0252                             0.7143                              0.2500
        low_defense       PP_best_fallback      119                        0.0020                         0.0113                              0.0420                             0.6807                              0.5000
        low_defense active_sleeve_redeploy      119                        0.0010                         0.0103                              0.0420                             0.6807                              0.4500
        low_defense     balanced_defensive      119                        0.0015                         0.0105                              0.0420                             0.6807                              0.4000
        low_defense               keep_BIL      119                        0.0010                         0.0095                              0.0420                             0.6807                              0.0000
        low_defense      partial_bond_gold      119                        0.0015                         0.0104                              0.0420                             0.6807                              0.2500
     medium_defense       PP_best_fallback      139                        0.0061                         0.0221                              0.0791                             0.6403                              0.5000
     medium_defense active_sleeve_redeploy      139                        0.0067                         0.0227                              0.0791                             0.6403                              0.4500
     medium_defense     balanced_defensive      139                        0.0061                         0.0216                              0.0791                             0.6403                              0.4000
     medium_defense               keep_BIL      139                        0.0060                         0.0202                              0.0791                             0.6403                              0.0000
     medium_defense      partial_bond_gold      139                        0.0061                         0.0212                              0.0791                             0.6403                              0.2500
```

## Fallback Mix Risk Summary
```
cash_defense_bucket               mix_name  n_weeks  avg_approx_forward_4w_return  avg_approx_forward_13w_return  prob_stressed_panic_within_next_4w  prob_prod_drawdown_worsen_next_4w  avg_replacement_fraction_of_25_bil  keep_forward_4w  keep_forward_13w  approx_forward_4w_delta_vs_keep  approx_forward_13w_delta_vs_keep
       high_defense       PP_best_fallback      119                        0.0059                         0.0164                              0.0252                             0.7143                              0.5000           0.0062            0.0146                          -0.0003                            0.0018
       high_defense active_sleeve_redeploy      119                        0.0070                         0.0163                              0.0252                             0.7143                              0.4500           0.0062            0.0146                           0.0008                            0.0017
       high_defense     balanced_defensive      119                        0.0061                         0.0159                              0.0252                             0.7143                              0.4000           0.0062            0.0146                          -0.0001                            0.0013
       high_defense               keep_BIL      119                        0.0062                         0.0146                              0.0252                             0.7143                              0.0000           0.0062            0.0146                           0.0000                            0.0000
       high_defense      partial_bond_gold      119                        0.0061                         0.0155                              0.0252                             0.7143                              0.2500           0.0062            0.0146                          -0.0001                            0.0009
        low_defense       PP_best_fallback      119                        0.0020                         0.0113                              0.0420                             0.6807                              0.5000           0.0010            0.0095                           0.0010                            0.0017
        low_defense active_sleeve_redeploy      119                        0.0010                         0.0103                              0.0420                             0.6807                              0.4500           0.0010            0.0095                          -0.0000                            0.0008
        low_defense     balanced_defensive      119                        0.0015                         0.0105                              0.0420                             0.6807                              0.4000           0.0010            0.0095                           0.0006                            0.0010
        low_defense               keep_BIL      119                        0.0010                         0.0095                              0.0420                             0.6807                              0.0000           0.0010            0.0095                           0.0000                            0.0000
        low_defense      partial_bond_gold      119                        0.0015                         0.0104                              0.0420                             0.6807                              0.2500           0.0010            0.0095                           0.0005                            0.0009
     medium_defense       PP_best_fallback      139                        0.0061                         0.0221                              0.0791                             0.6403                              0.5000           0.0060            0.0202                           0.0001                            0.0019
     medium_defense active_sleeve_redeploy      139                        0.0067                         0.0227                              0.0791                             0.6403                              0.4500           0.0060            0.0202                           0.0007                            0.0025
     medium_defense     balanced_defensive      139                        0.0061                         0.0216                              0.0791                             0.6403                              0.4000           0.0060            0.0202                           0.0001                            0.0014
     medium_defense               keep_BIL      139                        0.0060                         0.0202                              0.0791                             0.6403                              0.0000           0.0060            0.0202                           0.0000                            0.0000
     medium_defense      partial_bond_gold      139                        0.0061                         0.0212                              0.0791                             0.6403                              0.2500           0.0060            0.0202                           0.0000                            0.0010
```

## Candidates Tested
- `improved_phaseqq_cash_defense_score_fallback`
- `improved_phaseqq_reason_specific_fallback`
- `improved_phaseqq_pp_combined_score_filtered`

## Candidate Metrics Table
```
                                        name  missing  ann_return  ann_vol  sharpe  max_drawdown  calmar  cvar_5  avg_turnover  avg_BIL  avg_SPY  avg_offense  avg_defense  holdout_sharpe  holdout_ann_return  recovery_capture
    improved_phase2b_regime_confidence_boost    False      0.0689   0.0779  0.8848       -0.1398  0.4932 -0.0262        0.0562   0.2839   0.0708       0.4750       0.2411          1.6249              0.1243            0.1281
                  improved_phase2b_combo_abc    False      0.0686   0.0776  0.8840       -0.1367  0.5016 -0.0261        0.0566   0.2856   0.0708       0.4743       0.2402          1.6277              0.1236            0.1249
improved_phaseqq_cash_defense_score_fallback    False      0.0690   0.0783  0.8818       -0.1402  0.4925 -0.0264        0.0581   0.2769   0.0708       0.4755       0.2477          1.6221              0.1256            0.1303
   improved_phaseqq_reason_specific_fallback    False      0.0688   0.0786  0.8749       -0.1515  0.4541 -0.0265        0.0567   0.2824   0.0713       0.4760       0.2416          1.6285              0.1250            0.1281
 improved_phaseqq_pp_combined_score_filtered    False      0.0697   0.0784  0.8886       -0.1401  0.4975 -0.0264        0.0576   0.2768   0.0714       0.4781       0.2451          1.6376              0.1265            0.1328
```

## State-By-State Candidate Impact
```
                                        name                 state  n_weeks  ann_return  sharpe  avg_BIL  avg_SPY  avg_offense  avg_defense  mean_weekly_return  prod_ann_return  prod_sharpe  prod_mean_weekly_return  ann_return_delta_vs_prod  sharpe_delta_vs_prod
    improved_phase2b_regime_confidence_boost            calm_trend      295      0.0356  0.3849   0.0685   0.0962       0.6927       0.2388              0.0008           0.0356       0.3849                   0.0008                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost neutral_healthy_proxy      293      0.0992  1.2630   0.2131   0.0863       0.5263       0.2606              0.0019           0.0992       1.2630                   0.0019                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost         neutral_mixed      200      0.1271  1.7996   0.3860   0.0648       0.3827       0.2313              0.0024           0.1271       1.7996                   0.0024                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost    recovery_confirmed       44      0.0261  0.3891   0.1257   0.0596       0.4717       0.4026              0.0005           0.0261       0.3891                   0.0005                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost      recovery_fragile       49      0.0697  1.3305   0.2182   0.0623       0.4558       0.3260              0.0013           0.0697       1.3305                   0.0013                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost        stressed_panic      229      0.0337  0.4978   0.6074   0.0275       0.2141       0.1785              0.0007           0.0337       0.4978                   0.0007                    0.0000                0.0000
                  improved_phase2b_combo_abc            calm_trend      295      0.0357  0.3861   0.0699   0.0961       0.6917       0.2384              0.0008           0.0356       0.3849                   0.0008                    0.0001                0.0012
                  improved_phase2b_combo_abc neutral_healthy_proxy      293      0.0990  1.2562   0.2132   0.0865       0.5270       0.2598              0.0019           0.0992       1.2630                   0.0019                   -0.0002               -0.0068
                  improved_phase2b_combo_abc         neutral_mixed      200      0.1252  1.7990   0.3899   0.0645       0.3802       0.2298              0.0023           0.1271       1.7996                   0.0024                   -0.0019               -0.0006
                  improved_phase2b_combo_abc    recovery_confirmed       44      0.0256  0.3791   0.1259   0.0597       0.4720       0.4021              0.0005           0.0261       0.3891                   0.0005                   -0.0006               -0.0101
                  improved_phase2b_combo_abc      recovery_fragile       49      0.0677  1.2979   0.2288   0.0621       0.4520       0.3192              0.0013           0.0697       1.3305                   0.0013                   -0.0020               -0.0326
                  improved_phase2b_combo_abc        stressed_panic      229      0.0343  0.5151   0.6076   0.0275       0.2140       0.1785              0.0007           0.0337       0.4978                   0.0007                    0.0006                0.0173
improved_phaseqq_cash_defense_score_fallback            calm_trend      295      0.0366  0.3942   0.0541   0.0965       0.6934       0.2525              0.0008           0.0356       0.3849                   0.0008                    0.0011                0.0092
improved_phaseqq_cash_defense_score_fallback neutral_healthy_proxy      293      0.0987  1.2492   0.2054   0.0864       0.5270       0.2675              0.0019           0.0992       1.2630                   0.0019                   -0.0005               -0.0138
improved_phaseqq_cash_defense_score_fallback         neutral_mixed      200      0.1275  1.8020   0.3853   0.0646       0.3829       0.2318              0.0024           0.1271       1.7996                   0.0024                    0.0004                0.0024
improved_phaseqq_cash_defense_score_fallback    recovery_confirmed       44      0.0271  0.3990   0.1085   0.0598       0.4723       0.4192              0.0006           0.0261       0.3891                   0.0005                    0.0010                0.0099
improved_phaseqq_cash_defense_score_fallback      recovery_fragile       49      0.0705  1.3423   0.2152   0.0624       0.4561       0.3287              0.0013           0.0697       1.3305                   0.0013                    0.0008                0.0119
improved_phaseqq_cash_defense_score_fallback        stressed_panic      229      0.0328  0.4822   0.6062   0.0271       0.2143       0.1795              0.0007           0.0337       0.4978                   0.0007                   -0.0009               -0.0156
   improved_phaseqq_reason_specific_fallback            calm_trend      295      0.0349  0.3726   0.0654   0.0971       0.6955       0.2391              0.0007           0.0356       0.3849                   0.0008                   -0.0007               -0.0123
   improved_phaseqq_reason_specific_fallback neutral_healthy_proxy      293      0.0995  1.2652   0.2119   0.0865       0.5268       0.2613              0.0019           0.0992       1.2630                   0.0019                    0.0003                0.0022
   improved_phaseqq_reason_specific_fallback         neutral_mixed      200      0.1279  1.8083   0.3855   0.0651       0.3830       0.2315              0.0024           0.1271       1.7996                   0.0024                    0.0008                0.0086
   improved_phaseqq_reason_specific_fallback    recovery_confirmed       44      0.0261  0.3888   0.1255   0.0596       0.4719       0.4027              0.0005           0.0261       0.3891                   0.0005                   -0.0000               -0.0003
   improved_phaseqq_reason_specific_fallback      recovery_fragile       49      0.0697  1.3300   0.2181   0.0624       0.4559       0.3260              0.0013           0.0697       1.3305                   0.0013                   -0.0000               -0.0005
   improved_phaseqq_reason_specific_fallback        stressed_panic      229      0.0330  0.4750   0.6059   0.0280       0.2146       0.1795              0.0007           0.0337       0.4978                   0.0007                   -0.0007               -0.0228
 improved_phaseqq_pp_combined_score_filtered            calm_trend      295      0.0367  0.3945   0.0537   0.0968       0.6941       0.2522              0.0008           0.0356       0.3849                   0.0008                    0.0011                0.0096
 improved_phaseqq_pp_combined_score_filtered neutral_healthy_proxy      293      0.1009  1.2732   0.2066   0.0876       0.5328       0.2606              0.0019           0.0992       1.2630                   0.0019                    0.0017                0.0102
 improved_phaseqq_pp_combined_score_filtered         neutral_mixed      200      0.1273  1.7979   0.3851   0.0650       0.3835       0.2313              0.0024           0.1271       1.7996                   0.0024                    0.0002               -0.0017
 improved_phaseqq_pp_combined_score_filtered    recovery_confirmed       44      0.0278  0.4067   0.1159   0.0627       0.4827       0.4013              0.0006           0.0261       0.3891                   0.0005                    0.0017                0.0176
 improved_phaseqq_pp_combined_score_filtered      recovery_fragile       49      0.0717  1.3440   0.2048   0.0639       0.4642       0.3310              0.0014           0.0697       1.3305                   0.0013                    0.0020                0.0135
 improved_phaseqq_pp_combined_score_filtered        stressed_panic      229      0.0329  0.4837   0.6056   0.0271       0.2146       0.1797              0.0007           0.0337       0.4978                   0.0007                   -0.0008               -0.0141
```

## Composite Internal BIL Reduction
```
                                        name          group_type            group_name  avg_composite_internal_bil  composite_bil_reduction_vs_prod  avg_composite_hidden_bil_contrib  composite_hidden_bil_reduction_vs_prod  avg_final_portfolio_bil  avg_final_portfolio_spy
improved_phaseqq_cash_defense_score_fallback               state            calm_trend                      0.0694                           0.0447                            0.0200                                  0.0144                   0.0541                   0.0965
improved_phaseqq_cash_defense_score_fallback               state neutral_healthy_proxy                      0.2026                           0.0265                            0.0550                                  0.0076                   0.2054                   0.0864
improved_phaseqq_cash_defense_score_fallback               state         neutral_mixed                      0.2709                           0.0000                            0.0486                                  0.0006                   0.3853                   0.0646
improved_phaseqq_cash_defense_score_fallback               state    recovery_confirmed                      0.1369                           0.0483                            0.0447                                  0.0171                   0.1085                   0.0598
improved_phaseqq_cash_defense_score_fallback               state      recovery_fragile                      0.2296                           0.0102                            0.0618                                  0.0030                   0.2152                   0.0624
improved_phaseqq_cash_defense_score_fallback               state        stressed_panic                      0.5380                           0.0000                            0.0854                                  0.0010                   0.6062                   0.0271
improved_phaseqq_cash_defense_score_fallback cash_defense_bucket          high_defense                      0.2500                           0.0000                            0.0692                                  0.0008                   0.2155                   0.0859
improved_phaseqq_cash_defense_score_fallback cash_defense_bucket           low_defense                      0.1250                           0.1250                            0.0392                                  0.0398                   0.1146                   0.1008
improved_phaseqq_cash_defense_score_fallback cash_defense_bucket        medium_defense                      0.1875                           0.0625                            0.0525                                  0.0179                   0.1781                   0.0804
   improved_phaseqq_reason_specific_fallback               state            calm_trend                      0.1053                           0.0089                            0.0313                                  0.0031                   0.0654                   0.0971
   improved_phaseqq_reason_specific_fallback               state neutral_healthy_proxy                      0.2265                           0.0026                            0.0615                                  0.0011                   0.2119                   0.0865
   improved_phaseqq_reason_specific_fallback               state         neutral_mixed                      0.2709                           0.0000                            0.0488                                  0.0004                   0.3855                   0.0651
   improved_phaseqq_reason_specific_fallback               state    recovery_confirmed                      0.1852                           0.0000                            0.0616                                  0.0002                   0.1255                   0.0596
   improved_phaseqq_reason_specific_fallback               state      recovery_fragile                      0.2398                           0.0000                            0.0646                                  0.0002                   0.2181                   0.0624
   improved_phaseqq_reason_specific_fallback               state        stressed_panic                      0.5380                           0.0000                            0.0849                                  0.0015                   0.6059                   0.0280
   improved_phaseqq_reason_specific_fallback cash_defense_bucket          high_defense                      0.2500                           0.0000                            0.0695                                  0.0005                   0.2158                   0.0857
   improved_phaseqq_reason_specific_fallback cash_defense_bucket           low_defense                      0.2267                           0.0233                            0.0708                                  0.0082                   0.1462                   0.1032
   improved_phaseqq_reason_specific_fallback cash_defense_bucket        medium_defense                      0.2457                           0.0043                            0.0693                                  0.0010                   0.1950                   0.0803
 improved_phaseqq_pp_combined_score_filtered               state            calm_trend                      0.0680                           0.0462                            0.0197                                  0.0147                   0.0537                   0.0968
 improved_phaseqq_pp_combined_score_filtered               state neutral_healthy_proxy                      0.2062                           0.0229                            0.0562                                  0.0064                   0.2066                   0.0876
 improved_phaseqq_pp_combined_score_filtered               state         neutral_mixed                      0.2709                           0.0000                            0.0484                                  0.0008                   0.3851                   0.0650
 improved_phaseqq_pp_combined_score_filtered               state    recovery_confirmed                      0.1574                           0.0278                            0.0524                                  0.0094                   0.1159                   0.0627
 improved_phaseqq_pp_combined_score_filtered               state      recovery_fragile                      0.1918                           0.0480                            0.0513                                  0.0135                   0.2048                   0.0639
 improved_phaseqq_pp_combined_score_filtered               state        stressed_panic                      0.5380                           0.0000                            0.0847                                  0.0017                   0.6056                   0.0271
 improved_phaseqq_pp_combined_score_filtered cash_defense_bucket          high_defense                      0.2200                           0.0300                            0.0612                                  0.0088                   0.2074                   0.0873
 improved_phaseqq_pp_combined_score_filtered cash_defense_bucket           low_defense                      0.1504                           0.0996                            0.0463                                  0.0327                   0.1217                   0.1012
 improved_phaseqq_pp_combined_score_filtered cash_defense_bucket        medium_defense                      0.2090                           0.0410                            0.0590                                  0.0114                   0.1846                   0.0815
```

## Stressed-Panic Protection Check
- The Phase QQ actions only apply to favorable-state `25% BIL` rows. The stressed `65%` tier remains untouched by construction.
- See `stressed_panic` rows in the state summary and candidate diagnostics for any spillover.

## Recovery-Fragile Protection Check
- Recovery-fragile performance is explicitly checked in the selection gate.
- See `recovery_fragile` rows in the state summary.

## Hidden Beta / Hidden SPY Check
- Hidden beta / SPY checks passed narrowly; SPY deltas stayed modest and Sharpe changes, not raw beta drift alone, drove the verdict.

## Best Candidate
- Best candidate: `improved_phaseqq_pp_combined_score_filtered`
- Quick committee verdict: **KEEP AS SHADOW**
- Research committee report: `reports/research_committee/improved_phaseqq_pp_combined_score_filtered_audit.md`
- Layer 5/6 status: Skipped Layer 5/6 quick audits.
- Interpretation: QQ3 is best because it behaves like a more selective PP-combined redesign, not because the new cash-defense score convincingly solved the useful-BIL-vs-drag problem.

## Final Decision
**KEEP AS SHADOW**

- Production pin remains unchanged.
- Shadow pin remains unchanged.
- This component-level cash-defense-score path should probably **not** continue in its current narrow form.
- Recommended next phase if this fails: stop modifying `composite_regime_conditioned` via small cash-tier heuristics and move to a broader allocator / sleeve-architecture redesign, because the score did not cleanly separate useful defense from drag.
