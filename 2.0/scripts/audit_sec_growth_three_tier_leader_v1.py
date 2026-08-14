#!/usr/bin/env python3
"""Post-selection robustness diagnostics for the three-tier provisional leader."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/sec_growth_three_tier_cap_frequency_v1"
LEADER = EVIDENCE / "path__base__breadth3_concentration60_vol_60__weekly__50bps.csv"
CONTROL = EVIDENCE / "path__base__binary_10_40_control__monthly__50bps.csv"
OUTPUT = EVIDENCE / "leader_robustness.json"
SEED = 20260814


def read_path(path: Path) -> pd.Series:
    frame = pd.read_csv(path, parse_dates=["Date"]).set_index("Date")
    return pd.to_numeric(frame["net_return"], errors="raise")


def block_bootstrap(delta: np.ndarray, block: int, draws: int, seed: int) -> dict[str, float | int]:
    rng = np.random.default_rng(seed)
    length = len(delta)
    starts = np.arange(max(1, length - block + 1))
    estimates = np.empty(draws)
    blocks_needed = int(np.ceil(length / block))
    for draw in range(draws):
        sampled_starts = rng.choice(starts, size=blocks_needed, replace=True)
        sample = np.concatenate([delta[start:start + block] for start in sampled_starts])[:length]
        estimates[draw] = sample.mean() * 52.0
    return {
        "observations": length,
        "block_weeks": block,
        "draws": draws,
        "annualized_arithmetic_return_difference": float(delta.mean() * 52.0),
        "ci_2_5": float(np.quantile(estimates, 0.025)),
        "median": float(np.quantile(estimates, 0.50)),
        "ci_97_5": float(np.quantile(estimates, 0.975)),
        "probability_positive": float((estimates > 0.0).mean()),
    }


def main() -> int:
    aligned = pd.concat([read_path(LEADER).rename("leader"), read_path(CONTROL).rename("control")], axis=1, join="inner").dropna()
    end = aligned.index.max()
    samples = {
        "holdout": aligned.loc[aligned.index >= pd.Timestamp("2023-08-11")],
        "trailing_2y": aligned.loc[aligned.index >= end - pd.DateOffset(years=2)],
        "trailing_1y": aligned.loc[aligned.index >= end - pd.DateOffset(years=1)],
    }
    bootstraps: list[dict[str, object]] = []
    rolling: dict[str, object] = {}
    for window, sample in samples.items():
        delta = (sample["leader"] - sample["control"]).to_numpy()
        for block in (4, 13):
            result = block_bootstrap(delta, block, 5000, SEED + block + len(delta))
            result["window"] = window
            bootstraps.append(result)
        if len(sample) >= 26:
            leader_rolling = (1.0 + sample["leader"]).rolling(26).apply(np.prod, raw=True) - 1.0
            control_rolling = (1.0 + sample["control"]).rolling(26).apply(np.prod, raw=True) - 1.0
            difference = (leader_rolling - control_rolling).dropna()
            rolling[window] = {
                "rolling_26w_windows": len(difference),
                "outperformance_share": float((difference > 0.0).mean()),
                "median_return_difference": float(difference.median()),
                "worst_return_difference": float(difference.min()),
                "best_return_difference": float(difference.max()),
            }
    result = {
        "leader": "breadth3_concentration60_vol_60__weekly__50bps",
        "control": "binary_10_40_control__monthly__50bps",
        "post_selection_diagnostic_only": True,
        "paired_block_bootstrap": bootstraps,
        "rolling_diagnostics": rolling,
        "promotion_authorized": False,
    }
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    pd.DataFrame(bootstraps).to_csv(EVIDENCE / "leader_paired_bootstrap.csv", index=False)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
