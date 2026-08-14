# Layer 2B Modifier Rule Definitions

## Signal Variants
- **A**: market_state=neutral_mixed AND macro_state=slowdown
- **B**: A + credit trend improving (HYG/LQD 4w momentum > 0, 1-week lag)
- **C**: A + credit not worsening (4w momentum > -1%, 1-week lag)
- **D**: A + financial_conditions_proxy < 0 (FC benign/easing)
- **E**: A + credit improving + FC benign

## Persistence Filter
- activate_after: consecutive True weeks before activation
- deactivate_after: consecutive False weeks before deactivation
- min_hold: minimum weeks to remain active before can deactivate

## Modifier Types
- **offense_budget**: drain from BIL/IEF/TLT, add to SPY/QQQ/HYG/EFA proportionally
- **defense_release**: reduce BIL specifically, redistribute to all non-BIL ETFs
- **risk_multiplier**: scale all offensive ETF weights by (1+intensity), fund from BIL
- **combined**: 60% offense_budget + 40% defense_release

## Intensity levels tested
- 2.5%, 5.0%, 7.5%, 10.0%

## Constraints preserved
- Long-only (no short positions)
- Weight sum normalized to 1
- BIL floor: minimum 2% retained
- No leverage
- stressed_panic weeks: never modified (only neutral_mixed)
