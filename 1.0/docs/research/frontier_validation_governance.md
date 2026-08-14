# Frontier Validation Governance

This document is the research constitution for frontier deployment work. Its job is to prevent the next phase from becoming backtest theater.

## Purpose

Frontier research starts from the Fama/EMH prior: most apparent edges are false, already competed away, too small after costs, or artifacts of repeated testing. A candidate becomes evidence only after it survives exact-plumbing reproduction, out-of-sample checks, state-conditional review, cost and turnover analysis, and statistical validation.

## Candidate Classifications

| Classification | Meaning |
|---|---|
| Promote | Meets all gates, improves the exact stabilized benchmark, has a clear implementation path, and does not rely on hidden beta, cash tricks, or unlogged selection. |
| Keep as Shadow | Strong enough to monitor beside production, but missing one or more promotion gates. |
| Research-only | Useful evidence or a plausible branch, but not deployable. |
| Diagnostic-only | Helps explain the system but should not affect allocations. |
| Drop | Failed clearly enough that repeating the branch requires a new hypothesis or new data. |

## Required Evidence Before Promotion

Every promotion candidate must document:

- Exact stabilized wrapper baseline used.
- Safe checkpoint used.
- Full-period metrics.
- Holdout metrics.
- Rolling-origin validation.
- Block bootstrap or equivalent resampling support.
- PSR/DSR proxy or stronger statistical validation.
- State-by-state performance.
- `stressed_panic` preservation.
- Turnover and cost impact.
- BIL/cash exposure.
- SPY/offense/defense exposure.
- Hidden beta check.
- Benchmark comparison versus exact GGG and pinned Phase2B when relevant.
- Complexity justification.
- Files changed and commands run.
- Production/dashboard diff result.

## Frontier-Specific Gates

Suggested thresholds are configurable, but a sprint must state them before judging results:

- Sharpe improves by at least a small predeclared amount, or return improves with equal/better drawdown and CVaR.
- Max drawdown is not materially worse.
- CVaR 5% is not materially worse.
- 2020+ holdout is improved or at least not damaged.
- Rolling-origin win rate is supportive.
- Bootstrap support is supportive.
- PSR and DSR proxy are supportive after trial-count adjustment.
- No hidden beta, lower-BIL, or cash-drag trick explains the improvement.
- Turnover and cost drag are not materially worse.
- `stressed_panic` performance is preserved.
- Complexity is justified by evidence.

## Research Hygiene

- Every sprint writes a summary report.
- Every sprint updates `project_journey.md` unless explicitly deferred.
- Every sprint records exact commands run.
- Every sprint records files changed.
- Every sprint confirms protected production/dashboard diff.
- Every rejected idea explains why.
- Every skipped item states the exact reason.
- Every research-only artifact is labeled as research-only.

## Lopez de Prado Checklist

- No leakage.
- Use purging and embargo when labels overlap future periods.
- Avoid overfitting through repeated trials.
- Do not interpret one lucky backtest as proof.
- For ML, require feature-importance or attribution stability.
- Keep train/test split discipline.
- Reject if the idea is too complex for the evidence.
- Count all attempted variants, including failures.
- Prefer walk-forward and rolling-origin validation over one static split.
- Separate model selection from final evaluation.

## Stop / Pivot Rules

Stop or pivot a branch when:

- The same failure mode appears in three or more consecutive sprints.
- There is no holdout improvement.
- Improvement comes only from higher beta or lower BIL/cash.
- Turnover or cost drag overwhelms the apparent edge.
- Statistical support collapses after multiple-testing adjustment.
- The edge depends on unreproducible path dependence.
- `stressed_panic` defense is weakened.
- The branch requires data that cannot be made point-in-time.
- The implementation is too complex to audit.

## Default Frontier Posture

The default classification for any new frontier idea is `Research-only`. It earns its way upward; it is never promoted by narrative, novelty, or one attractive chart.
