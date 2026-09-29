"use client";

import { useEffect, useMemo, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, LineChart as LineChartIcon } from "lucide-react";

type ReplayDay = { date: string; nav: number; pnl: number; ret: number };
type ReplayStrategy = {
  id: string;
  label: string;
  start: string;
  end: string;
  finalValue: number;
  total_pnl: number;
  total_return: number;
  up_days: number;
  days: number;
  best_day: number;
  worst_day: number;
  max_drawdown: number;
  final_value: number;
  daily: ReplayDay[];
};
type ReplayGroup = {
  id: string;
  title: string;
  start: string;
  strategies: ReplayStrategy[];
  benchmarks: Record<string, { date: string; nav: number }[]>;
};
type ReplayPayload = {
  generatedAtUtc: string;
  through: string;
  notional: number;
  whatThisIs: string;
  whatThisIsNot: string;
  method: string;
  groups: ReplayGroup[];
};

// Fixed order, assigned by position in the group so a line keeps its colour.
const SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9"];
const BENCHMARK_STYLE: Record<string, string> = { SPY: "2 4", QQQ: "7 4" };

const money = (value: number) => `${value < 0 ? "-" : ""}$${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const signedMoney = (value: number) => `${value >= 0 ? "+" : "-"}$${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const pct = (value: number, digits = 2) => `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;

export function PaperReplay() {
  const [payload, setPayload] = useState<ReplayPayload | null>(null);
  const [failed, setFailed] = useState(false);
  const [groupId, setGroupId] = useState<string | null>(null);
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    fetch("/paper-replay.json")
      .then((response) => {
        if (!response.ok) throw new Error("missing");
        return response.json() as Promise<ReplayPayload>;
      })
      .then(setPayload)
      .catch(() => setFailed(true));
  }, []);

  const group = payload?.groups.find((item) => item.id === groupId) ?? payload?.groups[0] ?? null;
  const selected = group?.strategies.find((row) => row.id === focus) ?? group?.strategies[0] ?? null;

  const chartRows = useMemo(() => {
    if (!group) return [];
    const byDate = new Map<string, Record<string, number | string>>();
    const put = (date: string, key: string, nav: number) => {
      const row = byDate.get(date) ?? { date };
      row[key] = nav;
      byDate.set(date, row);
    };
    group.strategies.forEach((row) => row.daily.forEach((day) => put(day.date, row.id, day.nav)));
    Object.entries(group.benchmarks).forEach(([symbol, series]) => series.forEach((day) => put(day.date, symbol, day.nav)));
    return [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date)));
  }, [group]);

  if (failed) return <article className="panel"><span className="section-kicker">WHAT-IF REPLAY</span><h2>Replay unavailable</h2><p>Run <code>scripts/build_paper_replay_v1.py</code> and refresh.</p></article>;
  if (!payload || !group || !selected) return <article className="panel"><span className="section-kicker">WHAT-IF REPLAY</span><h2>Loading the replay&hellip;</h2></article>;

  const benchmarkFinal = Object.fromEntries(Object.entries(group.benchmarks).map(([symbol, series]) => [symbol, series[series.length - 1]?.nav ?? payload.notional]));
  const recentDays = [...selected.daily].slice(1).reverse();

  return (
    <>
      <article className="panel">
        <span className="section-kicker">WHAT-IF REPLAY</span>
        <h2><LineChartIcon size={18} /> What {money(payload.notional)} in each strategy would be worth on {payload.through}</h2>
        <p>{payload.whatThisIs}</p>
        <p className="forward-attribution"><AlertTriangle size={14} /><span>{payload.whatThisIsNot}</span></p>

        <div className="replay-groups" role="tablist" aria-label="Strategy group">
          {payload.groups.map((item) => (
            <button key={item.id} type="button" role="tab" aria-selected={item.id === group.id}
              className={item.id === group.id ? "active" : ""}
              onClick={() => { setGroupId(item.id); setFocus(null); }}>
              {item.title} <small>from {item.start}</small>
            </button>
          ))}
        </div>

        <div className="replay-legend">
          {group.strategies.map((row, index) => (
            <span key={row.id}><i style={{ background: SERIES[index % SERIES.length] }} />{row.label} {money(row.final_value)}</span>
          ))}
          {Object.keys(group.benchmarks).map((symbol) => (
            <span key={symbol}><i className="dashed" style={{ borderTopStyle: symbol === "SPY" ? "dotted" : "dashed" }} />{symbol} {money(benchmarkFinal[symbol])}</span>
          ))}
        </div>
        <div className="replay-chart" role="img" aria-label={`Value of ${money(payload.notional)} in each strategy from ${group.start} to ${payload.through}, against SPY and QQQ`}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartRows} margin={{ top: 8, right: 16, left: 4, bottom: 4 }}>
              <CartesianGrid vertical={false} stroke="#292b37" />
              <XAxis dataKey="date" tickFormatter={(value) => String(value).slice(5)} tick={{ fontSize: 10, fill: "#8b8d9b" }} minTickGap={24} />
              <YAxis domain={["auto", "auto"]} tickFormatter={(value) => money(Number(value))} tick={{ fontSize: 10, fill: "#8b8d9b" }} width={64} />
              <Tooltip
                contentStyle={{ background: "rgba(19,20,27,.97)", border: "1px solid #393c4b", borderRadius: 10 }}
                labelStyle={{ color: "#aaaab4" }}
                formatter={(value, key) => [money(Number(value)), group.strategies.find((row) => row.id === key)?.label ?? String(key)]}
              />
              {Object.keys(group.benchmarks).map((symbol) => (
                <Line key={symbol} dataKey={symbol} stroke="#8b8d9b" strokeWidth={1.5} strokeDasharray={BENCHMARK_STYLE[symbol]} dot={false} isAnimationActive={false} />
              ))}
              {group.strategies.map((row, index) => (
                <Line key={row.id} dataKey={row.id} stroke={SERIES[index % SERIES.length]} strokeWidth={row.id === selected.id ? 2.6 : 1.6}
                  dot={false} isAnimationActive={false} connectNulls />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>

        <table className="holdings-table forward-table">
          <thead>
            <tr><th>Strategy</th><th>Value now</th><th>Profit</th><th>Up days</th><th>Best day</th><th>Worst day</th><th>Deepest dip</th></tr>
          </thead>
          <tbody>
            {group.strategies.map((row) => (
              <tr key={row.id} className={row.id === selected.id ? "selected" : ""} onClick={() => setFocus(row.id)} style={{ cursor: "pointer" }}>
                <td>{row.label}</td>
                <td>{money(row.final_value)}</td>
                <td className={row.total_pnl >= 0 ? "gain" : "loss"}>{signedMoney(row.total_pnl)} <small>{pct(row.total_return)}</small></td>
                <td>{row.up_days}/{row.days}</td>
                <td className="gain">{pct(row.best_day)}</td>
                <td className="loss">{pct(row.worst_day)}</td>
                <td className="loss">{pct(row.max_drawdown)}</td>
              </tr>
            ))}
            <tr className="forward-benchmark-row"><td colSpan={7}>Same days — {Object.entries(benchmarkFinal).map(([symbol, nav]) => `${symbol} ${money(nav)} (${pct(nav / payload.notional - 1)})`).join(" · ")}</td></tr>
          </tbody>
        </table>
      </article>

      <article className="panel">
        <span className="section-kicker">DAILY WINNINGS</span>
        <h3>{selected.label}: every trading day since {selected.start}</h3>
        <p className="muted">Click a strategy in the table above to switch. Newest first.</p>
        <div className="replay-daily">
          <table className="holdings-table forward-table">
            <thead><tr><th>Day</th><th>Made or lost</th><th>Return</th><th>Account value</th></tr></thead>
            <tbody>
              {recentDays.map((day) => (
                <tr key={day.date}>
                  <td>{day.date}</td>
                  <td className={day.pnl >= 0 ? "gain" : "loss"}>{signedMoney(day.pnl)}</td>
                  <td className={day.ret >= 0 ? "gain" : "loss"}>{pct(day.ret)}</td>
                  <td>{money(day.nav)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </article>

      <article className="panel">
        <span className="section-kicker">HOW IT IS COMPUTED</span>
        <p>{payload.method}</p>
        <p className="muted">Generated {payload.generatedAtUtc.slice(0, 16).replace("T", " ")} UTC. No order has been placed; nothing on this page promotes a strategy.</p>
      </article>
    </>
  );
}
