"""Consolidated follow-up experiments for the moonshot discovery sprint.

Reproduces, in one deterministic script, the follow-ups that were first run
interactively (all labeled post-hoc where applicable):

    F1  alpha amplitude curve 0.08..0.48 with full Phase D gates
        (0.08..0.16 was the predeclared M4 grid; beyond 0.16 is post-hoc
        extension driven by the boundary solution of the walk-forward test)
    F2  extended-grid walk-forward adaptive alpha (checks the boundary again)
    F3  latched-context M1 (design fix: deep-DD context = 13w rolling min
        drawdown <= -10%, so confirmations arriving after the trough count)
        + 200 random-placement nulls
    F4  combined candidates: alpha x latched-M1 (state-disjoint mechanisms)
    F5  shuffled-r2a null at alpha=0.24: separates timing value from
        mechanical vol shrink (50 seeded shuffles)

Nothing here selects a promotion; outputs feed the sprint report only.
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
FRONTIER2_DIR = SCRIPTS_DIR / "frontier2_overlays"
if str(FRONTIER2_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTIER2_DIR))

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, exact_rebuild_tolerance_ok  # noqa: E402
from path1_path3_research_utils import DATA  # noqa: E402
from production_allocator import production_modifier  # noqa: E402
from production_config import OFFICIAL_HOLDOUT_START  # noqa: E402

from run_frontier2_overlay_experiments import (  # noqa: E402
    block_bootstrap_p,
    phase_d_gates,
    rolling_origin_win_rate,
    series_modifier,
    state_sharpe,
    window_metrics,
)

from moonshot_features import build_feature_panel, panic_improvement_composite  # noqa: E402
from moonshot_models import adaptive_alpha_path, r2a_scale_with_alpha  # noqa: E402

OUT_DIR = DATA / "research" / "moonshot1_discovery"
SEED = 20260707
N_SHUFFLE_NULL = 50


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    rng = np.random.default_rng(SEED)

    wrapper = AllocatorCheckpointWrapper()
    if not exact_rebuild_tolerance_ok(wrapper.compare_to_saved()):
        print("ABORT: wrapper does not reproduce saved GGG.")
        return 1
    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    prod_mod = production_modifier(wrapper)
    prod = wrapper.run("production_pin", [prod_mod])
    base_m = window_metrics(prod.path, OFFICIAL_HOLDOUT_START)
    base_sp = state_sharpe(prod.path, wrapper.states, "stressed_panic")
    prod_net = prod.path.set_index("Date")["net_return"]
    prod_net.index = pd.to_datetime(prod_net.index)

    ph1 = pd.read_csv(DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv")
    ph1["date"] = pd.to_datetime(ph1["date"]); ph1 = ph1.set_index("date")
    ph4 = pd.read_csv(DATA / "research" / "frontier_phase4" / "leadership_signals.csv")
    ph4["date"] = pd.to_datetime(ph4["date"]); ph4 = ph4.set_index("date")
    r2a = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(wrapper.index).fillna(0.0)
    lead = pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce").reindex(wrapper.index).ffill().fillna(0.0)

    def evaluate(name: str, mods: list) -> dict:
        res = wrapper.run(name, mods)
        m = window_metrics(res.path, OFFICIAL_HOLDOUT_START)
        cand = res.path.set_index("Date")["net_return"]
        cand.index = pd.to_datetime(cand.index)
        boot = block_bootstrap_p(cand, prod_net)
        roll = rolling_origin_win_rate(cand, prod_net)
        sp_s = state_sharpe(res.path, wrapper.states, "stressed_panic")
        passed, ok, fail = phase_d_gates(m, base_m, cand_sp_sharpe=sp_s, base_sp_sharpe=base_sp, bootstrap=boot, rolling=roll)
        return {
            "variant": name,
            "full_sharpe": m["full"]["sharpe"], "full_ret": m["full"]["ann_return"],
            "maxdd": m["full"]["max_drawdown"], "cvar5": m["full"]["cvar_5"],
            "ann_vol": m["full"]["ann_vol"], "holdout_sharpe": m["holdout"]["sharpe"],
            "turnover": m["full"]["avg_turnover"], "sp_sharpe_delta": sp_s - base_sp,
            "boot_p": boot["p_cand_gt_base"], "roll_win": float(roll["beats"].mean()),
            "gfc_ret": m["gfc_2008"]["ann_return"], "covid_ret": m["covid_2020"]["ann_return"],
            "bear22_ret": m["bear_2022"]["ann_return"],
            "gates": "PASS" if passed else "FAIL", "fail": " | ".join(fail),
            "_path": res.path,
        }

    # F1: alpha curve.
    rows = []
    for a in (0.08, 0.12, 0.16, 0.20, 0.24, 0.32, 0.40, 0.48):
        r = evaluate(f"alpha_{a}", [series_modifier(f"a{a}", "offense_budget", r2a_scale_with_alpha(r2a, lead, states, a))])
        r.pop("_path")
        r["post_hoc_extension"] = a > 0.16
        rows.append(r)
    alpha_df = pd.DataFrame(rows)
    alpha_df.to_csv(OUT_DIR / "f1_alpha_curve_gates.csv", index=False)
    print("F1 alpha curve:")
    print(alpha_df.drop(columns=["fail"]).round(4).to_string(index=False))

    # F2: extended-grid walk-forward adaptive alpha.
    alpha_paths, alpha_weights = {}, {}
    for a in (0.08, 0.16, 0.24, 0.32):
        res = wrapper.run(f"alpha_{a}", [series_modifier(f"a{a}", "offense_budget", r2a_scale_with_alpha(r2a, lead, states, a))])
        alpha_paths[a] = res.path
        alpha_weights[a] = res.weights
    f2_rows = []
    for obj in ("sharpe", "tail_utility", "calmar_blend"):
        net, chosen = adaptive_alpha_path(alpha_paths, alpha_weights, obj)
        ch = chosen.dropna()
        f2_rows.append({"objective": obj, "avg_alpha": float(ch.mean()),
                        "switches": int(ch.diff().fillna(0).ne(0).sum()),
                        "share_at_grid_max": float((ch == 0.32).mean())})
    f2 = pd.DataFrame(f2_rows)
    f2.to_csv(OUT_DIR / "f2_adaptive_alpha_extended.csv", index=False)
    print("\nF2 extended-grid adaptive alpha:")
    print(f2.round(4).to_string(index=False))

    # F3: latched M1 + nulls.
    feats = build_feature_panel(wrapper.index, warnings)
    pbi = panic_improvement_composite(feats)
    latched = feats["market_drawdown"].rolling(13, min_periods=1).min() <= -0.10
    count = pbi["confirm_count"]
    sp = states.eq("stressed_panic")

    def latched_mult(mp: float, mf: float) -> pd.Series:
        m = pd.Series(1.0, index=wrapper.index)
        m[sp & latched & (count >= 2) & (count < 3)] = mp
        m[sp & latched & (count >= 3)] = mf
        return m

    f3_rows = []
    for (mp, mf) in ((1.15, 1.30), (1.25, 1.50)):
        mm = latched_mult(mp, mf)
        r = evaluate(f"m1_latched_{mp}_{mf}", [prod_mod, series_modifier("m1L", "offense_budget", mm)])
        r.pop("_path")
        r["n_fire"] = int((mm > 1).sum())
        f3_rows.append(r)
    f3 = pd.DataFrame(f3_rows)
    f3.to_csv(OUT_DIR / "f3_m1_latched_gates.csv", index=False)
    print("\nF3 latched M1:")
    print(f3.drop(columns=["fail"]).round(4).to_string(index=False))

    mm_primary = latched_mult(1.15, 1.30)
    fires = mm_primary[mm_primary > 1.0]
    fires.groupby(fires.index.year).size().rename("fires").to_csv(OUT_DIR / "f3_m1_latched_fires_by_year.csv")
    elig_idx = np.where((sp & latched).to_numpy())[0]
    fm = fires.to_numpy()
    base_full = base_m["full"]["sharpe"]
    nulls = []
    for _ in range(200):
        pick = rng.choice(elig_idx, size=min(len(fm), len(elig_idx)), replace=False)
        m2 = pd.Series(1.0, index=wrapper.index)
        m2.iloc[pick] = rng.permutation(fm)[: len(pick)]
        p = wrapper.run("m1Ln", [prod_mod, series_modifier("m1Ln", "offense_budget", m2)]).path
        nulls.append(window_metrics(p, OFFICIAL_HOLDOUT_START)["full"]["sharpe"] - base_full)
    nulls = np.array(nulls)
    actual = f3.loc[0, "full_sharpe"] - base_full
    pd.DataFrame({"null_full_sharpe_delta": nulls}).to_csv(OUT_DIR / "f3_m1_latched_nulls.csv", index=False)
    m1_null_pct = float((nulls < actual).mean())
    print(f"F3 null: actual {actual:+.4f}, null mean {nulls.mean():+.4f}, actual percentile {m1_null_pct:.1%}")

    # F4: combined candidates (state-disjoint stack).
    m1_max_mod = series_modifier("m1L_max", "offense_budget", latched_mult(1.25, 1.50))
    f4_rows = []
    for a in (0.16, 0.24, 0.32):
        sc = r2a_scale_with_alpha(r2a, lead, states, a)
        r = evaluate(f"combo_alpha{a}_m1L", [series_modifier(f"a{a}", "offense_budget", sc), m1_max_mod])
        path = r.pop("_path")
        path.to_csv(OUT_DIR / f"path_combo_alpha{a}_m1L.csv", index=False)
        f4_rows.append(r)
    f4 = pd.DataFrame(f4_rows)
    f4.to_csv(OUT_DIR / "f4_combo_gates.csv", index=False)
    print("\nF4 combos:")
    print(f4.drop(columns=["fail"]).round(4).to_string(index=False))

    # F5: shuffled-r2a null at alpha=0.24 (timing vs vol-shrink control).
    actual_024 = float(alpha_df.loc[alpha_df["variant"].eq("alpha_0.24"), "full_sharpe"].iloc[0])
    f5_nulls = []
    r2a_arr = r2a.to_numpy()
    for _ in range(N_SHUFFLE_NULL):
        shuf = pd.Series(rng.permutation(r2a_arr), index=r2a.index)
        sc = r2a_scale_with_alpha(shuf, lead, states, 0.24)
        p = wrapper.run("f5n", [series_modifier("f5n", "offense_budget", sc)]).path
        f5_nulls.append(window_metrics(p, OFFICIAL_HOLDOUT_START)["full"]["sharpe"])
    f5_nulls = np.array(f5_nulls)
    pd.DataFrame({"null_full_sharpe": f5_nulls}).to_csv(OUT_DIR / "f5_shuffled_r2a_nulls.csv", index=False)
    f5_pct = float((f5_nulls < actual_024).mean())
    print(f"\nF5 shuffled-r2a null at alpha=0.24: actual Sharpe {actual_024:.4f}, "
          f"null mean {f5_nulls.mean():.4f}, null 95th {np.percentile(f5_nulls, 95):.4f}, "
          f"actual percentile {f5_pct:.1%}")

    manifest = {
        "script": "run_moonshot_followups",
        "seed": SEED,
        "f3_null_percentile": m1_null_pct,
        "f5_actual_alpha024_sharpe": actual_024,
        "f5_null_mean": float(f5_nulls.mean()),
        "f5_percentile": f5_pct,
        "warnings": warnings,
    }
    (OUT_DIR / "followups_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
