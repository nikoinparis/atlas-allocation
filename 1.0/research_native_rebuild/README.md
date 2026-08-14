# Path B — Shadow Native Rebuild

**Status: SCAFFOLD ONLY (Sprint 0)**
**Created: 2026-06-07**
**Production pin (champion benchmark): `improved_frontier_phase5_fragility_guard`**
**Sharpe: 0.9542 | Holdout Sharpe: 2.0479 | AnnRet: 7.18% | MaxDD: -11.60%**

---

## What This Is

Path B is a completely isolated research sandbox for testing whether a **native rebuild** of the
portfolio system — with macro, credit, trend, and transition-cost awareness built into the regime
engine from the start — can outperform the existing production pin.

This is NOT:
- A production replacement
- A post-hoc overlay (those are closed — see experiment log)
- An optimization of existing parameters
- A live deployment

This IS:
- An isolated research architecture
- A clean apples-to-apples equivalence framework
- A forward-looking experiment plan
- A place to test whether the V3 macro/credit signal can be integrated natively

---

## Why Path B Exists

Steps 2, 2B, and 2C exhausted all overlay implementation paths for the V3 NM+slowdown+FC_benign
macro signal:

| Sprint | Best ΔSharpe | Min TO_increase | G1 | G6 |
| --- | --- | --- | --- | --- |
| Step 2 (ETF tilt overlay) | +0.0049 | 0.170 | FAIL | FAIL |
| Step 2B (persistent modifier) | +0.0145 | 0.084 | PASS | FAIL |
| Step 2C (near-zero calibration) | +0.0194 | 0.057 | PASS | FAIL |

The signal is real (G1 passes in Step 2B and 2C) but cannot be profitably overlaid onto the
existing architecture because the existing regime engine's NM transition frequency (8.9/yr) makes
the turnover gate (≤0.03/yr) structurally unreachable via any post-hoc overlay.

**Path B hypothesis**: If macro conditioning is built natively into the regime engine, so that
state transitions themselves encode the macro/credit distinction (rather than adding an overlay
on top of existing states), the signal can be exploited without additional rebalancing episodes.

---

## Sprint Plan

| Sprint | Goal | Status |
| --- | --- | --- |
| **Sprint 0** | Scaffold + design memo + equivalence framework | **IN PROGRESS** |
| Sprint 0.5 | Equivalence audit — verify all non-target components match production | NOT STARTED |
| Sprint 1 | Native feature panel (raw inputs, no architecture decisions) | NOT STARTED |
| Sprint 2 | Native regime engine with hysteresis and transition penalties | NOT STARTED |
| Sprint 3 | Regime-specific signal weighting (walk-forward IC, shrinkage) | NOT STARTED |
| Sprint 4 | Native risk budgets (state-specific offense/defense/fragility) | NOT STARTED |
| Sprint 5 | Portfolio backtest vs production pin | NOT STARTED |
| Sprint 6 | Robustness, gates, final verdict | NOT STARTED |

**No performance claims are allowed before Sprint 5.**
**Production pin remains the champion until Sprint 6 gate checks pass.**

---

## What Path B May Change (Intentional Differences)

1. Native regime engine states (may add `neutral_soft_landing` etc.)
2. Macro/credit conditioning as native regime features
3. State persistence / hysteresis / transition penalties
4. State-specific signal weighting (walk-forward IC only)
5. State-specific risk budgets
6. Turnover-aware regime-state transition behavior

## What Path B Must NOT Change

- ETF universe (35 ETFs)
- Weekly data framing and date index
- Lag/timing convention (1-week execution delay, causal signals)
- Return calculation convention
- Transaction cost model (10 bps per unit turnover)
- Holdout split (2024-04-19 onward, 104 weeks)
- Phase D promotion gates
- Benchmark comparison to production pin
- No leverage, no short selling, weights sum to 1

---

## Directory Structure

```
research_native_rebuild/
  README.md                          ← This file
  configs/
    native_rebuild_config.yaml       ← Global parameters
    validation_gates.yaml            ← Promotion gate definitions
    equivalence_requirements.yaml    ← What must match production
  data_contracts/
    required_inputs.md               ← All required input files
    artifact_manifest.md             ← Output artifacts specification
  scripts/
    00_compare_production_shadow_contract.py  ← Equivalence verifier
    01_build_native_feature_panel.py          ← Feature engineering
    02_build_native_regime_engine.py          ← Regime state builder
    03_build_native_signal_weighting.py       ← Walk-forward IC weights
    04_build_native_risk_budgets.py           ← State risk parameters
    05_run_native_portfolio_backtest.py       ← Full backtest
    06_compare_to_production.py              ← Gate + comparison
  outputs/
    feature_panel/
    regime_engine/
    signal_weighting/
    risk_budgets/
    portfolio_backtest/
    comparison/
  docs/
    design_memo.md                   ← Architecture + rationale
    experiment_log.md                ← Sprint history
    production_vs_shadow_equivalence_map.md  ← Apples-to-apples map
    final_verdict.md                 ← Verdict (placeholder)
```

---

## Key Files (Production, Read-Only)

| File | Purpose |
| --- | --- |
| `data/01_data_hub/weekly_prices.csv` | 35 ETFs, weekly, 2005-2026 |
| `data/01_data_hub/macro_weekly.csv` | FRED macro (currently empty) |
| `data/01_data_hub/vix_term_structure.csv` | VIX spot/term structure |
| `data/01_data_hub/google_trends.csv` | Google fear composite |
| `data/04_layer2b_risk_regime_engine/market_state_history.csv` | Production market states |
| `data/04_layer2b_risk_regime_engine/regime_score.csv` | Production regime scores |
| `data/05_layer3_portfolio_construction/portfolio_version_*_improved_frontier_phase5_fragility_guard.csv` | Production pin artifacts |
| `outputs/experiment_results/macro_regime_classifier_v3/macro_states_weekly_v3.csv` | V3 macro states |

**None of these files are written to by this research program.**

---

## Contact / Governance

All Path B scripts write only to `research_native_rebuild/outputs/`.
No script in this folder may write to `data/`, `outputs/experiment_results/`, or any production path.
Production pin promotion requires explicit human authorization — not automated.
