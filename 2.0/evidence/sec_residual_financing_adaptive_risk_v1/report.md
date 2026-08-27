# Financing and Adaptive-Risk Decision Record

## Decision

Retain the published 1.25x / 5% path as the dashboard's clearly labeled
historical reference. Do not replace it with either adaptive variant. For more
conservative planning, use the fixed 1.25x / 8% result as the baseline and 12%
as the financing stress.

## Comparable trailing 52 weeks through 2026-08-07

| Variant | CAGR | Sharpe | Max drawdown |
|---|---:|---:|---:|
| Unlevered 1.00x | 112.60% | 3.160 | -11.12% |
| Fixed 1.25x, published 5% reference | 150.86% | 3.120 | -13.87% |
| Fixed 1.25x, realistic 8% baseline | 149.01% | 3.096 | -13.95% |
| Adaptive 1.00x-1.25x, 8% | 147.66% | 3.088 | -13.86% |
| Adaptive plus residual risk-contribution limit, 8% | 147.76% | 3.090 | -13.86% |

The contribution rule improved the adaptive path slightly and held every
observable residual issuer at or below 12% of the sleeve's standalone
volatility-budget contribution. It did not beat fixed exposure. After the
four-comparison correction, neither adaptive variant had positive bootstrap
support versus the 8% fixed benchmark.

## Stress and path findings

- Fixed 1.25x returned 146.58% at 12% financing, with 3.064 Sharpe and -14.05%
  drawdown.
- The adaptive rule spent 125 weeks at 1.25x, two at 1.125x, and 66 at 1.00x,
  with 15 exposure transitions.
- Adaptive exposure beat the fixed 8% benchmark in only 2.8% of completed
  rolling 52-week windows. Adding the risk-contribution limit raised that to
  10.2%, still insufficient.
- No historical margin-safety breach occurred. At 1.25x, even a one-week 50%
  asset loss stays above the frozen equity-ratio thresholds but produces an
  approximately 62.5% equity loss. A 60% asset shock breaches the internal 50%
  safety ratio and produces an approximately 75.0% equity loss before
  liquidation costs. Absence of a margin call is therefore not a safety claim.

## Risk posture

- Intended alpha retained: the 80% control / 20% residual systematic signal.
- Unwanted risk tested: financing drag, leverage timing, margin breach, and
  residual issuer volatility concentration.
- Binding constraint: historical selection contamination and weak rolling
  evidence for adaptive timing, not broker maintenance margin at 1.25x.
- Liquidity and implementation readiness: not implementation-ready; broker
  rates, house requirements, security eligibility, ADV, tax, and actual
  execution terms remain absent.
- Action: keep as research only, do not alter the frozen forward candidate, and
  do not enable live trading.
