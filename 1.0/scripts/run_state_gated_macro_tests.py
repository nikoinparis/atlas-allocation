"""Research-only state-gated macro/VIX/credit signal tests.

This script does not alter production logic. It tests whether simple, lagged
activation gates can preserve useful macro information while reducing
stressed_panic damage observed in earlier R2 validation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HOLDOUT_START,
    HORIZONS,
    HUB_DIR,
    SIGNAL_DIR,
    ensure_parent,
    load_candidate_signal_panel,
    load_market_states,
    load_strong_existing_panels,
    load_weekly_prices,
    markdown_table,
    read_csv_safe,
    summarize_ic,
)


BASE_SIGNALS = {
    "r2_yield_curve": SIGNAL_DIR / "signal_r2_yield_curve.csv",
    "r2_credit_spread": SIGNAL_DIR / "signal_r2_credit_spread.csv",
    "r2_financial_conditions": SIGNAL_DIR / "signal_r2_financial_conditions.csv",
    "r2_vix_term_structure": SIGNAL_DIR / "signal_r2_vix_term_structure.csv",
    "r2_commodity_regime": SIGNAL_DIR / "signal_r2_commodity_regime.csv",
    "r2_cross_asset_divergence": SIGNAL_DIR / "signal_r2_cross_asset_divergence.csv",
    "r2_dollar_strength": SIGNAL_DIR / "signal_r2_dollar_strength.csv",
}


def load_gate_frame(warnings: list[str]) -> pd.DataFrame:
    states = read_csv_safe(HUB_DIR.parent / "04_layer2b_risk_regime_engine" / "market_state_history.csv", warnings)
    if states.empty or "Date" not in states.columns:
        states = load_market_states(warnings)
    if states.empty:
        return pd.DataFrame(columns=["Date"])
    states = states.copy()
    states["Date"] = pd.to_datetime(states["Date"], errors="coerce")
    states = states.dropna(subset=["Date"]).sort_values("Date")

    vix = read_csv_safe(HUB_DIR / "vix_term_structure.csv", warnings)
    if not vix.empty and {"Date", "VIX"}.issubset(vix.columns):
        vix = vix[["Date", "VIX"]].copy()
        vix["Date"] = pd.to_datetime(vix["Date"], errors="coerce")
        vix["VIX"] = pd.to_numeric(vix["VIX"], errors="coerce")
        states = states.merge(vix, on="Date", how="left")
        past_median = states["VIX"].rolling(156, min_periods=52).median().shift(1)
        states["vix_below_past_median"] = (states["VIX"] <= past_median).astype(float)
    else:
        warnings.append("vix_term_structure.csv lacks Date/VIX; VIX threshold gate unavailable.")
        states["vix_below_past_median"] = np.nan

    if "breadth_13w_mom" in states.columns:
        states["breadth_confirms"] = (pd.to_numeric(states["breadth_13w_mom"], errors="coerce") > 0).astype(float)
    else:
        warnings.append("market_state_history.csv lacks breadth_13w_mom; breadth confirmation gate unavailable.")
        states["breadth_confirms"] = np.nan

    state = states.get("market_state", pd.Series(index=states.index, dtype=object)).astype(str)
    states["gate_unconditional"] = 1.0
    states["gate_calm_trend_only"] = state.eq("calm_trend").astype(float)
    states["gate_no_stressed_panic"] = (~state.eq("stressed_panic")).astype(float)
    states["gate_recovery_only"] = state.isin(["recovery_fragile", "recovery_confirmed"]).astype(float)
    states["gate_vix_below_past_median"] = states["vix_below_past_median"]
    states["gate_breadth_confirms"] = states["breadth_confirms"]
    states["gate_calm_or_breadth_no_stress"] = (
        (state.eq("calm_trend") | states["breadth_confirms"].eq(1.0)) & ~state.eq("stressed_panic")
    ).astype(float)

    gate_cols = [c for c in states.columns if c.startswith("gate_")]
    states[gate_cols] = states[gate_cols].shift(1)
    return states[["Date", *gate_cols]]


def apply_gate(panel: pd.DataFrame, gate_frame: pd.DataFrame, gate_col: str, gated_name: str) -> pd.DataFrame:
    out = panel.merge(gate_frame[["Date", gate_col]], on="Date", how="left")
    out["signal_name"] = gated_name
    out["gate_name"] = gate_col.replace("gate_", "")
    out["gate_value_lagged"] = pd.to_numeric(out[gate_col], errors="coerce")
    if gate_col == "gate_unconditional":
        out["signal_value_tradable"] = pd.to_numeric(out["signal_value_tradable"], errors="coerce")
    else:
        out["signal_value_tradable"] = pd.to_numeric(out["signal_value_tradable"], errors="coerce") * out["gate_value_lagged"].fillna(0.0)
    return out[["Date", "Ticker", "signal_name", "signal_value_tradable", "gate_name", "gate_value_lagged"]]


def prepare_strong_stacks(strong_panels: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    stacks: dict[str, pd.Series] = {}
    for name, panel in strong_panels.items():
        if panel.empty:
            continue
        stacks[name] = panel.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last").stack()
    return stacks


def fast_redundancy(candidate: pd.DataFrame, strong_stacks: dict[str, pd.Series], min_obs: int = 100) -> tuple[float, str]:
    if candidate.empty or not strong_stacks:
        return np.nan, ""
    cand = candidate.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last").stack()
    best_abs = np.nan
    best_name = ""
    for name, other in strong_stacks.items():
        aligned = pd.concat([cand.rename("candidate"), other.rename("existing")], axis=1).dropna()
        if len(aligned) < min_obs:
            continue
        corr = aligned["candidate"].corr(aligned["existing"], method="spearman")
        if pd.notna(corr) and (pd.isna(best_abs) or abs(corr) > best_abs):
            best_abs = abs(float(corr))
            best_name = name
    return best_abs, best_name


def fast_cross_sectional_ic_by_date(panel: pd.DataFrame, prices: pd.DataFrame, horizon: int, min_assets: int = 5) -> pd.DataFrame:
    if panel.empty or prices.empty:
        return pd.DataFrame(columns=["Date", "ic", "n_assets"])
    sig = panel.pivot_table(index="Date", columns="Ticker", values="signal_value_tradable", aggfunc="last")
    fwd = prices.apply(pd.to_numeric, errors="coerce").shift(-horizon) / prices.apply(pd.to_numeric, errors="coerce") - 1.0
    common_dates = sig.index.intersection(fwd.index)
    common_cols = [c for c in sig.columns if c in fwd.columns]
    if len(common_dates) == 0 or len(common_cols) < min_assets:
        return pd.DataFrame(columns=["Date", "ic", "n_assets"])
    x = sig.loc[common_dates, common_cols]
    y = fwd.loc[common_dates, common_cols]
    valid = x.notna() & y.notna()
    n = valid.sum(axis=1)
    xr = x.rank(axis=1, method="average")
    yr = y.rank(axis=1, method="average")
    xr = xr.where(valid)
    yr = yr.where(valid)
    xc = xr.sub(xr.mean(axis=1, skipna=True), axis=0)
    yc = yr.sub(yr.mean(axis=1, skipna=True), axis=0)
    numerator = (xc * yc).sum(axis=1, skipna=True)
    denominator = np.sqrt((xc.pow(2).sum(axis=1, skipna=True)) * (yc.pow(2).sum(axis=1, skipna=True)))
    ic = numerator / denominator.replace(0, np.nan)
    out = pd.DataFrame({"Date": common_dates, "ic": ic.to_numpy(), "n_assets": n.to_numpy()})
    out = out[(out["n_assets"] >= min_assets) & out["ic"].notna()]
    return out


def combined_evaluation(panel: pd.DataFrame, prices: pd.DataFrame, states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute horizon IC once, then reuse it for full, holdout, and state summaries."""
    signal_name = panel["signal_name"].dropna().iloc[0] if not panel.empty else "unknown"
    state_map = states.set_index("Date")["market_state"] if not states.empty else pd.Series(dtype=object)
    eval_rows: list[dict] = []
    state_rows: list[dict] = []
    for horizon in HORIZONS:
        ic_dates = fast_cross_sectional_ic_by_date(panel, prices, horizon, min_assets=5)
        full = summarize_ic(ic_dates)
        holdout = summarize_ic(ic_dates[ic_dates["Date"] >= HOLDOUT_START]) if not ic_dates.empty else summarize_ic(ic_dates)
        eval_rows.append(
            {
                "signal_name": signal_name,
                "horizon_weeks": horizon,
                **{f"full_{key}": value for key, value in full.items()},
                **{f"holdout_{key}": value for key, value in holdout.items()},
            }
        )
        if ic_dates.empty:
            state_rows.append(
                {
                    "signal_name": signal_name,
                    "market_state": "ALL",
                    "horizon_weeks": horizon,
                    "mean_ic": np.nan,
                    "ic_tstat_nw": np.nan,
                    "hit_rate": np.nan,
                    "n_dates": 0,
                    "mean_coverage": np.nan,
                    "warning": "No valid cross-sectional IC observations.",
                }
            )
            continue
        ic_dates = ic_dates.copy()
        ic_dates["market_state"] = ic_dates["Date"].map(state_map)
        for state, group in ic_dates.dropna(subset=["market_state"]).groupby("market_state"):
            summary = summarize_ic(group)
            state_rows.append(
                {
                    "signal_name": signal_name,
                    "market_state": state,
                    "horizon_weeks": horizon,
                    "mean_ic": summary["mean_ic"],
                    "ic_tstat_nw": summary["ic_tstat_nw"],
                    "hit_rate": summary["hit_rate"],
                    "n_dates": summary["n_dates"],
                    "mean_coverage": summary["mean_coverage"],
                    "warning": "Small state sample; treat as directional only." if summary["n_dates"] < 30 else "",
                }
            )
    return pd.DataFrame(eval_rows), pd.DataFrame(state_rows)


def stress_mean_from_state_rows(state_rows: pd.DataFrame) -> float:
    if state_rows.empty:
        return np.nan
    stress = state_rows[state_rows["market_state"].eq("stressed_panic")]
    return float(stress["mean_ic"].mean()) if not stress.empty else np.nan


def verdict(row: dict) -> tuple[str, str]:
    reasons: list[str] = []
    if row["min_full_n_dates"] < 156 or row["min_holdout_n_dates"] < 52:
        reasons.append("insufficient observations")
    if pd.isna(row["avg_full_mean_ic"]) or row["avg_full_mean_ic"] <= 0:
        reasons.append("full IC not positive")
    if pd.isna(row["avg_holdout_mean_ic"]) or row["avg_holdout_mean_ic"] <= 0:
        reasons.append("holdout IC not positive")
    if pd.notna(row["stressed_panic_mean_ic"]) and row["stressed_panic_mean_ic"] < -0.02:
        reasons.append("stressed_panic damage remains")
    if row["gate_name"] != "unconditional" and row.get("stressed_panic_improvement", 0.0) > 0.01 and row.get("calm_trend_mean_ic", 0.0) > 0:
        if row["avg_holdout_mean_ic"] > 0:
            return "promising-if-gated", "Gate improved stressed_panic behavior while retaining positive holdout/calm evidence."
    if not reasons:
        return "candidate-pass", "Positive full/holdout IC and no large stressed_panic damage under this gate."
    if "stressed_panic damage remains" in reasons and row.get("calm_trend_mean_ic", np.nan) > 0.02:
        return "promising-if-gated", "; ".join(reasons)
    if "full IC not positive" in reasons and "holdout IC not positive" in reasons:
        return "reject", "; ".join(reasons)
    return "research-only", "; ".join(reasons)


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    strong_panels = load_strong_existing_panels(warnings)
    strong_stacks = prepare_strong_stacks(strong_panels)
    gates = load_gate_frame(warnings)
    macro_weekly = read_csv_safe(HUB_DIR / "macro_weekly.csv", warnings)
    if macro_weekly.empty:
        warnings.append("macro_weekly.csv missing or unreadable; B2 used existing R2 macro/VIX/credit signal panels only.")
    else:
        macro_cols = [col for col in macro_weekly.columns if col != "Date"]
        if not macro_cols:
            warnings.append("macro_weekly.csv contains only Date; no raw macro series were available to rebuild macro signals. B2 used existing R2 macro/VIX/credit signal panels only.")

    rows: list[dict] = []
    state_detail: list[pd.DataFrame] = []
    if prices.empty:
        warnings.append("weekly_prices.csv unavailable; state-gated macro tests skipped.")
    if gates.empty:
        warnings.append("No gate frame available; state-gated macro tests skipped.")

    for base_name, path in BASE_SIGNALS.items():
        if prices.empty or gates.empty:
            rows.append({"base_signal": base_name, "gate_name": "skipped", "verdict": "skipped", "verdict_reason": "Missing prices or gate frame."})
            continue
        if not path.exists():
            rows.append({"base_signal": base_name, "gate_name": "skipped", "verdict": "skipped", "verdict_reason": f"Missing base signal file: {path}"})
            warnings.append(f"Missing base signal file: {path}")
            continue
        base_panel = load_candidate_signal_panel(path, warnings)
        if base_panel.empty:
            rows.append({"base_signal": base_name, "gate_name": "skipped", "verdict": "skipped", "verdict_reason": "Base panel empty after loading."})
            continue

        unconditional_panel = apply_gate(base_panel, gates, "gate_unconditional", f"{base_name}__unconditional")
        unconditional_eval, unconditional_state = combined_evaluation(unconditional_panel, prices, states)
        base_stress = stress_mean_from_state_rows(unconditional_state)

        for gate_col in [c for c in gates.columns if c.startswith("gate_")]:
            gate_name = gate_col.replace("gate_", "")
            gated_name = f"{base_name}__{gate_name}"
            panel = apply_gate(base_panel, gates, gate_col, gated_name)
            if gate_col == "gate_unconditional":
                eval_rows, state_rows = unconditional_eval, unconditional_state.copy()
                state_rows["signal_name"] = gated_name
            else:
                eval_rows, state_rows = combined_evaluation(panel, prices, states)
            if not state_rows.empty:
                state_rows["base_signal"] = base_name
                state_rows["gate_name"] = gate_name
                state_detail.append(state_rows)
            max_red, red_name = fast_redundancy(panel, strong_stacks)
            calm = state_rows[state_rows["market_state"].eq("calm_trend")] if not state_rows.empty else pd.DataFrame()
            stress = state_rows[state_rows["market_state"].eq("stressed_panic")] if not state_rows.empty else pd.DataFrame()
            stress_ic = float(stress["mean_ic"].mean()) if not stress.empty else np.nan
            row = {
                "base_signal": base_name,
                "gated_signal_name": gated_name,
                "gate_name": gate_name,
                "avg_full_mean_ic": float(eval_rows["full_mean_ic"].mean()) if not eval_rows.empty else np.nan,
                "avg_holdout_mean_ic": float(eval_rows["holdout_mean_ic"].mean()) if not eval_rows.empty else np.nan,
                "avg_full_nw_tstat": float(eval_rows["full_ic_tstat_nw"].mean()) if not eval_rows.empty else np.nan,
                "avg_holdout_nw_tstat": float(eval_rows["holdout_ic_tstat_nw"].mean()) if not eval_rows.empty else np.nan,
                "min_full_n_dates": int(eval_rows["full_n_dates"].min()) if not eval_rows.empty else 0,
                "min_holdout_n_dates": int(eval_rows["holdout_n_dates"].min()) if not eval_rows.empty else 0,
                "calm_trend_mean_ic": float(calm["mean_ic"].mean()) if not calm.empty else np.nan,
                "stressed_panic_mean_ic": stress_ic,
                "base_unconditional_stressed_panic_mean_ic": base_stress,
                "stressed_panic_improvement": stress_ic - base_stress if pd.notna(stress_ic) and pd.notna(base_stress) else np.nan,
                "max_redundancy_vs_strong": max_red,
                "most_redundant_existing_signal": red_name,
                "gate_active_share": float(panel["gate_value_lagged"].fillna(0.0).mean()),
                "research_only": True,
            }
            row["verdict"], row["verdict_reason"] = verdict(row)
            rows.append(row)

    results = pd.DataFrame(rows)
    out = SIGNAL_DIR / "state_gated_macro_results.csv"
    ensure_parent(out)
    results.to_csv(out, index=False)

    detail = pd.concat(state_detail, ignore_index=True) if state_detail else pd.DataFrame()
    detail_out = SIGNAL_DIR / "state_gated_macro_state_detail.csv"
    detail.to_csv(detail_out, index=False)

    report_path = DOCS_RESEARCH_DIR / "state_gated_macro_report.md"
    report = [
        "# State-Gated Macro Report",
        "",
        "Research-only B2 tests of simple one-week-lagged activation gates on existing R2 macro/VIX/credit signal panels.",
        "",
        f"- Results CSV: `{out}`",
        f"- State detail CSV: `{detail_out}`",
        f"- Rows tested: {len(results)}",
        "",
        "## Best Gated Rows",
        "",
        markdown_table(
            results.sort_values(["verdict", "avg_holdout_mean_ic"], ascending=[True, False])[
                [
                    "base_signal",
                    "gate_name",
                    "verdict",
                    "avg_full_mean_ic",
                    "avg_holdout_mean_ic",
                    "calm_trend_mean_ic",
                    "stressed_panic_mean_ic",
                    "stressed_panic_improvement",
                    "gate_active_share",
                    "verdict_reason",
                ]
            ],
            max_rows=20,
        )
        if not results.empty
        else "_No rows._",
        "",
        "## Gates That Improved Stressed Panic Behavior",
        "",
        markdown_table(
            results.sort_values("stressed_panic_improvement", ascending=False)[
                [
                    "base_signal",
                    "gate_name",
                    "avg_holdout_mean_ic",
                    "calm_trend_mean_ic",
                    "stressed_panic_mean_ic",
                    "base_unconditional_stressed_panic_mean_ic",
                    "stressed_panic_improvement",
                    "verdict",
                ]
            ],
            max_rows=15,
        )
        if not results.empty
        else "_No rows._",
        "",
        "## Remaining Dangerous Rows",
        "",
        markdown_table(
            results.sort_values("stressed_panic_mean_ic")[
                [
                    "base_signal",
                    "gate_name",
                    "stressed_panic_mean_ic",
                    "avg_holdout_mean_ic",
                    "calm_trend_mean_ic",
                    "verdict",
                    "verdict_reason",
                ]
            ],
            max_rows=15,
        )
        if not results.empty
        else "_No rows._",
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
