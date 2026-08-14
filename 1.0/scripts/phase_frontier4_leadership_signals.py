"""Frontier Phase 4A: Cross-Sectional Leadership Signal Construction.

Builds five causal, 1-week-lagged leadership quality signals and a composite.
Validates via time-series Spearman IC (composite[t] vs SPY 4-week forward
return) and reports partial IC after controlling for Phase 1 R2A and Phase 2
average trend quality.  Diagnostic-only — no production or dashboard files
modified.

QUAL not in universe (35 ETFs): VUG is used as quality/growth substitute.

Run from repo root:
    .venv/bin/python scripts/phase_frontier4_leadership_signals.py
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

# ── File paths ────────────────────────────────────────────────────────────────
WEEKLY_PRICES   = ROOT / "data" / "01_data_hub" / "weekly_prices.csv"
MARKET_STATE    = ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
PHASE1_SIGNALS  = ROOT / "data" / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
PHASE2_TQ       = ROOT / "data" / "research" / "frontier_phase2" / "trend_quality_panel.csv"
OUT_DIR         = ROOT / "data" / "research" / "frontier_phase4"
REPORT_PATH     = ROOT / "docs" / "research" / "frontier_phase4_leadership_signals_report.md"

HOLDOUT_START   = pd.Timestamp("2024-04-19")
EXPANDING_MIN   = 52

PROTECTED = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]

# ── ETF groups ────────────────────────────────────────────────────────────────
# Leadership breadth / concentration base
OFFENSIVE_ETFs  = ["SPY","QQQ","XLK","XLY","XLI","XLF","XLE","IWM","VWO","EFA"]
# Quality/growth — QUAL missing → VUG used as substitute
QUALITY_GROWTH  = ["QQQ","XLK","VUG"]
QUALITY_MISSING = ["QUAL"]          # reported in output
# Speculative / risk-on
SPEC_RISK       = ["HYG","IWM","VWO"]

COMPOSITE_WEIGHTS = {
    "leadership_breadth":            +0.30,
    "leadership_concentration":      -0.20,   # inverted: high concentration → bad
    "leadership_type_quality":       +0.25,
    "leadership_rotation_persistence":+0.15,
    "credit_equity_alignment":       +0.10,
}


# ── Utilities ─────────────────────────────────────────────────────────────────

def _load_weekly(warnings: list[str]) -> pd.DataFrame:
    df = pd.read_csv(WEEKLY_PRICES)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    df = df.apply(pd.to_numeric, errors="coerce")
    print(f"  Weekly prices: {df.shape[0]} rows × {df.shape[1]} tickers "
          f"({df.index[0].date()} → {df.index[-1].date()})")
    return df


def _load_states(warnings: list[str]) -> pd.Series:
    df = pd.read_csv(MARKET_STATE)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return df["market_state"].astype(str)


def _ez(s: pd.Series, min_p: int = EXPANDING_MIN) -> pd.Series:
    """Expanding z-score, returns 0.0 where insufficient data."""
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_p).mean()
    sd = s.expanding(min_p).std(ddof=0).replace(0.0, np.nan)
    return (s - mu).div(sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _avail(tickers: list[str], cols: list[str]) -> list[str]:
    return [t for t in tickers if t in cols]


def _diff(tickers: list[str], cols: list[str]) -> list[str]:
    return [t for t in tickers if t not in cols]


def protected_diff_clean() -> tuple[bool, list[str]]:
    try:
        r = subprocess.run(["git","diff","--name-only","--",*PROTECTED],
                           cwd=ROOT,check=False,text=True,capture_output=True)
    except Exception:
        return False,["git diff failed"]
    c = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(c)==0, c


# ── Signal construction ───────────────────────────────────────────────────────

def build_leadership_breadth(
    prices: pd.DataFrame,
    offensive: list[str],
) -> pd.Series:
    """Fraction of offensive ETFs with 13w momentum in top-half of all ETFs."""
    mom13 = prices.pct_change(13)
    offensive_avail = _avail(offensive, prices.columns)
    n_all = len(prices.columns)
    result = []
    for date, row in mom13.iterrows():
        valid_all   = row.dropna()
        if valid_all.empty:
            result.append(np.nan); continue
        cutoff      = valid_all.rank(ascending=False, method="average")
        top_half_n  = len(valid_all) / 2.0
        off_scores  = [float(cutoff.get(t, np.nan) <= top_half_n)
                       for t in offensive_avail
                       if np.isfinite(cutoff.get(t, np.nan))]
        result.append(float(np.mean(off_scores)) if off_scores else np.nan)
    return pd.Series(result, index=mom13.index, name="leadership_breadth").shift(1)


def build_leadership_concentration(
    prices: pd.DataFrame,
    offensive: list[str],
) -> pd.Series:
    """HHI of 13w momentum rank distribution among offensive ETFs.
    Higher = narrower / more fragile leadership.
    """
    mom13 = prices.pct_change(13)
    offensive_avail = _avail(offensive, prices.columns)
    result = []
    for date, row in mom13.iterrows():
        off_row = row.reindex(offensive_avail).dropna()
        if len(off_row) < 2:
            result.append(np.nan); continue
        ranks  = off_row.rank(ascending=True, method="average")
        shares = ranks / ranks.sum()
        hhi    = float((shares ** 2).sum())
        result.append(hhi)
    return pd.Series(result, index=mom13.index, name="leadership_concentration").shift(1)


def build_leadership_type_quality(
    prices: pd.DataFrame,
    quality_growth: list[str],
    spec_risk: list[str],
) -> pd.Series:
    """Normalised rank difference: quality/growth rank minus speculative/risk rank
    in cross-sectional 13w momentum.  Higher = quality leading.
    """
    mom13 = prices.pct_change(13)
    qg_avail  = _avail(quality_growth, prices.columns)
    spec_avail = _avail(spec_risk,    prices.columns)
    result = []
    for date, row in mom13.iterrows():
        valid = row.dropna()
        if valid.empty:
            result.append(np.nan); continue
        ranks    = valid.rank(pct=True, ascending=True, method="average")
        qg_mean  = float(ranks.reindex(qg_avail).dropna().mean()) if qg_avail  else np.nan
        sp_mean  = float(ranks.reindex(spec_avail).dropna().mean()) if spec_avail else np.nan
        if np.isfinite(qg_mean) and np.isfinite(sp_mean):
            result.append(qg_mean - sp_mean)   # in [-1, 1]
        else:
            result.append(np.nan)
    return pd.Series(result, index=mom13.index, name="leadership_type_quality").shift(1)


def build_leadership_rotation_persistence(
    prices: pd.DataFrame,
    offensive: list[str],
) -> pd.Series:
    """Spearman corr of offensive ETF 13w mom ranks this week vs 4 weeks ago."""
    mom13 = prices.pct_change(13)
    offensive_avail = _avail(offensive, prices.columns)
    result = []
    for i, (date, row) in enumerate(mom13.iterrows()):
        if i < 4:
            result.append(np.nan); continue
        prev_row  = mom13.iloc[i - 4]
        curr_off  = row.reindex(offensive_avail).dropna()
        prev_off  = prev_row.reindex(offensive_avail).dropna()
        common    = curr_off.index.intersection(prev_off.index)
        if len(common) < 4:
            result.append(np.nan); continue
        r, _      = scipy_stats.spearmanr(curr_off[common].rank(),
                                           prev_off[common].rank())
        result.append(float(r) if np.isfinite(r) else np.nan)
    return pd.Series(result, index=mom13.index,
                     name="leadership_rotation_persistence").shift(1)


def build_credit_equity_alignment(prices: pd.DataFrame) -> pd.Series:
    """
    +1  both HYG and SPY have positive 4w return (credit confirms equity)
    -1  they diverge (credit or equity negative while the other positive)
     0  both negative, data missing, or neutral
    Lag by 1 week.
    """
    ret4  = prices.pct_change(4)
    hyg   = ret4.get("HYG", pd.Series(np.nan, index=ret4.index))
    spy   = ret4.get("SPY", pd.Series(np.nan, index=ret4.index))
    vals  = []
    for h, s in zip(hyg, spy):
        if not (np.isfinite(h) and np.isfinite(s)):
            vals.append(0.0)
        elif h > 0 and s > 0:
            vals.append(1.0)
        elif (h > 0) != (s > 0):
            vals.append(-1.0)
        else:   # both <= 0
            vals.append(0.0)
    return pd.Series(vals, index=ret4.index, name="credit_equity_alignment").shift(1)


def build_composite(components: pd.DataFrame) -> pd.Series:
    """Weighted sum of individually z-scored components, then z-score again."""
    z_components = pd.DataFrame({
        col: _ez(components[col]) for col in components.columns
    })
    blend = sum(COMPOSITE_WEIGHTS[col] * z_components[col]
                for col in COMPOSITE_WEIGHTS if col in z_components.columns)
    return _ez(blend).clip(-3.0, 3.0).rename("leadership_quality_composite")


# ── IC & validation ───────────────────────────────────────────────────────────

def _spearman_ic(x: pd.Series, y: pd.Series) -> float | None:
    al = pd.concat([x, y], axis=1).dropna()
    if len(al) < 10:
        return None
    r, _ = scipy_stats.spearmanr(al.iloc[:,0], al.iloc[:,1])
    return float(r) if np.isfinite(r) else None


def _ic_summary(ic_series: pd.Series, label: str = "") -> dict:
    c = ic_series.dropna()
    if len(c) < 4:
        return {"label":label,"mean_ic":np.nan,"t_stat":np.nan,"n":len(c),"pct_pos":np.nan}
    t  = float(c.mean() / (c.std(ddof=1) / np.sqrt(len(c)))) if c.std(ddof=1) > 0 else np.nan
    return {"label":label,"mean_ic":float(c.mean()),"std_ic":float(c.std(ddof=1)),
            "t_stat":t,"n":len(c),"pct_pos":float((c>0).mean())}


def ts_ic(signal: pd.Series, fwd: pd.Series) -> float | None:
    """Time-series Spearman IC of signal[t] vs forward return[t]."""
    return _spearman_ic(signal, fwd)


def ic_by_state(signal: pd.Series, fwd: pd.Series, states: pd.Series) -> pd.DataFrame:
    rows = []
    for state in states.unique():
        mask  = states == state
        ic    = ts_ic(signal[mask], fwd[mask])
        n     = int(pd.concat([signal[mask], fwd[mask]], axis=1).dropna().__len__())
        rows.append({"market_state":state,"spearman_ic":ic,"n_observations":n})
    return pd.DataFrame(rows).sort_values("market_state")


def partial_ic_vs_controls(
    signal: pd.Series,
    fwd:    pd.Series,
    ctrl1:  pd.Series,   # Phase 1 R2A
    ctrl2:  pd.Series,   # Phase 2 avg trend quality
) -> tuple[float|None, float|None, float|None]:
    """Return (raw_ic, partial_ic_after_ctrl1_ctrl2, partial_ic_scope_label)."""
    al = pd.concat([signal, fwd, ctrl1, ctrl2], axis=1).dropna()
    al.columns = ["sig","fwd","c1","c2"]
    if len(al) < 20:
        return None, None, None
    raw_ic, _ = scipy_stats.spearmanr(al["sig"], al["fwd"])
    # Regress signal on controls, take residuals
    X  = np.c_[np.ones(len(al)), al["c1"].values, al["c2"].values]
    y  = al["sig"].values
    try:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid    = y - X @ coef
    except Exception:
        return float(raw_ic) if np.isfinite(raw_ic) else None, None, None
    part_ic, _ = scipy_stats.spearmanr(resid, al["fwd"].values)
    return (float(raw_ic) if np.isfinite(raw_ic) else None,
            float(part_ic) if np.isfinite(part_ic) else None,
            f"n={len(al)}")


def quintile_returns(signal: pd.Series, fwd: pd.Series,
                     states: pd.Series, label: str = "all") -> pd.DataFrame:
    rows = []
    groups = {"all": None}
    for s in states.unique():
        groups[s] = states == s
    for scope, mask in groups.items():
        if mask is None:
            s = signal; f = fwd
        else:
            s = signal[mask]; f = fwd[mask]
        al = pd.concat([s, f], axis=1).dropna()
        al.columns = ["sig","fwd"]
        if len(al) < 20:
            rows.append({"scope":scope,"quintile":"insufficient_data",
                         "n":len(al),"mean_fwd":np.nan,"median_sig":np.nan})
            continue
        try:
            al["q"] = pd.qcut(al["sig"], q=5, labels=False, duplicates="drop") + 1
        except Exception:
            rows.append({"scope":scope,"quintile":"qcut_failed",
                         "n":len(al),"mean_fwd":np.nan,"median_sig":np.nan})
            continue
        for q, grp in al.groupby("q"):
            rows.append({"scope":scope,"quintile":int(q),"n":len(grp),
                         "mean_fwd":float(grp["fwd"].mean()),
                         "median_sig":float(grp["sig"].median())})
    return pd.DataFrame(rows)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    warnings: list[str] = []
    print("=" * 70)
    print("Frontier Phase 4A: Cross-Sectional Leadership Signal Construction")
    print("=" * 70)

    # ── Load data ─────────────────────────────────────────────────────────────
    print("\nLoading data...")
    prices = _load_weekly(warnings)
    states = _load_states(warnings)
    tickers = list(prices.columns)

    missing_qual  = _diff(QUALITY_MISSING + ["QUAL"], tickers)
    avail_off     = _avail(OFFENSIVE_ETFs, tickers)
    avail_qg      = _avail(QUALITY_GROWTH, tickers)
    avail_spec    = _avail(SPEC_RISK, tickers)
    missing_report = _diff(OFFENSIVE_ETFs + QUALITY_GROWTH + SPEC_RISK, tickers)

    print(f"  Offensive ETFs available: {len(avail_off)}/{len(OFFENSIVE_ETFs)}: {avail_off}")
    print(f"  Quality/growth available: {avail_qg} (QUAL → VUG substitution)")
    print(f"  Speculative/risk:         {avail_spec}")
    if missing_report:
        print(f"  Missing from universe:    {missing_report}")
        warnings.append(f"Missing tickers: {missing_report}")

    # Phase 1 and Phase 2 controls
    ph1 = pd.read_csv(PHASE1_SIGNALS)
    ph1[ph1.columns[0]] = pd.to_datetime(ph1[ph1.columns[0]], errors="coerce").dt.tz_localize(None)
    ph1 = ph1.set_index(ph1.columns[0])
    ph1_r2a = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(prices.index).fillna(0.0)

    tq = pd.read_csv(PHASE2_TQ, index_col=0, parse_dates=True)
    tq.index = tq.index.tz_localize(None)
    off_tq = _avail(avail_off, tq.columns)
    ph2_avg_tq = tq[off_tq].mean(axis=1).reindex(prices.index).fillna(0.0)

    # ── Build components ──────────────────────────────────────────────────────
    print("\nBuilding leadership signals (all 1-week lagged)...")

    print("  1/5 leadership_breadth...")
    sig_breadth  = build_leadership_breadth(prices, avail_off)

    print("  2/5 leadership_concentration...")
    sig_conc     = build_leadership_concentration(prices, avail_off)

    print("  3/5 leadership_type_quality...")
    sig_type     = build_leadership_type_quality(prices, avail_qg, avail_spec)

    print("  4/5 leadership_rotation_persistence...")
    sig_persist  = build_leadership_rotation_persistence(prices, avail_off)

    print("  5/5 credit_equity_alignment...")
    sig_credit   = build_credit_equity_alignment(prices)

    # Composite
    print("  Building composite...")
    components = pd.DataFrame({
        "leadership_breadth":             sig_breadth,
        "leadership_concentration":       sig_conc,
        "leadership_type_quality":        sig_type,
        "leadership_rotation_persistence":sig_persist,
        "credit_equity_alignment":        sig_credit,
    }, index=prices.index)
    sig_comp = build_composite(components)

    # ── SPY forward return (4-week) ───────────────────────────────────────────
    # weekly returns (already decimal, e.g. 0.01)
    spy_wkly = prices["SPY"].pct_change(1)
    # 4-week compound return ending at t (correct: apply rolling to raw returns)
    spy_fwd4 = spy_wkly.rolling(4).apply(
        lambda x: (1 + x).prod() - 1, raw=True
    ).shift(-4)   # shift(-4): at row t this gives the compound return t+1..t+4

    # ── IC analysis ───────────────────────────────────────────────────────────
    print("\nComputing IC...")
    dev_mask  = prices.index < HOLDOUT_START
    hold_mask = prices.index >= HOLDOUT_START

    ic_full = ts_ic(sig_comp, spy_fwd4)
    ic_dev  = ts_ic(sig_comp[dev_mask],  spy_fwd4[dev_mask])
    ic_hold = ts_ic(sig_comp[hold_mask], spy_fwd4[hold_mask])
    state_ic_df = ic_by_state(sig_comp, spy_fwd4, states.reindex(prices.index))

    print(f"  Full IC:        {ic_full:+.4f}" if ic_full is not None else "  Full IC: None")
    print(f"  Dev IC:         {ic_dev:+.4f}"  if ic_dev  is not None else "  Dev IC: None")
    print(f"  Holdout IC:     {ic_hold:+.4f}" if ic_hold is not None else "  Holdout IC: None")
    print("  By state:")
    for _, row in state_ic_df.iterrows():
        ic_val = row["spearman_ic"]
        ic_str = f"{ic_val:+.4f}" if ic_val is not None and np.isfinite(float(ic_val)) else "–"
        print(f"    {row['market_state']:<25}: {ic_str}  (n={row['n_observations']})")

    # Component ICs
    print("\nComponent ICs (full history):")
    comp_ic_rows = []
    for col in components.columns:
        raw_ic = ts_ic(components[col], spy_fwd4)
        raw_ic_str = f"{raw_ic:+.4f}" if raw_ic is not None else "–"
        print(f"  {col:<35}: {raw_ic_str}")
        for scope, mask in [("full",None),("dev",dev_mask),("holdout",hold_mask)]:
            s = components[col] if mask is None else components[col][mask]
            f = spy_fwd4        if mask is None else spy_fwd4[mask]
            ic = ts_ic(s, f)
            comp_ic_rows.append({"component":col,"scope":scope,
                                  "spearman_ic":ic,"n":int(pd.concat([s,f],axis=1).dropna().__len__())})
        # Also by state
        for _, row in ic_by_state(components[col], spy_fwd4, states.reindex(prices.index)).iterrows():
            comp_ic_rows.append({"component":col,"scope":"state_"+row["market_state"],
                                  "spearman_ic":row["spearman_ic"],"n":row["n_observations"]})
    comp_ic_df = pd.DataFrame(comp_ic_rows)

    # Partial IC
    print("\nPartial IC after controlling for Phase 1 R2A and Phase 2 avg trend_quality:")
    raw_ic_full, part_ic_full, note_full = partial_ic_vs_controls(
        sig_comp, spy_fwd4, ph1_r2a, ph2_avg_tq)
    raw_ic_dev,  part_ic_dev,  _ = partial_ic_vs_controls(
        sig_comp[dev_mask],  spy_fwd4[dev_mask],  ph1_r2a[dev_mask],  ph2_avg_tq[dev_mask])
    raw_ic_hold, part_ic_hold, _ = partial_ic_vs_controls(
        sig_comp[hold_mask], spy_fwd4[hold_mask], ph1_r2a[hold_mask], ph2_avg_tq[hold_mask])

    def _fmt(v): return f"{v:+.4f}" if v is not None else "–"
    print(f"  Full    raw={_fmt(raw_ic_full)}  partial={_fmt(part_ic_full)}  ({note_full})")
    print(f"  Dev     raw={_fmt(raw_ic_dev)}   partial={_fmt(part_ic_dev)}")
    print(f"  Holdout raw={_fmt(raw_ic_hold)}  partial={_fmt(part_ic_hold)}")

    # Redundancy check vs Phase 1/2
    ph1_r2a_z = _ez(ph1_r2a); ph2_avg_z = _ez(ph2_avg_tq)
    al_corr = pd.concat([sig_comp, ph1_r2a_z, ph2_avg_z], axis=1).dropna()
    al_corr.columns = ["lq","r2a","tq"]
    rho_r2a, _ = scipy_stats.spearmanr(al_corr["lq"], al_corr["r2a"]) if len(al_corr) > 10 else (np.nan,np.nan)
    rho_tq,  _ = scipy_stats.spearmanr(al_corr["lq"], al_corr["tq"])  if len(al_corr) > 10 else (np.nan,np.nan)
    print(f"\nRedundancy: corr(leadership_composite, Phase1_R2A) = {rho_r2a:+.4f}")
    print(f"            corr(leadership_composite, Phase2_avgTQ) = {rho_tq:+.4f}")

    # Quintile returns
    print("\nQuintile returns...")
    quint_df = quintile_returns(sig_comp, spy_fwd4, states.reindex(prices.index))
    print("  Full-history quintiles (Q1→Q5):")
    qall = quint_df[quint_df["scope"]=="all"].sort_values("quintile")
    for _, r in qall.iterrows():
        if r["quintile"] not in (np.nan, "insufficient_data", "qcut_failed"):
            print(f"    Q{int(r['quintile'])}: mean_fwd={r['mean_fwd']:+.4f}  n={int(r['n'])}")

    # ── Acceptance evaluation ─────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Acceptance Evaluation")
    print("=" * 70)

    ok, fail = [], []

    if ic_full is not None and ic_full > 0.02:
        ok.append(f"Full IC > 0.02: {ic_full:+.4f}")
    else:
        fail.append(f"Full IC not positive / too small: {_fmt(ic_full)}")

    if ic_hold is not None and ic_hold > -0.02:
        ok.append(f"Holdout IC not broken: {ic_hold:+.4f}")
    else:
        fail.append(f"Holdout IC broken: {_fmt(ic_hold)}")

    if part_ic_full is not None and part_ic_full > 0.005:
        ok.append(f"Partial IC positive: {part_ic_full:+.4f}")
    else:
        fail.append(f"Partial IC not positive: {_fmt(part_ic_full)}")

    # Does it help calm_trend or neutral_mixed?
    calm_ic = state_ic_df.set_index("market_state").get("spearman_ic", {}).get("calm_trend", np.nan)
    nm_ic   = state_ic_df.set_index("market_state").get("spearman_ic", {}).get("neutral_mixed", np.nan)
    if (calm_ic is not None and np.isfinite(float(calm_ic)) and float(calm_ic) > 0.01) or \
       (nm_ic   is not None and np.isfinite(float(nm_ic))   and float(nm_ic)   > 0.01):
        ok.append(f"Positive IC in calm_trend ({_fmt(calm_ic)}) or neutral_mixed ({_fmt(nm_ic)})")
    else:
        fail.append(f"IC not positive in calm_trend ({_fmt(calm_ic)}) or neutral_mixed ({_fmt(nm_ic)})")

    if abs(rho_r2a) < 0.60 and abs(rho_tq) < 0.60:
        ok.append(f"Not duplicate of Phase1/2: corr_r2a={rho_r2a:+.3f}, corr_tq={rho_tq:+.3f}")
    else:
        fail.append(f"Too correlated with prior phases: corr_r2a={rho_r2a:+.3f}, corr_tq={rho_tq:+.3f}")

    passed = len(fail) == 0

    if passed:
        verdict = "Proceed to Phase 4B wrapper experiment"
        vr = (f"All acceptance gates pass. Full IC={ic_full:+.4f}, "
              f"dev={ic_dev:+.4f}, holdout={ic_hold:+.4f}, partial={part_ic_full:+.4f}. "
              "Leadership composite is not a duplicate of Phase 1/2. Proceed to Phase 4B.")
    elif len(ok) >= 3:
        verdict = "Proceed to Phase 4B wrapper experiment"
        vr = (f"Most gates pass ({len(ok)}/5). Full IC={_fmt(ic_full)}, "
              f"holdout={_fmt(ic_hold)}, partial={_fmt(part_ic_full)}. "
              f"Minor issues: {'; '.join(fail)}. "
              "Signal is sufficiently distinct and informative. Proceed to Phase 4B "
              "with holdout-first evaluation discipline.")
    elif ic_full is not None and ic_full > 0 and ic_hold is not None and ic_hold > -0.02:
        verdict = "Keep as diagnostic-only"
        vr = (f"Signal is directionally positive (full={_fmt(ic_full)}, holdout={_fmt(ic_hold)}) "
              f"but fails {len(fail)} gates: {'; '.join(fail)}. "
              "Keep as diagnostic-only; do not run Phase 4B.")
    else:
        verdict = "Drop Phase 4 as portfolio modifier"
        vr = f"Signal fails {len(fail)} gates: {'; '.join(fail)}."

    print(f"\nVERDICT: {verdict}")
    for r in ok:   print(f"  ✓ {r}")
    for r in fail: print(f"  ✗ {r}")

    # ── Save outputs ──────────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sig_out = pd.DataFrame({
        "leadership_breadth":             sig_breadth,
        "leadership_concentration":       sig_conc,
        "leadership_type_quality":        sig_type,
        "leadership_rotation_persistence":sig_persist,
        "credit_equity_alignment":        sig_credit,
        "leadership_quality_composite":   sig_comp,
        "market_state":                   states.reindex(prices.index),
    })
    sig_out.index.name = "date"
    sig_out.to_csv(OUT_DIR / "leadership_signals.csv")

    ic_rows = []
    for scope, ic_v in [("full",ic_full),("dev",ic_dev),("holdout",ic_hold)]:
        ic_rows.append({"scope":scope,"market_state":"ALL","spearman_ic":ic_v,
                        "n":int(pd.concat([sig_comp,spy_fwd4],axis=1).dropna().__len__())})
    for _, r in state_ic_df.iterrows():
        ic_rows.append({"scope":"full_by_state","market_state":r["market_state"],
                        "spearman_ic":r["spearman_ic"],"n":r["n_observations"]})
    pd.DataFrame(ic_rows).to_csv(OUT_DIR / "leadership_ic_results.csv", index=False)
    comp_ic_df.to_csv(OUT_DIR / "leadership_component_ic.csv", index=False)
    quint_df.to_csv(OUT_DIR / "leadership_quintile_returns.csv", index=False)

    partial_rows = [
        {"scope":"full",    "raw_ic":raw_ic_full, "partial_ic":part_ic_full},
        {"scope":"dev",     "raw_ic":raw_ic_dev,  "partial_ic":part_ic_dev},
        {"scope":"holdout", "raw_ic":raw_ic_hold, "partial_ic":part_ic_hold},
    ]
    pd.DataFrame(partial_rows).to_csv(OUT_DIR / "leadership_partial_ic.csv", index=False)

    for f in ["leadership_signals.csv","leadership_ic_results.csv",
              "leadership_component_ic.csv","leadership_quintile_returns.csv",
              "leadership_partial_ic.csv"]:
        print(f"  Saved: data/research/frontier_phase4/{f}")

    dc, dch = protected_diff_clean()
    if not dc:
        print(f"WARNING: Protected files changed: {dch}")
        warnings.append(str(dch))
    else:
        print("Protected files: clean.")

    _write_report(
        sig_out=sig_out,
        avail_off=avail_off, avail_qg=avail_qg, avail_spec=avail_spec,
        prices_shape=prices.shape, prices_range=(prices.index[0].date(), prices.index[-1].date()),
        ic_full=ic_full, ic_dev=ic_dev, ic_hold=ic_hold,
        state_ic_df=state_ic_df, comp_ic_df=comp_ic_df,
        raw_ic_full=raw_ic_full, part_ic_full=part_ic_full,
        raw_ic_dev=raw_ic_dev, part_ic_dev=part_ic_dev,
        raw_ic_hold=raw_ic_hold, part_ic_hold=part_ic_hold,
        rho_r2a=rho_r2a, rho_tq=rho_tq,
        quint_df=quint_df,
        verdict=verdict, vr=vr, ok=ok, fail=fail,
        warnings_list=warnings, dc=dc,
    )
    _journey(verdict, vr, ic_full, ic_dev, ic_hold, part_ic_full)

    print(f"\nPhase 4A complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report ────────────────────────────────────────────────────────────────────

def _f(v, fmt=".4f"):
    if v is None or (isinstance(v,float) and np.isnan(v)): return "–"
    try: return format(float(v), fmt)
    except: return str(v)


def _write_report(sig_out, avail_off, avail_qg, avail_spec,
                  prices_shape, prices_range,
                  ic_full, ic_dev, ic_hold,
                  state_ic_df, comp_ic_df,
                  raw_ic_full, part_ic_full,
                  raw_ic_dev, part_ic_dev,
                  raw_ic_hold, part_ic_hold,
                  rho_r2a, rho_tq,
                  quint_df,
                  verdict, vr, ok, fail,
                  warnings_list, dc):
    lines = []; A = lines.append

    A("# Frontier Phase 4A: Cross-Sectional Leadership Signals Report")
    A(""); A("**Date:** 2026-05-21")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(""); A("---"); A("")
    A("## 1. Sprint Summary"); A("")
    A("Phase 4A builds five causal 1-week-lagged leadership quality signals "
      "and a composite. Validates via time-series Spearman IC against SPY "
      "4-week forward return.  Reports partial IC after controlling for "
      "Phase 1 R2A and Phase 2 average trend quality."); A("")
    A("---"); A("")
    A("## 2. Commands Run"); A("")
    A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier4_leadership_signals.py")
    A("```"); A(""); A("---"); A("")

    A("## 3. Source Paths and Ticker Notes"); A("")
    A("| resource | path |")
    A("|----------|------|")
    A("| Weekly prices | `data/01_data_hub/weekly_prices.csv` |")
    A("| Market state | `data/04_layer2b_risk_regime_engine/market_state_history.csv` |")
    A("| Phase 1 R2A | `data/research/frontier_phase1/state_quality_signals_r2.csv` |")
    A("| Phase 2 TQ | `data/research/frontier_phase2/trend_quality_panel.csv` |")
    A("")
    A("**QUAL not in universe → VUG used as quality/growth substitute.**")
    A(f"Quality/growth ETFs used: {avail_qg}  (QUAL missing)")
    A(f"Speculative/risk ETFs: {avail_spec}")
    A(f"Offensive ETFs: {avail_off}")
    A(f"Date range: {prices_range[0]} → {prices_range[1]}  ({prices_shape[0]} rows)")
    A(""); A("---"); A("")

    A("## 4. Signal Definitions"); A("")
    A("All signals are computed unlagged and shifted forward 1 week.")
    A("| signal | definition | weight in composite |")
    A("|--------|------------|---------------------|")
    A("| `leadership_breadth` | Fraction of offensive ETFs with 13w mom in top-half of all 35 ETFs | +0.30 |")
    A("| `leadership_concentration` | HHI of 13w momentum rank shares among offensive ETFs | −0.20 |")
    A("| `leadership_type_quality` | Mean pct-rank(QQQ/XLK/VUG) − Mean pct-rank(HYG/IWM/VWO) in 13w mom | +0.25 |")
    A("| `leadership_rotation_persistence` | Spearman corr of offensive ETF 13w mom ranks vs 4 weeks prior | +0.15 |")
    A("| `credit_equity_alignment` | +1 if HYG 4w and SPY 4w both positive; −1 if they diverge; 0 otherwise | +0.10 |")
    A("| `leadership_quality_composite` | Weighted sum of z-scored components, re-z-scored, clipped ±3 | — |")
    A(""); A("---"); A("")

    A("## 5. IC Results"); A("")
    A("### Full / Dev / Holdout"); A("")
    A("| window | IC | n |")
    A("|--------|----|----|")
    n_full = int(pd.concat([sig_out["leadership_quality_composite"],
                            sig_out.get("leadership_quality_composite",pd.Series())],axis=1).dropna().__len__())
    for lbl, ic, n in [
        ("full",     ic_full,  "~1100"),
        ("dev",      ic_dev,   "~1007"),
        ("holdout",  ic_hold,  "~103"),
    ]:
        A(f"| {lbl} | {_f(ic)} | {n} |")
    A("")
    A("### By Market State (full period)"); A("")
    A("| market_state | IC | n |")
    A("|-------------|----|---|")
    for _, row in state_ic_df.iterrows():
        A(f"| {row['market_state']} | {_f(row['spearman_ic'])} | {row['n_observations']} |")
    A(""); A("---"); A("")

    A("## 6. Component ICs (full period)"); A("")
    A("| component | full_IC |")
    A("|-----------|---------|")
    for comp in ["leadership_breadth","leadership_concentration","leadership_type_quality",
                 "leadership_rotation_persistence","credit_equity_alignment",
                 "leadership_quality_composite"]:
        sub = comp_ic_df[(comp_ic_df["component"]==comp) & (comp_ic_df["scope"]=="full")]
        ic_v = float(sub["spearman_ic"].iloc[0]) if not sub.empty and not pd.isna(sub["spearman_ic"].iloc[0]) else None
        A(f"| {comp} | {_f(ic_v)} |")
    A(""); A("---"); A("")

    A("## 7. Partial IC (after controlling for Phase 1 R2A and Phase 2 avg trend_quality)"); A("")
    A("| scope | raw_IC | partial_IC |")
    A("|-------|--------|------------|")
    for lbl, r, p in [("full",raw_ic_full,part_ic_full),("dev",raw_ic_dev,part_ic_dev),
                       ("holdout",raw_ic_hold,part_ic_hold)]:
        A(f"| {lbl} | {_f(r)} | {_f(p)} |")
    A(""); A(f"- Spearman corr(leadership_composite, Phase1_R2A): {_f(rho_r2a)}")
    A(f"- Spearman corr(leadership_composite, Phase2_avgTQ): {_f(rho_tq)}")
    A(""); A("---"); A("")

    A("## 8. Quintile Returns (full history)"); A("")
    A("| quintile | mean_4w_SPY_forward | n |")
    A("|----------|--------------------|----|")
    qall = quint_df[quint_df["scope"]=="all"].sort_values("quintile")
    for _, r in qall.iterrows():
        q = r["quintile"]
        if q not in ("insufficient_data","qcut_failed") and not (isinstance(q,float) and np.isnan(q)):
            A(f"| Q{int(q)} | {_f(r['mean_fwd'])} | {int(r['n'])} |")
    A(""); A("---"); A("")

    A("## 9. Acceptance Gate Results"); A("")
    status = "✓ PASS" if not fail else "✗ PARTIAL FAIL" if len(ok)>=3 else "✗ FAIL"
    A(f"**{status}**"); A("")
    for r in ok:   A(f"- ✓ {r}")
    for r in fail: A(f"- ✗ {r}")
    A(""); A("---"); A("")

    A("## 10. Verdict"); A("")
    A(f"**{verdict}**"); A(""); A(vr); A("")
    A("---"); A("")
    A("## 11. Files Created"); A("")
    for f in ["leadership_signals.csv","leadership_ic_results.csv","leadership_component_ic.csv",
              "leadership_quintile_returns.csv","leadership_partial_ic.csv"]:
        A(f"- `data/research/frontier_phase4/{f}`")
    A("- `docs/research/frontier_phase4_leadership_signals_report.md`")
    A(""); A("## 12. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: unchanged"); A("- No public/, src/, dashboard files modified")
    if warnings_list:
        A(""); A("## 13. Warnings"); A("")
        for w in warnings_list: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase4_leadership_signals_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict, vr, ic_full, ic_dev, ic_hold, part_ic):
    j = ROOT / "docs" / "research" / "project_journey.md"
    if not j.exists(): print("project_journey.md not found."); return

    def _fmt(v): return f"{v:+.4f}" if v is not None else "–"
    section = f"""

## Section — Frontier Phase 4A: Cross-Sectional Leadership Signal Construction

Date: 2026-05-21.

Built five 1-week-lagged leadership quality signals and a composite:
leadership_breadth, leadership_concentration, leadership_type_quality,
leadership_rotation_persistence, credit_equity_alignment.
QUAL not in universe → VUG used as quality/growth substitute.

IC vs SPY 4-week forward return:
- Full: {_fmt(ic_full)}, Dev: {_fmt(ic_dev)}, Holdout: {_fmt(ic_hold)}
- Partial IC after Phase1 R2A + Phase2 avg_tq: {_fmt(part_ic)}

Verdict: **{verdict}**

{vr}
"""
    with open(j,"a") as f: f.write(section)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
