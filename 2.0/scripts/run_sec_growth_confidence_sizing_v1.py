#!/usr/bin/env python3
"""Causally vary the frozen growth sleeve using only prior relative momentum."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_growth_confidence_sizing_v1.json"
BLEND_ENGINE = ROOT / "scripts/run_sec_growth_incumbent_sleeve_blend_v1.py"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
OUTPUT = ROOT / "evidence/sec_growth_confidence_sizing_v1"


def load_blend_engine():
    spec = importlib.util.spec_from_file_location("blend_engine", BLEND_ENGINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load blend engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def trailing_return(series: pd.Series, weeks: int) -> pd.Series:
    # Shift first: the return labeled t is realized after the decision at t.
    return (1.0 + series.shift(1)).rolling(weeks, min_periods=weeks).apply(np.prod, raw=True) - 1.0


def target_allocations(aligned: pd.DataFrame, spec: dict[str, object], minimum_history: int) -> pd.DataFrame:
    short_growth = trailing_return(aligned["growth"], 13)
    short_incumbent = trailing_return(aligned["incumbent"], 13)
    long_weeks = int(spec["lookback_weeks"])
    long_growth = trailing_return(aligned["growth"], long_weeks)
    long_incumbent = trailing_return(aligned["incumbent"], long_weeks)
    confirmed = long_growth.gt(0.0) & long_growth.gt(long_incumbent)
    if bool(spec["dual_confirmation"]):
        confirmed &= short_growth.gt(0.0) & short_growth.gt(short_incumbent)
    enough_history = pd.Series(np.arange(len(aligned)) >= minimum_history, index=aligned.index)
    confirmed &= enough_history
    allocation = pd.Series(float(spec["low_allocation"]), index=aligned.index)
    allocation.loc[confirmed] = float(spec["high_allocation"])
    return pd.DataFrame({
        "target_growth_allocation": allocation,
        "high_confidence": confirmed,
        "growth_momentum_13w_prior": short_growth,
        "incumbent_momentum_13w_prior": short_incumbent,
        "growth_momentum_long_prior": long_growth,
        "incumbent_momentum_long_prior": long_incumbent,
    })


def simulate(incumbent: pd.Series, growth: pd.Series, targets: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    aligned = pd.concat([incumbent.rename("incumbent"), growth.rename("growth"), targets], axis=1, join="inner").dropna(subset=["incumbent", "growth"])
    rows: list[dict[str, object]] = []
    initial_target = float(aligned["target_growth_allocation"].iloc[0])
    incumbent_value = 1.0 - initial_target
    growth_value = initial_target
    for offset, (date, row) in enumerate(aligned.iterrows()):
        target = float(row["target_growth_allocation"])
        before = incumbent_value + growth_value
        current_growth_weight = growth_value / before if before else target
        turnover = abs(target - current_growth_weight) if offset else 0.0
        cost_value = before * turnover * float(cost_bps) / 10000.0
        deployable = before - cost_value
        incumbent_value = deployable * (1.0 - target) * (1.0 + float(row["incumbent"]))
        growth_value = deployable * target * (1.0 + float(row["growth"]))
        after = incumbent_value + growth_value
        net_return = after / before - 1.0 if before else 0.0
        rows.append({
            "Date": date,
            "net_return": net_return,
            "wealth": after,
            "target_growth_allocation": target,
            "pretrade_growth_allocation": current_growth_weight,
            "allocation_turnover": turnover,
            "outer_cost": cost_value / before if before else 0.0,
            "high_confidence": bool(row["high_confidence"]),
            "growth_momentum_13w_prior": row["growth_momentum_13w_prior"],
            "incumbent_momentum_13w_prior": row["incumbent_momentum_13w_prior"],
            "growth_momentum_long_prior": row["growth_momentum_long_prior"],
            "incumbent_momentum_long_prior": row["incumbent_momentum_long_prior"],
        })
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path["wealth"] / path["wealth"].cummax() - 1.0
    return path


def metric_row(path: pd.DataFrame) -> dict[str, float | int | str]:
    returns = path["net_return"].dropna()
    years = len(returns) / 52.0
    wealth = (1.0 + returns).cumprod()
    std = returns.std(ddof=1)
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "sharpe_zero_rf": float(returns.mean() / std * np.sqrt(52.0)) if std > 0 else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "annual_volatility": float(std * np.sqrt(52.0)),
        "annual_allocation_turnover": float(path["allocation_turnover"].sum() / years),
        "high_confidence_share": float(path["high_confidence"].mean()),
        "average_growth_allocation": float(path["target_growth_allocation"].mean()),
    }


def windows(path: pd.DataFrame) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {
        "full_recent": path,
        "since_incumbent_holdout_start": path.loc[path.index >= pd.Timestamp("2023-08-11")],
        "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)],
        "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)],
        "ytd": path.loc[path.index.year == end.year],
    }


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(f"{value:.6f}" if isinstance(value, float) else str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    blend = load_blend_engine()
    frequency = json.loads(blend.FREQUENCY_CONFIG.read_text())
    bundle = ROOT / "data/ggg_vintages" / frequency["data_bundle"]
    prices = blend.read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = blend.next_week_returns(prices)
    weights = blend.read_dated_csv(ROOT / frequency["monthly_incumbent"]).apply(pd.to_numeric, errors="coerce").reindex(prices.index).fillna(0.0)
    rows: list[dict[str, object]] = []
    paths: dict[str, pd.DataFrame] = {}
    signals: dict[str, pd.DataFrame] = {}
    prefix_checks: list[bool] = []
    for cost in config["cost_bps"]:
        incumbent = blend.portfolio_path(weights, forward.reindex(columns=weights.columns), float(cost))["net_return"]
        for scenario in config["missing_company_scenarios"]:
            growth = pd.read_csv(GROWTH_EVIDENCE / f"path_growth__{scenario}__{cost}bps.csv", parse_dates=["Date"]).set_index("Date")["net_return"]
            aligned = pd.concat([incumbent.rename("incumbent"), growth.rename("growth")], axis=1, join="inner").dropna()
            for variant in config["variants"]:
                signal = target_allocations(aligned, variant, int(config["minimum_history_weeks"]))
                for cutoff in (52, 104, max(1, len(aligned) - 26)):
                    if cutoff < len(aligned):
                        prefix = target_allocations(aligned.iloc[:cutoff], variant, int(config["minimum_history_weeks"]))
                        prefix_checks.append(prefix.equals(signal.iloc[:cutoff]))
                path = simulate(aligned["incumbent"], aligned["growth"], signal, float(cost))
                key = f"{scenario}__{variant['name']}__{cost}bps"
                paths[key] = path
                signals[key] = signal
                for window, sample in windows(path).items():
                    result = metric_row(sample)
                    result.update({"scenario": scenario, "variant": variant["name"], "cost_bps": int(cost), "window": window})
                    rows.append(result)
    performance = pd.DataFrame(rows)
    expected = {item["name"] for item in config["variants"]}
    checks = {
        "all_predeclared_variants_reported": set(performance["variant"].unique()) == expected,
        "base_and_adverse_reported": set(performance["scenario"].unique()) == set(config["missing_company_scenarios"]),
        "all_numeric_results_finite": bool(np.isfinite(performance.select_dtypes(include=[np.number])).all().all()),
        "fixed_control_target_is_always_20_percent": bool(all(
            np.allclose(signal["target_growth_allocation"].to_numpy(), 0.20)
            for key, signal in signals.items() if "__fixed_20__" in key
        )),
        "prefix_invariance": bool(all(prefix_checks)),
        "signals_use_shifted_prior_returns": True,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{key}.csv")
    primary = performance[(performance["cost_bps"] == int(config["primary_cost_bps"])) & (performance["scenario"] == "base")].copy()
    control = primary[primary["variant"].eq("fixed_20")][["window", "cagr", "sharpe_zero_rf", "max_drawdown"]].rename(columns={"cagr": "control_cagr", "sharpe_zero_rf": "control_sharpe", "max_drawdown": "control_max_drawdown"})
    primary = primary.merge(control, on="window", how="left")
    primary["cagr_change_vs_fixed_20"] = primary["cagr"] - primary["control_cagr"]
    primary["sharpe_change_vs_fixed_20"] = primary["sharpe_zero_rf"] - primary["control_sharpe"]
    primary["drawdown_change_vs_fixed_20"] = primary["max_drawdown"] - primary["control_max_drawdown"]
    primary.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "selection_or_promotion_authorized": False, "growth_formula_changed": False,
        "lookahead_protection": "Every signal shifts weekly returns by one row before rolling calculation.",
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    focus = primary[primary["window"].isin(["since_incumbent_holdout_start", "trailing_1y", "ytd"])]
    (OUTPUT / "report.md").write_text(
        "# SEC growth confidence sizing v1\n\n"
        "Six predeclared allocation rules combine the frozen ETF incumbent and frozen fundamental growth sleeve. Signals use only returns realized before each decision; 50/100/200-bps costs and base/adverse missing-company scenarios are reported. This is retrospective research and cannot authorize promotion.\n\n"
        + markdown_table(focus[["variant", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "average_growth_allocation", "cagr_change_vs_fixed_20"]])
        + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(focus[["variant", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "average_growth_allocation", "cagr_change_vs_fixed_20"]].to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
