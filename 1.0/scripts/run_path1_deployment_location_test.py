"""Path 1.3 deployment-location test.

Research-only. Uses saved GGG artifacts and allocator checkpoints to test small
bounded confidence injections at different approximate deployment locations.
No production Layer 3 artifacts are overwritten.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DOCS,
    GGG,
    PATH1_OUT,
    PRODUCTION_COST_BPS,
    apply_offense_multiplier,
    ensure_dirs,
    exposure_summary,
    load_checkpoint,
    load_market_quality_inputs,
    load_next_week_returns,
    load_returns,
    load_states,
    load_weights,
    md_table,
    metrics_from_path,
    normalize_to_cash,
    production_portfolio_path,
    read_csv,
    rel,
    state_summary,
    write_text,
    OFFENSE,
    DEFENSE,
    PATH3_OUT,
    DATA,
)


def quality_frame(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    inputs = load_market_quality_inputs(index, warnings)
    out = pd.DataFrame(index=index)
    out["etf_breadth"] = inputs[
        ["bm_etf_above_50d_ma", "bm_etf_above_200d_ma", "bm_etf_positive_13w_mom", "bm_etf_positive_26w_mom"]
    ].mean(axis=1)
    out["sector_breadth"] = inputs[
        ["bm_sector_above_50d_ma", "bm_sector_above_200d_ma", "bm_sector_positive_13w_mom", "bm_sector_positive_26w_mom"]
    ].mean(axis=1)
    out["risk_on"] = inputs["bm_risk_on_participation"]
    out["dollar_pressure"] = inputs["bm_dollar_strength_blended"]
    out["vix_pressure"] = 1.0 - inputs["r2_vix_term_structure"]
    out["credit_pressure"] = 1.0 - inputs["r2_credit_spread"]
    out["signal_dispersion"] = inputs["bm_quality_signal_dispersion"]
    out["participation_quality"] = (0.40 * out["etf_breadth"] + 0.35 * out["sector_breadth"] + 0.25 * out["risk_on"]).clip(0, 1)
    out["deterioration_score"] = (
        0.30 * (1.0 - out["etf_breadth"])
        + 0.20 * (1.0 - out["sector_breadth"])
        + 0.20 * out["dollar_pressure"]
        + 0.15 * out["vix_pressure"]
        + 0.10 * out["credit_pressure"]
        + 0.05 * out["signal_dispersion"]
    ).clip(0, 1)
    out["confidence"] = (0.65 * out["participation_quality"] + 0.35 * (1.0 - out["deterioration_score"])).clip(0, 1)
    for col in ["market_state", "transition_non_stress_prob", "transition_good_state_prob"]:
        if col in inputs.columns:
            out[col] = inputs[col]
    return out


def load_target_vol_diag(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    path = DATA / "research" / "phase_jjj1_constraint_drag_isolation" / "raw" / "target_vol_diagnostics_by_date.csv"
    df = read_csv(path, warnings)
    if df.empty:
        return pd.DataFrame(index=index)
    if "Date" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Date"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df.get("version_name", "").eq(GGG)].dropna(subset=["Date"]).set_index("Date").sort_index()
    return df.reindex(index)


def stage_exposure_table(base_weights: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    rows = []
    for stage in [
        "raw_hrp_sleeve_weights",
        "post_state_tilt_sleeve_weights",
        "post_layer3_expression_sleeve_weights",
        "post_overlay_pre_lookthrough_sleeve_weights",
        "final_sleeve_weights",
        "final_etf_weights",
    ]:
        df = load_checkpoint(GGG, stage, warnings)
        if df.empty:
            rows.append({"stage": stage, "rows": 0})
            continue
        if "final_etf" in stage:
            offense_cols = [c for c in df.columns if c in OFFENSE]
            defense_cols = [c for c in df.columns if c in DEFENSE]
            rows.append(
                {
                    "stage": stage,
                    "rows": len(df),
                    "avg_cash": float(df.get("BIL", pd.Series(0.0, index=df.index)).mean()),
                    "avg_offense": float(df[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan,
                    "avg_defense": float(df[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan,
                    "avg_total": float(df.sum(axis=1).mean()),
                }
            )
        else:
            offense_cols = [c for c in df.columns if "offense" in c or c in {"dual_momentum_topn", "composite_selective_signals"}]
            defense_cols = [c for c in df.columns if "defense" in c or c in {"cta_trend_long_only", "taa_10m_sma"}]
            rows.append(
                {
                    "stage": stage,
                    "rows": len(df),
                    "avg_cash": float(df.get("cash::BIL", pd.Series(0.0, index=df.index)).mean()),
                    "avg_offense": float(df[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan,
                    "avg_defense": float(df[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan,
                    "avg_total": float(df.sum(axis=1).mean()),
                }
            )
    return pd.DataFrame(rows)


def build_variant_weights(base: pd.DataFrame, q: pd.DataFrame, tv: pd.DataFrame, variant: str) -> pd.DataFrame:
    state = q.get("market_state", pd.Series("", index=base.index)).astype(str)
    confidence = q["confidence"].reindex(base.index).fillna(0.5)
    deterioration = q["deterioration_score"].reindex(base.index).fillna(0.5)
    participation = q["participation_quality"].reindex(base.index).fillna(0.5)
    stress = state.eq("stressed_panic")
    recovery = state.isin(["recovery_fragile", "recovery_confirmed"])
    calm_or_neutral = state.isin(["calm_trend", "neutral_mixed"])

    mult = pd.Series(1.0, index=base.index)
    pressure_mult = pd.Series(1.0, index=base.index)

    if variant == "post_hoc_weight_scaling":
        mult = (0.95 + 0.10 * confidence).clip(0.95, 1.05)
    elif variant == "pre_overlay_proxy":
        # Proxy: only allow confidence to matter when the overlay was not already
        # strongly binding. This approximates pre-overlay injection being absorbed
        # by later overlay rules.
        binding = pd.to_numeric(tv.get("regime_binding", pd.Series(0.0, index=base.index)), errors="coerce").fillna(0.0) > 0
        mult = pd.Series(1.0, index=base.index)
        mult.loc[~binding & (confidence < 0.40)] = 0.96
        mult.loc[~binding & (confidence > 0.75)] = 1.02
    elif variant == "sleeve_level_scaling_proxy":
        mult = pd.Series(1.0, index=base.index)
        mult.loc[(participation < 0.35) & ~stress] = 0.95
        mult.loc[(participation > 0.75) & calm_or_neutral] = 1.02
    elif variant == "regime_aware_scaling":
        mult.loc[calm_or_neutral & (confidence < 0.35)] = 0.95
        mult.loc[recovery & (deterioration > 0.70)] = 0.97
    elif variant == "offense_only_scaling":
        mult.loc[(deterioration > 0.65) & ~stress] = 0.95
    elif variant == "defense_preserving_scaling":
        mult.loc[(deterioration > 0.60) & calm_or_neutral] = 0.96
        mult.loc[recovery] = mult.loc[recovery].clip(lower=0.98)
    elif variant == "volatility_target_aware_scaling":
        target_binding = pd.to_numeric(tv.get("target_vol_binding", pd.Series(0.0, index=base.index)), errors="coerce").fillna(0.0) > 0
        mult.loc[(deterioration > 0.65) & ~stress & ~target_binding] = 0.95
        mult.loc[(confidence > 0.80) & calm_or_neutral & ~target_binding] = 1.02
    elif variant == "dollar_pressure_location_proxy":
        pressure_mult.loc[(q["dollar_pressure"] > 0.75) & ~stress] = 0.94
    else:
        raise ValueError(f"Unknown variant {variant}")

    mult.loc[stress] = 1.0
    return apply_offense_multiplier(base, mult.clip(0.94, 1.05), pressure_multiplier=pressure_mult)


def row_for_variant(name: str, path: pd.DataFrame, weights: pd.DataFrame, base_metrics: dict[str, float]) -> dict[str, float | str]:
    row: dict[str, float | str] = {"variant": name, **metrics_from_path(path), **exposure_summary(weights)}
    row["delta_sharpe_vs_exact_ggg"] = float(row["sharpe"] - base_metrics["sharpe"])
    row["delta_ann_return_vs_exact_ggg"] = float(row["ann_return"] - base_metrics["ann_return"])
    row["delta_max_drawdown_vs_exact_ggg"] = float(row["max_drawdown"] - base_metrics["max_drawdown"])
    row["delta_cvar_5_vs_exact_ggg"] = float(row["cvar_5"] - base_metrics["cvar_5"])
    row["delta_avg_turnover_vs_exact_ggg"] = float(row["avg_turnover"] - base_metrics["avg_turnover"])
    return row


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()

    base = load_weights(GGG, warnings)
    saved = load_returns(GGG, warnings)
    next_returns = load_next_week_returns(warnings)
    states = load_states(warnings)
    if base.empty or next_returns.empty:
        raise SystemExit("Required GGG weights or price-derived forward returns are missing.")

    q = quality_frame(base.index, warnings)
    tv = load_target_vol_diag(base.index, warnings)
    base_path = production_portfolio_path(base, next_returns, PRODUCTION_COST_BPS)
    base_metrics = metrics_from_path(base_path)

    variants = [
        "post_hoc_weight_scaling",
        "pre_overlay_proxy",
        "sleeve_level_scaling_proxy",
        "regime_aware_scaling",
        "offense_only_scaling",
        "defense_preserving_scaling",
        "volatility_target_aware_scaling",
        "dollar_pressure_location_proxy",
    ]
    rows = [row_for_variant("exact_ggg_reference", base_path, base, base_metrics)]
    state_rows = []
    for name in variants:
        vw = normalize_to_cash(build_variant_weights(base, q, tv, name))
        path = production_portfolio_path(vw, next_returns, PRODUCTION_COST_BPS)
        row = row_for_variant(name, path, vw, base_metrics)
        row["deployment_location"] = name.replace("_", " ")
        row["promising"] = bool(
            row["delta_sharpe_vs_exact_ggg"] >= -0.01
            and row["delta_max_drawdown_vs_exact_ggg"] >= -0.005
            and row["delta_cvar_5_vs_exact_ggg"] >= -0.0005
        )
        rows.append(row)
        if not states.empty:
            state_rows.append(state_summary(path, states, name))

    results = pd.DataFrame(rows)
    stage_table = stage_exposure_table(base, warnings)
    results.to_csv(PATH1_OUT / "path1_deployment_location_results.csv", index=False)
    stage_table.to_csv(PATH1_OUT / "path1_stage_exposure_diagnostics.csv", index=False)
    if state_rows:
        pd.concat(state_rows, ignore_index=True).to_csv(PATH1_OUT / "path1_deployment_location_state_detail.csv", index=False)

    best = results[results["variant"].ne("exact_ggg_reference")].sort_values("sharpe", ascending=False).head(5)
    lines = [
        "# Path 1 Deployment Location Report",
        "",
        "Research-only deployment-location test. All variants use saved GGG weights as the reference and exact GGG return plumbing.",
        "",
        "## Stage Exposure Diagnostics",
        "",
        md_table(stage_table, ["stage", "rows", "avg_cash", "avg_offense", "avg_defense", "avg_total"], 10),
        "",
        "## Variant Results",
        "",
        md_table(results.sort_values("sharpe", ascending=False), ["variant", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "delta_sharpe_vs_exact_ggg", "promising"], 12),
        "",
        "## Best Non-Reference Locations",
        "",
        md_table(best, ["variant", "deployment_location", "ann_return", "sharpe", "delta_sharpe_vs_exact_ggg", "delta_max_drawdown_vs_exact_ggg", "delta_cvar_5_vs_exact_ggg"], 5),
        "",
        "## Interpretation",
        "",
        "- Deployment location matters because post-overlay final-weight scaling is not equivalent to changing confidence before regime, target-vol, and recovery/neutral budget rules.",
        "- The test is still a proxy: it does not rerun HRP or the production overlay engine, so pre-overlay and sleeve-level rows should be read as location diagnostics rather than production candidates.",
        "- Exact GGG plumbing makes the comparison cleaner than B7/B8: remaining failures are deployment architecture failures, not return-alignment artifacts.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path1_deployment_location_report.md", lines)

    print(f"Wrote {rel(PATH1_OUT / 'path1_deployment_location_results.csv')} rows={len(results)}")
    print(f"Wrote {rel(DOCS / 'path1_deployment_location_report.md')}")


if __name__ == "__main__":
    main()

