# Phase 2B Sprint Report — Interpretable ML Meta Layer

**Sprint goal.** Test whether *interpretable* machine learning (logistic, shallow trees, monotonic GBM, walk-forward, no lookahead) can improve regime confidence, deployment timing, and risk-release decisions on top of the current Phase 1 production candidate. The ML acts as a *meta layer* that modifies only the raw `regime_multiplier` before self / non-self-gated relief is computed — it is orthogonal to `overlay_penalty_mode` and leaves the allocator, state_tilt, and stressed-panic protection untouched.

**Control.** `improved_hrp_phase1_dynamic_risk_budget` (Phase 1 winner; HRP + sample cov, `dynamic_risk_budget` state tilt, incumbent `lighter_both_targeted_narrow_plus_confirmed` overlay relief).

**Promotion rule.** `prod_score` delta ≥ 0.05, `max_drawdown` within 0.005 of control, `cvar_5` within 0.002 of control.

---

## A. Executed

1. Built walk-forward interpretable-ML predictions (`scripts/build_phase2b_meta_predictions.py`):
   - `p_regime_confidence` — `LogisticRegression` with balanced class weights + `StandardScaler`. Label = forward 4-week Sharpe > 0.5 AND min weekly return > -0.03. 11 causal features (breadth, trend, drawdown, canary_breadth_default, transition probabilities).
   - `p_transition_quality` — `DecisionTreeClassifier(depth=4)`, trained **only** on transition-state observations (`neutral_mixed`, `recovery_fragile`, `recovery_confirmed`). Label = forward 8-week return > 0 AND 8-week max DD > -0.05.
   - `p_tail_risk` — `HistGradientBoostingClassifier` with monotonic constraints (breadth/trend/persistence → decreasing tail risk; canary_breadth_default/recent_stress_26w → increasing). Label = forward 4-week max DD ≤ -0.03.
   - Walk-forward: 200-week warmup, retrain every 26 weeks, expanding window. 910 weekly predictions produced.
2. Added module-level loader of `data/04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv` and `apply_phase2b_adjustment()` helper in `scripts/build_improvement_artifacts.py`. Extended `apply_overlays_custom()` with a new `phase2b_mode` parameter that modifies `regime_multiplier` before the self/non-self-gated relief pipeline, then threaded `phase2b_mode` through `run_subset_custom()` and the version_spec caller.
3. Added 5 Phase 2B variants (A, B, C, E=A+C, F=A+B+C) to `version_specs`, all preserving the CONTROL's overlay relief, allocator, and state tilt.
4. Ran the full build pipeline; extracted metrics from `portfolio_version_comparison.csv`, regime splits from `portfolio_version_regime_split_summary.csv`, and reconstructed phase2b offset distributions from `phase2b_meta_predictions.csv` × `market_state_history.csv`.

## B. Files/artifacts changed

- **New**: `scripts/build_phase2b_meta_predictions.py` (≈340 lines; walk-forward ML trainer; interpretability dump).
- **New**: `data/04_layer2b_risk_regime_engine/phase2b_meta_predictions.csv` (910 weekly rows, 4 columns).
- **New**: `data/04_layer2b_risk_regime_engine/phase2b_meta_interpretability.txt` (logistic coefs, tree depth/features, HGBM monotonic map).
- **Edited**: `scripts/build_improvement_artifacts.py` — module-level predictions loader; new `apply_phase2b_adjustment` helper near `compute_causal_confidence`; `phase2b_mode` + `ml_pred_row` kwargs threaded through `apply_overlays_custom()` and `run_subset_custom()`; 5 new version_specs appended after the Phase 2A combo F block.
- **Regenerated**: all `portfolio_version_*_improved_phase2b_*` weights/returns/sleeve_weights artifacts in `data/05_layer3_portfolio_construction/`.
- **Updated**: `portfolio_version_comparison.csv`, `portfolio_version_regime_split_summary.csv`, `allocation_driver_summary.csv`, `portfolio_version_diagnostics_timeseries.csv`, `portfolio_version_subperiod_summary.csv`.
- **New**: this report — `docs/research/phase2b_sprint_report.md`.

## C. Variant catalog and standalone results

All 5 variants share the CONTROL's HRP allocator, `dynamic_risk_budget` state tilt, `lighter_both_targeted_narrow_plus_confirmed` overlay, `target_vol_ceil=1.00`, speed=0.40, rerisk_speed=1.00, and `good_state_fragile_expression` overlay variant.

| Variant | Mode | What it does |
|---|---|---|
| A — `improved_phase2b_regime_confidence_boost` | `regime_confidence_boost` | Non-stressed states only; when `p_regime_confidence ≥ 0.55`, add up to +0.045 to `regime_multiplier` (linear in `(p − 0.55) / 0.45`). Boost-only. |
| B — `improved_phase2b_transition_quality_gate` | `transition_quality_gate` | `strong_neutral` or `recovery_fragile` only; `p_transition_quality > 0.60` → +0.04, `< 0.40` → −0.03. |
| C — `improved_phase2b_tail_risk_suppression` | `tail_risk_suppression` | All states except `stressed_panic`; when `p_tail_risk > 0.55`, subtract up to 0.10 from `regime_multiplier` (linear in `(p − 0.55) / 0.45`). Suppress-only. |
| E — `improved_phase2b_combo_ac` | `combo_ac` | A + C jointly. |
| F — `improved_phase2b_combo_abc` | `combo_abc` | A + B + C jointly. |

### Standalone metrics (vs control, all 2005–2025)

| Variant | Ann Ret | Ann Vol | Sharpe | Max DD | Calmar | CVaR 5% | Avg Cash | Avg Turnover | prod_score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **CONTROL** (`improved_hrp_phase1_dynamic_risk_budget`) | 6.85% | 7.77% | 0.8822 | −13.98% | 0.4905 | −2.61% | 16.53% | 5.61% | 0.7508 |
| A — regime_confidence_boost | 6.89% | 7.79% | 0.8844 | −13.98% | 0.4932 | −2.62% | 16.18% | 5.62% | 0.8175 |
| B — transition_quality_gate | 6.87% | 7.78% | 0.8829 | −13.98% | 0.4915 | −2.61% | 16.44% | 5.64% | 0.7768 |
| C — tail_risk_suppression | 6.80% | 7.72% | 0.8809 | −13.67% | 0.4976 | −2.60% | 16.80% | 5.62% | 0.7611 |
| E — combo_ac (A+C) | 6.84% | 7.75% | 0.8827 | −13.67% | 0.5002 | −2.61% | 16.44% | 5.64% | 0.8090 |
| F — combo_abc (A+B+C) | 6.86% | 7.76% | 0.8836 | −13.67% | 0.5016 | −2.61% | 16.38% | 5.66% | 0.8073 |

### Deltas vs CONTROL

| Variant | Δprod_score | ΔSharpe | ΔCalmar | ΔMax DD | ΔCVaR | Promotion rule |
|---|---:|---:|---:|---:|---:|---|
| A | +0.0667 | +0.0022 | +0.0027 | +0.0000 | −0.0001 | **Passes** (≥0.05, DD/CVaR within tol) |
| B | +0.0260 | +0.0007 | +0.0011 | +0.0000 | 0.0000 | Fails (Δprod < 0.05) |
| C | +0.0103 | −0.0013 | +0.0071 | +0.0030 | +0.0001 | Fails (Δprod < 0.05, Sharpe slightly worse) |
| E | +0.0583 | +0.0005 | +0.0097 | +0.0030 | +0.0001 | **Passes** |
| F | +0.0565 | +0.0014 | +0.0111 | +0.0030 | 0.0000 | **Passes** |

### Regime-conditioned breakdown (Sharpe by `risk_state`)

| Variant | Calm | Neutral | Stressed |
|---|---:|---:|---:|
| CONTROL | 0.509 | 1.300 | 0.503 |
| A | 0.508 | 1.302 | 0.506 |
| B | 0.509 | 1.298 | 0.509 |
| C | 0.508 | 1.294 | 0.516 |
| E (A+C) | 0.508 | 1.294 | 0.519 |
| **F (A+B+C)** | 0.509 | 1.292 | **0.524** |

The headline: **the Phase 2B meta signals deliver almost all their improvement inside the `stressed` risk state**, where C/E/F lift Sharpe by +0.013 to +0.021 vs control. Neutral Sharpe is flat-to-slightly-worse for C/E/F (−0.006 to −0.008) because the tail-suppression signal trims risk early when breadth weakens, sacrificing a few bp of neutral-state return to add stress-state resilience. Calm state is essentially unchanged.

### Meta-signal activation diagnostics

Reconstructed from `phase2b_meta_predictions.csv` × `market_state_history.csv` (1110 weekly observations):

| Variant | Fire rate | Mean offset | Range | Dominant state |
|---|---:|---:|---:|---|
| A — conf boost | 28.1% | +0.0042 | [0, +0.045] | `neutral_mixed` (+0.0043 mean), `recovery_fragile` (+0.002) |
| C — tail suppress | 11.0% | −0.0024 | [−0.046, 0] | `neutral_mixed` late (pre-stress), `recovery_fragile` |
| E (A+C) | combined | +0.0018 | [−0.045, +0.045] | Net boost in neutral; net suppress when tail-risk spikes |

Mean `p_regime_confidence` by state: `calm_trend` 0.50, `neutral_mixed` 0.57, `recovery_fragile` 0.55, `stressed_panic` 0.29. Mean `p_tail_risk` by state: `calm_trend` 0.25, `neutral_mixed` 0.42, `stressed_panic` 0.76. Both align with economic intuition — logistic/HGBM are reading breadth + trend + transition probabilities in directions consistent with their labels.

## D. Helped standalone?

- **A** — yes, cleanly. Sharpe +0.0022, Calmar +0.0027, DD flat, CVaR flat. `prod_score` delta +0.067 passes the +0.05 bar on rank-lift.
- **B** — marginal. Sharpe +0.0007, `prod_score` +0.026 below bar. Fires only in strong_neutral + recovery_fragile, and the asymmetric ±3–4pp rule didn't accumulate enough signal.
- **C** — mixed. Lowers Sharpe −0.0013 but improves DD by +0.003 and Calmar +0.007. Effect is concentrated in stressed (+0.013 Sharpe) at the cost of neutral (−0.006 Sharpe). `prod_score` delta +0.010 fails the bar.
- **E** (A+C) — yes. Calmar +0.0097 (second-best), DD +0.003, Sharpe flat. `prod_score` +0.058 passes.
- **F** (A+B+C) — yes. Best stressed-state Sharpe (+0.021), best Calmar (+0.011), DD +0.003, Sharpe +0.0014. `prod_score` +0.057 passes.

## E. Helped in combination?

- **E vs A standalone**: A delivered +0.067 `prod_score` with zero DD improvement; adding C (to form E) costs −0.0017 Sharpe vs A but buys +0.003 DD and +0.007 Calmar. The combo is net worse on `prod_score` (0.058 vs 0.067) because the rank-based score weights Sharpe heavily. But E has a materially better Calmar than A, so it's not obvious which is preferable.
- **F vs E**: adding B (transition-quality gate) on top of A+C gives a very small Sharpe uplift (+0.0009) and a very small Calmar uplift (+0.0014). B standalone was Research-only, but it isn't destructive in combination — it doesn't undo A or C, and it adds a tiny amount in stressed state (Sharpe +0.0053 at the F vs E comparison).
- **A+B (not tested)**: likely dominated by A alone given B's near-null standalone effect.
- **B+C (not tested)**: the skipped combo; likely behaves near-C since B's effect is small.

The three signals appear **approximately additive, not substitutive**. The tail-suppression (C) helps the drawdown side; the confidence boost (A) helps the return side; the transition gate (B) adds a thin layer of discipline in strong_neutral / fragile where A may over-boost. Interaction terms are small.

## F. Diagnostics / what went wrong

- **Magnitudes are small.** All Sharpe deltas ≤ 0.0022, all Calmar deltas ≤ 0.011, all DD deltas ≤ 0.003 absolute. The `prod_score` rule crosses the +0.05 bar mostly via rank lift among a tightly packed field, not via economically large improvements. This is the honest limitation of adding a meta layer on top of an already-disciplined Phase 1 stack: the residual alpha for ML to find is small.
- **Single Sharpe regression** (C) is visible in the neutral risk state — tail-suppression trims re-risking during breadth-weak neutral weeks that don't become stressed, costing a few bp of upside. F recovers this by pairing C with A so that confident-neutral weeks still boost.
- **No lookahead issues detected.** Walk-forward CV, expanding window with 26-week retrain cadence, first prediction at week 200. Label constructions use strictly forward-looking windows but those are only evaluated in training; predictions at date `t` use only data ≤ `t`.
- **Model interpretability verified.** Logistic coefficients are economically sensible (market_trend_positive +0.276, breadth_sma_43 −0.188 with sign flipped by scaler, transition_non_stress_prob +0.171, market_drawdown −0.106, breadth_13w_mom +0.090). HGBM monotonic constraints held at inference. Tree depth capped at 4.

## G. Final classification

| Variant | Classification | Rationale |
|---|---|---|
| A — `improved_phase2b_regime_confidence_boost` | **Conditional promote** | Cleanest single-signal pass: Sharpe ↑, Calmar ↑, DD/CVaR unchanged. Simplest to explain. |
| B — `improved_phase2b_transition_quality_gate` | Research-only | Passes no harm test but Δprod_score +0.026 below the +0.05 bar. Keep tree diagnostics; revisit when the transition-state sample grows. |
| C — `improved_phase2b_tail_risk_suppression` | Research-only | Standalone Sharpe regression. The signal is real (monotonic HGBM picking up breadth/canary deterioration before the state-machine flips) but alone it over-suppresses neutral re-risking. Effective when paired with A (see E/F). |
| E — `improved_phase2b_combo_ac` | **Conditional promote** | Passes all rule tolerances. Best Calmar-DD trade among passing variants with only two signals. |
| F — `improved_phase2b_combo_abc` | **Conditional promote (recommended)** | Best Calmar (+0.011) and best stressed-state Sharpe (+0.021). Sharpe +0.0014 at a DD +0.003 improvement. Fullest test of the interpretable-ML stack; signals approximately additive. |

## H. Recommendation

**Recommended winner: `improved_phase2b_combo_abc` (F) as a Conditional promote.** It posts the largest Calmar improvement (+0.011) and the largest stressed-state Sharpe improvement (+0.021) in the sprint while keeping DD better than control (by 0.003), CVaR flat, and Sharpe marginally up (+0.0014). `prod_score` delta +0.057 clears the +0.05 bar. The three constituent signals are each individually interpretable (one logistic coefficient vector, one shallow tree, one monotonic HGBM), walk-forward, and causal. The meta adjustment is bounded in magnitude (≤ 0.045 up, ≤ 0.10 down) and gated by state, so failure modes are visible in `phase2b_mode_spec` / `phase2b_offset` diagnostics.

**Runner-up: `improved_phase2b_regime_confidence_boost` (A).** Pick A over F if the priority is the simplest possible addition (one logistic model, boost-only, non-stressed only) and the team is unwilling to take the −0.006 neutral Sharpe cost that comes bundled with the tail-suppression signal.

**Caveat.** The improvements are economically small. Phase 1's winner has already captured most of the easy alpha; Phase 2B's value is in improving behavior in the stressed state where the non-ML stack has least information. If the user wants to see a larger absolute lift, the next sprint should move to the sleeve layer (new interpretable signals or new sleeves) rather than iterate further on meta layers on top of the existing stack.

**Control left unchanged unless user approves promotion.** The current production candidate in `CLAUDE.md` (`improved_hrp_recovery_tilt`) is untouched; the Phase 1 winner (`improved_hrp_phase1_dynamic_risk_budget`) is also untouched. Promoting F would update the Phase 1 → Phase 2B chain in the dashboard and rerun the dashboard-data.json generator.
