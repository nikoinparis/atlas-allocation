# Phase OOO0 — Signal/Data Inventory and Discovery Foundation

Date: 2026-04-27

## Commands executed
```
sed -n '1,180p' docs/research/2026-04-27_phase_nnn_hard_ml_meta_layer_report.md
sed -n '1,120p' docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md
find data/01_data_hub data/02_layer1_signals data/03_layer2a_strategy_logic data/04_layer2b_risk_regime_engine -maxdepth 1 -type f | sort
python3 scripts/phase_ooo0_ooo1_signal_discovery_foundation.py
```

## Files created / modified
- `scripts/phase_ooo0_ooo1_signal_discovery_foundation.py`
- `data/research/phase_ooo_signal_discovery/ooo0_inventory/*.csv`
- `docs/research/2026-04-27_phase_ooo0_signal_data_inventory_report.md`
- `docs/research/project_journey.md`

## Available data inventory
| file_path | category | row_count | column_count | start_date | end_date | frequency | recommended_use |
| --- | --- | --- | --- | --- | --- | --- | --- |
| data/01_data_hub/01_google_trends.png | data_hub |  |  | None | None | unknown |  |
| data/01_data_hub/01_price_sanity_check.png | data_hub |  |  | None | None | unknown |  |
| data/01_data_hub/01_vix_term_structure.png | data_hub |  |  | None | None | unknown |  |
| data/01_data_hub/benchmark_prices_weekly.csv | data_hub | 1110.000000 | 13.000000 | 2005-01-07 | 2026-04-10 | weekly |  |
| data/01_data_hub/benchmark_returns_weekly.csv | data_hub | 1109.000000 | 13.000000 | 2005-01-14 | 2026-04-10 | weekly |  |
| data/01_data_hub/benchmarks.csv | data_hub | 12.000000 | 4.000000 | None | None | unknown |  |
| data/01_data_hub/daily_prices.csv | data_hub | 5353.000000 | 36.000000 | 2005-01-03 | 2024-11-12 | daily |  |
| data/01_data_hub/daily_returns.csv | data_hub | 5352.000000 | 36.000000 | 2005-01-04 | 2024-11-13 | daily |  |
| data/01_data_hub/data_quality_report.csv | data_hub | 35.000000 | 10.000000 | None | None | unknown |  |
| data/01_data_hub/etf_distribution_history.csv | data_hub | 3741.000000 | 5.000000 | 1993-03-19 | 2026-04-01 | irregular |  |
| data/01_data_hub/google_trends.csv | data_hub | 1110.000000 | 11.000000 | 2005-01-07 | 2026-04-10 | weekly |  |
| data/01_data_hub/google_trends_raw.csv | data_hub | 1109.000000 | 5.000000 | 2005-01-07 | 2026-04-03 | weekly |  |
| data/01_data_hub/google_trends_snapshot_meta.json | data_hub | 8.000000 |  | None | None | unknown |  |
| data/01_data_hub/macro_weekly.csv | data_hub | 1110.000000 | 1.000000 | 2005-01-07 | 2026-04-10 | weekly |  |
| data/01_data_hub/market_proxy_weekly.csv | data_hub | 1110.000000 | 3.000000 | 2005-01-07 | 2026-04-10 | weekly |  |

## Existing signal inventory
| file_path | row_count | column_count | frequency | recommended_use |
| --- | --- | --- | --- | --- |
| data/02_layer1_signals/phase_a_incremental_diagnostics.csv | 4.000000 | 4.000000 | unknown | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/phase_a_signal_candidate_summary.csv | 4.000000 | 16.000000 | unknown | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/phase_a_signal_state_summary.csv | 24.000000 | 7.000000 | unknown | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/phase_a_stability_summary.csv | 8.000000 | 6.000000 | unknown | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/regime_features.csv | 1110.000000 | 13.000000 | weekly | state interactions and state-quality targets |
| data/02_layer1_signals/signal_bab.csv | 38850.000000 | 10.000000 | daily | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/signal_breadth_confirmation.csv | 38850.000000 | 10.000000 | daily | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/signal_carry.csv | 38850.000000 | 12.000000 | daily | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/signal_contained_recovery.csv | 38850.000000 | 11.000000 | daily | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/signal_eligibility_matrix.csv | 25.000000 | 10.000000 | unknown | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/signal_ic_by_horizon.csv | 110.000000 | 11.000000 | unknown | Layer 1 signal validation or live signal feature source |
| data/02_layer1_signals/signal_incremental_contribution.csv | 10.000000 | 35.000000 | unknown | Layer 1 signal validation or live signal feature source |

## Existing sleeve inventory
| file_path | row_count | column_count | frequency | recommended_use |
| --- | --- | --- | --- | --- |
| data/03_layer2a_strategy_logic/layer2_manifest.json | 24.000000 |  | unknown |  |
| data/03_layer2a_strategy_logic/phase_b_sleeve_candidate_summary.csv | 3.000000 | 14.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_b_sleeve_correlation.csv | 15.000000 | 3.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_b_sleeve_state_summary.csv | 15.000000 | 11.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_current_sleeve_correlation.csv | 15.000000 | 3.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_current_sleeve_role_summary.csv | 6.000000 | 8.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_current_sleeve_state_summary.csv | 30.000000 | 10.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_panel_blend_holdout_summary.csv | 2.000000 | 5.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_panel_blend_state_summary.csv | 10.000000 | 5.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_panel_blend_summary.csv | 2.000000 | 6.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_redesigned_sleeve_correlation.csv | 18.000000 | 3.000000 | unknown |  |
| data/03_layer2a_strategy_logic/phase_f_redesigned_sleeve_holdout_summary.csv | 3.000000 | 9.000000 | unknown |  |

## Missing data / instrumentation
| missing_item | recommendation | severity |
| --- | --- | --- |
| explicit signal-to-sleeve lineage by date | Persist a dated Layer2A signal_usage_by_sleeve table. | MEDIUM |
| IPCA/latent factor panel | Reserve for OOO6 after feature shortlist stabilizes. | LOW |
| per-signal live transaction cost sensitivity | Add only when OOO2 creates concrete candidate signals. | LOW |

## OOO1 readiness
Enough data exists to run OOO1: weekly ETF returns/prices, Layer 1 signal
panels, IC/redundancy files, Layer 2A sleeves, regime states, GGG1 artifacts,
component panels, and prior NNN ML outputs are present.
