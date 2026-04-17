export type MetricRow = {
  method_name: string;
  category?: string;
  engine?: string;
  description?: string;
  ann_return?: number | null;
  ann_vol?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  calmar?: number | null;
  cvar_5?: number | null;
  hit_rate?: number | null;
  avg_weekly_turnover?: number | null;
  annual_turnover?: number | null;
  avg_max_weight?: number | null;
  avg_effective_n?: number | null;
  avg_hhi?: number | null;
  weight_instability?: number | null;
  allocation_instability?: number | null;
  psr_zero?: number | null;
  psr_selection?: number | null;
  robustness_score?: number | null;
  instability_flag?: boolean | null;
  subperiod_sharpe_range?: number | null;
  [key: string]: string | number | boolean | null | undefined;
};

export type ReturnPoint = {
  date: string;
  method: string;
  gross_return?: number | null;
  net_return?: number | null;
  turnover?: number | null;
  cost?: number | null;
  wealth?: number | null;
  drawdown?: number | null;
};

export type WeightPoint = {
  name: string;
  weight: number;
};

export type WeightPayload = {
  latest: WeightPoint[];
  history: Array<Record<string, string | number | null>>;
  selectedColumns: string[];
};

export type StrategyRow = {
  strategy_name: string;
  strategy_type?: string;
  benchmark_group?: string;
  ann_return?: number | null;
  ann_vol?: number | null;
  sharpe?: number | null;
  max_drawdown?: number | null;
  calmar?: number | null;
  hit_rate?: number | null;
  avg_weekly_turnover?: number | null;
  validation_score?: number | null;
  [key: string]: string | number | boolean | null | undefined;
};

export type RegimeRow = {
  Date?: string;
  date?: string;
  risk_state?: string;
  signal_environment?: string;
  overlay_multiplier?: number | null;
  target_vol_multiplier?: number | null;
  defensive_weight?: number | null;
  defensive_asset?: string;
  secondary_defensive_asset?: string;
  risk_regime_score?: number | null;
  [key: string]: string | number | boolean | null | undefined;
};

export type SignalRow = {
  signal_name: string;
  recommendation?: string;
  avg_mean_ic?: number | null;
  avg_ic_tstat_nw?: number | null;
  avg_cross_coverage?: number | null;
  avg_abs_redundancy?: number | null;
  distinctiveness_score?: number | null;
  validation_quality_score?: number | null;
  net_sharpe_10bps?: number | null;
  [key: string]: string | number | boolean | null | undefined;
};

export type DashboardData = {
  generatedAt: string;
  latestDate: string | null;
  overview: {
    projectTitle: string;
    bestByRobustness: MetricRow | null;
    bestBySharpe: MetricRow | null;
    bestDrawdown: MetricRow | null;
    bestLowTurnover: MetricRow | null;
    defaultCandidate: MetricRow | null;
    latestRegime: RegimeRow | null;
    latestRegimeScore: RegimeRow | null;
    latestMarketState?: Record<string, string | number | boolean | null> | null;
    benchmarkSummary: StrategyRow[];
    regimeCounts: Array<{ name: string; count: number }>;
    baselineVersion?: Record<string, string | number | boolean | null> | null;
    improvedVersion?: Record<string, string | number | boolean | null> | null;
    currentAllocationSummary?: Record<string, string | number | boolean | null> | null;
  };
  methods: MetricRow[];
  metricsSummary: MetricRow[];
  portfolioReturns: Record<string, ReturnPoint[]>;
  benchmarkReturns: Record<string, ReturnPoint[]>;
  portfolioWeights: Record<string, WeightPayload>;
  sleeveWeights: Record<string, WeightPayload>;
  strategySummary: StrategyRow[];
  candidateSleeves: Array<{ sleeve_name: string; role?: string }>;
  regimeStates: RegimeRow[];
  regimeScore: RegimeRow[];
  marketStateHistory: Array<Record<string, string | number | boolean | null>>;
  regimeSplit: Array<Record<string, string | number | boolean | null>>;
  subperiods: Array<Record<string, string | number | boolean | null>>;
  diagnosticsSummary: Array<Record<string, string | number | boolean | null>>;
  diagnostics: Array<Record<string, string | number | boolean | null>>;
  costSensitivity: Array<Record<string, string | number | boolean | null>>;
  dampenerSensitivity: Array<Record<string, string | number | boolean | null>>;
  blConfidenceSensitivity: Array<Record<string, string | number | boolean | null>>;
  signalSummary: SignalRow[];
  signalIc: Array<Record<string, string | number | boolean | null>>;
  signalRedundancy: {
    signals: string[];
    rowLabels?: string[];
    values: number[][];
  };
  improvementLab: {
    signalIncremental: Array<Record<string, string | number | boolean | null>>;
    signalSubsets: Array<Record<string, string | number | boolean | null>>;
    sleeveIncremental: Array<Record<string, string | number | boolean | null>>;
    sleeveSubsets: Array<Record<string, string | number | boolean | null>>;
    versions: Array<Record<string, string | number | boolean | null>>;
    versionReturns: Record<string, ReturnPoint[]>;
    versionWeights: Record<string, WeightPayload>;
    versionSleeveWeights: Record<string, WeightPayload>;
    versionRegimeSplit: Array<Record<string, string | number | boolean | null>>;
    versionSubperiods: Array<Record<string, string | number | boolean | null>>;
    allocationDrivers: Array<Record<string, string | number | boolean | null>>;
    allocationDriverBreakdown: Array<Record<string, string | number | boolean | null>>;
    allocationDriverTimeseries: Array<Record<string, string | number | boolean | null>>;
    upsideCaptureAnalysis: Array<Record<string, string | number | boolean | null>>;
    rallyWindowAttribution: Array<Record<string, string | number | boolean | null>>;
    offensiveDefensiveCashDuringRallies: Array<Record<string, string | number | boolean | null>>;
    targetedWindowSummary: Array<Record<string, string | number | boolean | null>>;
    upsideDownsideCaptureByWindow: Array<Record<string, string | number | boolean | null>>;
    reriskingLagByWindow: Array<Record<string, string | number | boolean | null>>;
    stateConditionedAllocationSummary: Array<Record<string, string | number | boolean | null>>;
    sleevePerformanceByState: Array<Record<string, string | number | boolean | null>>;
    upsideCaptureVersionComparison: Array<Record<string, string | number | boolean | null>>;
  };
  manifests: Record<string, unknown>;
  artifacts: Array<{ path: string; exists: boolean; updatedAt: string | null; bytes: number }>;
};
