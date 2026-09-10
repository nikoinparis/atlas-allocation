# Path 3 Offense Eligibility Report

Research-only diagnostic of whether offense should be allowed, suppressed, or bounded based on market-quality states.

## Overall Rule Diagnostics

| rule_name | allowed_share | suppressed_share | future_4w_return_allowed | future_4w_return_suppressed | future_return_lift_allowed_minus_suppressed | whipsaw_rate_allowed | whipsaw_rate_suppressed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| strict_all_clear | 0.4486 | 0.5514 | 0.0069 | 0.0043 | 0.0027 | 0.2711 | 0.5911 |
| deterioration_suppression_only | 0.7559 | 0.2441 | 0.0060 | 0.0038 | 0.0022 | 0.2968 | 0.9179 |
| transition_quality_stable | 0.7225 | 0.2775 | 0.0057 | 0.0047 | 0.0010 | 0.3005 | 0.8328 |
| broad_breadth_low_deterioration | 0.5784 | 0.4216 | 0.0059 | 0.0049 | 0.0010 | 0.2882 | 0.6667 |
| risk_appetite_positive | 0.5820 | 0.4180 | 0.0057 | 0.0052 | 0.0005 | 0.2910 | 0.6659 |
| recovery_asymmetric_permission | 0.6631 | 0.3369 | 0.0056 | 0.0052 | 0.0005 | 0.2871 | 0.7634 |

## Calm Trend Diagnostics

| rule_name | allowed_share | suppressed_share | future_4w_return_allowed | future_4w_return_suppressed | future_return_lift_allowed_minus_suppressed | whipsaw_rate_allowed |
| --- | --- | --- | --- | --- | --- | --- |
| strict_all_clear | 0.7017 | 0.2983 | 0.0052 | 0.0018 | 0.0034 | 0.1498 |
| broad_breadth_low_deterioration | 0.8983 | 0.1017 | 0.0043 | 0.0029 | 0.0014 | 0.1736 |
| recovery_asymmetric_permission | 0.9695 | 0.0305 | 0.0042 | 0.0032 | 0.0010 | 0.1888 |
| transition_quality_stable | 0.9898 | 0.0102 | 0.0042 | 0.0044 | -0.0002 | 0.1884 |
| risk_appetite_positive | 0.9220 | 0.0780 | 0.0041 | 0.0055 | -0.0014 | 0.1801 |
| deterioration_suppression_only | 0.9966 | 0.0034 | 0.0041 | 0.0157 | -0.0115 | 0.1871 |

## Stressed Panic Behavior

| rule_name | allowed_share | suppressed_share | future_4w_return_allowed | future_4w_return_suppressed | whipsaw_rate_allowed |
| --- | --- | --- | --- | --- | --- |
| broad_breadth_low_deterioration | 0.0000 | 1.0000 |  | 0.0028 |  |
| transition_quality_stable | 0.0000 | 1.0000 |  | 0.0028 |  |
| risk_appetite_positive | 0.0000 | 1.0000 |  | 0.0028 |  |
| strict_all_clear | 0.0000 | 1.0000 |  | 0.0028 |  |
| deterioration_suppression_only | 0.0000 | 1.0000 |  | 0.0028 |  |
| recovery_asymmetric_permission | 0.0000 | 1.0000 |  | 0.0028 |  |

## Interpretation

- Useful eligibility rules should suppress low-quality weeks without suppressing too much calm_trend or recovery participation.
- Stronger future-return lift and lower whipsaw for allowed weeks suggests the confidence signal may be better used as offense permission than direct final-weight alpha.
- These rules are diagnostics only and are not production allocation logic.

## Warnings

- None.
