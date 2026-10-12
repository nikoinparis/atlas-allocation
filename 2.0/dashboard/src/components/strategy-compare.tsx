"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Window = Partial<Record<"periods" | "totalReturn" | "cagr" | "volatility" | "sharpe" | "maxDrawdown" | "winRate", number>>;
type Since = Window & {
  created: string; bookAsOf: string; through: string; tradingDays: number; spyReturn: number; excessVsSpy: number;
  upDays: number; downDays: number; bestDay: number; worstDay: number; topContributor: string; topContribution: number;
  returnWithoutTop: number; names: number; largestWeight: number; largestWeightSymbol: string;
};
type Row = {
  id: string; name: string; subtitle: string;
  commonBacktest: Window; beforeBreak: Window; afterBreak: Window;
  fullHistory: { start: string; cagr: number; sharpe: number; maxDrawdown: number; marketBeta: number; turnoverAnnual: number; costDragAnnual: number };
  sameRiskAlpha: { alpha: number | null; pValue: number | null; before: number | null; after: number | null; passed: boolean | null };
  sinceCreation: Since;
};
type Bundle = {
  through: string; commonWindow: [string, string]; breakDate: string; benchmark: string; readThisFirst: string;
  strategies: Row[]; daily: { dates: string[]; series: Record<string, (number | null)[]> };
};

const SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];
const pct = (v: number | null | undefined, d = 1) => (v == null || !Number.isFinite(v) ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);
const abs = (v: number | null | undefined, d = 1) => (v == null || !Number.isFinite(v) ? "—" : `${(v * 100).toFixed(d)}%`);
const plain = (v: number | null | undefined, d = 2) => (v == null || !Number.isFinite(v) ? "—" : v.toFixed(d));
const short = (name: string) => name.split(" — ")[0];

type Line = { label: string; hint?: string; cell: (r: Row) => string };
type Group = { title: string; blurb: string; lines: Line[] };

export function StrategyCompare() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/strategy-comparison.json")
      .then((r) => (r.ok ? (r.json() as Promise<Bundle>) : Promise.reject()))
      .then(setBundle)
      .catch(() => setError(true));
  }, []);

  const chartRows = useMemo(() => {
    if (!bundle) return [];
    return bundle.daily.dates.map((date, i) => {
      const row: Record<string, string | number | null> = { date };
      for (const [key, values] of Object.entries(bundle.daily.series)) row[key] = values[i] == null ? null : Number(values[i]);
      return row;
    });
  }, [bundle]);

  if (error) return <main className="loading-state"><h1>Comparison unavailable</h1><p>Run scripts/build_strategy_comparison_payload_v1.py and refresh.</p></main>;
  if (!bundle) return <main className="loading-state"><h1>Loading comparison…</h1></main>;

  const rows = bundle.strategies;
  const [cs, ce] = bundle.commonWindow;
  const groups: Group[] = [
    {
      title: `Backtest, common window ${cs} to ${ce}`,
      blurb: "The one window all five share, from each strategy's published weekly path after 50 bps costs. Chosen on this sample, so treat as an upper bound.",
      lines: [
        { label: "Annualised return", cell: (r) => pct(r.commonBacktest.cagr) },
        { label: "Sharpe (return ÷ volatility)", cell: (r) => plain(r.commonBacktest.sharpe) },
        { label: "Worst drawdown", cell: (r) => pct(r.commonBacktest.maxDrawdown) },
        { label: "Volatility", cell: (r) => abs(r.commonBacktest.volatility) },
        { label: "Winning weeks", cell: (r) => abs(r.commonBacktest.winRate, 0) },
      ],
    },
    {
      title: `Before and after ${bundle.breakDate}`,
      blurb: "The same backtest split at the start of the 2025 melt-up. Most of every book's headline return sits in the second half.",
      lines: [
        { label: "Annualised return, before", cell: (r) => pct(r.beforeBreak.cagr) },
        { label: "Sharpe, before", cell: (r) => plain(r.beforeBreak.sharpe) },
        { label: "Annualised return, after", cell: (r) => pct(r.afterBreak.cagr) },
        { label: "Sharpe, after", cell: (r) => plain(r.afterBreak.sharpe) },
      ],
    },
    {
      title: "Skill check: return over SPY at the same risk",
      blurb: "Alpha over SPY held at the strategy's own past-only market beta (Step 332). Passing needs p below 0.005 after correcting for ten trials.",
      lines: [
        { label: "Alpha per year, full", cell: (r) => pct(r.sameRiskAlpha.alpha) },
        { label: "p-value", cell: (r) => plain(r.sameRiskAlpha.pValue, 3) },
        { label: "Alpha before the break", cell: (r) => pct(r.sameRiskAlpha.before) },
        { label: "Alpha after the break", cell: (r) => pct(r.sameRiskAlpha.after) },
        { label: "Passes", cell: (r) => (r.sameRiskAlpha.passed == null ? "—" : r.sameRiskAlpha.passed ? "yes" : "no") },
      ],
    },
    {
      title: "Full history and running costs",
      blurb: "Each strategy's own full record. The 60/40 runs from 2005, the stock books from late 2022, so these are not directly comparable.",
      lines: [
        { label: "Starts", cell: (r) => r.fullHistory.start ?? "—" },
        { label: "Annualised return", cell: (r) => pct(r.fullHistory.cagr) },
        { label: "Worst drawdown", cell: (r) => pct(r.fullHistory.maxDrawdown) },
        { label: "Market beta", cell: (r) => plain(r.fullHistory.marketBeta) },
        { label: "Turnover per year", cell: (r) => (r.fullHistory.turnoverAnnual == null ? "—" : `${r.fullHistory.turnoverAnnual.toFixed(1)}x`) },
        { label: "Cost drag per year", cell: (r) => abs(r.fullHistory.costDragAnnual) },
      ],
    },
    {
      title: `Since creation, last book held to ${bundle.through}`,
      blurb: "Every strategy was created between 2026-08-14 and 2026-08-26 on data ending 2026-08-07. This holds the last book each one decided and marks it daily; no rebalancing, costs or financing.",
      lines: [
        { label: "Created", cell: (r) => r.sinceCreation.created ?? "—" },
        { label: "Return", cell: (r) => pct(r.sinceCreation.totalReturn, 2) },
        { label: `${bundle.benchmark}, same days`, cell: (r) => pct(r.sinceCreation.spyReturn, 2) },
        { label: `Ahead of ${bundle.benchmark}`, cell: (r) => pct(r.sinceCreation.excessVsSpy, 2) },
        { label: "Worst drawdown", cell: (r) => pct(r.sinceCreation.maxDrawdown, 2) },
        { label: "Up / down days", cell: (r) => `${r.sinceCreation.upDays} / ${r.sinceCreation.downDays}` },
        { label: "Best day / worst day", cell: (r) => `${pct(r.sinceCreation.bestDay)} / ${pct(r.sinceCreation.worstDay)}` },
        { label: "Biggest contributor", cell: (r) => `${r.sinceCreation.topContributor} ${pct(r.sinceCreation.topContribution, 2)}` },
        { label: "Return without it", cell: (r) => pct(r.sinceCreation.returnWithoutTop, 2) },
        { label: "Holdings · largest", cell: (r) => `${r.sinceCreation.names} · ${r.sinceCreation.largestWeightSymbol} ${(r.sinceCreation.largestWeight * 100).toFixed(0)}%` },
      ],
    },
  ];

  return (
    <main className="dashboard-page forward-standalone">
      <div className="content-frame">
        <nav className="forward-topbar">
          <Link href="/"><ChevronLeft size={15} />Portfolio Optimizer</Link>
          <span>
            <Link href="/metrics">Strategy metrics</Link>
            <Link href="/performance">Performance</Link>
            <Link href="/research">Research status</Link>
          </span>
        </nav>

        <div className="dashboard-content">
          <section className="section-block page-section metrics-view">
            <h2>Compare strategies</h2>
            <p className="muted">Five strategies, no leverage and no short positions. Prices through the {bundle.through} close.</p>

            <div className="callout callout-warning">
              <div><strong>Read this first.</strong><p>{bundle.readThisFirst}</p></div>
            </div>

            <div className="metric-group">
              <h3>Day by day since the last decided books ({bundle.daily.dates[0]} onward)</h3>
              <div className="replay-legend">
                {rows.map((row, index) => (
                  <span key={row.id}><i style={{ background: SERIES[index % SERIES.length] }} />{short(row.name)} {pct(row.sinceCreation.totalReturn, 2)}</span>
                ))}
                <span><i className="dashed" style={{ borderTopStyle: "dotted" }} />{bundle.benchmark} {pct(rows[0]?.sinceCreation.spyReturn, 2)}</span>
              </div>
              <div className="replay-chart" role="img" aria-label={`Cumulative daily return of each strategy's last book from ${bundle.daily.dates[0]} to ${bundle.through}, against ${bundle.benchmark}`}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartRows} margin={{ top: 8, right: 16, left: 4, bottom: 4 }}>
                    <CartesianGrid vertical={false} stroke="#292b37" />
                    <XAxis dataKey="date" tickFormatter={(value) => String(value).slice(5)} tick={{ fontSize: 10, fill: "#8b8d9b" }} minTickGap={24} />
                    <YAxis tickFormatter={(value) => pct(Number(value), 0)} tick={{ fontSize: 10, fill: "#8b8d9b" }} width={52} />
                    <Tooltip
                      contentStyle={{ background: "rgba(19,20,27,.97)", border: "1px solid #393c4b", borderRadius: 10 }}
                      labelStyle={{ color: "#aaaab4" }}
                      formatter={(value, key) => [pct(Number(value), 2), key === bundle.benchmark ? bundle.benchmark : short(rows.find((r) => r.id === key)?.name ?? String(key))]}
                    />
                    <Line dataKey={bundle.benchmark} stroke="#8b8d9b" strokeWidth={1.5} strokeDasharray="2 3" dot={false} isAnimationActive={false} />
                    {rows.map((row, index) => (
                      <Line key={row.id} dataKey={row.id} stroke={SERIES[index % SERIES.length]} strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            {groups.map((group) => (
              <div key={group.title} className="metric-group">
                <h3>{group.title}</h3>
                <p className="muted">{group.blurb}</p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>metric</th>
                        {rows.map((r) => <th key={r.id}><span className="metric-col">{short(r.name)}</span></th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {group.lines.map((line) => (
                        <tr key={line.label}>
                          <td>{line.label}</td>
                          {rows.map((r) => <td key={r.id} className="mono">{line.cell(r)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </section>
        </div>
      </div>
    </main>
  );
}
