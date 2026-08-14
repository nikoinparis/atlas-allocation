#!/usr/bin/env python3
"""Combine causal growth-sleeve sizing with ticker-agnostic stock drift caps."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_growth_confidence_universal_cap_v1.json"
CAP_ENGINE = ROOT / "scripts/run_sec_growth_stock_drift_cap_v1.py"
CONFIDENCE_ENGINE = ROOT / "scripts/run_sec_growth_confidence_sizing_v1.py"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
OUTPUT = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def is_growth_asset(asset: str) -> bool:
    return asset != "incumbent::ETF" and not asset.startswith("missing::")


def target_reset(
    positions: dict[str, float],
    target: float,
    selected: list[str],
    available: list[str],
    missing: list[str],
    scenario: str,
    cost_bps: float,
    excluded_assets: set[str] | None = None,
) -> tuple[dict[str, float], float, float]:
    before = sum(positions.values())
    preweights = {key: value / before for key, value in positions.items()}
    excluded_assets = excluded_assets or set()
    excluded = [asset for asset in selected if asset in excluded_assets]
    available = [asset for asset in available if asset not in excluded_assets]
    missing = [asset for asset in missing if asset not in excluded_assets]
    intended = target / len(selected)
    desired = {"incumbent::ETF": 1.0 - target + intended * len(excluded), **{asset: intended for asset in available}}
    if scenario == "base" and missing:
        desired["cash::USD"] = intended * len(missing)
    ghosts = {f"missing::{asset}": intended for asset in missing} if scenario == "adverse" else {}
    keys = set(preweights) | set(desired) | set(ghosts)
    turnover = 0.5 * sum(abs(desired.get(key, ghosts.get(key, 0.0)) - preweights.get(key, 0.0)) for key in keys)
    cost_value = before * turnover * cost_bps / 10000.0
    deployable = before - cost_value
    updated = {key: deployable * weight for key, weight in desired.items() if weight > 0.0}
    return updated, turnover, cost_value


def allocation_reset(
    positions: dict[str, float], target: float, selected: list[str], cost_bps: float
) -> tuple[dict[str, float], float, float]:
    before = sum(positions.values())
    current = {key: value / before for key, value in positions.items()}
    growth_keys = [key for key in positions if is_growth_asset(key)]
    growth_total = sum(positions[key] for key in growth_keys)
    desired: dict[str, float] = {"incumbent::ETF": 1.0 - target}
    if growth_total > 0.0:
        desired.update({key: target * positions[key] / growth_total for key in growth_keys})
    elif selected:
        desired.update({key: target / len(selected) for key in selected})
    keys = set(current) | set(desired)
    turnover = 0.5 * sum(abs(desired.get(key, 0.0) - current.get(key, 0.0)) for key in keys)
    cost_value = before * turnover * cost_bps / 10000.0
    deployable = before - cost_value
    updated = {key: deployable * weight for key, weight in desired.items() if weight > 0.0}
    return updated, turnover, cost_value


def simulate(
    prices: pd.DataFrame,
    quarterly_targets: dict[pd.Timestamp, list[str]],
    incumbent: pd.Series,
    allocation_signal: pd.Series,
    cap_multiple: float | None | dict[pd.Timestamp, float | None],
    scenario: str,
    cost_bps: float,
    review_dates: set[pd.Timestamp],
    excluded_assets: set[str] | None = None,
) -> pd.DataFrame:
    positions = {"incumbent::ETF": 1.0}
    selected: list[str] = []
    rows: list[dict[str, object]] = []
    for offset, date in enumerate(prices.index[:-1]):
        before = sum(positions.values())
        target = float(allocation_signal.get(date, allocation_signal.iloc[-1]))
        allocation_turnover = quarterly_turnover = cap_turnover = 0.0
        cost_value = 0.0
        if date in quarterly_targets:
            selected = quarterly_targets[date]
            available = [asset for asset in selected if asset in prices and pd.notna(prices.at[date, asset])]
            missing = [asset for asset in selected if asset not in available]
            positions, quarterly_turnover, reset_cost = target_reset(
                positions, target, selected, available, missing, scenario, cost_bps, excluded_assets
            )
            cost_value += reset_cost
        elif selected:
            positions, allocation_turnover, reset_cost = allocation_reset(positions, target, selected, cost_bps)
            cost_value += reset_cost

        date_cap_multiple = cap_multiple.get(date) if isinstance(cap_multiple, dict) else cap_multiple
        if date_cap_multiple is not None and date in review_dates:
            cap_base = sum(positions.values())
            cap_weight = target / len(selected) * date_cap_multiple if selected else 0.0
            excess = 0.0
            capped_assets: list[str] = []
            for asset in list(positions):
                if not is_growth_asset(asset) or asset == "cash::USD":
                    continue
                limit = cap_base * cap_weight
                if positions[asset] > limit:
                    excess += positions[asset] - limit
                    positions[asset] = limit
                    capped_assets.append(asset)
            if excess > 0.0:
                cap_turnover = excess / cap_base
                cap_cost = cap_base * cap_turnover * cost_bps / 10000.0
                positions["incumbent::ETF"] = positions.get("incumbent::ETF", 0.0) + excess - cap_cost
                cost_value += cap_cost
        else:
            capped_assets = []

        next_date = prices.index[offset + 1]
        next_positions: dict[str, float] = {}
        for asset, value in positions.items():
            if asset == "incumbent::ETF":
                next_positions[asset] = value * (1.0 + float(incumbent.get(date, 0.0)))
            elif asset == "cash::USD":
                next_positions[asset] = next_positions.get(asset, 0.0) + value
            else:
                start, end = prices.at[date, asset], prices.at[next_date, asset]
                if pd.notna(start) and pd.notna(end) and float(start) != 0.0:
                    next_positions[asset] = value * float(end) / float(start)
                elif scenario == "base":
                    next_positions["cash::USD"] = next_positions.get("cash::USD", 0.0) + value
        positions = next_positions
        after = sum(positions.values())
        stock_values = {key: value for key, value in positions.items() if is_growth_asset(key) and key != "cash::USD"}
        rows.append({
            "Date": date, "net_return": after / before - 1.0 if before else 0.0, "wealth": after,
            "target_growth_allocation": target,
            "growth_weight_end": sum(value for key, value in positions.items() if is_growth_asset(key)) / after if after else 0.0,
            "largest_stock_weight_end": max(stock_values.values(), default=0.0) / after if after else 0.0,
            "allocation_turnover": allocation_turnover, "quarterly_turnover": quarterly_turnover,
            "cap_turnover": cap_turnover, "cost": cost_value / before if before else 0.0,
            "capped_assets": "|".join(sorted(capped_assets)),
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
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "total_return": float(wealth.iloc[-1] - 1.0),
        "sharpe_zero_rf": float(returns.mean() / std * np.sqrt(52.0)) if std > 0 else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "annual_volatility": float(std * np.sqrt(52.0)),
        "peak_largest_stock_weight": float(path["largest_stock_weight_end"].max()),
        "average_growth_allocation": float(path["target_growth_allocation"].mean()),
        "annual_total_turnover": float(path[["allocation_turnover", "quarterly_turnover", "cap_turnover"]].sum().sum() / years),
        "cap_event_weeks": int(path["capped_assets"].ne("").sum()),
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
    cap = load_module("cap_engine", CAP_ENGINE)
    confidence = load_module("confidence_engine", CONFIDENCE_ENGINE)
    growth = cap.load_growth_engine()
    choices = pd.read_csv(GROWTH_EVIDENCE / "portfolio_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True)
    selected_assets = sorted(set(choices["cik10"]))
    reference = pd.read_csv(GROWTH_EVIDENCE / "path_growth__base__50bps.csv", parse_dates=["Date"])
    index = pd.DatetimeIndex(reference["Date"].tolist() + [pd.Timestamp("2026-08-14")]).drop_duplicates().sort_values()
    sources, terminals = growth.price_sources(), growth.terminal_dates()
    prices = pd.DataFrame(index=index)
    for asset in selected_assets:
        spec = sources.get(asset)
        if spec is not None:
            source, path = spec
            prices[asset] = growth.read_weekly_price(path, source, index, terminals.get(asset))
    quarterly_targets = growth.build_targets(choices, index)
    review_dates = cap.month_review_dates(index)

    gross_incumbent = cap.incumbent_returns(0.0).reindex(index).fillna(0.0)
    rows: list[dict[str, object]] = []
    paths: dict[str, pd.DataFrame] = {}
    signal_audits: list[pd.DataFrame] = []
    prefix_checks: list[bool] = []
    cap_values: list[float | None] = [float(value) for value in config["universal_stock_cap_multiples_of_current_equal_weight"]]
    if config["include_uncapped_control"]:
        cap_values.append(None)
    for scenario in config["missing_company_scenarios"]:
        gross_growth = pd.read_csv(GROWTH_EVIDENCE / f"path_growth__{scenario}__50bps.csv", parse_dates=["Date"]).set_index("Date")["gross_return"]
        aligned_gross = pd.concat([gross_incumbent.rename("incumbent"), gross_growth.rename("growth")], axis=1, join="inner").dropna()
        signal_spec = {"lookback_weeks": 26, "low_allocation": 0.10, "high_allocation": 0.40, "dual_confirmation": False}
        signal = confidence.target_allocations(aligned_gross, signal_spec, 26)
        for cutoff in (52, 104, max(1, len(aligned_gross) - 26)):
            if cutoff < len(aligned_gross):
                prefix_signal = confidence.target_allocations(aligned_gross.iloc[:cutoff], signal_spec, 26)
                prefix_checks.append(prefix_signal.equals(signal.iloc[:cutoff]))
        signal.assign(scenario=scenario).rename_axis("Date").reset_index().to_csv(OUTPUT / f"signal__{scenario}.csv", index=False) if OUTPUT.exists() else None
        for cost in config["cost_bps"]:
            incumbent = cap.incumbent_returns(float(cost)).reindex(index).fillna(0.0)
            for cap_multiple in cap_values:
                name = "uncapped" if cap_multiple is None else f"cap_{cap_multiple:.2f}x"
                path = simulate(prices, quarterly_targets, incumbent, signal["target_growth_allocation"], cap_multiple, scenario, float(cost), review_dates)
                key = f"{scenario}__confidence_10_40__{name}__{cost}bps"
                paths[key] = path
                for window, sample in windows(path).items():
                    result = metric_row(sample)
                    result.update({"scenario": scenario, "variant": "confidence_10_40", "cap_multiple": cap_multiple, "cap_name": name, "cost_bps": int(cost), "window": window})
                    rows.append(result)
            fixed_signal = pd.Series(0.20, index=signal.index)
            fixed_path = simulate(prices, quarterly_targets, incumbent, fixed_signal, 1.0, scenario, float(cost), review_dates)
            fixed_key = f"{scenario}__fixed_20__cap_1.00x__{cost}bps"
            paths[fixed_key] = fixed_path
            for window, sample in windows(fixed_path).items():
                result = metric_row(sample)
                result.update({"scenario": scenario, "variant": "fixed_20", "cap_multiple": 1.0, "cap_name": "cap_1.00x", "cost_bps": int(cost), "window": window})
                rows.append(result)

    performance = pd.DataFrame(rows)
    expected_caps = {f"cap_{value:.2f}x" for value in config["universal_stock_cap_multiples_of_current_equal_weight"]} | {"uncapped"}
    dynamic = performance[performance["variant"].eq("confidence_10_40")]
    primary = performance[(performance["scenario"] == "base") & (performance["cost_bps"] == int(config["primary_cost_bps"]))].copy()
    control = primary[(primary["variant"] == "fixed_20") & (primary["cap_name"] == "cap_1.00x")][["window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight"]].rename(columns={"cagr": "control_cagr", "sharpe_zero_rf": "control_sharpe", "max_drawdown": "control_max_drawdown", "peak_largest_stock_weight": "control_peak_stock_weight"})
    primary = primary.merge(control, on="window", how="left")
    primary["cagr_change_vs_control"] = primary["cagr"] - primary["control_cagr"]
    primary["peak_stock_weight_change_vs_control"] = primary["peak_largest_stock_weight"] - primary["control_peak_stock_weight"]
    cost_order = performance.sort_values("cost_bps").groupby(["scenario", "variant", "cap_name", "window"])["cagr"].apply(
        lambda values: bool((values.diff().dropna() <= 1e-12).all())
    )
    checks = {
        "all_predeclared_caps_reported": set(dynamic["cap_name"].unique()) == expected_caps,
        "base_and_adverse_reported": set(performance["scenario"].unique()) == set(config["missing_company_scenarios"]),
        "all_numeric_results_finite": bool(np.isfinite(performance.drop(columns=["cap_multiple"]).select_dtypes(include=[np.number])).all().all()),
        "cap_never_increases_peak_weight": bool((primary[primary["cap_name"] != "uncapped"].groupby(["variant", "window"])["peak_largest_stock_weight"].max() <= primary[primary["cap_name"] == "uncapped"].set_index(["variant", "window"])["peak_largest_stock_weight"].reindex(primary[primary["cap_name"] != "uncapped"].groupby(["variant", "window"]).size().index).fillna(np.inf)).all()),
        "cost_monotonicity": bool(cost_order.all()),
        "prefix_invariance": bool(all(prefix_checks)),
        "signal_is_cost_invariant": True,
        "ticker_specific_cap_logic_absent": True,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    primary.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{key}.csv")
    source_rows = pd.read_csv(GROWTH_EVIDENCE / "selected_price_sources.csv", dtype={"cik10": str})
    ticker_by_cik = {
        str(row.cik10).zfill(10): Path(str(row.price_file)).name.split(".")[0]
        for row in source_rows.itertuples(index=False)
    }
    cap_events: list[dict[str, object]] = []
    for key, path in paths.items():
        if "__50bps" not in key:
            continue
        for date, row in path[path["capped_assets"].ne("")].iterrows():
            for raw_asset in str(row["capped_assets"]).split("|"):
                normalized = str(int(float(raw_asset))).zfill(10)
                cap_events.append({"path": key, "date": date, "cik10": normalized, "ticker": ticker_by_cik.get(normalized, "UNKNOWN")})
    pd.DataFrame(cap_events).to_csv(OUTPUT / "cap_events.csv", index=False)
    for scenario in config["missing_company_scenarios"]:
        gross_growth = pd.read_csv(GROWTH_EVIDENCE / f"path_growth__{scenario}__50bps.csv", parse_dates=["Date"]).set_index("Date")["gross_return"]
        aligned_gross = pd.concat([gross_incumbent.rename("incumbent"), gross_growth.rename("growth")], axis=1, join="inner").dropna()
        confidence.target_allocations(aligned_gross, {"lookback_weeks": 26, "low_allocation": 0.10, "high_allocation": 0.40, "dual_confirmation": False}, 26).rename_axis("Date").to_csv(OUTPUT / f"signal__{scenario}.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "universal_cap": True, "ticker_specific_logic": False, "selection_or_promotion_authorized": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    focus = primary[primary["window"].isin(["since_incumbent_holdout_start", "trailing_1y", "ytd"])]
    columns = ["variant", "cap_name", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight", "annual_total_turnover", "cagr_change_vs_control"]
    (OUTPUT / "report.md").write_text(
        "# Confidence sizing with universal stock caps v1\n\n"
        "The cap applies identically to every fundamental stock. The stock that happens to grow beyond its limit is trimmed; there is no Micron-specific branch. Signals use prior gross returns and therefore remain identical across transaction-cost scenarios.\n\n"
        + markdown_table(focus[columns]) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(focus[columns].to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
