# Refined State Definitions — neutral_soft_landing (Step 2C)

## Raw weekly definitions

| Label | Definition |
| --- | --- |
| A | NM + macro_slowdown |
| B | NM + macro_slowdown + FC_benign |
| C | NM + macro_slowdown + credit_not_worsening |
| D | NM + macro_slowdown + FC_benign + credit_not_worsening (= Step2B Signal E) |
| E | NM + macro_slowdown + FC_benign + credit_improving (strict credit gate) |

## Smoothed variants

| Suffix | Method |
| --- | --- |
| _raw | Weekly binary (no smoothing) |
| _2wk | Rolling 2-week mean ≥ 0.5 (active ≥1 of last 2 weeks) |
| _4wk | Rolling 4-week mean ≥ 0.5 (active ≥2 of last 4 weeks) |
| _monthly | Frozen monthly: determined at month start using prior 4-week lookback, threshold ≥ 0.5 |
| _quarterly | Frozen quarterly: determined at quarter start using prior 8-week lookback, threshold ≥ 37.5% |

## Notes
- All signals are 1-week causally lagged (fc_proxy and credit already lagged in data load).
- Frozen monthly/quarterly use prior-data-only lookback (no look-ahead).
- These labels are NOT trading triggers. They are regime calibration candidates.