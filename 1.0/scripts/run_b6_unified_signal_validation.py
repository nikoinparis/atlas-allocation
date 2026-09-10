"""B6 unified research-only validation for selected breadth/macro/dollar signals.

This script is intentionally read-only with respect to production artifacts. It
loads existing Layer 1 research panels, applies any needed one-week-lagged gates,
and writes validation summaries for a later controlled portfolio pass-through
decision. It does not alter allocation, dashboard, public, R5, or R6 logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HORIZONS,
    SIGNAL_DIR,
    ensure_parent,
    load_candidate_signal_panel,
    load_market_states,
    load_strong_existing_panels,
    load_weekly_prices,
    markdown_table,
    newey_west_tstat,
    read_csv_safe,
    summarize_ic,
)
from run_state_gated_macro_tests import apply_gate, load_gate_frame


SELECTED_CANDIDATES = [
    ("bm_etf_above_50d_ma", "breadth", SIGNAL_DIR / "signal_bm_etf_above_50d_ma.csv", None, "alpha_or_offense_gate"),
    ("bm_etf_above_200d_ma", "breadth", SIGNAL_DIR / "signal_bm_etf_above_200d_ma.csv", None, "alpha_or_offense_gate"),
    ("bm_etf_positive_13w_mom", "breadth", SIGNAL_DIR / "signal_bm_etf_positive_13w_mom.csv", None, "alpha_or_offense_gate"),
    ("bm_etf_positive_26w_mom", "breadth", SIGNAL_DIR / "signal_bm_etf_positive_26w_mom.csv", None, "alpha_or_offense_gate"),
    ("bm_risk_on_participation", "breadth", SIGNAL_DIR / "signal_bm_risk_on_participation.csv", None, "offense_gate"),
    ("bm_sector_above_50d_ma", "sector_breadth", SIGNAL_DIR / "signal_bm_sector_above_50d_ma.csv", None, "offense_gate"),
    ("bm_sector_above_200d_ma", "sector_breadth", SIGNAL_DIR / "signal_bm_sector_above_200d_ma.csv", None, "offense_gate"),
    ("bm_sector_positive_13w_mom", "sector_breadth", SIGNAL_DIR / "signal_bm_sector_positive_13w_mom.csv", None, "offense_gate"),
    ("bm_sector_positive_26w_mom", "sector_breadth", SIGNAL_DIR / "signal_bm_sector_positive_26w_mom.csv", None, "offense_gate"),
    ("r2_credit_spread__calm_trend_only", "gated_macro", SIGNAL_DIR / "signal_r2_credit_spread.csv", "gate_calm_trend_only", "macro_gate"),
    ("r2_vix_term_structure__calm_trend_only", "gated_macro", SIGNAL_DIR / "signal_r2_vix_term_structure.csv", "gate_calm_trend_only", "macro_gate"),
    ("r2_vix_term_structure__no_stressed_panic", "gated_macro", SIGNAL_DIR / "signal_r2_vix_term_structure.csv", "gate_no_stressed_panic", "stress_filter"),
    ("r2_credit_spread__vix_below_past_median", "gated_macro", SIGNAL_DIR / "signal_r2_credit_spread.csv", "gate_vix_below_past_median", "macro_gate"),
    ("r2_financial_conditions__recovery_only", "gated_macro", SIGNAL_DIR / "signal_r2_financial_conditions.csv", "gate_recovery_only", "macro_gate"),
    ("r2_commodity_regime__recovery_only", "gated_macro", SIGNAL_DIR / "signal_r2_commodity_regime.csv", "gate_recovery_only", "macro_gate"),
    ("bm_dollar_strength_4w", "dollar_strength", SIGNAL_DIR / "signal_bm_dollar_strength_4w.csv", None, "risk_filter"),
    ("bm_dollar_strength_blended", "dollar_strength", SIGNAL_DIR / "signal_bm_dollar_strength_blended.csv", None, "risk_filter"),
    ("bm_dollar_strength_13w", "dollar_strength", SIGNAL_DIR / "signal_bm_dollar_strength_13w.csv", None, "risk_filter"),
    ("bm_quality_breadth_confirmation", "signal_quality", SIGNAL_DIR / "signal_bm_quality_breadth_confirmation.csv", None, "offense_gate"),
    ("bm_quality_signal_agreement", "signal_quality", SIGNAL_DIR / "signal_bm_quality_signal_agreement.csv", None, "meta_gate"),
    ("bm_quality_signal_dispersion", "signal_quality", SIGNAL_DIR / "signal_bm_quality_signal_dispersion.csv", None, "chop_filter"),
    ("bm_quality_risk_on_confirmation__no_stressed_panic", "signal_quality", SIGNAL_DIR / "signal_bm_quality_risk_on_confirmation.csv", "gate_no_stressed_panic", "offense_gate"),
]

HOLDOUTS = {
    "2016_plus": (pd.Timestamp("2016-01-01"), None),
    "2020_plus": (pd.Timestamp("2020-01-01"), None),
    "2022_bear_rate_shock": (pd.Timestamp("2022-01-01"), pd.Timestamp("2022-12-31")),
    "2023_plus": (pd.Timestamp("2023-01-01"), None),
}

SUBPERIODS = {
    "2005_2009": (pd.Timestamp("2005-01-01"), pd.Timestamp("2009-12-31")),
    "2010_2015": (pd.Timestamp("2010-01-01"), pd.Timestamp("2015-12-31")),
    "2016_2019": (pd.Timestamp("2016-01-01"), pd.Timestamp("2019-12-31")),
    "2020_2022": (pd.Timestamp("2020-01-01"), pd.Timestamp("2022-12-31")),
    "2023_latest": (pd.Timestamp("2023-01-01"), None),
}


def fast_ic_by_date(panel: pd.DataFrame, prices: pd.DataFrame, horizon: int, min_assets: int = 5) -> pd.DataFrame:
    if panel.empty or prices.empty:
        return pd.DataFrame(columns=["Date", "ic", "n_assets"])
    sig = panel.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last")
    numeric_prices = prices.apply(pd.to_numeric, errors="coerce")
    fwd = numeric_prices.shift(-horizon) / numeric_prices - 1.0
    common_dates = sig.index.intersection(fwd.index)
    common_cols = [col for col in sig.columns if col in fwd.columns]
    if len(common_dates) == 0 or len(common_cols) < min_assets:
        return pd.DataFrame(columns=["Date", "ic", "n_assets"])
    x = sig.loc[common_dates, common_cols]
    y = fwd.loc[common_dates, common_cols]
    valid = x.notna() & y.notna()
    n = valid.sum(axis=1)
    xr = x.rank(axis=1, method="average").where(valid)
    yr = y.rank(axis=1, method="average").where(valid)
    xc = xr.sub(xr.mean(axis=1, skipna=True), axis=0)
    yc = yr.sub(yr.mean(axis=1, skipna=True), axis=0)
    denom = np.sqrt(xc.pow(2).sum(axis=1, skipna=True) * yc.pow(2).sum(axis=1, skipna=True))
    ic = (xc * yc).sum(axis=1, skipna=True) / denom.replace(0, np.nan)
    out = pd.DataFrame({"Date": common_dates, "ic": ic.to_numpy(), "n_assets": n.to_numpy()})
    return out[(out["n_assets"] >= min_assets) & out["ic"].notna()]


def filter_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> pd.DataFrame:
    out = df[df["Date"] >= start]
    if end is not None:
        out = out[out["Date"] <= end]
    return out


def flatten_panel(panel: pd.DataFrame) -> pd.Series:
    if panel.empty:
        return pd.Series(dtype=float)
    return panel.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last").stack()


def panel_corr(a: pd.DataFrame, b: pd.DataFrame, min_obs: int = 100) -> float:
    aligned = pd.concat([flatten_panel(a).rename("a"), flatten_panel(b).rename("b")], axis=1).dropna()
    if len(aligned) < min_obs or aligned["a"].nunique() < 2 or aligned["b"].nunique() < 2:
        return np.nan
    return float(aligned["a"].corr(aligned["b"], method="spearman"))


def weekly_cross_signal_corr(candidate: pd.DataFrame, other: pd.DataFrame, min_assets: int = 5) -> pd.DataFrame:
    a = candidate.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last")
    b = other.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last")
    dates = a.index.intersection(b.index)
    cols = [col for col in a.columns if col in b.columns]
    rows: list[dict] = []
    for date in dates:
        aligned = pd.concat([a.loc[date, cols].rename("a"), b.loc[date, cols].rename("b")], axis=1).dropna()
        if len(aligned) < min_assets or aligned["a"].nunique() < 2 or aligned["b"].nunique() < 2:
            continue
        rows.append({"Date": date, "corr": float(aligned["a"].corr(aligned["b"], method="spearman"))})
    return pd.DataFrame(rows)


def load_selected_panels(warnings: list[str]) -> dict[str, dict]:
    gates = load_gate_frame(warnings)
    panels: dict[str, dict] = {}
    for name, category, path, gate_col, intended_use in SELECTED_CANDIDATES:
        if not path.exists():
            warnings.append(f"Missing selected candidate file: {path}")
            continue
        panel = load_candidate_signal_panel(path, warnings)
        if panel.empty:
            warnings.append(f"Selected candidate panel empty after load: {name}")
            continue
        if gate_col:
            if gates.empty or gate_col not in gates.columns:
                warnings.append(f"Gate {gate_col} unavailable for {name}; candidate skipped.")
                continue
            panel = apply_gate(panel, gates, gate_col, name)
        else:
            panel = panel.copy()
            panel["signal_name"] = name
        panels[name] = {
            "panel": panel[["Date", "Ticker", "signal_name", "signal_value_tradable"]],
            "category": category,
            "gate": gate_col.replace("gate_", "") if gate_col else "none",
            "intended_use": intended_use,
        }
    return panels


def summarize_candidate(name: str, info: dict, prices: pd.DataFrame, states: pd.DataFrame, existing: dict[str, pd.DataFrame], selected: dict[str, dict]) -> tuple[dict, list[dict]]:
    panel = info["panel"]
    state_map = states.set_index("Date")["market_state"] if not states.empty else pd.Series(dtype=object)
    row: dict = {
        "signal_name": name,
        "category": info["category"],
        "gate": info["gate"],
        "intended_use": info["intended_use"],
        "research_only": True,
    }
    state_rows: list[dict] = []
    horizon_full_ics: list[float] = []
    horizon_hit_rates: list[float] = []
    horizon_n_dates: list[int] = []
    horizon_tstats: list[float] = []
    all_ic_by_horizon: dict[int, pd.DataFrame] = {}
    for horizon in HORIZONS:
        ic = fast_ic_by_date(panel, prices, horizon)
        all_ic_by_horizon[horizon] = ic
        full = summarize_ic(ic)
        row[f"full_ic_{horizon}w"] = full["mean_ic"]
        row[f"full_tstat_{horizon}w"] = full["ic_tstat_nw"]
        row[f"full_hit_rate_{horizon}w"] = full["hit_rate"]
        row[f"full_n_{horizon}w"] = full["n_dates"]
        horizon_full_ics.append(full["mean_ic"])
        horizon_hit_rates.append(full["hit_rate"])
        horizon_n_dates.append(full["n_dates"])
        horizon_tstats.append(full["ic_tstat_nw"])

        for label, (start, end) in HOLDOUTS.items():
            summary = summarize_ic(filter_window(ic, start, end)) if not ic.empty else summarize_ic(ic)
            row[f"{label}_ic_{horizon}w"] = summary["mean_ic"]
            row[f"{label}_n_{horizon}w"] = summary["n_dates"]

        for label, (start, end) in SUBPERIODS.items():
            summary = summarize_ic(filter_window(ic, start, end)) if not ic.empty else summarize_ic(ic)
            row[f"{label}_ic_{horizon}w"] = summary["mean_ic"]

        if not ic.empty:
            tmp = ic.copy()
            tmp["market_state"] = tmp["Date"].map(state_map)
            for state, group in tmp.dropna(subset=["market_state"]).groupby("market_state"):
                s = summarize_ic(group)
                state_rows.append(
                    {
                        "signal_name": name,
                        "category": info["category"],
                        "market_state": state,
                        "horizon_weeks": horizon,
                        "mean_ic": s["mean_ic"],
                        "ic_tstat_nw": s["ic_tstat_nw"],
                        "hit_rate": s["hit_rate"],
                        "n_dates": s["n_dates"],
                        "mean_coverage": s["mean_coverage"],
                        "warning": "small sample" if s["n_dates"] < 30 else "",
                    }
                )

    row["avg_full_ic"] = float(pd.Series(horizon_full_ics).mean())
    row["avg_full_tstat"] = float(pd.Series(horizon_tstats).mean())
    row["avg_full_hit_rate"] = float(pd.Series(horizon_hit_rates).mean())
    row["min_full_n"] = int(pd.Series(horizon_n_dates).min()) if horizon_n_dates else 0
    for label in HOLDOUTS:
        values = [row.get(f"{label}_ic_{h}w", np.nan) for h in HORIZONS]
        ns = [row.get(f"{label}_n_{h}w", 0) for h in HORIZONS]
        row[f"{label}_avg_ic"] = float(pd.Series(values).mean())
        row[f"{label}_min_n"] = int(pd.Series(ns).min())
    for label in SUBPERIODS:
        values = [row.get(f"{label}_ic_{h}w", np.nan) for h in HORIZONS]
        row[f"{label}_avg_ic"] = float(pd.Series(values).mean())
    subperiod_avg = [row[f"{label}_avg_ic"] for label in SUBPERIODS]
    row["subperiod_positive_share"] = float((pd.Series(subperiod_avg) > 0).mean())
    row["subperiod_min_ic"] = float(pd.Series(subperiod_avg).min())

    state_df = pd.DataFrame(state_rows)
    if not state_df.empty:
        for state in ["calm_trend", "neutral_mixed", "recovery_fragile", "recovery_confirmed", "stressed_panic"]:
            state_slice = state_df[state_df["market_state"].eq(state)]
            row[f"{state}_avg_ic"] = float(state_slice["mean_ic"].mean()) if not state_slice.empty else np.nan
            row[f"{state}_min_n"] = int(state_slice["n_dates"].min()) if not state_slice.empty else 0

    existing_corrs = []
    for other_name, other_panel in existing.items():
        corr = panel_corr(panel, other_panel)
        if pd.notna(corr):
            existing_corrs.append((other_name, corr, abs(corr)))
    if existing_corrs:
        existing_corrs.sort(key=lambda item: item[2], reverse=True)
        row["max_abs_redundancy_existing"] = existing_corrs[0][2]
        row["most_redundant_existing_signal"] = existing_corrs[0][0]
        row["signed_redundancy_existing"] = existing_corrs[0][1]
        weekly_corr = weekly_cross_signal_corr(panel, existing[existing_corrs[0][0]])
        if not weekly_corr.empty:
            rolling = weekly_corr.set_index("Date")["corr"].rolling(104, min_periods=52).mean().dropna()
            row["rolling_104w_redundancy_median"] = float(rolling.abs().median()) if not rolling.empty else np.nan
            row["rolling_104w_redundancy_max"] = float(rolling.abs().max()) if not rolling.empty else np.nan
            row["rolling_104w_redundancy_recent"] = float(abs(rolling.iloc[-1])) if not rolling.empty else np.nan
    else:
        row["max_abs_redundancy_existing"] = np.nan
        row["most_redundant_existing_signal"] = ""

    selected_corrs = []
    for other_name, other_info in selected.items():
        if other_name == name:
            continue
        corr = panel_corr(panel, other_info["panel"])
        if pd.notna(corr):
            selected_corrs.append((other_name, corr, abs(corr)))
    if selected_corrs:
        selected_corrs.sort(key=lambda item: item[2], reverse=True)
        row["max_abs_redundancy_selected"] = selected_corrs[0][2]
        row["most_redundant_selected_signal"] = selected_corrs[0][0]
        row["signed_redundancy_selected"] = selected_corrs[0][1]

    flags: list[str] = []
    if row.get("stressed_panic_avg_ic", np.nan) < -0.03:
        flags.append("stressed_panic_ic_below_-0.03")
    if row.get("2022_bear_rate_shock_avg_ic", np.nan) < 0:
        flags.append("2022_ic_negative")
    if row.get("2020_plus_avg_ic", np.nan) < 0:
        flags.append("2020_holdout_ic_negative")
    if row.get("2016_plus_avg_ic", np.nan) < 0:
        flags.append("2016_holdout_ic_negative")
    if row.get("max_abs_redundancy_existing", 0) > 0.60:
        flags.append("redundancy_gt_0.60_existing")
    if row.get("min_full_n", 0) < 156 or row.get("2020_plus_min_n", 0) < 52:
        flags.append("sample_size_too_small")
    if row.get("subperiod_positive_share", 0) < 0.60:
        flags.append("unstable_subperiods")
    row["stress_safety_flags"] = "; ".join(flags)

    if "sample_size_too_small" in flags:
        row["verdict"] = "research-only"
        row["verdict_reason"] = "Insufficient sample for a robust B6 decision."
    elif any(flag in flags for flag in ["stressed_panic_ic_below_-0.03", "2020_holdout_ic_negative", "2016_holdout_ic_negative"]):
        row["verdict"] = "reject" if row["avg_full_ic"] <= 0 else "research-only"
        row["verdict_reason"] = "Failed stress/holdout safety flags: " + row["stress_safety_flags"]
    elif row.get("max_abs_redundancy_existing", 0) > 0.60:
        row["verdict"] = "candidate-pass-but-redundant"
        row["verdict_reason"] = "Passed core B6 checks but is redundant with existing strong signals."
    elif info["category"] in {"gated_macro"} or "gate" in info["intended_use"] or "filter" in info["intended_use"]:
        row["verdict"] = "promising-if-gated"
        row["verdict_reason"] = "Passed B6 checks as a gated/filter candidate, not standalone alpha."
    else:
        row["verdict"] = "candidate-pass"
        row["verdict_reason"] = "Passed B6 full/holdout/state/stress/redundancy checks."
    return row, state_rows


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    existing = load_strong_existing_panels(warnings)
    selected = load_selected_panels(warnings)
    if prices.empty:
        warnings.append("weekly_prices.csv unavailable; B6 validation cannot run.")
    rows: list[dict] = []
    state_rows: list[dict] = []
    if not prices.empty:
        for name, info in selected.items():
            row, states_part = summarize_candidate(name, info, prices, states, existing, selected)
            rows.append(row)
            state_rows.extend(states_part)

    results = pd.DataFrame(rows)
    detail = pd.DataFrame(state_rows)
    out = SIGNAL_DIR / "b6_unified_signal_validation.csv"
    detail_out = SIGNAL_DIR / "b6_state_validation_detail.csv"
    ensure_parent(out)
    results.to_csv(out, index=False)
    detail.to_csv(detail_out, index=False)

    report_path = DOCS_RESEARCH_DIR / "b6_unified_signal_validation_report.md"
    report = [
        "# B6 Unified Signal Validation Report",
        "",
        "Research-only unified validation of selected breadth, gated macro, dollar-strength, and signal-quality candidates. All panels use one-week-lagged tradable signals; gated signals use one-week-lagged gates.",
        "",
        f"- Validation CSV: `{out}`",
        f"- State detail CSV: `{detail_out}`",
        f"- Candidates validated: {len(results)}",
        "",
        "## Verdict Summary",
        "",
        markdown_table(results["verdict"].value_counts().rename_axis("verdict").reset_index(name="count") if not results.empty else results),
        "",
        "## Top Candidates By 2020+ Holdout IC",
        "",
        markdown_table(
            results.sort_values("2020_plus_avg_ic", ascending=False)[
                [
                    "signal_name",
                    "category",
                    "verdict",
                    "avg_full_ic",
                    "2016_plus_avg_ic",
                    "2020_plus_avg_ic",
                    "2022_bear_rate_shock_avg_ic",
                    "calm_trend_avg_ic",
                    "stressed_panic_avg_ic",
                    "max_abs_redundancy_existing",
                    "stress_safety_flags",
                ]
            ],
            max_rows=20,
        )
        if not results.empty
        else "_No rows._",
        "",
        "## Redundancy Watch",
        "",
        markdown_table(
            results.sort_values("max_abs_redundancy_existing", ascending=False)[
                [
                    "signal_name",
                    "verdict",
                    "max_abs_redundancy_existing",
                    "most_redundant_existing_signal",
                    "rolling_104w_redundancy_median",
                    "rolling_104w_redundancy_max",
                    "rolling_104w_redundancy_recent",
                ]
            ],
            max_rows=20,
        )
        if not results.empty
        else "_No rows._",
        "",
        "## State Detail Highlights",
        "",
        markdown_table(
            detail.sort_values("mean_ic", ascending=False)[["signal_name", "market_state", "horizon_weeks", "mean_ic", "ic_tstat_nw", "n_dates"]],
            max_rows=20,
        )
        if not detail.empty
        else "_No state rows._",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out} rows={len(results)}")
    print(f"Wrote {detail_out} rows={len(detail)}")
    print(f"Wrote {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
