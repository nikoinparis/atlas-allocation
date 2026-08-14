# GGG upstream sleeve causality audit — Batch 45

Five source sleeves were rebuilt with the pinned native Layer 2A notebook and tested at 3 truncated-history cutoffs. Qualified: **4/5**.

Maximum native position difference: 5.625e-01. Maximum prefix difference: 0.000e+00. Maximum next-week gross-return identity error: 1.041e-16.

Qualified sleeves: dual_momentum_topn, cta_trend_long_only, composite_selective_signals, taa_10m_sma. Unresolved sleeves: composite_regime_conditioned.

The return-label check confirms that a position dated t earns the return from t to t+1. That return is therefore a future outcome at the decision timestamp and must be excluded from date-t allocator training. Passing position-prefix tests does not change that label rule.

Qualification is limited to implementation causality and reproducibility. It does not cure fixed-universe survivorship risk, non-vintage source data, or historical strategy-selection contamination, and it does not authorize live trading.
