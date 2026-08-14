# Phase Y — Conditional W1 Sizing Inside the Production Allocator Family

**Date:** 2026-04-25
**Status:** Closed — none of the Y candidates promote; structural conflict diagnosed.
**Production pin:** `improved_phase2b_regime_confidence_boost` (unchanged).
**Shadow pin:** `improved_phase2b_combo_abc` (unchanged).

---

## A. What was changed

Three new candidates inside the production allocator family, each varying only the W1 sizing rule. No new sleeves, no new ML, no trust-layer or regime-engine changes. The 7-sleeve panel from Phase W is the input universe in Y1 and Y2; Y3 runs the production architecture on the 6-sleeve panel and overlays W1 on top.

- **Y1 — `improved_phasey_state_capped_w1`** — production architecture (inverse-vol + state risk multiplier + Phase 2B `regime_confidence_boost`) on the 7-sleeve panel, with explicit per-state caps on the W1 sleeve weight: 5% calm_trend, 8% neutral_mixed, 10% recovery_confirmed, 18% recovery_fragile, 0% stressed_panic (already zero via state mult). Excess weight beyond the cap is redistributed to the other six sleeves in proportion to their existing inverse-vol weight.
- **Y2 — `improved_phasey_trigger_driven_w1`** — base inverse-vol on the six non-W1 sleeves; W1 weight set by an explicit defensive trigger score in [0, 1] combining (i) recent 13-week SPY drawdown depth, (ii) Phase 2B `p_tail_risk`, (iii) `1 − p_regime_confidence`. W1 weight = 2% floor + score × 23%, bounded [2%, 25%]. Other sleeves split (1 − W1 weight) by inverse-vol.
- **Y3 — `improved_phasey_cash_replacement_w1`** — production architecture exactly on the 6-sleeve panel (X4 logic). Then a fraction of the cash share equal to (trigger score × 50%) is redirected to W1. W1 enters only by displacing cash, never by displacing offense. Most production-consistent integration.

All three use 1-week-lagged sleeve features, 156-week trailing inverse-vol, walk-forward state and Phase 2B predictions, and the same 5 bp half-spread turnover model as Phase X.

## B. What was executed

- **Code change:** new file `scripts/phase_y_conditional_w1_sizing.py` (~700 lines) building Y1, Y2, Y3 on top of `phase_x_allocator_rerun_7sleeve.py` infrastructure.
- **Run:** `python3 scripts/phase_y_conditional_w1_sizing.py` — built the three candidates, ran W1 diagnostics + state-conditional W1 usage tables + per-quintile trigger diagnostics, ran the validation bundle against the full Phase X comparator set extended with all four Phase X candidates (X1–X4) as additional reference points.
- **Research consulted (briefly):** AQR's defensive-equity work and ReSolve / Newfound on conditional risk budgeting and drawdown-aware exposure control, used to justify the explicit-cap and trigger-driven approaches as the right interpretable family to test inside a production allocator. No design borrowed from outside the project.

## C. Files / artifacts modified or regenerated

New code:
- `scripts/phase_y_conditional_w1_sizing.py`

New portfolio outputs (3 candidates × 3 frames):
- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phasey_{state_capped,trigger_driven,cash_replacement}_w1.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phasey_{state_capped,trigger_driven,cash_replacement}_w1.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phasey_{state_capped,trigger_driven,cash_replacement}_w1.csv`

New validation outputs:
- `data/05_layer3_portfolio_construction/phase_y_candidate_metrics_full.csv`
- `data/05_layer3_portfolio_construction/phase_y_candidate_metrics_dev.csv`
- `data/05_layer3_portfolio_construction/phase_y_candidate_metrics_holdout.csv`
- `data/05_layer3_portfolio_construction/phase_y_pairwise_validation.csv`
- `data/05_layer3_portfolio_construction/phase_y_rolling_origin_summary.csv`
- `data/05_layer3_portfolio_construction/phase_y_candidate_classification.csv`
- `data/05_layer3_portfolio_construction/phase_y_w1_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_y_state_w1_usage.csv`
- `data/05_layer3_portfolio_construction/phase_y_trigger_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_y_w1_ablation_table.csv`
- `data/05_layer3_portfolio_construction/phase_y_validation_protocol.json`

Docs updated:
- `docs/research/2026-04-25_phase_y_conditional_w1_sizing_report.md` (this file).
- `docs/research/project_journey.md` — Section 38 appended.

## D. Starting-point diagnosis

Why did Phase X fail to promote despite proving W1 matters?

Phase X established two separable facts:
1. The 7-sleeve panel (with W1) genuinely improves allocator quality on Sharpe (+0.069), MDD (-2.66pt), CVaR (-0.75pt), and turnover (-5.6pt) under the same allocator (X1 vs X4 ablation).
2. Inverse-vol weighting over-funds W1 — because W1 is the lowest-vol sleeve in the panel — pushing average W1 weight to 26%, average cash to 50%, and average offense down to 37% (vs production 55%). This crushes absolute return: ann_ret 4.59% vs production 6.90%.

The exact W1-sizing problem Phase Y is solving: prevent inverse-vol from over-allocating to W1 in calm and neutral states (where W1 is not needed) while still letting W1 contribute defensive value when stress builds. Three interpretable mechanisms tested: explicit per-state caps (Y1), demand-driven trigger sizing (Y2), and cash-displacement-only sizing (Y3).

This is the right next step because the design hypothesis — W1 should be sized as a callable defensive sleeve, not a generic low-vol bucket — is the one Phase X explicitly forecast as Phase Y's job.

## E. Phase Y results

### Full-sample metrics (all 1110 weekly observations)

| Version | ann_ret | ann_vol | sharpe | MDD | CVaR-5 | turnover | avg_offense | avg_cash | raw_composite |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Production (`regime_confidence_boost`) | 6.90% | 7.80% | 0.885 | -13.98% | -2.62% | 5.62% | 55.3% | 28.3% | 0.478 |
| Shadow (`combo_abc`) | 6.86% | 7.77% | 0.884 | -13.67% | -2.61% | 5.66% | 55.2% | 28.5% | 0.480 |
| U1a (`prod90_r2_10`) | 6.92% | 7.76% | 0.892 | -13.94% | -2.60% | 5.72% | 55.2% | 28.3% | 0.484 |
| **X1** uncapped W1 (7-sleeve) | 4.59% | 4.96% | **0.924** | **-7.41%** | **-1.68%** | 18.8% | 37.0% | 50.0% | **0.490** |
| **X4** no W1 (6-sleeve) | 5.98% | 7.00% | 0.855 | -10.07% | -2.43% | 24.4% | 50.8% | 33.9% | 0.469 |
| **Y1** state-capped W1 | 5.65% | 6.59% | 0.858 | -9.41% | -2.29% | 23.5% | 48.0% | 37.1% | 0.467 |
| **Y2** trigger-driven W1 | 5.76% | 6.76% | 0.852 | -9.57% | -2.34% | 24.2% | 49.3% | 35.6% | 0.465 |
| **Y3** cash-replacement W1 | 5.99% | 7.00% | 0.855 | -10.08% | -2.43% | 24.4% | 50.8% | 33.8% | 0.469 |

### Holdout metrics (final 139 weeks)

| Version | ann_ret | sharpe | MDD | raw_composite |
|---|---:|---:|---:|---:|
| Production | 15.37% | 2.100 | -5.66% | 0.963 |
| Shadow | 15.36% | 2.113 | -5.53% | 0.961 |
| U1a | 15.42% | 2.110 | -5.67% | 0.963 |
| X1 | 11.16% | 2.261 | -2.71% | 0.775 |
| X4 | 13.49% | 1.886 | -4.50% | 0.894 |
| Y1 | 12.92% | 1.937 | -4.14% | 0.849 |
| Y2 | 13.19% | 1.892 | -4.37% | 0.880 |
| Y3 | 13.50% | 1.887 | -4.50% | 0.894 |

### Pairwise vs production (Phase D 8-gate rule)

| Candidate | full Δ (≥+0.015) | holdout Δ (≥0) | hold-Sharpe Δ (≥-0.02) | rolling win (≥55%) | rolling mean Δ (>0) | bootstrap (≥0.60) | MDD Δ (≥-0.01) | CVaR Δ (≥-0.002) | Pass? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Y1 | -0.010 ✗ | -0.114 ✗ | -0.163 ✗ | 26.7% ✗ | -0.018 ✗ | 0.005 ✗ | +0.046 ✓ | +0.003 ✓ | 6/8 ✗ |
| Y2 | -0.013 ✗ | -0.083 ✗ | -0.208 ✗ | 26.7% ✗ | -0.012 ✗ | 0.008 ✗ | +0.044 ✓ | +0.003 ✓ | 6/8 ✗ |
| Y3 | -0.009 ✗ | -0.068 ✗ | -0.213 ✗ | 26.7% ✗ | -0.001 ✗ | 0.014 ✗ | +0.039 ✓ | +0.002 ✓ | 6/8 ✗ |

### Pairwise vs X1 (uncapped-W1 reference)

| Candidate | full Δ vs X1 | holdout Δ vs X1 | hold-Sharpe Δ vs X1 | bootstrap vs X1 |
|---|---:|---:|---:|---:|
| Y1 | -0.023 | **+0.074** | -0.325 | **0.971** |
| Y2 | -0.026 | **+0.105** | -0.369 | **0.973** |
| Y3 | -0.022 | **+0.119** | -0.375 | **0.976** |

### W1 weight diagnostics (1110 obs)

| Candidate | avg W1 | median W1 | max W1 | p90 W1 |
|---|---:|---:|---:|---:|
| X1 (uncapped) | 25.6% | 29.6% | 81.5% | 40.4% |
| Y1 (state-cap) | 5.5% | 7.6% | 10.7% | 7.9% |
| Y2 (trigger) | 3.0% | 2.0% | 23.8% | 6.6% |
| Y3 (cash-only) | 0.2% | 0.0% | 8.1% | 0.6% |

### W1 weight by market state

| Candidate | calm | neutral | recov_conf | recov_frag | stress |
|---|---:|---:|---:|---:|---:|
| X1 | 32.4% | 34.0% | 28.0% | 18.3% | 0.0% |
| Y1 | 5.0% | 7.7% | 8.0% | 10.0% | 0.0% |
| Y2 | 2.9% | 4.6% | 2.2% | 2.3% | 0.0% |
| Y3 | 0.0% | 0.3% | 0.3% | 2.1% | 0.0% |

### Y2 trigger-quintile W1 weight (the diagnostic that broke the design)

| Quintile | avg trigger | avg W1 weight |
|---:|---:|---:|
| q0 (lowest) | 0.4% | 2.0% |
| q1 | 5.7% | 3.1% |
| q2 (mid) | 23.7% | **5.2%** |
| q3 (highest) | 74.5% | **2.8%** |

W1 weight peaks in the *middle* trigger quintile, then drops in the *highest* trigger quintile. The reason: the highest trigger scores correspond to stressed_panic regimes, where the production state risk multiplier is exactly 0 — which zeros W1 along with everything else.

## F. Phase Y interpretation

**What helped.** Compared to X1, all three Y candidates materially recover absolute return: ann_ret 5.65%–5.99% vs X1's 4.59%, average offense back to 48-51% vs X1's 37%, average cash back to 34-37% vs X1's 50%. This is what was supposed to happen — fewer-but-smarter W1 weights, more offense, more return. And in the holdout window, all three Y candidates beat X1 on raw composite by 7-12 points and the bootstrap probability vs X1 is 0.97 across all three. So: **conditional W1 sizing did fix the X1 over-defensiveness pathology.** That part of the design hypothesis is validated.

**What did not help.** None of the Y candidates clear Phase D against the production pin, and none even classify as Research-only by the existing rule (full Δ vs U1a, holdout Δ vs U1a, holdout Sharpe Δ vs U1a, bootstrap Δ vs U1a, full Δ vs X1 all negative). Y1 / Y2 / Y3 fail 6 of 8 production gates each. They also fail to recover X1's *Sharpe* gain — Y1 Sharpe 0.858 vs X4 Sharpe 0.855 (essentially identical), Y2 Sharpe 0.852 (worse), Y3 Sharpe 0.855 (identical). The W1 ablation table makes this explicit:

| W1 sizing rule | ann_ret | sharpe | MDD | CVaR | turnover | offense | cash |
|---|---:|---:|---:|---:|---:|---:|---:|
| (a) no W1 (X4) | 5.98% | 0.855 | -10.07% | -2.43% | 24.4% | 50.8% | 33.9% |
| (b) uncapped W1 (X1) | 4.59% | **0.924** | **-7.41%** | **-1.68%** | **18.8%** | 37.0% | 50.0% |
| (c) state-capped (Y1) | 5.65% | 0.858 | -9.41% | -2.29% | 23.5% | 48.0% | 37.1% |
| (d) trigger-driven (Y2) | 5.76% | 0.852 | -9.57% | -2.34% | 24.2% | 49.3% | 35.6% |
| (e) cash-replacement (Y3) | 5.99% | 0.855 | -10.08% | -2.43% | 24.4% | 50.8% | 33.8% |

The ablation tells the full story: there is a cliff between *no W1* and *uncapped W1*. As soon as W1 weight drops out of the 25-30% range it ran at in X1, the Sharpe / MDD / CVaR benefits collapse back to the X4 level. There is no smooth middle ground where capped W1 captures most of the X1 benefit while preserving most of the X4 return. The W1 lift is not linear in W1 weight; it is closer to a step function.

**Did conditional W1 sizing preserve production offense better than Phase X?** Yes — Y1/Y2/Y3 all run avg offense 48-51% vs X1's 37%. **Did it preserve W1's defensive benefit?** No — almost none of the X1 Sharpe / MDD / CVaR lift survives.

**Did it improve holdout raw composite / bootstrap / rolling win-rate?** Holdout raw composite vs X1 yes (+7-12pts). Bootstrap vs X1 yes (0.97). Rolling win rate vs production: no — stuck at 26.7%, unchanged from Phase X.

**Did it beat X1?** On absolute return and holdout raw composite yes. On Sharpe, MDD, CVaR no.

**Did it beat the production pin under the validation rules?** No — fails 6 of 8 gates.

**The core mechanical reason this happened.** The Y2 trigger quintile diagnostic shows it cleanly: the production allocator's state risk multiplier is 0 in stressed_panic. So whichever sizing rule we use for W1, W1's weight gets multiplied by 0 in the exact regime where Phase W proved W1 earns its alpha (stressed_panic was the only regime with a positive sharpe for W1 while running an actual defensive basket). The trigger fires hardest at exactly the moment W1 gets zeroed out. The state-cap and cash-replacement rules have the same issue at the boundary. **Inside the production allocator family, W1 is structurally barred from being deployed in the regime it was built for.** That is the diagnosis Phase Y produced.

## G. Candidate classification

| Candidate | Sharpe | MDD | full raw | holdout raw | Class | Rationale |
|---|---:|---:|---:|---:|---|---|
| Y1 — state-capped W1 | 0.858 | -9.41% | 0.467 | 0.849 | **Drop** | Fails 6/8 production gates; fails research-vs-U1a and research-vs-X1 conditions on full-sample raw composite; Sharpe gain over X4 negligible |
| Y2 — trigger-driven W1 | 0.852 | -9.57% | 0.465 | 0.880 | **Drop** | Same gate failures; trigger-quintile diagnostic shows the design is structurally defeated by state_risk_mult=0 in stressed_panic |
| Y3 — cash-replacement W1 | 0.855 | -10.08% | 0.469 | 0.894 | **Drop** | Functionally identical to X4 (W1 avg weight 0.2%); proves cash-displacement-only is too restrictive |

Note: although all three beat X1 on holdout raw composite and bootstrap (≥0.97), they fail the existing classification rule's "research" condition because none beat U1a or X1 on full-sample raw composite. This is the honest reading.

## H. Strategic diagnosis

**Did Phase Y succeed?** No, in the sense that no candidate gets meaningfully closer to a production promotion. Yes, in the sense that it produced a clean, mechanism-level diagnosis of why the production allocator family cannot host W1 well.

**Is conditional W1 sizing the right way to use the 7-sleeve panel?** Conditional sizing is necessary but not sufficient. The Y candidates correctly removed the X1 over-allocation, but the production state risk multiplier scheme — which sets risk_share to 0 in stressed_panic — defeats W1's intended defensive role at the worst possible moment. To deploy W1 as the callable defensive sleeve Phase W validated, the *state risk multiplier itself* needs to be modified so that W1 is allowed to absorb risk_share when the rest of the panel is being de-risked.

**What should the next phase focus on?** Phase Z — *modifying the state risk multiplier scheme so that W1 (and only W1) carries non-zero risk allocation in stressed_panic.* Concretely: replace the single scalar `STATE_RISK_MULT[state]` with a per-sleeve or sleeve-class state multiplier, where `STATE_RISK_MULT_DEFENSIVE[stressed_panic]` is non-zero (e.g., 0.30) but the offense sleeves remain at 0. This is the smallest structural change that lets W1 be deployed as designed without disturbing the production allocator's de-risking discipline for offense sleeves.

This is a structural Layer-3 change, not a Layer-2 sleeve search or a Layer-2B regime engine change. It belongs to the production allocator family and is the natural follow-up Phase Y diagnosed.

## I. Final recommendation

- **Production pin:** unchanged (`improved_phase2b_regime_confidence_boost`).
- **Shadow pin:** unchanged (`improved_phase2b_combo_abc`).
- **Closest research reference:** unchanged (`improved_phaseu_prod90_r2_10_holdings_blend` — U1a).
- **W1 ablation reference:** unchanged (`improved_phasex_production_style_7sleeve` — X1).
- **No new Phase Y candidate becomes a reference** — the Y family is dominated by either X4 (on return) or X1 (on Sharpe / risk metrics) and adds no new Pareto point.
- **Next step:** Phase Z — sleeve-class-aware state risk multiplier so W1 can be deployed in `stressed_panic` while offense remains de-risked. Target: lift X1's defensive benefit into a candidate that also preserves X4-level offense in calm/neutral states.

## J. Project journey log update

- File updated: `docs/research/project_journey.md`.
- Section added: **Section 38 — Phase Y: Conditional W1 Sizing Inside the Production Allocator Family**.
- The project story is now current through Phase Y closure.
