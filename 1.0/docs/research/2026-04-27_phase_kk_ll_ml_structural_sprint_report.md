# Phase KK + Phase LL — Combined ML Refresh + Structural Dual-Bucket Sprint

**Date:** 2026-04-27
**Phase types:** Phase KK = targeted Phase 2B ML refresh (Target A + Group A only); Phase LL = post-hoc structural dual-bucket allocator with W1
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## 1. Commands executed

```
python scripts/phase_kk_targeta_regime_confidence_refresh.py
  └── invokes scripts/build_improvement_artifacts.py with
       BUILD_VERSION_NAMES=improved_phasekk_targeta_confidence_replacement,
                           improved_phasekk_targeta_confidence_blend25,
                           improved_phase2b_regime_confidence_boost
python scripts/research_committee_report.py improved_phasekk_targeta_confidence_replacement --quick
python scripts/phase_ll_dual_bucket_w1_allocator.py
python scripts/research_committee_report.py improved_phasell_w1_bucket_ml_conditional --quick
python scripts/research_committee_report.py improved_phasell_w1_bucket_fixed5 --quick
```

Layer 5 / Layer 6 quick audits **NOT run** — KK1 quick verdict is KEEP AS SHADOW with negative Sharpe (no genuine portfolio improvement); LL candidates all REJECT.

## 2. Files created or modified

Code (created / edited):
- `scripts/phase_kk_targeta_regime_confidence_refresh.py` (new — Phase KK driver)
- `scripts/phase_ll_dual_bucket_w1_allocator.py` (new — Phase LL driver)
- `scripts/build_improvement_artifacts.py` — three additive edits (KK lookup loaders + extend `apply_a` + runtime override of `p_regime` + 2 KK version specs)

Data (Phase KK ML outputs in `data/04_layer2b_risk_regime_engine/`):
- `phase_kk_targeta_regime_confidence_predictions.csv`
- `phase_kk_targeta_model_metrics.csv`
- `phase_kk_targeta_calibration.csv`
- `phase_kk_targeta_stability.csv`
- `phase_kk_targeta_coefficients.csv`

Data (Phase KK portfolio outputs in `data/05_layer3_portfolio_construction/`):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasekk_targeta_confidence_{replacement,blend25}.csv` (6 files via production pipeline)
- `phase_kk_{candidate_metrics_full,state_summary,selection_table}.csv` + `phase_kk_protocol.json`

Data (Phase LL post-hoc dual-bucket outputs):
- `portfolio_version_{returns,weights,sleeve_weights}_improved_phasell_w1_bucket_{fixed5,state_conditional,ml_conditional}.csv` (9 files post-hoc)
- `phase_ll_{candidate_metrics_full,state_summary,selection_table}.csv` + `phase_ll_protocol.json`

Reports:
- `reports/research_committee/improved_phasekk_targeta_confidence_replacement_audit.md`
- `reports/research_committee/improved_phasell_w1_bucket_ml_conditional_audit.md`
- `reports/research_committee/improved_phasell_w1_bucket_fixed5_audit.md`

Docs:
- `docs/research/2026-04-27_phase_kk_ll_ml_structural_sprint_report.md` (this file)
- `docs/research/project_journey.md` — Sections 50 + 51 appended

## 3. Phase KK dataset/model summary

- **Dataset:** 1,109 weekly rows × 15 features (12 Group A regime + 3 Group A Phase 2B predictions). No Phase CC features. No macro proxies.
- **Target:** A — `forward 4w max indicator of stressed_panic` (pos rate 27.7%).
- **Validation:** expanding-window walk-forward; 260w initial train; 26w retrain freq.
- **Model:** sklearn `LogisticRegression(liblinear, max_iter=1000)` with `StandardScaler`.

## 4. Phase KK OOS model metrics

```
            model                  label                            target  n_obs   brier    auc
baseline_existing p_regime_only_inverted     target_A_stress_transition_4w   1097  0.2214  0.7340
     logistic_kk    regime_only_target_a     target_A_stress_transition_4w    849  0.0937  0.8806
```

**58% Brier reduction; AUC 0.73 → 0.88.** This is the core methodological win of Phase KK: the simple Group-A logistic on Target A produces a high-quality, interpretable, walk-forward stress-risk score.

Period stability (4 OOS sub-periods, brier): logistic_kk shows consistent improvement vs baseline in every sub-period.

Top features by magnitude (last fit-window coefficients, standardized): drawdown / breadth / stress / canary breadth / transition probability features dominate. No single feature drives the signal.

## 5. Phase KK portfolio candidate metrics

```
                                      name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_BIL  avg_SPY  avg_turnover
improved_phasekk_targeta_confidence_replacement  0.0699       0.8838            -0.1451       -0.0265   0.2761   0.0714        0.1129
   improved_phasekk_targeta_confidence_blend25   0.0692       0.8834            -0.1418       -0.0263   0.2808   0.0711        0.1129
       improved_phase2b_regime_confidence_boost   0.0689       0.8848            -0.1398       -0.0262   0.2839   0.0708        0.1124
```

Headline deltas (KK1 = replacement vs production):
- ann return: **+0.10pp** (largest in any phase to date)
- Sharpe: **-0.0010** (just below 0.005 gate)
- MDD: **-0.53pp** (just past 0.5pp gate)
- CVaR-5%: -0.03pp (slightly worse but within gate)
- turnover: +0.4% (essentially flat)
- BIL: -0.78pp (slightly lower cash exposure)

State-by-state for KK1: **+6.32% cumulative in `neutral_mixed`** (the largest state-level gain in any post-Phase-Z candidate); -0.39% in `stressed_panic`; ~0 in `calm_trend`. The refreshed score correctly identifies more risk-on opportunities in neutral weeks.

KK2 (75/25 blend) is more conservative: +0.03pp ann return, -0.0014 Sharpe, -0.20pp MDD.

## 6. Phase KK quick verdict

**KEEP AS SHADOW (research reference)** for both KK1 and KK2 (Layer 2). Selection rule REJECTS both: KK1 fails on `sharpe_imp<0.005 (-0.0010)` AND `mdd_worse>0.5pp (-0.53pp)`. KK2 fails on Sharpe.

Per spec, gate for further audits is "KEEP AS SHADOW with **genuine** portfolio improvement." KK1's ann return improves materially (+0.10pp) but Sharpe is slightly negative. The verdict is borderline but per strict reading: skip Layer 5/6 audits.

## 7. Phase LL architecture description

**Post-hoc dual-bucket at the ETF level.** For each week:

```
new_etf_weights = (1 - w_W1) * production_etf_weights + w_W1 * W1_positions
```

The Core bucket is production's saved ETF weights (which already represent 100%). The Structural Defense bucket is the W1 sleeve, holding 6 ETFs (BIL/GLD/TLT/HYG/LQD/DBA). Three w_W1 schedules:

- **LL1** (`fixed5`): w_W1 = 0.05 always.
- **LL2** (`state_conditional`): w_W1 = 0.10 in {`stressed_panic`, `recovery_fragile`, `neutral_mixed`}; 0 in {`calm_trend`, `recovery_confirmed`}.
- **LL3** (`ml_conditional`): w_W1 = clip(p_stress_4w × 0.20, 0, 0.10) using Phase KK's refreshed forward-stress score.

**Limitation honestly reported:** This is post-hoc reconstruction. Unlike Phases FF/HH/JJ/KK which run inside `build_improvement_artifacts.py`, Phase LL adds a new ETF-level layer on top of production's already-saved weights and recomputes net returns with the standard 5bp half-spread cost. The Phase EE diagnosis applies — the layered approach can introduce reconstruction-noise turnover that the production pipeline would otherwise absorb.

## 8. W1 files / sleeves identified

- W1 sleeve name: **`composite_structural_defense_sleeve`**
- Returns file: `data/03_layer2a_strategy_logic/strategy_returns_composite_structural_defense_sleeve.csv` (1,109 rows; 6 columns including gross_return, net_return, turnover, cost, wealth, drawdown)
- Positions file: `data/03_layer2a_strategy_logic/strategy_positions_composite_structural_defense_sleeve.csv` (1,110 rows × 6 ETFs)
- Average ETF holdings: BIL 64.8%, GLD 8.0%, TLT 7.0%, LQD 6.2%, HYG 5.6%, DBA 4.9%

W1 is essentially a "diversified safety sleeve" — heavy cash with small allocations to gold, long Treasuries, IG/HY credit, and commodities.

## 9. Phase LL candidate metrics

```
                                        name  full_ann_return  full_sharpe  full_max_drawdown  full_cvar_5  avg_BIL  avg_turnover  avg_w_w1  max_w_w1
        improved_phasell_w1_bucket_fixed5         0.0595       0.7911            -0.1436       -0.0257   0.3039        0.1077    0.0500   0.0500
improved_phasell_w1_bucket_state_conditional       0.0579       0.7725            -0.1422       -0.0258   0.3017        0.1166    0.0695   0.1000
   improved_phasell_w1_bucket_ml_conditional       0.0601       0.7828            -0.1450       -0.0264   0.2881        0.1128    0.0457   0.1000
   improved_phase2b_regime_confidence_boost        0.0689       0.8848            -0.1398       -0.0262   0.2839        0.1124    0.0000   0.0000
```

**All three LL candidates DEGRADE every axis vs production.** Headline drag is 0.88pp – 1.10pp ann return, Sharpe drag 0.09 – 0.11, MDD modestly worse. Turnover stays essentially equal because the W1 bucket itself has low internal turnover (it's mostly BIL).

## 10. W1 allocation by state (LL3 — ML-conditional, the most informative variant)

```
              state  n  avg_w_w1   ll_minus_prod_cumulative
         calm_trend  295   2.12%             -6.63%
neutral_mixed       492   4.05%            -18.91%
recovery_confirmed   44   1.76%             -0.85%
recovery_fragile    49   4.74%             -0.81%
stressed_panic     229   9.36%             -3.83%
```

The LL3 ML gate concentrates W1 in stressed weeks (9.4% avg) and reduces it in calm weeks (2.1%) — the right direction structurally. **But the post-hoc dual-bucket construction adds defensive drag in every state**, including `stressed_panic` where W1 should help most.

This mirrors the Phase EE finding: post-hoc reconstruction outside the production code path loses fidelity in a way that overwhelms the structural intent.

## 11. Phase LL quick verdict

**REJECT** (Layer 2) for both LL3 and LL1: "Full-window annual return underperforms production by 0.89pp" and "0.95pp" respectively. Not even KEEP AS SHADOW — the headline drag is too large for the strict committee.

## 12. Layer 5/6 quick audits — were they run?

- **Phase KK:** No. KK1's quick verdict is KEEP AS SHADOW but Sharpe is slightly negative; per spec, "genuine portfolio improvement" gate not met. Skip.
- **Phase LL:** No. LL candidates REJECT outright. Running Layer 5/6 would not change the decision.

## 13. Best overall candidate

**KK1 (`improved_phasekk_targeta_confidence_replacement`)** is the strongest portfolio candidate of this combined sprint — and the strongest candidate produced anywhere in the post-Phase-Z arc on annual return improvement (+0.10pp). But it still fails the strict 9-gate selection rule by tiny margins (Sharpe -0.001 just below threshold; MDD -0.53pp just past threshold).

LL candidates are all worse than production; do not consider them.

## 14. Final decision

**REJECT all Phase KK and Phase LL portfolio candidates** under the strict selection rules.

**KEEP AS SHADOW (research reference)** for KK1 — it is the largest ann-return improvement in this project's recent history, and the underlying ML model is a major prediction-quality win.

**Production pin remains unchanged**: `improved_phase2b_regime_confidence_boost`. **Shadow pin remains unchanged**: `improved_phase2b_combo_abc`.

## 15. Should the ML path continue?

**Yes — focused on PRODUCTION RETRAIN, not on additional regime-confidence-multiplier candidates.**

Two specific recommendations:

1. **Retrain the production `p_regime_confidence` model with Target A's definition and Group A features only.** Phase KK has now confirmed (independently from Phase JJ) that this configuration produces a 58% Brier improvement and 0.88 AUC. This is a Phase 2B operational refresh, not a new portfolio candidate. The retrained score would be the new `p_regime_confidence` baseline — production's pin name stays the same; only the underlying ML model changes.

2. **Do NOT add refined-state, deterioration_z, defensive_overlay_hint, or macro-proxy features to the retrain.** Phase JJ's walk-forward evidence is unambiguous on this — they hurt OOS Brier despite helping in fixed-shift ablations.

The retrain should be tested against production's existing pin under the standard 8-gate Phase D rule. If the retrain alone improves all 8 gates (likely YES on prediction quality, UNCERTAIN on portfolio metrics given the saturation found in Phase JJ), it can replace the current p_regime_confidence ML inside the existing pin without changing any other production logic.

## 16. Should the structural allocator path continue?

**Conditionally yes, but NOT via post-hoc dual-bucket.** The Phase LL architecture (post-hoc ETF layering) has the same reconstruction-fidelity problem that defeated Phase EE. To extract value from a structural dual-bucket allocator, the W1 bucket must be integrated INSIDE the production code path — analogous to how Phase FF fixed Phase DD/EE's post-hoc problem.

The right architecture: a Phase MM-class change that:
1. Modifies `subset_sleeves` in the production version spec to include `composite_structural_defense_sleeve` as a separately-treated sleeve.
2. Modifies `apply_state_conditioned_tilt` (or a new function in front of the HRP allocator) to allocate a fixed or state-conditional fraction of the portfolio to W1 BEFORE the HRP-weighted Core bucket is computed.
3. Lets the existing per-sleeve cap, lighter_both overlay, and cost machinery run on the integrated portfolio.

This is more invasive but is the only structural path with material expected portfolio headroom that has not been thoroughly tested. Given the recurring "post-hoc reconstruction loses fidelity" pattern across DD/EE/LL, future structural work should be built directly inside the production allocator.

## 17. What to do next

**Recommended ordering for the next phases:**

1. **Phase MM (or equivalent — operational, not a new research phase):** Retrain `p_regime_confidence` using Phase KK's specification (Target A, Group A features only, walk-forward logistic). This is a single targeted change to `scripts/build_phase2b_meta_predictions.py`. Validate against production's existing `improved_phase2b_regime_confidence_boost` baseline under the standard 8-gate rule.

2. **Phase NN (or equivalent — structural, in-allocator):** A dual-bucket allocator with W1 as a separate, fixed-weight defensive bucket integrated inside `build_improvement_artifacts.py`. Match the Phase FF pattern (no post-hoc reconstruction).

3. **Stop pursuing additional regime-confidence-multiplier candidates** — that surface is saturated. Six consecutive sprints (HH / II / JJ / KK and the failed DD / EE / FF / GG offensive-multiplier sweep) have produced consistent positive-but-tiny portfolio improvements that fail the strict Sharpe gates.

4. **Stop pursuing post-hoc dual-bucket variants** — Phases EE and LL both confirm the same reconstruction-fidelity problem. Either go in-allocator or stop.

**If both Phase MM and Phase NN fail:** consider the project's current production pin essentially state-of-the-art on this dataset under the strict 8-gate rule. The natural next step would then be an evaluation-rule recalibration discussion (whether the strict rule is filtering noise or filtering signal) rather than another small-magnitude variant.

## Appendix — combined decision matrix per spec

| condition | result | action |
|---|---|---|
| KK improves prediction but not portfolio | TRUE | Mark KK ML-research useful; recommend retrain of p_regime_confidence |
| LL improves portfolio | FALSE | Do NOT continue post-hoc dual-bucket variants |
| Neither improves portfolio | TRUE | Retire small intervention surfaces; recommend in-allocator W1 integration as the next structural test |
| LL works but KK does not | FALSE | n/a |
| KK works but LL does not | TRUE (KK works at prediction layer) | Continue Phase 2B ML refresh path via operational retrain |
| Both work | FALSE | n/a |
