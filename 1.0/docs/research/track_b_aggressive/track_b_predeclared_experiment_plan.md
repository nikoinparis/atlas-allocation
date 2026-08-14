# Track B Predeclared Experiment Plan

## Mandate

Track B is a research-only higher-return sprint. It explicitly accepts more offense exposure, higher equity beta, lower BIL/cash allocation, and larger drawdown tolerance than Track A. Track B does not modify the Track A production candidate, does not write to the production registry, and does not claim production readiness.

Target profile:

- CAGR: 9% to 10% or better.
- Max drawdown tolerance: approximately -18% to -22%.
- Sharpe: target near Track A, minimum acceptable around 0.85.
- Calmar: preferably above 0.45.
- CVaR, turnover, cost sensitivity, beta, and regime behavior must be reported.

## Track A Baseline

Track A production is `improved_frontier_phase5_fragility_guard`, a wrapper-based allocator over GGG final ETF weights with Phase 1 R2A offense scaling and Phase 4 fragility guard. Track A canonical modules are:

- `scripts/production_metrics.py`
- `scripts/production_costs.py`
- `scripts/production_allocator.py`
- `scripts/reproduce_production_candidate.py`
- `scripts/run_track_a_validation_governance.py`

Track B must reuse these conventions and treat Track A as the conservative baseline.

## Namespace

Track B artifacts are isolated under:

- `scripts/track_b_aggressive/`
- `data/research/track_b_aggressive/`
- `docs/research/track_b_aggressive/`

No Track B script may write to `data/05_layer3_portfolio_construction/production_candidate_registry.json`.

## Benchmarks

Benchmarks are predeclared for honest comparison:

1. `track_a_production`
2. `spy_buy_hold`
3. `static_60_spy_40_ief`
4. `static_80_spy_20_bil`
5. `aggressive_taa_spy_trend`
6. `dual_momentum_top1`
7. `static_global_growth_90_10`

All benchmarks use existing weekly prices and Track A canonical path/cost logic.

## Candidate Grid

All candidates start from saved Track A production weights and apply a research-only final-weight overlay. The overlay does not alter Track A artifacts.

| candidate | hypothesis | exact parameters | expected tradeoff |
|---|---|---|---|
| `track_b_aggressive_cash_cap_20` | Lower idle cash in non-stress states may raise return without breaking defense. | Cap BIL at 20% in calm, neutral, recovery_confirmed, recovery_fragile; stressed_panic unchanged; excess allocated to existing offense weights. | Higher return and beta; slightly worse drawdown/CVaR. |
| `track_b_aggressive_cash_cap_15_good_20_neutral` | More targeted cash reduction in good states may improve return with less neutral-state risk. | Cap BIL at 15% in calm/recovery_confirmed, 20% in neutral/recovery_fragile; stressed_panic unchanged. | Lower BIL with moderate drawdown increase. |
| `track_b_aggressive_cash_cap_10_good_18_neutral` | A stronger cash cap tests whether 9% return is reachable without stress changes. | Cap BIL at 10% in calm/recovery_confirmed, 18% in neutral/recovery_fragile; stressed_panic unchanged. | Higher beta and larger drawdown risk. |
| `track_b_aggressive_offense_boost_10` | Small offense scaling may lift return while retaining Track A state timing. | Multiply offense assets by 1.10 in calm/recovery_confirmed, 1.05 in neutral/recovery_fragile; stressed_panic unchanged. | Higher offense and turnover; may be mostly beta. |
| `track_b_aggressive_offense_boost_20` | Stronger offense scaling tests the mandate boundary. | Multiply offense assets by 1.20 in calm/recovery_confirmed, 1.10 in neutral, 1.05 in recovery_fragile; stressed_panic unchanged. | Higher return potential; materially higher beta/drawdown. |
| `track_b_aggressive_cash10_offense10` | Combining cash reduction and mild offense boost may reach mandate with controlled stress behavior. | Cash caps: 10% calm/recovery_confirmed, 18% neutral/recovery_fragile; offense boost: 1.10 good states, 1.05 neutral/fragile; stressed_panic unchanged. | Higher return; likely higher beta and CVaR. |
| `track_b_aggressive_cash10_offense20` | Strongest Track A-timed overlay tests upper edge of drawdown tolerance. | Cash caps: 10% calm/recovery_confirmed, 18% neutral/recovery_fragile; offense boost: 1.20 good states, 1.10 neutral, 1.05 fragile; stressed_panic unchanged. | Highest Track A-timed return attempt; may fail drawdown or beta attribution. |
| `track_b_aggressive_rerisk_4w` | Faster re-risking after stress exits may reduce cash drag. | For four weeks after a stressed_panic exit, cap BIL at 12% and boost offense by 1.15 if current state is non-stress; stressed_panic unchanged. | May improve recoveries; can be path dependent. |
| `track_b_aggressive_vol_throttled` | Higher offense should be disabled during high realized SPY volatility. | Candidate `cash10_offense20` but disable offense boost and relax BIL caps to at least 20% when 13-week annualized SPY vol exceeds 25%. | Lower drawdown/CVaR than strongest overlay, lower return. |
| `track_b_aggressive_turnover_banded` | Aggressive weights may survive costs if small weekly changes are ignored. | Candidate `cash10_offense10`, but carry prior weights unless full L1 target change exceeds 5%. | Lower turnover and cost; may lag re-risking. |
| `track_b_aggressive_blend_static_growth_30` | A simple explicit risk budget may explain return gain versus timing. | 70% Track A production weights + 30% static global growth mix. | Higher beta, simple benchmark-like exposure. |
| `track_b_aggressive_blend_static_growth_50` | A more aggressive static blend tests whether 9-10% is mainly beta. | 50% Track A production weights + 50% static global growth mix. | Higher return potential; likely mostly beta and larger drawdown. |

## Success Criteria

A research-only candidate can enter the Track B shortlist only if it meets most of:

- CAGR at or above 9.0%, or a clear return improvement over Track A with acceptable risk tradeoff.
- Max drawdown no worse than -22%.
- Sharpe at or above 0.85.
- Calmar at or above 0.45.
- CVaR controlled versus aggressive benchmarks.
- 2x cost sensitivity remains acceptable.
- Turnover remains realistic.
- Holdout does not collapse.
- Stressed_panic behavior remains acceptable.
- It is competitive versus simple aggressive benchmarks.
- It is not obviously just a levered SPY/beta substitute.

## Kill Criteria

Reject or keep diagnostic-only if:

- CAGR remains below Track A without a major risk improvement.
- Max drawdown is worse than -22%.
- Sharpe falls below 0.85.
- Calmar falls below 0.45.
- CVaR is much worse than simple aggressive benchmarks.
- 2x cost sensitivity fails.
- Turnover is excessive.
- State-by-state behavior is unstable or stress protection collapses.
- Return gain is almost entirely explained by higher SPY beta.
- Complexity is not justified by improvement.

## Validation Gates

Every candidate must report:

- Full-period canonical metrics.
- Holdout metrics from Track A official holdout start.
- Rolling-origin metrics when enough data exists.
- 1x, 2x, and 3x transaction-cost sensitivity.
- Average BIL/cash, SPY, equity, offense, defense exposure.
- SPY beta and bond beta.
- State-by-state metrics.
- Stressed_panic, recovery_confirmed, and neutral_mixed behavior.
- Comparison versus Track A and all predeclared aggressive benchmarks.
- Attribution: beta, cash drag, offense/defense contribution, and state contribution.
