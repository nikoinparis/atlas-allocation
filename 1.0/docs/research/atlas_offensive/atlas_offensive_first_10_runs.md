# Atlas Offensive — The First Ten Runs

Detailed specifications. Full field set for all 47 runs: `atlas_offensive_future_run_registry.csv`. Dependencies: `atlas_offensive_run_dependency_graph.md`.

---

## Run 0 — Governance Reset and New Holdout Declaration

**Theme:** Foundation. **Question:** Under what rules will every offensive claim be believed?
**Work:** (1) Seal a new holdout: all data from a declared 2026 date forward is untouchable until final promotion gates; the burned 2024-04-19 holdout is demoted to descriptive. (2) Stand up the trial registry (SQLite/CSV): every strategy, parameter family, feature family, target, universe, model, seed, and post-hoc modification gets a row — including agent-generated candidates. (3) Pre-registration template (Confirm1 style) required for every subsequent run. (4) Per-instrument cost model library replacing the 10bps flat assumption (measured ETF/stock spreads, futures commission+roll, options at-the-spread fills, borrow-fee schedule). (5) Return-first gate set drafted (Part IX): net CAGR / log growth / expectancy primary; risk reported as price paid; drawdown vetoes deferred to Run 45.
**Deliverables:** governance doc, registry schema, sealed-holdout declaration, cost library.
**Duration:** days. **Cost:** $0. **Advance when:** registry operational and holdout sealed. **This run cannot fail; it can only be skipped — do not skip it.**

## Run 1 — PIT Stock Breadth Confirmation

**Theme:** Core alpha / data unlock. **Question:** Does the +0.517%/4w calm-trend breadth lift survive survivorship-free point-in-time data?
**Prior evidence:** Phase 5A-Free diagnostic (biased, current-constituent): stock breadth +0.517%/4w in calm_trend where ETF breadth shows −0.457%. Scaffold `scripts/build_pit_stock_breadth_panel.py` already built.
**Work:** Purchase Norgate (~$110/mo). Export S&P 500 PIT constituents + delisting-aware prices to 2005. Run the existing pipeline. Build `pct_above_200d`, A/D ratio, net highs. Re-run the 5A diagnostic unbiased; if the lift holds, test the pre-specified Phase 5B state-tilt (breadth-quality offense scaling 0.85/1.0/1.15 in calm_trend).
**Gates (pre-registered):** calm-trend state-conditional Sharpe +0.10 in the 2010+ walk-forward; overall portfolio not worse; full Phase D battery.
**Failure:** PIT lift < half the biased diagnostic → downgrade breadth to diagnostic-only and log the survivorship lesson.
**Duration:** 1–2 weeks. **Cost:** ~$110/mo. **Dependencies:** R00.

## Run 2 — Regime Engine Offensive Rebuild (Native PBI + Jump Model)

**Theme:** Core alpha. **Question:** How much of the −12 to −23pp early-recovery episode gaps is recoverable when panic modifiers are not frozen at 1.0?
**Prior evidence:** Moonshot episode map (67% of early-recovery weeks inside stressed_panic; pin holds 53% BIL there); PBI beats 91% of placement nulls, inverted control hurts, Confirm1 locked-battery passes — all while wrapper-capped at ~+0.003 Sharpe.
**Work:** (1) Implement PBI as a native Layer-2B sub-state (`stressed_panic_improving`) rather than a wrapper multiplier. (2) Pre-register offense-base grids for that sub-state (e.g., 25/40/55/70% vs the current ~15%) with a hard per-episode stop (exit re-risk if drawdown deepens X% after entry). (3) Benchmark the whole 5-state engine against a statistical jump model and an HMM for label stability (transitions/year). (4) Prototype per-asset regime probabilities (3 assets, logistic, per the breakthrough audit's minimal experiment).
**Gates:** early-recovery capture +5pp per episode average; stressed-panic Sharpe not worsened; no single episode erasing >2 years of contribution in stress replay (2008 explicitly).
**Duration:** 3–6 weeks. **Cost:** $0. **Dependencies:** R01 (breadth confirmations feed PBI).

## Run 3 — Single-Stock Universe Foundation + Momentum Family

**Theme:** Core alpha. **Question:** Do cross-sectional momentum variants deliver on 500–2,000 stocks what 35 ETFs could not?
**Work:** (1) Build the panel: Norgate US, PIT Russell-1000-like membership, delisting returns, corporate actions, per-name cost estimates. (2) Implement the momentum family: 12-1, 6-1, 52-week-high proximity, residual momentum (vs rolling factor fits), volatility-scaled variants, skip-month conventions, crash-control overlays. (3) Decile spreads long/short *measured*, top-k long-only *implementable*. (4) Decade-by-decade decomposition; post-2010 significance required (post-publication decay is the null).
**Gates:** post-2010 net L/S spread t>2 for ≥1 variant; long-only top-k beats SPY risk-adjusted in walk-forward.
**Duration:** 1–2 months. **Cost:** in Norgate. **Dependencies:** R01. **This run is the platform: every later equity run inherits its panel.**

## Run 4 — Concentrated Long-Only Compounder

**Theme:** Core alpha. **Question:** Can concentrated top-k (5–20 names) ranking beat SPY net of costs — the first deployable offensive product?
**Work:** Top-k portfolios from Run 3's best ranks; position stops; sector caps; turnover-banded rebalancing; compare k ∈ {5,10,20} and rebalance ∈ {1w,2w,1m}. Explicit comparison vs the HRP-diluted expression of identical signals (the concentration test the old stack never ran).
**Gates:** net CAGR > SPY+2pp, or = SPY with MaxDD ≥10pp better; expectancy positive across three regimes.
**Duration:** 2–4 weeks on Run 3's infrastructure. **Dependencies:** R03.

## Run 5 — Long/Short Equity Engine v1

**Theme:** Core alpha. **Question:** Does shorting unlock the relative signals that demonstrably failed long-only (Track C)?
**Work:** Easy-borrow large-cap universe; dollar-neutral, beta-verified (|β|<0.1), sector-neutralized books from residual momentum + short-term reversal + factor composites; borrow-fee haircuts from live IBKR data collection (start day one); cost-doubling stress; squeeze risk filters (short-interest screens).
**Gates:** net market-neutral Sharpe > 0.8; both legs contribute; survives cost doubling.
**Failure:** costs/borrow eat the spread → document retail L/S infeasibility honestly and route relative signals into long-only tilts (Run 4) instead.
**Duration:** 2–3 months. **Dependencies:** R03.

## Run 6 — Fundamental Factor Library

**Theme:** Core alpha. **Question:** Which published factors replicate on retail PIT data (Sharadar as-reported)?
**Work:** Value composite (E/P, B/P, FCF/EV, shareholder yield), profitability/quality (GP/A, margins, accruals), investment/issuance, BAB. FDR control across the family (this is a factor zoo by construction — the registry counts every tested definition). Compare against Ken-French-style published series for sanity.
**Gates:** ≥3 factors with net spread t>2 and correct published sign post-2010.
**Duration:** 1–2 months. **Cost:** ~$50/mo (Sharadar). **Dependencies:** R03.

## Run 7 — Statistical Arbitrage v1

**Theme:** Adjacent alpha. **Question:** Does residual mean reversion pay after real costs at daily frequency?
**Prior:** classic distance pairs publicly decayed; internal reversal ICs (0.18–0.41 holdout) are the strongest signal evidence in the repo; ETF pair (HYG/LQD) failure was universe-starvation, not refutation.
**Work:** cluster-based pair formation (correlation/graph clustering, not exhaustive scan); PCA-residual reversal portfolios; Kalman hedge ratios; regime-break stops; strict cost + borrow accounting; bear-market conditional analysis (where the literature says the alpha hides).
**Gates:** dollar-neutral net Sharpe > 1 on 2015+ sample.
**Duration:** 2–3 months. **Dependencies:** R05 (shorting economics proven first).

## Run 8 — Micro-Futures Trend and Macro Platform

**Theme:** Core alpha, parallel track (independent of equity runs). **Question:** Does multi-market trend replication work at solo scale?
**Work:** 10–15 micro/mini futures (MES, MNQ, M2K, ZN/ZF, micro gold/silver/crude, micro FX majors); multi-speed TSMOM ensemble (2w–12m) + breakout variants; vol-scaled sizing, 2× notional cap; roll modeling; crisis-window analysis (2008/2020/2022); benchmark vs SG Trend and trend ETFs (DBMF/KMLM). Capital gate first: owner declares the futures allocation (gap G08; $10–25k practical minimum).
**Gates:** correlation < 0.3 to equity book; positive standalone expectancy after micro-scale frictions.
**Duration:** 2–3 months. **Cost:** ~$100–200/mo data.

## Run 9 — Macro Factor Conditioning v2 (Vintage Data)

**Theme:** Adjacent alpha. **Question:** Do growth/inflation quadrants allocate capital better than pooling neutral_mixed — once vintages, honest lags, and monthly cadence fix the V1–V3 defects?
**Prior:** dev-period quadrant spread +1.41%/4w (real); holdout rank inversion (the open question, G15); internal conclusion that weekly-overlay framing was the error.
**Work:** ALFRED vintage panel (free); expanding PCA with 2-month publication lag; quadrants condition *monthly sleeve budgets* (equity/futures/defensive mix), not weekly tilts; explicit test of whether the 2024–26 "stress" classification was regime shift or artifact.
**Gates:** holdout rank consistency achieved; conditional allocation beats pooled in walk-forward.
**Duration:** 3–6 weeks. **Cost:** $0. **Dependencies:** R08 helpful (more sleeves to condition), not required.

---

**After Run 9, the program branches** (see dependency graph): the options track (R13–R16) can start any time after R00 given an ORATS purchase; the ML ladder (R22+) starts once R03+R06 provide the panel; integration runs (R42+) wait for three proven engines. The full sequence: `atlas_offensive_complete_research_sequence.md`.
