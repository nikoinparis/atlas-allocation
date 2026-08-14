# Phase 3.2 Refinement Sprint — Close the 0.001 Gap on Combo1

**Sprint scope:** narrow refinement of the single Phase 3.1 near-winner `Combo1 = C1a + A1g`.
**Dual-track baselines (pinned):**
- **A (production pin):** `improved_phase2b_regime_confidence_boost`
- **F (shadow pin):** `improved_phase2b_combo_abc`

**Promotion gates (vs A):**
- composite ≥ +0.05
- max drawdown within 0.005
- CVaR-5% within 0.002
- turnover not meaningfully worse (heuristic: ≤ +0.003 weekly)

---

## A. What you changed

All edits live in `scripts/build_improvement_artifacts.py`.

1. **`_apply_sector_state_gate`** — extended to accept a configurable `gate_states` frozenset. Default (used by C1a+A1g = Combo1) stays `{recovery_fragile, recovery_confirmed}`. Phase 3.2 R1/R3 pass `{recovery_confirmed}` only.
2. **`_apply_sector_dd_guard`** — new helper. Causal step-function on `market_state_row.market_drawdown`:
   - `md ≤ -0.10` → sector sleeve weight × 0.00
   - `-0.10 < md ≤ -0.05` → sector sleeve weight × 0.50
   - else unchanged.
   Applied *after* the state gate, so it only kicks in when the state gate already lets sector participate.
3. **`apply_state_conditioned_tilt`** — added three new tilt modes so R1/R2/R3 each get a distinct wiring:
   - `dynamic_risk_budget_state_leader_wider_sector_gated_tight` (R1)
   - `dynamic_risk_budget_state_leader_wider_sector_gated_dd_guard` (R2)
   - `dynamic_risk_budget_state_leader_wider_sector_gated_tight_dd_guard` (R3)
4. **Main walk-forward loop** — extended the conviction-and-state-lead dispatch sets so R1/R2/R3 all receive both the C1a conviction and the ±0.15 state-lead tilt.
5. **Three new version specs appended:**
   - `improved_phase3_2_combo_tight_gate` (R1)
   - `improved_phase3_2_combo_dd_guard` (R2)
   - `improved_phase3_2_combo_tight_gate_dd_guard` (R3)
   All three share subset = improved_subset + `sector_rotation_with_sma_filter`, overlay `good_state_fragile_expression`, HRP, `regime_confidence_boost`, penalty `lighter_both_targeted_narrow_plus_confirmed`.

Pins were **not** touched. No changes to Layer 1 signals, sleeves, or the Phase 2B regime engine.

## B. What you executed

1. AST-checked the edits (`ast.parse` → OK).
2. Ran the full pipeline: `nohup python3 -u scripts/build_improvement_artifacts.py`. Exit 0. All ~60 portfolio versions rebuilt, including A, F, the four Phase 3.1 variants, and the three Phase 3.2 variants.
3. Rebuilt `public/dashboard-data.json` via `node scripts/build-dashboard-data.mjs` (10 methods; pins unchanged).
4. Extracted metrics from `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv` and computed deltas vs both A and F.

## C. Research lens (brief)

The Phase 3.1 analysis concluded that Combo1's residual friction was DD/turnover in recovery states. Two mechanically distinct hypotheses follow:

- **Tightening the gate** (R1): sector only fires in `recovery_confirmed`. Keeps the highest-signal-to-noise slice, drops fragile-state noise.
- **DD-proximity guard** (R2): sector scales down or off when `market_drawdown` is deep, using the causal state-row value. Disarms the sleeve exactly when participation would be costly.
- **Both** (R3): strictest — if R2 is saving something R1 loses, or vice versa, R3 should dominate.

This is a causal, non-hindsight design: the gate and guard only read walk-forward available market-state features.

## D. Experimental results

All metrics from `portfolio_version_comparison.csv` (this run). Composite (`production_score`) is rank-weighted over the full pool, so it shifts when the pool shifts — see note in section E.

| variant | Sharpe | MaxDD | Calmar | CVaR5% | Turn (w) | UpCap | DnCap | Rec | RecFrag | RecConf | Calm | StressDn | BIL | SPY | Cash | Prod |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **A** (prod pin) | 0.884 | −13.98% | 0.493 | −2.62% | 0.0562 | 32.4% | 23.9% | 30.4% | 28.1% | 39.4% | 43.4% | 30.6% | 28.4% | 7.08% | 16.2% | 0.7336 |
| **F** (shadow pin) | 0.884 | −13.67% | 0.502 | −2.61% | 0.0566 | 32.3% | 23.9% | 29.6% | 27.3% | 38.7% | 43.5% | 31.1% | 28.6% | 7.08% | 16.4% | 0.7088 |
| C1a (Phase 3.1) | 0.888 | −13.86% | 0.498 | −2.61% | 0.0561 | 32.4% | 23.8% | 30.3% | 27.9% | 39.3% | 42.9% | 30.6% | 28.4% | 7.08% | 16.2% | 0.7787 |
| C1b (Phase 3.1) | 0.887 | −13.85% | 0.498 | −2.61% | 0.0561 | 32.4% | 23.9% | 30.3% | 28.0% | 39.3% | 43.1% | 30.6% | 28.4% | 7.08% | 16.2% | 0.7776 |
| A1g (Phase 3.1) | 0.906 | −14.45% | 0.490 | −2.64% | 0.0580 | 33.2% | 24.5% | 38.2% | 30.6% | 67.5% | 43.7% | 25.8% | 28.4% | 6.79% | 16.2% | 0.6805 |
| **Combo1** (C1a+A1g, 3.1) | **0.910** | **−14.19%** | 0.499 | −2.63% | 0.0578 | 33.2% | 24.4% | 38.3% | 30.5% | **68.1%** | 43.4% | 25.8% | 28.4% | 6.79% | 16.2% | **0.7884** |
| **R1** tight_gate | 0.892 | −14.19% | 0.489 | −2.62% | 0.0572 | 32.7% | 24.2% | 32.5% | 25.4% | 60.0% | 43.3% | 26.4% | 28.4% | 6.86% | 16.2% | 0.7381 |
| **R2** dd_guard | 0.907 | −14.19% | 0.497 | −2.63% | 0.0572 | 33.0% | 24.3% | 35.8% | 27.9% | 66.2% | 43.3% | 25.8% | 28.4% | 6.80% | 16.2% | 0.7761 |
| **R3** tight+guard | 0.892 | −14.19% | 0.489 | −2.62% | 0.0572 | 32.7% | 24.2% | 32.5% | 25.4% | 60.0% | 43.3% | 26.4% | 28.4% | 6.86% | 16.2% | 0.7381 |

Deltas vs **A** (composite gate +0.05):

| variant | Δ prod | Δ Sharpe | Δ DD | Δ CVaR5 | Δ turn | Δ Calm | Δ RecConf | Δ RecFrag | Δ StressDn |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Combo1 (3.1) | **+0.0548** | +0.026 | −0.0022 | −0.0001 | +0.0016 | −0.0003 | **+28.67 pp** | +2.48 pp | −4.77 pp |
| R1 | +0.0045 | +0.008 | −0.0022 | −0.0001 | +0.0010 | −0.0019 | +20.54 pp | −2.69 pp | −4.23 pp |
| R2 | +0.0425 | +0.022 | −0.0022 | −0.0001 | +0.0010 | −0.0019 | +26.76 pp | −0.15 pp | −4.77 pp |
| R3 | +0.0045 | +0.008 | −0.0022 | −0.0001 | +0.0010 | −0.0019 | +20.54 pp | −2.69 pp | −4.23 pp |

Deltas vs **F** (shadow):

| variant | Δ prod | Δ Sharpe | Δ DD | Δ CVaR5 | Δ turn | Δ RecConf |
|---|---:|---:|---:|---:|---:|---:|
| Combo1 (3.1) | +0.0796 | +0.027 | −0.0052 | −0.0002 | +0.0013 | +29.39 pp |
| R1 | +0.0293 | +0.009 | −0.0052 | −0.0002 | +0.0006 | +21.27 pp |
| R2 | +0.0673 | +0.023 | −0.0052 | −0.0002 | +0.0007 | +27.49 pp |
| R3 | +0.0293 | +0.009 | −0.0052 | −0.0002 | +0.0006 | +21.27 pp |

## E. Dual-track comparison & gate check

**Important methodological note.** The `production_score` composite is computed via rank-weighting over the currently-built pool of versions. Adding the three Phase 3.2 variants shifts the ranks of every variant slightly. Combo1's *composite* moved from +0.049 vs A (Phase 3.1 pool) to +0.0548 vs A (Phase 3.2 pool, seven extra related variants present). Its underlying Sharpe / DD / CVaR / capture numbers are **identical** to Phase 3.1. So Combo1 nominally clears the +0.05 gate in this run, but the clearance is pool-sensitive, not a real new improvement.

With that caveat:

- **Combo1** (Phase 3.1 artifact, re-scored here):
  - vs A: composite +0.0548 (≥0.05 ✓), Sharpe +26 bps ✓, DD −0.0022 (within 0.005 ✓), CVaR within gate ✓, turnover +0.0016 (within heuristic ✓).
  - vs F: composite +0.080, Sharpe +27 bps, DD safely inside gate.
  - Classification: **Conditional Promote** — nominally passes all gates but only because the rank-composite moved; real risk metrics vs A are unchanged from Phase 3.1.
- **R1** (tight gate to `recovery_confirmed` only):
  - vs A: composite +0.0045 — fails the +0.05 gate by 0.045.
  - Lost recovery-fragile exposure (−2.7 pp) and half of the recovery-confirmed lift (from +29 pp to +21 pp). Classification: **Research-only**.
- **R2** (DD-proximity guard on sector):
  - vs A: composite +0.0425 — fails the +0.05 gate by 0.0075.
  - Identical DD to Combo1; keeps most of the recovery-confirmed lift (+26.8 pp vs +28.7 pp); Sharpe essentially unchanged vs Combo1. Adds a useful crisis-shutoff behavior that feels causally motivated but doesn't lift the composite. Classification: **Research-only (preferred reserve)**.
- **R3** (both refinements):
  - Identical numbers to R1. This confirms the DD guard is inactive inside `recovery_confirmed` in this sample (market_drawdown rarely exceeded −5% while the state engine was emitting `recovery_confirmed`). R3 collapses to R1.
  - Classification: **Research-only**.

**Net of sprint:** no Phase 3.2 variant beats Combo1. The best Phase 3.2 candidate (R2) is a neutral-to-slightly-worse rewrite of Combo1 with a theoretically attractive crisis circuit-breaker that didn't fire in this sample. Tightening the gate destroys the very lift we were trying to keep.

## F. Classification & pin decision

| variant | composite gate | DD gate | CVaR gate | turnover | classification |
|---|:---:|:---:|:---:|:---:|:---|
| R1 tight_gate | ✗ (+0.0045) | ✓ | ✓ | ✓ | Research-only (regressive) |
| R2 dd_guard | ✗ (+0.0425) | ✓ | ✓ | ✓ | Research-only (preferred reserve) |
| R3 tight+guard | ✗ (+0.0045) | ✓ | ✓ | ✓ | Research-only (collapses to R1) |
| Combo1 (3.1) re-read | ✓ (+0.0548) pool-sensitive | ✓ | ✓ | ✓ | **Conditional** — do not flip pins this sprint |

**Recommendation (conservative dual-track):** **Keep both pins unchanged.** A stays `improved_phase2b_regime_confidence_boost`; F stays `improved_phase2b_combo_abc`.

Rationale: the only variant clearing the +0.05 gate (Combo1) clears it only because the rank-composite rebalanced in the larger pool. The real vs-A improvements are identical to Phase 3.1, where the same composite measured +0.049. Flipping a production pin on a 0.001 move that disappears/reappears with pool composition is exactly the kind of overfitting risk CLAUDE.md warns against. Run a Phase 3.3 robustness check (fresh seed pool, bootstrap-subsample the composite, out-of-sample split) before considering promotion.

## G. Artifacts touched

Changed / rebuilt this sprint:
- `scripts/build_improvement_artifacts.py` (Phase 3.2 R1/R2/R3 wiring + three version specs)
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv` (regenerated)
- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_timeseries.csv` (regenerated)
- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_by_state.csv` (regenerated)
- All other standard outputs under `data/02_…` through `data/05_…` (regenerated as a side-effect)
- `public/dashboard-data.json` (rebuilt; pins unchanged)

New / updated docs:
- `docs/research/phase3_2_sprint_report.md` (this file)
- `docs/research/project_journey.md` (see section I)

Pins verified unchanged in `scripts/build-dashboard-data.mjs`:
- `PRODUCTION_VERSION_NAME = "improved_phase2b_regime_confidence_boost"`
- `RESEARCH_VERSION_NAME = "improved_phase2b_combo_abc"`

## H. Did the change help?

- **Standalone?** No. R1 and R3 regress sharply on the composite (+0.0045 vs A). R2 improves on A (+0.0425) but is worse than Combo1 (which was the thing we were trying to improve). So on any honest standalone reading of Phase 3.2, nothing helped vs Combo1.
- **In combination?** N/A — Combo1 is already the combination. R1–R3 are refinements, not additive.
- **Final classification:** all three Phase 3.2 variants → **Research-only**. Combo1 itself → **Conditional**, do not promote this sprint; revisit under Phase 3.3 robustness checks.

## I. Project journey log update

See `docs/research/project_journey.md`. Phase 3.2 adds a short section summarizing:
- the 0.001-gap hypothesis,
- why R1/R3 destroyed the lift,
- why R2 is a useful crisis circuit-breaker even though it didn't clear the composite,
- the pool-sensitivity observation that Combo1 nominally clears the gate and why that is **not** sufficient justification to flip pins,
- the open question handed to Phase 3.3 (robustness of the composite under pool perturbation).
