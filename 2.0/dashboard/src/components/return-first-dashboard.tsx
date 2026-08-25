"use client";

import Link from "next/link";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SurvivalLab, type SurvivalBundlePayload } from "@/components/survival-lab";
import {
  ArrowUpRight,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  FlaskConical,
  Gauge,
  History,
  Info,
  Menu,
  PanelLeftClose,
  PieChart,
  Settings2,
  Siren,
  ShieldCheck,
  TrendingUp,
  Workflow,
  X,
} from "lucide-react";
import { type MouseEvent, useEffect, useMemo, useState } from "react";

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
    cashOnlyMetric?: { label: string; value: number; sharpe: number; maxDrawdown: number; note: string };
    forward: { status: string; observedWeeks: number; requiredWeeks: number; firstDecision: string; firstRealization: string; note: string };
    disclosures: { researchOnly: boolean; liveTradingEnabled: boolean; costBps: number; returnConvention: string };
  };
  records: StrategyRecord[];
  dailyRecords: DailyRecord[];
  assetPrices: Record<string, AssetPrice[]>;
};
type DashboardBundle = { strategies: DashboardPayload[] };
type SurvivalTest = { id: string; label: string; passed: boolean; status: "pass" | "fail"; value: number; threshold: number; points: number };
type SurvivalStrategy = {
  id: string;
  name: string;
  short_name: string;
  end: string;
  historical_resilience_score: number;
  historical_grade: "historically_resilient" | "mixed_evidence" | "historically_fragile";
  live_verdict: "not_proven_live" | "forward_validation_complete";
  plain_english_verdict: string;
  binding_failures: string[];
  historical: { full: { cagr: number; sharpe: number; max_drawdown: number }; trailing_52w: { cagr: number; sharpe: number; max_drawdown: number }; rolling_52w: { worst_return: number; median_return: number; positive_rate: number; windows: number } };
  stress_tests: Record<string, { cagr: number; sharpe: number; max_drawdown: number; total_return: number }>;
  monte_carlo: { primary_block_weeks: number; block_summaries: Record<string, { simulations: number; median_return: number; p05_return: number; p95_return: number; probability_of_profit: number; probability_of_50pct_capital_loss: number; probability_drawdown_over_30pct: number; median_max_drawdown: number; p05_max_drawdown: number }> };
  concentration: { maximum_single_position_weight: number; average_largest_position_weight: number; average_borrowed_exposure: number };
  test_results: SurvivalTest[];
  research_evidence_gate: { status: "passed" | "failed" | "not_exposed_in_dashboard"; boolean_checks: number; checks_passed: number };
  forward_evidence: { observed_weeks: number; required_weeks: number; status: string; passed: boolean };
  readiness: { execution_enabled: boolean; live_trading_enabled: boolean; missing_real_world_inputs: string[] };
};
type SurvivalBundle = {
  experiment: string;
  methodology: { selection_warning: string; interpretation: string; monte_carlo: { simulations: number; horizon_weeks: number; block_lengths: number[] } };
  comparison: Array<{ id: string; name: string; score: number; grade: string; recent_cagr: number; worst_rolling_year: number; monte_profit_probability: number; monte_30pct_drawdown_probability: number; live_verdict: string }>;
  strategies: SurvivalStrategy[];
  all_strategies_not_proven_live: boolean;
  known_missing_real_world_inputs: string[];
};
type MetricKey = "annualized" | "sharpe" | "drawdown" | "winRate" | "evidence";
type FormulaKey = "priceReturn" | "coreBlend" | "rankScore" | "sourceBlend" | "netReturn" | "equalFive" | "momentumGate" | "volatilityRatio" | "stockCap" | "turnover" | "baseLeader" | "cashSpread" | "equalTwenty" | "cashGate" | "netCost" | "signalBlend" | "sectorCap" | "outerGate" | "residualScore" | "controlledBlend" | "leverageFinancing" | "fragileLeverage" | "calendarDelta" | "annualized" | "sharpe" | "drawdown" | "winRate" | "cagr";
type MethodStep = { number: string; label: string; title: string; description: string; formula: FormulaKey; note: string };
type StrategyMethodology = { summary: string; cadence: string; universe: string; steps: MethodStep[] };
export type DashboardViewName = "overview" | "performance" | "activity" | "rebalances" | "survival" | "methodology" | "guardrails";

const viewDetails: Record<DashboardViewName, { label: string; title: string; description: string; path: string }> = {
  overview: { label: "Overview", title: "Portfolio overview", description: "A clear read on performance, risk, and the portfolio’s latest systematic decision.", path: "/" },
  performance: { label: "Performance", title: "Performance", description: "Study the simulated equity curve, risk-adjusted results, and the complete current allocation.", path: "/performance" },
  activity: { label: "Daily activity", title: "Daily activity", description: "Inspect daily P&L, historical holdings, and every recorded change in the strategy book.", path: "/activity" },
  rebalances: { label: "Rebalances", title: "Rebalances", description: "Review recent portfolio changes, turnover, and the strategy’s forward-validation clock.", path: "/rebalances" },
  survival: { label: "Survival lab", title: "Real-world survival lab", description: "See which strategies survive modeled stress, what still fails, and why none is proven live yet.", path: "/survival" },
  methodology: { label: "How it works", title: "How the portfolio works", description: "Follow the selected strategy from raw evidence to target weights, costs, and the final recorded decision.", path: "/methodology" },
  guardrails: { label: "Guardrails", title: "Research guardrails", description: "Understand exactly what the simulation can do, what it cannot do, and how its evidence is controlled.", path: "/guardrails" },
};

const methodologyByStrategy: Record<string, StrategyMethodology> = {
  "sec-residual-controlled-1.25x-5pct-v1": {
    summary: "The current recent-return leader combines the established dynamic portfolio with an independent residual-momentum sleeve, then applies a fixed 1.25x exposure assumption. The 20% sleeve weight and leverage choice were selected after observing the historical sample, so this remains frozen forward research rather than a promoted strategy.",
    cadence: "Quarterly residual selection · weekly targets · frozen 52-week forward clock",
    universe: "ETF core plus point-in-time SEC-screened U.S. companies",
    steps: [
      { number: "01", label: "CONTROL", title: "Keep the established dynamic leader", description: "Eighty percent begins with the existing ETF, growth, and cash-conversion leader. Its saved rules and costs are retained rather than retuned inside this experiment.", formula: "baseLeader", note: "The control remains the same portfolio used by the sealed residual-sleeve test." },
      { number: "02", label: "RESIDUAL", title: "Rank issuer-specific momentum", description: "The independent sleeve scores price strength left after separating broad market and sector effects, then selects twenty names under issuer and sector limits.", formula: "residualScore", note: "Signals are point-in-time and the execution schedule is carried forward from the sealed tournament inputs." },
      { number: "03", label: "BLEND", title: "Hold the fixed 80 / 20 mix", description: "The complete control portfolio receives 80% and the diversified residual sleeve receives 20%. No ticker-specific cap or Micron override is used.", formula: "controlledBlend", note: "The 20% choice is selection-contaminated; historical success cannot authorize promotion." },
      { number: "04", label: "EXPOSURE", title: "Apply 1.25x with explicit financing", description: "The combined portfolio is scaled to 125% gross exposure. The headline result assumes 5% annual financing on the borrowed 25%; an 8% financing stress is shown beside it.", formula: "leverageFinancing", note: "The corrected common-endpoint results are 150.86% at 5% financing and 149.01% at 8%." },
      { number: "05", label: "FALSIFY", title: "Keep the failed gate visible", description: "Costs, delays, missing-price stress, concentration, bootstrap evidence, and common-endpoint alignment are recorded. The multiplicity-adjusted statistical gate failed, so the strategy stays research-only.", formula: "netCost", note: "The frozen forward clock starts at zero and requires 52 untouched observations plus a separate review." },
    ],
  },
  "candidate-return-first-60-40-forward-v1": {
    summary: "A frozen ETF blend combines a pre-selected technology / HGB source with a retrospective rank-consensus source. The mix is fixed; the dashboard does not tune it after the fact.",
    cadence: "Frozen weekly decision record",
    universe: "Liquid ETFs plus BIL / cash",
    steps: [
      { number: "01", label: "INPUTS", title: "Read causal ETF prices", description: "Each decision uses the price history available by that date. Momentum and volatility calculations are shifted so the next return is never used to form today’s weight.", formula: "priceReturn", note: "k includes 4, 13, 26, and 52-week horizons in the rank-consensus source." },
      { number: "02", label: "BASE SOURCE", title: "Build the locked 60% core", description: "Sixty percent of the portfolio follows a source selected before the holdout: 70% XLK plus 30% from the embargoed HGB allocator.", formula: "coreBlend", note: "The base source itself receives 60% of the final portfolio." },
      { number: "03", label: "RANK SOURCE", title: "Score broad risk-on leadership", description: "Cross-sectional ranks across 4, 13, 26, and 52 weeks are averaged. The top positive candidate is selected, with inverse-volatility sizing used by the frozen source.", formula: "rankScore", note: "This 40% source was selected retrospectively and is explicitly labeled as hindsight evidence." },
      { number: "04", label: "COMBINE", title: "Blend without discretion", description: "The two complete source weight vectors are combined at fixed proportions. No manual asset overrides are applied in the dashboard.", formula: "sourceBlend", note: "If the sources hold cash or defensive ETFs, those weights remain in the blend." },
      { number: "05", label: "ACCOUNT", title: "Charge turnover and record", description: "A cost is deducted whenever the target vector changes, then the next period return is compounded into wealth.", formula: "netReturn", note: "Turnover is one-half of the sum of absolute weight changes." },
    ],
  },
  "sec-growth-survivorship-aware-v1": {
    summary: "A quarterly SEC-fundamental top-five sleeve is sized against the ETF incumbent using lagged relative momentum, breadth, concentration, and volatility checks.",
    cadence: "Quarterly selection · weekly risk review",
    universe: "SEC-screened U.S. companies",
    steps: [
      { number: "01", label: "SCREEN", title: "Select five filing-based leaders", description: "The strategy reads point-in-time SEC filing evidence, maps eligible companies to survivorship-aware price histories, and holds the five selected names at equal target weights inside the growth sleeve.", formula: "equalFive", note: "When a selected price is unavailable in the displayed base case, that portion stays in cash." },
      { number: "02", label: "CONFIRM", title: "Compare 26-week momentum", description: "The growth sleeve receives 40% only when its prior 26-week return is positive and beats the ETF incumbent; otherwise its base allocation is 10%.", formula: "momentumGate", note: "All return inputs are shifted one decision to preserve causality." },
      { number: "03", label: "STRESS CHECK", title: "Test breadth and volatility", description: "An exceptional 60% allocation also requires positive prior 13-week sleeve momentum, at least three positive holdings, a 13-to-52-week volatility ratio no greater than 1.5, and no single winner supplying more than 60% of positive momentum.", formula: "volatilityRatio", note: "Every exceptional condition must pass at the same decision." },
      { number: "04", label: "CAP", title: "Limit stock drift", description: "At weekly reviews, each growth stock is capped at 1.5 times its current equal-weight share of the sleeve; excess weight returns to the ETF incumbent.", formula: "stockCap", note: "The cap is ticker-agnostic and responds to the current sleeve allocation." },
      { number: "05", label: "ACCOUNT", title: "Rebalance, cost, compound", description: "Quarterly selection resets, allocation changes, and cap events create turnover. The simulation deducts 50 basis points per unit of turnover before compounding.", formula: "turnover", note: "This strategy remains a falsification-failed forward shadow, not a live mandate." },
    ],
  },
  "sec-cash-conversion-breadth20-dynamic-v1": {
    summary: "The research leader combines the ETF / growth portfolio with a diversified cash-conversion sleeve that turns on only after a lagged relative-return gate passes.",
    cadence: "Quarterly stock ranks · weekly allocation gate · daily audit",
    universe: "ETF core plus SEC-screened U.S. companies",
    steps: [
      { number: "01", label: "BASE", title: "Start with the frozen leader", description: "The base side combines the ETF incumbent and the dynamically sized SEC growth sleeve. Its internal rules remain unchanged before the cash-conversion overlay is considered.", formula: "baseLeader", note: "This preserves the existing leader rather than re-optimizing it inside the overlay." },
      { number: "02", label: "FUNDAMENTALS", title: "Measure cash conversion", description: "Companies are scored with operating cash-flow margin, free cash-flow margin, and the spread between operating cash flow and net income, scaled by quarterly revenue.", formula: "cashSpread", note: "The inputs come from point-in-time quarterly filings." },
      { number: "03", label: "SELECT", title: "Diversify across twenty names", description: "The top 20 sector-neutral scores are selected quarterly and equal weighted inside the independent sleeve.", formula: "equalTwenty", note: "At a 50% outer allocation, a new name begins near 2.5% of the total portfolio." },
      { number: "04", label: "GATE", title: "Require lagged relative strength", description: "The cash-conversion sleeve receives 50% only when its shifted prior 11-week return is both positive and higher than the base leader’s; otherwise it receives 0%.", formula: "cashGate", note: "The signal is lagged one week. No leverage and no short positions are allowed." },
      { number: "05", label: "VERIFY", title: "Audit execution daily", description: "Weights are marked with daily adjusted closes, including dividends and splits. The saved result charges 50 basis points and was separately stressed with one- and two-session delays and higher costs.", formula: "netCost", note: "The dashboard’s 102% evidence card comes from this daily execution audit." },
    ],
  },
  "sec-sector-aware-signal-ensemble-v1": {
    summary: "A deliberately preserved high-return diagnostic blends two diversified, filing-based stock rankings and places that sleeve beside the existing ETF / growth leader only when a lagged regime gate allows it. It did not pass every falsification gate.",
    cadence: "Quarterly stock ranks · weekly allocation gate",
    universe: "ETF core plus point-in-time SEC-screened companies",
    steps: [
      { number: "01", label: "BASE", title: "Keep the established leader", description: "The leader side retains the frozen ETF incumbent and its dynamically sized SEC growth sleeve. This experiment does not rewrite those underlying rules.", formula: "baseLeader", note: "The leader receives all capital whenever the independent sleeve gate is off." },
      { number: "02", label: "SIGNALS", title: "Blend two fundamental rankings", description: "One ranking uses cash conversion alone; the second uses 80% cash conversion and 20% balance-sheet quality. Their complete holdings vectors are mixed equally.", formula: "signalBlend", note: "The blend is across portfolios, not a discretionary stock override." },
      { number: "03", label: "DIVERSIFY", title: "Apply generic sector limits", description: "Each ranked cohort is filled from highest score downward subject to its saved sector limit. The rule is sector-based and never names Micron or any other company.", formula: "sectorCap", note: "The selected diagnostic used an 80% cash-ranking cap and a 90% balance-ranking cap." },
      { number: "04", label: "ALLOCATE", title: "Use the lagged weekly gate", description: "The independent sleeve is introduced only after the saved breadth and relative-strength conditions permit it; otherwise the established leader remains at 100%.", formula: "outerGate", note: "Inputs are lagged. No leverage or short positions are used." },
      { number: "05", label: "FALSIFY", title: "Keep the failure visible", description: "The simulation deducts turnover costs and records execution-delay, endpoint, bootstrap, and missing-issuer tests. The attractive return remains visible, but it is not a replacement strategy.", formula: "netCost", note: "Bootstrap confidence and the five-issuer stress missed the required thresholds." },
    ],
  },
  "sec-sector-ensemble-fragile-1.35x-v1": {
    summary: "This view preserves the highest exact-daily return ceiling discovered so far. It applies fixed 1.35x exposure to the sector-aware filing ensemble, but the source strategy failed its five-issuer and bootstrap falsification gates. It is intentionally shown as fragile research, not as the current strategy.",
    cadence: "Quarterly stock ranks · weekly allocation gate · exact daily accounting",
    universe: "ETF core plus point-in-time SEC-screened U.S. companies",
    steps: [
      { number: "01", label: "SOURCE", title: "Start with the sector-aware ensemble", description: "The underlying portfolio combines cash conversion and balance-sheet quality rankings beside the established dynamic leader.", formula: "signalBlend", note: "The source produced strong recent returns but did not pass complete issuer-dependence falsification." },
      { number: "02", label: "DIVERSIFY", title: "Retain generic sector limits", description: "The saved construction applies the same sector-based limits to every company and never names Micron or any other issuer.", formula: "sectorCap", note: "Generic limits reduced simple concentration but did not eliminate joint dependence on the best issuers." },
      { number: "03", label: "ALLOCATE", title: "Use the lagged outer gate", description: "The independent filing sleeve enters only when its saved causal gate permits it; otherwise capital remains with the established leader.", formula: "outerGate", note: "No future return is used to form the weekly allocation." },
      { number: "04", label: "AMPLIFY", title: "Apply fixed 1.35x exposure", description: "The complete portfolio is scaled to 135% and charged 6% annual financing on the borrowed 35%, plus an exposure-change cost.", formula: "fragileLeverage", note: "This layer lifts the trailing result to 174.97%, while also increasing exact-daily drawdown to 24.43%." },
      { number: "05", label: "REJECT", title: "Do not promote the ceiling", description: "The leverage layer passed its narrow daily checks, but leverage cannot repair a weak underlying issuer test. The candidate therefore remains ineligible for forward promotion.", formula: "netCost", note: "Failed robustness is part of the strategy label and remains visible throughout the dashboard." },
    ],
  },
};

const mathMarkup: Record<FormulaKey, { label: string; markup: string }> = {
  priceReturn: { label: "k-period return equals price at t divided by price at t minus k, minus one", markup: `<math display="block"><mrow><msub><mi>r</mi><mi>k</mi></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mfrac><mrow><mi>P</mi><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo></mrow><mrow><mi>P</mi><mo stretchy="false">(</mo><mi>t</mi><mo>−</mo><mi>k</mi><mo stretchy="false">)</mo></mrow></mfrac><mo>−</mo><mn>1</mn></mrow></math>` },
  coreBlend: { label: "core weight equals seventy percent XLK weight plus thirty percent HGB weight", markup: `<math display="block"><mrow><msub><mi>w</mi><mtext>core</mtext></msub><mo>=</mo><mn>0.70</mn><mo>·</mo><msub><mi>w</mi><mtext>XLK</mtext></msub><mo>+</mo><mn>0.30</mn><mo>·</mo><msub><mi>w</mi><mtext>HGB</mtext></msub></mrow></math>` },
  rankScore: { label: "asset score equals one quarter times the sum of its ranks over four, thirteen, twenty-six, and fifty-two weeks", markup: `<math display="block"><mrow><msub><mi>s</mi><mi>i</mi></msub><mo>=</mo><mfrac><mn>1</mn><mn>4</mn></mfrac><munder><mo>∑</mo><mrow><mi>h</mi><mo>∈</mo><mo>{</mo><mn>4</mn><mo>,</mo><mn>13</mn><mo>,</mo><mn>26</mn><mo>,</mo><mn>52</mn><mo>}</mo></mrow></munder><msub><mtext>rank</mtext><mrow><mi>i</mi><mo>,</mo><mi>h</mi></mrow></msub></mrow></math>` },
  sourceBlend: { label: "portfolio weight equals sixty percent core weight plus forty percent rank weight", markup: `<math display="block"><mrow><mi>w</mi><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>=</mo><mn>0.60</mn><mo>·</mo><msub><mi>w</mi><mtext>core</mtext></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo><mo>+</mo><mn>0.40</mn><mo>·</mo><msub><mi>w</mi><mtext>rank</mtext></msub><mo stretchy="false">(</mo><mi>t</mi><mo stretchy="false">)</mo></mrow></math>` },
  netReturn: { label: "net return equals gross return minus zero point zero zero five times turnover", markup: `<math display="block"><mrow><msub><mi>r</mi><mtext>net</mtext></msub><mo>=</mo><msub><mi>r</mi><mtext>gross</mtext></msub><mo>−</mo><mn>0.005</mn><mo>·</mo><mi>T</mi></mrow></math>` },
  equalFive: { label: "each growth sleeve weight equals one fifth or twenty percent", markup: `<math display="block"><mrow><msub><mi>w</mi><mi>i</mi></msub><mo>=</mo><mfrac><mn>1</mn><mn>5</mn></mfrac><mo>=</mo><mn>20</mn><mo>%</mo></mrow></math>` },
  momentumGate: { label: "high allocation when twenty-six-week growth return is positive and greater than the ETF return", markup: `<math display="block"><mrow><msub><mtext>High</mtext><mi>t</mi></msub><mo>=</mo><mo>[</mo><msub><mi>R</mi><mrow><mi>g</mi><mo>,</mo><mn>26</mn></mrow></msub><mo>&gt;</mo><mn>0</mn><mo>]</mo><mo>∧</mo><mo>[</mo><msub><mi>R</mi><mrow><mi>g</mi><mo>,</mo><mn>26</mn></mrow></msub><mo>&gt;</mo><msub><mi>R</mi><mrow><mtext>ETF</mtext><mo>,</mo><mn>26</mn></mrow></msub><mo>]</mo></mrow></math>` },
  volatilityRatio: { label: "thirteen-week volatility divided by fifty-two-week volatility is at most one point five", markup: `<math display="block"><mrow><mfrac><msub><mi>σ</mi><mn>13</mn></msub><msub><mi>σ</mi><mn>52</mn></msub></mfrac><mo>≤</mo><mn>1.5</mn></mrow></math>` },
  stockCap: { label: "asset cap equals one point five times the growth allocation divided by five", markup: `<math display="block"><mrow><msub><mtext>cap</mtext><mi>i</mi></msub><mo>=</mo><mn>1.5</mn><mo>×</mo><mfrac><msub><mi>A</mi><mtext>growth</mtext></msub><mn>5</mn></mfrac></mrow></math>` },
  turnover: { label: "turnover equals one half the sum of absolute target-weight changes", markup: `<math display="block"><mrow><msub><mi>T</mi><mi>t</mi></msub><mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><munder><mo>∑</mo><mi>i</mi></munder><mo>|</mo><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi></mrow></msub><mo>−</mo><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi><mo>−</mo><mn>1</mn></mrow></msub><mo>|</mo></mrow></math>` },
  baseLeader: { label: "base weight is the combined ETF and growth-leader weight vector", markup: `<math display="block"><mrow><msub><mi>w</mi><mtext>base</mtext></msub><mo>=</mo><msub><mi>w</mi><mtext>ETF</mtext></msub><mo>⊕</mo><msub><mi>w</mi><mtext>growth</mtext></msub></mrow></math>` },
  cashSpread: { label: "cash conversion spread equals operating cash flow minus net income, divided by revenue", markup: `<math display="block"><mrow><mtext>spread</mtext><mo>=</mo><mfrac><mrow><mtext>OCF</mtext><mo>−</mo><mtext>net income</mtext></mrow><mtext>revenue</mtext></mfrac></mrow></math>` },
  equalTwenty: { label: "each cash-conversion sleeve weight equals one twentieth or five percent", markup: `<math display="block"><mrow><msub><mi>w</mi><mi>i</mi></msub><mo>=</mo><mfrac><mn>1</mn><mn>20</mn></mfrac><mo>=</mo><mn>5</mn><mo>%</mo></mrow></math>` },
  cashGate: { label: "cash sleeve gate passes when its eleven-week return is positive and greater than the base return", markup: `<math display="block"><mrow><msub><mtext>Gate</mtext><mi>t</mi></msub><mo>=</mo><mo>[</mo><msub><mi>R</mi><mrow><mtext>cash</mtext><mo>,</mo><mn>11</mn></mrow></msub><mo>&gt;</mo><mn>0</mn><mo>]</mo><mo>∧</mo><mo>[</mo><msub><mi>R</mi><mrow><mtext>cash</mtext><mo>,</mo><mn>11</mn></mrow></msub><mo>&gt;</mo><msub><mi>R</mi><mrow><mtext>base</mtext><mo>,</mo><mn>11</mn></mrow></msub><mo>]</mo></mrow></math>` },
  netCost: { label: "net return equals gross return minus cost, where cost equals zero point zero zero five times turnover", markup: `<math display="block"><mtable columnalign="center"><mtr><mtd><msub><mi>r</mi><mtext>net</mtext></msub><mo>=</mo><msub><mi>r</mi><mtext>gross</mtext></msub><mo>−</mo><mi>C</mi></mtd></mtr><mtr><mtd><mi>C</mi><mo>=</mo><mn>0.005</mn><mo>·</mo><mi>T</mi></mtd></mtr></mtable></math>` },
  signalBlend: { label: "signal sleeve weight equals one half cash conversion portfolio plus one half balance quality portfolio", markup: `<math display="block"><mrow><msub><mi>w</mi><mtext>signal</mtext></msub><mo>=</mo><mn>0.50</mn><mo>·</mo><msub><mi>w</mi><mtext>cash</mtext></msub><mo>+</mo><mn>0.50</mn><mo>·</mo><msub><mi>w</mi><mtext>balance</mtext></msub></mrow></math>` },
  sectorCap: { label: "selected names in a sector cannot exceed the floor of sector cap times portfolio breadth", markup: `<math display="block"><mrow><msub><mi>N</mi><mtext>sector</mtext></msub><mo>≤</mo><mo>⌊</mo><msub><mi>c</mi><mtext>sector</mtext></msub><mo>·</mo><mi>B</mi><mo>⌋</mo></mrow></math>` },
  outerGate: { label: "portfolio weight equals leader allocation times leader weights plus signal allocation times signal weights", markup: `<math display="block"><mrow><mi>w</mi><mo>=</mo><mo stretchy="false">(</mo><mn>1</mn><mo>−</mo><mi>A</mi><mo stretchy="false">)</mo><msub><mi>w</mi><mtext>leader</mtext></msub><mo>+</mo><mi>A</mi><msub><mi>w</mi><mtext>signal</mtext></msub></mrow></math>` },
  residualScore: { label: "residual score equals seventy percent sector residual momentum plus thirty percent market residual momentum", markup: `<math display="block"><mrow><msub><mi>s</mi><mtext>residual</mtext></msub><mo>=</mo><mn>0.70</mn><mo>·</mo><msub><mi>R</mi><mtext>sector residual</mtext></msub><mo>+</mo><mn>0.30</mn><mo>·</mo><msub><mi>R</mi><mtext>market residual</mtext></msub></mrow></math>` },
  controlledBlend: { label: "controlled portfolio weight equals eighty percent control plus twenty percent residual sleeve", markup: `<math display="block"><mrow><msub><mi>w</mi><mtext>blend</mtext></msub><mo>=</mo><mn>0.80</mn><mo>·</mo><msub><mi>w</mi><mtext>control</mtext></msub><mo>+</mo><mn>0.20</mn><mo>·</mo><msub><mi>w</mi><mtext>residual</mtext></msub></mrow></math>` },
  leverageFinancing: { label: "levered return equals one point two five times portfolio return minus borrowed quarter times annual financing divided by fifty two", markup: `<math display="block"><mrow><msub><mi>r</mi><mtext>levered</mtext></msub><mo>=</mo><mn>1.25</mn><mo>·</mo><msub><mi>r</mi><mtext>blend</mtext></msub><mo>−</mo><mn>0.25</mn><mo>·</mo><mfrac><msub><mi>f</mi><mtext>annual</mtext></msub><mn>52</mn></mfrac></mrow></math>` },
  fragileLeverage: { label: "levered return equals one point three five times source return minus borrowed thirty-five percent times six percent financing divided by two hundred fifty-two", markup: `<math display="block"><mrow><msub><mi>r</mi><mtext>levered</mtext></msub><mo>=</mo><mn>1.35</mn><mo>·</mo><msub><mi>r</mi><mtext>source</mtext></msub><mo>−</mo><mn>0.35</mn><mo>·</mo><mfrac><mn>0.06</mn><mn>252</mn></mfrac></mrow></math>` },
  calendarDelta: { label: "change in asset weight equals current weight minus prior weight", markup: `<math display="block"><mrow><mi>Δ</mi><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi></mrow></msub><mo>=</mo><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi></mrow></msub><mo>−</mo><msub><mi>w</mi><mrow><mi>i</mi><mo>,</mo><mi>t</mi><mo>−</mo><mn>1</mn></mrow></msub></mrow></math>` },
  annualized: { label: "annualized return equals compounded daily returns raised to two hundred fifty-two divided by the observation count, minus one", markup: `<math display="block"><mrow><msub><mi>R</mi><mtext>ann</mtext></msub><mo>=</mo><msup><mrow><mo>[</mo><munderover><mo>∏</mo><mrow><mi>t</mi><mo>=</mo><mn>1</mn></mrow><mi>N</mi></munderover><mo stretchy="false">(</mo><mn>1</mn><mo>+</mo><msub><mi>r</mi><mi>t</mi></msub><mo stretchy="false">)</mo><mo>]</mo></mrow><mfrac><mn>252</mn><mi>N</mi></mfrac></msup><mo>−</mo><mn>1</mn></mrow></math>` },
  sharpe: { label: "Sharpe ratio equals mean daily return divided by daily standard deviation, multiplied by the square root of two hundred fifty-two", markup: `<math display="block"><mrow><mi>S</mi><mo>=</mo><mfrac><mrow><mtext>mean</mtext><mo stretchy="false">(</mo><msub><mi>r</mi><mi>d</mi></msub><mo stretchy="false">)</mo></mrow><mrow><mi>σ</mi><mo stretchy="false">(</mo><msub><mi>r</mi><mi>d</mi></msub><mo stretchy="false">)</mo></mrow></mfrac><mo>×</mo><msqrt><mn>252</mn></msqrt></mrow></math>` },
  drawdown: { label: "maximum drawdown is the minimum of portfolio value divided by its running peak minus one", markup: `<math display="block"><mrow><mtext>MDD</mtext><mo>=</mo><munder><mo>min</mo><mi>t</mi></munder><mo>[</mo><mfrac><msub><mi>V</mi><mi>t</mi></msub><munder><mo>max</mo><mrow><mi>u</mi><mo>≤</mo><mi>t</mi></mrow></munder><msub><mi>V</mi><mi>u</mi></msub></mfrac><mo>−</mo><mn>1</mn><mo>]</mo></mrow></math>` },
  winRate: { label: "win rate equals the count of positive non-zero sessions divided by the count of all non-zero sessions", markup: `<math display="block"><mrow><mtext>Win rate</mtext><mo>=</mo><mfrac><mrow><mi>N</mi><mo stretchy="false">(</mo><mi>r</mi><mo>&gt;</mo><mn>0</mn><mo stretchy="false">)</mo></mrow><mrow><mi>N</mi><mo stretchy="false">(</mo><mi>r</mi><mo>≠</mo><mn>0</mn><mo stretchy="false">)</mo></mrow></mfrac></mrow></math>` },
  cagr: { label: "compound annual growth rate equals ending wealth divided by starting wealth, raised to one over years, minus one", markup: `<math display="block"><mrow><mtext>CAGR</mtext><mo>=</mo><msup><mrow><mo>(</mo><mfrac><msub><mi>V</mi><mtext>end</mtext></msub><msub><mi>V</mi><mtext>start</mtext></msub></mfrac><mo>)</mo></mrow><mfrac><mn>1</mn><mi>Y</mi></mfrac></msup><mo>−</mo><mn>1</mn></mrow></math>` },
};

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });
const compactMoney = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const holdingColors = ["#8d7dff", "#7187ff", "#5fa8ff", "#50c8b1", "#c084fc", "#f4b860", "#fb7185", "#7f8797"];

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

function positionSpotlight(event: MouseEvent<HTMLElement>) {
  const bounds = event.currentTarget.getBoundingClientRect();
  event.currentTarget.style.setProperty("--spotlight-x", `${event.clientX - bounds.left}px`);
  event.currentTarget.style.setProperty("--spotlight-y", `${event.clientY - bounds.top}px`);
}

function MathEquation({ formula }: { formula: FormulaKey }) {
  const equation = mathMarkup[formula];
  return <div className="math-equation" role="math" aria-label={equation.label} dangerouslySetInnerHTML={{ __html: equation.markup }} />;
}

export function ReturnFirstDashboard({ initialView = "overview" }: { initialView?: DashboardViewName }) {
  const [bundle, setBundle] = useState<DashboardBundle | null>(null);
  const [survivalBundle, setSurvivalBundle] = useState<SurvivalBundle | null>(null);
  const [activeStrategy, setActiveStrategy] = useState("sec-residual-controlled-1.25x-5pct-v1");
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/return-first-dashboard.json")
      .then((response) => {
        if (!response.ok) throw new Error("Dashboard snapshot is unavailable");
        return response.json() as Promise<DashboardBundle>;
      })
      .then(setBundle)
      .catch(() => setError(true));
    fetch("/strategy-survival.json")
      .then((response) => response.ok ? response.json() as Promise<SurvivalBundle> : null)
      .then((payload) => payload && setSurvivalBundle(payload))
      .catch(() => undefined);
    const savedStrategy = window.localStorage.getItem("portfolio-optimizer-strategy-v2");
    if (savedStrategy) setActiveStrategy(savedStrategy);
  }, []);

  function changeStrategy(id: string) {
    setActiveStrategy(id);
    window.localStorage.setItem("portfolio-optimizer-strategy-v2", id);
  }

  if (error) return <main className="loading-state"><span>PORTFOLIO OPTIMIZER</span><h1>Research snapshot unavailable</h1><p>Rebuild the dashboard snapshot and refresh this page.</p></main>;
  if (!bundle) return <main className="loading-state"><span>PORTFOLIO OPTIMIZER</span><h1>Loading the research book…</h1></main>;
  const data = bundle.strategies.find((item) => item.strategy.id === activeStrategy) ?? bundle.strategies[0];
  return <DashboardView key={`${data.strategy.id}-${initialView}`} data={data} strategies={bundle.strategies} survivalBundle={survivalBundle} activeView={initialView} onStrategyChange={changeStrategy} />;
}

function DashboardView({ data, strategies, survivalBundle, activeView, onStrategyChange }: { data: DashboardPayload; strategies: DashboardPayload[]; survivalBundle: SurvivalBundle | null; activeView: DashboardViewName; onStrategyChange: (id: string) => void }) {
  const latest = data.records.at(-1)!;
  const latestDay = data.dailyRecords.at(-1)!;
  const firstHoldoutRecord = data.dailyRecords.find((row) => row.date > data.strategy.retrospectiveHoldout.start)?.date ?? data.strategy.retrospectiveHoldout.start;
  const [capital, setCapital] = useState(10_000);
  const [startDate, setStartDate] = useState(firstHoldoutRecord);
  const [selectedDate, setSelectedDate] = useState(latestDay.date);
  const [calendarDate, setCalendarDate] = useState(parseDate(latestDay.date));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [metricDetail, setMetricDetail] = useState<MetricKey | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [stockChart, setStockChart] = useState<{ symbol: string; endDate: string; source: "calendar" | "current" } | null>(null);

  const recordMap = useMemo(() => new Map(data.dailyRecords.map((row) => [row.date, row])), [data.dailyRecords]);
  const holdingsChangeDates = useMemo(
    () => new Set(data.records
      .filter((row) => row.holdings.some((holding) => Math.abs(holding.change ?? 0) > 1e-8))
      .map((row) => row.date)),
    [data.records],
  );
  const selected = recordMap.get(selectedDate) ?? latestDay;
  const selectedAllocation = useMemo(
    () => data.records.findLast((row) => row.date <= selectedDate) ?? data.records[0],
    [data.records, selectedDate],
  );
  const simulationRecords = useMemo(() => data.dailyRecords.filter((row) => row.date >= startDate), [data.dailyRecords, startDate]);
  const metrics = useMemo(() => portfolioMetrics(simulationRecords, capital), [simulationRecords, capital]);
  const selectedIndex = simulationRecords.findIndex((row) => row.date === selected.date);
  const selectedValue = selectedIndex >= 0 ? metrics.path[selectedIndex]?.value ?? capital : capital;
  const selectedStartValue = selectedValue / Math.max(1 + (selected.netReturn ?? 0), 1e-8);
  const allocationChangedToday = holdingsChangeDates.has(selected.date) && selectedAllocation.date === selected.date;
  const stockChartSeries = useMemo(
    () => stockChart ? (data.assetPrices[stockChart.symbol] ?? []).filter((row) => row.date <= stockChart.endDate) : [],
    [data.assetPrices, stockChart],
  );
  const stockStart = stockChartSeries[0];
  const stockEnd = stockChartSeries.at(-1);
  const stockChange = stockStart && stockEnd ? stockEnd.price / stockStart.price - 1 : 0;
  const attributionAllocation = useMemo(
    () => data.records.findLast((row) => row.date < selected.date) ?? data.records[0],
    [data.records, selected.date],
  );
  const holdingAttribution = useMemo(() => attributionAllocation.holdings
    .filter((holding) => (holding.weight ?? 0) > 1e-8)
    .map((holding) => {
      const weight = holding.weight ?? 0;
      if (holding.symbol === "cash::USD") return { symbol: holding.symbol, weight, assetReturn: 0, contribution: 0, dollar: 0, startPrice: null, endPrice: null };
      const prices = data.assetPrices[holding.symbol] ?? [];
      const priceIndex = prices.findIndex((point) => point.date === selected.date);
      if (priceIndex <= 0) return { symbol: holding.symbol, weight, assetReturn: null, contribution: null, dollar: null, startPrice: null, endPrice: null };
      const startPrice = prices[priceIndex - 1].price;
      const endPrice = prices[priceIndex].price;
      const assetReturn = startPrice ? endPrice / startPrice - 1 : null;
      const contribution = assetReturn === null ? null : weight * assetReturn;
      return { symbol: holding.symbol, weight, assetReturn, contribution, dollar: contribution === null ? null : selectedStartValue * contribution, startPrice, endPrice };
    })
    .sort((left, right) => Math.abs(right.contribution ?? 0) - Math.abs(left.contribution ?? 0)),
  [attributionAllocation.holdings, data.assetPrices, selected.date, selectedStartValue]);
  const attributedReturn = holdingAttribution.reduce((sum, row) => sum + (row.contribution ?? 0), 0);
  const attributionResidual = (selected.netReturn ?? 0) - attributedReturn;

  const currentHoldings = latest.holdings.filter((holding) => (holding.weight ?? 0) > 1e-8);
  const currentGrossExposure = currentHoldings.reduce((sum, holding) => sum + (holding.weight ?? 0), 0);
  let cumulativeAllocation = 0;
  const normalizedAllocationStops = currentHoldings.map((holding, index) => {
    const start = cumulativeAllocation / Math.max(currentGrossExposure, 1e-8) * 100;
    cumulativeAllocation += holding.weight ?? 0;
    const end = cumulativeAllocation / Math.max(currentGrossExposure, 1e-8) * 100;
    return `${holdingColors[index % holdingColors.length]} ${start}% ${end}%`;
  });
  const changedHoldings = selectedAllocation.holdings.filter((holding) => Math.abs(holding.change ?? 0) > 1e-8);
  const recentRebalances = useMemo(
    () => data.records
      .filter((row) => row.holdings.some((holding) => Math.abs(holding.change ?? 0) > 1e-8))
      .slice(-7)
      .reverse(),
    [data.records],
  );
  const activeViewDetails = viewDetails[activeView];
  const methodology = methodologyByStrategy[data.strategy.id] ?? methodologyByStrategy["candidate-return-first-60-40-forward-v1"];
  const latestChange = recentRebalances[0];
  const latestChangeItems = latestChange?.holdings.filter((holding) => Math.abs(holding.change ?? 0) > 1e-8) ?? [];
  const recentTape = data.dailyRecords.filter((row) => row.tradingDay).slice(-20);
  const forwardProgress = Math.min(1, data.strategy.forward.observedWeeks / Math.max(data.strategy.forward.requiredWeeks, 1));
  const metricDetails: Record<MetricKey, { label: string; value: string; formula: FormulaKey; explanation: string; note: string }> = {
    annualized: {
      label: "Annualized return",
      value: pct(metrics.annualizedReturn, 1),
      formula: "annualized",
      explanation: "Compounds every return in your selected simulation window, then converts that growth rate to a 252-trading-day year.",
      note: `${simulationRecords.length} saved observations from ${startDate} through ${latestDay.date}.`,
    },
    sharpe: {
      label: "Sharpe ratio",
      value: metrics.sharpe.toFixed(2),
      formula: "sharpe",
      explanation: "Compares average daily return with daily variability. This research view uses a zero risk-free rate and does not imply future risk-adjusted performance.",
      note: "Calculated from trading-day observations in the selected simulation window.",
    },
    drawdown: {
      label: "Maximum drawdown",
      value: pct(metrics.maxDrawdown, 1),
      formula: "drawdown",
      explanation: "Finds the deepest peak-to-trough decline in the simulated portfolio value, including the full path between your chosen start and end dates.",
      note: "A drawdown is path-dependent: changing the window can change the result.",
    },
    winRate: {
      label: "Win rate",
      value: plainPct(metrics.winRate, 0),
      formula: "winRate",
      explanation: "Measures how often a session finished positive after excluding flat sessions. It says nothing about the size of wins versus losses.",
      note: "A high win rate can coexist with a poor return if losing sessions are much larger.",
    },
    evidence: {
      label: data.strategy.featuredMetric.label,
      value: pct(data.strategy.featuredMetric.value, 2),
      formula: "cagr",
      explanation: "This is the strategy’s saved headline research result, calculated from its frozen evidence window rather than your adjustable what-if window.",
      note: data.strategy.featuredMetric.note,
    },
  };

  useEffect(() => {
    if (activeView !== "activity") return;
    const requestedDate = new URLSearchParams(window.location.search).get("date");
    if (!requestedDate || !recordMap.has(requestedDate)) return;
    setSelectedDate(requestedDate);
    setCalendarDate(parseDate(requestedDate));
  }, [activeView, recordMap]);

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

  useEffect(() => {
    function handleEscape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setSettingsOpen(false);
      setMetricDetail(null);
      setStockChart(null);
      setMobileMenuOpen(false);
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, []);

  return (
    <main className={`dashboard-page ${sidebarCollapsed ? "nav-collapsed" : ""}`}>
      <button className="mobile-menu-button" onClick={() => setMobileMenuOpen(true)} aria-label="Open navigation"><Menu size={20} /></button>
      {mobileMenuOpen && <button className="mobile-menu-scrim" aria-label="Close navigation" onClick={() => setMobileMenuOpen(false)} />}
      <aside className={`side-menu ${mobileMenuOpen ? "mobile-open" : ""}`} aria-label="Portfolio navigation">
        <div className="brand-mark" aria-hidden="true"><span /><span /><span /></div>
        <div className="brand-copy"><strong>Portfolio</strong><span>Optimizer</span></div>
        <button className="collapse-button" onClick={() => setSidebarCollapsed((value) => !value)} aria-label={sidebarCollapsed ? "Expand navigation" : "Collapse navigation"}><PanelLeftClose size={17} /></button>
        <button className="mobile-close-button" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation"><X size={18} /></button>
        <nav>
          <Link className={activeView === "overview" ? "active" : ""} href="/" onClick={() => setMobileMenuOpen(false)}><Gauge size={18} /><span>Overview</span></Link>
          <Link className={activeView === "performance" ? "active" : ""} href="/performance" onClick={() => setMobileMenuOpen(false)}><PieChart size={18} /><span>Performance</span></Link>
          <Link className={activeView === "activity" ? "active" : ""} href="/activity" onClick={() => setMobileMenuOpen(false)}><CalendarDays size={18} /><span>Daily activity</span></Link>
          <Link className={activeView === "rebalances" ? "active" : ""} href="/rebalances" onClick={() => setMobileMenuOpen(false)}><History size={18} /><span>Rebalances</span></Link>
          <Link className={activeView === "survival" ? "active" : ""} href="/survival" onClick={() => setMobileMenuOpen(false)}><Siren size={18} /><span>Survival lab</span></Link>
          <Link className={activeView === "methodology" ? "active" : ""} href="/methodology" onClick={() => setMobileMenuOpen(false)}><Workflow size={18} /><span>How it works</span></Link>
          <Link className={activeView === "guardrails" ? "active" : ""} href="/guardrails" onClick={() => setMobileMenuOpen(false)}><ShieldCheck size={18} /><span>Guardrails</span></Link>
        </nav>
        <div className="side-note">
          <span><i /> Research environment</span>
          <p>Simulated results only. No brokerage or live order connection.</p>
        </div>
      </aside>

      <div className="dashboard-content">
      <div className="utility-bar">
        <div className="breadcrumbs"><span>Portfolio Optimizer</span><ChevronRight size={14} /><strong>{activeViewDetails.label}</strong></div>
        <div className="utility-actions">
          <span className="freshness"><i /> Data through {latestDay.date}</span>
          <span className="avatar" aria-label="Portfolio owner">NT</span>
        </div>
      </div>

      <div className="content-frame">
      <header className="topbar">
        <div className="title-block">
          <div className="eyebrow"><span className="status-dot" /> SYSTEMATIC RESEARCH BOOK</div>
          <h1>{activeViewDetails.title}</h1>
          <p>{activeViewDetails.description}</p>
        </div>
        <div className="headline-card spotlight-surface" onMouseMove={positionSpotlight}>
          <div className="portfolio-headline">
            <span className="micro-label">SIMULATED PORTFOLIO VALUE</span>
            <strong>{money.format(metrics.endValue)}</strong>
            <span className={metrics.profit >= 0 ? "gain" : "loss"}>{metrics.profit >= 0 ? "↑" : "↓"} {money.format(Math.abs(metrics.profit))} · {pct(metrics.totalReturn)}</span>
          </div>
          <button className="settings-button" onClick={() => setSettingsOpen(true)} aria-label="Open simulation settings">
            <Settings2 size={16} /> What if
          </button>
        </div>
      </header>

      <section className="strategy-toolbar spotlight-surface" onMouseMove={positionSpotlight} aria-label="Strategy selection and status">
        <label className="strategy-picker">
          <span>STRATEGY</span>
          <select value={data.strategy.id} onChange={(event) => onStrategyChange(event.target.value)}>
            {strategies.map((item) => <option key={item.strategy.id} value={item.strategy.id}>{item.strategy.shortName}</option>)}
          </select>
        </label>
        <div className="strategy-summary"><strong>{data.strategy.name}</strong><span>{data.strategy.subtitle}</span></div>
        <div className="strategy-tags">
          <span className="pill research"><FlaskConical size={13} /> Research only</span>
          <span className="pill">50 bps costs</span>
          <span className="pill strategy-badge">{data.strategy.badge}</span>
        </div>
      </section>

      {activeView === "overview" && <section className="overview-dashboard page-section">
        <div className="overview-lead-grid">
          <article className="panel overview-performance-hero aurora-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="overview-performance-copy">
              <span className="section-kicker gradient-copy">PORTFOLIO SIGNAL</span>
              <h2>{metrics.totalReturn >= 0 ? "Compounding ahead." : "Drawdown in progress."}</h2>
              <strong className={`shiny-number ${metrics.totalReturn >= 0 ? "gain" : "loss"}`}>{pct(metrics.totalReturn, 1)}</strong>
              <p>Total simulated return from {startDate} through {latestDay.date}, after the frozen cost model.</p>
              <div className="overview-stat-row">
                <span><small>ANNUALIZED</small><b>{pct(metrics.annualizedReturn, 1)}</b></span>
                <span><small>SHARPE</small><b>{metrics.sharpe.toFixed(2)}</b></span>
                <span><small>MAX DRAWDOWN</small><b className="loss">{pct(metrics.maxDrawdown, 1)}</b></span>
              </div>
              <Link href="/performance" className="overview-primary-link">Explore performance <ArrowUpRight size={15} /></Link>
            </div>
            <div className="overview-chart" aria-label="Recent simulated portfolio trajectory">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={metrics.path.slice(-252)} margin={{ top: 12, right: 0, left: 0, bottom: 0 }}>
                  <defs><linearGradient id="overviewFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#9b72ff" stopOpacity={0.42} /><stop offset="100%" stopColor="#7187ff" stopOpacity={0} /></linearGradient></defs>
                  <Area type="monotone" dataKey="value" stroke="#9c8aff" strokeWidth={2.4} fill="url(#overviewFill)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </article>

          <div className="overview-side-stack">
            <article className="panel overview-decision-card spotlight-surface" onMouseMove={positionSpotlight}>
              <div className="overview-card-icon"><History size={18} /></div>
              <span className="section-kicker">LATEST HOLDINGS CHANGE</span>
              <h3>{latestChange?.date ?? "No recorded change"}</h3>
              <p>{latestChange ? `${latestChangeItems.length} target weights moved with ${plainPct(latestChange.turnover ?? 0)} turnover.` : "The current saved record contains no target-weight change."}</p>
              <div className="change-symbol-cloud">{latestChangeItems.slice(0, 7).map((holding) => <span key={holding.symbol}>{holding.symbol.replace("cash::", "")}</span>)}{latestChangeItems.length > 7 && <span>+{latestChangeItems.length - 7}</span>}</div>
              {latestChange && <Link href={`/activity?date=${latestChange.date}`}>Inspect the decision <ChevronRight size={14} /></Link>}
            </article>
            <article className="panel overview-validation-card spotlight-surface" onMouseMove={positionSpotlight}>
              <div className="validation-ring" style={{ background: `conic-gradient(#8f7dff ${forwardProgress * 360}deg, #292b37 0deg)` }}><span><b>{data.strategy.forward.observedWeeks}</b><small>OF {data.strategy.forward.requiredWeeks}</small></span></div>
              <div><span className="section-kicker">FORWARD EVIDENCE</span><h3>{data.strategy.forward.observedWeeks ? "Validation underway" : "Clock not started"}</h3><p>{data.strategy.forward.note}</p><Link href="/guardrails">Review guardrails <ChevronRight size={14} /></Link></div>
            </article>
          </div>
        </div>

        <article className="panel market-tape spotlight-surface" onMouseMove={positionSpotlight}>
          <div><span className="section-kicker">RECENT DAILY TAPE</span><h3>Twenty-session pulse</h3><p>Color shows direction; bar height shows the size of the move.</p></div>
          <div className="tape-bars" aria-label="Twenty most recent daily returns">
            {recentTape.map((row) => {
              const value = row.netReturn ?? 0;
              return <Link key={row.date} href={`/activity?date=${row.date}`} title={`${row.date}: ${pct(value)}`} className={value >= 0 ? "up" : "down"}><i style={{ height: `${Math.max(7, Math.min(42, Math.abs(value) * 1800))}px` }} /><small>{parseDate(row.date).toLocaleDateString("en-US", { month: "short", day: "numeric" })}</small></Link>;
            })}
          </div>
        </article>

        <div className="overview-quick-grid">
          <Link href="/performance" className="panel overview-quick-card spotlight-surface" onMouseMove={positionSpotlight}><TrendingUp size={20} /><span><small>ANALYZE</small><strong>Performance laboratory</strong><p>Open the full equity curve, every metric, and current allocation.</p></span><ArrowUpRight size={16} /></Link>
          <Link href="/activity" className="panel overview-quick-card spotlight-surface" onMouseMove={positionSpotlight}><CalendarDays size={20} /><span><small>TRACE</small><strong>Daily attribution</strong><p>See which holdings drove each day and whether weights changed.</p></span><ArrowUpRight size={16} /></Link>
          <Link href="/methodology" className="panel overview-quick-card spotlight-surface" onMouseMove={positionSpotlight}><Workflow size={20} /><span><small>UNDERSTAND</small><strong>Strategy methodology</strong><p>Follow the screening, sizing, volatility, and cost equations.</p></span><ArrowUpRight size={16} /></Link>
        </div>
      </section>}

      {activeView === "performance" && <>
      <section className="metric-grid" aria-label="Strategy metrics">
        <button className="metric-card spotlight-surface" onMouseMove={positionSpotlight} onClick={() => setMetricDetail("annualized")} aria-label="Explain annualized return">
          <div className="metric-label"><span>Annualized return</span></div>
          <strong>{pct(metrics.annualizedReturn, 1)}</strong>
          <small>{startDate} — {latestDay.date}</small>
        </button>
        <button className="metric-card spotlight-surface" onMouseMove={positionSpotlight} onClick={() => setMetricDetail("sharpe")} aria-label="Explain Sharpe ratio">
          <div className="metric-label"><span>Sharpe ratio</span></div>
          <strong>{metrics.sharpe.toFixed(2)}</strong>
          <small>Daily · zero risk-free rate</small>
        </button>
        <button className="metric-card spotlight-surface" onMouseMove={positionSpotlight} onClick={() => setMetricDetail("drawdown")} aria-label="Explain maximum drawdown">
          <div className="metric-label"><span>Max drawdown</span></div>
          <strong>{pct(metrics.maxDrawdown, 1)}</strong>
          <small>Selected simulation window</small>
        </button>
        <button className="metric-card spotlight-surface" onMouseMove={positionSpotlight} onClick={() => setMetricDetail("winRate")} aria-label="Explain win rate">
          <div className="metric-label"><span>Win rate</span></div>
          <strong>{plainPct(metrics.winRate, 0)}</strong>
          <small>Positive non-zero sessions</small>
        </button>
        <button className="metric-card proof-card spotlight-surface" onMouseMove={positionSpotlight} onClick={() => setMetricDetail("evidence")} aria-label={`Explain ${data.strategy.featuredMetric.label}`}>
          <div className="metric-label"><span>{data.strategy.featuredMetric.label}</span></div>
          <strong>{pct(data.strategy.featuredMetric.value, 2)}</strong>
          <small>{data.strategy.featuredMetric.note}</small>
        </button>
        {data.strategy.cashOnlyMetric && <article className="metric-card cash-only-card spotlight-surface" onMouseMove={positionSpotlight} aria-label="Cash-only performance without financing">
          <div className="metric-label"><span>{data.strategy.cashOnlyMetric.label}</span></div>
          <strong>{pct(data.strategy.cashOnlyMetric.value, 2)}</strong>
          <small>Sharpe {data.strategy.cashOnlyMetric.sharpe.toFixed(2)} · drawdown {pct(data.strategy.cashOnlyMetric.maxDrawdown, 1)} · {data.strategy.cashOnlyMetric.note}</small>
        </article>}
      </section>

      <section className="section-block">
        <div className="section-heading"><div><span>PERFORMANCE</span><h2>Portfolio trajectory</h2></div><p>Net of the frozen 50-bps turnover cost model.</p></div>
        <div className="performance-grid">
          <article className="panel chart-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head">
              <div><span className="section-kicker">SIMULATED EQUITY CURVE</span><h3>Portfolio value</h3><p>{startDate} — {latestDay.date}</p></div>
              <span className={`trend-chip ${metrics.totalReturn >= 0 ? "up" : "down"}`}>{metrics.totalReturn >= 0 ? "↑" : "↓"} {pct(metrics.totalReturn)}</span>
            </div>
            <div className="chart-wrap">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={metrics.path} margin={{ top: 12, right: 8, left: 4, bottom: 0 }}>
                  <defs><linearGradient id="valueFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8d7dff" stopOpacity={0.34} /><stop offset="100%" stopColor="#7187ff" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid vertical={false} stroke="#292b37" />
                  <XAxis dataKey="date" minTickGap={55} tick={{ fill: "#7c7d8a", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(value) => parseDate(String(value)).toLocaleDateString("en-US", { month: "short", year: "2-digit" })} />
                  <YAxis domain={["auto", "auto"]} width={58} tick={{ fill: "#7c7d8a", fontSize: 10 }} tickLine={false} axisLine={false} tickFormatter={(value) => compactMoney.format(Number(value))} />
                  <Tooltip contentStyle={{ background: "rgba(19,20,27,.97)", border: "1px solid #393c4b", borderRadius: 10, boxShadow: "0 16px 40px rgba(0,0,0,.35)" }} formatter={(value) => [money.format(Number(value)), "Value"]} labelStyle={{ color: "#aaaab4" }} />
                  <Area type="monotone" dataKey="value" stroke="#8d7dff" strokeWidth={2.2} fill="url(#valueFill)" isAnimationActive={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="chart-stats"><span><small>STARTING VALUE</small>{money.format(capital)}</span><span><small>SIMULATED PROFIT</small><b className={metrics.profit >= 0 ? "gain" : "loss"}>{money.format(metrics.profit)}</b></span><span><small>TRADING DAYS</small>{simulationRecords.length}</span></div>
          </article>

          <article className="panel allocation-panel spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="panel-head"><div><span className="section-kicker">LATEST DECISION</span><h3>Current allocation</h3></div><span className="as-of">As of {data.strategy.asOf}</span></div>
            <div className="allocation-body">
              <div className="donut" style={{ background: `conic-gradient(${normalizedAllocationStops.join(",")})` }}>
                <div><strong>{currentHoldings.length}</strong><small>{plainPct(currentGrossExposure)} GROSS</small></div>
              </div>
              <div className="allocation-list">
                {currentHoldings.map((holding, index) => <button key={holding.symbol} disabled={!data.assetPrices[holding.symbol]?.length} onClick={() => openStockChart(holding.symbol, latestDay.date, "current")}><i style={{ background: holdingColors[index % holdingColors.length] }} /><b>{holding.symbol.replace("cash::", "")}</b><span>{plainPct(holding.weight ?? 0)}</span><small>{classification(holding.symbol)}</small></button>)}
              </div>
              {currentHoldings.length > 8 && <p className="allocation-scroll-note">All {currentHoldings.length} holdings are available in the scrollable list.</p>}
            </div>
          </article>
        </div>
      </section>
      </>}

      {activeView === "activity" && <section className="section-block page-section">
        <div className="section-heading"><div><span>DAILY ACTIVITY</span><h2>Decision calendar</h2></div><p>Select any recorded date to inspect P&amp;L, holdings, and allocation changes.</p></div>
        <div className="activity-grid">
        <article className="panel calendar-panel spotlight-surface" onMouseMove={positionSpotlight}>
          <div className="panel-head calendar-head">
            <div>
              <span className="section-kicker">DAILY P&amp;L</span>
              <h3>{monthNames[month]} {year}</h3>
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
          <div className="calendar-legend"><span><i className="legend-dot green" /> daily gain</span><span><i className="legend-dot red" /> daily loss</span><span><i className="legend-dot holdings-change" /> holdings changed</span></div>
          <div className="calendar-grid weekdays">{["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"].map((day) => <span key={day}>{day}</span>)}</div>
          <div className="calendar-grid days">
            {calendarCells.map((cell, index) => {
              if (!cell) return <span className="day-cell spacer" key={`blank-${index}`} />;
              const holdingsChanged = holdingsChangeDates.has(cell.key);
              return (
                <button
                  key={cell.key}
                  disabled={!cell.record}
                  onClick={() => cell.record && setSelectedDate(cell.key)}
                  className={`day-cell ${cell.record ? (cell.record.netReturn ?? 0) >= 0 ? "positive" : "negative" : "empty"} ${holdingsChanged ? "holdings-changed" : ""} ${selectedDate === cell.key ? "selected" : ""}`}
                >
                  <span>{cell.day}</span>
                  {cell.record && <strong className={(cell.record.netReturn ?? 0) >= 0 ? "positive-return" : "negative-return"}>{pct(cell.record.netReturn ?? 0, 2)}</strong>}
                  {holdingsChanged && <i className="rebalance-mark" title="Holdings changed" aria-label="Holdings changed" />}
                </button>
              );
            })}
          </div>
        </article>

        <article className="panel date-inspector spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="inspector-title">
              <div><span className="section-kicker">SELECTED DATE</span><h3>{formatDate(selected.date)}</h3></div>
              <div className="selected-pnl"><span>DAILY P&amp;L</span><strong className={(selected.netReturn ?? 0) >= 0 ? "gain" : "loss"}>{money.format(selectedStartValue * (selected.netReturn ?? 0))}</strong><small>{pct(selected.netReturn ?? 0)}</small></div>
            </div>

            <div className="daily-attribution">
              <div className="subsection-heading"><span className="section-kicker">HOLDING RETURN ATTRIBUTION</span><i>prior close → selected close</i></div>
              <p>Shows each opening holding’s market move and estimated contribution to the portfolio’s daily result.</p>
              <div className="attribution-list">
                <div className="attribution-row attribution-head"><span>HOLDING</span><span>WEIGHT</span><span>ASSET MOVE</span><span>PORTFOLIO IMPACT</span><span>P&amp;L</span></div>
                {holdingAttribution.map((row) => <div className="attribution-row" key={row.symbol}>
                  <span><button className="holding-link" disabled={!data.assetPrices[row.symbol]?.length} onClick={() => openStockChart(row.symbol, selected.date, "calendar")}><b>{row.symbol.replace("cash::", "")}</b><small>{row.startPrice !== null && row.endPrice !== null ? `${money.format(row.startPrice)} → ${money.format(row.endPrice)}` : classification(row.symbol)}</small></button></span>
                  <span>{plainPct(row.weight)}</span>
                  <span className={(row.assetReturn ?? 0) >= 0 ? "gain" : "loss"}>{row.assetReturn === null ? "—" : pct(row.assetReturn)}</span>
                  <span className={(row.contribution ?? 0) >= 0 ? "gain" : "loss"}>{row.contribution === null ? "—" : pct(row.contribution)}</span>
                  <strong className={(row.dollar ?? 0) >= 0 ? "gain" : "loss"}>{row.dollar === null ? "—" : money.format(row.dollar)}</strong>
                </div>)}
                {Math.abs(attributionResidual) > 1e-8 && <div className="attribution-row residual-row">
                  <span><b>Costs / model residual</b><small>Reconciles holding moves to saved net return</small></span><span>—</span><span>—</span><span className={attributionResidual >= 0 ? "gain" : "loss"}>{pct(attributionResidual)}</span><strong className={attributionResidual >= 0 ? "gain" : "loss"}>{money.format(selectedStartValue * attributionResidual)}</strong>
                </div>}
              </div>
            </div>
            <div className="holdings-table">
              <div className="table-row table-head"><span>HOLDING</span><span>WEIGHT</span><span>CHANGE</span><span>VALUE</span></div>
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
              <div className="subsection-heading"><span className="section-kicker">HOLDINGS CHANGE LOG</span>{allocationChangedToday && <i>{changedHoldings.length} changes</i>}</div>
              {allocationChangedToday ? changedHoldings.map((holding) => (
                <div className="trade-row" key={holding.symbol}>
                  <span className={`trade-badge ${changeLabel(holding).toLowerCase()}`}>{changeLabel(holding)}</span>
                  <button className="trade-symbol" disabled={!data.assetPrices[holding.symbol]?.length} onClick={() => openStockChart(holding.symbol, selected.date, "calendar")}>{holding.symbol.replace("cash::", "")}</button>
                  <span className="trade-transition">{plainPct((holding.weight ?? 0) - (holding.change ?? 0))} <i>→</i> <b>{plainPct(holding.weight ?? 0)}</b></span>
                  <strong>{money.format(Math.abs(selectedValue * (holding.change ?? 0)))}</strong>
                </div>
              )) : <p>No holdings changed on this strategy date.</p>}
            </div>
        </article>
        </div>
      </section>}

      {activeView === "rebalances" && <section className="section-block page-section">
        <div className="section-heading"><div><span>RESEARCH DETAILS</span><h2>Validation and controls</h2></div></div>
      <div className="bottom-grid">
        <article className="panel compact-panel spotlight-surface" onMouseMove={positionSpotlight}>
          <span className="section-kicker">RECENT HOLDINGS CHANGES</span><h2>Rebalance Activity</h2>
          <div className="activity-list">{recentRebalances.map((row) => {
            const changes = row.holdings.filter((holding) => Math.abs(holding.change ?? 0) > 1e-8);
            return <Link key={row.date} href={`/activity?date=${row.date}`}><span><b>{row.date}</b><small>{changes.length} changes · {plainPct(row.turnover ?? 0)} turnover</small></span><span>{changes.slice(0, 3).map((item) => item.symbol.replace("cash::", "")).join(" · ")}</span><ChevronRight size={16} /></Link>;
          })}</div>
        </article>
        <article className="panel compact-panel protocol-panel spotlight-surface" onMouseMove={positionSpotlight}>
          <span className="section-kicker">FORWARD VALIDATION CLOCK</span><h2>{data.strategy.forward.observedWeeks} / {data.strategy.forward.requiredWeeks} weeks observed</h2>
          <div className="progress-track"><i style={{ width: `${(data.strategy.forward.observedWeeks / data.strategy.forward.requiredWeeks) * 100}%` }} /></div>
          <p>First eligible realization: <b>{data.strategy.forward.firstRealization}</b>. {data.strategy.forward.note}</p>
        </article>
      </div>
      </section>}

      {activeView === "methodology" && <section className="section-block page-section methodology-page">
        <article className="panel methodology-hero spotlight-surface" onMouseMove={positionSpotlight}>
          <div className="methodology-hero-copy">
            <span className="section-kicker gradient-copy">FROM EVIDENCE TO WEIGHTS</span>
            <h2>One decision, fully traceable.</h2>
            <p>{methodology.summary}</p>
            <div className="methodology-meta">
              <span><small>CADENCE</small>{methodology.cadence}</span>
              <span><small>INVESTMENT UNIVERSE</small>{methodology.universe}</span>
              <span><small>EXECUTION STATE</small>Simulation only</span>
            </div>
          </div>
          <div className="methodology-orbit" aria-hidden="true">
            <span className="orbit orbit-one" /><span className="orbit orbit-two" />
            <div><Workflow size={28} /><small>RULES</small><strong>FROZEN</strong></div>
          </div>
        </article>

        <div className="methodology-heading">
          <div><span className="section-kicker">DECISION PIPELINE</span><h2>The strategy, step by step</h2></div>
          <p>Change the strategy above and this explanation changes with it.</p>
        </div>
        <ol className="methodology-flow">
          {methodology.steps.map((step) => <li key={step.number} className="panel methodology-step spotlight-surface" onMouseMove={positionSpotlight}>
            <div className="step-index"><span>{step.number}</span><i /></div>
            <div className="step-copy">
              <span className="section-kicker">{step.label}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </div>
            <div className="formula-block"><span>RULE / FORMULA</span><MathEquation formula={step.formula} /><small>{step.note}</small></div>
          </li>)}
        </ol>

        <div className="methodology-audit-grid">
          <article className="panel audit-explainer spotlight-surface" onMouseMove={positionSpotlight}>
            <span className="section-kicker">WHAT COUNTS AS A HOLDINGS CHANGE?</span>
            <h3>The weight vector must actually move.</h3>
            <p>A scheduled review or a generated trade-ledger row is not enough. The calendar now marks a change only when at least one saved target weight differs from the prior target.</p>
            <div className="formula-block compact"><span>CALENDAR TEST</span><MathEquation formula="calendarDelta" /><small>Show the white ring when any |Δwᵢ,t| &gt; 10⁻⁸.</small></div>
          </article>
          <article className="panel audit-explainer spotlight-surface" onMouseMove={positionSpotlight}>
            <span className="section-kicker">TWO INDEPENDENT SIGNALS</span>
            <h3>Color shows P&amp;L. The ring shows action.</h3>
            <p>Green or red answers whether the strategy gained or lost that day. A white outline and top-right ring separately answer whether the holdings changed.</p>
            <div className="signal-key"><span className="gain-swatch">GAIN</span><span className="loss-swatch">LOSS</span><span className="change-swatch"><i /> HOLDINGS CHANGED</span></div>
          </article>
        </div>
      </section>}

      {activeView === "guardrails" && <section className="section-block page-section guardrails-page">
        <div className="guardrail-hero panel aurora-panel spotlight-surface" onMouseMove={positionSpotlight}>
          <div>
            <span className="section-kicker">OPERATING STATE</span>
            <h2>Research environment only</h2>
            <p>This dashboard is deliberately separated from execution. It can inspect saved evidence and simulate scenarios, but it cannot connect to a broker, place an order, or move money.</p>
          </div>
          <span className="guardrail-status"><i /> Live trading disabled</span>
        </div>
        <div className="guardrail-grid">
          <article className="panel guardrail-card spotlight-surface" onMouseMove={positionSpotlight}><span>01</span><div><h3>Execution boundary</h3><p>No brokerage credentials, order-routing endpoints, or automated trade actions are present.</p></div><strong>DISCONNECTED</strong></article>
          <article className="panel guardrail-card spotlight-surface" onMouseMove={positionSpotlight}><span>02</span><div><h3>Cost model</h3><p>Every simulated rebalance includes {data.strategy.disclosures.costBps} basis points of cost per unit of turnover.</p></div><strong>{data.strategy.disclosures.costBps} BPS</strong></article>
          <article className="panel guardrail-card spotlight-surface" onMouseMove={positionSpotlight}><span>03</span><div><h3>Return convention</h3><p>{data.strategy.disclosures.returnConvention}</p></div><strong>FROZEN</strong></article>
          <article className="panel guardrail-card spotlight-surface" onMouseMove={positionSpotlight}><span>04</span><div><h3>Evidence integrity</h3><p>The selected formula is frozen after selection; post-selection changes are not blended into the saved record.</p></div><strong>CONTROLLED</strong></article>
          <article className="panel guardrail-card spotlight-surface" onMouseMove={positionSpotlight}><span>05</span><div><h3>Forward validation</h3><p>{data.strategy.forward.observedWeeks} of {data.strategy.forward.requiredWeeks} required weeks have been observed. First eligible realization: {data.strategy.forward.firstRealization}.</p></div><strong>{data.strategy.forward.status.toUpperCase()}</strong></article>
          <article className="panel guardrail-card spotlight-surface" onMouseMove={positionSpotlight}><span>06</span><div><h3>Research disclosure</h3><p>Past simulated performance is not a promise of future returns and should not be read as investment advice.</p></div><strong>RESEARCH ONLY</strong></article>
        </div>
      </section>}

      {activeView === "survival" && <section className="section-block page-section survival-page">
        {!survivalBundle ? <article className="panel survival-loading"><span className="section-kicker">SURVIVAL EVIDENCE</span><h2>Loading the frozen stress results&hellip;</h2><p>The performance dashboard remains available while the separate survival artifact loads.</p></article> : (
          <SurvivalLab
            bundle={survivalBundle as unknown as SurvivalBundlePayload}
            selectedId={data.strategy.id}
            onSelect={onStrategyChange}
            positionSpotlight={positionSpotlight}
          />
        )}
      </section>}

      <footer>
          <span>Data through {latestDay.date} · daily P&amp;L from weekly strategy decisions</span>
        <span>Past simulated performance does not guarantee future returns.</span>
      </footer>
      </div>
      </div>

      {metricDetail && <div className="modal-backdrop metric-modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setMetricDetail(null)}>
        <aside className="metric-dialog spotlight-surface" onMouseMove={positionSpotlight} role="dialog" aria-modal="true" aria-labelledby="metric-dialog-title">
          <button className="close-button" onClick={() => setMetricDetail(null)} aria-label="Close metric explanation"><X size={18} /></button>
          <span className="section-kicker">METRIC EXPLAINER</span>
          <h2 id="metric-dialog-title">{metricDetails[metricDetail].label}</h2>
          <strong className="metric-dialog-value">{metricDetails[metricDetail].value}</strong>
          <p>{metricDetails[metricDetail].explanation}</p>
          <div className="metric-formula"><span>FORMULA</span><MathEquation formula={metricDetails[metricDetail].formula} /></div>
          <div className="metric-note"><Info size={16} /><p>{metricDetails[metricDetail].note}</p></div>
          <Link href="/methodology" onClick={() => setMetricDetail(null)} className="metric-method-link">See the full portfolio method <ChevronRight size={15} /></Link>
        </aside>
      </div>}

      {settingsOpen && <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setSettingsOpen(false)}>
        <aside className="settings-drawer" role="dialog" aria-modal="true" aria-label="Simulation settings">
          <button className="close-button" onClick={() => setSettingsOpen(false)} aria-label="Close simulation settings"><X size={18} /></button>
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
        <aside className="settings-drawer stock-drawer" role="dialog" aria-modal="true" aria-label={`${stockChart.symbol} historical price chart`}>
          <button className="close-button" onClick={() => setStockChart(null)} aria-label="Close historical price chart"><X size={18} /></button>
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
                  <defs><linearGradient id="stockPriceFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#0a6cff" stopOpacity={0.24} /><stop offset="100%" stopColor="#0a6cff" stopOpacity={0} /></linearGradient></defs>
                  <CartesianGrid vertical={false} stroke="#292b37" />
                  <XAxis dataKey="date" hide />
                  <YAxis domain={["dataMin", "dataMax"]} hide />
                  <Tooltip contentStyle={{ background: "rgba(19,20,27,.97)", border: "1px solid #393c4b", borderRadius: 10 }} formatter={(value) => [money.format(Number(value)), "Adjusted price"]} labelStyle={{ color: "#aaaab4" }} />
                  <Area type="monotone" dataKey="price" stroke="#0a6cff" strokeWidth={2.2} fill="url(#stockPriceFill)" isAnimationActive={false} />
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
