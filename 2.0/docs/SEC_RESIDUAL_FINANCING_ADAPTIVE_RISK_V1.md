# Residual Financing and Adaptive Risk Comparison V1

This experiment compares four portfolio constructions on the same causal path
and common endpoint: unlevered exposure, fixed 1.25x exposure, adaptive
1.00x–1.25x exposure, and adaptive exposure with issuer-neutral residual-sleeve
risk-contribution limits. It does not alter the existing frozen 0/52 forward
protocol.

Financing is charged weekly only on exposure above 1.00x. The published 5%
assumption is retained as a reference, while 8% is the baseline comparison and
12% is a stress. Leverage changes incur additional turnover costs. The margin
ledger calculates post-return equity ratios, flags an internal safety threshold
before the broker maintenance threshold, and forces the following week to
1.00x after a breach.

Adaptive leverage uses only returns available before the target week. Exposure
can reach 1.25x only when lagged 13- and 26-week trends are positive, lagged
volatility is below the frozen threshold, and rolling drawdown remains inside
the frozen budget. Otherwise it falls to 1.125x or 1.00x.

The contribution rule is ticker-neutral. Within the separately observable
residual-stock sleeve, it uses only pre-decision volatility history and limits
each issuer's standalone volatility-budget contribution. The already sealed
control sleeve is not decomposed or rewritten in this experiment.

All historical results remain selection-contaminated because the source path
and its history were known before these rules were specified. No retrospective
result authorizes replacement, resets or advances the forward clock, or enables
trading.
