"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AlertTriangle, Activity, BarChart3, Info, Landmark, ShieldAlert, SlidersHorizontal, TrendingDown } from "lucide-react";

/* ------------------------------------------------------------------ types */

export type SurvivalStat = {
  observations: number;
  total_return: number;
  cagr: number;
  sharpe: number;
  max_drawdown: number;
};

export type Histogram = { edges: number[]; counts: number[] };

export type CurveBands = {
  week: number[];
  p05: number[];
  p25: number[];
  p50: number[];
  p75: number[];
  p95: number[];
};

export type BlockSummary = {
  simulations: number;
  median_return: number;
  p05_return: number;
  p95_return: number;
  probability_of_profit: number;
  probability_of_50pct_capital_loss: number;
  probability_drawdown_over_30pct: number;
  median_max_drawdown: number;
  p05_max_drawdown: number;
  return_histogram?: Histogram;
  drawdown_histogram?: Histogram;
  curve_bands?: CurveBands;
  sample_curves?: number[][];
  quartiles?: {
    p25_return: number;
    p75_return: number;
    p01_return: number;
    p99_return: number;
    worst_return: number;
    best_return: number;
    mean_return: number;
    probability_of_20pct_capital_loss: number;
    probability_of_beating_10pct: number;
  };
};

export type SurvivalTest = {
  id: string;
  label: string;
  passed: boolean;
  value: number;
  threshold: number;
  points: number;
  status: string;
};

export type WeeklyReturn = { date: string; net: number; wealth: number; drawdown: number };

export type SurvivalStrategy = {
  id: string;
  name: string;
  short_name: string;
  as_of: string;
  observations: number;
  start: string;
  end: string;
  historical_resilience_score: number;
  historical_grade: string;
  live_verdict: string;
  plain_english_verdict: string;
  binding_failures: string[];
  research_evidence_gate: { status: string; boolean_checks: number; checks_passed: number };
  historical: { full: SurvivalStat; trailing_52w: SurvivalStat; rolling_52w: { worst_return: number; windows: number } };
  weekly_returns?: WeeklyReturn[];
  stress_tests: Record<string, SurvivalStat>;
  monte_carlo: { method: string; block_summaries: Record<string, BlockSummary>; primary_block_weeks: number };
  concentration: {
    maximum_single_position_weight: number;
    average_largest_position_weight: number;
    average_borrowed_exposure: number;
  };
  test_results: SurvivalTest[];
  forward_evidence: { observed_weeks: number; required_weeks: number; status: string; passed: boolean };
  readiness: { missing_real_world_inputs: string[] };
};

export type SurvivalComparisonRow = {
  id: string;
  name: string;
  score: number;
  grade: string;
  recent_cagr: number;
  worst_rolling_year: number;
  monte_profit_probability: number;
  monte_30pct_drawdown_probability: number;
  maximum_concentration: number;
  forward_weeks: number;
  live_verdict: string;
};

export type SurvivalBundlePayload = {
  comparison: SurvivalComparisonRow[];
  strategies: SurvivalStrategy[];
  methodology: {
    selection_warning: string;
    monte_carlo: { simulations: number; block_lengths: number[]; primary_block_length: number; horizon_weeks: number; seed: number };
    stress_tests: Record<string, number>;
  };
  known_missing_real_world_inputs: string[];
};

export type CapGate = {
  cap: number;
  before_p95: number; after_p95: number;
  before_max: number; after_max: number;
  before_passes: boolean; after_passes: boolean;
};

export type ExposurePath = { weeks: number; cagr: number; sharpe: number; max_drawdown: number; ending_value_10000: number };

export type CapsStrategy = {
  id: string; short_name: string; weeks: number;
  used_leverage: boolean; max_original_gross: number;
  gates: Record<string, CapGate>;
  all_caps_pass_after: boolean;
  cash_released: { median: number; p95: number; max: number };
  average_invested_after: number;
  average_names_capped: number;
  exposure?: {
    native_gross: number;
    uses_financing: boolean;
    benefits_heavily_from_financing: boolean;
    financing_uplift_cagr: number;
    paths: Record<string, ExposurePath>;
    default_path: string;
    note: string;
  };
};

export type CapsPayload = {
  caps: Record<string, number>;
  strategies: CapsStrategy[];
  every_strategy_passes_after_caps: boolean;
  return_impact_note: string;
  remaining_blocker: string;
};

const CAP_LABELS: Record<string, string> = {
  max_single_issuer_weight: "Largest single company",
  max_single_exchange_traded_weight: "Largest single fund",
  max_total_exchange_traded_weight: "Total fund exposure",
  max_look_through_sector_weight: "Sector after ETF look-through",
};

/* ---------------------------------------------------------------- helpers */

const pct = (value: number, digits = 1) => `${value >= 0 ? "" : "−"}${Math.abs(value * 100).toFixed(digits)}%`;
const plainPct = (value: number, digits = 1) => `${(value * 100).toFixed(digits)}%`;
const money = (value: number) => `$${Math.round(value).toLocaleString()}`;

const STRESS_LABELS: Record<string, string> = {
  double_cost: "Doubled trading cost",
  financing_plus_300bps: "Financing +300 bps",
  signal_decay: "25% signal decay",
  one_off_20pct_crash: "One −20% crash week",
};

type TabName = "montecarlo" | "history" | "stress" | "gates" | "design";

const TABS: { id: TabName; label: string; icon: typeof Activity }[] = [
  { id: "montecarlo", label: "Monte Carlo", icon: Activity },
  { id: "history", label: "Realized history", icon: TrendingDown },
  { id: "stress", label: "Stress battery", icon: ShieldAlert },
  { id: "gates", label: "Score gates", icon: BarChart3 },
  { id: "design", label: "Design gate", icon: SlidersHorizontal },
];

/* ------------------------------------------------------------- the module */

export function SurvivalLab({
  bundle,
  selectedId,
  onSelect,
  positionSpotlight,
}: {
  bundle: SurvivalBundlePayload;
  selectedId: string;
  onSelect: (id: string) => void;
  positionSpotlight?: (event: React.MouseEvent<HTMLElement>) => void;
}) {
  const [tab, setTab] = useState<TabName>("montecarlo");
  const [blockKey, setBlockKey] = useState<string>(String(bundle.methodology.monte_carlo.primary_block_length));
  const [showPaths, setShowPaths] = useState(true);
  const [capital, setCapital] = useState(10000);
  const [caps, setCaps] = useState<CapsPayload | null>(null);
  const [financed, setFinanced] = useState(false);

  useEffect(() => {
    let live = true;
    fetch("/concentration-caps.json")
      .then((response) => (response.ok ? (response.json() as Promise<CapsPayload>) : null))
      .then((payload) => { if (live && payload) setCaps(payload); })
      .catch(() => undefined);
    return () => { live = false; };
  }, []);

  const survival = useMemo(
    () => bundle.strategies.find((item) => item.id === selectedId) ?? bundle.strategies[0],
    [bundle.strategies, selectedId],
  );

  const capEntry = caps?.strategies.find((item) => item.id === survival.id) ?? null;
  const exposure = capEntry?.exposure ?? null;
  const leveredKey = exposure ? Object.keys(exposure.paths).find((k) => k !== "unlevered_1.00x") : undefined;
  const shownPath = exposure ? (financed && leveredKey ? exposure.paths[leveredKey] : exposure.paths["unlevered_1.00x"]) : null;

  const summary = survival.monte_carlo.block_summaries[blockKey] ?? survival.monte_carlo.block_summaries[String(survival.monte_carlo.primary_block_weeks)];
  const primary = survival.monte_carlo.block_summaries[String(survival.monte_carlo.primary_block_weeks)];

  /* ---- chart data ---- */

  const fanData = useMemo(() => {
    const bands = primary.curve_bands;
    if (!bands) return [];
    return bands.week.map((week, index) => ({
      week,
      p05: bands.p05[index],
      lowBand: bands.p25[index] - bands.p05[index],
      p25: bands.p25[index],
      midLow: bands.p50[index] - bands.p25[index],
      p50: bands.p50[index],
      midHigh: bands.p75[index] - bands.p50[index],
      p75: bands.p75[index],
      highBand: bands.p95[index] - bands.p75[index],
      p95: bands.p95[index],
    }));
  }, [primary]);

  const samplePathData = useMemo(() => {
    const curves = primary.sample_curves;
    if (!curves || !showPaths) return [];
    const weeks = curves[0]?.length ?? 0;
    return Array.from({ length: weeks }, (_, week) => {
      const row: Record<string, number> = { week: week + 1 };
      curves.forEach((curve, index) => { row[`s${index}`] = curve[week]; });
      return row;
    });
  }, [primary, showPaths]);

  const returnBins = useMemo(() => histogramRows(summary.return_histogram ?? primary.return_histogram), [summary, primary]);
  const drawdownBins = useMemo(() => histogramRows(summary.drawdown_histogram ?? primary.drawdown_histogram), [summary, primary]);

  const realized = useMemo(
    () => (survival.weekly_returns ?? []).map((row) => ({
      date: row.date,
      wealth: row.wealth * capital,
      drawdown: row.drawdown,
      net: row.net,
    })),
    [survival.weekly_returns, capital],
  );

  const stressRows = useMemo(() => {
    const rows = [{ key: "trailing", label: "Trailing 52 weeks", cagr: survival.historical.trailing_52w.cagr, drawdown: survival.historical.trailing_52w.max_drawdown, baseline: true }];
    Object.entries(survival.stress_tests).forEach(([key, stat]) => {
      rows.push({ key, label: STRESS_LABELS[key] ?? key, cagr: stat.cagr, drawdown: stat.max_drawdown, baseline: false });
    });
    return rows;
  }, [survival]);

  const grade = survival.historical_grade.replaceAll("_", " ");
  const resilient = survival.historical_grade === "historically_resilient";

  return (
    <div className="survival-lab">

      {/* ---------- strategy picker ---------- */}
      <div className="lab-picker" role="tablist" aria-label="Saved strategies">
        {bundle.comparison.map((row) => {
          const active = row.id === survival.id;
          return (
            <button
              key={row.id}
              role="tab"
              aria-selected={active}
              className={`lab-pick ${active ? "active" : ""}`}
              onClick={() => onSelect(row.id)}
            >
              <span className="lab-pick-name">{row.name}</span>
              <span className="lab-pick-score">
                <b>{row.score}</b>
                <i className={scoreClass(row.score)} style={{ width: `${row.score}%` }} />
              </span>
              <small>{row.grade.replaceAll("_", " ")}</small>
            </button>
          );
        })}
      </div>

      {/* ---------- hero ---------- */}
      <article className="panel survival-hero aurora-panel spotlight-surface" onMouseMove={positionSpotlight}>
        <div className="survival-hero-copy">
          <span className="section-kicker">REAL-WORLD READINESS</span>
          <h2>{survival.live_verdict === "not_proven_live" ? "Not proven live." : "Forward validation complete."}</h2>
          <p>{survival.plain_english_verdict} Monte Carlo resamples the history already observed; it cannot prove the future distribution looks the same.</p>
          <div className="survival-status-row">
            <span className={`survival-chip ${resilient ? "pass" : "warn"}`}>MODELED: {grade}</span>
            <span className={`survival-chip ${survival.research_evidence_gate.status === "passed" ? "pass" : "fail"}`}>RESEARCH GATE: {survival.research_evidence_gate.status.replaceAll("_", " ")}</span>
            <span className="survival-chip fail">FORWARD: {survival.forward_evidence.observed_weeks}/{survival.forward_evidence.required_weeks}</span>
          </div>
          {survival.binding_failures.length > 0 && (
            <p className="lab-binding"><AlertTriangle size={15} /> Binding failures: <b>{survival.binding_failures.join(" · ")}</b></p>
          )}
          {exposure?.benefits_heavily_from_financing && (
            <div className="lab-financing">
              <Landmark size={16} />
              <div>
                <strong>This strategy benefits heavily from financing.</strong>
                <p>{exposure.note}</p>
              </div>
              <div className="lab-controls">
                <button className={`lab-toggle ${!financed ? "on" : ""}`} onClick={() => setFinanced(false)}>Pure cash</button>
                <button className={`lab-toggle ${financed ? "on" : ""}`} onClick={() => setFinanced(true)}>Financed {exposure.native_gross.toFixed(2)}x</button>
              </div>
            </div>
          )}
          {shownPath && (
            <div className="lab-exposure-readout">
              <span>{financed && exposure?.uses_financing ? `FINANCED ${exposure.native_gross.toFixed(2)}x` : "PURE CASH 1.00x"} · TRAILING 52W</span>
              <b className={shownPath.cagr >= 0 ? "gain" : "loss"}>{pct(shownPath.cagr)}</b>
              <i>Sharpe {shownPath.sharpe.toFixed(2)} · drawdown {pct(shownPath.max_drawdown)}</i>
            </div>
          )}
        </div>
        <div className="survival-score">
          <span>MODELED RESILIENCE</span>
          <strong>{survival.historical_resilience_score}</strong>
          <small>/ 100 · historical diagnostic</small>
        </div>
      </article>

      {/* ---------- headline metrics ---------- */}
      <div className="survival-metric-grid">
        <article className="panel survival-metric">
          <span>MONTE CARLO PROFIT</span>
          <strong>{plainPct(summary.probability_of_profit)}</strong>
          <small>{summary.simulations.toLocaleString()} paths · {blockKey}-week blocks</small>
        </article>
        <article className="panel survival-metric">
          <span>5TH-PERCENTILE YEAR</span>
          <strong className={summary.p05_return >= 0 ? "gain" : "loss"}>{pct(summary.p05_return)}</strong>
          <small>1 in 20 simulated years is worse than this</small>
        </article>
        <article className="panel survival-metric">
          <span>30% DRAWDOWN RISK</span>
          <strong className={summary.probability_drawdown_over_30pct <= 0.25 ? "gain" : "loss"}>{plainPct(summary.probability_drawdown_over_30pct)}</strong>
          <small>Share of paths crossing −30%</small>
        </article>
        <article className="panel survival-metric">
          <span>WORST ROLLING YEAR</span>
          <strong className={survival.historical.rolling_52w.worst_return >= 0 ? "gain" : "loss"}>{pct(survival.historical.rolling_52w.worst_return)}</strong>
          <small>{survival.historical.rolling_52w.windows} actual windows tested</small>
        </article>
      </div>

      {/* ---------- tabs ---------- */}
      <div className="lab-tabs" role="tablist" aria-label="Survival evidence sections">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button key={id} role="tab" aria-selected={tab === id} className={`lab-tab ${tab === id ? "active" : ""}`} onClick={() => setTab(id)}>
            <Icon size={16} /><span>{label}</span>
          </button>
        ))}
      </div>

      {/* ================= MONTE CARLO ================= */}
      {tab === "montecarlo" && (
        <div className="lab-stack">
          <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head">
              <div>
                <span className="section-kicker">SIMULATED YEAR · WEALTH FAN</span>
                <h3>{summary.simulations.toLocaleString()} resampled 52-week paths</h3>
                <p>Shaded bands are the 5th–25th, 25th–50th, 50th–75th and 75th–95th percentiles of simulated wealth. {money(capital)} starting capital.</p>
              </div>
              <div className="lab-controls">
                {bundle.methodology.monte_carlo.block_lengths.map((block) => (
                  <button key={block} className={`lab-toggle ${blockKey === String(block) ? "on" : ""}`} onClick={() => setBlockKey(String(block))}>{block}w blocks</button>
                ))}
                <button className={`lab-toggle ${showPaths ? "on" : ""}`} onClick={() => setShowPaths((value) => !value)}>Sample paths</button>
              </div>
            </div>

            <div className="lab-chart tall">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={fanData} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="week" tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} label={{ value: "week", position: "insideBottomRight", fill: "var(--text-tertiary)", fontSize: 11, dy: 10 }} />
                  <YAxis tickFormatter={(value: number) => `${value.toFixed(1)}x`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={false} width={46} />
                  <Tooltip content={<FanTooltip capital={capital} />} />
                  <ReferenceLine y={1} stroke="var(--border-strong)" strokeDasharray="3 3" />
                  <Area type="monotone" dataKey="p05" stackId="fan" stroke="none" fill="transparent" isAnimationActive={false} />
                  <Area type="monotone" dataKey="lowBand" stackId="fan" stroke="none" fill="var(--blue)" fillOpacity={0.10} isAnimationActive={false} />
                  <Area type="monotone" dataKey="midLow" stackId="fan" stroke="none" fill="var(--blue)" fillOpacity={0.22} isAnimationActive={false} />
                  <Area type="monotone" dataKey="midHigh" stackId="fan" stroke="none" fill="var(--blue)" fillOpacity={0.22} isAnimationActive={false} />
                  <Area type="monotone" dataKey="highBand" stackId="fan" stroke="none" fill="var(--blue)" fillOpacity={0.10} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {showPaths && samplePathData.length > 0 && (
              <div className="lab-chart short">
                <span className="lab-chart-label">24 individual simulated paths</span>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={samplePathData} margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="week" tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                    <YAxis tickFormatter={(value: number) => `${value.toFixed(1)}x`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={false} width={46} />
                    <ReferenceLine y={1} stroke="var(--border-strong)" strokeDasharray="3 3" />
                    {(primary.sample_curves ?? []).map((_, index) => (
                      <Line key={index} type="monotone" dataKey={`s${index}`} stroke="var(--blue)" strokeOpacity={0.35} strokeWidth={1} dot={false} isAnimationActive={false} />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </article>

          <div className="survival-two-column">
            <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
              <div className="panel-head"><div><span className="section-kicker">OUTCOME DISTRIBUTION</span><h3>Where the 10,000 years land</h3><p>Red bars are losing years. The dashed line is break-even.</p></div></div>
              <div className="lab-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={returnBins} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="mid" tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                    <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
                    <Tooltip content={<BinTooltip unit="return" total={summary.simulations} />} />
                    <ReferenceLine x={0} stroke="var(--text-secondary)" strokeDasharray="3 3" />
                    <Bar dataKey="count" isAnimationActive={false}>
                      {returnBins.map((row) => <Cell key={row.mid} fill={row.mid < 0 ? "var(--red)" : "var(--green)"} fillOpacity={row.mid < 0 ? 0.75 : 0.6} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              {summary.quartiles && (
                <div className="lab-quartiles">
                  <div><dt>Worst</dt><dd className="loss">{pct(summary.quartiles.worst_return)}</dd></div>
                  <div><dt>5th</dt><dd className={summary.p05_return >= 0 ? "gain" : "loss"}>{pct(summary.p05_return)}</dd></div>
                  <div><dt>Median</dt><dd>{pct(summary.median_return)}</dd></div>
                  <div><dt>95th</dt><dd className="gain">{pct(summary.p95_return)}</dd></div>
                  <div><dt>Best</dt><dd className="gain">{pct(summary.quartiles.best_return)}</dd></div>
                </div>
              )}
            </article>

            <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
              <div className="panel-head"><div><span className="section-kicker">DEEPEST DRAWDOWN PER PATH</span><h3>How far each simulated year fell</h3><p>The marked line is the −30% failure threshold used by the score.</p></div></div>
              <div className="lab-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={drawdownBins} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                    <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
                    <XAxis dataKey="mid" tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                    <YAxis tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={false} width={40} />
                    <Tooltip content={<BinTooltip unit="drawdown" total={summary.simulations} />} />
                    <ReferenceLine x={-0.30} stroke="var(--red)" strokeDasharray="4 3" label={{ value: "−30%", fill: "var(--red)", fontSize: 11, position: "top" }} />
                    <Bar dataKey="count" isAnimationActive={false}>
                      {drawdownBins.map((row) => <Cell key={row.mid} fill={row.mid <= -0.30 ? "var(--red)" : "var(--amber)"} fillOpacity={row.mid <= -0.30 ? 0.8 : 0.5} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="lab-quartiles">
                <div><dt>Median DD</dt><dd className="loss">{pct(summary.median_max_drawdown)}</dd></div>
                <div><dt>5th pct DD</dt><dd className="loss">{pct(summary.p05_max_drawdown)}</dd></div>
                <div><dt>P(DD &gt; 30%)</dt><dd>{plainPct(summary.probability_drawdown_over_30pct, 2)}</dd></div>
                <div><dt>P(lose 50%)</dt><dd>{plainPct(summary.probability_of_50pct_capital_loss, 2)}</dd></div>
              </div>
            </article>
          </div>

          <article className="panel lab-note">
            <Info size={16} />
            <p><b>What this cannot tell you.</b> {bundle.methodology.selection_warning}</p>
          </article>
        </div>
      )}

      {/* ================= REALIZED HISTORY ================= */}
      {tab === "history" && (
        <div className="lab-stack">
          <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head">
              <div>
                <span className="section-kicker">ACTUAL SIMULATED PATH</span>
                <h3>{survival.observations} weeks, {survival.start} to {survival.end}</h3>
                <p>This is the single realized backtest, not a distribution. Adjust starting capital to rescale.</p>
              </div>
              <div className="lab-controls">
                {[10000, 100000, 1000000].map((value) => (
                  <button key={value} className={`lab-toggle ${capital === value ? "on" : ""}`} onClick={() => setCapital(value)}>{money(value)}</button>
                ))}
              </div>
            </div>
            <div className="lab-chart tall">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={realized} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
                  <defs>
                    <linearGradient id="labWealth" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--green)" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="var(--green)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} minTickGap={48} />
                  <YAxis tickFormatter={(value: number) => `$${(value / 1000).toFixed(0)}k`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={false} width={54} />
                  <Tooltip content={<HistoryTooltip />} />
                  <Area type="monotone" dataKey="wealth" stroke="var(--green)" strokeWidth={2} fill="url(#labWealth)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="lab-chart short">
              <span className="lab-chart-label">Drawdown from running peak</span>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={realized} margin={{ top: 6, right: 12, bottom: 4, left: 4 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} minTickGap={48} />
                  <YAxis tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={false} width={54} />
                  <Tooltip content={<HistoryTooltip drawdown />} />
                  <Area type="monotone" dataKey="drawdown" stroke="var(--red)" strokeWidth={1.5} fill="var(--red)" fillOpacity={0.12} isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </article>

          <div className="survival-metric-grid">
            <article className="panel survival-metric"><span>FULL-HISTORY CAGR</span><strong className={survival.historical.full.cagr >= 0 ? "gain" : "loss"}>{pct(survival.historical.full.cagr)}</strong><small>{survival.historical.full.observations} weeks</small></article>
            <article className="panel survival-metric"><span>FULL-HISTORY DRAWDOWN</span><strong className="loss">{pct(survival.historical.full.max_drawdown)}</strong><small>Deepest peak-to-trough</small></article>
            <article className="panel survival-metric"><span>FULL-HISTORY SHARPE</span><strong>{survival.historical.full.sharpe.toFixed(3)}</strong><small>Weekly returns annualized</small></article>
            <article className="panel survival-metric"><span>MAX SINGLE POSITION</span><strong className="loss">{pct(survival.concentration.maximum_single_position_weight)}</strong><small>Average largest {pct(survival.concentration.average_largest_position_weight)}</small></article>
          </div>

          <article className="panel lab-note">
            <Info size={16} />
            <p><b>Concentration is a floor, not a measurement.</b> Displayed weights are not ETF look-through exposures. A later holdings-level audit found the residual leader is an 81.6% technology book after look-through, with 48% in a single fund.</p>
          </article>
        </div>
      )}

      {/* ================= STRESS ================= */}
      {tab === "stress" && (
        <div className="lab-stack">
          <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head"><div><span className="section-kicker">PATH DEGRADATION</span><h3>Returns after harsher assumptions</h3><p>Positive CAGR here is survival, not proof of repeatability. Every bar uses the same frozen rules.</p></div></div>
            <div className="lab-chart tall">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={stressRows} layout="vertical" margin={{ top: 8, right: 24, bottom: 4, left: 8 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" horizontal={false} />
                  <XAxis type="number" tickFormatter={(value: number) => `${(value * 100).toFixed(0)}%`} tick={{ fill: "var(--text-tertiary)", fontSize: 11 }} tickLine={false} axisLine={{ stroke: "var(--border)" }} />
                  <YAxis type="category" dataKey="label" tick={{ fill: "var(--text-secondary)", fontSize: 12 }} tickLine={false} axisLine={false} width={150} />
                  <Tooltip content={<StressTooltip />} />
                  <ReferenceLine x={0} stroke="var(--text-secondary)" />
                  <Bar dataKey="cagr" isAnimationActive={false} radius={[0, 4, 4, 0]}>
                    {stressRows.map((row) => <Cell key={row.key} fill={row.cagr < 0 ? "var(--red)" : row.baseline ? "var(--blue)" : "var(--green)"} fillOpacity={row.baseline ? 0.85 : 0.6} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          <article className="panel lab-panel">
            <div className="panel-head"><div><span className="section-kicker">SCENARIO DETAIL</span><h3>CAGR and drawdown under each shock</h3></div></div>
            <div className="lab-table">
              <div className="lab-table-row head"><span>Scenario</span><span>CAGR</span><span>Max drawdown</span><span>Sharpe</span><span>Change vs base</span></div>
              {stressRows.map((row) => {
                const base = survival.historical.trailing_52w.cagr;
                const stat = row.baseline ? survival.historical.trailing_52w : survival.stress_tests[row.key];
                const delta = row.cagr - base;
                return (
                  <div key={row.key} className={`lab-table-row ${row.baseline ? "baseline" : ""}`}>
                    <span><strong>{row.label}</strong></span>
                    <span className={row.cagr >= 0 ? "gain" : "loss"}>{pct(row.cagr)}</span>
                    <span className="loss">{pct(row.drawdown)}</span>
                    <span>{stat ? stat.sharpe.toFixed(2) : "—"}</span>
                    <span className={row.baseline ? "" : delta >= 0 ? "gain" : "loss"}>{row.baseline ? "baseline" : `${delta >= 0 ? "+" : "−"}${Math.abs(delta * 100).toFixed(1)}pp`}</span>
                  </div>
                );
              })}
            </div>
          </article>
        </div>
      )}

      {/* ================= DESIGN GATE ================= */}
      {tab === "design" && (
        <div className="lab-stack">
          {!capEntry ? (
            <article className="panel lab-note"><Info size={16} /><p>Loading the concentration study&hellip;</p></article>
          ) : (
            <>
              <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
                <div className="panel-head">
                  <div>
                    <span className="section-kicker">CONCENTRATION CAPS ON A PURE-CASH BOOK</span>
                    <h3>{capEntry.all_caps_pass_after ? "Every cap can be satisfied" : "Caps still breached"}</h3>
                    <p>Leverage is removed first, then caps are applied. Released weight goes to cash and is never reinvested, so this is the conservative bound.</p>
                  </div>
                  <span className={`survival-chip ${capEntry.all_caps_pass_after ? "pass" : "fail"}`}>
                    {capEntry.all_caps_pass_after ? "DESIGN GATE SATISFIABLE" : "STILL FAILING"}
                  </span>
                </div>
                <div className="lab-table">
                  <div className="lab-table-row head design"><span>Constraint</span><span>Cap</span><span>Before</span><span>After</span><span>Result</span></div>
                  {Object.entries(capEntry.gates).map(([key, gate]) => (
                    <div key={key} className="lab-table-row design">
                      <span><strong>{CAP_LABELS[key] ?? key}</strong></span>
                      <span>{plainPct(gate.cap, 0)}</span>
                      <span className={gate.before_passes ? "" : "loss"}>{plainPct(gate.before_max, 1)}</span>
                      <span className={gate.after_passes ? "gain" : "loss"}>{plainPct(gate.after_max, 1)}</span>
                      <span className={gate.after_passes ? "gain" : "loss"}>{gate.after_passes ? "PASS" : "FAIL"}</span>
                    </div>
                  ))}
                </div>
              </article>

              <div className="survival-metric-grid">
                <article className="panel survival-metric"><span>WEIGHT FORCED TO CASH</span><strong className="loss">{plainPct(capEntry.cash_released.median, 1)}</strong><small>Median week · p95 {plainPct(capEntry.cash_released.p95, 1)}</small></article>
                <article className="panel survival-metric"><span>STILL INVESTED</span><strong>{plainPct(capEntry.average_invested_after, 1)}</strong><small>Average across {capEntry.weeks} weeks</small></article>
                <article className="panel survival-metric"><span>POSITIONS TRIMMED</span><strong>{capEntry.average_names_capped.toFixed(1)}</strong><small>Average per week</small></article>
                <article className="panel survival-metric"><span>NATIVE EXPOSURE</span><strong>{capEntry.max_original_gross.toFixed(2)}x</strong><small>{capEntry.used_leverage ? "Borrowed money used" : "Pure cash already"}</small></article>
              </div>

              <article className="panel lab-note">
                <AlertTriangle size={16} />
                <p><b>What this does and does not prove.</b> The caps are satisfiable, so the design gate is fixable rather than structural. But roughly {plainPct(capEntry.cash_released.median, 0)} of the book has to sit in cash to get there, because released weight has nowhere to go in this artifact. A real implementation redistributes into the next-ranked names instead, which requires re-running the strategy rather than re-weighting its output. {caps?.return_impact_note}</p>
              </article>

              <article className="panel lab-note">
                <Info size={16} />
                <p><b>Remaining blocker.</b> {caps?.remaining_blocker}</p>
              </article>
            </>
          )}
        </div>
      )}

      {/* ================= GATES ================= */}
      {tab === "gates" && (
        <div className="lab-stack">
          <article className="panel lab-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head">
              <div><span className="section-kicker">FROZEN TEST BATTERY</span><h3>What survived, and what broke</h3><p>Seven weighted gates, 100 points. Every saved strategy is scored by identical rules.</p></div>
              <span className="as-of">Data through {survival.end}</span>
            </div>
            <div className="survival-test-list">
              {survival.test_results.map((test) => (
                <div key={test.id} className={`survival-test ${test.status}`}>
                  <span className="test-state">{test.passed ? "PASS" : "FAIL"}</span>
                  <div>
                    <strong>{test.label}</strong>
                    <small>Observed {pct(test.value, 2)} · threshold {pct(test.threshold, 2)}</small>
                  </div>
                  <b>+{test.passed ? test.points : 0}</b>
                </div>
              ))}
            </div>
            <div className="lab-score-total">
              <span>TOTAL</span>
              <strong>{survival.historical_resilience_score} / 100</strong>
              <i><em className={scoreClass(survival.historical_resilience_score)} style={{ width: `${survival.historical_resilience_score}%` }} /></i>
            </div>
          </article>

          <article className="panel survival-comparison spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head"><div><span className="section-kicker">ALL SAVED STRATEGIES</span><h3>Same tests, side by side</h3><p>Click a row to open that strategy. The score ranks modeled historical resilience; it does not authorize trading.</p></div><span className="survival-chip fail">ALL {bundle.comparison.length} NOT PROVEN LIVE</span></div>
            <div className="survival-table">
              <div className="survival-table-row head"><span>Strategy</span><span>Score</span><span>Recent CAGR</span><span>Worst year</span><span>MC profit</span><span>MC DD &gt;30%</span><span>Verdict</span></div>
              {bundle.comparison.map((row) => (
                <button key={row.id} className={`survival-table-row ${row.id === survival.id ? "selected" : ""}`} onClick={() => onSelect(row.id)}>
                  <span><strong>{row.name}</strong><small>{row.grade.replaceAll("_", " ")}</small></span>
                  <b>{row.score}</b>
                  <span>{pct(row.recent_cagr)}</span>
                  <span className={row.worst_rolling_year >= 0 ? "gain" : "loss"}>{pct(row.worst_rolling_year)}</span>
                  <span>{plainPct(row.monte_profit_probability)}</span>
                  <span>{plainPct(row.monte_30pct_drawdown_probability)}</span>
                  <span className="loss">NOT PROVEN</span>
                </button>
              ))}
            </div>
          </article>

          <div className="survival-two-column readiness-grid">
            <article className="panel survival-readiness">
              <span className="section-kicker">WHAT IS STILL MISSING</span>
              <h3>Real-world implementation evidence</h3>
              <ul>{bundle.known_missing_real_world_inputs.map((item) => <li key={item}>{item}</li>)}</ul>
            </article>
            <article className="panel survival-readiness">
              <span className="section-kicker">HOW TO READ THIS PAGE</span>
              <h3>Three different standards</h3>
              <ol>
                <li><b>Modeled survival</b> asks whether resampled history and preset shocks destroy the path.</li>
                <li><b>Research validation</b> asks whether selection, concentration, timing, and multiple-testing gates passed.</li>
                <li><b>Live evidence</b> requires untouched forward observations and executable implementation data.</li>
              </ol>
              <p>{bundle.methodology.selection_warning}</p>
            </article>
          </div>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------ subcomponents */

function scoreClass(score: number) {
  if (score >= 75) return "good";
  if (score >= 55) return "mid";
  return "bad";
}

function histogramRows(histogram?: Histogram) {
  if (!histogram) return [] as { mid: number; count: number; lo: number; hi: number }[];
  return histogram.counts.map((count, index) => ({
    mid: (histogram.edges[index] + histogram.edges[index + 1]) / 2,
    lo: histogram.edges[index],
    hi: histogram.edges[index + 1],
    count,
  }));
}

type TooltipProps = { active?: boolean; payload?: { payload?: Record<string, number> }[]; label?: string | number };

function FanTooltip({ active, payload, capital }: TooltipProps & { capital: number }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="lab-tooltip">
      <strong>Week {row.week}</strong>
      <span><i>95th</i><b>{money(row.p95 * capital)}</b></span>
      <span><i>75th</i><b>{money(row.p75 * capital)}</b></span>
      <span className="mid"><i>Median</i><b>{money(row.p50 * capital)}</b></span>
      <span><i>25th</i><b>{money(row.p25 * capital)}</b></span>
      <span><i>5th</i><b>{money(row.p05 * capital)}</b></span>
    </div>
  );
}

function BinTooltip({ active, payload, unit, total }: TooltipProps & { unit: string; total: number }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="lab-tooltip">
      <strong>{pct(row.lo, 0)} to {pct(row.hi, 0)} {unit}</strong>
      <span><i>Paths</i><b>{row.count.toLocaleString()}</b></span>
      <span><i>Share</i><b>{((row.count / total) * 100).toFixed(2)}%</b></span>
    </div>
  );
}

function HistoryTooltip({ active, payload, label, drawdown }: TooltipProps & { drawdown?: boolean }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="lab-tooltip">
      <strong>{String(label)}</strong>
      {drawdown
        ? <span><i>Drawdown</i><b className="loss">{pct(row.drawdown, 2)}</b></span>
        : <><span><i>Value</i><b>{money(row.wealth)}</b></span><span><i>Week</i><b className={row.net >= 0 ? "gain" : "loss"}>{pct(row.net, 2)}</b></span></>}
    </div>
  );
}

function StressTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload;
  if (!row) return null;
  return (
    <div className="lab-tooltip">
      <strong>{String(row.label ?? "")}</strong>
      <span><i>CAGR</i><b className={Number(row.cagr) >= 0 ? "gain" : "loss"}>{pct(Number(row.cagr))}</b></span>
      <span><i>Max drawdown</i><b className="loss">{pct(Number(row.drawdown))}</b></span>
    </div>
  );
}
