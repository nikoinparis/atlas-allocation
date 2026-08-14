#!/usr/bin/env python3
"""Attempt to falsify the frozen three-tier recent-return leader."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_growth_three_tier_falsification_v1.json"
THREE_TIER_ENGINE = ROOT / "scripts/run_sec_growth_three_tier_cap_frequency_v1.py"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
SOURCE_EVIDENCE = ROOT / "evidence/sec_growth_three_tier_cap_frequency_v1"
OUTPUT = ROOT / "evidence/sec_growth_three_tier_falsification_v1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_signal(
    aligned: pd.DataFrame,
    prices: pd.DataFrame,
    quarterly_targets: dict[pd.Timestamp, list[str]],
    confidence,
    three,
    lookback: int,
    exceptional_allocation: float,
    breadth: int,
    concentration: float,
    volatility_ratio_limit: float,
) -> pd.DataFrame:
    base = confidence.target_allocations(
        aligned,
        {"lookback_weeks": lookback, "low_allocation": 0.10, "high_allocation": 0.40, "dual_confirmation": False},
        max(26, lookback),
    )
    growth_13 = (1.0 + aligned["growth"].shift(1)).rolling(13, min_periods=13).apply(np.prod, raw=True) - 1.0
    short_vol = aligned["growth"].shift(1).rolling(13, min_periods=13).std(ddof=1) * np.sqrt(52.0)
    long_vol = aligned["growth"].shift(1).rolling(52, min_periods=52).std(ddof=1) * np.sqrt(52.0)
    diagnostics = three.holding_diagnostics(aligned.index, prices, quarterly_targets, 13)
    table = base.join(diagnostics).assign(
        growth_momentum_13w_prior=growth_13,
        volatility_ratio_13w_to_52w=short_vol / long_vol.replace(0.0, np.nan),
    )
    exceptional = (
        table["high_confidence"]
        & table["growth_momentum_13w_prior"].gt(0.0)
        & table["positive_holding_count"].ge(breadth)
        & table["largest_positive_contribution_share"].le(concentration)
        & table["volatility_ratio_13w_to_52w"].le(volatility_ratio_limit)
    )
    allocation = table["target_growth_allocation"].copy()
    allocation.loc[exceptional] = exceptional_allocation
    return table.assign(target_growth_allocation=allocation, exceptional_confidence=exceptional)


def delay_targets(targets: dict[pd.Timestamp, list[str]], index: pd.DatetimeIndex, weeks: int) -> dict[pd.Timestamp, list[str]]:
    positions = {date: offset for offset, date in enumerate(index)}
    delayed: dict[pd.Timestamp, list[str]] = {}
    for date, assets in targets.items():
        offset = positions.get(date)
        if offset is not None and offset + weeks < len(index):
            delayed[index[offset + weeks]] = assets
    return delayed


def metrics(path: pd.DataFrame, three) -> dict[str, dict[str, float | int | str]]:
    return {name: three.metric_row(sample) for name, sample in three.windows(path).items()}


def ticker_map() -> dict[str, str]:
    rows = pd.read_csv(GROWTH_EVIDENCE / "selected_price_sources.csv", dtype={"cik10": str})
    output: dict[str, str] = {}
    for row in rows.itertuples(index=False):
        cik = str(row.cik10).zfill(10)
        name = Path(str(row.price_file)).name.split(".")[0]
        output[cik] = name if name != "prices" else cik
    return output


def main() -> int:
    config = json.loads(CONFIG.read_text())
    three = load_module("three_tier_engine", THREE_TIER_ENGINE)
    universal = load_module("universal_engine", three.UNIVERSAL_ENGINE)
    cap = load_module("cap_engine", universal.CAP_ENGINE)
    confidence = load_module("confidence_engine", universal.CONFIDENCE_ENGINE)
    growth = cap.load_growth_engine()

    choices = pd.read_csv(GROWTH_EVIDENCE / "portfolio_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True)
    selected_assets = sorted(set(choices["cik10"]))
    reference = pd.read_csv(GROWTH_EVIDENCE / "path_growth__base__50bps.csv", parse_dates=["Date"])
    index = pd.DatetimeIndex(reference["Date"].tolist() + [pd.Timestamp("2026-08-14")]).drop_duplicates().sort_values()
    sources, terminals = growth.price_sources(), growth.terminal_dates()
    prices = pd.DataFrame(index=index)
    for asset in selected_assets:
        source_spec = sources.get(asset)
        if source_spec is not None:
            source, path = source_spec
            try:
                prices[asset] = growth.read_weekly_price(path, source, index, terminals.get(asset))
            except (pd.errors.EmptyDataError, FileNotFoundError):
                continue
    quarterly_targets = growth.build_targets(choices, index)
    monthly_dates = cap.month_review_dates(index)
    weekly_dates = set(index[:-1])
    gross_incumbent = cap.incumbent_returns(0.0).reindex(index).fillna(0.0)
    gross_growth = pd.read_csv(GROWTH_EVIDENCE / "path_growth__base__50bps.csv", parse_dates=["Date"]).set_index("Date")["gross_return"]
    aligned = pd.concat([gross_incumbent.rename("incumbent"), gross_growth.rename("growth")], axis=1, join="inner").dropna()
    frozen_signal = build_signal(aligned, prices, quarterly_targets, confidence, three, 26, 0.60, 3, 0.60, 1.50)
    balanced_signal = build_signal(aligned, prices, quarterly_targets, confidence, three, 26, 0.50, 3, 0.60, 1.50)
    control_signal = confidence.target_allocations(aligned, {"lookback_weeks": 26, "low_allocation": 0.10, "high_allocation": 0.40, "dual_confirmation": False}, 26)

    incumbent_50 = cap.incumbent_returns(50.0).reindex(index).fillna(0.0)
    leader_path = universal.simulate(prices, quarterly_targets, incumbent_50, frozen_signal["target_growth_allocation"], 1.5, "base", 50.0, weekly_dates)
    control_path = universal.simulate(prices, quarterly_targets, incumbent_50, control_signal["target_growth_allocation"], 1.5, "base", 50.0, monthly_dates)
    leader_metrics, control_metrics = metrics(leader_path, three), metrics(control_path, three)

    tickers = ticker_map()
    leave_rows: list[dict[str, object]] = []
    for tested_variant, tested_signal in (("leader_60", frozen_signal), ("balanced_50", balanced_signal)):
        for asset in selected_assets:
            path = universal.simulate(prices, quarterly_targets, incumbent_50, tested_signal["target_growth_allocation"], 1.5, "base", 50.0, weekly_dates, excluded_assets={asset})
            for window, result in metrics(path, three).items():
                leave_rows.append({"tested_variant": tested_variant, "cik10": asset, "ticker": tickers.get(asset, asset), "window": window, **result})
    leave_one_out = pd.DataFrame(leave_rows)

    delay_rows: list[dict[str, object]] = []
    for weeks in config["signal_delays_weeks"]:
        delayed_signal = frozen_signal["target_growth_allocation"].shift(int(weeks)).fillna(0.10)
        path = universal.simulate(prices, quarterly_targets, incumbent_50, delayed_signal, 1.5, "base", 50.0, weekly_dates)
        for window, result in metrics(path, three).items():
            delay_rows.append({"delay_type": "allocation_signal", "delay_weeks": int(weeks), "window": window, **result})
    for weeks in config["selection_delays_weeks"]:
        delayed_selections = delay_targets(quarterly_targets, index, int(weeks))
        path = universal.simulate(prices, delayed_selections, incumbent_50, frozen_signal["target_growth_allocation"], 1.5, "base", 50.0, weekly_dates)
        for window, result in metrics(path, three).items():
            delay_rows.append({"delay_type": "selection_execution", "delay_weeks": int(weeks), "window": window, **result})
    delayed = pd.DataFrame(delay_rows)

    grid = config["parameter_neighborhood"]
    neighborhood_rows: list[dict[str, object]] = []
    for lookback in grid["relative_lookback_weeks"]:
        for allocation in grid["exceptional_allocation"]:
            for breadth in grid["minimum_positive_holdings"]:
                for concentration in grid["maximum_positive_contribution_share"]:
                    for vol_ratio in grid["maximum_volatility_ratio"]:
                        signal = build_signal(aligned, prices, quarterly_targets, confidence, three, int(lookback), float(allocation), int(breadth), float(concentration), float(vol_ratio))
                        path = universal.simulate(prices, quarterly_targets, incumbent_50, signal["target_growth_allocation"], 1.5, "base", 50.0, weekly_dates)
                        sample_metrics = metrics(path, three)
                        row: dict[str, object] = {
                            "lookback_weeks": int(lookback), "exceptional_allocation": float(allocation),
                            "minimum_positive_holdings": int(breadth), "maximum_positive_contribution_share": float(concentration),
                            "maximum_volatility_ratio": float(vol_ratio), "exceptional_share": float(signal["exceptional_confidence"].mean()),
                        }
                        for window in ("since_incumbent_holdout_start", "trailing_2y", "trailing_1y", "ytd"):
                            for metric in ("cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight", "annual_total_turnover"):
                                row[f"{window}__{metric}"] = sample_metrics[window][metric]
                        neighborhood_rows.append(row)
    neighborhood = pd.DataFrame(neighborhood_rows)

    extreme_rows: list[dict[str, object]] = []
    for cost_bps in config["extreme_cost_bps"]:
        incumbent = cap.incumbent_returns(float(cost_bps)).reindex(index).fillna(0.0)
        for variant, signal, reviews in (("leader", frozen_signal["target_growth_allocation"], weekly_dates), ("control", control_signal["target_growth_allocation"], monthly_dates)):
            path = universal.simulate(prices, quarterly_targets, incumbent, signal, 1.5, "base", float(cost_bps), reviews)
            for window, result in metrics(path, three).items():
                extreme_rows.append({"variant": variant, "cost_bps": int(cost_bps), "window": window, **result})
    extreme_costs = pd.DataFrame(extreme_rows)

    bundle_config = json.loads(cap.FREQUENCY_CONFIG.read_text())
    bundle = ROOT / "data/ggg_vintages" / bundle_config["data_bundle"] / "data/01_data_hub/weekly_prices.csv"
    market = cap.read_dated_csv(bundle).apply(pd.to_numeric, errors="coerce")
    market_returns = market.pct_change(fill_method=None)
    trailing13 = market.pct_change(13, fill_method=None)
    spy_vol = market_returns["SPY"].rolling(26, min_periods=26).std(ddof=1) * np.sqrt(52.0)
    vol_threshold = float(spy_vol.median())
    regimes = pd.DataFrame(index=leader_path.index)
    regimes["market_direction"] = np.where(trailing13["SPY"].reindex(regimes.index) > 0.0, "rising", "falling")
    regimes["volatility"] = np.where(spy_vol.reindex(regimes.index) >= vol_threshold, "high_vol", "low_vol")
    regimes["leadership"] = np.where(trailing13["XLK"].reindex(regimes.index) > trailing13["XLE"].reindex(regimes.index), "technology_led", "energy_led")
    regimes = regimes.join(leader_path["net_return"].rename("leader")).join(control_path["net_return"].rename("control"))
    regime_rows: list[dict[str, object]] = []
    for dimension in ("market_direction", "volatility", "leadership"):
        for state, sample in regimes.groupby(dimension):
            regime_rows.append({
                "dimension": dimension, "state": state, "weeks": len(sample),
                "leader_annualized_arithmetic_return": float(sample["leader"].mean() * 52.0),
                "control_annualized_arithmetic_return": float(sample["control"].mean() * 52.0),
                "annualized_return_difference": float((sample["leader"] - sample["control"]).mean() * 52.0),
                "leader_win_rate": float((sample["leader"] > 0.0).mean()),
            })
    regimes_summary = pd.DataFrame(regime_rows)

    concentration = pd.read_csv(GROWTH_EVIDENCE / "holding_period_concentration.csv", dtype={"cik10": str})
    positive = concentration[concentration["equal_weight_return_contribution"] > 0.0].copy()
    period_positive = positive.groupby("effective_date")["equal_weight_return_contribution"].transform("sum")
    positive["positive_contribution_share"] = positive["equal_weight_return_contribution"] / period_positive
    period_dominance = positive.groupby("effective_date").agg(
        largest_positive_contribution_share=("positive_contribution_share", "max"),
        dominant_company=("company_name", lambda values: values.iloc[positive.loc[values.index, "positive_contribution_share"].argmax()] if len(values) else ""),
    ).reset_index()

    gates_config = config["promotion_gates"]
    leader_recent = leader_metrics["trailing_1y"]
    leader_holdout = leader_metrics["since_incumbent_holdout_start"]
    control_recent = control_metrics["trailing_1y"]
    baseline_improvement = float(leader_recent["cagr"] - control_recent["cagr"])
    leave_recent = leave_one_out[(leave_one_out["window"] == "trailing_1y") & (leave_one_out["tested_variant"] == "leader_60")].copy()
    leave_recent["improvement_vs_control"] = leave_recent["cagr"] - float(control_recent["cagr"])
    worst_exclusion_improvement = float(leave_recent["improvement_vs_control"].min())
    balanced_path = universal.simulate(prices, quarterly_targets, incumbent_50, balanced_signal["target_growth_allocation"], 1.5, "base", 50.0, weekly_dates)
    balanced_recent_cagr = float(metrics(balanced_path, three)["trailing_1y"]["cagr"])
    balanced_leave = leave_one_out[(leave_one_out["window"] == "trailing_1y") & (leave_one_out["tested_variant"] == "balanced_50")].copy()
    balanced_leave["improvement_vs_control"] = balanced_leave["cagr"] - float(control_recent["cagr"])
    balanced_worst_exclusion_improvement = float(balanced_leave["improvement_vs_control"].min())
    neighborhood["positive_recent_and_holdout_improvement"] = (
        neighborhood["trailing_1y__cagr"].gt(float(control_recent["cagr"]))
        & neighborhood["since_incumbent_holdout_start__cagr"].gt(float(control_metrics["since_incumbent_holdout_start"]["cagr"]))
    )
    neighborhood_positive_share = float(neighborhood["positive_recent_and_holdout_improvement"].mean())
    delay_one = delayed[(delayed["delay_type"] == "allocation_signal") & (delayed["delay_weeks"] == 1) & (delayed["window"] == "trailing_1y")].iloc[0]
    gates = {
        "trailing_1y_cagr": float(leader_recent["cagr"]) >= float(gates_config["minimum_trailing_1y_cagr"]),
        "holdout_cagr": float(leader_holdout["cagr"]) >= float(gates_config["minimum_holdout_cagr"]),
        "trailing_1y_sharpe": float(leader_recent["sharpe_zero_rf"]) >= float(gates_config["minimum_trailing_1y_sharpe"]),
        "single_exclusion_does_not_destroy_half_improvement": worst_exclusion_improvement >= baseline_improvement * (1.0 - float(gates_config["maximum_fraction_of_improvement_destroyed_by_one_exclusion"])),
        "parameter_neighborhood": neighborhood_positive_share >= float(gates_config["minimum_positive_parameter_neighborhood_share"]),
        "one_week_delay_positive_recent_improvement": float(delay_one["cagr"]) > float(control_recent["cagr"]),
    }
    checks = {
        "all_selected_stocks_excluded_once_per_tier": bool(all(
            set(group["cik10"].unique()) == set(selected_assets)
            for _, group in leave_one_out.groupby("tested_variant")
        )),
        "complete_parameter_grid": len(neighborhood) == 3 * 3 * 2 * 3 * 3,
        "all_outputs_finite": bool(all(
            np.isfinite(frame.select_dtypes(include=[np.number])).all().all()
            for frame in (leave_one_out, delayed, neighborhood, extreme_costs, regimes_summary)
        )),
        "frozen_leader_reproduced": abs(float(leader_recent["cagr"]) - 1.104877) < 1e-6,
        "control_reproduced": abs(float(control_recent["cagr"]) - 0.923104) < 1e-6,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    leave_one_out.to_csv(OUTPUT / "leave_one_stock_out.csv", index=False)
    delayed.to_csv(OUTPUT / "delay_stress.csv", index=False)
    neighborhood.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    extreme_costs.to_csv(OUTPUT / "extreme_costs.csv", index=False)
    regimes_summary.to_csv(OUTPUT / "regime_decomposition.csv", index=False)
    period_dominance.to_csv(OUTPUT / "holding_period_contribution_dominance.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "promotion_gates": gates, "all_promotion_gates_passed": bool(all(gates.values())),
        "baseline_trailing_1y_cagr_improvement": baseline_improvement,
        "worst_leave_one_out_trailing_1y_improvement": worst_exclusion_improvement,
        "balanced_50_trailing_1y_cagr": balanced_recent_cagr,
        "balanced_50_worst_leave_one_out_improvement": balanced_worst_exclusion_improvement,
        "parameter_neighborhood_positive_share": neighborhood_positive_share,
        "selection_or_live_trading_authorized": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    worst = leave_recent.sort_values("improvement_vs_control").head(12)
    balanced_worst = balanced_leave.sort_values("improvement_vs_control").head(12)
    lines = [
        "# Three-tier leader falsification v1", "",
        "The frozen leader was tested without changing its formula. Every historically selected stock was removed once and replaced by the ETF incumbent; allocation and selection were delayed; 162 neighboring parameter combinations were run; 300/500-bps costs and three regime decompositions were added.", "",
        f"Promotion gates passed: **{all(gates.values())}**. This remains post-selection research and does not authorize live trading.", "",
        "## Promotion gates", "",
        *[f"- {'PASS' if passed else 'FAIL'} — `{name}`" for name, passed in gates.items()], "",
        "## Worst trailing-one-year exclusions", "",
        worst[["ticker", "cagr", "sharpe_zero_rf", "max_drawdown", "improvement_vs_control"]].to_csv(index=False),
        "", "## Balanced 50% tier worst exclusions", "",
        balanced_worst[["ticker", "cagr", "sharpe_zero_rf", "max_drawdown", "improvement_vs_control"]].to_csv(index=False),
    ]
    (OUTPUT / "report.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    print("\nWorst exclusions:\n", worst[["ticker", "cagr", "sharpe_zero_rf", "max_drawdown", "improvement_vs_control"]].to_string(index=False))
    print("\nBalanced 50% worst exclusions:\n", balanced_worst[["ticker", "cagr", "sharpe_zero_rf", "max_drawdown", "improvement_vs_control"]].to_string(index=False))
    print("\nDelay stress:\n", delayed[delayed["window"].isin(["since_incumbent_holdout_start", "trailing_1y", "ytd"])][["delay_type", "delay_weeks", "window", "cagr", "sharpe_zero_rf", "max_drawdown"]].to_string(index=False))
    print("\nExtreme costs:\n", extreme_costs[extreme_costs["window"].isin(["since_incumbent_holdout_start", "trailing_1y"])][["variant", "cost_bps", "window", "cagr", "sharpe_zero_rf", "max_drawdown"]].to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
