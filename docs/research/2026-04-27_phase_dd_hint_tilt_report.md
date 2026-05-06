# Phase DD — Production-Family Additive Tilt Consuming Phase CC's `defensive_overlay_hint`

**Date:** 2026-04-27
**Phase type:** Narrow downstream test of Phase CC; ETF-level additive tilt on production weights
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

Three new portfolio versions were added that consume Phase CC's
`defensive_overlay_hint` as an additive ETF-level tilt on top of
production weights:

- **DD1 — `improved_phasedd_hint_light`** — 5pp scale-down of all non-BIL
  ETF weights (the freed share rotates into BIL) on weeks where
  `defensive_overlay_hint == +1` AND production's BIL exposure is < 50%.
- **DD2 — `improved_phasedd_hint_moderate`** — same gate, 10pp scale-down.
- **DD3 — `improved_phasedd_hint_state_gated`** — 10pp scale-down ONLY in
  weeks where `refined_state == "neutral_deteriorating"` (the new state
  Phase CC created); does not touch `stressed_panic` or `recovery_fragile`.

Production strategy logic, sleeve definitions, allocator code, the
regime-engine, and the dashboard are all **unchanged**. The Phase DD
candidates are mechanically equal to production on every non-gate week.

## B. What was executed

```
python scripts/phase_dd_hint_tilt.py
python scripts/research_committee_report.py improved_phasedd_hint_light
python scripts/build_market_intelligence_report.py
python scripts/backtest_realism_audit.py improved_phasedd_hint_light
python scripts/robustness_simulation_audit.py improved_phasedd_hint_light
python scripts/allocator_benchmark_audit.py improved_phasedd_hint_light
```

## C. Files / artifacts modified or regenerated

Code (created):
- `scripts/phase_dd_hint_tilt.py` (new)

Data (created in `data/05_layer3_portfolio_construction/`):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasedd_hint_light.csv`
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasedd_hint_moderate.csv`
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasedd_hint_state_gated.csv`
- `phase_dd_candidate_metrics_full.csv`
- `phase_dd_pairwise_validation.csv`
- `phase_dd_state_summary.csv`
- `phase_dd_selection_table.csv`
- `phase_dd_protocol.json`

Reports (created):
- `reports/research_committee/improved_phasedd_hint_light_audit.md`
- `reports/backtest_realism/improved_phasedd_hint_light_realism_audit.md`
- `reports/backtest_realism/improved_phasedd_hint_light_simulation_audit.md`
- `reports/allocator_benchmark/improved_phasedd_hint_light_allocator_benchmark.md`
- `reports/market_intelligence/latest_market_context.md` (refreshed)
- `data/research/backtest_realism/improved_phasedd_hint_light_*.csv` (4 files)
- `data/research/allocator_benchmark/improved_phasedd_hint_light_*.csv` (2 files)

Docs:
- `docs/research/2026-04-27_phase_dd_hint_tilt_report.md` (this file)
- `docs/research/project_journey.md` (Section 43 appended)

## D. Starting point diagnosis

**Why Phase CC alone is not yet a portfolio improvement.** Phase CC produced a
refined `market_state_history_refined.csv` and a `defensive_overlay_hint`
column ∈ {-1, 0, +1}, but no portfolio. The defensive_overlay_hint distribution:
- `+1`: 449 weeks (40.5% of history) — `neutral_deteriorating` (171) +
  `recovery_fragile` (49) + `stressed_panic` (229)
- `0`: 112 weeks — `neutral_mixed` early-history fallback
- `-1`: 549 weeks — `calm_trend` (295) + `neutral_healthy` (210) +
  `recovery_confirmed` (44)

**Phase DD design rule.** The user asked for a conservative additive tilt that
(i) reduces offense only when refined state indicates deterioration, (ii) does
not increase defense everywhere, (iii) does not lower participation in
neutral_healthy / calm / recovery_confirmed, (iv) is easy to ablate, and
(v) keeps the variant count to ≤3.

**Critical structural constraint.** 229 of the 449 hint-positive weeks are
`stressed_panic`, where production already routes 40-60% of the portfolio into
BIL via the regime engine and the lighter_both overlay. Applying an additional
defensive tilt on those weeks would be exactly the "increase defense
everywhere" failure mode the user explicitly forbade. This is why DD1 and DD2
are gated by `production BIL < 50%` and DD3 is gated to `neutral_deteriorating`
only — three principled ways to avoid double-stacking defense on already-
defensive weeks.

## E. Phase DD candidate results

### Headline metrics (all candidates + production + shadow)

```
                                    name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_turnover  avg_BIL
             improved_phasedd_hint_light            0.0604       0.7815            -0.1442      -0.0267        0.1127   0.2930
          improved_phasedd_hint_moderate            0.0596       0.7812            -0.1391      -0.0264        0.1139   0.3020
       improved_phasedd_hint_state_gated            0.0600       0.7759            -0.1501      -0.0267        0.1205   0.2959
improved_phase2b_regime_confidence_boost            0.0689       0.8848            -0.1398      -0.0262        0.0562   0.2839
              improved_phase2b_combo_abc            0.0686       0.8840            -0.1367      -0.0261        0.0566   0.2856
```

### Apples-to-apples cost-consistent comparison (Layer 5 realism audit)

The headline metrics above compare Phase DD candidates' freshly-recomputed
net returns (using the project-standard 5bp half-spread on ETF-level turnover)
against production's *saved* net return series. Production's saved net return
uses a different cost pipeline (sleeve-internal cost handling).

When BOTH candidate AND production are reconstructed from weights with the
same 5bp half-spread cost model, the gap shrinks to **−0.08pp / year** at
all cost levels (0 / 5 / 10 / 25 / 50 bps half-spread):

```
halfspread_bps  cand_ann_return  prod_ann_return  delta_ann_return  cand_sharpe  delta_sharpe
             0           0.0619           0.0628           -0.0008       0.8015       +0.0006
             5           0.0604           0.0612           -0.0008       0.7815       +0.0003
            10           0.0588           0.0597           -0.0008       0.7615       +0.0000
            25           0.0542           0.0550           -0.0008       0.7016       -0.0008
            50           0.0465           0.0473           -0.0008       0.6021       -0.0023
```

Interpretation: **the tilt itself costs ~0.08pp / year and produces
essentially zero Sharpe change.** The 0.85pp gap reported in the headline
table is a cost-pipeline mismatch artifact, not a true cost of the tilt.

### State-by-state impact (DD1)

```
              state  n_weeks  dd_mean_wkly  prod_mean_wkly  delta_mean_wkly
         calm_trend      295        0.0006          0.0008          -0.0001
neutral_deteriorating  171        0.0015          0.0017          -0.0002
    neutral_healthy    210        0.0030          0.0031          -0.0002
      neutral_mixed    111        0.0006          0.0006          -0.0001
 recovery_confirmed     44        0.0004          0.0005          -0.0001
   recovery_fragile     49        0.0012          0.0013          -0.0001
     stressed_panic    229        0.0005          0.0007          -0.0002
```

Important diagnostic: **even in the targeted `neutral_deteriorating` state,
the candidate underperforms production by ~0.0002/wk (~1pp annualised).**
The tilt does not deliver on its mechanism in the very state it was designed
for.

### Pairwise validation under Phase D rule

All three candidates **fail the bootstrap probability test** (0.000 vs 0.60
threshold) and the holdout sharpe delta test (-0.10). DD3's full-window raw
target composite delta is -0.18 (worst of the three).

### Selection table (auto-applied)

```
NO Phase DD candidate passes all selection gates.
Best diagnostic candidate: improved_phasedd_hint_light;
failure reason(s): drag>0.30pp; sharpe_imp<0.005; turnover>1.10x.
```

The selection rule applied 6 gates: ann return drag ≤ 0.30pp,
Sharpe improvement ≥ 0.005, MDD worsening ≤ 0.5pp, CVaR worsening ≤ 0.05pp,
turnover ratio ≤ 1.10×, BIL increase ≤ 5pp.

DD1 fails on drag (0.85pp), Sharpe (-0.10), turnover (2.0× production).
DD2 and DD3 fail on the same gates with similar numbers.

## F. Interpretation

**What helped.** The mechanical implementation is correct, ablate-able,
and protected against the "increase defense everywhere" failure mode.
The gates fire only where intended (DD1/DD2: 247 of 1110 weeks; DD3:
171 of 1110 weeks). When measured under apples-to-apples cost
assumptions, the tilt produces no measurable harm beyond ~0.08pp/yr.

**What didn't help — the structural finding.** A flat ETF-level scale-down
of all non-BIL exposure cannot extract value from Phase CC's hint, because:

1. **Production's allocator is already state-aware.** Production already
   routes substantial defense in `stressed_panic` and `recovery_fragile`
   via the regime engine; further scale-down is either redundant
   (DD3 doesn't touch these) or counter-productive (DD1/DD2's BIL-guard
   already excludes deeply-defensive weeks).

2. **The tilt fights production's sleeve dynamics.** When production
   tilts toward `composite_regime_conditioned` and `taa_10m_sma` in
   stress weeks (per the Phase Z dynamic_risk_budget logic), an
   ETF-level scale-down treats those defensive sleeves identically to
   offensive sleeves like `dual_momentum_topn`. We are scaling down
   defense at the same rate as offense.

3. **Even in `neutral_deteriorating` (the new state), the tilt loses
   money.** This is the strongest evidence that the wrong sleeve is
   being scaled. Production's existing offensive-sleeve weight is small
   in this state (production already partially defends), so the
   incremental defense from a flat ETF scale-down is purely additive
   cost without additive insurance.

4. **The Phase CC hint is a SLEEVE-level signal applied at the ETF level.**
   The hint says "this is a deteriorating week, prefer defense over
   offense." But production's ETF weights already encode that preference
   through its sleeve choices. To consume the hint, we'd need to tilt
   the sleeve mix (specifically the OFFENSIVE-sleeve allocation) — not
   the ETF mix.

**Does Phase DD support the Phase CC story?** Negatively, but informatively.
Phase CC's split is statistically meaningful (3.6× higher panic-transition
probability in deteriorating vs healthy). The problem isn't the signal;
it's the consumption mechanism. A flat ETF tilt is too coarse.

## G. Candidate classification

**REJECT all three Phase DD candidates** for production promotion.

- DD1: REJECT (no measurable benefit; turnover ~2× production).
- DD2: REJECT (slightly larger MDD improvement but same Sharpe drag).
- DD3: REJECT (worst raw composite delta of the three; even fewer gate
  weeks but the same fundamental mechanism failure).

None are kept as shadow either, because the shadow rule requires a
positive holdout raw composite delta vs production, which all three fail
by ~0.16-0.18.

## H. Strategic diagnosis

**Did Phase DD succeed?** The phase succeeded as a *diagnostic*: it gave
a clean, ablate-able test of the simplest possible consumption mechanism
for Phase CC's hint, and that mechanism does not work. This is a
genuinely informative negative result.

**Does the project now have a deployable Phase CC consumer?** No. Phase
CC's regime refinement is still useful as upstream intelligence, but it
cannot be consumed via a flat ETF-level tilt on production weights.

**What should the next phase focus on?** A SLEEVE-level Phase DD2-bis
that consumes the hint inside the sleeve allocator, specifically
reducing the offensive sleeve share (dual_momentum_topn, cta_trend,
composite_selective_signals) when hint=+1 AND the production state is
NOT already stressed. This requires a small modification to the
production allocator code path itself (not a bolt-on at the ETF level)
and so is a Phase EE-class change, not a Phase DD-class one.

Alternative: revisit Phase BB / Phase Z with the refined state file as
the primary state input to the HRP allocator's regime-conditional
risk-budget tilt — the refined state may help the existing dynamic
risk-budget logic differentiate which neutral weeks deserve which sleeve
emphasis.

## I. Final recommendation

- **Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`.
- **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.
- **Phase DD candidates: REJECT.** None are promoted to production or shadow.
- **Phase CC artifact: kept on disk** (`market_state_history_refined.csv`)
  for use by future sleeve-level allocator integrations.
- **Next phase recommendation**: Phase EE — a sleeve-level allocator
  intervention that reads the refined state and modulates only the
  offensive sleeves' weights (not all non-BIL ETFs). This is the
  smallest change that respects the structural finding above.

## J. Project journey log update

- **File updated**: `docs/research/project_journey.md`
- **Section added**: Section 43 — Phase DD: Additive ETF-Level Tilt
  Consuming Phase CC's `defensive_overlay_hint`.
- **Story currency**: project journey is now current through the close
  of Phase DD with an honest negative-result narrative and a clear
  Phase EE recommendation.

## Audit cross-references

- Research Committee verdict (DD1): **REJECT** — full-window annual return underperforms production by 0.86pp.
- Backtest Realism (DD1): tilt costs ~0.08pp/yr at all cost levels (0/5/10/25/50bp); essentially flat Sharpe vs production under apples-to-apples cost assumptions.
- Robustness Simulation (DD1): bootstrap 5%-quantile of candidate ann return does NOT exceed production's 95%-quantile (full overlap).
- Allocator Benchmark (DD1): allocator-side promotion bar NOT passed; candidate does not beat production on annualised return AND does not clearly beat the best simple baseline on Sharpe.
