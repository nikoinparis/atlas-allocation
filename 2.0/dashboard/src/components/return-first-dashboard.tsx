"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChevronLeft, ChevronRight, FlaskConical, Settings2, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Holding = { symbol: string; weight: number | null; change: number | null };
type StrategyRecord = {
  date: string;
  grossReturn: number | null;
  netReturn: number | null;
  turnover: number | null;
  cost: number | null;
  wealth: number | null;
  drawdown: number | null;
  rebalance: boolean;
  holdings: Holding[];
};
type DailyRecord = {
  date: string;
  netReturn: number | null;
  rebalance: boolean;
  tradingDay: boolean;
};
type AssetPrice = { date: string; price: number };
type DashboardPayload = {
  strategy: {
    id: string;
    name: string;
    shortName: string;
    subtitle: string;
    badge: string;
    asOf: string;
    retrospectiveHoldout: { cagr: number; sharpe: number; maxDrawdown: number; start: string };
    fullHistory: { cagr: number; maxDrawdown: number; start: string };
    featuredMetric: { label: string; value: number; note: string };
    forward: { status: string; observedWeeks: number; requiredWeeks: number; firstDecision: string; firstRealization: string; note: string };
    disclosures: { researchOnly: boolean; liveTradingEnabled: boolean; costBps: number; returnConvention: string };
  };
  records: StrategyRecord[];
  dailyRecords: DailyRecord[];
  assetPrices: Record<string, AssetPrice[]>;
};
type DashboardBundle = { strategies: DashboardPayload[] };

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const compactMoney = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const holdingColors = ["#45d992", "#24bea7", "#15b8c5", "#58a8eb", "#8b9ce5", "#f0b843", "#dc775e", "#788889"];

function pct(value: number, digits = 2) {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(digits)}%`;
}

function plainPct(value: number, digits = 1) {
  return `${(value * 100).toFixed(digits)}%`;
}

function parseDate(value: string) {
  return new Date(`${value}T12:00:00`);
}

function formatDate(value: string) {
  return parseDate(value).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
}

function portfolioMetrics(records: DailyRecord[], capital: number) {
  const returns = records.map((row) => row.netReturn ?? 0);
  const tradingReturns = records.filter((row) => row.tradingDay).map((row) => row.netReturn ?? 0);
  const nonZero = tradingReturns.filter((value) => value !== 0);
  const totalMultiple = returns.reduce((wealth, value) => wealth * (1 + value), 1);
  const years = Math.max(tradingReturns.length / 252, 1 / 252);
  const annualizedReturn = totalMultiple > 0 ? Math.pow(totalMultiple, 1 / years) - 1 : -1;
  const mean = tradingReturns.reduce((sum, value) => sum + value, 0) / Math.max(tradingReturns.length, 1);
  const variance = tradingReturns.reduce((sum, value) => sum + Math.pow(value - mean, 2), 0) / Math.max(tradingReturns.length - 1, 1);
  const sharpe = variance > 0 ? (mean / Math.sqrt(variance)) * Math.sqrt(252) : 0;
  let wealth = 1;
  let peak = 1;
  let maxDrawdown = 0;
  const path = records.map((row) => {
    wealth *= 1 + (row.netReturn ?? 0);
    peak = Math.max(peak, wealth);
    maxDrawdown = Math.min(maxDrawdown, wealth / peak - 1);
    return { date: row.date, value: capital * wealth };
  });
  return {
    annualizedReturn,
    sharpe,
    maxDrawdown,
    winRate: nonZero.length ? nonZero.filter((value) => value > 0).length / nonZero.length : 0,
    totalReturn: totalMultiple - 1,
    endValue: capital * totalMultiple,
    profit: capital * (totalMultiple - 1),
    path,
  };
}

function classification(symbol: string) {
  if (["MU", "VICR", "PLTR", "RDDT"].includes(symbol)) return "Fundamental growth stock";
  if (symbol === "BKV") return "Fundamental energy stock";
  if (symbol === "MMAT") return "Unpriced historical selection";
  if (symbol === "cash::USD" || symbol === "BIL" || symbol === "SHY") return "Cash / defensive";
  if (["XLK", "QQQ", "VUG"].includes(symbol)) return "Technology / growth";
  if (["XLE", "USO", "PDBC", "GLD", "IAU", "SLV", "DBA"].includes(symbol)) return "Energy / commodities";
  if (["SPY", "IWM", "VTV", "XLF", "XLI", "XLP", "XLU", "XLV", "XLY"].includes(symbol)) return "U.S. equity";
  if (["EEM", "EFA", "VEA", "VWO", "EWJ"].includes(symbol)) return "International equity";
  if (["TLT", "IEF", "LQD", "HYG", "MBB", "TIP"].includes(symbol)) return "Rates / credit";
  return "Diversifier";
}

function changeLabel(holding: Holding) {
  const current = holding.weight ?? 0;
  const delta = holding.change ?? 0;
  if (current <= 1e-8 && delta < 0) return "SOLD";
  if (current > 0 && Math.abs(current - delta) <= 1e-8) return "NEW";
  return delta > 0 ? "ADD" : "TRIM";
}

export function ReturnFirstDashboard() {
  const [bundle, setBundle] = useState<DashboardBundle | null>(null);
  const [activeStrategy, setActiveStrategy] = useState("candidate-return-first-60-40-forward-v1");
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/return-first-dashboard.json")
      .then((response) => {
        if (!response.ok) throw new Error("Dashboard snapshot is unavailable");
        return response.json() as Promise<DashboardBundle>;
      })
      .then(setBundle)
      .catch(() => setError(true));
  }, []);

  if (error) return <main className="loading-state"><span>PORTFOLIO OPTIMIZER</span><h1>Research snapshot unavailable</h1><p>Rebuild the dashboard snapshot and refresh this page.</p></main>;
  if (!bundle) return <main className="loading-state"><span>PORTFOLIO OPTIMIZER</span><h1>Loading the research book…</h1></main>;
  const data = bundle.strategies.find((item) => item.strategy.id === activeStrategy) ?? bundle.strategies[0];
  return <DashboardView key={data.strategy.id} data={data} strategies={bundle.strategies} onStrategyChange={setActiveStrategy} />;
}

function DashboardView({ data, strategies, onStrategyChange }: { data: DashboardPayload; strategies: DashboardPayload[]; onStrategyChange: (id: string) => void }) {
  const latest = data.records.at(-1)!;
  const latestDay = data.dailyRecords.at(-1)!;
  const firstHoldoutRecord = data.dailyRecords.find((row) => row.date > data.strategy.retrospectiveHoldout.start)?.date ?? data.strategy.retrospectiveHoldout.start;
  const [capital, setCapital] = useState(10_000);
  const [startDate, setStartDate] = useState(firstHoldoutRecord);
  const [selectedDate, setSelectedDate] = useState(latestDay.date);
  const [calendarDate, setCalendarDate] = useState(parseDate(latestDay.date));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [stockChart, setStockChart] = useState<{ symbol: string; endDate: string; source: "calendar" | "current" } | null>(null);

  const recordMap = useMemo(() => new Map(data.dailyRecords.map((row) => [row.date, row])), [data.dailyRecords]);
  const selected = recordMap.get(selectedDate) ?? latestDay;
  const selectedAllocation = useMemo(
    () => data.records.findLast((row) => row.date <= selectedDate) ?? data.records[0],
    [data.records, selectedDate],
  );
  const simulationRecords = useMemo(() => data.dailyRecords.filter((row) => row.date >= startDate), [data.dailyRecords, startDate]);
  const metrics = useMemo(() => portfolioMetrics(simulationRecords, capital), [simulationRecords, capital]);
  const selectedIndex = simulationRecords.findIndex((row) => row.date === selected.date);
  const selectedValue = selectedIndex >= 0 ? metrics.path[selectedIndex]?.value ?? capital : capital;
  const allocationChangedToday = selected.rebalance && selectedAllocation.date === selected.date;
  const stockChartSeries = useMemo(
    () => stockChart ? (data.assetPrices[stockChart.symbol] ?? []).filter((row) => row.date <= stockChart.endDate) : [],
    [data.assetPrices, stockChart],
  );
  const stockStart = stockChartSeries[0];
  const stockEnd = stockChartSeries.at(-1);
  const stockChange = stockStart && stockEnd ? stockEnd.price / stockStart.price - 1 : 0;

  const currentHoldings = latest.holdings.filter((holding) => (holding.weight ?? 0) > 1e-8);
  const changedHoldings = selectedAllocation.holdings.filter((holding) => Math.abs(holding.change ?? 0) > 1e-8);
  const recentRebalances = useMemo(() => data.records.filter((row) => row.rebalance).slice(-7).reverse(), [data.records]);

  const month = calendarDate.getMonth();
  const year = calendarDate.getFullYear();
  const firstWeekday = new Date(year, month, 1).getDay();
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const calendarCells = Array.from({ length: firstWeekday + daysInMonth }, (_, index) => {
    if (index < firstWeekday) return null;
    const day = index - firstWeekday + 1;
    const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    return { day, key, record: recordMap.get(key) };
  });

  function setQuickRange(years: number | "max") {
    if (years === "max") {
      setStartDate(data.dailyRecords[0].date);
      return;
    }
    const target = parseDate(latestDay.date);
    target.setFullYear(target.getFullYear() - years);
    const iso = target.toISOString().slice(0, 10);
    const nearest = data.dailyRecords.find((row) => row.date >= iso) ?? data.dailyRecords[0];
    setStartDate(nearest.date);
  }

  function moveMonth(delta: number) {
    setCalendarDate(new Date(year, month + delta, 1));
  }

  function openStockChart(symbol: string, endDate: string, source: "calendar" | "current") {
    if (!data.assetPrices[symbol]?.length) return;
    setStockChart({ symbol, endDate, source });
  }

  return (
    <main className="dashboard-page">
      <header className="topbar">
        <div>
          <div className="eyebrow"><span className="status-dot" /> PORTFOLIO OPTIMIZER — RESEARCH BOOK</div>
          <h1>Return-First Control Room</h1>
          <div className="strategy-line">
            <label className="strategy-picker">
              <span>DISPLAY STRATEGY</span>
              <select value={data.strategy.id} onChange={(event) => onStrategyChange(event.target.value)}>
                {strategies.map((item) => <option key={item.strategy.id} value={item.strategy.id}>{item.strategy.shortName}</option>)}
              </select>
            </label>
            <span className="strategy-name">{data.strategy.name}</span>
            <span className="pill research"><FlaskConical size={13} /> Retrospective research</span>
            <span className="pill">50 bps costs</span>
            <span className="pill strategy-badge">{data.strategy.badge}</span>
          </div>
        </div>
        <div className="portfolio-headline">
          <button className="settings-button" onClick={() => setSettingsOpen(true)} aria-label="Open simulation settings">
            <Settings2 size={16} /> What if
          </button>
          <span className="micro-label">SIMULATED PORTFOLIO VALUE</span>
          <strong>{money.format(metrics.endValue)}</strong>
          <span className={metrics.profit >= 0 ? "gain" : "loss"}>{metrics.profit >= 0 ? "▲" : "▼"} {money.format(Math.abs(metrics.profit))} ({pct(metrics.totalReturn)})</span>
        </div>
      </header>

      <section className="metric-grid" aria-label="Strategy metrics">
        <article className="metric-card featured">
          <span>ANNUALIZED RETURN</span>
          <strong className={metrics.annualizedReturn >= 0 ? "gain" : "loss"}>{pct(metrics.annualizedReturn, 1)}</strong>
          <small>{startDate} to {latestDay.date}</small>
        </article>
        <article className="metric-card">
          <span>SHARPE RATIO</span>
          <strong>{metrics.sharpe.toFixed(2)}</strong>
          <small>daily, zero risk-free rate</small>
        </article>
        <article className="metric-card">
          <span>MAX DRAWDOWN</span>
          <strong className="loss">{pct(metrics.maxDrawdown, 1)}</strong>
          <small>selected simulation window</small>
        </article>
        <article className="metric-card">
          <span>WIN RATE</span>
          <strong>{plainPct(metrics.winRate, 0)}</strong>
          <small>positive non-zero trading days</small>
        </article>
        <article className="metric-card proof-card">
          <span>{data.strategy.featuredMetric.label}</span>
          <strong className="gain">{pct(data.strategy.featuredMetric.value, 2)}</strong>
          <small>{data.strategy.featuredMetric.note}</small>
        </article>
      </section>

      <section className="main-grid">
        <article className="panel calendar-panel">
          <div className="panel-head calendar-head">
            <div>
              <span className="section-kicker">DAILY P&amp;L CALENDAR</span>
              <h2>{monthNames[month]} {year}</h2>
            </div>
            <div className="calendar-controls">
              <button onClick={() => moveMonth(-1)} aria-label="Previous month"><ChevronLeft size={18} /></button>
              <select value={month} onChange={(event) => setCalendarDate(new Date(year, Number(event.target.value), 1))} aria-label="Month">
                {monthNames.map((name, index) => <option key={name} value={index}>{name}</option>)}
              </select>
              <select value={year} onChange={(event) => setCalendarDate(new Date(Number(event.target.value), month, 1))} aria-label="Year">
                {Array.from(new Set(data.dailyRecords.map((row) => parseDate(row.date).getFullYear()))).reverse().map((item) => <option key={item}>{item}</option>)}
              </select>
              <button onClick={() => moveMonth(1)} aria-label="Next month"><ChevronRight size={18} /></button>
            </div>
          </div>
          <div className="calendar-legend"><span><i className="legend-dot green" /> daily gain</span><span><i className="legend-dot red" /> daily loss</span><span><i className="legend-dot bone" /> holdings changed</span></div>
          <div className="calendar-grid weekdays">{["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-grid days">
            {calendarCells.map((cell, index) => cell ? (
              <button
                key={cell.key}
                disabled={!cell.record}
                onClick={() => cell.record && setSelectedDate(cell.key)}
                className={`day-cell ${cell.record ? cell.record.rebalance ? "rebalance" : (cell.record.netReturn ?? 0) >= 0 ? "positive" : "negative" : "empty"} ${selectedDate === cell.key ? "selected" : ""}`}
              >
                <span>{cell.day}</span>
                {cell.record && <strong className={(cell.record.netReturn ?? 0) >= 0 ? "positive-return" : "negative-return"}>{pct(cell.record.netReturn ?? 0, 2)}</strong>}
                {cell.record?.rebalance && <i className="rebalance-mark" title="Holdings changed" />}
              </button>
            ) : <span className="day-cell spacer" key={`blank-${index}`} />)}
          </div>

          <div className="date-inspector">
            <div className="inspector-title">
              <div><span className="section-kicker">SELECTED STRATEGY DATE</span><h3>{formatDate(selected.date)}</h3></div>
              <div className="selected-pnl"><span>DAILY P&amp;L</span><strong className={(selected.netReturn ?? 0) >= 0 ? "gain" : "loss"}>{money.format(selectedValue * (selected.netReturn ?? 0))}</strong><small>{pct(selected.netReturn ?? 0)}</small></div>
            </div>
            <div className="holdings-table">
              <div className="table-row table-head"><span>HOLDING</span><span>WEIGHT</span><span>CHANGE</span><span>SIMULATED VALUE</span></div>
              {selectedAllocation.holdings.filter((holding) => (holding.weight ?? 0) > 1e-8).map((holding) => (
                <div className="table-row" key={holding.symbol}>
                  <span><button className="holding-link" disabled={!data.assetPrices[holding.symbol]?.length} onClick={() => openStockChart(holding.symbol, selected.date, "calendar")}><b>{holding.symbol.replace("cash::", "")}</b><small>{classification(holding.symbol)}</small></button></span>
                  <span>{plainPct(holding.weight ?? 0)}</span>
                  <span className={(holding.change ?? 0) >= 0 ? "gain weight-transition" : "loss weight-transition"}>{!allocationChangedToday || Math.abs(holding.change ?? 0) < 1e-8 ? "—" : <>{plainPct((holding.weight ?? 0) - (holding.change ?? 0))} <i>→</i> <b>{plainPct(holding.weight ?? 0)}</b></>}</span>
                  <span>{money.format(selectedValue * (holding.weight ?? 0))}</span>
                </div>
              ))}
            </div>
            <div className="trade-log">
              <span className="section-kicker">HOLDINGS CHANGE LOG</span>
              {allocationChangedToday ? changedHoldings.map((holding) => (
                <div className="trade-row" key={holding.symbol}>
                  <span className={`trade-badge ${changeLabel(holding).toLowerCase()}`}>{changeLabel(holding)}</span>
                  <button className="trade-symbol" disabled={!data.assetPrices[holding.symbol]?.length} onClick={() => openStockChart(holding.symbol, selected.date, "calendar")}>{holding.symbol.replace("cash::", "")}</button>
                  <span className="trade-transition">{plainPct((holding.weight ?? 0) - (holding.change ?? 0))} <i>→</i> <b>{plainPct(holding.weight ?? 0)}</b></span>
                  <strong>{money.format(Math.abs(selectedValue * (holding.change ?? 0)))}</strong>
                </div>
              )) : <p>No holdings changed on this strategy date.</p>}
            </div>
          </div>
        </article>

        <div className="right-stack">
          <article className="panel chart-panel">
            <div className="panel-head">
              <div><span className="section-kicker">SIMULATED EQUITY CURVE</span><h2>Portfolio Value</h2><p>{startDate} — {latestDay.date}</p></div>
              <strong className={metrics.totalReturn >= 0 ? "gain" : "loss"}>{pct(metrics.totalReturn)}</strong>
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={metrics.path} margin={{ top: 12, right: 8, left: 4, bottom: 0 }}>
                  <defs><linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#31d590" stopOpacity={0.34} /><stop offset="100%" stopColor="#31d590" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid vertical={false} stroke="#1b2723" />
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["dataMin", "dataMax"]} hide />
                  <Tooltip contentStyle={{ background: "#0a100f", border: "1px solid #26332f", borderRadius: 10 }} formatter={(value) => [money.format(Number(value)), "Value"]} labelStyle={{ color: "#789087" }} />
                  <Area type="monotone" dataKey="value" stroke="#39d997" strokeWidth={2.2} fill="url(#valueFill)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-stats"><span><small>START</small>{money.format(capital)}</span><span><small>PROFIT</small><b className={metrics.profit >= 0 ? "gain" : "loss"}>{money.format(metrics.profit)}</b></span><span><small>TRADING DAYS</small>{simulationRecords.length}</span></div>
          </article>

          <article className="panel allocation-panel">
            <div className="panel-head"><div><span className="section-kicker">LATEST DECISION</span><h2>Current Allocation</h2></div><span className="as-of">Prices through {data.strategy.asOf}</span></div>
            <div className="allocation-body">
              <div className="donut" style={{ background: `conic-gradient(${currentHoldings.map((holding, index) => `${holdingColors[index % holdingColors.length]} ${currentHoldings.slice(0, index).reduce((sum, item) => sum + (item.weight ?? 0), 0) * 100}% ${(currentHoldings.slice(0, index + 1).reduce((sum, item) => sum + (item.weight ?? 0), 0)) * 100}%`).join(",")})` }}>
                <div><small>HOLDINGS</small><strong>{currentHoldings.length}</strong></div>
              </div>
              <div className="allocation-list">
                {currentHoldings.map((holding, index) => <button key={holding.symbol} disabled={!data.assetPrices[holding.symbol]?.length} onClick={() => openStockChart(holding.symbol, latestDay.date, "current")}><i style={{ background: holdingColors[index % holdingColors.length] }} /><b>{holding.symbol.replace("cash::", "")}</b><span>{plainPct(holding.weight ?? 0)}</span><small>{classification(holding.symbol)}</small></button>)}
              </div>
            </div>
          </article>
        </div>
      </section>

      <section className="bottom-grid">
        <article className="panel compact-panel">
          <span className="section-kicker">RECENT HOLDINGS CHANGES</span><h2>Rebalance Activity</h2>
          <div className="activity-list">{recentRebalances.map((row) => {
            const changes = row.holdings.filter((holding) => Math.abs(holding.change ?? 0) > 1e-8);
            return <button key={row.date} onClick={() => { setSelectedDate(row.date); setCalendarDate(parseDate(row.date)); }}><span><b>{row.date}</b><small>{changes.length} changes · {plainPct(row.turnover ?? 0)} turnover</small></span><span>{changes.slice(0, 3).map((item) => item.symbol.replace("cash::", "")).join(" · ")}</span><ChevronRight size={16} /></button>;
          })}</div>
        </article>
        <article className="panel compact-panel protocol-panel">
          <span className="section-kicker">FORWARD VALIDATION CLOCK</span><h2>{data.strategy.forward.observedWeeks} / {data.strategy.forward.requiredWeeks} weeks observed</h2>
          <div className="progress-track"><i style={{ width: `${(data.strategy.forward.observedWeeks / data.strategy.forward.requiredWeeks) * 100}%` }} /></div>
          <p>First eligible realization: <b>{data.strategy.forward.firstRealization}</b>. {data.strategy.forward.note}</p>
        </article>
        <article className="panel compact-panel guardrail-panel">
          <span className="section-kicker">STATUS &amp; GUARDRAILS</span><h2>Simulation only</h2>
          <ul><li>No brokerage connection</li><li>No live money or automatic orders</li><li>Costs included at 50 bps of turnover</li><li>Frozen formula; no post-selection changes</li></ul>
        </article>
      </section>

      <footer>
          <span>Data through {latestDay.date} · daily P&amp;L from weekly strategy decisions</span>
        <span>Past simulated performance does not guarantee future returns.</span>
      </footer>

      {settingsOpen && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSettingsOpen(false)}>
        <aside className="settings-drawer" aria-label="Simulation settings">
          <button className="close-button" onClick={() => setSettingsOpen(false)}><X size={18} /></button>
          <span className="section-kicker">WHAT-IF LAB</span>
          <h2>Replay the strategy</h2>
          <p>Change only the hypothetical starting amount and time window. The strategy rules, weekly returns, and 50-bps cost model remain frozen.</p>
          <label>Starting capital<input type="number" min="100" step="100" value={capital} onChange={(event) => setCapital(Math.max(100, Number(event.target.value) || 100))} /></label>
          <label>Start date<input type="date" min={data.dailyRecords[0].date} max={latestDay.date} value={startDate} onChange={(event) => setStartDate(event.target.value)} /></label>
          <div className="quick-ranges"><span>QUICK RANGE</span>{[1, 2, 3, 5].map((item) => <button key={item} onClick={() => setQuickRange(item)}>{item}Y</button>)}<button onClick={() => setQuickRange("max")}>MAX</button></div>
          <div className="scenario-result"><span>SIMULATED END VALUE</span><strong>{money.format(metrics.endValue)}</strong><small>{compactMoney.format(capital)} became {compactMoney.format(metrics.endValue)} · {pct(metrics.totalReturn)}</small></div>
          <button className="apply-button" onClick={() => setSettingsOpen(false)}>Apply scenario</button>
        </aside>
      </div>}

      {stockChart && <div className="modal-backdrop stock-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setStockChart(null)}>
        <aside className="settings-drawer stock-drawer" aria-label={`${stockChart.symbol} historical price chart`}>
          <button className="close-button" onClick={() => setStockChart(null)}><X size={18} /></button>
          <span className="section-kicker">HISTORICAL ADJUSTED PRICE</span>
          <h2>{stockChart.symbol}</h2>
          <p>{stockChart.source === "calendar" ? `Calendar cutoff: ${stockChart.endDate}` : `Latest strategy data: ${stockChart.endDate}`}. Prices after this cutoff are intentionally hidden.</p>
          {stockEnd ? <>
            <div className="stock-price-headline">
              <div><span>LAST PRICE THROUGH CUTOFF</span><strong>{money.format(stockEnd.price)}</strong><small>{stockEnd.date}</small></div>
              <div><span>AVAILABLE-HISTORY CHANGE</span><strong className={stockChange >= 0 ? "gain" : "loss"}>{pct(stockChange)}</strong><small>from {stockStart?.date}</small></div>
            </div>
            <div className="stock-chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stockChartSeries} margin={{ top: 12, right: 8, left: 4, bottom: 0 }}>
                  <defs><linearGradient id="stockPriceFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#39d997" stopOpacity={0.32} /><stop offset="100%" stopColor="#39d997" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid vertical={false} stroke="#1b2723" />
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["dataMin", "dataMax"]} hide />
                  <Tooltip contentStyle={{ background: "#0a100f", border: "1px solid #26332f", borderRadius: 10 }} formatter={(value) => [money.format(Number(value)), "Adjusted price"]} labelStyle={{ color: "#789087" }} />
                  <Area type="monotone" dataKey="price" stroke="#39d997" strokeWidth={2.2} fill="url(#stockPriceFill)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="stock-chart-footer"><span><small>FIRST AVAILABLE</small>{stockStart?.date}</span><span><small>CUTOFF</small>{stockChart.endDate}</span><span><small>OBSERVATIONS</small>{stockChartSeries.length}</span></div>
          </> : <div className="stock-unavailable"><strong>No validated price history</strong><p>This holding is shown in the strategy record, but no trusted price series is available for this cutoff.</p></div>}
        </aside>
      </div>}
    </main>
  );
}

