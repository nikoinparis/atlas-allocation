# Release Packaging Audit — 2026-05-07

**Purpose:** Pre-release state audit before packaging Phase 2–7 research and dashboard update.

---

## Repo State

- **Branch:** main
- **Worktrees:** main (`f10c3601`) + `.claude/worktrees/objective-dubinsky-1d724a` (existing research worktree, not touched)
- **Latest commits at audit time:**
  ```
  f10c3601 Add SSS3 shadow and OOO6 shadow candidate artifacts, scripts, and reports
  042d07f8 Add Phase 1 Return Unlock Audit script, outputs, and report
  dd37f2e8 Update project journey and layer3 diagnostic timeseries post-SSS3 Phase1
  461d3c37 Add SSS3 sequence portfolio pass-through research
  bc899b8b Document regenerable OOO signal discovery artifacts
  ```

---

## Required File Verification

| File | Exists |
|---|---|
| `docs/research/2026-05-07_phase_7_allocator_objective_rewrite_report.md` | ✓ |
| `data/research/phase_7_allocator_objective_rewrite/` (24 files) | ✓ |
| `portfolio_version_returns_improved_phase7_stretch_target.csv` | ✓ |
| `portfolio_version_weights_improved_phase7_stretch_target.csv` | ✓ |
| `portfolio_version_sleeve_weights_improved_phase7_stretch_target.csv` | ✓ |
| `docs/research/2026-05-07_phase_6_market_state_classifier_rebuild_report.md` | ✓ |
| `docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md` | ✓ |

---

## Untracked File Groups

**Group A — Phase 7 (all new, all safe):**
- `scripts/phase_7_allocator_objective_rewrite.py` — new script
- `scripts/build_improvement_artifacts.py` — modified
- `docs/research/2026-05-07_phase_7_allocator_objective_rewrite_report.md`
- `data/research/phase_7_allocator_objective_rewrite/` — 24 files, 140K total
- Phase 7 portfolio CSVs in `data/05_layer3_portfolio_construction/` (15 files × 3 kinds)

**Group B — Phases 2–6 (new, all safe):**
- `scripts/phase_2_*.py` through `scripts/phase_6_*.py` (8 scripts)
- `scripts/build_pit_stock_breadth_panel.py`
- Phase 2–6 research reports in `docs/research/`
- Phase 2–6 data in `data/research/` (all directories under 10 MB individually)
- Phase 2–6 portfolio CSVs in `data/05_layer3_portfolio_construction/`
- `data/stock_breadth/` — 28K (templates only)

**Group C — OOO2/OOO3/OOO5, SSS, SSS2 (safe to commit):**
- `scripts/phase_ooo2_*.py`, `phase_ooo3_*.py`, `phase_ooo5_*.py`
- `scripts/phase_ppp_*.py`, `phase_qqq_*.py`, `phase_sss_*.py`, `phase_sss2_*.py`
- OOO docs reports in `docs/research/`
- `data/research/phase_ooo_signal_discovery/ooo2_*/` — all files under 1 MB ✓
- `data/research/phase_ooo_signal_discovery/ooo3_*/` — all files under 5 MB ✓
- `data/research/phase_ooo_signal_discovery/ooo5_*/` — all files under 6 MB ✓
- `data/research/phase_sss_regime_sequence_modeling/` — 18 MB total, max file 6.7 MB ✓
- `data/research/phase_sss2_sequence_signal_validation/` — 1.3 MB total ✓

**Group D — PPP/QQQ (partial — exclude large files):**
- `scripts/phase_ppp_*.py`, `scripts/phase_qqq_*.py` — safe (Python files)
- `data/research/phase_ppp_latent_factor_discovery/` — EXCLUDE `ppp_panel_characteristics.csv` (96 MB)
- `data/research/phase_qqq_deep_feature_interaction_mining/` — EXCLUDE 3 large files (128M, 80M, 44M)

**Group E — Audit reports (new, all small):**
- `reports/allocator_benchmark/*.md` (6 files)
- `reports/backtest_realism/*.md` (6 files)
- `reports/research_committee/*.md` (6 files)
- `data/research/allocator_benchmark/*.csv` (12 files)
- `data/research/backtest_realism/*.csv` (18 files)

**Group F — Dashboard updates:**
- `public/production-candidate-dashboard-bundle.json` — updated, 1.37 MB ✓
- `src/components/executive-summary.tsx` — updated narrative
- `src/lib/compact-dashboard.ts` — TypeScript type fix
- `src/types/dashboard.ts` — `ReturnPoint.method` made optional
- `scripts/build_release_dashboard_bundle.py` — new script

**Group G — Project documentation:**
- `docs/research/project_journey.md` — updated with Section 102

---

## Hard Stops (DO NOT COMMIT)

| File | Size | Reason |
|---|---|---|
| `data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery/ooo1_feature_panel.csv` | 144 MB | Over GitHub 100 MB limit |
| `data/research/phase_qqq_deep_feature_interaction_mining/qqq_model_predictions.csv` | 128 MB | Over GitHub 100 MB limit |
| `data/research/phase_ppp_latent_factor_discovery/ppp_panel_characteristics.csv` | 96 MB | Over 90 MB safety threshold |
| `data/research/phase_qqq_deep_feature_interaction_mining/qqq_ml_dataset.csv` | 80 MB | Over 90 MB safety threshold |
| `data/research/phase_qqq_deep_feature_interaction_mining/qqq_tree_path_interaction_pairs.csv` | 44 MB | Large regenerable ML output |
| `data/research/phase_5a_free_current_constituent_breadth_diagnostic/phase5a_free_stock_prices_adjclose_daily.parquet` | 5.5 MB | Raw yfinance daily stock prices (diagnostic only, excludable per task rules) |
| `public/dashboard-data.json` | 15 MB | Explicitly forbidden by CLAUDE.md |
| `public/dashboard-data-detail-allocation.json` | 50 MB | Too large, not tracked |
| `public/dashboard-data-detail-returns.json` | 33 MB | Too large, not tracked |
| `public/dashboard-data-detail-weights.json` | 22 MB | Too large, not tracked |
| `.venv/` | Large | Local virtualenv, not for commit |

---

## Blockers

- None. All prerequisite files confirmed. Large files identified and excluded. Build passes.

---

## Current Production Truth (verified, not changed)

- Production pin: `improved_phase2b_regime_confidence_boost`
- Production candidate: `improved_phaseggg_confirmed_only_robust_offense` (GGG1)
- Official shadow: `improved_phase2b_combo_abc`
- Best aggressive shadow (return): `improved_phase7_stretch_target` (7.88% / 0.926 Sharpe)
- Best aggressive shadow (risk-adj): `improved_phase4b_refined_sector_20pct` (7.76% / 0.959 Sharpe)
