"""Phase JJJ3 — one targeted lookthrough repair candidate.

Creates at most one production-pipeline candidate:
improved_phasejjj3_targeted_lookthrough_repair.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
import re

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "01_data_hub"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
JJJ2 = ROOT / "data" / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = ROOT / "data" / "research" / "phase_jjj3_targeted_lookthrough_repair"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_jjj3_targeted_lookthrough_repair_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
EEE1 = "improved_phaseeee_smoothed_near_exclude_dual"
CANDIDATE = "improved_phasejjj3_targeted_lookthrough_repair"
VERSIONS = [CANDIDATE, GGG1, PRODUCTION, SHADOW, EEE1]

FAVORABLE_STATES = {"calm_trend", "neutral_mixed", "neutral_healthy", "recovery_confirmed", "recovery_fragile"}
STATE_GUARDS = ["stressed_panic", "recovery_confirmed", "recovery_fragile"]
CASH_ETFS = {"BIL", "SHY"}
OFFENSE_ETFS = {"SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "EEM", "VTV", "VUG", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
DEFENSE_ETFS = {"TLT", "IEF", "LQD", "MBB", "TIP", "HYG"}
COMMODITY_ETFS = {"GLD", "IAU", "SLV", "PDBC", "DBA", "USO", "UUP"}
COMPONENTS = {"composite_regime_offense_component", "composite_regime_defense_component", "composite_regime_cash_component"}

def json_scalar(value):
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def md_table(df: pd.DataFrame, max_rows: int = 30) -> str:
    small = df.head(max_rows).copy()
    for col in small.select_dtypes(include=[np.number]).columns:
        small[col] = small[col].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
    cols = list(small.columns)
    rows = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in small.iterrows():
        rows.append("| " + " | ".join(str(row[col]) for col in cols) + " |")
    if len(df) > max_rows:
        rows.append(f"| ... {len(df) - max_rows} more rows | " + " | ".join([""] * (len(cols) - 1)) + " |")
    return "\n".join(rows)


COMMANDS: list[str] = [
    "sed -n '1,180p' docs/research/2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md",
    "python3 - <<'PY' ... inspect JJJ2 drag summaries ...",
    "sed -n '360,430p' scripts/build_improvement_artifacts.py",
    "sed -n '1020,1225p' scripts/build_improvement_artifacts.py",
    "sed -n '9685,9745p' scripts/build_improvement_artifacts.py",
    "python3 scripts/phase_jjj3_targeted_lookthrough_repair.py",
]


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


def ann_return(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float((1 + s).prod() ** (52 / len(s)) - 1) if len(s) else np.nan


def ann_vol(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    return float(s.std(ddof=1) * np.sqrt(52)) if len(s) > 1 else np.nan


def sharpe(s: pd.Series) -> float:
    v = ann_vol(s)
    return ann_return(s) / v if v and np.isfinite(v) and v > 0 else np.nan


def max_dd(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    wealth = (1 + s).cumprod()
    return float((wealth / wealth.cummax() - 1).min()) if len(wealth) else np.nan


def cvar5(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    if s.empty:
        return np.nan
    q = s.quantile(0.05)
    return float(s[s <= q].mean())


def calmar(s: pd.Series) -> float:
    mdd = max_dd(s)
    return ann_return(s) / abs(mdd) if mdd and np.isfinite(mdd) and mdd < 0 else np.nan


def metrics(version: str) -> dict:
    ret = read_time_csv(L3 / f"portfolio_version_returns_{version}.csv")
    w = read_time_csv(L3 / f"portfolio_version_weights_{version}.csv")
    s = ret["net_return"]
    out = {
        "name": version,
        "ann_return": ann_return(s),
        "ann_vol": ann_vol(s),
        "sharpe": sharpe(s),
        "max_drawdown": max_dd(s),
        "calmar": calmar(s),
        "cvar_5": cvar5(s),
        "avg_turnover": float(w.diff().abs().sum(axis=1).fillna(0.0).mean()),
        "avg_BIL": float(w["BIL"].mean()) if "BIL" in w else np.nan,
        "avg_SPY": float(w["SPY"].mean()) if "SPY" in w else np.nan,
    }
    return out


def etf_role(etf: str) -> str:
    if etf in CASH_ETFS:
        return "cash"
    if etf in OFFENSE_ETFS:
        return "offense"
    if etf in DEFENSE_ETFS:
        return "defense"
    if etf in COMMODITY_ETFS:
        return "commodity"
    return "unknown"


def sleeve_role(sleeve: str) -> str:
    if sleeve == "cash::BIL" or sleeve.endswith("cash_component"):
        return "cash"
    if sleeve in {"taa_10m_sma", "composite_regime_defense_component"}:
        return "defense"
    if sleeve in {"dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component"}:
        return "offense"
    if sleeve == "composite_regime_conditioned":
        return "mixed"
    return "unknown"


def load_component_positions() -> dict[str, pd.DataFrame]:
    path = JJJ2 / f"component_positions_{GGG1}.csv"
    long = pd.read_csv(path, parse_dates=["Date"])
    out = {}
    for comp, sub in long.groupby("component"):
        out[comp] = sub.pivot_table(index="Date", columns="ETF", values="weight", aggfunc="sum").fillna(0.0)
        out[comp].index = pd.to_datetime(out[comp].index).tz_localize(None)
    return out


def load_positions(sleeve: str, component_positions: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    if sleeve in component_positions:
        return component_positions[sleeve]
    if sleeve == "cash::BIL":
        weekly = read_time_csv(L1 / "weekly_returns.csv")
        return pd.DataFrame({"BIL": 1.0}, index=weekly.index)
    p = L2A / f"strategy_positions_{sleeve}.csv"
    return read_time_csv(p) if p.exists() else None


def contribution_summary(version: str, state: pd.DataFrame) -> pd.DataFrame:
    sleeves = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{version}.csv")
    comp_pos = load_component_positions() if version in {GGG1, CANDIDATE} else {}
    rows = []
    for sleeve in sleeves.columns:
        pos = load_positions(sleeve, comp_pos)
        if pos is None:
            continue
        joined = sleeves[[sleeve]].join(pos, how="inner").join(state[["market_state"]], how="left")
        etfs = [c for c in pos.columns if c in joined.columns]
        contrib = joined[etfs].mul(joined[sleeve], axis=0)
        daily = pd.DataFrame({
            "sleeve_weight": joined[sleeve],
            "offense": contrib[[c for c in etfs if etf_role(c) == "offense"]].sum(axis=1) if any(etf_role(c) == "offense" for c in etfs) else 0.0,
            "defense": contrib[[c for c in etfs if etf_role(c) == "defense"]].sum(axis=1) if any(etf_role(c) == "defense" for c in etfs) else 0.0,
            "cash": contrib[[c for c in etfs if etf_role(c) == "cash"]].sum(axis=1) if any(etf_role(c) == "cash" for c in etfs) else 0.0,
            "commodity": contrib[[c for c in etfs if etf_role(c) == "commodity"]].sum(axis=1) if any(etf_role(c) == "commodity" for c in etfs) else 0.0,
            "SPY": contrib["SPY"] if "SPY" in contrib else 0.0,
            "BIL": contrib["BIL"] if "BIL" in contrib else 0.0,
            "market_state": joined["market_state"],
        })
        for st, sub in daily.groupby("market_state"):
            role = sleeve_role(sleeve)
            offense_drag = max(0.0, float(sub["sleeve_weight"].mean() - sub["offense"].mean())) if role == "offense" else 0.0
            rows.append({
                "version": version,
                "market_state": st,
                "sleeve": sleeve,
                "intended_role": role,
                "avg_sleeve_weight": float(sub["sleeve_weight"].mean()),
                "offense_contribution": float(sub["offense"].mean()),
                "defense_contribution": float(sub["defense"].mean()),
                "cash_contribution": float(sub["cash"].mean()),
                "commodity_contribution": float(sub["commodity"].mean()),
                "SPY_contribution": float(sub["SPY"].mean()),
                "BIL_contribution": float(sub["BIL"].mean()),
                "lookthrough_offense_drag": offense_drag,
            })
    return pd.DataFrame(rows)


def state_summary(version: str, state: pd.DataFrame) -> pd.DataFrame:
    ret = read_time_csv(L3 / f"portfolio_version_returns_{version}.csv")[["net_return"]].join(state[["market_state"]], how="inner").dropna()
    rows = []
    for st, sub in ret.groupby("market_state"):
        rows.append({"candidate": version, "state": st, "n_weeks": int(len(sub)), "ann_return": ann_return(sub["net_return"]), "sharpe": sharpe(sub["net_return"]), "vol_wkly": float(sub["net_return"].std()), "mean_wkly": float(sub["net_return"].mean())})
    return pd.DataFrame(rows)


def run_build() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = CANDIDATE
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    cmd = [sys.executable, str(ROOT / "scripts" / "build_improvement_artifacts.py")]
    COMMANDS.append("BUILD_VERSION_NAMES=improved_phasejjj3_targeted_lookthrough_repair SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py")
    res = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True, timeout=2400)
    (OUT / "phase_jjj3_build_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-40:]) + "\n")
    (OUT / "phase_jjj3_build_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-80:]) + "\n")
    if res.returncode != 0:
        raise RuntimeError(f"build_improvement_artifacts.py failed with {res.returncode}; see build stderr tail")


def run_quick_audits(selection_verdict: str) -> dict[str, str]:
    if selection_verdict == "REJECT":
        return {"research_committee": "skipped: candidate rejected by selection rule", "realism": "skipped", "allocator": "skipped"}
    audit_cmds = [
        ("research_committee", [sys.executable, "scripts/research_committee_report.py", CANDIDATE, "--quick"]),
        ("realism", [sys.executable, "scripts/backtest_realism_audit.py", CANDIDATE, "--quick"]),
        ("allocator", [sys.executable, "scripts/allocator_benchmark_audit.py", CANDIDATE, "--quick"]),
    ]
    out = {}
    for label, cmd in audit_cmds:
        COMMANDS.append(" ".join(["python3" if x == sys.executable else x for x in cmd]))
        res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=1200)
        out[label] = "passed" if res.returncode == 0 else f"failed rc={res.returncode}"
        (OUT / f"phase_jjj3_{label}_audit_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-40:]) + "\n")
        (OUT / f"phase_jjj3_{label}_audit_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-80:]) + "\n")
    return out


def write_report(outputs: dict[str, pd.DataFrame], audit_results: dict[str, str], final_decision: str) -> None:
    metrics_df = outputs["phase_jjj3_candidate_metrics_full"]
    effect = outputs["phase_jjj3_lookthrough_repair_effect"]
    rec = outputs["phase_jjj3_next_action_recommendation"].iloc[0]
    diagnosis = outputs["phase_jjj3_top_drag_path_diagnosis"].iloc[0]
    lines = [
        "# Phase JJJ3 — Targeted Lookthrough Repair",
        "",
        "Date: 2026-04-27",
        "Author: research stream",
        "",
        "## Commands executed",
        "```",
        *COMMANDS,
        "```",
        "",
        "## Files created / modified",
        "- `scripts/build_improvement_artifacts.py`",
        "- `scripts/phase_jjj3_targeted_lookthrough_repair.py`",
        "- `data/research/phase_jjj3_targeted_lookthrough_repair/*.csv`",
        "- `docs/research/2026-04-27_phase_jjj3_targeted_lookthrough_repair_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## Top drag path identified",
        f"- Version: `{diagnosis['version']}`",
        f"- State: `{diagnosis['market_state']}`",
        f"- Sleeve: `{diagnosis['sleeve']}`",
        f"- Drag: {diagnosis['lookthrough_offense_drag']:.4f}",
        f"- Classification: `{diagnosis['classification']}`",
        "",
        "## Candidate",
        "- Created: `improved_phasejjj3_targeted_lookthrough_repair`",
        "- Logic: GGG1 plus only a calm_trend cap on `composite_selective_signals` share of the offense bucket at 30%; excess stays within offense-family sleeves: 70% to `composite_regime_offense_component`, 30% to `cta_trend_long_only`.",
        "",
        "## Metrics",
        md_table(metrics_df),
        "",
        "## Targeted drag before vs after",
        md_table(effect),
        "",
        "## State guardrails",
        md_table(outputs["phase_jjj3_state_summary"]),
        "",
        "## Hidden beta / cash / turnover",
        "- See metrics table: avg SPY, avg BIL, and turnover ratio are included.",
        "",
        "## Audit results",
        *[f"- {k}: {v}" for k, v in audit_results.items()],
        "",
        "## Final decision",
        f"**{final_decision}**",
        "",
        "## Next action recommendation",
        f"**{rec['recommendation']}**",
        "",
        f"Reason: {rec['reason']}",
        "",
        f"Safe to proceed to adaptive risk-contribution allocation: **{bool(rec['safe_to_proceed_to_adaptive_risk_contribution'])}**.",
        "",
        "## Exact prompt outline for the next phase",
        rec["next_phase_prompt"],
    ]
    DOC.write_text("\n".join(lines) + "\n")


def update_journey(rec: pd.DataFrame, final_decision: str) -> None:
    r = rec.iloc[0]
    section = f"""

## Section 75 — Phase JJJ3 Targeted Lookthrough Repair

Date: 2026-04-27. Phase JJJ3 tested one diagnostic-gated repair candidate:
`improved_phasejjj3_targeted_lookthrough_repair`. It preserved GGG1's
state-conditional component logic and touched only the confirmed top drag path:
`calm_trend / composite_selective_signals`.

**Repair.** In calm_trend only, cap `composite_selective_signals` at 30% of the
offense bucket and reallocate excess inside the existing offense-family sleeves
to `composite_regime_offense_component` and `cta_trend_long_only`. No production
or official shadow pin changed.

**Decision.** `{final_decision}`.

**Next action.** `{r['recommendation']}`. Safe to proceed to adaptive
risk-contribution allocation: `{bool(r['safe_to_proceed_to_adaptive_risk_contribution'])}`.
Reason: {r['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 75 — Phase JJJ3 Targeted Lookthrough Repair"
    if marker in text:
        text = re.sub(r"\n## Section 75 — Phase JJJ3 Targeted Lookthrough Repair[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    state = read_time_csv(L2B / "market_state_history.csv")

    fav = pd.read_csv(JJJ2 / "phase_jjj2_favorable_state_drag_sources.csv")
    cls = pd.read_csv(JJJ2 / "phase_jjj2_drag_classification.csv")
    top = fav[(fav["version"].eq(GGG1)) & (fav["market_state"].isin(FAVORABLE_STATES))].sort_values("lookthrough_offense_drag", ascending=False).iloc[0].to_dict()
    c = cls[(cls["version"].eq(GGG1)) & (cls["market_state"].eq(top["market_state"])) & (cls["sleeve"].eq(top["sleeve"]))]
    top["classification"] = c.iloc[0]["classification"] if not c.empty else "NEEDS_REVIEW"
    diagnosis = pd.DataFrame([top])
    diagnosis.to_csv(OUT / "phase_jjj3_top_drag_path_diagnosis.csv", index=False)

    if not (top["market_state"] == "calm_trend" and top["sleeve"] == "composite_selective_signals" and top["classification"] == "ACCIDENTAL_GOOD_STATE_DRAG"):
        skip = pd.DataFrame([{"recommendation": "NEEDS_MORE_INSTRUMENTATION", "safe_to_proceed_to_adaptive_risk_contribution": False, "reason": "Top drag path did not match a safe one-path repair rule.", "next_phase_prompt": "Reinspect JJJ2 path classification before implementation."}])
        skip.to_csv(OUT / "phase_jjj3_next_action_recommendation.csv", index=False)
        pd.DataFrame([{"candidate_created": False, "reason": "no safe repair supported"}]).to_csv(OUT / "phase_jjj3_selection_table.csv", index=False)
        raise SystemExit("No safe repair supported; wrote skip recommendation.")

    run_build()

    metric_rows = [metrics(v) for v in [CANDIDATE, GGG1, PRODUCTION, SHADOW] if (L3 / f"portfolio_version_returns_{v}.csv").exists()]
    metrics_df = pd.DataFrame(metric_rows)
    prod_turn = float(metrics_df.loc[metrics_df["name"].eq(PRODUCTION), "avg_turnover"].iloc[0])
    metrics_df["turnover_ratio_vs_production"] = metrics_df["avg_turnover"] / prod_turn
    metrics_df.to_csv(OUT / "phase_jjj3_candidate_metrics_full.csv", index=False)

    states = pd.concat([state_summary(v, state) for v in [CANDIDATE, GGG1, PRODUCTION]], ignore_index=True)
    states.to_csv(OUT / "phase_jjj3_state_summary.csv", index=False)

    before = contribution_summary(GGG1, state)
    after = contribution_summary(CANDIDATE, state)
    key_cols = ["market_state", "sleeve"]
    effect = before.merge(after, on=key_cols, suffixes=("_before_ggg1", "_after_jjj3"))
    effect = effect[(effect["market_state"].eq(top["market_state"])) & (effect["sleeve"].eq(top["sleeve"]))]
    effect["delta_lookthrough_offense_drag"] = effect["lookthrough_offense_drag_after_jjj3"] - effect["lookthrough_offense_drag_before_ggg1"]
    effect["targeted_drag_reduced"] = effect["delta_lookthrough_offense_drag"] < -1e-6
    effect.to_csv(OUT / "phase_jjj3_lookthrough_repair_effect.csv", index=False)

    cand = metrics_df[metrics_df["name"].eq(CANDIDATE)].iloc[0]
    ggg = metrics_df[metrics_df["name"].eq(GGG1)].iloc[0]
    state_pivot = states.pivot(index="state", columns="candidate", values="ann_return")
    guard_ok = True
    guard_notes = []
    for st in STATE_GUARDS:
        if st in state_pivot.index:
            delta = float(state_pivot.loc[st, CANDIDATE] - state_pivot.loc[st, GGG1])
            guard_notes.append(f"{st}:{delta:+.4%}")
            if delta < -0.003:
                guard_ok = False
    target_reduced = bool(effect["targeted_drag_reduced"].iloc[0]) if not effect.empty else False
    conditions = {
        "target_drag_reduced": target_reduced,
        "sharpe_not_materially_worse": cand["sharpe"] >= ggg["sharpe"] - 0.005,
        "ann_return_not_materially_worse": cand["ann_return"] >= ggg["ann_return"] - 0.001,
        "drawdown_not_materially_worse": cand["max_drawdown"] >= ggg["max_drawdown"] - 0.0025,
        "cvar_not_materially_worse": cand["cvar_5"] >= ggg["cvar_5"] - 0.0005,
        "turnover_under_cap": cand["turnover_ratio_vs_production"] <= 1.10,
        "state_guardrails_preserved": guard_ok,
        "hidden_beta_not_higher": cand["avg_SPY"] <= ggg["avg_SPY"] + 0.0025,
    }
    clearly_better = (
        conditions["target_drag_reduced"]
        and cand["sharpe"] > ggg["sharpe"] + 0.001
        and cand["ann_return"] >= ggg["ann_return"]
        and cand["max_drawdown"] >= ggg["max_drawdown"] - 0.0005
    )
    if not all(conditions.values()):
        final_decision = "REJECT"
        recommendation = "KEEP_GGG1_AND_PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION"
        reason = "The one-path repair did not clear all selection gates; keep GGG1."
        safe = True
    elif clearly_better:
        final_decision = "KEEP_AS_SHADOW"
        recommendation = "PROMOTE_JJJ3_OVER_GGG1"
        reason = "JJJ3 reduces target drag and improves GGG1 metrics without breaking gates."
        safe = False
    else:
        final_decision = "KEEP_AS_SHADOW"
        recommendation = "KEEP_GGG1_AND_PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION"
        reason = "JJJ3 reduced target drag but did not clearly dominate GGG1."
        safe = True

    selection = pd.DataFrame([{**conditions, "guard_state_ann_return_deltas": ";".join(guard_notes), "final_decision": final_decision}])
    selection.to_csv(OUT / "phase_jjj3_selection_table.csv", index=False)
    protocol = {
        "phase": "JJJ3",
        "candidate": CANDIDATE,
        "base": GGG1,
        "repair": "calm_trend composite_selective_signals offense-bucket share cap 0.30; excess 70% composite_regime_offense_component / 30% cta_trend_long_only",
        "conditions": conditions,
        "final_decision": final_decision,
    }
    (OUT / "phase_jjj3_protocol.json").write_text(json.dumps(protocol, indent=2, default=json_scalar) + "\n")

    audit_results = run_quick_audits(final_decision)
    rec_df = pd.DataFrame([{
        "recommendation": recommendation,
        "safe_to_proceed_to_adaptive_risk_contribution": safe,
        "reason": reason,
        "next_phase_prompt": "Proceed to a narrowly scoped adaptive risk-contribution allocator test using GGG1 as the base and JJJ diagnostics as constraints; do not promote JJJ3 unless human review wants a shadow-only diagnostic." if safe else "Run full JJJ3 audits only if human review wants to challenge GGG1.",
    }])
    rec_df.to_csv(OUT / "phase_jjj3_next_action_recommendation.csv", index=False)

    outputs = {
        "phase_jjj3_top_drag_path_diagnosis": diagnosis,
        "phase_jjj3_candidate_metrics_full": metrics_df,
        "phase_jjj3_state_summary": states,
        "phase_jjj3_lookthrough_repair_effect": effect,
        "phase_jjj3_selection_table": selection,
        "phase_jjj3_next_action_recommendation": rec_df,
    }
    write_report(outputs, audit_results, final_decision)
    update_journey(rec_df, final_decision)
    print(f"candidate: {CANDIDATE}")
    print(f"final_decision: {final_decision}")
    print(f"recommendation: {recommendation}")
    print(f"target_drag_reduced: {target_reduced}")


if __name__ == "__main__":
    main()
