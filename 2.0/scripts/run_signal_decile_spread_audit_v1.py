#!/usr/bin/env python3
"""Do the names the rule buys actually beat the names it avoids?

The IC audit asked whether each signal orders the full cross-section. This asks
the question that decides whether a strategy makes money: does the top decile
outperform the bottom decile, and how much of any gain comes from one name.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/signal_decile_spread_audit_v1.json"
OUTPUT = ROOT / "evidence/signal_decile_spread_audit_v1"


def main() -> int:
    config = json.loads(CONFIG.read_text())
    panel = pd.read_csv(ROOT / config["panel"])
    label = config["label"]
    fraction = float(config["decile_fraction"])
    minimum = int(config["minimum_names_per_decision"])

    results, rows = {}, []
    for feature in config["features"]:
        tops, bottoms, wins, concentration = [], [], 0, []
        for decision, group in panel.groupby("decision_at"):
            frame = group[[feature, label]].dropna()
            if len(frame) < minimum:
                continue
            frame = frame.sort_values(feature)
            size = max(1, int(len(frame) * fraction))
            bottom = float(frame[label].iloc[:size].mean())
            top = float(frame[label].iloc[-size:].mean())
            gains = frame[label].iloc[-size:]
            positive = gains[gains > 0].sum()
            share = float(gains.max() / positive) if positive > 0 else float("nan")
            tops.append(top); bottoms.append(bottom); concentration.append(share)
            wins += int(top > bottom)
            rows.append({"feature": feature, "decision_at": decision, "top_decile": top,
                         "bottom_decile": bottom, "spread": top - bottom, "names": len(frame),
                         "best_name_return": float(gains.max()),
                         "best_name_share_of_decile_gain": share})
        if not tops:
            continue
        spread = float(np.mean(tops) - np.mean(bottoms))
        results[feature] = {
            "decisions_used": len(tops),
            "mean_top_decile_return": float(np.mean(tops)),
            "mean_bottom_decile_return": float(np.mean(bottoms)),
            "mean_spread": spread,
            "decisions_where_top_beat_bottom": wins,
            "hit_rate": float(wins / len(tops)),
            "spread_is_positive": bool(spread > 0),
            "mean_best_name_share_of_decile_gain": float(np.nanmean(concentration)),
        }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT / "decile_by_decision.csv", index=False)
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "features": results,
        "any_signal_has_positive_spread": bool(any(v["spread_is_positive"] for v in results.values())),
        "relationship_to_ic_audit": config["relationship_to_ic_audit"],
        "small_sample_warning": config["small_sample_warning"],
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"  {'signal':<20}{'top 10%':>10}{'bottom 10%':>12}{'spread':>10}{'hit rate':>11}{'best-name share':>17}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["mean_spread"]):
        print(f"  {name:<20}{100*r['mean_top_decile_return']:>9.2f}%{100*r['mean_bottom_decile_return']:>11.2f}%"
              f"{100*r['mean_spread']:>9.2f}%{r['decisions_where_top_beat_bottom']}/{r['decisions_used']:<9}"
              f"{100*r['mean_best_name_share_of_decile_gain']:>15.1f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
