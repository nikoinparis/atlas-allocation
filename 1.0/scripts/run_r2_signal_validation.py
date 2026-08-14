"""Validate R2 free-data candidate signals.

Research-only output. Candidate signals are not added to production logic; this
script only writes a validation CSV and a research report.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HORIZONS,
    SIGNAL_DIR,
    ensure_parent,
    evaluate_panel_signal,
    load_candidate_signal_panel,
    load_market_states,
    load_strong_existing_panels,
    load_weekly_prices,
    markdown_table,
    max_redundancy_against,
    state_conditional_ic_rows,
)


CANDIDATES = {
    "r2_yield_curve": SIGNAL_DIR / "signal_r2_yield_curve.csv",
    "r2_credit_spread": SIGNAL_DIR / "signal_r2_credit_spread.csv",
    "r2_financial_conditions": SIGNAL_DIR / "signal_r2_financial_conditions.csv",
    "r2_vix_term_structure": SIGNAL_DIR / "signal_r2_vix_term_structure.csv",
    "r2_dollar_strength": SIGNAL_DIR / "signal_r2_dollar_strength.csv",
    "r2_commodity_regime": SIGNAL_DIR / "signal_r2_commodity_regime.csv",
    "r2_cross_asset_divergence": SIGNAL_DIR / "signal_r2_cross_asset_divergence.csv",
    "r2_volume_divergence": SIGNAL_DIR / "signal_r2_volume_divergence.csv",
}


def verdict_from_metrics(row: dict) -> tuple[str, str]:
    reasons: list[str] = []
    if row["min_full_n_dates"] < 156 or row["min_holdout_n_dates"] < 52:
        reasons.append("insufficient observations")
    if pd.isna(row["avg_full_mean_ic"]):
        return "skipped", "No valid IC observations after lagging/alignment."
    if row["avg_full_mean_ic"] <= 0:
        reasons.append("full-period IC is not positive")
    if pd.isna(row["avg_holdout_mean_ic"]) or row["avg_holdout_mean_ic"] <= 0:
        reasons.append("holdout IC is not positive")
    if pd.notna(row["max_redundancy_vs_strong"]) and row["max_redundancy_vs_strong"] > 0.50:
        reasons.append("redundancy above 0.50 versus existing strong signals")
    if row.get("stressed_panic_damage", False):
        reasons.append("obvious stressed_panic damage")
    if not reasons:
        return "candidate-pass", "Passes positive full/holdout IC, redundancy, stressed_panic, and observation gates."
    if "full-period IC is not positive" in reasons or "holdout IC is not positive" in reasons or "obvious stressed_panic damage" in reasons:
        return "rejected", "; ".join(reasons)
    return "research-only", "; ".join(reasons)


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    strong_panels = load_strong_existing_panels(warnings)
    if prices.empty:
        raise SystemExit("weekly_prices.csv is required for R2 validation.")

    rows: list[dict] = []
    state_rows: list[pd.DataFrame] = []
    for name, path in CANDIDATES.items():
        if not path.exists():
            row = {
                "signal_name": name,
                "file": str(path),
                "verdict": "skipped",
                "verdict_reason": f"Missing candidate file: {path}",
                "avg_full_mean_ic": np.nan,
                "avg_holdout_mean_ic": np.nan,
                "max_redundancy_vs_strong": np.nan,
                "most_redundant_existing_signal": "",
                "stressed_panic_mean_ic": np.nan,
                "stressed_panic_damage": False,
                "min_full_n_dates": 0,
                "min_holdout_n_dates": 0,
                "tradable_missingness": np.nan,
            }
            rows.append(row)
            warnings.append(row["verdict_reason"])
            continue
        panel = load_candidate_signal_panel(path, warnings)
        if panel.empty or panel["signal_value_tradable"].notna().sum() == 0:
            row = {
                "signal_name": name,
                "file": str(path),
                "verdict": "skipped",
                "verdict_reason": "No tradable signal values after lagging/alignment.",
                "avg_full_mean_ic": np.nan,
                "avg_holdout_mean_ic": np.nan,
                "max_redundancy_vs_strong": np.nan,
                "most_redundant_existing_signal": "",
                "stressed_panic_mean_ic": np.nan,
                "stressed_panic_damage": False,
                "min_full_n_dates": 0,
                "min_holdout_n_dates": 0,
                "tradable_missingness": 1.0,
            }
            rows.append(row)
            continue

        eval_rows = evaluate_panel_signal(panel, prices, HORIZONS, min_assets=5)
        state_eval = state_conditional_ic_rows(panel, prices, states, HORIZONS, min_assets=5)
        if not state_eval.empty:
            state_rows.append(state_eval)
        max_red, red_name = max_redundancy_against(panel, strong_panels)
        stress = state_eval[state_eval["market_state"].eq("stressed_panic")] if not state_eval.empty else pd.DataFrame()
        stress_mean = float(stress["mean_ic"].mean()) if not stress.empty else np.nan
        stress_n = int(stress["n_dates"].max()) if not stress.empty else 0
        stressed_damage = bool(pd.notna(stress_mean) and stress_n >= 30 and stress_mean < -0.02)

        row = {
            "signal_name": name,
            "file": str(path),
            "avg_full_mean_ic": float(eval_rows["full_mean_ic"].mean()),
            "avg_holdout_mean_ic": float(eval_rows["holdout_mean_ic"].mean()),
            "avg_full_nw_tstat": float(eval_rows["full_ic_tstat_nw"].mean()),
            "avg_holdout_nw_tstat": float(eval_rows["holdout_ic_tstat_nw"].mean()),
            "min_full_n_dates": int(eval_rows["full_n_dates"].min()),
            "min_holdout_n_dates": int(eval_rows["holdout_n_dates"].min()),
            "max_redundancy_vs_strong": max_red,
            "most_redundant_existing_signal": red_name,
            "stressed_panic_mean_ic": stress_mean,
            "stressed_panic_damage": stressed_damage,
            "tradable_missingness": float(panel["signal_value_tradable"].isna().mean()),
        }
        for horizon in HORIZONS:
            hrow = eval_rows[eval_rows["horizon_weeks"].eq(horizon)]
            if not hrow.empty:
                row[f"full_ic_{horizon}w"] = float(hrow["full_mean_ic"].iloc[0])
                row[f"holdout_ic_{horizon}w"] = float(hrow["holdout_mean_ic"].iloc[0])
        verdict, reason = verdict_from_metrics(row)
        row["verdict"] = verdict
        row["verdict_reason"] = reason
        rows.append(row)

    results = pd.DataFrame(rows)
    out = SIGNAL_DIR / "r2_signal_validation_results.csv"
    ensure_parent(out)
    results.to_csv(out, index=False)

    state_all = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    pass_df = results[results["verdict"].eq("candidate-pass")]
    rejected = results[results["verdict"].eq("rejected")]
    skipped = results[results["verdict"].eq("skipped")]
    research_only = results[results["verdict"].eq("research-only")]

    report_path = DOCS_RESEARCH_DIR / "r2_signal_validation_report.md"
    report = [
        "# R2 Signal Validation Report",
        "",
        "Research-only validation of the expanded free-data signal zoo. All candidate signals are lagged via `signal_value_tradable` before validation. No signal was added to production logic.",
        "",
        f"- Output CSV: `{out}`",
        f"- Signals attempted: {len(results)}",
        f"- Candidate-pass: {len(pass_df)}",
        f"- Research-only: {len(research_only)}",
        f"- Rejected: {len(rejected)}",
        f"- Skipped: {len(skipped)}",
        "",
        "## Verdict table",
        "",
        markdown_table(
            results[
                [
                    "signal_name",
                    "verdict",
                    "avg_full_mean_ic",
                    "avg_holdout_mean_ic",
                    "max_redundancy_vs_strong",
                    "most_redundant_existing_signal",
                    "stressed_panic_mean_ic",
                    "verdict_reason",
                ]
            ]
        ),
        "",
        "## Candidate-pass signals",
        "",
        markdown_table(pass_df[["signal_name", "avg_full_mean_ic", "avg_holdout_mean_ic", "max_redundancy_vs_strong"]]),
        "",
        "## Research-only signals",
        "",
        markdown_table(research_only[["signal_name", "avg_full_mean_ic", "avg_holdout_mean_ic", "verdict_reason"]]),
        "",
        "## Rejected signals",
        "",
        markdown_table(rejected[["signal_name", "avg_full_mean_ic", "avg_holdout_mean_ic", "stressed_panic_mean_ic", "verdict_reason"]]),
        "",
        "## Skipped signals",
        "",
        markdown_table(skipped[["signal_name", "verdict_reason"]]),
        "",
        "## State-conditional notes",
        "",
    ]
    if state_all.empty:
        report.append("- State-conditional validation was unavailable because no state rows could be computed.")
    else:
        calm = state_all[state_all["market_state"].eq("calm_trend")].sort_values("mean_ic", ascending=False)
        stress_bad = state_all[state_all["market_state"].eq("stressed_panic")].sort_values("mean_ic")
        report.append("Top calm_trend R2 signal/horizon rows:")
        report.append("")
        report.append(markdown_table(calm[["signal_name", "horizon_weeks", "mean_ic", "ic_tstat_nw", "n_dates"]], max_rows=10))
        report.append("")
        report.append("Worst stressed_panic R2 signal/horizon rows:")
        report.append("")
        report.append(markdown_table(stress_bad[["signal_name", "horizon_weeks", "mean_ic", "ic_tstat_nw", "n_dates"]], max_rows=10))
    report.extend(
        [
            "",
            "## Warnings and limitations",
            "",
        ]
    )
    report.extend([f"- {w}" for w in sorted(set(warnings))] or ["- None."])
    report.extend(
        [
            "",
            "## Research-only confirmation",
            "",
            "R2 wrote candidate signal CSVs and validation reports only. It did not alter production pins, dashboard/public files, existing production portfolio returns/weights, or live trading/execution logic.",
        ]
    )
    ensure_parent(report_path)
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
