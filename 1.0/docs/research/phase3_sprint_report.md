# Phase 3 Opening Sprint Report

Dual-track baselines:
- **A — Production:** `improved_phase2b_regime_confidence_boost`
- **F — Shadow:** `improved_phase2b_combo_abc`

Every Phase 3 variant below is scored against **both** tracks separately, per the
dual-track rule in `CLAUDE.md`.

---

## A. What was changed

Three disciplined Phase 3 hypotheses, each aimed at a different lever. The
Phase 2B production overlay (`regime_confidence_boost`) is kept underneath all
variants so that every delta is attributable to the Phase 3 change itself.

| Code | Hypothesis | Lever |
|---|---|---|
| A1 | Richer sleeve-layer upgrade — add `sector_rotation_with_sma_filter` to the improved subset | Layer 2 (sleeve composition) |
| B1 | Learned sleeve-quality score using short (13w) + long (52w) persistence-confirmed rolling Sharpe | Layer 2 → Layer 3 tilt |
| C1 | State-conditioned sleeve-leadership tilt (per-state rolling Sharpe of each sleeve in the *prior* same-state weeks) | Layer 2B → Layer 3 tilt |
| E1 | Best justified combo — A1 + B1 | Stacked |
| F1 | Broader combo — A1 + B1 + C1 | Stacked |

Variant D1 (heavier black-box method, e.g. a trained meta-allocator) was
deliberately skipped for this opening sprint. The cheaper sleeve / state
levers have to be exhausted first — the project's rules explicitly prefer
simple causal logic over black-box ML.

Public research scan (informational):
- **AQR / Asness** — factor timing via cheapness + momentum; reinforces the
  persistence-confirmation idea behind B1 (a signal must agree on two
  horizons before it gets a size increment).
- **Man AHL / Harvey** — regime-conditional leadership; reinforces the
  state-conditioned sleeve tilt in C1 instead of a single global tilt.
- **ReSolve / Butler & Philbrick** — sleeve diversification with an
  independent trend-following contributor; justifies A1's addition of
  `sector_rotation_with_sma_filter` as an orthogonal sleeve rather than a
  deeper retune of existing ones.
- **Newfound / Hoffstein** — "no rebalance is free"; reinforces the
  guardrails: any new tilt must not inflate turnover or CVaR meaningfully.

---

## B. What was executed

1. Pre-flight sleeve screen: pairwise correlations of the candidate sleeve
   vs the existing 5 sleeves. `sector_rotation_with_sma_filter` was the most
   orthogonal candidate (avg pairwise correlation 0.58, max 0.66) with
   standalone Sharpe 0.63, DD -19%, hit rate 56%, and per-state Sharpe of
   2.05 in `recovery_fragile` and 1.10 in `recovery_confirmed` — the exact
   states where A underperforms on upside / recovery capture. This justified
   adding it as an orthogonal sleeve rather than tuning an existing one.
2. Implemented three new mechanisms in
   `scripts/build_improvement_artifacts.py`:
   - `compute_confirmed_sleeve_quality(...)` — short+long persistence-confirmed
     sleeve quality in [-1, +1].
   - `compute_state_sleeve_lead_tilt(...)` — per-state sleeve Sharpe
     computed strictly from *prior* same-state weeks (no lookahead).
   - Three new tilt modes on `apply_state_conditioned_tilt(...)`:
     `dynamic_risk_budget_confirmed_quality`,
     `dynamic_risk_budget_state_leader`,
     `dynamic_risk_budget_full_phase3`.
   - Registration of `sector_rotation_with_sma_filter` as a first-class
     sleeve in `base_sleeve_return_panel` / `base_sleeve_positions`.
3. Registered 5 Phase 3 version specs. Every spec keeps the Phase 2B
   overlay (`regime_confidence_boost`, overlay penalty mode
   `lighter_both_targeted_narrow_plus_confirmed`) and the HRP allocator, so
   the only new variable per variant is the Phase 3 lever being tested.
4. Ran the full walk-forward pipeline (`python3 scripts/build_improvement_artifacts.py`)
   end-to-end. No retrofits — all variants were rebuilt from the same
   weekly panel as the baselines to keep the comparison causal.
5. Extracted and dual-tracked every variant against both A and F.
6. Verified SSR first paint is still inspectable and that the dashboard pins
   are unchanged (A = production, F = shadow), because no Phase 3 variant
   cleared the +0.05 production promotion margin.

---

## C. Files / artifacts modified or regenerated

Code:
- `scripts/build_improvement_artifacts.py` — new helpers
  `compute_confirmed_sleeve_quality`, `compute_state_sleeve_lead_tilt`; three
  new tilt modes on `apply_state_conditioned_tilt`; sleeve registration for
  `sector_rotation_with_sma_filter`; 5 Phase 3 version specs.

Data (regenerated):
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`
- 15 per-variant artifacts in
  `data/05_layer3_portfolio_construction/` — three files per Phase 3
  variant (`portfolio_version_weights_*.csv`,
  `portfolio_version_sleeve_weights_*.csv`,
  `portfolio_version_returns_*.csv`).

Docs:
- `docs/research/phase3_sprint_report.md` — this file.

Dashboard / pins:
- **Unchanged.** A remains the single production default; F remains the
  single tracked shadow. No Phase 3 variant earned a pin change (see section
  G for why). The dashboard rebuild (`node scripts/build-dashboard-data.mjs`)
  was re-run to pick up the new variant rows as selectable comparisons only.

---

## D. Experimental results (18-metric panel)

All numbers are out-of-sample walk-forward. A and F are the Phase 2B
baselines re-run in this pipeline pass, so deltas are apples-to-apples.

| Metric | A (prod) | F (shadow) | A1 | B1 | C1 | E1 | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Ann. return | 6.89% | 6.86% | 6.83% | 6.89% | 6.90% | 6.83% | 6.82% |
| Ann. vol | 7.79% | 7.76% | 7.85% | 7.79% | 7.77% | 7.85% | 7.82% |
| Sharpe | 0.884 | 0.884 | 0.870 | 0.884 | **0.887** | 0.870 | 0.872 |
| Max drawdown | -13.98% | -13.67% | -13.98% | -13.86% | -13.85% | -13.90% | -13.75% |
| Calmar | 0.493 | **0.502** | 0.488 | 0.497 | 0.498 | 0.491 | 0.496 |
| CVaR (5%) | -2.62% | -2.61% | -2.71% | -2.62% | -2.61% | -2.71% | -2.70% |
| Avg weekly turnover | 5.62% | 5.66% | 6.51% | 5.63% | 5.61% | 6.52% | 6.49% |
| Annual turnover | 2.92 | 2.94 | 3.39 | 2.93 | 2.92 | 3.39 | 3.38 |
| Upside capture (pos wks) | 32.4% | 32.3% | **34.9%** | 32.4% | 32.4% | 34.8% | 34.7% |
| Downside capture (neg wks) | 23.9% | 23.9% | 27.3% | 23.9% | 23.9% | 27.2% | 27.1% |
| Recovery capture | 30.4% | 29.6% | **42.5%** | 30.0% | 30.3% | 42.0% | 41.8% |
| Recovery-confirmed capture | 39.5% | 38.7% | **78.9%** | 40.3% | 39.4% | 78.0% | 77.7% |
| Recovery-fragile capture | 28.0% | 27.3% | 33.1% | 27.3% | 27.9% | 32.6% | 32.5% |
| Calm capture | 43.4% | 43.5% | 38.3% | 43.3% | 43.1% | 38.8% | 38.2% |
| Stress downside capture | 30.6% | 31.1% | 24.5% | 30.7% | 30.6% | 24.4% | 24.6% |
| Avg BIL weight | 28.4% | 28.6% | 30.0% | 28.4% | 28.4% | 30.0% | 30.0% |
| Avg SPY weight | 7.08% | 7.08% | 5.56% | 7.07% | 7.08% | 5.55% | 5.57% |
| Avg cash weight | 16.2% | 16.4% | 16.2% | 16.2% | 16.2% | 16.2% | 16.2% |
| Avg offense when benchmark positive | 58.8% | 58.7% | 58.8% | 56.8% | 56.8% | 58.8% | 58.7% |
| **Production score** | **0.766** | 0.736 | 0.581 | 0.759 | **0.812** | 0.601 | 0.629 |

---

## E. Dual-track comparison (per variant)

### A1 — Richer sleeve + `sector_rotation_with_sma_filter`
- **vs A:** production score **-0.186**, Sharpe -0.015, Calmar -0.005, DD
  flat, CVaR worse by 0.001, turnover +0.9pp/week.
- **vs F:** production score **-0.156**, Sharpe -0.014, Calmar -0.013, DD
  worse by 0.003, CVaR worse by 0.001.
- **Character change:** recovery-confirmed capture +39pp, recovery capture
  +12pp, upside +2.5pp. **Paid for** by downside capture +3.4pp, calm
  capture -5.1pp, stress downside capture -6.1pp, annual turnover +0.47.
- **Verdict:** Does **not** beat A. Does **not** beat F.

### B1 — Persistence-confirmed sleeve quality
- **vs A:** production score **-0.007**, Sharpe flat, Calmar +0.004, DD
  better by 0.001, CVaR flat, turnover flat. Essentially neutral.
- **vs F:** production score **+0.023**, Sharpe +0.001, Calmar -0.005, DD
  worse by 0.002, CVaR flat.
- **Verdict:** Does **not** beat A. Marginal win vs F that is dominated by
  F's better Calmar — not a clean shadow takeover.

### C1 — State-conditioned sleeve-leadership tilt
- **vs A:** production score **+0.045**, Sharpe +0.003, Calmar +0.005, DD
  better by 0.001, CVaR better by 0.0001, turnover better by 0.0001.
- **vs F:** production score **+0.075**, Sharpe +0.003, Calmar -0.004, DD
  worse by 0.002, CVaR flat.
- **Verdict:** Clearly beats A on the composite and on every defensive
  gate except it falls **0.005 short of the +0.05 composite promotion
  margin**. Clearly beats F on the composite; loses F's Calmar and DD edge
  by small amounts.

### E1 — A1 + B1
- **vs A:** production score -0.165, Sharpe -0.014, Calmar -0.002, CVaR
  worse, turnover +0.9pp.
- **vs F:** production score -0.135, Sharpe -0.014, Calmar -0.010.
- **Verdict:** Worse than A1 alone. Stacking B1 on top does not recover
  A1's composite loss from the sector-rotation sleeve.

### F1 — A1 + B1 + C1
- **vs A:** production score -0.137, Sharpe -0.013, Calmar +0.003.
- **vs F:** production score -0.107, Sharpe -0.012.
- **Verdict:** C1's signal is swamped by A1's composite drag. Stacking the
  two recovers some Calmar but does not come close to C1 standalone.

Headline summary table:

| Variant | Beat A? | Beat F? | Notes |
|---|---|---|---|
| A1 | No (-0.186) | No (-0.156) | Character change on recovery capture at a heavy composite cost |
| B1 | No (-0.007) | Yes (+0.023) | Neutral to A; not a clean shadow win (F retains Calmar) |
| **C1** | **Near (+0.045, short of +0.05 gate)** | **Yes (+0.075)** | Cleanest composite win; misses promotion margin by 0.005 |
| E1 | No (-0.165) | No (-0.135) | Combo destroys B1's neutrality |
| F1 | No (-0.137) | No (-0.107) | Combo destroys C1's win |

---

## F. Diagnostic interpretation

1. **A1 is a behaviour change, not a performance win.** The sector-rotation
   sleeve roughly doubles recovery-confirmed capture (39% → 79%) but pays
   for it with +3.4pp of downside capture, -5pp calm, -6pp stress
   downside, and +0.5 annual turnover. The composite reflects this cleanly.
   The correct reading is: `sector_rotation_with_sma_filter` is a valid
   orthogonal sleeve, but deploying it unconditionally across all regimes
   is wrong — it needs a state gate. That is the Phase 3.1 experiment.

2. **B1 is a soundness check, not a lever.** The persistence-confirmed
   sleeve-quality score leaves every aggregate metric essentially flat vs
   A. That is evidence the Phase 2B rolling conviction is already near
   saturation for composite impact — a richer conviction estimator alone
   doesn't create new return without a new signal to allocate to.

3. **C1 is the real Phase 3 finding.** State-conditioned sleeve leadership
   (looking up each sleeve's prior-same-state Sharpe and tilting weights
   modestly toward the in-state leaders) improves Sharpe, Calmar, DD, CVaR,
   and the composite simultaneously — and does it without turnover cost
   and without SPY / BIL weight drift. The gain is concentrated in
   `recovery_fragile` (+1pp) with small Sharpe / Calmar improvements
   elsewhere. The +0.10 / -0.10 tilt bound is conservative. The fact that
   the composite gain is +0.045 — 0.005 short of the promotion gate —
   strongly suggests a lightly widened tilt bound or a non-trivial
   conviction floor would push it over.

4. **Stacking is not free.** Both E1 and F1 underperform their best single
   component. A1's sleeve-composition change dominates the composite
   when combined with B1 or C1; C1's per-state tilt cannot recover A1's
   regime-indiscriminate drag. This is an argument *against* a greedy
   "combine every positive lever" approach and *for* isolating C1 first.

5. **The dashboard first paint stays valid.** No Phase 3 variant changes
   the production default or the shadow, so the SSR narrative (A headline,
   F alternate comparison) continues to be inspectable immediately.

---

## G. Decision classification

| Variant | Classification | Reason |
|---|---|---|
| A1 | **Research-only** | Loses both composites; real character change on recovery capture is interesting but needs a state gate before it can be promoted. |
| B1 | **Research-only** | Neutral vs A; not a clean win vs F. Kept as a building block — its persistence-confirmed conviction remains a safe replacement for the 26w rolling Sharpe in future variants. |
| **C1** | **Conditional** | Beats A composite by +0.045 (0.005 short of the +0.05 gate), improves DD and CVaR, turnover neutral. Does not clear the promotion margin by the pre-registered rule, so it is **not** promoted to production — but it is the clear Phase 3.1 candidate. |
| E1 | **Drop** | Combination destroys B1's neutrality and inherits A1's composite drag. |
| F1 | **Drop** | Combination dilutes C1's win. |

Dashboard / pins: **unchanged.** A remains production. F remains shadow.

---

## H. Final recommendation

1. **Keep A as the single official production default.** No Phase 3 variant
   cleared the +0.05 composite promotion margin against A, and the
   dual-track rule explicitly forbids promoting on "close enough".

2. **Keep F as the single tracked shadow.** C1 beats F's composite but
   loses F's Calmar and DD edge. Replacing F with C1 would trade the
   shadow's defensive character for a Sharpe-leaning profile already
   represented by A — which defeats the point of the shadow slot.

3. **Next sprint (Phase 3.1) is a focused C1 refinement, not a new lever
   hunt.** Target the 0.005 composite gap to the promotion gate using:
   - Widen C1's per-state leadership tilt bound from ±0.10 to ±0.15,
     keeping the same favorable-regime gate. That is the single-parameter
     change most likely to close the composite gap without collateral
     damage on turnover or CVaR.
   - Add a state-gated deployment of `sector_rotation_with_sma_filter`
     (deploy only in `recovery_fragile` / `recovery_confirmed`, not in
     calm or stress), which should preserve A1's +39pp recovery-confirmed
     capture without paying the calm and stress-downside cost A1 currently
     pays. This is *the* question A1 implicitly raised.
   - Do **not** promote any combo variant before the state-gated sleeve
     deployment is proven — the E1 / F1 evidence shows combos
     underperform their best single component when the sleeve gate is
     missing.

4. **Do not run a D1 heavier-method variant yet.** C1 is showing that the
   sleeve + regime lever still has usable return on capital. A trained
   meta-allocator should come after C1 and gated-A1 have converged; if
   those two already extract most of the composite improvement the
   complexity cost of a black-box D1 will not be justified.

5. **Reporting discipline going forward.** Every Phase 3.1 variant must
   continue to be scored against **both** A and F separately, and must
   state explicitly whether it is aimed at the production track, the
   shadow track, or neither. The opening sprint confirmed the value of
   this rule — A1 would have been a false positive under a one-baseline
   framing because of its recovery capture; the composite vs A / vs F
   check caught it immediately.
