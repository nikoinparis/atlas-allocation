# Signal Discovery Next Sprint Plan

Research-only implementation plan for the next sprint before any R5 ensemble testing. The sprint should build and validate new Layer 1 candidate signals only; it should not promote signals or change portfolio allocation.

## Recommended Next Sprint

**R5-pre: Public-data signal implementation and validation.** Build a focused batch from the highest-priority existing/free-data backlog, then run the same IC, redundancy, holdout, decay, and state-conditional tests used in R1-R4.

## Sprint Guardrails

- Do not modify production pins, dashboard/public files, production portfolio artifacts, or live trading/execution logic.
- Do not implement R5/R6 ensemble allocation yet.
- Lag every signal before validation.
- Prefer simple public-data signals before ML.
- Use R3 state-conditional tests as a first-class gate.

## Batch 1: Existing Data, Fastest To Test

| signal_name | category | priority_score | repo_mapping | expected_best_regime | expected_bad_regime |
| --- | --- | --- | --- | --- | --- |
| Cyclicals vs defensives | G. Cross-Asset Leadership | 5 | Layer 1 cross-sector leadership | calm_trend, recovery_confirmed | stressed_panic |
| Defensive sector leadership | J. Quality / Defensive | 5 | sector leadership/risk signal | stressed_panic | calm_trend |
| Drawdown acceleration | E. Volatility / Risk | 5 | risk regime feature / Layer 1 meta | early stress | recovery whipsaw |
| Risk-on breadth basket | F. Breadth / Participation | 5 | Layer 1 breadth/risk participation | calm_trend | stressed_panic |
| Sector breadth using sector ETFs | F. Breadth / Participation | 5 | Layer 1 sector breadth signal | calm_trend | sector concentration |
| Signal agreement score | M. Signal Quality / Meta Signals | 5 | meta Layer 1 diagnostic | calm_trend, recovery_confirmed | signal crowding periods |
| Signal decay freshness | M. Signal Quality / Meta Signals | 5 | extend R1 rolling decay | all regimes | small samples |
| Signal dispersion / disagreement | M. Signal Quality / Meta Signals | 5 | meta signal environment | neutral_mixed warning | strong trends if false |
| % ETFs above 13/26/52w MA | F. Breadth / Participation | 4 | ETF breadth proxy Layer 1/meta | calm_trend | narrow mega-cap rallies |
| Breakout / 52-week high proximity | A. Momentum / Trend | 4 | new Layer 1 signal CSV + R2-style validation | calm_trend | neutral_mixed chop |

Implementation sketch:

1. Create signal builders for sector/risk-on breadth, defensive leadership, cyclicals-vs-defensives, value-vs-growth leadership, drawdown acceleration, correlation spike, signal agreement, signal dispersion, and signal decay freshness.
2. Write candidate CSVs under `data/02_layer1_signals/` with `research_only=True` and one-period lag.
3. Reuse the R2/R3 validation framework for full IC, holdout IC, redundancy, stressed_panic damage, and calm_trend contribution.
4. Produce a rejection-first report; passing signals remain candidates only.

## Batch 2: Free External Data/API

| signal_name | category | priority_score | data_source | repo_mapping |
| --- | --- | --- | --- | --- |
| Direct HY OAS level/change | D. Credit / Liquidity | 5 | FRED | repair R2 credit ingestion |
| Equal-weight vs cap-weight SPY proxy | F. Breadth / Participation | 5 | free yfinance; RSP not in current universe | add free external ETF input to data hub research |
| IG OAS level/change | D. Credit / Liquidity | 5 | FRED + ETF | credit macro signal |
| Real rates / TIPS yield trend | C. Macro / Cycle | 5 | FRED + existing ETFs | macro Layer 1 signal |
| Sahm rule / labor deterioration | C. Macro / Cycle | 5 | FRED | macro weekly ingestion + Layer 1 macro panel |
| VVIX vol-of-vol | E. Volatility / Risk | 5 | Cboe/Yahoo | extend vix_term_structure inputs |
| AAII bull-bear spread | K. Sentiment / Attention | 4 | AAII download | sentiment module |
| Bond real-yield valuation | I. Value / Relative Valuation | 4 | FRED + existing | bond valuation macro signal |
| Cash yield vs risk yield spread | H. Carry / Yield | 4 | FRED + distributions | macro/carry opportunity cost signal |
| Credit carry after spread risk adjustment | H. Carry / Yield | 4 | FRED + distributions | carry + credit composite Layer 1 |

Implementation sketch:

1. Repair/extend macro ingestion so `macro_weekly.csv` includes FRED series with as-of lags and clear source metadata.
2. Add Sahm rule, 3m10y recession probability/term spread, real rates, Fed funds/policy pressure, HY/IG OAS, VVIX, VIX9D/VIX, RSP/SPY, AAII sentiment, and factor ETF proxies where data is available.
3. Keep release-date and revision risk explicit in each signal CSV.

## Paid/PIT Data Queue

| signal_name | category | priority_score | data_needed | data_source |
| --- | --- | --- | --- | --- |
| Advance/decline line | F. Breadth / Participation | 4 | PIT stock returns or exchange A/D data | paid/free partial |
| New highs/new lows stock breadth | F. Breadth / Participation | 4 | PIT constituents and daily highs/lows | Norgate/Sharadar/WRDS or vendor |
| Cboe equity put/call ratio | K. Sentiment / Attention | 3 | Cboe daily put/call ratios | Cboe/YCharts/paid history |
| Industry participation breadth | F. Breadth / Participation | 3 | PIT stock industry membership/prices | Norgate/WRDS/Sharadar |
| PMI/ISM growth proxy | C. Macro / Cycle | 3 | ISM PMI or proxies | ISM paid; FRED partial/proxies |
| Sector valuation spreads | I. Value / Relative Valuation | 3 | sector P/E, P/B, dividend yield | ETF/fundamentals APIs |
| Treasury liquidity / MOVE proxy | D. Credit / Liquidity | 3 | MOVE index, Treasury vol ETF/proxy | ICE/paid or Yahoo proxies |
| ETF flows proxy | K. Sentiment / Attention | 2 | ETF fund flows/AUM | ETF.com/FactSet/Bloomberg |

These should not block the next sprint. They become serious only if paid PIT data is available and licensed for research.

## Research-Only / Avoid Queue

| signal_name | category | priority_score | short_hypothesis |
| --- | --- | --- | --- |
| Decision-focused learning | N. ML / Representation Signals | 1 | Directly optimizing portfolio utility may align model with objective but risks learning cash/bond hiding. |
| ETF price-to-own-history value | I. Value / Relative Valuation | 1 | Assets far below long-term trend may be cheap, but can be value traps. |
| Election cycle regime | L. Seasonality / Calendar | 1 | Policy uncertainty and liquidity differ by election year. |
| Holiday-week risk appetite | L. Seasonality / Calendar | 1 | Short holiday weeks and year-end may have flow effects. |
| Intraday gap/overnight effect | L. Seasonality / Calendar | 1 | Open-to-close vs close-to-open may contain information, but repo is weekly close-based. |
| Reinforcement learning allocator | N. ML / Representation Signals | 1 | RL can learn dynamic allocation but has extremely high overfit risk in short financial histories. |

Avoid these before R5 because they are too sample-starved, intraday-adjacent, or overfit-prone for the current weekly ETF project.

## Acceptance Criteria For Next Sprint

- Every attempted signal has a CSV, a source note, and a validation row.
- Every skipped signal has an exact reason.
- Outputs include full-period IC, holdout IC, IC by horizon, state-conditional IC, redundancy vs strong existing signals, missingness, and stressed_panic damage flag.
- The final report explicitly says whether any signal deserves later R5 ensemble testing.

## Expected Outcome

The most likely useful additions before R5 are not more price momentum variants. They are breadth/participation, stress-protection, macro/liquidity, and meta-signal quality measures that tell the system when existing signals are trustworthy.
