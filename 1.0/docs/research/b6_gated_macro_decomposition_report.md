# B6 Gated Macro Decomposition Report

Research-only decomposition of selected gated macro candidates. Each row compares the original R2 signal against its lagged gated version.

- Output CSV: `data/02_layer1_signals/b6_gated_macro_decomposition.csv`
- Rows tested: 6

## Gate Effects

| gated_signal_name | mechanism_hypothesis | gate_active_share | active_calm_trend_n | active_recovery_fragile_n | active_recovery_confirmed_n | active_stressed_panic_n | holdout_2020_ic_delta | stressed_panic_ic_delta | low_n_warning |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| r2_credit_spread__calm_trend_only | calm-state confirmation | 0.2658 | 253 | 0 | 2 | 0 | 0.0750 |  | False |
| r2_vix_term_structure__calm_trend_only | calm-state confirmation | 0.2658 | 253 | 0 | 2 | 0 | 0.0654 |  | False |
| r2_vix_term_structure__no_stressed_panic | stress avoidance | 0.7928 | 295 | 43 | 43 | 31 | 0.0495 | 0.2275 | False |
| r2_credit_spread__vix_below_past_median | volatility filter / credit condition improvement | 0.4865 | 247 | 25 | 22 | 11 | 0.0497 | 0.1033 | False |
| r2_financial_conditions__recovery_only | recovery timing | 0.0829 | 3 | 27 | 29 | 3 | 0.1613 | 0.0777 | True |
| r2_commodity_regime__recovery_only | commodity/inflation recovery regime | 0.0829 | 3 | 27 | 29 | 3 | 0.1218 | 0.0694 | True |

## Interpretation

- Calm-only gates mostly work by turning macro into calm-state confirmation rather than stress prediction.
- No-stressed-panic gates work by suppressing known stress damage, but still need portfolio pass-through checks.
- Recovery-only gates can look strong in holdout but are lower-N and should be treated carefully.
- VIX-below-past-median credit gating is interpretable as a volatility/credit-condition filter.

## Warnings

- None.
