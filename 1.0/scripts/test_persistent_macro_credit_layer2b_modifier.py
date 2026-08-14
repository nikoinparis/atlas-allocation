"""
Step 2B — Persistent Layer 2B Macro-Credit Regime Modifier
===========================================================
Tests whether the NM+slowdown V3 macro signal improves performance when applied as a
persistent Layer 2B modifier (offense/defense budget adjustment) rather than a weekly
ETF tilt overlay. Persistence filtering reduces the churn that killed Step 2.

Production pin: improved_frontier_phase5_fragility_guard
No production code modified.
"""

from __future__ import annotations

import json
import warnings
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "outputs" / "experiment_results" / "persistent_macro_credit_layer2b_modifier"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_HUB = ROOT / "data" / "01_data_hub"
LAYER2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3 = ROOT / "data" / "05_layer3_portfolio_construction"
V3_DIR = ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v3"
STEP2_DIR = ROOT / "outputs" / "experiment_results" / "macro_conditioned_etf_tilts"

PIN = "improved_frontier_phase5_fragility_guard"
HOLDOUT_START = pd.Timestamp("2024-04-19")
DEV_END = pd.Timestamp("2024-04-12")
COST_PER_TURNOVER = 0.001   # 10 bps per unit turnover
MAX_BIL_CAP = 0.75          # absolute BIL cap (safety floor preserve)
MIN_BIL_FLOOR = 0.00        # allow BIL to go to 0 in strongly bullish conditions
MIN_OBS_GATE = 30           # minimum active weeks for a promotion-eligible signal

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def sharpe(r: pd.Series, periods: int = 52) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5 or r.std() < 1e-12:
        return np.nan
    return float(r.mean() / r.std() * np.sqrt(periods))


def sortino(r: pd.Series, periods: int = 52) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5:
        return np.nan
    downside = r[r < 0].std()
    if downside < 1e-12:
        return np.nan
    return float(r.mean() / downside * np.sqrt(periods))


def cvar(r: pd.Series, alpha: float = 0.05) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 5:
        return np.nan
    cutoff = np.percentile(r, alpha * 100)
    tail = r[r <= cutoff]
    return float(tail.mean()) if len(tail) > 0 else np.nan


def max_drawdown(r: pd.Series) -> float:
    r = pd.Series(r, dtype=float).dropna()
    if len(r) < 2:
        return np.nan
    wealth = (1 + r).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def calmar(r: pd.Series, periods: int = 52) -> float:
    mdd = max_drawdown(r)
    if not mdd or mdd >= 0 or np.isnan(mdd):
        return np.nan
    return float(r.mean() * periods / abs(mdd))


def hit_rate(r: pd.Series) -> float:
    r = pd.Series(r, dtype=float).dropna()
    return float((r > 0).mean()) if len(r) >= 5 else np.nan


def full_metrics(r: pd.Series, to: pd.Series | None = None, label: str = "") -> dict:
    r = pd.Series(r, dtype=float)
    wealth = (1 + r.fillna(0)).cumprod()
    dd_series = wealth / wealth.cummax() - 1
    d = {
        "label": label,
        "ann_return": round(float(r.mean() * 52), 6),
        "ann_vol": round(float(r.std() * np.sqrt(52)), 6),
        "sharpe": round(sharpe(r), 6),
        "sortino": round(sortino(r), 6),
        "calmar": round(calmar(r), 6),
        "max_drawdown": round(max_drawdown(r), 6),
        "avg_drawdown": round(float(dd_series.mean()), 6),
        "cvar_5pct": round(cvar(r), 6),
        "hit_rate": round(hit_rate(r), 6),
        "n_weeks": int(r.notna().sum()),
    }
    if to is not None:
        d["avg_weekly_turnover"] = round(float(to.mean()), 6)
        d["ann_turnover"] = round(float(to.mean() * 52), 6)
        d["ann_cost_drag"] = round(float(to.mean() * COST_PER_TURNOVER * 52), 6)
    return d


# ---------------------------------------------------------------------------
# [1] Load data
# ---------------------------------------------------------------------------

def load_data() -> dict:
    print("[1] Loading data...")
    prices = pd.read_csv(DATA_HUB / "weekly_prices.csv", index_col=0, parse_dates=True)
    bl_rets = pd.read_csv(LAYER3 / f"portfolio_version_returns_{PIN}.csv", index_col=0, parse_dates=True)
    bl_wts  = pd.read_csv(LAYER3 / f"portfolio_version_weights_{PIN}.csv", index_col=0, parse_dates=True)
    msh     = pd.read_csv(LAYER2B / "market_state_history.csv", index_col=0, parse_dates=True)
    v3      = pd.read_csv(V3_DIR / "macro_states_weekly_v3.csv", index_col=0, parse_dates=True)

    # Causal confirmation features (1-week lag)
    hyg_lqd = prices["HYG"] / prices["LQD"]
    credit_improving   = (hyg_lqd.pct_change(4) > 0).shift(1)   # HYG/LQD 4w mom > 0
    credit_not_worsening = (hyg_lqd.pct_change(4) > -0.01).shift(1)  # mild negative ok
    fc_proxy  = v3["financial_conditions_proxy"].shift(1)          # already built in V3
    fc_benign = (fc_proxy < 0)                                    # conditions easing/easy
    fc_impr   = (fc_proxy.diff(1) < 0) & fc_benign               # fc improving AND benign

    etf_rets   = prices.pct_change()
    etf_rets_fwd = etf_rets.shift(-1)   # correct forward: gross[t] = w[t] @ r[t+1]

    ms  = msh["market_state"]
    mac = v3["macro_state"]

    # Identify ETF classes from baseline weights
    all_etfs = list(bl_wts.columns)
    # Offensive and defensive based on project convention
    CASH_PROXY = "BIL"
    DEFENSIVE_ETFS = [e for e in ["IEF", "SHY", "TLT", "TIP", "GLD"] if e in all_etfs]
    OFFENSIVE_ETFS = [e for e in all_etfs if e not in DEFENSIVE_ETFS + [CASH_PROXY]]

    print(f"  ETFs: {len(all_etfs)}, Offensive: {len(OFFENSIVE_ETFS)}, Defensive: {len(DEFENSIVE_ETFS)}, Cash: {CASH_PROXY}")
    print(f"  Dates: {bl_wts.index[0].date()} to {bl_wts.index[-1].date()}")
    print(f"  Baseline Sharpe: {sharpe(bl_rets['net_return']):.4f}")

    return {
        "prices": prices,
        "etf_rets": etf_rets,
        "etf_rets_fwd": etf_rets_fwd,
        "bl_rets": bl_rets,
        "bl_wts": bl_wts,
        "ms": ms,
        "mac": mac,
        "v3": v3,
        "credit_improving": credit_improving,
        "credit_not_worsening": credit_not_worsening,
        "fc_benign": fc_benign,
        "fc_impr": fc_impr,
        "all_etfs": all_etfs,
        "CASH_PROXY": CASH_PROXY,
        "DEFENSIVE_ETFS": DEFENSIVE_ETFS,
        "OFFENSIVE_ETFS": OFFENSIVE_ETFS,
    }


# ---------------------------------------------------------------------------
# [2] Raw signal variants
# ---------------------------------------------------------------------------

def build_raw_signals(data: dict) -> dict:
    ms  = data["ms"]
    mac = data["mac"]
    cr  = data["credit_improving"]
    crn = data["credit_not_worsening"]
    fcb = data["fc_benign"]
    fci = data["fc_impr"]

    nm = ms == "neutral_mixed"
    slow = mac == "slowdown"

    signals = {
        "A_nm_slow":         nm & slow,
        "B_nm_slow_credit":  nm & slow & cr,
        "C_nm_slow_crnotworse": nm & slow & crn,
        "D_nm_slow_fc":      nm & slow & fcb,
        "E_nm_slow_credit_fc": nm & slow & cr & fcb,
    }
    return {k: v.fillna(False) for k, v in signals.items()}


# ---------------------------------------------------------------------------
# [3] Persistence filter
# ---------------------------------------------------------------------------

def apply_persistence_filter(
    raw_signal: pd.Series,
    activate_after: int = 3,
    deactivate_after: int = 2,
    min_hold: int = 4,
) -> pd.Series:
    """
    Returns filtered signal series (bool).
    Activates after `activate_after` consecutive True weeks.
    Deactivates after `deactivate_after` consecutive False weeks,
    but not before `min_hold` weeks have elapsed since activation.
    """
    sig = raw_signal.astype(int).values
    n = len(sig)
    active = np.zeros(n, dtype=bool)
    consec_on = 0
    consec_off = 0
    is_active = False
    hold_counter = 0

    for i in range(n):
        if sig[i] == 1:
            consec_on += 1
            consec_off = 0
        else:
            consec_off += 1
            consec_on = 0

        if not is_active:
            if consec_on >= activate_after:
                is_active = True
                hold_counter = 0
        else:
            hold_counter += 1
            if hold_counter >= min_hold and consec_off >= deactivate_after:
                is_active = False
                consec_on = 0

        active[i] = is_active

    return pd.Series(active, index=raw_signal.index)


def episode_stats(signal: pd.Series) -> dict:
    """Compute episode statistics for a binary signal series."""
    s = signal.astype(int)
    episodes = []
    in_ep = False
    ep_start = None

    for i, (date, val) in enumerate(s.items()):
        if val and not in_ep:
            in_ep = True
            ep_start = i
        elif not val and in_ep:
            in_ep = False
            episodes.append(i - ep_start)
    if in_ep:
        episodes.append(len(s) - ep_start)

    return {
        "n_active": int(s.sum()),
        "pct_active": round(float(s.mean()), 4),
        "n_episodes": len(episodes),
        "avg_ep_len": round(float(np.mean(episodes)), 2) if episodes else 0,
        "med_ep_len": round(float(np.median(episodes)), 1) if episodes else 0,
        "min_ep_len": int(min(episodes)) if episodes else 0,
        "max_ep_len": int(max(episodes)) if episodes else 0,
        "n_transitions": int((s.diff().abs().sum()) / 2),
    }


# ---------------------------------------------------------------------------
# [4] Layer 2B modifier implementations
# ---------------------------------------------------------------------------

OFFENSIVES_FOR_BOOST = ["SPY", "QQQ", "IWM", "EFA", "VWO", "VEA", "VNQ", "HYG"]
DEFENSIVES_FOR_DRAIN = ["BIL", "IEF", "TLT", "SHY"]


def modifier_offense_budget(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    """
    Increase offense budget by `intensity`: drain proportionally from defensive+cash,
    add proportionally to offensive ETFs already present.
    """
    w = w.copy()
    drain_pool = [e for e in DEFENSIVES_FOR_DRAIN if e in all_etfs and w.get(e, 0) > 0.005]
    add_pool = [e for e in OFFENSIVES_FOR_BOOST if e in all_etfs and w.get(e, 0) > 0.001]
    if not drain_pool or not add_pool:
        return w
    total_drain = w[drain_pool].sum()
    shift = min(intensity, total_drain * 0.9)
    if shift <= 0:
        return w
    drain_weights = w[drain_pool]
    for e in drain_pool:
        w[e] -= shift * (drain_weights[e] / drain_weights.sum())
    add_weights = w[add_pool]
    for e in add_pool:
        w[e] += shift * (add_weights[e] / add_weights.sum()) if add_weights.sum() > 0 else shift / len(add_pool)
    return w


def modifier_defense_release(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    """
    Release BIL/cash by `intensity`, redistribute proportionally to all non-BIL ETFs.
    """
    w = w.copy()
    if "BIL" not in all_etfs:
        return w
    bil_current = w.get("BIL", 0)
    release = min(intensity, max(0, bil_current - 0.02))  # keep ≥2% BIL floor
    if release <= 0:
        return w
    w["BIL"] -= release
    non_bil = [e for e in all_etfs if e != "BIL" and w.get(e, 0) > 0]
    if not non_bil:
        return w
    non_bil_total = w[non_bil].sum()
    for e in non_bil:
        w[e] += release * (w[e] / non_bil_total)
    return w


def modifier_risk_multiplier(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    """
    Scale offensive ETF weights by (1+intensity), fund from BIL.
    """
    w = w.copy()
    off_pool = [e for e in OFFENSIVES_FOR_BOOST if e in all_etfs and w.get(e, 0) > 0.001]
    if not off_pool:
        return w
    total_off = w[off_pool].sum()
    extra = total_off * intensity
    bil_current = w.get("BIL", 0)
    actual_extra = min(extra, max(0, bil_current - 0.02))
    if actual_extra <= 0:
        return w
    w["BIL"] = bil_current - actual_extra
    scale = 1 + actual_extra / total_off
    for e in off_pool:
        w[e] *= scale
    return w


def modifier_combined_conservative(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    """
    Combined: small offense boost + small defense release.
    Intensity split: 60% offense boost, 40% defense release.
    """
    w = modifier_offense_budget(w, intensity * 0.6, all_etfs)
    w = modifier_defense_release(w, intensity * 0.4, all_etfs)
    return w


MODIFIER_FUNCTIONS = {
    "offense_budget":  modifier_offense_budget,
    "defense_release": modifier_defense_release,
    "risk_multiplier": modifier_risk_multiplier,
    "combined":        modifier_combined_conservative,
}


def apply_modifier_to_weights(
    baseline_wts: pd.DataFrame,
    active_signal: pd.Series,
    modifier_fn: callable,
    intensity: float,
    all_etfs: list,
) -> pd.DataFrame:
    """Apply a modifier function to baseline weights when active_signal is True."""
    modified = baseline_wts.copy()
    for date in baseline_wts.index:
        if not active_signal.get(date, False):
            continue
        w = baseline_wts.loc[date].copy()
        w = modifier_fn(w, intensity, all_etfs)
        # Enforce long-only and normalize
        w = w.clip(lower=0)
        total = w.sum()
        if total > 1e-6:
            w = w / total
        modified.loc[date] = w
    return modified


# ---------------------------------------------------------------------------
# [5] Portfolio return computation (correct convention)
# ---------------------------------------------------------------------------

def compute_returns(weights: pd.DataFrame, etf_rets: pd.DataFrame) -> pd.DataFrame:
    """
    Convention: gross[t] = w[t] @ etf_rets[t+1]  (weights set at t, earn returns t→t+1)
    Turnover[t] = half-round-trip from drifted w[t-1] to w[t]
    """
    etf_rets_fwd = etf_rets.shift(-1)
    dates = weights.index
    gross, turnover, cost = [], [], []
    w_prev = None

    for date in dates:
        w = weights.loc[date].fillna(0).values
        r_fwd = etf_rets_fwd.loc[date].reindex(weights.columns).fillna(0).values
        gross.append(float(np.dot(w, r_fwd)))

        if w_prev is None:
            to = 0.0
        else:
            r_cur = etf_rets.loc[date].reindex(weights.columns).fillna(0).values
            drift = w_prev * (1 + r_cur)
            ds = drift.sum()
            if ds > 1e-8:
                drift /= ds
            to = float(np.sum(np.abs(w - drift)) / 2)
        turnover.append(to)
        cost.append(to * COST_PER_TURNOVER)
        w_prev = w.copy()

    out = pd.DataFrame({
        "gross_return": gross,
        "net_return": [g - c for g, c in zip(gross, cost)],
        "turnover": turnover,
        "cost": cost,
    }, index=dates)
    out["wealth"] = (1 + out["net_return"]).cumprod()
    out["drawdown"] = out["wealth"] / out["wealth"].cummax() - 1
    return out


# ---------------------------------------------------------------------------
# [6] Signal persistence diagnostics
# ---------------------------------------------------------------------------

def build_persistence_diagnostics(raw_signals: dict, data: dict) -> pd.DataFrame:
    print("\n[3] Signal persistence diagnostics...")
    rows = []
    # Check overlap with Step 2 weekly tilt signals
    ms = data["ms"]
    mac = data["mac"]

    for sig_name, raw_sig in raw_signals.items():
        raw_stats = episode_stats(raw_sig)
        raw_stats["signal"] = sig_name
        raw_stats["filter"] = "raw"
        raw_stats["activate_after"] = 1
        raw_stats["deactivate_after"] = 1
        raw_stats["min_hold"] = 0
        raw_stats["dev_n_active"] = int(raw_sig[raw_sig.index <= DEV_END].sum())
        raw_stats["hold_n_active"] = int(raw_sig[raw_sig.index >= HOLDOUT_START].sum())
        rows.append(raw_stats)

        for act, deact, hold in product([2, 3, 4], [2, 3], [2, 4, 6]):
            filt = apply_persistence_filter(raw_sig, act, deact, hold)
            stats = episode_stats(filt)
            stats["signal"] = sig_name
            stats["filter"] = f"act{act}_deact{deact}_hold{hold}"
            stats["activate_after"] = act
            stats["deactivate_after"] = deact
            stats["min_hold"] = hold
            stats["dev_n_active"] = int(filt[filt.index <= DEV_END].sum())
            stats["hold_n_active"] = int(filt[filt.index >= HOLDOUT_START].sum())
            # Turnover reduction vs raw
            raw_to = raw_stats["n_transitions"]
            stats["turnover_reduction_pct"] = round(1 - stats["n_transitions"] / raw_to, 3) if raw_to > 0 else 0
            rows.append(stats)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "signal_persistence_diagnostics.csv", index=False)
    print(f"  Saved: signal_persistence_diagnostics.csv ({len(df)} rows)")

    # Print summary of raw signals
    for s in raw_signals:
        r = raw_signals[s]
        st = episode_stats(r)
        print(f"  {s}: n_active={st['n_active']} ({st['pct_active']:.1%}), "
              f"episodes={st['n_episodes']}, avg_len={st['avg_ep_len']:.1f}wk, "
              f"dev={r[r.index<=DEV_END].sum()}, hold={r[r.index>=HOLDOUT_START].sum()}")
    return df


# ---------------------------------------------------------------------------
# [7] Main candidate evaluation
# ---------------------------------------------------------------------------

def evaluate_candidates(data: dict, raw_signals: dict) -> tuple:
    print("\n[4/5] Building and evaluating candidates...")

    bl_wts  = data["bl_wts"]
    bl_rets = data["bl_rets"]
    etf_rets = data["etf_rets"]
    ms = data["ms"]
    mac = data["mac"]
    all_etfs = data["all_etfs"]

    bl_r = bl_rets["net_return"]
    bl_to = bl_rets["turnover"]

    HOLDOUT_START_TS = HOLDOUT_START
    DEV_END_TS = DEV_END

    # Baseline metrics
    bl_full = full_metrics(bl_r, bl_to, "BASELINE")
    bl_hold = full_metrics(bl_r[bl_r.index >= HOLDOUT_START_TS], bl_to[bl_to.index >= HOLDOUT_START_TS], "BASELINE_holdout")
    bl_dev  = full_metrics(bl_r[bl_r.index <= DEV_END_TS], bl_to[bl_to.index <= DEV_END_TS], "BASELINE_dev")

    nm_slow_mask = (ms == "neutral_mixed") & (mac == "slowdown")
    bl_nm_slow_sharpe = sharpe(bl_r[nm_slow_mask & (bl_r.index <= DEV_END_TS)])
    bl_nm_sharpe = sharpe(bl_r[(ms == "neutral_mixed") & (bl_r.index <= DEV_END_TS)])

    print(f"  Baseline: Sharpe={bl_full['sharpe']:.4f}, AnnRet={bl_full['ann_return']:.4%}")
    print(f"  Baseline NM dev Sharpe: {bl_nm_sharpe:.4f}, NM+slow dev Sharpe: {bl_nm_slow_sharpe:.4f}")
    print(f"  Baseline holdout Sharpe: {bl_hold['sharpe']:.4f}")

    # --- COARSE GRID ---
    # Stage 1: quick evaluation across all combinations, rank by NM+slow dev Sharpe
    coarse_candidates = []
    intensities = [0.025, 0.05, 0.075, 0.10]
    filter_combos = [(2, 2, 2), (2, 2, 4), (3, 2, 4), (3, 3, 4), (4, 2, 4), (4, 3, 4), (4, 3, 6)]
    mod_types = list(MODIFIER_FUNCTIONS.keys())

    total = len(raw_signals) * len(filter_combos) * len(mod_types) * len(intensities)
    print(f"\n  Coarse grid: {total} candidates")

    processed = 0
    for sig_name, raw_sig in raw_signals.items():
        for act, deact, hold in filter_combos:
            filt_sig = apply_persistence_filter(raw_sig, act, deact, hold)
            ep_st = episode_stats(filt_sig)
            n_dev_active = int(filt_sig[filt_sig.index <= DEV_END_TS].sum())
            if n_dev_active < 15:
                processed += len(mod_types) * len(intensities)
                continue

            for mod_name, mod_fn in MODIFIER_FUNCTIONS.items():
                for intensity in intensities:
                    name = f"{sig_name}|act{act}_deact{deact}_hold{hold}|{mod_name}|int{int(intensity*100)}pct"
                    try:
                        mod_wts = apply_modifier_to_weights(bl_wts, filt_sig, mod_fn, intensity, all_etfs)
                        mod_rets = compute_returns(mod_wts, etf_rets)
                        r = mod_rets["net_return"]
                        to = mod_rets["turnover"]

                        nm_slow_dev_sharpe = sharpe(r[nm_slow_mask & (r.index <= DEV_END_TS)])
                        full_sharpe_val = sharpe(r)
                        to_increase = float((to.mean() - bl_to.mean()) * 52)

                        coarse_candidates.append({
                            "name": name,
                            "signal": sig_name,
                            "activate_after": act,
                            "deactivate_after": deact,
                            "min_hold": hold,
                            "modifier": mod_name,
                            "intensity": intensity,
                            "n_dev_active": n_dev_active,
                            "n_episodes": ep_st["n_episodes"],
                            "avg_ep_len": ep_st["avg_ep_len"],
                            "full_sharpe": round(full_sharpe_val, 6),
                            "sharpe_delta": round(full_sharpe_val - bl_full["sharpe"], 6),
                            "nm_slow_dev_sharpe": round(nm_slow_dev_sharpe, 6) if not np.isnan(nm_slow_dev_sharpe) else None,
                            "ann_return": round(float(r.mean() * 52), 6),
                            "max_drawdown": round(max_drawdown(r), 6),
                            "turnover_increase_ann": round(to_increase, 6),
                        })
                    except Exception as e:
                        pass
                    processed += 1
            if processed % 100 == 0:
                print(f"    Processed {processed}/{total}...")

    print(f"  Coarse grid complete: {len(coarse_candidates)} candidates evaluated")

    # Stage 2: Select top 10 by NM+slow dev Sharpe, then full metrics
    df_coarse = pd.DataFrame(coarse_candidates)
    if df_coarse.empty:
        print("  ERROR: No candidates produced")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Filter: must have n_dev_active >= MIN_OBS_GATE
    df_coarse = df_coarse[df_coarse["n_dev_active"] >= MIN_OBS_GATE]

    # Rank by NM+slow dev Sharpe descending, then full Sharpe
    df_coarse = df_coarse.sort_values(
        ["nm_slow_dev_sharpe", "sharpe_delta"], ascending=[False, False]
    ).reset_index(drop=True)

    top10_names = list(df_coarse["name"].head(10))
    print(f"\n  Top 10 by NM+slow Sharpe selected for full evaluation:")
    for nm in top10_names:
        row = df_coarse[df_coarse["name"] == nm].iloc[0]
        print(f"    {nm}: NM_slow_Sharpe={row['nm_slow_dev_sharpe']:.3f}, Sharpe_delta={row['sharpe_delta']:+.4f}")

    # Stage 3: Full metrics on top 10
    metrics_full = []
    metrics_state = []
    metrics_holdout = []
    metrics_turnover = []

    # Baseline rows
    bl_base_row = {**bl_full, "variant": "BASELINE", "signal": "none", "modifier": "none", "intensity": 0, "n_dev_active": 0, "n_episodes": 0}
    bl_base_row["sharpe_delta_vs_baseline"] = 0.0
    bl_base_row["return_delta_vs_baseline"] = 0.0
    bl_base_row["dd_delta_vs_baseline"] = 0.0
    metrics_full.append(bl_base_row)

    for state in ["neutral_mixed", "calm_trend", "stressed_panic", "recovery_fragile", "recovery_confirmed"]:
        mask = ms == state
        bl_r_s = bl_r[(mask) & (bl_r.index <= DEV_END_TS)]
        bl_to_s = bl_to[(mask) & (bl_to.index <= DEV_END_TS)]
        row = full_metrics(bl_r_s, bl_to_s, state)
        row["variant"] = "BASELINE"
        row["state"] = state
        row["period"] = "dev"
        metrics_state.append(row)

    bl_hold_row = {**bl_hold, "variant": "BASELINE"}
    metrics_holdout.append(bl_hold_row)

    for cand_name in top10_names:
        coarse_row = df_coarse[df_coarse["name"] == cand_name].iloc[0]
        sig_name = coarse_row["signal"]
        act = coarse_row["activate_after"]
        deact = coarse_row["deactivate_after"]
        hold = coarse_row["min_hold"]
        mod_name = coarse_row["modifier"]
        intensity = coarse_row["intensity"]

        raw_sig = raw_signals[sig_name]
        filt_sig = apply_persistence_filter(raw_sig, act, deact, hold)
        mod_fn = MODIFIER_FUNCTIONS[mod_name]
        mod_wts = apply_modifier_to_weights(bl_wts, filt_sig, mod_fn, intensity, all_etfs)
        mod_rets = compute_returns(mod_wts, etf_rets)
        r = mod_rets["net_return"]
        to = mod_rets["turnover"]

        # Full period
        m = full_metrics(r, to, cand_name)
        m["variant"] = cand_name
        m["signal"] = sig_name
        m["modifier"] = mod_name
        m["intensity"] = intensity
        m["n_dev_active"] = int(filt_sig[filt_sig.index <= DEV_END_TS].sum())
        m["n_episodes"] = episode_stats(filt_sig)["n_episodes"]
        m["avg_ep_len"] = episode_stats(filt_sig)["avg_ep_len"]
        m["sharpe_delta_vs_baseline"] = round(m["sharpe"] - bl_full["sharpe"], 6)
        m["return_delta_vs_baseline"] = round(m["ann_return"] - bl_full["ann_return"], 6)
        m["dd_delta_vs_baseline"] = round(m["max_drawdown"] - bl_full["max_drawdown"], 6)
        metrics_full.append(m)

        # Holdout
        r_hold = r[r.index >= HOLDOUT_START_TS]
        to_hold = to[to.index >= HOLDOUT_START_TS]
        mh = full_metrics(r_hold, to_hold, f"{cand_name}_holdout")
        mh["variant"] = cand_name
        mh["holdout_sharpe_delta"] = round(mh["sharpe"] - bl_hold["sharpe"], 6)
        metrics_holdout.append(mh)

        # State metrics dev
        for state in ["neutral_mixed", "neutral_mixed+slowdown", "calm_trend",
                       "stressed_panic", "recovery_fragile", "recovery_confirmed"]:
            if "+" in state:
                parts = state.split("+")
                mask = (ms == parts[0]) & (mac == parts[1])
            else:
                mask = ms == state
            bl_r_s = bl_r[(mask) & (bl_r.index <= DEV_END_TS)]
            mod_r_s = r[(mask) & (r.index <= DEV_END_TS)]
            mod_to_s = to[(mask) & (to.index <= DEV_END_TS)]
            sm = full_metrics(mod_r_s, mod_to_s, state)
            sm["variant"] = cand_name
            sm["state"] = state
            sm["period"] = "dev"
            sm["bl_sharpe"] = round(sharpe(bl_r_s), 4)
            sm["sharpe_delta"] = round(sm["sharpe"] - sm["bl_sharpe"], 4) if not np.isnan(sm["sharpe"]) else None
            metrics_state.append(sm)

        # State metrics holdout
        for state in ["neutral_mixed", "neutral_mixed+slowdown"]:
            if "+" in state:
                parts = state.split("+")
                mask = (ms == parts[0]) & (mac == parts[1])
            else:
                mask = ms == state
            mod_r_h = r[(mask) & (r.index >= HOLDOUT_START_TS)]
            mod_to_h = to[(mask) & (to.index >= HOLDOUT_START_TS)]
            sh = full_metrics(mod_r_h, mod_to_h, state)
            sh["variant"] = cand_name
            sh["state"] = state
            sh["period"] = "holdout"
            sh["bl_sharpe"] = round(sharpe(bl_r[(mask) & (bl_r.index >= HOLDOUT_START_TS)]), 4)
            sh["sharpe_delta"] = round(sh["sharpe"] - sh["bl_sharpe"], 4) if not np.isnan(sh["sharpe"]) else None
            metrics_state.append(sh)

        # Turnover
        metrics_turnover.append({
            "variant": cand_name,
            "signal": sig_name,
            "modifier": mod_name,
            "intensity": intensity,
            "avg_weekly_turnover": round(float(to.mean()), 6),
            "ann_turnover": round(float(to.mean() * 52), 6),
            "baseline_ann_turnover": round(float(bl_to.mean() * 52), 6),
            "turnover_increase_ann": round(float((to.mean() - bl_to.mean()) * 52), 6),
            "ann_cost_drag": round(float(to.mean() * COST_PER_TURNOVER * 52), 6),
        })

        delta = m["sharpe_delta_vs_baseline"]
        nm_s = sharpe(r[(nm_slow_mask) & (r.index <= DEV_END_TS)])
        status = "✓" if delta > 0 else "✗"
        print(f"  {status} {cand_name}: Sharpe={m['sharpe']:.4f} (Δ={delta:+.4f}), NM+slow_Sharpe={nm_s:.3f}")

    return pd.DataFrame(metrics_full), pd.DataFrame(metrics_state), pd.DataFrame(metrics_holdout), pd.DataFrame(metrics_turnover), df_coarse


# ---------------------------------------------------------------------------
# [7] Gates
# ---------------------------------------------------------------------------

def apply_gates(df_full: pd.DataFrame, df_hold: pd.DataFrame, df_state: pd.DataFrame,
                df_turn: pd.DataFrame) -> pd.DataFrame:
    print("\n[6] Applying promotion gates...")

    bl_full = df_full[df_full["variant"] == "BASELINE"].iloc[0]
    bl_hold = df_hold[df_hold["variant"] == "BASELINE"].iloc[0] if "BASELINE" in df_hold["variant"].values else {}

    results = []
    candidates = df_full[df_full["variant"] != "BASELINE"]

    for _, row in candidates.iterrows():
        variant = row["variant"]

        hold_row = df_hold[df_hold["variant"] == variant]
        h_sharpe = hold_row["sharpe"].iloc[0] if not hold_row.empty else np.nan

        # NM dev
        nm_dev = df_state[(df_state["variant"] == variant) & (df_state["state"] == "neutral_mixed") & (df_state["period"] == "dev")]
        nm_sharpe = nm_dev["sharpe"].iloc[0] if not nm_dev.empty else np.nan
        bl_nm_dev = df_state[(df_state["variant"] == "BASELINE") & (df_state["state"] == "neutral_mixed") & (df_state["period"] == "dev")]
        bl_nm_sharpe = bl_nm_dev["sharpe"].iloc[0] if not bl_nm_dev.empty else np.nan

        # NM+slowdown dev
        nm_sl_dev = df_state[(df_state["variant"] == variant) & (df_state["state"] == "neutral_mixed+slowdown") & (df_state["period"] == "dev")]
        nm_sl_sharpe = nm_sl_dev["sharpe"].iloc[0] if not nm_sl_dev.empty else np.nan
        bl_nm_sl_dev = df_state[(df_state["variant"] == "BASELINE") & (df_state["state"] == "neutral_mixed+slowdown") & (df_state["period"] == "dev")]
        bl_nm_sl_sharpe = bl_nm_sl_dev["sharpe"].iloc[0] if not bl_nm_sl_dev.empty else np.nan

        # stressed_panic
        sp_dev = df_state[(df_state["variant"] == variant) & (df_state["state"] == "stressed_panic") & (df_state["period"] == "dev")]
        sp_sharpe = sp_dev["sharpe"].iloc[0] if not sp_dev.empty else np.nan
        bl_sp = df_state[(df_state["variant"] == "BASELINE") & (df_state["state"] == "stressed_panic") & (df_state["period"] == "dev")]
        bl_sp_sharpe = bl_sp["sharpe"].iloc[0] if not bl_sp.empty else np.nan

        # recovery_fragile
        rf_dev = df_state[(df_state["variant"] == variant) & (df_state["state"] == "recovery_fragile") & (df_state["period"] == "dev")]
        rf_sharpe = rf_dev["sharpe"].iloc[0] if not rf_dev.empty else np.nan
        bl_rf = df_state[(df_state["variant"] == "BASELINE") & (df_state["state"] == "recovery_fragile") & (df_state["period"] == "dev")]
        bl_rf_sharpe = bl_rf["sharpe"].iloc[0] if not bl_rf.empty else np.nan

        # Turnover
        turn_row = df_turn[df_turn["variant"] == variant]
        to_increase = turn_row["turnover_increase_ann"].iloc[0] if not turn_row.empty else np.nan

        # Gates
        g1 = (row["sharpe"] - bl_full["sharpe"]) >= 0.01
        g2 = (h_sharpe >= bl_full["sharpe"] - 0.02) if not np.isnan(h_sharpe) else False
        g3 = row["ann_return"] >= bl_full["ann_return"] - 0.002
        g4 = (row["max_drawdown"] - bl_full["max_drawdown"]) <= 0.01
        g5 = (row.get("cvar_5pct", 0) - bl_full.get("cvar_5pct", 0)) >= -0.005
        g6 = float(to_increase) <= 0.03 if not np.isnan(float(to_increase)) else False
        g7_nm = (nm_sharpe > bl_nm_sharpe - 0.01) if not (np.isnan(nm_sharpe) or np.isnan(bl_nm_sharpe)) else False
        g7_nmsl = (nm_sl_sharpe >= bl_nm_sl_sharpe - 0.05) if not (np.isnan(nm_sl_sharpe) or np.isnan(bl_nm_sl_sharpe)) else False
        g7 = g7_nm or g7_nmsl
        g8 = (sp_sharpe - bl_sp_sharpe >= -0.02) if not (np.isnan(sp_sharpe) or np.isnan(bl_sp_sharpe)) else False
        g9 = (rf_sharpe - bl_rf_sharpe >= -0.05) if not (np.isnan(rf_sharpe) or np.isnan(bl_rf_sharpe)) else True
        g10 = row.get("n_dev_active", 0) >= MIN_OBS_GATE

        gates_passed = sum([g1, g2, g3, g4, g5, g6, g7, g8, g9, g10])
        all_gates = all([g1, g2, g3, g4, g5, g6, g7, g8, g9, g10])

        if all_gates:
            verdict = "PROMOTE_TO_PHASE_D_TEST"
        elif g7 and gates_passed >= 7:
            verdict = "RESEARCH-ONLY"
        elif g7 and gates_passed >= 5:
            verdict = "RESEARCH-ONLY"
        else:
            verdict = "DROP"

        results.append({
            "variant": variant,
            "signal": row.get("signal", ""),
            "modifier": row.get("modifier", ""),
            "intensity": row.get("intensity", 0),
            "full_sharpe": round(row["sharpe"], 4),
            "sharpe_delta": round(row["sharpe"] - bl_full["sharpe"], 4),
            "ann_return": round(row["ann_return"], 4),
            "max_drawdown": round(row["max_drawdown"], 4),
            "holdout_sharpe": round(h_sharpe, 4) if not np.isnan(h_sharpe) else None,
            "nm_dev_sharpe": round(nm_sharpe, 4) if not np.isnan(nm_sharpe) else None,
            "nm_slow_dev_sharpe": round(nm_sl_sharpe, 4) if not np.isnan(nm_sl_sharpe) else None,
            "n_dev_active": row.get("n_dev_active", 0),
            "turnover_increase_ann": round(float(to_increase), 4) if not np.isnan(float(to_increase)) else None,
            "g1_sharpe_001": g1,
            "g2_holdout_ok": g2,
            "g3_return_ok": g3,
            "g4_dd_ok": g4,
            "g5_cvar_ok": g5,
            "g6_turnover_ok": g6,
            "g7_nm_improved": g7,
            "g8_sp_ok": g8,
            "g9_rf_ok": g9,
            "g10_obs_ok": g10,
            "gates_passed": gates_passed,
            "verdict": verdict,
        })

    df_results = pd.DataFrame(results).sort_values("sharpe_delta", ascending=False)
    return df_results


# ---------------------------------------------------------------------------
# [8] Robustness
# ---------------------------------------------------------------------------

def robustness_checks(data: dict, top3_names: list, df_full_all: pd.DataFrame,
                      raw_signals: dict, gates_df: pd.DataFrame) -> tuple:
    print(f"\n[7] Robustness checks for top {len(top3_names)} candidates...")

    bl_wts  = data["bl_wts"]
    bl_rets = data["bl_rets"]
    etf_rets = data["etf_rets"]
    all_etfs = data["all_etfs"]
    bl_r = bl_rets["net_return"]

    rows = []

    def add_row(r, to, label, cand_name, gate_row):
        m = full_metrics(r, to, label)
        bl_sub = bl_r.loc[bl_r.index.isin(r.index)].dropna()
        m["candidate"] = cand_name
        m["window"] = label
        m["bl_sharpe"] = round(sharpe(bl_sub), 4)
        m["sharpe_delta"] = round(m["sharpe"] - m["bl_sharpe"], 4) if not np.isnan(m["sharpe"]) else None
        rows.append(m)

    for cand_name in top3_names:
        cand_row = df_full_all[df_full_all["variant"] == cand_name]
        if cand_row.empty:
            continue
        crow = cand_row.iloc[0]
        sig_name = crow.get("signal", "A_nm_slow")
        mod_name = crow.get("modifier", "defense_release")
        intensity = crow.get("intensity", 0.05)

        # Reconstruct from gates_df
        gate_row = gates_df[gates_df["variant"] == cand_name]
        if not gate_row.empty:
            gr = gate_row.iloc[0]
            sig_name = gr.get("signal", sig_name)
            mod_name = gr.get("modifier", mod_name)
            intensity = float(gr.get("intensity", intensity))

        # Parse filter params from variant name
        # Format: sig|actX_deactY_holdZ|mod|intNpct
        try:
            import re
            parts = cand_name.split("|")
            filter_part = parts[1]
            # Use regex to extract the three integers after act, deact, hold
            act   = int(re.search(r'(?<!\w)act(\d+)', filter_part).group(1))
            deact = int(re.search(r'deact(\d+)', filter_part).group(1))
            hold  = int(re.search(r'hold(\d+)', filter_part).group(1))
        except Exception:
            act, deact, hold = 3, 2, 4

        raw_sig = raw_signals.get(sig_name, raw_signals["A_nm_slow"])
        filt_sig = apply_persistence_filter(raw_sig, act, deact, hold)
        mod_fn = MODIFIER_FUNCTIONS[mod_name]
        mod_wts = apply_modifier_to_weights(bl_wts, filt_sig, mod_fn, intensity, all_etfs)
        mod_rets = compute_returns(mod_wts, etf_rets)
        r = mod_rets["net_return"]
        to = mod_rets["turnover"]

        add_row(r, to, "full_period", cand_name, gate_row)
        add_row(r[r.index >= HOLDOUT_START], to[to.index >= HOLDOUT_START], "holdout", cand_name, gate_row)
        add_row(r[r.index <= DEV_END], to[to.index <= DEV_END], "dev", cand_name, gate_row)

        mask_ex2020 = ~((r.index >= "2020-02-01") & (r.index <= "2020-06-30"))
        add_row(r[(r.index <= DEV_END) & mask_ex2020], to[(r.index <= DEV_END) & mask_ex2020], "dev_ex_2020", cand_name, gate_row)

        mask_ex2022 = ~((r.index >= "2022-01-01") & (r.index <= "2022-12-31"))
        add_row(r[(r.index <= DEV_END) & mask_ex2022], to[(r.index <= DEV_END) & mask_ex2022], "dev_ex_2022", cand_name, gate_row)

        add_row(r[r.index < "2010-01-01"], to[to.index < "2010-01-01"], "pre_2010", cand_name, gate_row)
        add_row(r[(r.index >= "2010-01-01") & (r.index < "2020-01-01")], to[(to.index >= "2010-01-01") & (to.index < "2020-01-01")], "decade_2010s", cand_name, gate_row)

        # 2x cost
        r2x = mod_rets["gross_return"] - mod_rets["turnover"] * COST_PER_TURNOVER * 2
        add_row(r2x, to, "2x_cost_sensitivity", cand_name, gate_row)

        # Sensitivity to intensity
        for alt_int in [intensity * 0.5, intensity * 1.5]:
            alt_wts = apply_modifier_to_weights(bl_wts, filt_sig, mod_fn, alt_int, all_etfs)
            alt_rets = compute_returns(alt_wts, etf_rets)
            add_row(alt_rets["net_return"], alt_rets["turnover"], f"alt_intensity_{alt_int:.3f}", cand_name, gate_row)

        # Sensitivity to activation window
        for alt_act in [max(1, act - 1), act + 1]:
            alt_filt = apply_persistence_filter(raw_sig, alt_act, deact, hold)
            alt_wts = apply_modifier_to_weights(bl_wts, alt_filt, mod_fn, intensity, all_etfs)
            alt_rets = compute_returns(alt_wts, etf_rets)
            add_row(alt_rets["net_return"], alt_rets["turnover"], f"alt_activate_{alt_act}wk", cand_name, gate_row)

        gv = gate_row["verdict"].iloc[0] if not gate_row.empty else "UNKNOWN"
        full_idx = next((i for i, ro in enumerate(rows) if ro.get("candidate") == cand_name and ro.get("window") == "full_period"), None)
        fsh = rows[full_idx].get("sharpe_delta", "?") if full_idx is not None else "?"
        print(f"  {cand_name}: verdict={gv}, full_sharpe_delta={fsh}")

    df_rob = pd.DataFrame(rows)

    # Build markdown
    lines = ["# Top Candidate Robustness Checks (Step 2B)\n",
             f"**Sprint date:** 2026-06-06\n\n"]
    for cand_name in top3_names:
        gate_row = gates_df[gates_df["variant"] == cand_name]
        verdict = gate_row["verdict"].iloc[0] if not gate_row.empty else "UNKNOWN"
        lines.append(f"## {cand_name}\n")
        lines.append(f"**Gate verdict:** `{verdict}`\n\n")
        sub = df_rob[df_rob["candidate"] == cand_name][["window", "sharpe", "bl_sharpe", "sharpe_delta", "max_drawdown", "ann_return", "n_weeks"]]
        lines.append(sub.to_string(index=False))
        lines.append("\n\n")

    rob_md = "\n".join(lines)
    return df_rob, rob_md


# ---------------------------------------------------------------------------
# [9] Notes and summary
# ---------------------------------------------------------------------------

def write_notes(summary: dict, gates_df: pd.DataFrame, df_persist: pd.DataFrame,
                bl_full: dict, raw_signals: dict, data: dict) -> str:
    verdict = summary["overall_verdict"]

    bl_nm_sharpe_str = f"{summary.get('baseline_nm_sharpe', 'N/A')}"
    bl_nm_slow_sharpe_str = f"{summary.get('baseline_nm_slow_sharpe', 'N/A')}"

    best = gates_df.iloc[0] if not gates_df.empty else {}
    top5 = gates_df.head(5)

    lines = [
        "# Persistent Layer 2B Macro-Credit Modifier — Sprint Notes",
        "",
        f"**Sprint date:** 2026-06-06",
        f"**Verdict:** `{verdict}`",
        "",
        "---",
        "",
        "## 1. Did persistence filtering reduce signal churn vs Step 2?",
        "",
    ]

    # Pull raw signal stats
    raw_a = df_persist[(df_persist["signal"] == "A_nm_slow") & (df_persist["filter"] == "raw")]
    if not raw_a.empty:
        r = raw_a.iloc[0]
        lines.append(f"Raw NM+slowdown signal: {r['n_active']} active weeks ({r['pct_active']:.1%}), {r['n_episodes']} episodes, avg {r['avg_ep_len']:.1f} weeks/episode")
    # Best persistence setting (act=4, deact=3)
    best_persist = df_persist[(df_persist["signal"] == "A_nm_slow") & (df_persist["activate_after"] == 4) & (df_persist["deactivate_after"] == 3) & (df_persist["min_hold"] == 4)]
    if not best_persist.empty:
        bp = best_persist.iloc[0]
        lines.append(f"With act=4/deact=3/hold=4: {bp['n_active']} active weeks, {bp['n_episodes']} episodes, TO reduction {bp.get('turnover_reduction_pct', 0):.1%}")
    lines.append("")

    lines += [
        "## 2. Which target signal variant worked best?",
        "",
    ]
    for sig_name in sorted(gates_df["signal"].unique()):
        sub = gates_df[gates_df["signal"] == sig_name]
        if sub.empty:
            continue
        best_in_sig = sub.iloc[0]
        lines.append(f"- **{sig_name}**: best Sharpe delta = {best_in_sig['sharpe_delta']:+.4f} ({best_in_sig['verdict']})")
    lines.append("")

    lines += [
        "## 3. Which persistence settings worked best?",
        "",
        "Ranked by Sharpe delta among top 5 candidates:",
        "",
    ]
    if not gates_df.empty:
        for _, r in top5.iterrows():
            variant_parts = r["variant"].split("|")
            filt_part = variant_parts[1] if len(variant_parts) > 1 else "?"
            lines.append(f"- **{filt_part}** ({r['variant'].split('|')[0]}): Sharpe Δ={r['sharpe_delta']:+.4f}, NM+slow Sharpe={r.get('nm_slow_dev_sharpe','N/A')}")
    lines.append("")

    lines += [
        "## 4. Which Layer 2B modifier type worked best?",
        "",
    ]
    for mod in ["offense_budget", "defense_release", "risk_multiplier", "combined"]:
        sub = gates_df[gates_df["modifier"] == mod]
        if sub.empty:
            lines.append(f"- **{mod}**: no candidates")
            continue
        best_mod = sub.iloc[0]
        lines.append(f"- **{mod}**: best Sharpe delta = {best_mod['sharpe_delta']:+.4f}, verdict = {best_mod['verdict']}")
    lines.append("")

    lines += [
        "## 5. Which intensity worked best?",
        "",
    ]
    for intens in [0.025, 0.05, 0.075, 0.10]:
        sub = gates_df[abs(gates_df["intensity"] - intens) < 0.001]
        if sub.empty:
            continue
        best_int = sub.iloc[0]
        lines.append(f"- **{int(intens*100)}%**: best Sharpe delta = {best_int['sharpe_delta']:+.4f}")
    lines.append("")

    lines += [
        "## 6. Did the modifier improve neutral_mixed?",
        "",
        f"Baseline NM dev Sharpe: {bl_nm_sharpe_str}",
        f"Baseline NM+slow dev Sharpe: {bl_nm_slow_sharpe_str}",
        f"Candidates with NM improved (G7): {summary.get('nm_improved_count', 0)} of {summary.get('n_candidates', 0)}",
        "",
    ]

    lines += [
        "## 7. Did it improve the full portfolio?",
        "",
        f"Best full-period Sharpe delta: {best.get('sharpe_delta', 'N/A')}",
        f"PROMOTE_TO_PHASE_D_TEST: {summary.get('promote_count', 0)}",
        f"RESEARCH-ONLY: {summary.get('research_only_count', 0)}",
        f"DROP: {summary.get('drop_count', 0)}",
        "",
    ]

    lines += [
        "## 8–11. Holdout, stressed_panic, turnover, 2x-cost — see robustness report",
        "",
    ]

    lines += [
        "## 12. Did any candidate clear all promotion gates?",
        "",
        f"**PROMOTE_TO_PHASE_D_TEST: {summary.get('promote_count', 0)}**",
        "",
    ]
    if summary.get("promote_count", 0) > 0:
        promoted = gates_df[gates_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST"]
        for _, pr in promoted.iterrows():
            lines.append(f"- PROMOTED: `{pr['variant']}` — Sharpe Δ={pr['sharpe_delta']:+.4f}")

    lines += [
        "",
        "## 13. Final Verdict",
        "",
        f"**`{verdict}`**",
        "",
        "### Gate summary (top candidate)",
        "",
    ]
    if not gates_df.empty:
        gate_cols = [c for c in gates_df.columns if c.startswith("g")]
        b = best
        for gc in gate_cols:
            lines.append(f"- {gc}: {b.get(gc, 'N/A')}")

    lines += [
        "",
        "---",
        "*Research artifact sprint — no production artifacts modified.*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("STEP 2B — PERSISTENT LAYER 2B MACRO-CREDIT MODIFIER")
    print("=" * 70)

    data = load_data()

    raw_signals = build_raw_signals(data)

    df_persist = build_persistence_diagnostics(raw_signals, data)

    df_full, df_state, df_hold, df_turn, df_coarse = evaluate_candidates(data, raw_signals)

    if df_full.empty:
        print("No candidates produced — check signal coverage.")
        return

    df_full.to_csv(OUT_DIR / "candidate_metrics.csv", index=False)
    df_state.to_csv(OUT_DIR / "candidate_state_metrics.csv", index=False)
    df_hold.to_csv(OUT_DIR / "candidate_holdout_metrics.csv", index=False)
    df_turn.to_csv(OUT_DIR / "candidate_turnover_costs.csv", index=False)
    print("\n  Saved: candidate_metrics.csv, candidate_state_metrics.csv, "
          "candidate_holdout_metrics.csv, candidate_turnover_costs.csv")

    gates_df = apply_gates(df_full, df_hold, df_state, df_turn)
    gates_df.to_csv(OUT_DIR / "candidate_gate_results.csv", index=False)
    print("  Saved: candidate_gate_results.csv")

    top3_names = list(gates_df["variant"].head(3))
    print(f"\n  Top 3 candidates: {top3_names}")

    rob_df, rob_md = robustness_checks(data, top3_names, df_full, raw_signals, gates_df)
    rob_df.to_csv(OUT_DIR / "top_candidate_robustness.csv", index=False)
    (OUT_DIR / "top_candidate_robustness.md").write_text(rob_md)
    print("  Saved: top_candidate_robustness.csv, top_candidate_robustness.md")

    # Build rule definitions
    rule_lines = [
        "# Layer 2B Modifier Rule Definitions",
        "",
        "## Signal Variants",
        "- **A**: market_state=neutral_mixed AND macro_state=slowdown",
        "- **B**: A + credit trend improving (HYG/LQD 4w momentum > 0, 1-week lag)",
        "- **C**: A + credit not worsening (4w momentum > -1%, 1-week lag)",
        "- **D**: A + financial_conditions_proxy < 0 (FC benign/easing)",
        "- **E**: A + credit improving + FC benign",
        "",
        "## Persistence Filter",
        "- activate_after: consecutive True weeks before activation",
        "- deactivate_after: consecutive False weeks before deactivation",
        "- min_hold: minimum weeks to remain active before can deactivate",
        "",
        "## Modifier Types",
        "- **offense_budget**: drain from BIL/IEF/TLT, add to SPY/QQQ/HYG/EFA proportionally",
        "- **defense_release**: reduce BIL specifically, redistribute to all non-BIL ETFs",
        "- **risk_multiplier**: scale all offensive ETF weights by (1+intensity), fund from BIL",
        "- **combined**: 60% offense_budget + 40% defense_release",
        "",
        "## Intensity levels tested",
        "- 2.5%, 5.0%, 7.5%, 10.0%",
        "",
        "## Constraints preserved",
        "- Long-only (no short positions)",
        "- Weight sum normalized to 1",
        "- BIL floor: minimum 2% retained",
        "- No leverage",
        "- stressed_panic weeks: never modified (only neutral_mixed)",
        "",
    ]
    (OUT_DIR / "layer2b_modifier_rule_definitions.md").write_text("\n".join(rule_lines))

    # Compute baseline NM/NM+slow Sharpes
    bl_r = data["bl_rets"]["net_return"]
    ms = data["ms"]
    mac = data["mac"]
    nm_slow_mask = (ms == "neutral_mixed") & (mac == "slowdown")
    bl_nm_sharpe = sharpe(bl_r[(ms == "neutral_mixed") & (bl_r.index <= DEV_END)])
    bl_nm_slow_sharpe = sharpe(bl_r[nm_slow_mask & (bl_r.index <= DEV_END)])
    bl_full = df_full[df_full["variant"] == "BASELINE"].iloc[0].to_dict()

    promote_count = int((gates_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST").sum())
    ro_count = int((gates_df["verdict"] == "RESEARCH-ONLY").sum())
    drop_count = int((gates_df["verdict"] == "DROP").sum())
    nm_improved = int((gates_df["g7_nm_improved"]).sum())

    if promote_count > 0:
        overall_verdict = "PROMOTE_TO_PHASE_D_TEST"
    elif ro_count > 0:
        overall_verdict = "RESEARCH-ONLY"
    else:
        overall_verdict = "DROP"

    best = gates_df.iloc[0] if not gates_df.empty else {}
    summary = {
        "sprint": "persistent_macro_credit_layer2b_modifier",
        "date": "2026-06-06",
        "production_pin": PIN,
        "overall_verdict": overall_verdict,
        "baseline_sharpe": round(bl_full.get("sharpe", 0), 4),
        "baseline_ann_return": round(bl_full.get("ann_return", 0), 4),
        "baseline_max_dd": round(bl_full.get("max_drawdown", 0), 4),
        "baseline_nm_sharpe": round(bl_nm_sharpe, 4),
        "baseline_nm_slow_sharpe": round(bl_nm_slow_sharpe, 4),
        "n_candidates": len(gates_df),
        "promote_count": promote_count,
        "research_only_count": ro_count,
        "drop_count": drop_count,
        "nm_improved_count": nm_improved,
        "best_variant": best.get("variant", "none"),
        "best_sharpe_delta": round(float(best.get("sharpe_delta", 0)), 4),
        "best_nm_slow_sharpe": round(float(best.get("nm_slow_dev_sharpe", 0)), 4) if best.get("nm_slow_dev_sharpe") else None,
        "top3_candidates": top3_names,
    }

    with open(OUT_DIR / "persistent_macro_credit_layer2b_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    notes_md = write_notes(summary, gates_df, df_persist, bl_full, raw_signals, data)
    (OUT_DIR / "persistent_macro_credit_layer2b_notes.md").write_text(notes_md)

    print(f"\n  Saved: layer2b_modifier_rule_definitions.md, persistent_macro_credit_layer2b_summary.json, notes.md")

    print("\n" + "=" * 70)
    print(f"STEP 2B COMPLETE — OVERALL VERDICT: {overall_verdict}")
    print("=" * 70)
    print(f"  Baseline: Sharpe={bl_full.get('sharpe', 0):.4f}, AnnRet={bl_full.get('ann_return', 0):.4%}, MaxDD={bl_full.get('max_drawdown', 0):.4%}")
    print(f"  Baseline NM Sharpe: {bl_nm_sharpe:.4f}, NM+slow Sharpe: {bl_nm_slow_sharpe:.4f}")
    print(f"  Candidates evaluated: {summary['n_candidates']}")
    print(f"  PROMOTE_TO_PHASE_D_TEST: {promote_count}")
    print(f"  RESEARCH-ONLY: {ro_count}")
    print(f"  DROP: {drop_count}")
    if not gates_df.empty:
        print(f"  Best: {best['variant']} — Sharpe Δ={best['sharpe_delta']:+.4f}, verdict={best['verdict']}")


if __name__ == "__main__":
    main()
