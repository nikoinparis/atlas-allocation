#!/usr/bin/env python3
"""Search controlled allocations of validated survivorship-aware valuation sleeves."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_survivorship_valuation_overlay_search_v1.json"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
VALUATION = ROOT / "evidence/sec_survivorship_valuation_falsification_v1"
OUTPUT = ROOT / "evidence/sec_survivorship_valuation_overlay_search_v1"


def load_sleeve(name: str) -> pd.Series:
    if name.endswith("__exclude_split_affected"):
        path = VALUATION / "best_path_excluding_split_affected_50bps.csv"
    else:
        path = VALUATION / "candidate_paths_50bps" / f"{name}.csv"
    return pd.read_csv(path, parse_dates=["Date"]).set_index("Date").net_return.rename(name)


def metrics(returns: pd.Series) -> dict[str, float]:
    years = len(returns) / 52.0
    wealth = (1.0 + returns).cumprod()
    volatility = returns.std(ddof=1)
    return {"cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0), "sharpe": float(returns.mean() / volatility * np.sqrt(52)) if volatility else 0.0, "drawdown": float((wealth / wealth.cummax() - 1.0).min()), "total_return": float(wealth.iloc[-1] - 1.0)}


def simulate(control: pd.Series, sleeve: pd.Series, target: pd.Series, outer_cost_bps: float) -> pd.DataFrame:
    target = target.reindex(control.index).fillna(0.0).clip(0.0, 0.5)
    turnover = target.diff().abs().fillna(target.abs())
    gross = (1.0 - target) * control + target * sleeve
    cost = turnover * outer_cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    return pd.DataFrame({"leader_weight": 1.0 - target, "valuation_weight": target, "gross_return": gross, "turnover": turnover, "cost": cost, "net_return": net, "wealth": wealth, "drawdown": wealth / wealth.cummax() - 1.0})


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    control = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").net_return.rename("control")
    rows, paths = [], {}
    for sleeve_name in config["valuation_candidates"]:
        sleeve = load_sleeve(sleeve_name)
        joined = pd.concat([control, sleeve], axis=1, join="inner").dropna()
        windows = {"full_recent": joined.index >= joined.index.min(), "trailing_2y": joined.index >= joined.index.max() - pd.DateOffset(years=2), "trailing_1y": joined.index >= joined.index.max() - pd.DateOffset(years=1), "ytd": joined.index.year == joined.index.max().year}
        for lookback in config["lookbacks_weeks"]:
            leader_prior = (1.0 + joined.control).rolling(int(lookback)).apply(np.prod, raw=True).sub(1.0).shift(int(config["signal_shift_weeks"]))
            sleeve_prior = (1.0 + joined[sleeve_name]).rolling(int(lookback)).apply(np.prod, raw=True).sub(1.0).shift(int(config["signal_shift_weeks"]))
            for gate in config["gates"]:
                for allocation in config["allocations"]:
                    if gate == "static":
                        target = pd.Series(float(allocation), index=joined.index)
                    elif gate == "relative":
                        target = (sleeve_prior > leader_prior).astype(float) * float(allocation)
                    elif gate == "relative_positive":
                        target = ((sleeve_prior > leader_prior) & (sleeve_prior > 0.0)).astype(float) * float(allocation)
                    elif gate == "leader_negative_relative":
                        target = ((leader_prior < 0.0) & (sleeve_prior > leader_prior)).astype(float) * float(allocation)
                    else:
                        target = ((leader_prior < 0.0) & (sleeve_prior > 0.0)).astype(float) * float(allocation)
                    for cost in config["outer_cost_bps"]:
                        name = f"{sleeve_name}__{gate}__lb{lookback}__w{allocation:.2f}__{cost}bps"
                        path = simulate(joined.control, joined[sleeve_name], target, float(cost))
                        paths[name] = path
                        for window, mask in windows.items():
                            result = metrics(path.loc[mask, "net_return"])
                            rows.append({"candidate": name, "sleeve": sleeve_name, "gate": gate, "lookback_weeks": lookback, "allocation": allocation, "outer_cost_bps": cost, "window": window, **result, "active_share": float((path.valuation_weight > 0).mean()), "average_valuation_weight": float(path.valuation_weight.mean())})
    performance = pd.DataFrame(rows)
    primary_recent = performance[(performance.outer_cost_bps == 50) & (performance.window == "trailing_1y")].sort_values("cagr", ascending=False)
    primary_full = performance[(performance.outer_cost_bps == 50) & (performance.window == "full_recent")][["candidate", "cagr", "sharpe", "drawdown"]].rename(columns={"cagr": "full_cagr", "sharpe": "full_sharpe", "drawdown": "full_drawdown"})
    ranking = primary_recent.merge(primary_full, on="candidate", how="left")
    ranking["recent_delta"] = ranking.cagr - float(config["control_recent_cagr"])
    ranking["full_delta"] = ranking.full_cagr - float(config["control_full_cagr"])
    ranking["beats_both"] = ranking.recent_delta.gt(0) & ranking.full_delta.gt(0)
    qualifying = ranking[ranking.beats_both]
    best = ranking.iloc[0]
    best_name = str(best.candidate)
    severe = performance[(performance.sleeve == best.sleeve) & (performance.gate == best.gate) & (performance.lookback_weeks == best.lookback_weeks) & (performance.allocation == best.allocation) & (performance.outer_cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
    checks = {"signals_shifted": int(config["signal_shift_weeks"]) >= 1, "all_allocations_bounded": bool(all(path.valuation_weight.between(0.0, 0.5).all() for path in paths.values())), "all_costs_reported": set(performance.outer_cost_bps) == set(config["outer_cost_bps"]), "all_results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all())}
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    ranking.head(100).to_csv(OUTPUT / "top_candidates.csv", index=False)
    paths[best_name].rename_axis("Date").to_csv(OUTPUT / "best_path_50bps.csv")
    result = {"experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(), "tested_paths": int(len(paths)), "best_candidate": best_name, "best_recent_50bps_cagr": float(best.cagr), "best_recent_50bps_sharpe": float(best.sharpe), "best_recent_50bps_drawdown": float(best.drawdown), "best_full_50bps_cagr": float(best.full_cagr), "recent_cagr_delta": float(best.recent_delta), "full_cagr_delta": float(best.full_delta), "best_200bps_recent_cagr": float(severe.cagr), "candidates_beating_control_recent_and_full": int(len(qualifying)), "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())), "strategy_replacement_authorized": False, "live_trading_enabled": False}
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text("# Survivorship-aware valuation overlay search v1\n\n" f"Tested {len(paths)} controlled overlay paths. Best recent candidate: `{best_name}` at {best.cagr:.2%} CAGR versus {config['control_recent_cagr']:.2%}; full CAGR {best.full_cagr:.2%} versus {config['control_full_cagr']:.2%}. " f"At 200-bps outer costs, recent CAGR was {severe.cagr:.2%}. {len(qualifying)} candidates beat the control on both horizons before exclusion and delay falsification.\n\n" "This search cannot authorize replacement. Any qualifying candidate must survive company exclusion, signal delay, and neighboring-parameter tests.\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
