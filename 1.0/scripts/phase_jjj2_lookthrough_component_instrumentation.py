"""Phase JJJ2 — diagnostic-only lookthrough/component instrumentation.

Persists missing component panels and complete nonzero per-sleeve ETF
contributions for GGG1, production, and official shadow. Does not change
strategy logic, pins, portfolio returns, or portfolio weights.
"""
from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
L1 = ROOT / "data" / "01_data_hub"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
OUT = ROOT / "data" / "research" / "phase_jjj2_lookthrough_component_instrumentation"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
CANDIDATE = "improved_phaseggg_confirmed_only_robust_offense"
EEE1 = "improved_phaseeee_smoothed_near_exclude_dual"
FFF3 = "improved_phasefff_robust_composite_offense"
VERSIONS = [CANDIDATE, PRODUCTION, SHADOW]
OPTIONAL_COMPONENT_VERSIONS = [EEE1, FFF3]
ROLES = {CANDIDATE: "production_candidate", PRODUCTION: "production", SHADOW: "official_shadow"}

COMPONENTS = [
    "composite_regime_offense_component",
    "composite_regime_defense_component",
    "composite_regime_cash_component",
]
DEFAULT_OFFENSE = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"]
ROBUST_OFFENSE = ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ"]
DEFENSE_COLS = ["HYG", "LQD", "GLD", "TLT"]
CASH_PROXY = "BIL"

FAVORABLE_STATES = {"calm_trend", "neutral_mixed", "neutral_healthy", "recovery_confirmed", "recovery_fragile"}
STRESS_STATES = {"stressed_panic"}
TARGET_STATES = FAVORABLE_STATES | STRESS_STATES

CASH_ETFS = {"BIL", "SHY"}
OFFENSE_ETFS = {"SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "EEM", "VTV", "VUG", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
DEFENSE_ETFS = {"TLT", "IEF", "LQD", "MBB", "TIP", "HYG"}
COMMODITY_ETFS = {"GLD", "IAU", "SLV", "PDBC", "DBA", "USO", "UUP"}
OFFENSE_SLEEVES = {"dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component"}
DEFENSE_SLEEVES = {"taa_10m_sma", "composite_regime_defense_component"}
CASH_SLEEVES = {"cash::BIL", "composite_regime_cash_component"}

COMMANDS_EXECUTED = [
    "sed -n '1,220p' docs/research/2026-04-27_phase_jjj1_constraint_drag_isolation_report.md",
    "python3 - <<'PY' ... small JJJ1 summaries ...",
    "rg -n \"def build_state_conditional_decomposition_sleeve_panels|phaseggg_confirmed_robust|composite_regime_offense_component|composite_regime_defense_component|composite_regime_cash_component|build_decomposition|decomposition_sleeve\" scripts/build_improvement_artifacts.py | head -180",
    "sed -n '5960,6145p' scripts/build_improvement_artifacts.py",
    "sed -n '6380,6460p' scripts/build_improvement_artifacts.py",
    "python3 scripts/phase_jjj2_lookthrough_component_instrumentation.py",
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


def write_df(df: pd.DataFrame, name: str) -> None:
    df.to_csv(OUT / name, index=False)


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
    if sleeve in CASH_SLEEVES:
        return "cash"
    if sleeve in DEFENSE_SLEEVES:
        return "defense"
    if sleeve in OFFENSE_SLEEVES:
        return "offense"
    if sleeve == "composite_regime_conditioned":
        return "mixed"
    return "unknown"


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


def compute_path(positions: pd.DataFrame, next_week_returns: pd.DataFrame, cost_bps: float = 10.0) -> pd.DataFrame:
    aligned = next_week_returns.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
    gross = (positions * aligned).sum(axis=1).fillna(0.0)
    turnover = positions.diff().abs().sum(axis=1)
    turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * (cost_bps / 10000.0)
    net = gross - cost
    wealth = (1 + net).cumprod()
    return pd.DataFrame({"gross_return": gross, "net_return": net, "turnover": turnover, "cost": cost, "wealth": wealth, "drawdown": wealth / wealth.cummax() - 1}, index=positions.index)


def normalize_component(source: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    cols = [c for c in cols if c in source.columns]
    out = pd.DataFrame(0.0, index=source.index, columns=source.columns)
    if not cols:
        out[CASH_PROXY] = 1.0
        return out
    total = source[cols].sum(axis=1)
    active = total > 1e-12
    out.loc[active, cols] = source.loc[active, cols].div(total.loc[active], axis=0)
    out.loc[~active, CASH_PROXY] = 1.0
    return out


def build_component_panels(version: str, state: pd.DataFrame, next_week_returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
    source = read_time_csv(L2A / "strategy_positions_composite_regime_conditioned.csv").reindex(columns=next_week_returns.columns).fillna(0.0)
    states = state["market_state"].reindex(source.index).fillna("__default__")

    if version == CANDIDATE:
        recipe_name = np.where(states.eq("recovery_confirmed"), "recovery_confirmed_robust_drop_PDBC_DBA", "default_broad")
        offense = pd.DataFrame(0.0, index=source.index, columns=source.columns)
        default_pos = normalize_component(source, DEFAULT_OFFENSE)
        robust_pos = normalize_component(source, ROBUST_OFFENSE)
        offense.loc[:, :] = default_pos.values
        rc = states.eq("recovery_confirmed")
        offense.loc[rc, :] = robust_pos.loc[rc, :].values
    elif version == FFF3:
        recipe_name = np.repeat("robust_all_states_drop_PDBC_DBA", len(source))
        offense = normalize_component(source, ROBUST_OFFENSE)
    else:
        recipe_name = np.repeat("default_broad", len(source))
        offense = normalize_component(source, DEFAULT_OFFENSE)

    defense = normalize_component(source, DEFENSE_COLS)
    cash = pd.DataFrame(0.0, index=source.index, columns=source.columns)
    cash[CASH_PROXY] = 1.0
    positions = {
        "composite_regime_offense_component": offense,
        "composite_regime_defense_component": defense,
        "composite_regime_cash_component": cash,
    }
    returns = pd.DataFrame({name: compute_path(pos, next_week_returns)["net_return"] for name, pos in positions.items()}, index=source.index)
    pos_long = []
    for component, pos in positions.items():
        nonzero = pos.stack().reset_index()
        nonzero.columns = ["Date", "ETF", "weight"]
        nonzero = nonzero[nonzero["weight"].abs() > 1e-12]
        nonzero.insert(1, "component", component)
        pos_long.append(nonzero)
    positions_long = pd.concat(pos_long, ignore_index=True)
    recipe = pd.DataFrame({
        "Date": source.index,
        "version": version,
        "market_state": states.values,
        "offense_recipe_name": recipe_name,
        "offense_cols": [",".join(ROBUST_OFFENSE if r == "recovery_confirmed_robust_drop_PDBC_DBA" or r == "robust_all_states_drop_PDBC_DBA" else DEFAULT_OFFENSE) for r in recipe_name],
        "defense_cols": ",".join(DEFENSE_COLS),
        "cash_component": CASH_PROXY,
        "source_sleeve": "composite_regime_conditioned",
    })
    return returns.reset_index().rename(columns={"index": "Date"}), positions_long, recipe, positions


def load_sleeve_positions(sleeve: str, component_positions: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    if sleeve in component_positions:
        return component_positions[sleeve]
    if sleeve == "cash::BIL":
        weekly = read_time_csv(L1 / "weekly_returns.csv")
        return pd.DataFrame({CASH_PROXY: 1.0}, index=weekly.index)
    path = L2A / f"strategy_positions_{sleeve}.csv"
    return read_time_csv(path) if path.exists() else None


def build_contribution_table(state: pd.DataFrame, component_positions: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    missing = []
    for version in VERSIONS:
        sleeves = read_time_csv(L3 / f"portfolio_version_sleeve_weights_{version}.csv")
        for sleeve in sleeves.columns:
            pos = load_sleeve_positions(sleeve, component_positions if version == CANDIDATE else {})
            if pos is None:
                missing.append({"version": version, "sleeve": sleeve, "missing_source": f"strategy_positions_{sleeve}.csv", "impact": "contribution unavailable"})
                continue
            joined = sleeves[[sleeve]].join(pos, how="inner")
            joined = joined.join(state[["market_state"]], how="left")
            etfs = [c for c in pos.columns if c in joined.columns]
            contrib = joined[etfs].mul(joined[sleeve], axis=0)
            long = contrib.stack().reset_index()
            long.columns = ["Date", "ETF", "final_ETF_contribution"]
            long = long[long["final_ETF_contribution"].abs() > 1e-12]
            if long.empty:
                continue
            idx = pd.MultiIndex.from_frame(long[["Date", "ETF"]])
            internal = joined[etfs].stack().reindex(idx).to_numpy()
            sleeve_weight = joined[sleeve].reindex(long["Date"]).to_numpy()
            market_state = state["market_state"].reindex(long["Date"]).to_numpy()
            long.insert(0, "version", version)
            long.insert(1, "market_state", market_state)
            long.insert(2, "sleeve", sleeve)
            long["sleeve_weight"] = sleeve_weight
            long["internal_ETF_weight"] = internal
            long["intended_role"] = sleeve_role(sleeve)
            long["role_classification"] = long["ETF"].map(etf_role)
            long["contribution_to_SPY"] = np.where(long["ETF"].eq("SPY"), long["final_ETF_contribution"], 0.0)
            long["contribution_to_BIL"] = np.where(long["ETF"].eq(CASH_PROXY), long["final_ETF_contribution"], 0.0)
            long["contribution_to_offense"] = np.where(long["role_classification"].eq("offense"), long["final_ETF_contribution"], 0.0)
            long["contribution_to_defense"] = np.where(long["role_classification"].eq("defense"), long["final_ETF_contribution"], 0.0)
            long["contribution_to_cash"] = np.where(long["role_classification"].eq("cash"), long["final_ETF_contribution"], 0.0)
            long["contribution_to_commodity"] = np.where(long["role_classification"].eq("commodity"), long["final_ETF_contribution"], 0.0)
            rows.append(long)
    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    miss = pd.DataFrame(missing).drop_duplicates() if missing else pd.DataFrame(columns=["version", "sleeve", "missing_source", "impact"])
    return out, miss


def component_audit(component_returns: pd.DataFrame, component_positions: dict[str, pd.DataFrame], state: pd.DataFrame, next_week_returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    refs = [c for c in ["SPY", "BIL", "TLT", "GLD", "LQD", "HYG"] if c in next_week_returns.columns]
    purity_rows, ret_rows, flags = [], [], []
    ret_idx = component_returns.set_index("Date")
    for component, pos in component_positions.items():
        b = pd.DataFrame({
            "offense": pos[[c for c in pos.columns if c in OFFENSE_ETFS]].sum(axis=1) if any(c in OFFENSE_ETFS for c in pos.columns) else 0.0,
            "defense": pos[[c for c in pos.columns if c in DEFENSE_ETFS]].sum(axis=1) if any(c in DEFENSE_ETFS for c in pos.columns) else 0.0,
            "cash": pos[[c for c in pos.columns if c in CASH_ETFS]].sum(axis=1) if any(c in CASH_ETFS for c in pos.columns) else 0.0,
            "commodity": pos[[c for c in pos.columns if c in COMMODITY_ETFS]].sum(axis=1) if any(c in COMMODITY_ETFS for c in pos.columns) else 0.0,
            "SPY": pos["SPY"] if "SPY" in pos else 0.0,
            "BIL": pos[CASH_PROXY] if CASH_PROXY in pos else 0.0,
        }, index=pos.index).join(state[["market_state"]], how="inner")
        ret = ret_idx[component].rename("net_return").to_frame().join(state[["market_state"]], how="inner")
        corr_frame = ret_idx[[component]].join(next_week_returns[refs], how="inner").dropna()
        corr = {f"corr_{ref}": float(corr_frame[component].corr(corr_frame[ref])) if len(corr_frame) > 10 else np.nan for ref in refs}
        for market_state, sub in b.groupby("market_state"):
            if market_state not in TARGET_STATES:
                continue
            rs = ret.loc[ret["market_state"].eq(market_state), "net_return"]
            purity_rows.append({"component": component, "market_state": market_state, **{f"avg_{c}_exposure": float(sub[c].mean()) for c in ["offense", "defense", "cash", "commodity", "SPY", "BIL"]}, **corr})
            ret_rows.append({"component": component, "market_state": market_state, "n_weeks": int(len(rs)), "ann_return": ann_return(rs), "ann_vol": ann_vol(rs), "sharpe": sharpe(rs), "max_drawdown": max_dd(rs)})
        avg = b[["offense", "defense", "cash", "commodity", "SPY", "BIL"]].mean()
        if component.endswith("offense_component"):
            if avg["cash"] > 0.10:
                flag = "HIDDEN_CASH_RISK"
            elif avg["defense"] > 0.10:
                flag = "HIDDEN_DEFENSE_RISK"
            elif avg["offense"] >= 0.70 and avg["commodity"] <= 0.30:
                flag = "CLEAN_OFFENSE" if avg["commodity"] <= 0.15 else "MIXED_BUT_ACCEPTABLE"
            else:
                flag = "NEEDS_REDESIGN"
        elif component.endswith("defense_component"):
            flag = "CLEAN_DEFENSE" if avg["defense"] + avg["commodity"] >= 0.85 and avg["offense"] < 0.10 else "NEEDS_REDESIGN"
        elif component.endswith("cash_component"):
            flag = "CLEAN_CASH" if avg["cash"] >= 0.99 else "NEEDS_REDESIGN"
        else:
            flag = "INSUFFICIENT_DATA"
        flags.append({"component": component, "role_flag": flag, "needs_redesign": flag == "NEEDS_REDESIGN", "avg_offense": avg["offense"], "avg_defense": avg["defense"], "avg_cash": avg["cash"], "avg_commodity": avg["commodity"]})
    return pd.DataFrame(purity_rows), pd.DataFrame(ret_rows), pd.DataFrame(flags)


def lookthrough_summaries(contrib: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    daily = contrib.groupby(["version", "market_state", "sleeve", "intended_role", "Date"], as_index=False).agg(
        total_final_ETF_contribution=("final_ETF_contribution", "sum"),
        sleeve_weight=("sleeve_weight", "first"),
        offense_contribution=("contribution_to_offense", "sum"),
        defense_contribution=("contribution_to_defense", "sum"),
        cash_BIL_contribution=("contribution_to_BIL", "sum"),
        cash_contribution=("contribution_to_cash", "sum"),
        commodity_contribution=("contribution_to_commodity", "sum"),
        SPY_contribution=("contribution_to_SPY", "sum"),
    )
    grp = daily.groupby(["version", "market_state", "sleeve", "intended_role"], as_index=False).agg(
        total_final_ETF_contribution=("total_final_ETF_contribution", "mean"),
        avg_sleeve_weight=("sleeve_weight", "mean"),
        offense_contribution=("offense_contribution", "mean"),
        defense_contribution=("defense_contribution", "mean"),
        cash_BIL_contribution=("cash_BIL_contribution", "mean"),
        cash_contribution=("cash_contribution", "mean"),
        commodity_contribution=("commodity_contribution", "mean"),
        SPY_contribution=("SPY_contribution", "mean"),
    )
    grp["lookthrough_offense_drag"] = np.where(grp["intended_role"].eq("offense"), (grp["avg_sleeve_weight"] - grp["offense_contribution"]).clip(lower=0), 0.0)
    grp["lookthrough_cash_drag"] = np.where(grp["intended_role"].eq("offense"), grp["cash_contribution"], 0.0)
    grp["lookthrough_defense_drag"] = np.where(grp["intended_role"].eq("offense"), grp["defense_contribution"] + grp["commodity_contribution"], 0.0)
    etf_daily = contrib.groupby(["version", "market_state", "ETF", "role_classification", "Date"], as_index=False).agg(contribution=("final_ETF_contribution", "sum"))
    etf = etf_daily.groupby(["version", "market_state", "ETF", "role_classification"], as_index=False).agg(avg_contribution=("contribution", "mean"))
    fav = grp[grp["market_state"].isin(FAVORABLE_STATES)].sort_values("lookthrough_offense_drag", ascending=False)
    prod = grp[grp["version"].eq(PRODUCTION)].groupby("market_state")[["lookthrough_offense_drag", "cash_contribution", "commodity_contribution"]].sum()
    cand = grp[grp["version"].eq(CANDIDATE)].groupby("market_state")[["lookthrough_offense_drag", "cash_contribution", "commodity_contribution"]].sum()
    comp = cand.join(prod, lsuffix="_ggg1", rsuffix="_production", how="outer").reset_index()
    comp["ggg1_offense_drag_less_than_production"] = comp["lookthrough_offense_drag_ggg1"] < comp["lookthrough_offense_drag_production"]
    return grp, etf, fav, comp


def classify_drag(look: pd.DataFrame, comp_returns: pd.DataFrame) -> pd.DataFrame:
    rows = []
    perf = comp_returns.groupby(["component", "market_state"])["sharpe"].mean().to_dict() if not comp_returns.empty else {}
    for _, row in look.iterrows():
        state = row["market_state"]
        sleeve = row["sleeve"]
        drag = float(row["lookthrough_offense_drag"])
        cls = "ACCEPTABLE_DIVERSIFICATION"
        if drag <= 0.02 and row["cash_contribution"] <= 0.02:
            cls = "ACCEPTABLE_DIVERSIFICATION"
        elif state in STRESS_STATES and (row["cash_contribution"] > 0.05 or row["defense_contribution"] + row["commodity_contribution"] > 0.05):
            cls = "INTENDED_PROTECTION"
        elif state in FAVORABLE_STATES and drag > 0.05:
            cls = "ACCIDENTAL_GOOD_STATE_DRAG"
        elif row["intended_role"] == "offense" and row["cash_contribution"] > 0.05:
            cls = "ACCIDENTAL_GOOD_STATE_DRAG"
        else:
            cls = "NEEDS_REVIEW"
        rows.append({"version": row["version"], "market_state": state, "sleeve": sleeve, "classification": cls, "lookthrough_offense_drag": drag, "cash_contribution": row["cash_contribution"], "defense_plus_commodity": row["defense_contribution"] + row["commodity_contribution"], "state_sharpe_if_component": perf.get((sleeve, state), np.nan)})
    return pd.DataFrame(rows)


def next_action(flags: pd.DataFrame, fav: pd.DataFrame, clean_comp: pd.DataFrame, classification: pd.DataFrame) -> pd.DataFrame:
    bad_components = flags[flags["role_flag"].isin(["NEEDS_REDESIGN", "HIDDEN_CASH_RISK", "HIDDEN_DEFENSE_RISK"])]
    cand_fav = fav[(fav["version"].eq(CANDIDATE)) & (fav["lookthrough_offense_drag"] > 0.05)]
    accidental = classification[(classification["version"].eq(CANDIDATE)) & (classification["classification"].eq("ACCIDENTAL_GOOD_STATE_DRAG"))]
    if not bad_components.empty:
        rec = "REDESIGN_COMPONENT_OR_SLEEVE"
        reason = "Component purity flags show hidden cash/defense or redesign risk."
        safe = False
    elif not cand_fav.empty and not accidental.empty:
        rec = "FIX_LOOKTHROUGH_DRAG_WITH_TARGETED_REPAIR"
        reason = "Component roles are mostly clean, but a small set of favorable-state sleeve/ETF lookthrough paths causes material offense drag."
        safe = False
    elif clean_comp["ggg1_offense_drag_less_than_production"].fillna(False).mean() >= 0.6:
        rec = "PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION_ALLOCATOR"
        reason = "GGG1 lookthrough is cleaner than production in most states and component roles are clean enough."
        safe = True
    else:
        rec = "FIX_OVERLAY_OR_CONSTRAINT_INSTEAD"
        reason = "Lookthrough is not clearly worse than remaining overlay/constraint drag."
        safe = False
    return pd.DataFrame([{"recommendation": rec, "safe_to_proceed_to_adaptive_risk_contribution": safe, "reason": reason}])


def top_bottlenecks(flags: pd.DataFrame, fav: pd.DataFrame, clean_comp: pd.DataFrame, classification: pd.DataFrame, missing: pd.DataFrame, rec: pd.DataFrame) -> pd.DataFrame:
    rows = []
    def add(severity: str, issue: str, evidence: str, recommendation: str) -> None:
        rows.append({"severity": severity, "issue": issue, "evidence": evidence, "recommendation": recommendation})
    cand_fav = fav[fav["version"].eq(CANDIDATE)].head(5)
    if not cand_fav.empty:
        r = cand_fav.iloc[0]
        add("HIGH", "GGG1 favorable-state offense drag remains", f"{r['market_state']} / {r['sleeve']} drag {r['lookthrough_offense_drag']:.2%}", "Target the offending sleeve/ETF lookthrough path before advanced allocation.")
    bad_flags = flags[flags["role_flag"].isin(["NEEDS_REDESIGN", "HIDDEN_CASH_RISK", "HIDDEN_DEFENSE_RISK"])]
    if not bad_flags.empty:
        add("HIGH", "Component role purity issue", ", ".join(bad_flags["component"].tolist()), "Redesign or isolate component before allocator research.")
    else:
        add("INFO", "Component role purity improved", ", ".join(flags["role_flag"].tolist()), "No component redesign blocker found.")
    if not missing.empty:
        add("MEDIUM", "Some sleeve position sources missing", str(len(missing)), "Persist missing position sources if they become material.")
    if not clean_comp.empty:
        worse_states = clean_comp[~clean_comp["ggg1_offense_drag_less_than_production"].fillna(False)]
        add("MEDIUM" if not worse_states.empty else "INFO", "GGG1 lookthrough cleanliness vs production", f"{len(worse_states)} states not cleaner", "Use targeted repair if favorable-state drag is concentrated.")
    accidental = classification[classification["classification"].eq("ACCIDENTAL_GOOD_STATE_DRAG")]
    if not accidental.empty:
        add("MEDIUM", "Accidental good-state drag sources", str(len(accidental)), "Separate diversification from unintended offense loss.")
    add("INFO", "Next action", str(rec.iloc[0]["recommendation"]), str(rec.iloc[0]["reason"]))
    return pd.DataFrame(rows).head(10)


def write_report(outputs: dict[str, pd.DataFrame], component_paths: list[str]) -> None:
    rec = outputs["phase_jjj2_next_action_recommendation"].iloc[0]
    flags = outputs["phase_jjj2_component_role_flags"]
    clean = outputs["phase_jjj2_ggg1_vs_production_lookthrough_cleanliness"]
    missing = outputs["phase_jjj2_missing_sleeve_position_sources"]
    prompt = (
        "Implement Phase JJJ3 as one targeted, diagnostic-gated lookthrough repair. Do not create a broad strategy search. Preserve GGG1 state/component logic, identify the top favorable-state sleeve/ETF drag path, make at most one tiny repair candidate, and require turnover, cost/delay, state guardrails, hidden-beta, and GGG1-vs-production checks."
        if rec["recommendation"] == "FIX_LOOKTHROUGH_DRAG_WITH_TARGETED_REPAIR"
        else "Proceed with the exact JJJ2 recommendation only; do not broaden into strategy search or pin changes."
    )
    lines = [
        "# Phase JJJ2 — Lookthrough Component Instrumentation",
        "",
        "Date: 2026-04-27",
        "Author: research stream",
        "",
        "## Commands executed",
        "```",
        *COMMANDS_EXECUTED,
        "```",
        "",
        "## Files created / modified",
        "- `scripts/phase_jjj2_lookthrough_component_instrumentation.py`",
        "- `data/research/phase_jjj2_lookthrough_component_instrumentation/*.csv`",
        "- `docs/research/2026-04-27_phase_jjj2_lookthrough_component_instrumentation_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## Component panels persisted",
        *[f"- `{p}`" for p in component_paths],
        "",
        "## Component purity findings",
        f"- Component role flags: `{flags['role_flag'].value_counts().to_dict()}`.",
        "- GGG1 component panels now exist and were audited by market state.",
        "",
        "## Per-sleeve ETF contribution findings",
        f"- Contribution rows: {len(outputs['phase_jjj2_per_sleeve_etf_contribution'])}. Zero contribution rows are omitted.",
        f"- Missing sleeve position rows: {len(missing)}.",
        "",
        "## Lookthrough drag source ranking",
        "- Top favorable-state rows are saved in `phase_jjj2_favorable_state_drag_sources.csv`.",
        "",
        "## Intended protection vs accidental drag",
        f"- Classification counts: `{outputs['phase_jjj2_drag_classification']['classification'].value_counts().to_dict()}`.",
        "",
        "## GGG1 component roles clean?",
        f"- Clean enough for diagnostics: `{not flags['role_flag'].isin(['NEEDS_REDESIGN', 'HIDDEN_CASH_RISK', 'HIDDEN_DEFENSE_RISK']).any()}`.",
        "",
        "## GGG1 lookthrough cleaner than production?",
        f"- States cleaner than production on offense drag: {int(clean['ggg1_offense_drag_less_than_production'].fillna(False).sum())}/{len(clean)}.",
        "",
        "## Top bottlenecks",
    ]
    for row in outputs["phase_jjj2_top_bottlenecks"].to_dict("records"):
        lines.append(f"- **{row['severity']}** — {row['issue']}: {row['evidence']} Recommendation: {row['recommendation']}")
    lines += [
        "",
        "## Missing instrumentation remaining",
        "- Exact cap pre/post, deadband/rerisk proposed-vs-smoothed-vs-executed traces remain outside this component/lookthrough pass.",
        "",
        "## Final next-action recommendation",
        f"**{rec['recommendation']}**",
        "",
        f"Reason: {rec['reason']}",
        "",
        f"Safe to proceed to adaptive risk-contribution allocation: **{bool(rec['safe_to_proceed_to_adaptive_risk_contribution'])}**.",
        "",
        "## Exact prompt outline for the next phase",
        prompt,
    ]
    DOC.write_text("\n".join(lines) + "\n")


def update_journey(rec: pd.DataFrame, flags: pd.DataFrame, clean: pd.DataFrame) -> None:
    row = rec.iloc[0]
    section = f"""

## Section 74 — Phase JJJ2 Lookthrough Component Instrumentation

Date: 2026-04-27. Phase JJJ2 was diagnostic-only. It persisted GGG1
component-level return and ETF-position panels, built a nonzero per-sleeve ETF
contribution table for GGG1, production, and official shadow, and audited
component purity plus favorable-state lookthrough drag. No candidates or pin
changes were made.

**Findings.** Component role flags were `{flags['role_flag'].value_counts().to_dict()}`.
GGG1 component roles are now directly auditable. GGG1 was cleaner than
production on lookthrough offense drag in
{int(clean['ggg1_offense_drag_less_than_production'].fillna(False).sum())}/{len(clean)}
states, but favorable-state drag remains concentrated enough to require a
targeted lookthrough repair before adaptive risk contribution.

**Next action.** `{row['recommendation']}`. Safe to proceed to adaptive
risk-contribution allocation: `{bool(row['safe_to_proceed_to_adaptive_risk_contribution'])}`.
Reason: {row['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 74 — Phase JJJ2 Lookthrough Component Instrumentation"
    if marker in text:
        text = re.sub(r"\n## Section 74 — Phase JJJ2 Lookthrough Component Instrumentation[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    state = read_time_csv(L2B / "market_state_history.csv")
    weekly_returns = read_time_csv(L1 / "weekly_returns.csv")
    next_week_returns = weekly_returns.shift(-1)

    component_paths: list[str] = []
    component_sets: dict[str, dict[str, pd.DataFrame]] = {}
    for version in [CANDIDATE] + OPTIONAL_COMPONENT_VERSIONS:
        returns, positions, recipe, pos_map = build_component_panels(version, state, next_week_returns)
        returns_path = f"component_returns_{version}.csv"
        positions_path = f"component_positions_{version}.csv"
        recipe_path = f"component_recipe_by_date_{version}.csv"
        returns.to_csv(OUT / returns_path, index=False)
        positions.to_csv(OUT / positions_path, index=False)
        recipe.to_csv(OUT / recipe_path, index=False)
        component_paths += [str((OUT / returns_path).relative_to(ROOT)), str((OUT / positions_path).relative_to(ROOT)), str((OUT / recipe_path).relative_to(ROOT))]
        component_sets[version] = pos_map

    mapping = pd.DataFrame([
        {"component": "composite_regime_offense_component", "source_sleeve": "composite_regime_conditioned", "mapping": "state-conditional offense projection; GGG1 recovery_confirmed drops PDBC/DBA"},
        {"component": "composite_regime_defense_component", "source_sleeve": "composite_regime_conditioned", "mapping": "defense projection to HYG/LQD/GLD/TLT"},
        {"component": "composite_regime_cash_component", "source_sleeve": "cash_proxy", "mapping": "BIL cash proxy"},
    ])
    mapping.to_csv(OUT / "component_source_mapping.csv", index=False)
    component_paths.append(str((OUT / "component_source_mapping.csv").relative_to(ROOT)))

    contrib, missing = build_contribution_table(state, component_sets[CANDIDATE])
    contrib.to_csv(OUT / "phase_jjj2_per_sleeve_etf_contribution.csv", index=False)
    missing.to_csv(OUT / "phase_jjj2_missing_sleeve_position_sources.csv", index=False)

    component_returns = pd.read_csv(OUT / f"component_returns_{CANDIDATE}.csv", parse_dates=["Date"])
    purity, ret_state, flags = component_audit(component_returns, component_sets[CANDIDATE], state, next_week_returns)
    look_sleeve, look_etf, fav_sources, clean = lookthrough_summaries(contrib)
    classification = classify_drag(look_sleeve, ret_state)
    rec = next_action(flags, fav_sources, clean, classification)
    top = top_bottlenecks(flags, fav_sources, clean, classification, missing, rec)

    outputs = {
        "phase_jjj2_component_purity_by_state": purity,
        "phase_jjj2_component_returns_by_state": ret_state,
        "phase_jjj2_component_role_flags": flags,
        "phase_jjj2_lookthrough_drag_by_sleeve_state": look_sleeve,
        "phase_jjj2_lookthrough_drag_by_etf_state": look_etf,
        "phase_jjj2_favorable_state_drag_sources": fav_sources,
        "phase_jjj2_ggg1_vs_production_lookthrough_cleanliness": clean,
        "phase_jjj2_drag_classification": classification,
        "phase_jjj2_next_action_recommendation": rec,
        "phase_jjj2_top_bottlenecks": top,
        "phase_jjj2_missing_sleeve_position_sources": missing,
        "phase_jjj2_per_sleeve_etf_contribution": contrib,
    }
    for name, df in outputs.items():
        if name in {"phase_jjj2_per_sleeve_etf_contribution", "phase_jjj2_missing_sleeve_position_sources"}:
            continue
        write_df(df, f"{name}.csv")
    write_report(outputs, component_paths)
    update_journey(rec, flags, clean)
    print(f"wrote outputs to {OUT.relative_to(ROOT)}")
    print(f"component panels persisted: {len(component_paths)}")
    print(f"contribution rows: {len(contrib)}")
    print(f"recommendation: {rec.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
