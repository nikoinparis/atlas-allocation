# Regime-conditioned sleeve lineage recovery — Batch 46

The saved sleeve is reproduced exactly only when Layer 2B regime files are absent and the notebook uses its Layer 1 `macro_risk_score_tradable` fallback. Position difference: 0.000e+00; saved return-path difference: 1.332e-15; all three prefix tests and the deterministic rerun passed: **True**.

The newer Layer 2B path remains different on 979 rows with maximum weight difference 0.5625. It is evaluated only as a post-discovery diagnostic and is not promoted in this batch.

At 50 bps, causal GGG using the recovered saved lineage has recent three-year CAGR 12.89%, Sharpe 1.544, and max drawdown -7.36%. Substituting the current Layer 2B sleeve diagnostically gives 12.25%, 1.449, and -8.21%.

This closes implementation lineage for the fifth upstream sleeve. It does not create untouched out-of-sample evidence or remove universe and source-data-vintage limitations. The current Layer 2B alternative requires a separately predeclared forward comparison before it can replace the frozen lineage.
