#!/usr/bin/env python3
"""Which of the four features is doing anything? MDA and MDI.

Queue item A7, and the owner's framing is the right one: this is not machine
learning predicting returns, it is machine learning as a diagnostic. The books in
this project are built from four features -- residual momentum, trend quality,
quality momentum and event score -- and nobody has ever measured which of them
carries information once the others are present.

Two measures, because they disagree in a known way and the disagreement is
informative. MDI is what the forest thinks it used, and it is biased toward
features with more distinct values. MDA is what actually degrades when a feature
is shuffled, which is the honest one, and it is computed here on a purged and
embargoed split so a feature cannot look important by leaking across the fold
boundary.

Nothing here predicts anything or proposes a strategy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data/sec_broad_research_panel_v4_clean"
FEATURES = ["residual_momentum", "trend_quality", "quality_momentum", "event_score"]
EMBARGO_WEEKS = 13


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="evidence/feature_importance_v1")
    parser.add_argument("--trees", type=int, default=200)
    parser.add_argument("--shuffles", type=int, default=10)
    args = parser.parse_args()

    panel = pd.read_csv(PANEL / "panel.csv.gz", dtype={"cik10": str})
    panel["decision_at"] = pd.to_datetime(panel.decision_at, utc=True)
    target = next((c for c in panel.columns if "future" in c and "return" in c), None)
    if target is None:
        raise SystemExit(f"no forward-return column in the panel; columns are {list(panel.columns)}")

    usable = panel.dropna(subset=FEATURES + [target]).copy()
    decisions = sorted(usable.decision_at.unique())
    folds = []
    for holdout in decisions[3:]:
        # purge the embargo window around the holdout so nothing leaks across it
        train = usable[usable.decision_at < holdout - pd.Timedelta(weeks=EMBARGO_WEEKS)]
        test = usable[usable.decision_at == holdout]
        if len(train) < 2000 or len(test) < 200:
            continue
        folds.append((holdout, train, test))
    if not folds:
        raise SystemExit("no usable folds after purging")

    rng = np.random.default_rng(20260906)
    mdi_rows, mda_rows, baselines = [], [], []
    for holdout, train, test in folds:
        model = RandomForestRegressor(n_estimators=args.trees, max_depth=6, min_samples_leaf=50,
                                      n_jobs=-1, random_state=20260906)
        model.fit(train[FEATURES], train[target])
        mdi_rows.append(dict(zip(FEATURES, model.feature_importances_)))

        predicted = model.predict(test[FEATURES])
        # reset both indexes before correlating. pd.Series(predicted) carries a
        # fresh 0..n index while test[target] keeps the panel's, and .corr aligns
        # on index, so without this almost nothing overlaps and every fold returns
        # NaN -- which the first run reported as "no feature is load-bearing".
        actual = test[target].reset_index(drop=True)
        base = float(pd.Series(predicted).rank().corr(actual.rank()))
        baselines.append(base)
        row = {}
        for feature in FEATURES:
            drops = []
            for _ in range(args.shuffles):
                shuffled = test[FEATURES].copy()
                shuffled[feature] = rng.permutation(shuffled[feature].to_numpy())
                score = float(pd.Series(model.predict(shuffled)).rank().corr(actual.rank()))
                drops.append(base - score)
            row[feature] = float(np.mean(drops))
        mda_rows.append(row)

    mdi = pd.DataFrame(mdi_rows)
    mda = pd.DataFrame(mda_rows)
    baseline = np.array(baselines)

    summary = []
    for feature in FEATURES:
        values = mda[feature].to_numpy()
        summary.append({
            "feature": feature,
            "mdi_mean_share": float(mdi[feature].mean()),
            "mda_mean_drop": float(values.mean()),
            "mda_t_stat": float(values.mean() / (values.std(ddof=1) / np.sqrt(len(values)))) if len(values) > 1 else None,
            "mda_share_positive": float((values > 0).mean()),
        })
    table = pd.DataFrame(summary).sort_values("mda_mean_drop", ascending=False)

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    table.to_csv(out / "feature_importance.csv", index=False)

    carrying = table[(table.mda_mean_drop > 0) & (table.mda_t_stat > 2.0)]
    if float(np.mean(baseline)) <= 0:
        verdict = (f"the model itself has no skill on held-out decisions (mean rank correlation "
                   f"{np.mean(baseline):+.4f}), so feature importance is measuring which input best "
                   f"explains a prediction that does not work. That is the finding: the four features "
                   f"do not jointly predict forward returns on purged holdout folds.")
    elif carrying.empty:
        verdict = ("the model has some skill but no single feature's removal degrades it "
                   "significantly, which means no one of the four is load-bearing")
    else:
        verdict = (f"{', '.join(carrying.feature)} degrade the model significantly when shuffled; "
                   f"the others do not and are candidates for removal")

    result = {"experiment": "feature_importance_v1", "queue_item": "A7",
              "framing": "diagnosis, not prediction: which of the four features carries information",
              "folds": len(folds), "embargo_weeks": EMBARGO_WEEKS,
              "holdout_rank_correlation_mean": float(np.mean(baseline)),
              "holdout_rank_correlation_share_positive": float((baseline > 0).mean()),
              "features": summary, "verdict": verdict,
              "live_trading_enabled": False, "strategy_promotion_authorized": False}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(f"folds {len(folds)}, embargo {EMBARGO_WEEKS} weeks")
    print(f"model skill on held-out decisions: mean rank correlation {np.mean(baseline):+.4f}, "
          f"positive in {(baseline > 0).mean():.0%} of folds\n")
    print(table.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nVERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
