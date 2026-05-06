"""Phase EE — Sleeve-level downstream test of Phase CC's `defensive_overlay_hint`.

Phase DD applied a flat ETF-level scale-down which treated production's
defensive sleeves identically to its offensive sleeves and provided ~zero
benefit. Phase EE corrects the level of intervention: scale only OFFENSIVE
sleeves down and redirect the freed weight into existing DEFENSIVE sleeves
(not blindly to BIL). The cash::BIL bucket is left untouched.

Production sleeve schema (confirmed from
portfolio_version_sleeve_weights_improved_phase2b_regime_confidence_boost.csv):

  Offensive sleeves (this phase scales them DOWN):
    - dual_momentum_topn
    - cta_trend_long_only
    - composite_selective_signals
  Defensive sleeves (this phase scales them UP):
    - composite_regime_conditioned
    - taa_10m_sma
  Cash bucket (untouched):
    - cash::BIL

ETF weights are re-derived per project convention as a long-only weighted
sum of sleeve_positions × sleeve_weights, plus the cash::BIL share.

Two candidates (≤2 per spec):
  EE1 — improved_phaseee_sleeve_hint_light
        Gate: defensive_overlay_hint == +1
              AND market_state NOT IN {stressed_panic, recovery_fragile}
        Tilt: delta = 0.10 (scale offensive sleeves by 1-delta;
              redirect freed weight into defensive sleeves proportionally)
  EE2 — improved_phaseee_sleeve_hint_state_gated
        Gate: refined_state == 'neutral_deteriorating' (the new state Phase CC created)
        Tilt: delta = 0.10 (same mechanic)

Selection rule (auto-applied):
  - ann return drag <= 0.30pp
  - Sharpe improvement >= 0.005
  - MDD worsening <= 0.5pp
  - CVaR worsening <= 0.05pp
  - turnover ratio vs production <= 1.10x
  - avg BIL increase <= 5pp
  - candidate must NOT underperform production in `neutral_deteriorating`
    (the targeted state — addressing Phase DD's failure mode directly)

Outputs to data/05_layer3_portfolio_construction/:
  portfolio_version_{returns,weights,sleeve_weights}_improved_phaseee_*.csv
  phase_ee_candidate_metrics_full.csv
  phase_ee_state_summary.csv
  phase_ee_selection_table.csv
  phase_ee_protocol.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
HALFSPREAD = roc.DEFAULT_HALFSPREAD
CASH_BUCKET = "cash::BIL"
CASH_TICKER = "BIL"

OFFENSIVE_SLEEVES = ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals"]
DEFENSIVE_SLEEVES = ["composite_regime_conditioned", "taa_10m_sma"]

EE1_NAME = "improved_phaseee_sleeve_hint_light"
EE2_NAME = "improved_phaseee_sleeve_hint_state_gated"
PHASE_EE_CANDIDATES = [EE1_NAME, EE2_NAME]

VARIANTS = {
    EE1_NAME: {
        "delta": 0.10,
        "gate_kind": "hint_excluding_already_stressed",
        "exclude_states": ["stressed_panic", "recovery_fragile"],
        "description": "Scale offensive sleeves by (1-delta); redirect freed weight into defensive sleeves proportionally. "
                       "Gate: hint == +1 AND state NOT IN {stressed_panic, recovery_fragile}.",
    },
    EE2_NAME: {
        "delta": 0.10,
        "gate_kind": "refined_state_gated",
        "trigger_states": ["neutral_deteriorating"],
        "description": "Same sleeve-level rotation; gate fires ONLY when refined_state == 'neutral_deteriorating'.",
    },
}


def load_refined_state() -> pd.DataFrame:
    df = pd.read_csv(roc.LAYER2B_DIR / "market_state_history_refined.csv",
                     parse_dates=["Date"]).set_index("Date").sort_index()
    df.index = df.index.tz_localize(None)
    return df


def load_sleeve_positions(name: str) -> pd.DataFrame:
    p = roc.LAYER2A_DIR / f"strategy_positions_{name}.csv"
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    df.index.name = None
    return df.sort_index().fillna(0.0)


def gate_mask(refined: pd.DataFrame, sleeve_w_index: pd.DatetimeIndex, cfg: dict) -> pd.Series:
    aligned = refined.reindex(sleeve_w_index)
    if cfg["gate_kind"] == "hint_excluding_already_stressed":
        hint = aligned["defensive_overlay_hint"].fillna(0).astype(int)
        state = aligned["market_state"].astype(str).fillna("")
        gate = (hint == 1) & ~state.isin(cfg["exclude_states"])
    elif cfg["gate_kind"] == "refined_state_gated":
        states = aligned["refined_state"].astype(str).fillna("")
        gate = states.isin(cfg["trigger_states"])
    else:
        raise ValueError(f"unknown gate_kind: {cfg['gate_kind']}")
    return gate.fillna(False)


def apply_sleeve_tilt(prod_sleeve_w: pd.DataFrame, gate: pd.Series, delta: float) -> pd.DataFrame:
    """For gate weeks: scale offensive sleeves by (1-delta), redistribute the
    freed total proportionally across defensive sleeves. Cash bucket untouched."""
    new_sw = prod_sleeve_w.copy()
    off_cols = [c for c in OFFENSIVE_SLEEVES if c in new_sw.columns]
    def_cols = [c for c in DEFENSIVE_SLEEVES if c in new_sw.columns]
    g = gate.reindex(new_sw.index).fillna(False).values

    if not g.any():
        return new_sw

    off_sum = new_sw[off_cols].sum(axis=1).values
    def_sum = new_sw[def_cols].sum(axis=1).values

    # On gate rows, freed = delta * off_sum
    freed = np.where(g, delta * off_sum, 0.0)

    # Scale offensive sleeves down by (1-delta)
    for c in off_cols:
        col = new_sw[c].values.copy()
        col[g] = col[g] * (1.0 - delta)
        new_sw[c] = col

    # Redistribute freed across defensive sleeves proportionally to current defensive weights
    # If def_sum is 0 (very unusual), put freed into the first defensive sleeve as a fallback
    for c in def_cols:
        col = new_sw[c].values.copy()
        share = np.where(def_sum > 1e-12, new_sw[c].values / def_sum, 0.0)
        col[g] = col[g] + freed[g] * share[g]
        new_sw[c] = col
    # Fallback: if def_sum was 0 on a gate row, push freed into the first defensive sleeve
    zero_def = (def_sum <= 1e-12) & g
    if zero_def.any() and def_cols:
        c = def_cols[0]
        col = new_sw[c].values.copy()
        col[zero_def] = col[zero_def] + freed[zero_def]
        new_sw[c] = col

    # Renormalise (defensive — math is exact, but guard against tiny drift)
    s = new_sw.sum(axis=1)
    s = s.replace(0.0, 1.0)
    new_sw = new_sw.div(s, axis=0)
    return new_sw


def rebuild_etf_weights(sleeve_weights: pd.DataFrame, sleeve_positions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """ETF weights = sum over sleeves of (sleeve_weight × sleeve_positions) +
    cash bucket assigned to BIL. Standard project convention."""
    risky_sleeves = [c for c in sleeve_weights.columns if not c.startswith("cash::")]
    etf_universe = sorted({c for s in risky_sleeves for c in sleeve_positions[s].columns} | {CASH_TICKER})
    rows = []
    for date in sleeve_weights.index:
        etf_w = pd.Series(0.0, index=etf_universe)
        for s in risky_sleeves:
            sw = float(sleeve_weights.at[date, s]) if s in sleeve_weights.columns else 0.0
            if sw <= 0 or s not in sleeve_positions:
                continue
            pos = sleeve_positions[s]
            if date in pos.index:
                pos_today = pos.loc[date].fillna(0.0)
            else:
                # forward-fill: use most recent past row
                prev = pos.loc[:date]
                if prev.empty:
                    continue
                pos_today = prev.iloc[-1].fillna(0.0)
            for etf, val in pos_today.items():
                if val == 0 or etf not in etf_w.index:
                    continue
                etf_w[etf] += sw * float(val)
        # cash bucket -> BIL
        cash_w = float(sleeve_weights.at[date, CASH_BUCKET]) if CASH_BUCKET in sleeve_weights.columns else 0.0
        etf_w[CASH_TICKER] = float(etf_w.get(CASH_TICKER, 0.0)) + cash_w
        # renormalise
        s = float(etf_w.sum())
        if s > 1e-12:
            etf_w = etf_w / s
        else:
            etf_w[:] = 0.0
            etf_w[CASH_TICKER] = 1.0
        etf_w.name = date
        rows.append(etf_w)
    out = pd.DataFrame(rows).fillna(0.0)
    out.index.name = None
    return out


def recompute_returns(weights: pd.DataFrame, weekly_returns: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
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


def state_breakdown(net: pd.Series, prod_net: pd.Series, refined: pd.DataFrame) -> pd.DataFrame:
    df = pd.concat([net.rename("ee"), prod_net.rename("prod")], axis=1).join(
        refined[["market_state", "refined_state"]], how="inner"
    ).dropna()
    rows = []
    for col in ["market_state", "refined_state"]:
        for s, sub in df.groupby(col):
            rows.append({
                "state_kind": col,
                "state": s,
                "n_weeks": int(len(sub)),
                "ee_mean_wkly": float(sub["ee"].mean()),
                "prod_mean_wkly": float(sub["prod"].mean()),
                "delta_mean_wkly": float(sub["ee"].mean() - sub["prod"].mean()),
                "ee_minus_prod_cumulative": float(((1 + sub["ee"]).prod() - 1) - ((1 + sub["prod"]).prod() - 1)),
            })
    return pd.DataFrame(rows)


def select_best(summary: pd.DataFrame, state_df: pd.DataFrame) -> tuple[str, str, dict]:
    """Apply all 7 selection gates including the new `must beat in
    neutral_deteriorating` gate."""
    cands = summary[summary["name"].isin(PHASE_EE_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    rows = []
    for _, r in cands.iterrows():
        name = r["name"]
        ann_drag_pp = (prod["full_ann_return"] - r["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else float("inf")
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100
        # New gate: candidate must NOT underperform production in neutral_deteriorating
        det_row = state_df[(state_df["candidate"] == name) &
                           (state_df["state_kind"] == "refined_state") &
                           (state_df["state"] == "neutral_deteriorating")]
        det_delta_wkly = float(det_row["delta_mean_wkly"].iloc[0]) if not det_row.empty else float("nan")
        cond_drag = ann_drag_pp <= 0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_bil = bil_inc_pp <= 5.0
        cond_det = (not np.isnan(det_delta_wkly)) and det_delta_wkly >= 0
        passes = all([cond_drag, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_bil, cond_det])
        fail_reasons = "; ".join([
            r for r in [
                "drag>0.30pp" if not cond_drag else "",
                "sharpe_imp<0.005" if not cond_sharpe else "",
                "mdd_worse>0.5pp" if not cond_mdd else "",
                "cvar_worse>0.05pp" if not cond_cvar else "",
                "turnover>1.10x" if not cond_turn else "",
                "bil_inc>5pp" if not cond_bil else "",
                f"underperforms in neutral_deteriorating (Δ={det_delta_wkly:+.5f}/wk)" if not cond_det else "",
            ] if r
        ]) or "none"
        rows.append({
            "name": name,
            "ann_drag_pp": ann_drag_pp,
            "sharpe_imp": sharpe_imp,
            "mdd_imp_pp": mdd_imp_pp,
            "cvar_imp_pp": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio,
            "bil_inc_pp": bil_inc_pp,
            "deteriorating_state_delta_wkly": det_delta_wkly,
            "passes_all_gates": passes,
            "fail_reasons": fail_reasons,
        })
    decision = pd.DataFrame(rows)
    passing = decision[decision["passes_all_gates"]]
    if not passing.empty:
        best = passing.sort_values(["sharpe_imp", "ann_drag_pp"], ascending=[False, True]).iloc[0]
        rationale = (f"Selected {best['name']}: passes all 7 gates including "
                     f"`must not underperform in neutral_deteriorating` "
                     f"(Δ {best['deteriorating_state_delta_wkly']:+.5f}/wk).")
        return best["name"], rationale, decision.to_dict("records")
    least = decision.sort_values(["sharpe_imp", "ann_drag_pp"], ascending=[False, True]).iloc[0]
    rationale = f"NO Phase EE candidate passes. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons']}."
    return "", rationale, decision.to_dict("records")


def main():
    print("Loading inputs...")
    refined = load_refined_state()
    prod_sleeve = roc.load_portfolio_sleeve_weights(PRODUCTION)
    prod_w = roc.load_portfolio_weights(PRODUCTION)
    prod_ret = roc.load_portfolio_returns(PRODUCTION)
    weekly = roc.load_weekly_returns()
    if prod_sleeve is None or prod_w is None or prod_ret is None:
        print("ERROR: production files missing"); sys.exit(1)

    sleeve_positions = {}
    for s in OFFENSIVE_SLEEVES + DEFENSIVE_SLEEVES:
        sleeve_positions[s] = load_sleeve_positions(s)
        print(f"  loaded sleeve_positions for {s} (shape={sleeve_positions[s].shape})")

    candidate_outputs = {}
    for name, cfg in VARIANTS.items():
        print(f"\n=== {name} ===")
        print(f"  description: {cfg['description']}")
        gate = gate_mask(refined, prod_sleeve.index, cfg)
        print(f"  gate triggers: {int(gate.sum())} of {len(gate)} weeks ({gate.mean()*100:.1f}%)")
        # Sleeve-level tilt
        new_sw = apply_sleeve_tilt(prod_sleeve, gate, cfg["delta"])
        # Re-derive ETF weights from sleeve weights × sleeve positions
        new_etf_w = rebuild_etf_weights(new_sw, sleeve_positions)
        # Net returns
        gross, net, turn, cost = recompute_returns(new_etf_w, weekly)
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
        new_sw.to_csv(roc.LAYER3_DIR / f"portfolio_version_sleeve_weights_{name}.csv")
        new_etf_w.to_csv(roc.LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        ret_df.to_csv(roc.LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        candidate_outputs[name] = {"net": net, "weights": new_etf_w, "sleeve": new_sw, "gate": gate}

    # Headline metrics
    rows = []
    for name in PHASE_EE_CANDIDATES:
        c = candidate_outputs[name]
        n = c["net"].dropna()
        full_m = roc.metric_block(n)
        hold_m = roc.metric_block(n.tail(roc.HOLDOUT_WEEKS))
        avg_t = float(c["weights"].diff().abs().sum(axis=1).fillna(0.0).mean())
        avg_bil = float(c["weights"]["BIL"].mean()) if "BIL" in c["weights"].columns else float("nan")
        avg_spy = float(c["weights"]["SPY"].mean()) if "SPY" in c["weights"].columns else float("nan")
        max_etf = float(c["weights"].max(axis=1).max())
        rows.append({
            "name": name,
            "weeks_triggered": int(c["gate"].sum()),
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
    # Production + shadow rows
    for ref in [PRODUCTION, SHADOW]:
        rr = roc.load_portfolio_returns(ref)
        rw = roc.load_portfolio_weights(ref)
        if rr is None: continue
        n = rr["net_return"].dropna()
        full_m = roc.metric_block(n)
        hold_m = roc.metric_block(n.tail(roc.HOLDOUT_WEEKS))
        avg_t = float(rr["turnover"].mean()) if "turnover" in rr.columns else float("nan")
        avg_bil = float(rw["BIL"].mean()) if (rw is not None and "BIL" in rw.columns) else float("nan")
        avg_spy = float(rw["SPY"].mean()) if (rw is not None and "SPY" in rw.columns) else float("nan")
        max_etf = float(rw.max(axis=1).max()) if rw is not None else float("nan")
        rows.append({
            "name": ref, "weeks_triggered": 0,
            "full_ann_return": full_m["ann_return"], "full_ann_vol": full_m["ann_vol"],
            "full_sharpe": full_m["sharpe"], "full_max_drawdown": full_m["max_drawdown"],
            "full_cvar_5": full_m["cvar_5"], "full_calmar": full_m["calmar"],
            "holdout_ann_return": hold_m["ann_return"], "holdout_sharpe": hold_m["sharpe"],
            "holdout_max_drawdown": hold_m["max_drawdown"], "avg_turnover": avg_t,
            "avg_BIL": avg_bil, "avg_SPY": avg_spy, "max_etf_weight": max_etf,
        })
    summary = pd.DataFrame(rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_ee_candidate_metrics_full.csv", index=False)

    # State breakdown
    state_rows = []
    for name in PHASE_EE_CANDIDATES:
        sb = state_breakdown(candidate_outputs[name]["net"], prod_ret["net_return"], refined)
        sb["candidate"] = name
        state_rows.append(sb)
    state_df = pd.concat(state_rows, ignore_index=True)
    state_df.to_csv(roc.LAYER3_DIR / "phase_ee_state_summary.csv", index=False)

    # Selection
    best, rationale, gate_records = select_best(summary, state_df)
    sel_df = pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + gate_records)
    sel_df.to_csv(roc.LAYER3_DIR / "phase_ee_selection_table.csv", index=False)

    print("\n=== Phase EE candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase EE state-by-state (refined_state) ===")
    print(state_df[state_df["state_kind"] == "refined_state"][["candidate", "state", "n_weeks", "delta_mean_wkly", "ee_minus_prod_cumulative"]].to_string(index=False, float_format=lambda x: f"{x:.6f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase EE — Sleeve-level downstream test of Phase CC defensive_overlay_hint",
        "candidates": PHASE_EE_CANDIDATES,
        "variant_configs": VARIANTS,
        "offensive_sleeves": OFFENSIVE_SLEEVES,
        "defensive_sleeves": DEFENSIVE_SLEEVES,
        "tilt_mechanic": (
            "On gate weeks at the SLEEVE level: scale all offensive sleeves by (1-delta); "
            "redistribute the freed weight proportionally across defensive sleeves. "
            "cash::BIL is untouched. ETF weights are then re-derived as the standard "
            "long-only weighted sum of sleeve_positions × sleeve_weights + cash share."
        ),
        "selection_rule": {
            "ann_ret_drag_max_pp": 0.30,
            "sharpe_improvement_min": 0.005,
            "mdd_worsening_max_pp": 0.5,
            "cvar_worsening_max_pp": 0.05,
            "turnover_ratio_max_vs_prod": 1.10,
            "bil_increase_max_pp": 5.0,
            "neutral_deteriorating_state_must_not_underperform": True,
        },
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_ee_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase EE artifacts.")


if __name__ == "__main__":
    main()
