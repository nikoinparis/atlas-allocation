# 2026-04-27 Phase PP — Composite Fallback Redesign

## Commands Executed
```
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_pp_composite_fallback_redesign.py
python scripts/phase_pp_composite_fallback_redesign.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/build_improvement_artifacts.py
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/research_committee_report.py improved_phasepp_composite_combined_fallback_redesign --quick
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/backtest_realism_audit.py improved_phasepp_composite_combined_fallback_redesign --quick
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/nicholasturangan/Documents/Portfolio Optimizer/scripts/allocator_benchmark_audit.py improved_phasepp_composite_combined_fallback_redesign --quick
```

## Files Created / Modified
- Script: `scripts/phase_pp_composite_fallback_redesign.py`
- Builder variants: `scripts/build_improvement_artifacts.py`
- Diagnostics: `data/research/phase_pp_composite_fallback_redesign/`
- Candidate outputs: `data/05_layer3_portfolio_construction/phase_pp_*`
- Report: `docs/research/2026-04-27_phase_pp_composite_fallback_redesign_report.md`
- Quick audits: `reports/research_committee/improved_phasepp_composite_combined_fallback_redesign_audit.md`, `reports/backtest_realism/improved_phasepp_composite_combined_fallback_redesign_realism_audit.md`, `reports/allocator_benchmark/improved_phasepp_composite_combined_fallback_redesign_allocator_benchmark.md`

## How The 25% BIL Tier Works
- The favorable-state fallback manifests as a discrete sleeve-position tier rather than a small residual weight. In the saved sleeve outputs, the common pattern is `25% BIL` plus four non-cash holdings at roughly `18.75%` each.
- The stressed architecture is separate: the high-defense tier is around `65% BIL` and is preserved unchanged in this phase.

## Fallback Tier By State
```
                state  n_weeks  avg_BIL  pct_BIL_0  pct_BIL_25  pct_BIL_65  pct_BIL_7375  dominant_BIL_tier  avg_noncash_offense_when_25  avg_noncash_defense_when_25  avg_GLD_when_25  avg_TLT_when_25  avg_LQD_when_25  avg_HYG_when_25  avg_SPY_when_25
           calm_trend      295   0.1142     0.5593      0.4271      0.0068        0.0000             0.0000                       0.6607                       0.0893           0.0551           0.0342           0.0699           0.0789           0.0476
neutral_healthy_proxy      293   0.2291     0.2526      0.6382      0.1024        0.0000             0.2500                       0.5685                       0.1815           0.1023           0.0792           0.1143           0.0672           0.0311
        neutral_mixed      200   0.2709     0.2000      0.6400      0.1000        0.0000             0.2500                       0.5273                       0.2227           0.1084           0.1143           0.1069           0.0850           0.0293
   recovery_confirmed       44   0.1852     0.2955      0.6818      0.0227        0.0000             0.2500                       0.4813                       0.2687           0.1313           0.1375           0.1125           0.0938           0.0125
     recovery_fragile       49   0.2398     0.2041      0.6939      0.1020        0.0000             0.2500                       0.5349                       0.2151           0.1103           0.1048           0.1158           0.1213           0.0055
       stressed_panic      229   0.5380     0.0349      0.2271      0.7205        0.0175             0.6500                       0.4976                       0.2524           0.1046           0.1478           0.1370           0.1478           0.0216
```

## Fallback Mix Candidates Tested
```
                                                  name  keep_bil_fraction                        fallback_mix  avg_internal_bil_all  avg_internal_bil_favorable  avg_internal_bil_stressed  pct_target_25_rows_touched  avg_hidden_bil_contrib  ann_return  sharpe  avg_BIL_portfolio  avg_SPY_portfolio
         improved_phasepp_composite_bond_gold_fallback             0.5000                   GLD:0.50|TLT:0.50                0.2261                      0.1080                     0.5380                      0.3396                  0.0453      0.0690  0.8754             0.2702             0.0712
improved_phasepp_composite_balanced_defensive_fallback             0.4500 GLD:0.35|TLT:0.30|LQD:0.20|HYG:0.15                0.2218                      0.1011                     0.5380                      0.3396                  0.0440      0.0690  0.8757             0.2691             0.0713
 improved_phasepp_composite_combined_fallback_redesign             0.5000                   GLD:0.50|TLT:0.50                0.2451                      0.1390                     0.5380                      0.3396                  0.0507      0.0697  0.8879             0.2764             0.0716
```

## Candidate Metrics Table
```
                                                  name  missing  ann_return  ann_vol  sharpe  max_drawdown  calmar  cvar_5  avg_turnover  avg_BIL  avg_SPY  avg_offense  avg_defense  holdout_sharpe  holdout_ann_return  recovery_capture
              improved_phase2b_regime_confidence_boost    False      0.0689   0.0779  0.8848       -0.1398  0.4932 -0.0262        0.0562   0.2839   0.0708       0.5522       0.1639          1.6249              0.1243            0.1281
                            improved_phase2b_combo_abc    False      0.0686   0.0776  0.8840       -0.1367  0.5016 -0.0261        0.0566   0.2856   0.0708       0.5511       0.1634          1.6277              0.1236            0.1249
         improved_phasepp_composite_bond_gold_fallback    False      0.0690   0.0788  0.8754       -0.1415  0.4878 -0.0266        0.0573   0.2702   0.0712       0.5533       0.1765          1.6426              0.1286            0.1243
improved_phasepp_composite_balanced_defensive_fallback    False      0.0690   0.0788  0.8757       -0.1414  0.4879 -0.0266        0.0573   0.2691   0.0713       0.5578       0.1731          1.6399              0.1280            0.1257
 improved_phasepp_composite_combined_fallback_redesign    False      0.0697   0.0785  0.8879       -0.1401  0.4973 -0.0264        0.0576   0.2764   0.0716       0.5548       0.1688          1.6345              0.1263            0.1328
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
         improved_phasepp_composite_bond_gold_fallback            calm_trend      295      0.0364  0.3911   0.0516   0.0968       0.7812       0.1672              0.0008           0.0356       0.3849                   0.0008                    0.0009                0.0062
         improved_phasepp_composite_bond_gold_fallback neutral_healthy_proxy      293      0.0996  1.2432   0.1898   0.0868       0.6121       0.1982              0.0019           0.0992       1.2630                   0.0019                    0.0004               -0.0198
         improved_phasepp_composite_bond_gold_fallback         neutral_mixed      200      0.1277  1.8017   0.3847   0.0654       0.4536       0.1617              0.0024           0.1271       1.7996                   0.0024                    0.0006                0.0021
         improved_phasepp_composite_bond_gold_fallback    recovery_confirmed       44      0.0269  0.3919   0.0941   0.0601       0.5850       0.3209              0.0006           0.0261       0.3891                   0.0005                    0.0007                0.0028
         improved_phasepp_composite_bond_gold_fallback      recovery_fragile       49      0.0659  1.2192   0.1928   0.0633       0.5631       0.2441              0.0013           0.0697       1.3305                   0.0013                   -0.0039               -0.1113
         improved_phasepp_composite_bond_gold_fallback        stressed_panic      229      0.0327  0.4770   0.6053   0.0274       0.2633       0.1314              0.0007           0.0337       0.4978                   0.0007                   -0.0010               -0.0208
improved_phasepp_composite_balanced_defensive_fallback            calm_trend      295      0.0362  0.3886   0.0500   0.0968       0.7873       0.1626              0.0008           0.0356       0.3849                   0.0008                    0.0006                0.0037
improved_phasepp_composite_balanced_defensive_fallback neutral_healthy_proxy      293      0.0999  1.2490   0.1878   0.0867       0.6202       0.1920              0.0019           0.0992       1.2630                   0.0019                    0.0007               -0.0140
improved_phasepp_composite_balanced_defensive_fallback         neutral_mixed      200      0.1273  1.7934   0.3845   0.0655       0.4535       0.1620              0.0024           0.1271       1.7996                   0.0024                    0.0002               -0.0063
improved_phasepp_composite_balanced_defensive_fallback    recovery_confirmed       44      0.0272  0.3971   0.0916   0.0600       0.5951       0.3133              0.0006           0.0261       0.3891                   0.0005                    0.0010                0.0080
improved_phasepp_composite_balanced_defensive_fallback      recovery_fragile       49      0.0667  1.2403   0.1911   0.0632       0.5718       0.2371              0.0013           0.0697       1.3305                   0.0013                   -0.0030               -0.0902
improved_phasepp_composite_balanced_defensive_fallback        stressed_panic      229      0.0326  0.4769   0.6054   0.0276       0.2631       0.1314              0.0007           0.0337       0.4978                   0.0007                   -0.0011               -0.0210
 improved_phasepp_composite_combined_fallback_redesign            calm_trend      295      0.0365  0.3921   0.0519   0.0967       0.7806       0.1675              0.0008           0.0356       0.3849                   0.0008                    0.0009                0.0071
 improved_phasepp_composite_combined_fallback_redesign neutral_healthy_proxy      293      0.1008  1.2719   0.2066   0.0876       0.6163       0.1771              0.0019           0.0992       1.2630                   0.0019                    0.0017                0.0089
 improved_phasepp_composite_combined_fallback_redesign         neutral_mixed      200      0.1275  1.7971   0.3853   0.0656       0.4537       0.1610              0.0024           0.1271       1.7996                   0.0024                    0.0004               -0.0026
 improved_phasepp_composite_combined_fallback_redesign    recovery_confirmed       44      0.0278  0.4068   0.1159   0.0628       0.5900       0.2941              0.0006           0.0261       0.3891                   0.0005                    0.0017                0.0177
 improved_phasepp_composite_combined_fallback_redesign      recovery_fragile       49      0.0717  1.3444   0.2049   0.0637       0.5719       0.2233              0.0014           0.0697       1.3305                   0.0013                    0.0020                0.0139
 improved_phasepp_composite_combined_fallback_redesign        stressed_panic      229      0.0330  0.4850   0.6057   0.0272       0.2631       0.1311              0.0007           0.0337       0.4978                   0.0007                   -0.0007               -0.0128
```

## Candidate Diagnostics
```
                                                  name                 state  avg_composite_internal_bil  composite_bil_reduction_vs_prod  avg_composite_hidden_bil_contrib  composite_hidden_bil_reduction_vs_prod  avg_composite_internal_spy  avg_composite_internal_gld  avg_composite_internal_tlt  avg_composite_internal_lqd  avg_composite_internal_hyg  avg_final_portfolio_bil  avg_final_portfolio_spy
improved_phasepp_composite_balanced_defensive_fallback            calm_trend                      0.0554                           0.0587                            0.0159                                  0.0184                      0.0452                      0.1160                      0.0753                      0.1101                      0.1080                   0.0500                   0.0968
improved_phasepp_composite_balanced_defensive_fallback neutral_healthy_proxy                      0.1413                           0.0878                            0.0373                                  0.0253                      0.0423                      0.1413                      0.1168                      0.1268                      0.0943                   0.1878                   0.0867
improved_phasepp_composite_balanced_defensive_fallback         neutral_mixed                      0.2709                           0.0000                            0.0473                                  0.0019                      0.0411                      0.1083                      0.1047                      0.1021                      0.0732                   0.3845                   0.0655
improved_phasepp_composite_balanced_defensive_fallback    recovery_confirmed                      0.0915                           0.0938                            0.0278                                  0.0340                      0.0142                      0.1925                      0.1673                      0.1372                      0.1007                   0.0916                   0.0600
improved_phasepp_composite_balanced_defensive_fallback      recovery_fragile                      0.1444                           0.0954                            0.0374                                  0.0274                      0.0128                      0.1609                      0.1289                      0.1492                      0.1360                   0.1911                   0.0632
improved_phasepp_composite_balanced_defensive_fallback        stressed_panic                      0.5380                           0.0000                            0.0842                                  0.0022                      0.0178                      0.0605                      0.0703                      0.0814                      0.0899                   0.6054                   0.0276
         improved_phasepp_composite_bond_gold_fallback            calm_trend                      0.0608                           0.0534                            0.0175                                  0.0169                      0.0452                      0.1221                      0.0844                      0.0984                      0.0992                   0.0516                   0.0968
         improved_phasepp_composite_bond_gold_fallback neutral_healthy_proxy                      0.1493                           0.0798                            0.0394                                  0.0232                      0.0423                      0.1504                      0.1303                      0.1092                      0.0812                   0.1898                   0.0868
         improved_phasepp_composite_bond_gold_fallback         neutral_mixed                      0.2709                           0.0000                            0.0476                                  0.0016                      0.0411                      0.1083                      0.1047                      0.1021                      0.0732                   0.3847                   0.0654
         improved_phasepp_composite_bond_gold_fallback    recovery_confirmed                      0.1000                           0.0852                            0.0303                                  0.0315                      0.0142                      0.2023                      0.1818                      0.1185                      0.0866                   0.0941                   0.0601
         improved_phasepp_composite_bond_gold_fallback      recovery_fragile                      0.1531                           0.0867                            0.0398                                  0.0250                      0.0128                      0.1709                      0.1436                      0.1301                      0.1217                   0.1928                   0.0633
         improved_phasepp_composite_bond_gold_fallback        stressed_panic                      0.5380                           0.0000                            0.0842                                  0.0022                      0.0178                      0.0605                      0.0703                      0.0814                      0.0899                   0.6053                   0.0274
 improved_phasepp_composite_combined_fallback_redesign            calm_trend                      0.0608                           0.0534                            0.0178                                  0.0166                      0.0452                      0.1221                      0.0844                      0.0984                      0.0992                   0.0519                   0.0967
 improved_phasepp_composite_combined_fallback_redesign neutral_healthy_proxy                      0.2062                           0.0229                            0.0562                                  0.0064                      0.0441                      0.1135                      0.0931                      0.1129                      0.0834                   0.2066                   0.0876
 improved_phasepp_composite_combined_fallback_redesign         neutral_mixed                      0.2709                           0.0000                            0.0484                                  0.0008                      0.0411                      0.1083                      0.1047                      0.1021                      0.0732                   0.3853                   0.0656
 improved_phasepp_composite_combined_fallback_redesign    recovery_confirmed                      0.1574                           0.0278                            0.0524                                  0.0094                      0.0146                      0.1647                      0.1439                      0.1229                      0.0898                   0.1159                   0.0628
 improved_phasepp_composite_combined_fallback_redesign      recovery_fragile                      0.1918                           0.0480                            0.0514                                  0.0134                      0.0163                      0.1327                      0.1078                      0.1388                      0.1280                   0.2049                   0.0637
 improved_phasepp_composite_combined_fallback_redesign        stressed_panic                      0.5380                           0.0000                            0.0846                                  0.0018                      0.0178                      0.0605                      0.0703                      0.0814                      0.0899                   0.6057                   0.0272
```

## Selection Table
```
                                                  name  ann_return_delta_pp_vs_prod  sharpe_delta_vs_prod  max_drawdown_delta_pp_vs_prod  cvar_delta_pp_vs_prod  turnover_ratio_vs_prod  avg_SPY_delta_pp_vs_prod  avg_composite_hidden_bil_reduction_vs_prod  avg_favorable_hidden_bil_reduction_vs_prod  passes_all_gates         fail_reasons
         improved_phasepp_composite_bond_gold_fallback                       0.0078               -0.0094                        -0.1714                -0.0402                  1.0193                    0.0430                                      0.0167                                      0.0242             False sharpe_delta -0.0094
improved_phasepp_composite_balanced_defensive_fallback                       0.0049               -0.0092                        -0.1614                -0.0382                  1.0196                    0.0456                                      0.0182                                      0.0263             False sharpe_delta -0.0092
 improved_phasepp_composite_combined_fallback_redesign                       0.0741                0.0031                        -0.0326                -0.0211                  1.0238                    0.0747                                      0.0081                                      0.0114             False sharpe_delta +0.0031
```

## Stressed-Panic Protection Check
- The redesigns only touch rows on the favorable-state `25%` BIL tier. The `65%` stressed tier is left untouched by construction.
- See `stressed_panic` rows in the candidate diagnostics for any spillover into final portfolio behavior.

## Recovery-Fragile Protection Check
- Recovery-fragile state performance is explicitly checked in the selection gate.
- See `recovery_fragile` rows in the candidate diagnostics and state summary.

## Best Candidate
- Best candidate: `improved_phasepp_composite_combined_fallback_redesign`
- Quick committee verdict: **KEEP AS SHADOW**
- Research committee report: `reports/research_committee/improved_phasepp_composite_combined_fallback_redesign_audit.md`
- Layer 5/6 status: Ran quick Layer 5/6 audits.
- Quick realism verdict: survived doubled-cost and rebalance-delay stress with a small but persistent annual-return edge.
- Quick allocator-benchmark verdict: beats production on annual return and Sharpe, but does not clear the "complexity clearly earns its keep" bar versus the best simple baseline.

## Final Decision
**KEEP AS SHADOW**

- Production pin remains unchanged.
- Shadow pin remains unchanged.
- This composite fallback redesign path should continue.
- Recommended next phase if this fails: a deeper `composite_regime_conditioned` component-level fallback redesign that replaces the coarse favorable-state `25%` cash tier with subcomponent-specific fallbacks rather than another small sleeve-level cash relief patch.
