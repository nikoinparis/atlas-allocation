import type { DashboardData, MetricRow, ReturnPoint, SignalRow, WeightPayload } from "@/types/dashboard";

type AnyRow = Record<string, string | number | boolean | null>;

type InputRow = Record<string, string | number | boolean | null | undefined>;

type CompactBundle = {
  registry?: Record<string, unknown>;
  summary?: InputRow[];
  state_summary?: InputRow[];
  exposure_summary?: InputRow[];
  promotion_checklist?: InputRow[];
  layer1_signal_validation_summary?: AnyRow[];
  layer1_signal_quality_ranking?: AnyRow[];
  layer1_incremental_signal_contribution?: AnyRow[];
  layer1_signal_subset_comparison?: AnyRow[];
  layer1_ic_decay_by_horizon?: AnyRow[];
  layer1_signal_redundancy_matrix?: {
    signals?: string[];
    rowLabels?: string[];
    values?: number[][];
  };
  layer1_data_status?: Record<string, unknown>;
  versionReturns?: Record<string, ReturnPoint[]>;
  versionWeights?: Record<string, WeightPayload>;
  versionSleeveWeights?: Record<string, WeightPayload>;
};

const PRODUCTION = "improved_frontier_phase5_fragility_guard";
const PRIOR_PRODUCTION = "improved_phase2b_regime_confidence_boost";
const SHADOW = "improved_phase2b_combo_abc";
const CANDIDATE = "improved_frontier_phase5_fragility_guard";

function roleLabel(name: string, role: unknown): string {
  if (name === PRODUCTION || role === "current_production") return "Current production: Frontier Phase5 Fragility Guard";
  if (name === PRIOR_PRODUCTION || role === "prior_production_pin_and_rollback") return "Prior production / rollback";
  if (name === CANDIDATE || role === "production_candidate_pending_human_review") return "Production candidate: Frontier Phase5 Fragility Guard";
  if (name === SHADOW) return "Official shadow";
  return typeof role === "string" ? role : "Tracked strategy";
}

function asArray<T>(value: T[] | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
  }
  return null;
}

function pickFirst<T>(...values: Array<T | null | undefined>): T | null {
  for (const value of values) {
    if (value !== null && value !== undefined && value !== "") return value;
  }
  return null;
}

function cleanRecord(row: Record<string, string | number | boolean | null | undefined> | null): AnyRow | null {
  if (!row) return null;
  return Object.fromEntries(Object.entries(row).map(([key, value]) => [key, value ?? null])) as AnyRow;
}

function latestWeight(payload: WeightPayload | undefined, name: string): number | null {
  return asNumber(payload?.latest?.find((row) => row.name === name)?.weight);
}

function sumSleeves(payload: WeightPayload | undefined, names: string[]): number | null {
  const sum = asArray(payload?.latest).reduce((total, row) => {
    if (!names.includes(row.name)) return total;
    return total + (asNumber(row.weight) ?? 0);
  }, 0);
  return Number.isFinite(sum) ? sum : null;
}

function normalizeReturns(rows: ReturnPoint[] | undefined): ReturnPoint[] {
  let wealth = 1;
  return asArray(rows).map((row) => {
    const netReturn = asNumber(row.net_return) ?? asNumber(row.gross_return) ?? 0;
    const existingWealth = asNumber(row.wealth);
    wealth = existingWealth ?? wealth * (1 + netReturn);
    return {
      ...row,
      date: String(row.date ?? "").slice(0, 10),
      net_return: netReturn,
      wealth,
      drawdown: asNumber(row.drawdown),
    };
  }).filter((row) => row.date);
}

function asVersionRow(row: AnyRow): MetricRow {
  const name = String(row.name ?? row.version_name ?? "");
  const avgBil = pickFirst(row.avg_BIL, row.avg_bil_weight);
  const avgSpy = pickFirst(row.avg_SPY, row.avg_spy_weight);
  return {
    ...row,
    version_name: name,
    method_name: name,
    display_label: roleLabel(name, row.role),
    category: roleLabel(name, row.role),
    ann_return: asNumber(pickFirst(row.ann_return, row.full_ann_return)),
    ann_vol: asNumber(pickFirst(row.ann_vol, row.full_ann_vol)),
    sharpe: asNumber(pickFirst(row.sharpe, row.full_sharpe)),
    max_drawdown: asNumber(pickFirst(row.max_drawdown, row.full_max_drawdown)),
    cvar_5: asNumber(pickFirst(row.cvar_5, row.full_cvar_5)),
    calmar: asNumber(pickFirst(row.calmar, row.full_calmar)),
    avg_weekly_turnover: asNumber(pickFirst(row.avg_weekly_turnover, row.avg_turnover)),
    annual_turnover: asNumber(pickFirst(row.annual_turnover, row.avg_turnover)),
    avg_bil_weight: asNumber(avgBil),
    avg_spy_weight: asNumber(avgSpy),
    avg_cash_weight: asNumber(avgBil),
    avg_cash_proxy_weight: asNumber(avgBil),
    production_score: row.role === "production_candidate_pending_human_review" || row.role === "current_production" ? 1 : 0,
    robustness_score: row.role === "production_candidate_pending_human_review" || row.role === "current_production" ? 1 : 0,
  };
}

function rows(rows: AnyRow[] | undefined): AnyRow[] {
  return rows ?? [];
}

function normalizeInputRows(value: InputRow[] | undefined): AnyRow[] {
  if (!value) return [];
  return value.map((row) => {
    const out: AnyRow = {};
    for (const [k, v] of Object.entries(row)) {
      out[k] = v !== undefined ? (v as string | number | boolean | null) : null;
    }
    return out;
  });
}

function normalizeDataRows(value: AnyRow[] | undefined): AnyRow[] {
  return rows(value).map((row) => {
    const normalized: AnyRow = {};
    Object.entries(row).forEach(([key, value]) => {
      normalized[key] = asNumber(value) ?? value;
    });
    return normalized;
  });
}

function normalizeRedundancy(value: CompactBundle["layer1_signal_redundancy_matrix"]) {
  const signals = Array.isArray(value?.signals) ? value.signals.map(String) : [];
  const rowLabels = Array.isArray(value?.rowLabels) ? value.rowLabels.map(String) : signals;
  const values = Array.isArray(value?.values)
    ? value.values.map((row) => (Array.isArray(row) ? row.map((item) => asNumber(item) ?? 0) : []))
    : [];
  return { signals, rowLabels, values };
}

function normalizeSignalRows(value: AnyRow[] | undefined): SignalRow[] {
  return normalizeDataRows(value)
    .filter((row) => row.signal_name)
    .map((row) => ({
      ...row,
      signal_name: String(row.signal_name),
    }));
}

function emptyWeight(): WeightPayload {
  return { latest: [], history: [], selectedColumns: [] };
}

export function compactBundleToDashboardData(bundle: CompactBundle): DashboardData {
  const summary: MetricRow[] = normalizeInputRows(bundle.summary).map(asVersionRow);
  const findVersion = (name: string) => summary.find((row) => row.version_name === name) ?? null;
  const production = findVersion(PRODUCTION);
  const priorProduction = findVersion(PRIOR_PRODUCTION);
  const shadow = findVersion(SHADOW);
  const candidate = findVersion(CANDIDATE);
  const summaryRecords = summary.map((row) => cleanRecord(row)).filter((row): row is AnyRow => Boolean(row));
  const versionReturns = Object.fromEntries(
    Object.entries(bundle.versionReturns ?? {}).map(([name, value]) => [name, normalizeReturns(value)]),
  );
  const versionWeights = bundle.versionWeights ?? {
    [PRODUCTION]: emptyWeight(),
    [SHADOW]: emptyWeight(),
  };
  const versionSleeveWeights = bundle.versionSleeveWeights ?? {
    [PRODUCTION]: emptyWeight(),
    [SHADOW]: emptyWeight(),
  };
  const latestDate = Object.values(versionReturns)
    .flatMap((rows) => rows.map((row) => row.date).filter(Boolean))
    .sort()
    .at(-1) ?? null;
  const exposureRows = normalizeInputRows(bundle.exposure_summary);
  const candidateExposure = exposureRows.find((row) => row.name === CANDIDATE);
  const productionExposure = exposureRows.find((row) => row.name === PRODUCTION);
  const latestMarketState: AnyRow = {
    date: latestDate,
    market_state: "frontier_phase5_production",
    risk_state: "production",
    market_state_reason: "Compact bundle carries Phase 5 production data; live market-state history not included.",
  };
  const sleeveGroups = {
    offensive: ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component"],
    defensive: ["composite_regime_defense_component", "taa_10m_sma"],
  };
  const allocationDrivers = exposureRows.map((row) => {
    const name = String(row.name ?? "");
    const weights = versionWeights[name];
    const sleeves = versionSleeveWeights[name];
    const currentBil = pickFirst(latestWeight(weights, "BIL"), row.avg_BIL);
    const currentSpy = pickFirst(latestWeight(weights, "SPY"), row.avg_SPY);
    const offensive = sumSleeves(sleeves, sleeveGroups.offensive);
    const defensive = sumSleeves(sleeves, sleeveGroups.defensive);
    return {
      ...row,
      version_name: name,
      method_name: name,
      current_date: latestDate,
      current_market_state: latestMarketState.market_state,
      current_market_state_reason: latestMarketState.market_state_reason,
      current_state_label: "review",
      current_offensive_weight: offensive,
      current_defensive_weight: defensive,
      current_cash_proxy_weight: currentBil,
      current_bil_weight: currentBil,
      current_spy_weight: currentSpy,
      avg_offensive_weight: offensive,
      avg_defensive_weight: defensive,
      avg_cash_proxy_weight: row.avg_BIL,
      avg_bil_weight: row.avg_BIL,
      avg_spy_weight: row.avg_SPY,
    };
  });
  const allocationDriverTimeseries = Object.entries(versionReturns).flatMap(([versionName, returns]) => {
    const driver = allocationDrivers.find((row) => row.version_name === versionName);
    return returns.map((row) => ({
      date: row.date,
      version_name: versionName,
      offensive_weight: asNumber(driver?.current_offensive_weight),
      defensive_weight: asNumber(driver?.current_defensive_weight),
      cash_proxy_weight: asNumber(driver?.current_cash_proxy_weight),
      bil_weight: asNumber(driver?.current_bil_weight),
      spy_weight: asNumber(driver?.current_spy_weight),
    }));
  });
  const allocationDriverBreakdown = exposureRows.flatMap((row) => {
    const name = String(row.name ?? "");
    const label = name === CANDIDATE ? "Candidate" : name === SHADOW ? "Official shadow" : "Production";
    return [
      {
        version_name: name,
        asset: "BIL",
        driver: `${label} avg BIL vs production`,
        contribution: name === PRODUCTION ? 0 : delta(row.avg_BIL, productionExposure?.avg_BIL),
      },
      {
        version_name: name,
        asset: "SPY",
        driver: `${label} avg SPY vs production`,
        contribution: name === PRODUCTION ? 0 : delta(row.avg_SPY, productionExposure?.avg_SPY),
      },
    ];
  });
  const stateSummary = normalizeInputRows(bundle.state_summary).map((row) => ({
    ...row,
    version_name: row.candidate,
    method_name: row.candidate,
    strategy_name: row.candidate,
    market_state: row.state,
    ann_vol: row.vol_wkly,
    max_drawdown: row.max_drawdown ?? null,
  }));
  const stateConditionedAllocationSummary = asArray(versionSleeveWeights[CANDIDATE]?.latest).map((row) => ({
    version_name: CANDIDATE,
    market_state: latestMarketState.market_state,
    sleeve_name: row.name,
    avg_weight: row.weight,
  }));
  const signalSummary = normalizeSignalRows(bundle.layer1_signal_validation_summary?.length ? bundle.layer1_signal_validation_summary : bundle.layer1_signal_quality_ranking);
  const signalIc = normalizeDataRows(bundle.layer1_ic_decay_by_horizon);
  const signalIncremental = normalizeDataRows(bundle.layer1_incremental_signal_contribution);
  const signalSubsets = normalizeDataRows(bundle.layer1_signal_subset_comparison);
  const signalRedundancy = normalizeRedundancy(bundle.layer1_signal_redundancy_matrix);

  return {
    generatedAt: String(bundle.registry?.generated_at ?? new Date().toISOString()),
    latestDate,
    overview: {
      projectTitle: "ETF Quant Portfolio Production Candidate Review",
      bestByRobustness: candidate,
      bestBySharpe: candidate,
      bestDrawdown: candidate,
      bestLowTurnover: production,
      defaultCandidate: candidate,
      latestRegime: null,
      latestRegimeScore: null,
      latestMarketState,
      benchmarkSummary: [],
      regimeCounts: [],
      baselineVersion: cleanRecord(priorProduction ?? production),
      improvedVersion: cleanRecord(candidate),
      researchVersion: cleanRecord(shadow),
      currentAllocationSummary: allocationDrivers.find((row) => row.version_name === CANDIDATE) ?? null,
      researchAllocationSummary: null,
      trackPolicy: {
        productionVersion: PRODUCTION,
        researchVersion: SHADOW,
        promotionMargin: 0,
        note: "Compact package: Frontier Phase5 Fragility Guard is now the current production pin; Phase2B is preserved as rollback.",
      },
    },
    methods: summary,
    metricsSummary: summary,
    portfolioReturns: versionReturns,
    benchmarkReturns: {},
    portfolioWeights: versionWeights,
    sleeveWeights: versionSleeveWeights,
    strategySummary: [],
    candidateSleeves: [],
    regimeStates: [],
    regimeScore: [],
    marketStateHistory: [latestMarketState],
    regimeSplit: [],
    subperiods: [],
    diagnosticsSummary: [],
    diagnostics: [],
    costSensitivity: [],
    dampenerSensitivity: [],
    blConfidenceSensitivity: [],
    signalSummary,
    signalIc,
    signalRedundancy,
    improvementLab: {
      signalIncremental,
      signalSubsets,
      sleeveIncremental: [],
      sleeveSubsets: [],
      versions: summaryRecords,
      versionReturns,
      versionWeights,
      versionSleeveWeights,
      versionRegimeSplit: [],
      versionSubperiods: [],
      allocationDrivers,
      allocationDriverBreakdown,
      allocationDriverTimeseries,
      upsideCaptureAnalysis: [],
      rallyWindowAttribution: [],
      offensiveDefensiveCashDuringRallies: [],
      targetedWindowSummary: [],
      upsideDownsideCaptureByWindow: [],
      reriskingLagByWindow: [],
      stateConditionedAllocationSummary,
      sleevePerformanceByState: stateSummary,
      upsideCaptureVersionComparison: summaryRecords,
    },
    manifests: { productionCandidateRegistry: bundle.registry ?? {}, layer1DataStatus: bundle.layer1_data_status ?? {} },
    artifacts: [],
  };
}

function delta(current: unknown, baseline: unknown): number | null {
  const currentNumber = asNumber(current);
  const baselineNumber = asNumber(baseline);
  return currentNumber !== null && baselineNumber !== null ? currentNumber - baselineNumber : null;
}
