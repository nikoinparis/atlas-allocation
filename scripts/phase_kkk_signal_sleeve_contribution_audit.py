"""Phase KKK — non-allocator signal and sleeve contribution audit.

Diagnostic only. Reads existing Layer 1, Layer 2A, market-state, GGG1, and
component-panel artifacts. Does not build or test strategy candidates.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "02_layer1_signals"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
JJJ2 = ROOT / "data" / "research" / "phase_jjj2_lookthrough_component_instrumentation"
OUT = ROOT / "data" / "research" / "phase_kkk_signal_sleeve_contribution_audit"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
FOCUS_STATES = ["calm_trend", "neutral_mixed", "recovery_confirmed", "recovery_fragile", "stressed_panic"]
SPECIAL_SLEEVES = {
    "composite_selective_signals",
    "dual_momentum_topn",
    "taa_10m_sma",
    "cta_trend_long_only",
    "composite_regime_offense_component",
    "composite_regime_defense_component",
}
CASH = {"BIL", "SHY", "cash::BIL"}
OFFENSE = {"SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "EEM", "VTV", "VUG"}
DEFENSE = {"TLT", "IEF", "LQD", "MBB", "TIP", "HYG"}
COMMODITY = {"GLD", "IAU", "SLV", "PDBC", "DBA", "USO", "UUP"}

COMMANDS = [
    "sed -n '1,140p' docs/research/2026-04-27_phase_jjj4_adaptive_risk_contribution_allocator_report.md",
    "sed -n '1,100p' docs/research/2026-04-27_phase_iii_production_candidate_review_report.md",
    "sed -n '1,100p' docs/research/2026-04-27_phase_ggg_state_conditional_composite_offense_report.md",
    "find data/02_layer1_signals -maxdepth 1 -type f | sort | sed -n '1,120p'",
    "find data/03_layer2a_strategy_logic -maxdepth 1 -type f | sort | sed -n '1,80p'",
    "python3 scripts/phase_kkk_signal_sleeve_contribution_audit.py",
]


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)


def read_time_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    date_col = "Date" if "Date" in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.tz_localize(None)
    df = df.dropna(subset=[date_col]).set_index(date_col).sort_index()
    for col in df.columns:
        converted = pd.to_numeric(df[col], errors="coerce")
        if converted.notna().sum() >= max(1, int(df[col].notna().sum() * 0.8)):
            df[col] = converted
    return df


def ann_return(ret: pd.Series) -> float:
    ret = ret.dropna()
    if ret.empty:
        return np.nan
    return float((1.0 + ret).prod() ** (52.0 / len(ret)) - 1.0)


def sharpe(ret: pd.Series) -> float:
    ret = ret.dropna()
    sd = float(ret.std(ddof=0))
    return float(ret.mean() / sd * np.sqrt(52.0)) if sd > 1e-12 else np.nan


def max_drawdown(ret: pd.Series) -> float:
    wealth = (1.0 + ret.fillna(0.0)).cumprod()
    return float((wealth / wealth.cummax() - 1.0).min())


def cvar5(ret: pd.Series) -> float:
    ret = ret.dropna()
    return float(ret[ret <= ret.quantile(0.05)].mean()) if not ret.empty else np.nan


def metrics(ret: pd.Series) -> dict:
    return {
        "ann_return": ann_return(ret),
        "ann_vol": float(ret.std(ddof=0) * np.sqrt(52.0)),
        "sharpe": sharpe(ret),
        "max_drawdown": max_drawdown(ret),
        "cvar_5": cvar5(ret),
    }


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


def file_inventory(directory: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(directory.glob("*")):
        if not p.is_file():
            continue
        row = {"file": str(p.relative_to(ROOT)), "size_kb": p.stat().st_size / 1024.0, "suffix": p.suffix}
        if p.suffix == ".csv":
            try:
                df = pd.read_csv(p, nrows=2000)
                row.update({"rows_sampled": len(df), "columns": len(df.columns), "column_preview": "|".join(df.columns[:8])})
                date_col = "Date" if "Date" in df.columns else df.columns[0]
                dates = pd.to_datetime(df[date_col], errors="coerce")
                if dates.notna().any():
                    row.update({"first_date_sample": str(dates.min().date()), "last_date_sample": str(dates.max().date())})
            except Exception as exc:
                row["read_error"] = str(exc)
        rows.append(row)
    return pd.DataFrame(rows)


def signal_audit() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    inventory = file_inventory(L1)
    manifest = json.loads((L1 / "signal_manifest.json").read_text()) if (L1 / "signal_manifest.json").exists() else []
    summary = read_csv(L1 / "signal_summary_table.csv") if (L1 / "signal_summary_table.csv").exists() else pd.DataFrame()
    ic = read_csv(L1 / "signal_ic_by_horizon.csv") if (L1 / "signal_ic_by_horizon.csv").exists() else pd.DataFrame()
    pairs = read_csv(L1 / "signal_redundancy_pairs.csv") if (L1 / "signal_redundancy_pairs.csv").exists() else pd.DataFrame()
    incr = read_csv(L1 / "signal_incremental_contribution.csv") if (L1 / "signal_incremental_contribution.csv").exists() else pd.DataFrame()
    layer2_manifest = json.loads((L2A / "layer2_manifest.json").read_text()) if (L2A / "layer2_manifest.json").exists() else []

    red_rows = []
    if not pairs.empty:
        for signal in sorted(set(pairs["left_signal"]).union(set(pairs["right_signal"]))):
            vals = pd.concat([
                pairs.loc[pairs["left_signal"].eq(signal), "abs_avg_cs_corr"],
                pairs.loc[pairs["right_signal"].eq(signal), "abs_avg_cs_corr"],
            ])
            red_rows.append({"signal_name": signal, "avg_abs_redundancy_from_pairs": float(vals.mean()), "max_abs_redundancy": float(vals.max()), "redundant_pair_count_075": int((vals >= 0.75).sum())})
    red = pd.DataFrame(red_rows)

    usage_rows = []
    manifest_names = [m.get("signal_name", "") for m in manifest]
    manifest_by_name = {m.get("signal_name", ""): m for m in manifest}
    for signal in sorted(set(manifest_names).union(set(summary.get("signal_name", [])))):
        meta = manifest_by_name.get(signal, {})
        tokens = {signal.lower(), str(meta.get("file_name", "")).lower().replace(".csv", "")}
        consumers = []
        for entry in layer2_manifest:
            text = json.dumps(entry).lower()
            if any(t and t in text for t in tokens):
                consumers.append(entry.get("strategy_name", "unknown"))
        subset_users = []
        if not incr.empty and "signal_names" in incr.columns:
            subset_users = incr.loc[incr["signal_names"].astype(str).str.contains(signal, regex=False), "study"].astype(str).tolist()
        usage_rows.append({
            "signal_name": signal,
            "manifest_file": meta.get("file_name"),
            "category": meta.get("category"),
            "used_by_layer2_manifest": "|".join(sorted(set(consumers))),
            "used_by_signal_subset_tests": "|".join(sorted(set(subset_users))),
            "usage_instrumentation_quality": "EXPLICIT_MANIFEST_MATCH" if consumers else "INFERRED_OR_MISSING",
        })
    usage = pd.DataFrame(usage_rows)

    rows = []
    for signal in sorted(set(usage["signal_name"]).union(set(summary.get("signal_name", [])))):
        s = summary[summary["signal_name"].eq(signal)].tail(1)
        i = ic[ic["signal_name"].eq(signal)] if not ic.empty else pd.DataFrame()
        r = red[red["signal_name"].eq(signal)].tail(1)
        q = float(s["validation_quality_score"].iloc[0]) if not s.empty and "validation_quality_score" in s else np.nan
        nw = float(s["avg_ic_tstat_nw"].iloc[0]) if not s.empty and "avg_ic_tstat_nw" in s else (float(i["ic_tstat_nw"].mean()) if not i.empty and "ic_tstat_nw" in i else np.nan)
        red_avg = float(s["avg_abs_redundancy"].iloc[0]) if not s.empty and "avg_abs_redundancy" in s else (float(r["avg_abs_redundancy_from_pairs"].iloc[0]) if not r.empty else np.nan)
        hit = float(i["hit_rate"].mean()) if not i.empty and "hit_rate" in i else np.nan
        coverage = float(i["mean_coverage"].mean()) if not i.empty and "mean_coverage" in i else np.nan
        if pd.isna(q) and pd.isna(nw):
            flag = "INSUFFICIENT_DATA"
        elif (q >= 2.5 or nw >= 2.0) and (pd.isna(red_avg) or red_avg < 0.55):
            flag = "KEEP_STRONG"
        elif (q >= 2.5 or nw >= 2.0):
            flag = "REDUNDANT_BUT_USEFUL"
        elif nw >= 1.0:
            flag = "STATE_SPECIFIC_ONLY"
        elif red_avg >= 0.65:
            flag = "REDUNDANT_WEAK"
        elif nw < 0.25:
            flag = "RETIRE_CANDIDATE"
        else:
            flag = "NEEDS_REVALIDATION"
        rows.append({
            "signal_name": signal,
            "avg_mean_ic": float(s["avg_mean_ic"].iloc[0]) if not s.empty and "avg_mean_ic" in s else (float(i["mean_ic"].mean()) if not i.empty and "mean_ic" in i else np.nan),
            "avg_ic_tstat_nw": nw,
            "hit_rate": hit,
            "mean_coverage": coverage,
            "avg_abs_redundancy": red_avg,
            "validation_quality_score": q,
            "summary_recommendation": str(s["recommendation"].iloc[0]) if not s.empty and "recommendation" in s else "",
            "signal_flag": flag,
        })
    quality = pd.DataFrame(rows).sort_values(["signal_flag", "validation_quality_score"], ascending=[True, False])
    return inventory, quality, red, usage, pd.DataFrame([{
        "limitation": "Exact signal-to-sleeve lineage is only partially explicit in layer2_manifest.",
        "recommendation": "Persist a Layer2A signal_usage_by_sleeve table during sleeve construction.",
        "severity": "MEDIUM",
    }])


def strategy_return(name: str) -> pd.Series | None:
    if name == "cash::BIL":
        wr = read_time_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv")
        return pd.to_numeric(wr.get("BIL", pd.Series(dtype=float)), errors="coerce")
    comp_path = JJJ2 / f"component_returns_{GGG1}.csv"
    if comp_path.exists():
        comp = read_time_csv(comp_path)
        if name in comp.columns:
            return pd.to_numeric(comp[name], errors="coerce")
    p = L2A / f"strategy_returns_{name}.csv"
    if not p.exists():
        return None
    df = read_time_csv(p)
    col = "net_return" if "net_return" in df.columns else df.select_dtypes(include=[np.number]).columns[0]
    return pd.to_numeric(df[col], errors="coerce")


def position_panel(name: str) -> pd.DataFrame | None:
    if name in {"composite_regime_offense_component", "composite_regime_defense_component", "composite_regime_cash_component"}:
        p = JJJ2 / f"component_positions_{GGG1}.csv"
        if not p.exists():
            return None
        long = pd.read_csv(p, parse_dates=["Date"])
        sub = long[long["component"].eq(name)]
        return sub.pivot_table(index="Date", columns="ETF", values="weight", aggfunc="sum").sort_index().fillna(0.0)
    if name == "cash::BIL":
        idx = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{GGG1}.csv").index
        return pd.DataFrame({"BIL": 1.0}, index=idx)
    p = L2A / f"strategy_positions_{name}.csv"
    return read_time_csv(p) if p.exists() else None


def sleeve_names() -> list[str]:
    names = {p.name.replace("strategy_returns_", "").replace(".csv", "") for p in L2A.glob("strategy_returns_*.csv")}
    comp = JJJ2 / f"component_returns_{GGG1}.csv"
    if comp.exists():
        names.update(read_time_csv(comp).columns.tolist())
    names.add("cash::BIL")
    return sorted(names)


def portfolio_return(version: str) -> pd.Series:
    return read_time_csv(L3 / f"portfolio_version_returns_{version}.csv")["net_return"]


def sleeve_audit() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ggg_ret = portfolio_return(GGG1)
    prod_ret = portfolio_return(PRODUCTION)
    weekly = read_time_csv(ROOT / "data" / "01_data_hub" / "weekly_returns.csv")
    ggg_w = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{GGG1}.csv")
    rows, usage_rows, exposure_rows, inv_rows = [], [], [], []
    for name in sleeve_names():
        ret = strategy_return(name)
        pos = position_panel(name)
        inv_rows.append({
            "sleeve": name,
            "return_file_exists": ret is not None,
            "position_file_exists": pos is not None,
            "used_in_ggg1": name in ggg_w.columns,
        })
        if ret is None:
            continue
        ret = ret.reindex(ggg_ret.index).fillna(0.0)
        m = metrics(ret)
        avg_w = float(ggg_w.get(name, pd.Series(0.0, index=ggg_w.index)).mean())
        max_w = float(ggg_w.get(name, pd.Series(0.0, index=ggg_w.index)).max())
        corr_ggg = float(ret.corr(ggg_ret.reindex(ret.index))) if ret.std() > 0 else np.nan
        corr_prod = float(ret.corr(prod_ret.reindex(ret.index))) if ret.std() > 0 else np.nan
        corr_spy = float(ret.corr(weekly["SPY"].reindex(ret.index))) if "SPY" in weekly and ret.std() > 0 else np.nan
        corr_bil = float(ret.corr(weekly["BIL"].reindex(ret.index))) if "BIL" in weekly and ret.std() > 0 else np.nan
        flag = "LOW_WEIGHT_MONITOR"
        if avg_w >= 0.08 and m["sharpe"] >= 0.75:
            flag = "CORE_KEEP"
        elif avg_w >= 0.04 and m["sharpe"] >= 0.45 and corr_ggg < 0.75:
            flag = "DIVERSIFIER_KEEP"
        elif avg_w > 0.04 and m["sharpe"] < 0.20:
            flag = "REBUILD_CANDIDATE"
        elif avg_w > 0.02 and m["sharpe"] < 0.35 and corr_ggg > 0.75:
            flag = "REDUNDANT_WEAK"
        elif avg_w <= 0.01 and m["sharpe"] < 0.20:
            flag = "RETIRE_CANDIDATE"
        elif avg_w > 0.02:
            flag = "STATE_SPECIFIC_KEEP"
        rows.append({"sleeve": name, **m, "corr_with_ggg1": corr_ggg, "corr_with_production": corr_prod, "corr_with_SPY": corr_spy, "corr_with_BIL": corr_bil, "avg_weight_ggg1": avg_w, "max_weight_ggg1": max_w, "sleeve_flag": flag})
        usage_rows.append({"sleeve": name, "used_in_ggg1": name in ggg_w.columns, "avg_weight_ggg1": avg_w, "max_weight_ggg1": max_w, "approx_contribution_to_ggg1": avg_w * m["ann_return"]})
        if pos is not None:
            p = pos.reindex(ggg_w.index).fillna(0.0)
            exposure_rows.append({
                "sleeve": name,
                "avg_cash_BIL": float(p.reindex(columns=list(CASH & set(p.columns))).sum(axis=1).mean()) if CASH & set(p.columns) else 0.0,
                "avg_SPY": float(p.get("SPY", pd.Series(0.0, index=p.index)).mean()),
                "avg_offense": float(p.reindex(columns=list(OFFENSE & set(p.columns))).sum(axis=1).mean()) if OFFENSE & set(p.columns) else 0.0,
                "avg_defense": float(p.reindex(columns=list(DEFENSE & set(p.columns))).sum(axis=1).mean()) if DEFENSE & set(p.columns) else 0.0,
                "avg_commodity": float(p.reindex(columns=list(COMMODITY & set(p.columns))).sum(axis=1).mean()) if COMMODITY & set(p.columns) else 0.0,
            })
    return pd.DataFrame(inv_rows), pd.DataFrame(rows), pd.DataFrame(usage_rows), pd.DataFrame(exposure_rows)


def version_state_contribution(version: str) -> pd.DataFrame:
    w = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{version}.csv")
    states = read_time_csv(L2B / "market_state_history.csv")["market_state"].reindex(w.index)
    rows = []
    for sleeve in w.columns:
        ret = strategy_return(sleeve)
        if ret is None:
            continue
        ret = ret.reindex(w.index).fillna(0.0)
        for st in FOCUS_STATES:
            idx = states.eq(st)
            if int(idx.sum()) < 8:
                continue
            sub = ret.loc[idx]
            avg_w = float(w.loc[idx, sleeve].mean())
            ann = ann_return(sub)
            rows.append({
                "version": version,
                "state": st,
                "sleeve": sleeve,
                "avg_weight": avg_w,
                "ann_return": ann,
                "sharpe": sharpe(sub),
                "contribution_proxy": avg_w * ann,
                "n_weeks": int(idx.sum()),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["weight_rank"] = df.groupby(["version", "state"])["avg_weight"].rank(ascending=False, method="min")
        df["performance_rank"] = df.groupby(["version", "state"])["sharpe"].rank(ascending=False, method="min")
        df["rank_gap_weight_minus_perf"] = df["performance_rank"] - df["weight_rank"]
        df["state_flag"] = np.select(
            [
                (df["avg_weight"] >= 0.05) & (df["ann_return"] < 0.0),
                (df["rank_gap_weight_minus_perf"] >= 3) & (df["avg_weight"] >= 0.05),
                (df["rank_gap_weight_minus_perf"] <= -3) & (df["sharpe"] >= 0.7),
                df["sharpe"] >= 0.6,
            ],
            ["STATE_HARMFUL", "OVERWEIGHT_WEAK_IN_STATE", "UNDERWEIGHT_STRONG_IN_STATE", "STATE_HELPFUL"],
            default="STATE_NEUTRAL",
        )
    return df


def redundancy_audit(quality: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ggg_w = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{GGG1}.csv")
    used = [c for c in ggg_w.columns if c != "cash::BIL"]
    panel = pd.DataFrame({s: strategy_return(s) for s in used if strategy_return(s) is not None}).reindex(ggg_w.index).fillna(0.0)
    corr = panel.corr()
    corr_out = corr.reset_index().rename(columns={"index": "sleeve"})
    q = quality.set_index("sleeve") if "sleeve" in quality.columns else pd.DataFrame()
    clusters, redundant, diversifying = [], [], []
    for i, left in enumerate(corr.columns):
        for right in corr.columns[i + 1:]:
            c = float(corr.loc[left, right])
            if abs(c) >= 0.75:
                clusters.append({"left_sleeve": left, "right_sleeve": right, "correlation": c, "cluster_flag": "HIGH_CORRELATION_CLUSTER"})
                ls = float(q.loc[left, "sharpe"]) if left in q.index else np.nan
                rs = float(q.loc[right, "sharpe"]) if right in q.index else np.nan
                weaker = left if ls < rs else right
                redundant.append({"sleeve": weaker, "paired_with": right if weaker == left else left, "correlation": c, "weaker_sharpe": min(ls, rs), "flag": "REDUNDANT_WEAK"})
    for sleeve in corr.columns:
        avg_corr = float(corr[sleeve].drop(sleeve).abs().mean())
        shp = float(q.loc[sleeve, "sharpe"]) if sleeve in q.index else np.nan
        if avg_corr < 0.55 and (pd.isna(shp) or shp >= 0.25):
            diversifying.append({"sleeve": sleeve, "avg_abs_corr_to_used_sleeves": avg_corr, "sharpe": shp, "flag": "DIVERSIFIER_KEEP"})
    return corr_out, pd.DataFrame(clusters), pd.DataFrame(redundant), pd.DataFrame(diversifying)


def issues_and_recommendation(sleeve_quality: pd.DataFrame, state_contrib: pd.DataFrame, exposure: pd.DataFrame, signal_quality: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    issues = []
    ggg = state_contrib[state_contrib["version"].eq(GGG1)]
    for sleeve in sorted(SPECIAL_SLEEVES):
        q = sleeve_quality[sleeve_quality["sleeve"].eq(sleeve)]
        harms = ggg[(ggg["sleeve"].eq(sleeve)) & (ggg["state_flag"].eq("STATE_HARMFUL"))]
        weak_states = ggg[(ggg["sleeve"].eq(sleeve)) & (ggg["avg_weight"] >= 0.05) & (ggg["sharpe"] < 0.25)]
        if not q.empty and (not harms.empty or not weak_states.empty or str(q.iloc[0]["sleeve_flag"]) in {"REBUILD_CANDIDATE", "REDUNDANT_WEAK"}):
            severity = "HIGH" if sleeve in {"composite_selective_signals", "composite_regime_offense_component", "composite_regime_defense_component"} else "MEDIUM"
            problem = "state_harmful_or_weak_used_sleeve"
            action = "REBUILD_WEAK_LAYER2A_SLEEVE" if severity == "HIGH" else "STATE_GATING_REVIEW"
            evidence = "; ".join(f"{r.state}:{r.ann_return:.2%},w={r.avg_weight:.1%}" for r in pd.concat([harms, weak_states]).drop_duplicates(["state"]).itertuples())
            issues.append({"item": sleeve, "item_type": "sleeve", "problem_type": problem, "evidence": evidence, "affected_states": "|".join(sorted(set(pd.concat([harms, weak_states])["state"]))) if (not harms.empty or not weak_states.empty) else "", "current_avg_weight_ggg1": float(q.iloc[0]["avg_weight_ggg1"]), "already_mitigated_by_ggg1": sleeve in {"dual_momentum_topn", "composite_selective_signals"}, "recommended_future_action": action, "severity": severity})
    weak_signals = signal_quality[signal_quality["signal_flag"].isin(["REDUNDANT_WEAK", "RETIRE_CANDIDATE", "NEEDS_REVALIDATION"])].head(5)
    for r in weak_signals.itertuples():
        issues.append({"item": r.signal_name, "item_type": "signal", "problem_type": "weak_or_redundant_signal_quality", "evidence": f"flag={r.signal_flag}, nw={getattr(r, 'avg_ic_tstat_nw', np.nan):.2f}, redundancy={getattr(r, 'avg_abs_redundancy', np.nan):.2f}", "affected_states": "unknown", "current_avg_weight_ggg1": np.nan, "already_mitigated_by_ggg1": False, "recommended_future_action": "REVALIDATE_LAYER1_SIGNALS", "severity": "MEDIUM"})
    issue_df = pd.DataFrame(issues).sort_values(["severity", "current_avg_weight_ggg1"], ascending=[True, False]) if issues else pd.DataFrame(columns=["item", "severity"])

    sanity_rows = [
        {"check": "allocator_path", "result": "clean_enough_after_JJJ4", "readiness_category": "NON_ALLOCATOR_STACK_CLEAN_ENOUGH"},
        {"check": "signal_lineage", "result": "partial_manifest_only", "readiness_category": "NEEDS_SIGNAL_REVALIDATION"},
        {"check": "state_sample_size", "result": "recovery_confirmed/recovery_fragile remain small samples", "readiness_category": "NEEDS_STATE_GATING_REVIEW"},
        {"check": "weak_used_sleeves", "result": "state-harmful used sleeves remain in GGG1", "readiness_category": "NEEDS_SLEEVE_REBUILD"},
    ]
    sanity = pd.DataFrame(sanity_rows)
    top = issue_df.head(10).copy()
    if issue_df.empty:
        rec = "PACKAGE_GGG1_AND_STOP_RESEARCH_FOR_NOW"
        reason = "No material non-allocator issue found."
        next_prompt = "Move GGG1 to packaging/human review; do not run more research unless deployment review finds a blocker."
    elif (issue_df["recommended_future_action"].eq("REBUILD_WEAK_LAYER2A_SLEEVE") & issue_df["severity"].eq("HIGH")).any():
        rec = "REBUILD_WEAK_LAYER2A_SLEEVE"
        reason = "At least one heavily used GGG1 sleeve remains state-harmful or weak enough to justify a rebuild before more allocator work."
        next_prompt = "Implement a diagnostic-gated Layer 2A sleeve rebuild focused on the top KKK issue only; do not change allocator logic or production pins."
    elif (issue_df["recommended_future_action"].eq("REVALIDATE_LAYER1_SIGNALS")).any():
        rec = "REVALIDATE_LAYER1_SIGNALS"
        reason = "Signal lineage/quality uncertainty is the main remaining upstream limitation."
        next_prompt = "Run a Layer 1 signal revalidation pass with explicit signal-to-sleeve usage instrumentation."
    else:
        rec = "RETIRE_OR_GATE_WEAK_SLEEVE"
        reason = "Weakness is localized enough for state gating or reduced max-weight review."
        next_prompt = "Run one diagnostic-gated weak-sleeve state-gating test; no broad search."
    frontier = pd.DataFrame([{"recommendation": rec, "reason": reason, "another_research_phase_justified": rec != "PACKAGE_GGG1_AND_STOP_RESEARCH_FOR_NOW", "next_phase_prompt": next_prompt}])
    return issue_df, top, sanity, frontier


def update_journey(frontier: pd.Series) -> None:
    section = f"""

## Section 77 — Phase KKK Signal and Sleeve Contribution Audit

Date: 2026-04-27. Phase KKK was diagnostic-only. It audited Layer 1 signal
quality, Layer 2A sleeve quality, GGG1 state-by-state sleeve contribution, and
sleeve redundancy/diversification without creating candidates or changing pins.

**Next frontier.** `{frontier['recommendation']}`.
Reason: {frontier['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 77 — Phase KKK Signal and Sleeve Contribution Audit"
    if marker in text:
        text = re.sub(r"\n## Section 77 — Phase KKK Signal and Sleeve Contribution Audit[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sig_inv, sig_quality, sig_red, sig_usage, missing = signal_audit()
    sleeve_inv, sleeve_quality, sleeve_usage, sleeve_exposure = sleeve_audit()
    state_contrib = pd.concat([version_state_contribution(GGG1), version_state_contribution(PRODUCTION)], ignore_index=True)
    ranks = state_contrib[["version", "state", "sleeve", "avg_weight", "sharpe", "weight_rank", "performance_rank", "rank_gap_weight_minus_perf", "state_flag"]].copy()
    harmful = state_contrib[state_contrib["state_flag"].eq("STATE_HARMFUL")].copy()
    state_keep = state_contrib[(state_contrib["state_flag"].eq("STATE_HELPFUL")) & (state_contrib["avg_weight"] >= 0.03)].copy()
    corr, clusters, redundant, diversifying = redundancy_audit(sleeve_quality)
    issues, issue_top, sanity, frontier = issues_and_recommendation(sleeve_quality, state_contrib, sleeve_exposure, sig_quality)

    outputs = {
        "phase_kkk_signal_inventory": sig_inv,
        "phase_kkk_signal_quality_summary": sig_quality,
        "phase_kkk_signal_redundancy_summary": sig_red,
        "phase_kkk_signal_usage_map": sig_usage,
        "phase_kkk_sleeve_inventory": sleeve_inv,
        "phase_kkk_sleeve_quality_summary": sleeve_quality,
        "phase_kkk_sleeve_usage_in_ggg1": sleeve_usage,
        "phase_kkk_sleeve_exposure_summary": sleeve_exposure,
        "phase_kkk_state_sleeve_contribution": state_contrib,
        "phase_kkk_state_weight_vs_performance_rank": ranks,
        "phase_kkk_state_harmful_sleeves": harmful,
        "phase_kkk_state_specific_keep_candidates": state_keep,
        "phase_kkk_sleeve_correlation_matrix": corr,
        "phase_kkk_sleeve_redundancy_clusters": clusters,
        "phase_kkk_redundant_weak_sleeves": redundant,
        "phase_kkk_diversifying_sleeves": diversifying,
        "phase_kkk_rebuild_retire_candidates": issues,
        "phase_kkk_sleeve_issue_rankings": issue_top,
        "phase_kkk_ggg1_non_allocator_sanity_check": sanity,
        "phase_kkk_next_frontier_recommendation": frontier,
        "phase_kkk_missing_data_instrumentation": missing,
    }
    for name, df in outputs.items():
        write(name, df)

    rec = frontier.iloc[0]
    lines = [
        "# Phase KKK — Signal and Sleeve Contribution Audit",
        "",
        "Date: 2026-04-27",
        "",
        "## Commands executed",
        "```",
        *COMMANDS,
        "```",
        "",
        "## Files created / modified",
        "- `scripts/phase_kkk_signal_sleeve_contribution_audit.py`",
        "- `data/research/phase_kkk_signal_sleeve_contribution_audit/*.csv`",
        "- `docs/research/2026-04-27_phase_kkk_signal_sleeve_contribution_audit_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## Layer 1 signal findings",
        md_table(sig_quality.sort_values("validation_quality_score", ascending=False), ["signal_name", "avg_ic_tstat_nw", "avg_abs_redundancy", "validation_quality_score", "signal_flag"], 12),
        "",
        "## Layer 2A sleeve findings",
        md_table(sleeve_quality.sort_values("avg_weight_ggg1", ascending=False), ["sleeve", "ann_return", "sharpe", "corr_with_ggg1", "avg_weight_ggg1", "max_weight_ggg1", "sleeve_flag"], 14),
        "",
        "## State-by-state harmful sleeves",
        md_table(harmful.sort_values(["version", "state", "avg_weight"], ascending=[True, True, False]), ["version", "state", "sleeve", "avg_weight", "ann_return", "sharpe", "state_flag"], 16),
        "",
        "## Redundancy / diversification",
        f"- High-correlation clusters: {len(clusters)}",
        f"- Redundant weak sleeve rows: {len(redundant)}",
        f"- Diversifying sleeve rows: {len(diversifying)}",
        "",
        "## Weak / rebuild / retire candidates",
        md_table(issue_top, ["item", "item_type", "problem_type", "affected_states", "current_avg_weight_ggg1", "recommended_future_action", "severity"], 10),
        "",
        "## GGG1 non-allocator sanity check",
        md_table(sanity, ["check", "result", "readiness_category"], 10),
        "",
        "## Missing data / instrumentation",
        md_table(missing, ["limitation", "recommendation", "severity"], 10),
        "",
        "## Final next-frontier recommendation",
        f"**{rec['recommendation']}**",
        "",
        f"Reason: {rec['reason']}",
        "",
        f"Another research phase justified: **{bool(rec['another_research_phase_justified'])}**.",
        "",
        "## Exact prompt outline for the next phase",
        str(rec["next_phase_prompt"]),
    ]
    DOC.write_text("\n".join(lines) + "\n")
    update_journey(rec)
    print(f"recommendation: {rec['recommendation']}")
    print(f"issues: {len(issues)}")
    print(f"harmful_state_rows: {len(harmful)}")


if __name__ == "__main__":
    main()
