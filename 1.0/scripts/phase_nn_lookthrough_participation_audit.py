"""Phase NN — sleeve-to-ETF lookthrough participation audit.

Focus:
1. Measure hidden BIL / cash introduced during sleeve-to-ETF translation.
2. Attribute that drag by state and by sleeve.
3. Test up to three narrow in-pipeline fixes using the existing production
   construction path.
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
PHASE_NN_CANDIDATES = [
    "improved_phasenn_recovery_lookthrough_relief",
    "improved_phasenn_neutral_lookthrough_relief",
    "improved_phasenn_mm_plus_lookthrough_relief",
]
AUDIT_DIR = ROOT / "data" / "research" / "phase_nn_lookthrough_participation"
CHECKPOINT_DIR = ROOT / "data" / "research" / "allocator_checkpoints"
REPORT_PATH = ROOT / "docs" / "research" / "2026-04-27_phase_nn_lookthrough_participation_report.md"
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


def ensure_production_checkpoints() -> list[str]:
    required = [
        CHECKPOINT_DIR / f"{PRODUCTION}__final_sleeve_weights.csv",
        CHECKPOINT_DIR / f"{PRODUCTION}__final_etf_weights.csv",
    ]
    if all(path.exists() for path in required):
        return [str(path.relative_to(ROOT)) for path in required]
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = PRODUCTION
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    run_logged([sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")], env=env)
    return [str(path.relative_to(ROOT)) for path in required if path.exists()]


def build_candidates() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join([PRODUCTION, SHADOW] + PHASE_NN_CANDIDATES)
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


def load_base_positions(sleeves: list[str]) -> dict[str, pd.DataFrame]:
    positions: dict[str, pd.DataFrame] = {}
    for sleeve in sleeves:
        path = ROOT / "data" / "03_layer2a_strategy_logic" / f"strategy_positions_{sleeve}.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        positions[sleeve] = df
    return positions


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
            state_name = str(state_row.get("market_state") or "")
            redeploy_fraction = 0.0
            if bool(state_row.get("strong_neutral", False)):
                redeploy_fraction = strong_neutral_fraction
            else:
                redeploy_fraction = float(redeploy_config.get(state_name, 0.0))
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


def candidate_position_maps(base_positions: dict[str, pd.DataFrame], state_history: pd.DataFrame) -> dict[str, dict[str, pd.DataFrame]]:
    return {
        PRODUCTION: base_positions,
        SHADOW: base_positions,
        "improved_phasenn_recovery_lookthrough_relief": apply_internal_redeploy(
            base_positions,
            state_history,
            target_sleeves=["composite_regime_conditioned", "dual_momentum_topn"],
            redeploy_config={"recovery_fragile": 0.20, "recovery_confirmed": 0.18},
            strong_neutral_fraction=0.0,
        ),
        "improved_phasenn_neutral_lookthrough_relief": apply_internal_redeploy(
            base_positions,
            state_history,
            target_sleeves=["composite_regime_conditioned"],
            redeploy_config={},
            strong_neutral_fraction=0.12,
        ),
        "improved_phasenn_mm_plus_lookthrough_relief": apply_internal_redeploy(
            base_positions,
            state_history,
            target_sleeves=["composite_regime_conditioned", "dual_momentum_topn"],
            redeploy_config={"recovery_fragile": 0.18, "recovery_confirmed": 0.15},
            strong_neutral_fraction=0.0,
        ),
    }


def offensive_etf_weight(row: pd.Series) -> float:
    offensive_cols = [c for c in row.index if c not in DEFENSIVE_ETFS.union({"BIL"})]
    return float(row.reindex(offensive_cols).fillna(0.0).sum())


def defensive_etf_weight(row: pd.Series) -> float:
    defensive_cols = [c for c in row.index if c in DEFENSIVE_ETFS]
    return float(row.reindex(defensive_cols).fillna(0.0).sum())


def compute_lookthrough_state_drag(
    version_name: str,
    sleeve_weights: pd.DataFrame,
    etf_weights: pd.DataFrame,
    positions_map: dict[str, pd.DataFrame],
    state_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    sleeves = [c for c in sleeve_weights.columns if not str(c).startswith("cash::")]
    joined_rows = []
    sleeve_rows = []
    common_index = sleeve_weights.index.intersection(etf_weights.index).intersection(state_history.index)
    for date in common_index:
        sleeve_row = sleeve_weights.loc[date]
        etf_row = etf_weights.loc[date]
        state_row = state_history.loc[date]
        hidden_bil_total = 0.0
        offensive_from_sleeves = 0.0
        spy_from_sleeves = 0.0
        defensive_from_sleeves = 0.0
        for sleeve in sleeves:
            sw = float(sleeve_row.get(sleeve, 0.0) or 0.0)
            pos = positions_map.get(sleeve)
            pos_row = pos.loc[date] if pos is not None and date in pos.index else pd.Series(dtype=float)
            internal_bil = float(pos_row.get("BIL", 0.0) or 0.0)
            hidden_bil = sw * internal_bil
            internal_spy = sw * float(pos_row.get("SPY", 0.0) or 0.0)
            internal_defensive = sw * float(pos_row.reindex(list(DEFENSIVE_ETFS - {"BIL"})).fillna(0.0).sum())
            internal_offensive = sw * float(
                pos_row.drop(labels=list(DEFENSIVE_ETFS.union({"BIL"})), errors="ignore").fillna(0.0).sum()
            )
            hidden_bil_total += hidden_bil
            offensive_from_sleeves += internal_offensive
            spy_from_sleeves += internal_spy
            defensive_from_sleeves += internal_defensive
            sleeve_rows.append(
                {
                    "Date": str(date.date()),
                    "version_name": version_name,
                    "state": state_row["state_bucket"],
                    "sleeve_name": sleeve,
                    "sleeve_weight": sw,
                    "internal_bil": internal_bil,
                    "hidden_bil_contrib": hidden_bil,
                    "spy_contrib": internal_spy,
                    "offensive_etf_contrib": internal_offensive,
                    "defensive_etf_contrib": internal_defensive,
                }
            )
        sleeve_cash = float(sleeve_row.get("cash::BIL", 0.0) or 0.0)
        final_bil = float(etf_row.get("BIL", 0.0) or 0.0)
        joined_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version_name,
                "state": state_row["state_bucket"],
                "sleeve_cash_weight": sleeve_cash,
                "final_bil_weight": final_bil,
                "lookthrough_hidden_bil_drag": final_bil - sleeve_cash,
                "hidden_bil_from_sleeves": hidden_bil_total,
                "sleeve_level_risky_weight": 1.0 - sleeve_cash,
                "etf_level_risky_weight": 1.0 - final_bil,
                "final_spy_weight": float(etf_row.get("SPY", 0.0) or 0.0),
                "final_offensive_etf_weight": offensive_etf_weight(etf_row),
                "final_defensive_etf_weight": defensive_etf_weight(etf_row),
                "offensive_from_sleeves": offensive_from_sleeves,
                "spy_from_sleeves": spy_from_sleeves,
                "defensive_from_sleeves": defensive_from_sleeves,
            }
        )
    drag_df = pd.DataFrame(joined_rows)
    sleeve_detail_df = pd.DataFrame(sleeve_rows)
    return drag_df, sleeve_detail_df


def summarise_drag_by_state(drag_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for state, sub in drag_df.groupby("state"):
        rows.append(
            {
                "state": state,
                "n_weeks": int(len(sub)),
                "avg_sleeve_cash_weight": float(sub["sleeve_cash_weight"].mean()),
                "avg_final_bil_weight": float(sub["final_bil_weight"].mean()),
                "avg_lookthrough_hidden_bil_drag": float(sub["lookthrough_hidden_bil_drag"].mean()),
                "avg_hidden_bil_from_sleeves": float(sub["hidden_bil_from_sleeves"].mean()),
                "avg_sleeve_level_risky_weight": float(sub["sleeve_level_risky_weight"].mean()),
                "avg_etf_level_risky_weight": float(sub["etf_level_risky_weight"].mean()),
                "avg_final_spy_weight": float(sub["final_spy_weight"].mean()),
                "avg_final_offensive_etf_weight": float(sub["final_offensive_etf_weight"].mean()),
                "avg_final_defensive_etf_weight": float(sub["final_defensive_etf_weight"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
    if not out.empty:
        out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
        out = out.sort_values("state").reset_index(drop=True)
    return out


def summarise_drag_by_sleeve(sleeve_detail_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = sleeve_detail_df.groupby(["state", "sleeve_name"], observed=False)
    for (state, sleeve), sub in grouped:
        rows.append(
            {
                "state": state,
                "sleeve_name": sleeve,
                "n_weeks": int(len(sub)),
                "avg_sleeve_weight": float(sub["sleeve_weight"].mean()),
                "avg_internal_bil": float(sub["internal_bil"].mean()),
                "avg_hidden_bil_contrib": float(sub["hidden_bil_contrib"].mean()),
                "avg_spy_contrib": float(sub["spy_contrib"].mean()),
                "avg_offensive_etf_contrib": float(sub["offensive_etf_contrib"].mean()),
                "avg_defensive_etf_contrib": float(sub["defensive_etf_contrib"].mean()),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
        out["state"] = pd.Categorical(out["state"], categories=order, ordered=True)
        out = out.sort_values(["state", "avg_hidden_bil_contrib"], ascending=[True, False]).reset_index(drop=True)
    return out


def hidden_bil_sources_table(sleeve_summary: pd.DataFrame) -> pd.DataFrame:
    if sleeve_summary.empty:
        return sleeve_summary
    overall = (
        sleeve_summary.groupby("sleeve_name", observed=False)[["avg_hidden_bil_contrib", "avg_offensive_etf_contrib", "avg_defensive_etf_contrib"]]
        .mean()
        .reset_index()
        .rename(columns={"avg_hidden_bil_contrib": "avg_hidden_bil_contrib_all_states"})
    )
    return overall.sort_values("avg_hidden_bil_contrib_all_states", ascending=False).reset_index(drop=True)


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
            joined.loc[recovery_mask.reindex(joined.index, fill_value=False), "portfolio"].mean() /
            joined.loc[recovery_mask.reindex(joined.index, fill_value=False), "benchmark"].mean()
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


def build_selection_table(metrics_df: pd.DataFrame, candidate_diag: pd.DataFrame, state_summary: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    prod = metrics_df[metrics_df["name"] == PRODUCTION].iloc[0]
    prod_states = state_summary[state_summary["name"] == PRODUCTION].set_index("state")
    rows = []
    for candidate in PHASE_NN_CANDIDATES:
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
        drag_sub = candidate_diag[candidate_diag["name"] == candidate]
        avg_drag_reduction = float(drag_sub["lookthrough_drag_reduction_vs_prod"].mean()) if not drag_sub.empty else np.nan
        rec_drag_reduction = float(
            drag_sub[drag_sub["state"].isin(["recovery_confirmed", "recovery_fragile"])]["lookthrough_drag_reduction_vs_prod"].mean()
        ) if not drag_sub.empty else np.nan
        cand_states = state_summary[state_summary["name"] == candidate].set_index("state")
        sp_delta = float(cand_states.loc["stressed_panic", "mean_weekly_return"] - prod_states.loc["stressed_panic", "mean_weekly_return"]) if "stressed_panic" in cand_states.index else np.nan
        cond_ann = ann_delta_pp >= -0.30
        cond_sharpe = sharpe_delta >= 0.005
        cond_mdd = mdd_delta_pp >= -0.50
        cond_cvar = cvar_delta_pp >= -0.05
        cond_turn = turn_ratio <= 1.10
        cond_stress = np.isnan(sp_delta) or sp_delta >= -0.0005
        cond_beta = not (spy_delta_pp > 2.0 and sharpe_delta < 0.005)
        cond_drag = np.isfinite(avg_drag_reduction) and avg_drag_reduction > 0 and (ann_delta_pp > 0 or sharpe_delta > 0)
        passes = all([cond_ann, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_stress, cond_beta, cond_drag])
        fail_reasons = "; ".join(
            reason for reason in [
                f"ann_return_drag {ann_delta_pp:+.2f}pp" if not cond_ann else "",
                f"sharpe_delta {sharpe_delta:+.4f}" if not cond_sharpe else "",
                f"max_drawdown_delta {mdd_delta_pp:+.2f}pp" if not cond_mdd else "",
                f"cvar_delta {cvar_delta_pp:+.2f}pp" if not cond_cvar else "",
                f"turnover_ratio {turn_ratio:.2f}x" if not cond_turn else "",
                f"stressed_panic worse {sp_delta:+.5f}/wk" if not cond_stress else "",
                f"hidden beta {spy_delta_pp:+.2f}pp SPY" if not cond_beta else "",
                f"drag reduction not translating ({avg_drag_reduction:+.4f})" if not cond_drag else "",
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
                "avg_lookthrough_drag_reduction_vs_prod": avg_drag_reduction,
                "recovery_state_drag_reduction_vs_prod": rec_drag_reduction,
                "passes_all_gates": passes,
                "fail_reasons": fail_reasons,
            }
        )
    selection = pd.DataFrame(rows)
    if selection.empty:
        return selection, ""
    best = selection.sort_values(
        by=["passes_all_gates", "sharpe_delta_vs_prod", "ann_return_delta_pp_vs_prod", "avg_lookthrough_drag_reduction_vs_prod"],
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
        and r["avg_lookthrough_drag_reduction_vs_prod"] > 0
    )


def write_report(
    drag_by_state: pd.DataFrame,
    drag_by_sleeve: pd.DataFrame,
    etf_by_state: pd.DataFrame,
    hidden_sources: pd.DataFrame,
    metrics_df: pd.DataFrame,
    state_summary: pd.DataFrame,
    candidate_diag: pd.DataFrame,
    selection: pd.DataFrame,
    best_candidate: str,
    quick_verdict: str,
    committee_report: Path,
    ran_layer56: bool,
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final_decision = quick_verdict if quick_verdict in {"KEEP AS PRODUCTION", "KEEP AS SHADOW", "REJECT", "NEEDS FIX BEFORE JUDGMENT"} else "REJECT"
    layer56_text = "Ran quick Layer 5/6 audits." if ran_layer56 else "Skipped Layer 5/6 quick audits."
    lines = [
        "# 2026-04-27 Phase NN — Lookthrough Participation Audit\n\n",
        "## Commands Executed\n```\n",
        "python scripts/phase_nn_lookthrough_participation_audit.py\n",
        *[f"{cmd}\n" for cmd in COMMAND_LOG],
        "```\n\n",
        "## Files Created / Modified\n",
        "- Script: `scripts/phase_nn_lookthrough_participation_audit.py`\n",
        "- Builder variants: `scripts/build_improvement_artifacts.py`\n",
        "- Diagnostics: `data/research/phase_nn_lookthrough_participation/`\n",
        "- Candidate outputs: `data/05_layer3_portfolio_construction/phase_nn_*`\n",
        f"- Report: `{REPORT_PATH.relative_to(ROOT)}`\n\n",
        "## Lookthrough Drag By State\n```\n",
        drag_by_state.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not drag_by_state.empty else "No state drag table available.",
        "\n```\n\n",
        "## Lookthrough Drag By Sleeve\n```\n",
        drag_by_sleeve.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not drag_by_sleeve.empty else "No sleeve drag table available.",
        "\n```\n\n",
        "## Biggest Hidden BIL / Cash Sources\n```\n",
        hidden_sources.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not hidden_sources.empty else "No hidden-BIL source table available.",
        "\n```\n\n",
        "## ETF Exposure By State\n```\n",
        etf_by_state.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not etf_by_state.empty else "No ETF exposure table available.",
        "\n```\n\n",
        "## Candidate Metrics Table\n```\n",
        metrics_df.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not metrics_df.empty else "No metrics available.",
        "\n```\n\n",
        "## State-By-State Candidate Impact\n```\n",
        state_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not state_summary.empty else "No state summary available.",
        "\n```\n\n",
        "## Candidate Lookthrough Diagnostics\n```\n",
        candidate_diag.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not candidate_diag.empty else "No candidate diagnostics available.",
        "\n```\n\n",
        "## Selection Table\n```\n",
        selection.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not selection.empty else "No selection table available.",
        "\n```\n\n",
        "## Best Candidate\n",
        f"- Best candidate: `{best_candidate or 'none'}`\n",
        f"- Quick committee verdict: **{quick_verdict}**\n",
        f"- Research committee report: `{committee_report.relative_to(ROOT) if committee_report.exists() else committee_report}`\n",
        f"- Layer 5/6 status: {layer56_text}\n\n",
        "## Final Decision\n",
        f"**{final_decision}**\n\n",
        "- Production pin remains unchanged.\n",
        "- Shadow pin remains unchanged.\n",
        f"- Lookthrough participation path should {'continue' if final_decision in {'KEEP AS SHADOW', 'KEEP AS PRODUCTION'} else 'not continue in its current narrow form'}.\n",
        f"- Recommended next phase if this fails: {'targeted composite_regime_conditioned sleeve redesign or more direct sleeve-internal cash architecture audit' if final_decision in {'REJECT', 'NEEDS FIX BEFORE JUDGMENT'} else 'follow-on robustness validation on the best lookthrough fix'}.\n",
    ]
    REPORT_PATH.write_text("".join(lines))


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_files = ensure_production_checkpoints()
    state_history = load_state_history()

    prod_sleeve_weights = roc.load_portfolio_sleeve_weights(PRODUCTION)
    prod_etf_weights = roc.load_portfolio_weights(PRODUCTION)
    if prod_sleeve_weights is None or prod_etf_weights is None:
        raise RuntimeError("Production sleeve or ETF weights missing.")
    sleeves = [c for c in prod_sleeve_weights.columns if not str(c).startswith("cash::")]
    base_positions = load_base_positions(sleeves)
    position_maps = candidate_position_maps(base_positions, state_history)

    prod_drag_df, prod_sleeve_detail = compute_lookthrough_state_drag(
        PRODUCTION, prod_sleeve_weights, prod_etf_weights, position_maps[PRODUCTION], state_history
    )
    drag_by_state = summarise_drag_by_state(prod_drag_df)
    drag_by_state.to_csv(AUDIT_DIR / "phase_nn_lookthrough_drag_by_state.csv", index=False)
    drag_by_sleeve = summarise_drag_by_sleeve(prod_sleeve_detail)
    drag_by_sleeve.to_csv(AUDIT_DIR / "phase_nn_lookthrough_drag_by_sleeve.csv", index=False)
    etf_by_state = drag_by_state[[
        "state",
        "n_weeks",
        "avg_final_bil_weight",
        "avg_final_spy_weight",
        "avg_final_offensive_etf_weight",
        "avg_final_defensive_etf_weight",
        "avg_sleeve_level_risky_weight",
        "avg_etf_level_risky_weight",
    ]].copy()
    etf_by_state.to_csv(AUDIT_DIR / "phase_nn_etf_exposure_by_state.csv", index=False)
    hidden_sources = hidden_bil_sources_table(drag_by_sleeve)
    hidden_sources.to_csv(AUDIT_DIR / "phase_nn_hidden_bil_sources.csv", index=False)

    build_candidates()

    benchmark_returns = roc.load_weekly_returns()["SPY"]
    metrics_rows = [metric_row(name, benchmark_returns, state_history) for name in [PRODUCTION, SHADOW] + PHASE_NN_CANDIDATES]
    metrics_df = pd.DataFrame(metrics_rows)
    prod_metrics = metrics_df[metrics_df["name"] == PRODUCTION].iloc[0]
    metrics_df["ann_return_delta_vs_prod"] = metrics_df["ann_return"] - prod_metrics["ann_return"]
    metrics_df["sharpe_delta_vs_prod"] = metrics_df["sharpe"] - prod_metrics["sharpe"]
    metrics_df.to_csv(roc.LAYER3_DIR / "phase_nn_candidate_metrics_full.csv", index=False)

    state_frames = []
    candidate_diag_rows = []
    prod_drag_by_state = summarise_drag_by_state(prod_drag_df).set_index("state")
    for name in [PRODUCTION, SHADOW] + PHASE_NN_CANDIDATES:
        frame = state_summary_row(name, benchmark_returns, state_history)
        if not frame.empty:
            state_frames.append(frame)
        if name in position_maps:
            sleeve_w = roc.load_portfolio_sleeve_weights(name)
            etf_w = roc.load_portfolio_weights(name)
            if sleeve_w is not None and etf_w is not None:
                cand_drag_df, _ = compute_lookthrough_state_drag(name, sleeve_w, etf_w, position_maps[name], state_history)
                cand_drag_state = summarise_drag_by_state(cand_drag_df)
                for _, row in cand_drag_state.iterrows():
                    state_name = row["state"]
                    prod_drag = float(prod_drag_by_state.loc[state_name, "avg_lookthrough_hidden_bil_drag"]) if state_name in prod_drag_by_state.index else np.nan
                    candidate_diag_rows.append(
                        {
                            "name": name,
                            "state": state_name,
                            "avg_lookthrough_hidden_bil_drag": row["avg_lookthrough_hidden_bil_drag"],
                            "lookthrough_drag_reduction_vs_prod": prod_drag - row["avg_lookthrough_hidden_bil_drag"] if np.isfinite(prod_drag) else np.nan,
                            "avg_final_bil_weight": row["avg_final_bil_weight"],
                            "avg_final_spy_weight": row["avg_final_spy_weight"],
                            "avg_final_offensive_etf_weight": row["avg_final_offensive_etf_weight"],
                        }
                    )
    state_summary = pd.concat(state_frames, ignore_index=True) if state_frames else pd.DataFrame()
    if not state_summary.empty:
        prod_states = state_summary[state_summary["name"] == PRODUCTION][["state", "ann_return", "sharpe", "mean_weekly_return"]].rename(
            columns={"ann_return": "prod_ann_return", "sharpe": "prod_sharpe", "mean_weekly_return": "prod_mean_weekly_return"}
        )
        state_summary = state_summary.merge(prod_states, on="state", how="left")
        state_summary["ann_return_delta_vs_prod"] = state_summary["ann_return"] - state_summary["prod_ann_return"]
        state_summary["sharpe_delta_vs_prod"] = state_summary["sharpe"] - state_summary["prod_sharpe"]
    state_summary.to_csv(roc.LAYER3_DIR / "phase_nn_state_summary.csv", index=False)

    candidate_diag = pd.DataFrame(candidate_diag_rows)
    candidate_diag = candidate_diag[candidate_diag["name"].isin(PHASE_NN_CANDIDATES)].copy()
    if not candidate_diag.empty:
        order = ["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
        candidate_diag["state"] = pd.Categorical(candidate_diag["state"], categories=order, ordered=True)
        candidate_diag = candidate_diag.sort_values(["name", "state"]).reset_index(drop=True)
    candidate_diag.to_csv(AUDIT_DIR / "phase_nn_candidate_diagnostics.csv", index=False)

    selection, best_candidate = build_selection_table(metrics_df, candidate_diag, state_summary)
    selection.to_csv(roc.LAYER3_DIR / "phase_nn_selection_table.csv", index=False)

    quick_verdict = "NEEDS FIX BEFORE JUDGMENT"
    committee_report = roc.REPORTS_DIR / "research_committee" / "missing.md"
    ran_layer56 = False
    if best_candidate:
        run_logged([sys.executable, str(ROOT / "scripts" / "research_committee_report.py"), best_candidate, "--quick"], timeout=1800)
        quick_verdict, committee_report = parse_committee_verdict(best_candidate)
        if quick_verdict in {"KEEP AS PRODUCTION", "KEEP AS SHADOW"} and genuine_improvement(selection, best_candidate):
            run_logged([sys.executable, str(ROOT / "scripts" / "backtest_realism_audit.py"), best_candidate, "--quick"], timeout=1800)
            run_logged([sys.executable, str(ROOT / "scripts" / "allocator_benchmark_audit.py"), best_candidate, "--quick"], timeout=1800)
            ran_layer56 = True

    protocol = {
        "phase": "Phase NN — sleeve-to-ETF participation loss audit and fix",
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "checkpoint_files": checkpoint_files,
        "commands_executed": COMMAND_LOG,
        "best_candidate": best_candidate,
        "quick_verdict": quick_verdict,
        "layer5_6_quick_audits_ran": ran_layer56,
    }
    (roc.LAYER3_DIR / "phase_nn_protocol.json").write_text(json.dumps(protocol, indent=2))

    write_report(
        drag_by_state,
        drag_by_sleeve,
        etf_by_state,
        hidden_sources,
        metrics_df[metrics_df["name"].isin([PRODUCTION, SHADOW] + PHASE_NN_CANDIDATES)].copy(),
        state_summary[state_summary["name"].isin([PRODUCTION, SHADOW] + PHASE_NN_CANDIDATES)].copy(),
        candidate_diag,
        selection,
        best_candidate,
        quick_verdict,
        committee_report,
        ran_layer56,
    )

    print("\nPhase NN complete.")
    print(f"Best candidate: {best_candidate or 'none'}")
    print(f"Quick committee verdict: {quick_verdict}")
    print(f"Layer 5/6 quick audits ran: {ran_layer56}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
