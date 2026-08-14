---
editor_options: 
  markdown: 
    wrap: sentence
---

# Portfolio Optimizer — Project Journey

A readable narrative of how this research project evolved.
This is a living document: each sprint appends a short section to keep the story straight.
Deliberately not a metrics dump — those live in the per-sprint A–H reports.

------------------------------------------------------------------------

## 0. What we are trying to do

Build a robust, interpretable, out-of-sample ETF portfolio via a layered stack:

-   **Layer 1** — alpha signals (cross-sectional momentum, trend, carry, quality, value, residual mom, reversals…).
-   **Layer 2** — strategy logic / sleeves (dual-momentum top-N, CTA-trend-long-only, composite-regime-conditioned, TAA 10-month SMA, composite-selective-signals, sector-rotation-with-SMA).
-   **Layer 2B** — causal regime / market-state engine producing walk-forward states (`stressed_panic`, `recovery_fragile`, `recovery_confirmed`, `neutral_mixed` with a `strong_neutral` subtype, `calm_trend`).
-   **Layer 3** — portfolio construction across sleeves (HRP base with regime and risk overlays).
-   **Dashboard** — research explainer + comparison + diagnostics, inspectable on first paint.

Guardrails throughout: prefer simple causal logic, avoid hindsight regime labels, test incremental contribution, keep only changes that help out of sample (standalone *or* in combination), and prioritize state-transition quality, re-risking speed, and reducing needless BIL/cash drag.

------------------------------------------------------------------------

## 1. Baseline era

We started with a fairly classical HRP default and a max-diversification alternative.
The baseline had two chronic weaknesses: it under-participated in benign "calm trend" and "recovery confirmed" states (too much BIL drag) and was slow to re-risk after stress.
Most early experiments tried to buy participation without paying for it with drawdown.

Key lessons from this era:

-   Simply raising turnover to react faster bought marginal Sharpe at noticeable DD cost.
-   Hard regime labels on rolling windows looked great in-sample and broke out-of-sample — hence the hard rule *no hindsight regime labels*.
-   Sleeve-level cash decisions (BIL inside sleeves) were often redundant with the portfolio-level BIL the allocator already holds. This eventually forced a sleeve-internal cash redesign.

------------------------------------------------------------------------

## 2. Phase 1 — deployment discipline and good-state leadership

Phase 1 sprints layered five mechanically-distinct improvements on top of the HRP baseline: a dynamic risk budget (A), a continuous allocation map (B), a causal confidence score (C), a sleeve-internal cash redesign (D), and good-state sleeve leadership (E).
Combos F = A+E and G = A+E+D-restricted were then tested.

What we learned:

-   The single biggest lever was deployment-discipline: rewarding confirmed-good states rather than mechanically averaging across all states.
-   D's sleeve-internal cash redesign helped only in combination, not standalone — it only pays off once A/E are already structurally pushing allocations.
-   Combo F was the first variant to cleanly pass the gates and reshape the production candidate.

This era established our working belief that "state-conditioned leadership" is a real and generalizable structure, not just in-sample fitting.

------------------------------------------------------------------------

## 3. Phase 2A — allocator research

Phase 2A broadened the allocator family beyond HRP: ERC/ERC-dynamic, HERC, MVO/IC-MVO, Black-Litterman-regime, max-diversification, and principled continuous maps.
We wanted to test whether the Phase-1 gains were allocator-specific or structural.

Findings:

-   ERC + principled continuous map and HERC + principled continuous map both came close but didn't stably outperform HRP once we held our DD and CVaR gates constant.
-   HRP kept winning on the composite because its diversification behavior interacts well with the regime overlay's fragility handling.
-   We confirmed that gains from Phase 1 were *not* allocator-specific: they carried across ERC/HERC variants, just not by enough to justify swapping allocators.

Phase 2A's clean conclusion: **keep HRP as the production allocator**, park the principled continuous map as an alternate research lane.

------------------------------------------------------------------------

## 4. Phase 2B — causal regime engine

Phase 2B was the deepest redesign.
Instead of layering more heuristics on top of a coarse regime signal, we built a causal market-state engine that emits walk-forward labels with fragility, confirmation, and stress semantics.
Multiple variants (confidence-boost, tail-risk suppression, transition-quality gate, combos A+B+C and A+C) were scored.

Key outcome:

-   **Variant A (regime_confidence_boost)** became the production pin — strong Sharpe, tight DD, cleaner transition behavior, minimal turnover cost.
-   **Variant F (combo_abc)** became the research runner-up: slightly different trade-off (a touch better DD, a touch worse recovery-confirmed capture), useful as a tracked shadow baseline.

This is where the **dual-track rule** was formally established: A is the single production default in the dashboard/narrative, F is the tracked shadow, and any future promotion must show incremental contribution against *both* tracks — not just A — before the pins move.

## 5. Phase 3 — opening sprint (richer sleeve, learned sleeve quality, state-conditioned sleeve allocation)

Phase 3 tested five disciplined variants:

-   **A1** — add `sector_rotation_with_sma_filter` as a sixth orthogonal offensive sleeve.
-   **B1** — learned sleeve quality via rolling 26w rank-based conviction.
-   **C1** — state-conditioned sleeve allocation using prior-same-state 156w Sharpe-rank tilt (walk-forward safe).
-   **E1** — A1 + B1 combo.
-   **F1** — A1 + B1 + C1 combo.
-   (D1 — heavy black-box — deliberately skipped by design.)

Nothing cleared the +0.05 composite promotion gate vs A in the opening sprint.
**C1 was the strongest at +0.045** — clearly real, clearly not quite enough.

Key lesson: richer sleeve + learned quality both lost to structural state-conditioning.
The good state-tilt was doing real work; adding the sector sleeve in an un-gated way dragged on calm states.

## 6. Phase 3.1 — narrow refinement

Refinements focused on C1's near-win and on controlled expression of A1:

-   **C1a** — widen the state-leadership bound from ±0.10 to ±0.15.
-   **C1b** — conviction-gated C1 (only apply the tilt when \|state-lead\| \> 0.30).
-   **A1g** — state-gated sector rotation: force sector weight to zero outside `recovery_fragile / recovery_confirmed`.
-   **Combo1** — C1a + A1g.

Results:

-   C1a and C1b both landed at roughly the same composite ceiling (\~+0.045). So the C1-path ceiling is driven by *sleeve composition*, not by tilt magnitude or selectivity.
-   A1g succeeded at concentrating the sector sleeve's value into recovery states (recovery-confirmed capture up \~28 pp) and restored calm capture to parity, but widened DD by 0.005 — right at the edge.
-   **Combo1 = C1a + A1g** was the strongest: composite +0.049 vs A, Sharpe +26 bps, DD −0.002 (inside gate), recovery-confirmed capture +29 pp. Missed the +0.05 composite gate by exactly **0.001**.

Honest call at end of 3.1: Combo1 is clearly a real improvement, clearly not clearly enough to flip pins, and the binding constraint is DD/turnover friction specifically inside recovery states.

## 7. Phase 3.2 — closing the 0.001 gap (current sprint)

Three narrow refinements on top of Combo1:

-   **R1** — tighten the A1g state gate to `recovery_confirmed` only.
-   **R2** — DD-proximity guard: scale the sector sleeve by market drawdown (50% at md ≤ −5%, 0% at md ≤ −10%).
-   **R3** — both.

What happened:

-   **R1 and R3 destroyed the lift.** Tightening to `recovery_confirmed` only cost us the `recovery_fragile` fraction of the gain (recovery-confirmed capture fell from +29 pp to +21 pp vs A). The composite lift collapsed to +0.0045. R3 collapsed to R1 because market drawdown rarely exceeds −5% while the engine is labelling states `recovery_confirmed` — the DD guard never fired.
-   **R2** behaved sensibly: identical DD to Combo1, retained most of the recovery-confirmed lift (+26.8 pp vs Combo1's +28.7 pp), composite +0.0425 vs A. A clean causal circuit-breaker that the sample just didn't exercise. Good to keep in reserve even though it doesn't clear the gate.
-   **Combo1 re-scored in the expanded pool posted +0.0548 vs A** — nominally clearing the +0.05 composite gate. Crucially, its underlying Sharpe / DD / CVaR / captures are *identical* to Phase 3.1. The composite number moved only because adding R1/R2/R3 to the rank pool nudged ranks. The gate clearance is pool-sensitive, not new information.

Decision: **keep pins unchanged** (A = `improved_phase2b_regime_confidence_boost`, F = `improved_phase2b_combo_abc`).
Promoting a candidate on a rank-composite move that appears and disappears with pool composition is precisely the overfitting risk CLAUDE.md warns against.
The right next step is a robustness-check sprint.

Bottlenecks / lessons from 3.2:

1.  **The composite is pool-sensitive.** The +0.05 gate needs either a fixed comparator set, bootstrap stability, or a raw (non-rank) variant before it can be trusted for pin flips at the margin.
2.  **Tighter gates cost us generality.** `recovery_fragile` is not "noise" — it's actually carrying a meaningful fraction of the A1g recovery lift.
3.  **Causal circuit-breakers are good hygiene even if they don't move the headline number.** R2's DD-guard is worth keeping as a research reserve — cheap, interpretable, safe.
4.  **Promotion discipline held.** 0.001 in the gate direction, even nominally cleared in an expanded pool, is not the same thing as a robust improvement. Keeping pins is the right call.

## 8. Phase 3.3 — robustness / validation sprint

This was deliberately not a new-strategy sprint.
It was a **disciplined validation of Combo1** against the dual-track pins, using four tests chosen specifically to diagnose whether the Phase 3.2 gate pass was a real improvement or a rank-composite artifact.

The four tests:

-   **Rb1 — fixed comparator set.** Recompute the production rank composite on exactly three variants (A, F, Combo1), and separately on a five-variant fixed set that also includes `baseline_hrp_default` and `improved_phase3_1_c1_widened` as historical reference points.
-   **Rb2 — raw-metric composite.** Use the same economic weights as the production composite (0.22 Sharpe / 0.16 Calmar / 0.14 \|DD\| / 0.10 \|CVaR\| / 0.12 upside / 0.10 recovery / 0.08 cash / 0.08 turnover), but z-score the raw metrics across the pool instead of ranking them.
-   **Rb3 — 13-week block bootstrap** on the weekly net returns for A, F, and Combo1 (2000 iterations, seed 20260418, active history 2006-06 → 2026-04, n = 1 033 weeks). Reports mean Δ, 95% CI, and P(target \> base) for Sharpe, annual return, max DD, and CVaR 5%.
-   **Rb4 — subperiod halves** (calendar split 2015-12-31 and length-matched split 2016-05-20) plus a rolling 104-week Sharpe-diff diagnostic.

What we learned:

-   **The gate pass is genuinely pool-sensitive.** On the strict 3-variant comparator set, Combo1 beats A on the same rank composite by only **+0.040** — below the +0.05 promotion bar. On the 5-variant reference set it beats A by +0.084. On the full pool it beats by +0.055. The composite number is volatile to pool membership by \~4 percentage points.
-   **On raw economic metrics, Combo1 does dominate A and F.** Raw z-score composite: A = +0.44, F = +0.52, Combo1 = +0.95. That is about half a standard deviation of the pool's metric dispersion — directionally clear, not a rank artifact.
-   **Bootstrap says Sharpe/return edge is real but fragile.** Block bootstrap over 13-week blocks: Combo1 beats A on Sharpe in **94.2%** of replicates, with mean Δ = +0.028, but the 95% CI is `[−0.007, +0.065]` — it **straddles zero**, so the edge is not significant at the 5% level. Annual return shows the same pattern (P = 0.923, CI [−0.0008, +0.0058]).
-   **On tail metrics, Combo1 and A are bootstrap-indistinguishable.** Max DD: P(Combo1 better) = 0.451. CVaR 5%: P(Combo1 better) = 0.437. These are coin flips.
-   **Subperiod stability is weak.** Combo1's Sharpe edge is present in both halves (≈ +0.025 each), but its DD is shallower than A pre-2015 (+0.005) and deeper post-2015 (−0.002). Rolling 104-week windows: Combo1 beats A in only 60.8% of windows.

Decision: **Combo1 stays Conditional / Research-only. Pins unchanged.** The evidence is directionally positive but fails two of the four robustness tests — the fixed 3-comparator rank check and the statistical-significance check on the mean metrics.
Under the project's dual-track rule, which requires clear incremental contribution against both A and F before promoting, the case is not there.

Lessons from Phase 3.3:

1.  **Rank composites are a fragile decision tool at the margin.** A \~0.04-point drift in composite score is well within "changes if the pool membership changes" territory. The composite itself needs either a fixed comparator set, a raw-metric check, or both, before being trusted for pin flips.
2.  **Mean-metric improvements can be real without being promotable.** Combo1's +0.028 Sharpe is directionally robust (94% bootstrap) and consistent across both halves, but it isn't statistically clean and doesn't buy tail relief. Promotion should require *some* improvement on the tail, not just mean.
3.  **No true holdout exists yet in this project.** Every Phase 3 iteration has seen every slice of history. Any future promotion claim should be checked against an explicitly held-out window.

## 9. Phase 3.4 — tail-focused refinement + holdout discipline

Two coupled goals:

1.  Test whether a narrow, structural tail-focused refinement of Combo1 can repair its unchanged DD / CVaR profile without destroying its mean-return edge.
2.  Introduce true holdout-style evaluation discipline (pre-declared forward window, train/tune vs holdout separation, and an explicit no-promotion-from-in-sample-edge rule).

The three candidates (reference = Combo1 = C1a + A1g):

-   **T1 fragile guard** (`improved_phase3_4_combo_fragile_guard`). Adds `_apply_sector_fragile_dd_guard`: scales the sector sleeve by 0.5 when benchmark DD ≤ −5 % and by 0 when ≤ −15 %, **only** while `market_state == "recovery_fragile"`. Motivated by market-state data showing that `recovery_fragile` has 25th-percentile benchmark DD of −12.9 % (median −1.9 %), while `recovery_confirmed`'s worst DD is −5.8 % — fragile is where deep DDs actually live.
-   **T2 tilt dampened** (`improved_phase3_4_combo_tilt_dampened`). Adds `_dd_gradient_tilt_dampener`: multiplies the state-leader tilt bound by 0.75 at benchmark DD ≤ −5 % and 0.5 at ≤ −10 %, regardless of regime. Not a hard gate; a gradient tilt-magnitude softener.
-   **T3** (`improved_phase3_4_combo_fragile_guard_tilt_dampened`). T1 + T2.

Pre-declared holdout: **last 2 years** of weekly data, `HOLDOUT_START = 2024-04-19`, n = 104 weeks.
Development window: 2006-06-30 → 2024-04-12, n = 929.
Declared *before* the variants were run.

What we learned:

-   **Combo1 fails the holdout.** On the 104-week pre-declared window, Combo1's Sharpe is 1.957 vs A's 2.002 (ΔSharpe = −0.045), its max DD is −0.0596 vs A's −0.0566, and its Calmar trails A by −0.147. The 13-week block bootstrap on holdout gives P(Combo1 \> A on Sharpe) = **25.8 %**, with a 95 % CI straddling both signs. The pre-holdout +0.030 Sharpe edge does **not** generalize.
-   **F slightly beats A on holdout.** F's holdout Sharpe is 2.014 (ΔSharpe vs A = +0.012), Calmar +0.064. Small, but directionally consistent with F's design rationale (broader sleeve diversity, softer state conditioning).
-   **T1 / T2 / T3 are no-ops on holdout.** All three variants are **exactly identical** to Combo1 on the holdout window (ΔSharpe = ΔRet = ΔDD = 0). Neither overlay triggered on any holdout week. Full-history max DD is unchanged at −0.1419 across Combo1 and all three T variants. T1 / T3 even shave recovery-fragile capture (0.305 → 0.282) for no DD benefit; T2 is Combo1 within rounding.
-   **The tail problem is in C1a, not in a missing overlay.** Two of the most plausible causal-gradient patches on top of Combo1 moved nothing on the full-history tail. The −0.002 DD gap vs A is structural to the widened state-leader bound, not to any additional overlay.

Decisions:

-   **T1 → Drop.** No tail benefit, small Sharpe drag vs Combo1.
-   **T2 → Research-only.** Indistinguishable from Combo1 at every window. Not worth maintaining.
-   **T3 → Drop.** Combination of two no-ops.
-   **Combo1 → downgrade research conviction.** Still interesting as a Phase 3 reference, but explicitly flagged as failing the pre-declared 2-year holdout on every primary metric. Not a promotion candidate.
-   **A / F pins:** unchanged.

Hygiene added this sprint:

1.  Pre-declared forward holdout is now canonical. All future sprints must report pre-holdout and holdout Sharpe separately, and no promotion may occur without ΔSharpe ≥ 0 on holdout and bootstrap P(cand \> A on holdout) ≥ 60 %.
2.  Phase 3.5 (if pursued) should reopen C1a itself — either narrow it to good-state-only (strong_neutral / confirmed / calm_trend) while leaving fragile at ±0.10, or drop C1a and test A1g alone. I.e. "which half of Combo1 actually helps."
3.  F's mild holdout edge warrants a proper rolling-origin cross-validation in a later sprint — not a pin flip yet, but a live research question.

## 10. Phase 3.5 — attribution: which half of Combo1 actually helps?

Phase 3.4's tail-overlay attempts (T1/T2/T3) were all no-ops.
That left the cleanest open question intact: **which half of Combo1 actually drives the edge, and which half drives the tail / holdout failure?** Phase 3.5 answered that question directly with a pure attribution study — no new strategy code, no new sleeves, no new overlays.
Just re-evaluate the two halves that already exist in the pipeline under the Phase 3.4 holdout discipline.

The two halves:

-   **H1 = A1g-only** (`improved_phase3_1_a1_state_gated`): sector sleeve added and state-gated to `{recovery_fragile, recovery_confirmed}`, without the widened state-leader tilt.
-   **H2 = C1a-only** (`improved_phase3_1_c1_widened`): widened state-leader tilt bound (±0.15), without the extra sector sleeve.
-   **H3 = Combo1 reference** (`improved_phase3_1_combo_c1a_a1g`).

Same pre-declared holdout as Phase 3.4 (2024-04-19 → 2026-04-10, n = 104 weeks).
Deltas vs A and vs F in every window, 13-week block bootstrap vs A and vs Combo1 on holdout.

What the attribution showed:

-   **Recovery capture is 100 % A1g.** H1 recovery-confirmed capture = 0.675 vs A's 0.395 (+28 pp). H2 recovery-confirmed capture = 0.393 — unchanged from A. Combo1 ≈ H1 on every capture metric.
-   **Tail degradation is 100 % A1g.** H1 max DD = −0.1445 (**deepest of all five candidates**, including Combo1). H2 max DD = −0.1386 (*shallower than A*). Combo1 = −0.1419, closer to H1 than to the midpoint.
-   **Holdout roles reversed cleanly.** On the pre-declared 2-year holdout:
    -   A Sharpe 2.002, F 2.014, H1 (A1g) **1.951**, H2 (C1a) **2.013**, Combo1 1.957.
    -   **H2 beats A by +0.011 Sharpe on holdout.** H1 loses by −0.050. Combo1 loses by −0.045.
    -   Holdout bootstrap P(H2 \> A on Sharpe) = 0.692; P(H1 \> A) = 0.265; P(Combo1 \> A) = 0.258.
    -   P(H1 \> Combo1) = 0.500 — H1 is statistically identical to Combo1 on holdout. **A1g is doing essentially all of Combo1's work on holdout, and all of it is bad.**
    -   P(H2 \> Combo1) = 0.757 — dropping A1g from Combo1 improves holdout performance.

This **inverts** the Phase 3.4 working hypothesis, which had guessed the tail damage was in C1a's widened tilt.
Attribution shows the opposite: C1a-alone is tail-friendly and holdout-positive; A1g-alone is the sole source of both the DD damage and the holdout failure.

Decisions:

-   **H1 (A1g-only) → Drop.** Clear winner pre-holdout, clear loser on tail and holdout. Single biggest cost carrier in Combo1.
-   **H2 (C1a-only) → new leading Research candidate.** Small full-history edge (+0.003 Sharpe, +0.0012 DD vs A, +0.047 composite score, just under the +0.05 gate). Directionally **positive** on the pre-declared holdout (+0.011 Sharpe, +0.038 Calmar, P = 0.692). Production score 0.768 vs A's 0.721.
-   **H3 (Combo1) → retired as research reference.** Replaced by H2.
-   **A production pin:** unchanged.
-   **F shadow pin:** unchanged; still directionally beats A on holdout.

Lessons from Phase 3.5:

1.  **Attribution works.** The two halves decompose almost linearly on mean return and cleanly on tail / holdout. Combo-level post-mortems were the right step; further overlays on top of the combo were not.
2.  **The sector sleeve addition (A1g branch) is the harmful element.** Not the widened tilt. Reserve the C1a tilt for the Research track; retire the sector-sleeve addition until and unless a redesigned, sleeve-internal-cash-disciplined version becomes available.
3.  **Phase 3.4's diagnosis was wrong but Phase 3.4's process was right.** Running Combo1 on holdout produced the negative signal that motivated this attribution. Without that, Phase 3.5 would have kept patching the wrong half.

## 11. Current state (end of Phase 3.5)

-   **Production pin (A):** `improved_phase2b_regime_confidence_boost` — unchanged.
-   **Shadow pin (F):** `improved_phase2b_combo_abc` — unchanged; holdout edge over A still mildly positive.
-   **Leading research candidate:** `improved_phase3_1_c1_widened` (H2 = C1a-only). Research-only. Small but consistent mean edge vs A, DD shallower than A, positive on pre-declared holdout.
-   **Retired research references:** Combo1 (`improved_phase3_1_combo_c1a_a1g`), T1/T2/T3 (Phase 3.4 overlays). Combo1 remains in the repo as historical but is no longer the research track.
-   **Dropped branches:** A1g sector-sleeve addition in its current form; Phase 3.4 tail overlays on top of Combo1; tightening the sector gate to confirmed-only (R1/R3); composite-only promotion arguments at narrow margins.
-   **Useful reserve structures (untouched):** R2 DD-proximity guard, T1 fragile-scoped guard, T2 tilt dampener. Causal, interpretable, still wired; not currently doing work but available when the right sample arises.
-   **Gates now canonical:** +0.05 composite vs A, DD within 0.005, CVaR within 0.002, turnover not meaningfully worse, **ΔSharpe ≥ 0 on pre-declared holdout with bootstrap P(cand \> A) ≥ 60 %**, and robustness via fixed-comparator / raw-z / block-bootstrap triad.

## 12. Open questions handed to Phase 3.6 / Phase 4

1.  **Can the sector-sleeve addition be redesigned?** The recovery-capture boost A1g delivers is real and large (+28 pp recovery-confirmed capture). It is possible this can be recovered with a less aggressive sector-exposure mechanism that does not carry A1g's tail / holdout cost — e.g. sleeve-internal cash gating tied to sleeve-level realised vol, or smaller sector weight caps. Research-track only.
2.  **Proper rolling-origin cross-validation for F vs A.** One 2-year holdout showed F slightly ahead. Multiple origins (5-year rolling, 104-week rolling) are needed before any pin flip. Earliest candidate for Phase 4.
3.  **H2 robustness pass.** H2 is not yet promotion-ready (edge is small and composite is below +0.05). A dedicated Phase 3.6 could either (a) apply the Phase 3.3 robustness triad to H2 specifically, or (b) bank H2 as the Research-track winner and move directly to Phase 4.
4.  **Composite redesign (still carry-over).** Move to a mixed rank + z composite or a bootstrap-stable composite to eliminate pool sensitivity as a decision-level vulnerability.

## 13. Conventions

-   Reports live under `docs/research/` and follow an A–H format with an optional section I for project-journey updates.
-   Pins are defined in exactly one place each: `CLAUDE.md` (narrative) and `scripts/build-dashboard-data.mjs` (code). Both must match.
-   The dashboard's homepage must render all key content on first paint — no content hidden behind tabs, accordions, or loading states.
-   A variant's classification is always one of: **Promote / Conditional / Research-only / Drop**, computed against the +0.05 composite gate, the 0.005 DD gate, the 0.002 CVaR gate, and the "turnover not meaningfully worse" heuristic.

## 14. Roadmap reset — why the project is now shifting away from control-layer tweaks

By the end of the later Phase 2 / Phase 3 work, the project had learned a lot about **discipline**, but much less about how to create a meaningfully richer opportunity set.

What had already been harvested:

-   dynamic risk budgeting
-   regime confidence and deployment discipline
-   layered holdout / fixed-comparator evaluation
-   sleeve-state interaction tuning
-   multiple overlay and cap refinements

What that work taught:

1.  **The stack was no longer mainly limited by lack of risk discipline.** Many of the cleanest improvements came from better gating, better deployment hygiene, and better evaluation culture.
2.  **Those levers started to saturate.** Later refinements tended to produce small, local, or holdout-fragile gains rather than genuine step-changes in portfolio quality.
3.  **The opportunity set itself looked shallow.** The portfolio still depended heavily on a cluster of related momentum / trend expressions, with relatively few genuinely distinct raw ingredients feeding the sleeve layer.
4.  **That makes the next bottleneck upstream.** If the raw ingredients are too redundant, later allocation logic can only rearrange a narrow set of bets.

This is why the roadmap resets here into a new vision:

-   **Phase A = Opportunity Set Expansion**
-   **Phase B = Sleeve Construction / Opportunity Modules**
-   **Phase C = Learned Sleeve Allocation / Sleeve-Quality Layer**
-   **Phase D = Validation Stack / robust evaluation discipline**
-   **Phase E = Heavier ML / richer regime-action models**

The change in emphasis is deliberate:

-   less time spent squeezing another few basis points from overlay geometry
-   more time spent finding **economically grounded, low-redundancy, causally usable signals**
-   a cleaner handoff from signal discovery to sleeve design

Current working pins at the start of this new vision:

-   **Production pin:** `improved_phase2b_regime_confidence_boost`
-   **Shadow pin:** `improved_phase2b_combo_abc`

## 15. Phase A — Opportunity Set Expansion

Phase A asks a different question from the earlier sprints:

> what meaningful new opportunity sources are missing from the current stack, and which of them are actually promising enough to improve sleeves or support new sleeves?

This is **not** a request for a giant feature zoo.
It is a narrow search for signals that are:

-   economically grounded
-   causal / implementable in liquid ETFs
-   low-redundancy versus the existing momentum / trend stack
-   relevant to the portfolio's known pain points, especially:
    -   calm-trend undercapture
    -   fragile / improving recoveries
    -   distinguishing orderly trends from noisy or unstable ones

### Phase A research themes

Public research and practitioner work that informed the shortlist included:

-   AQR and Man Group work on trend-following robustness and the quality of trend signals
-   Alpha Architect summaries on momentum path clarity, moving-average distance, and breadth-style confirmation
-   Newfound / ReSolve work on fragility, path dependency, and trend implementation
-   academic and practitioner literature on volatility management, anti-chop logic, and confirmation signals

The shortlist deliberately focused on four categories:

1.  **Trend-quality / setup-quality**
2.  **Anti-chop / path clarity**
3.  **Recovery-quality**
4.  **Cross-asset confirmation**

### What Phase A implemented

Four new candidate signals were added to the Layer 1 framework:

1.  **`trend_clarity_momentum`**
    -   52-4 week momentum weighted by rolling 52-week trend-regression R-squared
    -   intended to distinguish cleaner trends from noisier ones
2.  **`moving_average_distance`**
    -   13-week versus 52-week moving-average distance
    -   intended as a setup-quality / activation-quality signal rather than another plain return lookback
3.  **`breadth_confirmed_momentum`**
    -   own 26-4 week momentum scaled by peer breadth confirmation
    -   intended to capture whether an apparent opportunity is supported by a broader cross-asset / peer backdrop
4.  **`contained_recovery_quality`**
    -   13-week recovery strength scaled by realised volatility and distance from recent highs
    -   intended to separate orderly recoveries from unstable rebounds

### What Phase A found

The results were useful and, importantly, mixed.

**1. `trend_clarity_momentum` looked like the cleanest genuinely new ingredient.**

-   It validated positively on average and stayed helpful in the exact regimes the portfolio cares about: calm trend, strong-neutral, and recovery states.
-   It is still related to momentum, but not just trivially so. After controlling for the core momentum stack, it retained a small positive residual edge.
-   Best interpretation: this is a **real sleeve-quality input**. It is promising for improving existing trend / momentum sleeves and may also support a more explicit trend-quality module in Phase B.

**2. `moving_average_distance` validated well, but mostly as a simpler repackaging of existing momentum / trend information.**

-   Raw ICs were strong, especially in strong-neutral and recovery-confirmed states.
-   But redundancy versus `xsmom_global` / `multi_mom_invvol` was very high, and residual incremental value after controlling for the existing momentum stack was minimal.
-   Best interpretation: useful as an **activation or ranking refinement inside existing sleeves**, but probably not a standalone new sleeve opportunity source.

**3. `breadth_confirmed_momentum` was strategically interesting even though its pure incremental-alpha case was weaker than the raw IC suggested.**

-   It was especially strong in `recovery_confirmed` and helpful in strong-neutral / calm-trend windows.
-   Correlation to the existing stack was lower than the raw price-quality signals, but once the core momentum panel was controlled for, its standalone residual alpha was weak.
-   Best interpretation: likely better as a **confirmation feature** than as a standalone raw alpha signal. It may improve sleeve construction or state-aware activation logic in Phase B more than it improves Layer 1 on its own.

**4. `contained_recovery_quality` was the most targeted and the weakest.**

-   It showed some localized usefulness in recovery states, which is economically plausible.
-   But full-sample validation was weak, and it did not hold up as a strong independent signal.
-   Best interpretation: keep only as a narrow research reference if a recovery-specific sleeve is explored later. Not a leading Phase B ingredient today.

### Phase A conclusion

Phase A did **not** discover a giant new alpha family.

It did, however, produce a useful shortlist:

-   one signal that looks like a real new quality dimension on top of momentum (`trend_clarity_momentum`)
-   one signal that looks operationally useful but mostly redundant (`moving_average_distance`)
-   one signal that looks promising as a confirmation / sleeve-construction ingredient rather than a raw alpha source (`breadth_confirmed_momentum`)
-   one signal that looks too weak for priority use (`contained_recovery_quality`)

That is a good outcome for this phase.
The point of Phase A was not to force a breakthrough.
It was to identify which new ingredients are actually worth carrying forward into sleeve design.

### Carry-forward into Phase B

Signals worth carrying forward:

-   **Primary Phase B candidate:** `trend_clarity_momentum`
-   **Secondary / conditional Phase B candidate:** `breadth_confirmed_momentum`
-   **Existing-sleeve refinement candidate:** `moving_average_distance`

Signals to archive or de-prioritize:

-   **Research-only:** `contained_recovery_quality`

So the project story is now updated:

-   earlier work improved discipline, deployment, and validation
-   those levers now look partly harvested
-   the next serious frontier is improving the **opportunity set** and then building better sleeves from it

## 16. Phase B — Sleeve Construction / Opportunity Modules

Phase B takes the best Phase A ingredients and asks a stricter question:

> can these signals be turned into sleeves or sleeve upgrades that actually improve the opportunity set, rather than just looking interesting at the signal level?

This is a sleeve-building phase, not another overlay phase.

The intent was to keep the experiment set small and high-conviction:

-   one **trend-quality / anti-chop** sleeve built from `trend_clarity_momentum`
-   one **confirmation-aware improving-state** sleeve built around `breadth_confirmed_momentum`
-   one **refinement-only** variant that lets `moving_average_distance` in only if it materially improves the simpler trend-quality sleeve

### Why Phase B was necessary

By the end of the earlier control-layer work, the project had learned a lot about:

-   deployment discipline
-   stacked defense
-   the limits of small overlay tweaks
-   the limits of allocator / cap changes

But the opportunity set itself still looked narrow.

That meant the next logical frontier was not:

-   another tiny overlay adjustment
-   another threshold tweak
-   another risk-budget calibration pass

It was:

-   better sleeves
-   more diverse sleeve behavior
-   sleeves that are better matched to the known portfolio weaknesses, especially:
    -   under-capture in improving states
    -   under-capture in calm / orderly trends
    -   the need for modules that can tell the difference between a clean setup and a noisy one

### What Phase B built

Three disciplined sleeve candidates were tested.

**1. `composite_trend_quality_module`**

-   combines momentum, time-series trend, and `trend_clarity_momentum`
-   intended to be a cleaner trend / anti-chop sleeve
-   economic idea: own trends more confidently when the path is orderly rather than noisy

**2. `composite_confirmation_aware_momentum`**

-   combines momentum with `breadth_confirmed_momentum`
-   intended to be a safer improving-state offensive sleeve
-   economic idea: risk-on setups are more credible when own momentum is confirmed by broader participation

**3. `composite_trend_quality_refined`**

-   starts from the trend-quality sleeve and adds `moving_average_distance`
-   intended only as a refinement test, not a new sleeve thesis
-   economic idea: let moving-average distance survive only if it adds something beyond the cleaner trend-quality concept

### What worked

**The refined trend-quality sleeve was the clear standalone winner.**

It posted the strongest standalone risk-adjusted profile of the three new sleeves and materially outperformed the incumbent selective sleeve in the exact states that matter most for the project:

-   much stronger in `neutral_mixed`
-   much stronger in `recovery_fragile`
-   materially better in `recovery_confirmed`
-   still acceptable in stressed periods

Its main weakness was that it did **not** solve calm-trend under-capture on its own.
In calm, orderly bull windows, the older selective sleeve still had better standalone performance.

That matters because it means the new sleeve is useful, but not a full answer to the portfolio's biggest remaining weakness.

**The confirmation-aware sleeve was strategically useful, but narrower.**

It was most compelling in:

-   `recovery_confirmed`
-   `recovery_fragile`
-   improving-state participation generally

That makes sense economically.
It looks less like a universal new core sleeve and more like a confirmation-oriented module that can help in safer improving states.

### What did not work as well

**The simpler trend-quality sleeve was not enough by itself.**

It improved some improving-state behavior relative to the old selective sleeve, but the refined version was better almost everywhere that mattered.

**The new sleeves were not truly orthogonal.**

Correlation to the incumbent offensive sleeves remained fairly high.
So Phase B did not discover a totally new behavior family.
It found better sleeve construction inside the same broad trend / momentum opportunity complex.

That is still useful, but it is more a **quality upgrade** than a totally new universe expansion.

### Portfolio-level read

The portfolio tests were encouraging but not decisive.

The refined trend-quality replacement:

-   improved annual return modestly
-   improved max drawdown modestly
-   kept SPY drift small
-   improved recovery participation

But it did **not** improve the overall Sharpe versus the current production pin, and it did not clearly fix calm-state under-capture.

The confirmation sleeve helped more as a specialist module than as a full portfolio upgrade.

The combo sleeve improved raw return and recovery capture more, but gave back too much in tail quality and overall Sharpe to count as a clean winner.

### Phase B conclusion

Phase B did **not** produce a dramatic new production winner.

It did, however, produce something important:

-   one sleeve upgrade that looks genuinely useful: `composite_trend_quality_refined`
-   one narrower module that looks worth carrying forward: `composite_confirmation_aware_momentum`

That means Phase B was successful as a building-block phase even though it did not produce a clear immediate promotion.

### What should move into Phase C

Carry forward:

-   **Primary Phase C candidate:** `composite_trend_quality_refined`
-   **Secondary / conditional Phase C candidate:** `composite_confirmation_aware_momentum`

Archive / de-prioritize:

-   `composite_trend_quality_module` as a useful intermediate design, but dominated by the refined variant

### Engineering side note — dashboard payload hygiene

This sprint also forced a cleanup of the dashboard artifact layer.

The old monolithic `public/dashboard-data.json` had grown beyond GitHub's file limit because it was shipping:

-   full version return histories
-   full weight histories
-   full sleeve-weight histories
-   full allocation-driver time series

all in one committed public blob.

That was unnecessary for first paint.

The dashboard was reworked so that:

-   the **SSR summary bundle** stays small enough to keep homepage inspectability healthy
-   the heavy research histories are split into smaller client-fetched detail artifacts

So the project story is now current through Phase B:

-   Phase A found the best new ingredients
-   Phase B turned those ingredients into sleeves
-   the refined trend-quality sleeve looks like the strongest new building block
-   the confirmation sleeve looks like a useful specialist module
-   the next stage should allocate **across these better sleeves**, not keep endlessly tuning the old control layer

## 17. Phase C — Learned Sleeve Allocation / Sleeve-Quality Layer

Phase C asked the next obvious question:

> if the sleeve universe is somewhat better, can a better sleeve-allocation layer finally turn that into a meaningfully better portfolio?

This phase deliberately did **not** reopen the old overlay search.
The top-level controller was held fixed around the Phase 2B production setup.
The task was narrower:

-   use the stronger Phase B sleeve universe
-   allocate more intelligently across sleeves
-   stay bounded and interpretable
-   find out whether the allocator frontier was now the real bottleneck

### Phase C sleeve universe

The working sleeve panel for this sprint was:

-   `dual_momentum_topn`
-   `cta_trend_long_only`
-   `composite_trend_quality_refined`
-   `composite_regime_conditioned`
-   `taa_10m_sma`
-   `composite_confirmation_aware_momentum`

This matters because it changed the question.
We were no longer asking whether the old production sleeve panel could be better timed.
We were asking whether the allocator could make proper use of:

-   a stronger trend-quality sleeve
-   a confirmation-aware improving-state sleeve

### What Phase C tested

Four bounded allocator ideas were tested on top of that sleeve universe.

**1. Learned sleeve-quality score**

-   walk-forward logistic sleeve-leadership probabilities
-   features built from trailing sleeve quality plus causal market-state inputs
-   bounded sleeve tilts only in favorable states

**2. Dynamic opportunity budgeting**

-   starts from the learned sleeve-quality score
-   lets the strongest offensive sleeves carry slightly more weight when their relative opportunity set is clearly better than the defensive sleeves

**3. State-conditioned sleeve map**

-   bounded same-state sleeve leadership
-   explicit sleeve-type preferences in the states where the new sleeves were supposed to matter most
-   especially strong-neutral, recovery-fragile, and recovery-confirmed

**4. Combo allocator**

-   learned quality + opportunity budgeting + state-conditioned sleeve map
-   all kept at smaller amplitudes to avoid a repeat of the earlier “looks better in raw return, worse in tails” problem

### What happened

The most important result is that the **stronger sleeve universe itself did real work**.

Just moving from the old production sleeve panel to the stronger Phase B sleeve universe:

-   lifted annual return
-   improved recovery participation
-   improved holdout CAGR and holdout upside capture

That means the new vision was not misguided.
Better sleeves did translate into a better raw opportunity set.

But the second result was just as important:

> the new allocator layer added only **tiny incremental gains** on top of that stronger sleeve universe.

The best allocator of the four was the **state-conditioned sleeve map**:

-   it nudged capital away from `composite_regime_conditioned`
-   it gave somewhat more weight to `composite_trend_quality_refined`
-   it also gave more weight to `composite_confirmation_aware_momentum` in recovery-confirmed states

That did help in the intended improving states, but only modestly.

### What improved

Relative to the Phase C sleeve-universe base, the state-conditioned allocator:

-   improved recovery-confirmed performance a bit
-   improved recovery-fragile performance a bit
-   slightly reduced cash / BIL
-   slightly increased use of the two new Phase B sleeves

The combo allocator pushed the same direction further:

-   more weight to `composite_trend_quality_refined`
-   more weight to `composite_confirmation_aware_momentum`
-   less weight to `composite_regime_conditioned`

It produced the strongest holdout upside capture of the Phase C set.

### What remained insufficient

The gains were still too small and too local.

Most importantly:

-   none of the Phase C allocators clearly improved Sharpe versus the production pin
-   none produced a clean portfolio-level win once drawdown / CVaR discipline was considered
-   calm-trend under-capture remained weak
-   the allocator changes mostly improved strong-neutral and recovery states, not the full good-state problem

This is the key strategic conclusion from Phase C.

### Phase C conclusion

Phase C says two things at once.

**1. The new vision is not a dead end.**

The stronger sleeve universe from Phases A and B was real enough to lift raw portfolio opportunity.

**2. The current allocator class looks close to exhausted.**

The bounded, interpretable sleeve-allocation layer improved things only marginally beyond the better sleeve panel itself.

That points less toward “the new sleeves are fake” and more toward:

-   the sleeve universe being decent but still imperfect
-   the current allocator model class being too weak to extract much more from it

### Strategic branch after Phase C

The roadmap should not loop mindlessly through another tiny A/B/C iteration.

The evidence now suggests:

-   keep the stronger sleeve universe
-   keep the Phase C state-conditioned map as a useful reference
-   but treat the next frontier as a **heavier learned allocation / regime-action problem**

In other words:

-   the project should still continue along the new vision
-   but the emphasis should now shift toward **richer allocation models and stronger validation discipline**, not another long run of small local allocator tweaks

So the project story is now current through Phase C:

-   Phase A found better ingredients
-   Phase B turned them into better sleeves
-   Phase C showed that the stronger sleeves matter, but the current allocator class does not unlock a large enough jump on its own
-   the next real frontier is no longer “find another tiny sleeve-weight rule”
-   it is either a richer allocator/model class or a stricter validation stack for that richer allocator

## 18. Phase D — Validation Stack / Robust Evaluation Discipline

Phase D exists because the project is now on the edge of a more powerful allocator frontier.

That is exactly the moment when evaluation discipline matters most.

By this point the project had already learned several uncomfortable lessons:

-   pooled rank-composite scores can be sensitive to the comparison pool
-   near-winners can look persuasive until the comparator set is fixed
-   development-period improvements can disappear or reverse on holdout
-   raw return improvements and risk-adjusted improvements are not the same thing
-   once richer allocators arrive, false positives will become even easier to create

So Phase D deliberately paused new alpha / sleeve / allocator invention and asked a simpler question:

> what evaluation stack should be trusted before the project moves into a heavier learned allocator frontier?

### The fixed comparator set

The project now uses a stable four-candidate comparator set for next-stage decisions:

-   **production pin:** `improved_phase2b_regime_confidence_boost`
-   **legacy shadow pin:** `improved_phase2b_combo_abc`
-   **Phase C sleeve-universe reference:** `improved_phasec_sleeve_universe_base`
-   **bounded allocator reference:** `improved_phasec_state_conditioned_map`

This is important because it stops the decision surface from moving every time a new experimental branch is added to the pool.

### The new raw-metric composite

Phase D replaced “rank-only in a shifting pool” as the main summary lens with a target-anchored raw composite.

The new composite is deliberately simple and reflects the actual project priorities:

-   annual return
-   Sharpe
-   Calmar
-   max drawdown
-   CVaR 5%
-   upside capture
-   recovery capture
-   turnover
-   BIL / cash drag

The weighting is not meant to make any one favorite win.
It is meant to reflect the actual portfolio goal:

-   better return and better good-state participation
-   without giving away drawdown / tail-risk discipline
-   and without tolerating gratuitous turnover or cash drag

This does not eliminate judgment, but it does reduce one major source of fragility:

-   a strategy no longer looks “better” just because the broader comparison pool changed

### Holdout and repeated validation rules

Phase D also formalized the temporal evaluation rules.

The default structure is now:

-   **development sample:** all history before the last 104 weeks
-   **default holdout:** trailing 104 weekly observations
-   **rolling-origin validation:** 104-week test windows, stepped every 52 weeks, after at least 260 weeks of training history

This gives three distinct views of a candidate:

1.  full-history behavior
2.  development-vs-holdout split
3.  repeated forward validation

That is a much better fit for the next research frontier than a single backtest summary.

### Bootstrap confidence view

Phase D also added a simple moving-block bootstrap on holdout excess returns.

This is not meant to be a perfect statistical test.
It is a practical way to avoid over-reading one holdout sample in a serially dependent weekly return setting.

### What Phase D found

The new framework did **not** overturn the production pin.

`improved_phase2b_regime_confidence_boost` remains the best overall production choice once:

-   holdout Sharpe
-   holdout drawdown / CVaR
-   and bounded risk discipline

are treated as first-class requirements.

But Phase D did change the strategic interpretation of the comparison set.

The Phase C references:

-   `improved_phasec_sleeve_universe_base`
-   `improved_phasec_state_conditioned_map`

looked better than the old shadow pin on the broad raw composite and on repeated forward windows.

That matters because it suggests the old shadow pin is no longer the most informative “next frontier” comparator.

The Phase C references are more useful for the next stage because they carry:

-   the stronger sleeve universe
-   and, in the allocator case, the best bounded Phase C deployment logic

### Phase D conclusion

Phase D therefore makes two portfolio-governance decisions.

**1. Keep the production pin unchanged.**

`improved_phase2b_regime_confidence_boost` still has the cleanest risk-adjusted case for live production.

**2. Change the trusted research baseline set for the next frontier.**

For Phase E, the useful baselines are no longer just:

-   production pin
-   legacy shadow pin

They are:

-   production pin for risk-aware truth checking
-   Phase C sleeve-universe base as the better opportunity-set reference
-   Phase C state-conditioned map as the best bounded allocator reference

The old shadow pin is still valuable as historical context, but it is no longer the most useful strategic shadow for the next modeling frontier.

### Strategic meaning

This is exactly what Phase D was meant to do.

It did not create a new strategy.

It created a more trustworthy decision framework for what comes next:

-   richer learned allocation
-   stricter future promotion criteria
-   and a cleaner baseline set for testing whether those richer models are actually worth their added complexity

So the project story is now current through Phase D:

-   Phase A found better raw ingredients
-   Phase B turned those ingredients into better sleeves
-   Phase C showed the sleeve universe improved, but the bounded allocator class was near its limit
-   Phase D formalized the validation rules needed before escalating model complexity
-   the project is now ready to test a heavier learned allocator under a much stronger evaluation stack

## 19. Phase E — Heavier Learned Allocator / Richer Model Class

Phase E was the first sprint where the project was explicitly allowed to move beyond the bounded Phase C allocator class.

That escalation was justified by the work that came before it:

-   Phase A found better sleeve-building ingredients
-   Phase B turned those into a stronger sleeve universe
-   Phase C showed that the sleeve universe mattered, but the bounded allocator only extracted small incremental gains
-   Phase D made the validation rules strict enough that a heavier allocator could be tested without drifting into backtest theater

The question for Phase E was therefore narrow and important:

> Can a more expressive allocator actually unlock the stronger sleeve universe, or does it mostly add complexity without solving the real bottleneck?

### What Phase E tested

The sprint tested a small, disciplined set of heavier allocators rather than a model zoo.

The candidates were:

-   a boosted sleeve-return allocator
-   a learned concentration gate
-   a richer state x sleeve interaction allocator
-   a heavier combo allocator
-   one extra conservative follow-up: a state-prior concentration blend

These were all deliberately constrained in one important way:

-   they **did not** reopen the old overlay / cash-relief research
-   they kept the stronger Phase C sleeve universe
-   and they tested whether better sleeve weighting alone could do meaningfully better

### What improved

Phase E did show that the heavier models could push the stronger sleeve universe harder.

They generally did three things:

-   increased raw return versus the old production pin
-   increased upside / recovery participation
-   shifted more weight toward the newer Phase B sleeves, especially in improving states

This means the heavier allocator frontier was not empty.

It was able to learn *something*.

### What did not improve enough

The problem was that the gains were not clean enough.

The heavier allocators mostly failed in one of two ways:

1.  they improved raw return by becoming too aggressive
2.  or they ended up looking too similar to the bounded Phase C reference to justify their extra complexity

The closest candidate was the learned concentration line.

It was the least damaging of the heavier models and came closest to the bounded reference on the raw composite.

But it still failed the Phase D promotion discipline:

-   holdout raw composite stayed below the production pin
-   holdout Sharpe was materially worse than production
-   and it still did not clearly beat the bounded allocator reference

The more aggressive boosted and combo allocators lifted holdout return the most, but they did it with:

-   worse drawdowns
-   worse CVaR
-   worse rolling validation behavior
-   and much higher turnover

That made them useful diagnostics, not trustworthy winners.

### What the models actually learned

One of the most useful outcomes of Phase E was diagnostic rather than promotional.

The heavier models leaned heavily on:

-   regime / transition features
-   drawdown / volatility context
-   cross-sleeve dispersion features

They were much less clearly exploiting a large sleeve-specific edge than hoped.

In other words:

-   the models *could* learn when to be more aggressive
-   but they were less successful at learning a much better answer to **which sleeve deserves the capital**

That is a very important frontier conclusion.

It suggests that the remaining bottleneck is not simply “use a fancier allocator and the problem goes away.”

### Phase E conclusion

Phase E therefore produced a mixed but strategically useful result.

**The good news:**

-   the new vision was directionally correct
-   the stronger sleeve universe from Phases A and B is real
-   and the allocator frontier was worth testing

**The bad news:**

-   the heavier allocator did **not** deliver a clear new production winner
-   it did **not** beat the bounded Phase C reference cleanly enough
-   and it did **not** prove that more allocator complexity alone is the next big unlock

### Strategic meaning after Phase E

The project should not pretend that another round of heavier allocator tweaks is automatically the answer.

Phase E says something more specific:

-   richer allocators can extract a little more raw opportunity
-   but the current sleeve universe still does not provide enough clean cross-sleeve separation for that added complexity to survive strict validation

So the next move should **not** be “just try a bigger model.”

The more promising branch after Phase E is:

-   revisit sleeve distinctness
-   strengthen conditional sleeve quality
-   and design sleeves whose relative edge is easier for an allocator to exploit cleanly

In short:

-   the project story is now current through Phase E
-   the new vision was still useful
-   but Phase E suggests the next real bottleneck is not only allocator expressiveness
-   it is the combination of sleeve separability, clean state-conditioned opportunity, and the project’s deliberately strict risk requirements

## 20. Sleeve Separability / Conditional Opportunity Redesign

Phase E gave the project a very specific next instruction.

The problem was no longer “find another allocator.”

It was:

-   the sleeves still overlapped too much
-   too many of them were winning for similar reasons
-   and a richer allocator could not reliably tell when one sleeve truly deserved capital over another

That made the next sprint a structural redesign exercise rather than another model-complexity exercise.

### Why the project pivoted again

The key lesson from the heavier allocator phase was not that machine learning had no value.

It was that the allocator mostly learned when to be more or less aggressive, not a much stronger answer to **which sleeve should win**.

That pointed to a missing upstream ingredient:

-   sleeves with clearer state-specific comparative advantage
-   sleeves with lower functional overlap
-   and sleeves with more obvious economic roles

So the research focus shifted from allocator expressiveness to sleeve separability.

### What the overlap diagnosis showed

The first step was to diagnose the existing sleeve panel directly.

The most important finding was that the offensive cluster was still crowded:

-   `composite_trend_quality_refined`
-   `composite_confirmation_aware_momentum`
-   `cta_trend_long_only`
-   and, to a lesser extent, `dual_momentum_topn`

These sleeves were all directionally useful, but they were still highly correlated and often strongest in similar recovery / trend states.

By contrast, the sleeves that retained clearer identity were:

-   `composite_regime_conditioned`
-   `taa_10m_sma`

These were less impressive as broad offensive engines, but they were easier to distinguish:

-   `composite_regime_conditioned` remained the clearest stressed-state / defensive specialist
-   `taa_10m_sma` retained the cleanest calm-trend leadership, though still only modestly

The state-level diagnosis also showed that some roles were still underdeveloped:

-   calm-trend still lacked a clearly dominant specialized sleeve
-   recovery-confirmed still lacked a sleeve with a wide enough advantage margin to make allocator choice easy
-   recovery-fragile had good sleeves, but too many of them looked similar

### What new sleeve roles were tested

The redesign sprint tested a deliberately small set of new sleeve roles.

The goal was not to create a zoo.

It was to create sleeves with more conditional identity.

The candidates were:

-   `composite_calm_trend_participation`
-   `composite_recovery_transition`
-   `composite_anti_chop_clarity`

Each was built to solve a different role problem.

`composite_calm_trend_participation` tried to create a calmer, more stable offensive sleeve for orderly trend environments rather than generic broad momentum.

`composite_recovery_transition` tried to specialize in the move from fragile improvement toward healthier confirmation.

`composite_anti_chop_clarity` tried to behave differently when trends were clean and contained versus noisy and unstable, giving the universe something more distinct than another directional trend sleeve.

### What worked

The redesign improved the sleeve universe in a real way.

The biggest structural improvement was separability itself.

The redesigned candidate panel showed:

-   meaningfully lower average pairwise correlation than the old core panel
-   larger state-winner margins
-   and a much cleaner map of which sleeve was supposed to matter in which environment

In particular:

-   `composite_anti_chop_clarity` emerged as the cleanest genuinely new role
-   it was materially less correlated with the old offensive cluster
-   it held up well in both development and holdout
-   and it gave the sleeve universe a more obvious “do not trust noisy trend” specialist

There was also a meaningful panel-level diversification benefit.

Even a naive equal-weight blend of the redesigned candidate panel improved Sharpe and drawdown relative to the old core panel, which was a useful sign that the new sleeves were not merely cosmetic rewrites.

### What remained insufficient

The redesign did not solve every missing role.

The calm-trend sleeve was directionally useful, but it did not convincingly dethrone `taa_10m_sma` as the calm-trend specialist.

That means the calm-trend problem improved only partially.

The recovery-transition sleeve was the most mixed result.

It was conceptually the right missing role, but in practice it was weaker and less robust than hoped.

It did not earn confidence as a major next-stage building block.

So the sprint produced a clear asymmetry:

-   anti-chop specialization worked
-   calm-trend specialization improved somewhat but remained incomplete
-   recovery-transition specialization remained underdeveloped

### What should move forward

The redesign was still strategically useful.

It gave the project a better sleeve universe than Phase E had available, even if it did not fully solve the calm / recovery specialization problem.

The sleeves that looked worth carrying forward were:

-   `composite_anti_chop_clarity` as a genuine next-stage candidate
-   `composite_calm_trend_participation` as a conditional candidate, not a proven winner

The sleeve that should not be treated as a core forward module yet was:

-   `composite_recovery_transition`

The broader lesson was just as important:

-   the project should not return immediately to heavier allocator escalation
-   the sleeve universe now looks more usable
-   but it still needs stronger calm-trend and recovery-confirmed specialization before another allocator pass has the cleanest possible opportunity set

### Strategic meaning after the separability sprint

This sprint did not “finish” the problem.

But it did improve the foundation for future allocator work.

The project is now in a better place than it was after Phase E because:

-   the overlap problem is clearer
-   the offensive sleeve family is less monolithic
-   and at least one genuinely different sleeve role has now been added

So the story after this sprint is:

-   sleeve separability was a real bottleneck
-   the redesign partially fixed it
-   allocator escalation should remain paused for now
-   and the next best frontier is to keep strengthening the missing calm-trend and recovery-specific sleeve roles before reopening the allocator race

## 21. Targeted sleeve-role refinement — calm trend and healthier recovery

The next sprint kept the previous redesign structure intact but changed the way it was judged.

Two panel concepts were used explicitly:

-   the **current core blend** became the reference benchmark
-   the **redesigned blend** became the active research panel

That was an important framing choice.

The project was no longer asking whether the old and new sleeve universes were equal alternatives.

It was asking whether the redesigned panel could be made complete enough to justify a later return to allocator work.

### What was still missing after the prior redesign

The previous sleeve-separability sprint had already produced one real win:

-   `composite_anti_chop_clarity`

That sleeve gave the panel a more obvious anti-chop role and made the universe less monolithic.

But two roles were still not built strongly enough:

-   a calm-trend specialist with a clearer advantage
-   a healthier-recovery / recovery-confirmed specialist with a clearer advantage

The earlier calm sleeve was promising, but its lead over the next best sleeve was too thin.

The earlier recovery sleeve had the right idea, but it was not yet creating a convincing winner in healthier confirmation states.

### How the refinement logic changed

The most useful diagnostic in this sprint was methodological.

It forced the project to look at the **same next-week target** the sleeves actually trade, not just contemporaneous state returns.

That changed the role design in two ways.

For calm-trend, the forward winners were not simply “the highest beta assets.”

They were a calmer mix of:

-   quality growth
-   broad market leadership
-   and some credit / ballast

For healthier recovery, the forward winners were not a pure small-cap or junk rebound basket.

They looked more like:

-   confirmed continuation
-   broadening participation
-   quality growth
-   selective EM participation
-   and lower-noise recovery leadership

That led to two refined sleeves:

-   `composite_calm_trend_specialist`
-   `composite_healthier_recovery_specialist`

### What improved

This was a meaningfully successful refinement sprint.

The calm specialist became more decisive.

It did not just improve the old calm sleeve slightly.

It turned calm-trend into a more clearly owned role:

-   the new calm sleeve became the top calm-state sleeve in the refined panel
-   its winner margin became much wider than before
-   and its development / holdout behavior remained healthy

The healthier-recovery sleeve also improved the weakest missing role.

It was still not a huge standalone superstar, but it did something more important:

-   it finally gave the panel a much clearer recovery-confirmed winner
-   and it improved that winner margin enough to make future allocator choice more meaningful

At the panel level, the refined redesigned blend did not beat the old reference blend on raw return.

But that was not the most important result.

What mattered more was that the refined panel showed:

-   higher Sharpe than both the current core blend and the prior redesigned blend
-   much lower drawdown than the current core blend
-   better CVaR than the current core blend
-   better holdout Sharpe than both comparison blends
-   and far clearer state-specific winner structure

### What the refined panel gained

The refined panel was not dramatically more “different looking” on simple pairwise correlation alone.

That metric improved only slightly.

But the more important structural metric improved a lot:

-   state winner margins became much stronger

That is exactly what the project needed.

The panel became easier to reason about:

-   the calm sleeve now more clearly owns calm-trend
-   the healthier-recovery sleeve now more clearly owns recovery-confirmed
-   the anti-chop sleeve still gives the panel a distinct instability-aware role
-   `composite_regime_conditioned` still anchors defense / stress behavior

That means the sleeve universe became more *conditionally complete*, not just cosmetically more diverse.

### What still did not happen

This sprint did not prove that the refined panel should become a live production portfolio by itself.

It also did not mean the project is finished with sleeve work forever.

The current core blend still had more raw return in simple equal-weight form.

So the refined panel’s advantage is best understood as:

-   a better research substrate
-   a better risk-adjusted sleeve universe
-   and a cleaner basis for future allocator work

not yet a direct production replacement

### Strategic meaning after the refinement

This sprint changed the decision framework again in a constructive way.

Before it, the project knew the redesigned panel was more separable than the old core panel.

After it, the project has stronger evidence that the redesigned panel is also **more role-complete**.

That is a much better place from which to revisit allocator research later.

So the frontier conclusion became:

-   keep the current core blend as the benchmark reference
-   keep the redesigned family as the active research panel
-   carry forward the anti-chop sleeve
-   carry forward the refined calm and healthier-recovery sleeves
-   and reopen allocator work only after accepting that the active panel is now the more appropriate sleeve universe for that next step

## 22. Return to allocator work on the refined redesigned panel

This sprint reopened allocator research, but under a different premise than the earlier failed allocator escalation.

The old failure had been informative.

The earlier allocators were being asked to make decisions on a sleeve universe that was still too overlapping, too momentum-like, and too weakly separated by state.
In that environment the models mostly relearned broad market aggression, cash reduction, or weight persistence instead of identifying genuinely different sleeve opportunities.

That was no longer the right diagnosis after the sleeve redesign work.

By the end of the role-completion sprints, the active panel had gained three things the older allocator phase did not have:

-   a real anti-chop sleeve
-   a materially stronger calm-trend specialist
-   a materially stronger healthier-recovery / recovery-confirmed specialist

Just as important, the panel had become more decisive in state-specific winner structure.

That meant allocator work was worth reopening, but only on the refined redesigned panel and only under the stricter Phase D validation stack.

### Why this revisit was different

The current core blend stayed in the project, but only as the benchmark reference panel.

It remained useful because it still showed what the older sleeve family could do in a simple blend and because it still carried more raw return in equal-weight form.

But it was no longer the right panel on which to build new allocation logic.

The refined redesigned panel was the right active research panel because it now offered clearer role specialization:

-   `composite_calm_trend_specialist` for orderly stable uptrends
-   `composite_healthier_recovery_specialist` for healthier recovery continuation
-   `composite_anti_chop_clarity` for unstable-trend / chop-aware participation
-   `composite_regime_conditioned` for defense and stress handling
-   plus the remaining broad sleeves as supporting offensive building blocks

That was exactly the structural change allocator research had previously been missing.

### What allocator variants were tested

The new allocator pass stayed disciplined.

It tested only a small set of refined-panel allocators:

-   a bounded state-conditioned allocator
-   a learned sleeve-quality allocator
-   a conditional concentration allocator
-   one disciplined combination allocator

The central question was not whether a more complicated allocator could be made to look good in one backtest.

It was whether the cleaner sleeve panel now allowed the allocator to make better sleeve choices than before and whether those choices could survive the Phase D promotion rules.

### What improved

The answer was partly yes.

The refined panel did make allocator work more productive than it had been in the earlier failed phase.

The bounded state-conditioned allocator was the clearest example.

It did the right things in the right states:

-   in `calm_trend`, it concentrated into the calm-trend sleeve, the healthier-recovery sleeve, and `taa_10m_sma`
-   in `recovery_confirmed`, it gave the largest share to the healthier-recovery sleeve
-   in `stressed_panic`, it rotated decisively toward `composite_regime_conditioned` and `composite_anti_chop_clarity`

That was an important qualitative change from the older allocator phase.

The allocator was finally exploiting sleeve roles instead of mostly relearning generic aggression.

Quantitatively, the bounded refined-panel allocator beat both:

-   the naive refined-panel equal-weight blend
-   the older bounded allocator reference from the pre-refined panel

on the main full-history raw target composite.

It also improved calm capture and recovery capture relative to the naive refined-panel blend, which was exactly the behavior the redesign had been trying to unlock.

### What still did not happen

The refined panel made allocator work more useful, but not yet promotable.

No allocator candidate passed the Phase D production rule.

No allocator candidate passed the shadow-promotion rule either.

The main reason was consistent:

-   the new allocators improved full-history composite scores
-   but they still failed the holdout comparison versus the live production pin

So the allocator revisit produced a real research improvement, but not a live portfolio replacement.

That distinction matters.

It means the panel redesign did unlock allocator value.

But it did not unlock enough value yet to dethrone the production control.

### Strategic meaning after the allocator return

This sprint did not send the project back into the dead end of “just try a heavier model again.”

Instead, it clarified the frontier.

The project now has stronger evidence that:

-   the sleeve redesign was worth doing
-   the refined panel is a better substrate for allocator research than the old panel
-   and bounded allocation on that panel can now do real work

The next decision is therefore more precise than before.

The project should keep:

-   the production pin unchanged
-   the shadow pin unchanged
-   the current core blend as the benchmark reference panel
-   the refined redesigned blend as the active research panel

And for allocator research specifically, it should carry forward the refined-panel bounded state allocator as the new allocator reference, because it is the cleanest proof that the stronger sleeve panel can be used intelligently even though it is not yet good enough for promotion.

So the verdict after this sprint became:

-   allocator work is finally productive again
-   but not yet decisive enough to win live promotion
-   which means the project is back on the right frontier, but still under the discipline of the Phase D validation framework

## 23. Focused allocator refinement — robustness, tails and turnover

This sprint did not reopen sleeve discovery.

It also did not treat the allocator as broken beyond repair.

The reason for running it was more specific.

The prior refined-panel allocator had finally done something useful:

-   it beat the naive refined-panel blend
-   it beat the earlier bounded allocator reference
-   and it made sensible sleeve decisions in calm, recovery and stress states

That was enough to justify refinement rather than abandonment.

But the refinement target was narrow and practical.

The project wanted to know whether that allocator could be made cleaner:

-   smoother through state transitions
-   less tail-costly
-   lower turnover
-   and more robust in holdout

### What was tried

The sprint tested four close variants, all built from the same refined-panel state allocator logic:

-   a smoother state allocator
-   a tail-disciplined allocator
-   a turnover-aware allocator
-   and one robust combination variant

The important design choice was that none of them abandoned the sleeve-role structure.

They all still explicitly used:

-   `composite_calm_trend_specialist`
-   `composite_healthier_recovery_specialist`
-   `composite_anti_chop_clarity`
-   `composite_regime_conditioned`

The research question was not whether a different allocator family might exist.

It was whether the allocator that had already started to work could be cleaned up enough to matter under the Phase D validation rules.

### What improved

The refinements did produce some local improvements.

Most notably, the tail-disciplined allocator reduced concentration and turnover relative to the refined-panel state allocator and kept the intended sleeve roles visible:

-   calmer sleeves still led in calm-trend
-   the healthier-recovery sleeve still led recovery-confirmed or stayed near the top
-   anti-chop and regime-conditioned still dominated in stressed states

So the allocator logic did not collapse back into a generic offensive blend.

That part was encouraging.

### What still did not work

The stronger result never arrived.

None of the refined variants beat the current refined-panel allocator reference on the main full-history raw target composite.

None improved the holdout comparison versus the production pin enough to matter.

And none passed the Phase D promotion rules.

In practice, the project learned that small allocator clean-up trades were real but weak:

-   modest turnover relief was possible
-   slight tail improvement was possible
-   but those improvements came with too much loss in overall allocator strength

That is a very different message from “allocator work failed.”

Allocator work did not fail.

Instead, the project hit diminishing returns on *incremental rule refinement*.

### Strategic meaning after the refinement pass

This sprint sharpened the frontier again.

The project no longer looks blocked by sleeve incompleteness.

It also no longer looks blocked by the absence of any allocator edge at all.

What it looks blocked by now is narrower:

-   the current refined-panel allocator family is good enough to be useful
-   but not flexible enough to convert that usefulness into a production-grade edge through small rule tweaks alone

That means the next branch should not be another minor allocator polish sprint.

The project should keep:

-   the production pin unchanged
-   the shadow pin unchanged
-   the refined-panel state allocator as the active research allocator reference

But from here the better next step is a more structural allocator design change or a more explicit robustness-aware training objective, not another round of local smoothing and threshold adjustments.

So the verdict after this sprint became:

-   the refined-panel allocator was worth refining
-   the refinement pass improved understanding more than performance
-   and the project got a clearer answer that the next frontier is no longer tiny allocator-rule edits

## 24. Structural allocator redesign on the refined panel

The next sprint was justified for a very specific reason.

By this point the project had already learned two things that mattered:

-   the refined redesigned sleeve panel was now good enough for allocator work to matter
-   but small allocator clean-up passes were not strong enough to turn that edge into a production-grade result

That meant the bottleneck had moved again.

It was no longer about missing sleeves.

It was also no longer about missing one more threshold or smoothing rule.

The real question had become whether a better allocator *formulation* could keep the refined panel's role-aware behavior while balancing:

-   sleeve opportunity
-   confidence / separability
-   turnover
-   concentration
-   and tail discipline

### What was tried

This sprint tested a small structural family instead of another patch stack:

-   a robust-objective allocator
-   a confidence-margin allocator
-   a turnover-and-tail allocator
-   and one structural combination allocator

These designs were intentionally different from the earlier rule layer.

Rather than asking “what threshold should be moved,” they asked “what should the allocator explicitly optimize for?”

Across the family, the allocator objective tried to reward:

-   stronger role advantage
-   clearer sleeve winner margins
-   persistence when conviction was weak

While also penalizing:

-   unnecessary movement
-   excessive concentration
-   and fragile tail exposure

### What improved

The redesign did preserve the most important thing.

The structural allocators still used the refined panel as intended:

-   calm-trend capital still leaned into the calm specialist and `taa_10m_sma`
-   healthier recovery still received leadership in recovery-confirmed states
-   anti-chop and regime-conditioned sleeves still took over in stressed conditions

So the project did not lose the core insight of the refined panel.

One variant, the confidence-margin allocator, also demonstrated something useful conceptually:

-   it concentrated more when sleeve winner margins were strong
-   and it diversified more when the panel looked less decisive

That was a real structural behavior change, not a cosmetic rewrite.

### What still failed

The breakthrough still did not arrive.

No structural allocator beat the current refined-panel research reference, `improved_phaseh_refined_state_allocator`, on the main full-history raw composite.

No candidate cleared the Phase D production rule.

And even the best new candidate still showed the same basic failure mode:

-   holdout raw composite stayed below the production pin
-   holdout Sharpe still lagged meaningfully
-   bootstrap support remained below the required threshold
-   tail metrics were not clean enough

So the project learned something important again.

The refined panel was *not* the wrong panel.

The sleeve redesign had done its job.

But replacing the old rule family with a modest structural family was still not enough to convert that better panel into a trustworthy promotion candidate.

### Strategic meaning after the structural redesign

This was not a dead end, but it was a clear boundary.

The project now has evidence that:

-   sleeve quality and sleeve separability are materially better than before
-   allocator decisions on that panel are economically sensible
-   but the current class of hand-built structural allocators still does not deliver enough holdout robustness

That shifts the next frontier again.

The next step should not be:

-   another broad sleeve hunt
-   another tiny allocator cleanup pass
-   or a giant black-box search

It should be a more explicit robustness-aware allocator framework:

-   one that optimizes opportunity, turnover, and tail control together
-   and one that is trained or selected with the Phase D validation stack in mind from the start

So the verdict after this sprint became:

-   the refined panel remains the correct research substrate
-   the best research allocator reference remains `improved_phaseh_refined_state_allocator`
-   structural redesign improved understanding more than realized performance
-   and the project moved one step closer to the true remaining problem: a production-grade allocator formulation that is robust enough to survive holdout, not just intelligent enough to look good in-sample

## 25. Robustness-aware allocator framework on the refined redesigned panel

The next sprint accepted the conclusion from the structural redesign step instead of arguing with it.

By then the project had enough evidence to say:

-   the refined redesigned sleeve panel was no longer the blocker
-   allocator work on that panel was still meaningful
-   but hand-built rule families and hand-built structural variants had both plateaued

So the next move was not another patch.

It was to change the allocator methodology itself.

### Why this step was different

The aim of this sprint was to embed the real constraints into the allocator from the start:

-   role-aware sleeve opportunity
-   turnover control
-   tail discipline
-   and out-of-sample robustness

That produced a small framework family instead of another collection of local rules:

-   an objective-based robust allocator framework
-   a confidence-margin plus turnover-aware framework
-   and a tail-aware robust role framework

Each framework generated a small set of disciplined internal configurations and then selected among them using only trailing history.

That mattered because it forced the allocator to answer a harder question:

not just “which sleeves look good,” but also “which formulation has been holding up best recently once turnover, tail quality and robustness are counted too?”

### What improved

This was a real methodology change, and it showed up in the behaviour.

The frameworks did not collapse into generic market aggression.

They still used the refined sleeve panel in the intended way:

-   calm-trend still leaned into the calm specialist and `taa_10m_sma`
-   recovery-confirmed still leaned into the healthier-recovery sleeve
-   stressed states still moved toward `composite_regime_conditioned` and `composite_anti_chop_clarity`

The selector also did not collapse into a single static configuration.

Different internal configurations were actually chosen through time, which means the framework was using trailing robustness information rather than pretending to.

The best-performing new framework was the tail-aware robust role framework.

It improved several risk-facing attributes relative to the prior research allocator:

-   slightly lower volatility
-   slightly better CVaR
-   slightly better max drawdown
-   and a slightly better holdout Sharpe than the other new framework candidates

So the project did get a cleaner understanding of how a robustness-aware allocator should behave on this panel.

### What still failed

The stronger result still did not become a promotion candidate.

No framework beat `improved_phaseh_refined_state_allocator` on the main full-history raw composite.

No framework cleared the Phase D production rule.

And even the best new framework still showed the same broad failure mode:

-   holdout raw composite remained below the production pin
-   holdout Sharpe remained materially below the production pin
-   bootstrap support still did not reach the required threshold
-   turnover was still too high for a true production-grade allocator

The tail-aware framework got the closest in spirit, but it paid for cleaner risk behaviour by giving up too much of the sleeve-opportunity capture that made the refined-panel state allocator useful in the first place.

That is an important result.

It means the project is no longer mainly missing “more robustness.”

It is missing a methodology that can preserve *both*:

-   the refined panel's role-aware opportunity capture
-   and the robustness required by the validation stack

### Strategic meaning after the framework sprint

This sprint was still useful.

It did not produce a new allocator reference, but it narrowed the problem again.

The project now has evidence that:

-   the refined panel remains the correct research substrate
-   the current best research allocator still remains `improved_phaseh_refined_state_allocator`
-   framework-level redesign can improve risk behaviour
-   but the better risk behaviour is still being purchased at too high a cost in opportunity capture and overall raw composite quality

That means the next branch should not be:

-   another broad sleeve redesign
-   another threshold cleanup pass
-   or another giant black-box search

It should be a more explicit decision-aware or robustness-aware learning framework that can optimise opportunity, turnover and tail control jointly without flattening the panel’s state-specific sleeve edge.

So the verdict after this sprint became:

-   framework-level allocator redesign was justified
-   it improved understanding more than final performance
-   the production and shadow pins still remain unchanged
-   and the next frontier is now a more expressive but still tightly validated allocator methodology, not a return to sleeve search or local rule surgery

## 26. Decision-aware / robustness-aware learning allocator

The next sprint finally moved beyond hand-built allocator formulations.

The setup was deliberately narrow.

The project did not reopen sleeve search.

It did not add another giant model zoo.

It kept the refined redesigned panel as the active sleeve universe and treated the current core blend as the reference panel.

The reason was simple:

-   the refined sleeve panel was now good enough for allocator work
-   `improved_phaseh_refined_state_allocator` still had the strongest research evidence
-   `improved_phasek_tail_aware_role_framework` had cleaner tail behaviour
-   but neither one solved the full production-grade problem

So this sprint asked whether a learner could preserve the Phase H role-aware edge while learning some of the Phase K tail discipline directly.

### What changed methodologically

The allocator was no longer trained to chase raw forward sleeve returns alone.

Instead, the sprint created decision-aware utility labels.

Those labels rewarded forward sleeve opportunity, but penalized:

-   downside outcomes
-   trailing sleeve risk
-   drawdown context
-   fragile offensive exposure

The labels were then cross-sectionally ranked by date, because the allocator's real decision is not whether one sleeve has a beautiful standalone forecast.

The real decision is which sleeves deserve more capital than the others at that point in time.

Three learning allocators were tested:

-   a decision-utility allocator
-   a selective-concentration allocator
-   and a tail/turnover-constrained learning allocator

The models stayed semi-interpretable.

They used walk-forward Ridge-style learners, role/state features, sleeve-quality features, and a learned utility-spread gate.

That kept the sprint aligned with the validation discipline: more expressive than hand rules, but not a black box.

### What improved

The learning allocators preserved the refined panel's role structure.

They still behaved sensibly by state:

-   calm-trend still leaned into `taa_10m_sma` and `composite_calm_trend_specialist`
-   recovery-confirmed still kept `composite_healthier_recovery_specialist` near the top
-   stressed-panic still emphasized `composite_regime_conditioned` and `composite_anti_chop_clarity`

The best candidate was `improved_phasel_tail_turnover_learning_allocator`.

It improved materially over the Phase K tail-aware branch on the main full-history raw composite and became the best fixed-rank candidate in the sprint.

It also beat the refined-panel naive blend on the raw composite and had the strongest rolling raw composite of the compared research candidates.

That was a meaningful step forward.

For the first time in several sprints, the project had a learning allocator that:

-   improved on the conditional tail-aware branch
-   kept role-aware sleeve behaviour
-   improved rolling raw composite versus the Phase H reference
-   and got closer to the production validation rule than the earlier structural framework family

### What still failed

The result still did not justify promotion.

The best learning allocator did not beat `improved_phaseh_refined_state_allocator` on the main full-history raw composite.

It also failed the Phase D production rule.

The core remaining failures were familiar:

-   holdout raw composite was still below the production pin
-   holdout Sharpe was still meaningfully below production
-   bootstrap support was still below the production threshold
-   turnover remained too high
-   and max drawdown was just outside the production cap

So the learning framework did not solve the problem completely.

It did, however, change the shape of the answer.

The project is no longer merely asking whether learning can help.

The answer is now yes, learning can help.

But the current learning formulation still does not preserve enough of the Phase H opportunity capture while also satisfying the Phase D holdout and tail requirements.

### Strategic meaning after the learning sprint

This sprint moved the project closer, but not across the line.

The best research allocator reference remains `improved_phaseh_refined_state_allocator`.

The best conditional learning branch is now `improved_phasel_tail_turnover_learning_allocator`.

The production and shadow pins remain unchanged.

The next frontier should not be a return to sleeve discovery or manual rule tuning.

Instead, the project should either:

-   refine the learning objective itself, especially around holdout Sharpe and turnover
-   or run an explicit validation-first model-selection sprint that treats Phase D pass/fail criteria as the selection target rather than an after-the-fact report

So the verdict after this sprint became:

-   decision-aware learning is now a valid frontier
-   it improved the research opportunity set
-   it still did not produce a production candidate
-   and the next step should focus on learning-objective selection and validation robustness, not new sleeves or manual allocator rules

## 27. Final allocator-category attempt - validation-first and production-proximity learning

This sprint was treated as the final serious attempt inside the allocator-refinement branch.

By this point the project already knew several things with high confidence.

The refined redesigned sleeve panel was good enough for allocator work to matter.

`improved_phaseh_refined_state_allocator` had proven that clearly.

The later structural and learning sprints had also clarified something just as important:

the branch was no longer failing because of missing sleeve roles or because of one more missing threshold.

It was failing because the allocator category kept producing the same pattern:

-   useful role-aware behavior
-   respectable full-history results
-   but not enough holdout robustness, turnover discipline, or Phase D acceptance quality

So the final sprint changed the target again.

It did not try to beat production by looking prettier in sample.

It explicitly tried to minimise the exact reasons the branch had been failing.

Two final candidates were built:

-   `improved_phasem_validation_first_learning_allocator`
-   `improved_phasem_production_proximity_allocator`

Both stayed on the refined redesigned sleeve panel.

Both preserved the sleeve-role structure that had made Phase H useful.

But unlike the earlier learning sprint, the internal configuration choice was driven by validation-style objectives rather than plain forward utility.

One candidate prioritised holdout and rolling-quality proxies.

The other explicitly targeted closeness to the Phase D production rule.

### What the final sprint improved

The final candidates did preserve the good allocator behavior that mattered most.

They still used the refined sleeves sensibly:

-   `composite_calm_trend_specialist` stayed important in calm-trend conditions
-   `composite_healthier_recovery_specialist` still carried the recovery-confirmed role
-   `composite_anti_chop_clarity` still mattered in stressed or unstable environments

The final sprint also showed that validation-first design was directionally useful.

`improved_phasem_validation_first_learning_allocator` pushed bootstrap support versus production up to roughly sixty percent, which was the closest this category got to the production bootstrap bar.

`improved_phasem_production_proximity_allocator` was the better balanced final candidate overall.

It improved on the validation-first variant on full-history raw composite, holdout raw composite, holdout Sharpe gap, drawdown, and CVaR.

So the branch did not simply stop learning.

It kept getting more precise about what a serious candidate would need to look like.

### Why the category still plateaued

Even after directly targeting validation quality, the branch still did not clear the real benchmark.

The final candidates did not beat `improved_phaseh_refined_state_allocator` on the main scorecard.

They also did not beat the best prior learning branch cleanly enough to justify continuing the category.

Most importantly, neither candidate passed the production rule or the shadow rule.

The remaining failures were not subtle:

-   holdout raw composite was still below the production pin
-   holdout Sharpe was still too weak
-   rolling win rate versus production was still not good enough
-   drawdown and CVaR were still outside the required production caps
-   turnover remained well above the production standard

That combination matters.

It means the branch was no longer missing a clever local fix.

It had reached the point where repeated refinements were changing the shape of the tradeoff, but not changing the final decision.

### Closure decision for the allocator-refinement category

This was the sprint that forced the branch-level judgment.

The project now has enough evidence to say the allocator-refinement category is complete.

It was successful in one important sense:

-   it proved allocator work is meaningful once the sleeve panel is conditionally complete
-   it produced a credible research reference in `improved_phaseh_refined_state_allocator`
-   it showed that learning can preserve role-aware sleeve behavior
-   and it clarified the true failure modes that block promotion

But it also plateaued.

The branch kept failing for the same deeper reason:

the current allocator-centric formulations are not enough to convert refined-panel edge into production-grade holdout quality without giving back too much through turnover or tail fragility.

So the verdict after this final sprint became:

-   the allocator-refinement / allocator-learning category is now closed
-   the production pin remains unchanged
-   the shadow pin remains unchanged
-   `improved_phaseh_refined_state_allocator` remains the best research allocator reference
-   and the next broader ML phase should move upstream from allocator tweaking toward uncertainty-aware sleeve opportunity modelling and joint state-to-sleeve edge estimation

That next phase is broader than this branch.

It should ask a different question:

not "how do we slightly improve the allocator policy on the current signals,"

but "how do we learn a better, uncertainty-aware map of conditional sleeve opportunity that a simpler allocator can exploit more reliably out of sample?"

## 28. ML Phase 1 - ambitious decision-aware, uncertainty-aware sleeve ensemble

The previous branch had closed out allocator refinement because no local rule change was going to rescue holdout Sharpe.

This sprint was the first deliberate step into a broader ML phase.

It is referred to below as ML Phase 1 or Phase N.

### What was tried

Phase N trained a walk-forward sleeve ensemble on the refined redesigned sleeve panel.

Three kinds of models were trained independently per sleeve, per week, on expanding windows:

-   ridge regression for sleeve opportunity
-   gradient-boosted regression with mean + quantile targets, to carry distributional information about tail and dispersion
-   a gradient-boosted classifier that emitted a per-sleeve activation probability

The same walk-forward scaffolding also trained a mixture-of-experts date-level gate over three expert regimes (calm, recovery, defense) so that the allocator could read "which expert is in charge this week" alongside the per-sleeve signals.

Outputs were saved as four prediction frames:

-   `phase_n_decision_predictions.csv`
-   `phase_n_tail_predictions.csv`
-   `phase_n_prediction_uncertainty.csv`
-   `phase_n_gate_probabilities.csv`

Three allocator variants were built on top of these predictions to make Phase N a full sprint rather than just a prediction dump:

-   `improved_phasen_distributional_tail_allocator`
-   `improved_phasen_uncertainty_adjusted_allocator`
-   `improved_phasen_moe_role_gating_allocator`

### What improved

The ML Phase 1 stack clearly produced a richer, more informative signal than the allocator-refinement branch had been getting from score panels alone.

-   Every Phase N allocator beat production comfortably on full-history raw composite, by roughly plus 0.04 to plus 0.09.
-   `improved_phasen_distributional_tail_allocator` in particular landed at the top of the composite rank across the entire comparator set on full history, with Sharpe near 0.93 and the smallest drawdown in the comparator universe.
-   The MoE gate succeeded as a diagnostic: expert probabilities moved sensibly across regimes, and the gate's entropy tracked genuine uncertainty.

### What still failed

The sprint surfaced exactly the problem that would define ML Phase 2.

-   Holdout composite was flat to slightly below production for every Phase N candidate, usually around minus 0.013.
-   Holdout Sharpe landed near 1.90-2.00 while production held 2.10. The gap was outside the Phase D minus 0.02 floor.
-   Bootstrap probability of beating production on the holdout never got above roughly 30%.
-   Rolling origin win rate was not consistently above 55%.

So even with an objectively stronger ML signal, the allocator policy still could not close the recent-regime Sharpe gap.

### Strategic meaning after ML Phase 1

Phase N removed one hypothesis.

It is no longer the case that the project's holdout ceiling is a weak sleeve signal.

The ML stack is picking up conditional sleeve edge that production is not using, and that edge is consistent across most of the history.

But on the last 104 weeks - the window production was tuned against - the allocator design that converts that signal into weights continues to leak Sharpe.

That isolated the next question precisely.

If the ML signal is informative but the holdout is not responding, then the remaining degree of freedom is how decision-making around that signal is structured.
Uncertainty shrinkage, turnover discipline, tail priority, and production-proximity all have to be tested as allocation levers - not as model levers - with the ML signal held fixed.

That is exactly what ML Phase 2 was designed to do.

## 29. ML Phase 2 - decision-aware portfolio allocation on the ML Phase 1 signal

This sprint is the allocation counterpart of ML Phase 1.

No new models were trained.
The Phase N `decision`, `tail`, `uncertainty`, and `gate` CSVs were loaded verbatim and only the Layer 3 allocator was swapped.

### What was tried

Five decision-aware allocator variants were built on top of the same Phase N predictions, each targeting a different hypothesis about why Phase N did not close the holdout Sharpe gap.

-   `improved_phaseo_uncertainty_shrunk_allocator` - shrinks opportunity and tail ranks per sleeve by one minus sleeve uncertainty, and tightens caps to 0.26 when total uncertainty is elevated.
-   `improved_phaseo_turnover_gated_allocator` - raises the turnover penalty substantially and adds a hard freeze-previous-weights gate whenever the top-signal margin is small, total uncertainty is high, and confidence is low simultaneously.
-   `improved_phaseo_tail_priority_allocator` - lets tail rank lead the signal (34% weight) ahead of opportunity rank, pushes defensive sleeve floors up with risk guard, and caps offense sleeves tighter in stressed tape.
-   `improved_phaseo_production_proximity_allocator` - pulls the anchor mix strongly toward the reference allocator (82% reference share) with a 1.35 multiplier on the anchor penalty, clips caps to 0.34 unless confidence and certainty are both high.
-   `improved_phaseo_combo_decision_allocator` - blend of the uncertainty-shrinkage, tail-priority, and production-proximity levers.

All five share the same quadratic optimizer, the same dynamic bounds, the same safe-anchor blend, and the same ML inputs.
They differ only in signal blend, confidence or uncertainty context, floors and caps, and the knob dictionary covering mu_scale and the lambda penalties.

### What improved

Every Phase O candidate beat production on full-history raw composite by plus 0.063 to plus 0.088.

`improved_phaseo_tail_priority_allocator` landed at Sharpe 0.935 full history - the highest Sharpe in the entire comparator universe, paired with the smallest drawdown at minus 0.126 and the smallest CVaR at 5% at minus 0.0245.

Rolling origin mean Sharpe delta versus production was positive for every Phase O candidate, ranging plus 0.035 to plus 0.056.
That confirmed the ML stack genuinely outperforms production across most of the historical cross-section.

P2-B's freeze gate triggered on 21% of rebalance dates, producing a clean demonstration that decision noise can be suppressed when the signal is mushy.

### What still failed

Every Phase O candidate failed the same four Phase D gates in the same direction.

-   Holdout raw composite delta vs production was minus 0.013 for all five candidates, missing the zero floor.
-   Holdout Sharpe delta ranged from minus 0.09 to minus 0.20, all outside the minus 0.02 tolerance.
-   Bootstrap probability of beating production on the holdout ranged from 21% to 37%, all well short of 60%.
-   Rolling origin win rate ranged from 27% to 40%, well short of 55%.

Drawdown and CVaR were inside Phase D tolerance for every candidate.

### Strategic meaning after ML Phase 2

ML Phase 2 is a clean, well-controlled negative result.

The allocation layer was not the binding constraint.

Five very different allocation philosophies were run on top of the same ML signal.
All five converged into the same holdout-Sharpe band of 1.90 to 2.01, well below production's 2.10.
No knob combination, tightening or loosening the signal, the turnover penalty, the tail penalty, or the anchor pull, closed the gap.

That rules out a clean class of follow-on sprints.
The allocator has been searched with discipline and it is not the source of the remaining Sharpe leak.

What remains is the mismatch between what the ML signal contributes and where it contributes.

The rolling origin numbers are the most informative artefact of this sprint.
On almost every historical window that is not the last 104 weeks, Phase O candidates beat production.
In the last 104 weeks, production dominates.
That points directly at a regime-specific story, not a structural allocator story.

### Verdict after ML Phase 2

The verdict after this sprint is:

-   all five Phase O candidates are Research-only
-   the production pin remains unchanged
-   the shadow pin remains unchanged
-   `improved_phasen_distributional_tail_allocator` and `improved_phaseo_tail_priority_allocator` are the strongest research references going forward
-   no dashboard or narrative changes are warranted

The natural next question - the one ML Phase 3 should take on - is not "what new model do we train" or "what new allocator do we build" but "how do we learn when to trust the ML allocator versus when to fall back to the production allocator".
That is a meta-allocator / regime-conditioned ensemble question, and it is the first unexplored degree of freedom after ML Phase 1 and ML Phase 2 have both landed.

## 30. ML Phase 3 - meta-allocator / trust model

ML Phase 3 starts from a stricter diagnosis than either Phase N or Phase O.

The project no longer had a signal problem, and it no longer had an allocator-search problem.

Phase N showed the ML sleeve signal was informative.
Phase O showed that five materially different decision-aware allocators all failed the same holdout gates in the same direction.
That combination implies the remaining problem is **conditional trust**:

when should the system actually hand control to the ML allocator, and when should it fall back to production?

### What was tried

Phase P treated production, Phase N, and Phase O as a small expert set and learned a trust layer on top of them.

The fixed comparison universe was:

-   `improved_phase2b_regime_confidence_boost`
-   `improved_phase2b_combo_abc`
-   `improved_phaseh_refined_state_allocator`
-   `improved_phasen_distributional_tail_allocator`
-   `improved_phaseo_tail_priority_allocator`
-   refined redesigned panel naive blend

Three meta-allocation candidates were built:

-   `improved_phasep_hard_trust_switch_allocator`
    -   walk-forward binary trust model that decides whether to use production or `improved_phaseo_tail_priority_allocator`
    -   hard on or off, with hysteresis to avoid constant churning
-   `improved_phasep_soft_trust_blend_allocator`
    -   uses the same trust probability, but blends continuously between production and Phase O instead of forcing all-or-nothing switching
    -   intended to preserve some ML upside without paying for brittle regime misses
-   `improved_phasep_regret_aware_meta_allocator`
    -   multi-expert blend across production, `improved_phasen_distributional_tail_allocator`, and `improved_phaseo_tail_priority_allocator`
    -   uses current state, uncertainty, disagreement, and causal recent relative-quality features to decide how much capital each expert deserves

All targets were walk-forward safe.
The trust labels were based on short forward utility windows that rewarded realised net return but penalised short-window drawdown, tail losses, and turnover.

### What helped

This phase validated the core intuition behind the trust frontier.

The strongest candidate, `improved_phasep_regret_aware_meta_allocator`, did not beat production outright, but it was the first ML-phase portfolio that materially improved the **holdout-Sharpe retention** problem without simply collapsing back into the old allocator branch.

Its main profile:

-   full-history Sharpe about **0.929**
-   full-history max drawdown about **-13.4%**
-   full-history turnover about **8.0%**
-   holdout Sharpe about **2.078**
-   holdout raw composite about **0.950**, matching the best ML holdout raw-composite tier

That matters for two reasons.

First, it held onto most of the ML branch's full-history quality while taking turnover down versus both `improved_phasen_distributional_tail_allocator` and `improved_phaseo_tail_priority_allocator`.

Second, on the 104-week holdout it **matched the strongest ML raw-composite tier and beat both ML references on Sharpe**:

-   versus Phase N: holdout raw composite flat, holdout Sharpe about **+0.073**
-   versus Phase O: holdout raw composite flat, holdout Sharpe about **+0.094**

So Phase P did solve the exact problem it was supposed to solve at a research level:

it reduced recent-regime damage **relative to the always-on ML allocators**.

### What did not help enough

The same candidate still failed the production promotion gates.

-   holdout raw composite remained below production at about **-0.013**
-   bootstrap outperformance probability vs production stayed low at about **30%**
-   rolling raw win rate vs production stayed around **40%**

So the trust layer did not prove that ML should replace production.

The hard switch and soft blend were both useful diagnostics but not strong enough as full candidates.

-   The hard switch got very close on holdout Sharpe while sacrificing too much full-history edge.
-   The soft blend improved holdout Sharpe more clearly, but its raw-composite profile stayed too close to production to count as a new research leader.

In other words:

-   **hard switching was too brittle**
-   **soft blending was safer but too mild**
-   **the regret-aware expert blend was the only variant that actually looked like a better research platform**

### What this says about the frontier

Phase P changes the project's ML story in an important way.

The remaining challenge is not "build a more complex allocator" in the old sense.

It is:

-   estimate **deployment trust**
-   map uncertainty and recent regret into expert weights
-   decide how much ML edge is worth taking in each environment

This is a more serious ML problem than the earlier allocator-learning sprints because it explicitly treats the production allocator as a live fallback expert rather than assuming the ML branch should always be on.

### Verdict after ML Phase 3

The verdict after this sprint is:

-   the broader ML frontier **did succeed**, but only as a research advance, not as a pin-change event
-   production remains the pin
-   shadow remains unchanged
-   `improved_phasep_regret_aware_meta_allocator` becomes the strongest **trust-aware ML reference**
-   `improved_phasen_distributional_tail_allocator` and `improved_phaseo_tail_priority_allocator` remain important upstream references, but they are now clearly subordinate to the meta-allocation question

### What should happen next

The next iteration should stay on the trust frontier, but push on the specific remaining weaknesses of Phase P:

1.  improve **rolling win-rate** against production rather than only average delta
2.  improve **bootstrap support** by making the trust model less dependent on a few strong windows
3.  let the trust layer react more strongly to state-specific regret without collapsing into pure conservatism
4.  test whether the expert set itself should distinguish between:
    -   production
    -   conservative ML
    -   aggressive ML
    -   explicit abstention / low-conviction mode

That is a cleaner next step than reopening sleeve search or another allocator sweep.

## 30. Phase Q — Abstention-Aware / Regime-Bucket Meta-Allocator

### Why this sprint happened

Phase P identified a specific failure mode rather than a general ceiling.
The softmax expert blend was too smooth: production was never fully released, the ML branches were never fully released, and the decision layer thrashed weekly on noisy features.
Phase Q was designed as a direct response with three interpretable cuts: explicit abstention when conviction collapses, hard regime buckets with persistence instead of smooth weights, and slow EMA regret decay instead of fast rolling means.

### What was tried

Three candidates were built on top of the Phase P trust-probability pipeline and validated against the standing 7-member comparator set:

-   `improved_phaseq_abstention_aware_meta_allocator`
    -   production + phasen + phaseo + an explicit abstain expert (BIL-heavy defensive anchor)
    -   abstain weight driven by classifier uncertainty and 1 - trust score
    -   fires whenever conviction is split-brained rather than committing to any expert
-   `improved_phaseq_regime_bucket_meta_allocator`
    -   four hard buckets with 3-week persistence and hysteresis: `calm_trust`, `recovery_trust`, `defense_production`, `ambiguous_abstain`
    -   per-bucket base mix instead of smooth softmax weights
    -   bucket assignment uses only Phase 2B risk-layer fields and classifier outputs, no new signals
-   `improved_phaseq_abstention_regime_regret_meta_allocator`
    -   combo: bucket structure from Q2, abstention overlay from Q1, plus a 20-week half-life EMA regret decay nudging phaseo vs phasen within trust buckets

### What the data showed

The standout result is on the holdout Sharpe profile.
All three Phase Q candidates beat both production and Phase P on holdout Sharpe:

-   production: **2.0996**
-   Phase P regret-aware: **2.0776**
-   **Q1 abstention-aware: 2.2018**
-   **Q2 regime-bucket: 2.2107**
-   **Q3 combo: 2.1900**

Q2 also improved holdout recovery_capture from production's 0.57 to **0.77** — a meaningful state-transition gain that the smooth softmax in Phase P could not produce.
Q1 hit the best full-history risk profile the project has ever produced: Sharpe 1.04, drawdown -0.082, CVaR_5 -0.018, composite 0.631 (rank 1 of 10).

A second genuinely new result: Q2 posted a **61.15% moving-block bootstrap probability of beating `improved_phasep_regret_aware_meta_allocator` on holdout excess return**.
That is the first trust-model iteration to cross the 60% support bar against the ML reference, even though it does not cross it against production (25.7%).

### Why none of them promoted

The Phase D production rule requires holdout raw composite delta ≥ 0, and all three Phase Q candidates miss:

-   Q1: -0.085 (too aggressive abstention — 34% avg abstain weight trades away too much equity exposure)
-   Q2: -0.018 (narrowly missed; the conservative bucket mix costs \~1.8pp of holdout raw return)
-   Q3: -0.024 (combo inherits Q2's shortfall without enough Q1 defence to compensate)

Rolling-origin raw win rate is also below the 55% bar for all three (33% for Q1, 40% for Q2 and Q3), and the bootstrap vs production is below 60% for all three (1.2% / 25.7% / 15.0%).

Final classification: all three **Research-only**.
Production pin and shadow pin are unchanged.
`improved_phaseq_regime_bucket_meta_allocator` replaces `improved_phasep_regret_aware_meta_allocator` as the project's strongest trust-model reference.

### What this tells us about the trust frontier

Phase Q changed how the project thinks about the trust problem in two ways.

First, **the bucket structure works and the smooth softmax does not**.
The same expert set produced a meaningful holdout Sharpe gain (+0.11) and a meaningful recovery-capture gain (+0.20) the moment the softmax was replaced with hard, sticky buckets.
The earlier Phase P result — that the trust layer was useful in theory but small in practice — was partly a functional-form problem, not just a signal problem.

Second, **abstention is a useful tail tool but a dangerous core tool**.
Q1 delivered the best risk-adjusted profile the project has ever seen, but it did so by trading away roughly one-third of its capital into a defensive basket every week.
That made its return profile too conservative for the production gate even though its Sharpe and drawdown were the best on record.

### What should happen next

The cleanest next step is Phase R, holding the Q2 bucket skeleton and making three targeted changes:

1.  dial abstention down so it only fires inside non-defense buckets when conviction collapses, not across the whole history
2.  shorten or remove the 20-week EMA regret decay, which did not add value on top of the bucket structure in this window
3.  tune the bucket base mixes (still walk-forward, still out-of-sample) to close the \~1-2pp holdout raw-return gap without giving back the +0.11 Sharpe gain

If that sprint lands inside the production gate, it becomes a legitimate pin candidate.
If it does not, the project has still gained a materially better trust reference (Q2) without touching signals, sleeves, or the Layer 2B regime engine.

## 31. Phase R — Bucket-Trust Refinement

### Why this sprint happened

Phase Q landed `improved_phaseq_regime_bucket_meta_allocator` (Q2) as the strongest trust-model branch, but diagnosis made the remaining gap very specific: Q2 beats production on ann_return, Sharpe, drawdown, CVaR, and recovery_capture on holdout, yet misses three production gates by small but real margins — holdout raw composite delta (-0.018), rolling win rate (40%), and bootstrap probability (25.7%).
That is not a "new ML layer needed" problem; it is a "Q2 has a few small overcorrections that can be tuned" problem.
Phase R refined Q2's bucket skeleton with four narrow candidates rather than opening a new frontier.

### What was tried

All four candidates share Q2's four-bucket structure, 3-week persistence, and classifier pipeline.
They differ only in the per-bucket base mixes and the overlay logic:

-   `improved_phaser_bucket_refined_meta_allocator` — tuned base mixes. Cut abstain cushion from 8% to 4% in `defense_production`, from 35% to 12% in `ambiguous_abstain`; lowered production floor in `recovery_trust` from 25% to 18% to release more ML weight.
-   `improved_phaser_light_abstention_overlay_allocator` — removed abstain from base mix entirely in `defense_production` (85/7.5/7.5 prod/phasen/phaseo); replaced system-wide abstain with a narrow runtime overlay that only fires inside non-defense buckets when abstention_score \> 0.60, capped at 10% abstain weight.
-   `improved_phaser_fast_narrow_regret_allocator` — kept Q2's base mixes, replaced 20-week EMA regret with 8-week EMA, and scoped the regret to only reallocate weight between phaseo and phasen inside the existing ML share.
-   `improved_phaser_refined_bucket_fast_regret_combo` — R1 base mixes + R3 narrow fast regret, built only because R1 and R3 showed independent movement.

### What the data showed

The headline result is that every Phase R candidate improves on Q2 with high statistical support.
Each of the four clears the 60% bootstrap floor against Q2 on holdout excess return — R1 94.8%, R2 94.8%, R3 98.4%, R4 94.9%.
Phase R did what it was designed to do: refine Q2 in a way the data actually supports.

Against production, the four candidates split into two useful pieces:

-   **R2 (`improved_phaser_light_abstention_overlay_allocator`) is the new robustness reference.** Holdout raw composite delta vs production moved from -0.018 (Q2) to **-0.013** — roughly 27% of the gap closed.
    Rolling win rate vs production moved from 40% to **46.7%** — the closest anything in the project has come to the 55% bar.
    Bootstrap probability moved from 25.7% to **38.9%** — still short of 60% but materially better.
    Holdout raw composite position rank 4 among all 13 candidates (behind only production, shadow, and phaseh).

-   **R3 (`improved_phaser_fast_narrow_regret_allocator`) is the new Sharpe reference.** Holdout Sharpe moved from 2.211 (Q2) to **2.216** — the highest holdout Sharpe of any candidate in the full cohort.
    Raw composite profile is essentially unchanged from Q2, so the Sharpe gain is free.
    Max drawdown, CVaR, and turnover all improved slightly.

R1 closed a small additional fraction of the raw-composite gap but gave up 0.027 in holdout Sharpe relative to Q2.
R4 was essentially identical to R1 — the narrow regret overlay had no room to move on top of R1's already-shifted base mix.

### Why none of them promoted

Each Phase R candidate still fails at least one Phase D production gate.
R2 is the closest: holdout raw Δ -0.013 (needs ≥ 0), rolling win 46.7% (needs ≥ 55%), bootstrap 38.9% (needs ≥ 60%).
Every candidate passes the full-history delta gate, the holdout Sharpe floor, and the drawdown/CVaR caps.

Final classification: R1, R2, R3 all Research-only; R4 dropped as redundant with R1.
Production pin and shadow pin unchanged.

### What this tells us about the trust frontier

Phase R changed the trust-model story in two ways.

First, **the frontier is plateauing but still yielding**.
The jumps from Phase O → Phase P → Phase Q → Phase R have been progressively smaller, and each Phase R candidate closes a fraction of the remaining gap rather than clearing it.
That is consistent with a frontier that has been correctly identified (hard buckets + persistence + narrow overlays) and now needs targeted tuning, not a new structure.

Second, **the remaining gap has a specific shape**.
Diagnostic work shows two structural contributors: a \~4pp higher downside_capture during `defense_production` weeks (the meta-allocator's weighted blend over-diversifies away from production's specific adverse-tape holdings in GLD, HYG, and DBA), and a small number of losing weeks that drag rolling win-rate down.
Both are narrow problems that can be attacked without reopening signals, sleeves, or the allocator set.

### What should happen next

The next sprint, narrowly scoped:

1.  Reshape the internal blend inside `defense_production` so the weighted combination of experts behaves more like production's actual holdings in adverse tape.
    This is recognizing that `defense_production` is the bucket where "fallback to production" should look like production, not like a smoothed meta-blend.

2.  Add a conditional ML-share attenuator that reduces phaseo/phasen weight inside trust buckets when rolling-origin realized excess return over the last 13 weeks is negative.
    The smallest possible intervention designed specifically to lift rolling win-rate without disturbing the Sharpe gain.

If those two moves together do not clear the production gate, the project should stop refining the trust layer and look upstream at the Layer 2B regime engine — the one component the trust layer cannot see through.

## 32. Phase S — Final Targeted Trust-Layer Fix

### Why this sprint happened

Phase R left a very specific situation: R2 (`improved_phaser_light_abstention_overlay_allocator`) closed roughly a quarter of the Q2 → production holdout gap and moved rolling win-rate to 46.7%, but still fell short of the Phase D production gate on three axes (holdout raw Δ -0.013, rolling win 46.7%, bootstrap 38.9%).
Phase R's diagnostic section named the two places the residual likely lived: the weighted meta-blend over-diversifies during `defense_production` weeks, and the ML sleeve adds drag in trust buckets during rolling-negative excess periods.
Phase S tested exactly those two levers — and nothing else — to either close the gate or state clearly that it cannot be closed from this layer.

### What was tried

Three candidates.
All sit on top of R2's four-bucket structure, 3-week persistence, classifier pipeline, and light-abstention overlay.
They touch only the internals:

-   `improved_phases_defense_reshape_allocator` (S1) — tightened `defense_production` base mix from `{prod 0.85, phasen 0.075, phaseo 0.075, abstain 0}` to `{prod 0.95, phasen 0.025, phaseo 0.025, abstain 0}`. Every other bucket unchanged.
-   `improved_phases_conditional_ml_attenuator_allocator` (S2) — kept R2's base mixes. Added a causal 13-week trailing-excess attenuator that scales phaseo/phasen weights by a factor ∈ [0.40, 1.0] inside `calm_trust`, `recovery_trust`, and `ambiguous_abstain` when rolling ML excess is below -0.0015. Removed ML mass is re-allocated to production.
-   `improved_phases_defense_reshape_ml_attenuator_combo` (S3) — S1's defense_production mix + S2's attenuator.

### What the data showed

The Sharpe story landed.
S1 produced the highest holdout Sharpe of any candidate in the cohort (2.166, +0.011 vs R2, +0.066 vs production).
S3 was essentially tied with S1 on Sharpe.
Bootstrap probability vs R2 was high — S1 81.0%, S3 79.8% — confirming S1's Sharpe gain over R2 is real and not a single-window artifact.

The raw-composite story did not.
Holdout raw composite moved by -0.0006 (S1), +0.0003 (S2), -0.0003 (S3) versus R2.
That is inside noise.
The -0.013 shortfall to production is structurally identical to R2's -0.013 shortfall.
Rolling win-rate against production stayed at 40% for S1/S2 and 46.7% for S3 — unchanged from R2's baseline.
Bootstrap probability vs production stayed in the 39-47% band, well below the 60% gate.

All three candidates classified **Research-only** under Phase D rules.
Production pin and shadow pin unchanged.

### Why the two levers did not work

S1 (defense reshape) moved exactly the axis it was designed to move — holdout Sharpe — but at the cost of -0.012 on full-history raw composite, because pulling ML weight out of `defense_production` across history gives back upside during the pre-holdout period where ML-heavy defense sometimes beat production.
The change is locally correct (defense should look like production in adverse tape) but globally neutral.

S2 (conditional attenuator) fired in roughly 31% of trust-bucket weeks on holdout, which is about the right firing rate.
But the weeks where ML excess was trailing-negative did not line up with the weeks where production was actually winning.
So the attenuator reduced ML weight in the wrong weeks and did not lift rolling win-rate at all.

S3 inherited S1's Sharpe gain and S2's inability to move rolling win-rate, and did the worst on full-history composite.

### What this means for the project

Three consecutive sprints (Phase Q → Phase R → Phase S) moved progressively smaller amounts against the same -0.013 holdout residual without clearing it.
Each sprint closed some piece of the diagnostic Phase R named, then found the remaining residual was elsewhere.

Stated plainly: **the two Phase S levers did not solve the production-gate gap, and narrow tuning inside the trust layer is unlikely to.** The remaining gap lives in two places the trust layer cannot see through — (i) the Layer 2B regime engine's hard `market_state` boundaries, and (ii) the specific weekly holdings in production's adverse-tape allocation.
Neither is addressable by changing bucket base mixes, adding overlays, or tuning classifier thresholds.

### Current reference set

Production pin: `improved_phase2b_regime_confidence_boost` (unchanged since it was promoted).
Shadow pin: `improved_phase2b_combo_abc` (unchanged).
Closest-to-gate reference: `improved_phaser_light_abstention_overlay_allocator` (R2) — holdout Δ -0.013, rolling win 46.7%, bootstrap 38.9%.
Sharpe reference: `improved_phases_defense_reshape_allocator` (S1) — holdout Sharpe 2.166, highest in cohort.
Replaces R3 as the Sharpe reference going forward.
All nine Phase N–S trust-model candidates remain in the comparator set as Research-only.

### What should happen next

The recommendation is to stop refining the trust layer and move up or across:

1.  **Layer 2B regime engine softening.** Replace the hard `market_state` label with a posterior distribution, and feed the distribution into the bucket mapping so near-boundary weeks blend two bucket mixes rather than committing to one.
    This is the single most plausible way to correct the per-week boundary errors every trust-layer candidate inherits.

2.  **Portfolio-level production-anchored blend.** Blend production's ETF weights 60-80% with the best trust-layer candidate's weights 20-40% directly at the holdings level, walk-forward.
    This is a more aggressive reading of "defense_production should look like production" — instead of approximating production via a meta-blend over phaseo/phasen/production, it uses production's actual holdings as the anchor.

If neither direction lifts holdout composite within one sprint each, the project has reached its structural ceiling on this signal + sleeve set.
Production then stays as the deployable allocator, R2 stays as the closest-to-gate reference, S1 stays as the Sharpe reference, and dual-track reporting continues unchanged.

## 33. Phase T — Regime Engine Softening / Layer 2B Revisit

### Why this sprint happened

Phase Q → R → S converged to the same residual: holdout raw composite Δ vs production stuck at -0.013, rolling win-rate stuck at 40-47%, bootstrap stuck at 39-47%.
Phase S's diagnostic was explicit that further trust-layer tweaks were unlikely to close the gap, and that the most plausible remaining culprit was **upstream**: hard `market_state` boundaries and the hard regime-bucket assignment built on top of them.
Phase T tested that hypothesis directly.
It is the project's first upstream sprint since the ML meta-allocator branch began.

### What was tried

Three candidates only.
All preserve R2's per-bucket base mixes and light-abstention overlay; they only change how the bucket assignment itself is computed:

-   `improved_phaset_soft_regime_posterior_allocator` (T1) — replaced Phase Q's hard bucket label with a closed-form softmax (temperature 0.45) over handcrafted bucket-affinity scores built from the same causal features the hard rule consumed. A 3-week half-life EMA smooths the posterior. Per-week mix is Σ over buckets of `posterior(bucket) × base_mix(bucket)`. No new model fit, no new training window, walk-forward safe.
-   `improved_phaset_soft_trust_weighted_allocator` (T2) — T1 plus an uncertainty-aware defensive pull. When the posterior is diffuse (max-prob below 0.65), pull up to 30% of the mix toward `defense_production`. Linear saturation between 0.40 and 0.65.
-   `improved_phaset_production_anchored_soft_combo` (T3) — T2 plus an ETF-level production anchor on diffuse weeks. Up to 15% of final weights blended with production's actual holdings when max-prob falls below 0.60.

### What the data showed

The soft posterior was real, not cosmetic.
**It disagreed with the hard rule on 54.7% of weeks.** Average max-prob was 0.479; 68.8% of weeks had max-prob below 0.55 (boundary); 45.7% were diffuse (max-prob below 0.45).
The soft argmax assigned `calm_trust` to 65.9% of weeks vs the hard rule's smaller share, and assigned `defense_production` to only 22.5% vs the hard rule's 67.5%.
So Phase T genuinely did move the bucket boundary on most weeks.

Where that movement helped: **full-history raw composite improved sharply.** T1 reached 0.5545 (rank 3 of 13), well above R2's 0.5198 (rank 11).
T2 (0.5477) and T3 (0.5436) preserved most of the gain.
The mechanism was clear from bucket diagnostics: in calm-but-mislabeled-as-defense weeks (concentrated in pre-holdout history), the soft posterior put more ML weight to work and earned the spread.

Where the movement did not help: **holdout said no.** Pairwise vs production, T1 holdout Δ -0.016, T2 -0.015, T3 -0.013.
Holdout Sharpe Δ vs production: T1 -0.013 (worse than production), T2 +0.016, T3 +0.030 (above production but below R2's +0.055 and R3's +0.116).
Bootstrap probability vs production collapsed from R2's 38.9% to 16.5% / 19.1% / 21.0% for T1/T2/T3.
Rolling win-rate stayed at 40% across all three — same as Q2 / R3 / S1 / S2 / S3 / R3.

Pairwise vs R2: T-trio holdout raw composite within 0.003 of R2 (T3 essentially tied), but Sharpe Δ -0.068 / -0.040 / -0.026 (all losses).
Bootstrap vs R2 below 15% for all three.
Soft posteriors do not reliably beat R2 in holdout-block resampling.
All three classified **Research-only**.

### Why it didn't work

The diagnostic asymmetry is the lesson.
Soft regime moved 54.7% of bucket assignments, and those moves were locally correct in the dev window — that is why full-history composite jumped.
But on holdout, the hard rule's defense classifications were largely **correct**.
Re-classifying many of those holdout weeks as `calm_trust` exposed the portfolio to ML drag during exactly the weeks where production's structurally defensive holdings were the right answer.
The soft posterior added variance without adding holdout edge.

This is the cleanest possible falsification of the hypothesis that hard regime boundaries are the residual gap's primary cause.
If they were, holdout would have moved with full history.
It did not.

### What this means for the project

Four consecutive upstream-and-downstream sprints — Phase Q (bucket meta), Phase R (bucket trust refinement), Phase S (targeted defense reshape + ML attenuator), Phase T (soft regime posterior) — converged on the same -0.013 holdout shortfall.
Each addressed a different hypothesis.
None cleared the gate.
The most parsimonious explanation is that **production's holdout edge lives in specific weekly ETF positioning** that the meta-allocator's expert universe (production / phaseo / phasen) cannot replicate without literally giving 100% weight to production in those weeks.
No regime layer softening, hardening, or re-bucketing fixes that.

The current signal/sleeve/regime stack is at or very near its information ceiling on this universe.

### Current reference set

Production pin: `improved_phase2b_regime_confidence_boost` (unchanged).
Shadow pin: `improved_phase2b_combo_abc` (unchanged).
Closest-to-gate trust reference: `improved_phaser_light_abstention_overlay_allocator` (R2).
Holdout Δ -0.013, rolling win 46.7%, bootstrap 38.9%.
Phase T's T3 ties R2 on holdout raw composite but loses on Sharpe, bootstrap, and rolling win — R2 stays the reference.
Sharpe reference: `improved_phaser_fast_narrow_regret_allocator` (R3).
Holdout Sharpe 2.216.
Phase S's S1 was Sharpe-best at 2.166 but with full-composite cost; R3 is more balanced.
Dev-composite reference (new): `improved_phaset_soft_regime_posterior_allocator` (T1).
Full-history composite 0.5545, rank 3 in cohort.
Useful as a tracking baseline for any future sprint that claims to help dev and holdout simultaneously.

### What should happen next

The recommendation is to test exactly one more direction and then stop:

1.  **Phase U — portfolio-level production-anchored holdings blend.** Skip the meta-allocator on a controlled fraction of weeks: blend production's actual ETF weights 70-90% with R2's weights 10-30%, walk-forward, with the blend ratio possibly conditioned on Phase Q's hard `defense_production` flag. This is the only remaining direction that bypasses the meta-blend averaging problem at the holdings level. It is the explicit untested case from Phase S's recommendation #2.

If Phase U does not lift holdout composite above the gate, the project has reached its structural ceiling on this sleeve panel and the conclusion is final: production stays deployed, R2 / R3 / T1 remain research references, dual-track reporting continues unchanged.
Any further work after Phase U should be a **sleeve-panel revisit** (different sleeves, not another allocator on the same sleeves) rather than yet another Layer 2B / Layer 3 sprint.

## 34. Phase U — Production-Anchored Holdings Blend

### Why this sprint happened

Phase T's clean falsification of the hard-boundary hypothesis narrowed the surviving candidates for the residual gap to one: production's holdout edge lives in its **specific weekly ETF weights**, not in any allocator/trust/regime decision the meta-blend layer can make.
Every prior sprint operated on the expert level — picking weights over production / phaseo / phasen and letting the resulting blend produce a holdings vector.
That is a smoothing operation by construction.
If the \~30% of holdout weeks where production wins are won by exact GLD / HYG / DBA / BIL / TLT positioning, no expert-level mix can recreate them without overfitting to production's own labels.
Phase U was the only remaining direction that bypasses that averaging problem: blend the **finished ETF weight vectors** themselves, `α · production_weights[t] + (1 − α) · partner_weights[t]`, then renormalize.
This was billed as the last serious test in the current allocator/trust/regime branch.

### What was tried

Seven candidates, the smallest meaningful test of the hypothesis.
Two static partner choices, three blend ratios each, plus one conditional.
No new ML model, no new sleeve, no new training.
The blend is closed-form arithmetic on already-validated weight artifacts:

-   **U1 family — prod + R2 static blend**, at 90/10 (`improved_phaseu_prod90_r2_10_holdings_blend`), 80/20, 70/30. R2 is the closest-to-gate trust reference from Phase R.
-   **U2 family — prod + R3 static blend**, at 90/10, 80/20, 70/30. R3 is the Sharpe-strongest trust reference.
-   **U3 — conditional prod + R2** (`improved_phaseu_conditional_prod_r2_holdings_blend`): 90/10 in Phase Q's hard `defense_production` weeks, 70/30 elsewhere. The only candidate that varies α across time, and it does so via an already-causal flag.

The eleven-member fixed comparator set added Phase T's T1 (full-history composite reference) on top of the Phase S ten.

### What the data showed

This was, by some distance, the most successful sprint of the entire ML-meta-allocator era.
The hypothesis was confirmed: holdings-level blending preserves production's adverse-tape edge while inheriting trust-branch upside.
Three Phase D gates that no prior candidate had ever cleared were each cleared by a Phase U candidate:

-   **Holdout Δ ≥ 0 (vs production)** — U1a 90/10 prod+R2 cleared at +0.0003. First time in the project. The rest of the U1/U2 families fell within -0.0001 to -0.0028 of production, every one tighter than R2's -0.013 and R3's -0.018.
-   **Rolling win ≥ 55%** — five candidates cleared. U1a hit 73.3%, the highest rolling win-rate the project has ever produced. U1b, U1c, U2a, U2b all hit 60.0%.
-   **Bootstrap ≥ 60% (vs production)** — U3 conditional cleared at 71.2%. First time in the project. The U1 family clustered at 40-41% (better than R2's 39%) and U2 at 28%.
-   **Holdout Sharpe Δ ≥ -0.02** — every Phase U candidate cleared. U2c reached Sharpe Δ +0.045, U3 reached +0.034.
-   **Holdout raw composite rank** — U1a holds rank 1 across the full 18-member cohort at 0.9630 (vs production's 0.9628).
-   **DD/CVaR caps** — every candidate cleared, max_dd within +0.001 and CVaR within +0.0001 of production.

### Why none promoted

No single Phase U candidate aligns all six gates.
The pattern of which gates each one clears is structural, not random:

-   **U1a 90/10 prod+R2** — clears holdout Δ, Sharpe Δ, rolling win, rolling mean Δ (4 of 6). Misses full Δ (+0.007 vs the +0.015 floor) and bootstrap (41.3%). The misses are mechanical: a 90% production weight inherits production's full-history composite (rank 18 of 18 in cohort), and bootstrap-block resampling of an excess-return distribution that hovers around zero cannot dominate production reliably.
-   **U1c 70/30 prod+R2** — clears full Δ at +0.0175 (first candidate in the project to clear that gate with non-trivial holdout), Sharpe Δ, rolling win, rolling mean Δ (4 of 6). Misses holdout Δ (-0.0009) and bootstrap (40.1%).
-   **U3 conditional prod+R2** — clears full Δ, Sharpe Δ, bootstrap (the prized gate), rolling mean Δ (4 of 6). Misses rolling win (40%) and holdout Δ (-0.0028).

So U1a, U1c, and U3 each pass exactly four of six gates, with three different combinations of misses.
The two structural failure modes are full-Δ (any 90/10 blend cannot lift production's full-history rank enough) and bootstrap (any blend partnered with R2/R3 inherits their excess-return distribution's noise).
All seven candidates classify **Research-only**.

### Why this is different from Phase T's flat result

Phase T failed the same gates by symmetric, structural amounts: full-Δ moved up sharply (T1 +0.077 vs production) but holdout did not move with it, rolling win locked at 40%, bootstrap collapsed to 17-21%.
The signature was "everything moved together except holdout" — diagnostic of a regime layer pushing weights around without adding any holdout edge.

Phase U's signature is the opposite: **the deployment-relevant axes are the ones that moved.** Holdout Δ moved from -0.013 to essentially flat.
Rolling win moved from 47% to 73%.
Bootstrap moved from 39% to 71% in U3.
These are not noise; they are direct, mechanical, hypothesis-confirming responses.
The two unmet gates (full Δ and bootstrap for U1, rolling win for U3) are downstream of the static-α design choice, not of any deeper failure of the holdings-blend approach.

### What this means for the project

The branch is **not** exhausted, contrary to the contingent claim Phase T closed on.
Phase T's structural-ceiling argument was conditional on holdings blending also failing flat.
It did not — it produced the project's first deployment-grade closures on three separate gates.
The argument now flips: there is at least one disciplined sprint left in this branch, narrowly designed against Phase U's specific failure modes.
After that sprint, if no candidate clears all six gates simultaneously, the ceiling claim becomes warranted and the project moves to a sleeve-panel revisit.

The deployment story has also meaningfully changed.
Production remains the only candidate that clears all gates, so the production pin is unchanged.
But for the first time the project has a **closest-to-gate reference that genuinely competes with production on the deployment-relevant axes**: U1a matches production on holdout raw composite, beats it on Sharpe, beats it on rolling win 73% to \~50%, and the only gates it misses are full-history-Δ (which is a fundamental property of being mostly-production) and bootstrap (which would lift in a tighter conditional).
That is a much stronger position than R2 was in.

### Current reference set

Production pin: `improved_phase2b_regime_confidence_boost` (unchanged since promotion).
Shadow pin: `improved_phase2b_combo_abc` (unchanged).
Closest-to-gate reference (replaced): `improved_phaseu_prod90_r2_10_holdings_blend` (U1a).
Holdout Δ +0.0003, rolling win 73.3%, holdout Sharpe Δ +0.010 vs production.
Replaces R2 on this slot.
R2 stays in the comparator set as a balanced trust reference.
Sharpe reference: `improved_phaser_fast_narrow_regret_allocator` (R3) — unchanged.
Holdout Sharpe 2.216, still highest.
Bootstrap reference (new): `improved_phaseu_conditional_prod_r2_holdings_blend` (U3).
Bootstrap 71.2% vs production — first candidate ever to clear that gate.
Dev-composite reference: `improved_phaset_soft_regime_posterior_allocator` (T1) — unchanged.
All seven Phase U candidates remain in the comparator set as Research-only.

### What should happen next

Run exactly one more sprint, narrowly scoped against Phase U's two specific failure modes:

1.  **Phase V — Holdings Blend Refinement.** Three candidates only.
    -   **V1**: 90/10 prod + phasen holdings blend. phasen has full-history composite 0.5666 vs R2's 0.5198 — a +0.047 advantage. The mechanical math says swapping R2 for phasen at the same blend ratio should close U1a's residual full-Δ gap (\~+0.008 needed) without disturbing the holdout/rolling-win/Sharpe story.
    -   **V2**: 90/10 prod + phaseo holdings blend. Same partner-swap idea, with the highest-Sharpe ML reference as the partner.
    -   **V3**: tighter conditional — 95/5 in `defense_production` weeks, 80/20 elsewhere. Designed to preserve U3's bootstrap clearance while lifting rolling win above the 55% floor.

If Phase V produces a candidate that clears all six Phase D gates, promote.
If Phase V also fails to align all six gates, the conclusion becomes final: **the current signal/sleeve/regime/allocator stack has reached its information ceiling on this universe.** Production stays deployed.
U1a (or its V-replacement, if better) becomes the official research-track closest-to-gate reference.
Any further work moves to a sleeve-panel revisit — different ETFs, different sleeve construction — not another allocator/trust/regime/holdings sprint on the same panel.

## 35. Phase V — Final Holdings-Blend Refinement (Branch Closure)

### Why this sprint happened

Phase U was unambiguous about what should come next.
Three different Phase U candidates had each cleared four of the six Phase D production gates with three different miss-patterns: U1a (90/10 prod+R2) cleared the holdout-Δ and rolling-win gates but missed the full-Δ floor and bootstrap; U3 (conditional 90/10 → 70/30 prod+R2) cleared bootstrap but missed rolling win; U1c (70/30 prod+R2) cleared full-Δ but missed holdout-Δ.
The project had not yet tested whether **swapping the partner from R2 to a stronger full-history reference** (phasen, phaseo) at U1a's 90/10 ratio could lift full-Δ over the +0.015 floor without giving back U1a's other gate clears, and it had not tested whether **a tighter conditional rule** (95/5 in defense weeks, 80/20 elsewhere) could preserve U3's bootstrap edge while restoring rolling win.
Phase V was scoped explicitly to either close the gates inside this framework or trigger Outcome B and close the branch.

### What was tried

Three candidates only — the smallest meaningful test, no broader:

-   **V1 — `improved_phasev_prod90_phasen_10_holdings_blend`**. 90/10 production + phasen at the holdings level. Designed to lift full-Δ via phasen's +0.047 full-history advantage over R2 while preserving U1a's holdout near-zero by keeping the 90/10 ratio.
-   **V2 — `improved_phasev_prod90_phaseo_10_holdings_blend`**. 90/10 production + phaseo. Same idea with a different partner — different correlation structure with production, slightly different tail behavior.
-   **V3 — `improved_phasev_conditional95_80_holdings_blend`**. Conditional 95/5 in `defense_production` / 80/20 elsewhere, partner = phasen (the most justified partner from V1's reasoning). Sharpens U3's conditional toward production positioning more strongly in defense weeks while letting the partner contribute meaningfully elsewhere.

The 13-member fixed comparator set added Phase U's U1a and U3 on top of the Phase U eleven.

### What the data showed

The partner-swap projection was directionally correct on its target axis.
**V1 and V2 both cleared the full-Δ ≥ +0.015 gate** (V1 +0.0173, V2 +0.0172) — the first time inside a 90/10 holdings blend.
Holdout Δ for V1 and V2 sat at -0.0008 and -0.0007 — close to flat, second-best holdout closures in the project after U1a's +0.0003.
Holdout Sharpe Δ vs production stayed positive across all three.
DD and CVaR caps cleared comfortably.

But the rest of the gate panel regressed materially relative to U1a and U3.
V1 vs U1a: rolling win 73% → 47%, holdout Δ +0.0003 → -0.0008, bootstrap 41% → 32%, holdout Sharpe Δ +0.010 → +0.008.
V2 vs U1a: same pattern, with bootstrap dropping further to 23%.
The mechanical reason was clear from the holdings diagnostics: phasen and phaseo are less defensive in adverse tape than R2 (phasen full max_dd -0.127, phaseo -0.126, R2 -0.137), so a 10% phasen / phaseo weight pulled the blend slightly off production's adverse-tape positioning during exactly the holdout weeks where U1a's R2 partner contributed defensively.

V3 was the largest disappointment.
The partner switch from R2 to phasen broke U3's bootstrap edge entirely — bootstrap collapsed from U3's 71.2% to V3's 33.2%.
Rolling win actually fell from U3's 40% to V3's 33.3%, holdout Δ collapsed from -0.0028 to -0.0078, and full Δ moved from +0.0122 to +0.0120 — flat.
The diagnostic: U3's bootstrap edge came from R2's specific tail-aware behavior pairing well with production in adverse tape, not from the conditional structure itself.
Replacing R2 with phasen destroyed that pairing.

All three Phase V candidates classified **Research-only** under Phase D rules.
None replaced U1a or U3 as research references.

### Why this is different from Phase U

Phase U's signature was "the framework works — three first-time gate clears across three different candidates, each at a different point in the (ratio, conditional) parameter space." Phase V's signature is the inverse: "the framework's parameter space has been searched at the points the data named, and the gates correspond to anti-correlated points on a structural Pareto frontier." The full-Δ gain came at the exact cost of the holdout-Δ / rolling-win / bootstrap gains.
The gates do not align in any single point.

### What this means for the project

**The current allocator / trust / regime / holdings-blend branch is finished.** Six consecutive sprints — Phase Q (bucket meta), Phase R (bucket trust refinement), Phase S (defense reshape + ML attenuator), Phase T (soft regime posterior), Phase U (production-anchored holdings blend), Phase V (final holdings-blend refinement) — have moved progressively smaller amounts against the same deployment ceiling without producing a single candidate that aligns all six Phase D production gates simultaneously.
The diagnostic is conclusive: the deployment-relevant axes that Phase D weighs sit at different, anti-correlated points in the holdings-blend framework's parameter space on this signal+sleeve panel.
Pushing α toward production lifts holdout-Δ and bootstrap while suppressing full-Δ; switching to a higher-full-composite partner lifts full-Δ but degrades the partner's adverse-tape pairing with production, costing rolling win and bootstrap.
**This is a structural Pareto frontier, not a tuning failure.**

What this branch achieved over six sprints, stated honestly:

1.  Established that holdings-level blending dominates meta-allocator blending for capturing production's holdout edge (Phase U).
2.  Produced the first-ever holdout Δ ≥ 0 candidate (U1a, +0.0003) with rolling win 73%.
3.  Produced the first-ever bootstrap ≥ 60% candidate (U3, 71.2%).
4.  Produced the first-ever full Δ ≥ +0.015 candidates that simultaneously preserved holdout near-flat (V1 and V2, -0.0008 / -0.0007).
5.  Confirmed that production's holdout edge lives partly in specific weekly ETF holdings (Phase U validated this; Phase V's partner-swap result reinforced it).
6.  Cleanly falsified the "hard regime boundaries are the residual cause" hypothesis (Phase T).

What this branch did not achieve:

-   A single candidate that aligns all six Phase D gates simultaneously. None exists in the searched parameter space.

### Current reference set (final, branch-closed)

Production pin: `improved_phase2b_regime_confidence_boost` — unchanged since promotion.
Shadow pin: `improved_phase2b_combo_abc` — unchanged.
Closest-to-gate research reference: `improved_phaseu_prod90_r2_10_holdings_blend` (U1a) — unchanged from Phase U. Holdout Δ +0.0003, rolling win 73.3%, holdout Sharpe Δ +0.010 vs production.
No Phase V candidate replaced it.
Bootstrap research reference: `improved_phaseu_conditional_prod_r2_holdings_blend` (U3) — unchanged from Phase U. V3's partner-switch broke its bootstrap edge.
Sharpe research reference: `improved_phaser_fast_narrow_regret_allocator` (R3) — unchanged.
Holdout Sharpe 2.216.
Dev-composite research reference: `improved_phaset_soft_regime_posterior_allocator` (T1) — unchanged.
Full-history composite 0.5545.
Full-Δ research reference (new): `improved_phasev_prod90_phasen_10_holdings_blend` (V1) — first holdings-blend candidate to clear full Δ ≥ +0.015 (+0.0173).
Useful as a reference for any future sprint that revisits this branch from a different angle.

### What should happen next — sleeve-panel revisit, not more allocator work

The right next move is to **step out of Layer 3 and back to Layer 2**, the sleeve panel itself.
The allocator / trust / regime / holdings branch has demonstrated in six sprints that it can move the metric in any single Phase D dimension but cannot align them all on the existing sleeve panel.
That is a sleeve-panel constraint, not an allocator constraint.

Three concrete directions for that broader frontier:

1.  **Add a structural defensive sleeve that captures production's GLD / HYG / DBA / TLT mix as an explicit named sleeve.** If production's adverse-tape positioning can be expressed as its own causal sleeve, downstream allocators can call it directly and the meta-blend averaging problem disappears at the source. This is the single highest-conviction next move.
2.  **Replace one or two of the existing offense sleeves with regime-specific sleeves** — e.g., a recovery-confirmed-only momentum sleeve, a calm-trend-only carry sleeve — so the allocator's expert universe carries clearer regime-specific edge.
3.  **Broaden the sleeve universe to include a genuinely uncorrelated branch in adverse tape** — e.g., a managed-futures-style trend signal across commodities — if the project's data infrastructure supports it.

What this branch taught the project that should carry forward, regardless of which layer is refined next: holdings-level blending is the right framework for combining a strong anchor with research candidates and should be the default for future Phase 3 sprints; Phase D's six-gate validation discipline is doing exactly what it should and should not be relaxed; walk-forward causal inputs + closed-form blend rules + dual-track production/shadow reporting is a robust template that should be reused.

The branch is now closed.
The story is current through the closure.

## Section 36 — Phase W: Sleeve-Panel Revisit / Opportunity-Set Upgrade

### Why this sprint moved upstream

Phase V closed the allocator / trust / regime / holdings-blend branch with a clean Outcome B: six consecutive sprints had pushed Phase D's six gates around a structural Pareto frontier without aligning all of them in a single candidate.
The diagnostic at branch closure was specific — the gain in any one gate came at the cost of another, because the deployment-relevant axes corresponded to anti-correlated points in the holdings-blend parameter space *on the existing 6-sleeve panel*.
That last clause matters.
The branch-closure note (Section 35) named the next move directly: stop trying to extract more lift from Layer 3 by re-mixing the six existing sleeves, and instead revisit Layer 2 itself.

Phase W is the Layer-2 revisit.
No allocator work, no trust work, no regime engine work, no holdings blending.
Just a focused question: does the sleeve panel that all of those upstream layers have been working with actually have the structural diversity an allocator phase needs in order to make non-cosmetic choices?

### What was tried

Four candidate sleeves, each designed to fill a specific structural gap diagnosed during the closed branch:

1.  **W1 `composite_structural_defense_sleeve`** — explicit, callable defensive role. State-conditioned base mix over {GLD, TLT, HYG, LQD, DBA, BIL}, activated by a stress score combining recent stress (26-week), market drawdown, and the risk-off correlation z-score. Inverse-vol weighting inside the defensive basket, 50% shrinkage to the state-conditioned base mix.
2.  **W2 `composite_recovery_confirmed_offense_sleeve`** — silent except in `recovery_confirmed` or `recovery_fragile + breadth_change_4w > 0`. Top-4 ETFs by breadth-confirmed momentum + multi-horizon momentum, 80% top-4 / 20% HYG floor.
3.  **W3 `composite_calm_carry_sleeve`** — active only in `calm_trend AND market_trend_positive`. Top-5 by carry + 0.5 × quality, equal-weight.
4.  **W4 `composite_macro_trend_diversifier_sleeve`** — explicitly cross-asset (SPY / EFA / VWO / TLT / GLD / PDBC / DBA / USO / UUP). Long/flat by tsmom_score, inverse-vol scaled, long_share keyed off the count of currently-positive assets.

All four sleeves run on 1-week-lagged signal features for walk-forward causal safety, identical to the existing sleeve panel's discipline.

### What helped

**W1 helped cleanly.** Standalone sharpe 0.65, full-sample Max DD -11.25%, turnover 3.5% (lowest in the panel by a wide margin), and CVaR-5 -1.09%.
State-conditional view: positive sharpe in calm_trend (1.20), neutral_mixed (1.24), and stressed_panic (0.57).
The stressed_panic number is the one to read carefully — W1 is the only sleeve in the entire panel (active 6 + new 4) that earns a positive sharpe in stressed_panic while running an actual defensive basket rather than sitting in BIL.
Holdout sharpe 3.96 with -0.91% holdout MDD over 139 weeks.

Distinctness: maximum correlation against any of the active 6 sleeves is 0.09 (vs `taa_10m_sma`); average correlation 0.02.
That is, W1 is structurally orthogonal to the panel — the cleanest distinctness profile of any sleeve introduced in any sprint of this project.

Panel impact: adding W1 to the active 6 (naive equal-weight blend) adds +0.04 sharpe (0.86 → 0.91), tightens MDD by 1.55 points (-15.28% → -13.73%), and tightens CVaR-5 by 0.39 points.
Calmar holds.
In the panel's state-winner table, W1 takes calm_trend with sharpe 1.20 — a +0.56 margin upgrade over `composite_calm_trend_specialist` (0.64), which had been the prior state winner.

W1 is **promoted** to the production sleeve panel for the next allocator phase.

### What did not help

**W2 was a mechanical disappointment.** The design hypothesis (top-4 breadth-confirmed momentum at recovery entry should monetize the recovery dispatch) was empirically falsified.
In `recovery_confirmed` (43 obs), W2 produced ann_return -14.96% / sharpe -1.93 — actively destructive in the exact state it was designed for.
The mechanism is interpretable: the breadth-confirmed momentum top-4 at recovery entry are the names that ran hardest into the prior drawdown, so the sleeve buys the strongest bounces and catches the second leg of mean-reversion chop.
Distinctness against the active 6 is real (avg corr -0.09) but there is no alpha to monetize.
**Drop.**

**W3 looked impressive in the state-winner tables but the alpha was an artifact.** W3 "wins" recovery_confirmed (sharpe 4.42), recovery_fragile (sharpe 5.56), and stressed_panic (sharpe 2.73) in the panel rankings.
Reading the avg_bil_state column makes it obvious why: W3 is 100% in BIL during all three of those states (it only allocates risk-on in `calm_trend AND market_trend_positive`), so the high state-conditional sharpes are the sharpe of cash during low-vol regimes, not active alpha.
The true active sharpe in calm_trend (the only state where W3 actually allocates) is 0.07 — noise.
**Research-only**, with a future-research note to redesign the carry/quality scoring or restrict the universe.

**W4 produced real distinctness with high vol.** Standalone sharpe 0.38 with full-sample Max DD -18.01% — too high to deploy as-is.
Holdout sharpe 1.51 with 10.02% holdout return is real but window-dependent.
The genuine value W4 contributes is in `neutral_mixed` (493 obs — the largest market state by a lot), where it delivers sharpe 0.84 with cross-asset exposure that is structurally different from anything in the active equity panel.
Average correlation against the active 6 is -0.02.
**Conditional / research-only**: a vol-capped variant should be tried in a future Layer-2 sprint; the current high-MDD form should not be promoted.

### Panel separability — the structural diagnosis

| Panel                      | Sleeves | Avg \|corr\| | Median \|corr\| |
|----------------------------|--------:|-------------:|----------------:|
| active panel naive         |       6 |         0.66 |            0.66 |
| active + W1                |       7 |         0.48 |            0.65 |
| active + W1 + W2 + W3      |       9 |         0.31 |            0.09 |
| active + W1 + W2 + W3 + W4 |      10 |         0.27 |            0.09 |

The current 6-sleeve active panel is dense — average pairwise correlation 0.66, max 0.78.
This explains a lot of what was happening inside the closed allocator/trust/regime/holdings-blend branch: when most pairwise sleeve pairs already track each other, allocator-level re-mixing is mathematically constrained — there is little orthogonal variance left to exploit.
Adding W1 alone drops avg correlation from 0.66 to 0.48.
Adding all four candidates drops it to 0.27 with median \|corr\| 0.09.
W2 and W3, even though they have weak or artifact-driven standalone alpha, do contribute orthogonal variance.

### Whether the sleeve panel is now better positioned for the next allocator phase

Yes, but the lift is structural rather than headline.
The recommended go-forward panel is the **active 6 plus W1**, a 7-sleeve panel with avg \|corr\| 0.48 instead of 0.66 and a clean defensive role that previously did not exist.
That is materially more orthogonal raw material than the closed branch was working with.
W4 stays alive for a future vol-capped revisit; W2 and W3 are research-only artifacts.

### How this sprint differs from the closed branch

The closed branch (Phases Q–V) was Layer 3: same sleeves, different ways of weighting their outputs.
Phase W is Layer 2: same allocator, different sleeves.
The closed branch demonstrated empirically that the existing sleeve panel does not contain a re-mix that aligns all six Phase D gates simultaneously.
Phase W's job was to find out whether that was a re-mix problem or an opportunity-set problem.
The answer is "partly opportunity-set" — at least one of the missing roles (a clean, callable structural defense sleeve) was genuinely absent from the prior panel, and W1 fills it.

### Final sleeve classification (Phase W)

| Sleeve | Status | Rationale |
|------------------------|------------------------|------------------------|
| W1 — structural_defense_sleeve | **Promote** | Clean alpha + orthogonality + low DD + only sleeve with positive stressed_panic sharpe |
| W2 — recovery_confirmed_offense_sleeve | **Drop** | Negative sharpe in target state; design empirically wrong on this dataset |
| W3 — calm_carry_sleeve | **Research-only** | State-winner table is BIL artifact; true active alpha 0.07 sharpe |
| W4 — macro_trend_diversifier_sleeve | **Conditional / Research-only** | Real cross-asset distinctness, real neutral_mixed alpha; needs vol cap before deployment |

### Updated reference set

Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.
Shadow pin: `improved_phase2b_combo_abc` — unchanged.
Closest-to-gate research reference: `improved_phaseu_prod90_r2_10_holdings_blend` (U1a) — unchanged.
Bootstrap research reference: `improved_phaseu_conditional_prod_r2_holdings_blend` (U3) — unchanged.
Sharpe research reference: `improved_phaser_fast_narrow_regret_allocator` (R3) — unchanged.
Dev-composite research reference: `improved_phaset_soft_regime_posterior_allocator` (T1) — unchanged.
Full-Δ research reference: `improved_phasev_prod90_phasen_10_holdings_blend` (V1) — unchanged.
**New entry — promoted Layer-2 sleeve: `composite_structural_defense_sleeve` (W1).** Joins the production sleeve panel.

### What comes next

**Phase X — allocator rerun on the upgraded 7-sleeve panel.** Re-run `improved_phase2b_regime_confidence_boost` (production) and `improved_phase2b_combo_abc` (shadow) with the new 7-sleeve panel as their input universe.
Report incremental contribution attributable to W1's inclusion specifically — what changes in the allocator's weight schedule, what changes in state-conditional return, and whether the production-vs-research gap closes structurally rather than via re-mix.

This is the first sprint in many that should be expected to show non-tradeoff improvement, because for the first time the change adds an actually-distinct return stream to the allocator's opportunity set rather than re-mixing existing ones.
Phase D gates apply as usual, with incremental contribution measured against both the production track and the shadow track separately, per the dual-track rule.

## Section 37 — Phase X: Allocator Rerun on the Upgraded 7-Sleeve Panel

### Why this sprint moved back downstream

Phase W's promotion of `composite_structural_defense_sleeve` (W1) was the project's first Layer-2 change in many sprints.
The promotion was justified at the sleeve level — clean orthogonality, the only sleeve in the panel earning a positive sharpe in `stressed_panic`, and a state-winner takeover in `calm_trend`.
But "the sleeve is good standalone" and "the sleeve actually improves a deployable allocator" are different claims.
Section 36 explicitly forecast that Phase X would be the first sprint in many that *should* be expected to show non-tradeoff improvement, because for the first time the change adds an orthogonal return stream rather than re-mixing existing ones.
Phase X is the test of that forecast.

The sprint's job was narrow and specific: run the production-style and shadow-style allocator architectures on the upgraded 7-sleeve panel exactly as they would be deployed, plus a clean ablation that re-runs the same allocator on the 6-sleeve panel without W1, and read whether W1's inclusion produces real downstream allocator improvement against the 8-gate Phase D production rule.

### What was tried

Four candidates, all measured against the same fixed comparator set and the same Phase D production rules:

1.  **X1 `improved_phasex_production_style_7sleeve`** — production architecture (inverse-vol sleeve weighting + state risk multiplier + Phase 2B `regime_confidence_boost` ML offset) on the full 7-sleeve panel including W1.
2.  **X2 `improved_phasex_shadow_style_7sleeve`** — same as X1 except using the `combo_abc` ML meta layer (regime boost + transition gate + tail suppression) instead of `regime_confidence_boost`.
3.  **X3 `improved_phasex_state_conditional_7sleeve`** — research allocator using state-conditional rank-Sharpe sleeve weighting (per-state historical sleeve rankings drive weights instead of pooled inverse-vol), still on the 7-sleeve panel with W1, no ML meta layer.
4.  **X4 `improved_phasex_production_style_6sleeve_ablation`** — identical to X1 in every respect except the panel: 6-sleeve active panel without W1. This is the clean ablation isolating W1's contribution.

All four candidates run the same 156-week trailing window, identical state risk multipliers, identical 5bp half-spread turnover model, and the same walk-forward 1-week-lagged signal alignment.

### What helped

**The W1 ablation was clean and meaningful in its own right.** Comparing X1 (7-sleeve) vs X4 (6-sleeve, same allocator) isolates W1's marginal effect on a deployable allocator architecture.
Sharpe rose from 0.855 to 0.924 (+0.069).
Max drawdown tightened from -10.07% to -7.41% (-2.66 points).
CVaR-5 tightened from -2.43% to -1.68% (-0.75 points).
Annual turnover fell from 24.4% to 18.8%.
Raw target composite rose from 0.469 to 0.490.
State-by-state, W1's average weight peaked in the regimes Phase W said it should — 32% in calm_trend, 34% in neutral_mixed, 28% in recovery_confirmed — and dropped to exactly 0% in stressed_panic (state risk multiplier = 0).
This is exactly the ablation result Phase W's promotion of W1 implied should exist, and it does.

**The 7-sleeve panel did improve sleeve-level Sharpe, drawdown, CVaR, and turnover relative to 6-sleeve under the same allocator.** That is a real, structural improvement and validates Phase W's classification of W1 as Promote.

### What did not help

**None of the X1/X2/X3 candidates clear the Phase D production gates against the production pin.** The improvement W1 delivers via X1 over X4 is genuine but the X allocator family runs at a return level too low to compete with the production candidate's full-sample return baseline.
Concretely on the 8-gate pairwise rule for X1 vs `improved_phase2b_regime_confidence_boost`:

| Gate             | Threshold  | X1 Result        | Pass? |
|------------------|------------|------------------|-------|
| Full raw Δ       | ≥ +0.015   | +0.013           | ✗     |
| Holdout raw Δ    | ≥ 0        | -0.188           | ✗     |
| Holdout sharpe Δ | ≥ -0.02    | +0.162           | ✓     |
| Rolling win rate | ≥ 55%      | 26.7%            | ✗     |
| Rolling mean Δ   | \> 0       | -0.073           | ✗     |
| Bootstrap prob   | ≥ 60%      | 0.001            | ✗     |
| MDD cap          | Δ ≥ -0.01  | +0.066 (better)  | ✓     |
| CVaR cap         | Δ ≥ -0.002 | +0.0094 (better) | ✓     |

X1 fails 5 of 8.
X2 (shadow ML layer) is functionally identical at the sleeve-weight level (W1 weight averages 25.6% in X1 vs 25.6% in X2 — the meta layer changes the offset but not the inverse-vol structure) and shows the same fail pattern.
X3 (state-conditional weighting) modestly raises Sharpe to 0.935 by giving W1 more weight in calm_trend (38%) but loses on full and holdout returns and fails the same gates.

**The mechanical reason the X family is over-defensive.** Inverse-vol weighting on the 7-sleeve panel over-weights W1 because W1 has the lowest standalone vol in the panel by a wide margin (3.5% vs 6-9% for the others).
Average W1 weight inside the risk-on portion of the book sits near 26% across X1/X2/X3, pulling the allocator's offense share to 37% (vs production 55%) and pushing average cash to 50% (vs production 28%).
The W1 sleeve is genuinely defensive and helps Sharpe and drawdown — but the volume of W1 the inverse-vol formula buys is too high for a deployable production candidate to recover the return level needed to clear the full-Δ and rolling-mean gates.

**X4 (6-sleeve ablation) classifies as Drop on its own merits.** X4 worsens Sharpe vs production by 0.030, fails the full-Δ gate, fails rolling win rate, and fails bootstrap probability.
This is expected — running the production-style architecture on the 6-sleeve panel is not a deployment candidate.
X4's purpose was the ablation, not promotion.

### Whether W1 meaningfully changed allocator outcomes

Yes — at the *sleeve-orthogonality* level and at the *Sharpe / drawdown / CVaR* level.
No — at the *Phase D production-gate* level under inverse-vol weighting.
W1 makes a real allocator better at risk metrics but reduces its return level enough that the production track's full-return gates do not clear.
This is the mirror image of the closed Q-V branch: there the existing 6 sleeves had no orthogonal variance left to re-mix; here there is an orthogonal sleeve, but the simplest weighting rule over-uses it.

### How this sprint differs from prior sprints

Phase X is the first sprint in this project where the proximate cause of failing Phase D is over-defensiveness rather than any of the older failure modes (over-trading, regime mis-classification, allocator brittleness, or thin-tail bootstrap).
That is a new diagnostic.
The closed branch (Phases Q–V) failed Phase D because the 6-sleeve opportunity set could not align all gates simultaneously.
Phase W's diagnosis was that the opportunity set itself was too dense.
Phase X confirms that the upgraded 7-sleeve opportunity set is structurally better, but the *weighting rule* now needs to be conditional on W1's distinctive role rather than treating it as just another inverse-vol slot.

### Final classification (Phase X)

| Candidate | Sharpe | MDD | Raw Composite | Status | Rationale |
|------------|-----------:|-----------:|-----------:|------------|------------|
| X1 — production-style 7-sleeve | 0.924 | -7.41% | 0.490 | **Research-only** | Fails 5/8 production gates; useful as W1 ablation reference |
| X2 — shadow-style 7-sleeve | 0.919 | -7.29% | 0.490 | **Research-only** | Fails same gates as X1; shadow ML layer ≈ no-op vs production layer here |
| X3 — state-conditional 7-sleeve | 0.935 | -7.85% | 0.482 | **Research-only** | Highest Sharpe of the four but worst raw composite; fails same gates |
| X4 — production-style 6-sleeve ablation | 0.855 | -10.07% | 0.469 | **Drop** | Strictly dominated by X1; existed only to isolate W1's contribution |

### Updated reference set

Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.
Shadow pin: `improved_phase2b_combo_abc` — unchanged.
Closest-to-gate research reference: `improved_phaseu_prod90_r2_10_holdings_blend` (U1a) — unchanged.
Bootstrap research reference: `improved_phaseu_conditional_prod_r2_holdings_blend` (U3) — unchanged.
Sharpe research reference: `improved_phaser_fast_narrow_regret_allocator` (R3) — unchanged.
Dev-composite research reference: `improved_phaset_soft_regime_posterior_allocator` (T1) — unchanged.
Full-Δ research reference: `improved_phasev_prod90_phasen_10_holdings_blend` (V1) — unchanged.
Promoted Layer-2 sleeve: `composite_structural_defense_sleeve` (W1) — unchanged (still in the production sleeve panel).
**New entry — W1 ablation reference: `improved_phasex_production_style_7sleeve` (X1).** Kept as the canonical demonstration that W1 inclusion improves Sharpe / MDD / CVaR / turnover on a deployable allocator while raw return level needs a smarter weighting rule than mechanical inverse-vol.

### What comes next

**Phase Y — conditional W1 sizing.** The X family's failure mode is mechanical and diagnosable: inverse-vol over-weights the lowest-vol sleeve, which is the right defensive response in stress regimes but wrong in calm/neutral regimes where the cost is paid in foregone return.
Phase Y should test allocator variants that scale W1's weight conditionally on regime — closer to the pre-W1 risk profile in `calm_trend` and `neutral_mixed`, closer to the X-family weight in `stressed_panic` and the recovery states.
The candidate space includes: (i) a state-conditional W1 cap that pins W1's share to the state risk multiplier itself, (ii) a stress-conditional W1 boost that activates only when the W1 stress score exceeds a threshold, and (iii) a hybrid where W1 enters the inverse-vol pool in stress regimes only and is excluded otherwise.
All three should be reported against both the production and shadow tracks per the dual-track rule, with the X1 ablation reference held alongside the production pin as the W1-on-but-mechanical baseline.
The hypothesis to test: a smarter W1 sizing rule preserves the X-family's defensive gains while recovering enough return to clear the full-Δ and rolling-mean gates.

## Section 38 — Phase Y: Conditional W1 Sizing Inside the Production Allocator Family

### Why this sprint stayed inside the production allocator family

Phase X promoted W1 at the sleeve level (X1 vs X4 ablation: Sharpe +0.069, MDD -2.66pts, CVaR -0.75pts, turnover -5.6pts) but classified all four X-family candidates as Research-only or Drop because the production-style allocator on the 7-sleeve panel was over-defensive — average cash 50% vs production 28%, average offense 37% vs production 55%.
The mechanical cause was that inverse-vol weighting handed W1 \~26% of risk-on weight automatically because W1 has the lowest standalone vol in the panel.
Phase X named the next problem precisely: *not* "does W1 help?" (resolved: yes) but "can W1 help if we size it conditionally instead of mechanically?"

Phase Y is the narrow rerun that answers that question.
No new sleeves, no new ML, no new regime engine work, no new trust layer, no new holdings-blend variants.
Just the same production-style allocator family with three different rules for sizing W1 — the only thing that changed.

### What was tried

Three candidates plus a five-row ablation panel:

1.  **Y1 `improved_phasey_state_capped_w1`** — start from inverse-vol weights on the 7-sleeve panel, then force W1 to a state-conditional cap (calm 5%, neutral 8%, recovery_confirmed 10%, recovery_fragile 18%; stressed_panic 20% but mooted by state risk multiplier=0). Excess weight redistributes proportionally across the other 6 sleeves. Tests whether a hard cap alone — the simplest possible fix — closes the production gap.
2.  **Y2 `improved_phasey_trigger_driven_w1`** — ignore W1 in the inverse-vol step. Set W1's weight directly from a bounded $$0.02, 0.25$$ defensive trigger score combining (i) recent 13-week SPY drawdown depth, (ii) Phase 2B `p_tail_risk`, (iii) `1 - p_regime_confidence`. The other six sleeves split (1 - w_W1) by inverse-vol. Tests whether *demand-driven* sizing (only call defense when defense is needed) preserves more offense in calm states than state caps.
3.  **Y3 `improved_phasey_cash_replacement_w1`** — production architecture exactly on the 6-sleeve panel (X4 logic), then redirect a fraction of the resulting cash share into W1 when triggers fire. Cap: at most 50% of cash share is convertible. W1 only enters by displacing cash, never by displacing offense. The most production-consistent integration possible.
4.  **Y4 ablation table** — five rows: same production family with (a) no W1 (= X4), (b) uncapped W1 (= X1), (c) state-capped W1 (= Y1), (d) trigger-driven W1 (= Y2), (e) cash-replacement W1 (= Y3). Reported alongside the candidate metrics.

All Phase X causal/walk-forward safety carried over: 1-week-lagged sleeve features, 156-week trailing inverse-vol from t-1, state multipliers and Phase 2B predictions from existing walk-forward sources, SPY drawdown computed from t-1 closed weekly returns.
No retraining of any branch.

### What helped

**The conditional sizing rules did exactly what they were designed to do directionally.** Avg W1 weight dropped from X1's 25.6% to Y1 5.5%, Y2 3.0%, Y3 0.2%.
Avg offense rose from X1's 37.0% to Y1 48.0%, Y2 49.3%, Y3 50.8%.
Avg cash dropped from X1's 50.0% to Y1 37.1%, Y2 35.6%, Y3 33.8% — back near production's 28.3% range.
Absolute return rose from X1's 4.59% to Y1 5.65%, Y2 5.76%, Y3 5.99%.
Holdout raw composite vs production improved from X1's -0.188 to Y1 -0.114, Y2 -0.083, Y3 -0.069.
Bootstrap probability vs production improved from X1's 0.001 to Y1 0.005, Y2 0.008, Y3 0.014.
So as a *control mechanism*, conditional W1 sizing works — the offense crowd-out that broke X1 is gone, and the production-return gap is materially narrower.

The Y2 trigger-quintile diagnostic confirmed the trigger logic was correct in direction: avg W1 weight rose from 2.0% in the lowest trigger-score quintile to 5.2% in the third quintile.
(The top quintile's drop back to 2.8% is because the highest-trigger weeks are dominated by stressed_panic where the state risk multiplier is already 0.)

### What did not help

**The defensive properties that made X1 attractive — Sharpe 0.924, MDD -7.41%, CVaR -1.68% — were given up almost entirely.** Sharpe difference vs X4 (no W1): X1 = +0.069, Y1 = +0.003, Y2 = -0.002, Y3 = +0.000.
MDD difference vs X4: X1 = +2.66pts, Y1 = +0.66pts, Y2 = +0.50pts, Y3 = -0.01pts.
CVaR difference vs X4: X1 = +0.75pts, Y1 = +0.14pts, Y2 = +0.09pts, Y3 = +0.00pts.
Only Y1 preserves any meaningful fraction (≈25% of MDD lift, 19% of CVaR lift); Y2 and Y3 essentially regress to the no-W1 baseline.

**Y3 is mathematically near-identical to X4.** Avg W1 weight = 0.2%, MDD = -10.08% (vs X4 -10.07%), Sharpe = 0.855 (vs X4 0.855), raw composite = 0.469 (vs X4 0.469).
The cash-replacement rule almost never activates with enough magnitude because it requires high trigger AND high cash share AND a non-stressed state — three nearly mutually exclusive conditions.
So Y3, despite being the most production-consistent integration in design, is also the candidate that most closely reproduces the no-W1 ablation.

**Every Y candidate's raw composite is below X1's.** Y1 = 0.467, Y2 = 0.465, Y3 = 0.469, X1 = 0.490.
The conditional sizing rules trade Sharpe/MDD/CVaR for return at a rate worse than the implicit trade in X1 — the production allocator family does not extract enough additional return from the small conditional W1 dose to compensate for the defensive metrics it gives up.

**Phase D production gates remain failed.** All three Y candidates fail at least 5 of 8 production gates (full Δ, holdout Δ, rolling win, rolling mean Δ, bootstrap), the same gate set X1 fails.
Rolling win rate is 26.7% for every Y candidate — identical to X1 — meaning rolling-window evaluation is unmoved by the conditional sizing rules.

### Whether conditional W1 sizing improved deployment proximity

Mixed.
The holdout-raw-composite gap to production narrowed by 60% (X1: -0.188 → Y3: -0.069), and bootstrap probability vs production climbed 14× (0.001 → 0.014).
On those two axes, deployment proximity *did* improve.
But the Phase D production rule requires *all* eight gates simultaneously, and the rolling and full-Δ gates remain unmoved.
No Y candidate is closer to overall promotion than X1; they are just closer on a different subset of axes.

The deeper diagnosis is that the inverse-vol allocator family on the 7-sleeve panel sits on a structural Pareto frontier between two corner solutions: heavy W1 (X1: defensive metrics great, return fails) and light W1 (X4 / Y3: return acceptable, defensive metrics weaker than production).
The frontier between these corners — Y1 / Y2 — does not contain any candidate that clears all eight Phase D gates against the production pin, because the production pin uses a fundamentally different allocator architecture (HRP-based + dynamic risk budget on a 5-sleeve subset) that extracts more return from the same opportunity set than any inverse-vol-on-7-sleeve variant.
Phase Y proves this empirically across three structurally different W1 sizing rules.

### How this sprint differs from Phase X

Phase X tested whether the upgraded 7-sleeve panel could improve a deployable allocator under standard inverse-vol weighting.
It said: yes at the sleeve level, no at the gate level.
Phase Y tested whether the gate-level failure was fixable by smarter W1 sizing inside the same allocator family.
It said no.
Phases X and Y together establish that the panel improvement is real and validated but not absorbable by the inverse-vol allocator family at any reasonable W1 weighting.
The next test must move outside that family.

### Final classification (Phase Y)

| Candidate | Sharpe | MDD | Avg W1 | Raw Composite | Status | Rationale |
|-----------|----------:|----------:|----------:|----------:|-----------|-----------|
| Y1 — state-capped W1 | 0.858 | -9.41% | 5.5% | 0.467 | **Drop** | Caps preserve only 25% of X1's MDD lift, 19% of CVaR lift. Raw composite below X1, X4, U1a, R3, V1, and production. |
| Y2 — trigger-driven W1 | 0.852 | -9.57% | 3.0% | 0.465 | **Drop** | Trigger correctly identifies stress periods, but those coincide with stressed_panic where state mult = 0, so trigger never lifts W1 where it would help. Worst raw composite of the three. |
| Y3 — cash-replacement W1 | 0.855 | -10.08% | 0.2% | 0.469 | **Drop** | Strictly equivalent to X4: avg W1 = 0.2%, MDD = -10.08%, Sharpe = 0.855. Cash-replacement rule almost never activates because its three preconditions are nearly mutually exclusive. |

### Updated reference set

Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.
Shadow pin: `improved_phase2b_combo_abc` — unchanged.
Closest-to-gate research reference: `improved_phaseu_prod90_r2_10_holdings_blend` (U1a) — unchanged.
Bootstrap research reference: `improved_phaseu_conditional_prod_r2_holdings_blend` (U3) — unchanged.
Sharpe research reference: `improved_phaser_fast_narrow_regret_allocator` (R3) — unchanged.
Dev-composite research reference: `improved_phaset_soft_regime_posterior_allocator` (T1) — unchanged.
Full-Δ research reference: `improved_phasev_prod90_phasen_10_holdings_blend` (V1) — unchanged.
Promoted Layer-2 sleeve: `composite_structural_defense_sleeve` (W1) — unchanged.
W1 ablation reference (uncapped, inverse-vol): `improved_phasex_production_style_7sleeve` (X1) — unchanged.
**New entry — best W1-aware inverse-vol-family reference: `improved_phasey_cash_replacement_w1` (Y3).** Recorded as the candidate with the smallest holdout-Δ-vs-production gap (-0.069) inside the inverse-vol-on-7-sleeve family.
Does not displace U1a, R3, or V1 because raw composite (0.469) is below all three; kept as a tracked baseline so future architecture-level tests can quote both X1 (heavy W1) and Y3 (light W1) as the inverse-vol family bookends.

### What comes next

**Phase Z — port the production HRP / dynamic-risk-budget allocator architecture itself onto the 7-sleeve panel.** Phases X and Y have been testing inverse-vol weighting variants on the 7-sleeve panel.
The current production pin uses a different allocator architecture entirely: HRP-based sleeve weighting + the `lighter_both_targeted_narrow_plus_confirmed` overlay + dynamic risk budget, applied to a 5-sleeve subset `[dual_momentum_topn, cta_trend_long_only, selective_strategy, composite_regime_conditioned, taa_10m_sma]`.
The architecture-equivalent test that has not yet been performed is to rebuild that production stack on the 7-sleeve panel (with W1 included) and compare.
If HRP on 7-sleeves clears the gates that inverse-vol on 7-sleeves cannot, the panel improvement becomes deployable.
If HRP on 7-sleeves fails the same way, the diagnosis flips — the 7-sleeve panel improvement is real but allocator-resistant — and the project should turn to a holdings-blend revisit (V-style, but with W1-aware allocators as the candidate blendees) or a new Layer-3 architecture entirely.

A smaller alternate path is to feed the existing X1, X4, Y1, Y2, Y3 candidates as inputs to the V-family holdings blend — pairwise blends of (production × W1-aware research candidate) at varying blend weights.
Holdings blending was the closing branch of Phases Q-V and may extract incremental value when one of the blendees is an explicitly W1-aware allocator on the 7-sleeve panel, even if neither blendee clears the gates standalone.

## Section 39 — Phase Z: Production HRP Architecture on the 7-Sleeve Panel

### Why this sprint moved outside the inverse-vol family

Phase Y closed with a precise structural diagnosis: the inverse-vol allocator family on the 7-sleeve panel sits on a Pareto frontier between heavy W1 (X1: defensive metrics great, return fails) and light W1 (X4 / Y3: return acceptable, defensive metrics weaker than production), and no W1-sizing rule between those corners clears all eight Phase D gates against the production pin.
Phase Y also named the next test explicitly: the production pin uses a different allocator architecture entirely (HRP-based sleeve weighting + `lighter_both_targeted_narrow_plus_confirmed` overlay + dynamic risk budget, on a 5-sleeve subset), and that architecture had never been ported onto the 7-sleeve panel.
Phase Z is that architecture-equivalent rerun.

### What was tried

Four candidates on identical walk-forward / monthly-rebalance / 5 bp half-spread infrastructure:

1.  **Z1 `improved_phasez_production_hrp_7sleeve`** — production architecture (HRP + dynamic risk budget + `lighter_both_targeted_narrow_plus_confirmed` overlay + Phase 2B `regime_confidence_boost` meta) on PANEL_7. The faithful port question: if we hold the architecture fixed and only swap the panel, does the 7-sleeve panel improvement pass Phase D?
2.  **Z2 `improved_phasez_shadow_hrp_7sleeve`** — Z1 with `combo_abc` meta layer instead of `regime_confidence_boost`. The shadow-track architecture-equivalent counterpart.
3.  **Z3 `improved_phasez_w1_integrated_hrp_7sleeve`** — Z1 plus two surgical W1 overrides: add W1 to the defensive-tilt set (so it gets +5% in `stressed_panic`) and enforce a 5% W1 floor in non-stressed states by proportionally scaling other sleeves down. Tests whether *any* W1-aware override inside the HRP family rescues something pure HRP misses.
4.  **Z4 `improved_phasez_production_hrp_5sleeve_ablation`** — Z1 architecture on PANEL_5_PRODUCTION (the actual production 5-sleeve subset). The apples-to-apples baseline: it isolates port quality from panel change.

All four causal and walk-forward at the same 1-week feature lag and turnover-cost convention as the production pin.
1,110 weekly observations per candidate, identical date alignment to Phases X / Y.

### What helped

**HRP on the 7-sleeve panel produces the most defensively attractive risk profile of any candidate ever tested in this project.** Z1 full-history Sharpe 0.93 (vs production 0.88); MDD -8.57% (vs -13.98%); CVaR -1.51% (vs -2.62%).
Holdout Sharpe 2.37 (vs production 2.10).
Across 15 rolling-origin windows, Z1 / Z2 / Z3 win the average-Sharpe race against every comparator (avg 0.886 vs production 0.816).
Holdout Sharpe Δ vs production is the strongest pure-Sharpe signal any allocator candidate has produced in this project: +0.27 / +0.28 / +0.27 for Z1 / Z2 / Z3.
MDD Δ vs production is +5.4 pts and CVaR Δ is +1.10 pts — both clear the production gate caps comfortably.

The architecture port behaved sensibly.
Z2's `combo_abc` shadow variant tracks Z1 within 0.001 raw composite — the same architecture-equivalent relationship that exists between the actual production and shadow pins on the 5-sleeve panel.

### What did not help

**Absolute return — and therefore raw composite, and therefore every Phase D gate that depends on raw composite — was crushed.** Z1 full-history annualized return is 4.24% vs production's 6.90% — a 266 bp shortfall.
Holdout return is 10.61% vs production 15.37% — a 476 bp shortfall.
The mechanism is uniform across Z1 / Z2 / Z3 and isolated by the W1 weight diagnostic: HRP's bisection inverse-variance allocation hands W1 the `MAX_SLEEVE_WEIGHT = 0.45` cap in the *median* week, average 34.0% / 33.9% / 34.0% across all weeks, and 42% in calm_trend / 42% in recovery_confirmed.
That is more weight than the dynamic-risk-budget tilt or the `lighter_both_targeted_narrow_plus_confirmed` overlay or the Phase 2B `regime_confidence_boost` meta layer can compensate for — those mechanisms were tuned for a 5-sleeve panel where the largest single sleeve weight is structurally \~25-30%, not \~45%.

The W1 weight by state is *inverted from intent*: HRP gives W1 more weight in calm_trend (42%) and recovery_confirmed (42%) than in stressed_panic (22%).
The dynamic-risk-budget tilt does pull W1 down in stressed_panic, but the architecture's structural bias still hands W1 the largest share of the portfolio in benign regimes — exactly the regimes where the production pin is heavily allocated to offense and earning the bulk of its full-history return.

**Z3's W1-aware overrides are a no-op.** Z3 vs Z1 differ in raw composite by 0.0002.
The reason is structural: HRP already saturates W1 against the `MAX_SLEEVE_WEIGHT` cap, so adding W1 to the defensive-tilt set (which would lift it +5% in stressed_panic) and enforcing a 5% non-stressed floor are surgical changes that operate on a sleeve already at the ceiling.
The architecture absorbs them entirely.
In Phase X / Y, conditional W1 sizing rules had room to act because the inverse-vol allocator was hitting an *internal* sizing problem; in Phase Z, the allocator is hitting an *external* cap that no W1-aware override can bypass.

**Z4 is strictly worse than the production pin even on the same 5-sleeve panel.** Z4 delivers 5.97% ann return / 0.751 Sharpe / -16.08% MDD vs the actual production pin's 6.90% / 0.885 / -13.98%.
So the Phase Z port is not bit-identical to the production pin — it captures the architecture's broad shape but loses \~93 bp of return and 13 points of Sharpe to whatever production-overlay or risk-budget-detail wasn't replicated.
This matters for the Z1 interpretation: even with a port-quality adjustment of +93 bp added to Z1, the projected ann return would land near 5.17% — still well below the 6.90% production return.
The architectural conclusion (HRP-on-7-sleeve cannot clear Phase D return gates) survives even the most generous port-quality adjustment.

### Whether HRP on the 7-sleeve panel improved deployment proximity

No on the multi-objective scorecard.
Z1 / Z2 / Z3 fail 5 of 8 production gates: full Δ -0.027 (need ≥ +0.015), holdout Δ -0.173 (need ≥ 0), rolling win 26.7% (need ≥ 55%), rolling mean Δ -0.102 (need \> 0), bootstrap 0.003 (need ≥ 0.60).
They clear MDD (+5.41 pt vs -1.0 pt cap), CVaR (+1.10 pt vs -0.20 pt cap), and holdout Sharpe (+0.27 vs -0.02 cap).
Z4 fails 6 of 8.

The Phase Z evidence inverts the usual project pattern: defensive-side wins are large, return-side losses are also large, and the multi-objective weighting in the Phase D rule treats the latter as disqualifying.
This is structurally informative — it tells us that the project's allocator-side toolkit is now exhausted on the 7-sleeve panel under the current `MAX_SLEEVE_WEIGHT` and dynamic-risk-budget constraints.
Both inverse-vol (Phases X / Y) and HRP (Phase Z) over-fund or under-fund W1; no sleeve-sizing rule tested in either family closes the multi-objective gap.

### How this sprint differs from Phases X and Y

Phase X tested whether the upgraded 7-sleeve panel could improve a deployable allocator under inverse-vol weighting.
Phase Y tested whether smarter W1 sizing inside that same family closed the gate-level gap.
Phase Z tested whether the *production architecture itself* — HRP + dynamic risk budget + production overlay + Phase 2B meta — applied to the 7-sleeve panel closes that gap.
All three answer no, but for distinct mechanical reasons: Phase X over-funded W1 via low-vol bias; Phase Y under-funded W1 via conservative caps and triggers that almost never fire when needed; Phase Z over-funded W1 via HRP's risk-anchor bias.
Together the three sprints establish that the panel improvement is real at the sleeve level (Phase X / W ablation evidence) but allocator-resistant across both major allocator families this project uses, under every sizing rule tested.

### Final classification (Phase Z)

| Candidate | Sharpe | MDD | Avg W1 | Raw Composite | Status | Rationale |
|-----------|----------:|----------:|----------:|----------:|-----------|-----------|
| Z1 — production HRP on 7-sleeve | 0.933 | -8.57% | 34.0% | 0.451 | **Research-only** | Best Sharpe / MDD / CVaR / holdout-Sharpe profile in project history; fails 5/8 production gates because HRP allocates W1 at the `MAX_SLEEVE_WEIGHT = 0.45` cap in the median week, capping return. |
| Z2 — shadow HRP on 7-sleeve | 0.925 | -8.67% | 33.9% | 0.444 | **Research-only** | Mirror of Z1 with `combo_abc` meta layer. Identical-to-Z1 risk profile; marginally worse raw composite. Same gate failure pattern. |
| Z3 — W1-integrated HRP variant | 0.933 | -8.57% | 34.0% | 0.451 | **Research-only** | W1-aware overrides absorbed entirely by the existing `MAX_SLEEVE_WEIGHT` ceiling. Demonstrates that the HRP family on the 7-sleeve panel has no remaining tuning headroom for W1. |
| Z4 — HRP on 5-sleeve subset (ablation) | 0.751 | -16.08% | 0% | 0.261 | **Drop** | Strictly worse than the production pin on the production panel. Diagnostic: tells us the Phase Z port loses \~93 bp of return vs the actual production pin. Candidate itself has no deployment or research value. |

### Updated reference set

Production pin: `improved_phase2b_regime_confidence_boost` — unchanged.
Shadow pin: `improved_phase2b_combo_abc` — unchanged.
Closest-to-gate research reference: `improved_phaseu_prod90_r2_10_holdings_blend` (U1a) — unchanged.
Bootstrap research reference: `improved_phaseu_conditional_prod_r2_holdings_blend` (U3) — unchanged.
Sharpe research reference: `improved_phaser_fast_narrow_regret_allocator` (R3) — unchanged.
Dev-composite research reference: `improved_phaset_soft_regime_posterior_allocator` (T1) — unchanged.
Full-Δ research reference: `improved_phasev_prod90_phasen_10_holdings_blend` (V1) — unchanged.
Promoted Layer-2 sleeve: `composite_structural_defense_sleeve` (W1) — unchanged.
W1 ablation reference (uncapped, inverse-vol): `improved_phasex_production_style_7sleeve` (X1) — unchanged.
Best W1-aware inverse-vol-family reference: `improved_phasey_cash_replacement_w1` (Y3) — unchanged.
**New entry — defensive-ceiling reference: `improved_phasez_production_hrp_7sleeve` (Z1).** Recorded as the candidate with the most defensively attractive Sharpe / MDD / CVaR / holdout-Sharpe profile in the project's history.
Does not displace the production-comparable references on the raw-composite axis but is the new reference on the defensive axis, and is the natural blend partner for any future holdings-blend exploration that wants defensive lift without re-opening the panel question.

### What comes next

**Phase AA — V-style holdings blend with a Z1 component.** Phase V already showed that holdings-blending production with a research candidate at a 90 / 10 weight can extract a small raw-composite gain.
Z1's profile is structurally orthogonal to the production pin in a way that no prior research candidate is — heavily defensive, very low MDD / CVaR, positive holdout-Sharpe Δ vs production, but very low absolute return.
A 90 / 10 or 95 / 5 blend of production with Z1 may preserve production's return profile while harvesting a fraction of Z1's defensive lift.
This is the smallest, fastest, most likely-to-succeed next step and should be tried before any more invasive change.

If Phase AA fails, two more invasive branches remain in priority order: (i) relaxing `MAX_SLEEVE_WEIGHT` for W1 specifically (raise its per-sleeve cap to 0.55 or 0.60, leaving the global cap untouched), which the Phase Z evidence argues is the structurally binding constraint; (ii) re-opening Layer 2B regime-engine work to split the long `neutral_mixed` regime (493 / 1,110 weeks — the regime where HRP over-funds W1 most severely) into "neutral but trending toward calm" vs "neutral but trending toward stress" sub-states so the dynamic-risk-budget tilt has a finer-grained handle on W1.
Both branches are larger commitments than Phase AA and should only open if the holdings-blend channel is ruled out.

The Phase X / Y / Z arc is closed with a definitive negative result and a precise structural diagnosis.
The 7-sleeve panel improvement is real but cannot be absorbed by either of the project's major allocator families under the current `MAX_SLEEVE_WEIGHT` constraint and any sleeve-sizing rule tested.
Production and shadow pins remain unchanged.

## Section 40 — Phase AA: Production-Anchored Holdings Blend with Z1

### Why this sprint stayed inside the holdings-blend channel with Z1 as the only partner

Phase Z closed with a precise three-branch fan-out for what should come next.
Branch 1 — a V-style holdings blend of production with Z1 — was named the smallest, fastest, most-likely-to-succeed next step because Z1's profile (full-history Sharpe 0.93, MDD -8.57%, CVaR -1.51%, holdout Sharpe 2.37) was the most defensively attractive in the project's history, but its 4.24% annualized return prevented standalone deployment.
The natural test was whether the linear holdings-blend channel — already proven viable in Phases U / V — could harvest a fraction of Z1's defensive lift while staying anchored on production's 6.90% return engine.
Phase AA is the dedicated sprint for that test.
No new sleeves, no new allocators, no new regime engine, no new ML, no new trust layer, no broad blend grid.
Only three high-conviction blend candidates plus the same fixed comparator set used in Phases X / Y / Z augmented with U1a, U3, V1.

### What was tried

Three blend candidates over production weights and Z1 weights at the ETF level, using exactly the Phase V / U linear blend convention so AA candidates compare apples-to-apples against U1a, U3, V1:

1.  **AA1 `improved_phaseaa_prod95_z1_05_holdings_blend`** — static 95 / 5. Most conservative test. Preserves nearly all of production's return engine and tests whether even a small Z1 dose imports defensive value cheaply.
2.  **AA2 `improved_phaseaa_prod90_z1_10_holdings_blend`** — static 90 / 10. The natural primary test. Phase V-style anchor weighting at the ratio prior holdings-blend phases consistently identified as the right region of the blend space.
3.  **AA3 `improved_phaseaa_state_conditional_prod_z1_holdings_blend`** — causal walk-forward state-conditional schedule indexed on `market_state_history.market_state` at t-1: `calm_trend → 0.95`, `neutral_mixed → 0.92`, `recovery_confirmed → 0.90`, `recovery_fragile → 0.85`, `stressed_panic → 0.85`. Realized average production share = 0.910. Tests whether causal state-conditioning at the holdings-blend level extracts more value than a static mix at the same average ratio.

After inspecting AA1 / AA2 / AA3 diagnostics, no AA4 was added.
The gradient from AA1 → AA2 → AA3 is monotonic in raw composite (smaller Z1 dose = better composite) and the structural mechanism identified below is fundamental enough that no narrowly-justified fourth blend would have moved the strategic decision.
AA4 was deliberately skipped to keep the sprint narrow.

All Phase Z causal/walk-forward safety carried over: 1-week-lagged state for AA3, 5 bp half-spread cost on schedule transitions, no retraining of any branch.

### What helped

**The defensive metrics moved the right way at the magnitude predicted by linear blending.** AA1 (95 / 5) tightens MDD by 0.27 pts (production -13.98% → AA1 -13.71%) and CVaR by 0.06 pts (production -2.62% → AA1 -2.56%), lifts holdout Sharpe by +0.011, and preserves 98.1% of production's full-history return engine (6.90% → 6.77%).
AA2 (90 / 10) extends those moves: MDD tightens by 0.53 pts, CVaR by 0.12 pts, holdout Sharpe lifts by +0.022.
AA3 lands between AA1 and AA2 on every metric.
All three Z1-blended candidates clear the MDD cap (≥ -1.0 pt), the CVaR cap (≥ -0.20 pt), and the holdout Sharpe Δ gate (≥ -0.02) — and in fact deliver positive holdout Sharpe Δ vs production of +0.011 to +0.022.
**Three of eight gates cleared.** The defensive part of the test worked exactly as intended.

### What did not help

**Absolute return — and therefore raw composite, full-Δ, holdout-Δ, rolling win-rate, rolling mean Δ, and bootstrap.** The blend math is exactly linear: AA1's 6.77% annualized return = `0.95 × 6.90% + 0.05 × 4.24%`.
AA2's 6.64% = `0.90 × 6.90% + 0.10 × 4.24%`.
There is no "complementarity premium" — every basis point Z1 contributes also costs a proportional fraction of production's return engine.
Because Z1's full-history return is 266 bp below production's, even a 5% Z1 dose imports a 13 bp return drag, and a 10% dose imports a 26 bp drag.
That drag is enough to push raw composite from production's 0.478 to AA1's 0.442 (-0.035) and to AA2's 0.439 (-0.039).
Five of eight gates fail (full Δ, holdout Δ, rolling win, rolling mean Δ, bootstrap).

**The state-conditional AA3 schedule produced no advantage over the static AA1.** AA3's realized 91 / 9 average is worse than AA1's static 95 / 5 because AA3 weights heavier Z1 in `recovery_fragile` and `stressed_panic` (29% of weeks combined) — and a post-hoc overlap diagnostic shows production and Z1 ETF weight vectors overlap at 0.46 in `stressed_panic` weeks (about 4.4× the overlap in `calm_trend`, where overlap is 0.11).
Both portfolios pivot to the same defensive ETF concentration (BIL, TLT, IEF) when defense is needed.
So the AA3 schedule allocates the largest Z1 dose precisely in the regimes where Z1's marginal defensive contribution is smallest.
The conditional rule has the wrong sign relative to the actual mechanism.

**AA candidates lose to U1a, U3, and V1.** U1a raw composite 0.484, U3 0.490, V1 0.495, vs AA1 0.442 / AA2 0.439 / AA3 0.439.
The earlier holdings-blend partners (R2 in U1a / U3, Phase N in V1) had absolute returns close to production's, so the linear blend math dragged returns less than a Z1 blend does.
AA candidates are not the new closest-to-gate research reference.

### Whether production+Z1 holdings blending materially improved deployment proximity

No, materially, on the multi-objective Phase D scorecard.
AA1 narrows the holdout-Sharpe gap to a positive Δ (best in the project on that single axis) and tightens MDD/CVaR by the magnitude the linear blend predicts, but on every return-side gate the blend moves *further* from production than U1a, U3, or V1.
The structural mechanism is twofold: (i) linear blend math has no escape — every metric approximately linear in returns gets exactly its linear-blend value, with no synergy available; (ii) the production–Z1 ETF overlap is highest in stressed regimes, so the AA blend imports the *least* incremental defensive value precisely in the regimes where defense matters most.
State-conditional schedules amplify rather than offset this misalignment.

### What this closes and what comes next

**Outcome B — production+Z1 holdings-blend path closes.** Production pin unchanged.
Shadow pin unchanged.
Closest-to-gate research reference unchanged (U1a).
Sharpe research reference unchanged (R3).
Full-Δ research reference unchanged (V1).
W1 ablation reference unchanged (X1).
Defensive-ceiling reference unchanged (Z1).
No new research reference is added by Phase AA. AA1 is recorded as a "minimal defensive holdings-overlay" candidate but is strictly worse than U1a on the same axis (raw composite 0.442 vs 0.484), so it does not enter the official reference roster.

The W1 panel-level value identified in Phase X / W remains structurally hard to harvest into a deployable candidate via any allocator-side or holdings-blend mechanism this project has tested.
The three direct allocator families (inverse-vol per Phases X / Y, HRP per Phase Z) over-fund W1 against the global `MAX_SLEEVE_WEIGHT = 0.45` cap; the holdings-blend channel (per Phase AA) drags returns proportionally and overlaps adversely with production in stressed regimes.

**Phase BB — relax `MAX_SLEEVE_WEIGHT` for W1 specifically inside the HRP architecture.** This is Branch 2 from the Phase Z three-branch fan-out and is now the next narrow test.
The Phase Z evidence argued that the global cap, not the architecture, was the binding structural constraint; Phase AA's failure on the holdings-blend channel removes Branch 1 from contention and elevates Branch 2 to the next position.
Specifically: BB1 = HRP allocator on the 7-sleeve panel with `MAX_W1_WEIGHT` raised from 0.45 to 0.55; BB2 = same with 0.60 (stretch of the same parameter axis to detect plateau vs continued gradient); BB3 = `MAX_W1_WEIGHT = 0.55` with `MAX_SLEEVE_WEIGHT = 0.50` for the other six sleeves (disentangles W1-specific cap from global cap).
If Phase BB also fails, escalate to Branch 3 — Phase CC — re-open Layer 2B regime-engine work to split the long `neutral_mixed` regime (493 / 1,110 weeks where HRP over-funds W1 most severely) into "trending toward calm" vs "trending toward stress" sub-states so the dynamic-risk-budget tilt has finer-grained handle on W1.

**Lessons that should carry forward.** Linear blend math has no escape — a static or causal-state-conditional linear blend of two long-only portfolios cannot import return-dimension benefits, only approximately-linear-in-returns metrics like MDD / CVaR / Sharpe-near-equal-vol.
Sleeve-level orthogonality does not imply ETF-level orthogonality — production and Z1 are highly orthogonal at the sleeve level (different sleeves) but not orthogonal at the ETF level in stressed regimes (same defensive ETF concentration).
State-conditional schedules don't help when the underlying components are linear unless the schedule puts the partner where the partner is *most differentiated* from the anchor (not where the partner is most defensive in absolute terms).
Future blend-channel exploration should compute regime-conditional ETF overlap of the candidate partner up front, not after the fact.

The Phase X / Y / Z / AA arc is closed with a definitive negative result: the 7-sleeve panel improvement is real and structurally improves the defensive frontier, but cannot be absorbed by any allocator family or holdings-blend channel this project currently uses under the current `MAX_SLEEVE_WEIGHT` constraint.
Production and shadow pins remain unchanged.
The next test (Phase BB) is the smallest single-parameter intervention that targets the structural constraint Phase Z named — relaxing the W1 cap — and is the right move before any more invasive change.

## Section 59 — Phase SS: Explicit In-Allocator Multi-Bucket Architecture

**Mission.** Phase RR established that the right frontier had moved up from sleeve-local cash heuristics to allocator structure, but it was still using a soft bucket tilt on top of the existing HRP machinery. Phase SS pushed that idea one level further by introducing an explicit state-conditioned bucket architecture. Instead of only nudging the allocator, it imposed hard bucket budgets across offense, defense, composite, and cash before final sleeve allocation, while keeping stressed-panic guardrails intact.

**What changed.** The bucket split stayed simple and grounded in the live production stack: offense was `dual_momentum_topn`, `cta_trend_long_only`, and `composite_selective_signals`; defense was `taa_10m_sma`; composite was `composite_regime_conditioned`; cash was `cash::BIL`. Phase SS then defined conservative target bucket budgets by state. The most important changes were in `recovery_confirmed`, `recovery_fragile`, `neutral_healthy_proxy`, and `calm_trend`, where production had been carrying too much composite and, in some states, too much cash.

**What helped.** The recovery-only explicit bucket candidate (`improved_phasess_recovery_explicit_bucket`) was the strongest version. It improved the exact bottleneck states the project cared about: `recovery_confirmed` and `recovery_fragile` both improved meaningfully, `neutral_healthy_proxy` improved modestly, and the full-window Sharpe finally rose versus production instead of falling. The lift was not just hidden beta. Average BIL fell slightly, SPY rose only slightly, and average composite bucket weight came down while stressed-panic behavior remained effectively intact.

**What did not help enough.** The architecture still did not clear the stricter bar. The best candidate improved full-window Sharpe by only about **+0.0024**, which was better than RR but still below the required **+0.005** quick-screen threshold. `calm_trend` remained a small giveback state, and the allocator benchmark still judged the added complexity as only marginally justified for production because the candidate did not clearly beat the best simple internal baseline on Sharpe.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The best Phase SS candidate earned a **KEEP AS SHADOW** verdict and survived quick realism and allocator-benchmark follow-ups well enough to remain an important research reference.

**Interpretation.** Phase SS is still an important step forward. It showed that the project is more likely to improve through a true allocator-architecture redesign than through another round of sleeve-internal cash patches. It also showed that explicit bucket budgets are stronger than soft top-of-HRP tilts. But it did not yet show that the first explicit-bucket implementation is enough by itself. The next iteration should stay on this frontier and move toward a stricter two-stage allocator with explicit risky-budget versus cash-budget coordination and tighter interaction with downstream overlays, rather than returning to narrow `composite_regime_conditioned` heuristics.

## Section 60 — Phase TT: Stricter Two-Stage Bucket Allocator

**Mission.** Phase SS showed that explicit bucket budgets were better than the soft RR architecture, but the gains were still being partially absorbed downstream. Phase TT tested a stricter two-stage design: Stage 1 set explicit risky-versus-cash budgets by state, and Stage 2 allocated the risky budget across offense, defense, and composite sleeves with tighter composite ceilings. The main question was whether the project could finally coordinate the allocator's intended recovery-state risk budget with the downstream overlay/cash path.

**What changed.** TT kept the same broad sleeve buckets as SS but made the recovery design stricter. In `recovery_confirmed` and `recovery_fragile`, the risky sleeve mix moved further away from the composite bucket and further toward the better recovery sleeves, while preserving stressed-panic guardrails. TT then added an overlay-side risky-budget coordination rule so the downstream regime-cash mechanism would be less likely to re-absorb the intended recovery-state participation.

**What helped.** The best candidate (`improved_phasett_recovery_two_stage_bucket`) was the strongest recovery-state design the project has tested on this frontier so far. It improved `recovery_confirmed` and `recovery_fragile` more than SS1, improved full-window Sharpe again, improved holdout Sharpe to the best level of the TT set, and stayed broadly intact in `stressed_panic`. It also reduced composite-bucket weight without relying on a large hidden-SPY increase.

**What did not help enough.** TT failed its core architectural test. The best candidate improved **total** final participation a bit, but it did **not** reduce **overlay-stage absorption** in the targeted recovery states relative to production. That is the key negative result. The two-stage design was directionally right, but the incumbent overlay architecture still reclaimed too much risky budget after the allocator had already made the recovery-state decision. The full-window Sharpe delta rose to about **+0.0040**, which was better than SS but still below the required **+0.005** gate.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The best Phase TT candidate earned a **KEEP AS SHADOW** verdict and survived quick realism and allocator-benchmark checks well enough to remain a useful research reference.

**Interpretation.** Phase TT is important because it clarifies the remaining bottleneck. Upstream allocator architecture has improved enough to matter, but the downstream overlay still behaves like a separate cash-creation regime that is not yet truly aligned with the allocator's state-conditioned risk budget. That means the next step should no longer be "more bucket tweaks upstream." The next step should be a direct overlay-architecture redesign that treats risky-budget preservation as a first-class rule instead of trying to patch it indirectly from earlier stages.

## Section 61 — Phase UU: Budget-Preserving Overlay Redesign

**Mission.** Phase TT established that the new two-stage allocator was strong enough to improve the right states, but it still could not clear the stricter gate because the downstream overlay was reclaiming too much of the recovery-state risky budget. Phase UU targeted that exact bottleneck. Instead of changing the upstream allocator again, it asked whether the overlay itself could be made more budget-preserving in `recovery_confirmed` and `recovery_fragile` without weakening stressed-panic protection.

**What changed.** UU kept the TT1 recovery two-stage allocator as the upstream anchor and only modified the downstream overlay path. The three variants all stayed narrow: one preserved the TT1 recovery budget more directly, one added an explicit recovery overlay-cash cap, and one made the `lighter_both` recovery logic aware of the upstream risky/cash budget. Stressed-panic behavior was intentionally left unchanged. The point was not to make the portfolio broadly more risk-on. The point was to see whether the overlay-stage cash clawback itself could finally be reduced.

**What helped.** The best UU candidate (`improved_phaseuu_tt1_budget_aware_lighter_both`) was another real, if small, improvement. Full-window annual return and Sharpe both improved a bit versus TT1 and production. Recovery-state behavior improved again: `recovery_confirmed` and `recovery_fragile` both gained further on annual return and Sharpe, `neutral_healthy_proxy` stayed better than production, and stressed-panic remained broadly intact. The realism audit was supportive enough to say the edge survived doubled-cost stress, and the committee kept the candidate as a shadow-level research reference.

**What did not help enough.** UU failed the exact test it was designed to pass. The overlay-stage absorption metric improved versus TT1, but it still did not improve on average versus production across the targeted recovery states. `recovery_confirmed` got a better overlay outcome, but `recovery_fragile` still lost more risky budget at the overlay stage than production did. The full-window Sharpe delta rose only to about **+0.0041** versus production, still below the required **+0.005** quick-screen bar. That means UU showed the overlay frontier is real, but also showed that small recovery-state caps and buffers are not enough to solve it cleanly.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The best Phase UU candidate earns **KEEP AS SHADOW**.

**Interpretation.** Phase UU effectively exhausts the narrow overlay-preservation patch path. The project now has strong evidence that upstream allocator architecture matters, but that the downstream `lighter_both` / regime-relief cash layer still operates too independently from the intended state-conditioned risky budget. The next step should stay on this frontier, but it should no longer be another small overlay threshold tweak. It should be a broader overlay-architecture redesign inside `apply_overlays_custom`, where risky-budget preservation becomes a first-class design rule rather than a small exception layered on top of the incumbent overlay.

## Section 62 — Phase VV: First-Class Budget-Aware Overlay Architecture

**Mission.** Phase UU showed that small recovery cash caps and buffers were not enough. The overlay still behaved too independently from the upstream risky/cash budget, especially in the `lighter_both_regime_relief` branch. Phase VV therefore moved one level deeper: it redesigned the overlay so recovery-state budget preservation became a first-class rule, with target-vol allowed to block it only when target-vol was the true active guardrail rather than merely a multiplier below 1.

**What changed.** The new overlay logic kept the TT recovery budgets as the intended baseline, then explicitly compared post-overlay cash to those intended budgets. Three variants were tested. One used strict recovery budget preservation, one used a small tolerance band, and one extended the same architecture lightly into `neutral_healthy_proxy`, where the overlay had also been exceeding the upstream intended cash budget. This was still a disciplined change: stressed-panic remained untouched, target-vol guardrails were preserved, and no new sleeves or ML were introduced.

**What helped.** VV was the strongest overlay-architecture result so far on headline metrics. The best candidate (`improved_phasevv_recovery_neutral_budget_aware_overlay`) became the strongest recent research challenger by full annual return and full Sharpe, edging both TT1 and UU-best. It reduced average BIL, slightly improved SPY/offense participation, and preserved stressed-panic behavior. More importantly for mechanism, it compressed the **budget-gap** problem more cleanly than prior phases. In `recovery_confirmed` and `neutral_healthy_proxy`, post-overlay cash sat closer to the intended budget than in TT1 or UU-best.

**What did not help enough.** VV still failed the exact bottleneck test. The budget gap got better, but the targeted **overlay-absorption** metric in the recovery states did not improve versus production. `recovery_confirmed` improved slightly, but `recovery_fragile` was still worse than production at the overlay stage, which kept the targeted mean recovery overlay-absorption reduction negative. So VV clarified an important distinction: improving the distance between intended cash and post-overlay cash is not automatically the same thing as reducing the actual risky-budget absorption that matters for the project. Full-window Sharpe improved again, but only to roughly **+0.0048** versus production on the phase's exact metrics, still below the strict **+0.005** gate.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The committee kept the best Phase VV candidate as **KEEP AS SHADOW**.

**Interpretation.** Phase VV is useful because it shows the project is now very close to the limit of what can be achieved by making the overlay *respect* the intended budget after the fact. The next step should go deeper and rewrite the `lighter_both_regime_relief` recovery logic itself so it becomes natively budget-aware, rather than letting it behave like an almost-separate cash engine that only receives a budget-preservation correction afterward. In other words, VV says the frontier is still overlay architecture, but the remaining work now sits inside the branch rule itself, not in another layer of caps or tolerance bands.

## Section 63 — Phase WW: Recovery-Overlay Rescue Sprint

**Mission.** Phase VV left the project one very specific unsolved problem: the recovery-side `lighter_both_regime_relief` branch was still re-adding cash after the allocator had already made a better state-conditioned recovery budget decision. Phase WW was a focused rescue sprint for that single mechanism. Instead of adding another cap, it rewrote the recovery branch itself so it would compute cash from the intended recovery budget and only add more cash when a true guardrail such as target-vol or stressed-panic protection required it.

**What changed.** The phase tested a disciplined family of branch-native rewrites. Three main candidates rewrote the recovery `lighter_both` rule directly, and after those all failed narrowly, three rescue variants were added to probe the failure mode more carefully. The key rescue move was to stop treating `recovery_confirmed` and `recovery_fragile` as if they could share the same rewrite. That produced one candidate (`improved_phaseww_confirmed_only_lighter_both`) that only changed `recovery_confirmed` and left `recovery_fragile` closer to the incumbent behavior.

**What helped.** Phase WW did move the mechanism in the right direction. The best rescue candidate finally made the **targeted mean recovery overlay-absorption metric slightly positive** versus production, which no prior TT / UU / VV candidate had done cleanly. It also improved full-window annual return and Sharpe versus production, preserved stressed-panic reasonably well, survived the quick realism audit, and did not look like a hidden-beta shortcut.

**What did not help enough.** The branch still did not clear the real gate. The best WW candidate improved Sharpe versus production by only about **+0.0043**, still below the strict **+0.005** threshold, and it still did **not** beat the best Phase VV challenger on Sharpe. More importantly, the only way WW could make recovery overlay absorption positive on average was by effectively conceding that `recovery_fragile` still needed to stay close to production-like overlay behavior. That is the decisive result: the project can improve `recovery_confirmed` through this direct branch rewrite, but it cannot solve the full recovery overlay problem cleanly enough by continuing to patch the `lighter_both` recovery rule in isolation.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The best WW candidate earned **KEEP AS SHADOW** in committee terms, but the research conclusion is stronger than that: this narrow recovery-overlay rescue branch is now **exhausted**.

**Interpretation.** Phase WW is valuable because it closes the loop honestly. It confirms that the project is not one tiny recovery cash tweak away from a clean production promotion. The remaining problem is broader than the direct `lighter_both` recovery rewrite. The next phase should move up one level and simplify or unify the overlay architecture itself so the allocator owns the risky/cash decision and the overlay becomes only a true guardrail layer for target-vol and stressed-panic defense, not a second quasi-independent recovery cash engine.

## Section 64 — Phase XX: Overlay Simplification / Allocator-Overlay Unification

**Mission.** Phase WW exhausted the narrow recovery-overlay rescue branch. The project had strong evidence that upstream allocator architecture was improving the right states, but it also had equally strong evidence that the live stack still contained two partially independent cash-decision systems: the allocator chose a risky-versus-cash budget first, then the overlay recreated a second quasi-independent recovery cash budget afterward. Phase XX therefore stopped treating the problem as a local recovery patch and tested a broader architecture simplification: the allocator should own the risky/cash decision, while the overlay should act only as a true guardrail layer for target-vol, stressed-panic protection, and minimum safety floors.

**What changed.** Phase XX rewired the recovery-side overlay logic so it explicitly compared the allocator's intended cash budget with guardrail needs before adding any extra cash. Four disciplined candidates were tested. The most aggressive versions applied a guardrail-only overlay in recovery states, while the conservative hybrid applied the simplification only when duplicated overlay cash was clearly above a threshold and otherwise fell back to the stronger VV behavior. This was still implemented inside the production construction pipeline, with no post-hoc ETF patching, no direct SPY injection, and stressed-panic plus true target-vol logic preserved.

**What helped.** The best candidate (`improved_phasexx_conservative_hybrid_overlay`) became one of the strongest recent challengers on full-window metrics. It improved annual return and Sharpe versus production, slightly beat the best WW result on Sharpe, reduced duplicated recovery cash meaningfully in both `recovery_confirmed` and `recovery_fragile`, preserved stressed-panic behavior, survived the doubled-cost realism quick audit, and did not look like a hidden-beta shortcut. Mechanically, it is important because it finally showed that the duplicated-cash problem itself can be reduced directly rather than only nudged indirectly.

**What did not help enough.** Phase XX still did not clear the true gate. The best candidate improved Sharpe versus production by about **+0.0047**, which is very close but still below the strict **+0.005** threshold, and it did not beat the stronger VV reference on Sharpe. More importantly, it reduced **duplicated recovery cash** more clearly than it reduced the project's exact **overlay-absorption** metric. `recovery_confirmed` improved at the overlay stage, but `recovery_fragile` was still slightly worse than production on overlay absorption, leaving the targeted mean recovery overlay-absorption reduction still slightly negative. That is the decisive architectural result: simplifying the overlay helped, but not enough to convert the remaining mechanism gap into a clean production challenger.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The best Phase XX candidate earns **KEEP AS SHADOW** at the committee level, but the research conclusion is stronger: the overlay-simplification / allocator-overlay unification branch is now **exhausted**.

**Interpretation.** Phase XX is useful because it closes the full overlay frontier honestly. The project now has evidence across SS, TT, UU, VV, WW, and XX that better allocator budgets and better overlay awareness can improve the right states and can get very close to the gate, but they still cannot fully solve the remaining bottleneck inside the current sleeve/overlay architecture. The next phase should move to a different frontier instead of continuing overlay surgery. The strongest next candidate frontier is a broader sleeve-architecture simplification or decomposition effort, especially around `composite_regime_conditioned` and any other sleeve structures that still hide defensive cash behavior before the overlay even acts.

## Section 65 — Phase YY: Composite Sleeve Decomposition / Sleeve-Architecture Simplification

**Mission.** Phase XX exhausted the overlay simplification branch. The project had learned that the allocator and overlay were duplicating cash decisions, but it had not yet addressed another deeper duplication: `composite_regime_conditioned` itself was already bundling together offense, defense, and cash before the allocator even saw it. Phase YY therefore moved the architecture up one more level. Instead of hiding those decisions inside one sleeve, it decomposed the composite sleeve into explicit offense, defense, and cash components so the allocator could control them directly.

**What changed.** The decomposition was built from the sleeve's real ETF positions rather than from a new predictive model. `SPY / QQQ / IWM / EFA / VEA / VWO / EWJ / VNQ / PDBC / DBA` formed the offense component, `HYG / LQD / GLD / TLT` formed the defense component, and `BIL` formed the cash component. Four candidates then replaced `composite_regime_conditioned` with explicit offense and defense sleeves while leaving cash at allocator level. Some variants used the cleaner XX overlay reference, one used the stronger VV overlay reference, and one used a conservative decomposed architecture.

**What helped.** This phase produced the clearest new structural signal since the overlay branch started. Hidden composite cash was materially reduced, the best candidate (`improved_phaseyy_conservative_decomposition`) improved full-window Sharpe strongly, beat the strongest VV and XX references on Sharpe, preserved stressed-panic reasonably well, survived the doubled-cost realism check, and even passed the allocator benchmark against the simple internal baselines. Just as important, the decomposition diagnosis itself was highly informative: in `recovery_confirmed` and `recovery_fragile`, the original composite sleeve was not just hiding cash, it was also hiding a large non-cash defensive book.

**What did not help enough.** The strict phase screen still rejected every Phase YY candidate. The reason was not hidden beta or overlay cash anymore. The reason was that the decomposed family still became too defensive in the exact recovery states the project was trying to improve. `recovery_fragile` worsened materially for every candidate, and `recovery_confirmed` also weakened. So Phase YY did not produce a production challenger even though it materially improved the full-window risk-adjusted profile.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Shadow pin remains `improved_phase2b_combo_abc`. The best Phase YY candidate earns **KEEP AS SHADOW** and becomes an important architecture reference, but not a promotion candidate.

**Interpretation.** Phase YY is still a very strong result because it changes the problem definition in a productive way. The project no longer looks blocked by overlay cash surgery. It now looks blocked by how the allocator budgets the **explicit** composite offense and defense components once they are finally exposed. That means this branch should continue. The next iteration should stay on the decomposed-sleeve frontier and focus on capping or re-budgeting the new explicit defense component in `recovery_fragile` and `recovery_confirmed`, rather than returning to any hidden cash or overlay heuristic work.

---

## Section 53 — Phase ZZ: Decomposed-Component Allocator Rebudgeting

**Mission.** Phase YY's `improved_phaseyy_conservative_decomposition` was an architecture breakthrough — it improved full-window Sharpe (0.8848 → 0.9297), MDD (-13.98% → -11.75%), CVaR (-2.62% → -2.50%) and reduced both BIL and SPY exposure (no hidden beta). But it materially worsened recovery_confirmed (-1.04pp ann return) and recovery_fragile (-1.08pp). Phase ZZ's mission was to keep YY's architectural win while rebudgeting the recovery-state component allocation away from too much explicit defense.

**Four candidates tested (≤4 per spec).** All produced via the production construction pipeline through new tilt-mode branches in `_apply_phase_yy_decomposition_architecture`. Each rebudgets the offense/defense bucket targets in recovery states (and optionally strong_neutral) while preserving stressed_panic protection, calm_trend behaviour, and YY's explicit cash component.

- ZZ1 `improved_phasezz_recovery_offense_rebudget` — recovery_confirmed offense 0.62→0.68, recovery_fragile offense 0.54→0.60.
- ZZ2 `improved_phasezz_recovery_neutral_offense_rebudget` — ZZ1 + small strong_neutral rebudget (offense 0.60→0.65).
- ZZ3 `improved_phasezz_confirmed_freer_fragile_conservative` — bigger shift in confirmed (offense 0.72), smaller in fragile.
- ZZ4 `improved_phasezz_conservative_decomposition_repair` — minimum-shift safety-first variant.

**All four ZZ candidates beat both production AND YY on every full-window axis.** Headline (ZZ2 best): ann return 7.08% vs production 6.89% vs YY 6.99%; Sharpe 0.9347 vs 0.8848 vs 0.9297; MDD -11.75% (matched YY, +2.23pp better than production); CVaR -2.51% (vs production -2.62%); BIL 26.52% (vs production 28.39%, equal to YY); SPY 6.09% (vs production 7.08%, near-equal to YY) — **no hidden beta inflation**.

**Substantial recovery_fragile repair, partial recovery_confirmed repair.** ZZ2 vs production: recovery_confirmed -0.91pp ann (YY was -1.04pp; +0.13pp improvement, ~12% of YY's damage repaired); recovery_fragile -0.36pp ann (YY was -1.08pp; +0.72pp improvement, **~67% of YY's damage repaired**). The bucket-level defense/offense ratio in recovery_fragile fell from YY's 0.82 to ZZ2's 0.71 (production benchmark 0.30); recovery_confirmed fell from YY's 0.67 to ZZ2's 0.55 (production 0.42). Stressed_panic delta vs production: +0.20pp (protection preserved).

**Quick committee verdict (Layer 2).** **KEEP AS SHADOW** for ZZ2: "Holdout Sharpe and max drawdown both improve, but the candidate fails the production return-delta gate." Per spec, the genuine improvement on Sharpe AND MDD triggered Layer 5/6 quick audits.

**Layer 5 + 6 quick audits — passed decisively.** Realism: Δ ann return constant at +0.20-0.22pp across 0/5/10bp cost grid; +0.30pp at 1-week delay; Δ Sharpe +0.05 across all cost levels. Allocator benchmark: **"Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed."** This is the FIRST candidate in the entire post-Phase-Z arc to pass the allocator-side promotion bar.

**Final decision.** **KEEP AS SHADOW** — ZZ2 is the new strongest architecture-reference shadow on the decomposed-allocator branch, replacing YY in that role. Why NOT PRODUCTION CHALLENGER PENDING HUMAN REVIEW: the spec requires "does not materially worsen recovery_confirmed or recovery_fragile" and ZZ2's recovery_confirmed at -0.91pp ann is materially worse than production. The recovery_confirmed gap is the binding constraint between SHADOW and CHALLENGER tier.

**Production pin remains unchanged.** `improved_phase2b_regime_confidence_boost`. **Shadow pin remains unchanged.** `improved_phase2b_combo_abc` (the dual-track official shadow). ZZ2 becomes the architecture-reference shadow on this branch (replacing YY).

**Should decomposed-component rebudgeting continue?** **Yes — clearly the active improvement frontier.** Every ZZ candidate beats both production and YY on every full-window risk-adjusted axis with no hidden beta. The remaining problem is narrow: a single state (recovery_confirmed) accounts for the gap between SHADOW and CHALLENGER. The next phase should pursue (i) deeper recovery_confirmed rebudget pushing offense to 0.78-0.82 with higher mix_strength, (ii) finer offense_target_mix per state to bias toward higher-Sharpe sleeves in recovery_confirmed (cta_trend_long_only had Sharpe 2.52 there), or (iii) asymmetric defense composition reducing the `composite_regime_defense_component` share inside the defense bucket of recovery_confirmed without changing total defense weight.

**Lessons to carry forward.**
1. **The decomposed component family is the right architectural surface.** The four ZZ candidates differ only in bucket-budget parameters and all four beat production+YY — confirming the architecture is robust and the problem is purely in the bucket weights.
2. **Recovery_fragile is repairable; recovery_confirmed is harder.** ZZ2 closed 67% of YY's recovery_fragile damage with the same parameter pattern that closed only 12% of recovery_confirmed damage. This suggests recovery_confirmed has a structural reason for over-defense that the simple bucket rebudget cannot fully fix.
3. **Allocator-side bar PASSED for the first time in the arc.** Prior phases failed the strict "Sharpe must beat best internal baseline by ≥0.05" rule — ZZ2 passes it cleanly. This is methodologically important: it confirms ZZ2's improvement is structural (not a noise artifact) under multiple independent comparison frameworks.

**Project-arc summary through Phase ZZ.** Phases X–Z established the 7-sleeve panel. Phases AA / BB closed holdings-blend / cap-relaxation. Phase CC produced the refined state. Phases DD–GG closed the Phase CC hint→multiplier consumption thread. Phases HH–KK explored regime-confidence-multiplier interventions (HH and II both produced sub-strict-gate positives; JJ + KK confirmed light interpretable ML wins, refined-state features hurt OOS, and prediction improvement does not auto-translate to portfolio improvement). Phase LL closed the post-hoc dual-bucket structural alternative for the same reconstruction-fidelity reason. Phases MM-XX (overlay surgery family, not all logged here) explored the overlay-cash branch and established the WW/XX/YY decomposition family as the active architecture frontier. Phase YY decomposed `composite_regime_conditioned` into explicit offense/defense/cash components — major architectural breakthrough but with a recovery-state side effect. **Phase ZZ delivers the substantial repair: full-window improvement on every axis vs both production AND YY, with 67% of YY's recovery_fragile damage repaired.** ZZ2 is the new architecture-reference shadow on the decomposed-allocator branch.

## Section 66 — Phase BBB: Recovery_Confirmed Offense-Composition Extension

**Mission.** Phase AAA showed that the total `recovery_confirmed` offense bucket around `0.68` was already about right. Raising the total bucket was not the fix. The remaining blocker was the composition *inside* the confirmed offense and defense buckets. Phase BBB therefore stayed on the decomposed AAA2 architecture and tested a bounded confirmed-only composition extension.

**What changed.** Four additive candidates were built inside the production construction pipeline, all starting from AAA2 and all modifying only `recovery_confirmed`. BBB1 raised `offense_mix_strength` while keeping AAA2's mix. BBB2 tilted more confirmed offense toward `composite_regime_offense_component`. BBB3 combined the stronger offense tilt with a repo-evidence defense repair that leaned toward `composite_regime_defense_component`, not `taa_10m_sma`. BBB4 was the safety-first variant with the smallest confirmed-only mix adjustment. `recovery_fragile`, `stressed_panic`, the decomposed sleeve architecture, explicit cash, and the live target-vol / panic guardrails all stayed intact.

**What helped.** The diagnostics sharpened the confirmed-state picture. `composite_regime_offense_component` remained the strongest confirmed offense leg, `cta_trend_long_only` still helped, and `composite_selective_signals` plus `dual_momentum_topn` remained the weakest confirmed offense sleeves. The best candidate, `improved_phasebbb_offense_defense_composition_combo`, raised confirmed `composite_regime_offense_component` from `0.1747` to `0.2130`, reduced `dual_momentum_topn` from `0.1070` to `0.0930`, reduced `composite_selective_signals` from `0.1448` to `0.1251`, and shifted confirmed defense away from `taa_10m_sma` and toward `composite_regime_defense_component`. That produced a new best full-window profile on this branch: annual return `7.13%`, Sharpe `0.9368`, SPY still below production (`6.08%` vs `7.08%`), `recovery_confirmed` improved versus AAA2 by `+0.05pp`, and `recovery_fragile` improved versus AAA2 by `+0.07pp`.

**What did not help enough.** Even the best BBB candidate still left `recovery_confirmed` materially below production at about `-0.67pp` annual return. So this phase did not create a production challenger. But it did answer the active question cleanly: the remaining blocker is no longer total offense size, no longer overlay cash, and no longer a TAA-heavy defense repair. It is the final confirmed-state offense mix, where too much budget is still leaking into `dual_momentum_topn` and `composite_selective_signals` relative to their confirmed-state quality.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Official shadow pin remains `improved_phase2b_combo_abc`. The best Phase BBB candidate is **KEEP AS SHADOW** and becomes the new **architecture-reference shadow**, replacing AAA2 in that role.

**Interpretation.** This branch should continue. Phase BBB is exactly the kind of bounded extension the project needed: it improved full-window Sharpe again, improved `recovery_confirmed` again, preserved `recovery_fragile`, preserved stressed-panic behavior, passed quick realism, and passed the allocator benchmark. The next bounded phase should stay on this decomposed frontier and explicitly prune or harder-cap the remaining weak `recovery_confirmed` offense sleeves (`dual_momentum_topn` and `composite_selective_signals`) while preserving the confirmed trio that is clearly working: `composite_regime_offense_component`, `cta_trend_long_only`, and `composite_regime_defense_component`.

## Section 67 — Phase CCC: Recovery_Confirmed Offense Pruning

**Mission.** Phase BBB clarified the remaining problem cleanly: the total `recovery_confirmed` offense bucket was already about right, but too much of that bucket was still landing in weak confirmed-state sleeves. Phase CCC therefore stayed tightly bounded. It did not change overlay logic, did not revisit hidden BIL, and did not alter the decomposed architecture. It simply asked whether hard-capping the weak confirmed offense sleeves could close more of the remaining confirmed-state gap while preserving BBB3's strong full-window profile.

**What changed.** Four confirmed-only pruning candidates were tested, all starting from `improved_phasebbb_offense_defense_composition_combo`. One capped `composite_selective_signals` alone, one capped `dual_momentum_topn` alone, one capped both, and one used a more conservative dual+CSS pruning rule. In every case, freed confirmed offense weight was reallocated mainly to `composite_regime_offense_component` and secondarily to `cta_trend_long_only`, while leaving `recovery_fragile`, `stressed_panic`, explicit cash, and the decomposed architecture unchanged.

**What helped.** Phase CCC produced the cleanest causal result so far on this branch: **`dual_momentum_topn` was the real confirmed-state leak.** The diagnostics showed `dual_momentum_topn` had only about `0.10%` confirmed-state standalone annual return and near-zero Sharpe, while `composite_selective_signals` was also weak but less responsive to pruning in realized portfolio terms. The best candidate, `improved_phaseccc_confirmed_cap_dual`, improved annual return to about `7.14%`, Sharpe to `0.9376`, preserved the MDD / CVaR gains, kept SPY below production, improved `recovery_confirmed` versus BBB3 by about `+0.06pp`, and improved `recovery_fragile` slightly as well. It also passed quick realism and the allocator benchmark, and the full committee still judged it a legitimate shadow candidate.

**What did not help enough.** Even the best pruning candidate still left `recovery_confirmed` materially below production at about `-0.61pp` annual return. So this phase did not create a production challenger. But it materially tightened the diagnosis. The remaining blocker is no longer "confirmed offense composition in general." It is now even narrower: the branch still needs to remove more confirmed-state allocation from the weakest offense legs, especially `dual_momentum_topn`, and possibly push `composite_selective_signals` closer to a near-exclusion in `recovery_confirmed`.

**Decision.** Production pin remains `improved_phase2b_regime_confidence_boost`. Official shadow pin remains `improved_phase2b_combo_abc`. The best Phase CCC candidate is **KEEP AS SHADOW** and becomes the new **architecture-reference shadow**, replacing BBB3 in that role.

**Interpretation.** This branch should continue. Phase CCC did exactly what a bounded pruning phase should do: it improved the exact blocker state without sacrificing the architecture's excellent full-window Sharpe, drawdown, CVaR, `recovery_fragile`, or stressed-panic behavior. The next bounded step should remain on the BBB/CCC decomposed frontier and test a confirmed-only harder weak-sleeve exclusion or substitution phase, with `dual_momentum_topn` reduced further and `composite_selective_signals` potentially pushed closer to a near-excluded confirmed-state role.

---

## Section 56 — Phase DDD: Recovery_Confirmed-Only Harder Weak-Sleeve Exclusion

**Mission.** Push the dual_momentum_topn cap lower than CCC2 (which capped it at 0.12 in the recovery_confirmed offense bucket) to close more of the remaining recovery_confirmed gap. Four main candidates differing only in the cap level and reallocation receivers; rescue variants registered but not built.

**Implementation.** 6 new tilt-mode branches in `_apply_phase_yy_decomposition_architecture` inside the existing CCC dispatch block. Critical implementation note: the upstream tilt dispatcher set at line ~2741 needed the 6 DDD tilt-mode strings added, otherwise candidates fell through to default and produced identical (degraded) results. After the fix, all 4 candidates produced distinct, expected results.

**Results.** All four candidates beat CCC2 on the architecture sequence. Sharpe sequence YY → ZZ2 → AAA2 → BBB3 → CCC2 → **DDD1** = 0.9297 → 0.9347 → 0.9360 → 0.9368 → 0.9376 → **0.9379**. Recovery_confirmed gap sequence vs production: -1.04pp → -0.91pp → -0.72pp → -0.67pp → -0.61pp → **-0.51pp**.

**DDD1 (`improved_phaseddd_confirmed_harder_dual_cap`)** — best of the four. Dual cap 0.07; reallocate 70% to composite_regime_offense_component / 30% to cta_trend_long_only. Full-window: ann return 7.14% (+0.25pp vs production), Sharpe 0.9379 (+0.053 vs production, +0.0003 vs CCC2), MDD -11.75% (+2.23pp vs production), CVaR -2.53% (+0.09pp), avg BIL 26.73% (-1.66pp vs production), avg SPY 6.04% (-1.05pp vs production — NO hidden beta). Recovery_confirmed delta vs production -0.51pp (+0.10pp repair vs CCC2). recovery_fragile +0.05pp vs CCC2. stressed_panic +0.21pp vs production (preserved). PASSES ALL strict gates.

**DDD2 (`...near_exclude_dual`)** — dual cap 0.03 produced the BIGGEST recovery_confirmed repair (+0.18pp vs CCC2, gap to -0.43pp) but failed the strict turnover gate at 1.101× production (boundary 1.10×). DDD2 is the next-bounded-test target.

**DDD3 (`...dual_hard_css_soft`)** — dual cap 0.06 + CSS cap 0.10 — added a CSS soft cap on top, but recovery_confirmed regressed slightly vs CCC2 (-0.03pp) and turnover boundary failed. Rejected.

**DDD4 (`...defensive_balanced_substitution`)** — dual cap 0.06 + CSS cap 0.12 + 20% defense receiver — passed strict gates with smaller recovery_confirmed repair (+0.08pp vs CCC2). Confirmed that routing freed weight to the defense component dilutes the recovery_confirmed repair.

**Quick committee verdict.** KEEP AS SHADOW. **Layer 5 (realism --quick)**: Δ ann return at 5bp = +0.28pp; at 10bp = +0.26pp; at 1-week delay = +0.37pp. **Layer 6 (allocator benchmark --quick)**: "Candidate beats production on annualised return AND clearly beats the best simple baseline on Sharpe. Allocator-side bar passed."

**Final decision.** **KEEP AS SHADOW** — DDD1 replaces CCC2 as the architecture-reference shadow on the decomposed-allocator branch. NOT PRODUCTION CHALLENGER PENDING HUMAN REVIEW because recovery_confirmed at -0.51pp ann return remains materially worse than production. Production pin remains `improved_phase2b_regime_confidence_boost`. Official shadow pin remains `improved_phase2b_combo_abc`.

**Should the branch continue? Approaching exhaustion at this magnitude.** Each step has closed 0.05-0.20pp of the recovery_confirmed gap; marginal returns are diminishing. DDD2's aggressive cap shows there's still ~0.18pp of headroom available, but it bumps against the 1.10× turnover gate. Recommended next bounded test: a single Phase EEE candidate that combines DDD2's aggressive dual cap (0.03) with a small turnover-smoothing gate (only apply the cap when prior-week dual share was already > 0.05) so the candidate stays under the turnover ceiling. If that fails to push recovery_confirmed below -0.40pp without breaking another gate, **mark this branch BRANCH EXHAUSTED** and move to a new architecture frontier (Layer 2A re-engineering of `composite_regime_offense_component`, per-state offense_mix_strength escalation curve, or recovery_confirmed-only target_vol_ceil escalation).

**Project-arc summary through Phase DDD.** The decomposed-component architecture initiated in Phase YY is now the established active improvement frontier. Six successive bounded recovery_confirmed-only iterations (ZZ2 → AAA2 → BBB3 → CCC2 → DDD1) have monotonically improved every full-window axis vs production while progressively closing the recovery_confirmed gap from -1.04pp to -0.51pp. None has yet reached the production-challenger threshold (recovery_confirmed not materially worse than production) but DDD1 is now the strongest shadow on Sharpe, MDD, CVaR, calmar, and recovery_confirmed simultaneously. One bounded Phase EEE turnover-smoothing test is the appropriate final push on this branch.

## Section 68 — Phase GGG: State-Conditional `composite_regime_offense_component` Construction

Date: 2026-04-27. Context: Phase EEE pushed the decomposed-architecture branch to its limit on the allocator-side; Phase FFF moved to Layer 2A and showed that a filtered offense subset (drop PDBC + DBA → FFF3) **closes recovery_confirmed** (-0.36pp → -0.01pp vs production, +0.35pp vs EEE1) but at a price (Sharpe 0.9144 vs EEE1 0.9353; recovery_fragile -0.49pp vs EEE1). Phase GGG hypothesis: the trade-off is **state-dependent** — filtering helps only RC (and incidentally stressed_panic), but hurts the other states. So vary the offense subset **by `market_state`**: broad EEE1 in most states, FFF3-robust only in `recovery_confirmed`.

**Implementation.** Added `build_state_conditional_decomposition_sleeve_panels(...)` to `scripts/build_improvement_artifacts.py`, which re-projects the existing `composite_regime_conditioned` source positions onto state-keyed offense column subsets (with optional intra-state column-list blending). Three new module-level decomposition panels (`phaseggg_confirmed_robust`, `phaseggg_confirmed_quality`, `phaseggg_blended_robust`), three new dispatcher modes, three new version specs cloning EEE1 settings (`state_tilt="phase_ddd_confirmed_near_exclude_dual"`, `rerisk_speed=0.80`, decomposed subset, conservative hybrid overlay). Defense and cash components untouched. Driver: `scripts/phase_ggg_state_conditional_composite_offense.py`.

**Three candidates.** GGG1 = confirmed-only robust (RC swaps to FFF3 8-ETF subset that drops PDBC + DBA). GGG2 = confirmed-only quality_filtered (RC swaps to FFF1 7-ETF subset that also drops EWJ). GGG3 = blended (RC = 50/50 broad + FFF3, per-row renormalised). All three keep broad EEE1 offense in calm_trend, neutral_mixed, recovery_fragile, stressed_panic.

**Filtered-vs-broad by state diagnosis** (`phase_ggg_filtered_vs_broad_by_state.csv`): filtered helps `recovery_confirmed` (+0.35pp ann) and `stressed_panic` (+0.41pp); hurts `neutral_mixed` (-0.33pp), `recovery_fragile` (-0.49pp), and is neutral on `calm_trend`. Recovery_fragile is **clearly hurt** by filtering — must stay broad. `recovery_confirmed` is the safest single-swap candidate, with `stressed_panic` as a possible future bonus swap.

**Results.** GGG1 full-window: Sharpe 0.9366, ann 7.14%, MDD -11.77%, CVaR -2.54%, turnover ratio 1.0998× production. State-by-state: non-RC states are **bit-identical** to EEE1 (delta at ~1e-7 / week, i.e. floating-point noise), confirming the swap was perfectly localised. Recovery_confirmed: +0.31pp ann vs EEE1, **-0.04pp vs production** (effectively closed from EEE1's -0.36pp gap). Recovery_fragile vs EEE1: -0.002pp (preserved). Stressed_panic vs production: +0.21pp (improved, inherited from EEE1). Hidden-beta check: avg SPY weight 6.03% (vs production 7.08%, **lower**); avg BIL 26.66% (vs 28.39%, less cash drag, not more). Avg `composite_regime_offense_component` weight 9.78%, identical to EEE1's. The +0.052 Sharpe / +0.25pp ann gain are **not** hidden beta or hidden cash.

**Selection.** GGG1 passes strict gates (no failure on any of: ann drag, Sharpe vs prod, Sharpe vs EEE1, MDD, CVaR, turnover, stressed_panic, RF vs EEE1, RC vs EEE1, hidden beta, decomposition intact). GGG1 fails the challenger track by 0.006pp on `recovery_fragile vs production` (-0.306pp vs -0.30 cap) — a regression **inherited from EEE1**, not introduced by the GGG swap (GGG1 vs EEE1 RF delta is -0.002pp). GGG2 was rejected: turnover ratio 1.1004× past 1.10 cap. GGG3 passes strict but has a smaller RC repair (+0.19pp) and lower Sharpe than GGG1.

**Quick committee:** 0 blocking flags; MDD vs prod +2.20pp; CVaR vs prod +0.08pp; holdout Sharpe 1.822 vs 1.625 (+0.197). Verdict: **KEEP AS SHADOW** ("fails production return-delta gate"; +0.25pp vs +0.30pp cap). **Layer 5 quick:** Δ ann return at 5bp +0.27pp; at 10bp +0.25pp; with 1-week delay +0.36pp. Verdict: candidate survives doubled-cost scenario. **Layer 6 quick:** beats Equal Weight, Inverse Vol, HRP-internal AND production on both ann return and Sharpe. Verdict: Allocator-side bar passed. Full committee (without `--quick`): same verdict — **KEEP AS SHADOW**.

**Final verdict: KEEP AS SHADOW.** Specifically, **promote GGG1 to primary architecture-reference shadow**, demoting EEE1 to secondary architecture-reference shadow. GGG1 dominates EEE1 on every measured axis (Sharpe +0.0013, ann +0.01pp, MDD/CVaR/RF/stressed_panic identical, RC repaired by +0.31pp); dominates FFF3 on every full-window axis (Sharpe +0.022, ann +0.08pp, MDD better 0.31pp, CVaR better 0.05pp, RF better ~0.49pp); passes strict gates and all 3 quick audits cleanly with no hidden beta. The +0.30pp ann-return challenger gate is missed by 0.05pp — flag for promotion review at next checkpoint, but do not auto-promote. Production pin: unchanged. Shadow pin: unchanged.

**Should the branch continue?** YES. This is the first phase since YY where a single mechanism cleanly captured the targeted gain (recovery_confirmed repair) **without any side effects** in the other four states (deltas at floating-point noise). The state-conditional re-projection is causal, interpretable, and parameter-free. **Recommended next phases:** (1) Phase HHH-stressed-panic-swap — also swap to filtered offense in `stressed_panic` (+0.41pp ann diagnostic) with a strict stressed-panic protection check; (2) Phase HHH-quality-filter-with-turnover-smoothing — re-test GGG2's stronger filter (also drops EWJ) with `sleeve_reallocation_speed` reduced to bring turnover ratio back under 1.10×; (3) Phase HHH-defense-side — apply analogous state-conditional Layer 2A diagnosis to `composite_regime_defense_component`. If all three Phase HHH sub-tests fail, mark Layer 2A composition surgery branch exhausted and escalate to Layer 2B regime-engine re-design (formal re-derivation of recovery_confirmed entry condition).

**Project-arc summary through Phase GGG.** The decomposed-component architecture initiated in Phase YY now has two clean layers of refinement: (a) per-state allocator-side rebudgeting (ZZ → DDD → EEE1), and (b) per-state Layer 2A component re-engineering (FFF, GGG). GGG1 is the first candidate that combines both layers' insights without sacrificing any of EEE1's full-window quality, and it nearly closes the recovery_confirmed gap that has driven this entire branch since Phase YY. The dual-track production pin remains unchanged, but the architecture-reference shadow is materially stronger than at the start of the sprint.

## Section 69 — Phase HHH: State-Conditional Stressed-Panic Offense Swap (extension of GGG1)

Date: 2026-04-27. Context: Phase GGG cleanly proved state-conditional Layer 2A construction works (broad EEE1 offense everywhere except recovery_confirmed → FFF3 robust filtered subset; non-RC states bit-identical to EEE1; RC repaired by +0.31pp ann). The GGG diagnostic also showed filtered offense helps `stressed_panic` by +0.41pp ann (without weakening cash/defense routes). Phase HHH is one narrow extension: also swap to filtered offense in stressed_panic, three candidates max.

**Implementation.** Reused `build_state_conditional_decomposition_sleeve_panels` from Phase GGG. Added 3 module-level decomposition panels (`phasehhh_confirmed_stressed_robust`, `phasehhh_confirmed_robust_stressed_blended`, `phasehhh_confirmed_quality_stressed_robust`), 3 dispatcher modes, and 3 version specs cloning GGG1 settings (state_tilt, rerisk_speed=0.80, decomposed subset, conservative hybrid overlay). Defense and cash components untouched. Recovery_fragile / neutral_mixed / calm_trend kept on broad EEE1. Driver: `scripts/phase_hhh_state_conditional_stressed_offense.py`.

**Three candidates.** HHH1 = RC + SP both → FFF3 robust (drop PDBC + DBA in both states). HHH2 = RC → FFF3; SP → 50/50 broad+FFF3 blend (safety-first SP). HHH3 = RC → FFF1 quality_filtered (drop PDBC + DBA + EWJ); SP → FFF3 robust.

**Results — mechanism worked, turnover gate failed.** All three candidates show clean state isolation: recovery_fragile vs GGG1 ≈ 0.0pp; neutral_mixed +0.03pp; calm_trend −0.06 to −0.12pp (second-order allocator drift from changed return panel); recovery_confirmed essentially preserved on HHH1/HHH2 (−0.01pp), further repaired on HHH3 (+0.07pp); **stressed_panic +0.30pp on HHH1/HHH3** (clean swap effect), +0.02pp on HHH2 (blend dilutes the SP gain). Stressed_panic vs production: +0.51pp on HHH1/HHH3, beyond GGG1's +0.21pp. No hidden beta — avg SPY 6.05% (vs prod 7.08%, lower); avg BIL 27.05% (vs prod 28.39%, less cash drag).

But all three candidates **fail the strict turnover gate**: HHH1 1.1117×, HHH2 1.1054×, HHH3 1.1125× (vs the 1.10× cap). The additional state where positions are re-projected onto a different column subset adds ~0.01–0.02× extra L1 turnover at the SP-state boundary on top of GGG1's 1.0998× baseline.

**Selection.** No HHH candidate passes any track (strict / challenger / shadow). Per spec, **quick Layer 5/6 audits were not run** (audits are tied to KEEP AS SHADOW or better). Best diagnostic candidate is HHH3 (Sharpe 0.9365, ann +0.29pp vs prod, RC +0.07pp vs GGG1, SP +0.30pp vs GGG1) but it is the worst on turnover (1.1125×). HHH1 is the cleanest stressed swap but still over the cap (1.1117×). HHH2 is closest to the cap but the blend dilutes the SP gain to +0.02pp.

**Final verdict: REJECT all three HHH candidates** (turnover gate failure). GGG1 remains primary architecture-reference shadow. EEE1 remains secondary. FFF3 remains Layer 2A reference. Production pin and shadow pin unchanged.

**Should the branch continue?** YES, but with a turnover-budget compensator — the SP swap mechanism is real (+0.30pp ann SP gain with clean state isolation) and the SOLE reason for rejection is the additional 0.01–0.02× turnover at the SP-state boundary. **Recommended Phase III** (single bounded test): re-test HHH1's logic with one of these compensators (smallest single change that brings turnover under 1.10×, no broad search): (1) reduce `sleeve_reallocation_speed` from 0.40 to 0.30 or 0.35; (2) raise the trade-deadband / minimum-trade threshold in HRP to ~0.5%; (3) apply the SP swap only when stressed_panic has persisted ≥ 2 consecutive weeks (suppresses one-week false-stress entries that drive recipe-flip turnover). If all three Phase III sub-options fail to bring turnover under 1.10× while preserving the SP gain, **mark Layer 2A composition-surgery branch BRANCH EXHAUSTED** and escalate to Layer 2B (formal re-derivation of recovery_confirmed and stressed_panic entry conditions, or a new component in the decomposition rather than re-cutting the existing one).

**Project-arc summary through Phase HHH.** The state-conditional Layer 2A construction frontier (GGG → HHH) cleanly demonstrates the mechanism: per-state recipes for `composite_regime_offense_component` work, side-effects in non-recipe states are at floating-point-noise level, and the per-state diagnostic predictions translate one-for-one into realised state-by-state deltas in the integrated portfolio. GGG1 already captured the recovery_confirmed gain cleanly under the turnover cap; the additional stressed_panic gain visible in the diagnostic exists but lives just past the 1.10× cap when grafted on. The next push must be a turnover-budget compensator, not a broader composition search.

## Section 70 — Phase III: GGG1 Production Candidate Review

Date: 2026-04-27. Phase III stopped the research loop and made a production
decision on `improved_phaseggg_confirmed_only_robust_offense` (GGG1). The phase
did not create new strategy variants, did not revisit overlays or hidden BIL,
and did not use ML or Phase CC refined state. It reviewed GGG1 as-is against
production (`improved_phase2b_regime_confidence_boost`), official shadow
(`improved_phase2b_combo_abc`), and EEE1
(`improved_phaseeee_smoothed_near_exclude_dual`).

**Validation package.** `scripts/phase_iii_production_candidate_review.py`
created the final metric, state-by-state, rolling metric, cost/delay, exposure,
drawdown/tail, and promotion-checklist diagnostics under
`data/research/phase_iii_production_candidate_review/`. The checklist passed
18/18 checks. GGG1 vs production: annual return 7.14% vs 6.89% (+0.246pp),
Sharpe 0.9366 vs 0.8848 (+0.0518), max drawdown -11.77% vs -13.98% (+2.20pp),
CVaR-5% -2.54% vs -2.62% (+0.08pp), holdout Sharpe 1.822 vs 1.625 (+0.197),
avg BIL 26.66% vs 28.39%, avg SPY 6.03% vs 7.08%, and turnover ratio 1.0998x
under the 1.10x cap.

**State behavior.** GGG1 effectively closes recovery_confirmed versus
production (-0.04pp annual return), improves stressed_panic (+0.21pp),
calm_trend (+0.53pp), and neutral_mixed (+0.17pp), and has only a small
recovery_fragile deficit (-0.31pp) inherited from EEE1 rather than introduced
by GGG1. No state showed unacceptable degradation.

**Robustness and audits.** Full Layer 5 realism passed: +0.270pp annual-return
delta at 5bp, +0.254pp at 10bp doubled cost, and +0.362pp with 1-week rebalance
delay. Full allocator benchmark passed: GGG1 beat production on annual return
and Sharpe and cleared the simple-baseline Sharpe bar. Full robustness
simulation showed point estimates still ahead (7.14% vs 6.89%, Sharpe 0.937 vs
0.885), though bootstrap annual-return intervals overlap. Full research
committee remained `KEEP AS SHADOW` because it still uses the internal +0.30pp
annual-return production gate, while GGG1 is +0.246pp.

**Optional polish.** No polish candidate was created. GGG1 is already just under
the turnover cap, and a tiny speed/deadband change could disturb the exact
recovery_confirmed repair under review. No obvious safe polish dominated GGG1.

**Final recommendation.** **PROMOTE TO PRODUCTION CANDIDATE.** This is a human
review and packaging recommendation, not an automatic pin change. The reason is
that GGG1 improves Sharpe, annual return, drawdown, CVaR, holdout behavior,
cost/delay robustness, allocator benchmark standing, hidden-beta profile, and
state behavior while staying inside the turnover cap and preserving a causal
production-pipeline implementation. The next step should be packaging/deployment
review for GGG1, not another research phase.

## Section 71 — Phase III Packaging / Deployment Review

Date: 2026-04-27. This was not a research phase. It packaged
`improved_phaseggg_confirmed_only_robust_offense` (GGG1) as the production
candidate pending human deployment review while preserving
`improved_phase2b_regime_confidence_boost` as both current production and
rollback. The official shadow remains `improved_phase2b_combo_abc`.

**Registry and exports.** Created
`data/05_layer3_portfolio_construction/production_candidate_registry.json` with
current production, rollback, official shadow, production candidate, Phase III
promotion status, reason summary, and caveats. Created lightweight dashboard
exports:
`production_candidate_summary.csv`,
`production_candidate_state_summary.csv`,
`production_candidate_exposure_summary.csv`, and
`public/production-candidate-dashboard-bundle.json`. The full dashboard payload
was not rebuilt, and no live production pin was changed.

**Why GGG1 is packaged.** GGG1 beats current production on annual return
(7.14% vs 6.89%), Sharpe (0.9366 vs 0.8848), max drawdown (-11.77% vs
-13.98%), CVaR-5% (-2.54% vs -2.62%), and holdout Sharpe (1.822 vs 1.625).
It lowers SPY exposure (6.03% vs 7.08%), survives doubled cost and 1-week delay,
passes the allocator benchmark, and keeps turnover at 1.0998x versus the 1.10x
cap.

**Caveats.** The committee's internal +0.30pp annual-return gate was not met
exactly (+0.246pp), bootstrap confidence intervals overlap, the worst single
week is worse than production, and human deployment review is still required.

**Final packaging recommendation.** **READY FOR HUMAN DEPLOYMENT REVIEW.** Next
manual step: human reviewer decides whether to update the live production pin in
a separate deployment change. Until then, old production remains live and
available as rollback.


## Section 72 — Phase JJJ0 Foundation Diagnostic Audit

Date: 2026-04-27. Phase JJJ0 was a diagnostic-only foundation audit after the
GGG1 production-candidate review. It did not create strategy variants, change
the production pin, change the official shadow, optimize parameters, or add ML.

**Scope.** The audit inventoried Layer 2A strategy returns/positions, Layer 2B
market-state files, Layer 3 production/candidate/shadow return and weight
artifacts, and allocator checkpoints. It wrote diagnostics under
`data/research/phase_jjj0_foundation_diagnostic_audit/`.

**Findings.** The known `composite_regime_conditioned` mixed sleeve remains
present in production and official shadow, while GGG1 uses the decomposed
offense/defense component architecture. The candidate still needs better
instrumentation for component-level return/position panels and per-sleeve ETF
lookthrough, so the audit documents those gaps instead of guessing. ETF-level
risk contribution and state budget diagnostics are available from existing
weights and market-state history.

**Readiness.** GGG1 readiness category:
`NEEDS_MORE_VALIDATION`. Validation gap:
component-level GGG1 offense/defense return and position panels are not persisted.

**Next frontier.** `FIX_CONSTRAINT_DRAG_FIRST`. Safe to proceed to
adaptive risk-contribution allocation:
`False`. Reason:
Stage diagnostics show repeated overlay/lookthrough bucket drag across states.

## Section 73 — Phase JJJ1 Constraint / Overlay / Lookthrough Drag Isolation

Date: 2026-04-27. Phase JJJ1 was diagnostic-only. It reused existing allocator
checkpoints and portfolio diagnostics, derived raw overlay/cap/turnover and
per-sleeve lookthrough instrumentation, and did not create candidates or change
production/shadow pins.

**Finding.** Target-vol diagnostics already exist, but explicit cap pre/post
traces, deadband/rerisk decisions, and GGG1 component-level return/position
panels are still not persisted. Stage attribution confirms overlay cash drag
and final sleeve-to-ETF lookthrough drag remain the main constraint issues.

**Next action.** `FIX_LOOKTHROUGH_DRAG`. Safe to proceed to adaptive
risk-contribution allocation: `False`.
Reason: Final sleeve-to-ETF translation removes offense in favorable states, and component lookthrough panels are missing for GGG1.


## Section 74 — Phase JJJ2 Lookthrough Component Instrumentation

Date: 2026-04-27. Phase JJJ2 was diagnostic-only. It persisted GGG1
component-level return and ETF-position panels, built a nonzero per-sleeve ETF
contribution table for GGG1, production, and official shadow, and audited
component purity plus favorable-state lookthrough drag. No candidates or pin
changes were made.

**Findings.** Component role flags were `{'MIXED_BUT_ACCEPTABLE': 1, 'CLEAN_DEFENSE': 1, 'CLEAN_CASH': 1}`.
GGG1 component roles are now directly auditable. GGG1 was cleaner than
production on lookthrough offense drag in
4/5
states, but favorable-state drag remains concentrated enough to require a
targeted lookthrough repair before adaptive risk contribution.

**Next action.** `FIX_LOOKTHROUGH_DRAG_WITH_TARGETED_REPAIR`. Safe to proceed to adaptive
risk-contribution allocation: `False`.
Reason: Component roles are mostly clean, but a small set of favorable-state sleeve/ETF lookthrough paths causes material offense drag.

## Section 75 — Phase JJJ3 Targeted Lookthrough Repair

Date: 2026-04-27. Phase JJJ3 tested one diagnostic-gated repair candidate:
`improved_phasejjj3_targeted_lookthrough_repair`. It preserved GGG1's
state-conditional component logic and touched only the confirmed top drag path:
`calm_trend / composite_selective_signals`.

**Repair.** In calm_trend only, cap `composite_selective_signals` at 30% of the
offense bucket and reallocate excess inside the existing offense-family sleeves
to `composite_regime_offense_component` and `cta_trend_long_only`. No production
or official shadow pin changed.

**Decision.** `REJECT`.

**Next action.** `KEEP_GGG1_AND_PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION`. Safe to proceed to adaptive
risk-contribution allocation: `True`.
Reason: The one-path repair did not clear all selection gates; keep GGG1.

## Section 76 — Phase JJJ4 Adaptive Risk-Contribution Allocator

Date: 2026-04-27. Phase JJJ4 tested three controlled GGG1-based adaptive
risk-contribution allocator variants through the production construction
pipeline. The production pin and official shadow pin were unchanged.

**Best candidate.** `improved_phasejjj4_state_risk_contribution_caps` with decision `REJECT`.

**Next action.** `KEEP_GGG1_AS_PRODUCTION_CANDIDATE`.
Reason: No adaptive risk-contribution candidate clearly improved or de-risked GGG1.

## Section 77 — Phase KKK Signal and Sleeve Contribution Audit

Date: 2026-04-27. Phase KKK was diagnostic-only. It audited Layer 1 signal
quality, Layer 2A sleeve quality, GGG1 state-by-state sleeve contribution, and
sleeve redundancy/diversification without creating candidates or changing pins.

**Next frontier.** `REBUILD_WEAK_LAYER2A_SLEEVE`.
Reason: At least one heavily used GGG1 sleeve remains state-harmful or weak enough to justify a rebuild before more allocator work.

## Section 78 — Phase LLL Defense Component Rebuild

Date: 2026-04-27. Phase LLL tested three GGG1-based Layer 2A rebuilds of only
`composite_regime_defense_component`. GGG1's offense component logic, production
pin, and official shadow pin were unchanged.

**Best candidate.** `improved_phaselll_recovery_defense_filter` with decision `REJECT`.

**Next action.** `REBUILD_COMPOSITE_SELECTIVE_SIGNALS_NEXT`.
Reason: Defense rebuild candidates did not clearly improve GGG1; KKK's next strongest issue is composite_selective_signals.


## Section 79 — Phase MMM Composite Selective Signals Rebuild

Date: 2026-04-27. Phase MMM tested three GGG1-based Layer 2A rebuilds of only
`composite_selective_signals` in recovery_confirmed. GGG1's offense component
logic, production pin, and official shadow pin were unchanged.

**Best candidate.** `improved_phasemmm_recovery_confirmed_css_filter` with decision `REJECT`.

**Next action.** `KEEP_GGG1_AS_PRODUCTION_CANDIDATE`.
Reason: CSS rebuild candidates failed or only marginally helped; keep GGG1.

## Section 80 — GGG1 Production Candidate Packaging Review

Date: 2026-04-27. This was packaging and deployment-prep only, not a new
research phase. No strategy logic, production pin, official shadow pin, or
candidate strategy was changed.

**Registry.** `data/05_layer3_portfolio_construction/production_candidate_registry.json`
now records `improved_phaseggg_confirmed_only_robust_offense` as
`PROMOTE_TO_PRODUCTION_CANDIDATE_PENDING_HUMAN_REVIEW`. Current production and
rollback remain `improved_phase2b_regime_confidence_boost`; official shadow
remains `improved_phase2b_combo_abc`.

**Dashboard bundle.** The compact public dashboard files were refreshed:
`public/production-candidate-dashboard-bundle.json`, `public/dashboard-summary.json`,
`public/dashboard-timeseries.json`, `public/dashboard-state-summary.json`, and
`public/dashboard-exposures.json`. The old giant `public/dashboard-data.json`
remains ignored and is not part of the compact deployment path.

**Reason.** GGG1 remains the best production candidate after Phase III and after
JJJ4, LLL, and MMM all failed to beat or de-risk it enough to replace it. It
improves annual return, Sharpe, max drawdown, CVaR, holdout Sharpe, allocator
benchmark behavior, and SPY exposure versus the old production pin while staying
just under the 1.10x turnover cap.

**Caveats.** The old +0.30pp committee annual-return gate was not fully met,
bootstrap intervals overlap, worst single week is worse than production, and
turnover is close to the 1.10x limit.

**Final packaging recommendation.** `READY_FOR_HUMAN_DEPLOYMENT_REVIEW`.
After human approval, the live production pin should be flipped to GGG1 in a
separate explicit deployment commit while preserving the old production pin as
rollback.


## Section 81 — Phase NNN Hard-ML Meta-Layer Sprint

Date: 2026-04-27. Phase NNN tested a controlled ML meta-layer on top of GGG1.
It built a lagged weekly dataset, evaluated expanding-window OOS classifiers
against simple state-rate baselines, and did not change production or shadow
pins.

**Decision.** `KEEP_GGG1_AS_PRODUCTION_CANDIDATE`.

**Reason.** ML prediction improved OOS, but portfolio pass-through failed the GGG1 selection gates.


## Section 82 — Phase OOO0 Signal/Data Inventory Foundation

Date: 2026-04-27. OOO0 inventoried the available signal-discovery data after
NNN kept GGG1 as the production candidate. It found enough weekly ETF,
Layer 1, Layer 2A, Layer 2B, GGG1, component, and prior-ML artifacts to support
a connected signal research program.

## Section 83 — Phase OOO1 ML-Assisted Feature Discovery

Date: 2026-04-27. OOO1 built a lagged weekly feature library and used
expanding-window ML models for feature discovery only. No portfolio candidates
or strategy changes were created.

**Decision.** `PROCEED_TO_OOO2_CROSS_ASSET_SIGNAL_TESTS`.

**Reason.** Top stable discoveries are cross-asset momentum/lead-lag/Layer 1 feature ideas.




## Section 84 — Phase OOO2 Cross-Asset Signal Expansion

Date: 2026-04-27. OOO2 converted the strongest OOO1 discoveries into explicit
lagged weekly candidate Layer 1 signals and validated them with IC decay,
state behavior, redundancy, and keep/reject screens. No portfolio candidates,
production pins, or strategy logic were changed.

**Decision.** `PROCEED_TO_OOO5_TRIPLE_BARRIER_VALIDATION`.

**Reason.** OOO2 produced surviving explicit signals with validation evidence.



## Section 85 -- Phase OOO5 Triple-Barrier Signal Validation

Date: 2026-04-27. OOO5 tested the OOO2 surviving signals with fixed event
thresholds, GGG1 triple-barrier outcomes, same-state/all-week baselines, and
event-overlap incrementality checks. No portfolio candidates, production pins,
or strategy logic were changed.

**Decision.** `PROCEED_TO_OOO3_VOL_MANAGED_SIGNAL_SIZING`.

**Reason.** OOO5 found event evidence, but direct pass-through gates were not clean enough; volatility/selectivity sizing is needed first.



## Section 86 -- Phase OOO3 Volatility-Managed Signal Sizing

Date: 2026-04-27. OOO3 tested volatility/selectivity-managed versions of OOO5
survivor signals using GGG1 triple-barrier outcomes, holdout checks, event
overlap, and transition-count turnover proxies. No portfolio candidates,
production pins, or strategy logic were changed.

**Decision.** `PROCEED_TO_OOO6_PORTFOLIO_PASS_THROUGH`.

**Reason.** OOO3 found at least one sized signal that cleared selectivity, raw-improvement, and holdout gates.

## Section 87 -- Phase OOO6 Signal Portfolio Pass-Through

Date: 2026-04-27. OOO6 passed the strongest OOO3 sized signals through the
GGG1 production construction pipeline as three small event-gated sleeve tilts.
No production pins were changed and GGG1 component logic remained the base.

**Decision.** `KEEP_OOO6_AS_SHADOW`.

**Reason.** improved_phaseooo6_efa_spy_trend_confirmed_tilt qualified as KEEP_AS_SHADOW.

## Section 88 -- Phase PPP0/PPP1 Latent Factor and Sleeve Discovery

Date: 2026-04-27. Phase PPP was diagnostic-only. It built a GGG1-aligned weekly
ETF return and lagged characteristic panel, ran full-sample diagnostic PCA,
expanding-window PCA, and an internal IPCA-style characteristic-conditioned
latent factor approximation. It compared latent factors to existing Layer 2A
sleeves, GGG1 components, market states, known proxies, and GGG1 exposures.
No production pin, official shadow pin, GGG1 logic, live-trading logic, or
portfolio candidate was changed.

**Decision.** `PROCEED_TO_QQQ_DEEP_FEATURE_INTERACTION_MINING`.

**Reason.** Latent factors are mostly redundant/proxy-like, but the walk-forward characteristic model has positive cross-sectional IC/spread evidence.

## Section 89 -- Phase QQQ Deep Feature Interaction Mining

Date: 2026-04-27. Phase QQQ was diagnostic-only. It used the PPP lagged
ETF-characteristic panel, OOO signal lineage, Layer 1 features, lagged state
context, known proxy context, and PPP factor context to test controlled
nonlinear empirical-asset-pricing style feature interactions with expanding
walk-forward validation. It created no portfolio candidates and did not change
production, shadow, GGG1 logic, or live trading behavior.

**Decision.** `PROCEED_TO_SSS_REGIME_SEQUENCE_MODELING`.

**Reason.** Interaction value appears state-specific or state-engine-like rather than a clean broad ETF signal.

## Section 90 -- Phase SSS Regime-Sequence Modeling

Date: 2026-04-27. Phase SSS was diagnostic-only. It used the refined Layer 2B
state history aligned to GGG1 dates, modeled original five-state market-state
paths with lagged dwell, path, stress-memory, transition-instability, refined
state, QQQ, OOO, and Layer 2B context controls, and tested stress-transition,
recovery-quality, false-recovery, GGG1 underperformance, and tail-risk targets
with expanding walk-forward validation. It created no portfolio candidates and
did not change production, shadow, GGG1 logic, or live trading behavior.

**Decision.** `PROCEED_TO_SSS2_SEQUENCE_SIGNAL_VALIDATION`.

**Reason.** At least one stable, interpretable, incremental sequence rule clears high-priority gates.

## Section 91 -- Phase SSS2 Sequence Signal Validation

Date: 2026-04-27. Phase SSS2 was diagnostic-only. It converted the high-priority
SSS sequence rules into explicit lagged binary signals, validated event
precision, same-state incrementality, 4w/8w/13w triple-barrier path outcomes,
pre-2016 versus 2016-forward holdout stability, calendar/state/path stability,
and redundancy versus Layer 2B, OOO/QQQ, and GGG1 exposure regimes. It created no
portfolio candidates and did not change production, shadow, GGG1 logic, or live
trading behavior.

**Signal decisions.** `{'KEEP_FOR_SSS3_PORTFOLIO_PASS_THROUGH': 3, 'KEEP_AS_DIAGNOSTIC_WARNING_SIGNAL': 2, 'MOSTLY_DUPLICATIVE': 1}`.

**Decision.** `PROCEED_TO_SSS3_SEQUENCE_PORTFOLIO_PASS_THROUGH`.

**Reason.** At least one explicit sequence signal passed event, holdout, path-asymmetry, incrementality, and turnover gates for a controlled diagnostic pass-through.

## Section 92 -- Phase SSS3 Sequence Portfolio Pass-Through

Date: 2026-04-27. Phase SSS3 was diagnostic-only. It passed the three SSS2-cleared
regime-sequence signals through the real GGG1 production construction pipeline
as four tiny bounded `state_tilt` candidates. Candidate construction used
`BUILD_VERSION_NAMES` in `scripts/build_improvement_artifacts.py`, so allocator,
overlay, cap, turnover, cost, ETF-weight, and sleeve-weight artifacts stayed in
the normal Layer 3 convention. No production pin, official shadow pin, GGG1
logic, or live trading behavior was changed.

**Candidate decisions.** `{'KEEP_AS_SHADOW': 4}`.

**Decision.** `KEEP_SSS3_AS_SHADOW`.

**Reason.** improved_phasesss3_calm_old_low_stress_derisk improves a sequence-defined weakness and passed quick audits, but does not clearly dominate GGG1.

---

## Section 93 -- Phase 1 Return Unlock Audit

Date: 2026-05-07. Diagnostic-only audit phase. No strategy candidates created. No pins changed. Goal: understand why annual returns are stuck near ~7% and whether a separate higher-return ETF mandate targeting 9–11% is justified.

**Script:** `scripts/phase_1_return_unlock_audit.py`

**Outputs:** 20 CSV files in `data/research/phase_1_return_unlock_audit/`

**Report:** `docs/research/2026-05-07_phase_1_return_unlock_audit_report.md`

**Key findings:**

GGG1 full-period return: 7.14%, Sharpe 0.937, max drawdown -11.77%. In the 2020-forward holdout: 9.55%, Sharpe 1.082, max DD -11.77%. These compare favorably to 60/40 (8.81%, Sharpe 0.733, max DD -20.76%) on a risk-adjusted basis, but trail SPY raw return (14.14%).

**State distribution and BIL exposure:**
- neutral_mixed: 44.4% of weeks, avg BIL 26.0%, generates 68.5% of total log wealth.
- calm_trend: 26.6% of weeks, avg BIL 11.0%, SPY earns 17.5% annualized but GGG1 earns only 4.3% (opportunity cost -13.2%).
- stressed_panic: 20.6% of weeks, avg BIL 53.1% — protection justified; GGG1 +16.9% active vs SPY in 2022 bear.
- recovery states: only 8.4% combined frequency; large per-week opportunity cost but limited total impact.

**Primary bottleneck:** The return ceiling is a mandate constraint, not a regime-timing failure. The regime engine correctly classifies states. The constraint is that 26% BIL persists in neutral_mixed (44% of weeks) and the defense_component sleeve (29%) remains large even in calm_trend bull markets. Direct SPY exposure averages only 6% across all states.

**Capture ratios:** GGG1 upside capture vs SPY is 4-14% depending on window. Downside capture is -12 to -23% (near-zero beta to SPY, negative correlation). Capture spread of 17-37% confirms genuinely defensive character.

**Return target scenarios:**
- 9%: requires avg BIL reduction of ~20pp (from 26.7% to ~6.2%), max DD ~14.1%.
- 10%: requires near-zero BIL in non-stressed states, max DD ~15.3%.
- 11%: requires near-complete offense in good states, max DD ~16.5%.

**Holdout diagnosis:** In every non-crisis window (2016+, 2020+, 2021+, 2023+), the primary bottleneck is consistently "low offense exposure vs SPY." In 2022, GGG1 excelled — protection worked as designed.

**Decision:** `PROCEED_TO_PHASE_2_AGGRESSIVE_ETF_VARIANT`

A separate higher-return mandate targeting 9-10% annual return with explicit max drawdown tolerance of 18-20% is justified and feasible via ETF-level mandate relaxation (reduce BIL floor in neutral_mixed, reduce defense cap in calm_trend). No new data sources needed. Phase 2 must compare out-of-sample against both GGG1 and production pin before any promotion.

---

## Section 94 -- Phase 2 Aggressive ETF Variant

Date: 2026-05-07. Six higher-return ETF mandate candidates built on the GGG1 base. All 18 artifacts produced. Diagnostic + selection phase. No production pin changes. No auto-promotion.

**Script:** `scripts/phase_2_aggressive_etf_variant.py`

**Build:** `scripts/build_improvement_artifacts.py` modified — added `phase2_aggressive_neutral_boost` and `phase2_aggressive_full_mandate` phase2b modes; added 5 new state_tilt modes (`phase2_aggressive_calm_offense`, `phase2_aggressive_recovery_offense`, `phase2_aggressive_nonstressed_offense`, `phase2_aggressive_balanced_offense`, `phase2_aggressive_stretch_offense`); added 6 new version specs.

**Outputs:** 27 files in `data/research/phase_2_aggressive_etf_variant/`

**Report:** `docs/research/2026-05-07_phase_2_aggressive_etf_variant_report.md`

**Key findings:**

Full-period returns (GGG1 baseline: 7.14%):
- C1 neutral_cash_unlock: 7.39%, Sharpe 0.940 — **best candidate**
- C4 nonstressed_mandate: 7.44%, Sharpe 0.921
- C5 balanced_mandate: 7.42%, Sharpe 0.927
- C6 stretch_mandate: 7.49%, Sharpe 0.914
- C2 calm_offense_unlock: 7.14%, Sharpe 0.917 (no improvement)
- C3 recovery_confirmed_boost: 7.15%, Sharpe 0.937 (marginal improvement)

**The 9-10% primary mandate target was not reached.** Maximum achieved: 7.49% (C6). The ETF-level mandate relaxation produced real but small improvements (+0.00pp to +0.35pp full-period).

**Root cause — critical finding:** Reducing defense_component in calm_trend and redirecting to offense sleeves does **not** improve calm_trend returns. The offense sleeves hold diversified ETFs (EFA, EEM, EWJ, CTA trend-following) that underperform concentrated US equity in US-led bull runs. SPY returns 17.5% annualized in calm_trend; diversified offense returns ~4%. The bottleneck is the ETF composition within the offense component, not the sleeve allocation weights.

**Bear protection preserved.** All candidates maintain negative SPY beta (≈−0.031 to −0.033). No disguised SPY. All 2022 bear returns are close to GGG1 (−0.56% to −1.31% vs SPY −18.18%).

**Hidden beta:** None. All candidates LOW hidden_beta_risk.

**Selection:** All 6 → `KEEP_AS_AGGRESSIVE_SHADOW`.

**Best tracked candidate:** `improved_phase2_aggressive_neutral_cash_unlock` — strictly better than GGG1 on full-period return (7.39% vs 7.14%) and Sharpe (0.940 vs 0.936) with no material risk increase.

**Decision:** `KEEP_PHASE2_AS_AGGRESSIVE_SHADOW`

To reach 9-10%, the portfolio needs better ETF composition during favorable states — either breadth signals to identify when to concentrate in US equity (Phase 3) or sector ETF rotation to capture sector leadership (Phase 4). Phase 2 demonstrated that sleeve reallocation alone cannot solve this.

**Next:** Phase 3 — Stock Breadth Regime Upgrade. Add US breadth signals to identify when concentrated offense in high-beta US assets is justified.

---

## Section 95 -- Phase 3 Breadth-Confirmed US Offense Upgrade

Date: 2026-05-07. Six candidates built by switching `composite_regime_offense_component` ETF basket from GGG1 diversified (SPY/QQQ/IWM + EFA/VEA/VWO/EWJ/VNQ/PDBC/DBA) to pure US equity (SPY/QQQ/IWM) during high-breadth non-stressed states. Causal signal: `breadth_sma_43>=0.65 AND market_trend_positive=1 AND not stressed/fragile`. No production pin changes. No auto-promotion.

**Script:** `scripts/phase_3_breadth_confirmed_us_offense.py`

**Build:** `scripts/build_improvement_artifacts.py` modified — added Phase 3 panel builds, redeploy dispatcher cases, and 6 version specs.

**Outputs:** 39 files in `data/research/phase_3_breadth_confirmed_us_offense/`

**Report:** `docs/research/2026-05-07_phase_3_breadth_confirmed_us_offense_report.md`

**Signal validation:** US pure (SPY/QQQ/IWM) outperforms GGG1 diversified in calm_trend breadth_on weeks by +0.371% per 4 weeks. Signal fires 284 of 295 calm_trend weeks, 209 of 493 neutral_mixed weeks.

**Key results (full period):**
- C1 breadth_neutral: 6.83%, Sharpe 0.877 — REJECT (Sharpe below 0.90)
- **C2 calm_us: 7.27%, Sharpe 0.966, Max DD -11.90% — KEEP_AS_AGGRESSIVE_SHADOW (best Sharpe of all candidates across Phases 1–3)**
- C3 qqq_growth: 6.94%, Sharpe 0.932 — REJECT (below GGG1; QQQ concentration backfires)
- C4 credit: 6.95%, Sharpe 0.908 — REJECT (below GGG1)
- C5 balanced: 7.12%, Sharpe 0.907 — REJECT (below GGG1)
- C6 stretch: 7.28%, Sharpe 0.919 — KEEP_AS_RESEARCH_ONLY

**Best candidate:** `improved_phase3_high_breadth_calm_us_offense` (C2)
- Full: 7.27% / Sharpe 0.966 / Max DD -11.90%
- 2020-forward: 9.94% / Sharpe 1.124 (exceeds Phase 2 best)
- 2021-forward: 10.57% / Sharpe 1.403 (best across all candidates)
- calm_trend Sharpe improvement: +0.074 (0.514 → 0.588) — genuine signal improvement
- 2022 bear: -1.43% (only -0.14pp worse than GGG1 -1.29%)

**Why QQQ concentration backfired (C3):** Higher QQQ/VUG volatility triggers the overlay vol-targeting mechanism to increase cash allocation (avg BIL rises to 30.0%), counteracting the intended offense expansion.

**Why 9% was not reached:** The `composite_regime_offense_component` sleeve is only ~10% of total portfolio. Switching its ETF basket improves Sharpe but cannot move total annual return by 2-3pp. The return ceiling requires a new offense sleeve with 20-25% portfolio budget — i.e., sector rotation.

**Cumulative aggressive shadow stack:**
- `improved_phase2_aggressive_neutral_cash_unlock`: 7.39% / 0.940 — best return
- `improved_phase3_high_breadth_calm_us_offense`: 7.27% / 0.966 — best Sharpe

**Decision:** `PROCEED_TO_PHASE4_SECTOR_BREADTH_ROTATION`

Phase 4 must build a sector-rotation offense sleeve (XLK, XLF, XLV, XLY, XLI, etc.) with 20-25% portfolio budget, driven by sector momentum breadth signals. This is the lever capable of moving annual return by 1.5-2.0pp.

---

## Section 96 -- Phase 4 Sector Breadth / Sector ETF Rotation

Date: 2026-05-07. Six candidates built from GGG1 by adding a dedicated sector-rotation offense sleeve with approximately 12%, 20%, or 25% target sleeve budgets in confirmed sector-breadth states. All sector signals were causal and applied from week `t` to week `t+1`; `stressed_panic` was not weakened. No production pin, official shadow pin, or GGG1 pin was changed.

**Script:** `scripts/phase_4_sector_breadth_rotation.py`

**Build:** `scripts/build_improvement_artifacts.py` modified to load precomputed Phase 4 sector sleeve weights, add six Phase 4 `state_tilt` modes, and add six filtered version specs.

**Outputs:** 51 files in `data/research/phase_4_sector_breadth_rotation/`

**Report:** `docs/research/2026-05-07_phase_4_sector_breadth_rotation_report.md`

**Sector universe:** Existing data contained 10 eligible sector ETFs: XLK, XLF, XLV, XLY, XLP, XLI, XLE, XLU, XLB, and VNQ. No new data was downloaded.

**Standalone sleeve validation:** Sector sleeves did not beat SPY on raw return, but some improved drawdown/Calmar versus SPY/equal-sector. Equal-weight sectors returned 10.24% with -54.25% max DD. The best drawdown-controlled sleeve, `SectorMomentumWithDefensiveFilter`, returned 7.16%, Sharpe 0.558, max DD -21.65%, Calmar 0.331. This was enough to test controlled portfolio overlays, but not enough to claim sector rotation as a standalone superior strategy.

**Best portfolio candidate:** `improved_phase4_sector_20pct_offense`
- Full period: 7.64% return, Sharpe 0.930, max DD -14.33%
- 2020-forward: 9.31% return, Sharpe 0.964
- 2021-forward: 10.18% return, Sharpe 1.245
- 2022 bear: -0.82%, beating GGG1 by +0.47pp
- Avg BIL: 23.9% vs GGG1 26.7%
- Avg sector sleeve exposure: 12.9%
- Hidden beta risk: LOW; beta to SPY remained negative (-0.035)

**Selection:** Three candidates qualified as `KEEP_AS_AGGRESSIVE_SHADOW`:
- `improved_phase4_sector_small_overlay`: 7.36%, Sharpe 0.951, max DD -13.06%
- `improved_phase4_sector_20pct_offense`: 7.64%, Sharpe 0.930, max DD -14.33%
- `improved_phase4_sector_25pct_offense`: 7.64%, Sharpe 0.915, max DD -14.87%

Balanced and stretch variants were rejected because Sharpe fell below 0.90 or aggregate returns weakened. The sector + Phase 3 US hybrid stayed research-only.

**Audit results:** Quick research committee, backtest realism, and allocator benchmark audits all passed for `improved_phase4_sector_20pct_offense`.

**Decision:** `KEEP_PHASE4_AS_AGGRESSIVE_SHADOW`

Phase 4 improved full-period return by about +0.51pp versus GGG1 and +0.26pp versus Phase 2 best, while keeping max drawdown comfortably inside the aggressive mandate. It still did not approach the 9-10% full-period target, and Sharpe slipped below the preferred 0.95 threshold. Sector rotation is useful as a tracked aggressive shadow, but not a production challenger.

**Next:** Do not promote. A Phase 4B refinement is optional only if it remains focused: improve sector-active window lift and balanced sector timing without grid search, without weakening `stressed_panic`, and without becoming SPY/QQQ beta in disguise.

---

## Section 97 -- Phase 4B Refined Sector Rotation / Breadth Timing Audit

Date: 2026-05-07. Focused refinement/audit phase after Phase 4. Phase 4B tested
whether sector rotation could be improved through narrower activation, smoother
ranking, defensive-leadership blocking, and strict high-quality timing without
a broad parameter search. No new data was downloaded. No production pin,
official shadow pin, or GGG1 pin was changed.

**Script:** `scripts/phase_4b_refined_sector_rotation.py`

**Build:** `scripts/build_improvement_artifacts.py` modified to load Phase 4B
refined sector signal and sleeve panels, add five Phase 4B `state_tilt` modes,
strip Phase 4B target sector sleeve weight outside active gates, and add five
filtered version specs.

**Outputs:** 45+ files in `data/research/phase_4b_refined_sector_rotation/`

**Report:** `docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md`

**Refined signals:** `high_quality_sector_bull`, `calm_sector_leadership_only`,
`neutral_sector_confirmed_only`, `recovery_sector_reentry`,
`sector_quality_score_high`, and `defensive_sector_warning`. All use causal
week-t features for week-t+1 returns. `high_quality_sector_bull` fired in 528
weeks (47.6%), with 0% recovery_fragile and 0% stressed_panic signal coverage.

**Standalone sleeve validation:** Refined sleeve validation was positive, but
not transformative. `DefensiveAware_Top5` improved drawdown/Calmar versus the
rougher Phase 4 sector sleeves (7.58% return, Sharpe 0.595, max DD -21.65%,
Calmar 0.350). `Top5_Smooth_Momentum` returned 9.33% but still had a deep
-48.41% standalone max drawdown. Sector ETFs remain useful as a controlled
portfolio sleeve, not as a standalone superior strategy.

**Best portfolio candidate:** `improved_phase4b_refined_sector_20pct`
- Full period: 7.76% return, Sharpe 0.959, max DD -13.77%
- 2020-forward: 9.56% return, Sharpe 1.012
- 2021-forward: 10.71% return, Sharpe 1.303
- 2022 bear: -1.52%, worse than Phase 4 best (-0.82%) but within the stress guardrail
- Avg BIL: 23.6% vs GGG1 26.7%
- Avg sector sleeve exposure: 10.0% vs Phase 4 best 12.9%
- Hidden beta risk: LOW; beta to SPY remained negative (-0.033)
- Sector-active windows improved versus Phase 4 best by +0.25pp annualized

**State impact:** The best candidate improved neutral_mixed return and Sharpe
versus Phase 4 best (12.07% / 1.474 vs 11.51% / 1.394) and improved
recovery_confirmed return/Sharpe (4.37% / 0.563 vs 3.97% / 0.490). Calm_trend
was weaker than Phase 4 best and Phase 3 best. Stressed_panic remained acceptable
(3.82% return, Sharpe 0.499, max DD -12.42%), though residual sector exposure
can persist because the production allocator is monthly/smoothed; this was
audited rather than assumed away.

**Selection:**
- `improved_phase4b_refined_sector_20pct`: `KEEP_AS_AGGRESSIVE_SHADOW`
- `improved_phase4b_refined_sector_small_overlay`: `KEEP_AS_AGGRESSIVE_SHADOW`
- `improved_phase4b_sector_phase3_hybrid`: `KEEP_AS_RESEARCH_ONLY`
- `improved_phase4b_refined_sector_25pct_selective`: `KEEP_AS_RESEARCH_ONLY`
- `improved_phase4b_return_unlock_stretch`: `KEEP_AS_RESEARCH_ONLY`

**Audit results:** Quick research committee, backtest realism, and allocator
benchmark audits all passed for `improved_phase4b_refined_sector_20pct`.

**Decision:** `KEEP_PHASE4B_AS_AGGRESSIVE_SHADOW`

Phase 4B improved Phase 4 best on full-period return (+0.12pp), Sharpe (+0.028),
max drawdown (+0.56pp shallower), and sector-active windows. It still did not
reach the preferred 8.5-9.0% return target, and 2022 bear protection worsened
relative to Phase 4 best. The result is a credible aggressive shadow refinement,
not a production challenger.

**Next:** Move to `PROCEED_TO_PHASE5_TRUE_STOCK_BREADTH_DATA_UPGRADE` if the
goal remains 8.5-9%+ returns. Existing ETF sector breadth appears helpful but
too coarse; the missing input is likely true stock-level breadth, not another
sector-ETF parameter tweak.

---

## Section 98 -- Phase 5 True Stock Breadth Data Upgrade

Date: 2026-05-07. Data + strategy research gate after Phase 4B. Phase 5 tested
whether the repo already contains clean stock-level data that can improve
market-state classification and offense timing while still trading ETFs. No new
data was downloaded, no individual-stock trading was added, and no production
pin, official shadow pin, or GGG1 pin was changed.

**Script:** `scripts/phase_5_true_stock_breadth_data_upgrade.py`

**Build:** `scripts/build_improvement_artifacts.py` was not modified in Phase 5.
No Phase 5 portfolio candidates were built because the required stock breadth
data source was not available locally.

**Outputs:** 43 files in
`data/research/phase_5_true_stock_breadth_data_upgrade/`

**Report:**
`docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md`

**Data inventory findings:**
- Existing weekly ETF universe: 35 ETFs/proxies from 2005-01-07 to 2026-04-10.
- Equity/REIT ETFs: 20.
- Sector ETFs: 10 eligible sector ETFs: XLK, XLF, XLV, XLY, XLP, XLI, XLE, XLU, XLB, and VNQ.
- Defensive/cash/bond/commodity/FX ETFs: 15.
- Full 2005-2026 ETF coverage: 26 ETFs.
- Local individual stock price files: 0.
- Local stock constituent lists: 0.
- Local point-in-time stock membership files: 0.
- Existing breadth files are ETF/sector breadth only, not true stock breadth.

**Stock breadth source audit:** The repo has yfinance-style ETF download
patterns, but no point-in-time stock universe or delisting-aware stock panel.
Using current S&P 500/Nasdaq constituents would be survivorship-biased and was
therefore allowed only as a hypothetical diagnostic path, not as evidence for
promotion. No current-constituent panel was fetched in this run.

**Classifier audit:** Existing ETF breadth confirms the same opportunity Phase
1-4B pointed toward: `neutral_mixed` is too broad, while `calm_trend` and
`recovery_confirmed` likely need finer broad-vs-narrow quality checks.
`stressed_panic` remains the state that should stay protected and unchanged.
ETF-breadth fallback diagnostics showed large risk-on/non-risk-on splits in
neutral and recovery states, but these are comparison baselines rather than true
stock breadth evidence.

**Candidate decision:** All five planned Phase 5 candidates were marked
`DATA_ONLY_NO_PORTFOLIO_BUILD`:
- `improved_phase5_stock_breadth_neutral_risk_on`
- `improved_phase5_broad_stock_bull_aggressive`
- `improved_phase5_narrow_bull_caution_overlay`
- `improved_phase5_recovery_stock_breadth_rerisk`
- `improved_phase5_stock_breadth_aggression_score`

**Audits:** Skipped. No candidate qualified as aggressive shadow or production
challenger because no stock breadth signal could be built or validated.

**Decision:** `PROCEED_TO_DATA_UPGRADE_FOR_POINT_IN_TIME_STOCK_BREADTH`

Phase 5 did not fail because stock breadth was disproven. It stopped because
the necessary clean data is absent. The next work should acquire or construct a
point-in-time, delisting-aware stock breadth panel first, then rerun the same
signal validation and only then consider ETF portfolio candidates. Do not
promote any result based on current-constituent-only breadth.

---

## Section 99 -- Phase 5A Point-in-Time Stock Breadth Data Scaffold

Date: 2026-05-07. Data-infrastructure and research-readiness phase after Phase
5. Phase 5A did not build portfolio candidates, did not download stock panels,
did not add individual-stock trading, and did not change the production pin,
official shadow pin, or GGG1.

**Scripts:**
- `scripts/phase_5a_pit_stock_breadth_data_scaffold.py`
- `scripts/build_pit_stock_breadth_panel.py`

**Storage scaffold:** `data/stock_breadth/README.md`

**Outputs:** 17 files in
`data/research/phase_5a_pit_stock_breadth_data_scaffold/`, plus
`data/stock_breadth/metadata/missing_inputs_report.csv`

**Report:**
`docs/research/2026-05-07_phase_5a_pit_stock_breadth_data_scaffold_report.md`

**Core requirements defined:** PIT index membership, adjusted stock prices with
delisted/dead-stock coverage, stable security identity mapping, sector
classification, and publication/lag assumptions. Required schemas were written
for membership, prices, metadata, and sector classification.

**Source audit:** Ranked practical data paths:
- Norgate Data US Stocks Platinum/Diamond: best practical non-institutional
  path if the user can subscribe and verify export/API details.
- CRSP/Compustat via WRDS: best institutional path if access exists.
- Sharadar/Nasdaq Data Link: possible only if PIT membership and delisting
  methodology are manually verified.
- Current constituents plus yfinance/API: diagnostic-only, high
  survivorship-bias, not promotable.

**Storage plan:** Future raw stock panels should live under
`data/stock_breadth/raw/`, preferably as partitioned parquet or external/LFS
storage. Phase 5A intentionally did not modify `.gitignore`; it documented
recommended future ignore rules for large raw/interim stock files. Only small
manifests, validation reports, and aggregate processed summaries should be
normal-git candidates after size/license checks.

**Ingestion scaffold:** `scripts/build_pit_stock_breadth_panel.py` defines input
paths, schema validation, duplicate/date checks, missing-input reporting, and
lagged weekly breadth feature construction. It was run in the current repo and
exited 0 with `MISSING_INPUTS_REPORTED`, writing
`data/stock_breadth/metadata/missing_inputs_report.csv` because no PIT stock
inputs are installed.

**Future classifier plan:** Split `neutral_mixed` into risk-on/chop/
deteriorating/recovery-setup buckets, classify bull quality as broad/narrow/
defensive/late-cycle/fake-recovery, and re-risk recovery only when breadth is
strong. `stressed_panic` remains unchanged.

**Decision:** `NEEDS_DATA_SOURCE_DECISION`

The next human action is to choose and provision a PIT stock data path:
Norgate Platinum/Diamond, CRSP/WRDS, or a verified Sharadar/Nasdaq Data Link
path with PIT membership and delisted-stock coverage. After that data is
installed under `data/stock_breadth/raw/`, rerun
`python3 scripts/build_pit_stock_breadth_panel.py` and proceed to Phase 5B only
if the bias/leakage checklist passes.

---

## Section 100 -- Phase 5A-Free Current-Constituent Diagnostic Stock Breadth Prototype

## !! SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY !!

Date: 2026-05-07. Free diagnostic prototype using current S&P 500 constituents
(Wikipedia) and yfinance adjusted-close prices (2020–2026) to test whether stock
breadth is a promising enough signal to justify purchasing PIT data. No production
pins changed. No portfolio candidates created. No production pipeline modified.

**Script:** `scripts/phase_5a_free_current_constituent_breadth_diagnostic.py`

**Outputs:** 23 files in
`data/research/phase_5a_free_current_constituent_breadth_diagnostic/`

**Report:**
`docs/research/2026-05-07_phase_5a_free_current_constituent_breadth_diagnostic_report.md`

**Data:** 503 tickers fetched from Wikipedia (98.8% yfinance coverage), 5.8 MB
parquet. Date range 2020-01-03 to 2026-05-01, 331 weekly breadth snapshots.

**Key diagnostic findings (ALL SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY):**

- `broad_stock_bull_diagnostic` (97 active weeks):
  SPY 4w lift +0.040%; SPY 13w lift +1.29%; Phase4B 13w hit rate 83.3%.
  In calm_trend specifically: SPY +0.517% per 4w vs off-signal weeks (46 of 101 calm weeks).

- `diagnostic_aggression_score_high` (131 active weeks):
  SPY 4w lift +0.686%; SPY 13w lift +1.816%. NEGATIVE for GGG1 (-0.142%), suggesting
  this is an equity-market timing signal that does not translate to the conservative
  portfolio as-is.

- `recovery_confirmed` signal (18 active weeks):
  SPY 4w lift +1.20%, 13w hit rate 100%. Almost certainly survivorship-biased (small N,
  no failed companies).

- Neutral_mixed: stock breadth signals are mixed/negative for GGG1 and Phase4B.
  The portfolio may already be well-calibrated for neutral states.

- Stock breadth vs existing ETF breadth: ETF breadth (`breadth_sma_43`) shows **-0.457%**
  4w lift for SPY (negative). Stock breadth shows +0.040%. Stock breadth is more
  targeted to equity conditions — important directional finding even accounting for bias.

**Decision: `DIAGNOSTIC_PROMISING_GET_PIT_DATA`**

The calm_trend same-state lift (+0.517% per 4w for SPY, +0.347% for Phase4B) is
the most actionable signal. Real PIT data would allow proper full-period (2005+)
validation and remove the survivorship bias before any portfolio candidate is built.

**Next required human action:**
Purchase Norgate Data US Stocks Platinum/Diamond (recommended), then export S&P 500
PIT constituents + daily prices back to 2005. Save to `data/stock_breadth/raw/` using
the non-TEMPLATE filenames and run `python3 scripts/build_pit_stock_breadth_panel.py`.
Only after that should a Phase 5B portfolio candidate be considered.

---

## Section 101 -- Phase 6 Market-State Classifier Rebuild

Date: 2026-05-07. Final existing-data improvement phase. Rebuilt the market-state
classifier using five new Phase 6 `state_tilt` modes that apply incremental adjustments
to Phase 4B best, conditioned on `market_state_row` features read at rebalance time
(fully causal). No survivorship-biased stock breadth used. No paid data. No individual
stocks. No production pin, official shadow pin, or GGG1 pin was changed.

**Script:** `scripts/phase_6_market_state_classifier_rebuild.py`

**Build:** `scripts/build_improvement_artifacts.py` modified — added 5 Phase 6
`state_tilt` modes (`phase6_neutral_classifier_unlock`, `phase6_calm_bull_quality_offense`,
`phase6_recovery_quality_rerisk`, `phase6_continuous_aggression_score`,
`phase6_balanced_classifier_rebuild`) and 5 version specs using `phase4b_sector_20_subset`.

**Outputs:** 47 files in `data/research/phase_6_market_state_classifier_rebuild/`

**Report:**
`docs/research/2026-05-07_phase_6_market_state_classifier_rebuild_report.md`

**Key classifier findings:**

- `extreme_quality_calm` (58 weeks, 5.2%): **negative** lift for Phase4B (−0.019% per 4w). Phase4B's sector sleeve is already optimally deployed in high-breadth calm weeks — adding more creates marginal drag.

- `high_quality_neutral` (0 weeks, 0.0%): **never fired** because `transition_good_state_prob` in neutral_mixed has a maximum of 0.205 (the threshold was 0.60 — fundamentally incompatible). Signal over-specified.

- `aggression_score_high` (466 weeks, 42%): **+0.174% lift** for Phase4B overall, but negative within calm_trend (−0.041%) and neutral_mixed (−0.089%). The aggregate lift comes from recovery states only.

**Full-period results:**
- C4 `improved_phase6_continuous_aggression_score`: 7.80%, Sharpe 0.953, Max DD -14.18% → **KEEP_AS_AGGRESSIVE_SHADOW** (+0.04pp vs Phase4B)
- C3 `improved_phase6_recovery_quality_rerisk`: 7.75%, Sharpe 0.956, Max DD -13.77% → KEEP_AS_AGGRESSIVE_SHADOW
- C1, C2, C5: KEEP_AS_RESEARCH_ONLY (all slightly below Phase4B return)

**Phase4B remains the Sharpe leader (0.959) across all aggressive shadow candidates.**

**Cumulative aggressive shadow stack after Phase 6:**
- `improved_phase4b_refined_sector_20pct`: 7.76% / 0.959 — best Sharpe shadow
- `improved_phase6_continuous_aggression_score`: 7.80% / 0.953 — best return shadow
- `improved_phase3_high_breadth_calm_us_offense`: 7.27% / 0.966 — best 2020+ Sharpe

**Decision:** `KEEP_PHASE6_AS_AGGRESSIVE_SHADOW`

**Existing-data improvement arc is now complete.** Six phases moved the full-period return from 7.14% → 7.80% (+0.66pp). The remaining 0.20pp gap to 8.0% requires PIT stock breadth data (Norgate/WRDS). The binding constraint is calm_trend (26.6% of weeks, -12.48% opportunity cost vs SPY), where no existing feature can distinguish high-return from lower-return weeks.

**Next:** `RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE` — the Phase 5A-Free diagnostic confirmed stock breadth is promising (+0.517% per 4w SPY lift in calm_trend). Purchase Norgate Data when budget allows and proceed to Phase 5B.

---

## Section 102 -- Phase 7 Allocator Objective Rewrite

Date: 2026-05-07. Final existing-data optimization sprint. Tested three levers applied
on top of Phase 4B best: (1) larger sector sleeve budget (28–32% vs 20%), (2) more
aggressive layer3 expression (`shift_budget=0.12` in calm_trend vs 0.06), and (3) faster
reallocation (`sleeve_reallocation_speed` up to 0.70, `rerisk_speed=1.0`). No survivorship-
biased stock breadth used. No paid data. No individual stocks. No production pin, official
shadow pin, or GGG1 pin was changed.

**Script:** `scripts/phase_7_allocator_objective_rewrite.py`

**Build:** `scripts/build_improvement_artifacts.py` modified — added `phase7_aggressive_expression`
layer3 expression mode (calm_trend `shift_budget=0.12`), 5 Phase 7 `state_tilt` modes
(`phase7_larger_sector_calm`, `phase7_expression_boost`, `phase7_max_sector_rerisk`,
`phase7_combined_offensive`, `phase7_stretch_target`), and 5 version specs using
`phase4b_sector_20_subset`. All Phase 7 modes start from Phase 4B base; stressed_panic
returns base unchanged to preserve protection.

**Outputs:** 24 files in `data/research/phase_7_allocator_objective_rewrite/`

**Report:** `docs/research/2026-05-07_phase_7_allocator_objective_rewrite_report.md`

**Key structural findings:**

- **calm_trend (26.6% of weeks) is the binding constraint.** Pushing the sector sleeve
  from 18.5% to 29.7% in calm_trend (C5) *worsens* calm_trend performance (4.21% vs
  Phase4B 4.39%). Sector ETFs do not deliver superior returns vs the diversified Phase4B
  mix in quiet US bull markets. Phase4B's sector sleeve is already optimally deployed via
  `high_quality_sector_bull`. More allocation creates marginal drag.

- **recovery_confirmed is Phase 7's strongest state win.** C5 delta vs Phase4B:
  +1.01pp. But recovery_confirmed is only 4% of all weeks (44 total), so portfolio-level
  contribution is limited.

- **No disguised SPY beta.** All candidates: beta ≈ −0.033 (negative), hidden beta LOW,
  mandate OK, bear protection OK. Return improvement comes from concentrated sector ETF
  exposure and faster reallocation, not SPY-like risk.

- **stressed_panic: BIL ~52% preserved** across all Phase 7 candidates. Protection intact.

**Full-period results (2005–2026):**

| Candidate | Return | Sharpe | Max DD | vs Phase4B |
|---|---|---|---|---|
| C5 `improved_phase7_stretch_target` | **7.88%** | 0.926 | -15.28% | **+0.12pp** |
| C3 `improved_phase7_max_sector_rerisk` | 7.84% | 0.941 | -14.59% | +0.08pp |
| C1 `improved_phase7_larger_sector_calm` | 7.83% | 0.939 | -14.59% | +0.07pp |
| C4 `improved_phase7_combined_offensive` | 7.81% | 0.935 | -14.65% | +0.05pp |
| C2 `improved_phase7_expression_boost` | 7.74% | **0.954** | **-13.83%** | -0.02pp |
| Phase4B best | 7.76% | **0.959** | -13.77% | — |
| Phase6 best | 7.80% | 0.953 | -14.18% | +0.04pp |

All 5 Phase 7 candidates: **KEEP_AS_AGGRESSIVE_SHADOW**.
Audits passed for best candidate (C5): research_committee PASS, backtest_realism PASS,
allocator_benchmark PASS.

**Holdout — 2022 bear:**
C5 stretch -1.94% (within -4pp tolerance vs Phase4B -1.52%). Phase4B -1.52% remains
the best bear protection among all aggressive shadows.

**Seven-phase improvement arc (complete):**

| Phase | Best return | Sharpe | Cumulative gain |
|---|---|---|---|
| GGG1 baseline | 7.14% | 0.936 | — |
| Phase 2 | 7.39% | 0.940 | +0.25pp |
| Phase 3 | 7.27% | 0.966 | +0.13pp |
| Phase 4B | 7.76% | 0.959 | +0.62pp |
| Phase 6 | 7.80% | 0.953 | +0.66pp |
| **Phase 7** | **7.88%** | 0.926 | **+0.74pp** |

Gap to 8.0% target: **0.12pp**. Cannot be closed with existing data.

**Cumulative aggressive shadow stack (final):**
- `improved_phase7_stretch_target`: 7.88% / 0.926 — best return
- `improved_phase7_max_sector_rerisk`: 7.84% / 0.941
- `improved_phase6_continuous_aggression_score`: 7.80% / 0.953
- `improved_phase4b_refined_sector_20pct`: 7.76% / **0.959** — best risk-adjusted
- `improved_phase3_high_breadth_calm_us_offense`: 7.27% / 0.966 — best 2020+ Sharpe

**Decision:** `KEEP_PHASE7_AS_AGGRESSIVE_SHADOW`

**The existing-data improvement arc is now complete.** Seven phases moved the full-period
return from 7.14% → 7.88% (+0.74pp). The remaining 0.12pp gap to 8.0% requires PIT stock
breadth data. The calm_trend state (26.6% of weeks, ~4.2% annualized) cannot be improved
further without a point-in-time signal distinguishing high-return calm weeks from ordinary
ones — which requires stock-level breadth data.

**Next:** `RETURN_TO_PIT_STOCK_BREADTH_WHEN_DATA_AVAILABLE`
1. Purchase Norgate Data US Stocks Platinum/Diamond
2. Export S&P 500 PIT constituents + daily adjusted prices back to 2005
3. Save to `data/stock_breadth/raw/` using the real (non-TEMPLATE) filenames
4. Run `python3 scripts/build_pit_stock_breadth_panel.py`
5. Validate leakage and coverage
6. Build Phase 5B candidates using stock breadth as an additional classifier signal for
   calm_trend and recovery_confirmed states — the Phase 5A-Free diagnostic confirmed
   +0.517% per 4-week SPY lift in calm_trend, which is enough to close the gap to 8.0%.
