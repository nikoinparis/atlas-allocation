"use client";

import {
  BrainCircuit,
  ChevronDown,
  Layers3,
  LineChart as LineChartIcon,
  Scale,
  ShieldCheck,
  Table2,
  WalletCards,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Fragment } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";

import { chartColors, formatNumber, formatPercent, isFiniteNumber, methodColor, metricLabel, shortDate, titleCase } from "@/lib/format";
import type { DashboardData, MetricRow, ReturnPoint, WeightPoint } from "@/types/dashboard";

const sections = [
  { id: "overview", label: "Overview", icon: Layers3 },
  { id: "signals", label: "Layer 1", icon: BrainCircuit },
  { id: "sleeves", label: "Layer 2", icon: Scale },
  { id: "performance", label: "Layer 3", icon: LineChartIcon },
  { id: "methods", label: "Methods", icon: Table2 },
  { id: "improvement-lab", label: "Improvement Lab", icon: Layers3 },
  { id: "current-state", label: "Current State", icon: WalletCards },
  { id: "robustness", label: "Diagnostics", icon: ShieldCheck },
];

const defaultMetricKeys = [
  "ann_return",
  "ann_vol",
  "sharpe",
  "max_drawdown",
  "calmar",
  "cvar_5",
  "avg_weekly_turnover",
  "avg_effective_n",
];

const methodTableColumns = [
  "method_name",
  "category",
  "ann_return",
  "ann_vol",
  "sharpe",
  "max_drawdown",
  "calmar",
  "cvar_5",
  "avg_weekly_turnover",
  "annual_turnover",
  "avg_max_weight",
  "avg_effective_n",
  "avg_hhi",
  "weight_instability",
  "robustness_score",
  "psr_selection",
];

function metricValue(key: string, value: unknown) {
  if (["ann_return", "ann_vol", "max_drawdown", "cvar_5", "avg_weekly_turnover", "annual_turnover", "avg_max_weight", "hit_rate", "psr_zero", "psr_selection"].includes(key)) {
    return formatPercent(value, key === "psr_selection" || key === "psr_zero" ? 1 : 1);
  }
  if (["sharpe", "calmar", "avg_effective_n", "avg_hhi", "weight_instability", "allocation_instability", "robustness_score", "production_score"].includes(key)) {
    return formatNumber(value, 2);
  }
  if (typeof value === "string") return titleCase(value);
  return isFiniteNumber(value) ? formatNumber(value, 2) : "n/a";
}

function seriesLabel(name: string) {
  return titleCase(name.replace(/^benchmark::/, ""));
}

function combineSeries(portfolio: Record<string, ReturnPoint[]>, benchmarks: Record<string, ReturnPoint[]>, methods: string[], benchmarkNames: string[], valueKey: "wealth" | "drawdown" | "net_return") {
  const byDate = new Map<string, Record<string, string | number | null>>();
  const add = (label: string, rows: ReturnPoint[]) => {
    rows.forEach((row) => {
      const date = row.date;
      const value = row[valueKey];
      if (!date || !isFiniteNumber(value)) return;
      const item = byDate.get(date) ?? { date };
      item[label] = value;
      byDate.set(date, item);
    });
  };
  methods.forEach((name) => add(name, portfolio[name] ?? []));
  benchmarkNames.forEach((name) => add(`benchmark::${name}`, benchmarks[name] ?? []));
  return Array.from(byDate.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function rollingSharpeSeries(portfolio: Record<string, ReturnPoint[]>, methods: string[], window = 52) {
  const byDate = new Map<string, Record<string, string | number | null>>();
  methods.forEach((name) => {
    const rows = portfolio[name] ?? [];
    rows.forEach((row, index) => {
      const slice = rows.slice(Math.max(0, index - window + 1), index + 1).map((item) => item.net_return).filter(isFiniteNumber);
      if (slice.length < Math.max(20, window / 2)) return;
      const mean = slice.reduce((sum, value) => sum + value, 0) / slice.length;
      const variance = slice.reduce((sum, value) => sum + (value - mean) ** 2, 0) / Math.max(slice.length - 1, 1);
      const vol = Math.sqrt(variance) * Math.sqrt(52);
      const annReturn = mean * 52;
      const value = vol > 0 ? annReturn / vol : null;
      if (!row.date || !isFiniteNumber(value)) return;
      const item = byDate.get(row.date) ?? { date: row.date };
      item[name] = value;
      byDate.set(row.date, item);
    });
  });
  return Array.from(byDate.values()).sort((a, b) => String(a.date).localeCompare(String(b.date)));
}

function sortedTop<T extends Record<string, unknown>>(rows: T[], key: string, limit = 8) {
  return [...rows]
    .filter((row) => isFiniteNumber(row[key]))
    .sort((a, b) => Number(b[key]) - Number(a[key]))
    .slice(0, limit);
}

function MetricCard({ label, value, detail, tone = "neutral" }: { label: string; value: string; detail?: string; tone?: "neutral" | "good" | "warn" }) {
  const toneClass = tone === "good" ? "text-[#9dcfae]" : tone === "warn" ? "text-[#e0a77d]" : "text-[#f5f1e8]";
  return (
    <div className="glass-card rounded-3xl p-4">
      <p className="mono text-[0.7rem] uppercase tracking-[0.2em] text-[#b8b19f]">{label}</p>
      <p className={`mt-2 text-2xl font-semibold tracking-tight ${toneClass}`}>{value}</p>
      {detail ? <p className="mt-2 text-sm leading-relaxed text-[#c8c1ad]">{detail}</p> : null}
    </div>
  );
}

function Section({ id, eyebrow, title, children }: { id: string; eyebrow: string; title: string; children: ReactNode }) {
  return (
    <section id={id} className="scroll-mt-24 py-10">
      <p className="mono text-xs uppercase tracking-[0.28em] text-[#b9853b]">{eyebrow}</p>
      <h2 className="section-title mt-2 text-3xl font-semibold text-[#f5f1e8] md:text-5xl">{title}</h2>
      <div className="mt-6">{children}</div>
    </section>
  );
}

function Panel({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <div className="glass-card rounded-[2rem] p-5">
      <div className="mb-4">
        <h3 className="text-xl font-semibold text-[#f5f1e8]">{title}</h3>
        {subtitle ? <p className="mt-1 text-sm text-[#c8c1ad]">{subtitle}</p> : null}
      </div>
      {children}
    </div>
  );
}

function MultiSelectPills({ options, selected, onToggle, limit }: { options: string[]; selected: string[]; onToggle: (name: string) => void; limit?: number }) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.slice(0, limit ?? options.length).map((name) => {
        const active = selected.includes(name);
        return (
          <button
            key={name}
            onClick={() => onToggle(name)}
            className={`rounded-full border px-3 py-1.5 text-sm transition ${
              active ? "border-[#b9853b] bg-[#b9853b]/20 text-[#f5f1e8]" : "border-white/15 bg-white/[0.04] text-[#b8b19f] hover:border-white/30"
            }`}
          >
            {seriesLabel(name)}
          </button>
        );
      })}
    </div>
  );
}

function RankingBar({ rows, metric, labelKey = "method_name" }: { rows: Array<Record<string, unknown>>; metric: string; labelKey?: string }) {
  const chartRows = sortedTop(rows, metric, 10).map((row) => ({
    name: titleCase(String(row[labelKey] ?? "")),
    value: Number(row[metric]),
  }));
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={chartRows} layout="vertical" margin={{ left: 80, right: 20 }}>
        <CartesianGrid stroke="rgba(245,241,232,0.08)" horizontal={false} />
        <XAxis type="number" stroke="#b8b19f" tickFormatter={(value) => formatNumber(value, 1)} />
        <YAxis dataKey="name" type="category" stroke="#b8b19f" width={150} tick={{ fontSize: 12 }} />
        <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value) => formatNumber(value, 3)} />
        <Bar dataKey="value" radius={[0, 10, 10, 0]} fill="#b9853b" />
      </BarChart>
    </ResponsiveContainer>
  );
}

function SimpleTable({ rows, columns, maxRows = 12 }: { rows: Array<Record<string, unknown>>; columns: string[]; maxRows?: number }) {
  return (
    <div className="scrollbar-thin overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-full divide-y divide-white/10 text-left text-sm">
        <thead className="bg-white/[0.04] text-xs uppercase tracking-[0.15em] text-[#b8b19f]">
          <tr>
            {columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-4 py-3 font-medium">{metricLabel(column)}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {rows.slice(0, maxRows).map((row, index) => (
            <tr key={`${String(row[columns[0]])}-${index}`} className="bg-white/[0.015]">
              {columns.map((column) => (
                <td key={column} className="whitespace-nowrap px-4 py-3 text-[#eee7d6]">
                  {column.includes("return") || column.includes("vol") || column.includes("drawdown") || column.includes("turnover") || column.includes("cvar")
                    ? metricValue(column, row[column])
                    : column === "method_name" || column === "strategy_name" || column === "signal_name"
                      ? titleCase(String(row[column] ?? ""))
                      : metricValue(column, row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MethodComparisonTable({ rows }: { rows: MetricRow[] }) {
  const [sortKey, setSortKey] = useState("robustness_score");
  const [descending, setDescending] = useState(true);
  const sorted = useMemo(() => {
    return [...rows].sort((a, b) => {
      const av = a[sortKey];
      const bv = b[sortKey];
      if (isFiniteNumber(av) && isFiniteNumber(bv)) return descending ? bv - av : av - bv;
      return String(av ?? "").localeCompare(String(bv ?? "")) * (descending ? -1 : 1);
    });
  }, [rows, sortKey, descending]);

  return (
    <div className="scrollbar-thin overflow-x-auto rounded-2xl border border-white/10">
      <table className="min-w-[1400px] divide-y divide-white/10 text-left text-sm">
        <thead className="bg-white/[0.04] text-xs uppercase tracking-[0.14em] text-[#b8b19f]">
          <tr>
            {methodTableColumns.map((column) => (
              <th key={column} className="px-4 py-3">
                <button
                  className="inline-flex items-center gap-1 whitespace-nowrap"
                  onClick={() => {
                    if (sortKey === column) setDescending((value) => !value);
                    else {
                      setSortKey(column);
                      setDescending(true);
                    }
                  }}
                >
                  {metricLabel(column)}
                  <ChevronDown className={`h-3 w-3 transition ${sortKey === column && !descending ? "rotate-180" : ""}`} />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-white/10">
          {sorted.map((row) => (
            <tr key={row.method_name} className="bg-white/[0.015] hover:bg-white/[0.045]">
              {methodTableColumns.map((column) => (
                <td key={column} className="whitespace-nowrap px-4 py-3 text-[#eee7d6]">
                  {column === "method_name" || column === "category" ? titleCase(String(row[column] ?? "")) : metricValue(column, row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WeightBars({ rows, limit = 12 }: { rows: WeightPoint[]; limit?: number }) {
  const visible = rows.slice(0, limit);
  return (
    <div className="space-y-3">
      {visible.map((item, index) => (
        <div key={item.name}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="font-medium text-[#f5f1e8]">{item.name}</span>
            <span className="mono text-[#c8c1ad]">{formatPercent(item.weight, 1)}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div className="h-full rounded-full" style={{ width: `${Math.min(Math.abs(item.weight) * 100, 100)}%`, background: chartColors[index % chartColors.length] }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function RedundancyHeatmap({ data }: { data: DashboardData["signalRedundancy"] }) {
  const labels = data.rowLabels ?? data.signals;
  if (!data.signals.length) return <p className="text-sm text-[#c8c1ad]">No redundancy matrix found.</p>;
  return (
    <div className="scrollbar-thin overflow-auto rounded-2xl border border-white/10 p-3">
      <div className="grid min-w-[780px]" style={{ gridTemplateColumns: `160px repeat(${data.signals.length}, 32px)` }}>
        <div />
        {data.signals.map((signal) => (
          <div key={signal} className="h-28 origin-bottom -rotate-45 text-[10px] text-[#b8b19f]">{signal}</div>
        ))}
        {data.values.map((row, rowIndex) => (
          <Fragment key={`row-${labels[rowIndex]}`}>
            <div key={`label-${labels[rowIndex]}`} className="truncate pr-2 text-xs text-[#c8c1ad]">{labels[rowIndex]}</div>
            {row.map((value, colIndex) => {
              const alpha = Math.min(Math.abs(value), 1);
              const positive = value >= 0;
              return (
                <div
                  key={`${rowIndex}-${colIndex}`}
                  title={`${labels[rowIndex]} / ${data.signals[colIndex]}: ${formatNumber(value, 2)}`}
                  className="m-[1px] h-7 rounded"
                  style={{
                    background: positive ? `rgba(185, 133, 59, ${0.1 + alpha * 0.75})` : `rgba(61, 112, 87, ${0.1 + alpha * 0.75})`,
                  }}
                />
              );
            })}
          </Fragment>
        ))}
      </div>
    </div>
  );
}

function findRowByKey(rows: Array<Record<string, unknown>>, key: string, value: string | null | undefined) {
  if (!value) return null;
  return rows.find((row) => String(row[key] ?? "") === value) ?? null;
}

function deltaValue(current: unknown, baseline: unknown) {
  if (!isFiniteNumber(current) || !isFiniteNumber(baseline)) return null;
  return current - baseline;
}

function latestDifferenceRows(currentWeights: WeightPoint[], baselineWeights: WeightPoint[]) {
  const keys = new Set([...currentWeights.map((item) => item.name), ...baselineWeights.map((item) => item.name)]);
  return [...keys]
    .map((name) => {
      const current = currentWeights.find((item) => item.name === name)?.weight ?? 0;
      const baseline = baselineWeights.find((item) => item.name === name)?.weight ?? 0;
      return { asset: name, current_weight: current, baseline_weight: baseline, delta_weight: current - baseline };
    })
    .filter((row) => Math.abs(row.delta_weight) > 0.005 || row.current_weight > 0.02 || row.baseline_weight > 0.02)
    .sort((a, b) => Math.abs(b.delta_weight) - Math.abs(a.delta_weight))
    .slice(0, 12);
}

function buildAllocationMixChart(rows: Array<Record<string, string | number | boolean | null>>, versionName: string | null) {
  return rows
    .filter((row) => row.version_name === versionName)
    .map((row) => ({
      date: String(row.Date ?? row.date ?? ""),
      offensive_weight: Number(row.offensive_weight ?? 0),
      defensive_weight: Number(row.defensive_weight ?? 0),
      cash_proxy_weight: Number(row.cash_proxy_weight ?? 0),
      bil_weight: Number(row.bil_weight ?? 0),
      spy_weight: Number(row.spy_weight ?? 0),
    }));
}

function buildBreakdownRows(rows: Array<Record<string, string | number | boolean | null>>, versionName: string | null, asset: string) {
  return rows
    .filter((row) => row.version_name === versionName && row.horizon === "current" && row.asset === asset)
    .sort((a, b) => Math.abs(Number(b.contribution ?? 0)) - Math.abs(Number(a.contribution ?? 0)))
    .slice(0, 8);
}

export function DashboardShell({ initialData }: { initialData: DashboardData | null }) {
  const [data, setData] = useState<DashboardData | null>(initialData);
  const [error, setError] = useState<string | null>(null);
  const [selectedMethods, setSelectedMethods] = useState<string[]>([]);
  const [selectedBenchmarks, setSelectedBenchmarks] = useState<string[]>([]);
  const [weightMethod, setWeightMethod] = useState<string>("");
  const [baselineVersion, setBaselineVersion] = useState<string>("");
  const [comparisonVersion, setComparisonVersion] = useState<string>("");

  useEffect(() => {
    if (initialData) return;
    fetch("/dashboard-data.json", { cache: "no-store" })
      .then((response) => {
        if (!response.ok) throw new Error(`Unable to load dashboard data: ${response.status}`);
        return response.json() as Promise<DashboardData>;
      })
      .then((payload) => setData(payload))
      .catch((err: Error) => setError(err.message));
  }, [initialData]);

  useEffect(() => {
    if (!data) return;
    const defaults = [
      data.overview.defaultCandidate?.method_name,
      data.overview.bestBySharpe?.method_name,
      data.overview.bestDrawdown?.method_name,
      "equal_weight",
    ].filter(Boolean) as string[];
    setSelectedMethods([...new Set(defaults)].filter((name) => data.portfolioReturns[name]));
    setSelectedBenchmarks(Object.keys(data.benchmarkReturns).slice(0, 2));
    setWeightMethod(data.overview.defaultCandidate?.method_name ?? Object.keys(data.portfolioWeights)[0] ?? "");
    setBaselineVersion(String(data.overview.baselineVersion?.version_name ?? Object.keys(data.improvementLab.versionReturns)[0] ?? ""));
    setComparisonVersion(String(data.overview.improvedVersion?.version_name ?? Object.keys(data.improvementLab.versionReturns).slice(-1)[0] ?? ""));
  }, [data]);

  const methodNames = useMemo(() => Object.keys(data?.portfolioReturns ?? {}), [data]);
  const benchmarkNames = useMemo(() => Object.keys(data?.benchmarkReturns ?? {}), [data]);
  const versionNames = useMemo(() => Object.keys(data?.improvementLab.versionReturns ?? {}), [data]);

  const wealthData = useMemo(() => data ? combineSeries(data.portfolioReturns, data.benchmarkReturns, selectedMethods, selectedBenchmarks, "wealth") : [], [data, selectedMethods, selectedBenchmarks]);
  const drawdownData = useMemo(() => data ? combineSeries(data.portfolioReturns, data.benchmarkReturns, selectedMethods, selectedBenchmarks, "drawdown") : [], [data, selectedMethods, selectedBenchmarks]);
  const rollingSharpeData = useMemo(() => data ? rollingSharpeSeries(data.portfolioReturns, selectedMethods) : [], [data, selectedMethods]);
  const versionWealthData = useMemo(() => data ? combineSeries(data.improvementLab.versionReturns, {}, [baselineVersion, comparisonVersion].filter(Boolean), [], "wealth") : [], [data, baselineVersion, comparisonVersion]);
  const versionDrawdownData = useMemo(() => data ? combineSeries(data.improvementLab.versionReturns, {}, [baselineVersion, comparisonVersion].filter(Boolean), [], "drawdown") : [], [data, baselineVersion, comparisonVersion]);

  if (error) {
    return <main className="dashboard-shell flex min-h-screen items-center justify-center p-6"><Panel title="Dashboard data error"><p>{error}</p></Panel></main>;
  }

  if (!data) {
    return (
      <main className="dashboard-shell px-4 py-6 md:px-7">
        <div className="mx-auto max-w-[1500px]">
          <div className="glass-card rounded-[2.5rem] p-8">
            <p className="mono text-xs uppercase tracking-[0.28em] text-[#b9853b]">Dashboard Bundle</p>
            <h1 className="mt-3 text-4xl font-semibold text-[#f5f1e8]">Research dashboard data is not available yet.</h1>
            <p className="mt-4 max-w-2xl text-base leading-7 text-[#c8c1ad]">
              Run the research pipeline, refresh the saved artifacts, and regenerate <span className="mono text-[#d7b072]">public/dashboard-data.json</span>. The page now renders server-first when that bundle exists, so there is no heavy client-side loading shell in the normal path.
            </p>
          </div>
        </div>
      </main>
    );
  }

  const defaultCandidate = data.overview.defaultCandidate;
  const latestRegime = data.overview.latestRegime;
  const latestMarketState = data.overview.latestMarketState ?? data.marketStateHistory.at(-1) ?? null;
  const latestWeights = data.portfolioWeights[weightMethod]?.latest ?? [];
  const latestSleeves = data.sleeveWeights[weightMethod]?.latest ?? [];
  const baselineVersionRow = findRowByKey(data.improvementLab.versions, "version_name", baselineVersion);
  const comparisonVersionRow = findRowByKey(data.improvementLab.versions, "version_name", comparisonVersion);
  const currentAllocationSummary = findRowByKey(data.improvementLab.allocationDrivers, "version_name", comparisonVersion) ?? data.overview.currentAllocationSummary ?? null;
  const versionLatestWeights = data.improvementLab.versionWeights[comparisonVersion]?.latest ?? [];
  const versionLatestSleeves = data.improvementLab.versionSleeveWeights[comparisonVersion]?.latest ?? [];
  const baselineLatestWeights = data.improvementLab.versionWeights[baselineVersion]?.latest ?? [];
  const allocationMixChart = buildAllocationMixChart(data.improvementLab.allocationDriverTimeseries, comparisonVersion);
  const bilBreakdownRows = buildBreakdownRows(data.improvementLab.allocationDriverBreakdown, comparisonVersion, "BIL");
  const spyBreakdownRows = buildBreakdownRows(data.improvementLab.allocationDriverBreakdown, comparisonVersion, "SPY");
  const weightDifferenceRows = latestDifferenceRows(versionLatestWeights, baselineLatestWeights);
  const defensivePostureRows = [
    { metric: "Avg Offensive", value: currentAllocationSummary?.avg_offensive_weight },
    { metric: "Avg Defensive", value: currentAllocationSummary?.avg_defensive_weight },
    { metric: "Avg Cash Proxy", value: currentAllocationSummary?.avg_cash_proxy_weight },
    { metric: "Avg Overlay Cash", value: currentAllocationSummary?.avg_overlay_cash_weight },
    { metric: "Avg Sleeve BIL", value: currentAllocationSummary?.avg_sleeve_bil_weight },
    { metric: "Avg Regime Multiplier", value: currentAllocationSummary?.avg_regime_multiplier },
    { metric: "Avg Target Vol Multiplier", value: currentAllocationSummary?.avg_target_vol_multiplier },
    { metric: "Stressed Regime Frequency", value: currentAllocationSummary?.stressed_regime_frequency },
  ];
  const marketStateFeatureRows = [
    { metric: "Market State", value: latestMarketState?.market_state },
    { metric: "Risk State", value: latestMarketState?.risk_state },
    { metric: "State Reason", value: latestMarketState?.market_state_reason },
    { metric: "Breadth Above 10m", value: latestMarketState?.breadth_sma_43 },
    { metric: "Breadth 26w Momentum", value: latestMarketState?.breadth_26w_mom },
    { metric: "Market Drawdown", value: latestMarketState?.market_drawdown },
    { metric: "Google Fear Z", value: latestMarketState?.google_fear_z_tradable },
  ];
  const versionUpsideRows = [...data.improvementLab.upsideCaptureVersionComparison].sort((a, b) => Number(b.production_score ?? 0) - Number(a.production_score ?? 0));
  const targetedWindowComparisonRows = data.improvementLab.targetedWindowSummary.filter((row) => [baselineVersion, comparisonVersion].includes(String(row.version_name ?? "")));
  const rallyComparisonRows = data.improvementLab.rallyWindowAttribution.filter((row) => [baselineVersion, comparisonVersion].includes(String(row.version_name ?? "")));
  const reriskComparisonRows = data.improvementLab.reriskingLagByWindow.filter((row) => [baselineVersion, comparisonVersion].includes(String(row.version_name ?? "")));
  const sleeveStateRows = [...data.improvementLab.sleevePerformanceByState]
    .filter((row) => ["recovery_rebound", "calm_trend", "stressed_panic", "neutral_mixed"].includes(String(row.market_state ?? "")))
    .sort((a, b) => Number(b.sharpe ?? 0) - Number(a.sharpe ?? 0));
  const currentStateTiltRows = data.improvementLab.stateConditionedAllocationSummary
    .filter((row) => row.version_name === comparisonVersion && row.market_state === latestMarketState?.market_state)
    .sort((a, b) => Math.abs(Number(b.avg_weight ?? 0)) - Math.abs(Number(a.avg_weight ?? 0)))
    .slice(0, 10);
  const selectedLineKeys = [...selectedMethods, ...selectedBenchmarks.map((name) => `benchmark::${name}`)];
  const robustRows = [...data.methods].sort((a, b) => Number(b.robustness_score ?? 0) - Number(a.robustness_score ?? 0));
  const signalRows = [...data.signalSummary].sort((a, b) => Number(b.validation_quality_score ?? 0) - Number(a.validation_quality_score ?? 0));

  return (
    <main className="dashboard-shell">
      <div className="mx-auto flex max-w-[1500px] gap-6 px-4 py-5 md:px-7">
        <aside className="sticky top-5 hidden h-[calc(100vh-2.5rem)] w-64 shrink-0 rounded-[2rem] border border-white/10 bg-[#0c1324]/70 p-4 backdrop-blur-xl lg:block">
          <div className="rounded-3xl bg-[#b9853b]/15 p-4">
            <p className="mono text-xs uppercase tracking-[0.22em] text-[#d7b072]">Research Stack</p>
            <h1 className="mt-2 text-2xl font-semibold leading-tight">ETF Quant Portfolio</h1>
          </div>
          <nav className="mt-5 space-y-1">
            {sections.map(({ id, label, icon: Icon }) => (
              <a key={id} href={`#${id}`} className="flex items-center gap-3 rounded-2xl px-3 py-2.5 text-sm text-[#c8c1ad] transition hover:bg-white/10 hover:text-[#f5f1e8]">
                <Icon className="h-4 w-4 text-[#b9853b]" />
                {label}
              </a>
            ))}
          </nav>
          <div className="absolute bottom-4 left-4 right-4 rounded-3xl border border-white/10 p-4 text-sm text-[#c8c1ad]">
            <p className="mono text-[0.65rem] uppercase tracking-[0.2em] text-[#b8b19f]">Latest Data</p>
            <p className="mt-1 text-[#f5f1e8]">{shortDate(data.latestDate)}</p>
            <p className="mt-3">Generated {shortDate(data.generatedAt.slice(0, 10))}</p>
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <section id="overview" className="pb-10 pt-4">
            <div className="glass-card overflow-hidden rounded-[2.5rem] p-6 md:p-9">
              <div className="grid gap-8 lg:grid-cols-[1.2fr_0.8fr]">
                <div>
                  <p className="mono text-xs uppercase tracking-[0.28em] text-[#b9853b]">Layered ETF Quant Research</p>
                  <h1 className="section-title mt-4 text-5xl font-bold leading-[0.96] text-[#f5f1e8] md:text-7xl">{data.overview.projectTitle}</h1>
                  <p className="mt-5 max-w-3xl text-lg leading-8 text-[#d7d0bd]">
                    A full research stack that moves from Layer 1 alpha signals, to Layer 2 strategy logic and risk regimes, to Layer 3 portfolio construction. The dashboard emphasizes out-of-sample comparison, drawdown control, turnover, concentration, and robustness rather than choosing a winner by Sharpe alone.
                  </p>
                  <div className="mt-6 grid gap-3 md:grid-cols-3">
                    {[
                      ["Layer 1", "Signals: momentum, value, carry proxies, BAB, quality, residual momentum."],
                      ["Layer 2", "Strategy logic: dual momentum, CTA trend, selective composites, regime engine."],
                      ["Layer 3", "Portfolio construction: robust allocators, improvement lab, and baseline-vs-improved comparison."],
                    ].map(([title, copy]) => (
                      <div key={title} className="rounded-3xl border border-white/10 bg-white/[0.045] p-4">
                        <p className="font-semibold text-[#f5f1e8]">{title}</p>
                        <p className="mt-2 text-sm leading-6 text-[#c8c1ad]">{copy}</p>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="rounded-[2rem] border border-white/10 bg-[#0c1324]/60 p-5">
                  <p className="mono text-xs uppercase tracking-[0.22em] text-[#b8b19f]">Current Production Candidate</p>
                  <h2 className="mt-3 text-3xl font-semibold text-[#f5f1e8]">{titleCase(String(comparisonVersionRow?.version_name ?? defaultCandidate?.method_name ?? ""))}</h2>
                  <p className="mt-3 text-sm leading-6 text-[#c8c1ad]">
                    {String(comparisonVersionRow?.note ?? defaultCandidate?.description ?? "Chosen from the robustness framework when available.")}
                  </p>
                  <p className="mt-3 rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-6 text-[#d7d0bd]">
                    The current improvement pass focuses on one question: can the allocator re-risk faster after stress without giving back too much of the drawdown control that made the earlier versions credible?
                  </p>
                  <div className="mt-5 grid grid-cols-2 gap-3">
                    <MetricCard label="Best by Sharpe" value={titleCase(data.overview.bestBySharpe?.method_name)} />
                    <MetricCard label="Most Robust" value={titleCase(data.overview.bestByRobustness?.method_name)} tone="good" />
                    <MetricCard label="Drawdown Control" value={titleCase(data.overview.bestDrawdown?.method_name)} />
                    <MetricCard
                      label="Current Market State"
                      value={titleCase(String(latestMarketState?.market_state ?? latestRegime?.risk_state ?? ""))}
                      detail={titleCase(String(latestMarketState?.market_state_reason ?? latestRegime?.signal_environment ?? ""))}
                      tone={String(latestMarketState?.market_state ?? latestRegime?.risk_state ?? "") === "stressed_panic" ? "warn" : "good"}
                    />
                  </div>
                  <div className="mt-4 rounded-3xl border border-white/10 bg-white/[0.035] p-4">
                    <p className="mono text-[0.68rem] uppercase tracking-[0.18em] text-[#b8b19f]">Baseline vs Improved</p>
                    <div className="mt-3 grid gap-2 text-sm text-[#c8c1ad]">
                      <div className="flex items-center justify-between gap-3">
                        <span>{titleCase(String(baselineVersionRow?.version_name ?? ""))}</span>
                        <span className="mono text-[#f5f1e8]">{metricValue("sharpe", baselineVersionRow?.sharpe)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span>{titleCase(String(comparisonVersionRow?.version_name ?? ""))}</span>
                        <span className="mono text-[#9dcfae]">{metricValue("sharpe", comparisonVersionRow?.sharpe)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3 border-t border-white/10 pt-2">
                        <span>Production score</span>
                        <span className="mono text-[#d7b072]">{metricValue("robustness_score", comparisonVersionRow?.production_score)}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="metric-grid mt-5">
              {defaultMetricKeys.map((key) => (
                <MetricCard
                  key={key}
                  label={metricLabel(key)}
                  value={metricValue(key, comparisonVersionRow?.[key] ?? defaultCandidate?.[key])}
                  detail={isFiniteNumber(deltaValue(comparisonVersionRow?.[key], baselineVersionRow?.[key])) ? `vs baseline ${metricValue(key, deltaValue(comparisonVersionRow?.[key], baselineVersionRow?.[key]))}` : undefined}
                />
              ))}
            </div>
            <div className="mt-5">
              <Panel title="Benchmark comparison" subtitle="Layer 2 baselines retained for context: market proxy buy-and-hold, 60/40, and equal-weight risky assets when available.">
                <SimpleTable rows={data.overview.benchmarkSummary} columns={["strategy_name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "avg_weekly_turnover"]} maxRows={6} />
              </Panel>
            </div>
          </section>

          <Section id="signals" eyebrow="Layer 1" title="Signal research findings">
            <div className="grid gap-5 xl:grid-cols-2">
              <Panel title="Signal validation summary" subtitle="IC, Newey-West t-stats, redundancy, and validation-quality score from Layer 1.">
                <SimpleTable rows={signalRows} columns={["signal_name", "recommendation", "avg_mean_ic", "avg_ic_tstat_nw", "avg_cross_coverage", "avg_abs_redundancy", "validation_quality_score"]} maxRows={18} />
              </Panel>
              <Panel title="Signal quality ranking" subtitle="Higher quality does not guarantee production usefulness; redundancy and implementation cost still matter.">
                <RankingBar rows={signalRows as Array<Record<string, unknown>>} metric="validation_quality_score" labelKey="signal_name" />
              </Panel>
              <Panel title="Incremental signal contribution" subtitle="Starts from a sensible trend-plus-quality/value core and checks whether each add-on improves the downstream long-only ETF sleeve.">
                <SimpleTable
                  rows={[...data.improvementLab.signalIncremental]
                    .filter((row) => row.test_type === "add_one")
                    .sort((a, b) => Number(b.delta_sharpe_vs_base ?? 0) - Number(a.delta_sharpe_vs_base ?? 0))}
                  columns={["candidate_signal", "delta_sharpe_vs_base", "delta_ann_return_vs_base", "delta_max_drawdown_vs_base", "delta_turnover_vs_base", "avg_bil_weight", "avg_spy_weight"]}
                  maxRows={8}
                />
              </Panel>
              <Panel title="Signal subset comparison" subtitle="Compact comparison of the current full blend versus cleaner finalist subsets.">
                <SimpleTable
                  rows={[...data.improvementLab.signalSubsets].sort((a, b) => Number(b.sharpe ?? 0) - Number(a.sharpe ?? 0))}
                  columns={["combo_name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_weekly_turnover"]}
                  maxRows={8}
                />
              </Panel>
              <Panel title="IC decay by horizon" subtitle="Forward-horizon IC curves show whether predictive relationships persist or decay quickly.">
                <ResponsiveContainer width="100%" height={360}>
                  <LineChart data={buildSignalIcChart(data.signalIc, signalRows.slice(0, 6).map((row) => row.signal_name))}>
                    <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                    <XAxis dataKey="horizon" stroke="#b8b19f" />
                    <YAxis stroke="#b8b19f" tickFormatter={(value) => formatNumber(value, 2)} />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatNumber(value, 3), titleCase(String(name))]} />
                    {signalRows.slice(0, 6).map((row, index) => (
                      <Line key={row.signal_name} type="monotone" dataKey={row.signal_name} dot strokeWidth={2} stroke={chartColors[index % chartColors.length]} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </Panel>
              <Panel title="Signal redundancy heatmap" subtitle="Correlation among standardized signal panels. Similar signals may add less incremental value downstream.">
                <RedundancyHeatmap data={data.signalRedundancy} />
              </Panel>
            </div>
          </Section>

          <Section id="sleeves" eyebrow="Layer 2" title="Strategy and sleeve breakdown">
            <div className="grid gap-5 xl:grid-cols-[1fr_0.9fr]">
              <Panel title="Standalone Layer 2 strategy metrics" subtitle="These sleeves feed Layer 3; baselines are kept visible for honest comparison.">
                <SimpleTable rows={[...data.strategySummary].sort((a, b) => Number(b.validation_score ?? b.sharpe ?? 0) - Number(a.validation_score ?? a.sharpe ?? 0))} columns={["strategy_name", "strategy_type", "ann_return", "ann_vol", "sharpe", "max_drawdown", "avg_weekly_turnover", "validation_score"]} maxRows={18} />
              </Panel>
              <Panel title="Improved candidate sleeves" subtitle="The stronger finalist keeps the robust sleeves, drops the breadth brake, and tests whether a recovery-aware concentrated sleeve truly adds enough upside to justify promotion.">
                <SimpleTable
                  rows={[...data.improvementLab.sleeveSubsets]
                    .filter((row) => ["replace_equal_with_selective", "replace_equal_with_concentrated", "drop_breadth"].includes(String(row.subset_name ?? "")))
                    .sort((a, b) => Number(b.sharpe ?? 0) - Number(a.sharpe ?? 0))}
                  columns={["method_name", "subset_name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "avg_cash_weight", "avg_bil_weight"]}
                  maxRows={8}
                />
              </Panel>
              <Panel title="Incremental sleeve contribution" subtitle="Tests whether the extra sleeve actually improves the final stack or just adds another brake.">
                <SimpleTable
                  rows={[...data.improvementLab.sleeveIncremental]
                    .sort((a, b) => Number(b.delta_sharpe_vs_baseline ?? 0) - Number(a.delta_sharpe_vs_baseline ?? 0))}
                  columns={["method_name", "candidate_sleeve", "subset_name", "delta_sharpe_vs_baseline", "delta_ann_return_vs_baseline", "delta_max_drawdown_vs_baseline", "delta_avg_bil_vs_baseline"]}
                  maxRows={12}
                />
              </Panel>
              <Panel title="Sleeve behavior by market state" subtitle="Shows which sleeves actually earned the right to get more weight in recovery, calm, or stressed conditions.">
                <SimpleTable rows={sleeveStateRows} columns={["strategy_name", "market_state", "ann_return", "ann_vol", "sharpe", "max_drawdown"]} maxRows={12} />
              </Panel>
              <Panel title="Current sleeve allocation" subtitle={`Latest sleeve mix for ${titleCase(comparisonVersion || weightMethod)} and the current market-state tilt.`}>
                <div className="grid gap-5 lg:grid-cols-2">
                  <WeightBars rows={versionLatestSleeves.length ? versionLatestSleeves : latestSleeves} limit={10} />
                  <SimpleTable rows={currentStateTiltRows} columns={["sleeve_name", "avg_weight"]} maxRows={10} />
                </div>
              </Panel>
            </div>
          </Section>

          <Section id="performance" eyebrow="Layer 3" title="Performance comparison">
            <div className="grid gap-5">
              <Panel title="Comparison controls" subtitle="Select portfolio construction methods and benchmarks to compare side by side.">
                <div className="space-y-4">
                  <div>
                    <p className="mb-2 text-sm font-semibold text-[#f5f1e8]">Portfolio methods</p>
                    <MultiSelectPills options={methodNames} selected={selectedMethods} onToggle={(name) => setSelectedMethods((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name])} />
                  </div>
                  <div>
                    <p className="mb-2 text-sm font-semibold text-[#f5f1e8]">Benchmarks</p>
                    <MultiSelectPills options={benchmarkNames} selected={selectedBenchmarks} onToggle={(name) => setSelectedBenchmarks((current) => current.includes(name) ? current.filter((item) => item !== name) : [...current, name])} />
                  </div>
                </div>
              </Panel>
              <Panel title="Cumulative wealth" subtitle="Net-of-cost wealth paths from saved Layer 3 and Layer 2 benchmark outputs.">
                <ResponsiveContainer width="100%" height={420}>
                  <LineChart data={wealthData}>
                    <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                    <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                    <YAxis stroke="#b8b19f" tickFormatter={(value) => formatNumber(value, 1)} />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatNumber(value, 2), seriesLabel(String(name))]} />
                    <Legend formatter={(value) => seriesLabel(String(value))} />
                    {selectedLineKeys.map((name) => (
                      <Line key={name} type="monotone" dataKey={name} dot={false} strokeWidth={2} stroke={methodColor(name, selectedLineKeys)} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </Panel>
              <div className="grid gap-5 xl:grid-cols-2">
                <Panel title="Drawdowns" subtitle="Lower and shallower drawdowns matter more than one lucky full-sample Sharpe.">
                  <ResponsiveContainer width="100%" height={320}>
                    <LineChart data={drawdownData}>
                      <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                      <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                      <YAxis stroke="#b8b19f" tickFormatter={(value) => formatPercent(value, 0)} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatPercent(value, 1), seriesLabel(String(name))]} />
                      {selectedLineKeys.map((name) => (
                        <Line key={name} type="monotone" dataKey={name} dot={false} strokeWidth={2} stroke={methodColor(name, selectedLineKeys)} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Panel>
                <Panel title="Rolling Sharpe" subtitle="Approximate 52-week rolling Sharpe on selected Layer 3 methods.">
                  <ResponsiveContainer width="100%" height={320}>
                    <LineChart data={rollingSharpeData}>
                      <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                      <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                      <YAxis stroke="#b8b19f" tickFormatter={(value) => formatNumber(value, 1)} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatNumber(value, 2), seriesLabel(String(name))]} />
                      {selectedMethods.map((name) => (
                        <Line key={name} type="monotone" dataKey={name} dot={false} strokeWidth={2} stroke={methodColor(name, selectedMethods)} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Panel>
              </div>
            </div>
          </Section>

          <Section id="methods" eyebrow="Allocator Comparison" title="Method comparison table">
            <Panel title="Sortable allocator metrics" subtitle="This table is intentionally broad: return, drawdown, tail risk, turnover, concentration, stability, and selection-aware diagnostics all matter.">
              <MethodComparisonTable rows={data.methods} />
            </Panel>
          </Section>

          <Section id="improvement-lab" eyebrow="Improvement Lab" title="Baseline vs improved portfolio versions">
            <div className="grid gap-5">
              <Panel title="Version controls" subtitle="Compare the original defensive baseline with the improved finalist configurations.">
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="mb-2 text-sm font-semibold text-[#f5f1e8]">Baseline version</p>
                    <select value={baselineVersion} onChange={(event) => setBaselineVersion(event.target.value)} className="w-full rounded-2xl border border-white/15 bg-[#0c1324] px-4 py-3 text-[#f5f1e8]">
                      {versionNames.map((name) => <option key={name} value={name}>{titleCase(name)}</option>)}
                    </select>
                  </div>
                  <div>
                    <p className="mb-2 text-sm font-semibold text-[#f5f1e8]">Improved version</p>
                    <select value={comparisonVersion} onChange={(event) => setComparisonVersion(event.target.value)} className="w-full rounded-2xl border border-white/15 bg-[#0c1324] px-4 py-3 text-[#f5f1e8]">
                      {versionNames.map((name) => <option key={name} value={name}>{titleCase(name)}</option>)}
                    </select>
                  </div>
                </div>
              </Panel>
              <div className="metric-grid">
                <MetricCard label="Sharpe Delta" value={metricValue("sharpe", deltaValue(comparisonVersionRow?.sharpe, baselineVersionRow?.sharpe))} tone="good" />
                <MetricCard label="CAGR Delta" value={metricValue("ann_return", deltaValue(comparisonVersionRow?.ann_return, baselineVersionRow?.ann_return))} tone="good" />
                <MetricCard label="Max Drawdown Delta" value={metricValue("max_drawdown", deltaValue(comparisonVersionRow?.max_drawdown, baselineVersionRow?.max_drawdown))} />
                <MetricCard label="Cash Delta" value={metricValue("avg_cash_weight", deltaValue(comparisonVersionRow?.avg_cash_weight, baselineVersionRow?.avg_cash_weight))} />
                <MetricCard label="BIL Delta" value={metricValue("avg_bil_weight", deltaValue(comparisonVersionRow?.avg_bil_weight, baselineVersionRow?.avg_bil_weight))} />
                <MetricCard label="Effective N Delta" value={metricValue("avg_effective_n", deltaValue(comparisonVersionRow?.avg_effective_n, baselineVersionRow?.avg_effective_n))} tone="good" />
              </div>
              <div className="grid gap-5 xl:grid-cols-2">
                <Panel title="Wealth comparison" subtitle="Improved versions should earn their keep against the baseline, not just in isolated metrics.">
                  <ResponsiveContainer width="100%" height={340}>
                    <LineChart data={versionWealthData}>
                      <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                      <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                      <YAxis stroke="#b8b19f" tickFormatter={(value) => formatNumber(value, 1)} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatNumber(value, 2), seriesLabel(String(name))]} />
                      {[baselineVersion, comparisonVersion].filter(Boolean).map((name, index) => (
                        <Line key={name} type="monotone" dataKey={name} dot={false} strokeWidth={2} stroke={chartColors[index % chartColors.length]} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Panel>
                <Panel title="Drawdown comparison" subtitle="Checks whether the improved version buys return with a reasonable drawdown trade-off rather than hidden fragility.">
                  <ResponsiveContainer width="100%" height={340}>
                    <LineChart data={versionDrawdownData}>
                      <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                      <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                      <YAxis stroke="#b8b19f" tickFormatter={(value) => formatPercent(value, 0)} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatPercent(value, 1), seriesLabel(String(name))]} />
                      {[baselineVersion, comparisonVersion].filter(Boolean).map((name, index) => (
                        <Line key={name} type="monotone" dataKey={name} dot={false} strokeWidth={2} stroke={chartColors[index % chartColors.length]} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </Panel>
              </div>
              <Panel title="Version comparison table" subtitle="Shows what actually changed: sleeve set, overlay rules, and the resulting out-of-sample metrics.">
                <SimpleTable rows={data.improvementLab.versions} columns={["version_name", "method_name", "production_score", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_weekly_turnover", "avg_effective_n", "avg_bil_weight", "avg_cash_weight"]} maxRows={12} />
              </Panel>
              <div className="grid gap-5 xl:grid-cols-2">
                <Panel title="Upside and downside capture" subtitle="This is the key check for the new pass: do we participate better in rallies without giving back too much of the downside discipline?">
                  <SimpleTable rows={versionUpsideRows} columns={["version_name", "production_score", "upside_capture_positive_weeks", "recovery_week_capture", "calm_week_capture", "downside_capture_negative_weeks", "avg_cash_when_benchmark_positive"]} maxRows={10} />
                </Panel>
                <Panel title="Re-risking lag after stress" subtitle="The best improved versions should move back into offense faster once the causal recovery state is confirmed.">
                  <SimpleTable rows={reriskComparisonRows} columns={["version_name", "window_name", "weeks_to_offensive_50", "weeks_to_offensive_60", "weeks_to_cash_below_35", "weeks_to_cash_below_25", "avg_dynamic_speed"]} maxRows={12} />
                </Panel>
                <Panel title="Recovery and rally-window attribution" subtitle="Helps explain missed upside: was the drag coming from overlay cash, weak offense, or slow re-risking?">
                  <SimpleTable rows={rallyComparisonRows} columns={["version_name", "window_name", "capture_ratio", "portfolio_return", "benchmark_return", "avg_offensive_weight", "avg_cash_weight", "avg_regime_multiplier", "avg_dynamic_speed"]} maxRows={14} />
                </Panel>
                <Panel title="Targeted stress and recovery windows" subtitle="Full-sample metrics matter, but these windows show whether the new logic helps in the environments that most shape benchmark participation.">
                  <SimpleTable rows={targetedWindowComparisonRows} columns={["version_name", "window_name", "window_type", "capture_ratio", "portfolio_return", "benchmark_return", "portfolio_max_drawdown", "avg_cash_weight"]} maxRows={16} />
                </Panel>
              </div>
            </div>
          </Section>

          <Section id="current-state" eyebrow="Current State" title="Current allocation drivers">
            <div className="grid gap-5">
              <div className="metric-grid">
                <MetricCard label="Market State" value={titleCase(String(currentAllocationSummary?.current_market_state ?? latestMarketState?.market_state ?? ""))} detail={titleCase(String(currentAllocationSummary?.current_market_state_reason ?? latestMarketState?.market_state_reason ?? ""))} tone={String(currentAllocationSummary?.current_state_label ?? "") === "defensive" ? "warn" : "good"} />
                <MetricCard label="Offensive" value={metricValue("ann_return", currentAllocationSummary?.current_offensive_weight)} />
                <MetricCard label="Defensive" value={metricValue("ann_return", currentAllocationSummary?.current_defensive_weight)} />
                <MetricCard label="Cash Proxy" value={metricValue("ann_return", currentAllocationSummary?.current_cash_proxy_weight)} />
                <MetricCard label="Avg Offensive" value={metricValue("ann_return", currentAllocationSummary?.avg_offensive_weight)} />
                <MetricCard label="Avg Cash Proxy" value={metricValue("ann_return", currentAllocationSummary?.avg_cash_proxy_weight)} />
                <MetricCard label="Current BIL" value={metricValue("ann_return", currentAllocationSummary?.current_bil_weight)} />
                <MetricCard label="Current SPY" value={metricValue("ann_return", currentAllocationSummary?.current_spy_weight)} />
              </div>
              <div className="grid gap-5 xl:grid-cols-3">
                <Panel title="Causal market-state explainer" subtitle="Uses only contemporaneously observable inputs: existing risk state, drawdown, breadth, and lagged fear/stress features.">
                  <SimpleTable rows={marketStateFeatureRows as Array<Record<string, unknown>>} columns={["metric", "value"]} maxRows={12} />
                </Panel>
                <Panel title="Allocation mix through time" subtitle="Offensive, defensive, and cash-proxy weights for the selected production candidate.">
                  <ResponsiveContainer width="100%" height={340}>
                    <AreaChart data={allocationMixChart}>
                      <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                      <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                      <YAxis stroke="#b8b19f" tickFormatter={(value) => formatPercent(value, 0)} />
                      <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} formatter={(value, name) => [formatPercent(value, 1), titleCase(String(name).replace(/_/g, " "))]} />
                      <Area type="monotone" dataKey="offensive_weight" stackId="1" stroke="#b9853b" fill="#b9853b" fillOpacity={0.75} />
                      <Area type="monotone" dataKey="defensive_weight" stackId="1" stroke="#3d7057" fill="#3d7057" fillOpacity={0.7} />
                      <Area type="monotone" dataKey="cash_proxy_weight" stackId="1" stroke="#8796b0" fill="#8796b0" fillOpacity={0.65} />
                    </AreaChart>
                  </ResponsiveContainer>
                </Panel>
                <Panel title="Why BIL is high / why SPY is low" subtitle="Current-date attribution from overlay cash plus sleeve look-through. This is where missed upside or justified caution becomes visible." >
                  <div className="space-y-5">
                    <div>
                      <p className="mb-2 text-sm font-semibold text-[#f5f1e8]">BIL drivers</p>
                      <SimpleTable rows={bilBreakdownRows} columns={["driver", "contribution"]} maxRows={8} />
                    </div>
                    <div>
                      <p className="mb-2 text-sm font-semibold text-[#f5f1e8]">SPY drivers</p>
                      <SimpleTable rows={spyBreakdownRows} columns={["driver", "contribution"]} maxRows={8} />
                    </div>
                  </div>
                </Panel>
              </div>
              <div className="grid gap-5 xl:grid-cols-3">
                <Panel title="Defensive posture summary" subtitle="Helps separate overlay-driven caution from sleeve-level BIL and shows whether target-vol scaling is really the binding brake.">
                  <SimpleTable rows={defensivePostureRows as Array<Record<string, unknown>>} columns={["metric", "value"]} maxRows={12} />
                </Panel>
                <Panel title="Latest ETF weights" subtitle={`Look-through weights for ${titleCase(comparisonVersion || weightMethod)}.`}>
                  <WeightBars rows={versionLatestWeights.length ? versionLatestWeights : latestWeights} limit={16} />
                </Panel>
                <Panel title="Allocation changes vs baseline" subtitle="Shows which assets gained or lost weight after the improvement pass.">
                  <SimpleTable rows={weightDifferenceRows as Array<Record<string, unknown>>} columns={["asset", "baseline_weight", "current_weight", "delta_weight"]} maxRows={12} />
                </Panel>
              </div>
            </div>
          </Section>

          <Section id="robustness" eyebrow="Diagnostics" title="Robustness, regimes, and fragility checks">
            <div className="grid gap-5 xl:grid-cols-2">
              <Panel title="Robustness ranking" subtitle="Composite ranking from Layer 3, not a pure Sharpe ranking.">
                <RankingBar rows={robustRows} metric="robustness_score" />
              </Panel>
              <Panel title="Regime score and states" subtitle="Layer 2B risk regime score, sampled for display.">
                <ResponsiveContainer width="100%" height={320}>
                  <ComposedChart data={data.regimeScore}>
                    <CartesianGrid stroke="rgba(245,241,232,0.08)" />
                    <XAxis dataKey="date" stroke="#b8b19f" minTickGap={40} />
                    <YAxis stroke="#b8b19f" />
                    <Tooltip contentStyle={{ background: "#111827", border: "1px solid rgba(245,241,232,0.16)", borderRadius: 16 }} />
                    <Area type="monotone" dataKey="risk_regime_score" fill="rgba(185,133,59,0.22)" stroke="#b9853b" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </Panel>
              <Panel title="Regime-split performance" subtitle="How method behavior changes in calm, neutral, and stressed environments.">
                <SimpleTable rows={data.regimeSplit} columns={["method_name", "risk_state", "ann_return", "ann_vol", "sharpe", "hit_rate", "observations"]} maxRows={18} />
              </Panel>
              <Panel title="Subperiod performance" subtitle="Checks whether results are broad-based or sample-period dependent.">
                <SimpleTable rows={data.subperiods} columns={["method_name", "subperiod", "ann_return", "ann_vol", "sharpe", "max_drawdown"]} maxRows={18} />
              </Panel>
              <Panel title="Optimizer diagnostics" subtitle="Fallbacks, average cash, and overlay behavior from Layer 3 diagnostics.">
                <SimpleTable rows={data.diagnosticsSummary} columns={["method_name", "observations", "fallback_count", "fallback_rate", "avg_cash_weight", "avg_gross_multiplier", "avg_active_sleeves"]} maxRows={14} />
              </Panel>
              <Panel title="Cost sensitivity" subtitle="Transaction-cost-aware check across methods.">
                <SimpleTable rows={data.costSensitivity} columns={["method_name", "cost_bps", "ann_return", "sharpe", "max_drawdown", "avg_weekly_turnover"]} maxRows={16} />
              </Panel>
              <Panel title="Stacked dampener sensitivity" subtitle="Checks whether target-vol caps, reallocation speed, and regime overlays are leaving the allocator underdeployed. Appears after the latest Layer 3 notebook rerun.">
                {data.dampenerSensitivity.length ? (
                  <SimpleTable rows={data.dampenerSensitivity} columns={["label", "target_vol_ceil", "sleeve_reallocation_speed", "overlay_variant", "ann_return", "ann_vol", "sharpe", "max_drawdown", "avg_cash_weight"]} maxRows={14} />
                ) : (
                  <p className="text-sm leading-6 text-[#c8c1ad]">No dampener sensitivity file found yet. Rerun `05_layer3_portfolio_construction.ipynb`, then `npm run refresh:data` to populate this table.</p>
                )}
              </Panel>
              <Panel title="Black-Litterman confidence sanity check" subtitle="Documents the heuristic signal-spread to view-confidence mapping used by the practical BL allocator.">
                {data.blConfidenceSensitivity.length ? (
                  <SimpleTable rows={data.blConfidenceSensitivity} columns={["view_spread", "confidence_floor", "confidence", "spread_divisor", "confidence_ceiling"]} maxRows={12} />
                ) : (
                  <p className="text-sm leading-6 text-[#c8c1ad]">No BL confidence sensitivity file found yet. The dashboard will pick it up automatically after the Layer 3 notebook regenerates it.</p>
                )}
              </Panel>
            </div>
          </Section>

          <footer className="pb-10 pt-6 text-sm text-[#b8b19f]">
            <div className="glass-card rounded-[2rem] p-5">
              <p className="font-semibold text-[#f5f1e8]">Refresh workflow</p>
              <p className="mt-2 leading-6">
                Run the research notebooks to update `data/01_data_hub` through `data/05_layer3_portfolio_construction`, run <span className="mono text-[#d7b072]">python3 scripts/build_improvement_artifacts.py</span> to refresh the improvement lab outputs, then run <span className="mono text-[#d7b072]">npm run refresh:data</span>. Vercel builds run the ingestion step before compiling the dashboard.
              </p>
              <p className="mt-3 mono text-xs">Artifacts tracked: {data.artifacts.filter((item) => item.exists).length}/{data.artifacts.length} found · bundle generated {data.generatedAt}</p>
            </div>
          </footer>
        </div>
      </div>
    </main>
  );
}

function buildSignalIcChart(rows: Array<Record<string, string | number | boolean | null>>, signalNames: string[]) {
  const horizons = [...new Set(rows.map((row) => Number(row.horizon_weeks)).filter(Number.isFinite))].sort((a, b) => a - b);
  return horizons.map((horizon) => {
    const item: Record<string, string | number | null> = { horizon: `${horizon}w` };
    signalNames.forEach((signalName) => {
      const found = rows.find((row) => row.signal_name === signalName && Number(row.horizon_weeks) === horizon);
      item[signalName] = typeof found?.mean_ic === "number" ? found.mean_ic : null;
    });
    return item;
  });
}
