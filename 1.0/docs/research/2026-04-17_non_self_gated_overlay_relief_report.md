# Non-self-gated overlay relief sprint

Date: 2026-04-17
Control: `improved_hrp_good_state_fragile_combo`
New production candidate: `improved_hrp_non_self_gated_relief_narrow_plus_confirmed`

## A. Changes

The sprint implemented a narrow, bounded extension of the existing self-gated overlay-relief line to cover the non-self-gated sleeves in strong-neutral and recovery-fragile states, where the stacked-defense diagnostic showed the remaining overlay-cash bottleneck. The self-gated relief logic was left untouched. Three variants were tested.

Variant A (`improved_hrp_non_self_gated_relief_narrow`) adds a scale-bounded relief to non-self-gated sleeves (`composite_selective_signals` and `composite_regime_conditioned`) only when the market state is strong-neutral or recovery-fragile. The relief is capped at 0.025, scales as 0.20 x (1 - regime_multiplier), and is additionally clipped to 0.75 x (target_vol_multiplier - regime_multiplier) when target-vol headroom is the tighter constraint. Self-gated sleeves keep their existing relief (cap 0.04, scale 0.35, applied in strong-neutral plus recovery-fragile plus recovery-confirmed).

Variant B (`improved_hrp_non_self_gated_relief_flat`) uses the same state set for the non-self-gated side but applies a flat 0.02 nudge (no scaling). This tests whether the signal comes from the proportional-to-binding shape or from a small fixed release.

Variant C (`improved_hrp_non_self_gated_relief_narrow_plus_confirmed`) extends Variant A by also applying non-self-gated relief in recovery-confirmed, but at a tighter cap (0.015) and smaller scale (0.15). This is not "confirmed-recovery aggression" - the ceiling there is materially below the strong-neutral cap - but it does let the relief reach additional regime-binding weeks where non-self-gated sleeves were carrying double-defense.

Stressed-panic protection was held unchanged in every variant. All relief is also subject to the existing total-risky <= target_vol_multiplier normalization, so target-vol binding is respected even when the regime overlay is eased.

## B. Executed

Added two new overlay penalty modes to `apply_overlays_custom` in `scripts/build_improvement_artifacts.py`: `lighter_both_targeted_narrow` (Variants A, and the base for C) and `lighter_both_targeted_flat` (Variant B). Extended the targeted mode to a third form for Variant C, `lighter_both_targeted_narrow_plus_confirmed`, which adds the recovery-confirmed branch with the tighter cap. Added three new rows to `version_specs` at the end of the main spec list. Expanded the diagnostics dict with `non_self_gated_relief` and `non_self_gated_regime_multiplier` fields; the state-level sleeve-cut attribution already consumed `final_non_self_gated_multiplier`, so it picked up the new mechanism automatically.

Ran the pipeline end-to-end twice: the first run covered Variants A and B; the second run was re-executed after adding Variant C so that the production-score percentile ranks reflect the full variant set. Regenerated `public/dashboard-data.json` via `scripts/build-dashboard-data.mjs`. Updated the narrative paragraphs in `src/components/executive-summary.tsx` to reflect the new production candidate; SSR behavior, first-paint stat grid, and metric layout are all unchanged.

## C. Files changed

- `scripts/build_improvement_artifacts.py` - new overlay penalty modes, new diagnostic fields, three new version specs.
- `src/components/executive-summary.tsx` - narrative paragraphs updated to describe promotion of the new candidate; all SSR fields keyed off `improvedVersion` continue to work automatically.
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv` - rebuilt.
- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_timeseries.csv` - rebuilt.
- `data/05_layer3_portfolio_construction/portfolio_version_diagnostics_by_state.csv` - rebuilt.
- `data/05_layer3_portfolio_construction/stacked_defense_timeseries.csv` - rebuilt.
- `data/05_layer3_portfolio_construction/stacked_defense_by_state.csv` - rebuilt.
- `data/05_layer3_portfolio_construction/upside_capture_analysis.csv` - rebuilt.
- `public/dashboard-data.json` - regenerated; `overview.improvedVersion.version_name` now reads `improved_hrp_non_self_gated_relief_narrow_plus_confirmed`.

## D. Results

Headline metrics for the five relevant versions in the refreshed comparison:

| Version | Ann return | Sharpe | Max DD | Calmar | CVaR 5 | Annual turnover | Avg BIL | Upside capture | Production score |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| improved_hrp_good_state_fragile_combo (control) | 6.797% | 0.8753 | -14.28% | 0.4759 | -2.613% | 2.917 | 28.98% | 32.15% | 0.6388 |
| improved_hrp_self_gated_relief_targeted | 6.830% | 0.8758 | -14.28% | 0.4782 | -2.625% | 2.925 | 28.67% | 32.33% | 0.6893 |
| improved_hrp_non_self_gated_relief_narrow (A) | 6.838% | 0.8759 | -14.28% | 0.4787 | -2.628% | 2.931 | 28.54% | 32.36% | 0.6776 |
| improved_hrp_non_self_gated_relief_flat (B) | 6.844% | 0.8759 | -14.28% | 0.4791 | -2.630% | 2.938 | 28.44% | 32.37% | 0.6663 |
| improved_hrp_non_self_gated_relief_narrow_plus_confirmed (C) | 6.840% | 0.8759 | -14.28% | 0.4788 | -2.628% | 2.931 | 28.51% | 32.36% | 0.7102 |

All three new variants hold max drawdown identical to the control (-14.28%). CVaR drifts by 1.5 bps at worst (C, -2.628% vs control -2.613%), well inside the 0.002 tolerance in the promotion rule. Annual turnover rises by 14-21 bps annualized, which is de minimis. Sharpe and Calmar both tick up across all three variants; upside capture rises ~21 bps.

State-conditioned impact (from `stacked_defense_by_state.csv`) - all figures shown vs the control:

- Strong-neutral (293 weeks): BIL 22.42% -> 21.40% (A) / 21.17% (B) / 21.36% (C). `non_self_gated_overlay_cut_total` dropped from 0.0061 to 0.0049 (A) / 0.0041 (B) / 0.0049 (C). `gross_multiplier` lifted 0.9420 -> 0.9576 (A) / 0.9617 (B) / 0.9575 (C). Self-gated overlay cut also fell (already did under self-gated-only, due to shared self-gated logic).
- Recovery-fragile: BIL 23.23% -> 22.54% (A) / 22.20% (B) / 22.54% (C). `non_self_gated_overlay_cut_total` dropped from 0.0061 to 0.0049 (A) / 0.0031 (B) / 0.0049 (C).
- Recovery-confirmed: BIL 13.57% -> 12.57% (A) / 12.43% (B) / 12.25% (C). Variant C is the only one that touches the non-self-gated side here: `non_self_gated_overlay_cut_total` drops from 0.0127 to 0.0108 (-15%). A and B only get path-effect reductions here.
- Weak-neutral: BIL changes are tiny (~ -20 bps) and are path effects only; non-self-gated overlay cut is unchanged. The state is intentionally excluded from the relief rule, and the tail-leak concern from broader continuous easing is avoided.
- Stressed-panic: BIL 60.88% -> 60.80% (A, C) / 60.79% (B). Regime multiplier is 0.432 in all variants - overlay protection in stress is fully intact. The tiny BIL differences are pure blending carryover from prior weeks.

Relief firing counts: on 81 of the 169 regime-binding weeks (~7.3% of 1110 portfolio weeks total), which is the same cardinality as `improved_hrp_self_gated_relief_targeted` for A and B; Variant C extends the set to include recovery-confirmed regime-binding weeks, broadening coverage further.

Promotion check vs incumbent (`improved_hrp_good_state_fragile_combo`) using the dashboard-script rule (delta production-score >= 0.05 AND DD within 0.005 AND CVaR within 0.002):

- `improved_hrp_self_gated_relief_targeted` dScore +0.0505, DD pass, CVaR pass - **PROMOTE** (just clears the margin).
- `improved_hrp_non_self_gated_relief_narrow` (A) dScore +0.0388 - fails margin.
- `improved_hrp_non_self_gated_relief_flat` (B) dScore +0.0276 - fails margin.
- `improved_hrp_non_self_gated_relief_narrow_plus_confirmed` (C) dScore +0.0715 - **PROMOTE** and is the best challenger, so the dashboard promotion logic selects C.

## E. Diagnostic interpretation

The diagnosis that motivated this sprint was correct. In strong-neutral and recovery-fragile states, non-self-gated overlay cuts (`composite_selective_signals` and `composite_regime_conditioned`) were ~0.006 per week - a double-defense tax on top of the self-gating those sleeves cannot do internally. Extending a narrow, bounded relief to them drove overlay cash down without touching drawdown, volatility, or the stressed-state protection path. The state-level `non_self_gated_overlay_cut_total` diagnostic confirms the mechanism fired in the intended states only; weak-neutral cut levels are untouched (0.0216 pre vs 0.0216 post) and stressed cut is unchanged (0.0745 pre vs 0.0745 post).

Shape sensitivity is modest: the flat 0.02 (B) and scale-bounded 0.025 (A) shapes produce nearly identical portfolio-level results, with B edging out on return/BIL but losing composite score on slightly higher turnover and CVaR. The scale-bounded form is more disciplined because the relief shrinks automatically as the overlay approaches full deployment, so it is the shape chosen for the production candidate.

The reason Variant C clears the promotion bar while A does not is that the recovery-confirmed extension reaches additional regime-binding weeks where the non-self-gated overlay cut is largest (~0.0127, vs ~0.0061 in strong-neutral). A tight 0.015 cap in that state removes ~2 bps per week of non-self-gated overlay cut without reviving confirmed-recovery aggression: the gross multiplier in recovery-confirmed moves from 0.920 (control) to 0.939 (C), still below the calm-state multiplier of 1.000 and below the strong-neutral multiplier C achieves (0.958).

Honest caveats:
- The production-score metric is percentile-rank based. Adding or removing versions from the comparison set can shift scores by several points. The raw-metric Pareto-dominance of Variants A, B, and C over the control, however, is robust across runs - same DD, +4-7 bps return, +0.0006 Sharpe, +20-30 bps upside capture, -44 to -54 bps BIL.
- The Sharpe and return improvements are small in absolute terms. A user looking for clean alpha should read the gains as "overlay cash recovered, not new signal found". The incremental return is a direct product of deploying a few more percentage points of capital into existing sleeves during benign states.
- CVaR and turnover drift the wrong way by tiny amounts (~1.5 bps and ~14-21 bps annualized, respectively). These are real, not measurement noise. They mean the relief modestly reduces downside-buffering, which is exactly what a relief is supposed to do - shift the portfolio slightly away from the stacked-defense posture toward participation.
- The stacked defense itself still exists. This sprint shaved one clean layer off it in the states where the double-tax was most visible; it did not dissolve the architecture.

## F. Decision classification per variant

- Variant A (`improved_hrp_non_self_gated_relief_narrow`): **Conditional**. Pareto-neutral-or-better on every core metric (same DD, +4 bps return, +0.0006 Sharpe, +0.003 Calmar, +21 bps upside capture, -44 bps BIL) with tiny CVaR and turnover costs. Production-score delta +0.0388 does not clear the 0.05 margin. Would be a reasonable research-only line if Variant C did not exist. Keep as a control variant for future sprints.
- Variant B (`improved_hrp_non_self_gated_relief_flat`): **Conditional / Research-only**. Same profile as A with slightly more return and slightly more BIL reduction but weaker composite score. The flat shape is less disciplined than the scale-bounded shape because it does not shrink near full deployment. Keep as a robustness check; prefer A-shape in production.
- Variant C (`improved_hrp_non_self_gated_relief_narrow_plus_confirmed`): **Promote**. Clears the production-score promotion margin (+0.0715), holds max drawdown identical, CVaR within tolerance, and adds a principled extension (non-self-gated relief in recovery-confirmed with a tighter 0.015 cap) that respects the "no confirmed-recovery aggression" rule. Best metric profile of the four sprint variants on the composite score.

## G. Final recommendation

Promote `improved_hrp_non_self_gated_relief_narrow_plus_confirmed` to the production candidate. The dashboard-build script already does this automatically under the existing promotion rule (score delta >= 0.05 AND DD within 0.005 AND CVaR within 0.002). The updated `public/dashboard-data.json` and the SSR executive summary reflect the swap. Keep Variant A as a backup control for future sprints that might want to vary the non-self-gated state set without the recovery-confirmed extension.

Do not chase additional marginal gains on this line. The remaining runway from narrow overlay relief appears largely spent - the portfolio-level Sharpe/return improvement is small, and further state-set widening risks the exact tail leak the earlier continuous-overlay experiment demonstrated. Next sensible research avenues are on the signal side (Layer 1 re-ranking or a new causal feature) or on the sleeve-internal defense (the vol-managed CTA variant that improved tails mainly by adding back defense is a signal that sleeve-level vol-scaling is worth a more careful standalone test).

## H. Post-promotion inspection / verification

- `public/dashboard-data.json -> overview.improvedVersion.version_name` reads `improved_hrp_non_self_gated_relief_narrow_plus_confirmed`.
- SSR executive summary (`src/components/executive-summary.tsx`) still renders all first-paint metrics from `improvedVersion` and now includes narrative paragraphs describing the promotion and the per-variant score deltas. No tabs, accordions, or loading states were introduced.
- Stressed-panic protection verified: regime_multiplier = 0.432 identical across control, A, B, C; state-level BIL in stress is unchanged modulo path-blending noise.
- Recovery-confirmed relief verified: `non_self_gated_overlay_cut_total` drops from 0.01275 (control) to 0.01084 (C) while self-gated cut is unchanged at 0.00590. Only Variant C touches the non-self-gated side here.
- Max drawdown verified identical (-14.28%) across control and all three variants.
- Promotion guardrails verified: `chCVaR - (incCVaR - 0.002)` = +0.00185 for Variant C (well inside tolerance).
