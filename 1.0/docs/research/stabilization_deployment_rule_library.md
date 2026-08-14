# Stabilization Deployment Rule Library

Research-only rule library for future deployment tests.

## Contract

- Rules return bounded modifier series; they do not write weights or production files.
- Rules use C3 one-week-lagged confidence inputs by default.
- Parameters are conservative and explicit.
- Each rule declares an intended checkpoint so future tests avoid ad hoc injection.

## Rules

| rule | intended_checkpoint | bounded | lagged_inputs | description |
| --- | --- | --- | --- | --- |
| offense_eligibility | offense_budget | True | C3 one-week lagged scores | Small offense suppression when lagged eligibility is weak. |
| breadth_confirmation | regime_multipliers | True | C3 one-week lagged scores | Small risky-budget adjustment from ETF breadth confirmation. |
| sector_breadth_confirmation | regime_multipliers | True | C3 one-week lagged scores | Small risky-budget adjustment from sector breadth confirmation. |
| risk_on_participation | offense_budget | True | C3 one-week lagged scores | Offense trim when risk-on participation is weak. |
| dollar_pressure | offense_budget | True | C3 one-week lagged scores | Offense trim when dollar pressure is high. |
| macro_stress | regime_multipliers | True | C3 one-week lagged scores | Risk trim when macro/VIX/credit stress is active. |
| deterioration_acceleration | derisk_smoothing | True | C3 one-week lagged scores | Faster de-risking when deterioration is high. |
| transition_quality_rerisk | transition_rerisk_smoothing | True | C3 one-week lagged scores | Tiny re-risk boost only during high-quality transitions. |
| confidence_score_modifier | volatility_risk_overlay | True | C3 one-week lagged scores | Combined confidence modifier at overlay-aware checkpoint. |
| final_safety_clamp | final_etf_lookthrough_weights | True | C3 one-week lagged scores | Final no-increase safety clamp for comparison. |
| combined_conservative | volatility_risk_overlay | True | C3 one-week lagged scores | Conservative multi-input confidence deployment rule. |

## Usage Guidance

- Use `offense_budget` for eligibility, dollar pressure, and risk-on participation.
- Use `regime_multipliers` or `volatility_risk_overlay` for broad confidence/risk-budget changes.
- Use `transition_rerisk_smoothing` and `derisk_smoothing` for asymmetric timing research.
- Treat `final_etf_lookthrough_weights` as a comparison layer, not the preferred architecture.
