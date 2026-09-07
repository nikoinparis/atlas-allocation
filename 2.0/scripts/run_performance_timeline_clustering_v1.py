#!/usr/bin/env python3
"""Group strategies by WHEN they win, not by whether they move together.

The owner's idea, and it is a better question than the one Step 272 asked.
Correlation clustering asks whether two strategies move together. This asks
whether they *win at the same time*, which is different: two strategies can
correlate weakly week to week and still have their good years in the same place.

The method:

  1. for every saved path, a rolling 26-week return
  2. that profile standardised, so a strategy's SHAPE in time is compared rather
     than its level -- otherwise the high-return strategies cluster together for
     trivial reasons
  3. paths clustered on the correlation of those profiles
  4. for each cluster, when it wins, and what the macro state was doing then

If distinct groups of strategies peak in distinct periods, that is evidence for
regimes with something in them -- which is exactly what Steps 266, 267 and 269
looked for and did not find. If every cluster peaks in the same window, the
library has one good period and everything else is noise around it.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
WINDOW = 26
MIN_WEEKS = 120
MACRO = ROOT / "evidence/macro_state_v1/macro_state_probabilities.csv"


def load_paths() -> dict[str, pd.Series]:
    series = {}
    for path in sorted(ROOT.glob("evidence/**/*.csv")):
        name = path.name.lower()
        if not any(k in name for k in ("path", "candidate")):
            continue
        if path.stat().st_size > 20_000_000:
            continue
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty or len(frame.columns) < 2:
            continue
        column = frame.columns[0]
        try:
            frame[column] = pd.to_datetime(frame[column], utc=True, errors="coerce", format="mixed")
        except Exception:
            continue
        frame = frame.dropna(subset=[column]).set_index(column).sort_index()
        frame = frame[~frame.index.duplicated(keep="first")]
        numeric = [c for c in frame.columns if frame[c].dtype.kind == "f"]
        if not numeric:
            continue
        value = frame[numeric[0]].dropna()
        if len(value) < MIN_WEEKS or value.abs().median() > 0.2 or value.abs().max() > 2.0:
            continue
        # weekly grid so daily and weekly paths are comparable
        weekly = value.resample("W-FRI").apply(lambda x: float(np.prod(1 + x) - 1) if len(x) else np.nan)
        if weekly.notna().sum() >= MIN_WEEKS:
            series[str(path.relative_to(ROOT))] = weekly.dropna()
    return series


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/performance_timeline_v1")
    parser.add_argument("--cut", type=float, default=0.5)
    args = parser.parse_args()

    series = load_paths()
    frame = pd.DataFrame(series)
    rolling = (1.0 + frame.fillna(0.0)).rolling(WINDOW).apply(np.prod, raw=True) - 1.0
    rolling = rolling.where(frame.notna().rolling(WINDOW).sum() >= WINDOW * 0.8)
    # Paths span very different histories. Restrict to the window where most of
    # them exist before requiring coverage, or the intersection is two columns --
    # which is what the first run produced.
    rolling = rolling.loc[rolling.index >= pd.Timestamp("2023-06-01", tz="UTC")]
    rolling = rolling.dropna(axis=1, thresh=int(0.85 * len(rolling)))
    rolling = rolling.dropna(axis=0, how="any")
    if rolling.shape[1] < 20:
        raise SystemExit(f"only {rolling.shape[1]} paths with usable rolling profiles")

    # standardise each profile so shape in time is compared, not level
    shape = (rolling - rolling.mean()) / rolling.std(ddof=0)
    correlation = np.array(shape.corr(min_periods=40).fillna(0.0).to_numpy(), copy=True)
    np.fill_diagonal(correlation, 1.0)
    distance = np.clip(1.0 - correlation, 0.0, 2.0)
    np.fill_diagonal(distance, 0.0)
    tree = linkage(squareform(distance, checks=False), method="average")
    labels = fcluster(tree, t=args.cut, criterion="distance")

    macro = None
    if MACRO.is_file():
        macro = pd.read_csv(MACRO, index_col=0, parse_dates=True)
        macro.index = pd.to_datetime(macro.index, utc=True)

    rows = []
    for cluster in sorted(set(labels)):
        members = [c for c, lab in zip(shape.columns, labels) if lab == cluster]
        if len(members) < 2:
            continue
        profile = rolling[members].mean(axis=1).dropna()
        if profile.empty:
            continue
        peak = profile.idxmax()
        best = profile.nlargest(max(4, len(profile) // 10))
        entry = {"cluster": int(cluster), "members": len(members),
                 "peak_week": str(peak.date()),
                 "peak_26w_return": float(profile.max()),
                 "median_26w_return": float(profile.median()),
                 "best_decile_window": f"{str(best.index.min().date())} to {str(best.index.max().date())}",
                 "share_of_best_decile_after_2025_04": float((best.index >= "2025-04-04").mean()),
                 "example_members": members[:3]}
        if macro is not None:
            joined = pd.concat([profile.rename("p"), macro.mean(axis=1).rename("m")], axis=1).dropna()
            if len(joined) > 30:
                entry["correlation_with_macro_state"] = float(joined.p.corr(joined.m))
        rows.append(entry)
    table = pd.DataFrame(rows).sort_values("peak_week")

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"path": shape.columns, "cluster": labels}).to_csv(out / "membership.csv", index=False)
    table.to_csv(out / "clusters.csv", index=False)

    peaks = pd.to_datetime(table.peak_week)
    same_year = peaks.dt.year.nunique() == 1 if len(peaks) else False
    after_break = float((peaks >= pd.Timestamp("2025-04-04")).mean()) if len(peaks) else 0.0

    if len(table) < 2:
        verdict = "the profiles do not separate into distinct groups at this cut"
    elif after_break > 0.8:
        verdict = (f"{after_break:.0%} of clusters peak after 2025-04-04. The library has ONE good "
                   f"period and everything in it is a variation on the same bet. There is no earlier "
                   f"regime with its own winners to find.")
    elif same_year:
        verdict = (f"every cluster peaks in {peaks.dt.year.iloc[0]}, so the groups differ in shape "
                   f"but not in timing")
    else:
        verdict = (f"clusters peak in {sorted(set(peaks.dt.year))} -- distinct groups win in distinct "
                   f"periods, which is the first evidence here of regimes with different winners")

    result = {"experiment": "performance_timeline_v1",
              "question": "do different strategies win in different periods, or does the library have one good period",
              "paths_profiled": int(shape.shape[1]), "rolling_window_weeks": WINDOW,
              "clusters": rows, "share_of_clusters_peaking_after_the_break": after_break,
              "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    show = ["cluster", "members", "peak_week", "peak_26w_return", "median_26w_return",
            "best_decile_window", "share_of_best_decile_after_2025_04"]
    if "correlation_with_macro_state" in table.columns:
        show.append("correlation_with_macro_state")
    print(f"{shape.shape[1]} paths profiled on {WINDOW}-week rolling returns\n")
    print(table[show].to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
