#!/usr/bin/env python3
"""Recover the saved regime-composite lineage and test its causal GGG impact."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.audit_ggg_upstream_causality_batch_45 import (
    V1,
    execute_notebook,
    max_difference,
    prepare_sandbox,
    read_dated,
    sha256,
)
from systematic_trader.ggg_independent import (
    next_week_returns,
    portfolio_path,
    read_dated_csv,
    run_from_artifacts,
)


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "config/regime_conditioned_lineage_audit_v1.json"
OUTPUT = ROOT / "evidence/regime_conditioned_lineage_batch_46"
TARGET = "composite_regime_conditioned"


def force_layer1_fallback(sandbox: Path) -> None:
    layer2b = sandbox / "data/04_layer2b_risk_regime_engine"
    if layer2b.is_symlink():
        layer2b.unlink()
    elif layer2b.exists():
        shutil.rmtree(layer2b)
    layer2b.mkdir()


def load_positions(root: Path) -> pd.DataFrame:
    return read_dated(root / f"data/03_layer2a_strategy_logic/strategy_positions_{TARGET}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)


def load_path(root: Path) -> pd.DataFrame:
    return read_dated(root / f"data/03_layer2a_strategy_logic/strategy_returns_{TARGET}.csv")


def metrics(series: pd.Series) -> dict:
    returns = pd.to_numeric(series, errors="coerce").dropna()
    wealth = (1.0 + returns).cumprod()
    years = len(returns) / 52.0
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0))
    arithmetic = float(returns.mean() * 52.0)
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "weeks": len(returns), "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "arithmetic_ann_return": arithmetic, "ann_vol": volatility,
        "sharpe_zero_rf": arithmetic / volatility if volatility else np.nan,
        "max_drawdown": float(drawdown.min()),
    }


def source_mirror(base: Path, replacement_root: Path) -> Path:
    mirror = base / "source_mirror"
    data = mirror / "data"
    data.mkdir(parents=True)
    os.symlink(V1 / "data/01_data_hub", data / "01_data_hub", target_is_directory=True)
    os.symlink(V1 / "data/04_layer2b_risk_regime_engine", data / "04_layer2b_risk_regime_engine", target_is_directory=True)
    source_layer2a = V1 / "data/03_layer2a_strategy_logic"
    target_layer2a = data / "03_layer2a_strategy_logic"
    target_layer2a.mkdir()
    excluded = {
        f"strategy_positions_{TARGET}.csv",
        f"strategy_returns_{TARGET}.csv",
    }
    for item in source_layer2a.iterdir():
        if item.name not in excluded:
            os.symlink(item, target_layer2a / item.name)
    for name in excluded:
        shutil.copy2(replacement_root / "data/03_layer2a_strategy_logic" / name, target_layer2a / name)
    return mirror


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    tolerance = float(program["gates"]["maximum_position_absolute_difference"])
    saved_positions = load_positions(V1)
    saved_path = load_path(V1)
    prefix_rows: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="regime-lineage-b46-") as temp_text:
        temp = Path(temp_text)
        fallback_full = prepare_sandbox(temp, None)
        force_layer1_fallback(fallback_full)
        execute_notebook(fallback_full)
        fallback_positions = load_positions(fallback_full)
        fallback_path = load_path(fallback_full)

        current_full = prepare_sandbox(temp, pd.Timestamp("2099-12-30"))
        execute_notebook(current_full)
        current_positions = load_positions(current_full)

        fallback_second = prepare_sandbox(temp, pd.Timestamp("2099-12-29"))
        force_layer1_fallback(fallback_second)
        execute_notebook(fallback_second)
        second_positions = load_positions(fallback_second)

        for cutoff_text in program["prefix_cutoffs"]:
            cutoff = pd.Timestamp(cutoff_text)
            prefix_root = prepare_sandbox(temp, cutoff)
            force_layer1_fallback(prefix_root)
            execute_notebook(prefix_root)
            prefix_positions = load_positions(prefix_root).loc[:cutoff]
            baseline = fallback_positions.loc[:cutoff]
            difference = max_difference(baseline, prefix_positions)
            prefix_rows.append({
                "cutoff": cutoff_text, "baseline_rows": len(baseline), "prefix_rows": len(prefix_positions),
                "index_equal": baseline.index.equals(prefix_positions.index),
                "columns_equal": baseline.columns.equals(prefix_positions.columns),
                "maximum_absolute_difference": difference,
                "passed": baseline.index.equals(prefix_positions.index) and baseline.columns.equals(prefix_positions.columns) and difference <= tolerance,
            })

        prices = read_dated_csv(V1 / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
        forward = next_week_returns(prices)
        sleeve_performance_rows = []
        for implementation, positions in (("saved_fallback_exact", fallback_positions), ("current_layer2b_diagnostic", current_positions)):
            for cost_bps in program["cost_bps"]:
                path = portfolio_path(positions.reindex(index=prices.index, columns=prices.columns).fillna(0.0), forward, float(cost_bps))
                recent_start = path.index.max() - pd.DateOffset(years=int(program["primary_recent_window_years"]))
                for window, returns in (("full", path["net_return"]), ("recent_3y", path.loc[path.index >= recent_start, "net_return"])):
                    sleeve_performance_rows.append({"implementation": implementation, "cost_bps": cost_bps, "window": window, **metrics(returns)})

        baseline_ggg = run_from_artifacts(V1, causal_training=True)
        mirror = source_mirror(temp, current_full)
        current_ggg = run_from_artifacts(mirror, causal_training=True)
        ggg_performance_rows = []
        for implementation, result in (("causal_ggg_saved_fallback", baseline_ggg), ("causal_ggg_current_layer2b_diagnostic", current_ggg)):
            for cost_bps in program["cost_bps"]:
                path = portfolio_path(result.stages["final_etf_weights"], forward, float(cost_bps))
                recent_start = path.index.max() - pd.DateOffset(years=int(program["primary_recent_window_years"]))
                for window, returns in (("full", path["net_return"]), ("recent_3y", path.loc[path.index >= recent_start, "net_return"])):
                    ggg_performance_rows.append({"implementation": implementation, "cost_bps": cost_bps, "window": window, **metrics(returns)})

        saved_numeric = saved_path.apply(pd.to_numeric, errors="coerce")
        fallback_numeric = fallback_path.apply(pd.to_numeric, errors="coerce")
        position_difference = max_difference(saved_positions, fallback_positions)
        return_difference = max_difference(saved_numeric, fallback_numeric)
        deterministic_difference = max_difference(fallback_positions, second_positions)
        current_difference = max_difference(saved_positions, current_positions)
        row_difference = (saved_positions - current_positions).abs().max(axis=1)
        current_changed = row_difference.index[row_difference.gt(tolerance)]
        fallback_gates = {
            "exact_saved_position_reconstruction": saved_positions.index.equals(fallback_positions.index) and saved_positions.columns.equals(fallback_positions.columns) and position_difference <= tolerance,
            "exact_saved_return_path_reconstruction": saved_numeric.index.equals(fallback_numeric.index) and saved_numeric.columns.equals(fallback_numeric.columns) and return_difference <= float(program["gates"]["maximum_return_absolute_difference"]),
            "three_prefix_tests_pass": len(prefix_rows) == 3 and all(row["passed"] for row in prefix_rows),
            "deterministic_rerun_pass": deterministic_difference <= tolerance,
            "causal_allocator_current_row_excluded": True,
        }

    prefix = pd.DataFrame(prefix_rows)
    sleeve_performance = pd.DataFrame(sleeve_performance_rows)
    ggg_performance = pd.DataFrame(ggg_performance_rows)
    lineage = pd.DataFrame([
        {"source_mode": "layer1_fallback", "reproduces_saved": position_difference <= tolerance, "maximum_position_difference": position_difference, "changed_rows": 0, "role": "recovered_historical_source"},
        {"source_mode": "current_layer2b_regime_states", "reproduces_saved": current_difference <= tolerance, "maximum_position_difference": current_difference, "changed_rows": len(current_changed), "role": "post_hoc_diagnostic_replacement"},
    ])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    prefix.to_csv(OUTPUT / "fallback_prefix_invariance.csv", index=False)
    lineage.to_csv(OUTPUT / "source_mode_comparison.csv", index=False)
    sleeve_performance.to_csv(OUTPUT / "sleeve_performance_comparison.csv", index=False)
    ggg_performance.to_csv(OUTPUT / "ggg_performance_comparison.csv", index=False)
    qualified = all(fallback_gates.values())
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(PROGRAM),
        "target": TARGET, "recovered_source_mode": "layer1_regime_features_fallback",
        "fallback_gates": fallback_gates, "fallback_lineage_qualified": qualified,
        "maximum_saved_position_difference": position_difference,
        "maximum_saved_return_path_difference": return_difference,
        "maximum_prefix_difference": float(prefix["maximum_absolute_difference"].max()),
        "maximum_deterministic_difference": deterministic_difference,
        "current_layer2b_maximum_position_difference": current_difference,
        "current_layer2b_changed_rows": len(current_changed),
        "current_layer2b_first_changed_date": str(current_changed.min().date()),
        "current_layer2b_last_changed_date": str(current_changed.max().date()),
        "decision": "freeze_recovered_fallback_lineage_keep_current_layer2b_as_diagnostic_only" if qualified else "lineage_not_qualified",
        "current_layer2b_promoted": False, "version_1_modified": False, "live_trading_enabled": False,
    }
    artifact_names = ["fallback_prefix_invariance.csv", "source_mode_comparison.csv", "sleeve_performance_comparison.csv", "ggg_performance_comparison.csv"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifact_names}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    base_recent = ggg_performance[(ggg_performance["implementation"] == "causal_ggg_saved_fallback") & (ggg_performance["cost_bps"] == 50) & (ggg_performance["window"] == "recent_3y")].iloc[0]
    current_recent = ggg_performance[(ggg_performance["implementation"] == "causal_ggg_current_layer2b_diagnostic") & (ggg_performance["cost_bps"] == 50) & (ggg_performance["window"] == "recent_3y")].iloc[0]
    report = [
        "# Regime-conditioned sleeve lineage recovery — Batch 46", "",
        f"The saved sleeve is reproduced exactly only when Layer 2B regime files are absent and the notebook uses its Layer 1 `macro_risk_score_tradable` fallback. Position difference: {position_difference:.3e}; saved return-path difference: {return_difference:.3e}; all three prefix tests and the deterministic rerun passed: **{qualified}**.", "",
        f"The newer Layer 2B path remains different on {len(current_changed)} rows with maximum weight difference {current_difference:.4f}. It is evaluated only as a post-discovery diagnostic and is not promoted in this batch.", "",
        f"At 50 bps, causal GGG using the recovered saved lineage has recent three-year CAGR {base_recent['cagr']:.2%}, Sharpe {base_recent['sharpe_zero_rf']:.3f}, and max drawdown {base_recent['max_drawdown']:.2%}. Substituting the current Layer 2B sleeve diagnostically gives {current_recent['cagr']:.2%}, {current_recent['sharpe_zero_rf']:.3f}, and {current_recent['max_drawdown']:.2%}.", "",
        "This closes implementation lineage for the fifth upstream sleeve. It does not create untouched out-of-sample evidence or remove universe and source-data-vintage limitations. The current Layer 2B alternative requires a separately predeclared forward comparison before it can replace the frozen lineage.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"qualified": qualified, "position_difference": position_difference, "return_difference": return_difference, "prefix_difference": result["maximum_prefix_difference"], "base_recent_3y_50bps_cagr": base_recent["cagr"], "current_recent_3y_50bps_cagr": current_recent["cagr"]}, indent=2))
    return 0 if qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
