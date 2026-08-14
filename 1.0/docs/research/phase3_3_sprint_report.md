# Phase 3.3 Robustness / Validation Sprint — Is Combo1 Actually Better Than A?

**Sprint scope:** a disciplined validation of `Combo1 = C1a + A1g` against the dual-track pins. Nothing new was built, tuned, or invented. This report only answers one question: does the promotion-gate pass we saw in Phase 3.2 survive methods that remove pool sensitivity?

**Dual-track baselines (pinned):**
- **A (production pin):** `improved_phase2b_regime_confidence_boost`
- **F (shadow pin):** `improved_phase2b_combo_abc`
- **Validation target:** `improved_phase3_1_combo_c1a_a1g` (Combo1)

**Methods:**
- Rb1 — rank composite under fixed comparator sets (3-variant, 5-variant, full pool).
- Rb2 — raw-metric z-score composite with identical economic weights to the production score.
- Rb3 — 13-week block bootstrap (2000 iterations) on weekly net returns.
- Rb4 — subperiod / halves validation, plus rolling 104-week Sharpe diff.

---

## A. What you changed

- New validation script: `scripts/phase3_3_robustness.py`. It consumes existing pipeline artifacts (does **not** rerun the pipeline, does **not** mutate any strategy) and emits two files under `docs/research/phase3_3_artifacts/`:
  - `phase3_3_results.json`
  - `phase3_3_summary.txt`
- New sprint report: this file — `docs/research/phase3_3_sprint_report.md`.
- Extended project narrative: `docs/research/project_journey.md` — added Phase 3.3 section.

Dashboard, pins, pipeline code, strategy logic: **unchanged**. No variant was re-run. No composite weights were touched.

## B. What you executed

1. Wrote `scripts/phase3_3_robustness.py` — loads `portfolio_version_comparison.csv` and the weekly `portfolio_version_returns_<version>.csv` for A, F, and Combo1.
2. `python3 scripts/phase3_3_robustness.py` — runs Rb1–Rb4 end to end, ~5 s.
3. Cross-checked static metrics by reading the comparison CSV directly.

**Public research lens (brief):** block bootstrap for strategy inference (Politis–Romano 1994), composite instability in model selection (Hand 2006), and the general literature warning on rank-based composites whose ranks jiggle with pool composition (Ledoit–Wolf 2008 on Sharpe comparisons in large pools). Used only to justify choosing a 13-week block and reporting full CIs, not to shape the Combo1 result.

## C. Files / artifacts modified or regenerated

New:
- `scripts/phase3_3_robustness.py`
- `docs/research/phase3_3_artifacts/phase3_3_results.json`
- `docs/research/phase3_3_artifacts/phase3_3_summary.txt`
- `docs/research/phase3_3_sprint_report.md` (this file)

Updated:
- `docs/research/project_journey.md` (Phase 3.3 section appended)

Unchanged (verified):
- `scripts/build_improvement_artifacts.py` (no strategy edits)
- `scripts/build-dashboard-data.mjs` (pins unchanged: A production, F shadow)
- `public/dashboard-data.json` (not regenerated this sprint — no input changed)
- `data/05_layer3_portfolio_construction/*.csv` (not regenerated)

## D. Core metrics table (A, F, Combo1)

From `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv` (Phase 3.2 run; same artifacts drive Phase 3.3):

| metric | A (prod pin) | F (shadow pin) | Combo1 |
|---|---:|---:|---:|
| annual return | 6.89% | 6.86% | **7.08%** |
| annual vol | 7.79% | 7.76% | 7.78% |
| Sharpe | 0.884 | 0.884 | **0.910** |
| max drawdown | −13.98% | **−13.67%** | −14.19% |
| Calmar | 0.493 | **0.502** | 0.499 |
| CVaR 5% | −2.62% | **−2.61%** | −2.63% |
| avg weekly turnover | 0.0562 | 0.0566 | 0.0578 |
| upside capture (positive weeks) | 32.4% | 32.3% | **33.2%** |
| downside capture (negative weeks) | 23.9% | **23.9%** | 24.4% |
| recovery capture | 30.4% | 29.6% | **38.3%** |
| recovery-confirmed capture | 39.4% | 38.7% | **68.1%** |
| recovery-fragile capture | 28.1% | 27.3% | **30.5%** |
| calm capture | 43.4% | **43.5%** | 43.4% |
| stress downside capture | 30.6% | 31.1% | **25.8%** |
| avg BIL weight | 28.4% | 28.6% | **28.4%** |
| avg SPY weight | **7.08%** | **7.08%** | 6.79% |
| avg cash weight | 16.2% | 16.4% | **16.2%** |

Offense / defense / cash (from comparison diagnostics and the capture-attribution CSVs): Combo1's offensive uplift concentrates in recovery states (+29 pp recovery-confirmed, +2.5 pp recovery-fragile), it trims stress-downside capture by 4.8 pp, and it keeps calm capture and cash/BIL essentially unchanged vs A. It spends about 3 bps more gross turnover per week and takes on 0.2 pp more DD.

Bold = best of the three on that row. Combo1 wins 7 rows, A/F tie on 3 rows, A wins 2, F wins 3.

## E. Robustness results

### Rb1 — rank composite under fixed comparator sets

| comparator set | A | F | Combo1 | Δ Combo1−A |
|---|---:|---:|---:|---:|
| full pool (~70 variants, as-built) | 0.7336 | 0.7088 | 0.7884 | **+0.0548** |
| fixed 3 {A, F, Combo1} | 0.6667 | 0.6267 | 0.7067 | **+0.0400** |
| fixed 5 {A, F, Combo1, baseline_hrp_default, phase3_1_c1_widened} | 0.5960 | 0.5720 | 0.6800 | **+0.0840** |

**Key finding:** the Phase 3.2 +0.0548 gate pass was pool-sensitive. When the pool is collapsed to just the two pins plus the candidate, Combo1's lift over A drops to +0.040 — clearly **below** the +0.05 promotion gate. When the pool is broadened with two classical references, the lift jumps to +0.084. The "gate pass" was real-valued noise, not a stable signal.

### Rb2 — raw-metric z-score composite (same economic weights)

Each metric standardized across the full pool; same weights as the production composite (0.22 Sharpe + 0.16 Calmar + 0.14 |DD| + 0.10 |CVaR| + 0.12 upside + 0.10 recovery + 0.08 cash + 0.08 turnover); direction flipped where "lower is better".

| | A | F | Combo1 | Δ Combo1−A | Δ Combo1−F |
|---|---:|---:|---:|---:|---:|
| raw z-composite | +0.4398 | +0.5236 | **+0.9505** | **+0.5107** | **+0.4268** |

**Key finding:** measured on raw (non-rank) z-scores, Combo1 is clearly ahead of A by ~0.51 standard deviations and of F by ~0.43. This is not a rank artifact — the underlying metrics themselves favor Combo1 on the weighted economic priorities, dominated by Sharpe, recovery, and upside.

### Rb3 — 13-week block bootstrap (2000 iterations, weekly net returns, 2006-06 → 2026-04, n = 1 033 weeks)

| comparison | mean Δ | 95% CI | P(target > base) |
|---|---:|---:|---:|
| Sharpe: Combo1 − A | +0.028 | [−0.007, +0.065] | **0.942** |
| Sharpe: Combo1 − F | +0.029 | [−0.009, +0.067] | **0.935** |
| Annual return: Combo1 − A | +0.0023 | [−0.0008, +0.0058] | 0.923 |
| Annual return: Combo1 − F | +0.0027 | [−0.0005, +0.0061] | 0.943 |
| Max DD: Combo1 − A | +0.0008 | [−0.007, +0.014] | 0.451 |
| Max DD: Combo1 − F | −0.0008 | [−0.010, +0.013] | 0.394 |
| CVaR 5%: Combo1 − A | ≈ 0 | [−0.0006, +0.0005] | 0.437 |
| CVaR 5%: Combo1 − F | ≈ 0 | [−0.0007, +0.0004] | 0.347 |

**Key finding:**
- **Sharpe/return:** Combo1 beats A in **94% of bootstrap replicates**, which is encouraging. But the 95% CI for the Sharpe diff **straddles zero** (lower bound −0.007), so the edge is not statistically significant at the 5% level.
- **Downside risk:** Combo1 vs A is a **coin flip** on both max DD (P = 0.45) and CVaR 5% (P = 0.44). The two strategies are bootstrap-indistinguishable on downside metrics.

### Rb4 — subperiod / halves + rolling window

Calendar split at 2015-12-31 and length-matched split at 2016-05-20:

| split | pre Sharpe (A / F / C) | post Sharpe (A / F / C) | pre Δ(C−A) | post Δ(C−A) | pre Δ(C−A) DD | post Δ(C−A) DD |
|---|---|---|---:|---:|---:|---:|
| calendar_mid | 0.910 / 0.905 / 0.938 | 0.948 / 0.951 / 0.969 | +0.028 | +0.022 | +0.005 (shallower) | −0.002 (deeper) |
| half_length | 0.902 / 0.896 / 0.929 | 0.957 / 0.960 / 0.978 | +0.028 | +0.022 | +0.005 (shallower) | −0.002 (deeper) |

Rolling 104-week Sharpe(Combo1) − Sharpe(A) over the full active history:
- mean = +0.028, median = +0.025
- fraction of windows where Combo1 > A = **60.8%**
- min = −0.157, max = +0.198

**Key finding:** the Sharpe/return edge is small but consistent across both halves (~+0.025 Sharpe each way). Drawdown behavior flips sign between halves (shallower pre-2015, deeper post-2015), so no stable DD advantage. The rolling-window diagnostic says Combo1 beats A in 61% of 2-year windows — clearly better than a coin flip, but far from dominant.

### "Holdout" feasibility

A true out-of-sample holdout is not available: the same full history (2005-now) has been visible to every Phase 3 iteration, so no slice was actually held out during tuning. The subperiod-halves test in Rb4 is the best approximation we can produce without distorting the experimental setup.

### Does Combo1 robustly beat A and F?

- **Beat A robustly?** On Sharpe and return: yes in the raw-metric composite (+0.51 SD) and in 94% of bootstrap replicates, **but** the 95% CI for the Sharpe diff includes zero and the DD/CVaR comparison is a coin flip. On the fixed 3-variant rank composite the edge is only +0.04 (below the +0.05 gate).
- **Beat F robustly?** Same pattern — large raw-composite gap (+0.43 SD) and 94% bootstrap probability, but downside metrics indistinguishable.

## F. Diagnostic interpretation

**Was the earlier promotion signal mostly pool-sensitive?** Partly. The +0.0548 full-pool delta comes down to +0.040 under a strict 3-variant fixed comparator set — i.e. the gate passage itself is pool-sensitive and fails under the most conservative comparator choice. However, the *underlying* Combo1 advantage is real on raw metrics (Rb2) and on bootstrap frequencies (Rb3), just not large or rigorous enough to be statistically distinguishable from A on downside risk.

**Does Combo1 remain superior under more robust evaluation?** On Sharpe and return: yes, directionally and consistently, with 94% bootstrap probability and 61% rolling-window winners. On max DD and CVaR: no — statistically indistinguishable from A. So the honest summary is "Combo1 is a modestly better performer in means, essentially tied on tails."

**Is promotion justified now?** **No.** Under a strict dual-track rule — "incremental contribution versus both tracks before promoting" — the evidence is insufficient:
1. The rank-composite gate pass is pool-sensitive (fails under 3-variant comparator).
2. The bootstrap 95% CI for Sharpe diff includes zero.
3. Downside metrics (DD, CVaR) are bootstrap-indistinguishable.
4. One half of history shows worse Combo1 DD than A.

These are exactly the conditions CLAUDE.md warns against — "no key improvement that only helps in one fragile scoring regime."

**What is the next frontier after this?** Structural moves that target **tail risk** rather than Sharpe mean-shifts. Candidate directions for Phase 3.4+:
- A causal re-risking mechanism that shortens the state-transition tail (the Phase 3.2 R2 DD-guard is a first draft; it didn't fire here because the state engine already clears DD before re-risking — but broader variants could).
- Overlay-penalty dynamics targeting specifically `recovery_fragile` drawdown behavior, where Combo1 added 0.2 pp of DD.
- Cross-regime cash policy: the current 28.4 % average BIL is stable, but BIL deployment speed through stress → recovery is a potential structural lever that doesn't depend on sleeve mix.
- Out-of-sample holdout design: set aside ≥ 2 years (or a specific regime slice) as a true holdout before the next wave of tuning, so Phase 3.4 has a real unseen-data test available.

## G. Decision classification

**Combo1 classification:** **Conditional** (unchanged from Phase 3.2). Strong direction, insufficient rigor.
- Fails: pool-robust rank composite (fixed 3-set), statistical significance of Sharpe diff (CI straddles zero), DD/CVaR equivalence in bootstrap.
- Passes: raw-metric composite, directionally in both halves, 94% bootstrap win rate on Sharpe/return.

**Pins:**
- A (`improved_phase2b_regime_confidence_boost`) — **remains production**.
- F (`improved_phase2b_combo_abc`) — **remains shadow**.

## H. Final recommendation

1. **Keep A as official production.** The robustness evidence does not clear the bar for flipping the production pin.
2. **Keep F as official shadow.** No change.
3. **Keep Combo1 as `Conditional / research-only`.** Continue to build incremental evidence. Do not promote based on the current signal.
4. **Next sprint target (Phase 3.4):**
   - Tail-focused improvements (DD/CVaR), not Sharpe mean-shifts.
   - A true out-of-sample holdout design: freeze a 2-year or regime-specific window before tuning, evaluate only at sprint close.
   - Optionally reconsider the production composite itself: move from rank-based to a mixed rank+raw composite to eliminate pool sensitivity as a research-dependency.

## I. Project journey log update

- **File:** `docs/research/project_journey.md` (updated, not replaced).
- **Section added:** "Phase 3.3 — robustness / validation sprint", including the pool-sensitivity diagnosis, the four robustness tests (Rb1–Rb4), the explicit non-promotion conclusion, and the frontier for Phase 3.4.
- **Coverage:** the project narrative is now current through Phase 3.3, ending with the conditional-status finding on Combo1 and the pointer toward tail-focused structural work.

---

### Appendix — reproducibility

```bash
python3 scripts/phase3_3_robustness.py
```

Outputs:
- `docs/research/phase3_3_artifacts/phase3_3_results.json`
- `docs/research/phase3_3_artifacts/phase3_3_summary.txt`

Bootstrap seed: 20260418. Block length: 13 weeks. Iterations: 2000.
