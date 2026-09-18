"use client";

import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronLeft } from "lucide-react";

type Metrics = Record<string, number | string | null>;
type Bundle = {
  asOf: string;
  notional: number;
  metrics: Record<string, Metrics>;
  glossary: Record<string, string>;
  note: string;
  readThisFirst: string;
};

const shortName = (id: string) =>
  id
    .replace(/^sec-|^candidate-/, "")
    .replace(/-v1$/, "")
    .replace(/-/g, " ");

const pct = (v: number) => `${(v * 100).toFixed(2)}%`;
const num = (v: number, d = 2) => v.toFixed(d);
const money = (v: number) =>
  `£${v.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

// Grouped so a reader meets them in the order they should think about them:
// what it made, what it cost to hold, how it got there, then what it actually was.
const GROUPS: { title: string; blurb: string; keys: string[] }[] = [
  {
    title: "What it made",
    blurb: "The headline numbers. Easy to read, easy to be misled by on their own.",
    keys: ["totalReturn", "cagr", "pnlOnNotional"],
  },
  {
    title: "What it cost to hold",
    blurb: "The part that decides whether you could actually have stayed invested.",
    keys: ["maxDrawdown", "longestDrawdownWeeks", "timeUnderWater", "annualisedVolatility"],
  },
  {
    title: "Reward per unit of pain",
    blurb: "Return divided by some measure of risk. Three views because each hides something.",
    keys: ["sharpe", "sortino", "calmar"],
  },
  {
    title: "How it got there",
    blurb: "The texture of the returns. Frequent small wins and rare large ones look identical in a CAGR.",
    keys: ["winRate", "profitFactor", "bestWeek", "worstWeek", "turnoverAnnual", "costDragAnnual"],
  },
  {
    title: "What it actually was",
    blurb:
      "The two rows that decide whether any of the above came from skill. A long-only book with a beta near one is renting the market.",
    keys: ["marketBeta", "marketR2", "alphaAnnual"],
  },
];

const FORMAT: Record<string, (v: number) => string> = {
  totalReturn: pct, cagr: pct, maxDrawdown: pct, timeUnderWater: pct,
  annualisedVolatility: pct, winRate: pct, bestWeek: pct, worstWeek: pct,
  costDragAnnual: pct, alphaAnnual: pct,
  pnlOnNotional: money,
  sharpe: (v) => num(v, 3), sortino: (v) => num(v, 3), calmar: (v) => num(v, 2),
  profitFactor: (v) => num(v, 2), marketBeta: (v) => num(v, 2), marketR2: (v) => num(v, 2),
  turnoverAnnual: (v) => `${num(v, 1)}x`,
  longestDrawdownWeeks: (v) => `${v.toFixed(0)}w`,
};

const LABEL: Record<string, string> = {
  totalReturn: "Total return", cagr: "Annualised return", pnlOnNotional: "Profit on £10,000",
  maxDrawdown: "Worst drawdown", longestDrawdownWeeks: "Longest drawdown",
  timeUnderWater: "Time under water", annualisedVolatility: "Volatility",
  sharpe: "Sharpe", sortino: "Sortino", calmar: "Calmar",
  winRate: "Win rate", profitFactor: "Profit factor", bestWeek: "Best week",
  worstWeek: "Worst week", turnoverAnnual: "Turnover / yr", costDragAnnual: "Cost drag / yr",
  marketBeta: "Market beta", marketR2: "Explained by market", alphaAnnual: "Alpha / yr",
};

export function StrategyMetrics() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState(false);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    fetch("/strategy-metrics.json")
      .then((r) => (r.ok ? (r.json() as Promise<Bundle>) : Promise.reject()))
      .then(setBundle)
      .catch(() => setError(true));
  }, []);

  if (error) return <main className="loading-state"><h1>Metrics unavailable</h1><p>Run scripts/build_dashboard_metrics_v1.py and refresh.</p></main>;
  if (!bundle) return <main className="loading-state"><h1>Loading metrics…</h1></main>;

  const names = Object.keys(bundle.metrics);

  return (
    <main className="dashboard-page forward-standalone">
      <div className="content-frame">
        <nav className="forward-topbar">
          <Link href="/"><ChevronLeft size={15} />Portfolio Optimizer</Link>
          <span>
            <Link href="/performance">Performance</Link>
            <Link href="/research">Research status</Link>
            <Link href="/guardrails">Guardrails</Link>
          </span>
        </nav>

        <div className="dashboard-content">
          <section className="section-block page-section metrics-view">
            <h2>Strategy metrics</h2>
            <p className="muted">Records through {bundle.asOf}. Click any metric name to see what it means.</p>

            <div className="callout callout-warning">
              <div><strong>Read this first.</strong><p>{bundle.readThisFirst}</p></div>
            </div>

            {GROUPS.map((group) => (
              <div key={group.title} className="metric-group">
                <h3>{group.title}</h3>
                <p className="muted">{group.blurb}</p>
                <div className="table-scroll">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>metric</th>
                        {names.map((n) => (
                          <th key={n}>
                            <span className="metric-col">{shortName(n)}</span>
                            <small>{bundle.metrics[n].weeks}w to {String(bundle.metrics[n].end)}</small>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {group.keys.map((key) => (
                        <Fragment key={key}>
                          <tr>
                            <td>
                              <button
                                type="button"
                                className="metric-name"
                                onClick={() => setOpen(open === key ? null : key)}
                                aria-expanded={open === key}
                              >
                                {LABEL[key] ?? key}
                                <span className="metric-hint">{open === key ? "−" : "?"}</span>
                              </button>
                            </td>
                            {names.map((n) => {
                              const raw = bundle.metrics[n][key];
                              const v = typeof raw === "number" ? raw : NaN;
                              const fmt = FORMAT[key] ?? ((x: number) => num(x));
                              return (
                                <td key={n} className="mono">
                                  {Number.isFinite(v) ? fmt(v) : "—"}
                                </td>
                              );
                            })}
                          </tr>
                          {open === key && (
                            <tr className="metric-explainer">
                              <td colSpan={names.length + 1}>{bundle.glossary[key]}</td>
                            </tr>
                          )}
                        </Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}

            <div className="metrics-footnote">
              <p className="muted">{bundle.note}</p>
              <p className="muted">
                {bundle.glossary.dateConvention} Detected per series:{" "}
                {names.map((n, i) => (
                  <span key={n}>
                    {i > 0 ? ", " : ""}
                    {shortName(n)} <span className="mono">{String(bundle.metrics[n].dateConvention)}</span>
                  </span>
                ))}
                .
              </p>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
