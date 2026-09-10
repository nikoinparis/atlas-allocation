# B6 Priority Ranking Report

Research-only pre-R5 ranking. These recommendations indicate what deserves a later controlled portfolio pass-through test; they do not promote any signal.

- Priority table: `data/02_layer1_signals/b6_priority_table.csv`
- Candidates ranked: 22

## Controlled Pass-Through Candidates

_No rows._

## Gate / Filter Candidates

| signal_name | category | intended_use | 2020_plus_avg_ic | calm_trend_avg_ic | stressed_panic_avg_ic | portfolio_usefulness_score |
| --- | --- | --- | --- | --- | --- | --- |
| r2_commodity_regime__recovery_only | gated_macro | macro_gate | 0.0993 | 0.2611 | 0.0301 | 6.6719 |
| bm_etf_above_50d_ma | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4817 |
| bm_etf_positive_13w_mom | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4395 |
| bm_etf_above_200d_ma | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4144 |
| bm_etf_positive_26w_mom | breadth | alpha_or_offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.4086 |
| bm_sector_positive_26w_mom | sector_breadth | offense_gate | 0.1200 | 0.1233 | 0.0801 | 6.2637 |
| bm_sector_above_200d_ma | sector_breadth | offense_gate | 0.1188 | 0.1233 | 0.0745 | 6.2238 |
| bm_sector_above_50d_ma | sector_breadth | offense_gate | 0.1187 | 0.1220 | 0.0649 | 6.1912 |
| bm_quality_breadth_confirmation | signal_quality | offense_gate | 0.1258 | 0.1233 | 0.0834 | 6.1395 |
| r2_financial_conditions__recovery_only | gated_macro | macro_gate | 0.1973 | 0.0873 | 0.0417 | 6.1346 |
| bm_sector_positive_13w_mom | sector_breadth | offense_gate | 0.1113 | 0.1233 | 0.0523 | 5.9768 |
| bm_risk_on_participation | breadth | offense_gate | 0.1201 | 0.1260 | 0.0438 | 5.9004 |
| r2_credit_spread__calm_trend_only | gated_macro | macro_gate | 0.0916 | 0.0581 |  | 4.7031 |
| r2_vix_term_structure__no_stressed_panic | gated_macro | stress_filter | 0.0546 | 0.0857 | 0.0880 | 4.6057 |
| r2_vix_term_structure__calm_trend_only | gated_macro | macro_gate | 0.0705 | 0.0738 |  | 4.3640 |
| bm_dollar_strength_blended | dollar_strength | risk_filter | 0.0197 | 0.0132 | 0.0272 | 4.0812 |
| bm_quality_risk_on_confirmation__no_stressed_panic | signal_quality | offense_gate | 0.0678 | 0.0506 | 0.0513 | 4.0176 |
| bm_quality_signal_dispersion | signal_quality | chop_filter | 0.0272 | 0.0191 | -0.0052 | 3.9787 |
| bm_dollar_strength_4w | dollar_strength | risk_filter | 0.0221 | 0.0147 | 0.0159 | 3.9020 |
| r2_credit_spread__vix_below_past_median | gated_macro | macro_gate | 0.0662 | 0.0642 | 0.0252 | 3.7582 |

## Too Redundant

| signal_name | max_abs_redundancy_existing | most_redundant_existing_signal | 2020_plus_avg_ic | verdict_reason |
| --- | --- | --- | --- | --- |
| bm_quality_signal_agreement | 0.8855 | moving_average_distance | 0.0456 | Passed core B6 checks but is redundant with existing strong signals. |

## Rejected / Dangerous

_No rows._

## Gated Macro Decomposition Snapshot

| gated_signal_name | mechanism_hypothesis | gate_active_share | holdout_2020_ic_delta | stressed_panic_ic_delta | low_n_warning |
| --- | --- | --- | --- | --- | --- |
| r2_credit_spread__calm_trend_only | calm-state confirmation | 0.2658 | 0.0750 |  | False |
| r2_vix_term_structure__calm_trend_only | calm-state confirmation | 0.2658 | 0.0654 |  | False |
| r2_vix_term_structure__no_stressed_panic | stress avoidance | 0.7928 | 0.0495 | 0.2275 | False |
| r2_credit_spread__vix_below_past_median | volatility filter / credit condition improvement | 0.4865 | 0.0497 | 0.1033 | False |
| r2_financial_conditions__recovery_only | recovery timing | 0.0829 | 0.1613 | 0.0777 | True |
| r2_commodity_regime__recovery_only | commodity/inflation recovery regime | 0.0829 | 0.1218 | 0.0694 | True |

## Warnings

- None.
