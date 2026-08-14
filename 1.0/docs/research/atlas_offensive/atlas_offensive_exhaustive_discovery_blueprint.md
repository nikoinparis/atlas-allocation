# ATLAS OFFENSIVE
## Exhaustive Discovery Blueprint for a High-Return Systematic Investment Machine

**Date:** 2026-07-21
**Type:** Discovery and research-planning assignment only. No implementation, no production changes, no promotion, no profitability claims.
**Production pin (unchanged):** `improved_frontier_phase5_fragility_guard`
**Companion machine-readable artifacts:** 16 files in `docs/research/atlas_offensive/` (registries, catalogs, ledgers, run program — see Part XVI).

---

## Executive Summary

Atlas Allocation is a defense-first machine that has reached the ceiling of its own design. Seven years of simulated history, ~60 research branches, and three independent internal audits agree on the diagnosis: the production strategy earns 7.13% CAGR at 0.948 Sharpe with 0.24 SPY beta and an average 27.6% cash position, inside a universe of 35 collinear ETFs, long-only, unlevered, rebalanced weekly, governed by Sharpe-first gates. Track B proved that within this envelope the only way to earn more is to hold more beta. Track C proved that genuine relative-value signals — residual momentum, reversal, carry — cannot be expressed long-only on 35 ETFs even when their information content is real (holdout rank IC up to 0.407 for the reversal composite). The Moonshot sprint proved that even the promoted signal is deliberately under-sized: walk-forward selection picks 3–6× the production amplitude at essentially every checkpoint since 2009, and the binding constraint is a governance gate, not the data.

The conclusion of this blueprint is not that Atlas failed. Its validation culture — walk-forward-only labels, pre-registration, 8-gate promotion discipline, null controls, honest negative results — is the single most valuable asset in the repository and transfers intact. What must change is everything the validation culture was pointed at.

**The recommended identity for Atlas Offensive is a staged multi-engine platform:**

1. **Keep defensive Atlas as a capital-preservation core** (it does its job: −11.6% MaxDD through two bear markets).
2. **Build breadth first:** a survivorship-free single-stock universe (Norgate + Sharadar, ~$150–250/month total) converts Atlas from a 5-effective-bet system into a 500–2,000-name cross-sectional platform — the precondition for nearly every strategy family and every ML method that failed or was deferred on ETF data.
3. **Add genuinely different return engines in order of evidence:** equity cross-section (momentum → factors → long/short), micro-futures trend and carry (native shorting and embedded leverage), options (real chain data replacing the Black–Scholes proxies that produced all four internal REJECT verdicts), and short-horizon effects (overnight drift; daily reversal).
4. **Only then** re-introduce sizing (fractional Kelly), modest leverage (≤1.5×), multi-strategy allocation, and — last — drawdown engineering, priced explicitly rather than assumed.

The highest-conviction near-term actions are internal, cheap, and already validated in diagnostic form: (a) purchase PIT stock data and confirm the +0.517%/4-week calm-trend breadth lift (Run 1); (b) natively integrate the panic-but-improving re-risking mechanism whose expression the current wrapper caps at +0.003 Sharpe despite targeting the single largest repeating opportunity in the dataset — early-recovery weeks where SPY compounds at +73% annualized while the pin holds 53% cash (Run 2).

The program is organized into **47 sequenced research runs** with dependencies, budgets, advancement criteria, and failure conditions (Part XI; `atlas_offensive_future_run_registry.csv`). Everything Atlas ever tested appears in the historical registry with an explicit retest classification (Part I). Every defensive constraint is audited with its suppression mechanism and removal risk (Part II). Every strategy family in the mandate is cataloged and tiered (Parts IV–VII). The evidence disclosure — what was searched, what was not, and why the search stopped — is in Part XIII and the ledgers.

---

## Table of Contents

- Part I — Complete Audit of Everything Atlas Has Ever Done
- Part II — Redefinition from Zero: Constraints and Candidate Identities
- Part III — Global Research Search: Method and Findings
- Part IV — Strategy Catalog (full entries for Tier 1–2; compact for Tier 3–6)
- Part V — Classical Model Catalog
- Part VI — Frontier AI and Deep Learning
- Part VII — Mathematics and Science Beyond Finance
- Part VIII — Data, Markets, and Infrastructure
- Part IX — High-Return Targets and Evaluation
- Part X — Unbiased Research Governance
- Part XI — The Sequenced Run Program (47 runs)
- Part XII — Prioritization Without Omission (Tier System and Scoring)
- Part XIII — Search Coverage Disclosure
- Part XIV — Standardized Entries (Tier 1–2 Full Detail)
- Part XV — Final Recommendations (the 35 Questions)
- Part XVI — Deliverables Index
- Appendix A — Glossary
- Appendix B — Required Tables Index

---

# PART I — Complete Audit of Everything Atlas Has Ever Done

**Full registry:** `atlas_offensive_existing_research_registry.csv` (every branch, verdict, binding constraint, and retest classification). This section narrates what the registry shows.

## 1.1 What Atlas is today

A weekly ETF tactical allocation system in four layers: Layer 1 alpha signals (momentum, trend, reversal, quality, breadth, dollar-strength, macro/VIX features, all 1-week lagged), Layer 2A with eight sleeves (dual momentum, CTA-style trend long-only, regime-conditioned composites, TAA, trend-quality, confirmation-aware momentum, structural defense), Layer 2B a causal 5-state regime engine (stressed_panic ~8%, recovery_fragile ~14%, recovery_confirmed ~4%, neutral_mixed ~44%, calm_trend ~27%), and Layer 3 HRP allocation with state multipliers, target-vol scaling, BIL overlay, and the Phase 5 fragility guardrail. Production: 7.13% CAGR, 0.948 Sharpe, −11.60% MaxDD, CVaR5 −2.49%, holdout Sharpe 2.179, SPY beta 0.24, average BIL 27.6%, weekly turnover 6.7%.

## 1.2 The research history in one paragraph each

**Allocator research (Phases 2A, Q–V, W–AA, RR–ZZ, JJJ):** every allocator family that exists was tried — ERC, HERC, MVO, Black–Litterman, max-diversification, inverse-vol variants, learned concentration gates, boosted sleeve-return allocators, bucket-trust and abstention meta-allocators, holdings blends (six consecutive sprints), explicit bucket architectures, budget-preserving overlays, decomposed-component rebudgeting, adaptive risk contribution. HRP won and kept winning. The repeated three-sprint failure pattern of meta-allocator work (Phases Q–S) is one of the cleanest lessons in the repo: **allocator sophistication cannot manufacture return that the opportunity set does not contain.**

**Signal research (R1–R4, B6–B8, OOO, QQQ, SSS, frontier phases):** a Renaissance-inspired signal factory validated decay profiles, macro signal families (only dollar-strength passed strict gates), VIX term structure, volume divergence, ETF pairs, breadth composites, state-conditional IC, trend quality, re-risking gates, leadership/crowding (failed as alpha, promoted as guardrail), decision labels, cross-asset lead-lag (failed at weekly horizon). The B7/B8 negative result established that deployment architecture, not signal discovery, had become the bottleneck — which led to the checkpoint wrapper and the stabilization framework.

**ML research (ML Phases 1–3, NNN, OOO1–6, PPP, kNN/k-means moonshot tracks, ml_lab):** every attempt at allocator-level or regime-level machine learning on ~1,000 weekly samples failed Phase D gates or matched hand-built rules. The Moonshot kNN analog engine is the definitive internal result: a well-built nonparametric learner with leakage controls finds *real* signal (beats all 50 shuffled-target nulls) and still only matches the hand-built R2A composite (rank IC 0.090 vs 0.092) while delivering a sixth of its portfolio value. **The features, not the model class, are exhausted.** Deep learning and RL were correctly never attempted at this sample size.

**Aggressive-return research (Phases 1–7 of the return-unlock arc, Track B, Track C, Frontier-2, Moonshot, Confirm1):** the system's own attempts to earn more. Track B: cash caps, offense boosts, and static growth blends raise return only by raising SPY beta (best: 9.05% CAGR at −29.3% MaxDD and 0.58 beta — worse risk-adjusted than production). Track C: six alpha sleeves, five failed long-only, one (canary breadth timing) passed standalone sanity but added nothing in blend. Frontier-2: four overlay families, two DROPs, two research-only; the down-only vol throttle was permanently closed by its own stop rule after failing rolling-origin twice. Moonshot: the α amplitude finding (production signal under-sized 3–6×), the PBI panic-but-improving state (real mechanism, wrapper-capped), and clean ML negatives. Confirm1: three locked candidates all CONFIRMED-FOR-HUMAN-REVIEW (α=0.16+PBI recommended), awaiting the owner's pin decision — outside this blueprint's scope.

**Options research (four iterations):** v1 bullish overlay REJECT (Sharpe 0.948→0.577), v2 options-specific entry engine REJECT (0.830), recovery-only convexity RESEARCH-ONLY (0.958 — the sole survivor, but only +0.008 over an equivalent ETF tilt), v3 refined recovery REJECT. **Every verdict rests on Black–Scholes proxy pricing with a realized-vol IV substitute** — flagged in every report as not production-grade. The options domain has, in a strict sense, never actually been tested.

**Macro research (FRED-MD classifier V1–V3, Steps 2/2B/2C):** the growth×inflation quadrant structure is real in development data (+1.41%/4w spread; the neutral_mixed sub-split shows slowdown +1.47% vs stress +0.24%) but holdout rank order inverted, and all weekly-overlay expressions were research-only. The internal conclusion — monthly macro information belongs at monthly capital-allocation frequency, not in weekly overlays — sets up Run 9.

## 1.3 Retest classifications (mandate §9)

Every branch in the registry carries one of the mandate's twelve classifications. The distribution:

- **Retest with broader universe (14 branches):** everything cross-sectional — momentum sleeves, residual momentum, reversal, ML rankers, latent factors, feature mining, triple-barrier, leadership. These did not fail; they were starved. 35 collinear ETFs ≈ 5 effective bets.
- **Retest long/short (3):** residual momentum, reversal, carry/value — signals that are long/short constructs by definition and were force-fitted into long tilts.
- **Retest after removing the defensive allocator (9):** R2A amplitude, PBI, re-risking, offense composites, overlay architecture, state thresholds — mechanisms whose measured effect is the wrapper-capped residue of their true effect.
- **Retest with better data (7):** PIT breadth (scaffold built, purchase pending), all options work (real chains), macro vintages, news/text.
- **Retest at different horizon (2):** cross-asset lead-lag (a daily effect tested weekly), credit/VIX signal families.
- **No retest justified (11):** meta-allocator trust family, holdings blends, bucket architectures, k-means states, VIX gate, canary gate, vol-managed offense (closed by stop rule), TAA SMA, index-effect-style ideas the system already handles.
- **Adopted/kept (remainder):** governance stack, validation layer, episode map, decay analysis — the transferable assets.

**Nothing Atlas ever attempted is silently dropped**; the registry is the auditable record.

---

# PART II — Redefinition from Zero

## 2.1 The Defensive Constraint Audit

**Full audit:** `atlas_offensive_defensive_constraint_audit.csv` — 18 constraints, each with location, purpose, suppression mechanism, evidence, removal risk, and retest plan. The five that matter most:

1. **Long-only, no shorting (the deepest constraint).** Half of every cross-sectional signal is discarded. Track C's residual momentum and reversal sleeves had real holdout IC and still failed, because a long-only top-5 of 35 ETFs is not a residual strategy — it is a beta portfolio with a tilt. Removal risk: borrow costs, squeezes, unlimited-loss mechanics. Retest: Run 5, easy-borrow large caps, beta- and sector-neutralized, with borrow-fee haircuts.

2. **The 35-ETF universe (the widest constraint).** Phase PPP's null (no latent sleeve) is a statement about ETF collinearity, not about markets. Gu–Kelly–Xiu-class ML gains, factor investing, stat arb, PEAD, insider signals — all require breadth that ETFs cannot provide. Removal: Norgate + Sharadar. This is the single highest-expected-value change in the entire blueprint.

3. **The permanent cash cushion (the most quantified constraint).** The Moonshot episode map is the internal smoking gun: in 76 early-recovery weeks, SPY compounded at +72.6% annualized while the pin held 53% BIL and earned 11.9%. The top four contiguous opportunity gaps in 21 years are all early recoveries (−23pp, −15pp, −12pp, −10pp vs the ideal bound). 67% of those weeks sit inside `stressed_panic`, where every overlay's modifier is frozen at 1.0 **by convention**. The PBI mechanism that addresses exactly this passed every null control and is capped at +0.003 Sharpe by the wrapper. This is the clearest documented case of the defensive mandate suppressing a validated return source.

4. **Sharpe-first gates with hard risk vetoes.** The Phase D gate set rejects every candidate that buys return with any risk (all of Track B) and passes candidates that buy Sharpe by *reducing* return (α=0.40: CAGR 7.13%→6.97%, PASS 8/8). The gates are excellent at what they were designed for — protecting a defensive product — and structurally incapable of promoting a return-seeking one. Part IX re-derives the gate set around return-first objectives; Part X keeps every anti-overfitting control intact.

5. **The 10bps flat cost model + 1.10× turnover gate.** Moonshot's α-curve stops at 0.48 because of the cost gate, not the signal ("governance, not the data, is the constraint" — the sprint's own words). A measured per-instrument cost model (SPY trades at ~1bp) plus strategy-earned turnover budgets replaces a blanket veto with a price.

Also audited: target-vol at 10% (realized 7.5%), fragility-guard SPY reduction, frozen-panic convention, conservative state thresholds, signal clipping, ensemble dilution, monthly-macro-as-weekly-overlay, proxy-only options pricing, no futures/FX/crypto, weekly-only cadence, HRP conviction dilution, and the burned holdout (an *evidence* constraint: Atlas Offensive seals a new one).

## 2.2 Candidate Identities (mandate §11, A–J)

Each identity assessed on return source, plausible profile, capacity, data/infra needs, solo feasibility, and Atlas compatibility. Summary verdicts:

**A. Aggressive Long-Only Compounder** — momentum/quality/trend on single stocks, concentrated top-k, tactical exposure, optional modest leverage. Return source: equity premium + cross-sectional alpha. Plausible profile: 10–15% CAGR at 15–25% MaxDD. Solo feasibility: **high** (simplest path off the ETF ceiling; no borrow, no margin complexity). Verdict: **the bridge identity — Runs 3–4, first new capital deployed here.**

**B. Long/Short Equity Alpha Engine** — residual ranking, factor/sector/beta neutralization, pairs. Return source: cross-sectional alpha proper. Profile: 5–10% on gross with low beta if it works; the hardest thing in the catalog to do well at retail (borrow, costs, crowding). Feasibility: **medium**. Verdict: **the alpha test-bed — Run 5/7; sized small until proven.**

**C. Multi-Strategy Systematic Platform** — independent sleeves: equity XS, trend, carry, options, event, short-horizon. Return source: diversification across genuinely different premia. Feasibility: **high as an end-state, impossible as a starting point.** Verdict: **the target identity — Run 44 assembles it from whatever survives.**

**D. Systematic Macro / Futures Platform** — micro-futures trend, curve carry, macro conditioning. Return source: trend premium + carry + macro timing. Profile: 5–12% standalone, crisis-convex, near-zero equity correlation. Feasibility: **high at $10–25k+ via micros** (verified — commission friction is the binding constraint below that). Verdict: **first genuinely new market — Run 8; also the natural home of the existing CTA sleeve done properly.**

**E. Statistical Arbitrage Platform** — clustered pairs, residual reversion. Evidence: classic distance pairs decayed publicly; internal reversal IC is the strongest signal evidence in the repo. Feasibility: **medium-low** (execution- and borrow-intensive). Verdict: **contingent — Run 7 only after Run 5 proves shorting economics.**

**F. Options and Volatility Platform** — defined-risk VRP, recovery convexity, dispersion (documented infeasible), tail-hedge-plus-aggressive-core. Return source: variance risk premium + convexity timing. Feasibility: **medium** ($100–200/month data; execution learnable). Verdict: **the largest untested domain — Runs 13–16; internal rejections carry no weight because they priced a fiction.**

**G. AI-Native Predictive System** — GBM ranking (the one ML class with strong replicated evidence), then sequence/attention/GNN/foundation-model benchmarks against it. Verdict: **not an identity — a capability inside identities A/B/C. Runs 22–31, gated on breadth existing first.** The internal lesson stands: models do not create information; data does.

**H. Short-Horizon Trading Platform** — overnight drift, daily reversal, swing. Evidence for overnight effects is moderate-strong and unexploited by construction (weekly cadence). Feasibility: **medium** (needs intraday infra, G06). Verdict: **Runs 17–18, opportunistic.**

**I. Core + Offensive Sleeves** — defensive Atlas as core, offensive engines around it, drawdown-aware capital allocation. Verdict: **the recommended deployment architecture** — it preserves the only production-grade asset while everything else is proven, and it gives the drawdown-engineering phase (Run 45) a natural anchor.

**J. New Hybrid** — the honest answer discovered in this exercise: **B-inside-I with D and F as satellites**, i.e., the multi-engine core-satellite platform described in the Executive Summary. It is not one of the nine textbook identities; it is the sequence A → D → F → B/E assembled under I's capital governance with C as the limit.

---

# PART III — Global Research Search: Method and Findings

**Method.** Two evidence streams: (1) the complete internal record — ~60 branches, 20+ full reports read, verdicts extracted (source ledger S01–S15); (2) targeted external verification — 28 logged web searches (Q01–Q28 in `atlas_offensive_search_query_ledger.csv`) prioritizing questions training-data knowledge cannot answer: post-2024 strategy health, data vendor pricing, model-family benchmark results, retail feasibility facts. Source priority followed the mandate: peer-reviewed > working papers > institutional research > vendor documentation > practitioner claims, with every material claim tagged by evidence class in the source ledger.

**Findings that shape the program (each verified this session):**

- **Trend following is healthy out-of-sample** (2020–2025 slice positive; short and very long horizons dominate mid horizons) — supports Run 8. [Q01]
- **Factor investing largely survives replication** (Jensen–Kelly–Pedersen: most factors replicate across 93 countries) — supports Run 6; post-publication haircuts of ⅓–½ are the planning assumption. [Q12]
- **VRP remains positive but tails remain lethal** (SVOL −33% in the 2025 tariff selloff; VIX-futures crowding at half pre-COVID levels) — defined-risk-only rule for Run 14. [Q02]
- **Overnight drift persists and is where momentum's alpha lives** (overnight 3-factor alpha 0.95% vs 0.11% intraday) — Run 17. [Q03]
- **ML ranking gains are real and breadth-dependent** (GKX and European replications: trees/nets beat OLS decisively on thousands of stocks) — Run 22, and the reason Run 3 precedes all ML. [Q04]
- **Time-series foundation models mostly fail to beat scratch baselines on equities** (2025 Diebold–Mariano evidence) — Run 29 is a benchmark, not a bet. [Q07]
- **Portfolio RL degrades OOS consistently; execution RL is the defensible scope** — Run 32 only. [Q09]
- **Classic pairs decayed; residual/cluster variants and bear-market alpha persist** — Run 7 design. [Q11]
- **PEAD is contested in large caps, alive in small caps per 2025 papers** — Run 12 targets small/mid. [Q15]
- **The index effect is disappearing** — de-prioritized (Tier 4 inside Run 11). [Q22]
- **Merger arb is having its best year since 2021 (~500bps over cash median spread)** — Run 11. [Q23]
- **Vol-managed portfolios often fail real-time OOS** — independently corroborates the internal Frontier-2 stop rule; the closed branch stays closed. [Q20]
- **Data costs are retail-tractable:** Norgate ~$110/mo (PIT constituents, survivorship-free), Sharadar ~$50/mo (25y PIT fundamentals), ORATS ~$100/mo (2007+ chains), ThetaData $40–160/mo, Polygon/Databento ~$125–199/mo intraday, micro futures at $5/point. The full offensive data stack is ≈ $300–500/month. [Q05, Q06, Q16, Q19]
- **Signature methods, OT, DFL are live 2024–25 research areas with credible but preliminary finance evidence** — Tier 3–4 runs with negative-control framing. [Q21, Q25]

What was **not** searched (disclosed in Part XIII): systematic conference-proceeding enumeration, paywalled journals, institutional research requiring licenses. The mandate's standard — auditable coverage, not omniscience — is met by the ledgers plus the gap register.

---

# PART IV — Strategy Catalog

**Full catalog:** `atlas_offensive_strategy_catalog.csv` — 40 strategy families, each with mechanism, markets, data, horizon, expression, turnover, capacity, evidence strength, crowding/decay/tail risk, Atlas prior test, how the offensive test differs, tier, and proposed run. Part XIV gives the full standardized entries for the Tier 1–2 families. The catalog covers every family the mandate enumerates (§17–§32); families with no viable path for this project (e.g., market making, sub-minute microstructure, single-name credit) appear with explicit infeasibility documentation rather than being omitted.

**Tier 1 (strong evidence, high practical value, early testing):** PIT stock breadth timing, PBI native re-risking, single-stock cross-sectional momentum (incl. residual variants), futures trend following, multi-strategy sleeve allocation, drawdown-engineering-last as a principle.

**Tier 2 (strong concept, higher implementation cost):** fundamental factor library (quality/value/BAB), factor momentum, GBM ranking, short-term reversal/stat-arb, PEAD/revisions, overnight effects, defined-risk VRP, recovery convexity on real chains, macro quadrant conditioning, cross-asset carry, Kelly sizing, concentrated top-k, execution optimization, HAR vol conditioning.

**Tier 3 (frontier):** LLM text signals, insider/congress screens, merger arb, FX carry/momentum/value, crypto sleeve, low-vol/BAB with leverage, defined-risk options leverage, tail-hedge-plus-aggressive-core, lead-lag networks, GEX dealer-positioning conditioners, decision-focused learning, analog retrieval v2.

**Tier 4 (moonshot transfer):** GNNs, signatures/OT/DRO, transfer entropy, network crowding, symbolic regression, TSFMs, RL beyond execution, control-barrier drawdown governors.

**Tier 5 (educational/negative-control):** TDA crash prediction, Ising/contagion indicators, Koopman modes, evolutionary search without governance (as the control condition), ETF-flow dislocation at retail speed.

**Tier 6 (currently infeasible, documented):** dispersion at scale, market making, sub-minute microstructure, single-name credit, offshore perps for US persons, institutional alt-data (credit-card/satellite/geolocation). Each carries a "what would make it feasible" note in the catalog or gap register.

---

# PART V — Classical Model Catalog

**Full catalog:** `atlas_offensive_model_catalog.csv` (50 model families with Atlas-fit verdicts). The organizing judgment, earned by Atlas the hard way and confirmed by the external record: **model capacity was never the constraint — sample geometry was.** On ~1,000 weekly market-level observations, a hand-built linear composite sits at the information ceiling (kNN matched it; ridge lost to it; GBM failed gates). On 500–2,000 stocks × 2,500+ days, the published evidence flips: trees and shallow nets beat linear models decisively and the gains are economic, not just statistical.

Standing rules for every run: (1) OLS/ridge and logistic baselines are mandatory in every experiment; (2) GARCH→HAR upgrade for all vol inputs; (3) statistical jump models and HMMs benchmark the regime engine (Run 2); (4) PCA residualization moves to the stock panel where it has factors to find; (5) Kalman filters for pairs hedge ratios; (6) quantile/distributional models serve sizing, not point prediction; (7) EVT calibrates stops; (8) every classical model's job is stated in the catalog — none is invoked for sophistication's sake.

---

# PART VI — Frontier AI and Deep Learning

**Catalog rows in** `atlas_offensive_model_catalog.csv`; runs 22–34 in the registry. The posture the evidence supports: **one workhorse, many benchmarks, no faith.**

- **The workhorse (Run 22):** gradient-boosted ranking on a 150+ feature library over the stock panel — the only ML family with strong, replicated, economically meaningful evidence (GKX lineage). Everything else must beat it to earn compute.
- **The ladder (Runs 24–27):** CNN → LSTM/GRU/S4/Mamba → PatchTST/iTransformer/cross-asset attention → GNNs, each a controlled benchmark against the GBM with identical features, purged CV, and seed-stability requirements. The GNN literature's baseline-sensitivity problem (Q14) is designed in: graphs must beat GBM-*with-graph-derived-features*, not a naive baseline.
- **Foundation models (Run 29):** benchmarked honestly; 2025 evidence says expect parity. A confirmed parity result closes the branch cheaply.
- **Representation learning (Run 28, 30):** conditional autoencoders and market-state embeddings feed the analog-retrieval engine — the one internal ML idea that found real structure and is waiting on richer features, not better models.
- **Generative models (Run 33):** stress-path generation only. Direct alpha training on synthetic data is a documented Tier 5 negative-control idea.
- **LLMs (Run 20, 34):** two distinct uses. As *feature extractors* on filings/transcripts/news with strict PIT timestamps and a priced-in null (enter at t+2; if the signal dies, it was never tradable). As *research agents* for hypothesis generation and code audit — with every generated hypothesis logged in the trial registry so agentic speed does not become an overfit factory.
- **RL (Run 32):** execution scheduling only, offline, against TWAP baselines. The published OOS failure record for portfolio RL (Q09) plus the internal sample-size arithmetic keep portfolio RL in Tier 4.
- **Decision-focused learning (Run 31):** genuine 2024–25 momentum in the literature; the known turnover-inflation pathology is a pre-registered check.

---

# PART VII — Mathematics and Science Beyond Finance

**Full catalog:** `atlas_offensive_math_transfer_catalog.csv` — 26 transfers, each with origin field, key idea, financial representation, executable experiment, failure modes, and novelty assessment. Highlights by expected value:

**Likely useful (Tier 3):** model-predictive control for multi-period, cost-aware rebalancing (established via Boyd's cvxportfolio lineage; Run 35); random-matrix covariance denoising for wide universes (Run 44); double-ML/invariant-prediction screens that ask of every signal "does it survive orthogonalization and regime environments?" — a direct attack on the decay problem (Run 40); anomaly-detection drift alarms from cybersecurity for live degradation monitoring (Run 47); optimal stopping for exits (Run 45).

**Credible moonshots (Tier 4):** path signatures as canonical path features (active 2024–25 finance literature; test = signature-augmented GBM vs hand features, Run 38); optimal transport for regime distance and DRO allocation (Run 38); transfer entropy for daily lead-lag discovery where correlation failed (Run 37); network centrality as a crowding gauge to replace ETF leadership (Run 39) — with the absorption-ratio lesson encoded: fragility throttles double-count stress on a defensive base, so these test only on aggressive bases; control-barrier functions as provable drawdown governors (Run 45).

**Negative-control class (Tier 5):** persistent homology crash prediction, Ising/epidemic contagion indicators, Koopman mode shifts, EMD trend extraction (endpoint leakage documented). These run, if at all, to establish what does not work — with nulls designed before results are seen.

Every transfer names its executable experiment; nothing appears as decoration.

---

# PART VIII — Data, Markets, and Infrastructure

## 8.1 Markets (mandate §55)

**Full assessment:** `atlas_offensive_market_catalog.csv` — 17 markets with data, liquidity, minimum capital, leverage/shorting access, costs, regulation, and fit. The expansion order the evidence supports:

1. **US single stocks** (core; unlimited capacity for solo scale; $0 commissions; the breadth precondition).
2. **Micro futures** — equity index, Treasuries, FX, commodities (embedded leverage and native shorting at $5/point granularity; 60/40 tax treatment; $10–25k practical minimum).
3. **Listed index/ETF options** (defined-risk structures; ORATS-grade data at retail prices).
4. **Crypto spot/regulated derivatives** (small sleeve; offshore perps documented infeasible for US persons).
5. **Satellites:** ADRs, CEF discounts, preferreds — niche mean-reversion and carry with capacity limits that suit retail.

Explicitly deferred with reasons: single-name credit (no retail execution), spot FX at leverage (financing asymmetry), prediction markets (capacity), international direct (tax/PFIC complexity before ADRs are exhausted).

## 8.2 Data architecture (mandate §56)

**Full classification:** `atlas_offensive_data_catalog.csv` — 20 datasets tagged free/low/medium/institutional. The purchase sequence: **Norgate (~$110/mo) → Sharadar fundamentals (~$50/mo) → ORATS (~$100/mo) → futures/intraday (~$125–200/mo as runs demand)**. Free tier already available and under-exploited: full EDGAR (Form 4, 13F, filings text), FRED/ALFRED vintages, FINRA short interest, exchange crypto APIs, CBOE indices. Institutional tier (IBES estimates, credit-card panels, satellite) is documented in the gap register with upgrade triggers, not assumed.

Non-negotiable data rules carried over from Atlas culture: survivorship-free always; PIT constituents for any breadth signal; as-reported fundamentals with filing-lag alignment; timestamp audits for any text/news source; delisting returns included; borrow-fee collection from day one of any short book.

## 8.3 Infrastructure roadmap (mandate §57)

**Essential (before Run 3):** local Python research stack (exists), Norgate/Sharadar ingestion, a panel feature store (Parquet + DuckDB is sufficient at this scale), the trial-registry database, and an experiment-tracking convention (extend the existing scoreboard).
**Essential (before Runs 13/17):** event-driven backtester with realistic fills — LEAN local is the leading candidate (open-source, options/futures native, live-trading path to IBKR); a custom vectorized engine remains acceptable for daily-frequency runs.
**Deferred luxuries:** GPU cluster (rent per-run), distributed backtesting, L2 storage, colocation (never, at this scale).
**Governance infrastructure is not optional:** the registry, pre-registration templates, holdout seal, and cost-model library are Run 0 deliverables.

---

# PART IX — High-Return Targets and Evaluation

## 9.1 Prediction targets (mandate §58)

Atlas has already demonstrated internally that exact-return prediction is a weak target (triple-barrier and decision-label phases). Run 23 is a dedicated **targets laboratory**: on identical features and models, compare raw/excess/residual forward return, cross-sectional rank, top-quintile membership, probability-of-exceeding-costs, triple-barrier outcomes, MFE/MAE, expected log growth, and meta-labels — scored by realized portfolio value per unit of overfitting risk. The catalog's standing hypothesis, from both internal evidence and the labeling literature: **rank and threshold targets beat point-return targets at weekly-monthly horizons; barrier targets matter most at trade level.**

## 9.2 Horizons (mandate §59)

Feasible and mapped: overnight, 1d, 2–5d, 1–2w, 1m, 1q, 6–12m — each tied in the catalog to the families that live there (reversal/overnight at the short end; momentum/factors/macro at the long end). Documented infeasible at current scale: tick/seconds/minutes.

## 9.3 Return-first evaluation (mandate §60)

Discovery-phase ranking metrics: **net CAGR, expected log growth, average trade expectancy, profit factor, capacity-adjusted return, residual alpha after factor regression.** Risk is reported alongside — vol, MaxDD, CVaR, skew, beta, leverage, turnover, concentration, tail dependence — but as *prices paid*, not vetoes, until Run 45. One Sharpe number never appears alone; every result table decomposes return into beta, factor exposure, leverage, short-vol/carry exposure, timing, selection, and sizing (mandate §63). The Track B lesson is codified: **a return improvement explained by beta is reported as beta, not as alpha.**

---

# PART X — Unbiased Research Governance

Atlas's existing stack (walk-forward-only labels, time-ordered splits, purged CV utilities, PSR/DSR proxies, PBO proxy, bootstrap, null controls, pre-registration, stop rules) carries over intact and is extended:

1. **New sealed holdout.** The 2024-04-19 holdout is burned (consulted across sprints; internal reports already treat it as descriptive). Atlas Offensive seals data from a declared 2026 date forward, untouched until final promotion decisions, plus mandatory paper-trading confirmation.
2. **Trial registry counts everything** — every strategy, parameter family, feature family, target, horizon, universe, model, seed sweep, and post-hoc modification, including agent-generated candidates (mandate §62). DSR/PBO computed per family, not per survivor.
3. **Pre-registration before any run**, in the Confirm1 mold: candidates, parameters, gates, and stop rules locked in a file before execution; post-hoc discoveries explicitly flagged and re-confirmed before belief.
4. **Cost realism per instrument:** measured spreads, borrow fees, financing, margin, futures rolls, options slippage at the spread — plus the retained cost-doubling stress.
5. **Null batteries as standard equipment:** shuffled targets, random placement, inverted signals, synthetic null strategies — the Moonshot template becomes the house style.
6. **Sensitivity axes:** parameters, universe, start date, regime, seeds — reported, never selected on.
7. **Alpha decomposition (mandate §63)** in every result table, and **§64 discipline:** raw unconstrained behavior evaluated first, constraints layered progressively with their return price tagged, and no candidate rejected solely because its standalone drawdown exceeds the old defensive portfolio's.

---

# PART XI — The Sequenced Run Program

**Full registry:** `atlas_offensive_future_run_registry.csv` (47 runs with the full §66 structure fields); dependency structure in `atlas_offensive_run_dependency_graph.md`; the first ten in `atlas_offensive_first_10_runs.md`; the complete sequence narrative in `atlas_offensive_complete_research_sequence.md`; the Run 1 prompt in `atlas_offensive_run_01_prompt.md`.

**Shape of the program:**

- **Foundation (R00–R01):** governance reset + the PIT breadth confirmation — cheap, fast, already-scaffolded.
- **Core alpha (R02–R08):** regime rebuild, stock universe, momentum, concentration, long/short, factors, futures trend. This is where the identity is decided by evidence.
- **Adjacent alpha (R09–R21):** macro conditioning, carry, events, earnings, short-horizon, alt-data, crypto.
- **Derivatives (R13–R16):** the options program on real data.
- **Frontier ML (R22–R34):** the GBM workhorse and its challenger ladder.
- **Moonshot mathematics (R35–R41):** transfers with executable experiments and negative-control framing.
- **Integration and risk (R42–R47):** sizing → leverage → multi-strategy allocation → generative stress → drawdown engineering → execution → paper-trading gate.

**Critical path:** R00 → R01 → R03 → R05 → R22 → R42 → R44 → R45 → R47. **Three tracks parallelize immediately after R00/R01:** futures/macro (R08+), options (R13+), and short-horizon (R17+) are independent of the equity track. Low-cost quick screens (R01, R19, R21, R29) are interleaved to keep discovery cheap; high-cost moonshots (R27, R32–R34) sit behind explicit advancement gates. Every run declares failure conditions and stop rules — the Frontier-2 precedent (a branch that closed itself permanently) is the model for how branches die.

---

# PART XII — Prioritization Without Omission

The six-tier system (defined in Part IV) is applied to every idea in every catalog; nothing is deleted. Scoring on the mandate's 19 axes is encoded qualitatively in the catalogs (evidence_strength, crowding/decay/tail columns, difficulty, cost, capacity, fit) rather than as false-precision 1–10 grids for all 100+ entries; the standardized entries in Part XIV carry fuller scoring for Tier 1–2. Uncertainty statements accompany every score-bearing claim; where evidence is contested (PEAD, LLM signals, vol targeting) the disagreement itself is documented in the catalog row and source ledger.

---

# PART XIII — Search Coverage Disclosure

**Databases/sources searched:** the complete Atlas repository (472 markdown files enumerated, 20+ full reports read — S01–S15); public web via 28 logged queries spanning arXiv, SSRN, journal-published summaries (JF/JFE/RFS/FAJ lineage), Quantpedia, Alpha Architect, institutional publications (Man, AQR-adjacent, BIS), vendor documentation (Norgate, Sharadar, ORATS, ThetaData, CBOE, Polygon, Databento, IBKR, QuantConnect), and practitioner sources (clearly labeled).
**Keyword families covered:** all 28 query rows in the ledger, mapped to taxonomy domains in `atlas_offensive_coverage_matrix.csv` (35 domains, each with depth rating).
**Time period:** foundational literature through July 2026.
**Counts:** ~180 external result links returned; ~60 sources retained in the ledger (S16–S38); the remainder rejected as duplicative, promotional, or low-quality. Internal: ~60 research branches registered; 0 skipped.
**Not searched / unavailable:** systematic NeurIPS/ICML/ICLR proceeding enumeration; paywalled full texts; OptionMetrics/IBES-grade institutional data documentation beyond public pages; private-firm methodology (unknowable — G04).
**Stopping criteria:** searches stopped when (a) each taxonomy domain had at least one current-evidence anchor, (b) marginal queries returned sources already in the ledger, and (c) the remaining unknowns were data-access questions answerable only by purchase (logged in the gap register). Fifteen open gaps are registered in `atlas_offensive_gap_register.csv` with closure conditions.

This is an honest single-deep-session coverage of a mandate that will consume many future sessions; each future run embeds its own literature phase, and the ledgers are designed to be appended, not rewritten.

---

# PART XIV — Standardized Entries (Tier 1–2, Full Detail)

Format per mandate §Part XIV. Compact-catalog entries for Tier 3–6 live in the CSVs with the same field logic.

## Entry 1 — PIT Stock Breadth Calm-State Timing

**Category:** Regime timing / data unlock. **Core idea:** stock-level breadth (% above 200d MA, A/D, highs-lows on PIT index constituents) distinguishes healthy broad bulls from narrow fragile ones; ETF-level breadth cannot. **Mechanism:** breadth measures participation — a structural property of rallies invisible at basket level. **Markets:** US equity allocation decisions. **Data:** Norgate PIT constituents + delisted prices. **Horizon:** 4w. **Expression:** offense scaling in calm/neutral states. **Long-only compatible.** **Leverage:** none. **Turnover:** low. **Capacity:** unlimited. **Cost sensitivity:** minimal. **Tail risk:** missed narrow rallies. **Failure regimes:** megacap-led bulls (2023-style) where narrowness persists profitably. **Academic evidence:** breadth/participation literature moderate. **Practitioner evidence:** ubiquitous use. **Atlas prior test:** Phase 5A-Free diagnostic, survivorship-biased: +0.517%/4w in calm_trend vs −0.457% for ETF breadth; scaffold `build_pit_stock_breadth_panel.py` ready. **Why retest:** the bias is the only open question; the pipeline exists. **Offensive difference:** none needed — this is the rare already-designed experiment. **Infrastructure:** existing. **Difficulty:** 2/10. **Cost:** ~$110/mo. **Novelty:** low. **Evidence strength:** internal-diagnostic strong. **Bias risks:** survivorship (addressed by purchase), calm-state definition drift. **Validation:** Phase D battery + new-holdout discipline. **Run:** R01. **Advance if:** calm-trend Sharpe +0.10 holdout. **Reject if:** PIT lift < half the biased diagnostic. **Sources:** S04, phase 5A reports.

## Entry 2 — Panic-But-Improving Native Re-Risking

**Category:** Regime timing. **Core idea:** inside deep-drawdown panic, three causal confirmations (credit improving, breadth 4w change > 0, VIX term structure in contango) identify improving panic; re-risk early instead of waiting for state exit. **Mechanism:** recovery begins while volatility statistics still scream panic; conventional regime engines are late by construction. **Markets:** broad equity allocation. **Data:** existing. **Horizon:** weekly decisions, 13w episode window. **Expression:** native Layer-2B sub-state driving offense budget (not a wrapper multiplier). **Leverage:** optional later. **Turnover:** low (9 episodes/21y). **Capacity:** unlimited. **Tail risk:** the 2008 failure mode — improving-then-collapsing panic. **Atlas prior test:** Moonshot M1 + Confirm1: beats 91% of random placements, inverted control hurts (−0.025), stressed-panic Sharpe *improves*, all three confirmation candidates passed the locked battery — but wrapper-capped at ~+0.003 Sharpe because panic holds ~15% offense. **Offensive difference:** uncap the offense base in confirmed-improving panic (e.g., 15% → 40–70%) with a hard per-episode stop-loss; this converts a +0.003 mechanism into the primary attack on the −12 to −23pp early-recovery gaps. **Difficulty:** 5/10. **Cost:** $0. **Novelty:** medium (contrarian re-risking literature exists; the state-machine expression is house-built). **Evidence:** internal strong. **Bias risks:** episode scarcity (9 events) — mitigate with per-episode attribution and international/futures out-of-sample replication. **Validation:** episode-blocked bootstrap, 2008-style stress replay, pre-registered amplitudes. **Run:** R02. **Advance if:** early-recovery capture +5pp/episode without new left tail. **Reject if:** any single episode erases > 2 years of contribution. **Sources:** S05, S06.

## Entry 3 — Single-Stock Cross-Sectional Momentum (with Residual Variants)

**Category:** Equity cross-section. **Core idea:** 6–12m winners minus losers, skip-month; residualized against factors to cut crash risk. **Mechanism:** underreaction + flow persistence. **Markets:** US large/mid caps (500–2,000 names). **Data:** Norgate survivorship-free. **Horizon:** 1–12m, monthly-ish rebalance. **Expression:** long top-k (identity A) and dollar-neutral deciles (identity B). **Shorting:** doubles the spread; long-only top-k is a legitimate first expression. **Turnover:** medium. **Capacity:** far beyond solo scale. **Cost sensitivity:** moderate. **Tail risk:** momentum crashes (2009-type reversal); crash controls (vol scaling, market-state gate) are themselves well-evidenced. **Academic evidence:** among the strongest in finance; survives the replication-crisis audit; international. **Atlas prior:** dual_momentum_topn on 35 ETFs — starved, not refuted. Track C residual xsmom failed *long-only on ETFs* — the wrong expression of a long/short construct. **Offensive difference:** breadth (×50 name count), residualization, both legs, crash overlay. **Difficulty:** 5/10. **Cost:** in Norgate. **Evidence:** strong. **Bias risks:** post-publication decay (plan for ⅓–½ haircut), crowding. **Validation:** decade-by-decade decomposition mandatory; post-2010-only significance required. **Run:** R03 (foundation) → R04/R05. **Advance if:** post-2010 net spread t > 2. **Reject if:** modern-sample spread ≤ costs. **Sources:** S16–S18, Q12.

## Entry 4 — Micro-Futures Trend Following

**Category:** Managed futures. **Core idea:** multi-speed time-series momentum across 10–15 micro futures (equity, bond, FX, metals, energy), vol-scaled, long/short. **Mechanism:** slow-moving capital, hedging flows, behavioral persistence — the premium with a century of evidence and positive 2020–25 OOS. **Data:** Norgate futures or Databento CME. **Horizon:** 2w–12m ensemble. **Expression:** native long/short with embedded leverage; 2× notional cap initially. **Turnover:** medium. **Capacity:** unlimited at solo scale. **Cost sensitivity:** commission friction at micro size — verified manageable at $10–25k+. **Tail risk:** trend whipsaw (2023-type); crisis convexity is the compensating asset. **Atlas prior:** `cta_trend_long_only` — a long-only ETF proxy that discards the short half and the leverage. **Offensive difference:** the real thing. **Difficulty:** 6/10 (rolls, margin ops). **Cost:** ~$100–200/mo data. **Evidence:** strong. **Bias risks:** replication-index tracking error; roll modeling. **Validation:** benchmark vs SG Trend and DBMF/KMLM; crisis-window analysis. **Run:** R08. **Advance if:** <0.3 correlation to equity book with positive expectancy. **Reject if:** micro-scale frictions consume the premium. **Sources:** S16, S19, S32, Q10.

## Entry 5 — Long/Short Equity Alpha Engine

**Category:** Equity market-neutral. **Core idea:** rank stocks on residual momentum/reversal/factor composites; hold beta≈0, sector-neutralized long/short book in easy-borrow large caps. **Mechanism:** cross-sectional mispricing net of common risk. **Data:** Norgate + Sharadar + live borrow fees. **Horizon:** 1–4w. **Turnover:** high — costs decide viability. **Capacity:** ample. **Tail risks:** squeezes, factor unwinds (Aug 2007-type), borrow recalls. **Academic evidence:** strong for the signals; thinner for retail net-of-cost viability — this is the honest uncertainty. **Atlas prior:** all relative-value sleeves failed long-only; the informational content (reversal composite holdout IC 0.407) is the strongest signal evidence in the repo. **Offensive difference:** actual shorting, actual neutralization, actual borrow costs. **Difficulty:** 7/10. **Evidence:** strong-for-signals / moderate-for-implementation. **Validation:** verified beta/sector exposures, borrow-fee haircuts, cost-doubling stress. **Run:** R05 → R07. **Advance if:** dollar-neutral net Sharpe > 0.8 at |beta| < 0.1. **Reject if:** costs/borrow consume the spread. **Sources:** S17, S18, S21, internal Track C.

## Entry 6 — Defined-Risk Volatility Risk Premium

**Category:** Options/vol. **Core idea:** harvest implied-minus-realized premium via put credit spreads / iron condors (capped loss), gated by Atlas's own regime engine — sell premium only outside stress/pre-stress states. **Mechanism:** insurance premium for crash risk; persistent because the risk is real. **Data:** ORATS 2007+. **Horizon:** 2w–2m. **Turnover:** medium. **Capacity:** high at retail size. **Tail risk:** the defining feature — 2018/2020/2025 episodes; defined-risk structures cap it structurally. **Academic/practitioner evidence:** strong average returns, catastrophic unmanaged tails, half-decrowded post-COVID. **Atlas prior:** none — all internal options work priced a Black–Scholes fiction. **Offensive difference:** real chains, regime gating (Atlas's genuine comparative advantage), defined-risk-only mandate. **Difficulty:** 7/10. **Cost:** ~$100–200/mo. **Evidence:** strong-with-tails. **Bias risks:** picking gate rules after seeing 2020; pre-register gates from the existing regime engine unchanged. **Validation:** episode stress replay incl. synthetic gap scenarios; premium-capture attribution vs luck. **Run:** R14 (after R13 foundation). **Advance if:** +2pp CAGR contribution at <5pp MaxDD contribution. **Reject if:** tail episodes erase multi-year premium even defined-risk. **Sources:** S22, Q02, Q06.

## Entry 7 — Recovery Convexity on Real Chains

**Category:** Options/vol. **Core idea:** the one internal options survivor — long calls/call spreads triggered by recovery/PBI signals, when trend acceleration + vol normalization create expected-move surplus over breakevens. **Atlas prior:** RESEARCH-ONLY at 0.958 vs 0.948 baseline on proxy pricing, only +0.008 over an equivalent ETF tilt — the tilt-control comparison is the right test and is retained. **Offensive difference:** real vol surfaces (entry IV actually observable), meaningful premium budget (vs 0.5% NAV), integration with the uncapped PBI state from R02 — the convexity thesis and the re-risking thesis are the same thesis at different moneyness. **Difficulty:** 6/10. **Run:** R15. **Advance if:** options beat the equivalent tilt by > 0.03 Sharpe on real data. **Reject if:** tilt equivalence confirmed — then simply re-risk with delta-one and save the theta. **Sources:** S10, S37.

## Entry 8 — Gradient-Boosted Cross-Sectional Ranking

**Category:** ML alpha. **Core idea:** LightGBM/XGBoost ranker on 150+ features (price, fundamental, breadth, macro-conditioning, text-derived) over the stock panel; top-k long (A-identity) or L/S (B-identity) portfolios. **Mechanism:** nonlinear interaction capture across a wide cross-section — the documented GKX gain. **Atlas prior:** GBM failed at allocator level on 1,000 samples; ml_lab correctly deferred. **Offensive difference:** millions of panel observations; ranking not regression; SHAP-audited features; the targets laboratory (R23) feeding it. **Difficulty:** 6/10. **Evidence:** strong (replicated). **Bias risks:** the classic ML overfitting complex — met with purged CV, embargo, DSR-per-family, seed stability, and the trial registry. **Run:** R22. **Advance if:** GBM beats the linear ranker by ≥50% IC with OOS stability. **Reject if:** linear parity (then linear wins — cheaper and more robust). **Sources:** S18, Q04.

## Entry 9 — Fractional Kelly Sizing + Dynamic Leverage (≤1.5×)

**Category:** Capital allocation. **Core idea:** growth-optimal sizing with posterior-shrunk return estimates; leverage applied to the highest-conviction diversified mix, capped at 1.5×, via portfolio margin or futures (never daily-reset levered ETFs — decay documented). **Mechanism:** compounding mathematics; the return lever that requires no new alpha. **Atlas prior:** none — Sharpe-first sizing throughout. **Tail risk:** estimation-error over-betting; leverage amplifies model error precisely when correlations converge. **Difficulty:** 5–6/10. **Evidence:** strong theory, well-documented failure modes. **Validation:** drawdown-constrained Kelly fractions, financing-cost realism, stress-window replay at leverage. **Runs:** R42–R43 (gated on ≥3 proven alpha engines and the owner's capital declaration, G08). **Advance if:** levered log growth > unlevered at MaxDD < 1.4× unlevered. **Reject if:** financing + estimation error erase the gain. **Sources:** S23, S36, Q16, Q27.

## Entry 10 — Multi-Strategy Capital Allocation (the End State)

**Category:** Architecture. **Core idea:** risk-budgeted allocation across genuinely different engines (equity XS, trend, options, carry, short-horizon, defensive core), correlation-aware, drawdown-aware, strategy-momentum-tilted. **Mechanism:** diversification across premia is the only free lunch that survives audits; the compound-growth gain from combining 0.6-Sharpe uncorrelated engines exceeds any single-engine improvement available. **Atlas prior:** HRP over eight flavors of long-only equity beta — diversification theater at the sleeve level. **Offensive difference:** the sleeves are actually different this time. **Difficulty:** 6/10. **Run:** R44 (needs ≥3 engines in paper). **Advance if:** book Sharpe > best single engine with return ≥ weighted average. **Reject if:** crisis correlation convergence erases the benefit (then the defensive core earns its keep). **Sources:** S17, internal Track A/B/C arc.

---

# PART XV — Final Recommendations: The 35 Questions

1. **What has Atlas tested?** ~60 branches across allocators, sleeves, signals, regimes, ML, overlays, options, macro — fully registered with verdicts in `atlas_offensive_existing_research_registry.csv`.
2. **Which conclusions were shaped by defensive constraints?** Every cross-sectional signal verdict (breadth-starved), every relative-value failure (long-only), the options rejections (proxy pricing + overlay framing), the R2A amplitude (predeclared conservatism), PBI's tiny measured effect (frozen-panic convention), and all of Track B's "higher return = worse" findings (beta was the only available lever).
3. **Which rejected ideas deserve clean offensive retests?** Residual momentum, short-term reversal, carry/value, ML ranking, latent factors, triple-barrier targets, lead-lag (at daily horizon), options (on real data), leadership/crowding (on stock data), macro quadrants (on vintages at monthly cadence).
4. **Which should remain rejected?** Meta-allocator/trust family, holdings blends, bucket architectures, learned k-means states, VIX/canary overlay gates, vol-managed offense (self-closed by stop rule), post-hoc scaling without exact wrappers.
5. **What identities could Atlas Offensive take?** All ten of Part II.2; the recommendation is the staged multi-engine core-satellite platform (J = B-inside-I with D and F satellites, C as the limit).
6. **Which markets should be added?** US single stocks first; micro futures second; listed options third; small crypto sleeve fourth.
7. **Which instruments?** Common stocks, micro futures (ES/NQ/Treasury/FX/metals/energy), defined-risk option structures, VIX futures (carefully), BTC/ETH via regulated venues.
8. **Should individual equities replace or supplement ETFs?** Supplement then largely replace as the alpha universe; ETFs remain as macro-sleeve building blocks and the defensive core.
9. **Should futures be used?** Yes — the natural home of trend/carry/macro and the cheapest honest leverage. Capital gate: ≥ $10–25k allocated (G08).
10. **Should options become a primary engine?** They should be *tested* as one (Runs 13–16). The internal rejections are void — they priced a fiction. No commitment until real-chain results exist.
11. **Should short selling be introduced?** Yes, in stages: easy-borrow large caps, beta/sector-neutral, borrow-cost-haircut, Run 5. The signal evidence demands it; the economics must prove it.
12. **Should leverage be introduced?** Modest (≤1.5×), late (R43), only on a diversified proven book, never via daily-reset products.
13. **Strongest-evidence return sources?** Equity risk premium held more fully; futures trend; cross-sectional momentum/factors on stocks; VRP (defined-risk); the internal PBI/breadth mechanisms.
14. **Highest plausible-upside sources?** Early-recovery capture (documented −12 to −23pp episode gaps); GBM ranking on breadth; options convexity timed by the regime engine; multi-engine compounding.
15. **Best suited to the user's capital/infrastructure?** Runs 1–4 (breadth, PBI, stock momentum, concentrated long-only): free-to-cheap, no margin, existing skills.
16. **Which require institutional access?** Dispersion at scale, sub-minute microstructure, market making, single-name credit, credit-card/satellite data, IBES-grade estimates — all Tier 6, documented.
17. **Which AI/ML methods are genuinely promising?** Gradient-boosted ranking (strong evidence); meta-labeling/target engineering; LLM feature extraction with PIT discipline; analog retrieval on enriched features; decision-focused learning (watch turnover).
18. **Which deep-learning methods are likely unnecessary?** TSFMs for return forecasting (2025 evidence: parity), GNNs beyond graph-feature baselines, portfolio RL, generic sequence models below millions of observations.
19. **Which frontier methods deserve moonshots?** Signatures, optimal transport/DRO, transfer entropy lead-lag, invariant-prediction screens, control-barrier drawdown governors, execution RL.
20. **Which outside mathematics offers credible transfer?** MPC rebalancing, RMT covariance denoising, double-ML/ICP causal screens, optimal stopping, drift-detection monitoring — the low-glamour, high-probability set.
21. **Highest-expected-value data investments?** Norgate (~$110/mo) → Sharadar (~$50/mo) → ORATS (~$100/mo) → futures/intraday (as runs demand). Total ≈ $300–500/mo fully built.
22. **What infrastructure first?** Trial registry + new holdout seal + per-instrument cost models (R00); panel feature store; event-driven backtester (LEAN local candidate) before options/intraday runs.
23. **First ten runs?** R00–R09 as specified in `atlas_offensive_first_10_runs.md` (governance, breadth, PBI, universe, concentration, long/short, factors, stat-arb prep, futures, macro).
24. **Complete long-term sequence?** The 47-run program in the registry with the dependency graph.
25. **Which runs parallelize?** Equity, futures/macro, options, and short-horizon tracks are mutually independent after R00/R01; within-track dependencies are graphed.
26. **Main self-deception risks?** Survivorship in new universes; borrow/cost optimism in L/S; post-hoc amplitude selection (the α lesson); burned-holdout reuse; agentic overfit factories; episode-count illusions (PBI has 9 events); regime-shift narratives excusing failures.
27. **How to record trials?** The R00 registry: every variant, every family, every seed, every agent-generated candidate; DSR/PBO per family.
28. **How to protect the holdout?** Seal 2026+ data; consult only at final gates; paper-trading as the true holdout; the old holdout demoted to descriptive.
29. **How to distinguish alpha from leverage/beta?** Mandatory decomposition table in every result (beta, factors, leverage, short-vol/carry, timing, selection, sizing) — §63 discipline.
30. **How to delay drawdown engineering?** Structurally: it is Run 45 of 47, gated behind proven alpha, with a priced give-up budget (≤20% of CAGR) instead of standing vetoes.
31. **Most promising overall direction today?** The staged multi-engine platform anchored on stock-universe breadth.
32. **Most promising realistic direction?** Runs 1–4: PIT breadth + PBI native + stock momentum + concentrated long-only — all cheap, fast, and standing on validated internal diagnostics.
33. **Highest-upside moonshot?** Options as a primary engine timed by the regime machinery (Runs 13–15) — the largest domain where Atlas has genuine infrastructure advantage and zero valid evidence either way.
34. **What should not be pursued?** Sub-minute microstructure, market making, dispersion at scale, offshore perps, portfolio RL, further allocator redesigns on the old universe, any un-registered discovery loop.
35. **The exact Run 1 prompt?** `atlas_offensive_run_01_prompt.md`.

---

# PART XVI — Deliverables Index

All in `docs/research/atlas_offensive/`:

| # | File | Content |
|---|---|---|
| 1 | atlas_offensive_exhaustive_discovery_blueprint.pdf | This document, rendered |
| 2 | atlas_offensive_exhaustive_discovery_blueprint.md | This document (editable source) |
| 3 | atlas_offensive_existing_research_registry.csv | ~60 historical branches with verdicts and retest classes |
| 4 | atlas_offensive_defensive_constraint_audit.csv | 18 constraints with suppression mechanisms |
| 5 | atlas_offensive_strategy_catalog.csv | 40 strategy families, tiered |
| 6 | atlas_offensive_model_catalog.csv | 50 model families with Atlas-fit verdicts |
| 7 | atlas_offensive_market_catalog.csv | 17 markets assessed |
| 8 | atlas_offensive_data_catalog.csv | 20 datasets with costs and PIT quality |
| 9 | atlas_offensive_math_transfer_catalog.csv | 26 cross-field transfers with experiments |
| 10 | atlas_offensive_source_ledger.csv | 38 sources with quality/evidence class |
| 11 | atlas_offensive_search_query_ledger.csv | 28 external + 3 internal logged searches |
| 12 | atlas_offensive_coverage_matrix.csv | 35 taxonomy domains × coverage depth |
| 13 | atlas_offensive_gap_register.csv | 15 open gaps with closure conditions |
| 14 | atlas_offensive_future_run_registry.csv | 47 runs, full §66 structure |
| 15 | atlas_offensive_run_dependency_graph.md | Edge list + Mermaid + critical path |
| 16 | atlas_offensive_first_10_runs.md | Detailed first ten runs |
| 17 | atlas_offensive_complete_research_sequence.md | Narrative long-term sequence |
| 18 | atlas_offensive_run_01_prompt.md | The locked Run 1 prompt |

---

# Appendix A — Glossary

**Alpha decomposition** — attribution of returns to beta, factor exposures, leverage, carry/short-vol, timing, selection, sizing. **BIL** — 1–3 month T-bill ETF; Atlas's cash proxy. **DSR** — Deflated Sharpe Ratio (multiple-testing-corrected). **DFL/SPO** — decision-focused learning / smart predict-then-optimize. **GGG1** — the production base allocation logic. **HRP** — hierarchical risk parity. **IC** — information coefficient (signal-forward-return rank correlation). **MFE/MAE** — maximum favorable/adverse excursion of a trade. **PBI** — panic-but-improving sub-state (Moonshot finding). **PBO** — probability of backtest overfitting. **PEAD** — post-earnings-announcement drift. **Phase D gates** — Atlas's 8-gate promotion battery. **PIT** — point-in-time (as-known-then) data. **PSR** — probabilistic Sharpe ratio. **R2A** — deployment-state-quality signal promoted in Frontier Phase 1. **SJM** — statistical jump model (transition-penalized regimes). **TSFM** — time-series foundation model. **VRP** — volatility risk premium. **XS/TS momentum** — cross-sectional / time-series momentum.

# Appendix B — Required Tables Index (mandate Part XIII)

1 Historical inventory → registry CSV. 2 Constraint audit → constraint CSV. 3 Strategy taxonomy → strategy CSV + Part IV tiers. 4 Market taxonomy → market CSV. 5 Data taxonomy → data CSV. 6 Classical models → model CSV (statistical rows). 7 AI/ML models → model CSV (ml/dl rows). 8 Math transfers → math CSV. 9 Institutional evidence → source ledger (practitioner rows) + Part III. 10 Paper evidence → source ledger (academic rows). 11 Dataset cost/feasibility → data CSV. 12 Infrastructure → Part VIII.3. 13 Return-source decomposition → Part IX.3 protocol. 14–17 Strategy×horizon/market/data/model → encoded as columns of the strategy CSV. 18 Evidence×novelty → strategy + math CSVs (columns). 19–20 Potential×feasibility, difficulty×EV → tier system + difficulty/EV columns. 21 Run dependency graph → dependency file. 22–23 Timeline/parallel map → Part XI + sequence doc. 24 Prioritization → Part XII. 25 Moonshots → math CSV Tier 4–5 rows. 26 Rejected/infeasible → registry (no-retest rows) + Tier 6 entries. 27 Coverage → coverage CSV. 28 Gaps → gap register.

---

*Prepared by Fable 5 under the Atlas Offensive master mandate, 2026-07-21. Discovery only: no production code, weights, pins, or promotions were touched. The production pin remains `improved_frontier_phase5_fragility_guard`.*
