"""Phase X — Allocator Rerun on the Upgraded 7-Sleeve Panel.

Phase W promoted `composite_structural_defense_sleeve` (W1) into the active
panel, taking it from 6 sleeves to 7. The upgraded panel has:
  - max correlation between W1 and any active sleeve = 0.09
  - panel avg |corr| dropped from 0.66 to 0.48
  - W1 is the only sleeve with positive sharpe in stressed_panic while
    actually running a defensive basket (not BIL parking)

Phase X tests the next question: does the upgraded panel let the allocator
finally produce a candidate that materially improves deployment quality
versus the prior branch? Specifically, four narrowly justified candidates
on the same opportunity set:

  X1 — production-style allocator on the 7-sleeve panel
       inverse-vol sleeve weighting + state risk multiplier + Phase 2B
       regime_confidence_boost meta. Tests whether the production allocator
       family, given W1 as a callable defensive sleeve, would produce a
       cleaner gate alignment than the prior production candidate which
       had to approximate defense via overlay.

  X2 — shadow-style allocator on the 7-sleeve panel
       Same allocator with combo_abc (A+B+C) meta layer. Tests whether the
       full interpretable-ML stack now interacts more constructively with
       the panel's better defensive stance.

  X3 — best-justified research-style allocator on the 7-sleeve panel
       state-conditional sleeve weights (each market state has its own
       weighting), without ML meta layer. Represents a Phase-H-style
       refined-state allocator. Tests whether a state-aware allocator
       extracts a measurable benefit from W1's clear defensive role.

  X4 — clean ablation: same X1 logic on 6-sleeve vs 7-sleeve panel
       Identical allocator with and without W1 included. Isolates the
       *incremental contribution* of W1 inside the X1 family.

Causal / walk-forward safety:
  - All sleeve features 1-week-lagged.
  - Inverse-vol weights computed from 156-week trailing returns, t-1 only.
  - State multipliers and ML predictions from existing walk-forward sources.
  - No retraining of any branch, no new sleeves.

Outputs to data/05_layer3_portfolio_construction/:
  portfolio_version_weights_{X1,X2,X3,X4}.csv (ETF level)
  portfolio_version_returns_{X1,X2,X3,X4}.csv
  portfolio_version_sleeve_weights_{X1,X2,X3,X4}.csv (sleeve level)
  phase_x_candidate_metrics_{full,dev,holdout}.csv
  phase_x_pairwise_validation.csv
  phase_x_rolling_origin_summary.csv
  phase_x_candidate_classification.csv
  phase_x_w1_diagnostics.csv
  phase_x_state_w1_usage.csv
  phase_x_validation_protocol.json
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


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

PRODUCTION_PIN = pp.PRODUCTION_PIN
SHADOW_PIN = pp.SHADOW_PIN
PHASEH_REFERENCE = pp.PHASEH_REFERENCE
PHASEN_REFERENCE = pp.PHASEN_REFERENCE
PHASEO_REFERENCE = pp.PHASEO_REFERENCE
ACTIVE_PANEL_BASELINE = pp.ACTIVE_PANEL_BASELINE
PHASEP_REFERENCE = "improved_phasep_regret_aware_meta_allocator"
PHASEQ_BUCKET_REFERENCE = "improved_phaseq_regime_bucket_meta_allocator"
PHASER_R2_REFERENCE = "improved_phaser_light_abstention_overlay_allocator"
PHASER_R3_REFERENCE = "improved_phaser_fast_narrow_regret_allocator"
PHASET_T1_REFERENCE = "improved_phaset_soft_regime_posterior_allocator"
PHASEU_U1A_REFERENCE = "improved_phaseu_prod90_r2_10_holdings_blend"
PHASEU_U3_REFERENCE = "improved_phaseu_conditional_prod_r2_holdings_blend"
PHASEV_V1_REFERENCE = "improved_phasev_prod90_phasen_10_holdings_blend"

FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEH_REFERENCE,
    PHASEN_REFERENCE,
    PHASEO_REFERENCE,
    PHASEP_REFERENCE,
    PHASEQ_BUCKET_REFERENCE,
    PHASER_R2_REFERENCE,
    PHASER_R3_REFERENCE,
    PHASET_T1_REFERENCE,
    PHASEU_U1A_REFERENCE,
    PHASEU_U3_REFERENCE,
    PHASEV_V1_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

# 7-sleeve active panel (Phase W upgrade)
PANEL_7 = [
    "dual_momentum_topn",
    "composite_calm_trend_specialist",
    "composite_healthier_recovery_specialist",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
    "composite_structural_defense_sleeve",  # W1
]
PANEL_6 = PANEL_7[:-1]  # legacy panel without W1

W1_NAME = "composite_structural_defense_sleeve"

# Phase X candidate version names
X1_NAME = "improved_phasex_production_style_7sleeve"
X2_NAME = "improved_phasex_shadow_style_7sleeve"
X3_NAME = "improved_phasex_state_conditional_7sleeve"
X4_NAME = "improved_phasex_production_style_6sleeve_ablation"

PHASE_X_CANDIDATES = [X1_NAME, X2_NAME, X3_NAME, X4_NAME]

EPS = 1e-9
LOOKBACK = 156
MIN_HISTORY = 26


# --------------------------------------------------------------------------
#                        sleeve loading
# --------------------------------------------------------------------------

def load_sleeve_returns(sleeve: str) -> pd.Series:
    df = pd.read_csv(LAYER2A_DIR / f"strategy_returns_{sleeve}.csv", index_col=0, parse_dates=True)
    s = df["net_return"].astype(float)
    s.index.name = None
    return s.sort_index()


def load_sleeve_positions(sleeve: str) -> pd.DataFrame:
    df = pd.read_csv(LAYER2A_DIR / f"strategy_positions_{sleeve}.csv", index_col=0, parse_dates=True)
    df.index.name = None
    df = df.sort_index().fillna(0.0)
    return df


def load_market_state() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


def load_phase2b_predictions() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "phase2b_meta_predictions.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index()


# --------------------------------------------------------------------------
#                  state risk multipliers + ML adjustments
# --------------------------------------------------------------------------

# Hard state risk multiplier (controls total risk-on exposure).
# stressed_panic = 0 (full BIL); recovery_fragile = 0.55; recovery_confirmed = 0.80;
# calm_trend = 1.0; neutral_mixed = 0.95.
STATE_RISK_MULT = {
    "calm_trend": 1.00,
    "neutral_mixed": 0.95,
    "recovery_confirmed": 0.80,
    "recovery_fragile": 0.55,
    "stressed_panic": 0.00,
}


def regime_confidence_boost_offset(state: str, p_regime: float, p_trans: float, p_tail: float, mode: str) -> float:
    """Phase 2B meta-layer offset replicated from build_improvement_artifacts.py."""
    offset = 0.0
    apply_a = mode in {"regime_confidence_boost", "combo_abc"}
    apply_b = mode in {"combo_abc"}
    apply_c = mode in {"combo_abc"}

    if apply_a and state != "stressed_panic" and not np.isnan(p_regime):
        if p_regime >= 0.55:
            raw_boost = 0.10 * (p_regime - 0.55) / max(EPS, 1.0 - 0.55)
            offset += float(min(0.045, max(0.0, raw_boost)))
    if apply_b and state in {"neutral_mixed", "recovery_fragile"} and not np.isnan(p_trans):
        if p_trans > 0.60:
            offset += 0.04
        elif p_trans < 0.40:
            offset -= 0.03
    if apply_c and state != "stressed_panic" and not np.isnan(p_tail):
        if p_tail > 0.55:
            raw_suppress = -0.10 * (p_tail - 0.55) / max(EPS, 1.0 - 0.55)
            offset += float(max(-0.10, min(0.0, raw_suppress)))
    return offset


# --------------------------------------------------------------------------
#                    sleeve allocators (X1, X2, X3, X4)
# --------------------------------------------------------------------------

def inverse_vol_weights(sleeve_returns_panel: pd.DataFrame, as_of: pd.Timestamp, panel: list[str]) -> pd.Series:
    """Walk-forward inverse-volatility weights, normalized to sum to 1."""
    history = sleeve_returns_panel.loc[:as_of, panel].iloc[:-1] if len(sleeve_returns_panel.loc[:as_of]) > 1 else sleeve_returns_panel.loc[:as_of, panel]
    history = history.tail(LOOKBACK)
    if len(history) < MIN_HISTORY:
        return pd.Series(1.0 / len(panel), index=panel)
    vol = history.std(ddof=0).replace(0.0, np.nan)
    inv = 1.0 / vol
    inv = inv.fillna(inv.median()).fillna(1.0)
    inv = inv.clip(lower=EPS)
    w = inv / inv.sum()
    return w.reindex(panel).fillna(1.0 / len(panel))


def state_conditional_weights(
    sleeve_returns_panel: pd.DataFrame,
    market_state_history: pd.DataFrame,
    as_of: pd.Timestamp,
    panel: list[str],
    *,
    lookback: int = 156,
    min_state_obs: int = 16,
) -> pd.Series:
    """X3: state-conditional rank-Sharpe weights with inverse-vol fallback."""
    base = inverse_vol_weights(sleeve_returns_panel, as_of, panel)
    try:
        current_state = str(market_state_history.loc[as_of, "market_state"]) if as_of in market_state_history.index else ""
    except KeyError:
        current_state = ""
    if not current_state:
        return base
    history = market_state_history.loc[:as_of].iloc[:-1].tail(lookback)
    if history.empty:
        return base
    mask = history["market_state"] == current_state
    if int(mask.sum()) < min_state_obs:
        return base
    state_dates = history.index[mask]
    state_returns = sleeve_returns_panel.reindex(state_dates)[panel].dropna(how="all")
    if state_returns.empty:
        return base
    mu = state_returns.mean()
    sigma = state_returns.std(ddof=0).replace(0.0, np.nan)
    sharpe = (mu / sigma).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    # Convert sharpe to positive tilt: shift so worst is small positive, exp temper
    tilt = np.exp(2.0 * sharpe.clip(-2.0, 2.0))
    tilted = base * tilt.reindex(panel).fillna(1.0)
    if tilted.sum() <= 0:
        return base
    return tilted / tilted.sum()


# --------------------------------------------------------------------------
#                  build candidate weights (sleeve-level + ETF-level)
# --------------------------------------------------------------------------

def build_candidate(
    panel: list[str],
    *,
    meta_mode: str,
    state_conditional: bool,
    sleeve_returns_panel: pd.DataFrame,
    sleeve_positions: dict[str, pd.DataFrame],
    market_state_history: pd.DataFrame,
    phase2b_pred: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Compute weekly sleeve weights + ETF weights for one candidate.

    Returns:
      sleeve_weights_df: rows = dates, cols = panel + ['cash::BIL']
      etf_weights_df:    rows = dates, cols = ETF universe (incl 'BIL'), sums to 1
      net_returns:       weekly net return series (gross - turnover cost)
    """
    # Common date index = intersection of sleeve return panel and market state.
    common_idx = sleeve_returns_panel.index.intersection(market_state_history.index)
    common_idx = common_idx.sort_values()

    etf_universe = sorted({c for sleeve in panel for c in sleeve_positions[sleeve].columns})
    sleeve_w_rows = []
    etf_w_rows = []

    for date in common_idx:
        try:
            state = str(market_state_history.loc[date, "market_state"])
        except KeyError:
            state = "neutral_mixed"

        if state_conditional:
            base_w = state_conditional_weights(sleeve_returns_panel, market_state_history, date, panel)
        else:
            base_w = inverse_vol_weights(sleeve_returns_panel, date, panel)

        # Apply state risk multiplier
        risk_mult = STATE_RISK_MULT.get(state, 0.80)
        # Apply ML meta-layer offset to multiplier
        if meta_mode != "none":
            try:
                row = phase2b_pred.loc[date]
                p_regime = float(row.get("p_regime_confidence", np.nan))
                p_trans = float(row.get("p_transition_quality", np.nan))
                p_tail = float(row.get("p_tail_risk", np.nan))
            except KeyError:
                p_regime = p_trans = p_tail = np.nan
            offset = regime_confidence_boost_offset(state, p_regime, p_trans, p_tail, meta_mode)
            risk_mult = float(np.clip(risk_mult + offset, 0.0, 1.0))

        # Risk-on share = risk_mult; cash share = 1 - risk_mult
        risk_share = float(np.clip(risk_mult, 0.0, 1.0))
        cash_share = 1.0 - risk_share

        sleeve_alloc = base_w * risk_share
        sleeve_alloc["cash::BIL"] = cash_share
        sleeve_w_rows.append(pd.Series(sleeve_alloc, name=date))

        # Roll up to ETF level
        etf_w = pd.Series(0.0, index=etf_universe)
        for sleeve in panel:
            sleeve_pos_today = sleeve_positions[sleeve].reindex([date]).fillna(0.0).iloc[0]
            etf_w = etf_w.add(sleeve_alloc[sleeve] * sleeve_pos_today.reindex(etf_universe).fillna(0.0), fill_value=0.0)
        # cash from BIL parking + sleeve cash share
        etf_w["BIL"] = float(etf_w.get("BIL", 0.0)) + cash_share
        # Renormalize (numerical safety)
        total = float(etf_w.sum())
        if total > EPS:
            etf_w = etf_w / total
        else:
            etf_w[:] = 0.0
            etf_w["BIL"] = 1.0
        etf_w_rows.append(etf_w.rename(date))

    sleeve_weights_df = pd.DataFrame(sleeve_w_rows).fillna(0.0)
    sleeve_weights_df.index.name = None
    etf_weights_df = pd.DataFrame(etf_w_rows).fillna(0.0)
    etf_weights_df.index.name = None

    # Compute net returns from ETF weights and weekly returns.
    # Weights at date t earn return realized at t+1 (one-week-ahead alignment).
    weekly_returns = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", index_col=0, parse_dates=True)
    weekly_returns.index.name = None
    weekly_returns = weekly_returns.sort_index()
    next_week_returns = weekly_returns.shift(-1)
    common_idx_returns = etf_weights_df.index.intersection(next_week_returns.index)
    common_etfs = [c for c in etf_weights_df.columns if c in next_week_returns.columns]
    aligned_w = etf_weights_df.loc[common_idx_returns, common_etfs]
    aligned_r = next_week_returns.loc[common_idx_returns, common_etfs].fillna(0.0)
    gross_returns = (aligned_w * aligned_r).sum(axis=1)
    # Turnover cost: 5 bps per unit change weight, half-cost (one-side)
    turnover = aligned_w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * 0.0005 * 0.5
    net_returns = gross_returns - cost

    return sleeve_weights_df, etf_weights_df, net_returns


# --------------------------------------------------------------------------
#                  W1 diagnostics
# --------------------------------------------------------------------------

def w1_diagnostics(sleeve_weights: pd.DataFrame, market_state_history: pd.DataFrame, name: str) -> dict:
    if W1_NAME not in sleeve_weights.columns:
        return {
            "version_name": name,
            "panel_size": int(len([c for c in sleeve_weights.columns if not c.startswith("cash::")])),
            "w1_in_panel": False,
            "avg_w1_weight": 0.0,
            "max_w1_weight": 0.0,
            "obs": int(len(sleeve_weights)),
        }
    w1 = sleeve_weights[W1_NAME]
    return {
        "version_name": name,
        "panel_size": int(len([c for c in sleeve_weights.columns if not c.startswith("cash::")])),
        "w1_in_panel": True,
        "avg_w1_weight": float(w1.mean()),
        "median_w1_weight": float(w1.median()),
        "max_w1_weight": float(w1.max()),
        "p90_w1_weight": float(w1.quantile(0.90)),
        "obs": int(len(sleeve_weights)),
    }


def w1_state_usage(sleeve_weights: pd.DataFrame, market_state_history: pd.DataFrame, name: str) -> pd.DataFrame:
    if W1_NAME not in sleeve_weights.columns:
        return pd.DataFrame()
    aligned = sleeve_weights[[W1_NAME]].join(market_state_history[["market_state"]], how="inner")
    rows = []
    for state, sub in aligned.groupby("market_state"):
        rows.append({
            "version_name": name,
            "market_state": state,
            "observations": int(len(sub)),
            "avg_w1_weight": float(sub[W1_NAME].mean()),
            "median_w1_weight": float(sub[W1_NAME].median()),
            "max_w1_weight": float(sub[W1_NAME].max()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
#                  validation bundle
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
        )
        if research:
            return "Research-only"
        return "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_x_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_x_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_x_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_x_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_x_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_x_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase X — Allocator Rerun on the Upgraded 7-Sleeve Panel",
        "panel_7": PANEL_7,
        "panel_6": PANEL_6,
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_x_candidates": list(candidate_names),
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
    (LAYER3_DIR / "phase_x_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {"full": full_df, "dev": dev_df, "holdout": holdout_df, "rolling": rolling_df, "pairwise": pairwise_df, "classification": classification_df}


# --------------------------------------------------------------------------
#                                 main
# --------------------------------------------------------------------------

def main() -> None:
    print("Loading sleeve panel...")
    sleeve_returns = pd.DataFrame({s: load_sleeve_returns(s) for s in PANEL_7}).dropna(how="all")
    sleeve_positions = {s: load_sleeve_positions(s) for s in PANEL_7}
    market_state_history = load_market_state()
    phase2b_pred = load_phase2b_predictions()

    # Note: weights at t earn returns from t to t+1 (we use weekly_returns.shift(-1) inside build_candidate)

    print("\n=== Building X1 (production-style on 7-sleeve panel) ===")
    x1_sw, x1_ew, x1_ret = build_candidate(
        PANEL_7,
        meta_mode="regime_confidence_boost",
        state_conditional=False,
        sleeve_returns_panel=sleeve_returns,
        sleeve_positions=sleeve_positions,
        market_state_history=market_state_history,
        phase2b_pred=phase2b_pred,
    )

    print("=== Building X2 (shadow-style on 7-sleeve panel) ===")
    x2_sw, x2_ew, x2_ret = build_candidate(
        PANEL_7,
        meta_mode="combo_abc",
        state_conditional=False,
        sleeve_returns_panel=sleeve_returns,
        sleeve_positions=sleeve_positions,
        market_state_history=market_state_history,
        phase2b_pred=phase2b_pred,
    )

    print("=== Building X3 (state-conditional on 7-sleeve panel) ===")
    x3_sw, x3_ew, x3_ret = build_candidate(
        PANEL_7,
        meta_mode="none",
        state_conditional=True,
        sleeve_returns_panel=sleeve_returns,
        sleeve_positions=sleeve_positions,
        market_state_history=market_state_history,
        phase2b_pred=phase2b_pred,
    )

    print("=== Building X4 (production-style on 6-sleeve panel — ablation) ===")
    sleeve_returns_6 = sleeve_returns[PANEL_6]
    sleeve_positions_6 = {s: sleeve_positions[s] for s in PANEL_6}
    x4_sw, x4_ew, x4_ret = build_candidate(
        PANEL_6,
        meta_mode="regime_confidence_boost",
        state_conditional=False,
        sleeve_returns_panel=sleeve_returns_6,
        sleeve_positions=sleeve_positions_6,
        market_state_history=market_state_history,
        phase2b_pred=phase2b_pred,
    )

    bundles = [
        (X1_NAME, x1_sw, x1_ew, x1_ret),
        (X2_NAME, x2_sw, x2_ew, x2_ret),
        (X3_NAME, x3_sw, x3_ew, x3_ret),
        (X4_NAME, x4_sw, x4_ew, x4_ret),
    ]

    print("\n=== Saving portfolio_version files ===")
    w1_diag_rows = []
    w1_state_rows = []
    for name, sw, ew, ret in bundles:
        sw.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")
        ew.to_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        # Build returns frame matching expected schema
        gross = ret  # Already gross-net here (no further cost adj)
        turnover = ew.diff().abs().sum(axis=1).fillna(0.0)
        cost = turnover * 0.0005 * 0.5
        wealth = (1.0 + ret.fillna(0.0)).cumprod()
        drawdown = wealth / wealth.cummax() - 1.0
        ret_df = pd.DataFrame({
            "gross_return": gross + cost,
            "net_return": ret,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": drawdown,
        })
        ret_df.to_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        # diagnostics
        w1_diag_rows.append(w1_diagnostics(sw, market_state_history, name))
        sus = w1_state_usage(sw, market_state_history, name)
        if not sus.empty:
            w1_state_rows.append(sus)

    pd.DataFrame(w1_diag_rows).to_csv(LAYER3_DIR / "phase_x_w1_diagnostics.csv", index=False)
    if w1_state_rows:
        pd.concat(w1_state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_x_state_w1_usage.csv", index=False)

    print("\n=== Validation under Phase D rules ===")
    bundle = build_validation_bundle(PHASE_X_CANDIDATES)

    print("\n=== Phase X — full-history metrics ===")
    full_view = bundle["full"][bundle["full"]["version_name"].isin([PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASER_R3_REFERENCE, PHASEV_V1_REFERENCE] + PHASE_X_CANDIDATES)][[
        "version_name", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "raw_target_composite"
    ]]
    print(full_view.to_string(index=False))

    print("\n=== Phase X — holdout metrics ===")
    holdout_view = bundle["holdout"][bundle["holdout"]["version_name"].isin([PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASER_R3_REFERENCE, PHASEV_V1_REFERENCE] + PHASE_X_CANDIDATES)][[
        "version_name", "ann_return", "sharpe", "max_drawdown", "raw_target_composite"
    ]]
    print(holdout_view.to_string(index=False))

    print("\n=== Phase X — pairwise vs production ===")
    pw = bundle["pairwise"][bundle["pairwise"]["version_name"].isin(PHASE_X_CANDIDATES)][[
        "version_name", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
        "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production",
        "rolling_mean_raw_delta_vs_production", "bootstrap_prob_vs_production",
        "max_drawdown_delta_vs_production", "cvar_delta_vs_production",
    ]]
    print(pw.to_string(index=False))

    print("\n=== Phase X — classification ===")
    cls = bundle["classification"][["version_name", "classification"]]
    print(cls.to_string(index=False))

    print("\n=== Phase X — W1 weight diagnostics ===")
    print(pd.DataFrame(w1_diag_rows).to_string(index=False))

    if w1_state_rows:
        print("\n=== Phase X — W1 state-conditional usage (X1) ===")
        sus_x1 = pd.concat(w1_state_rows, ignore_index=True)
        sus_x1 = sus_x1[sus_x1["version_name"] == X1_NAME]
        print(sus_x1.to_string(index=False))

    print("\nSaved Phase X artifacts.")


if __name__ == "__main__":
    main()
