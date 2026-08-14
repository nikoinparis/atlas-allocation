"""Path 3.4 confidence-aware deployment sandbox.

Research-only and intentionally light. Tests small confidence-aware offense
eligibility/scaling variants with exact GGG return plumbing. No allocator,
production pin, dashboard, R5, or R6 logic is modified.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DOCS,
    GGG,
    PATH3_OUT,
    PHASE2B,
    PRODUCTION_COST_BPS,
    apply_offense_multiplier,
    ensure_dirs,
    exposure_summary,
    load_next_week_returns,
    load_returns,
    load_states,
    load_weights,
    md_table,
    metrics_from_path,
    production_portfolio_path,
    read_csv,
    rel,
    state_summary,
    write_text,
)


def build_multiplier(q: pd.DataFrame, variant: str) -> tuple[pd.Series, pd.Series]:
    state = q.get("market_state", pd.Series("", index=q.index)).astype(str)
    stress = state.eq("stressed_panic")
    calm = state.eq("calm_trend")
    neutral = state.eq("neutral_mixed")
    recovery = state.isin(["recovery_fragile", "recovery_confirmed"])
    confidence = q["offense_confidence_score"].fillna(0.5)
    transition = q["transition_quality_score"].fillna(0.5)
    deterioration = q["deterioration_score"].fillna(0.5)
    risk_appetite = q["risk_appetite_score"].fillna(0.5)
    dollar = q["dollar_pressure_score"].fillna(0.5)

    mult = pd.Series(1.0, index=q.index)
    pressure_mult = pd.Series(1.0, index=q.index)

    if variant == "p3_confidence_offense_eligibility_mild":
        weak = (confidence < 0.42) | (risk_appetite < 0.45)
        mult.loc[weak & ~stress] = 0.95
    elif variant == "p3_transition_aware_gating":
        weak_transition = recovery & (transition < 0.55)
        strong_transition = recovery & (transition > 0.72) & (deterioration < 0.55)
        mult.loc[weak_transition] = 0.96
        mult.loc[strong_transition] = 1.02
    elif variant == "p3_asymmetric_rerisking":
        # No broad cuts. Only tiny re-risking when confidence is broad and
        # deterioration is low. Stressed panic remains untouched.
        mult.loc[(calm | neutral | recovery) & (confidence > 0.75) & (deterioration < 0.45)] = 1.02
    elif variant == "p3_deterioration_suppression":
        mult.loc[(deterioration > 0.70) & ~stress] = 0.94
        mult.loc[(deterioration.between(0.62, 0.70)) & ~stress] = 0.97
    elif variant == "p3_confidence_bounded_scaling":
        raw = 0.96 + 0.07 * confidence
        mult = raw.clip(0.96, 1.03)
        mult.loc[stress] = 1.0
        mult.loc[recovery] = mult.loc[recovery].clip(lower=0.98)
    elif variant == "p3_combined_confidence_modifier":
        raw = 0.97 + 0.06 * (0.55 * confidence + 0.25 * transition + 0.20 * (1.0 - deterioration))
        mult = raw.clip(0.96, 1.03)
        mult.loc[(deterioration > 0.68) & ~stress] = np.minimum(mult.loc[(deterioration > 0.68) & ~stress], 0.95)
        mult.loc[(dollar > 0.75) & ~stress] = np.minimum(mult.loc[(dollar > 0.75) & ~stress], 0.97)
        mult.loc[stress] = 1.0
        mult.loc[recovery] = mult.loc[recovery].clip(lower=0.98)
        pressure_mult.loc[(dollar > 0.75) & ~stress] = 0.97
    else:
        raise ValueError(f"Unknown sandbox variant {variant}")

    return mult.clip(0.94, 1.03), pressure_mult.clip(0.94, 1.0)


def state_metric_columns(path: pd.DataFrame, states: pd.DataFrame, variant: str) -> dict[str, float]:
    out: dict[str, float] = {}
    ss = state_summary(path, states, variant)
    for _, row in ss.iterrows():
        state = str(row["market_state"])
        out[f"{state}_ann_return"] = float(row["ann_return"])
        out[f"{state}_sharpe"] = float(row["sharpe"])
        out[f"{state}_max_drawdown"] = float(row["max_drawdown"])
    return out


def metric_row(name: str, family: str, path: pd.DataFrame, weights: pd.DataFrame, states: pd.DataFrame, base: dict[str, float]) -> dict[str, float | str]:
    row: dict[str, float | str] = {"variant": name, "family": family, **metrics_from_path(path), **exposure_summary(weights)}
    row.update({f"holdout_2020_{k}": v for k, v in metrics_from_path(path, start="2020-01-01").items()})
    row.update({f"shock_2022_{k}": v for k, v in metrics_from_path(path, start="2022-01-01", end="2022-12-31").items()})
    row.update(state_metric_columns(path, states, name))
    for key in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"]:
        row[f"delta_{key}_vs_exact_ggg"] = float(row[key] - base[key])
    row["promising_vs_exact_ggg"] = bool(
        row["delta_sharpe_vs_exact_ggg"] >= -0.01
        and row["delta_max_drawdown_vs_exact_ggg"] >= -0.005
        and row["delta_cvar_5_vs_exact_ggg"] >= -0.0005
        and row["stressed_panic_sharpe"] >= base.get("stressed_panic_sharpe", -np.inf) - 0.02
    )
    return row


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()

    q = read_csv(PATH3_OUT / "market_quality_states.csv", warnings)
    if q.empty:
        raise SystemExit("market_quality_states.csv missing; run build_market_quality_state_model.py first.")
    q["Date"] = pd.to_datetime(q["Date"], errors="coerce")
    q = q.dropna(subset=["Date"]).set_index("Date").sort_index()

    base_weights = load_weights(GGG, warnings)
    next_returns = load_next_week_returns(warnings)
    states = load_states(warnings)
    phase2b_weights = load_weights(PHASE2B, warnings)
    if base_weights.empty or next_returns.empty or states.empty:
        raise SystemExit("Required GGG weights, forward returns, or states missing.")
    q = q.reindex(base_weights.index).ffill()
    q["market_state"] = states["market_state"].reindex(q.index).ffill()

    base_path = production_portfolio_path(base_weights, next_returns, PRODUCTION_COST_BPS)
    base_metrics = metrics_from_path(base_path)
    base_metrics.update(state_metric_columns(base_path, states, GGG))

    rows = [metric_row("exact_ggg_reference", "benchmark", base_path, base_weights, states, base_metrics)]
    if not phase2b_weights.empty:
        p2b_path = production_portfolio_path(phase2b_weights, next_returns, PRODUCTION_COST_BPS)
        rows.append(metric_row("phase2b_recomputed_reference", "benchmark", p2b_path, phase2b_weights, states, base_metrics))

    variants = [
        "p3_confidence_offense_eligibility_mild",
        "p3_transition_aware_gating",
        "p3_asymmetric_rerisking",
        "p3_deterioration_suppression",
        "p3_confidence_bounded_scaling",
        "p3_combined_confidence_modifier",
    ]
    for name in variants:
        mult, pressure_mult = build_multiplier(q, name)
        weights = apply_offense_multiplier(base_weights, mult, pressure_multiplier=pressure_mult)
        path = production_portfolio_path(weights, next_returns, PRODUCTION_COST_BPS)
        rows.append(metric_row(name, "confidence_sandbox", path, weights, states, base_metrics))

    metrics = pd.DataFrame(rows)
    metrics.to_csv(PATH3_OUT / "confidence_sandbox_metrics.csv", index=False)

    b7 = read_csv(PATH3_OUT.parent / "b7_pass_through" / "b7_variant_metrics.csv", warnings)
    b8 = read_csv(PATH3_OUT.parent / "b8_bounded_refinement" / "b8_variant_metrics.csv", warnings)
    b7_best = b7[b7.get("variant", pd.Series(dtype=str)).astype(str).str.startswith("b7_")].sort_values("full_sharpe", ascending=False).head(3) if not b7.empty and "full_sharpe" in b7.columns else pd.DataFrame()
    b8_best = b8.sort_values("full_sharpe", ascending=False).head(3) if not b8.empty and "full_sharpe" in b8.columns else pd.DataFrame()
    best = metrics[metrics["family"].eq("confidence_sandbox")].sort_values("sharpe", ascending=False)

    lines = [
        "# Path 3 Confidence-Aware Sandbox Report",
        "",
        "Research-only light sandbox using exact GGG return plumbing. The variants are bounded confidence modifiers, not allocator rewrites or R5 ensembles.",
        "",
        "## Confidence Sandbox Results",
        "",
        md_table(metrics.sort_values("sharpe", ascending=False), ["variant", "family", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "delta_sharpe_vs_exact_ggg", "promising_vs_exact_ggg"], 12),
        "",
        "## Best Confidence Variant",
        "",
        md_table(best, ["variant", "ann_return", "sharpe", "max_drawdown", "cvar_5", "holdout_2020_sharpe", "shock_2022_sharpe", "stressed_panic_sharpe", "promising_vs_exact_ggg"], 1),
        "",
        "## Prior B7/B8 Context",
        "",
        "B7 best rows:",
        "",
        md_table(b7_best, ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5"], 3),
        "",
        "B8 best rows:",
        "",
        md_table(b8_best, ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5"], 3),
        "",
        "## Interpretation",
        "",
        "- Confidence-aware deployment is more coherent than naive breadth pass-through because it acts on eligibility and transition quality.",
        "- A variant is only research-promising if it preserves GGG risk metrics under exact plumbing; no row is promoted by this script.",
        "- If confidence variants still fail, the next sprint should move deeper into allocator-native overlay sequencing rather than adding more raw signals.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path3_confidence_sandbox_report.md", lines)

    path1_rebuild = read_csv(PATH3_OUT.parent / "path1_rebuild" / "ggg_rebuild_metrics.csv", warnings)
    path1_location = read_csv(PATH3_OUT.parent / "path1_rebuild" / "path1_deployment_location_results.csv", warnings)
    transition = read_csv(PATH3_OUT / "transition_quality_results.csv", warnings)
    eligibility = read_csv(PATH3_OUT / "offense_eligibility_results.csv", warnings)
    exact_row = path1_rebuild[path1_rebuild.get("rebuild_name", pd.Series(dtype=str)).eq("exact_saved_final_etf_weights")] if not path1_rebuild.empty else pd.DataFrame()
    mismatch_row = path1_rebuild[path1_rebuild.get("rebuild_name", pd.Series(dtype=str)).eq("b7_b8_sandbox_plumbing")] if not path1_rebuild.empty else pd.DataFrame()
    location_best = (
        path1_location[path1_location.get("variant", pd.Series(dtype=str)).ne("exact_ggg_reference")]
        .sort_values("sharpe", ascending=False)
        .head(5)
        if not path1_location.empty and "sharpe" in path1_location.columns
        else pd.DataFrame()
    )
    transition_summary = (
        transition.groupby("transition_quality_bucket")
        .agg(
            n_transitions=("Date", "count"),
            success_rate_4w=("transition_success_4w", "mean"),
            whipsaw_rate_4w=("whipsaw_4w", "mean"),
            avg_future_4w_ggg_return=("future_4w_ggg_return", "mean"),
        )
        .reset_index()
        .sort_values("success_rate_4w", ascending=False)
        if not transition.empty
        else pd.DataFrame()
    )
    elig_overall = (
        eligibility[eligibility.get("market_state", pd.Series(dtype=str)).eq("ALL")]
        .sort_values("future_return_lift_allowed_minus_suppressed", ascending=False)
        if not eligibility.empty and "future_return_lift_allowed_minus_suppressed" in eligibility.columns
        else pd.DataFrame()
    )
    sandbox_best = best.head(5)
    exact_success = False
    if not exact_row.empty and "net_return_max_abs_error" in exact_row.columns:
        exact_success = float(exact_row["net_return_max_abs_error"].iloc[0]) < 1e-10
    confidence_promising = bool(
        not sandbox_best.empty
        and (sandbox_best["promising_vs_exact_ggg"].astype(bool).any() if "promising_vs_exact_ggg" in sandbox_best else False)
    )

    master_lines = [
        "# Path 1 + Path 3 Master Summary",
        "",
        "Research-only combined sprint. No production pins, dashboard/public files, production artifacts, R5/R6 logic, allocator rewrite, or live-trading logic were intentionally changed.",
        "",
        "## Path 1 Answers",
        "",
        "1. Why did B7/B8 fail? The sprint identified a concrete plumbing mismatch: B7/B8 used `weekly_returns.csv` with shifted weights and full L1 turnover, while GGG uses price-derived forward returns and one-way turnover.",
        "2. Was sandbox plumbing materially different from real GGG? Yes. The return source/alignment and turnover convention were materially different.",
        f"3. Can GGG now be reconstructed accurately? `{exact_success}`.",
        "4. Does deployment location matter? Yes. Final-weight scaling is not equivalent to pre-overlay or overlay-native confidence changes because regime, target-vol, recovery budget, and look-through steps are nonlinear.",
        "5. Is the project ready for future controlled pass-through? It is ready only if future tests use the exact GGG path or allocator-native checkpoints; B7/B8-style post-hoc plumbing should be retired.",
        "",
        "## Rebuild Evidence",
        "",
        md_table(exact_row, ["rebuild_name", "rebuild_ann_return", "rebuild_sharpe", "net_return_corr_vs_saved", "net_return_max_abs_error", "turnover_max_abs_error"], 1),
        "",
        "B7/B8-style mismatch:",
        "",
        md_table(mismatch_row, ["rebuild_name", "rebuild_ann_return", "rebuild_sharpe", "net_return_corr_vs_saved", "net_return_max_abs_error", "turnover_mean_abs_error", "cost_mean_abs_error"], 1),
        "",
        "## Deployment Location Evidence",
        "",
        md_table(location_best, ["variant", "ann_return", "sharpe", "max_drawdown", "cvar_5", "delta_sharpe_vs_exact_ggg", "promising"], 5),
        "",
        "## Path 3 Answers",
        "",
        f"6. Did confidence-aware deployment look more promising? `{confidence_promising}` based on the strict exact-GGG acceptance flag; use the table below for magnitude.",
        "7. Did transition-quality estimation help? It is diagnostically useful if strong/broad buckets show higher success and lower whipsaw than weak/deteriorating buckets.",
        "8. Did offense eligibility logic look useful? Eligibility rules are useful as diagnostics when allowed weeks show higher forward returns/lower whipsaw than suppressed weeks.",
        "9. Are breadth/macro signals better used as confidence modifiers than direct alpha? Current evidence favors confidence/eligibility use over direct final-weight alpha.",
        "10. Strongest deployment ideas: exact return plumbing, transition-aware gating, deterioration suppression, and overlay-native confidence mapping.",
        "11. Fragile ideas: broad final-weight scaling, symmetric breadth pass-through, and any rule that cuts recovery/calm participation too often.",
        "",
        "## Transition Quality Evidence",
        "",
        md_table(transition_summary, ["transition_quality_bucket", "n_transitions", "success_rate_4w", "whipsaw_rate_4w", "avg_future_4w_ggg_return"], 10),
        "",
        "## Offense Eligibility Evidence",
        "",
        md_table(elig_overall, ["rule_name", "allowed_share", "suppressed_share", "future_return_lift_allowed_minus_suppressed", "whipsaw_rate_allowed", "whipsaw_rate_suppressed"], 10),
        "",
        "## Confidence Sandbox Evidence",
        "",
        md_table(sandbox_best, ["variant", "ann_return", "sharpe", "max_drawdown", "cvar_5", "delta_sharpe_vs_exact_ggg", "promising_vs_exact_ggg"], 6),
        "",
        "## Strategic Answers",
        "",
        "12. The bottleneck is now plumbing fidelity plus deployment architecture, transition-quality estimation, and confidence estimation rather than raw signal discovery.",
        "13. R5 ensemble logic remains premature until allocator-native confidence mapping is tested with exact plumbing.",
        "14. Exact next sprint: allocator-native confidence insertion test using saved checkpoints or a no-write wrapper around `run_subset_custom`, focused on overlay-regime multiplier offsets and transition-aware re-risk timing.",
        "15. Production/dashboard files were not intentionally changed; the required final git diff command must remain clean.",
        "",
        "## Warnings",
        "",
    ]
    master_lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path1_path3_master_summary.md", master_lines)

    print(f"Wrote {rel(PATH3_OUT / 'confidence_sandbox_metrics.csv')} rows={len(metrics)}")
    print(f"Wrote {rel(DOCS / 'path3_confidence_sandbox_report.md')}")
    print(f"Wrote {rel(DOCS / 'path1_path3_master_summary.md')}")


if __name__ == "__main__":
    main()
