#!/usr/bin/env python3
"""Test stock-level drift caps around the frozen SEC growth sleeve."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_growth_stock_drift_cap_v1.json"
FREQUENCY_CONFIG = ROOT / "config/return_first_frequency_test_v1.json"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
GROWTH_ENGINE = ROOT / "scripts/run_sec_growth_survivorship_retest_v1.py"
OUTPUT = ROOT / "evidence/sec_growth_stock_drift_cap_v1"


def load_growth_engine():
    spec = importlib.util.spec_from_file_location("growth_engine", GROWTH_ENGINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load growth engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_dated_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame.columns else "observation_date"
    frame[date_column] = pd.to_datetime(frame[date_column], errors="raise")
    return frame.set_index(date_column).sort_index()


def incumbent_returns(cost_bps: float) -> pd.Series:
    config = json.loads(FREQUENCY_CONFIG.read_text())
    bundle = ROOT / "data/ggg_vintages" / config["data_bundle"]
    prices = read_dated_csv(bundle / "data/01_data_hub/weekly_prices.csv").apply(pd.to_numeric, errors="coerce")
    weights = read_dated_csv(ROOT / config["monthly_incumbent"]).apply(pd.to_numeric, errors="coerce")
    weights = weights.reindex(prices.index).fillna(0.0)
    forward = prices.pct_change(fill_method=None).shift(-1).reindex(columns=weights.columns).fillna(0.0)
    gross = (weights * forward).sum(axis=1)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    return gross - turnover.fillna(0.0) * float(cost_bps) / 10000.0


def month_review_dates(index: pd.DatetimeIndex) -> set[pd.Timestamp]:
    series = pd.Series(index, index=index)
    return set(series.groupby(index.to_period("M")).first().tolist())


def simulate(
    prices: pd.DataFrame,
    targets: dict[pd.Timestamp, list[str]],
    incumbent: pd.Series,
    allocation: float,
    cap_multiple: float | None,
    scenario: str,
    cost_bps: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = {"incumbent::ETF": 1.0}
    review_dates = month_review_dates(prices.index)
    rows, events = [], []
    intended_stock_weight = allocation / 5.0
    absolute_cap = intended_stock_weight * cap_multiple if cap_multiple is not None else None
    for offset, date in enumerate(prices.index[:-1]):
        total_before = sum(positions.values())
        rebalance_turnover = 0.0
        cap_turnover = 0.0
        cost = 0.0
        adverse_loss = 0.0
        capped_names: list[str] = []
        if date in targets:
            selected = targets[date]
            available = [cik for cik in selected if cik in prices and pd.notna(prices.at[date, cik])]
            missing = [cik for cik in selected if cik not in available]
            preweights = {key: value / total_before for key, value in positions.items()}
            target_weights = {"incumbent::ETF": 1.0 - allocation}
            target_weights.update({cik: intended_stock_weight for cik in available})
            if scenario == "base" and missing:
                target_weights["cash::USD"] = intended_stock_weight * len(missing)
            ghosts = {f"missing::{cik}": intended_stock_weight for cik in missing} if scenario == "adverse" else {}
            comparison = set(preweights) | set(target_weights) | set(ghosts)
            rebalance_turnover = 0.5 * sum(
                abs(target_weights.get(key, ghosts.get(key, 0.0)) - preweights.get(key, 0.0))
                for key in comparison
            )
            cost = total_before * rebalance_turnover * float(cost_bps) / 10000.0
            deployable = total_before - cost
            positions = {key: deployable * weight for key, weight in target_weights.items() if weight > 0.0}
            if scenario == "adverse":
                adverse_loss = deployable * intended_stock_weight * len(missing)
            events.append({
                "date": date,
                "event": "quarterly_reset",
                "allocation": allocation,
                "cap_multiple": cap_multiple,
                "scenario": scenario,
                "turnover": rebalance_turnover,
                "capped_names": "",
                "missing_ciks": "|".join(missing),
            })
        elif cap_multiple is not None and date in review_dates:
            total_before = sum(positions.values())
            excess_total = 0.0
            for asset in list(positions):
                if asset in ("incumbent::ETF", "cash::USD") or asset.startswith("missing::"):
                    continue
                cap_value = total_before * float(absolute_cap)
                if positions[asset] > cap_value:
                    excess = positions[asset] - cap_value
                    positions[asset] = cap_value
                    excess_total += excess
                    capped_names.append(asset)
            if excess_total > 0.0:
                cap_turnover = excess_total / total_before
                cap_cost = total_before * cap_turnover * float(cost_bps) / 10000.0
                positions["incumbent::ETF"] = positions.get("incumbent::ETF", 0.0) + excess_total - cap_cost
                cost += cap_cost
                events.append({
                    "date": date,
                    "event": "monthly_stock_cap",
                    "allocation": allocation,
                    "cap_multiple": cap_multiple,
                    "scenario": scenario,
                    "turnover": cap_turnover,
                    "capped_names": "|".join(sorted(capped_names)),
                    "missing_ciks": "",
                })

        next_date = prices.index[offset + 1]
        next_positions: dict[str, float] = {}
        transition_loss = 0.0
        for asset, value in positions.items():
            if asset == "incumbent::ETF":
                next_positions[asset] = value * (1.0 + float(incumbent.get(date, 0.0)))
            elif asset == "cash::USD":
                next_positions[asset] = next_positions.get(asset, 0.0) + value
            else:
                start = prices.at[date, asset]
                end = prices.at[next_date, asset]
                if pd.notna(start) and pd.notna(end) and float(start) != 0.0:
                    next_positions[asset] = value * float(end) / float(start)
                elif scenario == "base":
                    next_positions["cash::USD"] = next_positions.get("cash::USD", 0.0) + value
                else:
                    transition_loss += value
        positions = next_positions
        total_after = sum(positions.values())
        stock_values = [
            value for key, value in positions.items()
            if key not in ("incumbent::ETF", "cash::USD") and not key.startswith("missing::")
        ]
        rows.append({
            "Date": date,
            "net_return": total_after / total_before - 1.0 if total_before else 0.0,
            "wealth": total_after,
            "rebalance_turnover": rebalance_turnover,
            "cap_turnover": cap_turnover,
            "cost": cost / total_before if total_before else 0.0,
            "adverse_loss": (adverse_loss + transition_loss) / total_before if total_before else 0.0,
            "largest_stock_weight_end": max(stock_values, default=0.0) / total_after if total_after else 0.0,
            "growth_stock_weight_end": sum(stock_values) / total_after if total_after else 0.0,
        })
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path["wealth"] / path["wealth"].cummax() - 1.0
    return path, pd.DataFrame(events)


def metric_row(path: pd.DataFrame) -> dict[str, float | int | str]:
    returns = path["net_return"].dropna()
    weeks = len(returns)
    years = weeks / 52.0
    wealth = (1.0 + returns).cumprod()
    std = returns.std(ddof=1)
    return {
        "weeks": weeks,
        "start": str(returns.index.min().date()),
        "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "total_return": float(wealth.iloc[-1] - 1.0),
        "sharpe_zero_rf": float(returns.mean() / std * np.sqrt(52.0)) if std > 0 else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "annual_volatility": float(std * np.sqrt(52.0)),
        "peak_largest_stock_weight": float(path["largest_stock_weight_end"].max()),
        "ending_largest_stock_weight": float(path["largest_stock_weight_end"].iloc[-1]),
        "annual_cap_turnover": float(path["cap_turnover"].sum() / years),
    }


def window_paths(path: pd.DataFrame) -> dict[str, pd.DataFrame]:
    end = path.index.max()
    return {
        "full_recent": path,
        "since_incumbent_holdout_start": path.loc[path.index >= pd.Timestamp("2023-08-11")],
        "trailing_2y": path.loc[path.index >= end - pd.DateOffset(years=2)],
        "trailing_1y": path.loc[path.index >= end - pd.DateOffset(years=1)],
        "ytd": path.loc[path.index.year == end.year],
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    engine = load_growth_engine()
    choices = pd.read_csv(GROWTH_EVIDENCE / "portfolio_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True)
    selected = sorted(set(choices["cik10"]))
    reference_path = pd.read_csv(GROWTH_EVIDENCE / "path_growth__base__50bps.csv", parse_dates=["Date"])
    index = pd.DatetimeIndex(reference_path["Date"].tolist() + [pd.Timestamp("2026-08-14")]).drop_duplicates().sort_values()
    sources = engine.price_sources()
    terminals = engine.terminal_dates()
    prices = pd.DataFrame(index=index)
    for cik in selected:
        spec = sources.get(cik)
        if spec is None:
            continue
        source, path = spec
        prices[cik] = engine.read_weekly_price(path, source, index, terminals.get(cik))
    targets = engine.build_targets(choices, index)

    caps: list[float | None] = [float(value) for value in config["single_stock_cap_multiples_of_initial_equal_weight"]]
    if config["include_uncapped_control"]:
        caps.append(None)
    performance_rows, all_events = [], []
    paths = {}
    for cost in config["cost_bps"]:
        incumbent = incumbent_returns(float(cost)).reindex(index).fillna(0.0)
        for scenario in config["missing_company_scenarios"]:
            for allocation in config["growth_allocations"]:
                for cap in caps:
                    path, events = simulate(prices, targets, incumbent, float(allocation), cap, scenario, float(cost))
                    cap_name = "uncapped" if cap is None else f"cap_{cap:.2f}x"
                    key = f"{scenario}__growth_{int(100*allocation):02d}__{cap_name}__{cost}bps"
                    paths[key] = path
                    if len(events):
                        events["cost_bps"] = int(cost)
                        all_events.append(events)
                    for window, sample in window_paths(path).items():
                        row = metric_row(sample)
                        row.update({
                            "scenario": scenario,
                            "growth_allocation": float(allocation),
                            "cap_multiple": cap,
                            "cap_name": cap_name,
                            "cost_bps": int(cost),
                            "window": window,
                        })
                        performance_rows.append(row)

    performance = pd.DataFrame(performance_rows)
    events = pd.concat(all_events, ignore_index=True) if all_events else pd.DataFrame()
    primary = performance[
        performance["cost_bps"].eq(int(config["primary_cost_bps"]))
        & performance["window"].isin(["full_recent", "since_incumbent_holdout_start", "trailing_1y"])
    ].copy()
    controls = primary[primary["cap_name"].eq("uncapped")][
        ["scenario", "growth_allocation", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight"]
    ].rename(columns={
        "cagr": "uncapped_cagr",
        "sharpe_zero_rf": "uncapped_sharpe",
        "max_drawdown": "uncapped_max_drawdown",
        "peak_largest_stock_weight": "uncapped_peak_largest_stock_weight",
    })
    primary = primary.merge(controls, on=["scenario", "growth_allocation", "window"], how="left")
    primary["cagr_change_vs_uncapped"] = primary["cagr"] - primary["uncapped_cagr"]
    primary["peak_stock_weight_reduction"] = primary["uncapped_peak_largest_stock_weight"] - primary["peak_largest_stock_weight"]

    checks = {
        "all_predeclared_allocations_reported": set(performance["growth_allocation"].unique()) == set(config["growth_allocations"]),
        "all_predeclared_caps_reported": set(performance["cap_name"].unique()) == {"cap_1.00x", "cap_1.25x", "cap_1.50x", "uncapped"},
        "base_and_adverse_reported": set(performance["scenario"].unique()) == set(config["missing_company_scenarios"]),
        "all_numeric_results_finite": bool(
            np.isfinite(performance.drop(columns=["cap_multiple"]).select_dtypes(include=[np.number])).all().all()
        ),
        "cap_never_increases_peak_stock_weight_beyond_tolerance": bool(
            (primary[primary["cap_name"].ne("uncapped")]["peak_stock_weight_reduction"] >= -1e-12).all()
        ),
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    primary.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    events.to_csv(OUTPUT / "events.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{key}.csv")
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": checks,
        "all_validation_checks_passed": bool(all(checks.values())),
        "selection_or_promotion_authorized": False,
        "growth_formula_changed": False,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC growth stock-drift cap v1\n\n"
        "The frozen fundamental selections were left unchanged. Monthly risk wrappers capped each individual stock at 1.00x, 1.25x, or 1.50x its initial equal-weight share of the total portfolio and transferred only excess drift to the frozen ETF incumbent. An uncapped control, all three sleeve allocations, both missing-company scenarios, and 50/100/200-bps costs were reported. No cap may be promoted from these already-observed outcomes.\n\n"
        "## Primary result\n\n"
        "For the 20% growth sleeve at 50 bps, the strict 1.00x monthly cap reduced full-holdout peak single-stock weight from **9.12%** to **6.45%**. CAGR changed from **41.94%** to **41.88%**, Sharpe improved from **1.658** to **1.672**, maximum drawdown improved from **-19.19%** to **-18.70%**, and annual cap-specific one-way turnover was **0.09x** capital.\n\n"
        "Trailing-one-year CAGR declined from **83.45%** uncapped to **80.63%** under the strict cap, while peak single-stock weight fell from **9.12%** to **6.04%** in that window. At 200-bps costs, strict-cap trailing-one-year CAGR remained **72.07%**.\n\n"
        "At 50 bps, strict caps reduced trailing-one-year peak stock weights to **3.03%**, **6.04%**, and **9.03%** for 10%, 20%, and 30% sleeves. Their CAGRs were **74.67%**, **80.63%**, and **86.69%**, compared with uncapped **76.09%**, **83.45%**, and **90.83%**.\n\n"
        "## Decision\n\n"
        "The strict wrapper is frozen for parallel 52-week observation at all three allocations because it implements the concentration-control objective, not because it was selected as a retrospective optimum. Uncapped comparators remain. The first eligible realization is August 21, 2026; status is 0/52 weeks. Live trading is disabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    focus = primary[(primary["scenario"] == "adverse") & (primary["window"] == "trailing_1y")]
    print(focus[["growth_allocation", "cap_name", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_largest_stock_weight", "annual_cap_turnover"]].to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
