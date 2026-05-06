# Phase JJ — Controlled ML Sprint for the ETF Quant Portfolio Project

**Date:** 2026-04-27
**Phase type:** Full but controlled ML sprint testing whether ML can improve forward-stress prediction quality and translate into portfolio improvement
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## 1. Commands executed

```
python scripts/phase_jj_ml_regime_sprint.py
  └── invokes scripts/build_improvement_artifacts.py via subprocess with
       BUILD_VERSION_NAMES=improved_phasejj_ml_riskdial_25,
                           improved_phasejj_ml_riskdial_50,
                           improved_phase2b_regime_confidence_boost
python scripts/research_committee_report.py improved_phasejj_ml_riskdial_25 --quick
python scripts/research_committee_report.py improved_phasejj_ml_riskdial_50 --quick
```

Layer 5 / Layer 6 quick audits and Layer 3 / 4 audits were **NOT run**. Per spec, the gate for further audits is "KEEP AS SHADOW with **genuine** ML and portfolio improvement." ML prediction improvement is genuine (Brier −65%), but portfolio Sharpe is slightly negative on both candidates (-0.0012 / -0.0021), so portfolio improvement is not genuine.

## 2. Files created or modified

Code (created / edited):
- `scripts/phase_jj_ml_regime_sprint.py` (new — Parts 1–3c driver)
- `scripts/build_improvement_artifacts.py` — four additive edits (PHASEJJ_BLENDED_25/50_LOOKUP module-level loaders; extend `apply_a`; runtime override of `p_regime` in `apply_phase2b_adjustment`; two new version specs)

Data (Phase JJ ML outputs in `data/04_layer2b_risk_regime_engine/`):
- `phase_jj_ml_dataset.csv` (1109 × 39: 35 features + 4 targets)
- `phase_jj_ml_feature_manifest.csv`
- `phase_jj_ml_model_metrics.csv`
- `phase_jj_ml_predictions.csv`
- `phase_jj_ml_calibration.csv`
- `phase_jj_ml_feature_importance.csv`
- `phase_jj_ml_fit_log.csv`
- `phase_jj_ml_stability_period_baseline_existing.csv`
- `phase_jj_ml_stability_period_logistic_regime_only.csv`
- `phase_jj_ml_stability_state_baseline_existing.csv`
- `phase_jj_ml_stability_state_logistic_regime_only.csv`
- `phase_jj_blended_predictions.csv` (the 25/75 and 50/50 blends fed into the production pipeline)

Data (Phase JJ portfolio outputs in `data/05_layer3_portfolio_construction/`):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasejj_ml_riskdial_{25,50}.csv` (6 files via production pipeline)
- `phase_jj_candidate_metrics_full.csv`
- `phase_jj_state_summary.csv`
- `phase_jj_selection_table.csv`
- `phase_jj_protocol.json`

Reports:
- `reports/research_committee/improved_phasejj_ml_riskdial_25_audit.md`
- `reports/research_committee/improved_phasejj_ml_riskdial_50_audit.md`

Docs:
- `docs/research/2026-04-27_phase_jj_ml_regime_sprint_report.md` (this file)
- `docs/research/project_journey.md` — Section 49 appended

## 3. Dataset rows and feature count

- Rows: 1,109 weekly observations (2005-01-07 through 2026-04-10 minus the 4-week forward-target tail).
- Features: **35** total — 12 existing regime + 3 existing Phase 2B predictions + 7 refined-state one-hots + 3 refined numeric (deterioration_z, deterioration_rank_neutral_mixed, defensive_overlay_hint as a numeric feature only) + 10 macro/ETF proxies.
- Targets: **4** forward-risk binary labels.

## 4. Target definitions and class balance

| target | definition | n | pos rate |
|---|---|---:|---:|
| A — `stress_transition_4w` | 1 if any of next 4 weeks is `stressed_panic` | 1,105 | 27.7% |
| B — `prod_bad_return_4w` | 1 if forward 4w prod net return ≤ historical 25th percentile | 1,109 | 25.0% |
| C — `spy_bad_return_4w` | 1 if forward 4w SPY return ≤ historical 25th percentile | 1,109 | 25.0% |
| D — `prod_drawdown_worsens_4w` | 1 if min cumulative return in next 4w ≤ -3% | 1,109 | 5.8% |

Targets are computed using future windows (by definition) but never appear as features. Class balance is sufficient for all four.

## 5. Feature manifest summary

All 35 features:
- **Group A — existing regime** (12): `market_drawdown`, `market_trend_positive`, `breadth_sma_43`, `breadth_26w_mom`, `breadth_13w_mom`, `breadth_change_4w`, `canary_breadth_default`, `recent_stress_26w`, `transition_persistence_prob`, `transition_good_state_prob`, `transition_non_stress_prob`, `avg_corr_risk_off_z`.
- **Group A — existing Phase 2B predictions** (3): `p_regime_confidence`, `p_transition_quality`, `p_tail_risk`.
- **Group B — Phase CC refined-state one-hots** (7): `refined_state_is_calm_trend`, `..._neutral_healthy`, `..._neutral_mixed`, `..._neutral_deteriorating`, `..._recovery_confirmed`, `..._recovery_fragile`, `..._stressed_panic`.
- **Group B — Phase CC refined numeric** (3): `deterioration_z`, `deterioration_rank_neutral_mixed`, `defensive_overlay_hint` (used as a numeric feature, NEVER as a portfolio multiplier).
- **Group C — macro / ETF proxies** (10): `hyg_lqd_credit_spread_proxy`, `uup_dollar_strength_4w`, `tlt_rate_sensitive_4w`, `gld_defensive_4w`, `spy_realized_vol_4w`, `spy_drawdown_from_52w_high`, `spy_minus_iei_3m`, `xlf_minus_xlu_3m`, `ig_credit_4w`, `hy_credit_4w`.

All features are 1-week-lagged before entering X (causal_lag). Saved manifest is at `data/04_layer2b_risk_regime_engine/phase_jj_ml_feature_manifest.csv`.

## 6. Leakage checks

1. **All features lagged by +1 week** before entering the feature matrix (`causal_lag(feat, lag_weeks=1)`).
2. **Targets are forward-looking by construction** but never appear as features.
3. **Walk-forward training:** train rows have `index < score_idx[0]` strictly; no overlap.
4. **No random shuffle.** Time order is preserved.
5. **Refined-state features inherit Phase CC's walk-forward construction** — z-score uses trailing 156-week window lagged 1 week; rank uses only past `neutral_mixed` weeks.
6. **`defensive_overlay_hint` used as a numeric feature only**, never as a portfolio multiplier in this phase.
7. **Phase CC state file values are present from 2008-08 onwards** for the rank/z columns (earlier weeks fall back to original `neutral_mixed`); the dataset trims early observations where features are NaN, so OOS scoring begins after the 260-week initial training window.

## 7. Model list tested

Baseline:
1. **`baseline_existing` / `p_regime_only_inverted`** — uses `1 − p_regime_confidence` as the predicted forward-stress probability. No new model.

Light / interpretable:
2. **`logistic` / `regime_only`** — sklearn `LogisticRegression` (liblinear, max_iter=1000) on Group A features only.
3. **`logistic` / `regime_plus_refined`** — same but on all 35 features.
4. **`logistic_l2` / `all`** — `LogisticRegression(C=0.5, penalty="l2")` on all 35 features.
5. **`tree_d3` / `all`** — `DecisionTreeClassifier(max_depth=3, min_samples_leaf=20)`.

Harder controlled:
6. **`rf_shallow` / `all`** — `RandomForestClassifier(n_estimators=100, max_depth=3, min_samples_leaf=20)`.
7. **`hgb_shallow` / `all`** — `HistGradientBoostingClassifier(max_iter=100, max_depth=3, learning_rate=0.05, min_samples_leaf=20, l2_regularization=0.5, early_stopping=True)`.

No grid search. Hyperparameters fixed at the conservative values shown.

## 8. Model validation scheme

**Expanding-window walk-forward.** Initial training window: 260 weeks (~5 years). Retrain frequency: 26 weeks. At each retrain, scoring covers the next 26 weeks. Train rows must have at least 5 positive AND 5 negative examples; otherwise the retrain is skipped and the score window is left as NaN. Out-of-sample evaluation is the union of all scored 26-week chunks.

## 9. ML metrics table (all models × all targets)

```
            model                  label                            target  n_obs  brier    auc  log_loss
baseline_existing p_regime_only_inverted     target_A_stress_transition_4w   1105 0.2682 0.7281    0.7753
         logistic            regime_only     target_A_stress_transition_4w    845 0.0941 0.8648    0.3543
         logistic    regime_plus_refined     target_A_stress_transition_4w    845 0.1106 0.8673    0.3942
      logistic_l2                    all     target_A_stress_transition_4w    845 0.1047 0.8735    0.3643
          tree_d3                    all     target_A_stress_transition_4w    845 0.1230 0.7824    0.9260
       rf_shallow                    all     target_A_stress_transition_4w    845 0.0989 0.8439    0.3673
      hgb_shallow                    all     target_A_stress_transition_4w    845 0.1209 0.7831    0.4804
baseline_existing p_regime_only_inverted       target_B_prod_bad_return_4w   1109 0.3492 0.4386    0.9816
         logistic            regime_only       target_B_prod_bad_return_4w    849 0.2365 0.4932    0.6954
       rf_shallow                    all       target_B_prod_bad_return_4w    849 0.2059 0.4514    0.6038
      hgb_shallow                    all       target_B_prod_bad_return_4w    849 0.2137 0.5126    0.6282
baseline_existing p_regime_only_inverted        target_C_spy_bad_return_4w   1109 0.3166 0.5613    0.8963
         logistic            regime_only        target_C_spy_bad_return_4w    849 0.2174 0.4722    0.6425
       rf_shallow                    all        target_C_spy_bad_return_4w    849 0.1832 0.4638    0.5551
baseline_existing p_regime_only_inverted target_D_prod_drawdown_worsens_4w   1109 0.3723 0.4014    1.0516
         logistic            regime_only target_D_prod_drawdown_worsens_4w    823 0.0699 0.6574    0.2545
       rf_shallow                    all target_D_prod_drawdown_worsens_4w    823 0.0569 0.5892    0.2298
```

(Full table in `phase_jj_ml_model_metrics.csv`.)

## 10. Did refined-state features improve OOS prediction?

**No — and this is the most important finding of the sprint, contradicting the HH3 ablation.**

On Target A (stress_transition_4w):
- `logistic regime_only` (12 + 3 = 15 features): Brier **0.0941** (best)
- `logistic regime_plus_refined` (35 features incl. refined-state): Brier **0.1106** (worse by 0.0165, ~17%)
- `logistic_l2 all` (35 features w/ L2): Brier 0.1047 (still worse than regime_only)

Adding refined-state features **degrades** OOS Brier despite the HH3 single-shift Brier ablation suggesting they helped. Two consistent explanations:

1. **Collinearity.** `deterioration_z`, the refined-state one-hots, and `defensive_overlay_hint` are all mathematical functions of features already in Group A (drawdown, breadth, stress, transition probabilities). The added columns are largely redundant with the existing 12 features and increase parameter variance without adding information.
2. **HH3's ablation used a fixed, hand-coded shift, not a fitted model.** HH3 added `±0.05` based on refined_state to a pre-computed `1 − p_regime_confidence`. That fixed-coefficient shift can produce a Brier improvement that does NOT survive fitting the coefficients walk-forward, because the fitted model has to also choose the corresponding interaction between Group A and refined-state features and the resulting fit is less stable.

This is a clean methodological lesson: **a feature improving Brier in a fixed-shift ablation can fail to improve Brier in a walk-forward fitted model.** The latter is the operationally relevant test.

## 11. Did hard ML beat light ML?

**No.** `logistic regime_only` (Brier 0.0941, AUC 0.8648) is the best model on Target A. `rf_shallow all` (0.0989, 0.8439) and `logistic_l2 all` (0.1047, 0.8735) are close — but neither beats simple logistic on Brier. `tree_d3` (0.1230) and `hgb_shallow` (0.1209) are noticeably worse on Brier.

For the other targets, hard ML (RF, HGB) sometimes wins on Brier (Target B/C/D) but the AUCs are all close to 0.50 — those targets are not predictable from these features in this dataset.

**Interpretable ML is sufficient for this project.** No reason to add hard-ML complexity given the empirical result.

## 12. Best ML model and why

**`logistic regime_only` on Target A.**

- Lowest OOS Brier on Target A (0.0941; baseline 0.2682; reduction 65%).
- High AUC (0.8648).
- Strict subset of features (Group A only — 12 regime features + 3 existing Phase 2B predictions). Fully interpretable, no refined-state dependency, no macro-feature dependency.
- Stable across periods (see Section 16).

Selected as the input for the Phase JJ blended-predictions file.

## 13. Feature importance / coefficients (top by |coef|, logistic_l2 all on Target A, full-sample dump for interpretability)

| feature | std. coef |
|---|---:|
| deterioration_z | +1.60 |
| p_tail_risk | -1.15 |
| spy_drawdown_from_52w_high | -0.89 |
| canary_breadth_default | +0.88 |
| breadth_13w_mom | -0.71 |
| refined_state_is_stressed_panic | +0.64 |
| ig_credit_4w | -0.44 |
| spy_realized_vol_4w | +0.44 |
| transition_persistence_prob | +0.41 |
| market_drawdown | +0.41 |
| hyg_lqd_credit_spread_proxy | -0.41 |
| deterioration_rank_neutral_mixed | +0.41 |
| refined_state_is_recovery_fragile | -0.40 |
| refined_state_is_recovery_confirmed | -0.39 |
| p_regime_confidence | +0.37 |

Note the paradox: refined-state features and `deterioration_z` HAVE strong full-sample coefficients (so they help in-sample fit) but DEGRADE walk-forward OOS performance. This is the canonical overfitting signature.

(Full table for all models in `phase_jj_ml_feature_importance.csv`.)

## 14. Calibration summary (best model: logistic regime_only on Target A)

```
bucket    n  mean_pred  mean_actual
     0  169     0.0047       0.0533
     1  169     0.0208       0.0888
     2  169     0.0543       0.0888
     3  169     0.1949       0.1598
     4  169     0.8590       0.8166
```

The model is **slightly overconfident at the extremes** (predicts ~0.5% at the bottom, actual ~5.3%; predicts 86% at the top, actual 82%) but **broadly well calibrated** across mid-range buckets. No catastrophic miscalibration.

## 15. Top-risk-decile precision/recall

Bucket 4 (top quintile) captures 169 weeks with 82% actually transitioning into `stressed_panic` within 4 weeks (vs the 27% base rate). That is a ~3× positive lift. The bottom quintile predicts 0.5% probability and gets 5% actual — practical floor for low-risk classification.

(Top decile is not separately tabulated — the qcut is at 5 buckets for stability with the OOS sample size.)

## 16. Model stability by time period (4 equal-sized periods, OOS)

Brier per period for Target A:
- baseline_existing: [0.426, 0.221, 0.223, 0.201]
- logistic regime_only: [0.039, 0.163, 0.099, 0.076]

The ML model is dramatically better in the early period (0.039 vs 0.426 — capturing the 2008-09 GFC stress predictability) and meaningfully better in every later period. The improvement is NOT concentrated in a single window. Stability is acceptable.

## 17. Model stability by regime / refined_state

Saved at `phase_jj_ml_stability_state_logistic_regime_only.csv`. Predictions are available across all refined states; the model's Brier is lowest in `calm_trend` and `neutral_healthy` (where forward-stress probability is genuinely low, easy to predict) and highest in `neutral_deteriorating` and `recovery_fragile` (where forward stress is uncertain).

## 18. Candidate portfolio metrics

```
                                    name  full_ann_return  full_ann_vol  full_sharpe  full_max_drawdown  full_cvar_5  avg_BIL  avg_SPY  avg_turnover
         improved_phasejj_ml_riskdial_25            0.0692        0.0783       0.8837            -0.1418      -0.0263   0.2811   0.0711        0.1128
         improved_phasejj_ml_riskdial_50            0.0696        0.0788       0.8827            -0.1448      -0.0265   0.2777   0.0713        0.1129
improved_phase2b_regime_confidence_boost            0.0689        0.0779       0.8848            -0.1398      -0.0262   0.2839   0.0708        0.1124
              improved_phase2b_combo_abc            0.0686        0.0776       0.8840            -0.1367      -0.0261   0.2856   0.0708        0.1130
```

**Headline deltas:**

| metric | JJ1 (25/75) | JJ2 (50/50) | production |
|---|---:|---:|---:|
| ann return | 6.92% (+0.03pp) | **6.96% (+0.07pp)** | 6.89% |
| Sharpe | 0.8837 (-0.0012) | 0.8827 (-0.0021) | 0.8848 |
| MDD | -14.18% (-0.20pp) | -14.48% (**-0.50pp** at gate edge) | -13.98% |
| CVaR-5% | -2.63% (-0.01pp) | -2.65% (-0.03pp) | -2.62% |
| turnover | 0.1128 (+0.4%) | 0.1129 (+0.4%) | 0.1124 |
| avg BIL | 28.11% (-0.28pp) | 27.77% (-0.62pp) | 28.39% |

JJ2 produces the largest ann return improvement (+0.07pp) but at the cost of -0.50pp MDD (right at the strict gate edge). Both have slightly negative Sharpe deltas.

## 19. State-by-state impact (JJ1)

```
              state  n_weeks  Δ_mean_wkly   cumulative
         calm_trend  295      +0.000002      +0.07%
neutral_deteriorating 171     +0.000024      +0.53%
    neutral_healthy  210      +0.000021      +0.78%   ← good-state participation
      neutral_mixed  112       0.000000        0.00%
recovery_confirmed   44       -0.000006      -0.03%
  recovery_fragile   49       -0.000011      -0.06%
     stressed_panic 229       -0.000009      -0.26%
```

JJ2 amplifies the same pattern (neutral_healthy +2.17%, neutral_deteriorating +0.90%, stressed_panic -0.48%). The ML risk-dial is doing what it should: more risk-on in healthy, less in stressed. But the absolute magnitudes are still small.

## 20. Hidden beta / hidden cash check

JJ1: BIL -0.28pp, SPY +0.03pp. JJ2: BIL -0.62pp, SPY +0.05pp. Neither candidate inflates SPY exposure materially. The small BIL drop is the mechanical consequence of higher regime_multiplier in healthy weeks. **No hidden beta.**

## 21. Best candidate

**JJ1** — selected by tie-break (smaller Sharpe drag than JJ2). Selection-rule failure reason: `sharpe_imp<0.005 (-0.0012)`.

## 22. Quick committee verdict

Both candidates: **KEEP AS SHADOW (research reference).** "Competitive on risk-adjusted axes but does not pass the production return-delta gate."

## 23. Were Layer 5/6 quick audits run?

**No** — per spec, the gate for further audits is "KEEP AS SHADOW with **genuine** ML and portfolio improvement." ML prediction improvement is genuine (Brier −65%), but portfolio Sharpe is slightly negative on both candidates. The strict reading of "genuine portfolio improvement" is not met. Skipping further audits saves token budget without changing the verdict.

## 24. Final decision

**REJECT both Phase JJ portfolio candidates** under the strict 11-gate selection rule. JJ1 fails on Sharpe. JJ2 fails on Sharpe AND MDD (right at the -0.50pp boundary).

**KEEP AS SHADOW (research reference)** per quick committee — both candidates produce small headline gains and the underlying ML model is a major prediction improvement.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.

## 25. Should the ML path continue?

**Yes, but in a focused way — not as a portfolio-multiplier sprint.**

What worked:
- **Massive prediction improvement on Target A** (Brier 0.2682 → 0.0941, 65% reduction). This is the kind of result that would be a genuine ML contribution to a quant project.
- **Light interpretable ML wins.** No need for hard ML on this dataset.
- **The model's coefficients are economically sensible** (drawdown +, breadth -, credit spread tightness +, etc.).

What didn't work:
- **Refined-state features hurt OOS** despite helping in HH3's fixed-shift ablation. Should NOT be added to a future production retraining of `p_regime_confidence`.
- **Portfolio integration via blended `regime_multiplier` is too bounded** to express the full prediction improvement. The 25/75 and 50/50 blends produce only +0.03 and +0.07pp ann return because the lighter_both overlay re-equilibrates most of the change.

**Recommended ML follow-up (NOT another portfolio-multiplier sprint):**
- A targeted retrain of the production `p_regime_confidence` model using the EXISTING Group A features (no refined-state, no macro proxies) but with the Target A definition (`stress_transition_4w` instead of the existing `regime_confidence` Sharpe-based label). The simpler target appears to be more learnable. This is a Phase 2B refresh, not a new phase.
- If the user wants deeper ML, the next step is to enlarge the portfolio integration surface — instead of dialing `regime_multiplier`, the ML score could inform `dynamic_speed`, `target_vol_ceil`, or per-sleeve weights. This is much more invasive and should only be considered if the simpler portfolio-multiplier path is truly closed.

## 26. If the ML path is paused, recommended next non-ML structural path

**Path #1 from the prior recommendation: W1 (`composite_structural_defense_sleeve`) in a separate defensive risk bucket.** The Phase HH/II/JJ sequence has now thoroughly explored regime-confidence-style interventions and the headroom there is small. The next natural direction is a structural allocator change: build a dual-bucket allocator that places offensive sleeves in one risk budget and defensive sleeves (including W1) in another, with state-conditional bucket-weight decisions. This requires meaningful architectural change but is the only remaining direction with material expected portfolio headroom that has not been tested.

## Appendix — protocol summary

- ML path: useful for retraining the Phase 2B regime-confidence model (Target A definition; Group A features only); refined-state features should NOT be added.
- Portfolio path: REJECT for production promotion; KEEP AS SHADOW per quick committee.
- Hard ML did not beat light ML on this dataset. Stop pursuing hard-ML approaches for this prediction problem.
- Refined-state features did not improve OOS prediction in a fitted model, contradicting the HH3 fixed-shift ablation. The walk-forward fit is the operationally relevant test.
