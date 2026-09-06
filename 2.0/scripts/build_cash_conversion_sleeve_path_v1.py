#!/usr/bin/env python3
"""Simulate and save the breadth-20 cash-conversion sleeve's own return path.

The eleven-week overlay that allocates between the leader and cash-conversion
sleeves needs each sleeve's own returns. The leader's are saved;
cash-conversion's are not. `audit_sec_cash_conversion_breadth20_candidate_v1`
computes them in memory through `simulate_cash` and writes out only the composite
it feeds, so anything reconstructing the overlay has nothing to read.

Feeding the composite path back in as the sleeve input is circular and produces
an overlay that agrees with the real one on roughly half of weeks, which is worse
than an obvious failure because it looks right on any single date. This writes the
sleeve out so the overlay has a genuine input.

The setup below is transcribed from the audit rather than reinvented, so the two
stay in step: same choices, same weekly index, same price sources and terminal
dates, same base scenario at 50bps with breadth 20 and no cap.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import run_sec_growth_survivorship_retest_v1 as base
import run_sec_cash_conversion_capped_dynamic_v1 as capped
import run_sec_cash_conversion_breadth_dynamic_v1 as breadth_runner

DISCOVERY = ROOT / "evidence/sec_independent_fundamental_discovery_v1"
OUTPUT = ROOT / "evidence/cash_conversion_sleeve_path_v1"
BREADTH = 20
COST_BPS = 50.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--breadth", type=int, default=BREADTH)
    parser.add_argument("--cost-bps", type=float, default=COST_BPS)
    args = parser.parse_args()

    scores = pd.read_csv(DISCOVERY / "factor_scores.csv", dtype={"cik10": str}, parse_dates=["decision_at"])
    choices = breadth_runner.make_choices(scores[scores.family == "cash_conversion"], args.breadth)

    end = pd.to_datetime(pd.read_csv(base.BENCHMARK_PRICES, usecols=["observation_date"]).observation_date).max()
    index = pd.date_range(start="2023-01-01", end=end + pd.offsets.Week(weekday=4), freq="W-FRI")
    targets = base.build_targets(choices, index)

    sources, terminals = base.price_sources(), base.terminal_dates()
    series, missing = {}, []
    for cik in sorted(set(choices.cik10)):
        spec = sources.get(cik)
        if spec is None:
            missing.append(cik)
            continue
        source, path = spec
        series[cik] = base.read_weekly_price(path, source, index, terminals.get(cik))
    weekly = pd.DataFrame(series, index=index)
    print(f"priced {len(series)} of {len(set(choices.cik10))} selected issuers", flush=True)

    sleeve, peak_internal = capped.simulate_cash(weekly, targets, "base", args.cost_bps, None, args.breadth)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    name = f"sleeve_path__base__{int(args.cost_bps)}bps__breadth{args.breadth}.csv"
    sleeve.rename_axis("Date").to_csv(OUTPUT / name)
    payload = {
        "experiment": "cash_conversion_sleeve_path_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "what_this_is": "the breadth-20 cash-conversion sleeve's own returns, the overlay's missing input",
        "breadth": args.breadth, "cost_bps": args.cost_bps, "scenario": "base",
        "weeks": int(len(sleeve)), "first_week": str(sleeve.index[0].date()),
        "last_week": str(sleeve.index[-1].date()),
        "selected_issuers": int(len(set(choices.cik10))),
        "priced_issuers": int(len(series)),
        "unpriced_issuers": missing,
        "peak_internal_weight": float(peak_internal),
        "price_vintage_end": str(end.date()),
        "live_trading_enabled": False,
    }
    (OUTPUT / "manifest.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in payload.items() if k != "unpriced_issuers"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
