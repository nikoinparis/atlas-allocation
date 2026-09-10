#!/usr/bin/env python3
"""Atlas Offensive R2B — Exposure-level re-derivation (alpha amplitude + panic floor).

Three locked arms per docs/research/atlas_offensive/run2b_preregistration.md:
  A: full alpha curve on Base P (direct construction, no wrapper clip)
  B: alpha-analog on Base O (60/40 SPY/QQQ vacuum base)
  C: deep-panic offense floor on both bases (labeled intelligent beta)
plus shuffled-R2A null batteries, walk-forward selection honesty check,
2x measured-cost stress, decade and beta/alpha decompositions.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for sub in ("", "atlas_offensive_run02", "moonshot1_discovery", "frontier2_overlays", "confirm1_alpha_pbi"):
    p = str(SCRIPTS_DIR / sub) if sub else str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)

from r02_lib import (  # noqa: E402
    DEV_LAST_DECISION, R02Machinery, core_metrics, dev_window, load_cost_vector,
    per_instrument_path,
)
from path1_path3_research_utils import DATA, normalize_to_cash  # noqa: E402
from confirm_candidates import load_r2a_leadership  # noqa: E402
from moonshot_models import r2a_scale_with_alpha  # noqa: E402
from production_allocator import production_modifier  # noqa: E402
from allocator_checkpoint_wrapper import exact_rebuild_tolerance_ok  # noqa: E402

OUT = DATA / "research" / "atlas_offensive_run2b"
SEED = 20260723
ALPHAS = [0.08, 0.16, 0.24, 0.32, 0.40, 0.48, 0.64, 0.80]
FLOORS_P = [None, 0.20, 0.30, 0.40]
FLOORS_O = [0.20, 0.35, 0.50]
N_NULLS = 50
WF_FIRST = 208
WF_EVERY = 26
DECADES = [("2005-2009", "2005-01-01", "2009-12-31"), ("2010-2019", "2010-01-01", "2019-12-31"),
           ("2020-2025", "2020-01-01", "2025-12-31")]
STRESS = [("gfc_2008", "2007-10-01", "2009-03-31"), ("whipsaw_2011", "2011-05-01", "2011-12-31")]

BASE_O_EXPOSURE = {"calm_trend": 1.00, "neutral_mixed": 1.00, "recovery_confirmed": 1.00,
                   "recovery_fragile": 0.80, "stressed_panic": 0.20}


def base_p_weights(mach: R02Machinery, scale: pd.Series) -> pd.DataFrame:
    w = mach.base_weights.copy()
    w[mach.offense_cols] = w[mach.offense_cols].mul(scale.reindex(w.index).fillna(1.0), axis=0)
    return normalize_to_cash(w)


def base_o_weights(mach: R02Machinery, exposure: pd.Series) -> pd.DataFrame:
    e = exposure.clip(0.0, 1.0)
    w = pd.DataFrame(0.0, index=mach.index, columns=["SPY", "QQQ", "BIL"])
    w["SPY"] = 0.6 * e
    w["QQQ"] = 0.4 * e
    w["BIL"] = 1.0 - e
    return w


def base_o_exposure(mach: R02Machinery, q: pd.Series, alpha: float) -> pd.Series:
    e = mach.states.map(BASE_O_EXPOSURE).astype(float)
    if alpha > 0:
        m = (1.0 + alpha * q).clip(0.5, 1.5)
        non_sp = mach.states != "stressed_panic"
        e[non_sp] = (e[non_sp] * m[non_sp]).clip(upper=1.0)
    return e


def floor_p_weights(mach: R02Machinery, w008: pd.DataFrame, floor: float) -> pd.DataFrame:
    w = w008.copy()
    dom = (mach.states == "stressed_panic") & mach.latched
    for d in mach.index[dom]:
        o = float(w.loc[d, mach.offense_cols].sum())
        if o >= floor or o <= 1e-9:
            continue
        row = w.loc[d].copy()
        non_off = [c for c in w.columns if c not in mach.offense_cols]
        row[mach.offense_cols] = row[mach.offense_cols] * (floor / o)
        other = float(w.loc[d, non_off].sum())
        if other > 1e-9:
            row[non_off] = row[non_off] * ((1.0 - floor) / other)
        w.loc[d] = row
    return w


def window_return(path: pd.DataFrame, start: str, end: str) -> float:
    p = dev_window(path)
    net = pd.Series(p["net_return"].values, index=p["Date"])
    seg = net.loc[start:end]
    return float((1.0 + seg).prod() - 1.0) if len(seg) else np.nan


def decade_cagrs(path: pd.DataFrame) -> dict:
    p = dev_window(path)
    net = pd.Series(p["net_return"].values, index=p["Date"])
    out = {}
    for label, s, e in DECADES:
        seg = net.loc[s:e].dropna()
        out[f"cagr_{label}"] = float((1 + seg).prod() ** (52 / len(seg)) - 1) if len(seg) > 26 else np.nan
    return out


def cost_and_gross(path: pd.DataFrame) -> dict:
    p = dev_window(path)
    return {"ann_cost_drag": float(pd.to_numeric(p["cost"]).mean() * 52),
            "gross_log_growth": float(np.log1p(pd.to_numeric(p["gross_return"])).mean() * 52)}


def main() -> int:
    t0 = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    mach = R02Machinery()
    repro = mach.wrapper.compare_to_saved(mach.wrapper.run("ggg_check").path)
    if not exact_rebuild_tolerance_ok(repro):
        print("ABORT: GGG reproduction failed")
        return 1
    print(f"GGG reproduction OK (err {repro['net_return_max_abs_error']:.2e})")

    cost1x, cost2x = load_cost_vector(1.0), load_cost_vector(2.0)
    spy_next = mach.nwr["SPY"]
    r2a, lead = load_r2a_leadership(mach.index)
    q = r2a.clip(-1.0, 1.0).fillna(0.0)

    # Equivalence gate: direct construction at alpha=0.08 == production pin (10bps convention).
    flat10 = pd.Series(10.0, index=cost1x.index)
    scale008 = r2a_scale_with_alpha(r2a, lead, mach.states, 0.08)
    w008 = base_p_weights(mach, scale008)
    mine = per_instrument_path(w008, mach.nwr, flat10).set_index("Date")["net_return"]
    pin = mach.wrapper.run("pin_ref", [production_modifier(mach.wrapper)])
    pin_net = pin.path.set_index("Date")["net_return"]
    pin_net.index = pd.to_datetime(pin_net.index)
    err = float((mine - pin_net).abs().max())
    print(f"Equivalence gate: alpha=0.08 direct vs production pin err {err:.2e}")
    if err > 1e-12:
        print("ABORT: equivalence gate failed")
        return 1

    # ── Arm A: alpha curve on Base P ────────────────────────────────────────
    a_rows, p_paths, p_weights = [], {}, {}
    for a in ALPHAS:
        scale = r2a_scale_with_alpha(r2a, lead, mach.states, a)
        w = base_p_weights(mach, scale)
        p1 = per_instrument_path(w, mach.nwr, cost1x)
        p2 = per_instrument_path(w, mach.nwr, cost2x)
        m1, m2 = core_metrics(p1, spy_next), core_metrics(p2, spy_next)
        a_rows.append({"arm": "A_baseP", "alpha": a, **m1, **cost_and_gross(p1), **decade_cagrs(p1),
                       "net_cagr_2x": m2["net_cagr"], "log_growth_2x": m2["log_growth"]})
        p_paths[a], p_weights[a] = p1, w
        print(f"A alpha={a:.2f}: CAGR {m1['net_cagr']:.4%}  logG {m1['log_growth']:.4f}  "
              f"cost {cost_and_gross(p1)['ann_cost_drag']:.4%}  TO {m1['avg_oneway_turnover']:.3f}")
    arm_a = pd.DataFrame(a_rows)
    best_a_p = float(arm_a.loc[arm_a["log_growth"].idxmax(), "alpha"])
    print(f"Arm A growth-optimal alpha: {best_a_p}")

    # Walk-forward selection honesty check (Base P, log-growth objective).
    dev_idx = mach.index[mach.index <= DEV_LAST_DECISION]
    nets = {a: dev_window(p_paths[a]).set_index("Date")["net_return"].reindex(dev_idx) for a in ALPHAS}
    chosen_rows, spliced = [], pd.Series(np.nan, index=dev_idx)
    current = None
    for t in range(WF_FIRST, len(dev_idx), WF_EVERY):
        past = dev_idx[:t]
        best, best_v = None, -np.inf
        for a in ALPHAS:
            v = float(np.log1p(nets[a].loc[past].dropna()).mean())
            if v > best_v:
                best, best_v = a, v
        block = dev_idx[t:t + WF_EVERY]
        spliced.loc[block] = nets[best].loc[block]
        if current is not None and best != current:
            w_old, w_new = p_weights[current].loc[block[0]], p_weights[best].loc[block[0]]
            splice = 0.5 * float(((w_new - w_old).abs() * (cost1x.reindex(w_new.index).fillna(1.0) / 1e4)).sum())
            spliced.loc[block[0]] -= splice
        chosen_rows.append({"checkpoint": str(dev_idx[t].date()), "chosen_alpha": best})
        current = best
    wf = pd.DataFrame(chosen_rows)
    wf.to_csv(OUT / "arm_a_walkforward_selection.csv", index=False)
    sp_net = spliced.dropna()
    wf_logg = float(np.log1p(sp_net).mean() * 52)
    wf_cagr = float((1 + sp_net).prod() ** (52 / len(sp_net)) - 1)
    print(f"WF-selected path (from {sp_net.index[0].date()}): CAGR {wf_cagr:.4%}, logG {wf_logg:.4f}")
    print("WF chosen alpha counts:", wf["chosen_alpha"].value_counts().to_dict())

    # ── Arm B: alpha-analog on Base O ───────────────────────────────────────
    b_rows, o_paths = [], {}
    for a in [0.0] + ALPHAS:
        e = base_o_exposure(mach, q, a)
        w = base_o_weights(mach, e)
        p1 = per_instrument_path(w, mach.nwr, cost1x)
        p2 = per_instrument_path(w, mach.nwr, cost2x)
        m1, m2 = core_metrics(p1, spy_next), core_metrics(p2, spy_next)
        b_rows.append({"arm": "B_baseO", "alpha": a, **m1, **cost_and_gross(p1), **decade_cagrs(p1),
                       "net_cagr_2x": m2["net_cagr"], "log_growth_2x": m2["log_growth"]})
        o_paths[a] = p1
        print(f"B alpha={a:.2f}: CAGR {m1['net_cagr']:.4%}  logG {m1['log_growth']:.4f}")
    arm_b = pd.DataFrame(b_rows)
    b_nonzero = arm_b[arm_b["alpha"] > 0]
    best_a_o = float(b_nonzero.loc[b_nonzero["log_growth"].idxmax(), "alpha"])
    print(f"Arm B growth-optimal alpha: {best_a_o}")

    pd.concat([arm_a, arm_b], ignore_index=True).to_csv(OUT / "alpha_curves.csv", index=False)

    # ── Arm C: deep-panic floor (labeled beta) ──────────────────────────────
    c_rows = []
    base_p_m = core_metrics(p_paths[0.08], spy_next)
    base_o_m = core_metrics(o_paths[0.0], spy_next)
    for floor in FLOORS_P:
        if floor is None:
            path, name = p_paths[0.08], "P_floor_none"
            w = None
        else:
            w = floor_p_weights(mach, p_weights[0.08], floor)
            path = per_instrument_path(w, mach.nwr, cost1x)
            name = f"P_floor_{int(floor*100)}"
        m = core_metrics(path, spy_next)
        p2 = per_instrument_path(w, mach.nwr, cost2x) if w is not None else per_instrument_path(p_weights[0.08], mach.nwr, cost2x)
        m2 = core_metrics(p2, spy_next)
        c_rows.append({"variant": name, "base": "P", "floor": floor if floor else 0.0, **m,
                       **decade_cagrs(path),
                       "delta_cagr": m["net_cagr"] - base_p_m["net_cagr"],
                       "delta_logg": m["log_growth"] - base_p_m["log_growth"],
                       "delta_beta": m["beta_spy"] - base_p_m["beta_spy"],
                       "delta_resid_alpha": m["residual_alpha_ann"] - base_p_m["residual_alpha_ann"],
                       "net_cagr_2x": m2["net_cagr"],
                       **{f"ret_{lbl}": window_return(path, s, e) for lbl, s, e in STRESS}})
    for floor in FLOORS_O:
        e = base_o_exposure(mach, q, 0.0)
        dom = (mach.states == "stressed_panic") & mach.latched
        e[dom] = e[dom].clip(lower=floor)
        w = base_o_weights(mach, e)
        path = per_instrument_path(w, mach.nwr, cost1x)
        p2 = per_instrument_path(w, mach.nwr, cost2x)
        m, m2 = core_metrics(path, spy_next), core_metrics(p2, spy_next)
        name = f"O_floor_{int(floor*100)}" + ("_none" if floor == 0.20 else "")
        c_rows.append({"variant": name, "base": "O", "floor": floor, **m,
                       **decade_cagrs(path),
                       "delta_cagr": m["net_cagr"] - base_o_m["net_cagr"],
                       "delta_logg": m["log_growth"] - base_o_m["log_growth"],
                       "delta_beta": m["beta_spy"] - base_o_m["beta_spy"],
                       "delta_resid_alpha": m["residual_alpha_ann"] - base_o_m["residual_alpha_ann"],
                       "net_cagr_2x": m2["net_cagr"],
                       **{f"ret_{lbl}": window_return(path, s, e) for lbl, s, e in STRESS}})
        print(f"C {name}: dCAGR {m['net_cagr'] - base_o_m['net_cagr']:+.4%}")
    arm_c = pd.DataFrame(c_rows)
    arm_c.to_csv(OUT / "arm_c_floor_table.csv", index=False)
    for _, r in arm_c[arm_c["base"] == "P"].iterrows():
        print(f"C {r['variant']}: dCAGR {r['delta_cagr']:+.4%}  2008 {r['ret_gfc_2008']:+.2%}  2011 {r['ret_whipsaw_2011']:+.2%}")

    # ── Null batteries (shuffled R2A, dev-window positions only) ────────────
    dev_pos = mach.index <= DEV_LAST_DECISION
    null_res = {}
    for base_name, best_alpha, base_metric, base_ref in [
        ("P", best_a_p, "log_growth", core_metrics(p_paths[0.08], spy_next)),
        ("O", best_a_o, "log_growth", base_o_m),
    ]:
        actual_m = core_metrics(p_paths[best_a_p], spy_next) if base_name == "P" else core_metrics(o_paths[best_a_o], spy_next)
        actual = actual_m["log_growth"]
        vals = []
        for _ in range(N_NULLS):
            r2a_n = r2a.copy()
            perm = rng.permutation(r2a_n[dev_pos].to_numpy())
            r2a_n.loc[dev_pos] = perm
            if base_name == "P":
                scale = r2a_scale_with_alpha(r2a_n, lead, mach.states, best_alpha)
                w = base_p_weights(mach, scale)
            else:
                qn = r2a_n.clip(-1.0, 1.0).fillna(0.0)
                w = base_o_weights(mach, base_o_exposure(mach, qn, best_alpha))
            vals.append(core_metrics(per_instrument_path(w, mach.nwr, cost1x), spy_next)["log_growth"])
        vals = np.array(vals)
        pct = float((vals < actual).mean())
        gain = actual - base_ref["log_growth"]
        null_gain = float(vals.mean() - base_ref["log_growth"])
        null_res[base_name] = {"alpha": best_alpha, "actual_logg": actual, "null_mean_logg": float(vals.mean()),
                               "pctile": pct, "actual_gain_vs_base": gain, "null_mean_gain_vs_base": null_gain,
                               "pass_90pct": pct >= 0.90, "null_replicates_gain": bool(null_gain >= 0.5 * gain) if gain > 0 else True}
        pd.DataFrame({"null_log_growth": vals}).to_csv(OUT / f"nulls_base_{base_name}.csv", index=False)
        print(f"Nulls base {base_name} (alpha={best_alpha}): actual {actual:.4f}, null mean {vals.mean():.4f}, "
              f"pctile {pct:.0%}, actual gain {gain:+.4f}, null gain {null_gain:+.4f}")

    manifest = {"seed": SEED, "date": "2026-07-23", "ggg_repro_err": repro["net_return_max_abs_error"],
                "equivalence_err_alpha008": err,
                "growth_optimal_alpha_P": best_a_p, "growth_optimal_alpha_O": best_a_o,
                "wf_selected_cagr": wf_cagr, "wf_selected_logg": wf_logg,
                "nulls": null_res, "runtime_s": round(time.time() - t0, 1), "warnings": mach.warnings}
    (OUT / "r2b_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nR2B compute done ({time.time() - t0:.0f}s). Outputs in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
