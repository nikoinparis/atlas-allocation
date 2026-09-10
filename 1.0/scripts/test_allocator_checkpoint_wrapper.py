"""Test no-write allocator checkpoint wrapper against exact GGG."""

from __future__ import annotations

import numpy as np
import pandas as pd

from allocator_checkpoint_wrapper import (
    STABILIZATION_OUT,
    AllocatorCheckpointWrapper,
    exact_rebuild_tolerance_ok,
)
from path1_path3_research_utils import (
    DOCS,
    GGG,
    PRODUCTION_COST_BPS,
    exposure_summary,
    md_table,
    metrics_from_path,
    rel,
    write_text,
)


def write_baseline_doc(wrapper: AllocatorCheckpointWrapper, result_metrics: dict[str, float], compare: dict[str, float]) -> None:
    baseline = pd.DataFrame([{**result_metrics, **compare}])
    checkpoint_summary = wrapper.checkpoint_summary()
    lines = [
        "# Stabilization Exact GGG Baseline",
        "",
        "Research-only baseline lock for future deployment experiments.",
        "",
        f"- Official research baseline: `{GGG}`.",
        "- Return alignment: `weekly_prices.pct_change().shift(-1)` on the allocation decision-date index.",
        "- Weight timing: saved final ETF weights are applied to the next weekly return on the same decision date.",
        "- Turnover method: one-way turnover `0.5 * sum(abs(diff(final_etf_weights)))`.",
        f"- Cost method: one-way turnover times `{PRODUCTION_COST_BPS:.1f}` bps.",
        "- State labels: `data/04_layer2b_risk_regime_engine/market_state_history.csv`.",
        "- Future research must use this baseline because B7/B8 proved that return alignment and turnover conventions can dominate small signal edges.",
        "",
        "## Exact Benchmark Metrics",
        "",
        md_table(baseline, ["ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_turnover", "cost_drag", "avg_BIL", "avg_SPY", "avg_offense", "avg_defense"], 1),
        "",
        "## Exact Match Check",
        "",
        md_table(baseline, ["net_return_corr_vs_saved", "net_return_max_abs_error", "turnover_max_abs_error", "cost_max_abs_error", "weeks_compared"], 1),
        "",
        "## Checkpoint Availability",
        "",
        md_table(checkpoint_summary, ["checkpoint", "source_stage", "available", "rows", "cols", "safe_for_frontier_research", "dangerous_without_allocator_hook"], 20),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in wrapper.warnings] or ["- None."])
    write_text(DOCS / "stabilization_exact_ggg_baseline.md", lines)


def write_design_doc(wrapper: AllocatorCheckpointWrapper) -> None:
    summary = wrapper.checkpoint_summary()
    lines = [
        "# Stabilization Checkpoint Wrapper Design",
        "",
        "Research-only design for a no-write allocator checkpoint wrapper.",
        "",
        "## Wrapper Contract",
        "",
        "- Reads saved production/candidate artifacts and allocator checkpoints.",
        "- Writes only to `data/research/stabilization/` and `docs/research/` through caller scripts.",
        "- Reproduces exact GGG when no modifier is supplied.",
        "- Accepts optional modifier functions that return bounded modifier series.",
        "- Logs checkpoint, modifier bounds, and average weight movement.",
        "- Uses exact GGG return/cost/turnover conventions.",
        "",
        "## Exposed Checkpoints",
        "",
        md_table(summary, ["checkpoint", "source_stage", "available", "safe_for_frontier_research", "dangerous_without_allocator_hook", "source_path"], 20),
        "",
        "## Safe Checkpoints",
        "",
        "- `regime_multipliers`: useful for tiny confidence/risk-budget offsets.",
        "- `offense_budget`: useful for offense eligibility, dollar pressure, and risk-on participation rules.",
        "- `transition_rerisk_smoothing`: useful for controlled re-risk timing research.",
        "- `derisk_smoothing`: useful for deterioration acceleration and stress filters.",
        "- `volatility_risk_overlay`: useful for confidence modifiers that should respect risk overlay intent.",
        "- `final_etf_lookthrough_weights`: safe only as a comparison layer, not preferred for production design.",
        "",
        "## Dangerous Checkpoints",
        "",
        "- `raw_sleeve_targets`: upstream HRP and sleeve construction interactions are not faithfully invertible from saved final weights.",
        "- `defense_budget`: easy to damage stressed_panic defense unless a full sleeve-aware allocator hook is available.",
        "- `cost_turnover_calculation`: should not be modified by signals; it is measurement plumbing.",
        "",
        "## Limitation",
        "",
        "Early checkpoint modifications are represented by conservative final-weight proxy transformations. This stabilizes research comparisons, but a future no-write allocator hook should eventually insert modifiers before ETF look-through.",
    ]
    write_text(DOCS / "stabilization_checkpoint_wrapper_design.md", lines)


def write_test_report(metrics: pd.DataFrame, compare: dict[str, float], success: bool, wrapper: AllocatorCheckpointWrapper) -> None:
    lines = [
        "# Stabilization Checkpoint Wrapper Test Report",
        "",
        f"- No-modifier wrapper reproduces exact GGG: `{success}`.",
        "- This test is required before any future deployment rule harness can be trusted.",
        "",
        "## Rebuild Metrics",
        "",
        md_table(metrics, ["variant", "ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_turnover", "cost_drag", "avg_BIL", "avg_SPY", "avg_offense", "avg_defense"], 5),
        "",
        "## Match Against Saved GGG",
        "",
        md_table(pd.DataFrame([compare]), ["net_return_corr_vs_saved", "gross_return_max_abs_error", "net_return_max_abs_error", "turnover_max_abs_error", "cost_max_abs_error", "weeks_compared"], 1),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in wrapper.warnings] or ["- None."])
    write_text(DOCS / "stabilization_checkpoint_wrapper_test_report.md", lines)


def main() -> None:
    STABILIZATION_OUT.mkdir(parents=True, exist_ok=True)
    wrapper = AllocatorCheckpointWrapper()
    result = wrapper.run("no_modifier_wrapper_rebuild")
    compare = wrapper.compare_to_saved(result.path)
    success = exact_rebuild_tolerance_ok(compare)

    metrics = pd.DataFrame([{**{"variant": result.variant}, **result.metrics, **compare}])
    metrics.to_csv(STABILIZATION_OUT / "checkpoint_wrapper_rebuild_metrics.csv", index=False)
    wrapper.save_result(result, STABILIZATION_OUT)

    write_baseline_doc(wrapper, {**result.metrics, **exposure_summary(result.weights)}, compare)
    write_design_doc(wrapper)
    write_test_report(metrics, compare, success, wrapper)

    print(f"Wrote {rel(STABILIZATION_OUT / 'checkpoint_wrapper_rebuild_metrics.csv')} rows={len(metrics)}")
    print(f"No-modifier exact match: {success}")
    print(f"net_return_max_abs_error={compare.get('net_return_max_abs_error', np.nan):.3e}")
    print(f"net_return_corr_vs_saved={compare.get('net_return_corr_vs_saved', np.nan):.10f}")
    if not success:
        raise SystemExit("No-modifier wrapper failed exact GGG tolerance; stop and diagnose.")


if __name__ == "__main__":
    main()
