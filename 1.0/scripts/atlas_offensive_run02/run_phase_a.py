#!/usr/bin/env python3
"""R02 Phase A — native PBI sub-state, 12 locked variants, per-episode attribution.

Also runs every variant at 2x per-instrument costs (Phase C requirement folded
in here for efficiency) and writes the 2008 replay detail.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from r02_lib import (
    OFFENSE_BASES, STOP_LEVELS, OUT_DIR, SEED, WEEKS,
    R02Machinery, core_metrics, dev_window, episode_table, load_cost_vector,
    per_instrument_path, per_state_expectancy,
)
from allocator_checkpoint_wrapper import exact_rebuild_tolerance_ok
from production_allocator import production_modifier


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mach = R02Machinery()

    # Integrity gate: wrapper must reproduce saved GGG exactly (10bps convention).
    repro = mach.wrapper.compare_to_saved(mach.wrapper.run("ggg_check").path)
    if not exact_rebuild_tolerance_ok(repro):
        print("ABORT: wrapper does not reproduce saved GGG.")
        return 1
    print(f"Exact GGG reproduction OK (err {repro['net_return_max_abs_error']:.2e})")

    cost1x = load_cost_vector(1.0)
    cost2x = load_cost_vector(2.0)
    spy_next = mach.nwr["SPY"]

    base_path_1x = per_instrument_path(mach.base_weights, mach.nwr, cost1x)
    base_path_2x = per_instrument_path(mach.base_weights, mach.nwr, cost2x)
    base_m = core_metrics(base_path_1x, spy_next)
    base_m2x = core_metrics(base_path_2x, spy_next)

    pin_res = mach.wrapper.run("production_pin", [production_modifier(mach.wrapper)])
    pin_path = per_instrument_path(pin_res.weights, mach.nwr, cost1x)
    pin_m = core_metrics(pin_path, spy_next)

    ref_rows = [
        {"variant": "ggg_base_1x", **base_m, **per_state_expectancy(base_path_1x, mach.states, mach.fire_mask)},
        {"variant": "ggg_base_2x", **base_m2x},
        {"variant": "production_pin_ref_1x", **pin_m, **per_state_expectancy(pin_path, mach.states, mach.fire_mask)},
    ]
    pd.DataFrame(ref_rows).to_csv(OUT_DIR / "base_and_pin_metrics.csv", index=False)
    dev_window(base_path_1x).to_csv(OUT_DIR / "path_ggg_base_1x.csv", index=False)

    print(f"Base (dev, per-instrument costs): CAGR {base_m['net_cagr']:.4%}  logG {base_m['log_growth']:.4f}")
    print(f"Pin  (dev, reference):            CAGR {pin_m['net_cagr']:.4%}")
    print(f"Episodes: {[e['label'] for e in mach.episodes]}")

    var_rows, ep_frames, stop_frames = [], [], []
    detail = {}
    for B in OFFENSE_BASES:
        for S in STOP_LEVELS:
            name = f"pbi_native_B{int(B*100)}_S{int(S*100)}"
            res1 = mach.run_variant(B, S, cost1x)
            res2 = mach.run_variant(B, S, cost2x)
            m1 = core_metrics(res1["path"], spy_next)
            m2 = core_metrics(res2["path"], spy_next)
            ep = episode_table(mach, res1["path"], base_path_1x)
            ep.insert(0, "variant", name)
            ep_frames.append(ep)
            for s in res1["stop_log"]:
                stop_frames.append({"variant": name, **s})
            worst_contrib = float(ep["contribution_total"].min()) if not ep.empty else 0.0
            d_cagr = m1["net_cagr"] - base_m["net_cagr"]
            contained = worst_contrib >= -2.0 * max(d_cagr, 0.0) if d_cagr > 0 else worst_contrib >= 0.0
            row = {"variant": name, "offense_base": B, "stop": S,
                   "n_active_fires": len(res1["active_fires"]), "n_stops": len(res1["stop_log"]),
                   **m1,
                   "delta_cagr_vs_base": d_cagr,
                   "delta_logg_vs_base": m1["log_growth"] - base_m["log_growth"],
                   "mean_episode_capture_pp": float(ep["capture_pp_ann"].mean()),
                   "worst_episode_contribution": worst_contrib,
                   "containment_pass": bool(contained),
                   "cagr_2x": m2["net_cagr"], "delta_cagr_vs_base_2x": m2["net_cagr"] - base_m2x["net_cagr"],
                   "logg_2x": m2["log_growth"], "delta_logg_vs_base_2x": m2["log_growth"] - base_m2x["log_growth"],
                   **per_state_expectancy(res1["path"], mach.states, mach.fire_mask)}
            var_rows.append(row)
            detail[name] = res1
            print(f"{name}: dCAGR {d_cagr:+.4%}  capture {row['mean_episode_capture_pp']:+.2f}pp  "
                  f"stops {len(res1['stop_log'])}  contained {contained}  dCAGR2x {row['delta_cagr_vs_base_2x']:+.4%}")

    variants = pd.DataFrame(var_rows)
    variants.to_csv(OUT_DIR / "phase_a_variant_table.csv", index=False)
    pd.concat(ep_frames, ignore_index=True).to_csv(OUT_DIR / "phase_a_episode_attribution.csv", index=False)
    pd.DataFrame(stop_frames).to_csv(OUT_DIR / "phase_a_stop_log.csv", index=False)

    # Best variant: highest dev net CAGR subject to containment (pre-registered).
    ok = variants[variants["containment_pass"]]
    pool = ok if not ok.empty else variants
    best = pool.sort_values(["net_cagr", "log_growth"], ascending=False).iloc[0]
    best_name = str(best["variant"])
    print(f"\nBest variant: {best_name} (containment pool: {len(ok)}/12)")

    best_res = detail[best_name]
    dev_window(best_res["path"]).to_csv(OUT_DIR / f"path_{best_name}.csv", index=False)

    # 2008 replay: weekly detail across both 2008 episodes for the best variant.
    v = dev_window(best_res["path"]).set_index("Date")
    b = dev_window(base_path_1x).set_index("Date")
    rows = []
    for ep in mach.episodes:
        if not ep["label"].startswith(("2008", "2009")):
            continue
        for d in v.loc[ep["entry"]:ep["window_end"]].index:
            rows.append({"episode": ep["label"], "date": str(d.date()),
                         "state": mach.states.get(d, ""),
                         "fired": bool(mach.fire_mask.get(d, False)),
                         "active": d in best_res["active_fires"],
                         "grade": "3of3" if bool(mach.grade3.get(d, False)) else ("2of3" if bool(mach.fire_mask.get(d, False)) else ""),
                         "offense_share_base": float(mach.offense_share.get(d, np.nan)),
                         "offense_share_variant": float(best_res["weights"].loc[d, mach.offense_cols].sum()),
                         "variant_net": float(v.loc[d, "net_return"]), "base_net": float(b.loc[d, "net_return"]),
                         "spy_next": float(mach.nwr["SPY"].get(d, np.nan))})
    pd.DataFrame(rows).to_csv(OUT_DIR / "phase_a_2008_replay.csv", index=False)

    manifest = {"phase": "A", "seed": SEED, "date": "2026-07-21",
                "ggg_repro_err": repro["net_return_max_abs_error"],
                "base_dev_cagr": base_m["net_cagr"], "base_dev_logg": base_m["log_growth"],
                "pin_dev_cagr": pin_m["net_cagr"],
                "best_variant": best_name,
                "episodes": [e["label"] for e in mach.episodes],
                "runtime_s": round(time.time() - t0, 1), "warnings": mach.warnings}
    (OUT_DIR / "phase_a_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nPhase A done ({time.time() - t0:.0f}s). Outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
