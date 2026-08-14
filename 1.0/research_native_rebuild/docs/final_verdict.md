# Path B — Final Verdict

**Status: SCAFFOLD ONLY — NO PERFORMANCE CLAIMS**
**Date created: 2026-06-07**
**Sprint: 0 (Scaffold)**

---

## Current Status

Path B is in Sprint 0. **No backtest has been run. No performance claims can be made.**

The following statements are true as of this date:

- The production pin `improved_frontier_phase5_fragility_guard` (Sharpe 0.9542, holdout
  Sharpe 2.0479) is the **undisputed champion** and remains so until Sprint 6 gates are cleared.
- Path B has not proven any improvement over production.
- Path B has not proven any harm to production.
- Path B exists only as a scaffold and design framework.

---

## What Must Happen Before a Verdict Is Possible

### Sprint 0.5 — Equivalence Audit
All NEEDS_TEST and UNKNOWN items in the equivalence map must be resolved before the backtest
is run. Specifically:
- [ ] Weekly date index verified to match production exactly
- [ ] Return calculation convention verified to <1e-10 tolerance
- [ ] Transaction cost convention verified to match production
- [ ] Holdout split verified to match exactly (2024-04-19)
- [ ] Baseline metrics from production pin reproduced exactly in shadow framework
- [ ] All non-target differences documented and justified

### Sprint 1 — Native Feature Panel
- [ ] Feature panel built with all 1-week causal lags enforced
- [ ] V3 macro features confirmed available and correctly lagged
- [ ] Signal E_4wk reconstructable from native features
- [ ] No lookahead contamination in any feature

### Sprint 2 — Native Regime Engine
- [ ] Minimum 30 dev observations per new state
- [ ] Hysteresis parameters set without using holdout returns
- [ ] State boundaries not tuned for Sharpe
- [ ] stressed_panic protection preserved or strengthened
- [ ] calm_trend not inadvertently changed

### Sprint 3 — Signal Weighting
- [ ] Walk-forward IC only (no in-sample look-ahead)
- [ ] Shrinkage applied to IC estimates
- [ ] Minimum observation requirement enforced

### Sprint 4 — Risk Budgets
- [ ] State-specific parameters set using economic logic, not Sharpe maximization
- [ ] No hidden leverage
- [ ] Hard constraints preserved

### Sprint 5 — Portfolio Backtest
- [ ] Shadow portfolio constructed with verified equivalence components
- [ ] All non-target components confirmed to match production
- [ ] Metrics computed using identical convention as production

### Sprint 6 — Robustness + Gates
Gates required for PROMOTE_TO_PHASE_D_TEST:
- [ ] Full-history Sharpe improvement ≥ +0.01 vs production pin
- [ ] Holdout Sharpe not worse than production by more than 0.02
- [ ] Annual return improves or remains neutral
- [ ] Max drawdown worsens by no more than 1pp
- [ ] CVaR 5% does not materially worsen
- [ ] Annual turnover increase ≤ 0.03 (the gate that closed overlay path)
- [ ] 2x transaction cost sensitivity does not erase improvement
- [ ] stressed_panic protection preserved
- [ ] recovery_fragile not materially harmed
- [ ] No state with fewer than 30 dev observations
- [ ] No result driven entirely by 2020 or 2024-2025 AI rally
- [ ] Rolling 104-week win rate ≥ 55% if available
- [ ] Bootstrap / robustness checks pass for finalists

**Human authorization required before any promotion.**

---

## Provisional Verdict

```
VERDICT: SCAFFOLD ONLY — NO PERFORMANCE CLAIMS
Champion: improved_frontier_phase5_fragility_guard
Shadow status: Not yet run
Next milestone: Sprint 0.5 (equivalence audit)
```

This file will be updated at each sprint completion.

---
*No production artifacts modified. No promotion.*
