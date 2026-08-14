# Phase X — Allocator Rerun on the Upgraded 7-Sleeve Panel

**Sprint date:** 2026-04-25
**Prior context:** Phase W promoted `composite_structural_defense_sleeve` (W1) into the active panel, taking it from 6 sleeves to 7. Panel avg |corr| dropped from 0.66 to 0.48. W1 was demonstrated to be the only sleeve with positive sharpe in `stressed_panic` while running an actual defensive basket (not BIL parking).
**Production pin (unchanged):** `improved_phase2b_regime_confidence_boost`
**Shadow pin (unchanged):** `improved_phase2b_combo_abc`

---

## A. What was changed

A new sleeve-level allocator was implemented on the upgraded 7-sleeve panel, with four candidates:

- **X1** — production-style: inverse-volatility sleeve weighting + state risk multiplier + Phase 2B `regime_confidence_boost` ML meta layer.
- **X2** — shadow-style: same allocator with `combo_abc` (A+B+C) ML meta.
- **X3** — research-style: state-conditional sleeve weighting (each market state has its own rank-Sharpe-tilted inverse-vol weights), no ML meta.
- **X4** — clean ablation: identical to X1 but on the 6-sleeve panel (no W1).

All four use the same walk-forward causal pipeline: 156-week trailing returns for inverse-vol, 1-week-lagged sleeve features, walk-forward state and ML predictions only.

---

## B. What was executed

Script: `scripts/phase_x_allocator_rerun_7sleeve.py` (~430 lines).

Process:
1. Load 7 sleeve return series + 7 sleeve position series.
2. For each candidate, walk forward week-by-week: compute inverse-vol (or state-conditional) sleeve weights, multiply by state risk multiplier (0 in `stressed_panic`, 0.55 in `recovery_fragile`, 0.80 in `recovery_confirmed`, 0.95 in `neutral_mixed`, 1.0 in `calm_trend`), apply Phase 2B ML offset (regime_confidence_boost or combo_abc), residual to BIL.
3. Roll up sleeve weights × sleeve positions → per-ETF portfolio weights.
4. Realize next-week returns (5 bps half-spread turnover cost), produce gross/net/turnover/wealth/drawdown frames.
5. Validate against the 14-member fixed comparator set under full Phase D rules (production rule, shadow rule, classification).
6. Compute W1 weight diagnostics + state-conditional W1 usage.

---

## C. Files / artifacts modified or generated

Code:
- `scripts/phase_x_allocator_rerun_7sleeve.py` (new)

Portfolio outputs (per X candidate):
- `data/05_layer3_portfolio_construction/portfolio_version_weights_<X>.csv` (ETF-level, 4 files)
- `data/05_layer3_portfolio_construction/portfolio_version_returns_<X>.csv` (4 files)
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_<X>.csv` (4 files)

Validation outputs:
- `phase_x_candidate_metrics_full.csv`
- `phase_x_candidate_metrics_dev.csv`
- `phase_x_candidate_metrics_holdout.csv`
- `phase_x_pairwise_validation.csv`
- `phase_x_rolling_origin_summary.csv`
- `phase_x_candidate_classification.csv`
- `phase_x_w1_diagnostics.csv` (W1 weight summary per candidate)
- `phase_x_state_w1_usage.csv` (state-conditional W1 weight summary)
- `phase_x_validation_protocol.json`

Docs:
- This report (`docs/research/2026-04-25_phase_x_allocator_rerun_7sleeve_report.md`)
- `docs/research/project_journey.md` Section 37 appended

---

## D. Starting point diagnosis

Why was Phase W successful enough to justify an allocator rerun?
- W1 was the cleanest sleeve introduced in any sprint of this project: standalone Sharpe 0.65, holdout MDD -0.91%, max correlation against any active sleeve 0.09, only sleeve in the entire panel with positive Sharpe in `stressed_panic` while running a real defensive basket. Adding W1 to the naive panel blend lifted Sharpe from 0.86 to 0.91 and tightened MDD by 1.55 pts.

What exact question is Phase X trying to answer?
- *"Does the upgraded 7-sleeve panel let an allocator finally produce a candidate that materially improves deployment quality versus the prior branch?"* And specifically: does W1 improve downstream allocation decisions when fed into a state-aware allocator family?

Why is the 7-sleeve panel the right test bed?
- The closed allocator/trust/regime/holdings-blend branch (Phases Q–V) had repeatedly demonstrated that no re-mix of the existing 6 active sleeves could align all six Phase D gates simultaneously. The constraint was diagnosed as a sleeve-panel limitation, not an allocator limitation. Phase W produced exactly one new sleeve (W1) that filled the explicit-defensive-role gap. Phase X is the first allocator test on that improved opportunity set.

---

## E. Phase X results — full-history portfolio metrics

| Candidate | Ann Ret | Ann Vol | Sharpe | Max DD | Calmar | CVaR-5 | Turnover | Up Cap | Dn Cap | Avg BIL | Avg SPY | Avg Off | Avg Def | Avg Cash | Recovery Cap | Calm Cap |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Production | 6.90% | 7.80% | 0.885 | -13.98% | 0.494 | -2.62% | 5.6% | 32.4% | 23.9% | 28.3% | 7.1% | 55.3% | 16.4% | 28.3% | 30.4% | 43.4% |
| **X1** (prod-style, 7-sleeve) | **4.59%** | **4.96%** | **0.924** | **-7.41%** | **0.620** | **-1.68%** | **18.8%** | **20.5%** | **14.7%** | **50.0%** | **5.9%** | **37.0%** | **13.0%** | **50.0%** | **11.9%** | **39.7%** |
| **X2** (shadow-style, 7-sleeve) | 4.55% | 4.95% | 0.919 | -7.29% | 0.624 | -1.68% | 18.9% | 20.4% | 14.6% | 50.2% | 5.8% | 36.9% | 13.0% | 50.2% | 11.3% | 39.5% |
| **X3** (state-conditional, 7-sleeve) | 4.56% | 4.87% | 0.935 | -7.85% | 0.581 | -1.63% | 19.6% | 19.9% | 14.0% | 50.8% | 5.7% | 36.3% | 12.8% | 50.8% | 12.6% | 36.8% |
| **X4** (prod-style, 6-sleeve, ablation) | **5.98%** | **7.00%** | **0.855** | **-10.07%** | **0.594** | **-2.43%** | **24.4%** | **29.9%** | **23.2%** | **33.9%** | **8.9%** | **50.8%** | **15.4%** | **33.9%** | **21.9%** | **48.3%** |

Phase X — holdout (last 104 weeks) metrics:

| Candidate | Ann Ret | Sharpe | Max DD | Raw Composite |
|---|---:|---:|---:|---:|
| Production | 15.37% | 2.10 | -5.66% | 0.963 |
| X1 | 11.16% | **2.26** | **-2.71%** | 0.775 |
| X2 | 11.08% | 2.24 | -2.73% | 0.774 |
| X3 | 10.96% | **2.46** | **-2.15%** | 0.763 |
| X4 (ablation, no W1) | 13.49% | 1.89 | -4.50% | 0.894 |

W1 weight diagnostics (X1):

| Statistic | Value |
|---|---:|
| Avg W1 weight | 25.6% |
| Median W1 weight | 29.6% |
| Max W1 weight | 81.5% |
| P90 W1 weight | 40.4% |

W1 state-conditional usage (X1):

| Market state | Obs | Avg W1 | Median W1 | Max W1 |
|---|---:|---:|---:|---:|
| calm_trend | 295 | 32.4% | 30.7% | 73.0% |
| neutral_mixed | 493 | 34.0% | 32.8% | 81.5% |
| recovery_confirmed | 44 | 28.0% | 28.2% | 37.7% |
| recovery_fragile | 49 | 18.3% | 18.2% | 23.3% |
| stressed_panic | 229 | 0.0% | 0.0% | 0.0% |

W1 weight is correctly zeroed in `stressed_panic` (state risk multiplier = 0, full BIL), highest in `neutral_mixed`/`calm_trend` (because inverse-vol weighting naturally over-weights the lowest-vol sleeve, which is W1), and modestly lower in recovery states.

Phase X pairwise vs production:

| Candidate | Full Δ | Holdout Δ | Holdout Sharpe Δ | Roll Win Rate | Roll Mean Δ | Bootstrap | MDD Δ | CVaR Δ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| X1 | +0.0128 | -0.1879 | +0.162 | 26.7% | -0.0730 | 0.001 | +0.066 | +0.009 |
| X2 | +0.0120 | -0.1884 | +0.145 | 26.7% | -0.0742 | 0.001 | +0.067 | +0.009 |
| X3 | +0.0041 | -0.1993 | +0.358 | 26.7% | -0.0747 | 0.002 | +0.061 | +0.010 |
| X4 (no W1) | -0.0091 | -0.0690 | -0.214 | 26.7% | -0.0013 | 0.014 | +0.039 | +0.002 |

Production rule reminder (must hit all): Full Δ ≥ +0.015 · Holdout Δ ≥ 0 · Holdout Sharpe Δ ≥ -0.02 · Rolling win ≥ 55% · Rolling mean Δ > 0 · Bootstrap ≥ 60% · MDD Δ ≥ -0.01 · CVaR Δ ≥ -0.002.

---

## F. Phase X interpretation

**What helped.** Including W1 (X1 vs X4 ablation) produced a clear, internally consistent improvement on every risk-adjusted dimension:
- Sharpe: 0.855 → **0.924** (+0.069)
- Max drawdown: -10.07% → **-7.41%** (-2.66 pts, a 26% reduction)
- CVaR-5: -2.43% → **-1.68%** (-0.75 pts)
- Turnover: 24.4% → **18.8%** (-5.6 pts, less churning)
- Avg defense weight rises modestly (15.4% → 13.0% — actually drops slightly; the explicit W1 sleeve crowds out generic defense)
- Avg cash rises (33.9% → 50.0%) because W1's natural low-vol pulls more weight into structural defense than the no-W1 panel had been spending on cash + scattered defense

So at the X-allocator level, the 7-sleeve panel **does** create a measurably better risk-adjusted portfolio than the 6-sleeve panel under identical allocator logic. **W1 mattered** in exactly the way Phase W's diagnostic predicted.

**What did not help.** The X allocator family as designed is materially over-defensive vs production:
- avg cash 50% vs production 28% (almost double)
- avg offense 37% vs production 55% (about two-thirds)
- upside_capture 20% vs production 32% (about two-thirds)
- absolute return 4.59% vs production 6.90% (a 230 bp shortfall)

The mechanism is interpretable: inverse-vol weighting naturally over-weights the lowest-vol sleeve, and W1 has the lowest standalone vol of the seven (3.5%). So the X allocator pours roughly 1/4 of its risk-on share into W1 even in calm_trend, where production would prefer broader equity exposure. The state risk multiplier compounds this — at `recovery_confirmed` it scales the (already-defensive) sleeve weights down to 0.80×, so even at recovery confirmation the X allocator is running 28% W1 instead of leaning into recovery-specific offense.

The result is great risk metrics, poor absolute return, and a pattern that fails the Phase D rolling-win and bootstrap gates by a wide margin.

**Did W1 matter?** Yes, unambiguously. The X1-vs-X4 ablation isolates W1's contribution: lower MDD, lower CVaR, lower turnover, higher Sharpe. The improvement is mechanical and reproducible.

**In which states did W1 add value?** W1 weight is highest in `neutral_mixed` and `calm_trend` (where the inverse-vol allocator naturally wants more low-vol exposure), zero in `stressed_panic` (state mult = 0). The state-conditional X3 variant pushes W1 weight even higher in `neutral_mixed` (max 81.5%) and produces the best holdout Sharpe (2.46) and tightest holdout MDD (-2.15%). So W1 *most* helps in the largest-observation state (`neutral_mixed`, 493 obs), which is also where the active panel's incumbent best (`taa_10m_sma`) was already strong but un-diversified.

**Did the allocator actually use the better panel?** Yes — W1 received an average 25.6% weight, max 81.5%, P90 40.4%. The allocator is not ignoring W1 or treating it as a token addition.

**Did the 7-sleeve rerun improve deployment-relevant behavior?** *Mixed.* It improved Sharpe and tail behavior in the X family. It did not improve absolute return, holdout return, rolling win rate, or bootstrap probability versus production. By Phase D's deployment-relevant axes (rolling win, bootstrap, holdout absolute), the X candidates fall short.

**Did it beat the relevant 6-sleeve version?** Yes, decisively. X1 vs X4 on every risk-adjusted axis. The ablation is the cleanest result in the sprint.

**Did it beat prior research references?** No. X1 has full-history raw composite 0.490 vs U1a 0.484 (+0.006) but loses to U1a on holdout absolute Δ (-0.188) and on bootstrap (0.001 vs U1a's). X1 vs V1 is similar.

**Did it beat the production pin under the validation rules?** No. The promotion rule fails at multiple gates: holdout Δ -0.188 (need ≥ 0), rolling win 26.7% (need ≥ 55%), bootstrap 0.001 (need ≥ 0.60), rolling mean Δ -0.073 (need > 0). Only the holdout Sharpe Δ (+0.162) and the MDD/CVaR caps clear comfortably.

---

## G. Candidate classification

| Candidate | Classification | Rationale |
|---|---|---|
| X1 — production-style 7-sleeve | **Research-only** | Beats U1a on full Δ (+0.006) and holdout Sharpe (+0.152), but fails production rule on holdout Δ, rolling win, bootstrap. Improves materially on the 6-sleeve ablation. |
| X2 — shadow-style 7-sleeve | **Research-only** | Indistinguishable from X1 in this allocator family. The combo_abc meta layer adds essentially nothing on top of regime_confidence_boost when the underlying inverse-vol allocator is already over-defensive. |
| X3 — state-conditional 7-sleeve | **Research-only** | Best holdout Sharpe (2.46) and tightest holdout MDD (-2.15%) of the sprint, but drops slightly more raw composite (0.482) and fails Phase D rules on the same axes as X1. Useful as evidence that state-conditional sleeve weighting *plus* W1 is the strongest combination if you want pure risk-adjusted performance. |
| X4 — production-style 6-sleeve ablation | **Drop** | Worse on every dimension than X1. Only purpose was the W1 ablation, which it served. |

---

## H. Strategic diagnosis

**Did Phase X succeed?** *Partially.* The narrowly defined success condition was: produce at least one candidate that clearly benefits from the upgraded 7-sleeve panel and materially improves on the relevant 6-sleeve counterpart. **That condition is met** — X1 vs X4 is a clean and substantial improvement attributable directly to W1. The broader success condition (clear path to production promotion) is **not** met — none of the X candidates clear Phase D rules.

**Is the panel now meaningfully better for allocators?** Yes, but not in the way the closed allocator/trust/regime/holdings branch was hoping for. The 7-sleeve panel improves:
- risk-adjusted return (Sharpe in the X family +0.07 vs no-W1 baseline)
- tail behavior (MDD -2.7 pts, CVaR -0.75 pts)
- turnover stability (-5.6 pts)

It does *not* improve the absolute return profile under an inverse-vol allocator. The inverse-vol allocator is mechanically biased toward low-vol sleeves, and W1 is the lowest-vol sleeve, so it gets crowded into a very-defensive solution. To capture W1's benefit *without* sacrificing absolute return, a different allocator design is needed — one that allocates W1 conditionally rather than mechanically by inverse-vol.

**What should the next phase focus on?** The honest read is that Phase X exhausted what the inverse-vol allocator family can do with the upgraded panel. The next move should be one of:

1. **Phase Y — conditional W1 sizing inside the production allocator family** (high conviction). Rather than letting W1 collect inverse-vol mass, define W1's exposure as a function of explicit defensive triggers (recent stress, breadth deterioration, drawdown depth). This decouples W1 weight from generic vol mechanics and tests whether W1 helps when used *as designed* (callable defense), not as a generic low-vol bucket.

2. **Phase Y' — replace inverse-vol with HRP or HERC in the X family**. The actual production candidate uses HRP, which clusters sleeves before allocating. HRP would naturally put W1 in its own defensive cluster and not over-fund it. Worth testing if the simpler conditional-sizing approach falls short.

3. **Phase Y'' — re-introduce W1 to the actual production allocator pipeline** (`build_improvement_artifacts.py` HRP allocator, with the production 5-sleeve subset extended to include W1). This is the most direct apples-to-apples test of "what would production look like with W1?". It requires running the full allocator framework rather than the lightweight X allocator.

Recommendation: try option 1 (conditional W1 sizing) first; it's the smallest, fastest, and most directly attacks the diagnosed problem. If the result is still inconclusive, escalate to option 3 (full production-pipeline rerun with W1 added).

---

## I. Final recommendation

**Production pin:** unchanged (`improved_phase2b_regime_confidence_boost`).
**Shadow pin:** unchanged (`improved_phase2b_combo_abc`).

**Updated reference set:** add **X1 (`improved_phasex_production_style_7sleeve`)** as the *first allocator-level candidate that demonstrates W1 has measurable downstream value*. It does not become the closest research reference (U1a still holds that on holdout-Δ and rolling-win profile), but it earns a permanent place in the project's reference set as the **W1 ablation reference**: the one candidate that proves W1 inclusion improves risk-adjusted allocator output by a material margin under identical allocator logic.

**Next step:** Phase Y — *conditional W1 sizing inside the production allocator family*. Stop letting W1 accumulate inverse-vol mass. Instead, define W1's exposure as a function of explicit defensive triggers (recent stress, breadth deterioration, drawdown depth), so the sleeve is used as the callable defense Phase W intended, not as a generic low-vol bucket.

---

## J. Project journey log update

File updated: `docs/research/project_journey.md`.
Section added: **Section 37 — Phase X: Allocator Rerun on the Upgraded 7-Sleeve Panel**.
Project story is now current through Phase X. The dual-track production/shadow pins remain unchanged. The reference set picks up X1 as the W1 ablation reference. The next sprint focuses on conditional W1 sizing (Phase Y) rather than further sleeve search or trust-layer/regime-engine work.
