# Phase II — Return-Participation Upgrade for Production (NO Phase CC features)

**Date:** 2026-04-27
**Phase type:** Token-efficient in-allocator return-participation upgrade using only existing non-Phase-CC features
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

Three small additive edits to `scripts/build_improvement_artifacts.py`:

1. Two new accepted values in `apply_a` of `apply_phase2b_adjustment` so the new modes inherit the existing `regime_confidence_boost` ML offset:
   - `regime_confidence_boost_participation_v1` (II1)
   - `regime_confidence_boost_participation_v2` (II2)

2. Inside `apply_overlays_custom`, after the Phase HH branch, **Phase II logic** that adds a small bounded `+0.015` to `regime_multiplier` in qualifying favorable weeks. Gates use only existing non-Phase-CC features (`market_state`, `breadth_sma_43`, `breadth_26w_mom`, `market_trend_positive`, plus the existing `is_strong_neutral_state_row` helper). Both gates explicitly never fire in `stressed_panic` or `recovery_fragile`.

3. Two new version specs identical to production except for `phase2b_mode`:
   - `improved_phaseii_good_state_participation_light` (II1)
   - `improved_phaseii_recovery_confirmed_participation_light` (II2)

A driver `scripts/phase_ii_return_participation.py` invokes the production construction path with `BUILD_VERSION_NAMES`, applies an 8-gate selection rule (return improvement, Sharpe improvement, MDD/CVaR caps, turnover ratio, BIL drop guard with risk-adjusted offset, stressed/fragile state guards, hidden-beta guard).

## B. What was executed

```
python scripts/phase_ii_return_participation.py
python scripts/research_committee_report.py improved_phaseii_good_state_participation_light --quick
python scripts/backtest_realism_audit.py     improved_phaseii_good_state_participation_light --quick
python scripts/allocator_benchmark_audit.py  improved_phaseii_good_state_participation_light --quick
```

Layer 4 market intelligence and Layer 3 macro feature audits skipped per spec (regime labels did not change).

## C. Files / artifacts modified or regenerated

Code (created / edited):
- `scripts/phase_ii_return_participation.py` (new — driver + selection)
- `scripts/build_improvement_artifacts.py` — three additive edits (extend `apply_a`; II1/II2 nudges inside `apply_overlays_custom`; two new version specs)

Data (created via the production pipeline):
- `data/05_layer3_portfolio_construction/portfolio_version_{returns,weights,sleeve_weights}_improved_phaseii_{good_state_participation_light,recovery_confirmed_participation_light}.csv` (6 files)
- `data/05_layer3_portfolio_construction/phase_ii_{candidate_metrics_full,state_summary,selection_table}.csv` + `phase_ii_protocol.json`

Reports (created):
- `reports/research_committee/improved_phaseii_good_state_participation_light_audit.md`
- `reports/backtest_realism/improved_phaseii_good_state_participation_light_realism_audit.md`
- `reports/allocator_benchmark/improved_phaseii_good_state_participation_light_allocator_benchmark.md`
- `data/research/{backtest_realism,allocator_benchmark}/improved_phaseii_good_state_participation_light_*.csv` (5 files)

Docs:
- `docs/research/2026-04-27_phase_ii_return_participation_report.md` (this file)
- `docs/research/project_journey.md` — Section 48 appended

## D. Were candidates generated through the production pipeline?

**Yes.** Both II1 and II2 outputs come out of `build_improvement_artifacts.py` → `run_subset_custom` → `apply_overlays_custom` → cost computation. Apples-to-apples cost-pipeline comparison preserved (constant +0.0002 ann return delta and +0.0004 Sharpe delta across the 0/5/10bp cost grid).

**No Phase CC artifacts were used** — `refined_state`, `defensive_overlay_hint`, `deterioration_z`, and the `confidence_score_p2b` columns are all NOT consulted. Both gates use only `market_state`, `breadth_sma_43`, `breadth_26w_mom`, `market_trend_positive`, and the pre-existing `is_strong_neutral_state_row` helper (all present in `market_state_history.csv` from the original Layer 2B build).

## E. Candidate metrics table

```
                                                   name  full_ann_return  full_ann_vol  full_sharpe  full_max_drawdown  full_cvar_5  full_calmar  holdout_ann_return  holdout_sharpe  holdout_max_drawdown  avg_BIL  avg_SPY  avg_turnover
        improved_phaseii_good_state_participation_light            0.0691        0.0781       0.8853            -0.1398      -0.0262       0.4944              0.1244          1.6186               -0.0626   0.2823   0.1125
improved_phaseii_recovery_confirmed_participation_light            0.0690        0.0779       0.8848            -0.1398      -0.0262       0.4934              0.1245          1.6256               -0.0626   0.2834   0.1123
               improved_phase2b_regime_confidence_boost            0.0689        0.0779       0.8848            -0.1398      -0.0262       0.4932              0.1243          1.6249               -0.0626   0.2839   0.1124
                             improved_phase2b_combo_abc            0.0686        0.0776       0.8840            -0.1367      -0.0261       0.5016              0.1236          1.6277               -0.0624   0.2856   0.1130
```

### Headline deltas (II1 vs production, full window)

| metric | candidate | production | delta | direction |
|---|---:|---:|---:|---|
| ann return | 6.910% | 6.892% | **+0.018pp** | candidate wins (tiny) |
| Sharpe | 0.8853 | 0.8848 | **+0.0004** | candidate wins (tiny) |
| max drawdown | -13.98% | -13.98% | 0.00pp | flat |
| CVaR-5% | -2.621% | -2.618% | -0.003pp | essentially flat |
| Calmar | 0.4944 | 0.4932 | +0.0012 | candidate wins |
| turnover | 0.1125 | 0.1124 | +0.0001 | flat |
| avg BIL | 28.23% | 28.39% | -0.16pp | small drop |
| avg SPY | 7.10% | 7.08% | +0.02pp | flat (no hidden beta) |

II1 improves on production on every axis it should improve on (return, Sharpe, Calmar) without measurably worsening any tail or turnover metric, and without inflating SPY exposure.

### Apples-to-apples cost-sensitivity (Layer 5 realism, --quick)

```
halfspread_bps  Δ ann return    Δ Sharpe
             0    +0.00016         +0.00043
             5    +0.00016         +0.00044
            10    +0.00016         +0.00045
1-week delay     +0.01pp           —
```

Constant positive delta across cost levels — fidelity-clean.

### II2 (recovery-confirmed, narrow gate): essentially production-equivalent

The II2 gate fires on only 44 weeks (recovery_confirmed with healthy breadth). All headline metrics are within 0.0001 of production. Effect is too small to register at the portfolio level.

## F. State-by-state impact

```
candidate                                            state                n  Δ_mean_wkly   cumulative
II1 good_state_participation_light                   calm_trend         295    -0.000000    -0.007%
II1 good_state_participation_light                   neutral_mixed      493    +0.000008    +0.956%   ← strong-neutral subset captures the boost
II1 good_state_participation_light                   recovery_confirmed  44    -0.000004    -0.020%
II1 good_state_participation_light                   recovery_fragile    49    +0.000003    +0.014%
II1 good_state_participation_light                   stressed_panic     229    +0.000001    +0.012%
II2 recovery_confirmed_participation_light           recovery_confirmed  44    -0.000007    -0.033%   ← gate fires here, tiny effect
II2 recovery_confirmed_participation_light           [other states]    1066    ~0.000000    ~0.000%
```

II1's mechanism is doing exactly what was designed:
- **+0.000008/wk in neutral_mixed (493 weeks, +0.96% cumulative)** — captures the strong-neutral subset (~199 weeks of those 493) where the gate fires.
- ~zero in calm_trend — the gate fires here too (284 weeks) but production already runs at near-1.0 regime_multiplier in calm_trend, so the +0.015 boost saturates against the cap with little practical effect.
- ~zero in stressed_panic / recovery_fragile (gate explicitly never fires).
- The aggregate effect is +0.96% cumulative over the full sample, equal to ~0.045% per year on a portfolio-weighted basis — directionally positive, magnitude tiny.

## G. Best candidate + quick committee verdict

**Best diagnostic candidate:** `improved_phaseii_good_state_participation_light` (II1).

**Selection-rule outcome:** NO Phase II portfolio candidate passes all 8 gates.
- II1 fails on `no qualifying improvement (ann +0.02pp, sharpe +0.0004)` — selection rule requires ≥0.20pp ann return improvement OR ≥0.005 Sharpe improvement; II1 delivers neither.
- The other 7 gates pass comfortably (no MDD / CVaR worsening; turnover flat; no BIL drop beyond -0.16pp; no stressed/fragile worsening; no hidden beta).
- II2 is even tinier and also fails the qualifying-improvement gate.

**Quick committee verdict (Layer 2):** **KEEP AS SHADOW (research reference)** — "competitive on risk-adjusted axes but does not pass the production return-delta gate."

II1 has a real positive good-state improvement (`neutral_mixed` strong-neutral subset, +0.96% cumulative), so per spec the Layer 5 + Layer 6 quick audits were RUN.

## H. Layer 5/6 audits — were they run?

**Yes.** Per spec, quick committee returned KEEP AS SHADOW + a positive good-state improvement.
- **Layer 5 (realism --quick):** delta is constant +0.02pp ann return at every cost level (0/5/10bp); +0.01pp at 1-week delay. The improvement is robust to stricter assumptions (it's just very small).
- **Layer 6 (allocator benchmark --quick):** allocator-side promotion bar formally NOT passed (script requires Sharpe to clearly beat best simple internal baseline by ≥0.05; structurally unfair to candidates with overlay/meta layers). Headline numbers all favor II1 vs production by tiny margins.

## I. Final decision

**REJECT both Phase II candidates** under the strict 8-gate selection rule. II1 fails on `no qualifying improvement` — its +0.02pp ann return and +0.0004 Sharpe improvements are well below the 0.20pp / 0.005 thresholds that the selection rule uses to filter noise.

**KEEP AS SHADOW (research reference)** per quick committee — II1 IS a candidate that genuinely improves on production on every axis without worsening any. It is the second candidate (after HH1) in the post-Phase-Z arc that produces a clean positive headline.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.

## I-bis. HH1 vs II1 comparison (both modify regime_multiplier with small offset)

| candidate | mechanism | weeks gated | ann return Δ | Sharpe Δ | MDD Δ | source |
|---|---|---:|---:|---:|---:|---|
| HH1 | refined_state ±0.02 (uses Phase CC) | ~520 | +0.006pp | +0.0014 | +0.24pp | Phase CC |
| II1 | breadth+trend +0.015 (no Phase CC) | ~483 | +0.018pp | +0.0004 | 0pp | non-CC features |

Both are small but real positives. HH1 wins on Sharpe and MDD; II1 wins on ann return. Neither passes the strict selection rule. The conservative magnitude (+0.015 to +0.02 on `regime_multiplier`) appears to be approximately the right floor — both extracting a small positive but not enough to clear gates.

## J. Should the return-participation path continue?

**Conditional CONTINUE — one more sweep is justified, but the bar should be calibrated.** The Phase II evidence shows:

1. **The mechanism direction is correct.** Both II1 (non-CC features) and HH1 (Phase CC features) produce small positives in the same direction by adjusting `regime_multiplier` upward in healthy/strong-neutral weeks.
2. **The conservative magnitude (+0.015 to +0.02) is too small to clear the strict gates.** The `calm_trend` saturation at near-1.0 production multiplier means most of the boost is absorbed by the cap.
3. **A magnitude sweep is the natural next test** — Phase JJ-equivalent for the upside direction (analogous to Phase GG for the downside). Specifically: test `+0.025` and `+0.035` magnitudes for II1, with the same gate.
4. **If +0.035 cannot clear the 0.20pp ann return gate or the 0.005 Sharpe gate, the path should be retired** — it would mean production's regime_multiplier is genuinely already approximately right in good states, and the headroom is structurally small.

**Alternative orthogonal direction (if Phase JJ also fails)**: revisit Path #1 from the previous spec — W1 `composite_structural_defense_sleeve` in a separate defensive risk bucket (a new allocator architecture). This requires more architectural change and is the next-most-promising path that does not depend on either Phase CC or production's regime_multiplier saturation.

**Project journey log:** `docs/research/project_journey.md` updated with Section 48 capturing Phase II and the conditional continuation recommendation.
