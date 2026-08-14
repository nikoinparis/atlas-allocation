# R2 Signal Validation Report

Research-only validation of the expanded free-data signal zoo. All candidate signals are lagged via `signal_value_tradable` before validation. No signal was added to production logic.

- Output CSV: `data/02_layer1_signals/r2_signal_validation_results.csv`
- Signals attempted: 8
- Candidate-pass: 1
- Research-only: 0
- Rejected: 7
- Skipped: 0

## Verdict table

| signal_name | verdict | avg_full_mean_ic | avg_holdout_mean_ic | max_redundancy_vs_strong | most_redundant_existing_signal | stressed_panic_mean_ic | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r2_yield_curve | rejected | -0.0294 | 0.0757 | 0.0474 | breadth_confirmed_momentum | -0.0228 | full-period IC is not positive; obvious stressed_panic damage |
| r2_credit_spread | rejected | 0.0185 | 0.0166 | 0.2589 | xsmom_global | -0.0784 | obvious stressed_panic damage |
| r2_financial_conditions | rejected | 0.0581 | 0.0360 | 0.2167 | multi_mom_equal | -0.0362 | obvious stressed_panic damage |
| r2_vix_term_structure | rejected | 0.0134 | 0.0051 | 0.1199 | multi_mom_equal | -0.1394 | obvious stressed_panic damage |
| r2_dollar_strength | candidate-pass | 0.0314 | 0.0388 | 0.1122 | breadth_confirmed_momentum | 0.0161 | Passes positive full/holdout IC, redundancy, stressed_panic, and observation gates. |
| r2_commodity_regime | rejected | 0.0024 | -0.0224 | 0.2051 | breadth_confirmed_momentum | -0.0398 | holdout IC is not positive; obvious stressed_panic damage |
| r2_cross_asset_divergence | rejected | -0.0078 | -0.0382 | 0.0871 | breadth_confirmed_momentum | -0.1038 | full-period IC is not positive; holdout IC is not positive; obvious stressed_panic damage |
| r2_volume_divergence | rejected | -0.0173 | -0.0093 | 0.2441 | breadth_confirmed_momentum | -0.0586 | full-period IC is not positive; holdout IC is not positive; obvious stressed_panic damage |

## Candidate-pass signals

| signal_name | avg_full_mean_ic | avg_holdout_mean_ic | max_redundancy_vs_strong |
| --- | --- | --- | --- |
| r2_dollar_strength | 0.0314 | 0.0388 | 0.1122 |

## Research-only signals

_No rows._

## Rejected signals

| signal_name | avg_full_mean_ic | avg_holdout_mean_ic | stressed_panic_mean_ic | verdict_reason |
| --- | --- | --- | --- | --- |
| r2_yield_curve | -0.0294 | 0.0757 | -0.0228 | full-period IC is not positive; obvious stressed_panic damage |
| r2_credit_spread | 0.0185 | 0.0166 | -0.0784 | obvious stressed_panic damage |
| r2_financial_conditions | 0.0581 | 0.0360 | -0.0362 | obvious stressed_panic damage |
| r2_vix_term_structure | 0.0134 | 0.0051 | -0.1394 | obvious stressed_panic damage |
| r2_commodity_regime | 0.0024 | -0.0224 | -0.0398 | holdout IC is not positive; obvious stressed_panic damage |
| r2_cross_asset_divergence | -0.0078 | -0.0382 | -0.1038 | full-period IC is not positive; holdout IC is not positive; obvious stressed_panic damage |
| r2_volume_divergence | -0.0173 | -0.0093 | -0.0586 | full-period IC is not positive; holdout IC is not positive; obvious stressed_panic damage |

## Skipped signals

_No rows._

## State-conditional notes

Top calm_trend R2 signal/horizon rows:

| signal_name | horizon_weeks | mean_ic | ic_tstat_nw | n_dates |
| --- | --- | --- | --- | --- |
| r2_vix_term_structure | 13 | 0.1308 | 2.6976 | 273 |
| r2_credit_spread | 13 | 0.1175 | 2.1299 | 273 |
| r2_financial_conditions | 13 | 0.1129 | 2.0815 | 287 |
| r2_vix_term_structure | 8 | 0.1094 | 2.5333 | 273 |
| r2_vix_term_structure | 4 | 0.0865 | 2.3484 | 273 |
| r2_financial_conditions | 4 | 0.0745 | 1.8286 | 287 |
| r2_credit_spread | 4 | 0.0729 | 1.7680 | 273 |
| r2_financial_conditions | 8 | 0.0715 | 1.5159 | 287 |
| r2_credit_spread | 8 | 0.0645 | 1.2810 | 273 |
| r2_vix_term_structure | 2 | 0.0629 | 2.1277 | 273 |

Worst stressed_panic R2 signal/horizon rows:

| signal_name | horizon_weeks | mean_ic | ic_tstat_nw | n_dates |
| --- | --- | --- | --- | --- |
| r2_vix_term_structure | 13 | -0.2333 | -5.1310 | 166 |
| r2_vix_term_structure | 8 | -0.1916 | -3.6861 | 166 |
| r2_cross_asset_divergence | 13 | -0.1464 | -2.1770 | 187 |
| r2_cross_asset_divergence | 8 | -0.1320 | -2.1505 | 187 |
| r2_vix_term_structure | 4 | -0.1316 | -2.4857 | 167 |
| r2_credit_spread | 8 | -0.1106 | -1.7905 | 187 |
| r2_volume_divergence | 13 | -0.0981 | -2.0084 | 227 |
| r2_vix_term_structure | 2 | -0.0928 | -2.1179 | 167 |
| r2_commodity_regime | 13 | -0.0890 | -2.3200 | 216 |
| r2_cross_asset_divergence | 2 | -0.0855 | -2.1888 | 188 |

## Warnings and limitations

- None.

## Research-only confirmation

R2 wrote candidate signal CSVs and validation reports only. It did not alter production pins, dashboard/public files, existing production portfolio returns/weights, or live trading/execution logic.
