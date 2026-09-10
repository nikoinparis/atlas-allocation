"""Phase OOO2 — cross-asset signal expansion and validation.

Diagnostic-only. Converts selected OOO1 discoveries into explicit lagged
weekly candidate signals, validates them against forward outcomes, and produces
a keep/reject queue for later OOO phases. No portfolio candidates are created.
"""
from __future__ import annotations

import math
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L0 = ROOT / "data" / "01_data_hub"
L1 = ROOT / "data" / "02_layer1_signals"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
OOO1 = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo1_ml_feature_discovery"
OUT = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo2_cross_asset_signal_expansion"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_ooo2_cross_asset_signal_expansion_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
HORIZONS = [1, 4, 8, 13]
HOLDOUT_START = pd.Timestamp("2016-01-01")
CORE_SLEEVES = {
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    "composite_regime_offense_component",
    "composite_regime_defense_component",
    "taa_10m_sma",
    "cash::BIL",
    "composite_trend_quality_refined",
    "composite_anti_chop_clarity",
}

warnings.filterwarnings("ignore", category=RuntimeWarning)

COMMANDS = [
    "git status --short",
    "sed -n '1,180p' docs/research/2026-04-27_phase_ooo1_ml_feature_discovery_report.md",
    "find data/research/phase_ooo_signal_discovery/ooo1_ml_feature_discovery -maxdepth 1 -type f | sort",
    "find data/02_layer1_signals -maxdepth 1 -type f | sort | sed -n '1,80p'",
    "tail -n 70 docs/research/project_journey.md",
    "python3 scripts/phase_ooo2_cross_asset_signal_expansion.py",
]


def read_indexed(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else "date" if "date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    return df.dropna(subset=[date_col]).set_index(date_col).sort_index()


def read_numeric(path: Path) -> pd.DataFrame:
    return read_indexed(path).apply(pd.to_numeric, errors="coerce")


def trailing_return(s: pd.Series, weeks: int) -> pd.Series:
    return np.expm1(np.log1p(s.fillna(0.0)).rolling(weeks, min_periods=max(3, weeks // 2)).sum())


def forward_return(s: pd.Series, weeks: int) -> pd.Series:
    logs = np.log1p(s.fillna(0.0))
    return np.expm1(logs.shift(-1).rolling(weeks, min_periods=weeks).sum().shift(-(weeks - 1)))


def forward_min_drawdown(s: pd.Series, weeks: int = 4) -> pd.Series:
    vals = s.fillna(0.0).to_numpy()
    out = pd.Series(np.nan, index=s.index)
    for i in range(len(vals) - weeks):
        wealth = np.cumprod(1 + vals[i + 1 : i + weeks + 1])
        out.iloc[i] = float((wealth / np.maximum.accumulate(np.r_[1.0, wealth])[:-1] - 1).min()) if len(wealth) else np.nan
    return out


def spearman(x: pd.Series, y: pd.Series) -> float:
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 20 or df["x"].nunique() < 2 or df["y"].nunique() < 2:
        return np.nan
    return float(df["x"].rank().corr(df["y"].rank()))


def pearson(x: pd.Series, y: pd.Series) -> float:
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(df) < 20 or df["x"].nunique() < 2 or df["y"].nunique() < 2:
        return np.nan
    return float(df["x"].corr(df["y"]))


def simple_t(values: list[float]) -> float:
    arr = np.array([v for v in values if np.isfinite(v)], dtype=float)
    if len(arr) < 3:
        return np.nan
    sd = arr.std(ddof=1)
    return float(arr.mean() / (sd / math.sqrt(len(arr)))) if sd > 1e-12 else np.nan


def sign_hit_rate(x: pd.Series, y: pd.Series) -> float:
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    if len(df) < 20:
        return np.nan
    centered = df["x"] - df["x"].median()
    return float(((centered * df["y"]) > 0).mean())


def quantile_spread(x: pd.Series, y: pd.Series) -> dict:
    df = pd.concat([x.rename("x"), y.rename("y")], axis=1).dropna()
    if len(df) < 40 or df["x"].nunique() < 5:
        return {"top_quantile_return": np.nan, "bottom_quantile_return": np.nan, "top_minus_bottom": np.nan}
    top = df["x"] >= df["x"].quantile(0.80)
    bot = df["x"] <= df["x"].quantile(0.20)
    return {
        "top_quantile_return": float(df.loc[top, "y"].mean()),
        "bottom_quantile_return": float(df.loc[bot, "y"].mean()),
        "top_minus_bottom": float(df.loc[top, "y"].mean() - df.loc[bot, "y"].mean()),
    }


def load_ooo1_scores() -> pd.DataFrame:
    p = OOO1 / "ooo1_candidate_signal_shortlist.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def source_score(shortlist: pd.DataFrame, feature: str) -> tuple[float, str]:
    if shortlist.empty:
        return np.nan, ""
    exact = shortlist[shortlist["feature_formula"].eq(feature)]
    if exact.empty and feature.endswith("_signal"):
        exact = shortlist[shortlist["feature_formula"].eq(feature.replace("_signal", ""))]
    if exact.empty:
        return np.nan, ""
    row = exact.iloc[0]
    return float(row.get("discovery_score", np.nan)), str(row.get("signal_category", ""))


def build_designs(shortlist: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("leadlag_EFA_minus_SPY_13w_signal", "leadlag_EFA_minus_SPY_13w", "13-week EFA return minus 13-week SPY return, lagged 1 week", "international equity leadership / risk regime signal", "MARKET", "risk confirmation", "neutral_mixed|recovery_confirmed|calm_trend"),
        ("leadlag_GLD_minus_SPY_13w_signal", "leadlag_GLD_minus_SPY_13w", "13-week GLD return minus 13-week SPY return, lagged 1 week", "defensive / real-asset leadership signal", "MARKET", "risk confirmation", "stressed_panic|neutral_mixed"),
        ("leadlag_DBA_minus_SPY_13w_signal", "leadlag_DBA_minus_SPY_13w", "13-week DBA return minus 13-week SPY return, lagged 1 week", "commodity / inflation-sensitive leadership signal", "MARKET", "risk confirmation", "neutral_mixed|calm_trend"),
        ("leadlag_HYG_minus_LQD_13w_signal", "leadlag_HYG_minus_LQD_13w", "13-week HYG return minus 13-week LQD return, lagged 1 week", "credit risk appetite confirmation", "MARKET", "risk confirmation", "calm_trend|recovery_confirmed"),
        ("breadth_ret13_positive_signal", "breadth_ret13_positive", "share of ETF universe with positive 13-week return, lagged 1 week", "broad market participation", "MARKET", "gate", "all"),
        ("breadth_ret26_positive_signal", "breadth_ret26_positive", "share of ETF universe with positive 26-week return, lagged 1 week", "slower broad market participation", "MARKET", "gate", "all"),
        ("canary_breadth_pair_signal", "regime_canary_breadth_pair", "existing canary breadth pair field, lagged 1 week", "risk-on/risk-off confirmation", "MARKET", "risk confirmation", "all"),
        ("recent_stress_26w_signal", "regime_recent_stress_26w", "existing recent-stress memory field, lagged 1 week", "stress memory / risk regime", "MARKET", "risk confirmation", "stressed_panic|recovery_fragile"),
        ("market_drawdown_signal", "regime_market_drawdown", "existing market drawdown field, lagged 1 week", "drawdown-state risk confirmation", "MARKET", "risk confirmation", "stressed_panic|recovery_fragile"),
        ("market_trend_positive_signal", "regime_market_trend_positive", "existing market trend positive flag, lagged 1 week", "trend confirmation", "MARKET", "gate", "calm_trend|neutral_mixed"),
        ("breadth_ret13_positive_x_recovery_confirmed_signal", "breadth_ret13_positive_x_state_recovery_confirmed", "lagged 13-week breadth times lagged recovery_confirmed state flag", "state-specific breadth participation gate", "MARKET", "state quality", "recovery_confirmed"),
        ("breadth_ret13_positive_x_neutral_mixed_signal", "breadth_ret13_positive_x_state_neutral_mixed", "lagged 13-week breadth times lagged neutral_mixed state flag", "state-specific breadth participation gate", "MARKET", "state quality", "neutral_mixed"),
        ("breadth_ret13_positive_x_stressed_panic_signal", "breadth_ret13_positive_x_state_stressed_panic", "lagged 13-week breadth times lagged stressed_panic state flag", "state-specific breadth recovery/risk gate", "MARKET", "state quality", "stressed_panic"),
        ("leadlag_HYG_minus_LQD_13w_x_calm_trend_signal", "leadlag_HYG_minus_LQD_13w_x_state_calm_trend", "lagged HYG-LQD 13-week return spread times lagged calm_trend flag", "credit confirmation inside calm trend", "MARKET", "state quality", "calm_trend"),
    ]
    rows = []
    for signal_name, source, formula, interp, entity, use, states in specs:
        score, cat = source_score(shortlist, source)
        rows.append({
            "signal_name": signal_name,
            "source_feature": source,
            "formula": formula,
            "economic_interpretation": interp,
            "intended_entity_type": entity,
            "expected_use": use,
            "states_where_it_may_matter": states,
            "lag_rule": "signal value is shifted by 1 week before validation",
            "source_ooo1_discovery_score": score,
            "redundancy_warning": cat,
        })
    return pd.DataFrame(rows)


def construct_signals(designs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    returns = read_numeric(L0 / "weekly_returns.csv")
    state = read_indexed(L2B / "market_state_history.csv")
    idx = state.index.union(returns.index).sort_values()
    returns = returns.reindex(idx)
    state = state.reindex(idx)
    signal = pd.DataFrame(index=idx)
    missing = []

    def req(cols: list[str], name: str) -> bool:
        have = all(c in returns.columns for c in cols)
        if not have:
            missing.append({"signal_name": name, "missing_source": "|".join([c for c in cols if c not in returns.columns]), "action": "signal skipped"})
        return have

    if req(["EFA", "SPY"], "leadlag_EFA_minus_SPY_13w_signal"):
        signal["leadlag_EFA_minus_SPY_13w_signal"] = (trailing_return(returns["EFA"], 13) - trailing_return(returns["SPY"], 13)).shift(1)
    if req(["GLD", "SPY"], "leadlag_GLD_minus_SPY_13w_signal"):
        signal["leadlag_GLD_minus_SPY_13w_signal"] = (trailing_return(returns["GLD"], 13) - trailing_return(returns["SPY"], 13)).shift(1)
    if req(["DBA", "SPY"], "leadlag_DBA_minus_SPY_13w_signal"):
        signal["leadlag_DBA_minus_SPY_13w_signal"] = (trailing_return(returns["DBA"], 13) - trailing_return(returns["SPY"], 13)).shift(1)
    if req(["HYG", "LQD"], "leadlag_HYG_minus_LQD_13w_signal"):
        signal["leadlag_HYG_minus_LQD_13w_signal"] = (trailing_return(returns["HYG"], 13) - trailing_return(returns["LQD"], 13)).shift(1)

    ret13 = returns.apply(lambda s: trailing_return(s, 13))
    ret26 = returns.apply(lambda s: trailing_return(s, 26))
    signal["breadth_ret13_positive_signal"] = (ret13 > 0).mean(axis=1).shift(1)
    signal["breadth_ret26_positive_signal"] = (ret26 > 0).mean(axis=1).shift(1)
    for col, out in [
        ("canary_breadth_pair", "canary_breadth_pair_signal"),
        ("recent_stress_26w", "recent_stress_26w_signal"),
        ("market_drawdown", "market_drawdown_signal"),
        ("market_trend_positive", "market_trend_positive_signal"),
    ]:
        if col in state.columns:
            signal[out] = pd.to_numeric(state[col], errors="coerce").shift(1)
        else:
            missing.append({"signal_name": out, "missing_source": col, "action": "signal skipped"})

    lag_state = state["market_state"].astype(str).shift(1) if "market_state" in state.columns else pd.Series(index=idx, dtype=object)
    signal["breadth_ret13_positive_x_recovery_confirmed_signal"] = signal["breadth_ret13_positive_signal"] * lag_state.eq("recovery_confirmed").astype(float)
    signal["breadth_ret13_positive_x_neutral_mixed_signal"] = signal["breadth_ret13_positive_signal"] * lag_state.eq("neutral_mixed").astype(float)
    signal["breadth_ret13_positive_x_stressed_panic_signal"] = signal["breadth_ret13_positive_signal"] * lag_state.eq("stressed_panic").astype(float)
    if "leadlag_HYG_minus_LQD_13w_signal" in signal.columns:
        signal["leadlag_HYG_minus_LQD_13w_x_calm_trend_signal"] = signal["leadlag_HYG_minus_LQD_13w_signal"] * lag_state.eq("calm_trend").astype(float)

    keep = [c for c in designs["signal_name"] if c in signal.columns]
    signal = signal[keep].copy()
    panel = signal.reset_index(names="date")
    manifest_rows = []
    for _, row in designs.iterrows():
        name = row["signal_name"]
        if name not in signal.columns:
            continue
        s = signal[name]
        manifest_rows.append({
            "signal_name": name,
            "formula": row["formula"],
            "source_columns": row["source_feature"],
            "lag_rule": row["lag_rule"],
            "frequency": "weekly",
            "start_date": str(s.dropna().index.min().date()) if s.notna().any() else None,
            "end_date": str(s.dropna().index.max().date()) if s.notna().any() else None,
            "missingness": float(s.isna().mean()),
            "causal_ok": True,
            "economic_interpretation": row["economic_interpretation"],
            "OOO1_source_feature": row["source_feature"],
            "next_validation_stage": "OOO2 validation",
        })
    missing_df = pd.DataFrame(missing, columns=["signal_name", "missing_source", "action"])
    return panel, pd.DataFrame(manifest_rows), missing_df


def etf_forward_returns(index: pd.DatetimeIndex) -> dict[int, pd.DataFrame]:
    returns = read_numeric(L0 / "weekly_returns.csv").reindex(index)
    cols = [c for c in returns.columns if returns[c].notna().sum() > 150]
    returns = returns[cols]
    return {h: returns.apply(lambda s: forward_return(s, h)) for h in HORIZONS}


def sleeve_forward_returns(index: pd.DatetimeIndex) -> dict[int, pd.DataFrame]:
    frames = []
    for path in sorted(L2A.glob("strategy_returns_*.csv")):
        name = path.stem.replace("strategy_returns_", "")
        if name not in CORE_SLEEVES:
            continue
        try:
            frames.append(read_numeric(path).iloc[:, 0].reindex(index).rename(name))
        except Exception:
            continue
    sleeve = pd.concat(frames, axis=1) if frames else pd.DataFrame(index=index)
    return {h: sleeve.apply(lambda s: forward_return(s, h)) for h in HORIZONS}


def market_targets(index: pd.DatetimeIndex) -> pd.DataFrame:
    g = read_numeric(L3 / f"portfolio_version_returns_{GGG1}.csv")["net_return"].reindex(index)
    prod = read_numeric(L3 / f"portfolio_version_returns_{PRODUCTION}.csv")["net_return"].reindex(index)
    vol = g.rolling(26, min_periods=13).std(ddof=0).shift(1)
    out = pd.DataFrame(index=index)
    for h in HORIZONS:
        fwd = forward_return(g, h)
        out[f"fwd_ggg1_return_{h}w"] = fwd
        out[f"fwd_ggg1_risk_adj_{h}w"] = fwd / (vol * math.sqrt(h)).replace(0, np.nan)
        out[f"fwd_prod_return_{h}w"] = forward_return(prod, h)
    state = read_indexed(L2B / "market_state_history.csv").reindex(index)
    stress = state["market_state"].astype(str).eq("stressed_panic").astype(float)
    out["fwd_stress_transition_4w"] = stress.shift(-1).rolling(4, min_periods=4).max().shift(-3)
    out["fwd_drawdown_worsening_4w"] = (forward_min_drawdown(g, 4) <= -0.025).astype(float)
    out["state_quality_good_4w"] = (out["fwd_ggg1_risk_adj_4w"] >= out["fwd_ggg1_risk_adj_4w"].median()).astype(float)
    return out


def validate_signals(signal_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    signal = signal_panel.set_index("date").sort_index()
    signal.index = pd.to_datetime(signal.index)
    state = read_indexed(L2B / "market_state_history.csv").reindex(signal.index)["market_state"].astype(str)
    etf_fwd = etf_forward_returns(signal.index)
    sleeve_fwd = sleeve_forward_returns(signal.index)
    mt = market_targets(signal.index)
    summary_rows, ic_rows, state_rows, spread_rows, hit_rows = [], [], [], [], []

    def entity_ic_rows(target_group: str, fwd_map: dict[int, pd.DataFrame]) -> None:
        for sig in signal.columns:
            x = signal[sig]
            for h, fwd in fwd_map.items():
                ics, pears, spreads, hits = [], [], [], []
                holdout_ics = []
                for entity in fwd.columns:
                    y = fwd[entity]
                    ic = spearman(x, y)
                    pr = pearson(x, y)
                    if np.isfinite(ic):
                        ics.append(ic)
                    if np.isfinite(pr):
                        pears.append(pr)
                    if entity in fwd.columns:
                        spreads.append(quantile_spread(x, y)["top_minus_bottom"])
                        hits.append(sign_hit_rate(x, y))
                    hi = spearman(x.loc[x.index >= HOLDOUT_START], y.loc[y.index >= HOLDOUT_START])
                    if np.isfinite(hi):
                        holdout_ics.append(hi)
                row = {
                    "signal_name": sig,
                    "target_group": target_group,
                    "horizon_weeks": h,
                    "mean_ic": float(np.nanmean(ics)) if ics else np.nan,
                    "median_ic": float(np.nanmedian(ics)) if ics else np.nan,
                    "mean_pearson": float(np.nanmean(pears)) if pears else np.nan,
                    "ic_tstat_simple": simple_t(ics),
                    "holdout_mean_ic_2016_forward": float(np.nanmean(holdout_ics)) if holdout_ics else np.nan,
                    "positive_entity_share": float(np.mean(np.array(ics) > 0)) if ics else np.nan,
                    "n_entities": len(ics),
                    "t_stat_method": "simple t-stat across entity time-series ICs; NW not applicable to scalar date-level signals",
                }
                summary_rows.append(row)
                ic_rows.append(row.copy())
                spread_rows.append({
                    "signal_name": sig,
                    "target_group": target_group,
                    "horizon_weeks": h,
                    "mean_top_minus_bottom_spread": float(np.nanmean(spreads)) if spreads else np.nan,
                    "mean_directional_hit_rate": float(np.nanmean(hits)) if hits else np.nan,
                })
                hit_rows.append({
                    "signal_name": sig,
                    "target_group": target_group,
                    "horizon_weeks": h,
                    "hit_rate": float(np.nanmean(hits)) if hits else np.nan,
                    "positive_entity_share": row["positive_entity_share"],
                })
                for st, idx in state.groupby(state).groups.items():
                    sub_ics = []
                    idx = list(idx)
                    for entity in fwd.columns:
                        ic = spearman(x.loc[idx], fwd[entity].loc[idx])
                        if np.isfinite(ic):
                            sub_ics.append(ic)
                    state_rows.append({
                        "signal_name": sig,
                        "target_group": target_group,
                        "market_state": st,
                        "horizon_weeks": h,
                        "mean_ic": float(np.nanmean(sub_ics)) if sub_ics else np.nan,
                        "ic_tstat_simple": simple_t(sub_ics),
                        "n_entities": len(sub_ics),
                    })

    entity_ic_rows("ETF_forward_returns", etf_fwd)
    entity_ic_rows("SLEEVE_forward_returns", sleeve_fwd)

    for sig in signal.columns:
        x = signal[sig]
        for target in mt.columns:
            y = mt[target]
            h = int(re.search(r"_(\d+)w", target).group(1)) if re.search(r"_(\d+)w", target) else 4
            ic = spearman(x, y)
            pr = pearson(x, y)
            hold = spearman(x.loc[x.index >= HOLDOUT_START], y.loc[y.index >= HOLDOUT_START])
            spread = quantile_spread(x, y)
            row = {
                "signal_name": sig,
                "target_group": "MARKET",
                "target": target,
                "horizon_weeks": h,
                "mean_ic": ic,
                "median_ic": ic,
                "mean_pearson": pr,
                "ic_tstat_simple": np.nan,
                "holdout_mean_ic_2016_forward": hold,
                "positive_entity_share": np.nan,
                "n_entities": 1,
                "t_stat_method": "time-series Spearman/Pearson; no fitted model",
            }
            summary_rows.append(row)
            if target in [f"fwd_ggg1_return_{h}w", f"fwd_ggg1_risk_adj_{h}w"]:
                ic_rows.append(row.copy())
            spread_rows.append({"signal_name": sig, "target_group": "MARKET", "target": target, "horizon_weeks": h, **spread})
            hit_rows.append({"signal_name": sig, "target_group": "MARKET", "target": target, "horizon_weeks": h, "hit_rate": sign_hit_rate(x, y), "positive_entity_share": np.nan})
            for st, idx in state.groupby(state).groups.items():
                state_rows.append({
                    "signal_name": sig,
                    "target_group": "MARKET",
                    "target": target,
                    "market_state": st,
                    "horizon_weeks": h,
                    "mean_ic": spearman(x.loc[list(idx)], y.loc[list(idx)]),
                    "ic_tstat_simple": np.nan,
                    "n_entities": 1,
                })
    return pd.DataFrame(summary_rows), pd.DataFrame(ic_rows), pd.DataFrame(state_rows), pd.DataFrame(spread_rows), pd.DataFrame(hit_rows)


def redundancy(signal_panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    sig = signal_panel.set_index("date").apply(pd.to_numeric, errors="coerce")
    matrix = sig.corr(method="spearman")
    feature_panel_path = OOO1 / "ooo1_feature_panel.csv"
    existing_corr = {}
    if feature_panel_path.exists():
        usecols = ["date"] + [c for c in pd.read_csv(feature_panel_path, nrows=1).columns if c.startswith("l1_")]
        if len(usecols) > 1:
            l1 = pd.read_csv(feature_panel_path, usecols=usecols)
            l1["date"] = pd.to_datetime(l1["date"], errors="coerce")
            l1_agg = l1.groupby("date").mean(numeric_only=True)
            for col in sig.columns:
                vals = l1_agg.corrwith(sig[col], method="spearman").abs().dropna()
                existing_corr[col] = {
                    "avg_abs_corr_existing_layer1": float(vals.mean()) if not vals.empty else np.nan,
                    "max_abs_corr_existing_layer1": float(vals.max()) if not vals.empty else np.nan,
                }
    rows = []
    for col in matrix.columns:
        others = matrix[col].drop(labels=[col], errors="ignore").abs().dropna()
        rows.append({
            "signal_name": col,
            "avg_abs_redundancy_ooo2": float(others.mean()) if not others.empty else np.nan,
            "max_abs_redundancy_ooo2": float(others.max()) if not others.empty else np.nan,
            "cluster_label": "HIGH_REDUNDANCY_CLUSTER" if (not others.empty and others.max() >= 0.85) else "LOW_TO_MODERATE_REDUNDANCY",
            **existing_corr.get(col, {"avg_abs_corr_existing_layer1": np.nan, "max_abs_corr_existing_layer1": np.nan}),
        })
    return matrix.reset_index(names="signal_name"), pd.DataFrame(rows)


def score_and_decide(designs: pd.DataFrame, manifest: pd.DataFrame, summary: pd.DataFrame, state_ic: pd.DataFrame, red: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    design_scores = designs[["signal_name", "source_ooo1_discovery_score", "expected_use", "states_where_it_may_matter"]].copy()
    core = summary[summary["target_group"].isin(["ETF_forward_returns", "MARKET"])].copy()
    strength = core.groupby("signal_name", as_index=False).agg(
        best_abs_ic=("mean_ic", lambda s: float(np.nanmax(np.abs(s))) if s.notna().any() else np.nan),
        best_holdout_abs_ic=("holdout_mean_ic_2016_forward", lambda s: float(np.nanmax(np.abs(s))) if s.notna().any() else np.nan),
        best_spread=("mean_ic", lambda s: float(np.nanmax(s)) if s.notna().any() else np.nan),
    )
    state_strength = state_ic.groupby("signal_name", as_index=False).agg(
        best_state_abs_ic=("mean_ic", lambda s: float(np.nanmax(np.abs(s))) if s.notna().any() else np.nan),
        positive_state_count=("mean_ic", lambda s: int((s > 0.03).sum())),
    )
    out = design_scores.merge(strength, on="signal_name", how="left").merge(state_strength, on="signal_name", how="left").merge(red, on="signal_name", how="left").merge(manifest[["signal_name", "missingness", "causal_ok"]], on="signal_name", how="left")
    out["coverage_score"] = 1.0 - out["missingness"].fillna(1.0)
    out["redundancy_penalty"] = out[["avg_abs_redundancy_ooo2", "avg_abs_corr_existing_layer1"]].max(axis=1).fillna(0)
    out["incremental_signal_score"] = (
        out["best_abs_ic"].fillna(0).rank(pct=True)
        + out["best_holdout_abs_ic"].fillna(0).rank(pct=True)
        + out["best_state_abs_ic"].fillna(0).rank(pct=True)
        + out["source_ooo1_discovery_score"].fillna(0).rank(pct=True)
        + out["coverage_score"].rank(pct=True)
        - out["redundancy_penalty"].rank(pct=True) * 0.5
    )
    decisions = []
    for _, r in out.iterrows():
        strong = (r.get("best_abs_ic", 0) >= 0.04 or r.get("best_holdout_abs_ic", 0) >= 0.04 or r.get("best_state_abs_ic", 0) >= 0.06)
        sufficient = r.get("coverage_score", 0) >= 0.75 and bool(r.get("causal_ok", False))
        redundant = r.get("redundancy_penalty", 0) >= 0.85
        is_state = "_x_" in r["signal_name"] or "state" in str(r.get("expected_use"))
        if not sufficient:
            dec = "REJECT"
        elif redundant and not strong:
            dec = "REDUNDANT_WITH_EXISTING"
        elif is_state and strong:
            dec = "KEEP_STATE_SPECIFIC"
        elif strong and not redundant and r.get("incremental_signal_score", 0) >= out["incremental_signal_score"].median():
            dec = "KEEP_HIGH_PRIORITY"
        elif strong:
            dec = "KEEP_FOR_TRIPLE_BARRIER_VALIDATION"
        elif r.get("best_abs_ic", 0) >= 0.025:
            dec = "PROMISING_BUT_NEEDS_VOL_MANAGEMENT"
        else:
            dec = "WEAK_OR_UNSTABLE"
        decisions.append(dec)
    out["decision"] = decisions
    queue = out[out["decision"].str.startswith("KEEP") | out["decision"].eq("PROMISING_BUT_NEEDS_VOL_MANAGEMENT")].copy()
    def phase(row: pd.Series) -> str:
        if row["decision"] == "PROMISING_BUT_NEEDS_VOL_MANAGEMENT":
            return "OOO3 volatility-managed signal sizing"
        if row["decision"] in ["KEEP_STATE_SPECIFIC", "KEEP_FOR_TRIPLE_BARRIER_VALIDATION"]:
            return "OOO5 triple-barrier/meta-label validation"
        return "OOO6 GGG1 portfolio pass-through after OOO3/OOO5"
    if not queue.empty:
        queue["assigned_next_phase"] = queue.apply(phase, axis=1)
        queue = queue.sort_values("incremental_signal_score", ascending=False)
    if queue.empty:
        next_rec = "NEEDS_MORE_SIGNAL_DISCOVERY"
    elif queue["decision"].isin(["KEEP_STATE_SPECIFIC", "KEEP_FOR_TRIPLE_BARRIER_VALIDATION"]).any():
        next_rec = "PROCEED_TO_OOO5_TRIPLE_BARRIER_VALIDATION"
    elif queue["decision"].eq("PROMISING_BUT_NEEDS_VOL_MANAGEMENT").any():
        next_rec = "PROCEED_TO_OOO3_VOL_MANAGED_SIGNAL_SIZING"
    else:
        next_rec = "PROCEED_TO_OOO5_TRIPLE_BARRIER_VALIDATION"
    next_plan = pd.DataFrame([{
        "recommendation": next_rec,
        "reason": "OOO2 produced surviving explicit signals with validation evidence." if not queue.empty else "OOO2 did not produce enough surviving explicit signals.",
        "next_prompt_outline": "Use the OOO2 signal queue to run triple-barrier/meta-label validation and/or volatility-managed sizing before any GGG1 portfolio pass-through.",
    }])
    return out.sort_values("incremental_signal_score", ascending=False), queue, next_plan


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


def write_report(designs: pd.DataFrame, manifest: pd.DataFrame, missing: pd.DataFrame, summary: pd.DataFrame, ic: pd.DataFrame, state: pd.DataFrame, red: pd.DataFrame, decisions: pd.DataFrame, queue: pd.DataFrame, next_plan: pd.DataFrame) -> None:
    top_valid = summary.sort_values("mean_ic", key=lambda s: s.abs(), ascending=False)
    DOC.write_text(f"""# Phase OOO2 — Cross-Asset Signal Expansion and Validation

Date: 2026-04-27

## Commands executed
```
{chr(10).join(COMMANDS)}
```

## Files created / modified
- `scripts/phase_ooo2_cross_asset_signal_expansion.py`
- `data/research/phase_ooo_signal_discovery/ooo2_cross_asset_signal_expansion/*.csv`
- `docs/research/2026-04-27_phase_ooo2_cross_asset_signal_expansion_report.md`
- `docs/research/project_journey.md`

## OOO1 shortlist used
OOO2 started from OOO1's cross-asset lead-lag, breadth/state-interaction, and
regime-risk shortlist. Portfolio candidates were not created.

## Candidate signal designs
{md_table(designs, ["signal_name", "source_feature", "expected_use", "states_where_it_may_matter", "source_ooo1_discovery_score"], 14)}

## Signal construction summary
{md_table(manifest, ["signal_name", "start_date", "end_date", "missingness", "causal_ok", "next_validation_stage"], 14)}

## Missing signal sources
{md_table(missing)}

## IC / validation summary
{md_table(top_valid, ["signal_name", "target_group", "target", "horizon_weeks", "mean_ic", "holdout_mean_ic_2016_forward", "n_entities", "t_stat_method"], 18)}

## IC decay by horizon
{md_table(ic[ic["target_group"].eq("ETF_forward_returns")].sort_values(["signal_name", "horizon_weeks"]), ["signal_name", "horizon_weeks", "mean_ic", "holdout_mean_ic_2016_forward", "positive_entity_share"], 20)}

## State-specific behavior
{md_table(state.sort_values("mean_ic", key=lambda s: s.abs(), ascending=False), ["signal_name", "target_group", "market_state", "horizon_weeks", "mean_ic", "n_entities"], 18)}

## Redundancy / incrementality
{md_table(red, ["signal_name", "avg_abs_redundancy_ooo2", "max_abs_redundancy_ooo2", "avg_abs_corr_existing_layer1", "max_abs_corr_existing_layer1", "cluster_label"], 14)}

## Keep / reject decisions
{md_table(decisions, ["signal_name", "decision", "incremental_signal_score", "best_abs_ic", "best_holdout_abs_ic", "best_state_abs_ic", "redundancy_penalty"], 14)}

## Top 5 signals to test next
{md_table(queue, ["signal_name", "decision", "assigned_next_phase", "incremental_signal_score"], 5)}

## How OOO2 feeds OOO3, OOO5, and OOO6
OOO2 only validates explicit signals. Surviving state-specific/risk signals
should go to OOO5 triple-barrier/meta-label validation before portfolio
pass-through. Signals that need sizing polish should go to OOO3. Only after
OOO3/OOO5 should any signal enter OOO6 GGG1 pass-through.

## Final recommendation
**{next_plan.iloc[0]['recommendation']}**

Reason: {next_plan.iloc[0]['reason']}

## Exact prompt outline for next phase
{next_plan.iloc[0]['next_prompt_outline']}
""")


def update_journey(rec: str, reason: str) -> None:
    section = f"""

## Section 84 — Phase OOO2 Cross-Asset Signal Expansion

Date: 2026-04-27. OOO2 converted the strongest OOO1 discoveries into explicit
lagged weekly candidate Layer 1 signals and validated them with IC decay,
state behavior, redundancy, and keep/reject screens. No portfolio candidates,
production pins, or strategy logic were changed.

**Decision.** `{rec}`.

**Reason.** {reason}
"""
    text = JOURNEY.read_text()
    marker = "## Section 84 — Phase OOO2 Cross-Asset Signal Expansion"
    if marker in text:
        text = re.sub(r"\n## Section 84 — Phase OOO2 Cross-Asset Signal Expansion[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    shortlist = load_ooo1_scores()
    designs = build_designs(shortlist)
    panel, manifest, missing = construct_signals(designs)
    summary, ic, state_ic, spread, hit = validate_signals(panel)
    matrix, red_summary = redundancy(panel)
    decisions, queue, next_plan = score_and_decide(designs, manifest, summary, state_ic, red_summary)

    designs.to_csv(OUT / "ooo2_candidate_signal_designs.csv", index=False)
    panel.to_csv(OUT / "ooo2_candidate_signal_panel.csv", index=False)
    manifest.to_csv(OUT / "ooo2_signal_manifest.csv", index=False)
    missing.to_csv(OUT / "ooo2_missing_signal_sources.csv", index=False)
    summary.to_csv(OUT / "ooo2_signal_validation_summary.csv", index=False)
    ic.to_csv(OUT / "ooo2_signal_ic_by_horizon.csv", index=False)
    state_ic.to_csv(OUT / "ooo2_signal_ic_by_state.csv", index=False)
    spread.to_csv(OUT / "ooo2_signal_return_spread_by_quantile.csv", index=False)
    hit.to_csv(OUT / "ooo2_signal_hit_rate_summary.csv", index=False)
    matrix.to_csv(OUT / "ooo2_signal_redundancy_matrix.csv", index=False)
    red_summary.to_csv(OUT / "ooo2_signal_redundancy_summary.csv", index=False)
    decisions.to_csv(OUT / "ooo2_incremental_signal_score.csv", index=False)
    decisions.to_csv(OUT / "ooo2_signal_keep_reject_decisions.csv", index=False)
    queue.to_csv(OUT / "ooo2_next_phase_signal_queue.csv", index=False)
    next_plan.to_csv(OUT / "ooo2_next_phase_recommendation.csv", index=False)

    write_report(designs, manifest, missing, summary, ic, state_ic, red_summary, decisions, queue, next_plan)
    update_journey(str(next_plan.iloc[0]["recommendation"]), str(next_plan.iloc[0]["reason"]))

    print("Phase OOO2 cross-asset signal expansion complete")
    print(f"signals_constructed: {len(manifest)}")
    print(f"validation_rows: {len(summary)}")
    print(f"surviving_queue_rows: {len(queue)}")
    print(f"recommendation: {next_plan.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
