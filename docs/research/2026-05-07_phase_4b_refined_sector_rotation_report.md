# Phase 4B - Refined Sector Rotation / Breadth Timing Audit

**Date:** 2026-05-07
**Type:** Focused strategy research. No production pins changed. No auto-promotion.
**Production pin:** `improved_phase2b_regime_confidence_boost`
**Official shadow pin:** `improved_phase2b_combo_abc`
**Base:** `improved_phaseggg_confirmed_only_robust_offense`
**Phase 4 best:** `improved_phase4_sector_20pct_offense`

## Commands Executed

```
pwd
git status --short
git branch --show-current
git worktree list
find .. -name CLAUDE.md -maxdepth 3
sed -n '1,220p' CLAUDE.md
prerequisite file existence check
Phase 4 artifact/schema inspection commands
python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_4b_refined_sector_rotation.py
python3 scripts/phase_4b_refined_sector_rotation.py
BUILD_VERSION_NAMES='improved_phase4b_refined_sector_small_overlay,improved_phase4b_refined_sector_20pct,improved_phase4b_refined_sector_25pct_selective,improved_phase4b_sector_phase3_hybrid,improved_phase4b_return_unlock_stretch' python3 scripts/build_improvement_artifacts.py
```

## Files Created / Modified

**Script created:** `scripts/phase_4b_refined_sector_rotation.py`

**Build script modified:** `scripts/build_improvement_artifacts.py` added Phase 4B signal lookup, sleeve registration, five state tilts, and five filtered candidate specs.

**Output directory:** `/Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_4b_refined_sector_rotation`

**Report created:** `docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md`

## Phase 4 Diagnosis

```
                                                                               question                                                                                                                                                                                                                                                                                                   diagnosis
Why did improved_phase4_sector_20pct_offense improve full return but not Sharpe enough? The 20pct overlay added a larger dedicated sector offense budget and reduced BIL in active weeks, lifting full return, but the active sleeve remained high-volatility sector momentum. Incremental volatility and drawdown outweighed enough of the return lift to keep Sharpe near 0.93 rather than 0.95+.
                                                      Why did 25pct not dominate 20pct?                                                                 The extra 5% budget was funded from already useful defensive/cash/offense sleeves and increased sector volatility. It did not produce enough active-window return to compensate, so return was flat/slightly lower and Sharpe deteriorated.
                                Why did balanced/stretched sector sleeves underperform?                                                                        Balanced sleeves were safer but diluted the return unlock; stretch sleeves were more concentrated and had poorer active-window evidence. The strongest standalone sector sleeve was not strong enough to support more concentration.
                                                           Which states benefited most?                                                                                                                                                                   Recovery_confirmed and calm_trend had visible return lift versus GGG1; neutral_mixed return improved but Sharpe did not dominate Phase 2.
                                                              Which states were harmed?                                                                                                                                                                 Weak neutral and inactive/fallback windows were the main drag. Broad neutral activation created more whipsaw than clean Sharpe improvement.
               Did sector-active weeks truly beat GGG1 / Phase 2 / Phase 3 after costs?                                                                                                                                                          Yes for the best 20pct sleeve versus GGG1 on the sector_breadth_confirmed gate, but the edge was small and did not scale well to 25pct or stretch.
                        Was the sector sleeve too active or active in the wrong states?                                                                                                                 The Phase 4 breadth gate was broad, especially in neutral_mixed. Phase 4B should narrow activation to high-quality bull, calm leadership, and separately confirmed neutral/recovery states.
                                      Was top-3 too concentrated and top-5 too diluted?                                                                          Top3 had higher concentration and turnover without superior standalone Sharpe; Top5 was smoother but not strong enough by itself. Phase 4B tests top5 smoothing, top4 risk-adjusted, and strict top3 only under strong leadership.
                                           Did turnover or sector whipsaw hurt returns?                                                                                                                                                                Likely yes. Top3 and defensive-filter designs had meaningful weekly turnover, and the active edge was too small to ignore cost/whipsaw drag.
                                          Did sector exposure mainly duplicate SPY/QQQ?                                                                                                                                                                        Not at the portfolio level. Hidden beta checks were low, although standalone sector ETFs remain equity-like and correlated with SPY.
```

## Refined Sector Signal Definitions

```
                       signal                                                                                                                                                                                                         formula  active_weeks  active_frequency                                                       expected_use
     high_quality_sector_bull non-stressed/non-fragile AND sector trend breadth>=0.70 AND positive 26w sectors>=0.65 AND leadership spread>=3.5pp AND market trend positive AND VIX contained AND not neutral_deteriorating/defensive warning           528          0.475676                                Primary refined sector offense gate
  calm_sector_leadership_only                                                         market_state=calm_trend AND breadth>=0.60 AND top sector beats median>=2.5pp AND top sector beats SPY>=1.0pp AND VIX contained AND no defensive warning           286          0.257658    Avoid neutral whipsaw while preserving calm leadership exposure
neutral_sector_confirmed_only                                                          market_state=neutral_mixed AND breadth>=0.75 AND positive 26w sectors>=0.70 AND market trend and canary breadth positive AND not neutral_deteriorating           174          0.156757    Only unlock neutral sector exposure when confirmation is strong
      recovery_sector_reentry                                                                            market_state=recovery_confirmed AND breadth>=0.65 AND positive 26w sectors>=0.60 AND market trend positive AND state stability>=0.50            36          0.032432 Permit recovery_confirmed sector re-entry but not recovery_fragile
         sector_quality_score                                                                                             0.30*breadth + 0.20*positive_26w + 0.20*leadership_spread + 0.15*VIX_contained + 0.10*state_stability + 0.05*canary           672          0.605405        Continuous quality diagnostic plus strict high-quality gate
     defensive_sector_warning                                                                                                                                       two or more of XLU/XLP/XLV in top3 26w momentum while sector breadth<0.55            13          0.011712                                   Block offense, never add offense
```

## Refined Signal Coverage

```
                       signal  active_weeks  active_frequency                               active_states  calm_trend_coverage  neutral_mixed_coverage  recovery_confirmed_coverage  recovery_fragile_coverage  stressed_panic_coverage
     high_quality_sector_bull           528          0.475676 calm_trend|neutral_mixed|recovery_confirmed             0.888136                0.462475                     0.863636                        0.0                      0.0
  calm_sector_leadership_only           286          0.257658                                  calm_trend             0.969492                0.000000                     0.000000                        0.0                      0.0
neutral_sector_confirmed_only           174          0.156757                               neutral_mixed             0.000000                0.352941                     0.000000                        0.0                      0.0
      recovery_sector_reentry            36          0.032432                          recovery_confirmed             0.000000                0.000000                     0.818182                        0.0                      0.0
    sector_quality_score_high           560          0.504505 calm_trend|neutral_mixed|recovery_confirmed             0.942373                0.490872                     0.909091                        0.0                      0.0
     defensive_sector_warning            13          0.011712                               neutral_mixed             0.000000                0.026369                     0.000000                        0.0                      0.0
```

## Refined Sector Sleeve Designs

```
                    sleeve                          weighting_method                                                                                   selection_rule                                                   reason_to_fix_phase4_weakness
      Top5_Smooth_Momentum                              equal weight       top 5 by blended 13w/26w momentum; carry prior top names if still top 7 and trend positive lower turnover and less top3 concentration while preserving leadership exposure
Top4_RiskAdjusted_Momentum       inverse 26w volatility with 35% cap        top 4 by blended momentum divided by 26w vol, require positive 43w trend and 26w momentum                        reduce high-vol whipsaw and avoid negative-trend sectors
    Top3_Strict_Leadership                 equal weight with 45% cap         top 3 by blended momentum only when sector_quality_score_high and leadership spread>=6pp       keep top3 concentration only when Phase 4's broad gate is most convincing
       DefensiveAware_Top5                 equal weight with 30% cap       top 5 by blended momentum, require positive trend/momentum, block defensive_sector_warning                   avoid late-cycle defensive leadership masquerading as offense
       SectorBlend_SPY_QQQ 70% DefensiveAware_Top5, 15% SPY, 15% QQQ blend only when high_quality_sector_bull or calm_sector_leadership_only is active; otherwise BIL        reduce pure sector whipsaw while auditing hidden SPY/QQQ beta explicitly
SectorBalancedCarryForward                  inverse vol with 25% cap        top 5 by blended momentum; only admit new names after they persist in top 5 for two weeks                                           reduce churn from one-week rank noise
```

## Standalone Refined Sector Sleeve Validation

Refined sleeve validation positive: **True**.

```
                    sleeve  ann_return  ann_vol   sharpe  max_drawdown   calmar    cvar_5  avg_turnover  beta_spy  beta_qqq
      Top5_Smooth_Momentum    0.093312 0.163904 0.569310     -0.484092 0.192758 -0.055381      0.052299 -0.048618 -0.025627
       DefensiveAware_Top5    0.075810 0.127415 0.594983     -0.216493 0.350172 -0.043412      0.162834 -0.025306 -0.022011
Top4_RiskAdjusted_Momentum    0.065547 0.121497 0.539493     -0.205573 0.318849 -0.042043      0.178505 -0.026954 -0.027382
SectorBalancedCarryForward    0.060306 0.125754 0.479555     -0.213969 0.281844 -0.043493      0.111487 -0.026371 -0.024488
       SectorBlend_SPY_QQQ    0.044103 0.091427 0.482385     -0.159109 0.277186 -0.032332      0.144472 -0.009759 -0.009699
    Top3_Strict_Leadership    0.040148 0.095599 0.419962     -0.175818 0.228349 -0.033649      0.200781 -0.026314 -0.026613
```

## Signal-Active Validation

```
                    sleeve                        signal  active_weeks  active_ann_return  inactive_ann_return  active_minus_inactive_ann_return  active_vs_ggg1  active_vs_phase4_20pct  adverse_event_frequency
       SectorBlend_SPY_QQQ       recovery_sector_reentry            36           0.142907             0.040943                          0.101963        0.044087                0.041706                 0.083333
Top4_RiskAdjusted_Momentum neutral_sector_confirmed_only           174           0.146524             0.051136                          0.095388        0.036795                0.037604                 0.086207
       DefensiveAware_Top5 neutral_sector_confirmed_only           174           0.144764             0.063457                          0.081307        0.035035                0.035844                 0.114943
Top4_RiskAdjusted_Momentum       recovery_sector_reentry            36           0.135497             0.063278                          0.072219        0.036677                0.034296                 0.055556
      Top5_Smooth_Momentum neutral_sector_confirmed_only           174           0.142754             0.084360                          0.058394        0.033025                0.033834                 0.109195
       DefensiveAware_Top5       recovery_sector_reentry            36           0.130497             0.074023                          0.056474        0.031677                0.029296                 0.083333
       SectorBlend_SPY_QQQ   calm_sector_leadership_only           286           0.072510             0.034420                          0.038089        0.033067                0.026140                 0.090909
       SectorBlend_SPY_QQQ neutral_sector_confirmed_only           174           0.127582             0.029280                          0.098303        0.017853                0.018662                 0.109195
       DefensiveAware_Top5   calm_sector_leadership_only           286           0.064638             0.079715                         -0.015077        0.025196                0.018268                 0.083916
SectorBalancedCarryForward neutral_sector_confirmed_only           174           0.126785             0.048387                          0.078398        0.017056                0.017865                 0.091954
      Top5_Smooth_Momentum       recovery_sector_reentry            36           0.118244             0.092486                          0.025758        0.019424                0.017043                 0.083333
       DefensiveAware_Top5     sector_quality_score_high           560           0.089965             0.061586                          0.028379        0.016845                0.015133                 0.098214
Top4_RiskAdjusted_Momentum     sector_quality_score_high           560           0.089809             0.041398                          0.048411        0.016688                0.014977                 0.075000
    Top3_Strict_Leadership neutral_sector_confirmed_only           174           0.121924             0.025616                          0.096307        0.012194                0.013003                 0.109195
      Top5_Smooth_Momentum     sector_quality_score_high           560           0.086262             0.100538                         -0.014276        0.013141                0.011430                 0.107143
    Top3_Strict_Leadership       recovery_sector_reentry            36           0.108148             0.037942                          0.070206        0.009328                0.006947                 0.083333
       SectorBlend_SPY_QQQ      high_quality_sector_bull           528           0.073683             0.017973                          0.055710        0.005371                0.005678                 0.102273
       SectorBlend_SPY_QQQ     sector_quality_score_high           560           0.080173             0.008615                          0.071558        0.007052                0.005340                 0.096429
```

## Candidate Logic

```
                                      candidate                                    sector_sleeve                                                                                 budget                                                                                             logic
  improved_phase4b_refined_sector_small_overlay                             Top5_Smooth_Momentum                                                 12% target in high_quality_sector_bull                 Sharpe-first small overlay from the GGG1 base; target sector sleeve is stripped outside the gate, with residual monthly/smoothing exposure checked in stress diagnostics.
          improved_phase4b_refined_sector_20pct                              DefensiveAware_Top5                  20% target in high_quality_sector_bull or calm_sector_leadership_only           Main Phase 4B test: smoother/defensive-aware replacement for Phase 4 20pct top3 sleeve.
improved_phase4b_refined_sector_25pct_selective                           Top3_Strict_Leadership                                         25% target only when sector_quality_score_high       Selective concentrated version; accepts top3 only under the strongest fixed-quality signal.
          improved_phase4b_sector_phase3_hybrid SectorBlend_SPY_QQQ plus Phase 3 calm US offense                              16% target in high-quality/calm-leadership sector regimes          Risk-adjusted hybrid that combines Phase 3 calm US offense with a blended sector sleeve.
         improved_phase4b_return_unlock_stretch                           Top3_Strict_Leadership 25% target in strongest quality/confirmed neutral regimes plus full aggressive mandate Strongest return-unlock attempt; reject on Sharpe, drawdown, 2022/stress, or hidden beta failure.
```

## Full-Period Metrics

```
                                      portfolio  ann_return  ann_vol   sharpe  max_drawdown    cvar_5  avg_BIL  avg_sector_sleeve_exposure  beta_spy  corr_spy  active_return_vs_phase4_best
                                            QQQ    0.146918 0.198664 0.739527     -0.514472 -0.061888      NaN                         NaN  1.033657  0.914365                      0.070398
                                            SPY    0.105431 0.175737 0.599935     -0.546130 -0.058004      NaN                         NaN  1.000000  1.000000                      0.028911
                        EqualWeightSectorSleeve    0.102521 0.175329 0.584734     -0.542500 -0.058704      NaN                         NaN  0.967904  0.970153                      0.026001
                                    bench_60_40    0.080872 0.103078 0.784570     -0.313836 -0.032731      NaN                         NaN -0.046977 -0.080056                      0.004423
          improved_phase4b_refined_sector_20pct    0.077603 0.080954 0.958606     -0.137725 -0.026683 0.235703                    0.100481 -0.032742 -0.071045                      0.001155
                                    phase4_best    0.076448 0.082190 0.930141     -0.143286 -0.026837 0.238877                    0.128902 -0.035138 -0.075099                      0.000000
                                    phase2_best    0.073892 0.078627 0.939780     -0.125043 -0.026048 0.246166                    0.000000 -0.032065 -0.071636                     -0.002556
         improved_phase4b_return_unlock_stretch    0.073420 0.080255 0.914838     -0.140573 -0.025896 0.259889                    0.124687 -0.035404 -0.077492                     -0.003028
  improved_phase4b_refined_sector_small_overlay    0.073229 0.077379 0.946369     -0.131258 -0.025637 0.262902                    0.055430 -0.031651 -0.071853                     -0.003219
improved_phase4b_refined_sector_25pct_selective    0.072814 0.079848 0.911908     -0.138336 -0.025808 0.262945                    0.124340 -0.035255 -0.077557                     -0.003634
                                    phase3_best    0.072679 0.075242 0.965945     -0.119015 -0.024830 0.279285                    0.000000 -0.030418 -0.071013                     -0.003769
          improved_phase4b_sector_phase3_hybrid    0.072180 0.075729 0.953141     -0.124387 -0.024918 0.282278                    0.078238 -0.030424 -0.070570                     -0.004268
                                           ggg1    0.071381 0.076248 0.936168     -0.117739 -0.025377 0.266580                    0.000000 -0.030808 -0.070976                     -0.005067
                                       prod_pin    0.068923 0.077931 0.884416     -0.139754 -0.026181 0.283918                    0.000000 -0.024908 -0.056143                     -0.007525
                                official_shadow    0.068584 0.077616 0.883625     -0.136741 -0.026085 0.285552                    0.000000 -0.024890 -0.056330                     -0.007864
```

## Holdout And Recent Metrics

```
                                      portfolio        window  ann_return    sharpe  max_drawdown  avg_BIL  avg_sector_sleeve_exposure
                                    phase4_best     bear_2022   -0.008233 -0.131363     -0.066061 0.526652                    0.059215
                                    phase2_best     bear_2022   -0.011410 -0.177155     -0.069271 0.536657                    0.000000
                                           ggg1     bear_2022   -0.012933 -0.211239     -0.068418 0.550054                    0.000000
                                    phase3_best     bear_2022   -0.014259 -0.236065     -0.066584 0.552294                    0.000000
          improved_phase4b_refined_sector_20pct     bear_2022   -0.015241 -0.236977     -0.067847 0.526007                    0.017739
          improved_phase4b_sector_phase3_hybrid     bear_2022   -0.017770 -0.287098     -0.067894 0.548251                    0.013282
  improved_phase4b_refined_sector_small_overlay     bear_2022   -0.018659 -0.311112     -0.069124 0.543408                    0.012207
improved_phase4b_refined_sector_25pct_selective     bear_2022   -0.018815 -0.300322     -0.069342 0.535830                    0.020437
         improved_phase4b_return_unlock_stretch     bear_2022   -0.018952 -0.298052     -0.069974 0.531162                    0.019204
                                            SPY     bear_2022   -0.181754 -0.787666     -0.224795      NaN                         NaN
                                            QQQ     bear_2022   -0.325770 -1.138728     -0.310455      NaN                         NaN
                                            QQQ  holdout_2020    0.188260  0.834023     -0.350556      NaN                         NaN
                                            SPY  holdout_2020    0.141386  0.732351     -0.318290      NaN                         NaN
                                    phase3_best  holdout_2020    0.099358  1.124360     -0.119015 0.249414                    0.000000
                                    phase2_best  holdout_2020    0.097023  1.060738     -0.125043 0.219200                    0.000000
          improved_phase4b_sector_phase3_hybrid  holdout_2020    0.096409  1.068772     -0.124387 0.241550                    0.090103
          improved_phase4b_refined_sector_20pct  holdout_2020    0.095643  1.011697     -0.137725 0.197508                    0.115312
                                           ggg1  holdout_2020    0.095497  1.082205     -0.117739 0.235807                    0.000000
                                    phase4_best  holdout_2020    0.093131  0.964462     -0.143286 0.209708                    0.138619
  improved_phase4b_refined_sector_small_overlay  holdout_2020    0.090521  1.002416     -0.131258 0.234802                    0.063636
         improved_phase4b_return_unlock_stretch  holdout_2020    0.089303  0.917395     -0.140573 0.205523                    0.149983
improved_phase4b_refined_sector_25pct_selective  holdout_2020    0.089065  0.920537     -0.138336 0.207334                    0.150312
                                            QQQ  holdout_2021    0.143416  0.687667     -0.350556      NaN                         NaN
                                            SPY  holdout_2021    0.137128  0.855797     -0.239272      NaN                         NaN
          improved_phase4b_refined_sector_20pct  holdout_2021    0.107099  1.302573     -0.074226 0.181379                    0.124971
                                    phase3_best  holdout_2021    0.105679  1.403428     -0.074152 0.242049                    0.000000
                                    phase2_best  holdout_2021    0.105012  1.340756     -0.076287 0.207294                    0.000000
          improved_phase4b_sector_phase3_hybrid  holdout_2021    0.102583  1.315486     -0.069254 0.232247                    0.097337
                                           ggg1  holdout_2021    0.102228  1.348356     -0.072541 0.226471                    0.000000
                                    phase4_best  holdout_2021    0.101835  1.244575     -0.073421 0.194314                    0.144675
  improved_phase4b_refined_sector_small_overlay  holdout_2021    0.099129  1.296504     -0.071756 0.225189                    0.068470
         improved_phase4b_return_unlock_stretch  holdout_2021    0.098817  1.194661     -0.069974 0.196644                    0.153039
improved_phase4b_refined_sector_25pct_selective  holdout_2021    0.098188  1.190723     -0.069342 0.198659                    0.153451
                                            QQQ recovery_2023    0.294878  1.557826     -0.213416      NaN                         NaN
                                            SPY recovery_2023    0.206376  1.443324     -0.168772      NaN                         NaN
                                    phase3_best recovery_2023    0.149912  1.892587     -0.074152 0.143290                    0.000000
```

## State-By-State Impact

```
                                      portfolio              state  ann_return   sharpe  max_drawdown  avg_BIL  avg_sector_sleeve_exposure  avg_offense_exposure  avg_defense_exposure
                                           ggg1         calm_trend    0.040851 0.513625     -0.139322 0.110330                    0.000000              0.526720              0.436956
          improved_phase4b_refined_sector_20pct         calm_trend    0.043870 0.510065     -0.135916 0.074896                    0.185052              0.652261              0.319452
improved_phase4b_refined_sector_25pct_selective         calm_trend    0.040044 0.461802     -0.131471 0.109176                    0.227052              0.686546              0.285928
  improved_phase4b_refined_sector_small_overlay         calm_trend    0.041735 0.512090     -0.133699 0.101954                    0.098497              0.578501              0.379898
         improved_phase4b_return_unlock_stretch         calm_trend    0.040535 0.467717     -0.131133 0.109219                    0.228741              0.687276              0.285267
          improved_phase4b_sector_phase3_hybrid         calm_trend    0.044722 0.562085     -0.128417 0.129903                    0.146493              0.639248              0.326711
                                    phase2_best         calm_trend    0.041268 0.517105     -0.139793 0.105189                    0.000000              0.530285              0.439437
                                    phase3_best         calm_trend    0.043578 0.587964     -0.122006 0.158727                    0.000000              0.546169              0.418279
                                    phase4_best         calm_trend    0.046796 0.548294     -0.136643 0.087548                    0.185859              0.622390              0.338907
                                           ggg1      neutral_mixed    0.112112 1.461561     -0.091217 0.260356                    0.000000              0.459854              0.311500
          improved_phase4b_refined_sector_20pct      neutral_mixed    0.120736 1.474212     -0.106241 0.221528                    0.095824              0.531134              0.278680
improved_phase4b_refined_sector_25pct_selective      neutral_mixed    0.113652 1.429850     -0.086625 0.254948                    0.116881              0.549813              0.263329
  improved_phase4b_refined_sector_small_overlay      neutral_mixed    0.113275 1.469162     -0.095773 0.259420                    0.054357              0.480059              0.290314
         improved_phase4b_return_unlock_stretch      neutral_mixed    0.114608 1.433323     -0.087644 0.250083                    0.117000              0.552901              0.264856
          improved_phase4b_sector_phase3_hybrid      neutral_mixed    0.109431 1.432628     -0.099019 0.278500                    0.073509              0.501800              0.272324
                                    phase2_best      neutral_mixed    0.117435 1.468792     -0.097213 0.226784                    0.000000              0.481916              0.326545
                                    phase3_best      neutral_mixed    0.112714 1.461507     -0.093329 0.259897                    0.000000              0.468792              0.303369
                                    phase4_best      neutral_mixed    0.115123 1.393738     -0.106797 0.223783                    0.132908              0.537679              0.265745
                                           ggg1 recovery_confirmed    0.025705 0.344267     -0.053798 0.113607                    0.000000              0.576634              0.339096
          improved_phase4b_refined_sector_20pct recovery_confirmed    0.043660 0.562973     -0.052874 0.067867                    0.106914              0.661552              0.291774
improved_phase4b_refined_sector_25pct_selective recovery_confirmed    0.039556 0.450706     -0.065812 0.054192                    0.176457              0.713070              0.271700
  improved_phase4b_refined_sector_small_overlay recovery_confirmed    0.031001 0.417411     -0.053213 0.104949                    0.055650              0.603676              0.311869
         improved_phase4b_return_unlock_stretch recovery_confirmed    0.039560 0.448608     -0.066626 0.053330                    0.181533              0.719010              0.267954
          improved_phase4b_sector_phase3_hybrid recovery_confirmed    0.040072 0.524163     -0.054485 0.093206                    0.079498              0.629500              0.296207
                                    phase2_best recovery_confirmed    0.026741 0.346583     -0.053930 0.083963                    0.000000              0.599446              0.352769
                                    phase3_best recovery_confirmed    0.024606 0.322523     -0.054834 0.106780                    0.000000              0.590763              0.331010
                                    phase4_best recovery_confirmed    0.039650 0.489707     -0.056432 0.081820                    0.156458              0.670806              0.269594
                                           ggg1   recovery_fragile    0.066671 1.142121     -0.032194 0.169929                    0.000000              0.505352              0.364447
          improved_phase4b_refined_sector_20pct   recovery_fragile    0.077134 1.277422     -0.030084 0.147802                    0.020998              0.535998              0.357905
improved_phase4b_refined_sector_25pct_selective   recovery_fragile    0.069290 1.178338     -0.032527 0.165802                    0.020371              0.541865              0.352074
  improved_phase4b_refined_sector_small_overlay   recovery_fragile    0.071663 1.221341     -0.031259 0.167395                    0.015743              0.510304              0.360264
         improved_phase4b_return_unlock_stretch   recovery_fragile    0.070106 1.184957     -0.032840 0.161489                    0.019291              0.545362              0.352399
          improved_phase4b_sector_phase3_hybrid   recovery_fragile    0.068957 1.196302     -0.031627 0.185393                    0.016669              0.526304              0.343765
                                    phase2_best   recovery_fragile    0.069606 1.156644     -0.032387 0.147562                    0.000000              0.520357              0.373919
                                    phase3_best   recovery_fragile    0.067719 1.174409     -0.031296 0.175119                    0.000000              0.514618              0.356519
                                    phase4_best   recovery_fragile    0.080334 1.317319     -0.030419 0.142555                    0.084114              0.560502              0.332557
                                           ggg1     stressed_panic    0.035803 0.480687     -0.121622 0.531336                    0.000000              0.270028              0.220737
          improved_phase4b_refined_sector_20pct     stressed_panic    0.038174 0.499436     -0.124206 0.524431                    0.017331              0.281857              0.219308
improved_phase4b_refined_sector_25pct_selective     stressed_panic    0.037252 0.507180     -0.118034 0.539145                    0.020315              0.284673              0.216491
  improved_phase4b_refined_sector_small_overlay     stressed_panic    0.038936 0.508585     -0.125968 0.528520                    0.010710              0.266151              0.224614
         improved_phase4b_return_unlock_stretch     stressed_panic    0.037373 0.502403     -0.120614 0.535835                    0.018825              0.284380              0.218967
          improved_phase4b_sector_phase3_hybrid     stressed_panic    0.036732 0.507041     -0.116555 0.543765                    0.013425              0.276497              0.214255
```

## Risk / Realism Checks

```
                                      portfolio  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  holdout_2020_return  holdout_2020_sharpe  avg_BIL  avg_sector_sleeve_exposure  maxdd_ok  sharpe_ok  bear_ok  cvar_bad  better_than_60_40_sharpe  disguised_spy_qqq  improves_over_phase4_best_return  improves_over_phase4_best_sharpe  sector_active_delta_vs_phase4_best
  improved_phase4b_refined_sector_small_overlay         0.073229     0.946369          -0.131258    -0.025637             0.090521             1.002416 0.262902                    0.055430      True       True     True     False                      True              False                             False                              True                            0.000277
          improved_phase4b_refined_sector_20pct         0.077603     0.958606          -0.137725    -0.026683             0.095643             1.011697 0.235703                    0.100481      True       True     True     False                      True              False                              True                              True                            0.002548
improved_phase4b_refined_sector_25pct_selective         0.072814     0.911908          -0.138336    -0.025808             0.089065             0.920537 0.262945                    0.124340      True       True     True     False                      True              False                             False                             False                            0.001809
          improved_phase4b_sector_phase3_hybrid         0.072180     0.953141          -0.124387    -0.024918             0.096409             1.068772 0.282278                    0.078238      True       True     True     False                      True              False                             False                              True                            0.002706
         improved_phase4b_return_unlock_stretch         0.073420     0.914838          -0.140573    -0.025896             0.089303             0.917395 0.259889                    0.124687      True       True     True     False                      True              False                             False                             False                            0.001987
```

## Hidden Beta / Cash Checks

```
                                      portfolio  beta_spy  corr_spy  beta_qqq  corr_qqq  ann_improvement_vs_ggg1  ann_improvement_vs_phase4_best  beta_attribution_estimate  pct_improvement_from_beta hidden_beta_risk  avg_BIL  bil_reduction_vs_ggg1
  improved_phase4b_refined_sector_small_overlay -0.031651 -0.071853 -0.024624 -0.063193                 0.001848                       -0.003219                  -0.000089                   0.048101              LOW 0.262902              -0.003678
          improved_phase4b_refined_sector_20pct -0.032742 -0.071045 -0.026022 -0.063831                 0.006222                        0.001155                  -0.000204                   0.032763              LOW 0.235703              -0.030877
improved_phase4b_refined_sector_25pct_selective -0.035255 -0.077557 -0.028182 -0.070087                 0.001433                       -0.003634                  -0.000469                   0.327108              LOW 0.262945              -0.003635
          improved_phase4b_sector_phase3_hybrid -0.030424 -0.070570 -0.023413 -0.061393                 0.000799                       -0.004268                   0.000041                   0.050757              LOW 0.282278               0.015698
         improved_phase4b_return_unlock_stretch -0.035404 -0.077492 -0.028197 -0.069769                 0.002039                       -0.003028                  -0.000485                   0.237625              LOW 0.259889              -0.006691
```

## 2022 Bear Protection

```
                                      portfolio  bear_2022_return  ggg1_bear_2022_return  phase4_best_bear_2022_return  delta_vs_ggg1  delta_vs_phase4_best  bear_ok
  improved_phase4b_refined_sector_small_overlay         -0.018659              -0.012933                     -0.008233      -0.005726             -0.010426     True
          improved_phase4b_refined_sector_20pct         -0.015241              -0.012933                     -0.008233      -0.002308             -0.007008     True
improved_phase4b_refined_sector_25pct_selective         -0.018815              -0.012933                     -0.008233      -0.005882             -0.010582     True
          improved_phase4b_sector_phase3_hybrid         -0.017770              -0.012933                     -0.008233      -0.004837             -0.009537     True
         improved_phase4b_return_unlock_stretch         -0.018952              -0.012933                     -0.008233      -0.006019             -0.010720     True
```

## Sector Concentration / Turnover

```
                                      portfolio  avg_total_sector_etf_weight  avg_max_single_sector_etf_weight  max_single_sector_etf_weight  avg_top3_sector_etf_weight  active_sector_weeks
  improved_phase4b_refined_sector_small_overlay                     0.125758                          0.077233                          0.35                    0.099405                  862
          improved_phase4b_refined_sector_20pct                     0.167824                          0.082326                          0.35                    0.122240                  847
improved_phase4b_refined_sector_25pct_selective                     0.156395                          0.086904                          0.35                    0.146413                  804
          improved_phase4b_sector_phase3_hybrid                     0.109941                          0.070218                          0.35                    0.088309                  813
         improved_phase4b_return_unlock_stretch                     0.157567                          0.087377                          0.35                    0.147542                  802
```

## Sector-Active Candidate Windows

```
                                      portfolio                     signal  active_weeks  signal_active_ann_return  signal_inactive_ann_return  signal_active_delta_vs_ggg1  signal_active_delta_vs_phase4_best
  improved_phase4b_refined_sector_small_overlay high_quality_or_score_high           572                  0.070142                    0.076520                     0.000609                            0.000277
          improved_phase4b_refined_sector_20pct high_quality_or_score_high           572                  0.072414                    0.083149                     0.002880                            0.002548
improved_phase4b_refined_sector_25pct_selective high_quality_or_score_high           572                  0.071674                    0.074027                     0.002141                            0.001809
          improved_phase4b_sector_phase3_hybrid high_quality_or_score_high           572                  0.072571                    0.071765                     0.003037                            0.002706
         improved_phase4b_return_unlock_stretch high_quality_or_score_high           572                  0.071853                    0.075089                     0.002319                            0.001987
```

## Selection Table

```
                                      portfolio            classification                                                                       reason  full_ann_return  full_sharpe  full_max_drawdown  holdout_2020_return  holdout_2020_sharpe  holdout_2021_return  holdout_2021_sharpe  bear_2022_return  beats_ggg1  beats_phase2_best  beats_phase3_best  beats_phase4_best  sector_active_good  refined_sleeve_validation_positive
  improved_phase4b_refined_sector_small_overlay KEEP_AS_AGGRESSIVE_SHADOW credible refinement over Phase 4 best but not production-challenger strength         0.073229     0.946369          -0.131258             0.090521             1.002416             0.099129             1.296504         -0.018659        True               True               True               True                True                                True
          improved_phase4b_refined_sector_20pct KEEP_AS_AGGRESSIVE_SHADOW credible refinement over Phase 4 best but not production-challenger strength         0.077603     0.958606          -0.137725             0.095643             1.011697             0.107099             1.302573         -0.015241        True               True               True               True                True                                True
improved_phase4b_refined_sector_25pct_selective     KEEP_AS_RESEARCH_ONLY               partial refined-sector evidence but weak aggregate improvement         0.072814     0.911908          -0.138336             0.089065             0.920537             0.098188             1.190723         -0.018815        True              False               True              False                True                                True
          improved_phase4b_sector_phase3_hybrid     KEEP_AS_RESEARCH_ONLY               partial refined-sector evidence but weak aggregate improvement         0.072180     0.953141          -0.124387             0.096409             1.068772             0.102583             1.315486         -0.017770       False               True              False               True                True                                True
         improved_phase4b_return_unlock_stretch     KEEP_AS_RESEARCH_ONLY               partial refined-sector evidence but weak aggregate improvement         0.073420     0.914838          -0.140573             0.089303             0.917395             0.098817             1.194661         -0.018952        True              False               True              False                True                                True
```

## Audit Results

```
                    audit                             candidate status                                         log
research_committee_report improved_phase4b_refined_sector_20pct   PASS phase4b_research_committee_report_quick.log
   backtest_realism_audit improved_phase4b_refined_sector_20pct   PASS    phase4b_backtest_realism_audit_quick.log
allocator_benchmark_audit improved_phase4b_refined_sector_20pct   PASS phase4b_allocator_benchmark_audit_quick.log
```

## Final Recommendation

**Recommendation:** `KEEP_PHASE4B_AS_AGGRESSIVE_SHADOW`

**Best candidate:** `improved_phase4b_refined_sector_20pct`

**Rationale:** improved_phase4b_refined_sector_20pct is a credible refinement over Phase 4 best but not production-ready.

## Next Phase Prompt Outline

```
Phase 5 true stock breadth data upgrade prompt outline:
1. Do not change production, official shadow, or GGG1 pins.
2. Add or source causal stock-level breadth only through an explicit data-hub update with provenance and survivorship-bias controls.
3. Keep stressed_panic protection unchanged and use lagged/time-ordered validation only.
4. Test whether true stock breadth improves bull/neutral/recovery offense timing beyond ETF sector breadth.
5. Compare against GGG1, Phase 2, Phase 3, Phase 4, Phase 4B, SPY, QQQ, and 60/40 across full and holdout windows.
6. Reject if gains are hidden SPY/QQQ beta, weak holdout, or broken 2022/stressed protection.
```

## Resume / Project Story Summary

Phase 4B tested whether the dedicated sector sleeve from Phase 4 could be made more useful through narrower activation, smoother ranking, defensive-leadership blocking, and strict high-quality timing. The experiment used only existing ETF data, causal week-t signals, time-ordered validation, and the standard Layer 3 cost/build pipeline. Phase 4B state tilts strip target sector-sleeve weight outside their gates; small residual sector exposure can persist from the monthly/smoothed allocator, so stressed_panic, recovery_fragile, and 2022 protection were audited explicitly instead of assumed. The final recommendation above should guide the next research step; production, official shadow, and GGG1 pins remain unchanged.
