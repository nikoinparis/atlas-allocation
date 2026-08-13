#!/usr/bin/env python3
"""Build the Vercel dashboard snapshot from the frozen Version 2 strategy artifacts."""

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
RESULT = V2 / "evidence/forward_return_first_60_40_blend_v1/result.json"
STATUS = V2 / "evidence/forward_return_first_60_40_blend_v1/status.json"
CONFIG = V2 / "config/forward/return_first_60_40_blend_v1.json"
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


def main() -> int:
    weights = load_frame(WEIGHTS).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    prices = load_frame(PRICES).apply(pd.to_numeric, errors="coerce").reindex(weights.index)
    prices["cash::USD"] = 1.0
    prices = prices.reindex(columns=weights.columns)

    ordinary_returns = prices.pct_change()
    forward_returns = ordinary_returns.shift(-1)
    gross = (weights * forward_returns).sum(axis=1).fillna(0.0)
    turnover = 0.5 * weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * 50.0 / 10000.0
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0

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
        changed = bool((delta.abs() > 1e-8).any())
        records.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "grossReturn": clean(gross.loc[date]),
                "netReturn": clean(net.loc[date]),
                "turnover": clean(turnover.loc[date]),
                "cost": clean(cost.loc[date]),
                "wealth": clean(wealth.loc[date]),
                "drawdown": clean(drawdown.loc[date]),
                "rebalance": changed,
                "holdings": holdings,
            }
        )
        previous = row

    daily_source = pd.read_csv(
        DAILY_PRICES,
        usecols=["observation_date", "ticker", "adjusted_close"],
    )
    daily_source["observation_date"] = pd.to_datetime(daily_source["observation_date"], errors="coerce")
    daily_source["adjusted_close"] = pd.to_numeric(daily_source["adjusted_close"], errors="coerce")
    daily_prices = daily_source.pivot_table(
        index="observation_date",
        columns="ticker",
        values="adjusted_close",
        aggfunc="last",
    ).sort_index()
    daily_prices = daily_prices.reindex(columns=[column for column in weights.columns if column != "cash::USD"])

    rebalance_by_date = {record["date"]: bool(record["rebalance"]) for record in records}
    daily_records: list[dict[str, object]] = [
        {
            "date": weights.index[0].strftime("%Y-%m-%d"),
            "netReturn": 0.0,
            "rebalance": rebalance_by_date[weights.index[0].strftime("%Y-%m-%d")],
            "tradingDay": True,
        }
    ]
    for index in range(len(weights.index) - 1):
        decision = weights.index[index]
        realization = weights.index[index + 1]
        interval = daily_prices.loc[(daily_prices.index > decision) & (daily_prices.index <= realization)]
        if interval.empty:
            continue
        target = weights.iloc[index].drop(labels="cash::USD", errors="ignore")
        base = daily_prices.loc[:decision].iloc[-1]
        relatives = interval.divide(base).replace([np.inf, -np.inf], np.nan)
        invested = relatives.mul(target, axis=1).sum(axis=1, min_count=1)
        cash_weight = float(weights.iloc[index].get("cash::USD", 0.0))
        portfolio_level = (invested + cash_weight).fillna(1.0)
        raw_daily = portfolio_level.pct_change()
        raw_daily.iloc[0] = float(portfolio_level.iloc[0] - 1.0)

        desired_multiple = 1.0 + float(net.iloc[index])
        prior_multiple = float((1.0 + raw_daily.iloc[:-1]).prod()) if len(raw_daily) > 1 else 1.0
        raw_daily.iloc[-1] = desired_multiple / prior_multiple - 1.0
        for day, daily_return in raw_daily.items():
            date_string = day.strftime("%Y-%m-%d")
            daily_records.append(
                {
                    "date": date_string,
                    "netReturn": clean(daily_return),
                    "rebalance": rebalance_by_date.get(date_string, False),
                    "tradingDay": True,
                }
            )
    daily_dates = {record["date"] for record in daily_records}
    for date_string, is_rebalance in rebalance_by_date.items():
        if is_rebalance and date_string not in daily_dates:
            daily_records.append({"date": date_string, "netReturn": 0.0, "rebalance": True, "tradingDay": False})
    daily_records.sort(key=lambda record: str(record["date"]))

    result = json.loads(RESULT.read_text())
    status = json.loads(STATUS.read_text())
    config = json.loads(CONFIG.read_text())
    payload = {
        "strategy": {
            "id": result["candidate"],
            "name": "Return-First 60/40",
            "subtitle": "Frozen research candidate · 50 bps costs",
            "asOf": records[-1]["date"],
            "retrospectiveHoldout": {
                "cagr": result["holdout_50bps_cagr"],
                "sharpe": result["holdout_50bps_sharpe"],
                "maxDrawdown": result["holdout_50bps_drawdown"],
                "start": "2023-08-04",
            },
            "fullHistory": {
                "cagr": result["full_50bps_cagr"],
                "maxDrawdown": result["full_50bps_drawdown"],
                "start": records[0]["date"],
            },
            "forward": {
                "status": status["status"],
                "observedWeeks": status["observed_weeks"],
                "requiredWeeks": status["required_weeks"],
                "firstDecision": config["first_eligible_decision_date"],
                "firstRealization": config["first_eligible_realization_date"],
            },
            "disclosures": {
                "researchOnly": result["retrospective_research_only"],
                "liveTradingEnabled": result["live_trading_enabled"],
                "costBps": 50,
                "returnConvention": "Each weekly return is attributed to its strategy decision date and realized over the following weekly interval.",
            },
        },
        "records": records,
        "dailyRecords": daily_records,
    }
    OUTPUT.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(
        f"wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, "
        f"{len(records):,} weekly allocations, {len(daily_records):,} daily returns)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
