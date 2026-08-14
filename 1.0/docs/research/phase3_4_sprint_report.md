# Phase 3.4 Sprint — Tail-Focused Refinement of Combo1 + Holdout Discipline

**Sprint scope:** act on Phase 3.3's verdict. Combo1 = C1a + A1g is directionally better than A on mean performance but statistically indistinguishable on tail metrics, and the Phase 3 family has never been evaluated against a pre-declared forward holdout. This sprint therefore does two things at once:

1. Test narrow, structural tail-focused refinements to Combo1 (T1, T2, T3).
2. Introduce true holdout-style evaluation discipline (H1 pre-declared forward window, H2 train/tune vs holdout separation, H3 no promotion from in-sample edge alone).

**Dual-track baselines (pinned):**
- **A (production pin):** `improved_phase2b_regime_confidence_boost`
- **F (shadow pin):** `improved_phase2b_combo_abc`
- **Research reference:** `improved_phase3_1_combo_c1a_a1g` (Combo1 = C1a + A1g)

**Phase 3.4 candidates:**
- **T1** — `improved_phase3_4_combo_fragile_guard`. Combo1 + fragile-regime-only sector-sleeve DD guard (step down sector sleeve to 0.5× when benchmark DD ≤ −5 %, to 0× when ≤ −15 %, only in `recovery_fragile`).
- **T2** — `improved_phase3_4_combo_tilt_dampened`. Combo1 + benchmark-drawdown tilt-magnitude dampener on the state-leader bound (0.75× at DD ≤ −5 %, 0.5× at DD ≤ −10 %, regardless of regime).
- **T3** — `improved_phase3_4_combo_fragile_guard_tilt_dampened`. T1 + T2 combination.

All three share Combo1's exact structure (wider state-leader tilt bound C1a, sector-gated-to-fragile+confirmed A1g) and only add tail-scoped overlays on top.

**Pre-declared holdout:** last 2 years of available weekly data → `HOLDOUT_START = 2024-04-19`, n = 104 weeks. Development / tuning window: everything from 2006-06-30 to 2024-04-12 (n = 929 weeks). Holdout was declared *before* running the variants.

---

## A. What you changed

In `scripts/build_improvement_artifacts.py`:

1. Added two tail-scoped helpers:
   - `_apply_sector_fragile_dd_guard(weights, market_state, market_state_row)` — scales `sector_rotation_with_sma_filter` weight by 0.5 at benchmark DD ≤ −5 % and 0 at ≤ −15 %, only when `market_state == "recovery_fragile"`.
   - `_dd_gradient_tilt_dampener(market_state_row)` — returns a 0.5 / 0.75 / 1.0 multiplier applied to the state-lead-tilt bound depending on benchmark DD. Not regime-scoped; driven purely by causal DD gradient.
2. Wired three new tilt modes into `apply_state_conditioned_tilt`:
   - `dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard`
   - `dynamic_risk_budget_state_leader_wider_sector_gated_tilt_dampened`
   - `dynamic_risk_budget_state_leader_wider_sector_gated_fragile_guard_tilt_dampened`
3. Extended dispatch in the main walk-forward loop so the three modes feed the same conviction_row / state_lead_tilt_row pathway as Combo1.
4. Appended three version specs (T1, T2, T3) alongside the existing Combo1 spec; identical subset, method, overlay, penalty.

New script: `scripts/phase3_4_holdout.py` — pre-declares holdout, splits weekly net returns into full-history / pre-holdout / holdout, computes per-window metrics and deltas vs A / F / Combo1, then runs a 13-week block bootstrap (2000 iter) on Sharpe, ann return, and max DD differences vs A in every window.

No change to pins. No change to Phase 2 strategy code. No new optimization. No new universe expansion.

## B. What you executed

1. Edited `scripts/build_improvement_artifacts.py` — added helpers, tilt modes, dispatch, three version specs.
2. Ran `python3 scripts/build_improvement_artifacts.py` end-to-end. All six relevant version return files now exist under `data/05_layer3_portfolio_construction/`.
3. Wrote and ran `scripts/phase3_4_holdout.py`, producing `phase3_4_holdout.json` and `phase3_4_holdout_summary.txt` under `docs/research/phase3_4_artifacts/`.
4. Verified on `portfolio_version_comparison.csv` that Combo1, T1, T2, T3 all share the same pinned A/F baselines.

**Public-research lens (brief).** Tail-scoped overlays follow the same causal-gradient logic already used by `market_drawdown_step_function` (Taleb-style conditional risk scaling). Pre-declared forward holdouts are standard practice in López de Prado (2018) for out-of-sample inference, and the 13-week block bootstrap for serial-correlation-aware inference is Politis–Romano (1994). Used only to justify methodology, not to shape variant design.

## C. Files / artifacts modified or regenerated

Modified:
- `scripts/build_improvement_artifacts.py` — helpers + three new modes + three new version specs.

New:
- `scripts/phase3_4_holdout.py`
- `docs/research/phase3_4_artifacts/phase3_4_holdout.json`
- `docs/research/phase3_4_artifacts/phase3_4_holdout_summary.txt`
- `docs/research/phase3_4_sprint_report.md` (this file)

Regenerated (pipeline rerun):
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_4_combo_fragile_guard.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_4_combo_tilt_dampened.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase3_4_combo_fragile_guard_tilt_dampened.csv`
- Corresponding `portfolio_version_sleeve_weights_*` and `portfolio_version_weights_*` files.
- All other standard downstream CSVs in `data/05_layer3_portfolio_construction/`.

Updated:
- `docs/research/project_journey.md` — Phase 3.4 section appended.

Unchanged (verified):
- `scripts/build-dashboard-data.mjs` — pins still A production, F shadow.
- Phase 2 strategy code — untouched.

## D. Core metrics table (full-history)

From `portfolio_version_comparison.csv`:

| Version | Ann Ret | Ann Vol | Sharpe | Max DD | Calmar | CVaR₅ | Turnover | BIL | Cash | Prod Score | Δ Score vs A |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **A** production | 0.0689 | 0.0779 | 0.884 | −0.1398 | 0.493 | −0.0262 | 0.0562 | 0.284 | 0.162 | 0.721 | — |
| **F** shadow    | 0.0686 | 0.0776 | 0.884 | −0.1367 | 0.502 | −0.0261 | 0.0566 | 0.286 | 0.164 | 0.700 | −0.021 |
| **Combo1** (C1a+A1g) | 0.0708 | 0.0778 | 0.910 | −0.1419 | 0.499 | −0.0263 | 0.0578 | 0.284 | 0.162 | 0.785 | **+0.065** |
| **T1** fragile guard  | 0.0705 | 0.0778 | 0.907 | −0.1419 | 0.497 | −0.0263 | 0.0575 | 0.284 | 0.162 | 0.768 | +0.047 |
| **T2** tilt dampened  | 0.0708 | 0.0779 | 0.910 | −0.1419 | 0.499 | −0.0263 | 0.0579 | 0.284 | 0.162 | 0.778 | +0.057 |
| **T3** T1 + T2        | 0.0705 | 0.0778 | 0.906 | −0.1419 | 0.497 | −0.0263 | 0.0576 | 0.284 | 0.162 | 0.743 | +0.023 |

Tail-scoped capture metrics (full-history):

| Version | Upside Cap | Downside Cap | Recovery-Fragile Cap | Recovery-Confirmed Cap | Stress-Downside Cap |
|---|---:|---:|---:|---:|---:|
| A             | 0.3243 | 0.2392 | 0.2805 | 0.3945 | 0.3059 |
| F             | 0.3231 | 0.2385 | 0.2727 | 0.3873 | 0.3106 |
| Combo1        | 0.3316 | 0.2442 | 0.3053 | 0.6812 | 0.2582 |
| T1            | 0.3303 | 0.2433 | **0.2822** | 0.6621 | 0.2582 |
| T2            | 0.3318 | 0.2445 | 0.3053 | 0.6814 | 0.2585 |
| T3            | 0.3305 | 0.2435 | **0.2822** | 0.6623 | 0.2585 |

Main observation on D: **max DD is identical at −0.1419 for Combo1 and all three T variants.** CVaR₅ is −0.0263 for all four, within a basis point. The candidates made zero measurable impact on the left-tail full-history profile. T1/T3 did shave recovery-fragile capture from 0.305 back to 0.282 — this is the only place they bit, and they bit on the return side, not the loss side.

## E. Holdout / robustness results

From `scripts/phase3_4_holdout.py` outputs.

### E.1 Window definitions (H1)

- **Full history:** 2006-06-30 to 2026-04-10, n = 1033 weeks.
- **Pre-holdout (development):** 2006-06-30 to 2024-04-12, n = 929 weeks.
- **Holdout (pre-declared):** 2024-04-19 to 2026-04-10, n = 104 weeks.

Declared before the Phase 3.4 pipeline ran. All variant code was frozen prior to inspection of holdout metrics.

### E.2 Per-window point metrics

| Window | Version | Ann Ret | Sharpe | Max DD | Calmar | CVaR₅ |
|---|---|---:|---:|---:|---:|---:|
| Full hist | A      | 0.0742 | 0.929 | −0.1398 | 0.531 | −0.0269 |
| Full hist | F      | 0.0739 | 0.928 | −0.1367 | 0.540 | −0.0268 |
| Full hist | Combo1 | 0.0763 | 0.954 | −0.1419 | 0.538 | −0.0270 |
| Full hist | T1     | 0.0760 | 0.950 | −0.1419 | 0.535 | −0.0270 |
| Full hist | T2     | 0.0763 | 0.953 | −0.1419 | 0.538 | −0.0270 |
| Full hist | T3     | 0.0760 | 0.950 | −0.1419 | 0.535 | −0.0270 |
| Pre-hold  | A      | 0.0657 | 0.822 | −0.1398 | 0.470 | −0.0275 |
| Pre-hold  | F      | 0.0653 | 0.821 | −0.1367 | 0.478 | −0.0274 |
| Pre-hold  | Combo1 | 0.0681 | 0.852 | −0.1419 | 0.480 | −0.0275 |
| Pre-hold  | T1     | 0.0677 | 0.848 | −0.1419 | 0.477 | −0.0275 |
| Pre-hold  | T2     | 0.0680 | 0.852 | −0.1419 | 0.479 | −0.0276 |
| Pre-hold  | T3     | 0.0677 | 0.848 | −0.1419 | 0.477 | −0.0276 |
| **Holdout** | **A**      | **0.1537** | **2.002** | **−0.0566** | **2.714** | **−0.0204** |
| **Holdout** | **F**      | **0.1536** | **2.014** | **−0.0553** | **2.777** | **−0.0203** |
| **Holdout** | **Combo1** | **0.1530** | **1.957** | **−0.0596** | **2.566** | **−0.0209** |
| **Holdout** | **T1**     | **0.1530** | **1.957** | **−0.0596** | **2.566** | **−0.0209** |
| **Holdout** | **T2**     | **0.1530** | **1.957** | **−0.0596** | **2.566** | **−0.0209** |
| **Holdout** | **T3**     | **0.1530** | **1.957** | **−0.0596** | **2.566** | **−0.0209** |

### E.3 Deltas vs A

| Window | Version | ΔSharpe | ΔRet | ΔMaxDD | ΔCVaR₅ | ΔCalmar |
|---|---|---:|---:|---:|---:|---:|
| Full hist | F       | −0.001 | −0.0004 | +0.0030 | +0.0001 | +0.009 |
| Full hist | Combo1  | **+0.025** | **+0.0021** | −0.0022 | −0.0001 | +0.006 |
| Full hist | T1      | +0.022 | +0.0017 | −0.0022 | −0.0001 | +0.004 |
| Full hist | T2      | +0.025 | +0.0021 | −0.0022 | −0.0001 | +0.006 |
| Full hist | T3      | +0.021 | +0.0017 | −0.0022 | −0.0001 | +0.004 |
| Pre-hold  | Combo1  | **+0.030** | **+0.0024** | −0.0022 | ≈0      | +0.009 |
| Pre-hold  | T1      | +0.026 | +0.0020 | −0.0022 | ≈0      | +0.007 |
| Pre-hold  | T2      | +0.029 | +0.0024 | −0.0022 | −0.0001 | +0.009 |
| Pre-hold  | T3      | +0.025 | +0.0020 | −0.0022 | −0.0001 | +0.007 |
| **Holdout** | **F**      | **+0.012** | −0.0001 | +0.0013 | +0.0002 | **+0.064** |
| **Holdout** | **Combo1** | **−0.045** | −0.0007 | **−0.0030** | **−0.0005** | **−0.147** |
| **Holdout** | **T1**     | **−0.045** | −0.0007 | −0.0030 | −0.0005 | −0.147 |
| **Holdout** | **T2**     | **−0.045** | −0.0007 | −0.0030 | −0.0005 | −0.147 |
| **Holdout** | **T3**     | **−0.045** | −0.0007 | −0.0030 | −0.0005 | −0.147 |

### E.4 Deltas vs Combo1 (T* only)

| Window | T1 ΔSharpe | T1 ΔDD | T2 ΔSharpe | T2 ΔDD | T3 ΔSharpe | T3 ΔDD |
|---|---:|---:|---:|---:|---:|---:|
| Full hist | −0.0035 | 0.0000 | −0.0007 | 0.0000 | −0.0042 | 0.0000 |
| Pre-hold  | −0.0039 | 0.0000 | −0.0007 | 0.0000 | −0.0046 | 0.0000 |
| **Holdout** | **0.0000** | **0.0000** | **0.0000** | **0.0000** | **0.0000** | **0.0000** |

All three T variants are **exactly identical to Combo1 on the holdout window**. Neither the fragile-DD guard nor the tilt-magnitude dampener triggered on any holdout week — the holdout period had no `recovery_fragile` weeks with benchmark DD ≤ −5 % and no weeks with benchmark DD ≤ −5 % of any regime deep enough for the dampener to matter materially.

### E.5 Holdout block bootstrap vs A (13-week blocks, 2000 iter, seed 20260419)

| Candidate vs A (holdout) | mean Δ | 95 % CI | P(cand > A) |
|---|---:|---:|---:|
| Combo1 Sharpe  | −0.036 | [−0.163, +0.055] | 0.258 |
| Combo1 AnnRet  | +0.0004 | [−0.0046, +0.0065] | 0.539 |
| Combo1 MaxDD   | −0.0007 | [−0.0039, +0.0023] | 0.520 |
| T1 Sharpe      | −0.036 | [−0.163, +0.055] | 0.258 |
| T2 Sharpe      | −0.036 | [−0.163, +0.055] | 0.258 |
| T3 Sharpe      | −0.036 | [−0.163, +0.055] | 0.258 |
| T1 MaxDD       | −0.0007 | [−0.0039, +0.0023] | 0.520 |

(T1/T2/T3 bootstrap identical to Combo1's, as expected from E.4.)

### E.6 Summary of E

- **Pre-holdout only:** Combo1 and T2 show the familiar +0.03 Sharpe edge over A. T1 / T3 shave ≈0.004 Sharpe off Combo1 for no DD benefit.
- **Holdout:** Combo1 **loses** to A on Sharpe (−0.045), Calmar (−0.147), MaxDD (worse by 0.003), and CVaR (worse by 0.0005). F slightly **beats** A on holdout (+0.012 Sharpe, +0.064 Calmar). T* candidates inherit Combo1's holdout loss because their overlays never triggered.
- **Bootstrap:** P(Combo1 beats A on holdout Sharpe) = 25.8 %, CI spans both signs; no holdout evidence Combo1 is better than A, and directional evidence suggests it is slightly worse over this 2-year window.
- **Tail impact of T1/T2/T3:** zero. Full-history MaxDD unchanged from Combo1 (−0.1419). CVaR unchanged or marginally worse. Peak-DD event sits entirely outside the fragile-state / deep-benchmark-DD cell the T1 guard targets. The tilt dampener rarely binds tighter than the existing regime multiplier.

## F. Dual-track incremental contribution summary

| Candidate | ΔSharpe vs A (pre-hold) | ΔSharpe vs A (holdout) | ΔMaxDD vs A (full) | ΔMaxDD vs Combo1 (full) | Helps standalone? | Helps in combination? |
|---|---:|---:|---:|---:|---|---|
| T1 fragile guard      | +0.026 | −0.045 | −0.0022 | 0.000 | No | No — shaves Sharpe, no DD benefit |
| T2 tilt dampened      | +0.029 | −0.045 | −0.0022 | 0.000 | Marginal | No — indistinguishable from Combo1 |
| T3 T1 + T2            | +0.025 | −0.045 | −0.0022 | 0.000 | No | No — worst of the three |
| Combo1 (reference)    | +0.030 | **−0.045** | −0.0022 | — | Pre-hold yes, holdout no | — |

Dual-track view (A and F):

- **Vs A:** no T* variant is meaningfully different from Combo1 on any full-history metric. All three inherit Combo1's negative holdout Sharpe.
- **Vs F:** F itself has the strongest holdout Sharpe among the five candidates (+2.014). F's holdout edge over A survives this 2-year window; Combo1's does not.

## G. Decision

**Classification:**
- **T1** → **Drop.** Guard never improved the left tail; small Sharpe drag vs Combo1 with no DD benefit. Null result.
- **T2** → **Research-only.** Economically near-indistinguishable from Combo1 at full history and pre-holdout; zero effect on holdout. Not worth maintaining as a separate line.
- **T3** → **Drop.** Combination of two no-ops is a slightly worse no-op.
- **Combo1** → **Downgrade research conviction.** Combo1 still satisfies the Phase 3.2 composite gate under the full pool, but under pre-declared 2-year holdout it **loses** to A on every primary metric (Sharpe, DD, CVaR, Calmar). This converts Phase 3.3's "ambiguous, pool-sensitive" verdict into a concrete negative holdout signal. Combo1 remains in the repo as a **research reference only** — not a promotion candidate.
- **A** (production) → **unchanged.** Continues as production pin.
- **F** (shadow)    → **unchanged.** Shadow pin; also slightly *outperformed* A on the holdout window, which is a mild positive update for F but not yet a pin flip (single 2-year holdout, low Sharpe-diff statistical power, F is not beating A on development).

**Promotion gates (composite, DD, CVaR, turnover, holdout):**

| Gate | T1 | T2 | T3 | Combo1 |
|---|---|---|---|---|
| Composite ≥ +0.05 vs A     | Fail (+0.047) | Pass (+0.057) | Fail (+0.023) | Pass (+0.065) |
| Max DD within 0.005 of A   | Fail (−0.0022) | Fail (−0.0022) | Fail (−0.0022) | Fail (−0.0022) |
| CVaR within 0.002 of A     | Pass           | Pass           | Pass           | Pass           |
| Turnover not worse         | Pass           | Pass           | Pass           | Pass           |
| **Holdout Sharpe ≥ A**     | **Fail**       | **Fail**       | **Fail**       | **Fail**       |

Holdout gate (H3) is now explicit and binding. No candidate promoted.

## H. Open items / next actions

1. **Structural tail problem is not in the tilt/sector overlays.** T1 and T2 proved that the two most plausible causal-gradient patches on top of Combo1 don't move the full-history tail. The remaining DD-degradation vs A (−0.002) almost certainly comes from the C1a widened state-leader bound reallocating weight *into* the sector sleeve in pre-holdout recovery-fragile episodes that preceded the 2008 / 2020 drawdowns — that is, it is structural to C1a itself, not to A1g or to a missing overlay.
2. **Next Phase 3 direction (if pursued):** directly reconsider C1a. Either narrow C1a's tilt-widening to good-state-only (strong_neutral / confirmed / calm_trend) and leave fragile at the original ±0.10 bound, or retire C1a entirely and explore a non-widened A1g-only variant. That is effectively Phase 3.5 = "which half of Combo1 actually helps?"
3. **Holdout discipline now canonical.** All future sprints must report pre-holdout Sharpe and holdout Sharpe separately, and no candidate may be promoted without ΔSharpe ≥ 0 on holdout and statistical credibility ≥ 60 % P(cand > A) on the holdout bootstrap.
4. **F warrants a closer look independently.** F's holdout Sharpe edge over A is small but consistent with its Phase 2B design rationale (combo_abc = broader sleeve diversity + softer state conditioning). A dedicated Phase 4 sprint could re-evaluate whether F should become the production pin, specifically by running a proper rolling-origin cross-validation (not just one 2-year holdout).
5. **Dashboard / narrative update:** only the `project_journey.md` Phase 3.4 section is added. No pin flip. No change to `public/dashboard-data.json`.

## I. Project journey log update

Extended `docs/research/project_journey.md` with Phase 3.4 section (structural pivot from mean-return to tail-focused refinement; introduction of pre-declared forward holdout; negative holdout signal for Combo1; all Phase 3.4 candidates dropped or research-only; pins unchanged; dashboard unchanged). Narrative is now: baseline → Phase 1 → 2A → 2B → dual-track pinning → 3 → 3.1 → 3.2 (narrow refinements) → 3.3 (robustness, pool-sensitivity) → 3.4 (tail refinement, holdout discipline, negative holdout verdict on Combo1).
