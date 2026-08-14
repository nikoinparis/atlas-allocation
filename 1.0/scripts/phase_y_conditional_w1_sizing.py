"""Phase Y — Conditional W1 Sizing Inside the Production Allocator Family.

Phase X established two facts cleanly:
  1. The 7-sleeve panel (with W1) genuinely improves allocator quality
     on Sharpe / MDD / CVaR / turnover. (X1 vs X4 ablation: +0.069 Sharpe,
     -2.66pt MDD, -0.75pt CVaR, -5.6pt turnover.)
  2. Inverse-vol weighting over-funds W1 because W1 is the lowest-vol
     sleeve in the panel. Result: avg cash 50%, offense 37% (vs production
     55%), holdout raw composite far below production. Fails 5/8 Phase D
     gates against the production pin.

The diagnosis: the *opportunity set* is right; the *weighting rule* is wrong.
W1 was designed and validated as a callable defensive sleeve, but X used
it as a generic low-vol bucket.

Phase Y is a narrow rerun inside the production allocator family that fixes
this misuse. Four candidates, each with explicit, interpretable W1 sizing:

  Y1 — production allocator + state-capped W1
       Inverse-vol on the 7-sleeve panel as in X1, but with explicit
       state-conditional caps on W1 (calm 5%, neutral 8%, recovery_confirmed
       10%, recovery_fragile 18%, stressed 0% via state mult). Residual
       weight redistributed inverse-vol across the other 6 sleeves.
       Tests: does removing the inverse-vol over-allocation alone close
       the production gap?

  Y2 — production allocator + trigger-based W1 overlay
       Base inverse-vol on the 6 non-W1 sleeves. W1 weight set by an
       explicit defensive trigger score combining (i) recent 13w SPY
       drawdown, (ii) p_tail_risk from Phase 2B, (iii) p_regime_confidence
       (low confidence → more W1). W1 weight bounded [0, 25%]. Tests: does
       *demand-driven* W1 sizing preserve more offense in calm states than
       state-capped W1 while still delivering defense when stress builds?

  Y3 — production family + conditional W1 replaces cash (not offense)
       Run the production architecture exactly on the 6-sleeve panel
       (X4 logic): inverse-vol on the 6 + state risk multiplier + ML offset.
       Then redirect a fraction of the resulting cash share to W1 when
       defensive triggers are active. W1 only enters by displacing cash,
       never by displacing offense. Most production-consistent integration.

  Y4 — incremental ablation summary
       Side-by-side comparison of the production-style allocator under:
         (a) no W1               -> X4 reference
         (b) uncapped W1 (X1)    -> Phase X failure mode
         (c) state-capped W1     -> Y1
         (d) trigger-driven W1   -> Y2
         (e) cash-replacement W1 -> Y3
       This is reported inside the validation bundle, not a separate run.

All causal/walk-forward safety identical to Phase X:
  - 1-week-lagged sleeve features
  - 156-week trailing inverse-vol
  - state multipliers from existing walk-forward source
  - p_regime/p_trans/p_tail from existing Phase 2B walk-forward predictions
  - SPY drawdown computed from t-1 closed weekly returns
  - no retraining

Outputs to data/05_layer3_portfolio_construction/:
  portfolio_version_weights_{Y1,Y2,Y3}.csv (ETF level)
  portfolio_version_returns_{Y1,Y2,Y3}.csv
  portfolio_version_sleeve_weights_{Y1,Y2,Y3}.csv
  phase_y_candidate_metrics_{full,dev,holdout}.csv
  phase_y_pairwise_validation.csv
  phase_y_rolling_origin_summary.csv
  phase_y_candidate_classification.csv
  phase_y_w1_diagnostics.csv
  phase_y_state_w1_usage.csv
  phase_y_w1_ablation_table.csv
  phase_y_validation_protocol.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase_d_validate as pdv
import phase_p_meta_allocator as pp
import phase_p_evaluate as ppe
import phase_x_allocator_rerun_7sleeve as phase_x


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

PRODUCTION_PIN = pp.PRODUCTION_PIN
SHADOW_PIN = pp.SHADOW_PIN
ACTIVE_PANEL_BASELINE = pp.ACTIVE_PANEL_BASELINE
PHASEU_U1A_REFERENCE = "improved_phaseu_prod90_r2_10_holdings_blend"
PHASEU_U3_REFERENCE = "improved_phaseu_conditional_prod_r2_holdings_blend"
PHASER_R3_REFERENCE = "improved_phaser_fast_narrow_regret_allocator"
PHASEV_V1_REFERENCE = "improved_phasev_prod90_phasen_10_holdings_blend"
PHASEX_X1_REFERENCE = "improved_phasex_production_style_7sleeve"
PHASEX_X2_REFERENCE = "improved_phasex_shadow_style_7sleeve"
PHASEX_X3_REFERENCE = "improved_phasex_state_conditional_7sleeve"
PHASEX_X4_REFERENCE = "improved_phasex_production_style_6sleeve_ablation"

# Phase Y comparator: full Phase X comparator + Phase X candidates as new references.
FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEU_U1A_REFERENCE,
    PHASEU_U3_REFERENCE,
    PHASER_R3_REFERENCE,
    PHASEV_V1_REFERENCE,
    PHASEX_X1_REFERENCE,
    PHASEX_X2_REFERENCE,
    PHASEX_X3_REFERENCE,
    PHASEX_X4_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

PANEL_7 = phase_x.PANEL_7
PANEL_6 = phase_x.PANEL_6
W1_NAME = phase_x.W1_NAME

# Phase Y candidate names
Y1_NAME = "improved_phasey_state_capped_w1"
Y2_NAME = "improved_phasey_trigger_driven_w1"
Y3_NAME = "improved_phasey_cash_replacement_w1"

PHASE_Y_CANDIDATES = [Y1_NAME, Y2_NAME, Y3_NAME]

EPS = phase_x.EPS
LOOKBACK = phase_x.LOOKBACK
MIN_HISTORY = phase_x.MIN_HISTORY
STATE_RISK_MULT = phase_x.STATE_RISK_MULT


# --------------------------------------------------------------------------
#                Y1 — state-conditional W1 caps inside production family
# --------------------------------------------------------------------------

# Hand-picked, interpretable caps. Floor of W1's contribution in each state
# is small in calm/recovery (so it does not crowd offense), and rises in
# defensive states. In stressed_panic the state risk multiplier is already
# zero, so the cap is moot. Caps reflect Phase W's diagnosis (W1 is the
# only sleeve with positive sharpe in stressed_panic) and Phase X's failure
# mode (offense crowded out in calm/neutral by 32-34% W1 weight).
W1_STATE_CAP = {
    "calm_trend": 0.05,
    "neutral_mixed": 0.08,
    "recovery_confirmed": 0.10,
    "recovery_fragile": 0.18,
    "stressed_panic": 0.20,  # mooted by state_risk_mult = 0
}


def state_capped_inverse_vol_weights(
    sleeve_returns_panel: pd.DataFrame,
    as_of: pd.Timestamp,
    panel: list[str],
    state: str,
    w1_cap: float,
) -> pd.Series:
    """Inverse-vol weights with an explicit cap on W1.

    If the unconstrained inverse-vol weight on W1 exceeds `w1_cap`, force
    W1 to `w1_cap` and redistribute the (w_old - cap) excess across the
    other panel sleeves *in proportion to their existing inverse-vol weight*.
    This preserves the production family's inverse-vol structure on the
    non-W1 sleeves and only fixes the over-allocation pathology.
    """
    base = phase_x.inverse_vol_weights(sleeve_returns_panel, as_of, panel)
    if W1_NAME not in panel:
        return base
    w1_uncon = float(base.get(W1_NAME, 0.0))
    if w1_uncon <= w1_cap + EPS:
        return base
    # Cap and redistribute excess across the other panel members.
    excess = w1_uncon - w1_cap
    others = [s for s in panel if s != W1_NAME]
    other_w = base.reindex(others)
    if other_w.sum() <= EPS:
        return base
    redistrib = other_w / other_w.sum() * excess
    capped = base.copy()
    capped[W1_NAME] = w1_cap
    for s in others:
        capped[s] = float(capped[s]) + float(redistrib[s])
    return capped


# --------------------------------------------------------------------------
#                Y2 — trigger-driven W1 overlay
# --------------------------------------------------------------------------

# Trigger weights and bounds, hand-picked to be interpretable.
W1_TRIGGER_FLOOR = 0.02       # minimum W1 weight when no trigger active
W1_TRIGGER_CEILING = 0.25     # maximum W1 weight when triggers fully active
TRIGGER_DD_LOOKBACK = 13      # weeks for SPY rolling drawdown


def defensive_trigger_score(
    as_of: pd.Timestamp,
    spy_weekly: pd.Series,
    phase2b_pred: pd.DataFrame,
) -> float:
    """Compute a defensive trigger score in [0, 1].

    Combines three causally available, walk-forward signals (all use t-1
    closed information):
      (i)  recent SPY drawdown depth: scaled negatively → 0 means no DD,
           1 means -10% or worse over 13w
      (ii) p_tail_risk: scaled in [0, 1], directly used (capped at 0.55→0,
           0.80→1)
      (iii) (1 - p_regime_confidence): low regime confidence → more defense
            (0.45→0, 0.20→1)
    Score = mean of available components, clipped [0, 1].
    """
    parts: list[float] = []

    # (i) SPY drawdown
    spy_history = spy_weekly.loc[:as_of]
    if len(spy_history) >= TRIGGER_DD_LOOKBACK + 1:
        spy_history = spy_history.iloc[:-1].tail(TRIGGER_DD_LOOKBACK)
        wealth = (1.0 + spy_history.fillna(0.0)).cumprod()
        dd = float(wealth.iloc[-1] / wealth.cummax().iloc[-1] - 1.0)
        # dd in (-inf, 0]; map -10% → 1.0, 0% → 0.0
        dd_score = float(np.clip(-dd / 0.10, 0.0, 1.0))
        parts.append(dd_score)

    # (ii) p_tail_risk
    try:
        row = phase2b_pred.loc[as_of]
        p_tail = float(row.get("p_tail_risk", np.nan))
        p_regime = float(row.get("p_regime_confidence", np.nan))
    except KeyError:
        p_tail = np.nan
        p_regime = np.nan

    if not np.isnan(p_tail):
        # 0.55 → 0, 0.80 → 1
        tail_score = float(np.clip((p_tail - 0.55) / max(EPS, 0.80 - 0.55), 0.0, 1.0))
        parts.append(tail_score)

    if not np.isnan(p_regime):
        # 0.45 → 0, 0.20 → 1
        reg_score = float(np.clip((0.45 - p_regime) / max(EPS, 0.45 - 0.20), 0.0, 1.0))
        parts.append(reg_score)

    if not parts:
        return 0.0
    return float(np.mean(parts))


def trigger_driven_w1_weights(
    sleeve_returns_panel: pd.DataFrame,
    as_of: pd.Timestamp,
    state: str,
    spy_weekly: pd.Series,
    phase2b_pred: pd.DataFrame,
) -> pd.Series:
    """Y2 weights: inverse-vol on 6 non-W1 sleeves, W1 weight set by trigger.

    W1 weight = floor + score * (ceiling - floor)
    Other sleeves split (1 - W1 weight) by inverse-vol.
    In stressed_panic the state mult is already 0 so W1 weight is moot.
    """
    score = defensive_trigger_score(as_of, spy_weekly, phase2b_pred)
    w1 = W1_TRIGGER_FLOOR + score * (W1_TRIGGER_CEILING - W1_TRIGGER_FLOOR)
    others_inv = phase_x.inverse_vol_weights(sleeve_returns_panel, as_of, PANEL_6)
    out = pd.Series(0.0, index=PANEL_7)
    for s in PANEL_6:
        out[s] = float(others_inv[s]) * (1.0 - w1)
    out[W1_NAME] = w1
    return out


# --------------------------------------------------------------------------
#                Y3 — W1 replaces cash, never offense
# --------------------------------------------------------------------------

# Y3 conversion rate: when triggers fire, what fraction of the cash share
# is redirected into W1? Bounded so even at peak-trigger we keep some BIL.
Y3_CASH_TO_W1_MAX = 0.50


# --------------------------------------------------------------------------
#                build_candidate variants
# --------------------------------------------------------------------------

def build_y1_candidate(
    sleeve_returns_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    market_state_history: pd.DataFrame,
    phase2b_pred: pd.DataFrame,
    weekly_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Y1: production-style on 7-sleeve panel with explicit state-capped W1."""
    common_idx = sleeve_returns_panel.index.intersection(market_state_history.index).sort_values()
    etf_universe = sorted({c for sleeve in PANEL_7 for c in sleeve_positions[sleeve].columns})
    sleeve_w_rows, etf_w_rows = [], []
    for date in common_idx:
        try:
            state = str(market_state_history.loc[date, "market_state"])
        except KeyError:
            state = "neutral_mixed"
        cap = W1_STATE_CAP.get(state, 0.10)
        base_w = state_capped_inverse_vol_weights(sleeve_returns_panel, date, PANEL_7, state, cap)
        risk_mult = STATE_RISK_MULT.get(state, 0.80)
        try:
            row = phase2b_pred.loc[date]
            p_regime = float(row.get("p_regime_confidence", np.nan))
            p_trans = float(row.get("p_transition_quality", np.nan))
            p_tail = float(row.get("p_tail_risk", np.nan))
        except KeyError:
            p_regime = p_trans = p_tail = np.nan
        offset = phase_x.regime_confidence_boost_offset(state, p_regime, p_trans, p_tail, "regime_confidence_boost")
        risk_mult = float(np.clip(risk_mult + offset, 0.0, 1.0))
        risk_share = float(np.clip(risk_mult, 0.0, 1.0))
        cash_share = 1.0 - risk_share
        sleeve_alloc = base_w * risk_share
        sleeve_alloc["cash::BIL"] = cash_share
        sleeve_w_rows.append(pd.Series(sleeve_alloc, name=date))
        etf_w = pd.Series(0.0, index=etf_universe)
        for sleeve in PANEL_7:
            sleeve_pos_today = sleeve_positions[sleeve].reindex([date]).fillna(0.0).iloc[0]
            etf_w = etf_w.add(sleeve_alloc[sleeve] * sleeve_pos_today.reindex(etf_universe).fillna(0.0), fill_value=0.0)
        etf_w["BIL"] = float(etf_w.get("BIL", 0.0)) + cash_share
        total = float(etf_w.sum())
        if total > EPS:
            etf_w = etf_w / total
        else:
            etf_w[:] = 0.0
            etf_w["BIL"] = 1.0
        etf_w_rows.append(etf_w.rename(date))
    sleeve_weights_df = pd.DataFrame(sleeve_w_rows).fillna(0.0)
    etf_weights_df = pd.DataFrame(etf_w_rows).fillna(0.0)
    sleeve_weights_df.index.name = None
    etf_weights_df.index.name = None
    return sleeve_weights_df, etf_weights_df, _net_returns_from_etf_weights(etf_weights_df, weekly_returns)


def build_y2_candidate(
    sleeve_returns_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    market_state_history: pd.DataFrame,
    phase2b_pred: pd.DataFrame,
    weekly_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Y2: trigger-driven W1 weight; production architecture on the rest."""
    spy_weekly = weekly_returns["SPY"].astype(float).sort_index()
    common_idx = sleeve_returns_panel.index.intersection(market_state_history.index).sort_values()
    etf_universe = sorted({c for sleeve in PANEL_7 for c in sleeve_positions[sleeve].columns})
    sleeve_w_rows, etf_w_rows = [], []
    for date in common_idx:
        try:
            state = str(market_state_history.loc[date, "market_state"])
        except KeyError:
            state = "neutral_mixed"
        base_w = trigger_driven_w1_weights(sleeve_returns_panel, date, state, spy_weekly, phase2b_pred)
        risk_mult = STATE_RISK_MULT.get(state, 0.80)
        try:
            row = phase2b_pred.loc[date]
            p_regime = float(row.get("p_regime_confidence", np.nan))
            p_trans = float(row.get("p_transition_quality", np.nan))
            p_tail = float(row.get("p_tail_risk", np.nan))
        except KeyError:
            p_regime = p_trans = p_tail = np.nan
        offset = phase_x.regime_confidence_boost_offset(state, p_regime, p_trans, p_tail, "regime_confidence_boost")
        risk_mult = float(np.clip(risk_mult + offset, 0.0, 1.0))
        risk_share = float(np.clip(risk_mult, 0.0, 1.0))
        cash_share = 1.0 - risk_share
        sleeve_alloc = base_w * risk_share
        sleeve_alloc["cash::BIL"] = cash_share
        sleeve_w_rows.append(pd.Series(sleeve_alloc, name=date))
        etf_w = pd.Series(0.0, index=etf_universe)
        for sleeve in PANEL_7:
            sleeve_pos_today = sleeve_positions[sleeve].reindex([date]).fillna(0.0).iloc[0]
            etf_w = etf_w.add(sleeve_alloc[sleeve] * sleeve_pos_today.reindex(etf_universe).fillna(0.0), fill_value=0.0)
        etf_w["BIL"] = float(etf_w.get("BIL", 0.0)) + cash_share
        total = float(etf_w.sum())
        if total > EPS:
            etf_w = etf_w / total
        else:
            etf_w[:] = 0.0
            etf_w["BIL"] = 1.0
        etf_w_rows.append(etf_w.rename(date))
    sleeve_weights_df = pd.DataFrame(sleeve_w_rows).fillna(0.0)
    etf_weights_df = pd.DataFrame(etf_w_rows).fillna(0.0)
    sleeve_weights_df.index.name = None
    etf_weights_df.index.name = None
    return sleeve_weights_df, etf_weights_df, _net_returns_from_etf_weights(etf_weights_df, weekly_returns)


def build_y3_candidate(
    sleeve_returns_panel_full: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    market_state_history: pd.DataFrame,
    phase2b_pred: pd.DataFrame,
    weekly_returns: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Y3: production architecture on 6 sleeves; W1 displaces cash only."""
    spy_weekly = weekly_returns["SPY"].astype(float).sort_index()
    sleeve_returns_6 = sleeve_returns_panel_full[PANEL_6]
    common_idx = sleeve_returns_panel_full.index.intersection(market_state_history.index).sort_values()
    etf_universe = sorted({c for sleeve in PANEL_7 for c in sleeve_positions[sleeve].columns})
    sleeve_w_rows, etf_w_rows = [], []
    for date in common_idx:
        try:
            state = str(market_state_history.loc[date, "market_state"])
        except KeyError:
            state = "neutral_mixed"
        # Production architecture on 6 sleeves
        base_w_6 = phase_x.inverse_vol_weights(sleeve_returns_6, date, PANEL_6)
        risk_mult = STATE_RISK_MULT.get(state, 0.80)
        try:
            row = phase2b_pred.loc[date]
            p_regime = float(row.get("p_regime_confidence", np.nan))
            p_trans = float(row.get("p_transition_quality", np.nan))
            p_tail = float(row.get("p_tail_risk", np.nan))
        except KeyError:
            p_regime = p_trans = p_tail = np.nan
        offset = phase_x.regime_confidence_boost_offset(state, p_regime, p_trans, p_tail, "regime_confidence_boost")
        risk_mult = float(np.clip(risk_mult + offset, 0.0, 1.0))
        risk_share = float(np.clip(risk_mult, 0.0, 1.0))
        cash_share = 1.0 - risk_share

        # Defensive trigger → fraction of cash redirected to W1
        score = defensive_trigger_score(date, spy_weekly, phase2b_pred)
        cash_to_w1_frac = score * Y3_CASH_TO_W1_MAX
        # In stressed_panic: cash_share is high but state risk mult is 0; we still
        # keep W1 = 0 here because the production architecture intends fully
        # defensive cash. Phase W's W1 advantage in stressed_panic is moot
        # under production architecture because risk_mult = 0.
        if state == "stressed_panic":
            w1_alloc = 0.0
        else:
            w1_alloc = cash_share * cash_to_w1_frac
        new_cash_share = cash_share - w1_alloc

        sleeve_alloc = pd.Series(0.0, index=PANEL_7)
        for s in PANEL_6:
            sleeve_alloc[s] = float(base_w_6[s]) * risk_share
        sleeve_alloc[W1_NAME] = w1_alloc
        sleeve_alloc["cash::BIL"] = new_cash_share
        sleeve_w_rows.append(pd.Series(sleeve_alloc, name=date))

        etf_w = pd.Series(0.0, index=etf_universe)
        for sleeve in PANEL_7:
            sleeve_pos_today = sleeve_positions[sleeve].reindex([date]).fillna(0.0).iloc[0]
            etf_w = etf_w.add(sleeve_alloc[sleeve] * sleeve_pos_today.reindex(etf_universe).fillna(0.0), fill_value=0.0)
        etf_w["BIL"] = float(etf_w.get("BIL", 0.0)) + new_cash_share
        total = float(etf_w.sum())
        if total > EPS:
            etf_w = etf_w / total
        else:
            etf_w[:] = 0.0
            etf_w["BIL"] = 1.0
        etf_w_rows.append(etf_w.rename(date))
    sleeve_weights_df = pd.DataFrame(sleeve_w_rows).fillna(0.0)
    etf_weights_df = pd.DataFrame(etf_w_rows).fillna(0.0)
    sleeve_weights_df.index.name = None
    etf_weights_df.index.name = None
    return sleeve_weights_df, etf_weights_df, _net_returns_from_etf_weights(etf_weights_df, weekly_returns)


def _net_returns_from_etf_weights(etf_weights_df: pd.DataFrame, weekly_returns: pd.DataFrame) -> pd.Series:
    next_week_returns = weekly_returns.shift(-1)
    common_idx_returns = etf_weights_df.index.intersection(next_week_returns.index)
    common_etfs = [c for c in etf_weights_df.columns if c in next_week_returns.columns]
    aligned_w = etf_weights_df.loc[common_idx_returns, common_etfs]
    aligned_r = next_week_returns.loc[common_idx_returns, common_etfs].fillna(0.0)
    gross_returns = (aligned_w * aligned_r).sum(axis=1)
    turnover = aligned_w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * 0.0005 * 0.5
    return gross_returns - cost


# --------------------------------------------------------------------------
#                W1 ablation comparison table
# --------------------------------------------------------------------------

def w1_ablation_table(metrics_full: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side ablation: same production family, different W1 sizing rules."""
    cols = ["version_name", "ann_return", "sharpe", "max_drawdown", "cvar_5",
            "turnover", "avg_offense", "avg_cash", "raw_target_composite"]
    members = [
        ("(a) no W1                   ", PHASEX_X4_REFERENCE),
        ("(b) uncapped W1 (X1)        ", PHASEX_X1_REFERENCE),
        ("(c) state-capped W1 (Y1)    ", Y1_NAME),
        ("(d) trigger-driven W1 (Y2)  ", Y2_NAME),
        ("(e) cash-replacement W1 (Y3)", Y3_NAME),
    ]
    rows = []
    midx = metrics_full.set_index("version_name")
    for label, name in members:
        if name in midx.index:
            r = midx.loc[name]
            rows.append({"label": label, **{c: r.get(c, np.nan) for c in cols if c != "version_name"}, "version_name": name})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
#                W1 diagnostics + state usage (re-using Phase X functions)
# --------------------------------------------------------------------------

def w1_trigger_diag(sleeve_weights: pd.DataFrame, name: str, weekly_returns: pd.DataFrame, phase2b_pred: pd.DataFrame) -> pd.DataFrame:
    """Per-row trigger diagnostic for Y2/Y3 — mean W1 weight by trigger-score quintile."""
    spy = weekly_returns["SPY"].astype(float).sort_index()
    scores = []
    w1_w = []
    for d in sleeve_weights.index:
        try:
            scores.append(defensive_trigger_score(d, spy, phase2b_pred))
        except Exception:
            scores.append(np.nan)
        w1_w.append(float(sleeve_weights.loc[d].get(W1_NAME, 0.0)))
    df = pd.DataFrame({"date": sleeve_weights.index, "trigger_score": scores, "w1_weight": w1_w}).dropna()
    if df.empty:
        return pd.DataFrame()
    try:
        df["quintile"] = pd.qcut(df["trigger_score"], q=5, labels=False, duplicates="drop")
    except ValueError:
        # Fallback: bin by score thresholds
        df["quintile"] = pd.cut(df["trigger_score"], bins=[-0.01, 0.05, 0.20, 0.40, 0.60, 1.01], labels=False)
    df["quintile"] = df["quintile"].fillna(0).astype(int).astype(str)
    out = df.groupby("quintile", observed=True).agg(
        avg_trigger=("trigger_score", "mean"),
        avg_w1_weight=("w1_weight", "mean"),
        obs=("w1_weight", "size"),
    ).reset_index()
    out.insert(0, "version_name", name)
    return out


# --------------------------------------------------------------------------
#                  validation bundle (mirrors Phase X)
# --------------------------------------------------------------------------

def build_validation_bundle(candidate_names: list[str]) -> dict:
    all_versions = list(FIXED_COMPARATOR_SET) + candidate_names
    returns_map, weights_map, turnover_map, benchmark_returns, market_state_history = ppe.candidate_frames(all_versions)

    full_rows, dev_rows, holdout_rows = [], [], []
    for name in all_versions:
        full_rows.append(ppe.metric_row(name, returns_map[name], weights_map[name], turnover_map[name], benchmark_returns, market_state_history))
        dev_ret, hold_ret, dev_w, hold_w = pdv.split_dev_holdout(returns_map[name], weights_map[name], pdv.HOLDOUT_WEEKS)
        dev_rows.append(ppe.metric_row(name, dev_ret, dev_w, turnover_map[name].reindex(dev_ret.index), benchmark_returns.reindex(dev_ret.index), market_state_history))
        holdout_rows.append(ppe.metric_row(name, hold_ret, hold_w, turnover_map[name].reindex(hold_ret.index), benchmark_returns.reindex(hold_ret.index), market_state_history))
    full_df = pd.DataFrame(full_rows)
    dev_df = pd.DataFrame(dev_rows)
    holdout_df = pd.DataFrame(holdout_rows)
    for df in [full_df, dev_df, holdout_df]:
        df["fixed_rank_composite"] = pdv.fixed_rank_composite(df.set_index("version_name")).values
        df["fixed_rank_position"] = df["fixed_rank_composite"].rank(ascending=False, method="dense").astype(int)
        df["raw_composite_position"] = df["raw_target_composite"].rank(ascending=False, method="dense").astype(int)

    rolling_df, rolling_pairwise = ppe.rolling_evaluation(all_versions, returns_map, weights_map, turnover_map, benchmark_returns, market_state_history)

    full_idx = full_df.set_index("version_name")
    holdout_idx = holdout_df.set_index("version_name")
    production_full = full_idx.loc[PRODUCTION_PIN]
    production_holdout = holdout_idx.loc[PRODUCTION_PIN]
    production_holdout_returns = returns_map[PRODUCTION_PIN].tail(pdv.HOLDOUT_WEEKS)
    u1a_full = full_idx.loc[PHASEU_U1A_REFERENCE]
    u1a_holdout = holdout_idx.loc[PHASEU_U1A_REFERENCE]
    u1a_holdout_returns = returns_map[PHASEU_U1A_REFERENCE].tail(pdv.HOLDOUT_WEEKS)
    x1_full = full_idx.loc[PHASEX_X1_REFERENCE]
    x1_holdout = holdout_idx.loc[PHASEX_X1_REFERENCE]
    x1_holdout_returns = returns_map[PHASEX_X1_REFERENCE].tail(pdv.HOLDOUT_WEEKS)

    pairwise_rows = []
    for name in all_versions:
        cand_full = full_idx.loc[name]
        cand_holdout = holdout_idx.loc[name]
        cand_holdout_returns = returns_map[name].tail(pdv.HOLDOUT_WEEKS)
        roll = rolling_pairwise.set_index("version_name").loc[name]
        row = {
            "version_name": name,
            "full_raw_delta_vs_production": float(cand_full["raw_target_composite"] - production_full["raw_target_composite"]),
            "holdout_raw_delta_vs_production": float(cand_holdout["raw_target_composite"] - production_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_production": float(cand_holdout["sharpe"] - production_holdout["sharpe"]),
            "bootstrap_prob_vs_production": ppe.safe_bootstrap(cand_holdout_returns, production_holdout_returns),
            "full_raw_delta_vs_u1a": float(cand_full["raw_target_composite"] - u1a_full["raw_target_composite"]),
            "holdout_raw_delta_vs_u1a": float(cand_holdout["raw_target_composite"] - u1a_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_u1a": float(cand_holdout["sharpe"] - u1a_holdout["sharpe"]),
            "bootstrap_prob_vs_u1a": ppe.safe_bootstrap(cand_holdout_returns, u1a_holdout_returns),
            "full_raw_delta_vs_x1": float(cand_full["raw_target_composite"] - x1_full["raw_target_composite"]),
            "holdout_raw_delta_vs_x1": float(cand_holdout["raw_target_composite"] - x1_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_x1": float(cand_holdout["sharpe"] - x1_holdout["sharpe"]),
            "bootstrap_prob_vs_x1": ppe.safe_bootstrap(cand_holdout_returns, x1_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)
    pairwise_df = pd.DataFrame(pairwise_rows)

    classification_df = pairwise_df[pairwise_df["version_name"].isin(candidate_names)].copy()

    best_non_prod = (
        full_df[full_df["version_name"] != PRODUCTION_PIN]
        .sort_values("raw_target_composite", ascending=False)
        .iloc[0]["version_name"]
    )

    def classify(row: pd.Series) -> str:
        prod_rule_pass = (
            row["full_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["full_raw_composite_delta_vs_production_min"]
            and row["holdout_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_raw_composite_delta_vs_production_min"]
            and row["holdout_sharpe_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_sharpe_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= ppe.PRODUCTION_RULE["rolling_raw_win_rate_vs_production_min"]
            and row["rolling_mean_raw_delta_vs_production"] > ppe.PRODUCTION_RULE["rolling_mean_raw_delta_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= ppe.PRODUCTION_RULE["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= ppe.PRODUCTION_RULE["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= ppe.PRODUCTION_RULE["cvar_worsening_cap"]
        )
        if prod_rule_pass:
            return "Promote now"
        shadow_pass = (
            str(row["version_name"]) == best_non_prod
            and row["holdout_raw_delta_vs_production"] >= ppe.SHADOW_RULE["holdout_raw_composite_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= ppe.SHADOW_RULE["rolling_raw_win_rate_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= ppe.SHADOW_RULE["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= ppe.SHADOW_RULE["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= ppe.SHADOW_RULE["cvar_worsening_cap"]
        )
        if shadow_pass:
            return "Conditional"
        research = (
            row["full_raw_delta_vs_u1a"] > 0.0
            or row["holdout_sharpe_delta_vs_u1a"] > 0.0
            or row["holdout_raw_delta_vs_u1a"] > 0.0
            or row["bootstrap_prob_vs_u1a"] > 0.5
            or row.get("full_raw_delta_vs_x1", -1.0) > 0.0
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_y_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_y_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_y_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_y_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_y_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_y_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase Y — Conditional W1 Sizing Inside the Production Allocator Family",
        "panel_7": PANEL_7,
        "panel_6": PANEL_6,
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_y_candidates": list(candidate_names),
        "w1_state_cap": W1_STATE_CAP,
        "trigger_floor": W1_TRIGGER_FLOOR,
        "trigger_ceiling": W1_TRIGGER_CEILING,
        "y3_cash_to_w1_max": Y3_CASH_TO_W1_MAX,
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
    }
    (LAYER3_DIR / "phase_y_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {"full": full_df, "dev": dev_df, "holdout": holdout_df, "rolling": rolling_df, "pairwise": pairwise_df, "classification": classification_df}


# --------------------------------------------------------------------------
#                                 main
# --------------------------------------------------------------------------

def main() -> None:
    print("Loading sleeve panel...")
    sleeve_returns = pd.DataFrame({s: phase_x.load_sleeve_returns(s) for s in PANEL_7}).dropna(how="all")
    sleeve_positions = {s: phase_x.load_sleeve_positions(s) for s in PANEL_7}
    market_state_history = phase_x.load_market_state()
    phase2b_pred = phase_x.load_phase2b_predictions()
    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", index_col=0, parse_dates=True).sort_index()
    weekly_returns.index.name = None

    print("\n=== Building Y1 (state-capped W1) ===")
    y1_sw, y1_ew, y1_ret = build_y1_candidate(sleeve_returns, sleeve_positions, market_state_history, phase2b_pred, weekly_returns)
    print("=== Building Y2 (trigger-driven W1) ===")
    y2_sw, y2_ew, y2_ret = build_y2_candidate(sleeve_returns, sleeve_positions, market_state_history, phase2b_pred, weekly_returns)
    print("=== Building Y3 (cash-replacement W1) ===")
    y3_sw, y3_ew, y3_ret = build_y3_candidate(sleeve_returns, sleeve_positions, market_state_history, phase2b_pred, weekly_returns)

    bundles = [
        (Y1_NAME, y1_sw, y1_ew, y1_ret),
        (Y2_NAME, y2_sw, y2_ew, y2_ret),
        (Y3_NAME, y3_sw, y3_ew, y3_ret),
    ]

    print("\n=== Saving portfolio_version files ===")
    w1_diag_rows = []
    w1_state_rows = []
    trigger_diag_rows = []
    for name, sw, ew, ret in bundles:
        sw.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")
        ew.to_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        turnover = ew.diff().abs().sum(axis=1).fillna(0.0)
        cost = turnover * 0.0005 * 0.5
        wealth = (1.0 + ret.fillna(0.0)).cumprod()
        drawdown = wealth / wealth.cummax() - 1.0
        ret_df = pd.DataFrame({
            "gross_return": ret + cost,
            "net_return": ret,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": drawdown,
        })
        ret_df.to_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        w1_diag_rows.append(phase_x.w1_diagnostics(sw, market_state_history, name))
        sus = phase_x.w1_state_usage(sw, market_state_history, name)
        if not sus.empty:
            w1_state_rows.append(sus)
        if name in (Y2_NAME, Y3_NAME):
            td = w1_trigger_diag(sw, name, weekly_returns, phase2b_pred)
            if not td.empty:
                trigger_diag_rows.append(td)

    pd.DataFrame(w1_diag_rows).to_csv(LAYER3_DIR / "phase_y_w1_diagnostics.csv", index=False)
    if w1_state_rows:
        pd.concat(w1_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_y_state_w1_usage.csv", index=False)
    if trigger_diag_rows:
        pd.concat(trigger_diag_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_y_trigger_diagnostics.csv", index=False)

    print("\n=== Validation under Phase D rules ===")
    bundle = build_validation_bundle(PHASE_Y_CANDIDATES)

    print("\n=== Phase Y — full-history metrics (Y candidates + key references) ===")
    show_versions = [PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASEX_X1_REFERENCE, PHASEX_X4_REFERENCE] + PHASE_Y_CANDIDATES
    full_view = bundle["full"][bundle["full"]["version_name"].isin(show_versions)][[
        "version_name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5",
        "turnover", "avg_offense", "avg_cash", "raw_target_composite"
    ]]
    print(full_view.to_string(index=False))

    print("\n=== Phase Y — holdout metrics ===")
    holdout_view = bundle["holdout"][bundle["holdout"]["version_name"].isin(show_versions)][[
        "version_name", "ann_return", "sharpe", "max_drawdown", "raw_target_composite"
    ]]
    print(holdout_view.to_string(index=False))

    print("\n=== Phase Y — pairwise vs production ===")
    pw = bundle["pairwise"][bundle["pairwise"]["version_name"].isin(PHASE_Y_CANDIDATES)][[
        "version_name", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
        "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production",
        "rolling_mean_raw_delta_vs_production", "bootstrap_prob_vs_production",
        "max_drawdown_delta_vs_production", "cvar_delta_vs_production",
    ]]
    print(pw.to_string(index=False))

    print("\n=== Phase Y — pairwise vs X1 (uncapped W1 reference) ===")
    pwx = bundle["pairwise"][bundle["pairwise"]["version_name"].isin(PHASE_Y_CANDIDATES)][[
        "version_name", "full_raw_delta_vs_x1", "holdout_raw_delta_vs_x1",
        "holdout_sharpe_delta_vs_x1", "bootstrap_prob_vs_x1",
    ]]
    print(pwx.to_string(index=False))

    print("\n=== Phase Y — classification ===")
    cls = bundle["classification"][["version_name", "classification"]]
    print(cls.to_string(index=False))

    print("\n=== Phase Y — W1 sizing diagnostics ===")
    print(pd.DataFrame(w1_diag_rows).to_string(index=False))

    print("\n=== Phase Y — W1 ablation table (production family, varying W1 rule) ===")
    abl = w1_ablation_table(bundle["full"])
    abl.to_csv(LAYER3_DIR / "phase_y_w1_ablation_table.csv", index=False)
    print(abl.to_string(index=False))

    if w1_state_rows:
        print("\n=== Phase Y — W1 weight by state (Y1 / Y2 / Y3) ===")
        sus_all = pd.concat(w1_state_rows, ignore_index=True)
        print(sus_all.to_string(index=False))

    if trigger_diag_rows:
        print("\n=== Phase Y — trigger-quintile W1 weight (Y2 / Y3) ===")
        td = pd.concat(trigger_diag_rows, ignore_index=True)
        print(td.to_string(index=False))

    print("\nSaved Phase Y artifacts.")


if __name__ == "__main__":
    main()
