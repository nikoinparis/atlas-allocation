# Release Staging Plan — 2026-05-07

**Purpose:** Explicit list of files to stage per commit, with safety rules.

---

## Safety Pre-Checks

Before any `git add`:
- [x] No file >= 100 MB in any staged group
- [x] No raw stock price panels (only templates in data/stock_breadth/raw/)
- [x] No `.venv`, `node_modules`, `.DS_Store`, `__pycache__`
- [x] No `public/dashboard-data.json` (forbidden by CLAUDE.md)
- [x] No `public/dashboard-data-detail-*.json`
- [x] No `.claude/settings.local.json`
- [x] Large files explicitly excluded from PPP/QQQ/Phase5AFree (parquet)

---

## Commit 1: Research outputs (Phases 2–7 + signal discovery backlog)

### Scripts
- `scripts/build_improvement_artifacts.py` (modified)
- `scripts/phase_2_aggressive_etf_variant.py`
- `scripts/phase_3_breadth_confirmed_us_offense.py`
- `scripts/phase_4_sector_breadth_rotation.py`
- `scripts/phase_4b_refined_sector_rotation.py`
- `scripts/phase_5_true_stock_breadth_data_upgrade.py`
- `scripts/phase_5a_free_current_constituent_breadth_diagnostic.py`
- `scripts/phase_5a_pit_stock_breadth_data_scaffold.py`
- `scripts/phase_6_market_state_classifier_rebuild.py`
- `scripts/phase_7_allocator_objective_rewrite.py`
- `scripts/build_pit_stock_breadth_panel.py`
- `scripts/phase_ooo2_cross_asset_signal_expansion.py`
- `scripts/phase_ooo3_vol_managed_signal_sizing.py`
- `scripts/phase_ooo5_triple_barrier_signal_validation.py`
- `scripts/phase_ppp_latent_factor_discovery.py`
- `scripts/phase_qqq_deep_feature_interaction_mining.py`
- `scripts/phase_sss_regime_sequence_modeling.py`
- `scripts/phase_sss2_sequence_signal_validation.py`

### Research data directories (all safe)
- `data/research/phase_7_allocator_objective_rewrite/` (140 KB, 24 files)
- `data/research/phase_6_market_state_classifier_rebuild/` (700 KB)
- `data/research/phase_5a_pit_stock_breadth_data_scaffold/` (72 KB)
- `data/research/phase_5_true_stock_breadth_data_upgrade/` (340 KB)
- `data/research/phase_4b_refined_sector_rotation/` (3.3 MB)
- `data/research/phase_4_sector_breadth_rotation/` (6.2 MB)
- `data/research/phase_3_breadth_confirmed_us_offense/` (212 KB)
- `data/research/phase_2_aggressive_etf_variant/` (152 KB)
- `data/research/phase_ooo_signal_discovery/ooo2_cross_asset_signal_expansion/` (~600 KB)
- `data/research/phase_ooo_signal_discovery/ooo3_vol_managed_signal_sizing/` (~6 MB)
- `data/research/phase_ooo_signal_discovery/ooo5_triple_barrier_validation/` (~12 MB)
- `data/research/phase_sss_regime_sequence_modeling/` (18 MB, max file 6.7 MB)
- `data/research/phase_sss2_sequence_signal_validation/` (1.3 MB)
- `data/stock_breadth/` (28 KB, templates only)

### Phase 5A-Free (with parquet EXCLUDED)
- `data/research/phase_5a_free_current_constituent_breadth_diagnostic/`
  THEN: `git restore --staged ...phase5a_free_stock_prices_adjclose_daily.parquet`

### PPP (with large file EXCLUDED)
- `data/research/phase_ppp_latent_factor_discovery/`
  THEN: `git restore --staged ...ppp_panel_characteristics.csv`

### QQQ (with 3 large files EXCLUDED)
- `data/research/phase_qqq_deep_feature_interaction_mining/`
  THEN restore: `qqq_model_predictions.csv`, `qqq_ml_dataset.csv`, `qqq_tree_path_interaction_pairs.csv`

### Audit reports
- `reports/allocator_benchmark/` (6 files)
- `reports/backtest_realism/` (6 files)
- `reports/research_committee/` (6 files)
- `data/research/allocator_benchmark/` (12 CSV files)
- `data/research/backtest_realism/` (18 CSV files)

### Portfolio construction CSVs (returns/weights/sleeve_weights for Phases 2–7)
- Phase 7: 15 CSVs (5 × 3 types)
- Phase 6: 15 CSVs
- Phase 4B: 15 CSVs
- Phase 4: 18 CSVs
- Phase 3: 18 CSVs
- Phase 2: 18 CSVs
- Modified layer3 driver/defense/diagnostics CSVs (7 files)

---

## Commit 2: Dashboard update

- `public/production-candidate-dashboard-bundle.json` (updated, 1.37 MB)
- `src/components/executive-summary.tsx` (updated narrative)
- `src/lib/compact-dashboard.ts` (TypeScript type fix)
- `src/types/dashboard.ts` (ReturnPoint.method optional)
- `scripts/build_release_dashboard_bundle.py` (new)

---

## Commit 3: Documentation + project journey

- `docs/research/project_journey.md` (Phase 7 Section 102 added)
- `docs/research/2026-05-07_phase_7_allocator_objective_rewrite_report.md`
- `docs/research/2026-05-07_phase_6_market_state_classifier_rebuild_report.md`
- `docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md`
- `docs/research/2026-05-07_phase_4_sector_breadth_rotation_report.md`
- `docs/research/2026-05-07_phase_3_breadth_confirmed_us_offense_report.md`
- `docs/research/2026-05-07_phase_2_aggressive_etf_variant_report.md`
- `docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md`
- `docs/research/2026-05-07_phase_5a_free_current_constituent_breadth_diagnostic_report.md`
- `docs/research/2026-05-07_phase_5a_pit_stock_breadth_data_scaffold_report.md`
- `docs/research/2026-04-27_phase_ooo2_cross_asset_signal_expansion_report.md`
- `docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md`
- `docs/research/2026-04-27_phase_ooo5_triple_barrier_signal_validation_report.md`
- `docs/research/2026-04-27_phase_ppp_latent_factor_discovery_report.md`
- `docs/research/2026-04-27_phase_qqq_deep_feature_interaction_mining_report.md`
- `docs/research/2026-04-27_phase_sss_regime_sequence_modeling_report.md`
- `docs/research/2026-04-27_phase_sss2_sequence_signal_validation_report.md`
- `docs/research/2026-05-07_release_packaging_audit.md`
- `docs/research/2026-05-07_release_file_size_audit.md`
- `docs/research/2026-05-07_dashboard_release_audit.md`
- `docs/research/2026-05-07_release_validation_report.md`
- `docs/research/2026-05-07_release_staging_plan.md`
- `docs/research/2026-05-07_final_release_report.md` (written after commits)

---

## DO NOT STAGE

- `data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery/ooo1_feature_panel.csv` — 144 MB hard stop
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_predictions.csv` — 128 MB hard stop
- `data/research/phase_ppp_latent_factor_discovery/ppp_panel_characteristics.csv` — 96 MB caution
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset.csv` — 80 MB
- `data/research/phase_qqq_deep_feature_interaction_mining/qqq_tree_path_interaction_pairs.csv` — 44 MB
- `data/research/phase_5a_free_current_constituent_breadth_diagnostic/phase5a_free_stock_prices_adjclose_daily.parquet`
- `public/dashboard-data.json` — forbidden
- `public/dashboard-data-detail-*.json` — too large
- `.claude/settings.local.json` — local config
- `.venv/` — local virtualenv
- `node_modules/` — not present, but if ever added: do not stage
