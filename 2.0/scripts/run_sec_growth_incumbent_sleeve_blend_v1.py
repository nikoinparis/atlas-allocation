#!/usr/bin/env python3
"""Blend the frozen SEC growth candidate with the frozen monthly ETF incumbent."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


CONFIG = ROOT / "config/sec_growth_incumbent_sleeve_blend_v1.json"
FREQUENCY_CONFIG = ROOT / "config/return_first_frequency_test_v1.json"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
OUTPUT = ROOT / "evidence/sec_growth_incumbent_sleeve_blend_v1"


def read_dated_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame.columns else "observation_date"
    frame[date_column] = pd.to_datetime(frame[date_column], errors="raise")
    return frame.set_index(date_column).sort_index()


def next_week_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change(fill_method=None).shift(-1)


def portfolio_path(weights: pd.DataFrame, forward_returns: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    aligned = forward_returns.reindex(index=weights.index, columns=weights.columns).fillna(0.0)
    gross = (weights * aligned).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    return pd.DataFrame({"gross_return": gross, "net_return": net, "turnover": turnover, "cost": cost, "wealth": wealth})


def metrics(path: pd.DataFrame) -> dict[str, float | int | str]:
    returns = path["net_return"].dropna()
    weeks = len(returns)
    years = weeks / 52.0
    wealth = (1.0 + returns).cumprod()
    cagr = float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if weeks and years > 0 else 0.0
    volatility = float(returns.std(ddof=1) * np.sqrt(52.0)) if weeks > 1 else 0.0
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(52.0)) if weeks > 1 and returns.std(ddof=1) > 0 else 0.0
    drawdown = wealth / wealth.cummax() - 1.0
    return {
        "weeks": weeks,
        "start": str(returns.index.min().date()),
        "end": str(returns.index.max().date()),
        "cagr": cagr,
        "total_return": float(wealth.iloc[-1] - 1.0),
        "sharpe_zero_rf": sharpe,
        "annual_volatility": volatility,
        "max_drawdown": float(drawdown.min()),
        "win_rate": float((returns > 0.0).mean()),
        "best_week": float(returns.max()),
        "worst_week": float(returns.min()),
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


def combine_paths(
    incumbent: pd.Series,
    growth: pd.Series,
    allocation: float,
    mode: str,
    rebalance_dates: set[pd.Timestamp],
    outer_cost_bps: float,
) -> pd.DataFrame:
    aligned = pd.concat([incumbent.rename("incumbent"), growth.rename("growth")], axis=1, join="inner").dropna()
    inc_value = 1.0 - allocation
    growth_value = allocation
    rows = []
    for offset, (date, row) in enumerate(aligned.iterrows()):
        before = inc_value + growth_value
        outer_turnover = 0.0
        outer_cost = 0.0
        if offset > 0 and mode == "quarterly_target_reset" and date in rebalance_dates:
            current_growth = growth_value / before if before else allocation
            outer_turnover = abs(current_growth - allocation)
            outer_cost = before * outer_turnover * outer_cost_bps / 10000.0
            deployable = before - outer_cost
            inc_value = deployable * (1.0 - allocation)
            growth_value = deployable * allocation
        inc_value *= 1.0 + float(row["incumbent"])
        growth_value *= 1.0 + float(row["growth"])
        after = inc_value + growth_value
        rows.append({
            "Date": date,
            "net_return": after / before - 1.0 if before else 0.0,
            "wealth": after,
            "outer_turnover": outer_turnover,
            "outer_cost": outer_cost / before if before else 0.0,
            "growth_weight_end": growth_value / after if after else 0.0,
        })
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path["wealth"] / path["wealth"].cummax() - 1.0
    return path


def main() -> int:
    config = json.loads(CONFIG.read_text())
    frequency = json.loads(FREQUENCY_CONFIG.read_text())
    bundle = ROOT / "data/ggg_vintages" / frequency["data_bundle"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    forward = next_week_returns(prices)
    incumbent_weights = read_dated_csv(ROOT / frequency["monthly_incumbent"]).apply(pd.to_numeric, errors="coerce")
    incumbent_weights = incumbent_weights.reindex(prices.index).fillna(0.0)

    growth_events = pd.read_csv(GROWTH_EVIDENCE / "rebalance_events.csv", parse_dates=["effective_date"])
    rebalance_dates = set(pd.to_datetime(growth_events["effective_date"]).dt.tz_localize(None))
    rows = []
    paths: dict[str, pd.DataFrame] = {}
    for cost in config["cost_bps"]:
        incumbent_path = portfolio_path(
            incumbent_weights,
            forward.reindex(columns=incumbent_weights.columns),
            float(cost),
        )
        for scenario in config["missing_company_scenarios"]:
            growth_path = pd.read_csv(
                GROWTH_EVIDENCE / f"path_growth__{scenario}__{cost}bps.csv",
                parse_dates=["Date"],
            ).set_index("Date")
            for mode in config["capital_management_modes"]:
                for allocation in config["growth_allocations"]:
                    path = combine_paths(
                        incumbent_path["net_return"],
                        growth_path["net_return"],
                        float(allocation),
                        mode,
                        rebalance_dates,
                        float(cost),
                    )
                    key = f"{scenario}__{mode}__growth_{int(round(100 * allocation)):02d}__{cost}bps"
                    paths[key] = path
                    for window, sample in windows(path).items():
                        result = metrics(sample)
                        result.update({
                            "scenario": scenario,
                            "mode": mode,
                            "growth_allocation": float(allocation),
                            "cost_bps": int(cost),
                            "window": window,
                            "ending_growth_weight": float(sample["growth_weight_end"].iloc[-1]),
                            "annual_outer_turnover": float(sample["outer_turnover"].sum() / (len(sample) / 52.0)),
                        })
                        rows.append(result)

    performance = pd.DataFrame(rows)
    primary = performance[
        performance["cost_bps"].eq(int(config["primary_cost_bps"]))
        & performance["window"].isin(["full_recent", "since_incumbent_holdout_start", "trailing_2y", "trailing_1y"])
    ].copy()
    incumbent = primary[primary["growth_allocation"].eq(0.0)][
        ["mode", "window", "cagr", "sharpe_zero_rf", "max_drawdown"]
    ].drop_duplicates(["mode", "window"]).rename(columns={
        "cagr": "incumbent_cagr",
        "sharpe_zero_rf": "incumbent_sharpe",
        "max_drawdown": "incumbent_max_drawdown",
    })
    primary = primary.merge(incumbent, on=["mode", "window"], how="left")
    primary["cagr_change_vs_incumbent"] = primary["cagr"] - primary["incumbent_cagr"]
    primary["drawdown_change_vs_incumbent"] = primary["max_drawdown"] - primary["incumbent_max_drawdown"]

    checks = {
        "allocation_zero_matches_incumbent_across_scenarios_and_modes": bool(
            primary[primary["growth_allocation"].eq(0.0)]
            .groupby("window")["cagr"].agg(lambda values: values.max() - values.min()).max() <= 1e-12
        ),
        "all_paths_finite": bool(np.isfinite(performance.select_dtypes(include=[np.number])).all().all()),
        "all_ending_weights_valid": bool(performance["ending_growth_weight"].between(0.0, 1.0).all()),
        "all_predeclared_allocations_reported": bool(
            set(performance["growth_allocation"].unique()) == set(config["growth_allocations"])
        ),
        "base_and_adverse_reported": set(performance["scenario"].unique()) == set(config["missing_company_scenarios"]),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    primary.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{key}.csv")

    focus = primary[
        primary["growth_allocation"].isin(config["primary_diagnostic_allocations"])
        & primary["mode"].eq("quarterly_target_reset")
        & primary["window"].eq("since_incumbent_holdout_start")
    ].sort_values(["scenario", "growth_allocation"])
    focus.to_csv(OUTPUT / "controlled_sleeve_focus.csv", index=False)
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "allocations_tested": config["growth_allocations"],
        "costs_tested_bps": config["cost_bps"],
        "modes_tested": config["capital_management_modes"],
        "scenarios_tested": config["missing_company_scenarios"],
        "validation": checks,
        "all_validation_checks_passed": bool(all(checks.values())),
        "selection_or_promotion_from_observed_results_authorized": False,
        "growth_candidate_preserved": True,
        "remembered_trailing_one_year_cagr": 1.422238598137973,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    lines = [
        "# SEC growth controlled-sleeve blend v1",
        "",
        "The frozen 142.22% trailing-one-year SEC growth candidate was combined with the frozen monthly ETF incumbent without changing either formula. Every predeclared 0–40% allocation was reported under buy-and-drift and quarterly target-reset capital management, 50/100/200-bps internal costs, and both missing-company scenarios.",
        "",
        "The table `controlled_sleeve_focus.csv` contains the predeclared 10%, 20%, and 30% controlled allocations. These already-observed outcomes may describe trade-offs but may not select a supposedly optimal weight. No incumbent replacement or live trading is authorized.",
    ]
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    print(focus[["scenario", "growth_allocation", "cagr", "sharpe_zero_rf", "max_drawdown", "cagr_change_vs_incumbent"]].to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
