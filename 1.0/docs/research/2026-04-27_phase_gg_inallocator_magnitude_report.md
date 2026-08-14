# Phase GG — Magnitude Test for Phase CC Hint Integration (Last Test in Branch)

**Date:** 2026-04-27
**Phase type:** Final magnitude test for the Phase CC `defensive_overlay_hint` consumption branch; runs INSIDE production's own construction path
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

Three minimal additive edits to `scripts/build_improvement_artifacts.py` on top of the Phase FF integration:

1. **Refactored the Phase FF / GG tilt branch** to look up the offensive-sleeve scale-down magnitude from a per-tilt-mode dictionary (`PHASE_HINT_TILT_MAGNITUDES`) instead of the previously-hardcoded 0.95 multiplier. The four tilt modes now share the same gate-evaluation code with different magnitudes:
   - `dynamic_risk_budget_phaseff_light` → 0.05 (existing)
   - `dynamic_risk_budget_phaseff_state_gated` → 0.05 (existing)
   - `dynamic_risk_budget_phasegg_10` → **0.10 (new)**
   - `dynamic_risk_budget_phasegg_15` → **0.15 (new)**
2. **Added two new version specs** at the end of `version_specs`:
   - `improved_phasegg_hint_inallocator_10` (state_tilt = `dynamic_risk_budget_phasegg_10`)
   - `improved_phasegg_hint_inallocator_15` (state_tilt = `dynamic_risk_budget_phasegg_15`)
   Otherwise identical to production (same `subset_sleeves`, `overlay_variant`, `overlay_penalty_mode`, `phase2b_mode`, `target_vol_ceil`, etc.)

3. **No new tilt branch was added** — the existing Phase FF branch from the prior phase is now magnitude-parameterised. Production's `dynamic_risk_budget` tilt mode is unchanged.

A thin driver `scripts/phase_gg_inallocator_hint_magnitude.py` invokes the production construction path with `BUILD_VERSION_NAMES` set to the two GG candidates plus production, then applies the 7-gate selection rule and computes a final retire-or-continue branch decision.

## B. What was executed

```
python scripts/phase_gg_inallocator_hint_magnitude.py
python scripts/research_committee_report.py improved_phasegg_hint_inallocator_10 --quick
```

Per spec, Layer 5 realism (`backtest_realism_audit.py --quick`) and Layer 6 allocator benchmark (`allocator_benchmark_audit.py --quick`) were **NOT run**, because the gating condition ("KEEP AS SHADOW **with positive neutral_deteriorating delta**") is not met — the delta is negative (-0.000003/wk for GG1, -0.000005/wk for GG2). Layer 4 market intelligence and Layer 3 macro feature audits were also skipped per spec.

## C. Files / artifacts modified or regenerated

Code (created / edited):
- `scripts/phase_gg_inallocator_hint_magnitude.py` (new — driver)
- `scripts/build_improvement_artifacts.py` — two additive edits (parameterise existing Phase FF/GG tilt branch + append two new version specs)

Data (created in `data/05_layer3_portfolio_construction/` via the production pipeline):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasegg_hint_inallocator_10.csv`
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasegg_hint_inallocator_15.csv`
- `phase_gg_candidate_metrics_full.csv`
- `phase_gg_state_summary.csv`
- `phase_gg_selection_table.csv`
- `phase_gg_protocol.json`

Reports (created):
- `reports/research_committee/improved_phasegg_hint_inallocator_10_audit.md`

Docs:
- `docs/research/2026-04-27_phase_gg_inallocator_magnitude_report.md` (this file)
- `docs/research/project_journey.md` — Section 46 appended

## D. Candidate metrics

```
                                    name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_turnover  avg_BIL  avg_SPY
    improved_phasegg_hint_inallocator_10           0.0686       0.8785            -0.1408      -0.0263        0.1125   0.2840   0.0709
    improved_phasegg_hint_inallocator_15           0.0685       0.8782            -0.1409      -0.0263        0.1125   0.2841   0.0709
improved_phase2b_regime_confidence_boost           0.0689       0.8848            -0.1398      -0.0262        0.1124   0.2839   0.0708
              improved_phase2b_combo_abc           0.0686       0.8840            -0.1367      -0.0261        0.1130   0.2856   0.0708
```

### Magnitude scaling (Phase FF → GG1 → GG2)

| magnitude | ann return | Sharpe | MDD | CVaR-5% | turnover | avg BIL | Δ in `neutral_deteriorating` |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 5pp (Phase FF) | 6.86% | 0.879 | -14.08% | -2.63% | 0.1125 | 28.38% | -0.000001/wk |
| 10pp (GG1) | 6.86% | 0.878 | -14.08% | -2.63% | 0.1125 | 28.40% | -0.000003/wk |
| 15pp (GG2) | 6.85% | 0.878 | -14.09% | -2.63% | 0.1125 | 28.41% | -0.000005/wk |
| production | 6.89% | 0.885 | -13.98% | -2.62% | 0.1124 | 28.39% | — |

**The signal is monotonic, small, and unambiguously negative.** As magnitude increases:
- ann return drops by ~0.01pp per 5pp of magnitude (small, ~negligible)
- Sharpe drops by ~0.0003 per 5pp of magnitude
- MDD worsens by ~0.01pp per 5pp of magnitude
- the per-week delta in `neutral_deteriorating` becomes more negative monotonically (-0.000001 → -0.000003 → -0.000005)
- BIL exposure rises by ~0.01pp per 5pp of magnitude

### State-by-state delta vs production (refined_state, GG1)

```
                state  n_weeks  delta_mean_wkly  gg_minus_prod_cumulative
            calm_trend  295        -0.000015                -0.567%
 neutral_deteriorating  171        -0.000003                -0.063%
       neutral_healthy  210        -0.000016                -0.641%
         neutral_mixed  112        +0.000023                +0.269%
   recovery_confirmed   44        -0.000003                -0.016%
     recovery_fragile   49        -0.000014                -0.071%
        stressed_panic  229        -0.000000                -0.015%
```

The non-gate-state deltas are essentially identical to Phase FF
(reconstruction fidelity is preserved through the production pipeline).
Only the gate state (`neutral_deteriorating`) shows a monotonic
worsening with magnitude.

## E. Best candidate

**Best diagnostic candidate:** `improved_phasegg_hint_inallocator_10`
(slightly less harmful than GG2; both fail the selection rule).

**Selection-rule outcome:** NO Phase GG candidate passes all 7 gates.
Failures (GG1):
- `sharpe_imp<0.005 (-0.0063)` — FAILS
- `underperforms in neutral_deteriorating (Δ=-0.000003/wk)` — FAILS
The other 5 gates pass (drag 0.03pp, MDD -0.10pp, CVaR -0.013pp, turnover 1.0009×, BIL +0.01pp).

## F. Quick verdict

**Quick committee verdict (Layer 2):** **KEEP AS SHADOW (research reference)** — the Layer 2 Research Committee says GG1 "is competitive on risk-adjusted axes but does not pass the production return-delta gate."

**Per-spec gate for Layer 5/6 audits:** The spec says "Only if quick committee gives PASS_TO_FULL_AUDIT or KEEP AS SHADOW **with positive neutral_deteriorating delta**, run [realism + allocator]." GG1's `neutral_deteriorating` delta is -0.000003/wk (negative). So the Layer 5 + Layer 6 audits are **not run** — saves token budget without changing the decision.

## G. neutral_deteriorating delta

- GG1 (10pp): **-0.000003/wk** (≈ -0.016% annualised; cumulative -0.063% over 171 weeks)
- GG2 (15pp): **-0.000005/wk** (≈ -0.026% annualised; cumulative -0.105% over 171 weeks)

Both are negative, and the magnitude scaling shows that increasing the
intervention size makes the candidate MORE harmful in the targeted
state, not less.

## H. Did the stronger magnitude improve anything?

**No.** The full magnitude grid (Phase FF 5pp → GG1 10pp → GG2 15pp) is
monotonically harmful:

- Sharpe: production 0.885 → FF 0.879 → GG1 0.878 → GG2 0.878 (monotonic worsening)
- ann return: 6.89% → 6.86% → 6.86% → 6.85% (monotonic worsening)
- neutral_deteriorating Δ/wk: 0 (production) → -0.000001 → -0.000003 → -0.000005 (monotonic worsening)
- MDD: -13.98% → -14.08% → -14.08% → -14.09% (monotonic worsening)

The signed direction of the magnitude effect is consistent across every
metric: *more tilt = more harm*. There is no magnitude in the tested
range at which the candidate beats production on any axis the selection
rule cares about.

## I. Should the Phase CC hint-consumption branch continue or be retired?

**RETIRE.** This is the third consecutive in-allocator magnitude (after
Phase FF's 5pp) and the second magnitude tested in Phase GG (10pp and
15pp), all run inside the production pipeline so reconstruction fidelity
is not the issue. The marginal effect of an offensive-sleeve scale-down
on Phase CC gate weeks is monotonically negative across magnitudes 5pp
through 15pp.

This is the LAST test in the Phase CC consumption branch as defined by
the spec ("If neither 10% nor 15% improves Sharpe and
neutral_deteriorating performance, explicitly retire the Phase CC
hint-consumption branch"). Both conditions are met:
- Neither 10pp nor 15pp improves Sharpe (both worsen by ≥0.006).
- Neither 10pp nor 15pp delivers a positive `neutral_deteriorating` delta (both negative).

The Phase CC `defensive_overlay_hint` is therefore retired as a
production-allocator consumer mechanism. The Phase CC refined state
file (`market_state_history_refined.csv`) remains useful upstream
intelligence for state-classification reporting / dashboarding, but is
NOT a portfolio-improvement signal at the offensive-sleeve-multiplier
layer of production.

## J. Project journey log update

- **File updated**: `docs/research/project_journey.md`
- **Section added**: Section 46 — Phase GG: Magnitude Test for Phase CC
  Hint Integration (Last Test in Branch).
- **Story currency**: project journey is now current through Phase GG
  with an explicit retirement of the Phase CC hint-consumption branch.

## Methodological + structural conclusions across the Phase CC arc

1. **Phase CC's split is statistically real.** Forward 4w panic-transition
   probability is 3.6× higher in `neutral_deteriorating` than
   `neutral_healthy`; forward 13w SPY mean is more than 2× higher in
   healthy than deteriorating. This finding is preserved.

2. **Reconstruction fidelity matters more than mechanism choice.** Phase
   DD (ETF-level post-hoc) and Phase EE (sleeve-level post-hoc) both
   failed via the same ~0.0001/wk reconstruction noise floor. Phase FF
   (in-allocator) fixed that. This is a permanent methodological lesson
   for any future hint-style intervention.

3. **A statistically meaningful upstream signal can still have zero
   deployable portfolio value.** Phase FF (5pp), GG1 (10pp), and GG2
   (15pp) all show the same monotonic worsening of every selection
   metric vs production, with the worsening proportional to magnitude.
   This rules out the "magnitude was too small" hypothesis from the
   Phase FF report.

4. **Two interpretations of why the in-allocator tilt cannot help:**
   a. Production's dynamic_risk_budget tilt does not modify offensive
      sleeves in `neutral_mixed` (the original bucket containing
      `neutral_deteriorating`); raw HRP sizes them at what appears to
      be approximately the right level for that state.
   b. The lighter_both_targeted_narrow_plus_confirmed overlay
      downstream re-equilibrates risk in a way that absorbs much of
      the offensive scale-down — the visible per-week effect is small
      because the overlay partially undoes it.

5. **Future production-improvement work should NOT continue the Phase CC
   consumption branch.** Promising next directions (orthogonal to this
   branch):
   - Test whether the refined state file improves the
     `regime_confidence_boost` Phase 2B meta-layer's
     `p_regime_confidence` calibration (i.e., the hint informs the
     ML-based regime score rather than the sleeve weights).
   - Test whether the `composite_structural_defense_sleeve` (W1) can
     be re-introduced into a different allocator architecture where
     its forward profile matches production's defensive needs.
   - Revisit Phase 2B meta-layer construction with the refined state
     as an additional training-time feature.

## Final recommendation

- **Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`.
- **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.
- **Phase GG candidates: REJECT for production promotion.** Both fail the
  Sharpe and `neutral_deteriorating` selection gates. Layer 2 Research
  Committee verdict (`KEEP AS SHADOW (research reference)`) is honored
  only as a passive research reference; Phase 2B `combo_abc` remains
  materially stronger as the primary shadow.
- **Phase CC consumption branch: RETIRED.** The next phase should pursue
  an orthogonal improvement direction.
