"""Phase AA — Production-Anchored Holdings Blend with Z1.

Phase Z proved that:
  * the upgraded 7-sleeve panel is real
  * W1 (composite_structural_defense_sleeve) is real
  * but both major allocator families this project uses (inverse-vol per
    Phases X / Y, HRP per Phase Z) over-fund W1 against the
    MAX_SLEEVE_WEIGHT = 0.45 cap and give up too much absolute return to
    clear Phase D's return-side gates against the production pin
  * Z1 (improved_phasez_production_hrp_7sleeve) is now the strongest
    DEFENSIVE-CEILING reference (Sharpe 0.93, MDD -8.6%, CVaR -1.5%,
    holdout Sharpe 2.37) — but its absolute return is only 4.24% vs
    production's 6.90%, so it cannot be deployed standalone
  * production (improved_phase2b_regime_confidence_boost) remains the
    DEPLOYABLE return anchor

Phase AA is the narrow next step recommended by the Phase Z report:
  > test whether direct holdings-level blending of production with Z1
  > preserves production's return profile while importing some of Z1's
  > defensive / Sharpe / tail benefit

Candidates (small, high-conviction set — no broad blend grid):

  AA1 — static 95 / 5 production + Z1 holdings blend
        Most conservative test. Preserves nearly all of production's
        return engine. Tests whether even a tiny dose of Z1 imports
        defensive value cheaply.

  AA2 — static 90 / 10 production + Z1 holdings blend
        Phase V-style 90 / 10 anchor weighting. Z1's defensive-ceiling
        profile is structurally orthogonal to production in a way that
        no prior research-blend partner is, so this is the natural
        primary test.

  AA3 — state-conditional production + Z1 holdings blend
        Causal, walk-forward-safe schedule indexed on
        market_state_history.market_state at t-1:
          calm_trend           -> a = 0.95  (light Z1: production runs hot)
          neutral_mixed        -> a = 0.92  (mild defense)
          recovery_confirmed   -> a = 0.90  (mild defense)
          recovery_fragile     -> a = 0.85  (heavier Z1: transition risk)
          stressed_panic       -> a = 0.85  (heavier Z1: drawdown clip)
        Average a ≈ 0.91 — between AA1 and AA2 but expressed as
        defense-when-needed instead of constant tilt.

Optional AA4 added at runtime only if the AA1 / AA2 / AA3 diagnostics
clearly point to one missing test.

Holdings-blend math:
  blended_weight(t) = a(t) * prod_weight(t) + (1 - a(t)) * z1_weight(t)
  inherent_net_return(t) = a(t) * prod_net(t) + (1 - a(t)) * z1_net(t)
  This linear-in-stored-returns convention preserves each component's
  exact overlay accounting (production has minor formula drift vs the
  weights-only reconstruction; Z1 reconstructs to floating-point).
  For AA3, an additional 5 bp half-spread cost is applied to the
  schedule-induced rebalance whenever a(t) changes between weeks.

Outputs to data/05_layer3_portfolio_construction/:
  portfolio_version_{returns,weights,sleeve_weights}_{AA1,AA2,AA3,...}.csv
  phase_aa_candidate_metrics_{full,dev,holdout}.csv
  phase_aa_pairwise_validation.csv
  phase_aa_rolling_origin_summary.csv
  phase_aa_candidate_classification.csv
  phase_aa_blend_diagnostics.csv
  phase_aa_state_blend_schedule.csv
  phase_aa_validation_protocol.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase_d_validate as pdv
import phase_p_evaluate as ppe
import phase_p_meta_allocator as pp


ROOT = Path(__file__).resolve().parents[1]
LAYER1_DIR = ROOT / "data" / "01_data_hub"
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

TURNOVER_HALFSPREAD = 0.0005 * 0.5  # 5 bp half-spread (matches Phase Z / production)

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
PHASEX_X1_REFERENCE = "improved_phasex_production_style_7sleeve"
PHASEZ_Z1_REFERENCE = "improved_phasez_production_hrp_7sleeve"

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
    PHASEX_X1_REFERENCE,
    PHASEZ_Z1_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]

# AA3 conditional schedule: a(t) = production share at t (Z1 share = 1 - a(t))
AA3_STATE_SCHEDULE = {
    "calm_trend": 0.95,
    "neutral_mixed": 0.92,
    "recovery_confirmed": 0.90,
    "recovery_fragile": 0.85,
    "stressed_panic": 0.85,
}
AA3_DEFAULT_A = 0.92  # used if state is missing


# --------------------------------------------------------------------------
# data loading
# --------------------------------------------------------------------------

def load_weights(name: str) -> pd.DataFrame:
    df = pd.read_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index().fillna(0.0)


def load_returns(name: str) -> pd.DataFrame:
    df = pd.read_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv", index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index()


def load_market_state() -> pd.DataFrame:
    df = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df.set_index("Date").sort_index()


# --------------------------------------------------------------------------
# blend builders
# --------------------------------------------------------------------------

def build_static_blend(
    a: float,
    prod_w: pd.DataFrame,
    z1_w: pd.DataFrame,
    prod_ret: pd.DataFrame,
    z1_ret: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Return (blended_weights, blended_net_return, blended_turnover, a_series)."""
    common = prod_w.index.intersection(z1_w.index)
    blended_w = a * prod_w.loc[common] + (1.0 - a) * z1_w.loc[common]

    common_ret = prod_ret.index.intersection(z1_ret.index)
    inherent_net = a * prod_ret.loc[common_ret, "net_return"] + (1.0 - a) * z1_ret.loc[common_ret, "net_return"]

    # Static blend: no schedule-induced cost beyond what's already baked into
    # each component's own net return. Component costs are already in each
    # net_return column. Turnover series is reconstructed from blended weights
    # for reporting purposes.
    blended_turnover = blended_w.diff().abs().sum(axis=1).fillna(0.0)
    a_series = pd.Series(a, index=common)
    return blended_w, inherent_net.reindex(common).fillna(0.0), blended_turnover.reindex(common).fillna(0.0), a_series


def build_conditional_blend(
    schedule: dict,
    default_a: float,
    prod_w: pd.DataFrame,
    z1_w: pd.DataFrame,
    prod_ret: pd.DataFrame,
    z1_ret: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """State-conditional blend with t-1 lagged state for causal safety.

    Schedule cost: when a(t) changes between weeks, the implied rebalance
    of the inter-component spread incurs additional 5 bp half-spread cost
    proportional to |a(t)-a(t-1)| * |prod_w(t) - z1_w(t)|.sum().
    """
    common = prod_w.index.intersection(z1_w.index)
    state = market_state_history["market_state"].reindex(common).ffill()
    # 1-week lag for causal safety: the blend weight applied at week t uses
    # the state observed at the end of week t-1.
    state_lag = state.shift(1)
    a_series = state_lag.map(schedule).fillna(default_a).astype(float)

    a_arr = a_series.values[:, None]  # column vector
    blended_w_values = a_arr * prod_w.loc[common].values + (1.0 - a_arr) * z1_w.loc[common].values
    blended_w = pd.DataFrame(blended_w_values, index=common, columns=prod_w.columns)

    common_ret = prod_ret.index.intersection(z1_ret.index)
    aligned = a_series.reindex(common_ret).ffill().fillna(default_a)
    inherent_net = aligned * prod_ret.loc[common_ret, "net_return"] + (1.0 - aligned) * z1_ret.loc[common_ret, "net_return"]

    # Schedule transition cost
    da = aligned.diff().abs().fillna(0.0)
    spread = (prod_w.loc[common_ret] - z1_w.loc[common_ret]).abs().sum(axis=1)
    schedule_cost = (da * spread).fillna(0.0) * TURNOVER_HALFSPREAD
    blended_net = (inherent_net - schedule_cost).reindex(common).fillna(0.0)

    blended_turnover = blended_w.diff().abs().sum(axis=1).fillna(0.0)
    return blended_w, blended_net, blended_turnover.reindex(common).fillna(0.0), a_series.reindex(common)


# --------------------------------------------------------------------------
# pseudo-sleeve weight bookkeeping (so the validator can read a sleeve_weights
# file even though this is a holdings-level blend across two entire portfolios)
# --------------------------------------------------------------------------

def build_pseudo_sleeve_weights(a_series: pd.Series) -> pd.DataFrame:
    return pd.DataFrame({
        "production_anchor": a_series.values,
        "z1_overlay": (1.0 - a_series).values,
    }, index=a_series.index)


# --------------------------------------------------------------------------
# returns / wealth / drawdown bookkeeping
# --------------------------------------------------------------------------

def write_portfolio_files(name: str, weights: pd.DataFrame, net: pd.Series, turnover: pd.Series, a_series: pd.Series, schedule_cost: pd.Series | None = None):
    weights = weights.sort_index()
    weights.to_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")

    sw = build_pseudo_sleeve_weights(a_series)
    sw.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")

    cost = (turnover.fillna(0.0) * 0.0).copy()  # static blend cost is already in inherent net returns
    if schedule_cost is not None:
        cost = schedule_cost.reindex(net.index).fillna(0.0)
    gross = net + cost
    wealth = (1.0 + net.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    ret_df = pd.DataFrame({
        "gross_return": gross,
        "net_return": net,
        "turnover": turnover.reindex(net.index).fillna(0.0),
        "cost": cost,
        "wealth": wealth,
        "drawdown": drawdown,
    })
    ret_df.to_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")


# --------------------------------------------------------------------------
# diagnostics
# --------------------------------------------------------------------------

def blend_diagnostics(name: str, blended_w: pd.DataFrame, prod_w: pd.DataFrame, z1_w: pd.DataFrame, a_series: pd.Series) -> dict:
    common = blended_w.index
    avg_a = float(a_series.mean())
    avg_z1_share = 1.0 - avg_a
    # ETF deviations from pure production
    dev_from_prod = (blended_w - prod_w.loc[common]).abs().sum(axis=1)
    dev_from_z1 = (blended_w - z1_w.loc[common]).abs().sum(axis=1)
    return {
        "version_name": name,
        "obs": int(len(common)),
        "avg_production_share": avg_a,
        "avg_z1_share": avg_z1_share,
        "avg_etf_l1_dev_from_pure_production": float(dev_from_prod.mean()),
        "avg_etf_l1_dev_from_pure_z1": float(dev_from_z1.mean()),
        "p90_etf_l1_dev_from_pure_production": float(dev_from_prod.quantile(0.90)),
        "p90_etf_l1_dev_from_pure_z1": float(dev_from_z1.quantile(0.90)),
    }


def state_blend_schedule(name: str, a_series: pd.Series, market_state_history: pd.DataFrame) -> pd.DataFrame:
    aligned = pd.concat([
        a_series.rename("a"),
        market_state_history["market_state"].reindex(a_series.index).rename("market_state"),
    ], axis=1).dropna()
    rows = []
    for state, sub in aligned.groupby("market_state"):
        rows.append({
            "version_name": name,
            "market_state": state,
            "observations": int(len(sub)),
            "avg_production_share": float(sub["a"].mean()),
            "avg_z1_share": float((1.0 - sub["a"]).mean()),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# validation bundle (mirrors Phase X / Y / Z)
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
        prod_pass = (
            row["full_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["full_raw_composite_delta_vs_production_min"]
            and row["holdout_raw_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_raw_composite_delta_vs_production_min"]
            and row["holdout_sharpe_delta_vs_production"] >= ppe.PRODUCTION_RULE["holdout_sharpe_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= ppe.PRODUCTION_RULE["rolling_raw_win_rate_vs_production_min"]
            and row["rolling_mean_raw_delta_vs_production"] > ppe.PRODUCTION_RULE["rolling_mean_raw_delta_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= ppe.PRODUCTION_RULE["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= ppe.PRODUCTION_RULE["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= ppe.PRODUCTION_RULE["cvar_worsening_cap"]
        )
        if prod_pass:
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
        return "Research-only" if research else "Drop"

    classification_df["classification"] = classification_df.apply(classify, axis=1)

    full_df.to_csv(LAYER3_DIR / "phase_aa_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_aa_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_aa_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_aa_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_aa_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_aa_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase AA — Production-Anchored Holdings Blend with Z1",
        "anchor": PRODUCTION_PIN,
        "partner": PHASEZ_Z1_REFERENCE,
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_aa_candidates": list(candidate_names),
        "production_rule": ppe.PRODUCTION_RULE,
        "shadow_rule": ppe.SHADOW_RULE,
        "holdout_weeks": pdv.HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": pdv.ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": pdv.ROLLING_TEST_WEEKS,
            "step_weeks": pdv.ROLLING_STEP_WEEKS,
        },
        "bootstrap": {"method": "moving_block_bootstrap", "block_weeks": pdv.BOOTSTRAP_BLOCK_WEEKS, "samples": pdv.BOOTSTRAP_SAMPLES},
        "blend_definition": {
            "AA1_static_95_5": {"a": 0.95},
            "AA2_static_90_10": {"a": 0.90},
            "AA3_state_conditional": AA3_STATE_SCHEDULE,
        },
        "blend_math": "blended_w(t) = a(t) * prod_w(t) + (1 - a(t)) * z1_w(t); blended_net(t) = a(t) * prod_net(t) + (1 - a(t)) * z1_net(t); AA3 schedule transitions add 5 bp half-spread cost proportional to |a(t)-a(t-1)| * |prod_w(t)-z1_w(t)|.sum().",
    }
    (LAYER3_DIR / "phase_aa_validation_protocol.json").write_text(json.dumps(protocol, indent=2))
    return {"full": full_df, "dev": dev_df, "holdout": holdout_df, "rolling": rolling_df, "pairwise": pairwise_df, "classification": classification_df}


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

AA1_NAME = "improved_phaseaa_prod95_z1_05_holdings_blend"
AA2_NAME = "improved_phaseaa_prod90_z1_10_holdings_blend"
AA3_NAME = "improved_phaseaa_state_conditional_prod_z1_holdings_blend"
PHASE_AA_CANDIDATES = [AA1_NAME, AA2_NAME, AA3_NAME]


def main() -> None:
    print("Loading production and Z1 holdings artifacts...")
    prod_w = load_weights(PRODUCTION_PIN)
    z1_w = load_weights(PHASEZ_Z1_REFERENCE)
    prod_ret = load_returns(PRODUCTION_PIN)
    z1_ret = load_returns(PHASEZ_Z1_REFERENCE)
    market_state_history = load_market_state()

    assert list(prod_w.columns) == list(z1_w.columns), "ETF universes differ between production and Z1"
    assert prod_w.index.equals(z1_w.index), "Date indexes differ between production and Z1"
    print(f"  prod weights: {prod_w.shape}, Z1 weights: {z1_w.shape}, range: {prod_w.index.min().date()} -> {prod_w.index.max().date()}")

    diag_rows = []
    state_rows = []

    print("\n=== Building AA1 (static 95/5) ===")
    aa1_w, aa1_net, aa1_to, aa1_a = build_static_blend(0.95, prod_w, z1_w, prod_ret, z1_ret)
    write_portfolio_files(AA1_NAME, aa1_w, aa1_net, aa1_to, aa1_a, schedule_cost=None)
    diag_rows.append(blend_diagnostics(AA1_NAME, aa1_w, prod_w, z1_w, aa1_a))
    state_rows.append(state_blend_schedule(AA1_NAME, aa1_a, market_state_history))

    print("=== Building AA2 (static 90/10) ===")
    aa2_w, aa2_net, aa2_to, aa2_a = build_static_blend(0.90, prod_w, z1_w, prod_ret, z1_ret)
    write_portfolio_files(AA2_NAME, aa2_w, aa2_net, aa2_to, aa2_a, schedule_cost=None)
    diag_rows.append(blend_diagnostics(AA2_NAME, aa2_w, prod_w, z1_w, aa2_a))
    state_rows.append(state_blend_schedule(AA2_NAME, aa2_a, market_state_history))

    print("=== Building AA3 (state-conditional, t-1 lagged state) ===")
    aa3_w, aa3_net, aa3_to, aa3_a = build_conditional_blend(
        AA3_STATE_SCHEDULE, AA3_DEFAULT_A, prod_w, z1_w, prod_ret, z1_ret, market_state_history,
    )
    # Reconstruct schedule cost for AA3 to write to portfolio_version_returns
    common_ret = prod_ret.index.intersection(z1_ret.index)
    aligned_a = aa3_a.reindex(common_ret).ffill().fillna(AA3_DEFAULT_A)
    da = aligned_a.diff().abs().fillna(0.0)
    spread = (prod_w.loc[common_ret] - z1_w.loc[common_ret]).abs().sum(axis=1)
    aa3_schedule_cost = (da * spread).fillna(0.0) * TURNOVER_HALFSPREAD
    write_portfolio_files(AA3_NAME, aa3_w, aa3_net, aa3_to, aa3_a, schedule_cost=aa3_schedule_cost)
    diag_rows.append(blend_diagnostics(AA3_NAME, aa3_w, prod_w, z1_w, aa3_a))
    state_rows.append(state_blend_schedule(AA3_NAME, aa3_a, market_state_history))

    pd.DataFrame(diag_rows).to_csv(LAYER3_DIR / "phase_aa_blend_diagnostics.csv", index=False)
    if state_rows:
        pd.concat(state_rows, ignore_index=True).to_csv(LAYER3_DIR / "phase_aa_state_blend_schedule.csv", index=False)

    print("\n=== Validation under Phase D rules ===")
    bundle = build_validation_bundle(PHASE_AA_CANDIDATES)

    print("\n=== Phase AA — full-history metrics ===")
    full_view = bundle["full"][bundle["full"]["version_name"].isin([
        PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASEU_U3_REFERENCE, PHASER_R3_REFERENCE,
        PHASEV_V1_REFERENCE, PHASEX_X1_REFERENCE, PHASEZ_Z1_REFERENCE,
    ] + PHASE_AA_CANDIDATES)][[
        "version_name", "ann_return", "ann_vol", "sharpe", "max_drawdown",
        "calmar", "cvar_5", "turnover", "raw_target_composite",
    ]]
    print(full_view.to_string(index=False))

    print("\n=== Phase AA — holdout metrics ===")
    holdout_view = bundle["holdout"][bundle["holdout"]["version_name"].isin([
        PRODUCTION_PIN, SHADOW_PIN, PHASEU_U1A_REFERENCE, PHASEU_U3_REFERENCE, PHASER_R3_REFERENCE,
        PHASEV_V1_REFERENCE, PHASEX_X1_REFERENCE, PHASEZ_Z1_REFERENCE,
    ] + PHASE_AA_CANDIDATES)][[
        "version_name", "ann_return", "sharpe", "max_drawdown", "raw_target_composite",
    ]]
    print(holdout_view.to_string(index=False))

    print("\n=== Phase AA — pairwise vs production ===")
    pw = bundle["pairwise"][bundle["pairwise"]["version_name"].isin(PHASE_AA_CANDIDATES)][[
        "version_name", "full_raw_delta_vs_production", "holdout_raw_delta_vs_production",
        "holdout_sharpe_delta_vs_production", "rolling_raw_win_rate_vs_production",
        "rolling_mean_raw_delta_vs_production", "bootstrap_prob_vs_production",
        "max_drawdown_delta_vs_production", "cvar_delta_vs_production",
    ]]
    print(pw.to_string(index=False))

    print("\n=== Phase AA — pairwise vs U1a (closest reference) ===")
    pw_u = bundle["pairwise"][bundle["pairwise"]["version_name"].isin(PHASE_AA_CANDIDATES)][[
        "version_name", "full_raw_delta_vs_u1a", "holdout_raw_delta_vs_u1a",
        "holdout_sharpe_delta_vs_u1a", "bootstrap_prob_vs_u1a",
    ]]
    print(pw_u.to_string(index=False))

    print("\n=== Phase AA — classification ===")
    cls = bundle["classification"][["version_name", "classification"]]
    print(cls.to_string(index=False))

    print("\n=== Phase AA — blend diagnostics ===")
    print(pd.DataFrame(diag_rows).to_string(index=False))

    print("\n=== Phase AA — AA3 state-conditional schedule (realized) ===")
    aa3_state = pd.concat(state_rows, ignore_index=True)
    aa3_state = aa3_state[aa3_state["version_name"] == AA3_NAME]
    print(aa3_state.to_string(index=False))

    print("\nSaved Phase AA artifacts.")


if __name__ == "__main__":
    main()
