# Indonesia Equity Research Protocol V1

> **RESEARCH ONLY — not investment advice, not a recommendation, and not
> approved for live or paper brokerage execution.**

## Purpose

This protocol starts an Indonesian public-equity workstream without making a
performance or readiness claim. It reuses Portfolio Optimizer 2.0's causal
research principles while keeping all Indonesian data and market assumptions
behind explicit source gates.

The first provisional candidate is a long-only liquid-equity sleeve:

- primary research universe: IDX80;
- supported comparison universes: LQ45 and IDX30;
- optional point-in-time OJK Daftar Efek Syariah (DES) intersection;
- monthly decisions;
- 70% cross-sectional 52-week momentum excluding the latest four weeks;
- 30% cross-sectional low 26-week volatility;
- select up to 12 names;
- inverse-volatility sizing with a 10% per-name cap;
- minimum median daily traded value of Rp5 billion as an initial hypothesis;
- no shorting or leverage; and
- unallocated weight remains in research cash (`CASH_IDR`).

These parameters are predeclared starting hypotheses. They were not chosen from
Indonesian performance results and are not promoted strategy settings.

## Point-in-time requirements

Every index and DES membership row must contain:

- `ticker`: four-character IDX code;
- `universe`: `IDX80`, `LQ45`, `IDX30`, or `DES`;
- `effective_from` and optional `effective_to`;
- `available_at`: when the information became usable by the research process;
- `source_id`: immutable source reference.

Membership is eligible only when it was available strictly before the decision
instant and effective on that date. A current constituent list may not be used
to reconstruct the past.

Every signal row must contain `ticker`, `feature_asof_date`,
`momentum_52w_skip_4w`, `volatility_26w`, and
`median_daily_value_idr`. Feature timestamps must precede the decision time.

## Blocking source gates

No Indonesian backtest or performance statement is authorized until the
following are acquired, pinned, licensed where required, and audited:

1. Indonesian end-of-day prices with a documented commercial-use boundary.
2. Historical IDX80/LQ45/IDX30 membership vintages.
3. Historical DES vintages for Sharia-filtered experiments.
4. Corporate actions and an Indonesian adjustment policy.
5. Suspensions, delistings, ticker changes, and inactive securities.
6. Local fees, taxes, spreads, market impact, and lot-size treatment.
7. IHSG and relevant index total-return benchmarks.
8. Data publication and redistribution permission.

IDX XBRL financial statements can support a later fundamental sleeve, but they
are not required for this price-only starter candidate. Fundamental signals
must be added as a separate predeclared experiment with filing availability
timestamps and Indonesian accounting-field normalization.

## Current implementation

`src/systematic_trader/indonesia_equity.py` provides:

- IDX ticker normalization;
- effective-dated, point-in-time universe construction;
- an optional DES intersection;
- liquidity and feature-availability gates;
- deterministic momentum/low-volatility ranking;
- capped inverse-volatility research weights; and
- automatic all-cash blocking when eligible evidence is insufficient.

The tests use synthetic observations only. Passing them means the causal and
safety behavior works as specified; it says nothing about expected returns.

## Acquired current-universe pilot

On August 22, 2026, the project froze its first Indonesian research vintage in
`data/indonesia_equity_vintages/20260822T084601Z-indonesia-current-pilot-v1`.
It contains:

- all 80 names in the observed August–October 2026 IDX80 snapshot;
- nested LQ45 and IDX30 current-period membership snapshots;
- five years of Yahoo research-cache daily data for the 80 names;
- Yahoo histories for IHSG (`^JKSE`) and LQ45 (`^JKLQ45`);
- 93,920 price rows and 385 provider-reported corporate-action rows;
- source observations, hashes, security metadata, and an immutable manifest.

This is a current-constituent pilot, not a historical-universe dataset. The
constituent lists were observed from complete secondary-source tables and
cross-checked against independently reported index additions/removals. The
corresponding official IDX announcement file still needs to be acquired and
validated. Yahoo usage remains subject to provider terms and no redistribution
right is asserted.

The pilot can support ingestion development, data-quality analysis, feature
calculation, and forward-only observations after its acquisition time. It
cannot support survivorship-safe backtests or performance claims.

## Current-universe rehearsal

`scripts/run_indonesia_current_rehearsal_v1.py` converts the frozen daily cache
to Friday-ending weekly observations, computes one timestamped feature snapshot,
applies the provisional liquidity floor, and creates research weights for the
current IDX80 universe. Its dated output is stored under
`evidence/indonesia_current_rehearsal_v1/`, with `LATEST` identifying the active
run and a manifest pinning every artifact hash.

This rehearsal intentionally produces no historical portfolio path, benchmark
comparison, performance metric, or expected-return claim. Its candidate table
is a software-and-data workflow result, not a recommendation or approval to
trade.

## Preliminary survival diagnostic

The project subsequently acquired 11 official IDX80 review workbooks covering
February 2024 through October 2026. The archive contains 880 effective-dated
membership rows and 109 distinct securities. A frozen Yahoo research cache was
then acquired for the full 109-name union so former members were not silently
dropped.

The predeclared diagnostic remains `INCONCLUSIVE_DATA_GATED`: only 31 monthly
decisions are available versus the required 60, historical membership before
February 2024 remains incomplete, and the local cost, inactive-security, price
license, and total-return benchmark gates remain open. In this short window the
strategy cleared IHSG and LQ45 price-index comparisons but failed the
equal-weight eligible-universe hurdle, the 150 bps cost hurdle, and the 0.30
Sharpe hurdle. These observations are not an authorized performance claim.

The first August 2026 decision is separately frozen in
`data/indonesia_forward_shadow_v1/`. Future observations can be appended, but
the original decision, features, and weights must remain immutable.

## Launch-to-current reconstructed diagnostic

On August 22, 2026, the project added a separately labelled research archive
covering the IDX80 launch on February 1, 2019 through the current official
reviews. It contains 22 effective periods, 1,760 membership rows, and 157
distinct historical constituents. The 2019–2023 portion uses company-hosted or
public mirrors of original IDX announcements plus contemporaneous full-list
cross-checks; the 2024 onward portion remains the direct official IDX archive.
The September 29, 2021 BUKA fast-entry replacement is represented as its own
interval. Minor reviews in this older methodology are treated as weight-only.

The extended Yahoo snapshot contains 344,482 daily rows for every requested
symbol, but its apparent symbol coverage is misleading: SRIL and WSKT return
only stale 2026 observations and no usable history during their IDX80 periods.
This leaves inactive-security and delisting bias unresolved.

The reconstructed diagnostic spans 91 monthly decisions from February 2019 to
August 2026. At the predeclared 50 bps one-way cost assumption, the candidate
produced a 4.59% diagnostic CAGR, 0.31 zero-rate Sharpe, and -46.00% maximum
drawdown. The equal-weight eligible comparison produced 3.80%, 0.28, and
-52.34%, respectively. IHSG and LQ45 are Yahoo price indexes, not total-return
benchmarks. The candidate stayed slightly positive at 150 bps one-way cost
(0.29% CAGR), and its 50 bps CAGR and Sharpe exceeded all three preliminary
comparisons. However, the -40% drawdown gate failed, the best calendar year was
2025 (+35.81%), and the formal regime-dependency gate remains unassessed.

The verdict remains `INCONCLUSIVE_DATA_GATED`. This longer result is materially
more encouraging than the 2024-only rehearsal, but it is not a pass or an
authorized performance claim.

## Inactive-security repair and current result

The original reconstructed result above is retained as the before-repair
record. A separate V2 diagnostic added independently archived Telkom University
Dataverse histories for SRIL and WSKT, verified the published file checksums,
and made any price older than 10 calendar days ineligible for a new decision.
The signal, selection count, weighting, cost grid, and survival gates did not
change. SRIL's last positive-volume observation is May 17, 2021 and WSKT's is
May 5, 2023, immediately before their documented suspensions.

The repair materially weakened the result. From February 4, 2019 through
August 21, 2026, the 50 bps one-way diagnostic produced an 18.52% cumulative
return, 2.40% CAGR, 0.22 zero-rate Sharpe, and -46.00% maximum drawdown. At 150
bps one-way cost it produced a -2.18% CAGR. The equal-weight eligible comparison
fell to -0.10% CAGR. The strategy still exceeded the preliminary IHSG, LQ45,
and equal-weight CAGR and Sharpe comparisons, but failed the 0.30 Sharpe,
-40% drawdown, 150 bps cost, regime-dependency, total-return benchmark,
validated-cost, and complete inactive-security gates. The verdict remains
`INCONCLUSIVE_DATA_GATED`.

Calendar-year diagnostic returns after the repair were -9.17% in 2019, +13.15%
in 2020, +4.18% in 2021, +3.04% in 2022, +4.00% in 2023, +0.33% in 2024,
+20.31% in 2025, and -14.43% through August 21, 2026. These are retrospective
research calculations, not live or forward returns.

## Strategy lineage versus the main project

The Indonesian candidate is not a direct deployment of the main project's
Dynamic Breadth-20 return leader. It is a simpler local-market candidate: 70%
52-week momentum skipping the latest four weeks, 30% low 26-week volatility,
top 12 selection, inverse-volatility sizing, a 10% name cap, and a provisional
Rp5 billion median daily-value floor. The main return leader combines US ETF,
SEC-filing growth, and breadth/cash-conversion components that do not yet have
point-in-time Indonesian equivalents. Any Indonesian translation must therefore
be registered as a new challenger, not described as the same strategy.

## Indonesia Dynamic Breadth Challenger V1

The first architecture-inspired challenger was registered before its return was
inspected. It left the baseline stock ranking and inverse-volatility weights
unchanged, then measured the fraction of eligible point-in-time IDX80 members
above their 43-week simple moving average. Stock exposure was fixed at 100% for
breadth of at least 60%, 60% for breadth from 40% to 60%, and 25% below 40%; an
insufficient-history state held cash. The residual stayed in `CASH_IDR`, with no
leverage or shorting.

The February 4, 2019 through August 21, 2026 result failed the predeclared
return-challenger gates. At 50 bps one-way cost, CAGR fell from the baseline's
2.40% to 1.35%, cumulative return fell from 18.52% to 10.04%, and Sharpe fell
from 0.22 to 0.17. The overlay did materially reduce risk: annualized volatility
fell from 21.69% to 12.71%, maximum drawdown improved from -46.00% to -22.63%,
and the 2026 through-August loss improved from -14.43% to -0.87%. At 150 bps
one-way cost, however, the challenger CAGR was -2.88%.

Across 91 monthly decisions, breadth was broad 21 times, mixed 37 times, weak
31 times, and insufficient for two early decisions. The historical verdict is
`HISTORICAL_CHALLENGER_FAIL`: it behaved as a useful drawdown-control diagnostic,
not a better-return strategy. Thresholds will not be changed in response to
this result; any follow-up must be separately registered before testing.

## Indonesia Multi-Horizon Momentum Challenger V1

The next stock-selection experiment was separately registered as one fixed
hypothesis rather than a parameter search. It preserved the point-in-time IDX80
universe, top 12, inverse-volatility sizing, 10% name cap, Rp5 billion liquidity
floor, 10-day stale-price exclusion, monthly schedule, and cost grid. Only the
ranking score changed: 50% 52-week momentum skipping four weeks, 30% 26-week
momentum skipping four weeks, and 20% low 26-week volatility.

From February 4, 2019 through August 21, 2026, the challenger improved the 50
bps one-way CAGR from 2.40% to 3.28%, cumulative return from 18.52% to 26.00%,
and zero-rate Sharpe from 0.22 to 0.25. Maximum drawdown was similar at -46.29%
versus -46.00%, while annualized volatility increased from 21.69% to 25.01%.
Average overlap with the baseline top 12 was 8.15 names.

The predeclared verdict is nevertheless `HISTORICAL_SELECTION_FAIL`. The
candidate's 2026 return through August 21 was -29.59% versus -14.43% for the
baseline, and its CAGR at the 150 bps one-way stress was -1.46%. It therefore
passed the base-cost return, Sharpe, drawdown-tolerance, and observation-count
gates, but failed the high-cost, regime-dependency, inactive-security,
validated-cost, total-return-benchmark, and untouched-forward gates. The result
is a research lead—not a promoted strategy or approved portfolio.

## Official fundamental-data workstream and V2 result

On August 22, 2026, the project added a separately labelled research-only
fundamental workstream. Its first point-in-time input is the official IDX
Digital Statistic `Financial Data and Ratio` archive. Five December snapshots
from 2021 through 2025 were frozen with source URLs, observation times, file
hashes, and an eligibility delay to the next month's first trading decision.
The normalized panel contains 753 historical IDX80-constituent rows. Every
snapshot covers all 80 members active on its date. Available standardized fields
include the financial-statement date, industry, assets, liabilities, equity,
sales, owner profit, ROA, ROE, and leverage. An official filing/XBRL parser and
acquisition manifest are also implemented, but full XBRL acquisition remains a
follow-on because IDX rate-limits direct non-browser downloads.

Fundamental Momentum V1 was preserved as invalid after revealing a statement-
period comparability defect: the December 2025 table contains October statements
for many issuers while prior tables generally contain September statements. That
made V1 drop its growth features and hold cash during 2026. No V1 return is used
as evidence.

V2 was registered separately before rerunning. It annualizes cumulative sales
and owner profit by the numeric month in `FS Date`, while leaving the 70% price /
30% fundamental blend, feature weights, top-12 selection, inverse-volatility
sizing, liquidity rule, and cost grid unchanged. The like-for-like evaluation
runs from January 3, 2023 through August 21, 2026. At 50 bps one-way cost, the
price-only comparison returned -11.37% cumulatively (-3.50% CAGR), with -46.29%
maximum drawdown and -0.01 zero-rate Sharpe. V2 returned -9.79% cumulatively
(-2.99% CAGR), with -40.30% maximum drawdown and -0.02 Sharpe. At 150 bps,
V2's CAGR was -6.93%.

V2 therefore failed. It modestly improved CAGR and drawdown over the same-window
price comparison, but failed the Sharpe and high-cost survival gates. The
minimum usable fundamental universe was 70 names after excluding the one April
2025 decision already blocked by missing price evidence. Full history still
starts in 2021 rather than the IDX80 launch in 2019, and the aggregated archive
does not expose exact filing publication timestamps. The result remains
research-only and cannot authorize execution, recommendation, or a return claim.

## Quarterly Fundamental Momentum V3 result

V3 was registered before its return was calculated. It expanded the official
IDX archive to 22 March, June, September, and December snapshots from March 2021
through June 2026. The resulting point-in-time panel contains 3,296 historical
IDX80 rows and covers all 80 active members at every snapshot. Each month-end
snapshot remains ineligible until the following month, and the audit found zero
target rows whose fundamental availability time was on or after the decision.

V3 changed only the update frequency and growth-period matching. Cumulative
sales and owner profit are compared with the same fiscal-statement month exactly
one year earlier. The 70% price / 30% fundamental blend, feature weights, top-12
selection, inverse-volatility sizing, 10% cap, Rp5 billion liquidity floor, and
25–150 bps cost grid remained frozen. The price-only comparison used the same
fundamental-covered universe, monthly decisions, sizing, window, and costs.

From April 4, 2022 through August 21, 2026, V3 returned 15.82% cumulatively at
50 bps one-way cost, equivalent to 3.63% CAGR, with 19.70% annualized volatility,
a 0.28 zero-rate Sharpe, and -30.65% maximum drawdown. The matched price-only
comparison returned 26.19% cumulatively, equivalent to 5.80% CAGR, with a 0.39
Sharpe and -28.65% maximum drawdown. At 150 bps, V3 returned -5.76%
cumulatively (-1.43% CAGR). Calendar returns at 50 bps were +3.75% in the 2022
partial year, -1.22% in 2023, -1.46% in 2024, +14.23% in 2025, and +0.40%
through August 21, 2026.

The formal verdict is `HISTORICAL_SELECTION_FAIL`. Quarterly data made the
fundamental strategy positive at the base cost and materially improved the
annual-data experiment, but it failed the CAGR, Sharpe, and high-cost gates
against its matched price-only comparator. Forty-eight of 53 decisions were
invested candidates; five were blocked by insufficient comparable fundamentals
or the existing price-evidence rule. The minimum invested fundamental universe
was 55 names, below the predeclared 70% canonical-feature gate by one name.
No V3 setting will be changed in response to this result.

## Indonesia cost and benchmark readiness

The current evidence supports a provisional decomposition, not a validated
single cost number:

- broker commission is broker- and account-specific;
- OJK investor-literacy material illustrates roughly 0.20% all-in buying and
  0.30% all-in selling, including a 0.043% levy in that example;
- Indonesian tax guidance applies 0.10% final income tax to gross exchange-sale
  proceeds, not profits;
- commission VAT must use the tax treatment effective for the investor and
  broker at the trade date;
- bid/ask spread, market impact, odd-lot/board-lot effects, failed fills, and
  suspension exit costs remain security- and size-dependent.

Accordingly the existing 25–150 bps one-way grid remains a stress grid rather
than a certified live-trading model. A licensed IHSG/IDX80 total-return series
has not been acquired; Yahoo's `^JKSE` and `^JKLQ45` series remain price-only
diagnostic comparators.

## Next research sequence

1. Replace pre-2024 announcement mirrors with direct IDX files or a licensed
   point-in-time constituent dataset where obtainable.
2. Extend the independently archived SRIL and WSKT repair to complete
   suspension-exit, delisting, and other inactive-security histories.
3. Acquire official OJK DES period files and intervening changes.
4. Materialize an unadjusted-versus-adjusted Yahoo revision audit.
5. Obtain licensed total-return benchmarks and an approved commercial data route.
6. Validate broker-specific fees, current taxes/VAT, spread, impact, board-lot,
   delayed-fill, and suspension assumptions.
7. Stress 25–150 bps all-in costs, liquidity caps, delayed fills, and missing
   observations.
8. Keep all results retrospective and non-promotional until untouched forward
   evidence exists.
