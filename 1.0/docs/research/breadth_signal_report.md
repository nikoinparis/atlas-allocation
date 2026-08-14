# Breadth Signal Report

Research-only B1 breadth and participation-quality signal build. All signal CSVs include `research_only=True` and a one-week `signal_value_tradable` lag.

- Signals built: 14
- Summary CSV: `data/02_layer1_signals/breadth_signal_summary.csv`

## Verdicts

| signal_name | category | verdict | avg_full_mean_ic | avg_holdout_mean_ic | calm_trend_mean_ic | stressed_panic_mean_ic | max_redundancy_vs_strong | verdict_reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| bm_etf_above_50d_ma | ETF breadth | candidate-pass | 0.1182 | 0.1258 | 0.1236 | 0.0833 | 0.2120 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_etf_above_200d_ma | ETF breadth | candidate-pass | 0.1208 | 0.1258 | 0.1236 | 0.0833 | 0.2794 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_sector_above_50d_ma | sector breadth | candidate-pass | 0.1150 | 0.1187 | 0.1223 | 0.0647 | 0.2172 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_sector_above_200d_ma | sector breadth | candidate-pass | 0.1206 | 0.1188 | 0.1236 | 0.0741 | 0.3072 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_etf_positive_13w_mom | ETF breadth | candidate-pass | 0.1213 | 0.1258 | 0.1236 | 0.0833 | 0.2542 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_etf_positive_26w_mom | ETF breadth | candidate-pass | 0.1198 | 0.1258 | 0.1236 | 0.0833 | 0.2851 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_sector_positive_13w_mom | sector breadth | candidate-pass | 0.1169 | 0.1113 | 0.1236 | 0.0521 | 0.2732 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_sector_positive_26w_mom | sector breadth | candidate-pass | 0.1202 | 0.1200 | 0.1236 | 0.0796 | 0.3102 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_offensive_vs_defensive_sector_breadth | sector breadth | research-only | -0.0168 | 0.0070 | -0.0079 | 0.0276 | 0.0570 | full IC not positive |
| bm_risk_on_participation | risk-on breadth | candidate-pass | 0.1209 | 0.1201 | 0.1263 | 0.0436 | 0.2766 | Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy. |
| bm_risk_on_minus_defensive_participation | risk-on breadth | promising-if-gated | 0.0081 | 0.0254 | 0.0506 | -0.0407 | 0.1852 | stressed_panic damage |
| bm_breadth_change_4w | breadth thrust | research-only | 0.0236 | -0.0092 | 0.0187 | 0.0148 | 0.0818 | holdout IC not positive |
| bm_breadth_momentum_13w | breadth thrust | promising-if-gated | 0.0064 | -0.0470 | 0.0263 | -0.0842 | 0.0632 | holdout IC not positive; stressed_panic damage |
| bm_participation_acceleration | breadth thrust | research-only | -0.0152 | 0.0042 | -0.0033 | 0.0353 | 0.0345 | full IC not positive |

## Strongest Calm Trend Rows

| signal_name | category | calm_trend_mean_ic | avg_holdout_mean_ic | verdict |
| --- | --- | --- | --- | --- |
| bm_risk_on_participation | risk-on breadth | 0.1263 | 0.1201 | candidate-pass |
| bm_etf_above_50d_ma | ETF breadth | 0.1236 | 0.1258 | candidate-pass |
| bm_etf_above_200d_ma | ETF breadth | 0.1236 | 0.1258 | candidate-pass |
| bm_sector_above_200d_ma | sector breadth | 0.1236 | 0.1188 | candidate-pass |
| bm_etf_positive_13w_mom | ETF breadth | 0.1236 | 0.1258 | candidate-pass |
| bm_etf_positive_26w_mom | ETF breadth | 0.1236 | 0.1258 | candidate-pass |
| bm_sector_positive_13w_mom | sector breadth | 0.1236 | 0.1113 | candidate-pass |
| bm_sector_positive_26w_mom | sector breadth | 0.1236 | 0.1200 | candidate-pass |
| bm_sector_above_50d_ma | sector breadth | 0.1223 | 0.1187 | candidate-pass |
| bm_risk_on_minus_defensive_participation | risk-on breadth | 0.0506 | 0.0254 | promising-if-gated |

## Stressed Panic Damage Watch

| signal_name | category | stressed_panic_mean_ic | avg_full_mean_ic | verdict |
| --- | --- | --- | --- | --- |
| bm_breadth_momentum_13w | breadth thrust | -0.0842 | 0.0064 | promising-if-gated |
| bm_risk_on_minus_defensive_participation | risk-on breadth | -0.0407 | 0.0081 | promising-if-gated |
| bm_breadth_change_4w | breadth thrust | 0.0148 | 0.0236 | research-only |
| bm_offensive_vs_defensive_sector_breadth | sector breadth | 0.0276 | -0.0168 | research-only |
| bm_participation_acceleration | breadth thrust | 0.0353 | -0.0152 | research-only |
| bm_risk_on_participation | risk-on breadth | 0.0436 | 0.1209 | candidate-pass |
| bm_sector_positive_13w_mom | sector breadth | 0.0521 | 0.1169 | candidate-pass |
| bm_sector_above_50d_ma | sector breadth | 0.0647 | 0.1150 | candidate-pass |
| bm_sector_above_200d_ma | sector breadth | 0.0741 | 0.1206 | candidate-pass |
| bm_sector_positive_26w_mom | sector breadth | 0.0796 | 0.1202 | candidate-pass |

## Warnings

- sector breadth missing tickers skipped: XLRE, XLC
- RSP absent from weekly_prices.csv; RSP/SPY equal-weight breadth proxy skipped.
