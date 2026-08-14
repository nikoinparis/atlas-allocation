# Phase 3.1 Refinement Sprint Report

Narrow refinement of the two concrete levers identified by the opening Phase 3 sprint:
- refine the near-winner C1 (state-conditioned sleeve-leadership tilt)
- gate the offensive sleeve A1 (`sector_rotation_with_sma_filter`) to recovery states only

Dual-track baselines (unchanged):
- **A — production:** `improved_phase2b_regime_confidence_boost`
- **F — shadow:** `improved_phase2b_combo_abc`

---

## A. What was changed

Four narrow variants, each touching exactly one hypothesis (or, for Combo1,
the two standalone hypotheses combined). No new sleeves, no new allocators,
no black-box D1 method.

| Code | Hypothesis | Lever |
|---|---|---|
| C1a | Widen C1's state-leader tilt bound from ±0.10 to ±0.15 | Layer 3 tilt size |
| C1b | Keep C1's ±0.10 bound, but only fire when the rank-tilt magnitude exceeds 0.30 (conviction floor) | Layer 3 tilt selectivity |
| A1g | Deploy `sector_rotation_with_sma_filter` **only** in `recovery_fragile` and `recovery_confirmed`; force to zero in calm / neutral / stress | Layer 2 sleeve gate |
| Combo1 | C1a + A1g stacked (only if standalones show promise) | Layer 2 + Layer 3 |

All four keep the Phase 2B overlay (`regime_confidence_boost`), HRP, and the
same overlay penalty mode as A and F. Every delta is therefore attributable
to the Phase 3.1 lever alone.

**Dashboard / narrative changes:** none. No Phase 3.1 variant cleared the
+0.05 production promotion gate, so A remains the single production pin
and F remains the single shadow pin.

Research scan (narrow, targeted):
- AQR (Asness & coauthors) on factor timing — persistence and conviction
  filters work when applied selectively, not as a rate modifier. Justifies
  the *conviction-gated* C1b design rather than a blanket tilt widening.
- Newfound / Hoffstein on "no rebalance is free" — a state-gated sleeve
  deployment should never relocate more weight across states than the
  underlying signal strength supports; justified the ±0.15 ceiling on C1a
  rather than a larger bound.
- ReSolve on sleeve gating — deploying a single offensive sleeve only in
  its prior-strongest regimes is standard tactical practice and the
  correct response to A1's character change in the opening sprint.

---

## B. What was executed

1. Added `_apply_sector_state_gate(weights, market_state)` helper. In any
   non-recovery state (`calm_trend`, `neutral_mixed`, `stressed_panic`) the
   `sector_rotation_with_sma_filter` sleeve weight is forced to zero before
   long-only renormalisation, which redistributes weight proportionally to
   the surviving sleeves.
2. Added four Phase 3.1 tilt modes to `apply_state_conditioned_tilt`:
   `dynamic_risk_budget_state_leader_wider` (C1a),
   `dynamic_risk_budget_state_leader_conviction_gated` (C1b),
   `dynamic_risk_budget_sector_gated` (A1g), and
   `dynamic_risk_budget_state_leader_wider_sector_gated` (Combo1). All
   reuse the same `favorable`-state gate, the same
   `compute_rolling_sleeve_conviction`, the same
   `compute_state_sleeve_lead_tilt`, and the same
   `recovery_fragile` / `stressed_panic` protection as the Phase 3 C1.
3. Widened the conviction / state-lead dispatch in the main walk-forward
   loop so that the four new tilt modes receive the correct conviction
   and state-lead inputs.
4. Registered four new version specs alongside the existing Phase 3
   specs. No existing spec was modified.
5. Ran the full walk-forward pipeline end-to-end via
   `python3 scripts/build_improvement_artifacts.py` so that A, F, and all
   Phase 3 / 3.1 variants are rebuilt in the same pass — every delta below
   is apples-to-apples.
6. Rebuilt `public/dashboard-data.json` to pick up the new variants as
   selectable comparisons (pins unchanged).

---

## C. Files / artifacts modified or regenerated

Code:
- `scripts/build_improvement_artifacts.py` — added `_apply_sector_state_gate`
  helper, four new tilt modes in `apply_state_conditioned_tilt`, updated
  the conviction + state-lead dispatch in the walk-forward loop, and
  appended four Phase 3.1 version specs.

Data (regenerated):
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`
- 12 new per-variant artifacts
  (`portfolio_version_returns_*`, `portfolio_version_weights_*`,
  `portfolio_version_sleeve_weights_*` for C1a, C1b, A1g, Combo1).

Docs:
- `docs/research/phase3_1_sprint_report.md` — this file.

Dashboard / pins:
- **Unchanged.** A remains the single production default; F remains the
  single tracked shadow. `public/dashboard-data.json` regenerated to
  include the four new variants as selectable comparisons.

---

## D. Experimental results (full metric panel)

All out-of-sample walk-forward. A and F re-run in this pass so the pool is
consistent for rank-based composites.

| Metric | A (prod) | F (shadow) | C1a | C1b | A1g | Combo1 |
|---|---:|---:|---:|---:|---:|---:|
| Ann. return | 6.89% | 6.86% | 6.89% | 6.89% | 7.08% | **7.08%** |
| Ann. vol | 7.79% | 7.76% | 7.77% | 7.78% | 7.81% | 7.78% |
| Sharpe | 0.884 | 0.884 | 0.888 | 0.887 | 0.906 | **0.910** |
| Max drawdown | -13.98% | -13.67% | -13.86% | -13.85% | -14.45% | -14.19% |
| Calmar | 0.493 | **0.502** | 0.498 | 0.498 | 0.490 | 0.499 |
| CVaR (5%) | -2.62% | -2.61% | -2.61% | -2.61% | -2.64% | -2.63% |
| Avg weekly turnover | 5.62% | 5.66% | 5.61% | 5.61% | 5.80% | 5.78% |
| Annual turnover | 2.92 | 2.94 | 2.92 | 2.92 | 3.02 | 3.01 |
| Upside capture (pos wks) | 32.4% | 32.3% | 32.4% | 32.4% | 33.2% | **33.2%** |
| Downside capture (neg wks) | 23.9% | 23.9% | 23.8% | 23.9% | 24.5% | 24.4% |
| Recovery capture | 30.4% | 29.6% | 30.2% | 30.3% | 38.2% | **38.3%** |
| Recovery-confirmed capture | 39.5% | 38.7% | 39.3% | 39.3% | 67.5% | **68.1%** |
| Recovery-fragile capture | 28.0% | 27.3% | 27.9% | 28.0% | 30.6% | 30.5% |
| Calm capture | 43.4% | 43.5% | 42.9% | 43.1% | 43.7% | 43.4% |
| Stress downside capture | 30.6% | 31.1% | 30.6% | 30.6% | **25.8%** | **25.8%** |
| Avg BIL weight | 28.4% | 28.6% | 28.4% | 28.4% | 28.4% | 28.4% |
| Avg SPY weight | 7.08% | 7.08% | 7.08% | 7.08% | 6.79% | 6.79% |
| Avg cash weight | 16.2% | 16.4% | 16.2% | 16.2% | 16.2% | 16.2% |
| Avg offense when benchmark positive | 56.8% | 56.7% | 56.8% | 56.8% | 57.5% | 57.6% |
| **Production score** | 0.743 | 0.718 | 0.788 | 0.787 | 0.689 | **0.792** |

---

## E. Dual-track comparison

Deltas vs A (production) and vs F (shadow). Pre-registered production
promotion gate: composite ≥ **+0.05** AND DD within 0.005 AND CVaR within
0.002 AND turnover not meaningfully worse.

| Variant | Δ prod-score vs A | Δ prod-score vs F | Beat A? | Beat F? | Gate check |
|---|---:|---:|---|---|---|
| C1a | **+0.045** | +0.069 | Near (0.005 short of +0.05) | Yes | Composite misses; DD/CVaR/turnover pass |
| C1b | **+0.044** | +0.068 | Near (0.006 short) | Yes | Same pattern as C1a |
| A1g | **-0.054** | -0.029 | No | No | Composite loses despite +0.022 Sharpe and +28pp recovery-confirmed |
| **Combo1** | **+0.049** | **+0.073** | **Near (0.001 short of +0.05)** | **Yes** | DD, CVaR, turnover, calm, stress all within gate; only composite misses |

Character of each:
- **C1a / C1b** — Sharpe-leaning, near-identical to Phase 3 C1. No
  material improvement from widening or gating C1's tilt. Both beat F on
  composite but duplicate A's character (Sharpe, not defensive).
- **A1g** — heavy recovery-state character change. Recovery capture +8pp,
  recovery-confirmed +28pp, stress downside capture IMPROVES by 4.8pp
  (less downside captured in stress). Sharpe +22bps. But DD worsens to
  the edge of the gate (−0.005, barely in) and turnover +18bps/week. On
  the rank-based composite those small defensive penalties dominate
  and A1g actually **loses** composite by 0.054. Distinct shadow-style
  character but fails the gate.
- **Combo1** — best Phase 3.1 result. Stacks the small C1 lift on top of
  A1g's recovery character: Sharpe +26bps, Calmar +0.006, recovery
  capture +7.9pp, recovery-confirmed +29pp, stress downside capture
  IMPROVES by 4.8pp, calm capture essentially flat. DD worsens by 0.0022
  (within the 0.005 gate). CVaR flat. Turnover +16bps/week (not
  meaningfully worse). **Composite misses the +0.05 promotion bar by
  0.001.** Strongest dual-track delta (+0.049 vs A, +0.073 vs F).

Did the state gate on A1g actually concentrate effect in the intended
states? **Yes.** A1 (unconditional, Phase 3 sprint) showed calm capture
falling from 43.4% → 38.3% and stress-downside rising from 30.6% → 24.5%
(that direction is protective, but only because the sleeve was badly
sized in stress). A1g restores calm capture to 43.7% (essentially A
baseline) while keeping recovery-confirmed at 67.5% (still +28pp over A).
The state gate successfully isolated the sleeve's effect to the recovery
states it was hypothesised to add value in.

---

## F. Diagnostic interpretation

**Did widening C1's tilt bound (C1a) help?** No. C1a's composite vs A is
+0.045 — identical, to two decimals, to the original Phase 3 C1. The
±0.10 bound was not the binding constraint; widening it to ±0.15 does not
unlock additional composite. **C1 has a hard composite ceiling around
+0.045 under the current gate, and tilt sizing is not the answer.**

**Did conviction-gating C1 (C1b) help?** No. C1b is also +0.044 vs A.
Selective deployment of the same mechanism doesn't beat the ceiling
either. This is useful evidence: the limit is not signal quality, it is
the underlying signal's inherent composite footprint.

**Did state-gating A1 (A1g) help?** Partially. The state gate worked as
designed — calm capture recovered to A baseline, stress-downside
capture actually improved (−4.8pp protective), and recovery-confirmed
capture stayed +28pp over A. Sharpe improved +22bps. But max drawdown
worsened by 0.005 (at the edge of the defensive gate) and turnover
rose 18bps/week, and the rank-based composite penalised these small
defensive degradations heavily. A1g as a standalone is **not** a
production candidate.

**Did the combo help or hurt?** Helped — it is the strongest Phase 3.1
result. Combo1 stacks C1a's small Sharpe/Calmar lift on top of A1g's
recovery character and gets a +0.049 composite delta vs A, +0.073 vs F,
while tightening DD from A1g's −14.45% back to −14.19%
(inside the 0.005 gate) and improving stress-downside protection. The
net result is: a Sharpe +26bps, Calmar +0.006, recovery-confirmed +29pp,
stress-downside −4.8pp portfolio that **misses the composite promotion
bar by exactly 0.001**.

**Which result is strongest now?** **Combo1.** It has the best composite
delta of any Phase 3 / 3.1 variant we have tested, the best recovery
character, and better stress protection than A. It is a near-winner.

**What is the main remaining bottleneck?** Drawdown preservation.
Combo1's DD worsening of 0.0022 vs A, plus the 0.0016 turnover increase,
are what hold the composite at +0.049 instead of +0.05+. If a narrow
Phase 3.2 refinement can close even half of that DD gap without
sacrificing the recovery character, Combo1 clears the gate. The most
justified single next change would be to tighten A1g's state gate
further (e.g., `recovery_confirmed` only — the state where the prior
evidence was overwhelmingly strongest at Sharpe 1.10 — and not
`recovery_fragile`) and see whether the narrower gate recovers the lost
DD without surrendering the recovery-confirmed character.

---

## G. Decision classification

| Variant | Classification | Reason |
|---|---|---|
| C1a — widened tilt | **Research-only** | Confirms C1's composite ceiling under the current gate; no incremental lift over Phase 3 C1. |
| C1b — conviction-gated tilt | **Research-only** | Same ceiling as C1a; selective deployment doesn't unlock additional composite. |
| A1g — state-gated sector sleeve | **Research-only** | Standalone composite loss (−0.054) despite large recovery-confirmed and stress-protection gains; valid as a building block but not as a standalone candidate. |
| **Combo1 — C1a + A1g** | **Conditional** | Best composite delta of all Phase 3 / 3.1 variants (+0.049 vs A, +0.073 vs F). Passes DD, CVaR, turnover, calm, stress gates. Misses +0.05 composite by 0.001. Promising Phase 3.2 seed; not promoted today. |

Dashboard / pins: **unchanged.** A remains production. F remains shadow.

---

## H. Final recommendation

1. **A remains the single official production default.** No Phase 3.1
   variant cleared the pre-registered +0.05 composite margin. The
   dual-track rule explicitly forbids promoting on "close enough", even
   though Combo1 is only 0.001 short and improves Sharpe, Calmar, recovery,
   and stress protection simultaneously.

2. **F remains the single tracked shadow.** Combo1 beats F's composite
   (+0.073) but is Sharpe-leaning with a slightly worse DD than F; it does
   not preserve the distinct defensive character that justifies a separate
   shadow slot. Replacing F with Combo1 would collapse the dual-track into
   two Sharpe-leaning candidates.

3. **Phase 3.2 is a focused Combo1 refinement — not a new lever hunt.**
   The binding constraint is a 0.002 DD worsening and a 0.0016 turnover
   uptick inside Combo1. Two disciplined candidate refinements:
   - tighten A1g's state gate from
     `{recovery_fragile, recovery_confirmed}` to `{recovery_confirmed}`
     only — the state where the prior per-state Sharpe evidence was
     overwhelmingly the strongest (Sharpe 1.10);
   - add a DD-proximity guard that pulls the sector sleeve weight toward
     zero when the portfolio's rolling drawdown is already deep, so the
     sleeve cannot add to DD in the tail.
   Either or both, applied narrowly, are the shortest path to closing
   the 0.001 composite gap without surrendering Combo1's recovery and
   stress-protection character.

4. **C1 is effectively exhausted as a composite lever under the current
   gate.** C1a and C1b pinned the ceiling at ≈+0.045. Future work on C1
   should only be attempted in combination with a different sleeve
   composition or a tighter DD guard — not by further tuning the tilt
   size or selectivity.

5. **Do not run a D1 heavier-method variant.** Combo1 is already at the
   edge of promotion on a simple, causal, fully-inspectable construction.
   A trained meta-allocator is not justified while a narrow
   state-gate / DD-guard refinement can plausibly finish the job.

6. **Reporting discipline for Phase 3.2.** Every candidate must continue
   to be scored against both A and F separately. Combo1 is now the
   natural anchor for "aimed at the production track"; gated-A1 variants
   that *don't* combine with C1 are better classified as shadow
   candidates (heavy character change, not composite wins).

## Summary

Phase 3.1 confirmed that C1 tilt sizing is not the binding constraint,
that state-gating the sector sleeve concentrates its effect correctly,
and that stacking the two produces the closest approach yet to the
+0.05 composite promotion gate — missing it by exactly 0.001. A and F
remain pinned; Combo1 is the clear Phase 3.2 anchor.
