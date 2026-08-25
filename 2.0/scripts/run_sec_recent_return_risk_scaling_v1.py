#!/usr/bin/env python3
"""Test frozen causal risk-scaling overlays on the endpoint-stabilized SEC path."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/sec_recent_return_risk_scaling_v1.json"
OUTPUT = ROOT / "evidence/sec_recent_return_risk_scaling_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(returns: pd.Series) -> dict[str, float | int]:
    values = returns.dropna().astype(float)
    if values.empty:
        return {"weeks": 0, "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "total_return": 0.0}
    wealth = (1.0 + values).cumprod()
    years = len(values) / 52.0
    std = float(values.std(ddof=1))
    return {
        "weeks": int(len(values)),
        "cagr": float(wealth.iloc[-1] ** (1.0 / years) - 1.0),
        "sharpe": float(values.mean() / std * math.sqrt(52.0)) if std > 0 else 0.0,
        "max_drawdown": float((wealth / wealth.cummax() - 1.0).min()),
        "total_return": float(wealth.iloc[-1] - 1.0),
    }


def desired_exposure(
    history: pd.Series,
    spec: dict,
    rules: dict,
    prior_portfolio_drawdown: float,
) -> float:
    family = str(spec["family"])
    if family == "fixed":
        return float(spec["fixed_exposure"])
    lookback = int(rules["volatility_lookback_weeks"])
    minimum = int(rules["minimum_volatility_observations"])
    usable = history.dropna().astype(float)
    if len(usable) < minimum:
        return 1.0
    realized = float(usable.tail(lookback).std(ddof=1) * math.sqrt(52.0))
    target = float(spec["target_volatility"])
    exposure = target / realized if realized > 0 else 1.0
    if "trend" in family:
        trend_window = usable.tail(int(rules["trend_lookback_weeks"]))
        trend_return = float((1.0 + trend_window).prod() - 1.0)
        if trend_return <= 0:
            exposure = min(exposure, float(rules["failed_trend_exposure_cap"]))
    if "crash_guard" in family:
        short = usable.tail(int(rules["crash_return_lookback_weeks"]))
        short_return = float((1.0 + short).prod() - 1.0)
        minimum_history = int(rules["crash_minimum_history_weeks"])
        prior_vols = usable.rolling(lookback, min_periods=minimum).std(ddof=1) * math.sqrt(52.0)
        prior_vols = prior_vols.dropna()
        if len(usable) >= minimum_history and len(prior_vols):
            high_vol = realized >= float(prior_vols.quantile(float(rules["crash_volatility_quantile"])))
            if short_return < 0 and high_vol:
                exposure = min(exposure, float(rules["crash_exposure_cap"]))
    if "drawdown" in family:
        if prior_portfolio_drawdown <= float(rules["drawdown_hard_threshold"]):
            exposure = min(exposure, float(rules["hard_drawdown_exposure_cap"]))
        elif prior_portfolio_drawdown <= float(rules["drawdown_soft_threshold"]):
            exposure = min(exposure, float(rules["soft_drawdown_exposure_cap"]))
    return float(np.clip(exposure, float(rules["minimum_exposure"]), float(rules["maximum_exposure"])))


def simulate(
    source_returns: pd.Series,
    spec: dict,
    rules: dict,
    financing_rate: float,
    outer_turnover_bps: float,
    signal_delay_weeks: int = 0,
) -> pd.DataFrame:
    source = source_returns.astype(float).copy()
    rows: list[dict] = []
    previous_exposure = 1.0
    wealth = 1.0
    peak = 1.0
    prior_drawdown = 0.0
    delay = int(rules["full_observation_delay_weeks"]) + int(signal_delay_weeks)
    for position, (date, source_return) in enumerate(source.items()):
        cutoff = max(0, position - delay + 1)
        history = source.iloc[:cutoff]
        desired = desired_exposure(history, spec, rules, prior_drawdown)
        change_limit = float(rules["maximum_weekly_exposure_change"])
        exposure = float(np.clip(desired, previous_exposure - change_limit, previous_exposure + change_limit))
        outer_turnover = abs(exposure - previous_exposure)
        financing = max(0.0, exposure - 1.0) * float(financing_rate) / 52.0
        outer_cost = outer_turnover * float(outer_turnover_bps) / 10000.0
        net_return = exposure * float(source_return) - financing - outer_cost
        wealth *= 1.0 + net_return
        peak = max(peak, wealth)
        drawdown = wealth / peak - 1.0
        rows.append({
            "Date": date,
            "source_return": float(source_return),
            "desired_exposure": desired,
            "exposure": exposure,
            "outer_turnover": outer_turnover,
            "financing_cost": financing,
            "outer_cost": outer_cost,
            "net_return": net_return,
            "wealth": wealth,
            "drawdown": drawdown,
        })
        previous_exposure = exposure
        prior_drawdown = drawdown
    return pd.DataFrame(rows).set_index("Date")


def rolling_outperformance(candidate: pd.Series, control: pd.Series, weeks: int) -> tuple[float, int]:
    joined = pd.concat([candidate.rename("candidate"), control.rename("control")], axis=1).dropna()
    compounded = (1.0 + joined).rolling(int(weeks), min_periods=int(weeks)).apply(np.prod, raw=True) - 1.0
    complete = compounded.dropna()
    return float((complete.candidate > complete.control + 1e-12).mean()), int(len(complete))


def endpoint_share(candidate: pd.Series, control: pd.Series, offsets: list[int]) -> float:
    joined = pd.concat([candidate.rename("candidate"), control.rename("control")], axis=1).dropna()
    outcomes = []
    for offset in offsets:
        finish = len(joined) - int(offset)
        frame = joined.iloc[max(0, finish - 52):finish]
        outcomes.append(metrics(frame.candidate)["cagr"] > metrics(frame.control)["cagr"])
    return float(np.mean(outcomes))


def block_summary(candidate: pd.Series, control: pd.Series, block_weeks: int) -> tuple[int, int, pd.DataFrame]:
    joined = pd.concat([candidate.rename("candidate"), control.rename("control")], axis=1).dropna()
    count = len(joined) // int(block_weeks)
    rows = []
    for number in range(count):
        finish = len(joined) - number * int(block_weeks)
        frame = joined.iloc[finish - int(block_weeks):finish]
        cm, bm = metrics(frame.candidate), metrics(frame.control)
        rows.append({"block": count - number, "start": frame.index.min(), "end": frame.index.max(),
                     "candidate_cagr": cm["cagr"], "control_cagr": bm["cagr"],
                     "candidate_positive": cm["cagr"] > 0, "candidate_beats": cm["cagr"] > bm["cagr"]})
    detail = pd.DataFrame(rows).sort_values("block")
    return int(detail.candidate_positive.sum()), int(detail.candidate_beats.sum()), detail


def block_bootstrap_probability(excess: pd.Series, block: int, draws: int, seed: int) -> float:
    values = excess.dropna().to_numpy(dtype=float)
    rng = np.random.default_rng(int(seed) + int(block))
    starts = np.arange(max(1, len(values) - int(block) + 1))
    outcomes = np.empty(int(draws), dtype=float)
    blocks_needed = int(math.ceil(len(values) / int(block)))
    for draw in range(int(draws)):
        sample = np.concatenate([values[start:start + int(block)] for start in rng.choice(starts, blocks_needed)])[:len(values)]
        outcomes[draw] = sample.mean()
    return float((outcomes > 0).mean())


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = {
        int(cost): pd.read_csv(ROOT / path, parse_dates=["Date"]).set_index("Date").net_return
        for cost, path in config["source_paths"].items()
    }
    rules, costs, evaluation, gates = config["signal_rules"], config["costs"], config["evaluation"], config["gates"]
    specs = {str(spec["name"]): spec for spec in config["candidate_specs"]}
    paths = {
        name: simulate(sources[50], spec, rules, costs["base_financing_rate_annual"], costs["base_outer_turnover_bps"])
        for name, spec in specs.items()
    }
    stress_paths = {
        name: simulate(sources[200], spec, rules, costs["stress_financing_rate_annual"], costs["stress_outer_turnover_bps"])
        for name, spec in specs.items()
    }
    control = paths["unscaled_control"]
    exact_control = np.allclose(control.net_return, sources[50].reindex(control.index), rtol=0, atol=1e-15)
    if not exact_control:
        raise RuntimeError("unscaled control does not reproduce source returns")
    rows, blocks = [], []
    challenger_count = int(config["multiple_testing"]["challenger_count"])
    for name, spec in specs.items():
        path, stress = paths[name], stress_paths[name]
        recent = metrics(path.net_return.iloc[-int(evaluation["recent_weeks"]):])
        full = metrics(path.net_return)
        stress_recent = metrics(stress.net_return.iloc[-int(evaluation["recent_weeks"]):])
        rolling26, windows26 = rolling_outperformance(path.net_return, control.net_return, 26)
        positive_blocks, beating_blocks, detail = block_summary(
            path.net_return, control.net_return, int(evaluation["nonoverlapping_blocks_weeks"])
        )
        detail.insert(0, "candidate", name)
        blocks.append(detail)
        recent_excess = path.net_return.iloc[-52:] - control.net_return.reindex(path.index).iloc[-52:]
        raw_probabilities = [block_bootstrap_probability(
            recent_excess, int(block), int(evaluation["bootstrap_draws"]), int(evaluation["bootstrap_seed"])
        ) for block in evaluation["bootstrap_blocks_weeks"]]
        minimum_raw = min(raw_probabilities)
        adjusted_probability = 1.0 if name == "unscaled_control" else max(
            0.0, 1.0 - min(1.0, (1.0 - minimum_raw) * challenger_count)
        )
        delay_metrics = []
        if spec["family"] != "fixed":
            for delay in [1, 2]:
                delayed = simulate(sources[50], spec, rules, costs["base_financing_rate_annual"],
                                   costs["base_outer_turnover_bps"], signal_delay_weeks=delay)
                delay_metrics.append(metrics(delayed.net_return.iloc[-52:])["cagr"])
        else:
            delay_metrics.append(recent["cagr"])
        row = {
            "candidate": name,
            "family": spec["family"],
            "recent_cagr": recent["cagr"],
            "recent_sharpe": recent["sharpe"],
            "recent_drawdown": recent["max_drawdown"],
            "full_cagr": full["cagr"],
            "stress_recent_cagr": stress_recent["cagr"],
            "endpoint_outperformance_share": endpoint_share(path.net_return, control.net_return, evaluation["endpoint_offsets_weeks"]),
            "rolling26_outperformance_share": rolling26,
            "rolling26_windows": windows26,
            "positive_nonoverlapping_blocks": positive_blocks,
            "beating_nonoverlapping_blocks": beating_blocks,
            "minimum_delay_recent_cagr": min(delay_metrics),
            "minimum_raw_bootstrap_probability": minimum_raw,
            "bonferroni_adjusted_probability": adjusted_probability,
            "average_exposure": float(path.exposure.mean()),
            "maximum_exposure": float(path.exposure.max()),
            "annual_outer_turnover": float(path.outer_turnover.mean() * 52.0),
        }
        row["all_candidate_gates"] = bool(
            name != "unscaled_control"
            and row["recent_cagr"] >= float(gates["minimum_recent_cagr"])
            and row["recent_sharpe"] >= float(gates["minimum_recent_sharpe"])
            and row["recent_drawdown"] >= float(gates["minimum_recent_drawdown"])
            and row["full_cagr"] >= float(gates["minimum_full_cagr"])
            and row["stress_recent_cagr"] >= float(gates["minimum_stress_recent_cagr"])
            and row["endpoint_outperformance_share"] >= float(gates["minimum_endpoint_outperformance_share"])
            and row["rolling26_outperformance_share"] >= float(gates["minimum_rolling_26w_outperformance_share"])
            and row["positive_nonoverlapping_blocks"] >= int(gates["minimum_positive_nonoverlapping_blocks"])
            and row["beating_nonoverlapping_blocks"] >= int(gates["minimum_beating_nonoverlapping_blocks"])
            and row["bonferroni_adjusted_probability"] >= float(gates["minimum_bootstrap_probability"])
        )
        rows.append(row)
    screen = pd.DataFrame(rows)
    passers = screen[screen.all_candidate_gates]
    if len(passers):
        selected_row = passers.sort_values(["recent_cagr", "recent_sharpe"], ascending=False).iloc[0]
        selection_reason = "all predeclared return, risk, temporal, stress, and multiple-testing gates"
    else:
        eligible = screen[screen.candidate != "unscaled_control"]
        selected_row = eligible.sort_values(["recent_cagr", "recent_sharpe"], ascending=False).iloc[0]
        selection_reason = "no candidate passed all gates; highest-return diagnostic only"
    selected = str(selected_row.candidate)
    screen.sort_values(["all_candidate_gates", "recent_cagr", "recent_sharpe"], ascending=False).to_csv(OUTPUT / "screening.csv", index=False)
    pd.concat(blocks, ignore_index=True).to_csv(OUTPUT / "nonoverlapping_blocks.csv", index=False)
    for name, path in paths.items():
        path.rename_axis("Date").to_csv(OUTPUT / f"path__{name}__base.csv")
    stress_paths[selected].rename_axis("Date").to_csv(OUTPUT / f"path__{selected}__stress.csv")
    underlying_passed = bool(config["underlying_strategy_falsification_passed"])
    complete_pass = bool(selected_row.all_candidate_gates) and underlying_passed
    result = {
        "experiment": config["experiment"],
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "frozen_config_sha256": sha256(CONFIG),
        "candidate_count": int(len(screen)),
        "challenger_count": challenger_count,
        "selected_candidate": selected,
        "selection_reason": selection_reason,
        "selected_metrics": {key: (bool(value) if isinstance(value, (bool, np.bool_)) else float(value) if isinstance(value, (float, np.floating)) else int(value) if isinstance(value, (int, np.integer)) else value)
                             for key, value in selected_row.to_dict().items()},
        "candidate_level_gates_passed": bool(selected_row.all_candidate_gates),
        "underlying_strategy_falsification_passed": underlying_passed,
        "complete_falsification_passed": complete_pass,
        "control_exact_reproduction": bool(exact_control),
        "strategy_replacement_authorized": False,
        "live_trading_enabled": False,
        "artifact_sha256": {
            "screening": sha256(OUTPUT / "screening.csv"),
            "selected_path": sha256(OUTPUT / f"path__{selected}__base.csv"),
            "blocks": sha256(OUTPUT / "nonoverlapping_blocks.csv")
        }
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (OUTPUT / "report.md").write_text(
        "# Recent-return risk scaling v1\n\n"
        f"The frozen test evaluated {len(screen)} bounded causal exposure rules. `{selected}` produced "
        f"{selected_row.recent_cagr:.2%} trailing-year CAGR, {selected_row.recent_sharpe:.3f} Sharpe, "
        f"and {selected_row.recent_drawdown:.2%} maximum drawdown. Its full-period CAGR was "
        f"{selected_row.full_cagr:.2%}; the severe-cost/financing recent CAGR was {selected_row.stress_recent_cagr:.2%}.\n\n"
        f"Candidate-level gates: **{'PASS' if bool(selected_row.all_candidate_gates) else 'FAIL'}**. "
        f"Complete falsification including the underlying strategy: **{'PASS' if complete_pass else 'FAIL'}**. "
        "The experiment is research-only; it does not authorize promotion or live trading.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
