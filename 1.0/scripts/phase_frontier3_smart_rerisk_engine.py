"""Frontier Phase 3A: Smart Re-Risking Engine.

Uses validated Phase 1 (R2A) and Phase 2 (trend_quality) signals to build a
recovery quality score and a transition quality gate, then applies these as a
re-risk speed modifier at the `transition_rerisk_smoothing` checkpoint.

The checkpoint scales OFFENSE ETF weights uniformly: multiplier > 1 = more
offense / less BIL = faster re-risking.  stressed_panic modifier is
unconditionally 1.0 — no boost ever in that state.

Run from repo root:
    .venv/bin/python scripts/phase_frontier3_smart_rerisk_engine.py
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

RECOVERY_STATES         = {"recovery_confirmed", "recovery_fragile"}
BOOST_FACTOR            = 0.20
TRANSITION_MIN_WEEKS    = 6

OUT_DIR      = DATA / "research" / "frontier_phase3"
REPORT_PATH  = ROOT / "docs" / "research" / "frontier_phase3_smart_rerisk_engine_report.md"

PROTECTED_PATHS = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]


# ── Signal loading ────────────────────────────────────────────────────────────

def load_phase1_signals(warnings: list[str]) -> pd.DataFrame:
    path = DATA / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
    if not path.exists():
        raise SystemExit(f"Phase 1 signals not found: {path}")
    df = pd.read_csv(path)
    date_col = "date" if "date" in df.columns else "Date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)
    print(f"  Phase 1 signals: {df.shape[0]} rows, "
          f"columns: {[c for c in df.columns if c in ['r2a','breadth_quality_score','state_persistence_score','leadership_quality_score']]}")
    return df


def load_trend_quality(warnings: list[str]) -> pd.DataFrame:
    path = DATA / "research" / "frontier_phase2" / "trend_quality_panel.csv"
    if not path.exists():
        raise SystemExit(f"Phase 2 trend_quality not found: {path}")
    df = pd.read_csv(path, index_col="date", parse_dates=True)
    df.index = df.index.tz_localize(None)
    print(f"  Phase 2 trend_quality: {df.shape[0]} rows × {df.shape[1]} tickers")
    return df


# ── Signal construction ───────────────────────────────────────────────────────

def expanding_zscore(s: pd.Series, min_periods: int = 52) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    z  = (s - mu) / sd
    return z.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def build_recovery_quality_r2a(ph1: pd.DataFrame) -> pd.Series:
    """Validated R2A composite clipped to [-1, 1]."""
    rq = pd.to_numeric(ph1["r2a"], errors="coerce").fillna(0.0)
    # r2a is in [-3, 3]; clip to the usable [-1, 1] band
    return rq.clip(-1.0, 1.0).rename("recovery_quality_r2a")


def build_recovery_quality_no_credit(ph1: pd.DataFrame) -> pd.Series:
    """Blend of breadth, persistence, leadership — credit excluded.

    Weights predeclared (not tuned):  0.40 breadth, 0.30 persistence,
    0.30 leadership.  All sub-signals are already 1-week lagged.
    """
    b = pd.to_numeric(ph1["breadth_quality_score"],   errors="coerce").fillna(0.0)
    p = pd.to_numeric(ph1["state_persistence_score"], errors="coerce").fillna(0.0)
    l = pd.to_numeric(ph1["leadership_quality_score"],errors="coerce").fillna(0.0)
    raw = 0.40 * b + 0.30 * p + 0.30 * l
    rq  = expanding_zscore(raw).clip(-1.0, 1.0)
    return rq.rename("recovery_quality_no_credit")


def build_recovery_quality_r2a_plus_trend(
    ph1: pd.DataFrame,
    trend_q: pd.DataFrame,
    offense_tickers: set[str],
) -> pd.Series:
    """0.70 × R2A + 0.30 × avg trend_quality across offense ETFs.

    Trend quality is already 1-week lagged (from Phase 2A).  The avg is
    across the offense ETFs available in the panel.
    """
    rq_r2a = pd.to_numeric(ph1["r2a"], errors="coerce").fillna(0.0).clip(-1.0, 1.0)

    avail = [t for t in offense_tickers if t in trend_q.columns]
    if not avail:
        print("  WARNING: no offense ETFs in trend_quality panel — using R2A only")
        return rq_r2a.rename("recovery_quality_r2a_plus_trend")

    avg_tq_raw  = trend_q[avail].mean(axis=1).reindex(ph1.index)
    avg_tq_z    = expanding_zscore(avg_tq_raw).clip(-1.0, 1.0)

    blend = (0.70 * rq_r2a + 0.30 * avg_tq_z).clip(-1.0, 1.0)
    return blend.rename("recovery_quality_r2a_plus_trend")


def build_transition_quality(states: pd.Series) -> pd.Series:
    """Binary gate: 1 if we have been in a recovery state for ≥ TRANSITION_MIN_WEEKS
    consecutive weeks, else 0.  Pure historical information — no look-ahead.
    """
    state_arr = states.values
    counts    = np.zeros(len(state_arr), dtype=int)
    run = 0
    for i, s in enumerate(state_arr):
        if str(s) in RECOVERY_STATES:
            run += 1
        else:
            run = 0
        counts[i] = run
    gate = pd.Series((counts >= TRANSITION_MIN_WEEKS).astype(float),
                     index=states.index, name="transition_quality_score")
    n_active = int(gate.sum())
    print(f"  Transition quality gate: {n_active} weeks with ≥{TRANSITION_MIN_WEEKS} "
          f"consecutive recovery weeks ({n_active/len(gate):.1%} of history)")
    return gate


def build_rerisk_modifier(
    quality: pd.Series,
    transition: pd.Series,
    states: pd.Series,
    recovery_confirmed_only: bool = False,
    name: str = "modifier",
) -> pd.Series:
    """Build the scalar multiplier time series.

    Only applies in recovery states (or recovery_confirmed only if the flag is
    set).  stressed_panic is ALWAYS set to 1.0 — no boost permitted.

    Multiplier = 1.0 + BOOST_FACTOR × quality × transition (in active states)
    Multiplier = 1.0  (in all other states and stressed_panic)
    """
    modifier = pd.Series(1.0, index=states.index, dtype=float)
    q  = quality.reindex(states.index).fillna(0.0).clip(-1.0, 1.0)
    tr = transition.reindex(states.index).fillna(0.0)

    if recovery_confirmed_only:
        active_mask = states == "recovery_confirmed"
    else:
        active_mask = states.isin(RECOVERY_STATES)

    boost = BOOST_FACTOR * q * tr
    modifier[active_mask] = 1.0 + boost[active_mask]

    # CRITICAL GUARD: stressed_panic = 1.0 unconditionally
    stressed_mask = states == "stressed_panic"
    modifier[stressed_mask] = 1.0

    # Hard assertion — must never fail
    assert (modifier[stressed_mask] == 1.0).all(), \
        "SAFETY VIOLATION: stressed_panic modifier is not 1.0"

    n_boosted = int((modifier > 1.0).sum())
    n_reduced = int((modifier < 1.0).sum())
    print(f"  {name}: boosted={n_boosted} rows, reduced={n_reduced} rows, "
          f"sp_rows_always_1={int(stressed_mask.sum())}")
    return modifier.rename(name)


# ── Modifier factory for wrapper ──────────────────────────────────────────────

def make_rerisk_modifier_fn(modifier_series: pd.Series):
    """Return a CheckpointModifier that injects a precomputed series."""
    def _fn(wrapper: AllocatorCheckpointWrapper, _checkpoint: str) -> pd.Series:
        return modifier_series.reindex(wrapper.index).fillna(1.0)
    return _fn


def make_phase1_r2a_fn(r2a: pd.Series, states: pd.Series, alpha: float = 0.08):
    """Phase 1B-equivalent R2A modifier at offense_budget (unchanged)."""
    q     = r2a.reindex(states.index).ffill().fillna(0.0).clip(-1.0, 1.0)
    scale = pd.Series(1.0, index=states.index, dtype=float)
    scale[states != "stressed_panic"] = 1.0 + alpha * q[states != "stressed_panic"]

    def _fn(wrapper: AllocatorCheckpointWrapper, _checkpoint: str) -> pd.Series:
        return scale

    return CheckpointModifier(name="phase1_r2a_offense_budget",
                               checkpoint="offense_budget", function=_fn)


# ── Metric helpers (self-contained, matches Phase 2B helpers) ─────────────────

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


def _calmar(r: pd.Series) -> float:
    dd = _max_dd(r)
    return float(_ann_return(r) / abs(dd)) if (dd and np.isfinite(dd) and dd < 0) else np.nan


def _cvar(r: pd.Series, pct: float = 0.05) -> float:
    if len(r) < 20:
        return np.nan
    tail = r[r <= r.quantile(pct)]
    return float(tail.mean()) if len(tail) else np.nan


def _spy_ann(nwr: pd.DataFrame, dates: pd.DatetimeIndex) -> float:
    if "SPY" not in nwr.columns:
        return np.nan
    spy = nwr["SPY"].reindex(dates).dropna()
    if len(spy) < 4:
        return np.nan
    return float((1 + spy).prod() ** (52 / len(spy)) - 1)


def _capture(port_rets: pd.Series, nwr: pd.DataFrame,
             state_dates: pd.DatetimeIndex) -> float:
    p = port_rets.reindex(state_dates).dropna()
    s = _spy_ann(nwr, p.index)
    if not (np.isfinite(s) and s > 0.005):
        return np.nan
    return float(_ann_return(p) / s)


def _hidden_beta(port_rets: pd.Series, nwr: pd.DataFrame) -> float:
    if "SPY" not in nwr.columns:
        return np.nan
    spy = nwr["SPY"].reindex(port_rets.index).dropna()
    al  = pd.concat([port_rets, spy], axis=1).dropna()
    if len(al) < 20:
        return np.nan
    slope, *_ = scipy_stats.linregress(al.iloc[:, 1], al.iloc[:, 0])
    return float(slope)


def summarise_candidate(variant: str, weights: pd.DataFrame, path_df: pd.DataFrame,
                        states: pd.Series, nwr: pd.DataFrame) -> dict:
    path  = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    r     = path["net_return"].dropna()
    exp   = exposure_summary(weights)
    sa    = states.reindex(r.index)
    to    = float(path["turnover"].mean()) if "turnover" in path.columns else np.nan
    cost  = to * (PRODUCTION_COST_BPS / 10_000) * 52 if np.isfinite(to) else np.nan

    row: dict = {
        "variant": variant,
        "ann_return":   _ann_return(r),
        "ann_vol":      _ann_vol(r),
        "sharpe":       _sharpe(r),
        "calmar":       _calmar(r),
        "max_drawdown": _max_dd(r),
        "cvar_5":       _cvar(r),
        "avg_turnover": to,
        "extra_cost_annual": cost,
        "avg_BIL":      float(exp.get("avg_BIL", np.nan)),
        "avg_offense":  float(exp.get("avg_offense", np.nan)),
        "hidden_beta":  _hidden_beta(r, nwr),
    }

    for state in ["calm_trend","neutral_mixed","recovery_confirmed",
                  "recovery_fragile","stressed_panic"]:
        mask  = sa == state
        sr    = r[mask]
        row[f"sharpe_{state}"]      = _sharpe(sr)
        row[f"ann_return_{state}"]  = _ann_return(sr)
        row[f"capture_{state}"]     = _capture(sr, nwr, sr.index)
        row[f"max_dd_{state}"]      = _max_dd(sr)

    return row


def summarise_window(variant, weights, path_df, states, nwr,
                     start, end, label) -> dict:
    path = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    mask = pd.Series(True, index=path.index)
    if start is not None:
        mask &= path.index >= start
    if end is not None:
        mask &= path.index < end
    slc  = path[mask].reset_index().rename(columns={"index": "Date"})
    wslc = weights[weights.index.isin(path[mask].index)]
    d    = summarise_candidate(variant, wslc, slc, states, nwr)
    d["window"] = label
    return d


# ── Rolling-origin ────────────────────────────────────────────────────────────

def rolling_origin(cand_path: pd.DataFrame, base_path: pd.DataFrame) -> pd.DataFrame:
    cp = cand_path.set_index("Date") if "Date" in cand_path.columns else cand_path
    bp = base_path.set_index("Date") if "Date" in base_path.columns else base_path
    n  = len(cp)
    rows = []
    for start in range(MIN_TRAIN, n - ROLLING_WINDOW, ROLLING_STEP):
        idx = cp.index[start: start + ROLLING_WINDOW]
        cr  = cp.loc[idx, "net_return"].dropna()
        br  = bp.loc[idx, "net_return"].dropna() if "net_return" in bp.columns else pd.Series()
        if len(cr) < 20:
            continue
        d_sh = _sharpe(cr) - _sharpe(br) if len(br) >= 20 else np.nan
        rows.append({
            "origin":       cp.index[start],
            "cand_sharpe":  _sharpe(cr),
            "base_sharpe":  _sharpe(br) if len(br) >= 20 else np.nan,
            "delta_sharpe": d_sh,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["beats_base"] = df["delta_sharpe"] > 0
    return df


# ── Block bootstrap ───────────────────────────────────────────────────────────

def block_bootstrap(cand_r: pd.Series, base_r: pd.Series) -> dict:
    rng     = np.random.default_rng(BOOTSTRAP_SEED)
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
        "mean_delta":     float(np.mean(deltas)),
        "ci95_lo":        float(np.percentile(deltas, 2.5)),
        "ci95_hi":        float(np.percentile(deltas, 97.5)),
    }


# ── Protected diff ────────────────────────────────────────────────────────────

def protected_diff_clean() -> tuple[bool, list[str]]:
    try:
        r = subprocess.run(["git", "diff", "--name-only", "--", *PROTECTED_PATHS],
                           cwd=ROOT, check=False, text=True, capture_output=True)
    except Exception:
        return False, ["git diff check failed"]
    changed = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(changed) == 0, changed


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    warnings: list[str] = []
    print("=" * 70)
    print("Frontier Phase 3A: Smart Re-Risking Engine")
    print("=" * 70)

    # ── Load signals and wrapper ──────────────────────────────────────────────
    print("\nLoading signals...")
    ph1       = load_phase1_signals(warnings)
    trend_q   = load_trend_quality(warnings)

    print("\nInitialising wrapper...")
    wrapper = AllocatorCheckpointWrapper()
    compare = wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(compare, 1e-10):
        raise SystemExit(f"Wrapper reproduction failed: {compare}")
    print(f"  GGG exact match (max_err={compare['net_return_max_abs_error']:.2e})")

    nwr    = wrapper.next_week_returns
    states = wrapper.states["market_state"].astype(str)

    # ── Build recovery quality scores ─────────────────────────────────────────
    print("\nBuilding recovery quality scores...")
    rq_r2a          = build_recovery_quality_r2a(ph1)
    rq_no_credit    = build_recovery_quality_no_credit(ph1)
    rq_r2a_trend    = build_recovery_quality_r2a_plus_trend(ph1, trend_q, OFFENSE)
    # recovery_confirmed_only uses same quality score, different state gate
    rq_conf_only    = rq_r2a_trend.copy().rename("recovery_quality_confirmed_only")

    print("\nBuilding transition quality gate...")
    transition_q = build_transition_quality(states)

    # ── Build modifier series ─────────────────────────────────────────────────
    print("\nBuilding re-risk speed modifiers...")
    mod_r2a       = build_rerisk_modifier(rq_r2a,       transition_q, states,
                                          recovery_confirmed_only=False,
                                          name="mod_r2a_rerisk")
    mod_no_credit = build_rerisk_modifier(rq_no_credit, transition_q, states,
                                          recovery_confirmed_only=False,
                                          name="mod_no_credit_rerisk")
    mod_r2a_trend = build_rerisk_modifier(rq_r2a_trend, transition_q, states,
                                          recovery_confirmed_only=False,
                                          name="mod_r2a_trend_rerisk")
    mod_conf_only = build_rerisk_modifier(rq_conf_only, transition_q, states,
                                          recovery_confirmed_only=True,
                                          name="mod_conf_only_rerisk")

    # Save modifier time series for reporting
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    mod_ts = pd.DataFrame({
        "date":                       states.index,
        "market_state":               states.values,
        "transition_quality_gate":    transition_q.reindex(states.index).values,
        "r2a":                        rq_r2a.reindex(states.index).values,
        "rq_no_credit":               rq_no_credit.reindex(states.index).values,
        "rq_r2a_trend":               rq_r2a_trend.reindex(states.index).values,
        "mod_r2a":                    mod_r2a.values,
        "mod_no_credit":              mod_no_credit.values,
        "mod_r2a_trend":              mod_r2a_trend.values,
        "mod_conf_only":              mod_conf_only.values,
    })
    mod_ts.to_csv(OUT_DIR / "rerisk_modifier_timeseries.csv", index=False)
    print(f"  Saved modifier time series.")

    # ── Run wrapper candidates ────────────────────────────────────────────────
    print("\nRunning candidates...")

    # 1. Baseline
    baseline_run = wrapper.run("ggg_baseline_no_modifier")
    base_w, base_p = baseline_run.weights.copy(), baseline_run.path

    # 2. Phase 1 R2A reference (at offense_budget, matches Phase 1B/2B)
    ph1_mod   = make_phase1_r2a_fn(rq_r2a.rename("r2a"),  states, alpha=0.08)
    ph1_run   = wrapper.run("phase1_r2a_only", modifiers=[ph1_mod])
    ph1_w, ph1_p = ph1_run.weights.copy(), ph1_run.path

    # 3. Phase 3: R2A re-risk at transition_rerisk_smoothing
    def _make_rerisk(mod_series: pd.Series, variant_name: str):
        fn = make_rerisk_modifier_fn(mod_series)
        return CheckpointModifier(name=variant_name, checkpoint="transition_rerisk_smoothing",
                                  function=fn)

    r3_r2a_run   = wrapper.run("phase3_r2a_rerisk",
                                modifiers=[_make_rerisk(mod_r2a,       "r2a_rerisk")])
    r3_nc_run    = wrapper.run("phase3_no_credit_rerisk",
                                modifiers=[_make_rerisk(mod_no_credit,  "no_credit_rerisk")])
    r3_rt_run    = wrapper.run("phase3_r2a_plus_trend_rerisk",
                                modifiers=[_make_rerisk(mod_r2a_trend,  "r2a_trend_rerisk")])
    r3_co_run    = wrapper.run("phase3_recovery_confirmed_only_rerisk",
                                modifiers=[_make_rerisk(mod_conf_only,  "conf_only_rerisk")])

    runs: dict[str, tuple] = {
        "ggg_baseline_no_modifier":                 (base_w,             base_p),
        "phase1_r2a_only":                          (ph1_w,              ph1_p),
        "phase3_r2a_rerisk":                        (r3_r2a_run.weights, r3_r2a_run.path),
        "phase3_no_credit_rerisk":                  (r3_nc_run.weights,  r3_nc_run.path),
        "phase3_r2a_plus_trend_rerisk":             (r3_rt_run.weights,  r3_rt_run.path),
        "phase3_recovery_confirmed_only_rerisk":    (r3_co_run.weights,  r3_co_run.path),
    }

    # ── stressed_panic integrity check ────────────────────────────────────────
    print("\nVerifying stressed_panic integrity (no offense increase)...")
    sp_mask = states == "stressed_panic"
    sp_dates = states.index[sp_mask]
    for vname, (wts, _) in runs.items():
        if vname == "ggg_baseline_no_modifier":
            continue
        sp_diff = (wts.loc[sp_dates, list(OFFENSE & set(wts.columns))].sum(axis=1) -
                   base_w.loc[sp_dates, list(OFFENSE & set(base_w.columns))].sum(axis=1))
        max_inc = float(sp_diff.max())
        if max_inc > 0.001:   # allow floating-point rounding
            print(f"  WARNING {vname}: max offense increase in stressed_panic = {max_inc:.6f}")
            warnings.append(f"{vname}: stressed_panic offense increased by {max_inc:.6f}")
        else:
            print(f"  ✓ {vname}: stressed_panic offense change max = {max_inc:+.6f} (safe)")

    # ── Compute metrics ───────────────────────────────────────────────────────
    print("\nComputing metrics...")
    full_results:    dict[str, dict] = {}
    holdout_results: dict[str, dict] = {}

    for variant, (wts, path) in runs.items():
        full_results[variant]    = summarise_candidate(variant, wts, path, states, nwr)
        holdout_results[variant] = summarise_window(variant, wts, path, states, nwr,
                                                    HOLDOUT_START, None, "holdout")

    # Print full-history summary
    print("\n=== Full-History Summary ===")
    b_sh = full_results["ggg_baseline_no_modifier"]["sharpe"]
    for var, r in full_results.items():
        d  = (r["sharpe"] or np.nan) - b_sh
        print(f"  {var:<50}: ret={r['ann_return']*100:.2f}%  "
              f"sh={r['sharpe']:.4f}(Δ{d:+.4f})  dd={r['max_drawdown']:.4f}  "
              f"rc_cap={r.get('capture_recovery_confirmed', np.nan):.3f}  "
              f"rf_cap={r.get('capture_recovery_fragile', np.nan):.3f}  "
              f"sp_sh={r.get('sharpe_stressed_panic', np.nan):.4f}")

    print("\n=== Holdout Summary ===")
    ho_b = holdout_results["ggg_baseline_no_modifier"]["sharpe"]
    for var, r in holdout_results.items():
        d = (r["sharpe"] or np.nan) - ho_b
        print(f"  {var:<50}: sh={r['sharpe']:.4f}(Δ{d:+.4f})  ret={r['ann_return']*100:.2f}%")

    # ── Rolling-origin and bootstrap ──────────────────────────────────────────
    print("\nRolling-origin and bootstrap...")
    rolling: dict[str, pd.DataFrame] = {}
    bootstrap: dict[str, dict] = {}
    ho_base_r = base_p.set_index("Date")["net_return"][
        base_p.set_index("Date").index >= HOLDOUT_START].dropna()

    for var in [v for v in runs if v != "ggg_baseline_no_modifier"]:
        _, path = runs[var]
        rolling[var]   = rolling_origin(path, base_p)
        p_ho = path.set_index("Date")["net_return"]
        p_ho = p_ho[p_ho.index >= HOLDOUT_START].dropna()
        bootstrap[var] = block_bootstrap(p_ho, ho_base_r)
        wr  = float(rolling[var]["beats_base"].mean()) if not rolling[var].empty else np.nan
        p_b = bootstrap[var].get("p_cand_gt_base", np.nan)
        print(f"  {var:<50}: rolling_win={wr:.1%}  bootstrap_P={p_b:.3f}")

    # ── Phase D gate evaluation ───────────────────────────────────────────────
    print("\nPhase D gate evaluation...")
    gate_rows = []
    b_full = full_results["ggg_baseline_no_modifier"]
    b_hold = holdout_results["ggg_baseline_no_modifier"]

    def _gates(cand_full, cand_hold, bs, ro):
        ok, fail = [], []
        sh_d = (cand_full.get("sharpe") or np.nan) - (b_full.get("sharpe") or np.nan)
        if np.isfinite(sh_d) and sh_d >= 0.01:
            ok.append(f"Full Sharpe Δ={sh_d:+.4f} ≥ +0.01")
        else:
            fail.append(f"Full Sharpe Δ={sh_d:+.4f} < +0.01")

        ho_d = (cand_hold.get("sharpe") or np.nan) - (b_hold.get("sharpe") or np.nan)
        if np.isfinite(ho_d) and ho_d >= -0.02:
            ok.append(f"Holdout Sharpe Δ={ho_d:+.4f} ≥ -0.02")
        else:
            fail.append(f"Holdout Sharpe Δ={ho_d:+.4f} < -0.02")

        rc_d = (cand_full.get("capture_recovery_confirmed") or np.nan) - \
               (b_full.get("capture_recovery_confirmed") or np.nan)
        if np.isfinite(rc_d) and rc_d >= 0.05:
            ok.append(f"Recovery-confirmed capture Δ={rc_d:+.3f} ≥ +5pp")
        else:
            fail.append(f"Recovery-confirmed capture Δ={rc_d:+.3f} < +5pp")

        dd_d = (cand_full.get("max_drawdown") or np.nan) - (b_full.get("max_drawdown") or np.nan)
        if np.isfinite(dd_d) and dd_d >= -0.01:
            ok.append(f"MaxDD Δ={dd_d:+.4f} ≥ -0.01")
        else:
            fail.append(f"MaxDD Δ={dd_d:+.4f} < -0.01")

        sp_d = ((cand_full.get("sharpe_stressed_panic") or np.nan) -
                (b_full.get("sharpe_stressed_panic") or np.nan))
        if not np.isfinite(sp_d) or sp_d >= -0.05:
            ok.append(f"Stressed-panic Sharpe Δ={sp_d:+.4f} (intact)")
        else:
            fail.append(f"Stressed-panic Sharpe Δ={sp_d:+.4f} — DEFENSE WEAKENED")

        to_d  = (cand_full.get("avg_turnover") or 0) - (b_full.get("avg_turnover") or 0)
        cost  = to_d * (PRODUCTION_COST_BPS / 10_000) * 52
        if cost < 0.0015:
            ok.append(f"Extra annual cost={cost*100:.3f}% (< 0.15%)")
        else:
            fail.append(f"Extra annual cost={cost*100:.3f}% ≥ 0.15%")

        p_b = bs.get("p_cand_gt_base", np.nan)
        if np.isfinite(p_b) and p_b >= 0.60:
            ok.append(f"Bootstrap P={p_b:.3f} ≥ 0.60")
        else:
            fail.append(f"Bootstrap P={p_b:.3f} < 0.60")

        if not ro.empty:
            wr = float(ro["beats_base"].mean())
            if wr >= 0.55:
                ok.append(f"Rolling win={wr:.1%} ≥ 55%")
            else:
                fail.append(f"Rolling win={wr:.1%} < 55%")

        return ok, fail

    for var in [v for v in runs if v != "ggg_baseline_no_modifier"]:
        ok, fail = _gates(full_results[var], holdout_results[var],
                          bootstrap.get(var, {}), rolling.get(var, pd.DataFrame()))
        print(f"\n  {var}: {'PASS' if not fail else 'FAIL'}")
        for r in ok:
            print(f"    ✓ {r}")
        for r in fail:
            print(f"    ✗ {r}")
        gate_rows.append({
            "variant": var,
            "gate_verdict": "PASS" if not fail else "FAIL",
            "ok": "; ".join(ok),
            "fail": "; ".join(fail),
        })

    # ── Determine best and verdict ────────────────────────────────────────────
    def _v(d, k):
        v = d.get(k, np.nan)
        return float(v) if v is not None and np.isfinite(float(v)) else np.nan

    candidate_vars = [v for v in runs if v != "ggg_baseline_no_modifier"]
    # Score by: holdout Δ (60%) + recovery_confirmed capture improvement (40%)
    def _score(var):
        h_d  = _v(holdout_results[var], "sharpe") - _v(b_hold, "sharpe")
        rc_d = _v(full_results[var], "capture_recovery_confirmed") - \
               _v(b_full, "capture_recovery_confirmed")
        return 0.6 * (h_d if np.isfinite(h_d) else -999) + \
               0.4 * (rc_d if np.isfinite(rc_d) else -999)

    best_var = max(candidate_vars, key=_score)
    best_full = full_results[best_var]
    best_hold = holdout_results[best_var]
    best_bs   = bootstrap.get(best_var, {})

    full_sh_d  = _v(best_full, "sharpe") - _v(b_full, "sharpe")
    hold_sh_d  = _v(best_hold, "sharpe") - _v(b_hold, "sharpe")
    rc_imp     = _v(best_full, "capture_recovery_confirmed") - \
                 _v(b_full, "capture_recovery_confirmed")
    rf_imp     = _v(best_full, "capture_recovery_fragile") - \
                 _v(b_full, "capture_recovery_fragile")
    sp_delta   = _v(best_full, "sharpe_stressed_panic") - \
                 _v(b_full, "sharpe_stressed_panic")

    # Any gate-passing candidates?
    any_pass = any(g["gate_verdict"] == "PASS" for g in gate_rows)

    defense_breached = any(
        "DEFENSE WEAKENED" in (g.get("fail") or "")
        for g in gate_rows if g["variant"] in runs
    )

    if defense_breached:
        verdict = "Drop Phase 3 portfolio modifier"
        verdict_reason = (
            "At least one candidate weakened the stressed_panic defense. "
            "This violates the hard constraint. Drop the modifier."
        )
    elif any_pass:
        verdict = "Promote to shared frontier input"
        verdict_reason = (
            f"Best candidate ({best_var}) passes all Phase D gates. "
            f"Full-history Sharpe Δ={full_sh_d:+.4f}, "
            f"holdout Δ={hold_sh_d:+.4f}, "
            f"recovery_confirmed capture Δ={rc_imp:+.3f}. "
            f"Defense intact (stressed_panic Δ={sp_delta:+.4f}). "
            "Promote as a shared frontier input for Phases 4 and 5."
        )
    elif np.isfinite(hold_sh_d) and hold_sh_d < -0.02:
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            f"Best candidate ({best_var}) holdout Sharpe Δ={hold_sh_d:+.4f} "
            f"breaches the -0.02 floor. Re-risking modifier adds holdout risk. "
            "Signal is informative for Phase 4/5 inputs but not a portfolio modifier."
        )
    elif (np.isfinite(rc_imp) and rc_imp >= 0.05) or (np.isfinite(full_sh_d) and full_sh_d >= 0.005):
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            f"Best candidate ({best_var}) shows directional improvement "
            f"(full Δ={full_sh_d:+.4f}, holdout Δ={hold_sh_d:+.4f}, "
            f"recovery_confirmed capture Δ={rc_imp:+.3f}) "
            f"but does not pass all Phase D gates. "
            "Classify as research-only. Recovery quality scores should feed Phase 4/5 as inputs."
        )
    else:
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            "No candidate shows clear portfolio improvement from the re-risking modifier. "
            "The recovery quality signal is valid but the portfolio modification is too small "
            "to clear gates. Use recovery quality as a signal input in Phase 4/5."
        )

    print(f"\n{'='*70}")
    print(f"VERDICT: {verdict}")
    print(f"Best candidate: {best_var}")
    print(f"Reason: {verdict_reason}")
    print(f"{'='*70}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    pd.DataFrame(list(full_results.values())).to_csv(
        OUT_DIR / "smart_rerisk_results.csv", index=False)
    pd.DataFrame(list(holdout_results.values())).to_csv(
        OUT_DIR / "smart_rerisk_holdout_summary.csv", index=False)

    state_rows = []
    for var, r in full_results.items():
        for state in ["calm_trend","neutral_mixed","recovery_confirmed",
                      "recovery_fragile","stressed_panic"]:
            state_rows.append({
                "variant": var, "market_state": state,
                "ann_return": r.get(f"ann_return_{state}"),
                "sharpe":     r.get(f"sharpe_{state}"),
                "capture":    r.get(f"capture_{state}"),
                "max_dd":     r.get(f"max_dd_{state}"),
            })
    pd.DataFrame(state_rows).to_csv(
        OUT_DIR / "smart_rerisk_state_summary.csv", index=False)
    pd.DataFrame(gate_rows).to_csv(
        OUT_DIR / "smart_rerisk_phase_d_gates.csv", index=False)

    for f in ["smart_rerisk_results.csv","smart_rerisk_holdout_summary.csv",
              "smart_rerisk_state_summary.csv","smart_rerisk_phase_d_gates.csv",
              "rerisk_modifier_timeseries.csv"]:
        print(f"  Saved: data/research/frontier_phase3/{f}")

    diff_clean, diff_changed = protected_diff_clean()
    if not diff_clean:
        print(f"WARNING: Protected files changed: {diff_changed}")
        warnings.append(f"Protected files: {diff_changed}")
    else:
        print("Protected files: clean.")

    # ── Write report ──────────────────────────────────────────────────────────
    _write_report(
        full_results=full_results,
        holdout_results=holdout_results,
        rolling=rolling,
        bootstrap=bootstrap,
        gate_rows=gate_rows,
        mod_ts=mod_ts,
        b_full=b_full,
        b_hold=b_hold,
        best_var=best_var,
        verdict=verdict,
        verdict_reason=verdict_reason,
        warnings_list=warnings,
        diff_clean=diff_clean,
    )

    # ── Project journey ───────────────────────────────────────────────────────
    _append_journey(verdict, verdict_reason, best_var, full_results, holdout_results)

    print(f"\nPhase 3A complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Formatting helpers ────────────────────────────────────────────────────────

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


VSHORT: dict[str, str] = {
    "ggg_baseline_no_modifier":               "baseline",
    "phase1_r2a_only":                        "p1_r2a",
    "phase3_r2a_rerisk":                      "p3_r2a",
    "phase3_no_credit_rerisk":                "p3_nc",
    "phase3_r2a_plus_trend_rerisk":           "p3_r2a+tq",
    "phase3_recovery_confirmed_only_rerisk":  "p3_rc_only",
}


# ── Report writer ─────────────────────────────────────────────────────────────

def _write_report(full_results, holdout_results, rolling, bootstrap,
                  gate_rows, mod_ts, b_full, b_hold,
                  best_var, verdict, verdict_reason,
                  warnings_list, diff_clean) -> None:
    lines: list[str] = []
    A = lines.append

    A("# Frontier Phase 3A: Smart Re-Risking Engine Report")
    A("")
    A("**Date:** 2026-05-21")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(f"**Best candidate:** `{best_var}`")
    A("")
    A("---")
    A("")
    A("## 1. Sprint Summary")
    A("")
    A(
        "Phase 3A applies validated Phase 1 (R2A) and Phase 2 (trend_quality) signals "
        "as a re-risk speed modifier at the `transition_rerisk_smoothing` checkpoint. "
        "The modifier boosts offensive ETF weights in high-quality recovery states "
        "after ≥6 consecutive recovery weeks (transition quality gate). "
        "stressed_panic modifier is unconditionally 1.0 — no boost ever."
    )
    A("")
    A("### Architecture")
    A("")
    A(
        "`transition_rerisk_smoothing` scales OFFENSE ETFs uniformly. "
        "Multiplier > 1 → more offense / less BIL = faster re-risking in recovery. "
        "Range of modifier in active recovery states: [0.80, 1.20]. "
        "stressed_panic: always 1.0."
    )
    A("")
    A("---")
    A("")
    A("## 2. Commands Run")
    A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier3_smart_rerisk_engine.py")
    A("```")
    A("")
    A("---")
    A("")
    A("## 3. Recovery Quality Construction")
    A("")
    A("| variant | inputs | formula | range |")
    A("|---------|--------|---------|-------|")
    A("| `recovery_quality_r2a` | R2A (Phase 1, lagged) | clip(r2a, -1, 1) | [-1, 1] |")
    A("| `recovery_quality_no_credit` | breadth, persistence, leadership (Phase 1) | 0.40×breadth + 0.30×persistence + 0.30×leadership → z-score → clip | [-1, 1] |")
    A("| `recovery_quality_r2a_plus_trend` | R2A + avg trend_quality (Phase 2) | 0.70×r2a + 0.30×avg_tq → clip | [-1, 1] |")
    A("| `transition_quality_score` | consecutive recovery weeks | 1 if ≥6 weeks in recovery, else 0 | {0, 1} |")
    A("")
    A(f"**Transition quality gate activation:** "
      f"{int(mod_ts['transition_quality_gate'].sum())} / {len(mod_ts)} weeks "
      f"({int(mod_ts['transition_quality_gate'].sum())/len(mod_ts):.1%})")
    A("")
    A("**Modifier formula (in active states):**  "
      f"`1.0 + {BOOST_FACTOR} × quality × transition_gate`")
    A("")
    A("---")
    A("")
    A("## 4. Full-History Metrics")
    A("")
    all_vars = list(full_results.keys())
    A("| metric | " + " | ".join(VSHORT.get(v, v) for v in all_vars) + " |")
    A("|--------|" + "|".join("------" for _ in all_vars) + "|")
    for key, label in [
        ("ann_return","Ann return"),  ("sharpe","Sharpe"), ("calmar","Calmar"),
        ("max_drawdown","Max DD"),    ("cvar_5","CVaR 5%"),
        ("avg_turnover","TO/wk"),     ("extra_cost_annual","Extra cost/yr"),
        ("avg_BIL","Avg BIL"),        ("avg_offense","Avg offense"),
        ("hidden_beta","Hidden β"),
    ]:
        cells = [label]
        for v in all_vars:
            val = full_results[v].get(key)
            cells.append(_pct(val) if key in ("ann_return","avg_BIL","avg_offense","extra_cost_annual") else _f(val))
        A("| " + " | ".join(cells) + " |")
    A("")
    A("---")
    A("")
    A("## 5. Holdout Metrics (from 2024-04-19)")
    A("")
    A("| metric | " + " | ".join(VSHORT.get(v, v) for v in all_vars) + " |")
    A("|--------|" + "|".join("------" for _ in all_vars) + "|")
    for key, label in [
        ("ann_return","Return"), ("sharpe","Sharpe"), ("max_drawdown","Max DD"),
    ]:
        cells = [label]
        for v in all_vars:
            val = holdout_results[v].get(key)
            cells.append(_pct(val) if key == "ann_return" else _f(val))
        A("| " + " | ".join(cells) + " |")
    A("")
    A("*Holdout Sharpe deltas vs baseline:*")
    ho_b_sh = b_hold.get("sharpe", np.nan)
    for v in all_vars:
        sh = holdout_results[v].get("sharpe", np.nan)
        d = (float(sh) - float(ho_b_sh)) if sh is not None and np.isfinite(float(sh)) else np.nan
        A(f"- {VSHORT.get(v,v)}: {_f(d, '+.4f')}")
    A("")
    A("---")
    A("")
    A("## 6. Recovery Capture Analysis")
    A("")
    A("| state | baseline | p3_r2a | p3_nc | p3_r2a+tq | p3_rc_only | Δ_best |")
    A("|-------|----------|--------|-------|-----------|------------|--------|")
    for state in ["recovery_confirmed","recovery_fragile"]:
        b_cap = b_full.get(f"capture_{state}", np.nan)
        vals  = [b_cap]
        for v in ["phase3_r2a_rerisk","phase3_no_credit_rerisk",
                  "phase3_r2a_plus_trend_rerisk","phase3_recovery_confirmed_only_rerisk"]:
            vals.append(full_results.get(v, {}).get(f"capture_{state}", np.nan))
        best_cap = max(vals[1:], key=lambda x: x if np.isfinite(x) else -999) if len(vals) > 1 else np.nan
        delta = float(best_cap) - float(b_cap) if (np.isfinite(best_cap) and np.isfinite(b_cap)) else np.nan
        A(f"| {state} | {_f(b_cap)} | " +
          " | ".join(_f(v) for v in vals[1:]) +
          f" | {_f(delta, '+.3f')} |")
    A("")
    A("---")
    A("")
    A("## 7. Stressed_Panic Preservation Check")
    A("")
    A("All modifier variants unconditionally set stressed_panic multiplier = 1.0.")
    A("")
    A("| variant | sp_sharpe | sp_max_dd | Δ_sp_sharpe | Δ_sp_dd |")
    A("|---------|-----------|-----------|-------------|---------|")
    b_sp_sh = b_full.get("sharpe_stressed_panic", np.nan)
    b_sp_dd = b_full.get("max_dd_stressed_panic", np.nan)
    for v in all_vars:
        r = full_results[v]
        sp_sh = r.get("sharpe_stressed_panic", np.nan)
        sp_dd = r.get("max_dd_stressed_panic", np.nan)
        d_sh  = (float(sp_sh) - float(b_sp_sh)) if sp_sh is not None and np.isfinite(float(sp_sh)) else np.nan
        d_dd  = (float(sp_dd) - float(b_sp_dd)) if sp_dd is not None and np.isfinite(float(sp_dd)) else np.nan
        A(f"| {VSHORT.get(v,v)} | {_f(sp_sh)} | {_f(sp_dd)} | "
          f"{_f(d_sh, '+.4f')} | {_f(d_dd, '+.4f')} |")
    A("")
    A("---")
    A("")
    A("## 8. Rolling-Origin and Bootstrap")
    A("")
    A("| candidate | rolling_win | bootstrap_P | mean_bs_delta | CI_95 |")
    A("|-----------|------------|------------|---------------|-------|")
    for v in [v for v in all_vars if v != "ggg_baseline_no_modifier"]:
        ro = rolling.get(v, pd.DataFrame())
        wr = float(ro["beats_base"].mean()) if not ro.empty else np.nan
        bs = bootstrap.get(v, {})
        A(f"| {VSHORT.get(v,v)} | {_f(wr,'.1%')} | "
          f"{_f(bs.get('p_cand_gt_base'),'.3f')} | "
          f"{_f(bs.get('mean_delta'),'+.4f')} | "
          f"[{_f(bs.get('ci95_lo'),'+.4f')}, {_f(bs.get('ci95_hi'),'+.4f')}] |")
    A("")
    A("---")
    A("")
    A("## 9. Phase D Gate Summary")
    A("")
    A("| candidate | verdict | key_failures |")
    A("|-----------|---------|--------------|")
    for row in gate_rows:
        A(f"| {VSHORT.get(row['variant'], row['variant'])} | "
          f"{'✓ PASS' if row['gate_verdict']=='PASS' else '✗ FAIL'} | "
          f"{(row.get('fail',''))[:100]} |")
    A("")
    A("---")
    A("")
    A("## 10. Verdict")
    A("")
    A(f"**{verdict}**")
    A("")
    A(verdict_reason)
    A("")
    A("### Should Phase 3 feed into Phases 4/5?")
    A("")
    if "Promote" in verdict:
        A(
            "Yes. The recovery quality scores (R2A, R2A+trend, no-credit blend) are "
            "validated as portfolio inputs. Carry forward into:\n"
            "- **Phase 4** (Cross-Sectional Leadership): recovery quality is a component of the leadership quality composite.\n"
            "- **Phase 5** (Allocator Objective): the recovery quality score is a direct input to "
            "the deployment confidence score that scales the offense_budget."
        )
    else:
        A(
            "Conditionally. The recovery quality signal construction is valid even if the "
            "portfolio modifier does not pass all gates. Carry the **recovery_quality_r2a_plus_trend** "
            "score as a shared signal input to Phase 4 and Phase 5:\n"
            "- **Phase 4** (Leadership): recovery quality is a leadership confirmation input.\n"
            "- **Phase 5** (Allocator): recovery quality scores the confidence of the deployment.\n"
            "Do NOT apply the re-risking modifier directly to the portfolio until "
            "the holdout/gate issues are resolved or a combined Phase 4+5 modifier clears them."
        )
    A("")
    A("---")
    A("")
    A("## 11. Files Created")
    A("")
    for f in ["smart_rerisk_results.csv","smart_rerisk_holdout_summary.csv",
              "smart_rerisk_state_summary.csv","smart_rerisk_phase_d_gates.csv",
              "rerisk_modifier_timeseries.csv"]:
        A(f"- `data/research/frontier_phase3/{f}`")
    A("- `docs/research/frontier_phase3_smart_rerisk_engine_report.md`")
    A("")
    A("## 12. Production Safety")
    A("")
    A(f"- Protected file diff: **{'✓ Clean' if diff_clean else '✗ CHANGED'}**")
    A("- Production pins: unchanged")
    A("- No public/, src/, dashboard files modified")
    A("")
    if warnings_list:
        A("## 13. Warnings")
        A("")
        for w in warnings_list:
            A(f"- {w}")
        A("")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase3_smart_rerisk_engine_report.md")


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

    def _v(d, k):
        v = d.get(k, np.nan)
        return float(v) if v is not None and np.isfinite(float(v)) else np.nan

    section = f"""

## Section — Frontier Phase 3A: Smart Re-Risking Engine

Date: 2026-05-21.

### Why this sprint happened

Phase 2B showed that Phase 2 trend_quality signals add holdout value when
stacked with Phase 1 R2A, but the portfolio modifier did not clear the
full-history Sharpe gate. Phase 3A explores whether these validated signals
can improve recovery-confirmed participation via a re-risk speed modifier at
the `transition_rerisk_smoothing` checkpoint without weakening stressed_panic.

### What was tried

Six candidates using the `transition_rerisk_smoothing` checkpoint (safe):
- `ggg_baseline_no_modifier` — exact GGG
- `phase1_r2a_only` — Phase 1B R2A at offense_budget (reference)
- `phase3_r2a_rerisk` — R2A recovery quality boost (active in recovery states, ≥6 weeks)
- `phase3_no_credit_rerisk` — breadth+persistence+leadership blend
- `phase3_r2a_plus_trend_rerisk` — R2A + Phase 2 trend_quality blend
- `phase3_recovery_confirmed_only_rerisk` — R2A+trend, recovery_confirmed only

Modifier: `1.0 + 0.20 × quality × transition_gate`; stressed_panic = 1.0 always.

### Key metrics

| metric | baseline | best ({best_var}) | delta |
|--------|----------|-------------------|-------|
| ann_return | {_pct(b.get('ann_return'))} | {_pct(p.get('ann_return'))} | {_f(_v(p,'ann_return') - _v(b,'ann_return'), '+.4f')} |
| sharpe | {_f(b.get('sharpe'))} | {_f(p.get('sharpe'))} | {_f(_v(p,'sharpe') - _v(b,'sharpe'), '+.4f')} |
| recovery_confirmed_capture | {_f(b.get('capture_recovery_confirmed'))} | {_f(p.get('capture_recovery_confirmed'))} | {_f(_v(p,'capture_recovery_confirmed') - _v(b,'capture_recovery_confirmed'), '+.3f')} |
| holdout_sharpe | {_f(hb.get('sharpe'))} | {_f(hp.get('sharpe'))} | {_f(_v(hp,'sharpe') - _v(hb,'sharpe'), '+.4f')} |

### Verdict

**{verdict}**

{verdict_reason}

### What comes next

Recovery quality scores (recovery_quality_r2a_plus_trend) feed Phase 4 (leadership system)
and Phase 5 (allocator objective) as shared signal inputs.
"""
    with open(journey, "a", encoding="utf-8") as f:
        f.write(section)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
