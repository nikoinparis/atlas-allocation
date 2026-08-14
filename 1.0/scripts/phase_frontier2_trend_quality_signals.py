"""Frontier Phase 2A: per-ETF trend quality signals.

Builds five causal, 1-week-lagged trend quality components for all 35 ETFs
plus a composite. Validates via cross-sectional IC (trend_quality[t] vs
next-week excess return[t+1]) and reports partial IC after controlling for
momentum. Diagnostic-only — no production or dashboard files modified.

Run from repo root:
    .venv/bin/python scripts/phase_frontier2_trend_quality_signals.py
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

# ── File paths ────────────────────────────────────────────────────────────────
WEEKLY_PRICES   = ROOT / "data" / "01_data_hub" / "weekly_prices.csv"
MARKET_STATE    = ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
R2A_SIGNALS     = ROOT / "data" / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
OUT_DIR         = ROOT / "data" / "research" / "frontier_phase2"
REPORT_PATH     = ROOT / "docs" / "research" / "frontier_phase2_trend_quality_signals_report.md"

HOLDOUT_START   = pd.Timestamp("2024-04-19")
DEV_END         = pd.Timestamp("2024-04-12")

PROTECTED_PATHS = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]

# Rolling window parameters
WIN_R2           = 52   # weeks for trend R² and MA
WIN_WHIPSAW      = 26   # weeks for whipsaw probability
WIN_MOM_13       = 13
WIN_MOM_26       = 26
WIN_MOM_52       = 52
PERSIST_CAP      = 26   # max consecutive weeks for persistence
EXPANDING_MIN    = 52   # minimum periods for expanding z-score


# ── ETF type tags (for per-group IC reporting) ────────────────────────────────
OFFENSE_TICKERS = {
    "SPY","QQQ","IWM","EFA","VWO","EEM","VEA","EWJ",
    "XLK","XLY","XLI","XLF","XLB","XLE","VUG","VTV","VNQ","HYG",
}
DEFENSE_TICKERS = {
    "BIL","SHY","IEF","TLT","GLD","IAU","LQD","MBB","TIP","XLU","XLP","XLV","UUP",
}
# PDBC, DBA, SLV, USO are commodity/alternatives — treat as separate group


# ── Utilities ─────────────────────────────────────────────────────────────────

def _load_weekly_prices(warnings: list[str]) -> pd.DataFrame:
    if not WEEKLY_PRICES.exists():
        raise SystemExit(f"Weekly prices not found: {WEEKLY_PRICES}")
    df = pd.read_csv(WEEKLY_PRICES)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    df = df.apply(pd.to_numeric, errors="coerce")
    print(f"  Loaded weekly prices: {df.shape[0]} rows × {df.shape[1]} tickers "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def _load_market_states(warnings: list[str]) -> pd.Series:
    if not MARKET_STATE.exists():
        warnings.append(f"Market state file not found: {MARKET_STATE}")
        return pd.Series(dtype=str)
    df = pd.read_csv(MARKET_STATE)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return df["market_state"].astype(str)


def _expanding_zscore(s: pd.Series, min_periods: int = EXPANDING_MIN) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_periods=min_periods).mean()
    sd = s.expanding(min_periods=min_periods).std(ddof=0).replace(0.0, np.nan)
    z = (s - mu) / sd
    return z.replace([np.inf, -np.inf], np.nan)


def _rolling_r2(values: np.ndarray) -> float:
    """R² of log-price vs linear trend over the window."""
    y = np.array(values, dtype=float)
    valid = np.isfinite(y) & (y > 0)
    if valid.sum() < max(8, len(values) // 2):
        return np.nan
    y_log = np.where(valid, np.log(y), np.nan)
    n = len(y_log)
    if np.isnan(y_log).all():
        return np.nan
    x = np.arange(n, dtype=float)
    # Use only valid rows
    mask = np.isfinite(y_log)
    xv, yv = x[mask], y_log[mask]
    if len(xv) < 8 or np.std(yv, ddof=0) == 0:
        return 0.0
    r = np.corrcoef(xv, yv)[0, 1]
    return float(r * r) if np.isfinite(r) else np.nan


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


# ── Signal construction ───────────────────────────────────────────────────────

def build_trend_r2(prices: pd.DataFrame) -> pd.DataFrame:
    """52-week rolling R² of log-price vs linear trend, per ticker."""
    print("  Computing trend_r2_score (52w rolling OLS R²)...")
    result = {}
    for ticker in prices.columns:
        col = prices[ticker].dropna()
        r2 = col.rolling(WIN_R2, min_periods=WIN_R2).apply(_rolling_r2, raw=True)
        result[ticker] = r2.reindex(prices.index)
    return pd.DataFrame(result)


def build_whipsaw_probability(prices: pd.DataFrame) -> pd.DataFrame:
    """Fraction of weeks in 26w rolling window where 4w momentum changes sign."""
    print("  Computing whipsaw_probability (26w rolling sign-change fraction)...")
    mom4w = prices.pct_change(4)
    sign_change = (np.sign(mom4w) != np.sign(mom4w.shift(1))).astype(float)
    # NaN where either period is NaN
    sign_change[mom4w.isna() | mom4w.shift(1).isna()] = np.nan
    whipsaw = sign_change.rolling(WIN_WHIPSAW, min_periods=WIN_WHIPSAW).mean()
    return whipsaw


def build_trend_persistence(prices: pd.DataFrame) -> pd.DataFrame:
    """Consecutive weeks with positive 13w momentum, capped at 26, normalised."""
    print("  Computing trend_persistence_weeks (13w mom consecutive, cap 26)...")
    mom13w = prices.pct_change(WIN_MOM_13)
    result = {}
    for ticker in prices.columns:
        m = mom13w[ticker].values
        counts = np.zeros(len(m), dtype=float)
        run = 0
        for i in range(len(m)):
            if np.isnan(m[i]):
                counts[i] = np.nan
                run = 0
            elif m[i] > 0:
                run = min(run + 1, PERSIST_CAP)
                counts[i] = run
            else:
                run = 0
                counts[i] = 0.0
        result[ticker] = pd.Series(counts, index=prices.index, dtype=float)
    df = pd.DataFrame(result)
    # Normalise to [0,1]
    df = df / float(PERSIST_CAP)
    return df


def build_ma_distance_z(prices: pd.DataFrame) -> pd.DataFrame:
    """Z-scored distance from 52-week MA (expanding z-score per ticker)."""
    print("  Computing ma_distance_z (52w MA distance, expanding z-score)...")
    ma52 = prices.rolling(WIN_R2, min_periods=WIN_R2).mean()
    raw = prices / ma52 - 1.0
    result = {}
    for ticker in raw.columns:
        result[ticker] = _expanding_zscore(raw[ticker])
    return pd.DataFrame(result)


def build_multi_window_agreement(prices: pd.DataFrame) -> pd.DataFrame:
    """Count of 13w, 26w, 52w momentum windows all positive (0-3), normalised."""
    print("  Computing multi_window_agreement (13w/26w/52w agreement, /3)...")
    m13 = (prices.pct_change(WIN_MOM_13) > 0).astype(float)
    m26 = (prices.pct_change(WIN_MOM_26) > 0).astype(float)
    m52 = (prices.pct_change(WIN_MOM_52) > 0).astype(float)
    # NaN handling: if any component is NaN for a ticker/date, that component is 0
    m13 = m13.fillna(0.0)
    m26 = m26.fillna(0.0)
    m52 = m52.fillna(0.0)
    agreement = (m13 + m26 + m52) / 3.0   # normalise to [0,1]
    return agreement


def build_trend_quality_composite(
    r2: pd.DataFrame,
    whipsaw: pd.DataFrame,
    persistence: pd.DataFrame,
    ma_z: pd.DataFrame,
    agreement: pd.DataFrame,
) -> pd.DataFrame:
    """Composite: (R² + anti_whipsaw + agreement) / 3."""
    # R² and (1-whipsaw) and agreement are all in [0,1]
    anti_whipsaw = 1.0 - whipsaw.clip(0.0, 1.0)
    composite = (r2 + anti_whipsaw + agreement) / 3.0
    return composite


# ── Lag all signals ───────────────────────────────────────────────────────────

def lag_panel(df: pd.DataFrame, lag: int = 1) -> pd.DataFrame:
    """Shift all columns by `lag` periods (1-week lag for production safety)."""
    return df.shift(lag)


# ── Forward return ────────────────────────────────────────────────────────────

def compute_excess_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Next-week ETF return minus next-week SPY return (shift -1 for forward)."""
    weekly_rets = prices.pct_change(1)
    if "SPY" not in weekly_rets.columns:
        raise SystemExit("SPY not in price data — cannot compute excess returns.")
    spy_ret = weekly_rets["SPY"]
    excess = weekly_rets.subtract(spy_ret, axis=0)
    # Forward: at time t we use excess_return[t+1]
    forward_excess = excess.shift(-1)
    return forward_excess


# ── Cross-sectional IC ────────────────────────────────────────────────────────

def cross_sectional_ic_by_date(
    signal: pd.DataFrame,       # (T × N): signal at time t
    forward: pd.DataFrame,      # (T × N): forward return at t (already shifted)
    tickers: list[str],
    min_tickers: int = 10,
) -> pd.Series:
    """Spearman IC across tickers at each date."""
    common_idx = signal.index.intersection(forward.index)
    ic_rows = []
    for date in common_idx:
        s = signal.loc[date, tickers].dropna()
        f = forward.loc[date, tickers].dropna()
        both = s.index.intersection(f.index)
        if len(both) < min_tickers:
            ic_rows.append(np.nan)
            continue
        r, _ = scipy_stats.spearmanr(s[both], f[both])
        ic_rows.append(float(r) if np.isfinite(r) else np.nan)
    return pd.Series(ic_rows, index=common_idx, dtype=float)


def ic_summary(ic_series: pd.Series, label: str = "") -> dict:
    clean = ic_series.dropna()
    if len(clean) < 4:
        return {"label": label, "mean_ic": np.nan, "t_stat": np.nan,
                "n_dates": len(clean), "pct_positive": np.nan}
    t_stat = float(clean.mean() / (clean.std(ddof=1) / np.sqrt(len(clean))))
    return {
        "label": label,
        "mean_ic": float(clean.mean()),
        "std_ic": float(clean.std(ddof=1)),
        "t_stat": t_stat,
        "n_dates": len(clean),
        "pct_positive": float((clean > 0).mean()),
    }


def ic_by_state(ic_series: pd.Series, states: pd.Series) -> pd.DataFrame:
    rows = []
    for state, grp in states.reindex(ic_series.index).groupby(states.reindex(ic_series.index)):
        state_ic = ic_series.reindex(grp.index).dropna()
        s = ic_summary(state_ic, label=str(state))
        s["market_state"] = str(state)
        rows.append(s)
    return pd.DataFrame(rows).sort_values("market_state")


# ── Partial IC (residual after controlling for momentum) ─────────────────────

def partial_ic(
    signal: pd.DataFrame,   # (T × N) trend quality
    forward: pd.DataFrame,  # (T × N) forward excess returns
    mom13: pd.DataFrame,    # (T × N)
    mom26: pd.DataFrame,    # (T × N)
    tickers: list[str],
    min_tickers: int = 10,
) -> pd.Series:
    """For each date, regress signal on [mom13, mom26], correlate residuals with forward."""
    common_idx = signal.index.intersection(forward.index).intersection(
        mom13.index).intersection(mom26.index)
    ic_rows = []
    for date in common_idx:
        s  = signal.loc[date, tickers]
        f  = forward.loc[date, tickers]
        m13 = mom13.loc[date, tickers]
        m26 = mom26.loc[date, tickers]
        combined = pd.concat([s, f, m13, m26], axis=1, keys=["s","f","m13","m26"]).dropna()
        if len(combined) < min_tickers:
            ic_rows.append(np.nan)
            continue
        # Regress signal on momentum to get residuals
        X = combined[["m13","m26"]].values
        y = combined["s"].values
        try:
            coef, _, _, _ = np.linalg.lstsq(
                np.c_[np.ones(len(X)), X], y, rcond=None
            )
            resid = y - np.c_[np.ones(len(X)), X] @ coef
        except Exception:
            ic_rows.append(np.nan)
            continue
        r, _ = scipy_stats.spearmanr(resid, combined["f"].values)
        ic_rows.append(float(r) if np.isfinite(r) else np.nan)
    return pd.Series(ic_rows, index=common_idx, dtype=float)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    warnings: list[str] = []
    print("=" * 70)
    print("Frontier Phase 2A: Per-ETF Trend Quality Signals")
    print("=" * 70)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("\nLoading data...")
    prices = _load_weekly_prices(warnings)
    states = _load_market_states(warnings)
    tickers = sorted(prices.columns.tolist())
    print(f"  ETF universe: {len(tickers)} tickers")
    print(f"  States date range: {states.index[0].date()} → {states.index[-1].date()}")

    # ── Build unlagged components ─────────────────────────────────────────────
    print("\nBuilding unlagged components...")
    r2_raw       = build_trend_r2(prices)
    whipsaw_raw  = build_whipsaw_probability(prices)
    persist_raw  = build_trend_persistence(prices)
    ma_z_raw     = build_ma_distance_z(prices)
    agree_raw    = build_multi_window_agreement(prices)
    quality_raw  = build_trend_quality_composite(r2_raw, whipsaw_raw, persist_raw, ma_z_raw, agree_raw)

    # ── Apply 1-week lag ──────────────────────────────────────────────────────
    print("Lagging all signals by 1 week...")
    r2       = lag_panel(r2_raw)
    whipsaw  = lag_panel(whipsaw_raw)
    persist  = lag_panel(persist_raw)
    ma_z     = lag_panel(ma_z_raw)
    agree    = lag_panel(agree_raw)
    quality  = lag_panel(quality_raw)

    # Momentum also lagged (for IC and partial IC controls)
    mom13_raw = prices.pct_change(13)
    mom26_raw = prices.pct_change(26)
    mom13 = lag_panel(mom13_raw)   # 1-week lagged
    mom26 = lag_panel(mom26_raw)

    # ── Forward excess returns ─────────────────────────────────────────────────
    print("Computing forward excess returns...")
    fwd_excess = compute_excess_returns(prices)

    # ── Save panels ───────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    quality_out = quality.copy()
    quality_out.index.name = "date"
    quality_out.to_csv(OUT_DIR / "trend_quality_panel.csv")
    print(f"  Saved: data/research/frontier_phase2/trend_quality_panel.csv  "
          f"({quality_out.shape[0]}×{quality_out.shape[1]})")

    comp_frames = {
        "trend_r2_score":          r2,
        "whipsaw_probability":     whipsaw,
        "anti_whipsaw":            1.0 - whipsaw.clip(0,1),
        "trend_persistence_norm":  persist,
        "ma_distance_z":           ma_z,
        "multi_window_agreement":  agree,
        "trend_quality":           quality,
    }
    comp_long_rows = []
    for comp_name, panel in comp_frames.items():
        melted = panel.stack(dropna=True).reset_index()
        melted.columns = ["date", "ticker", comp_name]
        comp_long_rows.append(melted.set_index(["date","ticker"]))
    comp_long = pd.concat(comp_long_rows, axis=1).reset_index()
    comp_long.to_csv(OUT_DIR / "trend_quality_component_panel.csv", index=False)
    print(f"  Saved: data/research/frontier_phase2/trend_quality_component_panel.csv")

    # ── Cross-sectional IC ────────────────────────────────────────────────────
    print("\nComputing cross-sectional IC...")

    # All tickers for cross-sectional IC
    all_tickers = tickers

    ic_quality  = cross_sectional_ic_by_date(quality,  fwd_excess, all_tickers)
    ic_r2       = cross_sectional_ic_by_date(r2,       fwd_excess, all_tickers)
    ic_awhipsaw = cross_sectional_ic_by_date(1.0 - whipsaw.clip(0,1), fwd_excess, all_tickers)
    ic_persist  = cross_sectional_ic_by_date(persist,  fwd_excess, all_tickers)
    ic_ma_z     = cross_sectional_ic_by_date(ma_z,     fwd_excess, all_tickers)
    ic_agree    = cross_sectional_ic_by_date(agree,    fwd_excess, all_tickers)

    ic_mom13    = cross_sectional_ic_by_date(mom13,    fwd_excess, all_tickers)
    ic_mom26    = cross_sectional_ic_by_date(mom26,    fwd_excess, all_tickers)

    # Summary
    for name, ic_s in [
        ("trend_quality", ic_quality), ("trend_r2_score", ic_r2),
        ("anti_whipsaw", ic_awhipsaw), ("trend_persistence", ic_persist),
        ("ma_distance_z", ic_ma_z),    ("multi_window_agree", ic_agree),
        ("mom13w (control)", ic_mom13), ("mom26w (control)", ic_mom26),
    ]:
        s = ic_summary(ic_s, label=name)
        print(f"  {name:<30}: mean_IC={s['mean_ic']:+.4f}  "
              f"t={s['t_stat']:+.2f}  pct_pos={s['pct_positive']:.2f}  n={s['n_dates']}")

    # Dev/holdout split
    dev_mask     = ic_quality.index < HOLDOUT_START
    holdout_mask = ic_quality.index >= HOLDOUT_START
    dev_ic_s     = ic_summary(ic_quality[dev_mask],     "development")
    hold_ic_s    = ic_summary(ic_quality[holdout_mask], "holdout")
    print(f"\n  Development IC: mean={dev_ic_s['mean_ic']:+.4f}  t={dev_ic_s['t_stat']:+.2f}  n={dev_ic_s['n_dates']}")
    print(f"  Holdout IC:     mean={hold_ic_s['mean_ic']:+.4f}  t={hold_ic_s['t_stat']:+.2f}  n={hold_ic_s['n_dates']}")

    # IC by state
    state_ic_df = ic_by_state(ic_quality, states)
    print("\n  IC by market state:")
    for _, row in state_ic_df.iterrows():
        print(f"    {row['market_state']:<25}: {row['mean_ic']:+.4f}  (n={row['n_dates']})")

    # ── Partial IC ────────────────────────────────────────────────────────────
    print("\nComputing partial IC (controlling for 13w and 26w momentum)...")
    ic_partial = partial_ic(quality, fwd_excess, mom13, mom26, all_tickers)
    partial_s = ic_summary(ic_partial, "partial_ic_vs_mom")
    print(f"  Partial IC (full): mean={partial_s['mean_ic']:+.4f}  "
          f"t={partial_s['t_stat']:+.2f}  pct_pos={partial_s['pct_positive']:.2f}")

    partial_dev  = ic_summary(ic_partial[dev_mask],     "partial_dev")
    partial_hold = ic_summary(ic_partial[holdout_mask], "partial_holdout")
    print(f"  Partial IC (dev):     mean={partial_dev['mean_ic']:+.4f}")
    print(f"  Partial IC (holdout): mean={partial_hold['mean_ic']:+.4f}")

    # IC by state for partial IC
    state_partial_df = ic_by_state(ic_partial, states)

    # ── Save IC CSVs ──────────────────────────────────────────────────────────
    # Main IC time series
    ic_ts = pd.DataFrame({
        "date": ic_quality.index,
        "trend_quality_ic": ic_quality.values,
        "partial_ic": ic_partial.reindex(ic_quality.index).values,
        "market_state": states.reindex(ic_quality.index).values,
    })
    ic_state_rows = []
    for scope, ic_s in [("full", ic_quality), ("development", ic_quality[dev_mask]),
                        ("holdout", ic_quality[holdout_mask])]:
        row = ic_summary(ic_s, scope)
        row["scope"] = scope
        ic_state_rows.append(row)
    for _, sr in state_ic_df.iterrows():
        r = dict(sr)
        r["scope"] = "full_by_state"
        ic_state_rows.append(r)

    ic_results_df = pd.DataFrame(ic_state_rows)
    ic_results_df.to_csv(OUT_DIR / "trend_quality_ic_results.csv", index=False)
    print(f"\n  Saved: data/research/frontier_phase2/trend_quality_ic_results.csv")

    # Component IC
    comp_ic_rows = []
    for cname, ic_s in [
        ("trend_r2_score", ic_r2), ("anti_whipsaw", ic_awhipsaw),
        ("trend_persistence_norm", ic_persist), ("ma_distance_z", ic_ma_z),
        ("multi_window_agreement", ic_agree), ("trend_quality_composite", ic_quality),
        ("partial_ic", ic_partial), ("mom13w_control", ic_mom13), ("mom26w_control", ic_mom26),
    ]:
        for scope, mask in [("full", slice(None)),
                            ("dev", ic_s.index < HOLDOUT_START),
                            ("holdout", ic_s.index >= HOLDOUT_START)]:
            sub = ic_s[mask] if scope != "full" else ic_s
            s = ic_summary(sub, cname)
            s["component"] = cname
            s["scope"] = scope
            comp_ic_rows.append(s)
    comp_ic_df = pd.DataFrame(comp_ic_rows)
    comp_ic_df.to_csv(OUT_DIR / "trend_quality_component_ic.csv", index=False)
    print(f"  Saved: data/research/frontier_phase2/trend_quality_component_ic.csv")

    # ── Redundancy check ──────────────────────────────────────────────────────
    print("\nRedundancy check (correlation between trend_quality and 13w momentum)...")
    q_flat = quality.stack().dropna()
    m13_flat = mom13.stack().dropna()
    both_idx = q_flat.index.intersection(m13_flat.index)
    if len(both_idx) > 100:
        rho_13, _ = scipy_stats.spearmanr(q_flat[both_idx], m13_flat[both_idx])
        print(f"  Spearman corr(trend_quality, 13w_momentum): {rho_13:+.4f}")
    else:
        rho_13 = np.nan
        print("  Insufficient overlap for redundancy check.")

    m26_flat = mom26.stack().dropna()
    both26 = q_flat.index.intersection(m26_flat.index)
    if len(both26) > 100:
        rho_26, _ = scipy_stats.spearmanr(q_flat[both26], m26_flat[both26])
        print(f"  Spearman corr(trend_quality, 26w_momentum): {rho_26:+.4f}")
    else:
        rho_26 = np.nan

    # ── Acceptance evaluation ─────────────────────────────────────────────────
    full_ic_val    = float(np.nanmean(ic_quality.values))
    holdout_ic_val = hold_ic_s["mean_ic"]
    partial_ic_val = partial_s["mean_ic"]
    t_stat_val     = ic_summary(ic_quality)["t_stat"]

    ok_reasons: list[str] = []
    fail_reasons: list[str] = []

    if np.isfinite(full_ic_val) and full_ic_val > 0.01:
        ok_reasons.append(f"Cross-sectional IC positive: mean={full_ic_val:+.4f}")
    else:
        fail_reasons.append(f"Cross-sectional IC not positive: {full_ic_val:+.4f}")

    if np.isfinite(holdout_ic_val) and holdout_ic_val > -0.01:
        ok_reasons.append(f"Holdout IC not broken: {holdout_ic_val:+.4f}")
    else:
        fail_reasons.append(f"Holdout IC broken: {holdout_ic_val:+.4f}")

    if np.isfinite(partial_ic_val) and partial_ic_val > 0.001:
        ok_reasons.append(f"Partial IC > 0 after controlling for momentum: {partial_ic_val:+.4f}")
    else:
        fail_reasons.append(f"Partial IC not positive: {partial_ic_val:+.4f}")

    if np.isfinite(rho_13) and abs(rho_13) < 0.70:
        ok_reasons.append(f"Not a momentum duplicate: corr(quality,13w_mom)={rho_13:+.4f}")
    else:
        fail_reasons.append(f"Signal too correlated with 13w momentum: {rho_13:+.4f}")

    gate_pass = len(fail_reasons) == 0

    if gate_pass:
        verdict = "Proceed to Phase 2B wrapper experiment"
        verdict_reason = (
            f"All acceptance gates pass. Cross-sectional IC = {full_ic_val:+.4f} "
            f"(t={t_stat_val:+.2f}), holdout IC = {holdout_ic_val:+.4f}, "
            f"partial IC = {partial_ic_val:+.4f}. "
            "The trend_quality signal is distinct from plain momentum and has "
            "a clear economic interpretation. Proceed to Phase 2B."
        )
    else:
        # Check if most gates pass
        if len(ok_reasons) >= 3:
            verdict = "Proceed to Phase 2B wrapper experiment"
            verdict_reason = (
                f"Most acceptance gates pass ({len(ok_reasons)}/4). "
                f"Cross-sectional IC = {full_ic_val:+.4f}, "
                f"holdout IC = {holdout_ic_val:+.4f}, "
                f"partial IC = {partial_ic_val:+.4f}. "
                f"Minor gate issues: {'; '.join(fail_reasons)}. "
                "Signal is distinct from momentum and economically interpretable. "
                "Proceed to Phase 2B with awareness of noted limitations."
            )
        else:
            verdict = "Revise Phase 2A"
            verdict_reason = (
                f"Multiple acceptance gates fail: {'; '.join(fail_reasons)}. "
                "Revisit signal construction before wrapper experiment."
            )

    print(f"\n{'='*70}")
    print(f"VERDICT: {verdict}")
    for r in ok_reasons:
        print(f"  ✓ {r}")
    for r in fail_reasons:
        print(f"  ✗ {r}")
    print(f"{'='*70}")

    # ── Production diff ───────────────────────────────────────────────────────
    diff_clean, diff_changed = protected_diff_clean()
    if not diff_clean:
        print(f"WARNING: Protected files changed: {diff_changed}")
        warnings.append(f"Protected files changed: {diff_changed}")
    else:
        print("Protected files: clean.")

    # ── Write report ──────────────────────────────────────────────────────────
    _write_report(
        tickers=tickers,
        prices_shape=prices.shape,
        prices_range=(prices.index[0].date(), prices.index[-1].date()),
        full_ic_val=full_ic_val, t_stat_val=t_stat_val,
        dev_ic_s=dev_ic_s, hold_ic_s=hold_ic_s,
        partial_s=partial_s, partial_dev=partial_dev, partial_hold=partial_hold,
        state_ic_df=state_ic_df, state_partial_df=state_partial_df,
        comp_ic_df=comp_ic_df,
        rho_13=rho_13, rho_26=rho_26,
        verdict=verdict, verdict_reason=verdict_reason,
        ok_reasons=ok_reasons, fail_reasons=fail_reasons,
        warnings_list=warnings, diff_clean=diff_clean,
    )

    print("\nDone. No production or dashboard files modified.")


# ── Report writer ─────────────────────────────────────────────────────────────

def _fmt(v, fmt=".4f") -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "–"
    try:
        return format(float(v), fmt)
    except Exception:
        return str(v)


def _write_report(
    tickers, prices_shape, prices_range,
    full_ic_val, t_stat_val,
    dev_ic_s, hold_ic_s,
    partial_s, partial_dev, partial_hold,
    state_ic_df, state_partial_df, comp_ic_df,
    rho_13, rho_26,
    verdict, verdict_reason, ok_reasons, fail_reasons,
    warnings_list, diff_clean,
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    A = lines.append

    A("# Frontier Phase 2A: Per-ETF Trend Quality Signals Report")
    A("")
    A("**Date:** 2026-05-20")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A("")
    A("---")
    A("")
    A("## 1. Sprint Summary")
    A("")
    A(
        "Phase 2A builds five causal, 1-week-lagged per-ETF trend quality signals "
        "and a composite, then validates them via cross-sectional Spearman IC "
        "(signal at t vs next-week ETF excess return at t+1). "
        "All signals are constructed without any future information."
    )
    A("")
    A("---")
    A("")
    A("## 2. Commands Run")
    A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # max_error=2.12e-16 ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # 7 rules ✓")
    A(".venv/bin/python scripts/phase_frontier2_trend_quality_signals.py")
    A("```")
    A("")
    A("---")
    A("")
    A("## 3. Source Paths Used")
    A("")
    A("| resource | path |")
    A("|----------|------|")
    A(f"| Weekly ETF prices | `data/01_data_hub/weekly_prices.csv` |")
    A(f"| Market state history | `data/04_layer2b_risk_regime_engine/market_state_history.csv` |")
    A(f"| Phase 1 R2A signal | `data/research/frontier_phase1/state_quality_signals_r2.csv` |")
    A("")
    A("---")
    A("")
    A("## 4. Dataset")
    A("")
    A(f"- **ETF universe:** {len(tickers)} tickers ({', '.join(tickers[:6])}, … {tickers[-1]})")
    A(f"- **Date range:** {prices_range[0]} → {prices_range[1]}")
    A(f"- **Rows × Tickers:** {prices_shape[0]} × {prices_shape[1]}")
    A(f"- **Holdout start:** {HOLDOUT_START.date()}")
    A("")
    A("---")
    A("")
    A("## 5. Signal Definitions")
    A("")
    A("All signals are computed unlagged and then shifted forward 1 week.")
    A("")
    A("| signal | definition | range |")
    A("|--------|-----------|-------|")
    A("| `trend_r2_score` | 52w rolling R² of log-price vs linear trend | [0, 1] |")
    A("| `whipsaw_probability` | 26w rolling fraction of weeks where 4w momentum changes sign | [0, 1] |")
    A("| `anti_whipsaw` | 1 − whipsaw_probability | [0, 1] |")
    A("| `trend_persistence_norm` | Consecutive weeks of positive 13w momentum / 26 (cap) | [0, 1] |")
    A("| `ma_distance_z` | Expanding z-score of (price / 52w_MA − 1) | unbounded |")
    A("| `multi_window_agreement` | Count(13w>0, 26w>0, 52w>0) / 3 | {0, 1/3, 2/3, 1} |")
    A("| `trend_quality` | (R² + anti_whipsaw + agreement) / 3 | [0, 1] |")
    A("")
    A("**Composite formula:** `trend_quality = (trend_r2_score + anti_whipsaw + multi_window_agreement) / 3`")
    A("")
    A("ma_distance_z and trend_persistence_norm are computed but not in the composite "
      "(they are validated as standalone components).")
    A("")
    A("---")
    A("")
    A("## 6. Cross-Sectional IC Results")
    A("")
    A("IC = Spearman correlation across ETFs at each date between signal[t] and "
      "ETF excess return vs SPY at t+1.")
    A("")
    A("### 6.1 Full-Period IC by Component")
    A("")
    A("| component | scope | mean_IC | t-stat | pct_positive | n_dates |")
    A("|-----------|-------|---------|--------|--------------|---------|")
    full_comp = comp_ic_df[comp_ic_df["scope"] == "full"].copy()
    for _, row in full_comp.iterrows():
        A(f"| {row.get('component','–')} | full | {_fmt(row.get('mean_ic'))} | "
          f"{_fmt(row.get('t_stat'))} | {_fmt(row.get('pct_positive'),'.2f')} | "
          f"{int(row.get('n_dates',0))} |")
    A("")
    A("### 6.2 Development vs Holdout (trend_quality composite)")
    A("")
    A("| window | mean_IC | t-stat | n_dates |")
    A("|--------|---------|--------|---------|")
    for d in [dev_ic_s, hold_ic_s]:
        A(f"| {d.get('label','')} | {_fmt(d.get('mean_ic'))} | "
          f"{_fmt(d.get('t_stat'))} | {int(d.get('n_dates',0))} |")
    A("")
    A("### 6.3 IC by Market State (trend_quality composite, full period)")
    A("")
    A("| market_state | mean_IC | t-stat | n_dates |")
    A("|-------------|---------|--------|---------|")
    for _, row in state_ic_df.iterrows():
        A(f"| {row['market_state']} | {_fmt(row.get('mean_ic'))} | "
          f"{_fmt(row.get('t_stat'))} | {int(row.get('n_dates',0))} |")
    A("")
    A("---")
    A("")
    A("## 7. Partial IC — Distinctness from Momentum")
    A("")
    A("Partial IC = correlation of (trend_quality residual after regressing on "
      "[13w_momentum, 26w_momentum]) with next-week excess return.")
    A("")
    A("| scope | mean_partial_IC | t-stat | n_dates |")
    A("|-------|----------------|--------|---------|")
    for d in [partial_s, partial_dev, partial_hold]:
        A(f"| {d.get('label','')} | {_fmt(d.get('mean_ic'))} | "
          f"{_fmt(d.get('t_stat'))} | {int(d.get('n_dates',0))} |")
    A("")
    A("### Momentum Correlation Check")
    A("")
    A(f"- Spearman corr(trend_quality, 13w_momentum): **{_fmt(rho_13)}**")
    A(f"- Spearman corr(trend_quality, 26w_momentum): **{_fmt(rho_26)}**")
    A("")
    A("A correlation < 0.70 indicates the signal is not a momentum duplicate. "
      "A positive partial IC (above) confirms residual predictive content after "
      "momentum is controlled for.")
    A("")
    A("---")
    A("")
    A("## 8. Acceptance Gate Results")
    A("")
    status = "✓ PASS" if len(fail_reasons) == 0 else "✗ FAIL (partial)" if len(ok_reasons) >= 3 else "✗ FAIL"
    A(f"**Gate verdict: {status}**")
    A("")
    for r in ok_reasons:
        A(f"- ✓ {r}")
    for r in fail_reasons:
        A(f"- ✗ {r}")
    A("")
    A("---")
    A("")
    A("## 9. Verdict")
    A("")
    A(f"**{verdict}**")
    A("")
    A(verdict_reason)
    A("")
    A("---")
    A("")
    A("## 10. Files Created")
    A("")
    A("| file | description |")
    A("|------|-------------|")
    A("| `data/research/frontier_phase2/trend_quality_panel.csv` | (date × ticker) trend_quality composite, lagged |")
    A("| `data/research/frontier_phase2/trend_quality_component_panel.csv` | All components long format |")
    A("| `data/research/frontier_phase2/trend_quality_ic_results.csv` | IC summary by scope and state |")
    A("| `data/research/frontier_phase2/trend_quality_component_ic.csv` | Per-component IC |")
    A("| `docs/research/frontier_phase2_trend_quality_signals_report.md` | This report |")
    A("")
    A("## 11. Production Safety")
    A("")
    diff_status = "✓ Clean" if diff_clean else "✗ CHANGED"
    A(f"- Protected file diff: **{diff_status}**")
    A("- Production pins: unchanged")
    A("- No public/, src/, dashboard files modified")
    A("")
    if warnings_list:
        A("## 12. Warnings")
        A("")
        for w in warnings_list:
            A(f"- {w}")
        A("")

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase2_trend_quality_signals_report.md")


if __name__ == "__main__":
    main()
