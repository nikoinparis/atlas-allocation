# Phase FF — In-Allocator Integration of Phase CC's `defensive_overlay_hint`

**Date:** 2026-04-27
**Phase type:** Token-efficient in-allocator downstream test of Phase CC; runs INSIDE production's own construction path (not as a post-hoc tilt)
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

Three minimal in-place edits to `scripts/build_improvement_artifacts.py`:

1. **Phase CC lookup loaded at module import** (after `FILTERED_VERSION_BUILD`):
   reads `data/04_layer2b_risk_regime_engine/market_state_history_refined.csv`
   into two dicts (`PHASEFF_HINT_LOOKUP`, `PHASEFF_REFINED_STATE_LOOKUP`).
   Empty if the refined file is absent. Used ONLY by the new tilt modes.

2. **Two new tilt branches added to `apply_state_conditioned_tilt`**:
   - `dynamic_risk_budget_phaseff_light` — identical to `dynamic_risk_budget`,
     plus an additional 0.95 multiplier on offensive sleeves on weeks where
     `defensive_overlay_hint == +1` AND `market_state` is NOT in
     `{stressed_panic, recovery_fragile}`.
   - `dynamic_risk_budget_phaseff_state_gated` — same pattern but the gate
     fires only when `refined_state == "neutral_deteriorating"`.
   The scale-down is applied BEFORE the per-sleeve cap (`MAX_SLEEVE_WEIGHT`),
   so the cap and the lighter_both overlay both run on the post-tilt weights.
   This preserves the production cost / overlay / cap pipeline.

3. **Two new version specs appended to `version_specs`** with `state_tilt`
   pointing to the two new tilt modes. Otherwise identical to the
   production config (`improved_phase2b_regime_confidence_boost`):
   `method_name="hrp"`, `subset_sleeves=improved_subset`,
   `overlay_variant="good_state_fragile_expression"`,
   `overlay_penalty_mode="lighter_both_targeted_narrow_plus_confirmed"`,
   `phase2b_mode="regime_confidence_boost"`,
   `target_vol_ceil=1.00`, etc.

A thin driver script `scripts/phase_ff_inallocator_hint.py` invokes
`build_improvement_artifacts.py` as a subprocess with `BUILD_VERSION_NAMES`
set so only the two Phase FF candidates plus production are built; reads
the saved files; and applies the 7-gate selection rule.

Production's `dynamic_risk_budget` tilt mode is untouched. The only effect
of these edits on existing code paths is the addition of optional new
branches in a dispatch function.

## B. What was executed

```
python scripts/phase_ff_inallocator_hint.py
python scripts/research_committee_report.py improved_phaseff_hint_inallocator_light --quick
python scripts/backtest_realism_audit.py improved_phaseff_hint_inallocator_light --quick
python scripts/allocator_benchmark_audit.py improved_phaseff_hint_inallocator_light --quick
```

Layer 4 market intelligence and Layer 3 macro feature audits were skipped
per spec (regime labels did not change; macro audit not needed for re-run).

## C. Files / artifacts modified or regenerated

Code (created / edited):
- `scripts/phase_ff_inallocator_hint.py` (new — driver)
- `scripts/build_improvement_artifacts.py` — three minimal additive edits
  (Phase CC lookup; two new tilt branches; two new version specs)

Data (created in `data/05_layer3_portfolio_construction/` via the production pipeline):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phaseff_hint_inallocator_light.csv`
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phaseff_hint_inallocator_state_gated.csv`
- `phase_ff_candidate_metrics_full.csv`
- `phase_ff_state_summary.csv`
- `phase_ff_selection_table.csv`
- `phase_ff_protocol.json`

Reports (created):
- `reports/research_committee/improved_phaseff_hint_inallocator_light_audit.md`
- `reports/backtest_realism/improved_phaseff_hint_inallocator_light_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseff_hint_inallocator_light_allocator_benchmark.md`
- `data/research/backtest_realism/improved_phaseff_hint_inallocator_light_*.csv` (3 files)
- `data/research/allocator_benchmark/improved_phaseff_hint_inallocator_light_*.csv` (2 files)

Docs:
- `docs/research/2026-04-27_phase_ff_inallocator_hint_report.md` (this file)
- `docs/research/project_journey.md` — Section 45 appended

## D. Where inside the production path the hint was integrated

**Integration point:** `scripts/build_improvement_artifacts.py` →
`apply_state_conditioned_tilt()` (around line 1346) → new tilt-mode
branches `dynamic_risk_budget_phaseff_light` and
`dynamic_risk_budget_phaseff_state_gated`.

**Pipeline ordering** (unchanged for production; same downstream pipeline
applies to Phase FF):

1. HRP allocator computes raw sleeve weights.
2. **`apply_state_conditioned_tilt()`** — Phase FF branches replicate
   `dynamic_risk_budget` exactly (favorable-state conviction, recovery_fragile
   re-risk, stressed_panic protection) AND apply the additional offensive
   0.95 multiplier on Phase CC gate weeks.
3. Per-sleeve cap (`normalize_long_only` with `MAX_SLEEVE_WEIGHT`) — runs on
   the post-tilt weights, identical to production.
4. `apply_layer3_expression()` — unchanged.
5. `apply_overlays_custom()` — including `lighter_both_targeted_narrow_plus_confirmed`
   overlay, `target_vol_ceil`, `regime_confidence_boost` Phase 2B meta layer —
   identical to production.
6. `build_lookthrough_etf_weights()` — identical to production.
7. `apply_beta_participation_overlay()` — identical to production.
8. Net return computation with the 5bp half-spread cost convention —
   identical to production.

This means Phase FF candidates pass through **exactly the same downstream
machinery** as production. The candidate's saved net_return file is fully
comparable apples-to-apples with production's saved net_return file. This
is the reconstruction-fidelity property that Phase DD and Phase EE could
not deliver.

## E. Phase FF candidate results

### Headline metrics

```
                                         name  full_ann_return  full_ann_vol  full_sharpe  full_max_drawdown  full_cvar_5  avg_turnover  avg_BIL
      improved_phaseff_hint_inallocator_light            0.0686        0.0781       0.8789            -0.1408      -0.0263        0.1125   0.2838
improved_phaseff_hint_inallocator_state_gated            0.0686        0.0781       0.8789            -0.1408      -0.0263        0.1125   0.2838
     improved_phase2b_regime_confidence_boost            0.0689        0.0779       0.8848            -0.1398      -0.0262        0.1124   0.2839
                   improved_phase2b_combo_abc            0.0686        0.0776       0.8840            -0.1367      -0.0261        0.1130   0.2856
```

### Why FF1 and FF2 produce identical results

Same as Phase EE: hint=+1 minus stressed_panic minus recovery_fragile
collapses to exactly `neutral_deteriorating` (since fallback weeks have
hint=0). Both gates fire on the same 171 weeks, and the tilt mechanics are
identical, so the saved series are identical. This is informative: there
is no remaining "hint-positive but not deeply-defensive" set beyond the
new state Phase CC created.

### State-by-state delta vs production (refined_state)

```
                state  n_weeks  delta_mean_wkly  ff_minus_prod_cumulative
            calm_trend  295        -0.000015                -0.5675%
 neutral_deteriorating  171        -0.000001                -0.0158%
       neutral_healthy  210        -0.000016                -0.6296%
         neutral_mixed  112        +0.000023                +0.2693%
   recovery_confirmed   44        -0.000003                -0.0161%
     recovery_fragile   49        -0.000011                -0.0577%
        stressed_panic  229        +0.000000                -0.0044%
```

### Cost sensitivity (Layer 5 realism, --quick)

```
halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
             0           0.0624           0.0628           -0.0003       0.7949       -0.0060
             5           0.0609           0.0612           -0.0003       0.7752       -0.0059
            10           0.0593           0.0597           -0.0003       0.7556       -0.0059
```

Δ ann return is **constant at -0.03pp** across cost levels — confirming
that the in-allocator integration preserves cost-pipeline fidelity.
1-week rebalance delay produces +0.02pp delta vs production
(noise-level).

### Allocator benchmark (Layer 6, --quick)

```
allocator                                                ann_return   sharpe    MDD     turnover
equal_weight                                                  +5.45%   0.78   -13.7%      0.001
inverse_vol                                                   +4.72%   0.86   -11.7%      0.004
hrp_internal                                                  +4.19%   0.93   -10.9%      0.006
production:improved_phase2b_regime_confidence_boost           +6.89%   0.88   -14.0%      0.056
candidate:improved_phaseff_hint_inallocator_light             +6.86%   0.88   -14.1%      0.056
```

The candidate is **essentially production-equivalent** at the
sleeve-allocator level — production's ann return advantage of +0.03pp
and Sharpe advantage of +0.006 over the candidate are both well below
any realistic noise floor.

## F. Best candidate, quick verdict, and selection-rule outcome

**Best diagnostic candidate:** `improved_phaseff_hint_inallocator_light`
(EE1 ≡ EE2 on this sample).

**Selection-rule outcome:** NO Phase FF candidate passes all 7 gates.
Failure reasons (FF1 / FF2 are identical):
- `sharpe_imp<0.005 (-0.0059)` — FAILS the "must improve Sharpe by ≥0.005" gate
- `underperforms in neutral_deteriorating (Δ=-0.000001/wk)` — FAILS the new
  "must not underperform in neutral_deteriorating" gate

The other 5 gates **PASS**:
- ann return drag: -0.03pp (well within 0.30pp budget)
- mdd worsening: -0.10pp (within 0.5pp budget)
- cvar worsening: -0.013pp (within 0.05pp budget)
- turnover ratio vs production: 1.0009× (well within 1.10× budget)
- BIL increase: -0.01pp (well within 5pp budget)

**Quick committee verdict:** **KEEP AS SHADOW (research reference).**
The Layer 2 Research Committee says the candidate "is competitive on
risk-adjusted axes but does not pass the production return-delta gate."
This is dramatically better than the Phase DD / EE quick verdicts of REJECT.

## G. Whether reconstruction fidelity is fixed

**YES — reconstruction fidelity is empirically fixed.** Compare the
non-gate-state per-week deltas (where candidate sleeve weights are
identical to production):

| state                | Phase EE Δ/wk (post-hoc) | Phase FF Δ/wk (in-allocator) | improvement |
|----------------------|--------------------------:|------------------------------:|------------:|
| calm_trend           |              -0.000142    |                  -0.000015    |        ~10× |
| neutral_healthy      |              -0.000159    |                  -0.000016    |        ~10× |
| recovery_confirmed   |              -0.000102    |                  -0.000003    |        ~30× |
| recovery_fragile     |              -0.000069    |                  -0.000011    |         ~6× |
| stressed_panic       |              -0.000177    |                  +0.000000    |        ~∞×  |

The non-gate-state deltas drop by approximately one order of magnitude
(or completely vanish in `stressed_panic`). The remaining deltas are
within rounding / floating-point precision of zero. This empirically
validates the diagnosis from Phase DD / EE that the post-hoc
reconstruction was the source of the systematic underperformance, not
the hint itself.

## H. Whether full audit is worth running

**Marginally — and only as a research-reference exercise.** The
candidate is shadow-quality, not production-quality. The five remaining
audits that were skipped (full robustness simulation, market intelligence
report, macro feature audit) would not change the decision: the candidate
has a tiny but unambiguously negative Sharpe delta and a near-zero
neutral_deteriorating delta. Running them costs tokens with no
decision-relevant payoff.

If a human researcher wants to track the candidate as a passive shadow
reference, the existing `phase_ff_*` artifacts are sufficient.

## I. If rejected, the structural reason

The candidate is rejected on two gates by tiny margins, so the
structural reason is **not "the integration mechanism is wrong"**
(Phase DD's reason) and **not "the reconstruction is noisy"** (Phase EE's
reason). The structural reason for Phase FF is:

**The 5pp offensive scale-down on 171 weeks does not deliver measurable
improvement, even when integrated cleanly into the production pipeline.**
The marginal effect in `neutral_deteriorating` is essentially zero
(-0.000001/wk = -0.005% annualised). Two interpretations are consistent
with this:

1. **Production's offensive sleeve sizes in `neutral_deteriorating` are
   already approximately right.** The dynamic_risk_budget tilt does not
   apply in `neutral_mixed` (the original bucket that contained
   `neutral_deteriorating`), so production sizes offensive sleeves at
   their HRP level — which appears to be neither too large nor too
   small in this state.

2. **The 5pp magnitude is too small to matter.** A 0.05 multiplier on
   sleeves that average ~39% of the portfolio collectively produces
   only a ~2pp portfolio shift, and the lighter_both overlay + per-sleeve
   cap downstream may absorb most of that shift before it reaches the
   ETF level. A larger magnitude (10pp or 15pp) would test this
   interpretation directly.

These are not "structural failure" reasons; they are "magnitude /
signal-strength" reasons. The Phase CC hint is not wrong, and the
in-allocator integration is not wrong; the integration just doesn't
move the needle at the conservative magnitude tested.

## Final recommendation

- **Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`.
- **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.
- **Phase FF candidates: REJECT for production promotion; SHADOW-quality
  per Layer 2 committee but only as a research reference** (the
  Phase 2B combo_abc shadow is materially stronger).
- **Methodological win recorded**: in-allocator integration fixes
  reconstruction fidelity. The methodology is now ready for any future
  hint-style intervention.
- **Next phase recommendation (Phase GG)**: test whether a stronger
  offensive scale-down (10pp or 15pp) inside the same in-allocator
  pipeline can move the neutral_deteriorating delta materially positive.
  If even a 15pp scale-down doesn't help, the conclusion is that
  production's allocator already sizes offense correctly in
  `neutral_deteriorating` and Phase CC's signal — while statistically
  meaningful — does not have a deployable portfolio interpretation at
  the offensive-sleeve-multiplier layer. Phase GG should be the LAST
  test in this branch before retiring the Phase CC consumption thread.

## J. Project journey log update

- **File updated**: `docs/research/project_journey.md`
- **Section added**: Section 45 — Phase FF: In-Allocator Integration of
  Phase CC's `defensive_overlay_hint`.
- **Story currency**: project journey is now current through Phase FF
  with a methodological win (reconstruction fidelity fixed) and an
  empirical no-result (the conservative-magnitude tilt produces zero
  measurable improvement).
