#!/usr/bin/env python3
"""Test the normalized valuation pilot only as a controlled sleeve."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_split_normalized_valuation_overlay_v1.json"
CONTROL = ROOT / "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv"
SLEEVE = ROOT / "evidence/sec_split_normalized_valuation_pilot_v1/best_factor_path_50bps.csv"
OUTPUT = ROOT / "evidence/sec_split_normalized_valuation_overlay_v1"


def metrics(returns: pd.Series) -> dict[str, float]:
    years = len(returns) / 52.0
    curve = (1.0 + returns).cumprod()
    volatility = returns.std(ddof=1)
    return {
        "cagr": float(curve.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(returns.mean() / volatility * np.sqrt(52)) if volatility else 0.0,
        "drawdown": float((curve / curve.cummax() - 1.0).min()),
        "total_return": float(curve.iloc[-1] - 1.0),
    }


def path_for(control: pd.Series, sleeve: pd.Series, target: pd.Series, cost_bps: float) -> pd.DataFrame:
    target = target.reindex(control.index).fillna(0.0).clip(0.0, 1.0)
    turnover = target.diff().abs().fillna(target.abs())
    gross = (1.0 - target) * control + target * sleeve
    cost = turnover * cost_bps / 10000.0
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    return pd.DataFrame({"control_weight": 1.0 - target, "valuation_weight": target, "gross_return": gross, "turnover": turnover, "cost": cost, "net_return": net, "wealth": wealth, "drawdown": wealth / wealth.cummax() - 1.0})


def main() -> int:
    config = json.loads(CONFIG.read_text())
    control_frame = pd.read_csv(CONTROL, parse_dates=["Date"]).set_index("Date").sort_index()
    sleeve_frame = pd.read_csv(SLEEVE, parse_dates=["Date"]).set_index("Date").sort_index()
    joined = pd.concat([control_frame.net_return.rename("control"), sleeve_frame.net_return.rename("sleeve")], axis=1, join="inner").dropna()
    joined = joined.loc[control_frame.index.min():control_frame.index.max()]

    candidates: dict[str, pd.DataFrame] = {}
    rows = []
    control_metrics = {}
    windows = {
        "full_recent": joined.index >= joined.index.min(),
        "trailing_2y": joined.index >= joined.index.max() - pd.DateOffset(years=2),
        "trailing_1y": joined.index >= joined.index.max() - pd.DateOffset(years=1),
        "ytd": joined.index.year == joined.index.max().year,
    }
    for window, mask in windows.items():
        control_metrics[window] = metrics(joined.loc[mask, "control"])

    for lookback in config["lookbacks_weeks"]:
        control_prior = (1.0 + joined.control).rolling(int(lookback)).apply(np.prod, raw=True).sub(1.0).shift(int(config["signal_shift_weeks"]))
        sleeve_prior = (1.0 + joined.sleeve).rolling(int(lookback)).apply(np.prod, raw=True).sub(1.0).shift(int(config["signal_shift_weeks"]))
        for gate in config["gates"]:
            for allocation in config["allocations"]:
                if gate == "static":
                    target = pd.Series(float(allocation), index=joined.index)
                elif gate == "relative":
                    target = (sleeve_prior > control_prior).astype(float) * float(allocation)
                elif gate == "relative_and_positive":
                    target = ((sleeve_prior > control_prior) & (sleeve_prior > 0.0)).astype(float) * float(allocation)
                else:
                    target = ((control_prior < 0.0) & (sleeve_prior > control_prior)).astype(float) * float(allocation)
                for cost_bps in config["outer_cost_bps"]:
                    name = f"{gate}__lb{lookback}__w{allocation:.1f}__{cost_bps}bps"
                    path = path_for(joined.control, joined.sleeve, target, float(cost_bps))
                    candidates[name] = path
                    for window, mask in windows.items():
                        result = metrics(path.loc[mask, "net_return"])
                        rows.append({"candidate": name, "gate": gate, "lookback_weeks": lookback, "allocation": allocation, "outer_cost_bps": cost_bps, "window": window, **result, "control_cagr": control_metrics[window]["cagr"], "cagr_delta": result["cagr"] - control_metrics[window]["cagr"]})
    performance = pd.DataFrame(rows)
    primary = performance[(performance.outer_cost_bps == 50) & (performance.window == "trailing_1y")].sort_values("cagr", ascending=False)
    best_name = str(primary.iloc[0].candidate)
    best_recent = primary.iloc[0]
    best_full = performance[(performance.candidate == best_name) & (performance.window == "full_recent")].iloc[0]
    control_recent = control_metrics["trailing_1y"]
    control_full = control_metrics["full_recent"]
    beats_both = bool(best_recent.cagr > control_recent["cagr"] and best_full.cagr > control_full["cagr"])
    checks = {
        "signal_shifted_before_application": int(config["signal_shift_weeks"]) >= 1,
        "weights_bounded": bool(all(frame.valuation_weight.between(0.0, 0.5).all() for frame in candidates.values())),
        "all_results_finite": bool(np.isfinite(performance.select_dtypes("number").to_numpy()).all()),
        "cost_stress_included": set(config["outer_cost_bps"]) == {0, 50, 100, 200},
        "control_recomputed_from_frozen_path": True,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    performance.to_csv(OUTPUT / "performance.csv", index=False)
    candidates[best_name].rename_axis("Date").to_csv(OUTPUT / "best_candidate_path.csv")
    primary.head(30).to_csv(OUTPUT / "top_recent_candidates.csv", index=False)
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "tested_paths": int(len(candidates)), "best_candidate": best_name,
        "best_trailing_1y_50bps_cagr": float(best_recent.cagr), "best_trailing_1y_50bps_sharpe": float(best_recent.sharpe), "best_trailing_1y_50bps_drawdown": float(best_recent.drawdown),
        "control_trailing_1y_cagr": float(control_recent["cagr"]), "recent_cagr_delta": float(best_recent.cagr - control_recent["cagr"]),
        "best_full_50bps_cagr": float(best_full.cagr), "control_full_cagr": float(control_full["cagr"]), "full_cagr_delta": float(best_full.cagr - control_full["cagr"]),
        "best_candidate_beats_control_full_and_recent": beats_both,
        "decision": "retain_for_survivorship_safe_retest" if beats_both else "do_not_add_to_current_leader",
        "validation_checks": checks, "all_validation_checks_passed": bool(all(checks.values())),
        "survivor_pilot_warning": True, "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Split-normalized valuation overlay v1\n\n"
        f"Tested {len(candidates)} controlled valuation-sleeve paths. Best 50-bps recent candidate: `{best_name}` at {best_recent.cagr:.2%} versus {control_recent['cagr']:.2%} for the frozen control. "
        f"Full CAGR was {best_full.cagr:.2%} versus {control_full['cagr']:.2%}. Decision: `{result['decision']}`.\n\n"
        "Signals are shifted one week before application. The valuation sleeve remains a current-survivor pilot and cannot be promoted without a broader survivorship-aware retest.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["all_validation_checks_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
