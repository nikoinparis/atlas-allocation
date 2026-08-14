# Evidence

## Research laboratory Batch 01

`research_lab_batch_01/` contains the complete 288-experiment registry,
leaderboard, chronological walk-forward returns, machine-readable result, and
human-readable report. It compares eight momentum/trend signal recipes, three
smoothing windows, three portfolio sizes, and four allocation methods using the
same immutable free-data snapshot and bias-aware accounting rules.

This is retrospective research evidence, not an untouched forward result. The
exact v4 benchmark reconciles to the previously rebuilt free-snapshot pipeline.

## Robustness Batch 02

`robustness_batch_02/` contains predeclared parameter-neighborhood, 10–100 bps
cost, and point-in-time SPY-regime tests for every saved provisional strategy.
All ten passed these initial retrospective gates. The label is intentionally
`provisional_robust`: multiple-testing, ensemble interaction, survivorship-safe
history, and 52 untouched forward weeks remain outstanding.

## Ensemble and Dependence Batch 03

`ensemble_dependence_batch_03/` measures pairwise return correlation, holdings
overlap, correlation clusters, marginal contribution, and netted target-weight
ensembles across the ten provisional candidates. It also applies a 25,000-
sample, 13-week circular block-bootstrap test with Bonferroni adjustment for the
original 288-experiment search.

The candidates pass that specific zero-mean multiple-testing diagnostic, but
they provide only about 1.15 effective independent return streams and form one
connected 0.90-correlation cluster. This is evidence for a shared
trend/momentum family, not ten separate alphas.

## New Strategy Families Batch 04

`new_families_batch_04/` contains 288 standardized experiments across mean
reversion, defensive selection, and a trailing-distribution-yield carry proxy.
It saves one development-selected leader per family, later-period and 50 bps
results, correlation to frozen v4, and netted multi-family diagnostics.

The defensive and carry leaders are provisional new-family candidates. Mean
reversion is retained as provisional fragile because its full drawdown reached
-45.3% and weekly turnover exceeded 12 times capital annually. Carry is strictly
research-only because distribution event history came from one current Yahoo
vintage rather than an archived point-in-time feed.

## New-Family Robustness Batch 05

`new_family_robustness_batch_05/` tests all three Batch 04 family leaders over
nine nearby parameter choices, costs through 100 bps, three causally defined
market regimes, and a 50,000-sample block-bootstrap correction for all 576
strategies searched in Batches 01 and 04.

Only the defensive leader passed every declared gate. Carry passed its
neighborhood, regime, and 100 bps tests but failed the search-wide statistical
hurdle; it also retains its point-in-time distribution-data limitation. Mean
reversion failed both the 100 bps and multiple-testing gates. The surviving
50/50 trend/defensive diagnostic improved retrospective Sharpe from 0.754 to
0.860 and drawdown from -26.25% to -24.29%, while lowering annual return from
9.91% to 8.64%. It is not a promoted or untouched portfolio.

## Covariance-Aware Portfolios Batch 06

`covariance_portfolios_batch_06/` combines only frozen trend v4 and the Batch 05
robust defensive sleeve. Six primary allocation rules use monthly decisions,
104 trailing weeks, 25% diagonal covariance shrinkage, an 80% sleeve cap, a 35%
underlying-asset cap, explicit residual cash, and netted combined turnover.
Forty-five additional configurations vary lookback and shrinkage without using
the best one as the reported primary setting.

Minimum variance won the predeclared 2006–2015 development selection. Its full
retrospective result was 7.83% annual return, 0.901 Sharpe, and -23.39% drawdown;
at 50 bps it retained 6.58%, 0.769, and -23.50%. All of its sensitivity variants
were positive in both later periods. HRP's full-history Sharpe was marginally
higher at 0.903, but choosing it from that full-history result would be
hindsight. Maximum diversification and inverse volatility produced identical
primary returns, as expected with two sleeves. Nothing in this batch is final.

## Portfolio Robustness Batch 07

`portfolio_robustness_batch_07/` audits the development-selected minimum-
variance portfolio at 50 bps. It contains 20 rolling three-year windows, a
20,000-sample 13-week circular block bootstrap, covariance delays through 13
weeks, rounded inputs, deterministic ±5 bps synthetic revisions, 10% missing
estimator observations, and malformed-covariance fallback tests.

All declared gates passed. Every rolling window had a positive return; the
bootstrap 95% intervals were 3.09%–9.96% for annual return and 0.361–1.231 for
Sharpe, while the adverse drawdown bound was -35.31%. The selected portfolio's
bootstrapped annual volatility was 1.12–1.82 percentage points lower than equal
weight. Because only one real free-data vintage exists, synthetic revision
tests do not satisfy the multi-vintage gate.

The rules are frozen as `covariance_minimum_variance_v1`, but the candidate is
not final or approved for trading. Its first eligible untouched decision date
is 2026-08-14 and its recorded untouched observation count is zero.

## Frozen Portfolio Forward Evidence

`forward_covariance_minimum_variance_v1/` contains the pre-freeze August 7
turnover anchor, current clock status, and the future append-only decision and
observation chains. The existing snapshot is too early for the August 14 first
decision boundary, so no decision or return was appended during initialization.

The decision chain must capture a target from a snapshot observed between 21:00
UTC on its Friday and 21:00 UTC the following Friday. A separate realization
chain later attaches the following week's return to that exact decision hash.
Duplicate, out-of-order, pre-freeze, changed, or hash-invalid records are
rejected. Missing windows cannot be filled from a later vintage. The current
truth remains 0/52 weeks, with no performance claim and no execution path.

## Guarded Weekly Forward Cycles

`weekly_forward_cycles/` stores one immutable result directory per successful
weekly acquisition. The cycle fails closed before the Friday 21:00 UTC cutoff,
under concurrent execution, on duplicate weekly runs, failed data freshness,
crossed timing boundaries, recorder rejection, or any backward clock movement.

The first completed cycle created snapshot
`20260809T002313Z-0d8632e2cf759918` for the pre-freeze August 7 week and passed
that exact ID to the recorder. It correctly appended zero forward decisions and
zero observations. Of 209,568 common price rows, 151,125 adjusted closes differed
at machine-scale tolerance, but no raw close changed, the largest relative
adjusted difference was 0.000226%, and zero rows exceeded the 0.01% materiality
threshold. The clock remains 0/52.

This directory contains immutable or reproducible evidence produced by catalog
reviews and experiments. Evidence is separated by review batch and linked from
the master research registry.

## Batch 1: backtest, execution, and simulation systems

- `batch_01_backtest_execution/source_health.csv` — normalized evidence for all 41 repositories
- `batch_01_backtest_execution/github_metadata.json` — raw GitHub metadata snapshot
- `batch_01_backtest_execution/license_resolution.json` — nonstandard-license review results
- `batch_01_backtest_execution/license_snapshots/` — exact reviewed license texts
- `batch_01_backtest_execution/report.md` — readable screening report
- `batch_01_backtest_execution/summary.json` — machine-readable totals
- `batch_01_backtest_execution/smoke_test_queue.csv` — pinned execution queue and blockers
- `batch_01_backtest_execution/isolation_runtime.json` — local isolation-runtime check
- `batch_01_backtest_execution/source_smoke/` — pinned source-acquisition evidence
- `batch_01_backtest_execution/python_execution/` — disposable install and offline test evidence
- `batch_01_backtest_execution/execution_report.md` — readable execution findings and decisions
- `batch_01_backtest_execution/behavioral_probes/` — canonical bt and FlashAlpha probe evidence
- `hftbacktest_behavioral/` — platform-owned execution, accounting, and unsafe-boundary probes
- `hftbacktest_recorded_replay/` — pinned recorded BTCUSDT order-book chronology replay
- `strategy_scoreboard/` — bias-aware metrics, reconciliation, uncertainty, and forward-validation lock for 33 strategies
- `strategy_rebuild_trend_quality/` — independent five-signal lag audit, explicit-cash portfolio rebuild, cost stress, and comparison evidence
- `strategy_raw_formula_rebuild/` — full reconstruction of five formulas and 31 intermediate columns from weekly market inputs
- `data_vintage_store/` — immutable legacy snapshot registration, integrity evidence, and strict historical/production rejection gates
- `free_data_acquisition/` — isolated zero-cost ETF pulls, freshness validation, and cross-vintage revision monitoring
- `free_snapshot_research_pipeline/` — completed-week preparation, five-signal simulation extension, revision audit, and inactive paper target

Repository-health scores are triage signals only. They do not represent code
quality, strategy validity, security certification, or expected profitability.
