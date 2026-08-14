# Atlas Offensive — Run Report: R00 (Governance Reset) + R01 (PIT Stock Breadth Confirmation)

**Date:** 2026-07-21
**Type:** Research run. No production pin changes, no production code edits, no dashboard changes.
**Production pin (untouched):** `improved_frontier_phase5_fragility_guard`
**Run verdict:** R00 **COMPLETE** · R01 **BLOCKED_PREREQUISITE** (Norgate Data not installed — stopped per run card; no substitute universe used)

---

## Commands Executed

```bash
pwd; git status --short; git branch --show-current; git worktree list
ls data/stock_breadth/raw/                      # only *_TEMPLATE.csv placeholders
python3 -c "import norgatedata"                 # ModuleNotFoundError
python3 scripts/atlas_offensive_run01/build_cost_library.py       # 3 iterations (see Warnings)
python3 scripts/atlas_offensive_run01/check_r01_prerequisites.py  # -> R01_BLOCKED_PREREQUISITE
```

Required reading completed first: `CLAUDE.md`; Master Run Book Part A + R00/R01 cards;
Phase 5A scaffold report; `scripts/build_pit_stock_breadth_panel.py`.

## Files Created

| File | Purpose |
|---|---|
| `docs/research/atlas_offensive/offensive_holdout_declaration.md` | Seals 2026-01-01+ holdout; demotes 2024-04-19 holdout to descriptive-only |
| `data/research/atlas_offensive_trial_registry.csv` | Trial registry (run_id, date, variant, params, primary_metric, value, verdict, notes) |
| `docs/research/atlas_offensive/preregistration_template.md` | Standing pre-registration template for all runs |
| `docs/research/atlas_offensive/run01_preregistration.md` | R01's locked pre-registration (filed before any experiment; binding on the future executing session) |
| `data/research/atlas_offensive_cost_library.csv` | Per-instrument cost library v1: measured spreads, 35-ETF universe incl. SPY/QQQ |
| `scripts/atlas_offensive_run01/build_cost_library.py` | Cost library builder (reproducible) |
| `scripts/atlas_offensive_run01/check_r01_prerequisites.py` | R01 prerequisite gate (reproducible) |
| `data/research/atlas_offensive_run01/r01_prerequisite_check.csv` | Gate output: R01_BLOCKED_PREREQUISITE |
| `docs/research/atlas_offensive/run01_report.md` | This report |

No production files, pins, weights, dashboard bundles, or `public/dashboard-data.json` touched.
No `git add` performed; nothing committed.

---

## PHASE 1 — R00 Governance Reset: COMPLETE

1. **Holdout sealed.** 2026-01-01 holdout start declared; data on/after it untouchable until
   final Book promotion decisions with human authorization. The burned 2024-04-19 holdout is
   demoted to descriptive-only. One amendment made during the run (before any experiment):
   the seal covers strategy/signal/return data; current-market *microstructure* measurements
   (spread widths) are explicitly permitted for the cost library since they carry no forward
   return information and minute-level data only exists for the trailing month.
2. **Trial registry created** with the required columns. Current rows: R00 governance
   artifacts (COMPLETE), R01 run-level status (BLOCKED_PREREQUISITE). **Experimental variant
   count this run: 0** — nothing was backtested.
3. **Pre-registration template + R01 pre-registration written before any experiment.** R01's
   hypothesis (unbiased lift ≥ +0.26%/4w), both locked grids, null controls (200 placements +
   inverted signal), and success/failure branches are locked and binding on whichever session
   executes R01 after data installation.
4. **Cost library v1 built — the 10bps flat assumption is retired for Atlas Offensive runs.**

### Cost library method (and why it took three iterations)

- **Iteration 1 (rejected):** daily-bar Corwin–Schultz/Abdi–Ranaldo/Roll estimators gave
  SPY ≈ 28bp one-way — ~50× the true quoted spread. Daily estimators measure volatility, not
  spread, at this liquidity tier.
- **Iteration 2 (rejected):** overnight-gap adjustment + closing-quote snapshots still left
  the median estimate at SPY ≈ 12bp one-way. Overstating costs re-creates the exact
  α-amplitude suppression the run book documents (Lesson 3), so this was not shippable.
- **Iteration 3 (shipped):** quiet-minute proxy — P10 of RTH 1-minute (high−low)/mid over the
  last 5 sessions (in a quiet minute a liquid ETF's traded range collapses toward its spread),
  P50 fallback where single-trade minutes dominate, valid closing NBBO quotes taken when
  tighter, daily estimators retained as labeled upper bounds, floor 0.25bp.

Headline one-way costs (bp): SPY 0.47 · QQQ 1.43 · IWM 0.67 · sector XLs 0.9–1.7 ·
BIL 0.27 · TLT 0.30 · GLD 0.94 · EEM 1.15 · worst instrument SLV 1.88. Every instrument
carries a `one_way_cost_2x_bps` column for the mandatory 2x-cost stress reporting.

**Caveats (recorded honestly):** measured in a calm July-2026 tape; spreads widen in stress —
the pre-registered 2x-cost reporting is the stress allowance until R46 supplies live fills.
No market-impact term (negligible at retail size). Quote snapshots taken after hours are
filtered; four instruments use closing-NBBO as primary (`MEASURED_QUOTE`).

---

## PHASE 2 — R01 PIT Stock Breadth Confirmation: BLOCKED AT PREREQUISITE GATE

Per the run card ("STOP and report if missing") and Master Run Book §A.4, R01 did not execute.

| Prerequisite | Status |
|---|---|
| Norgate Data subscription active and exportable | **FAIL** — `norgatedata` package not installed; no Norgate app on this Mac |
| `data/stock_breadth/raw/` real inputs (index_membership, stock_prices_daily, security_master) | **FAIL** — only `*_TEMPLATE.csv` placeholders (scaffold rejects these by design) |
| `scripts/build_pit_stock_breadth_panel.py` present | PASS |
| Phase 1 (R00) artifacts written | PASS (all 5) |

Full detail: `data/research/atlas_offensive_run01/r01_prerequisite_check.csv`.

**No substitute universe was scraped** — the survivorship-biased Phase 5A-Free diagnostic
(+0.517%/4w stock breadth vs −0.457%/4w ETF breadth in calm_trend) remains descriptive-only,
which is precisely the claim R01 exists to test on honest data.

### Biased-vs-unbiased diagnostic table

Not available — unbiased leg blocked. Biased reference (descriptive-only, from Phase 5A-Free):
calm_trend top-vs-bottom stock-breadth tercile ≈ **+0.517%/4w**; ETF-level breadth same state
≈ **−0.457%/4w**. Pre-registered pass threshold for the unbiased rerun: **≥ +0.26%/4w** with
correct tercile ordering.

### Variant table / null results

None — zero variants evaluated (registry reflects this).

### Exact next human action to unblock R01

1. Subscribe to **Norgate Data** (Platinum or Diamond — historical S&P 500 constituents +
   delisted securities require these tiers; ~$110/mo per the run book).
2. **Norgate Data Updater is Windows-only.** Run it on a Windows machine/VM, install the
   *US Stocks* database + *Index Constituent* plugin, and export (via the `norgatedata`
   Python package on that machine): PIT S&P 500 membership intervals, delisting-aware daily
   adjusted prices to 2005 (delisted symbols included), and the security master.
3. Copy exports into `data/stock_breadth/raw/` as `index_membership.csv|parquet`,
   `stock_prices_daily.parquet` (or partitioned dir), `security_master.csv`, optionally
   `sector_classification.csv` — schemas in `data/stock_breadth/raw/README_FILL_THESE_FILES.md`.
   Keep the raw panel out of normal git (100 MB limit; see Phase 5A git plan).
4. Re-run `python3 scripts/atlas_offensive_run01/check_r01_prerequisites.py` → then
   `python3 scripts/build_pit_stock_breadth_panel.py` → then execute R01 **exactly per
   `docs/research/atlas_offensive/run01_preregistration.md`** (no grid changes permitted).

---

## Verdicts

| Item | Verdict |
|---|---|
| R00 governance artifacts | **COMPLETE** (Adopt — these are now binding program infrastructure) |
| Cost library v1 | **Adopt-into-Book infrastructure** — supersedes 10bps flat for Atlas Offensive runs; superseded in turn by R46 live fills |
| R01 | **BLOCKED_PREREQUISITE** — not Drop, not Research-only; hypothesis untested, pre-registration locked and waiting |
| Standalone / combination help | n/a — no strategy variant was built or evaluated |

## Warnings and Anomalies

1. **Session ran after US market close (23:41 ET)** — quote snapshots are closing/after-hours
   NBBO; implausible (>20bp) quotes rejected, minute-bar proxy used as primary.
2. **Daily-bar spread estimators are unusable at this liquidity tier** (10–40bp readings vs
   sub-2bp reality). They remain in the CSV strictly as labeled upper bounds. Any future run
   citing them as effective spreads would be wrong.
3. **Cost library floor cases:** HYG/LQD/TIP/DBA P10 or P50 readings near zero hit the 0.25bp
   floor; plausible for these tickers but flagged for R46 verification.
4. **Holdout declaration amended once during the run** (microstructure carve-out) — done
   before any experiment executed and documented in both the declaration and this report.
5. The working tree carries ~300 pre-existing modified/untracked files from earlier phases;
   none were touched by this run.

## Git Status After Work

Branch `main`, nothing committed, nothing staged. New untracked paths from this run only:

```
data/research/atlas_offensive_cost_library.csv
data/research/atlas_offensive_trial_registry.csv
data/research/atlas_offensive_run01/            (r01_prerequisite_check.csv)
scripts/atlas_offensive_run01/                  (build_cost_library.py, check_r01_prerequisites.py)
docs/research/atlas_offensive/offensive_holdout_declaration.md
docs/research/atlas_offensive/preregistration_template.md
docs/research/atlas_offensive/run01_preregistration.md
docs/research/atlas_offensive/run01_report.md
```

Production pin, weights, `public/dashboard-data.json`, and dashboard bundles untouched.
Nothing promoted; Book adoption and pin changes remain gated on explicit human authorization.
