# B6 Breadth Decomposition Report

Research-only decomposition of breadth into participation confirmation, deterioration warning, risk-on expansion, defensive rotation, and whipsaw/chop diagnostics. Inverted signs are diagnostic only and are not optimization choices.

- Output CSV: `data/02_layer1_signals/b6_breadth_decomposition.csv`
- Rows tested: 17

## Suggested Uses

| signal_name | breadth_component | sign_variant | suggested_use | avg_full_ic | 2020_plus_avg_ic | 2022_bear_rate_shock_avg_ic | calm_trend_avg_ic | stressed_panic_avg_ic | max_abs_redundancy_existing | suggested_use_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm_etf_above_50d_ma | participation_confirmation | natural | alpha_signal | 0.1182 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2121 | Positive holdout and acceptable stress behavior. |
| bm_etf_above_200d_ma | participation_confirmation | natural | alpha_signal | 0.1207 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2794 | Positive holdout and acceptable stress behavior. |
| bm_etf_positive_13w_mom | participation_confirmation | natural | alpha_signal | 0.1213 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2542 | Positive holdout and acceptable stress behavior. |
| bm_etf_positive_26w_mom | participation_confirmation | natural | alpha_signal | 0.1196 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.2851 | Positive holdout and acceptable stress behavior. |
| bm_quality_deterioration_warning__inverted_diagnostic | deterioration_warning | inverted_diagnostic | alpha_signal | 0.1181 | 0.1258 | -0.0297 | 0.1233 | 0.0834 | 0.1936 | Positive holdout and acceptable stress behavior. |
| bm_risk_on_participation | risk_on_expansion | natural | alpha_signal | 0.1209 | 0.1201 | -0.0979 | 0.1260 | 0.0438 | 0.2767 | Positive holdout and acceptable stress behavior. |
| bm_breadth_momentum_13w__inverted_diagnostic | breadth_thrust | inverted_diagnostic | alpha_signal | -0.0066 | 0.0470 | 0.1170 | -0.0262 | 0.0842 | 0.0632 | Positive holdout and acceptable stress behavior. |
| bm_breadth_change_4w__inverted_diagnostic | breadth_thrust | inverted_diagnostic | research_only_diagnostic | -0.0233 | 0.0092 | 0.0316 | -0.0179 | -0.0146 | 0.0819 | Holdout instability prevents pass-through use. |
| bm_offensive_vs_defensive_sector_breadth | risk_on_expansion_vs_defensive_rotation | natural | research_only_diagnostic | -0.0166 | 0.0070 | 0.0928 | -0.0076 | 0.0278 | 0.0564 | Holdout instability prevents pass-through use. |
| bm_participation_acceleration | whipsaw_chop_warning | natural | research_only_diagnostic | -0.0155 | 0.0042 | -0.0086 | -0.0035 | 0.0355 | 0.0345 | Holdout instability prevents pass-through use. |
| bm_participation_acceleration__inverted_diagnostic | whipsaw_chop_warning | inverted_diagnostic | research_only_diagnostic | 0.0155 | -0.0042 | 0.0086 | 0.0035 | -0.0355 | 0.0345 | Holdout instability prevents pass-through use. |
| bm_offensive_vs_defensive_sector_breadth__inverted_diagnostic | risk_on_expansion_vs_defensive_rotation | inverted_diagnostic | research_only_diagnostic | 0.0166 | -0.0070 | -0.0928 | 0.0076 | -0.0278 | 0.0564 | Holdout instability prevents pass-through use. |
| bm_breadth_change_4w | breadth_thrust | natural | research_only_diagnostic | 0.0233 | -0.0092 | -0.0316 | 0.0179 | 0.0146 | 0.0819 | Holdout instability prevents pass-through use. |
| bm_risk_on_minus_defensive_participation__inverted_diagnostic | risk_on_expansion_vs_defensive_rotation | inverted_diagnostic | research_only_diagnostic | -0.0081 | -0.0254 | 0.0417 | -0.0506 | 0.0407 | 0.1852 | Negative full and holdout IC; not a standalone alpha. |
| bm_risk_on_minus_defensive_participation | risk_on_expansion_vs_defensive_rotation | natural | risk_filter_or_invert_diagnostic | 0.0081 | 0.0254 | -0.0417 | 0.0506 | -0.0407 | 0.1852 | Natural sign is dangerous in stressed_panic; inverted version should be inspected only as diagnostic. |
| bm_breadth_momentum_13w | breadth_thrust | natural | risk_filter_or_invert_diagnostic | 0.0066 | -0.0470 | -0.1170 | 0.0262 | -0.0842 | 0.0632 | Natural sign is dangerous in stressed_panic; inverted version should be inspected only as diagnostic. |
| bm_quality_deterioration_warning | deterioration_warning | natural | risk_filter_or_invert_diagnostic | -0.1181 | -0.1258 | 0.0297 | -0.1233 | -0.0834 | 0.1936 | Natural sign is dangerous in stressed_panic; inverted version should be inspected only as diagnostic. |

## Diagnostic Sign Review

- Participation confirmation breadth remains the cleanest breadth family.
- Risk-on minus defensive breadth is informative, but the natural sign can behave poorly in stressed_panic and should be treated as a gate/filter candidate.
- Deterioration warning signs remain diagnostic. Inverted signs are inspected only to understand orientation; they are not promoted.
- Breadth thrust and acceleration are less stable than level/participation breadth.

## Warnings

- None.
