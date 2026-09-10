"""Moonshot discovery sprint runner.

Candidates (all through the exact production wrapper, all costs included):
    M1 pbi_rerisk       - panic-but-improving re-risk engine (rule; fires ONLY
                          inside stressed_panic; never scales below 1.0)
    M2 knn_analog       - walk-forward kNN analog decision engine (ML track);
                          tested both replacing and stacked on the R2A rule
    M3 kmeans_states    - walk-forward learned market states (ML track)
    M4 adaptive_alpha   - walk-forward objective-driven alpha selection

Controls:
    * M1: 200 seeded random-placement nulls + inverted-composite control
    * M2: ridge baseline, 50 shuffled-target nulls, feature-group ablations
    * M3: 200 permuted cluster-action nulls, k sensitivity
    * M4: fixed-alpha baselines under each objective

Every wrapper evaluation is counted and reported for data-mining accounting.
No production files are modified. The official holdout is only consumed by
the final gate table, never for selection.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
FRONTIER2_DIR = SCRIPTS_DIR / "frontier2_overlays"
if str(FRONTIER2_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTIER2_DIR))

from allocator_checkpoint_wrapper import (  # noqa: E402
    AllocatorCheckpointWrapper,
    CheckpointModifier,
    exact_rebuild_tolerance_ok,
)
from path1_path3_research_utils import DATA, rel, state_summary  # noqa: E402
from production_allocator import production_modifier, production_scale  # noqa: E402
from production_config import OFFICIAL_HOLDOUT_START  # noqa: E402

from run_frontier2_overlay_experiments import (  # noqa: E402  (shared harness)
    block_bootstrap_p,
    phase_d_gates,
    rolling_origin_win_rate,
    series_modifier,
    state_sharpe,
    window_metrics,
)

from moonshot_features import (  # noqa: E402
    ALL_FEATURES,
    FEATURE_GROUPS,
    build_feature_panel,
    expanding_standardize,
    offense_excess_forward,
    panic_improvement_composite,
)
from moonshot_models import (  # noqa: E402
    AMPLITUDE,
    adaptive_alpha_path,
    kmeans_state_multiplier,
    knn_analog_predictions,
    pbi_multiplier,
    predictions_to_multiplier,
    r2a_scale_with_alpha,
    ridge_predictions,
)

OUT_DIR = DATA / "research" / "moonshot1_discovery"
SEED = 20260707
N_NULL_M1 = 200
N_NULL_M2 = 50
N_NULL_M3 = 200

RUN_COUNTER = {"wrapper_runs": 0}


def counted_run(wrapper, name, mods):
    RUN_COUNTER["wrapper_runs"] += 1
    return wrapper.run(name, mods)


def net_series(path: pd.DataFrame) -> pd.Series:
    s = path.set_index("Date")["net_return"]
    s.index = pd.to_datetime(s.index)
    return s


def sharpe_full(path: pd.DataFrame) -> float:
    m = window_metrics(path, OFFICIAL_HOLDOUT_START)
    return m["full"]["sharpe"]


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    rng = np.random.default_rng(SEED)

    print("=" * 72)
    print("Moonshot discovery sprint")
    print("=" * 72)

    wrapper = AllocatorCheckpointWrapper()
    baseline = counted_run(wrapper, "ggg_baseline", [])
    repro = wrapper.compare_to_saved(baseline.path)
    if not exact_rebuild_tolerance_ok(repro):
        print("ABORT: wrapper does not reproduce saved GGG.")
        return 1
    print(f"Exact GGG reproduction OK (err {repro['net_return_max_abs_error']:.2e})")

    prod_mod = production_modifier(wrapper)
    production = counted_run(wrapper, "production_pin", [prod_mod])
    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")

    feats = build_feature_panel(wrapper.index, warnings)
    z = expanding_standardize(feats)
    target = offense_excess_forward(wrapper.final_weights, wrapper.index, warnings)
    pbi = panic_improvement_composite(feats)

    variants: dict[str, pd.DataFrame] = {
        "ggg_baseline": baseline.path,
        "production_pin": production.path,
    }
    mult_store: dict[str, pd.Series] = {}

    # ── M1: panic-but-improving re-risk engine ──────────────────────────────
    print("\n[M1] panic-but-improving re-risk engine")
    m1_primary_cfg = dict(count_gate=2, mult_partial=1.15, mult_full=1.30, dd_context=-0.10)
    m1_mult = pbi_multiplier(states, pbi, **m1_primary_cfg)
    mult_store["m1_pbi"] = m1_mult
    m1_mod = series_modifier("m1_pbi", "offense_budget", m1_mult)
    variants["m1_pbi__stacked"] = counted_run(wrapper, "m1_pbi__stacked", [prod_mod, m1_mod]).path
    fire_weeks = m1_mult[m1_mult > 1.0]
    print(f"  fires in {len(fire_weeks)} weeks ({len(fire_weeks)/len(m1_mult):.1%}); "
          f"full={int((m1_mult >= 1.30).sum())}, partial={int(((m1_mult > 1.0) & (m1_mult < 1.30)).sum())}")
    pd.DataFrame({"multiplier": fire_weeks}).to_csv(OUT_DIR / "m1_fire_weeks.csv")

    # M1 sensitivity grid (reporting only)
    m1_sens = []
    for (mp, mf) in ((1.10, 1.20), (1.15, 1.30), (1.25, 1.50)):
        for cg in (2, 3):
            for ddc in (-0.08, -0.10, -0.15):
                cfg = dict(count_gate=cg, mult_partial=mp, mult_full=mf, dd_context=ddc)
                mm = pbi_multiplier(states, pbi, **cfg)
                p = counted_run(wrapper, "m1s", [prod_mod, series_modifier("m1s", "offense_budget", mm)]).path
                m = window_metrics(p, OFFICIAL_HOLDOUT_START)
                m1_sens.append({**{f"param_{k}": v for k, v in cfg.items()},
                                "n_fire": int((mm > 1.0).sum()),
                                "full_sharpe_delta": m["full"]["sharpe"] - sharpe_full(production.path),
                                "holdout_sharpe_delta": m["holdout"]["sharpe"] - window_metrics(production.path, OFFICIAL_HOLDOUT_START)["holdout"]["sharpe"],
                                "maxdd_delta": m["full"]["max_drawdown"] - window_metrics(production.path, OFFICIAL_HOLDOUT_START)["full"]["max_drawdown"],
                                "is_primary": cfg == m1_primary_cfg})
    pd.DataFrame(m1_sens).to_csv(OUT_DIR / "m1_sensitivity.csv", index=False)

    # M1 nulls: random placement of the same number of fire weeks within
    # stressed_panic & deep-drawdown weeks (dev-period Sharpe delta only).
    eligible = (states.eq("stressed_panic") & (pbi["deep_dd_context"] > 0)).to_numpy()
    n_fire = int((m1_mult > 1.0).sum())
    fire_mults = m1_mult[m1_mult > 1.0].to_numpy()
    elig_idx = np.where(eligible)[0]
    null_deltas = []
    base_full_sharpe = sharpe_full(production.path)
    for i in range(N_NULL_M1):
        pick = rng.choice(elig_idx, size=min(n_fire, len(elig_idx)), replace=False)
        mm = pd.Series(1.0, index=wrapper.index)
        mm.iloc[pick] = rng.permutation(fire_mults)[: len(pick)]
        p = counted_run(wrapper, "m1n", [prod_mod, series_modifier("m1n", "offense_budget", mm)]).path
        null_deltas.append(sharpe_full(p) - base_full_sharpe)
    null_deltas = np.array(null_deltas)
    actual_delta = sharpe_full(variants["m1_pbi__stacked"]) - base_full_sharpe
    m1_null_pct = float((null_deltas < actual_delta).mean())
    pd.DataFrame({"null_full_sharpe_delta": null_deltas}).to_csv(OUT_DIR / "m1_null_distribution.csv", index=False)
    print(f"  actual full-Sharpe delta {actual_delta:+.4f}; null mean {null_deltas.mean():+.4f}; "
          f"percentile of actual vs null: {m1_null_pct:.1%}")

    # M1 inverted-composite control (fire when confirmations are ABSENT).
    inv = pd.Series(1.0, index=wrapper.index)
    inv_fire = states.eq("stressed_panic") & (pbi["deep_dd_context"] > 0) & (pbi["confirm_count"] <= 1)
    inv[inv_fire] = 1.30
    p_inv = counted_run(wrapper, "m1_inverted", [prod_mod, series_modifier("m1_inverted", "offense_budget", inv)]).path
    m1_inverted_delta = sharpe_full(p_inv) - base_full_sharpe
    print(f"  inverted-composite control delta {m1_inverted_delta:+.4f} (should be <= 0 if composite is real)")

    # ── M2: kNN analog decision engine ──────────────────────────────────────
    print("\n[M2] kNN analog decision engine")
    knn_pred = knn_analog_predictions(z, target)
    m2_mult = predictions_to_multiplier(knn_pred, target, states)
    mult_store["m2_knn"] = m2_mult
    m2_mod = series_modifier("m2_knn", "offense_budget", m2_mult)
    variants["m2_knn__replace"] = counted_run(wrapper, "m2_knn__replace", [m2_mod]).path
    variants["m2_knn__stacked"] = counted_run(wrapper, "m2_knn__stacked", [prod_mod, m2_mod]).path

    ridge_pred = ridge_predictions(z, target)
    ridge_mult = predictions_to_multiplier(ridge_pred, target, states)
    variants["m2_ridge__replace"] = counted_run(wrapper, "m2_ridge__replace", [series_modifier("m2_ridge", "offense_budget", ridge_mult)]).path

    # Rank IC diagnostics (dev only)
    dev_mask = (z.index < OFFICIAL_HOLDOUT_START)
    def rank_ic(pred: pd.Series) -> float:
        j = pd.concat([pred, target], axis=1, keys=["p", "y"]).loc[dev_mask].dropna()
        return float(j["p"].rank().corr(j["y"].rank())) if len(j) > 100 else np.nan
    print(f"  dev rank IC: knn={rank_ic(knn_pred):+.4f}, ridge={rank_ic(ridge_pred):+.4f}, "
          f"r2a={rank_ic(production_scale(wrapper).reindex(z.index)):+.4f}")

    # M2 nulls: shuffled targets (analog structure destroyed, geometry kept)
    m2_null_deltas = []
    y_arr = target.copy()
    for i in range(N_NULL_M2):
        y_shuf = pd.Series(rng.permutation(y_arr.to_numpy()), index=y_arr.index)
        pred_n = knn_analog_predictions(z, y_shuf)
        mult_n = predictions_to_multiplier(pred_n, y_shuf, states)
        p = counted_run(wrapper, "m2n", [series_modifier("m2n", "offense_budget", mult_n)]).path
        m2_null_deltas.append(sharpe_full(p) - sharpe_full(baseline.path))
    m2_null_deltas = np.array(m2_null_deltas)
    m2_actual_delta = sharpe_full(variants["m2_knn__replace"]) - sharpe_full(baseline.path)
    m2_null_pct = float((m2_null_deltas < m2_actual_delta).mean())
    pd.DataFrame({"null_full_sharpe_delta": m2_null_deltas}).to_csv(OUT_DIR / "m2_null_distribution.csv", index=False)
    print(f"  m2 replace delta vs GGG {m2_actual_delta:+.4f}; null pct {m2_null_pct:.1%}")

    # M2 ablations: drop one feature group at a time
    m2_abl = []
    for gname, gcols in FEATURE_GROUPS.items():
        keep = [c for c in ALL_FEATURES if c not in gcols]
        pred_a = knn_analog_predictions(z[keep], target)
        mult_a = predictions_to_multiplier(pred_a, target, states)
        p = counted_run(wrapper, "m2a", [series_modifier("m2a", "offense_budget", mult_a)]).path
        m2_abl.append({"dropped_group": gname,
                       "full_sharpe_delta_vs_ggg": sharpe_full(p) - sharpe_full(baseline.path),
                       "dev_rank_ic": rank_ic(pred_a)})
    pd.DataFrame(m2_abl).to_csv(OUT_DIR / "m2_ablations.csv", index=False)

    # ── M3: walk-forward learned states ─────────────────────────────────────
    print("\n[M3] walk-forward k-means state discovery")
    m3_mult, m3_clusters = kmeans_state_multiplier(z, target, states, k=7)
    mult_store["m3_kmeans"] = m3_mult
    variants["m3_kmeans__replace"] = counted_run(wrapper, "m3_kmeans__replace", [series_modifier("m3_kmeans", "offense_budget", m3_mult)]).path
    m3_clusters.rename("cluster").to_csv(OUT_DIR / "m3_cluster_assignments.csv")

    m3_sens = []
    for kk in (5, 9):
        mm, _ = kmeans_state_multiplier(z, target, states, k=kk)
        p = counted_run(wrapper, "m3s", [series_modifier("m3s", "offense_budget", mm)]).path
        m3_sens.append({"k": kk, "full_sharpe_delta_vs_ggg": sharpe_full(p) - sharpe_full(baseline.path)})
    pd.DataFrame(m3_sens).to_csv(OUT_DIR / "m3_sensitivity.csv", index=False)

    m3_null_deltas = []
    for i in range(N_NULL_M3):
        perm = rng.permutation(7)
        mm, _ = kmeans_state_multiplier(z, target, states, k=7, action_permutation=perm)
        p = counted_run(wrapper, "m3n", [series_modifier("m3n", "offense_budget", mm)]).path
        m3_null_deltas.append(sharpe_full(p) - sharpe_full(baseline.path))
    m3_null_deltas = np.array(m3_null_deltas)
    m3_actual_delta = sharpe_full(variants["m3_kmeans__replace"]) - sharpe_full(baseline.path)
    m3_null_pct = float((m3_null_deltas < m3_actual_delta).mean())
    pd.DataFrame({"null_full_sharpe_delta": m3_null_deltas}).to_csv(OUT_DIR / "m3_null_distribution.csv", index=False)
    print(f"  m3 replace delta vs GGG {m3_actual_delta:+.4f}; permuted-action null pct {m3_null_pct:.1%}")

    # ── M4: adaptive alpha under invented objectives ─────────────────────────
    print("\n[M4] walk-forward objective-driven alpha selection")
    ph1 = pd.read_csv(DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv")
    ph1["date"] = pd.to_datetime(ph1["date"]); ph1 = ph1.set_index("date")
    ph4 = pd.read_csv(DATA / "research" / "frontier_phase4" / "leadership_signals.csv")
    ph4["date"] = pd.to_datetime(ph4["date"]); ph4 = ph4.set_index("date")
    r2a = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(wrapper.index).fillna(0.0)
    leadership = pd.to_numeric(ph4["leadership_quality_composite"], errors="coerce").reindex(wrapper.index).ffill().fillna(0.0)

    alpha_paths, alpha_weights = {}, {}
    for a in (0.0, 0.04, 0.08, 0.12, 0.16):
        sc = r2a_scale_with_alpha(r2a, leadership, states, a)
        res = counted_run(wrapper, f"alpha_{a}", [series_modifier(f"alpha_{a}", "offense_budget", sc)])
        alpha_paths[a] = res.path
        alpha_weights[a] = res.weights
    m4_rows = []
    for obj in ("sharpe", "tail_utility", "calmar_blend"):
        net, chosen = adaptive_alpha_path(alpha_paths, alpha_weights, obj)
        active = net.dropna()
        fixed = net_series(alpha_paths[0.08]).loc[active.index]
        def _sh(x):
            wv = float((1 + x).prod());
            return (wv ** (52.0 / len(x)) - 1.0) / (x.std(ddof=1) * np.sqrt(52.0))
        m4_rows.append({"objective": obj,
                        "adaptive_sharpe": _sh(active),
                        "fixed_008_sharpe": _sh(fixed),
                        "delta": _sh(active) - _sh(fixed),
                        "alpha_switches": int(chosen.dropna().diff().fillna(0).ne(0).sum()),
                        "avg_alpha": float(chosen.mean())})
    m4_df = pd.DataFrame(m4_rows)
    m4_df.to_csv(OUT_DIR / "m4_adaptive_alpha.csv", index=False)
    print(m4_df.round(4).to_string(index=False))

    # ── Gates / bootstrap / rolling for primary candidates ──────────────────
    print("\nGates for primary candidates vs production pin...")
    prod_series = net_series(production.path)
    all_metrics = {name: window_metrics(path, OFFICIAL_HOLDOUT_START) for name, path in variants.items()}
    sp_sharpes = {name: state_sharpe(path, wrapper.states, "stressed_panic") for name, path in variants.items()}

    gate_rows, boot_rows = [], []
    primary_candidates = ["m1_pbi__stacked", "m2_knn__replace", "m2_knn__stacked", "m3_kmeans__replace"]
    for name in primary_candidates:
        cand = net_series(variants[name])
        boot = block_bootstrap_p(cand, prod_series)
        roll = rolling_origin_win_rate(cand, prod_series)
        roll.to_csv(OUT_DIR / f"rolling_origin_{name}.csv", index=False)
        passed, ok, fail = phase_d_gates(
            all_metrics[name], all_metrics["production_pin"],
            cand_sp_sharpe=sp_sharpes[name], base_sp_sharpe=sp_sharpes["production_pin"],
            bootstrap=boot, rolling=roll)
        gate_rows.append({"variant": name, "vs_production_pin": "PASS" if passed else "FAIL",
                          "ok": " | ".join(ok), "fail": " | ".join(fail)})
        boot_rows.append({"variant": name, "base": "production_pin", **boot})
    gate_df = pd.DataFrame(gate_rows)
    gate_df.to_csv(OUT_DIR / "phase_d_gates.csv", index=False)
    pd.DataFrame(boot_rows).to_csv(OUT_DIR / "bootstrap_summary.csv", index=False)

    metric_rows = []
    for name, wins in all_metrics.items():
        for win, m in wins.items():
            metric_rows.append({"variant": name, "window": win, **m})
    pd.DataFrame(metric_rows).to_csv(OUT_DIR / "variant_window_metrics.csv", index=False)

    state_frames = [state_summary(path, wrapper.states, name) for name, path in variants.items()]
    pd.concat([f for f in state_frames if not f.empty], ignore_index=True).to_csv(OUT_DIR / "variant_state_metrics.csv", index=False)

    pd.DataFrame(mult_store).to_csv(OUT_DIR / "candidate_multipliers.csv")
    for name, path in variants.items():
        path.to_csv(OUT_DIR / f"path_{name}.csv", index=False)

    manifest = {
        "sprint": "moonshot1_discovery",
        "date": "2026-07-07",
        "seed": SEED,
        "exact_ggg_reproduction": True,
        "m1_primary_config": m1_primary_cfg,
        "m1_fire_weeks": int(n_fire),
        "m1_null_percentile": m1_null_pct,
        "m1_inverted_control_delta": float(m1_inverted_delta),
        "m2_null_percentile": m2_null_pct,
        "m3_null_percentile": m3_null_pct,
        "total_wrapper_runs": RUN_COUNTER["wrapper_runs"],
        "runtime_seconds": round(time.time() - t0, 1),
        "warnings": warnings,
    }
    (OUT_DIR / "sprint_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(f"\nTotal wrapper evaluations: {RUN_COUNTER['wrapper_runs']}")
    print(f"Outputs: {rel(OUT_DIR)}  ({time.time()-t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
