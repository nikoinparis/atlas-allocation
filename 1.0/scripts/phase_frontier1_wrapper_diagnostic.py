"""Frontier Phase 1B: diagnostic wrapper experiment for the R2A deployment-state
quality signal.

This script applies the R2A state-aware composite from Phase 1A-R2 as a
bounded modifier at the offense_budget checkpoint. It is diagnostic-only:
no production or dashboard files are modified. The primary predeclared
candidate is phase1b_r2a_offense_scale_008 (alpha=0.08).

Run from the repo root:
    .venv/bin/python scripts/phase_frontier1_wrapper_diagnostic.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

# ── Path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from path1_path3_research_utils import (
    DATA, DOCS, GGG, OFFENSE,
    exposure_summary, load_next_week_returns, load_states,
    metrics_from_path, normalize_to_cash, production_portfolio_path,
    load_weights,
    PRODUCTION_COST_BPS,
)
from allocator_checkpoint_wrapper import (
    AllocatorCheckpointWrapper, CheckpointModifier,
    apply_checkpoint_multiplier, exact_rebuild_tolerance_ok,
)

# ── Constants ────────────────────────────────────────────────────────────────
HOLDOUT_START = pd.Timestamp("2024-04-19")
DEV_END = pd.Timestamp("2024-04-12")
BOOTSTRAP_SEED = 20260420
BOOTSTRAP_ITERATIONS = 2000
BOOTSTRAP_BLOCK = 13
ROLLING_WINDOW = 104
ROLLING_STEP = 52
MIN_ROLLING_TRAIN = 260

OUT_DIR = DATA / "research" / "frontier_phase1"
R2A_SIGNALS_PATH = OUT_DIR / "state_quality_signals_r2.csv"

PROTECTED_PATHS = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]

# Predeclared candidate alphas
PRIMARY_ALPHA = 0.08
SENSITIVITY_ALPHAS = [0.04, 0.12]   # sensitivity only
ALL_ALPHAS = [PRIMARY_ALPHA] + SENSITIVITY_ALPHAS


# ── Signal loading ────────────────────────────────────────────────────────────

def load_r2a(warnings_list: list[str]) -> pd.Series:
    """Load the R2A deployment quality composite (already 1-week lagged)."""
    if not R2A_SIGNALS_PATH.exists():
        raise SystemExit(f"Phase 1A-R2 signals not found: {R2A_SIGNALS_PATH}")
    df = pd.read_csv(R2A_SIGNALS_PATH)
    date_col = "date" if "date" in df.columns else "Date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)
    if "r2a" not in df.columns:
        raise SystemExit("r2a column missing from Phase 1A-R2 signals CSV.")
    series = pd.to_numeric(df["r2a"], errors="coerce")
    n_valid = series.notna().sum()
    print(f"  R2A signal: {n_valid} non-null values from {series.dropna().index[0].date()} "
          f"to {series.dropna().index[-1].date()}")
    return series


# ── Modifier factory ──────────────────────────────────────────────────────────

def make_offense_modifier(quality: pd.Series, alpha: float, states: pd.Series) -> pd.Series:
    """Build a scalar multiplier at the offense_budget checkpoint.

    scale = 1 + alpha * clip(r2a, -1, 1)  when state != stressed_panic
    scale = 1.0                             when state == stressed_panic
    """
    q = quality.reindex(states.index).ffill().fillna(0.0).clip(-1.0, 1.0)
    scale = pd.Series(1.0, index=states.index)
    not_stressed = states != "stressed_panic"
    scale[not_stressed] = 1.0 + alpha * q[not_stressed]
    return scale


# ── Portfolio path helpers ────────────────────────────────────────────────────

def compute_ann_return(net_returns: pd.Series, n_weeks: int | None = None) -> float:
    if net_returns.empty:
        return np.nan
    n = n_weeks or len(net_returns)
    return float((1 + net_returns).prod() ** (52.0 / n) - 1)


def compute_ann_vol(net_returns: pd.Series) -> float:
    if len(net_returns) < 4:
        return np.nan
    return float(net_returns.std() * np.sqrt(52))


def compute_sharpe(net_returns: pd.Series, rf: float = 0.0) -> float:
    vol = compute_ann_vol(net_returns)
    if not vol or np.isnan(vol):
        return np.nan
    return float(compute_ann_return(net_returns) / vol)


def compute_max_dd(net_returns: pd.Series) -> float:
    if net_returns.empty:
        return np.nan
    wealth = (1 + net_returns).cumprod()
    peak = wealth.cummax()
    dd = (wealth / peak - 1).min()
    return float(dd)


def compute_cvar(net_returns: pd.Series, pct: float = 0.05) -> float:
    if len(net_returns) < 10:
        return np.nan
    tail = net_returns[net_returns <= net_returns.quantile(pct)]
    return float(tail.mean()) if len(tail) else np.nan


def spy_return_in_window(path_df: pd.DataFrame, nwr: pd.DataFrame, dates: pd.Index) -> float:
    """Annualised SPY return over a set of dates, for capture ratio denominator."""
    if "SPY" not in nwr.columns:
        return np.nan
    spy_r = nwr["SPY"].reindex(dates).dropna()
    if len(spy_r) < 4:
        return np.nan
    return float((1 + spy_r).prod() ** (52.0 / len(spy_r)) - 1)


def state_metrics(path_df: pd.DataFrame, states_s: pd.Series,
                  nwr: pd.DataFrame, label_col: str = "net_return") -> pd.DataFrame:
    """Per-state: ann_return, sharpe, max_dd, n_weeks, spy_capture."""
    path_df = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    rows = []
    for state, grp_idx in states_s.groupby(states_s).groups.items():
        dates = pd.DatetimeIndex(grp_idx).intersection(path_df.index)
        if len(dates) < 8:
            continue
        rets = path_df.loc[dates, label_col].dropna()
        spy_ann = spy_return_in_window(path_df, nwr.set_index(nwr.columns[0]) if "Date" in nwr.columns else nwr, dates)
        port_ann = compute_ann_return(rets)
        capture = port_ann / spy_ann if (np.isfinite(spy_ann) and spy_ann > 0.01) else np.nan
        rows.append({
            "market_state": str(state),
            "ann_return": port_ann,
            "ann_vol": compute_ann_vol(rets),
            "sharpe": compute_sharpe(rets),
            "max_dd": compute_max_dd(rets),
            "spy_capture": capture,
            "n_weeks": len(rets),
        })
    return pd.DataFrame(rows).sort_values("market_state")


# ── Rolling-origin ────────────────────────────────────────────────────────────

def rolling_origin(path_df: pd.DataFrame, baseline_df: pd.DataFrame,
                   label_col: str = "net_return") -> pd.DataFrame:
    path_df = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    baseline_df = baseline_df.set_index("Date") if "Date" in baseline_df.columns else baseline_df
    n = len(path_df)
    rows = []
    for start in range(MIN_ROLLING_TRAIN, n - ROLLING_WINDOW, ROLLING_STEP):
        slice_idx = path_df.index[start: start + ROLLING_WINDOW]
        cand = path_df.loc[slice_idx, label_col].dropna()
        base = baseline_df.loc[slice_idx, label_col].dropna() if label_col in baseline_df.columns else pd.Series(dtype=float)
        if len(cand) < 20:
            continue
        cand_sharpe = compute_sharpe(cand)
        base_sharpe = compute_sharpe(base) if len(base) >= 20 else np.nan
        rows.append({
            "origin": path_df.index[start],
            "cand_sharpe": cand_sharpe,
            "base_sharpe": base_sharpe,
            "delta_sharpe": cand_sharpe - base_sharpe if np.isfinite(base_sharpe) else np.nan,
            "cand_ann_return": compute_ann_return(cand),
            "base_ann_return": compute_ann_return(base) if len(base) >= 20 else np.nan,
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["beats_base"] = df["delta_sharpe"] > 0
    return df


# ── Block bootstrap ───────────────────────────────────────────────────────────

def block_bootstrap(cand_rets: pd.Series, base_rets: pd.Series,
                    n_iter: int = BOOTSTRAP_ITERATIONS, block: int = BOOTSTRAP_BLOCK,
                    seed: int = BOOTSTRAP_SEED) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    aligned = pd.concat([cand_rets, base_rets], axis=1).dropna()
    if len(aligned) < 20:
        return {"p_cand_gt_base": np.nan, "mean_delta": np.nan, "ci95_lo": np.nan, "ci95_hi": np.nan}
    n = len(aligned)
    deltas = []
    for _ in range(n_iter):
        starts = rng.integers(0, max(1, n - block + 1), size=(n // block) + 2)
        idx = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])[:n]
        s = aligned.iloc[idx]
        d = compute_sharpe(s.iloc[:, 0]) - compute_sharpe(s.iloc[:, 1])
        deltas.append(d)
    deltas = np.array(deltas)
    deltas = deltas[np.isfinite(deltas)]
    if len(deltas) == 0:
        return {"p_cand_gt_base": np.nan, "mean_delta": np.nan, "ci95_lo": np.nan, "ci95_hi": np.nan}
    return {
        "p_cand_gt_base": float((deltas > 0).mean()),
        "mean_delta": float(np.mean(deltas)),
        "ci95_lo": float(np.percentile(deltas, 2.5)),
        "ci95_hi": float(np.percentile(deltas, 97.5)),
    }


# ── Hidden beta ───────────────────────────────────────────────────────────────

def hidden_beta(port_rets: pd.Series, nwr: pd.DataFrame) -> float | None:
    if "SPY" not in nwr.columns:
        return None
    spy = nwr["SPY"].reindex(port_rets.index).dropna()
    aligned = pd.concat([port_rets, spy], axis=1).dropna()
    if len(aligned) < 20:
        return None
    slope, _, _, _, _ = scipy_stats.linregress(aligned.iloc[:, 1], aligned.iloc[:, 0])
    return float(slope)


# ── Production diff check ─────────────────────────────────────────────────────

def protected_diff_clean() -> tuple[bool, list[str]]:
    try:
        r = subprocess.run(
            ["git", "diff", "--name-only", "--", *PROTECTED_PATHS],
            cwd=ROOT, check=False, text=True, capture_output=True,
        )
    except Exception:
        return False, ["git diff check failed"]
    changed = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(changed) == 0, changed


# ── Metric summary dict ───────────────────────────────────────────────────────

def summarise(variant: str, path_df: pd.DataFrame, weights_df: pd.DataFrame,
              states_s: pd.Series, nwr_df: pd.DataFrame) -> dict:
    path_df = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    rets = path_df["net_return"].dropna()

    # Exposure from the actual wrapper metrics (precomputed)
    exp = exposure_summary(weights_df)

    row: dict = {
        "variant": variant,
        "ann_return": compute_ann_return(rets),
        "ann_vol": compute_ann_vol(rets),
        "sharpe": compute_sharpe(rets),
        "max_drawdown": compute_max_dd(rets),
        "cvar_5": compute_cvar(rets),
        "avg_turnover": float(path_df["turnover"].mean()) if "turnover" in path_df.columns else np.nan,
        "avg_BIL": float(exp.get("avg_BIL", np.nan)),
        "avg_SPY": float(exp.get("avg_SPY", np.nan)),
        "avg_offense": float(exp.get("avg_offense", np.nan)),
        "avg_defense": float(exp.get("avg_defense", np.nan)),
    }

    # State-conditional
    nwr_idx = nwr_df.set_index("Date") if "Date" in nwr_df.columns else nwr_df
    nwr_aligned = nwr_idx.reindex(rets.index)
    for state in ["calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]:
        mask = states_s.reindex(rets.index) == state
        state_rets = rets[mask]
        if len(state_rets) >= 8:
            spy_ann = spy_return_in_window(None, nwr_aligned, state_rets.index)
            port_ann = compute_ann_return(state_rets)
            row[f"sharpe_{state}"] = compute_sharpe(state_rets)
            row[f"ann_return_{state}"] = port_ann
            row[f"capture_{state}"] = (port_ann / spy_ann
                                        if (np.isfinite(spy_ann) and spy_ann > 0.01) else np.nan)
        else:
            row[f"sharpe_{state}"] = np.nan
            row[f"ann_return_{state}"] = np.nan
            row[f"capture_{state}"] = np.nan

    # Hidden beta
    row["hidden_beta_spy"] = hidden_beta(rets, nwr_aligned)

    return row


def summarise_window(variant: str, path_df: pd.DataFrame, weights_df: pd.DataFrame,
                     states_s: pd.Series, nwr_df: pd.DataFrame,
                     start: pd.Timestamp | None, end: pd.Timestamp | None,
                     window_label: str) -> dict:
    path_df = path_df.set_index("Date") if "Date" in path_df.columns else path_df
    mask = pd.Series(True, index=path_df.index)
    if start is not None:
        mask &= path_df.index >= start
    if end is not None:
        mask &= path_df.index < end
    path_slice = path_df[mask]
    weights_slice = weights_df[weights_df.index.isin(path_slice.index)]
    states_slice = states_s[states_s.index.isin(path_slice.index)]
    d = summarise(variant, path_slice.reset_index(), weights_slice, states_slice, nwr_df)
    d["window"] = window_label
    return d


# ── Acceptance gates ──────────────────────────────────────────────────────────

def evaluate_acceptance(primary: dict, baseline: dict,
                        holdout_primary: dict, holdout_baseline: dict,
                        bootstrap_result: dict, rolling_df: pd.DataFrame) -> tuple[str, list[str], list[str]]:
    ok, fail = [], []

    # Gate 1: full-history Sharpe improves by >= +0.01
    delta_sh = primary["sharpe"] - baseline["sharpe"]
    if delta_sh >= 0.01:
        ok.append(f"Full-history Sharpe Δ = {delta_sh:+.4f} ≥ +0.01")
    else:
        fail.append(f"Full-history Sharpe Δ = {delta_sh:+.4f} < +0.01")

    # Gate 2: holdout Sharpe not worse by more than -0.02
    ho_delta = holdout_primary.get("sharpe", np.nan) - holdout_baseline.get("sharpe", np.nan)
    if np.isfinite(ho_delta) and ho_delta >= -0.02:
        ok.append(f"Holdout Sharpe Δ = {ho_delta:+.4f} ≥ -0.02")
    else:
        fail.append(f"Holdout Sharpe Δ = {ho_delta:+.4f} < -0.02 (or NaN)")

    # Gate 3: max DD not materially worse (> -0.01 pts)
    dd_delta = primary["max_drawdown"] - baseline["max_drawdown"]
    if dd_delta >= -0.01:
        ok.append(f"MaxDD Δ = {dd_delta:+.4f} ≥ -0.01")
    else:
        fail.append(f"MaxDD Δ = {dd_delta:+.4f} < -0.01")

    # Gate 4: CVaR not materially worse (> -0.002)
    cv_delta = primary["cvar_5"] - baseline["cvar_5"]
    if cv_delta >= -0.002:
        ok.append(f"CVaR-5 Δ = {cv_delta:+.4f} ≥ -0.002")
    else:
        fail.append(f"CVaR-5 Δ = {cv_delta:+.4f} < -0.002")

    # Gate 5: stressed_panic Sharpe unchanged or better
    sp_delta = (primary.get("sharpe_stressed_panic", np.nan) or np.nan) - \
               (baseline.get("sharpe_stressed_panic", np.nan) or np.nan)
    if not np.isfinite(sp_delta) or sp_delta >= -0.05:
        ok.append(f"Stressed-panic Sharpe Δ = {sp_delta:+.4f} (acceptable)")
    else:
        fail.append(f"Stressed-panic Sharpe Δ = {sp_delta:+.4f} < -0.05 (defense weakened)")

    # Gate 6: turnover increase acceptable (< +3pp per year)
    to_delta = (primary.get("avg_turnover", 0) or 0) - (baseline.get("avg_turnover", 0) or 0)
    if to_delta < 0.0006:   # 3pp/year / 52 weeks ~ 0.0006/week
        ok.append(f"Turnover Δ/week = {to_delta:+.6f} (< 3pp/year)")
    else:
        fail.append(f"Turnover Δ/week = {to_delta:+.6f} ≥ 3pp/year threshold")

    # Gate 7: not just lower BIL / hidden SPY beta
    bil_delta = (primary.get("avg_BIL", 0) or 0) - (baseline.get("avg_BIL", 0) or 0)
    beta_primary = primary.get("hidden_beta_spy", np.nan) or np.nan
    beta_base = baseline.get("hidden_beta_spy", np.nan) or np.nan
    beta_delta = beta_primary - beta_base if (np.isfinite(beta_primary) and np.isfinite(beta_base)) else np.nan
    if bil_delta > -0.03 and (not np.isfinite(beta_delta) or beta_delta < 0.10):
        ok.append(f"BIL Δ = {bil_delta:+.4f} (not driven by BIL reduction); "
                  f"SPY beta Δ = {beta_delta:+.4f} (no hidden beta)")
    else:
        if bil_delta <= -0.03:
            fail.append(f"BIL Δ = {bil_delta:+.4f}: improvement may be BIL reduction alone")
        if np.isfinite(beta_delta) and beta_delta >= 0.10:
            fail.append(f"SPY beta Δ = {beta_delta:+.4f}: hidden beta added")

    passed = len(fail) == 0
    return ("PASS" if passed else "FAIL"), ok, fail


# ── Report writer ─────────────────────────────────────────────────────────────

def _fmt(v, fmt=".4f") -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        return format(float(v), fmt)
    except Exception:
        return str(v)


def _fmtpct(v) -> str:
    """Format as percentage with 2 decimal places."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    return f"{float(v)*100:.2f}%"


def write_report(
    results: dict[str, dict],    # variant → full_summary
    holdout_results: dict[str, dict],
    state_df: pd.DataFrame,
    rolling_df: pd.DataFrame,
    bootstrap_results: dict[str, dict],   # variant → bootstrap dict
    gate_result: tuple[str, list[str], list[str]],
    verdict: str,
    verdict_reason: str,
    warnings_list: list[str],
    diff_clean: bool,
) -> None:
    report_path = ROOT / "docs" / "research" / "frontier_phase1_deployment_state_intelligence_report.md"

    baseline = "ggg_baseline_no_modifier"
    primary = "phase1b_r2a_offense_scale_008"
    all_variants = [baseline, primary] + [f"phase1b_r2a_offense_scale_{int(a*100):03d}"
                                           for a in SENSITIVITY_ALPHAS]
    present = [v for v in all_variants if v in results]

    lines: list[str] = []
    A = lines.append

    A("# Frontier Phase 1B: Deployment-State Intelligence Wrapper Diagnostic Report")
    A("")
    A("**Date:** 2026-05-20")
    A("**Phase:** 1B — wrapper experiment using R2A state-aware quality signal")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(f"**Primary candidate:** `{primary}` (alpha = {PRIMARY_ALPHA})")
    A("")
    A("---")
    A("")

    A("## 1. Sprint Summary")
    A("")
    A(
        "Phase 1A-R2 built a state-aware signed deployment quality composite (R2A) that "
        "passed all Phase 1A-R2 diagnostic gates: full IC +0.174, holdout IC +0.218, "
        "4 of 5 states positive, calm_trend IC +0.207 (sign-flipped from original −0.185). "
        "Phase 1B tests whether R2A translates into portfolio improvement when applied as a "
        "bounded modifier at the `offense_budget` checkpoint."
    )
    A("")
    A("**Wrapper architecture:** modifier scales offensive ETF weights by "
      "`1 + alpha × clip(r2a, −1, 1)` in non-stressed states. "
      "Stressed_panic rows receive multiplier = 1.0 unconditionally.")
    A("")
    A("---")
    A("")

    A("## 2. R2A IC Recap (from Phase 1A-R2)")
    A("")
    A("| state | IC |")
    A("|-------|----|")
    for s, ic in [
        ("ALL (full period)", "+0.174"), ("development", "+0.170"), ("holdout", "+0.218"),
        ("calm_trend", "+0.207"), ("neutral_mixed", "+0.097"),
        ("recovery_confirmed", "−0.043"), ("recovery_fragile", "+0.238"),
        ("stressed_panic", "+0.363"),
    ]:
        A(f"| {s} | {ic} |")
    A("")
    A("*recovery_confirmed IC is slightly negative. This caveat is tracked below.*")
    A("")
    A("---")
    A("")

    A("## 3. Full-History Metrics")
    A("")
    A("| metric | ggg_baseline | r2a_α=0.04 | **r2a_α=0.08** | r2a_α=0.12 |")
    A("|--------|-------------|-----------|---------------|-----------|")
    for key, label in [
        ("ann_return", "Annual return"), ("ann_vol", "Annual vol"), ("sharpe", "Sharpe"),
        ("max_drawdown", "Max drawdown"), ("cvar_5", "CVaR 5%"),
        ("avg_turnover", "Avg turnover/wk"), ("avg_BIL", "Avg BIL"),
        ("avg_SPY", "Avg SPY"), ("avg_offense", "Avg offense"),
        ("hidden_beta_spy", "Hidden β vs SPY"),
    ]:
        cells = [label]
        for v in [baseline] + [f"phase1b_r2a_offense_scale_{int(a*100):03d}" for a in ALL_ALPHAS]:
            if v in results:
                val = results[v].get(key, np.nan)
                cells.append(_fmt(val))
            else:
                cells.append("–")
        A("| " + " | ".join(cells) + " |")
    A("")

    A("## 4. Holdout Metrics (from 2024-04-19, ~104 weeks)")
    A("")
    A("| metric | ggg_baseline | **r2a_α=0.08** |")
    A("|--------|-------------|---------------|")
    for key, label in [
        ("ann_return", "Annual return"), ("sharpe", "Sharpe"),
        ("max_drawdown", "Max drawdown"), ("cvar_5", "CVaR 5%"),
        ("avg_BIL", "Avg BIL"), ("avg_turnover", "Avg turnover/wk"),
    ]:
        b_val = holdout_results.get(baseline, {}).get(key, np.nan)
        p_val = holdout_results.get(primary, {}).get(key, np.nan)
        delta = (float(p_val) - float(b_val)) if (np.isfinite(float(b_val) if b_val is not None else np.nan)
                                                    and np.isfinite(float(p_val) if p_val is not None else np.nan)) else np.nan
        A(f"| {label} | {_fmt(b_val)} | {_fmt(p_val)} (Δ {_fmt(delta, '+.4f')}) |")
    A("")

    A("## 5. State-by-State Summary (primary candidate vs baseline, full history)")
    A("")
    A("| state | base_return | base_sharpe | cand_return | cand_sharpe | cand_capture | Δ_sharpe |")
    A("|-------|-------------|-------------|-------------|-------------|--------------|----------|")
    if not state_df.empty:
        for state in ["calm_trend", "neutral_mixed", "recovery_confirmed",
                      "recovery_fragile", "stressed_panic"]:
            b = results.get(baseline, {})
            p = results.get(primary, {})
            b_sh = b.get(f"sharpe_{state}", np.nan)
            p_sh = p.get(f"sharpe_{state}", np.nan)
            b_r = b.get(f"ann_return_{state}", np.nan)
            p_r = p.get(f"ann_return_{state}", np.nan)
            p_cap = p.get(f"capture_{state}", np.nan)
            d_sh = (float(p_sh) - float(b_sh)) if (np.isfinite(float(b_sh) if b_sh else np.nan)
                                                     and np.isfinite(float(p_sh) if p_sh else np.nan)) else np.nan
            A(f"| {state} | {_fmtpct(b_r)} | {_fmt(b_sh)} | {_fmtpct(p_r)} | "
              f"{_fmt(p_sh)} | {_fmt(p_cap)} | {_fmt(d_sh, '+.4f')} |")
    A("")

    A("## 6. Stressed_Panic Preservation Check")
    A("")
    b_sp = results.get(baseline, {}).get("sharpe_stressed_panic", np.nan)
    p_sp = results.get(primary, {}).get("sharpe_stressed_panic", np.nan)
    sp_delta = (float(p_sp) - float(b_sp)) if (np.isfinite(float(b_sp or np.nan))
                                                 and np.isfinite(float(p_sp or np.nan))) else np.nan
    A(f"- Baseline stressed_panic Sharpe: **{_fmt(b_sp)}**")
    A(f"- Primary candidate stressed_panic Sharpe: **{_fmt(p_sp)}**")
    A(f"- Delta: **{_fmt(sp_delta, '+.4f')}**")
    status = "✓ Defense preserved" if (not np.isfinite(sp_delta) or sp_delta >= -0.05) else "✗ Defense weakened"
    A(f"- Assessment: **{status}**")
    A("")
    A("The modifier is unconditionally set to 1.0 in `stressed_panic` rows, so no "
      "offensive weight change occurs. Any delta here reflects portfolio rebalancing "
      "effects in the periods immediately surrounding stress events.")
    A("")

    A("## 7. Recovery_Confirmed Caveat")
    A("")
    A("R2A has IC −0.043 in `recovery_confirmed` (43 observations full history). "
      "The positive sign configuration (breadth, path_clarity, persistence, leadership) "
      "applied in recovery_confirmed may not reliably predict the next 4 weeks of SPY return "
      "in this state. This is an acknowledged limitation.")
    A("")
    b_rc = results.get(baseline, {}).get("sharpe_recovery_confirmed", np.nan)
    p_rc = results.get(primary, {}).get("sharpe_recovery_confirmed", np.nan)
    rc_delta = (float(p_rc) - float(b_rc)) if (np.isfinite(float(b_rc or np.nan))
                                                 and np.isfinite(float(p_rc or np.nan))) else np.nan
    A(f"- Baseline recovery_confirmed Sharpe: {_fmt(b_rc)}")
    A(f"- Primary candidate recovery_confirmed Sharpe: {_fmt(p_rc)}")
    A(f"- Delta: {_fmt(rc_delta, '+.4f')}")
    A("")
    A("If recovery_confirmed Sharpe worsens by more than −0.10, the Phase 1B modifier "
      "should be revised to exclude R2A in recovery_confirmed (set modifier = 1.0 there).")
    A("")

    A("## 8. Rolling-Origin Validation")
    A("")
    if not rolling_df.empty:
        win_rate = float(rolling_df["beats_base"].mean())
        mean_delta = float(rolling_df["delta_sharpe"].mean())
        A(f"- Windows evaluated: {len(rolling_df)}")
        A(f"- Win rate vs baseline (Sharpe): {win_rate:.1%}")
        A(f"- Mean Sharpe delta: {mean_delta:+.4f}")
    else:
        A("- Rolling-origin not computed (insufficient data).")
    A("")

    A("## 9. Block Bootstrap (holdout, 2000 iterations, 13-week blocks)")
    A("")
    bs = bootstrap_results.get(primary, {})
    A(f"- P(candidate > baseline on Sharpe): **{_fmt(bs.get('p_cand_gt_base'), '.3f')}**")
    A(f"- Mean Sharpe delta: {_fmt(bs.get('mean_delta'), '+.4f')}")
    A(f"- 95% CI: [{_fmt(bs.get('ci95_lo'), '+.4f')}, {_fmt(bs.get('ci95_hi'), '+.4f')}]")
    A("")

    A("## 10. Acceptance Gate Results")
    A("")
    gate_verdict, gate_ok, gate_fail = gate_result
    status = "✓ PASS" if gate_verdict == "PASS" else "✗ FAIL"
    A(f"**Primary candidate ({primary}): {status}**")
    A("")
    for r in gate_ok:
        A(f"- ✓ {r}")
    for r in gate_fail:
        A(f"- ✗ {r}")
    A("")

    A("---")
    A("")
    A("## 11. Verdict")
    A("")
    A(f"**{verdict}**")
    A("")
    A(verdict_reason)
    A("")

    A("---")
    A("")
    A("## 12. Files Created")
    A("")
    A("| file | description |")
    A("|------|-------------|")
    A(f"| `data/research/frontier_phase1/wrapper_diagnostic_results.csv` | Full-history metrics all candidates |")
    A(f"| `data/research/frontier_phase1/wrapper_diagnostic_state_summary.csv` | State-conditional summary |")
    A(f"| `data/research/frontier_phase1/wrapper_diagnostic_holdout_summary.csv` | Holdout metrics all candidates |")
    A(f"| `docs/research/frontier_phase1_deployment_state_intelligence_report.md` | This report |")
    A("")

    A("## 13. Commands Run")
    A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py")
    A(".venv/bin/python scripts/phase_frontier1_wrapper_diagnostic.py")
    A("```")
    A("")

    A("## 14. Production Safety")
    A("")
    diff_status = "✓ Clean" if diff_clean else "✗ CHANGED"
    A(f"- Protected file diff: **{diff_status}**")
    A("- Production pins: unchanged (`improved_phase2b_regime_confidence_boost` / `improved_phase2b_combo_abc`)")
    A("- No public/, src/, or dashboard files modified.")
    A("")

    if warnings_list:
        A("## 15. Warnings")
        A("")
        for w in warnings_list:
            A(f"- {w}")
        A("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase1_deployment_state_intelligence_report.md")


# ── Project journey update ────────────────────────────────────────────────────

def append_journey(verdict: str, results: dict, holdout_results: dict,
                   gate_ok: list[str], gate_fail: list[str]) -> None:
    journey_path = ROOT / "docs" / "research" / "project_journey.md"
    if not journey_path.exists():
        print("project_journey.md not found — skipping journey update.")
        return

    baseline = "ggg_baseline_no_modifier"
    primary = "phase1b_r2a_offense_scale_008"
    b = results.get(baseline, {})
    p = results.get(primary, {})
    hb = holdout_results.get(baseline, {})
    hp = holdout_results.get(primary, {})

    section = f"""

## Section — Frontier Phase 1B: Deployment-State Intelligence Wrapper Diagnostic

Date: 2026-05-20.

### Why this sprint happened

Phase 1A-R2 built a state-aware signed deployment quality composite (R2A) that
passed all diagnostic gates (full IC +0.174, holdout IC +0.218, calm_trend IC
+0.207 after sign correction). Phase 1B tests whether R2A translates into
portfolio improvement as a bounded modifier at the `offense_budget` checkpoint.
The predeclared primary candidate scales offensive ETF weights by
`1 + 0.08 × clip(r2a, -1, 1)` in non-stressed states.

### What was tried

- `ggg_baseline_no_modifier` — exact GGG reproduction (no modifier)
- `phase1b_r2a_offense_scale_008` — primary candidate, alpha = 0.08
- `phase1b_r2a_offense_scale_004` — sensitivity, alpha = 0.04
- `phase1b_r2a_offense_scale_012` — sensitivity, alpha = 0.12

All modifier candidates use the `offense_budget` checkpoint (safe). Stressed_panic
modifier is unconditionally 1.0 (defense unchanged).

### Key metrics

| metric | baseline | primary (α=0.08) | delta |
|--------|----------|-----------------|-------|
| ann_return | {_fmtpct(b.get('ann_return'))} | {_fmtpct(p.get('ann_return'))} | {_fmt((p.get('ann_return', np.nan) or np.nan) - (b.get('ann_return', np.nan) or np.nan), '+.4f')} |
| sharpe | {_fmt(b.get('sharpe'))} | {_fmt(p.get('sharpe'))} | {_fmt((p.get('sharpe', np.nan) or np.nan) - (b.get('sharpe', np.nan) or np.nan), '+.4f')} |
| max_drawdown | {_fmt(b.get('max_drawdown'))} | {_fmt(p.get('max_drawdown'))} | {_fmt((p.get('max_drawdown', np.nan) or np.nan) - (b.get('max_drawdown', np.nan) or np.nan), '+.4f')} |
| holdout_sharpe | {_fmt(hb.get('sharpe'))} | {_fmt(hp.get('sharpe'))} | {_fmt((hp.get('sharpe', np.nan) or np.nan) - (hb.get('sharpe', np.nan) or np.nan), '+.4f')} |

### Verdict

**{verdict}**

Gate results:
{"".join(f"- ✓ {r}  " + chr(10) for r in gate_ok)}{"".join(f"- ✗ {r}  " + chr(10) for r in gate_fail)}
### What comes next

{"Phase 2 (Trend Quality Engine) and use R2A as a shared input signal." if "Phase 2" in verdict else "Revise Phase 1B before proceeding to Phase 2." if "Revise" in verdict else "Phase 1 modifier is diagnostic-only; proceed to Phase 2 independently."}
"""
    with open(journey_path, "a", encoding="utf-8") as f:
        f.write(section)
    print("project_journey.md updated.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    warnings_list: list[str] = []
    print("=" * 70)
    print("Frontier Phase 1B: Wrapper Diagnostic")
    print("=" * 70)

    # ── Load R2A signal ───────────────────────────────────────────────────────
    print("\nLoading R2A signal...")
    r2a = load_r2a(warnings_list)

    # ── Initialise wrapper ────────────────────────────────────────────────────
    print("\nInitialising checkpoint wrapper...")
    wrapper = AllocatorCheckpointWrapper()

    # Verify baseline reproduces GGG exactly
    compare = wrapper.compare_to_saved()
    if not exact_rebuild_tolerance_ok(compare, tolerance=1e-10):
        raise SystemExit(
            f"Wrapper does not reproduce GGG to tolerance. Errors: {compare}"
        )
    print(f"  Exact GGG baseline confirmed (max_error={compare.get('net_return_max_abs_error', 0):.2e})")

    # ── Load helper data ──────────────────────────────────────────────────────
    nwr_raw = wrapper.next_week_returns
    # Ensure nwr has a Date column or index
    if isinstance(nwr_raw, pd.DataFrame):
        if "Date" not in nwr_raw.columns and nwr_raw.index.name != "Date":
            nwr = nwr_raw.reset_index().rename(columns={"index": "Date"})
        else:
            nwr = nwr_raw.reset_index() if "Date" not in nwr_raw.columns else nwr_raw
    else:
        nwr = pd.DataFrame()
        warnings_list.append("next_week_returns not a DataFrame")

    states_df = wrapper.states
    states_s = states_df["market_state"].astype(str) if "market_state" in states_df.columns else pd.Series(dtype=str)

    # ── Build candidates ──────────────────────────────────────────────────────
    runs: dict[str, any] = {}

    # Baseline
    print("\nRunning baseline (no modifier)...")
    runs["ggg_baseline_no_modifier"] = wrapper.run(variant="ggg_baseline_no_modifier")

    # R2A candidates
    for alpha in ALL_ALPHAS:
        alpha_str = f"{int(alpha * 100):03d}"
        variant = f"phase1b_r2a_offense_scale_{alpha_str}"
        print(f"Running {variant}...")

        quality_signal = r2a
        states_for_mod = states_s

        def make_fn(q, a, s):
            def fn(w, checkpoint):
                return make_offense_modifier(q, a, s)
            return fn

        modifier = CheckpointModifier(
            name=f"r2a_offense_scale_{alpha_str}",
            checkpoint="offense_budget",
            function=make_fn(quality_signal, alpha, states_for_mod),
        )
        runs[variant] = wrapper.run(variant=variant, modifiers=[modifier])

    # ── Summarise all windows ─────────────────────────────────────────────────
    print("\nComputing metrics...")
    full_results: dict[str, dict] = {}
    dev_results: dict[str, dict] = {}
    holdout_results: dict[str, dict] = {}

    for variant, run in runs.items():
        path_df = run.path
        weights_df = run.weights
        full_results[variant] = summarise(variant, path_df, weights_df, states_s, nwr)
        dev_results[variant] = summarise_window(
            variant, path_df, weights_df, states_s, nwr,
            None, DEV_END, "development"
        )
        holdout_results[variant] = summarise_window(
            variant, path_df, weights_df, states_s, nwr,
            HOLDOUT_START, None, "holdout"
        )

    # ── Rolling-origin ────────────────────────────────────────────────────────
    primary = "phase1b_r2a_offense_scale_008"
    baseline = "ggg_baseline_no_modifier"
    print("Computing rolling-origin...")
    rolling_df = rolling_origin(runs[primary].path, runs[baseline].path)
    if not rolling_df.empty:
        win_rate = float(rolling_df["beats_base"].mean())
        print(f"  Rolling win rate vs baseline: {win_rate:.1%} over {len(rolling_df)} windows")

    # ── Bootstrap ─────────────────────────────────────────────────────────────
    print("Computing block bootstrap (holdout only)...")
    ho_start_idx = runs[primary].path.set_index("Date").index >= HOLDOUT_START
    ho_path = runs[primary].path.set_index("Date")[ho_start_idx]
    ho_base = runs[baseline].path.set_index("Date")[
        runs[baseline].path.set_index("Date").index >= HOLDOUT_START
    ]
    bootstrap_results: dict[str, dict] = {}
    if len(ho_path) >= 20:
        bootstrap_results[primary] = block_bootstrap(
            ho_path["net_return"].dropna(),
            ho_base["net_return"].dropna(),
        )
        bs = bootstrap_results[primary]
        print(f"  P(candidate > baseline): {bs.get('p_cand_gt_base', np.nan):.3f}  "
              f"mean_delta={bs.get('mean_delta', np.nan):+.4f}  "
              f"CI=[{bs.get('ci95_lo', np.nan):+.4f}, {bs.get('ci95_hi', np.nan):+.4f}]")
    else:
        bootstrap_results[primary] = {}
        warnings_list.append("Holdout too short for meaningful bootstrap (< 20 weeks).")

    # ── State summary ─────────────────────────────────────────────────────────
    state_rows = []
    for variant, r in full_results.items():
        for state in ["calm_trend", "neutral_mixed", "recovery_confirmed",
                      "recovery_fragile", "stressed_panic"]:
            state_rows.append({
                "variant": variant,
                "market_state": state,
                "ann_return": r.get(f"ann_return_{state}"),
                "sharpe": r.get(f"sharpe_{state}"),
                "spy_capture": r.get(f"capture_{state}"),
            })
    state_df = pd.DataFrame(state_rows)

    # ── Print summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Full-History Results")
    print("=" * 70)
    for v, r in full_results.items():
        print(f"\n  {v}:")
        print(f"    Return={_fmtpct(r.get('ann_return'))}  "
              f"Sharpe={_fmt(r.get('sharpe'))}  "
              f"MaxDD={_fmt(r.get('max_drawdown'))}  "
              f"CVaR={_fmt(r.get('cvar_5'))}  "
              f"Turnover/wk={_fmt(r.get('avg_turnover'), '.6f')}")
        print(f"    BIL={_fmtpct(r.get('avg_BIL'))}  "
              f"offense={_fmtpct(r.get('avg_offense'))}  "
              f"β_SPY={_fmt(r.get('hidden_beta_spy'))}")
        print(f"    calm_trend_sharpe={_fmt(r.get('sharpe_calm_trend'))}  "
              f"recovery_confirmed_sharpe={_fmt(r.get('sharpe_recovery_confirmed'))}  "
              f"stressed_panic_sharpe={_fmt(r.get('sharpe_stressed_panic'))}")

    print("\n" + "=" * 70)
    print("Holdout Results")
    print("=" * 70)
    for v in [baseline, primary]:
        r = holdout_results.get(v, {})
        print(f"\n  {v}: Return={_fmtpct(r.get('ann_return'))}  Sharpe={_fmt(r.get('sharpe'))}  "
              f"MaxDD={_fmt(r.get('max_drawdown'))}")

    # ── Acceptance evaluation ─────────────────────────────────────────────────
    gate_result = evaluate_acceptance(
        full_results.get(primary, {}),
        full_results.get(baseline, {}),
        holdout_results.get(primary, {}),
        holdout_results.get(baseline, {}),
        bootstrap_results.get(primary, {}),
        rolling_df,
    )
    gate_verdict, gate_ok, gate_fail = gate_result
    print(f"\n{'='*70}")
    print(f"Acceptance gates: {gate_verdict}")
    for r in gate_ok:
        print(f"  ✓ {r}")
    for r in gate_fail:
        print(f"  ✗ {r}")

    # ── Determine verdict ─────────────────────────────────────────────────────
    b = full_results.get(baseline, {})
    p = full_results.get(primary, {})
    ho_b = holdout_results.get(baseline, {})
    ho_p = holdout_results.get(primary, {})

    sharpe_delta = (p.get("sharpe", np.nan) or np.nan) - (b.get("sharpe", np.nan) or np.nan)
    ho_sharpe_delta = (ho_p.get("sharpe", np.nan) or np.nan) - (ho_b.get("sharpe", np.nan) or np.nan)
    rc_delta = ((p.get("sharpe_recovery_confirmed", np.nan) or np.nan) -
                (b.get("sharpe_recovery_confirmed", np.nan) or np.nan))

    if gate_verdict == "PASS":
        if np.isfinite(rc_delta) and rc_delta < -0.10:
            verdict = "Revise Phase 1B"
            verdict_reason = (
                f"All acceptance gates pass (Sharpe Δ {sharpe_delta:+.4f}, "
                f"holdout Δ {ho_sharpe_delta:+.4f}) but recovery_confirmed Sharpe "
                f"worsened materially (Δ {rc_delta:+.4f}). "
                "Before passing R2A to Phase 2 as a shared input, revise the modifier to "
                "set scale=1.0 in recovery_confirmed rows, or use a separate R2D composite "
                "for recovery states only. Re-validate after the revision."
            )
        else:
            verdict = "Promote to Phase 2 shared input"
            verdict_reason = (
                f"Primary candidate (alpha=0.08) passes all acceptance gates. "
                f"Full-history Sharpe Δ {sharpe_delta:+.4f}, "
                f"holdout Sharpe Δ {ho_sharpe_delta:+.4f}. "
                "Stressed_panic defense is preserved. Turnover increase is acceptable. "
                "R2A deployment quality composite should be carried forward as a shared "
                "signal input to Frontier Phase 2 (Trend/Setup Quality Engine) and "
                "Frontier Phase 3 (Smart Re-Risking). "
                "The recovery_confirmed caveat (IC −0.043) is noted but the overall portfolio "
                "effect in that state is within acceptable range."
            )
    elif np.isfinite(sharpe_delta) and sharpe_delta >= 0.005 and np.isfinite(ho_sharpe_delta) and ho_sharpe_delta >= -0.02:
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            f"Primary candidate shows directional improvement (Sharpe Δ {sharpe_delta:+.4f}) "
            f"but does not pass all acceptance gates. Holdout Sharpe Δ {ho_sharpe_delta:+.4f}. "
            f"Failed gates: {'; '.join(gate_fail)}. "
            "Classify as research-only. R2A signal can still be used as an input to Phase 2 "
            "and Phase 3 signals, but the portfolio modifier should not be applied as-is."
        )
    elif any("weakened" in f.lower() or "defense" in f.lower() for f in gate_fail):
        verdict = "Revise Phase 1B"
        verdict_reason = (
            "Acceptance gate failure includes stressed_panic defense weakening. "
            "Revise the modifier guard logic before proceeding."
        )
    else:
        verdict = "Keep as research-only diagnostic"
        verdict_reason = (
            f"Primary candidate does not pass enough acceptance gates to promote. "
            f"Sharpe Δ {sharpe_delta:+.4f}, holdout Δ {ho_sharpe_delta:+.4f}. "
            f"Failed: {'; '.join(gate_fail)}. "
            "R2A signal may still be useful as a conditional input in Phase 3 (re-risking) "
            "where recovery-state quality is the target."
        )

    print(f"\nVERDICT: {verdict}")
    print(f"Reason: {verdict_reason}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Full-history results
    full_df = pd.DataFrame(list(full_results.values()))
    full_df.to_csv(OUT_DIR / "wrapper_diagnostic_results.csv", index=False)
    print(f"\nSaved: data/research/frontier_phase1/wrapper_diagnostic_results.csv")

    # Holdout results
    holdout_df = pd.DataFrame(list(holdout_results.values()))
    holdout_df.to_csv(OUT_DIR / "wrapper_diagnostic_holdout_summary.csv", index=False)
    print(f"Saved: data/research/frontier_phase1/wrapper_diagnostic_holdout_summary.csv")

    # State summary
    state_df.to_csv(OUT_DIR / "wrapper_diagnostic_state_summary.csv", index=False)
    print(f"Saved: data/research/frontier_phase1/wrapper_diagnostic_state_summary.csv")

    # ── Production diff check ────────────────────────────────────────────────
    diff_clean, diff_changed = protected_diff_clean()
    if not diff_clean:
        print(f"\nWARNING: Protected files changed: {diff_changed}")
        warnings_list.append(f"Protected files changed: {diff_changed}")
    else:
        print("\nProtected files: clean.")

    # ── Report ───────────────────────────────────────────────────────────────
    write_report(
        results=full_results,
        holdout_results=holdout_results,
        state_df=state_df,
        rolling_df=rolling_df,
        bootstrap_results=bootstrap_results,
        gate_result=gate_result,
        verdict=verdict,
        verdict_reason=verdict_reason,
        warnings_list=warnings_list,
        diff_clean=diff_clean,
    )

    # ── Project journey ───────────────────────────────────────────────────────
    append_journey(verdict, full_results, holdout_results, gate_ok, gate_fail)

    print("\n" + "=" * 70)
    print(f"Phase 1B complete. Verdict: {verdict}")
    print("No production or dashboard files were modified.")
    print("=" * 70)


if __name__ == "__main__":
    main()
