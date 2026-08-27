# SEC Form 4 rank feature v1

Tested 90 causal, diversified ranking variants. The selected candidate produced 105.48% recent CAGR, 2.705 Sharpe, -9.83% drawdown, and 38.17% full CAGR, versus 105.10% and 40.93% for the frozen control.

Against its matched zero-Form-4 baseline, the feature added 0.73% to recent CAGR but removed 2.69% from full CAGR. A one-week decision delay returned 98.21%; only 25.77% of completed rolling windows beat the control; 4-week and 13-week bootstrap probabilities were 80.54% and 87.22%; and excluding GITLAB INC. reduced recent CAGR to 96.24%.

The full falsification decision was FAIL. Form 4 boosts were bounded, every sleeve held 20 equal-target names, sector exposure was capped, extreme prior winners received a causal ranking penalty, and exact leave-one-company-out reranking replaced each excluded issuer. The candidate was not promoted. No live trading was enabled.
