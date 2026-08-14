# Frontier Phase 1A Component Diagnostics

Diagnostic-only review of the first deployment-quality composite. No wrapper experiment was run.

## Full-Period Component IC

| component | spearman_ic | n_observations | mean_component | mean_forward_4w_return |
| --- | --- | --- | --- | --- |
| path_clarity_r2 | 0.0345 | 1093 | 0.4961 | 0.0089 |
| state_persistence_score | -0.0318 | 1105 | 0.4906 | 0.0087 |
| credit_confirmation | -0.0434 | 983 | 0.0142 | 0.0086 |
| deployment_quality_composite | -0.0495 | 1106 | 0.0346 | 0.0087 |
| leadership_quality_score | -0.0553 | 1092 | 0.5942 | 0.0089 |
| breadth_quality_score | -0.0566 | 1105 | 0.5729 | 0.0087 |

## Component IC By State

| market_state | component | spearman_ic | n_observations |
| --- | --- | --- | --- |
| calm_trend | credit_confirmation | -0.0197 | 273 |
| calm_trend | leadership_quality_score | -0.0484 | 295 |
| calm_trend | breadth_quality_score | -0.1070 | 295 |
| calm_trend | path_clarity_r2 | -0.1502 | 295 |
| calm_trend | state_persistence_score | -0.1641 | 295 |
| calm_trend | deployment_quality_composite | -0.1846 | 295 |
| neutral_mixed | path_clarity_r2 | -0.0253 | 478 |
| neutral_mixed | breadth_quality_score | -0.0517 | 490 |
| neutral_mixed | state_persistence_score | -0.0646 | 490 |
| neutral_mixed | credit_confirmation | -0.0729 | 399 |
| neutral_mixed | deployment_quality_composite | -0.1085 | 491 |
| neutral_mixed | leadership_quality_score | -0.1090 | 477 |
| recovery_confirmed | state_persistence_score | 0.0850 | 43 |
| recovery_confirmed | breadth_quality_score | 0.0484 | 43 |
| recovery_confirmed | leadership_quality_score | 0.0143 | 43 |
| recovery_confirmed | path_clarity_r2 | -0.0207 | 43 |
| recovery_confirmed | deployment_quality_composite | -0.1329 | 43 |
| recovery_confirmed | credit_confirmation | -0.2041 | 40 |
| recovery_fragile | state_persistence_score | 0.3019 | 49 |
| recovery_fragile | path_clarity_r2 | 0.2671 | 49 |
| recovery_fragile | deployment_quality_composite | 0.2303 | 49 |
| recovery_fragile | leadership_quality_score | 0.1812 | 49 |
| recovery_fragile | breadth_quality_score | 0.1506 | 49 |
| recovery_fragile | credit_confirmation | -0.2432 | 46 |
| stressed_panic | path_clarity_r2 | 0.3862 | 228 |
| stressed_panic | deployment_quality_composite | 0.1676 | 228 |
| stressed_panic | state_persistence_score | 0.0969 | 228 |
| stressed_panic | leadership_quality_score | 0.0314 | 228 |
| stressed_panic | credit_confirmation | 0.0062 | 225 |
| stressed_panic | breadth_quality_score | -0.1109 | 228 |

## Helping Components

| component | positive_state_count |
| --- | --- |
| leadership_quality_score | 3 |
| state_persistence_score | 3 |
| breadth_quality_score | 2 |
| deployment_quality_composite | 2 |
| path_clarity_r2 | 2 |
| credit_confirmation | 1 |

## Hurting Components

| component | negative_state_count |
| --- | --- |
| credit_confirmation | 4 |
| breadth_quality_score | 3 |
| deployment_quality_composite | 3 |
| path_clarity_r2 | 3 |
| leadership_quality_score | 2 |
| state_persistence_score | 2 |

## Composite Redundancy

Full-period Spearman correlation versus the original composite:

| component_1 | spearman_corr | n_observations |
| --- | --- | --- |
| leadership_quality_score | 0.7157 | 1096 |
| breadth_quality_score | 0.7090 | 1109 |
| path_clarity_r2 | 0.6249 | 1097 |
| credit_confirmation | 0.4956 | 987 |
| state_persistence_score | 0.2257 | 1109 |

## Diagnostic Composite Variants

| variant | mean_state_ic | min_state_ic | positive_states | negative_states | total_state_obs |
| --- | --- | --- | --- | --- | --- |
| variant_b_flip_negative_full_ic | 0.0772 | 0.0154 | 5 | 0 | 1106 |
| variant_c_flip_negative_3plus_states | -0.0015 | -0.1059 | 3 | 2 | 1106 |
| variant_f_exclude_persistence_and_credit | 0.0465 | -0.1068 | 2 | 3 | 1106 |
| variant_e_exclude_credit_confirmation | 0.0248 | -0.2035 | 2 | 3 | 1106 |
| variant_d_exclude_state_persistence | 0.0098 | -0.1137 | 2 | 3 | 1106 |
| variant_a_original_equal_weight | -0.0056 | -0.1846 | 2 | 3 | 1106 |

Full-period variant IC:

| variant | spearman_ic | n_observations | overfitting_warning |
| --- | --- | --- | --- |
| variant_b_flip_negative_full_ic | 0.1053 | 1106 | diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals |
| variant_c_flip_negative_3plus_states | -0.0084 | 1106 | diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals |
| variant_f_exclude_persistence_and_credit | -0.0340 | 1106 | diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals |
| variant_d_exclude_state_persistence | -0.0378 | 1106 | diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals |
| variant_e_exclude_credit_confirmation | -0.0438 | 1106 | diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals |
| variant_a_original_equal_weight | -0.0495 | 1106 | diagnostic variant; signs/exclusions are full-history diagnostics, not selected signals |

## Monotonicity Sample

| market_state | component | quintile | n_observations | mean_forward_4w_return | median_component |
| --- | --- | --- | --- | --- | --- |
| calm_trend | breadth_quality_score | insufficient_data | 295 |  |  |
| calm_trend | path_clarity_r2 | 1 | 59 | 0.0111 | 0.1192 |
| calm_trend | path_clarity_r2 | 2 | 59 | 0.0138 | 0.4691 |
| calm_trend | path_clarity_r2 | 3 | 59 | 0.0028 | 0.7314 |
| calm_trend | path_clarity_r2 | 4 | 59 | 0.0034 | 0.8353 |
| calm_trend | path_clarity_r2 | 5 | 59 | 0.0021 | 0.9309 |
| calm_trend | state_persistence_score | insufficient_data | 295 |  |  |
| calm_trend | credit_confirmation | insufficient_data | 273 |  |  |
| calm_trend | leadership_quality_score | insufficient_data | 295 |  |  |
| calm_trend | deployment_quality_composite | 1 | 59 | 0.0110 | -0.5852 |
| calm_trend | deployment_quality_composite | 2 | 59 | 0.0079 | 0.1545 |
| calm_trend | deployment_quality_composite | 3 | 59 | 0.0112 | 0.7535 |
| calm_trend | deployment_quality_composite | 4 | 59 | 0.0036 | 1.1123 |
| calm_trend | deployment_quality_composite | 5 | 59 | -0.0005 | 1.5784 |
| neutral_mixed | breadth_quality_score | insufficient_data | 490 |  |  |
| neutral_mixed | path_clarity_r2 | 1 | 96 | 0.0078 | 0.0438 |
| neutral_mixed | path_clarity_r2 | 2 | 95 | 0.0147 | 0.2598 |
| neutral_mixed | path_clarity_r2 | 3 | 96 | 0.0070 | 0.5005 |
| neutral_mixed | path_clarity_r2 | 4 | 95 | 0.0149 | 0.7162 |
| neutral_mixed | path_clarity_r2 | 5 | 96 | 0.0079 | 0.8824 |
| neutral_mixed | state_persistence_score | insufficient_data | 490 |  |  |
| neutral_mixed | credit_confirmation | insufficient_data | 399 |  |  |
| neutral_mixed | leadership_quality_score | 1 | 113 | 0.0190 | 0.2500 |
| neutral_mixed | leadership_quality_score | 2 | 132 | 0.0078 | 0.6250 |
| neutral_mixed | leadership_quality_score | 3 | 94 | 0.0057 | 0.7500 |
| neutral_mixed | leadership_quality_score | 4 | 94 | 0.0062 | 0.8750 |
| neutral_mixed | leadership_quality_score | 5 | 44 | 0.0158 | 1.0000 |
| neutral_mixed | deployment_quality_composite | 1 | 99 | 0.0145 | -1.3453 |
| neutral_mixed | deployment_quality_composite | 2 | 98 | 0.0127 | -0.4322 |
| neutral_mixed | deployment_quality_composite | 3 | 98 | 0.0066 | 0.0000 |

## Diagnosis

- The negative IC is not assumed to be proof against every component; it can reflect sign errors, state dependence, redundancy, or a design that rewards late-cycle maturity rather than forward opportunity.
- Variant sign flips and exclusions are diagnostics only. They use full-history IC and therefore carry overfitting risk.
- The original composite should not be passed into the wrapper until signs and state behavior are predeclared and revalidated.

## Explicit Recommendation

Do not run wrapper diagnostics yet, but Phase 1A is worth revising around the best diagnostic variant with predeclared signs and fresh validation.
