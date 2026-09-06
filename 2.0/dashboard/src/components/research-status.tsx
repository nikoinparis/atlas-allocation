"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, Layers, XCircle } from "lucide-react";

type WeeklyReturn = { week: string | null; netReturn: number };

type Clock = {
  protocol: string;
  observedWeeks: number;
  requiredWeeks: number;
  savedDecisions: number;
  promotionAuthorized: boolean;
  weekly: WeeklyReturn[];
  cumulativeReturn: number | null;
};

type Pending = { protocol: string; firstDecision: string; purpose: string; modifies: string };
type Closed = { name: string; verdict: string; step: number };

type ResearchStatus = {
  generatedAtUtc: string;
  liveTradingEnabled: boolean;
  anyStrategyPromoted: boolean;
  headline: {
    closedFamilies: number;
    clocksRunning: number;
    clocksPending: number;
    totalUntouchedWeeks: number;
    weeksRequiredEach: number;
  };
  breadth: {
    effectiveIndependentStrategies: number;
    effectiveBetsPerYear: number;
    betsNeededForInformationRatio025: number;
    measuredIn: string;
    plainEnglish: string;
  };
  clocks: Clock[];
  pending: Pending[];
  closedFamilies: Closed[];
  readMe: string;
};

const percent = (value: number | null | undefined, digits = 2) =>
  value === null || value === undefined ? "—" : `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;

const readable = (protocol: string) =>
  protocol.replace(/_v\d+$/, "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function ResearchStatus() {
  const [data, setData] = useState<ResearchStatus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/research-status.json")
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then(setData)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <section className="section-block page-section"><p>Research status is unavailable.</p></section>;
  if (!data) return <section className="section-block page-section"><p>Loading research status…</p></section>;

  return (
    <section className="section-block page-section research-status">
      <header className="section-heading">
        <h2>Research status</h2>
        <p>
          What the research programme is actually doing, read from the evidence files rather than
          summarised by hand. The strategy pages show what backtests produced. This page shows how
          much of it has survived contact with data it was not selected on.
        </p>
      </header>

      <div className="stat-row">
        <div className="stat-card">
          <span className="stat-label"><Clock size={16} /> Untouched weeks recorded</span>
          <span className="stat-value">{data.headline.totalUntouchedWeeks}</span>
          <span className="stat-note">across {data.headline.clocksRunning} running clocks, {data.headline.weeksRequiredEach} required each</span>
        </div>
        <div className="stat-card">
          <span className="stat-label"><Layers size={16} /> Clocks starting</span>
          <span className="stat-value">{data.headline.clocksPending}</span>
          <span className="stat-note">frozen and waiting for their first eligible decision</span>
        </div>
        <div className="stat-card">
          <span className="stat-label"><XCircle size={16} /> Candidate families closed</span>
          <span className="stat-value">{data.headline.closedFamilies}</span>
          <span className="stat-note">tested and rejected, with the reason recorded</span>
        </div>
        <div className="stat-card">
          <span className="stat-label"><CheckCircle2 size={16} /> Strategies promoted</span>
          <span className="stat-value">0</span>
          <span className="stat-note">nothing here has ever traded</span>
        </div>
      </div>

      <div className="callout">
        <AlertTriangle size={18} />
        <div>
          <strong>The binding constraint is breadth, not return.</strong>
          <p>{data.breadth.plainEnglish}</p>
          <p>
            Measured in {data.breadth.measuredIn}: {data.breadth.effectiveIndependentStrategies} effective
            independent strategies, {data.breadth.effectiveBetsPerYear} independent bets a year, against
            roughly {data.breadth.betsNeededForInformationRatio025} needed for an information ratio of 0.25.
          </p>
        </div>
      </div>

      <h3>Clocks running</h3>
      <table className="data-table">
        <thead>
          <tr><th>Protocol</th><th>Progress</th><th>Weekly returns</th><th>Cumulative</th></tr>
        </thead>
        <tbody>
          {data.clocks.filter((c) => c.observedWeeks > 0).map((clock) => (
            <tr key={clock.protocol}>
              <td>{readable(clock.protocol)}</td>
              <td>{clock.observedWeeks} / {clock.requiredWeeks}</td>
              <td className="mono">{clock.weekly.map((w) => percent(w.netReturn)).join("  ")}</td>
              <td className="mono">{percent(clock.cumulativeReturn)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Clocks starting</h3>
      <table className="data-table">
        <thead><tr><th>Protocol</th><th>First decision</th><th>What it is for</th></tr></thead>
        <tbody>
          {data.pending.map((row) => (
            <tr key={row.protocol}>
              <td>{readable(row.protocol)}</td>
              <td className="mono">{row.firstDecision}</td>
              <td>{row.purpose.slice(0, 220)}{row.purpose.length > 220 ? "…" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Closed without promotion</h3>
      <p className="section-note">
        Each of these was proposed, built, tested and rejected. Preserving them is the point: a rejected
        candidate is exactly as much of a result as a passing one, and it stops the same idea being
        proposed again in six months.
      </p>
      <table className="data-table">
        <thead><tr><th>Family</th><th>Why it closed</th><th>Step</th></tr></thead>
        <tbody>
          {data.closedFamilies.map((row) => (
            <tr key={`${row.name}-${row.step}`}>
              <td>{row.name}</td><td>{row.verdict}</td><td className="mono">{row.step}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="section-note">{data.readMe}</p>
      <p className="section-note">Generated {new Date(data.generatedAtUtc).toISOString().slice(0, 19)}Z.</p>
    </section>
  );
}
