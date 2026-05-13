# Phase MLX Neural Network Notes

## Research-Only Warning

Phase MLX-4 is experimental only. It is not production-valid, has high overfitting risk, uses `yfinance` / expanded ETF research data, and should not drive live trading or candidate promotion. No production pins, production strategy logic, dashboard code, or production/shadow candidate status are changed by this work.

## Educational Explanation

A neural network is a flexible function approximator: it learns many small weights that transform inputs into predictions. In this lab, the inputs are date × ETF features such as momentum, volatility, drawdown, regime scores, and breadth diagnostics.

An MLP, or multilayer perceptron, is the simplest common neural-network architecture. It stacks fully connected linear layers with nonlinear activation functions. Here, each ETF-date row is passed through hidden layers and the model outputs either a probability or a predicted forward return.

Dropout randomly turns off a fraction of hidden units during training. That forces the network not to rely too heavily on one pathway and can reduce overfitting, though it does not eliminate data-mining risk.

Early stopping watches validation loss and stops training when the model stops improving. It is a guardrail against training until the network memorizes the training split.

Train, validation, and holdout mean three chronological data blocks. Train data fits preprocessing and model weights. Validation data chooses when to stop training. Holdout data is kept out of fitting and is the main research check.

Neural networks might help this ETF project if there are nonlinear interactions between trend, volatility, cross-sectional strength, market regime, and breadth. They might overfit because the ETF universe is expanded, signals are noisy, validation windows are short, and many model/portfolio choices create multiple-testing risk.

This project uses neural networks only to rank ETFs each week. The highest-scoring ETFs are tested in simple top-N portfolios; no neural-network output is promoted automatically.

## Technical Setup

- Torch available: True / version: 2.8.0
- Device used: `cpu`
- Input features: numeric MLX-2 features only; `Date` and `ticker` are identifiers, not model inputs.
- Targets: `top_quintile_forward_4w`, `beats_SPY_4w`, and `forward_return_4w`.
- Splits: train through 2017-12-31; validation 2018-01-01 through 2019-12-31; holdout 2020-01-01 onward.
- Architecture: small MLPs with ReLU activations and dropout, plus one deeper dropout MLP.
- Loss functions: BCEWithLogitsLoss for classifiers and SmoothL1/Huber loss for regression.
- Preprocessing: train-only medians for missing values and train-only mean/std standardization.
- Leakage controls: no `forward_*`, `beats_*`, `top_quintile_*`, or other target-like columns are used as input features; validation and holdout are not used for preprocessing or fitting model weights.

## Results

Models run:

- mlp_classifier_top_quintile_forward_4w
- mlp_classifier_beats_SPY_4w
- mlp_regressor_forward_return_4w
- deep_dropout_mlp_classifier_top_quintile_forward_4w

Models skipped:

- autoencoder_feature_compression_mlp: Skipped in MLX-4 sprint to keep runtime and complexity bounded; candidate for later representation-learning phase.

- Best validation model: mlp_classifier_beats_SPY_4w__top5__inverse_vol (Sharpe 0.437, annual return 7.59%)
- Best holdout model: deep_dropout_mlp_classifier_top_quintile_forward_4w__top10__inverse_vol (Sharpe 0.907, annual return 18.03%)
- Best holdout annual return model: deep_dropout_mlp_classifier_top_quintile_forward_4w__top10__inverse_vol (Sharpe 0.907, annual return 18.03%)
- Best holdout drawdown model: mlp_classifier_top_quintile_forward_4w__top10__equal_weight (Sharpe 0.715, annual return 12.74%)
- Best holdout Sharpe: 0.907
- Best holdout annual return: 18.03%

Comparisons by holdout Sharpe:

- Beats MLX-3 best tabular model: True
- Beats simple momentum: True
- Beats SPY: True
- Beats 60/40: True
- Beats production: False
- Beats official shadow: False

## Interpretation

Neural networks are useful infrastructure here, but the bar is not whether one backtest looks clever. The key question is whether the model beats simple, robust baselines on holdout without suspicious train/validation behavior. Any promising result remains research-only or ML shadow at most until it survives harsher walk-forward testing, turnover realism, regime slicing, and human review.

Warnings:

- None
