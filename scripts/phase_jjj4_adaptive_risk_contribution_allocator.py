"""Phase JJJ4 — adaptive risk-contribution allocator test.

Narrowly tests three GGG1-based allocator variants already registered in
build_improvement_artifacts.py. This script does not reconstruct ETF weights
post hoc; it invokes the production construction pipeline, then evaluates the
generated return/weight/sleeve artifacts.
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
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
JJJ2 = ROOT / "data" / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = ROOT / "data" / "research" / "phase_jjj4_adaptive_risk_contribution_allocator"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
CANDIDATES = [
    "improved_phasejjj4_state_risk_contribution_caps",
    "improved_phasejjj4_adaptive_mom_vol_corr_budget",
    "improved_phasejjj4_conservative_adaptive_risk_budget",
]
COMPARE = CANDIDATES + [GGG1, PRODUCTION, SHADOW]
GUARD_STATES = ["recovery_confirmed", "recovery_fragile", "stressed_panic"]
FOCUS_STATES = ["calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]

COMMANDS: list[str] = [
    "sed -n '1,160p' docs/research/2026-04-27_phase_jjj3_targeted_lookthrough_repair_report.md",
    "sed -n '1,120p' docs/research/2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md",
    "rg -n 'phaseggg|phase_jjj3|state_tilt|internal_redeploy|version_name|apply_state_conditioned_tilt|risk' scripts/build_improvement_artifacts.py | head -n 120",
    "python3 - <<'PY' ... inspect GGG1 sleeve risk contribution ...",
    "python3 scripts/phase_jjj4_adaptive_risk_contribution_allocator.py",
]


def read_path(version: str) -> pd.DataFrame:
    p = L3 / f"portfolio_version_returns_{version}.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    return df.apply(pd.to_numeric, errors="coerce")


def read_weights(version: str) -> pd.DataFrame:
    p = L3 / f"portfolio_version_weights_{version}.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_csv(p, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce").fillna(0.0)


def read_sleeves(version: str) -> pd.DataFrame:
    p = L3 / f"portfolio_version_sleeve_weights_{version}.csv"
    if not p.exists():
        raise FileNotFoundError(p)
    return pd.read_csv(p, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce").fillna(0.0)


def state_series(index: pd.Index) -> pd.Series:
    state = pd.read_csv(L2B / "market_state_history.csv", index_col=0, parse_dates=True)
    return state["market_state"].reindex(index)


def ann_return(net: pd.Series) -> float:
    net = net.dropna()
    if net.empty:
        return np.nan
    wealth = float((1.0 + net).prod())
    return wealth ** (52.0 / len(net)) - 1.0


def sharpe(net: pd.Series) -> float:
    sd = float(net.std(ddof=0))
    return float(net.mean() / sd * np.sqrt(52.0)) if sd > 1e-12 else np.nan


def metrics(version: str) -> dict:
    path = read_path(version)
    w = read_weights(version)
    net = path["net_return"].fillna(0.0)
    return {
        "name": version,
        "ann_return": ann_return(net),
        "ann_vol": float(net.std(ddof=0) * np.sqrt(52.0)),
        "sharpe": sharpe(net),
        "max_drawdown": float(path["drawdown"].min()),
        "calmar": ann_return(net) / abs(float(path["drawdown"].min())) if float(path["drawdown"].min()) < 0 else np.nan,
        "cvar_5": float(net[net <= net.quantile(0.05)].mean()),
        "avg_turnover": float(path["turnover"].fillna(0.0).mean()),
        "avg_BIL": float(w.get("BIL", pd.Series(0.0, index=w.index)).mean()),
        "avg_SPY": float(w.get("SPY", pd.Series(0.0, index=w.index)).mean()),
    }


def state_summary(version: str) -> pd.DataFrame:
    path = read_path(version)
    states = state_series(path.index)
    rows = []
    for st in FOCUS_STATES:
        ret = path.loc[states.eq(st), "net_return"].dropna()
        if ret.empty:
            continue
        rows.append({
            "candidate": version,
            "state": st,
            "n_weeks": len(ret),
            "ann_return": ann_return(ret),
            "ann_vol": float(ret.std(ddof=0) * np.sqrt(52.0)),
            "sharpe": sharpe(ret),
            "cvar_5": float(ret[ret <= ret.quantile(0.05)].mean()),
        })
    return pd.DataFrame(rows)


def sleeve_return_panel(version: str, index: pd.Index) -> pd.DataFrame:
    sleeves = read_sleeves(version).columns
    data: dict[str, pd.Series] = {}
    comp_path = JJJ2 / f"component_returns_{GGG1}.csv"
    comp = pd.read_csv(comp_path, index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce") if comp_path.exists() else pd.DataFrame()
    weekly = pd.read_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv", index_col=0, parse_dates=True).apply(pd.to_numeric, errors="coerce")
    for sleeve in sleeves:
        if sleeve == "cash::BIL":
            data[sleeve] = weekly.get("BIL", pd.Series(0.0, index=index))
            continue
        if sleeve in comp.columns:
            data[sleeve] = comp[sleeve]
            continue
        p = L2A / f"strategy_returns_{sleeve}.csv"
        if p.exists():
            raw = pd.read_csv(p, index_col=0, parse_dates=True)
            data[sleeve] = pd.to_numeric(raw.iloc[:, 0], errors="coerce")
    return pd.DataFrame(data).reindex(index).fillna(0.0)


def risk_contribution(version: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    w = read_sleeves(version)
    r = sleeve_return_panel(version, w.index).reindex(columns=w.columns).fillna(0.0)
    states = state_series(w.index)
    rc_rows, quality_rows, conc_rows = [], [], []
    for st in ["full_window"] + FOCUS_STATES:
        mask = pd.Series(True, index=w.index) if st == "full_window" else states.eq(st)
        if int(mask.sum()) < 8:
            continue
        ww = w.loc[mask]
        rr = r.loc[mask]
        avg_w = ww.mean().reindex(rr.columns).fillna(0.0)
        cov = rr.cov() * 52.0
        mrc = cov.dot(avg_w)
        port_var = float(avg_w.dot(mrc))
        rc = (avg_w * mrc / port_var).replace([np.inf, -np.inf], np.nan).fillna(0.0) if port_var > 1e-12 else avg_w * 0.0
        ann = rr.mean() * 52.0
        vol = rr.std(ddof=0) * np.sqrt(52.0)
        shp = ann.div(vol.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        for sleeve in rr.columns:
            rc_rows.append({
                "candidate": version, "state": st, "sleeve": sleeve,
                "avg_weight": float(avg_w.get(sleeve, 0.0)),
                "risk_contribution": float(rc.get(sleeve, 0.0)),
                "risk_minus_weight": float(rc.get(sleeve, 0.0) - avg_w.get(sleeve, 0.0)),
                "return_contribution_proxy": float(avg_w.get(sleeve, 0.0) * ann.get(sleeve, 0.0)),
            })
            quality_rows.append({
                "candidate": version, "state": st, "sleeve": sleeve,
                "ann_return": float(ann.get(sleeve, np.nan)),
                "ann_vol": float(vol.get(sleeve, np.nan)),
                "sharpe": float(shp.get(sleeve, np.nan)) if pd.notna(shp.get(sleeve, np.nan)) else np.nan,
            })
        conc_rows.append({
            "candidate": version,
            "state": st,
            "risk_herfindahl": float((rc.clip(lower=0.0) ** 2).sum()),
            "top_risk_sleeve": str(rc.sort_values(ascending=False).index[0]),
            "top_risk_contribution": float(rc.max()),
            "avg_pairwise_corr": float(rr.corr().where(~np.eye(len(rr.columns), dtype=bool)).stack().mean()),
        })
    corr = r.corr().reset_index().rename(columns={"index": "sleeve"})
    corr.insert(0, "candidate", version)
    return pd.DataFrame(rc_rows), pd.DataFrame(quality_rows), pd.DataFrame(conc_rows), corr


def run_build() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    cmd = [sys.executable, "scripts/build_improvement_artifacts.py"]
    res = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    COMMANDS.append("BUILD_VERSION_NAMES=" + env["BUILD_VERSION_NAMES"] + " SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py")
    (OUT / "phase_jjj4_build_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-120:]) + "\n")
    (OUT / "phase_jjj4_build_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-120:]) + "\n")
    if res.returncode != 0:
        raise RuntimeError(f"build_improvement_artifacts failed: {res.returncode}")


def run_audit(candidate: str, full: bool = False) -> dict[str, str]:
    audits = {
        "research_committee": ["scripts/research_committee_report.py", candidate],
        "realism": ["scripts/backtest_realism_audit.py", candidate],
        "allocator": ["scripts/allocator_benchmark_audit.py", candidate],
    }
    if full:
        audits["robustness"] = ["scripts/robustness_simulation_audit.py", candidate]
    results = {}
    for label, args in audits.items():
        cmd = [sys.executable, *args] + ([] if full else ["--quick"])
        COMMANDS.append("python3 " + " ".join(args + ([] if full else ["--quick"])))
        res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        (OUT / f"phase_jjj4_{label}_audit_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-100:]) + "\n")
        (OUT / f"phase_jjj4_{label}_audit_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-100:]) + "\n")
        results[label] = "PASS" if res.returncode == 0 else f"FAIL rc={res.returncode}"
    return results


def md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int = 12) -> str:
    small = df[cols].head(max_rows).copy() if cols else df.head(max_rows).copy()
    for col in small.select_dtypes(include=[np.number]).columns:
        small[col] = small[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
    headers = list(small.columns)
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for _, row in small.iterrows():
        out.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(out)


def write_outputs(name: str, df: pd.DataFrame) -> None:
    df.to_csv(OUT / f"{name}.csv", index=False)
    df.to_csv(L3 / f"{name}.csv", index=False)


def update_journey(rec: pd.Series, best: str, best_decision: str) -> None:
    section = f"""

## Section 76 — Phase JJJ4 Adaptive Risk-Contribution Allocator

Date: 2026-04-27. Phase JJJ4 tested three controlled GGG1-based adaptive
risk-contribution allocator variants through the production construction
pipeline. The production pin and official shadow pin were unchanged.

**Best candidate.** `{best}` with decision `{best_decision}`.

**Next action.** `{rec['recommendation']}`.
Reason: {rec['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 76 — Phase JJJ4 Adaptive Risk-Contribution Allocator"
    if marker in text:
        text = re.sub(r"\n## Section 76 — Phase JJJ4 Adaptive Risk-Contribution Allocator[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    run_build()

    missing = [v for v in CANDIDATES for suffix in ["returns", "weights", "sleeve_weights"] if not (L3 / f"portfolio_version_{suffix}_{v}.csv").exists()]
    if missing:
        raise FileNotFoundError(f"missing candidate artifacts: {missing[:5]}")

    metrics_df = pd.DataFrame([metrics(v) for v in COMPARE])
    prod_turn = float(metrics_df.loc[metrics_df["name"].eq(PRODUCTION), "avg_turnover"].iloc[0])
    metrics_df["turnover_ratio_vs_production"] = metrics_df["avg_turnover"] / prod_turn
    write_outputs("phase_jjj4_candidate_metrics_full", metrics_df)

    states = pd.concat([state_summary(v) for v in CANDIDATES + [GGG1, PRODUCTION]], ignore_index=True)
    write_outputs("phase_jjj4_state_summary", states)

    rc_all, qual_all, conc_all, corr_all = [], [], [], []
    for v in CANDIDATES + [GGG1, PRODUCTION, SHADOW]:
        rc, qual, conc, corr = risk_contribution(v)
        rc_all.append(rc); qual_all.append(qual); conc_all.append(conc); corr_all.append(corr)
    rc_df = pd.concat(rc_all, ignore_index=True)
    qual_df = pd.concat(qual_all, ignore_index=True)
    conc_df = pd.concat(conc_all, ignore_index=True)
    corr_df = pd.concat(corr_all, ignore_index=True)
    write_outputs("phase_jjj4_candidate_risk_contribution", rc_df)
    write_outputs("phase_jjj4_sleeve_return_quality_by_state", qual_df)
    write_outputs("phase_jjj4_candidate_concentration_diagnostics", conc_df)
    write_outputs("phase_jjj4_sleeve_correlation_matrix", corr_df)

    ggg = metrics_df[metrics_df["name"].eq(GGG1)].iloc[0]
    ggg_conc = conc_df[(conc_df["candidate"].eq(GGG1)) & (conc_df["state"].eq("full_window"))].iloc[0]
    selection_rows = []
    for cand_name in CANDIDATES:
        cand = metrics_df[metrics_df["name"].eq(cand_name)].iloc[0]
        c_conc = conc_df[(conc_df["candidate"].eq(cand_name)) & (conc_df["state"].eq("full_window"))].iloc[0]
        st_piv = states[states["candidate"].isin([cand_name, GGG1])].pivot(index="state", columns="candidate", values="ann_return")
        guard_deltas = {st: float(st_piv.loc[st, cand_name] - st_piv.loc[st, GGG1]) for st in GUARD_STATES if st in st_piv.index}
        conditions = {
            "sharpe_not_materially_worse": bool(cand["sharpe"] >= ggg["sharpe"] - 0.005),
            "ann_return_not_materially_worse": bool(cand["ann_return"] >= ggg["ann_return"] - 0.001),
            "drawdown_not_materially_worse": bool(cand["max_drawdown"] >= ggg["max_drawdown"] - 0.0025),
            "cvar_not_materially_worse": bool(cand["cvar_5"] >= ggg["cvar_5"] - 0.0005),
            "turnover_under_cap": bool(cand["turnover_ratio_vs_production"] <= 1.10),
            "guard_states_preserved": bool(all(v >= -0.003 for v in guard_deltas.values())),
            "hidden_beta_not_higher": bool(cand["avg_SPY"] <= ggg["avg_SPY"] + 0.0025),
            "concentration_not_worse": bool(c_conc["risk_herfindahl"] <= ggg_conc["risk_herfindahl"] + 0.005),
        }
        clearly_beats = (
            cand["sharpe"] > ggg["sharpe"] + 0.002
            and cand["ann_return"] >= ggg["ann_return"]
            and cand["max_drawdown"] >= ggg["max_drawdown"] - 0.001
            and cand["turnover_ratio_vs_production"] <= 1.10
        )
        de_risks = c_conc["risk_herfindahl"] < ggg_conc["risk_herfindahl"] - 0.003 and all(conditions.values())
        if clearly_beats:
            decision = "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        elif de_risks:
            decision = "KEEP_AS_SHADOW"
        else:
            decision = "REJECT"
        selection_rows.append({
            "candidate": cand_name,
            **conditions,
            "guard_state_ann_return_deltas": ";".join(f"{k}:{v:.4%}" for k, v in guard_deltas.items()),
            "risk_herfindahl": float(c_conc["risk_herfindahl"]),
            "delta_risk_herfindahl_vs_ggg1": float(c_conc["risk_herfindahl"] - ggg_conc["risk_herfindahl"]),
            "delta_sharpe_vs_ggg1": float(cand["sharpe"] - ggg["sharpe"]),
            "delta_ann_return_vs_ggg1": float(cand["ann_return"] - ggg["ann_return"]),
            "decision": decision,
        })
    selection = pd.DataFrame(selection_rows)
    write_outputs("phase_jjj4_selection_table", selection)

    ranked = selection.assign(rank_score=selection["delta_sharpe_vs_ggg1"] + selection["delta_ann_return_vs_ggg1"] - selection["delta_risk_herfindahl_vs_ggg1"].clip(lower=0.0))
    best_row = ranked.sort_values(["decision", "rank_score"], ascending=[True, False]).iloc[0]
    qualified = selection[selection["decision"].isin(["KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"])]
    if not qualified.empty:
        best_row = qualified.sort_values(["delta_sharpe_vs_ggg1", "delta_risk_herfindahl_vs_ggg1"], ascending=[False, True]).iloc[0]
    best = str(best_row["candidate"])
    best_decision = str(best_row["decision"])

    full_audits = best_decision == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
    audits = run_audit(best, full=full_audits) if best_decision in {"KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"} else {"research_committee": "skipped: no candidate qualified", "realism": "skipped", "allocator": "skipped"}

    if best_decision == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW":
        recommendation = "PROMOTE_JJJ4_OVER_GGG1"
        reason = "A JJJ4 candidate clearly beat GGG1 while preserving risk and turnover gates."
    elif best_decision == "KEEP_AS_SHADOW":
        recommendation = "KEEP_JJJ4_AS_SHADOW"
        reason = "A JJJ4 candidate reduced risk concentration while preserving GGG1-quality gates."
    else:
        recommendation = "KEEP_GGG1_AS_PRODUCTION_CANDIDATE"
        reason = "No adaptive risk-contribution candidate clearly improved or de-risked GGG1."

    rec = pd.DataFrame([{
        "recommendation": recommendation,
        "best_candidate": best,
        "best_decision": best_decision,
        "reason": reason,
        "adaptive_risk_contribution_should_continue": recommendation != "KEEP_GGG1_AS_PRODUCTION_CANDIDATE",
        "next_phase_prompt": "Keep GGG1 as production candidate; do not force allocator changes. Next work should be packaging/human review unless a separate Layer 2A sleeve-design hypothesis is explicitly requested.",
    }])
    write_outputs("phase_jjj4_next_action_recommendation", rec)
    protocol = {
        "phase": "JJJ4",
        "base": GGG1,
        "candidates": CANDIDATES,
        "production_pipeline_build": True,
        "selection_rule": "Reject unless GGG1-level Sharpe/return/tail/state/turnover/hidden-beta gates are preserved and concentration improves or full metrics clearly dominate.",
        "best_candidate": best,
        "best_decision": best_decision,
        "audits": audits,
    }
    (OUT / "phase_jjj4_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")
    (L3 / "phase_jjj4_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")

    lines = [
        "# Phase JJJ4 — Adaptive Risk-Contribution Allocator",
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
        "- `scripts/phase_jjj4_adaptive_risk_contribution_allocator.py`",
        "- `data/research/phase_jjj4_adaptive_risk_contribution_allocator/*`",
        "- `data/05_layer3_portfolio_construction/phase_jjj4_*.csv`",
        "- `docs/research/2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## Candidate metrics",
        md_table(metrics_df, ["name", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "turnover_ratio_vs_production", "avg_BIL", "avg_SPY"]),
        "",
        "## Selection table",
        md_table(selection, ["candidate", "decision", "delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1", "delta_risk_herfindahl_vs_ggg1", "turnover_under_cap", "guard_states_preserved", "hidden_beta_not_higher"]),
        "",
        "## Risk-contribution diagnosis",
        md_table(rc_df[(rc_df["candidate"].eq(GGG1)) & (rc_df["state"].isin(["full_window", "recovery_confirmed", "recovery_fragile", "stressed_panic"]))].sort_values(["state", "risk_contribution"], ascending=[True, False]), ["state", "sleeve", "avg_weight", "risk_contribution", "risk_minus_weight", "return_contribution_proxy"], 18),
        "",
        "## Concentration results",
        md_table(conc_df[conc_df["candidate"].isin(CANDIDATES + [GGG1])], ["candidate", "state", "risk_herfindahl", "top_risk_sleeve", "top_risk_contribution", "avg_pairwise_corr"], 24),
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
        "## Answers",
        f"- Did any JJJ4 candidate beat GGG1? {'Yes' if best_decision == 'PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW' else 'No'}.",
        f"- Did any candidate reduce concentration or tail risk without hurting Sharpe? {'Yes' if best_decision == 'KEEP_AS_SHADOW' else 'No'}.",
        f"- Did turnover stay under 1.10x production? {bool(selection['turnover_under_cap'].all())}.",
        f"- Did guard states stay protected? {bool(selection['guard_states_preserved'].all())}.",
        f"- Was improvement hidden beta or real? Hidden beta gate passed for all candidates: {bool(selection['hidden_beta_not_higher'].all())}.",
        f"- Adaptive risk-contribution allocation should continue: {bool(rec.iloc[0]['adaptive_risk_contribution_should_continue'])}.",
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
