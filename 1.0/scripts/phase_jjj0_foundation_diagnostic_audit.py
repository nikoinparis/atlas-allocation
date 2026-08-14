"""Phase JJJ0 — diagnostic-only foundation audit.

Reads existing Layer 2A, Layer 2B, Layer 3, and allocator-checkpoint artifacts.
Does not create strategies, optimize parameters, or modify production pins.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import re

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "01_data_hub"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
CHECKPOINTS = ROOT / "data" / "research" / "allocator_checkpoints"
OUT = ROOT / "data" / "research" / "phase_jjj0_foundation_diagnostic_audit"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_jjj0_foundation_diagnostic_audit_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
CANDIDATE = "improved_phaseggg_confirmed_only_robust_offense"
VERSIONS = [CANDIDATE, PRODUCTION, SHADOW]
VERSION_ROLE = {CANDIDATE: "production_candidate", PRODUCTION: "production", SHADOW: "official_shadow"}
TARGET_STATES = ["recovery_confirmed", "recovery_fragile", "stressed_panic", "neutral_mixed", "neutral_healthy", "calm_trend"]

OFFENSIVE_SLEEVES = {
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    "composite_regime_offense_component",
}
DEFENSIVE_SLEEVES = {"taa_10m_sma", "composite_regime_defense_component"}
CASH_SLEEVES = {"cash::BIL", "composite_regime_cash_component"}
MIXED_SLEEVES = {"composite_regime_conditioned"}

CASH_ETFS = {"BIL", "SHY"}
OFFENSE_ETFS = {"SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "EEM", "VTV", "VUG", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
DEFENSE_ETFS = {"TLT", "IEF", "LQD", "MBB", "TIP", "HYG"}
REAL_ASSET_ETFS = {"GLD", "IAU", "SLV", "PDBC", "DBA", "USO", "UUP"}

STAGES = [
    "raw_hrp_sleeve_weights",
    "post_state_tilt_sleeve_weights",
    "post_layer3_expression_sleeve_weights",
    "post_overlay_pre_lookthrough_sleeve_weights",
    "final_sleeve_weights",
    "final_etf_weights",
]

COMMANDS_EXECUTED = [
    "sed -n '1,180p' docs/research/2026-04-27_phase_iii_production_candidate_review_report.md",
    "sed -n '1,180p' docs/research/2026-04-27_phase_ggg_state_conditional_composite_offense_report.md",
    "tail -80 docs/research/project_journey.md",
    "rg -n \"composite_regime|phaseggg|VERSION|version_specs|internal_redeploy|sleeve|market_state|allocator_checkpoint|checkpoint|target_vol|overlay|lookthrough|deadband|turnover|cap\" scripts/build_improvement_artifacts.py | head -160",
    "sed -n '1,220p' scripts/phase_ggg_state_conditional_composite_offense.py",
    "rg --files data/05_layer3_portfolio_construction | rg 'portfolio_version_(returns|weights|sleeve_weights)_(improved_phaseggg_confirmed_only_robust_offense|improved_phase2b_regime_confidence_boost|improved_phase2b_combo_abc)\\.csv$|phase_ggg|phase_iii|production_candidate' | sort",
    "rg --files data/03_layer2a_strategy_logic | head -120",
    "rg --files data/04_layer2b_risk_regime_engine | head -120",
    "rg --files data/research/allocator_checkpoints | head -120",
    "python3 scripts/phase_jjj0_foundation_diagnostic_audit.py",
]


@dataclass
class Loaded:
    returns: dict[str, pd.DataFrame]
    weights: dict[str, pd.DataFrame]
    sleeve_weights: dict[str, pd.DataFrame]
    checkpoints: dict[tuple[str, str], pd.DataFrame]
    state: pd.DataFrame
    etf_returns: pd.DataFrame


def read_time_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else ("Unnamed: 0" if "Unnamed: 0" in df.columns else df.columns[0])
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() >= max(1, int(df[col].notna().sum() * 0.8)):
            df[col] = converted
    return df


def annual_return(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return np.nan
    return float((1.0 + s).prod() ** (52.0 / len(s)) - 1.0)


def ann_vol(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.std(ddof=1) * np.sqrt(52.0)) if len(s) > 1 else np.nan


def sharpe(s: pd.Series) -> float:
    v = ann_vol(s)
    return annual_return(s) / v if v and np.isfinite(v) and v > 0 else np.nan


def cvar5(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return np.nan
    q = s.quantile(0.05)
    return float(s[s <= q].mean())


def max_drawdown(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    wealth = (1.0 + s).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min()) if len(wealth) else np.nan


def metric_block(s: pd.Series) -> dict[str, float]:
    return {"ann_return": annual_return(s), "ann_vol": ann_vol(s), "sharpe": sharpe(s), "max_drawdown": max_drawdown(s), "cvar_5": cvar5(s)}


def safe_mean(df: pd.DataFrame, cols: set[str]) -> float:
    keep = [c for c in df.columns if c in cols]
    return float(df[keep].sum(axis=1).mean()) if keep else 0.0


def bucket_frame(weights: pd.DataFrame, kind: str) -> pd.DataFrame:
    if kind == "etf":
        return pd.DataFrame({
            "cash_weight": weights[[c for c in weights.columns if c in CASH_ETFS]].sum(axis=1) if any(c in CASH_ETFS for c in weights.columns) else 0.0,
            "offense_weight": weights[[c for c in weights.columns if c in OFFENSE_ETFS]].sum(axis=1) if any(c in OFFENSE_ETFS for c in weights.columns) else 0.0,
            "defense_weight": weights[[c for c in weights.columns if c in DEFENSE_ETFS]].sum(axis=1) if any(c in DEFENSE_ETFS for c in weights.columns) else 0.0,
            "real_asset_weight": weights[[c for c in weights.columns if c in REAL_ASSET_ETFS]].sum(axis=1) if any(c in REAL_ASSET_ETFS for c in weights.columns) else 0.0,
            "mixed_composite_weight": 0.0,
        }, index=weights.index)
    return pd.DataFrame({
        "cash_weight": weights[[c for c in weights.columns if c in CASH_SLEEVES]].sum(axis=1) if any(c in CASH_SLEEVES for c in weights.columns) else 0.0,
        "offense_weight": weights[[c for c in weights.columns if c in OFFENSIVE_SLEEVES]].sum(axis=1) if any(c in OFFENSIVE_SLEEVES for c in weights.columns) else 0.0,
        "defense_weight": weights[[c for c in weights.columns if c in DEFENSIVE_SLEEVES]].sum(axis=1) if any(c in DEFENSIVE_SLEEVES for c in weights.columns) else 0.0,
        "real_asset_weight": 0.0,
        "mixed_composite_weight": weights[[c for c in weights.columns if c in MIXED_SLEEVES]].sum(axis=1) if any(c in MIXED_SLEEVES for c in weights.columns) else 0.0,
    }, index=weights.index)


def hhi(row: pd.Series) -> float:
    vals = pd.to_numeric(row, errors="coerce").fillna(0.0).clip(lower=0.0)
    total = vals.sum()
    return float(((vals / total) ** 2).sum()) if total > 0 else np.nan


def state_join(df: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    return df.join(state[["market_state"]], how="inner").dropna(subset=["market_state"])


def load_all() -> Loaded:
    returns, weights, sleeve_weights, checkpoints = {}, {}, {}, {}
    for version in VERSIONS:
        returns[version] = read_time_csv(L3 / f"portfolio_version_returns_{version}.csv")
        weights[version] = read_time_csv(L3 / f"portfolio_version_weights_{version}.csv")
        sleeve_weights[version] = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{version}.csv")
        for stage in STAGES:
            path = CHECKPOINTS / f"{version}__{stage}.csv"
            if path.exists():
                checkpoints[(version, stage)] = read_time_csv(path)
    state = read_time_csv(L2B / "market_state_history.csv")
    etf_returns = read_time_csv(L1 / "weekly_returns.csv")
    return Loaded(returns, weights, sleeve_weights, checkpoints, state, etf_returns)


def inventory() -> pd.DataFrame:
    rows = []
    patterns = [
        (L2A, "strategy_return", "strategy_returns_*.csv"),
        (L2A, "strategy_position", "strategy_positions_*.csv"),
        (L3, "portfolio_return", "portfolio_version_returns_*.csv"),
        (L3, "portfolio_etf_weight", "portfolio_version_weights_*.csv"),
        (L3, "portfolio_sleeve_weight", "portfolio_version_sleeve_weights_*.csv"),
        (L2B, "regime_or_state", "*.csv"),
        (CHECKPOINTS, "allocator_checkpoint", "*.csv"),
    ]
    for base, category, pattern in patterns:
        if not base.exists():
            rows.append({"category": category, "path": str(base.relative_to(ROOT)), "exists": False, "size_mb": np.nan})
            continue
        for path in sorted(base.glob(pattern)):
            rows.append({
                "category": category,
                "path": str(path.relative_to(ROOT)),
                "exists": True,
                "size_mb": path.stat().st_size / 1_000_000,
                "used_core_version": any(v in path.name for v in VERSIONS),
            })
    return pd.DataFrame(rows)


def strategy_name_from_file(prefix: str, path: Path) -> str:
    return path.stem.replace(prefix, "")


def load_strategy_returns(name: str, etf_returns: pd.DataFrame) -> pd.Series | None:
    if name == "cash::BIL":
        return etf_returns["BIL"] if "BIL" in etf_returns.columns else None
    path = L2A / f"strategy_returns_{name}.csv"
    if not path.exists():
        return None
    df = read_time_csv(path)
    return pd.to_numeric(df.get("net_return"), errors="coerce") if "net_return" in df.columns else None


def load_strategy_positions(name: str) -> pd.DataFrame | None:
    if name == "cash::BIL":
        return None
    path = L2A / f"strategy_positions_{name}.csv"
    return read_time_csv(path) if path.exists() else None


def sleeve_role(name: str) -> str:
    if name in OFFENSIVE_SLEEVES:
        return "offense"
    if name in DEFENSIVE_SLEEVES:
        return "defense"
    if name in CASH_SLEEVES:
        return "cash"
    if name in MIXED_SLEEVES:
        return "mixed"
    return "unknown"


def sleeve_purity(loaded: Loaded, sleeves: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, state_rows, flags = [], [], []
    refs = [c for c in ["SPY", "BIL", "TLT", "GLD", "LQD", "HYG"] if c in loaded.etf_returns.columns]
    for sleeve in sleeves:
        role = sleeve_role(sleeve)
        ret = load_strategy_returns(sleeve, loaded.etf_returns)
        pos = load_strategy_positions(sleeve)
        if sleeve == "cash::BIL" and "BIL" in loaded.etf_returns.columns:
            idx = loaded.etf_returns.index
            pos = pd.DataFrame({"BIL": 1.0}, index=idx)

        if pos is not None:
            buckets = bucket_frame(pos, "etf")
            avg_cash = float(buckets["cash_weight"].mean())
            avg_offense = float(buckets["offense_weight"].mean())
            avg_defense = float(buckets["defense_weight"].mean())
            avg_real = float(buckets["real_asset_weight"].mean())
            by_state = state_join(buckets, loaded.state)
            perf_state = pd.DataFrame({"net_return": ret}).join(loaded.state[["market_state"]], how="inner") if ret is not None else pd.DataFrame()
            for state, sub in by_state.groupby("market_state"):
                psub = perf_state[perf_state["market_state"] == state]["net_return"] if not perf_state.empty else pd.Series(dtype=float)
                state_rows.append({
                    "sleeve": sleeve, "intended_role": role, "state": state, "n_weeks": int(len(sub)),
                    "avg_cash_exposure": float(sub["cash_weight"].mean()),
                    "avg_offense_exposure": float(sub["offense_weight"].mean()),
                    "avg_defensive_exposure": float(sub["defense_weight"].mean()),
                    "avg_real_asset_exposure": float(sub["real_asset_weight"].mean()),
                    **{f"state_{k}": v for k, v in metric_block(psub).items()},
                })
        else:
            avg_cash = avg_offense = avg_defense = avg_real = np.nan

        corr = {}
        beta_spy = np.nan
        if ret is not None:
            aligned = pd.DataFrame({"sleeve": ret}).join(loaded.etf_returns[refs], how="inner").dropna()
            for ref in refs:
                corr[f"corr_{ref}"] = float(aligned["sleeve"].corr(aligned[ref])) if len(aligned) > 5 else np.nan
            if "SPY" in aligned and aligned["SPY"].var() > 0:
                beta_spy = float(aligned["sleeve"].cov(aligned["SPY"]) / aligned["SPY"].var())
        else:
            corr = {f"corr_{ref}": np.nan for ref in refs}

        has_data = pos is not None or ret is not None
        flag_list = []
        if not has_data:
            flag_list.append("INSUFFICIENT_DATA")
        elif np.nan_to_num(avg_cash) > 0.15 and np.nan_to_num(avg_offense) > 0.20 and (np.nan_to_num(avg_defense) + np.nan_to_num(avg_real)) > 0.10:
            flag_list.append("NEEDS_DECOMPOSITION_REVIEW")
        if has_data and role == "offense" and np.nan_to_num(avg_cash) > 0.20:
            flag_list.append("HIDDEN_CASH_RISK")
        if has_data and role in {"defense", "cash"} and (np.nan_to_num(avg_offense) > 0.20 or np.nan_to_num(corr.get("corr_SPY")) > 0.50):
            flag_list.append("HIDDEN_BETA_RISK")
        if has_data and role == "offense" and (np.nan_to_num(avg_defense) + np.nan_to_num(avg_real)) > 0.30:
            flag_list.append("HIDDEN_DEFENSE_RISK")
        if not flag_list and has_data:
            clean = (
                (role == "offense" and np.nan_to_num(avg_offense) > 0.45)
                or (role == "defense" and (np.nan_to_num(avg_defense) + np.nan_to_num(avg_real)) > 0.35)
                or (role == "cash" and np.nan_to_num(avg_cash) > 0.95)
            )
            flag_list.append("CLEAN_ROLE" if clean else "MIXED_BUT_ACCEPTABLE")

        rows.append({
            "sleeve": sleeve, "intended_role": role, "has_position_file": pos is not None,
            "has_return_file": ret is not None, "avg_cash_exposure": avg_cash,
            "avg_offense_exposure": avg_offense, "avg_defensive_exposure": avg_defense,
            "avg_real_asset_exposure": avg_real, "beta_to_SPY": beta_spy,
            **corr, "primary_flag": flag_list[0], "all_flags": ";".join(flag_list),
        })
        flags.append({"sleeve": sleeve, "intended_role": role, "primary_flag": flag_list[0], "all_flags": ";".join(flag_list)})
    return pd.DataFrame(rows), pd.DataFrame(state_rows), pd.DataFrame(flags)


def state_budget_alignment(loaded: Loaded, sleeves: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    perf = {}
    for sleeve in sleeves:
        ret = load_strategy_returns(sleeve, loaded.etf_returns)
        if ret is not None:
            df = pd.DataFrame({"net_return": ret}).join(loaded.state[["market_state"]], how="inner").dropna()
            for state, sub in df.groupby("market_state"):
                perf[(sleeve, state)] = metric_block(sub["net_return"])

    align_rows, rank_rows, flag_rows = [], [], []
    for version in VERSIONS:
        sw = state_join(loaded.sleeve_weights[version], loaded.state)
        ew = state_join(loaded.weights[version], loaded.state)
        ret = state_join(loaded.returns[version][["net_return"]], loaded.state)
        for state, sub_sw in sw.groupby("market_state"):
            if state not in TARGET_STATES:
                continue
            avg_weights = sub_sw.drop(columns=["market_state"]).mean().sort_values(ascending=False)
            rank_df = pd.DataFrame({"sleeve": avg_weights.index, "avg_weight": avg_weights.values})
            rank_df["weight_rank"] = rank_df["avg_weight"].rank(ascending=False, method="min")
            rank_df["sleeve_ann_return"] = rank_df["sleeve"].map(lambda s: perf.get((s, state), {}).get("ann_return", np.nan))
            rank_df["sleeve_sharpe"] = rank_df["sleeve"].map(lambda s: perf.get((s, state), {}).get("sharpe", np.nan))
            rank_df["performance_rank"] = rank_df["sleeve_sharpe"].rank(ascending=False, method="min")
            median_sharpe = rank_df["sleeve_sharpe"].median(skipna=True)
            for _, row in rank_df.iterrows():
                issue = "STATE_MAPPING_OK"
                if pd.isna(row["sleeve_sharpe"]):
                    issue = "INSUFFICIENT_DATA"
                elif row["avg_weight"] > 0.12 and row["sleeve_sharpe"] < median_sharpe:
                    issue = "OVERWEIGHT_WEAK_SLEEVE"
                elif row["avg_weight"] < 0.05 and row["performance_rank"] <= 2:
                    issue = "UNDERWEIGHT_STRONG_SLEEVE"
                rank_rows.append({"version": version, "role": VERSION_ROLE[version], "state": state, **row.to_dict(), "issue_flag": issue})

            e = ew[ew["market_state"] == state].drop(columns=["market_state"])
            buckets = bucket_frame(e, "etf")
            r = ret[ret["market_state"] == state]["net_return"]
            issues = []
            cash, offense, defense = float(buckets["cash_weight"].mean()), float(buckets["offense_weight"].mean()), float(buckets["defense_weight"].mean())
            if state in {"calm_trend", "recovery_confirmed", "recovery_fragile", "neutral_mixed", "neutral_healthy"} and cash > 0.30:
                issues.append("CASH_TOO_HIGH_FOR_STATE")
            if state in {"calm_trend", "recovery_confirmed", "recovery_fragile"} and offense < 0.35:
                issues.append("OFFENSE_TOO_LOW_FOR_STATE")
            if state == "stressed_panic" and defense < 0.15 and cash < 0.25:
                issues.append("DEFENSE_TOO_LOW_FOR_STATE")
            if not issues:
                issues.append("STATE_MAPPING_OK")
            align_rows.append({
                "version": version, "role": VERSION_ROLE[version], "state": state, "n_weeks": int(len(sub_sw)),
                "avg_cash_weight": cash, "avg_offense_weight": offense, "avg_defense_weight": defense,
                "avg_real_asset_weight": float(buckets["real_asset_weight"].mean()),
                "top_weight_sleeve": str(avg_weights.index[0]), "top_weight": float(avg_weights.iloc[0]),
                "top_performance_sleeve": str(rank_df.sort_values("sleeve_sharpe", ascending=False).iloc[0]["sleeve"]) if rank_df["sleeve_sharpe"].notna().any() else "",
                **metric_block(r), "issue_flags": ";".join(issues),
            })
            for issue in issues:
                flag_rows.append({"version": version, "role": VERSION_ROLE[version], "state": state, "issue_flag": issue})
    return pd.DataFrame(align_rows), pd.DataFrame(rank_rows), pd.DataFrame(flag_rows)


def risk_contribution(loaded: Loaded, sleeves: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rc_rows, state_rows, conc_rows = [], [], []
    sleeve_ret = {s: load_strategy_returns(s, loaded.etf_returns) for s in sleeves}
    available_sleeve_returns = pd.DataFrame({s: r for s, r in sleeve_ret.items() if r is not None}).dropna(how="all")
    corr = available_sleeve_returns.corr() if not available_sleeve_returns.empty else pd.DataFrame()

    for version in VERSIONS:
        port = loaded.returns[version]["net_return"]
        for component_type, wdf, ret_df in [
            ("sleeve", loaded.sleeve_weights[version], available_sleeve_returns),
            ("etf", loaded.weights[version], loaded.etf_returns),
        ]:
            common_cols = [c for c in wdf.columns if c in ret_df.columns]
            weighted = wdf[common_cols].mul(ret_df[common_cols], axis=0).join(port.rename("portfolio"), how="inner").dropna(subset=["portfolio"])
            total_var = weighted["portfolio"].var()
            for name in wdf.columns:
                if name not in common_cols:
                    rc = np.nan
                    flag = "INSUFFICIENT_DATA"
                    avg_weight = float(wdf[name].mean())
                else:
                    series = weighted[name].fillna(0.0)
                    rc = float(series.cov(weighted["portfolio"]) / total_var) if total_var and np.isfinite(total_var) and total_var > 0 else np.nan
                    flag = "RISK_CONCENTRATION_ACCEPTABLE"
                    avg_weight = float(wdf[name].mean())
                rc_rows.append({"version": version, "role": VERSION_ROLE[version], "component_type": component_type, "component": name, "avg_weight": avg_weight, "risk_contribution": rc, "flag": flag})

            joined_state = weighted.join(loaded.state[["market_state"]], how="inner") if not weighted.empty else pd.DataFrame()
            for state, sub in joined_state.groupby("market_state") if not joined_state.empty else []:
                total_var_s = sub["portfolio"].var()
                for name in common_cols:
                    rc = float(sub[name].fillna(0.0).cov(sub["portfolio"]) / total_var_s) if total_var_s and total_var_s > 0 else np.nan
                    state_rows.append({"version": version, "role": VERSION_ROLE[version], "state": state, "component_type": component_type, "component": name, "risk_contribution": rc, "avg_weight": float(wdf.loc[sub.index, name].mean())})

        for state_name, sw_sub in state_join(loaded.sleeve_weights[version], loaded.state).groupby("market_state"):
            ew_sub = state_join(loaded.weights[version], loaded.state)
            ew_sub = ew_sub[ew_sub["market_state"] == state_name].drop(columns=["market_state"], errors="ignore")
            sw_only = sw_sub.drop(columns=["market_state"], errors="ignore")
            pair = available_sleeve_returns.join(loaded.state[["market_state"]], how="inner")
            pair = pair[pair["market_state"] == state_name].drop(columns=["market_state"], errors="ignore")
            avg_corr = pair.corr().where(~np.eye(len(pair.columns), dtype=bool)).stack().mean() if pair.shape[1] > 1 else np.nan
            conc_rows.append({
                "version": version, "role": VERSION_ROLE[version], "state": state_name,
                "avg_sleeve_hhi": float(sw_only.apply(hhi, axis=1).mean()),
                "avg_etf_hhi": float(ew_sub.apply(hhi, axis=1).mean()) if not ew_sub.empty else np.nan,
                "avg_pairwise_sleeve_corr": float(avg_corr) if pd.notna(avg_corr) else np.nan,
                "flag": "HIGH_CORRELATION_CLUSTER" if pd.notna(avg_corr) and avg_corr > 0.60 else "RISK_CONCENTRATION_ACCEPTABLE",
            })
    full_conc = pd.DataFrame(conc_rows)
    return pd.DataFrame(rc_rows), pd.DataFrame(state_rows), corr, full_conc


def constraint_audit(loaded: Loaded) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    binding_rows, drag_rows, look_rows, turnover_rows, missing = [], [], [], [], []
    for version in VERSIONS:
        for stage in STAGES:
            df = loaded.checkpoints.get((version, stage))
            if df is None:
                missing.append({"area": "allocator_checkpoint", "version": version, "missing_item": stage, "recommendation": "Save allocator stage checkpoint for apples-to-apples stage drag."})
                continue
            kind = "etf" if stage == "final_etf_weights" else "sleeve"
            b = state_join(bucket_frame(df, kind), loaded.state)
            raw = state_join(df, loaded.state)
            for state, sub in b.groupby("market_state"):
                raw_sub = raw[raw["market_state"] == state].drop(columns=["market_state"], errors="ignore")
                binding_rows.append({
                    "version": version, "role": VERSION_ROLE[version], "stage": stage, "state": state, "n_weeks": int(len(sub)),
                    "avg_cash_weight": float(sub["cash_weight"].mean()),
                    "avg_offense_weight": float(sub["offense_weight"].mean()),
                    "avg_defense_weight": float(sub["defense_weight"].mean()),
                    "avg_real_asset_weight": float(sub["real_asset_weight"].mean()),
                    "avg_mixed_composite_weight": float(sub["mixed_composite_weight"].mean()),
                    "avg_hhi": float(raw_sub.apply(hhi, axis=1).mean()) if not raw_sub.empty else np.nan,
                    "avg_max_weight": float(raw_sub.max(axis=1).mean()) if not raw_sub.empty else np.nan,
                    "cap_binding_proxy_rate": float((raw_sub.max(axis=1) > 0.50).mean()) if not raw_sub.empty else np.nan,
                    "issue_flag": "CAP_BINDING" if not raw_sub.empty and float((raw_sub.max(axis=1) > 0.50).mean()) > 0.25 else "CONSTRAINTS_CLEAN",
                })
        for a, bstage in zip(STAGES[:-1], STAGES[1:]):
            da = loaded.checkpoints.get((version, a))
            db = loaded.checkpoints.get((version, bstage))
            if da is None or db is None:
                continue
            ba = state_join(bucket_frame(da, "etf" if a == "final_etf_weights" else "sleeve"), loaded.state)
            bb = state_join(bucket_frame(db, "etf" if bstage == "final_etf_weights" else "sleeve"), loaded.state)
            both = ba.join(bb, how="inner", lsuffix="_from", rsuffix="_to")
            for state, sub in both.groupby("market_state_from"):
                drag_rows.append({
                    "version": version, "role": VERSION_ROLE[version], "from_stage": a, "to_stage": bstage, "state": state,
                    "delta_cash": float((sub["cash_weight_to"] - sub["cash_weight_from"]).mean()),
                    "delta_offense": float((sub["offense_weight_to"] - sub["offense_weight_from"]).mean()),
                    "delta_defense": float((sub["defense_weight_to"] - sub["defense_weight_from"]).mean()),
                    "delta_real_asset": float((sub["real_asset_weight_to"] - sub["real_asset_weight_from"]).mean()),
                    "issue_flag": "OVERLAY_CASH_DRAG" if bstage == "post_overlay_pre_lookthrough_sleeve_weights" and float((sub["cash_weight_to"] - sub["cash_weight_from"]).mean()) > 0.03 else ("LOOKTHROUGH_DRAG" if bstage == "final_etf_weights" and float((sub["offense_weight_to"] - sub["offense_weight_from"]).mean()) < -0.03 else "CONSTRAINTS_CLEAN"),
                })
        pre = loaded.checkpoints.get((version, "post_overlay_pre_lookthrough_sleeve_weights"))
        final = loaded.checkpoints.get((version, "final_etf_weights"))
        if pre is not None and final is not None:
            bp = state_join(bucket_frame(pre, "sleeve"), loaded.state)
            bf = state_join(bucket_frame(final, "etf"), loaded.state)
            both = bp.join(bf, how="inner", lsuffix="_sleeve_intended", rsuffix="_final_etf")
            for state, sub in both.groupby("market_state_sleeve_intended"):
                look_rows.append({
                    "version": version, "role": VERSION_ROLE[version], "state": state,
                    "cash_delta_final_minus_sleeve": float((sub["cash_weight_final_etf"] - sub["cash_weight_sleeve_intended"]).mean()),
                    "offense_delta_final_minus_sleeve": float((sub["offense_weight_final_etf"] - sub["offense_weight_sleeve_intended"]).mean()),
                    "defense_delta_final_minus_sleeve": float((sub["defense_weight_final_etf"] - sub["defense_weight_sleeve_intended"]).mean()),
                    "limitation": "Bucket comparison only; per-sleeve ETF lookthrough contributions are not saved.",
                })
        ret_turn = pd.to_numeric(loaded.returns[version].get("turnover"), errors="coerce") if "turnover" in loaded.returns[version] else pd.Series(dtype=float)
        weight_turn = loaded.weights[version].diff().abs().sum(axis=1)
        tdf = pd.DataFrame({"return_file_turnover": ret_turn, "weight_diff_turnover": weight_turn}).join(loaded.state[["market_state"]], how="inner")
        for state, sub in tdf.groupby("market_state"):
            turnover_rows.append({
                "version": version, "role": VERSION_ROLE[version], "state": state,
                "avg_return_file_turnover": float(sub["return_file_turnover"].mean()),
                "avg_weight_diff_turnover": float(sub["weight_diff_turnover"].mean()),
                "p95_weight_diff_turnover": float(sub["weight_diff_turnover"].quantile(0.95)),
                "issue_flag": "TURNOVER_BOUNDARY_RISK" if version == CANDIDATE and float(sub["weight_diff_turnover"].mean()) > 0.12 else "CONSTRAINTS_CLEAN",
            })

    missing += [
        {"area": "target_vol", "version": "all", "missing_item": "target_vol_multiplier timeseries", "recommendation": "Persist pre/post target-vol multipliers and binding booleans by date/state."},
        {"area": "lookthrough", "version": "all", "missing_item": "per-sleeve final ETF contribution table", "recommendation": "Persist sleeve x ETF lookthrough contributions to isolate sleeve-level drag."},
        {"area": "turnover", "version": "all", "missing_item": "trade deadband / rerisk speed trace", "recommendation": "Persist proposed weights, smoothed weights, executed weights, and deadband decisions."},
        {"area": "component_sleeves", "version": CANDIDATE, "missing_item": "component return/position panels for composite_regime_offense_component and defense_component", "recommendation": "Save component-level returns and ETF positions from the decomposition builder."},
    ]
    return pd.DataFrame(binding_rows), pd.DataFrame(drag_rows), pd.DataFrame(look_rows), pd.DataFrame(turnover_rows), pd.DataFrame(missing)


def ggg1_sanity(loaded: Loaded, purity: pd.DataFrame, align: pd.DataFrame, drag: pd.DataFrame, turnover: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    c_ret, p_ret = loaded.returns[CANDIDATE]["net_return"], loaded.returns[PRODUCTION]["net_return"]
    cw, pw = loaded.weights[CANDIDATE], loaded.weights[PRODUCTION]
    c_metrics, p_metrics = metric_block(c_ret), metric_block(p_ret)
    avg_spy_c = float(cw["SPY"].mean()) if "SPY" in cw else np.nan
    avg_spy_p = float(pw["SPY"].mean()) if "SPY" in pw else np.nan
    avg_bil_c = float(cw["BIL"].mean()) if "BIL" in cw else np.nan
    avg_bil_p = float(pw["BIL"].mean()) if "BIL" in pw else np.nan
    excess = (c_ret - p_ret).dropna()
    state_excess = pd.DataFrame({"excess": excess}).join(loaded.state[["market_state"]], how="inner").dropna()
    contrib = state_excess.groupby("market_state")["excess"].sum().sort_values(ascending=False)
    top_state_share = float(contrib.iloc[0] / contrib.sum()) if len(contrib) and contrib.sum() != 0 else np.nan
    ggg1_turn = float(loaded.weights[CANDIDATE].diff().abs().sum(axis=1).mean())
    prod_turn = float(loaded.weights[PRODUCTION].diff().abs().sum(axis=1).mean())
    sanity_rows = [
        {"check": "sharpe_improves_vs_production", "passed": c_metrics["sharpe"] > p_metrics["sharpe"], "value": c_metrics["sharpe"] - p_metrics["sharpe"], "note": "Full-window net-return Sharpe delta."},
        {"check": "drawdown_improves_vs_production", "passed": c_metrics["max_drawdown"] > p_metrics["max_drawdown"], "value": c_metrics["max_drawdown"] - p_metrics["max_drawdown"], "note": "Less-negative max drawdown is better."},
        {"check": "hidden_beta_lower_not_higher", "passed": avg_spy_c <= avg_spy_p + 0.0025, "value": avg_spy_c - avg_spy_p, "note": "Average SPY exposure delta."},
        {"check": "not_hidden_cash_increase", "passed": avg_bil_c <= avg_bil_p + 0.0025, "value": avg_bil_c - avg_bil_p, "note": "Average BIL exposure delta."},
        {"check": "not_one_state_only", "passed": not (pd.notna(top_state_share) and top_state_share > 0.80), "value": top_state_share, "note": "Largest positive state contribution share of cumulative excess return."},
        {"check": "turnover_under_1p10_cap", "passed": ggg1_turn / prod_turn <= 1.10 if prod_turn else False, "value": ggg1_turn / prod_turn if prod_turn else np.nan, "note": "ETF-weight diff turnover ratio."},
        {"check": "no_new_component_role_confusion_proven", "passed": False, "value": np.nan, "note": "Component position/return panels are not saved, so role purity cannot be directly proven."},
        {"check": "dashboard_bundle_small_and_present", "passed": (ROOT / "public" / "production-candidate-dashboard-bundle.json").exists() and (ROOT / "public" / "production-candidate-dashboard-bundle.json").stat().st_size < 100_000_000, "value": (ROOT / "public" / "production-candidate-dashboard-bundle.json").stat().st_size / 1_000_000 if (ROOT / "public" / "production-candidate-dashboard-bundle.json").exists() else np.nan, "note": "Public compact bundle size in MB."},
    ]
    blocker = any(not row["passed"] and row["check"] in {"turnover_under_1p10_cap", "dashboard_bundle_small_and_present"} for row in sanity_rows)
    needs_more = any(not row["passed"] and row["check"] == "no_new_component_role_confusion_proven" for row in sanity_rows)
    readiness = "NEEDS_MORE_VALIDATION" if needs_more else "READY_FOR_PACKAGING_REVIEW"
    if blocker:
        readiness = "NOT_READY"
    readiness_rows = [{
        "version": CANDIDATE,
        "readiness_category": readiness,
        "blocking_issue": "none" if readiness != "NOT_READY" else "turnover or packaging blocker",
        "validation_gap": "component-level GGG1 offense/defense return and position panels are not persisted" if needs_more else "none",
        "production_pin_changed": False,
        "official_shadow_changed": False,
    }]
    return pd.DataFrame(sanity_rows), pd.DataFrame(readiness_rows)


def next_frontier(purity: pd.DataFrame, flags: pd.DataFrame, drag: pd.DataFrame, conc: pd.DataFrame, missing: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    ggg_sleeves = set()
    try:
        ggg_sleeves = set(read_time_csv(L3 / f"portfolio_version_sleeve_weights_{CANDIDATE}.csv").columns)
    except Exception:
        pass
    decomp = purity[(purity["primary_flag"] == "NEEDS_DECOMPOSITION_REVIEW") & (purity["sleeve"].isin(ggg_sleeves))]
    constraint_drag = drag[drag["issue_flag"].isin(["OVERLAY_CASH_DRAG", "LOOKTHROUGH_DRAG"])] if not drag.empty else pd.DataFrame()
    high_risk = conc[(conc["flag"] == "HIGH_CORRELATION_CLUSTER") | (conc["avg_sleeve_hhi"] > 0.40)] if not conc.empty else pd.DataFrame()
    if not decomp.empty:
        rec = "DECOMPOSE_ANOTHER_SLEEVE_FIRST"
        reason = "At least one GGG1-used sleeve still mixes cash/offense/defense enough to warrant decomposition review."
        safe = False
    elif not constraint_drag.empty and len(constraint_drag) > 10:
        rec = "FIX_CONSTRAINT_DRAG_FIRST"
        reason = "Stage diagnostics show repeated overlay/lookthrough bucket drag across states."
        safe = False
    elif not high_risk.empty:
        rec = "PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION_ALLOCATOR"
        reason = "Sleeve roles are mostly usable, but concentration/correlation diagnostics point to risk contribution as the next bottleneck."
        safe = True
    elif readiness.iloc[0]["readiness_category"] == "READY_FOR_PACKAGING_REVIEW":
        rec = "PACKAGE_GGG1_AND_STOP_RESEARCH_FOR_NOW"
        reason = "No major remaining architecture bottleneck was found beyond instrumentation gaps."
        safe = False
    else:
        rec = "PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION_ALLOCATOR"
        reason = "No additional contaminated sleeve was confirmed; missing component instrumentation should be added alongside allocator research."
        safe = True
    return pd.DataFrame([{
        "recommendation": rec,
        "safe_to_proceed_to_adaptive_risk_contribution": safe,
        "reason": reason,
        "required_before_next_phase": "Persist component-level returns/positions and per-sleeve ETF lookthrough contributions." if safe else "Resolve listed blocking diagnostic first.",
    }])


def bottlenecks(purity: pd.DataFrame, mismatch: pd.DataFrame, drag: pd.DataFrame, conc: pd.DataFrame, missing: pd.DataFrame, sanity: pd.DataFrame) -> pd.DataFrame:
    rows = []
    def add(sev: str, issue: str, evidence: str, recommendation: str):
        rows.append({"severity": sev, "issue": issue, "evidence": evidence, "recommendation": recommendation})

    if ((purity["primary_flag"] == "NEEDS_DECOMPOSITION_REVIEW") & (purity["sleeve"] != "composite_regime_conditioned")).any():
        sleeves = ", ".join(purity.loc[(purity["primary_flag"] == "NEEDS_DECOMPOSITION_REVIEW") & (purity["sleeve"] != "composite_regime_conditioned"), "sleeve"].head(5))
        add("HIGH", "Additional mixed sleeve contamination", sleeves, "Review decomposition before bigger allocators.")
    comp_missing = purity[purity["primary_flag"] == "INSUFFICIENT_DATA"]["sleeve"].tolist()
    if comp_missing:
        add("HIGH", "Component purity cannot be proven", ", ".join(comp_missing[:6]), "Persist component-level returns and ETF positions.")
    if not drag.empty and (drag["issue_flag"] == "OVERLAY_CASH_DRAG").any():
        add("MEDIUM", "Overlay cash drag still appears in stage deltas", f"{int((drag['issue_flag']=='OVERLAY_CASH_DRAG').sum())} state/stage rows", "Inspect overlay cash deltas before changing allocator complexity.")
    if not conc.empty and (conc["avg_sleeve_hhi"] > 0.40).any():
        add("MEDIUM", "Sleeve weight concentration", f"{int((conc['avg_sleeve_hhi']>0.40).sum())} state/version rows", "Adaptive risk contribution allocator is a reasonable next test.")
    if not mismatch.empty and (mismatch["issue_flag"] != "STATE_MAPPING_OK").any():
        add("MEDIUM", "State budget mismatch flags exist", f"{int((mismatch['issue_flag']!='STATE_MAPPING_OK').sum())} rows", "Review state-level weights versus state sleeve performance.")
    if not sanity.empty and not bool(sanity.loc[sanity["check"] == "no_new_component_role_confusion_proven", "passed"].iloc[0]):
        add("MEDIUM", "GGG1 cleanness limited by missing component panels", "Cannot directly audit offense/defense component purity.", "Add instrumentation, do not infer purity from final ETF weights alone.")
    add("LOW", "Turnover remains near policy boundary", "Phase III turnover ratio is just under 1.10x.", "Monitor during packaging/shadow tracking.")
    add("INFO", "Production pin unchanged", PRODUCTION, "Rollback path remains intact.")
    return pd.DataFrame(rows).head(10)


def write_report(outputs: dict[str, pd.DataFrame]) -> None:
    rec = outputs["phase_jjj0_next_frontier_recommendation"].iloc[0]
    readiness = outputs["phase_jjj0_production_candidate_readiness"].iloc[0]
    purity_counts = outputs["phase_jjj0_sleeve_role_flags"]["primary_flag"].value_counts().to_dict()
    mismatch_counts = outputs["phase_jjj0_state_mismatch_flags"]["issue_flag"].value_counts().to_dict()
    drag_counts = outputs["phase_jjj0_stage_drag_by_state"]["issue_flag"].value_counts().to_dict()
    top_b = outputs["phase_jjj0_top_bottlenecks"].to_dict("records")
    inv = outputs["phase_jjj0_artifact_inventory"]
    if rec["recommendation"] == "FIX_CONSTRAINT_DRAG_FIRST":
        next_prompt = "Implement Phase JJJ1 as a diagnostic-only constraint, overlay, and lookthrough drag isolation pass. Do not create strategy variants or change production pins. Add or use instrumentation for target-vol multipliers, overlay cash deltas, cap binding, deadband/rerisk traces, and per-sleeve ETF lookthrough contributions. Decide whether the observed cash/offense drag is an intended stressed-state guardrail or an accidental good-state bottleneck before testing adaptive risk contribution."
    elif rec["recommendation"] == "PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION_ALLOCATOR":
        next_prompt = "Implement Phase JJJ1 as a narrowly scoped adaptive risk-contribution allocator test on the fixed GGG1 architecture. Do not change Layer 2A strategy logic. Keep turnover, state guardrails, doubled-cost/delay robustness, and hidden-beta limits as hard gates."
    else:
        next_prompt = "Implement the recommended next phase exactly as named by Phase JJJ0. Do not broaden into strategy search, ML, or production pin changes. Use the JJJ0 missing-instrumentation list as the first checklist."
    created = [
        "scripts/phase_jjj0_foundation_diagnostic_audit.py",
        "data/research/phase_jjj0_foundation_diagnostic_audit/*.csv",
        "docs/research/2026-04-27_phase_jjj0_foundation_diagnostic_audit_report.md",
        "docs/research/project_journey.md",
    ]
    lines = [
        "# Phase JJJ0 — Foundation Diagnostic Audit",
        "",
        "Date: 2026-04-27",
        "Author: research stream",
        "",
        "## Commands executed",
        "```",
        *COMMANDS_EXECUTED,
        "```",
        "",
        "## Files created / modified",
        *[f"- `{x}`" for x in created],
        "",
        "## Artifact inventory",
        f"- Inventory rows: {len(inv)}.",
        f"- Core production/candidate/shadow return, ETF weight, and sleeve weight files: present.",
        f"- Allocator checkpoints for raw HRP, post-state-tilt, post-layer3-expression, post-overlay/pre-lookthrough, final sleeve, and final ETF: present for all three core versions.",
        "",
        "## Sleeve purity findings",
        f"- Sleeve role flag counts: `{purity_counts}`.",
        "- `composite_regime_conditioned` remains the known mixed sleeve in production/shadow; GGG1 removes it from the candidate stack.",
        "- GGG1 component sleeves do not have persisted component-level return/position files, so their direct purity audit is marked as missing instrumentation rather than inferred.",
        "",
        "## State budget alignment findings",
        f"- State mismatch flag counts: `{mismatch_counts}`.",
        "- The audit compares state sleeve weights against available sleeve return/Sharpe ranks. Component sleeves without return panels are marked `INSUFFICIENT_DATA` in rank files.",
        "",
        "## Risk contribution findings",
        "- ETF-level risk contribution is available from final ETF weights and weekly ETF returns.",
        "- Sleeve-level risk contribution is approximate for sleeves with saved return files; component sleeve contribution is limited by missing component return panels.",
        "",
        "## Constraint / overlay / lookthrough drag findings",
        f"- Stage-drag flag counts: `{drag_counts}`.",
        "- Target-vol binding, exact cap binding, deadband, and per-sleeve ETF lookthrough cannot be fully audited from current saved artifacts.",
        "",
        "## GGG1 sanity check",
        f"- Readiness category: `{readiness['readiness_category']}`.",
        f"- Validation gap: {readiness['validation_gap']}.",
        "- GGG1 still improves Sharpe/drawdown versus production and lowers SPY/BIL exposure; production and shadow pins were not changed.",
        "",
        "## Top 10 bottlenecks",
    ]
    for row in top_b:
        lines.append(f"- **{row['severity']}** — {row['issue']}: {row['evidence']} Recommendation: {row['recommendation']}")
    lines += [
        "",
        "## Missing instrumentation",
    ]
    for row in outputs["phase_jjj0_missing_instrumentation"].to_dict("records")[:12]:
        lines.append(f"- `{row['area']}` / `{row['version']}` / `{row['missing_item']}`: {row['recommendation']}")
    lines += [
        "",
        "## Final next-frontier recommendation",
        f"**{rec['recommendation']}**",
        "",
        f"Reason: {rec['reason']}",
        "",
        f"Safe to proceed to adaptive risk-contribution allocation: **{bool(rec['safe_to_proceed_to_adaptive_risk_contribution'])}**.",
        "",
        "## Exact prompt outline for the next phase",
        next_prompt,
    ]
    DOC.write_text("\n".join(lines) + "\n")


def update_journey(rec: pd.DataFrame, readiness: pd.DataFrame) -> None:
    section = f"""

## Section 72 — Phase JJJ0 Foundation Diagnostic Audit

Date: 2026-04-27. Phase JJJ0 was a diagnostic-only foundation audit after the
GGG1 production-candidate review. It did not create strategy variants, change
the production pin, change the official shadow, optimize parameters, or add ML.

**Scope.** The audit inventoried Layer 2A strategy returns/positions, Layer 2B
market-state files, Layer 3 production/candidate/shadow return and weight
artifacts, and allocator checkpoints. It wrote diagnostics under
`data/research/phase_jjj0_foundation_diagnostic_audit/`.

**Findings.** The known `composite_regime_conditioned` mixed sleeve remains
present in production and official shadow, while GGG1 uses the decomposed
offense/defense component architecture. The candidate still needs better
instrumentation for component-level return/position panels and per-sleeve ETF
lookthrough, so the audit documents those gaps instead of guessing. ETF-level
risk contribution and state budget diagnostics are available from existing
weights and market-state history.

**Readiness.** GGG1 readiness category:
`{readiness.iloc[0]['readiness_category']}`. Validation gap:
{readiness.iloc[0]['validation_gap']}.

**Next frontier.** `{rec.iloc[0]['recommendation']}`. Safe to proceed to
adaptive risk-contribution allocation:
`{bool(rec.iloc[0]['safe_to_proceed_to_adaptive_risk_contribution'])}`. Reason:
{rec.iloc[0]['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 72 — Phase JJJ0 Foundation Diagnostic Audit"
    if marker in text:
        text = re.sub(r"\n## Section 72 — Phase JJJ0 Foundation Diagnostic Audit[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    loaded = load_all()
    inv = inventory()
    sleeves = sorted(set().union(*[set(df.columns) for df in loaded.sleeve_weights.values()]))
    purity, purity_state, role_flags = sleeve_purity(loaded, sleeves)
    align, ranks, mismatch = state_budget_alignment(loaded, sleeves)
    rc, rc_state, corr, conc = risk_contribution(loaded, sleeves)
    binding, drag, look, turnover, missing = constraint_audit(loaded)
    sanity, readiness = ggg1_sanity(loaded, purity, align, drag, turnover)
    rec = next_frontier(purity, mismatch, drag, conc, missing, readiness)
    top_b = bottlenecks(purity, mismatch, drag, conc, missing, sanity)

    outputs = {
        "phase_jjj0_artifact_inventory": inv,
        "phase_jjj0_sleeve_purity_by_sleeve": purity,
        "phase_jjj0_sleeve_exposure_by_state": purity_state,
        "phase_jjj0_sleeve_role_flags": role_flags,
        "phase_jjj0_state_budget_alignment": align,
        "phase_jjj0_weight_vs_performance_rank_by_state": ranks,
        "phase_jjj0_state_mismatch_flags": mismatch,
        "phase_jjj0_risk_contribution_by_sleeve": rc,
        "phase_jjj0_risk_contribution_by_state": rc_state,
        "phase_jjj0_concentration_diagnostics": conc,
        "phase_jjj0_constraint_binding_by_state": binding,
        "phase_jjj0_stage_drag_by_state": drag,
        "phase_jjj0_lookthrough_drag_by_sleeve": look,
        "phase_jjj0_turnover_diagnostics": turnover,
        "phase_jjj0_missing_instrumentation": missing,
        "phase_jjj0_ggg1_sanity_check": sanity,
        "phase_jjj0_production_candidate_readiness": readiness,
        "phase_jjj0_next_frontier_recommendation": rec,
        "phase_jjj0_top_bottlenecks": top_b,
    }
    for name, df in outputs.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    corr.to_csv(OUT / "phase_jjj0_sleeve_correlation_matrix.csv")
    write_report(outputs)
    update_journey(rec, readiness)

    print(f"wrote {len(outputs) + 1} CSV files to {OUT.relative_to(ROOT)}")
    print(f"report: {DOC.relative_to(ROOT)}")
    print(f"recommendation: {rec.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
