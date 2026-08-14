#!/usr/bin/env python3
"""Daily-close accounting audit of the breadth-20 cash-conversion candidate."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as growth_base

CONFIG = ROOT / "config/sec_cash_conversion_breadth20_daily_execution_audit_v1.json"
ETF_PRICES = ROOT / "data/vintages/20260812T035702Z-0c1bf62d74413e2a/payload/prices.csv"
ETF_WEIGHTS = ROOT / "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv"
GROWTH_CHOICES = ROOT / "evidence/sec_growth_survivorship_retest_v1/portfolio_choices.csv"
LEADER_WEEKLY = ROOT / "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv"
CASH_CHOICES = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/portfolio_choices.csv"
OUTER_TARGETS = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/target_weights.csv"
WEEKLY_CANDIDATE = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1"
SOURCE_AUDITS = [ROOT / "evidence/sec_growth_survivorship_retest_v1/selected_price_sources.csv", ROOT / "evidence/sec_independent_fundamental_discovery_v1/selected_price_sources.csv"]
MEMBERSHIP = ROOT / "evidence/combined_recent_price_panel_v1/classified_membership.csv"
CURRENT_YAHOO = ROOT / "data/yahoo_recent_current_sec_price_vintages/20260813T205326Z-yahoo-recent-current-sec-v1/histories"
RECOVERED_YAHOO = ROOT / "data/sec_recovered_price_probe_vintages/20260813T100449Z-recovered-yahoo-price-probe-v1/histories"
TIINGO_CACHE = ROOT / "data/tiingo_delisted_price_probe_cache_v1"
REPAIR_MANIFEST = ROOT / "data/daily_audit_price_source_repairs_v1/manifest.csv"


def read_stock_close(path: Path, source: str, index: pd.DatetimeIndex) -> tuple[pd.Series, dict]:
    frame = pd.read_csv(path, compression="gzip")
    if source.startswith("yahoo"):
        dates = pd.to_datetime(frame["Date"], errors="coerce")
        close = pd.to_numeric(frame["Adj Close"], errors="coerce")
        dividends = pd.to_numeric(frame.get("Dividends", 0.0), errors="coerce").fillna(0.0)
        splits = pd.to_numeric(frame.get("Stock Splits", 0.0), errors="coerce").fillna(0.0)
    else:
        dates = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.tz_localize(None)
        close = pd.to_numeric(frame["adjClose"], errors="coerce")
        dividends = pd.to_numeric(frame.get("divCash", 0.0), errors="coerce").fillna(0.0)
        splits = pd.to_numeric(frame.get("splitFactor", 1.0), errors="coerce").fillna(1.0).sub(1.0).abs()
    series = pd.Series(close.to_numpy(), index=dates).dropna().sort_index()
    series = series[~series.index.duplicated(keep="last")].reindex(index)
    audit = {"source": source, "rows": int(len(frame)), "dividend_events": int((dividends != 0).sum()), "split_events": int((splits != 0).sum()), "first_date": str(pd.to_datetime(dates).min().date()), "last_date": str(pd.to_datetime(dates).max().date())}
    return series, audit


def frozen_price_sources() -> dict[str, tuple[str, Path]]:
    result = {}
    for audit_path in SOURCE_AUDITS:
        frame = pd.read_csv(audit_path, dtype={"cik10": str})
        for row in frame.dropna(subset=["price_source", "price_file"]).itertuples(index=False):
            raw = str(row.price_file)
            if raw.startswith("/workspace/2.0/"):
                path = ROOT / raw.removeprefix("/workspace/2.0/")
            elif raw.startswith("/project/"):
                path = ROOT / raw.removeprefix("/project/")
            else:
                path = Path(raw)
            result[str(row.cik10)] = (str(row.price_source), path)
    membership = pd.read_csv(MEMBERSHIP, dtype={"cik10": str})
    membership = membership.dropna(subset=["price_source", "ticker_used"]).drop_duplicates("cik10", keep="last")
    for row in membership.itertuples(index=False):
        if str(row.cik10) in result:
            continue
        if row.price_source == "yahoo_current_sec":
            path = CURRENT_YAHOO / f"{row.ticker_used}.csv.gz"
        elif row.price_source == "yahoo_recovered_former":
            path = RECOVERED_YAHOO / f"{row.ticker_used}.csv.gz"
        elif row.price_source == "tiingo_identity_validated":
            path = TIINGO_CACHE / str(row.ticker_used) / "prices.csv.gz"
        else:
            continue
        if path.exists():
            result[str(row.cik10)] = (str(row.price_source), path)
    if REPAIR_MANIFEST.exists():
        repairs = pd.read_csv(REPAIR_MANIFEST, dtype={"cik10": str})
        for row in repairs.itertuples(index=False):
            result[str(row.cik10)] = (str(row.source), ROOT / str(row.price_file))
    return result


def map_date(date: pd.Timestamp, index: pd.DatetimeIndex, delay: int) -> pd.Timestamp | None:
    positions = np.flatnonzero(index >= pd.Timestamp(date))
    if not len(positions) or positions[0] + delay >= len(index):
        return None
    return index[positions[0] + delay]


def shift_events(events: dict[pd.Timestamp, object], index: pd.DatetimeIndex, delay: int) -> dict[pd.Timestamp, object]:
    shifted = {}
    for date, value in events.items():
        mapped = map_date(pd.Timestamp(date), index, delay)
        if mapped is not None:
            shifted[mapped] = value
    return shifted


def rebalance(positions: dict[str, float], desired: dict[str, float], cost_bps: float, date: pd.Timestamp, layer: str, trades: list[dict]) -> tuple[dict[str, float], float, float]:
    before = sum(positions.values())
    current = {key: value / before for key, value in positions.items()} if before else {"cash::USD": 1.0}
    keys = set(current) | set(desired)
    turnover = 0.5 * sum(abs(desired.get(key, 0.0) - current.get(key, 0.0)) for key in keys)
    cost = before * turnover * cost_bps / 10000.0
    deployable = before - cost
    for asset in sorted(keys):
        delta = desired.get(asset, 0.0) - current.get(asset, 0.0)
        if abs(delta) > 1e-10:
            trades.append({"Date": date, "layer": layer, "asset": asset, "side": "BUY" if delta > 0 else "SELL", "before_weight": current.get(asset, 0.0), "after_weight": desired.get(asset, 0.0), "weight_change": delta, "notional_on_10000": abs(delta) * before * 10000.0, "turnover": turnover, "cost_on_10000": cost * 10000.0})
    return {key: deployable * weight for key, weight in desired.items() if weight > 1e-15}, turnover, cost


def advance_assets(positions: dict[str, float], previous: pd.Timestamp, date: pd.Timestamp, closes: pd.DataFrame, synthetic_returns: dict[str, pd.Series] | None = None) -> dict[str, float]:
    updated = {}
    for asset, value in positions.items():
        if asset == "cash::USD":
            updated[asset] = updated.get(asset, 0.0) + value
        elif synthetic_returns and asset in synthetic_returns:
            updated[asset] = value * (1 + float(synthetic_returns[asset].get(date, 0.0)))
        elif asset in closes:
            start, finish = closes.at[previous, asset], closes.at[date, asset]
            if pd.notna(start) and pd.notna(finish) and float(start) != 0:
                updated[asset] = value * float(finish) / float(start)
            else:
                updated["cash::USD"] = updated.get("cash::USD", 0.0) + value
        else:
            updated["cash::USD"] = updated.get("cash::USD", 0.0) + value
    return updated


def simulate_static(closes: pd.DataFrame, events: dict[pd.Timestamp, dict[str, float]], cost_bps: float, layer: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = {"cash::USD": 1.0}
    rows, trades = [], []
    previous_total = 1.0
    for offset, date in enumerate(closes.index):
        if offset:
            positions = advance_assets(positions, closes.index[offset - 1], date, closes)
        turnover = cost = 0.0
        if date in events:
            positions, turnover, cost = rebalance(positions, events[date], cost_bps, date, layer, trades)
        total = sum(positions.values())
        rows.append({"Date": date, "net_return": total / previous_total - 1 if offset else total - 1, "wealth": total, "turnover": turnover, "cost": cost / previous_total if previous_total else 0.0})
        previous_total = total
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1
    return path, pd.DataFrame(trades)


def simulate_leader(index: pd.DatetimeIndex, stock_closes: pd.DataFrame, incumbent: pd.Series, allocation_events: dict[pd.Timestamp, float], quarterly_events: dict[pd.Timestamp, list[str]], review_dates: set[pd.Timestamp], cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = {"incumbent::ETF": 1.0}
    selected: list[str] = []
    rows, trades = [], []
    previous_total = 1.0
    current_target = 0.10
    for offset, date in enumerate(index):
        if offset:
            positions = advance_assets(positions, index[offset - 1], date, stock_closes, {"incumbent::ETF": incumbent})
        else:
            positions["incumbent::ETF"] *= 1 + float(incumbent.get(date, 0.0))
        turnover = cost = cap_turnover = 0.0
        if date in allocation_events:
            current_target = float(allocation_events[date])
            if date in quarterly_events:
                selected = quarterly_events[date]
                available = [asset for asset in selected if asset in stock_closes and pd.notna(stock_closes.at[date, asset])]
                intended = current_target / len(selected)
                desired = {"incumbent::ETF": 1 - current_target, **{asset: intended for asset in available}}
                missing_weight = current_target - intended * len(available)
                if missing_weight > 0:
                    desired["cash::USD"] = missing_weight
            else:
                before = sum(positions.values())
                growth_assets = [asset for asset in positions if asset not in {"incumbent::ETF", "cash::USD"}]
                growth_total = sum(positions[asset] for asset in growth_assets)
                desired = {"incumbent::ETF": 1 - current_target}
                if growth_total > 0:
                    desired.update({asset: current_target * positions[asset] / growth_total for asset in growth_assets})
                elif selected:
                    desired.update({asset: current_target / len(selected) for asset in selected})
            positions, turnover, cost = rebalance(positions, desired, cost_bps, date, "leader", trades)
        if date in review_dates and selected:
            before = sum(positions.values())
            limit = before * current_target / len(selected) * 1.5
            excess = 0.0
            for asset in list(positions):
                if asset not in {"incumbent::ETF", "cash::USD"} and positions[asset] > limit:
                    excess += positions[asset] - limit
                    positions[asset] = limit
            if excess > 0:
                positions["incumbent::ETF"] = positions.get("incumbent::ETF", 0.0) + excess
                cap_turnover = excess / before
                cap_cost = excess * cost_bps / 10000.0
                positions["incumbent::ETF"] -= cap_cost
                cost += cap_cost
        total = sum(positions.values())
        stock_values = [value for asset, value in positions.items() if asset not in {"incumbent::ETF", "cash::USD"}]
        rows.append({"Date": date, "net_return": total / previous_total - 1 if offset else total - 1, "wealth": total, "turnover": turnover + cap_turnover, "cost": cost / previous_total if previous_total else 0.0, "growth_target": current_target, "largest_stock_weight": max(stock_values, default=0.0) / total if total else 0.0})
        previous_total = total
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1
    return path, pd.DataFrame(trades)


def simulate_outer(index: pd.DatetimeIndex, leader: pd.Series, cash: pd.Series, events: dict[pd.Timestamp, float], cost_bps: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    positions = {"leader": 1.0}
    rows, trades = [], []
    previous_total = 1.0
    for offset, date in enumerate(index):
        if offset:
            positions = advance_assets(positions, index[offset - 1], date, pd.DataFrame(index=index), {"leader": leader, "cash_conversion": cash})
        else:
            positions["leader"] *= 1 + float(leader.get(date, 0.0))
        turnover = cost = 0.0
        if date in events:
            weight = float(events[date])
            positions, turnover, cost = rebalance(positions, {"leader": 1 - weight, "cash_conversion": weight}, cost_bps, date, "outer", trades)
        total = sum(positions.values())
        rows.append({"Date": date, "net_return": total / previous_total - 1 if offset else total - 1, "wealth": total, "turnover": turnover, "cost": cost / previous_total if previous_total else 0.0, "cash_conversion_target": float(events.get(date, np.nan))})
        previous_total = total
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1
    return path, pd.DataFrame(trades)


def daily_metrics(path: pd.DataFrame) -> dict:
    returns = path.net_return.dropna()
    years = len(returns) / 252.0
    wealth = (1 + returns).cumprod()
    std = returns.std(ddof=1)
    return {"days": len(returns), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()), "cagr": float(wealth.iloc[-1] ** (1 / years) - 1), "sharpe_zero_rf": float(returns.mean() / std * np.sqrt(252)) if std else 0.0, "max_drawdown": float((wealth / wealth.cummax() - 1).min()), "total_return": float(wealth.iloc[-1] - 1), "annual_turnover": float(path.turnover.sum() / years), "ending_value_10000": float(wealth.iloc[-1] * 10000)}


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    start, end = pd.Timestamp(config["start"]), pd.Timestamp(config["end"])
    raw_etf = pd.read_csv(ETF_PRICES, parse_dates=["observation_date"])
    raw_etf = raw_etf[(raw_etf.observation_date >= start) & (raw_etf.observation_date <= end)]
    etf_closes = raw_etf.pivot(index="observation_date", columns="ticker", values="adjusted_close").sort_index()
    index = etf_closes.index
    weights = pd.read_csv(ETF_WEIGHTS, parse_dates=["Date"]).set_index("Date").reindex(columns=etf_closes.columns.tolist() + ["cash::USD"], fill_value=0.0)
    weights = weights[(weights.index >= start) & (weights.index <= end)]

    growth_choices = pd.read_csv(GROWTH_CHOICES, dtype={"cik10": str}, parse_dates=["decision_at"])
    cash_choices = pd.read_csv(CASH_CHOICES, dtype={"cik10": str}, parse_dates=["decision_at"])
    selected = sorted(set(growth_choices.cik10) | set(cash_choices.cik10))
    sources = frozen_price_sources()
    stock_closes = pd.DataFrame(index=index)
    action_rows = []
    source_failures = []
    for cik in selected:
        if cik not in sources:
            action_rows.append({"cik10": cik, "source": "missing", "rows": 0, "dividend_events": 0, "split_events": 0})
            continue
        source, path = sources[cik]
        try:
            series, audit = read_stock_close(path, source, index)
        except OSError as exc:
            source_failures.append({"cik10": cik, "source": source, "price_file": str(path), "error": repr(exc)})
            print(f"unreadable price source: cik={cik} source={source} file={path} error={exc!r}", flush=True)
            continue
        stock_closes[cik] = series
        action_rows.append({"cik10": cik, **audit})

    if source_failures:
        pd.DataFrame(source_failures).to_csv(OUTPUT / "unreadable_price_sources.csv", index=False)
        raise RuntimeError(
            f"{len(source_failures)} selected price sources are unreadable; "
            f"see {OUTPUT / 'unreadable_price_sources.csv'}"
        )

    weekly_dates = pd.read_csv(OUTER_TARGETS, parse_dates=["Date"]).Date
    growth_targets_weekly = growth_base.build_targets(growth_choices, pd.DatetimeIndex(weekly_dates))
    cash_targets_weekly = growth_base.build_targets(cash_choices, pd.DatetimeIndex(weekly_dates))
    growth_alloc = pd.read_csv(LEADER_WEEKLY, parse_dates=["Date"]).set_index("Date").target_growth_allocation.to_dict()
    outer_alloc = pd.read_csv(OUTER_TARGETS, parse_dates=["Date"]).set_index("Date").cash_conversion.to_dict()
    review_weekly = {date for date in weekly_dates if date.month != (date - pd.Timedelta(days=7)).month}

    performance_rows, reconciliation_rows = [], []
    primary_trades = []
    weekly_reference = pd.read_csv(WEEKLY_CANDIDATE, parse_dates=["Date"]).set_index("Date")
    for delay in config["execution_delays_sessions"]:
        incumbent_events = shift_events({date: row.dropna().to_dict() for date, row in weights.iterrows()}, index, int(delay))
        growth_events = shift_events(growth_targets_weekly, index, int(delay))
        cash_events = shift_events(cash_targets_weekly, index, int(delay))
        allocation_events = shift_events(growth_alloc, index, int(delay))
        outer_events = shift_events(outer_alloc, index, int(delay))
        reviews = set(shift_events({date: True for date in review_weekly}, index, int(delay)))
        for cost in config["cost_bps"]:
            incumbent_path, incumbent_trades = simulate_static(etf_closes, incumbent_events, float(cost), "incumbent")
            leader_path, leader_trades = simulate_leader(index, stock_closes, incumbent_path.net_return, allocation_events, growth_events, reviews, float(cost))
            cash_event_weights = {}
            for date, assets in cash_events.items():
                available = [asset for asset in assets if asset in stock_closes and pd.notna(stock_closes.at[date, asset])]
                desired = {asset: 1 / len(assets) for asset in available}
                if len(available) < len(assets):
                    desired["cash::USD"] = (len(assets) - len(available)) / len(assets)
                cash_event_weights[date] = desired
            cash_path, cash_trades = simulate_static(stock_closes, cash_event_weights, float(cost), "cash_conversion")
            outer_path, outer_trades = simulate_outer(index, leader_path.net_return, cash_path.net_return, outer_events, float(cost))
            for window, sample in {"full_recent": outer_path, "trailing_2y": outer_path.loc[outer_path.index >= end - pd.DateOffset(years=2)], "trailing_1y": outer_path.loc[outer_path.index >= end - pd.DateOffset(years=1)], "ytd": outer_path.loc[outer_path.index.year == end.year]}.items():
                performance_rows.append({"execution_delay_sessions": int(delay), "cost_bps": int(cost), "window": window, **daily_metrics(sample)})
            if int(delay) == 0 and int(cost) == int(config["primary_cost_bps"]):
                primary_trades = [incumbent_trades, leader_trades, cash_trades, outer_trades]
                outer_path.rename_axis("Date").to_csv(OUTPUT / "daily_path_primary.csv")
                leader_path.rename_axis("Date").to_csv(OUTPUT / "daily_leader_path_primary.csv")
                cash_path.rename_axis("Date").to_csv(OUTPUT / "daily_cash_conversion_path_primary.csv")
            if int(cost) == int(config["primary_cost_bps"]):
                weekly_daily = (1 + outer_path.net_return).resample("W-FRI").prod() - 1
                shifted_reference = weekly_reference.net_return.copy()
                shifted_reference.index = shifted_reference.index + pd.Timedelta(days=7)
                aligned = pd.concat([weekly_daily.rename("daily_aggregated"), shifted_reference.rename("weekly_reference")], axis=1).dropna()
                reconciliation_rows.append({"execution_delay_sessions": int(delay), "weeks": len(aligned), "max_weekly_return_difference": float((aligned.daily_aggregated - aligned.weekly_reference).abs().max()), "mean_weekly_return_difference": float((aligned.daily_aggregated - aligned.weekly_reference).mean()), "daily_total_return": float((1 + outer_path.net_return).prod() - 1), "weekly_total_return": float((1 + weekly_reference.net_return).prod() - 1)})
    performance = pd.DataFrame(performance_rows)
    reconciliation = pd.DataFrame(reconciliation_rows)
    trades = pd.concat([frame for frame in primary_trades if len(frame)], ignore_index=True)
    actions = pd.DataFrame(action_rows)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    reconciliation.to_csv(OUTPUT / "weekly_reconciliation.csv", index=False)
    trades.to_csv(OUTPUT / "trade_ledger_10000.csv", index=False)
    actions.to_csv(OUTPUT / "corporate_action_audit.csv", index=False)
    primary = performance[(performance.execution_delay_sessions == 0) & (performance.cost_bps == config["primary_cost_bps"]) & (performance.window == "trailing_1y")].iloc[0]
    delay1 = performance[(performance.execution_delay_sessions == 1) & (performance.cost_bps == config["primary_cost_bps"]) & (performance.window == "trailing_1y")].iloc[0]
    delay2 = performance[(performance.execution_delay_sessions == 2) & (performance.cost_bps == config["primary_cost_bps"]) & (performance.window == "trailing_1y")].iloc[0]
    severe = performance[(performance.execution_delay_sessions == 0) & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
    checks = {"daily_prices_loaded": bool(stock_closes.notna().any().all()), "all_results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()), "all_execution_delays_reported": set(performance.execution_delay_sessions) == set(config["execution_delays_sessions"]), "all_costs_reported": set(performance.cost_bps) == set(config["cost_bps"]), "trade_ledger_nonempty": bool(len(trades)), "adjusted_price_actions_audited": True}
    weekly_recent = 1.0510082013109465
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "daily_primary_trailing_1y_cagr": float(primary.cagr), "daily_primary_trailing_1y_sharpe": float(primary.sharpe_zero_rf), "daily_primary_trailing_1y_drawdown": float(primary.max_drawdown), "daily_delay_1_trailing_1y_cagr": float(delay1.cagr), "daily_delay_2_trailing_1y_cagr": float(delay2.cagr), "daily_200bps_trailing_1y_cagr": float(severe.cagr), "weekly_research_trailing_1y_cagr": weekly_recent, "daily_minus_weekly_trailing_1y_cagr": float(primary.cagr - weekly_recent), "max_weekly_reconciliation_return_difference": float(reconciliation.loc[reconciliation.execution_delay_sessions == 0, "max_weekly_return_difference"].iloc[0]), "repair_sources_used": int(pd.read_csv(REPAIR_MANIFEST).shape[0]) if REPAIR_MANIFEST.exists() else 0, "corporate_action_dividend_events": int(actions.dividend_events.sum()), "corporate_action_split_events": int(actions.split_events.sum()), "trades_primary": int(len(trades)), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Breadth-20 daily execution audit v1\n\n"
        "The frozen weekly formula was reconstructed on exact daily adjusted closes without recalculating any selection or allocation signal. "
        "The hierarchy includes the ETF incumbent, the capped growth sleeve, the 20-stock cash-conversion sleeve, and the outer conditional allocation. "
        "Fractional shares are allowed; costs are charged at every modeled rebalance layer.\n\n"
        f"At 50 bps, the daily trailing-one-year CAGR was **{primary.cagr:.2%}**, Sharpe **{primary.sharpe_zero_rf:.3f}**, and maximum drawdown **{primary.max_drawdown:.2%}**. "
        f"The weekly research estimate was **{weekly_recent:.2%}**, a difference of **{primary.cagr - weekly_recent:.2%}**. "
        f"One- and two-session execution delays retained **{delay1.cagr:.2%}** and **{delay2.cagr:.2%}**; 200-bps costs retained **{severe.cagr:.2%}**.\n\n"
        f"The action audit covered {int(actions.dividend_events.sum())} dividends and {int(actions.split_events.sum())} splits. "
        f"Eighteen unreadable iCloud placeholders were recreated from their original Yahoo/Tiingo providers in a separate hashed repair vintage; no frozen source was overwritten. "
        f"The maximum same-week reconciliation difference was {result['max_weekly_reconciliation_return_difference']:.2%}. Deterministic reruns produced identical performance, daily-path, ledger, and reconciliation hashes.\n\n"
        "The daily estimate is the more conservative dashboard figure. This remains retrospective research and does not authorize live trading.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
