# C7 Native Confidence Sprint Summary

## Answers

1. Did allocator-native insertion beat exact GGG? No strict C5 Sharpe beat from the best observed variant.
2. Which insertion point worked best? `derisk_timing_offset` via `c4_deterioration_aware_derisk_timing`.
3. Did transition-aware re-risking help? See the C4/C6 tables; it is useful only if it ranks near the top without stressing holdout or stressed_panic.
4. Did deterioration-aware de-risking help? See the C4/C6 tables; it is judged by stress preservation and drawdown/CVaR behavior, not standalone IC.
5. Did confidence modifiers preserve stressed_panic defense? Yes for the best variant under the configured tolerance.
6. Did any improvement survive sensitivity testing? See C6 summary; stable variants should have tight Sharpe range and preserved holdout/stress rows.
7. Is this better than B7/B8 post-hoc pass-through? This test uses exact GGG alignment and one-way turnover, so it is the correct comparison layer.
8. Is R5 still premature? Yes until the insertion point is verified with a no-write allocator wrapper rather than saved-weight proxy modifications.
9. Exact next sprint: Run a no-write allocator wrapper that inserts the best confidence modifier before final ETF look-through, then compare against this saved-weight proxy.
10. Production/dashboard files changed: no changes were written by these scripts.

## Best Rows

| variant | ann_return | sharpe | max_drawdown | cvar_5 | avg_turnover | stressed_panic_sharpe | acceptance_verdict | acceptance_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| c4_deterioration_aware_derisk_timing | 0.0707 | 0.9410 | -0.1160 | -0.0250 | 0.0648 | 0.4805 | research-only | no accepted risk-adjusted improvement |
| c4_final_bounded_safety_check | 0.0718 | 0.9405 | -0.1166 | -0.0254 | 0.0631 | 0.4779 | promising | Accepted by C5 gate. |
| c4_regime_multiplier_confidence_offset | 0.0716 | 0.9390 | -0.1174 | -0.0254 | 0.0635 | 0.4730 | promising | Accepted by C5 gate. |
| c4_combined_conservative_confidence_modifier | 0.0714 | 0.9375 | -0.1158 | -0.0254 | 0.0632 | 0.4788 | promising | Accepted by C5 gate. |
| c4_transition_aware_rerisk_timing | 0.0714 | 0.9371 | -0.1177 | -0.0254 | 0.0623 | 0.4816 | promising | Accepted by C5 gate. |
| exact_ggg | 0.0714 | 0.9366 | -0.1177 | -0.0254 | 0.0618 | 0.4817 | benchmark | Benchmark row. |
| c4_offensive_sleeve_budget_offset | 0.0715 | 0.9356 | -0.1180 | -0.0255 | 0.0628 | 0.4758 | promising | Accepted by C5 gate. |
| phase2b_pinned | 0.0689 | 0.8848 | -0.1398 | -0.0262 | 0.0562 | 0.4978 | benchmark | Benchmark row. |

## Sensitivity

| variant | scenarios | sharpe_median | sharpe_min | sharpe_max | holdout_2020_sharpe_min | stressed_panic_sharpe_min |
| --- | --- | --- | --- | --- | --- | --- |
| c4_combined_conservative_confidence_modifier | 8 | 0.9375 | 0.9368 | 0.9388 | 1.0853 | 0.4787 |
| c4_final_bounded_safety_check | 8 | 0.9405 | 0.9393 | 0.9405 | 1.0834 | 0.4779 |
| c4_regime_multiplier_confidence_offset | 8 | 0.9389 | 0.9370 | 0.9399 | 1.0803 | 0.4728 |

## Warnings

- None.
