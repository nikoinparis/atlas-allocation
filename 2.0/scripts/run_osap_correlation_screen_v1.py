#!/usr/bin/env python3
"""Screen this project's strategies against 212 published anomalies for breadth.

This inverts the project's usual order. Every previous cycle found a signal with a
good backtest and then discovered what it correlated with; this measures
correlation first, against return series somebody else published, and costs zero
trials on our own data because nothing is being fitted.

Two outputs, and the second is the more useful one.

  most orthogonal   the published anomalies least correlated with what we already
                    hold, which is where breadth could come from

  nearest neighbour the published anomaly each of our strategies is closest to,
                    which asks whether we have been rediscovering something that
                    was already in the literature

Source: openassetpricing.com, October 2025 release, monthly long-short returns for
212 predictors. It ends 2024-12, so the ETF family overlaps by 240 months and the
SEC family by only 24. Twenty-four months puts a 95% interval of roughly +/-0.40
around a zero correlation, so SEC-family numbers are reported as directional and
must not be read as measurements.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
GGG = ROOT / "data/ggg_vintages/ggg_causal_v2_027530550388432a/data/01_data_hub/weekly_prices.csv"
OUTPUT = ROOT / "evidence/osap_correlation_screen_v1"
CASH = "cash::USD"
MIN_MONTHS_LONG = 60
MIN_MONTHS_SHORT = 18

ETF_BOOKS = {
    "return_first_60_40_blend": "evidence/forward_return_first_60_40_blend_v1/frozen_weights.csv",
    "past_only_consensus_selector": "evidence/exhaustive_return_first_discovery_batch_66/"
                                    "retrospective_ceiling_adversarial/past_only_selector_weights.csv",
}
SEC_PATHS = {
    "cash_conversion_sleeve_b20": "evidence/cash_conversion_sleeve_path_v1/sleeve_path__base__50bps__breadth20.csv",
    "cash_conversion_composite": "evidence/sec_cash_conversion_breadth20_candidate_audit_v1/candidate_path_50bps.csv",
    "growth_leader_sleeve": "evidence/sec_growth_confidence_universal_cap_v1/path__base__confidence_10_40__cap_1.50x__50bps.csv",
}


def monthly_from_weights(path: Path, prices: pd.DataFrame) -> pd.Series:
    weights = pd.read_csv(path, index_col=0)
    weights.index = pd.to_datetime(weights.index)
    weights = weights.drop(columns=[CASH], errors="ignore")
    shared = [c for c in weights.columns if c in prices.columns]
    weekly = prices[shared].pct_change()
    aligned = weights[shared].reindex(weekly.index).ffill().fillna(0.0)
    gross = (aligned.shift(1) * weekly).sum(axis=1)          # decide on t, earn over t+1
    return (1 + gross).resample("ME").prod() - 1


def monthly_from_path(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    column = "Date" if "Date" in frame else frame.columns[0]
    frame[column] = pd.to_datetime(frame[column])
    series = frame.set_index(column).sort_index()["net_return"]
    return (1 + series).resample("ME").prod() - 1


def screen(ours: pd.Series, anomalies: pd.DataFrame, minimum: int) -> pd.DataFrame:
    rows = []
    for name in anomalies.columns:
        joined = pd.concat([ours.rename("ours"), anomalies[name].rename("them")], axis=1).dropna()
        if len(joined) < minimum:
            continue
        rows.append({"anomaly": name, "months": len(joined),
                     "correlation": float(joined.ours.corr(joined.them))})
    return pd.DataFrame(rows).sort_values("correlation", key=lambda s: s.abs())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--osap", required=True)
    args = parser.parse_args()

    anomalies = pd.read_csv(args.osap)
    anomalies["date"] = pd.to_datetime(anomalies.date)
    anomalies = anomalies.set_index("date").resample("ME").last()
    if anomalies.abs().median().median() > 1.0:          # percent, not decimal
        anomalies = anomalies / 100.0

    prices = pd.read_csv(GGG, index_col=0)
    prices.index = pd.to_datetime(prices.index)

    ours: dict[str, tuple[pd.Series, int]] = {}
    for name, rel in ETF_BOOKS.items():
        ours[name] = (monthly_from_weights(ROOT / rel, prices), MIN_MONTHS_LONG)
    for name, rel in SEC_PATHS.items():
        ours[name] = (monthly_from_path(ROOT / rel), MIN_MONTHS_SHORT)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    summary, frames = [], []
    for name, (series, minimum) in ours.items():
        table = screen(series.dropna(), anomalies, minimum)
        if table.empty:
            summary.append({"strategy": name, "note": "no anomaly met the minimum overlap"})
            continue
        table.insert(0, "strategy", name)
        frames.append(table)
        nearest = table.reindex(table.correlation.abs().sort_values(ascending=False).index)
        summary.append({
            "strategy": name,
            "overlap_months_median": int(table.months.median()),
            "anomalies_compared": int(len(table)),
            "median_abs_correlation": round(float(table.correlation.abs().median()), 4),
            "most_orthogonal": table.head(5)[["anomaly", "correlation"]].to_dict("records"),
            "nearest_neighbour": nearest.head(5)[["anomaly", "correlation"]].to_dict("records"),
        })
    if frames:
        pd.concat(frames, ignore_index=True).to_csv(OUTPUT / "correlations.csv", index=False)

    payload = {
        "experiment": "osap_correlation_screen_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "openassetpricing.com October 2025 release, 212 predictors, monthly long-short",
        "source_last_month": str(anomalies.index.max().date()),
        "trials_consumed": 0,
        "why_zero_trials": "nothing is fitted here; these are correlations against series published by others",
        "caveat": "SEC-family overlap is ~24 months, where a 95% interval around zero is about +/-0.40; treat as directional",
        "strategies": summary,
        "live_trading_enabled": False,
    }
    (OUTPUT / "result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    for row in summary:
        if "note" in row:
            print(f"{row['strategy']:<30} {row['note']}"); continue
        print(f"\n{row['strategy']}   ({row['overlap_months_median']} months, "
              f"{row['anomalies_compared']} anomalies, median |r| {row['median_abs_correlation']:.3f})")
        print("   most orthogonal :", ", ".join(f"{d['anomaly']} {d['correlation']:+.3f}" for d in row["most_orthogonal"][:4]))
        print("   nearest         :", ", ".join(f"{d['anomaly']} {d['correlation']:+.3f}" for d in row["nearest_neighbour"][:4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
