# Frontier Phase 6B: Decision Model Training and Validation Report

**Date:** 2026-05-22
**Mode:** Research-only — no production or dashboard files modified

---

## 1. Sprint Summary

Phase 6B trains walk-forward classifiers on Phase 6A decision labels. The primary target is `triple_barrier_label` (balanced 3-class). Portfolio meta-gate rules apply model probabilities to decide between FG, GGG, and 50%/GGG+BIL allocations.  Predeclared thresholds only.

---

## 2. Commands Run
```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier6_decision_model.py
```

---

## 3. Walk-Forward Setup

| parameter | value |
|-----------|-------|
| min_training_weeks | 260 |
| step_weeks | 26 |
| embargo_weeks | 4 |
| holdout_start | 2024-04-19 |
| model_a | LogisticRegression (C=1.0, balanced class weight) |
| model_b | GradientBoostingClassifier (max_depth=3, n_estimators=50) |

---

## 4. Classification Results (triple_barrier_label)

| model | scope | n | accuracy | balanced_accuracy |
|-------|-------|---|----------|------------------|
| GBM | dev | 720 | 0.375 | 0.345 |
| LogReg | dev | 720 | 0.393 | 0.392 |
| naive_always_majority | dev | 720 | 0.392 | 0.312 |
| naive_mdq_gt0 | dev | 1006 | 0.358 | 0.339 |
| naive_r2a_gt0 | dev | 1006 | 0.350 | 0.333 |
| GBM | full | 806 | 0.400 | 0.362 |
| LogReg | full | 806 | 0.396 | 0.397 |
| naive_always_majority | full | 806 | 0.417 | 0.315 |
| naive_mdq_gt0 | full | 1102 | 0.373 | 0.343 |
| naive_r2a_gt0 | full | 1102 | 0.366 | 0.340 |
| GBM | holdout | 86 | 0.605 | 0.565 |
| LogReg | holdout | 86 | 0.419 | 0.511 |
| naive_always_majority | holdout | 86 | 0.628 | 0.333 |
| naive_mdq_gt0 | holdout | 96 | 0.531 | 0.325 |
| naive_r2a_gt0 | holdout | 96 | 0.531 | 0.402 |

**Best model balanced_accuracy (full):** 0.397
**Best naive baseline balanced_accuracy (full):** 0.343
**Best model balanced_accuracy (holdout):** 0.565
**Best naive balanced_accuracy (holdout):** 0.402

---

## 5. Confusion Matrix (best model, full period)

Model: LogReg  (rows=actual, cols=predicted)
| actual \ predicted | -1 | 0 | +1 |
|--------------------|----|---|-----|
| -1 | 92 | 70 | 101 |
| 0 | 53 | 81 | 54 |
| 1 | 110 | 99 | 146 |

---

## 6. Portfolio Rule Results (full history)

Predeclared thresholds: Rule A loss_gate=0.45, Rule B good_gate=0.55, Rule C good/bad=0.60/0.60

| variant | Sharpe | Δ_vs_GGG | Max DD | Holdout Sharpe |
|---------|--------|----------|--------|----------------|
| ggg_baseline | 0.9362 | +0.0000 | -0.1177 | 2.1510 |
| fg_fragility_guard | 0.9483 | +0.0121 | -0.1160 | 2.1786 |
| rule_a_defensive_gate | 0.9147 | -0.0215 | -0.0925 | 2.0717 |
| rule_b_confidence_deploy | 0.9354 | -0.0008 | -0.1177 | 2.1463 |
| rule_c_tri_state | 0.9220 | -0.0142 | -0.1177 | 2.1510 |

---

## 7. Holdout Analysis (from 2024-04-19)

- GGG baseline holdout Sharpe: 2.1510
- Phase5 fragility_guard holdout Sharpe: 2.1786
- Best portfolio rule holdout Sharpe: 2.1510 (rule_c_tri_state)
- Rolling-origin win rate (best rule vs GGG): 33.3%
- Bootstrap P(best rule > GGG on holdout): 0.000

---

## 8. Stressed-Panic Preservation

| variant | sp_sharpe | Δ_vs_GGG |
|---------|-----------|----------|
| ggg_baseline | 0.4807 | +0.0000 |
| fg_fragility_guard | 0.4793 | -0.0014 |
| rule_a_defensive_gate | 0.5729 | +0.0923 |
| rule_b_confidence_deploy | 0.4807 | +0.0000 |
| rule_c_tri_state | 0.4733 | -0.0074 |

---

## 9. Overfitting Warnings

Phase 6 has the highest overfitting risk in the frontier arc.
Protections applied: walk-forward only, no tuning after seeing results, predeclared thresholds, simple models (max_depth=3), no holdout used for selection.
Key risk: the model has only ~850 out-of-sample training observations after the minimum window, and the feature set has 14 columns — overfitting risk is moderate.

---

## 10. Acceptance Gate Results

**✗ FAIL**

- ✓ Model balanced_accuracy (0.397) beats naive (0.343)
- ✓ Holdout balanced_accuracy (0.565) not worse than naive (0.402)
- ✓ Stressed-panic Sharpe preserved across all rules
- ✗ No portfolio rule beats GGG holdout Sharpe (2.1510), best rule: 2.1510

---

## 11. Verdict

**Keep as research-only diagnostic**

Model classification beats naive (bacc 0.397 vs 0.343) but portfolio rules do not improve holdout Sharpe. Research-only.

### Should Phase 6 feed into Phase 7?

Conditionally. The model's balanced_accuracy improvement over naive baseline (if any) suggests some signal exists. However, the inability to improve portfolio Sharpe on holdout means Phase 6 should NOT be used as an active portfolio modifier.

For Phase 7 (Cross-Asset Relational Intelligence):
- Use `phase5_master_deployment_quality` as the primary feature
- The model probability scores may be computed and stored as features
- Do NOT apply the portfolio rule switching in production

**The strongest frontier portfolio modifier remains `phase5_fragility_guard` (Phase 5A):**
All 8 Phase D gates passed. Full Δ+0.012, holdout Δ+0.028, bootstrap 84%.

---

## 12. Files Created

- `data/research/frontier_phase6/decision_model_predictions.csv`
- `data/research/frontier_phase6/decision_model_classification_metrics.csv`
- `data/research/frontier_phase6/decision_model_confusion_matrices.csv`
- `data/research/frontier_phase6/decision_model_portfolio_results.csv`
- `data/research/frontier_phase6/decision_model_holdout_summary.csv`
- `data/research/frontier_phase6/decision_model_state_summary.csv`
- `docs/research/frontier_phase6_decision_model_report.md`

## 13. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified