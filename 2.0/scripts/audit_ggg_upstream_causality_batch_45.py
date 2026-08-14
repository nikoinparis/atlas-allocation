#!/usr/bin/env python3
"""Native reconstruction and prefix-causality audit for GGG's five source sleeves."""

from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
PROGRAM = ROOT / "config/ggg_upstream_causality_audit_v1.json"
NOTEBOOK = V1 / "03_layer2a_strategy_logic.ipynb"
OUTPUT = ROOT / "evidence/ggg_upstream_causality_batch_45"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dated(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_col = "Date" if "Date" in frame.columns else "date" if "date" in frame.columns else frame.columns[0]
    frame[date_col] = pd.to_datetime(frame[date_col], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)


def max_difference(left: pd.DataFrame, right: pd.DataFrame) -> float:
    index = left.index.intersection(right.index)
    columns = left.columns.intersection(right.columns)
    values = (left.loc[index, columns] - right.loc[index, columns]).abs().to_numpy()
    return float(np.nanmax(values)) if values.size else float("inf")


def link_directory_contents(source: Path, destination: Path, copied_names: set[str] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    copied_names = copied_names or set()
    for item in source.iterdir():
        if item.name not in copied_names:
            os.symlink(item, destination / item.name, target_is_directory=item.is_dir())


def truncate_csv(source: Path, destination: Path, cutoff: pd.Timestamp) -> None:
    frame = pd.read_csv(source)
    date_col = "Date" if "Date" in frame.columns else "date" if "date" in frame.columns else frame.columns[0]
    dates = pd.to_datetime(frame[date_col], errors="coerce").dt.tz_localize(None)
    frame.loc[dates.le(cutoff)].to_csv(destination, index=False)


def prepare_sandbox(base: Path, cutoff: pd.Timestamp | None) -> Path:
    sandbox = base / ("full" if cutoff is None else cutoff.strftime("prefix_%Y%m%d"))
    sandbox.mkdir(parents=True)
    shutil.copy2(NOTEBOOK, sandbox / NOTEBOOK.name)
    data = sandbox / "data"
    data.mkdir()
    if cutoff is None:
        os.symlink(V1 / "data/01_data_hub", data / "01_data_hub", target_is_directory=True)
        # The notebook emits a diagnostic contribution table into Layer 1.
        # Link immutable inputs individually so that output lands only in this
        # disposable directory rather than the read-only Version 1 mount.
        notebook_layer1_outputs = {"signal_incremental_contribution.csv", "signal_subset_comparison.csv"}
        link_directory_contents(V1 / "data/02_layer1_signals", data / "02_layer1_signals", notebook_layer1_outputs)
        os.symlink(V1 / "data/04_layer2b_risk_regime_engine", data / "04_layer2b_risk_regime_engine", target_is_directory=True)
    else:
        hub_source = V1 / "data/01_data_hub"
        hub_dest = data / "01_data_hub"
        truncated_hub = {"weekly_prices.csv", "weekly_returns.csv", "daily_returns.csv", "market_proxy_weekly.csv", "benchmark_returns_weekly.csv"}
        link_directory_contents(hub_source, hub_dest, truncated_hub)
        for name in truncated_hub:
            source = hub_source / name
            if source.exists():
                truncate_csv(source, hub_dest / name, cutoff)

        layer1_source = V1 / "data/02_layer1_signals"
        layer1_dest = data / "02_layer1_signals"
        dated_layer1 = {
            "signal_tsmom.csv", "signal_xsmom.csv", "signal_reversal.csv",
            "signal_multi_horizon_mom.csv", "signal_residual_momentum.csv",
            "signal_carry.csv", "signal_value.csv", "signal_bab.csv",
            "signal_quality.csv", "regime_features.csv",
            "signal_incremental_contribution.csv", "signal_subset_comparison.csv",
        }
        link_directory_contents(layer1_source, layer1_dest, dated_layer1)
        for name in dated_layer1:
            source = layer1_source / name
            if name not in {"signal_incremental_contribution.csv", "signal_subset_comparison.csv"}:
                truncate_csv(source, layer1_dest / name, cutoff)

        regime_source = V1 / "data/04_layer2b_risk_regime_engine"
        regime_dest = data / "04_layer2b_risk_regime_engine"
        dated_regime = {"regime_states.csv", "regime_score.csv"}
        link_directory_contents(regime_source, regime_dest, dated_regime)
        for name in dated_regime:
            source = regime_source / name
            if source.exists():
                truncate_csv(source, regime_dest / name, cutoff)
    (data / "03_layer2a_strategy_logic").mkdir()
    return sandbox


def execute_notebook(sandbox: Path) -> None:
    notebook = json.loads((sandbox / NOTEBOOK.name).read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__", "display": lambda *args, **kwargs: None}
    old_cwd = Path.cwd()
    try:
        os.chdir(sandbox)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for cell_number, cell in enumerate(notebook["cells"]):
                if cell.get("cell_type") != "code":
                    continue
                source = "".join(cell.get("source", []))
                exec(compile(source, f"{NOTEBOOK.name}:cell-{cell_number}", "exec"), namespace)
    finally:
        os.chdir(old_cwd)


def negative_shift_findings() -> list[dict]:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    findings: list[dict] = []
    for cell_number, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr != "shift" or not node.args:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.UnaryOp) and isinstance(argument.op, ast.USub):
                expression = ast.unparse(node)
                if expression == "month_key.shift(-1)":
                    classification = "known_calendar_month_end_mask_not_market_data"
                    affects_audited_decision = False
                elif expression == "gross.shift(-step)":
                    classification = "forward_ic_research_target_not_used_by_audited_sleeves"
                    affects_audited_decision = False
                elif expression == "weekly_simple_returns.shift(-1)":
                    classification = "realized_outcome_label_not_position_input"
                    affects_audited_decision = False
                else:
                    classification = "unresolved_negative_shift"
                    affects_audited_decision = True
                findings.append({
                    "cell": cell_number, "line": node.lineno, "expression": expression,
                    "classification": classification,
                    "affects_audited_decision": affects_audited_decision,
                })
    return findings


def signal_lag_evidence() -> dict[str, bool]:
    notebook_text = NOTEBOOK.read_text(encoding="utf-8")
    return {
        "global_signal_lag_one_week": 'SIGNAL_LAG_WEEKS = 1' in notebook_text,
        "dual_absolute_momentum_additional_price_lag": 'raw_momentum_52_4w = apply_price_lag' in notebook_text,
        "cta_uses_tradable_score": 'multi_mom_invvol_score_tradable' in notebook_text,
        "selective_inputs_use_tradable_fields": all(token in notebook_text for token in [
            'xsmom_score_tradable', 'multi_mom_invvol_score_tradable', 'quality_score_tradable',
            'value_score_tradable', 'bab_score_tradable', 'carry_score_tradable',
        ]),
        "taa_price_filter_lagged": 'filter_signal = apply_price_lag' in notebook_text,
        "regime_state_uses_dated_regime_file": 'regime_states.csv' in notebook_text,
    }


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    sleeves = program["sleeves"]
    tolerance = float(program["gates"]["maximum_position_absolute_difference"])
    prefix_tolerance = float(program["gates"]["maximum_prefix_absolute_difference"])
    return_tolerance = float(program["gates"]["maximum_return_identity_absolute_difference"])
    equivalence_rows: list[dict] = []
    prefix_rows: list[dict] = []
    return_rows: list[dict] = []
    determinism_rows: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="ggg-upstream-b45-") as temp_text:
        temp = Path(temp_text)
        full = prepare_sandbox(temp, None)
        execute_notebook(full)
        generated: dict[str, pd.DataFrame] = {}
        for sleeve in sleeves:
            expected = read_dated(V1 / f"data/03_layer2a_strategy_logic/strategy_positions_{sleeve}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
            actual_path = full / f"data/03_layer2a_strategy_logic/strategy_positions_{sleeve}.csv"
            actual = read_dated(actual_path).apply(pd.to_numeric, errors="coerce").fillna(0.0)
            generated[sleeve] = actual
            difference = max_difference(expected, actual)
            common_index = expected.index.intersection(actual.index)
            common_columns = expected.columns.intersection(actual.columns)
            row_difference = (expected.loc[common_index, common_columns] - actual.loc[common_index, common_columns]).abs().max(axis=1)
            changed_dates = row_difference.index[row_difference.gt(tolerance)]
            equivalence_rows.append({
                "sleeve": sleeve, "expected_rows": len(expected), "actual_rows": len(actual),
                "index_equal": expected.index.equals(actual.index), "columns_equal": expected.columns.equals(actual.columns),
                "maximum_absolute_difference": difference,
                "changed_rows": len(changed_dates),
                "first_changed_date": "" if len(changed_dates) == 0 else str(changed_dates.min().date()),
                "last_changed_date": "" if len(changed_dates) == 0 else str(changed_dates.max().date()),
                "native_position_equivalence_passed": expected.index.equals(actual.index) and expected.columns.equals(actual.columns) and difference <= tolerance,
                "saved_sha256": sha256(V1 / f"data/03_layer2a_strategy_logic/strategy_positions_{sleeve}.csv"),
                "generated_sha256": sha256(actual_path),
            })

        for cutoff_text in program["prefix_cutoffs"]:
            cutoff = pd.Timestamp(cutoff_text)
            prefix = prepare_sandbox(temp, cutoff)
            execute_notebook(prefix)
            for sleeve in sleeves:
                truncated = read_dated(prefix / f"data/03_layer2a_strategy_logic/strategy_positions_{sleeve}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
                baseline = generated[sleeve].loc[:cutoff]
                difference = max_difference(baseline, truncated.loc[:cutoff])
                prefix_rows.append({
                    "sleeve": sleeve, "cutoff": cutoff_text, "baseline_rows": len(baseline),
                    "truncated_rows": len(truncated.loc[:cutoff]),
                    "index_equal": baseline.index.equals(truncated.loc[:cutoff].index),
                    "columns_equal": baseline.columns.equals(truncated.columns),
                    "maximum_prefix_absolute_difference": difference,
                    "prefix_invariance_passed": baseline.index.equals(truncated.loc[:cutoff].index) and baseline.columns.equals(truncated.columns) and difference <= prefix_tolerance,
                })

        second_full = prepare_sandbox(temp, pd.Timestamp("2099-12-31"))
        execute_notebook(second_full)
        for sleeve in sleeves:
            second = read_dated(second_full / f"data/03_layer2a_strategy_logic/strategy_positions_{sleeve}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
            first = generated[sleeve]
            difference = max_difference(first, second)
            determinism_rows.append({
                "sleeve": sleeve, "index_equal": first.index.equals(second.index),
                "columns_equal": first.columns.equals(second.columns),
                "maximum_absolute_difference": difference,
                "deterministic_rerun_passed": first.index.equals(second.index) and first.columns.equals(second.columns) and difference <= tolerance,
            })

    log_returns = read_dated(V1 / "data/01_data_hub/weekly_returns.csv").apply(pd.to_numeric, errors="coerce")
    next_simple_returns = np.expm1(log_returns).shift(-1)
    for sleeve in sleeves:
        positions = read_dated(V1 / f"data/03_layer2a_strategy_logic/strategy_positions_{sleeve}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
        path = read_dated(V1 / f"data/03_layer2a_strategy_logic/strategy_returns_{sleeve}.csv")
        common_columns = positions.columns.intersection(next_simple_returns.columns)
        expected_gross = (positions[common_columns] * next_simple_returns.reindex(index=positions.index, columns=common_columns)).sum(axis=1)
        actual_gross = pd.to_numeric(path["gross_return"], errors="coerce").reindex(expected_gross.index)
        valid = expected_gross.notna() & actual_gross.notna()
        error = float((expected_gross[valid] - actual_gross[valid]).abs().max())
        same_week = (positions[common_columns] * np.expm1(log_returns).reindex(index=positions.index, columns=common_columns)).sum(axis=1)
        same_valid = same_week.notna() & actual_gross.notna()
        same_week_error = float((same_week[same_valid] - actual_gross[same_valid]).abs().max())
        return_rows.append({
            "sleeve": sleeve, "observations": int(valid.sum()),
            "maximum_next_week_return_identity_error": error,
            "maximum_same_week_identity_error": same_week_error,
            "next_week_return_identity_passed": error <= return_tolerance,
            "label_semantics": "position dated t earns price return t_to_t_plus_1; outcome unavailable at t",
        })

    equivalence = pd.DataFrame(equivalence_rows)
    prefixes = pd.DataFrame(prefix_rows)
    returns = pd.DataFrame(return_rows)
    determinism = pd.DataFrame(determinism_rows)
    lag_checks = signal_lag_evidence()
    static_findings = negative_shift_findings()
    static_unexpected = [finding for finding in static_findings if finding["affects_audited_decision"]]
    qualification_rows = []
    for sleeve in sleeves:
        native_pass = bool(equivalence.loc[equivalence["sleeve"].eq(sleeve), "native_position_equivalence_passed"].all())
        sleeve_prefix = prefixes[prefixes["sleeve"].eq(sleeve)]
        prefix_pass = len(sleeve_prefix) == len(program["prefix_cutoffs"]) and bool(sleeve_prefix["prefix_invariance_passed"].all())
        return_pass = bool(returns.loc[returns["sleeve"].eq(sleeve), "next_week_return_identity_passed"].all())
        deterministic_pass = bool(determinism.loc[determinism["sleeve"].eq(sleeve), "deterministic_rerun_passed"].all())
        lag_pass = all(lag_checks.values())
        qualified = native_pass and prefix_pass and return_pass and deterministic_pass and lag_pass and not static_unexpected
        qualification_rows.append({
            "sleeve": sleeve, "native_equivalence_passed": native_pass,
            "prefix_invariance_passed": prefix_pass, "return_identity_passed": return_pass,
            "deterministic_rerun_passed": deterministic_pass,
            "declared_lag_evidence_passed": lag_pass, "unexpected_negative_shift_clean": not static_unexpected,
            "qualified_for_frozen_causal_benchmark": qualified,
            "decision": "freeze_as_causal_input" if qualified else "retain_as_unresolved_upstream_dependency",
        })
    qualifications = pd.DataFrame(qualification_rows)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    equivalence.to_csv(OUTPUT / "native_position_equivalence.csv", index=False)
    prefixes.to_csv(OUTPUT / "prefix_invariance.csv", index=False)
    returns.to_csv(OUTPUT / "return_label_identity.csv", index=False)
    determinism.to_csv(OUTPUT / "deterministic_rerun.csv", index=False)
    qualifications.to_csv(OUTPUT / "sleeve_qualification.csv", index=False)
    (OUTPUT / "signal_lag_evidence.json").write_text(json.dumps(lag_checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "static_negative_shift_findings.json").write_text(json.dumps(static_findings, indent=2) + "\n", encoding="utf-8")
    qualified = qualifications.loc[qualifications["qualified_for_frozen_causal_benchmark"], "sleeve"].tolist()
    unresolved = qualifications.loc[~qualifications["qualified_for_frozen_causal_benchmark"], "sleeve"].tolist()
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(PROGRAM), "notebook_sha256": sha256(NOTEBOOK),
        "sleeves_tested": len(sleeves), "qualified_sleeves": qualified, "unresolved_sleeves": unresolved,
        "all_sleeves_qualified": len(qualified) == len(sleeves),
        "maximum_native_position_difference": float(equivalence["maximum_absolute_difference"].max()),
        "maximum_prefix_difference": float(prefixes["maximum_prefix_absolute_difference"].max()),
        "maximum_next_week_return_identity_error": float(returns["maximum_next_week_return_identity_error"].max()),
        "negative_shift_findings": static_findings,
        "interpretation": "Sleeve positions may be causal while their row-t realized returns remain future outcomes. The causal GGG allocator must exclude row t from date-t training.",
        "version_1_modified": False, "live_trading_enabled": False,
    }
    artifact_names = ["native_position_equivalence.csv", "prefix_invariance.csv", "return_label_identity.csv", "deterministic_rerun.csv", "sleeve_qualification.csv", "signal_lag_evidence.json", "static_negative_shift_findings.json"]
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in artifact_names}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# GGG upstream sleeve causality audit — Batch 45", "",
        f"Five source sleeves were rebuilt with the pinned native Layer 2A notebook and tested at {len(program['prefix_cutoffs'])} truncated-history cutoffs. Qualified: **{len(qualified)}/5**.", "",
        f"Maximum native position difference: {result['maximum_native_position_difference']:.3e}. Maximum prefix difference: {result['maximum_prefix_difference']:.3e}. Maximum next-week gross-return identity error: {result['maximum_next_week_return_identity_error']:.3e}.", "",
        f"Qualified sleeves: {', '.join(qualified) if qualified else 'none'}. Unresolved sleeves: {', '.join(unresolved) if unresolved else 'none'}.", "",
        "The return-label check confirms that a position dated t earns the return from t to t+1. That return is therefore a future outcome at the decision timestamp and must be excluded from date-t allocator training. Passing position-prefix tests does not change that label rule.", "",
        "Qualification is limited to implementation causality and reproducibility. It does not cure fixed-universe survivorship risk, non-vintage source data, or historical strategy-selection contamination, and it does not authorize live trading.", "",
    ]
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"qualified": qualified, "unresolved": unresolved, "maximum_native_difference": result["maximum_native_position_difference"], "maximum_prefix_difference": result["maximum_prefix_difference"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
