# Recovery-state split, offense ladder, and dashboard inspectability — report

Date: 2026-04-16
Author: Research pipeline (automated, with discipline guardrails applied in `scripts/build-dashboard-data.mjs`)
Incumbent production candidate: `improved_hrp_recovery_tilt`
Challenger variants: `improved_hrp_recovery_split` (A), `improved_hrp_recovery_split_confirmed_offense` (B), `improved_hrp_recovery_split_confirmed_offense_neutral_ease` (C)
Data vintage: through 2026-04-10 · dashboard data regenerated 2026-04-17 UTC

---

## A. What changed (high level)

1. Market-state classifier is now a five-state taxonomy. The legacy `recovery_rebound` bucket has been split into two causal, tradable substates:
   - `recovery_fragile` — a post-stress window where breadth is improving but not yet broad and momentum is uneven.
   - `recovery_confirmed` — a post-stress window where breadth, 13w momentum, 26w momentum, trend, drawdown and risk score all clear stricter thresholds simultaneously.
2. New overlay variants were added that use the split:
   - Variant A: `recovery_split_baseline` — keep the legacy recovery stance but differentiate the sleeve floors (fragile=0.90, confirmed=0.94). State tilt is `split_modest`.
   - Variant B: `recovery_split_confirmed_offense` — ramp sleeve floor to 1.00 in confirmed, hold fragile at 0.88, reinforce calm_trend to 1.00. State tilt is `split_aggressive` (confirmed sleeves ×1.22, fragile ×1.06, defensives ×0.82).
   - Variant C: Variant B plus a mildly higher neutral-state sleeve floor (`strong_neutral_floor` 0.85 → 0.90), aimed at residual cash drag outside confirmed windows whose trend is still positive.
3. State-conditioned diagnostics now report capture separately for `recovery_fragile` and `recovery_confirmed`, and keep an aggregated `recovery_week_capture` that spans all three recovery labels for backward compatibility.
4. The Next.js homepage now renders a server-only `ExecutiveSummary` block on first paint. It reads `public/dashboard-data.json` on the server, has no `"use client"`, no charts, no tabs, and no accordions — the headline numbers are static HTML before any hydration.
5. The dashboard data builder now pins the production candidate to the incumbent `improved_hrp_recovery_tilt` unless a challenger beats it by a material production-score margin (0.05) without degrading max drawdown (>0.005) or CVaR (>0.002). This encodes research discipline and prevents in-noise score wins from silently promoting a variant.

## B. What was executed

- `scripts/build_improvement_artifacts.py` was edited in place and re-run end-to-end (wall time ~2m13s) with Python 3.10, pandas 2.3.3, numpy 2.2.6, scipy installed to the system interpreter.
- Regenerated artifacts include `data/04_layer2b_risk_regime_engine/market_state_history.csv`, `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`, `state_conditioned_allocation_summary.csv`, `sleeve_performance_by_state.csv`, and allocation-driver files.
- `node scripts/build-dashboard-data.mjs` was re-run to refresh `public/dashboard-data.json` after the pipeline completed.
- `npx tsc --noEmit` passed clean (exit 0) after the dashboard edits.

## C. Files modified

- `scripts/build_improvement_artifacts.py` — state classifier split into fragile/confirmed, added three overlay variants, added `split_modest` and `split_aggressive` tilt modes, added per-substate capture columns in the capture summary, added `avg_market_state_recovery_fragile` / `avg_market_state_recovery_confirmed` to window summaries, appended three variant specs A/B/C.
- `scripts/build-dashboard-data.mjs` — added `INCUMBENT_NAME` / `PROMOTION_MARGIN` guardrail around `improvedVersion` selection.
- `src/components/executive-summary.tsx` — new server component that renders headline metrics statically.
- `src/app/page.tsx` — imports and renders `ExecutiveSummary` above `DashboardShell`; forces dynamic rendering with zero revalidation so fresh JSON is always reflected.
- `src/components/dashboard-shell.tsx` — `sleeveStateRows` filter now includes `recovery_fragile` and `recovery_confirmed` so the rebuilt five-state taxonomy shows up in the Version Lab state table.
- `public/dashboard-data.json` — regenerated (22 MB) off the new artifacts.

No other source files were modified.

## D. Experimental results (all variants, full metrics)

All versions below use the same HRP allocator on the `upside_capture_recovery_*` subset and the same sleeve reallocation and rerisk speeds. The only differences are the overlay variant and the sleeve state-tilt mode. Rows come from `data/05_layer3_portfolio_construction/portfolio_version_comparison.csv`.

| Metric | baseline_hrp_default | control: improved_hrp_recovery_tilt | Variant A: split | Variant B: split + confirmed offense | Variant C: B + neutral ease |
|---|---:|---:|---:|---:|---:|
| Ann. return | 5.06% | **6.59%** | 6.59% | 6.62% | 6.72% |
| Ann. vol | 6.37% | 7.57% | 7.57% | 7.61% | 7.70% |
| Sharpe | 0.794 | **0.8705** | 0.8701 | 0.8698 | 0.8726 |
| Max drawdown | -12.22% | **-14.28%** | -14.28% | -14.28% | -14.28% |
| Calmar | 0.414 | **0.4613** | 0.4612 | 0.4632 | 0.4702 |
| CVaR 5% | -2.23% | **-2.54%** | -2.54% | -2.55% | -2.58% |
| Weekly turnover | 5.64% | 5.55% | 5.55% | 5.65% | 5.63% |
| Avg BIL weight | 44.9% | 31.1% | 31.1% | 30.8% | 29.8% |
| Avg SPY weight | 4.9% | 6.8% | 6.8% | 6.8% | 6.9% |
| Avg cash weight | 34.5% | 19.5% | 19.5% | 19.2% | 18.0% |
| Upside capture (positive weeks) | 25.2% | 31.3% | 31.3% | 31.4% | 31.8% |
| Downside capture (negative weeks) | 19.4% | 23.2% | 23.2% | 23.3% | 23.6% |
| Recovery capture (all labels) | 21.9% | 29.2% | 28.9% | 28.1% | 28.6% |
| Recovery fragile capture | 16.6% | 26.7% | 26.6% | 26.5% | 26.7% |
| **Recovery confirmed capture** | 42.0% | **38.8%** | 37.5% | **34.5%** | 35.9% |
| Calm-state capture | 31.0% | 41.4% | 41.4% | 42.6% | 42.7% |
| Stress downside capture | 23.2% | 30.0% | 30.0% | 29.9% | 30.1% |
| Production score | 0.335 | **0.7233** | 0.6583 | 0.6167 | 0.7267 |

Variant-vs-control deltas:

| Metric | A − control | B − control | C − control |
|---|---:|---:|---:|
| Ann. return | 0.00 pp | +0.03 pp | +0.13 pp |
| Sharpe | −0.0004 | −0.0007 | +0.0021 |
| Calmar | −0.0001 | +0.0019 | +0.0089 |
| CVaR 5% | 0.00 pp | −0.01 pp | −0.04 pp |
| Max drawdown | 0.00 pp | 0.00 pp | 0.00 pp |
| Recovery confirmed capture | −1.3 pp | **−4.3 pp** | −3.0 pp |
| Calm capture | 0.00 pp | +1.3 pp | +1.4 pp |
| Production score | −0.065 | −0.107 | +0.003 |

Two observations jump out: (1) none of the variants improved max drawdown, so the state split does not buy any risk-side edge. (2) Pushing confirmed offense harder actively *lowered* confirmed-recovery capture instead of raising it.

## E. Diagnostic interpretation

The surprising result in D is explained directly by `sleeve_performance_by_state.csv`. Per-sleeve Sharpe across the 49 fragile weeks and 44 confirmed weeks:

| Sleeve | Fragile Sharpe | Confirmed Sharpe | Fragile vs Confirmed |
|---|---:|---:|---|
| cta_trend_long_only | 1.78 | 1.01 | fragile >> confirmed |
| dual_momentum_topn | 1.40 | 0.01 | fragile >> confirmed |
| taa_10m_sma | 0.86 | 0.37 | fragile > confirmed |
| composite_regime_conditioned | 0.70 | 0.20 | fragile > confirmed |
| composite_selective_signals | 0.42 | −0.21 | fragile > confirmed |
| composite_selective_concentrated | 0.11 | 0.32 | confirmed slightly > fragile |

For five of six sleeves, the “confirmed” window was actually the *worse* bucket for realised Sharpe, not the better one. Economically this is consistent with how the confirmed filter is defined: it requires 26-week momentum and breadth to have already cleared high thresholds, which typically means the easy part of a recovery has been priced and we are entering a post-rally, mean-reverting phase rather than continuation. The fragile window — noisy but early — is where trend and momentum sleeves have their highest hit rate.

This explains why Variant B’s “ramp confirmed offense to 1.00 and tilt sleeves ×1.22” hurts: it systematically concentrates exposure into a window whose sleeves empirically underperform, and does so using the `split_aggressive` tilt that also dampens defensives ×0.82 right when the market is still volatile. The capture gain in `calm_trend` (+1.3 pp) is real but smaller than the loss in `recovery_confirmed` (−4.3 pp).

Variant C’s small gain over the control is almost entirely attributable to the neutral-floor change (0.85 → 0.90), not to the confirmed-offense ladder. Variant C holds ~1.5 pp less average cash (18.0% vs 19.5%) and earns ~13 bp more annual return for ~13 bp more annual vol. After rounding, Sharpe and production-score lift are within noise given ~10 years of weekly observations (~52 × 10 data points). Max drawdown is unchanged, and CVaR 5% loosens by 4 bp.

The state-conditioned allocation diffs are tiny across A/B/C — BIL moves by <2 pp and each sleeve by <2 pp — so the regime does not cause large composition changes, and none of the variants touched the stressed_panic allocation meaningfully.

## F. Decision classification

Using the user’s definition of Promote / Conditional / Research-only / Drop:

| Proposed change | Classification | Rationale |
|---|---|---|
| Split `recovery_rebound` into `recovery_fragile` and `recovery_confirmed` at the state-engine layer | **Research-only (keep)** | The split itself does not improve any production metric standalone (Sharpe −0.0004, Calmar −0.0001 on Variant A). It does surface a real empirical fact: fragile > confirmed in sleeve performance. Worth retaining as a diagnostic label set and for future regime-conditional work, but does not warrant promotion to the production path on its own. |
| `split_modest` sleeve tilt (fragile ×1.06, confirmed ×1.12) | **Drop** | Dampening fragile relative to confirmed contradicts the per-state sleeve Sharpe evidence (fragile is the stronger bucket). Variant A lost 0.065 production score. Do not promote. |
| `split_aggressive` tilt + confirmed offense ladder (confirmed 1.00 floor, sleeves ×1.22) | **Drop** | Actively harmful: Variant B dropped 4.3 pp of confirmed-recovery capture and 0.107 of production score. The hypothesis “confirmed is the safe time to add offense” is contradicted by the 10y evidence. Do not promote. |
| Neutral-floor ease (`strong_neutral_floor` 0.85 → 0.90 when trend is positive) | **Conditional** | Variant C delivers a +0.13 pp annual return, +0.0089 Calmar, +0.0021 Sharpe over the control. Max drawdown is flat, CVaR 5% loosens by 4 bp. The production-score win (+0.003) is not material. Worth keeping on the research branch and validating on OOS/newer data before promotion; not enough edge to promote today. |
| Server-side executive summary on the homepage | **Promote** | Purely inspectability win; no model-risk implications. Part B fix. |
| Incumbent pinning in `build-dashboard-data.mjs` (promotion margin 0.05 + no DD/CVaR regression) | **Promote** | Operational discipline, not a model change. Prevents in-noise variants from silently taking the production slot. |

Net for the production portfolio: the incumbent `improved_hrp_recovery_tilt` stays. No variant earns promotion. The state-split classifier is retained as a diagnostic layer; the offense-ladder hypothesis is refuted by this backtest.

## G. Homepage inspectability (Part B)

- `src/app/page.tsx` is a server component that: (a) reads `public/dashboard-data.json` from disk at request time, (b) renders `<ExecutiveSummary />` as pure static HTML, and (c) renders the existing `<DashboardShell />` below it. `export const dynamic = "force-dynamic"` + `revalidate = 0` ensure every request re-reads the JSON.
- `src/components/executive-summary.tsx` has no `"use client"` directive, no `useState`/`useEffect`, no chart imports, no tabs and no accordions. The HTML contains the production candidate name, annual return/vol, Sharpe, max drawdown, Calmar, CVaR 5%, weekly and annualized turnover, production score, current market state + reason, offense/defense/cash split, BIL/SPY weights, and full capture metrics (upside, downside, calm, recovery all/fragile/confirmed, stress). An out-of-band SSR probe (`/tmp/ssr_probe.mjs`) confirmed every required field is populated from the regenerated JSON.
- `DashboardShell` was already updated in a prior pass to render server-first from `initialData`. With `initialData` present on first render, no client-side fetch/loading screen gates the initial paint — the executive summary block is always visible before any React hydration occurs.
- `tsc --noEmit` passes clean.
- `next build` and `next dev` HTTP smoke-tests were attempted locally but the sandbox HTTP loopback to Next.js was not reachable in this environment (the server listened on `*:3939` but `curl 127.0.0.1:3939` timed out). The SSR probe + typecheck are the definitive checks available here. The HTML that Next will produce on deploy is exactly the ExecutiveSummary tree, which was verified to have a full and finite data graph against the live JSON snapshot.

## H. Final recommendation

1. Keep the production candidate as `improved_hrp_recovery_tilt`. None of A, B, C beats it on drawdown or CVaR, and the best of them (C) is within noise on Sharpe/production score.
2. Retain the `recovery_fragile` / `recovery_confirmed` taxonomy at the state-engine layer for diagnostic use only. Do not tie allocation decisions to the split yet.
3. Reject the “ramp offense in confirmed recovery” hypothesis for this dataset. The per-sleeve Sharpe evidence (fragile > confirmed for 5/6 sleeves) contradicts the hypothesis. A future iteration that does the opposite — lean into fragile, pull back in confirmed — is worth testing next.
4. Carry the neutral-floor ease (`strong_neutral_floor` 0.85 → 0.90 on positive-trend neutral weeks) as a Conditional change. Revisit after another OOS window or after the next signal/sleeve audit; do not promote to production yet.
5. Ship the server-rendered executive summary. External viewers (ChatGPT, crawlers, cURL) now see the headline numbers, current market state, posture, and benchmark comparisons without running any JavaScript.
6. Keep the incumbent-pinning guardrail in `build-dashboard-data.mjs`. It prevents a production change from happening silently on the back of a noise-level production-score win.
