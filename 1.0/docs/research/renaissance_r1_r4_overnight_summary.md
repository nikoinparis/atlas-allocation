# Renaissance R1-R4 Overnight Summary

Research-only sprint for phases R1-R4. No R5/R6/R7/R8 work was implemented.

## Commands executed

```bash
.venv/bin/python -m py_compile scripts/renaissance_r1_r4_utils.py scripts/run_signal_decay_analysis.py scripts/build_macro_signal_library.py scripts/build_vix_term_structure_signal.py scripts/build_volume_divergence_signal.py scripts/run_r2_signal_validation.py scripts/run_state_conditional_signal_ic.py scripts/build_etf_pairs_signals.py
.venv/bin/python scripts/run_signal_decay_analysis.py
.venv/bin/python scripts/build_macro_signal_library.py
.venv/bin/python scripts/build_macro_signal_library.py
.venv/bin/python scripts/build_vix_term_structure_signal.py
.venv/bin/python scripts/build_volume_divergence_signal.py
.venv/bin/python scripts/run_r2_signal_validation.py
.venv/bin/python scripts/run_state_conditional_signal_ic.py
.venv/bin/python scripts/build_etf_pairs_signals.py
.venv/bin/python scripts/run_signal_decay_analysis.py
.venv/bin/python scripts/run_signal_decay_analysis.py
git status --short
git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv
```

Additional inline Python verification commands inspected output existence, CSV heads, shapes, verdict tables, and top state-conditional rows.

## Files created or modified

### Scripts

- `scripts/renaissance_r1_r4_utils.py`
- `scripts/run_signal_decay_analysis.py`
- `scripts/build_macro_signal_library.py`
- `scripts/build_vix_term_structure_signal.py`
- `scripts/build_volume_divergence_signal.py`
- `scripts/run_r2_signal_validation.py`
- `scripts/run_state_conditional_signal_ic.py`
- `scripts/build_etf_pairs_signals.py`

### Data outputs

- `data/02_layer1_signals/signal_decay_profiles.csv`
- `data/02_layer1_signals/signal_r2_yield_curve.csv`
- `data/02_layer1_signals/signal_r2_credit_spread.csv`
- `data/02_layer1_signals/signal_r2_financial_conditions.csv`
- `data/02_layer1_signals/signal_r2_vix_term_structure.csv`
- `data/02_layer1_signals/signal_r2_dollar_strength.csv`
- `data/02_layer1_signals/signal_r2_commodity_regime.csv`
- `data/02_layer1_signals/signal_r2_cross_asset_divergence.csv`
- `data/02_layer1_signals/signal_r2_volume_divergence.csv`
- `data/02_layer1_signals/r2_signal_validation_results.csv`
- `data/02_layer1_signals/signal_state_conditional_ic.csv`
- `data/02_layer1_signals/etf_pairs_cointegration_report.csv`
- `data/02_layer1_signals/signal_r4_pair_hyg_lqd.csv`

### Reports

- `docs/research/renaissance_r1_r4_discovery_note.md`
- `docs/research/signal_research_log.md`
- `docs/research/r1_signal_decay_report.md`
- `docs/research/r2_signal_validation_report.md`
- `docs/research/state_conditional_signal_report.md`
- `docs/research/etf_pairs_signal_report.md`
- `docs/research/renaissance_r1_r4_overnight_summary.md`

## Phase status

| Phase | Status | Notes |
| --- | --- | --- |
| R1 | completed | Decay profiles covered 25 existing manifest/summary signals; research log initialized. |
| R2 | completed with warnings | All 8 requested R2 signals were attempted and validated; 1 candidate-pass, 7 rejected. |
| R3 | completed | Existing plus R2 signals evaluated by market state and horizon; no skipped signal loads. |
| R4 | completed | All 8 priority pairs tested; 0 candidate-pass, 1 research-only, 7 rejected. |

## Skipped or partial items

- R2 skipped signals: none.
- R3 skipped/partial signal loads: none.
- R4 skipped pairs: none.
- R1 unclear decay: `google_fear_regime`, `macro_risk_score`, and `vix_term_structure_regime` had no IC-by-horizon rows in `signal_ic_by_horizon.csv`.
- R2 credit spread warning: direct FRED OAS data was unavailable or insufficient in the run, so `r2_credit_spread` used an HYG/LQD ETF relative-price proxy and was labeled as such in the signal CSV.
- R2 volume warning: yfinance ran with a urllib LibreSSL/OpenSSL environment warning, but volume data was still pulled and the signal was built.

## Signals tested

Existing signals from the Layer 1 manifest and summary table were tested in R1/R3, including momentum, reversal, carry, value, BAB, quality, trend clarity, moving-average distance, breadth-confirmed momentum, contained recovery, and regime-feature entries.

R2 signals tested:

- `r2_yield_curve`
- `r2_credit_spread`
- `r2_financial_conditions`
- `r2_vix_term_structure`
- `r2_dollar_strength`
- `r2_commodity_regime`
- `r2_cross_asset_divergence`
- `r2_volume_divergence`

R4 pairs tested:

- SPY/QQQ
- IWM/SPY
- TLT/SPY
- GLD/TLT
- XLE/USO
- HYG/LQD
- EEM/SPY
- XLK/QQQ

## Signals that passed

Only one R2 signal passed the strict candidate gate:

| Signal | Avg full IC | Avg holdout IC | Max redundancy | Stressed panic avg IC |
| --- | ---: | ---: | ---: | ---: |
| `r2_dollar_strength` | 0.0314 | 0.0388 | 0.1122 | 0.0161 |

No R4 ETF pair passed the full weekly-frequency gate.

## Signals rejected

R2 rejected:

- `r2_yield_curve`: full-period IC was negative and stressed_panic damage was present.
- `r2_credit_spread`: full and holdout IC were positive, but stressed_panic damage was present.
- `r2_financial_conditions`: positive full/holdout IC, but stressed_panic damage was present.
- `r2_vix_term_structure`: positive full/holdout IC, but severe stressed_panic damage was present.
- `r2_commodity_regime`: holdout IC was negative and stressed_panic damage was present.
- `r2_cross_asset_divergence`: full and holdout IC were negative and stressed_panic damage was present.
- `r2_volume_divergence`: full and holdout IC were negative and stressed_panic damage was present.

R4 rejected:

- SPY/QQQ: failed cointegration, failed ADF, half-life too long, and weak/non-positive full/holdout pair IC.
- IWM/SPY: failed cointegration and half-life was too long.
- TLT/SPY: failed cointegration, failed ADF, half-life too long, and redundancy was above 0.50.
- GLD/TLT: failed cointegration, failed ADF, half-life too long, and weak/non-positive full/holdout pair IC.
- XLE/USO: failed cointegration and half-life was too long.
- EEM/SPY: failed cointegration, half-life too long, and weak/non-positive full/holdout pair IC.
- XLK/QQQ: failed cointegration, failed ADF, and half-life was too long.

HYG/LQD was research-only rather than candidate-pass: it passed training cointegration and ADF but had a 16.28-week half-life, outside the 2-13 week weekly-frequency gate.

## Best calm_trend signals

Top calm_trend rows were mostly existing momentum/trend signals at 13 weeks:

| Signal | Source | Horizon | Mean IC | NW t-stat |
| --- | --- | ---: | ---: | ---: |
| `moving_average_distance` | existing | 13w | 0.1473 | 3.6812 |
| `multi_mom_equal` | existing | 13w | 0.1425 | 3.5004 |
| `trend_clarity_momentum` | existing | 13w | 0.1375 | 3.2434 |
| `multi_mom_invvol` | existing | 13w | 0.1361 | 3.3838 |
| `xsmom_global` | existing | 13w | 0.1358 | 3.1284 |

Some R2 macro/risk signals looked useful in calm_trend, especially `r2_vix_term_structure`, `r2_credit_spread`, and `r2_financial_conditions`, but they failed the unconditional gate because they hurt stressed_panic.

## Dangerous stressed_panic signals

Worst stressed_panic rows:

| Signal | Source | Horizon | Mean IC | NW t-stat |
| --- | --- | ---: | ---: | ---: |
| `r2_vix_term_structure` | R2 | 13w | -0.2333 | -5.1310 |
| `r2_vix_term_structure` | R2 | 8w | -0.1916 | -3.6861 |
| `bab_proxy` | existing | 13w | -0.1633 | -2.2905 |
| `r2_cross_asset_divergence` | R2 | 13w | -0.1464 | -2.1770 |
| `r2_cross_asset_divergence` | R2 | 8w | -0.1320 | -2.1505 |

This is the key rejection finding: several macro/risk-on signals are attractive in calm_trend but dangerous when the portfolio most needs defensive behavior.

## Did ETF pairs work?

Not as a production-ready weekly signal family. HYG/LQD is the only statistically viable research-only pair signal file generated, with positive full and holdout IC but a slower 16.28-week half-life than the 2-13 week gate. The broader pair set mostly failed training cointegration, spread stationarity, or usable half-life requirements.

## Do the new R2 signals look useful?

Yes, selectively. `r2_dollar_strength` is the cleanest new orthogonal candidate because it passed full-period IC, holdout IC, redundancy, and stressed_panic gates. The macro/VIX/credit signals look more like regime-conditional ingredients than unconditional signals: they help calm_trend but can damage stressed_panic.

## Does the evidence support the Renaissance-inspired direction?

Yes. The sprint shows why disciplined decay, orthogonality, regime-conditional testing, and statistical rejection matter. A looser research process would have accepted several attractive full-period macro signals; the stressed_panic checks rejected them. The result supports better information and state-aware signal validation rather than higher turnover or blind parameter tuning.

## Recommended next sprint

Run a research-only follow-up focused on:

- Robustness tests for `r2_dollar_strength`: subperiods, alternative UUP windows, state-specific behavior, and redundancy drift.
- State-gated macro signal prototypes that activate calm_trend benefits while explicitly suppressing stressed_panic damage.
- Better credit-spread data ingestion so direct OAS can be compared against the HYG/LQD proxy.
- Signal decay monitoring automation for the existing strong momentum/trend family.

## Production safety confirmation

- No production pins were changed.
- No dashboard or public files were modified.
- No production portfolio return/weight artifacts were overwritten.
- No live trading/execution logic was added or changed.
- `git diff -- public src data/05_layer3_portfolio_construction/production_candidate_registry.json data/05_layer3_portfolio_construction/production_candidate_summary.csv` returned no diff.

The repo still has pre-existing dirty worktree items unrelated to this sprint, including `requirements.txt` and prior untracked ML/turnover research artifacts. Those were not modified by this R1-R4 work.
