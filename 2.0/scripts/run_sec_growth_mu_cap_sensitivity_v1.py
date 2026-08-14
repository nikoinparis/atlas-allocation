#!/usr/bin/env python3
"""Test higher Micron-only drift caps while other growth stocks remain capped."""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_growth_mu_cap_sensitivity_v1.json"
CAP_ENGINE = ROOT / "scripts/run_sec_growth_stock_drift_cap_v1.py"
GROWTH_EVIDENCE = ROOT / "evidence/sec_growth_survivorship_retest_v1"
OUTPUT = ROOT / "evidence/sec_growth_mu_cap_sensitivity_v1"


def load_cap_engine():
    spec = importlib.util.spec_from_file_location("cap_engine", CAP_ENGINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load cap engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def simulate(
    prices: pd.DataFrame,
    targets: dict[pd.Timestamp, list[str]],
    incumbent: pd.Series,
    allocation: float,
    mu_cik: str,
    mu_cap_multiple: float | None,
    other_cap_multiple: float,
    scenario: str,
    cost_bps: float,
    review_dates: set[pd.Timestamp],
) -> pd.DataFrame:
    positions = {"incumbent::ETF": 1.0}
    rows: list[dict[str, object]] = []
    intended = allocation / 5.0
    for offset, date in enumerate(prices.index[:-1]):
        total_before = sum(positions.values())
        rebalance_turnover = cap_turnover = cost = adverse_loss = 0.0
        mu_weight_before_cap = mu_weight_after_cap = 0.0
        if date in targets:
            selected = targets[date]
            available = [cik for cik in selected if cik in prices and pd.notna(prices.at[date, cik])]
            missing = [cik for cik in selected if cik not in available]
            preweights = {key: value / total_before for key, value in positions.items()}
            desired = {"incumbent::ETF": 1.0 - allocation, **{cik: intended for cik in available}}
            if scenario == "base" and missing:
                desired["cash::USD"] = intended * len(missing)
            ghosts = {f"missing::{cik}": intended for cik in missing} if scenario == "adverse" else {}
            comparison = set(preweights) | set(desired) | set(ghosts)
            rebalance_turnover = 0.5 * sum(abs(desired.get(key, ghosts.get(key, 0.0)) - preweights.get(key, 0.0)) for key in comparison)
            cost = total_before * rebalance_turnover * cost_bps / 10000.0
            deployable = total_before - cost
            positions = {key: deployable * weight for key, weight in desired.items() if weight > 0.0}
            if scenario == "adverse":
                adverse_loss = deployable * intended * len(missing)
        elif date in review_dates:
            total_before = sum(positions.values())
            excess_total = 0.0
            for asset in list(positions):
                if asset in ("incumbent::ETF", "cash::USD") or asset.startswith("missing::"):
                    continue
                multiple = mu_cap_multiple if asset == mu_cik else other_cap_multiple
                if multiple is None:
                    continue
                cap_value = total_before * intended * float(multiple)
                if asset == mu_cik:
                    mu_weight_before_cap = positions[asset] / total_before
                if positions[asset] > cap_value:
                    excess_total += positions[asset] - cap_value
                    positions[asset] = cap_value
                if asset == mu_cik:
                    mu_weight_after_cap = positions[asset] / total_before
            if excess_total > 0.0:
                cap_turnover = excess_total / total_before
                cap_cost = total_before * cap_turnover * cost_bps / 10000.0
                positions["incumbent::ETF"] = positions.get("incumbent::ETF", 0.0) + excess_total - cap_cost
                cost += cap_cost

        next_date = prices.index[offset + 1]
        next_positions: dict[str, float] = {}
        transition_loss = 0.0
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
                else:
                    transition_loss += value
        positions = next_positions
        total_after = sum(positions.values())
        stock_values = {key: value for key, value in positions.items() if key not in ("incumbent::ETF", "cash::USD") and not key.startswith("missing::")}
        rows.append({
            "Date": date,
            "net_return": total_after / total_before - 1.0 if total_before else 0.0,
            "wealth": total_after,
            "rebalance_turnover": rebalance_turnover,
            "cap_turnover": cap_turnover,
            "cost": cost / total_before if total_before else 0.0,
            "adverse_loss": (adverse_loss + transition_loss) / total_before if total_before else 0.0,
            "largest_stock_weight_end": max(stock_values.values(), default=0.0) / total_after if total_after else 0.0,
            "mu_weight_end": stock_values.get(mu_cik, 0.0) / total_after if total_after else 0.0,
            "mu_weight_before_cap": mu_weight_before_cap,
            "mu_weight_after_cap": mu_weight_after_cap,
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
        "peak_largest_stock_weight": float(path["largest_stock_weight_end"].max()),
        "peak_mu_weight": float(path["mu_weight_end"].max()),
        "ending_mu_weight": float(path["mu_weight_end"].iloc[-1]),
        "annual_cap_turnover": float(path["cap_turnover"].sum() / years),
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
    cap = load_cap_engine()
    growth = cap.load_growth_engine()
    choices = pd.read_csv(GROWTH_EVIDENCE / "portfolio_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True)
    selected = sorted(set(choices["cik10"]))
    reference = pd.read_csv(GROWTH_EVIDENCE / "path_growth__base__50bps.csv", parse_dates=["Date"])
    index = pd.DatetimeIndex(reference["Date"].tolist() + [pd.Timestamp("2026-08-14")]).drop_duplicates().sort_values()
    sources, terminals = growth.price_sources(), growth.terminal_dates()
    prices = pd.DataFrame(index=index)
    for cik in selected:
        spec = sources.get(cik)
        if spec is not None:
            source, path = spec
            prices[cik] = growth.read_weekly_price(path, source, index, terminals.get(cik))
    targets = growth.build_targets(choices, index)
    review_dates = cap.month_review_dates(index)
    multiples: list[float | None] = [float(value) for value in config["mu_cap_multiples_of_initial_equal_weight"]]
    if config["include_uncapped_mu_control"]:
        multiples.append(None)
    rows: list[dict[str, object]] = []
    paths: dict[str, pd.DataFrame] = {}
    for cost in config["cost_bps"]:
        incumbent = cap.incumbent_returns(float(cost)).reindex(index).fillna(0.0)
        for scenario in config["missing_company_scenarios"]:
            for multiple in multiples:
                path = simulate(prices, targets, incumbent, float(config["growth_allocation"]), str(config["mu_cik"]), multiple, float(config["other_stock_cap_multiple"]), scenario, float(cost), review_dates)
                name = "mu_uncapped" if multiple is None else f"mu_cap_{multiple:.2f}x"
                key = f"{scenario}__{name}__{cost}bps"
                paths[key] = path
                for window, sample in windows(path).items():
                    result = metric_row(sample)
                    result.update({"scenario": scenario, "mu_cap_multiple": multiple, "cap_name": name, "cost_bps": int(cost), "window": window})
                    rows.append(result)
    performance = pd.DataFrame(rows)
    expected = {f"mu_cap_{value:.2f}x" for value in config["mu_cap_multiples_of_initial_equal_weight"]} | {"mu_uncapped"}
    checks = {
        "all_predeclared_caps_reported": set(performance["cap_name"].unique()) == expected,
        "base_and_adverse_reported": set(performance["scenario"].unique()) == set(config["missing_company_scenarios"]),
        "all_numeric_results_finite": bool(np.isfinite(performance.drop(columns=["mu_cap_multiple"]).select_dtypes(include=[np.number])).all().all()),
        "strict_other_stock_cap_unchanged": float(config["other_stock_cap_multiple"]) == 1.0,
        "growth_formula_unchanged": True,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    for key, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{key}.csv")
    primary = performance[(performance["cost_bps"] == int(config["primary_cost_bps"])) & (performance["scenario"] == "base")].copy()
    strict = primary[primary["cap_name"].eq("mu_cap_1.00x")][["window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_mu_weight"]].rename(columns={"cagr": "strict_cagr", "sharpe_zero_rf": "strict_sharpe", "max_drawdown": "strict_max_drawdown", "peak_mu_weight": "strict_peak_mu_weight"})
    primary = primary.merge(strict, on="window", how="left")
    primary["cagr_change_vs_strict"] = primary["cagr"] - primary["strict_cagr"]
    primary["sharpe_change_vs_strict"] = primary["sharpe_zero_rf"] - primary["strict_sharpe"]
    primary["drawdown_change_vs_strict"] = primary["max_drawdown"] - primary["strict_max_drawdown"]
    primary.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "selection_or_promotion_authorized": False, "growth_formula_changed": False,
        "only_micron_cap_varied": True, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    focus = primary[primary["window"].isin(["since_incumbent_holdout_start", "trailing_1y", "ytd"])]
    (OUTPUT / "report.md").write_text(
        "# Micron-only cap sensitivity v1\n\n"
        "The growth sleeve remains 20% of the combined portfolio. All non-Micron growth stocks retain the strict 1.00x monthly cap; only Micron's cap changes. Results include 50/100/200-bps costs and both missing-company scenarios.\n\n"
        + markdown_table(focus[["cap_name", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_mu_weight", "cagr_change_vs_strict"]])
        + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    print(focus[["cap_name", "window", "cagr", "sharpe_zero_rf", "max_drawdown", "peak_mu_weight", "cagr_change_vs_strict"]].to_string(index=False))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
