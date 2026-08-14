# Phase 4 — Sector Breadth / Sector ETF Rotation

**Date:** 2026-05-07
**Type:** Strategy research. No production pins changed. No auto-promotion.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Official shadow pin:** `improved_phase2b_combo_abc`
**Base:** `improved_phaseggg_confirmed_only_robust_offense`

## Commands Executed

```
pwd
git status --short
git branch --show-current
git worktree list
find .. -name CLAUDE.md -maxdepth 3
sed -n '1,220p' CLAUDE.md
for path in docs/research/2026-05-07_phase_1_return_unlock_audit_report.md docs/research/2026-05-07_phase_2_aggressive_etf_variant_report.md docs/research/2026-05-07_phase_3_breadth_confirmed_us_offense_report.md data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phaseggg_confirmed_only_robust_offense.csv data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2_aggressive_neutral_cash_unlock.csv data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_high_breadth_calm_us_offense.csv scripts/build_improvement_artifacts.py data/research/phase_1_return_unlock_audit data/research/phase_2_aggressive_etf_variant data/research/phase_3_breadth_confirmed_us_offense; do test -e "$path"; done
sed -n '1,240p' docs/research/2026-05-07_phase_1_return_unlock_audit_report.md
sed -n '1,260p' docs/research/2026-05-07_phase_2_aggressive_etf_variant_report.md
sed -n '1,280p' docs/research/2026-05-07_phase_3_breadth_confirmed_us_offense_report.md
find data/research/phase_1_return_unlock_audit -maxdepth 2 -type f | sort | head -120
find data/research/phase_2_aggressive_etf_variant -maxdepth 2 -type f | sort | head -160
find data/research/phase_3_breadth_confirmed_us_offense -maxdepth 2 -type f | sort | head -180
find data/01_data_hub data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine data/05_layer3_portfolio_construction -maxdepth 2 -type f | sort | head
rg -n "phase3|phase2_aggressive|phaseggg|VERSION|VersionSpec|state_tilt|offense|DEFAULT_COST|BUILD_VERSION_NAMES" scripts/build_improvement_artifacts.py
head -5 data/01_data_hub/weekly_returns.csv
head -5 data/01_data_hub/weekly_prices.csv
head -5 data/04_layer2b_risk_regime_engine/market_state_history.csv
python3 -m py_compile scripts/build_improvement_artifacts.py
python3 -m py_compile scripts/phase_4_sector_breadth_rotation.py scripts/build_improvement_artifacts.py
python3 scripts/phase_4_sector_breadth_rotation.py
BUILD_VERSION_NAMES='improved_phase4_sector_small_overlay,improved_phase4_sector_20pct_offense,improved_phase4_sector_25pct_offense,improved_phase4_balanced_sector_breadth,improved_phase4_stretch_sector_momentum,improved_phase4_sector_us_hybrid' python3 scripts/build_improvement_artifacts.py
python3 scripts/research_committee_report.py improved_phase4_sector_20pct_offense --quick
python3 scripts/backtest_realism_audit.py improved_phase4_sector_20pct_offense --quick
python3 scripts/allocator_benchmark_audit.py improved_phase4_sector_20pct_offense --quick
git status --short
```

## Files Created / Modified

**Script created:** `scripts/phase_4_sector_breadth_rotation.py`

**Build script modified:** `scripts/build_improvement_artifacts.py` added Phase 4 sector sleeve registration, state tilts, and six filtered version specs.

**Output directory:** `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_4_sector_breadth_rotation`

**Report created:** `docs/research/2026-05-07_phase_4_sector_breadth_rotation_report.md`

## Phase 1-3 Bottleneck Summary

Phase 1 found the return ceiling was mandate-driven: high non-stressed BIL/cash and limited calm-trend upside capture, while stressed_panic protection worked and should not be weakened.

Phase 2 reduced some cash and shifted sleeves, but the best aggressive shadow reached only about 7.39% full-period return because internal sleeve BIL and diversified offense composition remained the real bottlenecks.

Phase 3 improved the small offense component by using pure US equity in high-breadth calm states. It improved Sharpe, especially recent holdouts, but the modified component was too small to lift full-period return toward 9-10%.

## Sector Universe Inventory

Eligible sector ETFs found in existing data: `XLK, XLF, XLV, XLY, XLP, XLI, XLE, XLU, XLB, VNQ`.

```
ticker           category start_date   end_date  ann_return  ann_vol   sharpe  max_drawdown  correlation_to_SPY  eligible_for_phase4_sector_sleeve
   XLK       broad_sector 2005-01-07 2026-04-10    0.145738 0.202418 0.719983     -0.507040            0.906257                               True
   XLF       broad_sector 2005-01-07 2026-04-10    0.055771 0.268270 0.207890     -0.826865            0.845020                               True
   XLV       broad_sector 2005-01-07 2026-04-10    0.096228 0.161000 0.597688     -0.379124            0.786497                               True
   XLY       broad_sector 2005-01-07 2026-04-10    0.105856 0.213779 0.495165     -0.584314            0.912730                               True
   XLP       broad_sector 2005-01-07 2026-04-10    0.089262 0.132264 0.674879     -0.313426            0.750050                               True
   XLI       broad_sector 2005-01-07 2026-04-10    0.105647 0.206064 0.512690     -0.616256            0.918437                               True
   XLE       broad_sector 2005-01-07 2026-04-10    0.087212 0.279471 0.312060     -0.688993            0.679382                               True
   XLU       broad_sector 2005-01-07 2026-04-10    0.097076 0.179163 0.541830     -0.451984            0.626711                               True
   XLB       broad_sector 2005-01-07 2026-04-10    0.085484 0.223394 0.382660     -0.590069            0.849978                               True
   VNQ broad_sector_proxy 2005-01-07 2026-04-10    0.070869 0.253007 0.280106     -0.725401            0.745384                               True
```

## Sector Features And Signals

All features are computed through week `t` and applied to week `t+1` returns. No centered windows, future returns, or future states are used.

```
                     signal  active_weeks  active_frequency                                                active_states  calm_trend_coverage  neutral_mixed_coverage  recovery_confirmed_coverage  stressed_panic_coverage
   sector_breadth_confirmed           649          0.584685                  calm_trend|neutral_mixed|recovery_confirmed             0.942373                0.669371                     0.931818                      0.0
sector_leadership_confirmed           672          0.605405                  calm_trend|neutral_mixed|recovery_confirmed             0.952542                0.705882                     0.977273                      0.0
   high_breadth_sector_bull           599          0.539640 calm_trend|neutral_mixed|recovery_confirmed|recovery_fragile             0.854237                0.578093                     0.863636                      0.0
   defensive_sector_warning            13          0.011712                                                neutral_mixed             0.000000                0.026369                     0.000000                      0.0
```

## Sector Sleeve Standalone Validation

```
                           sleeve  ann_return  ann_vol   sharpe  max_drawdown   calmar    cvar_5  avg_turnover
                EqualWeightSector    0.102424 0.175251 0.584442     -0.542500 0.188800 -0.058704      0.000000
               Top5SectorMomentum    0.091795 0.164506 0.558003     -0.484694 0.189387 -0.055308      0.110911
               Top3SectorMomentum    0.082130 0.168319 0.487940     -0.477832 0.171880 -0.057687      0.147580
SectorMomentumWithDefensiveFilter    0.071591 0.128381 0.557644     -0.216493 0.330684 -0.044056      0.162744
                 RiskAdjustedTop3    0.058380 0.139949 0.417151     -0.386058 0.151220 -0.048766      0.183242
          SectorStretchAggressive    0.044855 0.090329 0.496579     -0.149263 0.300513 -0.032360      0.165243
    SectorMomentumWithBreadthGate    0.044630 0.100970 0.442009     -0.222845 0.200273 -0.035732      0.151307
         SectorBalancedAggressive    0.044280 0.098143 0.451180     -0.217048 0.204010 -0.034698      0.162661
```

Standalone validation positive: **True**. The gate is based on whether any sector sleeve improves a useful risk-adjusted dimension versus SPY/equal-sector, especially Calmar/drawdown after costs.

## Candidate Logic

```
                              candidate                                      sector_sleeve                                             budget                                                                                                     logic
   improved_phase4_sector_small_overlay                                 Top5SectorMomentum      12% target in sector_breadth_confirmed states                  small overlay funded from cash/defense/old diversified offense; stressed_panic unchanged
   improved_phase4_sector_20pct_offense                                 Top3SectorMomentum      20% target in sector_breadth_confirmed states first true return-unlock candidate; neutral boost plus dedicated sector offense; stressed_panic unchanged
   improved_phase4_sector_25pct_offense                                 Top3SectorMomentum      25% target in sector_breadth_confirmed states                                     more aggressive sector budget; reject on Sharpe/drawdown/CVaR failure
improved_phase4_balanced_sector_breadth                           SectorBalancedAggressive      20% target in sector_breadth_confirmed states                                                    top5 inverse-vol sector sleeve for Sharpe preservation
improved_phase4_stretch_sector_momentum                            SectorStretchAggressive 25% target only in high_breadth_sector_bull states                               concentrated stretch candidate; reject if hidden beta or drawdown dominates
       improved_phase4_sector_us_hybrid SectorBalancedAggressive + Phase 3 calm US offense        16% target when sector_leadership_confirmed                                            hybrid of Phase 3 US pure offense and sector leadership sleeve
```

## Full-Period Metrics

```
                              portfolio  ann_return  ann_vol   sharpe  max_drawdown    cvar_5  avg_BIL  avg_sector_sleeve_exposure  beta_spy  corr_spy
                                    QQQ    0.146918 0.198664 0.739527     -0.514472 -0.061888      NaN                         NaN  1.033657  0.914365
                                    SPY    0.105431 0.175737 0.599935     -0.546130 -0.058004      NaN                         NaN  1.000000  1.000000
                EqualWeightSectorSleeve    0.102424 0.175251 0.584442     -0.542500 -0.058704      NaN                         NaN -0.076009 -0.076185
                            bench_60_40    0.080872 0.103078 0.784570     -0.313836 -0.032731      NaN                         NaN -0.046977 -0.080056
   improved_phase4_sector_20pct_offense    0.076448 0.082190 0.930141     -0.143286 -0.026837 0.238877                    0.128902 -0.035138 -0.075099
   improved_phase4_sector_25pct_offense    0.076362 0.083469 0.914853     -0.148681 -0.027231 0.238968                    0.155854 -0.035298 -0.074283
                            phase2_best    0.073892 0.078627 0.939780     -0.125043 -0.026048 0.246166                    0.000000 -0.032065 -0.071636
   improved_phase4_sector_small_overlay    0.073598 0.077406 0.950800     -0.130574 -0.025585 0.262088                    0.082518 -0.032452 -0.073645
                            phase3_best    0.072679 0.075242 0.965945     -0.119015 -0.024830 0.279285                    0.000000 -0.030418 -0.071013
                                   ggg1    0.071381 0.076248 0.936168     -0.117739 -0.025377 0.266580                    0.000000 -0.030808 -0.070976
                               prod_pin    0.068923 0.077931 0.884416     -0.139754 -0.026181 0.283918                    0.000000 -0.024908 -0.056143
                        official_shadow    0.068584 0.077616 0.883625     -0.136741 -0.026085 0.285552                    0.000000 -0.024890 -0.056330
improved_phase4_balanced_sector_breadth    0.068024 0.077511 0.877598     -0.136302 -0.026398 0.291666                    0.210251 -0.028941 -0.065587
       improved_phase4_sector_us_hybrid    0.067040 0.073916 0.906973     -0.122538 -0.024976 0.323281                    0.194073 -0.027213 -0.064671
improved_phase4_stretch_sector_momentum    0.066232 0.074871 0.884613     -0.136453 -0.025760 0.309784                    0.241944 -0.028330 -0.066467
```

## Holdout And Recent Metrics

```
                              portfolio       window  ann_return    sharpe  max_drawdown  avg_BIL  avg_sector_sleeve_exposure
   improved_phase4_sector_25pct_offense    bear_2022   -0.007112 -0.113177     -0.065493 0.526219                    0.066140
   improved_phase4_sector_20pct_offense    bear_2022   -0.008233 -0.131363     -0.066061 0.526652                    0.059215
                            phase2_best    bear_2022   -0.011410 -0.177155     -0.069271 0.536657                    0.000000
                                   ggg1    bear_2022   -0.012933 -0.211239     -0.068418 0.550054                    0.000000
   improved_phase4_sector_small_overlay    bear_2022   -0.013621 -0.225214     -0.065900 0.541292                    0.042815
                            phase3_best    bear_2022   -0.014259 -0.236065     -0.066584 0.552294                    0.000000
       improved_phase4_sector_us_hybrid    bear_2022   -0.016013 -0.339356     -0.045670 0.665020                    0.156539
improved_phase4_balanced_sector_breadth    bear_2022   -0.017211 -0.360595     -0.045239 0.659713                    0.168872
improved_phase4_stretch_sector_momentum    bear_2022   -0.018079 -0.398292     -0.043215 0.680695                    0.184495
                                    SPY    bear_2022   -0.181754 -0.787666     -0.224795      NaN                         NaN
                                    QQQ    bear_2022   -0.325770 -1.138728     -0.310455      NaN                         NaN
                                    QQQ holdout_2020    0.188260  0.834023     -0.350556      NaN                         NaN
                                    SPY holdout_2020    0.141386  0.732351     -0.318290      NaN                         NaN
                            phase3_best holdout_2020    0.099358  1.124360     -0.119015 0.249414                    0.000000
                            phase2_best holdout_2020    0.097023  1.060738     -0.125043 0.219200                    0.000000
                                   ggg1 holdout_2020    0.095497  1.082205     -0.117739 0.235807                    0.000000
   improved_phase4_sector_small_overlay holdout_2020    0.094411  1.044786     -0.130574 0.233547                    0.086782
   improved_phase4_sector_20pct_offense holdout_2020    0.093131  0.964462     -0.143286 0.209708                    0.138619
   improved_phase4_sector_25pct_offense holdout_2020    0.091370  0.929911     -0.148681 0.208830                    0.167882
       improved_phase4_sector_us_hybrid holdout_2020    0.085226  0.967038     -0.122538 0.287040                    0.239568
improved_phase4_balanced_sector_breadth holdout_2020    0.081402  0.881036     -0.136302 0.252719                    0.253117
improved_phase4_stretch_sector_momentum holdout_2020    0.078304  0.890158     -0.136453 0.280403                    0.288714
                                    QQQ holdout_2021    0.143416  0.687667     -0.350556      NaN                         NaN
                                    SPY holdout_2021    0.137128  0.855797     -0.239272      NaN                         NaN
                            phase3_best holdout_2021    0.105679  1.403428     -0.074152 0.242049                    0.000000
                            phase2_best holdout_2021    0.105012  1.340756     -0.076287 0.207294                    0.000000
                                   ggg1 holdout_2021    0.102228  1.348356     -0.072541 0.226471                    0.000000
   improved_phase4_sector_small_overlay holdout_2021    0.102093  1.334569     -0.070085 0.222725                    0.090220
   improved_phase4_sector_20pct_offense holdout_2021    0.101835  1.244575     -0.073421 0.194314                    0.144675
   improved_phase4_sector_25pct_offense holdout_2021    0.100831  1.211702     -0.073234 0.192901                    0.175871
```

## State-By-State Impact

```
                              portfolio              state  ann_return   sharpe  max_drawdown  avg_BIL  avg_sector_sleeve_exposure  avg_offense_exposure  avg_defense_exposure
                                   ggg1         calm_trend    0.040851 0.513625     -0.139322 0.110330                    0.000000              0.526720              0.436956
improved_phase4_balanced_sector_breadth         calm_trend    0.041398 0.478158     -0.132261 0.080259                    0.274143              0.678862              0.293613
   improved_phase4_sector_20pct_offense         calm_trend    0.046796 0.548294     -0.136643 0.087548                    0.185859              0.622390              0.338907
   improved_phase4_sector_25pct_offense         calm_trend    0.047053 0.535925     -0.137026 0.086088                    0.230349              0.647027              0.309106
   improved_phase4_sector_small_overlay         calm_trend    0.043264 0.534966     -0.134387 0.101459                    0.111967              0.577675              0.381303
       improved_phase4_sector_us_hybrid         calm_trend    0.041914 0.514924     -0.127093 0.129009                    0.261078              0.668853              0.297008
improved_phase4_stretch_sector_momentum         calm_trend    0.029706 0.365512     -0.152856 0.103897                    0.309099              0.690345              0.282197
                            phase2_best         calm_trend    0.041268 0.517105     -0.139793 0.105189                    0.000000              0.530285              0.439437
                            phase3_best         calm_trend    0.043578 0.587964     -0.122006 0.158727                    0.000000              0.546169              0.418279
                                   ggg1      neutral_mixed    0.112112 1.461561     -0.091217 0.260356                    0.000000              0.459854              0.311500
improved_phase4_balanced_sector_breadth      neutral_mixed    0.104783 1.316588     -0.104890 0.267618                    0.201904              0.573272              0.240276
   improved_phase4_sector_20pct_offense      neutral_mixed    0.115123 1.393738     -0.106797 0.223783                    0.132908              0.537679              0.265745
   improved_phase4_sector_25pct_offense      neutral_mixed    0.114085 1.364929     -0.109522 0.224775                    0.161112              0.551468              0.248845
   improved_phase4_sector_small_overlay      neutral_mixed    0.112105 1.455170     -0.095411 0.258448                    0.082796              0.489075              0.280784
       improved_phase4_sector_us_hybrid      neutral_mixed    0.101798 1.332653     -0.098429 0.302242                    0.179882              0.540637              0.233546
improved_phase4_stretch_sector_momentum      neutral_mixed    0.103861 1.348132     -0.104696 0.292305                    0.234976              0.589965              0.228360
                            phase2_best      neutral_mixed    0.117435 1.468792     -0.097213 0.226784                    0.000000              0.481916              0.326545
                            phase3_best      neutral_mixed    0.112714 1.461507     -0.093329 0.259897                    0.000000              0.468792              0.303369
                                   ggg1 recovery_confirmed    0.025705 0.344267     -0.053798 0.113607                    0.000000              0.576634              0.339096
improved_phase4_balanced_sector_breadth recovery_confirmed    0.050664 0.590993     -0.057580 0.057408                    0.249237              0.725468              0.259417
   improved_phase4_sector_20pct_offense recovery_confirmed    0.039650 0.489707     -0.056432 0.081820                    0.156458              0.670806              0.269594
   improved_phase4_sector_25pct_offense recovery_confirmed    0.042247 0.517822     -0.056350 0.081615                    0.189830              0.683335              0.254552
   improved_phase4_sector_small_overlay recovery_confirmed    0.034994 0.468408     -0.053090 0.109585                    0.094177              0.613246              0.297768
       improved_phase4_sector_us_hybrid recovery_confirmed    0.049119 0.594933     -0.054603 0.105422                    0.225793              0.683361              0.250104
improved_phase4_stretch_sector_momentum recovery_confirmed    0.073296 0.868791     -0.052643 0.078741                    0.282400              0.744805              0.242706
                            phase2_best recovery_confirmed    0.026741 0.346583     -0.053930 0.083963                    0.000000              0.599446              0.352769
                            phase3_best recovery_confirmed    0.024606 0.322523     -0.054834 0.106780                    0.000000              0.590763              0.331010
                                   ggg1   recovery_fragile    0.066671 1.142121     -0.032194 0.169929                    0.000000              0.505352              0.364447
improved_phase4_balanced_sector_breadth   recovery_fragile    0.050009 1.059160     -0.030114 0.347914                    0.221435              0.627463              0.273300
   improved_phase4_sector_20pct_offense   recovery_fragile    0.080334 1.317319     -0.030419 0.142555                    0.084114              0.560502              0.332557
   improved_phase4_sector_25pct_offense   recovery_fragile    0.083160 1.361349     -0.030334 0.142840                    0.092714              0.565657              0.327228
   improved_phase4_sector_small_overlay   recovery_fragile    0.077464 1.335814     -0.028919 0.164713                    0.070351              0.533012              0.336148
       improved_phase4_sector_us_hybrid   recovery_fragile    0.049361 1.059110     -0.029293 0.358839                    0.205870              0.607787              0.266965
improved_phase4_stretch_sector_momentum   recovery_fragile    0.078646 1.488107     -0.030755 0.255940                    0.262609              0.654019              0.250820
                            phase2_best   recovery_fragile    0.069606 1.156644     -0.032387 0.147562                    0.000000              0.520357              0.373919
                            phase3_best   recovery_fragile    0.067719 1.174409     -0.031296 0.175119                    0.000000              0.514618              0.356519
```

## Risk / Realism Checks

```
                              portfolio  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  holdout_2020_return  holdout_2020_sharpe  avg_BIL  avg_sector_sleeve_exposure  maxdd_ok  sharpe_ok  bear_ok  cvar_bad  better_than_60_40_sharpe  disguised_spy_qqq
   improved_phase4_sector_small_overlay         0.073598     0.950800          -0.130574    -0.025585             0.094411             1.044786 0.262088                    0.082518      True       True     True     False                      True              False
   improved_phase4_sector_20pct_offense         0.076448     0.930141          -0.143286    -0.026837             0.093131             0.964462 0.238877                    0.128902      True       True     True     False                      True              False
   improved_phase4_sector_25pct_offense         0.076362     0.914853          -0.148681    -0.027231             0.091370             0.929911 0.238968                    0.155854      True       True     True     False                      True              False
improved_phase4_balanced_sector_breadth         0.068024     0.877598          -0.136302    -0.026398             0.081402             0.881036 0.291666                    0.210251      True      False     True     False                      True              False
improved_phase4_stretch_sector_momentum         0.066232     0.884613          -0.136453    -0.025760             0.078304             0.890158 0.309784                    0.241944      True      False     True     False                      True              False
       improved_phase4_sector_us_hybrid         0.067040     0.906973          -0.122538    -0.024976             0.085226             0.967038 0.323281                    0.194073      True       True     True     False                      True              False
```

## Hidden Beta / Cash Checks

```
                              portfolio  beta_spy  corr_spy  beta_qqq  corr_qqq  ann_improvement_vs_ggg1  beta_attribution_estimate  pct_improvement_from_beta hidden_beta_risk  avg_BIL  bil_reduction_vs_ggg1
   improved_phase4_sector_small_overlay -0.032452 -0.073645 -0.024634 -0.063196                 0.002217                  -0.000173                   0.078187              LOW 0.262088              -0.004492
   improved_phase4_sector_20pct_offense -0.035138 -0.075099 -0.027154 -0.065605                 0.005067                  -0.000456                   0.090091              LOW 0.238877              -0.027703
   improved_phase4_sector_25pct_offense -0.035298 -0.074283 -0.027450 -0.065304                 0.004981                  -0.000473                   0.095025              LOW 0.238968              -0.027612
improved_phase4_balanced_sector_breadth -0.028941 -0.065587 -0.022799 -0.058409                -0.003357                   0.000197                   0.058640              LOW 0.291666               0.025086
improved_phase4_stretch_sector_momentum -0.028330 -0.066467 -0.023307 -0.061816                -0.005149                   0.000261                   0.050738              LOW 0.309784               0.043204
       improved_phase4_sector_us_hybrid -0.027213 -0.064671 -0.021489 -0.057729                -0.004341                   0.000379                   0.087320              LOW 0.323281               0.056700
```

## 2022 Bear Protection

```
                              portfolio  bear_2022_return  ggg1_bear_2022_return  delta_vs_ggg1  bear_ok
   improved_phase4_sector_small_overlay         -0.013621              -0.012933      -0.000688     True
   improved_phase4_sector_20pct_offense         -0.008233              -0.012933       0.004700     True
   improved_phase4_sector_25pct_offense         -0.007112              -0.012933       0.005821     True
improved_phase4_balanced_sector_breadth         -0.017211              -0.012933      -0.004278     True
improved_phase4_stretch_sector_momentum         -0.018079              -0.012933      -0.005146     True
       improved_phase4_sector_us_hybrid         -0.016013              -0.012933      -0.003080     True
```

## Sector Concentration / Turnover

```
                              portfolio  avg_total_sector_etf_weight  avg_max_single_sector_etf_weight  max_single_sector_etf_weight  avg_top3_sector_etf_weight  active_sector_weeks
   improved_phase4_sector_small_overlay                     0.150486                          0.078983                          0.35                    0.111990                 1033
   improved_phase4_sector_20pct_offense                     0.194363                          0.092472                          0.35                    0.178406                 1033
   improved_phase4_sector_25pct_offense                     0.218240                          0.096388                          0.35                    0.200291                 1033
improved_phase4_balanced_sector_breadth                     0.203836                          0.084377                          0.35                    0.148822                  821
improved_phase4_stretch_sector_momentum                     0.209993                          0.096278                          0.35                    0.194956                  803
       improved_phase4_sector_us_hybrid                     0.187739                          0.078396                          0.35                    0.137462                  820
```

## Sector-Active Windows

```
                              portfolio                   signal  active_weeks  signal_active_ann_return  signal_inactive_ann_return  signal_active_delta_vs_ggg1
   improved_phase4_sector_small_overlay sector_breadth_confirmed           649                  0.078876                    0.066211                     0.000103
   improved_phase4_sector_20pct_offense sector_breadth_confirmed           649                  0.079980                    0.071495                     0.001208
   improved_phase4_sector_25pct_offense sector_breadth_confirmed           649                  0.078838                    0.072886                     0.000065
improved_phase4_balanced_sector_breadth sector_breadth_confirmed           649                  0.080863                    0.050207                     0.002090
improved_phase4_stretch_sector_momentum sector_breadth_confirmed           649                  0.077192                    0.050991                    -0.001580
       improved_phase4_sector_us_hybrid sector_breadth_confirmed           649                  0.079299                    0.050018                     0.000526
```

## Selection Table

```
                              portfolio            classification                                                                            reason  full_ann_return  full_sharpe  full_max_drawdown  holdout_2020_return  holdout_2020_sharpe  bear_2022_return  beats_ggg1  beats_phase2_best  beats_phase3_best  sector_active_good  sector_validation_positive
   improved_phase4_sector_small_overlay KEEP_AS_AGGRESSIVE_SHADOW credible incremental sector sleeve benefit but not production-challenger strength         0.073598     0.950800          -0.130574             0.094411             1.044786         -0.013621        True               True               True                True                        True
   improved_phase4_sector_20pct_offense KEEP_AS_AGGRESSIVE_SHADOW credible incremental sector sleeve benefit but not production-challenger strength         0.076448     0.930141          -0.143286             0.093131             0.964462         -0.008233        True               True               True                True                        True
   improved_phase4_sector_25pct_offense KEEP_AS_AGGRESSIVE_SHADOW credible incremental sector sleeve benefit but not production-challenger strength         0.076362     0.914853          -0.148681             0.091370             0.929911         -0.007112        True               True               True                True                        True
improved_phase4_balanced_sector_breadth                    REJECT                                                failed hard risk/realism guardrail         0.068024     0.877598          -0.136302             0.081402             0.881036         -0.017211       False              False              False                True                        True
improved_phase4_stretch_sector_momentum                    REJECT                                                failed hard risk/realism guardrail         0.066232     0.884613          -0.136453             0.078304             0.890158         -0.018079       False              False              False               False                        True
       improved_phase4_sector_us_hybrid     KEEP_AS_RESEARCH_ONLY                            partial sector evidence but weak aggregate improvement         0.067040     0.906973          -0.122538             0.085226             0.967038         -0.016013       False              False              False                True                        True
```

## Audit Results

```
                    audit                            candidate status                                        log
research_committee_report improved_phase4_sector_20pct_offense   PASS phase4_research_committee_report_quick.log
   backtest_realism_audit improved_phase4_sector_20pct_offense   PASS    phase4_backtest_realism_audit_quick.log
allocator_benchmark_audit improved_phase4_sector_20pct_offense   PASS phase4_allocator_benchmark_audit_quick.log
```

## Final Recommendation

**Recommendation:** `KEEP_PHASE4_AS_AGGRESSIVE_SHADOW`

**Best candidate:** `improved_phase4_sector_20pct_offense`

**Rationale:** improved_phase4_sector_20pct_offense is a credible higher-return/risk tradeoff but not strong enough for production challenge.

## Next Phase Prompt Outline

```
Phase 4B should refine sector rotation only if it can fix the observed weaknesses without a grid search:
1. keep the same existing ETF universe and causal lag rule;
2. test whether sector sleeve timing should use calmer top-5 balanced exposure rather than top-3 concentration;
3. isolate whether active sector-signal weeks beat GGG1 after costs;
4. keep stressed_panic unchanged;
5. reject any candidate that is mostly SPY/QQQ beta or worse than Phase 2/Phase 3 shadows.
```

## Resume / Project Story Summary

Phase 4 tested whether a larger dedicated sector ETF sleeve could move the strategy toward 9-10% annual return without abandoning the defensive identity. The sector universe was present and clean, features/signals were causal, standalone sleeves were validated before portfolio candidates, and Layer 3 candidates were built only through the filtered production pipeline. The final decision above should guide the next research step; production, shadow, and GGG1 pins remain unchanged.
