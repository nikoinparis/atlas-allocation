"""Phase PP — direct redesign of composite_regime_conditioned fallback tiers.

Focus:
1. Diagnose how the sleeve's favorable-state 25% BIL tier behaves.
2. Test a small set of direct fallback-mix redesigns that preserve the
   stressed 65% BIL tier.
3. Evaluate whether fallback-tier redesign translates into real portfolio
   benefit through the production pipeline.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


ROOT = roc.ROOT
PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
TARGET_SLEEVE = "composite_regime_conditioned"
PHASE_PP_CANDIDATES = [
    "improved_phasepp_composite_bond_gold_fallback",
    "improved_phasepp_composite_balanced_defensive_fallback",
    "improved_phasepp_composite_combined_fallback_redesign",
]
AUDIT_DIR = ROOT / "data" / "research" / "phase_pp_composite_fallback_redesign"
OUTPUT_DIR = ROOT / "data" / "05_layer3_portfolio_construction"
REPORT_PATH = ROOT / "docs" / "research" / "2026-04-27_phase_pp_composite_fallback_redesign_report.md"
DEFENSIVE_ETFS = {"IEF", "SHY", "TLT", "TIP", "GLD"}
COMMAND_LOG: list[str] = []


def record_command(command: list[str]) -> str:
    rendered = " ".join(command)
    COMMAND_LOG.append(rendered)
    return rendered


def run_logged(command: list[str], *, env: dict[str, str] | None = None, timeout: int = 7200) -> subprocess.CompletedProcess:
    rendered = record_command(command)
    result = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {rendered}\n"
            f"stdout tail:\n{chr(10).join((result.stdout or '').splitlines()[-20:])}\n"
            f"stderr tail:\n{chr(10).join((result.stderr or '').splitlines()[-20:])}"
        )
    return result


def build_candidates() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join([PRODUCTION, SHADOW] + PHASE_PP_CANDIDATES)
    run_logged([sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")], env=env)


def is_strong_neutral(row: pd.Series) -> bool:
    if row is None or row.empty:
        return False
    try:
        return (
            str(row.get("market_state") or "") == "neutral_mixed"
            and float(row.get("market_trend_positive") or 0.0) > 0.0
            and float(row.get("breadth_sma_43") or 0.0) >= 0.55
            and float(row.get("breadth_26w_mom") or 0.0) >= 0.50
        )
    except (TypeError, ValueError):
        return False


def load_state_history() -> pd.DataFrame:
    state = roc.load_market_state(refined=False).copy()
    state["strong_neutral"] = state.apply(is_strong_neutral, axis=1)
    state["state_bucket"] = np.where(
        state["strong_neutral"] & state["market_state"].eq("neutral_mixed"),
        "neutral_healthy_proxy",
        state["market_state"],
    )
    return state


def load_positions(strategy_name: str) -> pd.DataFrame:
    path = ROOT / "data" / "03_layer2a_strategy_logic" / f"strategy_positions_{strategy_name}.csv"
    df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def load_base_positions(sleeves: list[str]) -> dict[str, pd.DataFrame]:
    return {
        sleeve: load_positions(sleeve)
        for sleeve in sleeves
        if (ROOT / "data" / "03_layer2a_strategy_logic" / f"strategy_positions_{sleeve}.csv").exists()
    }


def apply_internal_redeploy(
    base_positions: dict[str, pd.DataFrame],
    state_history: pd.DataFrame,
    *,
    target_sleeves: list[str],
    redeploy_config: dict[str, float],
    strong_neutral_fraction: float = 0.0,
    cash_proxy: str = "BIL",
) -> dict[str, pd.DataFrame]:
    out = {name: df.copy() for name, df in base_positions.items()}
    aligned_state = state_history.reindex(next(iter(base_positions.values())).index)
    for sleeve_name in target_sleeves:
        if sleeve_name not in out:
            continue
        positions = out[sleeve_name].copy()
        if cash_proxy not in positions.columns:
            continue
        modified = positions.copy()
        for date, row in positions.iterrows():
            if date not in aligned_state.index:
                continue
            state_row = aligned_state.loc[date]
            redeploy_fraction = 0.0
            if bool(state_row.get("strong_neutral", False)):
                redeploy_fraction = strong_neutral_fraction
            else:
                redeploy_fraction = float(redeploy_config.get(str(state_row.get("market_state") or ""), 0.0))
            if redeploy_fraction <= 0.0:
                continue
            bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
            if bil_weight <= 0.0:
                continue
            risky_row = row.drop(cash_proxy, errors="ignore")
            risky_sum = float(risky_row.sum())
            if risky_sum <= 1e-9:
                continue
            bil_shift = bil_weight * redeploy_fraction
            modified.at[date, cash_proxy] = bil_weight - bil_shift
            for col in risky_row.index:
                w = float(risky_row.get(col, 0.0) or 0.0)
                if w > 0.0:
                    modified.at[date, col] = w + bil_shift * (w / risky_sum)
        out[sleeve_name] = modified
    return out


def apply_fallback_redesign(
    base_positions: dict[str, pd.DataFrame],
    state_history: pd.DataFrame,
    *,
    sleeve_name: str,
    favorable_keep_bil_fraction: float,
    fallback_mix: dict[str, float],
    apply_market_states: set[str],
    apply_strong_neutral: bool = True,
    target_bil_tier: float = 0.25,
    cash_proxy: str = "BIL",
) -> dict[str, pd.DataFrame]:
    out = {name: df.copy() for name, df in base_positions.items()}
    aligned_state = state_history.reindex(next(iter(base_positions.values())).index)
    if sleeve_name not in out:
        return out
    positions = out[sleeve_name].copy()
    if cash_proxy not in positions.columns:
        return out
    available_mix = {k: float(v) for k, v in fallback_mix.items() if k in positions.columns and k != cash_proxy and float(v) > 0.0}
    mix_sum = float(sum(available_mix.values()))
    if mix_sum <= 0.0:
        return out

    modified = positions.copy()
    for date, row in positions.iterrows():
        if date not in aligned_state.index:
            continue
        state_row = aligned_state.loc[date]
        market_state = str(state_row.get("market_state") or "")
        strong_neutral = bool(state_row.get("strong_neutral", False))
        if market_state not in apply_market_states and not (apply_strong_neutral and strong_neutral):
            continue
        bil_weight = float(row.get(cash_proxy, 0.0) or 0.0)
        if abs(bil_weight - target_bil_tier) > 1e-9:
            continue
        new_bil = bil_weight * favorable_keep_bil_fraction
        bil_shift = bil_weight - new_bil
        if bil_shift <= 0.0:
            continue
        modified.at[date, cash_proxy] = new_bil
        for etf, weight in available_mix.items():
            modified.at[date, etf] = float(modified.at[date, etf]) + bil_shift * (weight / mix_sum)
    out[sleeve_name] = modified
    return out


def candidate_position_maps(base_positions: dict[str, pd.DataFrame], state_history: pd.DataFrame) -> tuple[dict[str, dict[str, pd.DataFrame]], dict[str, dict]]:
    configs = {
        "improved_phasepp_composite_bond_gold_fallback": {
            "kind": "fallback",
            "keep_bil_fraction": 0.50,
            "fallback_mix": {"GLD": 0.50, "TLT": 0.50},
            "apply_market_states": {"calm_trend", "recovery_confirmed", "recovery_fragile"},
            "apply_strong_neutral": True,
        },
        "improved_phasepp_composite_balanced_defensive_fallback": {
            "kind": "fallback",
            "keep_bil_fraction": 0.45,
            "fallback_mix": {"GLD": 0.35, "TLT": 0.30, "LQD": 0.20, "HYG": 0.15},
            "apply_market_states": {"calm_trend", "recovery_confirmed", "recovery_fragile"},
            "apply_strong_neutral": True,
        },
        "improved_phasepp_composite_combined_fallback_redesign": {
            "kind": "combo",
            "keep_bil_fraction": 0.50,
            "fallback_mix": {"GLD": 0.50, "TLT": 0.50},
            "apply_market_states": {"calm_trend", "recovery_confirmed", "recovery_fragile"},
            "apply_strong_neutral": True,
            "redeploy_config": {"recovery_fragile": 0.20, "recovery_confirmed": 0.15},
            "strong_neutral_fraction": 0.10,
        },
    }
    maps: dict[str, dict[str, pd.DataFrame]] = {PRODUCTION: base_positions, SHADOW: base_positions}
    for name, cfg in configs.items():
        if cfg["kind"] == "combo":
            base = apply_internal_redeploy(
                base_positions,
                state_history,
                target_sleeves=[TARGET_SLEEVE],
                redeploy_config=cfg["redeploy_config"],
                strong_neutral_fraction=cfg["strong_neutral_fraction"],
            )
        else:
            base = base_positions
        maps[name] = apply_fallback_redesign(
            base,
            state_history,
            sleeve_name=TARGET_SLEEVE,
            favorable_keep_bil_fraction=cfg["keep_bil_fraction"],
            fallback_mix=cfg["fallback_mix"],
            apply_market_states=cfg["apply_market_states"],
            apply_strong_neutral=cfg["apply_strong_neutral"],
        )
    return maps, configs


def fallback_tier_by_state(positions: pd.DataFrame, state_history: pd.DataFrame) -> pd.DataFrame:
    merged = positions.join(state_history[["state_bucket"]], how="inner")
    rows = []
    for state, sub in merged.groupby("state_bucket", observed=False):
        bil = sub["BIL"]
        is_25 = bil.round(4) == 0.25
        tier_sub = sub.loc[is_25]
        offense_cols = [c for c in positions.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
        defense_cols = [c for c in positions.columns if c not in offense_cols and c != "BIL"]
        rows.append(
            {
                "state": state,
                "n_weeks": int(len(sub)),
                "avg_BIL": float(bil.mean()),
                "pct_BIL_0": float((bil == 0.0).mean()),
                "pct_BIL_25": float(is_25.mean()),
                "pct_BIL_65": float((bil.round(4) == 0.65).mean()),
                "pct_BIL_7375": float((bil.round(4) == 0.7375).mean()),
                "dominant_BIL_tier": float(bil.round(4).value_counts(normalize=True).idxmax()),
                "avg_noncash_offense_when_25": float(tier_sub.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1).mean()) if not tier_sub.empty else np.nan,
                "avg_noncash_defense_when_25": float(tier_sub.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1).mean()) if not tier_sub.empty else np.nan,
                "avg_GLD_when_25": float(tier_sub.get("GLD", pd.Series(0.0, index=tier_sub.index)).mean()) if not tier_sub.empty else np.nan,
                "avg_TLT_when_25": float(tier_sub.get("TLT", pd.Series(0.0, index=tier_sub.index)).mean()) if not tier_sub.empty else np.nan,
                "avg_LQD_when_25": float(tier_sub.get("LQD", pd.Series(0.0, index=tier_sub.index)).mean()) if not tier_sub.empty else np.nan,
                "avg_HYG_when_25": float(tier_sub.get("HYG", pd.Series(0.0, index=tier_sub.index)).mean()) if not tier_sub.empty else np.nan,
                "avg_SPY_when_25": float(tier_sub.get("SPY", pd.Series(0.0, index=tier_sub.index)).mean()) if not tier_sub.empty else np.nan,
            }
        )
    out = pd.DataFrame(rows)
    order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
    if not out.empty:
        out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
        out = out.sort_values("state").reset_index(drop=True)
    return out


def metric_row(name: str, benchmark_returns: pd.Series, state_history: pd.DataFrame) -> dict:
    ret = roc.load_portfolio_returns(name)
    weights = roc.load_portfolio_weights(name)
    if ret is None or weights is None:
        return {"name": name, "missing": True}
    net = ret["net_return"].dropna()
    metrics = roc.metric_block(net)
    turnover = float(ret["turnover"].mean()) if "turnover" in ret.columns else float(roc.weekly_turnover(weights).mean())
    offense_cols = [c for c in weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
    defense_cols = [c for c in weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
    joined = pd.concat([net.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    state = state_history.reindex(net.index)
    recovery_mask = state["state_bucket"].isin(["recovery_confirmed", "recovery_fragile"]).reindex(net.index, fill_value=False).astype(bool)
    row = {
        "name": name,
        "missing": False,
        "ann_return": metrics["ann_return"],
        "ann_vol": metrics["ann_vol"],
        "sharpe": metrics["sharpe"],
        "max_drawdown": metrics["max_drawdown"],
        "calmar": metrics["calmar"],
        "cvar_5": metrics["cvar_5"],
        "avg_turnover": turnover,
        "avg_BIL": float(weights.get("BIL", pd.Series(0.0, index=weights.index)).mean()),
        "avg_SPY": float(weights.get("SPY", pd.Series(0.0, index=weights.index)).mean()),
        "avg_offense": float(weights.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1).mean()),
        "avg_defense": float(weights.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1).mean()),
        "holdout_sharpe": roc.sharpe(net.tail(roc.HOLDOUT_WEEKS)),
        "holdout_ann_return": roc.annualised_return(net.tail(roc.HOLDOUT_WEEKS)),
        "recovery_capture": float(
            joined.loc[recovery_mask.reindex(joined.index, fill_value=False), "portfolio"].mean()
            / joined.loc[recovery_mask.reindex(joined.index, fill_value=False), "benchmark"].mean()
        ) if recovery_mask.any() else np.nan,
    }
    return row


def state_summary_row(name: str, benchmark_returns: pd.Series, state_history: pd.DataFrame) -> pd.DataFrame:
    ret = roc.load_portfolio_returns(name)
    weights = roc.load_portfolio_weights(name)
    if ret is None or weights is None:
        return pd.DataFrame()
    net = ret["net_return"].rename("portfolio")
    joined = pd.concat(
        [
            net,
            benchmark_returns.rename("benchmark"),
            weights.get("BIL", pd.Series(0.0, index=weights.index)).rename("BIL"),
            weights.get("SPY", pd.Series(0.0, index=weights.index)).rename("SPY"),
            state_history[["state_bucket"]],
        ],
        axis=1,
    ).dropna(subset=["portfolio", "state_bucket"])
    offense_cols = [c for c in weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
    defense_cols = [c for c in weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
    joined["offense"] = weights.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1).reindex(joined.index)
    joined["defense"] = weights.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1).reindex(joined.index)
    rows = []
    for state, sub in joined.groupby("state_bucket", observed=False):
        rows.append(
            {
                "name": name,
                "state": state,
                "n_weeks": int(len(sub)),
                "ann_return": roc.annualised_return(sub["portfolio"]),
                "sharpe": roc.sharpe(sub["portfolio"]),
                "avg_BIL": float(sub["BIL"].mean()),
                "avg_SPY": float(sub["SPY"].mean()),
                "avg_offense": float(sub["offense"].mean()),
                "avg_defense": float(sub["defense"].mean()),
                "mean_weekly_return": float(sub["portfolio"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
        out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
        out = out.sort_values("state").reset_index(drop=True)
    return out


def fallback_mix_diagnostics(
    configs: dict[str, dict],
    position_maps: dict[str, dict[str, pd.DataFrame]],
    prod_sleeve_weights: pd.DataFrame,
    state_history: pd.DataFrame,
    metrics_df: pd.DataFrame,
) -> pd.DataFrame:
    base_pos = position_maps[PRODUCTION][TARGET_SLEEVE].reindex(state_history.index)
    base_sw = prod_sleeve_weights.get(TARGET_SLEEVE, pd.Series(0.0, index=prod_sleeve_weights.index)).reindex(state_history.index).fillna(0.0)
    rows = []
    favorable_mask = state_history["state_bucket"].isin(["calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"])
    for name in PHASE_PP_CANDIDATES:
        pos = position_maps[name][TARGET_SLEEVE].reindex(state_history.index)
        bil = pos.get("BIL", pd.Series(0.0, index=pos.index)).fillna(0.0)
        hidden = bil * base_sw
        cfg = configs[name]
        metric_sub = metrics_df[metrics_df["name"] == name]
        metric_row_df = metric_sub.iloc[0] if not metric_sub.empty else pd.Series(dtype=float)
        rows.append(
            {
                "name": name,
                "keep_bil_fraction": cfg["keep_bil_fraction"],
                "fallback_mix": "|".join(f"{k}:{v:.2f}" for k, v in cfg["fallback_mix"].items()),
                "avg_internal_bil_all": float(bil.mean()),
                "avg_internal_bil_favorable": float(bil.reindex(state_history.index)[favorable_mask].mean()),
                "avg_internal_bil_stressed": float(bil.reindex(state_history.index)[state_history["state_bucket"] == "stressed_panic"].mean()),
                "pct_target_25_rows_touched": float(((base_pos["BIL"].round(4) == 0.25) & (bil.round(4) != base_pos["BIL"].round(4))).mean()),
                "avg_hidden_bil_contrib": float(hidden.mean()),
                "ann_return": float(metric_row_df.get("ann_return", np.nan)),
                "sharpe": float(metric_row_df.get("sharpe", np.nan)),
                "avg_BIL_portfolio": float(metric_row_df.get("avg_BIL", np.nan)),
                "avg_SPY_portfolio": float(metric_row_df.get("avg_SPY", np.nan)),
            }
        )
    return pd.DataFrame(rows)


def candidate_diagnostics(
    state_history: pd.DataFrame,
    prod_sleeve_weights: pd.DataFrame,
    position_maps: dict[str, dict[str, pd.DataFrame]],
) -> pd.DataFrame:
    prod_positions = position_maps[PRODUCTION][TARGET_SLEEVE].reindex(state_history.index)
    prod_target_weight = prod_sleeve_weights.get(TARGET_SLEEVE, pd.Series(0.0, index=prod_sleeve_weights.index)).reindex(state_history.index).fillna(0.0)
    prod_hidden = prod_positions.get("BIL", pd.Series(0.0, index=prod_positions.index)).fillna(0.0) * prod_target_weight
    rows = []
    for name in PHASE_PP_CANDIDATES:
        sw = roc.load_portfolio_sleeve_weights(name)
        pw = roc.load_portfolio_weights(name)
        if sw is None or pw is None:
            continue
        pos = position_maps[name][TARGET_SLEEVE].reindex(state_history.index)
        bil = pos.get("BIL", pd.Series(0.0, index=pos.index)).fillna(0.0)
        target_weight = sw.get(TARGET_SLEEVE, pd.Series(0.0, index=sw.index)).reindex(state_history.index).fillna(0.0)
        hidden = bil * target_weight
        for state, idx in state_history.groupby("state_bucket", observed=False).groups.items():
            sub_idx = pd.Index(idx)
            rows.append(
                {
                    "name": name,
                    "state": state,
                    "avg_composite_internal_bil": float(bil.reindex(sub_idx).mean()),
                    "composite_bil_reduction_vs_prod": float(prod_positions.get("BIL", pd.Series(0.0, index=prod_positions.index)).reindex(sub_idx).mean() - bil.reindex(sub_idx).mean()),
                    "avg_composite_hidden_bil_contrib": float(hidden.reindex(sub_idx).mean()),
                    "composite_hidden_bil_reduction_vs_prod": float(prod_hidden.reindex(sub_idx).mean() - hidden.reindex(sub_idx).mean()),
                    "avg_composite_internal_spy": float(pos.get("SPY", pd.Series(0.0, index=pos.index)).reindex(sub_idx).mean()),
                    "avg_composite_internal_gld": float(pos.get("GLD", pd.Series(0.0, index=pos.index)).reindex(sub_idx).mean()),
                    "avg_composite_internal_tlt": float(pos.get("TLT", pd.Series(0.0, index=pos.index)).reindex(sub_idx).mean()),
                    "avg_composite_internal_lqd": float(pos.get("LQD", pd.Series(0.0, index=pos.index)).reindex(sub_idx).mean()),
                    "avg_composite_internal_hyg": float(pos.get("HYG", pd.Series(0.0, index=pos.index)).reindex(sub_idx).mean()),
                    "avg_final_portfolio_bil": float(pw.get("BIL", pd.Series(0.0, index=pw.index)).reindex(sub_idx).mean()),
                    "avg_final_portfolio_spy": float(pw.get("SPY", pd.Series(0.0, index=pw.index)).reindex(sub_idx).mean()),
                }
            )
    out = pd.DataFrame(rows)
    if not out.empty:
        order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
        out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
        out = out.sort_values(["name", "state"]).reset_index(drop=True)
    return out


def build_selection_table(metrics_df: pd.DataFrame, candidate_diag: pd.DataFrame, state_summary: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    prod = metrics_df[metrics_df["name"] == PRODUCTION].iloc[0]
    prod_states = state_summary[state_summary["name"] == PRODUCTION].set_index("state")
    rows = []
    for candidate in PHASE_PP_CANDIDATES:
        cand_df = metrics_df[metrics_df["name"] == candidate]
        if cand_df.empty:
            rows.append({"name": candidate, "passes_all_gates": False, "fail_reasons": "candidate metrics missing"})
            continue
        cand = cand_df.iloc[0]
        ann_delta_pp = (cand["ann_return"] - prod["ann_return"]) * 100.0
        sharpe_delta = cand["sharpe"] - prod["sharpe"]
        mdd_delta_pp = (cand["max_drawdown"] - prod["max_drawdown"]) * 100.0
        cvar_delta_pp = (cand["cvar_5"] - prod["cvar_5"]) * 100.0
        turn_ratio = cand["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else np.inf
        spy_delta_pp = (cand["avg_SPY"] - prod["avg_SPY"]) * 100.0
        diag_sub = candidate_diag[candidate_diag["name"] == candidate]
        avg_hidden_reduction = float(diag_sub["composite_hidden_bil_reduction_vs_prod"].mean()) if not diag_sub.empty else np.nan
        fav_hidden_reduction = float(diag_sub[diag_sub["state"].isin(["calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"])]["composite_hidden_bil_reduction_vs_prod"].mean()) if not diag_sub.empty else np.nan
        cand_states = state_summary[state_summary["name"] == candidate].set_index("state")
        sp_delta = float(cand_states.loc["stressed_panic", "mean_weekly_return"] - prod_states.loc["stressed_panic", "mean_weekly_return"]) if "stressed_panic" in cand_states.index else np.nan
        rf_delta = float(cand_states.loc["recovery_fragile", "mean_weekly_return"] - prod_states.loc["recovery_fragile", "mean_weekly_return"]) if "recovery_fragile" in cand_states.index else np.nan
        cond_ann = ann_delta_pp >= -0.30
        cond_sharpe = sharpe_delta >= 0.005
        cond_mdd = mdd_delta_pp >= -0.50
        cond_cvar = cvar_delta_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_stress = np.isnan(sp_delta) or sp_delta >= -0.0005
        cond_recovery = np.isnan(rf_delta) or rf_delta >= -0.0005
        cond_beta = not (spy_delta_pp > 2.0 and sharpe_delta < 0.005)
        cond_translation = np.isfinite(fav_hidden_reduction) and fav_hidden_reduction > 0 and (ann_delta_pp > 0 or sharpe_delta > 0)
        passes = all([cond_ann, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_stress, cond_recovery, cond_beta, cond_translation])
        fail_reasons = "; ".join(
            reason for reason in [
                f"ann_return_drag {ann_delta_pp:+.2f}pp" if not cond_ann else "",
                f"sharpe_delta {sharpe_delta:+.4f}" if not cond_sharpe else "",
                f"max_drawdown_delta {mdd_delta_pp:+.2f}pp" if not cond_mdd else "",
                f"cvar_delta {cvar_delta_pp:+.2f}pp" if not cond_cvar else "",
                f"turnover_ratio {turn_ratio:.2f}x" if not cond_turn else "",
                f"stressed_panic worse {sp_delta:+.5f}/wk" if not cond_stress else "",
                f"recovery_fragile worse {rf_delta:+.5f}/wk" if not cond_recovery else "",
                f"hidden beta {spy_delta_pp:+.2f}pp SPY" if not cond_beta else "",
                f"favorable cash reduction not translating ({fav_hidden_reduction:+.4f})" if not cond_translation else "",
            ] if reason
        ) or "none"
        rows.append(
            {
                "name": candidate,
                "ann_return_delta_pp_vs_prod": ann_delta_pp,
                "sharpe_delta_vs_prod": sharpe_delta,
                "max_drawdown_delta_pp_vs_prod": mdd_delta_pp,
                "cvar_delta_pp_vs_prod": cvar_delta_pp,
                "turnover_ratio_vs_prod": turn_ratio,
                "avg_SPY_delta_pp_vs_prod": spy_delta_pp,
                "avg_composite_hidden_bil_reduction_vs_prod": avg_hidden_reduction,
                "avg_favorable_hidden_bil_reduction_vs_prod": fav_hidden_reduction,
                "passes_all_gates": passes,
                "fail_reasons": fail_reasons,
            }
        )
    selection = pd.DataFrame(rows)
    if selection.empty:
        return selection, ""
    best = selection.sort_values(
        by=["passes_all_gates", "sharpe_delta_vs_prod", "ann_return_delta_pp_vs_prod", "avg_favorable_hidden_bil_reduction_vs_prod"],
        ascending=[False, False, False, False],
    ).iloc[0]["name"]
    return selection, str(best)


def parse_committee_verdict(candidate: str) -> tuple[str, Path]:
    report_path = roc.REPORTS_DIR / "research_committee" / f"{candidate}_audit.md"
    if not report_path.exists():
        return "NEEDS FIX BEFORE JUDGMENT", report_path
    text = report_path.read_text()
    match = re.search(r"Verdict:\s*([A-Z ]+)", text)
    if not match:
        return "NEEDS FIX BEFORE JUDGMENT", report_path
    verdict = match.group(1).strip()
    if verdict.startswith("KEEP AS PRODUCTION"):
        return "KEEP AS PRODUCTION", report_path
    if verdict.startswith("KEEP AS SHADOW"):
        return "KEEP AS SHADOW", report_path
    if verdict.startswith("REJECT"):
        return "REJECT", report_path
    return "NEEDS FIX BEFORE JUDGMENT", report_path


def genuine_improvement(selection: pd.DataFrame, candidate: str) -> bool:
    row = selection[selection["name"] == candidate]
    if row.empty:
        return False
    r = row.iloc[0]
    return bool(
        r["ann_return_delta_pp_vs_prod"] > 0
        and r["sharpe_delta_vs_prod"] > 0
        and r["avg_favorable_hidden_bil_reduction_vs_prod"] > 0
    )


def write_report(
    fallback_tier_df: pd.DataFrame,
    fallback_mix_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    state_summary: pd.DataFrame,
    candidate_diag: pd.DataFrame,
    selection: pd.DataFrame,
    best_candidate: str,
    quick_verdict: str,
    committee_report: Path,
    ran_layer56: bool,
) -> None:
    final_decision = quick_verdict if quick_verdict in {"KEEP AS PRODUCTION", "KEEP AS SHADOW", "REJECT", "NEEDS FIX BEFORE JUDGMENT"} else "DIAGNOSTIC ONLY / NO SAFE CANDIDATE"
    layer56_text = "Ran quick Layer 5/6 audits." if ran_layer56 else "Skipped Layer 5/6 quick audits."
    lines = [
        "# 2026-04-27 Phase PP — Composite Fallback Redesign\n\n",
        "## Commands Executed\n```\n",
        "python scripts/phase_pp_composite_fallback_redesign.py\n",
        *[f"{cmd}\n" for cmd in COMMAND_LOG],
        "```\n\n",
        "## Files Created / Modified\n",
        "- Script: `scripts/phase_pp_composite_fallback_redesign.py`\n",
        "- Builder variants: `scripts/build_improvement_artifacts.py`\n",
        "- Diagnostics: `data/research/phase_pp_composite_fallback_redesign/`\n",
        "- Candidate outputs: `data/05_layer3_portfolio_construction/phase_pp_*`\n",
        f"- Report: `{REPORT_PATH.relative_to(ROOT)}`\n\n",
        "## How The 25% BIL Tier Works\n",
        "- The favorable-state fallback manifests as a discrete sleeve-position tier rather than a small residual weight. In the saved sleeve outputs, the common pattern is `25% BIL` plus four non-cash holdings at roughly `18.75%` each.\n",
        "- The stressed architecture is separate: the high-defense tier is around `65% BIL` and is preserved unchanged in this phase.\n\n",
        "## Fallback Tier By State\n```\n",
        fallback_tier_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not fallback_tier_df.empty else "No fallback tier table available.",
        "\n```\n\n",
        "## Fallback Mix Candidates Tested\n```\n",
        fallback_mix_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not fallback_mix_df.empty else "No fallback mix diagnostics available.",
        "\n```\n\n",
        "## Candidate Metrics Table\n```\n",
        metrics_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not metrics_df.empty else "No metrics available.",
        "\n```\n\n",
        "## State-By-State Candidate Impact\n```\n",
        state_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not state_summary.empty else "No state summary available.",
        "\n```\n\n",
        "## Candidate Diagnostics\n```\n",
        candidate_diag.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not candidate_diag.empty else "No candidate diagnostics available.",
        "\n```\n\n",
        "## Selection Table\n```\n",
        selection.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not selection.empty else "No selection table available.",
        "\n```\n\n",
        "## Stressed-Panic Protection Check\n",
        "- The redesigns only touch rows on the favorable-state `25%` BIL tier. The `65%` stressed tier is left untouched by construction.\n",
        "- See `stressed_panic` rows in the candidate diagnostics for any spillover into final portfolio behavior.\n\n",
        "## Recovery-Fragile Protection Check\n",
        "- Recovery-fragile state performance is explicitly checked in the selection gate.\n",
        "- See `recovery_fragile` rows in the candidate diagnostics and state summary.\n\n",
        "## Best Candidate\n",
        f"- Best candidate: `{best_candidate or 'none'}`\n",
        f"- Quick committee verdict: **{quick_verdict}**\n",
        f"- Research committee report: `{committee_report.relative_to(ROOT) if committee_report.exists() else committee_report}`\n",
        f"- Layer 5/6 status: {layer56_text}\n\n",
        "## Final Decision\n",
        f"**{final_decision}**\n\n",
        "- Production pin remains unchanged.\n",
        "- Shadow pin remains unchanged.\n",
        f"- This composite fallback redesign path should {'continue' if final_decision in {'KEEP AS SHADOW', 'KEEP AS PRODUCTION'} else 'not continue in its current narrow form'}.\n",
        f"- Recommended next phase if this fails: {'deeper composite_regime_conditioned sleeve rewrite or broader defensive sleeve architecture rethink' if final_decision in {'REJECT', 'NEEDS FIX BEFORE JUDGMENT', 'DIAGNOSTIC ONLY / NO SAFE CANDIDATE'} else 'follow-on robustness validation on the best direct fallback redesign'}.\n",
    ]
    REPORT_PATH.write_text("".join(lines))


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    state_history = load_state_history()
    benchmark_returns = roc.load_weekly_returns()["SPY"]

    prod_sleeve_weights = roc.load_portfolio_sleeve_weights(PRODUCTION)
    if prod_sleeve_weights is None:
        raise RuntimeError("Production sleeve weights missing.")
    sleeves = [c for c in prod_sleeve_weights.columns if not str(c).startswith("cash::")]
    base_positions = load_base_positions(sleeves)
    position_maps, configs = candidate_position_maps(base_positions, state_history)

    fallback_tier_df = fallback_tier_by_state(base_positions[TARGET_SLEEVE].reindex(state_history.index), state_history)
    fallback_tier_df.to_csv(AUDIT_DIR / "phase_pp_fallback_tier_by_state.csv", index=False)

    build_candidates()

    metrics_rows = [metric_row(name, benchmark_returns, state_history) for name in [PRODUCTION, SHADOW] + PHASE_PP_CANDIDATES]
    metrics_df = pd.DataFrame(metrics_rows)
    metrics_df.to_csv(OUTPUT_DIR / "phase_pp_candidate_metrics_full.csv", index=False)

    fallback_mix_df = fallback_mix_diagnostics(configs, position_maps, prod_sleeve_weights, state_history, metrics_df)
    fallback_mix_df.to_csv(AUDIT_DIR / "phase_pp_fallback_mix_diagnostics.csv", index=False)

    state_frames = [state_summary_row(name, benchmark_returns, state_history) for name in [PRODUCTION, SHADOW] + PHASE_PP_CANDIDATES]
    state_summary = pd.concat(state_frames, ignore_index=True) if any(not f.empty for f in state_frames) else pd.DataFrame()
    if not state_summary.empty:
        prod_lookup = state_summary[state_summary["name"] == PRODUCTION][["state", "ann_return", "sharpe", "mean_weekly_return"]].rename(
            columns={
                "ann_return": "prod_ann_return",
                "sharpe": "prod_sharpe",
                "mean_weekly_return": "prod_mean_weekly_return",
            }
        )
        state_summary = state_summary.merge(prod_lookup, on="state", how="left")
        state_summary["ann_return_delta_vs_prod"] = state_summary["ann_return"] - state_summary["prod_ann_return"]
        state_summary["sharpe_delta_vs_prod"] = state_summary["sharpe"] - state_summary["prod_sharpe"]
    state_summary.to_csv(OUTPUT_DIR / "phase_pp_state_summary.csv", index=False)

    candidate_diag = candidate_diagnostics(state_history, prod_sleeve_weights, position_maps)
    candidate_diag.to_csv(AUDIT_DIR / "phase_pp_candidate_diagnostics.csv", index=False)

    selection, best_candidate = build_selection_table(metrics_df, candidate_diag, state_summary)
    selection.to_csv(OUTPUT_DIR / "phase_pp_selection_table.csv", index=False)

    quick_verdict = "DIAGNOSTIC ONLY / NO SAFE CANDIDATE"
    committee_report = roc.REPORTS_DIR / "research_committee" / "phase_pp_no_candidate.md"
    ran_layer56 = False
    if best_candidate:
        run_logged([sys.executable, str(ROOT / "scripts" / "research_committee_report.py"), best_candidate, "--quick"])
        quick_verdict, committee_report = parse_committee_verdict(best_candidate)
        if quick_verdict in {"KEEP AS SHADOW", "KEEP AS PRODUCTION"} and genuine_improvement(selection, best_candidate):
            run_logged([sys.executable, str(ROOT / "scripts" / "backtest_realism_audit.py"), best_candidate, "--quick"])
            run_logged([sys.executable, str(ROOT / "scripts" / "allocator_benchmark_audit.py"), best_candidate, "--quick"])
            ran_layer56 = True

    protocol = {
        "phase": "PP",
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "target_sleeve": TARGET_SLEEVE,
        "candidate_names": PHASE_PP_CANDIDATES,
        "commands_executed": ["python scripts/phase_pp_composite_fallback_redesign.py", *COMMAND_LOG],
        "diagnostic_outputs": [
            "data/research/phase_pp_composite_fallback_redesign/phase_pp_fallback_tier_by_state.csv",
            "data/research/phase_pp_composite_fallback_redesign/phase_pp_fallback_mix_diagnostics.csv",
            "data/research/phase_pp_composite_fallback_redesign/phase_pp_candidate_diagnostics.csv",
        ],
        "candidate_outputs": [
            "data/05_layer3_portfolio_construction/phase_pp_candidate_metrics_full.csv",
            "data/05_layer3_portfolio_construction/phase_pp_state_summary.csv",
            "data/05_layer3_portfolio_construction/phase_pp_selection_table.csv",
        ],
        "best_candidate": best_candidate,
        "quick_verdict": quick_verdict,
        "layer56_quick_audits_ran": ran_layer56,
    }
    (OUTPUT_DIR / "phase_pp_protocol.json").write_text(json.dumps(protocol, indent=2))

    write_report(
        fallback_tier_df,
        fallback_mix_df,
        metrics_df,
        state_summary,
        candidate_diag,
        selection,
        best_candidate,
        quick_verdict,
        committee_report,
        ran_layer56,
    )


if __name__ == "__main__":
    main()
