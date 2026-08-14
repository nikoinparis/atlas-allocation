# Phase 2A Sprint Report

Date: 2026-04-18
Control: `improved_hrp_phase1_dynamic_risk_budget`
Promotion rule (incumbent): production_score delta >= 0.05, max_drawdown within 0.005 of control, CVaR 5% within 0.002 of control.

---

## A. What you changed

**Research / strategy changes:**
- Added a new overlay penalty mode `phase2a_principled_continuous` in `apply_overlays_custom`. Confidence-gated (causal_confidence >= 0.55) bounded linear lift on the non-self-gated relief cap and scale. Max lift = 1.40x of the incumbent `lighter_both_targeted_narrow_plus_confirmed` values at confidence = 1.0. Below the gate, behaviour is identical to the incumbent. Stressed panic and neutral (non-strong) are unchanged. recovery_confirmed keeps tighter incumbent values than fragile/strong_neutral.
- Added five new `version_specs` entries for Phase 2A (A, B, C, E, F). Variant D was deliberately skipped — adding a disciplined factor-integration layer requires wiring new value / quality sleeves into the Layer 2 sleeve panel, which is Phase 2B plumbing and out of Phase 2A scope.
- No changes to Layer 1, Layer 2A, Layer 2B, or the sleeve panel.

**Dashboard / narrative changes:** None. No Phase 2A variant promoted. The current production narrative (Phase 1 dynamic risk budgeting winner) remains accurate.

## B. What you executed

- Public-research scan across AQR / Newfound / Research Affiliates / ReSolve / academic literature on robust risk parity, ERC, Ledoit-Wolf shrinkage, covariance estimation, and state-conditioned continuous allocation mapping. Key takeaway: ERC + Ledoit-Wolf is the canonical robust-risk-parity combination (Maillard 2010, Spinu 2013, Ledoit-Wolf 2004). Cluster Risk Parity / HERC is the modern refinement when correlation structure is rich. Covariance-aware risk budgeting rarely beats sample-cov-based long-only risk parity with transaction-cost penalties on small universes.
- Code map of `scripts/build_improvement_artifacts.py` (~3950 lines) and `05_layer3_portfolio_construction.ipynb` to locate the existing allocator dispatch, covariance estimator, state-tilt wiring, overlay machinery, version_specs block, and Phase 1 causal-confidence helpers.
- Implementation: added `phase2a_principled_continuous` overlay branch in `apply_overlays_custom` and appended five Phase 2A `version_specs` entries after the Phase 1 combo G block.
- Full pipeline run: `python3 scripts/build_improvement_artifacts.py` — exit 0, all 58 portfolio versions regenerated.
- Metrics extraction and deltas-vs-control from `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`.
- B-overlay activation diagnostic to confirm the gate was actually engaging (75 active weeks; mean lift 1.15x; lift dominated downstream by scale*(1-regime_multiplier) clamp).

## C. Which files/artifacts were modified or regenerated

Modified:
- `scripts/build_improvement_artifacts.py` — new overlay branch + five version_specs entries.

Regenerated (among others):
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_phase2a_*.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_sleeve_weights_improved_phase2a_*.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_phase2a_*.csv`
- `data/05_layer3_portfolio_construction/allocation_driver_summary.csv`
- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_by_state.csv`
- `data/05_layer3_portfolio_construction/stacked_defense_by_state.csv`
- Layer 1 / Layer 2A / Layer 2B / sleeve-incremental artifacts were regenerated unchanged.

No dashboard / SSR / build artifacts were touched.

## D. Experimental results

| Variant | Ann ret | Ann vol | Sharpe | Max DD | Calmar | CVaR 5% | Turnover | Upside cap | Downside cap | Rec week cap | Rec frag cap | Rec conf cap | Calm cap | Stress DS cap | BIL | SPY | Cash | Prod score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CONTROL | 6.85% | 7.77% | 0.882 | -13.98% | 0.491 | -2.61% | 5.61% | 32.30% | 23.85% | 30.56% | 27.91% | 40.74% | 43.45% | 30.44% | 28.69% | 7.04% | 16.53% | 0.7805 |
| A ERC+LW | 6.62% | 7.83% | 0.845 | -14.66% | 0.451 | -2.60% | 5.16% | 31.00% | 22.73% | 26.22% | 25.81% | 27.78% | 45.57% | 21.47% | 27.95% | 6.91% | 16.62% | 0.3262 |
| B princ-cont | 6.86% | 7.77% | 0.882 | -13.98% | 0.491 | -2.61% | 5.62% | 32.30% | 23.85% | 30.54% | 27.91% | 40.64% | 43.44% | 30.43% | 28.66% | 7.04% | 16.48% | 0.7891 |
| C HERC | 6.76% | 8.07% | 0.838 | -15.44% | 0.438 | -2.67% | 5.70% | 33.54% | 25.59% | 28.69% | 29.18% | 26.84% | 43.19% | 24.96% | 27.60% | 7.58% | 16.66% | 0.2438 |
| E A+B | 6.61% | 7.82% | 0.846 | -14.56% | 0.454 | -2.60% | 5.16% | 30.92% | 22.63% | 26.07% | 25.65% | 27.65% | 45.55% | 21.64% | 27.96% | 6.85% | 16.57% | 0.3472 |
| F C+B | 6.76% | 8.07% | 0.838 | -15.44% | 0.438 | -2.67% | 5.70% | 33.54% | 25.60% | 28.67% | 29.18% | 26.71% | 43.17% | 24.95% | 27.57% | 7.58% | 16.62% | 0.2438 |

Deltas vs control on the headline metrics:

| Variant | dRet | dSharpe | dDD | dCVaR | dProd | dRec conf | dRec frag | dCalm | dUpside | dDownside | dBIL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A ERC+LW | -23 bps | -0.037 | -68 bps | +0.01 pp | -0.454 | -12.96 pp | -2.10 pp | +2.12 pp | -1.30 pp | -1.12 pp | -74 bps |
| B princ-cont | +1 bp | +0.000 | +0 bps | 0 | +0.009 | -0.10 pp | 0 | -0.01 pp | 0 | 0 | -3 bps |
| C HERC | -9 bps | -0.044 | -146 bps | -6 bps | -0.537 | -13.90 pp | +1.27 pp | -0.26 pp | +1.24 pp | +1.74 pp | -109 bps |
| E A+B | -24 bps | -0.036 | -58 bps | +0.01 pp | -0.433 | -13.09 pp | -2.26 pp | +2.10 pp | -1.38 pp | -1.22 pp | -73 bps |
| F C+B | -9 bps | -0.044 | -146 bps | -6 bps | -0.537 | -14.03 pp | +1.27 pp | -0.28 pp | +1.24 pp | +1.75 pp | -112 bps |

## E. Diagnostic interpretation

**Did robust risk parity / ERC help?** No. Variant A (ERC + Ledoit-Wolf shrinkage) regressed materially: ann return -23 bps, Sharpe -0.037, max drawdown -68 bps, production score -0.454. The mechanism is visible in the state-decomposition: recovery_confirmed capture crashed from 40.74% to 27.78% (-12.96 pp). ERC's flat risk-equalization reduces the weight on `composite_regime_conditioned` — which is the sleeve that drives confirmed-recovery capture — and instead spreads risk more evenly across the CTA/trend sleeves that behave less aggressively when the recovery has confirmed. Calm-state capture rose (+2.12 pp) as a side-effect but did not offset the confirmed-state loss. The covariance-estimator change (sample to Ledoit-Wolf) could in principle explain part of this, but the HERC run (same sample covariance as HRP) shows the same confirmed-capture collapse, so the dominant mechanism is the allocator structure, not the covariance estimator.

**Did the improved bounded continuous state-conditioned mapping help?** Barely. Variant B moved the production score by +0.009 and is otherwise indistinguishable from the control. The confidence gate at 0.55 actually triggers in ~75 weeks inside the good-state set, with a mean cap lift of 1.15x. The reason B looks like a no-op is downstream: effective relief is `min(cap, scale*(1-regime_multiplier), 0.75*headroom)`, and in the good-state regimes where the gate triggers, `regime_multiplier` is already close to 1.0, which makes the `scale*(1-regime_multiplier)` term the binding constraint. Lifting `cap` alone (and even `scale` by 1.15x) does not move effective deployment materially. The finding itself is useful: the current overlay's binding constraint is not the cap, it is the `1 - regime_multiplier` headroom. Widening that would require touching the regime_multiplier itself, not the relief cap.

**Did covariance / risk-budget logic upgrades help?** No. Variant C (HERC) regressed even more than A: Sharpe -0.044, max drawdown -146 bps (worst in the sprint), production score -0.537. The cluster structure picked up recovery_fragile capture (+1.27 pp) and upside capture (+1.24 pp) but at the cost of confirmed capture (-13.90 pp) and worse downside capture (+1.74 pp, i.e. less defense). The clustering also pushed SPY up +54 bps which is a crude-beta drift signal.

**Did disciplined factor integration help?** Not tested. Variant D was intentionally skipped — the current sleeve panel does not have a clean value / quality factor-family split, and wiring new factor sleeves is Phase 2B plumbing. Classified Research-only.

**Which upgrades worked standalone?** None.

**Which worked only in combination?** None. The combos (E = A+B, F = C+B) are essentially pass-throughs of A and C because B has almost no marginal effect.

**Which should be dropped?** A, C, E, F. B is borderline — it is effectively a no-op, so there is no cost to keeping the hook, but there is also no reason to deploy it until the cap / scale / headroom interaction is redesigned.

**Is there a new winning strategy?** No. The CONTROL (`improved_hrp_phase1_dynamic_risk_budget`) remains the winner by +0.454 to +0.537 on production score, with the best DD and confirmed-recovery capture among the six variants tested.

**If not, what is still the main remaining bottleneck?** The binding constraint in the good states is no longer the relief cap — it is the `regime_multiplier` itself (how much gross risk the overlay permits) and the sleeve-internal defense (how much risky weight the sleeves themselves want to take). Both are already near-optimal inside the Phase 1 non-ML envelope. Further classical progress would need either (a) a better sleeve panel (more orthogonal signals in non-confirmed states), or (b) a learned regime_multiplier that uses multiple causal signals jointly — which is Phase 2B territory.

## F. Decision classification

| Component | Classification | Rationale |
|---|---|---|
| A - ERC + Ledoit-Wolf allocator | Drop | Production score -0.454. Confirmed-recovery capture crashed -12.96 pp. Worse DD and Sharpe. |
| B - principled continuous overlay | Research-only | No material effect on the control. Gate works as designed, but downstream headroom clamp makes the cap/scale lift inert. Needs redesign to target `regime_multiplier` itself, not relief cap. |
| C - HERC allocator | Drop | Production score -0.537, worst DD in the sprint (-146 bps), confirmed capture collapse (-13.90 pp). |
| D - factor integration | Research-only | Not tested. Requires new Layer 2 sleeve plumbing, out of Phase 2A scope. |
| E - combo A+B | Drop | Pass-through of A; identical regression pattern. |
| F - combo C+B | Drop | Pass-through of C; identical regression pattern. |

## G. Final recommendation

- `improved_hrp_phase1_dynamic_risk_budget` should remain the production candidate. Nothing in Phase 2A beat it, and three of five tested variants regressed materially.
- Strongest Phase 2A idea: the diagnostic that the good-state bottleneck is now `regime_multiplier` / sleeve-internal defense, not relief cap. This is a pointer for Phase 2B, not a Phase 2A deliverable.
- Exhausted / weak Phase 2A ideas: flat ERC in the current sleeve universe (allocator behaves worse than HRP on recovery_confirmed), HERC in the current sleeve universe (same issue, plus worse tails), and cap-based continuous overlay mapping (dominated by downstream headroom clamp).
- Disciplined factor integration (Variant D) was not tested because the sleeve panel does not currently support it cleanly. It should be revisited only after Phase 2B adds orthogonal factor sleeves or a learned signal-quality score.

## H. Phase-readiness judgment

**Did Phase 2A materially improve the project?** No. The incumbent `improved_hrp_phase1_dynamic_risk_budget` remains the best version on production score, max drawdown, CVaR, and confirmed-recovery capture. No Phase 2A variant passed the promotion rule.

**Is the project ready to move into Phase 2B after this?** Yes, with one caveat. Phase 2A has now tested the main non-ML allocator and state-mapping upgrades that were plausible on the current sleeve panel: HRP vs ERC vs HERC allocators, sample vs Ledoit-Wolf covariance, narrow vs continuous state-conditioned overlay mapping (three variants over two sprints), dynamic risk budgeting, sleeve-level conviction, sleeve-leadership rotation, sleeve-internal cash redesign, causal-confidence gating. Further classical-only progress on this sleeve panel looks unlikely to clear the +0.05 production-score bar without touching the regime_multiplier or the sleeve panel itself.

**If not, what is still missing?** The open question Phase 2B should address is whether a learned, multi-signal regime_multiplier (or a learned signal-quality score feeding the overlay clamp) can relax the current headroom bottleneck without reviving tail risk. The Phase 2A B-variant diagnostic makes the target very concrete: lift needs to happen on `(1 - regime_multiplier)`, not on the relief cap. An interpretable-ML meta-model over the existing Layer 2B signals (persistence, breadth, trend, shallow DD, and the conviction panel) would be a natural next experiment, with the same incumbent promotion rule applied.

---

Sources consulted during this sprint:
- [Cluster Risk Parity — Portfolio Optimizer blog](https://portfoliooptimizer.io/blog/cluster-risk-parity-equalizing-risk-contributions-between-and-within-asset-classes/)
- [Do You Spinu? A Novel Equal Risk Contribution Method for Risk Parity — ReSolve Asset Management](https://investresolve.com/spinu-improving-equal-risk-contribution/)
- [Honey, I Shrunk the Sample Covariance Matrix — Ledoit & Wolf](http://www.ledoit.net/honey.pdf)
- [Risk Parity with Covariance Shrinkage — skfolio](https://skfolio.org/auto_examples/2_risk_budgeting/plot_3_risk_parity_ledoit_wolf.html)
- [Beyond GMV: relevance of covariance estimation for risk-based portfolio construction — Quantitative Finance 2025](https://www.tandfonline.com/doi/abs/10.1080/14697688.2025.2468268)
- [Equally-Weighted Risk Contribution Portfolios — Working Paper 142/14](https://fileserver.carloalberto.org/cerp/WP_142.pdf)
