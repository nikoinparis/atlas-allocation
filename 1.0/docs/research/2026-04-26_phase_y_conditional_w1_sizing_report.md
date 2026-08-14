# Phase Y — Conditional W1 Sizing Inside the Production Allocator Family

**Date:** 2026-04-26
**Scope:** Narrow rerun of the production-style allocator on the 7-sleeve panel with conditional W1 sizing rules. Goal: test whether W1 used as a *callable defensive sleeve* (rather than a generic low-vol bucket) preserves W1's defensive benefit without destroying production-style offense.
**Comparator anchor:** `improved_phase2b_regime_confidence_boost` (production), with `improved_phasex_production_style_7sleeve` (X1) and `improved_phasex_production_style_6sleeve_ablation` (X4) as the W1 ablation reference points.

---

## A. What was changed

Three conditional W1 sizing rules built inside the existing production allocator family. No new sleeves. No new ML. No new regime engine work. No new trust layer. Same 7-sleeve panel, same state risk multipliers, same Phase 2B `regime_confidence_boost` meta layer. The only thing that changes is how W1's sleeve weight is determined inside the risk-on share:

- **Y1 — state-capped W1:** start from inverse-vol weights on the 7-sleeve panel; force W1 to a state-conditional cap (calm 5%, neutral 8%, recovery_confirmed 10%, recovery_fragile 18%, stressed 20% but mooted by state risk multiplier=0); redistribute the freed weight across the other 6 sleeves proportionally to their inverse-vol weights.
- **Y2 — trigger-driven W1:** ignore W1 in the inverse-vol step; instead set W1's weight directly from a bounded \[0.02, 0.25\] defensive trigger score combining (i) recent 13-week SPY drawdown depth, (ii) Phase 2B `p_tail_risk`, (iii) `1 − p_regime_confidence`. Other six sleeves split (1 − w_W1) by inverse-vol.
- **Y3 — cash-replacement W1:** run the production-style architecture exactly on the 6-sleeve panel (no W1 in the inverse-vol pool); then redirect a fraction of the resulting cash share into W1 when the same trigger score is high. Cap: at most 50% of cash share is convertible to W1, scaled linearly by trigger score. W1 only enters by displacing cash, never by displacing offense.

All three rules are causal and walk-forward: trigger fields read t-1 closed information (state, market_state_history, Phase 2B predictions, SPY weekly returns), inverse-vol uses 156-week trailing returns ending at t-1.

## B. What was executed

1. Read Phase X infrastructure (`scripts/phase_x_allocator_rerun_7sleeve.py`) and the production-pin allocator architecture in `scripts/build_improvement_artifacts.py` to understand exactly which knobs to leave alone.
2. Profiled `data/04_layer2b_risk_regime_engine/market_state_history.csv` for trigger field distributions (market_drawdown, breadth_change_4w, recent_stress_26w, avg_corr_risk_off_z, transition_non_stress_prob) per state to set sensible thresholds.
3. Wrote `scripts/phase_y_conditional_w1_sizing.py` implementing Y1/Y2/Y3 plus the Y4 ablation table.
4. Ran the script: 1,110 weekly observations per candidate, identical date alignment to Phase X.
5. Validated each candidate against the 11-member fixed comparator set under Phase D's 8-gate production rule and the shadow rule.

Brief external research consulted (used only to justify the trigger design, not to broaden scope): defensive-overlay literature from AQR (managed-volatility / quality-defensive), Newfound / ReSolve (tactical drawdown-aware allocation), Man Group (trend overlays), Alpha Architect (defensive-trend overlays), Research Affiliates (downside protection via low-vol assets); academic work on conditional risk budgeting and drawdown-conditional exposure adjustment. Common pattern across these sources: (a) cap defensive sleeve allocations by *state* not just by vol, and (b) drive defensive overlays from explicit early-warning signals (drawdown depth, breadth deterioration, regime instability) rather than from realized volatility. Y1 implements (a) directly. Y2 implements (b). Y3 combines (b) with the further constraint that defense should never crowd offense.

## C. Files / artifacts touched

**Code (new):**

- `scripts/phase_y_conditional_w1_sizing.py` — main Phase Y script (≈ 800 lines).

**Data outputs (new):**

- `data/05_layer3_portfolio_construction/portfolio_version_weights_{Y1,Y2,Y3}.csv` — ETF-level weight schedules.
- `data/05_layer3_portfolio_construction/portfolio_version_returns_{Y1,Y2,Y3}.csv` — gross/net/turnover/cost/wealth/drawdown.
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_{Y1,Y2,Y3}.csv` — sleeve-level weight schedules including `cash::BIL`.
- `data/05_layer3_portfolio_construction/phase_y_candidate_metrics_{full,dev,holdout}.csv`
- `data/05_layer3_portfolio_construction/phase_y_pairwise_validation.csv`
- `data/05_layer3_portfolio_construction/phase_y_rolling_origin_summary.csv`
- `data/05_layer3_portfolio_construction/phase_y_candidate_classification.csv`
- `data/05_layer3_portfolio_construction/phase_y_w1_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_y_state_w1_usage.csv`
- `data/05_layer3_portfolio_construction/phase_y_trigger_diagnostics.csv` — W1 weight by trigger-score quintile.
- `data/05_layer3_portfolio_construction/phase_y_w1_ablation_table.csv` — five-row ablation: no W1 / uncapped W1 / state-capped / trigger-driven / cash-replacement.
- `data/05_layer3_portfolio_construction/phase_y_validation_protocol.json`

**Docs (updated):**

- `docs/research/project_journey.md` — Section 38 appended.
- `docs/research/2026-04-26_phase_y_conditional_w1_sizing_report.md` — this report.

## D. Starting point diagnosis

> **Why did Phase X fail to promote despite proving W1 matters?**

X1 vs X4 (same allocator, 7 vs 6 sleeves) gave clean evidence that W1 inclusion improves Sharpe by +0.069, MDD by -2.66 points, CVaR by -0.75 points, and turnover by -5.6 points. So W1 is real. But X1 fails 5 of 8 production gates: full Δ +0.013 (need ≥+0.015), holdout Δ -0.188, rolling win 26.7%, rolling mean Δ -0.073, bootstrap 0.001. The mechanical cause is X1's offense crowd-out: avg cash 50% (vs production 28%), avg offense 37% (vs production 55%). Because W1 has the lowest standalone vol in the panel (~3.5% vs 6-9% for the others), inverse-vol weighting hands it ~26% of the risk-on share automatically — that is more defense than the production allocator's full-history return level can absorb without falling below the gate thresholds.

> **What exact W1-sizing problem is Phase Y solving?**

Phase X used W1 as a generic low-vol bucket: inverse-vol weighting treats W1 like just another sleeve and lets the math hand it 26% of risk-on weight every week regardless of whether defense is actually needed. But W1 was designed and validated (Phase W) as a *callable defensive sleeve* — its alpha lives specifically in stress regimes and at recovery transitions, and it only earns its keep when defense is the right answer. In calm_trend and neutral_mixed (the largest two regimes in the dataset, 788 of 1,110 weeks) Phase X still gave W1 ~32% of risk-on weight, displacing offense in environments where offense was the right answer. Phase Y removes that misuse and replaces it with explicit, interpretable, regime/trigger-conditioned W1 sizing.

> **Why is this the right next step?**

Two reasons. First, Phase X already isolated the failure mode mechanically (offense crowd-out from low-vol over-allocation), so the fix is narrow and known: stop the inverse-vol mechanic from over-funding W1. Second, the alternative — going back upstream to Layer 2 sleeve search, Layer 2B regime-engine work, or Layer 3 trust/holdings-blend territory — would re-open closed branches without first finishing the test of the Phase W → Phase X premise. The premise is "the upgraded panel is enough; the allocator just needs to use it correctly." Phase Y is the cleanest test of that premise.

## E. Phase Y results

### Full-history portfolio metrics

| Version | Ann Ret | Ann Vol | Sharpe | MDD | Calmar | CVaR-5 | Turnover | Up Cap | Down Cap | Rec Cap | Calm Cap | Avg BIL | Avg SPY | Off | Def | Cash | Raw Comp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Production** | **6.90%** | 7.80% | 0.885 | -13.98% | 0.494 | -2.62% | 5.6% | 0.324 | 0.239 | 0.304 | 0.434 | 28.3% | 7.1% | 55.3% | 16.4% | 28.3% | **0.478** |
| Combo ABC (shadow) | 6.86% | 7.77% | 0.884 | -13.67% | 0.502 | -2.61% | 5.7% | 0.323 | 0.239 | 0.296 | 0.435 | 28.5% | 7.1% | 55.2% | 16.4% | 28.5% | 0.480 |
| U1a (closest research ref) | 6.92% | 7.76% | 0.892 | -13.94% | 0.497 | -2.60% | 5.7% | 0.325 | 0.240 | 0.305 | 0.443 | 28.3% | 7.2% | 55.2% | 16.5% | 28.3% | 0.484 |
| **X1 (uncapped W1)** | 4.59% | 4.96% | **0.924** | **-7.41%** | 0.620 | **-1.68%** | 18.8% | 0.205 | 0.147 | 0.119 | 0.397 | 50.0% | 5.9% | **37.0%** | 13.0% | **50.0%** | 0.490 |
| X4 (no W1, 6-sleeve) | 5.98% | 7.00% | 0.855 | -10.07% | 0.594 | -2.43% | 24.4% | 0.299 | 0.232 | 0.219 | 0.483 | 33.9% | 8.9% | 50.8% | 15.4% | 33.9% | 0.469 |
| **Y1 — state-capped W1** | 5.65% | 6.59% | 0.858 | -9.41% | 0.600 | -2.29% | 23.5% | 0.280 | 0.215 | 0.173 | 0.467 | 37.1% | 8.3% | 48.0% | 14.9% | 37.1% | 0.467 |
| **Y2 — trigger-driven W1** | 5.76% | 6.76% | 0.852 | -9.57% | 0.602 | -2.34% | 24.2% | 0.288 | 0.223 | 0.207 | 0.464 | 35.6% | 8.6% | 49.3% | 15.1% | 35.6% | 0.465 |
| **Y3 — cash-replacement W1** | 5.99% | 7.00% | 0.855 | -10.08% | 0.594 | -2.43% | 24.4% | 0.299 | 0.232 | 0.217 | 0.483 | 33.8% | 8.9% | 50.8% | 15.4% | 33.8% | 0.469 |

### Conditional W1 diagnostics

W1 average / median / max weight by candidate:

| Candidate | Avg W1 | Median W1 | Max W1 | p90 W1 |
|---|---:|---:|---:|---:|
| X1 (uncapped W1) | **25.6%** | 29.6% | 81.5% | 40.4% |
| Y1 — state-capped | 5.5% | 7.6% | 10.7% | 7.9% |
| Y2 — trigger-driven | 3.0% | 2.0% | 23.8% | 6.6% |
| Y3 — cash-replacement | 0.2% | 0.0% | 8.1% | 0.6% |

W1 weight by market state:

| State | Obs | X1 | Y1 | Y2 | Y3 |
|---|---:|---:|---:|---:|---:|
| calm_trend | 295 | 32.4% | 5.0% | 2.9% | 0.0% |
| neutral_mixed | 493 | 34.0% | 7.7% | 4.6% | 0.3% |
| recovery_confirmed | 44 | 28.0% | 8.0% | 2.2% | 0.3% |
| recovery_fragile | 49 | 18.3% | 10.0% | 2.3% | 2.1% |
| stressed_panic | 229 | 0.0% | 0.0% | 0.0% | 0.0% |

Y2 — W1 weight by trigger-score quintile (the trigger fires in the right direction but the magnitudes are small):

| Trigger quintile | Avg trigger | Avg W1 weight | Obs |
|---|---:|---:|---:|
| 0 (lowest trigger) | 0.004 | 2.0% | 444 |
| 1 | 0.057 | 3.1% | 222 |
| 2 | 0.237 | **5.2%** | 222 |
| 3 (highest) | 0.745 | 2.8% | 222 |

(The non-monotonicity at the top quintile is because the highest trigger-score weeks coincide heavily with stressed_panic, where the state risk multiplier is 0 and W1 is therefore de-funded.)

### Validation views

**Pairwise vs production pin (8-gate Phase D rule):**

| Candidate | Full Δ | Hold Δ | Hold Sharpe Δ | Roll Win | Roll Mean Δ | Bootstrap | MDD Δ | CVaR Δ | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Threshold | ≥ +0.015 | ≥ 0 | ≥ -0.02 | ≥ 55% | > 0 | ≥ 60% | ≥ -1.0 pt | ≥ -0.2 pt | 8/8 |
| X1 | +0.013 | -0.188 | +0.162 | 26.7% | -0.073 | 0.001 | +0.066 | +0.009 | **3/8** |
| X4 | -0.009 | -0.069 | -0.214 | 26.7% | -0.001 | 0.014 | +0.039 | +0.002 | 3/8 |
| **Y1** | -0.010 | -0.114 | -0.163 | 26.7% | -0.018 | 0.005 | +0.046 | +0.003 | **3/8** |
| **Y2** | -0.013 | -0.083 | -0.208 | 26.7% | -0.012 | 0.008 | +0.044 | +0.003 | **3/8** |
| **Y3** | -0.009 | -0.069 | -0.213 | 26.7% | -0.001 | 0.014 | +0.039 | +0.002 | **3/8** |

(Pass column = number of 8 gates cleared. Only the MDD, CVaR, and Sharpe-related gates pass; the rolling and bootstrap and full-Δ gates fail for every Y candidate, exactly as for X1 and X4.)

**Pairwise vs U1a (closest-to-gate research reference):**

| Candidate | Full Δ vs U1a | Hold Δ vs U1a | Hold Sharpe Δ vs U1a | Bootstrap vs U1a |
|---|---:|---:|---:|---:|
| X1 | +0.006 | -0.188 | +0.152 | 0.001 |
| X4 | -0.016 | -0.069 | -0.224 | 0.014 |
| Y1 | -0.017 | -0.114 | -0.173 | 0.003 |
| Y2 | -0.020 | -0.083 | -0.218 | 0.006 |
| Y3 | -0.016 | -0.069 | -0.223 | 0.014 |

**Y4 — production-family W1 ablation (same allocator, varying W1 sizing rule):**

| Rule | Ann Ret | Sharpe | MDD | CVaR | Turn | Off | Cash | Raw Comp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| (a) no W1 (= X4) | 5.98% | 0.855 | -10.07% | -2.43% | 24.4% | 50.8% | 33.9% | 0.469 |
| (b) uncapped W1 (= X1) | 4.59% | **0.924** | **-7.41%** | **-1.68%** | 18.8% | 37.0% | 50.0% | **0.490** |
| (c) state-capped W1 (Y1) | 5.65% | 0.858 | -9.41% | -2.29% | 23.5% | 48.0% | 37.1% | 0.467 |
| (d) trigger-driven W1 (Y2) | 5.76% | 0.852 | -9.57% | -2.34% | 24.2% | 49.3% | 35.6% | 0.465 |
| (e) cash-replacement W1 (Y3) | 5.99% | 0.855 | -10.08% | -2.43% | 24.4% | 50.8% | 33.8% | 0.469 |

## F. Phase Y interpretation

> **What helped?**

Phase Y closed roughly 60% of the holdout-Δ gap to production that X1 had blown open: X1 was -0.188 vs production on holdout raw composite, Y3 is -0.069 and Y2 is -0.083. Bootstrap probability vs production also moved: X1 = 0.001, Y1 = 0.005, Y2 = 0.008, Y3 = 0.014. The conditional sizing rules did exactly what they were designed to do directionally — they suppressed W1 weight in calm/neutral environments (32%→ ≤ 8%) and gave it back to offense, restoring upside capture (X1: 0.205, Y3: 0.299) and absolute return (X1: 4.59%, Y3: 5.99%).

> **What did not help?**

The defensive properties that made X1 attractive — Sharpe 0.924, MDD -7.41%, CVaR -1.68% — were sacrificed in proportion to the W1 weight that was given back to offense. All three Y candidates landed on the Sharpe / MDD / CVaR axis between X4 (no W1) and X1 (uncapped W1), but closer to X4. Y3 in particular is mathematically near-identical to X4: average W1 weight 0.2% means cash-replacement essentially never activates with enough magnitude to matter, because the trigger score must be high *and* cash share must be high *and* the state must not be stressed_panic — three conditions that almost never coincide outside of recovery_fragile.

> **Did conditional W1 sizing help?**

It produced a more deployable absolute-return profile than X1 (5.65–5.99% ann return vs X1's 4.59%) without re-creating Phase X's catastrophic offense crowd-out. So as a *control mechanism* it works. But the position on the multi-objective frontier landed on the wrong side: Y candidates' raw composite scores (0.465-0.469) are below both X1 (0.490) and X4 (0.469), and below the production-pin baseline (0.478). The conditional sizing rules trade Sharpe/MDD/CVaR for return at a rate worse than the implicit trade in X1 — meaning the production allocator family does not extract enough additional return from the small conditional W1 dose to compensate for the defensive metrics it gives up.

> **Did it preserve production offense better than Phase X?**

Yes, decisively. Avg offense share: X1 = 37.0%, Y1 = 48.0%, Y2 = 49.3%, Y3 = 50.8%. The offense crowd-out is gone. Avg cash share: X1 = 50.0%, Y1 = 37.1%, Y2 = 35.6%, Y3 = 33.8% — back near X4's 33.9% and within striking distance of production's 28.3%.

> **Did it preserve W1's defensive benefit?**

Only partially. Sharpe difference vs X4 (which has no W1):
- X1: +0.069 (uncapped W1 lifts Sharpe by 0.069)
- Y1: +0.003 (state caps preserve essentially none of the X1 lift)
- Y2: -0.002
- Y3: +0.000

MDD difference vs X4:
- X1: +2.66 pts (uncapped W1 tightens MDD by 2.66 points)
- Y1: +0.66 pts (state caps preserve 25% of the lift)
- Y2: +0.50 pts
- Y3: -0.01 pts (no preservation at all)

CVaR difference vs X4:
- X1: +0.75 pts
- Y1: +0.14 pts (state caps preserve 19%)
- Y2: +0.09 pts
- Y3: +0.00 pts

Honest reading: only Y1 preserves a small fraction of W1's defensive lift; Y2 and Y3 essentially regress to the no-W1 baseline. This is the central finding of Phase Y.

> **Did it improve holdout raw composite / bootstrap / rolling win-rate?**

Holdout raw composite vs production: X1 = -0.188, Y1 = -0.114, Y2 = -0.083, Y3 = -0.069. Improved. Bootstrap: X1 = 0.001, Y3 = 0.014. Marginally improved. Rolling win rate: X1 = 26.7%, all Y candidates = 26.7%. *Unchanged* — every Y candidate fails the rolling gate at the same level X1 did, because rolling-window evaluation penalizes the same deployment-relevant return level that conditional W1 sizing only partially restores.

> **Did it beat X1 and the key research references?**

No. Every Y candidate has lower raw composite than X1 (Y best = 0.469 vs X1 0.490). Every Y candidate has lower raw composite than U1a (0.484), R3 (0.525), and V1 (0.495). On holdout Sharpe Y candidates lose to X1 by 0.32-0.37 points. The Y rules suppressed W1's harm to offense but did not restore enough return-side performance to overtake any deployable reference.

> **Did it beat the production pin under the validation rules?**

No. All three Y candidates fail at least 4 of 8 production gates (full Δ, holdout Δ, rolling win, rolling mean Δ, bootstrap), the same set of gates that X1 fails. Conditional W1 sizing improves *which* gates fail and *by how much*, but does not move any failed gate to passing.

## G. Candidate classification

| Candidate | Status | Rationale |
|---|---|---|
| Y1 — state-capped W1 | **Drop** | Cap schedule (5/8/10/18%) preserves only 4% of X1's Sharpe lift, 25% of MDD lift, 19% of CVaR lift. Misses every Phase D production gate that X1 misses. Raw composite 0.467 < X1 0.490 < production 0.478. No metric beats any reference. |
| Y2 — trigger-driven W1 | **Drop** | Trigger score correctly identifies stress periods, but those periods are dominated by stressed_panic where state mult = 0, so the trigger never gets to lift W1 weight where it would help. Avg W1 = 3.0%. Worst raw composite (0.465) of the three. |
| Y3 — cash-replacement W1 | **Drop** | Strictly dominated by X4: identical avg cash, offense, MDD, CVaR, raw composite to within 0.001. The cash-replacement rule almost never activates because it requires high trigger score AND high cash share AND a non-stressed state — three conditions that are nearly mutually exclusive. Mechanically equivalent to "no W1." |

Y4 ablation table (above) is reported but is not a separate classification — it is the diagnostic that explains why all three Y candidates classify as Drop.

## H. Strategic diagnosis

> **Did Phase Y succeed?**

No. The Phase Y success condition was: produce at least one candidate that (a) clearly improves on X1 by using W1 more intelligently, (b) preserves much of W1's Sharpe / tail benefit, (c) materially improves absolute return / holdout raw composite vs Phase X, and (d) improves deployment proximity. Phase Y delivered (c) — Y3 narrows the holdout-Δ gap from -0.188 to -0.069. Phase Y did not deliver (a), (b), or (d): no Y candidate's raw composite beats X1's, no Y candidate preserves more than 25% of W1's defensive lift, and no Y candidate moves any failed Phase D gate to passing.

> **Is conditional W1 sizing the right way to use the 7-sleeve panel?**

Probably not, at least not inside the inverse-vol allocator family. The Phase Y test exposes a structural bind: W1's defensive value lives in the 25-35% weight range (X1's territory), but at that weight share the inverse-vol allocator has too little risk-on capacity to clear the production return gates. At the 5-10% range (Y1's territory) most of W1's defensive value is gone but the offense crowd-out is also gone. The frontier between these two corner solutions does not contain a candidate that clears all Phase D gates against the production pin — because the production pin uses a fundamentally different allocator architecture (HRP + dynamic risk budget on a 5-sleeve subset) that extracts more return from the same opportunity set than any inverse-vol-on-7-sleeve variant.

The Phase X promotion of W1 was correct at the *sleeve* level: the panel improvement is real and was validated in the X1 vs X4 ablation. The error was assuming that the production allocator family could absorb that improvement under any reasonable W1 sizing rule. Phase Y now demonstrates that it cannot.

> **What should the next phase focus on?**

**Phase Z — port the production allocator architecture itself onto the 7-sleeve panel.** The current production pin uses HRP-based sleeve weighting + the `lighter_both_targeted_narrow_plus_confirmed` overlay + dynamic risk budget on the 5-sleeve subset `[dual_momentum_topn, cta_trend_long_only, selective_strategy, composite_regime_conditioned, taa_10m_sma]`. Phase X / Phase Y have been testing inverse-vol weighting on the 7-sleeve panel — a different architecture entirely. The right next step is not another conditional-sizing variant of inverse-vol, but rebuilding HRP / dynamic risk budget on the 7-sleeve panel (with W1 included) so the comparison is architecture-equivalent. If HRP on 7-sleeves still fails, that would reopen the *opportunity set* question. If HRP on 7-sleeves clears Phase D, that promotes W1's panel value into a deployable allocator change.

A smaller alternate path: run the V-style holdings-blend (production × U1a-style research candidate with a variable blend weight) over Phase X / Y candidates. Holdings blending was the closing branch of Phases Q-V and may still extract incremental value when one of the blendees is a 7-sleeve W1-aware allocator.

## I. Final recommendation

**Production pin: unchanged.** `improved_phase2b_regime_confidence_boost` remains. No Phase Y candidate is deployment-ready.

**Shadow pin: unchanged.** `improved_phase2b_combo_abc` remains. No Phase Y candidate clears the shadow rule either.

**No new closest-to-gate research reference.** Y3 has the best holdout-Δ vs production of any inverse-vol-on-7-sleeve variant (-0.069 vs X1's -0.188), so it is the new W1-aware reference inside that family — recorded as a tracked baseline. But it does not displace U1a, R3, or V1 as research references because its raw composite is below all of them.

**Next step after Phase Y: Phase Z — port the production HRP / dynamic-risk-budget allocator architecture itself onto the 7-sleeve panel.** This is the architecture-equivalent test that Phase X and Phase Y did not perform. If Phase Z clears the production gates, W1's panel value becomes deployable. If Phase Z fails the same way Phase X and Phase Y failed, the diagnosis flips: the panel improvement is real but allocator-resistant, and the project should turn to either a holdings-blend revisit (V-style) or a new Layer-3 architecture entirely.

## J. Project journey log update

File updated: `docs/research/project_journey.md`. Section added: **Section 38 — Phase Y: Conditional W1 Sizing Inside the Production Allocator Family.** The project story is now current through the close of Phase Y, including the diagnosis that the 7-sleeve panel improvement is real but cannot be absorbed by the inverse-vol allocator family under any of the three conditional W1 sizing rules tested, and the explicit recommendation that Phase Z should port the production HRP architecture onto the upgraded panel rather than continue tuning inverse-vol-based variants.
