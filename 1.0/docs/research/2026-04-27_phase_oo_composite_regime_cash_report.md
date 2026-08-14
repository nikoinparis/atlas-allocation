# 2026-04-27 Phase OO — Composite Regime Cash Architecture Audit

## Commands Executed
```
python scripts/phase_oo_composite_regime_cash_audit.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/research_committee_report.py improved_phaseoo_composite_combined_cash_relief --quick
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/backtest_realism_audit.py improved_phaseoo_composite_combined_cash_relief --quick
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/allocator_benchmark_audit.py improved_phaseoo_composite_combined_cash_relief --quick
```

## Files Created / Modified
- Script: `scripts/phase_oo_composite_regime_cash_audit.py`
- Builder variants: `scripts/build_improvement_artifacts.py`
- Diagnostics: `data/research/phase_oo_composite_regime_cash/`
- Candidate outputs: `data/05_layer3_portfolio_construction/phase_oo_*`
- Report: `docs/research/2026-04-27_phase_oo_composite_regime_cash_report.md`

## composite_regime_conditioned BIL / Cash By State
```
                state  n_weeks  avg_BIL  avg_SPY  avg_offense  avg_defense  avg_total_risky  avg_HYG  avg_LQD  avg_TLT  avg_GLD  avg_VNQ  avg_EFA  avg_QQQ
           calm_trend      295   0.1142   0.0452       0.7327       0.1531           0.8858   0.0992   0.0984   0.0577   0.0954   0.0869   0.0802   0.0388
neutral_healthy_proxy      293   0.2291   0.0423       0.5699       0.2010           0.7709   0.0812   0.1092   0.0904   0.1105   0.0735   0.0477   0.0366
        neutral_mixed      200   0.2709   0.0411       0.5161       0.2130           0.7291   0.0732   0.1021   0.1047   0.1083   0.0796   0.0334   0.0328
   recovery_confirmed       44   0.1852   0.0142       0.5159       0.2989           0.8148   0.0866   0.1185   0.1392   0.1597   0.0810   0.0233   0.0526
     recovery_fragile       49   0.2398   0.0128       0.5324       0.2278           0.7602   0.1217   0.1301   0.1003   0.1276   0.0485   0.0485   0.0413
       stressed_panic      229   0.5380   0.0178       0.3312       0.1308           0.4620   0.0899   0.0814   0.0703   0.0605   0.0207   0.0096   0.0106
```

## Biggest Internal Source Of BIL / Cash Behavior
- stressed_panic: dominant tier 0.6500, avg hidden contribution 0.0864, classification defensive_fallback_dominant.

## BIL Source Diagnostics
```
                state  n_weeks  avg_BIL  pct_BIL_0  pct_BIL_25  pct_BIL_4375  pct_BIL_65  pct_BIL_7375  pct_BIL_100  dominant_BIL_tier  avg_prod_hidden_bil_contrib       source_classification
           calm_trend      295   0.1142     0.5593      0.4271        0.0068      0.0068        0.0000       0.0000             0.0000                       0.0344        tiered_fallback_drag
neutral_healthy_proxy      293   0.2291     0.2526      0.6382        0.0068      0.1024        0.0000       0.0000             0.2500                       0.0626        tiered_fallback_drag
        neutral_mixed      200   0.2709     0.2000      0.6400        0.0250      0.1000        0.0000       0.0350             0.2500                       0.0492        tiered_fallback_drag
   recovery_confirmed       44   0.1852     0.2955      0.6818        0.0000      0.0227        0.0000       0.0000             0.2500                       0.0618        tiered_fallback_drag
     recovery_fragile       49   0.2398     0.2041      0.6939        0.0000      0.1020        0.0000       0.0000             0.2500                       0.0648        tiered_fallback_drag
       stressed_panic      229   0.5380     0.0349      0.2271        0.0000      0.7205        0.0175       0.0000             0.6500                       0.0864 defensive_fallback_dominant
```

## Defense Or Drag?
- In `stressed_panic`, the sleeve's internal BIL looks like appropriate defense, not a bug. The `0.65` BIL tier dominates `72.05%` of stressed weeks and average sleeve-level BIL is `53.80%`.
- In `neutral_healthy_proxy`, `recovery_confirmed`, and `recovery_fragile`, the `0.25` BIL tier dominates and behaves more like excessive carry-over drag than necessary protection. Those states still carry average internal BIL of `22.91%`, `18.52%`, and `23.98%` respectively.
- The key issue is therefore not "remove composite defense." It is "relax the sleeve's quarter-cash fallback in favorable and recovery states while preserving the stressed 65% tier."

## Component Breakdown
```
       signal_name  mean_weight  median_weight  min_weight  max_weight  n_dates     component_role_guess
  multi_mom_invvol       0.1744         0.1875      0.0980      0.2075     1110      trend_momentum_core
     quality_proxy       0.1533         0.1406      0.1297      0.2157     1110 cross_sectional_balancer
 residual_momentum       0.1433         0.1562      0.0817      0.1657     1110      trend_momentum_core
      xsmom_global       0.1433         0.1562      0.0817      0.1657     1110      trend_momentum_core
         bab_proxy       0.1217         0.1094      0.1009      0.1797     1110 cross_sectional_balancer
       value_proxy       0.1046         0.1094      0.0980      0.1094     1110 cross_sectional_balancer
reversal_4w_global       0.0892         0.0625      0.0576      0.1961     1110       short_term_overlay
       carry_proxy       0.0703         0.0781      0.0490      0.0781     1110 cross_sectional_balancer
```

## Candidate Metrics Table
```
                                           name  missing  ann_return  ann_vol  sharpe  max_drawdown  calmar  cvar_5  avg_turnover  avg_BIL  avg_SPY  avg_offense  avg_defense  holdout_sharpe  holdout_ann_return  recovery_capture
       improved_phase2b_regime_confidence_boost    False      0.0689   0.0779  0.8848       -0.1398  0.4932 -0.0262        0.0562   0.2839   0.0708       0.5522       0.1639          1.6249              0.1243            0.1281
                     improved_phase2b_combo_abc    False      0.0686   0.0776  0.8840       -0.1367  0.5016 -0.0261        0.0566   0.2856   0.0708       0.5511       0.1634          1.6277              0.1236            0.1249
improved_phaseoo_composite_recovery_cash_relief    False      0.0690   0.0780  0.8847       -0.1399  0.4931 -0.0262        0.0568   0.2826   0.0710       0.5531       0.1643          1.6252              0.1245            0.1311
 improved_phaseoo_composite_neutral_cash_relief    False      0.0691   0.0783  0.8832       -0.1407  0.4912 -0.0263        0.0570   0.2802   0.0715       0.5553       0.1645          1.6209              0.1250            0.1257
improved_phaseoo_composite_combined_cash_relief    False      0.0693   0.0783  0.8854       -0.1405  0.4933 -0.0263        0.0570   0.2807   0.0718       0.5552       0.1641          1.6211              0.1250            0.1303
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
improved_phaseoo_composite_recovery_cash_relief            calm_trend      295      0.0355  0.3840   0.0685   0.0962       0.7803       0.1513              0.0008           0.0356       0.3849                   0.0008                   -0.0001               -0.0009
improved_phaseoo_composite_recovery_cash_relief neutral_healthy_proxy      293      0.0991  1.2621   0.2127   0.0864       0.6110       0.1763              0.0019           0.0992       1.2630                   0.0019                   -0.0000               -0.0009
improved_phaseoo_composite_recovery_cash_relief         neutral_mixed      200      0.1271  1.7995   0.3859   0.0649       0.4530       0.1611              0.0024           0.1271       1.7996                   0.0024                    0.0000               -0.0002
improved_phaseoo_composite_recovery_cash_relief    recovery_confirmed       44      0.0268  0.3938   0.1143   0.0597       0.5891       0.2966              0.0006           0.0261       0.3891                   0.0005                    0.0006                0.0047
improved_phaseoo_composite_recovery_cash_relief      recovery_fragile       49      0.0713  1.3340   0.2024   0.0637       0.5738       0.2237              0.0014           0.0697       1.3305                   0.0013                    0.0016                0.0036
improved_phaseoo_composite_recovery_cash_relief        stressed_panic      229      0.0337  0.4971   0.6072   0.0276       0.2623       0.1305              0.0007           0.0337       0.4978                   0.0007                   -0.0000               -0.0007
 improved_phaseoo_composite_neutral_cash_relief            calm_trend      295      0.0354  0.3831   0.0677   0.0966       0.7812       0.1511              0.0008           0.0356       0.3849                   0.0008                   -0.0002               -0.0018
 improved_phaseoo_composite_neutral_cash_relief neutral_healthy_proxy      293      0.1008  1.2663   0.2018   0.0876       0.6197       0.1785              0.0019           0.0992       1.2630                   0.0019                    0.0016                0.0033
 improved_phaseoo_composite_neutral_cash_relief         neutral_mixed      200      0.1273  1.7981   0.3853   0.0656       0.4537       0.1610              0.0024           0.1271       1.7996                   0.0024                    0.0002               -0.0016
 improved_phaseoo_composite_neutral_cash_relief    recovery_confirmed       44      0.0239  0.3578   0.1218   0.0602       0.5873       0.2909              0.0005           0.0261       0.3891                   0.0005                   -0.0022               -0.0313
 improved_phaseoo_composite_neutral_cash_relief      recovery_fragile       49      0.0699  1.3322   0.2173   0.0627       0.5628       0.2199              0.0013           0.0697       1.3305                   0.0013                    0.0002                0.0018
 improved_phaseoo_composite_neutral_cash_relief        stressed_panic      229      0.0333  0.4885   0.6063   0.0279       0.2628       0.1309              0.0007           0.0337       0.4978                   0.0007                   -0.0004               -0.0093
improved_phaseoo_composite_combined_cash_relief            calm_trend      295      0.0352  0.3811   0.0680   0.0966       0.7811       0.1509              0.0007           0.0356       0.3849                   0.0008                   -0.0003               -0.0038
improved_phaseoo_composite_combined_cash_relief neutral_healthy_proxy      293      0.1006  1.2681   0.2061   0.0879       0.6172       0.1767              0.0019           0.0992       1.2630                   0.0019                    0.0014                0.0051
improved_phaseoo_composite_combined_cash_relief         neutral_mixed      200      0.1273  1.7964   0.3855   0.0658       0.4536       0.1609              0.0024           0.1271       1.7996                   0.0024                    0.0002               -0.0033
improved_phaseoo_composite_combined_cash_relief    recovery_confirmed       44      0.0258  0.3781   0.1144   0.0631       0.5937       0.2919              0.0005           0.0261       0.3891                   0.0005                   -0.0004               -0.0110
improved_phaseoo_composite_combined_cash_relief      recovery_fragile       49      0.0717  1.3434   0.2047   0.0639       0.5723       0.2230              0.0014           0.0697       1.3305                   0.0013                    0.0019                0.0129
improved_phaseoo_composite_combined_cash_relief        stressed_panic      229      0.0337  0.4963   0.6066   0.0278       0.2625       0.1308              0.0007           0.0337       0.4978                   0.0007                    0.0000               -0.0015
```

## Candidate Diagnostics
```
                                           name                 state  avg_composite_internal_bil  composite_bil_reduction_vs_prod  avg_composite_hidden_bil_contrib  composite_hidden_bil_reduction_vs_prod  avg_composite_sleeve_weight  avg_internal_spy  avg_internal_offense  avg_internal_defense  avg_final_portfolio_bil  avg_final_portfolio_spy  state_ann_return  state_sharpe  state_mean_weekly_return
improved_phaseoo_composite_combined_cash_relief            calm_trend                      0.1142                           0.0000                            0.0339                                  0.0005                       0.3079            0.0452                0.7327                0.1531                   0.0680                   0.0966            0.0352        0.3811                    0.0007
improved_phaseoo_composite_combined_cash_relief neutral_healthy_proxy                      0.2062                           0.0229                            0.0557                                  0.0069                       0.2721            0.0441                0.5872                0.2066                   0.2061                   0.0879            0.1006        1.2681                    0.0019
improved_phaseoo_composite_combined_cash_relief         neutral_mixed                      0.2709                           0.0000                            0.0486                                  0.0006                       0.2088            0.0411                0.5161                0.2130                   0.3855                   0.0658            0.1273        1.7964                    0.0024
improved_phaseoo_composite_combined_cash_relief    recovery_confirmed                      0.1574                           0.0278                            0.0511                                  0.0107                       0.3242            0.0146                0.5340                0.3086                   0.1144                   0.0631            0.0258        0.3781                    0.0005
improved_phaseoo_composite_combined_cash_relief      recovery_fragile                      0.1918                           0.0480                            0.0513                                  0.0135                       0.2762            0.0163                0.5678                0.2404                   0.2047                   0.0639            0.0717        1.3434                    0.0014
improved_phaseoo_composite_combined_cash_relief        stressed_panic                      0.5380                           0.0000                            0.0854                                  0.0010                       0.1706            0.0178                0.3312                0.1308                   0.6066                   0.0278            0.0337        0.4963                    0.0007
 improved_phaseoo_composite_neutral_cash_relief            calm_trend                      0.1142                           0.0000                            0.0336                                  0.0008                       0.3061            0.0452                0.7327                0.1531                   0.0677                   0.0966            0.0354        0.3831                    0.0008
 improved_phaseoo_composite_neutral_cash_relief neutral_healthy_proxy                      0.1924                           0.0367                            0.0514                                  0.0112                       0.2692            0.0452                0.5976                0.2100                   0.2018                   0.0876            0.1008        1.2663                    0.0019
 improved_phaseoo_composite_neutral_cash_relief         neutral_mixed                      0.2709                           0.0000                            0.0483                                  0.0009                       0.2070            0.0411                0.5161                0.2130                   0.3853                   0.0656            0.1273        1.7981                    0.0024
 improved_phaseoo_composite_neutral_cash_relief    recovery_confirmed                      0.1852                           0.0000                            0.0583                                  0.0036                       0.3169            0.0142                0.5159                0.2989                   0.1218                   0.0602            0.0239        0.3578                    0.0005
 improved_phaseoo_composite_neutral_cash_relief      recovery_fragile                      0.2398                           0.0000                            0.0638                                  0.0010                       0.2751            0.0128                0.5324                0.2278                   0.2173                   0.0627            0.0699        1.3322                    0.0013
 improved_phaseoo_composite_neutral_cash_relief        stressed_panic                      0.5380                           0.0000                            0.0849                                  0.0015                       0.1696            0.0178                0.3312                0.1308                   0.6063                   0.0279            0.0333        0.4885                    0.0007
improved_phaseoo_composite_recovery_cash_relief            calm_trend                      0.1142                           0.0000                            0.0343                                  0.0000                       0.3109            0.0452                0.7327                0.1531                   0.0685                   0.0962            0.0355        0.3840                    0.0008
improved_phaseoo_composite_recovery_cash_relief neutral_healthy_proxy                      0.2291                           0.0000                            0.0622                                  0.0004                       0.2736            0.0423                0.5699                0.2010                   0.2127                   0.0864            0.0991        1.2621                    0.0019
improved_phaseoo_composite_recovery_cash_relief         neutral_mixed                      0.2709                           0.0000                            0.0491                                  0.0001                       0.2108            0.0411                0.5161                0.2130                   0.3859                   0.0649            0.1271        1.7995                    0.0024
improved_phaseoo_composite_recovery_cash_relief    recovery_confirmed                      0.1519                           0.0333                            0.0505                                  0.0114                       0.3298            0.0147                0.5376                0.3105                   0.1143                   0.0597            0.0268        0.3938                    0.0006
improved_phaseoo_composite_recovery_cash_relief      recovery_fragile                      0.1822                           0.0576                            0.0490                                  0.0158                       0.2777            0.0170                0.5748                0.2429                   0.2024                   0.0637            0.0713        1.3340                    0.0014
improved_phaseoo_composite_recovery_cash_relief        stressed_panic                      0.5380                           0.0000                            0.0862                                  0.0002                       0.1722            0.0178                0.3312                0.1308                   0.6072                   0.0276            0.0337        0.4971                    0.0007
```

## Did Composite Hidden BIL Drag Fall?
- Yes. The cleanest recovery-only variant reduced composite hidden BIL contribution by about `+1.14pp` in `recovery_confirmed` and `+1.58pp` in `recovery_fragile`.
- The best portfolio candidate, `improved_phaseoo_composite_combined_cash_relief`, reduced composite hidden BIL contribution by about `+0.69pp` in `neutral_healthy_proxy`, `+1.07pp` in `recovery_confirmed`, and `+1.35pp` in `recovery_fragile`.
- That reduction translated into a real but still small portfolio benefit: full-window annual return improved by about `+0.04pp` and Sharpe by about `+0.0006` versus production.

## Stressed-Panic Protection Check
- Passed. None of the OO candidates reduced the sleeve's `stressed_panic` internal BIL tier; production and all candidates stayed at average internal BIL `53.80%` in that state.
- The best candidate's `stressed_panic` mean weekly return was effectively unchanged versus production, and the quick risk-manager screen passed drawdown and CVaR caps.

## Selection Table
```
                                           name  ann_return_delta_pp_vs_prod  sharpe_delta_vs_prod  max_drawdown_delta_pp_vs_prod  cvar_delta_pp_vs_prod  turnover_ratio_vs_prod  avg_SPY_delta_pp_vs_prod  avg_composite_bil_reduction_vs_prod  avg_composite_hidden_bil_reduction_vs_prod  passes_all_gates         fail_reasons
improved_phaseoo_composite_recovery_cash_relief                       0.0056               -0.0001                        -0.0137                -0.0028                  1.0106                    0.0141                               0.0151                                      0.0046             False sharpe_delta -0.0001
 improved_phaseoo_composite_neutral_cash_relief                       0.0212               -0.0016                        -0.0988                -0.0092                  1.0128                    0.0731                               0.0061                                      0.0032             False sharpe_delta -0.0016
improved_phaseoo_composite_combined_cash_relief                       0.0371                0.0006                        -0.0725                -0.0089                  1.0140                    0.0967                               0.0164                                      0.0055             False sharpe_delta +0.0006
```

## Best Candidate
- Best candidate: `improved_phaseoo_composite_combined_cash_relief`
- Quick committee verdict: **KEEP AS SHADOW**
- Research committee report: `reports/research_committee/improved_phaseoo_composite_combined_cash_relief_audit.md`
- Layer 5/6 status: Ran quick Layer 5/6 audits.

## Final Decision
**KEEP AS SHADOW**

- Production pin remains unchanged.
- Shadow pin remains unchanged.
- This sleeve-internal cash architecture path should continue.
- Recommended next phase if this fails: deeper `composite_regime_conditioned` sleeve redesign focused on replacing the favorable-state `25%` cash tier with a more state-appropriate internal fallback mix.
