# Phase OOO6 Signal Portfolio Pass-Through

## Commands Executed
- `BUILD_VERSION_NAMES=improved_phaseooo6_efa_spy_selective_tilt,improved_phaseooo6_efa_spy_vol_filtered_tilt,improved_phaseooo6_efa_spy_trend_confirmed_tilt python3 scripts/build_improvement_artifacts.py`
- `python3 scripts/research_committee_report.py improved_phaseooo6_efa_spy_trend_confirmed_tilt --quick`
- `python3 scripts/backtest_realism_audit.py improved_phaseooo6_efa_spy_trend_confirmed_tilt --quick`
- `python3 scripts/allocator_benchmark_audit.py improved_phaseooo6_efa_spy_trend_confirmed_tilt --quick`

## Files Created / Modified
- `scripts/phase_ooo6_signal_portfolio_pass_through.py`
- `scripts/build_improvement_artifacts.py`
- `data/research/phase_ooo_signal_discovery/ooo6_portfolio_pass_through/`
- `docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md`
- `docs/research/project_journey.md`

## OOO3 Queue Used
| variant_name | OOO3_decision | event_count | event_frequency | selected_for_candidate |
| --- | --- | --- | --- | --- |
| efa_spy_raw_top10_event | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 84 | 0.0757 | improved_phaseooo6_efa_spy_selective_tilt |
| efa_spy_low_or_normal_vol_top20_event | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 89 | 0.0802 | none |
| efa_spy_vol_filtered_top20_event | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 109 | 0.0982 | improved_phaseooo6_efa_spy_vol_filtered_tilt |
| market_trend_breadth_confirmed_event | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 344 | 0.3099 | improved_phaseooo6_efa_spy_trend_confirmed_tilt |
| efa_spy_market_trend_confirmed_top20_event | KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH | 107 | 0.0964 | improved_phaseooo6_efa_spy_trend_confirmed_tilt |

## Candidate Logic
- OOO6-1 uses `efa_spy_raw_top10_event` for a small calm/neutral offense-family tilt.
- OOO6-2 uses `efa_spy_vol_filtered_top20_event` for a smaller volatility-filtered tilt.
- OOO6-3 requires EFA/SPY strength plus market trend/breadth confirmation.
- All candidates retain GGG1 recovery and stressed-state logic.

## Candidate Metrics
| version | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | turnover_ratio_vs_production | avg_BIL | avg_SPY |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phase2b_regime_confidence_boost | 0.0689 | 0.8848 | -0.1398 | -0.0262 | 0.0562 | 1.0000 | 0.2839 | 0.0708 |
| improved_phase2b_combo_abc | 0.0686 | 0.8840 | -0.1367 | -0.0261 | 0.0566 | 1.0061 | 0.2856 | 0.0708 |
| improved_phaseggg_confirmed_only_robust_offense | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 1.0998 | 0.2666 | 0.0603 |
| improved_phaseooo6_efa_spy_selective_tilt | 0.0714 | 0.9364 | -0.1177 | -0.0254 | 0.0619 | 1.1002 | 0.2666 | 0.0603 |
| improved_phaseooo6_efa_spy_vol_filtered_tilt | 0.0714 | 0.9368 | -0.1177 | -0.0254 | 0.0619 | 1.1002 | 0.2665 | 0.0603 |
| improved_phaseooo6_efa_spy_trend_confirmed_tilt | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.0619 | 1.1000 | 0.2665 | 0.0603 |

## Event-Active Results
| candidate | n_weeks | ann_return_delta_vs_ggg1 | mean_weekly_delta_vs_ggg1 | candidate_sharpe | ggg1_sharpe |
| --- | --- | --- | --- | --- | --- |
| improved_phaseooo6_efa_spy_selective_tilt | 84 | -0.0003 | -0.0000 | 1.4929 | 1.5024 |
| improved_phaseooo6_efa_spy_vol_filtered_tilt | 109 | 0.0001 | 0.0000 | 1.6961 | 1.6977 |
| improved_phaseooo6_efa_spy_trend_confirmed_tilt | 44 | 0.0001 | 0.0000 | 1.0464 | 1.0489 |

## Selection
| candidate | decision | delta_sharpe_vs_ggg1 | delta_ann_return_vs_ggg1 | turnover_ratio_vs_production | guard_states_preserved | hidden_beta_not_higher | event_active_improved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| improved_phaseooo6_efa_spy_selective_tilt | REJECT_KEEP_GGG1 | -0.0002 | 0.0000 | 1.1002 | True | True | False |
| improved_phaseooo6_efa_spy_vol_filtered_tilt | REJECT_KEEP_GGG1 | 0.0002 | 0.0000 | 1.1002 | True | True | True |
| improved_phaseooo6_efa_spy_trend_confirmed_tilt | KEEP_AS_SHADOW | 0.0000 | 0.0000 | 1.1000 | True | True | True |

## Audit Results
| candidate | audit | returncode | log |
| --- | --- | --- | --- |
| improved_phaseooo6_efa_spy_trend_confirmed_tilt | research_committee_quick | 0 | /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ooo_signal_discovery/ooo6_portfolio_pass_through/ooo6_research_committee_quick.log |
| improved_phaseooo6_efa_spy_trend_confirmed_tilt | backtest_realism_quick | 0 | /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ooo_signal_discovery/ooo6_portfolio_pass_through/ooo6_backtest_realism_quick.log |
| improved_phaseooo6_efa_spy_trend_confirmed_tilt | allocator_benchmark_quick | 0 | /Users/nicholasturangan/Documents/Portfolio Optimizer/data/research/phase_ooo_signal_discovery/ooo6_portfolio_pass_through/ooo6_allocator_benchmark_quick.log |

## Final Decision
`KEEP_OOO6_AS_SHADOW`

## Signal Discovery Recommendation
Do not promote automatically. Keep GGG1 unless a human review elects to shadow a qualified OOO6 candidate.

## Next Phase Prompt Outline
If OOO6 fails: review whether sleeve/factor momentum (`OOO4`) has stronger portfolio relevance than cross-asset signal pass-through. If OOO6 shadows: run full Layer 5/6 audits before any production discussion.