# Phase HH — Refined-State Regime-Confidence FEATURE (not a portfolio multiplier)

**Date:** 2026-04-27
**Phase type:** Token-efficient downstream test of Phase CC as a regime-confidence feature inside production's pipeline; complements (and closes) the Phase DD/EE/FF/GG portfolio-multiplier branch
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

Four small additive edits to `scripts/build_improvement_artifacts.py`:

1. Two new accepted values in `apply_a` of `apply_phase2b_adjustment` so the new Phase 2B modes inherit the existing `regime_confidence_boost` ML offset:
   - `regime_confidence_boost_refined_v1` (HH1)
   - `regime_confidence_boost_refined_v2` (HH2)

2. Inside `apply_overlays_custom`, after the production phase2b adjustment runs, **HH1 logic** that nudges `regime_multiplier` by ±0.02 based on Phase CC's `refined_state`:
   - `neutral_healthy`: +0.02 (small risk-on lift)
   - `neutral_deteriorating`: -0.02 (small caution)
   - `recovery_confirmed`: +0.01 (mild boost)
   - all other states: 0

3. Inside `apply_overlays_custom`, after `dynamic_speed` is finalized, **HH2 logic** that scales `dynamic_speed` by 0.85 ONLY in `neutral_deteriorating` weeks. No effect in healthy / calm / recovery_confirmed (avoids defensive drag).

4. Two new version specs at the end of `version_specs` with `phase2b_mode` set to the new modes; otherwise identical to production.

A driver script `scripts/phase_hh_refined_confidence_feature.py` invokes the production construction path with `BUILD_VERSION_NAMES`, applies a 9-gate selection rule (the previous 7 gates plus two new ones for `neutral_healthy` and `recovery_confirmed` participation), and runs the **HH3 feature-ablation** test (a strictly-causal Brier-score comparison of `p_regime_confidence` alone vs `p_regime_confidence` augmented with a refined-state shift, on the forward-4-week probability of transitioning into `stressed_panic`).

Production's `dynamic_risk_budget` tilt and `regime_confidence_boost` mode are unchanged. The HH1/HH2 candidate returns/weights come out of the same build pipeline as production (subprocess invocation with filtered version names).

## B. What was executed

```
python scripts/phase_hh_refined_confidence_feature.py
python scripts/research_committee_report.py improved_phasehh_refined_confidence_additive --quick
python scripts/backtest_realism_audit.py     improved_phasehh_refined_confidence_additive --quick
python scripts/allocator_benchmark_audit.py  improved_phasehh_refined_confidence_additive --quick
```

Layer 4 market intelligence and Layer 3 macro feature audits were skipped per spec (regime labels did not change).

## C. Files / artifacts modified or regenerated

Code (created / edited):
- `scripts/phase_hh_refined_confidence_feature.py` (new — driver + HH3 ablation)
- `scripts/build_improvement_artifacts.py` — four additive edits (extend `apply_a`; HH1 nudge; HH2 smoothing; two new version specs)

Data (created via the production pipeline):
- `data/05_layer3_portfolio_construction/portfolio_version_{returns,weights,sleeve_weights}_improved_phasehh_refined_confidence_{additive,smoothing}.csv` (6 files)
- `data/05_layer3_portfolio_construction/phase_hh_{candidate_metrics_full,state_summary,selection_table}.csv`
- `data/05_layer3_portfolio_construction/phase_hh_feature_ablation.csv` (HH3)
- `data/05_layer3_portfolio_construction/phase_hh_protocol.json`

Reports (created):
- `reports/research_committee/improved_phasehh_refined_confidence_additive_audit.md`
- `reports/backtest_realism/improved_phasehh_refined_confidence_additive_realism_audit.md`
- `reports/allocator_benchmark/improved_phasehh_refined_confidence_additive_allocator_benchmark.md`
- `data/research/{backtest_realism,allocator_benchmark}/improved_phasehh_refined_confidence_additive_*.csv` (5 files)

Docs:
- `docs/research/2026-04-27_phase_hh_refined_confidence_feature_report.md` (this file)
- `docs/research/project_journey.md` — Section 47 appended

## D. Were candidates generated through the production pipeline?

**Yes.** The driver invokes `build_improvement_artifacts.py` as a subprocess with `BUILD_VERSION_NAMES` set to the two HH portfolio candidates plus production. All HH1/HH2 outputs (returns, weights, sleeve weights, diagnostics) come out of the same `run_subset_custom` → `apply_overlays_custom` → `build_lookthrough_etf_weights` → cost computation path that production uses. Apples-to-apples cost-pipeline comparison is preserved.

This is the critical methodological property established in Phase FF and now applied a second time. Both HH1 and HH2 are fidelity-clean.

## E. Candidate metrics table

```
                                         name  full_ann_return  full_ann_vol  full_sharpe  full_max_drawdown  full_cvar_5  full_calmar  holdout_ann_return  holdout_sharpe  holdout_max_drawdown  avg_BIL  avg_SPY  avg_turnover
 improved_phasehh_refined_confidence_additive            0.0690        0.0778       0.8862            -0.1374      -0.0262       0.5021              0.1243          1.6169               -0.0625   0.2835   0.0708        0.1122
improved_phasehh_refined_confidence_smoothing            0.0689        0.0779       0.8843            -0.1399      -0.0262       0.4925              0.1243          1.6241               -0.0626   0.2839   0.0709        0.1123
     improved_phase2b_regime_confidence_boost            0.0689        0.0779       0.8848            -0.1398      -0.0262       0.4932              0.1243          1.6249               -0.0626   0.2839   0.0708        0.1124
                   improved_phase2b_combo_abc            0.0686        0.0776       0.8840            -0.1367      -0.0261       0.5016              0.1236          1.6277               -0.0624   0.2856   0.0708        0.1130
```

### Headline deltas (HH1 vs production, full window)

| metric | candidate | production | delta | direction |
|---|---:|---:|---:|---|
| ann return | 6.898% | 6.892% | **+0.006pp** | candidate wins |
| Sharpe | 0.8862 | 0.8848 | **+0.0014** | candidate wins |
| max drawdown | -13.74% | -13.98% | **+0.24pp** | candidate wins |
| CVaR-5% | -2.620% | -2.618% | -0.002pp | essentially equal |
| Calmar | 0.502 | 0.493 | **+0.009** | candidate wins |
| turnover (weekly L1) | 0.1122 | 0.1124 | **-0.0002** | candidate wins (lower) |
| avg BIL | 28.35% | 28.39% | -0.04pp | essentially equal |

**HH1 beats production on every headline axis except the two ~zero ones.** This is the FIRST candidate in the entire DD/EE/FF/GG/HH arc to beat production on the production-pin's own headline metrics.

### Apples-to-apples cost sensitivity (Layer 5 realism)

```
halfspread_bps  Δ ann return    Δ Sharpe
             0    +0.0001         +0.0015
             5    +0.0001         +0.0015
            10    +0.0001         +0.0015
1-week delay     +0.02pp           —
```

Both deltas are constant across cost levels and slightly positive — confirming this is a clean, reconstruction-fidelity-respecting result.

### HH2 (smoothing): essentially production-equivalent

HH2's `dynamic_speed *= 0.85` in `neutral_deteriorating` produces
indistinguishable headline metrics (ann return 6.89%, Sharpe 0.8843
vs prod 0.8848 — Δ -0.0005). The state breakdown shows ~zero per-week
deltas in every state. This is consistent with the Phase GG finding that
production's existing dynamic_speed logic in `neutral_mixed` already
produces approximately the right re-risking pace.

## F. State-by-state impact (HH1)

```
              state  n_weeks  Δ_mean_wkly   cumulative
         calm_trend  295        0.000000       +0.011%
neutral_deteriorating 171      -0.000028       -0.600%
    neutral_healthy  210       +0.000031       +1.192%
      neutral_mixed  112        0.000000        0.000%
recovery_confirmed   44       -0.000014       -0.063%
  recovery_fragile   49       -0.000016       -0.083%
     stressed_panic 229       +0.000002       +0.090%
```

The mechanism is doing exactly what was designed:
- **+0.000031/wk in neutral_healthy (210 weeks, +1.19% cumulative)** — the +0.02 risk-on offset captures more upside in healthy weeks.
- **-0.000028/wk in neutral_deteriorating (171 weeks, -0.60% cumulative)** — the -0.02 caution offset reduces participation in pre-stress weeks.
- The aggregate effect is positive (the gain in healthy outweighs the small drag in deteriorating).

But the per-week magnitude in deteriorating is slightly negative, which fails the strict selection rule's "must not underperform in neutral_deteriorating" gate.

## G. Best candidate + quick committee verdict

**Best diagnostic candidate:** `improved_phasehh_refined_confidence_additive` (HH1).

**Selection-rule outcome:** NO portfolio candidate passes all 9 gates.
- HH1 fails on `sharpe_imp<0.005 (+0.0014)` and `underperforms in neutral_deteriorating (Δ=-0.000028/wk)`. The other 7 gates pass comfortably (drag +0.006pp gain, MDD +0.24pp gain, turnover lower, BIL lower).
- HH2 fails similarly with smaller magnitudes.

**Quick committee verdict (Layer 2):** **KEEP AS SHADOW (research reference).** "Candidate is competitive on risk-adjusted axes but does not pass the production return-delta gate."

This is the first candidate in the entire arc to also satisfy the spec's "with at least one genuinely positive state-level improvement" condition (`neutral_healthy` Δ +0.000031/wk, +1.19% cumulative). Per spec, the Layer 5 + Layer 6 quick audits were therefore RUN.

## H. Layer 5/6 audits — were they run? what did they say?

**Yes, both run** because the quick committee returned KEEP AS SHADOW + a genuine positive state-level improvement.

**Layer 5 (backtest realism, --quick):** candidate beats production on ann return AND Sharpe at every cost level (0/5/10bp half-spread); +0.02pp ann return advantage with 1-week delay. Realism is solid — the small headline win persists under stricter assumptions.

**Layer 6 (allocator benchmark, --quick):** candidate ann return 6.898% vs production 6.892% (+0.006pp); Sharpe 0.8862 vs 0.8848 (+0.0014); MDD -13.74% vs -13.98%; calmar 0.502 vs 0.493. Allocator-side promotion bar formally NOT passed (the script requires Sharpe to clearly beat the best simple internal baseline by ≥0.05; internal HRP scores 0.93, candidate 0.89 — the comparison is structurally unfair because internal HRP has no overlay/meta layer, but the script's threshold is strict).

## H-bis. HH3 — feature ablation (the most informative finding)

A strictly-causal walk-forward Brier-score comparison: does augmenting
`p_regime_confidence` with a refined-state shift (healthy −0.05, mixed 0,
deteriorating +0.05, calm −0.05, recovery_confirmed −0.03,
recovery_fragile +0.03) improve forward-4-week stress prediction?

```
n_obs = 906
brier_baseline (p_regime_confidence alone)            = 0.21110
brier_aug      (p_regime_confidence + refined_state)  = 0.19243
improvement                                            = +0.01867
relative improvement                                   = 8.84%
```

**Yes — refined_state carries genuine incremental forward-stress
information beyond `p_regime_confidence`.** This is the strongest
methodological evidence in the entire Phase CC arc that the refined
state file is *informative* at the prediction layer, even though the
portfolio-consumption mechanisms (DD/EE/FF/GG and now HH1/HH2) cannot
extract enough deployable value from it to clear the strict 9-gate
selection rule.

This is informative for the next-direction recommendation: the right
place to consume refined_state is probably as a TRAINING-time feature
for the Phase 2B logistic / decision tree / GBM, not as a runtime
adjustment of regime_multiplier or sleeve weights.

## I. Final decision

**REJECT both Phase HH portfolio candidates for production promotion**
under the strict 9-gate selection rule. Both fail by tiny margins:
- HH1 ann return DOES improve (+0.006pp) but Sharpe gain (+0.0014) is
  below the +0.005 gate; `neutral_deteriorating` per-week delta is
  -0.000028/wk (just below zero).
- HH2 effect is essentially zero across all metrics.

**KEEP AS SHADOW (research reference)** per the Layer 2 quick verdict —
HH1 is the first candidate in the entire arc that genuinely beats
production on the headline axes, and the underlying refined_state
signal demonstrably carries incremental information (HH3 Brier
improvement 8.8%).

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`.
**Shadow pin remains unchanged**: `improved_phase2b_combo_abc`. The Phase 2B
combo_abc shadow remains the recorded shadow because it has been the
shadow for many phases and HH1 is not materially stronger.

## I-bis. Phase CC refined-state PORTFOLIO-CONSUMPTION path: RETIRE

Per the spec's escalation rule ("If all HH candidates fail: Mark Phase CC
portfolio-consumption path as retired"), and consistent with the
DD/EE/FF/GG retirement decision, the **direct portfolio-consumption path
for Phase CC's refined_state is now formally retired**. Five mechanisms
have now been tested and rejected:
- Phase DD: post-hoc ETF-level scale-down — REJECT (zero benefit; double-defense risk).
- Phase EE: post-hoc sleeve-level rotation — REJECT (reconstruction noise).
- Phase FF: in-allocator 5pp offensive scale-down — REJECT (zero benefit, fixed fidelity).
- Phase GG: in-allocator 10pp / 15pp magnitudes — REJECT (monotonically harmful).
- Phase HH: in-allocator regime-confidence offset / smoothing — REJECT (tiny positive but below thresholds).

**What stays valid from Phase CC:**
- The refined state file (`market_state_history_refined.csv`) and its diagnostic columns (deterioration_z, rank, defensive_overlay_hint).
- The HH3 ablation result: `refined_state` carries +8.8% Brier improvement on forward-stress prediction over `p_regime_confidence` alone.
- The methodological pattern (DD → EE → FF → GG → HH) for testing downstream consumers of an upstream signal.

## J. Recommended orthogonal next path

**Recommend Path #3 from the spec list:**
**"Return-participation upgrade for production that does not depend on Phase CC"** — i.e., a phase that targets production's return drag on `calm_trend` and `neutral_healthy` weeks (where production is already well-positioned defensively but leaves a small amount of return on the table) without using any Phase CC artifact.

Reasoning:
- Path #1 (W1 in a separate defensive risk bucket) requires building a new allocator architecture; high effort, uncertain payoff.
- Path #2 (non-Z1 holdings-blend partner) requires identifying and validating a new partner candidate; moderate effort, structurally similar to Phase AA's failed test.
- Path #3 attacks the metric where production has the most headroom (calm_trend annualized return ~3pp below the equity benchmark) and does not depend on the Phase CC consumption thread that has now been thoroughly explored and closed.

The HH1 result (+1.19% cumulative gain in `neutral_healthy` from a
+0.02 risk-on offset) is direct evidence that production's risk dial in
neutral states has a small amount of return-participation headroom.
A Phase II-class intervention that adds a small participation overlay
in calm + healthy + recovery_confirmed states (using existing,
non-Phase-CC features like breadth_sma_43 or trend_persistence) is the
cleanest next exploration.

**Project journey log:** `docs/research/project_journey.md` updated with
Section 47 capturing Phase HH and the formal retirement of the Phase CC
direct portfolio-consumption thread.
