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
LATEST_ETF_PRICES = APP / "data/latest-etf-snapshot/prices.csv"
INCUMBENT_RESULT = V2 / "evidence/forward_return_first_60_40_blend_v1/result.json"
INCUMBENT_STATUS = V2 / "evidence/forward_return_first_60_40_blend_v1/status.json"
INCUMBENT_CONFIG = V2 / "config/forward/return_first_60_40_blend_v1.json"
GROWTH = V2 / "evidence/sec_growth_survivorship_retest_v1"
GROWTH_STATUS = V2 / "evidence/sec_growth_stock_drift_cap_v1/forward_status.json"
BREADTH_AUDIT = V2 / "evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1"
BREADTH_WEEKLY = V2 / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1"
BREADTH_FORWARD = V2 / "config/forward/sec_cash_conversion_breadth20_challenger_v1.json"
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


def main() -> int:
    payload = {"strategies": [incumbent_payload(), growth_payload(), breadth20_payload()]}
    temporary = OUTPUT.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    temporary.replace(OUTPUT)
    print(f"wrote {OUTPUT} ({OUTPUT.stat().st_size:,} bytes, {len(payload['strategies'])} strategies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
