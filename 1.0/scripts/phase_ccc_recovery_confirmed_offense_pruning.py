"""Phase CCC — bounded recovery_confirmed offense pruning.

Starts from the live BBB3 architecture-reference shadow
(`improved_phasebbb_offense_defense_composition_combo`) and tests whether
hard-capping the weak confirmed-state offense sleeves
(`dual_momentum_topn`, `composite_selective_signals`) can close more of the
remaining recovery_confirmed gap without giving back BBB3's strong
full-window Sharpe / drawdown / CVaR profile, recovery_fragile repair,
or stressed-panic protection.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import research_ops_common as roc


PRODUCTION = roc.PRODUCTION_PIN
SHADOW = roc.SHADOW_PIN
YY_BEST = "improved_phaseyy_conservative_decomposition"
ZZ2 = "improved_phasezz_recovery_neutral_offense_rebudget"
AAA2 = "improved_phaseaaa_confirmed_offense_mix_tilt"
BBB3 = "improved_phasebbb_offense_defense_composition_combo"

CCC1 = "improved_phaseccc_confirmed_cap_css"
CCC2 = "improved_phaseccc_confirmed_cap_dual"
CCC3 = "improved_phaseccc_confirmed_cap_dual_css"
CCC4 = "improved_phaseccc_conservative_confirmed_pruning"
PHASE_CCC_CANDIDATES = [CCC1, CCC2, CCC3, CCC4]

OFFENSE_COMPONENT = "composite_regime_offense_component"
DEFENSE_COMPONENT = "composite_regime_defense_component"
CASH_COMPONENT = "composite_regime_cash_component"
OFFENSIVE_SLEEVES = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    OFFENSE_COMPONENT,
]
DEFENSIVE_SLEEVES = ["taa_10m_sma", DEFENSE_COMPONENT]
RAW_SLEEVE_SET = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_selective_signals",
    "taa_10m_sma",
    "composite_regime_conditioned",
]
TOP_ETFS = ["SPY", "QQQ", "IWM", "GLD", "TLT", "HYG", "LQD", "IEF", "SHY", "BIL"]

OUT_DATA = roc.ROOT / "data" / "research" / "phase_ccc_recovery_confirmed_offense_pruning"
OUT_DATA.mkdir(parents=True, exist_ok=True)
LAYER2A = roc.ROOT / "data" / "03_layer2a_strategy_logic"
DEFAULT_COST_BPS = 10
CASH_PROXY = "BIL"


def normalize_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.index = pd.to_datetime(out.index).tz_localize(None)
    out.index.name = None
    return out.sort_index()


def run_production_path() -> None:
    targets = [PRODUCTION, SHADOW, YY_BEST, ZZ2, AAA2, BBB3] + PHASE_CCC_CANDIDATES
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(targets)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    print(f"[Phase CCC] invoking build_improvement_artifacts.py with BUILD_VERSION_NAMES={env['BUILD_VERSION_NAMES']}")
    cmd = [sys.executable, str(roc.ROOT / "scripts" / "build_improvement_artifacts.py")]
    res = subprocess.run(cmd, env=env, cwd=str(roc.ROOT), capture_output=True, text=True, timeout=2400)
    print("--- subprocess stdout (last 25 lines) ---")
    for line in (res.stdout or "").splitlines()[-25:]:
        print(line)
    if res.returncode != 0:
        print("--- subprocess stderr (last 50 lines) ---")
        for line in (res.stderr or "").splitlines()[-50:]:
            print(line)
        raise RuntimeError(f"build_improvement_artifacts.py exited with code {res.returncode}")


def load_state() -> pd.DataFrame:
    return roc.load_market_state(refined=False)


def load_returns_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return normalize_index(df)


def load_positions_csv(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    return normalize_index(df).fillna(0.0)


def compute_strategy_path(
    weights: pd.DataFrame,
    next_week_returns: pd.DataFrame,
    *,
    transaction_cost_bps: float = DEFAULT_COST_BPS,
    cash_proxy_returns: pd.Series | None = None,
) -> pd.DataFrame:
    weights = weights.reindex(index=next_week_returns.index, columns=next_week_returns.columns).fillna(0.0)
    gross_return = (weights * next_week_returns).sum(axis=1)
    if cash_proxy_returns is not None:
        cash_proxy_returns = pd.Series(cash_proxy_returns).reindex(weights.index).fillna(0.0)
        long_only_like = weights.ge(-1e-12).all(axis=1)
        residual_cash_weight = (1.0 - weights.clip(lower=0.0).sum(axis=1)).clip(lower=0.0)
        gross_return = gross_return + residual_cash_weight.where(long_only_like, 0.0) * cash_proxy_returns
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover) > 0:
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * (transaction_cost_bps / 10000.0)
    net_return = gross_return - cost
    wealth = (1.0 + net_return.fillna(0.0)).cumprod()
    running_peak = wealth.cummax()
    drawdown = wealth.div(running_peak) - 1.0
    return pd.DataFrame(
        {
            "gross_return": gross_return,
            "net_return": net_return,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": drawdown,
        }
    )


def build_component_streams() -> tuple[dict[str, pd.Series], dict[str, pd.DataFrame]]:
    next_week_returns = normalize_index(roc.load_weekly_returns())
    cash_proxy_returns = next_week_returns.get(CASH_PROXY, pd.Series(0.0, index=next_week_returns.index)).fillna(0.0)

    returns_map: dict[str, pd.Series] = {}
    positions_map: dict[str, pd.DataFrame] = {}
    for sleeve in RAW_SLEEVE_SET:
        r_path = LAYER2A / f"strategy_returns_{sleeve}.csv"
        p_path = LAYER2A / f"strategy_positions_{sleeve}.csv"
        ret = load_returns_csv(r_path)
        pos = load_positions_csv(p_path)
        if ret is None or pos is None:
            continue
        returns_map[sleeve] = ret["net_return"].reindex(next_week_returns.index).fillna(0.0)
        positions_map[sleeve] = pos.reindex(index=next_week_returns.index, columns=next_week_returns.columns).fillna(0.0)

    source = positions_map.get("composite_regime_conditioned")
    if source is not None:
        offense_cols = [
            c for c in ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"]
            if c in next_week_returns.columns
        ]
        defense_cols = [c for c in ["HYG", "LQD", "GLD", "TLT"] if c in next_week_returns.columns]
        component_specs = {
            OFFENSE_COMPONENT: offense_cols,
            DEFENSE_COMPONENT: defense_cols,
        }
        for sleeve_name, cols in component_specs.items():
            component_positions = pd.DataFrame(0.0, index=source.index, columns=source.columns)
            component_sum = source.reindex(columns=cols).sum(axis=1)
            active_mask = component_sum > 1e-12
            if cols:
                component_positions.loc[active_mask, cols] = source.loc[active_mask, cols].div(component_sum.loc[active_mask], axis=0)
            component_positions.loc[~active_mask, CASH_PROXY] = 1.0
            path = compute_strategy_path(
                component_positions,
                next_week_returns,
                transaction_cost_bps=DEFAULT_COST_BPS,
                cash_proxy_returns=cash_proxy_returns,
            )
            returns_map[sleeve_name] = path["net_return"].fillna(0.0)
            positions_map[sleeve_name] = component_positions

        cash_positions = pd.DataFrame(0.0, index=source.index, columns=source.columns)
        cash_positions[CASH_PROXY] = 1.0
        cash_path = compute_strategy_path(
            cash_positions,
            next_week_returns,
            transaction_cost_bps=DEFAULT_COST_BPS,
            cash_proxy_returns=cash_proxy_returns,
        )
        returns_map[CASH_COMPONENT] = cash_path["net_return"].fillna(0.0)
        positions_map[CASH_COMPONENT] = cash_positions

    cash_positions = pd.DataFrame(0.0, index=next_week_returns.index, columns=next_week_returns.columns)
    cash_positions[CASH_PROXY] = 1.0
    positions_map["cash::BIL"] = cash_positions
    returns_map["cash::BIL"] = cash_proxy_returns.reindex(next_week_returns.index).fillna(0.0)
    return returns_map, positions_map


def headline(name: str) -> dict:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return {"name": name}
    ret = normalize_index(ret)
    w = roc.load_portfolio_weights(name)
    sw = roc.load_portfolio_sleeve_weights(name)
    if w is not None:
        w = normalize_index(w)
    if sw is not None:
        sw = normalize_index(sw)

    net = ret["net_return"].dropna()
    full_m = roc.metric_block(net)
    hold_m = roc.metric_block(net.tail(roc.HOLDOUT_WEEKS))
    out = {
        "name": name,
        "full_ann_return": full_m["ann_return"],
        "full_ann_vol": full_m["ann_vol"],
        "full_sharpe": full_m["sharpe"],
        "full_max_drawdown": full_m["max_drawdown"],
        "full_cvar_5": full_m["cvar_5"],
        "full_calmar": full_m["calmar"],
        "holdout_ann_return": hold_m["ann_return"],
        "holdout_sharpe": hold_m["sharpe"],
        "holdout_max_drawdown": hold_m["max_drawdown"],
    }
    if w is not None:
        out["avg_BIL"] = float(w["BIL"].mean()) if "BIL" in w.columns else float("nan")
        out["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else float("nan")
        out["avg_turnover"] = float(w.diff().abs().sum(axis=1).fillna(0.0).mean())
    if sw is not None:
        off = [c for c in OFFENSIVE_SLEEVES if c in sw.columns]
        defe = [c for c in DEFENSIVE_SLEEVES if c in sw.columns]
        cash_cols = [c for c in sw.columns if c.startswith("cash::")]
        out["avg_offensive_sleeve"] = float(sw[off].sum(axis=1).mean()) if off else float("nan")
        out["avg_defensive_sleeve"] = float(sw[defe].sum(axis=1).mean()) if defe else float("nan")
        out["avg_explicit_cash_sleeve"] = float(sw[cash_cols].sum(axis=1).mean()) if cash_cols else float("nan")
        out["avg_explicit_defense_exposure"] = out["avg_defensive_sleeve"]
        out["avg_composite_component_total"] = float(sw[[c for c in [OFFENSE_COMPONENT, DEFENSE_COMPONENT] if c in sw.columns]].sum(axis=1).mean()) if any(c in sw.columns for c in [OFFENSE_COMPONENT, DEFENSE_COMPONENT]) else float("nan")
        for col in [OFFENSE_COMPONENT, DEFENSE_COMPONENT, CASH_COMPONENT]:
            out[f"avg_{col}"] = float(sw[col].mean()) if col in sw.columns else float("nan")
    if "turnover" in ret.columns and pd.isna(out.get("avg_turnover", float("nan"))):
        out["avg_turnover"] = float(ret["turnover"].mean())
    return out


def state_metrics(name: str, state: pd.DataFrame) -> dict:
    ret = roc.load_portfolio_returns(name)
    if ret is None:
        return {}
    ret = normalize_index(ret)
    df = ret[["net_return"]].join(state[["market_state"]], how="inner").dropna()
    out: dict[str, dict] = {}
    for s, sub in df.groupby("market_state"):
        n = sub["net_return"]
        out[s] = {
            "ann_return": roc.annualised_return(n),
            "sharpe": roc.sharpe(n),
            "n_weeks": int(len(sub)),
        }
    return out


def state_weights(name: str, state: pd.DataFrame) -> pd.DataFrame:
    sw = roc.load_portfolio_sleeve_weights(name)
    if sw is None:
        return pd.DataFrame()
    sw = normalize_index(sw)
    joined = sw.join(state[["market_state"]], how="inner").dropna(subset=["market_state"])
    rows = []
    cols = [
        OFFENSE_COMPONENT,
        DEFENSE_COMPONENT,
        CASH_COMPONENT,
        "dual_momentum_topn",
        "cta_trend_long_only",
        "composite_selective_signals",
        "taa_10m_sma",
        "composite_regime_conditioned",
        "cash::BIL",
    ]
    for s, sub in joined.groupby("market_state"):
        row = {"version": name, "state": s, "n_weeks": int(len(sub))}
        for col in cols:
            row[f"avg_{col}"] = float(sub[col].mean()) if col in sub.columns else float("nan")
        off = [c for c in OFFENSIVE_SLEEVES if c in sub.columns]
        defe = [c for c in DEFENSIVE_SLEEVES if c in sub.columns]
        cash_cols = [c for c in sub.columns if c.startswith("cash::")]
        row["avg_offensive_total"] = float(sub[off].sum(axis=1).mean()) if off else float("nan")
        row["avg_defensive_total"] = float(sub[defe].sum(axis=1).mean()) if defe else float("nan")
        row["avg_explicit_cash"] = float(sub[cash_cols].sum(axis=1).mean()) if cash_cols else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def build_sleeve_contribution_table(
    versions: list[str],
    state_df: pd.DataFrame,
    returns_map: dict[str, pd.Series],
    positions_map: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    rows = []
    for version in versions:
        sw = roc.load_portfolio_sleeve_weights(version)
        if sw is None:
            continue
        sw = normalize_index(sw)
        joined = sw.join(state_df[["market_state"]], how="inner").dropna(subset=["market_state"])
        for state_name in ["recovery_confirmed", "recovery_fragile", "stressed_panic"]:
            sub = joined[joined["market_state"] == state_name]
            if sub.empty:
                continue
            sleeves = [c for c in sw.columns if c != "market_state"]
            for sleeve in sleeves:
                if sleeve not in returns_map:
                    continue
                sleeve_weight = sub[sleeve].astype(float)
                sleeve_ret = returns_map[sleeve].reindex(sub.index).fillna(0.0)
                contrib = sleeve_weight * sleeve_ret
                pos = positions_map.get(sleeve)
                eff = None
                if pos is not None:
                    eff = pos.reindex(index=sub.index, columns=pos.columns).fillna(0.0).mul(sleeve_weight, axis=0)
                bucket = (
                    "offense" if sleeve in OFFENSIVE_SLEEVES else
                    "defense" if sleeve in DEFENSIVE_SLEEVES else
                    "cash" if sleeve.startswith("cash::") or sleeve == CASH_COMPONENT else
                    "composite" if sleeve == "composite_regime_conditioned" else
                    "other"
                )
                row = {
                    "version": version,
                    "state": state_name,
                    "sleeve": sleeve,
                    "bucket": bucket,
                    "n_weeks": int(len(sub)),
                    "avg_sleeve_weight": float(sleeve_weight.mean()),
                    "standalone_ann_return": roc.annualised_return(sleeve_ret),
                    "standalone_sharpe": roc.sharpe(sleeve_ret),
                    "ann_contribution_mean": float(contrib.mean() * roc.WEEKS_PER_YEAR),
                    "cumulative_contribution": float((1.0 + contrib).prod() - 1.0),
                }
                if eff is not None:
                    for tic in TOP_ETFS:
                        if tic in eff.columns:
                            row[f"avg_{tic}_exposure"] = float(eff[tic].mean())
                rows.append(row)
    return pd.DataFrame(rows)


def build_pruning_diagnostics(contrib_df: pd.DataFrame, weights_df: pd.DataFrame) -> pd.DataFrame:
    rc = contrib_df[(contrib_df["state"] == "recovery_confirmed") & (contrib_df["bucket"] == "offense")].copy()
    if rc.empty:
        return rc
    rank_map = (
        rc.groupby("sleeve")[["standalone_ann_return", "standalone_sharpe"]]
        .mean()
        .sort_values(["standalone_sharpe", "standalone_ann_return"], ascending=[False, False])
    )
    rank_lookup = {sleeve: i + 1 for i, sleeve in enumerate(rank_map.index.tolist())}
    comp_off_ret = float(rank_map.loc[OFFENSE_COMPONENT, "standalone_ann_return"]) if OFFENSE_COMPONENT in rank_map.index else np.nan
    cta_ret = float(rank_map.loc["cta_trend_long_only", "standalone_ann_return"]) if "cta_trend_long_only" in rank_map.index else np.nan

    rc["offense_quality_rank"] = rc["sleeve"].map(rank_lookup)
    rc["is_weak_confirmed_sleeve"] = rc["sleeve"].isin(["dual_momentum_topn", "composite_selective_signals"])
    rc["uplift_if_shift_1pp_to_comp_off_ann_pp"] = (comp_off_ret - rc["standalone_ann_return"]) * 1.0
    rc["uplift_if_shift_1pp_to_cta_ann_pp"] = (cta_ret - rc["standalone_ann_return"]) * 1.0

    rf = contrib_df[(contrib_df["state"] == "recovery_fragile") & (contrib_df["bucket"] == "offense")][
        ["version", "sleeve", "standalone_ann_return", "standalone_sharpe", "ann_contribution_mean"]
    ].rename(
        columns={
            "standalone_ann_return": "recovery_fragile_standalone_ann_return",
            "standalone_sharpe": "recovery_fragile_standalone_sharpe",
            "ann_contribution_mean": "recovery_fragile_ann_contribution_mean",
        }
    )
    diag = rc.merge(rf, on=["version", "sleeve"], how="left")

    weight_view = weights_df[weights_df["state"] == "recovery_confirmed"].copy()
    for sleeve in ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", OFFENSE_COMPONENT]:
        col = f"avg_{sleeve}"
        if col not in weight_view.columns:
            weight_view[col] = np.nan
    weight_view = weight_view[
        [
            "version",
            "avg_offensive_total",
            "avg_dual_momentum_topn",
            "avg_cta_trend_long_only",
            "avg_composite_selective_signals",
            f"avg_{OFFENSE_COMPONENT}",
        ]
    ]
    diag = diag.merge(weight_view, on="version", how="left")
    diag["recovery_confirmed_dual_share_of_offense"] = diag["avg_dual_momentum_topn"] / diag["avg_offensive_total"]
    diag["recovery_confirmed_css_share_of_offense"] = diag["avg_composite_selective_signals"] / diag["avg_offensive_total"]
    return diag.sort_values(["version", "offense_quality_rank", "avg_sleeve_weight"], ascending=[True, True, False])


def evaluate(summary: pd.DataFrame, all_state_metrics: dict[str, dict]) -> tuple[str, str, list[dict]]:
    cands = summary[summary["name"].isin(PHASE_CCC_CANDIDATES)].copy()
    prod = summary[summary["name"] == PRODUCTION].iloc[0].to_dict()
    aaa2 = summary[summary["name"] == AAA2].iloc[0].to_dict()
    bbb3 = summary[summary["name"] == BBB3].iloc[0].to_dict()
    yy = summary[summary["name"] == YY_BEST].iloc[0].to_dict()
    zz2 = summary[summary["name"] == ZZ2].iloc[0].to_dict()
    shadow = summary[summary["name"] == SHADOW]
    shadow_d = shadow.iloc[0].to_dict() if not shadow.empty else {}
    prod_state = all_state_metrics.get(PRODUCTION, {})
    bbb3_state = all_state_metrics.get(BBB3, {})
    rows = []

    for _, r in cands.iterrows():
        name = r["name"]
        cand_state = all_state_metrics.get(name, {})

        ann_imp_pp = (r["full_ann_return"] - prod["full_ann_return"]) * 100
        sharpe_imp = r["full_sharpe"] - prod["full_sharpe"]
        ann_vs_bbb3 = (r["full_ann_return"] - bbb3["full_ann_return"]) * 100
        sharpe_vs_bbb3 = r["full_sharpe"] - bbb3["full_sharpe"]
        sharpe_vs_aaa2 = r["full_sharpe"] - aaa2["full_sharpe"]
        sharpe_vs_yy = r["full_sharpe"] - yy["full_sharpe"]
        sharpe_vs_zz2 = r["full_sharpe"] - zz2["full_sharpe"]
        sharpe_vs_shadow = r["full_sharpe"] - shadow_d.get("full_sharpe", float("nan"))
        mdd_imp_pp = (r["full_max_drawdown"] - prod["full_max_drawdown"]) * 100
        cvar_imp_pp = (r["full_cvar_5"] - prod["full_cvar_5"]) * 100
        turn_ratio = r["avg_turnover"] / prod["avg_turnover"] if prod.get("avg_turnover", 0.0) > 0 else float("inf")
        spy_inc_pp = (r["avg_SPY"] - prod["avg_SPY"]) * 100
        bil_inc_pp = (r["avg_BIL"] - prod["avg_BIL"]) * 100

        def state_delta(ref_metrics: dict[str, dict], state_name: str) -> tuple[float, float]:
            cand = cand_state.get(state_name, {})
            ref = ref_metrics.get(state_name, {})
            ann = (cand.get("ann_return", float("nan")) - ref.get("ann_return", float("nan"))) * 100
            sh = cand.get("sharpe", float("nan")) - ref.get("sharpe", float("nan"))
            return ann, sh

        rc_ann, rc_sh = state_delta(prod_state, "recovery_confirmed")
        rf_ann, rf_sh = state_delta(prod_state, "recovery_fragile")
        sp_ann, sp_sh = state_delta(prod_state, "stressed_panic")
        rc_ann_vs_bbb3, rc_sh_vs_bbb3 = state_delta(bbb3_state, "recovery_confirmed")
        rf_ann_vs_bbb3, rf_sh_vs_bbb3 = state_delta(bbb3_state, "recovery_fragile")
        sp_ann_vs_bbb3, sp_sh_vs_bbb3 = state_delta(bbb3_state, "stressed_panic")

        cand_sw = roc.load_portfolio_sleeve_weights(name)
        cand_sw = normalize_index(cand_sw) if cand_sw is not None else None
        decomposition_intact = bool(
            cand_sw is not None
            and "composite_regime_conditioned" not in cand_sw.columns
            and OFFENSE_COMPONENT in cand_sw.columns
            and DEFENSE_COMPONENT in cand_sw.columns
            and any(c.startswith("cash::") for c in cand_sw.columns)
        )

        cond_drag = ann_imp_pp >= -0.30
        cond_sharpe = sharpe_imp >= 0.005
        cond_sharpe_vs_bbb3 = sharpe_vs_bbb3 >= -0.0025
        cond_mdd = mdd_imp_pp >= -0.5
        cond_cvar = cvar_imp_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_sp = (np.isnan(sp_ann) or sp_ann >= -0.30) and (np.isnan(sp_sh) or sp_sh >= -0.05)
        cond_rf = (np.isnan(rf_ann_vs_bbb3) or rf_ann_vs_bbb3 >= -0.10) and (np.isnan(rf_sh_vs_bbb3) or rf_sh_vs_bbb3 >= -0.05)
        cond_rc_repair = (not np.isnan(rc_ann_vs_bbb3)) and (rc_ann_vs_bbb3 > 0.0)
        cond_hidden_beta = not (spy_inc_pp > 0.75 and sharpe_imp < 0.01)
        cond_decomposition = decomposition_intact

        passes_strict = all([
            cond_drag,
            cond_sharpe,
            cond_sharpe_vs_bbb3,
            cond_mdd,
            cond_cvar,
            cond_turn,
            cond_sp,
            cond_rf,
            cond_rc_repair,
            cond_hidden_beta,
            cond_decomposition,
        ])

        challenger_track = all([
            sharpe_imp >= 0.020,
            mdd_imp_pp >= -0.10,
            cvar_imp_pp >= -0.02,
            (np.isnan(rc_ann) or rc_ann >= -0.30),
            (np.isnan(rf_ann_vs_bbb3) or rf_ann_vs_bbb3 >= -0.05),
            cond_hidden_beta,
            cond_decomposition,
        ])

        shadow_track = all([
            sharpe_imp > 0.0,
            ann_imp_pp >= -0.30,
            cond_sp,
            cond_rf,
            cond_hidden_beta,
            cond_decomposition,
            cond_rc_repair,
        ])

        fail = "; ".join(filter(None, [
            f"drag>0.30pp ({-ann_imp_pp:+.2f}pp)" if not cond_drag else "",
            f"sharpe_imp<0.005 ({sharpe_imp:+.4f})" if not cond_sharpe else "",
            f"sharpe materially worse than BBB3 ({sharpe_vs_bbb3:+.4f})" if not cond_sharpe_vs_bbb3 else "",
            f"mdd_worse>0.5pp ({mdd_imp_pp:+.2f}pp)" if not cond_mdd else "",
            f"cvar_worse>0.05pp ({cvar_imp_pp:+.2f}pp)" if not cond_cvar else "",
            f"turnover>1.10x ({turn_ratio:.2f}x)" if not cond_turn else "",
            f"stressed_panic worse ({sp_ann:+.2f}pp ann / {sp_sh:+.3f} sharpe)" if not cond_sp else "",
            f"recovery_fragile worse vs BBB3 ({rf_ann_vs_bbb3:+.2f}pp ann / {rf_sh_vs_bbb3:+.3f} sharpe)" if not cond_rf else "",
            f"recovery_confirmed not improved vs BBB3 ({rc_ann_vs_bbb3:+.2f}pp ann)" if not cond_rc_repair else "",
            f"hidden beta SPY +{spy_inc_pp:+.2f}pp" if not cond_hidden_beta else "",
            "decomposition no longer reduces hidden cash/defense duplication" if not cond_decomposition else "",
        ])) or "none"

        rows.append({
            "name": name,
            "ann_imp_pp_vs_prod": ann_imp_pp,
            "sharpe_imp_vs_prod": sharpe_imp,
            "ann_imp_pp_vs_bbb3": ann_vs_bbb3,
            "sharpe_vs_bbb3": sharpe_vs_bbb3,
            "sharpe_vs_aaa2": sharpe_vs_aaa2,
            "sharpe_vs_yy": sharpe_vs_yy,
            "sharpe_vs_zz2": sharpe_vs_zz2,
            "sharpe_vs_shadow": sharpe_vs_shadow,
            "mdd_imp_pp_vs_prod": mdd_imp_pp,
            "cvar_imp_pp_vs_prod": cvar_imp_pp,
            "turnover_ratio_vs_prod": turn_ratio,
            "spy_inc_pp_vs_prod": spy_inc_pp,
            "bil_inc_pp_vs_prod": bil_inc_pp,
            "stressed_panic_ann_delta_pp_vs_prod": sp_ann,
            "stressed_panic_sharpe_delta_vs_prod": sp_sh,
            "stressed_panic_ann_delta_pp_vs_bbb3": sp_ann_vs_bbb3,
            "recovery_confirmed_ann_delta_pp_vs_prod": rc_ann,
            "recovery_confirmed_sharpe_delta_vs_prod": rc_sh,
            "recovery_confirmed_ann_delta_pp_vs_bbb3": rc_ann_vs_bbb3,
            "recovery_confirmed_sharpe_delta_vs_bbb3": rc_sh_vs_bbb3,
            "recovery_fragile_ann_delta_pp_vs_prod": rf_ann,
            "recovery_fragile_sharpe_delta_vs_prod": rf_sh,
            "recovery_fragile_ann_delta_pp_vs_bbb3": rf_ann_vs_bbb3,
            "recovery_fragile_sharpe_delta_vs_bbb3": rf_sh_vs_bbb3,
            "decomposition_reduction_intact": decomposition_intact,
            "passes_strict_gates": passes_strict,
            "passes_challenger_track": challenger_track,
            "passes_shadow_track": shadow_track,
            "fail_reasons_strict": fail,
        })

    decision = pd.DataFrame(rows)
    challenger = decision[decision["passes_challenger_track"]]
    if not challenger.empty:
        best = challenger.sort_values(
            ["recovery_confirmed_ann_delta_pp_vs_bbb3", "sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"],
            ascending=[False, False, False],
        ).iloc[0]
        return best["name"], f"PRODUCTION CHALLENGER PENDING HUMAN REVIEW: {best['name']}", decision.to_dict("records")
    strict = decision[decision["passes_strict_gates"]]
    if not strict.empty:
        best = strict.sort_values(
            ["recovery_confirmed_ann_delta_pp_vs_bbb3", "sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"],
            ascending=[False, False, False],
        ).iloc[0]
        return best["name"], f"Selected {best['name']} (strict CCC gates passed).", decision.to_dict("records")
    shadow = decision[decision["passes_shadow_track"]]
    if not shadow.empty:
        best = shadow.sort_values(
            ["recovery_confirmed_ann_delta_pp_vs_bbb3", "sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"],
            ascending=[False, False, False],
        ).iloc[0]
        return best["name"], f"Selected {best['name']} as KEEP AS SHADOW: improves vs production while partially repairing recovery_confirmed vs BBB3.", decision.to_dict("records")
    least = decision.sort_values(
        ["recovery_confirmed_ann_delta_pp_vs_bbb3", "sharpe_imp_vs_prod", "ann_imp_pp_vs_prod"],
        ascending=[False, False, False],
    ).iloc[0]
    return "", f"NO Phase CCC candidate passes any track. Best diagnostic: {least['name']}; failure reasons: {least['fail_reasons_strict']}.", decision.to_dict("records")


def main() -> str:
    if "--no-rebuild" not in sys.argv:
        run_production_path()
    else:
        print("--no-rebuild: using existing files")

    state = load_state()
    returns_map, positions_map = build_component_streams()

    print("[Phase CCC Part A] recovery_confirmed offense-pruning diagnostics...")
    versions = [PRODUCTION, SHADOW, YY_BEST, ZZ2, AAA2, BBB3] + PHASE_CCC_CANDIDATES
    weights_rows = []
    for name in versions:
        sw = state_weights(name, state)
        if not sw.empty:
            weights_rows.append(sw)
    weights_df = pd.concat(weights_rows, ignore_index=True) if weights_rows else pd.DataFrame()

    contrib_df = build_sleeve_contribution_table(versions, state, returns_map, positions_map)
    pruning_diag = build_pruning_diagnostics(contrib_df, weights_df)
    pruning_diag.to_csv(OUT_DATA / "phase_ccc_recovery_confirmed_pruning_diagnostics.csv", index=False)
    contrib_df.to_csv(OUT_DATA / "phase_ccc_recovery_confirmed_sleeve_contribution.csv", index=False)

    summary_rows = []
    for name in versions:
        h = headline(name)
        if h:
            summary_rows.append(h)
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(roc.LAYER3_DIR / "phase_ccc_candidate_metrics_full.csv", index=False)

    all_state_metrics = {name: state_metrics(name, state) for name in versions}

    prod_ret = normalize_index(roc.load_portfolio_returns(PRODUCTION))
    bbb3_ret = normalize_index(roc.load_portfolio_returns(BBB3))
    state_rows = []
    for name in PHASE_CCC_CANDIDATES:
        ret = roc.load_portfolio_returns(name)
        if ret is None:
            continue
        ret = normalize_index(ret)
        df = pd.concat(
            [
                ret["net_return"].rename("ccc"),
                prod_ret["net_return"].rename("prod"),
                bbb3_ret["net_return"].rename("bbb3"),
            ],
            axis=1,
        ).join(state[["market_state"]], how="inner").dropna()
        for s, sub in df.groupby("market_state"):
            state_rows.append(
                {
                    "candidate": name,
                    "state": s,
                    "n_weeks": int(len(sub)),
                    "ccc_mean_wkly": float(sub["ccc"].mean()),
                    "prod_mean_wkly": float(sub["prod"].mean()),
                    "bbb3_mean_wkly": float(sub["bbb3"].mean()),
                    "delta_vs_prod_mean_wkly": float(sub["ccc"].mean() - sub["prod"].mean()),
                    "delta_vs_bbb3_mean_wkly": float(sub["ccc"].mean() - sub["bbb3"].mean()),
                    "ccc_minus_prod_cumulative": float(((1.0 + sub["ccc"]).prod() - 1.0) - ((1.0 + sub["prod"]).prod() - 1.0)),
                    "ccc_minus_bbb3_cumulative": float(((1.0 + sub["ccc"]).prod() - 1.0) - ((1.0 + sub["bbb3"]).prod() - 1.0)),
                }
            )
    state_summary = pd.DataFrame(state_rows)
    state_summary.to_csv(roc.LAYER3_DIR / "phase_ccc_state_summary.csv", index=False)

    best, rationale, recs = evaluate(summary, all_state_metrics)
    pd.DataFrame([{"best_candidate": best, "rationale": rationale}] + recs).to_csv(
        roc.LAYER3_DIR / "phase_ccc_selection_table.csv", index=False
    )
    pd.DataFrame(recs).to_csv(OUT_DATA / "phase_ccc_candidate_diagnostics.csv", index=False)

    print("\n=== Phase CCC candidate summary ===")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase CCC recovery_confirmed pruning diagnostics ===")
    view_cols = [
        "version",
        "sleeve",
        "avg_sleeve_weight",
        "standalone_ann_return",
        "standalone_sharpe",
        "ann_contribution_mean",
        "offense_quality_rank",
        "is_weak_confirmed_sleeve",
        "recovery_confirmed_dual_share_of_offense",
        "recovery_confirmed_css_share_of_offense",
        "uplift_if_shift_1pp_to_comp_off_ann_pp",
        "uplift_if_shift_1pp_to_cta_ann_pp",
    ]
    print(pruning_diag[pruning_diag["state"] == "recovery_confirmed"][view_cols].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("\n=== Phase CCC selection ===")
    print(pd.DataFrame(recs).to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print(f"\n{rationale}")

    protocol = {
        "phase": "Phase CCC — bounded recovery_confirmed offense pruning",
        "candidates": PHASE_CCC_CANDIDATES,
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "yy_reference": YY_BEST,
        "zz2_reference": ZZ2,
        "aaa2_reference": AAA2,
        "bbb3_reference": BBB3,
        "best_candidate": best,
        "rationale": rationale,
    }
    (roc.LAYER3_DIR / "phase_ccc_protocol.json").write_text(json.dumps(protocol, indent=2))
    print("\nSaved Phase CCC artifacts.")
    return best


if __name__ == "__main__":
    main()
