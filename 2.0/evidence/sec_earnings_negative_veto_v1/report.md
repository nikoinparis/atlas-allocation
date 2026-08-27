# SEC negative-earnings veto v1

Tested 18 sparse rules that use a recent strongly negative sector-relative
earnings reaction only to veto a stock at an existing quarterly cash-conversion
rebalance. The selected `veto4__q30__max2` path used a four-week event window,
the bottom 30% within each sector, and no more than two vetoes per rebalance.
It made only five substitutions across three issuers.

At realistic 50-bps costs, the selected path produced 105.10% trailing-one-year
CAGR, 2.692 Sharpe, -10.08% drawdown, and 41.05% full CAGR. The frozen control
produced 105.10%, 2.692, -10.08%, and 40.93%. At severe 200-bps costs, both
returned 93.20%. The veto therefore added 0.11 points to full CAGR but no recent
or severe-cost return improvement.

The robustness evidence was weak: event delays returned 105.82%/98.73%, outer
overlay delays returned 98.13%/102.72%, completed rolling-window outperformance
was 49.08%, no neighboring rule improved both horizons, and 4-week/13-week
bootstrap probabilities were only 11.92%/14.20%. Removing GitLab reduced recent
CAGR to 96.44%.

The complete falsification decision was **FAIL**. This veto family is rejected,
the frozen leader remains unchanged, and no promotion, forward clock, or live
execution was enabled.
