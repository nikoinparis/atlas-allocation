# Frontier Phase 6A: Decision-Focused Learning Label Construction Report

**Date:** 2026-05-21
**Mode:** Diagnostic-only — no production or dashboard files modified
**IMPORTANT: No model was trained. No feature-label correlations were computed.**

---

## 1. Sprint Summary

Phase 6A builds five predeclared decision-quality labels using forward returns from `phase5_fragility_guard` and the GGG baseline.  The labels capture when the frontier candidate beats the baseline, when deploying was a good decision, and when staying with the baseline would have been better.  Labels are validated for usability and class balance before Phase 6B model training.

---

## 2. Commands Run

```
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓
.venv/bin/python scripts/run_deployment_rule_harness.py          # ✓
.venv/bin/python scripts/phase_frontier6_decision_labels.py
```

---

## 3. Predeclared Label Parameters

*These parameters are locked. They must not change after running.*

| parameter | value |
|-----------|-------|
| horizon_weeks | 8 |
| lag_weeks (feature) | 1 |
| deploy_profit_barrier | +0.020 (+2.0%) |
| deploy_loss_barrier | -0.012 (-1.2%) |
| frontier_beats_margin | +0.0025 (+0.25bp) |
| rerisk_margin | +0.010 (+1.0%) |
| deploy_min_sharpe | 0.5 |
| holdout_start | 2024-04-19 |
| embargo_weeks | 4 |

---

## 4. Label Definitions

| label | definition |
|-------|-----------|
| `frontier_beats_ggg_label` | 1 if FG 8w cumulative return > GGG 8w cumulative return + 0.25pp |
| `deploy_quality_label` | 1 if FG 8w return ≥ 0 AND FG 8w annualised Sharpe ≥ 0.5 |
| `triple_barrier_label` | +1 if +2% profit hit before -1.2% loss within 8w; -1 if loss first; 0 if neither |
| `conservative_override_label` | 1 if GGG 8w return > FG 8w return + 0.25pp (stay with baseline) |
| `rerisk_quality_label` | Recovery states only: 1 if FG beats BIL by ≥1% over next 8w |

**Leakage check:** All labels use forward returns (t+1..t+8) only. All features in the snapshot use backward-looking data only.

---

## 5. Dataset

- Total rows: 1110
- Date range: 2005-01-07 → 2026-04-10
- Development window: up to 2024-04-19 (1006 rows)
- Holdout window: from 2024-04-19 (104 rows)
- Recovery rows (confirmed+fragile): 93

---

## 6. Full-History Label Distributions

| label | n | base_rate(+1) | pct_pos | pct_zero | pct_neg |
|-------|---|-------------|---------|----------|---------|
| frontier_beats_ggg_label | 1102 | 2.81% | 2.81% | 97.19% | 0.00% |
| deploy_quality_label | 1033 | 62.83% | 62.83% | 37.17% | 0.00% |
| triple_barrier_label | 1102 | 42.20% | 42.20% | 27.68% | 30.13% |
| conservative_override_label | 1102 | 2.18% | 2.18% | 97.82% | 0.00% |
| rerisk_quality_label | 92 | 67.39% | 67.39% | 32.61% | 0.00% |

---

## 7. Development vs Holdout Base Rates

| label | dev_n | dev_base_rate | holdout_n | holdout_base_rate |
|-------|-------|--------------|-----------|------------------|
| frontier_beats_ggg_label | 1006 | 3.08% | 96 | 0.00% |
| deploy_quality_label | 937 | 60.94% | 96 | 81.25% |
| triple_barrier_label | 1006 | 40.06% | 96 | 64.58% |
| conservative_override_label | 1006 | 2.39% | 96 | 0.00% |
| rerisk_quality_label | 79 | 63.29% | 13 | 92.31% |

---

## 8. By Market State (`frontier_beats_ggg_label`)

| state | n | base_rate |
|-------|---|-----------|
| calm_trend | 295 | 6.10% |
| neutral_mixed | 488 | 1.84% |
| recovery_confirmed | 43 | 9.30% |
| recovery_fragile | 49 | 0.00% |
| stressed_panic | 227 | 0.00% |

---

## 9. Class Imbalance Warnings

- ⚠ frontier_beats_ggg_label: extreme imbalance (base_rate=2.81%) — too few positive examples for reliable learning
- ⚠ conservative_override_label: extreme imbalance (base_rate=2.18%) — too few positive examples for reliable learning

---

## 10. Usability Assessment

**⚠ WARNINGS**

- ✓ deploy_quality_label: n=1033, base_rate=62.83%
- ✓ triple_barrier_label: n=1102, pos=42.2%, zero=27.7%, neg=30.1%
- ✓ rerisk_quality_label: n=92, base_rate=67.39%
- ⚠ frontier_beats_ggg_label: extreme imbalance (base_rate=2.81%) — too few positive examples for reliable learning
- ⚠ conservative_override_label: extreme imbalance (base_rate=2.18%) — too few positive examples for reliable learning

---

## 11. Structural Diagnosis

**`frontier_beats_ggg_label` and `conservative_override_label` are fundamentally too sparse.** The Phase 5 fragility_guard and GGG baseline are so similar in weekly returns (full-history annualized difference: −0.01pp) that the 0.25pp margin over any 8-week window is almost never exceeded. The holdout has **0% positive examples** for `frontier_beats_ggg_label` — completely unusable for model evaluation.

This is not a parameter choice issue; it is a structural property of the two return series. Even without the 0.25pp margin, the raw "FG beats GGG" probability over 8 weeks would only slightly exceed 50%.

**The three usable labels are:**

| label | base_rate | class balance | usability |
|-------|-----------|--------------|-----------|
| `triple_barrier_label` | +42% / 0=28% / -30% | Excellent | ✓ Primary Phase 6B target |
| `deploy_quality_label` | 62.8% | Acceptable | ✓ Binary secondary target |
| `rerisk_quality_label` | 67.4% (n=92) | Acceptable (small n) | ✓ Recovery-state target |

**`triple_barrier_label` is the correct primary Phase 6B target.** It is balanced (42%/28%/30%), captures the portfolio's profit/loss trajectory independent of the GGG comparison, and has enough observations across all states.

---

## 12. Verdict

**Revise labels once — replace `frontier_beats_ggg_label` and `conservative_override_label`**

The two FG-vs-GGG comparison labels are structurally unusable because the return series are too similar to generate sufficient positive examples. The triple_barrier, deploy_quality, and rerisk_quality labels are usable.

**For Phase 6B, proceed with the following revised targets:**

1. **Primary:** `triple_barrier_label` — well-balanced 3-class label
2. **Secondary:** `deploy_quality_label` — binary (63% positive, manageable imbalance)
3. **Recovery-state only:** `rerisk_quality_label` — small n but usable for targeted analysis

**Do NOT use** `frontier_beats_ggg_label` or `conservative_override_label` in Phase 6B model training.

**These predeclared parameters remain locked:**
- triple_barrier: profit=+2.0%, loss=−1.2%, horizon=8w ✓
- deploy_quality: return≥0, Sharpe≥0.5, horizon=8w ✓

### Phase 6B Readiness Checklist

When Phase 6B is implemented, it must follow these rules:
- Walk-forward expanding windows only (no k-fold)
- Minimum training window: 260 weeks before first prediction
- Purged cross-validation: 4-week embargo at train/test boundary
- Model: calibrated logistic regression or GBM (max_depth ≤ 3)
- **Primary target: `triple_barrier_label`** (replace `frontier_beats_ggg_label`)
- Features: causal-only Phase 1–5 quality signals (from the snapshot in `decision_labels.csv`)
- Report: out-of-sample accuracy AND phase5_fragility_guard Sharpe on holdout
- DO NOT select model hyperparameters using holdout performance
- DO NOT change the label parameters above after this run

---

## 12. Files Created

- `data/research/frontier_phase6/decision_labels.csv`
- `data/research/frontier_phase6/decision_label_distribution_summary.csv`
- `data/research/frontier_phase6/decision_label_state_summary.csv`
- `docs/research/frontier_phase6_decision_labels_report.md`

## 13. Production Safety

- Protected file diff: **✓ Clean**
- Production pins: unchanged
- No public/, src/, dashboard files modified
- No model was trained. No feature-label correlations were computed.