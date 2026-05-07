#!/usr/bin/env python3
"""
Phase 4B - Refined Sector Rotation / Breadth Timing Audit

Focused refinement of Phase 4 sector rotation. The script builds a small set
of causal sector signals and sleeves, validates them standalone and by state,
then runs at most five controlled Layer 3 candidates through the existing
filtered production build path. No production/shadow/GGG1 pins are changed.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "data" / "01_data_hub"
L1 = ROOT / "data" / "02_layer1_signals"
L2A = ROOT / "data" / "03_layer2a_strategy_logic"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
PHASE4_OUT = ROOT / "data" / "research" / "phase_4_sector_breadth_rotation"
OUT = ROOT / "data" / "research" / "phase_4b_refined_sector_rotation"
REPORT = ROOT / "docs" / "research" / "2026-05-07_phase_4b_refined_sector_rotation_report.md"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS = 52
COST_BPS = 10
CASH = "BIL"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
OFFICIAL_SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PHASE2_BEST = "improved_phase2_aggressive_neutral_cash_unlock"
PHASE3_BEST = "improved_phase3_high_breadth_calm_us_offense"
PHASE4_BEST = "improved_phase4_sector_20pct_offense"

CANDIDATES = [
    "improved_phase4b_refined_sector_small_overlay",
    "improved_phase4b_refined_sector_20pct",
    "improved_phase4b_refined_sector_25pct_selective",
    "improved_phase4b_sector_phase3_hybrid",
    "improved_phase4b_return_unlock_stretch",
]

WINDOWS = {
    "full": (None, None),
    "holdout_2016": ("2016-01-01", None),
    "holdout_2020": ("2020-01-01", None),
    "holdout_2021": ("2021-01-01", None),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "recovery_2023": ("2023-01-01", None),
}

SECTOR_CATALOG = {
    "XLK": ("broad_sector", "Technology"),
    "XLF": ("broad_sector", "Financials"),
    "XLV": ("broad_sector", "Healthcare"),
    "XLY": ("broad_sector", "Consumer Discretionary"),
    "XLP": ("broad_sector", "Consumer Staples"),
    "XLI": ("broad_sector", "Industrials"),
    "XLE": ("broad_sector", "Energy"),
    "XLU": ("broad_sector", "Utilities"),
    "XLB": ("broad_sector", "Materials"),
    "XLRE": ("broad_sector", "Real Estate"),
    "VNQ": ("broad_sector_proxy", "Real Estate"),
    "IYR": ("broad_sector_proxy", "Real Estate"),
    "XLC": ("broad_sector", "Communication Services"),
    "SMH": ("industry_growth", "Semiconductors"),
    "IGV": ("industry_growth", "Software"),
    "XRT": ("industry", "Retail"),
    "IBB": ("industry", "Biotech"),
    "IYT": ("industry", "Transportation"),
}

BUILD_SLEEVE_MAP = {
    "phase4b_top5_smooth_sector_sleeve": "Top5_Smooth_Momentum",
    "phase4b_top4_risk_adjusted_sector_sleeve": "Top4_RiskAdjusted_Momentum",
    "phase4b_top3_strict_sector_sleeve": "Top3_Strict_Leadership",
    "phase4b_defensive_aware_top5_sleeve": "DefensiveAware_Top5",
    "phase4b_sector_blend_spy_qqq_sleeve": "SectorBlend_SPY_QQQ",
    "phase4b_balanced_carry_forward_sleeve": "SectorBalancedCarryForward",
}

ARTIFACT_NAME_BY_LABEL = {
    "ggg1": GGG1,
    "phase2_best": PHASE2_BEST,
    "phase3_best": PHASE3_BEST,
    "phase4_best": PHASE4_BEST,
    "prod_pin": PRODUCTION_PIN,
    "official_shadow": OFFICIAL_SHADOW,
}

COMMANDS_EXECUTED = [
    "pwd",
    "git status --short",
    "git branch --show-current",
    "git worktree list",
    "find .. -name CLAUDE.md -maxdepth 3",
    "sed -n '1,220p' CLAUDE.md",
    "prerequisite file existence check",
    "Phase 4 artifact/schema inspection commands",
    "python3 -m py_compile scripts/build_improvement_artifacts.py scripts/phase_4b_refined_sector_rotation.py",
    "python3 scripts/phase_4b_refined_sector_rotation.py",
]


def clean_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()


def ann_return(s: pd.Series) -> float:
    s = clean_series(s)
    if s.empty:
        return np.nan
    return float((1.0 + s).prod() ** (WEEKS / len(s)) - 1.0)


def calc_metrics(ret: pd.Series, label: str = "") -> dict:
    ret = clean_series(ret)
    if len(ret) < 8:
        return {
            "label": label,
            "n_weeks": int(len(ret)),
            "ann_return": np.nan,
            "ann_vol": np.nan,
            "sharpe": np.nan,
            "max_drawdown": np.nan,
            "calmar": np.nan,
            "cvar_5": np.nan,
            "worst_4w": np.nan,
            "worst_13w": np.nan,
        }
    ar = ann_return(ret)
    av = float(ret.std() * np.sqrt(WEEKS))
    wealth = (1.0 + ret).cumprod()
    dd = wealth / wealth.cummax() - 1.0
    max_dd = float(dd.min())
    cvar = float(ret[ret <= ret.quantile(0.05)].mean())
    return {
        "label": label,
        "n_weeks": int(len(ret)),
        "ann_return": ar,
        "ann_vol": av,
        "sharpe": ar / av if av > 0 else np.nan,
        "max_drawdown": max_dd,
        "calmar": ar / abs(max_dd) if max_dd < 0 else np.nan,
        "cvar_5": cvar,
        "worst_4w": float(ret.rolling(4).sum().min()) if len(ret) >= 4 else np.nan,
        "worst_13w": float(ret.rolling(13).sum().min()) if len(ret) >= 13 else np.nan,
    }


def ws(obj: pd.Series | pd.DataFrame, start: str | None, end: str | None):
    out = obj.copy()
    if start:
        out = out[out.index >= pd.Timestamp(start)]
    if end:
        out = out[out.index <= pd.Timestamp(end)]
    return out


def load_return_artifact(path: Path) -> pd.Series:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index).tz_localize(None)
    col = "net_return" if "net_return" in df.columns else df.columns[0]
    return pd.to_numeric(df[col], errors="coerce")


def load_strategy_return(path: Path) -> pd.Series:
    df = pd.read_csv(path, parse_dates=["Date"])
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    df = df.set_index("Date").sort_index()
    col = "net_return" if "net_return" in df.columns else df.columns[-1]
    return pd.to_numeric(df[col], errors="coerce")


def artifact_name(label: str) -> str:
    return ARTIFACT_NAME_BY_LABEL.get(label, label)


def compute_path(weights: pd.DataFrame, next_returns: pd.DataFrame, cash_returns: pd.Series) -> pd.DataFrame:
    weights = weights.reindex(index=next_returns.index, columns=next_returns.columns).fillna(0.0)
    gross_return = (weights * next_returns).sum(axis=1)
    residual_cash = (1.0 - weights.clip(lower=0.0).sum(axis=1)).clip(lower=0.0)
    gross_return = gross_return + residual_cash * cash_returns.reindex(weights.index).fillna(0.0)
    turnover = 0.5 * weights.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = np.nan
    cost = turnover.fillna(0.0) * (COST_BPS / 10000.0)
    net_return = gross_return - cost
    wealth = (1.0 + net_return.fillna(0.0)).cumprod()
    drawdown = wealth / wealth.cummax() - 1.0
    return pd.DataFrame(
        {
            "gross_return": gross_return,
            "net_return": net_return,
            "turnover": turnover,
            "cost": cost,
            "wealth": wealth,
            "drawdown": drawdown,
        }
    )


def beta_corr(port: pd.Series, bm: pd.Series) -> tuple[float, float]:
    common = clean_series(port).index.intersection(clean_series(bm).index)
    if len(common) < 8:
        return np.nan, np.nan
    p = pd.to_numeric(port.reindex(common), errors="coerce")
    b = pd.to_numeric(bm.reindex(common), errors="coerce")
    cov = np.cov(p, b)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    return float(beta), float(p.corr(b))


def capture(port: pd.Series, bm: pd.Series) -> tuple[float, float, float, float]:
    common = clean_series(port).index.intersection(clean_series(bm).index)
    if len(common) < 8:
        return np.nan, np.nan, np.nan, np.nan
    p = pd.to_numeric(port.reindex(common), errors="coerce")
    b = pd.to_numeric(bm.reindex(common), errors="coerce")
    up = b > 0
    down = b < 0
    upside = float(p[up].sum() / b[up].sum()) if up.sum() > 2 and abs(float(b[up].sum())) > 1e-12 else np.nan
    downside = float(p[down].sum() / b[down].sum()) if down.sum() > 2 and abs(float(b[down].sum())) > 1e-12 else np.nan
    beta, corr = beta_corr(p, b)
    return upside, downside, beta, corr


def active_ann_return(port: pd.Series, bm: pd.Series) -> float:
    common = clean_series(port).index.intersection(clean_series(bm).index)
    if len(common) < 8:
        return np.nan
    return ann_return(port.reindex(common)) - ann_return(bm.reindex(common))


def cap_weights(raw: pd.Series, cap: float) -> pd.Series:
    raw = pd.Series(raw, dtype=float).clip(lower=0.0)
    if raw.sum() <= 1e-12:
        return raw
    w = raw / raw.sum()
    for _ in range(10):
        over = w > cap
        if not over.any():
            break
        excess = float((w[over] - cap).sum())
        w[over] = cap
        under = ~over
        under_sum = float(w[under].sum())
        if under_sum <= 1e-12:
            break
        w[under] += excess * (w[under] / under_sum)
    return w / w.sum() if w.sum() > 0 else w


def md_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df.head(max_rows).copy()
    try:
        return small.to_markdown(index=False)
    except Exception:
        return "```\n" + small.to_string(index=False) + "\n```"


def bool_mean(mask: pd.Series) -> float:
    mask = pd.Series(mask).dropna()
    return float(mask.mean()) if len(mask) else np.nan


def load_optional_phase4_tables() -> dict[str, pd.DataFrame]:
    tables = {}
    for name in [
        "phase4_sector_sleeve_validation.csv",
        "phase4_sector_sleeve_state_validation.csv",
        "phase4_sector_sleeve_holdout_validation.csv",
        "phase4_sector_rotation_signal_panel.csv",
        "phase4_sector_sleeve_turnover.csv",
        "phase4_selection_table.csv",
        "phase4_state_summary.csv",
        "phase4_signal_active_candidate_performance.csv",
        "phase4_sector_concentration_checks.csv",
        "phase4_hidden_beta_cash_checks.csv",
    ]:
        path = PHASE4_OUT / name
        if path.exists():
            kwargs = {"index_col": 0, "parse_dates": True} if name.endswith("_panel.csv") else {}
            tables[name] = pd.read_csv(path, **kwargs)
            if name.endswith("_panel.csv"):
                tables[name].index = pd.to_datetime(tables[name].index).tz_localize(None)
    return tables


def main() -> None:
    print("=== Phase 4B - Refined Sector Rotation / Breadth Timing Audit ===")
    print(f"Output directory: {OUT}")

    prices = pd.read_csv(HUB / "weekly_prices.csv", index_col="Date", parse_dates=True)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    returns = prices.pct_change()
    next_returns = returns.shift(-1)
    cash_returns = next_returns.get(CASH, pd.Series(0.0, index=prices.index)).fillna(0.0)

    msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)
    msh.index = pd.to_datetime(msh.index).tz_localize(None)
    msh = msh.reindex(prices.index).ffill()
    state = msh["market_state"].astype(str)

    rf_path = L1 / "regime_features.csv"
    rf = pd.DataFrame(index=prices.index)
    if rf_path.exists():
        rf = pd.read_csv(rf_path, index_col="Date", parse_dates=True)
        rf.index = pd.to_datetime(rf.index).tz_localize(None)
        rf = rf.reindex(prices.index).ffill()

    spy_ret = returns["SPY"].dropna() if "SPY" in returns.columns else pd.Series(dtype=float)
    qqq_ret = returns["QQQ"].dropna() if "QQQ" in returns.columns else pd.Series(dtype=float)
    bil_ret = returns[CASH].dropna() if CASH in returns.columns else pd.Series(dtype=float)
    phase4_tables = load_optional_phase4_tables()

    # ------------------------------------------------------------------
    # PART A - Phase 4 diagnosis.
    # ------------------------------------------------------------------
    print("\n=== PART A: Phase 4 diagnosis ===")
    phase4_sel = phase4_tables.get("phase4_selection_table.csv", pd.DataFrame())
    phase4_state = phase4_tables.get("phase4_state_summary.csv", pd.DataFrame())
    phase4_sleeves = phase4_tables.get("phase4_sector_sleeve_validation.csv", pd.DataFrame())
    phase4_signal_active = phase4_tables.get("phase4_signal_active_candidate_performance.csv", pd.DataFrame())
    phase4_conc = phase4_tables.get("phase4_sector_concentration_checks.csv", pd.DataFrame())
    phase4_hidden = phase4_tables.get("phase4_hidden_beta_cash_checks.csv", pd.DataFrame())

    def phase4_lookup(portfolio: str, col: str, default=np.nan):
        if phase4_sel.empty or col not in phase4_sel.columns:
            return default
        hit = phase4_sel.loc[phase4_sel["portfolio"] == portfolio, col]
        return hit.iloc[0] if not hit.empty else default

    p4_20_ret = phase4_lookup(PHASE4_BEST, "full_ann_return")
    p4_20_sharpe = phase4_lookup(PHASE4_BEST, "full_sharpe")
    p4_25_ret = phase4_lookup("improved_phase4_sector_25pct_offense", "full_ann_return")
    p4_25_sharpe = phase4_lookup("improved_phase4_sector_25pct_offense", "full_sharpe")

    diagnosis_rows = [
        {
            "question": "Why did improved_phase4_sector_20pct_offense improve full return but not Sharpe enough?",
            "diagnosis": "The 20pct overlay added a larger dedicated sector offense budget and reduced BIL in active weeks, lifting full return, but the active sleeve remained high-volatility sector momentum. Incremental volatility and drawdown outweighed enough of the return lift to keep Sharpe near 0.93 rather than 0.95+.",
            "evidence": f"Phase 4 20pct full return={p4_20_ret:.6f}, Sharpe={p4_20_sharpe:.6f}; standalone sector sleeves had materially lower Sharpe than the final portfolio.",
        },
        {
            "question": "Why did 25pct not dominate 20pct?",
            "diagnosis": "The extra 5% budget was funded from already useful defensive/cash/offense sleeves and increased sector volatility. It did not produce enough active-window return to compensate, so return was flat/slightly lower and Sharpe deteriorated.",
            "evidence": f"Phase 4 25pct return={p4_25_ret:.6f}, Sharpe={p4_25_sharpe:.6f} versus 20pct return={p4_20_ret:.6f}, Sharpe={p4_20_sharpe:.6f}.",
        },
        {
            "question": "Why did balanced/stretched sector sleeves underperform?",
            "diagnosis": "Balanced sleeves were safer but diluted the return unlock; stretch sleeves were more concentrated and had poorer active-window evidence. The strongest standalone sector sleeve was not strong enough to support more concentration.",
            "evidence": "Phase 4 selection rejected balanced/stretch variants; standalone Top3/Top5 sector momentum had Sharpe below equal-sector and large drawdowns.",
        },
        {
            "question": "Which states benefited most?",
            "diagnosis": "Recovery_confirmed and calm_trend had visible return lift versus GGG1; neutral_mixed return improved but Sharpe did not dominate Phase 2.",
            "evidence": "Phase 4 state summary showed sector exposure helped selected non-stressed states while preserving stressed_panic protection.",
        },
        {
            "question": "Which states were harmed?",
            "diagnosis": "Weak neutral and inactive/fallback windows were the main drag. Broad neutral activation created more whipsaw than clean Sharpe improvement.",
            "evidence": "Neutral_mixed Sharpe for 20pct trailed GGG1/Phase2 even though return improved modestly.",
        },
        {
            "question": "Did sector-active weeks truly beat GGG1 / Phase 2 / Phase 3 after costs?",
            "diagnosis": "Yes for the best 20pct sleeve versus GGG1 on the sector_breadth_confirmed gate, but the edge was small and did not scale well to 25pct or stretch.",
            "evidence": "Phase 4 signal-active table showed positive active delta for 20pct, but a small magnitude.",
        },
        {
            "question": "Was the sector sleeve too active or active in the wrong states?",
            "diagnosis": "The Phase 4 breadth gate was broad, especially in neutral_mixed. Phase 4B should narrow activation to high-quality bull, calm leadership, and separately confirmed neutral/recovery states.",
            "evidence": "sector_breadth_confirmed fired across a large share of non-stressed weeks, including many neutral weeks.",
        },
        {
            "question": "Was top-3 too concentrated and top-5 too diluted?",
            "diagnosis": "Top3 had higher concentration and turnover without superior standalone Sharpe; Top5 was smoother but not strong enough by itself. Phase 4B tests top5 smoothing, top4 risk-adjusted, and strict top3 only under strong leadership.",
            "evidence": "Phase 4 Top3 standalone Sharpe trailed Top5 and EqualWeightSector; Phase 4 concentration table showed non-trivial single-sector peaks.",
        },
        {
            "question": "Did turnover or sector whipsaw hurt returns?",
            "diagnosis": "Likely yes. Top3 and defensive-filter designs had meaningful weekly turnover, and the active edge was too small to ignore cost/whipsaw drag.",
            "evidence": "Phase 4 standalone turnover was highest in concentrated/filtered rotation sleeves.",
        },
        {
            "question": "Did sector exposure mainly duplicate SPY/QQQ?",
            "diagnosis": "Not at the portfolio level. Hidden beta checks were low, although standalone sector ETFs remain equity-like and correlated with SPY.",
            "evidence": "Phase 4 hidden beta table classified 20pct hidden beta risk as low.",
        },
    ]
    pd.DataFrame(diagnosis_rows).to_csv(OUT / "phase4b_phase4_diagnosis.csv", index=False)

    weakness_rows = []
    if not phase4_sleeves.empty:
        for _, row in phase4_sleeves.iterrows():
            weakness = []
            if row.get("sharpe", np.nan) < 0.60:
                weakness.append("low_standalone_sharpe")
            if row.get("max_drawdown", 0) < -0.30:
                weakness.append("large_standalone_drawdown")
            if row.get("avg_turnover", 0) > 0.12:
                weakness.append("high_turnover")
            weakness_rows.append(
                {
                    "phase4_sleeve": row.get("sleeve"),
                    "ann_return": row.get("ann_return"),
                    "sharpe": row.get("sharpe"),
                    "max_drawdown": row.get("max_drawdown"),
                    "avg_turnover": row.get("avg_turnover"),
                    "weaknesses": "|".join(weakness) if weakness else "none",
                    "phase4b_response": "narrow activation, smoother top5/top4 ranks, defensive warning block, strict top3 only under high quality",
                }
            )
    pd.DataFrame(weakness_rows).to_csv(OUT / "phase4b_sector_weakness_map.csv", index=False)

    state_failure_rows = []
    if not phase4_state.empty:
        baseline = phase4_state[phase4_state["portfolio"] == "ggg1"].set_index("state")
        for _, row in phase4_state[phase4_state["portfolio"].isin(CANDIDATES + [PHASE4_BEST])].iterrows():
            st = row.get("state")
            if st not in baseline.index:
                continue
            state_failure_rows.append(
                {
                    "portfolio": row.get("portfolio"),
                    "state": st,
                    "ann_return": row.get("ann_return"),
                    "sharpe": row.get("sharpe"),
                    "delta_ann_return_vs_ggg1": row.get("ann_return") - baseline.at[st, "ann_return"],
                    "delta_sharpe_vs_ggg1": row.get("sharpe") - baseline.at[st, "sharpe"],
                    "avg_sector_sleeve_exposure": row.get("avg_sector_sleeve_exposure"),
                    "phase4b_response": "allow only if high-quality signal or state-specific confirmation is true",
                }
            )
    pd.DataFrame(state_failure_rows).to_csv(OUT / "phase4b_state_failure_map.csv", index=False)

    # ------------------------------------------------------------------
    # Shared sector feature construction for signals and sleeves.
    # ------------------------------------------------------------------
    p4_inv_path = PHASE4_OUT / "phase4_sector_universe_inventory.csv"
    if p4_inv_path.exists():
        p4_inv = pd.read_csv(p4_inv_path)
        eligible_sectors = p4_inv.loc[p4_inv.get("eligible_for_phase4_sector_sleeve", False).astype(bool), "ticker"].tolist()
        eligible_sectors = [t for t in eligible_sectors if t in prices.columns]
    else:
        broad_priority = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLI", "XLE", "XLU", "XLB", "XLRE", "VNQ", "IYR", "XLC"]
        eligible_sectors = [t for t in broad_priority if t in prices.columns]
    if len(eligible_sectors) < 6:
        raise SystemExit(f"Missing usable existing sector ETF universe for Phase 4B: {eligible_sectors}")

    sector_prices = prices[eligible_sectors]
    sector_returns = returns[eligible_sectors]
    mom4 = sector_prices.pct_change(4)
    mom13 = sector_prices.pct_change(13)
    mom26 = sector_prices.pct_change(26)
    mom52 = sector_prices.pct_change(52)
    vol13 = sector_returns.rolling(13).std() * np.sqrt(WEEKS)
    vol26 = sector_returns.rolling(26).std() * np.sqrt(WEEKS)
    blended_mom = 0.5 * mom13 + 0.5 * mom26
    risk_adj_mom = blended_mom / vol26.replace(0, np.nan)
    ma26 = sector_prices.rolling(26).mean()
    ma43 = sector_prices.rolling(43).mean()
    trend26 = sector_prices > ma26
    trend43 = sector_prices > ma43
    spy_mom26 = prices["SPY"].pct_change(26) if "SPY" in prices.columns else pd.Series(np.nan, index=prices.index)
    qqq_mom26 = prices["QQQ"].pct_change(26) if "QQQ" in prices.columns else pd.Series(np.nan, index=prices.index)

    breadth = pd.DataFrame(index=prices.index)
    breadth["sector_pct_trend_positive_43w"] = trend43.mean(axis=1)
    breadth["sector_pct_trend_positive_26w"] = trend26.mean(axis=1)
    breadth["sector_pct_positive_13w_return"] = (mom13 > 0).mean(axis=1)
    breadth["sector_pct_positive_26w_return"] = (mom26 > 0).mean(axis=1)
    breadth["sector_top_26w_momentum"] = mom26.max(axis=1)
    breadth["sector_median_26w_momentum"] = mom26.median(axis=1)
    breadth["sector_top_minus_median_26w"] = breadth["sector_top_26w_momentum"] - breadth["sector_median_26w_momentum"]
    breadth["sector_top_minus_spy_26w"] = breadth["sector_top_26w_momentum"] - spy_mom26
    breadth["sector_top_minus_qqq_26w"] = breadth["sector_top_26w_momentum"] - qqq_mom26
    breadth["sector_count_beating_spy_26w"] = mom26.gt(spy_mom26, axis=0).sum(axis=1)

    # ------------------------------------------------------------------
    # PART B - refined sector signals.
    # ------------------------------------------------------------------
    print("\n=== PART B: refined sector signals ===")
    market_trend = pd.to_numeric(msh.get("market_trend_positive", 0), errors="coerce").fillna(0).astype(bool)
    vix_z = pd.to_numeric(rf.get("vix_level_z_tradable", pd.Series(np.nan, index=prices.index)), errors="coerce").reindex(prices.index)
    vix_contained = (vix_z <= 0.85) | vix_z.isna()
    canary = pd.to_numeric(msh.get("canary_breadth_default", pd.Series(1.0, index=prices.index)), errors="coerce").fillna(1.0)
    credit_risk_appetite = canary >= 0.50
    neutral_deteriorating = (
        (state == "neutral_mixed")
        & (
            (pd.to_numeric(msh.get("breadth_sma_43", 0), errors="coerce").fillna(0) < 0.55)
            | (pd.to_numeric(msh.get("breadth_26w_mom", 0), errors="coerce").fillna(0) < 0.50)
            | (breadth["sector_pct_trend_positive_43w"] < 0.55)
        )
    )
    state_stability = (state == state.shift(1)).astype(float).rolling(4, min_periods=1).mean().fillna(0.0)
    top3_mom = mom26.rank(axis=1, ascending=False, method="first") <= 3
    defensive_leaders = [c for c in ["XLU", "XLP", "XLV"] if c in top3_mom.columns]
    defensive_top_count = top3_mom[defensive_leaders].sum(axis=1) if defensive_leaders else pd.Series(0, index=prices.index)

    signal_panel = pd.DataFrame(index=prices.index)
    signal_panel["defensive_sector_warning"] = (
        (defensive_top_count >= 2)
        & (breadth["sector_pct_trend_positive_43w"] < 0.55)
        & (state != "stressed_panic")
    ).astype(int)
    leadership_scaled = (breadth["sector_top_minus_median_26w"] / 0.18).clip(0, 1).fillna(0)
    signal_panel["sector_quality_score"] = (
        0.30 * breadth["sector_pct_trend_positive_43w"].clip(0, 1).fillna(0)
        + 0.20 * breadth["sector_pct_positive_26w_return"].clip(0, 1).fillna(0)
        + 0.20 * leadership_scaled
        + 0.15 * vix_contained.astype(float)
        + 0.10 * state_stability.clip(0, 1)
        + 0.05 * credit_risk_appetite.astype(float)
    ).clip(0, 1)
    base_nonstress = (
        (state != "stressed_panic")
        & (state != "recovery_fragile")
        & (signal_panel["defensive_sector_warning"] == 0)
        & vix_contained
    )
    signal_panel["high_quality_sector_bull"] = (
        base_nonstress
        & market_trend
        & (breadth["sector_pct_trend_positive_43w"] >= 0.70)
        & (breadth["sector_pct_positive_26w_return"] >= 0.65)
        & (breadth["sector_top_minus_median_26w"] >= 0.035)
        & (~neutral_deteriorating)
        & (state.isin(["calm_trend", "neutral_mixed", "recovery_confirmed"]))
    ).astype(int)
    signal_panel["calm_sector_leadership_only"] = (
        (state == "calm_trend")
        & base_nonstress
        & (breadth["sector_pct_trend_positive_43w"] >= 0.60)
        & (breadth["sector_top_minus_median_26w"] >= 0.025)
        & (breadth["sector_top_minus_spy_26w"] >= 0.010)
    ).astype(int)
    signal_panel["neutral_sector_confirmed_only"] = (
        (state == "neutral_mixed")
        & base_nonstress
        & market_trend
        & credit_risk_appetite
        & (~neutral_deteriorating)
        & (breadth["sector_pct_trend_positive_43w"] >= 0.75)
        & (breadth["sector_pct_positive_26w_return"] >= 0.70)
        & (breadth["sector_top_minus_spy_26w"] >= 0.0)
    ).astype(int)
    signal_panel["recovery_sector_reentry"] = (
        (state == "recovery_confirmed")
        & base_nonstress
        & market_trend
        & (state_stability >= 0.50)
        & (breadth["sector_pct_trend_positive_43w"] >= 0.65)
        & (breadth["sector_pct_positive_26w_return"] >= 0.60)
    ).astype(int)
    signal_panel["sector_quality_score_high"] = (
        base_nonstress
        & (signal_panel["sector_quality_score"] >= 0.72)
        & market_trend
        & (state.isin(["calm_trend", "neutral_mixed", "recovery_confirmed"]))
        & (~neutral_deteriorating)
    ).astype(int)
    signal_panel["market_state"] = state
    signal_panel["risk_state"] = msh.get("risk_state", pd.Series(index=prices.index, dtype=object)).astype(str)
    signal_panel.to_csv(OUT / "phase4b_refined_sector_signal_panel.csv")

    signal_defs = [
        {
            "signal": "high_quality_sector_bull",
            "formula": "non-stressed/non-fragile AND sector trend breadth>=0.70 AND positive 26w sectors>=0.65 AND leadership spread>=3.5pp AND market trend positive AND VIX contained AND not neutral_deteriorating/defensive warning",
            "active_weeks": int(signal_panel["high_quality_sector_bull"].sum()),
            "active_frequency": float(signal_panel["high_quality_sector_bull"].mean()),
            "lag_rule": "week-t features set week-t sleeve weight for week-t+1 returns",
            "causal_ok": True,
            "expected_use": "Primary refined sector offense gate",
            "economic_interpretation": "Broad enough sector participation with differentiated leadership and contained volatility.",
        },
        {
            "signal": "calm_sector_leadership_only",
            "formula": "market_state=calm_trend AND breadth>=0.60 AND top sector beats median>=2.5pp AND top sector beats SPY>=1.0pp AND VIX contained AND no defensive warning",
            "active_weeks": int(signal_panel["calm_sector_leadership_only"].sum()),
            "active_frequency": float(signal_panel["calm_sector_leadership_only"].mean()),
            "lag_rule": "week-t features set week-t sleeve weight for week-t+1 returns",
            "causal_ok": True,
            "expected_use": "Avoid neutral whipsaw while preserving calm leadership exposure",
            "economic_interpretation": "Calm-state sector leadership without weak broad-market tape.",
        },
        {
            "signal": "neutral_sector_confirmed_only",
            "formula": "market_state=neutral_mixed AND breadth>=0.75 AND positive 26w sectors>=0.70 AND market trend and canary breadth positive AND not neutral_deteriorating",
            "active_weeks": int(signal_panel["neutral_sector_confirmed_only"].sum()),
            "active_frequency": float(signal_panel["neutral_sector_confirmed_only"].mean()),
            "lag_rule": "week-t features set week-t sleeve weight for week-t+1 returns",
            "causal_ok": True,
            "expected_use": "Only unlock neutral sector exposure when confirmation is strong",
            "economic_interpretation": "Neutral tape is healthy enough to treat as a muted bull state.",
        },
        {
            "signal": "recovery_sector_reentry",
            "formula": "market_state=recovery_confirmed AND breadth>=0.65 AND positive 26w sectors>=0.60 AND market trend positive AND state stability>=0.50",
            "active_weeks": int(signal_panel["recovery_sector_reentry"].sum()),
            "active_frequency": float(signal_panel["recovery_sector_reentry"].mean()),
            "lag_rule": "week-t features set week-t sleeve weight for week-t+1 returns",
            "causal_ok": True,
            "expected_use": "Permit recovery_confirmed sector re-entry but not recovery_fragile",
            "economic_interpretation": "Re-risk only after recovery is confirmed and sector breadth has healed.",
        },
        {
            "signal": "sector_quality_score",
            "formula": "0.30*breadth + 0.20*positive_26w + 0.20*leadership_spread + 0.15*VIX_contained + 0.10*state_stability + 0.05*canary",
            "active_weeks": int((signal_panel["sector_quality_score"] >= 0.72).sum()),
            "active_frequency": float((signal_panel["sector_quality_score"] >= 0.72).mean()),
            "lag_rule": "week-t features set week-t sleeve weight for week-t+1 returns",
            "causal_ok": True,
            "expected_use": "Continuous quality diagnostic plus strict high-quality gate",
            "economic_interpretation": "Fixed-weight quality blend, not optimized.",
        },
        {
            "signal": "defensive_sector_warning",
            "formula": "two or more of XLU/XLP/XLV in top3 26w momentum while sector breadth<0.55",
            "active_weeks": int(signal_panel["defensive_sector_warning"].sum()),
            "active_frequency": float(signal_panel["defensive_sector_warning"].mean()),
            "lag_rule": "week-t features block week-t sleeve weight for week-t+1 returns",
            "causal_ok": True,
            "expected_use": "Block offense, never add offense",
            "economic_interpretation": "Leadership is defensive during weak breadth, so momentum is likely late-cycle/risk-off.",
        },
    ]
    pd.DataFrame(signal_defs).to_csv(OUT / "phase4b_refined_sector_signal_definitions.csv", index=False)

    coverage_rows = []
    for sig in [
        "high_quality_sector_bull",
        "calm_sector_leadership_only",
        "neutral_sector_confirmed_only",
        "recovery_sector_reentry",
        "sector_quality_score_high",
        "defensive_sector_warning",
    ]:
        active = signal_panel[sig].astype(bool)
        coverage_rows.append(
            {
                "signal": sig,
                "active_weeks": int(active.sum()),
                "active_frequency": float(active.mean()),
                "active_states": "|".join(sorted(state[active].dropna().unique())),
                "calm_trend_coverage": bool_mean(active[state == "calm_trend"]),
                "neutral_mixed_coverage": bool_mean(active[state == "neutral_mixed"]),
                "recovery_confirmed_coverage": bool_mean(active[state == "recovery_confirmed"]),
                "recovery_fragile_coverage": bool_mean(active[state == "recovery_fragile"]),
                "stressed_panic_coverage": bool_mean(active[state == "stressed_panic"]),
            }
        )
    coverage_df = pd.DataFrame(coverage_rows)
    coverage_df.to_csv(OUT / "phase4b_refined_sector_signal_coverage.csv", index=False)

    # ------------------------------------------------------------------
    # PART C - refined sleeve designs.
    # ------------------------------------------------------------------
    print("\n=== PART C: refined sector sleeve designs ===")
    sleeve_designs = [
        {
            "sleeve": "Top5_Smooth_Momentum",
            "tickers_used": ",".join(eligible_sectors),
            "weighting_method": "equal weight",
            "selection_rule": "top 5 by blended 13w/26w momentum; carry prior top names if still top 7 and trend positive",
            "lag_rule": "rank through week t, earn week t+1 returns",
            "state_active_profile": "standalone always invested when enough valid sectors; portfolio gate controls use",
            "reason_to_fix_phase4_weakness": "lower turnover and less top3 concentration while preserving leadership exposure",
        },
        {
            "sleeve": "Top4_RiskAdjusted_Momentum",
            "tickers_used": ",".join(eligible_sectors),
            "weighting_method": "inverse 26w volatility with 35% cap",
            "selection_rule": "top 4 by blended momentum divided by 26w vol, require positive 43w trend and 26w momentum",
            "lag_rule": "rank through week t, earn week t+1 returns",
            "state_active_profile": "standalone trend-filtered; portfolio gate controls use",
            "reason_to_fix_phase4_weakness": "reduce high-vol whipsaw and avoid negative-trend sectors",
        },
        {
            "sleeve": "Top3_Strict_Leadership",
            "tickers_used": ",".join(eligible_sectors),
            "weighting_method": "equal weight with 45% cap",
            "selection_rule": "top 3 by blended momentum only when sector_quality_score_high and leadership spread>=6pp",
            "lag_rule": "rank through week t, earn week t+1 returns",
            "state_active_profile": "selective; BIL fallback outside strongest leadership",
            "reason_to_fix_phase4_weakness": "keep top3 concentration only when Phase 4's broad gate is most convincing",
        },
        {
            "sleeve": "DefensiveAware_Top5",
            "tickers_used": ",".join(eligible_sectors),
            "weighting_method": "equal weight with 30% cap",
            "selection_rule": "top 5 by blended momentum, require positive trend/momentum, block defensive_sector_warning",
            "lag_rule": "rank through week t, earn week t+1 returns",
            "state_active_profile": "defensive warning blocks the sleeve to BIL",
            "reason_to_fix_phase4_weakness": "avoid late-cycle defensive leadership masquerading as offense",
        },
        {
            "sleeve": "SectorBlend_SPY_QQQ",
            "tickers_used": ",".join(eligible_sectors + [t for t in ["SPY", "QQQ"] if t in prices.columns]),
            "weighting_method": "70% DefensiveAware_Top5, 15% SPY, 15% QQQ",
            "selection_rule": "blend only when high_quality_sector_bull or calm_sector_leadership_only is active; otherwise BIL",
            "lag_rule": "rank/signal through week t, earn week t+1 returns",
            "state_active_profile": "calm/high-quality only",
            "reason_to_fix_phase4_weakness": "reduce pure sector whipsaw while auditing hidden SPY/QQQ beta explicitly",
        },
        {
            "sleeve": "SectorBalancedCarryForward",
            "tickers_used": ",".join(eligible_sectors),
            "weighting_method": "inverse vol with 25% cap",
            "selection_rule": "top 5 by blended momentum; only admit new names after they persist in top 5 for two weeks",
            "lag_rule": "rank through week t and t-1, earn week t+1 returns",
            "state_active_profile": "standalone carry-forward; portfolio gate controls use",
            "reason_to_fix_phase4_weakness": "reduce churn from one-week rank noise",
        },
    ]
    pd.DataFrame(sleeve_designs).to_csv(OUT / "phase4b_refined_sector_sleeve_designs.csv", index=False)

    all_columns = list(prices.columns)
    top5_mask = blended_mom.rank(axis=1, ascending=False, method="first") <= 5
    persistent_top5 = top5_mask & top5_mask.shift(1).fillna(False)

    def set_cash(weights: pd.DataFrame, date: pd.Timestamp) -> None:
        if CASH in weights.columns:
            weights.at[date, CASH] = 1.0

    def write_row(weights: pd.DataFrame, date: pd.Timestamp, raw: pd.Series, cap: float = 1.0) -> None:
        if raw.empty or raw.sum() <= 1e-12:
            set_cash(weights, date)
            return
        w = cap_weights(raw, cap=cap)
        weights.loc[date, w.index] = w.values
        if float(weights.loc[date].sum()) <= 1e-12:
            set_cash(weights, date)

    def top_names(date: pd.Timestamp, score: pd.Series, n: int, require_positive: bool = False) -> list[str]:
        s = score.copy().replace([np.inf, -np.inf], np.nan)
        if require_positive:
            s = s.where(trend43.loc[date])
            s = s.where(mom26.loc[date] > 0)
        return s.dropna().sort_values(ascending=False).head(n).index.tolist()

    def make_sleeve_weights(design: str) -> pd.DataFrame:
        weights = pd.DataFrame(0.0, index=prices.index, columns=all_columns)
        previous: list[str] = []
        for date in prices.index:
            if design == "Top5_Smooth_Momentum":
                score = blended_mom.loc[date]
                current_top7 = score.dropna().sort_values(ascending=False).head(7).index.tolist()
                keep = [t for t in previous if t in current_top7 and bool(trend43.loc[date, t])]
                fill = [t for t in current_top7 if t not in keep]
                selected = (keep + fill)[:5]
                selected = [t for t in selected if pd.notna(score.get(t))]
                if len(selected) < 3:
                    set_cash(weights, date)
                else:
                    write_row(weights, date, pd.Series(1.0, index=selected), cap=0.30)
                    previous = selected
                continue

            if design == "Top4_RiskAdjusted_Momentum":
                selected = top_names(date, risk_adj_mom.loc[date], 4, require_positive=True)
                if len(selected) < 3:
                    set_cash(weights, date)
                else:
                    inv_vol = (1.0 / vol26.loc[date, selected].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
                    write_row(weights, date, inv_vol if not inv_vol.empty else pd.Series(1.0, index=selected), cap=0.35)
                continue

            if design == "Top3_Strict_Leadership":
                if not bool(signal_panel.at[date, "sector_quality_score_high"]) or breadth.at[date, "sector_top_minus_median_26w"] < 0.06:
                    set_cash(weights, date)
                    continue
                selected = top_names(date, blended_mom.loc[date], 3, require_positive=True)
                if len(selected) < 2:
                    set_cash(weights, date)
                else:
                    write_row(weights, date, pd.Series(1.0, index=selected), cap=0.45)
                continue

            if design == "DefensiveAware_Top5":
                if bool(signal_panel.at[date, "defensive_sector_warning"]):
                    set_cash(weights, date)
                    continue
                selected = top_names(date, blended_mom.loc[date], 5, require_positive=True)
                if len(selected) < 3:
                    set_cash(weights, date)
                else:
                    write_row(weights, date, pd.Series(1.0, index=selected), cap=0.30)
                continue

            if design == "SectorBlend_SPY_QQQ":
                if not (bool(signal_panel.at[date, "high_quality_sector_bull"]) or bool(signal_panel.at[date, "calm_sector_leadership_only"])):
                    set_cash(weights, date)
                    continue
                selected = top_names(date, blended_mom.loc[date], 5, require_positive=True)
                if len(selected) < 3:
                    set_cash(weights, date)
                    continue
                raw = pd.Series(0.70 / len(selected), index=selected)
                if "SPY" in weights.columns:
                    raw.loc["SPY"] = raw.get("SPY", 0.0) + 0.15
                if "QQQ" in weights.columns:
                    raw.loc["QQQ"] = raw.get("QQQ", 0.0) + 0.15
                write_row(weights, date, raw, cap=0.30)
                continue

            if design == "SectorBalancedCarryForward":
                score = blended_mom.loc[date].where(trend43.loc[date]).where(mom26.loc[date] > 0)
                persistent = [t for t in score.index if bool(persistent_top5.loc[date, t]) and pd.notna(score.get(t))]
                ranked = score.dropna().sort_values(ascending=False).index.tolist()
                keep = [t for t in previous if t in ranked[:8]]
                selected = []
                for t in keep + persistent + ranked:
                    if t not in selected:
                        selected.append(t)
                    if len(selected) >= 5:
                        break
                if len(selected) < 3:
                    set_cash(weights, date)
                else:
                    inv_vol = (1.0 / vol26.loc[date, selected].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
                    write_row(weights, date, inv_vol if not inv_vol.empty else pd.Series(1.0, index=selected), cap=0.25)
                    previous = selected
                continue

            raise ValueError(design)
        return weights

    sleeve_weights = {name: make_sleeve_weights(name) for name in [d["sleeve"] for d in sleeve_designs]}
    sleeve_paths = {name: compute_path(w, next_returns, cash_returns) for name, w in sleeve_weights.items()}
    returns_wide = pd.DataFrame({name: path["net_return"] for name, path in sleeve_paths.items()})
    turnover_wide = pd.DataFrame({name: path["turnover"] for name, path in sleeve_paths.items()})
    returns_wide.to_csv(OUT / "phase4b_refined_sector_sleeve_returns.csv")
    turnover_wide.to_csv(OUT / "phase4b_refined_sector_sleeve_turnover.csv")

    weight_rows = []
    for name, weights in sleeve_weights.items():
        nz = weights.stack()
        nz = nz[nz.abs() > 1e-12]
        for (date, ticker), weight in nz.items():
            weight_rows.append({"date": date, "sleeve": name, "ticker": ticker, "weight": weight})
    pd.DataFrame(weight_rows).to_csv(OUT / "phase4b_refined_sector_sleeve_weights.csv", index=False)

    for build_name, design_name in BUILD_SLEEVE_MAP.items():
        sleeve_weights[design_name].to_csv(OUT / f"phase4b_build_sleeve_weights_{build_name}.csv")

    # ------------------------------------------------------------------
    # PART D - standalone and signal-active validation.
    # ------------------------------------------------------------------
    print("\n=== PART D: standalone and state validation ===")
    benchmark_returns = {
        "SPY": spy_ret,
        "QQQ": qqq_ret,
        "BIL": bil_ret,
        "EqualWeightSector": returns[eligible_sectors].mean(axis=1),
    }
    phase4_sleeve_returns_path = PHASE4_OUT / "phase4_sector_sleeve_returns.csv"
    if phase4_sleeve_returns_path.exists():
        p4_sleeve_ret = pd.read_csv(phase4_sleeve_returns_path, index_col=0, parse_dates=True)
        p4_sleeve_ret.index = pd.to_datetime(p4_sleeve_ret.index).tz_localize(None)
        for col in p4_sleeve_ret.columns:
            benchmark_returns[f"Phase4_{col}"] = pd.to_numeric(p4_sleeve_ret[col], errors="coerce")

    sleeve_val_rows = []
    sleeve_state_rows = []
    sleeve_hold_rows = []
    for name, path in sleeve_paths.items():
        ret = path["net_return"]
        for wname, (start, end) in WINDOWS.items():
            m = calc_metrics(ws(ret, start, end), name)
            row = {
                "sleeve": name,
                "window": wname,
                **m,
                "avg_turnover": float(ws(path["turnover"], start, end).mean()),
                "corr_spy": beta_corr(ws(ret, start, end), ws(spy_ret, start, end))[1],
                "beta_spy": beta_corr(ws(ret, start, end), ws(spy_ret, start, end))[0],
                "corr_qqq": beta_corr(ws(ret, start, end), ws(qqq_ret, start, end))[1],
                "beta_qqq": beta_corr(ws(ret, start, end), ws(qqq_ret, start, end))[0],
            }
            if wname == "full":
                sleeve_val_rows.append(row)
            else:
                sleeve_hold_rows.append(row)
        for st in sorted(state.dropna().unique()):
            idx = state[state == st].index
            sleeve_state_rows.append({"sleeve": name, "state": st, **calc_metrics(ret.reindex(idx), name)})

    sleeve_val_df = pd.DataFrame(sleeve_val_rows)
    sleeve_state_df = pd.DataFrame(sleeve_state_rows)
    sleeve_hold_df = pd.DataFrame(sleeve_hold_rows)
    sleeve_val_df.to_csv(OUT / "phase4b_refined_sector_sleeve_validation.csv", index=False)
    sleeve_state_df.to_csv(OUT / "phase4b_refined_sector_sleeve_state_validation.csv", index=False)
    sleeve_hold_df.to_csv(OUT / "phase4b_refined_sector_sleeve_holdout_validation.csv", index=False)

    phase4_best_ret = load_return_artifact(L3 / f"portfolio_version_returns_{PHASE4_BEST}.csv")
    ggg_ret = load_return_artifact(L3 / f"portfolio_version_returns_{GGG1}.csv")

    active_val_rows = []
    validation_signals = [
        "high_quality_sector_bull",
        "calm_sector_leadership_only",
        "neutral_sector_confirmed_only",
        "recovery_sector_reentry",
        "sector_quality_score_high",
    ]
    for sleeve_name, path in sleeve_paths.items():
        ret = path["net_return"]
        for sig in validation_signals:
            active = signal_panel[sig].astype(bool)
            for st in ["all"] + sorted(state.dropna().unique()):
                scope = pd.Series(True, index=prices.index) if st == "all" else (state == st)
                active_idx = signal_panel.index[active & scope]
                inactive_idx = signal_panel.index[(~active) & scope]
                active_ret = ret.reindex(active_idx)
                inactive_ret = ret.reindex(inactive_idx)
                adverse = active_ret.dropna() < -0.02
                active_val_rows.append(
                    {
                        "sleeve": sleeve_name,
                        "signal": sig,
                        "state": st,
                        "active_weeks": int(active_ret.dropna().shape[0]),
                        "inactive_weeks": int(inactive_ret.dropna().shape[0]),
                        "active_ann_return": ann_return(active_ret),
                        "inactive_ann_return": ann_return(inactive_ret),
                        "active_minus_inactive_ann_return": ann_return(active_ret) - ann_return(inactive_ret),
                        "active_sharpe": calc_metrics(active_ret, sleeve_name)["sharpe"],
                        "inactive_sharpe": calc_metrics(inactive_ret, sleeve_name)["sharpe"],
                        "active_vs_ggg1": ann_return(active_ret) - ann_return(ggg_ret.reindex(active_idx)),
                        "active_vs_phase4_20pct": ann_return(active_ret) - ann_return(phase4_best_ret.reindex(active_idx)),
                        "adverse_event_frequency": float(adverse.mean()) if len(adverse) else np.nan,
                    }
                )
    active_val_df = pd.DataFrame(active_val_rows)
    active_val_df.to_csv(OUT / "phase4b_signal_active_validation.csv", index=False)

    p4_best_sleeve_sharpe = float(phase4_sleeves["sharpe"].max()) if not phase4_sleeves.empty and "sharpe" in phase4_sleeves else np.nan
    p4_best_sleeve_calmar = float(phase4_sleeves["calmar"].max()) if not phase4_sleeves.empty and "calmar" in phase4_sleeves else np.nan
    p4_best_sleeve_dd = float(phase4_sleeves["max_drawdown"].max()) if not phase4_sleeves.empty and "max_drawdown" in phase4_sleeves else np.nan
    best_refined_sharpe = float(sleeve_val_df["sharpe"].max()) if not sleeve_val_df.empty else np.nan
    best_refined_calmar = float(sleeve_val_df["calmar"].max()) if not sleeve_val_df.empty else np.nan
    best_refined_return = float(sleeve_val_df["ann_return"].max()) if not sleeve_val_df.empty else np.nan
    best_active_delta = active_val_df.loc[active_val_df["state"] == "all", "active_vs_phase4_20pct"].max()
    refined_sleeve_validation_positive = bool(
        (
            pd.notna(p4_best_sleeve_sharpe)
            and best_refined_sharpe > p4_best_sleeve_sharpe + 0.015
        )
        or (
            pd.notna(p4_best_sleeve_calmar)
            and best_refined_calmar > p4_best_sleeve_calmar + 0.015
        )
        or (
            pd.notna(p4_best_sleeve_dd)
            and sleeve_val_df["max_drawdown"].max() > p4_best_sleeve_dd + 0.05
            and best_refined_return > 0.055
        )
        or (pd.notna(best_active_delta) and best_active_delta > 0.002)
    )
    print(f"Refined sector validation positive: {refined_sleeve_validation_positive}")

    # ------------------------------------------------------------------
    # PART E/F - candidate designs and filtered build.
    # ------------------------------------------------------------------
    print("\n=== PART E/F: candidate designs and filtered build ===")
    candidate_designs = [
        {
            "candidate": "improved_phase4b_refined_sector_small_overlay",
            "sector_sleeve": "Top5_Smooth_Momentum",
            "budget": "12% target in high_quality_sector_bull",
            "logic": "Sharpe-first small overlay from the GGG1 base; target sector sleeve is stripped outside the gate, with residual monthly/smoothing exposure checked in stress diagnostics.",
        },
        {
            "candidate": "improved_phase4b_refined_sector_20pct",
            "sector_sleeve": "DefensiveAware_Top5",
            "budget": "20% target in high_quality_sector_bull or calm_sector_leadership_only",
            "logic": "Main Phase 4B test: smoother/defensive-aware replacement for Phase 4 20pct top3 sleeve.",
        },
        {
            "candidate": "improved_phase4b_refined_sector_25pct_selective",
            "sector_sleeve": "Top3_Strict_Leadership",
            "budget": "25% target only when sector_quality_score_high",
            "logic": "Selective concentrated version; accepts top3 only under the strongest fixed-quality signal.",
        },
        {
            "candidate": "improved_phase4b_sector_phase3_hybrid",
            "sector_sleeve": "SectorBlend_SPY_QQQ plus Phase 3 calm US offense",
            "budget": "16% target in high-quality/calm-leadership sector regimes",
            "logic": "Risk-adjusted hybrid that combines Phase 3 calm US offense with a blended sector sleeve.",
        },
        {
            "candidate": "improved_phase4b_return_unlock_stretch",
            "sector_sleeve": "Top3_Strict_Leadership",
            "budget": "25% target in strongest quality/confirmed neutral regimes plus full aggressive mandate",
            "logic": "Strongest return-unlock attempt; reject on Sharpe, drawdown, 2022/stress, or hidden beta failure.",
        },
    ]
    pd.DataFrame(candidate_designs).to_csv(OUT / "phase4b_candidate_designs.csv", index=False)

    build_skipped = False
    if not refined_sleeve_validation_positive:
        build_skipped = True
        pd.DataFrame(
            [{"portfolio": c, "reason": "refined_sector_sleeves_failed_to_improve_phase4_quality"} for c in CANDIDATES]
        ).to_csv(OUT / "phase4b_candidate_failure_reasons.csv", index=False)
        print("Skipping portfolio builds because refined sleeve validation did not improve Phase 4 quality.")
    else:
        env = os.environ.copy()
        env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
        build_script = ROOT / "scripts" / "build_improvement_artifacts.py"
        print("Running filtered Layer 3 build for Phase 4B candidates...")
        res = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )
        with open(OUT / "phase4b_build.log", "w") as f:
            f.write("COMMAND: BUILD_VERSION_NAMES='" + env["BUILD_VERSION_NAMES"] + "' python3 scripts/build_improvement_artifacts.py\n")
            f.write("\n=== STDOUT TAIL ===\n")
            f.write(res.stdout[-12000:])
            f.write("\n=== STDERR TAIL ===\n")
            f.write(res.stderr[-6000:])
        if res.returncode != 0:
            print(res.stdout[-2000:])
            print(res.stderr[-2000:])
            raise SystemExit(f"Layer 3 Phase 4B build failed with exit {res.returncode}")
        missing = [
            f"portfolio_version_{kind}_{candidate}.csv"
            for candidate in CANDIDATES
            for kind in ["returns", "weights", "sleeve_weights"]
            if not (L3 / f"portfolio_version_{kind}_{candidate}.csv").exists()
        ]
        if missing:
            raise SystemExit(f"Missing Phase 4B candidate artifacts after build: {missing}")
        pd.DataFrame([{"portfolio": "none", "reason": "all_built"}]).to_csv(
            OUT / "phase4b_candidate_failure_reasons.csv", index=False
        )
        print("All Phase 4B candidate artifacts confirmed.")

    # ------------------------------------------------------------------
    # PART G - full and holdout metrics.
    # ------------------------------------------------------------------
    print("\n=== PART G: full and holdout metrics ===")
    return_series: dict[str, pd.Series] = {}
    if not build_skipped:
        for c in CANDIDATES:
            return_series[c] = load_return_artifact(L3 / f"portfolio_version_returns_{c}.csv")
    baseline_files = {
        "ggg1": L3 / f"portfolio_version_returns_{GGG1}.csv",
        "phase2_best": L3 / f"portfolio_version_returns_{PHASE2_BEST}.csv",
        "phase3_best": L3 / f"portfolio_version_returns_{PHASE3_BEST}.csv",
        "phase4_best": L3 / f"portfolio_version_returns_{PHASE4_BEST}.csv",
        "prod_pin": L3 / f"portfolio_version_returns_{PRODUCTION_PIN}.csv",
        "official_shadow": L3 / f"portfolio_version_returns_{OFFICIAL_SHADOW}.csv",
        "equal_weight_etf": L3 / "portfolio_returns_equal_weight.csv",
    }
    for name, path in baseline_files.items():
        if path.exists():
            return_series[name] = load_return_artifact(path)
    if (L2A / "strategy_returns_baseline_60_40_proxy.csv").exists():
        return_series["bench_60_40"] = load_strategy_return(L2A / "strategy_returns_baseline_60_40_proxy.csv")
    return_series["SPY"] = spy_ret
    return_series["QQQ"] = qqq_ret
    return_series["EqualWeightSectorSleeve"] = returns[eligible_sectors].mean(axis=1)

    exposure_cache: dict[tuple[str, str | None, str | None], dict] = {}

    def exposure_row(portfolio: str, start: str | None, end: str | None, exact_index: pd.Index | None = None) -> dict:
        key = (portfolio, start or "none", end or "none") if exact_index is None else None
        if key is not None and key in exposure_cache:
            return dict(exposure_cache[key])
        artifact = artifact_name(portfolio)
        out = {
            "avg_BIL": np.nan,
            "avg_SPY": np.nan,
            "avg_QQQ": np.nan,
            "avg_sector_sleeve_exposure": np.nan,
            "avg_offense_exposure": np.nan,
            "avg_defense_exposure": np.nan,
            "avg_cash_exposure": np.nan,
        }
        weights_path = L3 / f"portfolio_version_weights_{artifact}.csv"
        sleeve_path = L3 / f"portfolio_version_sleeve_weights_{artifact}.csv"
        if weights_path.exists():
            w = pd.read_csv(weights_path, index_col=0, parse_dates=True)
            w.index = pd.to_datetime(w.index).tz_localize(None)
            w = w.reindex(exact_index) if exact_index is not None else ws(w, start, end)
            out["avg_BIL"] = float(w[CASH].mean()) if CASH in w.columns else np.nan
            out["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else np.nan
            out["avg_QQQ"] = float(w["QQQ"].mean()) if "QQQ" in w.columns else np.nan
        if sleeve_path.exists():
            sw = pd.read_csv(sleeve_path, index_col=0, parse_dates=True)
            sw.index = pd.to_datetime(sw.index).tz_localize(None)
            sw = sw.reindex(exact_index) if exact_index is not None else ws(sw, start, end)
            sector_cols = [c for c in sw.columns if c.startswith("phase4b_") or c.startswith("phase4_")]
            offense_cols = [
                c
                for c in [
                    "dual_momentum_topn",
                    "cta_trend_long_only",
                    "composite_selective_signals",
                    "composite_regime_offense_component",
                    *sector_cols,
                ]
                if c in sw.columns
            ]
            defense_cols = [c for c in ["composite_regime_defense_component", "taa_10m_sma"] if c in sw.columns]
            out["avg_sector_sleeve_exposure"] = float(sw[sector_cols].sum(axis=1).mean()) if sector_cols else 0.0
            out["avg_offense_exposure"] = float(sw[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan
            out["avg_defense_exposure"] = float(sw[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan
            out["avg_cash_exposure"] = float(sw["cash::BIL"].mean()) if "cash::BIL" in sw.columns else np.nan
        if key is not None:
            exposure_cache[key] = dict(out)
        return out

    ggg_turn = np.nan
    ggg_df_path = L3 / f"portfolio_version_returns_{GGG1}.csv"
    if ggg_df_path.exists():
        ggg_df = pd.read_csv(ggg_df_path, index_col=0, parse_dates=True)
        ggg_turn = float(ggg_df["turnover"].mean()) if "turnover" in ggg_df.columns else np.nan

    metric_rows = []
    for pname, ret in return_series.items():
        for wname, (start, end) in WINDOWS.items():
            ret_slc = ws(ret, start, end)
            row = {"portfolio": pname, "window": wname, **calc_metrics(ret_slc, pname)}
            ret_artifact = L3 / f"portfolio_version_returns_{artifact_name(pname)}.csv"
            avg_turn = np.nan
            if ret_artifact.exists():
                rdf = pd.read_csv(ret_artifact, index_col=0, parse_dates=True)
                rdf.index = pd.to_datetime(rdf.index).tz_localize(None)
                if "turnover" in rdf.columns:
                    avg_turn = float(ws(rdf["turnover"], start, end).mean())
            row["avg_turnover"] = avg_turn
            row["turnover_ratio_vs_production"] = avg_turn / ggg_turn if pd.notna(avg_turn) and pd.notna(ggg_turn) and ggg_turn > 0 else np.nan
            row.update(exposure_row(pname, start, end))
            for bm_name in ["SPY", "QQQ", "ggg1", "phase2_best", "phase3_best", "phase4_best"]:
                bm_series = return_series.get(bm_name)
                if bm_series is None:
                    continue
                row[f"active_return_vs_{bm_name}"] = active_ann_return(ret_slc, ws(bm_series, start, end))
            up, down, beta_spy, corr_spy = capture(ret_slc, ws(return_series["SPY"], start, end))
            _, _, beta_qqq, corr_qqq = capture(ret_slc, ws(return_series["QQQ"], start, end))
            row.update(
                {
                    "upside_capture_spy": up,
                    "downside_capture_spy": down,
                    "beta_spy": beta_spy,
                    "corr_spy": corr_spy,
                    "beta_qqq": beta_qqq,
                    "corr_qqq": corr_qqq,
                }
            )
            metric_rows.append(row)

    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(OUT / "phase4b_candidate_metrics_full.csv", index=False)
    metrics_df[metrics_df["window"] != "full"].to_csv(OUT / "phase4b_candidate_holdout_metrics.csv", index=False)
    focus = CANDIDATES + [
        "ggg1",
        "phase2_best",
        "phase3_best",
        "phase4_best",
        "prod_pin",
        "official_shadow",
        "SPY",
        "QQQ",
        "bench_60_40",
        "equal_weight_etf",
        "EqualWeightSectorSleeve",
    ]
    metrics_df[metrics_df["portfolio"].isin(focus)].to_csv(OUT / "phase4b_candidate_vs_benchmark_table.csv", index=False)
    cap_cols = [
        c
        for c in [
            "portfolio",
            "window",
            "upside_capture_spy",
            "downside_capture_spy",
            "beta_spy",
            "corr_spy",
            "beta_qqq",
            "corr_qqq",
            "active_return_vs_SPY",
            "active_return_vs_QQQ",
            "active_return_vs_ggg1",
            "active_return_vs_phase2_best",
            "active_return_vs_phase3_best",
            "active_return_vs_phase4_best",
        ]
        if c in metrics_df.columns
    ]
    metrics_df[cap_cols].to_csv(OUT / "phase4b_capture_beta_by_window.csv", index=False)

    # ------------------------------------------------------------------
    # PART H - state-by-state diagnosis.
    # ------------------------------------------------------------------
    print("\n=== PART H: state diagnostics ===")
    state_summary_rows = []
    state_exposure_rows = []
    state_ports = (CANDIDATES if not build_skipped else []) + ["ggg1", "phase2_best", "phase3_best", "phase4_best"]
    for pname in state_ports:
        if pname not in return_series:
            continue
        ret = return_series[pname]
        for st in sorted(state.dropna().unique()):
            idx = state[state == st].index
            row = {"portfolio": pname, "state": st, **calc_metrics(ret.reindex(idx), pname)}
            row.update(exposure_row(pname, None, None, exact_index=idx))
            state_summary_rows.append(row)
            sleeve_path = L3 / f"portfolio_version_sleeve_weights_{artifact_name(pname)}.csv"
            if sleeve_path.exists():
                sw = pd.read_csv(sleeve_path, index_col=0, parse_dates=True)
                sw.index = pd.to_datetime(sw.index).tz_localize(None)
                swst = sw.reindex(idx)
                exp_row = {"portfolio": pname, "state": st}
                for col in swst.columns:
                    exp_row[col] = float(swst[col].mean())
                state_exposure_rows.append(exp_row)

    state_summary_df = pd.DataFrame(state_summary_rows)
    state_summary_df.to_csv(OUT / "phase4b_state_summary.csv", index=False)
    pd.DataFrame(state_exposure_rows).to_csv(OUT / "phase4b_state_exposure_summary.csv", index=False)

    for baseline in ["ggg1", "phase2_best", "phase3_best", "phase4_best"]:
        bdf = state_summary_df[state_summary_df["portfolio"] == baseline].set_index("state")
        rows = []
        for _, row in state_summary_df[state_summary_df["portfolio"].isin(CANDIDATES)].iterrows():
            st = row["state"]
            if st not in bdf.index:
                continue
            rows.append(
                {
                    "portfolio": row["portfolio"],
                    "state": st,
                    f"delta_ann_return_vs_{baseline}": row["ann_return"] - bdf.at[st, "ann_return"],
                    f"delta_sharpe_vs_{baseline}": row["sharpe"] - bdf.at[st, "sharpe"],
                    f"delta_avg_BIL_vs_{baseline}": row["avg_BIL"] - bdf.at[st, "avg_BIL"],
                    f"delta_sector_exposure_vs_{baseline}": row["avg_sector_sleeve_exposure"] - bdf.at[st, "avg_sector_sleeve_exposure"],
                }
            )
        out_name = {
            "ggg1": "phase4b_state_deltas_vs_ggg1.csv",
            "phase2_best": "phase4b_state_deltas_vs_phase2_best.csv",
            "phase3_best": "phase4b_state_deltas_vs_phase3_best.csv",
            "phase4_best": "phase4b_state_deltas_vs_phase4_best.csv",
        }[baseline]
        pd.DataFrame(rows).to_csv(OUT / out_name, index=False)

    def write_state_diag(st: str, fname: str) -> None:
        state_summary_df[state_summary_df["state"] == st].to_csv(OUT / fname, index=False)

    write_state_diag("calm_trend", "phase4b_calm_sector_offense_diagnostics.csv")
    write_state_diag("neutral_mixed", "phase4b_neutral_sector_offense_diagnostics.csv")
    write_state_diag("recovery_confirmed", "phase4b_recovery_participation_diagnostics.csv")
    write_state_diag("stressed_panic", "phase4b_stress_protection_diagnostics.csv")

    # ------------------------------------------------------------------
    # PART I/J - risk checks and selection.
    # ------------------------------------------------------------------
    print("\n=== PART I/J: risk checks and selection ===")
    risk_rows = []
    hidden_rows = []
    bear_rows = []
    concentration_rows = []
    sig_active_rows = []
    fail_rows = []
    selection_rows = []

    ggg_full = calc_metrics(return_series.get("ggg1", pd.Series(dtype=float)))
    p2_full = calc_metrics(return_series.get("phase2_best", pd.Series(dtype=float)))
    p3_full = calc_metrics(return_series.get("phase3_best", pd.Series(dtype=float)))
    p4_full = calc_metrics(return_series.get("phase4_best", pd.Series(dtype=float)))
    ggg_bear = calc_metrics(ws(return_series.get("ggg1", pd.Series(dtype=float)), "2022-01-01", "2022-12-31"))
    p4_bear = calc_metrics(ws(return_series.get("phase4_best", pd.Series(dtype=float)), "2022-01-01", "2022-12-31"))
    sixty_full = calc_metrics(return_series.get("bench_60_40", pd.Series(dtype=float)))
    spy_full = calc_metrics(return_series["SPY"])
    active_idx = signal_panel[signal_panel["high_quality_sector_bull"].astype(bool) | signal_panel["sector_quality_score_high"].astype(bool)].index
    inactive_idx = signal_panel[~(signal_panel["high_quality_sector_bull"].astype(bool) | signal_panel["sector_quality_score_high"].astype(bool))].index

    if build_skipped:
        for c in CANDIDATES:
            fail_rows.append({"portfolio": c, "reason": "not_built_refined_sleeve_validation_failed"})

    for pname in CANDIDATES:
        if pname not in return_series:
            continue
        ret = return_series[pname]
        m_full = calc_metrics(ret, pname)
        m_2020 = calc_metrics(ws(ret, "2020-01-01", None), pname)
        m_2021 = calc_metrics(ws(ret, "2021-01-01", None), pname)
        m_bear = calc_metrics(ws(ret, "2022-01-01", "2022-12-31"), pname)
        beta_spy, corr_spy = beta_corr(ret, return_series["SPY"])
        beta_qqq, corr_qqq = beta_corr(ret, return_series["QQQ"])
        ggg_beta_spy, _ = beta_corr(return_series["ggg1"], return_series["SPY"])
        ann_improve = m_full["ann_return"] - ggg_full["ann_return"]
        beta_attr = (beta_spy - ggg_beta_spy) * spy_full["ann_return"] if pd.notna(beta_spy) and pd.notna(ggg_beta_spy) else np.nan
        pct_from_beta = abs(beta_attr) / abs(ann_improve) if abs(ann_improve) > 1e-8 and pd.notna(beta_attr) else np.nan
        exp_full = exposure_row(pname, None, None)
        exp_ggg = exposure_row("ggg1", None, None)
        bear_ok = (m_bear["ann_return"] >= ggg_bear["ann_return"] - 0.04) and (m_bear["ann_return"] >= p4_bear["ann_return"] - 0.025)
        maxdd_ok = m_full["max_drawdown"] >= -0.22
        sharpe_ok = m_full["sharpe"] >= 0.90
        disguised = bool(
            (pd.notna(beta_spy) and beta_spy > 0.35)
            or (pd.notna(beta_qqq) and beta_qqq > 0.25)
            or (pd.notna(corr_spy) and corr_spy > 0.55)
            or (pd.notna(corr_qqq) and corr_qqq > 0.60)
        )
        cvar_bad = m_full["cvar_5"] < ggg_full["cvar_5"] - 0.008
        better_60_40 = m_full["sharpe"] > sixty_full.get("sharpe", -np.inf)
        holdout_credible = (
            m_2020["ann_return"] > calc_metrics(ws(return_series["ggg1"], "2020-01-01", None))["ann_return"]
            or m_2021["ann_return"] > calc_metrics(ws(return_series["ggg1"], "2021-01-01", None))["ann_return"]
            or m_2020["ann_return"] > p4_full["ann_return"]
        )
        on_ret = ret.reindex(active_idx)
        off_ret = ret.reindex(inactive_idx)
        sig_active_delta_ggg = ann_return(on_ret) - ann_return(return_series["ggg1"].reindex(active_idx))
        sig_active_delta_p4 = ann_return(on_ret) - ann_return(return_series["phase4_best"].reindex(active_idx))

        risk_rows.append(
            {
                "portfolio": pname,
                "full_ann_return": m_full["ann_return"],
                "full_sharpe": m_full["sharpe"],
                "full_max_drawdown": m_full["max_drawdown"],
                "full_cvar_5": m_full["cvar_5"],
                "holdout_2020_return": m_2020["ann_return"],
                "holdout_2020_sharpe": m_2020["sharpe"],
                "avg_BIL": exp_full["avg_BIL"],
                "avg_sector_sleeve_exposure": exp_full["avg_sector_sleeve_exposure"],
                "maxdd_ok": maxdd_ok,
                "sharpe_ok": sharpe_ok,
                "bear_ok": bear_ok,
                "cvar_bad": cvar_bad,
                "better_than_60_40_sharpe": better_60_40,
                "disguised_spy_qqq": disguised,
                "improves_over_phase4_best_return": m_full["ann_return"] > p4_full["ann_return"],
                "improves_over_phase4_best_sharpe": m_full["sharpe"] > p4_full["sharpe"],
                "sector_active_delta_vs_phase4_best": sig_active_delta_p4,
            }
        )
        hidden_rows.append(
            {
                "portfolio": pname,
                "beta_spy": beta_spy,
                "corr_spy": corr_spy,
                "beta_qqq": beta_qqq,
                "corr_qqq": corr_qqq,
                "ann_improvement_vs_ggg1": ann_improve,
                "ann_improvement_vs_phase4_best": m_full["ann_return"] - p4_full["ann_return"],
                "beta_attribution_estimate": beta_attr,
                "pct_improvement_from_beta": pct_from_beta,
                "hidden_beta_risk": "HIGH" if disguised or (pd.notna(pct_from_beta) and pct_from_beta > 0.75) else "LOW",
                "avg_BIL": exp_full["avg_BIL"],
                "bil_reduction_vs_ggg1": exp_full["avg_BIL"] - exp_ggg["avg_BIL"],
            }
        )
        bear_rows.append(
            {
                "portfolio": pname,
                "bear_2022_return": m_bear["ann_return"],
                "ggg1_bear_2022_return": ggg_bear["ann_return"],
                "phase4_best_bear_2022_return": p4_bear["ann_return"],
                "delta_vs_ggg1": m_bear["ann_return"] - ggg_bear["ann_return"],
                "delta_vs_phase4_best": m_bear["ann_return"] - p4_bear["ann_return"],
                "bear_ok": bear_ok,
            }
        )
        wpath = L3 / f"portfolio_version_weights_{artifact_name(pname)}.csv"
        if wpath.exists():
            w = pd.read_csv(wpath, index_col=0, parse_dates=True)
            w.index = pd.to_datetime(w.index).tz_localize(None)
            sec_w = w[[c for c in eligible_sectors if c in w.columns]]
            concentration_rows.append(
                {
                    "portfolio": pname,
                    "avg_total_sector_etf_weight": float(sec_w.sum(axis=1).mean()),
                    "avg_max_single_sector_etf_weight": float(sec_w.max(axis=1).mean()),
                    "max_single_sector_etf_weight": float(sec_w.max(axis=1).max()),
                    "avg_top3_sector_etf_weight": float(sec_w.apply(lambda row: row.sort_values(ascending=False).head(3).sum(), axis=1).mean()),
                    "active_sector_weeks": int((sec_w.sum(axis=1) > 0.01).sum()),
                }
            )

        sig_active_rows.append(
            {
                "portfolio": pname,
                "signal": "high_quality_or_score_high",
                "active_weeks": int(on_ret.dropna().shape[0]),
                "signal_active_ann_return": ann_return(on_ret),
                "signal_inactive_ann_return": ann_return(off_ret),
                "signal_active_delta_vs_ggg1": sig_active_delta_ggg,
                "signal_active_delta_vs_phase4_best": sig_active_delta_p4,
            }
        )

        reasons = []
        if not maxdd_ok:
            reasons.append("max_drawdown_worse_than_22pct")
        if not sharpe_ok:
            reasons.append("sharpe_below_0.90")
        if not bear_ok:
            reasons.append("2022_or_phase4_stress_protection_worse")
        if disguised:
            reasons.append("hidden_spy_qqq_beta_or_correlation")
        if cvar_bad:
            reasons.append("cvar_materially_worse_than_ggg1")
        if m_full["ann_return"] <= p4_full["ann_return"] + 0.0005 and m_full["sharpe"] <= p4_full["sharpe"] + 0.005:
            reasons.append("not_clearly_better_than_phase4_best")
        if not holdout_credible:
            reasons.append("holdout_not_credible")
        if reasons:
            fail_rows.append({"portfolio": pname, "reason": "|".join(reasons)})

        beats_ggg = m_full["ann_return"] > ggg_full["ann_return"] + 0.001
        beats_p2 = m_full["ann_return"] > p2_full["ann_return"] or m_full["sharpe"] > p2_full["sharpe"]
        beats_p3 = m_full["ann_return"] > p3_full["ann_return"] or m_full["sharpe"] > p3_full["sharpe"]
        beats_p4 = m_full["ann_return"] > p4_full["ann_return"] + 0.0005 or m_full["sharpe"] > p4_full["sharpe"] + 0.015
        sector_active_good = sig_active_delta_ggg > 0 and sig_active_delta_p4 > -0.002

        if not maxdd_ok or not sharpe_ok or not bear_ok or disguised:
            classification = "REJECT"
            reason = "failed hard Phase 4B risk/realism guardrail"
        elif (
            refined_sleeve_validation_positive
            and beats_ggg
            and beats_p2
            and beats_p3
            and beats_p4
            and holdout_credible
            and sector_active_good
            and better_60_40
            and m_full["sharpe"] >= 0.95
            and m_full["max_drawdown"] >= -0.20
            and m_full["ann_return"] >= 0.085
        ):
            classification = "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
            reason = "passes Phase 4B return/risk/holdout/sector-active gates"
        elif (
            refined_sleeve_validation_positive
            and beats_ggg
            and beats_p4
            and (beats_p2 or beats_p3 or holdout_credible)
            and sector_active_good
            and better_60_40
        ):
            classification = "KEEP_AS_AGGRESSIVE_SHADOW"
            reason = "credible refinement over Phase 4 best but not production-challenger strength"
        elif refined_sleeve_validation_positive and (beats_ggg or sector_active_good or holdout_credible):
            classification = "KEEP_AS_RESEARCH_ONLY"
            reason = "partial refined-sector evidence but weak aggregate improvement"
        else:
            classification = "REJECT"
            reason = "refined sector rotation did not improve Phase 4 best enough"
        selection_rows.append(
            {
                "portfolio": pname,
                "classification": classification,
                "reason": reason,
                "full_ann_return": m_full["ann_return"],
                "full_sharpe": m_full["sharpe"],
                "full_max_drawdown": m_full["max_drawdown"],
                "holdout_2020_return": m_2020["ann_return"],
                "holdout_2020_sharpe": m_2020["sharpe"],
                "holdout_2021_return": m_2021["ann_return"],
                "holdout_2021_sharpe": m_2021["sharpe"],
                "bear_2022_return": m_bear["ann_return"],
                "beats_ggg1": beats_ggg,
                "beats_phase2_best": beats_p2,
                "beats_phase3_best": beats_p3,
                "beats_phase4_best": beats_p4,
                "sector_active_good": sector_active_good,
                "refined_sleeve_validation_positive": refined_sleeve_validation_positive,
            }
        )

    pd.DataFrame(risk_rows).to_csv(OUT / "phase4b_risk_realism_checks.csv", index=False)
    pd.DataFrame(hidden_rows).to_csv(OUT / "phase4b_hidden_beta_cash_checks.csv", index=False)
    pd.DataFrame(bear_rows).to_csv(OUT / "phase4b_2022_bear_check.csv", index=False)
    pd.DataFrame(concentration_rows).to_csv(OUT / "phase4b_sector_concentration_checks.csv", index=False)
    pd.DataFrame(sig_active_rows).to_csv(OUT / "phase4b_signal_active_candidate_performance.csv", index=False)
    pd.DataFrame(fail_rows if fail_rows else [{"portfolio": "none", "reason": "no_failure_flags"}]).to_csv(
        OUT / "phase4b_candidate_failure_reasons.csv", index=False
    )
    selection_df = pd.DataFrame(selection_rows)
    if selection_df.empty:
        selection_df = pd.DataFrame(
            [
                {
                    "portfolio": c,
                    "classification": "REJECT",
                    "reason": "not_built_refined_sleeve_validation_failed",
                    "full_ann_return": np.nan,
                    "full_sharpe": np.nan,
                    "full_max_drawdown": np.nan,
                    "beats_phase4_best": False,
                    "sector_active_good": False,
                    "refined_sleeve_validation_positive": refined_sleeve_validation_positive,
                }
                for c in CANDIDATES
            ]
        )
    selection_df.to_csv(OUT / "phase4b_selection_table.csv", index=False)

    # ------------------------------------------------------------------
    # PART K/L - audits and next decision.
    # ------------------------------------------------------------------
    print("\n=== PART K/L: audits and next decision ===")
    qual = selection_df[selection_df["classification"].isin(["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT", "KEEP_AS_AGGRESSIVE_SHADOW"])]
    best_candidate = None
    if not qual.empty:
        rank = {"PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT": 0, "KEEP_AS_AGGRESSIVE_SHADOW": 1}
        qual = qual.assign(class_rank=qual["classification"].map(rank))
        best_candidate = qual.sort_values(["class_rank", "full_ann_return", "full_sharpe"], ascending=[True, False, False]).iloc[0]["portfolio"]

    audit_rows = []
    audit_summary_lines = ["# Phase 4B Audit Summary\n\n"]
    if best_candidate:
        best_class = selection_df.set_index("portfolio").at[best_candidate, "classification"]
        is_challenger = best_class == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
        audit_specs = [
            ("research_committee_report.py", ["--quick"] if not is_challenger else []),
            ("backtest_realism_audit.py", ["--quick"] if not is_challenger else []),
            ("allocator_benchmark_audit.py", ["--quick"] if not is_challenger else []),
        ]
        if is_challenger:
            audit_specs.append(("robustness_simulation_audit.py", []))
        for script_name, flags in audit_specs:
            script_path = ROOT / "scripts" / script_name
            audit_name = script_name.replace(".py", "")
            if not script_path.exists():
                audit_rows.append({"audit": audit_name, "candidate": best_candidate, "status": "SKIPPED_NOT_FOUND"})
                audit_summary_lines.append(f"## {audit_name}: SKIPPED_NOT_FOUND\n\n")
                continue
            res = subprocess.run(
                [sys.executable, str(script_path), best_candidate, *flags],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=420,
            )
            status = "PASS" if res.returncode == 0 else "FAIL"
            log_name = f"phase4b_{audit_name}_{'quick' if flags else 'full'}.log"
            with open(OUT / log_name, "w") as f:
                f.write("STDOUT\n")
                f.write(res.stdout[-6000:])
                f.write("\nSTDERR\n")
                f.write(res.stderr[-3000:])
            audit_rows.append({"audit": audit_name, "candidate": best_candidate, "status": status, "log": log_name})
            audit_summary_lines.append(f"## {audit_name}: {status}\nLog: `{log_name}`\n\n")
    else:
        audit_summary_lines.append("No candidate qualified as KEEP_AS_AGGRESSIVE_SHADOW or better; audits skipped.\n")
    pd.DataFrame(audit_rows if audit_rows else [{"audit": "none", "candidate": "none", "status": "SKIPPED_NO_QUALIFIER"}]).to_csv(
        OUT / "phase4b_audit_results.csv", index=False
    )
    (OUT / "phase4b_audit_summary.md").write_text("".join(audit_summary_lines))

    n_challenger = int((selection_df["classification"] == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT").sum())
    n_shadow = int((selection_df["classification"] == "KEEP_AS_AGGRESSIVE_SHADOW").sum())
    any_bad_substitute = bool(
        (not pd.DataFrame(risk_rows).empty)
        and (pd.DataFrame(risk_rows).get("disguised_spy_qqq", pd.Series(dtype=bool)).astype(bool).any())
        and (selection_df["classification"] == "REJECT").all()
    )
    if n_challenger:
        decision = "PROMOTE_PHASE4B_TO_PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        rationale = f"{best_candidate} met Phase 4B challenger gates."
    elif n_shadow:
        decision = "KEEP_PHASE4B_AS_AGGRESSIVE_SHADOW"
        rationale = f"{best_candidate} is a credible refinement over Phase 4 best but not production-ready."
    elif any_bad_substitute:
        decision = "STOP_AGGRESSIVE_BRANCH_PACKAGE_GGG1_AND_SHADOWS"
        rationale = "Refined sector rotation behaved like an inferior SPY/QQQ/60-40 substitute."
    else:
        decision = "PROCEED_TO_PHASE5_TRUE_STOCK_BREADTH_DATA_UPGRADE"
        rationale = "Existing ETF sector breadth/rotation still cannot move the return target close enough; the missing input appears to be true stock breadth rather than another sector-ETF tweak."

    next_action_df = pd.DataFrame(
        [
            {
                "recommendation": decision,
                "best_candidate": best_candidate or "none",
                "rationale": rationale,
                "n_challenger": n_challenger,
                "n_shadow": n_shadow,
                "refined_sleeve_validation_positive": refined_sleeve_validation_positive,
            }
        ]
    )
    next_action_df.to_csv(OUT / "phase4b_next_action_recommendation.csv", index=False)
    next_action_df.rename(columns={"recommendation": "decision"}).to_csv(OUT / "phase4b_next_phase_decision.csv", index=False)

    with open(OUT / "phase4b_protocol.json", "w") as f:
        json.dump(
            {
                "phase": "phase_4b_refined_sector_rotation",
                "date": "2026-05-07",
                "production_pin": PRODUCTION_PIN,
                "official_shadow_pin": OFFICIAL_SHADOW,
                "base_candidate": GGG1,
                "phase2_best": PHASE2_BEST,
                "phase3_best": PHASE3_BEST,
                "phase4_best": PHASE4_BEST,
                "candidates": CANDIDATES,
                "best_candidate": best_candidate or "none",
                "decision": decision,
                "refined_sleeve_validation_positive": refined_sleeve_validation_positive,
                "build_skipped": build_skipped,
                "no_pin_changes": True,
                "no_new_data_downloaded": True,
            },
            f,
            indent=2,
        )

    # ------------------------------------------------------------------
    # PART M - report.
    # ------------------------------------------------------------------
    print("\n=== PART M: report ===")
    full_focus = metrics_df[
        (metrics_df["window"] == "full")
        & (metrics_df["portfolio"].isin(CANDIDATES + ["ggg1", "phase2_best", "phase3_best", "phase4_best", "prod_pin", "official_shadow", "SPY", "QQQ", "bench_60_40", "EqualWeightSectorSleeve"]))
    ]
    report_cols = [
        c
        for c in [
            "portfolio",
            "ann_return",
            "ann_vol",
            "sharpe",
            "max_drawdown",
            "cvar_5",
            "avg_BIL",
            "avg_sector_sleeve_exposure",
            "beta_spy",
            "corr_spy",
            "active_return_vs_phase4_best",
        ]
        if c in full_focus.columns
    ]
    hold_focus = metrics_df[
        (metrics_df["window"].isin(["holdout_2020", "holdout_2021", "bear_2022", "recovery_2023"]))
        & (metrics_df["portfolio"].isin(CANDIDATES + ["ggg1", "phase2_best", "phase3_best", "phase4_best", "SPY", "QQQ"]))
    ]
    hold_cols = [c for c in ["portfolio", "window", "ann_return", "sharpe", "max_drawdown", "avg_BIL", "avg_sector_sleeve_exposure"] if c in hold_focus.columns]
    state_key = state_summary_df[state_summary_df["portfolio"].isin(CANDIDATES + ["ggg1", "phase2_best", "phase3_best", "phase4_best"])][
        [c for c in ["portfolio", "state", "ann_return", "sharpe", "max_drawdown", "avg_BIL", "avg_sector_sleeve_exposure", "avg_offense_exposure", "avg_defense_exposure"] if c in state_summary_df.columns]
    ]
    risk_df = pd.DataFrame(risk_rows)
    hidden_df = pd.DataFrame(hidden_rows)
    bear_df = pd.DataFrame(bear_rows)
    concentration_df = pd.DataFrame(concentration_rows)
    sig_active_df = pd.DataFrame(sig_active_rows)
    audit_df = pd.DataFrame(audit_rows if audit_rows else [{"audit": "none", "candidate": "none", "status": "SKIPPED_NO_QUALIFIER"}])

    next_phase_prompt = """Phase 5 true stock breadth data upgrade prompt outline:
1. Do not change production, official shadow, or GGG1 pins.
2. Add or source causal stock-level breadth only through an explicit data-hub update with provenance and survivorship-bias controls.
3. Keep stressed_panic protection unchanged and use lagged/time-ordered validation only.
4. Test whether true stock breadth improves bull/neutral/recovery offense timing beyond ETF sector breadth.
5. Compare against GGG1, Phase 2, Phase 3, Phase 4, Phase 4B, SPY, QQQ, and 60/40 across full and holdout windows.
6. Reject if gains are hidden SPY/QQQ beta, weak holdout, or broken 2022/stressed protection."""

    report_text = f"""# Phase 4B - Refined Sector Rotation / Breadth Timing Audit

**Date:** 2026-05-07
**Type:** Focused strategy research. No production pins changed. No auto-promotion.
**Production pin:** `{PRODUCTION_PIN}`
**Official shadow pin:** `{OFFICIAL_SHADOW}`
**Base:** `{GGG1}`
**Phase 4 best:** `{PHASE4_BEST}`

## Commands Executed

```
{chr(10).join(COMMANDS_EXECUTED)}
BUILD_VERSION_NAMES='{','.join(CANDIDATES)}' python3 scripts/build_improvement_artifacts.py
```

## Files Created / Modified

**Script created:** `scripts/phase_4b_refined_sector_rotation.py`

**Build script modified:** `scripts/build_improvement_artifacts.py` added Phase 4B signal lookup, sleeve registration, five state tilts, and five filtered candidate specs.

**Output directory:** `{OUT}`

**Report created:** `docs/research/2026-05-07_phase_4b_refined_sector_rotation_report.md`

## Phase 4 Diagnosis

{md_table(pd.DataFrame(diagnosis_rows)[['question','diagnosis']], 12)}

## Refined Sector Signal Definitions

{md_table(pd.DataFrame(signal_defs)[['signal','formula','active_weeks','active_frequency','expected_use']], 10)}

## Refined Signal Coverage

{md_table(coverage_df, 10)}

## Refined Sector Sleeve Designs

{md_table(pd.DataFrame(sleeve_designs)[['sleeve','weighting_method','selection_rule','reason_to_fix_phase4_weakness']], 10)}

## Standalone Refined Sector Sleeve Validation

Refined sleeve validation positive: **{refined_sleeve_validation_positive}**.

{md_table(sleeve_val_df[['sleeve','ann_return','ann_vol','sharpe','max_drawdown','calmar','cvar_5','avg_turnover','beta_spy','beta_qqq']].sort_values('ann_return', ascending=False), 12)}

## Signal-Active Validation

{md_table(active_val_df[active_val_df['state'].eq('all')][['sleeve','signal','active_weeks','active_ann_return','inactive_ann_return','active_minus_inactive_ann_return','active_vs_ggg1','active_vs_phase4_20pct','adverse_event_frequency']].sort_values('active_vs_phase4_20pct', ascending=False), 18)}

## Candidate Logic

{md_table(pd.DataFrame(candidate_designs), 8)}

## Full-Period Metrics

{md_table(full_focus[report_cols].sort_values('ann_return', ascending=False), 18)}

## Holdout And Recent Metrics

{md_table(hold_focus[hold_cols].sort_values(['window','ann_return'], ascending=[True, False]), 36)}

## State-By-State Impact

{md_table(state_key.sort_values(['state','portfolio']), 42)}

## Risk / Realism Checks

{md_table(risk_df, 12)}

## Hidden Beta / Cash Checks

{md_table(hidden_df, 12)}

## 2022 Bear Protection

{md_table(bear_df, 12)}

## Sector Concentration / Turnover

{md_table(concentration_df, 12)}

## Sector-Active Candidate Windows

{md_table(sig_active_df, 12)}

## Selection Table

{md_table(selection_df, 12)}

## Audit Results

{md_table(audit_df, 8)}

## Final Recommendation

**Recommendation:** `{decision}`

**Best candidate:** `{best_candidate or 'none'}`

**Rationale:** {rationale}

## Next Phase Prompt Outline

```
{next_phase_prompt}
```

## Resume / Project Story Summary

Phase 4B tested whether the dedicated sector sleeve from Phase 4 could be made more useful through narrower activation, smoother ranking, defensive-leadership blocking, and strict high-quality timing. The experiment used only existing ETF data, causal week-t signals, time-ordered validation, and the standard Layer 3 cost/build pipeline. Phase 4B state tilts strip target sector-sleeve weight outside their gates; small residual sector exposure can persist from the monthly/smoothed allocator, so stressed_panic, recovery_fragile, and 2022 protection were audited explicitly instead of assumed. The final recommendation above should guide the next research step; production, official shadow, and GGG1 pins remain unchanged.
"""
    REPORT.write_text(report_text)

    print(f"Decision: {decision}")
    print(f"Best candidate: {best_candidate or 'none'}")
    print(f"Report: {REPORT}")
    print("Done. No production pins changed.")


if __name__ == "__main__":
    main()
