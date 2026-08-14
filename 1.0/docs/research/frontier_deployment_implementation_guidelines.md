---
editor_options: 
  markdown: 
    wrap: 72
---

# Frontier Deployment Intelligence — Implementation Guidelines

**Document version:** 2026-05-20\
**Purpose:** Concrete engineering rules for all frontier phase sprints\
**Scope:** Covers wrapper usage, signal construction, validation
discipline, governance, and common failure modes

------------------------------------------------------------------------

## 1. Wrapper Engineering Rules

### 1.1 The Exact Wrapper Is Mandatory

Every frontier sprint starts from
`scripts/allocator_checkpoint_wrapper.py` in no-modifier mode. This
wrapper reproduces GGG to machine precision:

```         
Net-return max error: 2.116e-16
Return correlation vs saved GGG: 1.0000000000
```

If a sprint's wrapper run does not reproduce this baseline to within
1e-10, stop and debug before proceeding. Never continue with an
incorrect baseline.

**Verification command:**

``` bash
.venv/bin/python scripts/test_allocator_checkpoint_wrapper.py
```

### 1.2 Read-Only First, Write Later

All new experiments start as diagnostic-only runs: 1. Load checkpoints
(read-only) 2. Build the modifier in memory 3. Apply the modifier in
memory 4. Compare returns vs GGG baseline

Only when the experiment has passed the diagnostic validation gates
should it become a portfolio pass-through candidate with write-mode
output.

### 1.3 Safe Checkpoints Only

| Checkpoint | Status | When to use |
|----|----|----|
| `regime_multipliers` | Safe | State-quality scaling of regime offsets |
| `offense_budget` | Safe | Trend quality, leadership quality modifiers |
| `cash_bil_budget` | Safe | Defensive floor adjustments |
| `transition_rerisk_smoothing` | Safe | Re-risk speed modifiers |
| `derisk_smoothing` | Safe | De-risk speed modifiers |
| `volatility_risk_overlay` | Safe | Vol-managed overlay adjustments |
| `final_etf_lookthrough_weights` | Read-only comparison only | Never modify |
| `raw_sleeve_targets` | Dangerous — diagnostic only | Never modify in portfolio candidates |
| `defense_budget` | Dangerous — diagnostic only | Never modify in portfolio candidates |
| `cost_turnover_calculation` | Dangerous — diagnostic only | Never modify |

### 1.4 Modifier Application Order

When stacking multiple modifiers from different frontier phases, apply
in this order:

1.  `regime_multipliers` — apply Phase 1 quality and Phase 4 leadership
    modifiers
2.  `offense_budget` — apply Phase 2 trend quality modifier
3.  `transition_rerisk_smoothing` — apply Phase 3 re-risk and Phase 7
    cross-asset modifiers
4.  `volatility_risk_overlay` — apply Phase 5 allocator objective
    modifier last

Never apply two modifiers to the same checkpoint without checking for
interaction effects. Document all modifier stacking explicitly in the
sprint report.

### 1.5 Stressed Panic Is Sacred

The `stressed_panic` state defense is unconditionally protected. No
modifier may: - Reduce `cash_bil_budget` in stressed_panic - Increase
`offense_budget` in stressed_panic - Speed up
`transition_rerisk_smoothing` in stressed_panic - Change
`regime_multipliers` in the offensive direction in stressed_panic

Violations of this rule are implementation errors, not research
findings. Fix them before reporting.

------------------------------------------------------------------------

## 2. Signal Construction Rules

### 2.1 One-Week Lag is Mandatory

All signals used in production-facing code must use `t-1` data for a
decision made at time `t`. This means:

-   All rolling windows compute from `price[t-52w]` to `price[t-1]`
-   Market state labels used as features come from
    `market_state_history.csv[t-1]`
-   Breadth signals are computed from prices at `t-1`
-   IC computations use `signal[t]` to predict `return[t+1..t+4]`

**Verification method:** After computing any new signal, verify that
`signal.shift(-1).corr(returns)` (shifting signal forward to align with
next-week returns) has different correlation than
`signal.corr(returns)`. If they are identical, there is likely a
look-ahead error.

### 2.2 No Hindsight State Labels

Market state labels must never use future information. The
`market_state_history.csv` file contains walk-forward labels — verify
that the label generation script was run with `t-1` data before using
it.

**Anti-pattern to avoid:**

``` python
# WRONG: Uses current prices to determine current state
state = classify_state(prices.iloc[-1])  # Wrong — uses current price
signal = state * momentum

# CORRECT: Uses prior period state
state = market_state_history.shift(1)  # Correct — one-week lag
signal = state * momentum
```

### 2.3 No Rolling Window Leakage

When using rolling calculations in signal construction, ensure the
rolling window does not include the current period:

``` python
# WRONG: Rolling includes current period before shifting
r2 = price.rolling(52).apply(lambda x: r_squared(x)).shift(1)

# CORRECT: Apply rolling first (which ends at t), then shift by 1 for lag
r2 = price.rolling(52).apply(lambda x: r_squared(x))  # ends at t
r2_lagged = r2.shift(1)  # now ends at t-1
```

### 2.4 Z-Score and Winsorize All Composites

Raw signals with different scales should be z-scored before blending.
Always winsorize at [-3, 3] to prevent outlier dominance:

``` python
def z_winsorize(s, clip_at=3.0):
    z = (s - s.mean()) / s.std()
    return z.clip(-clip_at, clip_at)
```

### 2.5 Economic Weights Must Be Pre-Declared

Composite weights for quality scores, leadership scores, etc. must be
declared *before* examining their effects. Do not tune weights to
maximize IC. If weights are adjusted, document the economic reason (not
the data reason) and report both the original-weight and revised-weight
results.

### 2.6 Ensemble Windows Reduce Rebalance Luck

For momentum signals, use an average of slightly different lookback
windows rather than a single lookback:

``` python
# Instead of:
mom = price.pct_change(26)

# Prefer:
mom = (price.pct_change(22) + price.pct_change(26) + price.pct_change(30)) / 3
```

This costs nothing and reduces period-specific artifacts from
single-window measurement.

------------------------------------------------------------------------

## 3. Validation Discipline

### 3.1 Pre-Declare the Holdout Window

The holdout window is `HOLDOUT_START = '2024-04-19'`, the last 104
weeks. This was declared in Phase 3.4 and has not changed. Never change
the holdout window declaration after beginning a sprint.

**Before running any experiment, write at the top of the script:**

``` python
HOLDOUT_START = pd.Timestamp('2024-04-19')
DEVELOPMENT_END = pd.Timestamp('2024-04-12')  # last date before holdout
```

### 3.2 Required Validation Report Contents

Every sprint report must include ALL of the following. A report is
incomplete if any section is missing:

**Full-history metrics:** - Annual return, Sharpe, Calmar, max drawdown,
CVaR 5% - Recovery-confirmed capture, stressed-panic Sharpe - Average
BIL weight, average turnover - Hidden beta vs SPY (should be \< 0.15
incremental)

**Holdout metrics (last 104 weeks):** - Annual return, Sharpe, Calmar,
max drawdown - Delta vs production pin

**Rolling-origin validation:** - 104-week test windows, 52-week step -
Table: origin date, candidate Sharpe, production Sharpe, delta - Win
rate: fraction of origins where candidate beats production

**Bootstrap:** - 2000 iterations, 13-week blocks, seed = 20260420 - Mean
delta, 95% CI, P(candidate \> production)

**State-by-state:** - For all 6 states: annual return, Sharpe, capture
ratio - Comparison vs production pin in each state

**Cost / turnover:** - Average weekly turnover (%) - Turnover cost
estimate (\@ 5bp half-spread) - Delta vs production pin on net-of-cost
returns

**Phase D gate table:** \| Gate \| Threshold \| Candidate \| Pass? \|
\|------\|-----------\|-----------\|-------\| \| Full Δ \| ≥ +0.015 \|
\| \| \| Holdout Δ \| ≥ 0 \| \| \| \| Holdout Sharpe Δ \| ≥ -0.02 \| \|
\| \| Rolling Win Rate \| ≥ 55% \| \| \| \| Rolling Mean Δ \| \> 0 \| \|
\| \| Bootstrap P \| ≥ 60% \| \| \| \| MDD Δ \| ≥ -0.01 \| \| \| \| CVaR
Δ \| ≥ -0.002 \| \| \|

### 3.3 Fixed Comparator Set

All Phase D comparisons use the same fixed comparator set: 1.
`improved_phase2b_regime_confidence_boost` (production pin) 2.
`improved_phaseggg_confirmed_only_robust_offense` (production candidate,
pending review) 3. `improved_phase2b_combo_abc` (shadow pin) 4. GGG
no-modifier wrapper baseline (exact reproduction)

Do not expand the comparator set without documenting the reason. A
larger comparator set makes the rank composite more volatile (documented
in Phase 3.3).

### 3.4 Purged Cross-Validation for ML

For any ML model training in Phase 6:

``` python
# Embargo configuration
EMBARGO_WEEKS = 4  # minimum gap between train and test

def purged_cv_splits(n, n_folds=5, embargo=4):
    """Generate train/test indices with purging and embargo."""
    fold_size = n // n_folds
    for k in range(n_folds):
        test_start = k * fold_size
        test_end = (k + 1) * fold_size
        # Training: all data before test_start - embargo
        train_idx = list(range(max(0, test_start - embargo)))
        test_idx = list(range(test_start, test_end))
        yield train_idx, test_idx
```

Standard k-fold CV will overstate performance on time-series data. Do
not use it for any ML model in this project.

### 3.5 Bootstrap Configuration

``` python
BOOTSTRAP_SEED = 20260420
BOOTSTRAP_N_ITERATIONS = 2000
BOOTSTRAP_BLOCK_SIZE_WEEKS = 13
```

Use these exact parameters for all bootstrap tests to ensure
comparability across phases.

------------------------------------------------------------------------

## 4. Governance Rules

### 4.1 Promotion Classification

Every experiment must receive exactly one of these verdicts with
explicit justification:

| Verdict | Criteria |
|----|----|
| **Promote** | Passes ALL 8 Phase D gates AND has clear economic interpretation |
| **Keep as Shadow** | Passes holdout Sharpe gate and bootstrap gate, but not all 8 gates. Better than current shadow pin on at least 3 metrics |
| **Research-only** | Directionally positive on at least 2 metrics but fails at least 3 Phase D gates |
| **Drop** | Does not improve on the production pin on any primary metric, or is redundant with an existing strategy, or has an implementation defect |

### 4.2 Production Pin Governance

The production pin is `improved_phase2b_regime_confidence_boost`. This
pin does NOT change: - Because a new candidate looks good in-sample -
Because a new candidate clears 6 of 8 Phase D gates - Because the user
asks without an explicit promotion review - Because the project is eager
to show improvement

The production pin changes ONLY when: 1. A candidate passes ALL 8 Phase
D gates 2. Human deployment review is completed (this is a human
decision, not automated) 3. The change is explicitly requested via
CLAUDE.md update

The shadow pin (`improved_phase2b_combo_abc`) changes only when a new
candidate clearly outperforms it on the holdout window AND receives
explicit governance approval.

### 4.3 Project Journey Updates

Every sprint adds a new section to `docs/research/project_journey.md`.
The entry must follow the established format:

``` markdown
## Section N — Phase [Name]: [Short Description]

### Why this sprint happened
[1 paragraph: what motivated it, what prior sprint indicated it]

### What was tried
[Specific candidates, scripts, modifications]

### What helped
[Specific results with numbers]

### What did not help
[Specific failures with numbers]

### Why it did not work (if applicable)
[Economic interpretation, not just "the numbers were bad"]

### Current reference set
[Updated pin/reference table]

### What comes next
[Next sprint recommendation, specific and narrow]
```

### 4.4 Git Commit Rules

Staging rules: - Stage specific files by name. Never use `git add -A` or
`git add .` - Always run `git status` before staging - Never stage
`public/dashboard-data.json` - Never stage files over 50 MB without
checking if they should be in `.gitignore` - Do not commit without
reviewing the diff

Commit message format:

```         
Add [Phase N] [brief description]

[1-2 sentences on what the sprint found]
```

### 4.5 File Naming Conventions

Scripts: - `scripts/phase_frontier{N}_{component}_{action}.py` -
Example: `scripts/phase_frontier1_state_quality_signals.py` - Example:
`scripts/phase_frontier2_wrapper_experiment.py`

Data outputs: -
`data/research/frontier_phase{N}/{descriptive_name}.csv` - Example:
`data/research/frontier_phase1/state_quality_signals.csv`

Reports: -
`docs/research/frontier_phase{N}_{descriptive_name}_report.md` -
Example:
`docs/research/frontier_phase1_deployment_state_intelligence_report.md`

------------------------------------------------------------------------

## 5. Common Failure Modes and How to Detect Them

### 5.1 Look-Ahead Bias

**What it looks like:** The candidate outperforms by a suspiciously
large margin in-sample but collapses on holdout. Or signals have
implausibly high IC (\> 0.15).

**How to detect:** 1. Shift the signal forward by 1 week
(`signal.shift(-1)`) and check if correlations with returns are the
same. If they are, the signal is leaking future information. 2. Check
that rolling windows use `.shift(1)` after the rolling calculation, not
before. 3. Verify that market state labels are from `t-1` (prior week's
state, not current week's state).

**How to fix:** Apply `.shift(1)` consistently to all signals. Never use
the current-period state for a signal that feeds into the current-period
allocation decision.

### 5.2 Redundancy with Existing Signals

**What it looks like:** A new signal has high IC but adds nothing when
controlling for existing signals. The wrapper modification produces
results nearly identical to the GGG baseline with small random
differences.

**How to detect:** Compute partial IC of the new signal after regressing
out the Phase 1–4 composites. If partial IC \< 0.01, the signal is
redundant.

**How to fix:** Either redesign the signal to be orthogonal (use
residuals from the momentum/breadth regression as the signal), or
reclassify as an internal refinement of existing signals rather than a
new signal.

### 5.3 Pool-Sensitive Composite Scores

**What it looks like:** A candidate clears the +0.015 composite gate in
a 10-member pool but falls to +0.008 in a 3-member pool (or vice versa).

**How to detect:** Always report the composite score on the FIXED
comparator set (production, GGG, shadow) as well as the full pool. If
the scores differ by \> 0.03, flag the gate clearance as pool-sensitive.

**How to fix:** Use the fixed comparator set's composite score as the
primary promotion decision metric. Use the full-pool composite only as
supplementary information.

### 5.4 Hidden SPY Beta

**What it looks like:** A candidate improves returns but mostly in bull
markets. Defensive-period performance is similar to or worse than the
production pin.

**How to detect:** Regress candidate excess returns on SPY returns.
Incremental beta \> 0.15 is a red flag. Check state-conditional returns
specifically in `stressed_panic` — if the candidate has lower Sharpe
than production in stressed panic, it is likely carrying hidden SPY
beta.

**How to fix:** Check whether the offensive sleeve weighting change is
appropriate, or reduce the modifier amplitude.

### 5.5 Overfitted Quality Composites

**What it looks like:** The quality composite has very high IC in the
development window but near-zero IC on holdout.

**How to detect:** Compute IC separately on the development window and
the holdout window. If the ratio of holdout IC to development IC is \<
0.30, the composite is overfit.

**How to fix:** Reduce the number of components in the composite. Use
equal-weighting rather than data-driven weighting. Check that no
component is based on look-ahead logic.

### 5.6 Turnover Creep

**What it looks like:** A candidate improves returns and Sharpe but has
30-50% higher turnover than the production pin.

**How to detect:** Always report average weekly turnover and turnover
delta in the sprint report. Compare against the 5bp half-spread cost
model.

**How to fix:** Apply a minimum holding period (e.g., minimum 2 weeks in
a position before the signal can exit), or apply exponential smoothing
to the modifier signal before applying it to checkpoints.

### 5.7 Recovery Capture Trap

**What it looks like:** Re-risking changes dramatically improve
recovery-confirmed capture but worsen stressed_panic or transition
protection.

**How to detect:** Always report stressed-panic Sharpe in every sprint
report. If stressed-panic Sharpe falls by \> 0.05 vs production, the
change is too aggressive.

**How to fix:** The re-risk modifier must have an unconditional
`if market_state == 'stressed_panic': return 0` guard. Verify this guard
is in place before running any re-risking experiment.

------------------------------------------------------------------------

## 6. Data Management Rules

### 6.1 Output Paths

All frontier phase data outputs go to
`data/research/frontier_phase{N}/`. These directories must be created by
the script before writing, and they should NOT be committed to the
repository if they contain large CSV files.

Files under 1 MB: can be committed. Files 1–10 MB: commit selectively;
prefer saving only summary outputs. Files \> 10 MB: add to `.gitignore`
or use LFS.

The following files are NEVER committed: - `public/dashboard-data.json`
(see CLAUDE.md) - Any production or dashboard data files in `public/` or
`src/`

### 6.2 Checkpoint Files

The checkpoint files loaded by the wrapper
(`data/03_layer2_strategy/checkpoints/`) are read-only reference
artifacts. Never overwrite them in a frontier sprint. If you need to
store a modified version of a checkpoint for comparison, write it to
`data/research/frontier_phase{N}/checkpoints/` instead.

### 6.3 Market State History

`data/03_layer2_strategy/market_state_history.csv` is the canonical
walk-forward state label file. It must not be modified in frontier
sprints. If a frontier phase experiment generates modified state labels,
save them to
`data/research/frontier_phase{N}/experimental_state_labels.csv`.

------------------------------------------------------------------------

## 7. Calibration Discipline

### 7.1 The Deflated Sharpe Warning

After 35+ tested strategy variants in this project, the expected Sharpe
inflation from selection bias is approximately 0.12 Sharpe units (see
Source Review for derivation). This means:

-   A +0.015 composite improvement at Phase D is below the deflation
    threshold on its own
-   A +0.05 Sharpe improvement vs. production needs context: is this the
    36th test or the 3rd?
-   All sprint reports should note the cumulative trial count when
    discussing significance

This does not invalidate the Phase D gates — they were calibrated with
this in mind. It does mean that candidates at the margin of the gates
should be treated as "probably not real" rather than "barely passes."

### 7.2 Realistic Improvement Targets

Based on the project history and literature review:

| Phase | Realistic Improvement Target |
|----|----|
| Phase 1 (State quality) | +0.10–0.25pp return, +0.02–0.05 Sharpe |
| Phase 2 (Trend quality) | +0.05–0.15pp return, +0.01–0.03 Sharpe |
| Phase 3 (Re-risking) | +0.05–0.20pp return, +5–15pp recovery capture |
| Phase 4 (Leadership) | +0.05–0.15pp return, +0.01–0.03 Sharpe |
| Phase 5 (Allocator) | +0.02–0.10pp return, -1 to -2pp turnover |
| Phase 6 (Decision ML) | +0.05–0.15pp return (uncertain, high risk) |
| Phase 7 (Cross-asset) | +0.03–0.10pp return |
| **Full frontier arc (Phases 1–7)** | **+0.3–0.8pp total** |

If a single phase claims to produce +0.30pp improvement or +0.10 Sharpe,
it is almost certainly overfit. Investigate before reporting.

### 7.3 The 10% Return Honesty Rule

The project's current best research is at 7.88% annualized. The gap to
10% is 2.12pp. Based on the literature review and project history:

-   The frontier deployment intelligence arc (Phases 1–7, free data) is
    likely to deliver +0.3–0.8pp.
-   PIT stock breadth (Phase 9, paid data) is likely to deliver an
    additional +0.2–0.5pp.
-   Together, maximum realistic improvement: 7.88% + 0.8% + 0.5% =
    **9.18% best case**.

10% annual return with the current ETF universe and risk discipline is
**not a realistic near-term target** under any combination of free-data
improvements. It would require either: 1. Genuinely new return streams
(commodities, managed futures, carry strategies) with meaningful
allocation 2. Accepting materially higher drawdown (which the Phase D
gates prohibit) 3. Data and methods beyond the current scope (e.g.,
factor timing with valuation data)

Do not optimize for 10% as a target. Optimize for robust,
holdout-validated improvement. If the frontier arc delivers 8.3–8.7%
annualized, that is a genuine success.

------------------------------------------------------------------------

## 8. Quick Reference Card

| Rule | Requirement |
|----|----|
| Wrapper baseline | Exact GGG reproduction to 1e-10 |
| Signal lag | Always 1 week (no look-ahead) |
| Holdout window | Last 104 weeks (declared, never changed) |
| Production pins | Never change without explicit authorization |
| Safe checkpoints | regime_multipliers, offense_budget, cash_bil_budget, transition_rerisk_smoothing, derisk_smoothing, volatility_risk_overlay |
| Dangerous checkpoints | Never modify in portfolio candidates |
| Stressed panic | Defense sacred, no modifier can increase offense in this state |
| Composite weights | Pre-declared, not tuned to data |
| Bootstrap | 2000 iterations, 13-week blocks, seed 20260420 |
| ML cross-validation | Purged with 4-week embargo |
| Promotion | ALL 8 Phase D gates must pass simultaneously |
| Report contents | Full, holdout, rolling-origin, bootstrap, state-by-state, turnover, hidden beta |
| Git commits | Specific files only, never git add -A |
| Dashboard files | Never modify public/ or src/ |
| Project journey | Updated every sprint, no exceptions |

------------------------------------------------------------------------

*Document ends. No production files modified.*
