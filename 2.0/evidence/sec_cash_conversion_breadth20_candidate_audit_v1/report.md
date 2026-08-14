# Breadth-20 cash-conversion candidate audit v1

The frozen candidate assigns 50% to the existing 10/40 universal-cap leader
unless the breadth-20 cash-conversion sleeve has both a positive prior 11-week
return and a higher prior 11-week return than the leader. When both conditions
hold, the allocation is 50% leader and 50% cash conversion. All rolling inputs
are shifted one week. The cash-conversion sleeve selects the top 20
sector-neutral SEC scores quarterly and equal weights them.

At 50-bps costs, trailing-one-year CAGR was **105.10%**, Sharpe was **2.692**,
and maximum drawdown was **-10.08%**, versus **92.31%**, **2.433**, and
**-13.44%** for the control. YTD CAGR was **109.50%**, trailing-two-year CAGR
was **59.70%**, and full-period CAGR was **40.93%** versus **38.59%** for the
control. At 100 and 200 bps, trailing-one-year CAGR remained **101.06%** and
**93.20%**. The 50-bps adverse missing-company full-period CAGR was **37.45%**
versus **37.04%** for the adverse control.

Every declared falsification check passed. Removing GitLab, the worst recent
single-company exclusion, left **96.50%** trailing-one-year CAGR. One- and
two-week signal delays retained **98.13%** and **102.72%**. The 4- and 13-week
block bootstraps assigned 99.62% and 99.38% probability to a positive recent
annualized return difference, although their fifth-percentile lower bounds
were effectively zero rather than economically large. Prefix invariance passed.
Across the 48 breadth/cap/lookback/allocation variants, 91.67% beat the control
recently and 50% improved both recent and full-period CAGR. Modeled peak target
weight for one cash-conversion stock was **4.61%** of total capital.

This is the new provisional return-first research leader, not a live strategy.
It was identified after a large retrospective search, only 42.02% of rolling
26-week windows beat the control, and full-period overlay turnover was 3.22x
capital annually before adding the already-charged internal sleeve turnover.
These limitations require forward confirmation.
