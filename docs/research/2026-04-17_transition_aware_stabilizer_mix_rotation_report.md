# Transition-Aware / Stabilizer / Mix-Rotation Study

Date: 2026-04-17
Control: improved_hrp_good_state_fragile_combo

## A. Changes Proposed

The control still underparticipates in sustained good states (avg BIL 28.98%, avg cash 17.06%; neutral_mixed is 45% of history and holds 23.6% BIL). Momentum-family signals already exist in the stack, so this study targets the overlay / state / sleeve-mix layer rather than re-adding signals. Five variants were wired, each controlled against the same control.

- Variant A `good_state_fragile_transition_aware`: adds a causal, observable transition-matrix feature. At each week t, compute trailing-3-year (156w) P(state stays) and P(next state is not stressed_panic) from pairs strictly before t. In strong-neutral weeks, when both measures are elevated (persistence >= 0.70 and P(non-stress next) >= 0.92), lift the strong-neutral overlay floor 0.94 -> 0.97. Sleeve tilt left at fragile_plus.
- Variant B `good_state_fragile_stabilizer`: one-sided hysteresis on entry into stressed_panic. Delay the first week of a stressed_panic entry unless drawdown is already <= -10% or risk_regime_score > 0.85. Exits are never delayed. Overlay floors identical to control.
- Variant C `good_state_fragile_strong_offense`: keep control fragile/confirmed floors; raise strong-neutral floor 0.94 -> 0.98 and the broad neutral base floor 0.80 -> 0.83. Sleeve tilt left at fragile_plus.
- Variant D `good_state_mix_rotation`: same overlay floors as control; new sleeve-tilt mode fragile_plus_mix_rotation. In calm_trend, cut composite_regime_conditioned x0.80 and lift dual_momentum / cta_trend x1.14, composite_selective_signals x1.12. In recovery_fragile, cta_trend x1.15, dual_momentum x1.12, composite_regime_conditioned x0.88.
- Variant E `good_state_combo_plus`: layered combination. Stabilizer (B) + strong-neutral floor 0.97 with transition-aware lift to 0.98 (A + C) + mix-rotation tilt (D).

Variant F (explicit beta overlay) was intentionally not re-tested; it was already shown to be benchmark-like in the prior round.

## B. Executed

1. Added transition-probability features to `build_market_state_history`: `transition_persistence_prob`, `transition_good_state_prob`, `transition_non_stress_prob`. All use causal trailing 156-week rolling means with `shift(1)` so each week sees only transitions that completed strictly before it.
2. Added `market_state_stable` column with one-sided hysteresis on entry into stressed_panic.
3. Added 5 overlay variants in `build_variant_regime_states`: `good_state_fragile_transition_aware`, `good_state_fragile_stabilizer`, `good_state_strong_offense`, `good_state_mix_rotation`, `good_state_combo_plus`. Added a neutral-base override map so Variants C and E raise the neutral floor 0.80 -> 0.83.
4. Added sleeve-tilt mode `fragile_plus_mix_rotation` in `apply_state_conditioned_tilt`.
5. Added `stabilize_market_state: bool` parameter to `run_subset_custom`. When True, the runner swaps `market_state_stable` into `market_state` in the market_state_history copy it uses, so both the overlay builder and the tilt layer see the stabilized state. Exits are not delayed because the stabilizer rule is one-sided.
6. Added 5 version_specs for Variants A-E.
7. Reran `scripts/build_improvement_artifacts.py` end-to-end (all 27 versions).
8. Reran `scripts/build-dashboard-data.mjs` to regenerate the homepage JSON.

## C. Files changed or written

- `scripts/build_improvement_artifacts.py`
  - `build_market_state_history`: added transition-matrix features + `market_state_stable`.
  - `build_variant_regime_states`: joins the new columns + 5 new overlay variants + neutral-base override map.
  - `apply_state_conditioned_tilt`: added `fragile_plus_mix_rotation` tilt mode.
  - `run_subset_custom`: `stabilize_market_state` parameter and effective-market-state-history swap.
  - `version_specs`: appended Variants A-E entries + stabilize_market_state flag.
- `data/04_layer2b_risk_regime_engine/market_state_history.csv` (adds `market_state_stable`, `transition_persistence_prob`, `transition_good_state_prob`, `transition_non_stress_prob`).
- `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv` (5 new variant rows).
- All per-version artifacts: returns, weights, sleeve_weights, regime_split, subperiod, upside_capture.
- `public/dashboard-data.json` regenerated.

## D. Results

### Core metrics

| Version | ann_return | ann_vol | sharpe | max_DD | calmar | CVaR_5 | turnover |
|---|---|---|---|---|---|---|---|
| CONTROL (good_state_fragile_combo) | 6.80% | 7.77% | 0.8753 | -14.28% | 0.476 | -2.61% | 5.61% |
| Variant A (transition_aware) | 6.85% | 7.82% | 0.8762 | -14.28% | 0.480 | -2.64% | 5.64% |
| Variant B (stabilizer) | 6.80% | 7.77% | 0.8753 | -14.28% | 0.476 | -2.61% | 5.61% |
| Variant C (strong_offense) | 6.94% | 7.91% | 0.8782 | -14.64% | 0.474 | -2.66% | 5.67% |
| Variant D (mix_rotation) | 6.82% | 7.80% | 0.8748 | -14.65% | 0.466 | -2.62% | 5.60% |
| Variant E (combo_plus) | 6.97% | 7.94% | 0.8775 | -15.01% | 0.464 | -2.67% | 5.66% |

### Allocations + captures

| Version | avg_BIL | avg_SPY | avg_cash | upside_cap+ | downside_cap- | recovery_cap | calm_week_cap | stress_dn_cap |
|---|---|---|---|---|---|---|---|---|
| CONTROL | 28.98% | 7.03% | 17.06% | 32.15% | 23.80% | 30.41% | 42.46% | 30.42% |
| Variant A | 28.39% | 7.10% | 16.36% | 32.40% | 23.98% | 30.72% | 42.50% | 30.52% |
| Variant B | 28.98% | 7.03% | 17.06% | 32.15% | 23.80% | 30.41% | 42.46% | 30.42% |
| Variant C | 27.76% | 7.16% | 15.62% | 32.72% | 24.14% | 31.21% | 42.54% | 30.44% |
| Variant D | 28.82% | 7.14% | 17.06% | 32.32% | 23.96% | 30.65% | 42.59% | 30.38% |
| Variant E | 27.59% | 7.27% | 15.62% | 32.89% | 24.30% | 31.44% | 42.67% | 30.40% |

### Production score (rank-based, 22 pts Sharpe / 16 pts Calmar / 14 pts DD / 10 pts CVaR / 12 pts upside / 10 pts recovery / 8 pts cash / 8 pts turnover)

| Version | production_score | delta vs control |
|---|---|---|
| CONTROL | 0.7152 | - |
| Variant A | 0.6993 | -0.0159 |
| Variant B | 0.7152 | 0.0000 |
| Variant C | 0.6859 | -0.0293 |
| Variant D | 0.6059 | -0.1093 |
| Variant E | 0.6037 | -0.1115 |

No variant clears the 0.05 promotion margin against the incumbent.

### Transition matrix (full-sample observed, row=curr, col=next)

| curr \ next | calm_trend | neutral_mixed | recovery_confirmed | recovery_fragile | stressed_panic |
|---|---|---|---|---|---|
| calm_trend | 0.858 | 0.136 | 0.007 | 0.000 | 0.000 |
| neutral_mixed | 0.079 | 0.807 | 0.024 | 0.032 | 0.057 |
| recovery_confirmed | 0.070 | 0.326 | 0.581 | 0.023 | 0.000 |
| recovery_fragile | 0.000 | 0.327 | 0.082 | 0.531 | 0.061 |
| stressed_panic | 0.000 | 0.105 | 0.004 | 0.026 | 0.865 |

Row counts: calm 295, neutral 493, conf 43, fragile 49, stressed 229. Good states are structurally sticky; neutral_mixed is also sticky (81%) and rarely steps straight to stress (5.7%).

## E. Diagnostic interpretation

1. Variant A (transition-aware): the trailing-window engine showed that for every strong-neutral week in the 20-year sample, P(non-stress next) was >= 0.92 (25th percentile 0.930, mean 0.949, 75th 0.962). The boost therefore fires on all 293 strong-neutral weeks in-sample, which is consistent with the fact that strong-neutral is structurally benign-continuing. The feature is interpretable and observable, but in this sample it reduces to "raise strong-neutral floor 0.94 -> 0.97 unconditionally." Variant A's metrics are net positive but the delta is small because most of the potential gain from a higher strong-neutral floor is already captured by the control's 0.94 floor. The ornament risk is real: unless a future regime shows strong-neutral weeks with P(non-stress next) < 0.92, the transition engine does not discriminate. It would become decision-useful in a stressed re-sampled regime.
2. Variant B (stabilizer): of 31 observed first-week entries into stressed_panic, 23 were "severe" at entry (DD <= -10% or risk_regime_score > 0.85) and 8 were mild. Only those 8 get delayed by one week, so stabilization touches 0.72% of all weeks. The metrics are literally identical to control to 4 decimal places. The stabilizer is correctly one-sided and semantically clean, but the effect size is too small to matter at this sample size. Loosening the severity bar would delay more entries but risks delaying real stress and violates the "preserve de-risking response to real stress" rule from the top-level spec.
3. Variant C (strong offense): cuts BIL by 122 bps and cash by 144 bps. Lifts upside capture 57 bps and recovery capture 79 bps. Sharpe is also better (+0.0028), but DD worsens 36 bps and Calmar falls slightly. This is a controlled, interpretable return-for-DD trade, not a Pareto improvement; it fails the "avoid carelessly worsening drawdown" rule.
4. Variant D (mix rotation): rotating away from composite_regime_conditioned and toward the trend trio improves sleeve-by-state Sharpe on paper but hurts at the portfolio level. The defensive sleeve contributes more to covariance-based risk parity than its standalone Sharpe suggests; removing it concentrates equity and trend risk, which widens DD (+37 bps) and shrinks Calmar (-0.010). The sleeve-by-state Sharpe signal is not portfolio-level causal.
5. Variant E (combo_plus): stacks C + D's overlay and tilt changes plus A's transition boost and B's stabilizer. The return gain (+17 bps) is the biggest in the study but so is the DD worsening (-73 bps). Same caveat as C but amplified. Stabilizer contributed 0 bps, mix-rotation tilt contributed negatively via DD, strong-offense floors contributed most of the return lift.

## F. Classification per variant

- Variant A (transition-aware): Conditional. Net positive on every return-side metric (ann_return +6 bps, Sharpe +0.0009, Calmar +0.004, upside cap +25 bps, recovery cap +30 bps) with max DD exactly unchanged. The transition-matrix engine itself is the main research artifact but does not discriminate in-sample at the current threshold. Does not clear the 0.05 production-score margin so the incumbent stays. Keep as a demoted but live feature.
- Variant B (stabilizer): Research-only. Metrics identical to control in 4 decimal places because only 8 of 1110 weeks change state. Keep the `market_state_stable` column since it is cheap to compute and offers a clean audit trail for future regime engineering.
- Variant C (strong offense): Conditional. Lifts return and Sharpe but costs 36 bps of DD and drops Calmar. Only acceptable if the DD tolerance is raised explicitly.
- Variant D (mix rotation): Drop. No meaningful return gain, Sharpe down marginally, DD worse, Calmar worse by 1 percentage point, production score -0.11.
- Variant E (combo_plus): Conditional. Biggest return gain but biggest DD worsening. Same structural issue as C plus the mix-rotation drag.

## G. Final recommendation

Keep the incumbent `improved_hrp_good_state_fragile_combo` as the production candidate. It remains pinned as the dashboard's improvedVersion. No variant clears the 0.05 promotion margin and only Variant A is Pareto-consistent with the DD rule.

Leave the transition-matrix features, `market_state_stable`, and the new overlay variants in the pipeline so they are available for future regime work, but classify the current research as:

- Variant A: Conditional (demoted, infrastructure retained).
- Variant B: Research-only (infrastructure retained; effect size too small at current rules).
- Variant C: Conditional (DD-tolerant branch only).
- Variant D: Drop.
- Variant E: Conditional (DD-tolerant branch only; dominated by C for return-for-DD efficiency since mix-rotation adds drag).

Next logical research follow-up, if a future round resumes: (i) probe whether the transition engine becomes discriminative when the trailing window shrinks from 156w to 52w (more regime sensitivity), (ii) test whether mix-rotation works only when gated by P(next state stays in calm_trend) >= some threshold (i.e., mix-rotation conditioned on transition persistence), and (iii) profile which historical windows account for Variant C's DD hit, to judge whether it is one drawdown episode or structural.
