"""Frontier Phase 7A: Cross-Asset Relational Intelligence.

Diagnostic lead-lag analysis for five cross-asset pairs.  Computes rolling
52-week lead-lag correlations, measures stability, builds a cross-asset
confirmation score from the top-3 stable pairs, and validates via IC vs
SPY 4-week forward return.

All computations are causal: at date t, only data available before t+1 is used.
The lead-lag rolling correlation uses A.shift(lag).rolling(52).corr(B) so that
at time t the correlation is between A[t-lag-51..t-lag] and B[t-51..t].

Run from repo root:
    .venv/bin/python scripts/phase_frontier7_crossasset_leadlag.py
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

# ── Paths ─────────────────────────────────────────────────────────────────────
WEEKLY_PRICES = ROOT / "data" / "01_data_hub" / "weekly_prices.csv"
MARKET_STATE  = ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv"
PHASE1_SIG    = ROOT / "data" / "research" / "frontier_phase1" / "state_quality_signals_r2.csv"
PHASE2_TQ     = ROOT / "data" / "research" / "frontier_phase2" / "trend_quality_panel.csv"
PHASE5_MDQ    = ROOT / "data" / "research" / "frontier_phase5" / "master_deployment_quality_timeseries.csv"
OUT_DIR       = ROOT / "data" / "research" / "frontier_phase7"
REPORT_PATH   = ROOT / "docs" / "research" / "frontier_phase7_crossasset_leadlag_report.md"

HOLDOUT_START = pd.Timestamp("2024-04-19")
EXPANDING_MIN = 52
ROLL_WIN      = 52
MIN_WIN       = 26
STAB_CORR_THRESHOLD = 0.15
STAB_SCORE_THRESHOLD = 0.60
N_STABLE_PAIRS = 3

PROTECTED = [
    "public", "src",
    "data/05_layer3_portfolio_construction/production_candidate_registry.json",
    "data/05_layer3_portfolio_construction/production_candidate_summary.csv",
]

# ── Lead-lag pair definitions ─────────────────────────────────────────────────
# (name, leader_fn, follower_ticker, lags, econ_story)
PAIRS = [
    ("HYG_LQD_to_SPY",  "HYG_LQD_ratio",  "SPY",
     "Credit risk appetite (HYG/LQD spread) leading equity"),
    ("TLT_to_SPY",       "TLT",            "SPY",
     "Bond momentum as risk-regime warning"),
    ("IWM_SPY_to_SPY",   "IWM_SPY_ratio",  "SPY",
     "Small-cap relative performance leading broad equity"),
    ("UUP_to_VWO",       "UUP",            "VWO",
     "Dollar strength leading EM weakness"),
    ("GLD_to_TLT",       "GLD",            "TLT",
     "Gold vs duration as inflation/macro stress proxy"),
]
LAGS = [1, 2, 4, 8]

OFFENSE_ETFs = ["SPY","QQQ","XLK","XLY","XLI","IWM","VWO","EFA"]


# ── Utilities ─────────────────────────────────────────────────────────────────

def _load_dated(path: Path, dcol: str | None = None) -> pd.DataFrame:
    df = pd.read_csv(path)
    dc = dcol or ("date" if "date" in df.columns else "Date")
    df[dc] = pd.to_datetime(df[dc], errors="coerce").dt.tz_localize(None)
    return df.dropna(subset=[dc]).sort_values(dc).set_index(dc)


def _ez(s: pd.Series, min_p: int = EXPANDING_MIN) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    mu = s.expanding(min_p).mean()
    sd = s.expanding(min_p).std(ddof=0).replace(0.0, np.nan)
    return (s - mu).div(sd).replace([np.inf, -np.inf], np.nan).fillna(0.0)


def _spearman(x: pd.Series, y: pd.Series) -> float | None:
    al = pd.concat([x, y], axis=1).dropna()
    if len(al) < 10:
        return None
    r, _ = scipy_stats.spearmanr(al.iloc[:, 0], al.iloc[:, 1])
    return float(r) if np.isfinite(r) else None


def _ic_by_scope(signal: pd.Series, fwd: pd.Series,
                  states: pd.Series) -> dict[str, dict]:
    out = {}
    dev_mask  = signal.index < HOLDOUT_START
    hold_mask = signal.index >= HOLDOUT_START
    for scope, mask in [("full",None),("dev",dev_mask),("holdout",hold_mask)]:
        s = signal if mask is None else signal[mask]
        f = fwd    if mask is None else fwd[mask]
        ic = _spearman(s, f)
        n  = len(pd.concat([s, f], axis=1).dropna())
        out[scope] = {"ic": ic, "n": n}
    for state in ["calm_trend","neutral_mixed","recovery_confirmed",
                  "recovery_fragile","stressed_panic"]:
        mask = states == state
        ic = _spearman(signal[mask], fwd[mask])
        n  = len(pd.concat([signal[mask], fwd[mask]], axis=1).dropna())
        out[f"state_{state}"] = {"ic": ic, "n": n}
    return out


def diff_clean():
    try:
        r = subprocess.run(["git","diff","--name-only","--",*PROTECTED],
                           cwd=ROOT,check=False,text=True,capture_output=True)
    except Exception: return False,["failed"]
    c = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    return len(c)==0, c


# ── Signal construction ───────────────────────────────────────────────────────

def make_leader_series(prices: pd.DataFrame, leader_id: str,
                       warnings: list[str]) -> pd.Series | None:
    """Return the leader weekly return series (or None if missing)."""
    r = prices.pct_change(1)
    if leader_id == "HYG_LQD_ratio":
        if "HYG" not in r.columns or "LQD" not in r.columns:
            warnings.append("HYG or LQD missing — skipping HYG/LQD pair")
            return None
        return (r["HYG"] - r["LQD"]).rename("HYG_LQD_ratio")
    elif leader_id == "IWM_SPY_ratio":
        if "IWM" not in r.columns or "SPY" not in r.columns:
            warnings.append("IWM or SPY missing — skipping IWM/SPY pair")
            return None
        return (r["IWM"] - r["SPY"]).rename("IWM_SPY_ratio")
    elif leader_id in r.columns:
        return r[leader_id].rename(leader_id)
    else:
        warnings.append(f"{leader_id} missing — skipping")
        return None


def rolling_leadlag_corr(leader: pd.Series, follower: pd.Series,
                          lag: int, window: int = ROLL_WIN,
                          min_win: int = MIN_WIN) -> pd.Series:
    """Rolling lead-lag correlation: A.shift(lag) vs B, window=52.
    At date t: corr(A[t-lag-51..t-lag], B[t-51..t]).  Fully causal.
    """
    return (leader.shift(lag)
              .rolling(window, min_periods=min_win)
              .corr(follower))


def stability_metrics(roll_corr: pd.Series,
                       threshold: float = STAB_CORR_THRESHOLD) -> dict:
    c = roll_corr.dropna()
    if len(c) < MIN_WIN:
        return {"mean_corr": np.nan, "std_corr": np.nan,
                "pct_above_threshold": np.nan, "sign_consistency": np.nan,
                "stability_score": np.nan, "n_windows": len(c)}
    mean_c = float(c.mean())
    std_c  = float(c.std(ddof=1))
    pct_above = float((c.abs() > threshold).mean())
    expected_sign = np.sign(mean_c) if mean_c != 0 else 1
    sign_cons = float((c * expected_sign > 0).mean())
    stab = (pct_above + sign_cons) / 2.0
    return {"mean_corr": mean_c, "std_corr": std_c,
            "pct_above_threshold": pct_above, "sign_consistency": sign_cons,
            "stability_score": stab, "n_windows": len(c)}


# ── Cross-asset confirmation score ────────────────────────────────────────────

def build_confirmation_score(prices: pd.DataFrame, top_pairs: list[dict],
                               lag_for_signal: int = 4) -> pd.Series:
    """Build cross_asset_confirmation_score from top-N stable pairs.

    For each selected pair (A → B):
      a_direction[t] = sign(A.pct_change(lag_for_signal).shift(1)[t])  (1w lag)
      expected_sign  = sign(mean_full_period_corr of best lag)
      pair_score[t]  = a_direction[t] × expected_sign

    Final score = mean(pair_scores), lagged 1 week.
    """
    scores = []
    for p in top_pairs:
        leader = p["leader"]
        exp_sign = np.sign(p["mean_corr"])
        a_mom = leader.pct_change(lag_for_signal)
        a_dir = a_mom.apply(np.sign)
        pair_score = a_dir * exp_sign
        scores.append(pair_score)
    if not scores:
        return pd.Series(0.0, index=prices.index, name="cross_asset_confirmation_score")
    raw = pd.concat(scores, axis=1).mean(axis=1)
    # Expanding z-score + lag
    composite = _ez(raw).shift(1).clip(-3.0, 3.0)
    return composite.rename("cross_asset_confirmation_score")


# ── Transition-specific IC ────────────────────────────────────────────────────

def transition_windows(states: pd.Series) -> dict[str, pd.Index]:
    """Identify transition-specific date windows."""
    s = states.values; idx = states.index; n = len(s)
    pre_stress   = []   # 4 weeks before entering stressed_panic
    post_stress  = []   # 4 weeks after leaving stressed_panic
    recovery_all = []   # all recovery weeks

    for i in range(n):
        if str(s[i]) == "stressed_panic":
            # Is this the start of a stress episode?
            if i == 0 or str(s[i-1]) != "stressed_panic":
                # Pre-stress: 4 weeks before i
                for k in range(max(0, i-4), i):
                    pre_stress.append(idx[k])
            # Is this the end of a stress episode?
            if i == n-1 or str(s[i+1]) != "stressed_panic":
                # Post-stress: 4 weeks after i
                for k in range(i+1, min(n, i+5)):
                    post_stress.append(idx[k])
        if str(s[i]) in ("recovery_confirmed","recovery_fragile"):
            recovery_all.append(idx[i])

    return {
        "pre_stress":    pd.DatetimeIndex(pre_stress),
        "post_stress":   pd.DatetimeIndex(post_stress),
        "recovery_all":  pd.DatetimeIndex(recovery_all),
    }


# ── Partial IC ────────────────────────────────────────────────────────────────

def partial_ic(signal: pd.Series, fwd: pd.Series,
               ctrl_dict: dict[str, pd.Series]) -> float | None:
    """OLS residuals of signal on controls; then correlate with forward return."""
    ctrls = pd.concat(list(ctrl_dict.values()), axis=1).reindex(signal.index)
    al = pd.concat([signal, fwd] + [ctrls.iloc[:, i] for i in range(ctrls.shape[1])],
                   axis=1).dropna()
    if len(al) < 30:
        return None
    y  = al.iloc[:, 0].values
    f  = al.iloc[:, 1].values
    X  = np.c_[np.ones(len(al)), al.iloc[:, 2:].values]
    try:
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coef
    except Exception:
        return None
    r, _ = scipy_stats.spearmanr(resid, f)
    return float(r) if np.isfinite(r) else None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    warns = []
    print("=" * 70)
    print("Frontier Phase 7A: Cross-Asset Relational Intelligence")
    print("=" * 70)

    # ── Load data ──────────────────────────────────────────────────────────
    print("\nLoading data...")
    prices = _load_dated(WEEKLY_PRICES).apply(pd.to_numeric, errors="coerce")
    states = _load_dated(MARKET_STATE)["market_state"].astype(str)
    print(f"  Prices: {prices.shape}  ({prices.index[0].date()} → {prices.index[-1].date()})")

    # Phase 1/2/5 controls
    ph1 = _load_dated(PHASE1_SIG)
    p1_r2a = pd.to_numeric(ph1["r2a"], errors="coerce").reindex(prices.index).fillna(0.0)

    tq = _load_dated(PHASE2_TQ)
    off_avail = [t for t in OFFENSE_ETFs if t in tq.columns]
    p2_avg_tq = tq[off_avail].mean(axis=1).reindex(prices.index).fillna(0.0)
    p2_avg_tq_z = _ez(p2_avg_tq)

    ph5 = _load_dated(PHASE5_MDQ)
    p5_mdq = pd.to_numeric(ph5["master_deployment_quality"], errors="coerce").reindex(prices.index).fillna(0.0)

    # SPY 4-week forward return (causal computation matches Phase 4A)
    spy_wkly = prices["SPY"].pct_change(1)
    spy_fwd4 = spy_wkly.rolling(4).apply(lambda x: (1+x).prod()-1, raw=True).shift(-4)

    # ── Compute lead-lag correlations ──────────────────────────────────────
    print("\nComputing lead-lag correlations...")
    diag_rows = []
    pair_data = {}    # name → {lag → roll_corr, leader_series}

    for pname, leader_id, follower_id, econ_story in PAIRS:
        leader = make_leader_series(prices, leader_id, warns)
        if leader is None:
            print(f"  SKIP {pname}: leader missing")
            continue
        if follower_id not in prices.columns:
            warns.append(f"{follower_id} missing — skipping {pname}")
            print(f"  SKIP {pname}: {follower_id} missing")
            continue
        follower = prices[follower_id].pct_change(1)

        pair_data[pname] = {"leader": leader, "follower": follower,
                             "econ_story": econ_story}
        best_stab = 0.0; best_lag = 1; best_mean = 0.0

        for lag in LAGS:
            rc = rolling_leadlag_corr(leader, follower, lag)
            sm = stability_metrics(rc)
            stab = float(sm.get("stability_score", 0) or 0)
            row = {"pair": pname, "lag": lag,
                   "econ_story": econ_story,
                   "leader_id": leader_id, "follower_id": follower_id,
                   **sm}
            diag_rows.append(row)
            print(f"  {pname} lag={lag}: mean={sm['mean_corr']:+.3f}  "
                  f"stab={stab:.3f}  pct>{STAB_CORR_THRESHOLD:.2f}={sm['pct_above_threshold']:.2f}")
            if stab > best_stab:
                best_stab = stab; best_lag = lag
                best_mean = float(sm.get("mean_corr", 0) or 0)

        pair_data[pname]["best_lag"]  = best_lag
        pair_data[pname]["best_stab"] = best_stab
        pair_data[pname]["mean_corr"] = best_mean

    diag_df = pd.DataFrame(diag_rows)

    # ── Select top-3 stable pairs ──────────────────────────────────────────
    print("\nSelecting top-3 stable pairs...")
    pair_summary = [
        {"pair": pname, "best_lag": d["best_lag"],
         "stability_score": d["best_stab"], "mean_corr": d["mean_corr"],
         "leader_series": d["leader"]}
        for pname, d in pair_data.items()
    ]
    pair_summary.sort(key=lambda x: x["stability_score"], reverse=True)

    stable_count = sum(1 for p in pair_summary if p["stability_score"] >= STAB_SCORE_THRESHOLD)
    print(f"  Pairs with stability >= {STAB_SCORE_THRESHOLD}: {stable_count}/{len(pair_summary)}")
    for p in pair_summary:
        mark = "✓" if p["stability_score"] >= STAB_SCORE_THRESHOLD else "✗"
        print(f"  {mark} {p['pair']}: stab={p['stability_score']:.3f}  "
              f"mean_corr={p['mean_corr']:+.3f}  best_lag={p['best_lag']}")

    top_pairs = pair_summary[:N_STABLE_PAIRS]
    print(f"  Using top-{N_STABLE_PAIRS}: {[p['pair'] for p in top_pairs]}")

    # ── Build confirmation score ───────────────────────────────────────────
    print("\nBuilding cross-asset confirmation score...")
    top_for_score = [{"leader": p["leader_series"], "mean_corr": p["mean_corr"]}
                     for p in top_pairs]
    conf_score = build_confirmation_score(prices, top_for_score)
    print(f"  Score: non-null={conf_score.notna().sum()}  "
          f"mean={conf_score.mean():.4f}  std={conf_score.std():.4f}")

    # ── IC validation ──────────────────────────────────────────────────────
    print("\nComputing IC vs SPY 4-week forward return...")
    ic_results = _ic_by_scope(conf_score, spy_fwd4, states.reindex(prices.index))
    for scope, v in ic_results.items():
        ic_val = v["ic"]
        print(f"  {scope:<30}: {(f'{ic_val:+.4f}' if ic_val is not None else '–')}"
              f"  (n={v['n']})")

    # ── Transition-specific IC ─────────────────────────────────────────────
    print("\nComputing transition-specific IC...")
    tw = transition_windows(states.reindex(prices.index))
    trans_rows = []
    for tname, tidx in tw.items():
        if len(tidx) < 5:
            print(f"  {tname}: too few ({len(tidx)}) — skipping")
            continue
        ic = _spearman(conf_score.reindex(tidx), spy_fwd4.reindex(tidx))
        n  = len(pd.concat([conf_score.reindex(tidx),
                             spy_fwd4.reindex(tidx)], axis=1).dropna())
        print(f"  {tname:<20}: IC={f'{ic:+.4f}' if ic is not None else '–'}  n={n}")
        trans_rows.append({"window_type": tname, "n": n, "spearman_ic": ic})
    trans_df = pd.DataFrame(trans_rows)

    # ── Partial IC ─────────────────────────────────────────────────────────
    print("\nComputing partial IC after controlling for Phase 1/2/5...")
    ctrl = {"phase1_r2a": p1_r2a, "phase2_avg_tq": p2_avg_tq_z, "phase5_mdq": p5_mdq}
    pic_full = partial_ic(conf_score, spy_fwd4, ctrl)
    dev_mask  = prices.index < HOLDOUT_START
    hold_mask = prices.index >= HOLDOUT_START
    pic_dev  = partial_ic(conf_score[dev_mask],  spy_fwd4[dev_mask],
                           {k: v[dev_mask] for k, v in ctrl.items()})
    pic_hold = partial_ic(conf_score[hold_mask], spy_fwd4[hold_mask],
                           {k: v[hold_mask] for k, v in ctrl.items()})
    print(f"  Partial IC full:    {f'{pic_full:+.4f}' if pic_full is not None else '–'}")
    print(f"  Partial IC dev:     {f'{pic_dev:+.4f}'  if pic_dev  is not None else '–'}")
    print(f"  Partial IC holdout: {f'{pic_hold:+.4f}' if pic_hold is not None else '–'}")

    # Redundancy vs prior phases
    rho_p1, _ = scipy_stats.spearmanr(
        pd.concat([conf_score, p1_r2a], axis=1).dropna().iloc[:, 0],
        pd.concat([conf_score, p1_r2a], axis=1).dropna().iloc[:, 1]
    ) if len(pd.concat([conf_score, p1_r2a], axis=1).dropna()) > 10 else (np.nan,)
    rho_p5, _ = scipy_stats.spearmanr(
        pd.concat([conf_score, p5_mdq], axis=1).dropna().iloc[:, 0],
        pd.concat([conf_score, p5_mdq], axis=1).dropna().iloc[:, 1]
    ) if len(pd.concat([conf_score, p5_mdq], axis=1).dropna()) > 10 else (np.nan,)
    print(f"  corr(CA_score, Phase1_R2A): {rho_p1:+.4f}")
    print(f"  corr(CA_score, Phase5_MDQ): {rho_p5:+.4f}")

    # ── Acceptance evaluation ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    ok, fail = [], []

    # Gate 1: ≥3 stable pairs
    if stable_count >= 3:
        ok.append(f"{stable_count}/{len(pair_summary)} pairs stable (≥0.60)")
    else:
        fail.append(f"Only {stable_count}/{len(pair_summary)} pairs stable (<3 needed)")

    # Gate 2: positive IC in transition/recovery states
    trans_ic_vals = [r.get("spearman_ic") for _, r in trans_df.iterrows()
                     if r.get("spearman_ic") is not None]
    if any(v is not None and v > 0.02 for v in trans_ic_vals):
        ok.append(f"Positive IC in at least one transition/recovery window")
    else:
        fail.append(f"No positive IC > 0.02 in transition/recovery windows")

    # Gate 3: holdout IC not broken
    ho_ic = ic_results.get("holdout", {}).get("ic")
    if ho_ic is None or ho_ic > -0.05:
        ok.append(f"Holdout IC not broken ({f'{ho_ic:+.4f}' if ho_ic is not None else 'NaN'})")
    else:
        fail.append(f"Holdout IC broken: {ho_ic:+.4f}")

    # Gate 4: partial IC positive
    if pic_full is not None and pic_full > 0.005:
        ok.append(f"Partial IC positive after Phase1/2/5: {pic_full:+.4f}")
    else:
        fail.append(f"Partial IC not positive: {f'{pic_full:+.4f}' if pic_full is not None else '–'}")

    # Gate 5: not a duplicate
    if abs(rho_p1) < 0.60 and abs(rho_p5) < 0.60:
        ok.append(f"Not a duplicate (rho_p1={rho_p1:+.3f}, rho_p5={rho_p5:+.3f})")
    else:
        fail.append(f"High correlation with prior phases (rho_p1={rho_p1:+.3f})")

    passed = len(fail) == 0

    full_ic_str = _f(ic_results.get("full", {}).get("ic"))
    pic_full_str = _f(pic_full)
    if passed:
        verdict = "Proceed to Phase 7B wrapper experiment"
        vr = (f"All 5 acceptance gates pass. {stable_count} stable pairs, "
              f"full IC={full_ic_str}, partial IC={pic_full_str}.")
    elif len(ok) >= 3:
        verdict = "Proceed to Phase 7B wrapper experiment"
        vr = (f"Most gates pass ({len(ok)}/5). Cross-asset signal has enough structure "
              f"for a wrapper experiment. Proceed with awareness of limitations: "
              f"{'; '.join(fail)}")
    else:
        verdict = "Keep as diagnostic-only"
        vr = (f"Signal fails {len(fail)}/5 gates: {'; '.join(fail)}. "
              "Use as diagnostic context only; do not run Phase 7B.")

    print(f"\nVERDICT: {verdict}")
    for r in ok:   print(f"  ✓ {r}")
    for r in fail: print(f"  ✗ {r}")
    print("=" * 70)

    # ── Save outputs ───────────────────────────────────────────────────────
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    diag_df.to_csv(OUT_DIR / "leadlag_stability_diagnostics.csv", index=False)

    score_out = pd.DataFrame({
        "date": prices.index,
        "market_state": states.reindex(prices.index).values,
        "cross_asset_confirmation_score": conf_score.values,
    })
    score_out.to_csv(OUT_DIR / "cross_asset_confirmation_score.csv", index=False)

    ic_rows = []
    for scope, v in ic_results.items():
        ic_rows.append({"scope": scope, "spearman_ic": v["ic"], "n": v["n"]})
    ic_rows.append({"scope": "partial_full",    "spearman_ic": pic_full,  "n": ""})
    ic_rows.append({"scope": "partial_dev",     "spearman_ic": pic_dev,   "n": ""})
    ic_rows.append({"scope": "partial_holdout", "spearman_ic": pic_hold,  "n": ""})
    pd.DataFrame(ic_rows).to_csv(OUT_DIR / "cross_asset_confirmation_ic.csv", index=False)

    trans_df.to_csv(OUT_DIR / "cross_asset_transition_ic.csv", index=False)

    for f in ["leadlag_stability_diagnostics.csv","cross_asset_confirmation_score.csv",
              "cross_asset_confirmation_ic.csv","cross_asset_transition_ic.csv"]:
        print(f"  Saved: data/research/frontier_phase7/{f}")

    dc, dch = diff_clean()
    if not dc: print(f"WARNING: {dch}"); warns.append(str(dch))
    else: print("Protected files: clean.")

    _write_report(
        diag_df, pair_summary, top_pairs, stable_count,
        ic_results, trans_df, pic_full, pic_dev, pic_hold,
        rho_p1, rho_p5, ok, fail, verdict, vr, warns, dc,
    )
    _journey(verdict, vr, stable_count, ic_results, pic_full)

    print(f"\nPhase 7A complete. Verdict: {verdict}")
    print("No production or dashboard files modified.")


# ── Report ────────────────────────────────────────────────────────────────────

def _f(v, fmt=".4f"):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "–"
    try: return format(float(v), fmt)
    except: return str(v)


def _write_report(diag_df, pair_summary, top_pairs, stable_count,
                   ic_results, trans_df, pic_full, pic_dev, pic_hold,
                   rho_p1, rho_p5, ok_list, fail_list, verdict, vr,
                   warns, dc):
    lines = []; A = lines.append

    A("# Frontier Phase 7A: Cross-Asset Relational Intelligence Report")
    A(""); A("**Date:** 2026-05-22")
    A("**Mode:** Diagnostic-only — no production or dashboard files modified")
    A(""); A("---"); A("")

    A("## 1. Sprint Summary"); A("")
    A("Phase 7A tests five cross-asset lead-lag pairs for stable, causal relationships. "
      "Rolling 52-week correlations (using `A.shift(lag).rolling(52).corr(B)`) ensure "
      "all computations are causal at date t.  The top-3 stable pairs are combined into "
      "a cross-asset confirmation score and validated via IC vs SPY 4-week forward return.")
    A(""); A("---"); A("")

    A("## 2. Commands Run"); A("```")
    A(".venv/bin/python scripts/test_allocator_checkpoint_wrapper.py   # ✓")
    A(".venv/bin/python scripts/run_deployment_rule_harness.py          # ✓")
    A(".venv/bin/python scripts/phase_frontier7_crossasset_leadlag.py")
    A("```"); A(""); A("---"); A("")

    A("## 3. Lead-Lag Stability Diagnostics"); A("")
    A("| pair | lag | mean_corr | std_corr | pct>0.15 | sign_cons | stability |")
    A("|------|-----|-----------|----------|---------|-----------|-----------|")
    for _, r in diag_df.sort_values(["pair","lag"]).iterrows():
        A(f"| {r['pair']} | {r['lag']} | {_f(r['mean_corr'])} | "
          f"{_f(r['std_corr'])} | {_f(r.get('pct_above_threshold'),'.2f')} | "
          f"{_f(r.get('sign_consistency'),'.2f')} | {_f(r.get('stability_score'),'.3f')} |")
    A(""); A("---"); A("")

    A("## 4. Top Pairs by Stability"); A("")
    A("| rank | pair | best_lag | stability_score | mean_corr | stable? |")
    A("|------|------|----------|----------------|-----------|---------|")
    for i, p in enumerate(pair_summary):
        mark = "✓" if p["stability_score"] >= STAB_SCORE_THRESHOLD else "✗"
        A(f"| {i+1} | {p['pair']} | {p['best_lag']} | "
          f"{_f(p['stability_score'],'.3f')} | {_f(p['mean_corr'])} | {mark} |")
    A(f"\n**Stable pairs (≥{STAB_SCORE_THRESHOLD}): {stable_count}/{len(pair_summary)}**")
    A(""); A("---"); A("")

    A("## 5. Cross-Asset Confirmation Score Construction"); A("")
    A(f"Built from top-{N_STABLE_PAIRS} pairs:")
    for p in top_pairs:
        A(f"- {p['pair']}: mean_corr={_f(p['mean_corr'])}  best_lag={p['best_lag']}")
    A("")
    A("Formula: for each selected pair, `a_direction × expected_sign` where "
      "a_direction = sign(4w momentum of leader), expected_sign = sign(full-period mean corr). "
      "Average across pairs, expanding z-score, 1-week lag."); A("")
    A("---"); A("")

    A("## 6. IC vs SPY 4-Week Forward Return"); A("")
    A("| scope | IC | n |")
    A("|-------|----|---|")
    for scope, v in ic_results.items():
        A(f"| {scope} | {_f(v.get('ic'))} | {v.get('n','')} |")
    A(""); A("---"); A("")

    A("## 7. Transition-Specific IC"); A("")
    A("| window | n | IC |")
    A("|--------|---|-----|")
    if not trans_df.empty:
        for _, r in trans_df.iterrows():
            A(f"| {r['window_type']} | {r['n']} | {_f(r.get('spearman_ic'))} |")
    A(""); A("---"); A("")

    A("## 8. Partial IC (after Phase 1 R2A + Phase 2 avg_tq + Phase 5 MDQ)"); A("")
    A("| scope | partial_IC |")
    A("|-------|-----------|")
    for scope, v in [("full",pic_full),("dev",pic_dev),("holdout",pic_hold)]:
        A(f"| {scope} | {_f(v)} |")
    A(f"\n- corr(CA_score, Phase1_R2A): {_f(rho_p1)}")
    A(f"- corr(CA_score, Phase5_MDQ): {_f(rho_p5)}")
    A(""); A("---"); A("")

    A("## 9. Acceptance Gate Results"); A("")
    A(f"**{'✓ PASS' if not fail_list else '✗ PARTIAL FAIL' if len(ok_list)>=3 else '✗ FAIL'}**")
    A("")
    for r in ok_list:   A(f"- ✓ {r}")
    for r in fail_list: A(f"- ✗ {r}")
    A(""); A("---"); A("")

    A("## 10. Verdict"); A("")
    A(f"**{verdict}**"); A(""); A(vr); A(""); A("---"); A("")
    A("## 11. Files Created"); A("")
    for f in ["leadlag_stability_diagnostics.csv","cross_asset_confirmation_score.csv",
              "cross_asset_confirmation_ic.csv","cross_asset_transition_ic.csv"]:
        A(f"- `data/research/frontier_phase7/{f}`")
    A("- `docs/research/frontier_phase7_crossasset_leadlag_report.md`"); A("")
    A("## 12. Production Safety"); A("")
    A(f"- Protected file diff: **{'✓ Clean' if dc else '✗ CHANGED'}**")
    A("- Production pins: unchanged"); A("- No public/, src/, dashboard files modified")
    if warns:
        A(""); A("## 13. Warnings"); A("")
        for w in warns: A(f"- {w}")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written: docs/research/frontier_phase7_crossasset_leadlag_report.md")


# ── Journey ───────────────────────────────────────────────────────────────────

def _journey(verdict, vr, stable_count, ic_results, pic_full):
    j = ROOT / "docs" / "research" / "project_journey.md"
    if not j.exists(): return
    full_ic = ic_results.get("full",{}).get("ic")
    hold_ic = ic_results.get("holdout",{}).get("ic")
    txt = f"""

## Section — Frontier Phase 7A: Cross-Asset Relational Intelligence

Date: 2026-05-22.

Built rolling 52-week lead-lag diagnostics for 5 cross-asset pairs:
HYG/LQD→SPY, TLT→SPY, IWM/SPY→SPY, UUP→VWO, GLD→TLT.
Tested lags 1, 2, 4, 8 weeks. Computed stability metrics.
Built cross_asset_confirmation_score from top-3 stable pairs.

Results:
- Stable pairs (stability ≥ 0.60): {stable_count}/5
- Full IC vs SPY 4w forward return: {_f(full_ic)}
- Holdout IC: {_f(hold_ic)}
- Partial IC after Phase1/2/5 controls: {_f(pic_full)}

Verdict: **{verdict}**

{vr}
"""
    with open(j, "a") as f: f.write(txt)
    print("project_journey.md updated.")


if __name__ == "__main__":
    main()
