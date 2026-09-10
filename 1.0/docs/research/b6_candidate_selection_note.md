# B6 Candidate Selection Note

Research-only continuation of the Breadth + State-Gated Macro Intelligence Sprint. This note selects a narrow candidate set for stricter validation before any controlled portfolio pass-through or R5 ensemble work.

## Inputs Reviewed

- `docs/research/breadth_macro_sprint_summary.md`
- `data/02_layer1_signals/breadth_signal_summary.csv`
- `data/02_layer1_signals/state_gated_macro_results.csv`
- `data/02_layer1_signals/signal_quality_feature_validation.csv`
- `data/02_layer1_signals/dollar_strength_deep_dive.csv`
- `data/02_layer1_signals/r2_signal_validation_results.csv`
- `data/02_layer1_signals/signal_state_conditional_ic.csv`

## Selected Breadth Candidates

- `bm_etf_above_50d_ma`
- `bm_etf_above_200d_ma`
- `bm_etf_positive_13w_mom`
- `bm_etf_positive_26w_mom`
- `bm_risk_on_participation`
- `bm_sector_above_50d_ma`
- `bm_sector_above_200d_ma`
- `bm_sector_positive_13w_mom`
- `bm_sector_positive_26w_mom`

These were selected because they showed positive full and holdout IC, useful calm_trend behavior, and no obvious stressed_panic damage in B1-B5.

## Selected Gated Macro Candidates

- `r2_credit_spread__calm_trend_only`
- `r2_vix_term_structure__calm_trend_only`
- `r2_vix_term_structure__no_stressed_panic`
- `r2_credit_spread__vix_below_past_median`
- `r2_financial_conditions__recovery_only`
- `r2_commodity_regime__recovery_only`

These were selected because simple state/VIX gates appeared to preserve useful macro information while reducing or avoiding the stressed_panic damage observed in unconditional R2 macro/VIX/credit signals.

## Selected Dollar Strength Candidates

- `bm_dollar_strength_4w`
- `bm_dollar_strength_blended`
- `bm_dollar_strength_13w`

These were selected because they retained positive full/holdout IC and avoided obvious stressed_panic damage. The 8-week variant was not selected because holdout IC was near zero, and 26-week was rejected in B4.

## Selected Signal-Quality / Meta Candidates

- `bm_quality_breadth_confirmation`
- `bm_quality_signal_agreement`
- `bm_quality_signal_dispersion`
- `bm_quality_risk_on_confirmation__no_stressed_panic`

`bm_quality_risk_on_confirmation` is included only as a stress-gated diagnostic because the ungated version damaged stressed_panic.

## Diagnostic-Only Breadth Decomposition Candidates

- `bm_quality_deterioration_warning`
- `bm_breadth_change_4w`
- `bm_breadth_momentum_13w`
- `bm_participation_acceleration`
- `bm_risk_on_minus_defensive_participation`
- `bm_offensive_vs_defensive_sector_breadth`

These are not selected as pass-through candidates. They are included in B6.3 to separate participation confirmation, deterioration warning, risk-on expansion, defensive rotation, and whipsaw/chop diagnostics. Both natural and inverted signs may be tested, but only as labeled diagnostics to avoid cherry-picking.

## Research-Only Guardrails

- No production pins, dashboard/public files, portfolio artifacts, allocation logic, R5 ensemble code, R6 meta-labeling integration, or live trading logic should be changed.
- Every candidate panel used in validation must use a one-week lagged tradable signal.
- Gated candidates must use lagged gates.
- Results are evidence for a later controlled portfolio pass-through test, not a promotion decision.
