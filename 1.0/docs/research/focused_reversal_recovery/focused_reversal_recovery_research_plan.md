# Focused Reversal Recovery Research Plan

> Standalone research experiment. This is not Track A/B/C/D. It does not
> modify production allocation logic and does not promote anything into production.

## Research Question

After recent weakness or drawdown in SPY/QQQ, can simple reversal signals
identify bounce setups that improve the ETF baseline and beat random timing?

## Focused Signal Families

1. Short-horizon reversal.
2. Drawdown reversal.
3. Momentum/reversal interaction.

Breadth thrust, credit improvement, and volatility normalization are not
primary alpha families in this experiment. Credit and volatility are used
only as coarse filters to avoid panic, deteriorating credit, and exploding volatility.

## Predeclared Candidates

- `short_reversal_only`: recent negative 1/2/4-week return with non-panic filter.
- `drawdown_recovery_only`: drawdown plus recovery from recent low and trend reclaim.
- `pullback_in_uptrend`: medium-term uptrend with short-term pullback and benign filters.
- `oversold_rebound_after_stress`: stress followed by sharp loss and early stabilization.
- `momentum_reversal_interaction_score`: focused momentum/reversal interaction while avoiding bearish continuation.
- `focused_reversal_composite`: equal blend of only the three focused reversal families.
- `classifier_logistic_reversal`: simple train-only logistic classifier on focused reversal features.
- `classifier_ridge_reversal`: simple train-only ridge probability model on focused reversal features.

## Portfolio Test

The baseline ETF strategy is left unchanged. When a signal fires, the research
overlay tests +2.5%, +5.0%, and +7.5% SPY/QQQ tilts, funded against the
existing baseline return stream with no leverage. The predeclared default is +5.0%.

## Validation

The run reports train/holdout IC, filter false-positive diagnostics, backtest
metrics, random-entry placebo with the same signal frequency, best/top-3
signal-period removal, subperiod checks, classifier precision, and a conservative
options-readiness diagnostic. Final verdicts may be REJECT or RESEARCH-ONLY.

## Causality

Features are built from weekly data and shifted one week before any signal score
or classifier input is used. Forward targets are stored in a separate file.
