"""Phase OOO5 -- triple-barrier / meta-label signal validation.

Diagnostic-only. Uses OOO2 lagged signal panel and existing GGG1/production
returns to test event-level outcomes. No portfolio candidates are created.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OOO2 = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo2_cross_asset_signal_expansion"
OUT = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo5_triple_barrier_validation"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_ooo5_triple_barrier_signal_validation_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
HORIZONS = [4, 8, 13]
HOLDOUT_START = pd.Timestamp("2016-01-01")
MIN_EVENTS = 20

COMMANDS = [
    "sed -n '1,220p' docs/research/2026-04-27_phase_ooo2_cross_asset_signal_expansion_report.md",
    "find data/research/phase_ooo_signal_discovery/ooo2_cross_asset_signal_expansion -maxdepth 1 -type f | sort",
    "python3 - <<'PY' ...small OOO2/return/state summaries...",
    "tail -n 80 docs/research/project_journey.md",
    "python3 scripts/phase_ooo5_triple_barrier_signal_validation.py",
]


def read_indexed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else "date" if "date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df.dropna(subset=[date_col]).set_index(date_col).sort_index()


def returns(version: str) -> pd.Series:
    df = read_indexed(L3 / f"portfolio_version_returns_{version}.csv")
    return pd.to_numeric(df["net_return"], errors="coerce").fillna(0.0).rename(version)


def future_compound(s: pd.Series, idx: int, horizon: int) -> float:
    vals = s.iloc[idx + 1 : idx + horizon + 1].to_numpy()
    if len(vals) < horizon:
        return np.nan
    return float(np.prod(1.0 + vals) - 1.0)


def future_path(s: pd.Series, idx: int, horizon: int) -> np.ndarray:
    vals = s.iloc[idx + 1 : idx + horizon + 1].to_numpy()
    if len(vals) < horizon:
        return np.array([])
    return np.cumprod(1.0 + vals) - 1.0


def signal_role(signal: str, expected_use: str) -> tuple[str, str, str, str]:
    """Return direction, threshold side, state filter, interpretation."""
    state = ""
    for st in ["recovery_confirmed", "recovery_fragile", "stressed_panic", "neutral_mixed", "calm_trend"]:
        if f"_x_{st}" in signal:
            state = st
    if "market_drawdown" in signal:
        return "risk_off_stress", "bottom", state, "Deep/weak drawdown readings should flag adverse GGG1 risk."
    if "recent_stress" in signal:
        return "risk_off_stress", "top", state, "Recent stress memory should flag adverse GGG1 risk."
    if "GLD_minus_SPY" in signal or "DBA_minus_SPY" in signal:
        return "defensive_leadership", "top", state, "Real-asset leadership over SPY should flag defensive/risk regime pressure."
    if "stressed_panic" in signal:
        return "state_quality_or_risk", "top", state or "stressed_panic", "State-conditioned breadth in stressed_panic should identify higher-quality stress events."
    if "breadth" in signal or "market_trend" in signal or "canary" in signal:
        return "risk_on_opportunity", "top", state, "Broad participation/trend should identify better opportunity states."
    if "HYG_minus_LQD" in signal or "EFA_minus_SPY" in signal:
        return "risk_on_opportunity", "top", state, "Relative strength should identify risk appetite/opportunity."
    return expected_use or "unknown", "top", state, "OOO2 survivor."


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    queue = pd.read_csv(OOO2 / "ooo2_next_phase_signal_queue.csv")
    decisions = pd.read_csv(OOO2 / "ooo2_signal_keep_reject_decisions.csv")
    panel = read_indexed(OOO2 / "ooo2_candidate_signal_panel.csv")
    states = read_indexed(L2B / "market_state_history.csv")[["market_state"]]
    keep = {"KEEP_HIGH_PRIORITY", "KEEP_STATE_SPECIFIC", "KEEP_FOR_TRIPLE_BARRIER_VALIDATION"}
    queue = queue[queue["decision"].isin(keep)].copy()
    panel = panel[[c for c in queue["signal_name"] if c in panel.columns]]
    return queue, decisions, panel, states


def build_event_definitions(queue: pd.DataFrame, panel: pd.DataFrame, states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    aligned = panel.join(states, how="left")
    defs, events = [], []
    for _, row in queue.iterrows():
        sig = row["signal_name"]
        direction, side, state_filter, interp = signal_role(sig, str(row.get("expected_use", "")))
        valid = aligned[[sig, "market_state"]].dropna(subset=[sig]).copy()
        if state_filter:
            valid = valid[valid["market_state"].eq(state_filter)]
        valid = valid[valid[sig].notna()]
        for pct, label in [(0.20, "primary_20pct"), (0.30, "diagnostic_30pct")]:
            if valid.empty:
                threshold = np.nan
                fire = valid
            elif side == "bottom":
                threshold = float(valid[sig].quantile(pct))
                fire = valid[valid[sig] <= threshold]
            else:
                threshold = float(valid[sig].quantile(1.0 - pct))
                fire = valid[valid[sig] >= threshold]
            n = int(len(fire))
            defs.append({
                "signal_name": sig,
                "event_direction": direction,
                "threshold_type": label,
                "threshold_side": side,
                "threshold_value": threshold,
                "state_filter": state_filter or "none",
                "n_events": n,
                "event_frequency": n / max(1, len(valid)),
                "min_event_count_passed": n >= MIN_EVENTS,
                "event_selectivity_passed": (n / max(1, len(valid))) <= 0.45,
                "economic_interpretation": interp,
            })
            for date, ev in fire.iterrows():
                events.append({
                    "date": date,
                    "signal_name": sig,
                    "threshold_type": label,
                    "signal_value": ev[sig],
                    "event_direction": direction,
                    "threshold_side": side,
                    "market_state": ev["market_state"],
                    "state_filter": state_filter or "none",
                })
    return pd.DataFrame(defs), pd.DataFrame(events)


def compute_event_outcomes(events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    g = returns(GGG1)
    p = returns(PRODUCTION).reindex(g.index).fillna(0.0)
    sh = returns(SHADOW).reindex(g.index).fillna(0.0)
    vol = g.rolling(13, min_periods=8).std().shift(1)
    events = events.copy()
    events["date"] = pd.to_datetime(events["date"])
    idx_map = {d: i for i, d in enumerate(g.index)}
    tb_rows, meta_rows = [], []
    for _, ev in events.iterrows():
        date = ev["date"]
        if date not in idx_map:
            continue
        i = idx_map[date]
        sigma = float(vol.loc[date]) if date in vol.index and pd.notna(vol.loc[date]) else np.nan
        for h in HORIZONS:
            path = future_path(g, i, h)
            if len(path) < h or not np.isfinite(sigma) or sigma <= 0:
                continue
            upper = sigma * math.sqrt(h)
            lower = -sigma * math.sqrt(h)
            label, ttb = 0, h
            for j, val in enumerate(path, start=1):
                if val >= upper:
                    label, ttb = 1, j
                    break
                if val <= lower:
                    label, ttb = -1, j
                    break
            g_ret = float(path[-1])
            prod_ret = future_compound(p, i, h)
            shadow_ret = future_compound(sh, i, h)
            max_fav = float(np.nanmax(path))
            max_adv = float(np.nanmin(path))
            base = {
                "date": date,
                "signal_name": ev["signal_name"],
                "threshold_type": ev["threshold_type"],
                "event_direction": ev["event_direction"],
                "market_state": ev["market_state"],
                "horizon_weeks": h,
                "signal_value": ev["signal_value"],
                "trailing_13w_weekly_vol": sigma,
            }
            tb_rows.append({
                **base,
                "upper_barrier": upper,
                "lower_barrier": lower,
                "triple_barrier_label": label,
                "time_to_barrier": ttb,
                "max_favorable_excursion": max_fav,
                "max_adverse_excursion": max_adv,
                "final_horizon_return": g_ret,
                "drawdown_worsening": max_adv < lower * 0.5,
            })
            meta_rows.append({
                **base,
                "final_horizon_return": g_ret,
                "positive_final_return": g_ret > 0,
                "positive_risk_adjusted_final_return": (g_ret / (sigma * math.sqrt(h))) > 0,
                "beats_old_production": g_ret > prod_ret,
                "beats_official_shadow": g_ret > shadow_ret,
                "avoids_adverse_tail": label != -1,
                "production_forward_return": prod_ret,
                "shadow_forward_return": shadow_ret,
            })
    return pd.DataFrame(tb_rows), pd.DataFrame(meta_rows), pd.concat([g, p, sh], axis=1)


def baseline_table(returns_df: pd.DataFrame, states: pd.DataFrame) -> pd.DataFrame:
    g = returns_df[GGG1]
    vol = g.rolling(13, min_periods=8).std().shift(1)
    rows = []
    for h in HORIZONS:
        for date in g.index:
            if pd.isna(vol.loc[date]) or vol.loc[date] <= 0:
                continue
            i = g.index.get_loc(date)
            path = future_path(g, i, h)
            if len(path) < h:
                continue
            upper = float(vol.loc[date]) * math.sqrt(h)
            lower = -float(vol.loc[date]) * math.sqrt(h)
            label = 0
            for val in path:
                if val >= upper:
                    label = 1
                    break
                if val <= lower:
                    label = -1
                    break
            rows.append({
                "date": date,
                "horizon_weeks": h,
                "market_state": states.reindex([date])["market_state"].iloc[0] if date in states.index else "unknown",
                "final_horizon_return": float(path[-1]),
                "positive_barrier_rate": label == 1,
                "negative_barrier_rate": label == -1,
            })
    b = pd.DataFrame(rows)
    allb = b.groupby("horizon_weeks", as_index=False).agg(
        all_weeks_avg_return=("final_horizon_return", "mean"),
        all_weeks_positive_barrier_rate=("positive_barrier_rate", "mean"),
        all_weeks_negative_barrier_rate=("negative_barrier_rate", "mean"),
    )
    stateb = b.groupby(["horizon_weeks", "market_state"], as_index=False).agg(
        same_state_avg_return=("final_horizon_return", "mean"),
        same_state_positive_barrier_rate=("positive_barrier_rate", "mean"),
        same_state_negative_barrier_rate=("negative_barrier_rate", "mean"),
    )
    return allb.merge(stateb, on="horizon_weeks", how="outer")


def summarize(tb: pd.DataFrame, meta: pd.DataFrame, returns_df: pd.DataFrame, states: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    primary = tb[tb["threshold_type"].eq("primary_20pct")].copy()
    meta_p = meta[meta["threshold_type"].eq("primary_20pct")].copy()
    group_cols = ["signal_name", "threshold_type", "event_direction", "horizon_weeks"]
    summary = primary.groupby(group_cols, as_index=False).agg(
        event_count=("date", "nunique"),
        positive_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == 1).mean())),
        negative_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == -1).mean())),
        neutral_no_hit_rate=("triple_barrier_label", lambda s: float((s == 0).mean())),
        avg_final_return=("final_horizon_return", "mean"),
        median_final_return=("final_horizon_return", "median"),
        avg_max_favorable_excursion=("max_favorable_excursion", "mean"),
        avg_max_adverse_excursion=("max_adverse_excursion", "mean"),
        avg_time_to_favorable_barrier=("time_to_barrier", lambda s: np.nan),
        avg_time_to_adverse_barrier=("time_to_barrier", lambda s: np.nan),
    )
    fav = primary[primary["triple_barrier_label"].eq(1)].groupby(group_cols)["time_to_barrier"].mean().rename("avg_time_to_favorable_barrier").reset_index()
    adv = primary[primary["triple_barrier_label"].eq(-1)].groupby(group_cols)["time_to_barrier"].mean().rename("avg_time_to_adverse_barrier").reset_index()
    summary = summary.drop(columns=["avg_time_to_favorable_barrier", "avg_time_to_adverse_barrier"]).merge(fav, on=group_cols, how="left").merge(adv, on=group_cols, how="left")
    summary["payoff_ratio"] = summary["avg_max_favorable_excursion"].abs() / summary["avg_max_adverse_excursion"].abs().replace(0, np.nan)
    meta_sum = meta_p.groupby(group_cols, as_index=False).agg(
        precision_positive_final_return=("positive_final_return", "mean"),
        precision_beats_old_production=("beats_old_production", "mean"),
        precision_beats_official_shadow=("beats_official_shadow", "mean"),
        precision_avoids_bad_outcome=("avoids_adverse_tail", "mean"),
    )
    summary = summary.merge(meta_sum, on=group_cols, how="left")
    hold = primary[primary["date"].ge(HOLDOUT_START)].groupby(group_cols, as_index=False).agg(
        holdout_event_count=("date", "nunique"),
        holdout_avg_final_return=("final_horizon_return", "mean"),
        holdout_positive_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == 1).mean())),
        holdout_negative_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == -1).mean())),
    )
    summary = summary.merge(hold, on=group_cols, how="left")
    baseline = baseline_table(returns_df, states)
    allb = baseline[["horizon_weeks", "all_weeks_avg_return", "all_weeks_positive_barrier_rate", "all_weeks_negative_barrier_rate"]].drop_duplicates()
    summary = summary.merge(allb, on="horizon_weeks", how="left")
    summary["return_lift_vs_all_weeks"] = summary["avg_final_return"] - summary["all_weeks_avg_return"]
    summary["positive_barrier_lift_vs_all_weeks"] = summary["positive_barrier_hit_rate"] - summary["all_weeks_positive_barrier_rate"]
    summary["negative_barrier_lift_vs_all_weeks"] = summary["negative_barrier_hit_rate"] - summary["all_weeks_negative_barrier_rate"]
    state_summary = primary.groupby(group_cols + ["market_state"], as_index=False).agg(
        event_count=("date", "nunique"),
        positive_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == 1).mean())),
        negative_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == -1).mean())),
        avg_final_return=("final_horizon_return", "mean"),
    )
    stateb = baseline[["horizon_weeks", "market_state", "same_state_avg_return", "same_state_positive_barrier_rate", "same_state_negative_barrier_rate"]].drop_duplicates()
    state_summary = state_summary.merge(stateb, on=["horizon_weeks", "market_state"], how="left")
    state_summary["return_lift_vs_same_state"] = state_summary["avg_final_return"] - state_summary["same_state_avg_return"]
    state_summary["positive_barrier_lift_vs_same_state"] = state_summary["positive_barrier_hit_rate"] - state_summary["same_state_positive_barrier_rate"]
    state_summary["negative_barrier_lift_vs_same_state"] = state_summary["negative_barrier_hit_rate"] - state_summary["same_state_negative_barrier_rate"]
    lift = summary[["signal_name", "horizon_weeks", "event_count", "return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks", "negative_barrier_lift_vs_all_weeks", "precision_beats_old_production", "precision_avoids_bad_outcome"]].copy()
    return summary, state_summary, lift


def overlap_and_incrementality(events: pd.DataFrame, states: pd.DataFrame, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    primary = events[events["threshold_type"].eq("primary_20pct")].copy()
    if primary.empty:
        return pd.DataFrame(), pd.DataFrame()
    dates = sorted(primary["date"].drop_duplicates())
    signals = sorted(primary["signal_name"].unique())
    mat = pd.DataFrame(0, index=pd.to_datetime(dates), columns=signals)
    for _, r in primary.iterrows():
        mat.loc[pd.to_datetime(r["date"]), r["signal_name"]] = 1
    overlaps = pd.DataFrame(index=signals, columns=signals, dtype=float)
    for a in signals:
        for b in signals:
            denom = max(1, int(mat[a].sum()))
            overlaps.loc[a, b] = float(((mat[a] == 1) & (mat[b] == 1)).sum() / denom)
    rows = []
    bil = pd.to_numeric(weights.get("BIL"), errors="coerce").reindex(mat.index)
    high_bil = bil >= bil.quantile(0.75)
    low_bil = bil <= bil.quantile(0.25)
    st = states.reindex(mat.index)["market_state"]
    for sig in signals:
        ev_dates = mat.index[mat[sig].eq(1)]
        ev_states = st.reindex(ev_dates)
        max_state_overlap = float(ev_states.value_counts(normalize=True).max()) if len(ev_states) else np.nan
        dominant_state = ev_states.value_counts().index[0] if len(ev_states.value_counts()) else "unknown"
        high_bil_overlap = float(high_bil.reindex(ev_dates).mean()) if len(ev_dates) else np.nan
        low_bil_overlap = float(low_bil.reindex(ev_dates).mean()) if len(ev_dates) else np.nan
        max_signal_overlap = float(overlaps.loc[sig, [c for c in signals if c != sig]].max()) if len(signals) > 1 else np.nan
        if len(ev_dates) < MIN_EVENTS:
            flag = "INSUFFICIENT_EVENTS"
        elif max_signal_overlap >= 0.80:
            flag = "REDUNDANT_WITH_STRONGER_SIGNAL"
        elif max_state_overlap >= 0.90:
            flag = "MOSTLY_DUPLICATES_STATE_ENGINE"
        elif len(ev_dates) < 40:
            flag = "INCREMENTAL_BUT_RARE"
        else:
            flag = "INCREMENTAL_TO_STATE_ENGINE"
        rows.append({
            "signal_name": sig,
            "n_events": len(ev_dates),
            "dominant_market_state": dominant_state,
            "max_state_overlap": max_state_overlap,
            "high_bil_overlap": high_bil_overlap,
            "low_bil_overlap": low_bil_overlap,
            "max_signal_event_overlap": max_signal_overlap,
            "incrementality_flag": flag,
        })
    return overlaps.reset_index(names="signal_name"), pd.DataFrame(rows)


def decisions(summary: pd.DataFrame, inc: pd.DataFrame, defs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    primary_defs = defs[defs["threshold_type"].eq("primary_20pct")][["signal_name", "n_events", "event_frequency", "event_direction", "min_event_count_passed", "event_selectivity_passed"]]
    rows = []
    for sig, g in summary.groupby("signal_name"):
        d = primary_defs[primary_defs["signal_name"].eq(sig)].iloc[0].to_dict()
        irow = inc[inc["signal_name"].eq(sig)]
        inc_flag = irow["incrementality_flag"].iloc[0] if not irow.empty else "INSUFFICIENT_DATA"
        g4 = g[g["horizon_weeks"].eq(4)]
        g8 = g[g["horizon_weeks"].eq(8)]
        best = g.sort_values(["return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks"], ascending=False).iloc[0]
        risk_sig = d["event_direction"] in {"risk_off_stress", "defensive_leadership", "state_quality_or_risk"}
        if not d["min_event_count_passed"]:
            decision = "PROMISING_BUT_NEEDS_MORE_EVENTS"
            reason = "Primary event count below minimum."
        elif inc_flag in {"MOSTLY_DUPLICATES_STATE_ENGINE", "REDUNDANT_WITH_STRONGER_SIGNAL"}:
            decision = "REDUNDANT_OR_DUPLICATIVE"
            reason = f"Event timing flag: {inc_flag}."
        elif risk_sig:
            risk_lift = max(float(g4["negative_barrier_lift_vs_all_weeks"].max()) if not g4.empty else -9, float(g8["negative_barrier_lift_vs_all_weeks"].max()) if not g8.empty else -9)
            avoid_rate = float(g["precision_avoids_bad_outcome"].mean())
            if risk_lift >= 0.05:
                decision = "KEEP_FOR_OOO3_VOL_MANAGED_SIZING"
                reason = "Risk event identifies elevated negative-barrier odds; sizing/risk-dial validation needed."
            elif avoid_rate >= 0.72 and best["return_lift_vs_all_weeks"] > 0:
                decision = "KEEP_STATE_SPECIFIC_META_LABEL"
                reason = "Event avoids adverse tails and has positive return lift."
            else:
                decision = "REJECT_EVENT_VALIDATION"
                reason = "Risk event did not show enough adverse-path or favorable asymmetry lift."
        else:
            pos_lift = max(float(g4["positive_barrier_lift_vs_all_weeks"].max()) if not g4.empty else -9, float(g8["positive_barrier_lift_vs_all_weeks"].max()) if not g8.empty else -9)
            ret_lift = max(float(g4["return_lift_vs_all_weeks"].max()) if not g4.empty else -9, float(g8["return_lift_vs_all_weeks"].max()) if not g8.empty else -9)
            neg_ok = float(g[["negative_barrier_lift_vs_all_weeks"]].max().iloc[0]) <= 0.05
            holdout_ok = bool((g["holdout_event_count"].fillna(0) >= 10).any() and (g["holdout_avg_final_return"].fillna(-9) > 0).any())
            if pos_lift >= 0.04 and ret_lift > 0 and neg_ok and bool(d["event_selectivity_passed"]) and holdout_ok:
                decision = "KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH"
                reason = "Opportunity event beats baseline with acceptable negative-barrier lift."
            elif ret_lift > 0 or pos_lift >= 0.025:
                decision = "KEEP_FOR_OOO3_VOL_MANAGED_SIZING"
                reason = "Directional lift exists but needs volatility/sizing/selectivity polish."
            else:
                decision = "REJECT_EVENT_VALIDATION"
                reason = "Event did not improve path outcomes versus all-weeks baseline."
        rows.append({
            "signal_name": sig,
            "decision": decision,
            "reason": reason,
            "event_count": int(d["n_events"]),
            "event_frequency": float(d["event_frequency"]),
            "event_selectivity_passed": bool(d["event_selectivity_passed"]),
            "event_direction": d["event_direction"],
            "incrementality_flag": inc_flag,
            "best_avg_return_lift": float(g["return_lift_vs_all_weeks"].max()),
            "best_positive_barrier_lift": float(g["positive_barrier_lift_vs_all_weeks"].max()),
            "best_negative_barrier_lift": float(g["negative_barrier_lift_vs_all_weeks"].max()),
            "avg_precision_beats_production": float(g["precision_beats_old_production"].mean()),
            "avg_precision_avoids_bad": float(g["precision_avoids_bad_outcome"].mean()),
            "holdout_event_count_max": int(g["holdout_event_count"].fillna(0).max()) if "holdout_event_count" in g else 0,
            "holdout_avg_return_best": float(g["holdout_avg_final_return"].fillna(-9).max()) if "holdout_avg_final_return" in g else np.nan,
            "holdout_feasible": True,
        })
    dec = pd.DataFrame(rows).sort_values(["decision", "best_avg_return_lift"], ascending=[True, False])
    keep = {
        "KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH",
        "KEEP_FOR_OOO3_VOL_MANAGED_SIZING",
        "KEEP_STATE_SPECIFIC_META_LABEL",
        "PROMISING_BUT_NEEDS_MORE_EVENTS",
    }
    queue = dec[dec["decision"].isin(keep)].copy()
    def next_phase(x: str) -> str:
        if x == "KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH":
            return "OOO6 GGG1 portfolio pass-through"
        if x == "KEEP_FOR_OOO3_VOL_MANAGED_SIZING":
            return "OOO3 volatility-managed signal sizing"
        return "additional event validation before portfolio pass-through"
    if not queue.empty:
        queue["assigned_next_phase"] = queue["decision"].map(next_phase)
        queue = queue.sort_values(["decision", "best_avg_return_lift"], ascending=[True, False])
    if dec["decision"].eq("KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH").any():
        rec = "PROCEED_TO_OOO6_PORTFOLIO_PASS_THROUGH"
        reason = "OOO5 found at least one selective event signal strong enough for later GGG1 pass-through testing."
    elif dec["decision"].eq("KEEP_FOR_OOO3_VOL_MANAGED_SIZING").any():
        rec = "PROCEED_TO_OOO3_VOL_MANAGED_SIGNAL_SIZING"
        reason = "OOO5 found event evidence, but direct pass-through gates were not clean enough; volatility/selectivity sizing is needed first."
    elif dec["decision"].eq("KEEP_STATE_SPECIFIC_META_LABEL").any():
        rec = "PROCEED_TO_OOO3_VOL_MANAGED_SIGNAL_SIZING"
        reason = "OOO5 found state-specific meta-label evidence that needs sizing validation before portfolio pass-through."
    elif dec["decision"].eq("PROMISING_BUT_NEEDS_MORE_EVENTS").any():
        rec = "NEEDS_MORE_SIGNAL_DISCOVERY"
        reason = "OOO5 found promising but event-sparse signals; more signal discovery or broader validation is needed."
    else:
        rec = "STOP_SIGNAL_DISCOVERY_FOR_NOW"
        reason = "OOO5 did not find event-validated signals strong enough to continue."
    plan = pd.DataFrame([{
        "recommendation": rec,
        "reason": reason,
        "next_prompt_outline": "Use OOO5 event decisions to test volatility-managed sizing or, only for direct keep signals, a later GGG1 portfolio pass-through. Do not create portfolio candidates before that gate.",
    }])
    return dec, queue, plan


def md_table(df: pd.DataFrame, cols: list[str] | None = None, n: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df[cols].head(n).copy() if cols else df.head(n).copy()
    for col in small.select_dtypes(include=[np.number]).columns:
        small[col] = small[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
    lines = ["| " + " | ".join(small.columns) + " |", "| " + " | ".join(["---"] * len(small.columns)) + " |"]
    for _, row in small.iterrows():
        lines.append("| " + " | ".join(str(row[c]) for c in small.columns) + " |")
    return "\n".join(lines)


def write_report(defs: pd.DataFrame, summary: pd.DataFrame, state_summary: pd.DataFrame, lift: pd.DataFrame, inc: pd.DataFrame, dec: pd.DataFrame, queue: pd.DataFrame, plan: pd.DataFrame) -> None:
    DOC.write_text(f"""# Phase OOO5 -- Triple-Barrier Signal Validation

Date: 2026-04-27

## Commands executed
```
{chr(10).join(COMMANDS)}
```

## Files created / modified
- `scripts/phase_ooo5_triple_barrier_signal_validation.py`
- `data/research/phase_ooo_signal_discovery/ooo5_triple_barrier_validation/*.csv`
- `docs/research/2026-04-27_phase_ooo5_triple_barrier_signal_validation_report.md`
- `docs/research/project_journey.md`

## OOO2 signal queue used
OOO5 used OOO2 signals classified as `KEEP_HIGH_PRIORITY`,
`KEEP_STATE_SPECIFIC`, or `KEEP_FOR_TRIPLE_BARRIER_VALIDATION`. No portfolio
candidates, pin changes, or strategy logic changes were created.

## Event definitions
{md_table(defs[defs["threshold_type"].eq("primary_20pct")], ["signal_name", "event_direction", "threshold_side", "threshold_value", "state_filter", "n_events", "event_frequency", "min_event_count_passed", "event_selectivity_passed"], 16)}

## Triple-barrier methodology
Events use the OOO2 lagged signal panel. Primary events fire at the fixed top
or bottom 20% threshold; 30% events are diagnostic only. GGG1 outcomes use
4w/8w/13w forward paths, trailing 13-week weekly volatility known at the event
date, upper barrier `+1.0 * vol * sqrt(horizon)`, lower barrier
`-1.0 * vol * sqrt(horizon)`, and vertical horizon close.

## Event performance summary
{md_table(summary.sort_values(["return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks"], ascending=False), ["signal_name", "event_direction", "horizon_weeks", "event_count", "positive_barrier_hit_rate", "negative_barrier_hit_rate", "avg_final_return", "return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks", "negative_barrier_lift_vs_all_weeks", "holdout_event_count", "holdout_avg_final_return"], 18)}

## State-specific event behavior
{md_table(state_summary.sort_values(["return_lift_vs_same_state", "positive_barrier_lift_vs_same_state"], ascending=False), ["signal_name", "market_state", "horizon_weeks", "event_count", "avg_final_return", "return_lift_vs_same_state", "positive_barrier_lift_vs_same_state", "negative_barrier_lift_vs_same_state"], 18)}

## Baseline comparison
{md_table(lift.sort_values(["return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks"], ascending=False), ["signal_name", "horizon_weeks", "event_count", "return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks", "negative_barrier_lift_vs_all_weeks", "precision_beats_old_production", "precision_avoids_bad_outcome"], 18)}

## Event overlap / incrementality
{md_table(inc.sort_values(["incrementality_flag", "n_events"]), ["signal_name", "n_events", "dominant_market_state", "max_state_overlap", "high_bil_overlap", "max_signal_event_overlap", "incrementality_flag"], 16)}

## Keep / reject decisions
{md_table(dec, ["signal_name", "decision", "event_count", "event_frequency", "event_selectivity_passed", "event_direction", "incrementality_flag", "best_avg_return_lift", "best_positive_barrier_lift", "best_negative_barrier_lift", "holdout_avg_return_best", "reason"], 16)}

## Top signals to test next
{md_table(queue, ["signal_name", "decision", "assigned_next_phase", "best_avg_return_lift", "best_positive_barrier_lift"], 8)}

## Final recommendation
**{plan.iloc[0]['recommendation']}**

Reason: {plan.iloc[0]['reason']}

## How OOO5 feeds OOO3 or OOO6
OOO5 is an event-validation gate. Signals routed to OOO3 need volatility-managed
sizing before any portfolio pass-through. Signals routed to OOO6 may be tested
later through GGG1, but this phase created no portfolio candidates.

## Exact prompt outline for next phase
{plan.iloc[0]['next_prompt_outline']}
""")


def update_journey(rec: str, reason: str) -> None:
    section = f"""

## Section 85 -- Phase OOO5 Triple-Barrier Signal Validation

Date: 2026-04-27. OOO5 tested the OOO2 surviving signals with fixed event
thresholds, GGG1 triple-barrier outcomes, same-state/all-week baselines, and
event-overlap incrementality checks. No portfolio candidates, production pins,
or strategy logic were changed.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 85 -- Phase OOO5 Triple-Barrier Signal Validation"
    if marker in text:
        text = re.sub(r"\n## Section 85 -- Phase OOO5 Triple-Barrier Signal Validation[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    queue, _decisions, panel, states = load_inputs()
    defs, events = build_event_definitions(queue, panel, states)
    tb, meta, rets = compute_event_outcomes(events)
    weights = read_indexed(L3 / f"portfolio_version_weights_{GGG1}.csv")
    summary, state_summary, lift = summarize(tb, meta, rets, states)
    overlap, inc = overlap_and_incrementality(events, states, weights)
    dec, next_queue, plan = decisions(summary, inc, defs)

    defs.to_csv(OUT / "ooo5_signal_event_definitions.csv", index=False)
    events.to_csv(OUT / "ooo5_signal_events.csv", index=False)
    tb.to_csv(OUT / "ooo5_triple_barrier_event_outcomes.csv", index=False)
    meta.to_csv(OUT / "ooo5_meta_label_event_outcomes.csv", index=False)
    summary.to_csv(OUT / "ooo5_event_performance_summary.csv", index=False)
    state_summary.to_csv(OUT / "ooo5_state_specific_event_performance.csv", index=False)
    lift.to_csv(OUT / "ooo5_signal_vs_baseline_event_lift.csv", index=False)
    overlap.to_csv(OUT / "ooo5_event_overlap_matrix.csv", index=False)
    inc.to_csv(OUT / "ooo5_incrementality_after_event_filtering.csv", index=False)
    dec.to_csv(OUT / "ooo5_signal_event_validation_decisions.csv", index=False)
    next_queue.to_csv(OUT / "ooo5_next_phase_signal_queue.csv", index=False)
    plan.to_csv(OUT / "ooo5_next_phase_recommendation.csv", index=False)

    write_report(defs, summary, state_summary, lift, inc, dec, next_queue, plan)
    update_journey(str(plan.iloc[0]["recommendation"]), str(plan.iloc[0]["reason"]))
    print("Phase OOO5 triple-barrier signal validation complete")
    print(f"signals_tested: {defs['signal_name'].nunique()}")
    print(f"primary_events: {events[events['threshold_type'].eq('primary_20pct')].shape[0]}")
    print(f"triple_barrier_rows: {len(tb)}")
    print(f"recommendation: {plan.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
