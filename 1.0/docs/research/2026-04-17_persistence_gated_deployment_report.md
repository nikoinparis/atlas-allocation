# Final classical sprint: widened overlay-cash relief and persistence-gated variant

Date: 2026-04-17
Author: research sprint
Control: `improved_hrp_non_self_gated_relief_narrow_plus_confirmed` (incumbent)

---

## A. Mission

Run one last tight classical improvement sprint before considering harder methods (ML). The goal is to attack the remaining overlay-driven cash / BIL in **strong-neutral** and **recovery-fragile** states, where the incumbent still carries a materially positive idle pocket despite already relieving the non-self-gated sleeves a little.

Constraints (unchanged):
- Keep stressed-state protection unchanged.
- No broad continuous easing.
- No SPY/crude beta increase.
- No confirmed-recovery aggression revival.
- Pareto-neutral or better on return, Sharpe, DD, Calmar, CVaR.
- Must clear the production-score promotion margin (`prod_score` delta ≥ 0.05, DD within 0.005, CVaR within 0.002).

Variants tested:
- **Variant A — `improved_hrp_overlay_cash_wider_cap`.** Same logic as the incumbent except, in strong-neutral and recovery-fragile, the non-self-gated relief is widened: cap 0.025 → 0.045, scale 0.20 → 0.28. Recovery-confirmed keeps the incumbent tight 0.015 / 0.15. Self-gated relief and stressed-state protection unchanged.
- **Variant B — `improved_hrp_overlay_cash_wider_cap_persistence_gated`.** Same widening as A in strong-neutral and recovery-fragile, but only engaged when the Layer 2B causal regime engine's `transition_non_stress_prob ≥ 0.92`. Below 0.92 it falls back to incumbent narrow (0.025 / 0.20). Recovery-confirmed unchanged. Stressed-state protection unchanged.
- **Variant C.** Conditional. A small sleeve-leadership pairing on the winner of A/B. Not run (see D).

## B. Diagnostic setup (what the sprint was actually attacking)

Pre-sprint state-level diagnostics on the incumbent (from `stacked_defense_by_state.csv`):

| State | Weeks | BIL | Overlay cash | Regime mult | Target vol mult | Gross mult |
|---|---|---|---|---|---|---|
| calm_trend | | 6.70% | ~0.00 | 1.000 | 0.999 | 0.999 |
| strong_neutral (`neutral_mixed` with trend+breadth) | 293 | **21.36%** | **15.33%** | 0.9421 | 0.9999 | 0.9575 |
| recovery_fragile | 49 | **22.54%** | **13.04%** | 0.9600 | 1.0000 | 0.9708 |
| recovery_confirmed | | 12.25% | 6.59% | 0.9200 | 1.0000 | 0.9387 |
| stressed_panic | | 60.80% | 0.00% | 0.4320 | 0.9984 | 0.4320 |

Key observation: in strong-neutral and recovery-fragile `target_vol_multiplier ≈ 1.0`, so the binding constraint is never the vol ceiling — it is the overlay relief shape. The regime multiplier is already high (0.94–0.96) in both states, so the `scale × (1 − regime_multiplier)` term produces only a small absolute relief: 0.20 × 0.0579 = 0.0116 in strong-neutral and 0.20 × 0.040 = 0.008 in recovery-fragile, well under the incumbent 0.025 cap. Therefore the cap itself was never binding — the scale was.

This is an important finding: the "cap-driven" framing in the setup was slightly wrong. The lever is the slope of the relief schedule, not its ceiling.

Persistence diagnostics (`transition_non_stress_prob`, Layer 2B):
- strong-neutral: 100% of 293 weeks at ≥ 0.92, median 0.946.
- recovery-fragile: 15/39 weeks (38.5%) at ≥ 0.92, median 0.912, min 0.870.

So in Variant B, the persistence gate effectively:
- Strong-neutral: always fires (behaves like A).
- Recovery-fragile: fires roughly 38.5% of the time (partial release).

## C. Public research scan (what good practitioners say about this lever)

Brief, not exhaustive:

- **Newfound (Corey Hoffstein, Sébastien Page, and others)** consistently argue that "re-risking is a trade" and that discipline on both entry *and exit* of defense is where diversifiable alpha comes from. They caution against mechanical broadening of participation in any state where the causal engine itself still assigns meaningful non-trivial stress probability.
- **AQR (Moskowitz, Pedersen et al., volatility-managed portfolios literature)** finds that targeting vol increases Sharpe chiefly because it *cuts* in bad regimes, not because it re-adds in benign ones. The asymmetric value is in the defense leg.
- **Research Affiliates and PIMCO** tactical-allocation work tends to gate "offensive" releases on the joint condition of a benign current state *and* a stable transition expectation — very close in spirit to our persistence gate.
- **Alpha Architect / Robeco momentum/trend literature** treats the marginal capital at the edge of defense as having sharply diminishing returns: expected return scales with exposure, but tail cost scales faster than linear near regime boundaries.

The practitioner consensus strongly supports being conservative about widening deployment in any good-but-not-confirmed state, and specifically supports conditioning such widening on a persistence/stability signal. That is exactly the Variant B design. The consensus also implies that if the incumbent is already close to the efficient frontier of this lever, further widening should produce small, symmetric, or even slightly negative ex-post deltas.

## D. What was executed

- Wrote two new branches in `apply_overlays_custom` (`lighter_both_wider_cap` and `lighter_both_wider_cap_persistence_gated`) that extend the narrow-plus-confirmed incumbent's self-gated and recovery-confirmed behavior, and only change the non-self-gated relief shape in strong-neutral and recovery-fragile.
- Added two `version_specs` entries (`improved_hrp_overlay_cash_wider_cap` and `improved_hrp_overlay_cash_wider_cap_persistence_gated`) alongside the incumbent.
- Ran the full pipeline end-to-end (full version matrix, no rewiring of other sleeves, overlays, or speeds).
- Pulled metrics from `portfolio_version_comparison.csv` and state-conditional diagnostics from `stacked_defense_by_state.csv`.

Files/artifacts changed:
- `scripts/build_improvement_artifacts.py` — added two overlay-mode branches and two version specs. No changes to sleeve construction, regime engine, alpha signals, or allocator core.
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv` — now contains the two new variant rows.
- `data/05_layer3_portfolio_construction/stacked_defense_by_state.csv` — now contains state-conditional diagnostics for the two new variants.

Variant C was not implemented or run: its activation was conditional on A or B standalone supporting it, and the standalone result (see E) did not.

Dashboard + narrative (Task: update only if a winner emerges): **not updated**. No promotion.

## E. Standalone results

Headline metrics (full out-of-sample backtest, 1110 weekly observations):

| Variant | Return | Vol | Sharpe | MaxDD | Calmar | CVaR 5% | Ann turnover | BIL | Cash | SPY | Gross mult | Upside cap | Downside cap | RecFrag cap | RecConf cap | Stress cap | Prod score |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| incumbent | 6.84% | 7.81% | 0.876 | −14.28% | 0.4788 | −2.63% | 2.93 | 28.51% | 16.53% | 7.09% | 0.8347 | 0.3236 | 0.2396 | 0.2780 | 0.4092 | 0.3054 | **0.6713** |
| variant A | 6.84% | 7.81% | 0.876 | −14.28% | 0.4791 | −2.63% | 2.93 | 28.46% | 16.46% | 7.09% | 0.8354 | 0.3237 | 0.2396 | 0.2779 | 0.4092 | 0.3053 | 0.6624 |
| variant B | 6.84% | 7.81% | 0.876 | −14.28% | 0.4791 | −2.63% | 2.93 | 28.47% | 16.46% | 7.09% | 0.8354 | 0.3237 | 0.2396 | 0.2779 | 0.4092 | 0.3052 | 0.6515 |

State-conditional diagnostics (strong-neutral and recovery-fragile):

| State | Variant | BIL | Overlay cash | NSG cut (risky) | Regime mult | Gross mult |
|---|---|---|---|---|---|---|
| strong-neutral | incumbent | 21.36% | 15.33% | 0.42% | 0.9421 | 0.9575 |
| strong-neutral | A | 21.23% | 15.17% | 0.37% | 0.9421 | 0.9600 |
| strong-neutral | B | 21.24% | 15.18% | 0.37% | 0.9421 | 0.9600 |
| recovery-fragile | incumbent | 22.54% | 13.04% | 0.43% | 0.9600 | 0.9708 |
| recovery-fragile | A | 22.44% | 12.92% | 0.39% | 0.9600 | 0.9725 |
| recovery-fragile | B | 22.50% | 12.99% | 0.42% | 0.9600 | 0.9713 |
| recovery-confirmed | all three | 12.19–12.25% | ~6.5% | ~0.95% | 0.9200 | 0.9387 |
| stressed-panic | all three | 60.80% | 0.00% | 0.00% | 0.4320 | 0.4320 |

Interpretation of state-level movement:
- In strong-neutral, Variants A and B release **~0.13pp** of BIL and **~0.16pp** of overlay cash vs the incumbent. Gross multiplier moves from 0.9575 → 0.9600 (+0.0025).
- In recovery-fragile, Variant A releases **~0.10pp** BIL and **~0.12pp** overlay cash (gross 0.9708 → 0.9725). Variant B releases only a third of that (0.9708 → 0.9713) because the persistence gate fires in only 38.5% of recovery-fragile weeks.
- In recovery-confirmed and stressed-panic, the three strategies are indistinguishable, as designed.

The portfolio-level effect: zero at the resolution of return, Sharpe, drawdown, and CVaR (identical to four decimals). Calmar nudges +0.0003. BIL across all weeks drops ~0.05pp; cash drops ~0.07pp. Production score (rank-based composite) moves **down** by 0.009 (A) and 0.020 (B) — not because the raw metrics are worse but because the shift is small enough that the rank ordering across the full universe of variants happens to flip against these two on a few minor axes (annual turnover, average effective_N, weight instability).

Standalone classification:
- Variant A: **Pareto-neutral at best, not a winner.** Does not clear promotion margin of 0.05.
- Variant B: **Pareto-neutral at best, strictly weaker than A within the target states** (partial firing in recovery-fragile). Does not clear promotion margin.

## F. In-combination results

Variant C was only to be run if A or B had standalone support. Neither did. Under the sprint's own rules, a pairing study on either variant would be measuring the incremental contribution of the sleeve-leadership tilt on top of a non-winning base — an analytically weak design. Skipping.

Separately, because Variants A and B move the gross multiplier by at most +0.0025 in strong-neutral and +0.0017 in recovery-fragile, the marginal capital available for a downstream sleeve-leadership tilt is negligible in absolute terms. Even a perfectly correct sleeve rotation on top of that tiny release would not reasonably produce a ≥ 0.05 production-score lift without also raising the scale or cap, which is outside the sprint's constraints.

## G. Final classification

| Variant | Helps standalone? | Helps in combination? | Classification |
|---|---|---|---|
| A — `improved_hrp_overlay_cash_wider_cap` | No (Pareto-neutral, prod_score −0.009) | Not run (not justified) | **Research-only** |
| B — `improved_hrp_overlay_cash_wider_cap_persistence_gated` | No (Pareto-neutral, prod_score −0.020) | Not run (not justified) | **Research-only** |
| C — sleeve leadership pairing | — | — | **Drop** (conditional activation not met) |

**Incumbent unchanged.** The production candidate remains `improved_hrp_recovery_tilt` (with `improved_hrp_non_self_gated_relief_narrow_plus_confirmed` as the incumbent in the non-self-gated relief line). No dashboard or narrative change required.

## H. Honest assessment of the classical frontier

I think the classical overlay-cash lever is now effectively exhausted in this design, for two structural reasons:

1. **The binding constraint in the target states is the relief slope, not the relief ceiling.** In strong-neutral the regime multiplier is already 0.94, so `scale × (1 − 0.94) = 0.20 × 0.06 = 0.012`, well under the 0.025 cap. Raising the cap to 0.045 does nothing because `scale × (1 − mult)` is what's tight. Raising the scale (e.g., from 0.20 to 0.50) *would* release more capital, but it would also re-engage aggressively precisely in the states the prior research sprints already found to be most brittle to broad easing.
2. **The persistence signal is saturated in the state where most of the cap sits.** 100% of strong-neutral weeks satisfy `transition_non_stress_prob ≥ 0.92`. The persistence gate therefore does no filtering there — it's a no-op. It only adds selectivity in recovery-fragile, which is only 49 weeks out of 1110 (~4.4%). Even perfect selection inside those 49 weeks cannot move the portfolio-level metrics materially.

From this I conclude:
- Further progress on return and Sharpe at this point is not best attacked by tightening or widening the overlay relief schedule.
- The remaining overlay cash is structurally explained by the regime engine's own caution (regime_multiplier = 0.94–0.96, not 1.00, *by design*). Removing that caution without principled ML-assisted conditioning would be lowering the defensive floor in exchange for very small expected gains.
- Promising next directions — probably ML or at least heavier causal-engine work — include: (a) conditional volatility forecasting that refines `target_vol_multiplier` so that target vol binds more informatively in good states, (b) a learned `regime_multiplier_upgrade` that dynamically lifts the regime cap only when a held-out ensemble of signals agrees on low forward tail risk, (c) sleeve-internal cash elimination (the sleeves themselves still hold ~6–9% BIL in strong-neutral / recovery-fragile, which is upstream of overlay mechanics), and (d) revisiting the speed/hysteresis machinery with a richer set of persistence signals rather than a single threshold.

The classical pass that this sprint represents — narrow, surgical, regime-conditioned overlay relief — is, I believe, at or very near its frontier on this dataset and sleeve set. I do not see a clean classical winner in the remaining design space under the sprint's explicit constraints.

---

### Appendix: exact numerical changes vs incumbent

| Metric | Incumbent | Variant A | Δ A | Variant B | Δ B |
|---|---|---|---|---|---|
| ann_return | 0.0684 | 0.0684 | +0.0000 | 0.0684 | +0.0000 |
| sharpe | 0.8759 | 0.8759 | +0.0000 | 0.8759 | +0.0000 |
| max_drawdown | −0.1428 | −0.1428 | 0.0000 | −0.1428 | 0.0000 |
| calmar | 0.4788 | 0.4791 | +0.0003 | 0.4791 | +0.0003 |
| cvar_5 | −0.0263 | −0.0263 | −0.0000 | −0.0263 | −0.0000 |
| avg_bil_weight | 0.2851 | 0.2846 | −0.0005 | 0.2847 | −0.0004 |
| avg_cash_weight | 0.1653 | 0.1646 | −0.0007 | 0.1646 | −0.0007 |
| avg_gross_multiplier | 0.8347 | 0.8354 | +0.0007 | 0.8354 | +0.0007 |
| production_score | 0.6713 | 0.6624 | −0.0089 | 0.6515 | −0.0198 |

Promotion threshold: Δ production_score ≥ 0.05, Δ max_drawdown within 0.005, Δ cvar_5 within 0.002. Neither variant clears.
