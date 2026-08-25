#!/usr/bin/env python3
"""Exact-daily reconstruction of cash-only and selected exposure diagnostics."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_cash_conversion_breadth20_daily_execution_audit_v1 as daily
import run_sec_fragility_industry_tournament_v1 as fragility
from systematic_trader.sec_real_tournament_v2 import build_family_weights

CONFIG = ROOT / "config/sec_fragility_exposure_daily_audit_v1.json"
SOURCE_CONFIG = ROOT / "config/sec_fragility_industry_tournament_v1.json"
PROGRAM = ROOT / "config/sec_return_improvement_program_v1.json"
PANEL_ROOT = ROOT / "data/sec_broad_research_panel_v2"
CONTROL_DAILY = ROOT / "evidence/sec_cash_conversion_breadth20_daily_execution_audit_v1/daily_path_primary.csv"
SECTOR_DAILY = ROOT / "evidence/sec_sector_ensemble_daily_risk_scaling_audit_v1/daily_path__1.00x.csv"
SOURCE_EVIDENCE = ROOT / "evidence/sec_fragility_industry_tournament_v1"
OUTPUT = ROOT / "evidence/sec_fragility_exposure_daily_audit_v1"
SEAL = OUTPUT / "execution_seal.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def week_label(value: pd.Timestamp) -> pd.Timestamp:
    return value + pd.Timedelta(days=(4 - value.weekday()) % 7)


def simulate_component_blend(components: pd.DataFrame, target_by_week: pd.DataFrame) -> pd.DataFrame:
    """Hold component notionals within each week and reset at the week boundary."""
    positions = pd.Series(0.0, index=components.columns)
    total = 1.0
    prior_total = 1.0
    prior_label = None
    rows = []
    for date, returns in components.iterrows():
        label = week_label(pd.Timestamp(date))
        if prior_label != label:
            eligible = target_by_week.loc[target_by_week.index <= label]
            target = eligible.iloc[-1] if not eligible.empty else pd.Series(0.0, index=components.columns)
            target = target.reindex(components.columns).fillna(0.0)
            positions = total * target
            prior_label = label
        positions = positions * (1.0 + returns.fillna(0.0))
        total = float(positions.sum())
        rows.append({"Date": date, "net_return": total / prior_total - 1.0, "wealth": total})
        prior_total = total
    output = pd.DataFrame(rows).set_index("Date")
    output["drawdown"] = output.wealth / output.wealth.cummax() - 1.0
    return output


def desired_exposure(source: pd.Series, rule: dict) -> pd.Series:
    if rule["kind"] == "fixed":
        return pd.Series(float(rule["gross"]), index=source.index)
    if rule["kind"] != "volatility_target":
        raise ValueError("unknown daily exposure rule")
    lagged = source.shift(1)
    volatility = lagged.rolling(rule["lookback_sessions"], min_periods=rule["minimum_sessions"]).std(ddof=1) * np.sqrt(252)
    gross = (rule["target_annual_volatility"] / volatility.replace(0, np.nan)).clip(rule["minimum_gross"], rule["maximum_gross"]).fillna(1.0)
    wealth = (1.0 + lagged.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.rolling(rule["drawdown_guard_sessions"], min_periods=2).max() - 1.0
    gross.loc[drawdown <= rule["drawdown_threshold"]] = gross.loc[drawdown <= rule["drawdown_threshold"]].clip(upper=rule["guarded_maximum_gross"])
    return gross


def apply_daily_exposure(source: pd.Series, gross: pd.Series, financing_rate: float, change_cost_bps: float) -> pd.DataFrame:
    previous = 1.0
    wealth = peak = 1.0
    rows = []
    for date, source_return in source.items():
        current = float(gross.loc[date])
        financing = max(0.0, current - 1.0) * financing_rate / 252.0
        change_cost = abs(current - previous) * change_cost_bps / 10000.0
        net = current * float(source_return) - financing - change_cost
        wealth *= 1.0 + net
        peak = max(peak, wealth)
        rows.append({"Date": date, "source_return": source_return, "exposure": current, "financing_cost": financing, "exposure_change_cost": change_cost, "net_return": net, "wealth": wealth, "drawdown": wealth / peak - 1.0})
        previous = current
    return pd.DataFrame(rows).set_index("Date")


def metrics(path: pd.DataFrame) -> dict[str, float | int | str]:
    returns = path.net_return.dropna()
    years = len(returns) / 252.0
    wealth = (1.0 + returns).cumprod()
    std = returns.std(ddof=1)
    prior_wealth = path.wealth.shift(1).fillna(1.0)
    financing_dollars = float((prior_wealth * path.financing_cost * 10000.0).sum())
    exposure_change_dollars = float((prior_wealth * path.exposure_change_cost * 10000.0).sum())
    return {
        "days": int(len(returns)), "start": str(returns.index.min().date()), "end": str(returns.index.max().date()),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(returns.mean() / std * np.sqrt(252)) if std else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "total_return": float(wealth.iloc[-1] - 1.0), "ending_value_10000": float(wealth.iloc[-1] * 10000.0),
        "financing_paid_on_10000": financing_dollars,
        "exposure_change_cost_paid_on_10000": exposure_change_dollars,
    }


def main() -> int:
    config = json.loads(CONFIG.read_text())
    seal = json.loads(SEAL.read_text()) if SEAL.exists() else {}
    seal_valid = all((ROOT / name).exists() and sha256(ROOT / name) == digest for name, digest in seal.get("sealed_sha256", {}).items())
    final = OUTPUT / "final_result.json"
    if not seal_valid or final.exists():
        print(json.dumps({"status": "blocked_execution_seal" if not seal_valid else "blocked_one_shot_already_complete", "live_trading_enabled": False}, indent=2)); return 0
    source_result = json.loads((SOURCE_EVIDENCE / "result.json").read_text())
    if source_result["frozen_config_sha256"] != sha256(SOURCE_CONFIG):
        raise RuntimeError("source config hash mismatch")

    start, end = pd.Timestamp(config["start"]), pd.Timestamp(config["end"])
    control = pd.read_csv(CONTROL_DAILY, parse_dates=["Date"]).set_index("Date").loc[start:end]
    sector = pd.read_csv(SECTOR_DAILY, parse_dates=["Date"]).set_index("Date").loc[start:end]
    index = control.index.intersection(sector.index)
    control = control.reindex(index); sector = sector.reindex(index)

    panel = pd.read_csv(PANEL_ROOT / "panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
    panel["execution_at"] = pd.to_datetime(panel.execution_at, utc=True)
    weekly = pd.read_csv(PANEL_ROOT / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    program = json.loads(PROGRAM.read_text())
    family_weights, _ = build_family_weights(panel, program)
    residual_weights = family_weights["residual_momentum"].copy()
    residual_weights["decision_at"] = pd.to_datetime(residual_weights.decision_at, utc=True).dt.tz_localize(None)

    sources = daily.frozen_price_sources()
    selected = sorted(residual_weights.cik10.astype(str).unique())
    closes = pd.DataFrame(index=index)
    source_rows, missing = [], []
    for cik in selected:
        if cik not in sources:
            missing.append(cik); continue
        source_name, path = sources[cik]
        try:
            series, audit = daily.read_stock_close(path, source_name, index)
        except OSError:
            missing.append(cik); continue
        closes[cik] = series
        source_rows.append({"cik10": cik, **audit})
    base_events = {
        pd.Timestamp(date): {str(row.cik10): float(row.weight) for row in frame.itertuples(index=False)}
        for date, frame in residual_weights.groupby("decision_at", sort=True)
    }
    shifted = daily.shift_events(base_events, index, 0)
    events = {}
    for date, desired in shifted.items():
        available, cash = {}, 0.0
        for cik, weight in desired.items():
            if cik in closes and pd.notna(closes.at[date, cik]):
                available[cik] = weight
            else:
                cash += weight
        if cash:
            available["cash::USD"] = cash
        events[date] = available
    residual, trades = daily.simulate_static(closes, events, config["trading_cost_bps"], "broad_residual_momentum")

    weekly_labels = sorted({week_label(date) for date in index})
    core_targets = pd.DataFrame({"control": config["core_control_weight"], "residual": config["core_residual_weight"]}, index=weekly_labels)
    core = simulate_component_blend(pd.DataFrame({"control": control.net_return, "residual": residual.net_return}, index=index), core_targets)

    endpoint = pd.Timestamp(config["end"], tz="UTC")
    weekly_source = weekly.loc[:endpoint]
    source_config = json.loads(SOURCE_CONFIG.read_text())
    core_paths = fragility.build_core_paths(panel, weekly_source, program, endpoint, [50], [])
    sector_weekly = fragility.sector_weekly_from_daily(endpoint).reindex(core_paths[(50, 0)].index).fillna(0.0)
    diagnostics = pd.read_csv(SOURCE_EVIDENCE / "fragility_diagnostics.csv", parse_dates=["Date"])
    diagnostics.Date = pd.to_datetime(diagnostics.Date, utc=True)
    risk_on = diagnostics[diagnostics.guard == config["source_guard"]].set_index("Date").risk_on.astype(bool).reindex(core_paths[(50, 0)].index).fillna(False)
    beta = fragility.causal_beta(sector_weekly, core_paths[(50, 0)])
    alpha = pd.Series(config["source_alpha_weight"], index=beta.index).where(risk_on, 0.0)
    accelerator_targets = pd.DataFrame({"core": 1.0 - alpha * beta, "sector": alpha})
    accelerator_targets.index = accelerator_targets.index.tz_localize(None)
    source_daily = simulate_component_blend(pd.DataFrame({"core": core.net_return, "sector": sector.net_return}, index=index), accelerator_targets)

    performance_rows, path_columns = [], {}
    for rule in config["daily_paths"]:
        gross = desired_exposure(source_daily.net_return, rule)
        path = apply_daily_exposure(source_daily.net_return, gross, rule["financing_rate"], config["exposure_change_cost_bps"])
        path.rename_axis("Date").to_csv(OUTPUT / f"daily_path__{rule['name']}.csv")
        path_columns[rule["name"]] = path.net_return
        for window, sample in {"full": path, "trailing_2y": path.iloc[-504:], "trailing_1y": path.iloc[-252:]}.items():
            performance_rows.append({"candidate": rule["name"], "window": window, **metrics(sample), "average_exposure": float(path.exposure.mean()), "maximum_exposure": float(path.exposure.max())})
    performance = pd.DataFrame(performance_rows)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    pd.DataFrame(path_columns).rename_axis("Date").to_csv(OUTPUT / "common_daily_paths.csv")
    pd.concat([pd.DataFrame(source_rows), pd.DataFrame({"cik10": missing, "source": "missing_base_case_cash"})], ignore_index=True, sort=False).to_csv(OUTPUT / "price_source_audit.csv", index=False)
    trades.to_csv(OUTPUT / "residual_trade_ledger.csv", index=False)
    source_daily.rename_axis("Date").to_csv(OUTPUT / "daily_source_alpha_path.csv")

    weekly_reconstructed = (1.0 + source_daily.net_return).resample("W-FRI").prod() - 1.0
    weekly_original = pd.read_csv(SOURCE_EVIDENCE / "common_paths.csv", parse_dates=["Date"]).set_index("Date")["alpha30_1.35x"]
    weekly_original.index = pd.to_datetime(weekly_original.index).tz_localize(None)
    # Undo the frozen 1.35x exposure to recover its weekly source return.
    weekly_source_return = (weekly_original + (1.35 - 1.0) * 0.08 / 52.0) / 1.35
    if not weekly_source_return.empty:
        weekly_source_return.iloc[0] += ((1.35 - 1.0) * config["exposure_change_cost_bps"] / 10000.0) / 1.35
    aligned = pd.concat([weekly_reconstructed.rename("daily_aggregate"), weekly_source_return.rename("weekly_source")], axis=1).dropna()
    max_difference = float((aligned.daily_aggregate - aligned.weekly_source).abs().max())
    reconciliation = pd.DataFrame({"daily_aggregate": aligned.daily_aggregate, "weekly_source": aligned.weekly_source, "difference": aligned.daily_aggregate - aligned.weekly_source})
    reconciliation.rename_axis("Date").to_csv(OUTPUT / "weekly_reconciliation.csv")
    artifacts = ["performance.csv", "common_daily_paths.csv", "price_source_audit.csv", "residual_trade_ledger.csv", "daily_source_alpha_path.csv", "weekly_reconciliation.csv", *[f"daily_path__{rule['name']}.csv" for rule in config["daily_paths"]]]
    cash = performance[(performance.candidate == "cash_only_1.00x") & (performance.window == "trailing_1y")].iloc[0].to_dict()
    selected = {rule["name"]: performance[(performance.candidate == rule["name"]) & (performance.window == "trailing_1y")].iloc[0].to_dict() for rule in config["daily_paths"]}
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "status": "exact_daily_audit_complete",
        "cash_only_trailing_1y": cash, "selected_trailing_1y": selected,
        "maximum_weekly_reconciliation_difference": max_difference,
        "reconciliation_within_frozen_tolerance": max_difference <= config["reconciliation_tolerance"],
        "missing_price_ciks_held_as_cash": missing, "cash_only_has_zero_financing": float(cash["financing_paid_on_10000"]) == 0.0,
        "selection_contaminated": True, "strategy_replacement_authorized": False, "live_trading_enabled": False,
        "artifact_sha256": {name: sha256(OUTPUT / name) for name in artifacts},
    }
    final.write_text(json.dumps(result, indent=2, sort_keys=True, default=str, allow_nan=False) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
