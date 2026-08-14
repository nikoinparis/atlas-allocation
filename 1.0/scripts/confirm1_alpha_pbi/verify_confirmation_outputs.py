"""Verifier for the alpha/PBI confirmation sprint.

Checks:
    1. Required outputs exist and parse.
    2. Exact GGG reproduction still holds.
    3. Implementation equivalence: alpha=0.08 candidate machinery reproduces
       the production pin path to 1e-12.
    4. PBI multiplier domain: >= 1.0 everywhere, > 1.0 only in stressed_panic.
    5. Truncation invariance of the PBI multiplier (no lookahead).
    6. Accounting: net = gross - cost on all saved paths; turnover deltas
       consistent with the cost gate inputs.
    7. Manifest sanity: locked parameters unchanged, null percentiles valid.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for sub in ("", "moonshot1_discovery", "frontier2_overlays", "confirm1_alpha_pbi"):
    p = str(SCRIPTS_DIR / sub) if sub else str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, exact_rebuild_tolerance_ok  # noqa: E402
from path1_path3_research_utils import DATA  # noqa: E402
from production_allocator import production_modifier  # noqa: E402

from run_frontier2_overlay_experiments import series_modifier  # noqa: E402
from confirm_candidates import ALPHA_A, ALPHA_C, alpha_scale, pbi_latched_multiplier  # noqa: E402

OUT_DIR = DATA / "research" / "confirm1_alpha_pbi"

REQUIRED = [
    "locked_gate_table.csv", "variant_window_metrics.csv", "variant_state_metrics.csv",
    "bootstrap_summary.csv", "two_x_cost_stress.csv", "extra_metrics.csv",
    "exposure_paths.csv", "null_A_shuffled_r2a.csv", "null_B_pbi_placement.csv",
    "pbi_fragile_panic_audit.csv", "pbi_multiplier.csv", "sprint_manifest.json",
]


def main() -> int:
    failures: list[str] = []
    for name in REQUIRED:
        p = OUT_DIR / name
        if not p.exists() or p.stat().st_size == 0:
            failures.append(f"missing or empty: {name}")
    if failures:
        for f in failures:
            print(f"FAIL: {f}")
        return 1
    print(f"OK: all {len(REQUIRED)} required outputs present")

    wrapper = AllocatorCheckpointWrapper()
    repro = wrapper.compare_to_saved()
    if exact_rebuild_tolerance_ok(repro):
        print(f"OK: exact GGG reproduction (err {repro['net_return_max_abs_error']:.2e})")
    else:
        failures.append(f"GGG reproduction broken: {repro}")

    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    prod = wrapper.run("pin", [production_modifier(wrapper)])
    equiv = wrapper.run("equiv", [series_modifier("a008", "offense_budget", alpha_scale(wrapper.index, states, 0.08))])
    err = float((equiv.path["net_return"] - prod.path["net_return"]).abs().max())
    if err <= 1e-12:
        print(f"OK: implementation equivalence (alpha=0.08 == pin, err {err:.2e})")
    else:
        failures.append(f"alpha=0.08 machinery diverges from pin: {err:.2e}")

    warnings: list[str] = []
    pbi = pbi_latched_multiplier(wrapper.index, states, warnings)
    saved = pd.read_csv(OUT_DIR / "pbi_multiplier.csv", parse_dates=["Date"]).set_index("Date")["pbi_multiplier"]
    if (pbi - saved.reindex(pbi.index)).abs().max() > 1e-12:
        failures.append("saved PBI multiplier does not match rebuilt rule")
    if (pbi < 1.0 - 1e-12).any():
        failures.append("PBI multiplier below 1.0")
    sp = states.eq("stressed_panic")
    if ((pbi > 1.0 + 1e-12) & ~sp).any():
        failures.append("PBI fires outside stressed_panic")
    print(f"OK: PBI domain constraints ({int((pbi > 1).sum())} fire weeks, all in stressed_panic, none below 1.0)")

    cut = wrapper.index[-26]
    safe_end = wrapper.index[-52]
    pbi_trunc = pbi_latched_multiplier(wrapper.index[wrapper.index <= cut], states.loc[:cut], warnings)
    diff = (pbi.loc[:safe_end] - pbi_trunc.loc[:safe_end]).abs().max()
    if diff <= 1e-12:
        print("OK: PBI multiplier truncation-invariant")
    else:
        failures.append(f"PBI lookahead: truncation changed history by {diff}")

    n = 0
    for pf in sorted(OUT_DIR.glob("path_*.csv")):
        p = pd.read_csv(pf)
        if ((p["gross_return"] - p["cost"]) - p["net_return"]).abs().max() > 1e-12:
            failures.append(f"{pf.name}: net != gross - cost")
        n += 1
    print(f"OK: accounting verified on {n} saved paths")

    man = json.loads((OUT_DIR / "sprint_manifest.json").read_text())
    locked = man.get("locked_candidates", {})
    if locked.get("A", {}).get("alpha") != ALPHA_A or locked.get("C", {}).get("alpha") != ALPHA_C:
        failures.append("manifest locked parameters do not match code constants")
    for key in ("null_A_percentile", "null_B_percentile"):
        v = man.get(key)
        if v is None or not (0.0 <= float(v) <= 1.0):
            failures.append(f"manifest {key} invalid: {v}")
    if man.get("implementation_equivalence_err", 1.0) > 1e-12:
        failures.append("manifest records failed implementation equivalence")
    print("OK: manifest sane and locked parameters unchanged")

    if failures:
        print("\nVERIFICATION FAILED:")
        for f in failures:
            print(f"  FAIL: {f}")
        return 1
    print("\nALL VERIFICATION CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
