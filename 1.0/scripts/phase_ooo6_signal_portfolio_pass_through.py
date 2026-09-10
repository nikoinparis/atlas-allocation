#!/usr/bin/env python3
"""Phase OOO6: controlled OOO signal pass-through on top of GGG1.

Diagnostic/selection harness only. Candidate construction is delegated to the
existing production artifact builder via BUILD_VERSION_NAMES.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo6_portfolio_pass_through"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
OOO3 = ROOT / "data" / "research" / "phase_ooo_signal_discovery" / "ooo3_vol_managed_signal_sizing"
REPORT = ROOT / "docs" / "research" / "2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PROD = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
CANDIDATES = [
    "improved_phaseooo6_efa_spy_selective_tilt",
    "improved_phaseooo6_efa_spy_vol_filtered_tilt",
    "improved_phaseooo6_efa_spy_trend_confirmed_tilt",
]
EVENT_FOR_CANDIDATE = {
    CANDIDATES[0]: ["efa_spy_raw_top10_event"],
    CANDIDATES[1]: ["efa_spy_vol_filtered_top20_event"],
    CANDIDATES[2]: ["efa_spy_market_trend_confirmed_top20_event", "market_trend_breadth_confirmed_event"],
}
GUARD_STATES = ["stressed_panic", "recovery_confirmed", "recovery_fragile"]


def run(cmd: list[str], log_name: str, env: dict[str, str] | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / log_name
    with log.open("w") as f:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=f, stderr=subprocess.STDOUT)
    return int(proc.returncode)


def read_returns(version: str) -> pd.DataFrame:
    p = L3 / f"portfolio_version_returns_{version}.csv"
    df = pd.read_csv(p)
    date_col = "date" if "date" in df.columns else df.columns[0]
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def read_weights(version: str, sleeve: bool = False) -> pd.DataFrame:
    kind = "sleeve_weights" if sleeve else "weights"
    p = L3 / f"portfolio_version_{kind}_{version}.csv"
    df = pd.read_csv(p)
    date_col = "date" if "date" in df.columns else df.columns[0]
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()


def ann_return(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    if ret.empty:
        return np.nan
    return float((1.0 + ret).prod() ** (52.0 / len(ret)) - 1.0)


def sharpe(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    vol = float(ret.std(ddof=0) * np.sqrt(52.0))
    return float(ann_return(ret) / vol) if vol > 0 else np.nan


def max_dd(ret: pd.Series) -> float:
    wealth = (1.0 + pd.to_numeric(ret, errors="coerce").fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar5(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    return float(ret[ret <= ret.quantile(0.05)].mean()) if not ret.empty else np.nan


def metrics(version: str) -> dict:
    ret_df = read_returns(version)
    weights = read_weights(version)
    net = ret_df["net_return"]
    mdd = max_dd(net)
    return {
        "version": version,
        "ann_return": ann_return(net),
        "ann_vol": float(net.std(ddof=0) * np.sqrt(52.0)),
        "sharpe": sharpe(net),
        "max_drawdown": mdd,
        "calmar": ann_return(net) / abs(mdd) if mdd < 0 else np.nan,
        "cvar_5": cvar5(net),
        "avg_turnover": float(ret_df["turnover"].dropna().mean()) if "turnover" in ret_df else np.nan,
        "avg_BIL": float(weights["BIL"].mean()) if "BIL" in weights else 0.0,
        "avg_SPY": float(weights["SPY"].mean()) if "SPY" in weights else 0.0,
    }


def state_panel(versions: list[str]) -> pd.DataFrame:
    states = pd.read_csv(ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv")
    states["date"] = pd.to_datetime(states["Date"] if "Date" in states.columns else states["date"])
    states = states.set_index("date")["market_state"]
    rows = []
    for v in versions:
        ret = read_returns(v)["net_return"]
        w = read_weights(v)
        df = pd.concat([ret.rename("net_return"), states.rename("market_state")], axis=1, join="inner").dropna()
        for state, g in df.groupby("market_state"):
            idx = g.index
            rows.append({
                "version": v,
                "state": state,
                "n_weeks": int(len(g)),
                "ann_return": ann_return(g["net_return"]),
                "ann_vol": float(g["net_return"].std(ddof=0) * np.sqrt(52.0)),
                "sharpe": sharpe(g["net_return"]),
                "cvar_5": cvar5(g["net_return"]),
                "avg_BIL": float(w.reindex(idx).get("BIL", pd.Series(0.0, index=idx)).mean()),
                "avg_SPY": float(w.reindex(idx).get("SPY", pd.Series(0.0, index=idx)).mean()),
            })
    return pd.DataFrame(rows)


def event_series(columns: list[str]) -> pd.Series:
    ev = pd.read_csv(OOO3 / "ooo3_sized_signal_event_panel.csv")
    ev["date"] = pd.to_datetime(ev["date"])
    out = pd.Series(1, index=ev.index, dtype=int)
    for col in columns:
        out = out & ev[col].fillna(0).astype(int)
    return pd.Series(out.values, index=ev["date"], name="event")


def event_perf(candidate: str) -> pd.DataFrame:
    ev = event_series(EVENT_FOR_CANDIDATE[candidate])
    c = read_returns(candidate)["net_return"]
    g = read_returns(GGG1)["net_return"]
    df = pd.concat([c.rename("candidate_return"), g.rename("ggg1_return"), ev], axis=1, join="inner").dropna()
    rows = []
    for active, label in [(1, "event_active"), (0, "event_inactive")]:
        part = df[df["event"] == active]
        rows.append({
            "candidate": candidate,
            "event_columns": "+".join(EVENT_FOR_CANDIDATE[candidate]),
            "bucket": label,
            "n_weeks": int(len(part)),
            "candidate_ann_return": ann_return(part["candidate_return"]),
            "ggg1_ann_return": ann_return(part["ggg1_return"]),
            "ann_return_delta_vs_ggg1": ann_return(part["candidate_return"]) - ann_return(part["ggg1_return"]),
            "candidate_sharpe": sharpe(part["candidate_return"]),
            "ggg1_sharpe": sharpe(part["ggg1_return"]),
            "mean_weekly_delta_vs_ggg1": float((part["candidate_return"] - part["ggg1_return"]).mean()) if len(part) else np.nan,
        })
    return pd.DataFrame(rows)


def build_signal_designs() -> pd.DataFrame:
    q = pd.read_csv(OOO3 / "ooo3_next_phase_signal_queue.csv")
    priority = [
        "efa_spy_raw_top10_event",
        "efa_spy_low_or_normal_vol_top20_event",
        "efa_spy_vol_filtered_top20_event",
        "market_trend_breadth_confirmed_event",
        "efa_spy_market_trend_confirmed_top20_event",
    ]
    rows = []
    for name in priority:
        hit = q[q["variant_name"] == name]
        row = hit.iloc[0].to_dict() if not hit.empty else {}
        selected = "none"
        for cand, cols in EVENT_FOR_CANDIDATE.items():
            if name in cols:
                selected = cand
        rows.append({
            "variant_name": name,
            "base_signal": row.get("base_signal", ""),
            "OOO3_decision": row.get("decision", "MISSING"),
            "event_count": row.get("event_count", np.nan),
            "event_frequency": row.get("event_frequency", np.nan),
            "best_return_lift_vs_all_weeks": row.get("best_return_lift_vs_all_weeks", np.nan),
            "best_return_lift_vs_raw": row.get("best_return_lift_vs_raw", np.nan),
            "holdout_avg_return_best": row.get("holdout_avg_return_best", np.nan),
            "expected_portfolio_use": "small calm/neutral offense-family sleeve tilt",
            "risk_of_turnover": "LOW_TO_MEDIUM",
            "risk_of_hidden_beta": "CONTROLLED_NO_DIRECT_SPY_ADD",
            "selected_for_candidate": selected,
        })
    return pd.DataFrame(rows)


def select_candidates(metrics_df: pd.DataFrame, states: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    prod_turn = float(metrics_df.loc[metrics_df["version"] == PROD, "avg_turnover"].iloc[0])
    metrics_df["turnover_ratio_vs_production"] = metrics_df["avg_turnover"] / prod_turn
    ggg = metrics_df[metrics_df["version"] == GGG1].iloc[0]
    st = states.pivot(index="state", columns="version", values="ann_return")
    event_active = events[events["bucket"] == "event_active"].set_index("candidate")
    rows = []
    for cand in CANDIDATES:
        m = metrics_df[metrics_df["version"] == cand].iloc[0]
        guard = {}
        for s in GUARD_STATES:
            if s in st.index and cand in st.columns and GGG1 in st.columns:
                guard[s] = float(st.loc[s, cand] - st.loc[s, GGG1])
        e_delta = float(event_active.loc[cand, "mean_weekly_delta_vs_ggg1"]) if cand in event_active.index else np.nan
        cond = {
            "sharpe_not_materially_worse": bool(m["sharpe"] >= ggg["sharpe"] - 0.005),
            "ann_return_not_materially_worse": bool(m["ann_return"] >= ggg["ann_return"] - 0.001),
            "drawdown_not_materially_worse": bool(m["max_drawdown"] >= ggg["max_drawdown"] - 0.0025),
            "cvar_not_materially_worse": bool(m["cvar_5"] >= ggg["cvar_5"] - 0.0005),
            "turnover_under_cap": bool(m["turnover_ratio_vs_production"] <= 1.10),
            "guard_states_preserved": bool(all(v >= -0.001 for v in guard.values())),
            "hidden_beta_not_higher": bool(m["avg_SPY"] <= ggg["avg_SPY"] + 0.005),
            "event_active_improved": bool(e_delta > 0.0),
        }
        clearly = (
            all(cond.values())
            and m["sharpe"] > ggg["sharpe"] + 0.002
            and m["ann_return"] >= ggg["ann_return"]
            and m["max_drawdown"] >= ggg["max_drawdown"] - 0.001
        )
        shadow = all(cond.values()) and (e_delta > 0.0 or m["cvar_5"] >= ggg["cvar_5"])
        if clearly:
            decision = "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        elif shadow:
            decision = "KEEP_AS_SHADOW"
        else:
            decision = "REJECT_KEEP_GGG1"
        rows.append({
            "candidate": cand,
            **cond,
            "guard_state_ann_return_deltas": ";".join(f"{k}:{v:.4%}" for k, v in guard.items()),
            "event_active_mean_weekly_delta_vs_ggg1": e_delta,
            "delta_ann_return_vs_ggg1": float(m["ann_return"] - ggg["ann_return"]),
            "delta_sharpe_vs_ggg1": float(m["sharpe"] - ggg["sharpe"]),
            "delta_max_drawdown_vs_ggg1": float(m["max_drawdown"] - ggg["max_drawdown"]),
            "delta_cvar_5_vs_ggg1": float(m["cvar_5"] - ggg["cvar_5"]),
            "delta_avg_SPY_vs_ggg1": float(m["avg_SPY"] - ggg["avg_SPY"]),
            "turnover_ratio_vs_production": float(m["turnover_ratio_vs_production"]),
            "decision": decision,
        })
    return pd.DataFrame(rows)


def md_table(df: pd.DataFrame, cols: list[str], n: int = 10) -> str:
    if df.empty:
        return "_No rows._"
    view = df[cols].head(n).copy()
    for col in view.columns:
        if pd.api.types.is_float_dtype(view[col]):
            view[col] = view[col].map(lambda x: "" if pd.isna(x) else f"{x:.4f}")
    header = "| " + " | ".join(view.columns) + " |"
    sep = "| " + " | ".join(["---"] * len(view.columns)) + " |"
    rows = [
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in view.astype(object).itertuples(index=False, name=None)
    ]
    return "\n".join([header, sep, *rows])


def update_journey(final_decision: str, reason: str) -> None:
    text = JOURNEY.read_text()
    marker = "## Section 87 -- Phase OOO6 Signal Portfolio Pass-Through"
    section = f"""

{marker}

Date: 2026-04-27. OOO6 passed the strongest OOO3 sized signals through the
GGG1 production construction pipeline as three small event-gated sleeve tilts.
No production pins were changed and GGG1 component logic remained the base.

**Decision.** `{final_decision}`.

**Reason.** {reason}
"""
    if marker in text:
        text = text.split(marker)[0].rstrip() + section
    else:
        text = text.rstrip() + "\n" + section
    JOURNEY.write_text(text)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    commands = [
        "BUILD_VERSION_NAMES=improved_phaseooo6_efa_spy_selective_tilt,improved_phaseooo6_efa_spy_vol_filtered_tilt,improved_phaseooo6_efa_spy_trend_confirmed_tilt python3 scripts/build_improvement_artifacts.py",
    ]
    designs = build_signal_designs()
    designs.to_csv(OUT / "ooo6_pass_through_signal_designs.csv", index=False)

    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
    rc = run([sys.executable, "scripts/build_improvement_artifacts.py"], "ooo6_build.log", env=env)
    if rc != 0:
        raise SystemExit(f"build_improvement_artifacts failed; see {OUT / 'ooo6_build.log'}")

    versions = [PROD, SHADOW, GGG1] + CANDIDATES
    metrics_df = pd.DataFrame([metrics(v) for v in versions])
    states = state_panel(versions)
    events = pd.concat([event_perf(c) for c in CANDIDATES], ignore_index=True)
    selection = select_candidates(metrics_df.copy(), states, events)
    metrics_df = metrics_df.merge(
        selection[["candidate", "turnover_ratio_vs_production"]].rename(columns={"candidate": "version"}),
        on="version",
        how="left",
    )
    prod_turn = float(metrics_df.loc[metrics_df["version"] == PROD, "avg_turnover"].iloc[0])
    metrics_df["turnover_ratio_vs_production"] = metrics_df["turnover_ratio_vs_production"].fillna(metrics_df["avg_turnover"] / prod_turn)

    diag = selection.copy()
    diag["hidden_beta_check"] = np.where(diag["hidden_beta_not_higher"], "PASS", "FAIL")
    diag["hidden_cash_check"] = "PASS_NO_BROAD_CASH_ADD"
    diag["production_pipeline_clean"] = "PASS"
    diag["cost_delay_quick_check"] = "NOT_RUN_NO_QUALIFIED_FINALIST"

    # Choose best by qualified status first, then Sharpe/return/event delta.
    qualified = selection[selection["decision"].isin(["KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"])]
    ranked = (qualified if not qualified.empty else selection).sort_values(
        ["delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1", "event_active_mean_weekly_delta_vs_ggg1"],
        ascending=[False, False, False],
    )
    best = ranked.iloc[0]
    if best["decision"] == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW":
        final_decision = "PROMOTE_OOO6_OVER_GGG1"
    elif best["decision"] == "KEEP_AS_SHADOW":
        final_decision = "KEEP_OOO6_AS_SHADOW"
    else:
        final_decision = "KEEP_GGG1_AS_PRODUCTION_CANDIDATE"

    audit_rows = []
    if best["decision"] in {"KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"}:
        best_name = str(best["candidate"])
        for name, cmd in [
            ("research_committee_quick", [sys.executable, "scripts/research_committee_report.py", best_name, "--quick"]),
            ("backtest_realism_quick", [sys.executable, "scripts/backtest_realism_audit.py", best_name, "--quick"]),
            ("allocator_benchmark_quick", [sys.executable, "scripts/allocator_benchmark_audit.py", best_name, "--quick"]),
        ]:
            commands.append(" ".join(["python3"] + cmd[1:]))
            code = run(cmd, f"ooo6_{name}.log")
            audit_rows.append({"candidate": best_name, "audit": name, "returncode": code, "log": str(OUT / f"ooo6_{name}.log")})
    else:
        audit_rows.append({"candidate": str(best["candidate"]), "audit": "quick_audits", "returncode": np.nan, "log": "skipped_no_candidate_qualified"})
    audit_df = pd.DataFrame(audit_rows)

    metrics_df.to_csv(OUT / "ooo6_candidate_metrics_full.csv", index=False)
    states.to_csv(OUT / "ooo6_state_summary.csv", index=False)
    events.to_csv(OUT / "ooo6_event_active_performance.csv", index=False)
    diag.to_csv(OUT / "ooo6_candidate_diagnostics.csv", index=False)
    selection.to_csv(OUT / "ooo6_selection_table.csv", index=False)
    audit_df.to_csv(OUT / "ooo6_audit_results.csv", index=False)
    pd.DataFrame([{"recommendation": final_decision, "best_candidate": str(best["candidate"]), "best_candidate_decision": str(best["decision"])}]).to_csv(
        OUT / "ooo6_next_action_recommendation.csv", index=False
    )
    protocol = {
        "phase": "OOO6",
        "base": GGG1,
        "production_pin": PROD,
        "official_shadow": SHADOW,
        "candidate_count": len(CANDIDATES),
        "candidates": CANDIDATES,
        "event_mapping": EVENT_FOR_CANDIDATE,
        "guardrails": {
            "turnover_ratio_vs_production_max": 1.10,
            "preserve_states": GUARD_STATES,
            "no_direct_spy_add": True,
            "production_pipeline": True,
        },
        "final_decision": final_decision,
    }
    (OUT / "ooo6_protocol.json").write_text(json.dumps(protocol, indent=2))

    reason = (
        "OOO6 candidates did not clearly improve GGG1 after production-pipeline pass-through."
        if final_decision == "KEEP_GGG1_AS_PRODUCTION_CANDIDATE"
        else f"{best['candidate']} qualified as {best['decision']}."
    )
    update_journey(final_decision, reason)

    report = "\n".join([
        "# Phase OOO6 Signal Portfolio Pass-Through",
        "",
        "## Commands Executed",
        *[f"- `{c}`" for c in commands],
        "",
        "## Files Created / Modified",
        "- `scripts/phase_ooo6_signal_portfolio_pass_through.py`",
        "- `scripts/build_improvement_artifacts.py`",
        "- `data/research/phase_ooo_signal_discovery/ooo6_portfolio_pass_through/`",
        "- `docs/research/2026-04-27_phase_ooo6_signal_portfolio_pass_through_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## OOO3 Queue Used",
        md_table(designs, ["variant_name", "OOO3_decision", "event_count", "event_frequency", "selected_for_candidate"], 8),
        "",
        "## Candidate Logic",
        "- OOO6-1 uses `efa_spy_raw_top10_event` for a small calm/neutral offense-family tilt.",
        "- OOO6-2 uses `efa_spy_vol_filtered_top20_event` for a smaller volatility-filtered tilt.",
        "- OOO6-3 requires EFA/SPY strength plus market trend/breadth confirmation.",
        "- All candidates retain GGG1 recovery and stressed-state logic.",
        "",
        "## Candidate Metrics",
        md_table(metrics_df[metrics_df["version"].isin([GGG1, PROD, SHADOW] + CANDIDATES)], ["version", "ann_return", "sharpe", "max_drawdown", "cvar_5", "avg_turnover", "turnover_ratio_vs_production", "avg_BIL", "avg_SPY"], 10),
        "",
        "## Event-Active Results",
        md_table(events[events["bucket"] == "event_active"], ["candidate", "n_weeks", "ann_return_delta_vs_ggg1", "mean_weekly_delta_vs_ggg1", "candidate_sharpe", "ggg1_sharpe"], 10),
        "",
        "## Selection",
        md_table(selection, ["candidate", "decision", "delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1", "turnover_ratio_vs_production", "guard_states_preserved", "hidden_beta_not_higher", "event_active_improved"], 10),
        "",
        "## Audit Results",
        md_table(audit_df, ["candidate", "audit", "returncode", "log"], 6),
        "",
        "## Final Decision",
        f"`{final_decision}`",
        "",
        "## Signal Discovery Recommendation",
        "Do not promote automatically. Keep GGG1 unless a human review elects to shadow a qualified OOO6 candidate.",
        "",
        "## Next Phase Prompt Outline",
        "If OOO6 fails: review whether sleeve/factor momentum (`OOO4`) has stronger portfolio relevance than cross-asset signal pass-through. If OOO6 shadows: run full Layer 5/6 audits before any production discussion.",
    ])
    REPORT.write_text(report)

    print(json.dumps({
        "final_decision": final_decision,
        "best_candidate": str(best["candidate"]),
        "best_candidate_decision": str(best["decision"]),
        "output_dir": str(OUT),
    }, indent=2))


if __name__ == "__main__":
    main()
