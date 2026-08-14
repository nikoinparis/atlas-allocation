# Macro Feature Coverage Report

**Sources used:** project-internal ETF returns and Layer 2B regime engine output. FRED API and OpenBB were not available in this environment (fredapi / openbb not installed; no live web egress).

**No predictive claims** — the audit reports availability and state-conditional means only.

**Successfully built:** 15 / 15 features.

## Coverage table

```
                          feature                                                                                                                                       description                                   source               lag_assumption first_date  last_date  n_obs  n_total_weeks  missing_frac  available
      hyg_lqd_credit_spread_proxy Credit-risk proxy: 13-week return of HYG minus 13-week return of LQD. Negative values indicate credit deterioration relative to investment grade.                   ETF returns (HYG, LQD) 0w (already weekly observed) 2007-07-13 2026-04-10    979           1109      0.117223       True
           uup_dollar_strength_4w                                                                        Dollar strength proxy: 4-week return of UUP. Positive = USD strengthening.                        ETF returns (UUP)                           0w 2007-03-30 2026-04-10    994           1109      0.103697       True
            tlt_rate_sensitive_4w                                         Rate-sensitive proxy: 4-week return of TLT (long Treasury). Positive = rates falling / flight to quality.                        ETF returns (TLT)                           0w 2005-02-04 2026-04-10   1106           1109      0.002705       True
                 gld_defensive_4w                                                                                                  Defensive/inflation proxy: 4-week return of GLD.                        ETF returns (GLD)                           0w 2005-02-04 2026-04-10   1106           1109      0.002705       True
              spy_realized_vol_4w                                             SPY realized weekly std × sqrt(52), 4-week trailing window. Used as VIX proxy in absence of VIX data.                        ETF returns (SPY)                           0w 2005-02-04 2026-04-10   1106           1109      0.002705       True
       spy_drawdown_from_52w_high                                                                                                     SPY drawdown vs trailing 52w cumulative high.                        ETF returns (SPY)                           0w 2006-01-06 2026-04-10   1058           1109      0.045987       True
                 spy_minus_iei_3m                                                                      Risk-on / risk-off proxy: 13-week return of SPY minus 13-week return of IEF.                   ETF returns (SPY, IEF)                           0w 2005-04-08 2026-04-10   1097           1109      0.010821       True
                 xlf_minus_xlu_3m                                                            Cyclical-vs-defensive sector proxy: 13-week return of XLF minus 13-week return of XLU.                   ETF returns (XLF, XLU)                           0w 2005-04-08 2026-04-10   1097           1109      0.010821       True
                     ig_credit_4w                                                                                              Investment-grade credit proxy: 4-week return of LQD.                        ETF returns (LQD)                           0w 2005-02-04 2026-04-10   1106           1109      0.002705       True
                     hy_credit_4w                                                                                                    High-yield credit proxy: 4-week return of HYG.                        ETF returns (HYG)                           0w 2007-05-11 2026-04-10    988           1109      0.109107       True
         regime_recent_stress_26w                                                                                       Layer 2B `recent_stress_26w` field — realized stress index. market_state_history.csv (regime engine)       regime engine baseline 2005-01-14 2026-04-10   1109           1109      0.000000       True
       regime_avg_corr_risk_off_z                                                                                   Layer 2B `avg_corr_risk_off_z` — pairwise correlation pressure. market_state_history.csv (regime engine)       regime engine baseline 2005-10-07 2026-04-10   1071           1109      0.034265       True
regime_transition_non_stress_prob                                                                                                            Layer 2B `transition_non_stress_prob`. market_state_history.csv (regime engine)       regime engine baseline 2005-03-18 2026-04-10   1060           1109      0.044184       True
           regime_market_drawdown                                                                                                                       Layer 2B `market_drawdown`. market_state_history.csv (regime engine)       regime engine baseline 2005-01-14 2026-04-10   1109           1109      0.000000       True
            regime_breadth_sma_43                                                                                      Layer 2B `breadth_sma_43` — % of universe above 43-week SMA. market_state_history.csv (regime engine)       regime engine baseline 2005-01-14 2026-04-10   1109           1109      0.000000       True
```

## Lag / release-timing assumptions

All ETF-derived features use weekly close prices already aligned to the project's weekly date index. No additional lag is applied because the ETF prices are observable in real time. Regime-engine-derived features inherit the regime engine's existing 1-week lag convention and are causal-safe at construction.

