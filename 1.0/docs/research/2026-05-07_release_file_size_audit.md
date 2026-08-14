# Release File Size Audit — 2026-05-07

**Purpose:** Verify no committed file exceeds GitHub's 100 MB limit.

---

## Hard Stop Files (>= 100 MB) — DO NOT COMMIT

| File | Size | Status |
|---|---|---|
| `data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery/ooo1_feature_panel.csv` | 144 MB | **EXCLUDED** — over limit |
| `data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_predictions.csv` | 128 MB | **EXCLUDED** — over limit |

## Caution Files (>= 90 MB) — DO NOT COMMIT

| File | Size | Status |
|---|---|---|
| `data/research/phase_ppp_latent_factor_discovery/ppp_panel_characteristics.csv` | 96 MB | **EXCLUDED** — exceeds 90 MB threshold |
| `data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset.csv` | 80 MB | **EXCLUDED** — large regenerable ML output |

## Large Files Excluded (>= 10 MB but safe if small-file exclusion applied)

| File | Size | Decision |
|---|---|---|
| `data/research/phase_qqq_deep_feature_interaction_mining/qqq_tree_path_interaction_pairs.csv` | 44 MB | **EXCLUDED** — ML feature interaction output, regenerable |
| `data/research/phase_5a_free_current_constituent_breadth_diagnostic/phase5a_free_stock_prices_adjclose_daily.parquet` | 5.5 MB | **EXCLUDED** — raw yfinance stock prices, diagnostic only |
| `public/dashboard-data-detail-allocation.json` | 50 MB | **EXCLUDED** — not tracked; would exceed practical limit |
| `public/dashboard-data-detail-returns.json` | 33 MB | **EXCLUDED** — not tracked; large detail file |
| `public/dashboard-data-detail-weights.json` | 22 MB | **EXCLUDED** — not tracked; large detail file |
| `public/dashboard-data.json` | 15 MB | **EXCLUDED** — explicitly forbidden by CLAUDE.md |

---

## Safe Dashboard Files (tracked, small)

| File | Size | Status |
|---|---|---|
| `public/production-candidate-dashboard-bundle.json` | 1,370 KB | ✓ SAFE — updated |
| `public/dashboard-summary.json` | 32 KB | ✓ SAFE — already tracked |
| `public/dashboard-timeseries.json` | 280 KB | ✓ SAFE — already tracked |
| `public/dashboard-exposures.json` | 12 KB | ✓ SAFE — already tracked |
| `public/dashboard-state-summary.json` | 8 KB | ✓ SAFE — already tracked |

---

## Safe Research Directories (all files under 7 MB individually)

| Directory | Total Size | Max File | Status |
|---|---|---|---|
| `data/research/phase_7_allocator_objective_rewrite/` | 140 KB | <50 KB | ✓ SAFE |
| `data/research/phase_6_market_state_classifier_rebuild/` | 700 KB | <200 KB | ✓ SAFE |
| `data/research/phase_5a_pit_stock_breadth_data_scaffold/` | 72 KB | <20 KB | ✓ SAFE |
| `data/research/phase_5_true_stock_breadth_data_upgrade/` | 340 KB | <100 KB | ✓ SAFE |
| `data/research/phase_5a_free_current_constituent_breadth_diagnostic/` | 6 MB | 5.5 MB parquet | SAFE except parquet |
| `data/research/phase_4b_refined_sector_rotation/` | 3.3 MB | 1.2 MB | ✓ SAFE |
| `data/research/phase_4_sector_breadth_rotation/` | 6.2 MB | 2.3 MB | ✓ SAFE |
| `data/research/phase_3_breadth_confirmed_us_offense/` | 212 KB | <100 KB | ✓ SAFE |
| `data/research/phase_2_aggressive_etf_variant/` | 152 KB | <50 KB | ✓ SAFE |
| `data/research/phase_ooo_signal_discovery/ooo2_*/` | ~600 KB | 204 KB | ✓ SAFE |
| `data/research/phase_ooo_signal_discovery/ooo3_*/` | ~6 MB | 4.6 MB | ✓ SAFE |
| `data/research/phase_ooo_signal_discovery/ooo5_*/` | ~12 MB | 6.0 MB | ✓ SAFE |
| `data/research/phase_sss_regime_sequence_modeling/` | 18 MB | 6.7 MB | ✓ SAFE |
| `data/research/phase_sss2_sequence_signal_validation/` | 1.3 MB | 500 KB | ✓ SAFE |
| `data/stock_breadth/` | 28 KB | <10 KB | ✓ SAFE |

---

## PPP/QQQ — Partial commit (safe files only)

**PPP safe files** (excluding 96 MB `ppp_panel_characteristics.csv`):
- All other PPP files are 6 MB or under — safe

**QQQ safe files** (excluding 128 MB, 80 MB, 44 MB files):
- Remaining files: `qqq_redundancy_summary.csv` (1.7 MB), `qqq_interaction_importance.csv` (2.7 MB), `qqq_ml_dataset_sample.csv` (2.9 MB), `qqq_feature_importance.csv` (4.9 MB), `qqq_rule_event_overlap.csv` (416 KB), `qqq_state_specific_rules.csv` (108 KB), `qqq_rejected_interaction_log.csv` (80 KB) — all safe

---

## Conclusion

All files intended for commit are verified below 90 MB individually. Hard stop files are explicitly excluded from the staging plan.
