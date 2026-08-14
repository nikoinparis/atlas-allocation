"""R3 state-conditional signal IC.

Research-only output. Evaluates existing Layer 1 signals plus R2 candidates by
market state and horizon without changing production allocation logic.
"""

from __future__ import annotations

import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HORIZONS,
    SIGNAL_DIR,
    ensure_parent,
    load_candidate_signal_panel,
    load_existing_signal_panel,
    load_manifest,
    load_market_states,
    load_weekly_prices,
    markdown_table,
    read_csv_safe,
    state_conditional_ic_rows,
)


R2_FILES = [
    SIGNAL_DIR / "signal_r2_yield_curve.csv",
    SIGNAL_DIR / "signal_r2_credit_spread.csv",
    SIGNAL_DIR / "signal_r2_financial_conditions.csv",
    SIGNAL_DIR / "signal_r2_vix_term_structure.csv",
    SIGNAL_DIR / "signal_r2_dollar_strength.csv",
    SIGNAL_DIR / "signal_r2_commodity_regime.csv",
    SIGNAL_DIR / "signal_r2_cross_asset_divergence.csv",
    SIGNAL_DIR / "signal_r2_volume_divergence.csv",
]


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    manifest = load_manifest(warnings)
    summary = read_csv_safe(SIGNAL_DIR / "signal_summary_table.csv", warnings)
    if prices.empty:
        raise SystemExit("weekly_prices.csv is required for R3 state-conditional IC.")
    if states.empty:
        warnings.append("Market states unavailable; state-conditional IC cannot be grouped.")

    names = set()
    if manifest:
        names.update(str(item.get("signal_name")) for item in manifest if item.get("signal_name"))
    if not summary.empty and "signal_name" in summary.columns:
        names.update(summary["signal_name"].dropna().astype(str))

    rows: list[pd.DataFrame] = []
    skipped: list[dict] = []
    for name in sorted(names):
        panel = load_existing_signal_panel(name, manifest, warnings)
        if panel.empty or panel["signal_value_tradable"].notna().sum() == 0:
            skipped.append({"signal_name": name, "source": "existing", "reason": "No usable tradable signal panel."})
            continue
        state_rows = state_conditional_ic_rows(panel, prices, states, HORIZONS, min_assets=5)
        if state_rows.empty:
            skipped.append({"signal_name": name, "source": "existing", "reason": "No state-conditional IC rows could be computed."})
        else:
            state_rows["signal_source"] = "existing"
            rows.append(state_rows)

    for path in R2_FILES:
        if not path.exists():
            skipped.append({"signal_name": path.stem, "source": "R2", "reason": f"Missing file {path}"})
            continue
        panel = load_candidate_signal_panel(path, warnings)
        signal_name = panel["signal_name"].dropna().iloc[0] if not panel.empty and "signal_name" in panel.columns and panel["signal_name"].notna().any() else path.stem
        if panel.empty or panel["signal_value_tradable"].notna().sum() == 0:
            skipped.append({"signal_name": signal_name, "source": "R2", "reason": "No usable tradable signal panel."})
            continue
        state_rows = state_conditional_ic_rows(panel, prices, states, HORIZONS, min_assets=5)
        if state_rows.empty:
            skipped.append({"signal_name": signal_name, "source": "R2", "reason": "No state-conditional IC rows could be computed."})
        else:
            state_rows["signal_source"] = "R2"
            rows.append(state_rows)

    result = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(
        columns=["signal_name", "market_state", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates", "mean_coverage", "warning", "signal_source"]
    )
    out = SIGNAL_DIR / "signal_state_conditional_ic.csv"
    ensure_parent(out)
    result.to_csv(out, index=False)

    skipped_df = pd.DataFrame(skipped)
    calm = result[result["market_state"].eq("calm_trend")].sort_values(["mean_ic", "n_dates"], ascending=[False, False])
    neutral = result[result["market_state"].eq("neutral_mixed")].sort_values(["mean_ic", "n_dates"], ascending=[False, False])
    fragile = result[result["market_state"].eq("recovery_fragile")].sort_values(["mean_ic", "n_dates"], ascending=[False, False])
    confirmed = result[result["market_state"].eq("recovery_confirmed")].sort_values(["mean_ic", "n_dates"], ascending=[False, False])
    stress = result[result["market_state"].eq("stressed_panic")].sort_values(["mean_ic", "n_dates"], ascending=[False, False])
    stress_bad = result[result["market_state"].eq("stressed_panic")].sort_values(["mean_ic", "n_dates"], ascending=[True, False])

    regime_specific = pd.DataFrame()
    if not result.empty:
        pivot = result.pivot_table(index=["signal_name", "horizon_weeks"], columns="market_state", values="mean_ic", aggfunc="mean")
        pivot["state_ic_range"] = pivot.max(axis=1) - pivot.min(axis=1)
        pivot["positive_state_count"] = (pivot.drop(columns=["state_ic_range"], errors="ignore") > 0).sum(axis=1)
        regime_specific = pivot.reset_index().sort_values("state_ic_range", ascending=False)

    valid_ratio = float((result["n_dates"] >= 30).mean()) if not result.empty else 0.0
    if valid_ratio < 0.70:
        bottleneck = "Missing/sparse state data is a material bottleneck, especially for small recovery states and newer R2 inputs."
    else:
        bottleneck = "The evidence points more to signal quality and regime fit than missing data; most state/horizon cells have enough dates for directional read-through."

    report_path = DOCS_RESEARCH_DIR / "state_conditional_signal_report.md"
    report = [
        "# R3 State-Conditional Signal Report",
        "",
        "Research-only signal IC by market state. Signals are validated using existing tradable columns or one-period-lagged R2 tradable values, then compared with forward ETF returns by horizon.",
        "",
        f"- Output CSV: `{out}`",
        f"- State/horizon rows: {len(result)}",
        f"- Skipped/partial signal loads: {len(skipped_df)}",
        "",
        "## Which signals help calm_trend?",
        "",
        markdown_table(calm[["signal_name", "signal_source", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates"]], max_rows=15),
        "",
        "## Which signals help neutral_mixed?",
        "",
        markdown_table(neutral[["signal_name", "signal_source", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates"]], max_rows=10),
        "",
        "## Which signals help recovery_fragile?",
        "",
        markdown_table(fragile[["signal_name", "signal_source", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates"]], max_rows=10),
        "",
        "## Which signals help recovery_confirmed?",
        "",
        markdown_table(confirmed[["signal_name", "signal_source", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates"]], max_rows=10),
        "",
        "## Best stressed_panic defensive signals",
        "",
        markdown_table(stress[["signal_name", "signal_source", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates"]], max_rows=10),
        "",
        "## Which signals hurt stressed_panic?",
        "",
        markdown_table(stress_bad[["signal_name", "signal_source", "horizon_weeks", "mean_ic", "ic_tstat_nw", "hit_rate", "n_dates"]], max_rows=15),
        "",
        "## Which signals appear regime-specific?",
        "",
        markdown_table(regime_specific, max_rows=15),
        "",
        "## Bottleneck read",
        "",
        bottleneck,
        "",
        "## Sample-size warnings",
        "",
    ]
    small = result[result["warning"].fillna("").ne("")]
    report.append(markdown_table(small[["signal_name", "market_state", "horizon_weeks", "n_dates", "warning"]].drop_duplicates(), max_rows=30))
    report.extend(
        [
            "",
            "## Skipped or partial items",
            "",
            markdown_table(skipped_df),
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
            "R3 wrote only `signal_state_conditional_ic.csv` and this report. It did not modify production pins, dashboard/public files, production portfolio artifacts, or live trading/execution logic.",
        ]
    )
    ensure_parent(report_path)
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out}")
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
