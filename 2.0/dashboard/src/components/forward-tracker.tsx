"use client";

import { useEffect, useState, type MouseEvent } from "react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, CalendarClock, Database, Flame, Timer } from "lucide-react";

export type ForwardObservation = {
  decisionDate: string | null;
  realizationDate: string | null;
  netReturn: number | null;
  turnover: number | null;
};

export type ForwardProtocol = {
  protocol: string;
  observedWeeks: number;
  requiredWeeks: number;
  latestRealization: string | null;
  executionEnabled: boolean;
  observations: ForwardObservation[];
};

export type HeldBook = {
  id: string;
  label: string;
  bookAsOf: string;
  namesPriced: number;
  namesInBook: number;
  grossExposure: number;
  cumulativeReturn: number;
  weeks: { weekEnding: string; netReturn: number; cumulative: number }[];
  energyWeight: number;
  energyContribution: number;
  exEnergyContribution: number;
};

export type ForwardTrackerPayload = {
  generatedAtUtc: string;
  dataThrough: string;
  priorDataThrough: string;
  backtestsEndAt: string;
  issuersPricedNewWeek: Record<string, number>;
  panelReconciliation: { compared_cells: number; cells_over_10bps: number; median_absolute_return_gap: number | null };
  protocols: ForwardProtocol[];
  registry: { firstEligibleRealization: string; trackedStrategies: string[] };
  heldBooks: {
    weeks: string[];
    whatThisIs: string;
    whatThisIsNot: string;
    costTreatment: string;
    strategies: HeldBook[];
    benchmarks: Record<string, number>;
    attributionNote: string;
    energySymbols: string[];
  };
  liveTradingEnabled: boolean;
};

const pct = (value: number, digits = 2) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
const protocolLabel = (id: string) => id.replace(/_/g, " ").replace(/ v(\d)$/, " v$1");

export function ForwardTracker({ positionSpotlight }: { positionSpotlight: (event: MouseEvent<HTMLElement>) => void }) {
  const [payload, setPayload] = useState<ForwardTrackerPayload | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    fetch("/forward-tracker.json")
      .then((response) => {
        if (!response.ok) throw new Error("missing");
        return response.json() as Promise<ForwardTrackerPayload>;
      })
      .then(setPayload)
      .catch(() => setFailed(true));
  }, []);

  if (failed) return <article className="panel"><span className="section-kicker">FORWARD EVIDENCE</span><h2>Forward tracker unavailable</h2><p>Rebuild <code>forward-tracker.json</code> and refresh.</p></article>;
  if (!payload) return <article className="panel"><span className="section-kicker">FORWARD EVIDENCE</span><h2>Loading the forward record&hellip;</h2></article>;

  const totalObserved = payload.protocols.reduce((sum, row) => sum + row.observedWeeks, 0);
  const heldChart = payload.heldBooks.strategies.map((row) => ({
    name: row.label,
    total: row.cumulativeReturn,
    energy: row.energyContribution,
    exEnergy: row.exEnergyContribution,
  }));

  return (
    <div className="forward-page">
      <article className="panel guardrail-hero spotlight-surface" onMouseMove={positionSpotlight}>
        <div>
          <span className="section-kicker">UNTOUCHED FORWARD EVIDENCE</span>
          <h2>{totalObserved} forward week{totalObserved === 1 ? "" : "s"} exist across every frozen protocol</h2>
          <p>
            Prices now run through <strong>{payload.dataThrough}</strong>, but every dashboard strategy&rsquo;s
            weekly record still stops at <strong>{payload.backtestsEndAt}</strong>, because that is where its
            backtest stops rather than where the data stops. Advancing a strategy means re-running its selection
            pipeline on new point-in-time filings, which re-opens the selection this project exists to guard
            against. Nothing on this page promotes anything and no order has ever been placed.
          </p>
        </div>
        <span className="guardrail-status"><i />RESEARCH ONLY</span>
      </article>

      <section className="forward-clock-grid">
        {payload.protocols.map((row) => {
          const share = row.requiredWeeks > 0 ? row.observedWeeks / row.requiredWeeks : 0;
          return (
            <article key={row.protocol} className="panel forward-clock spotlight-surface" onMouseMove={positionSpotlight}>
              <header>
                <Timer size={15} />
                <h3>{protocolLabel(row.protocol)}</h3>
              </header>
              <strong>{row.observedWeeks}<small> / {row.requiredWeeks} weeks</small></strong>
              <div className="forward-clock-bar"><i style={{ width: `${Math.max(share * 100, row.observedWeeks > 0 ? 1.5 : 0)}%` }} /></div>
              {row.observations.length > 0 ? (
                <ul className="forward-observations">
                  {row.observations.map((observation) => (
                    <li key={observation.realizationDate}>
                      <span>{observation.realizationDate}</span>
                      <b className={(observation.netReturn ?? 0) >= 0 ? "gain" : "loss"}>{pct(observation.netReturn ?? 0, 3)}</b>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="forward-empty">No eligible realization has been recorded. The clock reads zero and that is the honest number.</p>
              )}
            </article>
          );
        })}
      </section>

      <article className="panel forward-registry spotlight-surface" onMouseMove={positionSpotlight}>
        <span className="section-kicker">PRE-REGISTERED SCORER</span>
        <h3><CalendarClock size={15} /> The prediction registry opens {payload.registry.firstEligibleRealization}</h3>
        <p>
          Six strategies are scored each completed week against four thousand random portfolios matched on
          holding count and volatility percentile. The thresholds separating skill, selection and an unmeasured
          common exposure were frozen before any forward data existed and cannot be revised. Until the first
          eligible week closes, this scorer has produced rehearsals only.
        </p>
        <ul>{payload.registry.trackedStrategies.map((id) => <li key={id}><code>{id}</code></li>)}</ul>
      </article>

      <article className="panel forward-held spotlight-surface" onMouseMove={positionSpotlight}>
        <span className="section-kicker">HELD BOOK, MARKED TO MARKET</span>
        <h3>What the last decided books did over {payload.heldBooks.weeks.length} newly closed weeks</h3>
        <p className="forward-caution">
          <AlertTriangle size={14} />
          <span>{payload.heldBooks.whatThisIsNot}</span>
        </p>
        <div className="forward-held-chart">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={heldChart} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
              <CartesianGrid vertical={false} stroke="#292b37" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#8b8d9b" }} interval={0} angle={-18} textAnchor="end" height={64} />
              <YAxis tickFormatter={(value) => `${(Number(value) * 100).toFixed(0)}%`} tick={{ fontSize: 10, fill: "#8b8d9b" }} width={44} />
              <Tooltip
                contentStyle={{ background: "rgba(19,20,27,.97)", border: "1px solid #393c4b", borderRadius: 10 }}
                formatter={(value, name) => [pct(Number(value)), name === "total" ? "Three-week return" : name]}
                labelStyle={{ color: "#aaaab4" }}
              />
              <Bar dataKey="total" radius={[5, 5, 0, 0]} isAnimationActive={false}>
                {heldChart.map((row) => <Cell key={row.name} fill={row.total >= 0 ? "#56d98b" : "#ff7d8d"} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <table className="holdings-table forward-table">
          <thead>
            <tr><th>Book</th><th>Held return</th><th>Energy weight</th><th>From energy</th><th>Everything else</th></tr>
          </thead>
          <tbody>
            {payload.heldBooks.strategies.map((row) => (
              <tr key={row.id}>
                <td>{row.label}<small> · {row.namesPriced}/{row.namesInBook} priced</small></td>
                <td className={row.cumulativeReturn >= 0 ? "gain" : "loss"}>{pct(row.cumulativeReturn)}</td>
                <td>{(row.energyWeight * 100).toFixed(1)}%</td>
                <td className={row.energyContribution >= 0 ? "gain" : "loss"}>{pct(row.energyContribution)}</td>
                <td className={row.exEnergyContribution >= 0 ? "gain" : "loss"}>{pct(row.exEnergyContribution)}</td>
              </tr>
            ))}
            <tr className="forward-benchmark-row"><td colSpan={5}>Same three weeks — {Object.entries(payload.heldBooks.benchmarks).map(([key, value]) => `${key.replace(/_/g, " ")} ${pct(value)}`).join(" · ")}</td></tr>
          </tbody>
        </table>
        <p className="forward-attribution">
          <Flame size={14} />
          <span>
            Energy supplied most or all of every positive result here. Two books are negative once energy is
            removed. Five of the six hold the same energy instruments, which is the correlated-bet problem this
            project has measured before, not five independent confirmations. The energy grouping was made after
            seeing the result, so treat it as a diagnostic rather than a test.
          </span>
        </p>
      </article>

      <article className="panel forward-data spotlight-surface" onMouseMove={positionSpotlight}>
        <span className="section-kicker">DATA CURRENCY</span>
        <h3><Database size={15} /> Panel extended from {payload.priorDataThrough} to {payload.dataThrough}</h3>
        <p>
          {Object.entries(payload.issuersPricedNewWeek).map(([week, count]) => `${count.toLocaleString()} issuers priced in the week ending ${week}`).join("; ")}.
          The extension was reconciled against the sealed panel on weekly returns rather than price levels,
          because every issuer series is rebased to 1.0 at its first observation. Of{" "}
          {payload.panelReconciliation.compared_cells.toLocaleString()} overlapping cells,{" "}
          {payload.panelReconciliation.cells_over_10bps.toLocaleString()} differ by more than ten basis points
          and the median difference is exactly zero.
        </p>
      </article>
    </div>
  );
}
