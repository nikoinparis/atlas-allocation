#!/usr/bin/env python3
"""What is each signal actually worth?

Measures the rank information coefficient of every panel feature against the
forward sector-relative return, one decision date at a time, then tests it
against a permutation null and decomposes the Grinold-Kahn ceiling using the
breadth this project has actually measured rather than the breadth it wishes
it had.

Uses only data already on disk. No new vendor feed, no financing, no trading.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/signal_information_coefficient_audit_v1.json"
OUTPUT = ROOT / "evidence/signal_information_coefficient_audit_v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Rank correlation, implemented directly so the audit has no extra dependency."""
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    return pearson(rx, ry)


def pearson(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    denominator = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / denominator) if denominator else 0.0


def decision_ic(frame: pd.DataFrame, feature: str, label: str, minimum: int) -> float | None:
    subset = frame[[feature, label]].dropna()
    if len(subset) < minimum:
        return None
    if subset[feature].nunique() < 2 or subset[label].nunique() < 2:
        return None
    return spearman(subset[feature].to_numpy(), subset[label].to_numpy())


def main() -> int:
    config = json.loads(CONFIG.read_text())
    label = config["label"]
    minimum = int(config["method"]["minimum_names_per_decision"])
    panel = pd.read_csv(ROOT / config["panel"])
    decisions = sorted(panel.decision_at.unique())

    rng = np.random.default_rng(int(config["permutation_null"]["seed"]))
    shuffles = int(config["permutation_null"]["shuffles"])

    results = {}
    per_decision_rows = []
    for feature in config["features"]:
        ics = []
        for decision in decisions:
            frame = panel[panel.decision_at == decision]
            value = decision_ic(frame, feature, label, minimum)
            if value is None:
                continue
            ics.append(value)
            per_decision_rows.append({"feature": feature, "decision_at": decision, "ic": value,
                                      "names": int(frame[[feature, label]].dropna().shape[0])})
        ics = np.array(ics, dtype=float)
        if not len(ics):
            continue
        mean_ic = float(ics.mean())
        std_ic = float(ics.std(ddof=1)) if len(ics) > 1 else 0.0
        t_stat = float(mean_ic / (std_ic / np.sqrt(len(ics)))) if std_ic else 0.0

        # permutation null: shuffle labels inside each decision
        grouped = [panel[panel.decision_at == d][[feature, label]].dropna() for d in decisions]
        grouped = [g for g in grouped if len(g) >= minimum]
        rank_pairs = []
        for g in grouped:
            fx = pd.Series(g[feature].to_numpy()).rank().to_numpy()
            fy = pd.Series(g[label].to_numpy()).rank().to_numpy()
            rank_pairs.append((fx - fx.mean(), fy - fy.mean()))
        null_means = np.empty(shuffles)
        for index in range(shuffles):
            sample = np.empty(len(rank_pairs))
            for position, (fx, fy) in enumerate(rank_pairs):
                shuffled = rng.permutation(fy)
                denominator = np.sqrt((fx * fx).sum() * (shuffled * shuffled).sum())
                sample[position] = (fx * shuffled).sum() / denominator if denominator else 0.0
            null_means[index] = float(sample.mean())
        percentile = float((null_means < mean_ic).mean())
        two_sided_p = float((np.abs(null_means) >= abs(mean_ic)).mean())

        law = config["fundamental_law"]
        results[feature] = {
            "decisions_used": int(len(ics)),
            "mean_ic": mean_ic,
            "median_ic": float(np.median(ics)),
            "std_ic": std_ic,
            "t_statistic": t_stat,
            "ic_information_ratio": float(mean_ic / std_ic) if std_ic else 0.0,
            "share_of_decisions_positive": float((ics > 0).mean()),
            "best_decision_ic": float(ics.max()),
            "worst_decision_ic": float(ics.min()),
            "permutation_percentile": percentile,
            "permutation_two_sided_p": two_sided_p,
            "permutation_null_mean": float(null_means.mean()),
            "permutation_null_std": float(null_means.std(ddof=1)),
            "beats_permutation_null_at_5pct": bool(two_sided_p < 0.05),
            "information_ratio_published": False,
            "information_ratio_note": law["reason"],
        }

    OUTPUT.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(per_decision_rows).to_csv(OUTPUT / "ic_by_decision.csv", index=False)
    payload = {
        "experiment_id": config["experiment_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "panel_sha256": sha256(ROOT / config["panel"]),
        "decisions": [str(d)[:10] for d in decisions],
        "features": results,
        "fundamental_law": config["fundamental_law"],
        "small_sample_warning": config["small_sample_warning"],
        "any_feature_beats_null": bool(any(v["beats_permutation_null_at_5pct"] for v in results.values())),
        "live_trading_enabled": False,
    }
    (OUTPUT / "final_result.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    print(f"{'feature':<24}{'meanIC':>9}{'t':>7}{'IC_IR':>8}{'pos%':>7}{'perm_p':>9}  {'verdict'}")
    for name, r in sorted(results.items(), key=lambda kv: -kv[1]["mean_ic"]):
        verdict = "beats null" if r["beats_permutation_null_at_5pct"] else "indistinguishable from noise"
        print(f"  {name:<22}{r['mean_ic']:>9.4f}{r['t_statistic']:>7.2f}{r['ic_information_ratio']:>8.2f}"
              f"{100*r['share_of_decisions_positive']:>6.0f}%{r['permutation_two_sided_p']:>9.4f}  {verdict}")
    print()
    print("No information ratio is published.")
    print(f"  {config['fundamental_law']['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
