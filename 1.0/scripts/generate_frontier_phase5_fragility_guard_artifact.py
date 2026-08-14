"""Generate named artifact for Frontier Phase 5 fragility guard candidate.

This is a packaging/review script, not a live promotion. It creates stable
portfolio_version_* files for improved_frontier_phase5_fragility_guard and
updates candidate comparison registry/summary CSVs while preserving the live
production pin and official shadow pin.
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, CheckpointModifier, exact_rebuild_tolerance_ok
from path1_path3_research_utils import (
    DATA,
    DOCS,
    GGG,
    OFFENSE,
    OFFENSE_SLEEVES,
    PHASE2B,
    PORT,
    PRODUCTION_COST_BPS,
    exposure_summary,
    load_sleeve_weights,
    normalize_to_cash,
)


STABLE_NAME = "improved_frontier_phase5_fragility_guard"
SOURCE_LABEL = "phase5_fragility_guard"
PROD_PIN = "improved_phase2b_regime_confidence_boost"
SHADOW_PIN = "improved_phase2b_combo_abc"
HOLDOUT_START = pd.Timestamp("2024-04-19")

PH1_PATH = DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
PH4_PATH = DATA / "research" / "frontier_phase4" / "leadership_signals.csv"
PH10_METRICS = DATA / "research" / "frontier_phase10" / "final_candidate_metrics.csv"
PH10_HOLDOUT = DATA / "research" / "frontier_phase10" / "final_candidate_holdout_summary.csv"
PH10_BOOTSTRAP = DATA / "research" / "frontier_phase10" / "final_candidate_bootstrap_summary.csv"

SUMMARY_CSV = PORT / "production_candidate_summary.csv"
STATE_CSV = PORT / "production_candidate_state_summary.csv"
EXPOSURE_CSV = PORT / "production_candidate_exposure_summary.csv"
REGISTRY_JSON = PORT / "production_candidate_registry.json"
REPORT = DOCS / "frontier_phase5_named_artifact_packaging_report.md"
RESEARCH_OUT = DATA / "research" / "frontier_phase10" / "named_artifact_packaging_summary.csv"

PROTECTED_LIVE = [
    "public",
    "src",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read_dated(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    date_col = "date" if "date" in df.columns else "Date"
    if date_col not in df.columns:
        raise ValueError(f"{rel(path)} lacks date/Date column")
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def safe_json(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): safe_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_json(v) for v in value]
    return value


def annual_return(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").dropna()
    return float((1.0 + r).prod() ** (52 / len(r)) - 1.0) if len(r) >= 2 else np.nan


def annual_vol(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").dropna()
    return float(r.std() * np.sqrt(52)) if len(r) >= 4 else np.nan


def sharpe(r: pd.Series) -> float:
    ar = annual_return(r)
    av = annual_vol(r)
    return float(ar / av) if np.isfinite(ar) and np.isfinite(av) and av > 0 else np.nan


def max_drawdown(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").dropna()
    if r.empty:
        return np.nan
    wealth = (1.0 + r).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def calmar(r: pd.Series) -> float:
    ar = annual_return(r)
    dd = max_drawdown(r)
    return float(ar / abs(dd)) if np.isfinite(ar) and np.isfinite(dd) and dd < 0 else np.nan


def cvar_5(r: pd.Series) -> float:
    r = pd.to_numeric(r, errors="coerce").dropna()
    if len(r) < 20:
        return np.nan
    tail = r[r <= r.quantile(0.05)]
    return float(tail.mean()) if len(tail) else np.nan


def beta_to_spy(r: pd.Series, next_week_returns: pd.DataFrame) -> float:
    if "SPY" not in next_week_returns.columns:
        return np.nan
    df = pd.concat([r, next_week_returns["SPY"].reindex(r.index)], axis=1).dropna()
    if len(df) < 20 or df.iloc[:, 1].var() == 0:
        return np.nan
    return float(np.cov(df.iloc[:, 0], df.iloc[:, 1])[0, 1] / np.var(df.iloc[:, 1]))


def metric_dict(name: str, weights: pd.DataFrame, path: pd.DataFrame, next_week_returns: pd.DataFrame) -> dict:
    p = path.set_index("Date") if "Date" in path.columns else path.copy()
    r = pd.to_numeric(p["net_return"], errors="coerce").dropna()
    exp = exposure_summary(weights)
    return {
        "name": name,
        "full_ann_return": annual_return(r),
        "full_ann_vol": annual_vol(r),
        "full_sharpe": sharpe(r),
        "full_max_drawdown": max_drawdown(r),
        "full_cvar_5": cvar_5(r),
        "full_calmar": calmar(r),
        "holdout_ann_return": annual_return(r[r.index >= HOLDOUT_START]),
        "holdout_ann_vol": annual_vol(r[r.index >= HOLDOUT_START]),
        "holdout_sharpe": sharpe(r[r.index >= HOLDOUT_START]),
        "holdout_max_drawdown": max_drawdown(r[r.index >= HOLDOUT_START]),
        "holdout_cvar_5": cvar_5(r[r.index >= HOLDOUT_START]),
        "avg_BIL": float(exp.get("avg_BIL", np.nan)),
        "avg_SPY": float(exp.get("avg_SPY", np.nan)),
        "avg_turnover": float(pd.to_numeric(p["turnover"], errors="coerce").mean()),
        "max_single_etf_weight": float(weights.max(axis=1).max()) if not weights.empty else np.nan,
        "hidden_beta": beta_to_spy(r, next_week_returns),
        "window": "full_window",
        "start": "",
        "end": "",
        "ann_return": np.nan,
        "ann_vol": np.nan,
        "sharpe": np.nan,
        "max_drawdown": np.nan,
        "cvar_5": np.nan,
        "calmar": np.nan,
    }


def state_rows(role: str, name: str, path: pd.DataFrame, states: pd.Series, prod_state: dict[str, dict] | None = None) -> list[dict]:
    p = path.set_index("Date") if "Date" in path.columns else path.copy()
    r = pd.to_numeric(p["net_return"], errors="coerce").dropna()
    state_series = states.reindex(r.index)
    rows = []
    for state, sr in r.groupby(state_series):
        if not isinstance(state, str) or sr.empty:
            continue
        row = {
            "role": role,
            "candidate": name,
            "state": state,
            "n_weeks": int(len(sr)),
            "ann_return": annual_return(sr),
            "sharpe": sharpe(sr),
            "vol_wkly": float(sr.std()) if len(sr) >= 4 else np.nan,
            "mean_wkly": float(sr.mean()) if len(sr) else np.nan,
        }
        if prod_state and state in prod_state:
            row["ann_return_delta_vs_production"] = row["ann_return"] - prod_state[state]["ann_return"]
            row["sharpe_delta_vs_production"] = row["sharpe"] - prod_state[state]["sharpe"]
            row["mean_wkly_delta_vs_production"] = row["mean_wkly"] - prod_state[state]["mean_wkly"]
        else:
            row["ann_return_delta_vs_production"] = 0.0 if role == "current_production_and_rollback" else np.nan
            row["sharpe_delta_vs_production"] = 0.0 if role == "current_production_and_rollback" else np.nan
            row["mean_wkly_delta_vs_production"] = 0.0 if role == "current_production_and_rollback" else np.nan
        rows.append(row)
    return rows


def build_modifier(wrapper: AllocatorCheckpointWrapper) -> tuple[CheckpointModifier, pd.Series]:
    ph1 = read_dated(PH1_PATH)
    ph4 = read_dated(PH4_PATH)
    states = wrapper.states["market_state"].astype(str)
    r2_col = "r2a_quality" if "r2a_quality" in ph1.columns else "r2a"
    if r2_col not in ph1.columns:
        raise ValueError(f"{rel(PH1_PATH)} lacks r2a_quality/r2a")
    q = pd.to_numeric(ph1[r2_col], errors="coerce").reindex(states.index).fillna(0.0).clip(-1.0, 1.0)
    leadership = pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce").reindex(states.index).ffill().fillna(0.0)
    scale = pd.Series(1.0, index=states.index, dtype=float)
    not_sp = states.ne("stressed_panic")
    scale.loc[not_sp] = 1.0 + 0.08 * q.loc[not_sp]
    crowded = leadership.gt(0.50)
    scale.loc[crowded & not_sp] = scale.loc[crowded & not_sp].clip(upper=1.0)
    scale.loc[states.eq("stressed_panic")] = 1.0
    if not (scale.loc[states.eq("stressed_panic")] == 1.0).all():
        raise ValueError("stressed_panic scale changed")

    def _fn(_wrapper: AllocatorCheckpointWrapper, _checkpoint: str) -> pd.Series:
        return scale.reindex(_wrapper.index).fillna(1.0)

    return CheckpointModifier(name="frontier_phase5_fragility_guard", checkpoint="offense_budget", function=_fn), scale


def sleeve_proxy_from_ggg(scale: pd.Series, warnings: list[str]) -> pd.DataFrame:
    sw = load_sleeve_weights(GGG, warnings)
    if sw.empty:
        return sw
    out = sw.copy()
    offense_cols = [c for c in out.columns if c in OFFENSE_SLEEVES]
    mult = scale.reindex(out.index).ffill().fillna(1.0)
    if offense_cols:
        out[offense_cols] = out[offense_cols].mul(mult, axis=0)
    cash_col = "cash::BIL" if "cash::BIL" in out.columns else None
    if cash_col is None:
        out["cash::BIL"] = 0.0
        cash_col = "cash::BIL"
    non_cash = [c for c in out.columns if c != cash_col]
    total = out[non_cash].sum(axis=1)
    over = total > 1.0
    if over.any():
        out.loc[over, non_cash] = out.loc[over, non_cash].div(total.loc[over], axis=0)
    out[cash_col] = (1.0 - out[non_cash].sum(axis=1)).clip(lower=0.0)
    return out


def save_portfolio_artifacts(weights: pd.DataFrame, path: pd.DataFrame, sleeve: pd.DataFrame) -> list[Path]:
    files = [
        PORT / f"portfolio_version_weights_{STABLE_NAME}.csv",
        PORT / f"portfolio_version_returns_{STABLE_NAME}.csv",
        PORT / f"portfolio_version_sleeve_weights_{STABLE_NAME}.csv",
    ]
    weights.to_csv(files[0])
    (path.set_index("Date") if "Date" in path.columns else path).to_csv(files[1])
    sleeve.to_csv(files[2])
    return files


def build_summary(rows_by_name: dict[str, tuple[str, pd.DataFrame, pd.DataFrame, dict]]) -> pd.DataFrame:
    metrics = []
    for name, (role, weights, path, metric) in rows_by_name.items():
        row = {"role": role, **metric}
        metrics.append(row)
    df = pd.DataFrame(metrics)
    prod = df.set_index("name").loc[PROD_PIN]
    shadow = df.set_index("name").loc[SHADOW_PIN]
    for col in [
        "full_ann_return",
        "full_sharpe",
        "full_max_drawdown",
        "full_cvar_5",
        "holdout_ann_return",
        "holdout_sharpe",
        "avg_BIL",
        "avg_SPY",
        "avg_turnover",
    ]:
        df[f"{col}_delta_vs_production"] = df[col] - prod[col]
        df[f"{col}_delta_vs_official_shadow"] = df[col] - shadow[col]
    df["turnover_ratio_vs_production"] = df["avg_turnover"] / prod["avg_turnover"]
    existing_cols = pd.read_csv(SUMMARY_CSV, nrows=0).columns.tolist() if SUMMARY_CSV.exists() else df.columns.tolist()
    extra_cols = [c for c in df.columns if c not in existing_cols]
    return df.reindex(columns=existing_cols + extra_cols)


def build_state_summary(rows_by_name: dict[str, tuple[str, pd.DataFrame, pd.DataFrame, dict]], states: pd.Series) -> pd.DataFrame:
    prod_path = rows_by_name[PROD_PIN][2]
    prod_rows = state_rows("current_production_and_rollback", PROD_PIN, prod_path, states)
    prod_lookup = {r["state"]: r for r in prod_rows}
    all_rows = []
    for name, (role, _weights, path, _metric) in rows_by_name.items():
        all_rows.extend(state_rows(role, name, path, states, prod_lookup))
    return pd.DataFrame(all_rows)


def build_exposure_summary(summary: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "role",
        "name",
        "avg_BIL",
        "avg_SPY",
        "avg_turnover",
        "turnover_ratio_vs_production",
        "max_single_etf_weight",
        "avg_BIL_delta_vs_production",
        "avg_SPY_delta_vs_production",
        "avg_turnover_delta_vs_production",
    ]
    return summary[[c for c in cols if c in summary.columns]].copy()


def comparison_payload(summary: pd.DataFrame) -> dict:
    idx = summary.set_index("name")
    cand = idx.loc[STABLE_NAME]
    payload = {}
    for label, comp_name in [("vs_current_production", PROD_PIN), ("vs_official_shadow", SHADOW_PIN), ("vs_prior_production_candidate", GGG)]:
        if comp_name not in idx.index:
            continue
        comp = idx.loc[comp_name]
        payload[label] = {
            "comparator": comp_name,
            "annual_return": {"candidate": cand["full_ann_return"], "comparator": comp["full_ann_return"], "delta": cand["full_ann_return"] - comp["full_ann_return"]},
            "sharpe": {"candidate": cand["full_sharpe"], "comparator": comp["full_sharpe"], "delta": cand["full_sharpe"] - comp["full_sharpe"]},
            "max_drawdown": {"candidate": cand["full_max_drawdown"], "comparator": comp["full_max_drawdown"], "delta": cand["full_max_drawdown"] - comp["full_max_drawdown"]},
            "cvar_5": {"candidate": cand["full_cvar_5"], "comparator": comp["full_cvar_5"], "delta": cand["full_cvar_5"] - comp["full_cvar_5"]},
            "holdout_sharpe": {"candidate": cand["holdout_sharpe"], "comparator": comp["holdout_sharpe"], "delta": cand["holdout_sharpe"] - comp["holdout_sharpe"]},
            "avg_BIL": {"candidate": cand["avg_BIL"], "comparator": comp["avg_BIL"], "delta": cand["avg_BIL"] - comp["avg_BIL"]},
            "avg_SPY": {"candidate": cand["avg_SPY"], "comparator": comp["avg_SPY"], "delta": cand["avg_SPY"] - comp["avg_SPY"]},
            "avg_turnover": {"candidate": cand["avg_turnover"], "comparator": comp["avg_turnover"], "delta": cand["avg_turnover"] - comp["avg_turnover"]},
        }
    return payload


def update_registry(summary: pd.DataFrame) -> dict:
    existing = json.loads(REGISTRY_JSON.read_text()) if REGISTRY_JSON.exists() else {}
    current_pin = existing.get("current_production_pin", PROD_PIN)
    shadow_pin = existing.get("official_shadow_pin", SHADOW_PIN)
    if current_pin != PROD_PIN:
        raise ValueError(f"Refusing to update registry: current production pin is unexpected: {current_pin}")
    if shadow_pin != SHADOW_PIN:
        raise ValueError(f"Refusing to update registry: shadow pin is unexpected: {shadow_pin}")
    prior_candidate = existing.get("prior_production_candidate") or existing.get("production_candidate", GGG)
    if prior_candidate == STABLE_NAME:
        prior_candidate = GGG
    existing.update(
        {
            "current_production_pin": PROD_PIN,
            "rollback_pin": existing.get("rollback_pin", PROD_PIN),
            "official_shadow_pin": SHADOW_PIN,
            "production_candidate": STABLE_NAME,
            "prior_production_candidate": prior_candidate,
            "candidate_status": "FRONTIER_PHASE10A_PROMOTE_PENDING_HUMAN_REVIEW",
            "promotion_phase": "Frontier Phase 10A",
            "promotion_report": "docs/research/frontier_phase10_final_evaluation_report.md",
            "latest_research_status": "PHASE10A_PROMOTE_NAMED_ARTIFACT_READY_FOR_HUMAN_REVIEW",
            "do_not_auto_promote": True,
            "rollback_available": True,
            "dashboard_status_label": "Production candidate pending review: Frontier Phase5 Fragility Guard",
            "production_label": "Current production / rollback",
            "shadow_label": "Official shadow",
            "candidate_label": "Production candidate pending review: Frontier Phase5 Fragility Guard",
            "generated_at": pd.Timestamp.utcnow().isoformat(),
            "headline_metric_comparison": comparison_payload(summary),
            "promotion_reason_summary": [
                "Phase 10A verdict PROMOTE",
                "passes all Phase D gates versus GGG baseline",
                "passes all Phase D gates versus current production pin",
                "higher Sharpe than GGG and current production",
                "better max drawdown and CVaR than GGG",
                "holdout Sharpe improvement versus GGG",
                "bootstrap support versus GGG around 0.841",
                "stressed_panic offense unchanged",
            ],
            "known_caveats": [
                "live production pin intentionally unchanged",
                "public dashboard bundle not regenerated in this packaging sprint",
                "sleeve-weight artifact is a proxy derived from GGG sleeve weights because the candidate is a wrapper modifier",
                "human deployment review still required before production pin flip",
            ],
            "next_manual_steps": [
                "Review named artifact weights, returns, sleeve proxy, and summary CSVs.",
                "Run dashboard bundle regeneration in a separate review sprint if desired.",
                "Verify public dashboard rendering in review mode.",
                "After human approval, update current_production_pin in a separate explicit sprint.",
            ],
        }
    )
    REGISTRY_JSON.write_text(json.dumps(safe_json(existing), indent=2, allow_nan=False) + "\n")
    return existing


def diff_name_only(paths: list[str]) -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only", "--", *paths], cwd=ROOT, check=False, text=True, capture_output=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def md_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No Phase 10A metric comparison rows available._"
    display = df.copy()
    for col in display.columns:
        if pd.api.types.is_numeric_dtype(display[col]):
            display[col] = display[col].map(lambda x: "" if pd.isna(x) else f"{float(x):.10g}")
        else:
            display[col] = display[col].astype(str)
    headers = [str(c) for c in display.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for _, row in display.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in display.columns) + " |")
    return "\n".join(lines)


def write_report(summary: pd.DataFrame, artifact_files: list[Path], registry: dict, metric_check: pd.DataFrame, warnings: list[str]) -> None:
    cand = summary.set_index("name").loc[STABLE_NAME]
    prod = summary.set_index("name").loc[PROD_PIN]
    shadow = summary.set_index("name").loc[SHADOW_PIN]
    lines = [
        "# Frontier Phase 5 Fragility Guard Named Artifact Packaging",
        "",
        "**Mode:** production-candidate artifact packaging only. Live production pin unchanged.",
        "",
        "## Stable Candidate",
        "",
        f"- Stable name: `{STABLE_NAME}`",
        f"- Source research winner: `{SOURCE_LABEL}`",
        "- Definition: exact stabilized GGG wrapper baseline plus Phase 1 R2A offense scaling and Phase 4 crowding guard.",
        "- Phase 1 scale: `1 + 0.08 * clip(r2a, -1, 1)` outside `stressed_panic`.",
        "- Fragility guard: when raw `leadership_quality_composite > 0.50`, cap any offense boost at zero.",
        "- `stressed_panic`: unchanged.",
        "",
        "## Artifacts Written",
        "",
    ]
    lines.extend([f"- `{rel(path)}`" for path in artifact_files])
    lines.extend(
        [
            f"- `{rel(SUMMARY_CSV)}`",
            f"- `{rel(STATE_CSV)}`",
            f"- `{rel(EXPOSURE_CSV)}`",
            f"- `{rel(REGISTRY_JSON)}`",
            f"- `{rel(RESEARCH_OUT)}`",
            "",
            "## Registry Safety",
            "",
            f"- `current_production_pin`: `{registry.get('current_production_pin')}`",
            f"- `official_shadow_pin`: `{registry.get('official_shadow_pin')}`",
            f"- `production_candidate`: `{registry.get('production_candidate')}`",
            f"- `candidate_status`: `{registry.get('candidate_status')}`",
            "- Live production pin was not flipped.",
            "",
            "## Metrics",
            "",
            "| metric | current production | official shadow | frontier candidate |",
            "|---|---:|---:|---:|",
            f"| full Sharpe | {prod['full_sharpe']:.4f} | {shadow['full_sharpe']:.4f} | {cand['full_sharpe']:.4f} |",
            f"| full annual return | {prod['full_ann_return']:.4%} | {shadow['full_ann_return']:.4%} | {cand['full_ann_return']:.4%} |",
            f"| max drawdown | {prod['full_max_drawdown']:.4%} | {shadow['full_max_drawdown']:.4%} | {cand['full_max_drawdown']:.4%} |",
            f"| CVaR 5% | {prod['full_cvar_5']:.4%} | {shadow['full_cvar_5']:.4%} | {cand['full_cvar_5']:.4%} |",
            f"| holdout Sharpe | {prod['holdout_sharpe']:.4f} | {shadow['holdout_sharpe']:.4f} | {cand['holdout_sharpe']:.4f} |",
            f"| avg BIL | {prod['avg_BIL']:.4%} | {shadow['avg_BIL']:.4%} | {cand['avg_BIL']:.4%} |",
            f"| avg turnover | {prod['avg_turnover']:.4%} | {shadow['avg_turnover']:.4%} | {cand['avg_turnover']:.4%} |",
            "",
            "## Phase 10A Reproduction Check",
            "",
        ]
    )
    lines.append(md_table(metric_check))
    lines.extend(
        [
            "",
            "## Caveats",
            "",
            "- The candidate is still pending human production review.",
            "- The sleeve-weight file is a display/review proxy because the actual candidate is a wrapper modifier over final ETF weights.",
            "- Public dashboard bundles were not regenerated in this sprint.",
            "",
            "## Warnings",
            "",
        ]
    )
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    REPORT.write_text("\n".join(lines).rstrip() + "\n")


def main() -> None:
    warnings: list[str] = []
    print("Generating stable Frontier Phase 5 fragility guard artifact...")

    ggg_wrapper = AllocatorCheckpointWrapper(GGG)
    cmp = ggg_wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(cmp, 1e-10):
        raise SystemExit(f"GGG wrapper failed exact reproduction: {cmp}")

    prod_wrapper = AllocatorCheckpointWrapper(PROD_PIN)
    shadow_wrapper = AllocatorCheckpointWrapper(SHADOW_PIN)
    states = ggg_wrapper.states["market_state"].astype(str)
    modifier, scale = build_modifier(ggg_wrapper)
    result = ggg_wrapper.run(STABLE_NAME, [modifier])
    candidate_weights = result.weights.copy()
    candidate_path = result.path.copy()
    sleeve_proxy = sleeve_proxy_from_ggg(scale, warnings)

    sp_dates = states.index[states.eq("stressed_panic")]
    off_cols = sorted(OFFENSE & set(candidate_weights.columns) & set(ggg_wrapper.final_weights.columns))
    sp_diff = (
        candidate_weights.reindex(sp_dates)[off_cols].sum(axis=1)
        - ggg_wrapper.final_weights.reindex(sp_dates)[off_cols].sum(axis=1)
    ).abs().max()
    if not np.isfinite(sp_diff) or sp_diff > 1e-10:
        raise SystemExit(f"stressed_panic offense changed; max diff {sp_diff}")

    artifact_files = save_portfolio_artifacts(candidate_weights, candidate_path, sleeve_proxy)

    prod_run = prod_wrapper.run(PROD_PIN)
    shadow_run = shadow_wrapper.run(SHADOW_PIN)
    ggg_run = ggg_wrapper.run(GGG)
    rows_by_name = {
        STABLE_NAME: ("production_candidate_pending_human_review", candidate_weights, candidate_path, metric_dict(STABLE_NAME, candidate_weights, candidate_path, ggg_wrapper.next_week_returns)),
        PROD_PIN: ("current_production_and_rollback", prod_run.weights, prod_run.path, metric_dict(PROD_PIN, prod_run.weights, prod_run.path, ggg_wrapper.next_week_returns)),
        SHADOW_PIN: ("official_shadow", shadow_run.weights, shadow_run.path, metric_dict(SHADOW_PIN, shadow_run.weights, shadow_run.path, ggg_wrapper.next_week_returns)),
        GGG: ("prior_production_candidate_reference", ggg_run.weights, ggg_run.path, metric_dict(GGG, ggg_run.weights, ggg_run.path, ggg_wrapper.next_week_returns)),
    }
    summary = build_summary(rows_by_name)
    # Dashboard summary remains a three-role comparison; registry retains GGG as prior candidate.
    summary_for_dashboard = summary[summary["name"].isin([STABLE_NAME, PROD_PIN, SHADOW_PIN])].copy()
    summary_for_dashboard.to_csv(SUMMARY_CSV, index=False)
    state_summary = build_state_summary({k: v for k, v in rows_by_name.items() if k in [STABLE_NAME, PROD_PIN, SHADOW_PIN]}, states)
    state_summary.to_csv(STATE_CSV, index=False)
    build_exposure_summary(summary_for_dashboard).to_csv(EXPOSURE_CSV, index=False)
    registry = update_registry(summary)

    metric_check_rows = []
    if PH10_METRICS.exists():
        ph10 = pd.read_csv(PH10_METRICS)
        old = ph10[ph10["variant"].eq(SOURCE_LABEL)].head(1)
        if not old.empty:
            cand = summary.set_index("name").loc[STABLE_NAME]
            for new_col, old_col in [
                ("full_sharpe", "sharpe"),
                ("full_max_drawdown", "max_drawdown"),
                ("full_cvar_5", "cvar_5"),
                ("avg_turnover", "avg_turnover"),
            ]:
                metric_check_rows.append(
                    {
                        "metric": new_col,
                        "named_artifact": cand[new_col],
                        "phase10a_source": float(old.iloc[0][old_col]),
                        "abs_diff": abs(cand[new_col] - float(old.iloc[0][old_col])),
                    }
                )
    metric_check = pd.DataFrame(metric_check_rows)
    metric_check.to_csv(RESEARCH_OUT, index=False)

    if not metric_check.empty and metric_check["abs_diff"].max() > 1e-8:
        warnings.append("Named artifact metrics differ from Phase 10A source beyond 1e-8; inspect before production review.")

    public_src_diff = diff_name_only(PROTECTED_LIVE)
    if public_src_diff:
        raise SystemExit(f"Unexpected public/src diff after packaging: {public_src_diff}")

    if registry.get("current_production_pin") != PROD_PIN:
        raise SystemExit("Registry current_production_pin changed unexpectedly.")
    if registry.get("official_shadow_pin") != SHADOW_PIN:
        raise SystemExit("Registry official_shadow_pin changed unexpectedly.")

    write_report(summary_for_dashboard, artifact_files, registry, metric_check, warnings)

    print("Wrote named artifact files:")
    for path in artifact_files:
        print(f"- {rel(path)}")
    print(f"- {rel(SUMMARY_CSV)}")
    print(f"- {rel(STATE_CSV)}")
    print(f"- {rel(EXPOSURE_CSV)}")
    print(f"- {rel(REGISTRY_JSON)}")
    print(f"- {rel(RESEARCH_OUT)}")
    print(f"- {rel(REPORT)}")
    print("")
    cand = summary.set_index("name").loc[STABLE_NAME]
    print(f"{STABLE_NAME} Sharpe={cand['full_sharpe']:.6f} MaxDD={cand['full_max_drawdown']:.6f} HoldoutSharpe={cand['holdout_sharpe']:.6f}")
    print(f"stressed_panic offense max diff vs GGG={sp_diff:.3e}")
    print(f"current_production_pin remains {registry['current_production_pin']}")
    print(f"official_shadow_pin remains {registry['official_shadow_pin']}")
    print("public/ and src/ diff clean.")


if __name__ == "__main__":
    main()
