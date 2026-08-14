# Risk Manager Template — ETF Quant Research Committee

**Candidate:** {candidate}
**Production baseline:** improved_phase2b_regime_confidence_boost

The Risk Manager check is a binary pass/fail on each axis. Any single FAIL
prevents promotion to production.

## 1. Tail-loss caps (Phase D rule)

- max_drawdown_delta_vs_production ≥ -0.010 (≥ -1.0pp): __ PASS / __ FAIL
- cvar_5_delta_vs_production ≥ -0.0020 (≥ -0.20pp): __ PASS / __ FAIL

If either FAIL, the candidate worsens tail risk by more than the project
allows.

## 2. Out-of-sample stability

- holdout_raw_delta_vs_production ≥ 0: __ PASS / __ FAIL
- holdout_sharpe_delta_vs_production ≥ -0.02: __ PASS / __ FAIL
- bootstrap_prob_vs_production ≥ 0.60 on holdout: __ PASS / __ FAIL
- rolling_raw_win_rate_vs_production ≥ 0.55: __ PASS / __ FAIL
- rolling_mean_raw_delta_vs_production > 0: __ PASS / __ FAIL

## 3. Turnover and cost drag

- candidate weekly turnover materially higher than production
  (>1.5× threshold): __ PASS / __ FAIL
- candidate cost drag materially higher: __ PASS / __ FAIL
- if any FAIL: the gross-vs-net comparison may be hiding the candidate's
  true edge.

## 4. Hidden exposure check

- candidate avg SPY exposure not materially higher than production: __ PASS / __ FAIL
- candidate avg BIL/cash exposure not materially lower than production: __ PASS / __ FAIL
- candidate max sleeve weight not materially higher than production: __ PASS / __ FAIL

## 5. Comparison fairness

- same date range (start_date, end_date) for candidate and production: __ PASS / __ FAIL
- same cost convention (5bp half-spread): __ PASS / __ FAIL
- same metric definitions (`raw_target_composite`): __ PASS / __ FAIL
- same benchmark set in pairwise tables: __ PASS / __ FAIL
- candidate not present inside the comparator set used for its own
  ranking: __ PASS / __ FAIL

## 6. Causality / lookahead audit

- all new features 1-week-lagged: __ PASS / __ FAIL / __ N/A
- rolling z-scores or rolling normalisations are causal-window only: __ PASS / __ FAIL / __ N/A
- regime labels do not use future information: __ PASS / __ FAIL
- meta-layer probabilities sourced from a walk-forward training pipeline: __ PASS / __ FAIL / __ N/A

## 7. Promotion-readiness flags (any single TRUE = blocked)

- worse max drawdown beyond Phase D cap: __ TRUE / __ FALSE
- worse CVaR beyond Phase D cap: __ TRUE / __ FALSE
- materially higher turnover or cost drag: __ TRUE / __ FALSE
- materially higher SPY exposure (hidden beta): __ TRUE / __ FALSE
- materially lower BIL/cash (hidden defunding of defense): __ TRUE / __ FALSE
- unfair comparison window: __ TRUE / __ FALSE
- missing transaction cost evidence: __ TRUE / __ FALSE
- any possible lookahead or data leakage risk: __ TRUE / __ FALSE
