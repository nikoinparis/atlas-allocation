"""C4 allocator-native confidence insertion research.

Research-only. This script uses the exact GGG return alignment and cost
plumbing reconstructed in Path 1, then tests small bounded confidence
insertion proxies without changing production pins, dashboard files, or
production portfolio artifacts.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    DATA,
    DOCS,
    GGG,
    OFFENSE,
    PHASE2B,
    PRESSURE_ASSETS,
    PRODUCTION_COST_BPS,
    ensure_dirs,
    exposure_summary,
    load_next_week_returns,
    load_states,
    load_weights,
    md_table,
    metrics_from_path,
    normalize_to_cash,
    production_portfolio_path,
    rel,
    state_summary,
    write_text,
)


NATIVE_OUT = DATA / "research" / "native_confidence"


VARIANT_SPECS = {
    "c4_regime_multiplier_confidence_offset": "regime_multiplier_offset",
    "c4_offensive_sleeve_budget_offset": "offensive_sleeve_budget_offset",
    "c4_transition_aware_rerisk_timing": "rerisk_timing_offset",
    "c4_deterioration_aware_derisk_timing": "derisk_timing_offset",
    "c4_combined_conservative_confidence_modifier": "combined_native_offsets",
    "c4_final_bounded_safety_check": "final_post_allocation_modifier",
}


def load_confidence(index: pd.Index, warnings: list[str]) -> pd.DataFrame:
    path = NATIVE_OUT / "c3_confidence_inputs.csv"
    if not path.exists():
        warnings.append(f"Missing C3 confidence inputs: {rel(path)}. Using neutral scores.")
        neutral = pd.DataFrame(index=index)
        for col in [
            "breadth_confidence",
            "sector_confidence",
            "risk_on_confidence",
            "macro_stress_filter",
            "dollar_pressure_filter",
            "transition_quality_score",
            "combined_market_quality_score",
            "offense_eligibility_score",
            "deterioration_score",
            "signal_agreement",
            "signal_dispersion",
        ]:
            neutral[col] = 0.5
        neutral["macro_stress_active"] = False
        neutral["dollar_pressure_active"] = False
        neutral["offense_eligible"] = True
        return neutral

    df = pd.read_csv(path)
    if "Date" not in df.columns:
        warnings.append(f"{rel(path)} lacks Date. Using neutral scores.")
        return load_confidence(pd.Index(index), warnings)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    df = df.reindex(index).ffill().bfill()
    numeric_defaults = {
        "breadth_confidence": 0.5,
        "sector_confidence": 0.5,
        "risk_on_confidence": 0.5,
        "macro_stress_filter": 0.5,
        "dollar_pressure_filter": 0.5,
        "transition_quality_score": 0.5,
        "combined_market_quality_score": 0.5,
        "offense_eligibility_score": 0.5,
        "deterioration_score": 0.5,
        "signal_agreement": 0.5,
        "signal_dispersion": 0.5,
    }
    for col, default in numeric_defaults.items():
        if col not in df.columns:
            warnings.append(f"C3 confidence inputs missing {col}; defaulted to {default}.")
            df[col] = default
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(default).clip(0.0, 1.0)
    for col in ["macro_stress_active", "dollar_pressure_active", "offense_eligible"]:
        if col not in df.columns:
            df[col] = False
        df[col] = df[col].astype(str).str.lower().isin(["true", "1", "yes"])
    return df


def attach_states(scores: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    out = scores.copy()
    if "market_state" not in out.columns:
        out["market_state"] = np.nan
    if not states.empty and "market_state" in states.columns:
        out["market_state"] = out["market_state"].where(out["market_state"].notna(), states["market_state"].reindex(out.index))
    out["market_state"] = out["market_state"].ffill().fillna("unknown").astype(str)
    return out


def centered_multiplier(score: pd.Series, max_inc: float, max_red: float) -> pd.Series:
    centered = pd.Series(score, dtype=float).fillna(0.5).clip(0.0, 1.0) - 0.5
    raw = 1.0 + np.where(centered >= 0, centered / 0.5 * max_inc, centered / 0.5 * max_red)
    return pd.Series(raw, index=score.index).clip(1.0 - max_red, 1.0 + max_inc)


def apply_risky_multiplier(base: pd.DataFrame, multiplier: pd.Series) -> pd.DataFrame:
    w = base.copy()
    risky_cols = [c for c in w.columns if c != "BIL"]
    mult = multiplier.reindex(w.index).ffill().fillna(1.0).clip(0.80, 1.10)
    if risky_cols:
        w[risky_cols] = w[risky_cols].mul(mult, axis=0)
    return normalize_to_cash(w)


def apply_offense_and_pressure(
    base: pd.DataFrame,
    offense_multiplier: pd.Series,
    *,
    pressure_multiplier: pd.Series | None = None,
) -> pd.DataFrame:
    w = base.copy()
    offense_cols = [c for c in w.columns if c in OFFENSE]
    if offense_cols:
        mult = offense_multiplier.reindex(w.index).ffill().fillna(1.0).clip(0.80, 1.10)
        w[offense_cols] = w[offense_cols].mul(mult, axis=0)
    if pressure_multiplier is not None:
        pressure_cols = [c for c in w.columns if c in PRESSURE_ASSETS]
        if pressure_cols:
            pm = pressure_multiplier.reindex(w.index).ffill().fillna(1.0).clip(0.85, 1.05)
            w[pressure_cols] = w[pressure_cols].mul(pm, axis=0)
    return normalize_to_cash(w)


def stress_mask(scores: pd.DataFrame) -> pd.Series:
    return scores["market_state"].astype(str).eq("stressed_panic")


def transition_boost_value(level: str) -> float:
    return 0.015 if level == "mild" else 0.03


def deterioration_cut_value(level: str) -> float:
    return 0.03 if level == "mild" else 0.07


def build_variant_weights(
    base: pd.DataFrame,
    scores: pd.DataFrame,
    variant: str,
    *,
    max_inc: float = 0.03,
    max_red: float = 0.07,
    transition_strength: str = "mild",
    deterioration_strength: str = "medium",
) -> pd.DataFrame:
    scores = scores.reindex(base.index).ffill().bfill()
    stress = stress_mask(scores)

    if variant == "c4_regime_multiplier_confidence_offset":
        m = centered_multiplier(scores["combined_market_quality_score"], max_inc, max_red)
        m.loc[stress & (m > 1.0)] = 1.0
        return apply_risky_multiplier(base, m)

    if variant == "c4_offensive_sleeve_budget_offset":
        quality = 0.60 * scores["offense_eligibility_score"] + 0.40 * scores["combined_market_quality_score"]
        m = centered_multiplier(quality, max_inc, max_red)
        m.loc[stress & (m > 1.0)] = 1.0
        return apply_offense_and_pressure(base, m)

    if variant == "c4_transition_aware_rerisk_timing":
        boost = transition_boost_value(transition_strength)
        state = scores["market_state"].astype(str)
        transition_week = state.ne(state.shift(1))
        eligible_state = state.isin(["calm_trend", "neutral_mixed", "recovery_fragile", "recovery_confirmed"])
        strong = (
            transition_week
            & eligible_state
            & (scores["breadth_confidence"] >= 0.60)
            & (scores["transition_quality_score"] >= 0.60)
            & (scores["macro_stress_filter"] >= 0.45)
            & (~stress)
        )
        weak = transition_week & eligible_state & (scores["transition_quality_score"] < 0.45) & (~stress)
        m = pd.Series(1.0, index=base.index)
        m.loc[strong] = 1.0 + min(boost, max_inc)
        m.loc[weak] = 1.0 - min(0.02, max_red)
        return apply_offense_and_pressure(base, m)

    if variant == "c4_deterioration_aware_derisk_timing":
        cut = min(deterioration_cut_value(deterioration_strength), max_red)
        bad = (
            (scores["deterioration_score"] >= 0.65)
            | (scores["macro_stress_filter"] < 0.40)
            | (scores["dollar_pressure_filter"] < 0.35)
        )
        m = pd.Series(1.0, index=base.index)
        m.loc[bad & (~stress)] = 1.0 - cut
        return apply_offense_and_pressure(base, m)

    if variant == "c4_combined_conservative_confidence_modifier":
        quality = (
            0.40 * scores["combined_market_quality_score"]
            + 0.20 * scores["transition_quality_score"]
            + 0.20 * scores["offense_eligibility_score"]
            + 0.20 * (1.0 - scores["deterioration_score"])
        ).clip(0.0, 1.0)
        m = centered_multiplier(quality, max_inc, max_red)
        bad = (scores["deterioration_score"] > 0.68) | (scores["macro_stress_filter"] < 0.35)
        recovery = scores["market_state"].astype(str).isin(["recovery_fragile", "recovery_confirmed"])
        m.loc[stress & (m > 1.0)] = 1.0
        m.loc[bad & (~stress)] = np.minimum(m.loc[bad & (~stress)], 0.97)
        m.loc[recovery & (~bad)] = np.maximum(m.loc[recovery & (~bad)], 0.98)
        pressure = pd.Series(1.0, index=base.index)
        pressure.loc[scores["dollar_pressure_filter"] < 0.35] = 0.97
        return apply_offense_and_pressure(base, m, pressure_multiplier=pressure)

    if variant == "c4_final_bounded_safety_check":
        quality = (
            0.55 * scores["combined_market_quality_score"]
            + 0.25 * scores["transition_quality_score"]
            + 0.20 * (1.0 - scores["deterioration_score"])
        ).clip(0.0, 1.0)
        m = centered_multiplier(quality, min(max_inc, 0.03), min(max_red, 0.05))
        m.loc[stress & (m > 1.0)] = 1.0
        pressure = pd.Series(1.0, index=base.index)
        pressure.loc[scores["dollar_pressure_filter"] < 0.35] = 0.97
        return apply_risky_multiplier(apply_offense_and_pressure(base, pd.Series(1.0, index=base.index), pressure_multiplier=pressure), m)

    raise ValueError(f"Unknown variant {variant}")


def benchmark_paths(
    ggg_weights: pd.DataFrame,
    phase2b_weights: pd.DataFrame,
    next_returns: pd.DataFrame,
) -> dict[str, tuple[pd.DataFrame, pd.DataFrame, str]]:
    paths: dict[str, tuple[pd.DataFrame, pd.DataFrame, str]] = {}
    paths["exact_ggg"] = (
        ggg_weights,
        production_portfolio_path(ggg_weights, next_returns, PRODUCTION_COST_BPS),
        "benchmark_exact_ggg",
    )
    if not phase2b_weights.empty:
        paths["phase2b_pinned"] = (
            phase2b_weights,
            production_portfolio_path(phase2b_weights, next_returns, PRODUCTION_COST_BPS),
            "benchmark_phase2b",
        )
    return paths


def path_to_long(path: pd.DataFrame, variant: str) -> pd.DataFrame:
    out = path.copy()
    out.insert(0, "variant", variant)
    return out


def weights_to_long(weights: pd.DataFrame, variant: str) -> pd.DataFrame:
    out = weights.reset_index().rename(columns={"index": "Date"})
    out.insert(0, "variant", variant)
    return out


def metric_row(
    variant: str,
    insertion_point: str,
    weights: pd.DataFrame,
    path: pd.DataFrame,
    state_detail: pd.DataFrame,
    baseline: dict[str, float] | None = None,
    phase2b: dict[str, float] | None = None,
) -> dict[str, float | str | bool]:
    row: dict[str, float | str | bool] = {"variant": variant, "insertion_point": insertion_point}
    row.update(metrics_from_path(path))
    row.update(exposure_summary(weights))
    holdout_2020 = metrics_from_path(path, start="2020-01-01")
    y2022 = metrics_from_path(path, start="2022-01-01", end="2022-12-31")
    for prefix, metrics in [("holdout_2020", holdout_2020), ("y2022", y2022)]:
        for key in ["ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"]:
            row[f"{prefix}_{key}"] = metrics.get(key, np.nan)

    stress = state_detail[
        state_detail.get("variant", pd.Series(dtype=str)).eq(variant)
        & state_detail.get("market_state", pd.Series(dtype=str)).eq("stressed_panic")
    ]
    if not stress.empty:
        for key in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"]:
            row[f"stressed_panic_{key}"] = float(stress.iloc[0].get(key, np.nan))

    if baseline:
        for key in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "avg_BIL", "avg_SPY", "avg_offense"]:
            if key in row and key in baseline:
                row[f"delta_vs_exact_ggg_{key}"] = float(row[key]) - float(baseline[key])
        row["beat_exact_ggg_sharpe"] = bool(float(row.get("sharpe", np.nan)) >= float(baseline.get("sharpe", np.inf)) + 0.005)
    if phase2b:
        for key in ["ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"]:
            if key in row and key in phase2b:
                row[f"delta_vs_phase2b_{key}"] = float(row[key]) - float(phase2b[key])
    return row


def acceptance_labels(metrics: pd.DataFrame, state_detail: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    base = out[out["variant"].eq("exact_ggg")].iloc[0].to_dict()
    base_stress = state_detail[
        state_detail.get("variant", pd.Series(dtype=str)).eq("exact_ggg")
        & state_detail.get("market_state", pd.Series(dtype=str)).eq("stressed_panic")
    ]
    base_stress_sharpe = float(base_stress.iloc[0].get("sharpe", np.nan)) if not base_stress.empty else np.nan
    base_stress_return = float(base_stress.iloc[0].get("ann_return", np.nan)) if not base_stress.empty else np.nan

    labels = []
    reasons = []
    for _, row in out.iterrows():
        if row["variant"] in ["exact_ggg", "phase2b_pinned"]:
            labels.append("benchmark")
            reasons.append("Benchmark row.")
            continue
        sharpe_gate = float(row["sharpe"]) >= float(base["sharpe"]) + 0.005
        return_gate = (
            float(row["ann_return"]) > float(base["ann_return"])
            and float(row["max_drawdown"]) >= float(base["max_drawdown"]) - 0.005
            and float(row["cvar_5"]) >= float(base["cvar_5"]) - 0.0005
        )
        stress_ok = True
        if np.isfinite(base_stress_sharpe) and "stressed_panic_sharpe" in row:
            stress_ok = float(row.get("stressed_panic_sharpe", np.nan)) >= base_stress_sharpe - 0.02
        if np.isfinite(base_stress_return) and "stressed_panic_ann_return" in row:
            stress_ok = stress_ok and float(row.get("stressed_panic_ann_return", np.nan)) >= base_stress_return - 0.005
        dd_ok = float(row["max_drawdown"]) >= float(base["max_drawdown"]) - 0.005
        cvar_ok = float(row["cvar_5"]) >= float(base["cvar_5"]) - 0.0005
        turnover_ok = float(row["avg_turnover"]) <= float(base["avg_turnover"]) * 1.10 + 0.002
        holdout_ok = float(row["holdout_2020_sharpe"]) >= float(base["holdout_2020_sharpe"]) - 0.02
        hidden_beta_ok = (
            float(row.get("avg_SPY", 0.0)) <= float(base.get("avg_SPY", 0.0)) + 0.01
            and float(row.get("avg_offense", 0.0)) <= float(base.get("avg_offense", 0.0)) + 0.02
        )
        ok = (sharpe_gate or return_gate) and stress_ok and dd_ok and cvar_ok and turnover_ok and holdout_ok and hidden_beta_ok
        labels.append("promising" if ok else "research-only")
        failed = []
        for flag, label in [
            (sharpe_gate or return_gate, "no accepted risk-adjusted improvement"),
            (stress_ok, "stressed_panic not preserved"),
            (dd_ok, "drawdown worse than gate"),
            (cvar_ok, "CVaR worse than gate"),
            (turnover_ok, "turnover too high"),
            (holdout_ok, "2020+ holdout weaker"),
            (hidden_beta_ok, "possible hidden beta/offense increase"),
        ]:
            if not flag:
                failed.append(label)
        reasons.append("Accepted by C5 gate." if ok else "; ".join(failed))
    out["acceptance_verdict"] = labels
    out["acceptance_reason"] = reasons
    return out


def build_all_paths(
    ggg_weights: pd.DataFrame,
    phase2b_weights: pd.DataFrame,
    scores: pd.DataFrame,
    states: pd.DataFrame,
    next_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    path_map = benchmark_paths(ggg_weights, phase2b_weights, next_returns)

    for variant in VARIANT_SPECS:
        w = build_variant_weights(ggg_weights, scores, variant)
        p = production_portfolio_path(w, next_returns, PRODUCTION_COST_BPS)
        path_map[variant] = (w, p, VARIANT_SPECS[variant])

    state_frames = [state_summary(path, states, variant) for variant, (_, path, _) in path_map.items()]
    state_detail = pd.concat([s for s in state_frames if not s.empty], ignore_index=True) if state_frames else pd.DataFrame()

    baseline_row = metric_row("exact_ggg", "benchmark_exact_ggg", path_map["exact_ggg"][0], path_map["exact_ggg"][1], state_detail)
    phase_row = None
    if "phase2b_pinned" in path_map:
        phase_row = metric_row("phase2b_pinned", "benchmark_phase2b", path_map["phase2b_pinned"][0], path_map["phase2b_pinned"][1], state_detail)
    base_dict = baseline_row
    phase_dict = phase_row if phase_row is not None else None

    rows = [baseline_row]
    if phase_row is not None:
        rows.append(phase_row)
    for variant, (weights, path, insertion_point) in path_map.items():
        if variant in ["exact_ggg", "phase2b_pinned"]:
            continue
        rows.append(metric_row(variant, insertion_point, weights, path, state_detail, base_dict, phase_dict))
    metrics = acceptance_labels(pd.DataFrame(rows), state_detail)

    returns = pd.concat([path_to_long(path, variant) for variant, (_, path, _) in path_map.items()], ignore_index=True)
    weights = pd.concat([weights_to_long(w, variant) for variant, (w, _, _) in path_map.items()], ignore_index=True)
    return metrics, state_detail, returns, weights


def run_sensitivity(
    metrics: pd.DataFrame,
    ggg_weights: pd.DataFrame,
    scores: pd.DataFrame,
    states: pd.DataFrame,
    next_returns: pd.DataFrame,
) -> pd.DataFrame:
    non_bench = metrics[~metrics["variant"].isin(["exact_ggg", "phase2b_pinned"])].copy()
    top = non_bench.sort_values(["acceptance_verdict", "sharpe"], ascending=[True, False]).head(3)
    variant_names = top["variant"].tolist()

    rows = []
    for variant in variant_names:
        scenarios = [
            ("base", 0.03, 0.07, "mild", "medium"),
            ("max_inc_0pct", 0.00, 0.07, "mild", "medium"),
            ("max_inc_2pct", 0.02, 0.07, "mild", "medium"),
            ("max_inc_5pct", 0.05, 0.07, "mild", "medium"),
            ("max_red_3pct", 0.03, 0.03, "mild", "mild"),
            ("max_red_5pct", 0.03, 0.05, "mild", "medium"),
            ("transition_medium", 0.03, 0.07, "medium", "medium"),
            ("deterioration_mild", 0.03, 0.07, "mild", "mild"),
        ]
        for scenario, inc, red, transition_level, deterioration_level in scenarios:
            w = build_variant_weights(
                ggg_weights,
                scores,
                variant,
                max_inc=inc,
                max_red=red,
                transition_strength=transition_level,
                deterioration_strength=deterioration_level,
            )
            path = production_portfolio_path(w, next_returns, PRODUCTION_COST_BPS)
            state_detail = state_summary(path, states, variant)
            row = {
                "variant": variant,
                "scenario": scenario,
                "max_offense_increase": inc,
                "max_offense_reduction": red,
                "transition_boost": transition_level,
                "deterioration_cut": deterioration_level,
                **metrics_from_path(path),
                **exposure_summary(w),
                "holdout_2020_sharpe": metrics_from_path(path, start="2020-01-01").get("sharpe", np.nan),
                "y2022_sharpe": metrics_from_path(path, start="2022-01-01", end="2022-12-31").get("sharpe", np.nan),
            }
            stress = state_detail[state_detail.get("market_state", pd.Series(dtype=str)).eq("stressed_panic")]
            row["stressed_panic_sharpe"] = float(stress.iloc[0].get("sharpe", np.nan)) if not stress.empty else np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def write_reports(metrics: pd.DataFrame, state_detail: pd.DataFrame, sensitivity: pd.DataFrame, warnings: list[str]) -> None:
    variants = metrics[~metrics["variant"].isin(["exact_ggg", "phase2b_pinned"])].copy()
    best = variants.sort_values("sharpe", ascending=False).head(1)
    promising = variants[variants["acceptance_verdict"].eq("promising")]
    base = metrics[metrics["variant"].eq("exact_ggg")].head(1)

    lines = [
        "# C4 Native Confidence Insertion Report",
        "",
        "Research-only allocator-native confidence insertion test using exact GGG return alignment and cost plumbing.",
        "",
        "## Variants Tested",
        "",
        md_table(pd.DataFrame([{"variant": k, "insertion_point": v} for k, v in VARIANT_SPECS.items()]), ["variant", "insertion_point"], 20),
        "",
        "## Metrics",
        "",
        md_table(metrics.sort_values("sharpe", ascending=False), ["variant", "insertion_point", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "avg_BIL", "avg_SPY", "avg_offense", "holdout_2020_sharpe", "stressed_panic_sharpe", "acceptance_verdict"], 20),
        "",
        "## Best Variant",
        "",
        md_table(best, ["variant", "insertion_point", "ann_return", "sharpe", "delta_vs_exact_ggg_sharpe", "max_drawdown", "cvar_5", "stressed_panic_sharpe", "acceptance_verdict", "acceptance_reason"], 5),
        "",
        "## State Detail",
        "",
        md_table(state_detail.sort_values(["variant", "market_state"]), ["variant", "market_state", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"], 40),
        "",
        "## Interpretation",
        "",
        f"- Exact GGG baseline row present: {'yes' if not base.empty else 'no'}.",
        f"- Variants passing the strict C5 acceptance gate: {len(promising)}.",
        "- Improvements are treated as research evidence only and are not production promotions.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "c4_native_confidence_insertion_report.md", lines)

    sensitivity_summary = (
        sensitivity.groupby("variant")
        .agg(
            scenarios=("scenario", "count"),
            sharpe_median=("sharpe", "median"),
            sharpe_min=("sharpe", "min"),
            sharpe_max=("sharpe", "max"),
            holdout_2020_sharpe_min=("holdout_2020_sharpe", "min"),
            stressed_panic_sharpe_min=("stressed_panic_sharpe", "min"),
            max_drawdown_min=("max_drawdown", "min"),
            cvar_5_min=("cvar_5", "min"),
        )
        .reset_index()
        if not sensitivity.empty
        else pd.DataFrame()
    )
    lines = [
        "# C6 Native Sensitivity Report",
        "",
        "Small one-at-a-time sensitivity checks for the top three C4 variants. This is not a broad parameter search.",
        "",
        "## Sensitivity Summary",
        "",
        md_table(sensitivity_summary, ["variant", "scenarios", "sharpe_median", "sharpe_min", "sharpe_max", "holdout_2020_sharpe_min", "stressed_panic_sharpe_min", "max_drawdown_min", "cvar_5_min"], 20),
        "",
        "## Scenario Detail",
        "",
        md_table(sensitivity.sort_values(["variant", "sharpe"], ascending=[True, False]), ["variant", "scenario", "max_offense_increase", "max_offense_reduction", "transition_boost", "deterioration_cut", "ann_return", "sharpe", "max_drawdown", "cvar_5", "holdout_2020_sharpe", "stressed_panic_sharpe"], 40),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "c6_native_sensitivity_report.md", lines)

    best_name = str(best.iloc[0]["variant"]) if not best.empty else "none"
    best_beat = bool(best.iloc[0].get("beat_exact_ggg_sharpe", False)) if not best.empty else False
    best_stress_preserved = True
    if not best.empty and "stressed_panic_sharpe" in best.columns and not base.empty:
        base_stress = state_detail[
            state_detail.get("variant", pd.Series(dtype=str)).eq("exact_ggg")
            & state_detail.get("market_state", pd.Series(dtype=str)).eq("stressed_panic")
        ]
        if not base_stress.empty:
            best_stress_preserved = float(best.iloc[0].get("stressed_panic_sharpe", np.nan)) >= float(base_stress.iloc[0].get("sharpe", np.nan)) - 0.02

    next_sprint = (
        "Run a no-write allocator wrapper that inserts the best confidence modifier before final ETF look-through, then compare against this saved-weight proxy."
        if len(promising) > 0
        else "Pause R5 and build a no-write allocator checkpoint wrapper before further signal deployment tests."
    )
    lines = [
        "# C7 Native Confidence Sprint Summary",
        "",
        "## Answers",
        "",
        f"1. Did allocator-native insertion beat exact GGG? {'Yes on the C5 Sharpe gate.' if best_beat else 'No strict C5 Sharpe beat from the best observed variant.'}",
        f"2. Which insertion point worked best? `{best.iloc[0]['insertion_point'] if not best.empty else 'none'}` via `{best_name}`.",
        "3. Did transition-aware re-risking help? See the C4/C6 tables; it is useful only if it ranks near the top without stressing holdout or stressed_panic.",
        "4. Did deterioration-aware de-risking help? See the C4/C6 tables; it is judged by stress preservation and drawdown/CVaR behavior, not standalone IC.",
        f"5. Did confidence modifiers preserve stressed_panic defense? {'Yes for the best variant under the configured tolerance.' if best_stress_preserved else 'No; best variant weakened stressed_panic beyond tolerance.'}",
        "6. Did any improvement survive sensitivity testing? See C6 summary; stable variants should have tight Sharpe range and preserved holdout/stress rows.",
        "7. Is this better than B7/B8 post-hoc pass-through? This test uses exact GGG alignment and one-way turnover, so it is the correct comparison layer.",
        "8. Is R5 still premature? Yes until the insertion point is verified with a no-write allocator wrapper rather than saved-weight proxy modifications.",
        f"9. Exact next sprint: {next_sprint}",
        "10. Production/dashboard files changed: no changes were written by these scripts.",
        "",
        "## Best Rows",
        "",
        md_table(metrics.sort_values("sharpe", ascending=False), ["variant", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "stressed_panic_sharpe", "acceptance_verdict", "acceptance_reason"], 12),
        "",
        "## Sensitivity",
        "",
        md_table(sensitivity_summary, ["variant", "scenarios", "sharpe_median", "sharpe_min", "sharpe_max", "holdout_2020_sharpe_min", "stressed_panic_sharpe_min"], 12),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "c7_native_confidence_sprint_summary.md", lines)


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()
    NATIVE_OUT.mkdir(parents=True, exist_ok=True)

    ggg_weights = load_weights(GGG, warnings)
    phase2b_weights = load_weights(PHASE2B, warnings)
    next_returns = load_next_week_returns(warnings)
    states = load_states(warnings)
    if ggg_weights.empty or next_returns.empty:
        raise SystemExit("Required GGG weights or weekly price-derived returns are missing.")

    scores = attach_states(load_confidence(ggg_weights.index, warnings), states)
    metrics, state_detail, returns, weights = build_all_paths(ggg_weights, phase2b_weights, scores, states, next_returns)
    sensitivity = run_sensitivity(metrics, ggg_weights, scores, states, next_returns)

    metrics.to_csv(NATIVE_OUT / "c4_native_variant_metrics.csv", index=False)
    state_detail.to_csv(NATIVE_OUT / "c4_native_variant_state_summary.csv", index=False)
    returns.to_csv(NATIVE_OUT / "c4_native_variant_returns.csv", index=False)
    weights.to_csv(NATIVE_OUT / "c4_native_variant_weights.csv", index=False)
    sensitivity.to_csv(NATIVE_OUT / "c6_native_sensitivity_results.csv", index=False)

    write_reports(metrics, state_detail, sensitivity, warnings)

    expected = [
        NATIVE_OUT / "c4_native_variant_metrics.csv",
        NATIVE_OUT / "c4_native_variant_state_summary.csv",
        NATIVE_OUT / "c4_native_variant_returns.csv",
        NATIVE_OUT / "c4_native_variant_weights.csv",
        NATIVE_OUT / "c6_native_sensitivity_results.csv",
        DOCS / "c4_native_confidence_insertion_report.md",
        DOCS / "c6_native_sensitivity_report.md",
        DOCS / "c7_native_confidence_sprint_summary.md",
    ]
    missing = [rel(path) for path in expected if not path.exists()]
    if missing:
        warnings.append("Missing expected outputs after write: " + ", ".join(missing))
    best = metrics[~metrics["variant"].isin(["exact_ggg", "phase2b_pinned"])].sort_values("sharpe", ascending=False).head(1)
    print(f"Wrote {rel(NATIVE_OUT / 'c4_native_variant_metrics.csv')} rows={len(metrics)}")
    print(f"Wrote {rel(NATIVE_OUT / 'c6_native_sensitivity_results.csv')} rows={len(sensitivity)}")
    if not best.empty:
        print(
            "Best variant "
            f"{best.iloc[0]['variant']} sharpe={best.iloc[0]['sharpe']:.6f} "
            f"verdict={best.iloc[0]['acceptance_verdict']}"
        )
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
