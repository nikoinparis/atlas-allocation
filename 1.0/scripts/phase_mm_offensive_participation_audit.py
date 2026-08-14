"""Phase MM — offensive participation ceiling / overlay audit.

Diagnostic + narrow structural test on top of the existing production
construction pipeline. No new ML, no broad parameter sweep, and no pin
changes. The script:

1. Rebuilds production with allocator checkpoints enabled.
2. Quantifies stage-by-stage participation / cash behavior by state.
3. Runs up to three tightly scoped production-family candidates.
4. Applies a quick-screen selection rule.
5. Runs the Research Committee quick report for the best candidate.
6. Escalates to Layer 5 / 6 quick audits only for a genuine finalist.
7. Writes CSV diagnostics plus a markdown research report.
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
PHASE_MM_CANDIDATES = [
    "improved_phasemm_recovery_cash_relief",
    "improved_phasemm_good_state_overlay_relief",
    "improved_phasemm_recovery_confirmed_sleeve_fix",
]
CHECKPOINT_DIR = ROOT / "data" / "research" / "allocator_checkpoints"
AUDIT_DATA_DIR = ROOT / "data" / "research" / "phase_mm_offensive_participation"
REPORT_PATH = ROOT / "docs" / "research" / "2026-04-27_phase_mm_offensive_participation_audit_report.md"
DEFENSIVE_ETFS = {"IEF", "SHY", "TLT", "TIP", "GLD"}
OFFENSIVE_SLEEVES = {
    "dual_momentum_topn",
    "cta_trend_long_only",
    "cta_trend_vol_managed",
    "composite_selective_signals",
    "composite_selective_trend_ensemble",
    "composite_selective_concentrated",
    "composite_equal_weight",
    "composite_trend_quality_module",
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "sector_rotation_with_sma_filter",
}
DEFENSIVE_SLEEVES = {"composite_regime_conditioned", "taa_10m_sma"}
TARGET_STATE_ORDER = [
    "calm_trend",
    "neutral_healthy_proxy",
    "neutral_mixed",
    "recovery_confirmed",
    "recovery_fragile",
    "stressed_panic",
]
COMMAND_LOG: list[str] = []
COMMAND_OUTPUT_TAILS: list[dict] = []


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
    COMMAND_OUTPUT_TAILS.append(
        {
            "command": rendered,
            "returncode": result.returncode,
            "stdout_tail": "\n".join((result.stdout or "").splitlines()[-20:]),
            "stderr_tail": "\n".join((result.stderr or "").splitlines()[-20:]),
        }
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {rendered}\n"
            f"stdout tail:\n{COMMAND_OUTPUT_TAILS[-1]['stdout_tail']}\n"
            f"stderr tail:\n{COMMAND_OUTPUT_TAILS[-1]['stderr_tail']}"
        )
    return result


def clear_checkpoint_files(version_name: str) -> None:
    if not CHECKPOINT_DIR.exists():
        return
    for path in CHECKPOINT_DIR.glob(f"{version_name}__*.csv"):
        path.unlink()


def build_versions(version_names: list[str], *, save_checkpoints: bool = False) -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(version_names)
    if save_checkpoints:
        env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    command = [sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")]
    run_logged(command, env=env, timeout=7200)


def parse_stage_table(version_name: str, stage_name: str) -> pd.DataFrame:
    path = CHECKPOINT_DIR / f"{version_name}__{stage_name}.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path, index_col=0, parse_dates=True).sort_index()
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame


def is_strong_neutral_row(row: pd.Series) -> bool:
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


def prepare_state_history() -> pd.DataFrame:
    state = roc.load_market_state(refined=False).copy()
    state["strong_neutral"] = state.apply(is_strong_neutral_row, axis=1)
    state["state_bucket"] = np.where(
        state["market_state"].eq("neutral_mixed") & state["strong_neutral"],
        "neutral_healthy_proxy",
        state["market_state"],
    )
    return state


def sleeve_stage_exposures(panel: pd.DataFrame, cash_proxy: str = "BIL") -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    cash_col = f"cash::{cash_proxy}"
    offensive_cols = [c for c in panel.columns if c in OFFENSIVE_SLEEVES]
    defensive_cols = [c for c in panel.columns if c in DEFENSIVE_SLEEVES]
    out = pd.DataFrame(index=panel.index)
    out["offensive_exposure"] = panel.reindex(columns=offensive_cols, fill_value=0.0).sum(axis=1)
    out["defensive_exposure"] = panel.reindex(columns=defensive_cols, fill_value=0.0).sum(axis=1)
    out["cash_exposure"] = panel.get(cash_col, pd.Series(0.0, index=panel.index))
    out["bil_exposure"] = out["cash_exposure"]
    out["spy_exposure"] = np.nan
    out["risky_exposure"] = 1.0 - out["cash_exposure"]
    out["stage_type"] = "sleeve"
    return out


def etf_stage_exposures(panel: pd.DataFrame, cash_proxy: str = "BIL") -> pd.DataFrame:
    if panel.empty:
        return pd.DataFrame()
    offensive_cols = [c for c in panel.columns if c not in DEFENSIVE_ETFS.union({cash_proxy})]
    defensive_cols = [c for c in panel.columns if c in DEFENSIVE_ETFS and c != cash_proxy]
    out = pd.DataFrame(index=panel.index)
    out["offensive_exposure"] = panel.reindex(columns=offensive_cols, fill_value=0.0).sum(axis=1)
    out["defensive_exposure"] = panel.reindex(columns=defensive_cols, fill_value=0.0).sum(axis=1)
    out["cash_exposure"] = panel.get(cash_proxy, pd.Series(0.0, index=panel.index))
    out["bil_exposure"] = panel.get(cash_proxy, pd.Series(0.0, index=panel.index))
    out["spy_exposure"] = panel.get("SPY", pd.Series(0.0, index=panel.index))
    out["risky_exposure"] = 1.0 - out["cash_exposure"]
    out["stage_type"] = "etf"
    return out


def summarise_stage_by_state(stage_name: str, exposures: pd.DataFrame, state_history: pd.DataFrame) -> pd.DataFrame:
    if exposures.empty:
        return pd.DataFrame()
    joined = exposures.join(
        state_history[["market_state", "state_bucket", "strong_neutral"]],
        how="inner",
    ).dropna(subset=["state_bucket"])
    rows: list[dict] = []
    for state_name, sub in joined.groupby("state_bucket"):
        rows.append(
            {
                "stage": stage_name,
                "state": state_name,
                "n_weeks": int(len(sub)),
                "avg_offensive_exposure": float(sub["offensive_exposure"].mean()),
                "avg_defensive_exposure": float(sub["defensive_exposure"].mean()),
                "avg_cash_exposure": float(sub["cash_exposure"].mean()),
                "avg_bil_exposure": float(sub["bil_exposure"].mean()),
                "avg_spy_exposure": float(sub["spy_exposure"].mean()) if sub["spy_exposure"].notna().any() else np.nan,
                "avg_risky_exposure": float(sub["risky_exposure"].mean()),
                "strong_neutral_share": float(sub["strong_neutral"].mean()),
                "stage_type": sub["stage_type"].iloc[0],
            }
        )
    return pd.DataFrame(rows)


def build_stage_deltas(stage_summary: pd.DataFrame) -> pd.DataFrame:
    if stage_summary.empty:
        return pd.DataFrame()
    stage_order = [
        "raw_hrp_sleeve_weights",
        "post_state_tilt_sleeve_weights",
        "post_layer3_expression_sleeve_weights",
        "post_overlay_pre_lookthrough_sleeve_weights",
        "final_sleeve_weights",
        "final_etf_weights",
    ]
    frames = []
    ordered = stage_summary.copy()
    ordered["stage"] = pd.Categorical(ordered["stage"], categories=stage_order, ordered=True)
    ordered = ordered.sort_values(["state", "stage"])
    for state_name, sub in ordered.groupby("state", sort=False, observed=False):
        prior = None
        for _, row in sub.iterrows():
            if prior is not None:
                frames.append(
                    {
                        "state": state_name,
                        "stage_from": prior["stage"],
                        "stage_to": row["stage"],
                        "delta_offensive_exposure": row["avg_offensive_exposure"] - prior["avg_offensive_exposure"],
                        "delta_defensive_exposure": row["avg_defensive_exposure"] - prior["avg_defensive_exposure"],
                        "delta_cash_exposure": row["avg_cash_exposure"] - prior["avg_cash_exposure"],
                        "delta_bil_exposure": row["avg_bil_exposure"] - prior["avg_bil_exposure"],
                        "delta_spy_exposure": row["avg_spy_exposure"] - prior["avg_spy_exposure"],
                        "delta_risky_exposure": row["avg_risky_exposure"] - prior["avg_risky_exposure"],
                    }
                )
            prior = row
    return pd.DataFrame(frames)


def load_production_diagnostics_by_state() -> pd.DataFrame:
    path = roc.LAYER3_DIR / "portfolio_version_diagnostics_by_state.csv"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if "version_name" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["version_name"] == PRODUCTION].copy()


def annualised_capture(portfolio: pd.Series, benchmark: pd.Series, mask: pd.Series) -> float:
    aligned = pd.concat([portfolio.rename("p"), benchmark.rename("b"), mask.rename("m")], axis=1).dropna()
    aligned = aligned[aligned["m"]]
    if aligned.empty:
        return float("nan")
    b_mean = float(aligned["b"].mean())
    if abs(b_mean) < 1e-12:
        return float("nan")
    return float(aligned["p"].mean() / b_mean)


def compute_headline_metrics(name: str, state_history: pd.DataFrame, benchmark_returns: pd.Series) -> dict:
    ret = roc.load_portfolio_returns(name)
    weights = roc.load_portfolio_weights(name)
    sleeve_weights = roc.load_portfolio_sleeve_weights(name)
    if ret is None or weights is None:
        return {"name": name, "missing": True}
    net = ret["net_return"].dropna()
    metrics = roc.metric_block(net)
    turnover = (
        float(ret["turnover"].mean())
        if "turnover" in ret.columns
        else float(roc.weekly_turnover(weights).mean())
    )
    offensive_cols = [c for c in weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
    defensive_cols = [c for c in weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
    offense = weights.reindex(columns=offensive_cols, fill_value=0.0).sum(axis=1)
    defense = weights.reindex(columns=defensive_cols, fill_value=0.0).sum(axis=1)
    cash = weights.get("BIL", pd.Series(0.0, index=weights.index))
    joined = pd.concat([net.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    state_aligned = state_history.reindex(net.index)
    state_bucket = state_aligned["state_bucket"]
    recovery_mask = state_bucket.isin(["recovery_confirmed", "recovery_fragile"])
    calm_mask = state_bucket.eq("calm_trend")
    up_mask = joined["benchmark"] > 0
    down_mask = joined["benchmark"] < 0
    holdout = net.tail(roc.HOLDOUT_WEEKS)
    holdout_metrics = roc.metric_block(holdout)
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
        "upside_capture": annualised_capture(net, benchmark_returns, up_mask.reindex(net.index, fill_value=False).astype(bool)),
        "downside_capture": annualised_capture(net, benchmark_returns, down_mask.reindex(net.index, fill_value=False).astype(bool)),
        "recovery_capture": annualised_capture(net, benchmark_returns, recovery_mask.reindex(net.index, fill_value=False).astype(bool)),
        "calm_capture": annualised_capture(net, benchmark_returns, calm_mask.reindex(net.index, fill_value=False).astype(bool)),
        "avg_BIL": float(cash.mean()),
        "avg_SPY": float(weights.get("SPY", pd.Series(0.0, index=weights.index)).mean()),
        "avg_offense": float(offense.mean()),
        "avg_defense": float(defense.mean()),
        "avg_cash": float(cash.mean()),
        "holdout_ann_return": holdout_metrics["ann_return"],
        "holdout_sharpe": holdout_metrics["sharpe"],
        "holdout_max_drawdown": holdout_metrics["max_drawdown"],
        "sleeve_weight_avg_css": float(sleeve_weights.get("composite_selective_signals", pd.Series(0.0, index=sleeve_weights.index)).mean()) if sleeve_weights is not None else np.nan,
    }
    return row


def compute_state_summary(name: str, state_history: pd.DataFrame, benchmark_returns: pd.Series) -> pd.DataFrame:
    ret = roc.load_portfolio_returns(name)
    weights = roc.load_portfolio_weights(name)
    sleeve_weights = roc.load_portfolio_sleeve_weights(name)
    if ret is None or weights is None:
        return pd.DataFrame()
    net = ret["net_return"].rename("portfolio")
    cash = weights.get("BIL", pd.Series(0.0, index=weights.index))
    offense_cols = [c for c in weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
    defense_cols = [c for c in weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
    offense = weights.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1)
    defense = weights.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1)
    joined = pd.concat(
        [
            net,
            benchmark_returns.rename("benchmark"),
            cash.rename("cash"),
            weights.get("SPY", pd.Series(0.0, index=weights.index)).rename("SPY"),
            offense.rename("offense"),
            defense.rename("defense"),
            state_history[["state_bucket"]],
        ],
        axis=1,
    ).dropna(subset=["portfolio", "state_bucket"])
    if sleeve_weights is not None:
        css = sleeve_weights.get("composite_selective_signals", pd.Series(0.0, index=sleeve_weights.index))
        joined["css_weight"] = css.reindex(joined.index).fillna(0.0)
    rows = []
    for state_name, sub in joined.groupby("state_bucket"):
        metrics = roc.metric_block(sub["portfolio"])
        spy_metrics = roc.metric_block(sub["benchmark"])
        rows.append(
            {
                "name": name,
                "state": state_name,
                "n_weeks": int(len(sub)),
                "ann_return": metrics["ann_return"],
                "ann_vol": metrics["ann_vol"],
                "sharpe": metrics["sharpe"],
                "max_drawdown": metrics["max_drawdown"],
                "cvar_5": metrics["cvar_5"],
                "benchmark_ann_return": spy_metrics["ann_return"],
                "benchmark_sharpe": spy_metrics["sharpe"],
                "avg_BIL": float(sub["cash"].mean()),
                "avg_SPY": float(sub["SPY"].mean()),
                "avg_offense": float(sub["offense"].mean()),
                "avg_defense": float(sub["defense"].mean()),
                "avg_cash": float(sub["cash"].mean()),
                "avg_css_weight": float(sub["css_weight"].mean()) if "css_weight" in sub.columns else np.nan,
                "mean_weekly_return": float(sub["portfolio"].mean()),
                "mean_weekly_benchmark": float(sub["benchmark"].mean()),
            }
        )
    return pd.DataFrame(rows)


def build_selection_table(metrics_df: pd.DataFrame, state_summary: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    prod = metrics_df[metrics_df["name"] == PRODUCTION].iloc[0]
    rows: list[dict] = []
    for candidate in PHASE_MM_CANDIDATES:
        row = metrics_df[metrics_df["name"] == candidate]
        if row.empty:
            rows.append({"name": candidate, "passes_all_gates": False, "fail_reasons": "candidate metrics missing"})
            continue
        cand = row.iloc[0]
        ann_delta_pp = (cand["ann_return"] - prod["ann_return"]) * 100.0
        sharpe_delta = cand["sharpe"] - prod["sharpe"]
        mdd_delta_pp = (cand["max_drawdown"] - prod["max_drawdown"]) * 100.0
        cvar_delta_pp = (cand["cvar_5"] - prod["cvar_5"]) * 100.0
        turnover_ratio = cand["avg_turnover"] / prod["avg_turnover"] if prod["avg_turnover"] > 0 else np.inf
        bil_delta_pp = (cand["avg_BIL"] - prod["avg_BIL"]) * 100.0
        spy_delta_pp = (cand["avg_SPY"] - prod["avg_SPY"]) * 100.0

        cand_states = state_summary[state_summary["name"] == candidate].set_index("state")
        prod_states = state_summary[state_summary["name"] == PRODUCTION].set_index("state")
        rf_weekly_delta = float(cand_states.loc["recovery_fragile", "mean_weekly_return"] - prod_states.loc["recovery_fragile", "mean_weekly_return"]) if "recovery_fragile" in cand_states.index and "recovery_fragile" in prod_states.index else np.nan
        sp_weekly_delta = float(cand_states.loc["stressed_panic", "mean_weekly_return"] - prod_states.loc["stressed_panic", "mean_weekly_return"]) if "stressed_panic" in cand_states.index and "stressed_panic" in prod_states.index else np.nan
        calm_weekly_delta = float(cand_states.loc["calm_trend", "mean_weekly_return"] - prod_states.loc["calm_trend", "mean_weekly_return"]) if "calm_trend" in cand_states.index and "calm_trend" in prod_states.index else np.nan
        rc_css_delta_pp = float((cand_states.loc["recovery_confirmed", "avg_css_weight"] - prod_states.loc["recovery_confirmed", "avg_css_weight"]) * 100.0) if "recovery_confirmed" in cand_states.index and "recovery_confirmed" in prod_states.index else np.nan

        cond_ann = ann_delta_pp >= -0.30
        cond_sharpe = sharpe_delta >= 0.005
        cond_mdd = mdd_delta_pp >= -0.50
        cond_cvar = cvar_delta_pp >= -0.05
        cond_turn = turnover_ratio <= 1.10
        cond_bil = bil_delta_pp >= -6.0 or sharpe_delta >= 0.005 or mdd_delta_pp >= 0.0
        cond_stress = np.isnan(sp_weekly_delta) or sp_weekly_delta >= -0.0005
        cond_rf = candidate != "improved_phasemm_recovery_cash_relief" or np.isnan(rf_weekly_delta) or rf_weekly_delta >= 0.0
        cond_hidden_beta = not (spy_delta_pp > 2.0 and sharpe_delta < 0.005)
        passes = all([cond_ann, cond_sharpe, cond_mdd, cond_cvar, cond_turn, cond_bil, cond_stress, cond_rf, cond_hidden_beta])
        fail_reasons = "; ".join(
            reason for reason in [
                f"ann_return_drag {ann_delta_pp:+.2f}pp" if not cond_ann else "",
                f"sharpe_delta {sharpe_delta:+.4f}" if not cond_sharpe else "",
                f"max_drawdown_delta {mdd_delta_pp:+.2f}pp" if not cond_mdd else "",
                f"cvar_delta {cvar_delta_pp:+.2f}pp" if not cond_cvar else "",
                f"turnover_ratio {turnover_ratio:.2f}x" if not cond_turn else "",
                f"BIL drop without risk offset {bil_delta_pp:+.2f}pp" if not cond_bil else "",
                f"stressed_panic worse {sp_weekly_delta:+.5f}/wk" if not cond_stress else "",
                f"recovery_fragile worse {rf_weekly_delta:+.5f}/wk" if not cond_rf else "",
                f"hidden beta {spy_delta_pp:+.2f}pp SPY" if not cond_hidden_beta else "",
            ]
            if reason
        ) or "none"
        rows.append(
            {
                "name": candidate,
                "ann_return_delta_pp_vs_prod": ann_delta_pp,
                "sharpe_delta_vs_prod": sharpe_delta,
                "max_drawdown_delta_pp_vs_prod": mdd_delta_pp,
                "cvar_delta_pp_vs_prod": cvar_delta_pp,
                "turnover_ratio_vs_prod": turnover_ratio,
                "avg_BIL_delta_pp_vs_prod": bil_delta_pp,
                "avg_SPY_delta_pp_vs_prod": spy_delta_pp,
                "recovery_fragile_delta_weekly_vs_prod": rf_weekly_delta,
                "stressed_panic_delta_weekly_vs_prod": sp_weekly_delta,
                "calm_trend_delta_weekly_vs_prod": calm_weekly_delta,
                "recovery_confirmed_css_delta_pp": rc_css_delta_pp,
                "passes_all_gates": passes,
                "fail_reasons": fail_reasons,
            }
        )
    selection = pd.DataFrame(rows)
    if selection.empty:
        return selection, ""
    ordered = selection.sort_values(
        by=["passes_all_gates", "sharpe_delta_vs_prod", "ann_return_delta_pp_vs_prod", "max_drawdown_delta_pp_vs_prod"],
        ascending=[False, False, False, False],
    )
    best = str(ordered.iloc[0]["name"])
    return selection, best


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


def determine_genuine_improvement(selection: pd.DataFrame, candidate: str) -> bool:
    row = selection[selection["name"] == candidate]
    if row.empty:
        return False
    r = row.iloc[0]
    return bool(
        r["sharpe_delta_vs_prod"] > 0.0
        and r["ann_return_delta_pp_vs_prod"] > 0.0
        and r["max_drawdown_delta_pp_vs_prod"] >= -0.25
    )


def write_protocol(best_candidate: str, quick_verdict: str, ran_layer56: bool, checkpoint_files: list[str]) -> None:
    payload = {
        "phase": "Phase MM — offensive participation ceiling / overlay audit",
        "production_pin": PRODUCTION,
        "shadow_pin": SHADOW,
        "candidates": PHASE_MM_CANDIDATES,
        "commands_executed": COMMAND_LOG,
        "best_candidate": best_candidate,
        "quick_committee_verdict": quick_verdict,
        "layer5_6_quick_audits_ran": ran_layer56,
        "checkpoint_files": checkpoint_files,
        "notes": [
            "No production or shadow pin change was made by this script.",
            "No new ML or Phase CC refined_state / defensive_overlay_hint features were used.",
            "Candidate count capped at three and integrated inside the production construction pipeline.",
        ],
    }
    (roc.LAYER3_DIR / "phase_mm_protocol.json").write_text(json.dumps(payload, indent=2))


def write_markdown_report(
    stage_summary: pd.DataFrame,
    stage_deltas: pd.DataFrame,
    overlay_cash: pd.DataFrame,
    state_behavior: pd.DataFrame,
    metrics_df: pd.DataFrame,
    state_summary: pd.DataFrame,
    selection: pd.DataFrame,
    best_candidate: str,
    quick_verdict: str,
    committee_report_path: Path,
    ran_layer56: bool,
    checkpoint_files: list[str],
    suppressing_stage: str,
) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    best_state = state_summary[state_summary["name"] == best_candidate].copy() if best_candidate else pd.DataFrame()
    candidate_metrics_view = metrics_df[metrics_df["name"].isin(PHASE_MM_CANDIDATES + [PRODUCTION, SHADOW])].copy()
    focus_states = state_summary[
        state_summary["state"].isin(["calm_trend", "neutral_healthy_proxy", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"])
    ].copy()
    final_decision = quick_verdict if quick_verdict in {"KEEP AS PRODUCTION", "KEEP AS SHADOW", "REJECT", "NEEDS FIX BEFORE JUDGMENT"} else "REJECT"
    layer56_text = "Ran quick Layer 5/6 audits." if ran_layer56 else "Skipped Layer 5/6 quick audits."
    report_lines = [
        "# 2026-04-27 Phase MM — Offensive Participation / Overlay Audit\n",
        "\n",
        "## Commands Executed\n",
        "```\n",
        "python scripts/phase_mm_offensive_participation_audit.py\n",
        *[f"{cmd}\n" for cmd in COMMAND_LOG],
        "```\n\n",
        "## Files Created / Modified\n",
        f"- Script: `scripts/phase_mm_offensive_participation_audit.py`\n",
        f"- Builder instrumentation: `scripts/build_improvement_artifacts.py`\n",
        f"- Diagnostics: `data/research/phase_mm_offensive_participation/`\n",
        f"- Candidate outputs: `data/05_layer3_portfolio_construction/phase_mm_*`\n",
        f"- Report: `{REPORT_PATH.relative_to(ROOT)}`\n",
        "\n",
        "## Checkpoint Files Generated\n",
    ]
    if checkpoint_files:
        report_lines.extend([f"- `{path}`\n" for path in checkpoint_files])
    else:
        report_lines.append("- None generated.\n")
    report_lines.extend(
        [
            "\n",
            "## Stage-By-Stage Exposure Findings\n",
            f"- Largest participation suppression in favorable / recovery states came from **{suppressing_stage}**.\n",
            "- `raw_hrp -> post_state_tilt` shows what the sleeve tilt does before overlays.\n",
            "- `post_layer3_expression -> post_overlay_pre_lookthrough` isolates lighter_both / cash creation.\n",
            "- `post_overlay_pre_lookthrough -> final_etf` isolates lookthrough plus any ETF-level participation effects.\n",
            "\n",
            "```\n",
            stage_summary.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not stage_summary.empty else "No stage summary available.",
            "\n```\n\n",
            "## Stage Delta Table\n",
            "```\n",
            stage_deltas.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not stage_deltas.empty else "No stage deltas available.",
            "\n```\n\n",
            "## Overlay Cash / BIL By State\n",
            "```\n",
            overlay_cash.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not overlay_cash.empty else "No overlay-cash table available.",
            "\n```\n\n",
            "## State Allocation Behavior\n",
            "```\n",
            state_behavior.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not state_behavior.empty else "No state behavior table available.",
            "\n```\n\n",
            "## Candidate Metrics Table\n",
            "```\n",
            candidate_metrics_view.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not candidate_metrics_view.empty else "No candidate metrics available.",
            "\n```\n\n",
            "## State-By-State Candidate Impact\n",
            "```\n",
            focus_states.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not focus_states.empty else "No state summary available.",
            "\n```\n\n",
            "## Selection Table\n",
            "```\n",
            selection.to_string(index=False, float_format=lambda x: f"{x:.4f}") if not selection.empty else "No selection table available.",
            "\n```\n\n",
            "## Best Candidate\n",
            f"- Best candidate: `{best_candidate or 'none'}`\n",
            f"- Quick committee verdict: **{quick_verdict}**\n",
            f"- Research committee report: `{committee_report_path.relative_to(ROOT) if committee_report_path.exists() else committee_report_path}`\n",
            f"- Layer 5/6 status: {layer56_text}\n",
            "\n",
            "## Final Decision\n",
            f"**{final_decision}**\n\n",
            "- Production pin remains unchanged.\n",
            "- Shadow pin remains unchanged.\n",
            f"- Overlay / cash participation path should {'continue' if best_candidate and quick_verdict in {'KEEP AS SHADOW', 'KEEP AS PRODUCTION'} else 'not continue as currently specified'}.\n",
            f"- Recommended next phase if this fails: {'targeted recovery re-risking / regime-to-action mapping test' if final_decision in {'REJECT', 'NEEDS FIX BEFORE JUDGMENT'} else 'Layer 5/6 robustness validation on the best narrow structural fix'}.\n",
        ]
    )
    REPORT_PATH.write_text("".join(report_lines))


def main() -> None:
    AUDIT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (roc.REPORTS_DIR / "research_committee").mkdir(parents=True, exist_ok=True)

    clear_checkpoint_files(PRODUCTION)
    build_versions([PRODUCTION], save_checkpoints=True)

    state_history = prepare_state_history()
    checkpoint_stage_names = [
        "raw_hrp_sleeve_weights",
        "post_state_tilt_sleeve_weights",
        "post_layer3_expression_sleeve_weights",
        "post_overlay_pre_lookthrough_sleeve_weights",
        "final_sleeve_weights",
        "final_etf_weights",
    ]
    stage_frames = {stage: parse_stage_table(PRODUCTION, stage) for stage in checkpoint_stage_names}
    checkpoint_files = [str((CHECKPOINT_DIR / f"{PRODUCTION}__{stage}.csv").relative_to(ROOT)) for stage in checkpoint_stage_names if (CHECKPOINT_DIR / f"{PRODUCTION}__{stage}.csv").exists()]

    stage_summary_rows = []
    for stage_name, panel in stage_frames.items():
        exposures = etf_stage_exposures(panel) if stage_name == "final_etf_weights" else sleeve_stage_exposures(panel)
        summary = summarise_stage_by_state(stage_name, exposures, state_history)
        if not summary.empty:
            stage_summary_rows.append(summary)
    stage_summary = pd.concat(stage_summary_rows, ignore_index=True) if stage_summary_rows else pd.DataFrame()
    stage_summary["state"] = pd.Categorical(stage_summary["state"], categories=TARGET_STATE_ORDER, ordered=True)
    stage_summary = stage_summary.sort_values(["state", "stage"]).reset_index(drop=True)
    stage_summary.to_csv(AUDIT_DATA_DIR / "phase_mm_stage_exposure_by_state.csv", index=False)

    stage_deltas = build_stage_deltas(stage_summary)
    stage_deltas["state"] = pd.Categorical(stage_deltas["state"], categories=TARGET_STATE_ORDER, ordered=True)
    stage_deltas = stage_deltas.sort_values(["state", "stage_from"]).reset_index(drop=True)
    stage_deltas.to_csv(AUDIT_DATA_DIR / "phase_mm_stage_deltas_by_state.csv", index=False)

    overlay_cash = pd.DataFrame()
    if not stage_summary.empty:
        pre = stage_summary[stage_summary["stage"] == "post_layer3_expression_sleeve_weights"].set_index("state")
        post = stage_summary[stage_summary["stage"] == "post_overlay_pre_lookthrough_sleeve_weights"].set_index("state")
        common_states = pre.index.intersection(post.index)
        overlay_cash = pd.DataFrame(
            {
                "state": common_states,
                "pre_overlay_cash": pre.loc[common_states, "avg_cash_exposure"].values,
                "post_overlay_cash": post.loc[common_states, "avg_cash_exposure"].values,
                "overlay_cash_added": post.loc[common_states, "avg_cash_exposure"].values - pre.loc[common_states, "avg_cash_exposure"].values,
                "pre_overlay_offense": pre.loc[common_states, "avg_offensive_exposure"].values,
                "post_overlay_offense": post.loc[common_states, "avg_offensive_exposure"].values,
                "overlay_offense_change": post.loc[common_states, "avg_offensive_exposure"].values - pre.loc[common_states, "avg_offensive_exposure"].values,
            }
        )
        diag_state = load_production_diagnostics_by_state().set_index("market_state") if not load_production_diagnostics_by_state().empty else pd.DataFrame()
        if not diag_state.empty:
            overlay_cash["regime_binding_rate"] = [
                float(diag_state.loc[s, "regime_binding_rate"]) if s in diag_state.index and "regime_binding_rate" in diag_state.columns else np.nan
                for s in overlay_cash["state"]
            ]
            overlay_cash["target_vol_binding_rate"] = [
                float(diag_state.loc[s, "target_vol_binding_rate"]) if s in diag_state.index and "target_vol_binding_rate" in diag_state.columns else np.nan
                for s in overlay_cash["state"]
            ]
    overlay_cash.to_csv(AUDIT_DATA_DIR / "phase_mm_overlay_cash_by_state.csv", index=False)

    weekly = roc.load_weekly_returns()
    benchmark_returns = weekly["SPY"].copy() if "SPY" in weekly.columns else pd.Series(dtype=float)
    bil_returns = weekly["BIL"].copy() if "BIL" in weekly.columns else pd.Series(dtype=float)
    prod_returns = roc.load_portfolio_returns(PRODUCTION)
    prod_weights = roc.load_portfolio_weights(PRODUCTION)
    state_behavior_rows = []
    if prod_returns is not None and prod_weights is not None and not benchmark_returns.empty:
        prod_net = prod_returns["net_return"]
        offense_cols = [c for c in prod_weights.columns if c not in DEFENSIVE_ETFS.union({"BIL"})]
        defense_cols = [c for c in prod_weights.columns if c in DEFENSIVE_ETFS and c != "BIL"]
        joined = pd.concat(
            [
                prod_net.rename("portfolio"),
                benchmark_returns.rename("SPY_ret"),
                bil_returns.rename("BIL_ret"),
                prod_weights.get("BIL", pd.Series(0.0, index=prod_weights.index)).rename("BIL"),
                prod_weights.get("SPY", pd.Series(0.0, index=prod_weights.index)).rename("SPY"),
                prod_weights.reindex(columns=offense_cols, fill_value=0.0).sum(axis=1).rename("offense"),
                prod_weights.reindex(columns=defense_cols, fill_value=0.0).sum(axis=1).rename("defense"),
                state_history[["state_bucket", "market_state", "transition_non_stress_prob", "market_trend_positive", "breadth_sma_43", "breadth_26w_mom"]],
            ],
            axis=1,
        ).dropna(subset=["portfolio", "state_bucket"])
        for state_name, sub in joined.groupby("state_bucket"):
            state_behavior_rows.append(
                {
                    "state": state_name,
                    "n_weeks": int(len(sub)),
                    "production_ann_return": roc.annualised_return(sub["portfolio"]),
                    "production_sharpe": roc.sharpe(sub["portfolio"]),
                    "spy_ann_return": roc.annualised_return(sub["SPY_ret"]),
                    "spy_sharpe": roc.sharpe(sub["SPY_ret"]),
                    "bil_ann_return": roc.annualised_return(sub["BIL_ret"]) if sub["BIL_ret"].notna().any() else np.nan,
                    "prod_minus_spy_ann_return_pp": (roc.annualised_return(sub["portfolio"]) - roc.annualised_return(sub["SPY_ret"])) * 100.0,
                    "avg_BIL": float(sub["BIL"].mean()),
                    "avg_SPY": float(sub["SPY"].mean()),
                    "avg_offense": float(sub["offense"].mean()),
                    "avg_defense": float(sub["defense"].mean()),
                    "avg_cash": float(sub["BIL"].mean()),
                    "avg_transition_non_stress_prob": float(sub["transition_non_stress_prob"].mean()) if "transition_non_stress_prob" in sub.columns else np.nan,
                    "avg_market_trend_positive": float(sub["market_trend_positive"].mean()) if "market_trend_positive" in sub.columns else np.nan,
                    "avg_breadth_sma_43": float(sub["breadth_sma_43"].mean()) if "breadth_sma_43" in sub.columns else np.nan,
                    "avg_breadth_26w_mom": float(sub["breadth_26w_mom"].mean()) if "breadth_26w_mom" in sub.columns else np.nan,
                }
            )
    state_behavior = pd.DataFrame(state_behavior_rows)
    state_behavior["state"] = pd.Categorical(state_behavior["state"], categories=TARGET_STATE_ORDER, ordered=True)
    state_behavior = state_behavior.sort_values("state").reset_index(drop=True)
    state_behavior.to_csv(AUDIT_DATA_DIR / "phase_mm_bil_spy_offense_by_state.csv", index=False)

    build_versions([PRODUCTION] + PHASE_MM_CANDIDATES, save_checkpoints=False)

    metric_rows = []
    state_rows = []
    for name in [PRODUCTION, SHADOW] + PHASE_MM_CANDIDATES:
        metric_rows.append(compute_headline_metrics(name, state_history, benchmark_returns))
        summary = compute_state_summary(name, state_history, benchmark_returns)
        if not summary.empty:
            state_rows.append(summary)
    metrics_df = pd.DataFrame(metric_rows)
    prod_row = metrics_df[metrics_df["name"] == PRODUCTION].iloc[0]
    shadow_row = metrics_df[metrics_df["name"] == SHADOW].iloc[0] if not metrics_df[metrics_df["name"] == SHADOW].empty else None
    metrics_df["ann_return_delta_vs_prod"] = metrics_df["ann_return"] - prod_row["ann_return"]
    metrics_df["sharpe_delta_vs_prod"] = metrics_df["sharpe"] - prod_row["sharpe"]
    metrics_df["max_drawdown_delta_vs_prod"] = metrics_df["max_drawdown"] - prod_row["max_drawdown"]
    metrics_df["cvar_5_delta_vs_prod"] = metrics_df["cvar_5"] - prod_row["cvar_5"]
    if shadow_row is not None:
        metrics_df["ann_return_delta_vs_shadow"] = metrics_df["ann_return"] - shadow_row["ann_return"]
        metrics_df["sharpe_delta_vs_shadow"] = metrics_df["sharpe"] - shadow_row["sharpe"]
    metrics_df.to_csv(roc.LAYER3_DIR / "phase_mm_candidate_metrics_full.csv", index=False)

    state_summary = pd.concat(state_rows, ignore_index=True) if state_rows else pd.DataFrame()
    if not state_summary.empty:
        prod_state = state_summary[state_summary["name"] == PRODUCTION][["state", "ann_return", "sharpe", "mean_weekly_return"]].rename(
            columns={
                "ann_return": "prod_ann_return",
                "sharpe": "prod_sharpe",
                "mean_weekly_return": "prod_mean_weekly_return",
            }
        )
        shadow_state = state_summary[state_summary["name"] == SHADOW][["state", "ann_return", "sharpe"]].rename(
            columns={"ann_return": "shadow_ann_return", "sharpe": "shadow_sharpe"}
        )
        state_summary = state_summary.merge(prod_state, on="state", how="left").merge(shadow_state, on="state", how="left")
        state_summary["ann_return_delta_vs_prod"] = state_summary["ann_return"] - state_summary["prod_ann_return"]
        state_summary["sharpe_delta_vs_prod"] = state_summary["sharpe"] - state_summary["prod_sharpe"]
        state_summary["ann_return_delta_vs_shadow"] = state_summary["ann_return"] - state_summary["shadow_ann_return"]
        state_summary["sharpe_delta_vs_shadow"] = state_summary["sharpe"] - state_summary["shadow_sharpe"]
    state_summary.to_csv(roc.LAYER3_DIR / "phase_mm_state_summary.csv", index=False)

    selection, best_candidate = build_selection_table(metrics_df, state_summary)
    selection.to_csv(roc.LAYER3_DIR / "phase_mm_selection_table.csv", index=False)

    committee_report_path = roc.REPORTS_DIR / "research_committee" / "missing.md"
    quick_verdict = "NEEDS FIX BEFORE JUDGMENT"
    ran_layer56 = False
    if best_candidate:
        run_logged([sys.executable, str(ROOT / "scripts" / "research_committee_report.py"), best_candidate, "--quick"], timeout=1800)
        quick_verdict, committee_report_path = parse_committee_verdict(best_candidate)
        if quick_verdict in {"KEEP AS PRODUCTION", "KEEP AS SHADOW"} and determine_genuine_improvement(selection, best_candidate):
            run_logged([sys.executable, str(ROOT / "scripts" / "backtest_realism_audit.py"), best_candidate, "--quick"], timeout=1800)
            run_logged([sys.executable, str(ROOT / "scripts" / "allocator_benchmark_audit.py"), best_candidate, "--quick"], timeout=1800)
            ran_layer56 = True

    favorable_states = {"calm_trend", "neutral_healthy_proxy", "recovery_confirmed", "recovery_fragile"}
    suppressing_stage = "insufficient data"
    if not stage_deltas.empty:
        favored = stage_deltas[stage_deltas["state"].isin(favorable_states)].copy()
        if not favored.empty:
            by_stage = favored.groupby(["stage_from", "stage_to"], dropna=False)["delta_cash_exposure"].mean().reset_index()
            by_stage = by_stage.sort_values("delta_cash_exposure", ascending=False)
            if not by_stage.empty:
                suppressing_stage = f"{by_stage.iloc[0]['stage_from']} -> {by_stage.iloc[0]['stage_to']}"

    write_protocol(best_candidate, quick_verdict, ran_layer56, checkpoint_files)
    write_markdown_report(
        stage_summary,
        stage_deltas,
        overlay_cash,
        state_behavior,
        metrics_df,
        state_summary,
        selection,
        best_candidate,
        quick_verdict,
        committee_report_path,
        ran_layer56,
        checkpoint_files,
        suppressing_stage,
    )

    print("\nPhase MM complete.")
    print(f"Best candidate: {best_candidate or 'none'}")
    print(f"Quick committee verdict: {quick_verdict}")
    print(f"Layer 5/6 quick audits ran: {ran_layer56}")
    print(f"Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
