#!/usr/bin/env python3
"""Independently reconstruct the V1 wrapper and record its causal lineage limits."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
V1 = ROOT.parent / "1.0"
PROGRAM = ROOT / "config/v1_wrapper_equivalence_lineage_v1.json"
OUTPUT = ROOT / "evidence/v1_wrapper_equivalence_batch_41"
PORT = V1 / "data/05_layer3_portfolio_construction"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dated(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "date" in frame.columns:
        date_column = "date"
    elif "Date" in frame.columns:
        date_column = "Date"
    else:
        date_column = str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="coerce").dt.tz_localize(None)
    return frame.dropna(subset=[date_column]).sort_values(date_column).set_index(date_column)


def normalize_to_bil(weights: pd.DataFrame) -> pd.DataFrame:
    result = weights.clip(lower=0.0).copy()
    if "BIL" not in result:
        result["BIL"] = 0.0
    risky = [column for column in result if column != "BIL"]
    total = result[risky].sum(axis=1)
    over = total > 1.0
    result.loc[over, risky] = result.loc[over, risky].div(total.loc[over], axis=0)
    result["BIL"] = (1.0 - result[risky].sum(axis=1)).clip(lower=0.0)
    return result


def portfolio_path(weights: pd.DataFrame, prices: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    forward = prices.apply(pd.to_numeric, errors="coerce").pct_change().shift(-1)
    index = weights.index.intersection(forward.index)
    columns = [column for column in weights if column in forward]
    applied = weights.reindex(index=index, columns=columns).fillna(0.0)
    realized = forward.reindex(index=index, columns=columns).fillna(0.0)
    gross = (applied * realized).sum(axis=1)
    turnover = 0.5 * applied.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame({"gross_return": gross, "net_return": net, "turnover": turnover, "cost": cost, "wealth": wealth, "drawdown": drawdown})


def main() -> int:
    program = json.loads(PROGRAM.read_text(encoding="utf-8"))
    base = read_dated(PORT / "portfolio_version_weights_improved_phaseggg_confirmed_only_robust_offense.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
    expected_weights = read_dated(PORT / "portfolio_version_weights_improved_frontier_phase5_fragility_guard.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
    expected_path = read_dated(PORT / "portfolio_version_returns_improved_frontier_phase5_fragility_guard.csv").apply(pd.to_numeric, errors="coerce")
    states = read_dated(V1 / "data/04_layer2b_risk_regime_engine/market_state_history.csv")["market_state"].astype(str)
    phase1 = read_dated(V1 / "data/research/frontier_phase1/state_quality_signals_r2.csv")
    phase4 = read_dated(V1 / "data/research/frontier_phase4/leadership_signals.csv")
    prices = read_dated(V1 / "data/01_data_hub/weekly_prices.csv")

    index = base.index
    state = states.reindex(index).astype(str)
    r2a = pd.to_numeric(phase1["r2a"], errors="coerce").reindex(index).fillna(0.0).clip(-1.0, 1.0)
    leadership = pd.to_numeric(phase4["leadership_quality_composite"], errors="coerce").reindex(index).ffill().fillna(0.0)
    scale = pd.Series(1.0, index=index, dtype=float)
    active = state.ne("stressed_panic")
    scale.loc[active] = 1.0 + 0.08 * r2a.loc[active]
    crowded = leadership.gt(0.50)
    scale.loc[crowded & active] = scale.loc[crowded & active].clip(upper=1.0)
    scale.loc[state.eq("stressed_panic")] = 1.0

    reconstructed = base.copy()
    offense = [asset for asset in program["independent_reconstruction"]["offense_assets"] if asset in reconstructed]
    reconstructed[offense] = reconstructed[offense].mul(scale, axis=0)
    reconstructed = normalize_to_bil(reconstructed)
    common_columns = list(expected_weights.columns)
    weight_difference = (reconstructed.reindex(index=expected_weights.index, columns=common_columns) - expected_weights).abs()
    maximum_weight_difference = float(weight_difference.to_numpy().max())

    reconstructed_path = portfolio_path(reconstructed, prices, float(program["independent_reconstruction"]["cost_bps"]))
    path_columns = ["gross_return", "net_return", "turnover", "cost", "wealth", "drawdown"]
    joined = reconstructed_path[path_columns].join(expected_path[path_columns], how="inner", rsuffix="_expected")
    path_differences = {column: float((joined[column] - joined[f"{column}_expected"]).abs().max()) for column in path_columns}
    maximum_path_difference = max(path_differences.values())
    correlation = float(joined["net_return"].corr(joined["net_return_expected"]))
    rules = program["equivalence_gates"]
    equivalence_gates = {
        "weights": maximum_weight_difference <= float(rules["maximum_weight_absolute_difference"]),
        "path": maximum_path_difference <= float(rules["maximum_path_absolute_difference"]),
        "correlation": correlation >= float(rules["minimum_net_return_correlation"]),
    }

    lineage = {
        "phase1_raw_components_lagged_one_week": True,
        "phase1_and_phase4_normalization_expanding_only": True,
        "phase4_price_components_lagged_one_week": True,
        "final_weights_fund_next_week_not_same_week": True,
        "base_ggg_native_lineage_complete": False,
        "holdout_untouched_by_variant_selection": False,
        "point_in_time_universe": False,
        "source_price_vintage_known": False,
    }
    findings = [
        {
            "finding": "wrapper_return_timing",
            "status": "pass",
            "evidence": "V1 production_costs.py constructs pct_change().shift(-1), so date-t weights fund the next weekly close-to-close return."
        },
        {
            "finding": "phase1_feature_timing",
            "status": "pass_implementation",
            "evidence": "Phase 1 raw components are shifted one week and standardized with expanding statistics before R2A construction."
        },
        {
            "finding": "phase4_feature_timing",
            "status": "pass_implementation",
            "evidence": "All five Phase 4 price components are shifted one week and standardized with expanding statistics."
        },
        {
            "finding": "holdout_independence",
            "status": "fail",
            "evidence": "The 2026-05-21 Phase 5 report evaluated seven non-baseline variants on the 2024-04-19 holdout, used holdout Sharpe in its selection score, and selected the final fragility-guard family. The saved return history ends 2026-04-10, so it contains zero post-selection weeks."
        },
        {
            "finding": "base_weight_lineage",
            "status": "incomplete",
            "evidence": "The wrapper begins from saved GGG final weights produced after a long multi-phase candidate search; their complete native causal reconstruction has not yet been established in Version 2."
        },
        {
            "finding": "universe_and_vintage",
            "status": "fail",
            "evidence": "The 35-ETF universe is fixed using currently available symbols and the source weekly-price artifact has no immutable observation-vintage manifest."
        }
    ]
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "program": program["program"], "program_sha256": sha256(PROGRAM),
        "independent_of_v1_python_modules": True,
        "weight_rows": len(reconstructed), "assets": len(reconstructed.columns),
        "maximum_weight_absolute_difference": maximum_weight_difference,
        "path_weeks_compared": len(joined), "path_column_maximum_absolute_differences": path_differences,
        "maximum_path_absolute_difference": maximum_path_difference,
        "net_return_correlation": correlation,
        "equivalence_gates": equivalence_gates, "mechanical_equivalence_passed": all(equivalence_gates.values()),
        "lineage_gates": lineage, "causal_lineage_passed": all(lineage.values()),
        "decision": "mechanically_equivalent_but_not_qualified_as_v2_incumbent",
        "recent_performance_claim": "selection_contaminated_retrospective",
        "selection_record_date": "2026-05-21",
        "saved_history_last_date": str(expected_path.index.max().date()),
        "post_selection_weeks_in_saved_history": 0,
        "version_1_modified": False, "live_trading_enabled": False,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    scale_frame = pd.DataFrame({"date": index, "market_state": state.values, "r2a": r2a.values, "leadership_quality_composite": leadership.values, "crowded_guard": crowded.values, "offense_scale": scale.values})
    scale_frame.to_csv(OUTPUT / "scale_history.csv", index=False)
    pd.DataFrame(findings).to_csv(OUTPUT / "lineage_findings.csv", index=False)
    result["artifacts"] = {name: {"sha256": sha256(OUTPUT / name), "bytes": (OUTPUT / name).stat().st_size} for name in ("scale_history.csv", "lineage_findings.csv")}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# V1 wrapper equivalence and lineage — Batch 41", "",
        f"An implementation independent of V1 Python modules reconstructed {len(reconstructed)} weekly rows and {len(reconstructed.columns)} assets. Maximum weight difference was {maximum_weight_difference:.3e}; maximum return-path difference was {maximum_path_difference:.3e}; net-return correlation was {correlation:.15f}. Mechanical equivalence passed: **{result['mechanical_equivalence_passed']}**.", "",
        "The weekly implementation is causal: Phase 1 and Phase 4 price features are one-week lagged, their normalizers are expanding, and decision weights fund next-week returns. However, the April 2024 onward holdout was used to compare and select Phase 5 variants. The selection report is dated 2026-05-21 while saved history ends 2026-04-10, leaving zero post-selection weeks. The saved GGG base lineage is also incomplete, the fixed ETF universe is not point-in-time, and the weekly price file lacks a source-vintage manifest.", "",
        "Decision: mechanically equivalent, but not yet qualified as the Version 2 incumbent. Its recent returns remain the performance benchmark, labeled selection-contaminated retrospective evidence rather than independent validation.", ""
    ]
    (OUTPUT / "report.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps({"mechanical_equivalence_passed": result["mechanical_equivalence_passed"], "causal_lineage_passed": result["causal_lineage_passed"], "decision": result["decision"], "max_weight_diff": maximum_weight_difference, "max_path_diff": maximum_path_difference}, indent=2))
    return 0 if result["mechanical_equivalence_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
