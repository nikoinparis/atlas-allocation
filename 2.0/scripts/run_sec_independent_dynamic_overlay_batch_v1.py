#!/usr/bin/env python3
"""Large causal batch of conditional independent-factor overlays."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base

CONFIG = Path(os.environ.get("DYNAMIC_OVERLAY_CONFIG", ROOT / "config/sec_independent_dynamic_overlay_batch_v1.json"))
FACTORS = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
OUTPUT = Path(os.environ.get("DYNAMIC_OVERLAY_OUTPUT", ROOT / "evidence/sec_independent_dynamic_overlay_batch_v1"))


def read_path(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    date_column = "Date" if "Date" in frame else frame.columns[0]
    frame[date_column] = pd.to_datetime(frame[date_column])
    return frame.set_index(date_column).sort_index()


def rolling_total(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return (1 + returns.shift(1)).rolling(lookback, min_periods=lookback).apply(np.prod, raw=True) - 1


def rolling_sharpe(returns: pd.DataFrame, lookback: int) -> pd.DataFrame:
    shifted = returns.shift(1)
    return shifted.rolling(lookback, min_periods=lookback).mean() / shifted.rolling(lookback, min_periods=lookback).std(ddof=1) * np.sqrt(52)


def make_targets(signal_returns: pd.DataFrame, config: dict) -> dict[str, pd.DataFrame]:
    targets = {}
    assets = ["leader"] + config["families"]
    for lookback in config["cash_conversion_lookbacks"]:
        trend = rolling_total(signal_returns, int(lookback))
        gate = (trend.cash_conversion > trend.leader) & (trend.cash_conversion > 0)
        for low, high in config["cash_conversion_weight_pairs"]:
            name = f"cash_rel_{lookback}w_{int(low*100):02d}_{int(high*100):02d}"
            weight = pd.Series(np.where(gate, high, low), index=trend.index).where(trend.leader.notna(), 0.0)
            target = pd.DataFrame(0.0, index=trend.index, columns=assets)
            target["cash_conversion"], target["leader"] = weight, 1 - weight
            targets[name] = target
    for lookback in config["rotation_lookbacks"]:
        trend = rolling_total(signal_returns, int(lookback))
        factor_trend = trend[config["families"]]
        winner = factor_trend.fillna(-np.inf).idxmax(axis=1)
        best = factor_trend.max(axis=1)
        for high in config["rotation_high_weights"]:
            name = f"rotate_return_{lookback}w_{int(high*100):02d}"
            active = (best > trend.leader) & (best > 0) & trend.leader.notna()
            target = pd.DataFrame(0.0, index=trend.index, columns=assets)
            target["leader"] = 1.0
            for date in target.index[active]:
                target.at[date, "leader"] = 1 - high
                target.at[date, winner.at[date]] = high
            targets[name] = target
        sharpe = rolling_sharpe(signal_returns, int(lookback))
        factor_sharpe = sharpe[config["families"]]
        winner_s = factor_sharpe.fillna(-np.inf).idxmax(axis=1)
        best_s = factor_sharpe.max(axis=1)
        for high in config["rotation_high_weights"]:
            name = f"rotate_sharpe_{lookback}w_{int(high*100):02d}"
            active = (best_s > sharpe.leader) & (best > 0) & sharpe.leader.notna()
            target = pd.DataFrame(0.0, index=trend.index, columns=assets)
            target["leader"] = 1.0
            for date in target.index[active]:
                target.at[date, "leader"] = 1 - high
                target.at[date, winner_s.at[date]] = high
            targets[name] = target
    for lookback in config["top_two_lookbacks"]:
        trend = rolling_total(signal_returns, int(lookback))
        factor_trend = trend[config["families"]]
        ranks = factor_trend.rank(axis=1, ascending=False, method="first")
        top_two_average = factor_trend.where(ranks <= 2).mean(axis=1)
        for high in config["top_two_high_weights"]:
            name = f"top2_return_{lookback}w_{int(high*100):02d}"
            active = (top_two_average > trend.leader) & (top_two_average > 0) & trend.leader.notna()
            target = pd.DataFrame(0.0, index=trend.index, columns=assets)
            target["leader"] = 1.0
            for date in target.index[active]:
                selected = list(ranks.columns[ranks.loc[date] <= 2])
                target.at[date, "leader"] = 1 - high
                target.loc[date, selected] = high / len(selected)
            targets[name] = target
    return targets


def simulate(returns: pd.DataFrame, targets: pd.DataFrame, cost_bps: float) -> pd.DataFrame:
    assets = list(returns.columns)
    values = pd.Series(0.0, index=assets)
    values["leader"] = 1.0
    rows = []
    for date, asset_returns in returns.iterrows():
        before = float(values.sum())
        current = values / before if before else pd.Series(0.0, index=assets)
        target = targets.loc[date].reindex(assets).fillna(0.0)
        turnover = float(0.5 * (target - current).abs().sum())
        cost = before * turnover * float(cost_bps) / 10000.0
        deployable = before - cost
        values = deployable * target
        values *= 1 + asset_returns.fillna(0.0)
        after = float(values.sum())
        rows.append({"Date": date, "gross_return": after / before - 1 + (cost / before if before else 0), "net_return": after / before - 1 if before else 0, "turnover": turnover, "cost": cost / before if before else 0, "wealth": after})
    path = pd.DataFrame(rows).set_index("Date")
    path["drawdown"] = path.wealth / path.wealth.cummax() - 1
    return path


def aligned_returns(config: dict, scenario: str, cost: int) -> pd.DataFrame:
    paths = {"leader": read_path(LEADER / f"path__{scenario}__{config['frozen_control']}__{cost}bps.csv").net_return}
    for family in config["families"]:
        paths[family] = read_path(FACTORS / f"path_{family}__{scenario}__{cost}bps.csv").net_return
    return pd.DataFrame(paths).dropna()


def block_bootstrap(diff: pd.Series, block: int, draws: int, seed: int) -> dict:
    values = diff.dropna().to_numpy()
    rng = np.random.default_rng(seed + block)
    estimates = []
    blocks_needed = int(np.ceil(len(values) / block))
    for _ in range(draws):
        starts = rng.integers(0, len(values), size=blocks_needed)
        sample = np.concatenate([np.take(values, (np.arange(start, start + block) % len(values))) for start in starts])[:len(values)]
        estimates.append(float(sample.mean() * 52))
    return {"block_weeks": block, "annualized_mean_difference": float(values.mean() * 52), "lower_5pct": float(np.quantile(estimates, 0.05)), "median": float(np.quantile(estimates, 0.5)), "upper_95pct": float(np.quantile(estimates, 0.95)), "probability_positive": float(np.mean(np.asarray(estimates) > 0))}


def main() -> int:
    config = json.loads(CONFIG.read_text())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    signal_returns = aligned_returns(config, "base", 50)
    targets = make_targets(signal_returns, config)
    control_targets = pd.DataFrame(0.0, index=signal_returns.index, columns=signal_returns.columns)
    control_targets["leader"] = 1.0
    targets = {"control": control_targets, **targets}

    performance_rows, paths = [], {}
    for scenario in config["scenarios"]:
        for cost in config["cost_bps"]:
            returns = aligned_returns(config, scenario, int(cost)).reindex(signal_returns.index).dropna()
            for name, target in targets.items():
                path = simulate(returns, target.reindex(returns.index), float(cost))
                paths[(name, scenario, int(cost))] = path
                performance_rows.extend(base.metric_rows(name, scenario, int(cost), path))
    performance = pd.DataFrame(performance_rows)
    primary = performance[(performance.scenario == "base") & (performance.cost_bps == 50)]
    focus = primary[primary.window.isin(["full_recent", "trailing_2y", "trailing_1y", "ytd"])].copy()
    control = focus[focus.candidate == "control"].set_index("window")
    focus["cagr_delta"] = [row.cagr - control.loc[row.window, "cagr"] for row in focus.itertuples()]
    focus["sharpe_delta"] = [row.sharpe_zero_rf - control.loc[row.window, "sharpe_zero_rf"] for row in focus.itertuples()]
    focus["drawdown_delta"] = [row.max_drawdown - control.loc[row.window, "max_drawdown"] for row in focus.itertuples()]

    gates = config["promotion_gates"]
    rows = []
    severe = performance[(performance.scenario == "base") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].set_index("candidate")
    for candidate in targets:
        recent = focus[(focus.candidate == candidate) & (focus.window == "trailing_1y")].iloc[0]
        ytd = focus[(focus.candidate == candidate) & (focus.window == "ytd")].iloc[0]
        full = focus[(focus.candidate == candidate) & (focus.window == "full_recent")].iloc[0]
        recent_control, full_control = control.loc["trailing_1y"], control.loc["full_recent"]
        checks = {
            "recent_return": recent.cagr >= recent_control.cagr + gates["minimum_trailing_1y_cagr_improvement"],
            "ytd_return": ytd.cagr >= control.loc["ytd", "cagr"] + gates["minimum_ytd_cagr_improvement"],
            "recent_sharpe": recent.sharpe_zero_rf >= recent_control.sharpe_zero_rf * gates["minimum_recent_sharpe_ratio_to_control"],
            "recent_drawdown": abs(recent.max_drawdown) <= abs(recent_control.max_drawdown) * gates["maximum_recent_drawdown_ratio_to_control"],
            "full_return_gate": full.cagr >= full_control.cagr - gates["maximum_full_cagr_sacrifice"],
            "full_drawdown_gate": abs(full.max_drawdown) <= abs(full_control.max_drawdown) * gates["maximum_full_drawdown_ratio_to_control"],
            "severe_cost": severe.loc[candidate, "cagr"] > severe.loc["control", "cagr"] if candidate != "control" else True,
        }
        rows.append({"candidate": candidate, "trailing_1y_cagr": recent.cagr, "trailing_1y_sharpe": recent.sharpe_zero_rf, "trailing_1y_drawdown": recent.max_drawdown, "ytd_cagr": ytd.cagr, "full_cagr": full.cagr, "full_drawdown": full.max_drawdown, "trailing_1y_200bps_cagr": severe.loc[candidate, "cagr"], **checks, "all_screen_gates": all(checks.values()) if candidate != "control" else False})
    screen = pd.DataFrame(rows).sort_values("trailing_1y_cagr", ascending=False)
    eligible = screen[screen.all_screen_gates]
    selected = str((eligible if len(eligible) else screen[screen.candidate != "control"]).iloc[0].candidate)

    selected_target = targets[selected]
    delay_rows = []
    base_returns = aligned_returns(config, "base", 50).reindex(signal_returns.index).dropna()
    for delay in [0] + config["falsification"]["signal_delays_weeks"]:
        delayed = selected_target.shift(int(delay)).fillna(0.0)
        delayed["leader"] = 1 - delayed.drop(columns=["leader"]).sum(axis=1)
        path = simulate(base_returns, delayed.reindex(base_returns.index), 50.0)
        for row in base.metric_rows(selected, f"delay_{delay}", 50, path):
            if row["window"] in {"full_recent", "trailing_1y", "ytd"}:
                delay_rows.append(row)
    delays = pd.DataFrame(delay_rows)

    selected_path = paths[(selected, "base", 50)]
    control_path = paths[("control", "base", 50)]
    joined = pd.concat([selected_path.net_return.rename("candidate"), control_path.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    bootstrap = pd.DataFrame([block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(config["falsification"]["bootstrap_draws"]), int(config["falsification"]["bootstrap_seed"])) for block in config["falsification"]["bootstrap_blocks_weeks"]])
    roll = (1 + joined).rolling(int(config["falsification"]["rolling_comparison_weeks"])).apply(np.prod, raw=True) - 1
    rolling_share = float((roll.candidate > roll.control).dropna().mean())

    route = selected.split("_")[0]
    neighborhood = screen[screen.candidate.str.startswith(route) & (screen.candidate != "control")].copy()
    control_recent = screen.loc[screen.candidate == "control", "trailing_1y_cagr"].iloc[0]
    control_full = screen.loc[screen.candidate == "control", "full_cagr"].iloc[0]
    neighborhood["joint_improvement"] = (neighborhood.trailing_1y_cagr > control_recent) & (neighborhood.full_cagr > control_full)
    neighborhood_share = float(neighborhood.joint_improvement.mean()) if len(neighborhood) else 0.0
    selected_screen = screen[screen.candidate == selected].iloc[0]
    delay_one = delays[(delays.scenario == "delay_1") & (delays.window == "trailing_1y")].iloc[0]
    falsification = {
        "screen_gates_passed": bool(selected_screen.all_screen_gates),
        "one_week_delay_beats_control_recent": bool(delay_one.cagr > control_recent),
        "rolling_26w_outperformance_share": rolling_share,
        "neighborhood_joint_improvement_share": neighborhood_share,
        "neighborhood_gate_passed": neighborhood_share >= config["falsification"]["minimum_neighborhood_joint_improvement_share"],
        "bootstrap_4w_lower_bound_positive": bool(bootstrap.loc[bootstrap.block_weeks == 4, "lower_5pct"].iloc[0] > 0),
        "bootstrap_13w_lower_bound_positive": bool(bootstrap.loc[bootstrap.block_weeks == 13, "lower_5pct"].iloc[0] > 0),
    }
    falsification["all_passed"] = bool(all(falsification.values()))

    performance.to_csv(OUTPUT / "performance.csv", index=False)
    focus.to_csv(OUTPUT / "primary_comparison.csv", index=False)
    screen.to_csv(OUTPUT / "screening_gates.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    neighborhood.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    selected_target.rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    for cost in config["cost_bps"]:
        for scenario in config["scenarios"]:
            paths[(selected, scenario, int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{scenario}__{cost}bps.csv")
    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(targets) - 1, "selected_candidate": selected,
        "selected_trailing_1y_cagr": float(selected_screen.trailing_1y_cagr), "control_trailing_1y_cagr": float(control_recent),
        "selected_trailing_1y_sharpe": float(selected_screen.trailing_1y_sharpe), "selected_trailing_1y_drawdown": float(selected_screen.trailing_1y_drawdown),
        "selected_ytd_cagr": float(selected_screen.ytd_cagr), "selected_full_cagr": float(selected_screen.full_cagr),
        "selected_200bps_trailing_1y_cagr": float(selected_screen.trailing_1y_200bps_cagr),
        "qualified_screen_candidates": int(screen.all_screen_gates.sum()), "falsification": falsification,
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    decision = "passes the full falsification gauntlet" if falsification["all_passed"] else "does not pass the full falsification gauntlet"
    (OUTPUT / "report.md").write_text(
        "# Independent dynamic overlay batch v1\n\n"
        f"Tested **{len(targets)-1}** causal conditional overlays. The strongest screened candidate was `{selected}` with **{selected_screen.trailing_1y_cagr:.2%}** trailing-one-year CAGR, **{selected_screen.trailing_1y_sharpe:.3f}** Sharpe, and **{selected_screen.trailing_1y_drawdown:.2%}** drawdown versus **{control_recent:.2%}** for the control. It {decision}.\n\n"
        f"At 200 bps its trailing-one-year CAGR was **{selected_screen.trailing_1y_200bps_cagr:.2%}**. The parameter neighborhood jointly improved recent and full CAGR in **{neighborhood_share:.1%}** of related configurations, and rolling 26-week outperformance occurred **{rolling_share:.1%}** of the time. No strategy is promoted automatically.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
