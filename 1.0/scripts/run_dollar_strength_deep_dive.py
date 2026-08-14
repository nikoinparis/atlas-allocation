"""Research-only dollar strength deep dive and B5 priority ranking.

This script studies UUP momentum variants and then compiles the B1-B4 research
outputs into the sprint priority table. It does not promote any signal or alter
production allocation logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HORIZONS,
    SIGNAL_DIR,
    dollar_loading,
    ensure_parent,
    evaluate_panel_signal,
    load_market_states,
    load_strong_existing_panels,
    load_weekly_prices,
    markdown_table,
    max_redundancy_against,
    panel_from_series,
    read_csv_safe,
    state_conditional_ic_rows,
)


WINDOWS = {"4w": 4, "8w": 8, "13w": 13, "26w": 26}
RELATION_BASKETS = {
    "commodities": ["PDBC", "USO", "DBA", "SLV", "GLD"],
    "em": ["EEM", "VWO"],
    "bonds": ["TLT", "IEF", "LQD"],
    "spy": ["SPY"],
    "risk_on": ["SPY", "QQQ", "IWM", "HYG"],
}


def dollar_loadings(prices: pd.DataFrame) -> dict[str, float]:
    return {ticker: dollar_loading(ticker) for ticker in prices.columns}


def future_basket_return(prices: pd.DataFrame, tickers: list[str], horizon: int = 4) -> pd.Series:
    available = [t for t in tickers if t in prices.columns]
    if not available:
        return pd.Series(index=prices.index, dtype=float)
    fwd = prices[available].shift(-horizon) / prices[available] - 1.0
    return fwd.mean(axis=1, skipna=True)


def corr_safe(x: pd.Series, y: pd.Series) -> float:
    aligned = pd.concat([x, y], axis=1).dropna()
    if len(aligned) < 30 or aligned.iloc[:, 0].nunique() < 2 or aligned.iloc[:, 1].nunique() < 2:
        return np.nan
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman"))


def make_variant_series(prices: pd.DataFrame) -> dict[str, pd.Series]:
    if "UUP" not in prices.columns:
        return {}
    uup = prices["UUP"].astype(float)
    variants = {f"bm_dollar_strength_{label}": uup.pct_change(window) for label, window in WINDOWS.items()}
    variants["bm_dollar_strength_blended"] = pd.concat(list(variants.values()), axis=1).mean(axis=1, skipna=True)
    return variants


def first_second_half_redundancy(panel: pd.DataFrame, strong_panels: dict[str, pd.DataFrame]) -> tuple[float, float]:
    if panel.empty or not strong_panels:
        return np.nan, np.nan
    dates = pd.Series(panel["Date"].dropna().unique()).sort_values()
    if len(dates) < 100:
        return np.nan, np.nan
    split = dates.iloc[len(dates) // 2]
    first = panel[panel["Date"] <= split]
    second = panel[panel["Date"] > split]
    red_first, _ = max_redundancy_against(first, strong_panels, min_obs=50)
    red_second, _ = max_redundancy_against(second, strong_panels, min_obs=50)
    return red_first, red_second


def deep_dive_rows(
    name: str,
    scalar: pd.Series,
    panel: pd.DataFrame,
    prices: pd.DataFrame,
    states: pd.DataFrame,
    strong_panels: dict[str, pd.DataFrame],
) -> dict:
    eval_rows = evaluate_panel_signal(panel, prices, HORIZONS, min_assets=5)
    state_rows = state_conditional_ic_rows(panel, prices, states, HORIZONS, min_assets=5)
    max_red, red_name = max_redundancy_against(panel, strong_panels)
    red_first, red_second = first_second_half_redundancy(panel, strong_panels)
    calm = state_rows[state_rows["market_state"].eq("calm_trend")] if not state_rows.empty else pd.DataFrame()
    stress = state_rows[state_rows["market_state"].eq("stressed_panic")] if not state_rows.empty else pd.DataFrame()
    tradable_scalar = scalar.shift(1)
    row = {
        "signal_name": name,
        "avg_full_mean_ic": float(eval_rows["full_mean_ic"].mean()) if not eval_rows.empty else np.nan,
        "avg_holdout_mean_ic": float(eval_rows["holdout_mean_ic"].mean()) if not eval_rows.empty else np.nan,
        "avg_full_nw_tstat": float(eval_rows["full_ic_tstat_nw"].mean()) if not eval_rows.empty else np.nan,
        "avg_holdout_nw_tstat": float(eval_rows["holdout_ic_tstat_nw"].mean()) if not eval_rows.empty else np.nan,
        "calm_trend_mean_ic": float(calm["mean_ic"].mean()) if not calm.empty else np.nan,
        "stressed_panic_mean_ic": float(stress["mean_ic"].mean()) if not stress.empty else np.nan,
        "min_full_n_dates": int(eval_rows["full_n_dates"].min()) if not eval_rows.empty else 0,
        "min_holdout_n_dates": int(eval_rows["holdout_n_dates"].min()) if not eval_rows.empty else 0,
        "max_redundancy_vs_strong": max_red,
        "most_redundant_existing_signal": red_name,
        "redundancy_first_half": red_first,
        "redundancy_second_half": red_second,
        "redundancy_drift": red_second - red_first if pd.notna(red_first) and pd.notna(red_second) else np.nan,
        "research_only": True,
    }
    for basket, tickers in RELATION_BASKETS.items():
        row[f"corr_with_future_4w_{basket}_return"] = corr_safe(tradable_scalar, future_basket_return(prices, tickers, 4))
    if not states.empty and "Date" in states.columns:
        state_idx = states.copy()
        state_idx["Date"] = pd.to_datetime(state_idx["Date"], errors="coerce")
        state_idx = state_idx.dropna(subset=["Date"]).set_index("Date")
        if "breadth_13w_mom" in state_idx.columns:
            row["corr_with_future_4w_breadth_change"] = corr_safe(tradable_scalar, pd.to_numeric(state_idx["breadth_13w_mom"], errors="coerce").diff(4).shift(-4))
        if "market_drawdown" in state_idx.columns:
            row["corr_with_future_4w_drawdown_change"] = corr_safe(tradable_scalar, pd.to_numeric(state_idx["market_drawdown"], errors="coerce").diff(4).shift(-4))
    reasons: list[str] = []
    if row["avg_full_mean_ic"] <= 0 or pd.isna(row["avg_full_mean_ic"]):
        reasons.append("full IC not positive")
    if row["avg_holdout_mean_ic"] <= 0 or pd.isna(row["avg_holdout_mean_ic"]):
        reasons.append("holdout IC not positive")
    if pd.notna(row["stressed_panic_mean_ic"]) and row["stressed_panic_mean_ic"] < -0.02:
        reasons.append("stressed_panic damage")
    if not reasons:
        row["verdict"] = "candidate-pass"
        row["verdict_reason"] = "Positive full/holdout IC and no large stressed_panic damage."
    elif row["avg_holdout_mean_ic"] > 0 and row["calm_trend_mean_ic"] > 0:
        row["verdict"] = "research-only"
        row["verdict_reason"] = "; ".join(reasons)
    else:
        row["verdict"] = "reject"
        row["verdict_reason"] = "; ".join(reasons)
    return row


def recommendation(row: pd.Series) -> str:
    verdict = str(row.get("verdict", "research-only"))
    stress = row.get("stressed_panic_mean_ic", np.nan)
    calm = row.get("calm_trend_mean_ic", np.nan)
    holdout = row.get("avg_holdout_mean_ic", np.nan)
    full = row.get("avg_full_mean_ic", np.nan)
    if verdict == "candidate-pass":
        return "candidate-pass"
    if pd.notna(stress) and stress < -0.03:
        return "reject"
    if pd.notna(calm) and calm > 0.02 and pd.notna(holdout) and holdout > 0:
        return "promising-if-gated"
    if pd.notna(full) and full > 0 and pd.notna(holdout) and holdout > 0:
        return "research-only"
    return "reject"


def compile_priority_outputs() -> None:
    sources = [
        ("breadth", SIGNAL_DIR / "breadth_signal_summary.csv", "breadth/participation"),
        ("state_gated_macro", SIGNAL_DIR / "state_gated_macro_results.csv", "state-gated macro"),
        ("signal_quality", SIGNAL_DIR / "signal_quality_feature_validation.csv", "signal quality/meta"),
        ("dollar_strength", SIGNAL_DIR / "dollar_strength_deep_dive.csv", "dollar strength"),
    ]
    frames: list[pd.DataFrame] = []
    for source, path, category in sources:
        df = read_csv_safe(path, [])
        if df.empty:
            continue
        df = df.copy()
        if "signal_name" not in df.columns and "gated_signal_name" in df.columns:
            df["signal_name"] = df["gated_signal_name"]
        df["source_phase"] = source
        df["category"] = df.get("category", category)
        df["orthogonality"] = 1.0 - pd.to_numeric(df.get("max_redundancy_vs_strong", np.nan), errors="coerce")
        df["full_ic"] = pd.to_numeric(df.get("avg_full_mean_ic", np.nan), errors="coerce")
        df["holdout_ic"] = pd.to_numeric(df.get("avg_holdout_mean_ic", np.nan), errors="coerce")
        df["calm_trend_usefulness"] = pd.to_numeric(df.get("calm_trend_mean_ic", np.nan), errors="coerce")
        df["stressed_panic_danger"] = -pd.to_numeric(df.get("stressed_panic_mean_ic", np.nan), errors="coerce")
        df["data_quality_risk"] = np.where(source == "breadth", "low", np.where(source == "state_gated_macro", "medium", "low"))
        df["pit_dependence"] = "none"
        df["overfitting_risk"] = np.where(source == "state_gated_macro", "medium", "low")
        df["recommendation"] = df.apply(recommendation, axis=1)
        df["priority_score"] = (
            df["full_ic"].fillna(-0.05) * 10
            + df["holdout_ic"].fillna(-0.05) * 15
            + df["calm_trend_usefulness"].fillna(0) * 8
            - df["stressed_panic_danger"].clip(lower=0).fillna(0) * 10
            + df["orthogonality"].fillna(0.5)
        )
        df["implementation_difficulty"] = np.where(source == "state_gated_macro", "medium", "low")
        frames.append(df)
    table = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    keep = [
        "signal_name",
        "source_phase",
        "category",
        "orthogonality",
        "full_ic",
        "holdout_ic",
        "calm_trend_usefulness",
        "stressed_panic_danger",
        "implementation_difficulty",
        "data_quality_risk",
        "pit_dependence",
        "overfitting_risk",
        "recommendation",
        "priority_score",
        "verdict",
        "verdict_reason",
    ]
    for col in keep:
        if col not in table.columns:
            table[col] = np.nan
    table = table[keep].sort_values("priority_score", ascending=False)
    out = SIGNAL_DIR / "breadth_macro_priority_table.csv"
    ensure_parent(out)
    table.to_csv(out, index=False)

    report_path = DOCS_RESEARCH_DIR / "breadth_macro_priority_rankings.md"
    immediate = table[table["recommendation"].isin(["candidate-pass", "research-only"])].head(10)
    conditional = table[table["recommendation"].eq("promising-if-gated")].head(10)
    breadth = table[table["source_phase"].eq("breadth")].head(10)
    rejected = table[table["recommendation"].eq("reject")].sort_values("priority_score").head(10)
    report = [
        "# Breadth + Macro Priority Rankings",
        "",
        "Research-only B5 ranking of tested breadth, state-gated macro, signal-quality, and dollar-strength features. Recommendations are not production promotions.",
        "",
        f"- Priority table: `{out}`",
        f"- Rows ranked: {len(table)}",
        "",
        "## Top 10 Immediate Next-Test Candidates",
        "",
        markdown_table(immediate[["signal_name", "source_phase", "recommendation", "full_ic", "holdout_ic", "calm_trend_usefulness", "stressed_panic_danger", "priority_score"]]),
        "",
        "## Top 10 Promising Conditional Signals",
        "",
        markdown_table(conditional[["signal_name", "source_phase", "recommendation", "full_ic", "holdout_ic", "calm_trend_usefulness", "stressed_panic_danger", "priority_score"]]),
        "",
        "## Top Breadth Ideas",
        "",
        markdown_table(breadth[["signal_name", "recommendation", "full_ic", "holdout_ic", "calm_trend_usefulness", "stressed_panic_danger", "priority_score"]]),
        "",
        "## PIT-Data Future Ideas",
        "",
        "- No PIT-dependent signal was implemented in this sprint. True constituent breadth, new-high/new-low breadth, advance/decline lines, and sector valuation breadth remain future paid/PIT candidates from the prior discovery backlog.",
        "",
        "## Reject / Avoid",
        "",
        markdown_table(rejected[["signal_name", "source_phase", "recommendation", "full_ic", "holdout_ic", "stressed_panic_danger", "priority_score", "verdict_reason"]]),
    ]
    report_path.write_text("\n".join(report) + "\n")
    print(f"Wrote {out} rows={len(table)}")
    print(f"Wrote {report_path}")


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    strong_panels = load_strong_existing_panels(warnings)

    rows: list[dict] = []
    if prices.empty:
        warnings.append("weekly_prices.csv unavailable; dollar strength deep dive skipped.")
    elif "UUP" not in prices.columns:
        warnings.append("UUP absent from weekly_prices.csv; dollar strength deep dive skipped.")
    else:
        for name, scalar in make_variant_series(prices).items():
            panel = panel_from_series(
                scalar,
                signal_name=name,
                loadings=dollar_loadings(prices),
                source="data/01_data_hub/weekly_prices.csv UUP",
                frequency="weekly",
                notes="UUP momentum variant expanded using static dollar exposure loadings; one-week lagged before validation.",
            )
            out = SIGNAL_DIR / f"signal_{name}.csv"
            ensure_parent(out)
            panel.to_csv(out, index=False)
            rows.append(deep_dive_rows(name, scalar, panel, prices, states, strong_panels))

    results = pd.DataFrame(rows)
    out = SIGNAL_DIR / "dollar_strength_deep_dive.csv"
    ensure_parent(out)
    results.to_csv(out, index=False)
    relationship_cols = [
        "signal_name",
        "corr_with_future_4w_commodities_return",
        "corr_with_future_4w_em_return",
        "corr_with_future_4w_bonds_return",
        "corr_with_future_4w_spy_return",
        "corr_with_future_4w_risk_on_return",
        "corr_with_future_4w_breadth_change",
        "corr_with_future_4w_drawdown_change",
    ]
    for col in relationship_cols:
        if col not in results.columns:
            results[col] = np.nan

    report_path = DOCS_RESEARCH_DIR / "dollar_strength_deep_dive_report.md"
    report = [
        "# Dollar Strength Deep Dive Report",
        "",
        "Research-only B4 diagnostic of UUP momentum windows. This is an explanatory validation exercise, not a production deployment.",
        "",
        f"- Deep dive CSV: `{out}`",
        f"- Variants tested: {len(results)}",
        "",
        "## Variant Results",
        "",
        markdown_table(
            results[
                [
                    "signal_name",
                    "verdict",
                    "avg_full_mean_ic",
                    "avg_holdout_mean_ic",
                    "calm_trend_mean_ic",
                    "stressed_panic_mean_ic",
                    "max_redundancy_vs_strong",
                    "redundancy_drift",
                    "verdict_reason",
                ]
            ]
            if not results.empty
            else results
        ),
        "",
        "## Cross-Asset Relationship Diagnostics",
        "",
        markdown_table(results[relationship_cols] if not results.empty else results),
        "",
        "## Interpretation",
        "",
        "- Dollar strength is treated as a cross-asset pressure signal: positive UUP momentum generally loads positively on UUP/cash-like exposure and negatively on EM, commodities, and risk assets.",
        "- A robust dollar signal should not only pass average IC tests; it should also avoid becoming a hidden stressed_panic amplifier.",
        "- Window comparisons are diagnostic only. No window is optimized or promoted here.",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out} rows={len(results)}")
    print(f"Wrote {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    compile_priority_outputs()


if __name__ == "__main__":
    main()
