"""Phase DD — Production-family additive tilt consuming Phase CC's
`defensive_overlay_hint`.

Design rule:
  Phase DD does NOT replace production logic. It takes production's
  saved ETF-level weights and applies a small additive defensive tilt
  in weeks where Phase CC's refined state engine indicates rising
  deterioration AND production is not already deeply defensive.

  When the tilt triggers in week t:
      new_w[etf]   = prod_w[etf] * (1 - delta)        for etf != BIL
      new_w["BIL"] = prod_w["BIL"] + delta * (1 - prod_w["BIL"])

  When the tilt does NOT trigger in week t:
      new_w = prod_w  (exact production)

  This guarantees:
    - candidate ≡ production whenever the gate is off (full ablate-ability),
    - the tilt is one-parameter (delta) per variant,
    - the tilt cannot "increase defense everywhere" (the BIL<0.50 guard
      for DD1/DD2 prevents stacking on already-defensive weeks; DD3 only
      fires on the new neutral_deteriorating state),
    - weights still sum to 1 (the rescaling is exact),
    - turnover is bounded analytically by 2*delta*(1 - prod_w["BIL"]).

Variants (≤3 per spec):
  DD1 — hint_light          (delta = 0.05, BIL<0.50 guard)
  DD2 — hint_moderate       (delta = 0.10, BIL<0.50 guard)
  DD3 — hint_state_gated    (delta = 0.10, refined_state == neutral_deteriorating only)

Validation against the same 13-member fixed comparator set used by
Phase Z / AA / BB / Phase D, augmented with Z1, AA1/AA2/AA3, BB1/BB2/BB3
where present.

Outputs:
  data/05_layer3_portfolio_construction/portfolio_version_{returns,weights,sleeve_weights}_improved_phasedd_*.csv
  data/05_layer3_portfolio_construction/phase_dd_candidate_metrics_full.csv
  data/05_layer3_portfolio_construction/phase_dd_candidate_metrics_holdout.csv
  data/05_layer3_portfolio_construction/phase_dd_pairwise_validation.csv
  data/05_layer3_portfolio_construction/phase_dd_state_summary.csv
  data/05_layer3_portfolio_construction/phase_dd_selection_table.csv
  data/05_layer3_portfolio_construction/phase_dd_protocol.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc
import phase_d_validate as pdv
import phase_p_evaluate as ppe


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
HALFSPREAD = roc.DEFAULT_HALFSPREAD
CASH_TICKER = "BIL"

DD1_NAME = "improved_phasedd_hint_light"
DD2_NAME = "improved_phasedd_hint_moderate"
DD3_NAME = "improved_phasedd_hint_state_gated"
PHASE_DD_CANDIDATES = [DD1_NAME, DD2_NAME, DD3_NAME]

# Variant configs
VARIANTS = {
    DD1_NAME: {"delta": 0.05, "gate_kind": "hint_with_bil_guard", "bil_guard": 0.50,
               "description": "Tilt 5% of risk budget into BIL when defensive_overlay_hint == +1 AND production BIL exposure < 50%."},
    DD2_NAME: {"delta": 0.10, "gate_kind": "hint_with_bil_guard", "bil_guard": 0.50,
               "description": "Tilt 10% of risk budget into BIL when defensive_overlay_hint == +1 AND production BIL exposure < 50%."},
    DD3_NAME: {"delta": 0.10, "gate_kind": "refined_state_gated",
               "trigger_states": ["neutral_deteriorating"],
               "description": "Tilt 10% of risk budget into BIL ONLY in `neutral_deteriorating` weeks (the new state Phase CC created)."},
}

# Comparator set (13 members + augmented with Z1, AA, BB present-on-disk)
COMPARATOR_BASE = [
    PRODUCTION, SHADOW,
    "improved_recovery_split_with_persistence_gating",  # Phase H reference
    "improved_phasen_ambitious_ml_allocator",            # Phase N
    "improved_phaseo_decision_aware_allocator",          # Phase O
    "improved_phasep_regret_aware_meta_allocator",       # Phase P
    "improved_phaseq_regime_bucket_meta_allocator",      # Phase Q bucket
    "improved_phaser_light_abstention_overlay_allocator",# Phase R r2
    "improved_phaser_fast_narrow_regret_allocator",      # Phase R r3
    "improved_phaset_soft_regime_posterior_allocator",   # Phase T t1
    "improved_phaseu_prod90_r2_10_holdings_blend",       # Phase U u1a
    "improved_phaseu_conditional_prod_r2_holdings_blend",# Phase U u3
    "improved_phasev_prod90_phasen_10_holdings_blend",   # Phase V v1
]
COMPARATOR_AUGMENT = [
    "improved_phasez_production_hrp_7sleeve",
    "improved_phaseaa_prod95_z1_05_holdings_blend",
    "improved_phaseaa_prod90_z1_10_holdings_blend",
    "improved_phaseaa_state_conditional_prod_z1_holdings_blend",
    "improved_phasebb_w1cap_055_hrp_7sleeve",
    "improved_phasebb_w1cap_060_hrp_7sleeve",
    "improved_phasebb_w1cap_055_others_050_hrp_7sleeve",
]


def load_refined_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history_refined.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def gate_mask(prod_weights: pd.DataFrame, refined: pd.DataFrame, variant_cfg: dict) -> pd.Series:
    """Return a boolean Series indexed by prod_weights.index. True where the
    Phase DD tilt should be applied."""
    aligned = refined.reindex(prod_weights.index)
    if variant_cfg["gate_kind"] == "hint_with_bil_guard":
        hint = aligned["defensive_overlay_hint"].fillna(0).astype(int)
        bil = prod_weights.get(CASH_TICKER, pd.Series(0.0, index=prod_weights.index))
        gate = (hint == 1) & (bil < variant_cfg["bil_guard"])
    elif variant_cfg["gate_kind"] == "refined_state_gated":
        states = aligned["refined_state"].astype(str).fillna("")
        gate = states.isin(variant_cfg["trigger_states"])
    else:
        raise ValueError(f"unknown gate_kind: {variant_cfg['gate_kind']}")
    return gate.fillna(False)


def apply_tilt(prod_weights: pd.DataFrame, gate: pd.Series, delta: float) -> pd.DataFrame:
    """Apply scale-non-BIL-by-(1-delta) tilt only on `gate==True` rows."""
    new_w = prod_weights.copy()
    if CASH_TICKER not in new_w.columns:
        new_w[CASH_TICKER] = 0.0
    other_cols = [c for c in new_w.columns if c != CASH_TICKER]
    g = gate.reindex(new_w.index).fillna(False).values
    if g.any():
        # vectorized: for gate rows, scale others by (1-delta), add freed share to BIL
        bil = new_w[CASH_TICKER].values
        rest_sum = new_w[other_cols].sum(axis=1).values  # = 1 - bil typically
        # New BIL = bil + delta * rest_sum
        new_bil = bil.copy()
        new_bil[g] = bil[g] + delta * rest_sum[g]
        # Scale other ETFs by (1 - delta) on gate rows
        for c in other_cols:
            col = new_w[c].values.copy()
            col[g] = col[g] * (1.0 - delta)
            new_w[c] = col
        new_w[CASH_TICKER] = new_bil
    # Renormalise (defensive — should already be ~1 since math is exact)
    s = new_w.sum(axis=1)
    s = s.replace(0.0, 1.0)
    new_w = new_w.div(s, axis=0)
    return new_w


def recompute_returns(weights: pd.DataFrame, weekly_returns: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Standard project convention: weights at t earn t→t+1 returns; cost = L1
    turnover * half-spread."""
    next_week = weekly_returns.shift(-1)
    common = weights.index.intersection(next_week.index)
    cols = [c for c in weights.columns if c in next_week.columns]
    aligned_w = weights.loc[common, cols]
    aligned_r = next_week.loc[common, cols].fillna(0.0)
    gross = (aligned_w * aligned_r).sum(axis=1)
    turnover = aligned_w.diff().abs().sum(axis=1).fillna(0.0)
    cost = turnover * HALFSPREAD
    net = gross - cost
    return gross, net, turnover, cost


def build_sleeve_weights_proxy(name: str, prod_sleeve: pd.DataFrame, gate: pd.Series, delta: float) -> pd.DataFrame:
    """Mirror production sleeve_weights with the cash::BIL bucket bumped by
    delta*(1-cash) on gate weeks. Keeps file structure consistent with prior phases."""
    sw = prod_sleeve.copy()
    cash_col = "cash::BIL"
    if cash_col not in sw.columns:
        sw[cash_col] = 0.0
    other = [c for c in sw.columns if c != cash_col]
    g = gate.reindex(sw.index).fillna(False).values
    if g.any():
        cash = sw[cash_col].values
        risk = sw[other].sum(axis=1).values
        new_cash = cash.copy()
        new_cash[g] = cash[g] + delta * risk[g]
        for c in other:
            col = sw[c].values.copy()
            col[g] = col[g] * (1.0 - delta)
            sw[c] = col
        sw[cash_col] = new_cash
    s = sw.sum(axis=1)
    s = s.replace(0.0, 1.0)
    return sw.div(s, axis=0)


def metric_block(net: pd.Series) -> dict:
    return roc.metric_block(net)


def state_breakdown(net: pd.Series, prod_net: pd.Series, refined: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("dd"), prod_net.rename("prod")], axis=1).join(
        refined[["market_state", "refined_state"]], how="inner"
    ).dropna()
    rows = []
    for col in ["market_state", "refined_state"]:
        for s, sub in df.groupby(col):
            rows.append({
                "state_kind": col,
                "state": s,
                "n_weeks": int(len(sub)),
                "dd_mean_wkly": float(sub["dd"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "delta_mean_wkly": float(sub["dd"].mean() - sub["prod"].mean()),
                "dd_minus_prod_cumulative": float(((1 + sub["dd"]).prod() - 1) - ((1 + sub["prod"]).prod() - 1)),
            })
    return pd.DataFrame(rows)


def select_best_variant(summary: pd.DataFrame) -> tuple[str, str]:
    """Selection rule per user spec.

    Returns (best_name, rationale) — name == "" if NO candidate passes.
    """
    candidates = summary[summary["name"].isin(PHASE_DD_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    notes = []
    accept = []
    for _, r in candidates.iterrows():
        name = r["name"]
        ann_ret_drag_pp = (prod["full_ann_return"] - r["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        mdd_imp = r["full_max_drawdown"] - prod["full_max_drawdown"]    # higher = better
        cvar_imp = r["full_cvar_5"] - prod["full_cvar_5"]                # higher = better
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        bil_increase_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100
        # Pass conditions (all must hold)
        cond_drag = ann_ret_drag_pp <= 0.30                  # < 0.30pp ann return drag
        cond_sharpe = sharpe_imp >= 0.005                    # at least small Sharpe improvement
        cond_mdd = mdd_imp >= -0.005                         # MDD doesn't worsen by >0.5pp
        cond_cvar = cvar_imp >= -0.0005                      # CVaR-5% doesn't worsen by >0.05pp
        cond_turn = turn_ratio <= 1.10                       # turnover rises ≤10%
        cond_bil = bil_increase_pp <= 5.0                    # BIL rises ≤5pp on average
        passes = cond_drag and cond_sharpe and cond_mdd and cond_cvar and cond_turn and cond_bil
        accept.append({
            "name": name,
            "ann_ret_drag_pp": ann_ret_drag_pp,
            "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp * 100,
            "cvar_imp_pp": cvar_imp * 100,
            "turnover_ratio_vs_prod": turn_ratio,
            "bil_increase_pp": bil_increase_pp,
            "passes_all_gates": passes,
            "fail_reason": (
                ("drag>0.30pp; " if not cond_drag else "") +
                ("sharpe_imp<0.005; " if not cond_sharpe else "") +
                ("mdd_worse>0.5pp; " if not cond_mdd else "") +
                ("cvar_worse>0.05pp; " if not cond_cvar else "") +
                ("turnover>1.10x; " if not cond_turn else "") +
                ("bil_increase>5pp; " if not cond_bil else "")
            ).strip("; ") or "none",
        })
    accept_df = pd.DataFrame(accept)
    # Best = passing candidate with highest Sharpe improvement; tie-break by lowest drag
    passing = accept_df[accept_df["passes_all_gates"]]
    if not passing.empty:
        best = passing.sort_values(["sharpe_imp", "ann_ret_drag_pp"], ascending=[False, True]).iloc[0]
        rationale = (f"Selected {best['name']}: passes all 6 selection gates; sharpe_imp +{best['sharpe_imp']:.3f}, "
                     f"drag {best['ann_ret_drag_pp']:.2f}pp, mdd_imp {best['mdd_imp_pp']:+.2f}pp, "
                     f"turnover ratio {best['turnover_ratio_vs_prod']:.2f}x, BIL Δ {best['bil_increase_pp']:+.2f}pp.")
        return best["name"], rationale
    else:
        # No candidate passes — recommend the LEAST-bad one for diagnostic
        least = accept_df.sort_values(["sharpe_imp", "ann_ret_drag_pp"], ascending=[False, True]).iloc[0]
        rationale = (f"NO Phase DD candidate passes all selection gates. Best diagnostic candidate: {least['name']}; "
                     f"failure reason(s): {least['fail_reason']}.")
        return "", rationale


def main():
    print("Loading inputs...")
    refined = load_refined_state()
    prod_w = roc.load_portfolio_weights(PRODUCTION)
    prod_sleeve = roc.load_portfolio_sleeve_weights(PRODUCTION)
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    weekly = roc.load_weekly_returns()

    if prod_w is None or prod_ret is None:
        print("ERROR: production weights or returns missing; aborting"); sys.exit(1)
    if prod_sleeve is None:
        print("WARNING: production sleeve weights missing; sleeve_weights output will be skipped")

    # Build candidates
    candidate_summaries = []
    candidate_outputs = {}
    for name, cfg in VARIANTS.items():
        gate = gate_mask(prod_w, refined, cfg)
        weeks_triggered = int(gate.sum())
        print(f"\n=== {name} ===")
        print(f"  description: {cfg['description']}")
        print(f"  gate triggers: {weeks_triggered} of {len(gate)} weeks ({weeks_triggered/len(gate)*100:.1f}%)")
        new_w = apply_tilt(prod_w, gate, cfg["delta"])
        gross, net, turn, cost = recompute_returns(new_w, weekly)
        # Save weight file
        new_w.to_csv(roc.LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        # Save returns file in standard schema
        wealth = (1 + net.fillna(0)).cumprod()
        dd = wealth / wealth.cummax() - 1.0
        ret_df = pd.DataFrame({
            "gross_return": gross,
            "net_return": net,
            "turnover": turn.reindex(net.index).fillna(0.0),
            "cost": cost.reindex(net.index).fillna(0.0),
            "wealth": wealth,
            "drawdown": dd,
        })
        ret_df.to_csv(roc.LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        # Save sleeve_weights mirror
        if prod_sleeve is not None:
            new_sw = build_sleeve_weights_proxy(name, prod_sleeve, gate, cfg["delta"])
            new_sw.to_csv(roc.LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")

        # Headline
        prod_net_aligned = prod_ret["net_return"].reindex(net.index)
        full_m = metric_block(net)
        full_p = metric_block(prod_net_aligned)
        hold_m = metric_block(net.tail(roc.HOLDOUT_WEEKS))
        hold_p = metric_block(prod_net_aligned.tail(roc.HOLDOUT_WEEKS))
        candidate_summaries.append({
            "name": name,
            "weeks_triggered": weeks_triggered,
            "full_ann_return": full_m["ann_return"],
            "full_ann_vol": full_m["ann_vol"],
            "full_sharpe": full_m["sharpe"],
            "full_max_drawdown": full_m["max_drawdown"],
            "full_cvar_5": full_m["cvar_5"],
            "full_calmar": full_m["calmar"],
            "holdout_ann_return": hold_m["ann_return"],
            "holdout_sharpe": hold_m["sharpe"],
            "holdout_max_drawdown": hold_m["max_drawdown"],
            "avg_turnover": float(turn.mean()),
            "avg_BIL": float(new_w["BIL"].mean()) if "BIL" in new_w.columns else float("nan"),
            "avg_SPY": float(new_w["SPY"].mean()) if "SPY" in new_w.columns else float("nan"),
            "max_etf_weight": float(new_w.max(axis=1).max()),
        })
        candidate_outputs[name] = {"net": net, "weights": new_w, "gate": gate, "delta": cfg["delta"]}

    # Production + shadow rows
    for ref_name in [PRODUCTION, SHADOW]:
        ref_ret = roc.load_portfolio_returns(ref_name)
        ref_w = roc.load_portfolio_weights(ref_name)
        if ref_ret is None: continue
        n = ref_ret["net_return"].dropna()
        full_m = metric_block(n)
        hold_m = metric_block(n.tail(roc.HOLDOUT_WEEKS))
        avg_t = float(ref_ret["turnover"].mean()) if "turnover" in ref_ret.columns else float("nan")
        avg_bil = float(ref_w["BIL"].mean()) if (ref_w is not None and "BIL" in ref_w.columns) else float("nan")
        avg_spy = float(ref_w["SPY"].mean()) if (ref_w is not None and "SPY" in ref_w.columns) else float("nan")
        max_etf = float(ref_w.max(axis=1).max()) if ref_w is not None else float("nan")
        candidate_summaries.append({
            "name": ref_name,
            "weeks_triggered": 0,
            "full_ann_return": full_m["ann_return"],
            "full_ann_vol": full_m["ann_vol"],
            "full_sharpe": full_m["sharpe"],
            "full_max_drawdown": full_m["max_drawdown"],
            "full_cvar_5": full_m["cvar_5"],
            "full_calmar": full_m["calmar"],
            "holdout_ann_return": hold_m["ann_return"],
            "holdout_sharpe": hold_m["sharpe"],
            "holdout_max_drawdown": hold_m["max_drawdown"],
            "avg_turnover": avg_t,
            "avg_BIL": avg_bil,
            "avg_SPY": avg_spy,
            "max_etf_weight": max_etf,
        })

    summary = pd.DataFrame(candidate_summaries)
    summary.to_csv(roc.LAYER3_DIR / "phase_dd_candidate_metrics_full.csv", index=False)

    print("\n=== Phase DD candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    # State-by-state breakdown for each Phase DD candidate
    state_rows = []
    prod_net = prod_ret["net_return"]
    for name in PHASE_DD_CANDIDATES:
        sb = state_breakdown(candidate_outputs[name]["net"], prod_net, refined)
        sb["candidate"] = name
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True)
    state_df.to_csv(roc.LAYER3_DIR / "phase_dd_state_summary.csv", index=False)

    # Selection
    best_name, rationale = select_best_variant(summary)
    print(f"\n{rationale}")
    selection_df = pd.DataFrame([{
        "best_candidate": best_name,
        "rationale": rationale,
    }])
    selection_df.to_csv(roc.LAYER3_DIR / "phase_dd_selection_table.csv", index=False)

    # Pairwise validation against the comparator set + Phase D 8-gate rule
    all_versions = list(dict.fromkeys(COMPARATOR_BASE + COMPARATOR_AUGMENT + PHASE_DD_CANDIDATES))
    available = []
    for v in all_versions:
        if (roc.LAYER3_DIR / f"portfolio_version_returns_{v}.csv").exists():
            available.append(v)
        else:
            print(f"  comparator missing: {v}")
    try:
        returns_map, weights_map, turnover_map, benchmark_returns, market_state_history = ppe.candidate_frames(available)
        pairwise_rows = []
        prod_full = ppe.metric_row(PRODUCTION, returns_map[PRODUCTION], weights_map[PRODUCTION], turnover_map[PRODUCTION], benchmark_returns, market_state_history)
        prod_hold_ret, _, _, _ = pdv.split_dev_holdout(returns_map[PRODUCTION], weights_map[PRODUCTION], pdv.HOLDOUT_WEEKS)
        prod_hold = ppe.metric_row(PRODUCTION, prod_hold_ret, weights_map[PRODUCTION], turnover_map[PRODUCTION].reindex(prod_hold_ret.index), benchmark_returns.reindex(prod_hold_ret.index), market_state_history)
        for name in PHASE_DD_CANDIDATES:
            if name not in available:
                continue
            cand_full = ppe.metric_row(name, returns_map[name], weights_map[name], turnover_map[name], benchmark_returns, market_state_history)
            cand_hold_ret, _, _, _ = pdv.split_dev_holdout(returns_map[name], weights_map[name], pdv.HOLDOUT_WEEKS)
            cand_hold = ppe.metric_row(name, cand_hold_ret, weights_map[name], turnover_map[name].reindex(cand_hold_ret.index), benchmark_returns.reindex(cand_hold_ret.index), market_state_history)
            boot = ppe.safe_bootstrap(cand_hold_ret, prod_hold_ret)
            pairwise_rows.append({
                "version_name": name,
                "full_raw_delta_vs_production": float(cand_full["raw_target_composite"] - prod_full["raw_target_composite"]),
                "holdout_raw_delta_vs_production": float(cand_hold["raw_target_composite"] - prod_hold["raw_target_composite"]),
                "holdout_sharpe_delta_vs_production": float(cand_hold["sharpe"] - prod_hold["sharpe"]),
                "bootstrap_prob_vs_production": boot,
                "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - prod_full["max_drawdown"]),
                "cvar_delta_vs_production": float(cand_full["cvar_5"] - prod_full["cvar_5"]),
            })
        pw_df = pd.DataFrame(pairwise_rows)
        pw_df.to_csv(roc.LAYER3_DIR / "phase_dd_pairwise_validation.csv", index=False)
        print("\n=== Phase DD pairwise vs production (subset of Phase D rule) ===")
        print(pw_df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    except Exception as e:
        print(f"WARNING: pairwise validation skipped: {e}")

    # Protocol JSON
    protocol = {
        "phase": "Phase DD — Production-family additive tilt consuming Phase CC defensive_overlay_hint",
        "candidates": PHASE_DD_CANDIDATES,
        "variant_configs": VARIANTS,
        "tilt_mechanic": (
            "On gate weeks: scale all non-BIL ETF weights by (1-delta); add freed share to BIL. "
            "On non-gate weeks: candidate weights == production weights exactly (full ablate-ability)."
        ),
        "gates": {
            DD1_NAME: "defensive_overlay_hint == +1 AND production BIL exposure < 0.50",
            DD2_NAME: "defensive_overlay_hint == +1 AND production BIL exposure < 0.50",
            DD3_NAME: "refined_state == 'neutral_deteriorating' (the new state Phase CC created)",
        },
        "cost_convention": "5bp half-spread (0.0005 * 0.5)",
        "selection_rule": {
            "ann_ret_drag_max_pp": 0.30,
            "sharpe_improvement_min": 0.005,
            "mdd_worsening_max_pp": 0.5,
            "cvar_worsening_max_pp": 0.05,
            "turnover_ratio_max_vs_prod": 1.10,
            "bil_increase_max_pp": 5.0,
            "tie_break": "highest sharpe_improvement; then lowest ann_ret_drag",
        },
        "best_candidate": best_name,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_dd_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\nSaved Phase DD artifacts.")
    print(f"Best candidate: {best_name or '(none passed all gates)'}")


if __name__ == "__main__":
    main()
