# R1 Signal Decay Report

Research-only signal decay analysis using existing `signal_ic_by_horizon.csv`. Half-life estimates are based on an exponential fit to absolute IC across available horizons and are diagnostic, not a promotion rule.

- Signals covered: 25
- Output CSV: `data/02_layer1_signals/signal_decay_profiles.csv`
- Research log: `docs/research/signal_research_log.md`

## Strongest slow-decay signals

| signal_name | half_life_weeks | avg_available_ic | ic_1w | ic_4w | ic_13w |
| --- | --- | --- | --- | --- | --- |
| xsmom_global | 1930.4671 | 0.0536 | 0.0501 | 0.0538 |  |
| multi_mom_equal | inf | 0.0536 | 0.0481 | 0.0561 |  |
| moving_average_distance | inf | 0.0500 | 0.0396 | 0.0537 |  |
| multi_mom_invvol | inf | 0.0496 | 0.0447 | 0.0531 |  |
| trend_clarity_momentum | inf | 0.0435 | 0.0411 | 0.0433 |  |
| breadth_confirmed_momentum | inf | 0.0322 | 0.0290 | 0.0332 |  |
| xsmom_asset_class_neutral | 11.6294 | 0.0202 | 0.0221 | 0.0188 |  |
| tsmom_vol_scaled | 8.8732 | 0.0178 | 0.0225 | 0.0129 |  |
| residual_momentum | 7.4507 | 0.0083 | 0.0128 | 0.0042 |  |
| reversal_4w_global | inf | 0.0017 | 0.0029 | -0.0056 |  |
| reversal_4w_asset_class_neutral | inf | 0.0013 | 0.0002 | -0.0028 |  |
| quality_proxy_asset_class_neutral | 7.7558 | -0.0007 | -0.0009 | 0.0015 |  |

## Weakest or fast-decay signals

| signal_name | decay_classification | half_life_weeks | avg_available_ic | weekly_rebalance_viability_flag |
| --- | --- | --- | --- | --- |
| bab_proxy | slow decay | inf | -0.1043 | Weak/non-positive average IC. |
| value_proxy | slow decay | inf | -0.0540 | Weak/non-positive average IC. |
| quality_proxy | slow decay | inf | -0.0471 | Weak/non-positive average IC. |
| value_proxy_asset_class_neutral | slow decay | inf | -0.0299 | Weak/non-positive average IC. |
| bab_proxy_asset_class_neutral | slow decay | inf | -0.0262 | Weak/non-positive average IC. |
| carry_proxy | slow decay | inf | -0.0181 | Weak/non-positive average IC. |
| carry_proxy_asset_class_neutral | slow decay | inf | -0.0121 | Weak/non-positive average IC. |
| reversal_1w_asset_class_neutral | slow decay | 256.0640 | -0.0029 | Weak/non-positive average IC. |
| reversal_1w_global | slow decay | 27.8434 | -0.0021 | Weak/non-positive average IC. |
| quality_proxy_asset_class_neutral | slow decay | 7.7558 | -0.0007 | Weak/non-positive average IC. |

## Signals with unclear decay

| signal_name | fit_warning |
| --- | --- |
| google_fear_regime | No IC-by-horizon rows available. |
| macro_risk_score | No IC-by-horizon rows available. |
| vix_term_structure_regime | No IC-by-horizon rows available. |

## Data limitations and warnings

- No IC-by-horizon rows available.
- No observed exponential decay across available horizons.

## Research-only confirmation

R1 wrote only research reports and `data/02_layer1_signals/signal_decay_profiles.csv`; it did not alter production allocation, dashboard, public, or trading/execution files.
