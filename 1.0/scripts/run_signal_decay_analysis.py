"""R1 signal decay and research-log initializer.

Research-only output. This script uses existing Layer 1 validation artifacts and
does not recompute or promote any production portfolio logic.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import DOCS_RESEARCH_DIR, HORIZONS, SIGNAL_DIR, ensure_parent, load_manifest, markdown_table, read_csv_safe


def classify_half_life(half_life: float | None, warning: str) -> str:
    if half_life is not None and math.isinf(half_life):
        return "slow decay"
    if warning or half_life is None or pd.isna(half_life):
        return "unclear"
    if half_life > 6:
        return "slow decay"
    if half_life >= 2:
        return "medium decay"
    return "fast decay"


def estimate_half_life(rows: pd.DataFrame) -> tuple[float | None, str]:
    if rows.empty:
        return None, "No IC-by-horizon rows available."
    rows = rows.dropna(subset=["horizon_weeks", "mean_ic"]).copy()
    rows["abs_ic"] = rows["mean_ic"].abs()
    rows = rows[rows["abs_ic"] > 0].sort_values("horizon_weeks")
    if rows.shape[0] < 3:
        return None, "Insufficient non-zero horizon IC observations for half-life fit."
    if 1 not in set(rows["horizon_weeks"].astype(int)):
        return None, "No 1-week IC anchor available for half-life fit."
    x = rows["horizon_weeks"].astype(float).to_numpy()
    y = np.log(rows["abs_ic"].astype(float).to_numpy())
    try:
        slope, intercept = np.polyfit(x, y, 1)
    except Exception as exc:
        return None, f"Half-life fit failed: {exc}"
    if not np.isfinite(slope):
        return None, "Half-life fit produced non-finite slope."
    if slope >= 0:
        return math.inf, "No observed exponential decay across available horizons."
    half_life = float(math.log(0.5) / slope)
    if half_life <= 0 or not np.isfinite(half_life):
        return None, "Half-life estimate was not usable."
    return half_life, ""


def compact_incremental(incremental: pd.DataFrame, signal_name: str) -> str:
    if incremental.empty or "candidate_signal" not in incremental.columns:
        return ""
    matches = incremental[incremental["candidate_signal"].eq(signal_name)]
    if matches.empty:
        return ""
    cols = [
        "delta_ann_return_vs_base",
        "delta_sharpe_vs_base",
        "delta_max_drawdown_vs_base",
        "delta_cvar_5_vs_base",
        "delta_turnover_vs_base",
    ]
    parts = []
    row = matches.iloc[0]
    for col in cols:
        if col in matches.columns and pd.notna(row.get(col)):
            parts.append(f"{col}={row[col]:.4f}")
    return "; ".join(parts)


def main() -> None:
    warnings: list[str] = []
    manifest = load_manifest(warnings)
    manifest_df = pd.DataFrame(manifest)
    summary = read_csv_safe(SIGNAL_DIR / "signal_summary_table.csv", warnings)
    ic = read_csv_safe(SIGNAL_DIR / "signal_ic_by_horizon.csv", warnings)
    redundancy = read_csv_safe(SIGNAL_DIR / "signal_redundancy_matrix.csv", warnings)
    incremental = read_csv_safe(SIGNAL_DIR / "signal_incremental_contribution.csv", warnings)

    names = set()
    if not manifest_df.empty and "signal_name" in manifest_df.columns:
        names.update(manifest_df["signal_name"].dropna().astype(str))
    if not summary.empty and "signal_name" in summary.columns:
        names.update(summary["signal_name"].dropna().astype(str))
    if not ic.empty and "signal_name" in ic.columns:
        names.update(ic["signal_name"].dropna().astype(str))

    rows: list[dict] = []
    for name in sorted(names):
        ic_rows = ic[ic["signal_name"].eq(name)] if not ic.empty and "signal_name" in ic.columns else pd.DataFrame()
        half_life, warning = estimate_half_life(ic_rows)
        row = {
            "signal_name": name,
            "half_life_weeks": half_life,
            "decay_classification": classify_half_life(half_life, warning),
            "weekly_rebalance_viability_flag": "",
            "fit_warning": warning,
        }
        for horizon in HORIZONS:
            subset = ic_rows[ic_rows["horizon_weeks"].eq(horizon)] if not ic_rows.empty else pd.DataFrame()
            row[f"ic_{horizon}w"] = float(subset["mean_ic"].iloc[0]) if not subset.empty else np.nan
            row[f"nw_tstat_{horizon}w"] = float(subset["ic_tstat_nw"].iloc[0]) if not subset.empty and "ic_tstat_nw" in subset.columns else np.nan
        available_ics = [row[f"ic_{h}w"] for h in HORIZONS if pd.notna(row[f"ic_{h}w"])]
        avg_ic = float(np.mean(available_ics)) if available_ics else np.nan
        row["avg_available_ic"] = avg_ic
        if row["decay_classification"] == "fast decay":
            row["weekly_rebalance_viability_flag"] = "Potentially too short-lived for weekly rebalance; needs faster implementation evidence."
        if pd.notna(avg_ic) and avg_ic <= 0:
            row["weekly_rebalance_viability_flag"] = (row["weekly_rebalance_viability_flag"] + " Weak/non-positive average IC.").strip()
        rows.append(row)

    decay = pd.DataFrame(rows).sort_values(["decay_classification", "avg_available_ic"], ascending=[True, False])
    out_path = SIGNAL_DIR / "signal_decay_profiles.csv"
    ensure_parent(out_path)
    decay.to_csv(out_path, index=False)

    if redundancy.empty:
        avg_abs_redundancy = {}
    else:
        red = redundancy.copy()
        first = red.columns[0]
        red = red.rename(columns={first: "signal_name"}).set_index("signal_name")
        avg_abs_redundancy = red.abs().replace(1.0, np.nan).mean(axis=1).to_dict()

    log_rows: list[dict] = []
    for name in sorted(names):
        manifest_row = manifest_df[manifest_df["signal_name"].eq(name)].iloc[0].to_dict() if not manifest_df.empty and "signal_name" in manifest_df.columns and manifest_df["signal_name"].eq(name).any() else {}
        summary_row = summary[summary["signal_name"].eq(name)].iloc[0].to_dict() if not summary.empty and "signal_name" in summary.columns and summary["signal_name"].eq(name).any() else {}
        decay_row = decay[decay["signal_name"].eq(name)].iloc[0].to_dict() if not decay.empty and decay["signal_name"].eq(name).any() else {}
        log_rows.append(
            {
                "signal_name": name,
                "category": manifest_row.get("category", ""),
                "source_file": manifest_row.get("file_name", ""),
                "description": manifest_row.get("description", ""),
                "avg_mean_ic": summary_row.get("avg_mean_ic", np.nan),
                "avg_nw_tstat": summary_row.get("avg_ic_tstat_nw", np.nan),
                "validation_score": summary_row.get("validation_quality_score", np.nan),
                "avg_abs_redundancy": summary_row.get("avg_abs_redundancy", avg_abs_redundancy.get(name, np.nan)),
                "recommendation": summary_row.get("recommendation", "not_in_summary"),
                "decay_classification": decay_row.get("decay_classification", "unclear"),
                "half_life_weeks": decay_row.get("half_life_weeks", np.nan),
                "incremental_contribution": compact_incremental(incremental, name),
                "research_status": "existing_signal_research_log_entry",
            }
        )
    research_log = pd.DataFrame(log_rows)

    log_path = DOCS_RESEARCH_DIR / "signal_research_log.md"
    ensure_parent(log_path)
    log_text = [
        "# Signal Research Log",
        "",
        "Research-only inventory initialized during Renaissance R1. Existing signals are logged from the manifest, summary table, IC-by-horizon file, redundancy matrix, and incremental contribution file where available.",
        "",
        "No production pins, production portfolio artifacts, dashboard files, or live trading logic were modified.",
        "",
        markdown_table(research_log),
        "",
        "## Warnings",
        "",
    ]
    log_text.extend([f"- {w}" for w in warnings] or ["- None."])
    log_path.write_text("\n".join(log_text) + "\n")

    slow = decay[decay["decay_classification"].eq("slow decay")].sort_values("avg_available_ic", ascending=False)
    fast_or_weak = decay[
        decay["decay_classification"].eq("fast decay")
        | decay["weekly_rebalance_viability_flag"].fillna("").str.len().gt(0)
    ].sort_values("avg_available_ic")
    unclear = decay[decay["decay_classification"].eq("unclear")]

    report_path = DOCS_RESEARCH_DIR / "r1_signal_decay_report.md"
    report = [
        "# R1 Signal Decay Report",
        "",
        "Research-only signal decay analysis using existing `signal_ic_by_horizon.csv`. Half-life estimates are based on an exponential fit to absolute IC across available horizons and are diagnostic, not a promotion rule.",
        "",
        f"- Signals covered: {len(decay)}",
        f"- Output CSV: `{out_path}`",
        f"- Research log: `{log_path}`",
        "",
        "## Strongest slow-decay signals",
        "",
        markdown_table(slow[["signal_name", "half_life_weeks", "avg_available_ic", "ic_1w", "ic_4w", "ic_13w"]], max_rows=12),
        "",
        "## Weakest or fast-decay signals",
        "",
        markdown_table(fast_or_weak[["signal_name", "decay_classification", "half_life_weeks", "avg_available_ic", "weekly_rebalance_viability_flag"]], max_rows=15),
        "",
        "## Signals with unclear decay",
        "",
        markdown_table(unclear[["signal_name", "fit_warning"]], max_rows=30),
        "",
        "## Data limitations and warnings",
        "",
    ]
    report.extend([f"- {w}" for w in sorted(set(warnings + decay["fit_warning"].dropna().loc[lambda s: s.ne("")].tolist()))] or ["- None."])
    report.append("")
    report.append("## Research-only confirmation")
    report.append("")
    report.append("R1 wrote only research reports and `data/02_layer1_signals/signal_decay_profiles.csv`; it did not alter production allocation, dashboard, public, or trading/execution files.")
    ensure_parent(report_path)
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out_path}")
    print(f"Wrote {log_path}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
