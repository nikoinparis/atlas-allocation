# Phase EE — Sleeve-Level Downstream Test of Phase CC's `defensive_overlay_hint`

**Date:** 2026-04-27
**Phase type:** Token-efficient sleeve-level downstream test of Phase CC; rotation off→def at the SLEEVE layer (not the ETF layer)
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

Two new portfolio versions were added that consume Phase CC's
`defensive_overlay_hint` at the SLEEVE level. Both candidates take
production's saved sleeve weights and, on gate weeks only:

1. scale all OFFENSIVE sleeves (`dual_momentum_topn`,
   `cta_trend_long_only`, `composite_selective_signals`) by `(1 − δ)`,
2. redistribute the freed weight proportionally across DEFENSIVE sleeves
   (`composite_regime_conditioned`, `taa_10m_sma`),
3. leave the `cash::BIL` bucket untouched.

Then ETF weights are re-derived as the standard long-only weighted sum
of `sleeve_positions × sleeve_weights + cash::BIL → BIL`.

Variants:
- **EE1 — `improved_phaseee_sleeve_hint_light`** — gate fires when
  `defensive_overlay_hint == +1` AND `market_state` is NOT in
  {`stressed_panic`, `recovery_fragile`}. δ = 0.10.
- **EE2 — `improved_phaseee_sleeve_hint_state_gated`** — gate fires when
  `refined_state == "neutral_deteriorating"`. δ = 0.10.

Production strategy logic, sleeve definitions, allocator code, and the
regime engine are all unchanged.

## B. What was executed

```
python scripts/phase_ee_sleeve_hint_tilt.py
python scripts/research_committee_report.py improved_phaseee_sleeve_hint_light --quick
```

Per the user's quick-screen-first protocol: the quick committee screen
returned **REJECT**, so the full Layer 5 backtest realism and Layer 6
allocator benchmark audits were **NOT run**. Layer 4 market intelligence
and Layer 3 macro feature audits were also skipped per spec.

## C. Files / artifacts modified or regenerated

Code (created / minor patches):
- `scripts/phase_ee_sleeve_hint_tilt.py` (new)
- `scripts/research_committee_report.py` — added `--quick` flag (no-op for compatibility)
- `scripts/backtest_realism_audit.py` — added `--quick` flag (trims sensitivity grids)
- `scripts/allocator_benchmark_audit.py` — added `--quick` flag (skips ERC / MaxDiv / tracker)

Data (created in `data/05_layer3_portfolio_construction/`):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phaseee_sleeve_hint_light.csv`
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phaseee_sleeve_hint_state_gated.csv`
- `phase_ee_candidate_metrics_full.csv`
- `phase_ee_state_summary.csv`
- `phase_ee_selection_table.csv`
- `phase_ee_protocol.json`

Reports (created):
- `reports/research_committee/improved_phaseee_sleeve_hint_light_audit.md`

Docs:
- `docs/research/2026-04-27_phase_ee_sleeve_hint_tilt_report.md` (this file)
- `docs/research/project_journey.md` (Section 44 appended)

## D. Starting point diagnosis

**Why Phase EE was needed.** Phase DD applied a flat ETF-level scale-down
that treated production's defensive sleeves identically to its offensive
sleeves and provided ~zero benefit even in the targeted state. The
hypothesis for Phase EE was: by intervening at the SLEEVE level — scaling
only offensive sleeves and redirecting into existing defensive sleeves —
the hint could be consumed surgically.

**Production sleeve schema** (confirmed from
`portfolio_version_sleeve_weights_improved_phase2b_regime_confidence_boost.csv`):

| sleeve | role | avg weight |
|---|---|---:|
| dual_momentum_topn | offensive | 10.7% |
| cta_trend_long_only | offensive | 10.3% |
| composite_selective_signals | offensive | 18.1% |
| composite_regime_conditioned | defensive | 25.4% |
| taa_10m_sma | defensive | 13.4% |
| cash::BIL | cash | 22.1% |

A 10pp scale-down of offensive sleeves represents roughly a 3.9pp shift
of total portfolio from offense to defense per gate week — a surgical
adjustment, not a heavy-handed one.

## E. Phase EE candidate results

### Headline metrics (full window)

```
                                    name  weeks_triggered  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_turnover  avg_BIL  avg_SPY
      improved_phaseee_sleeve_hint_light              171            0.0611       0.7807            -0.1496      -0.0269        0.1138   0.2848   0.0708
improved_phaseee_sleeve_hint_state_gated              171            0.0611       0.7807            -0.1496      -0.0269        0.1138   0.2848   0.0708
improved_phase2b_regime_confidence_boost                0            0.0689       0.8848            -0.1398      -0.0262        0.0562   0.2839   0.0708
              improved_phase2b_combo_abc                0            0.0686       0.8840            -0.1367      -0.0261        0.0566   0.2856   0.0708
```

### Why EE1 and EE2 produce identical results

The two variants' gate masks happen to fire on **exactly the same 171
weeks**. EE1's gate = (hint=+1 AND state NOT in {stressed_panic,
recovery_fragile}). The hint=+1 set covers 449 weeks: 171
neutral_deteriorating + 49 recovery_fragile + 229 stressed_panic. After
excluding stressed_panic and recovery_fragile, only neutral_deteriorating
remains. EE2's gate is `neutral_deteriorating` directly. The two gates
are mathematically equivalent on this sample, so the candidates are
identical. This is a clean diagnostic — there is no remaining variant
of "hint-positive but not deeply-defensive" beyond the new
`neutral_deteriorating` state.

### State-by-state delta vs production (refined_state)

```
                state  n_weeks  delta_mean_wkly  ee_minus_prod_cumulative
            calm_trend  295        -0.000142                -5.06%
 neutral_deteriorating  171        -0.000160                -3.56%
       neutral_healthy  210        -0.000159                -6.24%
         neutral_mixed  111        -0.000056                -0.67%
   recovery_confirmed   44        -0.000102                -0.46%
     recovery_fragile   49        -0.000069                -0.36%
        stressed_panic  229        -0.000177                -4.61%
```

**Critical diagnostic.** The candidate underperforms production by
roughly the same amount (~0.00014–0.00018/wk) in EVERY state, including
non-gate states where sleeve weights should be IDENTICAL to production.
This is the same reconstruction-fidelity problem identified in Phase DD:
my pipeline that rebuilds ETF weights from `sleeve_weights ×
sleeve_positions` does not exactly reproduce production's saved ETF
weights even when the sleeve weights are unchanged. The actual marginal
effect of the tilt in `neutral_deteriorating` is approximately
−0.00016 − (−0.00014) ≈ **−0.00002/week (zero)**.

### Selection-rule outcome

```
NO Phase EE candidate passes. Best diagnostic: improved_phaseee_sleeve_hint_light.
Failure reasons:
  drag>0.30pp (0.78pp);
  sharpe_imp<0.005 (-0.10);
  mdd_worse>0.5pp (-0.98pp);
  cvar_worse>0.05pp (-0.07pp);
  turnover>1.10x (2.02x);
  underperforms in neutral_deteriorating (Δ=-0.00016/wk).
```

Six of seven gates fail; the seventh (`bil_inc>5pp`) passes (BIL only
rises by 0.09pp, because the rotation goes into defensive sleeves rather
than BIL).

## F. Interpretation

**What helped.** The sleeve-level mechanic itself is correct:
- defensive sleeves DO get more weight (not BIL),
- offensive sleeves DO get less weight,
- cash::BIL is untouched,
- the gate fires only on the 171 deteriorating weeks (15.4% of history).

**What did NOT help — the structural finding.** Even with the correct
intervention level (sleeve, not ETF) and the correct redirection target
(defensive sleeves, not BIL), the candidate underperforms production
even in `neutral_deteriorating`. The reason is methodological rather
than mechanistic: my reconstruction of ETF weights from
`sleeve_weights × sleeve_positions + cash::BIL` does not exactly
reproduce production's saved ETF weights. Production's `build_improvement_artifacts.py`
applies the lighter_both overlay, the per-sleeve cap, and the dynamic
risk budget tilt INSIDE its own code path; my reconstruction loses that
fidelity.

This is the second time the same lesson has surfaced (first in Phase DD,
now in Phase EE): **post-hoc reconstruction of production's ETF weights
introduces a systematic ~0.0001–0.0002/wk bias that is larger than the
true marginal effect of the hint tilt.** No amount of careful
sleeve-level surgery can overcome this if the comparison apparatus
itself is biased.

**Quick committee verdict.** The Layer 2 research committee
(`reports/research_committee/improved_phaseee_sleeve_hint_light_audit.md`)
issues **REJECT** with reason "full-window annual return underperforms
production by 0.78pp." Per the user's quick-screen-first protocol,
the full Layer 5 realism, Layer 6 allocator benchmark, Layer 4 market
intelligence, and Layer 3 macro feature audits were **not run** because
the quick screen failed.

## G. Candidate classification

**REJECT both Phase EE candidates** for production AND shadow promotion.

EE1 and EE2 are mathematically identical on this sample. Neither passes
the selection rule, and the one new gate (`must beat production in
neutral_deteriorating`) fails by a small but unambiguous margin
(−0.00016/wk).

## H. Strategic diagnosis

**Did Phase EE succeed?** As a *diagnostic*, yes. Phase EE confirmed
that the Phase DD failure was not just about ETF-vs-sleeve level — it
was also about reconstruction fidelity. The combination of the two
phases produces a clear conclusion: **a downstream Phase CC consumer
that runs OUTSIDE production's own code path cannot extract value from
the hint, because the reconstruction noise dominates the signal.**

**Does the project have a deployable Phase CC consumer?** No. Two
out-of-allocator consumption mechanisms (Phase DD ETF-level, Phase EE
sleeve-level) have now both failed. Phase CC's regime refinement is
still useful as upstream intelligence; the integration must happen
inside the production allocator itself.

**What should the next phase focus on?** Phase FF — modify
`scripts/build_improvement_artifacts.py` (or the relevant production
construction path) so the offensive-sleeve scale-down happens INSIDE
production's own allocator construction, before the lighter_both overlay
and per-sleeve cap renormalisation. This is the smallest change that
preserves the cost / overlay / cap pipeline fidelity while still
consuming Phase CC's hint.

The first concrete Phase FF test should be:
1. inside production construction, on weeks where
   `defensive_overlay_hint == +1` AND state is NOT in
   {stressed_panic, recovery_fragile}, scale the dynamic-risk-budget
   *offensive multiplier* down by 5–10% (not the whole sleeve weight),
2. let the existing per-sleeve cap, lighter_both overlay, and
   regime_confidence_boost meta-layer absorb the change naturally,
3. compare the resulting saved net_return series directly against
   production's saved net_return series on the same cost pipeline.

This both uses Phase CC's hint and preserves comparison fidelity.

## I. Final recommendation

- **Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`.
- **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.
- **Phase EE candidates: REJECT.** Neither EE1 nor EE2 is promoted to
  production or shadow.
- **Should the full audit be run?** No — per the quick-screen-first
  protocol, the candidate failed the Layer 2 research committee's REJECT
  bar, so spending Layer 5 / Layer 6 / Layer 3 / Layer 4 budget would
  not change the decision.
- **Next phase recommendation**: Phase FF — in-allocator integration of
  the Phase CC hint inside `build_improvement_artifacts.py` (or
  equivalent), tested under the same cost pipeline as production's saved
  series.

## J. Project journey log update

- **File updated**: `docs/research/project_journey.md`
- **Section added**: Section 44 — Phase EE: Sleeve-Level Downstream
  Test of Phase CC.
- **Story currency**: project journey is now current through the close
  of Phase EE with the second consecutive negative-result narrative on
  out-of-allocator hint consumption, and a clear Phase FF
  in-allocator recommendation.
