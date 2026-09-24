# WorldQuant BRAIN — every ladder measured, 2026-09-22 to 2026-09-24

Consolidated by hand because successive runs at neutralization NONE overwrote a shared
`summary.json` (fixed 2026-09-24: output dirs are now tagged by neutralization AND signal
set). Numbers marked *(log only)* were read from a run log that has since been cleaned up
and are recorded here because that is the only surviving copy.

**The bar that matters is not 0.5 and not BRAIN's 1.25. It is `control_size`.**
`group_rank(assets, sector)` — ranking companies by total assets, no skill in it whatever —
scores **monotonicity +0.867, middle-8 +0.905** market-neutral on 10/10 clean deciles.
Any signal that does not clear that is measuring size.

## Ladders, neutralization NONE unless stated

| signal | monotonicity | middle-8 | d10−d1 | distinct | vs control +0.867 |
|---|---|---|---|---|---|
| `sales_yield` *(log only)* | +0.988 | +0.976 | +43.5pp | 10/10 | +0.121 |
| `cash_conversion` | +0.939 | +0.905 | +26.4pp | 10/10 | +0.072 |
| `earnings_yield` *(log only)* | +0.891 | — | +26.7pp | 10/10 | +0.024 |
| `free_cash_flow_yield` *(log only)* | +0.879 | +0.762 | +31.2pp | 10/10 | +0.012 |
| **`control_size` (MARKET, NO SKILL)** | **+0.867** | **+0.905** | +14.1pp | 10/10 | — |
| `growth` | +0.855 | +0.738 | +35.9pp | 10/10 | **−0.012** |
| `control_size` (NONE, 9/10) | +0.832 | — | +25.3pp | 9/10 | — |
| `quality_acceleration` | +0.648 | +0.643 | +11.0pp | 10/10 | **−0.219** |
| `profitability` | +0.442 | +0.262 | +28.1pp | 10/10 | **−0.425** |
| `shareholder_discipline` | +0.139 | −0.381 | +11.2pp | 10/10 | **−0.728** |
| `balance_sheet_quality` | −0.927 | −0.857 | −24.0pp | 10/10 | inverted |

**Never obtained:** `composite_value` and `quality_at_reasonable_price`. Their first run died
on a session expiry and the re-run's output was overwritten before it was read. Two of
twelve families remain unmeasured and that is a gap, not a result.

## Production forms, SUBINDUSTRY, delay 1, TOP3000, ~3,045 names positioned

| signal | Sharpe | returns | turnover | fitness | drawdown |
|---|---|---|---|---|---|
| `growth` | **1.27** | 8.35% | 4.26% | **1.04** | 12.67% |
| `sales_yield` | 1.22 | 12.69% | 3.74% | — | — |
| `control_size` **(NO SKILL)** | 0.86 | **8.57%** | 2.13% | 0.71 | 25.61% |
| `cash_conversion` | 0.48 | 4.63% | 2.51% | 0.29 | 31.11% |
| `balance_sheet_quality` | −1.17 | −7.77% | 2.46% | −0.92 | 42.48% |

`growth` clears BRAIN's submission bar (Sharpe ≥ 1.25, fitness ≥ 1.0) **and returns less than
the no-skill control** (8.35% vs 8.57%). Its higher Sharpe is a drawdown difference.

## What MARKET neutralization did

| signal | mono NONE | mono MARKET | spread NONE | spread MARKET | beta share |
|---|---|---|---|---|---|
| `cash_conversion` | +0.939 | +0.939 | +26.4pp | +14.7pp | 44.3% |
| `growth` | +0.855 | +0.855 | +35.9pp | +20.4pp | 43.2% |
| `balance_sheet_quality` | −0.927 | −0.927 | −24.0pp | −13.4pp | 44.4% |

Monotonicity is **bit-identical** — market neutralization shifts decile levels without
reordering them, and monotonicity is scale-free, so it cannot see the change. What it removes
is ~44% of the *spread*, and the near-identical figure across three different signals is one
shared exposure rather than three independent ones. `cash_conversion`'s top decile earns
**+3.2%/yr** market-neutral, not +40% — Step 295's 16.65%→1.59% on someone else's data.

## Window and settings

`2019-01-01` to `2023-12-31` — five years, ~20 quarterly decisions. Read from the alpha
record's own `settings`, correcting an earlier claim of 2019–2022/four years. The `os`,
`train`, `test` and `prod` blocks are **null** on an unsubmitted alpha, so there are no
separate out-of-sample tabs and the entire span is in-sample. 2023 falls outside Step 300's
2013–2022 window; the other four years do not.

USA / TOP3000 / delay 1 / decay 0 / truncation 0.08 / pasteurization ON / nanHandling ON.
All fundamental fields sit at exactly **0.5 instrument coverage** — on the density floor,
clearing it but only just, and that is the binding caveat on every number above.

## Verdict

**Ten of twelve families measured. Zero beat a no-skill size control.** Four clear the
declared 0.5 monotonicity bar; all four clear it by roughly the margin `control_size` does,
and the highest of them (`sales_yield`, +0.988) is the most mechanically size-linked
construction in the set — sales over market cap is close to a size ranking with extra steps.

The Step 296–308 null replicates on data this project does not own, on a panel it did not
build, through a backtester it did not write, with a ~6× cross-section (3,045 names against
509). That was the declared expected outcome and it is the valuable one.

**The one genuinely new thing, which could not have been produced at home:** a decile ladder
on long-only baskets orders itself at +0.83 to +0.87 *on no signal at all*. Every monotonicity
this project has ever read needs that calibration point beside it.
