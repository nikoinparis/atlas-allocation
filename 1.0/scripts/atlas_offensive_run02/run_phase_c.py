#!/usr/bin/env python3
"""R02 Phase C — null battery for the best Phase A variant (pre-registered).

200 random-placement nulls (no-stop expression, SP-week domain), inverted-
confirmation control, episode-blocked bootstrap. 2x-cost stress already runs
inside Phase A; its result is summarized here from the variant table.
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from r02_lib import (
    GRADE_RATIO, OUT_DIR, SEED, DEV_LAST_DECISION,
    R02Machinery, core_metrics, episode_table, load_cost_vector, per_instrument_path,
)

N_NULLS = 200
N_BOOT = 10_000


def weights_for_fires(mach: R02Machinery, dates_2of3: list, dates_3of3: list, B: float) -> pd.DataFrame:
    w = mach.base_weights.copy()
    for d, target in [(d, B * GRADE_RATIO) for d in dates_2of3] + [(d, B) for d in dates_3of3]:
        o = float(mach.offense_share.loc[d])
        t = max(target, o)
        if o <= 1e-9 or t >= 0.999:
            continue
        row = w.loc[d].copy()
        non_off = [c for c in w.columns if c not in mach.offense_cols]
        row[mach.offense_cols] = row[mach.offense_cols] * (t / o)
        other = float(w.loc[d, non_off].sum())
        if other > 1e-9:
            row[non_off] = row[non_off] * ((1.0 - t) / other)
        w.loc[d] = row
    return w


def main() -> int:
    t0 = time.time()
    mach = R02Machinery()
    rng = np.random.default_rng(SEED)
    cost1x = load_cost_vector(1.0)
    spy_next = mach.nwr["SPY"]

    variants = pd.read_csv(OUT_DIR / "phase_a_variant_table.csv")
    ok = variants[variants["containment_pass"]]
    pool = ok if not ok.empty else variants
    best = pool.sort_values(["net_cagr", "log_growth"], ascending=False).iloc[0]
    B = float(best["offense_base"])
    print(f"Best variant: {best['variant']} (B={B:.2f}) — null battery on its no-stop expression")

    base_path = per_instrument_path(mach.base_weights, mach.nwr, cost1x)
    base_cagr = core_metrics(base_path, spy_next)["net_cagr"]

    # Actual no-stop expression of the best offense base.
    fires_2 = [d for d in mach.index[mach.fire_mask] if not mach.grade3.loc[d]]
    fires_3 = [d for d in mach.index[mach.fire_mask] if mach.grade3.loc[d]]
    actual_w = weights_for_fires(mach, fires_2, fires_3, B)
    actual_cagr = core_metrics(per_instrument_path(actual_w, mach.nwr, cost1x), spy_next)["net_cagr"]
    actual_delta = actual_cagr - base_cagr
    print(f"Actual no-stop dCAGR: {actual_delta:+.4%}")

    # Placement nulls: same fire count and grade mix, uniform over dev SP weeks.
    sp_dev = [d for d in mach.index[(mach.states == "stressed_panic")] if d <= DEV_LAST_DECISION]
    n2, n3 = len(fires_2), len(fires_3)
    null_deltas = []
    for i in range(N_NULLS):
        pick = rng.choice(len(sp_dev), size=n2 + n3, replace=False)
        dates = [sp_dev[j] for j in pick]
        w = weights_for_fires(mach, dates[:n2], dates[n2:], B)
        c = core_metrics(per_instrument_path(w, mach.nwr, cost1x), spy_next)["net_cagr"]
        null_deltas.append(c - base_cagr)
    null_deltas = np.array(null_deltas)
    pctile = float((null_deltas < actual_delta).mean())
    pd.DataFrame({"null_delta_cagr": null_deltas}).to_csv(OUT_DIR / "phase_c_null_distribution.csv", index=False)
    print(f"Placement nulls: mean {null_deltas.mean():+.4%}, actual pctile {pctile:.1%} (bar >=90%)")

    # Inverted-confirmation control.
    known = mach.pbi["confirm_count"].notna()
    count_neg = (3.0 - mach.pbi["confirm_count"]).where(known)
    dom = (mach.states == "stressed_panic") & mach.latched & known & (mach.index <= DEV_LAST_DECISION)
    inv2 = [d for d in mach.index[dom & (count_neg >= 2) & (count_neg < 3)]]
    inv3 = [d for d in mach.index[dom & (count_neg >= 3)]]
    inv_w = weights_for_fires(mach, inv2, inv3, B)
    inv_cagr = core_metrics(per_instrument_path(inv_w, mach.nwr, cost1x), spy_next)["net_cagr"]
    inv_delta = inv_cagr - base_cagr
    print(f"Inverted control: {len(inv2)+len(inv3)} fires, dCAGR {inv_delta:+.4%} (must hurt / be below actual)")

    # Episode-blocked bootstrap of the best variant's capture estimate.
    ep = pd.read_csv(OUT_DIR / "phase_a_episode_attribution.csv")
    caps = ep[ep["variant"] == best["variant"]]["capture_pp_ann"].to_numpy()
    boots = np.array([caps[rng.integers(0, len(caps), len(caps))].mean() for _ in range(N_BOOT)])
    ci = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)))
    print(f"Episode bootstrap mean capture: {caps.mean():+.2f}pp, 95% CI [{ci[0]:+.2f}, {ci[1]:+.2f}]")

    summary = {
        "best_variant": str(best["variant"]), "offense_base": B,
        "actual_no_stop_delta_cagr": actual_delta,
        "null_mean_delta_cagr": float(null_deltas.mean()),
        "null_90th_pct_value": float(np.percentile(null_deltas, 90)),
        "actual_percentile": pctile, "null_bar_pass": pctile >= 0.90,
        "inverted_n_fires": len(inv2) + len(inv3), "inverted_delta_cagr": inv_delta,
        "inverted_hurts": inv_delta < 0, "inverted_below_actual": inv_delta < actual_delta,
        "capture_mean_pp": float(caps.mean()), "capture_ci_lo": ci[0], "capture_ci_hi": ci[1],
        "two_x_delta_cagr": float(best["delta_cagr_vs_base_2x"]),
        "two_x_delta_logg": float(best["delta_logg_vs_base_2x"]),
        "two_x_pass": bool(best["delta_cagr_vs_base_2x"] > 0 and best["delta_logg_vs_base_2x"] > 0),
        "n_nulls": N_NULLS, "n_boot": N_BOOT, "seed": SEED,
        "runtime_s": round(time.time() - t0, 1),
    }
    (OUT_DIR / "phase_c_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"Phase C done ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
