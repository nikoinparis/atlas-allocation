# SEC Independent-Sleeve Return Accelerator V1

## Decision

Reject the new dynamic return accelerator and retain the frozen 80/20 residual
candidate. The accelerator improved locked-block Sharpe and drawdown but reduced
return too severely to replace the incumbent.

## Data-boundary correction

The control series ends on August 7, 2026, while the residual research panel
continues through August 21. The original 80/20 diagnostic reindexed the control
to the longer panel and filled the two missing control weeks with zero. This
tournament forbids that convention and truncates every comparison to the last
common observed endpoint, August 7.

On the corrected trailing-52-week endpoint, the existing 1.25x candidate
produced:

| Financing assumption | CAGR | Sharpe | Max drawdown |
| --- | ---: | ---: | ---: |
| 5% | 150.86% | 3.120 | -13.87% |
| 8% | 149.01% | 3.096 | -13.95% |

This is a historical correction, not new alpha. Financing is assumed, every
week was already visible, and the frozen 0/52 forward clock is unchanged.

## Tournament design

The execution seal was written before performance was read. The finite grid
contained 378 candidates combining residual momentum, trend quality, quality
momentum, and delayed filing/event conditioning. Allocation used only lagged
13/26/52-week evidence, selected one to three sleeves, allowed 10%-40% alpha
allocations, and bounded volatility-scaled exposure at 1.5x. The chronology was
84 development weeks, 52 validation weeks, and one 52-week locked block.

All paths included 50-bps primary costs, 100/200-bps stress, one/two-week
execution delays, 8% financing, exposure-change costs, missing-price stress,
issuer influence, block bootstrap, and correction for all 378 trials.

## Result

The validation-selected candidate used a 52-week lookback, one active sleeve,
a fixed 20% alpha allocation, a 35% volatility target, and a 1.0x cap. On the
locked block it delivered 111.19% CAGR, 3.143 Sharpe, and -11.12% drawdown. The
corrected 8%-financing benchmark delivered 149.01%, 3.096, and -13.95%.

The challenger survived 200-bps costs at 91.42% CAGR and one/two-week delays at
105.86%/102.33%. Incremental issuer contribution remained below 10%. However,
it trailed the benchmark by 37.83 percentage points of CAGR, and its 4/13-week
bootstrap probabilities were 0.28%/0.00% before the familywise correction.
It therefore fails both the return and multiplicity gates.

## Interpretation

The independent signals were genuinely low-correlation to the control, but not
independent from one another: quality momentum and event conditioning had 0.922
correlation, while residual and trend quality had 0.734 correlation. Their
combination primarily reduced risk rather than increasing return. More exposure
to this ensemble would be leverage disguised as diversification.

No strategy was promoted, the existing forward protocol was not modified, and
live trading remains disabled.

## Artifacts

- `config/sec_independent_sleeve_return_accelerator_v1.json`
- `scripts/run_sec_independent_sleeve_return_accelerator_v1.py`
- `scripts/audit_sec_residual_common_endpoint_v1.py`
- `tests/test_sec_independent_sleeve_return_accelerator_v1.py`
- `evidence/sec_independent_sleeve_return_accelerator_v1/`
