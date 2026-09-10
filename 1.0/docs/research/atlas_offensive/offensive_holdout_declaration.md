# Atlas Offensive — Holdout Declaration (SEALED)

**Declared:** 2026-07-21 (Atlas Offensive R00 — Governance Reset)
**Status:** SEALED — binding on every Atlas Offensive run (R00–R63)
**Production pin (untouched by this program):** `improved_frontier_phase5_fragility_guard`

---

## 1. The sealed holdout

- **Holdout start date: 2026-01-01.**
- All market data, returns, signals, and derived artifacts dated **on or after 2026-01-01** are
  **untouchable** for any model fitting, signal selection, parameter tuning, variant ranking,
  diagnostic table, or interim evaluation in any Atlas Offensive run.
- Development windows for every Atlas Offensive experiment must end **2025-12-31** or earlier.
- The holdout may be consulted **exactly once per final Book promotion decision**, and only with
  explicit human authorization at that decision point. It is never consulted to pick between
  variants mid-program.

## 2. Demotion of the old holdout

- The prior holdout boundary of **2024-04-19** (used across the Phase D validation stack and
  many phases since) is hereby **demoted to descriptive-only** status.
- Rationale (Master Run Book, R00 card): it has been consulted repeatedly across ~60 phases of
  research and promotion decisions. Its selective power is spent; results split on it may still
  be *reported* as descriptive context, but it can no longer serve as an out-of-sample claim.
- No Atlas Offensive run may cite performance after 2024-04-19 (but before 2026-01-01) as
  "holdout" evidence. That window is development data under this program.

## 3. Enforcement rules

1. Every Atlas Offensive script that loads dated data must truncate to `date < 2026-01-01`
   before any experimental computation. The seal covers strategy, signal, and return data —
   anything that could inform variant selection. Microstructure infrastructure measurements
   (bid-ask spread widths, fee schedules) may use current-market data: they contain no forward
   return information, and realistic cost inputs must reflect the market as traded today.
   Daily-bar spread *estimators* still use pre-2026 windows where the method permits.
2. Any accidental consultation of sealed data voids the affected results, must be logged in the
   trial registry (`data/research/atlas_offensive_trial_registry.csv`) with verdict
   `VOID_HOLDOUT_CONTAMINATION`, and the experiment must be re-run from a clean state.
3. Unsealing requires: (a) a final Book promotion decision is on the table, (b) explicit human
   authorization recorded in the relevant run report, (c) a one-shot evaluation — no iteration
   against holdout results.
4. This declaration is superseded only by a successor declaration written under a future R63
   annual program audit with human authorization.

## 4. Relation to standing integrity gates

This holdout seal is one of the binding integrity gates of the return-first doctrine
(Master Run Book §A.3): point-in-time data, survivorship-free universes, 1-week signal lags,
time-ordered splits, per-instrument realistic costs, full trial logging, and null controls for
headline claims. Volatility, drawdown, CVaR, and Sharpe are recorded but are not gates during
discovery.
