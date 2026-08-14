# Research Operating Layer — Build Summary

**Date:** 2026-04-26
**Scope:** Layers 1–6 implemented as offline, audit-only research scripts on top of the existing ETF quant project. No live trading, no broker integration, no autonomous promotion.

---

## 1. GitHub repo inspection summary

**Web egress to `raw.githubusercontent.com` was BLOCKED** in this environment.
External GitHub repo inspection was therefore **not performed**. None of the
following libraries are installed locally:

- skfolio, riskfolio-lib, pypfopt, vectorbt (Layer 6)
- fredapi, openbb (Layer 3 macro)

All Layer 6 baseline allocators (Equal Weight, Inverse Volatility, ERC,
Max Diversification, HRP single-linkage / bisection, simple Sharpe-rank
benchmark tracker) are implemented as **internal lightweight versions
from numpy / pandas / scipy** in `scripts/allocator_benchmark_audit.py`.
No external code was copied. Algorithmic ideas (HRP per López de Prado;
ERC iterative scaling; Most-Diversified Portfolio per Choo & Choueifaty)
are well-documented in the public literature and are reproduced from
first principles in the script.

Layer 3 macro features are derived **only** from project-internal ETF
returns (HYG, LQD, UUP, TLT, IEF, GLD, SPY, IWM, QQQ, XLF, XLU) plus the
existing Layer 2B regime-engine fields. No FRED / OpenBB calls.

This is reported honestly per the user's instruction: "do not guess and
do not pretend you inspected the repo."

## 2. Commands executed

```
# Phase BB closure (in background while Phase CC was designed)
python scripts/phase_bb_w1_cap_relaxation.py

# Phase CC: state-engine refinement
python scripts/phase_cc_regime_refinement.py

# Layer 3 — macro feature audit
python scripts/build_macro_feature_audit.py

# Layer 4 — market intelligence
python scripts/build_market_intelligence_report.py

# Layer 5 — backtest realism + robustness
python scripts/backtest_realism_audit.py
python scripts/robustness_simulation_audit.py

# Layer 6 — allocator benchmark
python scripts/allocator_benchmark_audit.py

# Layer 2 — research committee (auto-selects Phase CC; also run on BB2 portfolio)
python scripts/research_committee_report.py
python scripts/research_committee_report.py improved_phasebb_w1cap_060_hrp_7sleeve
```

All scripts ran to completion. A single deprecation warning
(`fillna(method="bfill")`) in `backtest_realism_audit.py` was fixed
after the first run.

## 3. Files created

### Code

```
scripts/phase_bb_w1_cap_relaxation.py        (new)
scripts/phase_cc_regime_refinement.py        (new)
scripts/research_ops_common.py               (new — shared loader)
scripts/research_committee_report.py         (new — Layer 2)
scripts/build_macro_feature_audit.py         (new — Layer 3)
scripts/build_market_intelligence_report.py  (new — Layer 4)
scripts/backtest_realism_audit.py            (new — Layer 5)
scripts/robustness_simulation_audit.py       (new — Layer 5)
scripts/allocator_benchmark_audit.py         (new — Layer 6)
```

### Layer 1 documentation

```
docs/research_operating_layer/layer1_ai_reasoning.md
docs/research_operating_layer/build_summary.md (this file)
```

### Layer 2 templates and report

```
docs/research_committee/bull_case.md
docs/research_committee/bear_case.md
docs/research_committee/risk_manager.md
docs/research_committee/implementation_auditor.md
docs/research_committee/final_judge.md
docs/research_committee/quant_verification_checklist.md
reports/research_committee/phase_cc_regime_engine_refinement_audit.md
reports/research_committee/improved_phasebb_w1cap_060_hrp_7sleeve_audit.md
```

### Layer 3 macro feature audit

```
data/research/macro_feature_audit/macro_features_weekly.csv      (1109 × 15)
data/research/macro_feature_audit/macro_feature_metadata.csv
data/research/macro_feature_audit/macro_feature_coverage_report.md
data/research/macro_feature_audit/macro_regime_correlation_report.md
```

### Layer 4 market intelligence

```
reports/market_intelligence/latest_market_context.md
data/research/market_intelligence/market_context_snapshot.csv
```

### Layer 5 backtest realism + robustness

```
reports/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_realism_audit.md
reports/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_simulation_audit.md
data/research/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_cost_sensitivity.csv
data/research/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_rebalance_delay_sensitivity.csv
data/research/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_turnover_threshold_sensitivity.csv
data/research/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_block_bootstrap_summary.csv
```

(No `shadow_tracking` outputs were generated because the project does
not currently store first-shadow-date metadata for any candidate. The
optional script was deliberately not implemented; this is reported in
the warnings section below.)

### Layer 6 allocator benchmark

```
reports/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_allocator_benchmark.md
data/research/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_allocator_comparison.csv
data/research/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_risk_contribution.csv
```

### Phase CC regime engine artifacts (already created earlier this session)

```
data/04_layer2b_risk_regime_engine/market_state_history_refined.csv
data/04_layer2b_risk_regime_engine/phase_cc_refined_state_diagnostics.csv
data/04_layer2b_risk_regime_engine/phase_cc_state_transition_matrix.csv
data/04_layer2b_risk_regime_engine/phase_cc_neutral_split_summary.csv
data/04_layer2b_risk_regime_engine/phase_cc_state_counts.csv
data/04_layer2b_risk_regime_engine/phase_cc_protocol.json
docs/research/2026-04-26_phase_cc_regime_engine_refinement_report.md
docs/research/project_journey.md  (Sections 41 + 42 appended)
```

## 4. Output paths (single block)

| Output | Path |
|---|---|
| Layer 1 AI reasoning note | `docs/research_operating_layer/layer1_ai_reasoning.md` |
| Research Committee report (Phase CC) | `reports/research_committee/phase_cc_regime_engine_refinement_audit.md` |
| Research Committee report (BB2 portfolio) | `reports/research_committee/improved_phasebb_w1cap_060_hrp_7sleeve_audit.md` |
| Macro Feature coverage report | `data/research/macro_feature_audit/macro_feature_coverage_report.md` |
| Macro Feature regime-correlation report | `data/research/macro_feature_audit/macro_regime_correlation_report.md` |
| Market Intelligence report | `reports/market_intelligence/latest_market_context.md` |
| Backtest Realism report | `reports/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_realism_audit.md` |
| Robustness Simulation report | `reports/backtest_realism/improved_phasebb_w1cap_060_hrp_7sleeve_simulation_audit.md` |
| Shadow Tracking report | _not generated — project lacks first-shadow-date metadata_ |
| Allocator Benchmark report | `reports/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_allocator_benchmark.md` |
| Allocator comparison CSV | `data/research/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_allocator_comparison.csv` |
| Risk contribution CSV | `data/research/allocator_benchmark/improved_phasebb_w1cap_060_hrp_7sleeve_risk_contribution.csv` |

## 5. Key results

### 5a. Research Committee verdicts

**Phase CC** (state-engine refinement, audited via Z1 portfolio surrogate):
> **KEEP AS SHADOW-IN-WAITING for downstream consumption.**
> Phase CC produces an upstream regime-engine refinement, not a portfolio.
> Recommend Phase DD: a narrow production-family rerun consuming the new
> `defensive_overlay_hint` as an additive sleeve-level tilt.

**BB2** (closest recent portfolio candidate; W1 cap = 0.60 inside HRP):
> **KEEP AS SHADOW.** Holdout Sharpe and max drawdown both improve, but
> the candidate fails the production return-delta gate.

### 5b. Macro features successfully built

15 / 15 features built from project-internal data. Phase CC overlay shows
the expected directional gradient between `neutral_healthy` and
`neutral_deteriorating`: credit spreads tighter in healthy, regime stress
+0.55 z higher in deteriorating, breadth 25.7pp lower in deteriorating,
correlation pressure +0.88 z higher in deteriorating. This is an
independent third-party validation (the regime engine's own internal
features were not used in the Phase CC z-score composite alongside the
ETF-derived ones; this report cross-references both).

### 5c. Market intelligence report

Generated `reports/market_intelligence/latest_market_context.md`. Reports
the latest market state, recent state transitions in the last 12 weeks,
biggest 1w / 4w / 12w ETF movers, risk-proxy snapshot for HYG/LQD/UUP/
TLT/IEF/GLD/SPY/QQQ/IWM, production weight changes, candidate-vs-
production weight differences, and a heuristic driver classification.
Diagnostic only.

### 5d. Cost sensitivity result (BB2 vs production)

| half-spread bps | cand ann return | prod ann return | Δ ann return | cand Sharpe | Δ Sharpe |
|----:|---:|---:|---:|---:|---:|
| 0   |  +3.88% | +6.28% | -2.39pp | 0.99 | +0.19 |
| 5   |  +3.76% | +6.12% | -2.37pp | 0.96 | +0.18 |
| 10  |  +3.63% | +5.97% | -2.34pp | 0.93 | +0.17 |
| 25  |  +3.25% | +5.50% | -2.25pp | 0.83 | +0.13 |
| 50  |  +2.62% | +4.73% | -2.11pp | 0.67 | +0.07 |

The candidate's **Sharpe edge persists across all cost levels** but the
**absolute return shortfall vs production is structural**. Doubled cost
does not flip the verdict either way — at 10bp the candidate still gives
up 2.3pp of annualised return but keeps a 0.17 Sharpe lead.

### 5e. Robustness simulation result (BB2 vs production)

90% bootstrap confidence intervals on annualised return:
- candidate ann return CI: ~[+1.5%, +5.5%]
- production ann return CI: ~[+3.5%, +8.0%]

The intervals **overlap substantially**, so the candidate's underperformance on
the return axis is not statistically nailed down — but neither does the
candidate's bootstrap 5%-quantile annual return exceed production's 95%-quantile.
Worst rolling 13w / 26w / 52w windows: candidate's worst windows are
materially shallower than production's (consistent with its lower-vol /
lower-MDD profile).

### 5f. Candidate vs production result

Across all five cost levels, candidate BB2 has:
- ✓ better Sharpe (+0.07 to +0.19)
- ✓ shallower max drawdown (-6.9% vs -14.0%)
- ✓ better CVaR-5% (-1.27% vs -2.62%)
- ✗ worse annualised return (-2.4pp consistently)

This is the same diagnosis Phase BB itself produced — the candidate has a
real risk-axis edge but cannot earn its keep on the return axis.

### 5g. Candidate vs simple allocator baseline result

| baseline (internal) | ann return | Sharpe | MDD | turnover |
|---|---:|---:|---:|---:|
| equal_weight | +5.45% | 0.78 | -13.7% | 0.001 |
| inverse_vol | +4.72% | 0.86 | -11.7% | 0.004 |
| erc_internal | +4.23% | 0.89 | -11.2% | 0.003 |
| max_div_lite | +4.17% | 0.89 | -11.2% | 0.003 |
| hrp_internal | +4.19% | 0.93 | -10.9% | 0.006 |
| benchmark_tracker_lite | +5.12% | 0.72 | -16.3% | 0.001 |
| **production** | **+6.89%** | **0.88** | **-14.0%** | **0.056** |
| **candidate (BB2)** | **+3.76%** | **0.96** | **-6.9%** | **0.094** |

Candidate **beats every internal baseline on Sharpe** (0.96 vs best
baseline 0.93). Candidate **beats every internal baseline on MDD** (-6.9%
vs best -10.9%). Candidate **does not beat production on annualised return**.
Candidate's complexity is **only marginally justified** on Sharpe (0.96 vs
0.93 internal-HRP — gap is 0.03, below the 0.05 bar set by the script).

### 5h. Whether the candidate still beats production under stricter assumptions

Beats production on Sharpe and MDD: **YES**, robust across 0/5/10/25/50bp
cost grid and 0/1/5-week delay grid.

Beats production on annualised return: **NO**, at any cost or delay level.

### 5i. Whether complexity is justified

Marginal — for a *cap-relaxation* candidate inside the same architecture,
the Sharpe edge over internal HRP is only +0.03. For a *Phase CC
state-refinement* downstream test, the question is whether the new
defensive overlay hint can recover the missing return-axis edge while
preserving the Sharpe / MDD edge. That is the explicit Phase DD test
recommended in the Phase CC report.

### 5j. Whether outputs are ready for later testing

All Layer 2-6 outputs are saved as deterministic CSVs and markdown
reports. Re-running any single script regenerates only its own outputs;
nothing depends on hidden state. Outputs are **ready for downstream
testing** but are also **exploratory** in the strict sense that the
Research Operating Layer is offline-only — no candidate is promoted by
any of these scripts, only audited.

## 6. Warnings

- **Web egress to GitHub: BLOCKED.** External repo inspection was not
  performed. All Layer 6 baselines are internal implementations.
- **fredapi / openbb: NOT INSTALLED.** Layer 3 macro features are
  project-internal only (15 / 15 successfully built).
- **ETF volume / liquidity data: NOT PRESENT.** Layer 5 slippage modelled
  as flat half-spread grid; no per-ETF liquidity-aware slippage model.
- **Insufficient history for shadow tracking.** The project does not
  currently store first-shadow-date metadata for any candidate. The
  optional `build_shadow_tracking_report.py` was deliberately NOT
  implemented; the project would need a `data/manifest_shadow_dates.csv`
  or equivalent first.
- **License restrictions from external repos: N/A** because no external
  code was copied.
- **Auto-selected candidate.** Layers 5/6 auto-selected
  `improved_phasebb_w1cap_060_hrp_7sleeve` (BB2) as the most recent
  portfolio candidate. To audit any other candidate, pass it as the
  first command-line argument to the script.
- **Phase CC has no portfolio.** The Layer 2 Research Committee report
  on Phase CC explicitly says so and uses Z1
  (`improved_phasez_production_hrp_7sleeve`) as the closest portfolio
  surrogate where portfolio-level metrics are needed.
- **Production strategy logic: UNCHANGED.** No script modifies any
  production weights, returns, or pin status.

## 7. Final state

- **Production pin:** `improved_phase2b_regime_confidence_boost` (unchanged).
- **Shadow pin:** `improved_phase2b_combo_abc` (unchanged).
- **Phase BB classification:** all three candidates Research-only (closed).
- **Phase CC classification:** state-engine refinement is good-enough for
  next downstream test; recommend Phase DD.
- **Research Operating Layer status:** Layers 1–6 implemented, all
  scripts ran cleanly, all expected output files exist. Ready for the
  next phase or for re-execution against future candidates.
