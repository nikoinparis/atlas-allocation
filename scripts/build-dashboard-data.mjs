import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const DATA_ROOT = path.join(ROOT, "data");
const PUBLIC_DIR = path.join(ROOT, "public");
const OUTPUT_PATH = path.join(PUBLIC_DIR, "dashboard-data.json");

const DIRS = {
  dataHub: path.join(DATA_ROOT, "01_data_hub"),
  layer1: path.join(DATA_ROOT, "02_layer1_signals"),
  layer2a: path.join(DATA_ROOT, "03_layer2a_strategy_logic"),
  layer2b: path.join(DATA_ROOT, "04_layer2b_risk_regime_engine"),
  layer3: path.join(DATA_ROOT, "05_layer3_portfolio_construction"),
};

function exists(filePath) {
  return fs.existsSync(filePath);
}

function readText(filePath) {
  if (!exists(filePath)) return "";
  return fs.readFileSync(filePath, "utf8");
}

function parseCsv(text) {
  if (!text.trim()) return [];
  const rows = [];
  let row = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        field += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === "," && !inQuotes) {
      row.push(field);
      field = "";
    } else if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") i += 1;
      row.push(field);
      if (row.some((value) => value !== "")) rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }

  if (field.length > 0 || row.length > 0) {
    row.push(field);
    if (row.some((value) => value !== "")) rows.push(row);
  }

  if (rows.length < 2) return [];
  const headers = rows[0].map((header, index) => {
    const clean = String(header || "").trim();
    if (!clean || clean === "Unnamed: 0") return index === 0 ? "Date" : `column_${index}`;
    return clean;
  });

  return rows.slice(1).map((values) => {
    const out = {};
    headers.forEach((header, index) => {
      out[header] = coerceValue(values[index]);
    });
    return out;
  });
}

function coerceValue(value) {
  if (value === undefined || value === null) return null;
  const trimmed = String(value).trim();
  if (trimmed === "" || trimmed.toLowerCase() === "nan" || trimmed.toLowerCase() === "none") return null;
  if (trimmed === "True") return true;
  if (trimmed === "False") return false;
  const num = Number(trimmed);
  if (Number.isFinite(num) && /^[-+]?(\d+\.?\d*|\.\d+)(e[-+]?\d+)?$/i.test(trimmed)) return num;
  return trimmed;
}

function readCsv(relativePath) {
  return parseCsv(readText(path.join(ROOT, relativePath)));
}

function readJson(relativePath, fallback = null) {
  try {
    const text = readText(path.join(ROOT, relativePath));
    return text ? JSON.parse(text) : fallback;
  } catch {
    return fallback;
  }
}

function listFiles(dirPath, matcher) {
  if (!exists(dirPath)) return [];
  return fs.readdirSync(dirPath).filter((name) => matcher.test(name)).sort();
}

function fileMeta(relativePath) {
  const absolute = path.join(ROOT, relativePath);
  if (!exists(absolute)) return { path: relativePath, exists: false, updatedAt: null, bytes: 0 };
  const stat = fs.statSync(absolute);
  return {
    path: relativePath,
    exists: true,
    updatedAt: stat.mtime.toISOString(),
    bytes: stat.size,
  };
}

function maxBy(rows, key, filter = () => true) {
  return rows.filter(filter).reduce((best, row) => {
    const value = Number(row[key]);
    if (!Number.isFinite(value)) return best;
    if (!best || value > Number(best[key])) return row;
    return best;
  }, null);
}

function minBy(rows, key, filter = () => true) {
  return rows.filter(filter).reduce((best, row) => {
    const value = Number(row[key]);
    if (!Number.isFinite(value)) return best;
    if (!best || value < Number(best[key])) return row;
    return best;
  }, null);
}

function methodNameFromFile(fileName, prefix) {
  return fileName.replace(prefix, "").replace(/\.csv$/, "");
}

function cleanDate(row) {
  return row.Date || row.date || row.index || null;
}

function readReturnSeries(dir, fileName, name) {
  return readCsv(path.relative(ROOT, path.join(dir, fileName))).map((row) => ({
    date: cleanDate(row),
    method: name,
    gross_return: row.gross_return ?? null,
    net_return: row.net_return ?? null,
    turnover: row.turnover ?? null,
    cost: row.cost ?? null,
    wealth: row.wealth ?? null,
    drawdown: row.drawdown ?? null,
  })).filter((row) => row.date);
}

function sampleRows(rows, step = 4) {
  if (rows.length <= 260) return rows;
  return rows.filter((_, index) => index % step === 0 || index === rows.length - 1);
}

function numericEntries(row) {
  return Object.entries(row).filter(([key, value]) => key !== "Date" && typeof value === "number" && Number.isFinite(value));
}

function weightPayload(dir, fileName, prefix) {
  const method = methodNameFromFile(fileName, prefix);
  const rows = readCsv(path.relative(ROOT, path.join(dir, fileName))).filter((row) => cleanDate(row));
  if (!rows.length) return [method, { latest: [], history: [] }];
  const latestRow = rows[rows.length - 1];
  const averages = new Map();
  rows.forEach((row) => {
    numericEntries(row).forEach(([key, value]) => averages.set(key, (averages.get(key) || 0) + Math.abs(value)));
  });
  const topAverage = [...averages.entries()]
    .map(([key, total]) => [key, total / rows.length])
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([key]) => key);
  const latestTop = numericEntries(latestRow)
    .filter(([, value]) => Math.abs(value) > 0.0001)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .slice(0, 12)
    .map(([key]) => key);
  const selected = [...new Set([...topAverage, ...latestTop])];

  const latest = numericEntries(latestRow)
    .filter(([, value]) => Math.abs(value) > 0.0001)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
    .map(([name, weight]) => ({ name, weight }));

  const history = sampleRows(rows).map((row) => {
    const out = { date: cleanDate(row) };
    selected.forEach((key) => {
      out[key] = typeof row[key] === "number" ? row[key] : 0;
    });
    return out;
  });

  return [method, { latest, history, selectedColumns: selected }];
}

function groupCount(rows, key) {
  return Object.values(rows.reduce((acc, row) => {
    const value = row[key] ?? "unknown";
    acc[value] ||= { name: value, count: 0 };
    acc[value].count += 1;
    return acc;
  }, {}));
}

function diagnosticsSummary(rows) {
  const grouped = rows.reduce((acc, row) => {
    const method = row.method_name || "unknown";
    acc[method] ||= {
      method_name: method,
      observations: 0,
      fallback_count: 0,
      avg_cash_weight: 0,
      avg_gross_multiplier: 0,
      avg_target_vol_multiplier: 0,
      avg_regime_multiplier: 0,
      avg_active_sleeves: 0,
    };
    const item = acc[method];
    item.observations += 1;
    if (row.hierarchical_fallback === true || row.hierarchical_fallback === "True") item.fallback_count += 1;
    item.avg_cash_weight += Number(row.cash_weight) || 0;
    item.avg_gross_multiplier += Number(row.gross_multiplier) || 0;
    item.avg_target_vol_multiplier += Number(row.target_vol_multiplier) || 0;
    item.avg_regime_multiplier += Number(row.regime_multiplier) || 0;
    item.avg_active_sleeves += Number(row.active_sleeves) || 0;
    return acc;
  }, {});

  return Object.values(grouped).map((item) => {
    const denom = Math.max(item.observations, 1);
    return {
      ...item,
      fallback_rate: item.fallback_count / denom,
      avg_cash_weight: item.avg_cash_weight / denom,
      avg_gross_multiplier: item.avg_gross_multiplier / denom,
      avg_target_vol_multiplier: item.avg_target_vol_multiplier / denom,
      avg_regime_multiplier: item.avg_regime_multiplier / denom,
      avg_active_sleeves: item.avg_active_sleeves / denom,
    };
  });
}

function redundancyPayload(rows) {
  if (!rows.length) return { signals: [], values: [] };
  const labelKey = Object.keys(rows[0])[0];
  const signals = Object.keys(rows[0]).filter((key) => key !== labelKey);
  const values = rows.map((row) => signals.map((signal) => Number(row[signal]) || 0));
  const rowLabels = rows.map((row) => String(row[labelKey]));
  return { signals, rowLabels, values };
}

const methods = readCsv("data/05_layer3_portfolio_construction/portfolio_method_comparison.csv");
const metricsSummary = readCsv("data/05_layer3_portfolio_construction/portfolio_metrics_summary.csv");
const strategySummary = readCsv("data/03_layer2a_strategy_logic/strategy_summary_table.csv");
const signalSummary = readCsv("data/02_layer1_signals/signal_summary_table.csv");
const signalIc = readCsv("data/02_layer1_signals/signal_ic_by_horizon.csv");
const signalRedundancy = redundancyPayload(readCsv("data/02_layer1_signals/signal_redundancy_matrix.csv"));
const regimeStates = readCsv("data/04_layer2b_risk_regime_engine/regime_states.csv");
const regimeScore = readCsv("data/04_layer2b_risk_regime_engine/regime_score.csv");
const marketStateHistory = readCsv("data/04_layer2b_risk_regime_engine/market_state_history.csv");
const sleevePerformanceByState = readCsv("data/04_layer2b_risk_regime_engine/sleeve_performance_by_state.csv");
const regimeSplit = readCsv("data/05_layer3_portfolio_construction/portfolio_regime_split_summary.csv");
const subperiods = readCsv("data/05_layer3_portfolio_construction/portfolio_subperiod_summary.csv");
const diagnostics = readCsv("data/05_layer3_portfolio_construction/portfolio_diagnostics.csv");
const costSensitivity = readCsv("data/05_layer3_portfolio_construction/portfolio_cost_sensitivity.csv");
const dampenerSensitivity = readCsv("data/05_layer3_portfolio_construction/portfolio_dampener_sensitivity.csv");
const blConfidenceSensitivity = readCsv("data/05_layer3_portfolio_construction/portfolio_bl_confidence_sensitivity.csv");
const candidateSleeves = readCsv("data/05_layer3_portfolio_construction/portfolio_candidate_sleeves.csv");
const signalIncremental = readCsv("data/02_layer1_signals/signal_incremental_contribution.csv");
const signalSubsets = readCsv("data/02_layer1_signals/signal_subset_comparison.csv");
const sleeveIncremental = readCsv("data/05_layer3_portfolio_construction/sleeve_incremental_contribution.csv");
const sleeveSubsets = readCsv("data/05_layer3_portfolio_construction/sleeve_subset_comparison.csv");
const versionComparison = readCsv("data/05_layer3_portfolio_construction/portfolio_version_comparison.csv");
const versionRegimeSplit = readCsv("data/05_layer3_portfolio_construction/portfolio_version_regime_split_summary.csv");
const versionSubperiods = readCsv("data/05_layer3_portfolio_construction/portfolio_version_subperiod_summary.csv");
const allocationDrivers = readCsv("data/05_layer3_portfolio_construction/allocation_driver_summary.csv");
const allocationDriverBreakdown = readCsv("data/05_layer3_portfolio_construction/allocation_driver_breakdown.csv");
const allocationDriverTimeseries = readCsv("data/05_layer3_portfolio_construction/allocation_driver_timeseries.csv");
const upsideCaptureAnalysis = readCsv("data/05_layer3_portfolio_construction/upside_capture_analysis.csv");
const rallyWindowAttribution = readCsv("data/05_layer3_portfolio_construction/rally_window_attribution.csv");
const offensiveDefensiveCashDuringRallies = readCsv("data/05_layer3_portfolio_construction/offensive_defensive_cash_during_rallies.csv");
const targetedWindowSummary = readCsv("data/05_layer3_portfolio_construction/targeted_window_summary.csv");
const upsideDownsideCaptureByWindow = readCsv("data/05_layer3_portfolio_construction/upside_downside_capture_by_window.csv");
const reriskingLagByWindow = readCsv("data/05_layer3_portfolio_construction/rerisking_lag_by_window.csv");
const stateConditionedAllocationSummary = readCsv("data/05_layer3_portfolio_construction/state_conditioned_allocation_summary.csv");
const upsideCaptureVersionComparison = readCsv("data/05_layer3_portfolio_construction/upside_capture_version_comparison.csv");

const portfolioReturnFiles = listFiles(DIRS.layer3, /^portfolio_returns_.*\.csv$/);
const portfolioReturns = Object.fromEntries(
  portfolioReturnFiles.map((file) => {
    const method = methodNameFromFile(file, "portfolio_returns_");
    return [method, readReturnSeries(DIRS.layer3, file, method)];
  }),
);

const benchmarkFiles = listFiles(DIRS.layer2a, /^strategy_returns_baseline_.*\.csv$/);
const benchmarkReturns = Object.fromEntries(
  benchmarkFiles.map((file) => {
    const benchmark = methodNameFromFile(file, "strategy_returns_");
    return [benchmark, readReturnSeries(DIRS.layer2a, file, benchmark)];
  }),
);

const portfolioWeights = Object.fromEntries(
  listFiles(DIRS.layer3, /^portfolio_weights_.*\.csv$/).map((file) => weightPayload(DIRS.layer3, file, "portfolio_weights_")),
);
const sleeveWeights = Object.fromEntries(
  listFiles(DIRS.layer3, /^portfolio_sleeve_weights_.*\.csv$/).map((file) => weightPayload(DIRS.layer3, file, "portfolio_sleeve_weights_")),
);
const versionReturns = Object.fromEntries(
  listFiles(DIRS.layer3, /^portfolio_version_returns_.*\.csv$/).map((file) => {
    const version = methodNameFromFile(file, "portfolio_version_returns_");
    return [version, readReturnSeries(DIRS.layer3, file, version)];
  }),
);
const versionWeights = Object.fromEntries(
  listFiles(DIRS.layer3, /^portfolio_version_weights_.*\.csv$/).map((file) => weightPayload(DIRS.layer3, file, "portfolio_version_weights_")),
);
const versionSleeveWeights = Object.fromEntries(
  listFiles(DIRS.layer3, /^portfolio_version_sleeve_weights_.*\.csv$/).map((file) => weightPayload(DIRS.layer3, file, "portfolio_version_sleeve_weights_")),
);

const bestByRobustness = maxBy(methods, "robustness_score");
const bestBySharpe = maxBy(methods, "sharpe");
const bestDrawdown = maxBy(methods, "max_drawdown");
const bestLowTurnover = minBy(methods, "avg_weekly_turnover");
const defaultCandidate = maxBy(methods, "robustness_score", (row) => row.instability_flag !== true) || bestByRobustness;
const latestRegime = regimeStates.length ? regimeStates[regimeStates.length - 1] : null;
const latestRegimeScore = regimeScore.length ? regimeScore[regimeScore.length - 1] : null;
const latestMarketState = marketStateHistory.length ? marketStateHistory[marketStateHistory.length - 1] : null;
const benchmarkSummary = strategySummary.filter((row) => String(row.strategy_name || "").startsWith("baseline_"));
const baselineVersion = versionComparison.find((row) => String(row.version_name || "").startsWith("baseline_hrp")) || versionComparison.find((row) => String(row.version_name || "").startsWith("baseline_")) || null;
// Pin the production candidate to the incumbent (`improved_hrp_recovery_tilt`) unless a
// challenger variant beats it by a material production-score margin AND does not degrade max
// drawdown or CVaR. This encodes research discipline: tiny, in-noise production-score gains from
// the recovery-split experiments are classified as Conditional / Research-only and do not promote.
const INCUMBENT_NAME = "improved_hrp_recovery_tilt";
const PROMOTION_MARGIN = 0.05; // production_score
const improvedCandidates = [...versionComparison].filter((row) => String(row.version_name || "").startsWith("improved_"));
const incumbent = improvedCandidates.find((row) => row.version_name === INCUMBENT_NAME) || null;
const bestChallenger = [...improvedCandidates]
  .filter((row) => row.version_name !== INCUMBENT_NAME)
  .sort((a, b) => Number(b.production_score ?? b.sharpe ?? 0) - Number(a.production_score ?? a.sharpe ?? 0))[0] || null;
let improvedVersion = incumbent;
if (incumbent && bestChallenger) {
  const incScore = Number(incumbent.production_score ?? incumbent.sharpe ?? 0);
  const chScore = Number(bestChallenger.production_score ?? bestChallenger.sharpe ?? 0);
  const incDD = Number(incumbent.max_drawdown ?? -1);
  const chDD = Number(bestChallenger.max_drawdown ?? -1);
  const incCVaR = Number(incumbent.cvar_5 ?? -1);
  const chCVaR = Number(bestChallenger.cvar_5 ?? -1);
  if (chScore - incScore >= PROMOTION_MARGIN && chDD >= incDD - 0.005 && chCVaR >= incCVaR - 0.002) {
    improvedVersion = bestChallenger;
  }
}
if (!improvedVersion) improvedVersion = bestChallenger;
const currentAllocationSummary = improvedVersion
  ? allocationDrivers.find((row) => row.version_name === improvedVersion.version_name) ?? null
  : allocationDrivers[0] ?? null;
const latestDate = [
  latestRegime?.Date,
  ...Object.values(portfolioReturns).map((series) => series.at(-1)?.date),
  ...Object.values(versionReturns).map((series) => series.at(-1)?.date),
].filter(Boolean).sort().at(-1) || null;

const artifactPaths = [
  "data/05_layer3_portfolio_construction/portfolio_method_comparison.csv",
  "data/05_layer3_portfolio_construction/portfolio_metrics_summary.csv",
  "data/05_layer3_portfolio_construction/portfolio_regime_split_summary.csv",
  "data/05_layer3_portfolio_construction/portfolio_subperiod_summary.csv",
  "data/05_layer3_portfolio_construction/portfolio_diagnostics.csv",
  "data/05_layer3_portfolio_construction/portfolio_version_comparison.csv",
  "data/05_layer3_portfolio_construction/portfolio_version_regime_split_summary.csv",
  "data/05_layer3_portfolio_construction/portfolio_version_subperiod_summary.csv",
  "data/05_layer3_portfolio_construction/allocation_driver_summary.csv",
  "data/05_layer3_portfolio_construction/allocation_driver_breakdown.csv",
  "data/05_layer3_portfolio_construction/allocation_driver_timeseries.csv",
  "data/05_layer3_portfolio_construction/upside_capture_analysis.csv",
  "data/05_layer3_portfolio_construction/rally_window_attribution.csv",
  "data/05_layer3_portfolio_construction/offensive_defensive_cash_during_rallies.csv",
  "data/05_layer3_portfolio_construction/targeted_window_summary.csv",
  "data/05_layer3_portfolio_construction/upside_downside_capture_by_window.csv",
  "data/05_layer3_portfolio_construction/rerisking_lag_by_window.csv",
  "data/05_layer3_portfolio_construction/state_conditioned_allocation_summary.csv",
  "data/05_layer3_portfolio_construction/upside_capture_version_comparison.csv",
  "data/05_layer3_portfolio_construction/sleeve_incremental_contribution.csv",
  "data/05_layer3_portfolio_construction/sleeve_subset_comparison.csv",
  "data/03_layer2a_strategy_logic/strategy_summary_table.csv",
  "data/04_layer2b_risk_regime_engine/regime_states.csv",
  "data/04_layer2b_risk_regime_engine/market_state_history.csv",
  "data/04_layer2b_risk_regime_engine/sleeve_performance_by_state.csv",
  "data/02_layer1_signals/signal_summary_table.csv",
  "data/02_layer1_signals/signal_ic_by_horizon.csv",
  "data/02_layer1_signals/signal_redundancy_matrix.csv",
  "data/02_layer1_signals/signal_incremental_contribution.csv",
  "data/02_layer1_signals/signal_subset_comparison.csv",
  "data/02_layer1_signals/signal_manifest.json",
  "data/03_layer2a_strategy_logic/layer2_manifest.json",
  "data/05_layer3_portfolio_construction/layer3_manifest.json",
];

const artifacts = artifactPaths.map(fileMeta);
const manifests = {
  layer1: readJson("data/02_layer1_signals/signal_manifest.json", []),
  layer2: readJson("data/03_layer2a_strategy_logic/layer2_manifest.json", []),
  layer3: readJson("data/05_layer3_portfolio_construction/layer3_manifest.json", []),
  universe: readJson("data/01_data_hub/universe.json", {}),
  proxyMapping: readJson("data/01_data_hub/proxy_mapping.json", {}),
};

const payload = {
  generatedAt: new Date().toISOString(),
  latestDate,
  overview: {
    projectTitle: "ETF Quant Portfolio Research Stack",
    bestByRobustness,
    bestBySharpe,
    bestDrawdown,
    bestLowTurnover,
    defaultCandidate,
    latestRegime,
    latestRegimeScore,
    latestMarketState,
    benchmarkSummary,
    regimeCounts: groupCount(regimeStates, "risk_state"),
    baselineVersion,
    improvedVersion,
    currentAllocationSummary,
  },
  methods,
  metricsSummary,
  portfolioReturns,
  benchmarkReturns,
  portfolioWeights,
  sleeveWeights,
  strategySummary,
  candidateSleeves,
  regimeStates: sampleRows(regimeStates, 2),
  regimeScore: sampleRows(regimeScore, 2).map((row) => ({
    date: row.Date,
    risk_regime_score: row.risk_regime_score,
    risk_state: row.risk_state,
    signal_environment: row.signal_environment,
  })),
  marketStateHistory: sampleRows(marketStateHistory, 2).map((row) => ({
    date: row.Date,
    market_state: row.market_state,
    market_state_reason: row.market_state_reason,
    risk_state: row.risk_state,
    signal_environment: row.signal_environment,
    breadth_sma_43: row.breadth_sma_43,
    breadth_26w_mom: row.breadth_26w_mom,
    market_drawdown: row.market_drawdown,
    google_fear_z_tradable: row.google_fear_z_tradable,
  })),
  regimeSplit,
  subperiods,
  diagnosticsSummary: diagnosticsSummary(diagnostics),
  diagnostics,
  costSensitivity,
  dampenerSensitivity,
  blConfidenceSensitivity,
  signalSummary,
  signalIc,
  signalRedundancy,
  improvementLab: {
    signalIncremental,
    signalSubsets,
    sleeveIncremental,
    sleeveSubsets,
    versions: versionComparison,
    versionReturns,
    versionWeights,
    versionSleeveWeights,
    versionRegimeSplit,
    versionSubperiods,
    allocationDrivers,
    allocationDriverBreakdown,
    allocationDriverTimeseries,
    upsideCaptureAnalysis,
    rallyWindowAttribution,
    offensiveDefensiveCashDuringRallies,
    targetedWindowSummary,
    upsideDownsideCaptureByWindow,
    reriskingLagByWindow,
    stateConditionedAllocationSummary,
    sleevePerformanceByState,
    upsideCaptureVersionComparison,
  },
  manifests,
  artifacts,
};

fs.mkdirSync(PUBLIC_DIR, { recursive: true });
fs.writeFileSync(OUTPUT_PATH, `${JSON.stringify(payload, null, 2)}\n`);
console.log(`Wrote ${path.relative(ROOT, OUTPUT_PATH)} with ${methods.length} portfolio methods`);
