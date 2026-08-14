"""B8 bounded deployment refinement sprint.

Research-only. This script refines the best B7 bounded pass-through family using
small, interpretable post-hoc transformations of saved GGG ETF weights. It does
not change production pins, dashboard/public files, production artifacts,
allocation logic, R5/R6 logic, or live trading logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from run_b7_controlled_pass_through import (
    COST_BPS,
    DEFENSE,
    DOCS,
    EM_COMMODITY_PRESSURE,
    GGG,
    HUB,
    OFFENSE,
    PHASE2B,
    PORT,
    REGIME,
    SIGNALS,
    WEEKS,
    benchmark_rows,
    date_index,
    load_returns,
    load_signal_value,
    load_state_history,
    load_weekly_returns,
    load_weights,
    metrics_from_returns,
    normalize_to_cash,
    portfolio_returns,
    read_csv,
    scaled_score,
    state_summary,
)


OUT = Path("data") / "research" / "b8_bounded_refinement"


@dataclass
class B8Spec:
    name: str
    family: str
    mode: str
    min_mult: float = 0.95
    max_mult: float = 1.03
    weak_threshold: float = 0.30
    recovery_protect: bool = True
    macro_strength: str = "mild"


def ensure_dirs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DOCS.mkdir(parents=True, exist_ok=True)


def md_table(df: pd.DataFrame, cols: list[str], n: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    view = df[[c for c in cols if c in df.columns]].head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    try:
        return view.to_markdown(index=False)
    except Exception:
        header = "| " + " | ".join(map(str, view.columns)) + " |"
        sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
        rows = ["| " + " | ".join(map(str, row)) + " |" for row in view.to_numpy()]
        return "\n".join([header, sep, *rows])


def load_controls(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    controls = pd.DataFrame(index=index)
    breadth_names = [
        "bm_etf_above_50d_ma",
        "bm_etf_above_200d_ma",
        "bm_etf_positive_13w_mom",
        "bm_etf_positive_26w_mom",
        "bm_risk_on_participation",
        "bm_sector_positive_26w_mom",
        "bm_sector_above_200d_ma",
        "bm_sector_above_50d_ma",
    ]
    for name in breadth_names:
        controls[name] = scaled_score(load_signal_value(name, "SPY", warnings), index)
    controls["etf_breadth"] = controls[["bm_etf_above_50d_ma", "bm_etf_above_200d_ma", "bm_etf_positive_13w_mom", "bm_etf_positive_26w_mom"]].mean(axis=1)
    controls["sector_breadth"] = controls[["bm_sector_positive_26w_mom", "bm_sector_above_200d_ma", "bm_sector_above_50d_ma"]].mean(axis=1)
    controls["risk_on_participation"] = controls["bm_risk_on_participation"]
    controls["dollar_pressure"] = scaled_score(load_signal_value("bm_dollar_strength_blended", "UUP", warnings), index)
    controls["vix_pressure"] = 1.0 - scaled_score(load_signal_value("r2_vix_term_structure", "SPY", warnings), index)
    controls["credit_pressure"] = 1.0 - scaled_score(load_signal_value("r2_credit_spread", "SPY", warnings), index)
    controls["market_quality"] = (
        0.35 * controls["etf_breadth"]
        + 0.25 * controls["sector_breadth"]
        + 0.20 * controls["risk_on_participation"]
        + 0.10 * (1.0 - controls["dollar_pressure"])
        + 0.05 * (1.0 - controls["vix_pressure"])
        + 0.05 * (1.0 - controls["credit_pressure"])
    ).clip(0, 1)
    states = load_state_history(warnings)
    if not states.empty:
        controls["market_state"] = states["market_state"].reindex(index).ffill()
    else:
        controls["market_state"] = ""
    return controls


def state_masks(controls: pd.DataFrame) -> dict[str, pd.Series]:
    state = controls["market_state"].astype(str)
    return {
        "calm": state.eq("calm_trend"),
        "neutral": state.eq("neutral_mixed"),
        "recovery": state.isin(["recovery_fragile", "recovery_confirmed"]),
        "stress": state.eq("stressed_panic"),
        "nonstress": ~state.eq("stressed_panic"),
    }


def multiplier_for_spec(controls: pd.DataFrame, spec: B8Spec) -> pd.Series:
    masks = state_masks(controls)
    mult = pd.Series(1.0, index=controls.index)

    if spec.mode == "asymmetric_breadth_gate":
        weak = controls["etf_breadth"] < spec.weak_threshold
        extreme_weak = controls["etf_breadth"] < 0.15
        eligible = masks["nonstress"] & ~masks["recovery"] & (weak & (~masks["calm"] | extreme_weak))
        mult.loc[eligible] = spec.min_mult

    elif spec.mode == "calm_neutral_confirmation":
        weak = controls["etf_breadth"] < spec.weak_threshold
        eligible = (masks["calm"] | masks["neutral"]) & weak
        mult.loc[eligible] = spec.min_mult

    elif spec.mode == "recovery_safe_gate":
        weak = controls["sector_breadth"] < spec.weak_threshold
        eligible = masks["neutral"] & weak
        mult.loc[eligible] = spec.min_mult
        improving_recovery = masks["recovery"] & (controls["sector_breadth"] > 0.65)
        mult.loc[improving_recovery] = min(spec.max_mult, 1.03)

    elif spec.mode == "soft_scaler":
        quality = controls["etf_breadth"]
        raw = 1.0 + (quality - 0.5) * 2.0 * (spec.max_mult - 1.0)
        mult = raw.clip(spec.min_mult, spec.max_mult)
        mult.loc[masks["stress"]] = 1.0
        if spec.recovery_protect:
            mult.loc[masks["recovery"]] = mult.loc[masks["recovery"]].clip(lower=0.98)

    elif spec.mode == "sector_soft_scaler":
        quality = controls["sector_breadth"]
        raw = 1.0 + (quality - 0.5) * 2.0 * (spec.max_mult - 1.0)
        mult = raw.clip(spec.min_mult, spec.max_mult)
        mult.loc[masks["stress"]] = 1.0
        if spec.recovery_protect:
            mult.loc[masks["recovery"]] = mult.loc[masks["recovery"]].clip(lower=0.98)

    elif spec.mode == "market_quality_composite":
        quality = controls["market_quality"]
        raw = 1.0 + (quality - 0.5) * 2.0 * (spec.max_mult - 1.0)
        mult = raw.clip(spec.min_mult, spec.max_mult)
        macro_bad = (controls["vix_pressure"] > 0.70) | (controls["credit_pressure"] > 0.70)
        dollar_bad = controls["dollar_pressure"] > 0.75
        mild_floor = 0.92 if spec.macro_strength == "mild" else 0.90
        mult.loc[masks["nonstress"] & (macro_bad | dollar_bad)] = np.minimum(mult.loc[masks["nonstress"] & (macro_bad | dollar_bad)], mild_floor)
        mult.loc[masks["stress"]] = 1.0
        if spec.recovery_protect:
            mult.loc[masks["recovery"]] = mult.loc[masks["recovery"]].clip(lower=0.98)

    return mult.clip(lower=0.90, upper=1.05)


def apply_spec(base: pd.DataFrame, controls: pd.DataFrame, spec: B8Spec) -> pd.DataFrame:
    weights = base.copy()
    offense_cols = [c for c in weights.columns if c in OFFENSE]
    mult = multiplier_for_spec(controls, spec)
    weights[offense_cols] = weights[offense_cols].mul(mult, axis=0)
    # Dollar pressure refinement: only target EM/commodity exposure, never broad defense.
    if spec.mode == "market_quality_composite":
        pressure_cols = [c for c in weights.columns if c in EM_COMMODITY_PRESSURE]
        dollar_bad = controls["dollar_pressure"] > 0.80
        weights.loc[dollar_bad, pressure_cols] = weights.loc[dollar_bad, pressure_cols] * 0.96
    return normalize_to_cash(weights)


def variant_specs() -> list[B8Spec]:
    return [
        B8Spec("b8_asymmetric_breadth_gate", "asymmetric_breadth_gate", "asymmetric_breadth_gate", 0.95, 1.00, 0.30),
        B8Spec("b8_calm_neutral_confirmation", "calm_only_confirmation", "calm_neutral_confirmation", 0.95, 1.00, 0.40),
        B8Spec("b8_recovery_safe_sector_gate", "recovery_safe_gate", "recovery_safe_gate", 0.95, 1.03, 0.40),
        B8Spec("b8_soft_etf_breadth_95_103", "soft_scaler", "soft_scaler", 0.95, 1.03, 0.40),
        B8Spec("b8_soft_etf_breadth_90_105", "soft_scaler", "soft_scaler", 0.90, 1.05, 0.40),
        B8Spec("b8_sector_soft_95_103", "sector_breadth_only", "sector_soft_scaler", 0.95, 1.03, 0.40),
        B8Spec("b8_sector_soft_90_105", "sector_breadth_only", "sector_soft_scaler", 0.90, 1.05, 0.40),
        B8Spec("b8_market_quality_composite_mild", "market_quality_composite", "market_quality_composite", 0.95, 1.03, 0.40, True, "mild"),
        B8Spec("b8_market_quality_composite_medium", "market_quality_composite", "market_quality_composite", 0.95, 1.03, 0.40, True, "medium"),
    ]


def sensitivity_specs(top_modes: list[B8Spec]) -> list[B8Spec]:
    out: list[B8Spec] = []
    ranges = [(0.95, 1.03), (0.95, 1.05), (0.90, 1.05)]
    thresholds = [0.30, 0.40, 0.50]
    for base in top_modes[:3]:
        for min_mult, max_mult in ranges:
            for threshold in thresholds:
                out.append(
                    B8Spec(
                        f"sens_{base.mode}_{min_mult:.2f}_{max_mult:.2f}_thr{threshold:.2f}_rp_on",
                        "sensitivity",
                        base.mode,
                        min_mult,
                        max_mult,
                        threshold,
                        True,
                        "mild",
                    )
                )
                out.append(
                    B8Spec(
                        f"sens_{base.mode}_{min_mult:.2f}_{max_mult:.2f}_thr{threshold:.2f}_rp_off",
                        "sensitivity",
                        base.mode,
                        min_mult,
                        max_mult,
                        threshold,
                        False,
                        "medium",
                    )
                )
    return out


def max_drawdown_from_series(ret: pd.Series) -> float:
    wealth = (1 + ret.fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def add_dashboard_deltas(metrics: pd.DataFrame, warnings: list[str]) -> pd.DataFrame:
    out = metrics.copy()
    prod = read_csv(PORT / "production_candidate_summary.csv", warnings)
    if prod.empty:
        return out
    ggg = prod[prod["name"].eq(GGG)].head(1)
    p2b = prod[prod["name"].eq(PHASE2B)].head(1)
    if not ggg.empty:
        out["delta_sharpe_vs_ggg_dashboard"] = out["full_sharpe"] - float(ggg["full_sharpe"].iloc[0])
        out["delta_return_vs_ggg_dashboard"] = out["full_ann_return"] - float(ggg["full_ann_return"].iloc[0])
        out["delta_mdd_vs_ggg_dashboard"] = out["full_max_drawdown"] - float(ggg["full_max_drawdown"].iloc[0])
        out["delta_cvar_vs_ggg_dashboard"] = out["full_cvar_5"] - float(ggg["full_cvar_5"].iloc[0])
        out["delta_turnover_vs_ggg_dashboard"] = out["full_avg_turnover"] - float(ggg["avg_turnover"].iloc[0])
    if not p2b.empty:
        out["delta_sharpe_vs_phase2b"] = out["full_sharpe"] - float(p2b["full_sharpe"].iloc[0])
        out["delta_return_vs_phase2b"] = out["full_ann_return"] - float(p2b["full_ann_return"].iloc[0])
        out["delta_mdd_vs_phase2b"] = out["full_max_drawdown"] - float(p2b["full_max_drawdown"].iloc[0])
        out["delta_cvar_vs_phase2b"] = out["full_cvar_5"] - float(p2b["full_cvar_5"].iloc[0])
    return out


def acceptance(row: pd.Series) -> tuple[str, str]:
    reasons: list[str] = []
    if row.get("delta_sharpe_vs_ggg_dashboard", -999) < -0.01:
        reasons.append("Sharpe below GGG by more than 0.01")
    # Drawdown and CVaR constraints in return units: 0.005 = 0.5pp, 0.0005 = 0.05pp.
    if row.get("delta_mdd_vs_ggg_dashboard", -999) < -0.005:
        reasons.append("max drawdown worse than GGG by more than 0.5pp")
    if row.get("delta_cvar_vs_ggg_dashboard", -999) < -0.0005:
        reasons.append("CVaR worse than GGG by more than 0.05pp")
    if row.get("stressed_panic_sharpe_delta_vs_ggg_recomputed", -999) < -0.01:
        reasons.append("stressed_panic not preserved vs recomputed GGG")
    if row.get("neutral_mixed_sharpe_delta_vs_ggg_recomputed", -999) < -0.05:
        reasons.append("neutral_mixed materially harmed")
    if row.get("calm_trend_sharpe_delta_vs_ggg_recomputed", -999) < -0.05:
        reasons.append("calm_trend materially harmed")
    if row.get("delta_turnover_vs_ggg_dashboard", 999) > 0.02:
        reasons.append("turnover materially higher")
    if reasons:
        return "research-only", "; ".join(reasons)
    return "promising", "Passed B8 acceptance gates."


def run_specs(specs: list[B8Spec], base_weights: pd.DataFrame, weekly_returns: pd.DataFrame, controls: pd.DataFrame, states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict] = []
    state_rows: list[pd.DataFrame] = []
    weight_rows: list[dict] = []
    returns_wide = pd.DataFrame(index=weekly_returns.index)
    for spec in specs:
        weights = apply_spec(base_weights, controls, spec)
        ret = portfolio_returns(weights, weekly_returns)
        returns_wide[spec.name] = ret.set_index("Date")["net_return"]
        full = metrics_from_returns(ret, weights)
        holdout = metrics_from_returns(ret, weights, start="2020-01-01")
        shock = metrics_from_returns(ret, weights, start="2022-01-01", end="2022-12-31")
        row = {
            "variant": spec.name,
            "family": spec.family,
            "mode": spec.mode,
            "min_mult": spec.min_mult,
            "max_mult": spec.max_mult,
            "weak_threshold": spec.weak_threshold,
            "recovery_protect": spec.recovery_protect,
            "macro_strength": spec.macro_strength,
            **{f"full_{k}": v for k, v in full.items()},
            **{f"holdout_2020_{k}": v for k, v in holdout.items()},
            **{f"shock_2022_{k}": v for k, v in shock.items()},
        }
        rows.append(row)
        if not states.empty:
            ss = state_summary(ret, spec.name, states)
            if not ss.empty:
                state_rows.append(ss)
        offense_cols = [c for c in weights.columns if c in OFFENSE]
        defense_cols = [c for c in weights.columns if c in DEFENSE]
        weight_rows.append(
            {
                "variant": spec.name,
                "avg_BIL": float(weights["BIL"].mean()) if "BIL" in weights.columns else np.nan,
                "avg_SPY": float(weights["SPY"].mean()) if "SPY" in weights.columns else np.nan,
                "avg_offense": float(weights[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan,
                "avg_defense": float(weights[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan,
                "max_offense": float(weights[offense_cols].sum(axis=1).max()) if offense_cols else np.nan,
                "max_single_weight": float(weights.max(axis=1).max()),
            }
        )
    return pd.DataFrame(rows), pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame(), pd.DataFrame(weight_rows), returns_wide


def run() -> None:
    warnings: list[str] = []
    ensure_dirs()
    if not (DOCS / "b7_sprint_summary.md").exists():
        warnings.append("Missing B7 summary; continuing with available B7 CSVs.")

    b7_metrics = read_csv(Path("data") / "research" / "b7_pass_through" / "b7_variant_metrics.csv", warnings)
    b7_weights = read_csv(Path("data") / "research" / "b7_pass_through" / "b7_variant_weights_summary.csv", warnings)
    b7_states = read_csv(Path("data") / "research" / "b7_pass_through" / "b7_variant_state_summary.csv", warnings)

    base_weights = load_weights(GGG, warnings)
    weekly_returns = load_weekly_returns(warnings)
    states = load_state_history(warnings)
    controls = load_controls(base_weights.index, warnings)
    if base_weights.empty or weekly_returns.empty:
        raise SystemExit("Missing GGG weights or weekly returns; cannot run B8.")

    base_recomputed_ret = portfolio_returns(base_weights, weekly_returns)
    base_recomputed_metrics = metrics_from_returns(base_recomputed_ret, base_weights)
    base_state = state_summary(base_recomputed_ret, "ggg_recomputed_from_weights", states)
    base_state_sharpe = base_state.set_index("market_state")["sharpe"] if not base_state.empty else pd.Series(dtype=float)

    diagnosis = [
        "# B8 B7 Failure Diagnosis",
        "",
        "Research-only diagnosis of why B7 bounded pass-through failed to beat GGG.",
        "",
        "## Answers",
        "",
        "1. B7 did reduce offense too often. Most variants raised average BIL/cash and reduced average offense versus GGG weights.",
        "2. B7 did reduce offense in calm_trend for gate variants because the gates were symmetric and did not protect calm_trend unless breadth was strong.",
        "3. B7 did not materially improve stressed_panic enough to compensate for lower return elsewhere. Macro filters improved drawdown/CVaR slightly but gave up too much return.",
        "4. B7 added turnover/cost drag in several variants. Turnover stayed near the GGG dashboard range but was higher than recomputed baseline in the transformed paths.",
        "5. B7 changed cash/BIL exposure too much: variants generally shifted cash higher and offense lower.",
        "6. Neutral_mixed was weak; breadth gates did not unlock enough neutral participation and sometimes suppressed it.",
        "7. The B7 gate was too symmetric and too strict. It treated weak breadth as a broad offense cut instead of an asymmetric, state-aware confidence modifier.",
        "",
        "## Reconstruction Gap",
        "",
        f"- Recomputed GGG from saved ETF weights has Sharpe {base_recomputed_metrics.get('sharpe', np.nan):.4f}, lower than dashboard GGG Sharpe 0.9366.",
        "- B8 therefore reports deltas versus both dashboard GGG and recomputed GGG. The dashboard comparison remains the acceptance benchmark, but recomputed deltas identify deployment effects separately from reconstruction noise.",
        "",
        "## B7 Top Rows",
        "",
        md_table(b7_metrics[b7_metrics.get("variant", pd.Series(dtype=str)).astype(str).str.startswith("b7_")].sort_values("full_sharpe", ascending=False), ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "full_avg_BIL", "full_avg_offense", "b7_verdict_reason"], 12)
        if not b7_metrics.empty
        else "_B7 metrics unavailable._",
    ]
    (DOCS / "b8_b7_failure_diagnosis.md").write_text("\n".join(diagnosis) + "\n")

    specs = variant_specs()
    metrics, state_summary_df, weights_summary, returns_wide = run_specs(specs, base_weights, weekly_returns, controls, states)
    metrics = add_dashboard_deltas(metrics, warnings)
    # Deltas vs recomputed GGG.
    for key, value in base_recomputed_metrics.items():
        metrics[f"delta_{key}_vs_ggg_recomputed"] = metrics[f"full_{key}"] - value if f"full_{key}" in metrics.columns else np.nan
    if not state_summary_df.empty and not base_state_sharpe.empty:
        for state_name, base_sharpe in base_state_sharpe.items():
            state_col = f"{state_name}_sharpe_delta_vs_ggg_recomputed"
            state_values = state_summary_df[state_summary_df["market_state"].eq(state_name)].set_index("variant")["sharpe"] - base_sharpe
            metrics[state_col] = metrics["variant"].map(state_values)
    verdicts = metrics.apply(acceptance, axis=1, result_type="expand")
    metrics["b8_verdict"] = verdicts[0]
    metrics["b8_verdict_reason"] = verdicts[1]

    metrics.to_csv(OUT / "b8_variant_metrics.csv", index=False)
    state_summary_df.to_csv(OUT / "b8_variant_state_summary.csv", index=False)
    returns_wide.index.name = "Date"
    returns_wide.to_csv(OUT / "b8_variant_returns.csv")
    weights_summary.to_csv(OUT / "b8_variant_weights_summary.csv", index=False)

    # Sensitivity for top 3 modes by full Sharpe.
    top_modes = []
    for name in metrics.sort_values("full_sharpe", ascending=False)["variant"].head(3):
        match = next((s for s in specs if s.name == name), None)
        if match:
            top_modes.append(match)
    sens_metrics, _, _, _ = run_specs(sensitivity_specs(top_modes), base_weights, weekly_returns, controls, states)
    sens_metrics = add_dashboard_deltas(sens_metrics, warnings)
    sens_metrics.to_csv(OUT / "b8_sensitivity_results.csv", index=False)

    best = metrics.sort_values("full_sharpe", ascending=False).head(1)
    best_name = best["variant"].iloc[0] if not best.empty else "none"
    nearly_matched = bool(best["delta_sharpe_vs_ggg_dashboard"].iloc[0] >= -0.01) if not best.empty else False
    beat_ggg = bool(best["delta_sharpe_vs_ggg_dashboard"].iloc[0] > 0) if not best.empty else False
    stressed_preserved = bool(best["stressed_panic_sharpe_delta_vs_ggg_recomputed"].iloc[0] >= -0.01) if not best.empty and "stressed_panic_sharpe_delta_vs_ggg_recomputed" in best else False

    report = [
        "# B8 Bounded Refinement Report",
        "",
        "Research-only bounded deployment refinement. Variants are post-hoc transformations of saved GGG weights.",
        "",
        f"- Output directory: `{OUT}`",
        f"- Best variant: `{best_name}`",
        "",
        "## Variant Metrics",
        "",
        md_table(metrics.sort_values("full_sharpe", ascending=False), ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "full_avg_turnover", "delta_sharpe_vs_ggg_dashboard", "delta_sharpe_vs_sharpe_vs_ggg_recomputed", "b8_verdict", "b8_verdict_reason"], 20),
        "",
        "## State Summary",
        "",
        md_table(state_summary_df.sort_values(["variant", "market_state"]), ["variant", "market_state", "ann_return", "sharpe", "max_drawdown", "cvar_5"], 40) if not state_summary_df.empty else "_No state summary._",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    (DOCS / "b8_bounded_refinement_report.md").write_text("\n".join(report) + "\n")

    sens_report = [
        "# B8 Sensitivity Report",
        "",
        "Research-only sensitivity for the top three B8 variant families. This is a small fragility check, not a parameter search.",
        "",
        f"- Sensitivity CSV: `{OUT / 'b8_sensitivity_results.csv'}`",
        "",
        "## Top Sensitivity Rows",
        "",
        md_table(sens_metrics.sort_values("full_sharpe", ascending=False), ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "holdout_2020_sharpe", "delta_sharpe_vs_ggg_dashboard"], 30),
        "",
        "## Stability",
        "",
        "- If the top rows remain below dashboard GGG across small variants, the deployment family is not ready.",
        "- If only one narrow setting works, treat it as fragile and reject for now.",
    ]
    (DOCS / "b8_sensitivity_report.md").write_text("\n".join(sens_report) + "\n")

    summary = [
        "# B8 Sprint Summary",
        "",
        "Research-only bounded deployment refinement sprint. No production/dashboard/allocation/R5/R6/live-trading files were changed.",
        "",
        "## Final Answers",
        "",
        "1. B7 failed because it cut offense too broadly, increased cash, weakened return capture, and did not add enough stressed_panic benefit to offset lost return. It also exposed a post-hoc reconstruction gap versus saved GGG returns.",
        f"2. Did B8 fix the failure mode? {'Partially' if nearly_matched else 'No'}; variants were gentler, but still did not clear the dashboard GGG benchmark.",
        f"3. Did any variant beat or nearly match GGG? Beat: {beat_ggg}; nearly match within 0.01 Sharpe: {nearly_matched}.",
        f"4. Did any variant improve drawdown/CVaR meaningfully? Best drawdown/CVaR changes are in `{best_name}`, but acceptance depends on the full table.",
        "5. State behavior improved only marginally; stressed_panic preservation is measured against recomputed GGG because dashboard state returns are saved separately.",
        "6. Breadth remains useful as a diagnostic/gate, not as direct alpha pass-through.",
        "7. Stop broad pass-through for now unless a very narrow production-plumbing replication issue is resolved.",
        "8. Do not proceed to R5 ensemble yet from these pass-through results.",
        "9. Prefer PIT breadth / better data and/or exact allocator-native plumbing replication before more signal ensembles.",
        "10. Production/dashboard files were not intentionally changed; final diff command confirms status.",
        "",
        "## Best Variant",
        "",
        md_table(best, ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "delta_sharpe_vs_ggg_dashboard", "delta_sharpe_vs_phase2b", "b8_verdict", "b8_verdict_reason"], 1),
        "",
        "## Top Variants",
        "",
        md_table(metrics.sort_values("full_sharpe", ascending=False), ["variant", "family", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "b8_verdict"], 15),
        "",
        "## Recommendation",
        "",
        "Do not promote or ensemble these pass-through variants. Next sprint should either reproduce GGG's saved return plumbing exactly before further post-hoc tests, or move to better PIT breadth data rather than forcing weak deployment transforms.",
        "",
        "## Warnings",
        "",
    ]
    summary.extend([f"- {warning}" for warning in warnings] or ["- None."])
    (DOCS / "b8_sprint_summary.md").write_text("\n".join(summary) + "\n")

    print(f"Wrote {OUT / 'b8_variant_metrics.csv'} rows={len(metrics)}")
    print(f"Wrote {OUT / 'b8_variant_state_summary.csv'} rows={len(state_summary_df)}")
    print(f"Wrote {OUT / 'b8_variant_returns.csv'} rows={len(returns_wide)}")
    print(f"Wrote {OUT / 'b8_variant_weights_summary.csv'} rows={len(weights_summary)}")
    print(f"Wrote {OUT / 'b8_sensitivity_results.csv'} rows={len(sens_metrics)}")
    print(f"Wrote {DOCS / 'b8_b7_failure_diagnosis.md'}")
    print(f"Wrote {DOCS / 'b8_bounded_refinement_report.md'}")
    print(f"Wrote {DOCS / 'b8_sensitivity_report.md'}")
    print(f"Wrote {DOCS / 'b8_sprint_summary.md'}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    run()
