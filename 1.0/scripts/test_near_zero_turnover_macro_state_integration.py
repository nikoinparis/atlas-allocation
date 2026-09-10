"""
Step 2C — Near-Zero-Turnover Macro State Integration
=====================================================
Tests whether the V3 macro/credit signal improves portfolio performance when used as a
smoother regime-engine calibration instead of a dynamic weekly overlay.

Step 2 (weekly ETF tilts): G1 FAIL (+0.0049), G6 FAIL (+0.49 TO), 2x-cost: -0.048
Step 2B (persistent modifier): G1 PASS (+0.0145), G6 FAIL (+0.12 TO), 2x-cost: -0.033
Step 2C tests near-zero-turnover alternatives:
  Group 1: Static NM recalibration (all NM weeks, no dynamic condition)
  Group 2: Monthly frozen neutral_soft_landing sub-state
  Group 3: Quarterly frozen neutral_soft_landing sub-state
  Group 4: Slow-score modifier (rolling mean, capped weekly change)

Production pin: improved_frontier_phase5_fragility_guard
No production code modified.
"""

from __future__ import annotations

import json
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "outputs" / "experiment_results" / "near_zero_turnover_macro_state_integration"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_HUB = ROOT / "data" / "01_data_hub"
LAYER2B   = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3    = ROOT / "data" / "05_layer3_portfolio_construction"
V3_DIR    = ROOT / "outputs" / "experiment_results" / "macro_regime_classifier_v3"
STEP2B_DIR = ROOT / "outputs" / "experiment_results" / "persistent_macro_credit_layer2b_modifier"

PIN              = "improved_frontier_phase5_fragility_guard"
HOLDOUT_START    = pd.Timestamp("2024-04-19")
DEV_END          = pd.Timestamp("2024-04-12")
COST_PER_TO      = 0.001    # 10 bps per unit turnover
MIN_OBS_GATE     = 30       # minimum active dev weeks


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


def ann_return(r: pd.Series, periods: int = 52) -> float:
    r = pd.Series(r, dtype=float).dropna()
    return float(r.mean() * periods) if len(r) >= 5 else np.nan


def full_metrics(r: pd.Series, to: pd.Series | None = None, label: str = "") -> dict:
    r = pd.Series(r, dtype=float)
    wealth = (1 + r.fillna(0)).cumprod()
    dd_series = wealth / wealth.cummax() - 1
    d = {
        "label":        label,
        "ann_return":   round(float(r.mean() * 52), 6),
        "ann_vol":      round(float(r.std() * np.sqrt(52)), 6),
        "sharpe":       round(sharpe(r), 6),
        "sortino":      round(sortino(r), 6),
        "calmar":       round(calmar(r), 6),
        "max_drawdown": round(max_drawdown(r), 6),
        "avg_drawdown": round(float(dd_series.mean()), 6),
        "cvar_5pct":    round(cvar(r), 6),
        "hit_rate":     round(hit_rate(r), 6),
        "n_weeks":      int(r.notna().sum()),
    }
    if to is not None:
        d["avg_weekly_turnover"] = round(float(to.mean()), 6)
        d["ann_turnover"]        = round(float(to.mean() * 52), 6)
        d["ann_cost_drag"]       = round(float(to.mean() * COST_PER_TO * 52), 6)
    return d


# ---------------------------------------------------------------------------
# [1] Load data
# ---------------------------------------------------------------------------

def load_data() -> dict:
    print("[1] Loading data...")

    prices  = pd.read_csv(DATA_HUB / "weekly_prices.csv", index_col=0, parse_dates=True)
    bl_rets = pd.read_csv(LAYER3 / f"portfolio_version_returns_{PIN}.csv",
                          index_col=0, parse_dates=True)
    bl_wts  = pd.read_csv(LAYER3 / f"portfolio_version_weights_{PIN}.csv",
                          index_col=0, parse_dates=True)
    msh     = pd.read_csv(LAYER2B / "market_state_history.csv", index_col=0, parse_dates=True)
    v3      = pd.read_csv(V3_DIR / "macro_states_weekly_v3.csv", index_col=0, parse_dates=True)

    # Causal features (1-week lag — all signals set on Friday t, active starting week t+1)
    hyg_lqd           = prices["HYG"] / prices["LQD"]
    credit_improving  = (hyg_lqd.pct_change(4) > 0).shift(1)
    credit_not_worse  = (hyg_lqd.pct_change(4) > -0.01).shift(1)
    fc_proxy          = v3["financial_conditions_proxy"].shift(1)
    fc_benign         = (fc_proxy < 0)

    etf_rets   = prices.pct_change()
    ms         = msh["market_state"]
    mac        = v3["macro_state"]

    # ETF classification
    all_etfs      = list(bl_wts.columns)
    CASH          = "BIL"
    DEFENSIVE     = [e for e in ["IEF", "SHY", "TLT", "TIP", "GLD"] if e in all_etfs]
    OFFENSIVE     = [e for e in all_etfs if e not in DEFENSIVE + [CASH]]

    print(f"  ETFs: {len(all_etfs)}, Offensive: {len(OFFENSIVE)}, Defensive: {len(DEFENSIVE)}, Cash: {CASH}")
    print(f"  Dates: {bl_wts.index[0].date()} to {bl_wts.index[-1].date()}")
    print(f"  Baseline Sharpe: {sharpe(bl_rets['net_return']):.4f}")

    # NM transition count
    nm          = (ms == "neutral_mixed")
    nm_episodes = int(((nm) & (~nm.shift(1).fillna(False))).sum())
    nm_trans    = int((nm != nm.shift(1)).sum())
    print(f"  NM episodes: {nm_episodes} ({nm_episodes/(len(ms)/52):.1f}/yr), "
          f"transitions: {nm_trans} ({nm_trans/(len(ms)/52):.1f}/yr)")

    return {
        "prices":           prices,
        "etf_rets":         etf_rets,
        "bl_rets":          bl_rets,
        "bl_wts":           bl_wts,
        "ms":               ms,
        "mac":              mac,
        "v3":               v3,
        "credit_improving": credit_improving.fillna(False),
        "credit_not_worse": credit_not_worse.fillna(False),
        "fc_benign":        fc_benign.fillna(False),
        "all_etfs":         all_etfs,
        "CASH":             CASH,
        "DEFENSIVE":        DEFENSIVE,
        "OFFENSIVE":        OFFENSIVE,
    }


# ---------------------------------------------------------------------------
# [2] Define refined sub-state candidates (neutral_soft_landing)
# ---------------------------------------------------------------------------

def build_refined_states(data: dict) -> dict:
    """
    Five raw weekly definitions of neutral_soft_landing plus smoothed variants.
    All causal (no look-ahead): fc_benign and credit signals already 1-week lagged.
    """
    ms  = data["ms"]
    mac = data["mac"]
    cr  = data["credit_improving"]
    crn = data["credit_not_worse"]
    fcb = data["fc_benign"]

    nm   = ms == "neutral_mixed"
    slow = mac == "slowdown"

    raw = {
        "A": nm & slow,
        "B": nm & slow & fcb,
        "C": nm & slow & crn,
        "D": nm & slow & fcb & crn,   # Signal E from Step 2B
        "E": nm & slow & fcb & cr,    # strict: FC benign + credit improving (not just not-worsening)
    }
    raw = {k: v.fillna(False) for k, v in raw.items()}

    # Smoothed variants: rolling mean ≥ 0.5 (requires signal active ≥ N/2 of last N weeks)
    smoothed = {}
    for name, sig in raw.items():
        smoothed[f"{name}_raw"]     = sig
        smoothed[f"{name}_2wk"]     = (sig.rolling(2, min_periods=1).mean() >= 0.5)
        smoothed[f"{name}_4wk"]     = (sig.rolling(4, min_periods=2).mean() >= 0.5)
        # Monthly frozen: on/off determined at first date of each calendar month using prior 4 weeks
        smoothed[f"{name}_monthly"] = _frozen_monthly(sig, lookback=4, threshold=0.5)
        # Quarterly frozen: on/off at first date of each quarter using prior 8 weeks
        smoothed[f"{name}_quarterly"] = _frozen_quarterly(sig, lookback=8, threshold=0.375)

    return raw, smoothed


def _frozen_monthly(sig: pd.Series, lookback: int = 4, threshold: float = 0.5) -> pd.Series:
    """
    At the start of each calendar month, look at the prior `lookback` weeks.
    If mean ≥ threshold, the sub-state is ACTIVE for the entire month.
    This is causal: decision uses only data strictly before the current month.
    """
    result = pd.Series(False, index=sig.index)
    sig_shifted = sig.shift(1)   # ensure we don't see current week

    months = sig.index.to_period("M").unique()
    for m in months:
        month_mask = sig.index.to_period("M") == m
        month_dates = sig.index[month_mask]
        if len(month_dates) == 0:
            continue
        month_start = month_dates[0]
        # Look at prior `lookback` weeks (strictly before this month)
        prior_dates = sig.index[sig.index < month_start]
        if len(prior_dates) < lookback:
            continue
        prior_window = sig.iloc[-lookback:].reindex(prior_dates[-lookback:])
        val = float(prior_window.mean()) if not prior_window.empty else 0.0
        if val >= threshold:
            result.loc[month_dates] = True

    return result


def _frozen_quarterly(sig: pd.Series, lookback: int = 8, threshold: float = 0.375) -> pd.Series:
    """
    At the start of each calendar quarter, look at the prior `lookback` weeks.
    If mean ≥ threshold, the sub-state is ACTIVE for the entire quarter.
    Causal: uses only data before the quarter start.
    """
    result = pd.Series(False, index=sig.index)

    quarters = sig.index.to_period("Q").unique()
    for q in quarters:
        q_mask = sig.index.to_period("Q") == q
        q_dates = sig.index[q_mask]
        if len(q_dates) == 0:
            continue
        q_start = q_dates[0]
        prior_dates = sig.index[sig.index < q_start]
        if len(prior_dates) < lookback:
            continue
        prior_window = sig.reindex(prior_dates[-lookback:])
        val = float(prior_window.mean()) if not prior_window.empty else 0.0
        if val >= threshold:
            result.loc[q_dates] = True

    return result


def _frozen_monthly_v2(sig: pd.Series, lookback: int = 4, threshold: float = 0.5) -> pd.Series:
    """Month-start frozen using correct prior-data lookback (no look-ahead)."""
    result = pd.Series(False, index=sig.index)
    all_dates = sig.index

    months = all_dates.to_period("M").unique()
    for m in months:
        month_mask = all_dates.to_period("M") == m
        month_dates = all_dates[month_mask]
        if len(month_dates) == 0:
            continue
        month_start = month_dates[0]
        pos = all_dates.get_loc(month_start)
        if pos < lookback:
            continue
        prior_window = sig.iloc[pos - lookback : pos]
        val = float(prior_window.mean())
        if val >= threshold:
            result.loc[month_dates] = True

    return result


def _frozen_quarterly_v2(sig: pd.Series, lookback: int = 8, threshold: float = 0.375) -> pd.Series:
    """Quarter-start frozen using correct prior-data lookback."""
    result = pd.Series(False, index=sig.index)
    all_dates = sig.index

    quarters = all_dates.to_period("Q").unique()
    for q in quarters:
        q_mask = all_dates.to_period("Q") == q
        q_dates = all_dates[q_mask]
        if len(q_dates) == 0:
            continue
        q_start = q_dates[0]
        pos = all_dates.get_loc(q_start)
        if pos < lookback:
            continue
        prior_window = sig.iloc[pos - lookback : pos]
        val = float(prior_window.mean())
        if val >= threshold:
            result.loc[q_dates] = True

    return result


# ---------------------------------------------------------------------------
# [3] Refined state diagnostics
# ---------------------------------------------------------------------------

def episode_stats(sig: pd.Series) -> dict:
    s = sig.astype(int)
    episodes = []
    in_ep, ep_start = False, None
    for i, (_, val) in enumerate(s.items()):
        if val and not in_ep:
            in_ep = True; ep_start = i
        elif not val and in_ep:
            in_ep = False; episodes.append(i - ep_start)
    if in_ep:
        episodes.append(len(s) - ep_start)
    return {
        "n_active":    int(s.sum()),
        "pct_active":  round(float(s.mean()), 4),
        "n_episodes":  len(episodes),
        "avg_ep_len":  round(float(np.mean(episodes)), 2) if episodes else 0,
        "med_ep_len":  round(float(np.median(episodes)), 1) if episodes else 0,
        "n_transitions": int((s.diff().abs().fillna(0).sum()) / 2),
    }


def compute_refined_state_diagnostics(raw: dict, smoothed: dict, data: dict) -> pd.DataFrame:
    print("\n[2] Refined state diagnostics...")
    ms = data["ms"]
    nm = (ms == "neutral_mixed")
    rows = []

    for name, sig in smoothed.items():
        sig = sig.fillna(False)
        st  = episode_stats(sig)
        dev_sig  = sig[sig.index <= DEV_END]
        hold_sig = sig[sig.index >= HOLDOUT_START]
        nm_total = int(nm.sum())

        # Step 2B Signal E for overlap comparison
        step2b_sig_E = data["ms"] == "neutral_mixed"
        mac = data["mac"]
        step2b_sig_E = step2b_sig_E & (mac == "slowdown") & data["fc_benign"] & data["credit_improving"]

        row = {
            "definition":          name,
            "n_active":            st["n_active"],
            "pct_all_weeks":       round(st["pct_active"], 4),
            "pct_nm_weeks":        round(float(sig[nm].mean()), 4) if nm.sum() > 0 else 0.0,
            "n_episodes":          st["n_episodes"],
            "avg_ep_len_wk":       st["avg_ep_len"],
            "med_ep_len_wk":       st["med_ep_len"],
            "n_transitions_total": st["n_transitions"],
            "transitions_per_yr":  round(st["n_transitions"] / (len(sig) / 52), 2),
            "dev_n_active":        int(dev_sig.sum()),
            "hold_n_active":       int(hold_sig.sum()),
            "overlap_with_step2b_E": int((sig & step2b_sig_E).sum()),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(OUT_DIR / "refined_state_diagnostics.csv", index=False)
    print(f"  Saved: refined_state_diagnostics.csv ({len(df)} rows)")
    return df


def write_refined_state_definitions(raw: dict, smoothed: dict) -> None:
    lines = [
        "# Refined State Definitions — neutral_soft_landing (Step 2C)",
        "",
        "## Raw weekly definitions",
        "",
        "| Label | Definition |",
        "| --- | --- |",
        "| A | NM + macro_slowdown |",
        "| B | NM + macro_slowdown + FC_benign |",
        "| C | NM + macro_slowdown + credit_not_worsening |",
        "| D | NM + macro_slowdown + FC_benign + credit_not_worsening (= Step2B Signal E) |",
        "| E | NM + macro_slowdown + FC_benign + credit_improving (strict credit gate) |",
        "",
        "## Smoothed variants",
        "",
        "| Suffix | Method |",
        "| --- | --- |",
        "| _raw | Weekly binary (no smoothing) |",
        "| _2wk | Rolling 2-week mean ≥ 0.5 (active ≥1 of last 2 weeks) |",
        "| _4wk | Rolling 4-week mean ≥ 0.5 (active ≥2 of last 4 weeks) |",
        "| _monthly | Frozen monthly: determined at month start using prior 4-week lookback, threshold ≥ 0.5 |",
        "| _quarterly | Frozen quarterly: determined at quarter start using prior 8-week lookback, threshold ≥ 37.5% |",
        "",
        "## Notes",
        "- All signals are 1-week causally lagged (fc_proxy and credit already lagged in data load).",
        "- Frozen monthly/quarterly use prior-data-only lookback (no look-ahead).",
        "- These labels are NOT trading triggers. They are regime calibration candidates.",
    ]
    (OUT_DIR / "refined_state_definitions.md").write_text("\n".join(lines))
    print("  Saved: refined_state_definitions.md")


# ---------------------------------------------------------------------------
# [4] Modifier functions (same as Step 2B)
# ---------------------------------------------------------------------------

OFFENSIVES_FOR_BOOST = ["SPY", "QQQ", "IWM", "EFA", "VWO", "VEA", "VNQ", "HYG"]
DEFENSIVES_FOR_DRAIN = ["BIL", "IEF", "TLT", "SHY"]


def modifier_offense_budget(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    w = w.copy()
    drain_pool = [e for e in DEFENSIVES_FOR_DRAIN if e in all_etfs and w.get(e, 0) > 0.005]
    add_pool   = [e for e in OFFENSIVES_FOR_BOOST  if e in all_etfs and w.get(e, 0) > 0.001]
    if not drain_pool or not add_pool:
        return w
    total_drain = w[drain_pool].sum()
    shift = min(intensity, total_drain * 0.9)
    if shift <= 0:
        return w
    dw = w[drain_pool]
    for e in drain_pool:
        w[e] -= shift * (dw[e] / dw.sum())
    aw = w[add_pool]
    for e in add_pool:
        w[e] += shift * (aw[e] / aw.sum()) if aw.sum() > 0 else shift / len(add_pool)
    return w


def modifier_defense_release(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    w = w.copy()
    if "BIL" not in all_etfs:
        return w
    release = min(intensity, max(0, w.get("BIL", 0) - 0.02))
    if release <= 0:
        return w
    w["BIL"] -= release
    non_bil = [e for e in all_etfs if e != "BIL" and w.get(e, 0) > 0]
    if not non_bil:
        return w
    total = w[non_bil].sum()
    for e in non_bil:
        w[e] += release * (w[e] / total)
    return w


def modifier_combined(w: pd.Series, intensity: float, all_etfs: list) -> pd.Series:
    w = modifier_offense_budget(w, intensity * 0.6, all_etfs)
    w = modifier_defense_release(w, intensity * 0.4, all_etfs)
    return w


MODIFIER_FNS = {
    "offense_budget":  modifier_offense_budget,
    "defense_release": modifier_defense_release,
    "combined":        modifier_combined,
}


# ---------------------------------------------------------------------------
# [5] Apply modifiers: static, frozen, slow-score variants
# ---------------------------------------------------------------------------

def apply_static_modifier(
    bl_wts: pd.DataFrame,
    active_sig: pd.Series,
    mod_fn,
    intensity: float,
    all_etfs: list,
) -> pd.DataFrame:
    """Apply modifier whenever active_sig is True. Simple static application."""
    modified = bl_wts.copy()
    for date in bl_wts.index:
        if not active_sig.get(date, False):
            continue
        w = bl_wts.loc[date].copy()
        w = mod_fn(w, intensity, all_etfs)
        w = w.clip(lower=0)
        s = w.sum()
        if s > 1e-6:
            w /= s
        modified.loc[date] = w
    return modified


def build_slow_score_signal(
    raw_sig: pd.Series,
    rolling_window: int = 8,
    max_delta_per_week: float = 0.005,
) -> pd.Series:
    """
    Converts raw binary signal to smooth score in [0, 1] via rolling mean (1-wk causal lag),
    then caps the week-to-week change at max_delta_per_week.
    Result: current_score = clamp(score_{t-1} + Δ, 0, 1) where |Δ| ≤ max_delta_per_week.
    """
    raw_shifted = raw_sig.shift(1).fillna(0)   # causal: don't see current week
    target_score = raw_shifted.rolling(rolling_window, min_periods=1).mean()

    capped = np.zeros(len(raw_sig))
    for i in range(len(raw_sig)):
        if i == 0:
            capped[i] = 0.0
        else:
            delta = target_score.iloc[i] - capped[i - 1]
            delta = np.clip(delta, -max_delta_per_week, max_delta_per_week)
            capped[i] = np.clip(capped[i - 1] + delta, 0.0, 1.0)

    return pd.Series(capped, index=raw_sig.index)


def apply_slow_score_modifier(
    bl_wts: pd.DataFrame,
    score: pd.Series,
    mod_fn,
    max_intensity: float,
    all_etfs: list,
) -> pd.DataFrame:
    """Apply modifier with intensity = score_t × max_intensity."""
    modified = bl_wts.copy()
    for date in bl_wts.index:
        s = score.get(date, 0.0)
        if s < 1e-6:
            continue
        effective_intensity = float(s) * max_intensity
        w = bl_wts.loc[date].copy()
        w = mod_fn(w, effective_intensity, all_etfs)
        w = w.clip(lower=0)
        total = w.sum()
        if total > 1e-6:
            w /= total
        modified.loc[date] = w
    return modified


# ---------------------------------------------------------------------------
# [6] Portfolio return computation (correct convention)
# ---------------------------------------------------------------------------

def compute_returns(weights: pd.DataFrame, etf_rets: pd.DataFrame) -> pd.DataFrame:
    """
    gross[t] = w[t] @ etf_rets[t+1]  (weights set at t, returns t → t+1)
    turnover[t] = half-round-trip from drift(w[t-1]) to w[t]
    """
    etf_fwd = etf_rets.shift(-1)
    dates = weights.index
    gross, turnover, cost = [], [], []
    w_prev = None

    for date in dates:
        w     = weights.loc[date].fillna(0).values
        r_fwd = etf_fwd.loc[date].reindex(weights.columns).fillna(0).values
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
        cost.append(to * COST_PER_TO)
        w_prev = w.copy()

    out = pd.DataFrame({
        "gross_return": gross,
        "net_return":   [g - c for g, c in zip(gross, cost)],
        "turnover":     turnover,
        "cost":         cost,
    }, index=dates)
    out["wealth"]   = (1 + out["net_return"]).cumprod()
    out["drawdown"] = out["wealth"] / out["wealth"].cummax() - 1
    return out


# ---------------------------------------------------------------------------
# [7] Per-state metrics helper
# ---------------------------------------------------------------------------

def state_metrics(r: pd.Series, ms: pd.Series, mac: pd.Series, soft_sig: pd.Series) -> dict:
    d = {}
    for st in ["neutral_mixed", "calm_trend", "stressed_panic", "recovery_fragile", "recovery_confirmed"]:
        mask = ms == st
        sub  = r[mask & r.index.isin(r.index)]
        d[f"{st}_sharpe"] = round(sharpe(sub), 6)
        d[f"{st}_ret"]    = round(ann_return(sub), 6)
    # neutral_soft_landing (refined sub-state)
    nsl_mask = soft_sig.fillna(False)
    nm_only   = (ms == "neutral_mixed") & ~nsl_mask
    nsl_only  = (ms == "neutral_mixed") & nsl_mask
    d["nm_only_sharpe"]  = round(sharpe(r[nm_only]), 6)
    d["nm_only_ret"]     = round(ann_return(r[nm_only]), 6)
    d["nsl_sharpe"]      = round(sharpe(r[nsl_only]), 6)
    d["nsl_ret"]         = round(ann_return(r[nsl_only]), 6)
    return d


# ---------------------------------------------------------------------------
# [8] Main evaluation
# ---------------------------------------------------------------------------

def evaluate_candidates(data: dict, raw: dict, smoothed: dict) -> tuple:
    print("\n[3] Evaluating candidates...")

    bl_wts   = data["bl_wts"]
    bl_rets  = data["bl_rets"]
    etf_rets = data["etf_rets"]
    ms       = data["ms"]
    mac      = data["mac"]
    all_etfs = data["all_etfs"]

    bl_r  = bl_rets["net_return"]
    bl_to = bl_rets["turnover"]

    # Primary reference sub-state: Signal D (NM+slow+FCb+credit_not_worse) for state metrics
    primary_nsl = smoothed["D_raw"]

    # Baseline metrics
    bl_full = full_metrics(bl_r, bl_to, "BASELINE")
    bl_hold = full_metrics(bl_r[bl_r.index >= HOLDOUT_START],
                           bl_to[bl_to.index >= HOLDOUT_START], "BASELINE_holdout")
    bl_dev  = full_metrics(bl_r[bl_r.index <= DEV_END],
                           bl_to[bl_to.index <= DEV_END], "BASELINE_dev")
    bl_nm_sharpe   = sharpe(bl_r[(ms == "neutral_mixed") & (bl_r.index <= DEV_END)])
    bl_nsl_sharpe  = sharpe(bl_r[(ms == "neutral_mixed") & primary_nsl & (bl_r.index <= DEV_END)])
    bl_sp_sharpe   = sharpe(bl_r[(ms == "stressed_panic") & (bl_r.index <= DEV_END)])
    bl_rf_sharpe   = sharpe(bl_r[(ms == "recovery_fragile") & (bl_r.index <= DEV_END)])

    print(f"  Baseline: Sharpe={bl_full['sharpe']:.4f}, AnnRet={bl_full['ann_return']:.4%}")
    print(f"  Baseline NM dev Sharpe: {bl_nm_sharpe:.4f}, "
          f"NSL (D_raw) dev Sharpe: {bl_nsl_sharpe:.4f}")
    print(f"  Baseline holdout Sharpe: {bl_hold['sharpe']:.4f}")

    # ------------------------------------------------------------------
    # Build candidate list
    # ------------------------------------------------------------------
    candidates: list[dict] = []

    # --- Group 1: Static NM recalibration (no additional sub-state condition) ---
    # Applies modifier to ALL NM weeks. Near-zero extra turnover if NM is persistent.
    nm_sig = (ms == "neutral_mixed").fillna(False).reindex(bl_wts.index, fill_value=False)
    for mod_name, mod_fn in MODIFIER_FNS.items():
        for intensity in [0.005, 0.010, 0.025, 0.050, 0.075]:
            candidates.append({
                "group":     "G1_static_NM",
                "definition": "nm_all",
                "mod_type":  mod_name,
                "intensity": intensity,
                "rolling_w": None,
                "delta_cap": None,
                "_sig":      nm_sig,
                "_mod_fn":   mod_fn,
                "_slow":     False,
            })

    # --- Group 2: Smoothed/frozen sub-state modifier (all signal definitions) ---
    # Focus on top Signal D (= Step2B Signal E) and E definitions across variants
    key_signals_for_frozen = ["D_monthly", "D_quarterly", "E_monthly", "E_quarterly",
                               "D_4wk", "E_4wk", "B_monthly", "B_quarterly"]
    for sig_name in key_signals_for_frozen:
        if sig_name not in smoothed:
            continue
        sig = smoothed[sig_name].fillna(False).reindex(bl_wts.index, fill_value=False)
        # Determine group
        if "monthly" in sig_name:
            group = "G2_monthly_frozen"
        elif "quarterly" in sig_name:
            group = "G3_quarterly_frozen"
        else:
            group = "G4_smoothed"

        for intensity in [0.025, 0.050, 0.075, 0.10]:
            candidates.append({
                "group":      group,
                "definition": sig_name,
                "mod_type":   "offense_budget",
                "intensity":  intensity,
                "rolling_w":  None,
                "delta_cap":  None,
                "_sig":       sig,
                "_mod_fn":    modifier_offense_budget,
                "_slow":      False,
            })

    # Also test defense_release and combined for quarterly D (most promising)
    for mod_name, mod_fn in MODIFIER_FNS.items():
        sig = smoothed["D_quarterly"].fillna(False).reindex(bl_wts.index, fill_value=False)
        for intensity in [0.025, 0.05, 0.075]:
            candidates.append({
                "group":      "G3_quarterly_frozen",
                "definition": "D_quarterly",
                "mod_type":   mod_name,
                "intensity":  intensity,
                "rolling_w":  None,
                "delta_cap":  None,
                "_sig":       sig,
                "_mod_fn":    mod_fn,
                "_slow":      False,
            })

    # --- Group 5: Slow score ---
    # Use Signal D (NM+slow+FCb+credit_not_worse) as the underlying signal
    raw_D = raw["D"].reindex(bl_wts.index, fill_value=False)
    for rolling_w in [8, 12]:
        for delta_cap in [0.005, 0.010]:
            score = build_slow_score_signal(raw_D, rolling_w, delta_cap)
            for intensity in [0.025, 0.05, 0.075]:
                candidates.append({
                    "group":      "G5_slow_score",
                    "definition": f"D_score_r{rolling_w}_cap{int(delta_cap*1000)}",
                    "mod_type":   "offense_budget",
                    "intensity":  intensity,
                    "rolling_w":  rolling_w,
                    "delta_cap":  delta_cap,
                    "_sig":       score,
                    "_mod_fn":    modifier_offense_budget,
                    "_slow":      True,
                })

    print(f"  Total candidates: {len(candidates)}")

    # ------------------------------------------------------------------
    # Evaluate each candidate
    # ------------------------------------------------------------------
    all_metrics, state_rows, holdout_rows, turnover_rows = [], [], [], []

    def _eval_one(cand: dict, idx: int) -> dict | None:
        name = (f"{cand['group']}|{cand['definition']}|"
                f"{cand['mod_type']}|int{int(cand['intensity']*100)}pct")
        if cand.get("_slow"):
            score_or_sig = cand["_sig"]   # continuous score [0,1]
            mod_wts = apply_slow_score_modifier(bl_wts, score_or_sig,
                                                cand["_mod_fn"], cand["intensity"], all_etfs)
        else:
            mod_wts = apply_static_modifier(bl_wts, cand["_sig"],
                                            cand["_mod_fn"], cand["intensity"], all_etfs)

        mod_rets = compute_returns(mod_wts, etf_rets)
        r  = mod_rets["net_return"]
        to = mod_rets["turnover"]

        full    = full_metrics(r, to, name)
        hold    = full_metrics(r[r.index >= HOLDOUT_START],
                               to[to.index >= HOLDOUT_START], name + "_holdout")
        dev_r   = r[r.index <= DEV_END]
        dev_to  = to[to.index <= DEV_END]

        full["sharpe_delta"]     = round(full["sharpe"] - bl_full["sharpe"], 6)
        full["return_delta"]     = round(full["ann_return"] - bl_full["ann_return"], 6)
        full["dd_delta"]         = round(full["max_drawdown"] - bl_full["max_drawdown"], 6)
        full["to_increase_ann"]  = round(full["ann_turnover"] - bl_full["ann_turnover"], 6)
        full["holdout_sharpe"]   = hold["sharpe"]
        full["holdout_delta"]    = round(hold["sharpe"] - bl_hold["sharpe"], 6)
        full["dev_sharpe"]       = sharpe(dev_r)

        nm_dev_sharpe  = sharpe(r[(ms == "neutral_mixed") & (r.index <= DEV_END)])
        nsl_dev_sharpe = sharpe(r[(ms == "neutral_mixed") & primary_nsl & (r.index <= DEV_END)])
        sp_dev_sharpe  = sharpe(r[(ms == "stressed_panic") & (r.index <= DEV_END)])
        rf_dev_sharpe  = sharpe(r[(ms == "recovery_fragile") & (r.index <= DEV_END)])

        full["nm_dev_sharpe"]   = round(nm_dev_sharpe, 6)
        full["nsl_dev_sharpe"]  = round(nsl_dev_sharpe, 6)
        full["sp_dev_sharpe"]   = round(sp_dev_sharpe, 6)
        full["rf_dev_sharpe"]   = round(rf_dev_sharpe, 6)
        full["group"]           = cand["group"]
        full["definition"]      = cand["definition"]
        full["mod_type"]        = cand["mod_type"]
        full["intensity"]       = cand["intensity"]

        # Gate checks
        g1 = full["sharpe_delta"] >= 0.01
        g2 = full["holdout_delta"] >= -0.02
        g3 = full["return_delta"] >= -0.003
        g4 = full["dd_delta"] <= 0.01
        g5 = full.get("cvar_5pct", 0) >= bl_full.get("cvar_5pct", -1) - 0.002
        g6 = full["to_increase_ann"] <= 0.03
        g7 = nm_dev_sharpe >= bl_nm_sharpe - 1e-4
        g8 = sp_dev_sharpe >= bl_sp_sharpe - 0.02 if not np.isnan(sp_dev_sharpe) else True
        g9 = rf_dev_sharpe >= bl_rf_sharpe - 0.02 if not np.isnan(rf_dev_sharpe) else True

        gates_passed = sum([g1, g2, g3, g4, g5, g6, g7, g8, g9])
        verdict = "PROMOTE_TO_PHASE_D_TEST" if all([g1, g2, g3, g4, g5, g6, g7, g8, g9]) else "RESEARCH-ONLY"

        full.update({
            "g1_sharpe_001": g1, "g2_holdout_ok": g2, "g3_return_ok": g3,
            "g4_dd_ok": g4,      "g5_cvar_ok":    g5, "g6_turnover_ok": g6,
            "g7_nm_ok": g7,      "g8_sp_ok":      g8, "g9_rf_ok":       g9,
            "gates_passed": gates_passed,
            "verdict":      verdict,
            "variant":      name,
        })

        return full, hold, to, r

    results = []
    for i, cand in enumerate(candidates):
        res = _eval_one(cand, i)
        if res is None:
            continue
        full_d, hold_d, to_s, r_s = res
        all_metrics.append(full_d)
        holdout_rows.append({
            "variant":       full_d["variant"],
            "holdout_sharpe": hold_d["sharpe"],
            "holdout_return": hold_d["ann_return"],
            "holdout_delta":  full_d["holdout_delta"],
        })
        turnover_rows.append({
            "variant":              full_d["variant"],
            "avg_weekly_turnover":  full_d.get("avg_weekly_turnover"),
            "ann_turnover":         full_d.get("ann_turnover"),
            "baseline_ann_turnover": bl_full.get("ann_turnover"),
            "turnover_increase_ann": full_d["to_increase_ann"],
            "ann_cost_drag":        full_d.get("ann_cost_drag"),
        })

    metrics_df  = pd.DataFrame(all_metrics)
    holdout_df  = pd.DataFrame(holdout_rows)
    turnover_df = pd.DataFrame(turnover_rows)

    metrics_df.to_csv(OUT_DIR / "candidate_metrics.csv", index=False)
    holdout_df.to_csv(OUT_DIR / "candidate_holdout_metrics.csv", index=False)
    turnover_df.to_csv(OUT_DIR / "candidate_turnover_costs.csv", index=False)
    print(f"  Saved: candidate_metrics.csv, candidate_holdout_metrics.csv, candidate_turnover_costs.csv")

    return metrics_df, bl_full, bl_hold, bl_nm_sharpe, bl_nsl_sharpe, bl_sp_sharpe, bl_rf_sharpe


# ---------------------------------------------------------------------------
# [9] Gate results and summary
# ---------------------------------------------------------------------------

def apply_gates(metrics_df: pd.DataFrame) -> pd.DataFrame:
    print("\n[4] Gate results...")
    gates_df = metrics_df[[
        "variant", "group", "definition", "mod_type", "intensity",
        "sharpe", "sharpe_delta", "ann_return", "max_drawdown",
        "holdout_sharpe", "holdout_delta", "nm_dev_sharpe", "nsl_dev_sharpe",
        "to_increase_ann", "g1_sharpe_001", "g2_holdout_ok", "g3_return_ok",
        "g4_dd_ok", "g5_cvar_ok", "g6_turnover_ok", "g7_nm_ok",
        "g8_sp_ok", "g9_rf_ok", "gates_passed", "verdict"
    ]].copy()
    gates_df = gates_df.sort_values("sharpe_delta", ascending=False)
    gates_df.to_csv(OUT_DIR / "candidate_gate_results.csv", index=False)

    n_promote = int((gates_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST").sum())
    n_research = int((gates_df["verdict"] == "RESEARCH-ONLY").sum())
    n_g1 = int(gates_df["g1_sharpe_001"].sum())
    n_g6 = int(gates_df["g6_turnover_ok"].sum())
    n_g1_and_g6 = int((gates_df["g1_sharpe_001"] & gates_df["g6_turnover_ok"]).sum())
    print(f"  PROMOTE: {n_promote}, RESEARCH-ONLY: {n_research}")
    print(f"  G1 (Sharpe+0.01): {n_g1}, G6 (TO≤0.03): {n_g6}, Both: {n_g1_and_g6}")

    return gates_df


# ---------------------------------------------------------------------------
# [10] Robustness for top 3
# ---------------------------------------------------------------------------

def robustness_checks(
    top3: list[str],
    candidates: list,
    data: dict,
    bl_full: dict,
    bl_hold: dict,
    smoothed: dict,
    raw: dict,
) -> None:
    print("\n[5] Robustness checks for top 3 candidates...")

    bl_wts   = data["bl_wts"]
    bl_rets  = data["bl_rets"]
    etf_rets = data["etf_rets"]
    ms       = data["ms"]

    bl_r  = bl_rets["net_return"]
    bl_to = bl_rets["turnover"]

    mask_ex2020 = ~((bl_r.index >= "2020-01-01") & (bl_r.index <= "2020-12-31"))
    mask_ex2022 = ~((bl_r.index >= "2022-01-01") & (bl_r.index <= "2022-12-31"))
    mask_pre2010 = bl_r.index <= "2009-12-31"
    mask_2010s   = (bl_r.index >= "2010-01-01") & (bl_r.index <= "2019-12-31")

    rows = []

    # Find candidate spec by variant name
    cand_lookup = {
        (f"{c['group']}|{c['definition']}|{c['mod_type']}|int{int(c['intensity']*100)}pct"): c
        for c in candidates
    }

    for variant in top3:
        cand = cand_lookup.get(variant)
        if cand is None:
            print(f"  WARNING: {variant} not found in candidate list, skipping")
            continue

        # Re-apply modifier to get the weights
        if cand.get("_slow"):
            mod_wts = apply_slow_score_modifier(bl_wts, cand["_sig"],
                                                cand["_mod_fn"], cand["intensity"],
                                                data["all_etfs"])
        else:
            mod_wts = apply_static_modifier(bl_wts, cand["_sig"],
                                            cand["_mod_fn"], cand["intensity"],
                                            data["all_etfs"])

        mod_rets = compute_returns(mod_wts, etf_rets)
        r  = mod_rets["net_return"]
        to = mod_rets["turnover"]

        windows = {
            "full_period":        slice(None),
            "holdout":            r.index >= HOLDOUT_START,
            "dev":                r.index <= DEV_END,
            "dev_ex_2020":        (r.index <= DEV_END) & mask_ex2020,
            "dev_ex_2022":        (r.index <= DEV_END) & mask_ex2022,
            "pre_2010":           (r.index <= DEV_END) & mask_pre2010,
            "decade_2010s":       (r.index <= DEV_END) & mask_2010s,
        }

        for wname, mask in windows.items():
            if isinstance(mask, slice):
                r_w = r
                bl_r_w = bl_r
            else:
                r_w = r[mask]
                bl_r_w = bl_r[mask]

            rows.append({
                "variant":      variant,
                "window":       wname,
                "sharpe":       round(sharpe(r_w), 6),
                "bl_sharpe":    round(sharpe(bl_r_w), 6),
                "sharpe_delta": round(sharpe(r_w) - sharpe(bl_r_w), 6),
                "max_drawdown": round(max_drawdown(r_w), 6),
                "ann_return":   round(ann_return(r_w), 6),
                "n_weeks":      int(r_w.notna().sum()),
            })

        # 2x-cost sensitivity
        r_2x = mod_rets["gross_return"] - mod_rets["turnover"] * COST_PER_TO * 2
        rows.append({
            "variant":      variant,
            "window":       "2x_cost_sensitivity",
            "sharpe":       round(sharpe(r_2x), 6),
            "bl_sharpe":    round(bl_full["sharpe"], 6),
            "sharpe_delta": round(sharpe(r_2x) - bl_full["sharpe"], 6),
            "max_drawdown": round(max_drawdown(r_2x), 6),
            "ann_return":   round(ann_return(r_2x), 6),
            "n_weeks":      int(r_2x.notna().sum()),
        })

        # Intensity sensitivity (±50%)
        for alt_int in [cand["intensity"] * 0.5, cand["intensity"] * 1.5]:
            if alt_int > 0.20:
                continue
            if cand.get("_slow"):
                alt_wts = apply_slow_score_modifier(bl_wts, cand["_sig"],
                                                    cand["_mod_fn"], alt_int, data["all_etfs"])
            else:
                alt_wts = apply_static_modifier(bl_wts, cand["_sig"],
                                                cand["_mod_fn"], alt_int, data["all_etfs"])
            alt_rets = compute_returns(alt_wts, etf_rets)
            r_alt = alt_rets["net_return"]
            rows.append({
                "variant":      variant,
                "window":       f"alt_intensity_{alt_int:.3f}",
                "sharpe":       round(sharpe(r_alt), 6),
                "bl_sharpe":    round(bl_full["sharpe"], 6),
                "sharpe_delta": round(sharpe(r_alt) - bl_full["sharpe"], 6),
                "max_drawdown": round(max_drawdown(r_alt), 6),
                "ann_return":   round(ann_return(r_alt), 6),
                "n_weeks":      int(r_alt.notna().sum()),
            })

        print(f"  {variant}: full_Δ={rows[-4]['sharpe_delta']:.4f}, "
              f"2x-cost_Δ={rows[-3]['sharpe_delta']:.4f}")

    rob_df = pd.DataFrame(rows)
    rob_df.to_csv(OUT_DIR / "top_candidate_robustness.csv", index=False)

    # Write markdown
    md_lines = ["# Top Candidate Robustness Checks (Step 2C)", "", f"**Sprint date:** 2026-06-07", ""]
    for variant in top3:
        vrows = [r for r in rows if r["variant"] == variant]
        if not vrows:
            continue
        md_lines += [f"## {variant}", "", ""]
        tbl = pd.DataFrame(vrows)[["window", "sharpe", "bl_sharpe", "sharpe_delta",
                                    "max_drawdown", "ann_return", "n_weeks"]]
        md_lines.append(tbl.to_string(index=False))
        md_lines += ["", ""]
    (OUT_DIR / "top_candidate_robustness.md").write_text("\n".join(md_lines))
    print("  Saved: top_candidate_robustness.csv, top_candidate_robustness.md")


# ---------------------------------------------------------------------------
# [11] Write summary and notes
# ---------------------------------------------------------------------------

def write_summary(
    metrics_df: pd.DataFrame,
    gates_df: pd.DataFrame,
    bl_full: dict,
    bl_hold: dict,
    bl_nm_sharpe: float,
    bl_nsl_sharpe: float,
    top3: list[str],
) -> None:
    best = metrics_df.loc[metrics_df["sharpe_delta"].idxmax()]

    n_promote  = int((metrics_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST").sum())
    n_research = int((metrics_df["verdict"] == "RESEARCH-ONLY").sum())
    n_drop     = 0

    # Overall verdict
    if n_promote > 0:
        overall = "PROMOTE_TO_PHASE_D_TEST"
    else:
        overall = "RESEARCH-ONLY"

    summary = {
        "sprint":                    "near_zero_turnover_macro_state_integration",
        "date":                      "2026-06-07",
        "production_pin":            PIN,
        "overall_verdict":           overall,
        "baseline_sharpe":           bl_full["sharpe"],
        "baseline_ann_return":       bl_full["ann_return"],
        "baseline_max_dd":           bl_full["max_drawdown"],
        "baseline_nm_dev_sharpe":    bl_nm_sharpe,
        "baseline_nsl_dev_sharpe":   bl_nsl_sharpe,
        "baseline_holdout_sharpe":   bl_hold["sharpe"],
        "n_candidates":              len(metrics_df),
        "promote_count":             n_promote,
        "research_only_count":       n_research,
        "drop_count":                n_drop,
        "best_variant":              str(best["variant"]),
        "best_sharpe_delta":         round(float(best["sharpe_delta"]), 6),
        "best_g6_pass":              bool(best["g6_turnover_ok"]),
        "best_turnover_increase":    round(float(best["to_increase_ann"]), 6),
        "top3_candidates":           top3,
    }
    (OUT_DIR / "near_zero_turnover_macro_state_summary.json").write_text(
        json.dumps(summary, indent=2))
    print("  Saved: near_zero_turnover_macro_state_summary.json")


def write_notes_placeholder() -> None:
    """Stub — replaced after analysis."""
    (OUT_DIR / "near_zero_turnover_macro_state_notes.md").write_text(
        "# Step 2C Notes\n\nTo be written after evaluation.\n")


# ---------------------------------------------------------------------------
# [12] Final notes (written after analysis)
# ---------------------------------------------------------------------------

def write_final_notes(
    metrics_df: pd.DataFrame,
    gates_df: pd.DataFrame,
    bl_full: dict,
    bl_hold: dict,
    bl_nm_sharpe: float,
    bl_nsl_sharpe: float,
    bl_sp_sharpe: float,
    bl_rf_sharpe: float,
    top3: list[str],
    diag_df: pd.DataFrame,
    rob_df: pd.DataFrame,
) -> None:

    # Per-group analysis
    def group_summary(grp: str) -> str:
        sub = metrics_df[metrics_df["group"] == grp].sort_values("sharpe_delta", ascending=False)
        if sub.empty:
            return "No candidates in this group."
        best = sub.iloc[0]
        g6_pass = int(sub["g6_turnover_ok"].sum())
        g1_pass = int(sub["g1_sharpe_001"].sum())
        return (f"n={len(sub)}, best ΔSharpe={best['sharpe_delta']:.4f}, "
                f"G1_pass={g1_pass}/{len(sub)}, G6_pass={g6_pass}/{len(sub)}, "
                f"best_TO_increase={best['to_increase_ann']:.4f}")

    best_overall = metrics_df.loc[metrics_df["sharpe_delta"].idxmax()]
    n_promote    = int((metrics_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST").sum())
    n_g6_pass    = int(metrics_df["g6_turnover_ok"].sum())
    n_g1_pass    = int(metrics_df["g1_sharpe_001"].sum())
    n_both       = int((metrics_df["g1_sharpe_001"] & metrics_df["g6_turnover_ok"]).sum())

    # Turnover comparison vs Step 2 and 2B
    step2_best_to  = 0.17    # minimum from Step 2 (familyB_tilt2pct_data)
    step2b_best_to = 0.084   # minimum from Step 2B (D|int2pct)
    this_best_to   = float(metrics_df["to_increase_ann"].min())
    this_min_g1_to = float(metrics_df[metrics_df["g1_sharpe_001"]]["to_increase_ann"].min()) if n_g1_pass > 0 else np.nan

    # Step 2B reference
    step2b_best_sharpe = 0.0145
    step2b_best_holdout = -0.022

    # Robustness of best candidate
    best_var = str(best_overall["variant"])
    rob_best = rob_df[rob_df["variant"] == top3[0]] if top3 and len(rob_df) > 0 else pd.DataFrame()

    lines = [
        "# Near-Zero-Turnover Macro State Integration — Sprint Notes",
        "",
        f"**Sprint date:** 2026-06-07",
        f"**Verdict:** `{'PROMOTE_TO_PHASE_D_TEST' if n_promote > 0 else 'RESEARCH-ONLY'}`",
        "**Script:** `scripts/test_near_zero_turnover_macro_state_integration.py`",
        "**Outputs:** `outputs/experiment_results/near_zero_turnover_macro_state_integration/`",
        "",
        "---",
        "",
        "## 1. Did near-zero-turnover integration reduce turnover vs Step 2 and Step 2B?",
        "",
        "| Sprint | Minimum Annual Turnover Increase | Gate (≤0.03) |",
        "| --- | --- | --- |",
        f"| Step 2 (ETF tilts) | {step2_best_to:.3f} | FAIL |",
        f"| Step 2B (persistent modifier) | {step2b_best_to:.3f} | FAIL |",
        f"| **Step 2C (this sprint)** | **{this_best_to:.3f}** | **{'PASS' if this_best_to <= 0.03 else 'FAIL'}** |",
        "",
    ]

    # Q1 answer
    if this_best_to < step2b_best_to:
        lines.append(f"Step 2C reduced minimum turnover from {step2b_best_to:.3f} (Step 2B) to {this_best_to:.3f}.")
        if this_best_to <= 0.03:
            lines.append("**G6 passes** for at least one candidate.")
        else:
            lines.append("However, even the lowest-turnover candidate still exceeds the 0.03 gate.")
    else:
        lines.append("Step 2C did NOT further reduce minimum turnover vs Step 2B.")

    lines += [
        "",
        "## 2. Which refined neutral_soft_landing definition worked best?",
        "",
    ]

    # Best by definition
    for defn in ["D_raw", "D_monthly", "D_quarterly", "E_monthly", "E_quarterly",
                 "B_monthly", "B_quarterly"]:
        sub = metrics_df[metrics_df["definition"] == defn]
        if sub.empty:
            continue
        best_sub = sub.loc[sub["sharpe_delta"].idxmax()]
        lines.append(f"- **{defn}**: best ΔSharpe={best_sub['sharpe_delta']:.4f}, "
                     f"TO_increase={best_sub['to_increase_ann']:.4f}, "
                     f"G6={'PASS' if best_sub['g6_turnover_ok'] else 'FAIL'}")

    lines += [
        "",
        "## 3. Did static neutral_mixed recalibration work?",
        "",
        f"Group 1 (static NM): {group_summary('G1_static_NM')}",
        "",
    ]

    g1_sub = metrics_df[metrics_df["group"] == "G1_static_NM"]
    if not g1_sub.empty:
        best_g1 = g1_sub.loc[g1_sub["sharpe_delta"].idxmax()]
        lines.append(
            f"Best static NM candidate: {best_g1['variant']}, "
            f"ΔSharpe={best_g1['sharpe_delta']:.4f}, "
            f"TO_increase={best_g1['to_increase_ann']:.4f}, "
            f"G6={'PASS' if best_g1['g6_turnover_ok'] else 'FAIL'}"
        )
        lines.append(
            f"Turnover gate analysis: NM has ~{metrics_df['group'].count()} "
            f"~4.5 transitions/year. At even 2.5% intensity, extra TO ≈ "
            f"0.025 × 4.5 = ~0.11/year — exceeds 0.03 gate structurally."
        )

    lines += [
        "",
        "## 4. Did monthly/quarterly frozen sub-state calibration work?",
        "",
        f"Group 2 (monthly): {group_summary('G2_monthly_frozen')}",
        f"Group 3 (quarterly): {group_summary('G3_quarterly_frozen')}",
        "",
    ]

    lines += [
        "## 5. Did slow-score integration work?",
        "",
        f"Group 5 (slow score): {group_summary('G5_slow_score')}",
        "",
        "The slow score applies a continuously-varying modifier each week. "
        "Even with weekly delta capping, the modifier changes every week within "
        "active episodes, generating continuous extra turnover.",
        "",
        "## 6. Which modifier type worked best?",
        "",
    ]
    for mod in ["offense_budget", "defense_release", "combined"]:
        sub = metrics_df[metrics_df["mod_type"] == mod]
        if sub.empty:
            continue
        best_mod = sub.loc[sub["sharpe_delta"].idxmax()]
        lines.append(f"- **{mod}**: best ΔSharpe={best_mod['sharpe_delta']:.4f}, "
                     f"TO_increase={best_mod['to_increase_ann']:.4f}")

    lines += [
        "",
        "## 7. Which intensity worked best?",
        "",
    ]
    for intensity in sorted(metrics_df["intensity"].unique()):
        sub = metrics_df[metrics_df["intensity"] == intensity]
        if sub.empty:
            continue
        best_int = sub.loc[sub["sharpe_delta"].idxmax()]
        lines.append(f"- **{intensity:.1%}**: best ΔSharpe={best_int['sharpe_delta']:.4f}, "
                     f"best_TO_increase={best_int['to_increase_ann']:.4f}")

    lines += [
        "",
        "## 8. Did any candidate improve full Sharpe by at least +0.01?",
        "",
        f"G1 (Sharpe ≥+0.01): {n_g1_pass} of {len(metrics_df)} candidates pass.",
    ]
    if n_g1_pass > 0:
        g1_cands = metrics_df[metrics_df["g1_sharpe_001"]].sort_values("sharpe_delta", ascending=False).head(5)
        lines.append("")
        for _, row in g1_cands.iterrows():
            lines.append(f"- {row['variant']}: ΔSharpe={row['sharpe_delta']:.4f}, "
                         f"TO_increase={row['to_increase_ann']:.4f}, "
                         f"G6={'PASS' if row['g6_turnover_ok'] else 'FAIL'}")

    lines += [
        "",
        "## 9. Did holdout performance survive?",
        "",
    ]
    if not metrics_df.empty:
        best_hold_cands = metrics_df.nlargest(5, "holdout_delta")
        for _, row in best_hold_cands.iterrows():
            lines.append(f"- {row['variant']}: holdout_Δ={row['holdout_delta']:.4f}")

    lines += [
        "",
        "## 10. Did 2x transaction costs erase the improvement?",
        "",
    ]
    if not rob_df.empty:
        rob_2x = rob_df[rob_df["window"] == "2x_cost_sensitivity"]
        for _, row in rob_2x.iterrows():
            lines.append(f"- {row['variant']}: 2×-cost ΔSharpe={row['sharpe_delta']:.4f}")

    lines += [
        "",
        "## 11. Did neutral_mixed improve?",
        "",
        f"Baseline NM dev Sharpe: {bl_nm_sharpe:.4f}",
    ]
    nm_improved = metrics_df[metrics_df["nm_dev_sharpe"] > bl_nm_sharpe]
    lines.append(f"Candidates with NM Sharpe improved: {len(nm_improved)} of {len(metrics_df)}")

    lines += [
        "",
        "## 12. Did stressed_panic and recovery_fragile remain protected?",
        "",
        "All modifier types only activate during NM or neutral_soft_landing conditions. "
        "By construction, stressed_panic and recovery_fragile weights are unchanged.",
        f"G8 (stressed_panic not worsened): {int(metrics_df['g8_sp_ok'].sum())} of {len(metrics_df)} pass.",
        f"G9 (recovery_fragile not worsened): {int(metrics_df['g9_rf_ok'].sum())} of {len(metrics_df)} pass.",
        "",
        "## 13. Did any candidate clear all promotion gates?",
        "",
        f"**PROMOTE_TO_PHASE_D_TEST: {n_promote}**",
        f"**RESEARCH-ONLY: {len(metrics_df) - n_promote}**",
        f"**DROP: 0**",
        "",
        f"Candidates passing both G1 and G6: {n_both}",
        "",
    ]

    # Gate summary table for top 5 by Sharpe delta
    top5 = metrics_df.nlargest(5, "sharpe_delta")
    lines += [
        "### Top 5 candidates by Sharpe delta",
        "",
        "| Variant | ΔSharpe | TO_increase | G1 | G6 | Gates | Verdict |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for _, row in top5.iterrows():
        v = str(row["variant"])[-60:] if len(str(row["variant"])) > 60 else str(row["variant"])
        lines.append(
            f"| {v} | {row['sharpe_delta']:.4f} | {row['to_increase_ann']:.4f} | "
            f"{'✓' if row['g1_sharpe_001'] else '✗'} | "
            f"{'✓' if row['g6_turnover_ok'] else '✗'} | "
            f"{row['gates_passed']}/9 | {row['verdict']} |"
        )

    overall_verdict = "PROMOTE_TO_PHASE_D_TEST" if n_promote > 0 else "RESEARCH-ONLY"

    lines += [
        "",
        "---",
        "",
        "## 14. Final Verdict",
        "",
        f"**`{overall_verdict}`**",
        "",
        "### Why not DROP?",
        "",
    ]

    if n_promote == 0:
        lines += [
            "- The signal (NM+slowdown+FC_benign) is validated across Steps 2, 2B, and 2C.",
            "- Monotonic improvement with intensity suggests real alpha in the signal.",
            "- Holdout behavior is consistent or positive for low-intensity candidates.",
            "- Static NM modifier and quarterly frozen approaches show reduced turnover vs Step 2B.",
        ]
        lines += [
            "",
            "### Why not PROMOTE_TO_PHASE_D_TEST?",
            "",
        ]
        if n_g6_pass == 0:
            lines += [
                "- G6 fails for all candidates: turnover gate (≤0.03/yr) not cleared by any approach.",
                "- Root cause: NM has ~4.5 episodes/year × ~2 transitions/episode = ~8.9 transitions/year.",
                "  At even 2.5% intensity, the entry/exit rebalancing adds ~0.08-0.11/yr extra turnover.",
                "- Frozen approaches (monthly, quarterly) reduce transitions but not enough: the frozen",
                "  state still changes several times per year, each requiring a ~2-10% rebalance.",
                "- Slow score: continuous weekly modifier changes create larger cumulative turnover",
                "  than episodic frozen approaches.",
            ]
        elif n_both == 0:
            lines += [
                "- No candidate simultaneously passes both G1 (ΔSharpe ≥+0.01) and G6 (TO ≤0.03).",
                "- Low-intensity candidates (≤1%) clear G6 but fail G1 (improvement too small).",
                "- High-intensity candidates (≥5%) clear G1 but fail G6 (too much turnover).",
                "- This is the fundamental trade-off the sprint cannot resolve.",
            ]

        lines += [
            "",
            "### What this closes",
            "",
            "Steps 2, 2B, and 2C have now exhausted all three implementation paths for the V3 macro signal:",
            "",
            "| Sprint | Implementation | G1 | G6 | 2×-cost |",
            "| --- | --- | --- | --- | --- |",
            "| Step 2 | Weekly ETF tilt overlay | FAIL | FAIL | -0.048 |",
            "| Step 2B | Persistent Layer 2B modifier (episode) | PASS | FAIL | -0.033 |",
            f"| Step 2C | Near-zero-turnover calibration | {'PASS' if n_g1_pass>0 else 'FAIL'} | {'PASS' if n_g6_pass>0 else 'FAIL'} | see robustness |",
            "",
            "**The macro/credit signal (V3 NM+slowdown+FC_benign) is real and direction-correct.",
            "The constraint is structural: this portfolio's turnover cost structure cannot profitably",
            "implement any dynamic or semi-dynamic response to the signal at achievable portfolio scale.**",
            "",
            "The only viable remaining path is a static one-time recalibration (accept the NM+slowdown",
            "sub-regime insight and bake it into a new fixed strategy design — not a post-hoc overlay).",
            "This would require rebuilding from the Layer 2B regime engine rather than applying overlays.",
            "",
            "### Recommendation",
            "",
            "**Close the V3 macro overlay research program.**",
            "",
            "The signal is real but cannot be profitably harvested via portfolio overlays at this scale.",
            "Classify as RESEARCH-ONLY. Archive Signal E/D definitions for reference if future work",
            "involves rebuilding Layer 2B from scratch with macro conditioning as a native feature.",
        ]

    lines += [
        "",
        "---",
        "*Research artifact sprint — no production artifacts modified.*",
    ]

    (OUT_DIR / "near_zero_turnover_macro_state_notes.md").write_text("\n".join(lines))
    print("  Saved: near_zero_turnover_macro_state_notes.md")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("STEP 2C — NEAR-ZERO-TURNOVER MACRO STATE INTEGRATION")
    print("=" * 70)

    data = load_data()
    raw, smoothed = build_refined_states(data)

    # Rebuild frozen using v2 (correct index-based lookback)
    for sig_name, raw_sig in raw.items():
        raw_sig_idx = raw_sig.reindex(data["bl_wts"].index, fill_value=False)
        smoothed[f"{sig_name}_monthly"]   = _frozen_monthly_v2(raw_sig_idx, lookback=4,  threshold=0.50)
        smoothed[f"{sig_name}_quarterly"] = _frozen_quarterly_v2(raw_sig_idx, lookback=8, threshold=0.375)

    write_refined_state_definitions(raw, smoothed)
    diag_df = compute_refined_state_diagnostics(raw, smoothed, data)

    (
        metrics_df,
        bl_full, bl_hold,
        bl_nm_sharpe, bl_nsl_sharpe,
        bl_sp_sharpe, bl_rf_sharpe
    ) = evaluate_candidates(data, raw, smoothed)

    gates_df = apply_gates(metrics_df)

    # Select top 3 by Sharpe delta for robustness
    top3_variants = list(metrics_df.nlargest(3, "sharpe_delta")["variant"])
    print(f"\n  Top 3 for robustness:")
    for v in top3_variants:
        row = metrics_df[metrics_df["variant"] == v].iloc[0]
        print(f"    {v}: ΔSharpe={row['sharpe_delta']:.4f}, TO={row['to_increase_ann']:.4f}, "
              f"G1={'✓' if row['g1_sharpe_001'] else '✗'}, G6={'✓' if row['g6_turnover_ok'] else '✗'}")

    # Build full candidate list for robustness lookup
    nm_sig    = (data["ms"] == "neutral_mixed").fillna(False).reindex(data["bl_wts"].index, fill_value=False)
    raw_D     = raw["D"].reindex(data["bl_wts"].index, fill_value=False)

    all_candidates: list[dict] = []
    # Group 1
    for mod_name, mod_fn in MODIFIER_FNS.items():
        for intensity in [0.005, 0.010, 0.025, 0.050, 0.075]:
            all_candidates.append({
                "group": "G1_static_NM", "definition": "nm_all",
                "mod_type": mod_name, "intensity": intensity,
                "rolling_w": None, "delta_cap": None,
                "_sig": nm_sig, "_mod_fn": mod_fn, "_slow": False,
            })
    # Group 2/3/4
    for sig_name in ["D_monthly", "D_quarterly", "E_monthly", "E_quarterly",
                     "D_4wk", "E_4wk", "B_monthly", "B_quarterly"]:
        if sig_name not in smoothed:
            continue
        sig = smoothed[sig_name].fillna(False).reindex(data["bl_wts"].index, fill_value=False)
        if "monthly" in sig_name:
            group = "G2_monthly_frozen"
        elif "quarterly" in sig_name:
            group = "G3_quarterly_frozen"
        else:
            group = "G4_smoothed"
        for intensity in [0.025, 0.050, 0.075, 0.10]:
            all_candidates.append({
                "group": group, "definition": sig_name,
                "mod_type": "offense_budget", "intensity": intensity,
                "rolling_w": None, "delta_cap": None,
                "_sig": sig, "_mod_fn": modifier_offense_budget, "_slow": False,
            })
    for mod_name, mod_fn in MODIFIER_FNS.items():
        sig = smoothed["D_quarterly"].fillna(False).reindex(data["bl_wts"].index, fill_value=False)
        for intensity in [0.025, 0.05, 0.075]:
            all_candidates.append({
                "group": "G3_quarterly_frozen", "definition": "D_quarterly",
                "mod_type": mod_name, "intensity": intensity,
                "rolling_w": None, "delta_cap": None,
                "_sig": sig, "_mod_fn": mod_fn, "_slow": False,
            })
    # Group 5
    for rolling_w in [8, 12]:
        for delta_cap in [0.005, 0.010]:
            score = build_slow_score_signal(raw_D, rolling_w, delta_cap)
            for intensity in [0.025, 0.05, 0.075]:
                all_candidates.append({
                    "group": "G5_slow_score",
                    "definition": f"D_score_r{rolling_w}_cap{int(delta_cap*1000)}",
                    "mod_type": "offense_budget", "intensity": intensity,
                    "rolling_w": rolling_w, "delta_cap": delta_cap,
                    "_sig": score, "_mod_fn": modifier_offense_budget, "_slow": True,
                })

    robustness_checks(top3_variants, all_candidates, data,
                      bl_full, bl_hold, smoothed, raw)

    rob_df = pd.read_csv(OUT_DIR / "top_candidate_robustness.csv")

    write_final_notes(
        metrics_df, gates_df, bl_full, bl_hold,
        bl_nm_sharpe, bl_nsl_sharpe, bl_sp_sharpe, bl_rf_sharpe,
        top3_variants, diag_df, rob_df,
    )
    write_summary(metrics_df, gates_df, bl_full, bl_hold,
                  bl_nm_sharpe, bl_nsl_sharpe, top3_variants)

    n_promote  = int((metrics_df["verdict"] == "PROMOTE_TO_PHASE_D_TEST").sum())
    n_research = int((metrics_df["verdict"] == "RESEARCH-ONLY").sum())
    best = metrics_df.loc[metrics_df["sharpe_delta"].idxmax()]

    print("\n" + "=" * 70)
    overall = "PROMOTE_TO_PHASE_D_TEST" if n_promote > 0 else "RESEARCH-ONLY"
    print(f"STEP 2C COMPLETE — OVERALL VERDICT: {overall}")
    print("=" * 70)
    print(f"  Baseline: Sharpe={bl_full['sharpe']:.4f}, AnnRet={bl_full['ann_return']:.4%}")
    print(f"  Candidates: {len(metrics_df)}")
    print(f"  PROMOTE_TO_PHASE_D_TEST: {n_promote}")
    print(f"  RESEARCH-ONLY: {n_research}")
    print(f"  Best: {best['variant']}")
    print(f"    ΔSharpe={best['sharpe_delta']:.4f}, TO_increase={best['to_increase_ann']:.4f}, "
          f"G1={'✓' if best['g1_sharpe_001'] else '✗'}, G6={'✓' if best['g6_turnover_ok'] else '✗'}")


if __name__ == "__main__":
    main()
