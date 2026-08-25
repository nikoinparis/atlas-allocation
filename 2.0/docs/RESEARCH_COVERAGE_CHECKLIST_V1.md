# Quant-Idea Research Coverage Checklist V1

As of 2026-08-23, this is the master audit map for every idea in the feasibility discussion. The machine-readable authority is `config/research_coverage_registry_v1.json`. A checked research item means that it has been implemented, falsified, or explicitly blocked with a named dependency. It does **not** mean the idea works or is approved for real money.

## Definition of done

- [x] Every discussed idea has a stable id, explicit hypothesis, current evidence, prerequisites, pass/fail/block gates, and intended runner/results.
- [x] Common quant-firm controls are mandatory: pre-registration, point-in-time data, causal execution, chronological splits, multiple-testing correction, controls, robustness, determinism, and an untouched forward gate.
- [x] Failed and blocked ideas remain visible. They cannot be removed from the trial count or silently renamed and retried.
- [x] Recursive generation may learn only from development and inner-validation evidence. The final OOS gate is terminal for that trial family.
- [x] ICIR is the primary metric only for genuine cross-sectional forecasts. Intraday/single-series strategies must use a predeclared net strategy metric instead of manufacturing an ICIR.
- [x] Passing retrospective research starts an immutable paper shadow; it does not enable trading. Production requires at least 52 untouched weekly observations plus explicit approval.

## Coverage register

| Done | ID | Idea | Current disposition | Controlling runner / result |
|---|---|---|---|---|
| [x] | `overnight_return_attribution` | Returns while the market is closed | Implemented in current challenger program; attribution is not automatically a tradable edge | `scripts/run_quant_idea_challengers_v1.py` / `evidence/quant_idea_challengers_v1/result.json` |
| [x] | `scrapling` | Scrapling | Conditional acquisition adapter only; source-by-source permission remains mandatory | `third_party_evaluation/runner.py` / `evidence/third_party_tool_evaluation_v1/report.json` |
| [x] | `smr_nuscale` | SMR/NuScale | Current SMR history acquired, but strategy inference is blocked by short history and missing historical theme membership | broad SEC acquisition / this registry |
| [x] | `stat_arb_pairs_us` | US statistical arbitrage/pairs | Properly implemented and economically rejected in Batch 21 | `scripts/run_etf_pairs_batch_21.py` / `evidence/etf_pairs_batch_21/result.json` |
| [x] | `stat_arb_pairs_indonesia` | Indonesia statistical arbitrage/pairs | Data/execution blocked; US accounting logic is reusable, US economics are not | Indonesia survival evidence plus pair runner |
| [x] | `always_wins_mispricing_claim` | “Always wins” pricing strategy | Rejected as a possible guarantee; replace with probabilistic falsification | this registry |
| [x] | `first_5m_ema_atr` | First five-minute bar vs 12 EMA with ATR trailing stop | Semantics predeclared; real test blocked by point-in-time intraday/NBBO data; synthetic contract tests only | challenger result |
| [x] | `kronos` | Kronos | Pinned CPU regression inference and feature boundary pass; incremental OOS alpha remains unproven | tool evaluation and `kronos_inference_smoke.json` |
| [x] | `derivatives_risk_and_expression` | Derivatives | Future hedge/expression layer; blocked by chain, contract, margin, and assignment data | this registry |
| [x] | `price_options_disagreement` | Price versus options-implied “bets” | Put-call-parity feature predeclared; real test blocked by options history; proxy evidence cannot validate options claim | challenger result |
| [x] | `kelly_criterion` | Kelly sizing | Fractional, estimation-aware diagnostic only; portfolio caps always dominate | challenger result |
| [x] | `everything_claude_code` | Everything Claude Code | Engineering workflow reference only; no runtime or alpha dependency | tool evaluation |
| [x] | `ranked_asset_allocation_model` | Ranked Asset Allocation Model | Current allocation challenger; exact paper identity/formula controls whether result is a replication or proxy | challenger result |
| [x] | `recursive_icir_oos_loop` | Recursive ICIR/OOS research loop | Implemented; first real three-trial family rejected in development without opening its lockbox | `scripts/run_recursive_overnight_v1.py` / `evidence/recursive_overnight_v1/result.json` |
| [x] | `politician_copying` | Copy politicians | Rules predeclared but real test blocked without complete timestamped all-person disclosures; never trade before filing | challenger result |
| [x] | `influencer_copying` | Copy influencers | Blocked without a complete timestamped archive including deleted/failed calls | this registry |
| [x] | `openbb` | OpenBB | Data connector candidate; API convenience does not confer provider entitlement | tool evaluation |
| [x] | `nautilus_trader` | NautilusTrader | Execution sandbox candidate; must reconcile against platform-owned accounting | tool evaluation |
| [x] | `monte_carlo_and_robustness` | Monte Carlo and proof of survival | Implemented risk falsification; Batch 28 passed its risk gate but cannot prove future profits | `scripts/run_monte_carlo_risk_batch_28.py` / Batch 28 evidence |
| [x] | `das_replay` | DAS Replay | Manual commercial evaluation blocked by account/license/export | tool evaluation |
| [x] | `trading_systems_repository` | Ambiguous Trading Systems repo | Blocked until exact GitHub URL/owner is supplied | tool evaluation |

## Existing evidence that already answers part of the discussion

### Pair trading was not a dead end caused by missing basic rigor

The saved US ETF test used causal quarterly Engle-Granger formation, FDR selection, disjoint pairs, next-period realization, full traded-notional turnover, borrow costs, relationship-break exits, negative controls, serial bootstrap, and an 80/20 portfolio test. At primary costs it returned -1.52% annually, Sharpe -0.751, and a -30.38% drawdown. The blend Sharpe was 0.722 versus 0.769 for the core, and the annual-return bootstrap lower bound was -2.22%. This specific implementation is rejected. A future retry needs materially new ex ante economics or qualified data; changing thresholds after seeing failure is not a new idea.

### Monte Carlo is a rejection tool, not a certificate

Batch 28 already runs Gaussian, IID empirical, 13-week block, mean-haircut, and forced-crash paths with rolling calibration. Its predeclared risk-validation gate passed, while its claimed “best-fit” forecasting edge failed. This is useful: the risk model survived its test, but the evidence did not turn simulation into alpha or approve live trading.

### IC evidence exists, but the recursive boundary matters

Batch 30 computed chronological rank IC for six source-preselected ETF factors and qualified two under its familywise bootstrap and control gates. It explicitly remained a retrospective factor diagnostic. The new recursive loop must preserve that distinction: development/inner validation can drive iteration; the final OOS result cannot be fed back into another generation.

## Required artifact map

### Quant challengers

- Program: `config/quant_idea_challengers_v1.json`
- Code: `src/systematic_trader/idea_challengers.py`, `src/systematic_trader/research_statistics.py`
- Runner: `scripts/run_quant_idea_challengers_v1.py`
- Tests: `tests/test_idea_challengers.py`, `tests/test_research_statistics.py`
- Results: `evidence/quant_idea_challengers_v1/result.json`, `scoreboard.csv`, `report.md`, `checklist.json`, `run_log.json`

### Recursive research loop

- Program: `config/recursive_quant_research_protocol_v1.json`
- Engine: `src/systematic_trader/recursive_research.py`
- Tests: `tests/test_recursive_research.py`
- Results: `evidence/recursive_overnight_v1/result.json` and its append-only, hash-chained `trial_ledger.jsonl`. The first bounded family tested all nights, after-negative-day nights, and after-positive-day nights at a frozen 10 bps cost; all failed development, so the 2021+ lockbox remained unopened.
- Terminal statuses: `rejected_in_development`, `failed_locked_test`, and `promoted_research_candidate`. Promotion remains research-only and is not live authorization.
- Non-negotiable: the final OOS partition is read once for a terminal gate and never becomes generator feedback.

### Third-party tool evaluations

- Manifest and runner: `third_party_evaluation/manifest.json`, `third_party_evaluation/runner.py`
- Kronos boundary: `third_party_evaluation/adapters/kronos_feature_contract.py`
- Tests: `tests/test_third_party_evaluation.py`
- Results: `evidence/third_party_tool_evaluation_v1/report.json`, `report.md`, `kronos_contract_smoke.json`, and saved raw observations

## What remains legitimately blocked

- Indonesian pairs need historic shortability/borrow rules, inactive-security coverage, local costs/taxes, suspensions/price limits, and defensible point-in-time constituents.
- A real options-disagreement strategy needs point-in-time chains, quotes, open interest, contract metadata, and an options-specific execution ledger. A price/volatility proxy is only a plumbing test.
- Derivative execution needs chain, expiry, assignment/exercise, margin, roll, and stressed Greek/P&L reconciliation.
- Influencer copying needs a complete lawful archive that preserves deleted and losing calls and supplies unambiguous post/fill timestamps.
- DAS Replay needs an account/license and reproducible order/fill export.
- “Trading Systems” needs the exact GitHub URL. Repository names are not unique identifiers.

Those rows are complete as blocked investigations. They become runnable only when the named dependency is supplied; they must never be marked failed merely because the needed evidence does not exist.
