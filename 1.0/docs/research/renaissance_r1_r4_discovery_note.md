# Renaissance R1-R4 Discovery Note

Research-only overnight sprint setup for phases R1-R4. This note was written before adding the sprint scripts.

## Repository map

- Existing Layer 1 signal research: `data/02_layer1_signals/`
- ETF prices, returns, macro, and VIX inputs: `data/01_data_hub/`
- Regime and market-state history: `data/04_layer2b_risk_regime_engine/`
- Portfolio returns, weights, candidate metrics, and production registry: `data/05_layer3_portfolio_construction/`
- Research reports: `docs/research/`
- Production/dashboard files intentionally excluded from this sprint: `public/`, `src/`, dashboard bundles, production registry edits, and production portfolio artifacts.

## Identified source files

| Requirement | File(s) identified | Notes |
| --- | --- | --- |
| Existing signal manifest | `data/02_layer1_signals/signal_manifest.json` | 25 manifest entries; includes several regime-feature entries not present in the summary table. |
| Signal IC by horizon | `data/02_layer1_signals/signal_ic_by_horizon.csv` | Existing horizons include 1, 2, 4, 8, and 13 weeks for 22 summary-table signals. |
| Signal redundancy matrix | `data/02_layer1_signals/signal_redundancy_matrix.csv` | Wide matrix with signal names as index in the first column. |
| Signal summary table | `data/02_layer1_signals/signal_summary_table.csv` | 22 validated signals with IC, Newey-West t-stat, redundancy, quality score, and recommendation. |
| Signal incremental contribution | `data/02_layer1_signals/signal_incremental_contribution.csv` | Contains base-plus-one incremental tests for a subset of signals. |
| Regime/market state history | `data/04_layer2b_risk_regime_engine/market_state_history.csv`; optional refined file `market_state_history_refined.csv` | The canonical five-state labels are in `market_state`: `calm_trend`, `neutral_mixed`, `recovery_fragile`, `recovery_confirmed`, and `stressed_panic`. |
| ETF price/return files | `data/01_data_hub/weekly_prices.csv`, `weekly_returns.csv`, `daily_prices.csv`, `daily_returns.csv` | Weekly prices/returns are the primary validation index; daily files have prices/returns only, not volume. |
| Macro weekly files | `data/01_data_hub/macro_weekly.csv` | Present but currently only contains `Date`, so macro scripts must fall back to FRED/public FRED CSVs when possible. |
| VIX term structure files | `data/01_data_hub/vix_term_structure.csv` | Contains `VIX`, `VIX3M`, `VIX6M`, slopes, `contango`, and `stress_flag`. |
| Portfolio return/weight files | `data/05_layer3_portfolio_construction/portfolio_version_returns_*.csv`; `portfolio_version_weights_*.csv` | GGG and Phase 2B return/weight artifacts both exist. These are read-only for this sprint. |
| Production/candidate metrics | `data/05_layer3_portfolio_construction/production_candidate_registry.json`, `production_candidate_summary.csv`, `portfolio_version_comparison.csv` | Registry still pins `improved_phase2b_regime_confidence_boost` as current production/rollback and lists `improved_phaseggg_confirmed_only_robust_offense` as production candidate pending human review. |

## Benchmark finding

The dashboard production candidate named in the prompt is confirmed in `production_candidate_summary.csv`:

- `improved_phaseggg_confirmed_only_robust_offense`
- Annual return: 7.14%
- Annual volatility: 7.62%
- Sharpe: 0.94
- Max drawdown: -11.77%
- Calmar: 0.61
- CVaR 5%: -2.54%
- Weekly turnover: 12.36%

There is a registry mismatch to explain in reports: `production_candidate_registry.json` still lists `improved_phase2b_regime_confidence_boost` as `current_production_pin` and rollback. R1-R4 reports should therefore treat GGG as the dashboard production candidate benchmark while also showing the pinned Phase 2B metrics where benchmark context matters.

## Initial data limitations

- `macro_weekly.csv` has no usable macro series beyond dates; yield curve, credit spread, and financial-conditions signals need FRED/public-FRED fallback or must be marked partial/skipped with exact reasons.
- Existing project data does not include volume columns; ETF volume divergence must use yfinance if available. If that pull fails, the volume signal must be written with warnings and validation should mark the signal skipped/research-only rather than disappearing silently.
- Existing Layer 1 signals already provide tradable columns. New R2/R4 signals will explicitly write observed and one-period-lagged tradable values to avoid lookahead.

## Scope guardrails

This sprint is research-only. It will not implement R5/R6/R7/R8, change production pins, modify dashboard or public files, overwrite production portfolio artifacts, promote candidates, or add live trading/execution logic.
