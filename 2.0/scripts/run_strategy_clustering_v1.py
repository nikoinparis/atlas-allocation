#!/usr/bin/env python3
"""How many genuinely distinct strategies has this project actually built?

Unsupervised learning used for what it is good at here -- finding structure --
rather than for predicting returns, which Step 264 established is not where it
helps on 58 quarterly decisions.

Step 245 measured 1.57 effective independent strategies among the four on the
dashboard. This asks the same question of everything: 710 saved return paths,
clustered by how they co-move. If the whole library collapses into a handful of
clusters, the breadth problem is not a property of the four displayed strategies,
it is a property of the entire research programme.

Correlation distance and hierarchical clustering, plus the participation ratio
used in Steps 245 to 247 so the number is comparable with them.
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
MIN_WEEKS = 100


def participation_ratio(correlation: np.ndarray) -> float:
    eigenvalues = np.linalg.eigvalsh(correlation)
    eigenvalues = eigenvalues[eigenvalues > 0]
    return float(eigenvalues.sum() ** 2 / (eigenvalues ** 2).sum())


def load_paths() -> pd.DataFrame:
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
        numeric = [c for c in frame.columns if frame[c].dtype.kind == "f"]
        if not numeric:
            continue
        value = frame[numeric[0]].dropna()
        if len(value) < MIN_WEEKS or value.abs().median() > 0.2 or value.abs().max() > 2.0:
            continue
        series[str(path.relative_to(ROOT))] = value
    return pd.DataFrame(series)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/strategy_clustering_v1")
    args = parser.parse_args()

    frame = load_paths()
    # Paths span very different windows -- some reach back to 2005, most start
    # 2023-01 -- so an outer join is mostly holes and requiring 60% coverage on
    # both axes collapsed the set to a single column. Restrict to the window where
    # most paths actually live, then require completeness inside it.
    window = frame.loc[frame.index >= pd.Timestamp("2023-01-06", tz="UTC")]
    frame = window.dropna(axis=1, thresh=int(0.9 * len(window)))
    frame = frame.dropna(axis=0, how="any")
    if frame.shape[1] < 10:
        raise SystemExit(f"only {frame.shape[1]} comparable paths after alignment")

    correlation = frame.corr().to_numpy()
    correlation = np.nan_to_num(correlation, nan=0.0)
    np.fill_diagonal(correlation, 1.0)
    ratio = participation_ratio(correlation)

    distance = np.clip(1.0 - correlation, 0.0, 2.0)
    np.fill_diagonal(distance, 0.0)
    tree = linkage(squareform(distance, checks=False), method="average")

    rows = []
    for cut in (0.1, 0.2, 0.3, 0.5, 0.7):
        labels = fcluster(tree, t=cut, criterion="distance")
        sizes = pd.Series(labels).value_counts()
        rows.append({"correlation_distance_cut": cut,
                     "implied_min_correlation": round(1 - cut, 2),
                     "clusters": int(labels.max()),
                     "largest_cluster": int(sizes.iloc[0]),
                     "share_in_largest": round(float(sizes.iloc[0] / len(labels)), 4),
                     "singletons": int((sizes == 1).sum())})
    table = pd.DataFrame(rows)

    labels = fcluster(tree, t=0.3, criterion="distance")
    membership = pd.DataFrame({"path": frame.columns, "cluster": labels})
    upper = correlation[np.triu_indices_from(correlation, k=1)]

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "cluster_counts.csv", index=False)
    membership.to_csv(out / "membership_at_0.3.csv", index=False)

    result = {"experiment": "strategy_clustering_v1",
              "paths_clustered": int(frame.shape[1]), "overlapping_weeks": int(frame.shape[0]),
              "effective_independent_strategies_participation_ratio": ratio,
              "share_of_nominal": float(ratio / frame.shape[1]),
              "median_pairwise_correlation": float(np.median(upper)),
              "share_of_pairs_above_0.8": float((upper > 0.8).mean()),
              "share_of_pairs_above_0.5": float((upper > 0.5).mean()),
              "cluster_counts": rows,
              "comparison": "Step 245 measured 1.57 effective independent strategies among the four on the dashboard",
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"{frame.shape[1]} saved paths over {frame.shape[0]} common weeks\n")
    print(f"median pairwise correlation      {np.median(upper):.4f}")
    print(f"share of pairs above 0.5         {(upper > 0.5).mean():.1%}")
    print(f"share of pairs above 0.8         {(upper > 0.8).mean():.1%}")
    print(f"effective independent strategies {ratio:.2f}  ({ratio/frame.shape[1]:.1%} of nominal)\n")
    print(table.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
