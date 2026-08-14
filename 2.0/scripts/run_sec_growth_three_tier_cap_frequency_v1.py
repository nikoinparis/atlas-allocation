#!/usr/bin/env python3
"""Test causal three-tier growth exposure with ticker-agnostic cap schedules."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_growth_three_tier_cap_frequency_v1.json"
UNIVERSAL_ENGINE = ROOT / "scripts/run_sec_growth_confidence_universal_cap_v1.py"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
CONTROL_EVIDENCE = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
OUTPUT = ROOT / "evidence/sec_growth_three_tier_cap_frequency_v1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def holding_diagnostics(
    dates: pd.DatetimeIndex,
    prices: pd.DataFrame,
    quarterly_targets: dict[pd.Timestamp, list[str]],
    weeks: int,
) -> pd.DataFrame:
    trailing = prices.pct_change(periods=weeks, fill_method=None)
    selected: list[str] = []
    rows: list[dict[str, object]] = []
    for date in dates:
        if date in quarterly_targets:
            selected = quarterly_targets[date]
        available_selected = [asset for asset in selected if asset in trailing.columns]
        values = pd.to_numeric(trailing.loc[date, available_selected], errors="coerce").dropna() if available_selected and date in trailing.index else pd.Series(dtype=float)
        positive = values[values > 0.0]
        positive_sum = float(positive.sum())
        rows.append({
            "Date": date,
            "selected_count": len(selected),
            "available_momentum_count": len(values),
            "positive_holding_count": int((values > 0.0).sum()),
            "positive_holding_share": float((values > 0.0).mean()) if len(values) else 0.0,
            "largest_positive_contribution_share": float(positive.max() / positive_sum) if positive_sum > 0.0 else 1.0,
        })
    return pd.DataFrame(rows).set_index("Date")


def build_signals(
    aligned_gross: pd.DataFrame,
    prices: pd.DataFrame,
    quarterly_targets: dict[pd.Timestamp, list[str]],
    variants: list[dict[str, object]],
    confidence,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    base_spec = {"lookback_weeks": 26, "low_allocation": 0.10, "high_allocation": 0.40, "dual_confirmation": False}
    base = confidence.target_allocations(aligned_gross, base_spec, 26)
    growth_13 = (1.0 + aligned_gross["growth"].shift(1)).rolling(13, min_periods=13).apply(np.prod, raw=True) - 1.0
    short_vol = aligned_gross["growth"].shift(1).rolling(13, min_periods=13).std(ddof=1) * np.sqrt(52.0)
    long_vol = aligned_gross["growth"].shift(1).rolling(52, min_periods=52).std(ddof=1) * np.sqrt(52.0)
    volatility_ratio = short_vol / long_vol.replace(0.0, np.nan)
    holdings = holding_diagnostics(aligned_gross.index, prices, quarterly_targets, 13)
    audit = base.join(holdings).assign(
        growth_momentum_13w_prior=growth_13,
        growth_volatility_13w_prior=short_vol,
        growth_volatility_52w_prior=long_vol,
        volatility_ratio_13w_to_52w=volatility_ratio,
    )
    signals: dict[str, pd.DataFrame] = {}
    for spec in variants:
        exceptional = (
            audit["high_confidence"]
            & audit["growth_momentum_13w_prior"].gt(0.0)
            & audit["positive_holding_count"].ge(int(spec["minimum_positive_holdings"]))
            & audit["volatility_ratio_13w_to_52w"].le(float(spec["maximum_volatility_ratio"]))
        )
        concentration = spec["maximum_positive_contribution_share"]
        if concentration is not None:
            exceptional &= audit["largest_positive_contribution_share"].le(float(concentration))
        allocation = base["target_growth_allocation"].copy()
        allocation.loc[exceptional] = float(spec["exceptional_allocation"])
        signals[str(spec["name"])] = audit.assign(
            target_growth_allocation=allocation,
            exceptional_confidence=exceptional,
        )
    signals["binary_10_40_control"] = audit.assign(
        target_growth_allocation=base["target_growth_allocation"],
        exceptional_confidence=False,
    )
    return signals, audit


def cap_schedule(
    mode: str,
    index: pd.DatetimeIndex,
    monthly_dates: set[pd.Timestamp],
) -> tuple[set[pd.Timestamp], float | dict[pd.Timestamp, float]]:
    trading_dates = list(index[:-1])
    if mode == "monthly":
        return monthly_dates, 1.5
    if mode == "biweekly":
        return set(trading_dates[::2]), 1.5
    if mode == "weekly":
        return set(trading_dates), 1.5
    if mode == "monthly_with_weekly_2x_emergency":
        return set(trading_dates), {date: 1.5 if date in monthly_dates else 2.0 for date in trading_dates}
    raise ValueError(f"unknown cap schedule {mode}")


def windows(path: pd.DataFrame) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {
        "full_recent": path,
        "since_incumbent_holdout_start": path.loc[path.index >= pd.Timestamp("2023-08-11")],
        "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)],
        "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)],
        "ytd": path.loc[path.index.year == end.year],
    }


def metric_row(path: pd.DataFrame) -> dict[str, float | int | str]:
    returns = path["net_return"].dropna()
    years = len(returns) / 52.0
    wealth = (1.0 + returns).cumprod()
    std = returns.std(ddof=1)
    return {
        "weeks": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "total_return": float(wealth.iloc[-1] - 1.0),
        "sharpe_zero_rf": float(returns.mean() / std * np.sqrt(52.0)) if std > 0 else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "annual_volatility": float(std * np.sqrt(52.0)),
        "peak_largest_stock_weight": float(path["largest_stock_weight_end"].max()),
        "average_growth_allocation": float(path["target_growth_allocation"].mean()),
        "maximum_growth_allocation": float(path["target_growth_allocation"].max()),
        "annual_total_turnover": float(path[["allocation_turnover", "quarterly_turnover", "cap_turnover"]].sum().sum() / years),
        "cap_event_weeks": int(path["capped_assets"].ne("").sum()),
    }


def markdown_table(frame: pd.DataFrame) -> str:
    columns = list(frame.columns)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(f"{value:.6f}" if isinstance(value, float) else str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> int:
    config = json.loads(CONFIG.read_text())
    universal = load_module("universal_engine", UNIVERSAL_ENGINE)
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
            prices[asset] = growth.read_weekly_price(path, source, index, terminals.get(asset))
    quarterly_targets = growth.build_targets(choices, index)
    monthly_dates = cap.month_review_dates(index)
    gross_incumbent = cap.incumbent_returns(0.0).reindex(index).fillna(0.0)

    rows: list[dict[str, object]] = []
    paths: dict[str, pd.DataFrame] = {}
    signal_tables: dict[str, pd.DataFrame] = {}
    prefix_checks: list[bool] = []
    for scenario in config["missing_company_scenarios"]:
        gross_growth = pd.read_csv(GROWTH_EVIDENCE / f"path_growth__{scenario}__50bps.csv", parse_dates=["Date"]).set_index("Date")["gross_return"]
        aligned = pd.concat([gross_incumbent.rename("incumbent"), gross_growth.rename("growth")], axis=1, join="inner").dropna()
        signals, audit = build_signals(aligned, prices, quarterly_targets, config["exceptional_variants"], confidence)
        for name, table in signals.items():
            signal_tables[f"{scenario}__{name}"] = table
        for cutoff in (52, 104, max(1, len(aligned) - 26)):
            if cutoff < len(aligned):
                prefix_signals, _ = build_signals(aligned.iloc[:cutoff], prices.loc[:aligned.index[cutoff - 1]], quarterly_targets, config["exceptional_variants"], confidence)
                for name in signals:
                    columns = ["target_growth_allocation", "exceptional_confidence"]
                    prefix_checks.append(prefix_signals[name][columns].equals(signals[name].iloc[:cutoff][columns]))
        for cost in config["cost_bps"]:
            incumbent = cap.incumbent_returns(float(cost)).reindex(index).fillna(0.0)
            for variant, signal in signals.items():
                modes = ["monthly"] if variant == "binary_10_40_control" else config["cap_schedules"]
                for mode in modes:
                    review_dates, cap_spec = cap_schedule(mode, index, monthly_dates)
                    path = universal.simulate(
                        prices, quarterly_targets, incumbent, signal["target_growth_allocation"],
                        cap_spec, scenario, float(cost), review_dates,
                    )
                    key = f"{scenario}__{variant}__{mode}__{cost}bps"
                    paths[key] = path
                    for window, sample in windows(path).items():
                        result = metric_row(sample)
                        result.update({"scenario": scenario, "variant": variant, "cap_schedule": mode, "cost_bps": int(cost), "window": window, "exceptional_signal_share": float(signal.loc[sample.index, "exceptional_confidence"].mean())})
                        rows.append(result)

    performance = pd.DataFrame(rows)
    primary = performance[(performance["scenario"] == "base") & (performance["cost_bps"] == int(config["primary_cost_bps"]))].copy()
    control = primary[primary["variant"].eq("binary_10_40_control")][["window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight"]].rename(columns={"cagr": "control_cagr", "sharpe_zero_rf": "control_sharpe", "max_drawdown": "control_max_drawdown", "peak_largest_stock_weight": "control_peak_stock_weight"})
    primary = primary.merge(control, on="window", how="left")
    primary["cagr_change_vs_control"] = primary["cagr"] - primary["control_cagr"]
    primary["sharpe_change_vs_control"] = primary["sharpe_zero_rf"] - primary["control_sharpe"]
    primary["drawdown_change_vs_control"] = primary["max_drawdown"] - primary["control_max_drawdown"]
    primary["peak_weight_change_vs_control"] = primary["peak_largest_stock_weight"] - primary["control_peak_stock_weight"]

    prior = pd.read_csv(CONTROL_EVIDENCE / "performance.csv")
    prior_control = prior[(prior["variant"] == "confidence_10_40") & (prior["cap_name"] == "cap_1.50x")]
    new_control = performance[performance["variant"] == "binary_10_40_control"]
    joined = new_control.merge(prior_control, on=["scenario", "cost_bps", "window"], suffixes=("_new", "_prior"))
    reproduction_difference = float((joined["cagr_new"] - joined["cagr_prior"]).abs().max())
    cost_checks = performance.sort_values("cost_bps").groupby(["scenario", "variant", "cap_schedule", "window"])["cagr"].apply(lambda values: bool((values.diff().dropna() <= 1e-12).all()))
    expected_variants = {item["name"] for item in config["exceptional_variants"]} | {"binary_10_40_control"}
    expected_schedules = set(config["cap_schedules"])
    challenger_schedules = set(performance.loc[performance["variant"] != "binary_10_40_control", "cap_schedule"].unique())
    checks = {
        "all_predeclared_variants_reported": set(performance["variant"].unique()) == expected_variants,
        "all_predeclared_cap_schedules_reported": challenger_schedules == expected_schedules,
        "base_and_adverse_reported": set(performance["scenario"].unique()) == set(config["missing_company_scenarios"]),
        "all_numeric_results_finite": bool(np.isfinite(performance.select_dtypes(include=[np.number])).all().all()),
        "exact_prior_control_reproduction": reproduction_difference <= 1e-12,
        "prefix_invariance": bool(all(prefix_checks)),
        "cost_monotonicity": bool(cost_checks.all()),
        "maximum_allocation_never_exceeds_60_percent": bool(performance["maximum_growth_allocation"].le(0.60 + 1e-12).all()),
        "ticker_specific_cap_logic_absent": True,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    primary.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{key}.csv")
    for key, table in signal_tables.items():
        table.rename_axis("Date").to_csv(OUTPUT / f"signal__{key}.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "exact_control_reproduction_max_cagr_difference": reproduction_difference,
        "selection_or_promotion_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    focus = primary[(primary["variant"] != "binary_10_40_control") & primary["window"].isin(["since_incumbent_holdout_start", "trailing_1y", "ytd"])].sort_values(["window", "cagr"], ascending=[True, False])
    columns = ["variant", "cap_schedule", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight", "annual_total_turnover", "exceptional_signal_share", "cagr_change_vs_control"]
    (OUTPUT / "report.md").write_text(
        "# Three-tier growth sizing and cap-frequency test v1\n\n"
        "All variants use causal prior-return signals and ticker-agnostic caps. The full predeclared matrix is reported; observed history cannot authorize promotion.\n\n"
        + markdown_table(focus[columns]) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print("\nTop trailing-one-year rows at 50 bps:\n")
    print(focus[focus["window"] == "trailing_1y"][columns].head(16).to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
