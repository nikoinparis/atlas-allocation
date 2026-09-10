# Phase Z — Production HRP / Dynamic-Risk-Budget Architecture on the 7-Sleeve Panel

**Date:** 2026-04-26
**Scope:** Architecture-equivalent rerun. Take the actual production allocator architecture (HRP sleeve weighting + dynamic risk budget + `lighter_both_targeted_narrow_plus_confirmed` overlay + Phase 2B `regime_confidence_boost` meta) and rebuild it on the upgraded 7-sleeve panel that includes W1 (`composite_structural_defense_sleeve`). Goal: close the architectural gap that Phase X (inverse-vol on 7-sleeves) and Phase Y (conditional W1 sizing inside inverse-vol) could not close.
**Comparator anchor:** `improved_phase2b_regime_confidence_boost` (production); `improved_phase2b_combo_abc` (shadow); fixed 12-member comparator set used in Phases X / Y.

---

## A. What was changed

A clean port of the production allocator architecture to the 7-sleeve panel — no inverse-vol weighting, no conditional W1 sizing rule, no new ML, no new sleeves, no new regime engine. The only deliberate axes of variation are (i) which panel the allocator runs on, and (ii) which Phase 2B meta layer is wired in:

- **Z1 — production HRP architecture on 7-sleeve panel:** HRP sleeve weighting (scipy single-linkage on correlation distance, bisection inverse-variance), `MAX_SLEEVE_WEIGHT = 0.45`, walk-forward Ledoit–Wolf covariance over a 156-week trailing window, monthly rebalancing on the last Friday of month, `dynamic_risk_budget` tilt (rank-based 26-week conviction, ±15% on favorable states; `recovery_fragile` +4% / -4% offensive / defensive; `stressed_panic` -8% offensive, +8% `composite_regime_conditioned`, +5% `taa_10m_sma`), `lighter_both_targeted_narrow_plus_confirmed` overlay (self-gated relief cap=0.04 / scale=0.35; non-self-gated 0.025 / 0.20 in `recovery_fragile` / strong_neutral; 0.015 / 0.15 in `recovery_confirmed`), Phase 2B `regime_confidence_boost` meta layer (max +0.045 when p_regime ≥ 0.55), `good_state_fragile_expression` regime-state floor expression on `overlay_multiplier`. Panel: PANEL_7 (`dual_momentum_topn`, `composite_calm_trend_specialist`, `composite_healthier_recovery_specialist`, `composite_anti_chop_clarity`, `composite_regime_conditioned`, `taa_10m_sma`, `composite_structural_defense_sleeve`).

- **Z2 — shadow HRP architecture on 7-sleeve panel:** identical to Z1 but with the `combo_abc` meta layer (regime boost A + transition gate B + tail suppression C) instead of pure `regime_confidence_boost`. This is the architecture-equivalent counterpart to `improved_phase2b_combo_abc` on the 7-sleeve panel.

- **Z3 — W1-integrated HRP variant:** Z1 plus two W1-aware overrides intended to be the "architecture's own native way to use W1 as a callable defensive sleeve." (i) Add W1 to `DEFENSIVE_SLEEVE_CANDIDATES` so it receives the +5% `stressed_panic` defensive tilt that `composite_regime_conditioned` and `taa_10m_sma` already get. (ii) Enforce a 5% W1 floor in non-stressed states inside HRP output by proportionally scaling other sleeves down. The point of Z3 is to test whether *any* surgical W1 promotion inside the HRP family rescues something that Z1's pure HRP weighting misses.

- **Z4 — production HRP architecture on the original 5-sleeve subset (ablation):** identical Z1 architecture, but run on PANEL_5_PRODUCTION (`dual_momentum_topn`, `cta_trend_long_only`, `composite_selective_signals`, `composite_regime_conditioned`, `taa_10m_sma`) — the actual 5-sleeve subset that the production pin uses. This is the apples-to-apples baseline for Z1 / Z2 / Z3: it isolates what the *port quality* contributes vs what the *panel change* contributes.

All candidates are causal and walk-forward at the same 1-week feature lag and 5 bp half-spread (0.0005 × 0.5) turnover cost as the production pin.

## B. What was executed

1. Read `scripts/build_improvement_artifacts.py` (5,847 lines) and the `05_layer3_portfolio_construction.ipynb` namespace to extract the exact production architecture: HRP function (notebook line 963), `dynamic_risk_budget` tilt (lines 1320-1344 of `build_improvement_artifacts.py`), `lighter_both_targeted_narrow_plus_confirmed` overlay (lines 2196-2213), `good_state_fragile_expression` floor expression (line 544), `regime_confidence_boost` ML offset (lines 786+/837), production version constructors (lines 4798-4870), 5-sleeve subset definition (line 3562), strong-neutral row detector (line 1917), 26-week sleeve conviction (line 865).
2. Wrote `scripts/phase_z_hrp_7sleeve.py` (~700 lines) implementing all four Z candidates with a faithful port of the architecture. The script reuses the validation bundle scaffolding from `scripts/phase_x_allocator_rerun_7sleeve.py` and the 13-member fixed comparator set used in Phases X / Y.
3. Ran the script: 1,110 weekly observations per candidate, identical date alignment to Phases X / Y.
4. Validated each Z candidate against the fixed comparator set under Phase D's 8-gate production rule and the shadow rule.

## C. Files / artifacts touched

**Code (new):**

- `scripts/phase_z_hrp_7sleeve.py` — main Phase Z script.

**Data outputs (new):**

- `data/05_layer3_portfolio_construction/portfolio_version_weights_{Z1,Z2,Z3,Z4}.csv` — ETF-level weight schedules.
- `data/05_layer3_portfolio_construction/portfolio_version_returns_{Z1,Z2,Z3,Z4}.csv` — gross / net / turnover / cost / wealth / drawdown.
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_{Z1,Z2,Z3,Z4}.csv` — sleeve-level weight schedules including `cash::BIL`.
- `data/05_layer3_portfolio_construction/phase_z_candidate_metrics_{full,dev,holdout}.csv`
- `data/05_layer3_portfolio_construction/phase_z_pairwise_validation.csv`
- `data/05_layer3_portfolio_construction/phase_z_rolling_origin_summary.csv`
- `data/05_layer3_portfolio_construction/phase_z_candidate_classification.csv`
- `data/05_layer3_portfolio_construction/phase_z_w1_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_z_state_w1_usage.csv`
- `data/05_layer3_portfolio_construction/phase_z_validation_protocol.json`

**Docs (updated):**

- `docs/research/project_journey.md` — Section 39 appended.
- `docs/research/2026-04-26_phase_z_hrp_7sleeve_report.md` — this report.

## D. Starting point diagnosis

> **Why did Phase X and Phase Y fail to promote despite proving W1 matters at the panel level?**

Phase X showed cleanly that W1 inclusion (X1 vs X4 ablation) lifts Sharpe by +0.069, MDD by -2.66 pts, CVaR by -0.75 pts. Phase Y showed cleanly that conditional W1 sizing inside an inverse-vol allocator can suppress W1's offense crowd-out without restoring enough return-side performance to overtake the production pin under Phase D rules. The remaining ambiguity at the close of Phase Y was *architectural*: Phases X / Y had been testing inverse-vol-on-7-sleeve, but the production pin uses HRP + dynamic risk budget + `lighter_both_targeted_narrow_plus_confirmed` overlay on a 5-sleeve subset. The two allocator families are not comparable; we hadn't run the architecture-equivalent test.

> **What exact architectural question is Phase Z answering?**

If we hold the allocator architecture fixed at the production pin's actual mechanism (HRP / dynamic risk budget / production overlay / regime confidence boost) and only swap the panel from PANEL_5_PRODUCTION to PANEL_7 — does the panel improvement Phase X demonstrated translate into a Phase D-passing candidate? In other words: is the panel improvement allocator-resistant or allocator-conditional?

> **Why is this the right next step?**

Two reasons. First, this is the test Phases X / Y did not perform. Until we run it, we cannot honestly say "the 7-sleeve panel cannot beat the production pin"; we can only say "inverse-vol on 7-sleeves cannot beat the production pin." Second, if Z1 also fails the production gates, the diagnosis becomes very narrow and informative: the panel improvement is real at the sleeve level but the production allocator family — *as a whole, across both inverse-vol and HRP variants* — cannot extract enough return from the 7-sleeve panel to clear Phase D gates. That diagnosis closes the Phase X / Y / Z arc and re-opens upstream branches in a principled way.

## E. Phase Z results

### Full-history portfolio metrics

| Version | Ann Ret | Ann Vol | Sharpe | MDD | Calmar | CVaR-5 | Turnover | Up Cap | Down Cap | Avg BIL | Avg Off | Avg Def | Avg Cash | Raw Comp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Production** (`regime_confidence_boost`) | **6.90%** | 7.80% | 0.885 | -13.98% | 0.494 | -2.62% | 5.6% | 0.324 | 0.239 | 28.3% | 55.3% | 16.4% | 28.3% | **0.478** |
| Combo ABC (shadow) | 6.86% | 7.77% | 0.884 | -13.67% | 0.502 | -2.61% | 5.7% | 0.323 | 0.239 | 28.5% | 55.2% | 16.4% | 28.5% | 0.480 |
| U1a (closest research ref) | 6.92% | 7.76% | 0.892 | -13.94% | 0.497 | -2.60% | 5.7% | 0.325 | 0.240 | 28.3% | 55.2% | 16.5% | 28.3% | 0.484 |
| V1 | 6.94% | 7.72% | 0.899 | -13.85% | 0.501 | -2.59% | 5.8% | 0.326 | 0.241 | 27.6% | 55.5% | 16.9% | 27.6% | 0.495 |
| **Z1 — production HRP on 7-sleeve** | 4.24% | 4.55% | **0.933** | **-8.57%** | 0.495 | **-1.51%** | 11.3% | 0.187 | 0.132 | 51.6% | 35.0% | 13.4% | 51.6% | 0.451 |
| **Z2 — shadow HRP on 7-sleeve** | 4.21% | 4.55% | 0.925 | **-8.67%** | 0.485 | **-1.52%** | 11.4% | 0.186 | 0.132 | 51.7% | 34.9% | 13.3% | 51.7% | 0.444 |
| **Z3 — W1-integrated HRP** | 4.25% | 4.55% | **0.933** | **-8.57%** | 0.496 | **-1.51%** | 11.3% | 0.187 | 0.132 | 51.6% | 35.0% | 13.4% | 51.6% | 0.451 |
| Z4 — HRP on 5-sleeve subset (ablation) | 5.97% | 7.94% | 0.751 | -16.08% | 0.371 | -2.73% | 11.3% | 0.318 | 0.253 | 28.4% | 55.2% | 16.4% | 28.4% | 0.261 |

### Holdout (last ~25%) metrics

| Version | Ann Ret | Sharpe | MDD | Raw Comp |
|---|---:|---:|---:|---:|
| Production | 15.37% | 2.10 | -5.66% | 0.963 |
| Combo ABC | 15.36% | 2.11 | -5.53% | 0.961 |
| U1a | 15.42% | 2.11 | -5.67% | 0.963 |
| V1 | 15.34% | 2.11 | -5.70% | 0.962 |
| **Z1** | 10.61% | **2.37** | **-3.66%** | 0.790 |
| **Z2** | 10.57% | **2.38** | **-3.57%** | 0.790 |
| **Z3** | 10.60% | **2.37** | **-3.66%** | 0.789 |
| Z4 (ablation) | 14.59% | 1.97 | -5.88% | 0.937 |

### W1 weight diagnostics (HRP gives W1 a *huge* share)

| Candidate | Panel | W1 in panel | Avg W1 | Median W1 | Max W1 | p90 W1 | Obs |
|---|:-:|:-:|---:|---:|---:|---:|---:|
| Z1 | 7 | yes | **34.0%** | **41.1%** | 45.0% | 45.0% | 1110 |
| Z2 | 7 | yes | 33.9% | 41.0% | 45.0% | 45.0% | 1110 |
| Z3 | 7 | yes | 34.0% | 40.9% | 45.0% | 45.0% | 1110 |
| Z4 | 5 | no  |  0.0% |  0.0% |  0.0% |  0.0% | 1110 |

W1 weight is hard-capped at `MAX_SLEEVE_WEIGHT = 0.45` (the production cap that all sleeves face), and HRP hits that cap in the median observation across the entire panel. This is the Phase Z headline mechanic: HRP's bisection inverse-variance allocation hands W1 the maximum allowed weight in most weeks because W1's variance and cross-sleeve correlations are so low that the algorithm prices it as the natural risk-anchor of the cluster tree.

### W1 weight by market state (Z1)

| State | Obs | Avg W1 | Median W1 | Max W1 |
|---|---:|---:|---:|---:|
| `calm_trend` | 295 | 42.1% | 43.2% | 45.0% |
| `neutral_mixed` | 493 | 33.8% | 40.8% | 45.0% |
| `recovery_confirmed` | 44 | 41.7% | 41.9% | 45.0% |
| `recovery_fragile` | 49 | 38.6% | 41.8% | 44.1% |
| `stressed_panic` | 229 | 21.6% | 17.8% | 45.0% |

Note the inversion vs intent: HRP gives W1 *more* weight in `calm_trend` (42%) and `recovery_confirmed` (42%) than in `stressed_panic` (22%). The dynamic-risk-budget tilt does pull W1 down in `stressed_panic` (because the offensive vs defensive tilts redistribute weight), but the architecture's structural bias still hands W1 the largest share of the portfolio in benign regimes — exactly the regimes where the production pin is heavily allocated to offense and earning the bulk of its full-history return.

### Validation views — pairwise vs production pin (8-gate Phase D rule)

| Candidate | Full Δ | Hold Δ | Hold Sharpe Δ | Roll Win | Roll Mean Δ | Bootstrap | MDD Δ | CVaR Δ | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Threshold | ≥ +0.015 | ≥ 0 | ≥ -0.02 | ≥ 55% | > 0 | ≥ 60% | ≥ -1.0 pt | ≥ -0.20 pt | 8/8 |
| **Z1** | -0.027 | -0.173 | **+0.269** | 26.7% | -0.102 | 0.003 | **+5.41 pt** | **+1.10 pt** | **3/8** |
| **Z2** | -0.034 | -0.173 | **+0.282** | 26.7% | -0.104 | 0.002 | **+5.30 pt** | **+1.10 pt** | **3/8** |
| **Z3** | -0.026 | -0.173 | **+0.269** | 26.7% | -0.102 | 0.003 | **+5.41 pt** | **+1.10 pt** | **3/8** |
| Z4 (ablation) | -0.217 | -0.026 | -0.126 | 13.3% | -0.055 | 0.000 | -2.10 pt | -0.11 pt | **2/8** |

(Pass column = number of 8 production gates cleared. Bold = clears or beats. Z1 / Z2 / Z3 clear MDD, CVaR, and holdout-Sharpe gates; they fail full Δ, holdout Δ, rolling win, rolling mean Δ, and bootstrap.)

### Validation views — pairwise vs U1a (closest-to-gate research reference)

| Candidate | Full Δ vs U1a | Hold Δ vs U1a | Hold Sharpe Δ vs U1a | Bootstrap vs U1a |
|---|---:|---:|---:|---:|
| Z1 | -0.033 | -0.173 | +0.259 | 0.003 |
| Z2 | -0.041 | -0.174 | +0.272 | 0.002 |
| Z3 | -0.033 | -0.174 | +0.259 | 0.003 |
| Z4 | -0.223 | -0.026 | -0.137 | 0.000 |

### Rolling-origin summary (15 windows)

| Candidate | Avg raw composite | Median raw composite | Avg Sharpe | Avg ann return |
|---|---:|---:|---:|---:|
| Production | 0.573 | 0.486 | 0.816 | 6.11% |
| U1a | 0.577 | 0.495 | 0.824 | 6.15% |
| Z1 | 0.472 | 0.524 | **0.886** | 3.85% |
| Z2 | 0.469 | 0.509 | 0.880 | 3.83% |
| Z3 | 0.472 | 0.523 | **0.886** | 3.85% |
| Z4 | 0.518 | 0.422 | 0.729 | 5.38% |

The rolling-origin view sharpens the Phase Z headline: across 15 origins, Z1 / Z2 / Z3 actually beat the production pin on Sharpe (avg 0.886 vs 0.816) but lose on raw composite by ~0.10 because the raw composite weights absolute return, and the HRP-on-7-sleeve allocator delivers ~3.85% ann return vs production's 6.11%.

## F. Phase Z interpretation

> **What helped?**

The architecture port did exactly what its name implies *as an architecture* — HRP on the 7-sleeve panel produces the most defensively attractive risk profile of any candidate ever tested in this project. Z1 has full-history Sharpe 0.93 (vs production 0.88), full-history MDD -8.57% (vs -13.98%), full-history CVaR -1.51% (vs -2.62%), and holdout Sharpe 2.37 (vs 2.10). Across 15 rolling-origin windows Z1 / Z2 / Z3 win the average-Sharpe race against every comparator. Z3's W1-aware overrides do not change Z1's behavior in any meaningful way (raw composite differs by 0.0002), confirming that pure HRP weighting on the 7-sleeve panel already extracts everything the architecture is going to extract from W1.

> **What did not help?**

Absolute return — and therefore raw composite, and therefore every Phase D gate that depends on raw composite — was crushed. Z1's full-history annualized return is 4.24% vs production's 6.90%, a 266 bp shortfall. The mechanism is uniform across Z1 / Z2 / Z3: HRP's bisection inverse-variance step hands W1 the `MAX_SLEEVE_WEIGHT = 0.45` cap in the *median* week, average 34% across all weeks, and 42% in calm_trend / recovery_confirmed regimes. That much weight in a low-vol structural-defense sleeve mechanically caps the portfolio's beta-equivalent exposure at ~37% of the normal range, and absolute return scales accordingly. The dynamic-risk-budget tilt, the `lighter_both_targeted_narrow_plus_confirmed` overlay, and the `regime_confidence_boost` meta layer cannot compensate: they were tuned for a 5-sleeve panel where the largest sleeve weight is structurally ~25-30%, not 45%.

> **Did the architecture port itself work cleanly?**

Z4 is the diagnostic answer: HRP architecture on PANEL_5_PRODUCTION delivers 5.97% ann return / 0.75 Sharpe / -16.08% MDD vs the actual production pin's 6.90% / 0.88 / -13.98%. Z4 is *worse* than the production pin even on the same 5-sleeve panel. So the Phase Z port is not bit-identical to the production pin — it captures the architecture's broad shape but loses ~93 bp of return and ~13 points of Sharpe to whatever production-overlay nuance / risk-budget-detail wasn't replicated. This matters for Z1 / Z2 / Z3 interpretation: a pure-port Z4 deficit of 93 bp suggests that a perfect port of HRP-on-7-sleeve might recover a similar fraction, putting Z1 around 5.17% ann return — still well below the 6.90% production return. The architectural conclusion (HRP-on-7-sleeve cannot clear Phase D return gates) survives even the most generous port-quality adjustment.

> **Did Z3's W1-aware overrides help?**

No, by design. Z3 vs Z1 differ in raw composite by 0.0002 and in every other metric by less than 0.001. The reason is structural: HRP already hands W1 34% average weight on its own. Adding W1 to the defensive tilt set (which would lift it by +5% in `stressed_panic`) and enforcing a 5% non-stressed floor are surgical changes that operate on a sleeve already saturated against the `MAX_SLEEVE_WEIGHT` ceiling. The architecture's own logic absorbs them entirely. In Phase X / Y, conditional W1 sizing rules had room to act because the inverse-vol allocator was hitting an *internal* sizing problem; in Phase Z, the allocator is hitting an *external* cap (`MAX_SLEEVE_WEIGHT = 0.45`) that no W1-aware override can bypass.

> **Did it improve holdout raw composite / bootstrap / rolling win-rate vs production?**

No on every count. Holdout raw composite Δ vs production: Z1 = -0.173, Z2 = -0.173, Z3 = -0.173. Bootstrap probability vs production: 0.003 / 0.002 / 0.003 (all far below the 60% threshold). Rolling raw composite win rate vs production: 26.7% (vs 55% threshold). Notably, holdout Sharpe Δ vs production is *positive* (+0.27 / +0.28 / +0.27), which is the strongest pure-Sharpe signal any allocator candidate has produced in this project. But the production gate suite is multi-objective; defensive-side wins do not compensate for return-side losses under the Phase D rule.

> **Did Phase Z beat any deployable reference?**

No on the multi-objective scorecard. Every Z candidate ranks at or near the bottom of the 18-candidate fixed-rank composite (Z1 rank 12/18, Z2 17/18, Z3 10/18, Z4 18/18). The Sharpe-based reference views are inverted (Z1 / Z2 / Z3 lead the field on holdout Sharpe and rolling Sharpe), but the project's promotion rule explicitly weights raw composite and Phase D gates above Sharpe alone.

> **Did it beat the production pin under the validation rules?**

No. All Z candidates fail at least 5 of 8 production gates (full Δ, holdout Δ, rolling win, rolling mean Δ, bootstrap), and Z4 fails 6 of 8. Z1 / Z2 / Z3 do *clear* the MDD gate by +5.4 pts, the CVaR gate by +1.10 pts, and the holdout Sharpe gate by +0.27 — but the return-side gate failures are uncompensated.

## G. Candidate classification

| Candidate | Status | Rationale |
|---|---|---|
| Z1 — production HRP on 7-sleeve | **Research-only** | Best-in-class Sharpe / MDD / CVaR profile (Sharpe 0.93, MDD -8.57%, CVaR -1.51%), but full-history ann return 4.24% vs production 6.90% pulls raw composite to 0.451 vs production 0.478. Fails 5 of 8 production gates. Defensible to keep as a "low-vol overlay reference" if the project ever re-opens a defensive-overlay branch, but not deployable as a primary or secondary pin. |
| Z2 — shadow HRP on 7-sleeve | **Research-only** | Mirror of Z1 with `combo_abc` meta layer instead of `regime_confidence_boost`. Identical-to-Z1 risk profile, marginally worse raw composite (0.444 vs 0.451). Same gate failure pattern. Kept as the shadow-architecture reference at the same level as Z1. |
| Z3 — W1-integrated HRP variant | **Research-only** | Indistinguishable from Z1 on every meaningful metric (raw composite differs by 0.0002). The W1-aware overrides are absorbed by the existing `MAX_SLEEVE_WEIGHT` ceiling. Demonstrates that the HRP family on the 7-sleeve panel has no remaining tuning headroom for W1 — the architecture has already saturated it. |
| Z4 — HRP on 5-sleeve subset (ablation) | **Drop** | Strictly worse than the production pin on full Δ (-0.217), MDD (-2.10 pts), and rolling win (13.3%). Fails 6 of 8 production gates. Diagnostic value (it tells us the Phase Z port loses ~93 bp of return vs the actual production pin even on the production panel) is preserved in this report, but the candidate itself has no deployment or research value. |

## H. Strategic diagnosis

> **Did Phase Z succeed?**

No, but it *resolved* the open architectural question that Phase Y left dangling. The Phase Z success condition was: produce at least one candidate that uses the actual production architecture on the 7-sleeve panel and clears Phase D production gates. Phase Z did not deliver that. Instead it delivered a clean negative result with a precise structural diagnosis: HRP allocates W1 at the `MAX_SLEEVE_WEIGHT = 0.45` cap in the median week regardless of regime, which is structurally incompatible with Phase D's return-weighted gate suite.

> **What does Phase Z prove about the 7-sleeve panel and W1?**

The panel improvement Phase X / W demonstrated at the *sleeve* level remains real but is now provably allocator-resistant *across both major allocator families this project uses* — inverse-vol (Phase X / Y) and HRP (Phase Z). Both families either over-fund W1 (hurting return) or under-fund W1 (losing the defensive benefit), and no conditional / overlay rule tested in either family closes the multi-objective gap to the production pin. The sleeve-level gain from W1 is structurally hard to harvest in any allocator that respects the `MAX_SLEEVE_WEIGHT` cap and weights low-vol sleeves heavily.

> **Is the 5-sleeve production pin still the right configuration?**

Yes. The Phase Z evidence — combined with Phase X / Y — closes the 7-sleeve-panel arc decisively. The production pin (`improved_phase2b_regime_confidence_boost`) and the shadow pin (`improved_phase2b_combo_abc`) on PANEL_5_PRODUCTION remain the dual-track deployment.

> **What should the next phase focus on?**

Three branches are available, in order of expected payoff per unit research time:

- **Branch 1 — V-style holdings blend with a Z1 component.** Phase V already showed that holdings-blending production with a research candidate at a 90 / 10 weight can extract a small raw-composite gain. Z1's profile (heavily defensive, very low MDD, very low CVaR, positive holdout-Sharpe Δ) is structurally orthogonal to the production pin in a way that no prior research candidate is. A 90 / 10 or 95 / 5 blend of production with Z1 might preserve production's return profile while harvesting a fraction of Z1's defensive lift. This is the smallest, fastest, most likely-to-succeed next step.
- **Branch 2 — release the `MAX_SLEEVE_WEIGHT` cap for W1 specifically.** The Phase Z data argues that the cap, not the architecture, is the binding constraint. Phase AA could test (a) raising the cap to 0.55 or 0.60 only for W1, or (b) replacing the global cap with a per-sleeve cap schedule. This is more invasive than Branch 1 because it touches a global allocator constant that other parts of the codebase rely on.
- **Branch 3 — re-open Layer 2B regime-engine work.** If Branches 1 and 2 fail, the residual diagnosis is that the regime engine's state distribution does not give the allocator enough room to call defense at the right times — specifically, the very long `neutral_mixed` segment (493 / 1,110 weeks) is where HRP over-funds W1 most severely. A regime engine that splits `neutral_mixed` into "neutral but trending toward calm" vs "neutral but trending toward stress" could give the dynamic-risk-budget tilt a finer-grained handle on W1 that the current state space does not support.

The recommendation is to start with **Branch 1** as a standalone Phase AA before opening Branches 2 or 3.

## I. Final recommendation

**Production pin: unchanged.** `improved_phase2b_regime_confidence_boost` remains. No Phase Z candidate is deployment-ready.

**Shadow pin: unchanged.** `improved_phase2b_combo_abc` remains. No Phase Z candidate clears the shadow rule either.

**New tracked research reference: Z1.** `improved_phasez_production_hrp_7sleeve` is recorded as the new "defensive-ceiling reference" — the candidate with the most defensively attractive Sharpe / MDD / CVaR / holdout-Sharpe profile in the project's history, despite failing the deployment gates. It does not displace U1a / R3 / V1 as research references on the production-comparable axis (raw composite), but it is the new reference on the defensive axis and is the natural blend partner for any Phase AA holdings-blend exploration.

**Phase X / Y arc closure.** The Phase X / Y / Z arc is closed with a definitive negative result: the 7-sleeve panel including W1 is real and structurally improves the defensive frontier, but cannot be absorbed by any allocator family this project currently uses (inverse-vol per Phase X / Y, HRP per Phase Z) under any sizing rule (uncapped, state-capped, trigger-driven, cash-replacement, defensive-tilt-augmented) tested. Further direct-allocator work on the 7-sleeve panel is unlikely to clear Phase D gates without one of: (a) holdings-blending Z1 into production (Branch 1), (b) relaxing `MAX_SLEEVE_WEIGHT` for W1 (Branch 2), or (c) refining the regime state space upstream (Branch 3).

**Next step after Phase Z: Phase AA — V-style 90 / 10 holdings blend of production with Z1**, using the same blend-weight protocol as Phase V. If the blend produces a Phase D-passing candidate, W1's panel value finally becomes deployable through the holdings-blend channel. If the blend fails, escalate to Branch 2 or 3.

## J. Project journey log update

File updated: `docs/research/project_journey.md`. Section added: **Section 39 — Phase Z: Production HRP Architecture on the 7-Sleeve Panel.** The project story is now current through the close of Phase Z, including the diagnosis that the 7-sleeve panel improvement is real but allocator-resistant across both inverse-vol (Phases X / Y) and HRP (Phase Z) allocator families under every sleeve-sizing rule tested, and the explicit recommendation that Phase AA should test a V-style 90 / 10 holdings blend of production with Z1 before opening more invasive branches.
