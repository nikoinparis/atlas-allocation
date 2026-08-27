# Quant idea challengers v1

Data snapshot: `20260821T213726Z-5ea7a9e5e4ce214c`. Live execution remains disabled.

| Idea | Outcome | Evidence |
|---|---:|---|
| Overnight effect (SPY) | REJECTED | 2021+ net Sharpe -5.48; CAGR -42.33%; Failed frozen post-2021 net gate |
| Overnight effect (QQQ) | REJECTED | 2021+ net Sharpe -3.92; CAGR -41.14%; Failed frozen post-2021 net gate |
| Overnight effect (IWM) | REJECTED | 2021+ net Sharpe -3.66; CAGR -39.41%; Failed frozen post-2021 net gate |
| RAAM-inspired allocation | REJECTED | Net Sharpe 0.78 vs 0.71; Frozen risk-adjusted gate passed, but the family failed benchmark-relative White Reality Check |
| Quarter-Kelly sizing | REJECTED | Frozen weight 50.0%; Kelly cannot create edge; it only sizes the frozen source strategy |
| First 5-minute candle / 12 EMA / ATR | BLOCKED | Causal simulator and tests complete; No PIT one-minute/NBBO dataset |
| Options-vs-stock disagreement | BLOCKED | Put-call-parity feature contract complete; No OPRA-quality PIT quotes, dividends, or trade signs |
| Politician/influencer delayed signal | BLOCKED | Public-time gate complete; No complete timestamped all-person/archive dataset |
| Indonesia market-neutral pairs | BLOCKED | Existing causal pair engine retained; Short-sale financing, borrow inventory, and cost history unavailable |
| Derivatives execution | BLOCKED | Research features allowed; trading disabled; Margin, Greeks, expiry, assignment and settlement oracle absent |
| NuScale/SMR thematic sleeve | RESEARCH_ONLY | Scenario/watchlist candidate, not systematic alpha; Binary commercial milestones and dilution; no frozen quantitative edge |
| Copy famous traders | REJECTED | Automatic copying prohibited; Reporting delays, selection bias, promotion risk; feature-only research allowed |
| IC/ICIR research scoring | WORKING | Annualized ICIR 0.27; Infrastructure metric; not a standalone promotion |
| Existing ETF pairs strategy | REJECTED | Net Sharpe -0.75 at 50 bps + borrow; Random/stale controls won; economics failed after costs |
| Monte Carlo robustness | WORKING | Existing block/tail engine integrated; Risk falsification tool, never proof of future profit |

## Interpretation

A rejected strategy is a completed experiment, not a missing deliverable. A blocked strategy has its causal contract implemented but lacks data or market access needed for a defensible real test. No retrospective pass is labeled proven alpha.
