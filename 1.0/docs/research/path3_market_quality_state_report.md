# Path 3 Market Quality State Report

Research-only interpretable confidence-state model. Scores are blended from existing tradable/lagged breadth, macro, dollar, and signal-quality signals; no return optimization was used.

## State Summary

| market_quality_state | n_weeks | avg_offense_confidence | avg_deterioration | avg_transition_quality | avg_future_4w_ggg_return | avg_future_4w_ggg_drawdown |
| --- | --- | --- | --- | --- | --- | --- |
| high_confidence_offense | 330 | 0.8260 | 0.3298 | 0.8010 | 0.0075 | -0.0097 |
| constructive_transition | 258 | 0.6812 | 0.4274 | 0.7664 | 0.0044 | -0.0110 |
| neutral_quality | 169 | 0.5083 | 0.5147 | 0.6296 | 0.0050 | -0.0046 |
| fragile_or_choppy | 291 | 0.4166 | 0.5957 | 0.4519 | 0.0040 | -0.0082 |
| defensive_deteriorating | 62 | 0.3231 | 0.7587 | 0.3090 | 0.0073 | -0.0069 |

## Market State Cross-Tab

| market_state | market_quality_state | n_weeks |
| --- | --- | --- |
| calm_trend | high_confidence_offense | 167 |
| calm_trend | constructive_transition | 84 |
| calm_trend | neutral_quality | 27 |
| calm_trend | fragile_or_choppy | 17 |
| neutral_mixed | high_confidence_offense | 129 |
| neutral_mixed | constructive_transition | 128 |
| neutral_mixed | fragile_or_choppy | 116 |
| neutral_mixed | neutral_quality | 103 |
| neutral_mixed | defensive_deteriorating | 17 |
| recovery_confirmed | constructive_transition | 25 |
| recovery_confirmed | high_confidence_offense | 17 |
| recovery_confirmed | fragile_or_choppy | 2 |
| recovery_fragile | constructive_transition | 21 |
| recovery_fragile | high_confidence_offense | 12 |
| recovery_fragile | fragile_or_choppy | 8 |
| recovery_fragile | neutral_quality | 8 |
| stressed_panic | fragile_or_choppy | 148 |
| stressed_panic | defensive_deteriorating | 45 |
| stressed_panic | neutral_quality | 31 |
| stressed_panic | high_confidence_offense | 5 |

## Interpretation

- The model is intended as environment estimation, not alpha.
- The key research question is whether breadth/macro/dollar information should control offense confidence and transition timing rather than directly scaling final ETF weights.
- Use later scripts to test transition quality, offense eligibility, and a very light sandbox.

## Warnings

- None.
