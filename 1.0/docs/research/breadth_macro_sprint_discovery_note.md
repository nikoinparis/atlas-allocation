# Breadth + State-Gated Macro Sprint Discovery Note

Research-only inventory before implementation. This sprint is scoped to signal construction, state-conditional validation, and priority ranking. It does not change production pins, dashboard/public files, portfolio artifacts, or allocation logic.

## Repo Inputs Inspected

- Existing R1-R4 outputs:
  - `data/02_layer1_signals/signal_decay_profiles.csv`
  - `data/02_layer1_signals/r2_signal_validation_results.csv`
  - `data/02_layer1_signals/signal_state_conditional_ic.csv`
  - `data/02_layer1_signals/etf_pairs_cointegration_report.csv`
  - `docs/research/r1_signal_decay_report.md`
  - `docs/research/r2_signal_validation_report.md`
  - `docs/research/state_conditional_signal_report.md`
  - `docs/research/etf_pairs_signal_report.md`
- Market state history:
  - `data/04_layer2b_risk_regime_engine/market_state_history.csv`
  - Key state labels include calm_trend, neutral_mixed, recovery_fragile, recovery_confirmed, and stressed_panic.
- ETF universe and prices:
  - `data/01_data_hub/weekly_prices.csv`
  - `data/01_data_hub/weekly_returns.csv`
  - `data/01_data_hub/daily_prices.csv`
  - `data/01_data_hub/universe_metadata.csv`
  - Universe metadata currently lists 35 ETFs.
- Sector ETF availability:
  - Available sector ETFs in weekly prices: XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY.
  - Missing requested sector ETFs: XLC and XLRE. Scripts should warn and continue.
- Macro/VIX/attention files:
  - `data/01_data_hub/macro_weekly.csv` exists but currently has only `Date`, so it is a date spine rather than a populated macro panel.
  - `data/01_data_hub/vix_term_structure.csv` includes VIX, VIX3M, VIX6M, slopes, contango, and stress flag columns.
  - `data/01_data_hub/google_trends.csv` includes fear-term levels and z-scores.
  - Existing R2 macro/VIX/credit candidates are available as panel CSVs in `data/02_layer1_signals/signal_r2_*.csv`.
- Current signal manifest and validation:
  - `data/02_layer1_signals/signal_manifest.json` has 25 manifest entries.
  - `data/02_layer1_signals/signal_summary_table.csv` has 22 validation rows. Strongest current signals remain momentum/trend-heavy, including multi-horizon momentum, cross-sectional momentum, moving-average distance, trend clarity, and breadth-confirmed momentum.
- Production/candidate metrics:
  - `data/05_layer3_portfolio_construction/production_candidate_summary.csv` confirms `improved_phaseggg_confirmed_only_robust_offense` as pending human-review production candidate with approximate full-window Sharpe near 0.94.
  - `data/05_layer3_portfolio_construction/production_candidate_registry.json` still marks `improved_phase2b_regime_confidence_boost` as current production/rollback. This sprint will not edit either file.

## Implementation Implications

- Breadth signals can be built from existing daily and weekly ETF price data without external data.
- Sector breadth must document the XLC/XLRE gap.
- State-gated macro tests should use the existing R2 panel signals because `macro_weekly.csv` does not contain populated macro series.
- Validation should reuse the existing R1-R4 IC framework where possible: cross-sectional IC, holdout IC, state-conditional IC, Newey-West-style t-stat, and redundancy versus strong existing signals.
- All research signals must include a one-week tradable lag before validation.
- Outputs are research-only and should not be promoted or wired into allocation logic.
