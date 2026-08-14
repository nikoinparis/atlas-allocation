#!/usr/bin/env python3
"""Build an auditable, bias-aware scoreboard for all saved Layer 2 strategies."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.systematic_trader.evaluation import (
    benchmark_regression,
    block_bootstrap_intervals,
    performance_metrics,
    rolling_window_summary,
)


V1_DATA = ROOT.parent / "1.0/data"
STRATEGY_DIR = V1_DATA / "03_layer2a_strategy_logic"
MARKET_RETURNS = V1_DATA / "01_data_hub/weekly_returns.csv"
MANIFEST = STRATEGY_DIR / "layer2_manifest.json"
OUTPUT = ROOT / "evidence/strategy_scoreboard"
RECENT_START = date(2021, 1, 1)
DEFAULT_COST_BPS = 10.0
STRESS_COST_BPS = (10.0, 25.0, 50.0)
RECONCILIATION_TOLERANCE = 1e-10


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def row_date(row: dict[str, str]) -> str:
    value = row.get("Date") or row.get("date") or row.get("")
    if not value:
        raise ValueError("row has no date field")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def realized_date(decision_date: str) -> str:
    return (date.fromisoformat(decision_date) + timedelta(days=7)).isoformat()


def load_market_simple_returns() -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for row in read_csv(MARKET_RETURNS):
        result[row_date(row)] = {
            asset: math.expm1(float(value)) if value not in ("", None) else None
            for asset, value in row.items()
            if asset != "Date"
        }
    return result


def finite(value: str | None, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError("non-finite strategy artifact")
    return parsed


def reconstruct_strategy(
    name: str, market: dict[str, dict[str, float | None]]
) -> tuple[list[dict[str, float | str]], dict[str, float | int | bool]]:
    returns_path = STRATEGY_DIR / f"strategy_returns_{name}.csv"
    positions_path = STRATEGY_DIR / f"strategy_positions_{name}.csv"
    saved = {row_date(row): row for row in read_csv(returns_path)}
    positions = read_csv(positions_path)
    periods: list[dict[str, float | str]] = []
    errors: list[float] = []
    cost_errors: list[float] = []
    unpriced_weeks = 0
    unpriced_events = 0
    negative_exposure_weeks = 0
    multi_asset_weeks = 0
    maximum_gross_exposure = 0.0
    total_turnover = 0.0

    for position in positions:
        decision = row_date(position)
        realization = realized_date(decision)
        if realization not in market or decision not in saved:
            continue
        market_row = market[realization]
        reconstructed_gross = 0.0
        week_unpriced = False
        nonzero_positions = 0
        gross_exposure = 0.0
        negative_exposure = False
        for asset, raw_weight in position.items():
            if asset in {"Date", "date", ""} or raw_weight in ("", None):
                continue
            weight = finite(raw_weight)
            if abs(weight) > 1e-12:
                nonzero_positions += 1
            gross_exposure += abs(weight)
            negative_exposure = negative_exposure or weight < -1e-12
            asset_return = market_row.get(asset)
            if asset_return is None:
                if abs(weight) > 1e-12:
                    week_unpriced = True
                    unpriced_events += 1
                asset_return = 0.0
            reconstructed_gross += weight * asset_return
        if week_unpriced:
            unpriced_weeks += 1
        if negative_exposure:
            negative_exposure_weeks += 1
        if nonzero_positions > 1:
            multi_asset_weeks += 1
        maximum_gross_exposure = max(maximum_gross_exposure, gross_exposure)

        artifact = saved[decision]
        reported_gross = finite(artifact.get("gross_return"))
        reported_net = finite(artifact.get("net_return"))
        turnover = finite(artifact.get("turnover"))
        total_turnover += turnover
        reported_cost = finite(artifact.get("cost"))
        errors.append(abs(reconstructed_gross - reported_gross))
        cost_errors.append(
            max(
                abs(reported_cost - turnover * DEFAULT_COST_BPS / 10_000.0),
                abs(reported_net - (reported_gross - reported_cost)),
            )
        )
        periods.append(
            {
                "decision_date": decision,
                "realization_date": realization,
                "reported_gross": reported_gross,
                "reconstructed_gross": reconstructed_gross,
                "reported_net": reported_net,
                "turnover": turnover,
                "reported_cost": reported_cost,
            }
        )

    audit: dict[str, float | int | bool] = {
        "matched_periods": len(periods),
        "max_return_reconstruction_error": max(errors) if errors else math.inf,
        "mean_return_reconstruction_error": sum(errors) / len(errors) if errors else math.inf,
        "return_reconstruction_pass": bool(errors) and max(errors) <= RECONCILIATION_TOLERANCE,
        "max_cost_reconciliation_error": max(cost_errors) if cost_errors else math.inf,
        "cost_reconciliation_pass": bool(cost_errors) and max(cost_errors) <= 1e-12,
        "unpriced_exposure_weeks": unpriced_weeks,
        "unpriced_exposure_events": unpriced_events,
        "negative_exposure_weeks": negative_exposure_weeks,
        "maximum_gross_exposure": maximum_gross_exposure,
        "static_multi_asset_zero_turnover": multi_asset_weeks > len(periods) * 0.8 and total_turnover <= 1e-12,
    }
    return periods, audit


def period_returns(periods: list[dict[str, float | str]], cost_bps: float) -> list[float]:
    return [
        float(period["reported_gross"]) - float(period["turnover"]) * cost_bps / 10_000.0
        for period in periods
    ]


def aligned_returns(
    periods: list[dict[str, float | str]], by_date: dict[str, float]
) -> tuple[list[dict[str, float | str]], list[float]]:
    selected = [period for period in periods if str(period["realization_date"]) in by_date]
    return selected, [by_date[str(period["realization_date"])] for period in selected]


def grade_strategy(
    *, audit: dict[str, float | int | bool], manifest_entry: dict[str, object] | None, years: float
) -> tuple[str, list[str]]:
    flags = [
        "research_and_selection_used_this_history_not_an_untouched_holdout",
        "multiple_testing_across_33_saved_strategies",
        "current_etf_universe_can_create_survivorship_selection_bias",
    ]
    if not audit["return_reconstruction_pass"]:
        flags.append("saved_returns_do_not_reconcile_to_dated_positions_and_next_week_returns")
        return "D", flags
    if not audit["cost_reconciliation_pass"]:
        flags.append("saved_costs_do_not_reconcile")
        return "D", flags
    if audit["unpriced_exposure_weeks"]:
        flags.append("nonzero_positions_exist_when_the_asset_return_is_missing")
    if audit["negative_exposure_weeks"]:
        flags.append("short_borrow_and_financing_costs_are_not_fully_modeled")
    if audit["static_multi_asset_zero_turnover"]:
        flags.append("fixed_multi_asset_weights_record_zero_turnover_and_can_imply_free_rebalancing")
    if manifest_entry is None:
        flags.append("no_primary_layer2_manifest_entry")
    else:
        flags.append("lag_is_declared_but_signal_generation_was_not_independently_reexecuted")
    if years < 10.0:
        flags.append("less_than_10_years_of_history")

    if (
        manifest_entry is not None
        and manifest_entry.get("type") != "experimental"
        and not audit["unpriced_exposure_weeks"]
        and not audit["negative_exposure_weeks"]
        and not audit["static_multi_asset_zero_turnover"]
        and years >= 10.0
    ):
        return "B", flags
    return "C", flags


def flatten(prefix: str, values: dict[str, object]) -> dict[str, object]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def build() -> dict[str, object]:
    market = load_market_simple_returns()
    manifest_rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest = {row["strategy_name"]: row for row in manifest_rows}
    names = sorted(
        path.stem.replace("strategy_returns_", "")
        for path in STRATEGY_DIR.glob("strategy_returns_*.csv")
        if (STRATEGY_DIR / path.name.replace("strategy_returns_", "strategy_positions_")).is_file()
    )

    all_periods: dict[str, list[dict[str, float | str]]] = {}
    audits: dict[str, dict[str, float | int | bool]] = {}
    for name in names:
        all_periods[name], audits[name] = reconstruct_strategy(name, market)

    spy_name = "baseline_market_proxy_buy_hold"
    spy_by_date = {
        str(period["realization_date"]): value
        for period, value in zip(all_periods[spy_name], period_returns(all_periods[spy_name], DEFAULT_COST_BPS))
    }
    spy_full_metrics = performance_metrics(list(spy_by_date.values())).to_dict()
    rows: list[dict[str, object]] = []
    detail: dict[str, object] = {}

    for name in names:
        periods, spy_returns = aligned_returns(all_periods[name], spy_by_date)
        returns_10 = period_returns(periods, 10.0)
        returns_25 = period_returns(periods, 25.0)
        returns_50 = period_returns(periods, 50.0)
        full = performance_metrics(returns_10).to_dict()
        recent_indices = [
            index for index, period in enumerate(periods)
            if date.fromisoformat(str(period["realization_date"])) >= RECENT_START
        ]
        recent_returns = [returns_10[index] for index in recent_indices]
        recent_spy = [spy_returns[index] for index in recent_indices]
        recent = performance_metrics(recent_returns).to_dict()
        costs = {
            "annual_return_10bps": full["annual_return"],
            "annual_return_25bps": performance_metrics(returns_25).annual_return,
            "annual_return_50bps": performance_metrics(returns_50).annual_return,
            "sharpe_10bps": full["sharpe_zero_rf"],
            "sharpe_25bps": performance_metrics(returns_25).sharpe_zero_rf,
            "sharpe_50bps": performance_metrics(returns_50).sharpe_zero_rf,
            "average_weekly_turnover": sum(float(period["turnover"]) for period in periods) / len(periods),
        }
        regression = benchmark_regression(returns_10, spy_returns)
        rolling = rolling_window_summary(returns_10, spy_returns)
        seed = int(hashlib.sha256(name.encode()).hexdigest()[:8], 16)
        bootstrap = block_bootstrap_intervals(returns_10, seed=seed)
        grade, flags = grade_strategy(
            audit=audits[name], manifest_entry=manifest.get(name), years=float(full["years"])
        )
        conservative_sharpe = min(
            float(full["sharpe_zero_rf"]),
            float(recent["sharpe_zero_rf"]),
            float(bootstrap["sharpe_ci_low"]),
        )
        row: dict[str, object] = {
            "strategy": name,
            "strategy_type": (manifest.get(name) or {}).get("type", "later_experimental_artifact"),
            "evidence_grade": grade,
            "eligible_for_trustworthy_ranking": grade in {"B", "C"},
            "promotion_status": "research_only_no_untouched_holdout",
            "conservative_sharpe": conservative_sharpe,
            "annual_return_delta_vs_spy": float(full["annual_return"]) - float(spy_full_metrics["annual_return"]),
            "sharpe_delta_vs_spy": float(full["sharpe_zero_rf"]) - float(spy_full_metrics["sharpe_zero_rf"]),
            "bias_flags": ";".join(flags),
            **audits[name],
            **flatten("full", full),
            **flatten("recent", recent),
            **costs,
            **regression,
            **rolling,
            **bootstrap,
        }
        rows.append(row)
        detail[name] = {
            "manifest": manifest.get(name),
            "audit": audits[name],
            "bias_flags": flags,
            "evidence_grade": grade,
            "metrics": {
                "full_10bps": full,
                "recent_since_2021_10bps": recent,
                "cost_stress": costs,
                "benchmark": regression,
                "rolling": rolling,
                "block_bootstrap_95pct": bootstrap,
            },
        }

    grade_order = {"B": 0, "C": 1, "D": 2}
    rows.sort(key=lambda row: (grade_order[str(row["evidence_grade"])], -float(row["conservative_sharpe"])))
    for rank, row in enumerate(rows, start=1):
        row["scoreboard_rank"] = rank

    provenance_files = [MARKET_RETURNS, MANIFEST]
    for name in names:
        provenance_files.extend(
            [
                STRATEGY_DIR / f"strategy_returns_{name}.csv",
                STRATEGY_DIR / f"strategy_positions_{name}.csv",
            ]
        )
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy_count": len(rows),
        "recent_window_start": RECENT_START.isoformat(),
        "recent_window_is_untouched_holdout": False,
        "default_cost_bps_per_unit_turnover": DEFAULT_COST_BPS,
        "stress_cost_bps": list(STRESS_COST_BPS),
        "sharpe_risk_free_rate": 0.0,
        "grades": {grade: sum(row["evidence_grade"] == grade for row in rows) for grade in grade_order},
        "return_reconstruction_passed": sum(bool(row["return_reconstruction_pass"]) for row in rows),
        "cost_reconciliation_passed": sum(bool(row["cost_reconciliation_pass"]) for row in rows),
        "promoted": 0,
    }
    provenance = {
        "source_root": str(V1_DATA.resolve()),
        "files": {
            str(path.relative_to(V1_DATA)): {"sha256": sha256(path), "bytes": path.stat().st_size}
            for path in provenance_files
        },
    }
    artifact_set_hash = hashlib.sha256(
        json.dumps(provenance["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "summary": summary,
        "rows": rows,
        "detail": detail,
        "provenance": provenance,
        "validation_protocol": {
            "protocol_version": 1,
            "locked_at": summary["generated_at"],
            "strategy_artifact_set_sha256": artifact_set_hash,
            "first_genuinely_untouched_week_end": "2026-08-14",
            "minimum_untouched_weeks_before_promotion": 52,
            "interim_review_weeks": 26,
            "parameter_or_logic_change_creates_new_candidate_version": True,
            "promotion_requirements": [
                "point_in_time_universe_and_inputs",
                "independently_reexecuted_signal_lags",
                "return_and_cost_reconciliation",
                "no_nonzero_unpriced_exposure",
                "spread_slippage_and_turnover_stress",
                "benchmark_and_regime_comparison",
                "locked_untouched_forward_period",
            ],
        },
    }


def format_percent(value: object) -> str:
    return f"{float(value) * 100:.2f}%"


def report_markdown(result: dict[str, object]) -> str:
    summary = result["summary"]
    rows = result["rows"]
    assert isinstance(summary, dict) and isinstance(rows, list)
    by_name = {str(row["strategy"]): row for row in rows}
    top = by_name["composite_selective_strength_weighted"]
    spy = by_name["baseline_market_proxy_buy_hold"]
    repair = by_name["composite_trend_quality_refined"]
    lines = [
        "# Bias-Aware Strategy Scoreboard",
        "",
        f"Generated: {str(summary['generated_at'])[:10]}",
        "",
        "This scoreboard shows every saved Layer 2 strategy, including weak and failed",
        "results. It verifies portfolio returns against dated positions and the following",
        "week's market returns, applies turnover costs, and reports uncertainty. It does",
        "not call the 2021+ period an untouched holdout because these strategies were",
        "researched while that history was already available.",
        "",
        "## Executive findings",
        "",
        f"- 33/33 saved return/position pairs are shown; 28 reconstruct exactly and 5 fail reconciliation.",
        f"- Only two rows currently earn Grade B. The strongest non-benchmark Grade B candidate is",
        f"  `composite_selective_strength_weighted`: {format_percent(top['full_annual_return'])} annual return,",
        f"  {float(top['full_sharpe_zero_rf']):.3f} Sharpe, {format_percent(top['full_max_drawdown'])} max drawdown,",
        f"  and {format_percent(top['annual_return_50bps'])} annual return under the 50 bps turnover stress.",
        f"- SPY returned {format_percent(spy['full_annual_return'])} annually with a {float(spy['full_sharpe_zero_rf']):.3f}",
        f"  Sharpe but suffered a much deeper {format_percent(spy['full_max_drawdown'])} drawdown.",
        f"- `composite_trend_quality_refined` is the clearest repair candidate: its headline return",
        f"  ({format_percent(repair['full_annual_return'])}) slightly exceeds SPY, but it remains Grade C because",
        f"  it carries nonzero positions across {repair['unpriced_exposure_weeks']} weeks with missing asset returns.",
        "- No strategy is promoted. The first genuinely untouched forward week is locked to 2026-08-14;",
        "  changing strategy logic after the lock creates a new candidate version.",
        "",
        "## Evidence grades",
        "",
        "- **B:** return and cost accounting reconcile, a lag convention is documented,",
        "  at least ten years are available, no nonzero holding lacks a price return,",
        "  and no unmodeled short financing or free multi-asset rebalancing is detected.",
        "- **C:** accounting reconciles, but missing-price exposure or missing primary",
        "  manifest evidence reduces trust.",
        "- **D:** saved returns do not reproduce from dated positions and next-week returns;",
        "  numbers are visible but excluded from trustworthy ranking.",
        "- No strategy can receive A yet: there is no genuinely untouched holdout after",
        "  the research process, and signal generation has not been independently rebuilt.",
        "",
        "## Results",
        "",
        "| Rank | Strategy | Grade | Ann. return | Sharpe | Max DD | Recent Sharpe | 50 bps return | vs SPY return | Conservative Sharpe |",
        "|---:|---|:---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['scoreboard_rank']} | `{row['strategy']}` | {row['evidence_grade']} | "
            f"{format_percent(row['full_annual_return'])} | {float(row['full_sharpe_zero_rf']):.3f} | "
            f"{format_percent(row['full_max_drawdown'])} | {float(row['recent_sharpe_zero_rf']):.3f} | "
            f"{format_percent(row['annual_return_50bps'])} | {format_percent(row['annual_return_delta_vs_spy'])} | "
            f"{float(row['conservative_sharpe']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation rules",
            "",
            "1. Compare Grade B before Grade C; do not rank Grade D by performance.",
            "2. Prefer conservative Sharpe, recent behavior, drawdown, and 50 bps cost",
            "   stress over the highest full-period return.",
            "3. A positive backtest is a research candidate, not proof of future profit.",
            "4. The current ETF universe and repeated strategy search create survivorship",
            "   and multiple-testing risk for every row.",
            "5. Promotion remains blocked until strategies are rebuilt from point-in-time",
            "   inputs and evaluated on a newly locked, genuinely untouched period.",
            "",
            "Machine-readable details and every bias flag are in `strategy_scoreboard.json`.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_csv(path: Path, rows: Iterable[dict[str, object]]) -> None:
    values = list(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(values[0]))
        writer.writeheader()
        writer.writerows(values)


def main() -> int:
    result = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT / "strategy_scoreboard.csv", result["rows"])
    (OUTPUT / "strategy_scoreboard.json").write_text(
        json.dumps({"summary": result["summary"], "strategies": result["detail"]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "provenance.json").write_text(
        json.dumps(result["provenance"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT / "validation_protocol.json").write_text(
        json.dumps(result["validation_protocol"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUTPUT / "report.md").write_text(report_markdown(result), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
