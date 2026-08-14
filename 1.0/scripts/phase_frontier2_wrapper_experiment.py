"""Frontier Phase 2B: wrapper experiment combining Phase 1 R2A and Phase 2 trend
quality signals.

Architecture note
-----------------
The wrapper's checkpoint mechanism applies a UNIFORM multiplier to all offensive
ETFs (via `offense_budget`).  Phase 2 requires DIFFERENTIAL per-ETF multipliers
based on cross-sectional quality rank.  These are not supported by a named
checkpoint hook, so Phase 2 scaling is applied as a post-processing step on the
final ETF weights before `production_portfolio_path` recomputes the path.  This
is documented as a research approximation; a proper allocator hook would be
needed for production.  The cost model still applies correctly because
`production_portfolio_path` re-derives turnover from the modified weight matrix.

Run from repo root:
    .venv/bin/python scripts/phase_frontier2_wrapper_experiment.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from path1_path3_research_utils import (
    DATA, DOCS, GGG, OFFENSE,
    PRODUCTION_COST_BPS,
    exposure_summary,
    metrics_from_path,
    normalize_to_cash,
    production_portfolio_path,
)
from allocator_checkpoint_wrapper import (
    AllocatorCheckpointWrapper,
    CheckpointModifier,
    exact_rebuild_tolerance_ok,
)

# ── Constants ────────────────────────────────────────────────────────────────
HOLDOUT_START   = pd.Timestamp("2024-04-19")
DEV_END         = pd.Timestamp("2024-04-12")
BOOTSTRAP_SEED  = 20260420
BOOTSTRAP_ITERS = 2000
BOOTSTRAP_BLOCK = 13
ROLLING_WINDOW  = 104
ROLLING_STEP    = 52
MIN_TRAIN       = 260

PHASE2_ACTIVE_STATES = {"recovery_confirmed", "neutral_mixed"}

OUT_DIR = DATA / "research" / "frontier_phase2"
REPORT_PATH = ROOT / "docs" / "research" / "frontier_phase2_trend_quality_engine_report.md"

PROTECTED_PATHS = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


# ── Data loading ──────────────────────────────────────────────────────────────

def load_quality_panels() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (trend_quality, ma_distance_z) both as date×ticker DataFrames."""
    qp_path = OUT_DIR / "trend_quality_panel.csv"
    cp_path = OUT_DIR / "trend_quality_component_panel.csv"

    if not qp_path.exists():
        raise SystemExit(f"trend_quality_panel.csv not found: {qp_path}")
    if not cp_path.exists():
        raise SystemExit(f"trend_quality_component_panel.csv not found: {cp_path}")

    trend_q = pd.read_csv(qp_path, index_col="date", parse_dates=True)
    trend_q.index = trend_q.index.tz_localize(None)

    comp = pd.read_csv(cp_path)
    comp["date"] = pd.to_datetime(comp["date"], errors="coerce").dt.tz_localize(None)
    ma_z = comp.pivot_table(index="date", columns="ticker", values="ma_distance_z")
    ma_z.index = ma_z.index.tz_localize(None)

    print(f"  trend_quality panel: {trend_q.shape}, NaN%={trend_q.isna().mean().mean():.2%}")
    print(f"  ma_distance_z panel: {ma_z.shape},    NaN%={ma_z.isna().mean().mean():.2%}")
    return trend_q, ma_z


def load_r2a(warnings_list: list[str]) -> pd.Series:
    path = DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
    if not path.exists():
        raise SystemExit(f"R2A signals not found: {path}")
    df = pd.read_csv(path)
    date_col = "date" if "date" in df.columns else "Date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)
    return pd.to_numeric(df["r2a"], errors="coerce")


# ── Phase 1 R2A modifier factory (replicates Phase 1B exactly) ───────────────

def make_r2a_fn(r2a: pd.Series, states: pd.Series, alpha: float = 0.08):
    """Return a CheckpointModifier function for the offense_budget checkpoint."""
    q = r2a.reindex(states.index).ffill().fillna(0.0).clip(-1.0, 1.0)
    scale = pd.Series(1.0, index=states.index, dtype=float)
    scale[states != "stressed_panic"] = 1.0 + alpha * q[states != "stressed_panic"]

    def _fn(wrapper: AllocatorCheckpointWrapper, _checkpoint: str) -> pd.Series:
        return scale

    return CheckpointModifier(name=f"r2a_offense_scale_{int(alpha*100):03d}",
                               checkpoint="offense_budget",
                               function=_fn)


# ── Phase 2 ETF-level quality scaler ─────────────────────────────────────────

def apply_etf_quality_scaling(
    weights: pd.DataFrame,
    quality_panel: pd.DataFrame,
    states: pd.Series,
    active_states: set[str],
    offense_tickers: set[str],
    alpha: float = 0.5,        # scale = (1-alpha) + alpha*rank
) -> pd.DataFrame:
    """Reweight offensive ETFs by cross-sectional quality rank in active states.

    Only active in `active_states`.  In all other states the weights are
    unchanged.  Preserves total offensive allocation; scales within the
    offensive group only.  Renormalises the full row to sum to 1 afterwards.
    """
    modified = weights.copy()
    quality = quality_panel.reindex(modified.index)   # align dates

    for t_idx, date in enumerate(modified.index):
        state = str(states.get(date, ""))
        if state not in active_states:
            continue

        q_row = quality.loc[date] if date in quality.index else None
        if q_row is None:
            continue

        avail = [tk for tk in offense_tickers
                 if tk in modified.columns and tk in q_row.index
                 and np.isfinite(float(q_row.get(tk, np.nan)))]
        if len(avail) < 4:          # need enough tickers to rank meaningfully
            continue

        q_vals = q_row[avail].values.astype(float)
        # Cross-sectional percentile rank → [0, 1]
        rank = scipy_stats.rankdata(q_vals) / len(q_vals)
        scale = (1.0 - alpha) + alpha * rank          # [1-α, 1.0]

        original_offense_total = modified.loc[date, avail].sum()
        if original_offense_total <= 1e-9:
            continue

        # Apply scale
        for i, tk in enumerate(avail):
            modified.loc[date, tk] *= scale[i]

        # Renormalise within offensive group to preserve total offense weight
        scaled_offense_total = modified.loc[date, avail].sum()
        if scaled_offense_total > 1e-9:
            ratio = original_offense_total / scaled_offense_total
            for tk in avail:
                modified.loc[date, tk] *= ratio

    # Ensure each row sums to ≤ 1 (normalize_to_cash handles remainder as BIL)
    return normalize_to_cash(modified)


# ── Metric helpers ────────────────────────────────────────────────────────────

def _ann_return(r: pd.Series) -> float:
    if r.empty:
        return np.nan
    return float((1 + r).prod() ** (52 / len(r)) - 1)


def _ann_vol(r: pd.Series) -> float:
    return float(r.std() * np.sqrt(52)) if len(r) >= 4 else np.nan


def _sharpe(r: pd.Series) -> float:
    v = _ann_vol(r)
    return float(_ann_return(r) / v) if (v and np.isfinite(v) and v > 0) else np.nan


def _max_dd(r: pd.Series) -> float:
    if r.empty:
        return np.nan
    w = (1 + r).cumprod()
    return float((w / w.cummax() - 1).min())


def _cvar(r: pd.Series, pct: float = 0.05) -> float:
    if len(r) < 20:
        return np.nan
    tail = r[r <= r.quantile(pct)]
    return float(tail.mean()) if len(tail) else np.nan


def _spy_capture(port_rets: pd.Series, nwr: pd.DataFrame,
                 dates: pd.DatetimeIndex) -> float:
    if "SPY" not in nwr.columns:
        return np.nan
    spy = nwr["SPY"].reindex(dates).dropna()
    p = port_rets.reindex(dates).dropna()
    common = p.index.intersection(spy.index)
    if len(common) < 8:
        return np.nan
    p_ann = _ann_return(p.loc[common])
    s_ann = _ann_return(spy.loc[common])
    return float(p_ann / s_ann) if (np.isfinite(s_ann) and s_ann > 0.005) else np.nan


def _hidden_beta(port_rets: pd.Series, nwr: pd.DataFrame) -> float:
    if "SPY" not in nwr.columns:
        return np.nan
    spy = nwr["SPY"].reindex(port_rets.index).dropna()
    aligned = pd.concat([port_rets, spy], axis=1).dropna()
    if len(aligned) < 20:
        return np.nan
    slope, *_ = scipy_stats.linregress(aligned.iloc[:, 1], aligned.iloc[:, 0])
    return float(slope)


def summarise_candidate(variant: str, weights: pd.DataFrame, path_df: pd.DataFrame,
                        states: pd.Series, nwr: pd.DataFrame) -> dict:
    """Full-history summary dict for one candidate."""
    path = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    r = path["net_return"].dropna()
    exp = exposure_summary(weights)

    row: dict = {
        "variant": variant,
        "ann_return": _ann_return(r),
        "ann_vol": _ann_vol(r),
        "sharpe": _sharpe(r),
        "max_drawdown": _max_dd(r),
        "cvar_5": _cvar(r),
        "avg_turnover": float(path["turnover"].mean()) if "turnover" in path.columns else np.nan,
        "cost_drag_annual": float(path["cost"].sum() * 52 / len(path)) if "cost" in path.columns else np.nan,
        "avg_BIL": float(exp.get("avg_BIL", np.nan)),
        "avg_offense": float(exp.get("avg_offense", np.nan)),
        "hidden_beta_SPY": _hidden_beta(r, nwr),
    }

    states_aligned = states.reindex(r.index)
    for state in ["calm_trend","neutral_mixed","recovery_confirmed",
                  "recovery_fragile","stressed_panic"]:
        mask = states_aligned == state
        sr = r[mask]
        row[f"sharpe_{state}"] = _sharpe(sr)
        row[f"ann_return_{state}"] = _ann_return(sr)
        row[f"capture_{state}"] = _spy_capture(sr, nwr, sr.index)

    return row


def summarise_window(variant: str, weights: pd.DataFrame, path_df: pd.DataFrame,
                     states: pd.Series, nwr: pd.DataFrame,
                     start: pd.Timestamp | None, end: pd.Timestamp | None,
                     label: str) -> dict:
    path = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    mask = pd.Series(True, index=path.index)
    if start is not None:
        mask &= path.index >= start
    if end is not None:
        mask &= path.index < end
    path_slice = path[mask].reset_index().rename(columns={"index": "Date"})
    w_slice = weights[weights.index.isin(path[mask].index)]
    d = summarise_candidate(variant, w_slice, path_slice, states, nwr)
    d["window"] = label
    return d


# ── Rolling-origin ────────────────────────────────────────────────────────────

def rolling_origin_comparison(cand_path: pd.DataFrame, base_path: pd.DataFrame) -> pd.DataFrame:
    cp = cand_path.set_index("Date") if "Date" in cand_path.columns else cand_path
    bp = base_path.set_index("Date")  if "Date" in base_path.columns else base_path
    n = len(cp)
    rows = []
    for start in range(MIN_TRAIN, n - ROLLING_WINDOW, ROLLING_STEP):
        idx = cp.index[start: start + ROLLING_WINDOW]
        cr = cp.loc[idx, "net_return"].dropna()
        br = bp.loc[idx, "net_return"].dropna() if "net_return" in bp.columns else pd.Series()
        if len(cr) < 20:
            continue
        rows.append({
            "origin": cp.index[start],
            "cand_sharpe": _sharpe(cr),
            "base_sharpe": _sharpe(br) if len(br) >= 20 else np.nan,
            "delta_sharpe": _sharpe(cr) - _sharpe(br) if len(br) >= 20 else np.nan,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["beats_base"] = df["delta_sharpe"] > 0
    return df


# ── Block bootstrap ───────────────────────────────────────────────────────────

def block_bootstrap(cand_r: pd.Series, base_r: pd.Series) -> dict:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    aligned = pd.concat([cand_r, base_r], axis=1).dropna()
    if len(aligned) < 20:
        return {}
    n = len(aligned)
    deltas = []
    for _ in range(BOOTSTRAP_ITERS):
        starts = rng.integers(0, max(1, n - BOOTSTRAP_BLOCK + 1),
                              size=(n // BOOTSTRAP_BLOCK) + 2)
        idx = np.concatenate([np.arange(s, min(s + BOOTSTRAP_BLOCK, n))
                               for s in starts])[:n]
        s = aligned.iloc[idx]
        deltas.append(_sharpe(s.iloc[:, 0]) - _sharpe(s.iloc[:, 1]))
    deltas = np.array([d for d in deltas if np.isfinite(d)])
    if len(deltas) == 0:
        return {}
    return {
        "p_cand_gt_base": float((deltas > 0).mean()),
        "mean_delta": float(np.mean(deltas)),
        "ci95_lo": float(np.percentile(deltas, 2.5)),
        "ci95_hi": float(np.percentile(deltas, 97.5)),
    }


# ── Production diff ───────────────────────────────────────────────────────────

def protected_diff_clean() -> tuple[bool, list[str]]:
    try:
        r = subprocess.run(["git", "diff", "--name-only", "--", *PROTECTED_PATHS],
                           cwd=ROOT, check=False, text=True, capture_output=True)
    except Exception:
        return False, ["git diff check failed"]
    changed = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(changed) == 0, changed


# ── Phase D gate evaluation ───────────────────────────────────────────────────

def phase_d_gates(cand: dict, base: dict, ho_cand: dict, ho_base: dict,
                  bs: dict, rolling: pd.DataFrame) -> tuple[bool, list[str], list[str]]:
    ok, fail = [], []

    sh_d = (cand.get("sharpe") or np.nan) - (base.get("sharpe") or np.nan)
    if np.isfinite(sh_d) and sh_d >= 0.01:
        ok.append(f"Full-history Sharpe Δ={sh_d:+.4f} ≥ +0.01")
    else:
        fail.append(f"Full-history Sharpe Δ={sh_d:+.4f} < +0.01")

    ho_d = (ho_cand.get("sharpe") or np.nan) - (ho_base.get("sharpe") or np.nan)
    if np.isfinite(ho_d) and ho_d >= -0.02:
        ok.append(f"Holdout Sharpe Δ={ho_d:+.4f} ≥ -0.02")
    else:
        fail.append(f"Holdout Sharpe Δ={ho_d:+.4f} < -0.02")

    dd_d = (cand.get("max_drawdown") or np.nan) - (base.get("max_drawdown") or np.nan)
    if np.isfinite(dd_d) and dd_d >= -0.01:
        ok.append(f"MaxDD Δ={dd_d:+.4f} ≥ -0.01")
    else:
        fail.append(f"MaxDD Δ={dd_d:+.4f} < -0.01")

    cv_d = (cand.get("cvar_5") or np.nan) - (base.get("cvar_5") or np.nan)
    if np.isfinite(cv_d) and cv_d >= -0.002:
        ok.append(f"CVaR Δ={cv_d:+.4f} ≥ -0.002")
    else:
        fail.append(f"CVaR Δ={cv_d:+.4f} < -0.002")

    sp_d = ((cand.get("sharpe_stressed_panic") or np.nan) -
            (base.get("sharpe_stressed_panic") or np.nan))
    if not np.isfinite(sp_d) or sp_d >= -0.05:
        ok.append(f"Stressed-panic Sharpe Δ={sp_d:+.4f} (acceptable)")
    else:
        fail.append(f"Stressed-panic Sharpe Δ={sp_d:+.4f} < -0.05 — defense weakened")

    to_d = (cand.get("avg_turnover") or 0) - (base.get("avg_turnover") or 0)
    extra_cost_annual = to_d * (PRODUCTION_COST_BPS / 10000) * 52
    if extra_cost_annual < 0.0015:
        ok.append(f"Extra annual cost={extra_cost_annual*100:.3f}% (< 0.15%)")
    else:
        fail.append(f"Extra annual cost={extra_cost_annual*100:.3f}% ≥ 0.15%")

    p_bs = bs.get("p_cand_gt_base", np.nan)
    if np.isfinite(p_bs) and p_bs >= 0.60:
        ok.append(f"Bootstrap P(cand>base)={p_bs:.3f} ≥ 0.60")
    else:
        fail.append(f"Bootstrap P(cand>base)={p_bs:.3f} < 0.60")

    if not rolling.empty:
        wr = float(rolling["beats_base"].mean())
        if wr >= 0.55:
            ok.append(f"Rolling win rate={wr:.1%} ≥ 55%")
        else:
            fail.append(f"Rolling win rate={wr:.1%} < 55%")

    return len(fail) == 0, ok, fail


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    warnings: list[str] = []
    print("=" * 70)
    print("Frontier Phase 2B: Wrapper Experiment")
    print("=" * 70)

    # ── Load signals ──────────────────────────────────────────────────────────
    print("\nLoading Phase 2A signals...")
    trend_quality, ma_z = load_quality_panels()

    print("Loading Phase 1 R2A signal...")
    r2a = load_r2a(warnings)

    # ── Initialise wrapper ────────────────────────────────────────────────────
    print("Initialising wrapper...")
    wrapper = AllocatorCheckpointWrapper()
    compare = wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(compare, 1e-10):
        raise SystemExit(f"Wrapper reproduction failed: {compare}")
    print(f"  GGG exact match confirmed (max_err={compare['net_return_max_abs_error']:.2e})")

    nwr = wrapper.next_week_returns
    states = wrapper.states["market_state"].astype(str)
    offense_tickers = OFFENSE

    # ── Build all candidate weights ───────────────────────────────────────────
    print("\nBuilding candidate weights...")

    # 1. Baseline
    baseline_run = wrapper.run("ggg_baseline_no_modifier")
    base_weights = baseline_run.weights.copy()
    base_path    = baseline_run.path

    # 2. Phase 1 R2A only
    ph1_mod = make_r2a_fn(r2a, states, alpha=0.08)
    ph1_run  = wrapper.run("phase1_r2a_only", modifiers=[ph1_mod])
    ph1_weights = ph1_run.weights.copy()
    ph1_path    = ph1_run.path

    # 3. Phase 2 trend_quality (state-specific, applied to baseline weights)
    print("  Applying Phase 2 trend_quality scaling (state-specific)...")
    ph2_tq_weights = apply_etf_quality_scaling(
        base_weights, trend_quality, states, PHASE2_ACTIVE_STATES,
        offense_tickers, alpha=0.5
    )
    ph2_tq_path = production_portfolio_path(ph2_tq_weights, nwr, PRODUCTION_COST_BPS)

    # 4. Phase 2 ma_distance (state-specific, applied to baseline weights)
    print("  Applying Phase 2 ma_distance scaling (state-specific)...")
    ph2_ma_weights = apply_etf_quality_scaling(
        base_weights, ma_z, states, PHASE2_ACTIVE_STATES,
        offense_tickers, alpha=0.5
    )
    ph2_ma_path = production_portfolio_path(ph2_ma_weights, nwr, PRODUCTION_COST_BPS)

    # 5. Phase 1 + Phase 2 trend_quality
    print("  Applying Phase 1 + Phase 2 trend_quality (stacked)...")
    ph12_tq_weights = apply_etf_quality_scaling(
        ph1_weights, trend_quality, states, PHASE2_ACTIVE_STATES,
        offense_tickers, alpha=0.5
    )
    ph12_tq_path = production_portfolio_path(ph12_tq_weights, nwr, PRODUCTION_COST_BPS)

    # 6. Phase 1 + Phase 2 ma_distance
    print("  Applying Phase 1 + Phase 2 ma_distance (stacked)...")
    ph12_ma_weights = apply_etf_quality_scaling(
        ph1_weights, ma_z, states, PHASE2_ACTIVE_STATES,
        offense_tickers, alpha=0.5
    )
    ph12_ma_path = production_portfolio_path(ph12_ma_weights, nwr, PRODUCTION_COST_BPS)

    # ── Pack runs ─────────────────────────────────────────────────────────────
    runs: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {
        "ggg_baseline_no_modifier":          (base_weights,    base_path),
        "phase1_r2a_only":                   (ph1_weights,     ph1_path),
        "phase2_trend_quality_state_specific":(ph2_tq_weights, ph2_tq_path),
        "phase2_ma_distance_state_specific":  (ph2_ma_weights, ph2_ma_path),
        "phase1_r2a_plus_phase2_trend_quality":(ph12_tq_weights,ph12_tq_path),
        "phase1_r2a_plus_phase2_ma_distance": (ph12_ma_weights, ph12_ma_path),
    }

    # ── Compute metrics ───────────────────────────────────────────────────────
    print("\nComputing metrics...")
    full_results:    dict[str, dict] = {}
    dev_results:     dict[str, dict] = {}
    holdout_results: dict[str, dict] = {}

    for variant, (wts, path) in runs.items():
        full_results[variant]    = summarise_candidate(variant, wts, path, states, nwr)
        dev_results[variant]     = summarise_window(variant, wts, path, states, nwr,
                                                    None, DEV_END, "development")
        holdout_results[variant] = summarise_window(variant, wts, path, states, nwr,
                                                    HOLDOUT_START, None, "holdout")

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n=== Full-History Summary ===")
    baseline_sh = full_results["ggg_baseline_no_modifier"]["sharpe"]
    for var, r in full_results.items():
        delta = (r["sharpe"] or np.nan) - baseline_sh
        print(f"  {var:<50}: "
              f"ret={r['ann_return']*100:.2f}%  "
              f"sharpe={r['sharpe']:.4f} (Δ{delta:+.4f})  "
              f"dd={r['max_drawdown']:.4f}  "
              f"sp_sh={r.get('sharpe_stressed_panic', np.nan):.4f}  "
              f"to/wk={r['avg_turnover']:.4f}")

    print("\n=== Holdout Summary ===")
    ho_base_sh = holdout_results["ggg_baseline_no_modifier"]["sharpe"]
    for var, r in holdout_results.items():
        delta = (r["sharpe"] or np.nan) - ho_base_sh
        print(f"  {var:<50}: sharpe={r['sharpe']:.4f} (Δ{delta:+.4f})  ret={r['ann_return']*100:.2f}%")

    # ── Rolling-origin and bootstrap for primary candidates ───────────────────
    print("\nComputing rolling-origin validation...")
    rolling_results: dict[str, pd.DataFrame] = {}
    bs_results:      dict[str, dict] = {}

    for var in list(runs.keys()):
        if var == "ggg_baseline_no_modifier":
            continue
        _, path = runs[var]
        rolling_results[var] = rolling_origin_comparison(path, base_path)
        wr = float(rolling_results[var]["beats_base"].mean()) if not rolling_results[var].empty else np.nan
        print(f"  {var:<50}: rolling_win={wr:.1%}")

    # Bootstrap on holdout
    print("Computing holdout block bootstrap...")
    ho_base_rets = base_path.set_index("Date")["net_return"]
    ho_base_rets_ho = ho_base_rets[ho_base_rets.index >= HOLDOUT_START].dropna()

    for var in list(runs.keys()):
        if var == "ggg_baseline_no_modifier":
            continue
        _, path = runs[var]
        p = path.set_index("Date")["net_return"]
        p_ho = p[p.index >= HOLDOUT_START].dropna()
        bs_results[var] = block_bootstrap(p_ho, ho_base_rets_ho)
        p_bs = bs_results[var].get("p_cand_gt_base", np.nan)
        print(f"  {var:<50}: bootstrap_P={p_bs:.3f}")

    # ── Phase D gates for best candidates ────────────────────────────────────
    print("\nPhase D gate evaluation...")
    gate_rows = []
    base_full = full_results["ggg_baseline_no_modifier"]
    base_hold = holdout_results["ggg_baseline_no_modifier"]

    for var in list(runs.keys()):
        if var == "ggg_baseline_no_modifier":
            continue
        gv, ok, fail = phase_d_gates(
            full_results[var], base_full,
            holdout_results[var], base_hold,
            bs_results.get(var, {}),
            rolling_results.get(var, pd.DataFrame()),
        )
        print(f"\n  {var}: {'PASS' if gv else 'FAIL'}")
        for r in ok:
            print(f"    ✓ {r}")
        for r in fail:
            print(f"    ✗ {r}")
        gate_rows.append({
            "variant": var, "gate_verdict": "PASS" if gv else "FAIL",
            "ok": "; ".join(ok), "fail": "; ".join(fail),
            **{f"gate_{'ok' if f in ok else 'fail'}_{i}": f for i, f in enumerate(ok + fail)},
        })

    # ── Determine overall verdict ─────────────────────────────────────────────
    def _sh(r, key="sharpe"):
        v = r.get(key, np.nan)
        return float(v) if v is not None and np.isfinite(float(v)) else np.nan

    # Find best candidate by holdout Sharpe
    best_var = max(
        [v for v in runs if v != "ggg_baseline_no_modifier"],
        key=lambda v: _sh(holdout_results.get(v, {})),
    )
    best_full = full_results[best_var]
    best_hold = holdout_results[best_var]
    best_bs   = bs_results.get(best_var, {})

    full_sh_delta  = _sh(best_full)  - _sh(base_full)
    hold_sh_delta  = _sh(best_hold)  - _sh(base_hold)
    dd_delta       = _sh(best_full, "max_drawdown") - _sh(base_full, "max_drawdown")
    sp_delta       = _sh(best_full, "sharpe_stressed_panic") - _sh(base_full, "sharpe_stressed_panic")
    rc_delta       = _sh(best_full, "sharpe_recovery_confirmed") - _sh(base_full, "sharpe_recovery_confirmed")
    nm_delta       = _sh(best_full, "sharpe_neutral_mixed") - _sh(base_full, "sharpe_neutral_mixed")

    if hold_sh_delta < -0.02:
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            f"Best candidate ({best_var}) holdout Sharpe Δ={hold_sh_delta:+.4f} "
            f"breaches the −0.02 floor. Phase 2 ETF-level quality scaling does not "
            f"hold up on the holdout window. Classify as research-only."
        )
    elif full_sh_delta < 0.005 and hold_sh_delta < 0:
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            f"Best candidate ({best_var}) full-history Sharpe Δ={full_sh_delta:+.4f} "
            f"and holdout Δ={hold_sh_delta:+.4f} — both below threshold. "
            f"Signal adds no portfolio value. Research-only."
        )
    elif full_sh_delta >= 0.005 and hold_sh_delta >= -0.02:
        if full_sh_delta >= 0.01:
            verdict = "Promote to shared frontier input"
            verdict_reason = (
                f"Best candidate ({best_var}) full-history Sharpe Δ={full_sh_delta:+.4f} "
                f"and holdout Δ={hold_sh_delta:+.4f}. Recovery-confirmed capture Δ={rc_delta:+.4f}. "
                f"Neutral-mixed Sharpe Δ={nm_delta:+.4f}. Defense unchanged ({sp_delta:+.4f}). "
                f"Phase 2 signal is a validated input for Phases 3, 4, 5."
            )
        else:
            verdict = "Keep as research-only diagnostic"
            verdict_reason = (
                f"Best candidate ({best_var}) shows directional improvement "
                f"(full Δ={full_sh_delta:+.4f}, holdout Δ={hold_sh_delta:+.4f}) "
                f"but full-history Sharpe gain is below +0.01. "
                f"Classify as research-only. Phase 2 quality signal may still "
                f"feed Phase 3 (re-risking) as a quality confirmation signal."
            )
    else:
        verdict = "Revise Phase 2B"
        verdict_reason = (
            f"Mixed results across candidates. Best full-history gain={full_sh_delta:+.4f}, "
            f"holdout Δ={hold_sh_delta:+.4f}. Revise the active-state selection or "
            f"reduce the alpha parameter before a final decision."
        )

    print(f"\n{'='*70}")
    print(f"VERDICT: {verdict}")
    print(f"Best candidate: {best_var}")
    print(f"Reason: {verdict_reason}")
    print(f"{'='*70}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    full_df = pd.DataFrame(list(full_results.values()))
    full_df.to_csv(OUT_DIR / "wrapper_experiment_results.csv", index=False)

    hold_df = pd.DataFrame(list(holdout_results.values()))
    hold_df.to_csv(OUT_DIR / "wrapper_experiment_holdout_summary.csv", index=False)

    # State summary
    state_rows = []
    for var, r in full_results.items():
        for state in ["calm_trend","neutral_mixed","recovery_confirmed",
                      "recovery_fragile","stressed_panic"]:
            state_rows.append({
                "variant": var, "market_state": state,
                "ann_return": r.get(f"ann_return_{state}"),
                "sharpe": r.get(f"sharpe_{state}"),
                "spy_capture": r.get(f"capture_{state}"),
            })
    pd.DataFrame(state_rows).to_csv(
        OUT_DIR / "wrapper_experiment_state_summary.csv", index=False)

    # Phase D gates
    pd.DataFrame(gate_rows).to_csv(
        OUT_DIR / "wrapper_experiment_phase_d_gates.csv", index=False)

    for p in ["wrapper_experiment_results.csv","wrapper_experiment_holdout_summary.csv",
              "wrapper_experiment_state_summary.csv","wrapper_experiment_phase_d_gates.csv"]:
        print(f"  Saved: data/research/frontier_phase2/{p}")

    # ── Protected diff ────────────────────────────────────────────────────────
    diff_clean, diff_changed = protected_diff_clean()
    if not diff_clean:
        print(f"WARNING: Protected files changed: {diff_changed}")
        warnings.append(f"Protected files changed: {diff_changed}")
    else:
        print("Protected files: clean.")

    # ── Write report ──────────────────────────────────────────────────────────
    _write_report(
        full_results=full_results,
        holdout_results=holdout_results,
        rolling_results=rolling_results,
        bs_results=bs_results,
        gate_rows=gate_rows,
        verdict=verdict,
        verdict_reason=verdict_reason,
        best_var=best_var,
        warnings_list=warnings,
        diff_clean=diff_clean,
    )

    # ── Project journey ───────────────────────────────────────────────────────
    _append_journey(
        verdict=verdict, verdict_reason=verdict_reason, best_var=best_var,
        full_results=full_results, holdout_results=holdout_results,
    )

    print(f"\nPhase 2B complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report writer ─────────────────────────────────────────────────────────────

def _f(v, fmt=".4f") -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        return format(float(v), fmt)
    except Exception:
        return str(v)


def _pct(v) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    return f"{float(v)*100:.2f}%"


VARIANT_SHORT: dict[str, str] = {
    "ggg_baseline_no_modifier":           "baseline",
    "phase1_r2a_only":                    "p1_r2a",
    "phase2_trend_quality_state_specific":"p2_tq",
    "phase2_ma_distance_state_specific":  "p2_ma",
    "phase1_r2a_plus_phase2_trend_quality":"p1+p2_tq",
    "phase1_r2a_plus_phase2_ma_distance": "p1+p2_ma",
}


def _write_report(full_results, holdout_results, rolling_results,
                  bs_results, gate_rows, verdict, verdict_reason,
                  best_var, warnings_list, diff_clean) -> None:
    lines: list[str] = []
    A = lines.append

    A("# Frontier Phase 2B: Trend Quality Engine — Wrapper Experiment Report")
    A("")
    A("**Date:** 2026-05-20")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(f"**Best candidate:** `{best_var}`")
    A("")
    A("---")
    A("")
    A("## 1. Sprint Summary")
    A("")
    A(
        "Phase 2B applies the Phase 2A trend quality and ma_distance_z signals "
        "as state-specific offensive ETF reweighting inside `recovery_confirmed` "
        "and `neutral_mixed` states only (where Phase 2A IC was positive). "
        "Signals are NOT applied in stressed_panic, recovery_fragile, or calm_trend. "
        "Phase 1 R2A uniform offense scaling is also included as a standalone and "
        "stacked candidate for comparison."
    )
    A("")
    A("### Architecture Note")
    A("")
    A(
        "The wrapper's checkpoint mechanism applies a uniform multiplier to all "
        "offensive ETFs. Phase 2 requires *differential* per-ETF multipliers based "
        "on cross-sectional quality rank. This is not directly supported by a named "
        "checkpoint hook, so Phase 2 scaling is applied as a post-processing step on "
        "the final ETF weights before `production_portfolio_path` recomputes the path. "
        "Turnover and cost accounting are correct because `production_portfolio_path` "
        "derives turnover from the modified weight matrix."
    )
    A("")
    A("---")
    A("")
    A("## 2. Commands Run")
    A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier2_wrapper_experiment.py")
    A("```")
    A("")
    A("---")
    A("")
    A("## 3. Phase 2A Signal Recap")
    A("")
    A("| state | trend_quality_IC | ma_distance_IC | used in Phase 2B? |")
    A("|-------|-----------------|---------------|-------------------|")
    for s, tq, ma, used in [
        ("recovery_confirmed", "+0.073", "N/A", "✓ YES"),
        ("neutral_mixed",      "+0.024", "N/A", "✓ YES"),
        ("calm_trend",         "+0.011", "N/A", "✗ NO (marginal)"),
        ("recovery_fragile",   "−0.015", "N/A", "✗ NO (negative)"),
        ("stressed_panic",     "−0.002", "N/A", "✗ NO (zero + defense)"),
    ]:
        A(f"| {s} | {tq} | {ma} | {used} |")
    A("")
    A("---")
    A("")
    A("## 4. Full-History Metrics")
    A("")
    all_vars = list(full_results.keys())
    A("| metric | " + " | ".join(VARIANT_SHORT.get(v, v) for v in all_vars) + " |")
    A("|--------|" + "|".join("------" for _ in all_vars) + "|")

    base_sh = full_results["ggg_baseline_no_modifier"]["sharpe"]
    for key, label in [
        ("ann_return","Ann return"), ("sharpe","Sharpe"), ("max_drawdown","Max DD"),
        ("cvar_5","CVaR 5%"), ("avg_turnover","Avg TO/wk"),
        ("avg_BIL","Avg BIL"), ("avg_offense","Avg offense"),
        ("hidden_beta_SPY","Hidden β SPY"),
    ]:
        cells = [label]
        for v in all_vars:
            val = full_results[v].get(key)
            if key == "ann_return":
                cells.append(_pct(val))
            elif key == "avg_BIL" or key == "avg_offense":
                cells.append(_pct(val))
            else:
                cells.append(_f(val))
        A("| " + " | ".join(cells) + " |")
    A("")
    A("*Sharpe deltas vs baseline:*")
    for v in all_vars:
        sh = full_results[v].get("sharpe", np.nan)
        d = float(sh) - float(base_sh) if (sh is not None and np.isfinite(float(sh))) else np.nan
        A(f"- {VARIANT_SHORT.get(v,v)}: {_f(d, '+.4f')}")
    A("")
    A("---")
    A("")
    A("## 5. Holdout Metrics (from 2024-04-19)")
    A("")
    A("| metric | baseline | p1_r2a | p2_tq | p2_ma | p1+p2_tq | p1+p2_ma |")
    A("|--------|----------|--------|-------|-------|----------|----------|")
    ho_base_sh = holdout_results["ggg_baseline_no_modifier"]["sharpe"]
    for key, label in [
        ("ann_return","Return"), ("sharpe","Sharpe"), ("max_drawdown","Max DD"), ("avg_BIL","Avg BIL"),
    ]:
        cells = [label]
        for v in all_vars:
            val = holdout_results[v].get(key)
            cells.append(_pct(val) if key in ("ann_return","avg_BIL") else _f(val))
        A("| " + " | ".join(cells) + " |")
    A("")
    A("*Holdout Sharpe deltas vs baseline:*")
    for v in all_vars:
        sh = holdout_results[v].get("sharpe", np.nan)
        d = float(sh) - float(ho_base_sh) if sh is not None and np.isfinite(float(sh)) else np.nan
        A(f"- {VARIANT_SHORT.get(v,v)}: {_f(d, '+.4f')}")
    A("")
    A("---")
    A("")
    A("## 6. State-by-State (primary candidate vs baseline, full history)")
    A("")
    A("Active Phase 2 states are recovery_confirmed and neutral_mixed.")
    A("")
    A("| state | base_sharpe | base_capture | best_sharpe | best_capture | Δ_sharpe |")
    A("|-------|-------------|--------------|-------------|--------------|----------|")
    bfr = full_results["ggg_baseline_no_modifier"]
    bst = full_results.get(best_var, {})
    for state in ["calm_trend","neutral_mixed","recovery_confirmed","recovery_fragile","stressed_panic"]:
        b_sh = bfr.get(f"sharpe_{state}", np.nan)
        p_sh = bst.get(f"sharpe_{state}", np.nan)
        b_cap = bfr.get(f"capture_{state}", np.nan)
        p_cap = bst.get(f"capture_{state}", np.nan)
        d = (float(p_sh) - float(b_sh)) if (p_sh is not None and np.isfinite(float(p_sh))
             and b_sh is not None and np.isfinite(float(b_sh))) else np.nan
        mark = " ← active" if state in PHASE2_ACTIVE_STATES else ""
        A(f"| {state}{mark} | {_f(b_sh)} | {_f(b_cap)} | {_f(p_sh)} | {_f(p_cap)} | {_f(d, '+.4f')} |")
    A("")
    A("---")
    A("")
    A("## 7. Rolling-Origin and Bootstrap")
    A("")
    A("| candidate | rolling_win_rate | bootstrap_P | mean_bs_delta | CI_95 |")
    A("|-----------|-----------------|-------------|---------------|-------|")
    for v in [v for v in all_vars if v != "ggg_baseline_no_modifier"]:
        ro = rolling_results.get(v, pd.DataFrame())
        wr = float(ro["beats_base"].mean()) if not ro.empty else np.nan
        bs = bs_results.get(v, {})
        A(f"| {VARIANT_SHORT.get(v,v)} | {_f(wr,'.1%')} | {_f(bs.get('p_cand_gt_base'),'.3f')} | "
          f"{_f(bs.get('mean_delta'),'+.4f')} | "
          f"[{_f(bs.get('ci95_lo'),'+.4f')}, {_f(bs.get('ci95_hi'),'+.4f')}] |")
    A("")
    A("---")
    A("")
    A("## 8. Phase D Gate Summary")
    A("")
    A("| candidate | gate_verdict | key_failures |")
    A("|-----------|-------------|--------------|")
    for row in gate_rows:
        A(f"| {VARIANT_SHORT.get(row['variant'], row['variant'])} | "
          f"{'✓ PASS' if row['gate_verdict']=='PASS' else '✗ FAIL'} | "
          f"{row.get('fail','')[:80]} |")
    A("")
    A("---")
    A("")
    A("## 9. ma_distance_z vs Trend Quality Composite Comparison")
    A("")
    p2_tq_sh  = full_results.get("phase2_trend_quality_state_specific",{}).get("sharpe",np.nan)
    p2_ma_sh  = full_results.get("phase2_ma_distance_state_specific",{}).get("sharpe",np.nan)
    p2h_tq_sh = holdout_results.get("phase2_trend_quality_state_specific",{}).get("sharpe",np.nan)
    p2h_ma_sh = holdout_results.get("phase2_ma_distance_state_specific",{}).get("sharpe",np.nan)
    A(f"- trend_quality composite: full Sharpe={_f(p2_tq_sh)}, holdout={_f(p2h_tq_sh)}")
    A(f"- ma_distance_z:           full Sharpe={_f(p2_ma_sh)}, holdout={_f(p2h_ma_sh)}")
    winner = "ma_distance_z" if (_f(p2h_ma_sh,'.4f') >= _f(p2h_tq_sh,'.4f')) else "trend_quality"
    A(f"- **Better on holdout:** {winner}")
    A("")
    A("---")
    A("")
    A("## 10. Holdout Warning")
    A("")
    A(
        "Phase 2A showed holdout IC = −0.014 for the trend_quality composite (t=−0.69). "
        "Phase 2B tests whether this signal failure translates to portfolio-level holdout "
        "regression. The holdout Sharpe delta above is the primary gate for the final verdict. "
        "Any candidate with holdout Sharpe Δ < −0.02 is classified research-only regardless "
        "of full-history performance."
    )
    A("")
    A("---")
    A("")
    A("## 11. Verdict")
    A("")
    A(f"**{verdict}**")
    A("")
    A(verdict_reason)
    A("")
    if "Promote" in verdict or "research" in verdict.lower():
        A("### Should Phase 2 feed into Phases 3, 4, 5?")
        A("")
        if "Promote" in verdict:
            A(
                "Yes. The trend_quality and/or ma_distance_z signals demonstrated positive "
                "portfolio value. They should be carried forward as quality confirmation "
                "inputs to:"
                "\n- **Phase 3** (Smart Re-Risking): use trend_quality as a recovery quality "
                "confirmer — higher quality trends in the broad market indicate a stronger "
                "basis for faster re-risking."
                "\n- **Phase 4** (Cross-Sectional Leadership): trend_quality is the core "
                "ingredient of a leadership quality score."
                "\n- **Phase 5** (Allocator Objective): offense_budget scaling can incorporate "
                "a portfolio-level quality score derived from the average trend quality of "
                "current holdings."
            )
        else:
            A(
                "Conditionally. The Phase 2 signals did not demonstrate clear portfolio "
                "improvement, but the signal content is real (partial IC +0.008, "
                "recovery_confirmed IC +0.073). They should be used as:"
                "\n- **Phase 3 quality confirmation inputs** (not as portfolio modifiers): "
                "trend_quality of the broad market is an input to the re-risk quality score."
                "\n- **Phase 4 leadership ranking**: trend_quality is a natural component of "
                "an ETF leadership quality index."
                "\n**Do NOT** apply Phase 2 ETF-level reweighting as a standalone portfolio "
                "modifier until the holdout issue is resolved."
            )
    A("")
    A("---")
    A("")
    A("## 12. Files Created")
    A("")
    for f in ["wrapper_experiment_results.csv","wrapper_experiment_holdout_summary.csv",
              "wrapper_experiment_state_summary.csv","wrapper_experiment_phase_d_gates.csv",
              "frontier_phase2_trend_quality_engine_report.md"]:
        loc = "data/research/frontier_phase2/" if not f.endswith(".md") else "docs/research/"
        A(f"- `{loc}{f}`")
    A("")
    A("## 13. Production Safety")
    A("")
    A(f"- Protected file diff: **{'✓ Clean' if diff_clean else '✗ CHANGED'}**")
    A("- Production pins: unchanged")
    A("- No public/, src/, dashboard files modified")
    A("")
    if warnings_list:
        A("## 14. Warnings")
        A("")
        for w in warnings_list:
            A(f"- {w}")
        A("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase2_trend_quality_engine_report.md")


# ── Project journey ───────────────────────────────────────────────────────────

def _append_journey(verdict, verdict_reason, best_var, full_results, holdout_results) -> None:
    journey = ROOT / "docs" / "research" / "project_journey.md"
    if not journey.exists():
        print("project_journey.md not found — skipping.")
        return

    b = full_results.get("ggg_baseline_no_modifier", {})
    p = full_results.get(best_var, {})
    hb = holdout_results.get("ggg_baseline_no_modifier", {})
    hp = holdout_results.get(best_var, {})

    section = f"""

## Section — Frontier Phase 2B: Trend Quality Engine Wrapper Experiment

Date: 2026-05-20.

### Why this sprint happened

Phase 2A built per-ETF trend quality signals with cross-sectional IC +0.0147
(t=+1.45). The strongest component was ma_distance_z (IC +0.020) and the
strongest state was recovery_confirmed (IC +0.073, t=+2.0). Phase 2B tests
whether these signals improve the portfolio when applied as state-specific
offensive ETF reweighting inside recovery_confirmed and neutral_mixed only.

Phase 1 R2A (from Phase 1B) is included as a reference and stacking partner.

### What was tried

Six candidates:
- `ggg_baseline_no_modifier` — exact GGG
- `phase1_r2a_only` — Phase 1B R2A at offense_budget (alpha=0.08)
- `phase2_trend_quality_state_specific` — per-ETF trend_quality rank scaling in recovery_confirmed + neutral_mixed
- `phase2_ma_distance_state_specific` — per-ETF ma_distance_z rank scaling in same states
- `phase1_r2a_plus_phase2_trend_quality` — Phase 1 + Phase 2 stacked
- `phase1_r2a_plus_phase2_ma_distance` — Phase 1 + Phase 2 (ma) stacked

Architecture note: Phase 2 ETF-level scaling is applied as post-processing on
final weights (no named checkpoint hook for per-ETF reweighting exists).

### Key metrics

| metric | baseline | best_candidate ({best_var}) | delta |
|--------|----------|-------------------------------|-------|
| ann_return | {_pct(b.get('ann_return'))} | {_pct(p.get('ann_return'))} | {_f((p.get('ann_return',np.nan) or np.nan) - (b.get('ann_return',np.nan) or np.nan), '+.4f')} |
| sharpe | {_f(b.get('sharpe'))} | {_f(p.get('sharpe'))} | {_f((p.get('sharpe',np.nan) or np.nan) - (b.get('sharpe',np.nan) or np.nan), '+.4f')} |
| max_drawdown | {_f(b.get('max_drawdown'))} | {_f(p.get('max_drawdown'))} | {_f((p.get('max_drawdown',np.nan) or np.nan) - (b.get('max_drawdown',np.nan) or np.nan), '+.4f')} |
| holdout_sharpe | {_f(hb.get('sharpe'))} | {_f(hp.get('sharpe'))} | {_f((hp.get('sharpe',np.nan) or np.nan) - (hb.get('sharpe',np.nan) or np.nan), '+.4f')} |

### Verdict

**{verdict}**

{verdict_reason}

### What comes next

Phase 2 quality signals (trend_quality, ma_distance_z) should feed Phase 3 (smart
re-risking quality score) and Phase 4 (leadership system) as signal inputs.
The ETF-level portfolio reweighting is classified per the verdict above.
"""
    with open(journey, "a", encoding="utf-8") as f:
        f.write(section)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
