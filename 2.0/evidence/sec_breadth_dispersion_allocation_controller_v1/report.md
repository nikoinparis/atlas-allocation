# Breadth and dispersion allocation controller v1

Tested 200 strictly lagged allocation controllers without changing the frozen cash-conversion holdings. The selected `h26__cal26__q40__breadth_high__w50_80` path produced 112.93% recent CAGR, 2.806 Sharpe, -9.13% drawdown, and 42.01% full CAGR versus 105.10%, 2.692, -10.08%, and 40.93% for the frozen control. At 200-bps costs it returned 100.00% versus 93.20%.

Controller delays returned 112.93%/112.93%, overlay delays returned 101.57%/109.14%, rolling outperformance was 19.02%, neighborhood joint improvement was 70.00%, and bootstrap probabilities were 88.40%/79.66%. Removing GITLAB INC. left 98.86%.

The complete falsification decision was **FAIL**. No strategy replacement, forward clock, or live execution was enabled.
