# 2026-04-27 Phase NN — Lookthrough Participation Audit

## Commands Executed
```
python scripts/phase_nn_lookthrough_participation_audit.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/research_committee_report.py improved_phasenn_mm_plus_lookthrough_relief --quick
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/backtest_realism_audit.py improved_phasenn_mm_plus_lookthrough_relief --quick
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/allocator_benchmark_audit.py improved_phasenn_mm_plus_lookthrough_relief --quick
```

## Files Created / Modified
- Script: `scripts/phase_nn_lookthrough_participation_audit.py`
- Builder variants: `scripts/build_improvement_artifacts.py`
- Diagnostics: `data/research/phase_nn_lookthrough_participation/`
- Candidate outputs: `data/05_layer3_portfolio_construction/phase_nn_*`
- Report: `docs/research/2026-04-27_phase_nn_lookthrough_participation_report.md`

## Lookthrough Drag By State
```
                state  n_weeks  avg_sleeve_cash_weight  avg_final_bil_weight  avg_lookthrough_hidden_bil_drag  avg_hidden_bil_from_sleeves  avg_sleeve_level_risky_weight  avg_etf_level_risky_weight  avg_final_spy_weight  avg_final_offensive_etf_weight  avg_final_defensive_etf_weight
           calm_trend      295                  0.0335                0.0685                           0.0350                       0.0350                         0.9665                      0.9315                0.0962                          0.7803                          0.1512
neutral_healthy_proxy      293                  0.1492                0.2131                           0.0638                       0.0638                         0.8508                      0.7869                0.0863                          0.6108                          0.1762
        neutral_mixed      200                  0.3317                0.3860                           0.0543                       0.0543                         0.6683                      0.6140                0.0648                          0.4529                          0.1611
   recovery_confirmed       44                  0.0638                0.1257                           0.0618                       0.0618                         0.9362                      0.8743                0.0596                          0.5818                          0.2925
     recovery_fragile       49                  0.1235                0.2182                           0.0947                       0.0947                         0.8765                      0.7818                0.0623                          0.5620                          0.2198
       stressed_panic      229                  0.5093                0.6074                           0.0981                       0.0981                         0.4907                      0.3926                0.0275                          0.2621                          0.1304
```

## Lookthrough Drag By Sleeve
```
                state                  sleeve_name  n_weeks  avg_sleeve_weight  avg_internal_bil  avg_hidden_bil_contrib  avg_spy_contrib  avg_offensive_etf_contrib  avg_defensive_etf_contrib
           calm_trend composite_regime_conditioned      295             0.3110            0.1142                  0.0344           0.0125                     0.2295                     0.0471
           calm_trend           dual_momentum_topn      295             0.1433            0.0305                  0.0006           0.0327                     0.1192                     0.0235
           calm_trend  composite_selective_signals      295             0.2165            0.0000                  0.0000           0.0068                     0.1773                     0.0392
           calm_trend          cta_trend_long_only      295             0.1262            0.0271                  0.0000           0.0171                     0.1178                     0.0084
           calm_trend                  taa_10m_sma      295             0.1695            0.0000                  0.0000           0.0271                     0.1365                     0.0330
neutral_healthy_proxy composite_regime_conditioned      293             0.2748            0.2291                  0.0626           0.0124                     0.1599                     0.0523
neutral_healthy_proxy           dual_momentum_topn      293             0.1136            0.0648                  0.0012           0.0244                     0.0815                     0.0309
neutral_healthy_proxy  composite_selective_signals      293             0.1977            0.0000                  0.0000           0.0079                     0.1460                     0.0517
neutral_healthy_proxy          cta_trend_long_only      293             0.1141            0.1092                  0.0000           0.0152                     0.1022                     0.0119
neutral_healthy_proxy                  taa_10m_sma      293             0.1505            0.0000                  0.0000           0.0264                     0.1211                     0.0294
        neutral_mixed composite_regime_conditioned      200             0.2113            0.2709                  0.0492           0.0109                     0.1183                     0.0438
        neutral_mixed           dual_momentum_topn      200             0.0907            0.1900                  0.0040           0.0177                     0.0617                     0.0250
        neutral_mixed                  taa_10m_sma      200             0.1115            0.1450                  0.0012           0.0216                     0.0840                     0.0264
        neutral_mixed  composite_selective_signals      200             0.1642            0.0575                  0.0000           0.0042                     0.1155                     0.0487
        neutral_mixed          cta_trend_long_only      200             0.0907            0.1800                  0.0000           0.0104                     0.0734                     0.0173
   recovery_confirmed composite_regime_conditioned       44             0.3311            0.1852                  0.0618           0.0034                     0.1670                     0.1022
   recovery_confirmed  composite_selective_signals       44             0.2311            0.0000                  0.0000           0.0016                     0.1502                     0.0809
   recovery_confirmed          cta_trend_long_only       44             0.1084            0.0000                  0.0000           0.0119                     0.0841                     0.0242
   recovery_confirmed           dual_momentum_topn       44             0.0878            0.0000                  0.0000           0.0161                     0.0507                     0.0370
   recovery_confirmed                  taa_10m_sma       44             0.1779            0.0000                  0.0000           0.0265                     0.1297                     0.0482
     recovery_fragile composite_regime_conditioned       49             0.2790            0.2398                  0.0648           0.0036                     0.1520                     0.0622
     recovery_fragile           dual_momentum_topn       49             0.1437            0.1837                  0.0299           0.0213                     0.0737                     0.0402
     recovery_fragile  composite_selective_signals       49             0.1901            0.0000                  0.0000           0.0023                     0.1347                     0.0554
     recovery_fragile          cta_trend_long_only       49             0.1246            0.0000                  0.0000           0.0097                     0.0970                     0.0275
     recovery_fragile                  taa_10m_sma       49             0.1391            0.0000                  0.0000           0.0254                     0.1046                     0.0345
       stressed_panic composite_regime_conditioned      229             0.1726            0.5380                  0.0864           0.0030                     0.0605                     0.0257
       stressed_panic           dual_momentum_topn      229             0.0635            0.1732                  0.0093           0.0112                     0.0385                     0.0158
       stressed_panic                  taa_10m_sma      229             0.0762            0.0568                  0.0024           0.0081                     0.0414                     0.0323
       stressed_panic  composite_selective_signals      229             0.1164            0.0000                  0.0000           0.0009                     0.0786                     0.0378
       stressed_panic          cta_trend_long_only      229             0.0620            0.0087                  0.0000           0.0043                     0.0431                     0.0189
```

## Biggest Hidden BIL / Cash Sources
```
                 sleeve_name  avg_hidden_bil_contrib_all_states  avg_offensive_etf_contrib  avg_defensive_etf_contrib
composite_regime_conditioned                             0.0599                     0.1479                     0.0556
          dual_momentum_topn                             0.0075                     0.0709                     0.0287
                 taa_10m_sma                             0.0006                     0.1029                     0.0340
 composite_selective_signals                             0.0000                     0.1337                     0.0523
         cta_trend_long_only                             0.0000                     0.0863                     0.0180
```

## ETF Exposure By State
```
                state  n_weeks  avg_final_bil_weight  avg_final_spy_weight  avg_final_offensive_etf_weight  avg_final_defensive_etf_weight  avg_sleeve_level_risky_weight  avg_etf_level_risky_weight
           calm_trend      295                0.0685                0.0962                          0.7803                          0.1512                         0.9665                      0.9315
neutral_healthy_proxy      293                0.2131                0.0863                          0.6108                          0.1762                         0.8508                      0.7869
        neutral_mixed      200                0.3860                0.0648                          0.4529                          0.1611                         0.6683                      0.6140
   recovery_confirmed       44                0.1257                0.0596                          0.5818                          0.2925                         0.9362                      0.8743
     recovery_fragile       49                0.2182                0.0623                          0.5620                          0.2198                         0.8765                      0.7818
       stressed_panic      229                0.6074                0.0275                          0.2621                          0.1304                         0.4907                      0.3926
```

## Candidate Metrics Table
```
                                        name  missing  ann_return  ann_vol  sharpe  max_drawdown  calmar  cvar_5  avg_turnover  avg_BIL  avg_SPY  avg_offense  avg_defense  holdout_sharpe  holdout_ann_return  recovery_capture  ann_return_delta_vs_prod  sharpe_delta_vs_prod
    improved_phase2b_regime_confidence_boost    False      0.0689   0.0779  0.8848       -0.1398  0.4932 -0.0262        0.0562   0.2839   0.0708       0.5522       0.1639          1.6249              0.1243            0.1281                    0.0000                0.0000
                  improved_phase2b_combo_abc    False      0.0686   0.0776  0.8840       -0.1367  0.5016 -0.0261        0.0566   0.2856   0.0708       0.5511       0.1634          1.6277              0.1236            0.1249                   -0.0003               -0.0008
improved_phasenn_recovery_lookthrough_relief    False      0.0690   0.0780  0.8846       -0.1399  0.4931 -0.0262        0.0568   0.2826   0.0709       0.5531       0.1643          1.6249              0.1244            0.1307                    0.0001               -0.0002
 improved_phasenn_neutral_lookthrough_relief    False      0.0691   0.0782  0.8839       -0.1405  0.4919 -0.0262        0.0567   0.2812   0.0714       0.5544       0.1645          1.6203              0.1248            0.1282                    0.0002               -0.0009
 improved_phasenn_mm_plus_lookthrough_relief    False      0.0691   0.0780  0.8851       -0.1399  0.4938 -0.0262        0.0569   0.2830   0.0712       0.5532       0.1638          1.6216              0.1244            0.1321                    0.0001                0.0003
```

## State-By-State Candidate Impact
```
                                        name                 state  n_weeks  ann_return  sharpe  avg_BIL  avg_SPY  avg_offense  avg_defense  mean_weekly_return  prod_ann_return  prod_sharpe  prod_mean_weekly_return  ann_return_delta_vs_prod  sharpe_delta_vs_prod
    improved_phase2b_regime_confidence_boost            calm_trend      295      0.0356  0.3849   0.0685   0.0962       0.7803       0.1512              0.0008           0.0356       0.3849                   0.0008                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost neutral_healthy_proxy      293      0.0992  1.2630   0.2131   0.0863       0.6108       0.1762              0.0019           0.0992       1.2630                   0.0019                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost         neutral_mixed      200      0.1271  1.7996   0.3860   0.0648       0.4529       0.1611              0.0024           0.1271       1.7996                   0.0024                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost    recovery_confirmed       44      0.0261  0.3891   0.1257   0.0596       0.5818       0.2925              0.0005           0.0261       0.3891                   0.0005                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost      recovery_fragile       49      0.0697  1.3305   0.2182   0.0623       0.5620       0.2198              0.0013           0.0697       1.3305                   0.0013                    0.0000                0.0000
    improved_phase2b_regime_confidence_boost        stressed_panic      229      0.0337  0.4978   0.6074   0.0275       0.2621       0.1304              0.0007           0.0337       0.4978                   0.0007                    0.0000                0.0000
                  improved_phase2b_combo_abc            calm_trend      295      0.0357  0.3861   0.0699   0.0961       0.7790       0.1511              0.0008           0.0356       0.3849                   0.0008                    0.0001                0.0012
                  improved_phase2b_combo_abc neutral_healthy_proxy      293      0.0990  1.2562   0.2132   0.0865       0.6110       0.1757              0.0019           0.0992       1.2630                   0.0019                   -0.0002               -0.0068
                  improved_phase2b_combo_abc         neutral_mixed      200      0.1252  1.7990   0.3899   0.0645       0.4500       0.1601              0.0023           0.1271       1.7996                   0.0024                   -0.0019               -0.0006
                  improved_phase2b_combo_abc    recovery_confirmed       44      0.0256  0.3791   0.1259   0.0597       0.5816       0.2925              0.0005           0.0261       0.3891                   0.0005                   -0.0006               -0.0101
                  improved_phase2b_combo_abc      recovery_fragile       49      0.0677  1.2979   0.2288   0.0621       0.5558       0.2154              0.0013           0.0697       1.3305                   0.0013                   -0.0020               -0.0326
                  improved_phase2b_combo_abc        stressed_panic      229      0.0343  0.5151   0.6076   0.0275       0.2621       0.1304              0.0007           0.0337       0.4978                   0.0007                    0.0006                0.0173
improved_phasenn_recovery_lookthrough_relief            calm_trend      295      0.0356  0.3849   0.0685   0.0960       0.7803       0.1512              0.0008           0.0356       0.3849                   0.0008                   -0.0000               -0.0000
improved_phasenn_recovery_lookthrough_relief neutral_healthy_proxy      293      0.0991  1.2618   0.2127   0.0864       0.6110       0.1763              0.0019           0.0992       1.2630                   0.0019                   -0.0001               -0.0012
improved_phasenn_recovery_lookthrough_relief         neutral_mixed      200      0.1271  1.7992   0.3859   0.0649       0.4530       0.1611              0.0024           0.1271       1.7996                   0.0024                   -0.0000               -0.0004
improved_phasenn_recovery_lookthrough_relief    recovery_confirmed       44      0.0268  0.3939   0.1143   0.0597       0.5891       0.2965              0.0006           0.0261       0.3891                   0.0005                    0.0006                0.0048
improved_phasenn_recovery_lookthrough_relief      recovery_fragile       49      0.0711  1.3227   0.2013   0.0635       0.5746       0.2241              0.0013           0.0697       1.3305                   0.0013                    0.0013               -0.0078
improved_phasenn_recovery_lookthrough_relief        stressed_panic      229      0.0337  0.4971   0.6073   0.0276       0.2622       0.1305              0.0007           0.0337       0.4978                   0.0007                   -0.0000               -0.0007
 improved_phasenn_neutral_lookthrough_relief            calm_trend      295      0.0355  0.3840   0.0679   0.0965       0.7809       0.1512              0.0008           0.0356       0.3849                   0.0008                   -0.0001               -0.0009
 improved_phasenn_neutral_lookthrough_relief neutral_healthy_proxy      293      0.1002  1.2635   0.2046   0.0874       0.6174       0.1780              0.0019           0.0992       1.2630                   0.0019                    0.0010                0.0006
 improved_phasenn_neutral_lookthrough_relief         neutral_mixed      200      0.1273  1.7987   0.3854   0.0656       0.4536       0.1610              0.0024           0.1271       1.7996                   0.0024                    0.0002               -0.0009
 improved_phasenn_neutral_lookthrough_relief    recovery_confirmed       44      0.0261  0.3888   0.1249   0.0598       0.5826       0.2924              0.0005           0.0261       0.3891                   0.0005                   -0.0000               -0.0003
 improved_phasenn_neutral_lookthrough_relief      recovery_fragile       49      0.0698  1.3310   0.2175   0.0626       0.5626       0.2199              0.0013           0.0697       1.3305                   0.0013                    0.0001                0.0005
 improved_phasenn_neutral_lookthrough_relief        stressed_panic      229      0.0333  0.4897   0.6065   0.0279       0.2627       0.1308              0.0007           0.0337       0.4978                   0.0007                   -0.0004               -0.0082
 improved_phasenn_mm_plus_lookthrough_relief            calm_trend      295      0.0354  0.3825   0.0686   0.0962       0.7804       0.1510              0.0008           0.0356       0.3849                   0.0008                   -0.0002               -0.0024
 improved_phasenn_mm_plus_lookthrough_relief neutral_healthy_proxy      293      0.0995  1.2646   0.2133   0.0870       0.6114       0.1753              0.0019           0.0992       1.2630                   0.0019                    0.0003                0.0017
 improved_phasenn_mm_plus_lookthrough_relief         neutral_mixed      200      0.1271  1.7978   0.3860   0.0651       0.4530       0.1610              0.0024           0.1271       1.7996                   0.0024                    0.0000               -0.0019
 improved_phasenn_mm_plus_lookthrough_relief    recovery_confirmed       44      0.0275  0.4021   0.1177   0.0623       0.5888       0.2935              0.0006           0.0261       0.3891                   0.0005                    0.0013                0.0130
 improved_phasenn_mm_plus_lookthrough_relief      recovery_fragile       49      0.0714  1.3325   0.2030   0.0636       0.5734       0.2236              0.0014           0.0697       1.3305                   0.0013                    0.0017                0.0020
 improved_phasenn_mm_plus_lookthrough_relief        stressed_panic      229      0.0337  0.4973   0.6073   0.0276       0.2622       0.1305              0.0007           0.0337       0.4978                   0.0007                   -0.0000               -0.0005
```

## Candidate Lookthrough Diagnostics
```
                                        name                 state  avg_lookthrough_hidden_bil_drag  lookthrough_drag_reduction_vs_prod  avg_final_bil_weight  avg_final_spy_weight  avg_final_offensive_etf_weight
 improved_phasenn_mm_plus_lookthrough_relief            calm_trend                           0.0351                             -0.0001                0.0686                0.0962                          0.7804
 improved_phasenn_mm_plus_lookthrough_relief neutral_healthy_proxy                           0.0641                             -0.0003                0.2133                0.0870                          0.6114
 improved_phasenn_mm_plus_lookthrough_relief         neutral_mixed                           0.0543                             -0.0000                0.3860                0.0651                          0.4530
 improved_phasenn_mm_plus_lookthrough_relief    recovery_confirmed                           0.0542                              0.0077                0.1177                0.0623                          0.5888
 improved_phasenn_mm_plus_lookthrough_relief      recovery_fragile                           0.0795                              0.0152                0.2030                0.0636                          0.5734
 improved_phasenn_mm_plus_lookthrough_relief        stressed_panic                           0.0980                              0.0001                0.6073                0.0276                          0.2622
 improved_phasenn_neutral_lookthrough_relief            calm_trend                           0.0344                              0.0006                0.0679                0.0965                          0.7809
 improved_phasenn_neutral_lookthrough_relief neutral_healthy_proxy                           0.0554                              0.0084                0.2046                0.0874                          0.6174
 improved_phasenn_neutral_lookthrough_relief         neutral_mixed                           0.0538                              0.0006                0.3854                0.0656                          0.4536
 improved_phasenn_neutral_lookthrough_relief    recovery_confirmed                           0.0611                              0.0007                0.1249                0.0598                          0.5826
 improved_phasenn_neutral_lookthrough_relief      recovery_fragile                           0.0940                              0.0007                0.2175                0.0626                          0.5626
 improved_phasenn_neutral_lookthrough_relief        stressed_panic                           0.0971                              0.0010                0.6065                0.0279                          0.2627
improved_phasenn_recovery_lookthrough_relief            calm_trend                           0.0350                              0.0000                0.0685                0.0960                          0.7803
improved_phasenn_recovery_lookthrough_relief neutral_healthy_proxy                           0.0635                              0.0003                0.2127                0.0864                          0.6110
improved_phasenn_recovery_lookthrough_relief         neutral_mixed                           0.0542                              0.0001                0.3859                0.0649                          0.4530
improved_phasenn_recovery_lookthrough_relief    recovery_confirmed                           0.0505                              0.0114                0.1143                0.0597                          0.5891
improved_phasenn_recovery_lookthrough_relief      recovery_fragile                           0.0777                              0.0170                0.2013                0.0635                          0.5746
improved_phasenn_recovery_lookthrough_relief        stressed_panic                           0.0979                              0.0002                0.6073                0.0276                          0.2622
```

## Selection Table
```
                                        name  ann_return_delta_pp_vs_prod  sharpe_delta_vs_prod  max_drawdown_delta_pp_vs_prod  cvar_delta_pp_vs_prod  turnover_ratio_vs_prod  avg_SPY_delta_pp_vs_prod  avg_lookthrough_drag_reduction_vs_prod  recovery_state_drag_reduction_vs_prod  passes_all_gates         fail_reasons
improved_phasenn_recovery_lookthrough_relief                       0.0053               -0.0002                        -0.0123                -0.0023                  1.0110                    0.0054                                  0.0048                                 0.0142             False sharpe_delta -0.0002
 improved_phasenn_neutral_lookthrough_relief                       0.0192               -0.0009                        -0.0738                -0.0068                  1.0086                    0.0608                                  0.0020                                 0.0007             False sharpe_delta -0.0009
 improved_phasenn_mm_plus_lookthrough_relief                       0.0144                0.0003                        -0.0107                -0.0033                  1.0126                    0.0388                                  0.0038                                 0.0114             False sharpe_delta +0.0003
```

## Best Candidate
- Best candidate: `improved_phasenn_mm_plus_lookthrough_relief`
- Quick committee verdict: **KEEP AS SHADOW**
- Research committee report: `reports/research_committee/improved_phasenn_mm_plus_lookthrough_relief_audit.md`
- Layer 5/6 status: Ran quick Layer 5/6 audits.

## Final Decision
**KEEP AS SHADOW**

- Production pin remains unchanged.
- Shadow pin remains unchanged.
- Lookthrough participation path should continue.
- Recommended next phase if this fails: follow-on robustness validation on the best lookthrough fix.
