# Portfolio Optimizer

A systematic equity research project, run as an adversarial process: every idea is
pre-registered, tested against a declared null, and killed when it fails.

**312 recorded research steps. Nineteen signal families closed. Zero strategies promoted.
Zero dollars traded.**

That last line is the result, not an apology for one. A research process that promotes
nothing from 312 attempts is either broken or working exactly as intended, and the record
below is the evidence for which.

---

## What this project set out to do

Find a systematic equity strategy with a real edge — using only free data, on a laptop,
held to the standard a quant firm would apply. The dashboard shows candidate strategies with
trailing returns from 100% to 175%. **None of them is an edge, and the research explains
why.**

## The main findings

**1. The strategies never had cross-sectional skill.**
Thirteen dashboard signals and fourteen closed families were measured three beta-neutral
ways — rank information coefficient, top-minus-bottom decile spread, and decile
monotonicity. None clears Bonferroni. More decisively, **none orders its deciles**:
monotonicity sits within ±0.17 of zero for every signal tested. A signal with genuine content
ranks its universe; these rank nothing.
*(Steps 296, 298, 299, 300)*

**2. The headline returns were market beta and a few lucky names.**
Taking the one signal that survived out-of-sample testing and neutralising its market
exposure dropped it from 16.65% CAGR to **1.59%** — roughly ninety per cent of the return was
beta. The top-N books were not winning on selection.
*(Step 295)*

**3. Nothing survives a window it was not selected on.**
Every fundamental panel began in 2023, so no strategy here had ever been tested outside its
selection window. Acquiring SEC Financial Statement Data Sets back to 2012 fixed that.
**Nought of six survive**; three of six have the wrong sign. Growth, the flagship, lost 15.4
points a year to its own scored universe.
*(Steps 287, 289, 290)*

**4. Breadth is not the binding constraint — skill is.**
The project spent roughly fifty steps trying to raise breadth on the theory that
`IR = IC × √BR` made it the lever. It is a product: an IC indistinguishable from zero yields
an IR indistinguishable from zero *at any breadth*. Adding a genuinely uncorrelated asset
raised effective bets from 2.00 to 2.88 and bought **0.021 of Sharpe**. Every liquid domain
measured collapses — 35 ETFs give 4.16 effective assets, 20 crypto assets give 3.09.
*(Steps 246, 277, 279, 285, 296)*

**5. A one-week date convention invalidated the project's best result.**
Two artifact families disagreed about whether a return stamped at date D was the week
*ending* or *beginning* at D, and nothing recorded which. Joining them by date compared week
*t* against week *t+1*, producing near-zero correlations that looked like diversification.
Corrected, the "independent" strategy correlates **+0.57 to +0.77** with the others, and a
blend that appeared to beat both components beats neither. The finding was withdrawn and the
forward clock built on it was superseded before it started.
*(Steps 291, 292, 294)*

**6. Market-neutral structure works. There was nothing to put in it.**
A long-short book removes market beta by construction — realised betas of −0.009 and +0.007,
clearing an orthogonality gate that fourteen families had failed. Both signals tested in it
had no skill. The machinery is sound and unfuelled.
*(Steps 293, 295)*

## What was tried

Roughly forty signal families across eight categories — momentum is four of them.

| category | families |
|---|---|
| Price / return | short-term reversal, seasonal momentum, opening-range breakout, coskewness, idiosyncratic skewness, trend consistency, sector dispersion, vol-of-vol, downside beta, residual reversal, industry-return-of-big-firms, daily OHLCV zoo, 22-signal literature screen, cross-asset crisis trend, futures trend |
| Fundamental | growth, cash conversion, balance-sheet quality, profitability, shareholder discipline, quality acceleration, earnings yield, FCF yield, sales yield, composite value, quality-at-reasonable-price, low asset growth, accounting-change family |
| Events | PEAD / SUE, 13D & 13G activist filings, Form 4 insider clusters, Form 4 routine-vs-opportunistic |
| Positioning / flow | 13F institutional linkage, FINRA short interest, FINRA daily short-sale volume |
| Text | 10-K language change, earnings-call transcripts |
| Network | supply-chain graph |
| Other markets | 35-ETF multi-asset, 20-asset crypto, futures + roll repair |
| Structure & ML | pairs / statistical arbitrage, long-short market-neutral, risk-budgeted sizing, breadth repair, meta-labeling, triple-barrier labelling, fractional differentiation, MDA/MDI importance, market-state and macro-state classifiers |

## Method

The rules are in [`CLAUDE.md`](CLAUDE.md) and they are enforced, not aspirational:

- **Pre-registration.** Configurations, gates, signs and outcome readings are frozen in
  `2.0/config/` before results exist. A signal declared positive that measures negative is
  reported as refuted, never re-interpreted as contrarian.
- **Point-in-time or it does not count.** Universes are built from historical filer rosters;
  a filing enters on its filing date, never its period end.
- **Multiple testing compounds across the whole project**, not the current batch.
- **Costs are not optional** — 0, 10, 50, 100bps, and borrow on any short.
- **Negative results are preserved.** [`2.0/PROJECT_HISTORY.md`](2.0/PROJECT_HISTORY.md) is
  append-only and includes every error the author made, several of which invalidated earlier
  conclusions.

### On errors

Ten measurement defects were found and recorded, most by noticing a number that could not
mean what it appeared to mean. Three times in a single session a result cleared a
significance bar and dissolved under inspection: an insider signal at p=0.0000 that was a
presence test on a 93.3%-zero series; a trend signal at p=0.0017 with a *negative* decile
spread; a text signal at p=0.0030 sitting below its own data's resolution. **A process that
stopped at the p-value would have reported all three as discoveries.**

## What happens next

Five forward clocks began on **2026-09-11**: a residual composite, an equal-weight benchmark,
a tie-agnostic companion, an earnings-surprise book and a valuation book. Each requires 52
untouched weeks. A missed weekly window cannot be backfilled, and the historical record never
advances a clock.

This is the only source of evidence the project has left that has not already been searched.

## Repository layout

```
2.0/
  dashboard/     Next.js research dashboard (the deployed site)
  scripts/       acquisition, construction, testing and audit scripts
  src/           forward-evidence ledger, return conventions, evaluation
  config/        frozen manifests, pre-registrations, forward protocols
  docs/          runbooks, protocols, the research queue
  evidence/      saved outputs of every experiment
  PROJECT_HISTORY.md   the full append-only record, 312 steps
CLAUDE.md        the operating rules
```

## Running it

```bash
cd 2.0 && python -m venv .venv && ./.venv/bin/pip install -r requirements.txt
./.venv/bin/python scripts/rebuild_all_data.py --core   # panels the dashboard and clocks need
cd dashboard && npm install && npm run dev
```

Raw acquisition caches are not stored in the repository — they are large and every byte is
re-downloadable from SEC EDGAR, FINRA and public price sources. `rebuild_all_data.py`
re-acquires them; `--core` fetches only what the dashboard and the forward clocks read.

Point-in-time vintage snapshots **cannot** be re-downloaded, because they record what a source
said on a given date. Those are preserved.

## Honest limits

- The universe is US-listed issuers; the fundamental work concentrated on technology and
  energy before being widened to 2,681 issuers across 69 sectors in Step 300.
- Weekly data throughout. Several ideas — pairs convergence in particular — are properly
  daily, and a negative result on weekly bars is weaker than a positive one would be.
- Short-sale borrow is modelled as a flat annual charge. Real borrow is name-specific and
  worst on exactly the names a short leg wants.
- No strategy here has forward evidence. As of this writing the clocks have just begun.

## Licence and status

Research only. Nothing in this repository is investment advice, and every configuration
carries `live_trading_enabled: false`.
