"""Phase W — Sleeve-Panel Revisit / Opportunity-Set Upgrade.

After the closure of the allocator / trust / regime / holdings-blend
branch (Phases Q→V), the project moves back upstream to Layer 2. The
diagnostic conclusion of that branch was clear: every Phase D gate could
be moved in one dimension by some allocator, but no allocator could
align all six gates simultaneously, because production's holdout edge
lives partly in *specific weekly ETF holdings* the existing sleeve panel
does not express as a clean callable role.

Phase W builds new sleeves designed to fill specific role gaps the
current six-sleeve active panel leaves open:

  W1 — `composite_structural_defense_sleeve`
    A causal, rules-based defensive sleeve that explicitly captures
    production's adverse-tape positioning (GLD / TLT / HYG / DBA / BIL /
    LQD) as a named, callable strategy module. Activates by stress
    score, market drawdown, breadth deterioration, and risk-off
    correlation; otherwise sits in BIL. Inverse-vol-weighted within the
    risk-off basket with a stress-keyed leverage profile across regimes.

  W2 — `composite_recovery_confirmed_offense_sleeve`
    A clean recovery-specific offensive sleeve. Silent in calm / chop /
    stress; decisive only in `recovery_confirmed` and `recovery_fragile`
    states with breadth-confirmed momentum. Picks top equity ETFs by
    breadth-confirmed multi-horizon momentum, plus HYG (recovery beta).
    Distinct from `composite_healthier_recovery_specialist`, which is
    also active in calm.

  W3 — `composite_calm_carry_sleeve`
    A calm-trend / carry-style sleeve, distinct from
    `composite_calm_trend_specialist`. Activates only in `calm_trend`
    with positive market trend; uses signal_carry + signal_quality to
    pick a top-quality basket (LQD / VTV / XLU / XLP / EFA / GLD).
    Lower vol, less correlated with momentum-heavy sleeves.

  W4 — `composite_macro_trend_diversifier_sleeve`
    A managed-futures-style cross-asset trend sleeve. Long/flat per
    asset class on positive multi-horizon trend; equal-weighted active
    legs scaled by inverse vol. Designed to pick up commodity / FX /
    rates trends the existing offensive sleeves miss. Distinct from
    sector-factor trend.

Causal / walk-forward safety:
  - Inputs are tradable signal columns and lagged market-state /
    breadth / drawdown features.
  - All weights at week t consume features observed up to t-1.
  - No retraining; rules-based weights only.

Outputs:
  data/03_layer2a_strategy_logic/
    strategy_positions_{sleeve}.csv (4 new files)
    strategy_returns_{sleeve}.csv   (4 new files)
    phase_w_sleeve_summary.csv
    phase_w_sleeve_state_summary.csv
    phase_w_sleeve_holdout_summary.csv
    phase_w_sleeve_correlation.csv
    phase_w_panel_blend_summary.csv
    phase_w_panel_state_winner_summary.csv
    phase_w_panel_separability_summary.csv
    phase_w_diagnostics_protocol.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_HUB_DIR = ROOT / "data" / "01_data_hub"
LAYER1_DIR = ROOT / "data" / "02_layer1_signals"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"

ACTIVE_PANEL = [
    "dual_momentum_topn",
    "composite_calm_trend_specialist",
    "composite_healthier_recovery_specialist",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

NEW_SLEEVES = [
    "composite_structural_defense_sleeve",
    "composite_recovery_confirmed_offense_sleeve",
    "composite_calm_carry_sleeve",
    "composite_macro_trend_diversifier_sleeve",
]

DEFAULT_COST_BPS = 10
HOLDOUT_WEEKS = 139  # consistent with Phase D / Phase U

EPS = 1e-9


# --------------------------------------------------------------------------
#                              data loading
# --------------------------------------------------------------------------

def load_weekly_prices() -> pd.DataFrame:
    return pd.read_csv(DATA_HUB_DIR / "weekly_prices.csv", index_col=0, parse_dates=True).sort_index()


def load_weekly_returns() -> pd.DataFrame:
    return pd.read_csv(DATA_HUB_DIR / "weekly_returns.csv", index_col=0, parse_dates=True).sort_index()


def load_market_state() -> pd.DataFrame:
    return pd.read_csv(LAYER2B_DIR / "market_state_history.csv", index_col=0, parse_dates=True).sort_index()


def load_signal_long(name: str) -> pd.DataFrame:
    df = pd.read_csv(LAYER1_DIR / f"{name}.csv", parse_dates=["Date"])
    return df


def signal_pivot(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    pivoted = (
        df.pivot_table(index="Date", columns="Ticker", values=value_col, aggfunc="first")
        .sort_index()
    )
    return pivoted


def reindex_to(weeks: pd.DatetimeIndex, frame: pd.DataFrame, fill_value: float = 0.0) -> pd.DataFrame:
    return frame.reindex(weeks).ffill().fillna(fill_value)


# --------------------------------------------------------------------------
#                              sleeve builders
# --------------------------------------------------------------------------

def normalize_to_one(weights: pd.Series) -> pd.Series:
    s = weights.clip(lower=0.0)
    total = s.sum()
    if total <= EPS:
        return s
    return s / total


def inverse_vol_weights(returns_window: pd.DataFrame) -> pd.Series:
    vols = returns_window.std(ddof=0)
    inv = 1.0 / (vols + EPS)
    inv = inv.replace([np.inf, -np.inf], 0.0).fillna(0.0)
    if inv.sum() <= EPS:
        return pd.Series(0.0, index=returns_window.columns)
    return inv / inv.sum()


def build_w1_structural_defense(prices: pd.DataFrame, returns: pd.DataFrame, market_state: pd.DataFrame) -> pd.DataFrame:
    """W1 — structural defensive sleeve.

    Builds an explicit causal defensive sleeve over GLD / TLT / HYG / LQD / DBA / BIL.

    Activation logic (all features observed at t-1):
      stress_score = clip(0..1) of:
        0.50 * (recent_stress_26w)
        + 0.30 * |market_drawdown|
        + 0.20 * max(avg_corr_risk_off_z, 0) / 3.0
      defensive_weight (total non-BIL) = clip(stress_score, 0.10, 0.85)
      cash_weight = 1 - defensive_weight

    Within the defensive basket:
      - state-conditioned base mix:
        stressed_panic     -> {GLD 0.30, TLT 0.30, HYG 0.10, LQD 0.10, DBA 0.10, BIL extra 0.10}
        recovery_fragile   -> {GLD 0.25, TLT 0.20, HYG 0.20, LQD 0.20, DBA 0.10, BIL extra 0.05}
        recovery_confirmed -> {GLD 0.25, TLT 0.10, HYG 0.30, LQD 0.20, DBA 0.10, BIL extra 0.05}
        neutral_mixed      -> {GLD 0.30, TLT 0.20, HYG 0.15, LQD 0.20, DBA 0.10, BIL extra 0.05}
        calm_trend         -> {GLD 0.20, TLT 0.10, HYG 0.10, LQD 0.30, DBA 0.10, BIL extra 0.20}
      - then inverse-vol scaled within the {GLD, TLT, HYG, LQD, DBA} subset using the
        trailing 26-week realized vol observed at t-1, with a 0.5 shrinkage toward base.
      - normalized to 1.0 of defensive_weight; remainder -> BIL.

    No model fitting, no walk-forward retraining. Pure rules.
    """
    state_base_mix = {
        "stressed_panic":     {"GLD": 0.30, "TLT": 0.30, "HYG": 0.10, "LQD": 0.10, "DBA": 0.10, "extra_bil": 0.10},
        "recovery_fragile":   {"GLD": 0.25, "TLT": 0.20, "HYG": 0.20, "LQD": 0.20, "DBA": 0.10, "extra_bil": 0.05},
        "recovery_confirmed": {"GLD": 0.25, "TLT": 0.10, "HYG": 0.30, "LQD": 0.20, "DBA": 0.10, "extra_bil": 0.05},
        "neutral_mixed":      {"GLD": 0.30, "TLT": 0.20, "HYG": 0.15, "LQD": 0.20, "DBA": 0.10, "extra_bil": 0.05},
        "calm_trend":         {"GLD": 0.20, "TLT": 0.10, "HYG": 0.10, "LQD": 0.30, "DBA": 0.10, "extra_bil": 0.20},
    }
    risky_set = ["GLD", "TLT", "HYG", "LQD", "DBA"]
    full_set = risky_set + ["BIL"]

    weeks = prices.index
    weights = pd.DataFrame(0.0, index=weeks, columns=full_set)

    # 1-week-lagged features
    ms_lag = market_state.shift(1)
    ret_for_vol = returns.shift(1)
    rolling_vol = ret_for_vol.rolling(window=26, min_periods=8).std(ddof=0)

    for date in weeks:
        if date not in ms_lag.index or pd.isna(ms_lag.loc[date, "market_state"]):
            weights.loc[date, "BIL"] = 1.0
            continue
        state = str(ms_lag.loc[date, "market_state"])
        base = state_base_mix.get(state, state_base_mix["neutral_mixed"])

        # stress score in [0,1]
        rs = float(ms_lag.loc[date, "recent_stress_26w"]) if "recent_stress_26w" in ms_lag.columns else 0.0
        dd = float(ms_lag.loc[date, "market_drawdown"]) if "market_drawdown" in ms_lag.columns else 0.0
        rc = float(ms_lag.loc[date, "avg_corr_risk_off_z"]) if "avg_corr_risk_off_z" in ms_lag.columns else 0.0
        stress = 0.50 * rs + 0.30 * abs(dd) + 0.20 * max(rc, 0.0) / 3.0
        stress = float(np.clip(stress, 0.0, 1.0))
        defensive_weight = float(np.clip(stress, 0.10, 0.85))

        # base mix
        base_mix = pd.Series({k: v for k, v in base.items() if k in risky_set}, index=risky_set).fillna(0.0)
        base_mix = base_mix / max(base_mix.sum(), EPS)

        # inverse-vol shrinkage within the risky set
        if date in rolling_vol.index:
            vol_row = rolling_vol.loc[date].reindex(risky_set).fillna(0.0)
            iv = inverse_vol_weights(pd.DataFrame({c: [vol_row[c]] for c in risky_set}, index=[0]))
            iv = iv.reindex(risky_set).fillna(0.0)
        else:
            iv = pd.Series(1.0 / len(risky_set), index=risky_set)
        if iv.sum() > EPS:
            iv = iv / iv.sum()
        else:
            iv = pd.Series(1.0 / len(risky_set), index=risky_set)
        mix = 0.5 * base_mix + 0.5 * iv

        # apply defensive vs cash split
        risky_weights = mix * defensive_weight
        bil_weight = 1.0 - defensive_weight + base.get("extra_bil", 0.0) * defensive_weight
        # renormalize to sum to 1.0
        total_alloc = risky_weights.sum() + bil_weight
        risky_weights = risky_weights / max(total_alloc, EPS)
        bil_weight = bil_weight / max(total_alloc, EPS)

        for t in risky_set:
            weights.loc[date, t] = float(risky_weights[t])
        weights.loc[date, "BIL"] = float(bil_weight)

    # Final renormalization for floating drift safety
    s = weights.sum(axis=1).replace(0.0, np.nan)
    weights = weights.div(s, axis=0).fillna(0.0)
    return weights


def build_w2_recovery_offense(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    market_state: pd.DataFrame,
    breadth_score: pd.DataFrame,
    multi_mom_score: pd.DataFrame,
) -> pd.DataFrame:
    """W2 — clean recovery-confirmed offense sleeve.

    Activation:
      Active iff state == 'recovery_confirmed' or
      (state == 'recovery_fragile' and breadth_change_4w > 0).
      Otherwise 100% BIL.

    Active selection (top-N=4):
      Universe = {SPY, QQQ, IWM, EFA, EEM, VWO, VNQ, HYG} for recovery beta.
      Score per ETF = breadth_confirmed_momentum_score_tradable + multi_mom_equal_score_tradable.
      Pick top 4 with positive score; equal-weight among picks.
      80% to top-4 basket, 20% to HYG (recovery beta floor).
      If fewer than 2 positive-score names, fall back to {SPY 0.25, EFA 0.25, HYG 0.25, BIL 0.25}.

    All features 1-week lagged.
    """
    universe = ["SPY", "QQQ", "IWM", "EFA", "EEM", "VWO", "VNQ", "HYG"]
    full_set = list(dict.fromkeys(universe + ["BIL"]))

    weeks = prices.index
    weights = pd.DataFrame(0.0, index=weeks, columns=full_set)

    ms_lag = market_state.shift(1)
    breadth_lag = breadth_score.shift(1)
    multi_mom_lag = multi_mom_score.shift(1)

    for date in weeks:
        if date not in ms_lag.index or pd.isna(ms_lag.loc[date, "market_state"]):
            weights.loc[date, "BIL"] = 1.0
            continue
        state = str(ms_lag.loc[date, "market_state"])
        breadth_4w = float(ms_lag.loc[date, "breadth_change_4w"]) if "breadth_change_4w" in ms_lag.columns else 0.0
        active = (state == "recovery_confirmed") or (state == "recovery_fragile" and breadth_4w > 0)
        if not active:
            weights.loc[date, "BIL"] = 1.0
            continue

        # combined recovery score
        b_row = breadth_lag.reindex(columns=universe).loc[date] if date in breadth_lag.index else pd.Series(0.0, index=universe)
        m_row = multi_mom_lag.reindex(columns=universe).loc[date] if date in multi_mom_lag.index else pd.Series(0.0, index=universe)
        score = b_row.fillna(0.0) + m_row.fillna(0.0)
        positives = score[score > 0]
        if len(positives) >= 2:
            top = positives.sort_values(ascending=False).head(4)
            equal_w = 0.80 / len(top)
            for t in top.index:
                weights.loc[date, t] = float(equal_w)
            # 20% HYG floor
            existing_hyg = float(weights.loc[date, "HYG"])
            weights.loc[date, "HYG"] = float(existing_hyg + 0.20)
        else:
            weights.loc[date, "SPY"] = 0.25
            weights.loc[date, "EFA"] = 0.25
            weights.loc[date, "HYG"] = 0.25
            weights.loc[date, "BIL"] = 0.25

    s = weights.sum(axis=1).replace(0.0, np.nan)
    weights = weights.div(s, axis=0).fillna(0.0)
    return weights


def build_w3_calm_carry(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    market_state: pd.DataFrame,
    carry_score: pd.DataFrame,
    quality_score: pd.DataFrame,
) -> pd.DataFrame:
    """W3 — calm-trend carry / quality sleeve.

    Activation:
      Active iff state == 'calm_trend' AND market_trend_positive == True.
      Otherwise 100% BIL.

    Active selection (top-N=5):
      Universe = {LQD, HYG, VTV, XLU, XLP, EFA, GLD, IEF, TIP, MBB}.
      Score = carry_score_tradable + 0.5 * quality_score_tradable (lagged).
      Top 5 by score, equal-weighted.
      Targets a low-vol carry/quality basket distinct from momentum sleeves.

    All features 1-week lagged.
    """
    universe = ["LQD", "HYG", "VTV", "XLU", "XLP", "EFA", "GLD", "IEF", "TIP", "MBB"]
    full_set = list(dict.fromkeys(universe + ["BIL"]))

    weeks = prices.index
    weights = pd.DataFrame(0.0, index=weeks, columns=full_set)

    ms_lag = market_state.shift(1)
    carry_lag = carry_score.shift(1)
    quality_lag = quality_score.shift(1)

    for date in weeks:
        if date not in ms_lag.index or pd.isna(ms_lag.loc[date, "market_state"]):
            weights.loc[date, "BIL"] = 1.0
            continue
        state = str(ms_lag.loc[date, "market_state"])
        trend_positive = bool(ms_lag.loc[date, "market_trend_positive"]) if "market_trend_positive" in ms_lag.columns else False
        active = (state == "calm_trend" and trend_positive)
        if not active:
            weights.loc[date, "BIL"] = 1.0
            continue

        c_row = carry_lag.reindex(columns=universe).loc[date] if date in carry_lag.index else pd.Series(0.0, index=universe)
        q_row = quality_lag.reindex(columns=universe).loc[date] if date in quality_lag.index else pd.Series(0.0, index=universe)
        score = c_row.fillna(0.0) + 0.5 * q_row.fillna(0.0)
        positives = score[score > 0]
        if len(positives) >= 3:
            top = positives.sort_values(ascending=False).head(5)
            equal_w = 1.0 / len(top)
            for t in top.index:
                weights.loc[date, t] = float(equal_w)
        else:
            for t in ["LQD", "VTV", "XLU", "XLP", "GLD"]:
                weights.loc[date, t] = 0.20

    s = weights.sum(axis=1).replace(0.0, np.nan)
    weights = weights.div(s, axis=0).fillna(0.0)
    return weights


def build_w4_macro_trend(
    prices: pd.DataFrame,
    returns: pd.DataFrame,
    market_state: pd.DataFrame,
    tsmom_score: pd.DataFrame,
) -> pd.DataFrame:
    """W4 — managed-futures-style cross-asset trend diversifier.

    Universe spans equities/rates/commodities/FX:
      {SPY, EFA, VWO, TLT, GLD, PDBC, DBA, USO, UUP}

    Logic:
      For each asset, long-only if tsmom_score_tradable > 0 (1-week lagged);
      otherwise that asset's weight goes to BIL.
      Active legs are inverse-vol scaled (26w trailing vol, lagged).
      Total active basket is normalized so the sum of |active legs| matches
      the long_share = clip(0.30 + 0.10 * num_positive, 0.30, 0.85). Remaining
      weight to BIL.

    Strict cross-asset trend, distinct from sector/factor trend.
    """
    universe = ["SPY", "EFA", "VWO", "TLT", "GLD", "PDBC", "DBA", "USO", "UUP"]
    full_set = list(dict.fromkeys(universe + ["BIL"]))

    weeks = prices.index
    weights = pd.DataFrame(0.0, index=weeks, columns=full_set)

    ts_lag = tsmom_score.shift(1)
    ret_lag = returns.shift(1)
    rolling_vol = ret_lag.rolling(window=26, min_periods=8).std(ddof=0)

    for date in weeks:
        if date not in ts_lag.index:
            weights.loc[date, "BIL"] = 1.0
            continue
        scores = ts_lag.reindex(columns=universe).loc[date].fillna(0.0)
        pos = scores[scores > 0]
        if len(pos) == 0:
            weights.loc[date, "BIL"] = 1.0
            continue

        if date in rolling_vol.index:
            vols = rolling_vol.loc[date].reindex(pos.index).fillna(0.0)
        else:
            vols = pd.Series(0.0, index=pos.index)
        inv = 1.0 / (vols + EPS)
        inv = inv.replace([np.inf, -np.inf], 0.0).fillna(0.0)
        if inv.sum() <= EPS:
            inv = pd.Series(1.0 / len(pos), index=pos.index)
        else:
            inv = inv / inv.sum()

        long_share = float(np.clip(0.30 + 0.10 * len(pos), 0.30, 0.85))
        active = inv * long_share
        for t in active.index:
            weights.loc[date, t] = float(active[t])
        weights.loc[date, "BIL"] = 1.0 - long_share

    s = weights.sum(axis=1).replace(0.0, np.nan)
    weights = weights.div(s, axis=0).fillna(0.0)
    return weights


# --------------------------------------------------------------------------
#                          backtest helpers
# --------------------------------------------------------------------------

def compute_strategy_returns(
    weights: pd.DataFrame, returns: pd.DataFrame, cost_bps: float = DEFAULT_COST_BPS
) -> pd.DataFrame:
    common_idx = weights.index.intersection(returns.index)
    aligned_w = weights.loc[common_idx].fillna(0.0)
    aligned_r = returns.loc[common_idx].reindex(columns=aligned_w.columns).fillna(0.0)
    # gross return: weights at t * returns at t (weights already lag-applied)
    gross = (aligned_w.shift(1).fillna(0.0) * aligned_r).sum(axis=1)
    turnover = aligned_w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * (cost_bps / 10_000.0)
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame({
        "gross_return": gross,
        "net_return": net,
        "turnover": turnover,
        "cost": cost,
        "wealth": wealth,
        "drawdown": drawdown,
    })


def annualized_return(s: pd.Series) -> float:
    s = pd.Series(s, dtype=float).dropna()
    if s.empty:
        return float("nan")
    return float((1.0 + s).prod() ** (52 / len(s)) - 1.0)


def annualized_vol(s: pd.Series) -> float:
    s = pd.Series(s, dtype=float).dropna()
    if len(s) < 2:
        return float("nan")
    return float(s.std(ddof=1) * np.sqrt(52))


def max_drawdown(s: pd.Series) -> float:
    s = pd.Series(s, dtype=float).dropna()
    if s.empty:
        return float("nan")
    wealth = (1.0 + s).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar_5(s: pd.Series) -> float:
    s = pd.Series(s, dtype=float).dropna()
    if s.empty:
        return float("nan")
    cutoff = s.quantile(0.05)
    tail = s[s <= cutoff]
    if tail.empty:
        return float("nan")
    return float(tail.mean())


def calmar(s: pd.Series) -> float:
    ann = annualized_return(s)
    dd = max_drawdown(s)
    if dd == 0 or np.isnan(dd):
        return float("nan")
    return float(ann / abs(dd))


def metric_row(name: str, returns_series: pd.Series, weights: pd.DataFrame, turnover_series: pd.Series) -> dict:
    s = returns_series.dropna()
    return {
        "strategy_name": name,
        "ann_return": annualized_return(s),
        "ann_vol": annualized_vol(s),
        "sharpe": annualized_return(s) / annualized_vol(s) if annualized_vol(s) and not np.isnan(annualized_vol(s)) and annualized_vol(s) > 0 else float("nan"),
        "max_drawdown": max_drawdown(s),
        "calmar": calmar(s),
        "cvar_5": cvar_5(s),
        "turnover": float(turnover_series.dropna().mean()),
        "avg_bil": float(weights.get("BIL", pd.Series(0.0)).mean()) if "BIL" in weights.columns else 0.0,
        "observations": int(len(s)),
    }


def state_summary(name: str, returns_series: pd.Series, weights: pd.DataFrame, market_state: pd.Series) -> pd.DataFrame:
    df = pd.DataFrame({"net_return": returns_series, "market_state": market_state}).dropna()
    rows = []
    for state, sub in df.groupby("market_state"):
        s = sub["net_return"]
        bil = weights.get("BIL", pd.Series(0.0)).reindex(sub.index).mean() if "BIL" in weights.columns else 0.0
        # decompose offense/defense/cash via sleeve composition
        offense_assets = [c for c in weights.columns if c not in {"BIL", "GLD", "TLT", "LQD", "HYG", "DBA", "IEF", "TIP", "MBB", "SHY", "IAU"}]
        defense_assets = [c for c in weights.columns if c in {"GLD", "TLT", "LQD", "HYG", "DBA", "IEF", "TIP", "MBB", "SHY", "IAU"}]
        avg_offense = weights.reindex(sub.index)[offense_assets].sum(axis=1).mean() if offense_assets else 0.0
        avg_defense = weights.reindex(sub.index)[defense_assets].sum(axis=1).mean() if defense_assets else 0.0
        rows.append({
            "strategy_name": name,
            "market_state": state,
            "observations": int(len(s)),
            "ann_return_state": annualized_return(s),
            "ann_vol_state": annualized_vol(s),
            "sharpe_state": (annualized_return(s) / annualized_vol(s)) if annualized_vol(s) and annualized_vol(s) > 0 else float("nan"),
            "avg_bil_state": float(bil),
            "avg_offense_state": float(avg_offense),
            "avg_defense_state": float(avg_defense),
            "avg_cash_state": float(bil),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
#                       panel diagnostics
# --------------------------------------------------------------------------

def load_existing_sleeve_returns() -> pd.DataFrame:
    out = {}
    for s in ACTIVE_PANEL:
        df = pd.read_csv(LAYER2A_DIR / f"strategy_returns_{s}.csv", index_col=0, parse_dates=True).sort_index()
        out[s] = df["net_return"]
    return pd.DataFrame(out)


def correlation_matrix(returns_panel: pd.DataFrame) -> pd.DataFrame:
    return returns_panel.corr()


def panel_blend_metrics(returns_panel: pd.DataFrame, market_state: pd.Series, label: str) -> dict:
    # Equal-weight naive blend of sleeves
    blend = returns_panel.mean(axis=1).dropna()
    return {
        "panel_name": label,
        "n_sleeves": int(returns_panel.shape[1]),
        "ann_return": annualized_return(blend),
        "ann_vol": annualized_vol(blend),
        "sharpe": annualized_return(blend) / annualized_vol(blend) if annualized_vol(blend) and annualized_vol(blend) > 0 else float("nan"),
        "max_drawdown": max_drawdown(blend),
        "cvar_5": cvar_5(blend),
        "calmar": calmar(blend),
    }


def state_winners(panel_returns: pd.DataFrame, market_state: pd.Series, label: str) -> pd.DataFrame:
    df = panel_returns.copy()
    df["market_state"] = market_state.reindex(df.index)
    rows = []
    for state, sub in df.groupby("market_state"):
        sleeve_sharpes = {}
        for s in df.columns:
            if s == "market_state":
                continue
            r = sub[s].dropna()
            v = annualized_vol(r)
            sh = (annualized_return(r) / v) if v and v > 0 else float("nan")
            sleeve_sharpes[s] = sh
        ranked = sorted(sleeve_sharpes.items(), key=lambda x: (x[1] if not np.isnan(x[1]) else -1e9), reverse=True)
        if not ranked:
            continue
        top_sleeve, top_sh = ranked[0]
        second_sh = ranked[1][1] if len(ranked) > 1 else float("nan")
        median_sh = float(np.nanmedian(list(sleeve_sharpes.values())))
        rows.append({
            "panel_name": label,
            "market_state": state,
            "top_sleeve": top_sleeve,
            "top_sharpe_state": top_sh,
            "margin_vs_second_best_sharpe": float(top_sh - second_sh) if not np.isnan(second_sh) else float("nan"),
            "margin_vs_panel_median_sharpe": float(top_sh - median_sh) if not np.isnan(median_sh) else float("nan"),
        })
    return pd.DataFrame(rows)


def separability_summary(returns_panel: pd.DataFrame, label: str) -> dict:
    corr = returns_panel.corr().abs()
    n = corr.shape[0]
    if n < 2:
        return {"panel_name": label, "n_sleeves": n, "avg_abs_corr_off_diag": float("nan"), "max_abs_corr_off_diag": float("nan"), "median_abs_corr_off_diag": float("nan")}
    mask = ~np.eye(n, dtype=bool)
    vals = corr.values[mask]
    return {
        "panel_name": label,
        "n_sleeves": n,
        "avg_abs_corr_off_diag": float(np.nanmean(vals)),
        "max_abs_corr_off_diag": float(np.nanmax(vals)),
        "median_abs_corr_off_diag": float(np.nanmedian(vals)),
    }


# --------------------------------------------------------------------------
#                                main
# --------------------------------------------------------------------------

def main() -> None:
    prices = load_weekly_prices()
    returns = load_weekly_returns()
    market_state = load_market_state()

    # Pivot signals to date x ticker frames for the relevant scores
    breadth_long = load_signal_long("signal_breadth_confirmation")
    breadth_score = signal_pivot(breadth_long, "breadth_confirmed_momentum_score_tradable")

    multi_mom_long = load_signal_long("signal_multi_horizon_mom")
    multi_mom_score = signal_pivot(multi_mom_long, "multi_mom_equal_score_tradable")

    carry_long = load_signal_long("signal_carry")
    carry_score = signal_pivot(carry_long, "carry_score_tradable")

    quality_long = load_signal_long("signal_quality")
    quality_score = signal_pivot(quality_long, "quality_score_tradable")

    tsmom_long = load_signal_long("signal_tsmom")
    tsmom_score = signal_pivot(tsmom_long, "tsmom_score_tradable")

    # align all signals to weekly index
    weeks = returns.index
    breadth_score = reindex_to(weeks, breadth_score)
    multi_mom_score = reindex_to(weeks, multi_mom_score)
    carry_score = reindex_to(weeks, carry_score)
    quality_score = reindex_to(weeks, quality_score)
    tsmom_score = reindex_to(weeks, tsmom_score)

    # Build sleeves
    print("Building W1 — structural defensive sleeve...")
    w1 = build_w1_structural_defense(prices, returns, market_state)
    print("Building W2 — recovery-confirmed offense sleeve...")
    w2 = build_w2_recovery_offense(prices, returns, market_state, breadth_score, multi_mom_score)
    print("Building W3 — calm carry sleeve...")
    w3 = build_w3_calm_carry(prices, returns, market_state, carry_score, quality_score)
    print("Building W4 — macro trend diversifier sleeve...")
    w4 = build_w4_macro_trend(prices, returns, market_state, tsmom_score)

    sleeve_weights = {
        "composite_structural_defense_sleeve": w1,
        "composite_recovery_confirmed_offense_sleeve": w2,
        "composite_calm_carry_sleeve": w3,
        "composite_macro_trend_diversifier_sleeve": w4,
    }

    sleeve_returns = {}
    for name, w in sleeve_weights.items():
        rets = compute_strategy_returns(w, returns, cost_bps=DEFAULT_COST_BPS)
        # Save in standard sleeve format
        # Position columns are the ticker columns of w
        pos_out = w.copy()
        pos_out.index.name = ""  # match existing convention (Unnamed: 0)
        pos_out.to_csv(LAYER2A_DIR / f"strategy_positions_{name}.csv")
        ret_out = rets.copy()
        ret_out.index.name = ""
        ret_out.to_csv(LAYER2A_DIR / f"strategy_returns_{name}.csv")
        sleeve_returns[name] = rets["net_return"]

    # Standalone summary
    market_state_lag = market_state.shift(1)
    state_series = market_state_lag["market_state"]

    summary_rows = []
    state_rows = []
    holdout_rows = []
    for name, w in sleeve_weights.items():
        rets = compute_strategy_returns(w, returns, cost_bps=DEFAULT_COST_BPS)
        m = metric_row(name, rets["net_return"], w, rets["turnover"])
        summary_rows.append(m)
        sr = state_summary(name, rets["net_return"], w, state_series)
        state_rows.append(sr)
        # holdout
        hold_idx = rets.index[-HOLDOUT_WEEKS:]
        h_ret = rets.loc[hold_idx, "net_return"]
        h_w = w.loc[hold_idx]
        h_t = rets.loc[hold_idx, "turnover"]
        hm = metric_row(name, h_ret, h_w, h_t)
        hm["window"] = "holdout"
        holdout_rows.append(hm)

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(LAYER2A_DIR / "phase_w_sleeve_summary.csv", index=False)

    state_df = pd.concat(state_rows, ignore_index=True)
    state_df.to_csv(LAYER2A_DIR / "phase_w_sleeve_state_summary.csv", index=False)

    holdout_df = pd.DataFrame(holdout_rows)
    holdout_df.to_csv(LAYER2A_DIR / "phase_w_sleeve_holdout_summary.csv", index=False)

    print("\n=== Phase W standalone sleeve summary ===")
    print(summary_df.round(4).to_string(index=False))

    print("\n=== Phase W sleeve state summary ===")
    print(state_df.round(4).to_string(index=False))

    print("\n=== Phase W sleeve holdout summary ===")
    print(holdout_df.round(4).to_string(index=False))

    # Correlation diagnostics — new sleeves vs current panel
    panel_returns = load_existing_sleeve_returns()
    new_returns_df = pd.DataFrame(sleeve_returns)
    combined = panel_returns.join(new_returns_df, how="inner").dropna()
    corr_full = correlation_matrix(combined)
    corr_full.to_csv(LAYER2A_DIR / "phase_w_sleeve_correlation.csv")
    print("\n=== Phase W panel correlation matrix (active + new) ===")
    print(corr_full.round(2).to_string())

    # Panel-blend sanity checks
    blend_rows = []
    sep_rows = []
    winner_frames = []

    blend_active = panel_returns.dropna()
    blend_rows.append(panel_blend_metrics(blend_active, state_series.reindex(blend_active.index), "active_panel_naive"))
    sep_rows.append(separability_summary(blend_active, "active_panel_naive"))
    winner_frames.append(state_winners(blend_active, state_series.reindex(blend_active.index), "active_panel_naive"))

    augmented_with_w1 = blend_active.join(new_returns_df[["composite_structural_defense_sleeve"]], how="inner").dropna()
    blend_rows.append(panel_blend_metrics(augmented_with_w1, state_series.reindex(augmented_with_w1.index), "active_plus_w1"))
    sep_rows.append(separability_summary(augmented_with_w1, "active_plus_w1"))
    winner_frames.append(state_winners(augmented_with_w1, state_series.reindex(augmented_with_w1.index), "active_plus_w1"))

    augmented_full = blend_active.join(new_returns_df, how="inner").dropna()
    blend_rows.append(panel_blend_metrics(augmented_full, state_series.reindex(augmented_full.index), "active_plus_w1_w2_w3_w4"))
    sep_rows.append(separability_summary(augmented_full, "active_plus_w1_w2_w3_w4"))
    winner_frames.append(state_winners(augmented_full, state_series.reindex(augmented_full.index), "active_plus_w1_w2_w3_w4"))

    # Selective panel — drop redundancies, keep the high-conviction additions
    selective_cols = [c for c in blend_active.columns]
    selective_cols += ["composite_structural_defense_sleeve", "composite_recovery_confirmed_offense_sleeve", "composite_calm_carry_sleeve"]
    selective = blend_active.join(new_returns_df[["composite_structural_defense_sleeve", "composite_recovery_confirmed_offense_sleeve", "composite_calm_carry_sleeve"]], how="inner").dropna()
    blend_rows.append(panel_blend_metrics(selective, state_series.reindex(selective.index), "active_plus_w1_w2_w3"))
    sep_rows.append(separability_summary(selective, "active_plus_w1_w2_w3"))
    winner_frames.append(state_winners(selective, state_series.reindex(selective.index), "active_plus_w1_w2_w3"))

    blend_df = pd.DataFrame(blend_rows)
    blend_df.to_csv(LAYER2A_DIR / "phase_w_panel_blend_summary.csv", index=False)

    sep_df = pd.DataFrame(sep_rows)
    sep_df.to_csv(LAYER2A_DIR / "phase_w_panel_separability_summary.csv", index=False)

    winner_df = pd.concat(winner_frames, ignore_index=True)
    winner_df.to_csv(LAYER2A_DIR / "phase_w_panel_state_winner_summary.csv", index=False)

    print("\n=== Phase W panel blend summary ===")
    print(blend_df.round(4).to_string(index=False))

    print("\n=== Phase W panel separability ===")
    print(sep_df.round(4).to_string(index=False))

    print("\n=== Phase W panel state winners ===")
    print(winner_df.round(4).to_string(index=False))

    # Save protocol
    protocol = {
        "phase": "Phase W — Sleeve-Panel Revisit / Opportunity-Set Upgrade",
        "active_panel": ACTIVE_PANEL,
        "new_sleeves": NEW_SLEEVES,
        "design_rationale": {
            "W1": "Structural defensive sleeve — explicit causal capture of production's adverse-tape positioning (GLD/TLT/HYG/LQD/DBA/BIL).",
            "W2": "Recovery-confirmed offense — silent in calm/chop/stress, decisive only in confirmed/fragile recovery with breadth confirmation.",
            "W3": "Calm-trend carry/quality sleeve — distinct from existing calm-trend-specialist via carry+quality scoring.",
            "W4": "Cross-asset managed-futures-style trend diversifier — equity/rates/commodity/FX universe, distinct from sector trend.",
        },
        "holdout_weeks": HOLDOUT_WEEKS,
        "cost_bps": DEFAULT_COST_BPS,
    }
    (LAYER2A_DIR / "phase_w_diagnostics_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\nSaved Phase W artifacts.")


if __name__ == "__main__":
    main()
