# Independent V2 GGG port — Batch 44

The Version 2-owned implementation reproduced all six saved stages with maximum difference 1.998e-15; return-path difference was 5.862e-14 and correlation 1.000000000000000. Determinism, static scanning, micro-scenarios, audit logging, and source hashing passed.

Qualification nevertheless failed. Across controlled future-price shocks, the legacy-equivalent decision weights changed by as much as 0.2380 before or at the cutoff. The cause is one-week allocator lookahead: the date-t covariance includes a sleeve return whose realization uses t+1 prices.

A causal correction excluding the current labeled sleeve-return row passed prefix invariance with maximum difference 0.000e+00. At 50 bps, its retrospective recent three-year metrics are CAGR 12.89%, arithmetic return 12.46%, Sharpe 1.544, and max drawdown -7.36%, versus the contaminated equivalent port's 12.86% CAGR and 1.542 Sharpe.

Decision: reject the mechanically equivalent legacy port as a qualified implementation. Keep the causal correction as a research shadow only; it still inherits upstream fixed-universe, vintage, and historical selection limitations.
