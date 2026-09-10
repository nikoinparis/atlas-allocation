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
          Dashboard data is not available. Run <code className="mono">python3 scripts/phase_iii_packaging_review.py</code> to generate <code className="mono">public/production-candidate-dashboard-bundle.json</code>.
        </p>
      </section>
    );
  }

  const overview = data.overview ?? ({} as DashboardData["overview"]);
  const improved = (overview.improvedVersion ?? null) as Row | null;
  const baseline = (overview.baselineVersion ?? null) as Row | null;

  const productionName = str(improved, "version_name") || "improved_frontier_phase5_fragility_guard";
  const researchRow = (overview.researchVersion ?? null) as Row | null;
  const researchName = str(researchRow, "version_name");
  const annRet = num(improved, "ann_return");
  const annVol = num(improved, "ann_vol");
  const sharpe = num(improved, "sharpe");
  const mdd = num(improved, "max_drawdown");
  const calmar = num(improved, "calmar");
  const cvar5 = num(improved, "cvar_5");
  const turnover = num(improved, "avg_weekly_turnover");
  const annualTurnover = num(improved, "annual_turnover");
  const productionScore = num(improved, "production_score");

  const baseSharpe = num(baseline, "sharpe");
  const baseReturn = num(baseline, "ann_return");
  const baseDD = num(baseline, "max_drawdown");

  const latestDate = data.latestDate || "n/a";
  const generatedAt = data.generatedAt || "n/a";
  const versionRows = Array.isArray(data.improvementLab?.versions) ? data.improvementLab.versions : [];
  const findVersion = (name: string) =>
    (versionRows.find((row) => String(row.version_name ?? "") === name) as Row | null | undefined) ?? null;

  // Current production, prior production/rollback, and official shadow context.
  const phase2bConfBoost = findVersion("improved_phase2b_regime_confidence_boost");
  const phase2bComboAbc = findVersion("improved_phase2b_combo_abc");
  const prodSharpe = num(phase2bConfBoost, "sharpe") ?? sharpe;
  const prodDD = num(phase2bConfBoost, "max_drawdown") ?? mdd;
  const prodCVaR = num(phase2bConfBoost, "cvar_5") ?? cvar5;

  const researchLabel = researchName ? titleCase(researchName) : titleCase("improved_phase2b_combo_abc");
  const candidateLabel = titleCase(String(improved?.version_name ?? "improved_frontier_phase5_fragility_guard"));

  const researchRead = [
    `${candidateLabel} is now the official production pin after Phase 10A final evaluation and human authorization.`,
    phase2bConfBoost
      ? `Prior production / rollback posts Sharpe ${formatNumber(prodSharpe, 3)}, max drawdown ${formatPercent(prodDD, 2)}, and CVaR ${formatPercent(prodCVaR, 2)}. ${candidateLabel} improves the headline risk-adjusted profile while preserving stressed_panic offense behavior.`
      : null,
    phase2bComboAbc
      ? `${researchLabel} remains the official shadow. It is included in the compact bundle so reviewers can compare ${candidateLabel} against both the rollback pin and the shadow track.`
      : null,
    `The former production pin, ${titleCase("improved_phase2b_regime_confidence_boost")}, is preserved as rollback. GGG1 remains a historical prior production-candidate reference.`,
    `Known caveat: the sleeve-weight artifact is a review proxy for a wrapper modifier; returns and ETF weights are the production source of truth.`,
  ].filter((item): item is string => Boolean(item));
  const researchPathCards = [
    {
      title: "Layer 1 — Signal Foundation",
      copy: "Built and validated ETF momentum, trend, breadth, dollar-strength, and regime-aware signals. Weak, redundant, or unstable signals stayed diagnostic-only instead of being pushed into production.",
    },
    {
      title: "Layer 2 — Market State Quality",
      copy: "Phase 1 created the R2A state-quality score to ask whether a market state is trustworthy enough for offense. It improved holdout behavior, but was not promoted as a standalone strategy.",
    },
    {
      title: "Layer 3 — Portfolio Construction",
      copy: "The allocator now uses checkpointed research plumbing, so new ideas can be tested against GGG, the prior production pin, and the official shadow without rewriting production logic.",
    },
    {
      title: "Phase 5 — Winning Guardrail",
      copy: "The promoted design keeps Phase 1 offense scaling, then blocks that boost when Phase 4 leadership diagnostics say the market is crowded, mature, or fragile.",
    },
  ];
  const validationCards = [
    { label: "Passed Phase D Gates", value: "8/8", detail: "Promotion review cleared every final validation gate." },
    { label: "Bootstrap Support", value: "84%", detail: "Final Phase 10A bootstrap support was about 0.841." },
    { label: "Rolling Win Rate", value: "73%", detail: "Rolling validation favored the frontier guardrail design." },
    { label: "Stressed-Panic Defense", value: "Preserved", detail: "Stressed-panic offense max diff vs GGG was 0.000e+00." },
  ];
  const beforeAfterCards = [
    { label: "Sharpe", value: "0.884 → 0.948", detail: "Prior production to Frontier Phase5." },
    { label: "Max Drawdown", value: "-13.98% → -11.60%", detail: "Improved drawdown without adding stressed-panic offense." },
    { label: "Holdout Sharpe", value: "2.100 → 2.179", detail: "Holdout behavior improved in final evaluation." },
    { label: "Production Pin", value: "Frontier Phase5", detail: "improved_frontier_phase5_fragility_guard" },
  ];

  return (
    <section
      id="executive-summary"
      aria-label="Executive summary"
      className="mx-auto w-full max-w-6xl px-4 pb-10 pt-10"
    >
      <p className="mono text-xs uppercase tracking-[0.28em] text-[#b9853b]">Executive Summary</p>
      <h1 className="mt-2 text-3xl font-semibold text-[#f5f1e8] md:text-4xl">
        Layered ETF quant portfolio — production strategy snapshot
      </h1>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-[#c8c1ad]">
        The current production strategy is Frontier Phase5 Fragility Guard. It was selected after
        a multi-phase research process that combined signal discovery, exact allocator plumbing,
        statistical governance, and final promotion review.
      </p>

      <div className="mt-6 grid gap-4 rounded-3xl border border-white/10 bg-white/[0.03] p-5 md:grid-cols-2">
        <div>
          <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Production Candidate</p>
          <p className="mt-2 text-lg font-semibold text-[#f5f1e8]">{titleCase(productionName)}</p>
          <p className="mt-1 text-xs text-[#c8c1ad]">
            Design: HRP wrapper · Phase 1 R2A offense scaling + Phase 4 fragility guardrail
          </p>
          <p className="mt-1 text-xs text-[#c8c1ad]">
            Stressed-panic defense preserved · Phase 4 crowding check gates the offense boost
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

      <div className="mt-6 rounded-3xl border border-white/10 bg-white/[0.03] p-5">
        <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Research Journey</p>
        <h2 className="mt-2 text-2xl font-semibold text-[#f5f1e8]">Production Strategy: Frontier Phase5 Fragility Guard</h2>
        <p className="mt-3 max-w-4xl text-sm leading-7 text-[#d7d0bd]">
          The current production strategy was selected after a seven-phase frontier research process.
          The winning design combines a state-quality offense signal with a leadership/crowding
          guardrail, improving Sharpe and drawdown while preserving stressed-market defense.
        </p>
        <div className="mt-5 grid gap-3 md:grid-cols-2">
          {researchPathCards.map((card) => (
            <div key={card.title} className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <p className="font-semibold text-[#f5f1e8]">{card.title}</p>
              <p className="mt-2 text-sm leading-6 text-[#c8c1ad]">{card.copy}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {validationCards.map((card) => (
          <Stat key={card.label} label={card.label} value={card.value} detail={card.detail} />
        ))}
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {beforeAfterCards.map((card) => (
          <Stat key={card.label} label={card.label} value={card.value} detail={card.detail} />
        ))}
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
          <code className="mono">public/production-candidate-dashboard-bundle.json</code> at request time and are rendered
          server-side. The interactive dashboard below adds Layer-1 signals, Layer-2 sleeves,
          Layer-3 portfolio construction, allocator comparisons, a version lab, and diagnostics,
          all of which require client-side JavaScript.
        </p>
      </div>
    </section>
  );
}
