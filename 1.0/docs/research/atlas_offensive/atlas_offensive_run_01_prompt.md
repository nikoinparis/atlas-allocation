# Atlas Offensive — First Run Prompt (v2.0, aligned with Master Run Book)

Supersedes v1. Copy-paste everything below the line to Fable 5 to execute the
program's first run: **R00 (Governance Reset) + R01 (PIT Stock Breadth
Confirmation)** from `atlas_offensive_master_run_book.md`. Do not edit
mid-run; scope changes require a new pre-registration.

---

You are executing the FIRST RUN of the Atlas Offensive program: **R00 + R01**
from the Master Run Book.

**Read first, in this order:**
1. `CLAUDE.md`
2. `docs/research/atlas_offensive/atlas_offensive_master_run_book.md` — Part A
   in full (backstory, return-first doctrine, standing rules), then the R00
   and R01 run cards.
3. `docs/research/2026-05-07_phase_5a_pit_stock_breadth_data_scaffold_report.md`
   and `scripts/build_pit_stock_breadth_panel.py`.

**Type:** Research run. No production pin changes, no production code edits,
no dashboard changes. Work only in `scripts/atlas_offensive_run01/` with
outputs in `data/research/atlas_offensive_run01/` and reports in
`docs/research/atlas_offensive/`.

**Prime directive (from the run book):** return first. Primary metrics are
net CAGR, expected log growth, per-trade/per-state expectancy, and residual
alpha. Volatility, drawdown, CVaR, and Sharpe are RECORDED in every table but
are NOT pass/fail gates. The only binding gates are integrity gates:
point-in-time data, survivorship-free universe, 1-week signal lags,
time-ordered splits, per-instrument realistic costs, every variant logged,
null controls for headline claims.

---

## PHASE 1 — R00: Governance Reset (do this before any backtest)

1. **Seal the new holdout:** declare 2026-01-01 as the holdout start. All
   data on/after it is untouchable in this and future runs until final Book
   promotion decisions. Write the declaration to
   `docs/research/atlas_offensive/offensive_holdout_declaration.md`. The old
   2024-04-19 holdout is demoted to descriptive-only.
2. **Create the trial registry:** a CSV/SQLite at
   `data/research/atlas_offensive_trial_registry.csv` with columns
   (run_id, date, variant, params, primary_metric, value, verdict, notes).
   Every variant evaluated in any Atlas Offensive run gets a row.
3. **Write the pre-registration template** and this run's own
   pre-registration file BEFORE any experiment executes (hypothesis, locked
   grids, thresholds — as specified in Phase 2 below).
4. **Start the per-instrument cost library:** measured spread estimates for
   the ETFs currently traded plus SPY/QQQ; retire the 10bps flat assumption;
   store at `data/research/atlas_offensive_cost_library.csv`.

## PHASE 2 — R01: PIT Stock Breadth Confirmation

**Prerequisite check (STOP and report if any is missing):**
- Norgate Data subscription active and exportable (the owner must have
  purchased it — do not scrape a substitute universe).
- `scripts/build_pit_stock_breadth_panel.py` present.
- Phase 1 artifacts written.

**Backstory you must internalize:** the survivorship-biased Phase 5A-Free
diagnostic showed stock-level breadth predicts +0.517% per 4 weeks of SPY
return inside calm_trend weeks, while ETF-level breadth shows −0.457%.
Calm_trend is ~27% of all weeks and the system currently earns ~4.2%
annualized there while SPY runs away. This run decides whether that lift is
real on honest point-in-time data.

**Pre-registered hypothesis:** unbiased PIT breadth retains ≥ half the biased
lift (≥ +0.26% per 4 weeks, top-vs-bottom breadth tercile within calm_trend).

**Locked design:**
1. Export PIT S&P 500 membership + delisting-aware daily prices to 2005 via
   Norgate; run the existing scaffold to build the breadth panel.
2. Build weekly signals, all lagged 1 week: `pct_above_200d_ma`,
   advance/decline ratio, net new highs.
3. Reproduce the 5A diagnostic exactly but unbiased: 4-week forward SPY
   returns by breadth tercile within calm_trend weeks; development window
   through 2025-12-31; the sealed 2026+ holdout untouched.
4. If the hypothesis passes, test breadth-scaled offense in calm_trend AND
   neutral_mixed via the checkpoint wrapper, with BOTH locked grids:
   - Conservative: ×0.85 / ×1.00 / ×1.15 (breadth <40% / 40–70% / >70%)
   - Return-first: ×1.00 / ×1.15 / ×1.30
   No other grids may be added mid-run.
5. Null controls: 200 random-tercile placements; inverted-signal control.
6. Costs: per-instrument library from Phase 1; also report at 2× costs.

**Locked success criteria (return-first):**
- Diagnostic: unbiased lift ≥ +0.26%/4w with correct tercile ordering.
- Portfolio: best locked variant improves full-period net CAGR and log
  growth vs the unmodified base in walk-forward, beats ≥90% of placement
  nulls, and survives 2× costs. Report (do not gate) Sharpe/MaxDD/CVaR and
  the beta-vs-alpha decomposition of the improvement.

**Prohibited:** consulting the sealed holdout; tuning outside locked grids;
touching production pins/weights/`public/dashboard-data.json`; `git add -A`;
regenerating dashboard bundles.

**Report** (`docs/research/atlas_offensive/run01_report.md`, per CLAUDE.md):
commands executed; files changed; biased-vs-unbiased diagnostic table;
variant table with return-first metrics primary and risk metrics recorded;
null results; trial count (every variant in the registry); verdict per
variant: Adopt-into-Book / Confirm-in-follow-up / Research-only / Drop;
warnings; git status.

**Verdict and branching (from the run book):**
- Hypothesis passes + a locked variant improves net CAGR →
  **CONFIRMED-FOR-HUMAN-REVIEW**: breadth becomes a REGIME_BRAIN input;
  recommend proceeding to R02 (PBI native rebuild) and R03 (stock universe)
  in parallel.
- Diagnostic < +0.26%/4w → classify breadth **DIAGNOSTIC-ONLY permanently**,
  record the survivorship lesson in the registry, and state whether Norgate
  remains justified by R03 alone (it almost certainly does — say so
  explicitly with reasoning).
- Ambiguous → **RESEARCH-ONLY** with exactly one pre-registered follow-up
  experiment specified for the next session.

Never promote anything yourself; pin changes and Book adoption require
explicit human authorization.
