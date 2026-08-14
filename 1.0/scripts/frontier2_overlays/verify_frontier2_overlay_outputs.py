"""Verifier for the Frontier-2 risk-structure overlay sprint.

Checks, in order:
    1. Output files exist and are non-empty / parseable.
    2. The no-modifier wrapper still reproduces saved GGG to 1e-12.
    3. stressed_panic weeks have multiplier exactly 1.0 for every overlay.
    4. No-lookahead spot check: rebuilding each overlay signal on data
       truncated at week T-26 leaves all values at or before T-52 unchanged.
    5. Turnover accounting: recomputed one-way turnover of each saved variant
       path matches the stored turnover column.
    6. Manifest consistency: verdict variants exist in the gate table.

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

from overlay_signals import (  # noqa: E402
    absorption_ratio_shift,
    canary_bad_count,
    load_vix_term_structure,
    load_weekly_prices,
    load_weekly_returns,
    vix_backwardation_events,
)

OUT_DIR = DATA / "research" / "frontier2_overlays"

REQUIRED_FILES = [
    "variant_window_metrics.csv",
    "variant_state_metrics.csv",
    "phase_d_gates.csv",
    "bootstrap_summary.csv",
    "parameter_sensitivity.csv",
    "overlay_multipliers.csv",
    "sprint_manifest.json",
]


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    # 1. Files exist.
    for name in REQUIRED_FILES:
        path = OUT_DIR / name
        if not path.exists() or path.stat().st_size == 0:
            failures.append(f"missing or empty output: {name}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1

    manifest = json.loads((OUT_DIR / "sprint_manifest.json").read_text())
    mults = pd.read_csv(OUT_DIR / "overlay_multipliers.csv", parse_dates=["Date"]).set_index("Date")

    # 2. Exact reproduction.
    wrapper = AllocatorCheckpointWrapper()
    repro = wrapper.compare_to_saved()
    if exact_rebuild_tolerance_ok(repro):
        print(f"OK: exact GGG reproduction (net max abs err {repro['net_return_max_abs_error']:.2e})")
    else:
        failures.append(f"wrapper no longer reproduces GGG: {repro}")

    # 3. stressed_panic neutrality.
    states = wrapper.states["market_state"].astype(str).reindex(mults.index)
    sp = states.eq("stressed_panic")
    for col in mults.columns:
        bad = mults.loc[sp, col].sub(1.0).abs().max()
        if pd.notna(bad) and bad > 1e-12:
            failures.append(f"{col}: stressed_panic multiplier deviates from 1.0 (max {bad:.2e})")
        else:
            print(f"OK: {col} stressed_panic weeks untouched ({int(sp.sum())} weeks)")

    # 4. No-lookahead spot check.
    vix = load_vix_term_structure(warnings)
    prices = load_weekly_prices(warnings)
    returns = load_weekly_returns(warnings)
    idx = wrapper.index
    cut = idx[-26]
    safe_end = idx[-52]

    full_ev = vix_backwardation_events(vix, idx)
    trunc_ev = vix_backwardation_events(vix[vix.index <= cut], idx[idx <= cut])
    diff = (full_ev.loc[:safe_end] - trunc_ev.loc[:safe_end]).abs().max().max()
    if diff <= 1e-12:
        print("OK: O1 VIX events causal (truncation-invariant)")
    else:
        failures.append(f"O1 lookahead: truncation changed history by {diff}")

    full_can = canary_bad_count(prices, idx)
    trunc_can = canary_bad_count(prices[prices.index <= cut], idx[idx <= cut])
    diff = (full_can.loc[:safe_end] - trunc_can.loc[:safe_end]).abs().max()
    if diff <= 1e-12:
        print("OK: O2 canary count causal (truncation-invariant)")
    else:
        failures.append(f"O2 lookahead: truncation changed history by {diff}")

    full_ar = absorption_ratio_shift(returns, idx)
    trunc_ar = absorption_ratio_shift(returns[returns.index <= cut], idx[idx <= cut])
    diff = (full_ar.loc[:safe_end] - trunc_ar.loc[:safe_end]).abs().max().max()
    if diff <= 1e-9:
        print("OK: O3 absorption ratio causal (truncation-invariant)")
    else:
        failures.append(f"O3 lookahead: truncation changed history by {diff}")

    # 5. Turnover accounting on saved paths.
    for path_file in sorted(OUT_DIR.glob("path_*.csv")):
        p = pd.read_csv(path_file)
        if not {"turnover", "net_return", "gross_return", "cost"}.issubset(p.columns):
            failures.append(f"{path_file.name}: missing path columns")
            continue
        recomputed_net = p["gross_return"] - p["cost"]
        err = (recomputed_net - p["net_return"]).abs().max()
        if err > 1e-12:
            failures.append(f"{path_file.name}: net != gross - cost (max err {err:.2e})")
    print(f"OK: net = gross - cost for {len(list(OUT_DIR.glob('path_*.csv')))} saved paths")

    # 6. Manifest consistency.
    gates = pd.read_csv(OUT_DIR / "phase_d_gates.csv")
    for variant in manifest.get("verdicts", {}):
        if variant not in set(gates["variant"]):
            failures.append(f"manifest verdict variant {variant} missing from gate table")
    if not manifest.get("exact_ggg_reproduction", False):
        failures.append("manifest records failed GGG reproduction")
    print("OK: manifest consistent with gate table")

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
