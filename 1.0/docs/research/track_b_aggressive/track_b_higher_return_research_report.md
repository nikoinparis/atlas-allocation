# Track B Higher-Return Research Report

## 1. Track B Mandate

Research-only sprint to test whether the ETF system can reach 9-10%+ annualized return by accepting more offense exposure, higher equity beta, lower BIL/cash, and larger drawdown tolerance. No Track B result is production-ready.

## 2. Track A Baseline Summary

Track A production remains `improved_frontier_phase5_fragility_guard`. It is the conservative, auditable baseline and was not modified by Track B.

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | holdout_sharpe | avg_weekly_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_a_production | 0.07134169432 | 0.9482556438 | -0.1160345789 | 0.6148313289 | -0.02494792886 | 0.2760603192 | 0.2949097764 | 0.2402307405 | 2.178585179 | 0.06738780266 |

## 3. Benchmark Comparison

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | holdout_sharpe | avg_weekly_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_a_production | 0.07134169432 | 0.9482556438 | -0.1160345789 | 0.6148313289 | -0.02494792886 | 0.2760603192 | 0.2949097764 | 0.2402307405 | 2.178585179 | 0.06738780266 |
| spy_buy_hold | 0.1053309083 | 0.5996349785 | -0.5461301945 | 0.1928677619 | -0.0580042681 | 0 | 1 | 1 | 1.219906078 | 0 |
| static_60_spy_40_ief | 0.0808715342 | 0.7845698297 | -0.3138361945 | 0.2576870853 | -0.03273141716 | 0 | 0.6 | 0.569015337 | 1.484958316 | 0 |
| static_80_spy_20_bil | 0.08872865466 | 0.6319156495 | -0.4584235979 | 0.1935516737 | -0.04633090118 | 0.2 | 0.8 | 0.799338497 | 1.296778084 | 0 |
| aggressive_taa_spy_trend | 0.09237202193 | 0.7368644892 | -0.3624634652 | 0.2548450556 | -0.04069558701 | 0.1653153153 | 0.8346846847 | 0.6719788291 | 1.542338 | 0.04147880974 |
| dual_momentum_top1 | 0.05619201476 | 0.3078510185 | -0.3964845068 | 0.1417256256 | -0.05786057138 | 0.05135135135 | 0.6027027027 | 0.3380573284 | 1.070313971 | 0.1992786294 |
| static_global_growth_90_10 | 0.1049740919 | 0.6401647047 | -0.4987412313 | 0.2104780702 | -0.05380554386 | 0.05 | 0.9 | 0.9204453864 | 1.405214474 | 0 |

## 4. Predeclared Experiment Grid

See `docs/research/track_b_aggressive/track_b_predeclared_experiment_plan.md`. The implemented grid has exactly `12` candidates.

## 5. Candidate Results Table

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | holdout_sharpe | avg_weekly_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_b_aggressive_cash_cap_20 | 0.07369069231 | 0.9118445231 | -0.1160934973 | 0.6347529711 | -0.02675292906 | 0.2000953764 | 0.3638658714 | 0.2714878956 | 2.214742914 | 0.07198150288 |
| track_b_aggressive_cash_cap_15_good_20_neutral | 0.07409003783 | 0.9123785457 | -0.1160934973 | 0.6381928323 | -0.02690448655 | 0.196137779 | 0.3672367823 | 0.2728141525 | 2.214742914 | 0.07250047748 |
| track_b_aggressive_cash_cap_10_good_18_neutral | 0.07452793345 | 0.9073571546 | -0.1161124721 | 0.6418598458 | -0.02724743021 | 0.1871052164 | 0.3744195973 | 0.2765881704 | 2.216032707 | 0.07335890243 |
| track_b_aggressive_offense_boost_10 | 0.07264821139 | 0.9348476182 | -0.1180156306 | 0.6155812666 | -0.02593993562 | 0.2544018004 | 0.3123147883 | 0.2505069091 | 2.128986118 | 0.06858805106 |
| track_b_aggressive_offense_boost_20 | 0.07363331165 | 0.9269113642 | -0.1201605336 | 0.6127911509 | -0.0265866469 | 0.2412721641 | 0.3253853404 | 0.2583638269 | 2.095020259 | 0.06942433791 |
| track_b_aggressive_cash10_offense10 | 0.07594667887 | 0.8909017169 | -0.1183566377 | 0.6416765493 | -0.02845792406 | 0.1599694713 | 0.396713901 | 0.2890857516 | 2.166849121 | 0.07604929473 |
| track_b_aggressive_cash10_offense20 | 0.07669464185 | 0.8792114176 | -0.1205316727 | 0.6363028084 | -0.02923111626 | 0.1453834937 | 0.4116846616 | 0.2979568852 | 2.131746929 | 0.07742967997 |
| track_b_aggressive_rerisk_4w | 0.06490017463 | 0.8327045651 | -0.1163418114 | 0.5578405035 | -0.02658231018 | 0.2540474985 | 0.3083964117 | 0.2566478682 | 2.236446513 | 0.07930215518 |
| track_b_aggressive_vol_throttled | 0.07691206044 | 0.8836320265 | -0.1203604581 | 0.6390143547 | -0.02910000494 | 0.1464311446 | 0.4112304978 | 0.2967569389 | 2.128648933 | 0.07701183312 |
| track_b_aggressive_turnover_banded | 0.07648655446 | 0.8975568661 | -0.117330524 | 0.651889652 | -0.02841836962 | 0.1598860974 | 0.3967806793 | 0.2895637917 | 2.17592512 | 0.07177415556 |
| track_b_aggressive_blend_static_growth_30 | 0.08335237019 | 0.9139925657 | -0.1963630961 | 0.4244808309 | -0.02924029616 | 0.2082422234 | 0.4764368435 | 0.4442951343 | 2.020749784 | 0.04717146186 |
| track_b_aggressive_blend_static_growth_50 | 0.09046267167 | 0.830827939 | -0.2926592421 | 0.3091058086 | -0.03518091804 | 0.1630301596 | 0.5974548882 | 0.5803380634 | 1.838482595 | 0.03369390133 |

## 6. Best Candidates

| name | ann_return | sharpe | max_drawdown | calmar | cvar_5 | avg_BIL | avg_equity | spy_beta | holdout_sharpe | avg_weekly_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_b_aggressive_blend_static_growth_50 | 0.09046267167 | 0.830827939 | -0.2926592421 | 0.3091058086 | -0.03518091804 | 0.1630301596 | 0.5974548882 | 0.5803380634 | 1.838482595 | 0.03369390133 |
| track_b_aggressive_blend_static_growth_30 | 0.08335237019 | 0.9139925657 | -0.1963630961 | 0.4244808309 | -0.02924029616 | 0.2082422234 | 0.4764368435 | 0.4442951343 | 2.020749784 | 0.04717146186 |
| track_b_aggressive_vol_throttled | 0.07691206044 | 0.8836320265 | -0.1203604581 | 0.6390143547 | -0.02910000494 | 0.1464311446 | 0.4112304978 | 0.2967569389 | 2.128648933 | 0.07701183312 |
| track_b_aggressive_cash10_offense20 | 0.07669464185 | 0.8792114176 | -0.1205316727 | 0.6363028084 | -0.02923111626 | 0.1453834937 | 0.4116846616 | 0.2979568852 | 2.131746929 | 0.07742967997 |
| track_b_aggressive_turnover_banded | 0.07648655446 | 0.8975568661 | -0.117330524 | 0.651889652 | -0.02841836962 | 0.1598860974 | 0.3967806793 | 0.2895637917 | 2.17592512 | 0.07177415556 |

## 7. Research-Only Watchlist And Rejected Candidates

The watchlist is not a production shortlist. It contains candidates with at least 50 bps annual return improvement or 9%+ return plus enough risk/cost gates to justify forward paper tracking.

| name | gate_score | mandate_9_10_met | track_b_shortlist | shortlist_reason |
| --- | --- | --- | --- | --- |
| track_b_aggressive_cash10_offense20 | 9 | False | True | research_only_shortlist |
| track_b_aggressive_vol_throttled | 9 | False | True | research_only_shortlist |
| track_b_aggressive_turnover_banded | 9 | False | True | research_only_shortlist |
| track_b_aggressive_blend_static_growth_30 | 8 | False | True | research_only_shortlist |

Rejected or diagnostic-only candidates:

| name | gate_score | shortlist_reason | return_ge_9 | drawdown_ge_minus_22 | sharpe_ge_085 |
| --- | --- | --- | --- | --- | --- |
| track_b_aggressive_cash_cap_20 | 8 | reject_or_diagnostic | False | True | True |
| track_b_aggressive_cash_cap_15_good_20_neutral | 8 | reject_or_diagnostic | False | True | True |
| track_b_aggressive_cash_cap_10_good_18_neutral | 8 | reject_or_diagnostic | False | True | True |
| track_b_aggressive_offense_boost_10 | 7 | reject_or_diagnostic | False | True | True |
| track_b_aggressive_offense_boost_20 | 7 | reject_or_diagnostic | False | True | True |
| track_b_aggressive_cash10_offense10 | 8 | reject_or_diagnostic | False | True | True |
| track_b_aggressive_rerisk_4w | 5 | reject_or_diagnostic | False | True | False |
| track_b_aggressive_blend_static_growth_50 | 4 | reject_or_diagnostic | True | False | False |

## 8. Risk Diagnostics

Track B candidates are judged with max drawdown, weekly CVaR 5%, annualized volatility, Calmar, state metrics, and stress-state behavior. Higher return is not accepted without naming the risk paid for it.

## 9. Cost Sensitivity

| name | kind | ann_return | sharpe | max_drawdown | cvar_5 | annualized_cost |
| --- | --- | --- | --- | --- | --- | --- |
| spy_buy_hold | benchmark | 0.1053309083 | 0.5996349785 | -0.5461301945 | -0.0580042681 | 0 |
| static_global_growth_90_10 | benchmark | 0.1049740919 | 0.6401647047 | -0.4987412313 | -0.05380554386 | 0 |
| aggressive_taa_spy_trend | benchmark | 0.09001728412 | 0.7177879056 | -0.3653301434 | -0.04077594415 | 0.00430990991 |
| static_80_spy_20_bil | benchmark | 0.08872865466 | 0.6319156495 | -0.4584235979 | -0.04633090118 | 0 |
| static_60_spy_40_ief | benchmark | 0.0808715342 | 0.7845698297 | -0.3138361945 | -0.03273141716 | 0 |
| track_a_production | benchmark | 0.06760219773 | 0.8985816015 | -0.1160692953 | -0.02504028716 | 0.007002017664 |
| dual_momentum_top1 | benchmark | 0.04530435611 | 0.2480802316 | -0.4601398224 | -0.05807847171 | 0.02070630631 |
| track_b_aggressive_blend_static_growth_50 | candidate | 0.0885576527 | 0.8132876403 | -0.2941165314 | -0.03521830199 | 0.003501008832 |
| track_b_aggressive_blend_static_growth_30 | candidate | 0.08070384429 | 0.8848985101 | -0.1986068094 | -0.02930022181 | 0.004901412365 |
| track_b_aggressive_vol_throttled | candidate | 0.07261302333 | 0.8337922442 | -0.1209420011 | -0.02922073481 | 0.008002015122 |
| track_b_aggressive_turnover_banded | candidate | 0.07248036255 | 0.8500410722 | -0.1179212477 | -0.02853713236 | 0.007457787392 |
| track_b_aggressive_cash10_offense20 | candidate | 0.07237247242 | 0.8291477125 | -0.1211443053 | -0.0293555755 | 0.008045432044 |
| track_b_aggressive_cash10_offense10 | candidate | 0.07170454126 | 0.8406233784 | -0.1189651585 | -0.02858064257 | 0.007902001313 |
| track_b_aggressive_cash_cap_10_good_18_neutral | candidate | 0.07044117752 | 0.8570859501 | -0.1162250803 | -0.02736451787 | 0.007622452586 |
| track_b_aggressive_cash_cap_15_good_20_neutral | candidate | 0.07005291296 | 0.8621710366 | -0.1161871309 | -0.02701840469 | 0.007533256821 |
| track_b_aggressive_offense_boost_20 | candidate | 0.06977320301 | 0.878388655 | -0.1207221151 | -0.02667535964 | 0.00721362652 |
| track_b_aggressive_cash_cap_20 | candidate | 0.06968387903 | 0.8617711859 | -0.1161871309 | -0.02686567718 | 0.007479332087 |
| track_b_aggressive_offense_boost_10 | candidate | 0.06883787324 | 0.8858743338 | -0.1185894082 | -0.02602818723 | 0.007126731042 |
| track_b_aggressive_rerisk_4w | candidate | 0.06052209217 | 0.7760129985 | -0.1225971882 | -0.02671785158 | 0.008239994026 |

## 10. Drawdown/CVaR Comparison

| name | ann_return | max_drawdown | cvar_5 | calmar | ann_vol |
| --- | --- | --- | --- | --- | --- |
| track_b_aggressive_blend_static_growth_50 | 0.09046267167 | -0.2926592421 | -0.03518091804 | 0.3091058086 | 0.1088825585 |
| track_b_aggressive_blend_static_growth_30 | 0.08335237019 | -0.1963630961 | -0.02924029616 | 0.4244808309 | 0.09119589515 |
| track_b_aggressive_vol_throttled | 0.07691206044 | -0.1203604581 | -0.02910000494 | 0.6390143547 | 0.08704082484 |
| track_b_aggressive_cash10_offense20 | 0.07669464185 | -0.1205316727 | -0.02923111626 | 0.6363028084 | 0.08723117138 |
| track_b_aggressive_turnover_banded | 0.07648655446 | -0.117330524 | -0.02841836962 | 0.651889652 | 0.08521638834 |
| track_b_aggressive_cash10_offense10 | 0.07594667887 | -0.1183566377 | -0.02845792406 | 0.6416765493 | 0.08524697778 |
| track_b_aggressive_cash_cap_10_good_18_neutral | 0.07452793345 | -0.1161124721 | -0.02724743021 | 0.6418598458 | 0.08213737344 |
| track_b_aggressive_cash_cap_15_good_20_neutral | 0.07409003783 | -0.1160934973 | -0.02690448655 | 0.6381928323 | 0.08120537048 |
| track_b_aggressive_cash_cap_20 | 0.07369069231 | -0.1160934973 | -0.02675292906 | 0.6347529711 | 0.08081497497 |
| track_b_aggressive_offense_boost_20 | 0.07363331165 | -0.1201605336 | -0.0265866469 | 0.6127911509 | 0.07943943131 |
| track_b_aggressive_offense_boost_10 | 0.07264821139 | -0.1180156306 | -0.02593993562 | 0.6155812666 | 0.07771128681 |
| track_b_aggressive_rerisk_4w | 0.06490017463 | -0.1163418114 | -0.02658231018 | 0.5578405035 | 0.07793901625 |

## 11. State-By-State Behavior

| name | kind | ann_return | sharpe | max_drawdown | cvar_5 |
| --- | --- | --- | --- | --- | --- |
| static_global_growth_90_10 | benchmark | 0.09612162088 | 0.370324867 | -0.401075179 | -0.08398873729 |
| spy_buy_hold | benchmark | 0.0771581232 | 0.2694762488 | -0.4509917473 | -0.09188485161 |
| static_60_spy_40_ief | benchmark | 0.07500313928 | 0.4408200474 | -0.2647892114 | -0.05264409622 |
| static_80_spy_20_bil | benchmark | 0.07145080763 | 0.312333607 | -0.3705115199 | -0.0734185973 |
| aggressive_taa_spy_trend | benchmark | 0.04008896531 | 0.2568635313 | -0.2818604157 | -0.05103554876 |
| track_a_production | benchmark | 0.03569658384 | 0.4792829659 | -0.1216372804 | -0.02312386413 |
| dual_momentum_top1 | benchmark | 0.01122130905 | 0.05203754544 | -0.281174166 | -0.06908995705 |
| track_b_aggressive_blend_static_growth_50 | candidate | 0.0722287586 | 0.4663466066 | -0.2297644074 | -0.0502025823 |
| track_b_aggressive_blend_static_growth_30 | candidate | 0.0590588849 | 0.5060735655 | -0.1576231452 | -0.03778906799 |
| track_b_aggressive_turnover_banded | candidate | 0.03596098564 | 0.4832561852 | -0.1195323214 | -0.02313112916 |
| track_b_aggressive_offense_boost_10 | candidate | 0.03564836656 | 0.4786436621 | -0.1216492906 | -0.02312791872 |
| track_b_aggressive_offense_boost_20 | candidate | 0.03556738549 | 0.4775685705 | -0.1216748667 | -0.02313197314 |
| track_b_aggressive_cash_cap_20 | candidate | 0.03493374919 | 0.4687877287 | -0.1216958254 | -0.02312903925 |
| track_b_aggressive_cash_cap_15_good_20_neutral | candidate | 0.03493374919 | 0.4687877287 | -0.1216958254 | -0.02312903925 |
| track_b_aggressive_cash_cap_10_good_18_neutral | candidate | 0.03486915048 | 0.4678874661 | -0.1217239859 | -0.02313223854 |
| track_b_aggressive_cash10_offense10 | candidate | 0.0347450516 | 0.4661870034 | -0.121770134 | -0.02313937254 |
| track_b_aggressive_rerisk_4w | candidate | 0.034722063 | 0.4662036068 | -0.1216372804 | -0.02313254026 |
| track_b_aggressive_vol_throttled | candidate | 0.03465942384 | 0.4650862034 | -0.1217604006 | -0.02314034255 |
| track_b_aggressive_cash10_offense20 | candidate | 0.03460086063 | 0.4642323804 | -0.1218162809 | -0.02314528249 |

## 12. Beta And Attribution Analysis

| name | ann_return | delta_ann_return_vs_track_a | spy_beta | delta_spy_beta_vs_track_a | avg_BIL | cash_drag_reduction_est_ann | beta_explained_return_est_ann | residual_return_vs_track_a_est_ann | return_source_label |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| track_b_aggressive_blend_static_growth_50 | 0.09046267167 | 0.01912097736 | 0.5803380634 | 0.3401073229 | 0.1630301596 | 0.01057219384 | 0.0318116913 | -0.01269071394 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_blend_static_growth_30 | 0.08335237019 | 0.01201067587 | 0.4442951343 | 0.2040643938 | 0.2082422234 | 0.006343316303 | 0.01908701478 | -0.007076338906 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_vol_throttled | 0.07691206044 | 0.005570366119 | 0.2967569389 | 0.05652619846 | 0.1464311446 | 0.01212477064 | 0.005287136896 | 0.0002832292232 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_cash10_offense20 | 0.07669464185 | 0.005352947534 | 0.2979568852 | 0.05772614468 | 0.1453834937 | 0.01222276191 | 0.005399372994 | -4.642545969e-05 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_turnover_banded | 0.07648655446 | 0.005144860145 | 0.2895637917 | 0.04933305123 | 0.1598860974 | 0.01086627141 | 0.004614331096 | 0.0005305290489 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_cash10_offense10 | 0.07594667887 | 0.00460498455 | 0.2890857516 | 0.0488550111 | 0.1599694713 | 0.01085847309 | 0.004569617961 | 3.536658944e-05 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_cash_cap_10_good_18_neutral | 0.07452793345 | 0.003186239134 | 0.2765881704 | 0.03635742993 | 0.1871052164 | 0.008320350897 | 0.003400665788 | -0.0002144266543 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_cash_cap_15_good_20_neutral | 0.07409003783 | 0.002748343507 | 0.2728141525 | 0.03258341205 | 0.196137779 | 0.007475496718 | 0.003047665768 | -0.000299322261 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_cash_cap_20 | 0.07369069231 | 0.00234899799 | 0.2714878956 | 0.03125715515 | 0.2000953764 | 0.007105325722 | 0.002923615293 | -0.0005746173027 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_offense_boost_20 | 0.07363331165 | 0.002291617333 | 0.2583638269 | 0.01813308646 | 0.2412721641 | 0.003253884802 | 0.001696065065 | 0.0005955522682 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_offense_boost_10 | 0.07264821139 | 0.001306517067 | 0.2505069091 | 0.01027616858 | 0.2544018004 | 0.002025813813 | 0.0009611739604 | 0.000345343107 | mostly_higher_beta_or_cash_drag |
| track_b_aggressive_rerisk_4w | 0.06490017463 | -0.006441519688 | 0.2566478682 | 0.01641712772 | 0.2540474985 | 0.002058953186 | 0.001535564111 | -0.0079770838 | no_return_improvement |

## 13. Is 9-10% Annual Return Realistic?

No tested candidate met the full 9-10% mandate with the risk gates intact. The highest-return candidate was `track_b_aggressive_blend_static_growth_50` at 9.05% CAGR, but it had Sharpe 0.831, max drawdown -29.27%, and Calmar 0.309. Full mandate hits: 0.

## 14. Genuine Improvement Or Mostly Higher Beta?

The attribution labels show that incremental return is largely explainable by higher SPY beta and lower BIL/cash drag. The Track B watchlist is therefore useful as a risk-budget reference, not evidence of a new edge.

## 15. What Should Be Tested Next

- Forward paper tracking only for candidates that cleared the tightened research-only shortlist.
- Stability of beta-adjusted residual return using a longer live-style paper window.
- Turnover-band sensitivity around the predeclared 5% band only if the banded candidate remains competitive in paper tracking.

## 16. What Should Not Be Pursued

- Larger parameter sweeps.
- ML overlays.
- Crisis-specific handcrafted rules.
- Any production-promotion narrative without a forward paper window.

## 17. Final Verdict

Track B produced higher returns, but mostly by taking more beta/risk.
