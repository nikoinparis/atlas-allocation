# B7 Sprint Summary

Research-only controlled portfolio pass-through sandbox. Saved GGG weights were transformed post-hoc with bounded signal gates/filters. No production files were changed.

## Final Answers

1. Did breadth improve portfolio-level results? No clear improvement versus GGG.
2. Breadth worked better as an offense gate/filter than standalone alpha in B7.
3. Macro gates did not improve enough after pass-through.
4. Dollar strength did not beat GGG in this pass-through.
5. Any variant beat GGG on risk-adjusted metrics? False.
6. Any variant beat Phase2B? False.
7. Stressed_panic defense was checked in state summaries; preserve/reject decision is based on the state table and risk metrics.
8. Variant deserving deeper testing: `b7_sector_breadth_gate`.
9. Run another controlled pass-through/refinement before R5 unless a variant cleanly beats GGG while preserving stressed_panic defense.
10. Production/dashboard files were not intentionally changed; final diff command confirms status.

## Best Variant

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | delta_sharpe_vs_ggg_dashboard | delta_sharpe_vs_phase2b | b7_verdict | b7_verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| b7_sector_breadth_gate | sector_breadth_gate | 0.0585 | 0.7742 | -0.1212 | -0.0259 | -0.1624 | -0.1106 | research-only | Sharpe worsened vs GGG |

## Top Variants

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | b7_verdict |
| --- | --- | --- | --- | --- | --- | --- |
| b7_sector_breadth_gate | sector_breadth_gate | 0.0585 | 0.7742 | -0.1212 | -0.0259 | research-only |
| b7_combined_conservative_gate | combined | 0.0572 | 0.7713 | -0.1152 | -0.0255 | research-only |
| b7_dollar_pressure_blended_mild | dollar_filter | 0.0587 | 0.7712 | -0.1270 | -0.0261 | research-only |
| b7_dollar_pressure_4w_mild | dollar_filter | 0.0586 | 0.7695 | -0.1270 | -0.0261 | research-only |
| b7_macro_stress_filter_mild | macro_filter | 0.0570 | 0.7692 | -0.1173 | -0.0254 | research-only |
| b7_macro_stress_filter_medium | macro_filter | 0.0561 | 0.7683 | -0.1124 | -0.0251 | research-only |
| b7_breadth_gate_50d | breadth_gate | 0.0574 | 0.7669 | -0.1212 | -0.0258 | research-only |
| b7_breadth_scaler_composite | breadth_scaler | 0.0590 | 0.7658 | -0.1250 | -0.0265 | research-only |
| b7_risk_on_participation_gate | risk_on_gate | 0.0577 | 0.7655 | -0.1212 | -0.0259 | research-only |
| b7_breadth_gate_13w | breadth_gate | 0.0575 | 0.7636 | -0.1212 | -0.0259 | research-only |

## Next Sprint

B8: refine the best bounded pass-through family only, add stricter stressed_panic/state guardrails, and compare against saved GGG and Phase2B without changing production logic.

## Warnings

- Registry mismatch confirmed: Phase2B remains current production/rollback pin while GGG is pending dashboard production candidate. B7 compares against both.
