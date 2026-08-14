"""Standardized deployment rule harness for stabilized research architecture."""

from __future__ import annotations

import numpy as np
import pandas as pd

from allocator_checkpoint_wrapper import (
    STABILIZATION_OUT,
    AllocatorCheckpointWrapper,
    CheckpointModifier,
    exact_rebuild_tolerance_ok,
)
from deployment_rule_library import RULE_REGISTRY, load_confidence_inputs, rule_summary
from path1_path3_research_utils import DOCS, md_table, metrics_from_path, rel, state_summary, write_text


HARNESS_TESTS = [
    ("no_modifier_baseline", None),
    ("offense_eligibility_at_offense_budget", "offense_eligibility"),
    ("breadth_confirmation_at_regime_multiplier", "breadth_confirmation"),
    ("transition_quality_rerisk_at_smoothing", "transition_quality_rerisk"),
    ("deterioration_acceleration_at_derisk", "deterioration_acceleration"),
    ("dollar_pressure_at_offense_budget", "dollar_pressure"),
    ("macro_stress_at_regime_multiplier", "macro_stress"),
    ("combined_conservative_at_overlay", "combined_conservative"),
]


def make_modifier(rule_name: str, inputs: pd.DataFrame) -> CheckpointModifier:
    spec = RULE_REGISTRY[rule_name]

    def _fn(_wrapper: AllocatorCheckpointWrapper, _checkpoint: str) -> pd.Series:
        return spec["function"](inputs)

    return CheckpointModifier(name=rule_name, checkpoint=str(spec["checkpoint"]), function=_fn)


def path_to_long(path: pd.DataFrame, variant: str) -> pd.DataFrame:
    out = path.copy()
    out.insert(0, "variant", variant)
    return out


def stress_metrics(state_detail: pd.DataFrame, variant: str) -> dict[str, float]:
    row = state_detail[
        state_detail.get("variant", pd.Series(dtype=str)).eq(variant)
        & state_detail.get("market_state", pd.Series(dtype=str)).eq("stressed_panic")
    ]
    if row.empty:
        return {}
    return {
        "stressed_panic_ann_return": float(row.iloc[0].get("ann_return", np.nan)),
        "stressed_panic_sharpe": float(row.iloc[0].get("sharpe", np.nan)),
        "stressed_panic_max_drawdown": float(row.iloc[0].get("max_drawdown", np.nan)),
        "stressed_panic_cvar_5": float(row.iloc[0].get("cvar_5", np.nan)),
    }


def metric_row(
    variant: str,
    rule_name: str,
    checkpoint: str,
    result_path: pd.DataFrame,
    result_metrics: dict[str, float],
    state_detail: pd.DataFrame,
    baseline: dict[str, float] | None = None,
) -> dict[str, float | str | bool]:
    row: dict[str, float | str | bool] = {
        "variant": variant,
        "rule": rule_name,
        "checkpoint": checkpoint,
        **result_metrics,
    }
    row.update({f"holdout_2020_{k}": v for k, v in metrics_from_path(result_path, start="2020-01-01").items()})
    row.update({f"y2022_{k}": v for k, v in metrics_from_path(result_path, start="2022-01-01", end="2022-12-31").items()})
    row.update(stress_metrics(state_detail, variant))
    if baseline:
        for key in ["ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_turnover", "cost_drag", "avg_BIL", "avg_offense", "avg_defense"]:
            if key in row and key in baseline:
                row[f"delta_vs_exact_ggg_{key}"] = float(row[key]) - float(baseline[key])
    return row


def architecture_verdict(metrics: pd.DataFrame, state_detail: pd.DataFrame) -> pd.DataFrame:
    out = metrics.copy()
    base = out[out["variant"].eq("no_modifier_baseline")].head(1)
    if base.empty:
        out["architecture_valid"] = False
        out["architecture_reason"] = "No baseline row."
        return out
    base_row = base.iloc[0]
    base_stress = stress_metrics(state_detail, "no_modifier_baseline")
    verdicts = []
    reasons = []
    for _, row in out.iterrows():
        if row["variant"] == "no_modifier_baseline":
            verdicts.append(True)
            reasons.append("Exact no-modifier baseline.")
            continue
        finite_metrics = np.isfinite(float(row.get("sharpe", np.nan))) and np.isfinite(float(row.get("max_drawdown", np.nan)))
        stress_ok = True
        if base_stress:
            stress_ok = (
                float(row.get("stressed_panic_sharpe", np.nan)) >= base_stress.get("stressed_panic_sharpe", np.nan) - 0.03
                and float(row.get("stressed_panic_max_drawdown", np.nan)) >= base_stress.get("stressed_panic_max_drawdown", np.nan) - 0.005
            )
        turnover_ok = float(row.get("avg_turnover", np.inf)) <= float(base_row.get("avg_turnover", np.inf)) * 1.15 + 0.002
        consistent = abs(float(row.get("n_weeks", 0)) - float(base_row.get("n_weeks", 0))) <= 1
        ok = bool(finite_metrics and stress_ok and turnover_ok and consistent)
        verdicts.append(ok)
        failed = []
        if not finite_metrics:
            failed.append("missing metrics")
        if not stress_ok:
            failed.append("stressed_panic not preserved")
        if not turnover_ok:
            failed.append("turnover not controlled")
        if not consistent:
            failed.append("week count mismatch")
        reasons.append("Architecture-valid." if ok else "; ".join(failed))
    out["architecture_valid"] = verdicts
    out["architecture_reason"] = reasons
    return out


def write_rule_library_doc() -> None:
    rows = rule_summary()
    lines = [
        "# Stabilization Deployment Rule Library",
        "",
        "Research-only rule library for future deployment tests.",
        "",
        "## Contract",
        "",
        "- Rules return bounded modifier series; they do not write weights or production files.",
        "- Rules use C3 one-week-lagged confidence inputs by default.",
        "- Parameters are conservative and explicit.",
        "- Each rule declares an intended checkpoint so future tests avoid ad hoc injection.",
        "",
        "## Rules",
        "",
        md_table(rows, ["rule", "intended_checkpoint", "bounded", "lagged_inputs", "description"], 20),
        "",
        "## Usage Guidance",
        "",
        "- Use `offense_budget` for eligibility, dollar pressure, and risk-on participation.",
        "- Use `regime_multipliers` or `volatility_risk_overlay` for broad confidence/risk-budget changes.",
        "- Use `transition_rerisk_smoothing` and `derisk_smoothing` for asymmetric timing research.",
        "- Treat `final_etf_lookthrough_weights` as a comparison layer, not the preferred architecture.",
    ]
    write_text(DOCS / "stabilization_deployment_rule_library.md", lines)


def write_harness_report(metrics: pd.DataFrame, state_detail: pd.DataFrame, compare: dict[str, float], logs: pd.DataFrame, warnings: list[str]) -> None:
    lines = [
        "# Stabilization Rule Harness Report",
        "",
        "Research-only standardized test suite over the no-write checkpoint wrapper and deployment rule library.",
        "",
        "## Exact Baseline Check",
        "",
        md_table(pd.DataFrame([compare]), ["net_return_corr_vs_saved", "net_return_max_abs_error", "turnover_max_abs_error", "cost_max_abs_error", "weeks_compared"], 1),
        "",
        "## Harness Results",
        "",
        md_table(metrics.sort_values("sharpe", ascending=False), ["variant", "rule", "checkpoint", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "avg_BIL", "avg_offense", "holdout_2020_sharpe", "y2022_sharpe", "stressed_panic_sharpe", "architecture_valid"], 20),
        "",
        "## State Summary",
        "",
        md_table(state_detail.sort_values(["variant", "market_state"]), ["variant", "market_state", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover"], 60),
        "",
        "## Modifier Logs",
        "",
        md_table(logs, ["variant", "modifier", "checkpoint", "modifier_min", "modifier_mean", "modifier_max", "avg_abs_weight_change", "max_abs_weight_change"], 30),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "stabilization_rule_harness_report.md", lines)


def write_summary(metrics: pd.DataFrame, wrapper: AllocatorCheckpointWrapper, compare: dict[str, float], warnings: list[str]) -> None:
    checkpoints = wrapper.checkpoint_summary()
    valid = metrics[metrics["architecture_valid"] & ~metrics["variant"].eq("no_modifier_baseline")]
    invalid = metrics[~metrics["architecture_valid"]]
    stable = exact_rebuild_tolerance_ok(compare) and not valid.empty
    safe = checkpoints[checkpoints["safe_for_frontier_research"]]
    dangerous = checkpoints[checkpoints["dangerous_without_allocator_hook"]]
    lines = [
        "# Deployment Architecture Stabilization Summary",
        "",
        "## Answers",
        "",
        f"1. Does the wrapper reproduce exact GGG? `{exact_rebuild_tolerance_ok(compare)}`.",
        "2. Safe checkpoints for future research: `regime_multipliers`, `offense_budget`, `cash_bil_budget`, `transition_rerisk_smoothing`, `derisk_smoothing`, `volatility_risk_overlay`, and `final_etf_lookthrough_weights` for comparison only.",
        "3. Dangerous checkpoints: `raw_sleeve_targets`, `defense_budget`, and `cost_turnover_calculation` without a deeper allocator hook.",
        f"4. Architecture-valid rules: {', '.join(valid['rule'].astype(str).tolist()) if not valid.empty else 'none'}.",
        "5. Use future rules at offense, regime/overlay, transition, and de-risk checkpoints before any ensemble work.",
        f"6. Stable enough for frontier research: `{stable}`.",
        "7. Exact next sprint: allocator-native transition-quality/re-risk model using this wrapper and no-write allocator checkpoint logs.",
        "8. Production/dashboard files changed: no scripts in this sprint write those paths.",
        "",
        "## Safe Checkpoints",
        "",
        md_table(safe, ["checkpoint", "source_stage", "available", "rows", "cols"], 20),
        "",
        "## Dangerous Checkpoints",
        "",
        md_table(dangerous, ["checkpoint", "source_stage", "available", "rows", "cols"], 20),
        "",
        "## Rule Results",
        "",
        md_table(metrics.sort_values("sharpe", ascending=False), ["variant", "rule", "checkpoint", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "stressed_panic_sharpe", "architecture_valid", "architecture_reason"], 20),
        "",
        "## Invalid Rules",
        "",
        md_table(invalid, ["variant", "rule", "checkpoint", "architecture_reason"], 20),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "deployment_architecture_stabilization_summary.md", lines)


def write_frontier_backlog() -> None:
    rows = [
        {"rank": 1, "frontier": "allocator-native confidence architecture", "expected_upside": "high", "why": "Near-miss native confidence tests suggest deployment location matters.", "next_action": "Test inside wrapper at overlay/offense checkpoints."},
        {"rank": 2, "frontier": "transition-quality/re-risk model", "expected_upside": "high", "why": "Could improve participation without weakening stressed_panic.", "next_action": "Build transition-specific diagnostics and timing rules."},
        {"rank": 3, "frontier": "PIT breadth when budget exists", "expected_upside": "high", "why": "ETF breadth is useful but coarse; stock-level PIT breadth may reduce false signals.", "next_action": "Scope Norgate/Sharadar/WRDS data requirements."},
        {"rank": 4, "frontier": "broader ETF/stock universe", "expected_upside": "medium-high", "why": "More breadth and leadership information may improve participation quality.", "next_action": "Add research-only universe feasibility audit."},
        {"rank": 5, "frontier": "cross-sectional attention/ranker", "expected_upside": "medium", "why": "Useful only after deployment plumbing is stable.", "next_action": "Keep research-only and benchmark against simple rankers."},
        {"rank": 6, "frontier": "decision-focused portfolio learning", "expected_upside": "medium", "why": "Can overfit; may help only with stable allocator wrapper.", "next_action": "Delay until simple confidence deployment is exhausted."},
        {"rank": 7, "frontier": "causal regime classifier", "expected_upside": "medium", "why": "Could improve transition quality but needs strict leakage controls.", "next_action": "Design labels and embargo rules first."},
        {"rank": 8, "frontier": "active sleeve specialization", "expected_upside": "medium", "why": "Allows targeted improvements without global weight scaling.", "next_action": "Map sleeve-specific failure modes."},
        {"rank": 9, "frontier": "stock overlay or stock breadth proxy", "expected_upside": "medium", "why": "Could improve breadth signal quality but increases data complexity.", "next_action": "Only with PIT or clearly documented survivorship limits."},
        {"rank": 10, "frontier": "frontier ML", "expected_upside": "uncertain", "why": "High overfitting risk before deployment architecture is mature.", "next_action": "Defer until wrapper-based tests are stable."},
    ]
    df = pd.DataFrame(rows)
    lines = [
        "# Frontier Research Backlog After Stabilization",
        "",
        "Ranked by expected upside under the current evidence and feasibility constraints.",
        "",
        md_table(df, ["rank", "frontier", "expected_upside", "why", "next_action"], 20),
    ]
    write_text(DOCS / "frontier_research_backlog_after_stabilization.md", lines)


def main() -> None:
    STABILIZATION_OUT.mkdir(parents=True, exist_ok=True)
    wrapper = AllocatorCheckpointWrapper()
    inputs = load_confidence_inputs(wrapper.index, already_lagged=True)

    results = []
    returns = []
    state_frames = []
    logs = []
    path_map: dict[str, pd.DataFrame] = {}

    baseline_result = wrapper.run("no_modifier_baseline")
    compare = wrapper.compare_to_saved(baseline_result.path)
    if not exact_rebuild_tolerance_ok(compare):
        raise SystemExit("Wrapper baseline failed exact GGG tolerance; stop and diagnose before running harness.")

    for variant, rule_name in HARNESS_TESTS:
        if rule_name is None:
            result = baseline_result
            checkpoint = "none"
            rule_label = "none"
        else:
            modifier = make_modifier(rule_name, inputs)
            result = wrapper.run(variant, [modifier])
            checkpoint = modifier.checkpoint
            rule_label = rule_name
        state = state_summary(result.path, wrapper.states, variant)
        state_frames.append(state)
        returns.append(path_to_long(result.path, variant))
        path_map[variant] = result.path
        if not result.log.empty:
            logs.append(result.log)
        results.append(metric_row(variant, rule_label, checkpoint, result.path, result.metrics, state))

    state_detail = pd.concat([s for s in state_frames if not s.empty], ignore_index=True)
    metrics = pd.DataFrame(results)
    baseline_row = metrics[metrics["variant"].eq("no_modifier_baseline")].iloc[0].to_dict()
    metric_rows = []
    for _, row in metrics.iterrows():
        variant_name = str(row["variant"])
        metric_rows.append(
            metric_row(
                variant_name,
                str(row["rule"]),
                str(row["checkpoint"]),
                path_map[variant_name],
                row.to_dict(),
                state_detail,
                baseline_row,
            )
        )
    metrics = architecture_verdict(pd.DataFrame(metric_rows), state_detail)
    returns_df = pd.concat(returns, ignore_index=True)
    logs_df = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame()

    metrics.to_csv(STABILIZATION_OUT / "rule_harness_results.csv", index=False)
    state_detail.to_csv(STABILIZATION_OUT / "rule_harness_state_summary.csv", index=False)
    returns_df.to_csv(STABILIZATION_OUT / "rule_harness_returns.csv", index=False)

    write_rule_library_doc()
    write_harness_report(metrics, state_detail, compare, logs_df, wrapper.warnings)
    write_summary(metrics, wrapper, compare, wrapper.warnings)
    write_frontier_backlog()

    print(f"Wrote {rel(STABILIZATION_OUT / 'rule_harness_results.csv')} rows={len(metrics)}")
    print(f"Wrote {rel(STABILIZATION_OUT / 'rule_harness_state_summary.csv')} rows={len(state_detail)}")
    print(f"Wrote {rel(STABILIZATION_OUT / 'rule_harness_returns.csv')} rows={len(returns_df)}")
    print(f"Architecture-valid rules={int(metrics['architecture_valid'].sum()) - 1}")


if __name__ == "__main__":
    main()
