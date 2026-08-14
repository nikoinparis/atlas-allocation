# Track C Predeclared New Alpha Research Plan

Track C is a research-only sprint. Track A production remains pinned to
`improved_frontier_phase5_fragility_guard`; Track B remains research-only and is
treated as evidence that extra return came mostly from higher SPY beta and lower
BIL/cash drag. No Track C output may update the production registry, overwrite a
Track A artifact, or be described as production-ready.

## Phase 0 Repo Understanding

### Track A Baseline

- Official production candidate: `improved_frontier_phase5_fragility_guard`.
- Canonical modules: `scripts/production_metrics.py` and
  `scripts/production_costs.py`.
- Production allocator component: `scripts/production_allocator.py`.
- Reproduction and governance: `scripts/reproduce_production_candidate.py`,
  `scripts/run_track_a_validation_governance.py`, and
  `scripts/run_track_a_verification_suite.py`.
- Full-period canonical baseline from Track B benchmark output:
  CAGR 7.13%, Sharpe 0.948, max drawdown -11.60%, CVaR 5% -2.49% weekly,
  average BIL/cash 27.61%, average equity 29.49%, SPY beta 0.240,
  average weekly turnover 6.74%.

### Track B Lesson

Track B tested 12 aggressive research-only variants and 7 benchmarks. The
highest-return candidate, `track_b_aggressive_blend_static_growth_50`, reached
about 9.05% CAGR but failed the mandate on drawdown (-29.27%), Sharpe (0.831),
and Calmar (0.309). The attribution output labeled the Track B candidates as
mostly higher beta/cash-drag rather than independent alpha. Track C therefore
must require beta/cash-drag attribution instead of accepting higher return alone.

### Current Signal Layer

The repo already has lagged/tradable Layer 1 signals for:

- Global and asset-class-neutral cross-sectional momentum.
- Time-series momentum and multi-horizon momentum.
- Residual momentum.
- 1-week and 4-week reversal.
- Carry and value proxies from ETF distribution/price history.
- Trend quality, breadth confirmation, and moving-average distance signals.
- A diagnostic HYG/LQD pair mean-reversion signal.

The Layer 1 summary shows basic momentum signals are statistically strongest but
redundant. Reversal is weak and high-turnover. Carry and value proxies are weak
as standalone signals. Residual momentum is more distinct but only modest.

### Current Strategy Sleeves And Universe

The current Layer 2A sleeve layer already includes momentum/trend sleeves,
defensive sleeves, calm carry, macro-trend diversification, reversal research,
pairs-stat-arb research, CTA trend, and vol-managed trend files. The available
ETF universe is 35 ETFs across equities, bonds, commodities, REITs, FX, and BIL
cash. No new data source will be added in Track C.

### Existing Research Notes Used

- `docs/research/signal_discovery_source_review.md`
- `docs/research/signal_discovery_backlog.md`
- `docs/research/frontier_deployment_intelligence_source_review.md`
- `docs/research/master_research_roadmap_and_resume_context.md`
- Layer 1 `signal_summary_table.csv` and `signal_incremental_contribution.csv`
- Layer 2A sleeve summaries and pair-stat-arb diagnostics

## Alpha Idea Classification

| Idea | Status | Independent-return thesis | Weekly ETF viability | Cost risk | Beta/cash-drag risk | Clean test | Success | Rejection |
|---|---:|---|---|---:|---:|---|---|---|
| Basic global xsmom / time-series trend | Already implemented sufficiently | Persistent ETF trend/relative strength | High | Medium | High | Compare new xsmom sleeve to existing momentum sleeve and Track A | Positive residual after SPY beta and low correlation | Mostly beta or high correlation to Track A/current sleeves |
| Multi-horizon momentum | Already implemented sufficiently | Reduces timing noise across lookbacks | High | Medium | High | Existing Layer 1/2 summaries | Incremental Sharpe after costs | Redundant with current momentum |
| HRP/HERC/risk-parity allocator variants | Already implemented sufficiently | Diversification and covariance-aware allocation | Medium | Low | Medium | Existing portfolio-version artifacts and Track A history | Lower CVaR/drawdown without return loss | Already tried extensively; no Track C implementation |
| Track B offense/cash overlays | Already implemented sufficiently | Higher return via higher risk budget | High | Low | Very high | Existing Track B reports | Not Track C success | Do not pursue in Track C |
| Carry/value ETF proxies | Implemented but likely incomplete/flawed | Distribution yield/value may diversify price momentum | Medium | Low/Medium | Medium | Standalone carry/value composite and 5/10/15% Track A overlays | Positive beta-adjusted residual and low correlation | Weak IC/returns or mostly defensive carry/cash tilt |
| Residual cross-sectional momentum | Implemented but incomplete as allocator | Momentum after broad SPY beta control may be less beta-like | Medium | Medium | Medium | Top-5 residual-momentum sleeve from tradable signal | Positive standalone residual, blend improves Sharpe or return | Low return, high turnover, or redundant with current trend |
| Short-horizon reversal | Implemented but likely incomplete/flawed | Mean reversion may help in neutral/choppy states | Low/Medium | High | Low/Medium | State-gated 4-week reversal only in neutral/reversal-friendly states | Improves neutral-state behavior after costs | Fails 2x costs or unstable by state |
| ETF pairs/stat arb | Implemented diagnostically, not robust | Relative-value spread mean reversion could be orthogonal | Low | Medium/High | Low | HYG/LQD diagnostic sleeve only | Positive residual and low turnover | Pair report already weak; reject if narrow/unstable |
| Defensive canary/breadth refinement | Partially implemented | Better risk-on/off gating could reduce false defensive states | Medium | Low | Medium | Continuous canary breadth sleeve, not a cash-cap overlay | Improves drawdown/CVaR or return with positive residual | Just lower cash drag or worse stressed-state behavior |
| Volatility-managed alpha | Partially implemented | Scale alpha exposure when realized vol is high | Medium | Medium | Medium | Vol-managed residual momentum sleeve | Better Sharpe/CVaR than unscaled residual momentum | Return destroyed or improvement purely lower beta |
| CVaR optimizer diagnostic | Not selected | Tail-aware allocation can audit risk construction | Medium | Low | Medium | Could be allocator diagnostic | Tail improvement without return loss | Too allocator-focused for new-alpha sprint |
| Black-Litterman views | Not selected | Priors plus explicit views may discipline allocation | Low/Medium | Low | Medium | Requires stable views | Clear, ex ante views with low turnover | Views are not independently validated |
| Macro/credit regime conditioning | Requires data or larger design | Credit/VIX/macro may improve regimes | Medium | Low | Medium | Needs point-in-time macro coverage | Robust state improvement | Current macro weekly file is underpopulated |
| PIT stock breadth / holdings breadth | Requires data | Breadth may be independent of ETF price momentum | High if PIT | Low | Medium | Needs clean point-in-time constituent data | Robust signal breadth | Not available in current data hub |
| ML/meta-labeling | Not worth testing now | Nonlinear filter may improve timing | Low/Medium | Low | High overfit risk | Requires purged CV and larger governance | Strong out-of-sample lift | Explicitly out of scope for Track C |

## Selected Experiments

Track C will test exactly six research-only standalone sleeves before any
Track A blend:

1. `track_c_residual_xsmom_top5`
   - Hypothesis: residual momentum can select ETFs with less broad-market beta
     than raw momentum.
   - Parameters: tradable `residual_mom_score_tradable`, top 5 ETFs, positive
     signal only, unused weight to BIL.
   - Success: positive beta-adjusted residual, reasonable turnover, and lower
     correlation to Track A than basic momentum.
   - Kill: weak standalone return, high beta explanation, or high overlap with
     Track A/current sleeves.

2. `track_c_vol_managed_residual_xsmom_top5`
   - Hypothesis: inverse realized-vol scaling can keep residual momentum alpha
     while improving tails.
   - Parameters: same top 5 residual sleeve, scaled to 60%/80%/100% risky
     exposure based on 13-week SPY realized vol using fixed thresholds.
   - Success: better Sharpe/CVaR than the unscaled residual sleeve and positive
     beta-adjusted residual.
   - Kill: lower return with no tail improvement or mostly reduced beta.

3. `track_c_carry_value_top5`
   - Hypothesis: carry plus value may diversify momentum if the ETF
     distribution/price-history proxies are usable.
   - Parameters: 50/50 blend of tradable carry and value scores, top 5 ETFs,
     positive score only, unused weight to BIL.
   - Success: low correlation to Track A and positive beta-adjusted residual.
   - Kill: weak IC/returns, obvious defensive/cash tilt, or stale data behavior.

4. `track_c_neutral_reversal_top5`
   - Hypothesis: 4-week reversal can add value in choppy neutral regimes where
     trend sleeves overreact.
   - Parameters: tradable 4-week global reversal score, active only in
     `neutral_mixed` or `reversal_friendly` regimes, top 5, otherwise BIL.
   - Success: positive neutral-state contribution after 2x costs.
   - Kill: high turnover, negative full-period result, or stress/recovery damage.

5. `track_c_hyg_lqd_pair_mean_reversion`
   - Hypothesis: the existing HYG/LQD diagnostic pair may provide a small
     credit relative-value sleeve independent of equity beta.
   - Parameters: use existing tradable pair signal; allocate HYG when positive,
     LQD when negative, BIL when missing/flat.
   - Success: positive standalone residual, low correlation, tolerable turnover.
   - Kill: narrow single-pair dependence, poor holdout, or high cost sensitivity.

6. `track_c_canary_breadth_timing`
   - Hypothesis: a continuous canary/breadth timing sleeve may improve timing
     quality without simply forcing a lower cash cap.
   - Parameters: fixed 60/40 risk basket when canary breadth is strong, partial
     risk when mixed, BIL/IEF defensive basket when weak/stress.
   - Success: drawdown/CVaR improvement or return lift with positive residual.
   - Kill: only lowers BIL/cash drag, fails stressed-panic behavior, or is
     dominated by simple Track B aggressive TAA benchmarks.

No other candidates will be added without a new predeclared plan.

## Blend Plan

Only standalone sleeves that pass sanity checks will be blended with Track A.
The blend weights are 5%, 10%, and 15%, funded proportionally from the existing
Track A allocation:

`blend_weights = (1 - overlay) * track_a_weights + overlay * sleeve_weights`

The blend must use Track A timing and canonical transaction-cost logic.

## Validation Gates

A Track C candidate can enter the research watchlist only if it satisfies most
of these checks:

- Track A blend improves CAGR by at least 50 bps without materially worse
  drawdown, or improves Sharpe by at least 0.03 with similar return, or reduces
  drawdown/CVaR with no major return loss.
- Estimated beta-adjusted residual contribution is positive.
- 2x cost sensitivity does not erase the case.
- Average weekly turnover remains realistic.
- Correlation to Track A and existing sleeves is not excessive.
- State-by-state behavior is explainable and not dependent only on the holdout.
- The logic is simple enough to audit.

Rejected or diagnostic-only status is required if return gain is mostly SPY beta
or BIL/cash drag, if 2x costs fail, if state behavior is unstable, if turnover is
too high, or if complexity is not justified.

## Governance

Every candidate will be logged with candidate name, hypothesis, parameters,
parent, source script, timestamp, standalone metrics, blend metrics where
applicable, SPY beta, Track A correlation, cost sensitivity, state performance,
and verdict: `research_watchlist`, `diagnostic_only`, or `rejected`.

Track C candidate count is six standalone sleeves plus small overlays only for
sleeves that pass the standalone sanity gate. No candidate may be marked
production.
