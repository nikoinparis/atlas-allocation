# B8 B7 Failure Diagnosis

Research-only diagnosis of why B7 bounded pass-through failed to beat GGG.

## Answers

1. B7 did reduce offense too often. Most variants raised average BIL/cash and reduced average offense versus GGG weights.
2. B7 did reduce offense in calm_trend for gate variants because the gates were symmetric and did not protect calm_trend unless breadth was strong.
3. B7 did not materially improve stressed_panic enough to compensate for lower return elsewhere. Macro filters improved drawdown/CVaR slightly but gave up too much return.
4. B7 added turnover/cost drag in several variants. Turnover stayed near the GGG dashboard range but was higher than recomputed baseline in the transformed paths.
5. B7 changed cash/BIL exposure too much: variants generally shifted cash higher and offense lower.
6. Neutral_mixed was weak; breadth gates did not unlock enough neutral participation and sometimes suppressed it.
7. The B7 gate was too symmetric and too strict. It treated weak breadth as a broad offense cut instead of an asymmetric, state-aware confidence modifier.

## Reconstruction Gap

- Recomputed GGG from saved ETF weights has Sharpe 0.7683, lower than dashboard GGG Sharpe 0.9366.
- B8 therefore reports deltas versus both dashboard GGG and recomputed GGG. The dashboard comparison remains the acceptance benchmark, but recomputed deltas identify deployment effects separately from reconstruction noise.

## B7 Top Rows

| variant | family | full_ann_return | full_sharpe | full_max_drawdown | full_cvar_5 | full_avg_BIL | full_avg_offense | b7_verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| b7_sector_breadth_gate | sector_breadth_gate | 0.0585 | 0.7742 | -0.1212 | -0.0259 | 0.2725 | 0.4104 | Sharpe worsened vs GGG |
| b7_combined_conservative_gate | combined | 0.0572 | 0.7713 | -0.1152 | -0.0255 | 0.2844 | 0.4002 | Sharpe worsened vs GGG |
| b7_dollar_pressure_blended_mild | dollar_filter | 0.0587 | 0.7712 | -0.1270 | -0.0261 | 0.2696 | 0.4144 | Sharpe worsened vs GGG; max drawdown worsened vs GGG |
| b7_dollar_pressure_4w_mild | dollar_filter | 0.0586 | 0.7695 | -0.1270 | -0.0261 | 0.2699 | 0.4139 | Sharpe worsened vs GGG; max drawdown worsened vs GGG |
| b7_macro_stress_filter_mild | macro_filter | 0.0570 | 0.7692 | -0.1173 | -0.0254 | 0.2857 | 0.3971 | Sharpe worsened vs GGG |
| b7_macro_stress_filter_medium | macro_filter | 0.0561 | 0.7683 | -0.1124 | -0.0251 | 0.2953 | 0.3875 | Sharpe worsened vs GGG |
| b7_breadth_gate_50d | breadth_gate | 0.0574 | 0.7669 | -0.1212 | -0.0258 | 0.2778 | 0.4050 | Sharpe worsened vs GGG |
| b7_breadth_scaler_composite | breadth_scaler | 0.0590 | 0.7658 | -0.1250 | -0.0265 | 0.2603 | 0.4247 | Sharpe worsened vs GGG; max drawdown worsened vs GGG; CVaR worsened vs GGG |
| b7_risk_on_participation_gate | risk_on_gate | 0.0577 | 0.7655 | -0.1212 | -0.0259 | 0.2746 | 0.4082 | Sharpe worsened vs GGG |
| b7_breadth_gate_13w | breadth_gate | 0.0575 | 0.7636 | -0.1212 | -0.0259 | 0.2757 | 0.4071 | Sharpe worsened vs GGG |
