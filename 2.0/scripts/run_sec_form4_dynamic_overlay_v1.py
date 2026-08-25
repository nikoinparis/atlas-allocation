#!/usr/bin/env python3
"""Test a causal conditional overlay of the Form 4 insider sleeve on the frozen breadth-20 leader.

Step 125 tested the Form 4 insider-purchase signal only as a fixed-weight static
blend against the frozen breadth-20 cash-conversion leader and found no static
allocation beat the control on both recent and full CAGR. This mirrors the
earlier cash-conversion result: a static blend (Step 114) also failed, and only
a causal relative-trend gate turned it into a genuine overlay (Step 115). This
script applies the same conditional-gate pattern to the Form 4 sleeve instead of
re-running the 480-structure Form 4 search.
"""

from __future__ import annotations

import json
import hashlib
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_sec_growth_survivorship_retest_v1 as base
import run_sec_independent_dynamic_overlay_batch_v1 as dynamic
import run_sec_cash_conversion_capped_dynamic_v1 as capped
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner
import run_sec_form4_insider_cluster_search_v1 as insider

CONFIG = ROOT / "config/sec_form4_dynamic_overlay_v1.json"
DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
LEADER = ROOT / "evidence/sec_growth_confidence_universal_cap_v1"
OUTPUT = ROOT / "evidence/sec_form4_dynamic_overlay_v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_runtime(config: dict) -> dict:
    expected = config["pinned_runtime"]
    actual = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
    }
    matches = {key: actual[key] == expected[key] for key in actual}
    if not all(matches.values()):
        raise RuntimeError(f"runtime mismatch: expected {expected}, observed {actual}")
    return {"expected": expected, "actual": actual, "versions_match": matches, "all_versions_match": True}


def completed_rolling_outperformance(joined: pd.DataFrame, weeks: int) -> tuple[float, int]:
    rolling = (1 + joined).rolling(int(weeks), min_periods=int(weeks)).apply(np.prod, raw=True) - 1
    complete = rolling.dropna(subset=["candidate", "control"])
    share = float((complete.candidate > complete.control).mean()) if len(complete) else 0.0
    return share, int(len(complete))


def required_gates_pass(values: dict, required_keys: list[str]) -> bool:
    return bool(all(values.get(key) is True for key in required_keys))


def cash_conversion_inputs():
    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = breadth_runner.make_choices(scores[scores.family == "cash_conversion"], 20)
    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    cash_targets = base.build_targets(choices, index)
    sources, terminals = base.price_sources(), base.terminal_dates()
    series = {}
    for cik in sorted(set(choices.cik10)):
        if cik in sources:
            source, path = sources[cik]
            series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
    weekly_cash = pd.DataFrame(series, index=index)
    return index, weekly_cash, cash_targets


def build_control(index: pd.DatetimeIndex, weekly_cash: pd.DataFrame, cash_targets: dict, cost: float, delay: int = 0) -> pd.DataFrame:
    leader = dynamic.read_path(LEADER / f"path__base__confidence_10_40__cap_1.50x__{int(cost)}bps.csv").net_return
    cash_path, _peak = capped.simulate_cash(weekly_cash, cash_targets, "base", float(cost), None, 20)
    returns = pd.concat([leader.rename("leader"), cash_path.net_return.rename("cash_conversion")], axis=1).dropna()
    target = capped.overlay_target(returns.index, returns.leader, returns.cash_conversion, 11, 0.5, delay)
    return dynamic.simulate(returns, target, float(cost))


def overlay_target(index: pd.DatetimeIndex, leader: pd.Series, sleeve: pd.Series, lookback: int, high: float, delay: int = 0) -> pd.DataFrame:
    signal = pd.DataFrame({"leader": leader, "sleeve": sleeve}).reindex(index)
    trend = dynamic.rolling_total(signal, lookback)
    active = ((trend.sleeve > trend.leader) & (trend.sleeve > 0)).shift(delay).fillna(False)
    target = pd.DataFrame(0.0, index=index, columns=["leader", "sleeve"])
    target.sleeve = np.where(active, high, 0.0)
    target.leader = 1 - target.sleeve
    return target


def form4_family_targets(events: pd.DataFrame, weekly: pd.DataFrame, dates: pd.DatetimeIndex, config: dict, family: str) -> dict[pd.Timestamp, list[str]]:
    small = {
        "event_windows_days": [config["event_window_days"]],
        "price_confirmation": [config["price_confirmation"]],
        "families": ["all_open_market", "cluster_2plus", "executive_or_cluster", "discretionary", "discretionary_cluster_2plus"],
    }
    panels = insider.build_panels(events, weekly, dates, small)
    panel = panels[(config["event_window_days"], family, config["price_confirmation"])]
    by_date = {date: frame for date, frame in panel.groupby("decision_at", sort=False)}
    floor, sector_cap, breadth = config["market_cap_floor"], config["sector_cap"], config["breadth"]
    targets = {}
    for date in dates[:-1]:
        frame = by_date.get(date)
        if frame is None:
            targets[date] = []
            continue
        frame = frame[pd.to_numeric(frame.market_cap, errors="coerce") >= float(floor)].sort_values(["score", "cik10"], ascending=[False, True])
        targets[date] = insider.fast_select_ciks(frame, int(breadth), float(sector_cap))
    return targets


def main() -> int:
    config = json.loads(CONFIG.read_text())
    runtime = verify_runtime(config)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    control_50 = pd.read_csv(config["control_path_50bps"], parse_dates=["Date"]).set_index("Date")
    index, weekly_cash, cash_targets = cash_conversion_inputs()
    control_paths = {50: control_50}
    for cost in config["cost_bps"]:
        if int(cost) == 50:
            continue
        control_paths[int(cost)] = build_control(index, weekly_cash, cash_targets, float(cost))

    events = insider.load_events()
    print(f"loaded {len(events):,} eligible Form 4 open-market purchase filings across {events.cik10.nunique()} issuers", flush=True)
    sources = {}
    import run_sec_survivorship_valuation_discovery_v1 as discovery
    price_sources = discovery.source_map()
    terminals = base.terminal_dates()
    dates = pd.date_range(pd.Timestamp(config["start_date"]), control_50.index.max() + pd.offsets.Week(weekday=4), freq="W-FRI")
    price_series = {}
    for cik in sorted(set(events.cik10)):
        spec = price_sources.get(cik)
        if spec:
            try:
                price_series[cik] = base.read_weekly_price(spec[1], spec[0], dates, terminals.get(cik))
            except OSError:
                price_series[cik] = pd.Series(np.nan, index=dates)
    weekly_form4 = pd.DataFrame(price_series, index=dates)
    print(f"loaded weekly prices for {weekly_form4.shape[1]} Form 4 issuers", flush=True)

    family_targets = {family: form4_family_targets(events, weekly_form4, dates, config, family) for family in config["predeclared_families"]}
    family_paths = {
        (family, int(cost)): insider.simulate_weekly(weekly_form4, family_targets[family], float(cost))
        for family in config["predeclared_families"] for cost in config["cost_bps"]
    }
    print("built Form 4 family sleeves", flush=True)

    performance_rows, paths, targets_by_name = [], {}, {}
    for family in config["predeclared_families"]:
        for lookback in config["lookbacks_weeks"]:
            for low, high in config["weight_pairs"]:
                name = f"{family}__{lookback}w__{int(high * 100):02d}"
                base_returns = pd.concat(
                    [control_paths[50].net_return.rename("leader"), family_paths[(family, 50)].net_return.rename("sleeve")], axis=1
                ).dropna()
                target = overlay_target(base_returns.index, base_returns.leader, base_returns.sleeve, int(lookback), float(high))
                targets_by_name[name] = target
                for cost in config["cost_bps"]:
                    returns = pd.concat(
                        [control_paths[int(cost)].net_return.rename("leader"), family_paths[(family, int(cost))].net_return.rename("sleeve")], axis=1
                    ).dropna()
                    path = dynamic.simulate(returns, target.reindex(returns.index), float(cost))
                    paths[(name, int(cost))] = path
                    performance_rows.extend(base.metric_rows(name, "base", int(cost), path))
    control_only = {int(cost): control_paths[int(cost)] for cost in config["cost_bps"]}
    for cost, path in control_only.items():
        performance_rows.extend(base.metric_rows("control", "base", cost, path))
    performance = pd.DataFrame(performance_rows)

    control_recent = performance[(performance.candidate == "control") & (performance.cost_bps == 50) & (performance.window == "trailing_1y")].iloc[0]
    control_full = performance[(performance.candidate == "control") & (performance.cost_bps == 50) & (performance.window == "full_recent")].iloc[0]
    control_ytd = performance[(performance.candidate == "control") & (performance.cost_bps == 50) & (performance.window == "ytd")].iloc[0]
    control_severe = performance[(performance.candidate == "control") & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]

    gates = config["promotion_gates"]
    screen_rows = []
    for name in targets_by_name:
        recent = performance[(performance.candidate == name) & (performance.cost_bps == 50) & (performance.window == "trailing_1y")].iloc[0]
        ytd = performance[(performance.candidate == name) & (performance.cost_bps == 50) & (performance.window == "ytd")].iloc[0]
        full = performance[(performance.candidate == name) & (performance.cost_bps == 50) & (performance.window == "full_recent")].iloc[0]
        severe = performance[(performance.candidate == name) & (performance.cost_bps == 200) & (performance.window == "trailing_1y")].iloc[0]
        checks = {
            "recent_return": bool(recent.cagr >= control_recent.cagr + gates["minimum_trailing_1y_cagr_improvement"]),
            "ytd_return": bool(ytd.cagr >= control_ytd.cagr + gates["minimum_ytd_cagr_improvement"]),
            "recent_sharpe": bool(recent.sharpe_zero_rf >= control_recent.sharpe_zero_rf * gates["minimum_recent_sharpe_ratio_to_control"]),
            "recent_drawdown": bool(abs(recent.max_drawdown) <= abs(control_recent.max_drawdown) * gates["maximum_recent_drawdown_ratio_to_control"]),
            "full_return_gate": bool(full.cagr >= control_full.cagr - gates["maximum_full_cagr_sacrifice"]),
            "full_drawdown_gate": bool(abs(full.max_drawdown) <= abs(control_full.max_drawdown) * gates["maximum_full_drawdown_ratio_to_control"]),
            "severe_cost": bool(severe.cagr > control_severe.cagr),
        }
        screen_rows.append({
            "candidate": name, "trailing_1y_cagr": recent.cagr, "trailing_1y_sharpe": recent.sharpe_zero_rf,
            "trailing_1y_drawdown": recent.max_drawdown, "ytd_cagr": ytd.cagr, "full_cagr": full.cagr,
            "full_drawdown": full.max_drawdown, "trailing_1y_200bps_cagr": severe.cagr, **checks,
            "all_screen_gates": all(checks.values()),
        })
    screen = pd.DataFrame(screen_rows).sort_values("trailing_1y_cagr", ascending=False)
    eligible = screen[screen.all_screen_gates]
    selected = str((eligible if len(eligible) else screen).iloc[0].candidate)
    selected_row = screen[screen.candidate == selected].iloc[0]

    delay_rows = []
    family, lookback_text, high_text = selected.split("__")
    lookback, high = int(lookback_text[:-1]), int(high_text) / 100
    base_returns = pd.concat(
        [control_paths[50].net_return.rename("leader"), family_paths[(family, 50)].net_return.rename("sleeve")], axis=1
    ).dropna()
    for delay in [0] + config["falsification"]["signal_delays_weeks"]:
        delayed_target = overlay_target(base_returns.index, base_returns.leader, base_returns.sleeve, lookback, high, delay)
        path = dynamic.simulate(base_returns, delayed_target, 50.0)
        for row in base.metric_rows(selected, f"delay_{delay}", 50, path):
            if row["window"] in {"full_recent", "trailing_1y", "ytd"}:
                delay_rows.append(row)
    delays = pd.DataFrame(delay_rows)

    targets_by_name[selected].rename_axis("Date").to_csv(OUTPUT / "selected_target_weights.csv")
    for cost in config["cost_bps"]:
        paths[(selected, int(cost))].rename_axis("Date").to_csv(OUTPUT / f"selected_path__{cost}bps.csv")

    # Falsification is calculated from the persisted artifacts that readers will
    # inspect, preventing an in-memory/on-disk evidence mismatch.
    selected_path = pd.read_csv(OUTPUT / "selected_path__50bps.csv", parse_dates=["Date"]).set_index("Date")
    control_path = pd.read_csv(config["control_path_50bps"], parse_dates=["Date"]).set_index("Date")
    joined = pd.concat([selected_path.net_return.rename("candidate"), control_path.net_return.rename("control")], axis=1).dropna()
    recent_joined = joined.loc[joined.index >= joined.index.max() - pd.DateOffset(years=1)]
    falsification_config = config["falsification"]
    bootstrap = pd.DataFrame([
        dynamic.block_bootstrap(recent_joined.candidate - recent_joined.control, int(block), int(falsification_config["bootstrap_draws"]), int(falsification_config["bootstrap_seed"]))
        for block in falsification_config["bootstrap_blocks_weeks"]
    ])
    rolling_share, completed_rolling_windows = completed_rolling_outperformance(
        joined, int(falsification_config["rolling_comparison_weeks"])
    )

    neighborhood = screen[screen.candidate.str.startswith(family)].copy()
    neighborhood["joint_improvement"] = (neighborhood.trailing_1y_cagr > control_recent.cagr) & (neighborhood.full_cagr > control_full.cagr)
    neighborhood_share = float(neighborhood.joint_improvement.mean()) if len(neighborhood) else 0.0

    recent_ciks = sorted({
        cik for date, ciks in family_targets[family].items()
        if date >= dates[-1] - pd.DateOffset(years=1) for cik in ciks
    })
    loo_rows = []
    company_names = events.drop_duplicates("cik10").set_index("cik10").company_name_as_filed
    for cik in recent_ciks:
        altered = weekly_form4.copy()
        altered[cik] = np.nan
        # Selection with price_confirmation="none" does not depend on the weekly price panel,
        # so the target list is unchanged; only simulate_weekly's execution differs (the
        # excluded ticker becomes untradeable and its weight is redistributed).
        loo_sleeve = insider.simulate_weekly(altered, family_targets[family], 50.0)
        returns = pd.concat([control_paths[50].net_return.rename("leader"), loo_sleeve.net_return.rename("sleeve")], axis=1).dropna()
        target = overlay_target(returns.index, returns.leader, returns.sleeve, lookback, high)
        path = dynamic.simulate(returns, target, 50.0)
        recent = next(row for row in base.metric_rows(selected, "base", 50, path) if row["window"] == "trailing_1y")
        loo_rows.append({"cik10": cik, "company_name": company_names.get(cik, cik), "trailing_1y_cagr": recent["cagr"], "cagr_change": recent["cagr"] - selected_row.trailing_1y_cagr})
    loo = pd.DataFrame(loo_rows).sort_values("cagr_change") if loo_rows else pd.DataFrame(columns=["cik10", "company_name", "trailing_1y_cagr", "cagr_change"])
    worst = loo.iloc[0] if len(loo) else None

    prefix_matches = []
    for cutoff in base_returns.index[26::26]:
        prefix = base_returns.loc[:cutoff]
        rebuilt = overlay_target(prefix.index, prefix.leader, prefix.sleeve, lookback, high)
        expected = targets_by_name[selected].loc[:cutoff]
        prefix_matches.append(bool(rebuilt.equals(expected)))

    bootstrap_4w = float(bootstrap.loc[bootstrap.block_weeks == 4, "probability_positive"].iloc[0])
    bootstrap_13w = float(bootstrap.loc[bootstrap.block_weeks == 13, "probability_positive"].iloc[0])
    minimum_bootstrap = float(falsification_config["minimum_bootstrap_probability_positive"])
    falsification = {
        "screen_gates_passed": bool(selected_row.all_screen_gates),
        "one_week_delay_beats_control": bool(delays[(delays.scenario == "delay_1") & (delays.window == "trailing_1y")].cagr.iloc[0] > control_recent.cagr),
        "two_week_delay_beats_control": bool(delays[(delays.scenario == "delay_2") & (delays.window == "trailing_1y")].cagr.iloc[0] > control_recent.cagr),
        "rolling_26w_outperformance_share": rolling_share,
        "completed_rolling_26w_windows": completed_rolling_windows,
        "rolling_window_gate_passed": bool(rolling_share >= float(falsification_config["minimum_completed_rolling_window_outperformance_share"])),
        "neighborhood_joint_improvement_share": neighborhood_share,
        "neighborhood_gate_passed": bool(neighborhood_share >= float(falsification_config["minimum_neighborhood_joint_improvement_share"])),
        "bootstrap_4w_probability_positive": bootstrap_4w,
        "bootstrap_13w_probability_positive": bootstrap_13w,
        "bootstrap_4w_gate_passed": bool(bootstrap_4w >= minimum_bootstrap),
        "bootstrap_13w_gate_passed": bool(bootstrap_13w >= minimum_bootstrap),
        "worst_leave_one_out_beats_control": bool(worst.trailing_1y_cagr > control_recent.cagr) if worst is not None else None,
        "prefix_invariance": bool(all(prefix_matches)) if prefix_matches else True,
    }
    required_gate_keys = [
        "screen_gates_passed", "one_week_delay_beats_control", "two_week_delay_beats_control",
        "rolling_window_gate_passed", "neighborhood_gate_passed", "bootstrap_4w_gate_passed",
        "bootstrap_13w_gate_passed", "worst_leave_one_out_beats_control", "prefix_invariance",
    ]
    falsification["required_gate_keys"] = required_gate_keys
    falsification["all_passed"] = required_gates_pass(falsification, required_gate_keys)

    performance.to_csv(OUTPUT / "performance.csv", index=False)
    screen.to_csv(OUTPUT / "screening_gates.csv", index=False)
    delays.to_csv(OUTPUT / "delay_stress.csv", index=False)
    bootstrap.to_csv(OUTPUT / "bootstrap.csv", index=False)
    neighborhood.to_csv(OUTPUT / "parameter_neighborhood.csv", index=False)
    loo.to_csv(OUTPUT / "recent_leave_one_company_out.csv", index=False)
    persisted_recent = next(row for row in base.metric_rows(selected, "persisted", 50, selected_path) if row["window"] == "trailing_1y")
    persisted_full = next(row for row in base.metric_rows(selected, "persisted", 50, selected_path) if row["window"] == "full_recent")
    roundtrip_checks = {
        "recent_cagr_matches_screen": bool(np.isclose(persisted_recent["cagr"], selected_row.trailing_1y_cagr, rtol=0, atol=1e-12)),
        "recent_sharpe_matches_screen": bool(np.isclose(persisted_recent["sharpe_zero_rf"], selected_row.trailing_1y_sharpe, rtol=0, atol=1e-12)),
        "full_cagr_matches_screen": bool(np.isclose(persisted_full["cagr"], selected_row.full_cagr, rtol=0, atol=1e-12)),
        "rolling_share_recomputable_from_persisted_paths": True,
    }
    roundtrip_checks["all_passed"] = bool(all(roundtrip_checks.values()))
    if not roundtrip_checks["all_passed"]:
        raise RuntimeError(f"persisted evidence mismatch: {roundtrip_checks}")

    artifact_hashes = {
        "control_path_50bps": sha256(ROOT / config["control_path_50bps"]),
        "selected_path_50bps": sha256(OUTPUT / "selected_path__50bps.csv"),
        "selected_path_100bps": sha256(OUTPUT / "selected_path__100bps.csv"),
        "selected_path_200bps": sha256(OUTPUT / "selected_path__200bps.csv"),
        "selected_target_weights": sha256(OUTPUT / "selected_target_weights.csv"),
    }

    result = {
        "experiment": config["experiment"], "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(targets_by_name), "selected_candidate": selected,
        "selected_trailing_1y_cagr": float(selected_row.trailing_1y_cagr), "selected_trailing_1y_sharpe": float(selected_row.trailing_1y_sharpe),
        "selected_trailing_1y_drawdown": float(selected_row.trailing_1y_drawdown), "selected_ytd_cagr": float(selected_row.ytd_cagr),
        "selected_full_cagr": float(selected_row.full_cagr), "selected_200bps_trailing_1y_cagr": float(selected_row.trailing_1y_200bps_cagr),
        "control_trailing_1y_cagr": float(control_recent.cagr), "control_full_cagr": float(control_full.cagr),
        "control_trailing_1y_sharpe": float(control_recent.sharpe_zero_rf), "control_trailing_1y_drawdown": float(control_recent.max_drawdown),
        "qualified_screen_candidates": int(screen.all_screen_gates.sum()), "falsification": falsification,
        "runtime": runtime, "persisted_artifact_roundtrip": roundtrip_checks, "artifact_sha256": artifact_hashes,
        "strategy_replacement_authorized": False, "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    decision = "passes" if falsification["all_passed"] else "does not pass"
    (OUTPUT / "report.md").write_text(
        "# SEC Form 4 dynamic overlay v1\n\n"
        f"Tested **{len(targets_by_name)}** predeclared causal conditional overlays combining three Form 4 insider-purchase "
        f"sleeve variants with the frozen breadth-20 cash-conversion leader. The strongest screened candidate was "
        f"`{selected}` with **{selected_row.trailing_1y_cagr:.2%}** trailing-one-year CAGR, **{selected_row.trailing_1y_sharpe:.3f}** "
        f"Sharpe, and **{selected_row.trailing_1y_drawdown:.2%}** drawdown, versus **{control_recent.cagr:.2%}**, "
        f"**{control_recent.sharpe_zero_rf:.3f}**, and **{control_recent.max_drawdown:.2%}** for the unchanged control. "
        f"Full-period CAGR was **{selected_row.full_cagr:.2%}** versus **{control_full.cagr:.2%}** for the control.\n\n"
        f"It {decision} the full falsification gauntlet. Across **{completed_rolling_windows}** completed 26-week windows, "
        f"it beat the control **{rolling_share:.2%}** of the time. The 4-week and 13-week block-bootstrap "
        f"probabilities of positive excess return were **{bootstrap_4w:.2%}** and **{bootstrap_13w:.2%}**, "
        f"against a predeclared **{minimum_bootstrap:.0%}** requirement. No strategy is promoted automatically.\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
