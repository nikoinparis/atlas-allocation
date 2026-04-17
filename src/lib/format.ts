export function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function formatPercent(value: unknown, digits = 1): string {
  if (!isFiniteNumber(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatNumber(value: unknown, digits = 2): string {
  if (!isFiniteNumber(value)) return "n/a";
  return value.toFixed(digits);
}

export function formatCompact(value: unknown): string {
  if (!isFiniteNumber(value)) return "n/a";
  return Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function titleCase(value: string | null | undefined): string {
  if (!value) return "n/a";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bIc\b/g, "IC")
    .replace(/\bHrp\b/g, "HRP")
    .replace(/\bHerc\b/g, "HERC")
    .replace(/\bMvo\b/g, "MVO")
    .replace(/\bCvar\b/g, "CVaR");
}

export function shortDate(value: string | null | undefined): string {
  if (!value) return "n/a";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export const chartColors = [
  "#b9853b",
  "#3d7057",
  "#31415f",
  "#6f2e2e",
  "#7b6f4d",
  "#9d5c42",
  "#426a8c",
  "#6f7d47",
  "#a95866",
  "#52706f",
  "#8f6fb0",
  "#d18a54",
];

export function methodColor(method: string, methods: string[]): string {
  const index = Math.max(0, methods.indexOf(method));
  return chartColors[index % chartColors.length];
}

export function metricLabel(key: string): string {
  const labels: Record<string, string> = {
    ann_return: "Ann. Return",
    ann_vol: "Ann. Vol",
    sharpe: "Sharpe",
    max_drawdown: "Max Drawdown",
    calmar: "Calmar",
    cvar_5: "CVaR 5%",
    avg_weekly_turnover: "Weekly Turnover",
    annual_turnover: "Annual Turnover",
    avg_max_weight: "Avg Max Weight",
    avg_effective_n: "Effective N",
    avg_hhi: "HHI",
    weight_instability: "Weight Instability",
    robustness_score: "Robustness",
    production_score: "Production Score",
    psr_selection: "Selection-Aware PSR",
    upside_capture_positive_weeks: "Upside Capture",
    downside_capture_negative_weeks: "Downside Capture",
    recovery_week_capture: "Recovery Capture",
    calm_week_capture: "Calm Capture",
    avg_cash_when_benchmark_positive: "Cash In Up Weeks",
    avg_dynamic_speed: "Avg Re-risk Speed",
    weeks_to_offensive_50: "Weeks To 50% Offense",
    weeks_to_offensive_60: "Weeks To 60% Offense",
    weeks_to_cash_below_35: "Weeks To Cash < 35%",
    weeks_to_cash_below_25: "Weeks To Cash < 25%",
  };
  return labels[key] ?? titleCase(key);
}
