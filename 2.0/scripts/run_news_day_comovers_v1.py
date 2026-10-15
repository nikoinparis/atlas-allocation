#!/usr/bin/env python3
"""Queue item A26: read A24's untouched 2019-2025H1 holdout for news-day co-movers, once.

Pre-registered in config/news_day_comovers_registry_v1.json (committed before this ran).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import run_news_jump_followers_v1 as a24  # noqa: E402

REGISTRY = ROOT / "config/news_day_comovers_registry_v1.json"
EVENTS = ROOT / "evidence/news_jump_followers_v1/events.csv"
OUTPUT = ROOT / "evidence/news_day_comovers_v1"


def main() -> int:
    registry = json.loads(REGISTRY.read_text())
    assert registry["registered_before_the_holdout_was_read"]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(20261016)
    ev = pd.read_csv(EVENTS, parse_dates=["date"])
    hold = ev[(ev.date >= "2019-01-01") & (ev.date <= "2025-06-30")]
    out = {}
    for col in ("T2_followers_126d_moved", "T1_followers_21d_moved"):
        frame = hold.rename(columns={col: "x"})[["date", "month", "leader", "x"]]
        out[col] = a24.summarise(frame, "x", rng)
        out[col]["regimes"] = {lab: a24.summarise(frame[(frame.date >= a) & (frame.date <= b)], "x", rng)
                               for lab, (a, b) in {"2019": ("2019-01-01", "2019-12-31"), "2020": ("2020-01-01", "2020-12-31"),
                                                   "2021-2022": ("2021-01-01", "2022-12-31"),
                                                   "2023-2025H1": ("2023-01-01", "2025-06-30")}.items()}
    h = out["T2_followers_126d_moved"]
    criteria = {"holdout_mean_positive_p_below_0.05": h["mean"] > 0 and h["bootstrap_p"] < 0.05,
                "survives_dropping_top10_events": h["mean_without_top10_events"] > 0,
                "mean_above_50bps": h["mean"] > 0.005}
    passes = all(criteria.values())
    for col, s in out.items():
        tag = "TRIAL" if col.startswith("T2") else "diagnostic"
        print(f"{tag} {col}: events {s['events']} mean {s['mean']:+.2%} median {s['median']:+.2%} positive {s['share_positive']:.0%} "
              f"p {s['bootstrap_p']:.4f} without top-10 {s['mean_without_top10_events']:+.2%}")
        for lab, r in s["regimes"].items():
            if not r.get("inconclusive"):
                print(f"    {lab:12s} events {r['events']:5d} mean {r['mean']:+.2%} p {r['bootstrap_p']:.3f}")
    for k, v in criteria.items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"A26 {'PASSES' if passes else 'FAILS'}")
    (OUTPUT / "result.json").write_text(json.dumps({"registry": str(REGISTRY.relative_to(ROOT)), "holdout": out,
                                                    "criteria": criteria, "passes": passes,
                                                    "live_trading_enabled": False,
                                                    "strategy_promotion_authorized": False}, indent=2, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
