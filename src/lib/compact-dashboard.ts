import type { DashboardData, ReturnPoint, WeightPayload } from "@/types/dashboard";

type AnyRow = Record<string, string | number | boolean | null>;

type CompactBundle = {
  registry?: AnyRow;
  summary?: AnyRow[];
  state_summary?: AnyRow[];
  exposure_summary?: AnyRow[];
  promotion_checklist?: AnyRow[];
  versionReturns?: Record<string, ReturnPoint[]>;
  versionWeights?: Record<string, WeightPayload>;
  versionSleeveWeights?: Record<string, WeightPayload>;
};

const PRODUCTION = "improved_phase2b_regime_confidence_boost";
const SHADOW = "improved_phase2b_combo_abc";
const CANDIDATE = "improved_phaseggg_confirmed_only_robust_offense";

function asVersionRow(row: AnyRow): AnyRow {
  return {
    ...row,
    version_name: row.name,
    ann_return: row.full_ann_return,
    ann_vol: row.full_ann_vol,
    sharpe: row.full_sharpe,
    max_drawdown: row.full_max_drawdown,
    cvar_5: row.full_cvar_5,
    calmar: row.full_calmar,
    avg_weekly_turnover: row.avg_turnover,
    avg_bil_weight: row.avg_BIL,
    avg_spy_weight: row.avg_SPY,
    production_score: row.role === "production_candidate_pending_human_review" ? 1 : 0,
  };
}

function rows(rows: AnyRow[] | undefined): AnyRow[] {
  return rows ?? [];
}

function emptyWeight(): WeightPayload {
  return { latest: [], history: [], selectedColumns: [] };
}

export function compactBundleToDashboardData(bundle: CompactBundle): DashboardData {
  const summary = rows(bundle.summary).map(asVersionRow);
  const findVersion = (name: string) => summary.find((row) => row.version_name === name) ?? null;
  const production = findVersion(PRODUCTION);
  const shadow = findVersion(SHADOW);
  const candidate = findVersion(CANDIDATE);
  const versionReturns = bundle.versionReturns ?? {};
  const latestDate = Object.values(versionReturns)
    .flatMap((rows) => rows.map((row) => row.date).filter(Boolean))
    .sort()
    .at(-1) ?? null;

  return {
    generatedAt: new Date().toISOString(),
    latestDate,
    overview: {
      projectTitle: "ETF Quant Portfolio Production Candidate Review",
      bestByRobustness: null,
      bestBySharpe: null,
      bestDrawdown: null,
      bestLowTurnover: null,
      defaultCandidate: null,
      latestRegime: null,
      latestRegimeScore: null,
      latestMarketState: null,
      benchmarkSummary: [],
      regimeCounts: [],
      baselineVersion: production,
      improvedVersion: candidate,
      researchVersion: shadow,
      currentAllocationSummary: null,
      researchAllocationSummary: null,
      trackPolicy: {
        productionVersion: CANDIDATE,
        researchVersion: SHADOW,
        promotionMargin: 0,
        note: "Compact Phase III package: current production remains rollback until human deployment review changes the live pin.",
      },
    },
    methods: [],
    metricsSummary: [],
    portfolioReturns: {},
    benchmarkReturns: {},
    portfolioWeights: {},
    sleeveWeights: {},
    strategySummary: [],
    candidateSleeves: [],
    regimeStates: [],
    regimeScore: [],
    marketStateHistory: [],
    regimeSplit: [],
    subperiods: [],
    diagnosticsSummary: [],
    diagnostics: [],
    costSensitivity: [],
    dampenerSensitivity: [],
    blConfidenceSensitivity: [],
    signalSummary: [],
    signalIc: [],
    signalRedundancy: { signals: [], values: [] },
    improvementLab: {
      signalIncremental: [],
      signalSubsets: [],
      sleeveIncremental: [],
      sleeveSubsets: [],
      versions: summary,
      versionReturns,
      versionWeights: bundle.versionWeights ?? {
        [PRODUCTION]: emptyWeight(),
        [SHADOW]: emptyWeight(),
        [CANDIDATE]: emptyWeight(),
      },
      versionSleeveWeights: bundle.versionSleeveWeights ?? {
        [PRODUCTION]: emptyWeight(),
        [SHADOW]: emptyWeight(),
        [CANDIDATE]: emptyWeight(),
      },
      versionRegimeSplit: [],
      versionSubperiods: [],
      allocationDrivers: rows(bundle.exposure_summary),
      allocationDriverBreakdown: [],
      allocationDriverTimeseries: [],
      upsideCaptureAnalysis: [],
      rallyWindowAttribution: [],
      offensiveDefensiveCashDuringRallies: [],
      targetedWindowSummary: [],
      upsideDownsideCaptureByWindow: [],
      reriskingLagByWindow: [],
      stateConditionedAllocationSummary: [],
      sleevePerformanceByState: rows(bundle.state_summary),
      upsideCaptureVersionComparison: summary,
    },
    manifests: { productionCandidateRegistry: bundle.registry ?? {} },
    artifacts: [],
  };
}
