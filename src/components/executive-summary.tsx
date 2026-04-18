// Server component (NO "use client") — renders a static executive summary on first paint.
// This block exists so external viewers (ChatGPT, cURL, Lighthouse, crawler preview, etc.) see
// the headline numbers without waiting for client hydration, chart libraries, tabs, or accordions.
import type { DashboardData } from "@/types/dashboard";
import { formatNumber, formatPercent, isFiniteNumber, titleCase } from "@/lib/format";

type Row = Record<string, string | number | boolean | null | undefined>;

function num(row: Row | null | undefined, key: string): number | null {
  if (!row) return null;
  const v = row[key];
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function str(row: Row | null | undefined, key: string): string {
  if (!row) return "";
  const v = row[key];
  return v == null ? "" : String(v);
}

function delta(current: number | null, baseline: number | null) {
  if (current == null || baseline == null) return null;
  return current - baseline;
}

function signedValue(value: number | null, kind: "percent" | "number" = "number", digits = 2) {
  if (value == null || !Number.isFinite(value)) return "n/a";
  const formatted = kind === "percent" ? formatPercent(Math.abs(value), digits) : formatNumber(Math.abs(value), digits);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

function Stat({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">{label}</p>
      <p className="mt-2 text-xl font-semibold tracking-tight text-[#f5f1e8]">{value}</p>
      {detail ? <p className="mt-1 text-xs leading-relaxed text-[#c8c1ad]">{detail}</p> : null}
    </div>
  );
}

export function ExecutiveSummary({ data }: { data: DashboardData | null }) {
  if (!data) {
    return (
      <section className="mx-auto w-full max-w-6xl px-4 pt-8">
        <p className="text-sm text-[#c8c1ad]">
          Dashboard data is not available. Run <code className="mono">node scripts/build-dashboard-data.mjs</code> to generate <code className="mono">public/dashboard-data.json</code>.
        </p>
      </section>
    );
  }

  const overview = data.overview ?? ({} as DashboardData["overview"]);
  const improved = (overview.improvedVersion ?? null) as Row | null;
  const baseline = (overview.baselineVersion ?? null) as Row | null;
  const alloc = (overview.currentAllocationSummary ?? null) as Row | null;
  const marketState = (overview.latestMarketState ?? null) as Row | null;

  const productionName = str(improved, "version_name") || "improved_hrp_good_state_fragile_combo";
  const annRet = num(improved, "ann_return");
  const annVol = num(improved, "ann_vol");
  const sharpe = num(improved, "sharpe");
  const mdd = num(improved, "max_drawdown");
  const calmar = num(improved, "calmar");
  const cvar5 = num(improved, "cvar_5");
  const turnover = num(improved, "avg_weekly_turnover");
  const annualTurnover = num(improved, "annual_turnover");
  const upsideCapture = num(improved, "upside_capture_positive_weeks");
  const downsideCapture = num(improved, "downside_capture_negative_weeks");
  const calmCapture = num(improved, "calm_week_capture");
  const stressDownside = num(improved, "stress_downside_capture");
  const recoveryCapture = num(improved, "recovery_week_capture");
  const recoveryFragile = num(improved, "recovery_fragile_capture");
  const recoveryConfirmed = num(improved, "recovery_confirmed_capture");
  const productionScore = num(improved, "production_score");

  const currentMarketState = str(alloc, "current_market_state") || str(marketState, "market_state");
  const currentStateReason = str(alloc, "current_market_state_reason") || str(marketState, "market_state_reason");
  const offWeight = num(alloc, "current_offensive_weight");
  const defWeight = num(alloc, "current_defensive_weight");
  const cashProxy = num(alloc, "current_cash_proxy_weight");
  const bilWeight = num(alloc, "current_bil_weight");
  const spyWeight = num(alloc, "current_spy_weight");

  const baseSharpe = num(baseline, "sharpe");
  const baseReturn = num(baseline, "ann_return");
  const baseDD = num(baseline, "max_drawdown");

  const benchmarkSummary = Array.isArray(overview.benchmarkSummary) ? overview.benchmarkSummary : [];
  const findBench = (needles: string[]) =>
    benchmarkSummary.find((row) => {
      const n = String(row.strategy_name || "").toLowerCase();
      return needles.some((needle) => n.includes(needle));
    }) ?? null;
  // SPY exposure benchmark ≈ the market-proxy buy-and-hold; BIL-like stable is approximated by
  // the 60/40 proxy, which is the closest all-cash/safer mix available in the benchmark summary.
  const spyRow = findBench(["market_proxy", "buy_hold_spy", "spy"]);
  const bilRow = findBench(["60_40", "buy_hold_bil", "bil", "equal_weight_risk"]);
  const spySharpe = num(spyRow as Row, "sharpe");
  const spyReturn = num(spyRow as Row, "ann_return");
  const spyDD = num(spyRow as Row, "max_drawdown");
  const bilSharpe = num(bilRow as Row, "sharpe");
  const bilReturn = num(bilRow as Row, "ann_return");
  const spyLabel = spyRow ? titleCase(String(spyRow.strategy_name ?? "SPY")) : "SPY Buy-and-Hold";
  const bilLabel = bilRow ? titleCase(String(bilRow.strategy_name ?? "BIL")) : "BIL Cash Benchmark";

  const latestDate = data.latestDate || str(marketState, "Date") || "n/a";
  const generatedAt = data.generatedAt || "n/a";
  const versionRows = Array.isArray(data.improvementLab?.versions) ? data.improvementLab.versions : [];
  const findVersion = (name: string) =>
    (versionRows.find((row) => String(row.version_name ?? "") === name) as Row | null | undefined) ?? null;
  const goodStateFragileCombo = findVersion("improved_hrp_good_state_fragile_combo");
  const control = goodStateFragileCombo ?? findVersion("improved_hrp_neutral_ease");
  const selfGatedRelief = findVersion("improved_hrp_self_gated_relief_targeted");
  const continuousOverlay = findVersion("improved_hrp_continuous_overlay_careful");
  const targetedCombo = findVersion("improved_hrp_targeted_relief_continuous_combo");
  const canaryProxy = findVersion("improved_hrp_separate_canary_proxy");
  const thresholdRecentering = findVersion("improved_hrp_threshold_recentering");
  const trendEnsemble = findVersion("improved_hrp_trend_horizon_ensemble");
  const ctaVolManaged = findVersion("improved_hrp_cta_vol_managed_local");
  const nonSelfGatedNarrow = findVersion("improved_hrp_non_self_gated_relief_narrow");
  const nonSelfGatedFlat = findVersion("improved_hrp_non_self_gated_relief_flat");
  const nonSelfGatedPlusConfirmed = findVersion("improved_hrp_non_self_gated_relief_narrow_plus_confirmed");

  const controlScore = num(control, "production_score");
  const selfGatedScore = num(selfGatedRelief, "production_score");
  const selfGatedScoreDelta = delta(selfGatedScore, controlScore);
  const selfGatedBilDelta = delta(num(selfGatedRelief, "avg_bil_weight"), num(control, "avg_bil_weight"));
  const selfGatedPromotable =
    selfGatedScore != null &&
    controlScore != null &&
    selfGatedScore - controlScore >= 0.05 &&
    (num(selfGatedRelief, "max_drawdown") ?? -1) >= (num(control, "max_drawdown") ?? -1) - 0.005 &&
    (num(selfGatedRelief, "cvar_5") ?? -1) >= (num(control, "cvar_5") ?? -1) - 0.002;

  const plusConfirmedScore = num(nonSelfGatedPlusConfirmed, "production_score");
  const plusConfirmedScoreDelta = delta(plusConfirmedScore, controlScore);
  const plusConfirmedBilDelta = delta(num(nonSelfGatedPlusConfirmed, "avg_bil_weight"), num(control, "avg_bil_weight"));
  const plusConfirmedPromoted =
    productionName === "improved_hrp_non_self_gated_relief_narrow_plus_confirmed";
  const narrowScore = num(nonSelfGatedNarrow, "production_score");
  const narrowScoreDelta = delta(narrowScore, controlScore);
  const flatScore = num(nonSelfGatedFlat, "production_score");
  const flatScoreDelta = delta(flatScore, controlScore);

  const researchRead = [
    plusConfirmedPromoted && nonSelfGatedPlusConfirmed
      ? `Production has moved to ${titleCase(String(nonSelfGatedPlusConfirmed.version_name ?? ""))}. It keeps the self-gated relief line intact and extends narrow, capped overlay relief to non-self-gated sleeves in strong-neutral, recovery-fragile, and recovery-confirmed states. Production score ${formatNumber(plusConfirmedScore, 3)} vs ${formatNumber(controlScore, 3)} for the prior incumbent clears the 0.05 margin, max drawdown is unchanged, and CVaR is within tolerance.`
      : goodStateFragileCombo
      ? `The current production base is ${titleCase(String(goodStateFragileCombo.version_name ?? ""))}. It remains the incumbent because the best new challenger did not clear the promotion guardrail: production score ${formatNumber(controlScore, 3)} still sets the bar, and the latest challenger gains were too small to justify a swap.`
      : null,
    nonSelfGatedPlusConfirmed || nonSelfGatedNarrow || nonSelfGatedFlat
      ? `The non-self-gated overlay-relief sprint diagnosed the remaining bottleneck. Strong-neutral and recovery-fragile weeks were still carrying ~22-23% BIL because the composite non-self-gated sleeves (regime-conditioned and selective) got the full overlay haircut. Extending a tight, bounded relief to those sleeves, only in the good-state set, shaved BIL ~100 bps in each state with no change to max drawdown and only marginal CVaR/turnover drift.`
      : null,
    selfGatedRelief && nonSelfGatedNarrow
      ? `Standalone comparisons: self-gated-only relief ${titleCase(String(selfGatedRelief.version_name ?? ""))} delta ${signedValue(selfGatedScoreDelta, "number", 3)}, Variant A (narrow scale-bounded) ${signedValue(narrowScoreDelta, "number", 3)}, Variant B (flat) ${signedValue(flatScoreDelta, "number", 3)}, Variant C (narrow + recovery_confirmed) ${signedValue(plusConfirmedScoreDelta, "number", 3)}. Variant C was the only line to clear the promotion margin; A and B were Pareto-neutral-or-better but composite-score neutral.`
      : selfGatedRelief
      ? `${titleCase(String(selfGatedRelief.version_name ?? ""))} was the cleanest fix: production score ${formatNumber(selfGatedScore, 3)} vs ${formatNumber(controlScore, 3)} for the incumbent, average BIL ${selfGatedBilDelta == null ? "n/a" : formatPercent(Math.abs(selfGatedBilDelta), 2)} lower, and the same max drawdown. It helped, but ${selfGatedPromotable ? "it cleared" : `its score gain of ${signedValue(selfGatedScoreDelta, "number", 3)} did not clear`} the current promotion margin.`
      : null,
    continuousOverlay || targetedCombo
      ? `${titleCase(String(continuousOverlay?.version_name ?? "continuous overlay"))} and ${titleCase(String(targetedCombo?.version_name ?? "the A+B combo"))} improved neutral and recovery participation, but they still leaked too much into weak-neutral weeks and deepened max drawdown and CVaR. The diagnosis was right; the broader easing path still looks too tail-expensive, which is why the newer variants keep the state set narrow.`
      : null,
    canaryProxy || thresholdRecentering || trendEnsemble || ctaVolManaged
      ? `${titleCase(String(canaryProxy?.version_name ?? "The canary test"))} was only marginal, ${titleCase(String(thresholdRecentering?.version_name ?? "threshold recentering"))} and ${titleCase(String(trendEnsemble?.version_name ?? "trend horizon ensemble"))} were effectively inert, and ${titleCase(String(ctaVolManaged?.version_name ?? "cta vol managed local"))} improved tails mainly by adding back defense. With targeted non-self-gated relief now promoted, next attention shifts to whether the fragile-recovery tilt or layer-3 expression can contribute anything incremental at this level.`
      : null,
  ].filter((item): item is string => Boolean(item));

  return (
    <section
      id="executive-summary"
      aria-label="Executive summary"
      className="mx-auto w-full max-w-6xl px-4 pb-10 pt-10"
    >
      <p className="mono text-xs uppercase tracking-[0.28em] text-[#b9853b]">Executive Summary</p>
      <h1 className="mt-2 text-3xl font-semibold text-[#f5f1e8] md:text-4xl">
        Layered ETF quant portfolio — production candidate snapshot
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[#c8c1ad]">
        This page is rendered server-side so the key metrics are visible on first paint without
        JavaScript, tabs, or accordions. The interactive dashboard loads below.
      </p>

      <div className="mt-6 grid gap-4 rounded-3xl border border-white/10 bg-white/[0.03] p-5 md:grid-cols-2">
        <div>
          <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Production Candidate</p>
          <p className="mt-2 text-lg font-semibold text-[#f5f1e8]">{titleCase(productionName)}</p>
          <p className="mt-1 text-xs text-[#c8c1ad]">
            Allocator: {titleCase(str(improved, "method_name") || "hrp")} · Subset: {titleCase(str(improved, "subset_name") || "n/a")}
          </p>
          <p className="mt-1 text-xs text-[#c8c1ad]">
            Overlay: {titleCase(str(improved, "overlay_variant") || "n/a")} · State tilt: {titleCase(str(improved, "state_tilt") || "n/a")}
          </p>
        </div>
        <div>
          <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">As of</p>
          <p className="mt-2 text-lg font-semibold text-[#f5f1e8]">{latestDate}</p>
          <p className="mt-1 text-xs text-[#c8c1ad]">Dashboard data generated {generatedAt}</p>
          <p className="mt-1 text-xs text-[#c8c1ad]">
            Production score: {isFiniteNumber(productionScore) ? formatNumber(productionScore, 2) : "n/a"}
            {isFiniteNumber(baseSharpe) && isFiniteNumber(sharpe)
              ? ` · Sharpe ${formatNumber(sharpe, 2)} vs baseline_hrp ${formatNumber(baseSharpe, 2)}`
              : ""}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        <Stat label="Annual Return" value={formatPercent(annRet, 2)} detail={isFiniteNumber(baseReturn) ? `Baseline ${formatPercent(baseReturn, 2)}` : undefined} />
        <Stat label="Annual Vol" value={formatPercent(annVol, 2)} />
        <Stat label="Sharpe" value={formatNumber(sharpe, 2)} detail={isFiniteNumber(baseSharpe) ? `Baseline ${formatNumber(baseSharpe, 2)}` : undefined} />
        <Stat label="Max Drawdown" value={formatPercent(mdd, 2)} detail={isFiniteNumber(baseDD) ? `Baseline ${formatPercent(baseDD, 2)}` : undefined} />
        <Stat label="Calmar" value={formatNumber(calmar, 2)} />
        <Stat label="CVaR 5%" value={formatPercent(cvar5, 2)} />
        <Stat label="Weekly Turnover" value={formatPercent(turnover, 2)} detail={isFiniteNumber(annualTurnover) ? `Annualized ${formatNumber(annualTurnover, 2)}x` : undefined} />
        <Stat label="Production Score" value={formatNumber(productionScore, 2)} />
      </div>

      <div className="mt-6 grid gap-4 rounded-3xl border border-white/10 bg-white/[0.03] p-5 md:grid-cols-2">
        <div>
          <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Current Market State</p>
          <p className="mt-2 text-lg font-semibold text-[#f5f1e8]">{titleCase(currentMarketState || "n/a")}</p>
          {currentStateReason ? (
            <p className="mt-1 text-xs leading-relaxed text-[#c8c1ad]">{currentStateReason}</p>
          ) : null}
        </div>
        <div>
          <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Current Posture</p>
          <p className="mt-2 text-sm text-[#f5f1e8]">
            Offense {formatPercent(offWeight, 1)} · Defense {formatPercent(defWeight, 1)} · Cash proxy {formatPercent(cashProxy, 1)}
          </p>
          <p className="mt-1 text-xs text-[#c8c1ad]">
            BIL {formatPercent(bilWeight, 1)} · SPY {formatPercent(spyWeight, 1)}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-3">
        <Stat label="Upside Capture (up weeks)" value={formatPercent(upsideCapture, 1)} />
        <Stat label="Downside Capture (down weeks)" value={formatPercent(downsideCapture, 1)} />
        <Stat label="Calm-State Capture" value={formatPercent(calmCapture, 1)} />
        <Stat label="Recovery Capture (all)" value={formatPercent(recoveryCapture, 1)} />
        <Stat label="Recovery (Fragile) Capture" value={formatPercent(recoveryFragile, 1)} />
        <Stat label="Recovery (Confirmed) Capture" value={formatPercent(recoveryConfirmed, 1)} />
        <Stat label="Stress-State Downside Capture" value={formatPercent(stressDownside, 1)} />
        <Stat
          label={spyLabel}
          value={isFiniteNumber(spySharpe) ? `Sharpe ${formatNumber(spySharpe, 2)}` : "n/a"}
          detail={
            isFiniteNumber(spyReturn) && isFiniteNumber(spyDD)
              ? `${formatPercent(spyReturn, 2)} ret · ${formatPercent(spyDD, 2)} MDD`
              : undefined
          }
        />
        <Stat
          label={bilLabel}
          value={isFiniteNumber(bilSharpe) ? `Sharpe ${formatNumber(bilSharpe, 2)}` : "n/a"}
          detail={isFiniteNumber(bilReturn) ? `${formatPercent(bilReturn, 2)} ret` : undefined}
        />
      </div>

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-5">
        <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Latest Research Takeaway</p>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          {researchRead.map((item) => (
            <div key={item} className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="text-sm leading-relaxed text-[#d7d0bd]">{item}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-5">
        <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">How to read this page</p>
        <p className="mt-2 text-xs leading-relaxed text-[#c8c1ad]">
          The block above is the static executive summary — all numbers come from{" "}
          <code className="mono">public/dashboard-data.json</code> at request time and are rendered
          server-side. The interactive dashboard below adds Layer-1 signals, Layer-2 sleeves,
          Layer-3 portfolio construction, allocator comparisons, a version lab, and diagnostics,
          all of which require client-side JavaScript.
        </p>
      </div>
    </section>
  );
}
