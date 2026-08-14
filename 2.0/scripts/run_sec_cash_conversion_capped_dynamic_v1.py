#!/usr/bin/env python3
"""Test ticker-agnostic stock caps inside the conditional cash-conversion sleeve."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic

CONFIG = ROOT / "config/sec_cash_conversion_capped_dynamic_v1.json"
DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
OUTPUT = ROOT / "evidence/sec_cash_conversion_capped_dynamic_v1"


def simulate_cash(prices: pd.DataFrame, targets: dict, scenario: str, cost_bps: float, cap_multiple: float | None, top_n: int = 10) -> tuple[pd.DataFrame, float]:
    positions = {"cash::USD": 1.0}
    rows, peak_weight = [], 0.0
    previous_month = None
    for offset, date in enumerate(prices.index[:-1]):
        total_before = sum(positions.values())
        turnover = 0.0
        if date in targets:
            selected = targets[date]
            intended = 1 / len(selected)
            available = [cik for cik in selected if cik in prices and pd.notna(prices.at[date, cik])]
            missing = [cik for cik in selected if cik not in available]
            current = {key: value / total_before for key, value in positions.items()} if total_before else {"cash::USD": 1.0}
            target = {cik: intended for cik in available}
            if scenario == "base":
                target["cash::USD"] = intended * len(missing)
            turnover = 0.5 * sum(abs(target.get(key, 0) - current.get(key, 0)) for key in set(target) | set(current))
            deployable = total_before * (1 - turnover * cost_bps / 10000)
            positions = {key: deployable * value for key, value in target.items() if value > 0}
        month = (date.year, date.month)
        if cap_multiple is not None and month != previous_month and date not in targets and total_before > 0:
            total_now = sum(positions.values())
            cap = float(cap_multiple) / float(top_n)
            excess = 0.0
            for asset in list(positions):
                if asset == "cash::USD":
                    continue
                maximum = total_now * cap
                if positions[asset] > maximum:
                    excess += positions[asset] - maximum
                    positions[asset] = maximum
            if excess > 0:
                positions["cash::USD"] = positions.get("cash::USD", 0.0) + excess
                extra_turnover = excess / total_now
                extra_cost = total_now * extra_turnover * cost_bps / 10000
                positions["cash::USD"] = max(0.0, positions.get("cash::USD", 0.0) - extra_cost)
                turnover += extra_turnover
        total_invested = sum(positions.values())
        for asset, value in positions.items():
            if asset != "cash::USD" and total_invested > 0:
                peak_weight = max(peak_weight, value / total_invested)
        next_date = prices.index[offset + 1]
        next_positions = {}
        for asset, value in positions.items():
            if asset == "cash::USD":
                next_positions[asset] = next_positions.get(asset, 0.0) + value
                continue
            start, finish = prices.at[date, asset], prices.at[next_date, asset]
            if pd.notna(start) and pd.notna(finish) and float(start) != 0:
                next_positions[asset] = value * float(finish) / float(start)
            elif scenario == "base":
                next_positions["cash::USD"] = next_positions.get("cash::USD", 0.0) + value
        positions = next_positions
        total_after = sum(positions.values())
        rows.append({"Date": date, "gross_return": total_after / total_before - 1, "net_return": total_after / total_before - 1, "turnover": turnover, "cost": turnover * cost_bps / 10000, "wealth": total_after})
        previous_month = month
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1
    return path, peak_weight


def overlay_target(index: pd.DatetimeIndex, leader: pd.Series, cash: pd.Series, lookback: int, high: float, delay: int = 0) -> pd.DataFrame:
    signal = pd.DataFrame({"leader": leader, "cash_conversion": cash}).reindex(index)
    trend = dynamic.rolling_total(signal, lookback)
    active = ((trend.cash_conversion > trend.leader) & (trend.cash_conversion > 0)).shift(delay).fillna(False)
    target = pd.DataFrame(0.0, index=index, columns=["leader", "cash_conversion"])
    target.cash_conversion = np.where(active, high, 0.0)
    target.leader = 1 - target.cash_conversion
    return target


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    choices = pd.read_csv(DISCOVERY / "portfolio_choices.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = choices[choices.family == "cash_conversion"]
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    stock_targets = base.build_targets(choices, index)
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(choices.cik10)):
        if cik in sources:
            source, path = sources[cik]
            series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
    weekly = pd.DataFrame(series, index=index)

    cash_paths, peaks = {}, {}
    for scenario in config["scenarios"]:
        for cost in config["cost_bps"]:
            for cap in config["cash_sleeve_cap_multiples"]:
                label = "uncapped" if cap is None else f"cap_{cap:.2f}x"
                cash_paths[(scenario, int(cost), label)], peaks[(scenario, int(cost), label)] = simulate_cash(weekly, stock_targets, scenario, float(cost), cap)
    performance_rows, composite_paths = [], {}
    for cap in config["cash_sleeve_cap_multiples"]:
        cap_label = "uncapped" if cap is None else f"cap_{cap:.2f}x"
        signal_cash = cash_paths[("base", 50, cap_label)].net_return
        signal_leader = dynamic.read_path(LEADER / "path__base__confidence_10_40__cap_1.50x__50bps.csv").net_return
        common_signal = pd.concat([signal_leader.rename("leader"), signal_cash.rename("cash_conversion")], axis=1).dropna()
        for lookback in config["lookbacks"]:
            for high in config["active_allocations"]:
                target = overlay_target(common_signal.index, common_signal.leader, common_signal.cash_conversion, int(lookback), float(high))
                name = f"{cap_label}__{lookback}w__{int(high*100):02d}"
                for scenario in config["scenarios"]:
                    for cost in config["cost_bps"]:
                        leader = dynamic.read_path(LEADER / f"path__{scenario}__confidence_10_40__cap_1.50x__{cost}bps.csv").net_return
                        cash = cash_paths[(scenario, int(cost), cap_label)].net_return
                        returns = pd.concat([leader.rename("leader"), cash.rename("cash_conversion")], axis=1).dropna()
                        path = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
                        composite_paths[(name, scenario, int(cost))] = path
                        performance_rows.extend(base.metric_rows(name, scenario, int(cost), path))
    performance = pd.DataFrame(performance_rows)
    screen = performance[(performance.scenario == "base") & (performance.cost_bps == 50) & performance.window.isin(["full_recent", "trailing_1y", "ytd"])].pivot(index="candidate", columns="window", values=["cagr", "sharpe_zero_rf", "max_drawdown"])
    screen.columns = [f"{a}_{b}" for a, b in screen.columns]
    severe = performance[(performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].set_index("candidate")
    screen["trailing_1y_200bps_cagr"] = severe.cagr
    screen = screen.reset_index().sort_values("cagr_trailing_1y", ascending=False)
    best = screen.iloc[0]

    delay_rows = []
    cap_label, lookback_text, high_text = best.candidate.split("__")
    lookback, high = int(lookback_text[:-1]), int(high_text) / 100
    signal_cash = cash_paths[("base", 50, cap_label)].net_return
    signal_leader = dynamic.read_path(LEADER / "path__base__confidence_10_40__cap_1.50x__50bps.csv").net_return
    returns = pd.concat([signal_leader.rename("leader"), signal_cash.rename("cash_conversion")], axis=1).dropna()
    for delay in (0, 1, 2):
        target = overlay_target(returns.index, returns.leader, returns.cash_conversion, lookback, high, delay)
        path = dynamic.simulate(returns, target, 50.0)
        delay_rows.extend(row for row in base.metric_rows(best.candidate, f"delay_{delay}", 50, path) if row["window"] in {"full_recent", "trailing_1y", "ytd"})
    delays = pd.DataFrame(delay_rows)
    screen.to_csv(OUTPUT / "screening.csv", index=False)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    for cost in config["cost_bps"]:
        composite_paths[(best.candidate, "base", int(cost))].rename_axis("Date").to_csv(OUTPUT / f"best_path__base__{cost}bps.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "candidate_count": int(len(screen)),
        "best_candidate": best.candidate, "best_trailing_1y_cagr": float(best.cagr_trailing_1y), "best_trailing_1y_sharpe": float(best.sharpe_zero_rf_trailing_1y),
        "best_trailing_1y_drawdown": float(best.max_drawdown_trailing_1y), "best_ytd_cagr": float(best.cagr_ytd), "best_full_cagr": float(best.cagr_full_recent),
        "best_200bps_trailing_1y_cagr": float(best.trailing_1y_200bps_cagr), "cash_sleeve_peak_internal_stock_weight": float(peaks[("base", 50, cap_label)]),
        "maximum_target_total_portfolio_stock_weight": float(high * peaks[("base", 50, cap_label)]),
        "one_week_delay_trailing_1y_cagr": float(delays[(delays.scenario == "delay_1") & (delays.window == "trailing_1y")].cagr.iloc[0]),
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
