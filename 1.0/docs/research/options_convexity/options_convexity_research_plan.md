# Options Convexity Overlay — Research Plan

> **Status: standalone research experiment.** This is **not** Track A/B/C/D and
> is **not** a production strategy. It does not modify, import, or change any
> production allocation logic. It only *reads* existing artifacts and writes its
> own outputs to `data/research/options_convexity/`. Nothing here is promoted
> into the main ETF strategy.

## 1. Question

The core ETF portfolio (production pin `improved_frontier_phase5_fragility_guard`)
is already defensive and regime-aware. Can a **small, rarely-active options
sleeve** improve *upside capture* during rare, high-confidence bullish setups —
without materially worsening Sharpe, drawdown, or CVaR?

The hypothesis: convex payoffs (defined-risk call spreads) bought only when the
system is unusually bullish could add asymmetric upside that the linear ETF
sleeve cannot, while the strict activation gates and a hard 3% premium cap keep
the downside contained.

## 2. What this experiment reads (read-only)

| Input | Source artifact |
|-------|-----------------|
| Baseline ETF weights | `data/05_layer3_portfolio_construction/portfolio_version_weights_improved_frontier_phase5_fragility_guard.csv` |
| Baseline weekly net returns | `data/05_layer3_portfolio_construction/portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv` |
| Regime / market-state history | `data/04_layer2b_risk_regime_engine/market_state_history.csv` |
| Weekly prices (underlyings) | `data/01_data_hub/weekly_prices.csv` |

The baseline is treated as fixed. The overlay sits on top and is **self-funded**
by reducing the matching ETF, never by adding leverage.

## 3. Eligible underlyings (v0)

`SPY`, `QQQ`, `IWM`, `TLT`, `GLD` — all highly liquid, all with full weekly
price history in this project (2005-01 → 2026-04).

## 4. Activation rules (v0)

An overlay activates for an ETF on a given week **only if all** hold (every
input is causal / lagged — no look-ahead):

1. **Risk-on / non-defensive regime** — `market_state ∈ {calm_trend, recovery_confirmed}`.
2. **Strong ETF trend** — trailing 13-week momentum ≥ +3% **and** 26-week ≥ +5% **and** price above its 40-week moving average.
3. **Positive baseline weight** — the ETF already carries ≥ 2% baseline weight.
4. **Not in panic / stress / drawdown-defense** — state not in `{stressed_panic, recovery_fragile}` and market drawdown shallower than −10%.
5. **Liquidity filter passes** — in proxy mode the five chosen ETFs are highly liquid (passes by construction); in live mode the bid/ask, OI and volume filters apply.
6. **IV not extremely elevated** — IV proxy below the 80th percentile of its own trailing 1-year range (skipped only if no IV history is available).
7. **Allocation stays small** — enforced at sizing time (see below).

Thresholds are simple round numbers chosen up front, **not** tuned to maximize
backtest performance, to avoid overfitting the activation logic.

## 5. Sizing

- Default premium budget: **2%** of portfolio value (range 1–3%).
- **Hard cap: total options premium never exceeds 3%** across all active options.
- Budget is capped by the matching ETF's baseline weight (self-funded).
- The premium is funded by reducing the matching ETF exposure (no leverage).

## 6. Option structure (v0)

Defined-risk **bull call spread**, preferred over naked long calls:

- Buy a call ~5% OTM (within the 3–7% band).
- Sell a same-expiration call ~15% OTM (within the 10–20% band).
- ~90 DTE (13 weeks), held to expiry, non-overlapping per underlying.
- Mid price = (bid + ask)/2 in live mode; Black-Scholes in proxy mode.
- Conservative entry slippage (5% markup on the debit) and an IV markup (×1.05)
  so options are modelled as **expensive**, biasing the proxy against the overlay.

## 7. Modes

1. **Live / snapshot mode** — pulls real option chains via `yfinance` for
   current research inspection (`option_data.load_live_option_chain`). Requires
   network; not used by the historical backtest.
2. **Historical proxy mode** — Black-Scholes pricing with a realized-volatility
   IV proxy. **This is what the backtest runs.** Results are explicitly
   **APPROXIMATE and not production-grade**, because no real historical
   option-chain data is available in this project.

## 8. Metrics compared (baseline vs baseline + overlay)

CAGR, annualized (arithmetic) return, annualized volatility, net Sharpe,
Sortino, max drawdown, Calmar, CVaR 5%, options hit rate, average / median /
worst option trade return, total premium spent per year, activations per year,
incremental return from the sleeve, incremental drawdown impact, and a
turnover/cost note.

## 9. Validation gates

The overlay only looks promising if **all** hold:

1. Net Sharpe improves vs baseline.
2. Max drawdown does not materially worsen.
3. CVaR does not materially worsen.
4. The overlay does not activate too frequently (kept rare).
5. The improvement is **not** driven by one lucky trade (re-checked after
   dropping the single best trade).
6. Results survive a basic train / holdout split (official holdout `2024-04-19`).
7. Costs / slippage are included.
8. Proxy assumptions are clearly documented.

## 10. Default verdict

The report defaults to **RESEARCH-ONLY** unless **all** gates pass, in which
case it may be labelled **CANDIDATE FOR FURTHER TESTING**. A clear failure of
core gates yields **REJECT**. No automatic promotion under any outcome.
