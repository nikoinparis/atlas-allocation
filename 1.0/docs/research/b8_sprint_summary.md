# B8 Sprint Summary

Research-only bounded deployment refinement sprint. No production/dashboard/allocation/R5/R6/live-trading files were changed.

## Final Answers

1. B7 failed because it cut offense too broadly, increased cash, weakened return capture, and did not add enough stressed_panic benefit to offset lost return. It also exposed a post-hoc reconstruction gap versus saved GGG returns.
2. Did B8 fix the failure mode? No; variants were gentler, but still did not clear the dashboard GGG benchmark.
3. Did any variant beat or nearly match GGG? Beat: False; nearly match within 0.01 Sharpe: False.
4. Did any variant improve drawdown/CVaR meaningfully? Best drawdown/CVaR changes are in `b8_market_quality_composite_mild`, but acceptance depends on the full table.
5. State behavior improved only marginally; stressed_panic preservation is measured against recomputed GGG because dashboard state returns are saved separately.
6. Breadth remains useful as a diagnostic/gate, not as direct alpha pass-through.
7. Stop broad pass-through for now unless a very narrow production-plumbing replication issue is resolved.
8. Do not proceed to R5 ensemble yet from these pass-through results.
9. Prefer PIT breadth / better data and/or exact allocator-native plumbing replication before more signal ensembles.
10. Production/dashboard files were not intentionally changed; final diff command confirms status.

## Best Variant

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | delta_sharpe_vs_ggg_dashboard | delta_sharpe_vs_phase2b | b8_verdict | b8_verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| b8_market_quality_composite_mild | market_quality_composite | 0.0577 | 0.7686 | -0.1252 | -0.0257 | -0.1680 | -0.1162 | research-only | Sharpe below GGG by more than 0.01; max drawdown worse than GGG by more than 0.5pp |

## Top Variants

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | b8_verdict |
| --- | --- | --- | --- | --- | --- | --- |
| b8_market_quality_composite_mild | market_quality_composite | 0.0577 | 0.7686 | -0.1252 | -0.0257 | research-only |
| b8_recovery_safe_sector_gate | recovery_safe_gate | 0.0586 | 0.7683 | -0.1282 | -0.0262 | research-only |
| b8_market_quality_composite_medium | market_quality_composite | 0.0574 | 0.7681 | -0.1245 | -0.0255 | research-only |
| b8_soft_etf_breadth_95_103 | soft_scaler | 0.0588 | 0.7665 | -0.1287 | -0.0263 | research-only |
| b8_sector_soft_95_103 | sector_breadth_only | 0.0589 | 0.7662 | -0.1288 | -0.0264 | research-only |
| b8_calm_neutral_confirmation | calm_only_confirmation | 0.0583 | 0.7659 | -0.1282 | -0.0261 | research-only |
| b8_asymmetric_breadth_gate | asymmetric_breadth_gate | 0.0584 | 0.7653 | -0.1282 | -0.0262 | research-only |
| b8_soft_etf_breadth_90_105 | soft_scaler | 0.0588 | 0.7651 | -0.1291 | -0.0264 | research-only |
| b8_sector_soft_90_105 | sector_breadth_only | 0.0590 | 0.7646 | -0.1291 | -0.0264 | research-only |

## Recommendation

Do not promote or ensemble these pass-through variants. Next sprint should either reproduce GGG's saved return plumbing exactly before further post-hoc tests, or move to better PIT breadth data rather than forcing weak deployment transforms.

## Warnings

- None.
