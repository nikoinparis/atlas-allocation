# Final Judge Template — ETF Quant Research Committee

**Candidate:** {candidate}

The Final Judge synthesises the Bull, Bear, Risk, and Implementation
sections into one of four outcomes. The Judge is bound by the Phase D
8-gate production rule, the Risk Manager's blocking flags, and the
Implementation Auditor's sign-off.

## Required reading before issuing a verdict

- Bull Case (this directory)
- Bear Case (this directory)
- Risk Manager (this directory)
- Implementation Auditor (this directory)
- Quant Verification Checklist (this directory)
- Backtest Realism summary (Layer 5; if produced)
- Allocator Benchmark summary (Layer 6; if produced)

## The four verdicts

### KEEP AS PRODUCTION
Issued only if **all** of the following hold:
1. Phase D 8-gate production rule passes (full Δ ≥ +0.015, holdout Δ ≥ 0,
   holdout Sharpe Δ ≥ -0.02, rolling win ≥ 55%, rolling mean Δ > 0,
   bootstrap ≥ 60%, MDD cap ≥ -1.0pp, CVaR cap ≥ -0.20pp).
2. Risk Manager has zero blocking flags TRUE.
3. Implementation Auditor sign-off is clean.
4. Backtest Realism (Layer 5) shows the candidate still beats production
   under doubled-cost and rebalance-delay sensitivities.
5. Allocator Benchmark (Layer 6) shows the candidate beats simple
   baselines (Equal Weight, Inverse Vol, internal-HRP); extra complexity
   is justified.

### KEEP AS SHADOW
Issued if Phase D production rule fails BUT the candidate is the best
non-production candidate in the comparator set on raw composite AND
satisfies the Phase D shadow rule (holdout Δ ≥ 0, rolling win ≥ 55%,
bootstrap ≥ 50%, MDD cap ≥ -1.5pp, CVaR cap ≥ -0.30pp).

### REJECT
Issued if the candidate is materially worse than production on the full
window, OR has at least one Risk Manager blocking flag TRUE that cannot
be remediated.

### NEEDS FIX BEFORE JUDGMENT
Issued if the Implementation Auditor finds any plumbing issue, or if
required artifacts are missing (e.g. holdout CSV not generated,
rolling-origin missing, no protocol JSON, no bootstrap evidence).

## Verdict statement format

> **Verdict:** {one of the four}
>
> **Headline reason:** {one sentence; cite the most binding gate}
>
> **Conditions for promotion (if any):** {bulleted}
>
> **Next-phase recommendation:** {one paragraph; reference specific
> Phase D / shadow gates the candidate would need to clear}

## Pin-status note

Promotion to production or shadow is a HUMAN action, not a script action.
The Final Judge is a recommendation; the user remains the sole approver
of any pin-status change in `CLAUDE.md`.
