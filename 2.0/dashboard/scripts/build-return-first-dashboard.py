#!/usr/bin/env python3
"""Build a multi-strategy Vercel dashboard snapshot from Version 2 evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


APP = Path(__file__).resolve().parents[1]
V2 = APP.parent
sys.path.insert(0, str(V2 / "src"))

from systematic_trader.sec_real_tournament_v2 import build_family_weights


WEIGHTS = V2 / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"
PRICES = V2 / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
DAILY_PRICES = V2 / "data/vintages/20260812T035702Z-0c1bf62d74413e2a/payload/prices.csv"
LATEST_ETF_PRICES = APP / "data/latest-etf-snapshot/prices.csv"
INCUMBENT_RESULT = V2 / "evidence/forward_return_first_60_40_blend_v1/result.json"
INCUMBENT_STATUS = V2 / "evidence/forward_return_first_60_40_blend_v1/status.json"
INCUMBENT_CONFIG = V2 / "config/forward/return_first_60_40_blend_v1.json"
GROWTH = V2 / "evidence/sec_growth_survivorship_retest_v1"
GROWTH_STATUS = V2 / "evidence/sec_growth_stock_drift_cap_v1/forward_status.json"
BREADTH_AUDIT = V2 / "evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1"
BREADTH_WEEKLY = V2 / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1"
BREADTH_FORWARD = V2 / "config/forward/sec_cash_conversion_breadth20_challenger_v1.json"
SECTOR_ENSEMBLE = V2 / "evidence/sec_sector_aware_signal_ensemble_v1"
RESIDUAL_CONTROLLED = V2 / "evidence/sec_residual_controlled_sleeve_v1"
RESIDUAL_COMMON_ENDPOINT = V2 / "evidence/sec_independent_sleeve_return_accelerator_v1/common_endpoint_audit.json"
RESIDUAL_FORWARD = V2 / "evidence/forward_sec_residual_controlled_sleeve_v1/status.json"
RESIDUAL_FORWARD_CONFIG = V2 / "config/forward/sec_residual_controlled_sleeve_forward_v1.json"
RESIDUAL_PROGRAM = V2 / "config/sec_return_improvement_program_v1.json"
SEC_BROAD_PANEL = V2 / "data/sec_broad_research_panel_v2/panel.csv.gz"
SEC_BROAD_PRICE_INVENTORY = V2 / "data/sec_broad_panel_inputs_v2/price_source_inventory.csv"
PRICE_REPAIRS = V2 / "data/daily_audit_price_source_repairs_v1/manifest.csv"
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


def asset_price_payload(prices: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    payload: dict[str, list[dict[str, object]]] = {}
    for symbol in prices.columns:
        series = pd.to_numeric(prices[symbol], errors="coerce").dropna()
        if series.empty:
            continue
        payload[str(symbol)] = [
            {"date": date.strftime("%Y-%m-%d"), "price": float(value)}
            for date, value in series.items()
        ]
    return payload


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
        terminal_extension = terminal_date is not None and index == len(weights.index) - 1 and decision == weights.index[-1]
        if not terminal_extension:
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


def daily_records_from_aligned_weekly_path(
    weights: pd.DataFrame,
    daily_prices: pd.DataFrame,
    weekly_net: pd.Series,
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    """Expand an authoritative week-ending path without dropping its final observation."""
    rebalance_by_date = {str(record["date"]): bool(record["rebalance"]) for record in records}
    output: list[dict[str, object]] = []
    boundaries = list(weights.index)
    for index, period_end in enumerate(boundaries):
        date_string = period_end.strftime("%Y-%m-%d")
        desired_return = float(weekly_net.get(period_end, 0.0))
        if index == 0:
            output.append({
                "date": date_string,
                "netReturn": clean(desired_return),
                "rebalance": rebalance_by_date.get(date_string, False),
                "tradingDay": True,
            })
            continue
        period_start = boundaries[index - 1]
        interval = daily_prices.loc[(daily_prices.index > period_start) & (daily_prices.index <= period_end)]
        if interval.empty:
            output.append({
                "date": date_string,
                "netReturn": clean(desired_return),
                "rebalance": rebalance_by_date.get(date_string, False),
                "tradingDay": True,
            })
            continue
        target = weights.loc[period_end].drop(labels="cash::USD", errors="ignore")
        base_history = daily_prices.loc[:period_start]
        if base_history.empty:
            raw = pd.Series(0.0, index=interval.index)
        else:
            base = base_history.ffill().iloc[-1]
            relatives = interval.ffill().divide(base).replace([np.inf, -np.inf], np.nan)
            invested = relatives.mul(target, axis=1).sum(axis=1, min_count=1)
            cash_weight = float(weights.loc[period_end].get("cash::USD", 0.0))
            level = (invested + cash_weight).fillna(1.0)
            raw = level.pct_change()
            raw.iloc[0] = float(level.iloc[0] - 1.0)
        prior = float((1.0 + raw.iloc[:-1]).prod()) if len(raw) > 1 else 1.0
        raw.iloc[-1] = (1.0 + desired_return) / prior - 1.0
        for day, daily_return in raw.items():
            day_string = day.strftime("%Y-%m-%d")
            output.append({
                "date": day_string,
                "netReturn": clean(daily_return),
                "rebalance": rebalance_by_date.get(day_string, False),
                "tradingDay": True,
            })
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
    if LATEST_ETF_PRICES.exists():
        try:
            latest_source = pd.read_csv(LATEST_ETF_PRICES, usecols=["observation_date", "ticker", "adjusted_close"])
        except OSError:
            latest_source = pd.DataFrame(columns=["observation_date", "ticker", "adjusted_close"])
        source = pd.concat([source, latest_source], ignore_index=True).drop_duplicates(["observation_date", "ticker"], keep="last")
    source["observation_date"] = pd.to_datetime(source["observation_date"], errors="coerce")
    source["adjusted_close"] = pd.to_numeric(source["adjusted_close"], errors="coerce")
    daily = source.pivot_table(index="observation_date", columns="ticker", values="adjusted_close", aggfunc="last").sort_index()
    daily = daily.reindex(columns=[column for column in weights.columns if column != "cash::USD"])
    daily_records = daily_records_from_weights(weights, daily, net, records, terminal_date=daily.index.max())

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
            "featuredMetric": {"label": "OFFICIAL RESEARCH CAGR", "value": result["holdout_50bps_cagr"], "note": "Holdout window · selected after observing this period"},
            "forward": {"status": status["status"], "observedWeeks": status["observed_weeks"], "requiredWeeks": status["required_weeks"], "firstDecision": config["first_eligible_decision_date"], "firstRealization": config["first_eligible_realization_date"], "note": "The 41.66% holdout result is evidence—not an expectation."},
            "disclosures": {"researchOnly": result["retrospective_research_only"], "liveTradingEnabled": result["live_trading_enabled"], "costBps": 50, "returnConvention": "Weekly decision returns, expanded to daily calendar observations."},
        },
        "records": records,
        "dailyRecords": daily_records,
        "assetPrices": asset_price_payload(daily),
    }


def growth_sources() -> tuple[dict[str, str], dict[str, pd.Series]]:
    rows = pd.read_csv(GROWTH / "selected_price_sources.csv", dtype={"cik10": str})
    repairs = {}
    if PRICE_REPAIRS.exists():
        repair_frame = pd.read_csv(PRICE_REPAIRS, dtype={"cik10": str})
        repairs = {str(row.cik10).zfill(10): V2 / str(row.price_file) for row in repair_frame.itertuples(index=False)}
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
        try:
            frame = pd.read_csv(path)
        except OSError:
            path = repairs.get(cik, path)
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

    def weekly_metric(sample: pd.DataFrame) -> dict[str, object]:
        returns = sample["net_return"].dropna()
        years = len(returns) / 52.0
        curve = (1.0 + returns).cumprod()
        volatility = returns.std(ddof=1)
        return {
            "cagr": float(curve.iloc[-1] ** (1.0 / years) - 1.0),
            "sharpe_zero_rf": float(returns.mean() / volatility * np.sqrt(52)) if volatility else 0.0,
            "max_drawdown": float((curve / curve.cummax() - 1.0).min()),
            "start": returns.index.min().strftime("%Y-%m-%d"),
        }
    full = weekly_metric(path)
    recent = weekly_metric(path.loc[path.index >= path.index.max() - pd.DateOffset(years=1)])
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
            "featuredMetric": {"label": "OFFICIAL RESEARCH CAGR", "value": recent["cagr"], "note": "Trailing 1Y · Micron supplied 67.63% of positive return"},
            "forward": {"status": status["status"], "observedWeeks": status["observed_weeks"], "requiredWeeks": status["required_weeks"], "firstDecision": "2026-08-14", "firstRealization": status["next_realization"], "note": "The 142.22% result is a historical simulation, not an expected annual return."},
            "disclosures": {"researchOnly": True, "liveTradingEnabled": False, "costBps": 50, "returnConvention": "Quarterly SEC selections with weekly mark-to-market; missing MMAT weight held in cash in the displayed base case."},
        },
        "records": records,
        "dailyRecords": daily_records,
        "assetPrices": asset_price_payload(daily),
    }


def latest_selection(choices: pd.DataFrame, date: pd.Timestamp) -> list[str]:
    eligible = choices[choices["decision_at"] < date]
    if eligible.empty:
        return []
    latest = eligible["decision_at"].max()
    return eligible.loc[eligible["decision_at"].eq(latest), "cik10"].astype(str).str.zfill(10).tolist()


def breadth_price_sources() -> tuple[dict[str, str], pd.DataFrame]:
    source_rows = []
    for source_file in [GROWTH / "selected_price_sources.csv", V2 / "evidence/sec_independent_fundamental_discovery_v1/selected_price_sources.csv"]:
        frame = pd.read_csv(source_file, dtype={"cik10": str})
        source_rows.append(frame[["cik10", "price_source", "price_file"]])
    if PRICE_REPAIRS.exists():
        repairs = pd.read_csv(PRICE_REPAIRS, dtype={"cik10": str}).rename(columns={"source": "price_source"})
        repairs["price_file"] = repairs["price_file"].map(lambda value: str(V2 / str(value)))
        source_rows.append(repairs[["cik10", "price_source", "price_file"]])
    sources = pd.concat(source_rows, ignore_index=True).dropna(subset=["price_file"]).drop_duplicates("cik10", keep="last")
    symbol_by_cik: dict[str, str] = {}
    series_by_symbol: dict[str, pd.Series] = {}
    for row in sources.itertuples(index=False):
        cik = str(row.cik10).zfill(10)
        raw_path = str(row.price_file)
        relative = raw_path.split("/2.0/", 1)[-1]
        source_path = V2 / relative if not Path(raw_path).is_absolute() or "/2.0/" in raw_path else Path(raw_path)
        if not source_path.exists():
            continue
        symbol = source_path.parent.name if source_path.name == "prices.csv.gz" else source_path.name.split(".", 1)[0]
        try:
            frame = pd.read_csv(source_path)
        except OSError:
            continue
        if "Date" in frame:
            dates = pd.to_datetime(frame["Date"], errors="coerce")
            values = pd.to_numeric(frame["Adj Close"], errors="coerce")
        else:
            dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
            values = pd.to_numeric(frame["adjClose"], errors="coerce")
        symbol_by_cik[cik] = symbol
        series_by_symbol[symbol] = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
    return symbol_by_cik, pd.DataFrame(series_by_symbol).sort_index()


def breadth20_payload() -> dict[str, object]:
    daily_path = load_frame(BREADTH_AUDIT / "daily_path_primary.csv")
    performance = pd.read_csv(BREADTH_AUDIT / "performance.csv")
    result = json.loads((BREADTH_AUDIT / "result.json").read_text())
    forward = json.loads(BREADTH_FORWARD.read_text())
    trades = pd.read_csv(BREADTH_AUDIT / "trade_ledger_10000.csv", parse_dates=["Date"])
    rebalance_dates = set(trades.Date.dt.strftime("%Y-%m-%d"))

    incumbent_weights = load_frame(WEIGHTS).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    growth_choices = pd.read_csv(GROWTH / "portfolio_choices.csv", dtype={"cik10": str})
    cash_choices = pd.read_csv(BREADTH_WEEKLY / "portfolio_choices.csv", dtype={"cik10": str})
    for choices in [growth_choices, cash_choices]:
        choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True).dt.tz_localize(None)
    growth_alloc = load_frame(V2 / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv")["target_growth_allocation"]
    outer_alloc = load_frame(BREADTH_WEEKLY / "target_weights.csv")["cash_conversion"]
    symbol_by_cik, stock_prices = breadth_price_sources()

    etf_source = pd.read_csv(DAILY_PRICES, usecols=["observation_date", "ticker", "adjusted_close"])
    etf_source["observation_date"] = pd.to_datetime(etf_source["observation_date"])
    etf_prices = etf_source.pivot_table(index="observation_date", columns="ticker", values="adjusted_close", aggfunc="last").sort_index()
    asset_prices = pd.concat([etf_prices, stock_prices], axis=1).loc[:daily_path.index.max()]

    weekly_dates = outer_alloc.index.intersection(daily_path.index)
    columns = sorted(set(incumbent_weights.columns) | set(symbol_by_cik.values()) | {"cash::USD"})
    targets = pd.DataFrame(0.0, index=weekly_dates, columns=columns)
    for date in weekly_dates:
        base_row = incumbent_weights.reindex([date], method="ffill").iloc[0]
        growth_weight = float(growth_alloc.reindex([date], method="ffill").iloc[0])
        cash_weight = float(outer_alloc.loc[date])
        leader_weight = 1.0 - cash_weight
        for asset, weight in base_row.items():
            targets.at[date, asset] += leader_weight * (1.0 - growth_weight) * float(weight)
        selected_growth = latest_selection(growth_choices, date)
        if selected_growth:
            per_name = leader_weight * growth_weight / len(selected_growth)
            for cik in selected_growth:
                targets.at[date, symbol_by_cik.get(cik, "cash::USD")] += per_name
        selected_cash = latest_selection(cash_choices, date)
        if selected_cash:
            per_name = cash_weight / len(selected_cash)
            for cik in selected_cash:
                targets.at[date, symbol_by_cik.get(cik, "cash::USD")] += per_name
        targets.loc[date] = targets.loc[date] / targets.loc[date].sum()

    weekly_returns = (1.0 + daily_path["net_return"]).resample("W-FRI").prod() - 1.0
    weekly_wealth = (1.0 + weekly_returns).cumprod()
    weekly_drawdown = weekly_wealth / weekly_wealth.cummax() - 1.0
    weekly_turnover = 0.5 * targets.diff().abs().sum(axis=1).fillna(0.0)
    records = records_from_weights(
        targets,
        weekly_returns.reindex(targets.index).fillna(0.0),
        weekly_returns.reindex(targets.index).fillna(0.0),
        weekly_turnover,
        pd.Series(0.0, index=targets.index),
        weekly_wealth.reindex(targets.index).ffill().fillna(1.0),
        weekly_drawdown.reindex(targets.index).ffill().fillna(0.0),
    )
    daily_records = [
        {"date": date.strftime("%Y-%m-%d"), "netReturn": clean(row.net_return), "rebalance": date.strftime("%Y-%m-%d") in rebalance_dates, "tradingDay": True}
        for date, row in daily_path.iterrows()
    ]

    def metric(window: str) -> pd.Series:
        return performance[(performance.execution_delay_sessions == 0) & (performance.cost_bps == 50) & (performance.window == window)].iloc[0]

    full, recent = metric("full_recent"), metric("trailing_1y")
    return {
        "strategy": {
            "id": "sec-cash-conversion-breadth20-dynamic-v1",
            "name": "Dynamic Breadth-20 — Return Leader",
            "shortName": "102% Daily-Audited",
            "subtitle": "ETF incumbent + growth sleeve + conditional cash-conversion breadth · 50 bps",
            "badge": "102.49% trailing 1Y CAGR",
            "asOf": daily_records[-1]["date"],
            "retrospectiveHoldout": {"cagr": recent.cagr, "sharpe": recent.sharpe_zero_rf, "maxDrawdown": recent.max_drawdown, "start": recent.start},
            "fullHistory": {"cagr": full.cagr, "maxDrawdown": full.max_drawdown, "start": full.start},
            "featuredMetric": {"label": "DAILY-AUDITED TRAILING 1Y", "value": recent.cagr, "note": "Daily adjusted closes · 50 bps costs · no leverage or shorting"},
            "forward": {"status": forward["status"], "observedWeeks": 0, "requiredWeeks": int(forward["observation_weeks"]), "firstDecision": forward["first_eligible_week_ending"], "firstRealization": forward["first_eligible_week_ending"], "note": "Research leader only; forward evidence has not started."},
            "disclosures": {"researchOnly": True, "liveTradingEnabled": False, "costBps": 50, "returnConvention": "Daily adjusted-close accounting; signal-date close with separate one- and two-session delay stress tests."},
        },
        "records": records,
        "dailyRecords": daily_records,
        "assetPrices": asset_price_payload(asset_prices),
    }


def sector_ensemble_payload() -> dict[str, object]:
    """Render the saved 124.20% diagnostic without implying that it passed promotion gates."""
    path = load_frame(SECTOR_ENSEMBLE / "selected_path__50bps.csv")
    result = json.loads((SECTOR_ENSEMBLE / "result.json").read_text())
    outer = load_frame(SECTOR_ENSEMBLE / "selected_strategy_target_weights.csv")
    stock_targets = pd.read_csv(SECTOR_ENSEMBLE / "selected_stock_target_weights.csv", dtype={"cik10": str})
    stock_targets["rebalance_at"] = pd.to_datetime(stock_targets["rebalance_at"])

    incumbent_weights = load_frame(WEIGHTS).apply(pd.to_numeric, errors="coerce").fillna(0.0)
    growth_choices = pd.read_csv(GROWTH / "portfolio_choices.csv", dtype={"cik10": str})
    growth_choices["decision_at"] = pd.to_datetime(growth_choices["decision_at"], utc=True).dt.tz_localize(None)
    growth_alloc = load_frame(V2 / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv")["target_growth_allocation"]
    symbol_by_cik, stock_prices = breadth_price_sources()

    etf_source = pd.read_csv(DAILY_PRICES, usecols=["observation_date", "ticker", "adjusted_close"])
    if LATEST_ETF_PRICES.exists():
        latest_source = pd.read_csv(LATEST_ETF_PRICES, usecols=["observation_date", "ticker", "adjusted_close"])
        etf_source = pd.concat([etf_source, latest_source], ignore_index=True).drop_duplicates(
            ["observation_date", "ticker"], keep="last"
        )
    etf_source["observation_date"] = pd.to_datetime(etf_source["observation_date"])
    etf_prices = etf_source.pivot_table(index="observation_date", columns="ticker", values="adjusted_close", aggfunc="last").sort_index()
    daily_prices = pd.concat([etf_prices, stock_prices], axis=1)

    dates = path.index.intersection(outer.index)
    columns = sorted(set(incumbent_weights.columns) | set(symbol_by_cik.values()) | {"cash::USD"})
    weights = pd.DataFrame(0.0, index=dates, columns=columns)
    for date in dates:
        cash_conversion_weight = float(outer.loc[date, "cash_conversion"])
        leader_weight = float(outer.loc[date, "leader"])
        base_row = incumbent_weights.reindex([date], method="ffill").iloc[0]
        growth_weight = float(growth_alloc.reindex([date], method="ffill").iloc[0])
        for asset, weight in base_row.items():
            weights.at[date, asset] += leader_weight * (1.0 - growth_weight) * float(weight)
        selected_growth = latest_selection(growth_choices, date)
        if selected_growth:
            per_name = leader_weight * growth_weight / len(selected_growth)
            for cik in selected_growth:
                weights.at[date, symbol_by_cik.get(cik, "cash::USD")] += per_name
        eligible = stock_targets[stock_targets["rebalance_at"] <= date]
        if not eligible.empty and cash_conversion_weight > 0:
            latest_rebalance = eligible["rebalance_at"].max()
            selected_stocks = eligible[eligible["rebalance_at"].eq(latest_rebalance)]
            for row in selected_stocks.itertuples(index=False):
                symbol = symbol_by_cik.get(str(row.cik10).zfill(10), "cash::USD")
                weights.at[date, symbol] += cash_conversion_weight * float(row.intended_weight)
        total = float(weights.loc[date].sum())
        if total < 1.0 - 1e-10:
            weights.at[date, "cash::USD"] += 1.0 - total
        elif total > 0:
            weights.loc[date] /= total

    turnover = path["turnover"].reindex(dates).fillna(0.0)
    records = records_from_weights(
        weights,
        path["gross_return"].reindex(dates).fillna(0.0),
        path["net_return"].reindex(dates).fillna(0.0),
        turnover,
        path["cost"].reindex(dates).fillna(0.0),
        path["wealth"].reindex(dates).ffill().fillna(1.0),
        path["drawdown"].reindex(dates).ffill().fillna(0.0),
    )
    daily_prices = daily_prices.reindex(columns=[column for column in weights.columns if column != "cash::USD"])
    daily_records = daily_records_from_weights(
        weights,
        daily_prices,
        path["net_return"].reindex(dates).fillna(0.0),
        records,
        terminal_date=daily_prices.index.max(),
    )
    return {
        "strategy": {
            "id": "sec-sector-aware-signal-ensemble-v1",
            "name": "Sector-Aware Signal Ensemble — 124% Diagnostic",
            "shortName": "124% Sector Ensemble",
            "subtitle": "50/50 cash-conversion and balance-quality holdings ensemble · 50 bps",
            "badge": "124.20% trailing 52W CAGR",
            "asOf": daily_records[-1]["date"],
            "retrospectiveHoldout": {
                "cagr": result["recent_cagr"],
                "sharpe": result["recent_sharpe"],
                "maxDrawdown": result["recent_drawdown"],
                "start": dates[-52].strftime("%Y-%m-%d"),
            },
            "fullHistory": {
                "cagr": result["full_cagr"],
                "maxDrawdown": float(path["drawdown"].min()),
                "start": dates[0].strftime("%Y-%m-%d"),
            },
            "featuredMetric": {
                "label": "TRAILING 52W CAGR",
                "value": result["recent_cagr"],
                "note": "50% endpoint pass · 57.1% rolling-26 pass · falsification gates failed",
            },
            "forward": {
                "status": "NOT ELIGIBLE",
                "observedWeeks": 0,
                "requiredWeeks": 52,
                "firstDecision": "Not scheduled",
                "firstRealization": "Not scheduled",
                "note": "High-return diagnostic only; it failed bootstrap and five-issuer robustness gates and was not promoted.",
            },
            "disclosures": {
                "researchOnly": True,
                "liveTradingEnabled": False,
                "costBps": 50,
                "returnConvention": "Weekly causal decisions expanded to daily adjusted-close observations; no live execution.",
            },
        },
        "records": records,
        "dailyRecords": daily_records,
        "assetPrices": asset_price_payload(daily_prices),
    }


def weekly_statistics(returns: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(returns, errors="coerce").dropna()
    wealth = (1.0 + values).cumprod()
    years = len(values) / 52.0
    volatility = values.std(ddof=1)
    return {
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0) if years else 0.0,
        "sharpe": float(values.mean() / volatility * np.sqrt(52.0)) if volatility else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()) if len(wealth) else 0.0,
    }


def payload_prices_to_frame(payload: dict[str, list[dict[str, object]]]) -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for symbol, points in payload.items():
        if not points:
            continue
        dates = pd.to_datetime([str(point["date"]) for point in points], errors="coerce")
        values = pd.to_numeric([point["price"] for point in points], errors="coerce")
        series[symbol] = pd.Series(values, index=dates).dropna().sort_index()
    return pd.DataFrame(series).sort_index()


def broad_price_sources(ciks: set[str]) -> tuple[dict[str, str], pd.DataFrame]:
    inventory = pd.read_csv(SEC_BROAD_PRICE_INVENTORY, dtype={"cik10": str})
    inventory["cik10"] = inventory["cik10"].astype(str).str.zfill(10)
    inventory = inventory[inventory["cik10"].isin(ciks)].drop_duplicates("cik10", keep="last")
    symbol_by_cik: dict[str, str] = {}
    series_by_symbol: dict[str, pd.Series] = {}
    for row in inventory.itertuples(index=False):
        source_path = Path(str(row.path))
        if not source_path.exists():
            continue
        symbol = source_path.parent.name if source_path.name == "prices.csv.gz" else source_path.name.split(".", 1)[0]
        try:
            frame = pd.read_csv(source_path)
        except OSError:
            continue
        if "Date" in frame:
            dates = pd.to_datetime(frame["Date"], errors="coerce")
            values = pd.to_numeric(frame["Adj Close"], errors="coerce")
        else:
            dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
            values = pd.to_numeric(frame["adjClose"], errors="coerce")
        symbol_by_cik[str(row.cik10).zfill(10)] = symbol
        series_by_symbol[symbol] = pd.Series(values.to_numpy(), index=dates).dropna().sort_index()
    return symbol_by_cik, pd.DataFrame(series_by_symbol).sort_index()


def residual_controlled_payload(control_payload: dict[str, object]) -> dict[str, object]:
    """Render the corrected common-endpoint 1.25x path without implying promotion."""
    audit = json.loads(RESIDUAL_COMMON_ENDPOINT.read_text())
    result = json.loads((RESIDUAL_CONTROLLED / "result.json").read_text())
    forward = json.loads(RESIDUAL_FORWARD.read_text())
    forward_config = json.loads(RESIDUAL_FORWARD_CONFIG.read_text())
    common_endpoint = pd.Timestamp(audit["common_endpoint"])

    candidate = load_frame(RESIDUAL_CONTROLLED / "candidate_path.csv")["net_return"]
    if candidate.index.tz is not None:
        candidate.index = candidate.index.tz_localize(None)
    candidate = candidate.loc[:common_endpoint]
    leverage = 1.25
    financing_rate = 0.05
    levered_returns = leverage * candidate - (leverage - 1.0) * financing_rate / 52.0

    control_rows = control_payload["records"]
    control_symbols = sorted({
        str(holding["symbol"])
        for record in control_rows
        for holding in record["holdings"]
    } | {"cash::USD"})
    control_weights = pd.DataFrame(0.0, index=pd.to_datetime([record["date"] for record in control_rows]), columns=control_symbols)
    for record in control_rows:
        date = pd.Timestamp(record["date"])
        for holding in record["holdings"]:
            control_weights.at[date, str(holding["symbol"])] = float(holding["weight"] or 0.0)
    control_weights = control_weights.reindex(candidate.index, method="ffill").fillna(0.0)
    empty_control = control_weights.sum(axis=1).abs() < 1e-10
    control_weights.loc[empty_control, "cash::USD"] = 1.0

    panel = pd.read_csv(SEC_BROAD_PANEL, dtype={"cik10": str})
    program = json.loads(RESIDUAL_PROGRAM.read_text())
    family_weights, _ = build_family_weights(panel, program)
    residual_schedule = family_weights["residual_momentum"].copy()
    residual_schedule["cik10"] = residual_schedule["cik10"].astype(str).str.zfill(10)
    residual_schedule["decision_at"] = pd.to_datetime(residual_schedule["decision_at"], utc=True).dt.tz_localize(None)
    selected_ciks = set(residual_schedule["cik10"])
    symbol_by_cik, residual_prices = broad_price_sources(selected_ciks)

    residual_symbols = sorted(set(symbol_by_cik.values()) | {"cash::USD"})
    residual_weights = pd.DataFrame(0.0, index=candidate.index, columns=residual_symbols)
    for date in residual_weights.index:
        eligible = residual_schedule[residual_schedule["decision_at"] <= date]
        if eligible.empty:
            residual_weights.at[date, "cash::USD"] = 1.0
            continue
        latest_decision = eligible["decision_at"].max()
        selected = eligible[eligible["decision_at"].eq(latest_decision)]
        for row in selected.itertuples(index=False):
            residual_weights.at[date, symbol_by_cik.get(str(row.cik10).zfill(10), "cash::USD")] += float(row.weight)
        missing_weight = 1.0 - float(residual_weights.loc[date].sum())
        if missing_weight > 1e-10:
            residual_weights.at[date, "cash::USD"] += missing_weight

    all_symbols = sorted(set(control_weights.columns) | set(residual_weights.columns) | {"cash::USD"})
    control_weights = control_weights.reindex(columns=all_symbols, fill_value=0.0)
    residual_weights = residual_weights.reindex(columns=all_symbols, fill_value=0.0)
    weights = leverage * (0.8 * control_weights + 0.2 * residual_weights)
    weights["cash::USD"] -= leverage - 1.0

    turnover = 0.5 * weights.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * 50.0 / 10000.0
    gross = levered_returns + cost
    wealth = (1.0 + levered_returns).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    records = records_from_weights(weights, gross, levered_returns, turnover, cost, wealth, drawdown)

    control_prices = payload_prices_to_frame(control_payload["assetPrices"])
    daily_prices = pd.concat([control_prices, residual_prices], axis=1)
    daily_prices = daily_prices.loc[:, ~daily_prices.columns.duplicated(keep="last")].sort_index().loc[:common_endpoint]
    daily_prices = daily_prices.reindex(columns=[column for column in weights.columns if column != "cash::USD"])
    daily_records = daily_records_from_aligned_weekly_path(
        weights,
        daily_prices,
        levered_returns,
        records,
    )

    recent = audit["trailing_52_week_paths"]["levered_1.25x_5pct_financing"]
    conservative = audit["trailing_52_week_paths"]["levered_1.25x_8pct_financing"]
    full = weekly_statistics(levered_returns)
    return {
        "strategy": {
            "id": "sec-residual-controlled-1.25x-5pct-v1",
            "name": "Residual-Controlled 1.25x — Recent Return Leader",
            "shortName": "150.86% Residual 1.25x",
            "subtitle": "80% dynamic leader + 20% residual momentum · 1.25x exposure · assumed 5% financing",
            "badge": "150.86% trailing 52W CAGR",
            "asOf": audit["common_endpoint"],
            "retrospectiveHoldout": {
                "cagr": recent["cagr"],
                "sharpe": recent["sharpe"],
                "maxDrawdown": recent["max_drawdown"],
                # Begin after the prior Friday so the daily expansion includes the
                # complete first weekly return in the audited 52-week window.
                "start": (candidate.tail(52).index.min() - pd.Timedelta(days=6)).strftime("%Y-%m-%d"),
            },
            "fullHistory": {
                "cagr": full["cagr"],
                "maxDrawdown": full["max_drawdown"],
                "start": candidate.index.min().strftime("%Y-%m-%d"),
            },
            "featuredMetric": {
                "label": "COMMON-ENDPOINT TRAILING 52W",
                "value": recent["cagr"],
                "note": f"5% financing assumption · 8% stress: {conservative['cagr'] * 100:.2f}% · selected on this sample",
            },
            "forward": {
                "status": "FROZEN FORWARD · NOT PROMOTED",
                "observedWeeks": forward["observed_weeks"],
                "requiredWeeks": forward["required_weeks"],
                "firstDecision": forward_config["first_eligible_decision_date"],
                "firstRealization": forward_config["first_eligible_realization_date"],
                "note": "Historical results never advance this clock; 52 untouched weeks and a separate statistical review are required.",
            },
            "disclosures": {
                "researchOnly": True,
                "liveTradingEnabled": False,
                "costBps": 50,
                "returnConvention": "Weekly net research path through the 2026-08-07 common endpoint; 1.25x exposure with a 5% annual financing assumption. Selection-contaminated and not promotion-authorized.",
            },
        },
        "records": records,
        "dailyRecords": daily_records,
        "assetPrices": asset_price_payload(daily_prices),
        "validation": {
            "promotionAuthorized": result["promotion_authorized"],
            "allStatisticalGatesPassed": result["all_statistical_validation_gates_passed"],
            "commonEndpoint": audit["common_endpoint"],
            "excludedMismatchedDates": audit["excluded_mismatched_candidate_dates"],
        },
    }


def main() -> int:
    breadth = breadth20_payload()
    residual = residual_controlled_payload(breadth)
    payload = {"strategies": [residual, incumbent_payload(), growth_payload(), breadth, sector_ensemble_payload()]}
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    temporary.replace(OUTPUT)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(payload['strategies'])} strategies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
