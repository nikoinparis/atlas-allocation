# Layer 1 — AI Reasoning (Research Operating Layer)

## Why no new Layer 1 dependency is being added

This project is a systematic ETF portfolio research stack. It is not a live
trading bot. There is no execution venue, no broker integration, no
autonomous order flow, and no public-prediction-market settlement. Every
strategy proposal is a **backtested research candidate** that must clear
the project's 8-gate Phase D production rule on out-of-sample data before
any pin status can change.

That makes the purpose of an LLM in this repo categorically different from
a live-bot stack. The repos referenced for Layer 1 (Qwen3-Coder, Claude
Squad, G0DM0D3) are designed for autonomous code generation, multi-agent
swarms, and uncensored model experimentation. None of those use cases are
needed here, and adopting them would import dependency surface, security
surface, and audit complexity that none of this project's existing
research outputs require.

## How LLMs ARE used in this repo (safely)

LLMs (Claude Code / Codex / similar) are used as **research and coding
assistants only** for tasks that humans verify before acceptance:

- writing the deterministic backtest, allocator, regime-engine, and
  reporting scripts that live under `scripts/`,
- generating phase-by-phase research narratives in
  `docs/research/2026-04-*_*.md`,
- summarizing diagnostic CSVs and pairwise validation tables,
- auditing earlier code for lookahead bias, walk-forward errors, or
  cost-handling mistakes,
- producing the markdown templates used by the Research Committee layer
  (Layer 2) so that human reviewers have a structured surface to fill in.

In every case the LLM produces text or code; a human (or a deterministic
script with explicit pass/fail gates) decides whether that output enters
the repo, and a human decides whether any candidate strategy is promoted
to production or shadow. **The LLM is never the final approver.**

## What LLMs are NOT used for in this repo

- live or simulated order execution,
- autonomous portfolio-weight changes,
- autonomous promotion of a candidate to production or shadow status,
- auto-tuning of allocator hyperparameters,
- discretionary judgement that bypasses the 8-gate Phase D rule,
- on-chain interaction, wallet inspection, or copy-trading.

These restrictions are deliberate and structural, not a temporary policy.
The project rule is that **strategy approval must come from**:

- backtests with realistic transaction costs (5bp half-spread default),
- out-of-sample validation (held-out 156-week tail and rolling-origin),
- max drawdown caps and CVaR caps (Phase D gates),
- state-by-state performance (regime engine state buckets),
- benchmark comparison against the 13-member fixed comparator set,
- and human review of the resulting reports.

## Practical rules of use for Claude Code / Codex inside this repo

1. **Do not modify production strategy logic** unless the user explicitly
   asks for that change. Production logic is the
   `improved_phase2b_regime_confidence_boost` pin; shadow is
   `improved_phase2b_combo_abc`.
2. **Do not auto-promote.** No script in this repo should write directly
   to a "production pin" file or change `CLAUDE.md` to promote a
   candidate. Promotion is a human action.
3. **Causal walk-forward only.** Every new feature, signal, or state must
   use only past information. Lookahead-bias regressions are the single
   most common silent failure mode in quant research code.
4. **Net returns, not gross.** Every backtest comparison must use
   transaction-cost-adjusted net returns at the half-spread already used
   by the rest of the project (`TURNOVER_HALFSPREAD = 0.0005 * 0.5`).
5. **Same window, same costs, same metrics.** When comparing a candidate
   to production, both must run on the identical date range with the
   identical cost convention and identical metric definitions.
6. **State-engine work stays additive.** When refining Layer 2B (e.g.
   Phase CC), the original `market_state_history.csv` must remain the
   primary state input; refinements must be saved as new files and
   consumed downstream as additive overlays, not replacements, until a
   downstream allocator rerun confirms they help.
7. **No silent infrastructure dependencies.** No new dependency is added
   without explicit justification in the task description and a
   compatible license. External optimizer libraries (skfolio, riskfolio,
   pypfopt, vectorbt) are not currently installed; their algorithmic
   ideas are adapted in lightweight internal implementations under
   `scripts/` rather than imported as opaque dependencies.

## Bottom line

Layer 1 in this project is the human researcher plus the LLM acting as
typing assistant, code reviewer, and report drafter. There is no
autonomous decision-making layer to add. Every other Layer in this
operating stack (2 through 6) is implemented as an offline,
deterministic, audit-only Python script that produces markdown reports
and CSVs for human review.
