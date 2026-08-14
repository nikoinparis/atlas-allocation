# Tilt Rule Definitions

**Sprint:** macro_conditioned_etf_tilt_sandbox (Step 2)

**Date:** 2026-06-06


## Variant Families
- **A**: Macro state only (no confirmation gate)
- **B**: Macro state + credit trend improving (HYG/LQD 4w momentum)
- **C**: Macro state + SPY above 40-week MA
- **D**: Macro state + credit AND SPY trend (most conservative)

## Tilt Sizes Tested
2.5%, 5.0%, 7.5%, 10.0%

## Bucket Types
- **data**: top ETFs from dev-period neutral_mixed asset diagnostics
- **intuitive**: risk-on/defensive buckets from macro intuition

## Data-Derived Buckets (neutral_mixed, dev only)

### NM + expansion
- Data top ETFs: ['BIL', 'XLU', 'XLV']
- Intuitive risk-on: ['SPY', 'QQQ', 'IWM']
- Contradiction: True

### NM + slowdown
- Data top ETFs: ['SPY', 'XLK', 'VTV']
- Intuitive risk-on: ['SPY', 'QQQ', 'IWM']
- Contradiction: False

### NM + stress
- Data top ETFs: ['PDBC', 'SHY', 'HYG']
- Intuitive risk-on: ['SPY', 'QQQ', 'IWM']
- Contradiction: False

### NM + overheating
- Data top ETFs: ['BIL', 'SHY', 'XLU']
- Intuitive risk-on: ['GLD', 'XLE', 'PDBC']
- Contradiction: True
