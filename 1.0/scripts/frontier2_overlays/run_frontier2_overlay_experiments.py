"""Frontier-2 risk-structure overlay sprint runner.

Tests four bounded, causal, low-turnover overlays stacked on the current
production pin (``improved_frontier_phase5_fragility_guard`` wrapper modifier)
and standalone on the GGG base:

    O1 vix_ts_stress_gate        - persistent VIX backwardation de-risk +
                                   contango-resolution re-risk window
    O2 canary_cash_gate          - DAA-style EEM+IEF canary count at the
                                   cash_bil_budget checkpoint
    O3 absorption_fragility      - Kritzman absorption-ratio shift throttle
    O4 vol_managed_offense       - conservative Moreira-Muir offense scalar

Protocol (predeclared before any candidate run):
    * Primary parameters are fixed in PRIMARY_CONFIGS below. Sensitivity grids
      are reported but never used to select the headline configuration.
    * stressed_panic weeks are always forced to multiplier 1.0.
    * All signals are shifted one week beyond the Friday-close convention.
    * Gates: the 8 Phase D gates from Frontier Phase 10A, applied vs the
      production pin (primary) and vs GGG (secondary).
    * Bootstrap: 13-week block, 2000 iterations, seed 20260706.
    * Rolling origin: 104-week windows, 13-week step, Sharpe win rate.
    * Verdict rules:
        PROMOTE-CANDIDATE: all 8 gates pass vs production pin, holdout
            Sharpe delta >= 0, and >= 60% of the sensitivity grid has a
            positive full-history Sharpe delta.
        SHADOW: all 8 gates pass vs GGG but not vs the production pin.
        RESEARCH-ONLY: directional improvement without full gate clearance.
        DROP: full and holdout Sharpe deltas both non-positive.

No production pins, registries, or dashboard files are touched.
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

from allocator_checkpoint_wrapper import (  # noqa: E402
    AllocatorCheckpointWrapper,
    CheckpointModifier,
    exact_rebuild_tolerance_ok,
)
from path1_path3_research_utils import (  # noqa: E402
    DATA,
    PHASE2B,
    SHADOW,
    metrics_from_path,
    rel,
    state_summary,
)
from production_allocator import production_modifier  # noqa: E402
from production_config import OFFICIAL_HOLDOUT_START, PRODUCTION_CANDIDATE  # noqa: E402

from overlay_signals import (  # noqa: E402
    absorption_ratio_shift,
    canary_bad_count,
    load_vix_term_structure,
    load_weekly_prices,
    load_weekly_returns,
    realized_vol_scalar,
    vix_backwardation_events,
)

OUT_DIR = DATA / "research" / "frontier2_overlays"
BOOTSTRAP_ITERS = 2000
BOOTSTRAP_BLOCK = 13
BOOTSTRAP_SEED = 20260706
ROLLING_WINDOW = 104
ROLLING_STEP = 13
COST_BPS = 10.0

STRESS_WINDOWS = {
    "gfc_2008": ("2007-10-01", "2009-03-31"),
    "covid_2020": ("2020-02-01", "2020-04-30"),
    "bear_2022": ("2022-01-01", "2022-10-31"),
}

PRIMARY_CONFIGS = {
    "o1_vix_ts_stress_gate": {
        "persist_weeks": 2,
        "derisk_mult": 0.90,
        "rerisk_mult": 1.06,
        "rerisk_window_weeks": 4,
    },
    "o2_canary_cash_gate": {"less_cash_mult": 0.97, "more_cash_mult": 1.06, "confirm_weeks": 2},
    "o3_absorption_fragility": {"threshold": 1.0, "scale": 0.92, "n_components": 2},
    "o4_vol_managed_offense": {
        "vol_window": 13,
        "clip_low": 0.85,
        "clip_high": 1.15,
        "update_every": 4,
    },
}

SENSITIVITY_GRIDS = {
    "o1_vix_ts_stress_gate": [
        {"persist_weeks": p, "derisk_mult": d, "rerisk_mult": r, "rerisk_window_weeks": 4}
        for p in (1, 2, 3)
        for d in (0.85, 0.90, 0.95)
        for r in (1.00, 1.06, 1.10)
    ],
    "o2_canary_cash_gate": [
        {"less_cash_mult": lc, "more_cash_mult": mc, "confirm_weeks": 2}
        for lc in (1.00, 0.97, 0.94)
        for mc in (1.00, 1.06, 1.12)
    ],
    "o3_absorption_fragility": [
        {"threshold": t, "scale": s, "n_components": n}
        for t in (0.75, 1.0, 1.25)
        for s in (0.88, 0.92, 0.96)
        for n in (1, 2)
    ],
    "o4_vol_managed_offense": [
        {"vol_window": w, "clip_low": lo, "clip_high": hi, "update_every": u}
        for w in (13, 26)
        for (lo, hi) in ((0.85, 1.15), (0.90, 1.10))
        for u in (1, 4)
    ],
}


# ── Modifier builders ─────────────────────────────────────────────────────────


def _neutralize_stressed_panic(mult: pd.Series, states: pd.Series) -> pd.Series:
    out = mult.copy()
    out.loc[states.eq("stressed_panic")] = 1.0
    return out


def build_o1_multiplier(wrapper, vix: pd.DataFrame, cfg: dict) -> pd.Series:
    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    ev = vix_backwardation_events(
        vix,
        wrapper.index,
        persist_weeks=cfg["persist_weeks"],
        rerisk_window_weeks=cfg["rerisk_window_weeks"],
    )
    mult = pd.Series(1.0, index=wrapper.index)
    mult[ev["bw_persistent"] > 0] = cfg["derisk_mult"]
    rerisk_states = states.isin(["recovery_fragile", "recovery_confirmed", "neutral_mixed"])
    rerisk_on = (ev["bw_resolved_window"] > 0) & (ev["bw_persistent"] == 0) & rerisk_states
    mult[rerisk_on] = cfg["rerisk_mult"]
    return _neutralize_stressed_panic(mult, states)


def build_o2_multiplier(wrapper, prices: pd.DataFrame, cfg: dict) -> pd.Series:
    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    count = canary_bad_count(prices, wrapper.index, confirm_weeks=cfg["confirm_weeks"])
    mult = pd.Series(1.0, index=wrapper.index)
    mult[count == 0] = cfg["less_cash_mult"]
    mult[count >= 2] = cfg["more_cash_mult"]
    return _neutralize_stressed_panic(mult, states)


def build_o3_multiplier(wrapper, returns: pd.DataFrame, cfg: dict) -> pd.Series:
    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    ar = absorption_ratio_shift(returns, wrapper.index, n_components=cfg["n_components"])
    mult = pd.Series(1.0, index=wrapper.index)
    mult[ar["ar_shift"] > cfg["threshold"]] = cfg["scale"]
    return _neutralize_stressed_panic(mult, states)


def build_o4_multiplier(wrapper, prod_net_returns: pd.Series, cfg: dict) -> pd.Series:
    states = wrapper.states["market_state"].astype(str).reindex(wrapper.index).fillna("neutral_mixed")
    scalar = realized_vol_scalar(
        prod_net_returns,
        wrapper.index,
        vol_window=cfg["vol_window"],
        clip_low=cfg["clip_low"],
        clip_high=cfg["clip_high"],
        update_every=cfg["update_every"],
    )
    return _neutralize_stressed_panic(scalar, states)


OVERLAY_CHECKPOINTS = {
    "o1_vix_ts_stress_gate": "offense_budget",
    "o2_canary_cash_gate": "cash_bil_budget",
    "o3_absorption_fragility": "volatility_risk_overlay",
    "o4_vol_managed_offense": "offense_budget",
}


def series_modifier(name: str, checkpoint: str, series: pd.Series) -> CheckpointModifier:
    def _fn(_wrapper, _checkpoint):
        return series.reindex(_wrapper.index).fillna(1.0)

    return CheckpointModifier(name=name, checkpoint=checkpoint, function=_fn)


# ── Metrics helpers ───────────────────────────────────────────────────────────


def _sharpe(returns: np.ndarray) -> float:
    n = len(returns)
    if n < 8:
        return np.nan
    wealth = float(np.prod(1.0 + returns))
    if wealth <= 0:
        return np.nan
    cagr = wealth ** (52.0 / n) - 1.0
    vol = float(np.std(returns, ddof=1)) * np.sqrt(52.0)
    return cagr / vol if vol > 0 else np.nan


def window_metrics(path: pd.DataFrame, holdout_start: pd.Timestamp) -> dict[str, dict[str, float]]:
    dates = pd.to_datetime(path["Date"])
    full = metrics_from_path(path)
    dev = metrics_from_path(path[dates < holdout_start])
    holdout = metrics_from_path(path[dates >= holdout_start])
    out = {"full": full, "dev": dev, "holdout": holdout}
    for label, (start, end) in STRESS_WINDOWS.items():
        mask = (dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))
        out[label] = metrics_from_path(path[mask])
    return out


def block_bootstrap_p(cand: pd.Series, base: pd.Series) -> dict[str, float]:
    joined = pd.concat([cand.rename("c"), base.rename("b")], axis=1).dropna()
    c = joined["c"].to_numpy()
    b = joined["b"].to_numpy()
    n = len(c)
    if n < ROLLING_WINDOW:
        return {"p_cand_gt_base": np.nan, "mean_sharpe_delta": np.nan, "ci_low": np.nan, "ci_high": np.nan}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    n_blocks = int(np.ceil(n / BOOTSTRAP_BLOCK))
    deltas = np.empty(BOOTSTRAP_ITERS)
    starts_max = n - BOOTSTRAP_BLOCK
    for i in range(BOOTSTRAP_ITERS):
        starts = rng.integers(0, starts_max + 1, size=n_blocks)
        idx = (starts[:, None] + np.arange(BOOTSTRAP_BLOCK)[None, :]).ravel()[:n]
        deltas[i] = _sharpe(c[idx]) - _sharpe(b[idx])
    deltas = deltas[np.isfinite(deltas)]
    return {
        "p_cand_gt_base": float((deltas > 0).mean()),
        "mean_sharpe_delta": float(deltas.mean()),
        "ci_low": float(np.percentile(deltas, 2.5)),
        "ci_high": float(np.percentile(deltas, 97.5)),
    }


def rolling_origin_win_rate(cand: pd.Series, base: pd.Series) -> pd.DataFrame:
    joined = pd.concat([cand.rename("c"), base.rename("b")], axis=1).dropna()
    rows = []
    for start in range(0, len(joined) - ROLLING_WINDOW + 1, ROLLING_STEP):
        chunk = joined.iloc[start : start + ROLLING_WINDOW]
        rows.append(
            {
                "window_start": str(chunk.index[0].date()),
                "window_end": str(chunk.index[-1].date()),
                "cand_sharpe": _sharpe(chunk["c"].to_numpy()),
                "base_sharpe": _sharpe(chunk["b"].to_numpy()),
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df["beats"] = (df["cand_sharpe"] > df["base_sharpe"]).astype(float)
    return df


def state_sharpe(path: pd.DataFrame, states: pd.DataFrame, state: str) -> float:
    summ = state_summary(path, states, "x")
    if summ.empty:
        return np.nan
    row = summ[summ["market_state"] == state]
    return float(row["sharpe"].iloc[0]) if not row.empty else np.nan


def phase_d_gates(
    cand: dict,
    base: dict,
    *,
    cand_sp_sharpe: float,
    base_sp_sharpe: float,
    bootstrap: dict[str, float],
    rolling: pd.DataFrame,
) -> tuple[bool, list[str], list[str]]:
    ok, fail = [], []

    def delta(key: str, win: str) -> float:
        try:
            return float(cand[win][key]) - float(base[win][key])
        except (KeyError, TypeError, ValueError):
            return np.nan

    sh = delta("sharpe", "full")
    (ok if np.isfinite(sh) and sh >= 0.01 else fail).append(f"full_sharpe_delta={sh:+.4f} (gate >= +0.01)")
    hd = delta("sharpe", "holdout")
    (ok if np.isfinite(hd) and hd >= -0.02 else fail).append(f"holdout_sharpe_delta={hd:+.4f} (gate >= -0.02)")
    dd = delta("max_drawdown", "full")
    (ok if np.isfinite(dd) and dd >= -0.01 else fail).append(f"max_dd_delta={dd:+.4f} (gate >= -0.01)")
    cv = delta("cvar_5", "full")
    (ok if np.isfinite(cv) and cv >= -0.002 else fail).append(f"cvar5_delta={cv:+.4f} (gate >= -0.002)")
    sp = cand_sp_sharpe - base_sp_sharpe
    (ok if (not np.isfinite(sp)) or sp >= -0.05 else fail).append(f"stressed_panic_sharpe_delta={sp:+.4f} (gate >= -0.05)")
    to = (cand["full"].get("avg_turnover") or 0.0) - (base["full"].get("avg_turnover") or 0.0)
    extra_cost = to * (COST_BPS / 1e4) * 52
    (ok if extra_cost < 0.0015 else fail).append(f"extra_annual_cost={extra_cost*100:.4f}% (gate < 0.15%)")
    p = bootstrap.get("p_cand_gt_base", np.nan)
    (ok if np.isfinite(p) and p >= 0.60 else fail).append(f"bootstrap_p={p:.3f} (gate >= 0.60)")
    wr = float(rolling["beats"].mean()) if not rolling.empty else np.nan
    (ok if np.isfinite(wr) and wr >= 0.55 else fail).append(f"rolling_win={wr:.3f} (gate >= 0.55)")
    return len(fail) == 0, ok, fail


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    print("=" * 72)
    print("Frontier-2 risk-structure overlay sprint")
    print("=" * 72)

    wrapper = AllocatorCheckpointWrapper()
    states = wrapper.states

    # Reproduction check: no-modifier wrapper must equal saved GGG exactly.
    baseline = wrapper.run("ggg_baseline")
    repro = wrapper.compare_to_saved(baseline.path)
    repro_ok = exact_rebuild_tolerance_ok(repro)
    print(f"Exact GGG reproduction: {'OK' if repro_ok else 'FAILED'} "
          f"(net max abs err {repro.get('net_return_max_abs_error'):.2e})")
    if not repro_ok:
        print("ABORT: wrapper does not reproduce saved GGG. No results are trustworthy.")
        return 1

    prod_mod = production_modifier(wrapper)
    production = wrapper.run("production_pin", [prod_mod])

    # Reference pins (saved weight sets, no modifier).
    reference_paths: dict[str, pd.DataFrame] = {}
    for name, label in ((PHASE2B, "rollback_pin"), (SHADOW, "shadow_pin")):
        try:
            ref_wrapper = AllocatorCheckpointWrapper(name)
            reference_paths[label] = ref_wrapper.run(label).path
        except Exception as exc:
            warnings.append(f"Could not rebuild {label} ({name}): {exc}")

    # Overlay inputs.
    vix = load_vix_term_structure(warnings)
    prices = load_weekly_prices(warnings)
    returns = load_weekly_returns(warnings)
    prod_net = production.path.set_index("Date")["net_return"]
    prod_net.index = pd.to_datetime(prod_net.index)

    def build_multiplier(overlay: str, cfg: dict) -> pd.Series:
        if overlay == "o1_vix_ts_stress_gate":
            return build_o1_multiplier(wrapper, vix, cfg)
        if overlay == "o2_canary_cash_gate":
            return build_o2_multiplier(wrapper, prices, cfg)
        if overlay == "o3_absorption_fragility":
            return build_o3_multiplier(wrapper, returns, cfg)
        if overlay == "o4_vol_managed_offense":
            return build_o4_multiplier(wrapper, prod_net, cfg)
        raise ValueError(overlay)

    holdout_start = OFFICIAL_HOLDOUT_START

    # ── Primary variants ─────────────────────────────────────────────────────
    variants: dict[str, pd.DataFrame] = {
        "ggg_baseline": baseline.path,
        "production_pin": production.path,
    }
    multipliers: dict[str, pd.Series] = {}
    for overlay, cfg in PRIMARY_CONFIGS.items():
        mult = build_multiplier(overlay, cfg)
        multipliers[overlay] = mult
        checkpoint = OVERLAY_CHECKPOINTS[overlay]
        mod = series_modifier(overlay, checkpoint, mult)
        variants[f"{overlay}__on_ggg"] = wrapper.run(f"{overlay}__on_ggg", [mod]).path
        variants[f"{overlay}__stacked"] = wrapper.run(f"{overlay}__stacked", [prod_mod, mod]).path

    # ── Metrics ──────────────────────────────────────────────────────────────
    all_metrics: dict[str, dict] = {}
    for name, path in {**variants, **reference_paths}.items():
        all_metrics[name] = window_metrics(path, holdout_start)

    def net_series(path: pd.DataFrame) -> pd.Series:
        s = path.set_index("Date")["net_return"]
        s.index = pd.to_datetime(s.index)
        return s

    prod_series = net_series(production.path)
    ggg_series = net_series(baseline.path)

    sp_sharpes = {name: state_sharpe(path, states, "stressed_panic") for name, path in variants.items()}

    # ── Gates, bootstrap, rolling for stacked variants ───────────────────────
    gate_rows, boot_rows, rolling_frames = [], [], {}
    stacked_names = [f"{o}__stacked" for o in PRIMARY_CONFIGS]
    positive_overlays: list[str] = []
    for overlay in PRIMARY_CONFIGS:
        name = f"{overlay}__stacked"
        cand_series = net_series(variants[name])
        boot_pin = block_bootstrap_p(cand_series, prod_series)
        rolling_pin = rolling_origin_win_rate(cand_series, prod_series)
        rolling_frames[name] = rolling_pin
        passed_pin, ok_pin, fail_pin = phase_d_gates(
            all_metrics[name],
            all_metrics["production_pin"],
            cand_sp_sharpe=sp_sharpes[name],
            base_sp_sharpe=sp_sharpes["production_pin"],
            bootstrap=boot_pin,
            rolling=rolling_pin,
        )
        boot_ggg = block_bootstrap_p(cand_series, ggg_series)
        rolling_ggg = rolling_origin_win_rate(cand_series, ggg_series)
        passed_ggg, ok_ggg, fail_ggg = phase_d_gates(
            all_metrics[name],
            all_metrics["ggg_baseline"],
            cand_sp_sharpe=sp_sharpes[name],
            base_sp_sharpe=sp_sharpes["ggg_baseline"],
            bootstrap=boot_ggg,
            rolling=rolling_ggg,
        )
        gate_rows.append(
            {
                "variant": name,
                "vs_production_pin": "PASS" if passed_pin else "FAIL",
                "pin_ok": " | ".join(ok_pin),
                "pin_fail": " | ".join(fail_pin),
                "vs_ggg": "PASS" if passed_ggg else "FAIL",
                "ggg_fail": " | ".join(fail_ggg),
            }
        )
        boot_rows.append({"variant": name, "base": "production_pin", **boot_pin})
        boot_rows.append({"variant": name, "base": "ggg_baseline", **boot_ggg})

        full_d = all_metrics[name]["full"]["sharpe"] - all_metrics["production_pin"]["full"]["sharpe"]
        hold_d = all_metrics[name]["holdout"]["sharpe"] - all_metrics["production_pin"]["holdout"]["sharpe"]
        if np.isfinite(full_d) and np.isfinite(hold_d) and full_d > 0 and hold_d > 0:
            positive_overlays.append(overlay)

    # ── Combined stack (predeclared rule: all overlays with positive full AND
    #    holdout Sharpe deltas vs production pin) ──────────────────────────────
    combo_name = None
    if len(positive_overlays) >= 2:
        combo_name = "combo_" + "_".join(sorted(o.split("_")[0] for o in positive_overlays)) + "__stacked"
        mods = [prod_mod] + [
            series_modifier(o, OVERLAY_CHECKPOINTS[o], multipliers[o]) for o in positive_overlays
        ]
        variants[combo_name] = wrapper.run(combo_name, mods).path
        all_metrics[combo_name] = window_metrics(variants[combo_name], holdout_start)
        sp_sharpes[combo_name] = state_sharpe(variants[combo_name], states, "stressed_panic")
        cand_series = net_series(variants[combo_name])
        boot_pin = block_bootstrap_p(cand_series, prod_series)
        rolling_pin = rolling_origin_win_rate(cand_series, prod_series)
        rolling_frames[combo_name] = rolling_pin
        passed_pin, ok_pin, fail_pin = phase_d_gates(
            all_metrics[combo_name],
            all_metrics["production_pin"],
            cand_sp_sharpe=sp_sharpes[combo_name],
            base_sp_sharpe=sp_sharpes["production_pin"],
            bootstrap=boot_pin,
            rolling=rolling_pin,
        )
        gate_rows.append(
            {
                "variant": combo_name,
                "vs_production_pin": "PASS" if passed_pin else "FAIL",
                "pin_ok": " | ".join(ok_pin),
                "pin_fail": " | ".join(fail_pin),
                "vs_ggg": "",
                "ggg_fail": "",
            }
        )
        boot_rows.append({"variant": combo_name, "base": "production_pin", **boot_pin})
        stacked_names.append(combo_name)

    # ── Sensitivity grids (reporting only, never selection) ──────────────────
    sens_rows = []
    for overlay, grid in SENSITIVITY_GRIDS.items():
        for cfg in grid:
            try:
                mult = build_multiplier(overlay, cfg)
                mod = series_modifier(overlay, OVERLAY_CHECKPOINTS[overlay], mult)
                path = wrapper.run("sens", [prod_mod, mod]).path
                m = window_metrics(path, holdout_start)
                sens_rows.append(
                    {
                        "overlay": overlay,
                        **{f"param_{k}": v for k, v in cfg.items()},
                        "full_sharpe_delta_vs_pin": m["full"]["sharpe"] - all_metrics["production_pin"]["full"]["sharpe"],
                        "holdout_sharpe_delta_vs_pin": m["holdout"]["sharpe"] - all_metrics["production_pin"]["holdout"]["sharpe"],
                        "max_dd_delta_vs_pin": m["full"]["max_drawdown"] - all_metrics["production_pin"]["full"]["max_drawdown"],
                        "turnover_delta": (m["full"].get("avg_turnover") or np.nan)
                        - (all_metrics["production_pin"]["full"].get("avg_turnover") or np.nan),
                        "is_primary": cfg == PRIMARY_CONFIGS[overlay],
                    }
                )
            except Exception as exc:
                sens_rows.append({"overlay": overlay, **{f"param_{k}": v for k, v in cfg.items()}, "error": str(exc)})
    sens_df = pd.DataFrame(sens_rows)

    # ── Verdicts (predeclared rules) ─────────────────────────────────────────
    gate_df = pd.DataFrame(gate_rows)
    verdicts = {}
    for overlay in PRIMARY_CONFIGS:
        name = f"{overlay}__stacked"
        row = gate_df[gate_df["variant"] == name].iloc[0]
        full_d = all_metrics[name]["full"]["sharpe"] - all_metrics["production_pin"]["full"]["sharpe"]
        hold_d = all_metrics[name]["holdout"]["sharpe"] - all_metrics["production_pin"]["holdout"]["sharpe"]
        grid = sens_df[(sens_df["overlay"] == overlay) & sens_df.get("error", pd.Series(dtype=object)).isna()] if "error" in sens_df.columns else sens_df[sens_df["overlay"] == overlay]
        frac_pos = float((grid["full_sharpe_delta_vs_pin"] > 0).mean()) if not grid.empty else np.nan
        # Note: stacked overlays inherit the production pin's edge vs GGG, so
        # "passes vs GGG" is not evidence the overlay itself adds value. The
        # overlay verdict is therefore based on the vs-pin comparison only.
        if row["vs_production_pin"] == "PASS" and hold_d >= 0 and np.isfinite(frac_pos) and frac_pos >= 0.60:
            verdict = "PROMOTE-CANDIDATE"
        elif (np.isfinite(full_d) and full_d > 0) or (np.isfinite(hold_d) and hold_d > 0):
            verdict = "RESEARCH-ONLY"
        else:
            verdict = "DROP"
        verdicts[name] = {
            "verdict": verdict,
            "full_sharpe_delta_vs_pin": float(full_d),
            "holdout_sharpe_delta_vs_pin": float(hold_d),
            "sensitivity_frac_positive": frac_pos,
        }
    if combo_name is not None:
        row = gate_df[gate_df["variant"] == combo_name].iloc[0]
        full_d = all_metrics[combo_name]["full"]["sharpe"] - all_metrics["production_pin"]["full"]["sharpe"]
        hold_d = all_metrics[combo_name]["holdout"]["sharpe"] - all_metrics["production_pin"]["holdout"]["sharpe"]
        verdicts[combo_name] = {
            "verdict": "PROMOTE-CANDIDATE" if row["vs_production_pin"] == "PASS" and hold_d >= 0 else "RESEARCH-ONLY",
            "full_sharpe_delta_vs_pin": float(full_d),
            "holdout_sharpe_delta_vs_pin": float(hold_d),
            "sensitivity_frac_positive": np.nan,
        }

    # ── Outputs ──────────────────────────────────────────────────────────────
    metric_rows = []
    for name, wins in all_metrics.items():
        for win, m in wins.items():
            metric_rows.append({"variant": name, "window": win, **m})
    pd.DataFrame(metric_rows).to_csv(OUT_DIR / "variant_window_metrics.csv", index=False)

    state_rows = []
    for name, path in variants.items():
        summ = state_summary(path, states, name)
        if not summ.empty:
            state_rows.append(summ)
    pd.concat(state_rows, ignore_index=True).to_csv(OUT_DIR / "variant_state_metrics.csv", index=False)

    gate_df.to_csv(OUT_DIR / "phase_d_gates.csv", index=False)
    pd.DataFrame(boot_rows).to_csv(OUT_DIR / "bootstrap_summary.csv", index=False)
    for name, frame in rolling_frames.items():
        frame.to_csv(OUT_DIR / f"rolling_origin_{name}.csv", index=False)
    sens_df.to_csv(OUT_DIR / "parameter_sensitivity.csv", index=False)

    mult_panel = pd.DataFrame(multipliers)
    mult_panel.index.name = "Date"
    mult_panel.to_csv(OUT_DIR / "overlay_multipliers.csv")

    for name, path in variants.items():
        path.to_csv(OUT_DIR / f"path_{name}.csv", index=False)

    manifest = {
        "sprint": "frontier2_overlays",
        "date": "2026-07-06",
        "production_candidate": PRODUCTION_CANDIDATE,
        "exact_ggg_reproduction": repro_ok,
        "reproduction_stats": {k: float(v) for k, v in repro.items()},
        "primary_configs": PRIMARY_CONFIGS,
        "bootstrap": {"iters": BOOTSTRAP_ITERS, "block": BOOTSTRAP_BLOCK, "seed": BOOTSTRAP_SEED},
        "holdout_start": str(holdout_start.date()),
        "verdicts": verdicts,
        "combo_variant": combo_name,
        "n_configs_evaluated": int(len(sens_df)) + len(PRIMARY_CONFIGS) * 2,
        "warnings": warnings,
    }
    (OUT_DIR / "sprint_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

    print("\nVerdicts:")
    for name, v in verdicts.items():
        print(f"  {name}: {v['verdict']} (full d={v['full_sharpe_delta_vs_pin']:+.4f}, "
              f"holdout d={v['holdout_sharpe_delta_vs_pin']:+.4f}, "
              f"sens frac+={v['sensitivity_frac_positive']})")
    print(f"\nOutputs written to {rel(OUT_DIR)}")
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  - {w}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
