# Portfolio Optimizer — Claude Code Project Instructions

## Source of Truth

Repo files are the source of truth. Do not invent phases, artifacts, metrics, signal names, sleeve names, or strategy state that are not present in the codebase or explicitly stated in this file.

---

## Session Startup Checklist

Before any implementation work, verify:
1. `pwd` — confirm you are in the correct working directory
2. `git status` — check for uncommitted changes
3. `git branch` — confirm the active branch
4. `git worktree list` — confirm worktree state

Stop and report if any prerequisite files or artifacts referenced in the task are missing. Do not proceed by assuming or recreating them.

---

## Project Structure

- Layer 1 = alpha signals
- Layer 2 = strategy logic / sleeves
- Layer 2B = causal regime engine
- Layer 3 = portfolio construction
- Dashboard = research explainer + comparison + diagnostics

## Goals

- Robust, interpretable, out-of-sample ETF portfolio
- Avoid overfitting and brute-force search
- Improve return without carelessly worsening Sharpe, drawdown, CVaR, or turnover

---

## Research Rules

- Prefer simple causal logic over black-box ML
- No hindsight regime labels
- Use causal lagged features only — no look-ahead
- No random train/test splits for time-series research; use time-ordered splits only
- Test incremental contribution, not just standalone signal quality
- Keep only changes that help out of sample alone or in combination
- Prioritize state-transition quality, re-risking speed, and reducing unnecessary BIL/cash drag

---

## Strategy Pins

**Production pin (official / rollback):**
- `improved_phase2b_regime_confidence_boost`

**Production candidate (pending human deployment review):**
- `improved_phaseggg_confirmed_only_robust_offense`

**Shadow / research runner-up:**
- `improved_phase2b_combo_abc`

### Dual-Track Rule

- `improved_phase2b_regime_confidence_boost` remains the single live production default until a human deployment review explicitly changes the pin.
- `improved_phaseggg_confirmed_only_robust_offense` is the Phase III production candidate pending human review; old production pin is preserved as rollback.
- `improved_phase2b_combo_abc` is a tracked research runner-up. It appears in the dashboard as an alternate comparison only — never as the headline production candidate.
- Future sprints must report incremental contribution versus **both** tracks (production + shadow) before promoting anything new.

### Pin Governance

- **Do not change production pins unless explicitly asked.**
- **Do not promote automatically.**
- **Do not force wins** — if a candidate does not clearly beat both tracks out of sample, classify it accurately.

---

## Phase / Research History

| Phase | Status | Notes |
|-------|--------|-------|
| OOO6  | Shadow candidate only | Was never promoted to production or production candidate |
| PPP   | Null result | Found no new latent sleeve |
| QQQ   | Direction set | Pointed to regime-sequence modeling |
| SSS2  | Signal audit | Cleared `calm_old_low_stress_signal`, `stress_new_state_signal`, and `qqq_efa_spy_trend_after_calm_or_recovery_signal` for SSS3 |

---

## Dashboard Rules

- Homepage must be inspectable immediately on first load
- No key content hidden behind tabs, accordions, or loading states
- Visible summaries for: baseline vs improved, current state, allocations, layers 1–3, diagnostics, benchmarks, holdings, and sleeve mix
- Use compact dashboard bundle files
- **Do not regenerate or commit `public/dashboard-data.json`** — use the bundle files instead

---

## Git / File Rules

- Never commit files over GitHub's 100 MB limit
- Do not regenerate or commit `public/dashboard-data.json`
- Stage specific files by name — do not use `git add -A` or `git add .` blindly

---

## Task Reporting

For every task, report:
- Commands executed
- Files changed
- Outputs / metrics
- Whether the change helped standalone
- Whether it helped in combination
- Final verdict: **Promote / Conditional / Research-only / Drop**
- Warnings or anomalies
- Git status after work is complete
