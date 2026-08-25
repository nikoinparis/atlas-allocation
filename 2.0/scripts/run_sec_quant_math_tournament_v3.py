#!/usr/bin/env python3
"""One-shot, seal-locked broad quant mathematics tournament v3."""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from systematic_trader import sec_quant_math_tournament_v3 as quant

CONFIG = ROOT / "config/sec_quant_math_tournament_v3.json"
PANEL = ROOT / "data/sec_broad_research_panel_v2"
GATE = ROOT / "evidence/sec_broad_research_gate_v2/result.json"
OUTPUT = ROOT / "evidence/sec_quant_math_tournament_v3"
SEAL = OUTPUT / "execution_seal.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_hashes(directory: Path, mapping: dict[str, str]) -> bool:
    return all((directory / name).exists() and sha256(directory / name) == digest for name, digest in mapping.items())


def authorization_state(gate: dict, panel_verified: bool, seal_verified: bool, result_exists: bool) -> str:
    if not bool(gate.get("strategy_testing_authorized", False)):
        return "blocked_research_gate"
    if not panel_verified:
        return "blocked_panel_hashes"
    if not seal_verified:
        return "blocked_execution_seal"
    if result_exists:
        return "blocked_one_shot_already_complete"
    return "authorized_one_shot_research"


def _sector_map(panel: pd.DataFrame) -> dict[str, str]:
    ordered = panel.sort_values("decision_at")
    return ordered.drop_duplicates("cik10", keep="last").set_index("cik10").sector.astype(str).to_dict()


def _remove_contributors(candidate: pd.Series, contributions: pd.DataFrame, gross: pd.Series, names: list[str]) -> pd.Series:
    existing = [name for name in names if name in contributions]
    if not existing:
        return candidate.copy()
    removed = contributions[existing].sum(axis=1).mul(gross, axis=0)
    return candidate - removed


def main() -> int:
    config = json.loads(CONFIG.read_text())
    gate = json.loads(GATE.read_text())
    manifest = json.loads((PANEL / "manifest.json").read_text())
    panel_verified = verify_hashes(PANEL, manifest["artifact_sha256"])
    seal_verified = False
    if SEAL.exists():
        seal = json.loads(SEAL.read_text())
        seal_verified = all((ROOT / name).exists() and sha256(ROOT / name) == digest for name, digest in seal.get("sealed_sha256", {}).items())
    final_path = OUTPUT / "final_result.json"
    state = authorization_state(gate, panel_verified, seal_verified, final_path.exists())
    if state != "authorized_one_shot_research":
        print(json.dumps({"experiment": config["experiment"], "status": state, "performance_evaluated": final_path.exists(), "live_trading_enabled": False}, indent=2))
        return 0

    quarterly = pd.read_csv(PANEL / "panel.csv.gz", dtype={"cik10": str})
    weekly = pd.read_csv(PANEL / "weekly_returns.csv.gz", index_col=0, parse_dates=True)
    weekly.index = pd.to_datetime(weekly.index, utc=True)
    weekly.columns = weekly.columns.astype(str).str.zfill(10)
    benchmarks = pd.read_csv(PANEL / "benchmark_weekly_returns.csv.gz", index_col=0, parse_dates=True)
    benchmarks.index = pd.to_datetime(benchmarks.index, utc=True)
    control = benchmarks[config["benchmark_column"]].reindex(weekly.index).fillna(0.0)

    monthly = quant.build_monthly_feature_panel(quarterly, weekly, config)
    signals, ridge_audit = quant.build_signal_panel(monthly, config)
    targets = quant.build_base_targets(signals, weekly, config)
    expected_base = config["candidate_accounting"]["base_candidates"]
    if len(targets) != expected_base:
        raise RuntimeError(f"expected {expected_base} base candidates, built {len(targets)}")

    sectors = _sector_map(monthly)
    primary_cost = config["costs"]["primary_bps"]
    stress_cost = max(config["costs"]["stress_bps"])
    financing = config["costs"]["primary_financing_rate"]
    change_cost = config["costs"]["exposure_change_bps"]
    candidate_paths: dict[str, pd.Series] = {}
    rows: list[dict] = []
    common_endpoint = pd.Timestamp(config["common_reference_endpoint"], tz="UTC")

    for base_name, target in sorted(targets.items()):
        base, contributions, turnover = quant.portfolio_path(target, weekly, primary_cost)
        severe_base, _, _ = quant.portfolio_path(target, weekly, stress_cost)
        adverse_base, _, _ = quant.portfolio_path(target, weekly, primary_cost, missing_scenario="adverse_total_loss")
        delayed_bases = [
            quant.portfolio_path(target, weekly, primary_cost, extra_delay_weeks=delay)[0]
            for delay in config["stress_tests"]["additional_execution_delays_weeks"]
        ]
        for rule in config["exposure_rules"]:
            name = f"{base_name}__{rule['name']}"
            gross = quant.exposure_series(base, rule)
            candidate = quant.apply_exposure(base, gross, financing, change_cost)
            severe_gross = quant.exposure_series(severe_base, rule)
            severe = quant.apply_exposure(severe_base, severe_gross, financing, change_cost)
            adverse_gross = quant.exposure_series(adverse_base, rule)
            adverse = quant.apply_exposure(adverse_base, adverse_gross, financing, change_cost)
            delayed = [
                quant.apply_exposure(path, quant.exposure_series(path, rule), financing, change_cost)
                for path in delayed_bases
            ]
            candidate_paths[name] = candidate
            exposed_contributions = contributions.mul(gross, axis=0)
            recent_positive = exposed_contributions.tail(52).sum().clip(lower=0.0)
            positive_sum = float(recent_positive.sum())
            top_issuers = recent_positive.sort_values(ascending=False).head(config["stress_tests"]["remove_top_positive_issuers"]).index.astype(str).tolist()
            issuer_share = float(recent_positive.max() / positive_sum) if positive_sum > 0 else 0.0
            by_sector: dict[str, float] = {}
            for cik, value in recent_positive.items():
                by_sector[sectors.get(str(cik), "unknown")] = by_sector.get(sectors.get(str(cik), "unknown"), 0.0) + float(value)
            worst_sector = max(by_sector, key=by_sector.get) if by_sector else "unknown"
            worst_sector_names = [cik for cik in contributions.columns.astype(str) if sectors.get(cik, "unknown") == worst_sector]
            issuer_removed = _remove_contributors(candidate, contributions, gross, top_issuers)
            sector_removed = _remove_contributors(candidate, contributions, gross, worst_sector_names)
            full = quant.metrics(candidate)
            recent = quant.metrics(candidate.tail(52))
            two_year = quant.metrics(candidate.tail(104))
            common = quant.metrics(candidate.loc[:common_endpoint].tail(52))
            rolling = {window: quant.rolling_outperformance(candidate, control, window) for window in config["stress_tests"]["rolling_windows_weeks"]}
            raw_bootstrap = min(
                quant.block_bootstrap_probability(candidate - control, block, config["stress_tests"]["bootstrap_draws"], config["stress_tests"]["bootstrap_seed"])
                for block in config["stress_tests"]["bootstrap_blocks_weeks"]
            )
            trials = config["candidate_accounting"]["familywise_trials"]
            adjusted = max(0.0, 1.0 - min(1.0, (1.0 - raw_bootstrap) * trials))
            rows.append({
                "candidate": name, "base_candidate": base_name, "signal_family": base_name.split("__")[0],
                "breadth": int(base_name.split("__n")[1].split("__")[0]),
                "construction": base_name.rsplit("__", 1)[1], "exposure_rule": rule["name"],
                "full_cagr": full["cagr"], "full_sharpe": full["sharpe"], "full_drawdown": full["max_drawdown"],
                "recent_cagr": recent["cagr"], "recent_sharpe": recent["sharpe"], "recent_drawdown": recent["max_drawdown"],
                "two_year_cagr": two_year["cagr"], "two_year_sharpe": two_year["sharpe"], "two_year_drawdown": two_year["max_drawdown"],
                "common_endpoint_recent_cagr": common["cagr"],
                "severe_200bps_recent_cagr": quant.metrics(severe.tail(52))["cagr"],
                "worst_delay_recent_cagr": min(quant.metrics(path.tail(52))["cagr"] for path in delayed),
                "adverse_missing_recent_cagr": quant.metrics(adverse.tail(52))["cagr"],
                "worst_five_issuer_recent_cagr": quant.metrics(issuer_removed.tail(52))["cagr"],
                "worst_sector_removed_recent_cagr": quant.metrics(sector_removed.tail(52))["cagr"],
                "maximum_positive_issuer_share": issuer_share, "removed_issuers": "|".join(top_issuers),
                "worst_positive_sector": worst_sector,
                "rolling_26w_outperformance_share": rolling[26][0], "rolling_26w_windows": rolling[26][1],
                "rolling_52w_outperformance_share": rolling[52][0], "rolling_104w_outperformance_share": rolling[104][0],
                "raw_bootstrap_probability": raw_bootstrap, "familywise_bootstrap_probability": adjusted,
                "deflated_sharpe_probability": quant.deflated_sharpe_probability(candidate, trials),
                "average_gross_exposure": float(gross.mean()), "maximum_gross_exposure": float(gross.max()),
                "annualized_turnover": float(turnover.mean() * 52),
            })

    screening = pd.DataFrame(rows)
    paths = pd.DataFrame(candidate_paths)
    pbo = quant.probability_of_backtest_overfitting(paths, config["stress_tests"]["cscv_partitions"])
    gates = config["historical_research_gates"]
    screening["probability_of_backtest_overfitting"] = pbo
    screening["passes_historical_gates"] = (
        screening.recent_cagr.ge(gates["minimum_recent_cagr"])
        & screening.recent_sharpe.ge(gates["minimum_recent_sharpe"])
        & screening.recent_drawdown.ge(gates["minimum_recent_drawdown"])
        & screening.two_year_cagr.ge(gates["minimum_two_year_cagr"])
        & screening.severe_200bps_recent_cagr.ge(gates["minimum_200bps_recent_cagr"])
        & screening.worst_delay_recent_cagr.ge(gates["minimum_worst_delay_recent_cagr"])
        & screening.worst_five_issuer_recent_cagr.ge(gates["minimum_worst_five_issuer_recent_cagr"])
        & screening.rolling_26w_outperformance_share.ge(gates["minimum_rolling_26w_outperformance_share"])
        & screening.familywise_bootstrap_probability.ge(gates["minimum_familywise_bootstrap_probability"])
        & screening.deflated_sharpe_probability.ge(gates["minimum_deflated_sharpe_probability"])
        & screening.probability_of_backtest_overfitting.le(gates["maximum_probability_of_backtest_overfitting"])
    )
    screening = screening.sort_values(["passes_historical_gates", "recent_cagr", "recent_sharpe"], ascending=[False, False, False]).reset_index(drop=True)
    selected = screening.iloc[0].to_dict()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(OUTPUT / "monthly_feature_panel.csv.gz", index=False, compression="gzip")
    ridge_audit.to_csv(OUTPUT / "causal_ridge_audit.csv", index=False)
    screening.to_csv(OUTPUT / "screening.csv", index=False)
    paths.to_csv(OUTPUT / "candidate_paths.csv.gz", compression="gzip")
    selected_path = paths[selected["candidate"]].rename("net_return")
    selected_path.to_csv(OUTPUT / "selected_path.csv")
    artifacts = ["monthly_feature_panel.csv.gz", "causal_ridge_audit.csv", "screening.csv", "candidate_paths.csv.gz", "selected_path.csv"]
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "one_shot_tournament_complete", "candidate_count": len(screening),
        "base_candidate_count": len(targets), "historical_gate_passers": int(screening.passes_historical_gates.sum()),
        "selected_diagnostic": selected["candidate"],
        "selected_metrics": {key: selected[key] for key in [
            "recent_cagr", "recent_sharpe", "recent_drawdown", "two_year_cagr", "two_year_sharpe", "two_year_drawdown",
            "common_endpoint_recent_cagr", "severe_200bps_recent_cagr", "worst_delay_recent_cagr",
            "worst_five_issuer_recent_cagr", "worst_sector_removed_recent_cagr", "rolling_26w_outperformance_share",
            "familywise_bootstrap_probability", "deflated_sharpe_probability", "probability_of_backtest_overfitting",
            "average_gross_exposure", "maximum_gross_exposure", "passes_historical_gates"
        ]},
        "historical_references": config["historical_references"],
        "selection_contaminated": True, "strategy_replacement_authorized": False, "live_trading_enabled": False,
        "required_next_step": "untouched forward evidence for any retained candidate",
        "artifact_sha256": {name: sha256(OUTPUT / name) for name in artifacts},
    }
    final_path.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    (OUTPUT / "report.md").write_text(
        "# SEC quant mathematics tournament v3\n\n"
        f"The one-shot, 96-candidate tournament selected `{selected['candidate']}` as its strongest historical diagnostic. "
        f"It produced {selected['recent_cagr']:.2%} trailing-52-week CAGR, {selected['recent_sharpe']:.3f} Sharpe, "
        f"and {selected['recent_drawdown']:.2%} drawdown. Historical gate passers: **{int(screening.passes_historical_gates.sum())}**.\n\n"
        "This tournament was designed after observing prior project results. No historical result authorizes replacement or live trading.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
