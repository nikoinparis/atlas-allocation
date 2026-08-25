#!/usr/bin/env python3
"""One-shot exposure mathematics study for the 186.90% fragile candidate."""

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
BASE_SPEC = importlib.util.spec_from_file_location("fragility_v1", ROOT / "scripts/run_sec_fragility_industry_tournament_v1.py")
fragility = importlib.util.module_from_spec(BASE_SPEC); assert BASE_SPEC.loader is not None; BASE_SPEC.loader.exec_module(fragility)
from systematic_trader import sec_quant_math_tournament_v3 as quant

CONFIG = ROOT / "config/sec_fragility_exposure_control_v1.json"
SOURCE_CONFIG = ROOT / "config/sec_fragility_industry_tournament_v1.json"
PANEL_ROOT = ROOT / "data/sec_broad_research_panel_v2"
PROGRAM = ROOT / "config/sec_return_improvement_program_v1.json"
SOURCE_EVIDENCE = ROOT / "evidence/sec_fragility_industry_tournament_v1"
OUTPUT = ROOT / "evidence/sec_fragility_exposure_control_v1"
SEAL = OUTPUT / "execution_seal.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dynamic_exposure(base: pd.Series, rule: dict, common: dict, risk_on: pd.Series | None = None) -> pd.Series:
    if "gross" in rule:
        return pd.Series(float(rule["gross"]), index=base.index)
    if "target_annual_volatility" in rule:
        lagged = base.shift(1)
        vol = lagged.rolling(common["lookback_weeks"], min_periods=common["minimum_history_weeks"]).std(ddof=1) * np.sqrt(52)
        gross = (rule["target_annual_volatility"] / vol.replace(0, np.nan)).clip(common["minimum_gross"], rule["maximum_gross"]).fillna(1.0)
    elif "fraction" in rule:
        lagged = base.shift(1)
        mean = lagged.rolling(common["lookback_weeks"], min_periods=common["minimum_history_weeks"]).mean()
        variance = lagged.rolling(common["lookback_weeks"], min_periods=common["minimum_history_weeks"]).var().replace(0, np.nan)
        gross = (rule["fraction"] * mean / variance).clip(common["minimum_gross"], rule["maximum_gross"]).fillna(1.0)
    elif "risk_on_gross" in rule:
        if risk_on is None:
            raise ValueError("fragility tier requires risk_on series")
        gross = pd.Series(float(rule["risk_off_gross"]), index=base.index)
        gross.loc[risk_on.reindex(base.index).fillna(False)] = float(rule["risk_on_gross"])
    else:
        raise ValueError("unknown exposure rule")
    if "risk_on_gross" not in rule:
        wealth = (1.0 + base.shift(1).fillna(0.0)).cumprod()
        drawdown = wealth / wealth.rolling(common["drawdown_guard_weeks"], min_periods=2).max() - 1.0
        gross.loc[drawdown <= common["drawdown_guard_threshold"]] = gross.loc[drawdown <= common["drawdown_guard_threshold"]].clip(upper=common["guarded_maximum_gross"])
    return gross


def main() -> int:
    config = json.loads(CONFIG.read_text())
    source_config = json.loads(SOURCE_CONFIG.read_text())
    source_result = json.loads((SOURCE_EVIDENCE / "result.json").read_text())
    seal = json.loads(SEAL.read_text()) if SEAL.exists() else {}
    seal_valid = all((ROOT / name).exists() and sha256(ROOT / name) == digest for name, digest in seal.get("sealed_sha256", {}).items())
    final = OUTPUT / "final_result.json"
    if not seal_valid or final.exists():
        print(json.dumps({"status": "blocked_execution_seal" if not seal_valid else "blocked_one_shot_already_complete", "live_trading_enabled": False}, indent=2)); return 0
    if sha256(SOURCE_CONFIG) != source_result["frozen_config_sha256"]:
        raise RuntimeError("source candidate config hash mismatch")

    endpoint = pd.Timestamp(config["common_endpoint"], tz="UTC")
    panel = pd.read_csv(PANEL_ROOT / "panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
    panel["execution_at"] = pd.to_datetime(panel.execution_at, utc=True)
    weekly = pd.read_csv(PANEL_ROOT / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True); weekly = weekly.loc[:endpoint]
    program = json.loads(PROGRAM.read_text())
    delays = list(map(int, config["costs"]["execution_delays_weeks"]))
    core_paths = fragility.build_core_paths(panel, weekly, program, endpoint, [50, 200], delays)
    sector_paths = fragility.rebuild_sector_paths(source_config)
    sector = fragility.sector_weekly_from_daily(endpoint).reindex(core_paths[(50, 0)].index).fillna(0.0)
    diagnostics = pd.read_csv(SOURCE_EVIDENCE / "fragility_diagnostics.csv", parse_dates=["Date"])
    diagnostics.Date = pd.to_datetime(diagnostics.Date, utc=True)
    risk_on = diagnostics[diagnostics.guard == config["source_guard"]].set_index("Date").risk_on.astype(bool).reindex(core_paths[(50, 0)].index).fillna(False)

    base, _ = fragility.accelerator_return(core_paths[(50, 0)], sector, config["source_alpha_weight"], risk_on)
    severe_base, _ = fragility.accelerator_return(core_paths[(200, 0)], sector_paths["base_200"].reindex(base.index).fillna(0.0), config["source_alpha_weight"], risk_on)
    delayed_bases = [fragility.accelerator_return(core_paths[(50, delay)], sector_paths["delay_worst"].reindex(base.index).fillna(0.0), config["source_alpha_weight"], risk_on)[0] for delay in delays]
    issuer_base, _ = fragility.accelerator_return(core_paths[(50, 0)], sector_paths["worst_five"].reindex(base.index).fillna(0.0), config["source_alpha_weight"], risk_on)

    rules = [*config["fixed_rules"], *config["volatility_target_rules"], *config["fractional_kelly_rules"], *config["fragility_tier_rules"]]
    if len(rules) != config["candidate_count"]:
        raise RuntimeError("candidate count mismatch")
    baseline, _ = fragility.apply_exposure(base, 1.35, 0.08, config["costs"]["exposure_change_bps"])
    paths, rows = {}, []
    for rule in rules:
        gross = dynamic_exposure(base, rule, config["dynamic_rule_common"], risk_on)
        path, _ = fragility.apply_exposure(base, gross, rule["financing_rate"], config["costs"]["exposure_change_bps"])
        severe_gross = dynamic_exposure(severe_base, rule, config["dynamic_rule_common"], risk_on)
        severe, _ = fragility.apply_exposure(severe_base, severe_gross, rule["financing_rate"], config["costs"]["exposure_change_bps"])
        delayed = []
        for delayed_base in delayed_bases:
            delayed_gross = dynamic_exposure(delayed_base, rule, config["dynamic_rule_common"], risk_on)
            delayed.append(fragility.apply_exposure(delayed_base, delayed_gross, rule["financing_rate"], config["costs"]["exposure_change_bps"])[0])
        issuer_gross = dynamic_exposure(issuer_base, rule, config["dynamic_rule_common"], risk_on)
        issuer, _ = fragility.apply_exposure(issuer_base, issuer_gross, rule["financing_rate"], config["costs"]["exposure_change_bps"])
        full = quant.metrics(path); recent = quant.metrics(path.tail(52)); two_year = quant.metrics(path.tail(104))
        raw = min(quant.block_bootstrap_probability(path - baseline, block, config["bootstrap_draws"], config["bootstrap_seed"]) for block in config["bootstrap_blocks_weeks"])
        adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw) * config["familywise_trials"]))
        rolling26 = quant.rolling_outperformance(path, baseline, 26)[0]
        rows.append({
            "candidate": rule["name"], "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["max_drawdown"],
            "two_year_cagr": two_year["cagr"], "two_year_sharpe": two_year["sharpe"], "two_year_drawdown": two_year["max_drawdown"],
            "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["max_drawdown"],
            "severe_200bps_recent_cagr": quant.metrics(severe.tail(52))["cagr"],
            "worst_delay_recent_cagr": min(quant.metrics(value.tail(52))["cagr"] for value in delayed),
            "worst_five_issuer_recent_cagr": quant.metrics(issuer.tail(52))["cagr"],
            "rolling_26w_outperformance_share": rolling26, "raw_bootstrap_probability": raw,
            "familywise_bootstrap_probability": adjusted, "deflated_sharpe_probability": quant.deflated_sharpe_probability(path, config["familywise_trials"]),
            "average_gross_exposure": float(gross.mean()), "maximum_gross_exposure": float(gross.max()),
        })
        paths[rule["name"]] = path
    screening = pd.DataFrame(rows)
    pbo = quant.probability_of_backtest_overfitting(pd.DataFrame(paths), config["cscv_partitions"])
    screening["probability_of_backtest_overfitting"] = pbo
    gates = config["historical_gates"]
    screening["passes_historical_gates"] = (
        screening.recent_cagr.ge(gates["minimum_recent_cagr"]) & screening.recent_sharpe.ge(gates["minimum_recent_sharpe"])
        & screening.recent_drawdown.ge(gates["minimum_recent_drawdown"]) & screening.two_year_cagr.ge(gates["minimum_two_year_cagr"])
        & screening.severe_200bps_recent_cagr.ge(gates["minimum_200bps_recent_cagr"])
        & screening.worst_delay_recent_cagr.ge(gates["minimum_worst_delay_recent_cagr"])
        & screening.worst_five_issuer_recent_cagr.ge(gates["minimum_worst_five_issuer_recent_cagr"])
        & screening.rolling_26w_outperformance_share.ge(gates["minimum_rolling_26w_outperformance_share"])
        & screening.familywise_bootstrap_probability.ge(gates["minimum_familywise_bootstrap_probability"])
        & screening.deflated_sharpe_probability.ge(gates["minimum_deflated_sharpe_probability"])
        & screening.probability_of_backtest_overfitting.le(gates["maximum_probability_of_backtest_overfitting"])
    )
    screening = screening.sort_values(["passes_historical_gates", "recent_cagr"], ascending=False).reset_index(drop=True)
    selected = screening.iloc[0].to_dict()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    screening.to_csv(OUTPUT / "screening.csv", index=False)
    pd.DataFrame(paths).rename_axis("Date").to_csv(OUTPUT / "candidate_paths.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "status": "one_shot_complete",
        "candidate_count": len(screening), "historical_gate_passers": int(screening.passes_historical_gates.sum()),
        "selected_diagnostic": selected["candidate"], "selected_metrics": selected,
        "source_candidate_recent_cagr": source_result["selected_metrics"]["recent_cagr"],
        "selection_contaminated": True, "strategy_replacement_authorized": False, "live_trading_enabled": False,
        "artifact_sha256": {"screening.csv": sha256(OUTPUT / "screening.csv"), "candidate_paths.csv": sha256(OUTPUT / "candidate_paths.csv")},
    }
    final.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (OUTPUT / "report.md").write_text(f"# Fragility exposure control v1\n\nThe strongest diagnostic was `{selected['candidate']}` at {selected['recent_cagr']:.2%} recent CAGR, {selected['recent_sharpe']:.3f} Sharpe, and {selected['recent_drawdown']:.2%} drawdown. Historical gate passers: **{int(screening.passes_historical_gates.sum())}**. No promotion or live trading is authorized.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
