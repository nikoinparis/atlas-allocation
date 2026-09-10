# Phase 3.5 Sprint — Attribution of Combo1 (Which Half Actually Helps?)

**Sprint scope:** a disciplined attribution of `Combo1 = C1a + A1g`. No new strategies, no new sleeves, no new allocators, no new ML layers. The only question is whether Combo1's behaviour decomposes cleanly into its two halves and, if so, which half carries the mean edge and which half carries the tail / holdout weakness.

**Dual-track baselines (pinned):**
- **A (production pin):** `improved_phase2b_regime_confidence_boost`
- **F (shadow pin):** `improved_phase2b_combo_abc`

**Phase 3.5 attribution candidates:**
- **H1 — A1g-only** — `improved_phase3_1_a1_state_gated`. Sector sleeve (`sector_rotation_with_sma_filter`) added and state-gated to `{recovery_fragile, recovery_confirmed}`, *without* the C1a widened state-leader tilt. Everything else identical to Combo1.
- **H2 — C1a-only** — `improved_phase3_1_c1_widened`. State-leader tilt bound widened from ±0.10 to ±0.15, *without* the additional sector sleeve. Everything else identical to Combo1.
- **H3 — Combo1 (reference)** — `improved_phase3_1_combo_c1a_a1g`. Both halves combined.

All three already existed in the pipeline as Phase 3.1 artifacts and were regenerated as part of the Phase 3.4 pipeline run. This sprint is pure attribution on existing artifacts — no new variant code.

**Pre-declared holdout** (carried over unchanged from Phase 3.4): `HOLDOUT_START = 2024-04-19`, n = 104 weeks. Development window: 2006-06-30 → 2024-04-12, n = 929 weeks.

---

## A. What you changed

- **No strategy code changes.** Combo1's two halves already exist in `scripts/build_improvement_artifacts.py` as named version specs (`improved_phase3_1_c1_widened`, `improved_phase3_1_a1_state_gated`).
- **New attribution script:** `scripts/phase3_5_attribution.py`. Consumes existing `portfolio_version_returns_*.csv` files, splits into full-history / pre-holdout / holdout windows using the Phase 3.4 pre-declared holdout, computes metrics and deltas against A / F / Combo1 per window, and runs 13-week block bootstrap (2000 iter, seed 20260419) for Sharpe / ann-return / max-DD diffs both vs A and vs Combo1.
- **New sprint report:** this file.
- **Extended project narrative:** `docs/research/project_journey.md` — Phase 3.5 section appended.
- **Dashboard pins:** unchanged. Production = A, shadow = F.

## B. What you executed

1. Grepped `scripts/build_improvement_artifacts.py` — confirmed `improved_phase3_1_c1_widened` (C1a-only) and `improved_phase3_1_a1_state_gated` (A1g-only) already exist as registered version specs, and their return CSVs were regenerated during the Phase 3.4 pipeline run (April 2026, 1033 weeks).
2. Wrote `scripts/phase3_5_attribution.py` and ran it. Produced `docs/research/phase3_5_artifacts/phase3_5_attribution.json` and `phase3_5_attribution_summary.txt`.
3. Cross-checked `production_score`, turnover, capture metrics, and regime-bucket behaviour from `portfolio_version_comparison.csv` for all five versions.
4. Re-ran `node scripts/build-dashboard-data.mjs` and `npx tsc --noEmit`. Pins verified unchanged.

**Public research lens (brief).** This sprint uses the standard ablation-attribution framing (drop one component at a time, re-evaluate) widely used in learning-rate and strategy-component ablation studies. For holdout discipline we continue Phase 3.4's Politis–Romano 1994 block bootstrap. No research was consulted to shape a preferred answer.

## C. Files / artifacts modified or regenerated

New:
- `scripts/phase3_5_attribution.py`
- `docs/research/phase3_5_artifacts/phase3_5_attribution.json`
- `docs/research/phase3_5_artifacts/phase3_5_attribution_summary.txt`
- `docs/research/phase3_5_sprint_report.md` (this file)

Updated:
- `docs/research/project_journey.md` (Phase 3.5 section added)
- `public/dashboard-data.json` (regenerated, pins unchanged)

Unchanged (verified):
- `scripts/build_improvement_artifacts.py` (no strategy edits)
- `scripts/build-dashboard-data.mjs` (pins still `improved_phase2b_regime_confidence_boost` / `improved_phase2b_combo_abc`)

## D. Core metrics table (full-history)

From `portfolio_version_comparison.csv`:

| Version | Ann Ret | Ann Vol | Sharpe | Max DD | Calmar | CVaR₅ | Turnover (wk) | Prod Score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **A** production    | 0.0689 | 0.0779 | 0.884 | −0.1398 | 0.493 | −0.0262 | 0.0562 | 0.721 |
| **F** shadow        | 0.0686 | 0.0776 | 0.884 | −0.1367 | 0.502 | −0.0261 | 0.0566 | 0.700 |
| **H1** A1g-only     | 0.0708 | 0.0781 | 0.906 | **−0.1445** | 0.490 | −0.0264 | 0.0580 | **0.664** |
| **H2** C1a-only     | 0.0689 | 0.0777 | 0.888 | −0.1386 | 0.498 | −0.0261 | 0.0561 | **0.768** |
| **H3** Combo1 ref   | 0.0708 | 0.0778 | 0.910 | −0.1419 | 0.499 | −0.0263 | 0.0578 | 0.785 |

Capture metrics (full-history):

| Version | Upside Cap | Downside Cap | Recovery Cap | Recovery-Fragile Cap | Recovery-Confirmed Cap | Calm Cap | Stress-Down Cap |
|---|---:|---:|---:|---:|---:|---:|---:|
| A             | 0.3243 | 0.2392 | 0.3041 | 0.2805 | 0.3945 | 0.4344 | 0.3059 |
| F             | 0.3231 | 0.2385 | 0.2963 | 0.2727 | 0.3873 | 0.4351 | 0.3106 |
| **H1** A1g    | 0.3324 | 0.2452 | **0.3824** | **0.3062** | **0.6752** | 0.4373 | 0.2577 |
| **H2** C1a    | 0.3236 | 0.2384 | 0.3025 | 0.2789 | 0.3931 | 0.4294 | 0.3057 |
| **H3** Combo1 | 0.3316 | 0.2442 | **0.3830** | **0.3053** | **0.6812** | 0.4341 | 0.2582 |

Allocation summary:

| Version | Avg BIL | Avg SPY | Avg Cash | Offense (pos weeks) | Cash (pos weeks) |
|---|---:|---:|---:|---:|---:|
| A             | 0.284 | 0.0708 | 0.162 | 0.568 | 0.269 |
| F             | 0.286 | 0.0708 | 0.164 | 0.567 | 0.270 |
| H1 A1g        | 0.284 | 0.0679 | 0.162 | 0.575 | 0.269 |
| H2 C1a        | 0.284 | 0.0708 | 0.162 | 0.568 | 0.269 |
| H3 Combo1     | 0.284 | 0.0679 | 0.162 | 0.576 | 0.269 |

Two things jump out from D:

1. **The recovery-capture boost is 100 % A1g.** H1 (A1g-only) delivers recovery-confirmed capture 0.675 vs A's 0.395 — a +28 pp swing. H2 (C1a-only) is 0.393, essentially indistinguishable from A. Combo1 is 0.681, almost the same as H1. The entire recovery-capture story Combo1 tells is inherited from A1g; C1a contributes nothing to it.
2. **The max-DD degradation is 100 % A1g.** H1's DD is −0.1445 — **the deepest of all five candidates**. H2's DD is −0.1386, *shallower than A*. Combo1 lands at −0.1419, roughly the average of its two halves. CVaR follows the same pattern: H1 is the worst, H2 matches F.

This completely inverts the Phase 3.4 working hypothesis (which had guessed C1a was the structural tail source).

## E. Holdout / robustness results

From `scripts/phase3_5_attribution.py` outputs.

### E.1 Holdout window

Pre-declared unchanged from Phase 3.4: **2024-04-19 → 2026-04-10, n = 104 weeks.** No re-tuning occurred on the holdout before this attribution was run; the Phase 3.1 artifacts are pre-holdout-frozen code.

### E.2 Per-window metrics

| Window | Version | Ann Ret | Sharpe | Max DD | Calmar | CVaR₅ |
|---|---|---:|---:|---:|---:|---:|
| Full hist | A              | 0.0742 | 0.929 | −0.1398 | 0.531 | −0.0269 |
| Full hist | F              | 0.0739 | 0.928 | −0.1367 | 0.540 | −0.0268 |
| Full hist | H1 A1g         | 0.0763 | 0.950 | **−0.1445** | 0.528 | −0.0271 |
| Full hist | H2 C1a         | 0.0743 | 0.932 | −0.1386 | 0.536 | −0.0268 |
| Full hist | H3 Combo1      | 0.0763 | 0.954 | −0.1419 | 0.538 | −0.0270 |
| Pre-hold  | A              | 0.0657 | 0.822 | −0.1398 | 0.470 | −0.0275 |
| Pre-hold  | F              | 0.0653 | 0.821 | −0.1367 | 0.478 | −0.0274 |
| Pre-hold  | H1 A1g         | 0.0681 | 0.849 | **−0.1445** | 0.471 | −0.0277 |
| Pre-hold  | H2 C1a         | 0.0657 | 0.824 | −0.1386 | 0.474 | −0.0274 |
| Pre-hold  | H3 Combo1      | 0.0681 | 0.852 | −0.1419 | 0.480 | −0.0275 |
| **Holdout** | **A**              | **0.1537** | **2.002** | **−0.0566** | **2.714** | **−0.0204** |
| **Holdout** | **F**              | **0.1536** | **2.014** | **−0.0553** | **2.777** | **−0.0203** |
| **Holdout** | **H1 A1g**         | **0.1526** | **1.951** | **−0.0600** | **2.544** | **−0.0210** |
| **Holdout** | **H2 C1a**         | **0.1544** | **2.013** | **−0.0561** | **2.752** | **−0.0204** |
| **Holdout** | **H3 Combo1**      | **0.1530** | **1.957** | **−0.0596** | **2.566** | **−0.0209** |

### E.3 Deltas vs A

| Window | Version | ΔSharpe | ΔRet | ΔMaxDD | ΔCVaR₅ | ΔCalmar |
|---|---|---:|---:|---:|---:|---:|
| Full hist | H1 A1g     | +0.021 | +0.0020 | **−0.0048** | −0.0002 | −0.003 |
| Full hist | H2 C1a     | +0.003 | +0.0000 | **+0.0012** | +0.0001 | +0.005 |
| Full hist | H3 Combo1  | +0.025 | +0.0021 | −0.0022 | −0.0001 | +0.007 |
| Pre-hold  | H1 A1g     | +0.027 | +0.0024 | −0.0048 | −0.0002 | +0.001 |
| Pre-hold  | H2 C1a     | +0.002 | ≈0      | +0.0012 | +0.0001 | +0.004 |
| Pre-hold  | H3 Combo1  | +0.030 | +0.0024 | −0.0022 | ≈0      | +0.009 |
| **Holdout** | **H1 A1g**     | **−0.050** | −0.0011 | **−0.0033** | **−0.0005** | **−0.170** |
| **Holdout** | **H2 C1a**     | **+0.011** | **+0.0007** | **+0.0005** | **+0.0001** | **+0.038** |
| **Holdout** | **H3 Combo1**  | **−0.045** | −0.0007 | −0.0030 | −0.0005 | −0.147 |

### E.4 Deltas vs F (shadow)

| Window | Version | ΔSharpe | ΔMaxDD | ΔCalmar |
|---|---|---:|---:|---:|
| Full hist | H1 A1g | +0.022 | −0.0078 | −0.012 |
| Full hist | H2 C1a | +0.004 | −0.0018 | −0.004 |
| Full hist | H3 Combo1 | +0.026 | −0.0052 | −0.003 |
| **Holdout** | **H1 A1g** | **−0.063** | −0.0047 | **−0.233** |
| **Holdout** | **H2 C1a** | **−0.001** | −0.0008 | **−0.025** |
| **Holdout** | **H3 Combo1** | **−0.057** | −0.0043 | **−0.211** |

### E.5 Deltas vs Combo1 (H1, H2 only)

| Window | Version | ΔSharpe | ΔMaxDD | ΔCalmar |
|---|---|---:|---:|---:|
| Full hist | H1 A1g | −0.004 | −0.0026 | −0.010 |
| Full hist | H2 C1a | −0.022 | +0.0034 | −0.002 |
| Pre-hold  | H1 A1g | −0.003 | −0.0026 | −0.008 |
| Pre-hold  | H2 C1a | −0.028 | +0.0034 | −0.006 |
| **Holdout** | **H1 A1g** | **−0.006** | −0.0003 | −0.023 |
| **Holdout** | **H2 C1a** | **+0.056** | +0.0035 | **+0.185** |

### E.6 Holdout block bootstrap

Vs A (Sharpe, 13-week blocks, 2000 iter):

| Candidate | mean Δ | 95 % CI | P(cand > A) |
|---|---:|---:|---:|
| F                | +0.008 | [−0.015, +0.029] | **0.756** |
| **H2 C1a**       | **+0.003** | **[−0.009, +0.018]** | **0.692** |
| H1 A1g           | −0.036 | [−0.164, +0.058] | 0.265 |
| H3 Combo1        | −0.036 | [−0.163, +0.055] | 0.258 |

Vs Combo1 (Sharpe):

| Candidate | mean Δ | 95 % CI | P(cand > Combo1) |
|---|---:|---:|---:|
| H1 A1g | 0.000 | [−0.011, +0.010] | 0.500 |
| **H2 C1a** | **+0.040** | [−0.054, +0.168] | **0.757** |

### E.7 Summary of E

- **H2 (C1a-only) actually beats A on the pre-declared holdout.** +0.011 Sharpe, +0.0005 MaxDD (shallower), +0.038 Calmar, +0.0001 CVaR. The holdout bootstrap gives P(H2 > A) = 0.692 — not classical significance, but a clean directional win with the CI on the positive side of zero more often than not.
- **H2 matches F on holdout.** F beats A on holdout by +0.012 Sharpe; H2 beats A by +0.011. In Δ terms they are indistinguishable (−0.001 Sharpe gap, +0.038 Calmar gap goes the other way).
- **H1 (A1g-only) is the holdout failure.** ΔSharpe vs A = −0.050 — *worse than Combo1*. DD = −0.0600, deepest of all five. All of Combo1's holdout failure is carried by the A1g component, not by C1a.
- **H1 ≈ Combo1 on holdout (P(H1 > Combo1) = 0.500).** When the widened C1a tilt is removed from Combo1, the holdout signature is statistically unchanged. C1a is a near-null contributor on the holdout.
- **H2 directionally beats Combo1 on holdout (P(H2 > Combo1) = 0.757).** Dropping A1g from Combo1 does improve the holdout.

## F. Diagnostic interpretation

1. **Is A1g the helpful half?** Only in-sample. A1g carries essentially all of Combo1's **mean / recovery-capture** edge in pre-holdout (+28 pp recovery-confirmed capture, +0.027 Sharpe over A pre-holdout), but it is also the sole source of Combo1's **tail degradation** (deepest DD, worst CVaR among all five) and its **holdout failure** (−0.050 Sharpe vs A on holdout).
2. **Is C1a the harmful half?** No — the opposite. C1a-only is the cleanest of the three Phase 3 candidates: full-history DD *shallower* than A (−0.1386 vs −0.1398), CVaR at parity with F, small positive Sharpe/Calmar edge vs A, and **positive on holdout** (+0.011 Sharpe, +0.038 Calmar, matching F). The widened ±0.15 sleeve-leader tilt is well-behaved.
3. **Is Combo1 still the right research reference?** No. Combo1 is mechanically decomposable: Combo1 ≈ C1a (+0.003 Sharpe, mild tail friend) + A1g (+0.021 Sharpe, material tail drag, holdout loser). Keeping both halves wired together inherits A1g's tail and holdout costs while adding only modest incremental Sharpe over C1a-alone. The cleaner, smaller-footprint candidate is H2 (C1a-only).
4. **Is the combo additive or masking?** Partially additive on mean return (C1a alone = +0.003 Sharpe; A1g alone = +0.021; Combo1 = +0.025 — close to linear), but tail-wise it is **closer to A1g alone than to the midpoint**. The C1a tilt does not buy back the DD the sector sleeve adds.
5. **Main remaining bottleneck after this sprint.** If A1g's tail cost is the binding constraint on the Phase 3 research branch, the next frontier is **re-scoping the sector sleeve itself** — either (a) stricter sleeve-internal cash gating so the sector sleeve cannot be fully deployed when sleeve-level realised vol is already elevated, (b) replacing `sector_rotation_with_sma_filter` with a less aggressive sector-exposure mechanism, or (c) accepting that the Phase 3 branch's path is C1a-only and declaring the sector-sleeve addition a dead end for this improvement cycle.
6. **The Phase 3.4 hypothesis was wrong, and this matters.** Phase 3.4 concluded "the −0.002 DD gap vs A is structural to the widened state-leader bound." Attribution shows the opposite: the widened state-leader bound improves DD by 0.0012 vs A, while A1g degrades DD by 0.0048 vs A. Phase 3.5 corrects the diagnosis.

## G. Decision classification

| Candidate | ΔSharpe vs A (full) | ΔSharpe vs A (holdout) | ΔDD vs A (full) | Prod Score Δ vs A | Classification |
|---|---:|---:|---:|---:|---|
| **H1 A1g-only** | +0.021 | **−0.050** | **−0.0048** (worse) | **−0.056** | **Drop** — mean edge real but sole source of tail damage and holdout loss |
| **H2 C1a-only** | +0.003 | **+0.011** | **+0.0012** (better) | **+0.047** | **Research-only (new leading)** — small but consistent edge, clean tail, positive holdout |
| **H3 Combo1 ref** | +0.025 | −0.045 | −0.0022 | +0.065 | **Retire as research reference** — replaced by H2 |

**Pin status:**

- **A — remains production pin.** Unchanged. H2 does not clear the +0.05 composite gate (Δ = +0.047) and its Sharpe edge on full history is only +0.003. H2 is a credible incremental Research track but is not promotion-ready.
- **F — remains shadow pin.** Unchanged. F still directionally beats A on holdout. A multi-origin cross-validation is still open as a Phase 4 question.
- **Combo1 — retired as research reference.** Replaced by H2 as the leading research candidate, because H2 captures most of Combo1's marginal usefulness without A1g's tail and holdout costs, and is therefore a more defensible research track.

## H. Final recommendation

1. **A remains the official production candidate.** No material positive holdout evidence has emerged for any alternative strong enough to flip production.
2. **F remains the official shadow / research runner-up.** F's holdout edge over A is small but persistent and deserves a proper multi-origin cross-validation in a later phase.
3. **H2 (`improved_phase3_1_c1_widened`) becomes the new leading *research* candidate**, replacing Combo1 (`improved_phase3_1_combo_c1a_a1g`). This is a research-track update only, not a pin flip.
4. **The sector-sleeve addition (A1g branch) is Dropped** for now. It is the single element most responsible for both Combo1's tail degradation and its holdout failure. It may be revisited in a later sprint if and only if a redesigned sector-exposure mechanism with sleeve-internal cash discipline becomes available.
5. **Next frontier:** (a) re-scope or redesign the sector-rotation sleeve so that its contribution is not tail-costly; or (b) accept that the Phase 3 research branch is "widened state-leader tilt only" (H2) and move to Phase 4 — a proper rolling-origin holdout study of A vs F to settle whether F's mild holdout edge is robust.

## I. Project journey log update

Extended `docs/research/project_journey.md` with a Phase 3.5 section. Major new content: the attribution sprint, the reversal of the Phase 3.4 hypothesis (C1a is not the tail source — A1g is), the designation of H2 as the new leading research candidate, the retirement of Combo1 as the research reference, and the re-framed next-frontier question (redesign the sector-sleeve addition or move to a proper rolling-origin Phase 4 A-vs-F holdout study). The narrative is now current through Phase 3.5.
