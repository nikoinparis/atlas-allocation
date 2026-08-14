#!/usr/bin/env python3
"""Audit the V1 GGG base strategy's mechanics, checkpoints, and selection lineage."""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
PROGRAM = ROOT / "config/v1_ggg_lineage_audit_v1.json"
OUTPUT = ROOT / "evidence/v1_ggg_lineage_batch_42"
PORT = V1 / "data/05_layer3_portfolio_construction"
CHECKPOINTS = V1 / "data/research/allocator_checkpoints"
NAME = "improved_phaseggg_confirmed_only_robust_offense"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dated(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "date" if "date" in frame else "Date" if "Date" in frame else str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=[date_column]).sort_values(date_column).set_index(date_column)


def portfolio_path(weights: pd.DataFrame, prices: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    forward_returns = prices.apply(pd.to_numeric, errors="coerce").pct_change().shift(-1)
    index = weights.index.intersection(forward_returns.index)
    columns = [column for column in weights if column in forward_returns]
    applied = weights.reindex(index=index, columns=columns).fillna(0.0)
    realized = forward_returns.reindex(index=index, columns=columns).fillna(0.0)
    gross = (applied * realized).sum(axis=1)
    turnover = 0.5 * applied.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame({
        "gross_return": gross, "net_return": net, "turnover": turnover,
        "cost": cost, "wealth": wealth, "drawdown": drawdown,
    })


def metrics(series: pd.Series) -> dict[str, float | int | str]:
    returns = pd.to_numeric(series, errors="coerce").dropna()
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years > 0 else float("nan")
    ann_return = float(returns.mean() * 52.0)
    ann_vol = float(returns.std(ddof=1) * np.sqrt(52.0))
    sharpe = ann_return / ann_vol if ann_vol > 0 else float("nan")
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "weeks": int(len(returns)), "cagr": cagr, "arithmetic_ann_return": ann_return,
        "ann_vol": ann_vol, "sharpe_zero_rf": sharpe,
        "max_drawdown": float(drawdown.min()),
    }


def allocator_catalog() -> tuple[pd.DataFrame, int, int]:
    source = V1 / "scripts/build_improvement_artifacts.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "version_specs" for target in targets):
            continue
        if not isinstance(node.value, ast.List):
            continue
        for element in node.value.elts:
            name = ""
            if isinstance(element, ast.Dict):
                for key, value in zip(element.keys, element.values):
                    if isinstance(key, ast.Constant) and key.value == "version_name" and isinstance(value, ast.Constant):
                        name = str(value.value)
            names.append(name)
        break
    frame = pd.DataFrame({"catalog_position_one_based": range(1, len(names) + 1), "version_name": names})
    target = frame.index[frame["version_name"].eq(NAME)]
    position = int(target[0] + 1) if len(target) else -1
    return frame, len(names), position


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    weights_path = PORT / f"portfolio_version_weights_{NAME}.csv"
    saved_path_file = PORT / f"portfolio_version_returns_{NAME}.csv"
    prices_path = V1 / "data/01_data_hub/weekly_prices.csv"
    selection_path = PORT / "phase_ggg_selection_table.csv"
    weights = read_dated(weights_path).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    saved = read_dated(saved_path_file).apply(pd.to_numeric, errors="coerce")
    prices = read_dated(prices_path)

    reconstructed_paths: dict[float, pd.DataFrame] = {}
    metric_rows: list[dict] = []
    for cost_bps in program["return_path"]["cost_scenarios_bps"]:
        cost_bps = float(cost_bps)
        path = portfolio_path(weights, prices, cost_bps)
        reconstructed_paths[cost_bps] = path
        recent_start = path.index.max() - pd.DateOffset(years=int(program["return_path"]["recent_years"]))
        for window, values in (("full", path["net_return"]), ("recent_3y", path.loc[path.index >= recent_start, "net_return"])):
            row = {"cost_bps": cost_bps, "window": window, **metrics(values)}
            row["avg_weekly_one_way_turnover"] = float(path["turnover"].mean())
            row["annualized_cost_drag"] = float(path["cost"].mean() * 52.0)
            metric_rows.append(row)

    reconstructed_10 = reconstructed_paths[10.0]
    path_columns = ["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]
    joined = reconstructed_10[path_columns].join(saved[path_columns], how="inner", rsuffix="_saved")
    path_differences = {
        column: float((joined[column] - joined[f"{column}_saved"]).abs().max())
        for column in path_columns
    }
    maximum_path_difference = max(path_differences.values())
    path_correlation = float(joined["net_return"].corr(joined["net_return_saved"]))

    checkpoint_rows: list[dict] = []
    final_checkpoint_difference = float("nan")
    for path in sorted(CHECKPOINTS.glob(f"{NAME}__*.csv")):
        frame = read_dated(path).apply(pd.to_numeric, errors="coerce").fillna(0.0)
        stage = path.stem.split("__", 1)[1]
        checkpoint_rows.append({
            "stage": stage, "rows": len(frame), "columns": len(frame.columns),
            "start": str(frame.index.min().date()), "end": str(frame.index.max().date()),
            "maximum_row_sum_error_from_one": float((frame.sum(axis=1) - 1.0).abs().max()),
            "sha256": sha256(path),
        })
        if stage == "final_etf_weights":
            common_index = weights.index.intersection(frame.index)
            common_columns = weights.columns.intersection(frame.columns)
            final_checkpoint_difference = float(
                (weights.loc[common_index, common_columns] - frame.loc[common_index, common_columns]).abs().to_numpy().max()
            )

    catalog, catalog_count, ggg_position = allocator_catalog()
    selection = pd.read_csv(selection_path)
    phase_candidates = selection[selection["name"].notna()].copy()
    selected = str(selection["best_candidate"].dropna().iloc[0])
    report_date = "2026-04-27"
    saved_last_date = saved.index.max().date()
    selection_date = pd.Timestamp(report_date).date()
    post_selection_weeks = int((saved.index.date > selection_date).sum())

    gates_config = program["equivalence_gates"]
    equivalence_gates = {
        "final_checkpoint_weights": final_checkpoint_difference <= float(gates_config["maximum_final_checkpoint_weight_difference"]),
        "saved_path": maximum_path_difference <= float(gates_config["maximum_saved_path_absolute_difference_at_10bps"]),
        "net_return_correlation": path_correlation >= float(gates_config["minimum_net_return_correlation_at_10bps"]),
    }
    mechanical_pass = all(equivalence_gates.values())
    qualification_gates = {
        "mechanical_equivalence": mechanical_pass,
        "underlying_allocator_native_lineage_complete": False,
        "candidate_selection_uses_untouched_holdout": False,
        "post_selection_observations_exist": post_selection_weeks > 0,
        "point_in_time_universe": False,
        "source_price_vintage_known": False,
        "multiplicity_adjusted_evidence": False,
    }
    findings = [
        {"finding": "saved_weights_and_returns", "status": "pass_mechanical",
         "evidence": "Independent CSV-only reconstruction uses date-t weights on next-week returns and reproduces the saved 10 bps path."},
        {"finding": "allocator_checkpoints", "status": "pass_mechanical",
         "evidence": f"Six saved allocator stages were inventoried; final_etf_weights matches the published weights with max difference {final_checkpoint_difference:.3e}."},
        {"finding": "phase_selection", "status": "selection_contaminated",
         "evidence": f"GGG selected one of {len(phase_candidates)} phase candidates using full-history return, Sharpe, drawdown, CVaR, turnover, and state deltas from the same history."},
        {"finding": "research_multiplicity", "status": "not_adjusted",
         "evidence": f"The monolithic allocator catalog contains {catalog_count} named variants; GGG1 is position {ggg_position}. No family-wise, false-discovery, or deflated-Sharpe correction qualifies the reported winner."},
        {"finding": "post_selection_record", "status": "fail",
         "evidence": f"The GGG report is dated {report_date}, while saved strategy history ends {saved_last_date}; post-selection weeks in the saved artifact: {post_selection_weeks}."},
        {"finding": "universe_and_vintage", "status": "fail",
         "evidence": "The 35-ETF universe is fixed rather than point-in-time and weekly_prices.csv has no immutable source-vintage manifest."},
    ]

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(checkpoint_rows).to_csv(OUTPUT / "checkpoint_inventory.csv", index=False)
    catalog.to_csv(OUTPUT / "allocator_candidate_catalog.csv", index=False)
    phase_candidates.to_csv(OUTPUT / "phase_ggg_candidates.csv", index=False)
    pd.DataFrame(metric_rows).to_csv(OUTPUT / "performance_cost_sensitivity.csv", index=False)
    pd.DataFrame(findings).to_csv(OUTPUT / "lineage_findings.csv", index=False)

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(PROGRAM),
        "source_candidate": NAME, "selected_candidate": selected,
        "source_inputs": {
            "published_weights": {"path": str(weights_path.relative_to(V1)), "sha256": sha256(weights_path)},
            "published_returns": {"path": str(saved_path_file.relative_to(V1)), "sha256": sha256(saved_path_file)},
            "weekly_prices": {"path": str(prices_path.relative_to(V1)), "sha256": sha256(prices_path)},
            "phase_selection": {"path": str(selection_path.relative_to(V1)), "sha256": sha256(selection_path)},
            "allocator_builder": {"path": "scripts/build_improvement_artifacts.py", "sha256": sha256(V1 / "scripts/build_improvement_artifacts.py")},
            "phase_runner": {"path": "scripts/phase_ggg_state_conditional_composite_offense.py", "sha256": sha256(V1 / "scripts/phase_ggg_state_conditional_composite_offense.py")},
        },
        "independent_of_v1_python_modules": True,
        "weight_rows": len(weights), "assets": len(weights.columns),
        "checkpoint_count": len(checkpoint_rows),
        "maximum_final_checkpoint_weight_difference": final_checkpoint_difference,
        "path_weeks_compared": len(joined),
        "path_column_maximum_absolute_differences": path_differences,
        "maximum_path_absolute_difference_at_10bps": maximum_path_difference,
        "net_return_correlation_at_10bps": path_correlation,
        "equivalence_gates": equivalence_gates,
        "mechanical_equivalence_passed": mechanical_pass,
        "allocator_catalog_variant_count": catalog_count,
        "ggg_catalog_position_one_based": ggg_position,
        "phase_ggg_candidate_count": len(phase_candidates),
        "ggg_selection_report_date": report_date,
        "saved_history_last_date": str(saved_last_date),
        "post_selection_weeks_in_saved_history": post_selection_weeks,
        "qualification_gates": qualification_gates,
        "independent_validation_passed": all(qualification_gates.values()),
        "decision": "retain_as_selection_contaminated_benchmark_not_v2_winner",
        "version_1_modified": False, "live_trading_enabled": False,
    }
    artifact_names = [
        "checkpoint_inventory.csv", "allocator_candidate_catalog.csv", "phase_ggg_candidates.csv",
        "performance_cost_sensitivity.csv", "lineage_findings.csv",
    ]
    result["artifacts"] = {
        name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size}
        for name in artifact_names
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    metric_frame = pd.DataFrame(metric_rows)
    recent = metric_frame[(metric_frame["window"] == "recent_3y") & (metric_frame["cost_bps"] == 50.0)].iloc[0]
    report = [
        "# V1 GGG base lineage audit — Batch 42", "",
        f"GGG was mechanically reconstructed from saved weights without importing V1 Python modules. The 10 bps path matched across {len(joined)} weeks with maximum absolute difference {maximum_path_difference:.3e} and net-return correlation {path_correlation:.15f}. The final allocator checkpoint matched published weights to {final_checkpoint_difference:.3e}.", "",
        f"At the requested realistic 50 bps cost assumption, its most recent three-year retrospective window ({recent['start']} through {recent['end']}) has CAGR {recent['cagr']:.2%}, arithmetic return {recent['arithmetic_ann_return']:.2%}, Sharpe {recent['sharpe_zero_rf']:.3f}, and max drawdown {recent['max_drawdown']:.2%}.", "",
        f"The evidence is not an untouched test. GGG1 is entry {ggg_position} of {catalog_count} named variants in the allocator catalog and was selected from {len(phase_candidates)} Phase GGG alternatives using the same full history. The selection report postdates the last saved return, leaving {post_selection_weeks} post-selection observations. No multiplicity-adjusted qualification, point-in-time universe, or immutable price-vintage manifest is present.", "",
        "Decision: retain GGG as a valuable, exactly reproducible benchmark and source of architecture ideas. Label all historical metrics selection-contaminated retrospective; do not treat them as proof of expected future profitability or as an independently validated Version 2 winner.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({
        "mechanical_equivalence_passed": mechanical_pass,
        "independent_validation_passed": result["independent_validation_passed"],
        "catalog_variants": catalog_count, "ggg_position": ggg_position,
        "phase_candidates": len(phase_candidates), "post_selection_weeks": post_selection_weeks,
        "recent_3y_50bps_cagr": recent["cagr"], "recent_3y_50bps_sharpe": recent["sharpe_zero_rf"],
        "recent_3y_50bps_max_drawdown": recent["max_drawdown"],
    }, indent=2))
    return 0 if mechanical_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
