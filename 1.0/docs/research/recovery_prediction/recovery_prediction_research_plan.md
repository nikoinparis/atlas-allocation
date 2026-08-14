# Recovery Prediction Research Plan

> Standalone research experiment. This is not Track A/B/C/D, does not modify
> production allocation logic, and does not promote anything into production.

## Research Question

After stress, drawdown, or defensive regimes, can SPY/QQQ recovery and re-risking
states be predicted better than simple baseline behavior?

## Signal Families

1. Drawdown-reversal signals.
2. Short-horizon reversal signals.
3. Breadth thrust / participation signals.
4. Credit improvement signals.
5. Volatility normalization signals.
6. Momentum + reversal interaction signals.

## Research Flow

Build lagged weekly features, separate forward targets, IC diagnostics, family
and combination ETF tilt backtests, simple train/holdout classifiers, a random
timing placebo, and finally an options-readiness diagnostic. No option strategy
is implemented here.

## Causality

All numeric features are shifted one week before scores are computed. Targets
are kept in a separate file and use future 4/8/12-week returns.
