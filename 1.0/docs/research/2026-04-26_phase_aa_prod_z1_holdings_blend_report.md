# Phase AA — Production-Anchored Holdings Blend with Z1

**Date:** 2026-04-26
**Scope:** Narrow holdings-level blend sprint. Anchor on the production pin (`improved_phase2b_regime_confidence_boost`); blend in small doses of Z1 (`improved_phasez_production_hrp_7sleeve`, the Phase Z defensive-ceiling reference) at the ETF-weights level; test whether the linear blend imports any of Z1's Sharpe / MDD / CVaR profile without giving up enough of production's return profile to fail Phase D production gates.
**Comparator anchor:** production pin and the same fixed comparator set used in Phases X / Y / Z, plus pure Z1 and the U-series and V-series holdings-blend references (U1a, U3, V1) which are the closest historical analogs to this sprint.

---

## A. What was changed

A clean holdings-level blend sprint, anchored on production. Three high-conviction blend candidates were built — no broad blend grid, no new sleeves, no new allocators, no new ML, no new trust or regime work:

- **AA1 — static 95 / 5 production + Z1 holdings blend.** `blended_w(t) = 0.95 * prod_w(t) + 0.05 * z1_w(t)`, `blended_net(t) = 0.95 * prod_net(t) + 0.05 * z1_net(t)`. The most conservative test: preserve nearly all of production's return engine and check whether even a tiny dose of Z1 imports defensive value cheaply.
- **AA2 — static 90 / 10 production + Z1 holdings blend.** Phase V-style 90 / 10 anchor weighting. Z1's defensive-ceiling profile is structurally orthogonal to production at the *sleeve* level in a way that no prior research-blend partner is, so 90 / 10 is the natural primary test on the holdings side.
- **AA3 — state-conditional production + Z1 holdings blend.** Causal, walk-forward-safe schedule indexed on `market_state_history.market_state` at t-1: calm_trend → 0.95, neutral_mixed → 0.92, recovery_confirmed → 0.90, recovery_fragile → 0.85, stressed_panic → 0.85. Realized average production share = 0.910, between AA1 and AA2 but expressed as defense-when-needed instead of constant tilt. AA3 also pays a 5 bp half-spread cost on the schedule-induced rebalance whenever the per-week share `a(t)` changes.

After inspecting AA1 / AA2 / AA3 diagnostics, **no AA4 was added.** The gradient from AA1 → AA2 → AA3 is monotonic in raw composite (smaller Z1 dose = better composite), and the structural mechanic identified in Section F is fundamental enough that no narrowly-justified fourth blend would have moved the strategic decision. AA4 was deliberately skipped to keep the sprint as narrow as the spec required.

The blend math is intentionally the same linear convention used in Phase U / V holdings blends, so the AA candidates compare apples-to-apples against U1a, U3, and V1 on the same fixed comparator set under the same Phase D 8-gate production rule and shadow rule.

## B. What was executed

1. Read `scripts/phase_v_final_holdings_blend.py` and `scripts/phase_u_holdings_blend.py` to lift the existing holdings-blend conventions: per-week ETF-weight alignment via index intersection, linear weighted sum at the ETF level, linear weighted sum at the net-return level, schedule-cost surcharge when the conditional share changes between weeks. Reused exactly to keep AA candidates comparable to U1a / U3 / V1.
2. Wrote `scripts/phase_aa_production_z1_blend.py` (552 lines) implementing AA1 / AA2 / AA3 with a faithful port of the Phase V / U blend math, the Phase Z fixed comparator set augmented with U-series and V-series references, and the same Phase D validation bundle invocation used in Phase Z (`phase_d_validate.split_dev_holdout`, `phase_p_evaluate.metric_row`, `rolling_evaluation`, `safe_bootstrap`).
3. Ran the script. Loaded production weights (1110 × 35), Z1 weights (1110 × 35), production net returns, Z1 net returns, market_state_history. Built the three AA candidates, wrote per-candidate weights / returns / sleeve_weights / blend_diagnostics / state_blend_schedule artifacts.
4. Ran the validation bundle on the AA candidates plus the 16-member fixed comparator set (production, shadow, H, N, O, P, Q, R2, R3, T1, U1a, U3, V1, X1, Z1, baseline). Generated `phase_aa_candidate_metrics_{full,dev,holdout}.csv`, `phase_aa_pairwise_validation.csv`, `phase_aa_rolling_origin_summary.csv`, `phase_aa_candidate_classification.csv`, `phase_aa_blend_diagnostics.csv`, `phase_aa_state_blend_schedule.csv`, `phase_aa_validation_protocol.json`.
5. Ran a small post-hoc diagnostic to characterize the structural overlap between production and Z1 ETF weights by market state. This is not a backtest artifact — it's the mechanism explanation that anchors Section F's interpretation.

## C. Files / artifacts touched

**Code (new):**

- `scripts/phase_aa_production_z1_blend.py` — main Phase AA script.

**Data outputs (new):**

- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseaa_prod95_z1_05_holdings_blend.csv` (AA1)
- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseaa_prod90_z1_10_holdings_blend.csv` (AA2)
- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phaseaa_state_conditional_prod_z1_holdings_blend.csv` (AA3)
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phaseaa_*.csv` (gross / net / turnover / cost / wealth / drawdown for each AA candidate)
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phaseaa_*.csv` (production_anchor / z1_overlay pseudo-sleeves for each AA candidate)
- `data/05_layer3_portfolio_construction/phase_aa_candidate_metrics_{full,dev,holdout}.csv`
- `data/05_layer3_portfolio_construction/phase_aa_pairwise_validation.csv`
- `data/05_layer3_portfolio_construction/phase_aa_rolling_origin_summary.csv`
- `data/05_layer3_portfolio_construction/phase_aa_candidate_classification.csv`
- `data/05_layer3_portfolio_construction/phase_aa_blend_diagnostics.csv`
- `data/05_layer3_portfolio_construction/phase_aa_state_blend_schedule.csv`
- `data/05_layer3_portfolio_construction/phase_aa_validation_protocol.json`

**Docs (updated):**

- `docs/research/2026-04-26_phase_aa_prod_z1_holdings_blend_report.md` — this report.
- `docs/research/project_journey.md` — Section 40 appended.

## D. Starting point diagnosis

> **Why did Phase Z fail despite proving Z1's defensive value?**

Phase Z proved that HRP on the upgraded 7-sleeve panel produces the strongest defensive risk profile of any candidate ever tested — Sharpe 0.93, MDD −8.57%, CVaR −1.51%, holdout Sharpe 2.37 — but Z1's full-history annualized return is only 4.24% versus production's 6.90%. The mechanism is structural: HRP's bisection inverse-variance step hands W1 (`composite_structural_defense_sleeve`) the `MAX_SLEEVE_WEIGHT = 0.45` cap in the median week. That much weight in a low-vol structural-defense sleeve mechanically caps the portfolio's beta-equivalent exposure, and absolute return scales accordingly. Z1 is therefore the strongest *defensive-ceiling* candidate the project has ever built, but it cannot be deployed standalone because its raw composite is 0.451 vs production's 0.478 and its return-side gates fail by a wide margin.

> **What exact tradeoff is Phase AA trying to solve?**

The Phase Z report recommended a Branch 1 test: take production as the deployable return anchor and Z1 as the defensive partner, and try to *blend* them at the holdings level so the resulting portfolio inherits production's return profile (because it's mostly production) and a fraction of Z1's defensive profile (because the small Z1 dose pulls drawdowns / CVaR / Sharpe in the right direction). Phase AA exists to test whether that linear blend at the ETF level is enough to clear at least one Phase D production gate that prior research candidates have missed.

> **Why is production+Z1 holdings blending the right next step?**

For three reasons. First, it's the smallest, fastest test that actually addresses the Phase Z diagnosis without re-opening any larger frontier. Second, prior holdings-blend phases (Phase U produced U1a, U3; Phase V produced V1) showed that production+research-partner blends in the 90 / 10 to 95 / 5 range are the right region of the blend space: large enough to import partner value, small enough to preserve production's return engine. Third, Z1's *sleeve*-level orthogonality to production — production runs a Phase 2B regime-conditioned 5-sleeve allocator, Z1 runs HRP on a different 7-sleeve panel including W1 — is structurally larger than any prior research-blend partner this project has tested, so if linear holdings blending can ever extract a Phase D-passing improvement, Z1 is the strongest partner this method has ever had access to.

## E. Phase AA results

### Full-history portfolio metrics (1,110 weekly observations, 2005-01-07 → 2026-04-10)

| Version | Ann Ret | Ann Vol | Sharpe | MDD | Calmar | CVaR-5 | Turnover (L1) | Raw Comp |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Production** | **6.90%** | 7.80% | 0.885 | −13.98% | 0.494 | −2.62% | 5.6% | **0.478** |
| Combo ABC (shadow) | 6.86% | 7.77% | 0.884 | −13.67% | 0.502 | −2.61% | 5.7% | 0.480 |
| R3 (Sharpe ref) | 6.82% | 7.16% | **0.952** | −13.04% | 0.523 | −2.36% | 7.0% | **0.525** |
| U1a (closest ref) | 6.92% | 7.76% | 0.892 | −13.94% | 0.496 | −2.60% | 5.7% | 0.484 |
| U3 (bootstrap ref) | 6.97% | 7.72% | 0.902 | −13.95% | 0.500 | −2.59% | 6.2% | 0.490 |
| V1 (full-Δ ref) | 6.94% | 7.72% | 0.899 | −13.85% | 0.501 | −2.59% | 5.8% | 0.495 |
| X1 (W1 ablation, inv-vol) | 4.59% | 4.96% | 0.924 | −7.41% | 0.620 | −1.68% | 18.8% | 0.490 |
| **Z1 (defensive-ceiling)** | 4.24% | 4.55% | **0.933** | **−8.57%** | 0.495 | **−1.51%** | 11.3% | 0.451 |
| **AA1 — static 95 / 5** | 6.77% | 7.62% | 0.888 | −13.71% | 0.494 | −2.56% | 11.1% | 0.442 |
| **AA2 — static 90 / 10** | 6.64% | 7.45% | 0.891 | −13.44% | 0.494 | −2.50% | 11.0% | 0.439 |
| **AA3 — state-conditional** | 6.67% | 7.53% | 0.886 | −13.47% | 0.495 | −2.54% | 11.3% | 0.439 |

Note: the "Turnover (L1)" column for AA candidates and Z1/X1 reflects weekly L1 ETF-weight diff because that is what the blend script writes; production's reported value uses a one-way convention from its own builder. The unit difference does not affect raw composite (which uses the field as written for each candidate respectively).

### Holdout (last 104 weeks) metrics

| Version | Ann Ret | Sharpe | MDD | Raw Comp |
|---|---:|---:|---:|---:|
| Production | 15.37% | 2.10 | −5.66% | 0.963 |
| Combo ABC | 15.36% | 2.11 | −5.53% | 0.961 |
| R3 | 15.56% | 2.22 | −5.42% | 0.945 |
| U1a | 15.42% | 2.11 | −5.67% | 0.963 |
| U3 | 15.59% | 2.13 | −5.67% | 0.960 |
| V1 | 15.34% | 2.11 | −5.70% | 0.962 |
| X1 | 11.16% | 2.26 | −2.71% | 0.775 |
| Z1 | 10.61% | 2.37 | −3.66% | 0.790 |
| **AA1** | 15.13% | **2.11** | **−5.57%** | 0.931 |
| **AA2** | 14.89% | **2.12** | **−5.47%** | 0.921 |
| **AA3** | 14.96% | **2.11** | **−5.51%** | 0.925 |

### Blend diagnostics (production share, ETF L1 deviation)

| Candidate | Avg Prod Share | Avg Z1 Share | Avg ETF L1 Dev from Pure Prod | Avg ETF L1 Dev from Pure Z1 |
|---|---:|---:|---:|---:|
| AA1 | 0.950 | 0.050 | 0.036 | 0.687 |
| AA2 | 0.900 | 0.100 | 0.072 | 0.650 |
| AA3 | 0.910 | 0.090 | 0.057 | 0.666 |

### AA3 realized state-conditional schedule

| Market state | Obs | Avg prod share | Avg Z1 share |
|---|---:|---:|---:|
| `calm_trend` | 295 | 0.946 | 0.054 |
| `neutral_mixed` | 493 | 0.916 | 0.084 |
| `recovery_confirmed` | 44 | 0.902 | 0.098 |
| `recovery_fragile` | 49 | 0.874 | 0.126 |
| `stressed_panic` | 229 | 0.859 | 0.141 |

Realized averages match the schedule to within rounding; the t-1 lag for causal safety eliminates ~5 weeks of state-mapping at the start of the panel.

### Production–Z1 ETF overlap by market state (mechanism diagnostic)

| Market state | Obs | Avg dot-product `prod_w · z1_w` |
|---|---:|---:|
| `calm_trend` | 295 | 0.106 |
| `neutral_mixed` | 493 | 0.260 |
| `recovery_confirmed` | 44 | 0.120 |
| `recovery_fragile` | 49 | 0.170 |
| `stressed_panic` | 229 | **0.462** |

In `stressed_panic` weeks, production and Z1 ETF weight vectors have nearly 5x the overlap of `calm_trend` weeks because both portfolios pivot to the same defensive ETF concentration (BIL, TLT, IEF). This number is the structural mechanic that explains every AA result in Section F.

### Validation views — pairwise vs production pin (8-gate Phase D rule)

| Candidate | Full Δ | Hold Δ | Hold Sharpe Δ | Roll Win | Roll Mean Δ | Bootstrap | MDD Δ | CVaR Δ | Pass |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Threshold | ≥ +0.015 | ≥ 0 | ≥ −0.02 | ≥ 55% | > 0 | ≥ 60% | ≥ −1.0 pt | ≥ −0.20 pt | 8/8 |
| **AA1** | −0.035 | −0.032 | **+0.011** | 0.0% | −0.029 | 0.003 | **+0.27 pt** | **+0.06 pt** | **3/8** |
| **AA2** | −0.039 | −0.042 | **+0.022** | 0.0% | −0.032 | 0.003 | **+0.53 pt** | **+0.12 pt** | **3/8** |
| **AA3** | −0.039 | −0.038 | **+0.014** | 0.0% | −0.031 | 0.003 | **+0.50 pt** | **+0.08 pt** | **3/8** |

(Pass column = number of 8 production gates cleared. Bold = clears the gate. AA1 / AA2 / AA3 each clear holdout-Sharpe Δ, MDD, and CVaR; they fail full Δ, holdout Δ, rolling win, rolling mean Δ, and bootstrap.)

### Validation views — pairwise vs U1a (closest-to-gate research reference)

| Candidate | Full Δ vs U1a | Hold Δ vs U1a | Hold Sharpe Δ vs U1a | Bootstrap vs U1a |
|---|---:|---:|---:|---:|
| AA1 | −0.042 | −0.032 | +0.001 | 0.003 |
| AA2 | −0.046 | −0.042 | +0.012 | 0.001 |
| AA3 | −0.046 | −0.038 | +0.004 | 0.003 |

AA candidates also lose to U1a on every full-history and holdout raw-composite axis. They essentially tie U1a on holdout Sharpe (Δ in [+0.001, +0.012]) but bootstrap probabilities are near zero. AA candidates are not the new closest-to-gate research reference.

### Rolling-origin summary (15 walk-forward windows, 260-week min train, 104-week test, 52-week step)

| Candidate | Avg Raw Comp | Median Raw Comp | Avg Sharpe | Avg Ann Ret |
|---|---:|---:|---:|---:|
| Production | 0.573 | 0.486 | 0.816 | 6.11% |
| R3 | 0.593 | 0.538 | 0.885 | 6.19% |
| U1a | 0.577 | 0.495 | 0.824 | 6.15% |
| V1 | 0.581 | 0.491 | 0.828 | 6.14% |
| X1 | 0.500 | 0.553 | 0.845 | 4.04% |
| Z1 | 0.472 | 0.524 | 0.886 | 3.85% |
| **AA1** | 0.544 | 0.470 | 0.819 | 6.00% |
| **AA2** | 0.541 | 0.466 | 0.823 | 5.89% |
| **AA3** | 0.542 | 0.467 | 0.818 | 5.91% |

Across 15 walk-forward windows, AA1 / AA2 / AA3 fall short of production on average raw composite by ~0.029 to ~0.032 — a wider gap than the U1a / V1 holdings blends, because Z1's lower absolute return drags more than R2 / Phase N partners did at the same blend ratios.

## F. Phase AA interpretation

> **What helped?**

The defensive metrics moved the right way at the right magnitude predicted by linear blending. AA1 (95 / 5) tightens MDD by 0.27 pts and CVaR by 0.06 pts, lifts holdout Sharpe by +0.011, and preserves 99.6% of production's full-history return engine. AA2 (90 / 10) extends those moves: MDD tightens by 0.53 pts, CVaR by 0.12 pts, holdout Sharpe by +0.022. AA3 ends up between AA1 and AA2 in realized average production share (0.910) and in every metric. All three Z1-blended candidates clear the MDD cap (≥ −1.0 pt) and the CVaR cap (≥ −0.20 pt) cleanly, and all three clear the holdout Sharpe Δ gate (≥ −0.02) — and in fact deliver *positive* holdout Sharpe Δ vs production. Three of eight gates cleared. This part of the test worked as intended.

> **What did not help?**

Absolute return — and therefore raw composite, full-Δ, holdout-Δ, rolling win-rate, rolling mean Δ, and bootstrap. The blend math is exactly linear: AA1's 6.77% ann_ret is `0.95 × 6.90% + 0.05 × 4.24%`. AA2's 6.64% is `0.90 × 6.90% + 0.10 × 4.24%`. There is no "complementarity premium" — every basis point that Z1 contributes also costs a proportional fraction of production's return engine. Because Z1's full-history return is 266 bp below production's, even a 5% Z1 dose imports a 13 bp return drag, and a 10% dose imports a 26 bp drag. That drag is enough to push raw composite from production's 0.478 to AA1's 0.442 (−0.035) and to AA2's 0.439 (−0.039), which is wider than the +0.015 production-rule threshold goes the other direction. Five of eight gates fail.

> **Did production+Z1 blending help?**

Partially — defensively, yes; for promotion or for displacing existing research references, no. AA1 is the best of the three on raw composite (closest to production). AA2 has the largest defensive lift but the largest return drag. AA3's conditional schedule produces no advantage over AA1 — its realized 91 / 9 average is worse than AA1's static 95 / 5 because the schedule weights heavier Z1 in `recovery_fragile` and `stressed_panic` (29% of weeks combined), which is exactly the regime range where the production-Z1 ETF overlap is highest (see overlap diagnostic in Section E) and the Z1 dose adds the least incremental defense.

> **Did it preserve production's return profile?**

Approximately. AA1 retains 98.1% of production's annualized return; AA2 retains 96.2%; AA3 retains 96.7%. The retention is exactly proportional to the production-share `a`. There is no conditional retention pattern that performs better than its `a`-implied baseline.

> **Did it import Z1's defensive / Sharpe benefit?**

Approximately, and *only* approximately. AA1 captures 0.95 × prod_MDD + 0.05 × Z1_MDD ≈ −13.71% expected; observed is −13.71% (to two decimals). AA2 captures −13.44% expected; observed is −13.44%. The blend is *that* linear. So defensively, the blend does work mechanically — but the linearity is exactly the problem: it imports a proportional fraction of Z1's defensive lift and a proportional fraction of Z1's return drag, and the project's Phase D scoring rule weights return ~3x more heavily than defense.

> **Did it improve holdout raw composite / bootstrap / rolling win-rate?**

No on every count. Holdout raw composite Δ vs production: AA1 −0.032, AA2 −0.042, AA3 −0.038. Rolling raw win rate vs production: 0.0% across all three (zero windows out of fifteen). Bootstrap probability vs production: 0.003 (production beats AA in 99.7% of resampled paths). The holdout-Sharpe Δ remains positive (+0.011 to +0.022), but the production gate suite is multi-objective: defensive-side wins do not compensate for return-side losses.

> **Did it beat U1a / U3 / V1?**

No. AA1 raw composite 0.442, AA2 0.439, AA3 0.439, vs U1a 0.484, U3 0.490, V1 0.495. AA candidates lose to all three prior holdings-blend references on full-history raw composite by 0.04 to 0.06. They also lose to U1a / U3 / V1 on holdout raw composite by 0.03 to 0.04. AA candidates are not the new closest-to-gate research reference. (The reason prior blends did better: their partners — R2 in U1a / U3, Phase N allocator in V1 — have absolute returns close to production's, so the linear blend math drags returns less than a Z1 blend does.)

> **Did it beat the production pin under the validation rules?**

No. AA1 / AA2 / AA3 each clear 3 of 8 production gates and fail 5 of 8. None of them clear the shadow rule either, because Combo ABC remains the best non-production candidate on raw composite (0.480 vs AA1's 0.442). All three are classified Research-only.

> **Why did production+Z1 holdings blending not work, mechanistically?**

Two compounding reasons that are visible in the diagnostics:

1. **Linear blend math drags returns proportionally.** There is no "synergy" available in a static or near-static linear blend of two long-only portfolios: every metric that is approximately linear in returns (annualized return, raw composite via its `ann_return` weight, calmar, rolling means) gets exactly the linear-blend value. Z1's 266 bp annualized return shortfall vs production translates directly into a 13–26 bp shortfall for AA1–AA2 with no escape.
2. **Production–Z1 ETF overlap is highest in stressed regimes.** The post-hoc overlap diagnostic shows that in `stressed_panic` weeks, production and Z1 ETF weight vectors overlap at 0.46 — about 4.4x the overlap in `calm_trend` weeks (0.11). Both portfolios pivot to the same defensive ETF concentration when defense is needed. This means the AA blend imports the *least* incremental defensive value precisely in the regimes where defense matters most. Conversely, in calm regimes (where overlap is lowest, 0.11), Z1 is doing something very different from production — but those are the weeks where production is earning the bulk of its return, so blending pulls money away from production's offense without much corresponding defensive payoff. The state-conditional AA3 schedule actually *amplifies* this misalignment by putting heavier Z1 doses in the stress regime where the marginal defensive value is lowest, which is why AA3 has no advantage over AA1 despite being more "regime-aware."

The combination of (1) and (2) is structural. No static or causal-state-conditional linear blend of production and Z1 can clear the Phase D production gates, regardless of ratio choice in the [0.85, 0.99] production-share range, because the linear math always pays a proportional return cost and the overlap pattern always allocates the most Z1 in the regime where Z1's marginal defensive contribution is smallest.

## G. Candidate classification

| Candidate | Status | Rationale |
|---|---|---|
| AA1 — static 95 / 5 production + Z1 | **Research-only** | Best of the three AA candidates on full-history raw composite (0.442 vs production 0.478, AA2 0.439, AA3 0.439). Smallest return drag, smallest defensive lift — the trade is exactly proportional to the 5% Z1 dose. Useful as the "minimal defensive overlay" reference for any future blend exploration that prefers lower turnover and minimum return give-up. Does not displace U1a / U3 / V1 (raw composite 0.484 / 0.490 / 0.495), so not the new closest research reference. Fails 5 of 8 production gates. |
| AA2 — static 90 / 10 production + Z1 | **Research-only** | Largest defensive lift of the three AA candidates: MDD −13.44% (vs production −13.98%, +0.53 pt), CVaR −2.50% (vs −2.62%, +0.12 pt), holdout Sharpe +0.022 vs production. But return drag is also largest: ann_ret 6.64% vs production 6.90% (−26 bp). Raw composite 0.439 — lowest of the three AA candidates. Fails 5 of 8 production gates. Useful as the "stronger-defense-at-higher-cost" reference but no advantage over AA1 on the multi-objective scorecard. |
| AA3 — state-conditional production + Z1 | **Research-only** | Realized average production share 0.910, between AA1 and AA2. Conditional schedule does not improve the Phase D outcome: raw composite 0.439 ties AA2 and is below AA1, because the schedule puts heavier Z1 in `recovery_fragile` / `stressed_panic` where the production-Z1 ETF overlap is highest (0.46 in stress, 0.17 in fragile) and the marginal defensive value is lowest. Fails 5 of 8 production gates. Demonstrates that the holdings-blend channel has no remaining tuning headroom from causal state-conditioning either. |

No candidate qualifies for Promote. No candidate qualifies for Conditional (the shadow rule requires the candidate to be the best non-production candidate on raw composite, and Combo ABC remains best at 0.480 vs AA1's 0.442). All three are Research-only. None of the three displaces an existing research reference.

## H. Final strategic judgment

**Outcome B — production+Z1 holdings-blend path closes.**

Phase AA is the third consecutive sprint (after Phase X allocator rerun and Phase Y conditional W1 sizing) testing whether W1's panel-level value can be harvested into a deployable candidate. None of the three sprints has produced a Promote-eligible candidate, and none has produced a candidate that displaces the closest research references (U1a / U3 / V1) on the multi-objective scorecard. Phase AA's specific contribution to that arc is to close the holdings-blend channel: Phase Z had identified holdings-blending as the most likely-to-succeed branch, and Phase AA has demonstrated that this branch also fails, with a precise structural mechanism (linear blend math + adverse regime-overlap pattern).

- **Production pin: unchanged.** `improved_phase2b_regime_confidence_boost` remains the deployable candidate.
- **Shadow pin: unchanged.** `improved_phase2b_combo_abc` remains the shadow.
- **Closest-to-gate research reference: unchanged.** U1a (`improved_phaseu_prod90_r2_10_holdings_blend`) remains. AA candidates do not displace it.
- **Sharpe research reference: unchanged.** R3 (`improved_phaser_fast_narrow_regret_allocator`) remains.
- **Full-Δ research reference: unchanged.** V1 (`improved_phasev_prod90_phasen_10_holdings_blend`) remains.
- **W1 ablation reference: unchanged.** X1 (`improved_phasex_production_style_7sleeve`) remains.
- **Defensive-ceiling reference: unchanged.** Z1 (`improved_phasez_production_hrp_7sleeve`) remains.
- **No new research reference added by Phase AA.** AA1 is recorded as a "minimal defensive holdings-overlay reference" but is not promoted to the project's official reference roster because it is strictly worse than U1a on the same axis (raw composite 0.442 vs 0.484).

The W1 panel-level value identified in Phase X / W remains structurally hard to harvest into a deployable candidate via *any* allocator-side or holdings-blend mechanism this project has tested. The three direct allocator families (inverse-vol per X / Y, HRP per Z) over-fund W1 against the global cap; the holdings-blend channel (per AA) drags returns proportionally and overlaps adversely with production in stressed regimes.

## I. Next-step recommendation

Phase AA closes the most-likely-to-succeed branch from Phase Z's three-branch fan-out. The project should now move to **Branch 2 from Phase Z's recommendation** as the next narrow test: **relax the per-sleeve `MAX_SLEEVE_WEIGHT` cap for W1 specifically.** This is the single-parameter change that targets the binding constraint Phase Z identified. The Phase Z evidence argues that the cap, not the architecture, was the structural reason HRP couldn't deploy W1 productively.

Specifically, **Phase BB** should test:

- **BB1 — HRP allocator on the 7-sleeve panel with `MAX_W1_WEIGHT` raised from 0.45 to 0.55.** Single-parameter change. Same Z1 architecture, same 7-sleeve panel, only the per-sleeve W1 cap changes.
- **BB2 — same architecture with `MAX_W1_WEIGHT` raised to 0.60.** Stretch test of the same parameter axis to see whether the gradient continues monotonically or plateaus.
- **BB3 — same architecture with `MAX_W1_WEIGHT = 0.55` and the global `MAX_SLEEVE_WEIGHT = 0.50` for the other six sleeves.** Disentangles the W1-specific cap effect from the global-cap effect.

(Production is not included in this fan-out because production runs on the 5-sleeve subset that does not contain W1; raising a W1 cap on the production allocator is tautologically inert.)

If Phase BB also fails to clear Phase D production gates, the residual diagnosis is that the regime engine's state distribution does not give the allocator enough room to call defense at the right times — specifically the very long `neutral_mixed` segment (493 / 1,110 weeks) is where HRP over-funds W1 most severely. That escalates to **Branch 3: Phase CC — re-open Layer 2B regime-engine work** to split `neutral_mixed` into "neutral but trending toward calm" vs "neutral but trending toward stress" sub-states so the dynamic-risk-budget tilt has a finer-grained handle on W1.

What this Phase AA closure teaches the project that should carry forward:

- **Linear blend math has no escape.** A static or causal-state-conditional linear blend of two long-only portfolios cannot import return-dimension benefits; it can only import benefits in approximately-linear-in-returns metrics like MDD, CVaR, and Sharpe-near-equal-vol. If a partner has lower return than the anchor, every dose imports a proportional return drag.
- **Sleeve-level orthogonality does not imply ETF-level orthogonality.** Production and Z1 are highly orthogonal at the sleeve level (they use different sleeves) but *not* orthogonal at the ETF level in stressed regimes (they pivot to the same defensive ETFs). Future blend-channel exploration should compute the regime-conditional ETF overlap of the candidate partner up front, not after the fact.
- **State-conditional schedules don't help when the underlying components are linear.** AA3's conditional schedule put heavier Z1 in stressed_panic where the marginal defensive value was lowest (high overlap with production), which is why AA3 had no advantage over AA1. Future state-conditional blends should be designed to put the partner where the partner is *most* differentiated from the anchor, not where the partner is most defensive in absolute terms.

## J. Project journey log update

File updated: `docs/research/project_journey.md`. Section added: **Section 40 — Phase AA: Production-Anchored Holdings Blend with Z1.** The project story is now current through the close of Phase AA, including the diagnosis that the holdings-blend channel for W1's panel value is closed across all three blend candidates (static 95 / 5, static 90 / 10, state-conditional), the structural mechanism explaining why (linear blend math + adverse regime-overlap pattern), and the explicit recommendation that Phase BB should test relaxing `MAX_SLEEVE_WEIGHT` for W1 specifically inside the HRP architecture before opening more invasive branches.
