# Upgrade Execution and Strategy Audit V2

Date: 2026-08-24

## Bottom line

The implementation process is unusually rigorous, but no strategy is ready for real
money. The current registry contains 24 strategy candidates and one portfolio
candidate; none is final or approved for live trading. The longest valid forward clock
contains one observed week out of 52. That is operational evidence, not evidence of a
survivable edge.

The V1 reports were accurate when written but became stale in two places: genuine
cross-sectional value was later completed and rejected, and an Indonesia/IDX80
international-equity program was later attempted. No attached instruction was treated
as proof; every claim below was reconciled against code, registry state, and saved
evidence.

## Strategy-family implementation audit

| Family | Implementation assessment | Economic/readiness verdict |
| --- | --- | --- |
| Trend/momentum and GGG variants | Frozen formulas reproduce to machine precision; causal repairs, prefix-invariance checks, costs, delays, and multiple-testing controls exist. The family is highly redundant. | Research-only. Batch 03 measured 0.84-0.98 correlations and about 1.15 effective strategies; later return leaders remain selection-contaminated or forward-incomplete. |
| Defensive | Correctly lagged and the only new ETF family to pass its 576-trial corrected historical gate. | Provisional only; lacks a survivorship-safe historical universe and 52 untouched weeks. |
| Mean reversion and carry proxy | Corrected implementations and realistic cost tests exist. | Mean reversion is fragile; carry did not beat its null. Drop as alpha candidates. |
| Cross-sectional ETF ML | Purged, embargoed, nested walk-forward implementation with label-shuffle and random-feature controls is sound. | Rejected: lost to the frozen portfolio or collapsed under costs/full-universe expansion. |
| Technical indicator repositories | Third-party bugs were independently found and corrected before economic testing. | Corrected variants still failed costs or drawdown gates. Drop. |
| SEC cash conversion | Point-in-time filings, historical filer universe, missing/delisted policies, issuer leave-one-out, exact daily reconstruction, and broad real tournament are implemented. | Strongest diversified historical research finding, but not promoted; recent leaders are regime/selection contaminated and forward evidence is insufficient. |
| SEC value and valuation | Point-in-time split-normalized valuation and broad-universe falsification were completed after the V1 upgrade list. | Rejected across liquidity, breadth, costs, timing, and concentration tests. |
| SEC overlays, leverage, and sizing | Insider, earnings, valuation, dispersion, cluster, residual, inverse-volatility, covariance/rank sizing, caps, fractional Kelly, and leverage tournaments were implemented. | No tested family qualified after dependence/multiplicity gates. The 22-candidate exposure and 96-candidate mathematics tournaments had zero passers. |
| International/Indonesia | Official IDX80 history, inactive-price supplements, local fundamentals, causal decisions, and several challenger versions exist. | Rejected or inconclusive/data-gated. Missing complete inactive/delisted history, licensed total-return benchmarks, validated local costs, and forward observations. |
| Options and futures | Platform data/risk contracts now model futures identity, rolls, fees and margin; option quote, exercise style, Greeks, margin, assignment fees, tail budget, and scenario gates are implemented. | Performance not run. Required point-in-time chains, surfaces, execution, margin, and roll histories are absent. |

## Upgrade dispositions

1. **Standing breadth governance - implemented.** New candidates must provide aligned
   returns and holdings overlap against every surviving incumbent. The output includes
   pairwise correlations, effective breadth, marginal contribution, and an optional
   IC/IR/transfer-coefficient decomposition. A marginal contribution rounding below
   0.01 rejects the candidate as a new independent source. This gate cannot promote a
   strategy.

2. **New asset classes - partly attempted, otherwise data-blocked.** Indonesia supplied
   a genuinely new market but no accepted strategy. Futures trend now has a fail-closed
   implementation contract, but no trustworthy dataset exists for a backtest.

3. **Volatility risk premium - implementation contract only.** Hull 11e sections
   10.6-10.8, 19.6, 19.8, 19.10-19.11, and 20.5 were checked directly. They confirm that
   spread and exercise/assignment costs, short-option margin, gamma/vega, scenario
   analysis, and a volatility surface are required. A naive end-of-day short-put test
   would therefore be invalid and was not run.

4. **Cross-sectional value - already completed and rejected.** Project History steps
   118-123 document the completed pipeline and falsification sequence.

5. **Kelly/risk-budgeted sizing - already tested and rejected.** Quarter-Kelly reduced
   risk and return without creating edge. Later issuer/sector caps, inverse-volatility,
   covariance/rank, and exposure tournaments produced zero historical gate passers.

6. **True meta-labeling - implemented and rejected before return testing.** The secondary
   model predicted whether the fixed primary ETF model's direction was correct; it did
   not retrain direction or optimize return. Out-of-sample precision moved from 52.37%
   to 52.67%, F1 fell from 0.687 to 0.680, and the shuffled-label control achieved 53.20%
   precision. The classification gate failed, so portfolio pass-through stayed blocked.

7. **Formal Markov regime scaling - implemented and rejected.** A two-state Gaussian
   hidden Markov model was fit only on 2005-2015 observations. Each period's exposure
   used state probability through the prior period. At 50 bps, locked-period maximum
   drawdown improved by 7.53 percentage points, but annual return fell by 3.14 points,
   exceeding the predeclared one-point tolerance.

## What can and cannot be concluded

The code is suitable for continued research and paper/forward observation. The saved
evidence supports claims about causality checks, accounting, falsification, and negative
results. It does not support a claim that any strategy will survive live trading.

Real-world authorization remains blocked by untouched forward time, market-impact and
capacity evidence, broker-specific execution/margin behavior, residual missing/delisted
data risk, cross-market replication, and the fact that the strongest recent results were
selected from the same 2023-2026 regime used to describe them.
