"""Alpha/PBI confirmation sprint runner (strict; no discovery, no tuning).

Runs the three locked candidates plus the Frontier-2 throttle comparison arm
against GGG and the production pin, with:

    * exact GGG reproduction check
    * implementation-equivalence check (alpha=0.08 machinery == production pin)
    * full Phase D gates vs the production pin
    * additional locked gates: 2x-cost stress, recovery_fragile capture
      delta >= -0.05 Sharpe, re-risking speed (post-trough 13w risky
      exposure delta >= -2pp)
    * bootstrap (13w block, 2000 iters, seed 20260708), rolling-origin
    * stress windows (GFC / COVID / 2022), worst month / worst quarter
    * exposure-path comparison vs the pin (by state and post-trough)
    * null controls re-run with a fresh seed: shuffled-r2a for Candidate A,
      random-placement PBI null for the B-minus-A increment
    * PBI fragile-panic audit: per-year fire contribution of B minus A

Verdicts follow the locked promotion/rejection rules only.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
for sub in ("", "moonshot1_discovery", "frontier2_overlays", "confirm1_alpha_pbi"):
    p = str(SCRIPTS_DIR / sub) if sub else str(SCRIPTS_DIR)
    if p not in sys.path:
        sys.path.insert(0, p)

from allocator_checkpoint_wrapper import AllocatorCheckpointWrapper, exact_rebuild_tolerance_ok  # noqa: E402
from path1_path3_research_utils import DATA, OFFENSE, load_weekly_prices, rel, state_summary  # noqa: E402
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

from confirm_candidates import (  # noqa: E402
    ALPHA_A,
    ALPHA_C,
    alpha_scale,
    load_r2a_leadership,
    pbi_latched_multiplier,
    throttle_multiplier,
)
from moonshot_models import r2a_scale_with_alpha  # noqa: E402

OUT_DIR = DATA / "research" / "confirm1_alpha_pbi"
SEED = 20260708
BOOT_ITERS = 2000
N_NULL_A = 50
N_NULL_B = 200
RF_CAPTURE_GATE = -0.05
RERISK_EXPOSURE_GATE = -0.02

STRESS_WINDOWS = {"gfc_2008": ("2007-10-01", "2009-03-31"),
                  "covid_2020": ("2020-02-01", "2020-04-30"),
                  "bear_2022": ("2022-01-01", "2022-10-31")}


def net_series(path: pd.DataFrame) -> pd.Series:
    s = path.set_index("Date")["net_return"]
    s.index = pd.to_datetime(s.index)
    return s


def worst_periods(net: pd.Series) -> dict[str, float]:
    monthly = (1 + net).resample("ME").prod() - 1
    quarterly = (1 + net).resample("QE").prod() - 1
    return {"worst_month": float(monthly.min()), "worst_quarter": float(quarterly.min())}


def major_troughs(prices: pd.DataFrame) -> list[pd.Timestamp]:
    spy = prices["SPY"]
    dd = spy / spy.cummax() - 1.0
    troughs = []
    i, idx = 0, spy.index
    while i < len(idx):
        if dd.iloc[i] < -0.10:
            start = i
            while start > 0 and dd.iloc[start - 1] < 0:
                start -= 1
            end = i
            while end < len(idx) - 1 and dd.iloc[end + 1] < 0:
                end += 1
            troughs.append(idx[start + int(np.argmin(dd.iloc[start:end + 1].to_numpy()))])
            i = end + 1
        else:
            i += 1
    return troughs


def risky_exposure(weights: pd.DataFrame) -> pd.Series:
    risky = [c for c in weights.columns if c != "BIL"]
    return weights[risky].sum(axis=1)


def post_trough_exposure(weights: pd.DataFrame, troughs: list[pd.Timestamp], horizon: int = 13) -> float:
    vals = []
    exp = risky_exposure(weights)
    for t in troughs:
        window = exp.loc[t:].iloc[1:horizon + 1]
        if len(window) >= 4:
            vals.append(float(window.mean()))
    return float(np.mean(vals)) if vals else np.nan


def main() -> int:
    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    rng = np.random.default_rng(SEED)

    print("=" * 72)
    print("Alpha/PBI confirmation sprint (locked parameters, no tuning)")
    print("=" * 72)

    wrapper = AllocatorCheckpointWrapper()
    baseline = wrapper.run("ggg_baseline")
    repro = wrapper.compare_to_saved(baseline.path)
    if not exact_rebuild_tolerance_ok(repro):
        print("ABORT: wrapper does not reproduce saved GGG.")
        return 1
    print(f"Exact GGG reproduction OK (err {repro['net_return_max_abs_error']:.2e})")

    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    prod_mod = production_modifier(wrapper)
    production = wrapper.run("production_pin", [prod_mod])

    # Implementation-equivalence check: candidate machinery at alpha=0.08
    # must reproduce the production pin path exactly.
    equiv = wrapper.run("equiv_check", [series_modifier("a008", "offense_budget", alpha_scale(wrapper.index, states, 0.08))])
    equiv_err = float((net_series(equiv.path) - net_series(production.path)).abs().max())
    if equiv_err > 1e-12:
        print(f"ABORT: alpha=0.08 machinery does not reproduce the production pin (err {equiv_err:.2e}).")
        return 1
    print(f"Implementation equivalence OK (alpha=0.08 == production pin, err {equiv_err:.2e})")

    # ── Build locked candidates ──────────────────────────────────────────────
    pbi_mult = pbi_latched_multiplier(wrapper.index, states, warnings)
    pbi_mod = series_modifier("pbi_latched", "offense_budget", pbi_mult)
    pin_net = net_series(production.path)

    runs: dict[str, list] = {
        "cand_A_alpha024": [series_modifier("a024", "offense_budget", alpha_scale(wrapper.index, states, ALPHA_A))],
        "cand_B_alpha024_pbi": [series_modifier("a024", "offense_budget", alpha_scale(wrapper.index, states, ALPHA_A)), pbi_mod],
        "cand_C_alpha016_pbi": [series_modifier("a016", "offense_budget", alpha_scale(wrapper.index, states, ALPHA_C)), pbi_mod],
        "arm_vol_throttle": [prod_mod, series_modifier("throttle", "offense_budget", throttle_multiplier(wrapper.index, states, pin_net))],
    }
    results = {"ggg_baseline": baseline, "production_pin": production}
    for name, mods in runs.items():
        results[name] = wrapper.run(name, mods)
    variants = {name: res.path for name, res in results.items()}

    # ── Metrics ──────────────────────────────────────────────────────────────
    all_metrics = {name: window_metrics(path, OFFICIAL_HOLDOUT_START) for name, path in variants.items()}
    sp_sharpes = {name: state_sharpe(path, wrapper.states, "stressed_panic") for name, path in variants.items()}
    rf_sharpes = {name: state_sharpe(path, wrapper.states, "recovery_fragile") for name, path in variants.items()}

    prices = load_weekly_prices(warnings)
    troughs = major_troughs(prices.reindex(wrapper.index))
    print(f"Major SPY troughs used for re-risking metric: {[str(t.date()) for t in troughs]}")
    post_trough = {name: post_trough_exposure(res.weights, troughs) for name, res in results.items()}

    # 2x-cost stress: identical modifiers on a 20 bps wrapper.
    wrapper2x = AllocatorCheckpointWrapper(cost_bps=20.0)
    prod_mod_2x = production_modifier(wrapper2x)
    pin2x = wrapper2x.run("production_pin", [prod_mod_2x])
    pin2x_m = window_metrics(pin2x.path, OFFICIAL_HOLDOUT_START)
    runs2x = dict(runs)
    runs2x["arm_vol_throttle"] = [prod_mod_2x, series_modifier("throttle", "offense_budget", throttle_multiplier(wrapper2x.index, states, pin_net))]
    twox_rows = []
    for name, mods in runs2x.items():
        p2 = wrapper2x.run(name, mods).path
        m2 = window_metrics(p2, OFFICIAL_HOLDOUT_START)
        twox_rows.append({"variant": name,
                          "full_sharpe_2x": m2["full"]["sharpe"],
                          "pin_full_sharpe_2x": pin2x_m["full"]["sharpe"],
                          "full_sharpe_delta_2x": m2["full"]["sharpe"] - pin2x_m["full"]["sharpe"],
                          "passes_2x": m2["full"]["sharpe"] - pin2x_m["full"]["sharpe"] > 0})
    twox = pd.DataFrame(twox_rows)
    twox.to_csv(OUT_DIR / "two_x_cost_stress.csv", index=False)

    # ── Gates ────────────────────────────────────────────────────────────────
    gate_rows, boot_rows = [], []
    extra_rows = []
    for name in runs:
        cand = net_series(variants[name])
        boot = block_bootstrap_p(cand, pin_net)
        roll = rolling_origin_win_rate(cand, pin_net)
        roll.to_csv(OUT_DIR / f"rolling_origin_{name}.csv", index=False)
        passed, ok, fail = phase_d_gates(
            all_metrics[name], all_metrics["production_pin"],
            cand_sp_sharpe=sp_sharpes[name], base_sp_sharpe=sp_sharpes["production_pin"],
            bootstrap=boot, rolling=roll)
        rf_delta = rf_sharpes[name] - rf_sharpes["production_pin"]
        rerisk_delta = post_trough[name] - post_trough["production_pin"]
        twox_pass = bool(twox.loc[twox["variant"] == name, "passes_2x"].iloc[0])
        extra_ok = (rf_delta >= RF_CAPTURE_GATE) and (rerisk_delta >= RERISK_EXPOSURE_GATE) and twox_pass
        gate_rows.append({"variant": name,
                          "phase_d_vs_pin": "PASS" if passed else "FAIL",
                          "rf_capture_delta": rf_delta, "rf_gate": rf_delta >= RF_CAPTURE_GATE,
                          "rerisk_exposure_delta": rerisk_delta, "rerisk_gate": rerisk_delta >= RERISK_EXPOSURE_GATE,
                          "two_x_cost_pass": twox_pass,
                          "all_locked_gates": "PASS" if (passed and extra_ok) else "FAIL",
                          "fail_detail": " | ".join(fail)})
        boot_rows.append({"variant": name, **boot})
        net = net_series(variants[name])
        extra_rows.append({"variant": name, **worst_periods(net),
                           "sp_sharpe": sp_sharpes[name], "rf_sharpe": rf_sharpes[name],
                           "post_trough_13w_risky_exposure": post_trough[name]})
    for name in ("ggg_baseline", "production_pin"):
        net = net_series(variants[name])
        extra_rows.append({"variant": name, **worst_periods(net),
                           "sp_sharpe": sp_sharpes[name], "rf_sharpe": rf_sharpes[name],
                           "post_trough_13w_risky_exposure": post_trough[name]})
    gate_df = pd.DataFrame(gate_rows)
    gate_df.to_csv(OUT_DIR / "locked_gate_table.csv", index=False)
    pd.DataFrame(boot_rows).to_csv(OUT_DIR / "bootstrap_summary.csv", index=False)
    pd.DataFrame(extra_rows).to_csv(OUT_DIR / "extra_metrics.csv", index=False)

    metric_rows = []
    for name, wins in all_metrics.items():
        for win, m in wins.items():
            metric_rows.append({"variant": name, "window": win, **m})
    pd.DataFrame(metric_rows).to_csv(OUT_DIR / "variant_window_metrics.csv", index=False)
    state_frames = [state_summary(path, wrapper.states, name) for name, path in variants.items()]
    pd.concat([f for f in state_frames if not f.empty], ignore_index=True).to_csv(OUT_DIR / "variant_state_metrics.csv", index=False)

    # ── Exposure paths ───────────────────────────────────────────────────────
    exp_rows = []
    pin_w = results["production_pin"].weights
    for name, res in results.items():
        w = res.weights
        offense_cols = [c for c in w.columns if c in OFFENSE]
        by_state = pd.DataFrame({"risky": risky_exposure(w), "offense": w[offense_cols].sum(axis=1),
                                 "bil": w.get("BIL", 0.0), "state": states})
        agg = by_state.groupby("state")[["risky", "offense", "bil"]].mean()
        for st, row in agg.iterrows():
            exp_rows.append({"variant": name, "state": st, **row.to_dict()})
        if name != "production_pin":
            l1 = (w - pin_w.reindex_like(w).fillna(0.0)).abs().sum(axis=1)
            exp_rows.append({"variant": name, "state": "ALL_avg_L1_weight_diff_vs_pin",
                             "risky": float(l1.mean()), "offense": float(l1.max()), "bil": np.nan})
    pd.DataFrame(exp_rows).to_csv(OUT_DIR / "exposure_paths.csv", index=False)

    # ── Null controls (fresh seed) ───────────────────────────────────────────
    print("\nNull controls (fresh seed)...")
    r2a, lead = load_r2a_leadership(wrapper.index)
    a_sharpe = all_metrics["cand_A_alpha024"]["full"]["sharpe"]
    a_nulls = []
    for _ in range(N_NULL_A):
        shuf = pd.Series(rng.permutation(r2a.to_numpy()), index=r2a.index)
        sc = r2a_scale_with_alpha(shuf, lead, states, ALPHA_A)
        p = wrapper.run("an", [series_modifier("an", "offense_budget", sc)]).path
        a_nulls.append(window_metrics(p, OFFICIAL_HOLDOUT_START)["full"]["sharpe"])
    a_nulls = np.array(a_nulls)
    a_null_pct = float((a_nulls < a_sharpe).mean())
    pd.DataFrame({"null_full_sharpe": a_nulls}).to_csv(OUT_DIR / "null_A_shuffled_r2a.csv", index=False)
    print(f"  A shuffled-r2a null: actual {a_sharpe:.4f}, null mean {a_nulls.mean():.4f}, pct {a_null_pct:.1%}")

    b_delta = all_metrics["cand_B_alpha024_pbi"]["full"]["sharpe"] - a_sharpe
    fires = pbi_mult[pbi_mult > 1.0]
    # Null eligibility domain matches the moonshot design: SP weeks inside the
    # 13-week deep-drawdown latch (same domain the real rule draws from).
    from moonshot_features import build_feature_panel as _bfp
    _feats = _bfp(wrapper.index, warnings)
    _latched = _feats["market_drawdown"].rolling(13, min_periods=1).min() <= -0.10
    feats_elig = np.where((states.eq("stressed_panic") & _latched).to_numpy())[0]
    fm = fires.to_numpy()
    b_nulls = []
    a_mods = runs["cand_A_alpha024"]
    for _ in range(N_NULL_B):
        pick = rng.choice(feats_elig, size=min(len(fm), len(feats_elig)), replace=False)
        m2 = pd.Series(1.0, index=wrapper.index)
        m2.iloc[pick] = rng.permutation(fm)[: len(pick)]
        p = wrapper.run("bn", a_mods + [series_modifier("bn", "offense_budget", m2)]).path
        b_nulls.append(window_metrics(p, OFFICIAL_HOLDOUT_START)["full"]["sharpe"] - a_sharpe)
    b_nulls = np.array(b_nulls)
    b_null_pct = float((b_nulls < b_delta).mean())
    pd.DataFrame({"null_b_minus_a_delta": b_nulls}).to_csv(OUT_DIR / "null_B_pbi_placement.csv", index=False)
    print(f"  B-minus-A PBI null: actual {b_delta:+.4f}, null mean {b_nulls.mean():+.4f}, pct {b_null_pct:.1%}")

    # PBI fragile-panic audit: per-year contribution of B minus A.
    diff = net_series(variants["cand_B_alpha024_pbi"]) - net_series(variants["cand_A_alpha024"])
    fire_diff = diff[fires.index]
    audit = fire_diff.groupby(fire_diff.index.year).agg(["sum", "count"])
    audit.columns = ["b_minus_a_return_in_fires", "n_fire_weeks"]
    audit.to_csv(OUT_DIR / "pbi_fragile_panic_audit.csv")
    print("\nPBI per-year fire contribution (B minus A):")
    print(audit.round(4).to_string())

    # ── Verdicts (locked rules only) ─────────────────────────────────────────
    verdicts = {}
    for name in ("cand_A_alpha024", "cand_B_alpha024_pbi", "cand_C_alpha016_pbi"):
        row = gate_df[gate_df["variant"] == name].iloc[0]
        null_ok = a_null_pct >= 0.95 if name == "cand_A_alpha024" else True
        if name in ("cand_B_alpha024_pbi", "cand_C_alpha016_pbi"):
            worst_year = float(audit["b_minus_a_return_in_fires"].min()) if not audit.empty else 0.0
            pbi_fragile_ok = worst_year > -0.02
        else:
            pbi_fragile_ok = True
        if row["all_locked_gates"] == "PASS" and null_ok and pbi_fragile_ok:
            verdict = "CONFIRMED-FOR-HUMAN-REVIEW"
        else:
            verdict = "RESEARCH-ONLY"
        verdicts[name] = {"verdict": verdict,
                          "all_locked_gates": row["all_locked_gates"],
                          "fail_detail": row["fail_detail"],
                          "null_ok": bool(null_ok), "pbi_fragile_ok": bool(pbi_fragile_ok)}

    for name, path in variants.items():
        path.to_csv(OUT_DIR / f"path_{name}.csv", index=False)
    pd.DataFrame({"pbi_multiplier": pbi_mult}).to_csv(OUT_DIR / "pbi_multiplier.csv")

    manifest = {
        "sprint": "confirm1_alpha_pbi", "date": "2026-07-07", "seed": SEED,
        "locked_candidates": {"A": {"alpha": ALPHA_A}, "B": {"alpha": ALPHA_A, "pbi": [1.15, 1.30]},
                              "C": {"alpha": ALPHA_C, "pbi": [1.15, 1.30]}},
        "exact_ggg_reproduction": True,
        "implementation_equivalence_err": equiv_err,
        "null_A_percentile": a_null_pct, "null_B_percentile": b_null_pct,
        "pbi_fire_weeks": int((pbi_mult > 1).sum()),
        "verdicts": verdicts,
        "runtime_seconds": round(time.time() - t0, 1),
        "warnings": warnings,
    }
    (OUT_DIR / "sprint_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

    print("\nVerdicts:")
    for name, v in verdicts.items():
        print(f"  {name}: {v['verdict']}" + (f"  [{v['fail_detail']}]" if v["fail_detail"] else ""))
    print(f"\nOutputs: {rel(OUT_DIR)}  ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
