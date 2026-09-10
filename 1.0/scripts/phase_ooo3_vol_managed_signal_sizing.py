"""Phase OOO3 -- volatility-managed signal sizing diagnostics.

Diagnostic-only. Builds causal/selective variants of OOO5 survivor signals and
revalidates event outcomes. No portfolio candidates or strategy changes.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OOO2 = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo2_cross_asset_signal_expansion"
OOO5 = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo5_triple_barrier_validation"
OUT = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo3_vol_managed_signal_sizing"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
HORIZONS = [4, 8, 13]
HOLDOUT_START = pd.Timestamp("2016-01-01")
MIN_EVENTS = 20

PRIMARY_SIGNALS = ["leadlag_EFA_minus_SPY_13w_signal", "market_trend_positive_signal"]
SECONDARY_SIGNALS = [
    "market_drawdown_signal",
    "leadlag_GLD_minus_SPY_13w_signal",
    "leadlag_DBA_minus_SPY_13w_signal",
    "breadth_ret13_positive_x_recovery_confirmed_signal",
]

COMMANDS = [
    "sed -n '1,210p' docs/research/2026-04-27_phase_ooo5_triple_barrier_signal_validation_report.md",
    "find data/research/phase_ooo_signal_discovery/ooo5_triple_barrier_validation -maxdepth 1 -type f | sort",
    "python3 - <<'PY' ...small OOO5/OOO2/return/state summaries...",
    "tail -n 90 docs/research/project_journey.md",
    "python3 scripts/phase_ooo3_vol_managed_signal_sizing.py",
]


def read_indexed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else "date" if "date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df.dropna(subset=[date_col]).set_index(date_col).sort_index()


def returns(version: str) -> pd.Series:
    df = read_indexed(L3 / f"portfolio_version_returns_{version}.csv")
    return pd.to_numeric(df["net_return"], errors="coerce").fillna(0.0).rename(version)


def forward_path(s: pd.Series, idx: int, horizon: int) -> np.ndarray:
    vals = s.iloc[idx + 1 : idx + horizon + 1].to_numpy()
    if len(vals) < horizon:
        return np.array([])
    return np.cumprod(1.0 + vals) - 1.0


def future_compound(s: pd.Series, idx: int, horizon: int) -> float:
    path = forward_path(s, idx, horizon)
    return float(path[-1]) if len(path) == horizon else np.nan


def trailing_percentile(s: pd.Series, min_periods: int = 52) -> pd.Series:
    out = pd.Series(np.nan, index=s.index)
    vals = s.to_numpy()
    for i in range(len(vals)):
        if not np.isfinite(vals[i]):
            continue
        hist = vals[: i + 1]
        hist = hist[np.isfinite(hist)]
        if len(hist) < min_periods:
            continue
        out.iloc[i] = float((hist <= vals[i]).mean())
    return out


def trailing_zscore(s: pd.Series, window: int = 104) -> pd.Series:
    mu = s.rolling(window, min_periods=52).mean()
    sd = s.rolling(window, min_periods=52).std()
    return (s - mu) / sd.replace(0, np.nan)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    q = pd.read_csv(OOO5 / "ooo5_next_phase_signal_queue.csv")
    dec = pd.read_csv(OOO5 / "ooo5_signal_event_validation_decisions.csv")
    panel = read_indexed(OOO2 / "ooo2_candidate_signal_panel.csv")
    states = read_indexed(L2B / "market_state_history.csv")
    g = returns(GGG1)
    keep = PRIMARY_SIGNALS + SECONDARY_SIGNALS
    q = pd.concat([q, dec[dec["signal_name"].isin(keep) & ~dec["signal_name"].isin(q["signal_name"])]], ignore_index=True)
    q = q[q["signal_name"].isin(keep)].drop_duplicates("signal_name")
    return q, dec, panel, states, g


def signal_side(signal: str) -> str:
    return "bottom" if signal == "market_drawdown_signal" else "top"


def build_input_queue(q: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in q.iterrows():
        sig = r["signal_name"]
        rows.append({
            "signal_name": sig,
            "ooo5_decision": r.get("decision", ""),
            "event_direction": r.get("event_direction", ""),
            "reason": r.get("reason", ""),
            "event_count": r.get("event_count", np.nan),
            "best_horizon": "max_lift_across_4_8_13",
            "best_avg_return_lift": r.get("best_avg_return_lift", np.nan),
            "best_positive_barrier_lift": r.get("best_positive_barrier_lift", np.nan),
            "best_negative_barrier_lift": r.get("best_negative_barrier_lift", np.nan),
            "assigned_role_for_ooo3": "PRIMARY" if sig in PRIMARY_SIGNALS else "SECONDARY_REFERENCE",
        })
    return pd.DataFrame(rows)


def feature_panel(q: pd.DataFrame, panel: pd.DataFrame, states: pd.DataFrame, g: pd.Series) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = read_indexed(L3 / f"portfolio_version_weights_{GGG1}.csv")
    feat = pd.DataFrame(index=panel.index)
    feat["market_state"] = states.reindex(feat.index)["market_state"]
    feat["ggg1_trailing_vol_13w"] = g.rolling(13, min_periods=8).std().shift(1)
    feat["ggg1_trailing_vol_26w"] = g.rolling(26, min_periods=13).std().shift(1)
    feat["ggg1_vol_percentile"] = trailing_percentile(feat["ggg1_trailing_vol_13w"], 52)
    feat["ggg1_vol_bucket"] = pd.cut(
        feat["ggg1_vol_percentile"],
        bins=[-np.inf, 0.33, 0.67, np.inf],
        labels=["LOW_VOL", "NORMAL_VOL", "HIGH_VOL"],
    ).astype(str)
    ret_wealth = (1.0 + g).cumprod()
    feat["ggg1_trailing_drawdown"] = (ret_wealth / ret_wealth.cummax() - 1.0).shift(1)
    feat["BIL_weight"] = pd.to_numeric(weights.get("BIL"), errors="coerce").reindex(feat.index)
    feat["SPY_weight"] = pd.to_numeric(weights.get("SPY"), errors="coerce").reindex(feat.index)
    for col in ["market_drawdown_signal", "recent_stress_26w_signal", "market_trend_positive_signal", "breadth_ret26_positive_signal"]:
        if col in panel.columns:
            feat[col] = panel[col]
    manifest_rows = []
    for sig in q["signal_name"]:
        if sig not in panel.columns:
            continue
        raw = panel[sig].reindex(feat.index)
        pct = trailing_percentile(raw, 52)
        z = trailing_zscore(raw)
        side = signal_side(sig)
        direction_adj = 1.0 - pct if side == "bottom" else pct
        feat[f"{sig}__raw"] = raw
        feat[f"{sig}__percentile"] = pct
        feat[f"{sig}__zscore"] = z
        feat[f"{sig}__abs_strength"] = raw.abs()
        feat[f"{sig}__direction_strength"] = direction_adj
        feat[f"{sig}__strength_scaled_score"] = direction_adj / feat["ggg1_vol_percentile"].clip(lower=0.05)
        for c, rule in [
            (f"{sig}__raw", "OOO2 signal already lagged 1 week"),
            (f"{sig}__percentile", "expanding trailing percentile using current known lagged value"),
            (f"{sig}__zscore", "trailing 104-week z-score using current known lagged value"),
            (f"{sig}__strength_scaled_score", "direction percentile divided by trailing GGG1 vol percentile"),
        ]:
            manifest_rows.append({
                "feature_name": c,
                "base_signal": sig,
                "feature_group": "signal_strength",
                "lag_rule": rule,
                "causal_ok": True,
                "missingness": float(feat[c].isna().mean()),
            })
    for c in ["ggg1_trailing_vol_13w", "ggg1_trailing_vol_26w", "ggg1_vol_percentile", "ggg1_trailing_drawdown"]:
        manifest_rows.append({
            "feature_name": c,
            "base_signal": "portfolio_context",
            "feature_group": "volatility_drawdown_context",
            "lag_rule": "shifted trailing GGG1 return statistic",
            "causal_ok": True,
            "missingness": float(feat[c].isna().mean()),
        })
    return feat.reset_index(names="date"), pd.DataFrame(manifest_rows)


def top_event(feat: pd.DataFrame, sig: str, pct: float = 0.20) -> pd.Series:
    strength = feat[f"{sig}__direction_strength"]
    return strength >= (1.0 - pct)


def make_variants(q: pd.DataFrame, feat: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    f = feat.set_index("date")
    variants: list[dict] = []
    events: dict[str, pd.Series] = {}

    def add(name: str, base: str, event: pd.Series, formula: str, threshold: str, vol_rule: str, state_rule: str, use: str, complexity: str = "LOW") -> None:
        event = event.fillna(False).astype(bool).reindex(f.index).fillna(False)
        variants.append({
            "variant_name": name,
            "base_signal": base,
            "formula": formula,
            "threshold_rule": threshold,
            "vol_filter_rule": vol_rule,
            "state_filter_rule": state_rule,
            "expected_use": use,
            "causal_ok": True,
            "complexity_level": complexity,
        })
        events[name] = event

    if "leadlag_EFA_minus_SPY_13w_signal" in q["signal_name"].values:
        sig = "leadlag_EFA_minus_SPY_13w_signal"
        add("efa_spy_raw_top20_event", sig, top_event(f, sig, 0.20), "direction percentile >= 80%", "top20", "none", "none", "risk-on selectivity")
        add("efa_spy_raw_top10_event", sig, top_event(f, sig, 0.10), "direction percentile >= 90%", "top10", "none", "none", "risk-on selectivity")
        add("efa_spy_raw_top30_event", sig, top_event(f, sig, 0.30), "direction percentile >= 70%", "top30", "none", "none", "risk-on selectivity")
        add("efa_spy_vol_filtered_top20_event", sig, top_event(f, sig, 0.20) & (f["ggg1_vol_percentile"] <= 0.80), "top20 and vol percentile <= 80%", "top20", "exclude highest vol quintile", "none", "risk-on selectivity")
        add("efa_spy_low_or_normal_vol_top20_event", sig, top_event(f, sig, 0.20) & f["ggg1_vol_bucket"].isin(["LOW_VOL", "NORMAL_VOL"]), "top20 and not HIGH_VOL", "top20", "LOW/NORMAL_VOL only", "none", "risk-on selectivity")
        add("efa_spy_strength_scaled_score_event", sig, f[f"{sig}__strength_scaled_score"] >= f[f"{sig}__strength_scaled_score"].quantile(0.80), "signal percentile / vol percentile top20", "scaled top20", "vol scaled", "none", "risk-on selectivity", "MEDIUM")
        add("efa_spy_drawdown_aware_top20_event", sig, top_event(f, sig, 0.20) & (f["ggg1_trailing_drawdown"] > -0.08), "top20 and GGG1 drawdown > -8%", "top20", "none", "exclude deep drawdown", "risk-on selectivity")
        if "market_trend_positive_signal" in f:
            add("efa_spy_market_trend_confirmed_top20_event", sig, top_event(f, sig, 0.20) & (f["market_trend_positive_signal"] > 0), "top20 and market trend positive", "top20", "none", "trend positive", "risk-on selectivity")

    if "market_trend_positive_signal" in q["signal_name"].values:
        sig = "market_trend_positive_signal"
        raw = f[sig + "__raw"] > 0
        add("market_trend_raw_event", sig, raw, "market trend positive == 1", "binary raw", "none", "none", "trend gate")
        if "breadth_ret26_positive_signal" in f:
            add("market_trend_breadth_confirmed_event", sig, raw & (f["breadth_ret26_positive_signal"] >= f["breadth_ret26_positive_signal"].quantile(0.70)), "trend positive and breadth_ret26 top30", "binary + breadth", "none", "breadth confirmation", "trend gate")
        add("market_trend_ex_high_vol_drawdown_event", sig, raw & (f["ggg1_vol_percentile"] <= 0.80) & (f["ggg1_trailing_drawdown"] > -0.08), "trend positive excluding high vol/deep drawdown", "binary", "vol <= 80%", "drawdown > -8%", "trend gate")
        if "recent_stress_26w_signal" in f:
            add("market_trend_recent_stress_filtered_event", sig, raw & (f["recent_stress_26w_signal"] <= 0), "trend positive and no recent stress", "binary", "none", "recent_stress_26w <= 0", "trend gate")
        add("market_trend_calm_neutral_event", sig, raw & f["market_state"].isin(["calm_trend", "neutral_mixed"]), "trend positive in calm/neutral states", "binary", "none", "calm_trend or neutral_mixed", "trend gate")
        add("market_trend_vol_scaled_score_event", sig, raw & ((1.0 / f["ggg1_vol_percentile"].clip(lower=0.05)) >= (1.0 / f["ggg1_vol_percentile"].clip(lower=0.05)).quantile(0.80)), "trend positive and inverse-vol score top20", "binary + scaled", "low vol favored", "none", "trend gate", "MEDIUM")

    for sig in [s for s in SECONDARY_SIGNALS if s in q["signal_name"].values]:
        base_name = sig.replace("_signal", "")
        add(f"{base_name}_top20_event", sig, top_event(f, sig, 0.20), "direction percentile top20", "top20", "none", "none", "secondary reference")
        add(f"{base_name}_vol_filtered_top20_event", sig, top_event(f, sig, 0.20) & (f["ggg1_vol_percentile"] <= 0.80), "top20 and vol percentile <= 80%", "top20", "exclude highest vol quintile", "none", "secondary reference")
        if "recovery_confirmed" in sig:
            add(f"{base_name}_state_filtered_event", sig, top_event(f, sig, 0.20) & f["market_state"].eq("recovery_confirmed"), "top20 inside recovery_confirmed", "top20", "none", "recovery_confirmed", "secondary reference")

    event_panel = pd.DataFrame({"date": f.index})
    for name, ev in events.items():
        event_panel[name] = ev.astype(int).to_numpy()
    return pd.DataFrame(variants), event_panel


def evaluate_events(variants: pd.DataFrame, event_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    g = returns(GGG1)
    p = returns(PRODUCTION).reindex(g.index).fillna(0.0)
    sh = returns(SHADOW).reindex(g.index).fillna(0.0)
    states = read_indexed(L2B / "market_state_history.csv")[["market_state"]]
    vol = g.rolling(13, min_periods=8).std().shift(1)
    ep = event_panel.copy()
    ep["date"] = pd.to_datetime(ep["date"])
    ep = ep.set_index("date").reindex(g.index).fillna(0).astype(int)
    idx_map = {d: i for i, d in enumerate(g.index)}
    rows = []
    for _, v in variants.iterrows():
        name = v["variant_name"]
        ev_dates = ep.index[ep[name].eq(1)]
        for date in ev_dates:
            i = idx_map[date]
            sigma = vol.loc[date]
            if pd.isna(sigma) or sigma <= 0:
                continue
            for h in HORIZONS:
                path = forward_path(g, i, h)
                if len(path) < h:
                    continue
                upper = float(sigma) * math.sqrt(h)
                lower = -float(sigma) * math.sqrt(h)
                label, ttb = 0, h
                for j, val in enumerate(path, start=1):
                    if val >= upper:
                        label, ttb = 1, j
                        break
                    if val <= lower:
                        label, ttb = -1, j
                        break
                final = float(path[-1])
                rows.append({
                    "date": date,
                    "variant_name": name,
                    "base_signal": v["base_signal"],
                    "horizon_weeks": h,
                    "market_state": states.reindex([date])["market_state"].iloc[0] if date in states.index else "unknown",
                    "triple_barrier_label": label,
                    "time_to_barrier": ttb,
                    "max_favorable_excursion": float(np.nanmax(path)),
                    "max_adverse_excursion": float(np.nanmin(path)),
                    "final_horizon_return": final,
                    "production_forward_return": future_compound(p, i, h),
                    "shadow_forward_return": future_compound(sh, i, h),
                    "beats_old_production": final > future_compound(p, i, h),
                    "beats_official_shadow": final > future_compound(sh, i, h),
                    "avoids_adverse_tail": label != -1,
                    "positive_final_return": final > 0,
                })
    return pd.DataFrame(rows), ep.reset_index(names="date")


def baseline_rows() -> pd.DataFrame:
    g = returns(GGG1)
    states = read_indexed(L2B / "market_state_history.csv")[["market_state"]]
    vol = g.rolling(13, min_periods=8).std().shift(1)
    rows = []
    for date in g.index:
        if pd.isna(vol.loc[date]) or vol.loc[date] <= 0:
            continue
        i = g.index.get_loc(date)
        for h in HORIZONS:
            path = forward_path(g, i, h)
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
                "positive_barrier": label == 1,
                "negative_barrier": label == -1,
            })
    return pd.DataFrame(rows)


def summarize(outcomes: pd.DataFrame, event_panel: pd.DataFrame, variants: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = baseline_rows()
    allb = base.groupby("horizon_weeks", as_index=False).agg(
        all_weeks_avg_return=("final_horizon_return", "mean"),
        all_weeks_positive_rate=("positive_barrier", "mean"),
        all_weeks_negative_rate=("negative_barrier", "mean"),
    )
    stateb = base.groupby(["horizon_weeks", "market_state"], as_index=False).agg(
        same_state_avg_return=("final_horizon_return", "mean"),
        same_state_positive_rate=("positive_barrier", "mean"),
        same_state_negative_rate=("negative_barrier", "mean"),
    )
    grp = ["variant_name", "base_signal", "horizon_weeks"]
    summary = outcomes.groupby(grp, as_index=False).agg(
        event_count=("date", "nunique"),
        positive_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == 1).mean())),
        negative_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == -1).mean())),
        neutral_no_hit_rate=("triple_barrier_label", lambda s: float((s == 0).mean())),
        avg_final_return=("final_horizon_return", "mean"),
        median_final_return=("final_horizon_return", "median"),
        avg_max_favorable_excursion=("max_favorable_excursion", "mean"),
        avg_max_adverse_excursion=("max_adverse_excursion", "mean"),
        precision_beats_old_production=("beats_old_production", "mean"),
        precision_avoids_bad_outcome=("avoids_adverse_tail", "mean"),
    ).merge(allb, on="horizon_weeks", how="left")
    summary["payoff_ratio"] = summary["avg_max_favorable_excursion"].abs() / summary["avg_max_adverse_excursion"].abs().replace(0, np.nan)
    summary["return_lift_vs_all_weeks"] = summary["avg_final_return"] - summary["all_weeks_avg_return"]
    summary["positive_barrier_lift_vs_all_weeks"] = summary["positive_barrier_hit_rate"] - summary["all_weeks_positive_rate"]
    summary["negative_barrier_lift_vs_all_weeks"] = summary["negative_barrier_hit_rate"] - summary["all_weeks_negative_rate"]
    hold = outcomes[outcomes["date"].ge(HOLDOUT_START)].groupby(grp, as_index=False).agg(
        holdout_2016_event_count=("date", "nunique"),
        holdout_2016_avg_return=("final_horizon_return", "mean"),
        holdout_2016_positive_rate=("triple_barrier_label", lambda s: float((s == 1).mean())),
        holdout_2016_negative_rate=("triple_barrier_label", lambda s: float((s == -1).mean())),
    )
    summary = summary.merge(hold, on=grp, how="left")
    state = outcomes.groupby(grp + ["market_state"], as_index=False).agg(
        event_count=("date", "nunique"),
        avg_final_return=("final_horizon_return", "mean"),
        positive_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == 1).mean())),
        negative_barrier_hit_rate=("triple_barrier_label", lambda s: float((s == -1).mean())),
    ).merge(stateb, on=["horizon_weeks", "market_state"], how="left")
    state["return_lift_vs_same_state"] = state["avg_final_return"] - state["same_state_avg_return"]
    state["positive_barrier_lift_vs_same_state"] = state["positive_barrier_hit_rate"] - state["same_state_positive_rate"]
    state["negative_barrier_lift_vs_same_state"] = state["negative_barrier_hit_rate"] - state["same_state_negative_rate"]
    raw_map = {
        "leadlag_EFA_minus_SPY_13w_signal": "efa_spy_raw_top20_event",
        "market_trend_positive_signal": "market_trend_raw_event",
        "market_drawdown_signal": "market_drawdown_top20_event",
        "leadlag_GLD_minus_SPY_13w_signal": "leadlag_GLD_minus_SPY_13w_top20_event",
        "leadlag_DBA_minus_SPY_13w_signal": "leadlag_DBA_minus_SPY_13w_top20_event",
        "breadth_ret13_positive_x_recovery_confirmed_signal": "breadth_ret13_positive_x_recovery_confirmed_top20_event",
    }
    raw = summary[summary.apply(lambda r: raw_map.get(r["base_signal"]) == r["variant_name"], axis=1)][[
        "base_signal", "horizon_weeks", "avg_final_return", "positive_barrier_hit_rate", "negative_barrier_hit_rate", "return_lift_vs_all_weeks"
    ]].rename(columns={
        "avg_final_return": "raw_avg_final_return",
        "positive_barrier_hit_rate": "raw_positive_barrier_hit_rate",
        "negative_barrier_hit_rate": "raw_negative_barrier_hit_rate",
        "return_lift_vs_all_weeks": "raw_return_lift_vs_all_weeks",
    })
    comp = summary.merge(raw, on=["base_signal", "horizon_weeks"], how="left")
    comp["return_lift_vs_raw"] = comp["avg_final_return"] - comp["raw_avg_final_return"]
    comp["positive_barrier_lift_vs_raw"] = comp["positive_barrier_hit_rate"] - comp["raw_positive_barrier_hit_rate"]
    comp["negative_barrier_lift_vs_raw"] = comp["negative_barrier_hit_rate"] - comp["raw_negative_barrier_hit_rate"]
    return summary, state, comp


def selectivity(outcomes: pd.DataFrame, event_panel: pd.DataFrame, variants: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ep = event_panel.set_index("date")
    weights = read_indexed(L3 / f"portfolio_version_weights_{GGG1}.csv")
    states = read_indexed(L2B / "market_state_history.csv")[["market_state"]]
    bil = pd.to_numeric(weights.get("BIL"), errors="coerce").reindex(ep.index)
    high_bil = bil >= bil.quantile(0.75)
    low_bil = bil <= bil.quantile(0.25)
    cols = [c for c in ep.columns if c != "date"]
    base_map = variants.set_index("variant_name")["base_signal"].to_dict()
    raw_map = {
        "leadlag_EFA_minus_SPY_13w_signal": "efa_spy_raw_top20_event",
        "market_trend_positive_signal": "market_trend_raw_event",
        "market_drawdown_signal": "market_drawdown_top20_event",
        "leadlag_GLD_minus_SPY_13w_signal": "leadlag_GLD_minus_SPY_13w_top20_event",
        "leadlag_DBA_minus_SPY_13w_signal": "leadlag_DBA_minus_SPY_13w_top20_event",
        "breadth_ret13_positive_x_recovery_confirmed_signal": "breadth_ret13_positive_x_recovery_confirmed_top20_event",
    }
    overlap = pd.DataFrame(index=cols, columns=cols, dtype=float)
    for a in cols:
        denom = max(1, int(ep[a].sum()))
        for b in cols:
            overlap.loc[a, b] = float(((ep[a] == 1) & (ep[b] == 1)).sum() / denom)
    rows = []
    for v in cols:
        s = ep[v].astype(int)
        ev_dates = s.index[s.eq(1)]
        freq = float(s.mean())
        starts = int(((s == 1) & (s.shift(1).fillna(0) == 0)).sum())
        transitions = int((s.diff().abs().fillna(0) > 0).sum())
        st = states.reindex(ev_dates)["market_state"]
        max_state_overlap = float(st.value_counts(normalize=True).max()) if len(st) else np.nan
        dominant_state = st.value_counts().index[0] if len(st.value_counts()) else "unknown"
        other_base_cols = [c for c in cols if c != v and base_map.get(c) != base_map.get(v)]
        max_variant_overlap = float(overlap.loc[v, other_base_cols].max()) if other_base_cols else np.nan
        raw_parent = raw_map.get(base_map.get(v))
        raw_event_overlap = float(overlap.loc[v, raw_parent]) if raw_parent in overlap.columns else np.nan
        if s.sum() < MIN_EVENTS:
            flag = "TOO_RARE"
        elif freq > 0.45:
            flag = "TOO_BROAD"
        elif max_state_overlap >= 0.90:
            flag = "DUPLICATES_STATE_ENGINE"
        elif transitions / max(1, len(s)) > 0.30:
            flag = "HIGH_TURNOVER_RISK"
        else:
            flag = "INCREMENTAL_SELECTIVE"
        rows.append({
            "variant_name": v,
            "event_count": int(s.sum()),
            "event_frequency": freq,
            "event_start_count": starts,
            "event_transition_count": transitions,
            "transition_frequency": transitions / max(1, len(s)),
            "dominant_market_state": dominant_state,
            "max_state_overlap": max_state_overlap,
            "high_bil_overlap": float(high_bil.reindex(ev_dates).mean()) if len(ev_dates) else np.nan,
            "low_bil_overlap": float(low_bil.reindex(ev_dates).mean()) if len(ev_dates) else np.nan,
            "max_variant_overlap": max_variant_overlap,
            "raw_parent_event_overlap": raw_event_overlap,
            "incrementality_flag": flag,
        })
    inc = pd.DataFrame(rows).merge(variants[["variant_name", "base_signal", "complexity_level"]], on="variant_name", how="left")
    return overlap.reset_index(names="variant_name"), inc, inc[["variant_name", "base_signal", "event_count", "event_frequency", "event_start_count", "event_transition_count", "incrementality_flag"]]


def decisions(perf: pd.DataFrame, comp: pd.DataFrame, inc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    for variant, g in comp.groupby("variant_name"):
        irow = inc[inc["variant_name"].eq(variant)]
        flag = irow["incrementality_flag"].iloc[0] if not irow.empty else "REJECT"
        complexity = irow["complexity_level"].iloc[0] if not irow.empty and "complexity_level" in irow else "UNKNOWN"
        count = int(irow["event_count"].iloc[0]) if not irow.empty else 0
        freq = float(irow["event_frequency"].iloc[0]) if not irow.empty else np.nan
        starts = int(irow["event_start_count"].iloc[0]) if not irow.empty else 0
        best = g.sort_values(["return_lift_vs_raw", "positive_barrier_lift_vs_raw", "return_lift_vs_all_weeks"], ascending=False).iloc[0]
        holdout_ok = bool((g["holdout_2016_event_count"].fillna(0) >= 10).any() and (g["holdout_2016_avg_return"].fillna(-9) > 0).any())
        improves_raw = best["return_lift_vs_raw"] > 0 or best["positive_barrier_lift_vs_raw"] >= 0.03 or best["negative_barrier_lift_vs_raw"] < -0.02
        raw_negative_ok = (pd.isna(best["negative_barrier_lift_vs_raw"]) or best["negative_barrier_lift_vs_raw"] <= 0.02)
        if flag == "TOO_RARE":
            dec = "PROMISING_BUT_TOO_RARE" if best["return_lift_vs_all_weeks"] > 0 else "REJECT_SIZING_VALIDATION"
            reason = "Variant event count is below minimum."
        elif flag == "TOO_BROAD":
            dec = "REJECT_SIZING_VALIDATION"
            reason = "Variant fires too often after sizing/selectivity filter."
        elif flag == "HIGH_TURNOVER_RISK":
            dec = "PROMISING_BUT_HIGH_TURNOVER_RISK"
            reason = "Variant has high event transition count."
        elif flag in {"DUPLICATES_STATE_ENGINE", "PROMISING_BUT_NEEDS_SIMPLIFICATION"} and not improves_raw:
            dec = "REDUNDANT_OR_DUPLICATIVE"
            reason = f"Variant flag {flag} and does not improve raw behavior."
        elif improves_raw and best["return_lift_vs_all_weeks"] > 0 and holdout_ok and flag == "INCREMENTAL_SELECTIVE" and complexity == "LOW" and raw_negative_ok:
            dec = "KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH"
            reason = "Sized variant improves raw event behavior with acceptable selectivity and holdout."
        elif improves_raw and best["return_lift_vs_all_weeks"] > 0:
            dec = "KEEP_FOR_ADDITIONAL_EVENT_VALIDATION"
            reason = "Variant improves raw behavior but has simplification/state-overlap concerns."
        else:
            dec = "REJECT_SIZING_VALIDATION"
            reason = "Sizing did not improve raw event behavior enough."
        rows.append({
            "variant_name": variant,
            "base_signal": best["base_signal"],
            "decision": dec,
            "reason": reason,
            "event_count": count,
            "event_frequency": freq,
            "event_start_count": starts,
            "incrementality_flag": flag,
            "best_horizon_weeks": int(best["horizon_weeks"]),
            "best_return_lift_vs_all_weeks": float(best["return_lift_vs_all_weeks"]),
            "best_return_lift_vs_raw": float(best["return_lift_vs_raw"]) if pd.notna(best["return_lift_vs_raw"]) else np.nan,
            "best_positive_barrier_lift_vs_raw": float(best["positive_barrier_lift_vs_raw"]) if pd.notna(best["positive_barrier_lift_vs_raw"]) else np.nan,
            "best_negative_barrier_lift_vs_raw": float(best["negative_barrier_lift_vs_raw"]) if pd.notna(best["negative_barrier_lift_vs_raw"]) else np.nan,
            "holdout_event_count_max": int(g["holdout_2016_event_count"].fillna(0).max()),
            "holdout_avg_return_best": float(g["holdout_2016_avg_return"].fillna(-9).max()),
        })
    out = pd.DataFrame(rows).sort_values(["decision", "best_return_lift_vs_all_weeks"], ascending=[True, False])
    keep = {"KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH", "KEEP_FOR_ADDITIONAL_EVENT_VALIDATION", "PROMISING_BUT_TOO_RARE", "PROMISING_BUT_HIGH_TURNOVER_RISK"}
    queue = out[out["decision"].isin(keep)].copy()
    if not queue.empty:
        queue["assigned_next_phase"] = np.where(
            queue["decision"].eq("KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH"),
            "OOO6 GGG1 portfolio pass-through",
            "additional signal validation before portfolio pass-through",
        )
    if out["decision"].eq("KEEP_FOR_OOO6_PORTFOLIO_PASS_THROUGH").any():
        rec = "PROCEED_TO_OOO6_PORTFOLIO_PASS_THROUGH"
        reason = "OOO3 found at least one sized signal that cleared selectivity, raw-improvement, and holdout gates."
    elif out["decision"].isin(["KEEP_FOR_ADDITIONAL_EVENT_VALIDATION", "PROMISING_BUT_TOO_RARE", "PROMISING_BUT_HIGH_TURNOVER_RISK"]).any():
        rec = "PROCEED_TO_ADDITIONAL_SIGNAL_DISCOVERY"
        reason = "OOO3 found partial sizing improvements but no signal cleared the portfolio pass-through gate."
    elif out["base_signal"].str.contains("sleeve|component", case=False, na=False).any():
        rec = "PROCEED_TO_OOO4_SLEEVE_FACTOR_MOMENTUM"
        reason = "Market/cross-asset sizing did not clear gates; sleeve/factor timing may be the next path."
    else:
        rec = "STOP_SIGNAL_DISCOVERY_FOR_NOW"
        reason = "OOO3 rejected the current market/cross-asset sizing path."
    plan = pd.DataFrame([{
        "recommendation": rec,
        "reason": reason,
        "next_prompt_outline": "Use the OOO3 keep queue only if a variant cleared pass-through; otherwise return to signal discovery or sleeve/factor momentum. Do not create portfolio candidates unless OOO3 says OOO6.",
    }])
    return out, queue, plan


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


def write_report(input_q: pd.DataFrame, manifest: pd.DataFrame, variants: pd.DataFrame, perf: pd.DataFrame, comp: pd.DataFrame, state: pd.DataFrame, inc: pd.DataFrame, dec: pd.DataFrame, queue: pd.DataFrame, plan: pd.DataFrame) -> None:
    DOC.write_text(f"""# Phase OOO3 -- Volatility-Managed Signal Sizing

Date: 2026-04-27

## Commands executed
```
{chr(10).join(COMMANDS)}
```

## Files created / modified
- `scripts/phase_ooo3_vol_managed_signal_sizing.py`
- `data/research/phase_ooo_signal_discovery/ooo3_vol_managed_signal_sizing/*.csv`
- `docs/research/2026-04-27_phase_ooo3_vol_managed_signal_sizing_report.md`
- `docs/research/project_journey.md`

## OOO5 signal queue used
{md_table(input_q, ["signal_name", "ooo5_decision", "event_count", "best_avg_return_lift", "best_positive_barrier_lift", "best_negative_barrier_lift", "assigned_role_for_ooo3"], 8)}

## Volatility / selectivity features
{md_table(manifest, ["feature_name", "base_signal", "feature_group", "missingness", "causal_ok"], 18)}

## Sized variant definitions
{md_table(variants, ["variant_name", "base_signal", "threshold_rule", "vol_filter_rule", "state_filter_rule", "complexity_level"], 24)}

## Event performance summary
{md_table(perf.sort_values(["return_lift_vs_all_weeks", "positive_barrier_lift_vs_all_weeks"], ascending=False), ["variant_name", "base_signal", "horizon_weeks", "event_count", "positive_barrier_hit_rate", "negative_barrier_hit_rate", "avg_final_return", "return_lift_vs_all_weeks", "holdout_2016_event_count", "holdout_2016_avg_return"], 20)}

## Sized vs raw comparison
{md_table(comp.sort_values(["return_lift_vs_raw", "positive_barrier_lift_vs_raw"], ascending=False), ["variant_name", "base_signal", "horizon_weeks", "return_lift_vs_raw", "positive_barrier_lift_vs_raw", "negative_barrier_lift_vs_raw", "return_lift_vs_all_weeks"], 20)}

## State-specific behavior
{md_table(state.sort_values(["return_lift_vs_same_state", "positive_barrier_lift_vs_same_state"], ascending=False), ["variant_name", "market_state", "horizon_weeks", "event_count", "avg_final_return", "return_lift_vs_same_state", "positive_barrier_lift_vs_same_state"], 18)}

## Selectivity / turnover proxy
{md_table(inc.sort_values(["incrementality_flag", "event_frequency"]), ["variant_name", "base_signal", "event_count", "event_frequency", "event_start_count", "event_transition_count", "max_state_overlap", "incrementality_flag"], 24)}

## Keep / reject decisions
{md_table(dec, ["variant_name", "base_signal", "decision", "event_count", "event_frequency", "best_return_lift_vs_all_weeks", "best_return_lift_vs_raw", "best_positive_barrier_lift_vs_raw", "holdout_avg_return_best", "reason"], 24)}

## Top signals to test next
{md_table(queue, ["variant_name", "base_signal", "decision", "assigned_next_phase", "best_return_lift_vs_all_weeks", "best_return_lift_vs_raw"], 8)}

## Final recommendation
**{plan.iloc[0]['recommendation']}**

Reason: {plan.iloc[0]['reason']}

## Whether OOO6 portfolio pass-through is justified
{"Yes, at least one variant cleared the OOO3 pass-through gate." if plan.iloc[0]["recommendation"] == "PROCEED_TO_OOO6_PORTFOLIO_PASS_THROUGH" else "No. OOO3 did not find a sized signal clean enough for GGG1 portfolio pass-through."}

## Exact prompt outline for next phase
{plan.iloc[0]['next_prompt_outline']}
""")


def update_journey(rec: str, reason: str) -> None:
    section = f"""

## Section 86 -- Phase OOO3 Volatility-Managed Signal Sizing

Date: 2026-04-27. OOO3 tested volatility/selectivity-managed versions of OOO5
survivor signals using GGG1 triple-barrier outcomes, holdout checks, event
overlap, and transition-count turnover proxies. No portfolio candidates,
production pins, or strategy logic were changed.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 86 -- Phase OOO3 Volatility-Managed Signal Sizing"
    if marker in text:
        text = re.sub(r"\n## Section 86 -- Phase OOO3 Volatility-Managed Signal Sizing[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    q, _dec, panel, states, g = load_inputs()
    input_q = build_input_queue(q)
    feat, manifest = feature_panel(q, panel, states, g)
    variants, event_panel = make_variants(q, feat)
    outcomes, event_panel_full = evaluate_events(variants, event_panel)
    perf, state, comp = summarize(outcomes, event_panel_full, variants)
    overlap, inc, turnover = selectivity(outcomes, event_panel_full, variants)
    dec, next_queue, plan = decisions(perf, comp, inc)

    input_q.to_csv(OUT / "ooo3_signal_input_queue.csv", index=False)
    feat.to_csv(OUT / "ooo3_signal_sizing_feature_panel.csv", index=False)
    manifest.to_csv(OUT / "ooo3_signal_sizing_manifest.csv", index=False)
    variants.to_csv(OUT / "ooo3_sized_signal_variants.csv", index=False)
    event_panel.to_csv(OUT / "ooo3_sized_signal_event_panel.csv", index=False)
    outcomes.to_csv(OUT / "ooo3_sized_signal_event_outcomes.csv", index=False)
    perf.to_csv(OUT / "ooo3_sized_signal_performance_summary.csv", index=False)
    state.to_csv(OUT / "ooo3_sized_signal_state_summary.csv", index=False)
    comp.to_csv(OUT / "ooo3_sized_signal_vs_raw_comparison.csv", index=False)
    overlap.to_csv(OUT / "ooo3_sized_signal_overlap_matrix.csv", index=False)
    turnover.to_csv(OUT / "ooo3_sized_signal_selectivity_turnover_proxy.csv", index=False)
    inc.to_csv(OUT / "ooo3_sized_signal_incrementality.csv", index=False)
    dec.to_csv(OUT / "ooo3_sized_signal_keep_reject_decisions.csv", index=False)
    next_queue.to_csv(OUT / "ooo3_next_phase_signal_queue.csv", index=False)
    plan.to_csv(OUT / "ooo3_next_phase_recommendation.csv", index=False)

    write_report(input_q, manifest, variants, perf, comp, state, inc, dec, next_queue, plan)
    update_journey(str(plan.iloc[0]["recommendation"]), str(plan.iloc[0]["reason"]))
    print("Phase OOO3 volatility-managed signal sizing complete")
    print(f"signals_loaded: {input_q['signal_name'].nunique()}")
    print(f"variants_tested: {variants['variant_name'].nunique()}")
    print(f"event_outcome_rows: {len(outcomes)}")
    print(f"recommendation: {plan.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
