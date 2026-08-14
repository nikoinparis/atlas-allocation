#!/usr/bin/env python3
"""Build a multi-strategy Vercel dashboard snapshot from Version 2 evidence."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


APP = Path(__file__).resolve().parents[1]
V2 = APP.parent
WEIGHTS = V2 / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"
PRICES = V2 / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
DAILY_PRICES = V2 / "data/vintages/20260812T035702Z-0c1bf62d74413e2a/payload/prices.csv"
INCUMBENT_RESULT = V2 / "evidence/forward_return_first_60_40_blend_v1/result.json"
INCUMBENT_STATUS = V2 / "evidence/forward_return_first_60_40_blend_v1/status.json"
INCUMBENT_CONFIG = V2 / "config/forward/return_first_60_40_blend_v1.json"
GROWTH = V2 / "evidence/sec_growth_survivorship_retest_v1"
GROWTH_STATUS = V2 / "evidence/sec_growth_stock_drift_cap_v1/forward_status.json"
OUTPUT = APP / "public/return-first-dashboard.json"


def load_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame.columns else "date" if "date" in frame.columns else str(frame.columns[0])
    frame[date_column] = pd.to_datetime(frame[date_column], errors="raise")
    return frame.set_index(date_column).sort_index()


def clean(value: float | int | None) -> float | int | None:
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def records_from_weights(
    weights: pd.DataFrame,
    gross: pd.Series,
    net: pd.Series,
    turnover: pd.Series,
    cost: pd.Series,
    wealth: pd.Series,
    drawdown: pd.Series,
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    previous = pd.Series(0.0, index=weights.columns)
    for date, row in weights.iterrows():
        delta = row - previous
        holdings = [
            {"symbol": str(symbol), "weight": clean(value), "change": clean(delta[symbol])}
            for symbol, value in row.items()
            if abs(float(value)) > 1e-10 or abs(float(delta[symbol])) > 1e-10
        ]
        holdings.sort(key=lambda item: abs(float(item["weight"] or 0.0)), reverse=True)
        records.append({
            "date": date.strftime("%Y-%m-%d"),
            "grossReturn": clean(gross.get(date, 0.0)),
            "netReturn": clean(net.get(date, 0.0)),
            "turnover": clean(turnover.get(date, 0.0)),
            "cost": clean(cost.get(date, 0.0)),
            "wealth": clean(wealth.get(date, 1.0)),
            "drawdown": clean(drawdown.get(date, 0.0)),
            "rebalance": bool((delta.abs() > 1e-8).any()),
            "holdings": holdings,
        })
        previous = row
    return records


def daily_records_from_weights(
    weights: pd.DataFrame,
    daily_prices: pd.DataFrame,
    weekly_net: pd.Series,
    records: list[dict[str, object]],
    terminal_date: pd.Timestamp | None = None,
) -> list[dict[str, object]]:
    rebalance_by_date = {str(record["date"]): bool(record["rebalance"]) for record in records}
    output: list[dict[str, object]] = [{
        "date": weights.index[0].strftime("%Y-%m-%d"),
        "netReturn": 0.0,
        "rebalance": rebalance_by_date[weights.index[0].strftime("%Y-%m-%d")],
        "tradingDay": True,
    }]
    boundaries = list(weights.index)
    if terminal_date is not None and terminal_date > boundaries[-1]:
        boundaries.append(terminal_date)
    for index in range(len(boundaries) - 1):
        decision, realization = boundaries[index], boundaries[index + 1]
        interval = daily_prices.loc[(daily_prices.index > decision) & (daily_prices.index <= realization)]
        if interval.empty:
            continue
        target = weights.loc[decision].drop(labels="cash::USD", errors="ignore")
        base_history = daily_prices.loc[:decision]
        if base_history.empty:
            continue
        base = base_history.ffill().iloc[-1]
        relatives = interval.ffill().divide(base).replace([np.inf, -np.inf], np.nan)
        invested = relatives.mul(target, axis=1).sum(axis=1, min_count=1)
        cash_weight = float(weights.loc[decision].get("cash::USD", 0.0))
        level = (invested + cash_weight).fillna(1.0)
        raw = level.pct_change()
        raw.iloc[0] = float(level.iloc[0] - 1.0)
        desired = 1.0 + float(weekly_net.get(decision, 0.0))
        prior = float((1.0 + raw.iloc[:-1]).prod()) if len(raw) > 1 else 1.0
        raw.iloc[-1] = desired / prior - 1.0
        for day, daily_return in raw.items():
            date_string = day.strftime("%Y-%m-%d")
            output.append({
                "date": date_string,
                "netReturn": clean(daily_return),
                "rebalance": rebalance_by_date.get(date_string, False),
                "tradingDay": True,
            })
    existing = {str(record["date"]) for record in output}
    for date_string, is_rebalance in rebalance_by_date.items():
        if is_rebalance and date_string not in existing:
            output.append({"date": date_string, "netReturn": 0.0, "rebalance": True, "tradingDay": False})
    output.sort(key=lambda record: str(record["date"]))
    return output


def incumbent_payload() -> dict[str, object]:
    weights = load_frame(WEIGHTS).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    prices = load_frame(PRICES).apply(pd.to_numeric, errors="coerce").reindex(weights.index)
    prices["cash::USD"] = 1.0
    prices = prices.reindex(columns=weights.columns)
    forward = prices.pct_change().shift(-1)
    gross = (weights * forward).sum(axis=1).fillna(0.0)
    turnover = 0.5 * weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * 50.0 / 10000.0
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    records = records_from_weights(weights, gross, net, turnover, cost, wealth, drawdown)

    source = pd.read_csv(DAILY_PRICES, usecols=["observation_date", "ticker", "adjusted_close"])
    source["observation_date"] = pd.to_datetime(source["observation_date"], errors="coerce")
    source["adjusted_close"] = pd.to_numeric(source["adjusted_close"], errors="coerce")
    daily = source.pivot_table(index="observation_date", columns="ticker", values="adjusted_close", aggfunc="last").sort_index()
    daily = daily.reindex(columns=[column for column in weights.columns if column != "cash::USD"])
    daily_records = daily_records_from_weights(weights, daily, net, records)

    result = json.loads(INCUMBENT_RESULT.read_text())
    status = json.loads(INCUMBENT_STATUS.read_text())
    config = json.loads(INCUMBENT_CONFIG.read_text())
    return {
        "strategy": {
            "id": result["candidate"],
            "name": "ETF Incumbent — Return-First 60/40",
            "shortName": "ETF Incumbent",
            "subtitle": "Frozen ETF research candidate · 50 bps costs",
            "badge": "41.66% holdout CAGR",
            "asOf": daily_records[-1]["date"],
            "retrospectiveHoldout": {"cagr": result["holdout_50bps_cagr"], "sharpe": result["holdout_50bps_sharpe"], "maxDrawdown": result["holdout_50bps_drawdown"], "start": "2023-08-04"},
            "fullHistory": {"cagr": result["full_50bps_cagr"], "maxDrawdown": result["full_50bps_drawdown"], "start": records[0]["date"]},
            "featuredMetric": {"label": "FROZEN HOLDOUT CAGR", "value": result["holdout_50bps_cagr"], "note": "selected after observing this period"},
            "forward": {"status": status["status"], "observedWeeks": status["observed_weeks"], "requiredWeeks": status["required_weeks"], "firstDecision": config["first_eligible_decision_date"], "firstRealization": config["first_eligible_realization_date"], "note": "The 41.66% holdout result is evidence—not an expectation."},
            "disclosures": {"researchOnly": result["retrospective_research_only"], "liveTradingEnabled": result["live_trading_enabled"], "costBps": 50, "returnConvention": "Weekly decision returns, expanded to daily calendar observations."},
        },
        "records": records,
        "dailyRecords": daily_records,
    }


def growth_sources() -> tuple[dict[str, str], dict[str, pd.Series]]:
    rows = pd.read_csv(GROWTH / "selected_price_sources.csv", dtype={"cik10": str})
    symbol_by_cik: dict[str, str] = {"0001431959": "MMAT"}
    prices: dict[str, pd.Series] = {}
    for row in rows.itertuples(index=False):
        cik = str(row.cik10).zfill(10)
        if not isinstance(row.price_file, str) or not row.price_file:
            continue
        relative = row.price_file.split("/2.0/", 1)[-1]
        path = V2 / relative
        symbol = path.name.split(".", 1)[0]
        symbol_by_cik[cik] = symbol
        frame = pd.read_csv(path)
        if "Date" in frame:
            dates = pd.to_datetime(frame["Date"], errors="coerce")
            values = pd.to_numeric(frame["Adj Close"], errors="coerce")
        else:
            dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
            values = pd.to_numeric(frame["adjClose"], errors="coerce")
        prices[symbol] = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
    return symbol_by_cik, prices


def growth_payload() -> dict[str, object]:
    path = load_frame(GROWTH / "path_growth__base__50bps.csv")
    choices = pd.read_csv(GROWTH / "portfolio_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True).dt.tz_localize(None)
    symbol_by_cik, price_series = growth_sources()
    symbols = sorted(set(symbol_by_cik.values()) | set(price_series))
    weights = pd.DataFrame(0.0, index=path.index, columns=[*symbols, "cash::USD"])
    for date in weights.index:
        eligible = choices[choices["decision_at"] < date]
        if eligible.empty:
            weights.at[date, "cash::USD"] = 1.0
            continue
        latest_decision = eligible["decision_at"].max()
        selected = eligible[eligible["decision_at"].eq(latest_decision)]
        for row in selected.itertuples(index=False):
            symbol = symbol_by_cik.get(str(row.cik10).zfill(10), "MMAT")
            if symbol in price_series:
                weights.at[date, symbol] += 0.2
            else:
                weights.at[date, "cash::USD"] += 0.2
    gross = path["gross_return"]
    net = path["net_return"]
    turnover = path["turnover"]
    cost = path["cost"]
    wealth = path["wealth"]
    drawdown = path["drawdown"]
    records = records_from_weights(weights, gross, net, turnover, cost, wealth, drawdown)
    daily = pd.DataFrame(price_series).sort_index().reindex(columns=[column for column in weights.columns if column != "cash::USD"])
    terminal = daily.index.max()
    daily_records = daily_records_from_weights(weights, daily, net, records, terminal_date=terminal)

    performance = pd.read_csv(GROWTH / "performance.csv")
    def metric(window: str) -> pd.Series:
        return performance[(performance["candidate"] == "growth") & (performance["scenario"] == "base") & (performance["cost_bps"] == 50) & (performance["window"] == window)].iloc[0]
    full, recent = metric("full_recent"), metric("trailing_1y")
    status = json.loads(GROWTH_STATUS.read_text())
    return {
        "strategy": {
            "id": "sec-growth-survivorship-aware-v1",
            "name": "SEC Growth Top-Five — Micron-Led",
            "shortName": "142% Growth / Micron",
            "subtitle": "Standalone fundamental strategy · base missing-stock case · 50 bps",
            "badge": "142.22% trailing 1Y CAGR",
            "asOf": daily_records[-1]["date"],
            "retrospectiveHoldout": {"cagr": recent["cagr"], "sharpe": recent["sharpe_zero_rf"], "maxDrawdown": recent["max_drawdown"], "start": str(recent["start"])},
            "fullHistory": {"cagr": full["cagr"], "maxDrawdown": full["max_drawdown"], "start": str(full["start"])},
            "featuredMetric": {"label": "TRAILING 1Y CAGR", "value": recent["cagr"], "note": "Micron supplied 67.63% of the latest period's positive return"},
            "forward": {"status": status["status"], "observedWeeks": status["observed_weeks"], "requiredWeeks": status["required_weeks"], "firstDecision": "2026-08-14", "firstRealization": status["next_realization"], "note": "The 142.22% result is a historical simulation, not an expected annual return."},
            "disclosures": {"researchOnly": True, "liveTradingEnabled": False, "costBps": 50, "returnConvention": "Quarterly SEC selections with weekly mark-to-market; missing MMAT weight held in cash in the displayed base case."},
        },
        "records": records,
        "dailyRecords": daily_records,
    }


def main() -> int:
    payload = {"strategies": [incumbent_payload(), growth_payload()]}
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(payload['strategies'])} strategies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
