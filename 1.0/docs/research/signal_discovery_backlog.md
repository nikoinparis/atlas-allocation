# Signal Discovery Backlog

Research-only Renaissance-style signal discovery backlog for the weekly ETF portfolio project. This file maps realistic public/retail-accessible signal families into the existing repo architecture. It does not claim any untested signal works and does not change production logic.

## Repo Context Inspected

- Existing Layer 1 manifest: `data/02_layer1_signals/signal_manifest.json` (25 manifest entries).
- Existing validation: `signal_summary_table.csv`, `signal_ic_by_horizon.csv`, `signal_redundancy_matrix.csv`, `signal_incremental_contribution.csv`.
- R1-R4 outputs: `signal_decay_profiles.csv`, `r2_signal_validation_results.csv`, `signal_state_conditional_ic.csv`, `etf_pairs_cointegration_report.csv`.
- Regimes: `data/04_layer2b_risk_regime_engine/market_state_history.csv` with `calm_trend`, `neutral_mixed`, `recovery_fragile`, `recovery_confirmed`, and `stressed_panic`.
- ETF universe: 35 ETFs in `data/01_data_hub/universe_metadata.csv` with weekly/daily price and return files.
- Macro/VIX/attention files: `macro_weekly.csv` currently contains only dates; `vix_term_structure.csv` and `google_trends.csv` are usable.
- ML lab outputs: tabular ML, sequence models, transformers, cross-asset attention, ensembles, meta-labeling, triple-barrier, decision-focused, and RL outputs under `data/research/ml_lab/`.
- Production/candidate metrics: GGG is the production candidate pending review; registry still pins `improved_phase2b_regime_confidence_boost` as current production/rollback.

## Top 25 Signals To Test Next

| signal_name | category | data_access | priority_score | recommended_next_action | expected_best_regime | expected_bad_regime | repo_mapping |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Cyclicals vs defensives | G. Cross-Asset Leadership | free/current | 5 | test now | calm_trend, recovery_confirmed | stressed_panic | Layer 1 cross-sector leadership |
| Defensive sector leadership | J. Quality / Defensive | free/current | 5 | test now | stressed_panic | calm_trend | sector leadership/risk signal |
| Drawdown acceleration | E. Volatility / Risk | free/current | 5 | test now | early stress | recovery whipsaw | risk regime feature / Layer 1 meta |
| Risk-on breadth basket | F. Breadth / Participation | free/current | 5 | test now | calm_trend | stressed_panic | Layer 1 breadth/risk participation |
| Sector breadth using sector ETFs | F. Breadth / Participation | free/current | 5 | test now | calm_trend | sector concentration | Layer 1 sector breadth signal |
| Signal agreement score | M. Signal Quality / Meta Signals | free/current | 5 | test now | calm_trend, recovery_confirmed | signal crowding periods | meta Layer 1 diagnostic |
| Signal decay freshness | M. Signal Quality / Meta Signals | free/current | 5 | test now | all regimes | small samples | extend R1 rolling decay |
| Signal dispersion / disagreement | M. Signal Quality / Meta Signals | free/current | 5 | test now | neutral_mixed warning | strong trends if false | meta signal environment |
| Direct HY OAS level/change | D. Credit / Liquidity | free/API | 5 | test with free external data/API | stressed_panic detection | calm_trend false alarms | repair R2 credit ingestion |
| Equal-weight vs cap-weight SPY proxy | F. Breadth / Participation | free external | 5 | test with free external data/API | calm_trend, recovery_confirmed | mega-cap narrow rallies | add free external ETF input to data hub research |
| IG OAS level/change | D. Credit / Liquidity | free/API | 5 | test with free external data/API | early stress | calm_trend | credit macro signal |
| Real rates / TIPS yield trend | C. Macro / Cycle | free/API | 5 | test with free external data/API | neutral_mixed, stressed_panic | calm_trend growth melt-up | macro Layer 1 signal |
| Sahm rule / labor deterioration | C. Macro / Cycle | free/API | 5 | test with free external data/API | stressed_panic detection | calm_trend false positives | macro weekly ingestion + Layer 1 macro panel |
| VVIX vol-of-vol | E. Volatility / Risk | free/current | 5 | test with free external data/API | stressed_panic detection | calm_trend false positives | extend vix_term_structure inputs |
| % ETFs above 13/26/52w MA | F. Breadth / Participation | free/current | 4 | test now | calm_trend | narrow mega-cap rallies | ETF breadth proxy Layer 1/meta |
| Breakout / 52-week high proximity | A. Momentum / Trend | free/current | 4 | test now | calm_trend | neutral_mixed chop | new Layer 1 signal CSV + R2-style validation |
| Canary asset momentum composite | A. Momentum / Trend | free/current | 4 | test now | calm_trend, recovery_confirmed | false panic in neutral_mixed | Layer 1 cross-asset/global risk filter |
| Correlation spike / diversification failure | E. Volatility / Risk | free/current | 4 | test now | stressed_panic | calm_trend | Layer 1 meta/risk signal |
| Drawdown-adjusted momentum | A. Momentum / Trend | free/current | 4 | test now | calm_trend | recovery_fragile if too defensive | new Layer 1 price path quality signal |
| GLD/TLT safe-haven rotation | G. Cross-Asset Leadership | free/current | 4 | test now | stressed_panic, inflation stress | calm growth | safe-haven rotation Layer 1 |
| Google Trends fear expansion | K. Sentiment / Attention | free/current | 4 | test now | stressed_panic/recovery | calm_trend noise | complete IC validation for existing Google feature |
| IWM/SPY small-cap leadership | G. Cross-Asset Leadership | free/current | 4 | test now | recovery_confirmed, calm_trend | credit stress | cross-asset leadership signal |
| Moving-average slope acceleration | A. Momentum / Trend | free/current | 4 | test now | calm_trend, recovery_confirmed | stressed_panic | extend signal_moving_average_distance family |
| Realized volatility trend | E. Volatility / Risk | free/current | 4 | test now | stressed_panic detection | calm_trend | Layer 1 risk signal |
| Redundancy/crowding monitor | M. Signal Quality / Meta Signals | free/current | 4 | test now | all regimes | rapid regime shifts | rolling redundancy monitor |

## Test Immediately With Existing Data

| signal_name | category | short_hypothesis | priority_score | repo_mapping |
| --- | --- | --- | --- | --- |
| Cyclicals vs defensives | G. Cross-Asset Leadership | Cyclical sector leadership indicates growth/risk-on; defensives warn stress. | 5 | Layer 1 cross-sector leadership |
| Defensive sector leadership | J. Quality / Defensive | Utilities/staples/healthcare leadership can protect when risk appetite fades. | 5 | sector leadership/risk signal |
| Drawdown acceleration | E. Volatility / Risk | Acceleration of market drawdown may be more informative than drawdown level. | 5 | risk regime feature / Layer 1 meta |
| Risk-on breadth basket | F. Breadth / Participation | Risk-on ETFs confirming together should improve participation and avoid false breakouts. | 5 | Layer 1 breadth/risk participation |
| Sector breadth using sector ETFs | F. Breadth / Participation | More sectors in uptrend means healthier risk regime. | 5 | Layer 1 sector breadth signal |
| Signal agreement score | M. Signal Quality / Meta Signals | When independent signals agree, forward IC may improve and turnover need not rise. | 5 | meta Layer 1 diagnostic |
| Signal decay freshness | M. Signal Quality / Meta Signals | Recent IC decay should reduce trust in stale signals. | 5 | extend R1 rolling decay |
| Signal dispersion / disagreement | M. Signal Quality / Meta Signals | High cross-signal disagreement may identify bad signal environments. | 5 | meta signal environment |
| % ETFs above 13/26/52w MA | F. Breadth / Participation | ETF universe participation confirms whether risk-on is broad or narrow. | 4 | ETF breadth proxy Layer 1/meta |
| Breakout / 52-week high proximity | A. Momentum / Trend | ETF near breakout/high may indicate persistent institutional demand beyond raw momentum. | 4 | new Layer 1 signal CSV + R2-style validation |
| Canary asset momentum composite | A. Momentum / Trend | Risk assets should be held more aggressively only when canaries such as TIP/HYG/EEM confirm. | 4 | Layer 1 cross-asset/global risk filter |
| Correlation spike / diversification failure | E. Volatility / Risk | Cross-asset correlations rising toward one signal liquidity stress and lower diversification. | 4 | Layer 1 meta/risk signal |
| Drawdown-adjusted momentum | A. Momentum / Trend | A trend with shallow drawdowns is higher quality than the same trailing return with deep path damage. | 4 | new Layer 1 price path quality signal |
| GLD/TLT safe-haven rotation | G. Cross-Asset Leadership | Gold vs Treasuries separates inflationary stress from deflationary stress. | 4 | safe-haven rotation Layer 1 |
| Google Trends fear expansion | K. Sentiment / Attention | Retail fear search spikes may flag stress or contrarian rebound windows. | 4 | complete IC validation for existing Google feature |
| IWM/SPY small-cap leadership | G. Cross-Asset Leadership | Small-cap strength can signal broad risk appetite and recovery breadth. | 4 | cross-asset leadership signal |
| Moving-average slope acceleration | A. Momentum / Trend | Slope and acceleration of 13/26/52w MAs may catch improving trends earlier than level filters. | 4 | extend signal_moving_average_distance family |
| Realized volatility trend | E. Volatility / Risk | Rising realized vol lowers signal reliability and should penalize risky assets. | 4 | Layer 1 risk signal |
| Redundancy/crowding monitor | M. Signal Quality / Meta Signals | Rising correlation among signals lowers diversification and increases model fragility. | 4 | rolling redundancy monitor |
| Regime confidence / transition probability | M. Signal Quality / Meta Signals | Signals should be trusted more when regime classifier confidence is high. | 4 | state-conditional meta signal |
| TLT stress leadership | G. Cross-Asset Leadership | TLT rising while SPY/HYG weaken can identify flight-to-safety regimes. | 4 | risk leadership signal |
| Value vs growth spread | I. Value / Relative Valuation | VTV/VUG or RPV/RPG spread captures style cycle and rate sensitivity. | 4 | style leadership Layer 1 |
| Google inflation attention | K. Sentiment / Attention | Inflation search interest may proxy public inflation anxiety and commodity/TIPS demand. | 3 | Google Trends sub-signal |
| International ex-US leadership | G. Cross-Asset Leadership | EFA/EEM/VWO vs SPY leadership may identify global risk appetite and dollar sensitivity. | 3 | cross-asset leadership module |
| Panic reversal after volatility spike | B. Reversal / Mean Reversion | Large negative return plus high VIX/volume may predict short-term bounce in risky ETFs. | 3 | Layer 1 state-gated reversal |
| QQQ/SPY leadership | G. Cross-Asset Leadership | Growth leadership often marks calm risk-on participation but can become crowded. | 3 | Layer 1 leadership feature |
| RSI oversold bounce | B. Reversal / Mean Reversion | Weekly RSI extremes may capture ETF relief rallies after panic selling. | 3 | Layer 1 reversal candidate |
| Rolling Sharpe / return-to-risk rank | A. Momentum / Trend | Assets with positive return per unit volatility may be better candidates than raw winners. | 3 | promote from ML feature panel to inspectable Layer 1 candidate |
| State-gated 1-week reversal | B. Reversal / Mean Reversion | Short-term losers may rebound only in calm/neutral states, not panics. | 3 | R3 conditional wrapper around reversal_1w |
| Trend persistence / run length | A. Momentum / Trend | Consecutive positive trend weeks may identify persistent trends and avoid one-week noise. | 3 | Layer 1 path-state feature |

## Test With Free External Data/API

| signal_name | category | short_hypothesis | priority_score | repo_mapping |
| --- | --- | --- | --- | --- |
| Direct HY OAS level/change | D. Credit / Liquidity | High/widening HY spreads should penalize risky assets and improve stress detection. | 5 | repair R2 credit ingestion |
| Equal-weight vs cap-weight SPY proxy | F. Breadth / Participation | RSP/SPY leadership signals broader participation than cap-weight index. | 5 | add free external ETF input to data hub research |
| IG OAS level/change | D. Credit / Liquidity | Investment-grade spread widening may detect broad funding stress earlier than HY ETFs. | 5 | credit macro signal |
| Real rates / TIPS yield trend | C. Macro / Cycle | Rising real yields pressure duration/growth assets and favor cash/dollar/value. | 5 | macro Layer 1 signal |
| Sahm rule / labor deterioration | C. Macro / Cycle | Rising unemployment momentum identifies recession onset and should reduce risky ETF scores. | 5 | macro weekly ingestion + Layer 1 macro panel |
| VVIX vol-of-vol | E. Volatility / Risk | VIX-of-VIX spikes may detect unstable stress before VIX level fully reacts. | 5 | extend vix_term_structure inputs |
| AAII bull-bear spread | K. Sentiment / Attention | Extreme bearishness may be contrarian; extreme bullishness may warn complacency. | 4 | sentiment module |
| Bond real-yield valuation | I. Value / Relative Valuation | High real yields may make Treasuries more attractive and pressure equities. | 4 | bond valuation macro signal |
| Cash yield vs risk yield spread | H. Carry / Yield | When cash yield is high versus risky carry, hurdle for risk assets rises. | 4 | macro/carry opportunity cost signal |
| Credit carry after spread risk adjustment | H. Carry / Yield | Credit yield is useful only when spread widening risk is controlled. | 4 | carry + credit composite Layer 1 |
| Fed funds trend / policy pressure | C. Macro / Cycle | Rising policy rates and restrictive policy may alter equity/bond/commodity leadership. | 4 | macro ingestion |
| Funding stress proxy | D. Credit / Liquidity | Stress in funding/liquidity proxies should trigger defensive signal environment. | 4 | macro/liquidity module |
| Inflation surprise proxy | C. Macro / Cycle | Inflation acceleration favors commodities/TIPS/dollar and hurts duration/growth. | 4 | macro release calendar-aware signal |
| Inflation/deflation quadrant score | C. Macro / Cycle | Assets have biases to growth/inflation/liquidity; quadrant score may separate TLT/GLD/PDBC/SPY regimes. | 4 | macro regime research module |
| Low-volatility leadership | J. Quality / Defensive | Low-vol/defensive ETFs outperforming may warn risk deterioration. | 4 | external factor ETF leadership |
| VIX9D/VIX ratio | E. Volatility / Risk | Short-end vol pressure relative to 1m VIX may flag acute panic. | 4 | VIX term structure module |
| Yield curve 10y-3m recession probability | C. Macro / Cycle | Term spread inversion/disinversion captures late-cycle recession risk better than 2s10s alone. | 4 | improve macro builder |
| Balance-sheet safe-haven proxy | J. Quality / Defensive | ETF factor proxies for quality/low debt may reduce drawdowns. | 3 | factor ETF proxy panel |
| CAPE / equity valuation regime | I. Value / Relative Valuation | High equity valuation lowers long-horizon forward returns and raises crash sensitivity. | 3 | slow macro/value signal |
| Duration carry / curve rolldown proxy | H. Carry / Yield | Steep curve and falling-rate regimes may reward intermediate/long Treasury exposure. | 3 | bond carry macro signal |
| Industrial production / housing starts cycle | C. Macro / Cycle | Physical economy deterioration may flag cyclical risk and sector rotation. | 3 | macro module |
| Quality ETF leadership | J. Quality / Defensive | QUAL/SPY or similar may capture profitable balance-sheet preference. | 3 | factor ETF leadership module |
| Semiconductors/tech leadership | G. Cross-Asset Leadership | Semis leading tech can be early growth-cycle signal, but data needs SOXX/SMH. | 3 | optional external ETF input |

## Test Only If Paid PIT Data Is Available

| signal_name | category | short_hypothesis | priority_score | repo_mapping |
| --- | --- | --- | --- | --- |
| Advance/decline line | F. Breadth / Participation | More advancers than decliners improves forward market/sector return odds. | 4 | stock_breadth module |
| New highs/new lows stock breadth | F. Breadth / Participation | Expansion in new highs vs lows often confirms durable trend. | 4 | stock_breadth module |
| Cboe equity put/call ratio | K. Sentiment / Attention | High put demand may mark fear; low put/call may mark complacency. | 3 | sentiment/vol module |
| Industry participation breadth | F. Breadth / Participation | Industry-level breadth may reveal healthier rotation than sector-level aggregates. | 3 | stock_breadth module |
| PMI/ISM growth proxy | C. Macro / Cycle | Manufacturing/services momentum may improve cyclical sector/commodity leadership. | 3 | macro module |
| Sector valuation spreads | I. Value / Relative Valuation | Cheap sectors may outperform when trend/quality confirm. | 3 | sector valuation module |
| Treasury liquidity / MOVE proxy | D. Credit / Liquidity | Bond vol/liquidity stress can hurt duration and risk assets simultaneously. | 3 | risk module |
| ETF flows proxy | K. Sentiment / Attention | Large flows into/out of ETFs may indicate crowding or capitulation. | 2 | flows module |

## Research-Only / High-Risk

| signal_name | category | short_hypothesis | priority_score | repo_mapping |
| --- | --- | --- | --- | --- |
| Autoencoder latent factors | N. ML / Representation Signals | Unsupervised latent factors may reveal hidden ETF regimes/orthogonal risk drivers. | 3 | ML lab latent factor module |
| Expanded ETF universe momentum breadth | F. Breadth / Participation | A broader ETF universe may reveal participation outside current 35 ETFs. | 3 | research universe inventory |
| Model confidence / entropy | M. Signal Quality / Meta Signals | Low-confidence predictions should shrink risk or skip ML sleeves. | 3 | ML lab diagnostics |
| Triple-barrier meta-labels | N. ML / Representation Signals | Path-aware labels can identify when a base signal is worth trusting. | 3 | ML lab only |
| Commodity roll proxy via ETF futures funds | H. Carry / Yield | Commodity ETF term/roll behavior may indicate carry/backwardation regimes. | 2 | commodity signal module |
| Credit-equity divergence | D. Credit / Liquidity | If equities rise while credit weakens, risk rally may be fragile. | 2 | R2 diagnostics |
| Cross-asset attention weights | N. ML / Representation Signals | Attention may learn leader/follower relationships across ETFs. | 2 | ML lab only |
| FOMC drift / Fed week | L. Seasonality / Calendar | Returns may differ around scheduled Fed meetings. | 2 | calendar module |
| Month-of-year seasonality | L. Seasonality / Calendar | Some months have persistent risk premia or tax/liquidity patterns. | 2 | calendar diagnostic |
| Sequence model embedding | N. ML / Representation Signals | Recent ETF paths may encode trend/reversal states better than hand-built features. | 2 | ML lab only |
| Tabular ML ranker using simple signal zoo | N. ML / Representation Signals | A regularized model may combine many weak signals into an ETF rank. | 2 | ML lab only |
| Tax-loss rebound | L. Seasonality / Calendar | Prior-year losers may rebound in January after tax-loss selling. | 2 | calendar diagnostic |
| ETF pair spread z-score | B. Reversal / Mean Reversion | Cointegrated ETF pairs may mean-revert at weekly frequency in limited cases. | 1 | R4 pair lab |
| News sentiment / LLM macro sentiment | K. Sentiment / Attention | News tone may capture macro stress, but source stability and lookahead are hard. | 1 | separate research sandbox |

## Avoid

| signal_name | category | short_hypothesis | priority_score | repo_mapping |
| --- | --- | --- | --- | --- |
| Decision-focused learning | N. ML / Representation Signals | Directly optimizing portfolio utility may align model with objective but risks learning cash/bond hiding. | 1 | ML lab only |
| ETF price-to-own-history value | I. Value / Relative Valuation | Assets far below long-term trend may be cheap, but can be value traps. | 1 | existing value signal |
| Election cycle regime | L. Seasonality / Calendar | Policy uncertainty and liquidity differ by election year. | 1 | none |
| Holiday-week risk appetite | L. Seasonality / Calendar | Short holiday weeks and year-end may have flow effects. | 1 | none |
| Intraday gap/overnight effect | L. Seasonality / Calendar | Open-to-close vs close-to-open may contain information, but repo is weekly close-based. | 1 | none |
| Reinforcement learning allocator | N. ML / Representation Signals | RL can learn dynamic allocation but has extremely high overfit risk in short financial histories. | 1 | ML lab only |

## Full Backlog By Category

### A. Momentum / Trend

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Breakout / 52-week high proximity | ETF near breakout/high may indicate persistent institutional demand beyond raw momentum. | free/current | 2-8 weeks | calm_trend | neutral_mixed chop | no | moving_average_distance adjacent | 4 | test now |
| Canary asset momentum composite | Risk assets should be held more aggressively only when canaries such as TIP/HYG/EEM confirm. | free/current | 1-8 weeks | calm_trend, recovery_confirmed | false panic in neutral_mixed | partial | market_state_history has canary breadth fields | 4 | test now |
| Drawdown-adjusted momentum | A trend with shallow drawdowns is higher quality than the same trailing return with deep path damage. | free/current | 4-13 weeks | calm_trend | recovery_fragile if too defensive | partial | contained_recovery_quality adjacent | 4 | test now |
| Moving-average slope acceleration | Slope and acceleration of 13/26/52w MAs may catch improving trends earlier than level filters. | free/current | 2-8 weeks | calm_trend, recovery_confirmed | stressed_panic | partial | moving_average_distance | 4 | test now |
| Rolling Sharpe / return-to-risk rank | Assets with positive return per unit volatility may be better candidates than raw winners. | free/current | 4-13 weeks | calm_trend | volatility regime shifts | partial in ML features | ml_feature_panel has rolling Sharpe | 3 | test now |
| Trend persistence / run length | Consecutive positive trend weeks may identify persistent trends and avoid one-week noise. | free/current | 2-8 weeks | calm_trend | late-cycle exhaustion | no | trend_clarity_momentum adjacent | 3 | test now |
| TSMOM 6/12-month ensemble | Own past returns should predict medium-term ETF relative/absolute returns when trend persists. | free/current | 4-13 weeks | calm_trend, recovery_confirmed | stressed_panic whipsaws | yes | signal_tsmom, signal_multi_horizon_mom | 2 | test later |
| Volatility-adjusted momentum refresh | Momentum scaled by realized vol may preserve trend upside while lowering crash exposure. | free/current | 4-13 weeks | calm_trend | stressed_panic if vol spike lags | yes | tsmom_vol_scaled | 2 | test later |
| Volume-confirmed breakout | Breakouts with abnormal volume may be more durable than price-only breakouts. | free/current | 2-8 weeks | calm_trend | stressed_panic false break | partial volume R2 failed | signal_r2_volume_divergence | 2 | test later |

### B. Reversal / Mean Reversion

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Panic reversal after volatility spike | Large negative return plus high VIX/volume may predict short-term bounce in risky ETFs. | free/current | 1-2 weeks | recovery_fragile | stressed_panic continuation | no | reversal and VIX R2 adjacent | 3 | test now |
| RSI oversold bounce | Weekly RSI extremes may capture ETF relief rallies after panic selling. | free/current | 1-4 weeks | recovery_fragile, neutral_mixed | stressed_panic continuation | no | reversal_1w/4w adjacent | 3 | test now |
| State-gated 1-week reversal | Short-term losers may rebound only in calm/neutral states, not panics. | free/current | 1-2 weeks | neutral_mixed | stressed_panic | yes base signal | reversal_1w_global | 3 | test now |
| Distance-from-MA z-score reversal | Extreme distance below medium-term MA may mean-revert when state is not stressed. | free/current | 1-4 weeks | neutral_mixed, recovery_fragile | stressed_panic | partial | moving_average_distance | 2 | test later |
| Liquidity shock rebound | ETFs with unusually high volume and negative return may rebound if market state stabilizes. | free/current | 1-4 weeks | recovery_fragile | stressed_panic | partial R2 volume failed | signal_r2_volume_divergence | 2 | test later |
| ETF pair spread z-score | Cointegrated ETF pairs may mean-revert at weekly frequency in limited cases. | free/current | 1-8 weeks | neutral_mixed | trending regimes | yes R4 | signal_r4_pair_hyg_lqd | 1 | research-only |

### C. Macro / Cycle

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Real rates / TIPS yield trend | Rising real yields pressure duration/growth assets and favor cash/dollar/value. | free/API | 4-26 weeks | neutral_mixed, stressed_panic | calm_trend growth melt-up | no | TIP exists; no direct real-rate signal | 5 | test with free external data/API |
| Sahm rule / labor deterioration | Rising unemployment momentum identifies recession onset and should reduce risky ETF scores. | free/API | 4-26 weeks | stressed_panic detection | calm_trend false positives | no | market_state uses stress proxies but not Sahm | 5 | test with free external data/API |
| Fed funds trend / policy pressure | Rising policy rates and restrictive policy may alter equity/bond/commodity leadership. | free/API | 13-52 weeks | late-cycle/stress detection | early recovery | no | macro_weekly empty | 4 | test with free external data/API |
| Inflation surprise proxy | Inflation acceleration favors commodities/TIPS/dollar and hurts duration/growth. | free/API | 13-52 weeks | inflationary calm/reflation | disinflationary recovery | partial commodity R2 | signal_r2_commodity_regime adjacent | 4 | test with free external data/API |
| Inflation/deflation quadrant score | Assets have biases to growth/inflation/liquidity; quadrant score may separate TLT/GLD/PDBC/SPY regimes. | free/API | 13-52 weeks | macro transitions | fast shocks | no | regime states adjacent | 4 | test with free external data/API |
| Yield curve 10y-3m recession probability | Term spread inversion/disinversion captures late-cycle recession risk better than 2s10s alone. | free/API | 13-52 weeks | early stress detection | calm_trend false positives | partial R2 2s10s | signal_r2_yield_curve | 4 | test with free external data/API |
| Financial conditions index state gate | Tightening financial conditions should reduce risk-on signal trust. | free/API | 4-26 weeks | early stress detection | calm_trend if too cautious | yes R2 rejected unconditional | signal_r2_financial_conditions | 3 | test later |
| Industrial production / housing starts cycle | Physical economy deterioration may flag cyclical risk and sector rotation. | free/API | 13-52 weeks | cycle transitions | fast shocks | no | none | 3 | test with free external data/API |
| PMI/ISM growth proxy | Manufacturing/services momentum may improve cyclical sector/commodity leadership. | paid/partial free | 13-26 weeks | recovery_confirmed, calm_trend | stressed_panic | no | none | 3 | needs paid data |

### D. Credit / Liquidity

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Direct HY OAS level/change | High/widening HY spreads should penalize risky assets and improve stress detection. | free/API | 4-26 weeks | stressed_panic detection | calm_trend false alarms | partial R2 proxy | signal_r2_credit_spread | 5 | test with free external data/API |
| IG OAS level/change | Investment-grade spread widening may detect broad funding stress earlier than HY ETFs. | free/API | 4-26 weeks | early stress | calm_trend | no | LQD exists | 5 | test with free external data/API |
| Funding stress proxy | Stress in funding/liquidity proxies should trigger defensive signal environment. | free/API | 1-13 weeks | stressed_panic | normal calm | no | none | 4 | test with free external data/API |
| HYG/LQD credit momentum | Credit risk appetite improves when HYG outperforms LQD. | free/current | 2-13 weeks | calm_trend, recovery_confirmed | stressed_panic | partial R2/R4 | r2_credit_spread proxy; HYG/LQD pair | 3 | test later |
| Treasury liquidity / MOVE proxy | Bond vol/liquidity stress can hurt duration and risk assets simultaneously. | paid/partial free | 1-13 weeks | stressed_panic | calm_trend | no | none | 3 | needs paid data |
| Credit-equity divergence | If equities rise while credit weakens, risk rally may be fragile. | free/current | 1-8 weeks | neutral_mixed warning | calm_trend strong breadth | yes R2 rejected | r2_cross_asset_divergence | 2 | research-only |

### E. Volatility / Risk

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Drawdown acceleration | Acceleration of market drawdown may be more informative than drawdown level. | free/current | 1-8 weeks | early stress | recovery whipsaw | partial regime | market_drawdown | 5 | test now |
| VVIX vol-of-vol | VIX-of-VIX spikes may detect unstable stress before VIX level fully reacts. | free/current | 1-8 weeks | stressed_panic detection | calm_trend false positives | no | vix_term_structure adjacent | 5 | test with free external data/API |
| Correlation spike / diversification failure | Cross-asset correlations rising toward one signal liquidity stress and lower diversification. | free/current | 1-8 weeks | stressed_panic | calm_trend | partial regime | market_state avg_corr_risk_off_z | 4 | test now |
| Realized volatility trend | Rising realized vol lowers signal reliability and should penalize risky assets. | free/current | 1-13 weeks | stressed_panic detection | calm_trend | partial quality | signal_quality | 4 | test now |
| VIX9D/VIX ratio | Short-end vol pressure relative to 1m VIX may flag acute panic. | free/current | 1-4 weeks | stressed_panic | normal calm | no | vix_term_structure adjacent | 4 | test with free external data/API |
| Volatility compression breakout | Low realized vol followed by expansion can precede trend continuation or risk break. | free/current | 1-8 weeks | calm_trend breakout | stressed_panic whipsaw | no | none | 3 | test now |
| Downside semivolatility | Downside-only volatility better captures bad path risk than total volatility. | free/current | 4-13 weeks | stressed_panic protection | calm_trend underparticipation | yes quality | signal_quality | 2 | test later |
| Volatility-managed momentum | Scale momentum signal by inverse realized vol to avoid noisy high-vol states. | free/current | 4-13 weeks | calm_trend | stressed_panic if lagging | partial | tsmom_vol_scaled | 2 | test later |

### F. Breadth / Participation

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Equal-weight vs cap-weight SPY proxy | RSP/SPY leadership signals broader participation than cap-weight index. | free external | 4-13 weeks | calm_trend, recovery_confirmed | mega-cap narrow rallies | no | none | 5 | test with free external data/API |
| Risk-on breadth basket | Risk-on ETFs confirming together should improve participation and avoid false breakouts. | free/current | 2-8 weeks | calm_trend | stressed_panic | partial | market_state canary/breadth fields | 5 | test now |
| Sector breadth using sector ETFs | More sectors in uptrend means healthier risk regime. | free/current | 4-13 weeks | calm_trend | sector concentration | partial sector phases | sector ETFs present | 5 | test now |
| % ETFs above 13/26/52w MA | ETF universe participation confirms whether risk-on is broad or narrow. | free/current | 2-13 weeks | calm_trend | narrow mega-cap rallies | partial | breadth_confirmed_momentum and regime breadth | 4 | test now |
| Advance/decline line | More advancers than decliners improves forward market/sector return odds. | paid/partial free | 1-8 weeks | calm_trend, recovery_confirmed | stressed_panic | no | none | 4 | needs paid data |
| New highs/new lows stock breadth | Expansion in new highs vs lows often confirms durable trend. | paid | 2-13 weeks | calm_trend | false breadth rebounds | prototype only | stock_breadth scaffold exists | 4 | needs paid data |
| Expanded ETF universe momentum breadth | A broader ETF universe may reveal participation outside current 35 ETFs. | free/current | 4-13 weeks | calm_trend | survivorship/universe drift | partial ML lab | expanded_universe exists | 3 | research-only |
| Industry participation breadth | Industry-level breadth may reveal healthier rotation than sector-level aggregates. | paid | 4-13 weeks | calm_trend | narrow rallies | no | none | 3 | needs paid data |

### G. Cross-Asset Leadership

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cyclicals vs defensives | Cyclical sector leadership indicates growth/risk-on; defensives warn stress. | free/current | 4-13 weeks | calm_trend, recovery_confirmed | stressed_panic | no | sector ETFs present | 5 | test now |
| GLD/TLT safe-haven rotation | Gold vs Treasuries separates inflationary stress from deflationary stress. | free/current | 4-26 weeks | stressed_panic, inflation stress | calm growth | partial R4 pair rejected | GLD/TLT pair rejected as stat-arb | 4 | test now |
| IWM/SPY small-cap leadership | Small-cap strength can signal broad risk appetite and recovery breadth. | free/current | 4-13 weeks | recovery_confirmed, calm_trend | credit stress | partial R4 | IWM/SPY pair rejected as stat-arb | 4 | test now |
| TLT stress leadership | TLT rising while SPY/HYG weaken can identify flight-to-safety regimes. | free/current | 1-8 weeks | stressed_panic | inflation shock | partial R2/R4 | cross_asset_divergence/pairs | 4 | test now |
| International ex-US leadership | EFA/EEM/VWO vs SPY leadership may identify global risk appetite and dollar sensitivity. | free/current | 4-13 weeks | global calm/recovery | USD stress | partial via xsmom | existing ETFs | 3 | test now |
| QQQ/SPY leadership | Growth leadership often marks calm risk-on participation but can become crowded. | free/current | 2-13 weeks | calm_trend | rate shock/stressed_panic | partial pairs | existing ETFs | 3 | test now |
| Semiconductors/tech leadership | Semis leading tech can be early growth-cycle signal, but data needs SOXX/SMH. | free external | 4-13 weeks | calm_trend | rate shock | no | none | 3 | test with free external data/API |
| USD leads EM/commodities | UUP strength may predict EM and commodity weakness. | free/current | 4-13 weeks | stress/disinflation | commodity bull | yes R2 dollar | r2_dollar_strength | 3 | test later |

### H. Carry / Yield

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cash yield vs risk yield spread | When cash yield is high versus risky carry, hurdle for risk assets rises. | free/API + existing | 13-52 weeks | late cycle/stress | early bull | no | BIL weights in portfolio | 4 | test with free external data/API |
| Credit carry after spread risk adjustment | Credit yield is useful only when spread widening risk is controlled. | free/API + existing | 13-52 weeks | calm_trend | stressed_panic | no | carry_proxy, credit spread | 4 | test with free external data/API |
| Duration carry / curve rolldown proxy | Steep curve and falling-rate regimes may reward intermediate/long Treasury exposure. | free/API | 13-52 weeks | disinflation/recession | inflation stress | no | none | 3 | test with free external data/API |
| Commodity roll proxy via ETF futures funds | Commodity ETF term/roll behavior may indicate carry/backwardation regimes. | free/paid | 13-52 weeks | inflation/commodity bull | contango bleed | partial commodity R2 | r2_commodity_regime | 2 | research-only |
| Currency carry proxy | USD/rate differential carry may affect UUP and international ETF leadership. | free/partial | 13-52 weeks | calm carry | global crisis unwind | no | r2_dollar_strength adjacent | 2 | test later |
| ETF distribution yield carry | Higher trailing ETF yield may proxy carry, especially bonds/credit/dividends. | free/current | 13-52 weeks | calm_trend, income regimes | stress if yield traps | yes weak | signal_carry | 2 | test later |

### I. Value / Relative Valuation

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Bond real-yield valuation | High real yields may make Treasuries more attractive and pressure equities. | free/API | 13-52 weeks | late tightening/recession | inflation shock | no | none | 4 | test with free external data/API |
| Value vs growth spread | VTV/VUG or RPV/RPG spread captures style cycle and rate sensitivity. | free/current | 4-26 weeks | rate rise/value cycle | growth melt-up | no | VTV/VUG in universe | 4 | test now |
| CAPE / equity valuation regime | High equity valuation lowers long-horizon forward returns and raises crash sensitivity. | free/paid | 52+ weeks | long-horizon allocation | short-horizon momentum | no | value_proxy price-only | 3 | test with free external data/API |
| Sector valuation spreads | Cheap sectors may outperform when trend/quality confirm. | paid/partial free | 13-52 weeks | recovery_confirmed, value rotation | growth mania | no | sector ETFs only | 3 | needs paid data |
| ETF price-to-own-history value | Assets far below long-term trend may be cheap, but can be value traps. | free/current | 13-52 weeks | recovery_confirmed | stressed_panic | yes weak | signal_value | 1 | avoid |

### J. Quality / Defensive

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Defensive sector leadership | Utilities/staples/healthcare leadership can protect when risk appetite fades. | free/current | 2-13 weeks | stressed_panic | calm_trend | no | sector ETFs present | 5 | test now |
| Low-volatility leadership | Low-vol/defensive ETFs outperforming may warn risk deterioration. | free external | 4-13 weeks | stressed_panic, neutral_mixed | speculative calm | partial quality/BAB | quality_proxy, bab_proxy | 4 | test with free external data/API |
| Balance-sheet safe-haven proxy | ETF factor proxies for quality/low debt may reduce drawdowns. | free external | 4-26 weeks | stressed_panic | momentum-led calm | no | none | 3 | test with free external data/API |
| Quality ETF leadership | QUAL/SPY or similar may capture profitable balance-sheet preference. | free external | 4-26 weeks | late cycle/stress | high-beta melt-up | no | quality_proxy price-risk | 3 | test with free external data/API |
| BAB extension with funding stress | Low-beta leadership may matter most when funding stress rises. | free/API | 4-26 weeks | stressed_panic | calm_trend | partial weak | bab_proxy weak | 2 | test later |

### K. Sentiment / Attention

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AAII bull-bear spread | Extreme bearishness may be contrarian; extreme bullishness may warn complacency. | free/manual | 4-13 weeks | recovery_fragile contrarian | stressed_panic continuation | no | none | 4 | test with free external data/API |
| Google Trends fear expansion | Retail fear search spikes may flag stress or contrarian rebound windows. | free/current | 1-8 weeks | stressed_panic/recovery | calm_trend noise | partial manifest no IC rows | google_trends.csv, google_fear_regime | 4 | test now |
| Cboe equity put/call ratio | High put demand may mark fear; low put/call may mark complacency. | partial free/paid | 1-8 weeks | recovery_fragile/stress warning | calm_trend | no | none | 3 | needs paid data |
| Google inflation attention | Inflation search interest may proxy public inflation anxiety and commodity/TIPS demand. | free/current | 4-26 weeks | inflationary stress | normal calm | no explicit | google_trends inflation column | 3 | test now |
| ETF flows proxy | Large flows into/out of ETFs may indicate crowding or capitulation. | paid/partial free | 4-13 weeks | crowding/stress | normal regimes | no | none | 2 | needs paid data |
| Retail attention volume/search hybrid | Search interest plus ETF volume may identify retail chase/capitulation. | free/current | 1-8 weeks | recovery/panic | calm noise | partial volume R2 | google_trends + volume divergence | 2 | test later |
| News sentiment / LLM macro sentiment | News tone may capture macro stress, but source stability and lookahead are hard. | free/paid | 1-8 weeks | stress transitions | normal chop | no | none | 1 | research-only |

### L. Seasonality / Calendar

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Turn-of-month effect | Equity returns may concentrate around month-end/month-start flows. | free/current | 1-4 weeks | calm_trend | stress overrides | no | none | 3 | test now |
| FOMC drift / Fed week | Returns may differ around scheduled Fed meetings. | free/manual | 1-2 weeks | calm liquidity | surprise stress | no | none | 2 | research-only |
| Month-of-year seasonality | Some months have persistent risk premia or tax/liquidity patterns. | free/current | 4-13 weeks | varies | regime breaks | no | none | 2 | research-only |
| Tax-loss rebound | Prior-year losers may rebound in January after tax-loss selling. | free/current | 4-8 weeks | January/recovery | tax regime changes | no | none | 2 | research-only |
| Election cycle regime | Policy uncertainty and liquidity differ by election year. | free/current | 13-52 weeks | varies | small sample | no | none | 1 | avoid |
| Holiday-week risk appetite | Short holiday weeks and year-end may have flow effects. | free/current | 1 week | calm_trend | stress overrides | no | none | 1 | avoid |
| Intraday gap/overnight effect | Open-to-close vs close-to-open may contain information, but repo is weekly close-based. | free external | 1-4 weeks | unknown | all | no | daily prices only no OHLC | 1 | avoid |

### M. Signal Quality / Meta Signals

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Signal agreement score | When independent signals agree, forward IC may improve and turnover need not rise. | free/current | 1-13 weeks | calm_trend, recovery_confirmed | signal crowding periods | partial | composite signals exist | 5 | test now |
| Signal decay freshness | Recent IC decay should reduce trust in stale signals. | free/current | 13-52 weeks | all regimes | small samples | partial R1 | signal_decay_profiles | 5 | test now |
| Signal dispersion / disagreement | High cross-signal disagreement may identify bad signal environments. | free/current | 1-13 weeks | neutral_mixed warning | strong trends if false | no | none | 5 | test now |
| Bad-signal-environment classifier | Predict weeks when the signal panel historically has low IC or stress damage. | free/current | 1-13 weeks | neutral_mixed/stress transition | small samples | partial ML lab | phase_jj/kk/nnn ML outputs | 4 | test later |
| Redundancy/crowding monitor | Rising correlation among signals lowers diversification and increases model fragility. | free/current | 13-52 weeks | all regimes | rapid regime shifts | partial static redundancy | signal_redundancy_matrix | 4 | test now |
| Regime confidence / transition probability | Signals should be trusted more when regime classifier confidence is high. | free/current | 1-13 weeks | state-specific | transition chop | yes partial | transition_* fields | 4 | test now |
| Liquidity-adjusted ETF signal quality | Thin/low-volume ETFs may have noisier signals and worse realized implementation. | free/paid | 1-13 weeks | all regimes | market stress | no | none | 3 | test later |
| Model confidence / entropy | Low-confidence predictions should shrink risk or skip ML sleeves. | free/current | 1-13 weeks | all regimes | overfit ML | yes ML lab | triple_barrier/ML outputs | 3 | research-only |

### N. ML / Representation Signals

| signal_name | short_hypothesis | data_access | expected_horizon | expected_best_regime | expected_bad_regime | already_tested_in_project | similar_signal_exists_in_current_repo | priority_score | recommended_next_action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Autoencoder latent factors | Unsupervised latent factors may reveal hidden ETF regimes/orthogonal risk drivers. | free/current | 13-52 weeks | regime diagnostics | overfit latent noise | partial PPP latent factors | phase_ppp artifacts | 3 | research-only |
| Triple-barrier meta-labels | Path-aware labels can identify when a base signal is worth trusting. | free/current | 4-13 weeks | all regimes | small sample/overfit | yes ML lab | triple_barrier_meta | 3 | research-only |
| Cross-asset attention weights | Attention may learn leader/follower relationships across ETFs. | free/current | 4-13 weeks | cross-asset regimes | small sample | yes ML lab | cross_asset_attention | 2 | research-only |
| Sequence model embedding | Recent ETF paths may encode trend/reversal states better than hand-built features. | free/current | 4-13 weeks | calm_trend | regime shifts | yes ML lab | sequence_models/transformers | 2 | research-only |
| Tabular ML ranker using simple signal zoo | A regularized model may combine many weak signals into an ETF rank. | free/current | 4-13 weeks | calm_trend | regime shifts | yes ML lab | tabular_ml/learning_to_rank | 2 | research-only |
| Decision-focused learning | Directly optimizing portfolio utility may align model with objective but risks learning cash/bond hiding. | free/current | 4-13 weeks | unknown | overfit/objective gaming | yes ML lab | decision_focused | 1 | avoid |
| Reinforcement learning allocator | RL can learn dynamic allocation but has extremely high overfit risk in short financial histories. | free/current | 4-52 weeks | unknown | regime shifts | yes ML lab | reinforcement_learning | 1 | avoid |

## Direct Answers

1. **Are there many more signals worth testing beyond dollar strength?** Yes. The highest-quality backlog is not another turnover lever; it is better public-data information: sector/risk-on breadth, defensive leadership, real rates, credit spreads, Sahm/labor deterioration, VVIX/short-vol structure, signal agreement, and signal decay freshness.
2. **Which signals should be tested next before R5?** Test the immediate-data group first: sector breadth, risk-on breadth, defensive sector leadership, cyclicals-vs-defensives, signal agreement, signal dispersion, signal decay freshness, drawdown acceleration, rolling correlation spike, and value-vs-growth leadership.
3. **Most likely to help calm_trend:** sector breadth, risk-on breadth, breakout/high proximity, moving-average slope acceleration, cyclicals-vs-defensives, QQQ/SPY leadership, and RSP/SPY breadth once RSP is added.
4. **Most likely to protect stressed_panic:** defensive sector leadership, Sahm/labor deterioration, direct HY/IG OAS, VVIX, VIX9D/VIX ratio, drawdown acceleration, correlation spike, real rates, and funding stress proxies.
5. **Require PIT data:** stock-level new highs/lows, advance/decline line, industry participation, sector valuation spreads, ETF flows, and any constituent-level quality/profitability/valuation signals.
6. **Probably exhausted already:** raw TSMOM, cross-sectional momentum, multi-horizon momentum, simple price-only value, raw carry, BAB/quality as currently proxied, and weekly ETF pair stat-arb.
7. **Realistic Renaissance-style ideas here:** broad idea generation, strict rejection, signal decay monitoring, redundancy/crowding checks, state-conditional IC, purged/walk-forward validation, and meta-signals that measure when signals are stale or disagree.
8. **Not realistic here:** HFT, market making, proprietary order flow, tick microstructure, intraday execution alpha, current-constituent stock breadth as production evidence, and large black-box ML before simple public-data signals are exhausted.
9. **Next implementation sprint:** build `R5-pre` signal discovery implementation for the top existing/free data candidates, still research-only: sector/risk-on breadth, defensive leadership, real-rates/Sahm/HY+IG spreads, VVIX/VIX9D, and signal agreement/dispersion/freshness.

## Production Safety

This sprint created only backlog/research files. It did not modify production pins, dashboard/public files, production portfolio artifacts, or live trading/execution logic.
