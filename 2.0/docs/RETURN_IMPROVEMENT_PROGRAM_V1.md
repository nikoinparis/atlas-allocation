# Return Improvement Program v1

## Objective

Find a higher-return systematic portfolio without relying on a ticker-specific
Micron rule, partial broad-universe data, lookahead, or another unconstrained
search over the already observed 2023–2026 result. This program is research
only. It cannot enable live trading.

## Current boundary

The broad SEC research gate remains the controlling authority. Until it passes,
the program may freeze specifications, build causal implementations, run unit
and mutation tests, and diagnose already-accounted strategy paths. It may not
calculate broad-universe strategy returns or select a broad-universe winner.

The frozen specification is
`evidence/sec_return_improvement_program_v1/frozen_config.json`. The tournament
guard is `scripts/run_sec_return_improvement_tournament_v1.py`.

## Frozen workstreams

| Workstream | Intended alpha | Main unwanted risk | First rejection |
| --- | --- | --- | --- |
| Residual momentum | Company-specific strength after sector and market effects | Hidden sector beta | No rolling improvement after costs |
| Trend quality | Persistent winners near long-term highs | One-jump or late-cycle winners | Result collapses under delayed signals |
| Quality momentum | Improving growth, cash flow, profitability, and capital allocation | Accounting denominator and missing-feature bias | Feature coverage or adverse-missing case fails |
| Event conditioning | Fundamental momentum confirmed by earnings 8-K or Form 4 evidence | Post-event overreaction and timing leakage | One-week delay or severe-cost case fails |
| Adaptive concentration | More capital when independent signals agree | Single-name and single-sector dominance | Leave-one-issuer or sector ablation fails |
| Confidence-weighted ML | Nonlinear cross-sectional rank combinations | Overfit confidence and regime instability | Purged nested out-of-sample rank evidence is non-positive |
| Holding and exit | Let persistent winners run while reducing churn | Stale holdings and slow exits | Gain disappears after turnover and delay stress |
| Strategy allocator | Diversify across independent return sources | Performance chasing and selected-sleeve dependence | Causal allocator loses to static allocation |

## Evaluation order after authorization

1. Materialize the validated broad price/fundamental/event panel from immutable
   source vintages.
2. Verify decision timestamps, prefix invariance, terminal handling, missing-
   company base/adverse policies, and exact artifact hashes.
3. Run each signal family separately under 50, 100, and 200 bps costs.
4. Apply purged walk-forward ML only to causal features and sector-relative
   future-return labels.
5. Test adaptive breadth and buffered exits only after their underlying signal
   families are fixed.
6. Compare every candidate with the frozen incumbents using rolling windows,
   block bootstraps, signal delays, issuer removals, sector removals, and
   familywise multiple-testing control.
7. Combine only families whose return streams are independently useful. A
   higher retrospective CAGR alone is insufficient.

## Promotion standard

A candidate must improve recent CAGR by at least three percentage points, not
reduce full-period CAGR, outperform in at least 60% of completed rolling
windows, retain at least 95% bootstrap probability of a positive increment,
survive 200-bps costs and missing-company stress, keep one issuer below 35% of
positive-return contribution, and remain above a -30% recent drawdown floor.

Passing these retrospective gates still does not imply expected profitability.
It creates a forward-research candidate, not a live strategy.

## Existing-path allocator diagnostic

The single predeclared causal strength/dependence allocator was tested only on
three already selected dashboard strategies. Over the common eligible window
beginning 2023-07-14, it produced 21.97% CAGR, 1.254 Sharpe, and -16.61% maximum
drawdown after its additional allocation-turnover charge. Static equal weight
produced 40.00% CAGR, 1.852 Sharpe, and -20.40% drawdown. The dynamic allocator
is rejected; it will not receive a post-result parameter rescue. Static equal
weight is an exploratory ceiling only because all three inputs were selected
using the same history.
