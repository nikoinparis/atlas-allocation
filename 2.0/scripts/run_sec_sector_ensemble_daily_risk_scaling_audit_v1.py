#!/usr/bin/env python3
"""Exact-daily audit of the sector ensemble and frozen fixed-exposure amplifiers."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_cash_conversion_breadth20_daily_execution_audit_v1 as daily

CONFIG = ROOT / "config/sec_sector_ensemble_daily_risk_scaling_audit_v1.json"
OUTPUT = ROOT / "evidence/sec_sector_ensemble_daily_risk_scaling_audit_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def leverage_path(source: pd.DataFrame, exposure: float, financing_rate: float,
                  change_cost_bps: float) -> pd.DataFrame:
    rows = []
    wealth, peak = 1.0, 1.0
    previous = 1.0
    for date, source_return in source.net_return.items():
        turnover = abs(float(exposure) - previous)
        financing = max(0.0, float(exposure) - 1.0) * float(financing_rate) / 252.0
        cost = turnover * float(change_cost_bps) / 10000.0
        net = float(exposure) * float(source_return) - financing - cost
        wealth *= 1.0 + net
        peak = max(peak, wealth)
        rows.append({"Date": date, "source_return": source_return, "exposure": exposure,
                     "exposure_turnover": turnover, "turnover": turnover, "financing_cost": financing,
                     "exposure_cost": cost, "net_return": net, "wealth": wealth,
                     "drawdown": wealth / peak - 1.0})
        previous = float(exposure)
    return pd.DataFrame(rows).set_index("Date")


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    leader = pd.read_csv(ROOT / config["daily_leader_path"], parse_dates=["Date"]).set_index("Date")
    index = leader.index
    stock_targets = pd.read_csv(ROOT / config["stock_targets"], dtype={"cik10": str}, parse_dates=["rebalance_at"])
    strategy_targets = pd.read_csv(ROOT / config["strategy_targets"], parse_dates=["Date"]).set_index("Date")
    selected = sorted(stock_targets.cik10.unique())
    sources = daily.frozen_price_sources()
    closes = pd.DataFrame(index=index)
    source_rows, missing = [], []
    for cik in selected:
        if cik not in sources:
            missing.append(cik)
            continue
        source, path = sources[cik]
        try:
            series, source_audit = daily.read_stock_close(path, source, index)
        except OSError:
            missing.append(cik)
            continue
        closes[cik] = series
        source_rows.append({"cik10": cik, **source_audit})
    base_stock_events = {
        pd.Timestamp(date): {str(row.cik10): float(row.intended_weight) for row in frame.itertuples(index=False)}
        for date, frame in stock_targets.groupby("rebalance_at", sort=True)
    }
    base_outer_events = {pd.Timestamp(date): float(row.cash_conversion)
                         for date, row in strategy_targets.iterrows()}
    performance_rows, reconciliation_rows, paths = [], [], {}
    weekly_reference = pd.read_csv(ROOT / config["weekly_reference"], parse_dates=["Date"]).set_index("Date").net_return
    weekly_reference.index = weekly_reference.index + pd.Timedelta(days=7)
    for delay in config["execution_delays_sessions"]:
        stock_events = daily.shift_events(base_stock_events, index, int(delay))
        cash_adjusted_events = {}
        for date, desired in stock_events.items():
            available, cash_weight = {}, 0.0
            for cik, weight in desired.items():
                if cik in closes and pd.notna(closes.at[date, cik]):
                    available[cik] = float(weight)
                else:
                    cash_weight += float(weight)
            if cash_weight > 0:
                available["cash::USD"] = cash_weight
            cash_adjusted_events[date] = available
        stock_events = cash_adjusted_events
        outer_events = daily.shift_events(base_outer_events, index, int(delay))
        sleeve, _ = daily.simulate_static(closes, stock_events, float(config["trading_cost_bps"]), "fundamental_ensemble")
        composite, _ = daily.simulate_outer(index, leader.net_return, sleeve.net_return, outer_events,
                                            float(config["trading_cost_bps"]))
        paths[(int(delay), 1.0)] = composite
        weekly_daily = (1.0 + composite.net_return).resample("W-FRI").prod() - 1.0
        aligned = pd.concat([weekly_daily.rename("daily"), weekly_reference.rename("weekly")], axis=1).dropna()
        reconciliation_rows.append({"execution_delay_sessions": int(delay), "weeks": int(len(aligned)),
                                    "maximum_return_difference": float((aligned.daily - aligned.weekly).abs().max()),
                                    "mean_return_difference": float((aligned.daily - aligned.weekly).mean())})
        for exposure in config["fixed_exposures"]:
            path = composite if float(exposure) == 1.0 else leverage_path(
                composite, float(exposure), float(config["financing_rate_annual"]),
                float(config["outer_exposure_change_cost_bps"])
            )
            paths[(int(delay), float(exposure))] = path
            for window, sample in {
                "full": path,
                "trailing_2y": path.iloc[-504:],
                "trailing_1y": path.iloc[-252:],
                "ytd": path.loc[path.index.year == path.index.max().year],
            }.items():
                performance_rows.append({"execution_delay_sessions": int(delay), "exposure": float(exposure),
                                         "window": window, **daily.daily_metrics(sample)})
    performance = pd.DataFrame(performance_rows)
    reconciliation = pd.DataFrame(reconciliation_rows)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    reconciliation.to_csv(OUTPUT / "weekly_reconciliation.csv", index=False)
    source_audit = pd.DataFrame(source_rows)
    missing_audit = pd.DataFrame({"cik10": missing, "source": "missing_base_case_cash"})
    pd.concat([source_audit, missing_audit], ignore_index=True, sort=False).to_csv(
        OUTPUT / "price_source_audit.csv", index=False
    )
    for exposure in config["fixed_exposures"]:
        paths[(0, float(exposure))].rename_axis("Date").to_csv(OUTPUT / f"daily_path__{float(exposure):.2f}x.csv")
    recent = performance[(performance.execution_delay_sessions == 0) & (performance.window == "trailing_1y")]
    selected = recent[recent.exposure > 1.0].sort_values(["cagr", "sharpe_zero_rf"], ascending=False).iloc[0]
    gates = config["gates"]
    recon = float(reconciliation.loc[reconciliation.execution_delay_sessions == 0, "maximum_return_difference"].iloc[0])
    candidate_pass = bool(
        selected.cagr >= float(gates["minimum_levered_daily_recent_cagr"])
        and selected.sharpe_zero_rf >= float(gates["minimum_levered_daily_recent_sharpe"])
        and selected.max_drawdown >= float(gates["minimum_levered_daily_drawdown"])
        and recon <= float(gates["maximum_weekly_reconciliation_difference"])
    )
    underlying_pass = bool(config["underlying_strategy_falsification_passed"])
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_config_sha256": sha256(CONFIG), "selected_exposure": float(selected.exposure),
        "daily_recent_cagr": float(selected.cagr), "daily_recent_sharpe": float(selected.sharpe_zero_rf),
        "daily_recent_drawdown": float(selected.max_drawdown), "daily_full_cagr": float(
            performance[(performance.execution_delay_sessions == 0) & (performance.exposure == selected.exposure) & (performance.window == "full")].cagr.iloc[0]
        ),
        "unlevered_daily_recent_cagr": float(recent[recent.exposure == 1.0].cagr.iloc[0]),
        "unlevered_daily_recent_sharpe": float(recent[recent.exposure == 1.0].sharpe_zero_rf.iloc[0]),
        "unlevered_daily_recent_drawdown": float(recent[recent.exposure == 1.0].max_drawdown.iloc[0]),
        "maximum_weekly_reconciliation_difference": recon,
        "missing_price_ciks_held_as_cash": missing,
        "candidate_level_gates_passed": candidate_pass,
        "underlying_strategy_falsification_passed": underlying_pass,
        "complete_falsification_passed": bool(candidate_pass and underlying_pass),
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
        "artifact_sha256": {"performance": sha256(OUTPUT / "performance.csv"),
                            "selected_path": sha256(OUTPUT / f"daily_path__{float(selected.exposure):.2f}x.csv"),
                            "reconciliation": sha256(OUTPUT / "weekly_reconciliation.csv")}
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Sector ensemble daily risk-scaling audit v1\n\n"
        f"The frozen ensemble reconstructed at {result['unlevered_daily_recent_cagr']:.2%} trailing-year CAGR, "
        f"{result['unlevered_daily_recent_sharpe']:.3f} Sharpe, and {result['unlevered_daily_recent_drawdown']:.2%} drawdown. "
        f"The selected fixed {result['selected_exposure']:.2f}x diagnostic produced {result['daily_recent_cagr']:.2%} CAGR, "
        f"{result['daily_recent_sharpe']:.3f} Sharpe, and {result['daily_recent_drawdown']:.2%} drawdown.\n\n"
        f"Candidate-level daily gates: **{'PASS' if candidate_pass else 'FAIL'}**. Complete falsification including "
        f"the underlying issuer test: **{'PASS' if candidate_pass and underlying_pass else 'FAIL'}**. "
        "No promotion or live trading was enabled.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
