"""Phase MMM — narrow composite_selective_signals rebuild.

Tests at most three GGG1-based CSS variants through the production pipeline.
No production/shadow pins are changed.
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
OUT = ROOT / "data" / "research" / "phase_mmm_composite_selective_signals_rebuild"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_mmm_composite_selective_signals_rebuild_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
CANDIDATES = [
    "improved_phasemmm_recovery_confirmed_css_cap",
    "improved_phasemmm_recovery_confirmed_css_filter",
    "improved_phasemmm_conservative_css_polish",
]
COMPARE = CANDIDATES + [GGG1, PRODUCTION, SHADOW]
FOCUS_STATES = ["calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
FILTER_KEEP = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "HYG", "LQD", "GLD", "PDBC", "BIL"]
FILTER_VERSION = "improved_phasemmm_recovery_confirmed_css_filter"

COMMANDS = [
    "sed -n '1,130p' docs/research/2026-04-27_phase_lll_defense_component_rebuild_report.md",
    "python3 - <<'PY' ... inspect KKK/LLL diagnostics and CSS internals ...",
    "rg -n 'composite_selective_signals|selective_strategy_name|phase_mmm' scripts/build_improvement_artifacts.py | head -n 160",
    "python3 scripts/phase_mmm_composite_selective_signals_rebuild.py",
]


def read_time(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    col = "Date" if "Date" in df.columns else df.columns[0]
    df[col] = pd.to_datetime(df[col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[col]).set_index(col).sort_index()
    for c in df.columns:
        converted = pd.to_numeric(df[c], errors="coerce")
        if converted.notna().sum() >= max(1, int(df[c].notna().sum() * 0.8)):
            df[c] = converted
    return df


def path_df(version: str) -> pd.DataFrame:
    return read_time(L3 / f"portfolio_version_returns_{version}.csv").apply(pd.to_numeric, errors="coerce")


def weights_df(version: str) -> pd.DataFrame:
    return read_time(L3 / f"portfolio_version_weights_{version}.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)


def state_series(index: pd.Index) -> pd.Series:
    return read_time(L2B / "market_state_history.csv")["market_state"].reindex(index)


def ann_return(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    return float((1.0 + ret).prod() ** (52.0 / len(ret)) - 1.0) if len(ret) else np.nan


def sharpe(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    sd = float(ret.std(ddof=0))
    return float(ret.mean() / sd * np.sqrt(52.0)) if sd > 1e-12 else np.nan


def max_dd(ret: pd.Series) -> float:
    wealth = (1.0 + pd.to_numeric(ret, errors="coerce").fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min()) if len(wealth) else np.nan


def cvar5(ret: pd.Series) -> float:
    ret = pd.to_numeric(ret, errors="coerce").dropna()
    return float(ret[ret <= ret.quantile(0.05)].mean()) if len(ret) else np.nan


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


def css_positions(version: str = GGG1) -> pd.DataFrame:
    pos = read_time(L2A / "strategy_positions_composite_selective_signals.csv").apply(pd.to_numeric, errors="coerce").fillna(0.0)
    if version != FILTER_VERSION:
        return pos
    states = state_series(pos.index)
    out = pos.copy()
    idx = states.eq("recovery_confirmed")
    keep = [c for c in FILTER_KEEP if c in out.columns]
    denom = out.loc[idx, keep].sum(axis=1)
    active = denom > 1e-12
    dates = denom.index[active]
    out.loc[idx, :] = 0.0
    out.loc[dates, keep] = pos.loc[dates, keep].div(denom.loc[dates], axis=0)
    inactive_dates = denom.index[~active]
    if len(inactive_dates) and "BIL" in out.columns:
        out.loc[inactive_dates, "BIL"] = 1.0
    return out


def css_path(version: str = GGG1) -> pd.DataFrame:
    pos = css_positions(version)
    wr = read_time(L1 / "weekly_returns.csv").shift(-1).reindex(index=pos.index, columns=pos.columns).fillna(0.0)
    gross = (pos * wr).sum(axis=1).fillna(0.0)
    turnover = pos.diff().abs().sum(axis=1)
    turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * 0.001
    net = gross - cost
    wealth = (1.0 + net).cumprod()
    return pd.DataFrame({"net_return": net, "turnover": turnover, "drawdown": wealth / wealth.cummax() - 1.0}, index=pos.index)


def css_diagnostics(version: str = GGG1) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pos = css_positions(version)
    path = css_path(version)
    wr = read_time(L1 / "weekly_returns.csv").shift(-1)
    states = state_series(pos.index)
    diag, contrib = [], []
    for st in FOCUS_STATES:
        idx = states.eq(st)
        ret = path.loc[idx, "net_return"].dropna()
        if len(ret) < 4:
            continue
        diag.append({"candidate": version, "state": st, "n_weeks": len(ret), "ann_return": ann_return(ret), "ann_vol": float(ret.std(ddof=0) * np.sqrt(52.0)), "sharpe": sharpe(ret), "max_drawdown": max_dd(ret), "avg_BIL": float(pos.loc[idx].get("BIL", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_SPY": float(pos.loc[idx].get("SPY", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_DBA": float(pos.loc[idx].get("DBA", pd.Series(0.0, index=pos.loc[idx].index)).mean()), "avg_TLT": float(pos.loc[idx].get("TLT", pd.Series(0.0, index=pos.loc[idx].index)).mean())})
        for etf in pos.columns:
            if etf not in wr.columns:
                continue
            x = (pos.loc[idx, etf] * wr.reindex(pos.index).loc[idx, etf]).dropna()
            if len(x):
                contrib.append({"candidate": version, "state": st, "ETF": etf, "avg_weight": float(pos.loc[idx, etf].mean()), "ann_contribution_proxy": ann_return(x), "mean_weekly_contribution": float(x.mean())})
    refs = {"SPY": wr.get("SPY"), "BIL": wr.get("BIL")}
    for name in ["composite_regime_offense_component", "dual_momentum_topn", "cta_trend_long_only"]:
        p = L2A / f"strategy_returns_{name}.csv"
        if p.exists():
            refs[name] = read_time(p)["net_return"]
    corr_rows = []
    ret = path["net_return"]
    for ref, series in refs.items():
        if series is not None:
            corr_rows.append({"candidate": version, "reference": ref, "correlation": float(ret.corr(series.reindex(ret.index)))})
    usefulness = pd.DataFrame(diag).assign(usefulness_flag=lambda d: np.select([d["sharpe"] >= 0.6, d["ann_return"] < 0.0], ["USEFUL", "HARMFUL"], default="MIXED"))
    return pd.DataFrame(diag), pd.DataFrame(contrib), pd.DataFrame(corr_rows), usefulness


def cost_delay(version: str) -> dict:
    p = path_df(version)
    w = weights_df(version)
    wr = read_time(L1 / "weekly_returns.csv").shift(-1).reindex(index=w.index, columns=w.columns).fillna(0.0)
    doubled = p["gross_return"].fillna(0.0) - 2.0 * p["cost"].fillna(0.0)
    delayed_gross = (w.shift(1).fillna(w) * wr).sum(axis=1)
    delayed_turnover = w.shift(1).fillna(0.0).diff().abs().sum(axis=1)
    delayed_net = delayed_gross - delayed_turnover.fillna(0.0) * 0.001
    return {"candidate": version, "doubled_cost_ann_return": ann_return(doubled), "doubled_cost_sharpe": sharpe(doubled), "one_week_delay_ann_return": ann_return(delayed_net), "one_week_delay_sharpe": sharpe(delayed_net)}


def run_build() -> None:
    env = os.environ.copy()
    env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
    env["SAVE_ALLOCATOR_CHECKPOINTS"] = "1"
    res = subprocess.run([sys.executable, "scripts/build_improvement_artifacts.py"], cwd=ROOT, env=env, text=True, capture_output=True)
    COMMANDS.append("BUILD_VERSION_NAMES=" + env["BUILD_VERSION_NAMES"] + " SAVE_ALLOCATOR_CHECKPOINTS=1 python3 scripts/build_improvement_artifacts.py")
    (OUT / "phase_mmm_build_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-120:]) + "\n")
    (OUT / "phase_mmm_build_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-120:]) + "\n")
    if res.returncode != 0:
        raise RuntimeError(f"build failed: {res.returncode}")


def run_audits(candidate: str, full: bool) -> dict[str, str]:
    specs = {"research_committee": ["scripts/research_committee_report.py", candidate], "realism": ["scripts/backtest_realism_audit.py", candidate], "allocator": ["scripts/allocator_benchmark_audit.py", candidate]}
    if full:
        specs["robustness"] = ["scripts/robustness_simulation_audit.py", candidate]
    out = {}
    for label, args in specs.items():
        cmd = [sys.executable, *args] + ([] if full else ["--quick"])
        COMMANDS.append("python3 " + " ".join(args + ([] if full else ["--quick"])))
        res = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
        (OUT / f"phase_mmm_{label}_audit_stdout_tail.txt").write_text("\n".join((res.stdout or "").splitlines()[-80:]) + "\n")
        (OUT / f"phase_mmm_{label}_audit_stderr_tail.txt").write_text("\n".join((res.stderr or "").splitlines()[-80:]) + "\n")
        out[label] = "PASS" if res.returncode == 0 else f"FAIL rc={res.returncode}"
    return out


def md_table(df: pd.DataFrame, cols: list[str] | None = None, max_rows: int = 12) -> str:
    small = df[cols].head(max_rows).copy() if cols else df.head(max_rows).copy()
    for c in small.select_dtypes(include=[np.number]).columns:
        small[c] = small[c].map(lambda x: "" if pd.isna(x) else f"{x:.6f}")
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

## Section 79 — Phase MMM Composite Selective Signals Rebuild

Date: 2026-04-27. Phase MMM tested three GGG1-based Layer 2A rebuilds of only
`composite_selective_signals` in recovery_confirmed. GGG1's offense component
logic, production pin, and official shadow pin were unchanged.

**Best candidate.** `{best}` with decision `{decision}`.

**Next action.** `{rec['recommendation']}`.
Reason: {rec['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 79 — Phase MMM Composite Selective Signals Rebuild"
    if marker in text:
        text = re.sub(r"\n## Section 79 — Phase MMM Composite Selective Signals Rebuild[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    css_diag, css_contrib, css_corr, css_use = css_diagnostics(GGG1)
    write("phase_mmm_css_diagnostics", css_diag)
    write("phase_mmm_css_etf_contribution_by_state", css_contrib)
    write("phase_mmm_css_correlation_summary", css_corr)
    write("phase_mmm_css_state_usefulness", css_use)

    run_build()
    missing = [v for v in CANDIDATES for kind in ["returns", "weights", "sleeve_weights"] if not (L3 / f"portfolio_version_{kind}_{v}.csv").exists()]
    if missing:
        raise FileNotFoundError(f"missing candidate artifacts: {missing[:4]}")

    metrics_df = pd.DataFrame([metrics(v) for v in COMPARE])
    prod_turn = float(metrics_df.loc[metrics_df["name"].eq(PRODUCTION), "avg_turnover"].iloc[0])
    metrics_df["turnover_ratio_vs_production"] = metrics_df["avg_turnover"] / prod_turn
    write("phase_mmm_candidate_metrics_full", metrics_df)
    states = pd.concat([state_summary(v) for v in CANDIDATES + [GGG1, PRODUCTION]], ignore_index=True)
    write("phase_mmm_state_summary", states)
    before_after = pd.concat([css_diagnostics(v)[0] for v in [GGG1, FILTER_VERSION]], ignore_index=True)
    write("phase_mmm_css_before_after", before_after)
    candidate_diag = pd.DataFrame([cost_delay(v) for v in CANDIDATES])
    write("phase_mmm_candidate_diagnostics", candidate_diag)

    ggg = metrics_df[metrics_df["name"].eq(GGG1)].iloc[0]
    state_piv = states[states["candidate"].isin(CANDIDATES + [GGG1])].pivot(index="state", columns="candidate", values="ann_return")
    selection_rows = []
    for v in CANDIDATES:
        m = metrics_df[metrics_df["name"].eq(v)].iloc[0]
        guard = {st: float(state_piv.loc[st, v] - state_piv.loc[st, GGG1]) for st in ["recovery_confirmed", "recovery_fragile", "stressed_panic"] if st in state_piv.index}
        conditions = {
            "sharpe_not_materially_worse": bool(m["sharpe"] >= ggg["sharpe"] - 0.005),
            "ann_return_not_materially_worse": bool(m["ann_return"] >= ggg["ann_return"] - 0.001),
            "drawdown_not_materially_worse": bool(m["max_drawdown"] >= ggg["max_drawdown"] - 0.0025),
            "cvar_not_materially_worse": bool(m["cvar_5"] >= ggg["cvar_5"] - 0.0005),
            "turnover_under_cap": bool(m["turnover_ratio_vs_production"] <= 1.10),
            "stressed_panic_preserved": bool(guard.get("stressed_panic", 0.0) >= -0.003),
            "recovery_confirmed_not_worse": bool(guard.get("recovery_confirmed", 0.0) >= -0.003),
            "recovery_fragile_not_worse": bool(guard.get("recovery_fragile", 0.0) >= -0.003),
            "recovery_confirmed_improved": bool(guard.get("recovery_confirmed", 0.0) > 0.0005),
            "hidden_beta_not_higher": bool(m["avg_SPY"] <= ggg["avg_SPY"] + 0.0025),
        }
        clearly = all(conditions.values()) and m["sharpe"] > ggg["sharpe"] + 0.002 and m["ann_return"] >= ggg["ann_return"]
        if clearly:
            decision = "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        elif all(conditions.values()):
            decision = "KEEP_AS_SHADOW"
        else:
            decision = "REJECT"
        selection_rows.append({"candidate": v, **conditions, "guard_state_ann_return_deltas": ";".join(f"{k}:{val:.4%}" for k, val in guard.items()), "delta_sharpe_vs_ggg1": float(m["sharpe"] - ggg["sharpe"]), "delta_ann_return_vs_ggg1": float(m["ann_return"] - ggg["ann_return"]), "decision": decision})
    selection = pd.DataFrame(selection_rows)
    write("phase_mmm_selection_table", selection)

    qualified = selection[selection["decision"].isin(["KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"])]
    best_row = (qualified if not qualified.empty else selection).sort_values(["delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1"], ascending=[False, False]).iloc[0]
    best, best_decision = str(best_row["candidate"]), str(best_row["decision"])
    audits = run_audits(best, full=(best_decision == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW")) if best_decision in {"KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"} else {"research_committee": "skipped: no candidate qualified", "realism": "skipped", "allocator": "skipped"}

    if best_decision == "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW":
        recommendation, reason = "PROMOTE_MMM_OVER_GGG1", "A CSS rebuild clearly dominated GGG1."
    elif best_decision == "KEEP_AS_SHADOW":
        recommendation, reason = "KEEP_MMM_AS_SHADOW", "A CSS rebuild improved recovery_confirmed while preserving GGG1 gates."
    else:
        recommendation, reason = "KEEP_GGG1_AS_PRODUCTION_CANDIDATE", "CSS rebuild candidates failed or only marginally helped; keep GGG1."
    rec = pd.DataFrame([{"recommendation": recommendation, "best_candidate": best, "best_decision": best_decision, "reason": reason, "css_rebuild_should_continue": best_decision in {"KEEP_AS_SHADOW", "PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"}, "next_phase_prompt": "Keep GGG1 as production candidate and move to packaging/human review; do not force more Layer 2A rebuilds unless a new diagnostic identifies a larger issue."}])
    write("phase_mmm_next_action_recommendation", rec)
    protocol = {"phase": "MMM", "base": GGG1, "candidates": CANDIDATES, "production_pipeline_build": True, "best_candidate": best, "best_decision": best_decision, "audits": audits}
    (OUT / "phase_mmm_protocol.json").write_text(json.dumps(protocol, indent=2) + "\n")

    lines = [
        "# Phase MMM — Composite Selective Signals Rebuild", "", "Date: 2026-04-27", "",
        "## Commands executed", "```", *COMMANDS, "```", "",
        "## Files created / modified", "- `scripts/build_improvement_artifacts.py`", "- `scripts/phase_mmm_composite_selective_signals_rebuild.py`", "- `data/research/phase_mmm_composite_selective_signals_rebuild/*`", "- `data/05_layer3_portfolio_construction/portfolio_version_*_improved_phasemmm_*.csv`", "- `docs/research/2026-04-27_phase_mmm_composite_selective_signals_rebuild_report.md`", "- `docs/research/project_journey.md`", "",
        "## CSS diagnosis", md_table(css_diag, ["candidate", "state", "ann_return", "sharpe", "avg_BIL", "avg_SPY", "avg_DBA", "avg_TLT"], 8), "",
        "## Internal ETF findings", md_table(css_contrib.sort_values(["state", "ann_contribution_proxy"]), ["state", "ETF", "avg_weight", "ann_contribution_proxy"], 18), "",
        "## Candidate metrics", md_table(metrics_df, ["name", "ann_return", "sharpe", "max_drawdown", "cvar_5", "turnover_ratio_vs_production", "avg_BIL", "avg_SPY"], 8), "",
        "## CSS before / after", md_table(before_after[before_after["state"].isin(["recovery_confirmed", "recovery_fragile", "stressed_panic"])], ["candidate", "state", "ann_return", "sharpe", "avg_DBA", "avg_TLT"], 8), "",
        "## Selection table", md_table(selection, ["candidate", "decision", "delta_sharpe_vs_ggg1", "delta_ann_return_vs_ggg1", "turnover_under_cap", "recovery_confirmed_improved", "recovery_fragile_not_worse", "stressed_panic_preserved", "hidden_beta_not_higher"], 6), "",
        "## Candidate diagnostics", md_table(candidate_diag, ["candidate", "doubled_cost_sharpe", "one_week_delay_sharpe"], 6), "",
        "## Audit results", *[f"- {k}: {v}" for k, v in audits.items()], "",
        "## Final decision", f"**{recommendation}**", "", f"Best candidate: `{best}` (`{best_decision}`).", "", f"Reason: {reason}", "", f"CSS rebuild should continue: **{bool(rec.iloc[0]['css_rebuild_should_continue'])}**.", "",
        "## Exact prompt outline for the next phase", str(rec.iloc[0]["next_phase_prompt"]),
    ]
    DOC.write_text("\n".join(lines) + "\n")
    update_journey(rec.iloc[0], best, best_decision)
    print(f"best_candidate: {best}")
    print(f"best_decision: {best_decision}")
    print(f"recommendation: {recommendation}")


if __name__ == "__main__":
    main()
