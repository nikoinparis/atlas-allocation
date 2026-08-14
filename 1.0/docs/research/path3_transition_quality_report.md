# Path 3 Transition Quality Report

Research-only diagnostic of whether calm/recovery transitions are strong, fragile, broad, weak, or deteriorating.

## Transition Summary

| to_state | transition_quality_bucket | n_transitions | success_rate_4w | whipsaw_rate_4w | stress_rate_8w | avg_future_4w_ggg_return | avg_future_4w_drawdown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| calm_trend | deteriorating | 1 | 1.0000 | 0.0000 | 0.0000 | 0.0157 | -0.0019 |
| calm_trend | strong_broad | 31 | 0.4516 | 0.3548 | 0.0000 | 0.0031 | -0.0103 |
| calm_trend | constructive | 10 | 0.4000 | 0.2000 | 0.1000 | 0.0033 | -0.0095 |
| recovery_confirmed | strong_broad | 17 | 0.2941 | 0.5294 | 0.0000 | 0.0091 | -0.0091 |
| recovery_confirmed | constructive | 1 | 0.0000 | 1.0000 | 0.0000 | -0.0001 | -0.0160 |
| recovery_confirmed | deteriorating | 1 | 0.0000 | 0.0000 |  |  |  |
| recovery_fragile | strong_broad | 11 | 0.2727 | 0.6364 | 0.0000 | -0.0012 | -0.0110 |
| recovery_fragile | constructive | 10 | 0.2000 | 0.7000 | 0.3000 | 0.0052 | -0.0087 |
| recovery_fragile | deteriorating | 2 | 0.0000 | 0.0000 | 0.5000 | -0.0002 | -0.0115 |

## Recent / Largest Weak Transitions

| Date | from_state | to_state | transition_quality_bucket | future_4w_ggg_return | whipsaw_4w | stress_within_8w | deterioration_score |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2013-05-17 00:00:00 | neutral_mixed | calm_trend | strong_broad | -0.0427 | 1.0000 | 0.0000 | 0.4708 |
| 2021-02-12 00:00:00 | neutral_mixed | calm_trend | strong_broad | -0.0232 | 1.0000 | 0.0000 | 0.3401 |
| 2024-12-13 00:00:00 | neutral_mixed | calm_trend | strong_broad | -0.0221 | 1.0000 | 0.0000 | 0.4094 |
| 2015-01-30 00:00:00 | stressed_panic | recovery_fragile | constructive | -0.0189 | 1.0000 | 1.0000 | 0.6465 |
| 2015-02-13 00:00:00 | stressed_panic | recovery_fragile | constructive | -0.0158 | 1.0000 | 0.0000 | 0.5820 |
| 2010-10-29 00:00:00 | neutral_mixed | calm_trend | strong_broad | -0.0153 | 1.0000 | 0.0000 | 0.2402 |
| 2006-12-08 00:00:00 | calm_trend | recovery_confirmed | strong_broad | -0.0149 | 1.0000 | 0.0000 | 0.2885 |
| 2008-05-16 00:00:00 | neutral_mixed | recovery_fragile | strong_broad | -0.0144 | 1.0000 | 0.0000 | 0.4538 |
| 2012-02-24 00:00:00 | recovery_fragile | recovery_confirmed | strong_broad | -0.0123 | 1.0000 | 0.0000 | 0.2609 |
| 2011-04-22 00:00:00 | neutral_mixed | calm_trend | strong_broad | -0.0103 | 1.0000 | 0.0000 | 0.2939 |
| 2012-03-09 00:00:00 | neutral_mixed | recovery_confirmed | strong_broad | -0.0086 | 1.0000 | 0.0000 | 0.3417 |
| 2006-09-01 00:00:00 | neutral_mixed | recovery_fragile | constructive | -0.0082 | 1.0000 | 0.0000 | 0.4481 |

## Deterioration Lead-Time Before Stressed Panic

| stress_entry_date | max_prior_8w_deterioration | weeks_with_prior_deterioration | first_warning_lead_weeks |
| --- | --- | --- | --- |
| 2006-05-26 00:00:00 | 0.5502 | 0 |  |
| 2006-06-23 00:00:00 | 0.5815 | 0 |  |
| 2006-07-21 00:00:00 | 0.5846 | 0 |  |
| 2007-08-03 00:00:00 | 0.5030 | 0 |  |
| 2007-10-12 00:00:00 | 0.6769 | 1 | 7.0000 |
| 2008-01-04 00:00:00 | 0.5619 | 0 |  |
| 2008-07-11 00:00:00 | 0.7446 | 3 | 3.0000 |
| 2008-09-05 00:00:00 | 0.7216 | 3 | 8.0000 |
| 2009-05-15 00:00:00 | 0.6867 | 1 | 8.0000 |
| 2011-08-12 00:00:00 | 0.6568 | 1 | 6.0000 |
| 2011-09-23 00:00:00 | 0.7321 | 5 | 6.0000 |
| 2011-11-25 00:00:00 | 0.7553 | 3 | 8.0000 |

## Interpretation

- Transition-quality modeling is promising if strong/broad transitions have higher success and lower whipsaw than weak/choppy or deteriorating transitions.
- These are diagnostics only; they do not optimize allocations or promote a rule.

## Warnings

- None.
