#!/usr/bin/env python3
"""Audit recent holding-period concentration for the frozen SEC growth retest."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence" / "sec_growth_survivorship_retest_v1"
ENGINE_PATH = ROOT / "scripts" / "run_sec_growth_survivorship_retest_v1.py"


def load_engine():
    spec = importlib.util.spec_from_file_location("sec_growth_engine", ENGINE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the SEC growth retest engine")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    engine = load_engine()
    choices = pd.read_csv(EVIDENCE / "portfolio_choices.csv", dtype={"cik10": str})
    choices["decision_at"] = pd.to_datetime(choices["decision_at"], utc=True)
    benchmark_raw = pd.read_csv(engine.BENCHMARK_PRICES, usecols=["observation_date"])
    end = pd.to_datetime(benchmark_raw["observation_date"]).max()
    weekly_index = pd.date_range(
        start=choices["decision_at"].min().tz_localize(None),
        end=end + pd.offsets.Week(weekday=4),
        freq="W-FRI",
    )
    targets = engine.build_targets(choices, weekly_index)
    sources = engine.price_sources()
    terminals = engine.terminal_dates()
    selected = sorted(set(choices["cik10"]))
    weekly = pd.DataFrame(index=weekly_index)
    for cik in selected:
        spec = sources.get(cik)
        if spec is None:
            continue
        source, path = spec
        weekly[cik] = engine.read_weekly_price(path, source, weekly_index, terminals.get(cik))

    name_map = choices.drop_duplicates("cik10").set_index("cik10")["company_name"].to_dict()
    target_dates = sorted(targets)
    rows = []
    for offset, effective in enumerate(target_dates):
        next_effective = target_dates[offset + 1] if offset + 1 < len(target_dates) else weekly_index[-1]
        for cik in targets[effective]:
            start_price = weekly.at[effective, cik] if cik in weekly else np.nan
            end_price = weekly.at[next_effective, cik] if cik in weekly else np.nan
            holding_return = (
                float(end_price) / float(start_price) - 1.0
                if pd.notna(start_price) and pd.notna(end_price) and float(start_price) != 0.0
                else np.nan
            )
            rows.append({
                "decision_at": choices.loc[
                    choices["cik10"].eq(cik)
                    & choices["decision_at"].lt(pd.Timestamp(effective, tz="UTC")),
                    "decision_at",
                ].max(),
                "effective_date": effective,
                "holding_end": next_effective,
                "cik10": cik,
                "company_name": name_map.get(cik, cik),
                "intended_weight": 0.2,
                "price_available": bool(pd.notna(start_price)),
                "holding_return": holding_return,
                "equal_weight_return_contribution": 0.2 * holding_return if pd.notna(holding_return) else np.nan,
            })
    periods = pd.DataFrame(rows).sort_values(["effective_date", "holding_return"], ascending=[True, False])
    periods.to_csv(EVIDENCE / "holding_period_concentration.csv", index=False)

    latest = periods[periods["effective_date"].eq(periods["effective_date"].max())].copy()
    available = latest.dropna(subset=["holding_return"]).sort_values("holding_return", ascending=False)
    best = available.iloc[0]
    equal_weight_period_return = float((1.0 + available["holding_return"]).prod() ** (1.0 / len(available)) - 1.0)
    arithmetic_contribution_sum = float(available["equal_weight_return_contribution"].sum())
    best_arithmetic_share = (
        float(best["equal_weight_return_contribution"] / arithmetic_contribution_sum)
        if arithmetic_contribution_sum > 0 else None
    )
    without_best_cash_return = float(
        available.loc[available["cik10"].ne(best["cik10"]), "equal_weight_return_contribution"].sum()
    )

    perf = pd.read_csv(EVIDENCE / "performance.csv")
    stress = perf[
        perf["candidate"].eq("growth")
        & perf["scenario"].isin(["base", "adverse"])
        & perf["window"].isin(["full_recent", "trailing_1y"])
    ][["scenario", "cost_bps", "window", "cagr", "sharpe_zero_rf", "max_drawdown"]]
    stress.to_csv(EVIDENCE / "cost_scenario_stress_summary.csv", index=False)

    summary = {
        "latest_effective_date": str(pd.Timestamp(latest["effective_date"].iloc[0]).date()),
        "latest_holding_end": str(pd.Timestamp(latest["holding_end"].iloc[0]).date()),
        "latest_available_holdings": int(len(available)),
        "best_latest_holding": str(best["company_name"]),
        "best_latest_holding_return": float(best["holding_return"]),
        "latest_arithmetic_equal_weight_return": arithmetic_contribution_sum,
        "latest_geometric_mean_holding_return": equal_weight_period_return,
        "best_holding_share_of_positive_arithmetic_return": best_arithmetic_share,
        "latest_return_if_best_weight_held_as_cash": without_best_cash_return,
        "interpretation": (
            "Recent performance is materially concentrated when the best holding accounts for more than half "
            "of the portfolio's arithmetic holding-period return. This is a diagnostic, not a tuned strategy."
        ),
    }
    (EVIDENCE / "recent_concentration_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
