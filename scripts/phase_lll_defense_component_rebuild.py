"""Phase LLL — narrow rebuild of composite_regime_defense_component.

Creates no broad search. Runs three GGG1-based production-pipeline candidates
registered in build_improvement_artifacts.py, then gates them against GGG1.
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


ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "01_data_hub"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
JJJ2 = ROOT / "data" / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = ROOT / "data" / "research" / "phase_lll_defense_component_rebuild"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_lll_defense_component_rebuild_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
CANDIDATES = [
    "improved_phaselll_recovery_defense_filter",
    "improved_phaselll_recovery_defense_blend",
    "improved_phaselll_conservative_defense_polish",
]
COMPARE = CANDIDATES + [GGG1, PRODUCTION, SHADOW]
FOCUS_STATES = ["calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
CASH_PROXY = "BIL"
DEFAULT_DEFENSE = ["HYG", "LQD", "GLD", "TLT"]
RC_FILTER = ["HYG", "LQD", "GLD"]
RF_FILTER = ["HYG", "LQD", "TLT"]
MODE_BY_VERSION = {
    GGG1: "ggg1",
    "improved_phaselll_recovery_defense_filter": "filter",
    "improved_phaselll_recovery_defense_blend": "blend",
    "improved_phaselll_conservative_defense_polish": "polish",
}

COMMANDS = [
    "sed -n '1,130p' docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md",
    "python3 - <<'PY' ... summarize KKK sleeve issue diagnostics ...",
    "rg -n 'build_state_conditional_decomposition_sleeve_panels|phaseggg_confirmed_robust|defense_component|internal_redeploy|phaseggg' scripts/build_improvement_artifacts.py | head -n 180",
    "python3 - <<'PY' ... diagnose GGG1 defense ETF contribution by state ...",
    "python3 scripts/phase_lll_defense_component_rebuild.py",
]


def read_time(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    col = "Date" if "Date" in df.columns else df.columns[0]
    df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[col]).set_index(col).sort_index()
    return df.apply(pd.to_numeric, errors="ignore")


def path_df(version: str) -> pd.DataFrame:
    return read_time(L3 / f"portfolio_version_returns_{version}.csv").apply(pd.to_numeric, errors="coerce")


def weights_df(version: str) -> pd.DataFrame:
    return read_time(L3 / f"portfolio_version_weights_{version}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)


def state_series(index: pd.Index) -> pd.Series:
    s = read_time(L2B / "market_state_history.csv")["market_state"]
    return s.reindex(index)


def ann_return(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    if ret.empty:
        return np.nan
    return float((1.0 + ret).prod() ** (52.0 / len(ret)) - 1.0)


def sharpe(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    sd = float(ret.std(ddof=0))
    return float(ret.mean() / sd * np.sqrt(52.0)) if sd > 1e-12 else np.nan


def max_dd(ret: pd.Series) -> float:
    wealth = (1.0 + pd.to_numeric(ret, errors="coerce").fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar5(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    return float(ret[ret <= ret.quantile(0.05)].mean()) if not ret.empty else np.nan


def metrics(version: str) -> dict:
    p = path_df(version)
    w = weights_df(version)
    net = p["net_return"].fillna(0.0)
    return {
        "name": version,
        "ann_return": ann_return(net),
        "ann_vol": float(net.std(ddof=0) * np.sqrt(52.0)),
        "sharpe": sharpe(net),
        "max_drawdown": float(p["drawdown"].min()),
        "calmar": ann_return(net) / abs(float(p["drawdown"].min())) if float(p["drawdown"].min()) < 0 else np.nan,
        "cvar_5": cvar5(net),
        "avg_turnover": float(p["turnover"].fillna(0.0).mean()),
        "avg_BIL": float(w.get("BIL", pd.Series(0.0, index=w.index)).mean()),
        "avg_SPY": float(w.get("SPY", pd.Series(0.0, index=w.index)).mean()),
    }


def state_summary(version: str) -> pd.DataFrame:
    p = path_df(version)
    states = state_series(p.index)
    rows = []
    for st in FOCUS_STATES:
        ret = p.loc[states.eq(st), "net_return"].dropna()
        if len(ret) < 4:
            continue
        rows.append({"candidate": version, "state": st, "n_weeks": len(ret), "ann_return": ann_return(ret), "sharpe": sharpe(ret), "cvar_5": cvar5(ret)})
    return pd.DataFrame(rows)


def project_component(source: pd.DataFrame, state: pd.Series, mode: str) -> pd.DataFrame:
    source = source.copy()
    out = pd.DataFrame(0.0, index=source.index, columns=source.columns)

    def recipe_for(st: str) -> list[tuple[list[str], float]]:
        if mode == "ggg1":
            return [(DEFAULT_DEFENSE, 1.0)]
        if mode == "filter":
            if st == "recovery_confirmed":
                return [(RC_FILTER, 1.0)]
            if st == "recovery_fragile":
                return [(RF_FILTER, 1.0)]
            return [(DEFAULT_DEFENSE, 1.0)]
        if mode == "blend":
            if st == "recovery_confirmed":
                return [(DEFAULT_DEFENSE, 0.5), (RC_FILTER, 0.5)]
            if st == "recovery_fragile":
                return [(DEFAULT_DEFENSE, 0.5), (RF_FILTER, 0.5)]
            return [(DEFAULT_DEFENSE, 1.0)]
        if mode == "polish":
            if st == "recovery_confirmed":
                return [(DEFAULT_DEFENSE, 0.75), (RC_FILTER, 0.25)]
            if st == "recovery_fragile":
                return [(DEFAULT_DEFENSE, 0.75), (RF_FILTER, 0.25)]
            return [(DEFAULT_DEFENSE, 1.0)]
        return [(DEFAULT_DEFENSE, 1.0)]

    for st, idx in state.groupby(state.fillna("__default__")).groups.items():
        dates = pd.Index(idx)
        blended = pd.DataFrame(0.0, index=dates, columns=source.columns)
        total = pd.Series(0.0, index=dates)
        for cols, weight in recipe_for(str(st)):
            cols = [c for c in cols if c in source.columns]
            sub = source.loc[dates, cols]
            denom = sub.sum(axis=1)
            active = denom > 1e-12
            if active.any():
                norm = sub.loc[active].div(denom.loc[active], axis=0)
                blended.loc[norm.index, cols] = blended.loc[norm.index, cols].add(norm * weight, fill_value=0.0)
                total.loc[norm.index] += weight
        active_total = total > 1e-12
        if active_total.any():
            blended.loc[active_total] = blended.loc[active_total].div(total.loc[active_total], axis=0)
        if (~active_total).any():
            blended.loc[~active_total, CASH_PROXY] = 1.0
        out.loc[dates] = blended.values
    return out


def compute_component_path(pos: pd.DataFrame) -> pd.DataFrame:
    ret = read_time(L1 / "weekly_returns.csv").reindex(index=pos.index, columns=pos.columns).fillna(0.0)
    gross = (pos * ret).sum(axis=1).fillna(0.0)
    turnover = pos.diff().abs().sum(axis=1)
    turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * 0.001
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    return pd.DataFrame({"net_return": net, "turnover": turnover, "drawdown": wealth / wealth.cummax() - 1.0}, index=pos.index)


def component_positions(version: str) -> pd.DataFrame:
    source = read_time(L2A / "strategy_positions_composite_regime_conditioned.csv")
    state = state_series(source.index)
    return project_component(source, state, MODE_BY_VERSION.get(version, "ggg1"))


def defense_diagnostics(version: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pos = component_positions(version)
    path = compute_component_path(pos)
    states = state_series(pos.index)
    weekly = read_time(L1 / "weekly_returns.csv")
    diag, contrib = [], []
    for st in FOCUS_STATES:
        idx = states.eq(st)
        ret = path.loc[idx, "net_return"].dropna()
        if len(ret) < 4:
            continue
        diag.append({"candidate": version, "state": st, "n_weeks": len(ret), "ann_return": ann_return(ret), "ann_vol": float(ret.std(ddof=0) * np.sqrt(52.0)), "sharpe": sharpe(ret), "max_drawdown": max_dd(ret), "avg_BIL": float(pos.loc[idx].get("BIL", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_GLD": float(pos.loc[idx].get("GLD", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_HYG": float(pos.loc[idx].get("HYG", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_LQD": float(pos.loc[idx].get("LQD", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_TLT": float(pos.loc[idx].get("TLT", pd.Series(0.0, index=pos.loc[idx].index)).mean())})
        for etf in ["BIL", "GLD", "HYG", "LQD", "TLT"]:
            if etf not in pos.columns or etf not in weekly.columns:
                continue
            x = (pos.loc[idx, etf] * weekly.reindex(pos.index).loc[idx, etf]).dropna()
            contrib.append({"candidate": version, "state": st, "ETF": etf, "avg_weight": float(pos.loc[idx, etf].mean()), "ann_contribution_proxy": ann_return(x), "mean_weekly_contribution": float(x.mean())})
    corr_rows = []
    d_ret = path["net_return"]
    for etf in ["SPY", "BIL", "TLT", "GLD", "LQD", "HYG"]:
        if etf in weekly.columns:
            corr_rows.append({"candidate": version, "reference": etf, "correlation": float(d_ret.corr(weekly[etf].reindex(d_ret.index)))})
    return pd.DataFrame(diag), pd.DataFrame(contrib), pd.DataFrame(corr_rows)


def cost_delay(version: str) -> dict:
    p = path_df(version)
    w = weights_df(version)
    weekly = read_time(L1 / "weekly_returns.csv").reindex(index=w.index, columns=w.columns).fillna(0.0)
    doubled = p["gross_return"].fillna(0.0) - 2.0 * p["cost"].fillna(0.0)
    delayed_gross = (w.shift(1).fillna(w) * weekly).sum(axis=1)
    delayed_turnover = w.shift(1).fillna(0.0).diff().abs().sum(axis=1)
    delayed_net = delayed_gross - delayed_turnover.fillna(0.0) * 0.001
    return {
        "candidate": version,
        "doubled_cost_ann_return": ann_return(doubled),
        "doubled_cost_sharpe": sharpe(doubled),
        "one_week_delay_ann_return": ann_return(delayed_net),
        "one_week_delay_sharpe": sharpe(delayed_net),
    }


def run_build() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    res = subprocess.run([sys.executable, "scripts/build_improvement_artifacts.py"], cwd=ROOT, env=env, text=True, capture_output=True)
    COMMANDS.append("BUILD_VERSION_NAMES=" + env["BUILD_VERSION_NAMES"] + " SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py")
    (OUT / "phase_lll_build_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-120:]) + "\n")
    (OUT / "phase_lll_build_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-120:]) + "\n")
    if res.returncode != 0:
        raise RuntimeError(f"build failed: {res.returncode}")


def run_audits(candidate: str, full: bool) -> dict[str, str]:
    specs = {
        "research_committee": ["scripts/research_committee_report.py", candidate],
        "realism": ["scripts/backtest_realism_audit.py", candidate],
        "allocator": ["scripts/allocator_benchmark_audit.py", candidate],
    }
    if full:
        specs["robustness"] = ["scripts/robustness_simulation_audit.py", candidate]
    out = {}
    for label, args in specs.items():
        cmd = [sys.executable, *args] + ([] if full else ["--quick"])
        COMMANDS.append("python3 " + " ".join(args + ([] if full else ["--quick"])))
        res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        (OUT / f"phase_lll_{label}_audit_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-80:]) + "\n")
        (OUT / f"phase_lll_{label}_audit_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-80:]) + "\n")
        out[label] = "PASS" if res.returncode == 0 else f"FAIL rc={res.returncode}"
    return out


def md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int = 12) -> str:
    small = df[cols].head(max_rows).copy() if cols else df.head(max_rows).copy()
    for col in small.select_dtypes(include=[np.number]).columns:
        small[col] = small[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
    headers = list(small.columns)
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in small.iterrows():
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    if len(df) > max_rows:
        lines.append("| ... | " + " | ".join([""] * (len(headers) - 1)) + " |")
    return "\n".join(lines)


def write(name: str, df: pd.DataFrame) -> pd.DataFrame:
    df.to_csv(OUT / f"{name}.csv", index=False)
    return df


def update_journey(rec: pd.Series, best: str, decision: str) -> None:
    section = f"""

## Section 78 — Phase LLL Defense Component Rebuild

Date: 2026-04-27. Phase LLL tested three GGG1-based Layer 2A rebuilds of only
`composite_regime_defense_component`. GGG1's offense component logic, production
pin, and official shadow pin were unchanged.

**Best candidate.** `{best}` with decision `{decision}`.

**Next action.** `{rec['recommendation']}`.
Reason: {rec['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 78 — Phase LLL Defense Component Rebuild"
    if marker in text:
        text = re.sub(r"\n## Section 78 — Phase LLL Defense Component Rebuild[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    before_diag, before_contrib, before_corr = defense_diagnostics(GGG1)
    before_diag.to_csv(OUT / "phase_lll_defense_component_diagnostics.csv", index=False)
    before_contrib.to_csv(OUT / "phase_lll_defense_component_etf_contribution_by_state.csv", index=False)
    before_corr.to_csv(OUT / "phase_lll_defense_component_correlation_summary.csv", index=False)

    run_build()
    missing = [v for v in CANDIDATES for kind in ["returns", "weights", "sleeve_weights"] if not (L3 / f"portfolio_version_{kind}_{v}.csv").exists()]
    if missing:
        raise FileNotFoundError(f"missing candidate artifacts: {missing[:4]}")

    metrics_df = pd.DataFrame([metrics(v) for v in COMPARE])
    prod_turn = float(metrics_df.loc[metrics_df["name"].eq(PRODUCTION), "avg_turnover"].iloc[0])
    metrics_df["turnover_ratio_vs_production"] = metrics_df["avg_turnover"] / prod_turn
    write("phase_lll_candidate_metrics_full", metrics_df)

    states = pd.concat([state_summary(v) for v in CANDIDATES + [GGG1, PRODUCTION]], ignore_index=True)
    write("phase_lll_state_summary", states)

    diag_rows, contrib_rows, corr_rows = [before_diag], [before_contrib], [before_corr]
    for v in CANDIDATES:
        d, c, r = defense_diagnostics(v)
        diag_rows.append(d); contrib_rows.append(c); corr_rows.append(r)
    all_def = pd.concat(diag_rows, ignore_index=True)
    all_contrib = pd.concat(contrib_rows, ignore_index=True)
    all_corr = pd.concat(corr_rows, ignore_index=True)
    write("phase_lll_defense_component_before_after", all_def)
    write("phase_lll_defense_component_etf_contribution_all", all_contrib)
    write("phase_lll_defense_component_correlation_all", all_corr)

    cost_delay_df = pd.DataFrame([cost_delay(v) for v in CANDIDATES])
    write("phase_lll_candidate_diagnostics", cost_delay_df)

    ggg = metrics_df[metrics_df["name"].eq(GGG1)].iloc[0]
    state_piv = states[states["candidate"].isin(CANDIDATES + [GGG1])].pivot(index="state", columns="candidate", values="ann_return")
    def_piv = all_def[all_def["candidate"].isin(CANDIDATES + [GGG1])].pivot(index="state", columns="candidate", values="ann_return")
    selection_rows = []
    for v in CANDIDATES:
        m = metrics_df[metrics_df["name"].eq(v)].iloc[0]
        guard = {st: float(state_piv.loc[st, v] - state_piv.loc[st, GGG1]) for st in ["recovery_confirmed", "recovery_fragile", "stressed_panic"] if st in state_piv.index}
        def_delta = {st: float(def_piv.loc[st, v] - def_piv.loc[st, GGG1]) for st in ["recovery_confirmed", "recovery_fragile", "stressed_panic"] if st in def_piv.index}
        conditions = {
            "sharpe_not_materially_worse": bool(m["sharpe"] >= ggg["sharpe"] - 0.005),
            "ann_return_not_materially_worse": bool(m["ann_return"] >= ggg["ann_return"] - 0.001),
            "drawdown_not_materially_worse": bool(m["max_drawdown"] >= ggg["max_drawdown"] - 0.0025),
            "cvar_not_materially_worse": bool(m["cvar_5"] >= ggg["cvar_5"] - 0.0005),
            "turnover_under_cap": bool(m["turnover_ratio_vs_production"] <= 1.10),
            "stressed_panic_preserved": bool(guard.get("stressed_panic", 0.0) >= -0.003 and def_delta.get("stressed_panic", 0.0) >= -0.001),
            "recovery_confirmed_not_worse": bool(guard.get("recovery_confirmed", 0.0) >= -0.003),
            "recovery_fragile_not_worse": bool(guard.get("recovery_fragile", 0.0) >= -0.003),
            "hidden_beta_not_higher": bool(m["avg_SPY"] <= ggg["avg_SPY"] + 0.0025),
            "defense_component_improved_in_recovery": bool(def_delta.get("recovery_confirmed", 0.0) > 0.0005 or def_delta.get("recovery_fragile", 0.0) > 0.0005),
        }
        clearly_beats = (
            all(conditions.values())
            and m["sharpe"] > ggg["sharpe"] + 0.002
            and m["ann_return"] >= ggg["ann_return"]
            and m["max_drawdown"] >= ggg["max_drawdown"] - 0.001
        )
        if clearly_beats:
            decision = "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        elif all(conditions.values()):
            decision = "KEEP_AS_SHADOW"
        else:
            decision = "REJECT"
        selection_rows.append({
            "candidate": v,
            **conditions,
            "guard_state_ann_return_deltas": ";".join(f"{k}:{val:.4%}" for k, val in guard.items()),
            "defense_component_ann_return_deltas": ";".join(f"{k}:{val:.4%}" for k, val in def_delta.items()),
            "delta_sharpe_vs_ggg1": float(m["sharpe"] - ggg["sharpe"]),
            "delta_ann_return_vs_ggg1": float(m["ann_return"] - ggg["ann_return"]),
            "decision": decision,
        })
    selection = pd.DataFrame(selection_rows)
    write("phase_lll_selection_table", selection)

    qualified = selection[selection["decision"].isin(["KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"])]
    if qualified.empty:
        best_row = selection.sort_values(["delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=[False, False]).iloc[0]
    else:
        best_row = qualified.sort_values(["delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=[False, False]).iloc[0]
    best = str(best_row["candidate"])
    best_decision = str(best_row["decision"])
    full_audits = best_decision == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
    audits = run_audits(best, full=full_audits) if best_decision in {"KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"} else {"research_committee": "skipped: no candidate qualified", "realism": "skipped", "allocator": "skipped"}

    if best_decision == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW":
        recommendation = "PROMOTE_LLL_OVER_GGG1"
        reason = "A defense rebuild candidate clearly dominated GGG1."
    elif best_decision == "KEEP_AS_SHADOW":
        recommendation = "KEEP_LLL_AS_SHADOW"
        reason = "A defense rebuild improved recovery-state defense drag while preserving GGG1 gates."
    else:
        css_issue = True
        recommendation = "REBUILD_COMPOSITE_SELECTIVE_SIGNALS_NEXT" if css_issue else "KEEP_GGG1_AS_PRODUCTION_CANDIDATE"
        reason = "Defense rebuild candidates did not clearly improve GGG1; KKK's next strongest issue is composite_selective_signals."
    rec = pd.DataFrame([{
        "recommendation": recommendation,
        "best_candidate": best,
        "best_decision": best_decision,
        "reason": reason,
        "defense_component_rebuild_should_continue": best_decision in {"KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"},
        "next_phase_prompt": "Implement a narrow diagnostic-gated rebuild of composite_selective_signals focused only on recovery_confirmed drag; preserve GGG1 offense component logic and production pins." if recommendation == "REBUILD_COMPOSITE_SELECTIVE_SIGNALS_NEXT" else "Keep GGG1 as production candidate and move to packaging/human review.",
    }])
    write("phase_lll_next_action_recommendation", rec)
    protocol = {
        "phase": "LLL",
        "base": GGG1,
        "candidates": CANDIDATES,
        "production_pipeline_build": True,
        "selection_rule": "Reject unless GGG1 full-window, turnover, hidden-beta, stressed-panic, recovery_confirmed, and recovery_fragile gates are preserved and defense recovery drag improves.",
        "best_candidate": best,
        "best_decision": best_decision,
        "audits": audits,
    }
    (OUT / "phase_lll_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")

    lines = [
        "# Phase LLL — Defense Component Rebuild",
        "",
        "Date: 2026-04-27",
        "",
        "## Commands executed",
        "```",
        *COMMANDS,
        "```",
        "",
        "## Files created / modified",
        "- `scripts/build_improvement_artifacts.py`",
        "- `scripts/phase_lll_defense_component_rebuild.py`",
        "- `data/research/phase_lll_defense_component_rebuild/*`",
        "- `data/05_layer3_portfolio_construction/portfolio_version_*_improved_phaselll_*.csv`",
        "- `docs/research/2026-04-27_phase_lll_defense_component_rebuild_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## Defense component diagnosis",
        md_table(before_diag, ["candidate", "state", "ann_return", "sharpe", "avg_GLD", "avg_HYG", "avg_LQD", "avg_TLT"], 8),
        "",
        "## Internal ETF findings",
        md_table(before_contrib.sort_values(["state", "ann_contribution_proxy"]), ["state", "ETF", "avg_weight", "ann_contribution_proxy"], 15),
        "",
        "## Candidate metrics",
        md_table(metrics_df, ["name", "ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover_ratio_vs_production", "avg_BIL", "avg_SPY"], 8),
        "",
        "## Defense component before / after",
        md_table(all_def[all_def["state"].isin(["recovery_confirmed", "recovery_fragile", "stressed_panic"])], ["candidate", "state", "ann_return", "sharpe", "avg_GLD", "avg_HYG", "avg_LQD", "avg_TLT"], 16),
        "",
        "## Selection table",
        md_table(selection, ["candidate", "decision", "delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1", "turnover_under_cap", "stressed_panic_preserved", "recovery_confirmed_not_worse", "recovery_fragile_not_worse", "hidden_beta_not_higher"], 6),
        "",
        "## Candidate diagnostics",
        md_table(cost_delay_df, ["candidate", "doubled_cost_sharpe", "one_week_delay_sharpe"], 6),
        "",
        "## Audit results",
        *[f"- {k}: {v}" for k, v in audits.items()],
        "",
        "## Final decision",
        f"**{recommendation}**",
        "",
        f"Best candidate: `{best}` (`{best_decision}`).",
        "",
        f"Reason: {reason}",
        "",
        f"Defense component rebuild should continue: **{bool(rec.iloc[0]['defense_component_rebuild_should_continue'])}**.",
        "",
        "## Exact prompt outline for the next phase",
        str(rec.iloc[0]["next_phase_prompt"]),
    ]
    DOC.write_text("\n".join(lines) + "\n")
    update_journey(rec.iloc[0], best, best_decision)
    print(f"best_candidate: {best}")
    print(f"best_decision: {best_decision}")
    print(f"recommendation: {recommendation}")


if __name__ == "__main__":
    main()
