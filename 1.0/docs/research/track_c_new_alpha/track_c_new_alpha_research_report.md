# Track C New Alpha Research Report

## 1. Track C Objective

Test whether a small number of research-only new-alpha sleeves can improve Track A after controlling for SPY beta, BIL/cash drag, transaction costs, turnover, drawdown, and repeated experimentation. Track A production is unchanged.

## 2. Track A Baseline

- Production candidate: `improved_frontier_phase5_fragility_guard`
- Official holdout start: `2024-04-19`
- Canonical metrics/cost modules: `scripts/production_metrics.py`, `scripts/production_costs.py`

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | avg_weekly_turnover | holdout_sharpe |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_a_production | 0.07134169432 | 0.9482556438 | -0.1160345789 | 0.6148313289 | -0.02494792886 | 0.2760603192 | 0.2949097764 | 0.2402307405 | 0.06738780266 | 2.178585179 |
| spy_buy_hold | 0.1053309083 | 0.5996349785 | -0.5461301945 | 0.1928677619 | -0.0580042681 | 0 | 1 | 1 | 0 | 1.219906078 |
| static_60_spy_40_ief | 0.0808715342 | 0.7845698297 | -0.3138361945 | 0.2576870853 | -0.03273141716 | 0 | 0.6 | 0.569015337 | 0 | 1.484958316 |
| static_80_spy_20_bil | 0.08872865466 | 0.6319156495 | -0.4584235979 | 0.1935516737 | -0.04633090118 | 0.2 | 0.8 | 0.799338497 | 0 | 1.296778084 |
| aggressive_taa_spy_trend | 0.09237202193 | 0.7368644892 | -0.3624634652 | 0.2548450556 | -0.04069558701 | 0.1653153153 | 0.8346846847 | 0.6719788291 | 0.04147880974 | 1.542338 |
| dual_momentum_top1 | 0.05619201476 | 0.3078510185 | -0.3964845068 | 0.1417256256 | -0.05786057138 | 0.05135135135 | 0.6027027027 | 0.3380573284 | 0.1992786294 | 1.070313971 |
| static_global_growth_90_10 | 0.1049740919 | 0.6401647047 | -0.4987412313 | 0.2104780702 | -0.05380554386 | 0.05 | 0.9 | 0.9204453864 | 0 | 1.405214474 |
| track_b_aggressive_cash10_offense20 | 0.07669464185 | 0.8792114176 | -0.1205316727 | 0.6363028084 | -0.02923111626 | 0.1453834937 | 0.4116846616 | 0.2979568852 | 0.07742967997 | 2.131746929 |

## 3. Track B Lesson Learned

Track B tested higher-risk variants and showed that higher returns were largely explained by higher SPY beta and lower BIL/cash drag. Track C therefore treats raw return improvement as insufficient unless beta/cash-adjusted residual is positive.

## 4. Earlier Research Ideas Considered

- Already implemented sufficiently: raw xsmom/tsmom, multi-horizon momentum, HRP/HERC/risk-parity allocator variants, and Track B cash/offense overlays.
- Implemented but incomplete or flawed: residual momentum, carry/value ETF proxies, short-horizon reversal, HYG/LQD pair diagnostics, volatility-managed alpha, and canary/breadth timing.
- Not selected: CVaR optimizer diagnostics and Black-Litterman because Track C is an alpha-sleeve audit, not an allocator redesign.
- Requires unavailable data: point-in-time stock breadth, holdings breadth, and richer macro/credit series.
- Explicitly out of scope: ML/meta-labeling and large parameter sweeps.

## 5. Ideas Selected And Why

Six predeclared sleeves were tested: residual xsmom, vol-managed residual xsmom, carry/value, neutral reversal, HYG/LQD pair mean reversion, and canary/breadth timing. Each uses existing repo data and has a different failure mode than Track B cash/offense overlays.

## 6. Ideas Rejected Before Implementation And Why

CVaR optimization, Black-Litterman, new macro/credit conditioning, PIT breadth, and ML were rejected before implementation because they either duplicate prior allocator research, need new data, or create overfit risk outside Track C's small-candidate mandate.

## 7. Standalone Sleeve Results

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | track_a_corr | avg_weekly_turnover | holdout_sharpe | beta_adjusted_residual_ann | standalone_sanity_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_c_canary_breadth_timing | 0.06146170133 | 1.044016802 | -0.09510100755 | 0.6462781301 | -0.01863389812 | 0.24 | 0.3958108108 | 0.1826483489 | 0.6550932658 | 0.04481514878 | 1.472930135 | 0.03258118573 | True |
| track_c_vol_managed_residual_xsmom_top5 | 0.07092932732 | 0.4880946751 | -0.4395504442 | 0.1613678891 | -0.04979299634 | 0.1205405405 | 0.4188828829 | 0.5245869365 | 0.6962788285 | 0.1511271416 | 1.389315847 | 0.01006583442 | True |
| track_c_residual_xsmom_top5 | 0.0773714632 | 0.4548556807 | -0.5218629155 | 0.148260129 | -0.05828357662 | 0.04954954955 | 0.4540540541 | 0.6589976926 | 0.6615294214 | 0.1536519387 | 1.51412895 | 0.003935957895 | False |
| track_c_hyg_lqd_pair_mean_reversion | 0.02785794782 | 0.3024284224 | -0.3581208429 | 0.07778923894 | -0.02894658589 | 0.1297297297 | 0 | 0.2616407012 | 0.5620369094 | 0.07484220018 | 1.19304696 | -0.008411060055 | False |
| track_c_carry_value_top5 | 0.04983346009 | 0.2877581485 | -0.4970005472 | 0.100268421 | -0.05644099195 | 0.005405405405 | 0.3095495495 | 0.6884055018 | 0.4615006384 | 0.07592425609 | 1.963101143 | -0.02635268328 | False |
| track_c_neutral_reversal_top5 | 0.04683531631 | 0.2636093402 | -0.5369190862 | 0.08722974748 | -0.06012888897 | 0.2927927928 | 0.3167567568 | 0.7189698624 | 0.398456977 | 0.3871956718 | 0.791928419 | -0.03220964231 | False |

## 8. Blend-With-Track-A Results

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | track_a_corr | avg_weekly_turnover | holdout_sharpe | delta_ann_return_vs_track_a | delta_sharpe_vs_track_a | beta_cash_adjusted_residual_vs_track_a_est_ann | track_c_watchlist |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_c_track_a_plus_canary_breadth_timing_15 | 0.07015733815 | 1.001510481 | -0.1046912536 | 0.6701356199 | -0.02315704124 | 0.2706512713 | 0.3100449316 | 0.2315831901 | 0.9954562779 | 0.06263250686 | 2.168950212 | -0.001184356173 | 0.05325483761 | -0.0008814451956 | False |
| track_c_track_a_plus_canary_breadth_timing_10 | 0.07057968798 | 0.9843068943 | -0.1080786596 | 0.6530400013 | -0.02373220148 | 0.2724542873 | 0.3049998799 | 0.234465639 | 0.9980749746 | 0.06387977486 | 2.175057012 | -0.0007620063416 | 0.0360512505 | -0.0005600593369 | False |
| track_c_track_a_plus_canary_breadth_timing_05 | 0.07098243261 | 0.966612799 | -0.1114733014 | 0.6367662187 | -0.02433514661 | 0.2742573032 | 0.2999548281 | 0.2373476927 | 0.9995413476 | 0.06532220082 | 2.178183331 | -0.0003592617112 | 0.01835715521 | -0.0002582417226 | False |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | 0.07166910623 | 0.9342858829 | -0.1156281918 | 0.6198238084 | -0.025412053 | 0.2682843302 | 0.3011084317 | 0.2544512287 | 0.9976864042 | 0.0706509801 | 2.142555326 | 0.0003274119103 | -0.01396976095 | -0.001730012592 | False |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | 0.07193698077 | 0.9160992568 | -0.1163690872 | 0.6181794709 | -0.02596097071 | 0.2605083413 | 0.3073070871 | 0.2686665803 | 0.9911400155 | 0.07442956943 | 2.102612144 | 0.0005952864478 | -0.03215638706 | -0.003519082114 | False |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | 0.07216568682 | 0.8947069743 | -0.1314229869 | 0.5491100799 | -0.02663099204 | 0.2527323524 | 0.3135057424 | 0.2828834819 | 0.9810088661 | 0.07835468829 | 2.060077311 | 0.0008239925053 | -0.05354866954 | -0.005347465092 | False |

## 9. Cost Sensitivity

| name | kind | cost_multiplier | ann_return | sharpe | max_drawdown | cvar_5 | avg_weekly_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| track_c_residual_xsmom_top5 | standalone_sleeve | 2 | 0.06882689659 | 0.4047770444 | -0.5243739477 | -0.05840699378 | 0.1536519387 |
| track_c_residual_xsmom_top5 | standalone_sleeve | 3 | 0.06034752577 | 0.3550290923 | -0.5268726046 | -0.05853199378 | 0.1536519387 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | 2 | 0.0625691126 | 0.4306886829 | -0.4420281888 | -0.04992656777 | 0.1511271416 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | 3 | 0.05427169808 | 0.3736614502 | -0.4444956813 | -0.05006013919 | 0.1511271416 |
| track_c_carry_value_top5 | standalone_sleeve | 2 | 0.04569568438 | 0.2638162898 | -0.5002820993 | -0.0565588491 | 0.07592425609 |
| track_c_carry_value_top5 | standalone_sleeve | 3 | 0.04157323457 | 0.2399666223 | -0.5035429847 | -0.05667729152 | 0.07592425609 |
| track_c_neutral_reversal_top5 | standalone_sleeve | 2 | 0.02599288626 | 0.1462891792 | -0.5440564796 | -0.06053960325 | 0.3871956718 |
| track_c_neutral_reversal_top5 | standalone_sleeve | 3 | 0.005551597365 | 0.03123661736 | -0.5510873033 | -0.06095031754 | 0.3871956718 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | 2 | 0.02386797511 | 0.2590232464 | -0.3651942302 | -0.02904927608 | 0.07484220018 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | 3 | 0.01988951856 | 0.2156816785 | -0.3721966861 | -0.02915641894 | 0.07484220018 |
| track_c_canary_breadth_timing | standalone_sleeve | 2 | 0.05899466244 | 1.001766434 | -0.1001557911 | -0.01868568383 | 0.04481514878 |
| track_c_canary_breadth_timing | standalone_sleeve | 3 | 0.05653230131 | 0.959376728 | -0.10518413 | -0.01873746954 | 0.04481514878 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | 2 | 0.06774781203 | 0.8832164497 | -0.1161937537 | -0.02550189493 | 0.0706509801 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | 3 | 0.0638399833 | 0.8322358828 | -0.1167592444 | -0.02559339883 | 0.0706509801 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | 2 | 0.06780556265 | 0.8635632709 | -0.1169379945 | -0.02606145293 | 0.07442956943 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | 3 | 0.063689212 | 0.8111415928 | -0.1175068135 | -0.02616284783 | 0.07442956943 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | 2 | 0.06781612598 | 0.8408818267 | -0.1324823472 | -0.02673112455 | 0.07835468829 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | 3 | 0.0634833679 | 0.7871946067 | -0.1335405929 | -0.02683162477 | 0.07835468829 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | 2 | 0.06735864731 | 0.9173078624 | -0.112024608 | -0.0244194192 | 0.06532220082 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | 3 | 0.0637462762 | 0.868060872 | -0.1125758686 | -0.0245036918 | 0.06532220082 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | 2 | 0.06703712893 | 0.9349497275 | -0.1086369609 | -0.02381201314 | 0.06387977486 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | 3 | 0.06350551072 | 0.885649655 | -0.1091951964 | -0.02389345259 | 0.06387977486 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | 2 | 0.06668521363 | 0.9519984688 | -0.1052564451 | -0.02323713758 | 0.06263250686 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | 3 | 0.06322362841 | 0.9025428345 | -0.1058215522 | -0.02331723391 | 0.06263250686 |

## 10. Turnover Analysis

Turnover is canonical one-way turnover from `scripts/production_costs.py`. Reversal and pair sleeves were expected to be the most vulnerable to cost drag; any watchlist candidate must survive at least 2x costs.

| name | avg_weekly_turnover | annualized_turnover | annualized_cost |
| --- | --- | --- | --- |
| track_c_neutral_reversal_top5 | 0.3871956718 | 20.13417493 | 0.02011603604 |
| track_c_residual_xsmom_top5 | 0.1536519387 | 7.989900812 | 0.007982702703 |
| track_c_vol_managed_residual_xsmom_top5 | 0.1511271416 | 7.858611362 | 0.007851531532 |
| track_c_carry_value_top5 | 0.07592425609 | 3.948061317 | 0.003944504505 |
| track_c_hyg_lqd_pair_mean_reversion | 0.07484220018 | 3.891794409 | 0.003888288288 |
| track_c_canary_breadth_timing | 0.04481514878 | 2.330387737 | 0.002328288288 |

## 11. Beta-Adjusted Attribution

Standalone residual compares each sleeve against a BIL plus SPY-beta expected-return proxy. Blend residual subtracts both incremental SPY beta and estimated BIL/cash-drag reduction versus Track A.

| name | kind | ann_return | delta_ann_return_vs_track_a | spy_beta | avg_BIL | cash_drag_reduction_est_ann | beta_explained_return_est_ann | beta_cash_adjusted_residual_vs_track_a_est_ann | beta_adjusted_residual_ann | return_source_label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_c_residual_xsmom_top5 | standalone_sleeve | 0.0773714632 |  | 0.6589976926 | 0.04954954955 |  |  |  | 0.003935957895 | positive_beta_adjusted_residual |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | 0.07092932732 |  | 0.5245869365 | 0.1205405405 |  |  |  | 0.01006583442 | positive_beta_adjusted_residual |
| track_c_carry_value_top5 | standalone_sleeve | 0.04983346009 |  | 0.6884055018 | 0.005405405405 |  |  |  | -0.02635268328 | no_positive_beta_adjusted_residual |
| track_c_neutral_reversal_top5 | standalone_sleeve | 0.04683531631 |  | 0.7189698624 | 0.2927927928 |  |  |  | -0.03220964231 | no_positive_beta_adjusted_residual |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | 0.02785794782 |  | 0.2616407012 | 0.1297297297 |  |  |  | -0.008411060055 | no_positive_beta_adjusted_residual |
| track_c_canary_breadth_timing | standalone_sleeve | 0.06146170133 |  | 0.1826483489 | 0.24 |  |  |  | 0.03258118573 | positive_beta_adjusted_residual |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | 0.07166910623 | 0.0003274119103 | 0.2544512287 | 0.2682843302 | 0.000727321474 | 0.001330103028 | -0.001730012592 |  | mostly_beta_or_cash_drag |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | 0.07193698077 | 0.0005952864478 | 0.2686665803 | 0.2605083413 | 0.001454642948 | 0.002659725614 | -0.003519082114 |  | mostly_beta_or_cash_drag |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | 0.07216568682 | 0.0008239925053 | 0.2828834819 | 0.2527323524 | 0.002181964422 | 0.003989493175 | -0.005347465092 |  | mostly_beta_or_cash_drag |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | 0.07098243261 | -0.0003592617112 | 0.2373476927 | 0.2742573032 | 0.0001686437875 | -0.0002696637762 | -0.0002582417226 |  | no_return_improvement |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | 0.07057968798 | -0.0007620063416 | 0.234465639 | 0.2724542873 | 0.0003372875749 | -0.0005392345796 | -0.0005600593369 |  | no_return_improvement |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | 0.07015733815 | -0.001184356173 | 0.2315831901 | 0.2706512713 | 0.0005059313624 | -0.00080884234 | -0.0008814451956 |  | no_return_improvement |

## 12. Correlation/Diversification Analysis

| name | kind | reference_type | reference_name | correlation |
| --- | --- | --- | --- | --- |
| track_c_residual_xsmom_top5 | standalone_sleeve | track_a | improved_frontier_phase5_fragility_guard | 0.6615294214 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | dual_momentum_topn | 0.6233036157 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | taa_10m_sma | 0.6278320526 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | composite_trend_quality_refined | 0.7318167957 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | composite_calm_carry_sleeve | -0.04901205532 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | composite_breadth_filtered | 0.6024833671 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | cross_sectional_reversal_combo_ls | 0.1828145814 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | pairs_stat_arb_research | -0.04249760541 |
| track_c_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | cta_trend_vol_managed | 0.6289032215 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | track_a | improved_frontier_phase5_fragility_guard | 0.6962788285 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | dual_momentum_topn | 0.6651559283 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | taa_10m_sma | 0.6497312326 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | composite_trend_quality_refined | 0.7515106847 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | composite_calm_carry_sleeve | -0.04128878486 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | composite_breadth_filtered | 0.612567248 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | cross_sectional_reversal_combo_ls | 0.1264088171 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | pairs_stat_arb_research | -0.04877780053 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | existing_sleeve | cta_trend_vol_managed | 0.6767862719 |
| track_c_carry_value_top5 | standalone_sleeve | track_a | improved_frontier_phase5_fragility_guard | 0.4615006384 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | dual_momentum_topn | 0.3628483298 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | taa_10m_sma | 0.4255265295 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | composite_trend_quality_refined | 0.4611563309 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | composite_calm_carry_sleeve | -0.03561569313 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | composite_breadth_filtered | 0.4749126754 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | cross_sectional_reversal_combo_ls | 0.2686903948 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | pairs_stat_arb_research | 0.2036670954 |
| track_c_carry_value_top5 | standalone_sleeve | existing_sleeve | cta_trend_vol_managed | 0.3877530561 |
| track_c_neutral_reversal_top5 | standalone_sleeve | track_a | improved_frontier_phase5_fragility_guard | 0.398456977 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | dual_momentum_topn | 0.3862998002 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | taa_10m_sma | 0.419427421 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | composite_trend_quality_refined | 0.4876974962 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | composite_calm_carry_sleeve | 0.005524597983 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | composite_breadth_filtered | 0.4268409974 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | cross_sectional_reversal_combo_ls | 0.5971101201 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | pairs_stat_arb_research | 0.1796615215 |
| track_c_neutral_reversal_top5 | standalone_sleeve | existing_sleeve | cta_trend_vol_managed | 0.3867972317 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | track_a | improved_frontier_phase5_fragility_guard | 0.5620369094 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | dual_momentum_topn | 0.4241304145 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | taa_10m_sma | 0.472838865 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | composite_trend_quality_refined | 0.4433216499 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | composite_calm_carry_sleeve | -0.07808790042 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | composite_breadth_filtered | 0.5271329105 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | cross_sectional_reversal_combo_ls | 0.1128682612 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | pairs_stat_arb_research | -0.009629656293 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | existing_sleeve | cta_trend_vol_managed | 0.4294162325 |
| track_c_canary_breadth_timing | standalone_sleeve | track_a | improved_frontier_phase5_fragility_guard | 0.6550932658 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | dual_momentum_topn | 0.5564955398 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | taa_10m_sma | 0.5632356879 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | composite_trend_quality_refined | 0.6138719516 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | composite_calm_carry_sleeve | -0.05395173169 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | composite_breadth_filtered | 0.4699980824 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | cross_sectional_reversal_combo_ls | -0.06328047023 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | pairs_stat_arb_research | 0.03221376714 |
| track_c_canary_breadth_timing | standalone_sleeve | existing_sleeve | cta_trend_vol_managed | 0.66526062 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | track_a | improved_frontier_phase5_fragility_guard | 0.9976864042 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | dual_momentum_topn | 0.8533727856 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | taa_10m_sma | 0.7790174769 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | composite_trend_quality_refined | 0.8377831615 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | composite_calm_carry_sleeve | -0.07398765841 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | composite_breadth_filtered | 0.8302792757 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | cross_sectional_reversal_combo_ls | 0.08666769756 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | pairs_stat_arb_research | -0.06604803041 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | existing_sleeve | cta_trend_vol_managed | 0.8407381546 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | track_a | improved_frontier_phase5_fragility_guard | 0.9911400155 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | dual_momentum_topn | 0.8545490941 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | taa_10m_sma | 0.7842371352 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | composite_trend_quality_refined | 0.8485330099 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | composite_calm_carry_sleeve | -0.07250168405 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | composite_breadth_filtered | 0.8280547126 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | cross_sectional_reversal_combo_ls | 0.09251792864 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | pairs_stat_arb_research | -0.06587677158 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | existing_sleeve | cta_trend_vol_managed | 0.8439931114 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | track_a | improved_frontier_phase5_fragility_guard | 0.9810088661 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | dual_momentum_topn | 0.8523018387 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | taa_10m_sma | 0.7861127572 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | composite_trend_quality_refined | 0.8554137028 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | composite_calm_carry_sleeve | -0.07080064974 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | composite_breadth_filtered | 0.822676254 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | cross_sectional_reversal_combo_ls | 0.09771668197 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | existing_sleeve | pairs_stat_arb_research | -0.06545665126 |

## 13. State-By-State Performance

| name | kind | market_state | ann_return | sharpe | max_drawdown | cvar_5 |
| --- | --- | --- | --- | --- | --- | --- |
| track_c_residual_xsmom_top5 | standalone_sleeve | calm_trend | 0.01680178029 | 0.1221067833 | -0.3170479052 | -0.04861169285 |
| track_c_residual_xsmom_top5 | standalone_sleeve | neutral_mixed | 0.1454750799 | 0.9981024412 | -0.1954638974 | -0.04665358142 |
| track_c_residual_xsmom_top5 | standalone_sleeve | recovery_confirmed | 0.08915723903 | 0.7506315317 | -0.08316485931 | -0.03255060644 |
| track_c_residual_xsmom_top5 | standalone_sleeve | recovery_fragile | 0.143049341 | 1.20143072 | -0.04948372451 | -0.03005769382 |
| track_c_residual_xsmom_top5 | standalone_sleeve | stressed_panic | 0.002354308519 | 0.009267738465 | -0.5379778031 | -0.08661248442 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | calm_trend | 0.01374647132 | 0.1008746919 | -0.3170479052 | -0.0480669713 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | neutral_mixed | 0.1384256342 | 1.033823828 | -0.197313804 | -0.04271627513 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | recovery_confirmed | 0.08469878411 | 0.7402071705 | -0.0749578682 | -0.03193590542 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | recovery_fragile | 0.1130538307 | 1.050476234 | -0.04731542358 | -0.02777230808 |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | stressed_panic | -0.003069624547 | -0.0164399352 | -0.4494709452 | -0.06599635583 |
| track_c_carry_value_top5 | standalone_sleeve | calm_trend | 0.02695152831 | 0.2122661301 | -0.2172476646 | -0.04226725317 |
| track_c_carry_value_top5 | standalone_sleeve | neutral_mixed | 0.05264424937 | 0.3923978908 | -0.320961899 | -0.04308550905 |
| track_c_carry_value_top5 | standalone_sleeve | recovery_confirmed | 0.04785077153 | 0.3478563154 | -0.1020051778 | -0.03959258468 |
| track_c_carry_value_top5 | standalone_sleeve | recovery_fragile | 0.05868030502 | 0.3988522014 | -0.08855854753 | -0.03921589272 |
| track_c_carry_value_top5 | standalone_sleeve | stressed_panic | 0.07232690839 | 0.2588718934 | -0.4189569615 | -0.09858291109 |
| track_c_neutral_reversal_top5 | standalone_sleeve | calm_trend | 0.008500009622 | 0.2969624607 | -0.05656278841 | -0.008732407948 |
| track_c_neutral_reversal_top5 | standalone_sleeve | neutral_mixed | 0.05046529184 | 0.3528971766 | -0.3140435579 | -0.04636218412 |
| track_c_neutral_reversal_top5 | standalone_sleeve | recovery_confirmed | 0.1784244618 | 2.976123633 | -0.008177632286 | -0.004129863687 |
| track_c_neutral_reversal_top5 | standalone_sleeve | recovery_fragile | 0.1270914136 | 1.605991801 | -0.02901325588 | -0.01886361776 |
| track_c_neutral_reversal_top5 | standalone_sleeve | stressed_panic | 0.0489847053 | 0.1503113726 | -0.4655342766 | -0.1128452865 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | calm_trend | 0.04048307562 | 0.6694097682 | -0.08705918091 | -0.01987705548 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | neutral_mixed | 0.05394007979 | 0.9997860282 | -0.06666507567 | -0.01743691759 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | recovery_confirmed | -0.0007223253764 | -0.01539331093 | -0.04219305079 | -0.01582941515 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | recovery_fragile | -0.01775979354 | -0.3021704566 | -0.04950483401 | -0.02037830635 |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | stressed_panic | -0.02670195758 | -0.1566417153 | -0.330348648 | -0.05950687603 |
| track_c_canary_breadth_timing | standalone_sleeve | calm_trend | 0.06543946478 | 0.9371223552 | -0.08427156078 | -0.02282392168 |
| track_c_canary_breadth_timing | standalone_sleeve | neutral_mixed | 0.07454392101 | 1.191637271 | -0.07839849104 | -0.01839756129 |
| track_c_canary_breadth_timing | standalone_sleeve | recovery_confirmed | 0.03894838385 | 0.5689712658 | -0.05481118746 | -0.02131507714 |
| track_c_canary_breadth_timing | standalone_sleeve | recovery_fragile | 0.1267040545 | 2.352310401 | -0.02795142183 | -0.01448817903 |
| track_c_canary_breadth_timing | standalone_sleeve | stressed_panic | 0.02001068237 | 0.834840612 | -0.03808763675 | -0.006665084543 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | calm_trend | 0.03939031987 | 0.5034489762 | -0.1466394504 | -0.02669973679 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | neutral_mixed | 0.1138763458 | 1.471694557 | -0.08719802106 | -0.02464259008 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | recovery_confirmed | 0.0283844141 | 0.3737843951 | -0.05468803996 | -0.02240917225 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | recovery_fragile | 0.06967059503 | 1.176833979 | -0.03129382241 | -0.01746680947 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | track_a_blend | stressed_panic | 0.03435098359 | 0.4484789501 | -0.1245034012 | -0.02457823913 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | calm_trend | 0.03824979191 | 0.4780576234 | -0.1518206272 | -0.02753746177 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | neutral_mixed | 0.1154051409 | 1.463956414 | -0.08813959303 | -0.02483895888 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | recovery_confirmed | 0.03143369847 | 0.4066613661 | -0.05567043346 | -0.02272219517 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | recovery_fragile | 0.07208897883 | 1.191173661 | -0.0312918936 | -0.01781274498 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | track_a_blend | stressed_panic | 0.03292553545 | 0.4145985624 | -0.1273763627 | -0.02612952999 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | calm_trend | 0.03708200595 | 0.4522385028 | -0.1571122519 | -0.02840163271 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | neutral_mixed | 0.1169011682 | 1.451554924 | -0.09111352934 | -0.0250776516 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | recovery_confirmed | 0.03447205789 | 0.4376972566 | -0.05665593382 | -0.0230352181 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | recovery_fragile | 0.07448028719 | 1.200283349 | -0.03130079233 | -0.01816209133 |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | track_a_blend | stressed_panic | 0.03143544865 | 0.3793282494 | -0.1373059981 | -0.02805635491 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | calm_trend | 0.04178372095 | 0.5524959604 | -0.1367456958 | -0.02552218987 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | neutral_mixed | 0.1105177761 | 1.481005216 | -0.08423398273 | -0.02385449403 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | recovery_confirmed | 0.02605421417 | 0.3541215248 | -0.05364128963 | -0.02199286646 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | recovery_fragile | 0.07039486696 | 1.246214095 | -0.02877180473 | -0.01648695333 |
| track_c_track_a_plus_canary_breadth_timing_05 | track_a_blend | stressed_panic | 0.03509838941 | 0.494300269 | -0.1148460055 | -0.02198422461 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | calm_trend | 0.04307795577 | 0.5773247537 | -0.1319579333 | -0.02515608561 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | neutral_mixed | 0.108697964 | 1.486427353 | -0.08222302071 | -0.02325017131 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | recovery_confirmed | 0.02680509771 | 0.3695606391 | -0.05357462093 | -0.02188823206 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | recovery_fragile | 0.07344207191 | 1.335844407 | -0.02683889396 | -0.01585375809 |
| track_c_track_a_plus_canary_breadth_timing_10 | track_a_blend | stressed_panic | 0.03443553704 | 0.5097248169 | -0.1080444956 | -0.02087725016 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | calm_trend | 0.04436497892 | 0.6021860485 | -0.1271499386 | -0.02478998136 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | neutral_mixed | 0.1068583756 | 1.490286609 | -0.08020865716 | -0.0226712007 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | recovery_confirmed | 0.02755018149 | 0.3849731807 | -0.0535087597 | -0.02178359766 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | recovery_fragile | 0.07645485668 | 1.426833734 | -0.02629528947 | -0.01522056285 |
| track_c_track_a_plus_canary_breadth_timing_15 | track_a_blend | stressed_panic | 0.03374769103 | 0.5262244398 | -0.1012097612 | -0.01978384447 |

## 14. Multiple-Testing/Governance Summary

- Predeclared standalone sleeves tested: `6`
- Blends tested after standalone gates: `6`
- All candidates are `research_only`; no Track C output writes to the production registry.
- DSR/PSR proxy fields are included in machine-readable metrics using Track A's statistical validation helpers.

| candidate_name | candidate_kind | parent_candidate | verdict | gate_score | verdict_reason |
| --- | --- | --- | --- | --- | --- |
| track_c_residual_xsmom_top5 | standalone_sleeve | none | rejected | 7 | failed standalone sanity gate |
| track_c_vol_managed_residual_xsmom_top5 | standalone_sleeve | none | diagnostic_only | 8 | standalone sanity gate passed; eligible for small Track A overlay |
| track_c_carry_value_top5 | standalone_sleeve | none | rejected | 6 | failed standalone sanity gate |
| track_c_neutral_reversal_top5 | standalone_sleeve | none | rejected | 4 | failed standalone sanity gate |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | none | rejected | 7 | failed standalone sanity gate |
| track_c_canary_breadth_timing | standalone_sleeve | none | diagnostic_only | 8 | standalone sanity gate passed; eligible for small Track A overlay |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_05 | blend | track_c_vol_managed_residual_xsmom_top5 | diagnostic_only | 6 | some improvement but failed enough Track C watchlist gates |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_10 | blend | track_c_vol_managed_residual_xsmom_top5 | diagnostic_only | 5 | some improvement but failed enough Track C watchlist gates |
| track_c_track_a_plus_vol_managed_residual_xsmom_top5_15 | blend | track_c_vol_managed_residual_xsmom_top5 | diagnostic_only | 5 | some improvement but failed enough Track C watchlist gates |
| track_c_track_a_plus_canary_breadth_timing_05 | blend | track_c_canary_breadth_timing | diagnostic_only | 6 | some improvement but failed enough Track C watchlist gates |
| track_c_track_a_plus_canary_breadth_timing_10 | blend | track_c_canary_breadth_timing | diagnostic_only | 7 | some improvement but failed enough Track C watchlist gates |
| track_c_track_a_plus_canary_breadth_timing_15 | blend | track_c_canary_breadth_timing | diagnostic_only | 7 | some improvement but failed enough Track C watchlist gates |

## 15. Research Watchlist

_No rows._

## 16. Rejected Candidates

| candidate_name | candidate_kind | parent_candidate | verdict | gate_score | verdict_reason |
| --- | --- | --- | --- | --- | --- |
| track_c_residual_xsmom_top5 | standalone_sleeve | none | rejected | 7 | failed standalone sanity gate |
| track_c_carry_value_top5 | standalone_sleeve | none | rejected | 6 | failed standalone sanity gate |
| track_c_neutral_reversal_top5 | standalone_sleeve | none | rejected | 4 | failed standalone sanity gate |
| track_c_hyg_lqd_pair_mean_reversion | standalone_sleeve | none | rejected | 7 | failed standalone sanity gate |

## 17. What Should Be Tested Next

- No Track C candidate should be production-promoted from this sprint.
- Diagnostic follow-up, if any, should focus only on canary/breadth timing and vol-managed residual momentum because those were the only standalone sleeves to pass sanity gates.
- Revisit canary/breadth only with explicit false-defense and false-risk-on diagnostics, then require a positive blend-level beta/cash-adjusted residual before watchlisting.
- Prioritize data expansion only where point-in-time coverage is credible.

## 18. What Should Not Be Pursued

- Do not promote Track C candidates from this sprint.
- Do not turn weak carry/value or reversal results into parameter sweeps.
- Do not relabel Track B beta/cash overlays as alpha.
- Do not add ML until the experiment registry, purged validation, and trial accounting are stronger than the expected lift.

## 19. Final Verdict

Track C found diversifying sleeves, but not enough evidence for return improvement.

Machine-readable outputs are saved under `data/research/track_c_new_alpha/`.
