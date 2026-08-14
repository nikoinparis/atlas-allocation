"""Verifier for the moonshot discovery sprint outputs.

Checks:
    1. Required output files exist and parse.
    2. No-modifier wrapper still reproduces saved GGG to 1e-12.
    3. Multiplier domain constraints:
       - M1 (pbi) multipliers are >= 1.0 everywhere and > 1.0 ONLY inside
         stressed_panic weeks.
       - M2/M3 multipliers are exactly 1.0 inside stressed_panic weeks.
    4. Truncation invariance (no lookahead): rebuilding the feature panel,
       PBI composite, latched context, and kNN predictions on data truncated
       26 weeks early leaves all values 52+ weeks before the cut unchanged.
    5. Path accounting: net = gross - cost on every saved path.
    6. Manifest sanity: null percentiles in [0, 1], run counts recorded.

Exit code 0 = all checks pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, exact_rebuild_tolerance_ok  # noqa: E402
from path1_path3_research_utils import DATA  # noqa: E402

from moonshot_features import (  # noqa: E402
    build_feature_panel,
    expanding_standardize,
    offense_excess_forward,
    panic_improvement_composite,
)
from moonshot_models import knn_analog_predictions  # noqa: E402

OUT_DIR = DATA / "research" / "moonshot1_discovery"

REQUIRED_FILES = [
    "episode_opportunity_map.csv",
    "episode_label_summary.csv",
    "variant_window_metrics.csv",
    "phase_d_gates.csv",
    "bootstrap_summary.csv",
    "candidate_multipliers.csv",
    "m1_null_distribution.csv",
    "m2_null_distribution.csv",
    "m3_null_distribution.csv",
    "m2_ablations.csv",
    "m4_adaptive_alpha.csv",
    "f1_alpha_curve_gates.csv",
    "f3_m1_latched_nulls.csv",
    "f5_shuffled_r2a_nulls.csv",
    "sprint_manifest.json",
    "followups_manifest.json",
]


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    for name in REQUIRED_FILES:
        p = OUT_DIR / name
        if not p.exists() or p.stat().st_size == 0:
            failures.append(f"missing or empty: {name}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"OK: all {len(REQUIRED_FILES)} required outputs present")

    wrapper = AllocatorCheckpointWrapper()
    repro = wrapper.compare_to_saved()
    if exact_rebuild_tolerance_ok(repro):
        print(f"OK: exact GGG reproduction (err {repro['net_return_max_abs_error']:.2e})")
    else:
        failures.append(f"wrapper no longer reproduces GGG: {repro}")

    states = wrapper.states["market_state"].astype(str)
    mults = pd.read_csv(OUT_DIR / "candidate_multipliers.csv", parse_dates=["Date"]).set_index("Date")
    st = states.reindex(mults.index)
    sp = st.eq("stressed_panic")

    m1 = mults["m1_pbi"]
    if (m1 < 1.0 - 1e-12).any():
        failures.append("m1_pbi multiplier drops below 1.0")
    elif ((m1 > 1.0 + 1e-12) & ~sp).any():
        failures.append("m1_pbi fires outside stressed_panic")
    else:
        print(f"OK: m1_pbi >= 1.0 and fires only inside stressed_panic ({int((m1 > 1).sum())} weeks)")

    for col in ("m2_knn", "m3_kmeans"):
        dev = mults.loc[sp, col].sub(1.0).abs().max()
        if pd.notna(dev) and dev > 1e-12:
            failures.append(f"{col}: stressed_panic multiplier deviates from 1.0 (max {dev:.2e})")
        else:
            print(f"OK: {col} neutral in stressed_panic")

    # Truncation invariance.
    idx = wrapper.index
    cut = idx[-26]
    safe_end = idx[-52]
    warn2: list[str] = []
    full_f = build_feature_panel(idx, warn2)
    trunc_f = build_feature_panel(idx[idx <= cut], warn2)
    diff = (full_f.loc[:safe_end] - trunc_f.loc[:safe_end]).abs().max().max()
    if diff <= 1e-9:
        print("OK: feature panel truncation-invariant")
    else:
        failures.append(f"feature panel lookahead: {diff}")

    full_pbi = panic_improvement_composite(full_f)["confirm_count"]
    trunc_pbi = panic_improvement_composite(trunc_f)["confirm_count"]
    diff = (full_pbi.loc[:safe_end] - trunc_pbi.loc[:safe_end]).abs().max()
    if diff <= 1e-12:
        print("OK: PBI composite truncation-invariant")
    else:
        failures.append(f"PBI composite lookahead: {diff}")

    full_latch = (full_f["market_drawdown"].rolling(13, min_periods=1).min() <= -0.10).astype(float)
    trunc_latch = (trunc_f["market_drawdown"].rolling(13, min_periods=1).min() <= -0.10).astype(float)
    diff = (full_latch.loc[:safe_end] - trunc_latch.loc[:safe_end]).abs().max()
    if diff <= 1e-12:
        print("OK: latched deep-DD context truncation-invariant")
    else:
        failures.append(f"latched context lookahead: {diff}")

    # kNN truncation invariance (embargo means preds well before the cut are fixed).
    full_z = expanding_standardize(full_f)
    trunc_z = expanding_standardize(trunc_f)
    full_y = offense_excess_forward(wrapper.final_weights, idx, warn2)
    trunc_y = offense_excess_forward(wrapper.final_weights, idx[idx <= cut], warn2)
    full_pred = knn_analog_predictions(full_z, full_y)
    trunc_pred = knn_analog_predictions(trunc_z, trunc_y)
    both = pd.concat([full_pred.rename("f"), trunc_pred.rename("t")], axis=1).loc[:safe_end].dropna()
    diff = (both["f"] - both["t"]).abs().max() if not both.empty else 0.0
    if diff <= 1e-9:
        print(f"OK: kNN predictions truncation-invariant ({len(both)} compared)")
    else:
        failures.append(f"kNN lookahead: {diff}")

    # Path accounting.
    n_paths = 0
    for pf in sorted(OUT_DIR.glob("path_*.csv")):
        p = pd.read_csv(pf)
        err = ((p["gross_return"] - p["cost"]) - p["net_return"]).abs().max()
        if err > 1e-12:
            failures.append(f"{pf.name}: net != gross - cost")
        n_paths += 1
    print(f"OK: accounting verified on {n_paths} saved paths")

    man = json.loads((OUT_DIR / "sprint_manifest.json").read_text())
    fol = json.loads((OUT_DIR / "followups_manifest.json").read_text())
    for key, src in (("m1_null_percentile", man), ("m2_null_percentile", man),
                     ("m3_null_percentile", man), ("f3_null_percentile", fol), ("f5_percentile", fol)):
        v = src.get(key)
        if v is None or not (0.0 <= float(v) <= 1.0):
            failures.append(f"manifest {key} invalid: {v}")
    if man.get("total_wrapper_runs", 0) < 400:
        warnings.append("manifest wrapper-run count unexpectedly low")
    print("OK: manifests sane")

    for w in warnings:
        print(f"WARN: {w}")
    if failures:
        print("\nVERIFICATION FAILED:")
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("\nALL VERIFICATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
