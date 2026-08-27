# Generic cap and persistence retest v1

Tested 180 ticker-agnostic cap/persistence variants around the frozen breadth challenger. The selected `cap1.50x__breadth2in1out__overlay1in1out` produced 112.37% recent CAGR, 2.802 Sharpe, -9.13% drawdown, and 42.28% full CAGR. The unchanged challenger was 112.93%; the frozen incumbent was 105.10%.

At 200-bps costs the result was 99.46%; a one-week overlay delay was 101.31%; the worst issuer removal (GITLAB INC.) left 98.54%. Bootstrap probabilities were 88.40%/79.66% and rolling outperformance was 20.25%.

Complete falsification: **FAIL**. No promotion or live execution was enabled.
