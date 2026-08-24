# Sealed Cross-Strategy Residual Allocator V2 / V3

Status: **completed, research-only, rejected.** No promotion, no forward clock,
no execution, no live trading. Superseded nothing that was ever promoted,
because nothing in this project has been.

V2 is the method. V3 is the same sealed experiment rerun against a corrected
instrument classification map after a post-result defect was found in V2's
concentration inputs; see *Correction: V3* below. **V3's numbers are the
authoritative ones.** Returns, stresses, breadth and bootstrap are bit-identical
between the two runs; only concentration moved.

## Why there is a V2

V1 (`sec-cross-strategy-residual-allocator-v1`) tested the same hypothesis but
operated exclusively on the two strategies' return series. Re-reading it turned
up five defects, four of which silently manufactured passing gates:

1. It never inspected holdings, so it could not see that the two "independent"
   strategies hold largely the same securities.
2. It charged reallocation cost only on the change in the allocator weight. The
   rule it selected was a static 20%, whose weight never changes, so inside the
   locked window turnover was zero and the doubled-cost stress was arithmetically
   identical to the headline. It "passed" a cost stress it never ran.
3. Both delay stresses shifted a constant series and were likewise no-ops.
4. The sleeve shock was applied at the midpoint of the *full* frame, which falls
   inside the development period, so it never touched the locked window at all.
5. There was no missing-stock stress and no reconciliation of either source
   against its own daily record.

V1's `double_cost_improvement` and `delay_improvement` gates both read `true`.
Neither test did anything.

## What V2 does

Seven stages, sealed before execution and run once.

**Stage 0 — exact daily reconciliation, fail closed.** Before any performance
number is computed, each source is checked three ways: weekly net return against
its own compounded daily records, published wealth against the cumulative
product of net returns, and the `net = gross − cost` identity. Any error above
1e-9 aborts the run before a result file can exist. Both sources passed at
machine precision (worst error 1.5e-16).

**Stage 1 — unlever, and prove it.** Display leverage and financing are removed
from both sources. The rebuilt cash-only base reproduces the published
`cashOnlyMetric` of 112.6039000930664% to an absolute error of exactly zero. The
de-levering is therefore verified against an independently published figure
rather than asserted.

**Cost symmetry.** The reconciliation surfaced that the sector sleeve is
published with 32.29 units of cumulative turnover and **zero** charged trading
cost, while the base pays a full 50 bps and carries 13.05 percentage points of
cumulative cost drag. Every prior comparison between them, including the
158.52% blend that motivated this experiment, was a cost-charged strategy
measured against a cost-free one. V2 rebuilds the combined book at the holdings
level and charges its real turnover at one rate, so both sources pay the same
price to trade.

**Stage 2 — concentration with ETF look-through.** Over half of each strategy's
weight sits in exchange traded products, so sector concentration measured on
single names alone is meaningless. A frozen map
(`data/cross_strategy_concentration_map_v1/`) resolves 214 held symbols to
SIC-derived sectors through the SEC broad research panel; 19 exchange traded
products are expanded through a declared look-through table. Concentration is
measured at the 95th percentile of the locked window for max single issuer, max
single ETF, total ETF, and max look-through sector.

**Stage 3 — breadth.** Weight overlap between the two books, per week, alongside
the return correlation.

**Stage 4 — purged walk-forward selection.** Twelve candidates (three rules ×
caps of 5%, 10%, 15%, 20%), selected on lagged residual momentum, beta,
correlation and residual information ratio only, over expanding folds inside the
development period with a four-week purge before the locked replay.

**Stage 5 — locked replay and non-vacuous stresses.** Doubled cost, one- and
two-week delays, 25% positive-signal decay, a −20% sleeve week placed *inside*
the locked window, and missing-stock stresses that remove the top 1, 3 and 5
sleeve names each week. Every stress records a vacuity flag comparing it against
the headline path, so a test that does nothing can no longer be mistaken for a
test that was passed.

**Stage 6 — leave-one-issuer-out and bootstrap.** The ten largest sleeve names
are removed one at a time. Paired moving-block bootstrap at 4- and 13-week
blocks, corrected for cumulative trials — V2's 12 plus the 378-candidate sealed
tournament of Step 175 on the same two return series, giving 390 for V2 and 402
for V3 once V2's own 12 are carried forward.

**Stage 7 — financing, deferred.** Levered paths are not computed at all unless
the unlevered book clears every gate. It did not, so none were computed.

## Results

Unlevered, cost-symmetric, 52 weeks ending 2026-08-07. Selected candidate:
static 20% (the same shape as the post-hoc hypothesis).

| | Base alone | With 20% sleeve |
|---|---|---|
| CAGR | 109.22% | 110.36% |
| Sharpe | 3.097 | 3.640 |
| Max drawdown | −11.31% | −8.97% |

The improvement is **+1.13 percentage points of CAGR**, not the +7.66 points
(150.86% → 158.52%) that motivated the experiment. The gap is financing, the
sleeve's uncharged trading costs, and real combined-book turnover.

### Every stress is larger than the edge

| Stress | CAGR | vs. base | Vacuous |
|---|---|---|---|
| Headline | 110.36% | +1.13pp | — |
| Doubled cost (100 bps) | 103.17% | −6.05pp | no |
| One-week delay | 110.36% | +1.13pp | **yes** |
| Two-week delay | 110.36% | +1.13pp | **yes** |
| 25% signal decay | 100.24% | −8.99pp | no |
| −20% sleeve week | 102.22% | −7.00pp | no |
| Missing top 1 sleeve name | 98.72% | −10.50pp | no |
| Missing top 3 sleeve names | 92.46% | −16.76pp | no |
| Missing top 5 sleeve names | 88.41% | −20.82pp | no |

The delay gate reads `true` but is flagged vacuous: for a static allocation,
delaying a constant weight is genuinely a no-op. It carries no evidential
weight, and unlike V1 the run says so.

### Leave-one-issuer-out

Removing **XLK alone** takes the allocator from +1.13pp to **−10.73pp** against
the base. Removing SLV, MU, PLTR, or VICR individually also flips it negative.
Only five of the ten largest sleeve names leave any improvement standing.

Micron appearing here is not a coincidence. It is the same single name that has
independently explained supposed improvements throughout this project's history.

### Breadth: the finding that matters

| | Value |
|---|---|
| Return correlation, recent 52w | **0.079** |
| Mean holdings overlap, recent 52w | **75.81%** |
| Mean holdings overlap, full history | 75.45% |
| Shared names in the final week | 25 of the sleeve's 29 |
| Effective independent strategies (returns) | 1.99 |

The 0.079 correlation that motivated this entire experiment is reproduced
exactly. It is also misleading. The two strategies hold **the same 25 names**,
including MU, GTLB, QLYS, PANW, PLTR, ZS, XLK and XLE. The low correlation comes
from weighting the same securities differently, not from a second source of
information.

Note the contrast in the last two rows: the returns-based effective-breadth
metric reports 1.99 independent strategies, which is nearly the maximum possible
for two series. The holdings-based measure reports 76% identity. Where the two
disagree, the holdings are the ground truth. A returns-only breadth statistic can
be fooled by re-weighting, and in this case it was.

Under Grinold & Kahn's IR ≈ IC × √BR, re-weighting an existing book does not
raise breadth. This is the same ceiling Batch 03 measured at ≈1.15 effective
strategies, reached by a different route.

### Concentration

Measured at the 95th percentile of the locked window. **V3 figures.**

| Metric | Cap | Base alone | With sleeve | Δ | Δ tolerance |
|---|---|---|---|---|---|
| Max single issuer | 10% | 7.4% | 7.5% | +0.12pp | 2pp — pass |
| Max single ETF | 35% | **48.0%** | **50.4%** | **+2.40pp** | 2pp — **fail** |
| Total ETF | 70% | 58.8% | 60.7% | +1.93pp | 3pp — pass |
| Max look-through sector | 45% | **81.6%** | **83.7%** | +2.08pp | 3pp — pass |

Two separate findings.

First, the incumbent already breaches two of four conventional caps on its own.
The 150.86% leader is, after ETF look-through, an **81.6% technology book** with
48% in a single fund. That is a concentrated sector bet held at leverage, and it
is a fact about the incumbent, not about the sleeve.

Second, the sleeve makes all four measures worse, and the single-ETF increase of
+2.40pp exceeds its 2pp tolerance. Every cap from 5% to 20% raises every
concentration measure monotonically; there is no size at which this sleeve
diversifies the book. That is the expected consequence of 76% holdings overlap.

The look-through sensitivity check tilts each broad fund a further 15 points into
its largest sector and renormalises. The verdict is unchanged, so the conclusion
does not rest on the exact declared ETF splits.

### Significance

Paired moving-block bootstrap probability that the allocator beats the base:
**0.4684** (4-week blocks) and **0.3968** (13-week blocks). The 13-week figure is
worse than a coin flip. The familywise threshold after correcting for 402
cumulative trials is 0.999876. This is not a near miss.

## Gate results

| Gate | Result |
|---|---|
| Daily reconciliation | pass |
| Locked Sharpe | pass |
| Locked drawdown | pass |
| Delay improvement | pass (vacuous, no weight) |
| Absolute issuer concentration | pass (V3; V2 wrongly failed this) |
| Locked CAGR improvement (≥5pp) | **fail** — +1.13pp |
| Doubled cost improvement | **fail** — −6.05pp |
| Missing-stock improvement | **fail** — −10.50 to −20.82pp |
| Leave-one-issuer-out | **fail** — XLK removal is −10.73pp |
| Incremental concentration | **fail** — single-ETF +2.40pp over a 2pp tolerance |
| Absolute concentration | **fail** — single ETF 50.4%, sector 83.7%; the incumbent fails both too |
| Breadth overlap | **fail** — 75.81% against a 40% ceiling |
| Familywise bootstrap | **fail** — 0.40 against a 0.9999 threshold |
| Source research gate | **fail** — sleeve has zero forward weeks |

Nine of thirteen gates fail, in V2 and V3 alike. Financing was never evaluated.

## Correction: V3

After V2's result file was written, a defect was found in its concentration
**inputs** — not in its logic. Concentration map v1 carried a hand-written list
of exchange traded products that omitted SLV, XLB, XLP, XLV, XLY, VTV, VWO, BIL
and PDBC. Any fund missing from that list fell through to the issuer bucket.

In this strategy pair the material omission was **SLV**, which reaches 21.5% and
26.8% de-levered weight in the base and sleeve respectively. Because the iShares
Silver Trust is itself an SEC filer with a CIK and a SIC code in the finance
division, V2 counted it twice over as a company: as the largest single "issuer"
and as financial-sector exposure. V2's headline "max single issuer 21.5%" was
SLV, and was wrong.

Because V2 was a completed one-shot, it was not re-run or overwritten. Map v2 was
built with a comprehensive fund list plus an explicit data-artifact class, and
the identical experiment was sealed and run once more as V3.

| | V2 | V3 |
|---|---|---|
| Max single issuer, base | 21.5% (was SLV) | **7.4%** |
| Max single issuer, selected | 22.5% | **7.5%** |
| Total ETF, base | 57.3% | **58.8%** |
| Max single ETF | 48.0% | 48.0% (unchanged) |
| Max look-through sector | 81.6% | 81.6% (unchanged) |
| Locked CAGR, base / selected | 109.22% / 110.36% | identical |
| Bootstrap 4w / 13w | 0.4684 / 0.3968 | identical |
| Holdings overlap | 75.81% | identical |
| Gates failed | 9 of 13 | 9 of 13 |

The absolute issuer gate flips from fail to pass. Every other gate, and the
rejection itself, is unchanged. Returns being bit-identical across the two runs
is the intended check that the map feeds only risk measurement and never the
return path.

A separate artifact surfaced while building map v2 and is **not** fixed here:
`sec-growth-survivorship-aware-v1` carries a holding whose symbol is the literal
string `PRICES`, at up to 40% weight across 54 weeks. Map v2 classifies it as a
data artifact so it can never be absorbed into an issuer or sector bucket, but
the underlying export defect belongs to that strategy and is recorded, not
repaired, by this experiment.

## Conclusion

The 158.52%/3.73-Sharpe blend was not a diversification discovery. It was a
levered, cost-asymmetric measurement of a 76%-overlapping book, selected after
looking at the answer. Unlevered and charged symmetrically, the edge is 1.13
percentage points, smaller than any stress applied to it and smaller than the
effect of removing any one of five individual securities.

The correct next step is not a different cap, a different rule, or a different
blend of these two strategies. Any allocator over these two books is a
re-weighting of one book. The binding constraint remains breadth, and breadth
here requires a return source that does not hold MU, XLK and PANW.

## Reproduce

```bash
.venv/bin/python3 scripts/build_cross_strategy_concentration_map_v2.py
.venv/bin/python3 scripts/seal_sec_cross_strategy_residual_allocator_v3.py
.venv/bin/python3 scripts/run_sec_cross_strategy_residual_allocator_v3.py
.venv/bin/python3 -m pytest tests/test_sec_cross_strategy_residual_allocator_v2.py -q
```

Run from `2.0/`. Swap `v3` for `v2` and map `v2` for `v1` to reproduce the
superseded run.

The runner refuses to execute unless the seal matches, and refuses to execute
twice.

## Known limitations

- The SIC sector map is the current SEC company-facts vintage, not the sector
  recorded at each historical decision date. It is used only as a risk
  constraint and never as a return signal, so it cannot inject lookahead into
  returns, but a wrong label could misclassify a concentration. The sensitivity
  check addresses the ETF splits, not the underlying SIC vintage.
- ETF look-through resolves to sectors, not to constituent issuers. True issuer
  concentration is therefore understated: names held both directly and inside
  XLK are counted once, directly. The reported issuer figures are a floor.
- 29 held symbols, all delisted or renamed and none above 5.4% weight, resolve
  to `unclassified` under map v2.
- The locked window is selection-contaminated. The 80/20 hypothesis was formed
  after observing this same window in Steps 173–175. No untouched data exists
  for it, and none is created by this run.
