# Path 1 GGG Plumbing Audit

Research-only audit. No production pins, dashboard/public files, or Layer 3 production artifacts were changed.

## Production Candidate Path

- Registry current production pin: `improved_phase2b_regime_confidence_boost`
- Registry production candidate: `improved_phaseggg_confirmed_only_robust_offense`
- Dashboard candidate benchmark for this sprint: `improved_phaseggg_confirmed_only_robust_offense`
- Phase2B pinned comparator: `improved_phase2b_regime_confidence_boost`

## Exact GGG Sequence Reconstructed From Code/Artifacts

1. Load weekly ETF prices from `data/01_data_hub/weekly_prices.csv`.
2. Build forward returns as `weekly_prices.pct_change().shift(-1)`, indexed by the allocation decision date.
3. Build GGG sleeve panels from the Phase YY decomposed architecture.
4. For `composite_regime_offense_component`, use the broad offense basket except in `recovery_confirmed`, where GGG swaps to the robust FFF3 subset and drops `PDBC` and `DBA`.
5. Allocate sleeves with HRP over the `phaseyy_conservative_decomposition` subset.
6. Apply `phase_ddd_confirmed_near_exclude_dual` state tilt before overlay.
7. Apply Layer 3 expression mode `none`.
8. Apply overlay mode `phasexx_conservative_hybrid_overlay` plus Phase2B `regime_confidence_boost` before final look-through.
9. Apply target-vol interaction inside the overlay step, with risky budget constrained by `min(regime_multiplier, target_vol_multiplier)` unless recovery/neutral budget repair rules apply.
10. Convert sleeve weights to final ETF look-through weights, keeping residual cash in `BIL`.
11. Compute gross returns from final ETF weights and forward returns on the same decision-date index.
12. Compute one-way turnover as `0.5 * sum(abs(diff(final_etf_weights)))`; cost is turnover times 10 bps.

## Checkpoint Availability

| stage | exists | rows | cols | avg_cash_or_BIL | avg_total_weight | path |
| --- | --- | --- | --- | --- | --- | --- |
| raw_hrp_sleeve_weights | True | 1110 | 7 | 0.0694 | 1.0000 | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__raw_hrp_sleeve_weights.csv |
| post_state_tilt_sleeve_weights | True | 1110 | 7 | 0.0694 | 1.0000 | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_state_tilt_sleeve_weights.csv |
| post_layer3_expression_sleeve_weights | True | 1110 | 7 | 0.0694 | 1.0000 | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_layer3_expression_sleeve_weights.csv |
| post_overlay_pre_lookthrough_sleeve_weights | True | 1110 | 7 | 0.2254 | 1.0000 | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__post_overlay_pre_lookthrough_sleeve_weights.csv |
| final_sleeve_weights | True | 1110 | 7 | 0.2254 | 1.0000 | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__final_sleeve_weights.csv |
| final_etf_weights | True | 1110 | 35 | 0.2666 | 1.0000 | data/research/allocator_checkpoints/improved_phaseggg_confirmed_only_robust_offense__final_etf_weights.csv |

## B7/B8 Mismatch Sources Identified

- B7/B8 used `weekly_returns.csv` and a one-period weight shift. The exact GGG path uses `weekly_prices.pct_change().shift(-1)` on the allocation-date index.
- B7/B8 used full L1 turnover `sum(abs(diff(weights)))` for cost. The production path uses one-way turnover `0.5 * sum(abs(diff(weights)))`.
- Because the turnover convention differs, B7/B8 variant costs and turnover labels were not directly comparable to the saved GGG path.
- The mismatch is a plumbing issue, not proof that the breadth/macro signals are false.

## Hidden Nonlinearities And Sequencing Effects

- HRP sleeve allocation is estimated from a rolling training window and normalized through max-sleeve constraints.
- State tilt happens before overlay, so a small confidence signal can be amplified or neutralized by later overlay budget rules.
- Phase2B regime confidence modifies the overlay multiplier, not final ETF weights directly.
- Target-vol and regime overlays bind jointly; injecting a signal after this step can violate the intended order.
- `phasexx_conservative_hybrid_overlay` has state-specific recovery/neutral cash budget logic, which means symmetric final-weight scaling is the wrong deployment abstraction.

## What Was Reconstructed

| rebuild_name | rebuild_ann_return | rebuild_sharpe | net_return_corr_vs_saved | net_return_max_abs_error | turnover_max_abs_error | cost_max_abs_error |
| --- | --- | --- | --- | --- | --- | --- |
| exact_saved_final_etf_weights | 0.0714 | 0.9366 | 1.0000 | 0.0000 | 0.0000 | 0.0000 |
| correct_returns_full_turnover_cost | 0.0679 | 0.8915 | 0.9999 | 0.0008 | 0.8000 | 0.0008 |
| b7_b8_sandbox_plumbing | 0.0588 | 0.7683 | -0.1035 | 0.1252 | 0.8000 | 0.0008 |

- Exact saved-weight return-path reconstruction succeeded: `True`.

## Production Metrics Snapshot

| role | name | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | avg_BIL | avg_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| production_candidate_pending_human_review | improved_phaseggg_confirmed_only_robust_offense | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.2666 | 0.1236 |

| role | name | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | avg_BIL | avg_turnover |
| --- | --- | --- | --- | --- | --- | --- | --- |
| current_production_and_rollback | improved_phase2b_regime_confidence_boost | 0.0689 | 0.8848 | -0.1398 | -0.0262 | 0.2839 | 0.1124 |

## Warnings

- None.
