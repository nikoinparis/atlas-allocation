# New Strategy Families — Batch 04

**288** configurations tested mean reversion, defensive selection, and a distribution-yield carry proxy on immutable snapshot `20260808T212827Z-de103c2e063d6c4a`.

## Development-selected family leaders

### Carry Proxy

- Experiment: `exp-3aa6e07c0cd53e52`; recipe **distribution_yield**.
- Configuration: monthly, score_inverse_volatility, top 6, smoothing 2 weeks.
- Development: return **6.26%**, Sharpe **0.726**, drawdown **-27.07%**.
- Retrospective 2016–2020: return **8.15%**, Sharpe **0.676**.
- Retrospective 2021–present: return **4.28%**, Sharpe **0.542**.
- 50 bps full-history stress: return **5.67%**, Sharpe **0.619**.
- Correlation to frozen v4: **0.581**.
- Registry status: **provisional_new_family**.

### Defensive

- Experiment: `exp-8a27cb8ba5a612a7`; recipe **defensive_quality_gated**.
- Configuration: monthly, equal_weight, top 6, smoothing 2 weeks.
- Development: return **7.06%**, Sharpe **1.000**, drawdown **-12.07%**.
- Retrospective 2016–2020: return **5.91%**, Sharpe **0.597**.
- Retrospective 2021–present: return **8.84%**, Sharpe **1.079**.
- 50 bps full-history stress: return **5.71%**, Sharpe **0.720**.
- Correlation to frozen v4: **0.719**.
- Registry status: **provisional_new_family**.

### Mean Reversion

- Experiment: `exp-81ffdbdf4dcdab3c`; recipe **reversal_4w**.
- Configuration: weekly, equal_weight, top 4, smoothing 4 weeks.
- Development: return **8.14%**, Sharpe **0.534**, drawdown **-45.34%**.
- Retrospective 2016–2020: return **6.48%**, Sharpe **0.488**.
- Retrospective 2021–present: return **10.23%**, Sharpe **0.817**.
- 50 bps full-history stress: return **3.61%**, Sharpe **0.306**.
- Correlation to frozen v4: **0.628**.
- Registry status: **provisional_fragile**.

## Multi-family ensemble diagnostics

- **trend_v4**: return **9.91%**, Sharpe **0.754**, drawdown **-26.25%**, annual turnover **1.93**.
- **trend_plus_defensive**: return **8.64%**, Sharpe **0.860**, drawdown **-24.29%**, annual turnover **2.45**.
- **trend_defensive_carry**: return **7.85%**, Sharpe **0.871**, drawdown **-24.44%**, annual turnover **1.82**.
- **all_four_families**: return **8.24%**, Sharpe **0.842**, drawdown **-25.28%**, annual turnover **4.22**.

These combinations net target weights before charging turnover, but they were designed after viewing the history and are not promotion candidates.

## Carry-data limitation

The carry proxy uses trailing cash distributions divided by unadjusted close and lags the cross-sectional signal one week. Event dates are causal, but Yahoo's entire action history was obtained in the current 2026 snapshot. The carry candidate therefore cannot pass the archived point-in-time distribution gate from this source.

## Interpretation

Family leaders were selected only from the development period and then displayed on later retrospective periods. They are saved for further testing, not promoted. Batch 04 adds another 288-way search, so robustness, dependence, and multiple-testing correction must be run before combining any leader with the trend sleeve.
