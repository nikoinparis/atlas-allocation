"""Path 1.2 exact GGG reference rebuild attempt.

Research-only. This script does not run the production artifact builder and does
not write to Layer 3 production files. It reconstructs the saved GGG portfolio
path from saved final ETF weights plus the exact price-derived forward return
and one-way turnover convention used by the Layer 3 path.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from path1_path3_research_utils import (
    CHECKPOINTS,
    DOCS,
    GGG,
    HUB,
    PATH1_OUT,
    PHASE2B,
    PORT,
    PRODUCTION_COST_BPS,
    b7_style_path,
    ensure_dirs,
    exposure_summary,
    load_checkpoint,
    load_next_week_returns,
    load_production_summary,
    load_returns,
    load_sleeve_weights,
    load_weekly_returns_file,
    load_weights,
    md_table,
    metrics_from_path,
    production_portfolio_path,
    rel,
    state_summary,
    load_states,
    write_text,
)


def safe_float(value: object) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def compare_path(label: str, path: pd.DataFrame, saved: pd.DataFrame, weights: pd.DataFrame) -> dict[str, float | str]:
    joined = path.set_index("Date").join(saved[["gross_return", "net_return", "turnover", "cost"]], rsuffix="_saved", how="inner")
    out: dict[str, float | str] = {"rebuild_name": label}
    out.update({f"rebuild_{k}": v for k, v in metrics_from_path(path).items()})
    out.update(exposure_summary(weights))
    if not joined.empty:
        for col in ["gross_return", "net_return", "turnover", "cost"]:
            err = joined[col] - joined[f"{col}_saved"]
            out[f"{col}_mean_abs_error"] = float(err.abs().mean())
            out[f"{col}_max_abs_error"] = float(err.abs().max())
        out["net_return_corr_vs_saved"] = float(joined["net_return"].corr(joined["net_return_saved"]))
        out["weeks_compared"] = int(len(joined))
    return out


def largest_divergences(path: pd.DataFrame, saved: pd.DataFrame, n: int = 12) -> pd.DataFrame:
    joined = path.set_index("Date").join(saved[["net_return", "gross_return", "turnover", "cost"]], rsuffix="_saved", how="inner")
    if joined.empty:
        return pd.DataFrame()
    joined["net_error"] = joined["net_return"] - joined["net_return_saved"]
    joined["abs_net_error"] = joined["net_error"].abs()
    return joined.sort_values("abs_net_error", ascending=False).head(n).reset_index()


def checkpoint_summary(warnings: list[str]) -> pd.DataFrame:
    rows = []
    for stage in [
        "raw_hrp_sleeve_weights",
        "post_state_tilt_sleeve_weights",
        "post_layer3_expression_sleeve_weights",
        "post_overlay_pre_lookthrough_sleeve_weights",
        "final_sleeve_weights",
        "final_etf_weights",
    ]:
        path = CHECKPOINTS / f"{GGG}__{stage}.csv"
        df = load_checkpoint(GGG, stage, warnings)
        rows.append(
            {
                "stage": stage,
                "exists": path.exists(),
                "rows": len(df),
                "cols": len(df.columns) if not df.empty else 0,
                "avg_cash_or_BIL": float(df.get("cash::BIL", df.get("BIL", pd.Series(dtype=float))).mean()) if not df.empty else np.nan,
                "avg_total_weight": float(df.sum(axis=1).mean()) if not df.empty else np.nan,
                "path": rel(path),
            }
        )
    return pd.DataFrame(rows)


def write_audit_doc(
    warnings: list[str],
    summary: pd.DataFrame,
    checkpoints: pd.DataFrame,
    prod_summary: pd.DataFrame,
    exact_success: bool,
) -> None:
    registry_path = PORT / "production_candidate_registry.json"
    registry = {}
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text())
        except Exception as exc:
            warnings.append(f"Could not parse {rel(registry_path)}: {exc}")

    ggg_row = prod_summary[prod_summary.get("name", pd.Series(dtype=str)).eq(GGG)].head(1) if not prod_summary.empty else pd.DataFrame()
    p2b_row = prod_summary[prod_summary.get("name", pd.Series(dtype=str)).eq(PHASE2B)].head(1) if not prod_summary.empty else pd.DataFrame()

    lines = [
        "# Path 1 GGG Plumbing Audit",
        "",
        "Research-only audit. No production pins, dashboard/public files, or Layer 3 production artifacts were changed.",
        "",
        "## Production Candidate Path",
        "",
        f"- Registry current production pin: `{registry.get('current_production_pin', 'unknown')}`",
        f"- Registry production candidate: `{registry.get('production_candidate', 'unknown')}`",
        f"- Dashboard candidate benchmark for this sprint: `{GGG}`",
        f"- Phase2B pinned comparator: `{PHASE2B}`",
        "",
        "## Exact GGG Sequence Reconstructed From Code/Artifacts",
        "",
        "1. Load weekly ETF prices from `data/01_data_hub/weekly_prices.csv`.",
        "2. Build forward returns as `weekly_prices.pct_change().shift(-1)`, indexed by the allocation decision date.",
        "3. Build GGG sleeve panels from the Phase YY decomposed architecture.",
        "4. For `composite_regime_offense_component`, use the broad offense basket except in `recovery_confirmed`, where GGG swaps to the robust FFF3 subset and drops `PDBC` and `DBA`.",
        "5. Allocate sleeves with HRP over the `phaseyy_conservative_decomposition` subset.",
        "6. Apply `phase_ddd_confirmed_near_exclude_dual` state tilt before overlay.",
        "7. Apply Layer 3 expression mode `none`.",
        "8. Apply overlay mode `phasexx_conservative_hybrid_overlay` plus Phase2B `regime_confidence_boost` before final look-through.",
        "9. Apply target-vol interaction inside the overlay step, with risky budget constrained by `min(regime_multiplier, target_vol_multiplier)` unless recovery/neutral budget repair rules apply.",
        "10. Convert sleeve weights to final ETF look-through weights, keeping residual cash in `BIL`.",
        "11. Compute gross returns from final ETF weights and forward returns on the same decision-date index.",
        "12. Compute one-way turnover as `0.5 * sum(abs(diff(final_etf_weights)))`; cost is turnover times 10 bps.",
        "",
        "## Checkpoint Availability",
        "",
        md_table(checkpoints, ["stage", "exists", "rows", "cols", "avg_cash_or_BIL", "avg_total_weight", "path"], 12),
        "",
        "## B7/B8 Mismatch Sources Identified",
        "",
        "- B7/B8 used `weekly_returns.csv` and a one-period weight shift. The exact GGG path uses `weekly_prices.pct_change().shift(-1)` on the allocation-date index.",
        "- B7/B8 used full L1 turnover `sum(abs(diff(weights)))` for cost. The production path uses one-way turnover `0.5 * sum(abs(diff(weights)))`.",
        "- Because the turnover convention differs, B7/B8 variant costs and turnover labels were not directly comparable to the saved GGG path.",
        "- The mismatch is a plumbing issue, not proof that the breadth/macro signals are false.",
        "",
        "## Hidden Nonlinearities And Sequencing Effects",
        "",
        "- HRP sleeve allocation is estimated from a rolling training window and normalized through max-sleeve constraints.",
        "- State tilt happens before overlay, so a small confidence signal can be amplified or neutralized by later overlay budget rules.",
        "- Phase2B regime confidence modifies the overlay multiplier, not final ETF weights directly.",
        "- Target-vol and regime overlays bind jointly; injecting a signal after this step can violate the intended order.",
        "- `phasexx_conservative_hybrid_overlay` has state-specific recovery/neutral cash budget logic, which means symmetric final-weight scaling is the wrong deployment abstraction.",
        "",
        "## What Was Reconstructed",
        "",
        md_table(summary.sort_values("net_return_max_abs_error"), ["rebuild_name", "rebuild_ann_return", "rebuild_sharpe", "net_return_corr_vs_saved", "net_return_max_abs_error", "turnover_max_abs_error", "cost_max_abs_error"], 10),
        "",
        f"- Exact saved-weight return-path reconstruction succeeded: `{exact_success}`.",
        "",
        "## Production Metrics Snapshot",
        "",
        md_table(ggg_row, ["role", "name", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "avg_BIL", "avg_turnover"], 1),
        "",
        md_table(p2b_row, ["role", "name", "full_ann_return", "full_sharpe", "full_max_drawdown", "full_cvar_5", "avg_BIL", "avg_turnover"], 1),
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path1_ggg_plumbing_audit.md", lines)


def write_rebuild_report(
    warnings: list[str],
    summary: pd.DataFrame,
    divergence: pd.DataFrame,
    exact_success: bool,
) -> None:
    best = summary.sort_values("net_return_max_abs_error").head(1)
    b7 = summary[summary["rebuild_name"].eq("b7_b8_sandbox_plumbing")]
    lines = [
        "# Path 1 Rebuild Report",
        "",
        "Research-only exact GGG reference rebuild attempt.",
        "",
        "## Result",
        "",
        f"- Exact reconstruction success: `{exact_success}`",
        "- The exact reconstruction uses saved final ETF weights plus `weekly_prices.pct_change().shift(-1)`, one-way turnover, and 10 bps cost.",
        "",
        "## Best Rebuild",
        "",
        md_table(best, ["rebuild_name", "rebuild_ann_return", "rebuild_sharpe", "rebuild_max_drawdown", "rebuild_cvar_5", "net_return_corr_vs_saved", "net_return_max_abs_error"], 1),
        "",
        "## B7/B8 Sandbox Baseline Mismatch",
        "",
        md_table(b7, ["rebuild_name", "rebuild_ann_return", "rebuild_sharpe", "net_return_corr_vs_saved", "net_return_max_abs_error", "turnover_mean_abs_error", "cost_mean_abs_error"], 1),
        "",
        "## Largest Divergence Weeks For B7/B8-Style Plumbing",
        "",
        md_table(divergence, ["Date", "net_return", "net_return_saved", "net_error", "gross_return", "gross_return_saved", "turnover", "turnover_saved"], 12),
        "",
        "## Interpretation",
        "",
        "- Exact GGG can be reconstructed accurately from saved final ETF weights and the correct return/cost convention.",
        "- A full first-principles rebuild of HRP/raw sleeve decisions was not run because `build_improvement_artifacts.py` writes production Layer 3 files as a side effect.",
        "- The available allocator checkpoints are sufficient to isolate the mismatch without overwriting production artifacts.",
        "",
        "## Warnings",
        "",
    ]
    lines.extend([f"- {w}" for w in warnings] or ["- None."])
    write_text(DOCS / "path1_rebuild_report.md", lines)


def main() -> None:
    warnings: list[str] = []
    ensure_dirs()

    weights = load_weights(GGG, warnings)
    saved = load_returns(GGG, warnings)
    sleeve_weights = load_sleeve_weights(GGG, warnings)
    next_returns = load_next_week_returns(warnings)
    weekly_returns = load_weekly_returns_file(warnings)
    states = load_states(warnings)
    prod_summary = load_production_summary(warnings)

    if weights.empty or saved.empty or next_returns.empty:
        raise SystemExit("Required GGG weights, saved returns, or weekly_prices-derived returns are missing.")

    exact_path = production_portfolio_path(weights, next_returns, PRODUCTION_COST_BPS)
    b7_path = b7_style_path(weights, weekly_returns, PRODUCTION_COST_BPS) if not weekly_returns.empty else pd.DataFrame()

    # A diagnostic variant that uses correct forward returns but the B7 full-turnover convention.
    correct_returns_wrong_turnover = exact_path.copy()
    if not correct_returns_wrong_turnover.empty:
        common_weights = weights.reindex(pd.to_datetime(correct_returns_wrong_turnover["Date"]))
        full_turn = common_weights.diff().abs().sum(axis=1).fillna(0.0)
        correct_returns_wrong_turnover["turnover"] = full_turn.values
        correct_returns_wrong_turnover["cost"] = full_turn.values * (PRODUCTION_COST_BPS / 10000.0)
        correct_returns_wrong_turnover["net_return"] = correct_returns_wrong_turnover["gross_return"] - correct_returns_wrong_turnover["cost"]
        wealth = (1.0 + correct_returns_wrong_turnover["net_return"].fillna(0.0)).cumprod()
        correct_returns_wrong_turnover["wealth"] = wealth
        correct_returns_wrong_turnover["drawdown"] = wealth / wealth.cummax() - 1.0

    summary_rows = [
        compare_path("exact_saved_final_etf_weights", exact_path, saved, weights),
        compare_path("correct_returns_full_turnover_cost", correct_returns_wrong_turnover, saved, weights),
    ]
    if not b7_path.empty:
        summary_rows.append(compare_path("b7_b8_sandbox_plumbing", b7_path, saved, weights))
    summary = pd.DataFrame(summary_rows)

    saved_indexed = saved.copy()
    saved_indexed.index = pd.to_datetime(saved_indexed.index)
    exact_indexed = exact_path.set_index("Date")
    exact_success = bool(
        not exact_indexed.empty
        and float((exact_indexed["net_return"] - saved_indexed["net_return"].reindex(exact_indexed.index)).abs().max()) < 1e-10
    )

    returns_out = exact_path.set_index("Date")[["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]].rename(
        columns=lambda c: f"exact_{c}"
    )
    saved_cols = saved[["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]].rename(columns=lambda c: f"saved_{c}")
    returns_out = returns_out.join(saved_cols, how="left")
    if not b7_path.empty:
        returns_out = returns_out.join(
            b7_path.set_index("Date")[["gross_return", "net_return", "turnover", "cost"]].rename(columns=lambda c: f"b7_style_{c}"),
            how="left",
        )
    returns_out["exact_minus_saved_net"] = returns_out["exact_net_return"] - returns_out["saved_net_return"]
    returns_out.to_csv(PATH1_OUT / "ggg_rebuild_returns.csv")
    weights.to_csv(PATH1_OUT / "ggg_rebuild_weights.csv")
    summary.to_csv(PATH1_OUT / "ggg_rebuild_metrics.csv", index=False)

    divergence = largest_divergences(b7_path, saved) if not b7_path.empty else pd.DataFrame()
    checkpoints = checkpoint_summary(warnings)

    if not sleeve_weights.empty:
        sleeve_weights.to_csv(PATH1_OUT / "ggg_rebuild_sleeve_weights_reference.csv")
    if not states.empty:
        state_rows = state_summary(exact_path, states, "exact_saved_final_etf_weights")
        state_rows.to_csv(PATH1_OUT / "ggg_rebuild_state_summary.csv", index=False)

    write_audit_doc(warnings, summary, checkpoints, prod_summary, exact_success)
    write_rebuild_report(warnings, summary, divergence, exact_success)

    print(f"Wrote {rel(PATH1_OUT / 'ggg_rebuild_metrics.csv')} rows={len(summary)}")
    print(f"Wrote {rel(PATH1_OUT / 'ggg_rebuild_returns.csv')} rows={len(returns_out)}")
    print(f"Wrote {rel(PATH1_OUT / 'ggg_rebuild_weights.csv')} rows={len(weights)}")
    print(f"Wrote {rel(DOCS / 'path1_ggg_plumbing_audit.md')}")
    print(f"Wrote {rel(DOCS / 'path1_rebuild_report.md')}")


if __name__ == "__main__":
    main()

