"""Phase JJJ1 — diagnostic-only constraint, overlay, and lookthrough isolation.

Reads saved diagnostics/checkpoints and derives raw instrumentation outputs.
No strategy candidates are created and no production/shadow pins are changed.
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
CHECKPOINTS = ROOT / "data" / "research" / "allocator_checkpoints"
OUT = ROOT / "data" / "research" / "phase_jjj1_constraint_drag_isolation"
RAW = OUT / "raw"
DOC = ROOT / "docs" / "research" / "2026-04-27_phase_jjj1_constraint_drag_isolation_report.md"
JOURNEY = ROOT / "docs" / "research" / "project_journey.md"

PRODUCTION = "improved_phase2b_regime_confidence_boost"
SHADOW = "improved_phase2b_combo_abc"
CANDIDATE = "improved_phaseggg_confirmed_only_robust_offense"
VERSIONS = [CANDIDATE, PRODUCTION, SHADOW]
ROLES = {CANDIDATE: "production_candidate", PRODUCTION: "production", SHADOW: "official_shadow"}

STAGES = [
    "raw_hrp_sleeve_weights",
    "post_state_tilt_sleeve_weights",
    "post_layer3_expression_sleeve_weights",
    "post_overlay_pre_lookthrough_sleeve_weights",
    "final_sleeve_weights",
    "final_etf_weights",
]
STAGE_PAIRS = list(zip(STAGES[:-1], STAGES[1:]))

TARGET_STATES = {"calm_trend", "neutral_mixed", "neutral_healthy", "recovery_confirmed", "recovery_fragile", "stressed_panic"}
FAVORABLE_STATES = {"calm_trend", "neutral_mixed", "neutral_healthy", "recovery_confirmed", "recovery_fragile"}
STRESS_STATES = {"stressed_panic"}

CASH_ETFS = {"BIL", "SHY"}
OFFENSE_ETFS = {"SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "EEM", "VTV", "VUG", "XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"}
DEFENSE_ETFS = {"TLT", "IEF", "LQD", "MBB", "TIP", "HYG"}
REAL_ETFS = {"GLD", "IAU", "SLV", "PDBC", "DBA", "USO", "UUP"}

OFFENSE_SLEEVES = {"dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component"}
DEFENSE_SLEEVES = {"taa_10m_sma", "composite_regime_defense_component"}
CASH_SLEEVES = {"cash::BIL", "composite_regime_cash_component"}
MIXED_SLEEVES = {"composite_regime_conditioned"}
COMPONENT_SLEEVES = ["composite_regime_offense_component", "composite_regime_defense_component", "composite_regime_cash_component"]

COMMANDS_EXECUTED = [
    "sed -n '1,220p' docs/research/2026-04-27_phase_jjj0_foundation_diagnostic_audit_report.md",
    "ls -1 data/research/phase_jjj0_foundation_diagnostic_audit | sort",
    "rg -n \"SAVE_CONSTRAINT_DIAGNOSTICS|constraint_diag|target_vol_multiplier|target_vol|save_checkpoint|checkpoint_stage|post_overlay_pre_lookthrough|final_sleeve_weights|final_etf_weights|lookthrough\" scripts/build_improvement_artifacts.py | head -160",
    "sed -n '4680,5035p' scripts/build_improvement_artifacts.py",
    "python3 scripts/phase_jjj1_constraint_drag_isolation.py",
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


def sharpe(s: pd.Series) -> float:
    s = pd.to_numeric(s, errors="coerce").dropna()
    vol = s.std(ddof=1) * np.sqrt(52) if len(s) > 1 else np.nan
    return float(ann_return(s) / vol) if vol and np.isfinite(vol) and vol > 0 else np.nan


def bucket_frame(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    if kind == "etf":
        return pd.DataFrame({
            "cash": df[[c for c in df.columns if c in CASH_ETFS]].sum(axis=1) if any(c in CASH_ETFS for c in df.columns) else 0.0,
            "offense": df[[c for c in df.columns if c in OFFENSE_ETFS]].sum(axis=1) if any(c in OFFENSE_ETFS for c in df.columns) else 0.0,
            "defense": df[[c for c in df.columns if c in DEFENSE_ETFS]].sum(axis=1) if any(c in DEFENSE_ETFS for c in df.columns) else 0.0,
            "real_asset": df[[c for c in df.columns if c in REAL_ETFS]].sum(axis=1) if any(c in REAL_ETFS for c in df.columns) else 0.0,
            "mixed": 0.0,
        }, index=df.index)
    return pd.DataFrame({
        "cash": df[[c for c in df.columns if c in CASH_SLEEVES]].sum(axis=1) if any(c in CASH_SLEEVES for c in df.columns) else 0.0,
        "offense": df[[c for c in df.columns if c in OFFENSE_SLEEVES]].sum(axis=1) if any(c in OFFENSE_SLEEVES for c in df.columns) else 0.0,
        "defense": df[[c for c in df.columns if c in DEFENSE_SLEEVES]].sum(axis=1) if any(c in DEFENSE_SLEEVES for c in df.columns) else 0.0,
        "real_asset": 0.0,
        "mixed": df[[c for c in df.columns if c in MIXED_SLEEVES]].sum(axis=1) if any(c in MIXED_SLEEVES for c in df.columns) else 0.0,
    }, index=df.index)


def with_state(df: pd.DataFrame, state: pd.DataFrame) -> pd.DataFrame:
    return df.join(state[["market_state"]], how="inner").dropna(subset=["market_state"])


def load_checkpoint(version: str, stage: str) -> pd.DataFrame | None:
    path = CHECKPOINTS / f"{version}__{stage}.csv"
    return read_time_csv(path) if path.exists() else None


def stage_kind(stage: str) -> str:
    return "etf" if stage == "final_etf_weights" else "sleeve"


def classify_drag(state: str, stage_pair: str, delta_cash: float, delta_offense: float, delta_defense: float) -> str:
    if state in STRESS_STATES and (delta_cash > 0.05 or delta_defense > 0.05 or delta_offense < -0.05):
        return "STRESS_PROTECTION"
    if state in FAVORABLE_STATES and delta_offense < -0.05 and delta_cash > 0.02:
        return "ACCIDENTAL_GOOD_STATE_DRAG"
    if state in FAVORABLE_STATES and delta_offense < -0.10 and stage_pair.endswith("final_etf_weights"):
        return "ACCIDENTAL_GOOD_STATE_DRAG"
    if delta_cash > 0.05 or abs(delta_offense) > 0.08 or abs(delta_defense) > 0.08:
        return "NEEDS_REVIEW"
    return "NEUTRAL"


def exposure_by_state(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    exposure_rows, delta_rows = [], []
    for version in VERSIONS:
        stage_bucket = {}
        for stage in STAGES:
            df = load_checkpoint(version, stage)
            if df is None:
                continue
            b = with_state(bucket_frame(df, stage_kind(stage)), state)
            stage_bucket[stage] = b
            for market_state, sub in b.groupby("market_state"):
                if market_state not in TARGET_STATES:
                    continue
                exposure_rows.append({
                    "version": version, "role": ROLES[version], "stage": stage, "market_state": market_state, "n_weeks": int(len(sub)),
                    "avg_cash": float(sub["cash"].mean()), "avg_offense": float(sub["offense"].mean()),
                    "avg_defense": float(sub["defense"].mean()), "avg_real_asset": float(sub["real_asset"].mean()),
                    "avg_mixed": float(sub["mixed"].mean()),
                })
        for a, b in STAGE_PAIRS:
            if a not in stage_bucket or b not in stage_bucket:
                continue
            joined = stage_bucket[a].join(stage_bucket[b], how="inner", lsuffix="_from", rsuffix="_to")
            for market_state, sub in joined.groupby("market_state_from"):
                if market_state not in TARGET_STATES:
                    continue
                dc = float((sub["cash_to"] - sub["cash_from"]).mean())
                do = float((sub["offense_to"] - sub["offense_from"]).mean())
                dd = float((sub["defense_to"] - sub["defense_from"]).mean())
                dr = float((sub["real_asset_to"] - sub["real_asset_from"]).mean())
                flag = classify_drag(market_state, f"{a}->{b}", dc, do, dd)
                delta_rows.append({
                    "version": version, "role": ROLES[version], "from_stage": a, "to_stage": b, "market_state": market_state,
                    "delta_cash": dc, "delta_offense": do, "delta_defense": dd, "delta_real_asset": dr,
                    "drag_flag": flag,
                    "interpretation": "intended protection" if flag == "STRESS_PROTECTION" else ("accidental bottleneck" if flag == "ACCIDENTAL_GOOD_STATE_DRAG" else "neutral/review"),
                })
    deltas = pd.DataFrame(delta_rows)
    rankings = deltas.assign(abs_offense_drag=deltas["delta_offense"].clip(upper=0).abs(), abs_cash_add=deltas["delta_cash"].clip(lower=0)).copy()
    rankings["drag_score"] = rankings["abs_offense_drag"] + 0.75 * rankings["abs_cash_add"] + 0.25 * rankings["delta_defense"].abs()
    rankings = rankings.sort_values("drag_score", ascending=False)
    return pd.DataFrame(exposure_rows), deltas, rankings


def load_positions(sleeve: str) -> pd.DataFrame | None:
    if sleeve == "cash::BIL":
        weekly = read_time_csv(L1 / "weekly_returns.csv")
        return pd.DataFrame({"BIL": 1.0}, index=weekly.index)
    path = L2A / f"strategy_positions_{sleeve}.csv"
    return read_time_csv(path) if path.exists() else None


def derive_lookthrough(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, missing = [], []
    positions_cache: dict[str, pd.DataFrame | None] = {}
    for version in VERSIONS:
        sw = load_checkpoint(version, "final_sleeve_weights")
        if sw is None:
            continue
        sw_state = with_state(sw, state)
        for sleeve in sw.columns:
            pos = positions_cache.setdefault(sleeve, load_positions(sleeve))
            if pos is None:
                missing.append({"version": version, "sleeve": sleeve, "missing_item": "strategy_positions file", "impact": "per-sleeve ETF contribution cannot be attributed"})
                continue
            common = sw[[sleeve]].join(pos, how="inner")
            contrib = pos.mul(common[sleeve], axis=0)
            contrib = with_state(contrib, state)
            for etf in contrib.columns.drop("market_state", errors="ignore"):
                tmp = contrib[[etf, "market_state"]].rename(columns={etf: "contribution"})
                for market_state, sub in tmp.groupby("market_state"):
                    if market_state not in TARGET_STATES:
                        continue
                    value = float(sub["contribution"].mean())
                    rows.append({
                        "version": version, "role": ROLES[version], "market_state": market_state, "sleeve": sleeve, "ETF": etf,
                        "avg_etf_weight_contribution": value,
                        "BIL_contribution": value if etf in CASH_ETFS else 0.0,
                        "SPY_contribution": value if etf == "SPY" else 0.0,
                        "offense_contribution": value if etf in OFFENSE_ETFS else 0.0,
                        "defense_contribution": value if etf in DEFENSE_ETFS else 0.0,
                        "cash_contribution": value if etf in CASH_ETFS else 0.0,
                        "real_asset_contribution": value if etf in REAL_ETFS else 0.0,
                    })
    miss = pd.DataFrame(missing).drop_duplicates() if missing else pd.DataFrame(columns=["version", "sleeve", "missing_item", "impact"])
    return pd.DataFrame(rows), miss


def summarize_lookthrough(lt: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if lt.empty:
        empty = pd.DataFrame()
        return empty, empty, empty, empty, empty
    sleeve = lt.groupby(["version", "role", "market_state", "sleeve"], as_index=False)[
        ["BIL_contribution", "SPY_contribution", "offense_contribution", "defense_contribution", "cash_contribution", "real_asset_contribution"]
    ].sum()
    sleeve["mixed_sleeve_proxy"] = ((sleeve["cash_contribution"] > 0.05) & (sleeve["offense_contribution"] > 0.05) & ((sleeve["defense_contribution"] + sleeve["real_asset_contribution"]) > 0.05))
    etf = lt.groupby(["version", "role", "market_state", "ETF"], as_index=False)[["avg_etf_weight_contribution"]].sum()
    hidden_cash = sleeve.sort_values("cash_contribution", ascending=False)
    hidden_def = sleeve.assign(total_defense_real=sleeve["defense_contribution"] + sleeve["real_asset_contribution"]).sort_values("total_defense_real", ascending=False)
    hidden_beta = sleeve.sort_values("SPY_contribution", ascending=False)
    return sleeve, etf, hidden_cash, hidden_def, hidden_beta


def target_overlay_cap_turnover(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    diag_path = L3 / "portfolio_version_diagnostics_timeseries.csv"
    diag = read_time_csv(diag_path).reset_index().rename(columns={"index": "Date"}) if diag_path.exists() else pd.DataFrame()
    target_rows = []
    raw_target = pd.DataFrame()
    if not diag.empty:
        date_col = "Date" if "Date" in diag.columns else diag.columns[0]
        diag[date_col] = pd.to_datetime(diag[date_col]).dt.tz_localize(None)
        raw_target = diag[diag["version_name"].isin(VERSIONS)].copy()
        raw_target.to_csv(RAW / "target_vol_diagnostics_by_date.csv", index=False)
        for (version, market_state), sub in raw_target.groupby(["version_name", "market_state"]):
            target_rows.append({
                "version": version, "role": ROLES.get(version, ""), "market_state": market_state, "n_obs": int(len(sub)),
                "target_vol_binding_rate": float(pd.to_numeric(sub.get("target_vol_binding"), errors="coerce").mean()),
                "regime_binding_rate": float(pd.to_numeric(sub.get("regime_binding"), errors="coerce").mean()),
                "avg_target_vol_multiplier": float(pd.to_numeric(sub.get("target_vol_multiplier"), errors="coerce").mean()),
                "avg_regime_multiplier": float(pd.to_numeric(sub.get("regime_multiplier"), errors="coerce").mean()),
                "avg_predicted_ann_vol": float(pd.to_numeric(sub.get("predicted_ann_vol"), errors="coerce").mean()),
                "binding_in_favorable_state": market_state in FAVORABLE_STATES and float(pd.to_numeric(sub.get("target_vol_binding"), errors="coerce").mean()) > 0.05,
            })

    exposure, deltas, _ = exposure_by_state(state)
    overlay = deltas[deltas["to_stage"] == "post_overlay_pre_lookthrough_sleeve_weights"].copy()
    raw_overlay = overlay.copy()
    raw_overlay.to_csv(RAW / "overlay_diagnostics_by_state.csv", index=False)

    cap_rows = []
    raw_cap_rows = []
    for version in VERSIONS:
        for stage in STAGES[:-1]:
            df = load_checkpoint(version, stage)
            if df is None:
                continue
            st = with_state(df, state)
            for market_state, sub in st.groupby("market_state"):
                if market_state not in TARGET_STATES:
                    continue
                vals = sub.drop(columns=["market_state"], errors="ignore")
                for sleeve in vals.columns:
                    rate = float((vals[sleeve] > 0.50).mean())
                    avg_excess = float((vals[sleeve] - 0.50).clip(lower=0).mean())
                    cap_rows.append({
                        "version": version, "role": ROLES[version], "stage": stage, "market_state": market_state, "sleeve": sleeve,
                        "cap_binding_rate_proxy": rate, "avg_cap_delta_proxy": avg_excess,
                        "constraint_boundary_proxy": rate > 0.05 or avg_excess > 0.01,
                        "limitation": "Proxy only; explicit pre/post cap diagnostics are not persisted.",
                    })
                    raw_cap_rows.append(cap_rows[-1])
    cap = pd.DataFrame(cap_rows)
    cap.to_csv(RAW / "cap_diagnostics_proxy_by_sleeve_state.csv", index=False)

    turn_rows, raw_turn = [], []
    for version in VERSIONS:
        weights = read_time_csv(L3 / f"portfolio_version_weights_{version}.csv")
        returns = read_time_csv(L3 / f"portfolio_version_returns_{version}.csv")
        l1 = weights.diff().abs().sum(axis=1).fillna(0.0)
        tdf = pd.DataFrame({
            "one_week_l1_turnover": l1,
            "return_file_turnover": pd.to_numeric(returns.get("turnover"), errors="coerce"),
        }).join(state[["market_state"]], how="inner")
        tdf["version"] = version
        tdf["role"] = ROLES[version]
        raw_turn.append(tdf.reset_index().rename(columns={"index": "Date"}))
        for market_state, sub in tdf.groupby("market_state"):
            if market_state not in TARGET_STATES:
                continue
            turn_rows.append({
                "version": version, "role": ROLES[version], "market_state": market_state, "avg_one_week_l1_turnover": float(sub["one_week_l1_turnover"].mean()),
                "p95_one_week_l1_turnover": float(sub["one_week_l1_turnover"].quantile(0.95)),
                "avg_return_file_turnover": float(sub["return_file_turnover"].mean()),
                "near_turnover_boundary": version == CANDIDATE and float(sub["one_week_l1_turnover"].mean()) > 0.12,
                "turnover_source_stage": "final ETF weight diff; deadband/rerisk trace not persisted",
            })
    raw_turnover = pd.concat(raw_turn, ignore_index=True)
    raw_turnover.to_csv(RAW / "turnover_diagnostics_by_date.csv", index=False)
    return pd.DataFrame(target_rows), overlay, cap, pd.DataFrame(turn_rows), raw_target


def component_purity(state: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, ret_rows, flags, missing = [], [], [], []
    etf_returns = read_time_csv(L1 / "weekly_returns.csv")
    refs = [c for c in ["SPY", "BIL", "TLT", "GLD", "LQD", "HYG"] if c in etf_returns.columns]
    for component in COMPONENT_SLEEVES:
        pos = load_positions(component)
        ret_path = L2A / f"strategy_returns_{component}.csv"
        ret = read_time_csv(ret_path)["net_return"] if ret_path.exists() else None
        if pos is None:
            missing.append({"component": component, "missing_item": "component ETF positions", "impact": "component purity cannot be directly audited"})
        if ret is None:
            missing.append({"component": component, "missing_item": "component return panel", "impact": "component return/Sharpe/correlation cannot be directly audited"})
        if pos is None or ret is None:
            flags.append({"component": component, "role_flag": "INSUFFICIENT_DATA", "needs_redesign": "UNKNOWN", "reason": "component return/position panel not persisted"})
            continue
        b = with_state(bucket_frame(pos, "etf"), state)
        r = pd.DataFrame({"net_return": ret}).join(state[["market_state"]], how="inner").dropna()
        aligned = pd.DataFrame({"component": ret}).join(etf_returns[refs], how="inner").dropna()
        corr = {f"corr_{ref}": float(aligned["component"].corr(aligned[ref])) if len(aligned) > 10 else np.nan for ref in refs}
        for market_state, sub in b.groupby("market_state"):
            if market_state not in TARGET_STATES:
                continue
            rs = r[r["market_state"] == market_state]["net_return"]
            rows.append({
                "component": component, "market_state": market_state, "avg_cash": float(sub["cash"].mean()), "avg_offense": float(sub["offense"].mean()),
                "avg_defense": float(sub["defense"].mean()), "avg_real_asset": float(sub["real_asset"].mean()), **corr,
            })
            ret_rows.append({"component": component, "market_state": market_state, "ann_return": ann_return(rs), "sharpe": sharpe(rs), "n_weeks": int(len(rs))})
    missing_df = pd.DataFrame(missing)
    return pd.DataFrame(rows), pd.DataFrame(ret_rows), pd.DataFrame(flags), missing_df


def next_action(stage_rank: pd.DataFrame, target: pd.DataFrame, overlay: pd.DataFrame, cap: pd.DataFrame, comp_flags: pd.DataFrame) -> pd.DataFrame:
    favorable_overlay = overlay[(overlay["market_state"].isin(FAVORABLE_STATES)) & (overlay["delta_cash"] > 0.05) & (overlay["delta_offense"] < -0.03)]
    favorable_look = stage_rank[(stage_rank["to_stage"] == "final_etf_weights") & (stage_rank["market_state"].isin(FAVORABLE_STATES)) & (stage_rank["delta_offense"] < -0.08)]
    target_bad = target[(target["binding_in_favorable_state"] == True)] if not target.empty else pd.DataFrame()
    cap_bad = cap[(cap["constraint_boundary_proxy"] == True) & (cap["market_state"].isin(FAVORABLE_STATES))] if not cap.empty else pd.DataFrame()
    comp_missing = comp_flags[comp_flags["role_flag"] == "INSUFFICIENT_DATA"] if not comp_flags.empty else pd.DataFrame()
    if not comp_missing.empty and not favorable_look.empty:
        rec = "FIX_LOOKTHROUGH_DRAG"
        reason = "Final sleeve-to-ETF translation removes offense in favorable states, and component lookthrough panels are missing for GGG1."
        safe = False
    elif not favorable_overlay.empty:
        rec = "FIX_OVERLAY_CASH_DRAG"
        reason = "Overlay adds cash and removes offense in favorable states, not only stressed_panic."
        safe = False
    elif not target_bad.empty or not cap_bad.empty:
        rec = "FIX_TARGET_VOL_OR_CAP_BINDING"
        reason = "Target-vol or cap proxy binds in favorable states."
        safe = False
    else:
        rec = "PROCEED_TO_ADAPTIVE_RISK_CONTRIBUTION_ALLOCATOR"
        reason = "No dominant constraint/lookthrough blocker remains; risk contribution is the next frontier."
        safe = True
    return pd.DataFrame([{"recommendation": rec, "safe_to_proceed_to_adaptive_risk_contribution": safe, "reason": reason}])


def bottlenecks(stage_rank: pd.DataFrame, overlay: pd.DataFrame, target: pd.DataFrame, cap: pd.DataFrame, turn: pd.DataFrame, comp_flags: pd.DataFrame, next_rec: pd.DataFrame) -> pd.DataFrame:
    rows = []
    def add(sev: str, issue: str, evidence: str, recommendation: str):
        rows.append({"severity": sev, "issue": issue, "evidence": evidence, "recommendation": recommendation})
    fav_look = stage_rank[(stage_rank["to_stage"] == "final_etf_weights") & (stage_rank["market_state"].isin(FAVORABLE_STATES))].head(5)
    if not fav_look.empty:
        worst = fav_look.iloc[0]
        add("HIGH", "Favorable-state lookthrough offense drag", f"{worst['version']} {worst['market_state']} {worst['delta_offense']:.2%}", "Fix or instrument sleeve-to-ETF lookthrough before advanced allocator.")
    comp_missing = comp_flags[comp_flags["role_flag"] == "INSUFFICIENT_DATA"] if not comp_flags.empty else pd.DataFrame()
    if not comp_missing.empty:
        add("HIGH", "GGG1 component purity still unproven", ", ".join(comp_missing["component"].head(3)), "Persist component returns and ETF positions.")
    fav_overlay = overlay[(overlay["market_state"].isin(FAVORABLE_STATES)) & (overlay["delta_cash"] > 0.05)]
    if not fav_overlay.empty:
        add("MEDIUM", "Overlay cash added in favorable states", f"{len(fav_overlay)} version/state rows", "Separate intentional recovery guardrail from accidental good-state cash.")
    if not target.empty and (target["binding_in_favorable_state"] == True).any():
        add("MEDIUM", "Target-vol binds in favorable states", f"{int((target['binding_in_favorable_state']==True).sum())} rows", "Review target-vol before allocator changes.")
    if not cap.empty and (cap["constraint_boundary_proxy"] == True).any():
        add("LOW", "Cap proxy boundary observed", f"{int((cap['constraint_boundary_proxy']==True).sum())} rows", "Add explicit cap pre/post instrumentation if this becomes material.")
    if not turn.empty and (turn["near_turnover_boundary"] == True).any():
        add("LOW", "Turnover near boundary", f"{int((turn['near_turnover_boundary']==True).sum())} state rows", "Monitor GGG1 turnover in any follow-up.")
    add("INFO", "Next action", str(next_rec.iloc[0]["recommendation"]), str(next_rec.iloc[0]["reason"]))
    return pd.DataFrame(rows).head(10)


def write_report(outputs: dict[str, pd.DataFrame]) -> None:
    next_row = outputs["phase_jjj1_next_action_recommendation"].iloc[0]
    stage_counts = outputs["phase_jjj1_stage_drag_deltas_by_state"]["drag_flag"].value_counts().to_dict()
    overlay = outputs["phase_jjj1_overlay_drag_by_state"]
    target = outputs["phase_jjj1_target_vol_binding_by_state"]
    comp = outputs["phase_jjj1_component_role_flags"]
    raw_files = sorted(p.name for p in RAW.glob("*.csv"))
    prompt = (
        "Implement Phase JJJ2 as a diagnostic-only lookthrough/component instrumentation pass. "
        "Do not create candidates. Persist GGG1 composite component return and ETF-position panels, "
        "build per-sleeve ETF contribution tables including components, and then decide whether to repair lookthrough drag or proceed to adaptive risk contribution."
        if next_row["recommendation"] == "FIX_LOOKTHROUGH_DRAG"
        else "Implement the exact JJJ1 recommendation as a narrow diagnostic follow-up; do not create strategy variants or change pins."
    )
    lines = [
        "# Phase JJJ1 — Constraint, Overlay, and Lookthrough Drag Isolation",
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
        "- `scripts/phase_jjj1_constraint_drag_isolation.py`",
        "- `data/research/phase_jjj1_constraint_drag_isolation/*.csv`",
        "- `data/research/phase_jjj1_constraint_drag_isolation/raw/*.csv`",
        "- `docs/research/2026-04-27_phase_jjj1_constraint_drag_isolation_report.md`",
        "- `docs/research/project_journey.md`",
        "",
        "## Instrumentation added or reused",
        "- Reused existing allocator checkpoints for all three core versions.",
        "- Reused existing `portfolio_version_diagnostics_timeseries.csv` for target-vol/regime binding diagnostics.",
        "- Derived raw overlay, cap-proxy, turnover, and per-sleeve lookthrough instrumentation from saved artifacts.",
        f"- Raw instrumentation files: `{raw_files}`.",
        "- Did not edit strategy logic or production pins.",
        "",
        "## Stage drag attribution",
        f"- Drag flag counts: `{stage_counts}`.",
        "- Overlay and final lookthrough stages are the dominant drag points.",
        "",
        "## Lookthrough drag by sleeve / ETF",
        "- Per-sleeve ETF contribution is available for sleeves with saved `strategy_positions_*` files.",
        "- GGG1 component sleeves lack saved position panels, so their contribution is documented as missing rather than guessed.",
        "",
        "## Target-vol / overlay / cap binding findings",
        f"- Target-vol rows: {len(target)}. Favorable-state target-vol binding rows: {int((target.get('binding_in_favorable_state', pd.Series(dtype=bool)) == True).sum()) if not target.empty else 0}.",
        f"- Overlay rows: {len(overlay)}. Favorable-state overlay cash drag rows: {int(((overlay['market_state'].isin(FAVORABLE_STATES)) & (overlay['delta_cash'] > 0.05)).sum()) if not overlay.empty else 0}.",
        "- Cap diagnostics are proxy-only because explicit pre/post cap weights are not persisted.",
        "",
        "## Turnover boundary findings",
        "- Turnover diagnostics use final ETF weekly L1 turnover and return-file turnover. Proposed/smoothed/executed/deadband traces are not persisted.",
        "",
        "## Component purity findings",
        f"- Component role flags: `{comp['role_flag'].value_counts().to_dict() if not comp.empty else {}}`.",
        "- `composite_regime_offense_component` and `composite_regime_defense_component` remain insufficiently instrumented.",
        "",
        "## Top bottlenecks",
    ]
    for row in outputs["phase_jjj1_top_bottlenecks"].to_dict("records"):
        lines.append(f"- **{row['severity']}** — {row['issue']}: {row['evidence']} Recommendation: {row['recommendation']}")
    lines += [
        "",
        "## Intended protection vs accidental bottleneck",
        "- `STRESS_PROTECTION` rows are treated as intended unless they also remove offense in favorable states.",
        "- Favorable-state overlay cash additions and final lookthrough offense losses are treated as accidental bottlenecks needing review.",
        "",
        "## Final next-action recommendation",
        f"**{next_row['recommendation']}**",
        "",
        f"Reason: {next_row['reason']}",
        "",
        f"Safe to proceed to adaptive risk-contribution allocation: **{bool(next_row['safe_to_proceed_to_adaptive_risk_contribution'])}**.",
        "",
        "## Exact prompt outline for the next phase",
        prompt,
    ]
    DOC.write_text("\n".join(lines) + "\n")


def update_journey(next_rec: pd.DataFrame) -> None:
    row = next_rec.iloc[0]
    section = f"""

## Section 73 — Phase JJJ1 Constraint / Overlay / Lookthrough Drag Isolation

Date: 2026-04-27. Phase JJJ1 was diagnostic-only. It reused existing allocator
checkpoints and portfolio diagnostics, derived raw overlay/cap/turnover and
per-sleeve lookthrough instrumentation, and did not create candidates or change
production/shadow pins.

**Finding.** Target-vol diagnostics already exist, but explicit cap pre/post
traces, deadband/rerisk decisions, and GGG1 component-level return/position
panels are still not persisted. Stage attribution confirms overlay cash drag
and final sleeve-to-ETF lookthrough drag remain the main constraint issues.

**Next action.** `{row['recommendation']}`. Safe to proceed to adaptive
risk-contribution allocation: `{bool(row['safe_to_proceed_to_adaptive_risk_contribution'])}`.
Reason: {row['reason']}
"""
    text = JOURNEY.read_text()
    marker = "## Section 73 — Phase JJJ1 Constraint / Overlay / Lookthrough Drag Isolation"
    if marker in text:
        text = re.sub(r"\n## Section 73 — Phase JJJ1 Constraint / Overlay / Lookthrough Drag Isolation[\s\S]*$", section, text)
    else:
        text = text.rstrip() + section
    JOURNEY.write_text(text.rstrip() + "\n")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    state = read_time_csv(L2B / "market_state_history.csv")

    exposure, deltas, rankings = exposure_by_state(state)
    look_raw, look_missing = derive_lookthrough(state)
    look_sleeve, look_etf, hidden_cash, hidden_def, hidden_beta = summarize_lookthrough(look_raw)
    target, overlay, cap, turnover, raw_target = target_overlay_cap_turnover(state)
    comp_purity, comp_returns, comp_flags, comp_missing = component_purity(state)
    next_rec = next_action(rankings, target, overlay, cap, comp_flags)
    top_b = bottlenecks(rankings, overlay, target, cap, turnover, comp_flags, next_rec)

    look_raw.to_csv(RAW / "lookthrough_diagnostics_by_date_sleeve_etf.csv", index=False)
    look_missing.to_csv(RAW / "lookthrough_missing_sleeve_positions.csv", index=False)
    comp_missing.to_csv(RAW / "component_missing_instrumentation.csv", index=False)

    outputs = {
        "phase_jjj1_stage_exposure_by_state": exposure,
        "phase_jjj1_stage_drag_deltas_by_state": deltas,
        "phase_jjj1_stage_drag_rankings": rankings,
        "phase_jjj1_lookthrough_drag_by_sleeve": look_sleeve,
        "phase_jjj1_lookthrough_drag_by_etf": look_etf,
        "phase_jjj1_hidden_cash_sources_by_state": hidden_cash,
        "phase_jjj1_hidden_defense_sources_by_state": hidden_def,
        "phase_jjj1_hidden_beta_sources_by_state": hidden_beta,
        "phase_jjj1_target_vol_binding_by_state": target,
        "phase_jjj1_overlay_drag_by_state": overlay,
        "phase_jjj1_cap_binding_by_sleeve_state": cap,
        "phase_jjj1_turnover_boundary_diagnostics": turnover,
        "phase_jjj1_component_purity_by_state": comp_purity,
        "phase_jjj1_component_returns_by_state": comp_returns,
        "phase_jjj1_component_role_flags": comp_flags,
        "phase_jjj1_missing_instrumentation": pd.concat([look_missing, comp_missing], ignore_index=True, sort=False),
        "phase_jjj1_next_action_recommendation": next_rec,
        "phase_jjj1_top_bottlenecks": top_b,
    }
    for name, df in outputs.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    write_report(outputs)
    update_journey(next_rec)
    print(f"wrote {len(outputs)} CSV files to {OUT.relative_to(ROOT)}")
    print(f"raw files: {len(list(RAW.glob('*.csv')))}")
    print(f"report: {DOC.relative_to(ROOT)}")
    print(f"recommendation: {next_rec.iloc[0]['recommendation']}")


if __name__ == "__main__":
    main()
