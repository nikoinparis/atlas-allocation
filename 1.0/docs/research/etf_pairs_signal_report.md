# R4 ETF Pairs Signal Report

Research-only ETF pairs/statistical-arbitrage lab. Cointegration, ADF, hedge ratio, and OU half-life are estimated on pre-2020 training data where possible. No traded long/short portfolio was created.

- Output CSV: `data/02_layer1_signals/etf_pairs_cointegration_report.csv`
- Priority pairs tested: 8
- Candidate-pass: 0
- Research-only: 1
- Rejected: 7
- Skipped: 0

## Pair verdicts

| pair | verdict | cointegration_pvalue_train | adf_pvalue_train_spread | ou_half_life_weeks_train | avg_full_ic | avg_holdout_ic | max_redundancy_vs_strong | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| SPY/QQQ | rejected | 0.6518 | 0.4036 | 56.2342 | -0.0042 | -0.1216 | 0.1798 | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range; weak or non-positive full/holdout pair IC |
| IWM/SPY | rejected | 0.0885 | 0.0268 | 22.8371 | 0.0634 | 0.0745 | 0.4301 | failed training-period cointegration p<=0.05; OU half-life not in 2-13 week range |
| TLT/SPY | rejected | 0.3738 | 0.1723 | 44.9583 | 0.0595 | 0.2087 | 0.6201 | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range; redundancy above 0.50 versus existing strong signals |
| GLD/TLT | rejected | 0.4275 | 0.2064 | 74.6743 | -0.0403 | 0.1943 | 0.4901 | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range; weak or non-positive full/holdout pair IC |
| XLE/USO | rejected | 0.1376 | 0.0460 | 34.7927 | 0.1011 | 0.0844 | 0.1178 | failed training-period cointegration p<=0.05; OU half-life not in 2-13 week range |
| HYG/LQD | research-only | 0.0223 | 0.0051 | 16.2813 | 0.0362 | 0.1193 | 0.4080 | OU half-life not in 2-13 week range |
| EEM/SPY | rejected | 0.0580 | 0.0160 | 37.7391 | -0.0466 | -0.0149 | 0.4806 | failed training-period cointegration p<=0.05; OU half-life not in 2-13 week range; weak or non-positive full/holdout pair IC |
| XLK/QQQ | rejected | 0.9851 | 0.9576 | 196.3829 | 0.0023 | 0.1528 | 0.1632 | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range |

## Viability at weekly frequency

No priority ETF pair cleared the full weekly-frequency candidate-pass gate. Pairs may still be useful diagnostics, but the evidence is not strong enough for a new production signal family.

## Candidate-pass pairs

_No rows._

## Research-only pairs

| pair | avg_full_ic | avg_holdout_ic | verdict_reason | signal_file |
| --- | --- | --- | --- | --- |
| HYG/LQD | 0.0362 | 0.1193 | OU half-life not in 2-13 week range | data/02_layer1_signals/signal_r4_pair_hyg_lqd.csv |

## Rejected pairs

| pair | verdict_reason |
| --- | --- |
| SPY/QQQ | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range; weak or non-positive full/holdout pair IC |
| IWM/SPY | failed training-period cointegration p<=0.05; OU half-life not in 2-13 week range |
| TLT/SPY | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range; redundancy above 0.50 versus existing strong signals |
| GLD/TLT | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range; weak or non-positive full/holdout pair IC |
| XLE/USO | failed training-period cointegration p<=0.05; OU half-life not in 2-13 week range |
| EEM/SPY | failed training-period cointegration p<=0.05; OU half-life not in 2-13 week range; weak or non-positive full/holdout pair IC |
| XLK/QQQ | failed training-period cointegration p<=0.05; failed training-spread ADF p<=0.05; OU half-life not in 2-13 week range |

## Skipped pairs

_No rows._

## State-conditional pair IC

| market_state | horizon_weeks | state_ic | state_ic_tstat_nw | state_hit_rate | state_n_obs | state_warning | pair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| recovery_fragile | 13 | 0.4681 | 6.1938 | 0.6939 | 49 |  | IWM/SPY |
| recovery_fragile | 4 | 0.3317 | 10.4145 | 0.4898 | 49 |  | XLK/QQQ |
| recovery_fragile | 2 | 0.3043 | 9.4012 | 0.5510 | 49 |  | XLK/QQQ |
| recovery_fragile | 4 | 0.2646 | 4.6855 | 0.5870 | 46 |  | XLE/USO |
| recovery_fragile | 13 | 0.2638 | 12.6778 | 0.3673 | 49 |  | SPY/QQQ |
| stressed_panic | 8 | 0.2584 | 4.2145 | 0.5179 | 224 |  | XLE/USO |
| recovery_fragile | 8 | 0.2536 | 0.9615 | 0.5714 | 49 |  | IWM/SPY |
| recovery_fragile | 1 | 0.2480 | 16.6773 | 0.5102 | 49 |  | XLK/QQQ |
| stressed_panic | 4 | 0.2360 | 5.3243 | 0.5467 | 225 |  | XLE/USO |
| stressed_panic | 8 | 0.2228 | 7.8057 | 0.5991 | 227 |  | XLK/QQQ |
| recovery_fragile | 4 | 0.2201 | 3.2313 | 0.5714 | 49 |  | IWM/SPY |
| neutral_mixed | 4 | 0.2183 | 8.0820 | 0.5327 | 413 |  | XLE/USO |
| stressed_panic | 13 | 0.2162 | 2.3533 | 0.4866 | 224 |  | XLE/USO |
| neutral_mixed | 2 | 0.2158 | 10.5700 | 0.5494 | 415 |  | XLE/USO |
| neutral_mixed | 8 | 0.2105 | 4.6626 | 0.5390 | 410 |  | XLE/USO |
| neutral_mixed | 13 | 0.2094 | 2.2824 | 0.5556 | 405 |  | XLE/USO |
| recovery_fragile | 1 | 0.1990 | 2.8452 | 0.5510 | 49 |  | SPY/QQQ |
| stressed_panic | 13 | 0.1875 | 5.5579 | 0.5639 | 227 |  | XLK/QQQ |
| recovery_fragile | 8 | 0.1869 | 10.2865 | 0.4490 | 49 |  | SPY/QQQ |
| stressed_panic | 2 | 0.1856 | 5.4433 | 0.5333 | 225 |  | XLE/USO |

Worst stressed_panic pair rows:

| market_state | horizon_weeks | state_ic | state_ic_tstat_nw | state_hit_rate | state_n_obs | state_warning | pair |
| --- | --- | --- | --- | --- | --- | --- | --- |
| stressed_panic | 8 | -0.1446 | 0.0883 | 0.3877 | 227 |  | SPY/QQQ |
| stressed_panic | 2 | -0.1095 | 0.0410 | 0.4430 | 228 |  | SPY/QQQ |
| stressed_panic | 4 | -0.1095 | 0.6802 | 0.4079 | 228 |  | SPY/QQQ |
| stressed_panic | 13 | -0.1086 | 1.4113 | 0.3744 | 227 |  | SPY/QQQ |
| stressed_panic | 1 | -0.0612 | 1.0795 | 0.4367 | 229 |  | SPY/QQQ |
| stressed_panic | 1 | -0.0610 | 0.0406 | 0.4891 | 229 |  | EEM/SPY |
| stressed_panic | 4 | -0.0583 | 0.4259 | 0.4868 | 228 |  | EEM/SPY |
| stressed_panic | 2 | -0.0576 | -0.0568 | 0.4912 | 228 |  | EEM/SPY |
| stressed_panic | 8 | 0.0203 | 2.4189 | 0.5286 | 227 |  | EEM/SPY |
| stressed_panic | 1 | 0.0211 | 3.7946 | 0.4847 | 229 |  | XLK/QQQ |

## Warnings and limitations

- None.

## Research-only confirmation

R4 wrote pair diagnostics and any statistically viable pair signal CSVs only. It did not create a traded long/short portfolio, change production pins, modify dashboard/public files, or alter live trading/execution logic.
