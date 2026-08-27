# Indonesia Dynamic Breadth Challenger V1

> **RESEARCH ONLY — architecture-inspired Indonesian challenger; not the US Dynamic Breadth-20 strategy, not an investment recommendation, and not approved for execution.**

## Verdict: HISTORICAL_CHALLENGER_FAIL

This is a separately registered Indonesian architecture translation. The stock
ranking and sizing rules are identical to the baseline; only total stock versus
cash allocation changes with causal IDX80 breadth.

| Series | CAGR | Cumulative return | Sharpe (0% RF) | Maximum drawdown |
|---|---:|---:|---:|---:|
| Baseline, net 50 bps one-way | 2.40% | 18.52% | 0.22 | -46.00% |
| Breadth challenger, net 50 bps one-way | 1.35% | 10.04% | 0.17 | -22.63% |
| Breadth challenger, net 150 bps one-way | -2.88% | -18.87% | -0.16 | -30.41% |

The run contains 91 monthly decisions from
2019-02-04 through 2026-08-21. Breadth states:
{"broad": 21, "insufficient_breadth": 2, "mixed": 37, "weak": 31}.

## Predeclared gate results

{
  "cagr_at_least_baseline_at_base_cost": false,
  "complete_inactive_security_and_delisting_history": false,
  "licensed_total_return_benchmarks": false,
  "maximum_drawdown_at_least_5pp_better_than_baseline": true,
  "minimum_monthly_decisions": true,
  "no_single_calendar_year_dependency": false,
  "positive_cagr_at_150bps": false,
  "sharpe_above_baseline_at_base_cost": false,
  "untouched_forward_observations": false,
  "validated_local_cost_model": false
}

## Interpretation boundary

- This is not the US Dynamic Breadth-20 strategy.
- Historical prices are vendor-revised research data and benchmarks remain price-only.
- Costs, suspension exits, delistings, and total-return benchmarks remain incomplete.
- No historical result can authorize execution or commercialization.
