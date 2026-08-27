# Portfolio Optimizer: End-to-End Project History

Last updated: 2026-08-16

This is the living reference for the project from its original 1.0 research
stack through the current 2.0 repository-evaluation platform. Update it whenever
a repository, component, dataset, strategy, or promotion gate is tested.

## Current truth at a glance

- Version 1.0 is a completed ETF research application with data, signals,
  strategy sleeves, risk/regime logic, portfolio construction, validation
  artifacts, and a Next.js dashboard.
- Version 2.0 is the safety-first rebuild for evaluating every entry in
  `awesome-systematic-trading` and selectively adopting only validated ideas.
- Catalog entries inventoried: **344/344**.
- First review batch screened: **41/41** backtest/execution/simulation entries.
- Pinned source acquisitions: **18/18** succeeded.
- Repositories whose code has genuinely executed: **13**.
- Repositories passing a scoped bundled/offline gate: **7**.
- Historical component replays: **2** (`bt`, FlashAlpha).
- Recorded market-data component tests: **2** (TradingView fixture and
  hftbacktest order-book replay).
- Saved Layer 2 strategies scored: **33/33**; 28 return series reconcile, 5 fail.
- Standardized 2.0 strategy configurations searched: **576** across trend,
  momentum, mean-reversion, defensive, and carry-proxy families.
- Canonical candidates tracked: **13**, all non-final; one new-family leader
  passed Batch 05's complete retrospective robustness gate.
- Portfolio candidates tracked: **1**, frozen for forward observation and
  non-final, with **0/52** untouched weeks recorded.
- Genuine immutable free-data vintages: **2**; the first cross-vintage audit
  found no economically material price revision at a 0.01% threshold.
- Current evidence grades: **2 B, 26 C, 5 D, 0 A**.
- Repositories or strategies proven durably profitable: **0**.
- Live brokerage or real-money trading approval: **none**.

Passing a software test means only that the tested behavior worked. It never
means a strategy is profitable, safe in every market, or ready for real money.

## Step 1 — Build the original 1.0 research stack

The first application was built as a layered ETF quantitative-research system.
Its five primary notebooks created:

1. a market-data hub and research calendar;
2. Layer 1 alpha-signal research;
3. Layer 2 strategy sleeves;
4. Layer 2B risk and causal market-state logic; and
5. Layer 3 portfolio construction and allocator comparison.

The data hub contains daily and weekly ETF/benchmark prices and returns,
universe metadata, macro inputs, VIX-term-structure inputs, provenance
snapshots, and data-quality reports. It is a saved research pipeline, not yet
an always-on automatic data service.

Layer 1 evaluated momentum, trend, moving-average, breadth, dollar-strength,
carry, reversal, value, cross-asset, and quality features. The saved signal
summary contains 22 primary signal rows plus many later experimental artifacts.

Layer 2 compared 24 baseline and strategy rows, including 60/40 and market
benchmarks, momentum/trend sleeves, tactical allocation, and regime-conditioned
composites. Layer 2B created causal lagged states such as stressed, recovering,
neutral, and calm conditions.

Layer 3 tested allocator families and overlays. HRP became the base allocator,
with market-state, target-risk, and fragility controls added through later
research phases. The saved 1.0 production candidate is
`improved_frontier_phase5_fragility_guard`, reporting 7.13% annualized return,
0.948 Sharpe, and -11.60% maximum drawdown over its recorded full research
window. These are historical research statistics, not a forward guarantee.

The 1.0 dashboard packages saved artifacts into a Next.js interface. It does
not recompute research, operate a broker, or automatically place orders.

Primary references:

- `../1.0/README.md`
- `../1.0/docs/research/final_resume_ready_project_summary.md`
- `../1.0/data/05_layer3_portfolio_construction/production_candidate_summary.csv`

## Step 2 — Preserve 1.0 and begin 2.0

The existing application was preserved in `1.0/`. A separate `2.0/` directory
was created so repository experiments could not silently alter the original
research stack.

Version 2.0 adopted these rules:

- examine every catalog entry rather than discarding ideas by reputation;
- do not install all projects into one shared environment;
- pin the reviewed catalog, repository commit, dependencies, and data fixture;
- isolate third-party code from the host and from canonical portfolio state;
- test simple behavior and baselines before complex strategies;
- preserve failures and inconclusive outcomes;
- require holdout, benchmark, cost, and adverse-condition evidence before
  strategy promotion; and
- keep live brokerage execution outside the initial scope.

Architecture reference: `docs/architecture.md`.

## Step 3 — Configure the isolated Podman laboratory

Rootless Podman was configured as the repository-testing environment. Each
candidate is restored in a disposable named volume. Dependency acquisition may
use the network; deterministic test/replay phases disable networking, avoid
host-directory mounts, drop privileges/capabilities, and apply resource limits.

Recorded runtime profiles currently cover the Python, Node.js, and Rust
toolchains required by the tested candidates, including Rust 1.55, 1.85, and
1.91.1 compatibility profiles.

References:

- `config/sandbox_policy.json`
- `config/runtime_profiles.json`
- `evidence/runtime_profiles.md`

## Step 4 — Inventory the complete source catalog

The `awesome-systematic-trading` source was pinned at catalog commit
`b4d8ec3d47813de0e87ab9151c23cb0192b9e26d`. Every linked catalog bullet was
normalized into `research_registry/registry.csv`.

Coverage is **344 entries across nine batches**:

1. backtest, execution, and simulation — 41;
2. data and storage — 42;
3. portfolio, risk, and analytics — 17;
4. signals and strategies — 22;
5. broker and venue interfaces — 8;
6. AI, ML, and automation — 28;
7. crypto, DeFi, and prediction markets — 69;
8. infrastructure, libraries, and visualization — 88; and
9. education, research, and industry resources — 29.

Duplicates remain traceable; books, blogs, commercial pages, and unavailable
projects receive documented reviews even when code cannot be executed.

References: `research_registry/README.md`, `research_registry/review_batches.md`.

## Step 5 — Screen all 41 Batch 1 repositories

All 41 backtest/execution/simulation listings received current repository,
maintenance, license, language, data-requirement, and installation-complexity
screening.

- 18 advanced to isolated source acquisition;
- 15 required manual review before sandboxing; and
- 8 remained reference-only at this gate.

This was triage, not a code audit or profitability test. All 18 selected pinned
commits were then acquired and structurally verified successfully without
executing repository code.

Reference: `evidence/batch_01_backtest_execution/report.md`.

## Step 6 — Execute nine Python repositories

Nine candidates were installed in disposable environments and tested offline:

| Repository | Outcome | Interpretation |
|---|---|---|
| `bt` | 188 tests passed | Advanced to behavioral and historical gates |
| FlashAlpha fill simulator | 63 passed, 1 skipped, 1 expected failure | Advanced only behind quote/output guards |
| Cipher | 66 passed | Candidate for later interface evaluation |
| finmarketpy | 5 passed | Review individual ideas; dependency surface is large |
| Investing Algorithm Framework | Collection failed | Duplicate SQLAlchemy table metadata |
| qf-lib | Collection failed | Undeclared `jwt` dependency |
| zvt | 57 passed, then offline failure | A test attempted a live exchange request |
| vn.py | Dependency failure | Pinned PySide6 unavailable for Linux ARM64 |
| PythonTradingFramework | Packaging failure | Multiple undeclared top-level packages |

Failures were recorded, not discarded. A failure at one packaging or dependency
gate does not invalidate every idea in that repository.

Reference: `evidence/batch_01_backtest_execution/execution_report.md`.

## Step 7 — Create the platform-owned execution oracle

Version 2.0 implemented canonical contracts for buying power, position limits,
order states, partial fills, overfill/duplicate-fill prevention, fees, cash,
positions, equity, next-bar execution, slippage, and invalid/crossed/non-finite
quotes.

Third-party components may propose or calculate behavior, but they cannot own
canonical cash, portfolio state, or risk approval.

References:

- `src/systematic_trader/execution.py`
- `tests/test_reference_execution.py`

## Step 8 — Probe and guard `bt` and FlashAlpha

`bt` correctly applied commissions and recorded transactions, but raw behavior
allowed a signal from a closing bar to transact on that same close. The adapter
therefore requires platform-owned signal lagging and canonical execution.

FlashAlpha correctly handled ordinary crosses/non-crosses and wide/crossed
quotes, but its raw model accepted a NaN leg and emitted non-finite diagnostics.
The guarded adapter rejects non-finite input and output.

Neither component was approved as an autonomous engine.

Reference: `evidence/batch_01_backtest_execution/behavioral_probes/report.md`.

## Step 9 — Run the first historical component replays

`bt` replayed a fixed monthly SPY/TLT/GLD momentum/trend example on 5,101 real
adjusted-close rows from 2006-01-03 through 2026-04-14. Signals were lagged and
commissions were stressed. The example failed the SPY benchmark overall and on
the 2021–2026 holdout, so the component was retained but the strategy was not
promoted.

FlashAlpha replayed 11 fixed SPY put-credit-spread limits against its recorded
29-bar sample for 2024-06-03. Seven filled under defaults and zero filled under
stricter assumptions, showing strong sensitivity. One day is insufficient for
P&L or fill-probability estimation.

Reference: `evidence/historical_validation/report.md`.

## Step 10 — Execute four non-Python repositories

| Repository | Outcome | Interpretation |
|---|---|---|
| TradingView Screener API | 142 Node tests passed | Screening/data adapter candidate only |
| QUANTAXIS Rust package | Dependency reproduction failed | Keep for source-level idea review |
| Barter instrument core | 15 Rust tests passed | Instrument/identity candidate only |
| hftbacktest core | 22 Rust tests passed | Advanced to execution-model probes |

The TradingView adapter was also tested against a recorded America-scan
response with strict schema, timestamp, finite-value, and freshness guards. It
is useful for current screening but is not point-in-time historical data and is
not a strategy.

References:

- `evidence/non_python_execution/report.md`
- `evidence/tradingview_adapter/report.md`

## Step 11 — Probe hftbacktest execution and accounting

At pinned commit `5f3ec40b2afb764e0fea112f941ed85523ef4e88`, eight platform tests passed.
Six confirmed latency/rejection ordering, monotonic order-bus time, conservative
queue behavior, partial-fill reconciliation, cancellation-before-trade behavior,
and fee/cash/position/equity reconciliation.

Two tests deliberately exposed unsafe library boundaries: the direct state API
accepts an overfill, and non-finite fee configuration can propagate NaN. The
component therefore remains behind finite-value, order-state, remaining-quantity,
accounting, and visible-depth guards.

Reference: `evidence/hftbacktest_behavioral/report.md`.

## Step 12 — Replay pinned recorded order-book events through hftbacktest

The pinned repository documentation contains a real BTCUSDT Binance Futures
excerpt. Twenty-three original rows (19 depth updates and 4 trades) were saved
with exact provenance and SHA-256.

The fixture contains one documented exchange/local timestamp inversion. The
platform detected it and split the dual chronology into 42 engine events without
changing prices, quantities, or timestamps. The offline replay reconstructed a
22,183.4 × 0.014 best bid and 22,194.3 × 0.270 best ask, retained all four
trades, accepted a 0.1 visible-depth-bounded hypothetical size, rejected a 0.5
oversized proposal, and produced no accidental fills.

This passes the small recorded-data ingestion/chronology gate. It does not test
profit because the excerpt lacks a full initial snapshot, a continuous session,
and a meaningful order schedule.

Reference: `evidence/hftbacktest_recorded_replay/report.md`.

## Step 13 — Build the bias-aware strategy scoreboard

All 33 saved Layer 2 return/position pairs from 1.0 were evaluated through a
platform-owned metrics engine. The engine reports total and annual return,
volatility, zero-risk-free Sharpe, Sortino, maximum drawdown and duration,
Calmar, weekly CVaR, SPY beta/alpha, information ratio, rolling three-year
behavior, turnover-cost stress at 10/25/50 bps, and deterministic 13-week block
bootstrap confidence intervals.

The accounting layer independently recomputed each strategy's gross return from
its dated positions and the following week's ETF returns. This also resolved a
potential labeling trap: saved returns use the decision date even though the
return is realized one week later. The scoreboard uses the realization date.

- 28/33 saved return series reconcile to machine precision.
- 5/33 fail reconciliation and receive Grade D regardless of performance.
- All 33 saved fee calculations reconcile to their recorded 10 bps turnover cost.
- Only two rows receive Grade B; 26 receive C and five receive D.
- No strategy receives A or promotion because the historical sample was already
  available during research and signal generation has not yet been independently
  re-executed from point-in-time inputs.

The strongest non-benchmark Grade B candidate is
`composite_selective_strength_weighted`: 7.03% annual return, 0.739 Sharpe,
-20.16% maximum drawdown, 7.96% annual return and 0.918 Sharpe since 2021,
and 6.17% annual return under the 50 bps turnover stress. SPY returned 10.54%
annually with 0.660 Sharpe but a much deeper -54.61% drawdown.

`composite_trend_quality_refined` is the clearest repair candidate. Its 10.59%
headline annual return narrowly exceeds SPY and its Sharpe is 0.800, but it
remains Grade C because it holds nonzero exposures during 33 weeks with missing
asset returns.

Additional bias findings include current-universe survivorship risk, repeated
search across 33 strategies, implicit free rebalancing in fixed multi-asset
baselines, unmodeled short borrow/financing, and missing primary manifest entries.

A forward validation protocol now freezes the exact strategy artifact set. The
first genuinely untouched weekly endpoint is 2026-08-14. At least 52 untouched
weeks are required before promotion; changing parameters or logic creates a new
candidate version and restarts its forward record.

References:

- `evidence/strategy_scoreboard/report.md`
- `evidence/strategy_scoreboard/strategy_scoreboard.csv`
- `evidence/strategy_scoreboard/strategy_scoreboard.json`
- `evidence/strategy_scoreboard/validation_protocol.json`

## Step 14 — Independently rebuild the trend-quality repair candidate

The portfolio logic for `composite_trend_quality_refined` was re-executed in
platform-owned, dependency-free code from its five dated tradable signal files.
The rebuild independently verifies that every tradable signal equals the prior
week's observed signal, averages the available signals, applies the original
four-week smoothing, selects up to four ETFs above 0.05, rebalances monthly,
and realizes returns only over the following week.

The old artifact's 33 missing-return weeks were all defensive BIL positions
before BIL had a recorded decision-date price. The rebuilt candidate records
that allocation explicitly as zero-yield `cash::USD`; BIL is eligible only
after its price is observable. The rebuilt path has zero nonzero unpriced
exposures, fully invested weights, and exact turnover-cost reconciliation.

The audit also found material lineage drift: the current dated signal files do
not reproduce the older saved positions on 203 weekly rows spanning 47
rebalance dates. The old 10.59% annual-return headline is therefore shown for
comparison but is not treated as independently validated. The separately
versioned rebuilt candidate is now the result of record:

- 9.97% annual return, 0.756 Sharpe, and -26.25% maximum drawdown;
- 14.17% annual return and 1.055 Sharpe since 2021;
- 9.13% annual return and 0.701 Sharpe at 50 bps per unit turnover;
- 95% block-bootstrap intervals of 4.99% to 15.14% for annual return and
  0.399 to 1.159 for Sharpe; and
- only 22.75% of rolling three-year windows beat SPY on cumulative return.

The candidate receives the internal label **B-rebuilt, research only**. It is
not promoted: the signal formulas have not yet been independently re-derived
from raw point-in-time vendor data, the universe was already researched, and
the full history is not untouched. The locked forward test still begins on
2026-08-14 and requires at least 52 weeks.

References:

- `evidence/strategy_rebuild_trend_quality/report.md`
- `evidence/strategy_rebuild_trend_quality/result.json`
- `evidence/strategy_rebuild_trend_quality/positions.csv`
- `evidence/strategy_rebuild_trend_quality/returns.csv`

## Step 15 — Re-derive all five signals from weekly market inputs

All five signals used by the rebuilt trend-quality strategy were independently
implemented in platform-owned, standard-library code from `weekly_prices.csv`
and `weekly_returns.csv`. The reconstruction covers the complete 35-ETF input
universe rather than only the 14 assets eligible for final portfolio selection.

The exact reconstructed logic includes 52-to-4-week momentum, 26-week sample
volatility, inverse-volatility momentum blending with a 1% volatility floor,
5th/95th-percentile cross-sectional winsorization, average ranks normalized to
[-1, +1], 52-week log-price trend R-squared, and 13/52-week moving averages.
Every tradable signal is shifted by one complete week.

The audit compared 31 raw, intermediate, observed-score, and tradable-score
columns against the saved signal artifacts:

- 1,113,560 numeric values compared;
- zero errors above 1e-10;
- zero missing-value mismatches; and
- maximum absolute floating-point difference of 8.64e-12.

A future-data truncation test also verifies that historical signal values do
not change when later rows are removed. The independently calculated signal
panels produce the same candidate-of-record portfolio as Step 14: 9.97% annual
return, 0.756 Sharpe, and -26.25% maximum drawdown, with no unpriced exposure
and exact fee accounting.

This narrows the unexplained 203-week difference to the older saved portfolio
artifact rather than the current signal files. The older 10.59% result remains
comparison-only. The new internal label is **B-raw-rebuilt, research only**.
It is still not promoted because the weekly source files are not vintage-by-
vintage vendor snapshots, the ETF universe was already selected, and the
historical period was already visible during research.

References:

- `evidence/strategy_raw_formula_rebuild/report.md`
- `evidence/strategy_raw_formula_rebuild/result.json`
- `evidence/strategy_raw_formula_rebuild/positions.csv`
- `evidence/strategy_raw_formula_rebuild/returns.csv`

## Step 16 — Introduce immutable, point-in-time data vintages

A platform-owned market-data store now creates immutable content-addressed
snapshots, records SHA-256 and byte-length provenance for every payload, checks
integrity before reads, and refuses snapshots learned after a simulated decision
time. Provider claims for point-in-time prices, historical universe membership,
permanent IDs, corporate actions, delistings, and retained revisions are
separate mandatory gates rather than assumptions inferred from long price
history.

The existing 1.0 Yahoo/yfinance data hub was registered as snapshot
`20260415T081954Z-5c0effb962d04b1e`. Its observed-at timestamp is the
conservative maximum timestamp in the companion April 2026 Yahoo metadata pull.
The snapshot preserves exact source files plus derived research-only identity,
current-universe, distribution, and empty-delisting tables.

All six production claims are false. The store successfully rejects both a
2005 as-of request, because the export was not known then, and a 2026 request
that requires point-in-time membership and delisting coverage. This is a
deliberate correction: earlier backtests remain useful research evidence but
cannot use this snapshot to pass a strict historical-data gate.

A vendor-neutral ingestion command and normalized five-table descriptor are now
ready for real exports. Official source review indicates that Norgate US Stocks
Platinum/Diamond is the practical individual-user candidate with delisted-stock
and historical-index-constituent coverage. CRSP remains the preferred
institutional/academic path because permanent PERMNO identity, distributions,
and delisting returns are explicit. No paid source has been acquired, and no
claim is accepted until an actual export passes the ingestion and coverage
tests.

References:

- `evidence/data_vintage_store/report.md`
- `evidence/data_vintage_store/result.json`
- `docs/data_vintage_protocol.md`
- `config/data_snapshot_descriptor.example.json`

## Step 17 — Add isolated, zero-cost ETF acquisition

Paid CRSP/Norgate work is explicitly deferred. A free Yahoo/yfinance acquisition
path now runs inside a rootless Podman container with no host filesystem mount.
The yfinance 1.5.2 environment and all 21 transitive dependencies are pinned in
`config/free_data_requirements.lock`; normalized files leave the container only
through `podman cp` and then pass the platform-owned vintage-store validator.

The first live free pull completed for all 35 configured ETFs:

- 209,568 daily price rows;
- 3,812 observed distribution, split, or capital-gain rows;
- zero failed symbols;
- latest market date 2026-08-07;
- maximum calendar staleness one day; and
- immutable snapshot `20260808T212827Z-de103c2e063d6c4a`.

This is the baseline free-provider vintage. Future pulls automatically compare
common rows for adjusted-price or close revisions and count new and disappeared
rows. A run is rejected before ingestion if any configured ETF is missing or
more than seven calendar days stale.

All production historical-data claims remain false. The snapshot is appropriate
for current ETF research, forward paper-data collection, and revision monitoring,
but not for survivorship-safe historical membership or delisted-security claims.
No paid data, host Python installation, or real-money trading path was added.

References:

- `evidence/free_data_acquisition/report.md`
- `evidence/free_data_acquisition/latest_result.json`
- `scripts/acquire_free_etf_snapshot.py`
- `config/images/yfinance-1.5.2.Containerfile`
- `config/free_data_requirements.lock`

## Step 18 — Connect the free snapshot to signals, simulation, and paper output

The first immutable free snapshot now flows through a platform-owned daily-to-
weekly preparation layer. Daily adjusted prices are assigned to completed
Friday weeks using the last available trading observation, weekly log returns
require consecutive valid prices, and the resulting derived files are hashed
and tied to source snapshot `20260808T212827Z-de103c2e063d6c4a`.

All five raw signal formulas were recalculated from the prepared weekly data,
then the four-week composite, top-four selection, explicit cash/BIL rule,
monthly schedule, next-week return realization, and turnover costs were rerun
through 2026-08-07.

The extended research result is 9.91% annual return, 0.754 Sharpe, and -26.25%
maximum drawdown. Since 2021 it reports 13.68% annual return and 1.030 Sharpe.
The April 17-August 7 retrospective extension returned 1.97%, but it is
explicitly not an untouched holdout because it was observable when v4 was
created. The 50 bps cost-stress annual return is 9.07%.

The new Yahoo pull changed 31,841 of 37,485 common adjusted-price cells relative
to the April data, which demonstrates why vintages are necessary. Most changes
cancel in ratios: 1,080 prior strategy weeks differ above 1e-10, but the maximum
weekly return difference is only about 0.000084%.

The pipeline initially exposed and fixed a sample-endpoint lookahead convention:
the old notebook forced the final data row to count as a monthly rebalance.
Calendar-causal scheduling now leaves 2026-08-07 as a non-rebalance row. The
July 31 allocation—QQQ, IWM, EWJ, and PDBC at 25% each—is shown only as a
reconstructed reference. It was not live-known on July 31, cannot submit orders,
and is marked waiting for the next scheduled monthly observation on 2026-08-28.

The first locked untouched return remains the week ending 2026-08-14. No
untouched returns are recorded yet and 52 weeks are still required.

References:

- `evidence/free_snapshot_research_pipeline/report.md`
- `evidence/free_snapshot_research_pipeline/result.json`
- `evidence/free_snapshot_research_pipeline/paper_target.json`
- `data/derived/20260808T212827Z-de103c2e063d6c4a/manifest.json`

## Step 19 — Freeze v4 and build the first strategy research laboratory

The user explicitly deprioritized the paper broker in favor of strategy and
portfolio-construction research. The v4 trend-quality strategy is now frozen as
a reproducible benchmark manifest. It pins the immutable source snapshot,
derived-data manifest, universe, five signals, timing, parameters, costs, code
hashes, historical metrics, and forward-test start. Any material change must
become v5 or later; the freeze does not convert historical results into an
untouched test.

A platform-owned research interface and four portfolio constructors were added:
equal weight, score weight, inverse volatility, and score combined with inverse
volatility. All use only information available on each decision row, retain the
one-week signal lag, rebalance on calendar-causal monthly observations, realize
returns in the following week, and charge turnover costs. When fewer risk
assets qualify, the missing slots remain in BIL or explicit cash rather than
being silently redistributed.

Research Laboratory Batch 01 ran 288 configurations: eight trend/momentum
signal recipes, three smoothing windows, three portfolio sizes, and four
construction methods. Every configuration received a deterministic experiment
ID and a permanent JSON Lines record, including failures and weak results.

The leader selected solely on 2006–2015 development data was one-week-smoothed
time-series momentum, top six, weighted by score and inverse volatility. It
reported:

- development annual return 8.29%, Sharpe 0.901, drawdown -13.39%;
- retrospective 2016–2020 annual return 5.11%, Sharpe 0.474, drawdown -19.27%;
- retrospective 2021–2026 annual return 9.57%, Sharpe 1.027, drawdown -13.58%;
- full-history annual return 7.49%, Sharpe 0.785, drawdown -19.27%.

This candidate reduced drawdown relative to v4 but did not beat v4's full
return. The exactly reconciled v4 laboratory row remains 9.91% annual return,
0.754 Sharpe, and -26.25% maximum drawdown. Its full-history metrics match the
earlier free-snapshot pipeline exactly.

Two causal retrospective folds selected parameters using only their earlier
10-year training windows and then spliced the later evaluation returns. The
combined 2016–2026 path reported 9.36% annual return, 0.825 Sharpe, and -19.27%
maximum drawdown. This is better risk-adjusted retrospective evidence than the
single frozen configuration, but it is not untouched because all dates were
visible when Batch 01 was designed. Testing 288 alternatives also creates
multiple-testing risk, so no candidate was promoted.

The awesome-systematic-trading catalog was used as guidance rather than as
unreviewed source code. Batch 01 adopted the high-throughput comparison pattern
from vectorbt, separation of forecasts and position sizing from pysystemtrade,
chronological model-selection framing from skfolio, multiple allocation
objectives from Riskfolio-Lib, and first-class cost/look-ahead/walk-forward
evidence from Manifold-BT. No code was copied from those repositories.

References:

- `config/strategies/composite_trend_quality_refined_free_snapshot_v4.json`
- `evidence/research_lab_batch_01/report.md`
- `evidence/research_lab_batch_01/result.json`
- `evidence/research_lab_batch_01/leaderboard.csv`
- `evidence/research_lab_batch_01/experiments.jsonl`
- `evidence/research_lab_batch_01/walk_forward_returns.csv`
- `src/systematic_trader/research_lab.py`
- `src/systematic_trader/portfolio_construction.py`

## Step 20 — Preserve provisional leaders and run Robustness Batch 02

A canonical strategy-candidate registry now prevents promising results from
being lost while keeping a hard boundary between “worth more research” and
“final.” The registry saved ten distinct candidates: the best qualifying
configuration from each of the eight signal recipes, the exact frozen v4
benchmark, and a distinct configuration selected by the second walk-forward
fold. Each entry records its configuration, selection reason, evidence, passed
gates, missing gates, and explicit `final: false` and
`approved_for_live_trading: false` flags.

The qualification rules were saved before Robustness Batch 02. A configuration
needed Sharpe of at least 0.40 in retrospective 2016–2020 and 0.80 since 2021,
drawdown no worse than -30% in either period, reconciled accounting, and no
unpriced exposure. Diversity was enforced by keeping the leading qualifier per
signal recipe rather than filling the registry with near-identical top ranks.

All ten candidates were then rerun through three new gates:

1. a nine-member neighborhood holding signal recipe and portfolio method fixed
   while varying smoothing across 1/4/8 weeks and portfolio size across 2/4/6;
2. full-history turnover-cost stress at 10, 25, 50, and 100 bps; and
3. fixed point-in-time regimes based on the trailing 26-week SPY return and
   volatility known at each decision date.

All ten passed the declared initial gates. The weakest neighborhood median
Sharpe for 2016–2020 was 0.365, above the 0.35 threshold; worst neighborhood
drawdowns ranged as low as roughly -29.9%, above the -35% limit. At 100 bps,
annual returns remained between 4.76% and 8.38% and Sharpes between 0.516 and
0.721. Each candidate remained above the -2% annual-return floor in all three
scored regimes.

The unanimous pass is interpreted as evidence that this trend/momentum family
is not dependent on one precise parameter or low cost assumption. It is not
proof that all ten are independent sources of return: they share signals,
assets, data, and history and are likely highly correlated. Every status is
therefore `provisional_robust`, not final. Multiple-testing correction,
cross-strategy dependence/ensemble analysis, survivorship-safe membership, and
52 untouched forward weeks remain mandatory.

References:

- `research_registry/strategy_candidates.json`


- `evidence/robustness_batch_02/report.md`
- `evidence/robustness_batch_02/result.json`
- `evidence/robustness_batch_02/neighborhoods.csv`
- `evidence/robustness_batch_02/cost_stress.csv`
- `evidence/robustness_batch_02/regimes.csv`
- `scripts/build_strategy_candidate_registry.py`
- `scripts/run_robustness_batch_02.py`

## Step 21 — Measure candidate dependence, ensembles, and multiple testing

Ensemble and Dependence Batch 03 reconstructed all ten provisional candidates
from their saved configurations and common immutable snapshot. It compared all
45 strategy pairs using full and recent return correlation plus average weighted
holdings overlap, then combined actual target weights before accounting so
shared turnover was netted rather than double-charged.

The primary finding is substantial duplication:

- pairwise full-history correlations range from 0.838 to 0.981;
- median pairwise correlation is 0.931;
- average historical holdings overlap is 69.1%;
- all ten candidates belong to one connected cluster at correlation ≥ 0.90;
- the correlation participation ratio estimates only 1.15 effective independent
  strategy streams.

An equal-weight combination of all candidate target portfolios reported 9.42%
annual return, 0.830 Sharpe, -22.74% maximum drawdown, and 2.02 annual turnover.
Frozen v4 remains 9.91%, 0.754, -26.25%, and 1.93 respectively. A four-member
greedy low-correlation diagnostic starting from v4 reported 9.24%, 0.816,
-23.28%, and 2.19. These ensembles improved retrospective risk adjustment but
did not create a meaningfully independent return source, and they were designed
after viewing the history.

The multiple-testing implementation was corrected after discovering that 2,000
bootstrap samples made a 5% Bonferroni gate mathematically impossible to pass
across 288 trials. The final evidence uses 25,000 deterministic circular block-
bootstrap samples with 13-week blocks, providing adequate tail resolution while
preserving short-range serial dependence under a centered zero-mean null.

The expected best annualized Sharpe across 288 independent Gaussian zero-alpha
trials is approximately 0.620. Candidate Sharpes range from about 0.744 to 0.894;
none of 25,000 centered bootstrap samples matched each observed mean, producing
the finite-sample p-value 1/25,001 and Bonferroni-adjusted p-value 0.0115. All ten
therefore pass this declared retrospective zero-mean diagnostic.

That statistical pass does not turn ten correlated variants into ten alphas and
does not satisfy the untouched-forward requirement. The correct research move
is to retain this family as one promising trend/momentum sleeve and seek truly
different sources of return—mean reversion, defensive allocation, carry, and
other non-momentum families—before constructing a broader ensemble.

References:

- `evidence/ensemble_dependence_batch_03/report.md`
- `evidence/ensemble_dependence_batch_03/result.json`
- `evidence/ensemble_dependence_batch_03/pairwise_dependence.csv`
- `evidence/ensemble_dependence_batch_03/ensemble_scoreboard.csv`
- `evidence/ensemble_dependence_batch_03/marginal_contribution.csv`
- `evidence/ensemble_dependence_batch_03/multiple_testing.csv`
- `research_registry/strategy_candidates.json`
- `src/systematic_trader/ensemble.py`
- `scripts/run_ensemble_dependence_batch_03.py`

## Step 22 — Add mean-reversion, defensive, and carry-proxy families

New Strategy Families Batch 04 introduced six independent platform-owned raw
signals: four-week reversal, moving-average deviation reversal, RSI reversal,
low volatility, drawdown resilience, and trailing cash-distribution yield. A
seventh defensive-quality signal combines low volatility and resilience while
requiring a positive 26-week absolute trend. Every observed value is shifted
one week before it becomes tradable.

The research design tested 288 configurations across eight recipes, 1/2/4-week
smoothing, top-2/4/6 portfolios, and the four established weighting methods.
Mean-reversion recipes made weekly decisions; defensive and carry recipes
remained monthly. All returns begin in the following week and include 10 bps
turnover costs, with family leaders additionally stressed at 50 bps.

The development-selected defensive leader uses two-week-smoothed gated
defensive quality, top six, equal weight. It reported 7.09% full-history annual
return, 0.879 Sharpe, -22.79% drawdown, and 3.26 annual turnover. Its 2016–2020
Sharpe was 0.597 and its post-2021 Sharpe 1.079. At 50 bps it retained 5.71%
annual return and 0.720 Sharpe. Correlation to frozen v4 was 0.719, and it was
saved as `provisional_new_family`.

The carry-proxy leader uses two-week-smoothed distribution yield, top six, and
score-plus-inverse-volatility weighting. It reported 6.00% annual return, 0.652
Sharpe, -27.07% drawdown, and 0.79 annual turnover. Its 2016–2020 and post-2021
Sharpes were 0.676 and 0.542. At 50 bps it retained 5.67% annual return and 0.619
Sharpe. Correlation to v4 was only 0.581, but the candidate remains research-only
because all historical distribution events were obtained in one current 2026
Yahoo vintage rather than archived point-in-time vintages.

The mean-reversion leader uses four-week reversal, four-week smoothing, weekly
top-four equal-weight decisions. It reported 8.80% annual return and 0.619 Sharpe,
but suffered a -45.34% drawdown and 12.20 annual turnover. At 50 bps its annual
return fell to 3.61% and Sharpe to 0.306. It is preserved as
`provisional_fragile`, not discarded or presented as safe.

The family correlations are materially lower than correlations within the
trend family: trend/v4 correlation was 0.719 to defensive, 0.581 to carry, and
0.628 to mean reversion. Defensive versus mean reversion was only 0.413.

Netted diagnostic combinations showed the diversification tradeoff:

- frozen v4: 9.91% return, 0.754 Sharpe, -26.25% drawdown;
- 50/50 trend and defensive: 8.64%, 0.860, -24.29%;
- equal trend/defensive/carry: 7.85%, 0.871, -24.44%;
- equal four-family portfolio: 8.24%, 0.842, -25.28% with substantially higher
  4.22 annual turnover because of weekly mean reversion.

These combinations improve retrospective risk adjustment but lower return and
were designed after viewing the data. They are diagnostics, not promoted
portfolios. Three family leaders were added to the canonical registry, raising
the tracked total from 10 to 13 while preserving all non-final flags.

The awesome-systematic-trading catalog guided the use of RSI/reversal hypotheses
from quant-trading and PythonTradingFramework and the separation of forecasts,
position sizing, and aggregation from pysystemtrade. No third-party strategy
code was copied.

References:

- `evidence/new_families_batch_04/report.md`
- `evidence/new_families_batch_04/result.json`
- `evidence/new_families_batch_04/leaderboard.csv`
- `evidence/new_families_batch_04/experiments.jsonl`
- `evidence/new_families_batch_04/family_pairwise_correlation.csv`
- `evidence/new_families_batch_04/multi_family_ensemble_diagnostics.csv`
- `research_registry/strategy_candidates.json`
- `src/systematic_trader/non_momentum_signals.py`
- `scripts/run_new_families_batch_04.py`

## Step 23 — Stress the new families and retain only the robust survivor

New-Family Robustness Batch 05 evaluated all three Batch 04 leaders using rules
fixed in the runner: nine nearby parameter settings, transaction costs through
100 bps per unit turnover, three regimes derived causally from trailing 26-week
SPY data, and 50,000 circular 13-week block-bootstrap samples. The statistical
test used a Bonferroni correction across all 576 configurations searched in
Batches 01 and 04, not just the three selected leaders.

Only the defensive leader passed every gate. At 100 bps it retained 4.00%
annual return, 0.518 Sharpe, and -23.02% maximum drawdown. All nine nearby
variants were profitable in both later evaluation periods; median Sharpe was
0.621 in 2016–2020 and 0.984 from 2021 onward. Its observed 0.879 Sharpe exceeded
the bootstrap estimate of 0.665 for the best zero-alpha result among 576 trials,
with a Bonferroni-adjusted p-value of 0.0115. It advanced only to
`provisional_robust_new_family` and remains non-final.

Carry passed its neighborhood, causal-regime, and 100 bps economic gates. At
100 bps it retained 5.25% annual return and 0.578 Sharpe. However, its 0.652
observed Sharpe did not exceed the estimated 0.665 best null result and its
adjusted p-value was 0.1498. It therefore returned to `provisional_fragile`, in
addition to its unresolved archived point-in-time distribution-history gate.

Mean reversion was stable across its nearby parameter choices and passed the
declared regime floor, but at 100 bps it lost 2.53% annually, had -0.085 Sharpe,
and reached a -62.88% drawdown. Its adjusted p-value was 0.1152. It remains
`provisional_fragile`.

A netted 50/50 trend-v4 and defensive diagnostic reported 8.64% annual return,
0.860 Sharpe, -24.29% maximum drawdown, and 2.45 annual turnover, compared with
9.91%, 0.754, -26.25%, and 1.93 for trend v4 alone. This is a retrospectively
designed portfolio diagnostic, not an untouched holdout or promotion candidate.

References:

- `evidence/new_family_robustness_batch_05/report.md`
- `evidence/new_family_robustness_batch_05/result.json`
- `evidence/new_family_robustness_batch_05/candidate_summary.csv`
- `evidence/new_family_robustness_batch_05/robust_ensemble_diagnostics.csv`
- `research_registry/strategy_candidates.json`
- `scripts/run_new_family_robustness_batch_05.py`

## Step 24 — Compare covariance-aware multi-strategy portfolios

Batch 06 combined only frozen trend v4 and the defensive family that survived
Batch 05. Six primary methods were declared: equal weight, inverse volatility,
minimum variance, maximum diversification, two-sleeve HRP, and unlevered 10%
volatility targeting. Every monthly decision used at most 104 trailing weeks
known by that date, required 52 observations, and shrank cross-covariance 25%
toward zero. Sleeve weights were capped at 80%, underlying non-cash holdings at
35%, and any excess concentration was held in explicit cash.

Minimum variance won selection using only the 2006–2015 development score. Its
full retrospective result at 10 bps was 7.83% annual return, 0.901 Sharpe,
-23.39% drawdown, and 2.90 annual turnover. In 2016–2020 it reported 6.30%
annual return and 0.613 Sharpe; from 2021 onward, 9.72% and 1.102. At 50 bps it
retained 6.58% annual return, 0.769 Sharpe, and -23.50% drawdown. It was saved in
a separate portfolio registry as `provisional_portfolio_research`, never as a
final or live-approved portfolio.

The full-history HRP Sharpe was marginally higher at 0.903, but using that fact
to override the development selection would be hindsight. Equal weighting
retained the highest annual return at 8.62% but had a lower 0.859 Sharpe and a
slightly deeper -24.29% drawdown. Maximum diversification and inverse
volatility produced exactly identical return paths because only two sleeves
were available. Two-sleeve HRP similarly has no meaningful hierarchy; it is an
inverse-variance split with an HRP label only for interface continuity.

Forty-five estimation-sensitivity runs covered 52/104/156-week lookbacks and
0/25/50% covariance shrinkage. Every variant remained positive in both later
evaluation periods. Minimum-variance full-history Sharpe ranged from 0.901 to
0.914 and annual return from 7.83% to 8.11%; the result was not dependent on one
isolated parameter choice. These remain retrospective diagnostics on a
survivorship-prone free ETF universe.

References:

- `evidence/covariance_portfolios_batch_06/report.md`
- `evidence/covariance_portfolios_batch_06/result.json`
- `evidence/covariance_portfolios_batch_06/method_scoreboard.csv`
- `evidence/covariance_portfolios_batch_06/estimation_sensitivity.csv`
- `research_registry/portfolio_candidates.json`
- `src/systematic_trader/strategy_allocation.py`
- `scripts/run_covariance_portfolios_batch_06.py`

## Step 25 — Adversarially stress and freeze the portfolio rules

Batch 07 tested the already-selected minimum-variance portfolio at 50 bps. It
did not search for a replacement method. Twenty rolling three-year windows,
stepped annually with a final endpoint window, were all profitable. The weakest
window returned 1.85% annually with 0.204 Sharpe, and the worst rolling drawdown
was -23.50%, inside the predeclared -35% limit.

A 20,000-sample circular block bootstrap preserved 13-week serial chunks. The
95% interval for annual return was 3.09%–9.96%, the Sharpe interval was
0.361–1.231, and the adverse drawdown bound was -35.31%, inside the declared
-40% floor. Relative to equal weight, the selected portfolio's annual
volatility was 1.12–1.82 percentage points lower across the 95% interval.

Covariance inputs were delayed by 1, 4, and 13 weeks; rounded to four decimals;
perturbed with deterministic ±5 bps synthetic revisions; and stripped of every
tenth estimator observation. Every scenario retained positive annual return,
Sharpe above 0.50, drawdown better than -30%, fully invested accounting, and no
unpriced exposure. Malformed, negative-variance, and non-finite covariance
matrices correctly fell back to equal sleeve weights. A valid zero-variance
matrix also resolved deterministically to equal weight.

All four Batch 07 gates passed. The rules were therefore frozen as
`covariance_minimum_variance_v1`, with code hashes and snapshot identity pinned.
The first eligible untouched decision date is 2026-08-14. The forward counter
starts at 0/52 weeks. Frozen means the rules cannot be tuned while accumulating
forward evidence; it does not mean final, survivorship-safe, or approved for
real-money trading. Only one genuine free-data vintage currently exists, so
synthetic revision stress does not satisfy the multi-vintage gate.

References:

- `evidence/portfolio_robustness_batch_07/report.md`
- `evidence/portfolio_robustness_batch_07/result.json`
- `evidence/portfolio_robustness_batch_07/rolling_windows.csv`
- `evidence/portfolio_robustness_batch_07/bootstrap_uncertainty.csv`
- `evidence/portfolio_robustness_batch_07/input_stress.csv`
- `config/portfolios/covariance_minimum_variance_v1.json`
- `research_registry/portfolio_candidates.json`
- `scripts/run_portfolio_robustness_batch_07.py`

## Step 26 — Lock the append-only forward evidence protocol

The forward recorder separates decision capture from return realization. A
decision may be saved only from an immutable snapshot observed at or after
21:00 UTC on its Friday and before the same time the following Friday. One week
later, a separately eligible snapshot can attach the realized return to that
exact decision-record hash. Later vintages cannot invent or backfill a missed
target.

Both JSON Lines logs are hash-chained, sequential, chronological, and unique by
date. The recorder rejects pre-freeze dates, duplicate dates, out-of-order
records, changed record contents, broken chain links, a changed portfolio
manifest, or changed pinned calculation dependencies. It applies the frozen
50 bps cost model and has no execution or broker capability.

An August 7 pre-freeze target was saved only as the turnover anchor. It assigns
20% to trend v4 and 80% to defensive before underlying positions are combined;
it is explicitly excluded from untouched evidence. Running the recorder twice
against the only available snapshot appended no decisions and no returns,
demonstrating idempotence and respect for the August 14 boundary. The truthful
clock remains 0/52, with the first possible realization on August 21 after a
valid August 14 decision snapshot exists.

References:

- `config/forward/covariance_minimum_variance_v1.json`
- `evidence/forward_covariance_minimum_variance_v1/anchor.json`
- `evidence/forward_covariance_minimum_variance_v1/status.json`
- `evidence/forward_covariance_minimum_variance_v1/report.md`
- `src/systematic_trader/forward_evidence.py`
- `scripts/record_forward_portfolio_evidence.py`

## Step 27 — Connect and execute the guarded weekly data cycle

The Podman collector and frozen recorder were joined behind one fail-closed
weekly command. The outer cycle enforces a Friday 21:00 UTC cutoff, a process
lock, one completed run per decision week unless explicitly overridden,
snapshot freshness, unchanged weekly timing, monotonic forward counters, and
disabled execution. It passes only the newly registered snapshot ID to the
independently guarded recorder.

The first real cycle completed for the August 7 pre-freeze week. It created
immutable snapshot `20260809T002313Z-0d8632e2cf759918`, covering all 35 symbols
and 209,568 price rows through August 7. The recorder correctly appended zero
decisions and zero returns because the first eligible decision remains August
14. The clock stayed at 0/52 and no broker or execution path was enabled.

The second vintage initially appeared to revise 151,125 of 209,568 common rows,
or 72.11%. Magnitude analysis showed this was adjusted-close floating-point
drift rather than an economic history rewrite: no raw close changed, the
largest adjusted-close relative difference was 0.000226%, only 1,267 rows
exceeded 0.0001%, and zero exceeded the declared 0.01% materiality threshold.
Future acquisition reports now preserve magnitude bands so row counts cannot be
misinterpreted without economic scale.

References:

- `evidence/weekly_forward_cycles/2026-08-07-20260809T002313Z-0d8632e2cf759918/report.md`
- `evidence/weekly_forward_cycles/2026-08-07-20260809T002313Z-0d8632e2cf759918/result.json`
- `evidence/weekly_forward_cycles/2026-08-07-20260809T002313Z-0d8632e2cf759918/revision_magnitude.json`
- `evidence/free_data_acquisition/latest_result.json`
- `scripts/run_guarded_weekly_forward_cycle.py`
- `src/systematic_trader/data_revision.py`

## Step 28 — Predeclare the six-track challenger program

A new Batch 08–13 program was created without modifying the frozen
`covariance_minimum_variance_v1` files. It covers trade buffering, a causal 1.0
fragility-guard reconstruction, independent third sleeves, four portfolio
libraries, four ML systems, and vectorbt equivalence. Every attempted rule is
counted in one trial ledger; failed, blocked, and license-restricted candidates
must remain visible. Common gates require exact commits, license review,
isolated execution, next-period realization, 10/25/50/100 bps costs, rolling
and bootstrap checks, perturbations, multiple-testing adjustment, and 52
untouched forward weeks before promotion.

Ten repositories were pinned and acquired sequentially in rootless Podman with
no host mounts. All ten exact commits passed the source-only gate, during which
no repository code was executed. Repository size and test structure varied
substantially: QLib exposed 619 tracked files and 59 test indicators, while
FinClaw exposed only 6 tracked files, no package manifest, and no tests. GPL
and restricted-license projects remain available for isolated study but their
source is not copied into the application core.

References:

- `config/challenger_program_v1.json`
- `evidence/challenger_program_v1/source_queue.csv`
- `evidence/challenger_program_v1/source_smoke/summary.json`
- `evidence/challenger_program_v1/repository_metadata.json`
- `evidence/challenger_program_v1/trial_ledger.csv`

## Step 29 — Test causal trade buffering

Batch 08 independently implemented the no-trade-band concept associated with
pysystemtrade without copying GPL source. A buffered target is a convex
combination of the previous target and new target, so long-only, fully invested
weights and existing asset caps are preserved. Twenty-eight trials covered
symmetric, asymmetric, and cost-aware bands at 10, 25, 50, and 100 bps.

The zero-band baseline retained the best 2006–2015 development score and
reproduced frozen v1 exactly: 7.826% annual return, 0.901 Sharpe, -23.39%
drawdown, and 2.90 annual turnover at 10 bps. Buffering therefore did not
replace the winner. It did improve high-cost resilience: at 100 bps the 10%
band raised full-history Sharpe from 0.602 to 0.656 and reduced annual turnover
from 2.90 to 2.10. The feature is retained as a conditional execution
challenger, not new alpha and not a promoted rule.

References:

- `src/systematic_trader/challenger_buffering.py`
- `scripts/run_trade_buffering_batch_08.py`
- `evidence/trade_buffering_batch_08/result.json`
- `evidence/trade_buffering_batch_08/scoreboard.csv`

## Step 30 — Reconstruct the 1.0 fragility guard causally

The 1.0 design was reviewed directly. Its central idea combined a modest
offense-quality scale with a leadership-crowding cap and prohibited offense
boosts during stressed-panic states. Batch 09 rebuilt that idea using only
free ETF prices known by each decision date: causal breadth, path clarity,
state persistence, and cross-sectional leadership spread. It did not reuse the
1.0 intermediate panels or implementation.

Fifty-two trials covered three boost strengths, two crowding thresholds, an
optional 5% trade buffer, and four cost assumptions. Stress weeks could never
receive a boost and crowded leadership capped positive boosts. The unmodified
baseline again won the development selection and reproduced frozen v1. The
original 1.0 improvement therefore did not transfer to the different 2.0
universe and construction method. The complete negative result remains saved.

References:

- `src/systematic_trader/challenger_fragility_guard.py`
- `scripts/run_fragility_guard_batch_09.py`
- `evidence/fragility_guard_batch_09/result.json`
- `evidence/fragility_guard_batch_09/scoreboard.csv`

## Step 31 — Reconcile independent third-sleeve evidence

Batch 10 reconciled all four predeclared third-sleeve families against the 288
Batch 04 strategy configurations and the 576-trial Batch 05 correction. Carry
remained positive and cost-robust but failed the multiple-testing gate and lacks
archived point-in-time distribution vintages. Short-term reversal failed the
100 bps and multiple-testing gates and had excessive turnover. Defensive macro
logic passed robustness but is already frozen sleeve two, so it cannot be
counted again as an independent sleeve. Genuine cross-sectional value remains
blocked by the absence of point-in-time fundamentals; a price-only substitute
would be mislabeled rather than a valid test.

No third sleeve was forced through. The track finished with no qualified
independent sleeve and retained explicit free-data backlog entries for value
and term-structure carry.

References:

- `scripts/build_independent_sleeves_batch_10.py`
- `evidence/independent_sleeves_batch_10/result.json`
- `evidence/independent_sleeves_batch_10/family_decisions.csv`

## Step 32 — Establish a nested walk-forward ML bar

Before accepting any external ML example, Batch 12 created a small auditable
ridge baseline. Features were available by the weekly decision close, labels
were next-week SPY returns, scaling and fitting occurred inside each training
window, inner selection used only time-ordered validation, and a one-week
embargo separated training labels from each outer test. A deterministic label
shuffle served as a negative control.

Seventeen outer folds produced 866 out-of-sample decisions. Three penalties per
fold across the real and shuffled variants created 102 logged fits. At 10 bps,
the unchanged frozen portfolio earned 7.59% annually with 0.851 Sharpe over the
common outer-test span. The nested ridge overlay earned 6.62% with 0.782
Sharpe; the label-shuffle overlay earned 6.52% with 0.779 Sharpe. The real model
beat its negative control slightly but did not beat the portfolio. No ML alpha
was accepted.

All four named ML repositories then received explicit source/capability
decisions. QLib installed after a preserved SCM-version failure, then its
offline suite stopped at the first RL test because optional `torch` was absent.
Ml-quant-trading was stopped once at the storage safety floor; after unused
Podman blocks were safely trimmed and 15 GB restored, its clean retry still
exceeded the fixed 600-second install limit after expanding beyond 4 GB.
Deepdow likewise exceeded 600 seconds on a clean retry and has been quiet since
2024. FinClaw was not executed: the pinned source had only 6 tracked files, no
package manifest, no tests, and no detected license. Packaging failures and
timeouts are retained as feasibility evidence; none of the repositories
supplied a strategy that beat the common nested bar.

References:

- `config/ml_sandbox_v1.json`
- `src/systematic_trader/nested_ml_challenger.py`
- `scripts/run_nested_ml_baseline_batch_12.py`
- `scripts/build_ml_repository_summary.py`
- `evidence/ml_sandbox_batch_12/result.json`
- `evidence/ml_sandbox_batch_12/outer_folds.csv`
- `evidence/ml_sandbox_batch_12/repository_summary.json`

## Step 33 — Probe four portfolio libraries on identical inputs

Batch 11 ran cvxportfolio, skfolio, Riskfolio-Lib, and PyPortfolioOpt from exact
commits in disposable Podman volumes. Each behavioral probe ran with networking
disabled and no host mount. Seven attempts were retained because clean-install
failures were not overwritten: cvxportfolio's GitHub archive needed explicit
SCM version metadata; PyPortfolioOpt's minimal install omitted the `packaging`
runtime dependency; and unconstrained Riskfolio exceeded the 35% asset cap.

The corrected latest attempt for every library passed its scoped capability.
Skfolio and explicitly bounded Riskfolio produced nearly identical constrained
minimum-variance weights on the same return matrix, both summing to 1.0 and
capping the largest asset at 35%. PyPortfolioOpt also produced a fully invested,
35%-capped solution after its missing dependency was supplied. Its broader
upstream run completed 236 tests with 14 skips before one HRP test failed
because it accessed a removed private SciPy attribute. Cvxportfolio constructed
a single-period policy after the archive-version fix, but remains sandbox-only
under GPL-3.0.

These results validate implementation and constraint behavior, not alpha. No
library replaced the platform-owned allocator or changed frozen v1.

References:

- `config/portfolio_library_comparison_v1.json`
- `scripts/run_portfolio_library_probes.py`
- `scripts/build_portfolio_library_summary.py`
- `evidence/portfolio_libraries_batch_11/result.json`
- `evidence/portfolio_libraries_batch_11/capability_probes/summary.json`
- `evidence/challenger_program_v1/python_execution/ast-0187.json`

## Step 34 — Test vectorbt as a research accelerator

Batch 13 installed vectorbt 1.1.0 from the pinned commit in a disposable
Podman volume and ran the probe offline. Its three- and five-period moving
averages matched the independent pandas reference exactly, repeated portfolio
runs were deterministic, one order incurred 9.9900 in modeled fees, and final
value was 10,758.47 from 10,000 initial cash. The first cold indicator and
backtest calls took 24.75 and 53.52 seconds respectively because Numba compiled
inside a clean no-cache volume; this is not a steady-state speed benchmark.

The track passed numerical-primitives and determinism gates. Vectorbt is
retained only as an optional sandbox research accelerator. It supplies no
alpha, is not incorporated into the core, and cannot be treated as an
unrestricted commercial dependency under its Commons Clause license.

References:

- `scripts/run_vectorbt_equivalence_batch_13.py`
- `evidence/vectorbt_equivalence_batch_13/result.json`

## Step 35 — Close the six-track comparison without forcing a winner

The Batch 08–13 program closed with 10/10 pinned sources acquired and 111
explicit trial-ledger rows. Every one of the six tracks was attempted. Trade
buffering improved only high-cost resilience; the causal fragility guard did
not transfer; no independent third sleeve passed; four portfolio libraries
passed corrected scoped capability checks but supplied no alpha; the nested ML
overlay lost to baseline and no external ML repository cleared capability plus
validation gates; vectorbt passed equivalence but remains a restricted-license
sandbox accelerator.

The winning historical candidate therefore remains the unchanged
`covariance_minimum_variance_v1`: 7.826% annual return, 0.901 Sharpe, -23.39%
maximum drawdown, and 2.90 annual turnover at 10 bps. It is still non-final and
the untouched forward clock is still 0/52 weeks. No live-trading approval was
created.

The complete unittest discovery run was interrupted after it became idle on an
iCloud-backed file read. A focused regression covering the new program plus
the frozen allocator, robustness, forward recorder, and guarded weekly cycle
then passed 36/36 tests. This is reported as a focused regression pass, not a
claim that every older test completed in the final invocation.

References:

- `evidence/challenger_program_v1/result.json`
- `evidence/challenger_program_v1/trial_ledger.csv`
- `research_registry/portfolio_candidates.json`
- `PROJECT_HISTORY.md`

## Current component decisions

- `bt`: retain as a guarded research adapter; reject the tested trading rule.
- FlashAlpha: retain as a guarded experimental fill component; needs many more
  dates/regimes.
- TradingView Screener API: retain for current screening only.
- Barter instrument core: advance to adversarial identity/serialization tests.
- hftbacktest: retain as a guarded sandbox execution candidate; advance to a
  substantially larger snapshot-plus-L2/trade replay.
- Cipher and finmarketpy: scoped code gates passed; deeper behavioral gates are
  still pending.
- All failed candidates remain in the registry for narrower idea review.

## What is complete and what is not

| Capability | 1.0 | 2.0 current state |
|---|---|---|
| Market-data artifacts | Complete saved research datasets | Two immutable free daily vintages plus hashed completed-week derivation and magnitude-aware revision audit |
| Automatic data gathering | No always-on service | One-command guarded acquisition/forward cycle works end to end; weekly Friday 14:30 America/Los_Angeles heartbeat is active |
| Signal research | Extensive ETF research | Five trend formulas plus seven lagged non-momentum signals tested on the newest free snapshot |
| Strategy sleeves | Extensive saved research | 576 standardized configurations searched; one new-family leader passed Batch 05 retrospectively, none final |
| Risk/regime logic | Implemented in research notebooks/scripts | Core execution guards implemented; full risk engine pending |
| Portfolio construction | Implemented and compared | Six strategy-allocation methods tested; minimum-variance v1 passed Batch 07 and is frozen at 0/52 untouched weeks |
| Historical backtesting | Implemented at bar/portfolio level | Free snapshot simulation extended through 2026-08-07 with revision audit |
| Paper broker | Not implemented | Explicitly deferred by user; strategy research does not depend on it |
| Dashboard | Implemented | Not yet rebuilt for 2.0 |
| Live real-money trading | Not implemented | Explicitly not approved |

## Required next steps

1. Let the scheduled guarded cycle collect only eligible Friday observations;
   investigate failures without backfilling missed weeks.
2. Recompute the frozen portfolio across successive real vintages and quantify
   target/return drift before clearing the multi-vintage gate.
3. Seek an archived point-in-time free distribution source before treating the
   carry proxy as more than research-only evidence.
4. Continue accumulating immutable free-data vintages and untouched forward
   observations without modifying frozen v4.
5. Continue repository Batches 1–9 without omitting failed or inconclusive
   entries, but prioritize research components over live execution components.
6. Promote strategies only after benchmark, cost, walk-forward, untouched
   holdout, regime, multiple-testing, and robustness gates pass.

Paid historical-membership/delisting data remains a deferred optional upgrade,
not a blocker for the remaining free research and simulation work.

## Update protocol for future work

After each material test:

1. preserve a pinned machine-readable result under `evidence/`;
2. write or update the corresponding human-readable report;
3. update the repository's row in `research_registry/registry.csv`;
4. add the outcome to this history in chronological order;
5. update the truth-at-a-glance totals; and
6. run the complete 2.0 regression suite.

This file reports what was actually tested. Planned work must never be recorded
as complete.

## Step 36 — Open the point-in-time third-sleeve program

The frozen `covariance_minimum_variance_v1` artifact set was left unchanged.
The forward status remains valid at 0/52 observed weeks, with execution and live
trading disabled. A new, separate program predeclared two free-data tracks:
official Treasury term structure and SEC-filed value fundamentals.

Primary official sources were screened before testing. Treasury provides a
daily nominal par-yield curve back to 1990 through a free XML feed. SEC EDGAR
provides submissions and companyfacts JSON without an API key, including filed
dates and accession numbers suitable for as-of fact selection. Neither source
was treated as solving historical ETF/stock-universe survivorship by itself.

References:

- `config/third_sleeve_program_v1.json`
- `src/systematic_trader/term_structure_challenger.py`
- `src/systematic_trader/sec_value_research.py`

## Step 37 — Test the official Treasury term-structure challenger

An immutable official Treasury snapshot captured 6,154 complete daily curve
rows from 2002-01-02 through 2026-08-07. Every signal used a curve at least seven
calendar days old, weights changed monthly, and results were charged at 10, 50,
and 100 bps. The two challenger rules and equal-weight reference were fixed
before their results were read.

The 2003–2015 development window selected `slope_regime`. At 10 bps its complete
retrospective record produced 4.185% annual return, 0.393 Sharpe, and -32.50%
maximum drawdown. Its return correlation to the frozen winner was only 0.016
over 1,126 common weeks, so it was genuinely diversifying. It nevertheless
failed promotion: at 100 bps its 2016–2020 annual return was 7.194%, but its
2021–present annual return was -4.993%, and the two-candidate-adjusted serial
block-bootstrap lower return bound was not positive. No forward clock was
started for it.

This test still carries honest limitations. The Treasury feed does not expose a
complete pre-acquisition revision history, the free ETF adjusted prices are a
current research snapshot, and SHY/IEF/TLT are not a survivorship-safe universe.

References:

- `data/official_treasury_vintages/20260809T023724Z-40d06905b5bc9b05/manifest.json`
- `evidence/treasury_term_structure_batch_14/result.json`
- `evidence/treasury_term_structure_batch_14/scoreboard.csv`
- `evidence/treasury_term_structure_batch_14/report.md`

## Step 38 — Establish the SEC value as-of gate

The SEC fact-vintage source gate passed, and tested selection logic now filters
facts by official filed date, applies a two-calendar-day execution delay, and
prevents later amendments from leaking backward. A value performance backtest
was deliberately not run: companyfacts alone does not provide historical
investable-universe membership, complete ticker mapping, or delisting returns.
Reporting a Sharpe from current survivors would therefore be misleading.

The value track remains active as a data-engineering candidate and requires no
paid source yet, but it cannot advance to performance claims until those missing
bias controls are supplied.

References:

- `evidence/sec_value_source_gate_batch_15/result.json`
- `evidence/sec_value_source_gate_batch_15/report.md`
- `tests/test_sec_value_research.py`

## Step 39 — Activate guarded weekly forward collection

A weekly heartbeat named `Weekly forward evidence` is active for Fridays at
14:30 America/Los_Angeles, which is always after the frozen 21:00 UTC cutoff.
It runs the existing guarded cycle only inside the permitted snapshot window,
verifies frozen hashes, never backfills, and cannot enable execution or live
trading. The first eligible decision is still 2026-08-14, so activation did not
manufacture an observation and the clock remains 0/52.

## Step 40 — Build the cross-sectional factor and ML baseline

The first Qlib/ml-quant-inspired component was implemented without installing a
large external framework into the core application. A predeclared factor panel
uses eleven price-derived features, including multiple momentum horizons,
52-week momentum excluding the newest four weeks, moving-average distance,
realized and downside volatility, drawdown, and trend consistency. Every feature
stops one completed week before its monthly decision. Four focused timing,
ranking, tie-handling, and concentration tests passed.

The immutable free ETF snapshot produced 8,324 asset-month rows across 247
monthly decisions, with zero timing violations. The fixed non-ML baseline ranks
features cross-sectionally, combines six predeclared ranks, selects five ETFs,
and applies capped inverse-volatility weights. This is now the common hurdle for
all later ML models.

At 10 bps, the fixed ranker returned 8.520% annually with 0.689 Sharpe, -24.42%
maximum drawdown, and 5.06 annual turnover. At 100 bps, the 2016–2020 and
2021–present annual returns remained positive at 2.003% and 6.956%. However,
mean monthly rank IC was only 0.0309 and its one-sided serial-block-bootstrap
lower bound was -0.0088, so the predictive-ranking gate failed. The baseline
also correlated 0.817 with the frozen winner over 1,126 common weeks, making it
too dependent to qualify as the missing independent sleeve. It was retained for
ML comparison but was not promoted or added to the frozen portfolio.

References:

- `config/cross_sectional_factor_program_v1.json`
- `evidence/cross_sectional_factor_baseline_batch_16/result.json`
- `evidence/cross_sectional_factor_baseline_batch_16/factor_dataset.csv`
- `evidence/cross_sectional_factor_baseline_batch_16/scoreboard.csv`
- `src/systematic_trader/cross_sectional_factors.py`
- `tests/test_cross_sectional_factors.py`

## Step 41 — Run the robust nested cross-sectional ML program

The Batch 16 factor panel became the locked common input for an isolated ML
experiment. A pinned Python 3.12/scikit-learn 1.9.0 Podman image searched ridge,
elastic-net, and histogram gradient-boosting models. Fifteen calendar-year outer
folds began in 2012; every outer training set required both its decision and its
four-week label to end before the test year. Three inner validation years chose
one configuration per model family using mean monthly rank IC minus a turnover
penalty. Five seeds were averaged, and family weights were based only on inner
scores with a 60% cap.

The canonical run completed 2,924 model fits and 690 recorded inner-search rows.
It also trained label-shuffled and within-month random-feature controls and
tested one- and three-month stale inputs. An initial partial run failed closed
when an ensemble family received all positive selection mass and the remaining
families had zero redistribution mass. The allocator was corrected to use equal
fallback redistribution, tested, and the entire experiment restarted. Two later
complete canonical runs produced the identical prediction SHA-256
`c479293b67437738c86313aad8cc9d4a67d5c5278458754dbab488512624caaa`.

The out-of-fold real model achieved 12.110% annual return, 0.855 Sharpe, -32.43%
maximum drawdown, and 8.35 annual turnover at 10 bps from 2012 onward. Its mean
monthly rank IC was 0.0696; the three-family-adjusted serial-bootstrap lower
bound was 0.0224, and 80% of outer years had positive mean rank IC. Label-shuffle
and random-feature rank ICs were negative, and their portfolios underperformed
the real model. Correlation to the frozen winner was 0.723, passing the
predeclared 0.75 dependence threshold.

At 100 bps, the ML portfolio retained 3.980% annual return but only 0.338 Sharpe
and suffered a -46.92% maximum drawdown. Both later windows remained positive.
On the common 10 bps period, ML's point Sharpe narrowly exceeded the frozen
winner, 0.855 versus 0.848, but paired 13-week block bootstrap did not establish
a positive Sharpe advantage: its one-sided lower difference bound was -0.303.
The annual-return advantage over the winner did remain statistically positive.

The candidate therefore passed predictive, negative-control, fold-stability,
cost, and dependence gates, but failed the explicitly required drawdown gate:
-32.43% versus the winner's -23.39%. It also lacks a survivorship-safe universe
and 52 untouched forward weeks. It was saved as
`provisional_promising_high_drawdown` for risk-control research and was not
merged into, or allowed to modify, the frozen winner.

References:

- `config/robust_cross_sectional_ml_v1.json`
- `evidence/robust_cross_sectional_ml_batch_17/result.json`
- `evidence/robust_cross_sectional_ml_batch_17/report.md`
- `evidence/robust_cross_sectional_ml_batch_17/predictions.csv`
- `evidence/robust_cross_sectional_ml_batch_17/inner_search_trials.csv`
- `evidence/robust_cross_sectional_ml_batch_17/determinism_check.json`
- `research_registry/ml_candidates.json`

## Step 42 — Test a confidence-sized ML overlay

The ML ensemble was extended to expose diagnostic disagreement without changing
its forecasts. Each outer fold now records the standard deviation across all 15
family-seed predictions, standard deviation across the three family means, and
the share of members agreeing with the ensemble sign. The isolated 2,924-fit
run was repeated in full. A canonical projection over every original prediction
column retained SHA-256
`22ffd359aee292d1b1e5337d44bd9b102d8681eb2e60e902bb95e645a7032dfd`,
proving that collecting diagnostics did not alter the prior model evidence.

Before viewing results, Batch 18 defined confidence as top-five forecast
separation multiplied by member sign agreement and divided by member-plus-family
disagreement. Expanding 60th, 80th, and 95th percentiles used only earlier
out-of-fold decisions and assigned 0%, 10%, 20%, or 30% ML weight after a
minimum 24-decision warm-up. A 13-week 18% volatility cap and a 26-week -12%
drawdown stop used only returns already realized by each decision. The frozen
winner remained the core and was not modified.

At 10 bps, the primary guarded overlay returned 8.027% annually with 0.878
Sharpe and -23.39% maximum drawdown, versus 7.643%, 0.850, and -23.39% for the
same-period frozen core. Mean ML weight was only 5.91%. Confidence calibration
was directionally useful: active decisions averaged 0.0843 future monthly rank
IC versus 0.0598 while inactive; the 20% and 30% tiers averaged 0.1402 and
0.1498. The 10% tier was much weaker at 0.0111, showing that modest confidence
did not identify a better forecasting state.

The improvement is not yet trustworthy enough for promotion. A paired 20,000
sample, 13-week block bootstrap placed the one-sided 95% lower Sharpe-difference
bound at -0.0153 and the annual-return-difference bound at -0.00043. At 100 bps,
the guarded overlay remained positive but returned 4.175% versus 4.645% for the
core. Fixed ML allocations had higher optimistic-cost point returns but worse
drawdowns and also lost their full-period advantage under 100 bps. The candidate
was saved as `provisional_promising_confidence_overlay`; it did not change the
frozen portfolio and live execution remains disabled.

References:

- `config/ml_confidence_overlay_v1.json`
- `evidence/ml_confidence_overlay_batch_18/result.json`
- `evidence/ml_confidence_overlay_batch_18/report.md`
- `evidence/ml_confidence_overlay_batch_18/confidence_decisions.csv`
- `evidence/ml_confidence_overlay_batch_18/portfolio_scoreboard.csv`
- `research_registry/ml_candidates.json`

## Step 43 — Retest only the strong ML-confidence tiers

Batch 18 showed weak future rank IC in the 10% ML tier but much stronger rank
IC in its 20% and 30% tiers. Because that pattern was observed after inspecting
the history, Batch 19 registered it as a separate retrospective follow-up rather
than rewriting the prior experiment. The new rule abstains below the expanding
prior 80th-confidence percentile, assigns 20% ML weight from the 80th through
95th percentiles, and assigns 30% above the 95th. The same causal volatility and
drawdown guards remain active, and the frozen core remains unchanged.

At 10 bps, the guarded strong-only overlay returned 8.049% annually with 0.882
Sharpe and -23.39% maximum drawdown, compared with 7.643%, 0.850, and -23.39%
for the same-period core. Mean ML exposure declined to 4.35%. This modestly
improved the Batch 18 guarded result while requiring less ML capital. Its paired
annual-return advantage became statistically positive: the one-sided 95% lower
annual-return-difference bound was 0.0135 percentage points. The corresponding
Sharpe-difference lower bound remained negative at -0.0068.

Strong decisions averaged 0.1432 future monthly rank IC versus 0.0452 for
inactive decisions, a point difference of 0.0981. However, a 20,000-sample
three-month serial-block bootstrap placed the one-sided lower difference at
-0.0011, narrowly failing the predeclared confidence-calibration gate. At 100
bps, the overlay returned 4.280% with 0.498 Sharpe versus 4.645% and 0.540 for
the core, failing both strengthened high-cost advantage gates.

The candidate was saved as `provisional_strong_confidence_cost_sensitive`. It
is a useful improvement hypothesis, not a promoted strategy. Two consecutive
evidence runs were identical, all original prediction values remained unchanged,
and live execution stayed disabled.

References:

- `config/ml_strong_confidence_overlay_v2.json`
- `evidence/ml_strong_confidence_overlay_batch_19/result.json`
- `evidence/ml_strong_confidence_overlay_batch_19/report.md`
- `evidence/ml_strong_confidence_overlay_batch_19/portfolio_scoreboard.csv`
- `evidence/ml_strong_confidence_overlay_batch_19/determinism_check.json`
- `research_registry/ml_candidates.json`

## Step 44 — Add cost-aware persistence and holding buffers

Batch 20 addressed Batch 19's high-cost weakness without changing its source
predictions or the frozen core. Before testing, it required two consecutive
strong-confidence decisions, positive mean buffered-ML excess over the core
during the prior 26 realized weeks at 100 bps, and the minimum of the two
confidence weights. Risk exits remained immediate. A holding buffer retained
incumbents unless a challenger cleared one quarter of the current prediction
IQR, and inverse-volatility weight updates below 10% one-way turnover were
skipped.

The buffers reduced ML annual turnover from 8.35 to 7.05. Persistence reduced
annual overlay-allocation turnover from Batch 19's 0.615 to 0.164 and average ML
exposure from 4.35% to 1.60%. The primary rule was active before risk guards in
only 13 of 151 eligible monthly decisions, making it a deliberately selective
overlay.

At 10 bps, the cost-aware portfolio returned 7.873% annually with 0.868 Sharpe
and -23.39% maximum drawdown, versus 7.643%, 0.850, and -23.39% for the core.
It gave up some of Batch 19's point return in exchange for much lower turnover.
Unlike the earlier confidence variants, both paired 20,000-sample lower bounds
were positive: 0.0026 for Sharpe difference and 0.0544 percentage points for
annual-return difference. Active decisions averaged 0.1887 future rank IC
versus 0.0608 while inactive, and the serial-bootstrap lower difference was
positive at 0.0015.

At 100 bps, annual return narrowly exceeded the core, 4.653% versus 4.645%, but
Sharpe was slightly lower, 0.5387 versus 0.5400. Thus the strengthened high-cost
Sharpe gate failed. The strategy also still lacks a survivorship-safe historical
universe and 52 untouched forward weeks. It was saved as
`provisional_cost_aware_statistically_supported`, the strongest confidence
candidate so far, but was not promoted and did not alter execution settings.

References:

- `config/ml_cost_aware_persistent_overlay_v1.json`
- `evidence/ml_cost_aware_persistent_overlay_batch_20/result.json`
- `evidence/ml_cost_aware_persistent_overlay_batch_20/report.md`
- `evidence/ml_cost_aware_persistent_overlay_batch_20/holding_buffer_audit.csv`
- `evidence/ml_cost_aware_persistent_overlay_batch_20/determinism_check.json`
- `research_registry/ml_candidates.json`

## Step 45 — Review quant-trading and reject its pair-trading concept

The next strategy catalog source, `ast-0079` (`ast-0087` is a duplicate), was
pinned at commit `611b73f2c3f577ac5b28aaa19ac8c43d3236c7a5` and inspected without
executing repository code. It uses Apache-2.0, contains 177 tracked files and 17
documented projects, but has no package manifest, dependency lock, or automated
test suite. Every project was inventoried: eight can use current free daily
data, two need new free macro/commodity sources, four require unavailable
intraday/options/analyst history, and three are methods or external projects.

The repository's pair sample was not safe to reuse. It sizes shares from the
maximum price over the complete future backtest, and its positive z-score entry
compares each z-score with that same z-score plus a positive standard deviation,
which cannot trigger. Batch 21 therefore rebuilt only the Engle-Granger idea
independently. Quarterly formation used 504 prior trading days, a 1% raw
cointegration threshold plus 5% Benjamini-Hochberg false-discovery control,
disjoint pairs, fixed 2.0/0.5 entry/exit z-scores, a 4.0 relationship-break
stop, monthly cointegration guards, next-close realization, full long-short
traded-notional costs, borrow fees, and three negative controls.

Across 126 quarterly formations the engine selected pairs in 47 quarters and
recorded 200 real/random selected-pair rows. The gross real sleeve had only
0.047% compound annual return and 0.031 Sharpe before costs. At the primary 50
bps plus 3% annual borrow assumption, it lost 1.518% annually with -0.751
Sharpe and -30.38% maximum drawdown. At 100 bps plus 8% borrow it lost 3.415%
annually. Both later evaluation windows were negative, and the random-pair and
five-day-stale controls outperformed the real rule.

Weekly correlation to the frozen core was usefully low at -0.065, but the
return source was negative. An 80/20 core-pair blend reduced common-period
Sharpe to 0.722 and its paired Sharpe lower bound was -0.071. The pair sleeve's
annual-return bootstrap lower bound was -2.223%. Every profitability and blend
gate failed; only independence passed. Two full isolated runs produced identical
evidence. The pair strategy was rejected, while the repository's remaining
feasible daily strategies stay explicitly queued.

References:

- `evidence/quant_trading_repository_batch_21/source_review.json`
- `evidence/quant_trading_repository_batch_21/strategy_inventory.csv`
- `config/etf_pairs_program_v1.json`
- `evidence/etf_pairs_batch_21/result.json`
- `evidence/etf_pairs_batch_21/report.md`
- `evidence/etf_pairs_batch_21/determinism_check.json`
- `research_registry/registry.csv`

## Step 46 — Test repository MACD and Awesome Oscillator rules

The next two feasible ideas from `je-suis-tm/quant-trading` were tested at its
pinned commit without executing repository code. The source comparison defines
MACD as an adjust-true EWM5/EWM34 close crossover and Awesome as SMA5 minus
SMA34 of median price `(high + low) / 2`. The standalone MACD's SMA10/SMA21
variant was retained as a diagnostic. Source hashes and exact defects were
recorded before results.

The Awesome source assigns two "saucer" transitions and then overwrites them
with the zero-line comparison in the same loop. Its fixed-share accounting is
price-scale dependent, and its displayed Sharpe is not an annualized
mean-over-volatility statistic. Batch 22 therefore treated the effective
zero-line rule as primary and a literal repaired saucer overlay as
diagnostic-only. No source result or parameter was optimized.

The independent implementation used the immutable free snapshot
`20260809T002313Z-0d8632e2cf759918` and the same 14 risk ETFs used by frozen
trend v4. Raw OHLC was made split-safe using each row's adjusted-close/raw-close
factor. Every decision used only the completed daily close and controlled the
next adjusted-close return. Active ETFs were equal weighted subject to a 20%
asset cap; residual exposure stayed in cash. Turnover used half-L1 changes
including cash and drifted holdings. Costs were tested at 10, 50, and 100 bps.

At 10 bps, Awesome returned 5.395% annually with 0.599 Sharpe and -18.90%
maximum drawdown; MACD returned 5.317% with 0.599 Sharpe and -22.11% drawdown.
Those superficially usable figures did not survive realistic turnover. Awesome
turned over 17.33 times annually. At the predeclared 50-bps primary cost it
lost 1.664% annually, had -0.125 Sharpe, and drew down -54.64%. MACD lost 1.914%
annually with -0.153 Sharpe and -49.32% drawdown. Awesome's paired Sharpe
advantage lower bound versus MACD was -0.103, so the apparent point advantage
was not statistically reliable and its worse drawdown failed the point gate.

At 100 bps, Awesome lost 9.836% annually, with -0.990 Sharpe and -89.55%
drawdown; both later windows were negative. The repaired source-saucer
diagnostic increased annual turnover to 53.69 and lost 18.69% annually at 50
bps. Inverted, one-day stale, five-day stale, and matched-random controls were
also run; the primary exceeded them, but this cannot rescue a negative primary
return source.

Awesome correlation was 0.586 to frozen trend v4 and 0.590 to the frozen core.
An 80/20 core-Awesome blend reduced common-period Sharpe from 0.771 to 0.619.
Drawdown improved from -23.50% to -20.60%, but because the joint gate required
both risk and risk-adjusted-return improvement, the blend point gate failed. The paired blend Sharpe
lower bound was -0.246. All promotion gates did not pass, survivorship safety
remains false, the untouched 52-week forward requirement remains incomplete,
and live trading remains disabled. MACD and Awesome are rejected in their
repository-prescribed daily forms; no conclusion is extended to unrelated,
lower-turnover trend designs.

Two independent full runs matched byte-for-byte across the six projected
evidence files after the process hash seed was explicitly fixed. All 199 project
tests passed, and all 11 files pinned by the forward protocol retained their
recorded hashes.

References:

- `config/oscillator_program_v1.json`
- `evidence/quant_trading_repository_batch_22/source_rule_review.json`
- `evidence/repository_oscillators_batch_22/result.json`
- `evidence/repository_oscillators_batch_22/scoreboard.csv`
- `evidence/repository_oscillators_batch_22/report.md`
- `evidence/repository_oscillators_batch_22/determinism_check.json`
- `src/systematic_trader/oscillator_protocol.py`
- `scripts/run_repository_oscillators_batch_22.py`

## Step 47 — Reject literal and direction-corrected Heikin-Ashi rules

Batch 23 reviewed `Heikin-Ashi backtest.py` at the same pinned repository
commit and recorded its SHA-256 before results. The source uses the standard
recursive Heikin-Ashi transform and a three-entry position limit, but its
claimed long rule triggers after two bearish candles with no upper wick while
its exit triggers after two bullish candles with no lower wick. This reverses
the momentum interpretation described in its own documentation. The source
also uses nominal 100-share entries, exact float equality, chained state
mutation, a final-50-observation portfolio slice mixed with full-history
statistics, nonstandard risk statistics, and no costs or next-period audit.

Two candidates were therefore fixed before testing: `source_exact` preserved
the repository's literal direction, and `direction_corrected` exchanged the
bullish and bearish entry/exit roles. Both retained the three-unit state
concept. Split-adjusted OHLC, signal-at-close/next-close realization, 20% asset
caps, explicit cash, drift-aware half-L1 turnover, 10/50/100-bps costs, one-day
and five-day stale states, and deterministic matched-random state controls were
used. The two-candidate blend uncertainty threshold used a familywise 5% level,
or 2.5% per candidate.

At 10 bps, the literal source returned 2.926% annually with 0.295 Sharpe and
-40.15% maximum drawdown. The direction-corrected interpretation returned only
0.778% with 0.128 Sharpe and -35.60% drawdown. Neither was a credible low-cost
candidate even before the primary friction test.

At 50 bps, the literal rule's 43.59 annual turnover produced -13.555% annual
return, -1.134 Sharpe, and -95.75% maximum drawdown. At 100 bps it returned
-30.523% annually. Its 80/20 core blend Sharpe was 0.299 versus 0.771 for the
core; the familywise paired lower Sharpe difference was -0.603.

The direction-corrected rule still turned over 37.17 times annually. At 50 bps
it returned -13.155% with -1.347 Sharpe and -95.30% drawdown; at 100 bps it
returned -27.915%. Its five-day-stale control outperformed it. The 80/20 blend
Sharpe fell to 0.326 and its familywise paired lower Sharpe difference was
-0.602. Correlations to the core/trend were 0.490/0.541, but independence could
not rescue a deeply negative return source.

Neither candidate passed performance, stress, or blend gates. The corrected
candidate also failed controls. Survivorship safety and the untouched 52-week
forward requirement remain false, and live trading remains disabled. Two full
runs matched byte-for-byte across all nine projected evidence files.

References:

- `config/heikin_ashi_program_v1.json`
- `evidence/quant_trading_repository_batch_23/source_rule_review.json`
- `evidence/heikin_ashi_batch_23/result.json`
- `evidence/heikin_ashi_batch_23/scoreboard.csv`
- `evidence/heikin_ashi_batch_23/report.md`
- `evidence/heikin_ashi_batch_23/determinism_check.json`
- `src/systematic_trader/heikin_ashi_protocol.py`
- `scripts/run_heikin_ashi_batch_23.py`

## Step 48 — Reject both repository Parabolic SAR acceleration variants

Batch 24 pinned and reviewed `Parabolic SAR backtest.py`. The source implements
a signed-duration recursive state, a constrained candidate SAR, an extreme
point, an accelerating factor, and a separate `real sar` used for its long/cash
position. The default initial/increment/cap is 0.02/0.02/0.20, while a source
comment proposes 0.01 steps for equities. Both parameterizations were fixed
before results, with the equity interpretation using 0.01 initial and increment
and retaining the 0.20 cap.

The repository has an unusual initialization: an uptrend starts from the prior
high and a downtrend from the prior low, opposite its own description of SAR
being below/above price. Its zero-initialized first row also creates a synthetic
long before recursive state exists. Batch 24 preserved the subsequent source
recursion and reversal `real sar`, ignored the invalid first-row position,
split-adjusted OHLC, and applied each completed-bar signal only to the next
adjusted close. Equal active weights, a 20% asset cap, cash, drift-aware
turnover, 10/50/100-bps costs, inverted and stale signals, and a fixed
asset-label permutation control were applied.

At 10 bps the default rule returned only 0.739% annually with 0.123 Sharpe and
-39.46% maximum drawdown. Its fixed asset-permutation control returned 4.768%
with 0.493 Sharpe. At the 50-bps primary cost, 46.74 annual turnover reduced the
default rule to -16.454% annual return, -1.605 Sharpe, and -97.99% drawdown. At
100 bps it lost 33.906% annually. Its 80/20 core blend Sharpe fell from 0.771
to 0.232, with a familywise paired lower Sharpe difference of -0.718.

The slower equity-step rule remained weak at 10 bps: 2.444% annual return,
0.291 Sharpe, and -31.62% drawdown. Its permuted control returned 4.715% with
0.511 Sharpe. At 50 bps, 36.61 annual turnover produced -11.525% annual return,
-1.118 Sharpe, and -93.10% drawdown. At 100 bps it lost 26.360% annually. Its
80/20 blend Sharpe was 0.372 and the paired lower Sharpe difference was -0.558.

Both candidates failed primary performance, stress, controls, blend point, and
familywise uncertainty gates. Their lower correlations to the core and trend
did not compensate for negative returns. Neither was promoted; survivorship
safety and the 52-week untouched forward requirement remain incomplete, and
live execution remains disabled. Two full runs matched byte-for-byte across
all nine projected evidence files.

References:

- `config/parabolic_sar_program_v1.json`
- `evidence/quant_trading_repository_batch_24/source_rule_review.json`
- `evidence/parabolic_sar_batch_24/result.json`
- `evidence/parabolic_sar_batch_24/scoreboard.csv`
- `evidence/parabolic_sar_batch_24/report.md`
- `evidence/parabolic_sar_batch_24/determinism_check.json`
- `src/systematic_trader/parabolic_sar_protocol.py`
- `scripts/run_parabolic_sar_batch_24.py`

## Step 49 — Reject repository Bollinger bottom-W for zero signal coverage

Batch 25 pinned and reviewed the repository's Bollinger Bands Pattern
Recognition script. It computes a 20-observation simple mean and sample standard
deviation, uses bands at plus/minus two deviations, and searches backward across
75 observations for five nodes of a bottom-W. Its current observation must
finish above the upper band. All searches are backward-looking, so the pattern
logic itself does not read future indices; Batch 25 still delayed execution to
the next adjusted close.

The source hard-codes `alpha=0.0001` for every node equality and `beta=0.0001`
for the contraction exit. Those are absolute GBP/USD price units from its local
input file, not portable quantities. Two interpretations were fixed before
results: `source_literal_fx_units` retained the absolute values, while
`scale_normalized` treated both values as fractions of contemporaneous price or
middle band. The 20/75 windows, search ordering, entry, and exit were otherwise
unchanged. No tolerance was widened after coverage was observed.

Across 14 ETFs and more than 21 common years, both versions generated exactly
zero entries. They therefore had zero exposure, turnover, return, volatility,
and drawdown at every cost level. This is not evidence of a safe strategy or a
profitable cash allocation; it is a failed signal-coverage test. Inverted,
stale, and fixed asset-permutation controls were still constructed, but no
profitability comparison can rehabilitate a primary rule that never trades.

An 80/20 core-pattern blend was mechanically 80% core and 20% zero-return cash.
Its common-period Sharpe was 0.768 versus 0.774 for the full core allocation.
Familywise paired lower Sharpe differences were -0.0075 for the literal rule
and -0.0074 for the normalized rule. Coverage, performance, stress, controls,
blend, survivorship, and untouched-forward gates failed. Neither candidate was
promoted, and live trading remains disabled.

Two complete runs matched byte-for-byte across all nine projected evidence
files. The result rejects these fixed repository rules on the present ETF
universe; designing a looser tolerance would be a new, separately predeclared
strategy rather than validation of this source.

References:

- `config/bollinger_pattern_program_v1.json`
- `evidence/quant_trading_repository_batch_25/source_rule_review.json`
- `evidence/bollinger_pattern_batch_25/result.json`
- `evidence/bollinger_pattern_batch_25/scoreboard.csv`
- `evidence/bollinger_pattern_batch_25/report.md`
- `evidence/bollinger_pattern_batch_25/determinism_check.json`
- `src/systematic_trader/bollinger_pattern_protocol.py`
- `scripts/run_bollinger_pattern_batch_25.py`

## Step 50 — Reject all repository RSI interpretations

Batch 26 pinned and reviewed `RSI Pattern Recognition backtest.py`. The file
contains two separate ideas: the code executed by its main block takes daily
long positions below RSI 30 and short positions above RSI 70, while an unused
function attempts to identify a head-and-shoulders pattern and short it. The
pattern function says that its five nodes are RSI nodes but actually searches
`Close` at every node. Batch 26 therefore predeclared four candidates before
observing results: literal long/short thresholds, a long-only safety variant,
the source price-pattern implementation, and the intended RSI-pattern
interpretation. The repository's 14-period smoothed RSI initialization and its
pattern ordering, 0.2 node tolerance, 25-day search period, four-RSI-point stop,
and five-day maximum holding period were preserved where applicable.

Every signal used only completed information and was applied to the next
adjusted close. The portfolio used equal active weights, a 20% per-asset cap,
cash, drift-aware full turnover, explicit short borrow, and 10/50/100-bps cost
scenarios. Each candidate also faced one- and five-session stale signals, an
inverted signal, and a fixed asset-label permutation control. Four-candidate
familywise uncertainty used a per-candidate one-sided alpha of 0.0125.

The long/short threshold rule generated 2,100 entries but returned -14.64%
annually at the primary 50-bps cost plus 3% borrow, with -2.139 Sharpe and
-96.70% maximum drawdown. Even at 10 bps it lost 0.62% annually. Its 80/20 core
blend Sharpe was 0.303 versus 0.771 for the core. The long-only threshold rule
was the least weak variant: at 10 bps it returned 2.11% annually with 0.349
Sharpe and -22.49% drawdown, but at the primary cost its annual return became
-3.00%, Sharpe -0.427, and drawdown -56.54%. Its blend Sharpe was 0.629.

The literal source price pattern generated 702 entries and was decisively
negative: -8.11% annual return, -2.579 Sharpe, and -83.82% drawdown at primary
costs. The corrected RSI pattern generated only three entries across more than
21 common years and none in either 2016-2020 or 2021-present, failing minimum
coverage. Its apparently tiny drawdown therefore reflects near-total cash
exposure, not useful safety. All four familywise paired blend lower bounds were
negative, and no candidate improved the core blend.

All candidates failed the complete promotion gate through some combination of
performance, stress, controls, coverage, blend, survivorship, and untouched
forward evidence. None was promoted and live trading remains disabled. Two
complete runs matched byte-for-byte across all 15 projected evidence files.

References:

- `config/rsi_pattern_program_v1.json`
- `evidence/quant_trading_repository_batch_26/source_rule_review.json`
- `evidence/rsi_pattern_batch_26/result.json`
- `evidence/rsi_pattern_batch_26/scoreboard.csv`
- `evidence/rsi_pattern_batch_26/report.md`
- `evidence/rsi_pattern_batch_26/determinism_check.json`
- `src/systematic_trader/rsi_pattern_protocol.py`
- `scripts/run_rsi_pattern_batch_26.py`

## Step 51 — Reject repository Shooting Star after removing lookahead

Batch 27 pinned and reviewed `Shooting Star backtest.py`. The repository rule
requires a red candle, a nearly absent lower wick, a small body, an upper wick
at least twice the body, and two non-decreasing closes into the star. It also
requires the following candle's high and close to remain below the star's high
and close. The source nevertheless puts the short on the earlier star row,
which earns a return before confirmation is knowable. Its body threshold also
uses the signed mean body over the entire dataset, so future candles change
historical signals. The source backtest is therefore directly lookahead-biased
and its return was intentionally not reproduced or considered.

Three causal candidates were fixed before results. `source_causal_confirmed`
replaced the full-sample body statistic with the absolute expanding signed mean
while preserving the source mathematics and delayed execution until after the
next-candle confirmation. `normalized_confirmed` used the expanding mean of
absolute body as a fraction of price and retained causal confirmation.
`normalized_unconfirmed` used the normalized body but entered after the star
close without confirmation. All retained the source 0.2 lower-wick ratio, 0.5
body multiplier, two-times upper wick, 5% close stop/profit threshold, and
seven-session maximum holding period. Same-asset signals could not stack.

Signals used split-adjusted OHLC and only completed bars. The portfolio used
equal active magnitudes, a 20% absolute asset cap, maximum gross exposure of
one, cash collateral, drift-aware full traded-asset turnover, explicit short
borrow, and 10/50/100-bps costs. Each candidate faced one- and five-session
stale states, inverted direction, and a fixed asset-label permutation. The
three-candidate familywise one-sided alpha was 1/60.

The source-faithful causal candidate produced zero entries. This demonstrates
that the source's signed-mean body definition is not portable to the current
adjusted ETF panel; zero return and drawdown are failed coverage, not safety.
The normalized confirmed rule produced only 18 entries, below the predeclared
minimum of 20. It lost 0.07% annually even at 10 bps and, at the primary 50-bps
cost plus 3% borrow, returned -0.21% annually with -0.463 Sharpe and -5.11%
drawdown. Its 80/20 core blend Sharpe was 0.760 versus 0.771 for the core.

The normalized unconfirmed rule produced 40 entries and passed the mechanical
coverage requirement, but it lost 0.21% annually at 10 bps. Under primary costs
it returned -0.50% annually with -0.651 Sharpe and -11.11% drawdown. Under the
100-bps plus 8% borrow stress it returned -0.92% annually with -1.036 Sharpe.
Its core and trend correlations were -0.080 and -0.112, but its blend Sharpe
fell to 0.752. The familywise paired lower Sharpe difference was -0.0293.

No candidate passed performance, stress, control, blend, survivorship, and
untouched-forward gates together. None was promoted and live trading remains
disabled. Daily accounting identities were exact, gross exposure remained at
or below one, two complete runs matched byte-for-byte across all 12 projected
evidence files, and the frozen forward portfolio was not modified.

References:

- `config/shooting_star_program_v1.json`
- `evidence/quant_trading_repository_batch_27/source_rule_review.json`
- `evidence/shooting_star_batch_27/result.json`
- `evidence/shooting_star_batch_27/scoreboard.csv`
- `evidence/shooting_star_batch_27/report.md`
- `evidence/shooting_star_batch_27/determinism_check.json`
- `src/systematic_trader/shooting_star_protocol.py`
- `scripts/run_shooting_star_batch_27.py`

## Step 52 — Add calibrated Monte Carlo risk evidence to the frozen portfolio

Batch 28 pinned and reviewed the repository's `Monte Carlo project`. Its code
estimates training log-return mean and variance, generates independent Gaussian
geometric-Brownian paths, selects the random path with the smallest price-level
error against the already observed training history, and evaluates that path's
future direction. The source correctly warns that simulation count cannot fix
a misspecified distribution and that history cannot describe truly unseen
events. The selected best-fit path was treated as a diagnostic only, never as
an allocation signal.

The frozen `covariance_minimum_variance_v1` portfolio was reconstructed from
its pinned source snapshot and 50-bps rules without invoking any mutating build
workflow. Its 1,126 weekly observations reproduced the Batch 07 baseline within
1e-12: 6.58% annual return, 0.769 Sharpe, 8.81% annual volatility, and -23.50%
maximum drawdown. The production risk program was fixed before results at
30,000 paths for one-, three-, and five-year horizons. It compared the source
Gaussian model, IID empirical resampling, circular 13-week blocks, 13-week
blocks after removing half the positive historical mean, and five-year paths
forced to begin with the worst historical 13-week block.

The primary five-year block model estimated a 3.54% chance of ending below
starting wealth and a 1.57% chance of experiencing at least a 30% drawdown. Its
fifth-percentile terminal return was +3.07%, although the mean of the worst 5%
was -4.95%; the distinction prevents a single percentile from hiding the lower
tail. Under the positive-mean haircut, the chance of ending below starting
wealth rose to 18.83%, the fifth-percentile terminal return fell to -13.43%,
and the chance of a 40% drawdown was 0.46%.

The worst observed portfolio block was 2019-12-27 through 2020-03-20 and lost
21.23%. Every forced-crash path experienced at least a 20% drawdown by design.
Across the subsequent block-resampled five-year paths, 75.91% recovered initial
wealth and 33.82% still ended below it. The median maximum drawdown was -25.54%,
the fifth-percentile drawdown was -37.81%, and 3.01% experienced a drawdown of
at least 40%.

Expanding, strictly past-only annual calibration used 5,000 paths at each of 16
origins. The nominal 90% block interval covered 87.5% of realized one-year
terminal returns and 75.0% of realized maximum drawdowns, meeting the fixed
minimums. All four predeclared risk gates passed. This is conditional evidence
that the frozen portfolio's historical risk is acceptable under the stated
scenarios, not a guarantee, a promotion, or completion of its 52-week forward
clock.

The source best-fit diagnostic scored 50%, 50%, and 75% direction accuracy at
100, 500, and 1,000 simulations. The largest run's original absolute gate was
12/16 with a 50.5% Wilson lower bound. A post-result methodological review found
that 12/16 realized years were positive, so always predicting positive also
scored 75%. An explicit amendment therefore requires strict improvement over
the majority-direction benchmark. The source forecast has no demonstrated
edge and was not incorporated.

Two process runs initially differed around 1e-16 because of floating-point
evaluation order in the frozen reconstruction. The same amendment established
a 12-decimal simulation boundary, far below one basis point. Two subsequent
complete runs then matched byte-for-byte across all seven projected evidence
files. No frozen portfolio or forward-protocol file was changed, and live
execution remains disabled.

References:

- `config/monte_carlo_risk_program_v1.json`
- `evidence/quant_trading_repository_batch_28/source_rule_review.json`
- `evidence/monte_carlo_risk_batch_28/post_result_methodological_amendment.json`
- `evidence/monte_carlo_risk_batch_28/result.json`
- `evidence/monte_carlo_risk_batch_28/path_risk_summary.csv`
- `evidence/monte_carlo_risk_batch_28/rolling_calibration.csv`
- `evidence/monte_carlo_risk_batch_28/source_best_fit_summary.csv`
- `evidence/monte_carlo_risk_batch_28/report.md`
- `evidence/monte_carlo_risk_batch_28/determinism_check.json`
- `src/systematic_trader/monte_carlo_risk.py`
- `scripts/run_monte_carlo_risk_batch_28.py`

## Step 53 — Qualify ml-quant-trading as an isolated research component

The next repository selection compared the catalog's strongest genuinely new
ML/factor candidate with AlphaGen and the already overlapping portfolio
libraries skfolio and PyPortfolioOpt. `initial-d/ml-quant-trading` was selected
because its 213 mask-aware factors, public ETF reproduction, model pipeline,
and bias-aware data structures add capabilities not already covered by the
frozen portfolio allocator. The source was pinned at commit
`867e8dfe628b1d0ea2af987ec6f74c32c645f63e`, version 0.2.6, under the MIT
license.

A reusable Linux/arm64 Podman image was built from that exact source. All 97
upstream tests passed in 40.41 seconds. A separate seeded technical audit then
computed a 180-date by 40-asset by 213-factor tensor and passed factor
finiteness, deterministic synthetic generation, poisoned-mask isolation,
forward-label boundary, lagged-weight execution, and transaction-cost scaling
checks. The repository's complete synthetic demo also ran, but returned -8.34%
annually with -0.421 Sharpe and -27.58% maximum drawdown. This was recorded as
an engineering smoke test only, not market evidence.

The source's own reality check says that its synthetic demo is not alpha, its
public ETF experiment is small, its paper-style data are restricted, and the
project is research infrastructure rather than a production trading system.
The registry decision is therefore `qualified_sandbox_component`, not a
strategy promotion or profitability claim. Live trading remains disabled.

References:

- `evidence/ml_quant_trading_repository_batch_29/source_review.json`
- `evidence/ml_quant_trading_repository_batch_29/container_validation.json`
- `research_registry/registry.csv`

## Step 54 — Qualify two source-preselected ETF factors without mining 213 winners

Before viewing market results, Batch 30 limited performance screening to the
six factors already named in the repository's public ETF script: `best_001`,
`best_002`, `original_001`, `stock_001`, `add_015`, and `old_042`. All 213
registered factors were still executed, but only for mechanical coverage and
finiteness. This separation prevents selecting the luckiest result from a
large factor zoo after seeing the test period.

The pinned source implementation ran inside Podman against the immutable
`20260809T002313Z-0d8632e2cf759918` snapshot and a fixed 14-ETF universe.
Split-adjusted OHLC and adjusted close were used. Because the free snapshot has
no VWAP, the program predeclared adjusted typical price as a proxy. Daily
cross-sectional Spearman IC measured each closing factor against the next
adjusted-close return. This is a signal-quality diagnostic, not an executable
close-price return. The universe is a fixed survivor list, so the result
remains retrospective rather than production-grade.

Factor direction was learned only from 2005-2015. Validation covered 2016-2020
and the retrospective test covered 2021 through 2026-08-07. Each candidate
faced one- and five-session staleness, inversion, fixed asset permutation, and
fixed forward-return permutation controls. A 65-session circular block
bootstrap used 20,000 replicates and a Bonferroni-adjusted one-sided alpha of
0.00833 across six candidates. Passing also required adequate observations,
development IC magnitude, positive validation and test IC, and superiority to
the fixed controls.

All 213 factors completed the mechanical audit with no non-finite values in
valid cells. Two of six candidates passed every gate. `best_002`, the
10-session time-series rank of negative close location, had development IC
+0.0466, validation signed IC +0.0328, test signed IC +0.0115, and a combined
familywise lower bound of +0.0036. `original_001`, cross-sectionally standardized
20-session close volatility, had development IC +0.0258, validation +0.0377,
test +0.0199, and lower bound +0.0138. Its combined IC of +0.0283 only narrowly
exceeded the absolute five-session stale control at +0.0255, so turnover-aware
portfolio evidence is especially important.

`best_001` failed because test IC turned negative. `stock_001` and `add_015`
failed the development threshold and uncertainty requirements. `old_042`
failed its familywise lower bound and permutation-control comparison. No other
factor was inspected for profitability. Only `best_002` and `original_001` are
authorized for a separately predeclared next-session portfolio experiment;
neither is yet a promoted strategy, and live trading remains disabled. Two
complete evaluation passes reproduced all seven projected evidence artifacts
byte-for-byte.

References:

- `config/mlquant_etf_factor_ic_program_v1.json`
- `evidence/mlquant_factor_ic_batch_30/result.json`
- `evidence/mlquant_factor_ic_batch_30/ic_summary.csv`
- `evidence/mlquant_factor_ic_batch_30/all_factor_audit.csv`
- `evidence/mlquant_factor_ic_batch_30/report.md`
- `evidence/mlquant_factor_ic_batch_30/artifact_hashes.json`
- `src/systematic_trader/factor_ic_protocol.py`
- `scripts/export_mlquant_factors_batch_30.py`
- `scripts/run_mlquant_factor_ic_batch_30.py`

## Step 55 — Reject weekly portfolios built from the two qualified factors

Batch 31 moved `best_002` and `original_001` from rank-IC diagnostics into a
fully costed portfolio experiment. Two constructions were fixed before
returns were viewed: equal-weight top five and inverse-20-session-volatility
top five with a 30% asset cap. Both averaged the repository's two
cross-sectional z-scores, selected only jointly valid ETFs, held residual cash,
and prohibited leverage and shorting.

The signal observed at one completed weekly close was not entered until the
following weekly close and earned returns only thereafter. Turnover was the
half-L1 change from holdings after market drift, including cash. Costs were
tested at 10, 50, and 100 bps. One- and five-additional-week stale signals,
inverted ranking, and a fixed asset permutation were evaluated at the primary
50-bps cost. Both candidates were also blended 80/20 with the exactly
reconstructed frozen core and compared through 20,000 paired 13-week block
bootstrap samples with a two-candidate familywise correction.

An initial accounting audit found that market-wide as-of dates left 23-25
primary ETF returns unpriced on dates where an individual ETF had a missing
quote. The preliminary results were discarded. Batch 31 changed the return
lookup to each asset's own latest available observation and constrained the
permutation control to assets with sufficient contemporaneous history. The
accepted run had zero unpriced exposures in every primary and control path.

The equal-weight portfolio returned +8.28% annually with 0.578 Sharpe at 10
bps, but annual turnover was 23.19 times capital. At the predeclared 50-bps
cost it fell to -1.31% annually, -0.002 Sharpe, and -64.46% maximum drawdown;
at 100 bps it returned -12.14% annually. Its 2016-2020 return was -3.57%
annually, although 2021-present was +2.71%. The 80/20 blend Sharpe was 0.569
versus 0.769 for the core, and the familywise paired lower Sharpe-difference
bound was -0.333.

The inverse-volatility portfolio returned +7.40% annually with 0.550 Sharpe at
10 bps, but turnover rose to 26.99 times capital. At 50 bps it returned -3.60%
annually with -0.168 Sharpe and -71.13% drawdown; at 100 bps it returned
-15.80%. Its validation-period return was -5.39% and its later test return was
only +0.34% annually. The 80/20 blend Sharpe was 0.525 and the paired lower
Sharpe-difference bound was -0.376.

Both candidates beat their stale, inverted, and permutation controls, so the
factor ordering contains some information. That information is too weak and
short-lived to survive weekly turnover at plausible costs. Neither candidate
passed the historical gate, neither was saved as a portfolio challenger, and
neither was promoted. Seven projected artifacts reproduced byte-for-byte
after applying the same 12-decimal core-simulation boundary approved in Batch
28. All frozen files remained intact and live trading remains disabled.

References:

- `config/mlquant_factor_portfolio_program_v1.json`
- `evidence/mlquant_factor_portfolio_batch_31/result.json`
- `evidence/mlquant_factor_portfolio_batch_31/scoreboard.csv`
- `evidence/mlquant_factor_portfolio_batch_31/report.md`
- `evidence/mlquant_factor_portfolio_batch_31/artifact_hashes.json`
- `src/systematic_trader/factor_portfolio_protocol.py`
- `scripts/export_mlquant_portfolio_inputs_batch_31.py`
- `scripts/run_mlquant_factor_portfolio_batch_31.py`

## Step 56 — Confirm 20-session factor persistence but reject four slower portfolios

Batch 32 predeclared factor-decay horizons of 1, 2, 5, 10, and 20 sessions and
four lower-turnover portfolios before examining any new results. The decay
test used the equal mean of qualified `best_002` and `original_001` repository
z-scores. The horizon was selected only by 2005-2015 development IC, with
2016-2020 validation and 2021-present retained as later evidence. A 20,000
replicate, 65-session circular block bootstrap used a five-horizon familywise
one-sided alpha of 0.05.

The development window selected 20 sessions with mean rank IC +0.0543. The
same horizon produced +0.0694 validation IC and +0.0254 retrospective-test IC;
the combined later-period familywise lower bound was +0.0084. The qualified
signals therefore persist longer than the original one-session test implied.
Their failure as weekly portfolios is principally an implementation, turnover,
and risk problem rather than immediate disappearance of rank information.

Monthly equal weight reduced annual turnover from 23.19 to 5.84 times capital.
At 50 bps it returned +5.24% annually with 0.399 Sharpe and -52.80% drawdown.
Monthly inverse volatility turned over 6.74 times, returned +4.09%, had 0.338
Sharpe, and drew down -50.67%. Both remained positive at 100 bps but failed the
primary risk gate, their controls, and their frozen-core blends.

The four-week, 0.5-score buffered equal-weight rule was the least weak
construction. It replaced at most one ETF per weekly review and traded only on
membership changes. Turnover fell to 7.44 times capital. At 50 bps it returned
+5.94% annually with 0.458 Sharpe and -44.06% drawdown; 2016-2020 returned
+4.81% and 2021-present +10.18%. It remained positive at 100 bps and beat its
stale, inverted, and permutation controls. It nevertheless missed the 0.50
Sharpe and -35% drawdown thresholds, and its 80/20 blend Sharpe was 0.724
versus 0.769 for the frozen core. The familywise paired lower blend
Sharpe-difference bound was -0.180.

Buffered inverse volatility turned over 9.46 times, returned +4.37% with 0.377
Sharpe and -40.37% drawdown at 50 bps, and became negative at 100 bps. Its
blend also failed. No construction passed all historical gates and none was
promoted. The buffered equal rule was retained in the ML candidate registry as
`provisional_repository_factor_fragile` because it preserves significant
horizon evidence, later-period returns, control separation, and materially
lower turnover, while its failed risk and blend gates remain explicit.

All primary and control paths had zero unpriced exposures and exact accounting
identities. Two complete runs reproduced all nine projected artifacts
byte-for-byte. Frozen files remained intact and live trading remains disabled.

References:

- `config/mlquant_factor_decay_turnover_program_v1.json`
- `evidence/mlquant_factor_decay_turnover_batch_32/result.json`
- `evidence/mlquant_factor_decay_turnover_batch_32/decay_summary.csv`
- `evidence/mlquant_factor_decay_turnover_batch_32/scoreboard.csv`
- `evidence/mlquant_factor_decay_turnover_batch_32/report.md`
- `evidence/mlquant_factor_decay_turnover_batch_32/artifact_hashes.json`
- `research_registry/ml_candidates.json`
- `src/systematic_trader/factor_decay_turnover_protocol.py`
- `scripts/run_mlquant_factor_decay_turnover_batch_32.py`

## Step 57 — Reject confidence- and risk-gated factor overlays

Batch 33 tested whether the provisional buffered factor sleeve could add value
only when its signals appeared strong and market conditions appeared safer.
Maximum allocations of 5%, 10%, and 15% were fixed before results. Confidence
required the mean combined score of the selected five ETFs to exceed its
expanding prior-week 60th percentile, with at least three ETFs receiving
positive z-scores from both qualified factors. Risk required SPY to be above
its trailing 200-session mean and its 20-session volatility to remain below
the expanding prior-week 80th percentile. Both expanding thresholds required
52 prior weekly observations.

The decision at a weekly close used the latest completed data available by the
previous weekly decision and earned only the following week's return. Matching
10/50/100-bps net returns were reconstructed for the frozen core and buffered
factor sleeve. Top-level allocation changes paid the same scenario cost using
drift-aware two-sleeve turnover. Always-on, shuffled-confidence, and
inverted-risk controls were predeclared. Three-candidate familywise uncertainty
used 20,000 paired 13-week blocks and a one-sided alpha of 1/60 per candidate.

Confidence was active in 472 of 1,126 weeks, the market-risk gate in 753, and
both jointly in 331 weeks, or 29.4%. The 5% overlay was the least damaging but
still reduced 50-bps annual return from 6.58% for the matching core to 5.97%,
Sharpe from 0.769 to 0.701, and drawdown from -23.50% to -23.60%. At 100 bps it
returned 3.92% versus 5.05% for the core. Its paired familywise lower Sharpe
difference was -0.090.

The 10% overlay returned 5.35% with 0.634 Sharpe and -23.69% drawdown. The 15%
overlay returned 4.74% with 0.567 Sharpe and -23.79% drawdown. Both later
windows also lagged the matching core at every cap. All three conditional
overlays had lower Sharpe than the always-on, shuffled-confidence, and
inverted-risk controls. The proposed confidence/risk gate therefore has no
evidence of selecting better weeks; increasing allocation simply increased
the damage.

No overlay passed a historical gate, none was saved as a challenger, and none
was promoted. The underlying buffered factor rule remains recorded as a
fragile diagnostic candidate, now annotated with this rejected follow-up.
Two complete runs reproduced all seven projected artifacts byte-for-byte,
accounting identities were exact, frozen files remained intact, and live
trading remains disabled.

References:

- `config/mlquant_conditional_overlay_program_v1.json`
- `evidence/mlquant_conditional_overlay_batch_33/result.json`
- `evidence/mlquant_conditional_overlay_batch_33/gate_decisions.csv`
- `evidence/mlquant_conditional_overlay_batch_33/scoreboard.csv`
- `evidence/mlquant_conditional_overlay_batch_33/report.md`
- `evidence/mlquant_conditional_overlay_batch_33/artifact_hashes.json`
- `research_registry/ml_candidates.json`
- `src/systematic_trader/conditional_overlay.py`
- `scripts/run_mlquant_conditional_overlay_batch_33.py`

## Step 58 — Add repository factors to matched nested walk-forward ML

Batch 34 tested the two qualified repository factors as model inputs rather
than direct portfolio weights. The experiment fixed a matched feature-ablation
design before training: one engine received the existing 11 causal technical
features and the other received the identical rows plus `best_002` and
`original_001`. Both predicted the unchanged four-week cross-sectional
relative-return target, which matches Batch 32's development-selected
20-session persistence horizon.

The repository factor panel covers the fixed 14-ETF research universe while
the older Batch 16 dataset covers more assets. Joining at each row's existing
one-week-lagged `feature_asof_date` therefore reduced the common sample from
8,324 to 3,252 asset-month rows. This restriction was applied equally to both
engines. Every decision retained at least nine assets and the join had zero
timing violations. Results are comparable only between these matched engines,
not directly with the broader-universe Batch 17 headline.

A feature-configurable wrapper ran the unchanged Batch 17 engine logic in a
pinned scikit-learn 1.9 Podman image. Each engine performed 2,924 fits across
15 embargoed calendar-year outer folds, three model families, five seeds,
three-year inner selection, and shuffled-label, shuffled-feature, one-month
stale, and three-month stale controls. All embargoes passed.

The 13-feature model improved every portfolio point estimate. At 10 bps its
annual return was 9.45% versus 8.76% for the matched 11-feature baseline,
Sharpe was 0.796 versus 0.749, drawdown was -24.21% versus -24.38%, and annual
turnover was 6.38 versus 6.55 times capital. At 50 bps, Sharpe improved from
0.533 to 0.589. At 100 bps, it improved from 0.264 to 0.328 while returning
3.34% annually; validation and retrospective-test returns were +2.90% and
+5.31%.

The improvement was not statistically established. Augmented mean monthly IC
was +0.0374 versus +0.0397 for the matched baseline, and its adjusted lower IC
bound was -0.0041. The paired 10-bps mean Sharpe difference was +0.046 but its
lower bound was -0.073; at 50 bps the mean difference was +0.054 with a -0.064
lower bound. The augmented model passed its shuffled controls and 13 of 15
outer folds had positive IC, but it failed the adjusted-IC and paired-ablation
gates.

The model was saved as
`mlquant-walk-forward-feature-augmentation-v1` with status
`provisional_repository_feature_augmentation`. It is promising enough for
future independent evidence but is not promoted. A deterministic evaluation
repeat using the frozen engine outputs reproduced all 17 artifacts exactly.
Frozen files remained intact and live trading remains disabled.

References:

- `config/mlquant_walk_forward_feature_program_v1.json`
- `evidence/mlquant_walk_forward_feature_batch_34/dataset_audit.json`
- `evidence/mlquant_walk_forward_feature_batch_34/result.json`
- `evidence/mlquant_walk_forward_feature_batch_34/portfolio_scoreboard.csv`
- `evidence/mlquant_walk_forward_feature_batch_34/report.md`
- `evidence/mlquant_walk_forward_feature_batch_34/artifact_hashes.json`
- `research_registry/ml_candidates.json`
- `containers/robust_cross_sectional_ml_configurable.py`
- `scripts/build_mlquant_augmented_ml_dataset_batch_34.py`
- `scripts/run_mlquant_walk_forward_feature_batch_34.py`

## Step 59 — Confirm repository features on the full free ETF universe

Batch 35 performed the predeclared final historical confirmation of the
`initial-d/ml-quant-trading` feature integration. It expanded `best_002` and
`original_001` from Batch 34's 14-ETF factor panel to every symbol in the
frozen 35-ETF free universe while holding the target, folds, embargoes, model
families, hyperparameters, seeds, controls, portfolio construction, costs, and
promotion gates unchanged. The program also fixed a stopping rule before
seeing results: failure of either the adjusted rank-IC comparison or paired
10-bps Sharpe gate would close the track to more tuning on the same history.

The pinned repository code generated 295,330 daily asset rows inside the
qualified Podman image. All 8,324 Batch 16 asset-month observations matched,
covering 35 assets with zero dropped rows and zero timing violations. Every
decision retained at least 24 assets. The matched baseline and augmented
engines each completed 2,924 fits across the same 15 embargoed outer folds;
all embargo checks passed.

The full-universe result reversed the restricted-universe point improvement.
At 10 bps, the unchanged 11-feature baseline returned 12.11% annually with
0.855 Sharpe and -32.43% maximum drawdown. The 13-feature augmented model
returned 11.36% with 0.825 Sharpe and -28.83% drawdown. The factors therefore
improved the historical drawdown by 3.60 percentage points and reduced annual
turnover from 8.35 to 8.07 times capital, but gave up 0.75 percentage points of
annual return and 0.029 Sharpe.

The underperformance persisted at higher assumed costs. At 50 bps, augmented
Sharpe was 0.598 versus 0.625 for baseline; at 100 bps it was 0.314 versus
0.338. Augmented validation and retrospective-test returns remained positive,
but its full 100-bps return was 3.55% versus 3.98% for baseline. Mean monthly
rank IC was 0.0653 versus 0.0696. Although the augmented adjusted IC lower
bound itself was positive at 0.0291, the predeclared comparison required its
mean IC to exceed baseline, so the rank-IC gate failed.

The paired evidence was also adverse. At 10 bps the mean Sharpe difference
was -0.035 and its one-sided lower bound was -0.199; the mean annual-return
difference was -0.76 percentage points. The augmented model passed embargo,
controls, drawdown, and fold-stability gates, but failed rank IC, 10-bps and
50-bps portfolio advantage, stress advantage, and both structural final gates.
It was not promoted.

Per the fixed stopping rule, the repository feature-augmentation track is now
recorded as historically promising but unproven and closed to further tuning
on this same dataset. This does not prove the factors can never work; it means
new consideration requires genuinely independent data, a point-in-time
universe, or a materially different predeclared hypothesis rather than more
parameter searching. A second evaluation from frozen engine outputs reproduced
the complete artifact hash manifest byte-for-byte. Frozen files remained
intact and live trading remains disabled.

References:

- `config/mlquant_full_universe_walk_forward_confirmation_v1.json`
- `evidence/mlquant_full_universe_walk_forward_batch_35/factor_export_metadata.json`
- `evidence/mlquant_full_universe_walk_forward_batch_35/dataset_audit.json`
- `evidence/mlquant_full_universe_walk_forward_batch_35/result.json`
- `evidence/mlquant_full_universe_walk_forward_batch_35/portfolio_scoreboard.csv`
- `evidence/mlquant_full_universe_walk_forward_batch_35/report.md`
- `evidence/mlquant_full_universe_walk_forward_batch_35/artifact_hashes.json`
- `research_registry/ml_candidates.json`
- `scripts/export_mlquant_full_universe_factors_batch_35.py`
- `scripts/build_mlquant_full_universe_ml_dataset_batch_35.py`
- `scripts/run_mlquant_full_universe_walk_forward_batch_35.py`

## Step 60 — Fail closed on the current Riskfolio-Lib repository

Batch 36 began the next independent portfolio-construction track with
Riskfolio-Lib, catalog entry `ast-0185`. The current master commit `632a9e4`
was pinned before runtime checks. The repository declares version 7.3.0 and a
BSD-3-Clause license. It installed successfully in an isolated 2.47-GB Podman
image with CVXPY 1.9.2 and the free CLARABEL, SCS, ECOS, SCIPY, HIGHS,
ECOS_BB, and OSQP solvers. Tests ran without network, project data, or
credentials.

The predeclared qualification required all seven bundled upstream tests to
pass before any profitability experiment. All seven failed. Four call the
removed `d` argument on `Portfolio.assets_stats`; one NCO test uses a removed
`covariance` argument; HERC calls an internal method with an unsupported
`linkage` argument; and the HRP regression test disagrees with all 270 stored
weight cells. These failures are present within the pinned repository itself,
not in project strategy code.

The repository was therefore disqualified at the current commit before it saw
our price history. Downstream weight, determinism, and causality checks fail
closed. We did not patch third-party source, select a favorable older release,
or claim that its portfolio methods are profitable. The catalog registry now
records the exact failure so a future fixed release can be evaluated as new
evidence. Live trading remains disabled.

References:

- `config/riskfolio_repository_qualification_v1.json`
- `config/images/riskfolio-7.3.0.Containerfile`
- `evidence/riskfolio_repository_batch_36/result.json`
- `evidence/riskfolio_repository_batch_36/report.md`
- `evidence/riskfolio_repository_batch_36/runtime/upstream_tests.txt`
- `research_registry/registry.csv`

## Step 61 — Fail closed on unrestricted skfolio use

Batch 37 pinned `skfolio/skfolio` version 0.20.1 at commit `c06db84` and tested
it in isolated Podman runtimes without project data, credentials, or test-time
network access. The repository has a BSD-3-Clause license and installs with the
free CLARABEL solver. All 20 offline dataset tests passed, and 464 x86 suite
tests passed before the terminal failure was confirmed.

The unrestricted-library gate nevertheless failed: the entropy-pooling module
had 92 passes and two failures on native ARM, and a failure reproduced under
x86. The parser rejects a numerical prior-view value written with a zero
imaginary component. Because the predeclared rule required every upstream test
to pass, completing thousands of additional tests could not reverse the gate;
the emulated run was stopped and the full library was not qualified. No market
performance test or profitability claim was made.

References:

- `config/skfolio_repository_qualification_v1.json`
- `config/images/skfolio-0.20.1.Containerfile`
- `evidence/skfolio_repository_batch_37/result.json`
- `evidence/skfolio_repository_batch_37/report.md`

## Step 62 — Qualify only skfolio's bounded drawdown optimizer

Batch 38 applied a separate boundary fixed before component results. It allowed
only `MeanRisk` with `MINIMIZE_RISK`, CLARABEL, and CDaR, maximum drawdown,
EDaR, or Ulcer Index. Entropy pooling, Black–Litterman, opinion views, and
expected-return views are prohibited.

All 274 matching upstream drawdown tests passed. Seeded probes for all four
measures produced finite, long-only, fully invested weights respecting a 35%
cap. Exact repeats were identical, and changing future observations left the
prior decision weights identical. This narrowly bounded component qualifies
for a separately predeclared causal portfolio experiment, but does not qualify
skfolio as a whole and does not demonstrate profitability.

References:

- `config/skfolio_drawdown_component_qualification_v1.json`
- `containers/skfolio_drawdown_component_probe.py`
- `evidence/skfolio_drawdown_component_batch_38/probe_result.json`
- `evidence/skfolio_drawdown_component_batch_38/result.json`
- `evidence/skfolio_drawdown_component_batch_38/report.md`
- `research_registry/registry.csv`

## Step 63 — Test skfolio drawdown portfolios without replacing the winner

Batch 39 tested the qualified skfolio drawdown component on the exact snapshot,
two frozen strategy sleeves, monthly timing, 104-week history, sleeve and asset
caps, and cost accounting used by Batch 06. The benchmark reconstruction matched
the frozen minimum-variance return, Sharpe, drawdown, and turnover exactly at 10
and 50 bps. CDaR was declared the sole primary challenger before results; maximum
drawdown, EDaR, and Ulcer Index were secondary and could not replace it later.

At 10 bps, minimum variance returned 7.83% annually with 0.901 Sharpe, -23.39%
maximum drawdown, and 2.90 annual turnover. CDaR returned 7.99% with 0.904
Sharpe, the same -23.39% drawdown, and 2.88 turnover. It remained positive at
100 bps in the full period and both later windows. However, the improvement was
only 0.003 Sharpe, the drawdown-improvement gate missed by essentially the full
two-percentage-point requirement, and the four-method familywise one-sided
paired lower Sharpe bound was -0.039 rather than above zero.

EDaR had the best retrospective point estimate at 8.11% and 0.911 Sharpe, but
it was not the primary method, had one controlled optimizer fallback, did not
improve the shared worst drawdown, and also failed its familywise paired bound.
The other two secondary methods did not beat the incumbent Sharpe. CDaR passed
8 of 12 total gates and was not promoted. The frozen minimum-variance candidate
was not overwritten. Twelve pinned frozen files verified intact, no live trading
was enabled, and the free ETF universe remains survivorship-prone.

References:

- `config/skfolio_drawdown_portfolio_experiment_v1.json`
- `scripts/run_skfolio_drawdown_portfolios_batch_39.py`
- `evidence/skfolio_drawdown_portfolios_batch_39/result.json`
- `evidence/skfolio_drawdown_portfolios_batch_39/portfolio_scoreboard.csv`
- `evidence/skfolio_drawdown_portfolios_batch_39/paired_bootstrap.csv`
- `evidence/skfolio_drawdown_portfolios_batch_39/allocation_history.csv`
- `evidence/skfolio_drawdown_portfolios_batch_39/weekly_returns.csv`
- `evidence/skfolio_drawdown_portfolios_batch_39/report.md`
- `research_registry/registry.csv`

## Step 64 — Begin a read-only migration of the Version 1 winner

Batch 40 Phase 0 started the migration of Version 1's
`improved_frontier_phase5_fragility_guard` into the stricter Version 2 research
process. Version 1 remained read-only. A protocol fixed recent performance as
the reporting priority: trailing three-year annual return at 50 bps is primary,
with trailing one-, two-, and five-year returns and 10/100-bps sensitivities
reported alongside it. Full-history metrics are secondary context.

All 17 direct production files and code dependencies were present and pinned by
SHA-256. The saved candidate contains 1,110 weekly rows across 35 assets. Its
weights were finite, nonnegative, and fully invested to a maximum sum error of
2.22e-16. Saved 10-bps net returns reconciled from gross returns and one-way
turnover to 4.34e-19. Version 1's existing formal reproduction record also
passed: maximum weight error was 9.93e-17, maximum path error was 4.44e-16, and
return correlation was effectively one.

All five Phase 0 gates passed. This proves internal artifact and accounting
coherence, not causal validity in Version 2. The production candidate is a
wrapper around previously saved GGG weights, with a state-quality multiplier
and leadership fragility guard applied before next-week returns. The lineage of
those base weights and both features still requires a lookahead, selection-date,
and data-revision audit. Version 1's canonical Sharpe also uses CAGR divided by
volatility, unlike Version 2's arithmetic mean-return Sharpe; future comparisons
will keep both conventions explicit. Nothing was promoted and live trading
remains disabled.

References:

- `config/v1_to_v2_equivalence_audit_v1.json`
- `scripts/audit_v1_production_pin_batch_40.py`
- `evidence/v1_migration_batch_40/source_inventory.csv`
- `evidence/v1_migration_batch_40/recent_metrics.csv`
- `evidence/v1_migration_batch_40/result.json`
- `evidence/v1_migration_batch_40/report.md`

## Step 65 — Reconstruct the V1 wrapper and fail its independence gate

Batch 41 independently reconstructed Version 1's final wrapper without importing
any Version 1 Python module. Starting from the pinned GGG weights, Version 2
applied the documented 0.08 R2A offense scale, 0.50 leadership fragility guard,
stressed-panic exclusion, BIL residual normalization, next-week return timing,
half-L1 turnover, and 10-bps costs. Version 1 was mounted read-only in an
offline Podman container.

The reconstruction was exact. Across 1,110 weeks and 35 assets, maximum weight
difference was 9.93e-17, maximum path difference was 2.66e-15, and net-return
correlation was effectively one. All three mechanical equivalence gates passed.
The wrapper implementation itself is causally timed: Phase 1 and Phase 4 price
components are lagged one week, their standardizers are expanding, and Friday
weights fund the next Friday return.

The evidence-independence gate failed. The Phase 5 report dated 2026-05-21
evaluated seven non-baseline variants on the April 2024 onward holdout, included
holdout Sharpe directly in its selection score, and chose the fragility-guard
family from that comparison. The saved performance history ends 2026-04-10,
so it contains zero weeks after that selection. The recent one-, two-, and
three-year results are therefore entirely retrospective selection-contaminated
evidence, not an untouched forward record.

Three other structural gates remain false: the saved GGG base has not received
a complete native lineage reconstruction, the fixed 35-ETF universe is not
point-in-time, and the Version 1 weekly-price file has no immutable observation
vintage. The candidate remains the recent-return benchmark but is not yet the
qualified Version 2 incumbent. No Version 1 or frozen Version 2 file changed,
and live trading remains disabled.

References:

- `config/v1_wrapper_equivalence_lineage_v1.json`
- `scripts/reconstruct_v1_wrapper_batch_41.py`
- `evidence/v1_wrapper_equivalence_batch_41/scale_history.csv`
- `evidence/v1_wrapper_equivalence_batch_41/lineage_findings.csv`
- `evidence/v1_wrapper_equivalence_batch_41/result.json`
- `evidence/v1_wrapper_equivalence_batch_41/report.md`

## Step 66 — Reconstruct the V1 GGG base and quantify research multiplicity

Batch 42 independently reconstructed the saved GGG base return path without
importing Version 1 Python modules. It also inventoried all six saved allocator
checkpoints, parsed the allocator's candidate catalog directly from its source,
and preserved the three-candidate Phase GGG selection table. Version 1 remained
read-only.

Mechanical equivalence passed. The final allocator checkpoint matched the
published 1,110-by-35 ETF weight history exactly. At the saved 10-bps cost
convention, all 1,110 return-path rows reproduced with maximum absolute
difference 6.57e-14, driven by compounded-wealth rounding; individual net
returns differed by at most 2.45e-16 and correlation was effectively one.

The requested return-focused view remains attractive but retrospective. At 50
bps, the latest three-year period, 2023-04-14 through 2026-04-10, produced
12.86% CAGR, 12.44% arithmetic annual return, 1.542 arithmetic Sharpe, and
-7.35% maximum drawdown. At 10 bps it produced 14.48% CAGR and 1.723 Sharpe;
at 100 bps it produced 10.87% CAGR and 1.314 Sharpe.

Independent validation failed. GGG1 occupies position 173 in a 230-variant
allocator catalog and its phase selected among three closely related candidates
using full-history return, Sharpe, drawdown, CVaR, turnover, and conditional
state outcomes. No multiplicity-adjusted qualification was applied. The GGG
selection report is dated 2026-04-27 while the saved return history ends
2026-04-10, leaving zero post-selection observations. Checkpoint consistency
establishes what the pipeline produced, but does not make the long upstream
research search independent. The fixed ETF universe is not point-in-time and
the price artifact still lacks an immutable observation-vintage manifest.

GGG is therefore retained as an exactly reproducible, selection-contaminated
benchmark and a source of architecture ideas, not promoted as the Version 2
winner. No frozen Version 2 file changed and live trading remains disabled.

References:

- `config/v1_ggg_lineage_audit_v1.json`
- `scripts/audit_v1_ggg_lineage_batch_42.py`
- `evidence/v1_ggg_lineage_batch_42/checkpoint_inventory.csv`
- `evidence/v1_ggg_lineage_batch_42/allocator_candidate_catalog.csv`
- `evidence/v1_ggg_lineage_batch_42/phase_ggg_candidates.csv`
- `evidence/v1_ggg_lineage_batch_42/performance_cost_sensitivity.csv`
- `evidence/v1_ggg_lineage_batch_42/lineage_findings.csv`
- `evidence/v1_ggg_lineage_batch_42/result.json`
- `evidence/v1_ggg_lineage_batch_42/report.md`

## Step 67 — Regenerate all six GGG allocator stages natively

Batch 43 executed Version 1's pinned allocator builder for GGG alone inside an
ephemeral writable container copy. The original Version 1 tree was mounted
read-only. Input-heavy research folders stayed read-only, while Layer 1 through
Layer 3 output folders and the checkpoint folder were isolated copies. The run
used an already installed local image and made no downloads or paid API calls.

Pandas 3 exposed two arrays as read-only where the historical notebook mutates
their diagonals. The ephemeral notebook therefore materialized writable NumPy
copies before applying the unchanged covariance-floor and unit-correlation
diagonal equations. This compatibility shim was accepted only subject to the
original exact-equivalence gates.

All six stages regenerated exactly: raw HRP sleeves, post-state-tilt sleeves,
post-Layer-3-expression sleeves, post-overlay/pre-lookthrough sleeves, final
sleeves, and final ETF weights. Every checkpoint had the same 1,110 dates,
columns, values, and SHA-256 hash as the pinned source artifact. Maximum
checkpoint difference was zero. Published 35-ETF weights, seven sleeve weights,
and all six return-path columns also matched byte-for-byte; net-return
correlation was effectively one.

The transition audit showed that the state tilt changed 577 rows with a maximum
weight movement of 0.2998. GGG's Layer 3 expression mode is intentionally none,
so that stage changed no rows. The overlay changed 1,033 rows with maximum
movement 0.60, while final sleeve weights were an exact carry-forward of the
post-overlay stage. ETF look-through then combined sleeve positions and GGG's
state-conditional offense recipe: the broad basket in most states and removal
of PDBC and DBA during recovery-confirmed weeks.

This closes native deterministic reconstruction, but not historical
independence. The implementation still resides in Version 1's large monolithic
research builder, and the prior selection-contamination findings remain. The
next engineering boundary is a minimal independent Version 2 extraction of the
six GGG stages, tested against these exact checkpoints before any improvement
experiments are allowed.

References:

- `config/v1_ggg_native_reconstruction_v1.json`
- `scripts/run_v1_ggg_native_batch_43.sh`
- `scripts/compare_v1_ggg_native_batch_43.py`
- `evidence/v1_ggg_native_batch_43/checkpoint_equivalence.csv`
- `evidence/v1_ggg_native_batch_43/stage_transition_summary.csv`
- `evidence/v1_ggg_native_batch_43/stage_rule_manifest.csv`
- `evidence/v1_ggg_native_batch_43/published_artifact_equivalence.csv`
- `evidence/v1_ggg_native_batch_43/result.json`
- `evidence/v1_ggg_native_batch_43/report.md`

## Step 68 — Independently port GGG and expose inherited allocator lookahead

Batch 44 extracted GGG into the Version 2-owned
`systematic_trader.ggg_independent` module. The implementation imports no
Version 1 Python or notebook code. It reads 13 pinned CSV inputs and directly
implements state-conditional component construction, monthly 156-week HRP,
the DDD confirmed-state sleeve tilt, identity Layer 3 expression, regime and
target-vol overlays, hybrid cash handling, sleeve look-through, ETF caps, and
next-week return accounting.

The exact port passed every mechanical gate. All six stage histories matched
the native checkpoints to a maximum difference of 2.00e-15. The complete
return path matched to 5.86e-14 in compounded wealth, individual net returns
matched to floating-point precision, and correlation was effectively one.
Two independent runs produced identical hashes. Static negative-shift scanning,
five behavioral micro-scenarios, structured rebalance audit logging, semantic
hashing, and source-input hashing passed.

However, the SysTradeBench-inspired runtime prefix test exposed a material
one-week lookahead inherited from Version 1. Each sleeve return is labeled by
the date of the weights that earn the following week's return. The historical
allocator includes that date-t return in the covariance used to choose date-t
HRP weights. Shocking only the first price observation after three frozen
decision cutoffs changed the legacy-equivalent raw HRP weights by as much as
0.2380 and final ETF weights by as much as 0.0434. Mechanical equivalence was
therefore insufficient, and the exact independent port failed governance
qualification.

A causal correction excludes the current labeled sleeve-return row and trains
only through the prior row. It passed all six controlled prefix-invariance
checks with zero weight difference. At the primary 50-bps assumption, its
latest three-year retrospective window produced 12.89% CAGR, 12.46% arithmetic
annual return, 1.544 arithmetic Sharpe, and -7.36% maximum drawdown. The
lookahead-contaminated equivalent produced 12.86% CAGR, 1.542 Sharpe, and
-7.35% drawdown over the same window. Full-history causal CAGR was 5.72% at
50 bps versus 5.77% for the contaminated version.

The causal correction remains a research shadow because removing allocator
lookahead does not remove the 230-variant historical search, fixed-universe
bias, unknown source-price vintage, or incomplete upstream sleeve lineage. No
live trading was enabled, Version 1 stayed read-only, and frozen Version 2
files were not changed.

The linked SysTradeBench paper was adopted as an engineering-governance source,
not an alpha source. Its frozen semantics, deterministic hashes, constrained
patching, stage/trace comparisons, anti-leakage checks, micro-scenarios, and
structured audit bundles materially improved this audit. Its reported D4
profitability tests use sampled ten-bar windows and zero costs, while full OOS
and cost sweeps are deferred, so its performance evidence is not imported into
the portfolio research process.

References:

- `config/v2_ggg_independent_port_v1.json`
- `src/systematic_trader/ggg_independent.py`
- `scripts/audit_v2_ggg_independent_batch_44.py`
- `evidence/v2_ggg_independent_batch_44/stage_equivalence.csv`
- `evidence/v2_ggg_independent_batch_44/prefix_invariance.csv`
- `evidence/v2_ggg_independent_batch_44/micro_scenarios.csv`
- `evidence/v2_ggg_independent_batch_44/performance_comparison.csv`
- `evidence/v2_ggg_independent_batch_44/rebalance_audit_log.csv`
- `evidence/v2_ggg_independent_batch_44/source_inventory.csv`
- `evidence/v2_ggg_independent_batch_44/result.json`
- `evidence/v2_ggg_independent_batch_44/report.md`
- `evidence/v2_ggg_independent_batch_44/systradebench_application.md`
- `https://arxiv.org/html/2604.04812v1`

## Step 69 — Audit and partially freeze GGG's upstream sleeves

Batch 45 returned to the five Layer 2A source sleeves that feed the causal GGG
allocator: dual momentum, long-only CTA trend, the selective signal composite,
10-month SMA tactical allocation, and the regime-conditioned composite. The
acceptance rules were written before execution. Qualification required native
position equivalence, three truncated-history prefix tests, an independent
deterministic rerun, declared one-week lag evidence, exact next-week return
accounting, and a classified static negative-shift audit.

The pinned Layer 2A notebook was executed five times inside disposable Podman
sandboxes: one full reconstruction, three histories ending on 2023-12-29,
2024-12-27, and 2025-12-26, and a second full reconstruction. Version 1 was
mounted read-only. All 15 sleeve/cutoff prefix comparisons were exact, with
maximum difference zero, and every second-run position history was identical.
The static scan found three negative shifts, none used as an audited position
input: a known-calendar month-end mask, a forward-IC research target outside
these sleeves, and the explicitly labeled next-week realized-return outcome.

Four sleeves reproduced their saved positions: dual momentum and selective
composite and TAA were exact, while CTA differed only by 3.11e-15 floating-point
noise. Their saved gross returns also reconciled to position(t) multiplied by
the price return from t to t+1 to a maximum error of 1.04e-16. This confirms
both causal position construction and the important label boundary: the return
stored on row t is not known on date t and the allocator must train only through
t-1. These four sleeves are now recorded in the partial upstream freeze with
exact position and return hashes.

The regime-conditioned composite failed native equivalence. Its current,
deterministic and prefix-causal reconstruction differs from the saved positions
on 979 of 1,110 rows, from 2005-02-25 through 2026-04-10, with a maximum weight
difference of 0.5625. This is a source-vintage/lineage failure, not evidence of
lookahead in the current formula. It is excluded from the freeze rather than
silently replaced. Because GGG uses this source to create its offense and
defense components, the causal GGG portfolio remains a research shadow and is
not yet a fully qualified benchmark.

This audit does not cure fixed-universe survivorship risk, non-vintage vendor
data, or historical strategy-selection contamination, and no live trading was
enabled.

References:

- `config/ggg_upstream_causality_audit_v1.json`
- `config/ggg_causal_upstream_freeze_v1.json`
- `scripts/audit_ggg_upstream_causality_batch_45.py`
- `evidence/ggg_upstream_causality_batch_45/native_position_equivalence.csv`
- `evidence/ggg_upstream_causality_batch_45/prefix_invariance.csv`
- `evidence/ggg_upstream_causality_batch_45/deterministic_rerun.csv`
- `evidence/ggg_upstream_causality_batch_45/return_label_identity.csv`
- `evidence/ggg_upstream_causality_batch_45/sleeve_qualification.csv`
- `evidence/ggg_upstream_causality_batch_45/static_negative_shift_findings.json`
- `evidence/ggg_upstream_causality_batch_45/result.json`
- `evidence/ggg_upstream_causality_batch_45/report.md`

## Step 70 — Recover the regime-composite source vintage and complete the upstream freeze

Batch 46 traced the only unresolved GGG source sleeve,
`composite_regime_conditioned`, through the notebook's two regime-input paths.
Git history confirmed that the saved positions, current Layer 2A notebook, and
current `regime_states.csv` were committed together, but rerunning those files
still produced a different sleeve. This proved the commit itself contained a
stale generated artifact and did not preserve its execution context.

The missing context was then recovered: when Layer 2B regime files are absent,
the notebook falls back to the Layer 1 `macro_risk_score_tradable` series and
constructs its own calm/neutral/stressed state and exposure multiplier. An
isolated rerun using that fallback reproduced all 1,110 saved position rows
exactly and the entire saved strategy-return file to 1.33e-15. Three truncated
histories ending in 2023, 2024, and 2025 produced zero prefix difference, and a
second complete run was identical. The historical fallback lineage therefore
passes the same implementation-causality and deterministic requirements as the
other four source sleeves.

The newer Layer 2B path was retained only as a post-discovery diagnostic. It
changes 979 position rows by as much as 0.5625 and is worse after substitution
into the corrected causal GGG allocator. At 50 bps, the latest three-year GGG
CAGR falls from 12.89% to 12.25%, arithmetic Sharpe falls from 1.544 to 1.449,
and maximum drawdown worsens from -7.36% to -8.21%. It was not promoted.

The upstream implementation freeze now contains all five source sleeves with
exact position and return hashes. The allocator still excludes the row-t
t-to-t+1 outcome from date-t covariance training. This closes reproducibility
and timing lineage, not profitability validation: fixed-universe bias, unknown
vendor-data vintage, the prior 230-variant search, and the lack of a long
untouched forward record all remain. No live trading was enabled.

References:

- `config/regime_conditioned_lineage_audit_v1.json`
- `config/ggg_causal_upstream_freeze_v1.json`
- `scripts/audit_regime_conditioned_lineage_batch_46.py`
- `evidence/regime_conditioned_lineage_batch_46/fallback_prefix_invariance.csv`
- `evidence/regime_conditioned_lineage_batch_46/source_mode_comparison.csv`
- `evidence/regime_conditioned_lineage_batch_46/sleeve_performance_comparison.csv`
- `evidence/regime_conditioned_lineage_batch_46/ggg_performance_comparison.csv`
- `evidence/regime_conditioned_lineage_batch_46/result.json`
- `evidence/regime_conditioned_lineage_batch_46/report.md`

## Step 71 — Test six recent-return overlays and reject insufficient improvements

Batch 47 began the first bounded challenger round against the fully frozen,
causal GGG benchmark. Before execution, the search budget was fixed at six:
two cross-sectional 26-week momentum tilts, two conditional cash-redeployment
rules, and two combinations. Cash could move to equal SPY/QQQ only when both
had positive 26-week momentum and were above their 43-week moving averages.
Every transformed portfolio retained the frozen 35% risky-ETF cap.

The primary gate required at least 0.50 percentage points of recent three-year
CAGR improvement at 50 bps, no post-2024 CAGR degradation, no more than 0.20
percentage points of full-history CAGR degradation, recent drawdown no worse
than -13%, deterministic output, exact frozen hashes, and zero change before
three controlled future-price shocks. All 18 prefix comparisons were exact and
all candidate hashes were deterministic.

No challenger qualified. Full conditional cash redeployment was best, raising
recent three-year CAGR from 12.89% to 13.01%, but the 0.12-point improvement
was below the predeclared 0.50-point gate. Its Sharpe fell from 1.544 to 1.448
and drawdown moved from -7.36% to -7.62%. Half redeployment produced 12.97%
CAGR and a 1.505 Sharpe. Both improved the post-2024 CAGR and full-history CAGR,
but neither supplied enough recent return lift. Both momentum tilts reduced
recent CAGR, and combining momentum with cash redeployment did not repair the
drag. The shortlist is therefore empty and no candidate was promoted.

During startup, Podman exposed several older macOS files as empty even though
their host-side content remained readable. Three hub files were rematerialized
from exact preserved copies, restoring their previously recorded hashes. To
remove that runtime ambiguity, Version 2 now owns a minimal 14-file GGG input
snapshot. All ten sleeve position/return hashes match the completed upstream
freeze; the price and three regime inputs are also pinned in its manifest.
This was a byte-preserving runtime repair, not a data or strategy revision.

The result argues against spending the next search budget on more ETF-level
momentum-overlay magnitudes. A more promising next challenger class is causal
sleeve-level allocation or a distinct return source, with the same bounded
search and recent-window gates.

References:

- `config/ggg_recent_return_challengers_v1.json`
- `src/systematic_trader/ggg_challengers.py`
- `scripts/run_ggg_recent_return_challengers_batch_47.py`
- `data/frozen_ggg_inputs_v1/manifest.json`
- `evidence/ggg_recent_return_challengers_batch_47/performance.csv`
- `evidence/ggg_recent_return_challengers_batch_47/prefix_invariance.csv`
- `evidence/ggg_recent_return_challengers_batch_47/determinism.csv`
- `evidence/ggg_recent_return_challengers_batch_47/qualification.csv`
- `evidence/ggg_recent_return_challengers_batch_47/result.json`
- `evidence/ggg_recent_return_challengers_batch_47/report.md`

## Step 72 — Test causal sleeve-level recency allocation and reject return drag

Batch 48 tested whether GGG could improve recent returns by reallocating among
its six sleeves instead of modifying final ETF weights. The search budget was
fixed at six before execution: mild and assertive 26-week sleeve momentum,
52-week sleeve momentum, 26- and 52-week sleeve Sharpe, and a 26-week momentum
plus low-volatility combination. Scores were recomputed monthly, clipped, and
applied multiplicatively to the frozen GGG sleeve weights while preserving the
existing total risky-sleeve budget, cash allocation, ETF look-through, and 35%
ETF cap.

The timing rule explicitly excluded the return labeled on the decision row:
at date t, scoring stopped at t-1 because row t realizes t-to-t+1. All 18
controlled future-price shock tests therefore had zero prefix difference. The
14-file runtime snapshot passed every hash check and all repeated candidate
histories had identical hashes.

No challenger qualified. At the primary 50-bps assumption, the best recent
three-year return came from the 52-week sleeve-Sharpe tilt, but CAGR declined
from 12.89% to 12.63% and post-2024 CAGR declined from 15.38% to 15.29%. That
candidate did improve the risk profile—Sharpe rose from 1.544 to 1.600 and
maximum drawdown improved from -7.36% to -6.68%—but it fails the user's stated
recent-return objective and both return gates. It remains rejection evidence,
not a shortlist candidate.

The other five candidates were weaker. Recent three-year CAGR ranged from
12.33% for 52-week momentum down to 11.32% for assertive 26-week momentum.
Short-horizon sleeve momentum and recent sleeve Sharpe were especially harmful,
showing that recent winner-chasing duplicates or conflicts with GGG's existing
state and HRP machinery. The research shortlist remains empty.

Two bounded rounds now reject both final-ETF momentum overlays and sleeve-level
recency tilts. The next return-seeking experiment should add a genuinely
distinct causal return source rather than retune GGG's existing exposures.
That source must be evaluated standalone first, then blended under a fixed
small allocation budget against the same 12.89% recent-three-year benchmark.

References:

- `config/ggg_sleeve_allocation_challengers_v1.json`
- `src/systematic_trader/ggg_sleeve_challengers.py`
- `scripts/run_ggg_sleeve_allocation_challengers_batch_48.py`
- `evidence/ggg_sleeve_allocation_challengers_batch_48/performance.csv`
- `evidence/ggg_sleeve_allocation_challengers_batch_48/prefix_invariance.csv`
- `evidence/ggg_sleeve_allocation_challengers_batch_48/determinism.csv`
- `evidence/ggg_sleeve_allocation_challengers_batch_48/qualification.csv`
- `evidence/ggg_sleeve_allocation_challengers_batch_48/result.json`
- `evidence/ggg_sleeve_allocation_challengers_batch_48/report.md`

## Step 73 — Add a distinct trend-qualified reversal source and reject it

Batch 49 moved beyond retuning GGG and implemented a new standalone return
source: monthly cross-sectional reversal conditioned on positive medium-term
trend. Two variants were fixed before execution. At each month-end they
required a positive 26-week return and a close above the 43-week moving average,
then equally weighted up to four ETFs with the largest 4- or 8-week pullbacks.
If no ETF qualified, the source held BIL. Four fixed blends completed the
six-candidate budget: 5%, 10%, and 15% allocations to the 4-week source and a
10% allocation to the 8-week source.

This formulation deliberately addressed the known problems in Version 1 Track
C's neutral-reversal diagnostic: weekly turnover was replaced by monthly
decisions, and reversal trades were allowed only inside established positive
trends. The source nevertheless had to qualify standalone before a blend could
pass. Required evidence included at least 6% recent three-year CAGR at 50 bps,
at least 2% full-history CAGR at 100 bps, correlation below 0.75 to causal GGG,
and recent drawdown better than -35%.

Neither source qualified. The 4-week source delivered only 3.10% recent CAGR
at 50 bps and -0.42% full-history CAGR at 100 bps. The 8-week source delivered
5.41% recent CAGR and -0.16% full-history CAGR at 100 bps. Their full-history
correlations to GGG were 0.694 and 0.675, so they were different enough, but
the independent returns did not survive realistic costs.

Every blend reduced recent returns. The least harmful 5% 4-week blend lowered
recent three-year CAGR from 12.89% to 12.51% and post-2024 CAGR by 0.26
percentage points. Larger weights increased the damage; the 15% blend fell to
11.64% recent CAGR. All 18 future-shock prefix checks were exact, every rerun
was deterministic, and all 14 snapshot hashes passed. The rejection is an
economic result, not an implementation or timing failure.

This closes the reversal branch. Further reversal lookback, rank, or filter
tuning is prohibited by the batch's no-sweep rule. The next distinct-source
test should use one of the only two prior Track C sleeves that passed standalone
sanity—volatility-managed residual momentum or canary/breadth timing—and port
its raw inputs causally before testing small fixed GGG blends.

References:

- `config/ggg_distinct_reversal_source_v1.json`
- `src/systematic_trader/trend_reversal_source.py`
- `scripts/run_ggg_distinct_reversal_source_batch_49.py`
- `evidence/ggg_distinct_reversal_source_batch_49/performance.csv`
- `evidence/ggg_distinct_reversal_source_batch_49/correlations.csv`
- `evidence/ggg_distinct_reversal_source_batch_49/prefix_invariance.csv`
- `evidence/ggg_distinct_reversal_source_batch_49/determinism.csv`
- `evidence/ggg_distinct_reversal_source_batch_49/source_qualification.csv`
- `evidence/ggg_distinct_reversal_source_batch_49/blend_qualification.csv`
- `evidence/ggg_distinct_reversal_source_batch_49/result.json`
- `evidence/ggg_distinct_reversal_source_batch_49/report.md`

## Step 74 — Independently reconstruct residual momentum and reject its blends

Batch 50 ported the most promising prior Track C alpha candidate into
Version 2 without using saved signal values for portfolio construction. The
implementation derives weekly log returns from prices, estimates each ETF's
rolling 52-week beta and alpha to SPY with a 26-week minimum, uses only lagged
beta and alpha to calculate residual returns, compounds a 48-week formation
period after skipping four weeks, converts it to a winsorized cross-sectional
rank, and applies a one-week execution lag. Weekly top-five positive scores are
equal weighted; the volatility-managed version scales risky exposure to 100%,
80%, or 60% based on 13-week SPY volatility.

The independent tradable signal reproduced the saved Layer 1 audit comparator
to a maximum error of 1.11e-16 with zero missingness differences. Saved signals
were not runtime inputs. All 18 future-price prefix comparisons had zero
difference, all candidate histories were deterministic, and every frozen input
hash passed.

Neither standalone source qualified. Raw residual momentum had strong recent
three-year CAGR of 13.29% at 50 bps and full-history correlation of 0.658 to
GGG, but its high weekly turnover made the long-run result collapse under the
predeclared 100-bps stress: full CAGR was only 0.28%, versus the required 3%.
Its full-history drawdown was -52.19% at 10 bps and -62.41% at 100 bps. The
volatility-managed source reduced volatility and the 10-bps drawdown to
-43.96%, but recent CAGR was lower at 11.99% and full 100-bps CAGR was -0.21%.

No fixed blend passed. The best, 10% raw residual momentum, lifted recent
three-year CAGR from 12.89% to 13.02% and improved post-2024 CAGR by 0.66
percentage points. The recent improvement was only 0.13 points, below the
fixed 0.50-point gate, Sharpe declined from 1.544 to 1.489, and the parent
source failed its cost-survival gate. Volatility-managed blends ranged from
12.90% to 12.87% recent CAGR and also failed the parent and return gates.

This is a stronger rejection than the earlier Track C evidence because the
formula is now independently reconstructed and evaluated directly against the
causal GGG benchmark at realistic 50- and 100-bps assumptions. Residual
momentum contains a real recent return signal, but in this weekly top-five ETF
implementation it is too costly and too drawdown-prone to qualify. Further
lookback or blend-weight tuning is prohibited for this branch.

References:

- `config/ggg_residual_momentum_source_v1.json`
- `src/systematic_trader/residual_momentum_source.py`
- `scripts/run_ggg_residual_momentum_source_batch_50.py`
- `data/audit_comparators/signal_residual_momentum.csv`
- `evidence/ggg_residual_momentum_source_batch_50/signal_equivalence.csv`
- `evidence/ggg_residual_momentum_source_batch_50/performance.csv`
- `evidence/ggg_residual_momentum_source_batch_50/correlations.csv`
- `evidence/ggg_residual_momentum_source_batch_50/prefix_invariance.csv`
- `evidence/ggg_residual_momentum_source_batch_50/determinism.csv`
- `evidence/ggg_residual_momentum_source_batch_50/source_qualification.csv`
- `evidence/ggg_residual_momentum_source_batch_50/blend_qualification.csv`
- `evidence/ggg_residual_momentum_source_batch_50/result.json`
- `evidence/ggg_residual_momentum_source_batch_50/report.md`

## Step 75 — Publish a same-basis main-strategy and trailing-period scorecard

Batch 51 rebuilt the displayed strategy returns from weekly holdings and the
same frozen price panel, then charged 50 basis points per unit of one-way
turnover. This avoids mixing cached summaries, different date ranges, or
different cost conventions. The frozen evidence ends on 2026-04-10.

The current deployable research benchmark remains causal GGG. Its net CAGR was
20.57% over the trailing year, 15.36% over two years, 12.89% over three years,
8.80% over five years, 6.89% over ten years, and 5.72% over the full history
starting 2005-01-07. Corresponding Sharpe ratios were 2.198, 1.748, 1.544,
1.167, 0.866, and 0.767. Maximum drawdown was -7.36% over the recent one- to
five-year windows and -11.87% over the ten-year and full-history windows.

Recent results are materially stronger than the long-run average, but causal
GGG is not an absolute-return winner against SPY. Over the recent three years,
SPY produced 19.49% CAGR versus GGG's 12.89%; GGG instead delivered the higher
Sharpe ratio and far smaller drawdown. Its three-year beta to SPY was only
0.354, which explains much of the return gap. The legacy Version 1 comparator
is retained only as an audit reference because its selection lineage is not
fully causal. The best rejected residual-momentum blend improved three-year
CAGR by only 0.13 percentage points and therefore remains rejected.

The cost table identifies the clearest improvement target. Causal GGG's recent
three-year CAGR falls from 14.51% at 10 basis points to 12.89% at 50 basis
points and 10.89% at 100 basis points, while recent annual one-way turnover is
3.57 times capital. The next work should therefore first update a separate
post-freeze market-data vintage, then decompose the return ceiling into cash,
exposure, cap, and trading-cost contributions. Only after that attribution
should fixed, causally locked tests be run for turnover buffers and
breadth-conditioned exposure expansion. This preserves honest walk-forward
testing while targeting higher net returns rather than further in-sample GGG
parameter tuning.

References:

- `scripts/report_main_strategy_metrics_batch_51.py`
- `data/audit_comparators/v1_frontier_phase5_fragility_guard_weights.csv`
- `evidence/main_strategy_metrics_batch_51/trailing_scorecard_50bps.csv`
- `evidence/main_strategy_metrics_batch_51/calendar_year_metrics.csv`
- `evidence/main_strategy_metrics_batch_51/benchmark_risk_metrics.csv`
- `evidence/main_strategy_metrics_batch_51/causal_ggg_cost_sensitivity.csv`
- `evidence/main_strategy_metrics_batch_51/result.json`

## Step 76 — Refresh free data, attribute GGG's return ceiling, and reject twelve expansion candidates

The project first acquired a new immutable, no-cost ETF vintage through
2026-08-11 using the pinned rootless Podman collector. All 35 configured ETFs
were present, the freshness gate passed, and the new snapshot identifier is
`20260812T035702Z-0c1bf62d74413e2a`. Compared with the preceding vintage,
150,914 adjusted-close cells changed at machine-rounding scale, but none
exceeded the fixed 0.01% economic-materiality threshold; raw closes were
unchanged. The April GGG dataset was not appended to or overwritten.

Before evaluating results, Batch 52 fixed a twelve-candidate budget. Four
turnover rules covered 1% and 2.5% no-trade bands, a 2.5% minimum total-change
threshold, and a 50% staggered transition. Three breadth rules used date-t
43-week trend and 26-week momentum across the offensive ETF universe, while
requiring SPY and QQQ confirmation. Two candidates raised the internal
volatility target from 12% to 14% or 16%, and three fixed combinations paired
the most plausible exposure changes with a 1% turnover band. No further
parameters were tried after the results were visible.

The return-ceiling attribution found that transaction costs, not the 12%
volatility target, are the dominant constraint. Over the recent three years,
the 50-bps baseline earned 12.89% CAGR, while its zero-cost gross path earned
14.92%, a 2.03-point ceiling. Removing the volatility ceiling changed CAGR by
less than 0.001 point because the target-vol multiplier averaged 0.992 and was
effectively non-binding. Removing the 35% ETF cap added 0.45 point. An
unconditional, diagnostic reinvestment of BIL added 1.78 points but increased
volatility and was not a selection candidate; the causal breadth-timed cash
rules actually reduced recent CAGR and failed cost stress.

The best candidate was the 2.5% no-trade band. It reduced recent annual
one-way turnover from 3.57 to 2.91 times capital, lifted recent three-year CAGR
from 12.89% to 13.14%, improved Sharpe from 1.544 to 1.576, and retained a
-7.47% drawdown. It also improved post-2024 CAGR by 0.34 point, full-history
CAGR by 0.19 point, and recent 100-bps CAGR by 0.61 point. Nevertheless, its
recent improvement was only 0.25 point versus the predeclared 0.50-point gate.
All other candidates produced less recent return improvement. The 14% and 16%
volatility targets were numerically indistinguishable from the benchmark, and
the breadth cash rules were harmful.

All 36 future-shock prefix comparisons were exact, all repeated histories were
deterministic, the frozen 14-file GGG manifest passed, and the new transformation
tests passed. Because no candidate cleared every gate, no forward challenger
was frozen and no forward clock was started. The 2.5% buffer is retained as
useful research evidence in `research_registry/strategy_candidates.json`, not
silently promoted. The next return-focused work
should target execution-aware turnover reduction or a genuinely higher-return
source; further volatility-target or breadth-cash parameter sweeps are closed.

References:

- `config/ggg_return_ceiling_program_v1.json`
- `src/systematic_trader/ggg_return_expansion.py`
- `scripts/run_ggg_return_ceiling_batch_52.py`
- `tests/test_ggg_return_expansion.py`
- `evidence/free_data_acquisition/runs/20260812T035702Z-0c1bf62d74413e2a/result.json`
- `data/vintages/20260812T035702Z-0c1bf62d74413e2a/manifest.json`
- `evidence/ggg_return_ceiling_batch_52/return_ceiling_attribution.csv`
- `evidence/ggg_return_ceiling_batch_52/performance.csv`
- `evidence/ggg_return_ceiling_batch_52/qualification.csv`
- `evidence/ggg_return_ceiling_batch_52/prefix_invariance.csv`
- `evidence/ggg_return_ceiling_batch_52/determinism.csv`
- `evidence/ggg_return_ceiling_batch_52/result.json`
- `evidence/ggg_return_ceiling_batch_52/report.md`

## Step 77 — Test execution-aware GGG and map the post-April engine gap

Batch 53 fixed ten execution candidates before observing their results. The
program tested biweekly and monthly scheduling, a monthly emergency override,
0.5% and 1% per-ETF deadbands, two asymmetric portfolio bands, a 13-week SPY
volatility-adaptive band, and two scheduled/buffered combinations. The Batch
52 symmetric 2.5% buffer remained an audit comparator rather than being counted
again as a new selection trial.

The best rule was `asymmetric_entry050_exit010`, which used a 5% no-trade band
when the portfolio reduced BIL and a 1% band when it increased BIL. At 50-bps
costs, recent three-year CAGR increased from 12.89% to 13.18%, Sharpe improved
from 1.544 to 1.596, maximum drawdown was -7.39%, and annual one-way turnover
fell from 3.57 to 2.81 times capital. It exceeded the prior symmetric buffer's
13.14% CAGR and 1.576 Sharpe. It also improved post-2024 CAGR by 0.37 point,
full-history CAGR by 0.17 point, and recent 100-bps CAGR by 0.71 point.

The result still failed the predeclared primary gate: recent CAGR improved by
only 0.30 percentage points instead of the required 0.50. All ten candidates
therefore remain unqualified. Monthly execution and several deadband variants
improved returns modestly, while biweekly execution damaged both recent and
full-history results. This closes the bounded execution-parameter branch; the
asymmetric rule is retained in the candidate registry as promising evidence,
not as a promoted strategy.

All 30 future-shock prefix comparisons were exact, all repeated histories were
deterministic, all frozen source hashes passed, and the execution plus prior
return-expansion unit tests passed. No forward lock or live-trading permission
was created.

The accompanying portability assessment found that prices are no longer the
post-April blocker. The immutable free-data collector is current through
2026-08-11, weekly preparation exists, and the final GGG allocator is causal
when supplied with a complete bundle. However, the four qualified sleeve
generators, the recovered composite fallback, `market_state_history`,
`regime_states`, and `phase2b_meta_predictions` do not yet have platform-owned
post-April generators. Passing new prices into the allocator merely reindexes
those frozen inputs and cannot create valid new holdings.

The next build must therefore port the exact Layer 1 input schema, the four
qualified Layer 2a sleeves and recovered fallback, then the Layer 2b state and
prediction path. Each stage must reconcile through 2026-04-10, pass prefix and
determinism checks, fail closed on missing inputs, and be connected through an
explicit immutable input bundle. Only a newly frozen complete engine may start
a genuine forward clock.

References:

- `config/ggg_execution_aware_program_v1.json`
- `src/systematic_trader/ggg_execution.py`
- `scripts/run_ggg_execution_aware_batch_53.py`
- `tests/test_ggg_execution.py`
- `evidence/ggg_execution_aware_batch_53/performance.csv`
- `evidence/ggg_execution_aware_batch_53/qualification.csv`
- `evidence/ggg_execution_aware_batch_53/prefix_invariance.csv`
- `evidence/ggg_execution_aware_batch_53/determinism.csv`
- `evidence/ggg_execution_aware_batch_53/result.json`
- `evidence/ggg_execution_aware_batch_53/report.md`
- `evidence/ggg_portable_engine_assessment_batch_53/assessment.json`
- `evidence/ggg_portable_engine_assessment_batch_53/report.md`

## Step 78 — Port and exactly reconcile GGG Layer 1, then fail closed on current regime data

Batch 54 replaced the Layer 1 notebook dependency with a platform-owned
adapter implementing the exact inputs consumed by GGG: global 52-4 momentum,
raw absolute momentum, inverse-volatility multi-horizon momentum, residual
momentum, four-week reversal, return-path quality, long-horizon value, daily
low-beta, distribution carry, and the macro/regime feature formula.

The audit compared nine signal panels plus the regime reference against the
frozen Version 1 outputs through 2026-04-10. All ten comparisons passed. The
maximum numerical difference was 5.06e-14, missingness matched exactly, all 30
three-cutoff prefix comparisons were exact, and repeated panel hashes were
deterministic. Three focused adapter tests also passed, including future-price
prefix invariance and an explicit missing-regime failure state.

The adapter was then run on immutable free snapshot
`20260812T035702Z-0c1bf62d74413e2a`. It generated current signals through the
last completed Friday, 2026-08-07. Eight panels plus raw momentum had values
for all 35 ETFs. Carry had values for 31 ETFs and intentionally retained
missing values where the free action history supplied no distributions.

The Layer 1 interface is not falsely marked complete. The ETF collector does
not contain current immutable VIX term structure, macro series, or Google fear
data, so the regime block cannot be extended past April. Forward-filling old
values, dropping components, or substituting unpinned current values would
change the formula. The verified price/daily/distribution block is therefore
frozen separately as `ggg_layer1_portable_price_block_v1`, while complete GGG
requests must fail closed.

The next build is an immutable no-cost regime-source bundle with observation
and knowledge timestamps, publication lags, revision monitoring, and the same
historical/prefix equivalence gates. Only then can the complete Layer 1 bundle
feed the portable sleeve engine. No forward clock or live execution was
enabled.

References:

- `src/systematic_trader/ggg_layer1.py`
- `scripts/audit_ggg_layer1_portable_batch_54.py`
- `tests/test_ggg_layer1.py`
- `config/ggg_layer1_portable_price_block_v1.json`
- `evidence/ggg_layer1_portable_batch_54/historical_equivalence.csv`
- `evidence/ggg_layer1_portable_batch_54/prefix_invariance.csv`
- `evidence/ggg_layer1_portable_batch_54/determinism.csv`
- `evidence/ggg_layer1_portable_batch_54/current_readiness.csv`
- `evidence/ggg_layer1_portable_batch_54/current_price_signal_snapshot.csv`
- `evidence/ggg_layer1_portable_batch_54/result.json`
- `evidence/ggg_layer1_portable_batch_54/report.md`

## Step 79 — Freeze the first no-cost regime snapshot and connect only proven lineage

Batch 55 added an isolated Podman collector for official Cboe volatility-index
history, no-key FRED CSV observations, and the four Google Trends fear searches
used by the frozen GGG formula. Every acquisition records observation dates,
the UTC knowledge timestamp, source URLs, raw files, and SHA-256 hashes. The
first immutable snapshot is
`20260812T084752Z-0420b0c979e4`.

Cboe completed all three required series through 2026-08-11. Its public history
does not match the prior Yahoo-derived panel exactly: the largest VIX difference
was 2.61 points and the Cboe VIX3M file lacked 165 early weekly observations
present in Yahoo. The continuation therefore preserves the already validated
history through 2026-04-10 and uses Cboe only after that cutoff. This avoids
silently rewriting the backtest while giving the platform an official current
continuation.

FRED returned six of seven requested series through 2026-08-11; the old `NAPM`
identifier now returns 404. More importantly, the frozen Version 1 macro panel
contained only dates and no macro values. The FRED snapshot is therefore kept
as supplemental research data and is not inserted into the exact GGG formula,
which would otherwise change the tested strategy.

Google rate-limited the first unofficial pytrends attempt. Only `bear market`
completed, so the incomplete snapshot was frozen but failed closed. A second
paced retry then completed all four keywords and was frozen separately as
`20260812T090851Z-5c6de663ac77`. All four passed the declared continuity gate
over 767 overlapping observations: correlations ranged from 0.9937 to 0.9985
and every median absolute difference was zero.

The spliced frozen-history reconstruction still matched every historical GGG
regime value through 2026-04-10 with maximum difference 5.06e-14 and no
missingness differences. Six focused regime/Layer 1 tests passed. The complete
regime block is now available through the completed week of 2026-08-07. The
forward clock and live execution remain disabled pending the downstream sleeve
and state-engine ports.

References:

- `containers/Containerfile.regime`
- `containers/regime_collector.py`
- `scripts/acquire_free_regime_snapshot.py`
- `scripts/run_free_regime_batch_55.py`
- `src/systematic_trader/regime_data.py`
- `tests/test_regime_data.py`
- `config/free_regime_collector_v1.json`
- `evidence/free_regime_data_batch_55/source_status.csv`
- `evidence/free_regime_data_batch_55/vix_source_reconciliation.csv`
- `evidence/free_regime_data_batch_55/google_source_reconciliation.csv`
- `evidence/free_regime_data_batch_55/result.json`
- `evidence/free_regime_data_batch_55/report.md`

## Step 80 — Assemble and freeze the complete current Layer 1 bundle

Batch 56 combined immutable price snapshot
`20260812T035702Z-0c1bf62d74413e2a` with the passing regime snapshot
`20260812T090851Z-5c6de663ac77`. The downstream-ready `normalized_v2` bundle
contains the frozen-history-spliced VIX and Google panels, the intentionally
empty exact-lineage macro panel, supplemental FRED research data, and the
reconstructed regime features. The earlier normalized derivation was retained
unchanged for audit history.

All nine current signal panels and the regime feature row were available through
2026-08-07. Two full builds had identical hashes. Rebuilding the stored regime
from its normalized inputs differed by only 5.33e-15, and all regime labels
matched after normalizing their CSV string representation. The current
macro-risk score was -0.554708, classified as `risk_on`.

The complete Layer 1 bundle is now frozen and ready to feed the portable Layer
2a sleeve engine. This is data-and-signal readiness, not evidence of future
profitability. No forward clock or live execution was enabled.

References:

- `data/regime_vintages/20260812T090851Z-5c6de663ac77/normalized_v2/manifest.json`
- `scripts/audit_complete_layer1_batch_56.py`
- `evidence/complete_layer1_bundle_batch_56/current_readiness.csv`
- `evidence/complete_layer1_bundle_batch_56/determinism.csv`
- `evidence/complete_layer1_bundle_batch_56/latest_regime.csv`
- `evidence/complete_layer1_bundle_batch_56/result.json`
- `evidence/complete_layer1_bundle_batch_56/report.md`

## Step 81 — Port, reconcile, and freeze the five GGG Layer 2a sleeves

Batch 57 replaced the Version 1 Layer 2a notebook dependency with a
platform-owned module for the four qualified sleeves and the recovered
regime-conditioned fallback: top-three dual momentum, weekly long-only CTA
trend, the selective six-signal composite, 43-week SMA tactical allocation,
and the Layer 1-regime-conditioned composite.

All five position histories matched the frozen Version 1 artifacts. The maximum
position difference was 3.11e-15. Their full gross/net/turnover/cost/wealth/
drawdown paths also matched, with maximum difference 5.15e-14. All 15
three-cutoff prefix tests were exact, two full builds had identical hashes, and
eight focused Layer 1/regime/Layer 2a tests passed.

The current continuation explicitly resolves the old notebook's terminal-row
artifact. Version 1 treated its final 2026-04-10 observation as if it were a
month-end rebalance. That row remains frozen for historical fidelity, seeds the
post-cutoff holdings, and is then replaced only on genuine calendar-final
Fridays. The incomplete 2026-08-07 month therefore did not create a false
monthly rebalance.

All five current sleeves were available and summed to one through 2026-08-07.
Dual momentum selected VWO, GLD, and PDBC equally. CTA held eight positive-trend
assets. The selective composite held HYG, LQD, PDBC, and TLT equally. TAA held
six risk assets equally. The regime-conditioned composite held IWM, EWJ, VNQ,
and PDBC at 18.75% each plus 25% BIL.

The immutable Layer 2a bundle
`20260812T035702Z_20260812T090851Z_23415b848f82` is ready for the portable
Layer 2b state and prediction engine. This completes strategy-sleeve generation
but does not remove historical selection, universe, or source-vintage biases.
No forward clock or live execution was enabled.

References:

- `src/systematic_trader/ggg_layer2a.py`
- `scripts/audit_ggg_layer2a_portable_batch_57.py`
- `tests/test_ggg_layer2a.py`
- `config/ggg_layer2a_portable_v1.json`
- `data/layer2a_vintages/20260812T035702Z_20260812T090851Z_23415b848f82/manifest.json`
- `evidence/ggg_layer2a_portable_batch_57/historical_equivalence.csv`
- `evidence/ggg_layer2a_portable_batch_57/return_path_equivalence.csv`
- `evidence/ggg_layer2a_portable_batch_57/prefix_invariance.csv`
- `evidence/ggg_layer2a_portable_batch_57/current_readiness.csv`
- `evidence/ggg_layer2a_portable_batch_57/latest_positions.csv`
- `evidence/ggg_layer2a_portable_batch_57/result.json`
- `evidence/ggg_layer2a_portable_batch_57/report.md`

## Step 82 — Port Layer 2b and replace two non-causal timing rules

Batch 58 ported the GGG regime score, defensive states, market-state classifier,
transition features, and three interpretable meta models. The deterministic
regime/state engine matched the frozen Version 1 artifacts with maximum
difference 6.25e-13 and no label or missingness differences.

The port uncovered two timing defects in the saved Layer 2b lineage. First, the
walk-forward ML fitter admitted recent labels without waiting for their full
four- or eight-week forward outcome windows to elapse. Second, state-conditional
transition probabilities were attached using knowledge that the current state
had a following observation. A 2024-12-27 prefix test caught 0.00641 of state
feature drift and 0.01894 of downstream probability drift when future rows were
added.

Both paths were retired from promotion rather than reproduced into the current
engine. `causal_embargo_v1` admits a training row only after its complete label
horizon is observable. The corrected transition engine updates its histories
only from transitions completed before the decision week. All twelve state and
corrected-meta prefix checks then passed exactly, repeated meta fits were
deterministic, and eleven focused tests passed.

The historical state labels remain reproduced, but the old meta probabilities
are retained only as contaminated lineage. Relative to the saved probabilities,
the corrected version changed 910 regime-confidence rows, 883 transition-quality
rows, and 910 tail-risk rows. This means previously quoted GGG performance still
describes the selected historical implementation and must not be presented as a
fully lookahead-clean ML result.

The corrected current Layer 2b bundle is complete through 2026-08-07. Its market
state is `calm_trend`, risk state is `calm`, regime confidence is 0.5217,
transition quality is 0.1558, and tail-risk probability is 0.2510. The next and
final portability stage is an end-to-end allocator comparison using these
corrected inputs. After that gate, new repository and strategy experiments can
resume against the clean current benchmark. No forward clock or live execution
was enabled.

References:

- `src/systematic_trader/ggg_layer2b.py`
- `scripts/audit_ggg_layer2b_portable_batch_58.py`
- `tests/test_ggg_layer2b.py`
- `config/ggg_layer2b_causal_v1.json`
- `data/layer2b_vintages/20260812T035702Z_20260812T090851Z_causalmeta_adc08ddb4c57/manifest.json`
- `evidence/ggg_layer2b_portable_batch_58/state_historical_equivalence.csv`
- `evidence/ggg_layer2b_portable_batch_58/meta_prediction_leakage_comparison.csv`
- `evidence/ggg_layer2b_portable_batch_58/prefix_invariance.csv`
- `evidence/ggg_layer2b_portable_batch_58/latest_state_and_predictions.csv`
- `evidence/ggg_layer2b_portable_batch_58/result.json`
- `evidence/ggg_layer2b_portable_batch_58/report.md`

## Step 83 — Freeze the complete corrected-causal GGG benchmark

Batch 59 assembled the immutable price, regime, Layer 2a, and corrected Layer
2b vintages into end-to-end bundle `ggg_causal_v2_027530550388432a`. The
allocator now trains without the current row's realized return and rebalances
monthly only on a calendar-final Friday. This removed the old behavior that
treated an incomplete terminal month as a known month-end.

All 18 staged historical-cutoff comparisons were prefix invariant, with maximum
difference 4.44e-16. Repeated full runs were deterministic, the incomplete
2026-08-07 August row was absent from the monthly rebalance log, all current
weights were finite and summed to one, and 13 focused regime/Layer 1/Layer
2a/Layer 2b/allocator tests passed. Correcting the timing rules changed 1,029
historical final-weight rows, with maximum single-asset difference 0.0163.

At the primary 50-basis-point transaction-cost assumption, the corrected
current history through 2026-08-07 produced the following retrospective
figures:

| Window | CAGR | Sharpe (zero RF) | Sortino | Maximum drawdown | Annual one-way turnover |
|---|---:|---:|---:|---:|---:|
| Trailing 1 year | 13.52% | 1.439 | 2.270 | -7.71% | 3.91x |
| Trailing 2 years | 12.63% | 1.436 | 2.250 | -7.71% | 3.90x |
| Trailing 3 years | 12.31% | 1.480 | 2.356 | -7.71% | 3.60x |
| Since 2024-01-05 | 12.43% | 1.515 | 2.404 | -7.71% | 3.75x |
| Full history | 5.52% | 0.744 | 1.074 | -11.87% | 3.22x |

On the common frozen history ending 2026-04-10, the corrected trailing-three-
year CAGR/Sharpe/drawdown at 50 bps were 12.90% / 1.544 / -7.37%, versus
12.89% / 1.544 / -7.36% for the saved legacy implementation. The correction
therefore materially improves causal trust, not historical profitability.

The current allocation has 14 nonzero holdings and 24.98% in BIL; it is a
research output, not a live order. Historical selection, source-vintage, and
universe limitations remain, and these results do not guarantee future profit.
No forward clock or live execution was enabled.

With the clean benchmark frozen, the next research program is now open. It
will first retest the strongest distinct saved candidates against this exact
causal baseline, then expand repository-derived signal families, revisit
cost-aware ML confidence using fully embargoed nested walk-forward evaluation,
and finally test allocator/execution interactions. Recent net returns at 50 bps
are the primary objective, with 10/100 bps, robustness, causal, ablation, and
multiple-testing gates retained.

References:

- `src/systematic_trader/ggg_independent.py`
- `scripts/audit_ggg_end_to_end_batch_59.py`
- `tests/test_ggg_allocator_calendar.py`
- `config/ggg_causal_v2_benchmark.json`
- `config/post_ggg_causal_v2_research_program.json`
- `data/ggg_vintages/ggg_causal_v2_027530550388432a/manifest.json`
- `evidence/ggg_end_to_end_batch_59/performance.csv`
- `evidence/ggg_end_to_end_batch_59/prefix_invariance.csv`
- `evidence/ggg_end_to_end_batch_59/current_holdings.csv`
- `evidence/ggg_end_to_end_batch_59/result.json`
- `evidence/ggg_end_to_end_batch_59/report.md`

## Step 84 — Begin improving GGG with fixed saved strategy definitions

Batch 60 began the post-clean-benchmark research program by rebuilding eight
previously saved robust momentum/trend definitions from the immutable GGG price
vintage. Each definition was tested standalone and at fixed 10%, 20%, and 30%
allocations to corrected-causal GGG, producing 24 predeclared blend trials.

Every candidate rebuild was deterministic. All 24 candidate/cutoff prefix
checks were exact, confirming that later observations did not alter earlier
candidate allocations. The formulas retained their one-week signal lag and
used only genuine calendar-final Fridays for monthly decisions. Portfolio-level
turnover costs were recalculated at 10, 50, and 100 basis points.

The only family to pass every first-screen gate was the fixed cross-sectional
momentum candidate `candidate-052f66f29b9fafbe`. Its 10%, 20%, and 30% blends
all passed the declared recent-return, Sharpe, drawdown, full-history-return,
and 24-trial adjusted paired block-bootstrap gates. The strongest point estimate
was the 30% version, saved as provisional candidate
`candidate-ggg-xsmom-30-v1`.

At the primary 50-basis-point cost assumption, its retrospective results versus
the causal GGG baseline were:

| Window | Baseline CAGR | Provisional CAGR | Provisional Sharpe | Provisional drawdown |
|---|---:|---:|---:|---:|
| Trailing 1 year | 13.52% | 17.86% | 1.629 | -8.51% |
| Trailing 2 years | 12.63% | 16.11% | 1.574 | -8.51% |
| Trailing 3 years | 12.31% | 14.89% | 1.553 | -8.51% |
| Since 2024-01-05 | 12.43% | 15.43% | 1.619 | -8.51% |
| Full history | 5.52% | 6.35% | 0.750 | -15.37% |

At 100 bps, the provisional blend's trailing-three-year CAGR and Sharpe remained
13.10% and 1.378, versus 10.31% and 1.252 for baseline. Annual one-way turnover
fell from 3.60x to 3.16x in the 50-bps trailing-three-year window. Its adjusted
paired-bootstrap p-value was 0.0494 after all 24 trials.

This is a promising first improvement, not a replacement winner. Full-history
maximum drawdown worsened from -11.87% to -15.37%, and all comparisons use
already observed history. The candidate therefore remains provisional pending
deeper subperiod, sizing-neighborhood, dependence, and drawdown validation plus
untouched forward evidence. No live trading or forward clock was enabled.

References:

- `config/ggg_saved_strategy_improvement_batch_60.json`
- `scripts/run_ggg_saved_strategy_improvement_batch_60.py`
- `research_registry/strategy_candidates.json`
- `evidence/ggg_saved_strategy_improvement_batch_60/performance.csv`
- `evidence/ggg_saved_strategy_improvement_batch_60/blend_comparison.csv`
- `evidence/ggg_saved_strategy_improvement_batch_60/prefix_invariance.csv`
- `evidence/ggg_saved_strategy_improvement_batch_60/provisional_challenger_current_holdings.csv`
- `evidence/ggg_saved_strategy_improvement_batch_60/result.json`
- `evidence/ggg_saved_strategy_improvement_batch_60/report.md`

## Step 85 — Deep-validate the momentum blend and identify a return-first successor

Batch 61 treated `candidate-ggg-xsmom-30-v1` as the favored challenger and
tested whether its improvement survived broader historical diagnostics. It
evaluated 76 overlapping rolling three-year windows, five nearby momentum
weights from 20% through 40%, five fixed subperiods, calendar years, 50/100-bps
costs, maximum-drawdown episodes, and six predeclared causal dynamic variants.

The static 30% challenger passed all declared deep-validation gates. It beat
causal GGG's CAGR in 85.5% of rolling three-year windows; its median rolling
improvement was +0.62 percentage points and its worst was -0.93 points. It
also beat GGG in five of the six calendar years from 2021 onward. Every nearby
20%, 25%, 30%, 35%, and 40% allocation improved current trailing-three-year
CAGR at 50 bps, and the 30% version retained its advantage at 100 bps.

The diagnostics also confirmed that the improvement is not uniform. Static
30% increased CAGR in every broad subperiod, but Sharpe fell modestly during
the 2008-2012 and 2020-2022 periods. Its worst full-history drawdown remained
the February-March 2020 episode at -15.37%, versus -11.87% for GGG.

Of six causal state/exposure modifications, only `exposure_boost_40_20` passed
the predeclared return route. It assigns 40% to the fixed cross-sectional
momentum sleeve when that sleeve's own non-cash exposure is at least 75%, and
20% otherwise. This rule uses only the already lagged candidate allocation at
the decision date. It is saved as return-first provisional candidate
`candidate-ggg-xsmom-exposure-boost-v2`.

At 50 bps, the return-first candidate produced 19.31%, 17.23%, and 15.72% CAGR
over the trailing one, two, and three years, respectively. Its trailing-three-
year Sharpe was 1.558, maximum drawdown -8.90%, and annual one-way turnover
3.08x. At 100 bps, trailing-three-year CAGR and Sharpe remained 13.95% and
1.395. Full-history CAGR was 6.54%, but maximum drawdown worsened to -16.61%.
The six-trial adjusted paired-bootstrap p-value for its recent advantage over
static 30% was 0.0159.

The exposure-aware candidate is now the return-first research leader, while
static 30% remains the less aggressive validated challenger. Neither is final:
the return leader consciously accepts worse historical crash drawdown, the ETF
universe is not survivorship-safe, and no untouched forward record exists. No
live trading or forward clock was enabled.

References:

- `config/ggg_xsmom_deep_validation_batch_61.json`
- `scripts/run_ggg_xsmom_deep_validation_batch_61.py`
- `research_registry/strategy_candidates.json`
- `evidence/ggg_xsmom_deep_validation_batch_61/alpha_neighborhood.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/rolling_3y_comparison.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/subperiods.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/calendar_years.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/dynamic_variant_qualification.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/maximum_drawdown_episodes.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/selected_variant_alpha.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/selected_variant_weights.csv`
- `evidence/ggg_xsmom_deep_validation_batch_61/result.json`
- `evidence/ggg_xsmom_deep_validation_batch_61/report.md`

## Step 86 — Open aggressive return discovery and reach the 20% target

Batch 62 deliberately relaxed only the drawdown budgets. It retained causal
timing, one-week signal lags, calendar-final monthly decisions, 50/100-bps
costs, deterministic rebuilds, prefix invariance, rolling-window consistency,
and multiple-testing control. No leverage was allowed.

The batch tested 35 candidates spanning higher global cross-sectional-momentum
allocations, concentrated top-two/top-four momentum, sector momentum across nine
sector ETFs, three-way GGG/global/sector combinations, and residual-momentum
additions to the prior return leader. All source rebuilds were deterministic
and all 33 source/cutoff prefix checks were exact.

The strongest recent-return point estimate was 100% of the fixed global
cross-sectional-momentum source, named `global_xsmom_100`. At 50 bps it reached
28.18%, 23.99%, and 20.55% CAGR over the trailing one, two, and three years.
Trailing-three-year Sharpe was 1.513, maximum drawdown -11.31%, and annual
one-way turnover 2.76x. At 100 bps, trailing-three-year CAGR remained 18.89%.
Full-history CAGR was 7.66% with -24.14% maximum drawdown.

| Engine | 1y CAGR | 2y CAGR | 3y CAGR | 3y Sharpe | 3y drawdown | Full drawdown |
|---|---:|---:|---:|---:|---:|---:|
| Prior return leader | 19.31% | 17.23% | 15.72% | 1.558 | -8.90% | -16.61% |
| Global xsmom 70% | 23.73% | 20.62% | 18.16% | 1.546 | -10.10% | -20.40% |
| Global xsmom 80% | 25.22% | 21.76% | 18.97% | 1.537 | -10.50% | -21.66% |
| Global xsmom 100% | 28.18% | 23.99% | 20.55% | 1.513 | -11.31% | -24.14% |

The 100% engine beat the prior return leader in 65.8% of rolling three-year
windows, with median CAGR improvement +0.81 percentage points. It passed every
return, cost, rolling-consistency, full-return, no-leverage, and deliberately
lenient drawdown gate. It narrowly failed only the multiplicity gate: raw paired
block-bootstrap p-value 0.00337 became 0.1178 after adjustment for all 35 trials,
above the predeclared 0.10 threshold.

Accordingly, the engine is saved as unqualified aggressive return ceiling
`candidate-global-xsmom-100-return-ceiling-v1`, not promoted over the qualified
return leader. It demonstrates that the requested 20% recent CAGR target is
reachable without leverage, but it requires an independent new-vintage or
untouched confirmation before stronger claims. Sector and residual-momentum
additions did not beat this ceiling in the current batch. Drawdown engineering
is intentionally deferred. No live trading or forward clock was enabled.

References:

- `config/aggressive_return_discovery_batch_62.json`
- `scripts/run_aggressive_return_discovery_batch_62.py`
- `research_registry/strategy_candidates.json`
- `evidence/aggressive_return_discovery_batch_62/performance.csv`
- `evidence/aggressive_return_discovery_batch_62/qualification.csv`
- `evidence/aggressive_return_discovery_batch_62/source_prefix_invariance.csv`
- `evidence/aggressive_return_discovery_batch_62/source_determinism.csv`
- `evidence/aggressive_return_discovery_batch_62/selected_candidate_weights.csv`
- `evidence/aggressive_return_discovery_batch_62/selected_candidate_current_holdings.csv`
- `evidence/aggressive_return_discovery_batch_62/result.json`
- `evidence/aggressive_return_discovery_batch_62/report.md`

## Step 87 — Add an independent trend-consistency source and reach 24% recent CAGR

Batch 63 searched for a return source that was not merely another copy of the
52-week cross-sectional-momentum ceiling. Guided by the Awesome Systematic
Trading signal/indicator catalog, it independently implemented causal weekly
breakout, acceleration, downside-adjusted momentum, trend consistency,
short-term reversal, risk-adjusted 13-week strength, multi-horizon strength,
and residual-momentum families. Previously tested repository oscillator and
candlestick rules were not recycled because their cost-adjusted evidence was
already decisively negative.

Sixteen standalone sources were built across top-three and top-six variants,
then 48 fixed 20/40/60% blends were tested against the Batch 62 aggressive
momentum ceiling. All signals were delayed one week, monthly decisions used
true calendar-final Fridays, every source rebuilt deterministically, three
focused tests passed, and all 48 source/cutoff prefix checks were exact.

Six standalone sources passed their return, cost, full-history, correlation,
and drawdown screens. The strongest was `trend_consistency_top3`, which ranks
52-week skip-four-week momentum multiplied by the prior 26-week share of
positive weekly returns. Standalone it produced 26.07% trailing-three-year CAGR
at 50 bps and 24.08% at 100 bps, but its full-history drawdown was -42.83%.

The highest blend combined 40% of the Batch 62 aggressive xsmom ceiling with
60% trend consistency. At 50 bps it produced 35.45%, 28.71%, and 24.10% CAGR
over the trailing one, two, and three years. Trailing-three-year Sharpe was
1.475, maximum drawdown -13.40%, and annual one-way turnover 2.98x. At 100 bps,
trailing-three-year CAGR remained 22.27%. Full-history CAGR was 8.39%, with
-30.61% maximum drawdown.

The blend beat the prior aggressive ceiling in 55.3% of rolling three-year
windows and passed every return, cost, rolling, no-leverage, and intentionally
lenient drawdown gate. However, the recent paired block-bootstrap advantage was
not broad enough: raw p-value 0.1774, so it failed the statistical gate even
before familywise adjustment.

The blend is therefore saved as unconfirmed aggressive ceiling
`candidate-xsmom-trend-consistency-60-return-ceiling-v2`, not as a qualified
winner. It establishes a 24.10% recent-CAGR research ceiling without leverage,
but its improvement may be disproportionately tied to the recent trend regime
and requires new-vintage or untouched confirmation. Drawdown engineering remains
deferred. No live trading or forward clock was enabled.

References:

- `src/systematic_trader/independent_return_sources.py`
- `tests/test_independent_return_sources.py`
- `config/independent_return_source_discovery_batch_63.json`
- `scripts/run_independent_return_source_discovery_batch_63.py`
- `research_registry/strategy_candidates.json`
- `evidence/independent_return_source_discovery_batch_63/standalone_qualification.csv`
- `evidence/independent_return_source_discovery_batch_63/blend_qualification.csv`
- `evidence/independent_return_source_discovery_batch_63/performance.csv`
- `evidence/independent_return_source_discovery_batch_63/prefix_invariance.csv`
- `evidence/independent_return_source_discovery_batch_63/determinism.csv`
- `evidence/independent_return_source_discovery_batch_63/selected_or_best_weights.csv`
- `evidence/independent_return_source_discovery_batch_63/result.json`
- `evidence/independent_return_source_discovery_batch_63/report.md`

## Step 88 — Test cross-asset confirmation and embargoed ML against the 24% ceiling

Batch 64 tested whether cross-asset context or a causal learned allocator could
confirm and diversify the 24.10% Batch 63 ceiling. The fixed budget contained
six interpretable cross-asset allocation rules and six expanding ridge models.
The learned target was the next four weeks of trend-consistency excess return
over the aggressive xsmom core.

Every ML fit required at least 60 prior monthly examples and admitted a label
only after its entire four-week outcome ended strictly before the new decision.
The six models generated 450 predictions in total. Every audit row passed the
label-horizon embargo, all full builds were deterministic, all 36 candidate/
cutoff prefix comparisons were exact, and three focused feature/embargo/prefix
tests passed.

The ML result was negative: all six embargoed models reduced trailing one-,
two-, and three-year returns relative to the fixed 24.10% ceiling and none
passed the return, cost, rolling, or statistical route. ML promotion is rejected
for this batch rather than tuned further on the same observed history.

The strongest cross-asset point estimate was `breadth_boost`. It measures the
prior week's share of 30 assets with positive 13-week returns. When at least 65%
are positive, it assigns 100% to top-three trend consistency; otherwise it uses
40% trend consistency and 60% aggressive xsmom.

At 50 bps, breadth boost produced 46.08%, 35.91%, and 28.17% CAGR over the
trailing one, two, and three years. Trailing-three-year Sharpe was 1.461,
maximum drawdown -15.23%, and annual one-way turnover 4.16x. At 100 bps,
trailing-three-year CAGR remained 25.52%. Full-history 50-bps CAGR was 8.93%
with -31.13% maximum drawdown; full-history drawdown at 100 bps reached -40.42%.

The point estimate did not confirm broadly. It beat the 24.10% ceiling in only
43.4% of rolling three-year windows, with median CAGR difference -0.29 points.
Its raw recent paired-bootstrap p-value was 0.0530, but the 12-trial adjusted
value was 0.636. It therefore failed the rolling and multiplicity gates.

The strategy is saved only as unconfirmed research ceiling
`candidate-breadth-confirmed-trend-return-ceiling-v3`. It raises the unlevered
recent-CAGR ceiling to 28.17%, but the qualified return leader remains unchanged
and the 24.10% ceiling remains the stronger comparator. Current breadth routes
the research ceiling entirely into XLK, XLE, and USO. No live trading or forward
clock was enabled.

References:

- `src/systematic_trader/return_confirmation.py`
- `tests/test_return_confirmation.py`
- `config/return_confirmation_diversification_batch_64.json`
- `scripts/run_return_confirmation_diversification_batch_64.py`
- `research_registry/strategy_candidates.json`
- `evidence/return_confirmation_diversification_batch_64/qualification.csv`
- `evidence/return_confirmation_diversification_batch_64/performance.csv`
- `evidence/return_confirmation_diversification_batch_64/ml_embargo_audit.csv`
- `evidence/return_confirmation_diversification_batch_64/prefix_invariance.csv`
- `evidence/return_confirmation_diversification_batch_64/determinism.csv`
- `evidence/return_confirmation_diversification_batch_64/selected_or_best_weights.csv`
- `evidence/return_confirmation_diversification_batch_64/result.json`
- `evidence/return_confirmation_diversification_batch_64/report.md`

## Step 89 — Adversarially challenge the 28% breadth ceiling and start its forward clock

Batch 65 froze the 65% breadth rule unchanged and challenged it without adding
another tuned return variant. The audit compared simple sector benchmarks,
removed the strongest recent calendar year, added one/two/four-week feature
delays, evaluated a 30-configuration parameter neighborhood, ranked the rule
against 100 permuted breadth histories, ran a past-only annual rolling selector,
tested six historical start dates, estimated single- and multifactor exposure,
and charged 50/100/200-bps costs.

The candidate retained 28.17% trailing-three-year CAGR at 50 bps versus 24.10%
for the prior ceiling. Every one of the 30 nearby threshold/high/low-weight
configurations beat the prior ceiling. Two of three additional feature delays
also beat it: one extra week produced 28.54%, two extra weeks 25.03%, and four
extra weeks 21.70%.

Excluding the candidate's strongest recent year, 2025, still left +1.97
percentage points of CAGR advantage over the prior ceiling. The frozen breadth
sequence ranked at the 95th percentile of 100 permuted breadth histories. Its
full-history multifactor regression against SPY, QQQ, XLK, and XLE estimated
+2.72% annual alpha with R-squared 0.353. At 200-bps costs its recent-three-year
drawdown remained inside the lenient budget at -18.36%.

Two adversarial gates failed. First, a strictly past-only annual selector among
the 30 neighboring rules produced only 16.88% trailing-three-year CAGR, so the
high retrospective point result did not reproduce through causal historical
model selection. Second, buy-and-hold XLK returned 31.72% over the same recent
three-year window, exceeding the candidate's 28.17%, although XLK had lower
Sharpe (1.274 versus 1.461) and worse drawdown (-24.02% versus -15.23%).

The breadth engine therefore remains an unconfirmed aggressive ceiling rather
than receiving stronger status. Its neighborhood, delay, omitted-year, placebo,
factor-alpha, and high-cost evidence is encouraging, but the rolling-selector
and simple-benchmark failures show that recent technology leadership explains
an important part of the result.

A 52-week untouched protocol was frozen before the next eligible observation.
The first eligible decision is 2026-08-14 and first eligible realization is
2026-08-21. The forward clock is active with zero observed weeks; changing the
selection rule is prohibited for that record. This is evidence collection only,
not paper or live trading.

References:

- `config/breadth_ceiling_adversarial_validation_batch_65.json`
- `scripts/run_breadth_ceiling_adversarial_validation_batch_65.py`
- `config/forward/breadth_confirmed_trend_return_ceiling_v3.json`
- `evidence/forward_breadth_confirmed_trend_return_ceiling_v3/status.json`
- `research_registry/strategy_candidates.json`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/performance.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/parameter_neighborhood.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/feature_delays.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/placebo_breadth.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/calendar_years.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/rolling_selector_choices.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/rolling_selector_performance.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/start_date_sensitivity.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/factor_attribution.csv`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/result.json`
- `evidence/breadth_ceiling_adversarial_validation_batch_65/report.md`

## Step 90 — Run the exhaustive return-first campaign and preserve three higher-return candidates

Batch 66 used a frozen 2023-08-04 training cutoff and one consolidated search
budget. It evaluated 805 unlevered, long-only candidates: 72 advanced causal
signals across trend quality, leadership persistence, gain-to-pain,
downside efficiency, low-volatility momentum, high proximity, volatility
breakout, drawdown recovery, and rank-consensus families; top-one/two/three
portfolios; equal and score-inverse-volatility construction; XLK and breadth
core blends; four cross-asset regimes; simple benchmark portfolios; two
strictly past-only selectors; and eight nonlinear ML allocators.

All source signals were delayed one week and applied to the next weekly return.
The run charged 50/100/200-bps costs, rebuilt all 805 candidates
deterministically, passed 216 truncated-history prefix checks, and generated
800 nonlinear predictions. Every ML label's full four-week outcome ended
strictly before its prediction decision.

The best of 30 finalists fixed without holdout outcomes was an expanding
histogram-gradient-boosting sign allocator between XLK and the frozen breadth
ceiling. It produced 34.71% holdout CAGR at 50 bps, 32.14% at 100 bps, and
27.10% at 200 bps, with Sharpe 1.432 and -19.77% drawdown. It beat XLK by 2.99
percentage points and the breadth ceiling by 6.54 points. It also passed the
delay majority and remained ahead after excluding 2025. It did not qualify:
its raw p-value versus XLK was 0.348, its 30-trial adjusted value was 1.0, and
it beat XLK in only 17.1% of full-history rolling three-year windows.

The unrestricted retrospective search found a higher point ceiling: broad
risk-on rank-consensus top-one at 52.35% holdout CAGR at 50 bps, 46.74% at
100 bps, 36.07% at 200 bps, and 26.09% at 300 bps. Its 90-rule adversarial
neighborhood beat XLK 71.1% of the time, two of three delays beat XLK, and the
frozen regime sequence ranked at the 98.5th percentile of 200 placebos. It
still failed confirmation: after removing 2025 it lost to XLK by 5.46 points,
multifactor alpha was -1.97%, and full-history rolling win share was 23.7%.
It is explicitly a hindsight-selected ceiling, not a replacement.

Finally, a strictly past-only annual selector chose among the 90 neighboring
rules using only each prior 260 weeks. It produced 41.72% holdout CAGR at 50
bps, 36.78% at 100 bps, and 27.34% at 200 bps. It beat both XLK and the breadth
ceiling even after removing 2025, and full-history CAGR was 10.54%. It also
failed replacement confirmation because only one of three added delays beat
the breadth ceiling, full drawdown was -50.70%, multifactor alpha was -2.62%,
raw p-value versus XLK was 0.202, and rolling win share was 3.9%.

No candidate replaced the qualified return leader or the existing 28.17%
forward candidate. All three new results were saved with their failed gates.
The past-only selector was chosen as the single new high-return candidate for
a frozen 52-week forward record because its historical annual choices never
used future outcomes. Its first eligible decision is 2026-08-14 and first
eligible realization is 2026-08-21, with zero observed weeks. The previously
frozen breadth protocol was not modified. No leverage, shorting, paper broker,
or live trading was enabled.

References:

- `src/systematic_trader/return_first_search.py`
- `config/exhaustive_return_first_discovery_batch_66.json`
- `config/batch66_retrospective_ceiling_adversarial.json`
- `scripts/run_exhaustive_return_first_discovery_batch_66.py`
- `scripts/run_batch66_retrospective_ceiling_adversarial.py`
- `config/forward/past_only_consensus_selector_return_v1.json`
- `evidence/forward_past_only_consensus_selector_return_v1/status.json`
- `research_registry/strategy_candidates.json`
- `evidence/exhaustive_return_first_discovery_batch_66/candidate_inventory.csv`
- `evidence/exhaustive_return_first_discovery_batch_66/training_rankings.csv`
- `evidence/exhaustive_return_first_discovery_batch_66/holdout_validation.csv`
- `evidence/exhaustive_return_first_discovery_batch_66/nonlinear_ml_embargo_audit.csv`
- `evidence/exhaustive_return_first_discovery_batch_66/source_prefix_invariance.csv`
- `evidence/exhaustive_return_first_discovery_batch_66/result.json`
- `evidence/exhaustive_return_first_discovery_batch_66/report.md`
- `evidence/exhaustive_return_first_discovery_batch_66/retrospective_ceiling_adversarial/result.json`
- `evidence/exhaustive_return_first_discovery_batch_66/retrospective_ceiling_adversarial/report.md`

## Step 91 — Test a frozen high-return ensemble and keep the 52% engine diagnostic-only

Batch 67 tested whether combining the 41.72% past-only selector, 34.71%
embargoed histogram-gradient-boosting allocator, XLK, and the 28.17% breadth
ceiling could preserve high recent return while making the result broader. A
frozen 10% allocation grid required at least two components and capped each at
70%, producing 246 clean-grid candidates. The only selection score used
history ending 2023-08-04: 60% trailing-five-year CAGR, 30% trailing-three-year
CAGR, and 10% trailing-five-year Sharpe.

The pre-holdout selection was 70% XLK and 30% embargoed HGB. In the later
period it returned 32.83% CAGR at 50 bps, 32.07% at 100 bps, and 30.56% at
200 bps, with Sharpe 1.361 and -22.55% drawdown. It beat XLK's 31.72% and the
breadth ceiling's 28.17%, all three added execution delays beat breadth, and
it remained ahead of both comparators after removing its strongest complete
year, 2024.

The ensemble did not qualify. It missed the frozen 35% return target, beat XLK
in only 25.0% of full-history rolling three-year windows, had -0.20% estimated
multifactor annual alpha, and its raw p-value versus XLK was 0.350; adjustment
for all 246 clean allocations was 1.0. The allocation was 95.31% explained by
XLK exposure in the single-factor regression and its current simulated
holdings were 82.56% XLK, 12.06% XLE, and 5.39% USO. The blend therefore
diluted the standalone ML candidate rather than creating a stronger successor.

The 52.35% hindsight-selected rule was not discarded. Eight diagnostic
overlays allocated 10/20/30/40% of it to the training-selected base and to the
hindsight-best clean blend. The best overlay reached 45.86% holdout CAGR,
Sharpe 1.615, and -21.27% drawdown. The more defensible overlay on the
pre-holdout-selected base reached 41.66% with 40% hindsight-rule allocation,
Sharpe 1.710, and -15.83% drawdown. These overlays remain ineligible because
their 52.35% component and the best overlay were chosen after observing the
same holdout period.

No ensemble was promoted and no additional forward clock was started. The
41.72% past-only selector and 28.17% breadth engine continue their already
frozen 52-week records. No leverage, shorting, paper trading, or live trading
was enabled.

References:

- `config/return_first_ensemble_batch_67.json`
- `scripts/run_return_first_ensemble_batch_67.py`
- `evidence/return_first_ensemble_batch_67/training_rankings.csv`
- `evidence/return_first_ensemble_batch_67/clean_grid_holdout_diagnostic.csv`
- `evidence/return_first_ensemble_batch_67/hindsight_52pct_overlay_diagnostic.csv`
- `evidence/return_first_ensemble_batch_67/execution_delay_stress.csv`
- `evidence/return_first_ensemble_batch_67/component_correlations.csv`
- `evidence/return_first_ensemble_batch_67/factor_attribution.csv`
- `evidence/return_first_ensemble_batch_67/result.json`
- `evidence/return_first_ensemble_batch_67/report.md`

## Step 92 — Freeze the exact 41.66% 60/40 blend for forward observation

The requested Batch 67 diagnostic blend was reconstructed from its two saved
source artifacts and frozen without further tuning. It assigns 60% to the
pre-2023-selected Batch 67 base (70% XLK plus 30% of the embargoed HGB
allocator) and 40% to the hindsight-selected broad-risk-on rank-consensus
top-one ceiling. The rebuilt weights were deterministic, summed to one on
every date, and were saved with SHA-256
`a3f5e0256fa30db10c3836fc7adc39609ea1dcd83d7e29a069a7e1ff916e34c4`.

At 50-bps costs its retrospective holdout CAGR was 41.66%, Sharpe 1.710, and
maximum drawdown -15.83%. Full-history CAGR was 12.60% with -44.10% maximum
drawdown. Its final simulated allocation was 49.53% XLK, 47.23% XLE, and 3.23%
USO. These statistics remain research-only because both the 52.35% component
and its 40% overlay weight were chosen after observing the same historical
holdout.

A 52-week forward-only protocol was frozen before the first eligible new
observation. The first eligible decision is 2026-08-14 and first eligible
realization is 2026-08-21. The status is 0/52 observed weeks. No changes to the
formula or component weights are permitted for this record. This does not
enable paper or live trading.

References:

- `scripts/freeze_return_first_60_40_blend_v1.py`
- `config/forward/return_first_60_40_blend_v1.json`
- `evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv`

## Step 101 — Test four trading schedules and retain monthly execution

The frozen 60/40 return-first candidate was preserved as the incumbent and
three causal schedule challengers were fixed before results were observed. The
full-weekly version retrained the embargoed histogram-gradient-boosting switch
every Friday using a 240-row minimum (the weekly equivalent of five years),
refreshed the broad-risk-on rank-consensus top-one sleeve weekly, and retained
the exact 60/40 and internal 70/30 component weights. The buffered version
passed those targets through a fixed 5% one-way no-trade band. The
monthly-emergency version executed at calendar month-end or when weekly target
turnover reached 15% or BIL changed by 10%.

Monthly remained decisively best. At 50-bps costs its retrospective holdout
CAGR was 41.66%, Sharpe 1.710, maximum drawdown -15.83%, and annual one-way
turnover 3.55 times capital. Full weekly refresh returned 20.64%, Sharpe 1.017,
drawdown -21.18%, and turnover 12.70. The 5% buffer improved weekly CAGR to
22.71% and reduced turnover to 10.56, but remained 18.95 percentage points
behind monthly. Monthly-emergency returned 20.66% with turnover 12.33 because
its emergency threshold triggered too frequently.

The shortfall was not merely transaction costs. With costs disabled, monthly
returned 44.20%, full weekly 28.52%, buffered weekly 29.34%, and
monthly-emergency 28.31%. At 200-bps costs monthly still returned 34.27%, while
full weekly fell to -0.30%, monthly-emergency to 0.29%, and buffered weekly to
4.75%. A one-week additional execution delay improved full weekly to 31.54%
and buffered weekly to 31.63%, indicating that raw weekly signals were too
reactive, but delayed monthly remained higher at 37.32%.

The weekly target was deterministic, every ML fit used only labels ending
strictly before its decision, both future-truncation prefix checks matched at
zero error, all portfolios were long-only and fully invested, and 20 focused
execution/signal tests passed. The evidence rejects weekly replacement for
this formula. The frozen monthly incumbent and its forward clock remain
unchanged.

References:

- `config/return_first_frequency_test_v1.json`
- `scripts/run_return_first_frequency_test_v1.py`
- `evidence/return_first_frequency_test_v1/comparison.csv`
- `evidence/return_first_frequency_test_v1/performance.csv`
- `evidence/return_first_frequency_test_v1/execution_delay_stress.csv`
- `evidence/return_first_frequency_test_v1/prefix_invariance.csv`
- `evidence/return_first_frequency_test_v1/weekly_hgb_embargo_audit.csv`
- `evidence/return_first_frequency_test_v1/result.json`
- `evidence/return_first_frequency_test_v1/report.md`
- `evidence/forward_return_first_60_40_blend_v1/current_holdings.csv`
- `evidence/forward_return_first_60_40_blend_v1/result.json`
- `evidence/forward_return_first_60_40_blend_v1/status.json`
- `research_registry/strategy_candidates.json`

## Step 93 — Build the free SEC point-in-time fundamental foundation

The next independent-information program began with the official SEC EDGAR
Submissions and Company Facts interfaces. A frozen 20-company technology and
energy pilot was declared solely for engineering. It is explicitly current
membership, not survivorship-safe, and cannot support strategy-promotion
claims.

The new ingestion layer caches ticker/CIK mapping, current and additional
submission histories, and per-company Company Facts JSON. Every response will
carry its URL, retrieval time, SHA-256, byte count, status, and cache key. The
client waits at least 0.25 seconds between requests—four per second, below the
SEC's published ten-per-second ceiling—and refuses live access unless the
`SEC_USER_AGENT` environment variable supplies a real identifying contact.

Facts are joined to precise EDGAR acceptance timestamps by accession number.
Missing acceptance timestamps receive a conservative end-of-filing-day UTC
fallback. Amendments remain separate later events and never overwrite earlier
history. Fifteen canonical metrics cover revenue, profitability, cash flow,
capital expenditure, assets, liabilities, equity, cash, debt, shares,
repurchases, and stock compensation. Direct-quarter, year-to-date, annual, and
instantaneous contexts are classified separately so incompatible periods
cannot be mixed silently.

The derived factor-input builder applies a strict `available_at < decision`
rule, uses only direct-quarter flow values and instantaneous balance-sheet
values, and calculates year-over-year growth only from the same fiscal period
that was also available at the decision. It prepares margins, free cash flow,
debt, cash, equity, dilution, buyback, and stock-compensation inputs without
yet assigning a strategy score.

Four focused synthetic tests passed. An original Q1 revenue value was visible
before its amendment, the restated value appeared only after the amendment's
acceptance, year-over-year growth changed at the correct time, and live network
access was rejected without a declared SEC contact. No live SEC observations
were downloaded because that contact setting is currently absent. Fundamental
factor testing remains unauthorized until a real vintage and its coverage,
unit, duplicate, amendment, and period audits pass.

References:

- `config/sec_fundamental_pilot_v1.json`
- `src/systematic_trader/sec_point_in_time.py`
- `scripts/build_sec_fundamental_vintage.py`
- `tests/test_sec_point_in_time.py`
- `docs/SEC_FUNDAMENTAL_DATA_GUIDE.md`
- `evidence/sec_point_in_time_pilot_v1/result.json`
- `evidence/sec_point_in_time_pilot_v1/report.md`

## Step 94 — Build the live SEC vintage and diagnose five fundamental families

The user supplied a real SEC automated-access contact, used only as a transient
environment variable and not persisted in project artifacts. The initial SEC
request exposed gzip transport encoding, so the client was extended and tested
for gzip/deflate decoding before the complete live retrieval continued. The
raw cache contains 74 content-hashed SEC responses.

The final immutable SEC vintage `20260813T065239Z-sec-pit-v1` contains 57,736
canonical fact events for 20 companies, 1,270 accessions, and 453 amendment
events. It has zero duplicates, zero missing availability timestamps, and zero
reversed periods. Accession-to-submission join coverage is 99.92%, while every
filing row carries a precise EDGAR acceptance time. One SLB long-term-debt fact
reported in EUR was retained in raw provenance and excluded from the USD
factor layer rather than silently converted or discarded.

The quarterly as-of builder reconstructed 58 decisions from 2012 onward and
created 1,076 company-decision rows. Each decision had at least 17 companies
and the median was 19. Thirty-one raw and derived inputs met the declared
recent coverage requirement. The audit therefore authorized a pilot factor
diagnostic, but not strategy promotion.

A pinned yfinance container then froze 214,947 adjusted-price rows for the 20
companies plus SPY, XLK, and XLE. The price vintage explicitly lacks
point-in-time membership, delisted constituents, and complete revision history.
Five predeclared sector-neutral factor families were evaluated quarterly:
growth, profitability, balance-sheet quality, shareholder discipline, and an
equal-family composite. Each selected five stocks, applied the decision only
from the first later Friday, and charged 50/100/200-bps turnover costs.

Growth was the best pilot family. After 2023-08-04 it produced 36.14% CAGR at
50 bps, 35.30% at 100 bps, and 33.64% at 200 bps, versus XLK at 31.70%. Its
50-bps Sharpe was 1.512, drawdown -24.48%, and full diagnostic-period CAGR
17.51%. Current diagnostic holdings were equal 20% weights in AMD, AVGO, EOG,
KMI, and NVDA. However, its mean 13-week cross-sectional rank IC was only
0.009 and positive in 50.9% of decisions.

The adversarial growth audit passed two of three top-N variants, two of three
additional delays, 90% of leave-one-stock-out cases, removal of 2025, and a
positive +1.86% multifactor annual alpha. It failed the strict placebo gate at
the 92nd percentile and its raw p-value versus XLK was 0.361; adjustment for
the five tested families was 1.0. The growth family is therefore retained only
as an unconfirmed pilot signal and a priority for a future survivorship-safe
rebuild. It was not blended into any frozen strategy, and no live trading was
enabled.

References:

- `data/sec_vintages/20260813T065239Z-sec-pit-v1/manifest.json`
- `data/sec_vintages/20260813T065239Z-sec-pit-v1/audit_result.json`
- `data/sec_vintages/20260813T065239Z-sec-pit-v1/audit_report.md`
- `data/sec_pilot_price_vintages/20260813T070329Z-sec-pilot-prices/manifest.json`
- `scripts/audit_sec_fundamental_vintage.py`
- `scripts/acquire_sec_pilot_stock_prices.py`
- `config/sec_fundamental_factor_diagnostic_v1.json`
- `scripts/run_sec_fundamental_factor_diagnostic_v1.py`
- `scripts/audit_sec_growth_factor_diagnostic_v1.py`
- `evidence/sec_fundamental_factor_diagnostic_v1/result.json`
- `evidence/sec_fundamental_factor_diagnostic_v1/report.md`
- `evidence/sec_fundamental_factor_diagnostic_v1/growth_adversarial/result.json`
- `evidence/sec_fundamental_factor_diagnostic_v1/growth_adversarial/report.md`

## Step 95 — Rebuild the fundamental universe from historical SEC filers

The current-winner pilot was replaced at the membership layer with an
acceptance-dated SEC filer roster. All 57 quarterly Financial Statement Data
Set archives from 2012Q1 through 2026Q1 were downloaded and hashed; their
original ZIPs totaled 5.38 GB, while only the compact `SUB` tables were kept in
the reusable cache. The declared universe uses as-filed SIC and as-filed SEC
filer status. A CIK becomes eligible only after an accepted 10-K/10-Q, must be
Large Accelerated or Accelerated, and expires when its last qualifying filing
is more than 450 days old.

The immutable universe vintage contains 32,338 qualifying submissions and
35,493 company-decision membership rows over 57 quarterly decisions. It found
1,283 historical qualifying CIKs; 708 had no current SEC ticker association.
A present-day mapping would therefore have silently lost 63.1% of the 2012
universe and 25.6% of the 2023Q2 universe. This directly demonstrates why the
20-company pilot could not support a survivorship-safe return claim.

Historical symbol recovery used only explicit SEC XBRL tags. The last eligible
inline filing recovered 247 valid former-company symbols after an all-numeric
false symbol was caught and excluded. A second pass through standalone legacy
XBRL instance documents recovered another 193. After excluding multi-symbol
CIKs and 12 overlapping symbol-collision pairs, 947 CIKs had a single symbol
eligible for a price-availability probe. Identity coverage was at least 92.3%
from 2023 onward, but 268 CIKs remained unresolved.

The critical free-price probe then requested the 411 unique usable symbols
recovered for former or unmapped companies. Yahoo returned only 89 histories;
just 56 overlapped the correct issuer's eligible SEC period, while 33 were
classified as possible ticker reuse. Even optimistically assuming every
current SEC ticker has valid history, total recent coverage fell as low as
75.25%. Direct Yahoo chart checks confirmed that representative delisted
histories were not merely hidden by the client library. Complete delisting
returns were also absent.

The expanded growth backtest was therefore not run. Dropping the failed firms
would recreate the exact survivorship bias this rebuild was designed to remove.
The original growth result remains an unconfirmed engineering signal. The next
valid route is either a licensed delisting-complete source, a user-supplied
free-account dataset with verified historical identifiers, or a clearly
labeled recent diagnostic whose missing-company sensitivity is reported and
which remains ineligible for promotion.

References:

- `config/sec_historical_filer_universe_v1.json`
- `src/systematic_trader/sec_historical_universe.py`
- `scripts/build_sec_historical_filer_universe_v1.py`
- `scripts/recover_sec_historical_symbols_v1.py`
- `scripts/recover_sec_legacy_symbols_v1.py`
- `scripts/audit_sec_historical_identity_v1.py`
- `scripts/probe_recovered_symbol_prices_v1.py`
- `scripts/audit_sec_recovered_price_probe_v1.py`
- `tests/test_sec_historical_universe.py`
- `data/sec_historical_universe_vintages/20260813T095119Z-sec-historical-filers-v1/manifest.json`
- `data/sec_historical_identity_vintages/20260813T095732Z-sec-symbol-recovery-v1/manifest.json`
- `data/sec_historical_identity_vintages/20260813T100124Z-sec-legacy-symbol-recovery-v1/manifest.json`
- `data/sec_recovered_price_probe_vintages/20260813T100449Z-recovered-yahoo-price-probe-v1/manifest.json`
- `evidence/sec_historical_identity_v1/result.json`
- `evidence/sec_historical_identity_v1/report.md`
- `evidence/sec_recovered_price_probe_v1/result.json`
- `evidence/sec_recovered_price_probe_v1/report.md`

## Step 96 — Select and prepare a free delisted-price rescue source

Free and free-account data sources were reviewed against the actual blocker:
recent daily adjusted prices for former companies, historical identifier
coverage, corporate actions, reproducible downloads, and explicit failure
handling. Alpha Vantage provides a useful free historical listing/delisting
roster, but full adjusted daily history is a premium function. Nasdaq Data
Link's public WIKI archive is free with registration but stops in 2018. SimFin
free access exposes only five years of chart/fundamental history. Tiingo was
selected because its free individual EOD tier documents raw and adjusted
prices, dividends, splits, up to 60+ years of history, and limited delisted
symbol support.

Tiingo's public daily symbol inventory required no account and was acquired as
an immutable, hashed vintage containing 108,290 rows, including 42,475 USD
stock records. It matched 877 of the 947 single-symbol SEC identities across
their eligible date intervals. More importantly, it found date-overlapping
candidates for 284 of the 327 SEC identities that failed at Yahoo, an 86.9%
potential rescue rate. Public-inventory coverage was at least 83.18% from 2023
onward and 88.33% at the latest decision. These are candidates rather than
validated prices because the inventory lacks issuer names and permanent IDs.

The authenticated probe was implemented before requesting a credential. It
uses a transient `TIINGO_API_TOKEN` HTTP header, never includes the token in a
URL or artifact, hashes every response, stores adjusted/raw fields and actions,
compares provider and SEC issuer names, rejects recycled-ticker mismatches, and
is resumable. Each batch is capped at 24 symbols so its maximum 48 metadata and
price requests remain within Tiingo's documented 50-request hourly free tier.
Three focused issuer-name tests passed, and execution correctly refuses to run
without the transient token.

No external account was created and no provider terms were accepted on the
user's behalf. Strategy testing remains blocked until the user supplies a free
Tiingo API token and the first authenticated coverage batch passes.

References:

- `docs/FREE_DELISTED_PRICE_SOURCE_REVIEW.md`
- `config/tiingo_delisted_price_probe_v1.json`
- `src/systematic_trader/tiingo_delisted.py`
- `scripts/probe_tiingo_symbol_inventory_v1.py`
- `scripts/acquire_tiingo_delisted_probe_batch_v1.py`
- `tests/test_tiingo_delisted.py`
- `data/tiingo_symbol_inventory_vintages/20260813T102139Z-tiingo-supported-symbols-v1/manifest.json`
- `evidence/tiingo_delisted_coverage_probe_v1/result.json`
- `evidence/tiingo_delisted_coverage_probe_v1/report.md`

## Step 97 — Validate the first authenticated Tiingo delisted-price batch

The user supplied a Tiingo API token. It was passed only as a transient process
environment variable and an HTTP authorization header; it was excluded from
URLs, configuration, source manifests, response metadata, and project files.
The first batch deliberately stopped at 24 symbols, consuming at most 48
metadata and price requests under Tiingo's documented 50-request hourly free
limit.

All 24 initial requests returned metadata and price rows, materially
outperforming Yahoo for the same recovered-symbol problem. The first issuer
audit then caught a recycled ticker: old GAN Ltd was being matched to current
GARAN Inc. despite its prices beginning only in 2026. The name validator was
tightened to require a shared meaningful token, and the history gate now
requires prices at the first eligible SEC decision. A SolarWinds history that
began years after eligibility was also rejected. Focused tests for legal-name
suffix changes and both recycled-ticker examples passed.

After correction, 22 of 24 histories passed identity and start-date validation,
a 91.67% rate. Eight extended through the last SEC decision. Fourteen ended
before the 450-day SEC filing-staleness window, so the price end date was used
to shorten tradable membership rather than pretending the security remained
listed. Cached SEC Submissions records independently showed that every one of
those fourteen had an 8-K within five days of its final trade containing Items
2.01, 3.01, and 5.01—the joint signature of a completed acquisition, exchange
delisting, and change of control. Their declared provisional return rule is
liquidation at the final tradable close followed by cash.

No strategy was run. The next free-tier batches are now prioritized by the
number of affected decisions from 2023 onward. Only 123 candidate CIKs affect
that recent window, reducing the priority acquisition program to roughly six
hourly batches rather than downloading all 284 candidates first.

References:

- `src/systematic_trader/tiingo_delisted.py`
- `scripts/acquire_tiingo_delisted_probe_batch_v1.py`
- `scripts/audit_tiingo_delisted_probe_v1.py`
- `scripts/audit_tiingo_terminal_outcomes_v1.py`
- `tests/test_tiingo_delisted.py`
- `data/tiingo_delisted_price_probe_runs/20260813T104838Z-tiingo-delisted-probe-batch-v1.json`
- `evidence/tiingo_delisted_authenticated_probe_v1/result.json`
- `evidence/tiingo_delisted_authenticated_probe_v1/report.md`
- `evidence/tiingo_terminal_outcomes_v1/result.json`
- `evidence/tiingo_terminal_outcomes_v1/report.md`

## Step 98 — Run the second authenticated Tiingo priority batch

After the free-tier hourly window reset, the resumable collector skipped all
first-batch symbols and acquired the next 24 companies ranked by how many SEC
decisions they affect from 2023 onward. Twenty-three passed the strict issuer
and first-eligible-price gates. ARCH was rejected because Tiingo's returned
history began after the CIK's eligibility interval. No failed or recycled
ticker was substituted.

Across both batches, 45 of 48 histories now pass identity and start-date
validation, a 93.75% success rate. Thirty-five histories end before the SEC
filing-staleness window. Every one was independently classified as a completed
merger or acquisition from acceptance-dated SEC metadata: an 8-K containing
Items 2.01 and 3.01 plus either Item 5.01 or a nearby Form 25-NSE, all within
ten days of the final trade. PRFT and TWKS required the Form 25-NSE branch and
were not accepted until that evidence was found. The declared rule remains
liquidation at the final tradable close followed by cash.

There are 123 Tiingo rescue candidates affecting quarterly decisions from 2023
onward. The two completed batches validated 45 and rejected three; 75 remain
untested. The valid histories restore 594 of the 1,086 company-decision gaps in
that priority population, or 54.70%. The current batch consumed the hourly
allowance, so further acquisition was stopped instead of exceeding provider
limits. Strategy testing remains unauthorized until the remaining recent
batches and combined Yahoo/Tiingo panel audit are complete.

References:

- `data/tiingo_delisted_price_probe_runs/20260813T202424Z-tiingo-delisted-probe-batch-v1.json`
- `scripts/audit_tiingo_recent_rescue_progress_v1.py`
- `evidence/tiingo_delisted_authenticated_probe_v1/result.json`
- `evidence/tiingo_terminal_outcomes_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/report.md`

## Step 99 — Assemble the recent combined price panel during the rate-limit wait

The Tiingo reset interval was used to build the non-Tiingo half of the recent
panel. Point-in-time SEC membership identified 487 currently mapped CIKs that
appeared in a decision from 2023 onward. A pinned Yahoo batch acquisition
returned 486 histories; the single AGYS cache-lock failure was isolated and
succeeded on a one-symbol retry, producing 487 of 487 frozen current-company
histories.

The combined audit keys every source to CIK and applies explicit precedence:
identity-validated Tiingo overrides recycled/former-symbol uncertainty,
current SEC identities use the new Yahoo vintage, and only issuer-period-valid
recovered Yahoo histories may fill remaining gaps. SEC-confirmed acquisitions
terminate membership after the final trading date. Unresolved members remain
missing instead of being deleted or converted to cash.

With two Tiingo batches complete, the combined panel contains 487 current
Yahoo CIKs, 56 issuer-period-valid recovered Yahoo CIKs, and 45 validated
Tiingo CIKs. Decision-date coverage from 2023 onward is currently 82.79% at
the minimum, 90.70% at the median, and 98.34% at the latest decision. The
remaining Tiingo candidates can theoretically raise every decision to at
least 95.73% and the latest to 98.75%, so completing them can satisfy the
predeclared 95% gate.

Three current mappings—DBD, WOLF, and NINE—were correctly flagged because
their Yahoo histories begin only after bankruptcy/restructuring gaps. Tiingo's
public inventory has no older DBD interval, has separate old/new WOLF records,
and has continuous NINE history. These are treated as identity-resolution
cases rather than normal current tickers.

Seventy-five original recent-priority candidates remain untested; including
the three reorganization cases yields 78 investigations, which still fit into
four free-tier batches of 24, 24, 24, and 6. No strategy test was run.

References:

- `scripts/acquire_yahoo_recent_current_sec_prices_v1.py`
- `scripts/audit_combined_recent_price_panel_v1.py`
- `data/yahoo_recent_current_sec_price_vintages/20260813T205326Z-yahoo-recent-current-sec-v1/manifest.json`
- `data/yahoo_recent_current_sec_price_vintages/20260813T205441Z-yahoo-recent-current-sec-agys-retry-v1/manifest.json`
- `evidence/combined_recent_price_panel_v1/result.json`
- `evidence/combined_recent_price_panel_v1/report.md`

## Step 100 — Run the third Tiingo priority batch and reassess weekly trading

After the hourly free-tier window reset, the resumable collector acquired the
next 24 recent-priority Tiingo histories. Twenty-one passed the issuer-name and
first-eligible-price gates. DO and SBOW were rejected because their returned
histories did not cover the beginning of the SEC eligibility interval. PCTI
was rejected as a name mismatch or recycled ticker. No rejected identity was
silently substituted.

Across three batches, 66 of 72 histories now pass strict validation, a 91.67%
rate. The accepted histories rescue 798 of 1,086 recent company-decision gaps,
or 73.48%. Fifty-one of the 123 original recent-priority CIKs remain. The
combined panel now contains 609 unique CIKs with a price source; minimum recent
decision coverage increased to 85.63%, median coverage to 94.05%, and latest
coverage to 98.54%. The predeclared 95% minimum-at-every-decision gate is not
yet met, so strategy testing remains unauthorized.

The terminal audit now covers 55 early-ending validated histories. Fifty-two
have SEC-supported terminal reasons and provisional liquidation-at-final-close
treatment; three still require resolution or adverse missing-company
sensitivity.

The frozen 60/40 return-first candidate was also checked for its actual trading
schedule. It has 1,127 weekly decision observations but only 232 target-weight
changes. Apart from the initial row, all 231 changes occurred on the fourth or
fifth Friday of a month, averaging one change per 4.87 weeks. It is therefore
weekly observed but effectively monthly traded. Earlier GGG execution evidence
found that biweekly execution damaged returns while monthly execution modestly
improved them, but that result does not answer whether the distinct Batch 66/67
return-first signals would benefit from genuine weekly recomputation. A fair
weekly challenger must recompute the source rankings every week, charge 50,
100, and 200-bps turnover costs, and compare untouched/past-only windows; merely
repeating unchanged monthly targets each Friday would not constitute a new
strategy.

References:

- `data/tiingo_delisted_price_probe_runs/20260814T010059Z-tiingo-delisted-probe-batch-v1.json`
- `evidence/tiingo_delisted_authenticated_probe_v1/result.json`
- `evidence/tiingo_terminal_outcomes_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/result.json`
- `evidence/combined_recent_price_panel_v1/result.json`
- `evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv`

## Step 102 — Run the fourth Tiingo priority batch and rebuild coverage audits

After the next free-tier reset, the resumable collector processed 24 more
priority symbol records. Twenty-one symbol histories passed the issuer-name
and first-eligible-price gates, two were rejected because their histories
began after the required eligibility date, and one was rejected for an issuer
name mismatch or ticker reuse. Because several symbol records resolve to an
already-investigated CIK, this batch added 13 distinct recent-priority company
investigations: 11 valid CIKs and two rejected CIKs.

Across all four batches, 85 distinct recent-priority CIKs have now been
audited. Seventy-seven are valid and eight are rejected, leaving 38 of the 123
recent-priority CIKs. The validated histories now rescue 878 of 1,086 missing
company-decision rows, or 80.85%, up from 73.48% after batch three.

The combined Yahoo/Tiingo panel now has a usable price source for 620 of 636
unique CIKs. Coverage across the 14 decisions from 2023 onward improved to
87.45% at the weakest decision, 95.49% at the median decision, and 98.54% at
the latest decision. Crossing 95% at the median is useful, but the declared
gate requires at least 95% at every recent decision, so strategy testing is
still unauthorized.

Sixty-six accepted histories end before the SEC filing-staleness window.
Sixty-three now have SEC-supported terminal reasons and provisional terminal
returns. The final evaluation must still include both liquidation at the last
observed close followed by cash and an adverse -100% treatment for every
unresolved early delisting.

References:

- `data/tiingo_delisted_price_probe_runs/20260814T021814Z-tiingo-delisted-probe-batch-v1.json`
- `evidence/tiingo_delisted_authenticated_probe_v1/result.json`
- `evidence/tiingo_terminal_outcomes_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/result.json`
- `evidence/combined_recent_price_panel_v1/result.json`

## Step 103 — Run the fifth Tiingo priority batch and close most recent gaps

After the next free-tier reset, the resumable collector processed another 24
priority symbol records. Twenty-two histories passed issuer-identity and
first-eligible-price validation. WLL and MCFE were rejected because their
returned histories began after the required eligibility date. No rejected
history was substituted or treated as valid.

The contemporaneous distinct-company snapshot showed 21 added investigations:
20 valid CIKs and one rejected CIK after aliases and already-investigated
identities were deduplicated. It reported 106 audited candidates, 97 valid
recent-priority CIKs, and 17 recent-priority CIKs remaining. The collector was
later found to have still been finishing cache writes when the first audit
started, so these are explicitly a provisional checkpoint. Step 104 performs
the completed-cache reconciliation and supersedes these CIK-level totals.

The accepted histories now rescue 963 of 1,086 missing recent
company-decision rows, or 88.67%, up from 80.85% after batch four. The combined
panel's weakest decision improved from 87.45% to 90.64%. Median coverage is
95.49% and latest-decision coverage is 98.54%. The weakest decision remains
below the predeclared 95% requirement, so strategy testing is still
unauthorized.

Eighty-six validated histories end before the SEC filing-staleness window.
Seventy-eight have SEC-supported terminal reasons and provisional terminal
returns. The remaining eight require explicit adverse sensitivity; the final
evaluation must compare liquidation at the last observed close followed by
cash against a -100% terminal return for every unresolved early delisting.

References:

- `data/tiingo_delisted_price_probe_runs/20260814T040305Z-tiingo-delisted-probe-batch-v1.json`
- `evidence/tiingo_delisted_authenticated_probe_v1/result.json`
- `evidence/tiingo_terminal_outcomes_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/result.json`
- `evidence/combined_recent_price_panel_v1/result.json`

## Step 104 — Run batch six and reconcile the complete authenticated cache

After the free-tier window reset, the collector processed 24 additional
symbol records and was allowed to exit fully before any result was accepted.
Twenty-three histories passed issuer-identity and first-eligible-price
validation. WORK was rejected as an issuer-name mismatch or recycled ticker.
The access token was supplied only to the running container and was not
persisted.

The completed-cache audit also incorporated the final cache writes that the
provisional Step 103 snapshot missed. The authoritative cumulative result is
therefore 144 distinct CIKs audited, 132 valid and 12 rejected. Within the 123
recent-priority CIKs, 111 are valid, 11 are rejected, and only one remains
untested: Aspen Technology (CIK 0000929940, symbol AZPN).

Validated Tiingo histories now restore 989 of the 1,086 recent
company-decision gaps, or 91.07%. Combined-panel coverage is 92.58% at the
weakest decision, 95.49% at the median decision, and 98.75% at the latest
decision. The last AZPN retry can close part of the remaining gap but cannot by
itself guarantee 95% observed coverage at every date, so the next stage must
finish AZPN and then explicitly resolve or adversely stress the rejected and
otherwise missing companies.

Of 118 valid histories that end before the SEC filing-staleness window, 107
now have SEC-supported terminal reasons and provisional terminal returns.
Eleven remain unresolved and must receive the declared -100% terminal-return
sensitivity alongside the base liquidation-at-final-close treatment. Strategy
testing remains unauthorized until the final priority retry and missing-company
gate are completed.

References:

- `data/tiingo_delisted_price_probe_runs/20260814T055851Z-tiingo-delisted-probe-batch-v1.json`
- `evidence/tiingo_delisted_authenticated_probe_v1/result.json`
- `evidence/tiingo_terminal_outcomes_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/result.json`
- `evidence/combined_recent_price_panel_v1/result.json`

## Step 105 — Resolve the final shared ticker and authorize research testing

The final recent-priority identity was not an ordinary failed download. AZPN
was shared by the former Aspen Technology CIK 0000929940 and its post-2022
successor CIK 0001897982. The collector previously treated a completed symbol
as a completed company, so the successor cache blocked the former issuer. The
collector now resumes by CIK and creates a separate identity-keyed cache entry
when the same ticker belongs to another SEC identity. Pure shared-ticker checks
were added before acquisition.

The former Aspen Technology interval then passed issuer-name and start-date
validation. All 123 recent-priority CIKs are now resolved: 112 are valid and
11 are explicitly rejected. The validated histories restore 992 of 1,086
priority company-decision gaps, or 91.34%. The transient Tiingo token was not
persisted.

The terminal audit was also corrected for stale provider tails. A qualifying
SEC completion may precede the provider's final repeated price by several
months, so the audit now searches the preceding year for an 8-K containing
Items 2.01 and 3.01 plus Item 5.01 or a nearby Form 25-NSE, then truncates the
tradable series at the completion filing. This resolved all 118 early-ending
validated histories with SEC evidence; none remains unknown.

A general terminal-membership audit then applied the same strict rule across
947 historical membership CIKs and required no later 10-K, 10-Q, 20-F, or
40-F. It found 331 SEC-confirmed issuer terminations. Combined with the
price-linked terminal evidence, 332 CIKs are removed only after confirmed
termination rather than remaining as stale tradable members.

The rebuilt panel now passes the predeclared observed-data gate at every recent
decision: minimum coverage is 95.06%, median coverage is 96.34%, and latest
coverage is 99.57%. All 230 residual missing company-decision rows have an
explicit paired policy. If a missing company is selected, its intended weight
stays in cash for the base scenario and receives a -100% holding-period return
in the adverse scenario. Missing weight may not be redistributed into known
survivors.

Research strategy testing is therefore authorized only when both base and
adverse missing-company scenarios are run. Live trading remains disabled, and
no new strategy result was produced in this step.

References:

- `data/tiingo_delisted_price_probe_runs/20260814T070731Z-tiingo-delisted-probe-batch-v1.json`
- `data/tiingo_delisted_price_probe_cache_v1/AZPN__0000929940/result.json`
- `scripts/acquire_tiingo_delisted_probe_batch_v1.py`
- `scripts/audit_tiingo_terminal_outcomes_v1.py`
- `scripts/audit_sec_terminal_membership_v1.py`
- `scripts/audit_missing_company_adverse_gate_v1.py`
- `config/missing_company_adverse_gate_v1.json`
- `evidence/sec_terminal_membership_v1/result.json`
- `evidence/tiingo_recent_rescue_progress_v1/result.json`
- `evidence/combined_recent_price_panel_v1/result.json`
- `evidence/missing_company_adverse_gate_v1/result.json`

## Step 106 — Retest the frozen SEC growth strategy on the survivorship-aware panel

The previously frozen SEC growth-factor rule was reconstructed without changing
its features, sector-neutral ranking, top-five selection, equal weighting, or
quarterly decision schedule. Company Facts were acquired successfully for all
598 recent tradable CIKs, and the factor used only filings available strictly
before each decision. Fourteen quarterly decisions from January 2023 onward
were tested with weekly mark-to-market accounting, 50/100/200-bps one-way cost
assumptions, and the required base/adverse treatment for missing companies.

All validation checks passed: filing availability, deterministic choices,
prefix invariance, five selections per decision, weights summing to one, cost
monotonicity, and execution of both missing-company scenarios. At 50 bps, the
base case produced 31.70% full-period CAGR, 0.948 Sharpe, and -36.50% maximum
drawdown. The adverse case produced 16.69% CAGR, 0.597 Sharpe, and -45.60%
maximum drawdown. SPY produced 22.32% CAGR, while XLK produced 36.59% with a
1.467 Sharpe and -24.02% drawdown. The base case therefore beats SPY on return
but not risk-adjusted performance, trails XLK, and does not survive the adverse
comparison strongly enough to authorize replacement.

Recent returns were much stronger: at 50 bps, trailing one-year CAGR was
142.22%, Sharpe was 2.332, and maximum drawdown was -23.44%; trailing two-year
CAGR was 71.08%. At 200 bps, trailing one-year CAGR remained 136.29%, while
full-period base CAGR declined to 26.80% and adverse CAGR to 12.17%. These
figures are not treated as expected future returns.

The concentration audit found that Micron returned 159.39% during the latest
holding period and supplied 67.63% of the portfolio's positive arithmetic
return. Holding Micron's 20% weight in cash would have reduced the latest
five-position arithmetic return from 47.13% to 15.25%. This makes the recent
result promising but fragile rather than broadly proven.

The only selected company without validated prices was Meta Materials (CIK
0001431959, MMAT), selected in January and April 2023. SEC evidence confirms
MMAT as its contemporaneous symbol, while neither MMAT nor legacy TRCH appears
in the downloaded Tiingo inventory. The base case therefore leaves its 20%
weight in cash; the adverse case assigns that intended weight a total loss.
Both scenarios are identical from August 2023 onward, where survivorship-aware
base CAGR was 37.24% versus 36.14% in the old current-survivor pilot. The old
pilot is not considered valid proof.

The strategy is retained only as a separate fundamental-sleeve research
candidate. It does not replace the 41.66% ETF incumbent, and live trading stays
disabled.

References:

- `config/sec_growth_survivorship_retest_v1.json`
- `data/sec_recent_companyfacts_runs/20260814T075518Z-sec-recent-companyfacts-v1.json`
- `scripts/acquire_sec_recent_companyfacts_v1.py`
- `scripts/run_sec_growth_survivorship_retest_v1.py`
- `scripts/audit_sec_growth_recent_concentration_v1.py`
- `evidence/sec_growth_survivorship_retest_v1/result.json`
- `evidence/sec_growth_survivorship_retest_v1/performance.csv`
- `evidence/sec_growth_survivorship_retest_v1/cost_scenario_stress_summary.csv`
- `evidence/sec_growth_survivorship_retest_v1/recent_concentration_summary.json`
- `evidence/sec_growth_survivorship_retest_v1/report.md`

## Step 107 — Preserve the 142% candidate and test it as a controlled sleeve

The survivorship-aware SEC growth strategy was saved as a named, formula-frozen
research candidate so its exceptional 142.22% trailing-one-year simulated CAGR
cannot be silently discarded or altered. Its registry card also preserves the
2.332 Sharpe, -23.44% drawdown, full-period base/adverse results, exact factor
definition, and the warning that Micron supplied 67.63% of the latest holding
period's positive arithmetic return.

The unchanged growth strategy was then combined with the frozen 41.66% monthly
ETF incumbent at predeclared 0%, 5%, 10%, 15%, 20%, 25%, 30%, and 40% capital
allocations. Both buy-and-drift and quarterly target-reset capital management
were tested at 50/100/200-bps costs under the base and adverse missing-company
scenarios. All allocations were reported; none was selected by optimizing the
already-observed outcomes. Five validation checks passed, including exact
zero-allocation equivalence to the incumbent.

At 50 bps from the incumbent holdout start, quarterly-reset allocations of 10%,
20%, and 30% produced 41.85%, 41.92%, and 41.88% CAGR versus 41.66% for the
incumbent. Sharpe declined from 1.710 to 1.700, 1.658, and 1.592, while maximum
drawdown worsened from -15.83% to -16.89%, -19.17%, and -21.43%. The standalone
growth strategy's enormous recent return therefore added little across the
complete comparable holdout.

The trailing-one-year comparison was materially stronger: the incumbent's
68.75% CAGR rose to 76.05%, 83.38%, and 90.74% at 10%, 20%, and 30% sleeve
allocations. Their drawdowns were -13.87%, -11.91%, and -12.20%. At 200-bps
costs, the same allocations still produced 67.61%, 74.99%, and 82.45% trailing
one-year CAGR. These results are historically concentrated and are not expected
returns.

The full-period adverse case rejected immediate retrospective promotion. CAGR
declined from 41.80% for the incumbent alone to 39.78%, 37.64%, and 35.38% at
10%, 20%, and 30%. Rather than choose a weight from contaminated outcomes, a
parallel 52-week forward ladder was frozen for all three predeclared controlled
allocations. The first eligible realization is August 21, 2026. Status is 0/52
weeks; live trading remains disabled.

References:

- `research_registry/sec_growth_survivorship_candidate_v1.json`
- `config/sec_growth_incumbent_sleeve_blend_v1.json`
- `config/forward/sec_growth_incumbent_sleeve_ladder_v1.json`
- `scripts/run_sec_growth_incumbent_sleeve_blend_v1.py`
- `evidence/sec_growth_incumbent_sleeve_blend_v1/result.json`
- `evidence/sec_growth_incumbent_sleeve_blend_v1/performance.csv`
- `evidence/sec_growth_incumbent_sleeve_blend_v1/controlled_sleeve_focus.csv`
- `evidence/sec_growth_incumbent_sleeve_blend_v1/forward_status.json`
- `evidence/sec_growth_incumbent_sleeve_blend_v1/report.md`

## Step 108 — Add stock-level drift caps to the controlled growth sleeve

The prior capital-sleeve test limited the fundamental strategy's starting
allocation but did not directly constrain an exceptional winner between its
quarterly rebalances. A stock-level wrapper therefore retained the exact frozen
SEC growth selections and tested monthly caps at 1.00x, 1.25x, and 1.50x each
stock's initial equal share of the total portfolio. Excess was transferred to
the frozen ETF incumbent rather than redistributed among the other selected
stocks. Uncapped controls, 10/20/30% sleeve allocations, 50/100/200-bps costs,
and base/adverse missing-company scenarios were all retained.

Five validation checks passed. Every predeclared cap and allocation was
reported, both missing-company scenarios ran, all numeric outputs were finite,
and no cap increased peak single-stock weight relative to its uncapped control.
The fundamental ranking and quarterly selections were not changed.

For the 20% sleeve at 50 bps, the strict 1.00x cap reduced full-holdout peak
single-stock weight from 9.12% to 6.45%. CAGR changed only from 41.94% to
41.88%, Sharpe improved from 1.658 to 1.672, maximum drawdown improved from
-19.19% to -18.70%, and cap-specific annual one-way turnover was 0.09x. At 100
and 200 bps, strict-cap holdout CAGRs were 39.43% and 34.64%, versus uncapped
39.58% and 34.97%.

In the trailing year, strict caps reduced peak single-stock weights to 3.03%,
6.04%, and 9.03% for the 10%, 20%, and 30% sleeves. Their 50-bps CAGRs were
74.67%, 80.63%, and 86.69%, compared with uncapped 76.09%, 83.45%, and 90.83%.
The 20% strict-cap version retained 72.07% trailing-one-year CAGR even at the
severe 200-bps cost assumption. These remain historical simulations rather
than forecasts.

The strict cap is carried forward because it directly implements the stated
concentration-control objective, not because it was the best retrospective
point. A new 52-week parallel protocol freezes strict-cap 10/20/30% allocations
and their uncapped comparators before the first eligible realization on August
21, 2026. Status is 0/52 weeks and live trading remains disabled.

References:

- `config/sec_growth_stock_drift_cap_v1.json`
- `config/forward/sec_growth_capped_sleeve_ladder_v1.json`
- `scripts/run_sec_growth_stock_drift_cap_v1.py`
- `evidence/sec_growth_stock_drift_cap_v1/result.json`
- `evidence/sec_growth_stock_drift_cap_v1/performance.csv`
- `evidence/sec_growth_stock_drift_cap_v1/primary_comparison.csv`
- `evidence/sec_growth_stock_drift_cap_v1/events.csv`
- `evidence/sec_growth_stock_drift_cap_v1/current_target_allocations.csv`
- `evidence/sec_growth_stock_drift_cap_v1/forward_status.json`
- `evidence/sec_growth_stock_drift_cap_v1/report.md`

## Step 109 — Test a Micron-only cap ladder

The 20% controlled growth sleeve was held fixed, every non-Micron stock retained
the strict 1.00x monthly drift cap, and only Micron's cap was varied across
1.00x, 1.50x, 2.00x, 2.50x, 3.00x, and uncapped. Base/adverse missing-company
cases and 50/100/200-bps costs were retained. All validation checks passed.

At 50 bps, raising the Micron cap from 1.00x to 1.50x increased trailing-one-year
CAGR from 80.63% to 81.91%; 2.00x reached 82.08%. The holdout CAGR increased
from 41.88% to 42.26%, while the largest observed Micron weight rose from 6.04%
to 9.14%. Drawdown was nearly unchanged. Caps above 2.00x produced exactly the
same path as 2.00x and uncapped because Micron never grew enough to bind those
higher limits. This is a small improvement with a clear concentration cost, not
a new 142% result.

References:

- `config/sec_growth_mu_cap_sensitivity_v1.json`
- `scripts/run_sec_growth_mu_cap_sensitivity_v1.py`
- `evidence/sec_growth_mu_cap_sensitivity_v1/performance.csv`
- `evidence/sec_growth_mu_cap_sensitivity_v1/primary_comparison.csv`
- `evidence/sec_growth_mu_cap_sensitivity_v1/report.md`
- `config/forward/sec_growth_mu_cap_amendment_v1.json`

## Step 110 — Add causal confidence sizing to the growth sleeve

Six predeclared rules tested whether the frozen growth sleeve should receive
more capital only when its own prior relative trend confirmed. Every signal
shifted realized weekly returns before computing its rolling window, prefix
invariance passed, weekly target-reset turnover was charged, and base/adverse
cases were tested at 50/100/200 bps.

The strongest recent-return challenger used a 10% normal allocation and 40%
when the growth sleeve's prior 26-week return was positive and exceeded the ETF
incumbent. At 50 bps it produced 92.56% trailing-one-year CAGR, 2.435 Sharpe,
and -13.49% maximum drawdown, versus 82.83%, 2.395, and -11.99% for the fixed
20% control. YTD CAGR rose from 71.09% to 88.72%. The recent result survived
100- and 200-bps costs at 89.15% and 82.51% trailing-one-year CAGR.

It did not dominate over the whole holdout: CAGR declined from 41.90% to
41.14%, Sharpe declined from 1.661 to 1.587, and annual allocation turnover rose
from 0.27x to 1.49x. It is therefore saved as a provisional return-first
challenger and frozen for 52 weeks of forward observation, not promoted over
the incumbent.

References:

- `config/sec_growth_confidence_sizing_v1.json`
- `scripts/run_sec_growth_confidence_sizing_v1.py`
- `evidence/sec_growth_confidence_sizing_v1/performance.csv`
- `evidence/sec_growth_confidence_sizing_v1/primary_comparison.csv`
- `evidence/sec_growth_confidence_sizing_v1/report.md`
- `research_registry/sec_growth_confidence_sizing_candidate_v1.json`
- `config/forward/sec_growth_confidence_sizing_challenger_v1.json`

## Step 111 — Combine confidence sizing with ticker-agnostic caps

The causal 10%-or-40% growth allocation was combined with monthly stock caps at
1.00x, 1.50x, 2.00x, and uncapped. The cap implementation contains no ticker
exceptions: every available fundamental holding is compared with the same
multiple of its current equal-weight share, and excess moves to the frozen ETF
incumbent. Historical cap events included NVDA and MU, confirming that this is
not a Micron-specific wrapper.

All validation checks passed, including prefix invariance, cost monotonicity,
base/adverse execution, finite results, cost-invariant signals, and the rule
that a cap cannot increase peak stock weight. At 50 bps the 1.50x version
produced 92.31% trailing-one-year CAGR, 2.433 Sharpe, and -13.44% drawdown. It
retained all but 0.26 percentage points of the uncapped 92.57% CAGR, while
reducing peak single-stock weight from 15.59% to 14.78%. YTD CAGR was 88.31%.

The strict 1.00x cap reduced recent CAGR more substantially to 88.85%. The
2.00x path was identical to uncapped because no holding reached that threshold
on a review date. The 1.50x version was therefore preserved as the balanced
provisional challenger, not promoted: its full-holdout CAGR was 38.71% versus
41.52% for the fixed 20% strict-cap control, and severe 200-bps costs materially
worsened the older-window drawdown. A 52-week forward protocol begins with the
August 21, 2026 realization.

References:

- `config/sec_growth_confidence_universal_cap_v1.json`
- `scripts/run_sec_growth_confidence_universal_cap_v1.py`
- `evidence/sec_growth_confidence_universal_cap_v1/performance.csv`
- `evidence/sec_growth_confidence_universal_cap_v1/primary_comparison.csv`
- `evidence/sec_growth_confidence_universal_cap_v1/cap_events.csv`
- `evidence/sec_growth_confidence_universal_cap_v1/report.md`
- `research_registry/sec_growth_confidence_universal_cap_candidate_v1.json`
- `config/forward/sec_growth_confidence_universal_cap_challenger_v1.json`

## Step 112 — Add an exceptional-confidence tier and test cap frequency

The binary 10%-or-40% growth allocation was extended with predeclared 50% and
60% exceptional tiers. Exceptional confidence required the 26-week relative
trend gate, positive 13-week sleeve momentum, at least three positive current
holdings, no single positive holding contributing more than 60% of summed
positive holding momentum, and a 13-week/52-week volatility ratio no greater
than 1.5. Monthly, biweekly, weekly, and monthly-plus-emergency universal cap
schedules were crossed with six signal variants at 50/100/200-bps costs and in
base/adverse scenarios.

All validation checks passed. The prior 10/40 monthly 1.50x control reproduced
to `5.6e-17` maximum CAGR difference, prefix invariance and cost monotonicity
passed, all predeclared variants were reported, and no ticker-specific cap logic
was introduced.

The return leader was the breadth-three, 60%-contribution-limit, 60%-allocation
variant with a weekly universal 1.50x cap. At 50 bps it produced 110.49%
trailing-one-year CAGR, 2.564 Sharpe, and -14.07% drawdown versus 92.31%, 2.433,
and -13.44% for the binary control. YTD CAGR was 109.06%, two-year CAGR was
62.44%, and holdout CAGR improved from 38.71% to 41.85%. The weekly cap reduced
peak recent single-stock weight to 20.36% versus 22.00% with monthly review,
while sacrificing only 0.002 percentage points of trailing-one-year CAGR.

The result survived cost stress: trailing-one-year CAGR was 105.40% at 100 bps
and 95.58% at 200 bps. However, turnover reached 3.17x capital annually, the
holdout drawdown worsened to -21.80%, and a paired block bootstrap placed the
holdout annualized return-difference lower bound near -0.9 percentage points.
Only 43.94% of rolling 26-week holdout windows beat the control, compared with
100% in the latest year. The strategy is therefore a provisional return-first
leader, not a promoted replacement. Both 50% and 60% exceptional tiers were
frozen for 52 weeks of forward comparison.

References:

- `config/sec_growth_three_tier_cap_frequency_v1.json`
- `scripts/run_sec_growth_three_tier_cap_frequency_v1.py`
- `scripts/audit_sec_growth_three_tier_leader_v1.py`
- `evidence/sec_growth_three_tier_cap_frequency_v1/performance.csv`
- `evidence/sec_growth_three_tier_cap_frequency_v1/primary_comparison.csv`
- `evidence/sec_growth_three_tier_cap_frequency_v1/leader_robustness.json`
- `evidence/sec_growth_three_tier_cap_frequency_v1/report.md`
- `research_registry/sec_growth_three_tier_return_leader_v1.json`
- `config/forward/sec_growth_three_tier_challenger_v1.json`

## Step 113 — Falsify the 110% three-tier leader

The frozen 10/40/60 weekly-cap leader was subjected to the predeclared
falsification gauntlet without changing its formula. Every historically
selected stock was excluded once with its capital transferred to the ETF
incumbent; allocation signals were delayed one and two weeks; quarterly stock
selection was delayed one week; 162 neighboring parameter combinations were
run; 300/500-bps costs were applied; and market direction, volatility, and
technology-versus-energy leadership regimes were decomposed.

The implementation passed every validation check and reproduced the frozen
leader and control. The candidate nevertheless failed two promotion gates.
Removing Micron reduced trailing-one-year CAGR from 110.49% to 75.23%, below
the 92.31% binary control. Removing VIAV reduced it to 87.78%. The balanced 50%
exceptional tier was not a cure: excluding Micron reduced its 101.35% CAGR to
70.74%. A single stock therefore destroyed more than the entire claimed
improvement in both versions.

Only 33.33% of the 162 parameter-neighborhood configurations improved both
trailing-one-year and holdout CAGR, versus the required 70%. The successful
neighborhood was concentrated around the selected 26-week lookback; the 20-
and 32-week alternatives did not form a broad plateau. This is further evidence
that the retrospective 110% point is too selection-sensitive for promotion.

Timing robustness did pass. A one-week allocation delay retained 99.19%
trailing-one-year CAGR and improved holdout CAGR to 44.06%; a one-week stock-
selection delay retained 105.64%. A two-week allocation delay fell to 89.50%.
At 300 and 500 bps the leader retained 86.20% and 68.71% recent CAGR, but its
holdout CAGR fell to 22.95% and 9.55%, with -35.28% and -46.25% drawdowns.

Descriptive regime averages were positive versus the control in every tested
state, but this did not overcome the direct stock-exclusion failure. The 110%
candidate is retained only as a falsification-failed forward shadow. It is not
eligible to replace the 10/40 universal-cap candidate or authorize trading.

References:

- `config/sec_growth_three_tier_falsification_v1.json`
- `scripts/run_sec_growth_three_tier_falsification_v1.py`
- `evidence/sec_growth_three_tier_falsification_v1/result.json`
- `evidence/sec_growth_three_tier_falsification_v1/leave_one_stock_out.csv`
- `evidence/sec_growth_three_tier_falsification_v1/parameter_neighborhood.csv`
- `evidence/sec_growth_three_tier_falsification_v1/delay_stress.csv`
- `evidence/sec_growth_three_tier_falsification_v1/extreme_costs.csv`
- `evidence/sec_growth_three_tier_falsification_v1/regime_decomposition.csv`
- `evidence/sec_growth_three_tier_falsification_v1/report.md`

## Step 114 — Discover and confirm an independent SEC cash-conversion sleeve

Five non-growth fundamental families were frozen before their survivorship-aware
outcomes were inspected: profitability, balance-sheet quality, shareholder
discipline, cash conversion, and quality acceleration. Each used SEC facts
accepted strictly before fourteen quarterly decisions, sector-neutral ranks, a
fixed top-ten equal-weight portfolio, weekly mark-to-market accounting, paired
base/adverse missing-company policies, and 50/100/200-bps costs. All 598 recent
tradable CIKs were reconstructed from the frozen Company Facts cache. Valuation
was deliberately excluded because multiplying retrospectively split-adjusted
prices by filing-date share counts would not produce a corporate-action-consistent
point-in-time market capitalization.

Balance-sheet quality had the highest trailing-one-year CAGR at 72.65%, but cash
conversion was the stronger independent profile. At 50 bps it produced 64.83%
trailing-one-year CAGR, 1.901 Sharpe, and -14.43% maximum drawdown; YTD CAGR was
95.54%. Its full-recent CAGR was 23.73% with 0.970 Sharpe and -33.10% drawdown.
Weekly correlation was 0.498 to the SEC growth sleeve and 0.594 to SPY. The
adverse missing-company full-period CAGR remained 23.73%. All filing-availability,
determinism, fixed-breadth, weight-sum, and paired-scenario checks passed.

A leave-one-company-out test replaced every occurrence of each excluded company
with cash without redistributing its weight. Across the 26 companies active in
the trailing year, the largest CAGR effect was 14.08 percentage points from Palo
Alto Networks. This is meaningfully broader than the rejected Micron-led result,
although it is not concentration-free.

The frozen cash-conversion sleeve was then added at 0%, 5%, 10%, 15%, and 20%
to the 10%-or-40% growth leader with the universal 1.5x stock cap. Static blends
did not improve the return-first objective. At 50 bps, the leader retained
92.31% trailing-one-year CAGR, 2.433 Sharpe, and -13.44% drawdown. A 10% sleeve
reduced CAGR to 89.70% while improving Sharpe to 2.534 and drawdown to -11.98%;
a 20% sleeve reduced CAGR to 87.06% while improving drawdown to -10.56% and
Sharpe to 2.625. The cash-conversion rule is therefore preserved as an optional
diversification/defensive research sleeve, but the static blend is rejected as
a replacement for the return-first leader. Live trading remains disabled.

References:

- `config/sec_independent_fundamental_discovery_v1.json`
- `scripts/run_sec_independent_fundamental_discovery_v1.py`
- `evidence/sec_independent_fundamental_discovery_v1/result.json`
- `evidence/sec_independent_fundamental_discovery_v1/primary_focus.csv`
- `config/sec_cash_conversion_confirmation_blend_v1.json`
- `scripts/run_sec_cash_conversion_confirmation_blend_v1.py`
- `evidence/sec_cash_conversion_confirmation_blend_v1/result.json`
- `evidence/sec_cash_conversion_confirmation_blend_v1/primary_comparison.csv`
- `evidence/sec_cash_conversion_confirmation_blend_v1/leave_one_company_out.csv`
- `research_registry/sec_cash_conversion_candidate_v1.json`

## Step 115 — Run the large independent-overlay search and find a broader return leader

The 92.31% 10/40 universal-cap strategy was frozen as the control. A causal
multi-branch batch then tested conditional cash-conversion allocations,
return-ranked and Sharpe-ranked rotations across all five SEC factor families,
top-two factor ensembles, 8/10/11/12/13/14/15/16/18/20/22/26/39-week signal
windows, 0%-50% allocations, monthly ticker-agnostic caps, and 10/15/20/30-stock
breadths. Signals used only shifted prior weekly returns. Base/adverse missing-
company cases and 50/100/200-bps costs were retained. More than 300 explicitly
reported configurations were evaluated. Factor rotation and top-two ensembles
did not beat the control; the best rotation produced only 90.56% trailing-year
CAGR.

The raw top-ten cash-conversion point reached 107.53% trailing-one-year CAGR,
2.709 Sharpe, and -10.67% drawdown. It was rejected as the preferred version
because removing Palo Alto Networks reduced CAGR to 91.21%, below the control.
A strict monthly cap retained 105.84% but merely shifted the worst exclusion to
Varonis at 90.06%. Expanding breadth was therefore tested rather than changing
a ticker-specific rule.

The breadth-20, uncapped, 11-week, 0%-or-50% version was the strongest broader
candidate. At 50 bps it produced 105.10% trailing-one-year CAGR, 2.692 Sharpe,
and -10.08% maximum drawdown versus 92.31%, 2.433, and -13.44% for the control.
YTD CAGR was 109.50%, trailing-two-year CAGR was 59.70%, trailing-three-year
CAGR was 41.45%, and full-period CAGR was 40.93% versus 38.59% for the control.
Trailing-one-year CAGR remained 101.06% at 100 bps and 93.20% at 200 bps. The
adverse 50-bps full-period CAGR was 37.45% versus 37.04% for the adverse control.

The final falsification audit passed every declared check. Removing each recent
holding individually left the worst result, GitLab, at 96.50% CAGR. One- and
two-week signal delays retained 98.13% and 102.72%. Four- and thirteen-week
block bootstraps assigned 99.62% and 99.38% probability to a positive recent
annualized difference, though their fifth-percentile lower bounds were
effectively zero. Prefix invariance passed. Across 48 breadth/cap/lookback/
allocation neighbors, 91.67% beat the control recently and 50% improved both
recent and full-period CAGR. The modeled peak target weight of one added stock
was 4.61% of the total portfolio.

This becomes the new provisional return-first research leader, not an approved
live strategy. It was found after a large retrospective search, only 42.02% of
rolling 26-week windows beat the control, and full-period cross-sleeve turnover
was 3.22x annually before including already-charged internal sleeve turnover.
A formula-frozen 52-week forward protocol begins with the August 21, 2026
weekly realization. The current research signal is active: 50% remains in the
prior leader and 50% is assigned equally across the 20 cash-conversion names.

References:

- `config/sec_independent_dynamic_overlay_batch_v1.json`
- `config/sec_cash_conversion_return_surface_v1.json`
- `scripts/run_sec_independent_dynamic_overlay_batch_v1.py`
- `evidence/sec_cash_conversion_return_surface_v1/result.json`
- `config/sec_cash_conversion_capped_dynamic_v1.json`
- `scripts/run_sec_cash_conversion_capped_dynamic_v1.py`
- `config/sec_cash_conversion_breadth_dynamic_v1.json`
- `scripts/run_sec_cash_conversion_breadth_dynamic_v1.py`
- `evidence/sec_cash_conversion_breadth_dynamic_v1/performance.csv`
- `scripts/audit_sec_cash_conversion_breadth20_candidate_v1.py`
- `evidence/sec_cash_conversion_breadth20_candidate_audit_v1/result.json`
- `evidence/sec_cash_conversion_breadth20_candidate_audit_v1/report.md`
- `research_registry/sec_cash_conversion_breadth20_candidate_v1.json`
- `config/forward/sec_cash_conversion_breadth20_challenger_v1.json`

## Step 116 — Reconstruct the leader on exact daily closes

The frozen breadth-20 formula was rebuilt as a hierarchical daily-close
simulation rather than inferred from weekly endpoints. The reconstruction
preserved the ETF incumbent, quarterly growth selections, weekly 10%-or-40%
growth allocation, monthly universal 1.5x cap, quarterly 20-stock
cash-conversion selection, and shifted 11-week outer gate. No signal was
recalculated from daily data. Fractional shares were allowed and costs were
charged at each modeled layer.

Eighteen selected price files had been evicted locally by iCloud and returned
I/O errors. They were reacquired from the same Yahoo and Tiingo providers into
a separate repair vintage. Every repaired file was hashed; the original frozen
files were not overwritten. The daily audit covered 622 dividend events, nine
split events, and produced a 2,220-row $10,000 trade ledger.

At 50 bps, the exact daily trailing-one-year result was 102.49% CAGR, 2.289
Sharpe, and -17.94% maximum drawdown. This is more conservative than the
105.10% weekly estimate and is now the preferred display number. A one-session
delay retained 94.70% CAGR, a two-session delay retained 96.96%, and a 200-bps
cost case retained 89.79%. The maximum individual weekly reconciliation
difference was 1.81 percentage points. Independent reruns produced identical
performance, daily-path, trade-ledger, and reconciliation hashes.

References:

- `config/sec_cash_conversion_breadth20_daily_execution_audit_v1.json`
- `scripts/run_sec_cash_conversion_breadth20_daily_execution_audit_v1.py`
- `scripts/repair_daily_audit_price_sources_v1.py`
- `data/daily_audit_price_source_repairs_v1/manifest.csv`
- `evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1/result.json`
- `evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1/report.md`
- `evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1/trade_ledger_10000.csv`

## Step 117 — Add the daily-audited leader to the Version 2 dashboard

The Next.js dashboard data builder now publishes three selectable strategies:
the ETF incumbent, the standalone Micron-led growth experiment, and the new
daily-audited breadth-20 leader. The new view uses daily returns through August
11, 2026, shows the conservative 102.49% audited metric, exposes the full
look-through allocation, marks holding-change dates in bone white, and retains
green/red daily P&L cells. Rebalance activity now calculates turnover from the
displayed look-through target change instead of showing zero for internal
sleeve changes.

The breadth view contains ETF and stock histories for clickable price charts.
A calendar-originated chart stops at that calendar date; a current-allocation
chart stops at the latest available date. The production TypeScript check and
Next.js build passed. A local browser check confirmed the strategy selector,
daily calendar, 27-position current allocation, rebalance log, Micron price
modal cutoff, and absence of console errors.

References:

- `dashboard/scripts/build-return-first-dashboard.py`
- `dashboard/public/return-first-dashboard.json`

## Step 177 — Fragility-aware accelerator and industry-residual tournament

A frozen 40-candidate tournament tested all five planned improvements on the
August 7, 2026 common endpoint: causal fragility guards, an 8%/12% financing
and 1.25x/1.30x/1.35x exposure map, a new industry-residual momentum plus SEC
acceleration family, common-cost robustness tests, and preservation of the
exact-daily 174.97% diagnostic in the dashboard.

The strongest retrospective candidate, `alpha30_1.35x`, returned 186.90% over
the trailing 52 weeks with 3.206 Sharpe and -15.06% maximum drawdown. It
retained 142.28% at 200-bps costs, 159.63% under the worst execution delay, and
162.32% under the conservative five-issuer stress. It nevertheless failed the
frozen evidence gates: rolling 26-week outperformance was only 47.02% and the
familywise-adjusted bootstrap probability was 83.68%, below the required 60%
and 95%. No candidate passed every historical gate.

The independent industry-residual family did not rival the incumbent. Its best
levered candidate returned 71.20% with 2.506 Sharpe and -7.37% drawdown, and
failed the issuer-dependence test. That branch is rejected in its present form.
The 186.90% result is saved as a fragile research lead, not a replacement.

The dashboard now includes the exact-daily 174.97% amplifier as a selectable
strategy with a visible failed-robustness label. The Next.js production build,
type check, and interactive browser verification passed without console errors.
Live trading and strategy replacement remain disabled.

References:

- `config/sec_fragility_industry_tournament_v1.json`
- `scripts/run_sec_fragility_industry_tournament_v1.py`
- `tests/test_sec_fragility_industry_tournament_v1.py`
- `docs/SEC_FRAGILITY_INDUSTRY_TOURNAMENT_V1.md`
- `research_registry/sec_fragility_industry_tournament_v1.json`
- `evidence/sec_fragility_industry_tournament_v1/`
- `dashboard/scripts/append-fragile-dashboard-strategy.py`

## Step 178 — Broad quant mathematics tournament v3

A pre-result sealed, one-shot tournament evaluated 96 broad-universe candidates
using causal monthly price features and the latest available point-in-time SEC
snapshot. The engine added robust residualization, quality interactions, purged
nonlinear ridge, inverse-volatility and covariance-shrinkage construction,
controlled exposure, deflated Sharpe, CSCV overfitting probability, and the
existing cost, delay, issuer, sector, and missing-company stresses.

The best broad candidate returned 123.33% recently but had -43.66% drawdown,
only 1.590 Sharpe, 23.99% under delayed execution, and -10.31% after removing
its five largest positive issuers. No candidate passed. The broad v3 strategy
family is rejected as a replacement, although its causal monthly panel and
portfolio mathematics are retained as infrastructure.

## Step 179 — Above-300% fragility exposure study

A second sealed study tested 22 exposure rules on the 186.90% fragility-aware
source candidate. It demonstrated that the historical path can exceed both
200% and 300%: fixed 1.50x returned 217.11%, fixed 1.65x returned 249.96%, and
fixed 2.00x returned 337.83%. The 2.00x path had 3.132 recent Sharpe and -22.02%
recent drawdown, but its full-history drawdown reached -37.16%.

No exposure rule passed all gates. The 2.00x ceiling achieved only 83.28%
familywise-adjusted bootstrap confidence and 85.90% deflated-Sharpe confidence,
while CSCV estimated a 37.14% probability of backtest overfitting. The 217.11%,
220.60%, and 337.83% variants are saved as fragile diagnostics only. No strategy
replacement, dashboard default change, execution, or live trading was enabled.

References:

- `docs/SEC_QUANT_MATH_TOURNAMENT_V3.md`
- `docs/SEC_FRAGILITY_EXPOSURE_CONTROL_V1.md`
- `evidence/sec_quant_math_tournament_v3/`
- `evidence/sec_fragility_exposure_control_v1/`


## Step 177 — Test realistic financing, adaptive leverage, and contribution risk

A separate sealed experiment compared unlevered exposure, fixed 1.25x exposure,
causal adaptive 1.00x-1.25x exposure, and adaptive exposure with a ticker-neutral
residual-sleeve volatility-contribution limit. It preserved the existing 0/52
forward protocol. Financing was charged weekly only above 1.00x, using the
published 5% path as a reference, 8% as the baseline, and 12% as a stress.
Leverage changes, internal margin safety, broker maintenance ratios, and forced
next-week deleveraging were modeled explicitly.

On the common trailing-52-week endpoint, fixed 1.25x returned 150.86% at the
published 5% assumption and 149.01% at 8%. Adaptive leverage returned 147.66%
with 3.088 Sharpe and -13.86% drawdown. Adding the residual contribution limit
improved that slightly to 147.76%, 3.090, and -13.86%, while keeping observed
issuer volatility-budget contribution at 12% or less. Neither adaptive path
beat the 8% fixed benchmark or had familywise bootstrap support, so no research
display winner or replacement was authorized.

No historical margin breach occurred, but shock arithmetic showed why this is
not evidence of safety: a 50% one-week asset loss at 1.25x would lose about
62.5% of equity without crossing the frozen threshold, while a 60% asset loss
would lose about 75% and trigger internal deleveraging. The dashboard incumbent,
forward clock, and live-trading-disabled state were unchanged.

References:

- `config/sec_residual_financing_adaptive_risk_v1.json`
- `scripts/run_sec_residual_financing_adaptive_risk_v1.py`
- `scripts/audit_sec_residual_financing_adaptive_risk_v1.py`
- `tests/test_sec_residual_financing_adaptive_risk_v1.py`
- `evidence/sec_residual_financing_adaptive_risk_v1/`
- `evidence/sec_residual_financing_adaptive_risk_audit_v1/`
- `dashboard/src/components/return-first-dashboard.tsx`

## Step 118 — Build a split-normalized point-in-time valuation pipeline

Valuation was reintroduced only after fixing the price/share basis. Market
capitalization now uses the last raw close strictly before the decision and the
latest SEC shares-outstanding fact known before that decision. If a split
occurred after the shares fact period but on or before the price date, the
share count is carried forward by that split ratio. Adjusted close is retained
only for a distortion audit and never enters a valuation signal. Zero and
negative SEC share facts are rejected rather than converted into artificial
market caps.

Across the current 20-stock technology/energy pilot, the old shortcut of
adjusted price times unadjusted filing shares understated market cap by a
median 58.4% on split-affected rows. The corrected pipeline passed all timing,
positivity, bounded-split, and finite-result checks. Sales yield was the best
pilot family: 41.25% holdout CAGR, 1.637 Sharpe, and -19.43% drawdown at 50
bps, versus 31.70% holdout CAGR for XLK. Its latest-year CAGR was 49.00%.

This result is not promotable because the pilot uses today's surviving 20
companies. It establishes a mechanically valid valuation foundation for a
future survivorship-aware universe.

References:

- `config/sec_split_normalized_valuation_pilot_v1.json`
- `scripts/run_sec_split_normalized_valuation_pilot_v1.py`
- `evidence/sec_split_normalized_valuation_pilot_v1/result.json`
- `evidence/sec_split_normalized_valuation_pilot_v1/split_distortion_audit.csv`
- `evidence/sec_split_normalized_valuation_pilot_v1/report.md`

## Step 119 — Reject the small valuation overlay after a controlled test

The corrected sales-yield pilot was tested as a 10%-50% sleeve beside the
frozen breadth-20 leader. The batch covered static allocation and three shifted
relative-return gates, 4/8/13/26-week lookbacks, and 0/50/100/200-bps outer
costs, for 320 paths. Every dynamic signal was shifted one week before use.

No variant improved both recent and full-period CAGR. The top recent row
matched the 105.10% weekly control only because its defensive gate remained
inactive during that window; its full CAGR fell to 40.29% from 40.93%. The
sales-yield sleeve is therefore rejected for the current leader and retained
only as a foundation for a broader survivorship-aware test.

References:

- `config/sec_split_normalized_valuation_overlay_v1.json`
- `scripts/run_sec_split_normalized_valuation_overlay_v1.py`
- `evidence/sec_split_normalized_valuation_overlay_v1/result.json`
- `evidence/sec_split_normalized_valuation_overlay_v1/top_recent_candidates.csv`
- `evidence/sec_split_normalized_valuation_overlay_v1/report.md`

## Step 120 — Expand corrected valuation to the survivorship-aware SEC universe

The point-in-time valuation pipeline was expanded from the 20-stock pilot to
598 historical issuers and 7,035 tradable membership rows. An initial run
exposed impossible market capitalizations caused by stale or class-specific
shares-outstanding facts. Those results were discarded. The repaired basis
accepts a recent shares-outstanding fact only when it is economically
consistent with diluted shares; otherwise it uses diluted shares known before
the decision. Split carry begins only after the relevant filing was available.

The corrected panel loaded 576 issuer price sources with no unreadable files
and maintained at least 89.92% market-cap coverage. Sales yield with ten names
was the strongest discovery result at 99.28% recent CAGR and 74.51% full CAGR,
but discovery alone did not authorize promotion.

References:

- `config/sec_survivorship_valuation_discovery_v1.json`
- `scripts/run_sec_survivorship_valuation_discovery_v1.py`
- `evidence/sec_survivorship_valuation_discovery_v1/result.json`
- `evidence/sec_survivorship_valuation_discovery_v1/normalized_valuation_panel.csv`
- `evidence/sec_survivorship_valuation_discovery_v1/report.md`

## Step 121 — Falsify valuation across liquidity, breadth, costs, and timing

Five factor families, six market-cap floors, three portfolio breadths, three
cost levels, execution delays, split exclusions, and leave-one-company-out
tests were run. The only structure to edge past the 105.10% weekly leader on
both recent and full horizons was ten-name sales yield with a $25 million
floor: 105.36% recent CAGR and 56.06% full CAGR.

That standalone result failed concentration and timing tests. Removing
Rackspace reduced recent CAGR to 62.47%; a one-week execution delay reduced it
to 81.48%. The strategy was therefore not promoted. Excluding every
split-affected issuer produced 109.10% recent CAGR and 42.66% full CAGR and was
retained for a controlled combination test.

References:

- `config/sec_survivorship_valuation_falsification_v1.json`
- `scripts/run_sec_survivorship_valuation_falsification_v1.py`
- `evidence/sec_survivorship_valuation_falsification_v1/result.json`
- `evidence/sec_survivorship_valuation_falsification_v1/recent_leave_one_company_out.csv`
- `evidence/sec_survivorship_valuation_falsification_v1/report.md`

## Step 122 — Test and reject the aggressive valuation combination

Seven valuation sleeves were combined with the weekly leader across 5%-50%
allocations, five timing gates, five lookbacks, and three outer cost levels.
The 3,675-path search found 322 retrospective combinations that beat the
leader on recent and full CAGR before falsification. The strongest was a
static 50% allocation to the split-excluded ten-name sales-yield sleeve:
111.69% recent CAGR, 2.138 Sharpe, -16.23% drawdown, and 43.81% full CAGR.

The follow-up audit tested 30%, 40%, and 50% allocations under one- and
two-week valuation delays, 50/100/200-bps underlying and overlay costs, and
leave-one-issuer-out scenarios. The 50% candidate retained 109.65% recent CAGR
at the severe 200-bps setting, but fell to 99.69% with a one-week delay and
86.69% without Rackspace. The 30% alternative had the best risk balance at
110.17% recent CAGR, 2.423 Sharpe, and -13.61% drawdown, but fell to 94.48%
without Rackspace and 39.83% full CAGR in that exclusion. No allocation passed
the concentration gate, so the 105.10% weekly leader remains the leader and
the valuation combination remains an unpromoted research challenger.

References:

- `config/sec_survivorship_valuation_overlay_search_v1.json`
- `scripts/run_sec_survivorship_valuation_overlay_search_v1.py`
- `evidence/sec_survivorship_valuation_overlay_search_v1/result.json`
- `config/sec_survivorship_valuation_overlay_audit_v1.json`
- `scripts/run_sec_survivorship_valuation_overlay_audit_v1.py`
- `evidence/sec_survivorship_valuation_overlay_audit_v1/result.json`
- `evidence/sec_survivorship_valuation_overlay_audit_v1/report.md`

## Step 123 — Repair valuation concentration with breadth, sector limits, and staggered cohorts

The rejected aggressive valuation overlay was rebuilt rather than merely
having Rackspace removed. Six point-in-time factor sets were tested across
10/15/20/30-stock breadths, four liquidity floors, 50%-80% two-sector limits,
one/two/four staggered cohorts, 10%-40% allocations, and 50/100/200-bps costs.
The two-sector limits reflect the actual historical SEC universe, which in
this experiment contains technology and energy issuers. The completed search
covered 360 sleeves and 12,960 costed portfolio paths.

The strongest raw diversified path was a 40% allocation to a ten-stock sales
yield sleeve at 111.21% recent CAGR, 2.333 Sharpe, -15.28% drawdown, and 41.96%
full CAGR. It retained 109.79% at 200 bps, but fell to 102.65% with a one-week
delay and 89.96% when Rackspace was removed. It therefore repeated the
concentration failure and was rejected.

The best risk-adjusted challenger used twenty stocks, a $50 million liquidity
floor, a 50% per-sector limit, and a 30% allocation. It produced 107.69%
recent CAGR, 2.994 Sharpe, -8.89% drawdown, and 42.39% full CAGR. It beat the
control in 55.83% of rolling 26-week windows and retained 106.82% under 200-bps
costs. Nevertheless, a one-week delay reduced recent CAGR to 102.78%, and the
weakest leave-one-issuer-out case reduced it to 100.72%. It is saved as a
diversified risk-adjusted challenger but not promoted. The 105.10% weekly
return leader remains unchanged.

References:

- `config/sec_diversified_valuation_ensemble_search_v1.json`
- `scripts/run_sec_diversified_valuation_ensemble_search_v1.py`
- `evidence/sec_diversified_valuation_ensemble_search_v1/result.json`
- `config/sec_diversified_valuation_ensemble_audit_v1.json`
- `scripts/run_sec_diversified_valuation_ensemble_audit_v1.py`
- `evidence/sec_diversified_valuation_ensemble_audit_v1/result.json`
- `evidence/sec_diversified_valuation_ensemble_audit_v1/candidate_summary.csv`
- `research_registry/sec_diversified_valuation_ensemble_v1.json`

## Step 124 — Test filing-triggered fundamental acceleration and reject the recent-only lift

A new event-driven research path used actual SEC availability timestamps rather
than quarterly portfolio dates. The panel contained 4,789 filing events across
578 historical issuers. Revenue, operating-income, cash-flow, margin, and
dilution changes became eligible only after their source facts were public.
Four- and eight-week price confirmation used the prior weekly close, not the
execution close.

The static search covered 5,832 paths across three fundamental-momentum
families, 4/8/13-week event ages, three price-confirmation rules, 10/20/30-name
breadths, three liquidity floors, two sector limits, four controlled
allocations, and 50/100/200-bps costs. The strongest recent result was a 20%
allocation to 30 positive-eight-week-price-confirmed filing names: 105.38%
recent CAGR, 2.929 Sharpe, and -10.76% drawdown. Full CAGR was only 38.59%, and
recent CAGR fell to 102.29% at 200 bps. No static path beat the leader on both
recent and full CAGR.

A second search tested 900 one-week-shifted conditional allocations. The best
recent gate activated a 50% sleeve only when the leader was negative and the
filing sleeve was positive over the prior eight weeks. It reached 107.04%
recent CAGR with -10.08% drawdown, but full CAGR remained 38.57% and its
200-bps recent CAGR was 104.11%. No conditional path beat the 105.10% recent
and 40.93% full control simultaneously. The filing signal is therefore
rejected as a replacement and recorded as a recent-only diagnostic rather
than a saved leader.

References:

- `config/sec_filing_fundamental_momentum_search_v1.json`
- `scripts/run_sec_filing_fundamental_momentum_search_v1.py`
- `evidence/sec_filing_fundamental_momentum_search_v1/result.json`
- `config/sec_filing_momentum_dynamic_overlay_v1.json`
- `scripts/run_sec_filing_momentum_dynamic_overlay_v1.py`
- `evidence/sec_filing_momentum_dynamic_overlay_v1/result.json`
- `research_registry/sec_filing_fundamental_momentum_v1.json`

## Step 125 — Test SEC Form 4 insider clusters and retain only as a diversifier

The official SEC Insider Transactions Data Sets were acquired for every
quarter from 2023 Q1 through 2026 Q2. All 14 source ZIP files were preserved
in an immutable timestamped vintage and their SHA-256 hashes were verified.
The normalized panel retained 2,560 original Form 4 filings across 362
historical issuers. Only non-derivative open-market purchase transactions
(code P, acquisition code A) with positive shares and prices were eligible;
amendments, grants, option exercises, sales, and equity swaps were excluded.
Because the bulk tables provide a filing date rather than an acceptance time,
each filing became eligible only on a strictly later Friday decision.

The search correctly counted distinct reporting-owner CIKs across separate
filings, so a CEO and CFO buying independently within the same window formed a
cluster. It tested all purchases, two-person clusters, executive-or-cluster,
non-10b5-1, and non-10b5-1 cluster families across 7/14/30-day windows,
optional lagged four-week price confirmation, 5/10/20/30-name breadths, two
liquidity floors, two sector limits, 10%-40% allocations, and 50/100/200-bps
costs. This produced 480 structures and 5,760 costed overlay paths.

The best return path was a 10% allocation to five executive-or-cluster names
from a 30-day window: 97.36% recent CAGR, 2.777 Sharpe, -9.13% recent drawdown,
and 37.38% full CAGR. It retained 91.32% recent CAGR at 200-bps costs. The
cluster-only version reached 97.28% recent CAGR, 2.788 Sharpe, and -8.88%
drawdown. These are useful risk-adjusted diversification results, but no path
beat the 105.10% recent and 40.93% full-CAGR control simultaneously. The
weekly leader therefore remains unchanged and the insider signal is saved as
an unpromoted research diversifier.

References:

- `config/sec_form4_bulk_acquisition_v1.json`
- `scripts/acquire_sec_form4_bulk_v1.py`
- `data/sec_form4_bulk_vintages/20260815T005416Z-sec-form4-bulk-v1/manifest.json`
- `config/sec_form4_insider_cluster_search_v1.json`
- `scripts/run_sec_form4_insider_cluster_search_v1.py`
- `evidence/sec_form4_insider_cluster_search_v1/result.json`
- `evidence/sec_form4_insider_cluster_search_v1/report.md`
- `research_registry/sec_form4_insider_cluster_v1.json`

## Step 126 — Test the Form 4 insider sleeve as a causal overlay and reject it on concentration grounds

Step 125 only tested the Form 4 insider-purchase signal as a fixed-weight static
blend against the frozen breadth-20 leader and found no static allocation beat
the control on both recent and full CAGR. This mirrored the cash-conversion
family's own history: a static blend failed in Step 114, and only a causal
relative-trend gate turned it into the current leader in Step 115. The same
gate pattern was applied to the Form 4 signal instead of re-running its
480-structure search, to avoid compounding a second layer of retrospective
selection on top of an already-searched signal. Three predeclared
insider-purchase families (all open-market purchases, two-or-more-owner
clusters, and executive-or-cluster purchases), a fixed 30-day event window, a
10-name breadth, a $50 million market-cap floor, and a 70% sector cap were
combined with a shifted rolling-trend gate at 8/13/26-week lookbacks and
10%/20%/30% allocations, producing 27 predeclared overlays at 50/100/200 bps.

The strongest screened candidate, a 13-week executive-or-cluster gate with a
30% allocation, produced 108.43% trailing-one-year CAGR, 2.768 Sharpe, and
-10.08% drawdown, versus 105.10%, 2.692, and -10.08% for the unchanged
control; full-period CAGR improved from 40.93% to 41.41%, and it retained
94.11% at 200 bps. On its face this passed every predeclared screening gate.

It failed the deeper falsification gauntlet. Excluding a single company,
ProFrac Holding Corp., from the sleeve dropped trailing-one-year CAGR to
99.27%, below the unchanged control — the same single-stock fragility that
sank the 110% three-tier candidate in Step 113. Only 35.11% of rolling
26-week windows beat the control, and only 33.33% of the same family's
neighboring lookback/allocation combinations jointly improved recent and full
CAGR, short of the 50% bar. The 4-week block bootstrap assigned only 70.80%
probability to a positive difference. One- and two-week signal delays did
still beat the control (106.76% and 106.61%), so timing was not the failure
mode.

Two further diagnostics limit what this experiment can claim even before
falsification: maximum drawdown was numerically identical across all 27
candidates and the control, and year-to-date 2026 CAGR matched the control to
nine decimal places, meaning the gate never activated during calendar-year
2026 or during the leader's own worst historical week. The entire claimed
improvement is concentrated in a minority of active weeks in 2025. The
candidate is rejected; the breadth-20 leader and its existing forward
protocol are unchanged, and no new forward observation clock is started for
this candidate.

References:

- `config/sec_form4_dynamic_overlay_v1.json`
- `scripts/run_sec_form4_dynamic_overlay_v1.py`
- `evidence/sec_form4_dynamic_overlay_v1/result.json`
- `evidence/sec_form4_dynamic_overlay_v1/performance.csv`
- `evidence/sec_form4_dynamic_overlay_v1/screening_gates.csv`
- `evidence/sec_form4_dynamic_overlay_v1/recent_leave_one_company_out.csv`
- `evidence/sec_form4_dynamic_overlay_v1/parameter_neighborhood.csv`
- `evidence/sec_form4_dynamic_overlay_v1/delay_stress.csv`
- `evidence/sec_form4_dynamic_overlay_v1/bootstrap.csv`
- `evidence/sec_form4_dynamic_overlay_v1/report.md`
- `research_registry/sec_form4_dynamic_overlay_v1.json`

## Step 143 — Raise the challenger to 123.71% with issuer-level multi-signal membership

The remaining issuer dependence was attacked inside the cash-conversion sleeve
without changing the breadth controller, fast market-regime activation, or
four-week equal-tranche schedule. The search tested 178 predeclared variants:
cash-conversion, balance-sheet-quality, and shareholder-discipline membership
blends crossed with equal, sector-balanced, inverse-volatility, inverse-
correlation, and combined causal risk weights. All adaptive weights used only
weekly returns ending before the quarterly decision, with generic shrinkage
and per-name caps.

The selected construction was simpler than the risk-weighted alternatives. It
ranked companies using 80% cash-conversion and 20% balance-sheet-quality scores,
selected the top 20, and equal weighted them. Rebuilding the complete regime
strategy around this sleeve produced 123.71% trailing-one-year CAGR, 3.117
Sharpe, -8.71% drawdown, 42.47% full CAGR, and 108.45% recent CAGR at 200-bps
costs. One/two-week delays of only the new increment retained 121.72%/120.15%,
and peak portfolio single-stock exposure was 6.82%.

The issuer result materially improved. Removing every recently held company
one at a time left a worst case of 120.04% when 10x Genomics was removed. This
beats both the 119.22% predecessor and the untouched 112.93% base. The candidate
also beat its predecessor in 51.53% of 163 completed rolling 26-week windows.
The local 15%/17.5%/20%/22.5%/25% balance-weight neighborhood passed the full
surface in three of five cases; the 20%, 22.5%, and 25% settings formed the
stable region.

Complete falsification nevertheless failed. Four-week and thirteen-week block-
bootstrap probabilities of positive excess versus the 119.22% predecessor were
82.90% and 80.28%, below the predeclared 95% promotion threshold. The 123.71%
path therefore becomes the strongest saved return-oriented research challenger,
but it does not replace the frozen 105.10% incumbent, start a forward clock, or
enable live execution.

References:

- `config/sec_cluster_aware_cash_sleeve_v1.json`
- `scripts/run_sec_cluster_aware_cash_sleeve_v1.py`
- `tests/test_sec_cluster_aware_cash_sleeve_v1.py`
- `evidence/sec_cluster_aware_cash_sleeve_v1/result.json`
- `evidence/sec_cluster_aware_cash_sleeve_v1/screening.csv`
- `evidence/sec_cluster_aware_cash_sleeve_v1/balance_weight_neighborhood.csv`
- `evidence/sec_cluster_aware_cash_sleeve_v1/leave_one_company_out.csv`
- `evidence/sec_cluster_aware_cash_sleeve_v1/report.md`
- `research_registry/sec_cluster_aware_cash_sleeve_v1.json`

## Step 144 — Locked audit exposes endpoint and multi-issuer fragility

The 123.71% challenger was frozen exactly and reconstructed byte-for-byte from
its 80% cash-conversion / 20% balance-sheet-quality top-20 rule. No parameters
were reselected. The 188 available weeks were divided into three non-overlapping
52-week retrospective pseudo-holdouts, and the fixed strategy was subjected to
rolling windows, fourteen nearby trailing-year endpoints, quarterly ablation,
decision and increment delays, severe costs, and simultaneous removal of the
historically most damaging issuers.

The candidate remained positive in all three one-year blocks and beat the
119.22% predecessor in two of three. Its block CAGRs were 17.31%, 16.00%, and
125.80%, versus 18.63%, 14.34%, and 121.04% for the predecessor. Every one/two-
week decision, increment, and combined delay retained at least 122.92% recent
CAGR. The exact trailing-52-week 200-bps result was 110.18%, and three of four
quarter-removal cases still beat the predecessor.

The audit also showed that the improvement is concentrated near the latest
endpoint. Only two of fourteen adjacent trailing-year endpoints beat the
predecessor. Rolling outperformance shares were 44.32%, 51.53%, and 46.72% for
13/26/52-week windows. Removing the single worst issuer retained 122.03%, but
simultaneously removing the worst two, three, and five issuers reduced recent
CAGR to 112.08%, 111.13%, and 110.56%. Four/thirteen-week bootstrap probabilities
were 83.94%/81.72%, still below 95%.

The locked audit failed. The 123.71% result remains the highest saved research
return, but it is not yet temporally broad enough for promotion. The next
justified branch is a fixed ensemble of the already-confirmed 20%/22.5%/25%
balance-score neighborhood and the cash-only predecessor—not another parameter
search—aimed specifically at endpoint and simultaneous-issuer robustness.

References:

- `config/sec_cluster_challenger_locked_audit_v1.json`
- `scripts/run_sec_cluster_challenger_locked_audit_v1.py`
- `tests/test_sec_cluster_challenger_locked_audit_v1.py`
- `evidence/sec_cluster_challenger_locked_audit_v1/result.json`
- `evidence/sec_cluster_challenger_locked_audit_v1/nonoverlapping_52w_blocks.csv`
- `evidence/sec_cluster_challenger_locked_audit_v1/trailing_endpoint_perturbation.csv`
- `evidence/sec_cluster_challenger_locked_audit_v1/missing_issuer_bundles.csv`
- `evidence/sec_cluster_challenger_locked_audit_v1/report.md`
- `research_registry/sec_cluster_challenger_locked_audit_v1.json`

## Step 145 — Improve endpoint breadth with a fixed holdings ensemble

Nine fixed ensembles combined only the already-confirmed 20%/22.5%/25%
balance-score cohorts and the cash-only predecessor. The complete sleeve,
breadth controller, fast-regime increment, and four-week schedule were rebuilt
for each ensemble. Selection required at least 119.22% exact trailing-52-week
CAGR, full CAGR no worse than the predecessor, severe-cost and delay floors,
at least 50% nearby-endpoint and rolling-26-week outperformance, and no more
than 8% peak single-stock exposure.

Only one candidate passed: a 50/50 holdings blend of the cash-only top 20 and
the 80/20 cash-conversion/balance-sheet top 20. It held 26 distinct names in
the latest cohort and produced 123.56% exact trailing-52-week CAGR, 3.088
Sharpe, -8.71% drawdown, 42.52% full CAGR, and 106.67% at 200-bps costs. Its
worst decision/increment-delay result was 122.32%, peak single-stock exposure
was 7.05%, nearby-endpoint outperformance improved from 14.29% to 50.00%, and
rolling-26-week outperformance improved from 51.53% to 57.06%.

The fixed ensemble repaired much of the timing concentration but did not solve
joint issuer dependence. Removing the historically worst one issuer left
121.57%, while removing the worst two, three, and five together left 111.44%,
109.98%, and 109.32%. Four/thirteen-week bootstrap probabilities improved only
to 84.88%/82.58%. The branch is retained as the strongest endpoint-stabilized
diagnostic, not promoted. The next bounded test is a mild sector-aware selection
constraint around this exact 50/50 ensemble because its latest cohort remains
87.5% technology.

References:

- `config/sec_signal_neighborhood_ensemble_v1.json`
- `scripts/run_sec_signal_neighborhood_ensemble_v1.py`
- `tests/test_sec_signal_neighborhood_ensemble_v1.py`
- `evidence/sec_signal_neighborhood_ensemble_v1/result.json`
- `evidence/sec_signal_neighborhood_ensemble_v1/screening.csv`
- `evidence/sec_signal_neighborhood_ensemble_v1/missing_issuer_bundles.csv`
- `evidence/sec_signal_neighborhood_ensemble_v1/report.md`
- `research_registry/sec_signal_neighborhood_ensemble_v1.json`

## Step 146 — Raise the endpoint-stabilized diagnostic to 124.20%

The remaining 87.5% technology concentration was tested with nine generic
sector-aware selection policies around the fixed 50/50 cash-only/balance-ranked
holdings ensemble. Both symmetric 70%–90% sector limits and three asymmetric
component limits were predeclared. Every construction rebuilt the underlying
sleeves, controller, regime increment, delays, severe-cost path, and one/two/
three/five-issuer bundle stresses.

No construction passed every gate because none lifted the simultaneous five-
issuer floor above the 112.93% base. The strongest diagnostic was asymmetric:
an 80% sector cap on the cash-only component and 90% on the balance-ranked
component. It raised exact trailing-52-week CAGR from the ensemble's 123.56%
to 124.20%, Sharpe from 3.088 to 3.103, full CAGR from 42.52% to 42.74%, and
200-bps CAGR from 106.67% to 107.27%, with the same -8.71% drawdown. The worst
delay retained 122.80%, peak single-stock exposure was 7.03%, and the latest
maximum sector share fell to 85% across 26 names.

Endpoint and rolling-26-week outperformance remained 50.00% and 57.06%.
Bootstrap probabilities improved to 88.50%/84.24%, but stayed below 95%.
The worst five-issuer bundle remained 109.32%, proving that simple sector
constraints do not resolve the shared-company dependence. The 124.20% path is
saved as the strongest return-plus-endpoint diagnostic, but it is not promoted
and does not replace the 123.71% locked research challenger.

References:

- `config/sec_sector_aware_signal_ensemble_v1.json`
- `scripts/run_sec_sector_aware_signal_ensemble_v1.py`
- `tests/test_sec_sector_aware_signal_ensemble_v1.py`
- `evidence/sec_sector_aware_signal_ensemble_v1/result.json`
- `evidence/sec_sector_aware_signal_ensemble_v1/screening.csv`
- `evidence/sec_sector_aware_signal_ensemble_v1/missing_issuer_bundles.csv`
- `evidence/sec_sector_aware_signal_ensemble_v1/report.md`
- `research_registry/sec_sector_aware_signal_ensemble_v1.json`

## Step 128 — Use Form 4 purchases as a diversified rank feature and reject the result

The concentration failure in Steps 126–127 suggested a narrower use for insider
purchases: a bounded feature inside the existing diversified cash-conversion
ranker, rather than a separate concentrated sleeve. A causal grid tested 30-day
and 90-day executive-or-cluster Form 4 scores at 0%/5%/10%/20%/30% feature
weights, ticker-agnostic prior-winner penalties of 0%/5%/10%, and
50%/70%/100% sector caps. Each stock sleeve targeted 20 equal-weight issuers,
used the existing 1.5x internal cap, and fed the frozen 11-week/50% causal
overlay. The 0% variants supplied matched no-Form-4 baselines. In total, 90
structures were evaluated at 50/100/200 bps under base and adverse scenarios.

The selected 90-day, 5%-feature path produced 105.48% trailing-one-year CAGR,
2.705 Sharpe, -9.83% drawdown, and 38.17% full CAGR. That was only 0.38
percentage points above the frozen leader's 105.10%, below the predeclared
one-point improvement gate, while full CAGR fell from 40.93% to 38.17%.
Against the exactly matched constrained no-Form-4 structure, the signal added
0.73 points recently but removed 2.69 points over the full period.

The deeper evidence was uniformly weak. A one-week decision delay returned
98.21% and a two-week delay 102.51%; only 25.77% of 163 completed rolling
26-week windows beat the control; no neighboring parameter combination jointly
improved recent and full CAGR; and 4-week/13-week block-bootstrap probabilities
were 80.54%/87.22%, below the required 95%. Exact leave-one-company-out
reranking identified GitLab as the worst omission and reduced recent CAGR to
96.24%. The candidate failed every substantive promotion group despite its
slightly higher headline return. It is rejected, the 105.10% frozen leader
remains unchanged, and neither execution nor a new forward clock was enabled.

References:

- `config/sec_form4_rank_feature_v1.json`
- `scripts/run_sec_form4_rank_feature_v1.py`
- `tests/test_sec_form4_rank_feature_v1.py`
- `evidence/sec_form4_rank_feature_v1/result.json`
- `evidence/sec_form4_rank_feature_v1/report.md`
- `research_registry/sec_form4_rank_feature_v1.json`

## Step 129 — Combine independent fundamentals at the issuer level and retain one promising diagnostic

Earlier factor-rotation and top-two-sleeve experiments combined the returns of
already-formed portfolios and failed. This experiment instead combined signals
before stock selection, requiring individual issuers to rank on cash conversion
and one or more independent SEC fundamental dimensions. Twenty-seven frozen
issuer-level ensemble specifications covered single secondary families at
10%/20%/30%, pairs at 20%/40% total weight, and all four secondaries at
20%/40%. Each was crossed with 0%/5% Form 4 confirmation and 70%/100% sector
caps, producing 108 breadth-20 candidates at 50/100/200 bps in base and adverse
scenarios. All fundamental inputs remained point-in-time and sector-neutral;
missing secondary scores received a neutral percentile rather than exclusion.

The strongest candidate that cleared the headline screen used 80% cash
conversion and 20% balance-sheet quality, with no Form 4 adjustment and no
additional sector cap. It produced 106.39% trailing-one-year CAGR, 2.712
Sharpe, -10.09% drawdown, and 41.54% full CAGR, versus 105.10%, 2.692,
-10.08%, and 40.93% for the frozen control. It retained 94.42% recent CAGR at
200 bps versus 93.20% for the control. Relative to its mechanically matched
cash-only candidate, the second signal added 1.63 points recently and 0.67
points over the full period.

This is better evidence than the prior Form 4 feature, but it is not sufficient
for promotion. A one-week delay retained 106.92%, while a two-week delay fell
to 100.43%. It beat the control in 55.83% of 163 completed rolling 26-week
windows, but only 8.33% of its twelve nearby weight/Form-4/sector variants
improved both recent and full CAGR. Four-week and thirteen-week block-bootstrap
probabilities of a positive difference were only 68.02% and 71.44%, below the
required 95%. Exact leave-one-company-out reranking left the worst case, 10X
Genomics, at 105.71%, still above the control, but that issuer explained 52.25%
of the small improvement and narrowly exceeded the 50% influence limit.

The 80/20 construction is preserved as a promising diagnostic, not a new
leader. The 105.10% breadth-20 strategy remains frozen, no new forward clock
was started, and live execution remains disabled. A future follow-up may test a
strictly predeclared fine weight/breadth plateau around the 80/20 structure,
but it must be treated as post-discovery confirmation rather than evidence from
this search.

References:

- `config/sec_multisignal_company_rank_v1.json`
- `scripts/run_sec_multisignal_company_rank_v1.py`
- `tests/test_sec_multisignal_company_rank_v1.py`
- `evidence/sec_multisignal_company_rank_v1/result.json`
- `evidence/sec_multisignal_company_rank_v1/report.md`
- `research_registry/sec_multisignal_company_rank_v1.json`

## Step 130 — Lock the 80/20 blend and reject it after a fine plateau confirmation

Step 129's 80% cash-conversion / 20% balance-sheet-quality breadth-20 result was
locked as the primary candidate before this follow-up. It was not reselected
from the new outcomes. The confirmation crossed five fine secondary weights
(15%, 17.5%, 20%, 22.5%, and 25%) with breadths 15, 20, 25, and 30, producing
twenty prespecified paths. Form 4 and sector constraints were held at the
discovery candidate's zero-adjustment settings. The existing 11-week/50%
causal overlay, 1.5x internal cap, base/adverse cases, and 50/100/200-bps costs
were unchanged.

The primary path reproduced byte-for-byte and retained 106.39% trailing-one-
year CAGR, 2.712 Sharpe, -10.09% drawdown, 41.54% full CAGR, and 94.42% recent
CAGR at 200 bps. This validates the implementation but not the economic
stability of the result.

Only two of twenty fine-grid paths improved both recent and full CAGR, a 10%
plateau share versus the required 50%. The primary was the only path to clear
all headline gates. The other joint improvement, 15% balance-sheet quality at
breadth 30, returned 105.15% recently—only 0.05 percentage points above the
control. The grid's highest recent result, 25% at breadth 25, reached 106.98%
but its full CAGR collapsed to 37.32%, well below the control's 40.93%.

Because the primary path is identical, its remaining falsification failures
also reproduce: two-week delay CAGR of 100.43%, 4-week/13-week bootstrap
probabilities of 68.02%/71.44%, and 52.25% of the small improvement attributable
to the worst issuer omission. The 55.83% completed rolling-window share and
worst leave-one-out CAGR of 105.71% still pass, but cannot overcome the fine-
plateau and resampling failures. The multi-signal blend is rejected as a
replacement. The frozen 105.10% leader remains unchanged and no execution or
new forward clock was enabled.

References:

- `config/sec_multisignal_plateau_confirmation_v1.json`
- `scripts/run_sec_multisignal_plateau_confirmation_v1.py`
- `tests/test_sec_multisignal_plateau_confirmation_v1.py`
- `evidence/sec_multisignal_plateau_confirmation_v1/result.json`
- `evidence/sec_multisignal_plateau_confirmation_v1/fine_plateau.csv`
- `evidence/sec_multisignal_plateau_confirmation_v1/report.md`
- `research_registry/sec_multisignal_plateau_confirmation_v1.json`

## Step 131 — Test issuer-level sector-relative momentum and close the branch

The next distinct source combined the cash-conversion score with strictly
lagged company-price momentum before stock selection. Momentum was measured
over 26, 39, or 52 weeks from the most recent weekly price strictly before each
decision, ranked within sector, and assigned 0%, 10%, 15%, 20%, or 25% of the
issuer score. Breadths 20, 25, and 30 and ticker-neutral rank buffers of zero
or five produced ninety prespecified paths. Fundamentals were carried forward
only after their point-in-time SEC decision date. Holding sets were evaluated
weekly, but an unchanged set was not forced back to equal weight, avoiding
artificial weekly turnover. Base/adverse scenarios and 50/100/200-bps costs
were retained.

The strongest positive-momentum challenger used a 52-week lookback, 15%
momentum weight, breadth 30, and a five-name buffer. It produced 100.09%
trailing-one-year CAGR, 2.593 Sharpe, -11.19% drawdown, and 39.06% full CAGR,
versus 105.10%, 2.692, -10.08%, and 40.93% for the frozen leader. At 200 bps
it returned 88.29% versus 93.20%. Its stock-sleeve annual one-way turnover was
only 2.56x, safely below the 6x gate, so excessive trading was not the cause.

The momentum feature did add 4.03 percentage points of recent CAGR to its
mechanically matched breadth-30 buffered zero-momentum construction. That
construction, however, returned only 96.06%, and no positive-momentum path
beat the actual frozen control recently; none improved both recent and full
CAGR. Falsification was correspondingly weak: one/two-week momentum delays
returned 99.88%/99.69%, one/two-week overlay delays returned 94.64%/94.33%,
48.47% of completed rolling windows won, no local neighbor improved both
horizons, and 4-week/13-week bootstrap probabilities were only 12.02%/17.78%.
Removing Qualys reduced recent CAGR to 93.80%.

This is an economic rejection rather than a timing, turnover, or implementation
failure. Further issuer-momentum weight and lookback tuning is prohibited for
this branch. The frozen 105.10% leader remains unchanged, no forward clock was
started, and live execution remains disabled.

References:

- `config/sec_cash_momentum_rank_v1.json`
- `scripts/run_sec_cash_momentum_rank_v1.py`
- `tests/test_sec_cash_momentum_rank_v1.py`
- `evidence/sec_cash_momentum_rank_v1/result.json`
- `evidence/sec_cash_momentum_rank_v1/screening.csv`
- `evidence/sec_cash_momentum_rank_v1/report.md`
- `research_registry/sec_cash_momentum_rank_v1.json`

## Step 132 — Complete and validate the free SEC earnings-event source

The issuer-level price-momentum branch failed, so the next distinct return
source requires earnings-announcement events. The existing SEC Submissions
cache covered only 111 of the 598 cash-conversion issuers and therefore could
not support an unbiased event test. A resumable collector was added using the
declared SEC contact identity, a 0.13-second global request interval, immutable
gzip response caching, response hashes, retries, and no persisted credentials.
It acquired every issuer's main Submissions record plus each historical segment
overlapping January 2022 onward.

Acquisition completed for all 598 issuers with zero failures. The normalized
vintage contains 10,854 unique Form 8-K/8-K-A Item 2.02 events across 594
issuers from January 3, 2022 through August 20, 2026. Every event has the SEC's
precise `acceptanceDateTime`; no filing-date fallback was required. The SEC can
assign the next business `filingDate` to an after-hours acceptance, including
a weekend gap, so the acceptance timestamp—not filing-date midnight—is frozen
as causal availability.

An independent audit decompressed and hashed all 608 referenced raw source
files, verified both normalized-manifest hashes, confirmed unique issuer rows
and event accessions, required Item 2.02 on every event, and checked every
acceptance time against the SEC filing-date convention. All checks passed.
The source is now authorized for research testing, but it supplies no strategy
result by itself and does not authorize promotion or live trading. The next
experiment can test post-earnings announcement drift using event reactions
known strictly before each portfolio decision.

References:

- `config/sec_earnings_8k_acquisition_v1.json`
- `scripts/acquire_sec_earnings_8k_v1.py`
- `scripts/audit_sec_earnings_8k_acquisition_v1.py`
- `tests/test_acquire_sec_earnings_8k_v1.py`
- `tests/test_audit_sec_earnings_8k_acquisition_v1.py`
- `data/sec_earnings_event_vintages/20260821T035516Z-sec-earnings-8k-v1/manifest.json`
- `data/sec_earnings_event_vintages/20260821T035516Z-sec-earnings-8k-v1/earnings_8k_events.csv`
- `evidence/sec_earnings_8k_acquisition_v1/result.json`
- `evidence/sec_earnings_8k_acquisition_v1/report.md`
- `research_registry/sec_earnings_8k_acquisition_v1.json`

## Step 133 — Test conservative post-earnings drift and reject the ranking overlay

The validated Item 2.02 source was converted into a deliberately conservative
price-reaction signal. Duplicate issuer/report-period filings were collapsed to
the earliest acceptance. Each reaction used the last weekly close before SEC
acceptance and the first weekly close strictly after the acceptance date, then
subtracted the same-period median return of the issuer's sector. A reaction was
not eligible until a later weekly portfolio decision. This produced 8,271
priced reactions across 558 issuers; unavailable reactions were not imputed.

The bounded grid applied centered event-rank adjustments of 10%, 20%, or 30%
for four, eight, or thirteen weeks, with breadths 20/25/30 and ticker-neutral
rank buffers of zero/five. Fifty-four paths were tested under base/adverse
missing-data treatment and 50/100/200-bps costs. Unchanged holding sets were
not mechanically rebalanced.

The strongest result used a four-week window, 30% event adjustment, breadth 20,
and a five-name buffer. At 50 bps it produced 105.84% trailing-one-year CAGR,
2.735 Sharpe, -8.88% drawdown, and 41.55% full CAGR, versus 105.10%, 2.692,
-10.08%, and 40.93% for the frozen control. The drawdown and full-history
improvements are useful evidence, but the 0.74-point recent-return lift missed
the required one-point gate.

The result did not survive implementation stress. Annual sleeve turnover was
6.71x, above the 6x cap, and recent CAGR at 200 bps was 93.41% versus the
control's 93.20%. One/two-week event-signal delays returned 93.64%/93.55%, and
one/two-week outer-overlay delays returned 98.16%/101.92%. Only 12.5% of local
neighbors improved both recent and full CAGR; 4-week/13-week bootstrap
probabilities were 58.84%/64.52%; and exact removal of GitLab reduced recent
CAGR to 96.00%. Only three of 54 paths improved both horizons and none cleared
the surface gates.

The issuer-ranking PEAD overlay is rejected. The validated earnings source is
retained for genuinely different future constructions, but this weight/window
grid must not be tuned further. The frozen 105.10% leader remains unchanged,
no forward clock was started, and live execution remains disabled.

References:

- `config/sec_earnings_drift_rank_v1.json`
- `scripts/run_sec_earnings_drift_rank_v1.py`
- `tests/test_sec_earnings_drift_rank_v1.py`
- `evidence/sec_earnings_drift_rank_v1/result.json`
- `evidence/sec_earnings_drift_rank_v1/event_reactions.csv`
- `evidence/sec_earnings_drift_rank_v1/report.md`
- `research_registry/sec_earnings_drift_rank_v1.json`

## Step 134 — Test a sparse quarterly negative-earnings veto and reject it

The validated earnings-event source was next tested as a low-turnover veto
rather than a weekly ranking feature. At each existing quarterly cash-conversion
rebalance, a top-20 company could be replaced only if its latest sector-relative
earnings reaction was negative and in the configured bottom sector percentile.
Windows of four/eight/thirteen weeks, percentiles of 10%/20%/30%, and limits of
two/four vetoes per rebalance created 18 bounded rules. No extra weekly trading
was introduced and unchanged holding sets were not rebalanced.

The strongest headline path, `veto4__q30__max2`, made five substitutions across
three issuers. At 50 bps it produced 105.10% trailing-one-year CAGR, 2.692
Sharpe, -10.08% drawdown, and 41.05% full CAGR, versus 105.10%, 2.692, -10.08%,
and 40.93% for the frozen control. At 200 bps both produced 93.20% recent CAGR.
The veto therefore added only 0.11 points to full CAGR and added no recent or
severe-cost return.

The result failed the broader evidence gates. One/two-week event delays produced
105.82%/98.73%; outer-overlay delays produced 98.13%/102.72%; completed rolling
outperformance was 49.08%; neighborhood joint improvement was 0%; and 4-week/
13-week bootstrap probabilities were only 11.92%/14.20%. Exact removal of
GitLab reduced recent CAGR to 96.44%. The quarterly veto family is rejected,
the frozen 105.10% leader remains unchanged, and no forward clock or live
execution was started.

During this audit, the earnings reranker and cash-momentum scripts were also
repaired so their 100/200-bps stress cases reuse the allocation targets frozen
from the base 50-bps signal. This prevents transaction costs from changing the
strategy being evaluated. Regenerated headline decisions did not change: the
earnings reranker remains rejected with a corrected 93.41% severe-cost CAGR,
and the cash-momentum challenger remains rejected with 88.29%.

References:

- `config/sec_earnings_negative_veto_v1.json`
- `scripts/run_sec_earnings_negative_veto_v1.py`
- `tests/test_sec_earnings_negative_veto_v1.py`
- `evidence/sec_earnings_negative_veto_v1/result.json`
- `evidence/sec_earnings_negative_veto_v1/selected_veto_log.csv`
- `evidence/sec_earnings_negative_veto_v1/report.md`
- `research_registry/sec_earnings_negative_veto_v1.json`

## Step 135 — Test persistent earnings direction with fundamental acceleration and reject it

The earnings branch next tested a structurally different quarterly confirmation
hypothesis. Rather than using one recent announcement or creating a new weekly
sleeve, it combined the existing cash-conversion rank with two independent,
timestamp-safe features: sector-relative direction across the latest two or
three completed earnings reactions, and acceleration in revenue, operating
income, and operating cash flow from SEC facts already public before the
quarterly decision. The test added no weekly stock-selection trades.

The bounded grid covered 26/52-week fundamental ages, two/three-event earnings
persistence, 0%-30% weights for each confirmation feature, and zero/five-name
rank buffers. Excluding the unchanged all-zero control left 120 candidates.
All higher-cost paths reused allocation targets frozen from the 50-bps signal.
Feature coverage was broad: the selected panel covered 82.28% of issuer rows
for acceleration and 84.96% for persistent earnings evidence.

The best combined candidate used a 26-week acceleration age, two earnings
events, 30% acceleration weight, 10% earnings weight, and a five-name buffer.
At 50 bps it produced 102.43% trailing-one-year CAGR, 2.680 Sharpe, -9.14%
drawdown, and 35.24% full CAGR, versus 105.10%, 2.692, -10.08%, and 40.93% for
the frozen control. At 200 bps it returned 90.70% versus 93.20%. The best path
anywhere on the surface reached only 102.66% recent CAGR. No candidate beat
the control recently, only two beat it over the full period, and none improved
both horizons or cleared the surface gates.

Robustness evidence confirmed the rejection. One/two-week feature delays both
returned 103.11%; outer-overlay delays returned 95.14%/99.05%; completed
rolling-window outperformance was only 5.52%; neighborhood joint improvement
was 0%; and 4-week/13-week bootstrap probabilities were 21.26%/11.88%.
Removing Qualys reduced recent CAGR to 93.13%. The feature timestamps were
strictly earlier than every affected decision, so the failure is economic,
not a lookahead artifact.

This construction is closed without further weight tuning. The frozen 105.10%
leader remains unchanged, and no strategy replacement, forward clock, or live
execution was enabled.

References:

- `config/sec_persistent_earnings_acceleration_rank_v1.json`
- `scripts/run_sec_persistent_earnings_acceleration_rank_v1.py`
- `tests/test_sec_persistent_earnings_acceleration_rank_v1.py`
- `evidence/sec_persistent_earnings_acceleration_rank_v1/result.json`
- `evidence/sec_persistent_earnings_acceleration_rank_v1/screening.csv`
- `evidence/sec_persistent_earnings_acceleration_rank_v1/report.md`
- `research_registry/sec_persistent_earnings_acceleration_rank_v1.json`

## Step 136 — Test a breadth/dispersion allocation controller and retain a 112.93% challenger

The next branch stopped changing issuer rankings and instead preserved the
frozen breadth-20 cash-conversion holdings and existing 11-week activation rule.
It asked whether strictly lagged market breadth and cross-sectional dispersion
could scale the cash-conversion sleeve only while that frozen rule was already
active. Signals were built from 576 historical issuer price series. At each
Friday, 13/26-week issuer returns ended at the prior Friday; breadth measured
the positive-return share and dispersion used cross-sectionally winsorized
returns. State thresholds used only earlier 26/52-week observations.

The bounded grid covered two return horizons, two calibration windows, two
state quantiles, five breadth/dispersion regimes, and five low/high active
allocation pairs, producing 200 controllers. Stock holdings never changed.
The maximum tested active sleeve weight was 80%; the promotion gate limited
portfolio-level single-stock exposure to 8% and annual controller turnover to
8x. Fifty candidates cleared the initial recent/full/severe-cost/concentration
surface.

The strongest path used 26-week breadth versus its trailing 26-week 40th
percentile. When the frozen rule was active, it raised the cash-conversion
allocation from 50% to 80% in the high-breadth state. At realistic 50-bps costs
it produced 112.93% trailing-one-year CAGR, 2.806 Sharpe, -9.13% drawdown, and
42.01% full CAGR, versus 105.10%, 2.692, -10.08%, and 40.93% for the incumbent.
It retained 100.00% recent CAGR at 200-bps costs versus 93.20%. Peak total
single-stock exposure was 7.38%, and controller turnover was 4.09x annually.

A confirmation sweep evaluated all 50 headline passers before issuer removal.
None cleared every preliminary robustness gate. For the 112.93% candidate,
one/two-week controller delays both retained 112.93%, while one/two-week outer-
overlay delays returned 101.57%/109.14%. The same-family neighborhood joint-
improvement share was 70%, but the candidate beat the control in only 19.02%
of 163 completed rolling windows. Four-week/13-week block-bootstrap positive-
excess probabilities were 88.40%/79.66%, below the required 95%. Removing
GitLab reduced recent CAGR to 98.86%, so one issuer accounted for more than the
entire measured improvement.

The audit also found that strict floating-point comparisons could turn CSV
round-trip differences near 1e-16 into false rolling wins and nonzero bootstrap
observations. This experiment now applies a 1e-12 economic tie tolerance and
asserts that shortlist statistics reproduce after persistence. Under the
corrected policy, 73 of the headline candidate's 163 rolling windows were ties,
not wins.

The 112.93% path is saved as the strongest return-oriented research challenger,
but it does not replace the frozen 105.10% leader and starts no forward clock.
No live execution was enabled.

References:

- `config/sec_breadth_dispersion_allocation_controller_v1.json`
- `scripts/run_sec_breadth_dispersion_allocation_controller_v1.py`
- `tests/test_sec_breadth_dispersion_allocation_controller_v1.py`
- `evidence/sec_breadth_dispersion_allocation_controller_v1/result.json`
- `evidence/sec_breadth_dispersion_allocation_controller_v1/robust_shortlist.csv`
- `evidence/sec_breadth_dispersion_allocation_controller_v1/report.md`
- `research_registry/sec_breadth_dispersion_allocation_controller_v1.json`

## Step 137 — Falsify generic sleeve caps and persistent controller states

The 112.93% breadth-controller challenger was retested without naming or
special-casing any company. The bounded surface crossed five monthly
cash-sleeve cap levels with one-to-three-week entry/exit confirmation for the
breadth state and one-to-two-week confirmation for the underlying activation
state, producing 180 generic variants. The unchanged specification reproduced
the saved 112.93% path to a 1e-12 tolerance in the pinned research runtime.

No candidate simultaneously preserved at least 110% recent CAGR and beat the
105.10% frozen incumbent after a one-week activation delay. Requiring a second
activation week mostly exchanged the current and delayed outcomes rather than
making them stable. State persistence therefore did not repair the timing
fragility.

The strongest genuinely capped diagnostic used a 1.5x monthly sleeve cap and
two-week breadth-state entry confirmation. It retained 112.37% trailing-one-
year CAGR, 2.802 Sharpe, -9.13% drawdown, and improved full CAGR to 42.28%.
At 200-bps costs it returned 99.46%. Peak portfolio-level single-stock weight
fell from 7.38% to 6.95%, showing that the generic cap worked mechanically.

That lower nominal exposure did not reduce economic dependence. A one-week
outer-overlay delay returned only 101.31%, the strategy beat the incumbent in
20.25% of 163 completed rolling windows, and 4-week/13-week bootstrap
probabilities remained 88.40%/79.66%. Removing GitLab reduced recent CAGR to
98.54%; the single-issuer improvement-share ratio worsened to 190.23%.

The cap/persistence branch is rejected. The frozen 105.10% incumbent and saved
112.93% return challenger remain unchanged. No forward clock, strategy
promotion, or live execution was enabled.

References:

- `config/sec_breadth_controller_cap_persistence_v1.json`
- `scripts/run_sec_breadth_controller_cap_persistence_v1.py`
- `tests/test_sec_breadth_controller_cap_persistence_v1.py`
- `evidence/sec_breadth_controller_cap_persistence_v1/result.json`
- `evidence/sec_breadth_controller_cap_persistence_v1/screening.csv`
- `evidence/sec_breadth_controller_cap_persistence_v1/report.md`
- `research_registry/sec_breadth_controller_cap_persistence_v1.json`

## Step 138 — Reject multi-horizon activation voting

The fragile 11-week activation boundary was replaced with strictly lagged
voting across 8-, 11-, 13-, 16-, and 20-week relative-return signals. Four
diversified lookback families plus the original 11-week rule were crossed with
all feasible vote thresholds and binary, proportional, or confidence-blended
sizing, producing 48 bounded candidates. Holdings and the 26-week breadth
controller were unchanged. The single-11-week control reproduced the saved
112.93% challenger to 1e-12 tolerance.

No candidate preserved at least 110% current CAGR while beating the 105.10%
incumbent under both one- and two-week activation delays. In fact, every
diversified rule retaining at least 110% current CAGR reproduced the original
recent activation pattern: 112.93% current CAGR, 101.57% after a one-week
delay, and 109.14% after two weeks. The nearby horizons agreed during the few
decisive recent weeks, so voting did not diversify the timing risk.

The best worst-current/delay diagnostic was a proportional two-of-three vote
across 8, 11, and 13 weeks. It produced only 105.62% current CAGR, 2.664
Sharpe, -11.20% drawdown, 40.63% full CAGR, and 91.80% at 200-bps costs. Its
one/two-week delayed results were 102.12%/104.37%. It beat the incumbent in
36.20% of completed rolling windows; bootstrap probabilities were
55.24%/62.36%; removing Qualys left 92.26%.

The multi-horizon ensemble branch is rejected. The evidence indicates that
the next timing experiment must use information different from trailing sleeve
relative returns rather than more nearby versions of the same signal. No
strategy promotion, forward clock, or live execution was enabled.

References:

- `config/sec_multi_horizon_activation_ensemble_v1.json`
- `scripts/run_sec_multi_horizon_activation_ensemble_v1.py`
- `tests/test_sec_multi_horizon_activation_ensemble_v1.py`
- `evidence/sec_multi_horizon_activation_ensemble_v1/result.json`
- `evidence/sec_multi_horizon_activation_ensemble_v1/screening.csv`
- `evidence/sec_multi_horizon_activation_ensemble_v1/report.md`
- `research_registry/sec_multi_horizon_activation_ensemble_v1.json`

## Step 139 — Test independent market regimes and retain a 119.33% return spike

The next activation branch stopped using only the cash sleeve's trailing
relative return. It built five strictly lagged market votes from SPY trend,
SPY realized volatility versus its prior median, HYG-versus-LQD credit
strength, VIX contango, and cross-sectional issuer breadth. Fast, balanced,
and slow calibrations were crossed with all one-to-five vote thresholds and
five activation constructions: market-only, confirmation, one/two-week
bridges, and union with the frozen activation rule. This produced 75 bounded
controllers using current frozen ETF and VIX vintages.

No candidate preserved at least 110% recent CAGR while improving both one- and
two-week timing delays, full CAGR, severe-cost performance, and concentration.
The best worst-current/delay diagnostic simply reproduced the 112.93% headline
path and its 101.57%/109.14% delayed results. It also retained the earlier
GitLab and bootstrap failures, so the independent regime information did not
repair the existing challenger.

One return-first result was important enough to audit separately. The fast
unanimous-union rule activated whenever either the frozen rule was active or
all five independent fast regime votes agreed. It reached 119.33% trailing-
one-year CAGR, 3.032 Sharpe, and -8.71% drawdown—the strongest recent-return
diagnostic found in this branch and an improvement over the 112.93% challenger.

The return spike failed validation. Full CAGR was only 39.63%, 200-bps recent
CAGR fell to 86.57%, and a one-week signal delay collapsed recent CAGR to
85.29% even though a two-week delay reached 121.79%. Removing Qualys left
103.97%, below the 105.10% incumbent, and one issuer explained 107.93% of the
measured improvement. Its separate paths, target weights, regime panel, and
issuer-removal evidence were retained for future comparison.

The 119.33% path is saved as the highest recent-return spike diagnostic, not a
replacement. The 112.93% breadth controller remains the stronger overall
return challenger and the 105.10% strategy remains the frozen incumbent. No
forward clock, strategy promotion, or live execution was enabled.

References:

- `config/sec_independent_market_regime_activation_v1.json`
- `scripts/run_sec_independent_market_regime_activation_v1.py`
- `tests/test_sec_independent_market_regime_activation_v1.py`
- `evidence/sec_independent_market_regime_activation_v1/result.json`
- `evidence/sec_independent_market_regime_activation_v1/screening.csv`
- `evidence/sec_independent_market_regime_activation_v1/report.md`
- `evidence/sec_independent_market_regime_activation_v1/return_leader_path__50bps.csv`
- `research_registry/sec_independent_market_regime_activation_v1.json`

## Step 140 — Stabilize the regime increment and retain a 119.22% challenger

The 119.33% fast-regime spike was decomposed against the unchanged 112.93%
breadth-controller base. Only the incremental allocation was modified; the
base target was never delayed, resized, or reselected. The attribution found
sixteen isolated incremental weeks across sixteen episodes. A bounded grid
then crossed 25%/50%/75%/100% increment strength with two-to-four-week equal,
front-loaded, entry-ramp, and exit-decay schedules, plus direct controls. This
produced 52 ticker-agnostic candidates, and the direct 100% control reproduced
the saved 119.33% spike to 1e-12 tolerance.

Six candidates passed the predeclared return, increment-delay, full-period,
severe-cost, and concentration surface gates. The strongest worst-current/
delay result deployed the full increment over four equal weekly tranches. It
produced 119.22% trailing-one-year CAGR, 3.037 Sharpe, -8.71% drawdown, 41.97%
full CAGR, and 102.86% recent CAGR at 200-bps costs. Peak portfolio-level
single-stock exposure remained 7.38%, and annual one-way controller turnover
was 4.87x.

Most importantly, delaying only the new increment by one/two weeks retained
118.96%/118.63% recent CAGR. This repaired the timing failure that reduced the
raw regime spike to 85.29% when the entire strategy was shifted. The test shows
that execution diversification can preserve the profitable addition without
disturbing the established base.

The challenger still failed complete falsification. Because the increment was
active in only sixteen isolated weeks, it beat the 112.93% base in just 9.20%
of 163 completed rolling windows; 4-week/13-week bootstrap probabilities of
positive incremental excess were 63.26%/64.34%. Removing Qualys left 109.17%,
above the frozen 105.10% incumbent but below the 112.93% base. One issuer
therefore explained 159.95% of the incremental improvement.

The four-week tranche path supersedes 112.93% as the strongest saved return-
oriented research challenger, but it does not replace the frozen 105.10%
incumbent, start a forward clock, or enable live execution. Its next required
improvement is generic issuer/cohort diversification, not further timing
tuning.

References:

- `config/sec_regime_increment_tranching_v1.json`
- `scripts/run_sec_regime_increment_tranching_v1.py`
- `tests/test_sec_regime_increment_tranching_v1.py`
- `evidence/sec_regime_increment_tranching_v1/result.json`
- `evidence/sec_regime_increment_tranching_v1/screening.csv`
- `evidence/sec_regime_increment_tranching_v1/increment_episode_attribution.csv`
- `evidence/sec_regime_increment_tranching_v1/report.md`
- `research_registry/sec_regime_increment_tranching_v1.json`

## Step 141 — Reject quarterly-cohort diversification around the 119.22% challenger

The next branch preserved the four-week equal-tranche regime increment and
changed only the quarterly cash-conversion membership construction. Thirteen
ticker-agnostic alternatives covered current top-20/top-25/top-30 cohorts,
five current/prior-quarter blends, and five three-cohort decay schedules. Each
construction rebuilt its own 11-week activation, breadth controller, unanimous
fast-regime increment, and four-week execution path. Issuer removal was run
for every construction and every company it held during the recent window
before diagnostic selection.

The unchanged current top-20 control reproduced the saved 119.22% challenger
to 1e-12 tolerance and was the only surface passer. No non-control construction
simultaneously retained at least 115% recent CAGR, both increment-delay floors,
the full-period floor, severe-cost performance, and concentration limits.

The best issuer-aware non-control diagnostic broadened the current cohort from
20 to 25 stocks. It produced 112.43% recent CAGR, 2.917 Sharpe, -8.71%
drawdown, 41.62% full CAGR, and 96.75% at 200-bps costs. One/two-week delayed
increment results were 111.34%/114.04%, and peak portfolio single-stock weight
fell to 6.01%. Removing Qualys left 108.62%. This reduced the drop from its own
headline result to 3.81 percentage points, but its absolute issuer-removal
floor remained below the top-20 control's 109.17%, while headline return fell
by 6.79 percentage points.

Prior-quarter blending did not solve the problem. The 67% current / 33% prior
blend slightly increased recent CAGR to 119.51% and retained 103.22% at
200-bps costs, but full CAGR fell to 40.00% and removing Qualys collapsed CAGR
to 102.04%. Smaller prior weights also failed the full-period gate and did not
improve the top-20 issuer-removal floor.

The cohort-diversification branch is rejected. The 119.22% four-week-tranched
top-20 path remains the strongest saved return challenger; the 105.10% strategy
remains the frozen incumbent. No forward clock, promotion, or live execution
was enabled.

References:

- `config/sec_cohort_diversified_regime_tranche_v1.json`
- `scripts/run_sec_cohort_diversified_regime_tranche_v1.py`
- `tests/test_sec_cohort_diversified_regime_tranche_v1.py`
- `evidence/sec_cohort_diversified_regime_tranche_v1/result.json`
- `evidence/sec_cohort_diversified_regime_tranche_v1/screening.csv`
- `evidence/sec_cohort_diversified_regime_tranche_v1/leave_one_company_out_summary.csv`
- `evidence/sec_cohort_diversified_regime_tranche_v1/report.md`
- `research_registry/sec_cohort_diversified_regime_tranche_v1.json`

## Step 142 — Diversify only the regime increment across independent sleeves

The 112.93% base target and the four-week equal-tranche execution schedule were
frozen. Only the extra regime allocation was routed among the breadth-20 cash-
conversion sleeve and four independently constructed, point-in-time SEC
families: profitability, balance-sheet quality, shareholder discipline, and
quality acceleration. Twenty-one ticker-agnostic routes covered single-family
25%/50%/75% substitutions, equal-family baskets, and strictly lagged 13/26-week
inverse-volatility baskets. The cash-only control reproduced the saved 119.22%
challenger to 1e-12 tolerance.

The strongest robust diversified route split the increment equally between
cash conversion and shareholder discipline. It produced 119.46% trailing-one-
year CAGR, 3.045 Sharpe, -8.71% drawdown, 41.91% full CAGR, and 102.54% recent
CAGR at 200-bps costs. One/two-week delays of only the increment retained
118.98%/120.45%. Removing either routed sleeve and returning that incremental
capital to the leader left at least 116.17%, above the 112.93% base. The
conservative overlapping-issuer concentration bound remained 7.38%.

The improvement is real but small and not statistically broad. It beat the
119.22% control in 44.17% of completed rolling 26-week windows, while 4/13-week
block-bootstrap probabilities of positive excess were only 57.34%/56.74%.
Full point-in-time company removal improved the worst case from the prior
challenger's 109.17% to 110.70%, but Qualys remained the worst issuer and the
result remained below the 112.93% base. The branch is therefore saved as an
issuer-improved return challenger, not promoted or forwarded, and no live
execution was enabled.

References:

- `config/sec_increment_sleeve_diversification_v1.json`
- `scripts/run_sec_increment_sleeve_diversification_v1.py`
- `tests/test_sec_increment_sleeve_diversification_v1.py`
- `evidence/sec_increment_sleeve_diversification_v1/result.json`
- `evidence/sec_increment_sleeve_diversification_v1/screening.csv`
- `evidence/sec_increment_sleeve_diversification_v1/leave_one_company_out.csv`
- `evidence/sec_increment_sleeve_diversification_v1/report.md`
- `research_registry/sec_increment_sleeve_diversification_v1.json`

## Step 127 — Reproduce and repair the Form 4 dynamic-overlay audit

The Step 126 implementation was independently rerun in the pinned
`po2-yfinance:1.5.2-v1` research container. Its central result reproduced:
the 13-week, 30% executive-or-cluster candidate retained 108.43% trailing-one-
year CAGR, 2.768 Sharpe, -10.08% drawdown, and 41.41% full CAGR, while the
ProFrac leave-one-out case remained 99.27%. The rejection decision therefore
did not change.

The audit found that the original rolling-window statistic counted incomplete
26-week windows as failures and that rolling and bootstrap observations had no
explicit promotion thresholds. The implementation was repaired to discard
incomplete windows, require at least 50% rolling-window outperformance, require
at least 95% positive-excess-return probability under both 4-week and 13-week
block bootstraps, and include those booleans explicitly in the all-gates
decision. It now calculates falsification from the persisted path artifacts,
round-trips their metrics, records SHA-256 hashes, and refuses to run outside
Python 3.12.13, NumPy 2.5.1, and Pandas 3.0.5.

The corrected candidate beat the control in 56.44% of 163 completed rolling
26-week windows, passing that gate. It still failed decisively elsewhere: the
same-family neighborhood pass share was 33.33%, the 4-week bootstrap probability
was 69.52%, the 13-week probability was 86.14%, and removing ProFrac left CAGR
below the control. Step 126 remains rejected, the frozen breadth-20 leader is
unchanged, and no forward clock or live execution was started.

References:

- `config/sec_form4_dynamic_overlay_v1.json`
- `scripts/run_sec_form4_dynamic_overlay_v1.py`
- `evidence/sec_form4_dynamic_overlay_v1/result.json`
- `evidence/sec_form4_dynamic_overlay_v1/report.md`
- `research_registry/sec_form4_dynamic_overlay_v1.json`

## Step 147 — Preserve the 124.20% diagnostic and open a broad SEC universe

The sector-aware signal ensemble from Step 146 was added to the Version 2
dashboard as a fourth selectable research strategy. Its saved trailing-52-week
result remains 124.20% CAGR, 3.103 Sharpe, and -8.71% maximum drawdown at 50-bps
turnover costs. The dashboard reconstructs the historical leader and stock-
sleeve allocations, exposes 188 weekly decisions and 909 daily observations,
and keeps the failed promotion evidence visible: 50.0% endpoint outperformance,
57.1% rolling-26-week outperformance, failed bootstrap thresholds, and a
109.32% five-issuer stress. It is explicitly marked not eligible; no live
execution or strategy replacement was enabled.

The next improvement started at the actual universe bottleneck. The historical
SEC filer builder was generalized from a technology/energy-only description to
a declared SIC taxonomy, and a new broad-v2 configuration was frozen. It keeps
technology and energy as first-match carve-outs, then covers the remaining SEC
SIC divisions. Membership still uses only filings accepted before each
quarterly decision, accelerated/large-accelerated filer status, and a 450-day
staleness limit.

Using the 57 already cached SEC Financial Statement Data Set quarters from
2012Q1 through 2026Q1, the first broad vintage contains 174,598 qualifying
submissions, 188,282 decision-membership rows, 6,094 unique historical CIKs,
and 2,889 members at the latest decision. The prior universe contained 1,281
unique CIKs, so the candidate pool expanded by about 4.8x without using today's
index constituents as historical membership. Only 51.09% of historical CIKs
have a current SEC ticker mapping, so price acquisition, historical identity
recovery, delisting outcomes, and explicit missing-company stress tests remain
mandatory before this universe can authorize any return claim.

A readiness audit then reduced that work to explicit queues. From 2023 onward
the broad universe has 3,587 unique CIKs across 14 decisions. Existing validated
prices cover 16.07% of company-decision rows and cached Company Facts cover
17.55%. Of the unique issuers, 485 are already ready in the existing panel, 12
need prices only, 1,997 need both prices and facts, and 1,093 require historical
identity recovery. Strategy testing stays blocked until decision-date coverage
reaches 95%, terminal outcomes are audited, and missing-company adverse tests
pass.

References:

- `dashboard/scripts/build-return-first-dashboard.py`
- `dashboard/src/components/return-first-dashboard.tsx`
- `dashboard/public/return-first-dashboard.json`
- `config/sec_historical_filer_universe_broad_v2.json`
- `scripts/build_sec_historical_filer_universe_v1.py`
- `scripts/audit_sec_broad_universe_readiness_v2.py`
- `evidence/sec_broad_universe_readiness_v2/result.json`
- `data/sec_historical_universe_vintages/20260821T231634Z-sec-historical-filers-broad-v2/manifest.json`

## Step 148 — Start validated broad-universe price and fundamentals batches

The broad-v2 acquisition queue was converted into a bounded, resumable batch
runner. Every requested current SEC ticker is checked against the issuer's
first and last eligible decision dates; a returned history is not accepted
merely because the symbol exists. SEC Company Facts use the existing paced,
cached fetcher and the real project contact. Each batch freezes its inputs,
results, provider/runtime metadata, and keeps strategy testing disabled.

The complete twelve-issuer price-only queue was attempted first. Nine histories
passed their eligible-date intervals. DBD, NINE, and WOLF began too late for
their historical membership and were routed to identity/terminal review rather
than silently backfilled under their current symbols.

Five controlled 40-company batches were then completed from the price-plus-
fundamentals queue. All 200 companies returned interval-valid adjusted price
histories and all 200 returned SEC Company Facts. Across both acquisition
stages, 209 of 212 attempted CIKs added valid histories. The number of fully
ready recent issuers rose from 485 to 694; validated price coverage across
company-decision rows rose from 16.07% to 22.41%, and cached Company Facts
coverage rose from 17.55% to 23.72%. The remaining queue contains 1,797
current-ticker issuers needing both datasets, 1,093 needing identity recovery,
and three needing explicit identity/terminal review. Broad-universe strategy
testing remains unauthorized until the 95% coverage and adverse missing-company
gates are satisfied.

References:

- `scripts/acquire_sec_broad_current_data_batch_v2.py`
- `evidence/sec_broad_universe_readiness_v2/result.json`
- `data/sec_broad_current_data_vintages/20260821T233030Z-broad-v2-acquire_price_only-o0-n12/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T233109Z-broad-v2-acquire_price_and_facts-o0-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T233202Z-broad-v2-acquire_price_and_facts-o40-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T233301Z-broad-v2-acquire_price_and_facts-o80-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T233408Z-broad-v2-acquire_price_and_facts-o120-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T233510Z-broad-v2-acquire_price_and_facts-o160-n40/manifest.json`

## Step 149 — Advance the refreshed broad-data queue by another 200 issuers

After rebuilding the readiness queue, five more fixed 40-company batches were
run against the same frozen queue hash. SEC Company Facts succeeded for all 200
issuers. Adjusted-price histories passed their full eligible-date intervals for
198. XAEIU returned no Yahoo history, while OPI's returned history began after
its earliest eligible decision; both were routed to identity/terminal review.

Cumulatively, 412 unique broad-universe issuers have now been attempted, 407
have interval-valid prices, and all 412 have cached Company Facts. Fully ready
recent issuers increased from 694 to 892. Validated company-decision price
coverage increased from 22.41% to 28.50%, and Company Facts coverage increased
from 23.72% to 29.86%. The current-ticker price-plus-fundamentals queue declined
from 1,797 to 1,597 issuers. Five current-ticker histories are now isolated for
identity/terminal review, and the separate 1,093-issuer historical identity
recovery queue is unchanged. No strategy test, promotion, or live execution was
enabled.

References:

- `evidence/sec_broad_universe_readiness_v2/result.json`
- `data/sec_broad_current_data_vintages/20260821T234641Z-broad-v2-acquire_price_and_facts-o0-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T234744Z-broad-v2-acquire_price_and_facts-o40-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T234831Z-broad-v2-acquire_price_and_facts-o80-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T234913Z-broad-v2-acquire_price_and_facts-o120-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260821T234953Z-broad-v2-acquire_price_and_facts-o160-n40/manifest.json`

## Step 150 — Complete a third 200-issuer broad-data tranche

The next refreshed price-plus-fundamentals queue was frozen by SHA-256 and run
in five more 40-company batches. Company Facts succeeded for all 200 issuers.
Adjusted-price histories passed their complete eligible intervals for 199.
ANG-PD began only on 2025-01-10 despite an earlier eligible membership interval,
so it was isolated for identity/terminal review rather than accepted.

Cumulatively, 612 unique issuers have been attempted without duplication, 606
have interval-valid adjusted prices, and all 612 have cached Company Facts.
Fully ready recent issuers increased from 892 to 1,091. Validated price coverage
across company-decision rows rose from 28.50% to 33.62%; Company Facts coverage
rose from 29.86% to 35.01%. The current-ticker price-plus-fundamentals queue now
contains 1,397 issuers, while six attempted current-ticker histories require
identity/terminal review. No broad strategy test, promotion, or live execution
was enabled.

References:

- `evidence/sec_broad_universe_readiness_v2/result.json`
- `data/sec_broad_current_data_vintages/20260822T002032Z-broad-v2-acquire_price_and_facts-o0-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260822T003029Z-broad-v2-acquire_price_and_facts-o40-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260822T003245Z-broad-v2-acquire_price_and_facts-o80-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260822T003321Z-broad-v2-acquire_price_and_facts-o120-n40/manifest.json`
- `data/sec_broad_current_data_vintages/20260822T003359Z-broad-v2-acquire_price_and_facts-o160-n40/manifest.json`

## Step 151 — Exhaust the current-ticker broad-data queue

The remaining 1,397 current-ticker issuers were processed in seven large,
frozen batches. An explicit-CIK retry mode was added so failures could be
retried without changing the queue or repeating successful companies. In
total, 1,392 histories passed their complete eligible intervals on the first
pass. CWH passed on retry. QVCAQ, STRZ, WW, and BALY remained isolated as
historical identity gaps rather than being accepted with incomplete data. The
current-ticker acquisition queue reached zero; no strategy test or execution
was enabled.

References:

- `scripts/acquire_sec_broad_current_data_batch_v2.py`
- `data/sec_broad_current_data_vintages/`
- `evidence/sec_broad_universe_readiness_v2/result.json`

## Step 152 — Recover historical identities and exhaust free Yahoo coverage

SEC submission records were downloaded in six resumable batches for all 1,093
historical-identity cases. Explicit XBRL trading symbols were recovered for
1,059 issuers. A strict identity audit retained 751 unique single-symbol cases,
quarantined 12 duplicate/ticker-reuse CIKs, and routed 330 multi-symbol or
missing-tag cases to review. All 751 accepted identities then received a Yahoo
history attempt and SEC Company Facts acquisition. Facts succeeded for all 751;
133 price histories passed their full eligible intervals. The other cases were
kept missing, primarily because the companies had already delisted or been
acquired, rather than being silently substituted with a present-day ticker.

References:

- `scripts/recover_sec_broad_historical_symbols_batch_v2.py`
- `scripts/audit_sec_broad_recovered_identity_v2.py`
- `scripts/acquire_sec_broad_recovered_data_batch_v2.py`
- `evidence/sec_broad_recovered_identity_v2/`
- `data/sec_broad_recovered_data_vintages/`

## Step 153 — Add authenticated delisted histories and terminal membership

The remaining recovered-symbol gaps were checked against Tiingo's public
inventory. Of 618 unresolved Yahoo cases, 134 had a matching public Tiingo
symbol and 484 were unsupported by that free inventory. The authenticated
free-tier downloader is capped at 24 candidates per hourly window and never
persists its token. The first two attempts produced 28 validated histories
before the provider rate limit. Six compatible, previously authenticated
histories were then reused under the same strict current audit, bringing the
validated Tiingo total to 34 and avoiding duplicate provider calls.

Separately, SEC filings confirmed 586 merger/acquisition terminations under a
strict form-and-item rule. Removing only decision rows after those confirmed
terminal dates reduced the recent evaluation population to 3,439 unique CIKs.
The latest readiness result contains 2,710 ready issuers, 91.12% Company Facts
coverage, and 83.25% validated price coverage. A combined hourly continuation
now advances at most one Tiingo batch per reset while preserving the frozen
Friday forward-evidence protocol. The broad strategy gate remains closed until
free sources are exhausted and the stated 95% coverage plus missing-company
stress requirements are evaluated; live trading remains disabled.

References:

- `scripts/build_sec_broad_tiingo_queue_v2.py`
- `scripts/acquire_sec_broad_tiingo_batch_v2.py`
- `scripts/audit_sec_broad_tiingo_v2.py`
- `scripts/audit_sec_broad_terminal_membership_v2.py`
- `scripts/audit_sec_broad_universe_readiness_v2.py`
- `evidence/sec_broad_tiingo_queue_v2/`
- `evidence/sec_broad_tiingo_audit_v2/`
- `evidence/sec_broad_terminal_membership_v2/`
- `evidence/sec_broad_universe_readiness_v2/result.json`

## Step 154 — Resolve multi-security issuers without choosing preferreds or units

The unresolved identity set was audited for issuers that report more than one
security. A deterministic primary-common-share rule accepted 272 candidates
and quarantined nine duplicate issuer symbols, preferred securities, and SPAC
units. The first acquisition attempt correctly rejected every price because a
merged date field had been renamed; this exposed a schema error without
allowing any false history into the panel. After correcting the canonical date
fields, the identical frozen queue was rerun. Yahoo histories passed their full
eligible intervals for 209 issuers and SEC Company Facts succeeded for all 272.

A separate conservative current-primary recovery found seven more candidates
among unresolved multi-ticker issuers; six histories and all seven Company Facts
validated. The remaining 49 missing Company Facts were then acquired directly
from SEC, bringing Company Facts coverage to 100%. Price coverage rose from
84.06% to 90.90%, with 2,949 issuers fully ready. No failed or ambiguous symbol
was treated as valid.

References:

- `scripts/audit_sec_broad_multi_symbol_primary_v2.py`
- `scripts/acquire_sec_broad_multi_symbol_primary_batch_v2.py`
- `scripts/build_sec_broad_current_primary_recovery_v2.py`
- `scripts/acquire_sec_broad_missing_companyfacts_v2.py`
- `evidence/sec_broad_multi_symbol_primary_v2/`
- `evidence/sec_broad_current_primary_recovery_v2/`
- `data/sec_broad_multi_symbol_data_vintages/`

## Step 155 — Rebuild delisted-provider eligibility after terminal adjustment

The Tiingo inventory queues were rebuilt against the current SEC-terminal-
adjusted membership intervals rather than the older pre-terminal dates. This
fixed a conservative screening error that had required acquired companies to
provide prices after they ceased to exist. A symmetric ten-calendar-day
decision-date tolerance now handles quarter dates that fall on weekends or
market holidays. The same tolerance is applied by the strict price audit.

The eligible free-provider universe expanded to 399 recovered single-symbol
companies plus 39 multi-symbol supplements. Seventy-eight earlier authenticated
histories were reusable; 123 of 130 audited candidates currently validate, and
all 67 histories ending before their final decision have independent SEC-
confirmed terminal events. There are no unconfirmed early delistings. The
remaining combined provider queue contains 308 unaudited candidates and can
theoretically lift overall price coverage above 96% if all histories validate.

References:

- `scripts/build_sec_broad_tiingo_queue_v2.py`
- `scripts/build_sec_broad_tiingo_multi_symbol_supplement_v2.py`
- `scripts/audit_sec_broad_tiingo_v2.py`
- `evidence/sec_broad_tiingo_queue_v2/`
- `evidence/sec_broad_tiingo_multi_symbol_supplement_v2/`
- `evidence/sec_broad_tiingo_audit_v2/`

## Step 156 — Freeze the broad research authorization gate

A new v2 gate now measures coverage at every quarterly decision, not only as an
overall average. It requires at least 95% price coverage at each decision, at
least 95% Company Facts coverage, completion of every authenticated free-
provider candidate, zero unconfirmed early delistings, and explicit missing-
company policies. Missing selections remain as cash in the base case and are
assigned a total loss in the adverse case. At this checkpoint, Company Facts
and terminal gates pass, but the free-provider queue and price-coverage gates
do not: minimum decision coverage is 85.98%, overall coverage is 90.90%, and
308 candidates remain. Research strategy testing therefore remains blocked and
live trading remains disabled.

The hourly continuation automation now runs one free-tier-safe batch, re-audits
the provider histories and readiness panel, and reruns this gate. It preserves
the separate frozen Friday forward-evidence protocol and will restore the
original weekly schedule when the provider queue is exhausted.

References:

- `config/sec_broad_missing_company_gate_v2.json`
- `scripts/audit_sec_broad_research_gate_v2.py`
- `evidence/sec_broad_research_gate_v2/`

## Step 157 — Make terminal evidence idempotent and recover the 95% path

The terminal audit was expanded with a second strict SEC rule: a Form 25
delisting followed within 45 days by Form 15 deregistration, with no later
10-K, 10-Q, 20-F, or 40-F. This covers public-equity terminations whose closing
8-K does not use the original exact merger item combination, while companies
that continue periodic reporting remain in the universe.

An audit rerun then revealed that the terminal detector was reading its own
already-filtered readiness output, causing fully removed companies to vanish on
subsequent runs. The source was corrected to the immutable broad-v2 quarterly
membership vintage. The regenerated result is stable and contains 634
SEC-confirmed terminal issuers: 556 under the completion-8-K rule and 78 under
the Form-25-plus-Form-15 rule. It removes 1,875 post-terminal decision rows,
leaving 3,431 recent unique CIKs.

At this checkpoint, Company Facts coverage is 100%, current validated price
coverage is 91.15%, and 2,948 issuers are fully ready. The combined Tiingo
inventory has 446 candidates, of which 315 are not yet audited; the downloader
also has seven previously rejected legacy cases scheduled for one controlled
recheck. If every eligible history validates, the minimum quarterly coverage is
95.20% and overall coverage is 96.87%, so the frozen 95%-at-every-decision gate
is now attainable without relaxing it. Research testing remains blocked until
the actual batches prove that outcome.

References:

- `scripts/audit_sec_terminal_membership_v1.py`
- `scripts/audit_sec_broad_terminal_membership_v2.py`
- `evidence/sec_broad_terminal_membership_v2/`
- `evidence/sec_broad_research_gate_v2/`

## Step 158 — Advance the Tiingo queue and fix a plain-Form-25 detection gap

Before running, the current UTC provider window (03:00-04:00Z) was confirmed to
have no prior successful batch; the last success was in the 02:00-03:00Z
window. One 24-candidate batch was run through the authenticated downloader.
Twenty-three candidates validated identity and start coverage; NOVA was
correctly rejected for a name mismatch/ticker-reuse rather than accepted on a
returned symbol history.

Re-running the three required audits then exposed a new
`validated_early_delisting_needs_terminal_audit` case: Cutera Inc (CIK
0001162461, CUTR), whose authenticated history ends 2025-03-12 while its
membership interval runs through 2026-01-01. Re-running the terminal audit
against the immutable broad-v2 vintage did not confirm it, so the research
gate's `terminal_outcome_gate` correctly failed with one unconfirmed early
delisting rather than silently accepting the truncated history.

Investigating the raw SEC submission record found the cause: Cutera filed a
plain Form 25 on 2025-03-20 and a Form 15-12G eleven days later on 2025-03-31,
with no periodic filing after the Form 25 — an exact match for the frozen
"Form 25 followed within 45 days by Form 15" rule. `terminal_filing()` in
`scripts/audit_sec_terminal_membership_v1.py` matched only the exact SEC form
value `25-NSE` (an exchange-filed removal notice) and never matched plain `25`
(an issuer-filed removal notice), which is the same substantive filing under
the same rule. A scan of the 1,093 cached historical-identity submissions
found 127 CIKs with a plain `25` filing, of which 33 have no `25-NSE` filing
at all and were therefore invisible to the old check. The fix adds `25`
alongside `25-NSE` to the notice-form set; no other matching logic changed,
and the completion-8-K rule was untouched. This did not loosen the rule itself
— it only widened form-code recognition to match the rule exactly as
specified, and only decisions with independent SEC filing evidence are now
confirmed terminal.

Re-running the terminal audit against the same immutable vintage raised
SEC-confirmed terminal issuers from 634 to 643, including CUTR under the
`form25_plus_form15_no_later_periodic` rule. Re-running all three audits in
order then cleared the regression: unconfirmed early delistings returned to
zero, `terminal_outcome_gate_passed` returned to true, and no other gate
regressed.

Before this step: 3,431 recent unique CIKs, 2,948 fully ready issuers, 91.15%
validated price coverage (86.15% at the weakest decision), 100% Company Facts
coverage, 634 SEC-confirmed terminal issuers, 131 audited Tiingo candidates
(315 pending), zero unconfirmed early delistings. After this step: 3,430
recent unique CIKs (one issuer's remaining decision rows were fully removed by
the newly confirmed terminal date), 2,971 fully ready issuers, 91.93% validated
price coverage (86.75% at the weakest decision), 100% Company Facts coverage,
643 SEC-confirmed terminal issuers, 155 audited Tiingo candidates (291
pending), zero unconfirmed early delistings. The Company Facts gate and
missing-company policy gate continue to pass; the free-provider-queue gate and
the 95%-at-every-decision price-coverage gate remain the only failures.
Research strategy testing remains unauthorized and live trading remains
disabled.

References:

- `scripts/acquire_sec_broad_tiingo_batch_v2.py`
- `scripts/audit_sec_terminal_membership_v1.py`
- `scripts/audit_sec_broad_terminal_membership_v2.py`
- `scripts/audit_sec_broad_tiingo_v2.py`
- `scripts/audit_sec_broad_universe_readiness_v2.py`
- `scripts/audit_sec_broad_research_gate_v2.py`
- `data/sec_broad_tiingo_runs_v2/20260822T031139Z-sec-broad-tiingo-batch-v2.json`
- `evidence/sec_broad_terminal_membership_v2/`
- `evidence/sec_broad_tiingo_audit_v2/`
- `evidence/sec_broad_universe_readiness_v2/`
- `evidence/sec_broad_research_gate_v2/`

## Step 159 — Prioritize scarce provider calls across the combined queue

The authenticated downloader previously concatenated the recovered-single-
symbol queue ahead of the multi-symbol supplement and then took the first 24
pending issuers. That unintentionally forced every base candidate to run before
any supplement, even when a supplement could fill more quarterly decisions.
The downloader now ranks the deduplicated combined queue by decision rows,
latest eligible decision, and CIK, preserving deterministic reruns while using
each hourly request where it can close the most panel gaps.

At the current checkpoint, the old next batch represented 266 missing
decision-company rows; the globally ranked batch represents 277, a 4.1%
increase in potential coverage contribution for the same 24-candidate limit.
This changes only acquisition order. It does not accept a price, relax any
identity rule, consume a provider request, authorize a strategy test, or enable
live trading. A regression test confirms that a higher-impact supplement is
ranked ahead of a lower-impact base candidate.

References:

- `scripts/acquire_sec_broad_tiingo_batch_v2.py`
- `tests/test_sec_broad_tiingo_batch.py`

## Step 160 — Resolve bankruptcy terminals using economic reporting periods

The next authenticated batch surfaced three histories that ended before their
last nominal membership decision: Lazydays Holdings, Nikola, and Benson Hill.
Their SEC sequences show bankruptcy and equity-termination evidence rather
than missing price observations. The terminal audit was therefore extended
with a narrow bankruptcy rule: an Item 1.03 8-K must have either a Form 25 or
25-NSE within 60 days, or at least two corroborating shutdown/delisting items
from 2.05, 2.06, and 3.01. A company is not classified terminal if it reports
an economic period after that event.

The economic-period condition fixes an important timing bug. A periodic report
filed after bankruptcy may cover a period that ended before bankruptcy; its
late filing date is not evidence that the equity remained economically active.
Nikola, for example, filed a 2024-period 10-K later in 2025. The audit now uses
the SEC `reportDate` for periodic evidence, falling back to filing date only
when the report date is absent. Regression tests cover that delayed-filing
case, a genuine later reporting period, and the stricter no-Form-25 path.

The rule identifies 58 bankruptcy equity terminations in the immutable broad
universe and raises the total SEC-confirmed terminal set to 696. All three new
early-ending histories now validate and the unconfirmed-early-delisting count
falls from three to zero. Post-terminal removal increases overall validated
price coverage to 92.91% and the weakest quarterly decision coverage to
87.61%; 2,992 issuers are fully ready. Company Facts coverage remains 100%.
The terminal and missing-company gates pass, while the frozen research gate
remains closed because 267 free-provider candidates are still pending and the
minimum price coverage is below 95%. No strategy test or live trading was
enabled.

References:

- `scripts/audit_sec_terminal_membership_v1.py`
- `scripts/audit_sec_broad_terminal_membership_v2.py`
- `tests/test_sec_terminal_membership.py`
- `evidence/sec_broad_terminal_membership_v2/`
- `evidence/sec_broad_tiingo_audit_v2/`
- `evidence/sec_broad_universe_readiness_v2/`
- `evidence/sec_broad_research_gate_v2/`

## Step 161 — Freeze eight independent return-improvement workstreams

A new return-improvement program was predeclared before the broad SEC research
gate opened. It covers sector/market-residual momentum, 52-week-high and trend
consistency, point-in-time quality momentum, delayed earnings/Form-4 event
confirmation, generic confidence-based concentration, purged walk-forward ML
ranking, buffered holding/exit rules, and causal allocation across independently
accounted strategy sleeves. Ticker-specific caps are explicitly forbidden.

All eight shared implementations are complete. Their causality contract uses a
full-observation delay for prices, strict pre-decision event cutoffs, sector-
neutral fundamental ranks, purged and embargoed ML folds, generic issuer/sector
caps with excess in explicit cash, and strategy weights computed only from past
returns. Eleven focused tests cover future-data mutation, event timing, feature
signs, cap enforcement, fold separation, out-of-sample ML predictions, holding
state, and allocator causality. Twelve existing compatibility tests also pass.

The frozen tournament guard currently reports
`blocked_broad_research_gate`: 267 authenticated candidates remain and minimum
decision coverage is 87.61%. It wrote no broad performance metric or selection
artifact. The preparation script now refuses to overwrite a differing frozen
configuration, closing a potential silent re-freeze path.

References:

- `config/sec_return_improvement_program_v1.json`
- `src/systematic_trader/sec_return_improvement.py`
- `scripts/prepare_sec_return_improvement_program_v1.py`
- `scripts/run_sec_return_improvement_tournament_v1.py`
- `tests/test_sec_return_improvement.py`
- `tests/test_sec_return_improvement_tournament.py`
- `docs/RETURN_IMPROVEMENT_PROGRAM_V1.md`
- `evidence/sec_return_improvement_program_v1/`
- `evidence/sec_return_improvement_tournament_v1/`

## Step 162 — Reject the first causal strategy allocator without rescue tuning

The predeclared past-strength and dependence-penalized allocator was tested on
the three already selected dashboard strategies, separately from the blocked
broad-universe tournament. The comparison begins only after its mandatory
26-week learning period and charges another 50 bps on allocator turnover.

From 2023-07-14 through 2026-08-07, the allocator returned 21.97% CAGR with
1.254 Sharpe and -16.61% maximum drawdown. Static equal weight returned 40.00%
CAGR with 1.852 Sharpe and -20.40% drawdown; the best standalone common-window
sleeve returned 38.91%. The dynamic allocator therefore fails both relevant
return comparisons and is rejected without a post-result parameter search.
Static equal weight is retained only as a selection-contaminated exploratory
ceiling, not a promoted strategy.

References:

- `scripts/run_strategy_allocator_diagnostic_v1.py`
- `evidence/strategy_allocator_diagnostic_v1/`

## Step 163 — Clear 150% with bounded exposure but keep issuer risk binding

A twelve-rule risk-scaling experiment was frozen around the 124.20% sector-aware
diagnostic. It tested fixed exposure, inverse-volatility scaling, trend
confirmation, a momentum-crash guard, and drawdown throttles. Exposure was
capped at 1.5x; financing was charged at 6% and stressed at 10%; underlying
costs were tested at 50/100/200 bps; and eleven challengers received a
Bonferroni multiple-testing adjustment. Five new causality and safety tests
passed before results were calculated.

Volatility targeting and drawdown throttles reduced both return and Sharpe. The
fixed 1.35x rule was the return leader at the weekly level: 185.77% trailing-
year CAGR, 3.046 Sharpe, -11.82% drawdown, 56.22% full CAGR, and 153.49% under
the severe cost/financing case. Fixed 1.25x returned 166.89% with 3.059 Sharpe
and -10.94% drawdown. Both passed every overlay-level gate, but neither passed
complete falsification because fixed exposure cannot repair the underlying
strategy's unresolved joint issuer dependence. No promotion or execution was
enabled.

References:

- `config/sec_recent_return_risk_scaling_v1.json`
- `scripts/run_sec_recent_return_risk_scaling_v1.py`
- `tests/test_sec_recent_return_risk_scaling_v1.py`
- `evidence/sec_recent_return_risk_scaling_v1/`

## Step 164 — Reject residual and trend confirmation inside the fundamental ensemble

Nine price-confirmation challengers were frozen before evaluation. They added
10%, 20%, or 30% sector/market-residual momentum, trend quality, or their equal
combination to the fixed fundamental membership scores. The existing breadth,
sector caps, delayed prices, costs, execution delays, endpoint checks, rolling
windows, issuer bundles, and Bonferroni-adjusted bootstrap gate were retained.
Seventeen focused and compatibility tests passed.

No challenger passed. The best recent point, a 10% trend-quality contribution,
reduced recent CAGR from 124.20% to 111.86%, Sharpe from 3.103 to 2.876, full
CAGR from 42.74% to 38.49%, and the worst five-issuer stress to 86.87%. The
entire price-confirmation branch was rejected without changing its lookbacks or
weights after seeing the result.

References:

- `config/sec_price_confirmed_fundamental_ensemble_v1.json`
- `scripts/run_sec_price_confirmed_fundamental_ensemble_v1.py`
- `tests/test_sec_price_confirmed_fundamental_ensemble_v1.py`
- `evidence/sec_price_confirmed_fundamental_ensemble_v1/`

## Step 165 — Replace the weekly 185.77% headline with an exact-daily 174.97% audit

The frozen sector-aware ensemble was reconstructed from its saved stock and
strategy targets on exact daily adjusted closes. Four holdings without
validated daily histories remained cash under the existing base missing-company
rule; no current-ticker substitution or fabricated history was used. The
unlevered daily result was 118.79% trailing-year CAGR, 2.643 Sharpe, and -17.94%
drawdown, establishing that weekly accounting had understated intrawweek risk.

After 6% financing, fixed 1.25x produced 157.93% CAGR, 2.605 Sharpe, and -22.59%
drawdown. Fixed 1.35x produced 174.97% CAGR, 2.594 Sharpe, and -24.43% drawdown.
One- and two-session delays retained roughly 152.5% at 1.25x and 168.7% at
1.35x. The maximum weekly reconciliation difference was 2.77%, inside the
frozen 3% tolerance. Both are preserved as research-only amplifiers; the 1.25x
path is the better risk trade-off and the 1.35x path is the return leader.
Neither is promoted because the source strategy's joint issuer test remains
failed. Live trading remains disabled.

References:

- `config/sec_sector_ensemble_daily_risk_scaling_audit_v1.json`
- `scripts/run_sec_sector_ensemble_daily_risk_scaling_audit_v1.py`
- `tests/test_sec_sector_ensemble_daily_risk_scaling_audit_v1.py`
- `evidence/sec_sector_ensemble_daily_risk_scaling_audit_v1/`
- `docs/RECENT_RETURN_ALPHA_SEARCH_V1.md`

## Step 166 — Reject forced cross-component issuer separation

A frozen 15-construction experiment limited the overlap between the two
fundamental ranking components from 20 shared issuers down to zero, tested in
both selection orders. The factors, 20-stock component breadth, 50/50 mix,
sector caps, outer controller, costs, and timing were held fixed. Five focused
tests passed, and the unconstrained control reproduced the 124.20% source path
exactly.

No challenger cleared all predeclared gates. The strongest five-issuer
diagnostic, `balance_first_overlap12`, expanded the latest portfolio from 26 to
28 distinct holdings and produced 122.37% recent CAGR, 3.078 Sharpe, -8.71%
drawdown, and 109.21% CAGR after removing the five previously worst issuers.
It missed the 124.20% return gate, the 112.93% issuer-stress gate, temporal
outperformance gates, and the multiple-testing-adjusted bootstrap gate. Tighter
overlap limits generally reduced returns further. The branch is rejected; the
daily leverage audit was not rerun on a weaker foundation, and no strategy was
promoted.

References:

- `config/sec_cross_component_overlap_budget_v1.json`
- `scripts/run_sec_cross_component_overlap_budget_v1.py`
- `tests/test_sec_cross_component_overlap_budget_v1.py`
- `evidence/sec_cross_component_overlap_budget_v1/`

## Step 167 — Advance the independent broad-universe gate by 24 issuers

At the next eligible hourly free-provider window, one bounded 24-candidate
Tiingo batch was acquired. All 24 histories passed issuer-identity and required
start-date validation; no rate-limit response occurred and the credential was
used transiently without persistence. The broad audits were then regenerated
inside the pinned research runtime.

Validated candidates increased from 191 to 215 and validated decision keys
from 2,004 to 2,251. Overall price coverage rose from 93.5724% to 94.1854%,
while minimum decision-date coverage rose from 88.3853% to 89.1289%. The
pending free-provider queue fell from 243 to 219. Company-facts,
missing-company-policy, and terminal-outcome gates pass, with zero unconfirmed
early delistings; the price and queue gates remain closed. Consequently, the
frozen broad-universe fundamental/ML tournament was not run and live trading
remains disabled. All eight refreshed audit artifact hashes verified.

## Step 168 — Add a no-performance tournament readiness preflight

The next independent-alpha stage was audited without loading a broad price
panel or calculating any strategy return. A deterministic preflight now checks
the frozen protocol hash, all nine required signal/portfolio primitives, and
the eight upstream gate, readiness, and Tiingo evidence hashes. Thirteen
focused and compatibility tests passed in the pinned runtime.

The frozen protocol, signal primitives, and every upstream artifact hash pass.
Tournament execution remains correctly blocked because the research gate is
closed and the broad-panel manifest does not yet exist. The next dependency is
therefore explicit: after the coverage gate opens, materialize a hash-verified
broad research panel, then run the frozen eight-family evaluator. The preflight
contains no performance engine and cannot enable promotion or live trading.

References:

- `scripts/audit_sec_return_tournament_readiness_v1.py`
- `tests/test_sec_return_tournament_readiness_v1.py`
- `evidence/sec_return_tournament_readiness_v1/`

## Step 169 — Complete and seal an eight-family synthetic tournament rehearsal

The broad-tournament execution path was rehearsed end to end without reading
incomplete real-universe returns. A deterministic fixture generated 260 weekly
observations for 48 fictional issuers and 15 quarterly point-in-time decisions
containing 720 issuer-decision rows. The schema rejects late-arriving features,
duplicate keys, and a target horizon longer than the decision interval.

All eight frozen workstream shapes executed: residual momentum, trend quality,
quality momentum, event conditioning, adaptive concentration, nested
walk-forward ML, buffered holding/exits, and the causal sleeve allocator. The
rehearsal applied 50/100/200-bps costs, zero/one/two-week delays, adverse missing
prices, issuer and sector dependence checks, rolling 26/52-week comparisons,
and 4/13-week block bootstraps. A future-target mutation test confirmed that
outer test labels cannot change ML predictions. Twenty-one tests passed.

The configuration, point-in-time schema, engine, runner, and tests were sealed
by SHA-256 and the seal independently reverified. Synthetic performance has no
investment meaning, no real broad return was calculated, and neither promotion
nor live execution was authorized. Once the independent data gate opens, the
next step is to materialize the real panel under this contract and freeze its
source manifest before running the real tournament.

References:

- `config/sec_return_tournament_synthetic_rehearsal_v1.json`
- `schemas/sec_broad_research_panel_v1.schema.json`
- `src/systematic_trader/sec_tournament_rehearsal.py`
- `scripts/run_sec_return_tournament_synthetic_rehearsal_v1.py`
- `scripts/seal_sec_return_tournament_rehearsal_v1.py`
- `tests/test_sec_tournament_rehearsal.py`
- `docs/SEC_TOURNAMENT_REHEARSAL_V1.md`
- `evidence/sec_return_tournament_synthetic_rehearsal_v1/`

## Step 170 — Build and pre-result seal the guarded real tournament

The synthetic rehearsal was converted into a separate real-data v2 contract
without modifying its sealed v1 files. The real schema corrects the synthetic
assumption that every issuer has a price: unavailable histories remain explicit
nulls governed by the frozen cash base case and total-loss adverse case.
Decision, feature-availability, execution, and label-end timestamps are all
preserved, and execution is delayed at least one full week.

A gate-locked materializer now requires a hash-verified causal feature, weekly
price, and frozen-benchmark input package before it can write the broad panel.
The final runner additionally verifies the frozen protocol, panel manifest, and
an eleven-file pre-result execution seal. It evaluates every family against
both benchmarks with true trailing-52-week and full-period metrics. The
strategy allocator now inherits the same cost, timing, missing-price, issuer,
and sector stresses as its constituent sleeves rather than receiving neutral
placeholders.

Twenty-eight fixture and compatibility tests passed. Future-price changes did
not alter completed labels, late features were rejected, missing prices retained
their explicit policy, all eight workstreams executed, and the four-stage guard
order was verified. The materializer and tournament runner both remain blocked
at the closed research gate, so no real panel or performance result was written.
The execution seal was created before results and reverified independently.

References:

- `schemas/sec_broad_research_panel_v2.schema.json`
- `src/systematic_trader/sec_broad_panel_v2.py`
- `src/systematic_trader/sec_real_tournament_v2.py`
- `scripts/materialize_sec_broad_research_panel_v2.py`
- `scripts/run_sec_return_improvement_tournament_v2.py`
- `scripts/seal_sec_return_improvement_tournament_v2.py`
- `tests/test_sec_broad_panel_and_tournament_v2.py`
- `docs/SEC_REAL_TOURNAMENT_V2.md`
- `evidence/sec_return_improvement_tournament_v2/execution_seal.json`

## Step 171 — Complete the broad data gate without lowering it

The completed 446-candidate Tiingo queue still missed the frozen 95% minimum
decision-date threshold by two rows and had one unresolved Li-Cycle endpoint.
Two generic identity false negatives were corrected: `PC TEL` versus `PCTEL`
and `AARON'S` versus `Aarons (The)`. Both had 0.909 normalized similarity; the
new rule accepts only no-overlap similarities of at least 0.90 and retains the
existing recycled-ticker rejection tests.

Li-Cycle's SEC record confirmed NYSE suspension, Form 25 delisting, OTC
transition, and bankruptcy/restructuring within one quarter. The generic
bankruptcy-delisting corroboration window was extended to one calendar quarter
with a boundary test rejecting older unrelated delistings. The full terminal
and Tiingo audits were parallelized without changing sorted deterministic
outputs.

The refreshed gate passed at 95.0071% minimum decision-date price coverage,
96.9219% overall price coverage, 100% Company Facts coverage, 446/446 provider
candidates audited, zero pending candidates, and zero unresolved early
delistings. Missing selections remain cash in the base case and total losses in
the adverse case. Authorization is research-only; live trading remains off.

## Step 172 — Materialize and run the sealed real tournament

A causal source adapter assembled 40,284 issuer-decision feature rows across 14
decisions, 3,253 identity-keyed adjusted-price histories, and 7,609 hashed SEC,
Yahoo, Tiingo, membership, and gate source records. Feature availability was
97.83% for sector-neutral quality momentum, 82.09% for residual momentum,
67.96% for trend quality, and explicit for every event row. Execution remains
one full week after each decision and 13-week ML labels are sector-relative.

The gate-locked materializer independently verified all input hashes and wrote
the real panel without evaluating performance. Two real-data compatibility
defects then caused safe pre-result aborts: a buffered incumbent with a missing
score had no auditable rank, and serialized timestamps had mismatched merge
types. Both were fixed generically, covered by regression tests, and recorded
as pre-result repairs. No `final_result.json` existed during either repair.
Seventeen focused tests passed and the 12-file execution seal reverified.

The one-shot tournament then evaluated all eight families against both frozen
benchmarks. No family qualified. Residual momentum led the rejected set at
101.20% trailing-52-week CAGR, 2.323 Sharpe, and -18.54% drawdown after 50 bps;
it beat the ETF incumbent but trailed the SEC cash-conversion control's 109.90%
recent CAGR and failed familywise bootstrap evidence. The ML family lost 19.18%
recently with a -42.64% drawdown. No winner, replacement, or live execution was
authorized.

## Step 173 — Validate a fixed residual-momentum sleeve hypothesis

Because residual momentum had only 0.081 full-return correlation to the SEC
cash control, an explicitly post-selection diagnostic froze a 20% residual / 80%
control sleeve. The unlevered blend produced 110.65% recent CAGR, 3.116 Sharpe,
and -11.12% drawdown versus 109.90%, 2.728, and -10.67% for the control. Full
CAGR improved from 37.54% to 39.41%, full Sharpe from 1.531 to 1.831, and full
drawdown from -23.26% to -18.69%. One- and two-week delay recent CAGRs remained
108.35% and 109.65%; 200-bps recent CAGR was 98.02%.

The 1.25x research stress reached 147.98% recent CAGR, 3.076 Sharpe, and -13.87%
drawdown at 5% financing, and 146.16%, 3.052, and -13.95% at 8% financing.
However, raw 4/13-week block-bootstrap probabilities were only 61.26% and
62.26%, becoming zero after the eight-family correction. The sleeve passes all
economic gates but fails the multiplicity gate. It is therefore the strongest
new frozen forward candidate, not a promoted strategy; the 20% weight was
chosen after observing this same sample.

References:

- `scripts/build_sec_broad_panel_inputs_v2.py`
- `data/sec_broad_panel_inputs_v2/manifest.json`
- `data/sec_broad_research_panel_v2/manifest.json`
- `evidence/sec_return_improvement_tournament_v2/final_result.json`
- `config/sec_residual_controlled_sleeve_v1.json`
- `scripts/run_sec_residual_controlled_sleeve_v1.py`
- `evidence/sec_residual_controlled_sleeve_v1/result.json`

## Step 174 — Freeze the residual controlled sleeve for untouched forward evidence

The exact 80% SEC cash-conversion control / 20% residual-momentum candidate was
frozen as a new forward-only protocol after all historical information through
August 21, 2026 had already been observed. The first eligible decision is
August 28, the first eligible realization is September 4, and no historical
week advances the new 0/52 clock. The unlevered portfolio and the 1.25x paths at
both 5% and 8% financing are tracked in parallel; none is promoted or executable.

A dedicated recorder now accepts only hashed, immutable decision and
realization packets inside their Friday 21:00 UTC snapshot windows. It validates
point-in-time source cutoffs and manifest hashes, saves control and residual
holdings, calculates turnover and 50-bps costs, derives security-level sleeve
returns, and writes separate append-only hash chains. Missing prices fail
closed. Duplicate, late, changed, out-of-order, pre-boundary, and backfilled
records are rejected. The first decision conservatively assumes a full
transition from cash rather than importing a favorable pre-freeze turnover
anchor.

Nine forward-recorder and shared-ledger tests passed, including weekly-window
boundaries, exact 80/20 and 1.25x arithmetic, hashed source packets, conservative
first-week costs, duplicate rejection, pre-freeze rejection, and tamper
detection. The initialized status is 0/52, with execution and live trading off.

References:

- `config/forward/sec_residual_controlled_sleeve_forward_v1.json`
- `scripts/record_sec_residual_controlled_sleeve_forward_v1.py`
- `tests/test_sec_residual_forward_recorder_v1.py`
- `docs/SEC_RESIDUAL_FORWARD_PROTOCOL_V1.md`
- `evidence/forward_sec_residual_controlled_sleeve_v1/`

## Step 175 — Test and reject the independent-sleeve return accelerator

A sealed 378-candidate tournament tested residual momentum, trend quality,
quality momentum, and delayed filing/event conditioning as a causal accelerator
around the SEC cash-conversion control. The rules were frozen before reading
performance. They used lagged 13/26/52-week selection, one to three active
sleeves, 10%-40% alpha allocations, volatility targets, a 1.5x maximum exposure,
50/100/200-bps costs, one/two-week delays, 8% financing, issuer influence, block
bootstrap, and correction for all trials. Chronology was split into 84
development, 52 validation, and one 52-week locked block.

The run also found an endpoint mismatch in the prior 80/20 diagnostic: the
control ended August 7 while residual data continued through August 21, and the
two missing control returns had been filled with zero. All new comparisons
truncate to the August 7 common endpoint. The corrected trailing-52-week 1.25x
incumbent returned 150.86% at 5% financing and 149.01% at the conservative 8%
assumption, with Sharpe 3.120/3.096 and drawdown -13.87%/-13.95%.

The validation-selected accelerator returned 111.19% in the locked block with
3.143 Sharpe and -11.12% drawdown. It survived 200-bps costs at 91.42% and
one/two-week delays at 105.86%/102.33%, but trailed the corrected benchmark by
37.83 percentage points and had zero familywise bootstrap support. The new
allocator is rejected. The corrected incumbent is retained as research-only;
its 0/52 forward protocol was not changed and live trading remains disabled.

References:

- `config/sec_independent_sleeve_return_accelerator_v1.json`
- `scripts/run_sec_independent_sleeve_return_accelerator_v1.py`
- `scripts/audit_sec_residual_common_endpoint_v1.py`
- `tests/test_sec_independent_sleeve_return_accelerator_v1.py`
- `docs/SEC_INDEPENDENT_SLEEVE_RETURN_ACCELERATOR_V1.md`
- `evidence/sec_independent_sleeve_return_accelerator_v1/`

## Step 176 — Publish the streamlined multi-strategy research dashboard

The locally developed dashboard redesign was consolidated into a dark-mode
Next.js interface with overview, performance, rebalances, methodology,
guardrails, and activity views. It now exposes five saved research strategies,
day-level calendar returns, bone-white rebalance markers, before-and-after
holding changes, adjustable starting-capital and date scenarios, and historical
price charts that stop at the selected calendar date.

The corrected common-endpoint residual-controlled candidate is the default
research view. Its displayed trailing-52-week figures reconcile to the sealed
weekly evidence: 150.86% CAGR, 3.120 Sharpe, and -13.87% maximum drawdown under
1.25x exposure and an assumed 5% financing rate through August 7, 2026. The
dashboard also states that this result is selection-contaminated, is not
promotion-authorized, and has 0/52 untouched forward weeks. No execution or
live-trading capability was added.

References:

- `dashboard/src/components/return-first-dashboard.tsx`
- `dashboard/scripts/build-return-first-dashboard.py`
- `dashboard/public/return-first-dashboard.json`

## Step 180 — Execute the V1 upgrade backlog and preserve the negative results

The two V1 strategy and upgrade audits were reconciled against the current repository
rather than treated as instructions that could override research controls. The current
registry contains 24 provisional strategy candidates and one portfolio candidate, with
zero final or live-approved strategies. One covariance-portfolio forward observation
has now been recorded; all other inspected forward clocks remain at zero, and no clock
is close to the required 52 weeks.

A mandatory candidate-breadth gate was added. It requires aligned return correlations
and holdings overlap against every surviving peer, reports participation-ratio effective
breadth and each candidate's marginal contribution, and rejects candidates whose
contribution rounds below 0.01 as new independent return sources. An optional
Fundamental Law decomposition keeps IC, breadth, transfer coefficient, theoretical IR,
and realized implementation efficiency explicit. The gate never authorizes promotion.

Two genuinely missing retrospective upgrades were then frozen and run. A two-state
Gaussian hidden Markov scaler, fit on 2005-2015 only and filtered with a one-period lag,
improved locked-period drawdown by 7.53 percentage points at 50 bps but reduced annual
return by 3.14 points, failing the predeclared one-point return-drag tolerance. A true
meta-label model used primary-direction correctness as its label and precision/F1 as its
objective. Precision improved only from 52.37% to 52.67%, F1 fell from 0.687 to 0.680,
and a shuffled-label control reached 53.20% precision. It failed before portfolio
pass-through, so no return backtest was allowed. Both upgrades are rejected.

The remaining V1 items were found to be either completed later or externally data-
blocked. Point-in-time cross-sectional value was already completed and rejected in
Steps 118-123. Fractional Kelly, inverse-volatility, covariance/rank sizing, issuer and
sector caps, and later sizing/exposure tournaments were also already tested; the latest
22- and 96-candidate programs had zero historical gate passers. The Indonesia/IDX80
international program is rejected or inconclusive because local inactive/delisted
history, benchmark, cost, and forward gates remain open.

Hull 11e sections 10.6-10.8, 19.6, 19.8, 19.10-19.11, and 20.5 were checked before
adding derivatives contracts. Futures research now requires explicit contract identity,
expiration, bid/ask, multiplier, fees, initial/maintenance margin, and both legs of a
roll. Options research requires quote time, exercise style, bid/ask, implied volatility,
Greeks, margin, assignment fees, explicit tail scenarios, and a maximum-weekly-loss
budget. No derivatives performance was calculated because the required point-in-time
chains, surfaces, execution, margin, and roll histories do not exist locally. Live
trading remains disabled.

References:

- `config/candidate_breadth_gate_v1.json`
- `scripts/run_candidate_breadth_gate_v1.py`
- `evidence/formal_markov_regime_scaling_v1/`
- `evidence/true_meta_labeling_v1/`
- `config/derivatives_breadth_program_v1.json`
- `docs/UPGRADE_EXECUTION_AUDIT_V2.md`
- `research_registry/upgrade_execution_audit_v2.json`

## Step 181 — Compare every dashboard strategy in a frozen survival laboratory

A common historical-survival battery was frozen and applied to all six saved
dashboard strategies using their native weekly records. Ten thousand 52-week
moving-block bootstrap paths were generated with 4- and 13-week blocks. The
same study also tested rolling-year failure, doubled trading costs, an extra
300 basis points of financing, 25% positive-signal decay, a forced -20% week,
displayed holding concentration, original research-gate status, and untouched
forward evidence.

Dynamic Breadth-20, the sector-aware ensemble, the residual-controlled 1.25x
leader, and the fragile 1.35x ceiling each scored 75/100 under the modeled
historical battery. Growth / Micron scored 55 and the ETF incumbent scored 40.
The 1.25x leader's 13-week block bootstrap produced 94.62% profitable paths,
a -0.83% 5th-percentile annual return, and a 1.59% probability of crossing a
30% drawdown. The Micron-led path was materially weaker at 81.14%, -19.21%,
and 21.91%, respectively.

No strategy is labeled proven or live-ready. All retain zero completed forward
weeks in this snapshot, and executable liquidity, market impact, financing,
tax, and model-drift evidence remains incomplete. A dedicated Survival Lab page
was added to the Next.js dashboard to keep modeled stress survival, original
research validation, and live-forward proof visibly separate.

References:

- `config/dashboard_strategy_survival_lab_v2.json`
- `scripts/run_dashboard_strategy_survival_lab_v2.py`
- `tests/test_dashboard_strategy_survival_lab_v2.py`
- `docs/DASHBOARD_STRATEGY_SURVIVAL_LAB_V2.md`
- `evidence/dashboard_strategy_survival_lab_v2/`
- `dashboard/src/app/survival/page.tsx`
- `dashboard/public/strategy-survival.json`

## Step 182 — Kill the cross-strategy residual allocator at the holdings level

The 158.52% / 3.73-Sharpe / -10.87% blend that motivated this step was a post-hoc
diagnostic: 80% of the 150.86% leader plus 20% of the fragile sector sleeve, noticed
after inspecting results, on the strength of a 0.079 recent return correlation. A
sealed, unlevered cross-strategy residual allocator was built to test it properly.

A v1 of this experiment already existed and had already run. Re-reading it found five
defects, four of which manufactured passing gates. It never inspected holdings. It
charged reallocation cost only on the change in the allocator weight, so the static 20%
rule it selected had zero turnover inside the locked window and its doubled-cost stress
was arithmetically identical to the headline. Both delay stresses shifted a constant and
were likewise no-ops. The sleeve shock landed at the midpoint of the full frame, inside
the development period, and never touched the locked window. There was no missing-stock
stress and no reconciliation. V1's `double_cost_improvement` and `delay_improvement`
gates both read true; neither test did anything.

V2 reconciles first and fails closed. Each source is checked against its own daily
records, its published wealth path, and the net-equals-gross-minus-cost identity before
any performance number is computed; both passed at machine precision, worst error
1.5e-16. The de-levered base reproduces the published cash-only trailing figure of
112.6039000930664% to an absolute error of exactly zero, so the unlevering is verified
against an independent published number rather than asserted.

Reconciliation then surfaced a cost asymmetry that invalidates every prior comparison
between these two strategies. The sector sleeve is published with 32.29 units of
cumulative turnover and zero charged trading cost, while the base pays a full 50 bps and
carries 13.05 points of cumulative cost drag. Charging the sleeve 50 bps on its own
turnover costs it roughly 8 points of trailing CAGR and 6.7 points of full-history CAGR.
The 158.52% blend was a cost-charged strategy measured against a cost-free one.

V2 rebuilds the combined book at the holdings level, charges its real turnover once, and
adds issuer, sector and ETF look-through concentration controls. Over half of each
strategy's weight sits in exchange traded products, so a frozen map resolves held symbols
to SIC-derived sectors and expands funds through a declared look-through table. Selection
uses only lagged residual momentum, beta, correlation and residual information ratio,
over purged expanding walk-forward folds with a four-week embargo. Twenty-three tests
pass, including two prefix-invariance tests confirming that perturbing future data leaves
historical signals and allocator paths unchanged, and three reconciliation tests that
detect a tampered daily record, a broken cost identity, and a zero-cost source.

Unlevered and cost-symmetric, the selected static 20% sleeve returned 110.36% against the
base's 109.22% over the 52 weeks ending August 7, 2026, with Sharpe 3.640 against 3.097
and drawdown -8.97% against -11.31%. The improvement is 1.13 percentage points, not the
7.66 points claimed. Every non-vacuous stress is larger than the edge: doubled cost
-6.05 points, 25% signal decay -8.99, a -20% sleeve week -7.00, and removing the single
largest sleeve name each week -10.50. Removing XLK alone costs 10.73 points against the
base; SLV, MU, PLTR and VICR each independently flip the result negative, and only five
of the ten largest sleeve names leave any improvement standing. Micron appearing again is
the same chronic failure mode. Paired moving-block bootstrap probability of outperformance
was 0.4684 at four-week blocks and 0.3968 at thirteen, against a 0.9999 familywise
threshold after correcting for 402 cumulative trials. The two delay stresses remain
genuine no-ops for a static rule; unlike v1 the run flags them as vacuous, so they carry
no evidential weight.

The decisive finding is at the holdings level. The 0.079 return correlation is reproduced
exactly and is misleading. Mean weight overlap between the two books is 75.81% over the
recent window and 75.45% over full history; they share 25 of the sleeve's 29 final-week
names, including MU, GTLB, QLYS, PANW, PLTR, ZS, XLK and XLE. The returns-based effective
breadth statistic reports 1.99 independent strategies, close to the maximum for two
series, while the holdings say the books are three-quarters identical. Where they
disagree the holdings are ground truth, and a returns-only breadth measure is fooled by
re-weighting. Under Grinold and Kahn this cannot raise breadth; it is the ≈1.15 ceiling
of Batch 03 reached by another route.

Concentration produced a second finding about the incumbent rather than the sleeve. After
look-through the 150.86% leader is an 81.6% technology book with 48.0% in a single fund at
the 95th percentile of the locked window, breaching two of four conventional caps on its
own. The sleeve worsens all four measures, and its single-fund increase of 2.40 points
exceeds the declared 2-point tolerance. Every cap from 5% to 20% raises every
concentration measure monotonically, so no allocation size diversifies the book. A
sensitivity check tilting each broad fund a further 15 points into its largest sector
leaves the verdict unchanged.

After v2's result was written, a defect was found in its concentration inputs. The v1
map's hand-written fund list omitted SLV, XLB, XLP, XLV, XLY, VTV, VWO, BIL and PDBC, and
unlisted funds fell through to the issuer bucket. SLV reaches 21.5% and 26.8% de-levered
weight in the two sources, and because the iShares Silver Trust is itself an SEC filer
with a finance-division SIC code, v2 counted it twice as a company; v2's headline
"max single issuer 21.5%" was SLV. V2 was a completed one-shot and was not overwritten. A
corrected map was built and the identical experiment was sealed and rerun as v3. Base max
single issuer falls from 21.5% to 7.4% and the absolute issuer gate flips to pass; total
fund weight rises from 57.3% to 58.8%; single-fund and sector figures are unchanged.
Returns, stresses, breadth and bootstrap are bit-identical across the two runs, which is
the intended proof that the map feeds risk measurement only and never the return path.
Nine of thirteen gates fail in both.

Financing was never evaluated. The runner computes no levered path unless the unlevered
book clears every gate, and it did not. The allocator is rejected. No forward clock was
started, no candidate was promoted, and live trading remains disabled. A separate
unrepaired artifact is recorded: `sec-growth-survivorship-aware-v1` carries a holding
whose symbol is the literal string `PRICES` at up to 40% weight across 54 weeks. The new
map classifies it as a data artifact so it cannot be absorbed into an issuer or sector
bucket, but the export defect belongs to that strategy.

The conclusion is that no allocator over these two books can help. Any blend of them is a
re-weighting of one book. Breadth requires a return source that does not hold MU, XLK and
PANW.

References:

- `config/sec_cross_strategy_residual_allocator_v2.json`
- `config/sec_cross_strategy_residual_allocator_v3.json`
- `scripts/build_cross_strategy_concentration_map_v1.py`
- `scripts/build_cross_strategy_concentration_map_v2.py`
- `scripts/seal_sec_cross_strategy_residual_allocator_v2.py`
- `scripts/seal_sec_cross_strategy_residual_allocator_v3.py`
- `scripts/run_sec_cross_strategy_residual_allocator_v2.py`
- `scripts/run_sec_cross_strategy_residual_allocator_v3.py`
- `tests/test_sec_cross_strategy_residual_allocator_v2.py`
- `docs/SEC_CROSS_STRATEGY_RESIDUAL_ALLOCATOR_V2.md`
- `research_registry/sec_cross_strategy_residual_allocator_v3.json`
- `evidence/sec_cross_strategy_residual_allocator_v2/`
- `evidence/sec_cross_strategy_residual_allocator_v3/`

## Step 183 — Expose the survival evidence per strategy, and refuse the forward shortcut

The dashboard's Survival Lab summarised ten thousand bootstrap paths per strategy
into eight numbers. This step exports the underlying distributions and rebuilds the
page so each strategy can be opened and inspected on its own.

A v3 of the survival laboratory was sealed and run. It changes no methodology: the
same seed, the same 10,000 moving-block simulations, the same 4- and 13-week blocks,
and the same seven scoring gates. A regression check confirms every summary number is
bit-identical to v2. What is new is what the run keeps: a 44-bin histogram of terminal
returns, a 44-bin histogram of the deepest drawdown per path, a week-by-week
percentile fan of simulated wealth at the 5th, 25th, 50th, 75th and 95th percentiles,
twenty-four deterministically sampled individual paths, extended quantiles, and the
realised weekly return, wealth and drawdown series for each strategy. The payload grew
from 30 KB to 253 KB. Nine tests pass, covering histogram coverage, percentile
monotonicity across the fan, deterministic sampling, the distributions-only-on-request
switch, and a JSON NaN guard.

The Survival Lab page was rebuilt as its own component. A strategy picker opens any of
the six saved strategies; four tabs then expose the Monte Carlo fan and both outcome
distributions, the realised equity and drawdown path with adjustable starting capital,
the stress battery as a ranked comparison against the trailing-year baseline, and the
seven scoring gates with the all-strategy table. Block length is switchable between 4
and 13 weeks, sample paths can be toggled, and every chart carries a detail tooltip.

Two requests were not implemented, for the same reason in different forms.

The 150.86% blend cannot be extended to the current date without regenerating a leg.
Its residual sleeve already runs through August 21, 2026 and returned +0.61% and
-0.44% in the two weeks past the published endpoint. The cash-conversion control stops
at August 7, so the common endpoint is August 7 and those two weeks are excluded by the
Step 175 audit rather than missing. Extending the blend requires re-running the control
for two decision dates, which changes a file pinned by the forward protocol and creates
a new protocol version. It is also worth stating that the extension would lower the
headline: both new weeks are far weaker than the +5.51% and +4.99% weeks they would
push out of the trailing window.

Those two weeks cannot count as forward evidence at all. The protocol was frozen on
August 24, 2026 with historical data through August 21, a first eligible decision on
August 28, and a first eligible realization on September 4. Today is August 24. Every
week now available predates the freeze and was already observed. The protocol's own
missed-snapshot policy forbids backfilling a window from a later vintage, and its
selection status records that historical results never advance the clock. The forward
count stays at 0 of 52. Counting pre-freeze weeks as forward evidence would destroy the
only untouched test this candidate has left.

No strategy was promoted, no pinned file was modified, and live trading remains
disabled.

References:

- `config/dashboard_strategy_survival_lab_v3.json`
- `scripts/run_dashboard_strategy_survival_lab_v3.py`
- `scripts/seal_dashboard_strategy_survival_lab_v3.py`
- `tests/test_dashboard_strategy_survival_lab_v3.py`
- `evidence/dashboard_strategy_survival_lab_v3/`
- `dashboard/src/components/survival-lab.tsx`
- `dashboard/public/strategy-survival.json`

## Step 184 — Make every book pure cash, and price the design gate honestly

The concentration gate fails for all six saved strategies. This step asks what it
would actually take to satisfy it, on money the account actually has.

Four caps were declared before measurement: 10% in any single company, 25% in any
single fund, 60% in funds altogether, and 35% in any sector after exchange-traded
look-through. Each book is first reduced to 1.00x, removing all borrowing and all
financing, and the caps are then applied iteratively because a sector cap can bind
after an issuer cap releases weight. Released weight goes to cash and is never
reinvested.

Every strategy satisfies every cap afterwards. The concentration failure is therefore
fixable rather than structural. The cost is the actual finding: between 30% and 50% of
each book has to sit in cash to get there. The residual leader releases a median 29.8%
and the fragile sleeve 41.8%; the ETF incumbent and the Micron-led growth book release a
median 50%. These strategies' returns are substantially a function of the concentration
that fails the gate.

That number is a conservative bound, and the reason matters. Released weight has nowhere
to go inside the dashboard artifact, so it becomes cash. A real implementation would
redistribute into the next-ranked names, which requires re-running each strategy against
the research panel rather than re-weighting its published output.

No capped return series was produced, deliberately. An attempt to reprice the strategies
from their own published holdings and asset prices failed: recomputed weekly gross
returns correlate only 0.25 with the published series, across every tested holdings lag
from -1 to +2, even though cumulative return is close (394% recomputed against 404%
published). Contributions decompose sensibly name by name, weights sum to the stated
gross, and price coverage is complete, so the mismatch is not missing data. Until that
is understood, any capped return derived from this artifact would be fiction, and the
program records risk geometry only.

Two of the six strategies ever used borrowed money; the other four were already 1.00x.
Pure cash is now the default presentation everywhere. For the two levered books the
dashboard states plainly that they benefit heavily from financing and offers a toggle
between the paths: the residual candidate returns 112.60% on pure cash against 150.86%
financed at 1.25x, and the fragile sleeve 114.12% against 168.68% at 1.35x. The ranking
inverts once borrowed money is removed. On pure cash the Micron-led growth book returns
155.72%, ahead of both levered strategies unlevered, though it also carries the weakest
Monte Carlo profile of the six.

A Design gate tab was added showing each constraint before and after caps, the weight
forced to cash, the positions trimmed, and the native exposure. The remaining blocker is
unchanged and cannot be shortened: 52 untouched forward weeks, first eligible
realization September 4, 2026.

No strategy was promoted, no pinned file was modified, and live trading remains disabled.

References:

- `config/unlevered_concentration_caps_v1.json`
- `scripts/run_unlevered_concentration_caps_v1.py`
- `scripts/run_unlevered_financing_comparison_v1.py`
- `evidence/unlevered_concentration_caps_v1/`
- `dashboard/public/concentration-caps.json`

## Step 185 — Measure what each signal is actually worth, using data already on disk

The free half of the upgrade backlog: no vendor feed, no financing, no trading. The
question is whether the panel's four features carry information at all.

Rank information coefficients were computed between each feature and the forward
sector-relative return, one quarterly decision at a time across the fourteen decisions
in the broad research panel, roughly three thousand issuers each. Each feature was then
tested against a permutation null of two thousand label shuffles performed inside each
decision, preserving cross-sectional size and the feature vector.

Three of four features carry real information. Trend quality averages an IC of 0.0665,
residual momentum 0.0571, and quality momentum 0.0285; all three sit outside the
permutation null at p below 0.0001. Residual momentum is the most consistent, positive
in 67% of decisions with the highest IC information ratio at 0.69, and the only feature
whose t-statistic clears 2 at 2.40. Trend quality has the largest average IC but a
weaker t-statistic of 1.85 across only fourteen observations.

Event score is noise. Its average IC is 0.0005, it is positive in 43% of decisions, and
its permutation p-value is 0.929. On this evidence it contributes nothing and should be
dropped from any future ensemble rather than carried along.

A methodological error was caught before publication and is recorded rather than hidden.
The first version of this audit multiplied each IC by the square root of the project's
measured effective breadth of 1.15 and reported the result as an information ratio. That
is wrong. In IR = IC * sqrt(BR), breadth is the number of genuinely independent bets per
year; the 1.15 figure from Batch 03 is the effective number of independent *strategies*,
a different quantity. Multiplying a cross-sectional IC by a cross-strategy breadth
produces a meaningless number. No information ratio is published. Obtaining one would
require an effective-independent-bet count estimated from the residual correlation
structure of the names actually held, which this project has not measured.

Fourteen quarterly observations is a small sample for an IC t-statistic, and the result
is recorded as indicative rather than established. The useful conclusions are narrow and
free: one feature can be dropped outright, and the remaining three have ICs in a normal
range for equity signals, meaning the project's problem has never been signal quality.

No strategy was promoted and live trading remains disabled.

References:

- `config/signal_information_coefficient_audit_v1.json`
- `scripts/run_signal_information_coefficient_audit_v1.py`
- `evidence/signal_information_coefficient_audit_v1/`

## Step 186 — Regime-probe the sector engine, and find the alpha is somewhere else

Five of the six saved strategies begin in 2023 and have never been measured through a
bear market. They cannot be extended backwards: their stock price panel starts
2022-12-02. Their engine can be. Nine SPDR sector ETFs have daily history to
December 1998, so the mechanism those strategies share — multi-horizon
cross-sectional momentum, sector balance, volatility targeting, an execution delay and
costs — was run once, unmodified, over 1,751 weeks from 1993 to 2026.

The engine parameters were copied from the saved sector ensemble's frozen configuration
and nothing was tuned inside the probe. Regime windows were declared before running.

The result is severe. Over the full sample the engine returned 0.32% annually against
SPY's 10.84%, with a Sharpe of 0.09 against 0.69, and a deeper maximum drawdown at
-56.4% against -54.6%. It underperformed the benchmark in six of eight declared regimes,
catastrophically during the post-GFC bull where it returned 41.7% against SPY's 389.1%.

It is genuinely defensive. Average drawdown across the four bear regimes was -27.2%
against SPY's -38.7%, and it beat the benchmark outright during the global financial
crisis by 24.5 points and through the 2022 bear by 9.1 points. It did not help during
the dot-com crash, losing 11.0 points more than the benchmark, and it was flat against
SPY through the COVID crash.

The most useful finding is an accident of the probe. In the 2023-2026 window where the
saved strategies returned between 92% and 175%, this engine returned 34.3% and
underperformed SPY's 111.5%. The mechanism therefore does not reproduce the saved
results at all, which means the probe fails as a proxy for those strategies and cannot
condemn them. What it does establish is where their return actually comes from: not the
sector rotation, which is measurably poor over three decades, but the SEC fundamental
stock selection layered on top of it.

That reframes the untested risk rather than resolving it. The component doing the work
is the stock picking, and the stock picking is exactly the component with only three and
a half years of history and no bear market in it. The regime question is not answered;
it is now correctly located.

Two conclusions are carried forward. Generic sector-momentum rotation should not be
built on again as a return source in this project; thirty-three years say it does not
pay. And any future regime work must target the fundamental selection layer, which
requires historical stock prices the project does not have.

No strategy was promoted and live trading remains disabled.

References:

- `config/sector_mechanism_regime_probe_v1.json`
- `scripts/run_sector_mechanism_regime_probe_v1.py`
- `evidence/sector_mechanism_regime_probe_v1/`

## Step 187 — Redistribute instead of holding cash, and find the caps are unreachable

Step 184 applied concentration caps by releasing every capped position to cash, and
noted that this was a conservative bound: a real implementation would redistribute the
released weight rather than sit on it. This step does the redistribution.

Released weight is now offered proportionally to holdings that are still below their own
issuer, single-fund, total-fund and sector limits, repeatedly, until either all of it is
placed or no headroom remains anywhere. Only genuinely unplaceable weight becomes cash.
No new names are introduced, because choosing what to buy next requires the strategy's
own ranking and cannot be recovered from a holdings snapshot.

Redistribution does what it was supposed to do about cash. Median released weight falls
from between 29.8% and 50% under v1 to between 0% and 10% for four of the six
strategies. The money stays invested.

It also breaks the caps, and that is the finding. Once weight is pushed back into the
names these books already hold, sector exposure after look-through climbs to between
43.0% and 65.0% against a 35% cap, and total fund exposure reaches 83.6% against a 60%
cap. Five of six strategies fail at least two caps under redistribution, where all six
passed when the same weight was dumped to cash.

The two results together say something neither says alone. The concentration in these
strategies is not a weighting problem that better sizing can solve. It is a selection
problem: the set of names each strategy chooses does not contain enough independent
exposure to be spread out. You can satisfy the caps or you can stay invested, and with
this name set you cannot do both.

One exception is instructive. The Micron-led growth book passes every cap under
redistribution, because it holds five single names and no funds at all; capping each at
10% leaves half the book in cash but breaches nothing. Its concentration is honest and
visible, where the fund-heavy books hide theirs inside baskets until look-through
exposes it.

The practical consequence is that fixing the design gate requires re-running each
strategy so that trimmed weight flows into the next-ranked name it already wanted, not
post-processing its published output. That work needs the strategy ranking at each
decision date, which lives in the research panel rather than the dashboard export.

No strategy was promoted and live trading remains disabled.

References:

- `config/unlevered_concentration_caps_v2.json`
- `scripts/run_unlevered_concentration_caps_v2.py`
- `evidence/unlevered_concentration_caps_v2/`

## Step 188 — The signals order the cross-section but cannot separate the tails

Step 185 measured information coefficients and found three of four signals outside a
permutation null at p below 0.0001. That is a statement about ordering the whole
cross-section. It is not the question that decides whether a strategy makes money, which
is whether the names actually bought beat the names actually avoided.

This step measures the top-decile minus bottom-decile forward return per signal, per
quarterly decision, on the same panel.

No signal has a usable spread. Residual momentum is the best at +0.45%, with the top
decile returning 4.50% against the bottom decile's 4.06%, and it beat its own bottom
decile in only six of twelve decisions. Quality momentum is -0.20%, event score -0.59%,
and trend quality is -1.17% despite having the highest measured IC of the four. Three of
four spreads are negative. Top-decile win rates sit between 49.6% and 54.5%.

The tension with Step 185 is real and worth stating plainly rather than reconciling away.
A rank correlation of 0.057 across roughly three thousand names can be statistically
significant while being economically negligible, and the tails, which is where trading
actually happens, are dominated by outliers rather than by the weak monotonic
relationship the IC detects. Both measurements are correct. The IC audit answered a
question that turns out not to be the operative one, and this correction is recorded
against it rather than replacing it.

The distribution explains why. In a single top decile of roughly 270 names, the best
single outcome reached +468% over thirteen weeks and supplied 14.3% of every gain in
that decile. Across all decisions the best single name averages 6-7% of the entire top
decile's positive return. Returns at this horizon are not merely fat-tailed; a handful of
names decide the result whatever the selection rule does.

That reframes this project's chronic single-name problem. Micron supplying 67.63% of the
growth strategy's return was never evidence that the rule found Micron. It is what a
concentrated draw from this distribution looks like when the draw goes well. The same
process produces the opposite outcome with the same probability, and nothing measured
here suggests the selection rule anticipated it.

The constructive reading is that breadth is not a risk-control preference in this
project, it is the only defence available. If single names decide outcomes and the rule
cannot rank them ex ante, then holding more of them is the sole mechanism that converts
a lottery into an expectation. Twenty names is better than five for that reason and not
for tidiness.

Ten to fourteen usable quarterly decisions per signal is a small sample and the result is
indicative rather than established. No strategy was promoted and live trading remains
disabled.

References:

- `config/signal_decile_spread_audit_v1.json`
- `scripts/run_signal_decile_spread_audit_v1.py`
- `evidence/signal_decile_spread_audit_v1/`

## Step 189 — Test the literature, and find the sample rewards volatility, not selection

The question was whether any selection rule on this panel produces a positive
top-minus-bottom decile spread. Twenty-two signals from the asset-pricing literature
were written into a frozen config before anything was computed. Eleven price-based
signals ran; the nine fundamental signals and two of the composites could not be built,
because extracting XBRL facts from 3,567 cached filings is blocked by a per-file-open
penalty on this machine that defeats sequential reads, bulk copying, and thread
parallelism alike. That is an environment limit, not a research result, and the
untested families are named below so the gap is explicit.

Signals were standardised inside SIC sector, ranked weekly across roughly 3,200
issuers, and scored on the forward 13-week return of the top decile minus the bottom
decile over 130 evaluation weeks. Significance used a moving-block bootstrap with a
13-week block, because weekly evaluation of a 13-week forward return produces
overlapping windows and an i.i.d. test would badly overstate confidence.

Three controls establish that the pipeline works. Perfect foresight, using the forward
return as its own signal, produced a 363.9% annualised spread and was positive in 100%
of weeks. Pure noise produced 0.3% and was positive in 51%. Buying high volatility
produced 39.0% and was positive in 68%.

No signal passed. Every one of the eleven has a negative mean spread. Ordered from least
to most negative: six-month momentum at -0.09%, one-month reversal at -0.14%, twelve-one
momentum at -4.85%, the momentum composite at -10.38%, proximity to the 52-week high at
-21.74%, low maximum return at -29.99%, low beta at -31.55%, the defensive composite at
-35.70%, low volatility at -38.97%, and low idiosyncratic volatility at -41.28%. No
signal survived Bonferroni at p below 0.00455, and none was positive in a majority of
weeks.

The pattern in those numbers is the finding. Every classic defensive factor is strongly
negative, which is the same statement as the control: in this sample the stocks that won
were the most volatile, highest-beta, most lottery-like names available. Low volatility,
the most robust defensive anomaly in the literature, was the second worst performing rule
tested.

A follow-up confirms the strategies are on that side of the trade. Weight-weighted
volatility percentiles of actual holdings are 0.717 for the Micron-led growth book, 0.642
for the residual leader, and 0.551 to 0.553 for the three mid-tier strategies, against
0.216 for the ETF incumbent. The incumbent is the only strategy below the panel median
and also the lowest returning at 70.31%. Correlation between volatility tilt and
pure-cash return across the six is 0.855 Pearson, on a sample of six, which is
corroborating rather than conclusive.

Taken with Step 188, the position is now specific rather than vague. The signals cannot
separate the tails, the sector overlay does not pay, and what the sample rewarded was
volatility exposure. A high-volatility tilt is sufficient to explain most of the return
ranking with no stock-selection skill required. That is not an edge; it is a factor
exposure that has been paid handsomely for three and a half years and is the single most
regime-dependent bet available.

Untested and owed: gross profitability, return on assets, accruals, asset growth, cash
conversion measured on this footing, net margin, book to market, earnings yield, low
leverage, and the quality and value composites. Those are the factor families most likely
to behave differently from the momentum and volatility group, and this program cannot
claim to have tested the literature until they run.

No strategy was promoted and live trading remains disabled.

References:

- `config/signal_discovery_program_v1.json`
- `scripts/run_signal_discovery_program_v1.py`
- `scripts/run_volatility_tilt_attribution_v1.py`
- `evidence/signal_discovery_program_v1/`
- `evidence/volatility_tilt_attribution_v1/`

## Step 190 — Price the breadth trade, and find diversification buys return here

Step 188 established two things: single names decide outcomes, and no signal on this
panel ranks them ex ante. If both hold, then holding more names is the only mechanism
available for converting a lottery into an expectation. This step measures the
conversion rate directly.

Equal-weight portfolios of N names were drawn uniformly at random from the 2,748 issuers
with a complete trailing year, four thousand draws at each size, over the 52 weeks ending
August 21, 2026. Selection is random by construction, which is the point: it isolates
breadth with zero skill assumed.

The variance result is the expected one and is dramatic. The gap between the 5th and 95th
percentile outcome falls from 152.3 points at one name to 43.5 points at twenty and 10.4
points at three hundred and twenty, a reduction to 0.07 of the single-name spread. The
probability of losing money falls from 31.6% to 6.3% at twenty names and to zero beyond
forty. The probability of losing more than 20% falls from 16.4% at one name to 3.0% at
five, and to zero at twenty.

The unexpected result is the median. It does not stay flat as diversification theory
usually implies; it rises from 6.7% at one name to 13.1% at five, 16.3% at twenty and
17.8% at three hundred and twenty. The reason is the skew this project keeps running
into. The cross-sectional return distribution has a long right tail, so its mean sits far
above its median. A single-name portfolio typically delivers something near the median.
A wide portfolio delivers something near the mean. Averaging does not sacrifice return
here, it collects the tail that a concentrated book usually misses.

That inverts the usual framing. In this universe diversification is not a cost paid for
safety; it is the mechanism that captures the skew. A randomly chosen twenty-name book
beat a randomly chosen five-name book on median return, on fifth-percentile outcome, and
on both loss probabilities simultaneously, with no selection ability whatsoever.

The direct consequence for the saved strategies is that the five-name growth book is
strictly dominated by breadth it could have had for free. A random five-name portfolio
carries a 23.1% chance of losing money and a 3.0% chance of losing more than a fifth of
capital over a year; at twenty names those become 6.3% and zero. Whatever selection skill
that strategy has must first overcome a structural handicap it chose.

The finding is one 52-week window in a strong bull market and the absolute numbers will
not generalise. The shape of the curve, which is what matters, follows from the skew of
the cross-section rather than from its direction.

No strategy was promoted and live trading remains disabled.

References:

- `scripts/run_breadth_diversification_curve_v1.py`
- `evidence/breadth_diversification_curve_v1/`

## Step 191 — Turn the volatility exposure into a gate, and sharpen the Step 189 claim

Step 189 found that a high-volatility tilt is sufficient to explain most of the saved
strategies' return ranking, and that nothing in the existing battery measures it. This
step turns that measurement into a standing gate so the exposure is chosen rather than
inherited.

The statistic is the weight-weighted mean cross-sectional volatility percentile of the
single names a book holds, where 0.50 is a book of typical volatility. Thresholds were
declared before measurement: a neutral band of 0.40 to 0.60, mandatory declaration and
bear-regime evidence above 0.60, and outright failure above 0.75.

Applied to the six saved strategies the result is more discriminating than the Step 189
write-up implied, and that write-up is corrected here. Two books sit clearly above the
band and fail: the Micron-led growth strategy at 0.717 and the residual leader at 0.642.
Three sit inside it at 0.551 to 0.553, which is above the median but not a declared bet.
The ETF incumbent at 0.216 is genuinely defensive. Step 189 stated that every SEC
strategy sits well above the median; the accurate statement is that two do markedly, three
do marginally, and the correlation of 0.855 between tilt and return across the six is
driven mainly by the spread between those two extremes and the incumbent.

The gate cannot currently be satisfied by any tilted book for a reason that is not the
strategies' fault. Above the neutral band it demands evidence of behaviour in a falling
market, and the SEC stock price panel starts 2022-12-02. That evidence does not exist and
cannot be produced without historical stock prices the project does not have. The gate is
therefore recorded as binding on data availability rather than on construction, which is
the honest description and keeps the requirement visible instead of quietly dropping it.

The gate applies to every candidate evaluated from this point onward. No strategy was
promoted and live trading remains disabled.

References:

- `config/volatility_tilt_gate_v1.json`
- `scripts/run_volatility_tilt_gate_v1.py`
- `evidence/volatility_tilt_gate_v1/`

## Step 192 — Run the fundamental half, and find one signal that survives

Moving the project off the iCloud-synced Documents folder unblocked the XBRL extraction
that had defeated three earlier attempts. It now completes in seventy seconds, producing
486,620 point-in-time facts across 3,567 issuers and eight concepts. The full
twenty-two-signal program then ran in twenty seconds.

Twenty-one of twenty-two signals fail, and the pattern from Step 189 holds. Every
defensive factor is heavily negative, with low idiosyncratic volatility at -41.28%
annualised spread and low volatility at -38.97%. The quality family is also negative:
gross profitability -13.88%, return on assets -17.63%, and the quality composite -19.37%.
Value is mildly negative, with book to market at -1.68% and earnings yield at -4.55%.
Momentum is flat to negative. Cash conversion, this project's incumbent signal, produces
+0.77% with a coin-flip 50% weekly hit rate and a permutation p of 0.85, which is the
first like-for-like measurement of it against the literature and is not encouraging.

One signal survives every pre-declared gate. Low asset growth, from Cooper, Gulen and
Schill (2008), returns a +7.61% annualised top-minus-bottom decile spread, is positive in
63.6% of weeks, and has a block-bootstrap p of 0.0020 against a Bonferroni threshold of
0.00227 across all twenty-two trials.

It was then attacked. Sub-period stability holds: +6.57% in the first half and +8.64% in
the second, positive in 58% and 69% of weeks respectively. It is not a size effect, with
a correlation to log assets of only -0.071 across 3,003 issuers. Most importantly for
this project, it is close to orthogonal to everything already here: its largest absolute
correlation with any other tested signal is +0.118 against gross profitability, and it
correlates -0.057 with twelve-one momentum and -0.032 with return on assets.

Two failures are recorded against it. Bootstrap significance is block-length sensitive:
p is 0.0000 at four weeks, 0.0015 at eight and 0.0020 at thirteen, but 0.0045 at
twenty-six, which fails the same Bonferroni threshold. And only 4.1% of the raw spread
survives removing the single best contributor from each decile in each window, so the
measured edge lives almost entirely in the tails. That last figure is less damning than it
first appears, because a portfolio holding the whole decile would capture those tails
rather than lose them, and Step 190 established that capturing skew is precisely what
breadth buys in this cross-section. It nonetheless means realised outcomes will be highly
variable.

The candidate's real interest is not its spread but its independence. This project's
binding constraint has been an effective breadth near 1.15, and no amount of retuning the
momentum and cash-conversion family moved it. A signal with a genuine, literature-backed
prior that correlates below 0.12 with everything already tested is the first plausible
route to a second bet rather than a re-weighting of the first.

It is a candidate, not a discovery. It rests on 129 overlapping weekly windows inside a
single 2023-2026 bull regime, it is one of twenty-two tested here on top of the project's
much larger cumulative search, and it has no forward evidence whatsoever. It should be
frozen and given its own forward clock rather than blended into anything.

No strategy was promoted and live trading remains disabled.

References:

- `scripts/build_fundamental_signal_panel_v1.py`
- `scripts/run_signal_discovery_program_v1.py`
- `evidence/signal_discovery_program_v1/`
- `data/fundamental_signal_panel_v1/`

## Step 193 — Test the survivor properly, and decline to freeze it

Step 192 found low asset growth surviving all pre-declared gates on overlapping weekly
windows. Before freezing it with a forward clock it was re-tested two ways: on strictly
non-overlapping windows, and as an actual long-only portfolio with costs, an execution
delay and varying breadth.

A defect in the first run is recorded rather than hidden. The equal-weight benchmark
returned infinity, because the price panel contains 52 zero prices, one of which produces
an infinite weekly return, together with twelve observations above +1000% in a single
week. The benchmark gate in v1 was therefore meaningless. A v2 was built with zero prices
dropped and weekly moves capped at +200%. That hygiene was checked before adoption: it
moves the non-overlapping spread from +2.43% to +2.17% per thirteen weeks, so the signal
never depended on the bad prints.

The strict test does not confirm the effect. Nine genuinely independent windows give a
mean spread of +2.17% per thirteen weeks, but a median of only +0.79%, and the spread is
positive in five of nine windows. Mean far above median across nine observations that are
close to a coin flip is not evidence. The overlapping test reused every observation
thirteen times, and its p of 0.0020 was correspondingly overstated despite the block
bootstrap.

The portfolio test is decisive. The equal-weight panel of all priced issuers returned
22.21% annually with a Sharpe of 1.28 and a maximum drawdown of -20.3%. Long-only books
built from the signal returned 17.32% at ten names, 24.73% at twenty, 17.46% at fifty,
15.58% at one hundred and 15.06% at two hundred, with Sharpe ratios between 0.62 and 0.88.
Every configuration has a worse Sharpe than simply holding the whole universe, and four of
five underperform it outright. The two-hundred-name book, which approximates the full top
decile, trailed the benchmark by 7.15 points.

The reconciliation between a positive long-short spread and a losing long-only book is
the interesting part, and it is consistent with everything else found this session. A top
decile can beat a bottom decile while both trail the mean. Steps 189 and 191 established
that this sample rewarded volatile, high-beta names; low asset growth selects
systematically against exactly those names. The signal is measuring something real about
the cross-section and that something is on the wrong side of the regime.

The candidate is therefore not frozen and no forward clock is started. Doing so would
commit a year of the project's only untouched evidence to a rule that loses to buying the
universe equally. The correct record is that low asset growth is the only literature
signal of twenty-two to produce a positive spread here, that the spread does not survive
independent windows, and that it does not convert into a long-only portfolio without a
short book this project cannot cost or borrow.

An unglamorous benchmark result is worth carrying forward. The equal-weight panel returned
22.21% with a Sharpe of 1.28 and a -20.3% drawdown over the same window, which is better
risk-adjusted performance than any of the six saved strategies achieved on pure cash.

No strategy was promoted and live trading remains disabled.

References:

- `config/low_asset_growth_candidate_v2.json`
- `scripts/run_low_asset_growth_candidate_v2.py`
- `evidence/low_asset_growth_candidate_v2/`

## Step 194 — Audit the price panel, and correct a comparison error in Step 193

Two things here: an integrity audit of the price panel every strategy is built on, and a
correction to a claim made in Step 193 that does not survive a matched-window comparison.

The sealed weekly price panel was audited without being modified. It is hashed in the
panel-inputs manifest, which chains to a file the forward protocol pins, so a cleaned
derivative is the only safe form this correction can take.

Across 3,253 issuers and 195 weeks the panel contains 52 zero prices, all inside a single
issuer, producing one infinite weekly return. There are no negative prices. Sixty-seven
weekly returns exceed +200%, twelve exceed +1000%, and the largest single week is a 29x
move; ten weekly returns are below -95%. Correcting all of it touches 77 return
observations out of roughly 630,000, so the price defects are real but small.

The larger finding is not the extremes. Four hundred and twenty-nine issuers, 13% of the
universe, carry runs of eight or more consecutive identical weekly prices. A frozen price
is a name that is not trading, usually delisted or halted, and it is being carried in the
universe as though it were investable. Twenty-five further issuers have internal coverage
gaps, where a price disappears and later returns, which manufactures a fake return across
the gap. A cleaned derivative was written to `data/clean_weekly_prices_v1/` with zero and
negative prices removed and weekly moves capped at +200% and floored at -95%.

The correction matters more. Step 193 reported that the equal-weight panel returned 22.21%
at a Sharpe of 1.28 and stated this was better risk-adjusted performance than any of the
six saved strategies achieved on pure cash. That comparison was invalid. The 22.21% figure
covers the full 143-week sample, while the saved strategies' figures are trailing
fifty-two weeks. It is the same mismatched-window error this project has caught elsewhere,
made here by me.

Measured over the identical trailing fifty-two weeks to August 7, 2026, the equal-weight
universe returned 30.19% with a Sharpe of 2.03 and a maximum drawdown of -6.7%. Every
saved strategy beat it on both return and Sharpe over that window: the sector ensemble at
124.20% and 3.10, the residual leader at 112.60% and 3.16, the daily-audited book at
92.68% and 2.47, and even the ETF incumbent at 70.31% and 2.13. The claim in Step 193 is
withdrawn.

What survives the correction is narrower and still worth keeping. The equal-weight
universe has the shallowest drawdown of any book measured here, at -6.7% against the
sector ensemble's -8.71%, and it achieves that with no selection, no leverage and
essentially no turnover at 0.0003 per week. Excluding the 429 stale issuers raises its
return to 23.72% on the full sample while slightly lowering its Sharpe, so the untradeable
names are not the source of its performance.

It is not a candidate. It has no thesis beyond owning everything, and over the window the
strategies are judged on it loses to all of them. It is a useful floor: any future
candidate that cannot beat owning the universe equally, after costs, is not earning its
complexity.

No strategy was promoted and live trading remains disabled.

References:

- `scripts/run_price_panel_integrity_audit_v1.py`
- `scripts/run_equal_weight_universe_candidate_v1.py`
- `evidence/price_panel_integrity_audit_v1/`
- `evidence/equal_weight_universe_candidate_v1/`
- `data/clean_weekly_prices_v1/`

## Step 195 — Reconcile every panel-dependent result against the cleaned prices

The request was to re-run the survival laboratory on the cleaned price panel. That
operation does not exist: the survival lab reads only each strategy's own weekly return
series from the dashboard export and never touches the price panel, so cleaning the panel
cannot change a single survival number. Recording that is more useful than performing a
re-run that would have produced identical output by construction.

Three analyses do depend on the panel, and all three were reconciled. The volatility tilt
gate and its attribution study use the panel to rank cross-sectional volatility; the
breadth diversification curve draws random portfolios from it.

Nothing material moves. Weight-weighted volatility tilts are identical to four decimal
places for five of six strategies, and the sixth changes by 0.000011. The reason is
structural rather than lucky: the tilt is a rank statistic, and correcting 77 observations
out of roughly 630,000 does not reorder a 52-week volatility ranking. The breadth curve's
median outcomes move by at most 0.85 percentage points at 320 names, leaving both the
shape of the curve and its conclusion untouched.

Every conclusion previously drawn from the dirty panel therefore stands: the tilt verdicts
in Step 191, the attribution in Step 189, and the diversification curve in Step 190.

A process failure is recorded. The first attempt at this reconciliation renamed three
scripts to v2 but did not repoint their output paths, so the clean-panel runs silently
overwrote the v1 evidence directories. Because the results were numerically identical the
overwrite destroyed nothing, but that was luck rather than design; a genuine difference
would have erased the comparison it was meant to establish. The duplicate scripts were
deleted and replaced with a single reconciliation that reads both panels and reports the
delta, which is what the check should have been from the start.

The cleaned panel remains the correct input for future work, not because it changes past
results but because carrying an infinite return and 429 untradeable issuers into new
research is an avoidable risk.

No strategy was promoted and live trading remains disabled.

References:

- `scripts/run_clean_panel_reconciliation_v1.py`
- `evidence/clean_panel_reconciliation_v1/`

## Step 196 — Test the strategies against a random-portfolio null, and correct Step 189

Every negative result this session concerned signals measured in isolation. None of them
asked the direct question: are the saved strategies themselves distinguishable from
portfolios drawn at random? They returned between 92% and 156% on pure cash while the
equal-weight universe returned 30.19% over the same trailing fifty-two weeks, so either
they are doing something or they are extreme draws.

For each strategy, four thousand random portfolios were generated holding the median
number of names that strategy actually held, over that strategy's own trailing
fifty-two weekly decision dates, using the cleaned price panel. A second null additionally
matched each random portfolio's volatility percentile to the strategy's own median tilt,
within a five-point tolerance, which asks whether anything survives once the exposure
identified in Step 191 is held constant.

Every strategy sits in the extreme right tail. Against the size-matched null the
percentiles are 99.4% for the sector ensemble and the residual leader, 99.1% for the
Micron-led growth book, 99.0% for the fragile sleeve, 98.4% for the daily-audited book and
86.1% for the ETF incumbent. The random medians are 21% to 30% and the ninety-fifth
percentiles 56% to 120%, against realised returns of 72% to 144%.

The volatility-matched null is the part that forces a correction. Controlling for tilt
does not reduce these figures, it raises them: 100.0% for the sector ensemble, the fragile
sleeve and the residual leader, 99.8% for the daily-audited book, 98.7% for the growth
book and 94.8% for the incumbent. Step 189 stated that a high-volatility tilt is
sufficient to explain most of the return ranking with no stock-selection skill required.
That claim is withdrawn. Holding tilt constant makes the strategies look more exceptional,
not less, so the tilt is not what is generating their returns.

What this does not establish is skill, and the reason is the oldest problem in this
project. These strategies were selected out of a very large search precisely because they
performed well in this window, and the test is run on that same window. Finding a
deliberately chosen high performer in the top percentile of random draws over its own
selection period is close to tautological. The result refutes one specific alternative
explanation; it does not confirm the positive one.

Three readings are consistent with the evidence and cannot be separated here. The
strategies may capture something real that the isolated signal tests were too blunt to
detect, since a portfolio combines several weak signals with sizing and timing that a
single-signal decile spread ignores. They may be the survivors of a search wide enough to
produce 99th-percentile outcomes by chance alone. Or the returns may come from an exposure
not yet measured, as the volatility tilt was not measured until Step 191.

Separating them requires data the selection never touched. That is what the forward clock
is for, and its first realisation is September 4, 2026. This step raises the value of
that clock considerably: there is now a specific, falsifiable expectation attached to it
rather than a vague hope.

No strategy was promoted and live trading remains disabled.

References:

- `scripts/run_random_portfolio_null_v1.py`
- `evidence/random_portfolio_null_v1/`

## Step 197 — Pre-register what September 4 will mean, and rehearse the scorer

Step 196 established that the saved strategies sit at the 98th to 100th percentile of
size- and volatility-matched random portfolios, and that the test cannot separate skill
from selection because it runs on the window the strategies were selected from. The only
thing that separates them is data the selection never touched. This step makes sure that
data will actually settle the question when it arrives.

Three things were registered before any forward observation exists, because a prediction
written after seeing the data is not a prediction.

First, the scoring method. Each completed week, every tracked strategy's realised return
is placed inside a distribution of four thousand random portfolios holding the same number
of names at the same volatility percentile within five points, over that same week. This is
considerably stricter than scoring against absolute return or a market index, because it
removes size, breadth and volatility exposure simultaneously.

Second, three competing hypotheses with fixed falsification thresholds. Skill implies the
median weekly percentile stays at or above 0.65 across the first thirteen forward weeks
and above 0.60 across fifty-two, and is falsified if it falls below 0.55 over any completed
thirteen-week block. Selection implies regression toward 0.50 with a fifty-two-week median
between 0.45 and 0.55. An unmeasured common exposure implies percentiles stay high while
the six strategies' weekly percentiles correlate above 0.6 with one another. The thresholds
are frozen; revising them creates a v2 and voids this registry rather than editing it.

Third, all six dashboard strategies are tracked rather than the one that currently holds a
forward protocol. Two of them are marked not eligible for promotion on their own
falsification record and are tracked as shadow observations only. Recording what happens to
an ineligible strategy cannot promote it, and declining to record it would discard free
evidence.

The scorer was then rehearsed on six historical weeks. A rehearsal writes to separate files,
is stamped as such, and advances no clock; its purpose is to ensure the machinery does not
fail on September 4 with nobody watching.

The rehearsal produced an unplanned observation worth recording. Over the six most recent
historical weeks the median weekly percentiles are 0.246 for the growth book, 0.293 for the
residual leader, 0.392 for the daily-audited book, 0.527 for the sector ensemble, 0.569 for
the fragile sleeve and 0.623 for the ETF incumbent. Four of six sit at or below 0.50. That
is the pattern the selection hypothesis predicts, appearing in the last weeks of the
selection window itself.

It should not be overread. Six weekly observations are extremely noisy, weekly percentiles
are far noisier than the fifty-two-week figures in Step 196, and these weeks remain inside
the sample the strategies were chosen on. It is a hint, not a result, and it is recorded
now precisely so that it cannot later be presented as a prediction made in advance.

No strategy was promoted, no forward clock advanced, and live trading remains disabled.

References:

- `config/forward_prediction_registry_v1.json`
- `scripts/score_forward_week_v1.py`
- `evidence/forward_prediction_registry_v1/`

## Step 198 — Vary construction instead of selection, and find drawdown control is the only real gain

Every prior program in this project varied which names to hold. The decile study measured
that space as empty, so searching it harder is searching something already known to be
flat. This step holds selection constant at "every priced issuer" and varies only portfolio
construction, which Step 190 showed moves the whole outcome distribution rather than just
its variance. Eight structural rules were declared before running; none has a fitted
parameter, so there is nothing to tune.

No variant beats equal weighting on both return and drawdown. The baseline returns 22.25%
annually at a Sharpe of 1.28 with a -20.3% maximum drawdown over the 143-week sample.

Drawdown control is the one variant that materially improves the shape of the outcome.
Cutting exposure to half whenever the book sits more than 8% below its running peak returns
20.63% at a Sharpe of 1.29, with the maximum drawdown improving from -20.3% to -16.1% and
the worst rolling fifty-two-week return improving from -5.5% to -0.5%. It gives up 1.62
points of annual return to remove almost all of the losing-year tail, and it is the only
rule in the set with a higher Sharpe than the baseline, if only by 0.01. Turnover rises
from 0.0003 to 0.0090 per week, which is still negligible.

Excluding the least volatile decile produces the highest return at 23.54% but a worse
drawdown at -22.1%, which is the volatility finding from Steps 189 and 191 appearing from
a third direction. The inverse-volatility and inverse-variance books confirm it in the
mirror: weighting toward low-volatility names returns 1.42% and -0.43% respectively,
destroying almost all return, because this sample punished exactly what those rules
overweight.

A design flaw in this run is recorded. The capped equal-weight variant produced results
identical to the baseline to every reported digit, because a 1% cap can never bind on a
book of roughly three thousand names each holding about 0.03%. The variant tested nothing.
It is left in the record as a no-op rather than quietly re-run with a tighter cap, because
choosing a cap after seeing that the first one did nothing is how a structural test turns
into a fitted one.

The comparison that matters is stated carefully to avoid repeating the Step 193 error.
These figures cover the full 143-week sample and are not comparable to the saved
strategies' trailing fifty-two-week returns of 92% to 156%. On drawdown they are
comparable in kind, and a -16.1% maximum drawdown with a -0.5% worst year is a materially
better distribution than any saved strategy achieved, all of which carry negative worst
rolling years between -14.06% and -39.81%.

The honest summary is that construction cannot manufacture return here, but it can
reshape the distribution, and drawdown control is the only rule tested that does so at an
acceptable price. That is worth carrying into any future candidate as an overlay rather
than treated as a strategy in itself.

No strategy was promoted and live trading remains disabled.

References:

- `config/portfolio_construction_tournament_v1.json`
- `scripts/run_portfolio_construction_tournament_v1.py`
- `evidence/portfolio_construction_tournament_v1/`

## Step 199 — Price the search itself, and find no saved book survives it

Step 196 said plainly that finding a deliberately chosen high performer in the top
percentile of random draws over its own selection period is close to tautological. It did
not put a number on the tautology. This does, using the deflated Sharpe ratio of Bailey
and Lopez de Prado (2014), which deflates an observed Sharpe by the expected maximum
Sharpe under a null of N zero-skill trials and corrects for sample length, skew and
kurtosis.

N has never been counted in this project, so it is reported as a sensitivity grid rather
than guessed at. The documented lower bounds are already large: 576 standardized
configurations in Batch 05, 288-experiment batches in Batches 01 and 04, 2,924 nested ML
fits in Batch 17, 22 literature signals across Steps 189 and 192, and 198 recorded steps.
A defensible N for the SEC family is in the thousands.

At ten trials, two of five books clear the 0.95 threshold: the residual leader at 0.958
and the ETF incumbent at 0.957. At one hundred trials, none do. At one thousand, the
deflated ratios are 0.520, 0.509, 0.440, 0.311 and 0.068. At five thousand they fall to
between 0.351 and 0.027.

The mechanism is worth stating because it changes what counts as progress. The residual
leader's full-history annualised Sharpe is 1.79 and the expected maximum Sharpe under a
thousand zero-skill trials on a sample this short is 1.76. The observed number is not
beaten by the null by much, but it is not distinguishable from it either. The Micron-led
growth book is the clearest case: an annualised Sharpe of 0.95 against a null threshold of
1.75, which is to say it underperforms what pure search would be expected to produce.

The consequence is the part that matters. This audit cannot be repaired by finding a
higher Sharpe on the same window, because raising the observed Sharpe on the sample the
search ran over also raises the null it is deflated against. Only two things move a
deflated Sharpe in the right direction: a longer or genuinely independent sample, and
fewer effective trials. Both are structural, and neither is available by tuning.

A low deflated ratio does not prove a strategy has no edge. It proves the retrospective
sample cannot establish one, which is the same conclusion Steps 196 and 197 reached from a
different direction, now with a number attached.

No strategy was promoted and live trading remains disabled.

References:

- `config/deflated_sharpe_audit_v1.json`
- `scripts/run_deflated_sharpe_audit_v1.py`
- `evidence/deflated_sharpe_audit_v1/`

## Step 200 — Find a second bet on the panel that was already on disk

Step 186 ran the 35-ETF vintage as a cross-sectional sector rotation and found it worthless
over 33 years, concluding that generic sector-momentum rotation should not be built on
again. That conclusion stands and is not revisited. It concerned one way of using the
panel. This step runs the other one: long-only time-series momentum across bonds,
commodities, FX, international and equity, which is a different mechanism with a different
literature behind it, and which the project has never tested.

Evaluation starts 2007-06-01, the first date on which the bond, commodity, FX and
international sleeves all exist. Before it the universe is equities only, and the probe
would be measuring sector rotation again. Signals are the mean sign of the 63, 126 and
252-day return, sizing is inverse trailing volatility scaled to a volatility target,
rebalancing is monthly with a one-day execution delay and 10 bps per unit turnover. Every
parameter was declared in the config before the run.

Over 4,832 trading days the sleeve returns between 3.68% and 9.12% annually depending on
the leverage cap, at a Sharpe of 0.92 that is almost invariant to that cap, against SPY's
0.62 and a 60/40 book's 0.77. Its maximum drawdown at the widest setting tested is -21.4%
against SPY's -55.2%.

The regime record is the part the equity books cannot produce. Through the global financial
crisis the sleeve returned +12.5% against SPY's -44.9%; through the 2022 bear, +0.2%
against -18.2%; through the COVID crash, -1.4% against -11.6%. It badly lags in the
2023-2026 window, returning 45.4% against SPY's 112.3%, which is the correct behaviour for
a defensive diversifier and the reason it must never be judged on that window alone.

The independence result is the reason to record this at all. Weekly correlations to the
saved books are -0.087, -0.053, -0.042 and +0.149; only the daily-audited book, which
itself holds ETFs, correlates meaningfully at +0.654. Adding the sleeve raises the
effective independent bet count across the tracked books from 2.48 to 3.08. The project's
binding constraint since Batch 03 has been an effective breadth near 1.15, and no
re-weighting inside the momentum and cash-conversion family has ever moved it. This is the
first tested source that does.

Two limits are recorded against it. Long-only trend is materially weaker than the
long-short trend the literature documents, because the short leg is where much of the
crisis payoff lives and this project can neither borrow nor cost it. And the leverage grid
is reported rather than selected; choosing a point on it after seeing the results is how a
structural test becomes a fitted one.

This is a probe, not a candidate. No forward clock was started, no strategy was promoted,
and live trading remains disabled.

References:

- `config/cross_asset_trend_probe_v1.json`
- `scripts/run_cross_asset_trend_probe_v1.py`
- `evidence/cross_asset_trend_probe_v1/`

## Step 201 — Extend the sleeve to 1993, and find the volatility target is a leverage rule

Step 200 evaluated the cross-asset trend sleeve from 2007 because that is when the bond,
commodity, FX and international sleeves all exist. This extends it to 1993, sweeps the
leverage grid, and adds two sizing variants to find out what the volatility target is
actually contributing.

The 1993 extension answers its own question, and the answer is that the earlier start is
not informative about the rule. Over the full span the Sharpe falls to 0.55, but the count
of assets the rule could choose from is 1 in 1994, 2 in 1999, 14 in 2003, 28 in 2007 and 35
today. Before 2007 this is not a cross-asset book; it is a single-asset trend filter on SPY
that gradually acquires company. The degradation measures the opportunity set, not the
signal. Recorded because a full-span Sharpe of 0.55 would otherwise look like the 2007-2026
result failing to generalise backwards, and it is not that.

The window that does generalise is 2002-08 onward, the point at which the Treasury and
credit sleeves arrive and the universe reaches fourteen assets. Over that span the Sharpe is
0.98, slightly better than the 0.92 measured from 2007, with the same -9.02% maximum
drawdown at the lowest leverage setting. Two independent windows of fourteen and nineteen
years now agree on a Sharpe near unity.

The sizing result is a correction to how Step 200 described itself. Three variants were run:
unconditional targeting, conditional targeting that intervenes only when realised volatility
exceeds the target, and no targeting at all. The conditional variant collapses onto the
untargeted control at every leverage cap, producing an identical 3.88% return, an identical
-9.02% drawdown and an identical 4.41 annual turnover. The reason is that this book's
natural volatility is almost always *below* the target, so a conditional rule that only acts
when volatility is high essentially never acts.

That means the unconditional "volatility target" in Step 200 was not reducing risk. It was
levering the book up to a chosen volatility, and the Sharpe invariance across the grid —
0.92 at every one of the four settings, to two decimals — is the signature of a pure scaling
operation rather than a risk control. The sleeve has a Sharpe near 0.95 and the grid is
simply a choice of how much of it to take. Step 200's leverage-grid figures are unaffected;
its description of them was imprecise, and this is the correction.

The practical consequence is that the conditional-targeting upgrade from the literature does
not apply to this sleeve, because the condition it triggers on does not occur here. It may
still apply to the SEC equity books, whose realised volatility is far higher, and that is
where it should be tested instead.

This remains a probe. No point on the leverage grid was selected, no forward clock was
started, and live trading remains disabled.

References:

- `config/cross_asset_trend_extended_v2.json`
- `scripts/run_cross_asset_trend_extended_v2.py`
- `evidence/cross_asset_trend_extended_v2/`

## Step 202 — Count the trials, and replace the sensitivity grid with a number

Step 199 could not state how many configurations this project has evaluated, so it reported
the deflated Sharpe ratio as a grid across assumed trial counts. A grid is the honest
fallback when the number is unknown; it is not a substitute for knowing it.

An append-only, hash-chained trial ledger was built with the same reasoning as the forward
evidence store: a trial count that can be quietly revised downward after a disappointing
result is not a trial count. It was then seeded from the counts the project record states
explicitly — 2,924 nested ML fits from Batch 17, 576 statistical trials from Batch 05, 288
each from Batches 01 and 04, 213 screened repository factors, 33 scored Layer 2 strategies,
22 literature signals, 8 construction rules, and a deliberately conservative 60 for the
entire SEC fundamental program.

That totals 4,412 and it is a lower bound, not a census. Steps that say a neighbourhood was
searched without naming a number contribute nothing to it, and the SEC entry in particular
assigns one configuration per step to a program that plainly evaluated more. The direction
of the error matters and is recorded: an undercount makes promotion easier, not harder, so
the reconstruction is marked as such and only trials registered at evaluation time count as
properly recorded from here.

Re-running the Step 199 audit against counted trials removes the last ambiguity. At family
scope, which asks only how many configurations were tried inside the family a book came
from and uses the deliberately generous 60 for the SEC program, the deflated ratios are
0.831, 0.776, 0.662, 0.573 and 0.280. At project scope, which is the right question because
the books that reached a dashboard were chosen by looking across families, they are 0.363,
0.353, 0.291, 0.186 and 0.029. Nothing clears 0.95 under either reading, and the family
scope is already the most favourable framing available.

The gate itself fails closed in three ways, each tested. An unregistered family returns a
refusal rather than treating an unknown N as one. A broken hash chain refuses to score at
all. And a return series with no usable dispersion is rejected rather than producing an
infinite Sharpe — a guard that a test caught failing on exactly constant input, because the
floating-point standard deviation of a constant series is small but not zero.

No strategy was promoted and live trading remains disabled.

References:

- `src/systematic_trader/trial_ledger.py`
- `tests/test_trial_ledger.py`
- `config/trial_ledger_reconstruction_v1.json`
- `scripts/seed_trial_ledger_v1.py`
- `scripts/run_deflated_sharpe_gate_v2.py`
- `evidence/deflated_sharpe_gate_v2/`
