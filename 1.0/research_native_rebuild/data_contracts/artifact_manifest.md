# Path B — Output Artifact Manifest

**Sprint 0 — 2026-06-07**
**All artifacts written ONLY to `research_native_rebuild/outputs/`.**
**No artifact is written to `data/`, `outputs/experiment_results/`, or any production path.**

---

## Artifact Status Key

- `PLANNED` — will be produced in the indicated sprint
- `NOT_YET_PRODUCED` — sprint not started
- `PRODUCED` — artifact exists and content is valid

---

## Sprint 0.5 — Equivalence Audit Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| Equivalence verification report | `outputs/comparison/sprint_0_5_equivalence_report.txt` | Plain text | 0.5 | NOT_YET_PRODUCED |
| Date index comparison | `outputs/comparison/date_index_check.csv` | CSV: date, production_date, shadow_date, match | 0.5 | NOT_YET_PRODUCED |
| Return calculation diff | `outputs/comparison/return_calculation_diff.csv` | CSV: date, ticker, prod_return, shadow_return, abs_diff | 0.5 | NOT_YET_PRODUCED |
| Holdout split check | `outputs/comparison/holdout_split_check.txt` | Plain text | 0.5 | NOT_YET_PRODUCED |
| Production baseline metrics | `outputs/comparison/production_baseline_metrics.csv` | CSV: metric, value | 0.5 | NOT_YET_PRODUCED |

**Pass condition for Sprint 0.5:** All NEEDS_TEST items in `equivalence_requirements.yaml` resolve
to VERIFIED. Any failure triggers a hard stop and must be resolved before Sprint 1 begins.

---

## Sprint 1 — Native Feature Panel Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| Native feature panel | `outputs/feature_panel/native_feature_panel.parquet` | Parquet: DatetimeIndex × N_features | 1 | NOT_YET_PRODUCED |
| Feature panel (CSV backup) | `outputs/feature_panel/native_feature_panel.csv` | CSV version for inspection | 1 | NOT_YET_PRODUCED |
| Feature availability report | `outputs/feature_panel/feature_availability.csv` | CSV: feature, first_date, null_count, lag_verified | 1 | NOT_YET_PRODUCED |
| Signal E_4wk reconstruction | `outputs/feature_panel/signal_e_4wk_native.csv` | CSV: date, signal_e_4wk (0/1) | 1 | NOT_YET_PRODUCED |
| Lag verification report | `outputs/feature_panel/lag_verification.txt` | Plain text confirming all features are 1-week lagged | 1 | NOT_YET_PRODUCED |

**Column requirements for native feature panel:**
- All Tier 1 features from `market_state_history.csv` and `regime_score.csv`
- All Tier 2 V3 macro/credit features from `macro_states_weekly_v3.csv`
- All Tier 3 VIX term structure features from `vix_term_structure.csv`
- `signal_e_4wk`: NM+slowdown+FC_benign+credit_improving 4-week rolling
- All features verified to have 1-week causal lag

---

## Sprint 2 — Native Regime Engine Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| Native state labels | `outputs/regime_engine/native_states.csv` | CSV: date, native_state, production_state, confidence | 2 | NOT_YET_PRODUCED |
| State observation counts | `outputs/regime_engine/state_obs_counts.csv` | CSV: state, dev_obs, holdout_obs, total_obs | 2 | NOT_YET_PRODUCED |
| State transition matrix (dev) | `outputs/regime_engine/state_transitions_dev.csv` | CSV: from_state × to_state (counts) | 2 | NOT_YET_PRODUCED |
| Hysteresis parameter log | `outputs/regime_engine/hysteresis_params.yaml` | YAML: activation/deactivation windows used | 2 | NOT_YET_PRODUCED |
| Regime engine diagnostics | `outputs/regime_engine/regime_diagnostics.txt` | Plain text: state counts, transition freq, OBS check | 2 | NOT_YET_PRODUCED |
| NM sub-state mapping | `outputs/regime_engine/nm_substate_mapping.csv` | CSV: date, nm_sub, v3_macro_state, fc_benign, credit_improving | 2 | NOT_YET_PRODUCED |

**Gate checks at Sprint 2 completion:**
- All active states must have ≥ 30 dev observations (HS9 hard stop if violated)
- stressed_panic definition must match or strengthen production (HS8 hard stop if weakened)
- calm_trend definition must be unchanged from production
- No state boundary derived using holdout data (HS3 hard stop if violated)

---

## Sprint 3 — Signal Weighting Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| Walk-forward IC table | `outputs/signal_weighting/ic_walkforward.parquet` | Parquet: date × (state, signal) | 3 | NOT_YET_PRODUCED |
| IC summary by state | `outputs/signal_weighting/ic_summary_by_state.csv` | CSV: state, signal, mean_ic, shrunk_ic, n_obs | 3 | NOT_YET_PRODUCED |
| Signal weights (final) | `outputs/signal_weighting/signal_weights_by_state.csv` | CSV: state, signal, weight | 3 | NOT_YET_PRODUCED |
| Shrinkage diagnostics | `outputs/signal_weighting/shrinkage_diagnostics.csv` | CSV: state, signal, raw_ic, shrunk_ic, shrinkage_applied | 3 | NOT_YET_PRODUCED |

**Requirements:**
- Walk-forward IC uses only dev-period data through each estimation date
- No holdout data in IC estimation (HS3 hard stop if violated)
- Shrinkage toward equal weighting applied to all IC estimates
- Signals with fewer than 30 obs in a state: use cross-state average IC (not state-specific)

---

## Sprint 4 — Risk Budget Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| State risk parameters | `outputs/risk_budgets/state_risk_params.yaml` | YAML: per-state offense_budget, defense_floor, fragility_cap, risk_multiplier | 4 | NOT_YET_PRODUCED |
| Risk budget diagnostics | `outputs/risk_budgets/risk_budget_diagnostics.txt` | Plain text: hard constraint verification | 4 | NOT_YET_PRODUCED |

**Hard constraints (must appear in state_risk_params.yaml):**
- `stressed_panic`: offense_budget ≤ 0.30, defense_floor ≥ 0.40
- All states: no_leverage = True, max_weight = 0.35, min_weight = 0.0, sum_weights = 1.0
- Parameters must be set by economic logic, not Sharpe maximization

---

## Sprint 5 — Portfolio Backtest Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| Shadow portfolio weights | `outputs/portfolio_backtest/shadow_weights.parquet` | Parquet: date × ETF | 5 | NOT_YET_PRODUCED |
| Shadow gross returns | `outputs/portfolio_backtest/shadow_gross_returns.csv` | CSV: date, gross_return | 5 | NOT_YET_PRODUCED |
| Shadow net returns | `outputs/portfolio_backtest/shadow_net_returns.csv` | CSV: date, net_return | 5 | NOT_YET_PRODUCED |
| Shadow turnover series | `outputs/portfolio_backtest/shadow_turnover.csv` | CSV: date, turnover | 5 | NOT_YET_PRODUCED |
| Shadow metrics (full + holdout) | `outputs/portfolio_backtest/shadow_metrics.csv` | CSV: metric, full_period, dev_period, holdout_period | 5 | NOT_YET_PRODUCED |
| Shadow state-level metrics | `outputs/portfolio_backtest/shadow_state_metrics.csv` | CSV: state, sharpe, annual_return, max_drawdown, obs_count | 5 | NOT_YET_PRODUCED |

---

## Sprint 6 — Comparison + Gate Artifacts

| Artifact | Path | Format | Sprint | Status |
|----------|------|--------|--------|--------|
| Gate evaluation report | `outputs/comparison/gate_evaluation.csv` | CSV: gate_id, gate_description, threshold, shadow_value, production_value, delta, pass | 6 | NOT_YET_PRODUCED |
| Bootstrap robustness report | `outputs/comparison/bootstrap_report.txt` | Plain text: n_draws, block_size, P(shadow>prod), verdict | 6 | NOT_YET_PRODUCED |
| Sensitivity to 2x costs | `outputs/comparison/cost_sensitivity.csv` | CSV: cost_multiple, shadow_sharpe, prod_sharpe, delta | 6 | NOT_YET_PRODUCED |
| Extreme-year exclusion | `outputs/comparison/extreme_year_exclusion.csv` | CSV: exclusion, shadow_sharpe, prod_sharpe, g1_passes | 6 | NOT_YET_PRODUCED |
| Rolling 104-week Sharpe | `outputs/comparison/rolling_sharpe.csv` | CSV: date, shadow_rolling_sharpe, prod_rolling_sharpe, shadow_wins | 6 | NOT_YET_PRODUCED |
| Final verdict summary | `outputs/comparison/final_verdict_sprint6.txt` | Plain text: verdict, all gates, champion | 6 | NOT_YET_PRODUCED |

---

## Governance Notes

1. No artifact in this manifest is written to `data/` or `outputs/experiment_results/`.
2. No artifact from Sprint 1–4 is used to update the production portfolio or any production file.
3. Sprint 5 and 6 artifacts are research outputs only — they cannot trigger production changes without explicit human authorization.
4. If Sprint 6 final verdict is PROMOTE_TO_PHASE_D_TEST, the user must authorize before any production file is touched.
5. Holdout-period data appears in outputs only in Sprint 5 and 6, strictly as evaluation targets — never as calibration inputs.
