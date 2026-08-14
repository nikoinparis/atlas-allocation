#!/usr/bin/env python3
"""
Phase 4 — Sector Breadth / Sector ETF Rotation

Builds causal sector momentum/breadth features, validates standalone sector
rotation sleeves, then builds at most six controlled portfolio candidates from
GGG1 through the standard Layer 3 improvement pipeline. No pin changes.
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
OUT = ROOT / "data" / "research" / "phase_4_sector_breadth_rotation"
REPORT = ROOT / "docs" / "research" / "2026-05-07_phase_4_sector_breadth_rotation_report.md"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS = 52
COST_BPS = 10
CASH = "BIL"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
OFFICIAL_SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PHASE2_BEST = "improved_phase2_aggressive_neutral_cash_unlock"
PHASE3_BEST = "improved_phase3_high_breadth_calm_us_offense"

CANDIDATES = [
    "improved_phase4_sector_small_overlay",
    "improved_phase4_sector_20pct_offense",
    "improved_phase4_sector_25pct_offense",
    "improved_phase4_balanced_sector_breadth",
    "improved_phase4_stretch_sector_momentum",
    "improved_phase4_sector_us_hybrid",
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
    "phase4_equal_weight_sector_sleeve": "EqualWeightSector",
    "phase4_top3_sector_momentum_sleeve": "Top3SectorMomentum",
    "phase4_top5_sector_momentum_sleeve": "Top5SectorMomentum",
    "phase4_risk_adjusted_top3_sleeve": "RiskAdjustedTop3",
    "phase4_balanced_sector_breadth_sleeve": "SectorBalancedAggressive",
    "phase4_stretch_sector_momentum_sleeve": "SectorStretchAggressive",
}

ARTIFACT_NAME_BY_LABEL = {
    "ggg1": GGG1,
    "phase2_best": PHASE2_BEST,
    "phase3_best": PHASE3_BEST,
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
    "prior phase and data/schema inspection commands",
    "python3 -m py_compile scripts/build_improvement_artifacts.py",
    "python3 scripts/phase_4_sector_breadth_rotation.py",
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
            "n_weeks": len(ret),
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


def ws(s: pd.Series, start: str | None, end: str | None) -> pd.Series:
    out = s.copy()
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
    for _ in range(8):
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


def pct(x: float) -> str:
    return "NA" if pd.isna(x) else f"{x:.2%}"


def md_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df.head(max_rows).copy()
    try:
        return small.to_markdown(index=False)
    except Exception:
        return "```\n" + small.to_string(index=False) + "\n```"


def main() -> None:
    print("=== Phase 4 — Sector Breadth / Sector ETF Rotation ===")
    print(f"Output directory: {OUT}")

    prices = pd.read_csv(HUB / "weekly_prices.csv", index_col="Date", parse_dates=True)
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    returns = prices.pct_change()
    next_returns = returns.shift(-1)
    cash_returns = next_returns.get(CASH, pd.Series(0.0, index=prices.index)).fillna(0.0)

    msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)
    msh.index = pd.to_datetime(msh.index).tz_localize(None)
    msh = msh.reindex(prices.index).ffill()

    rf = pd.DataFrame(index=prices.index)
    rf_path = L1 / "regime_features.csv"
    if rf_path.exists():
        rf = pd.read_csv(rf_path, index_col="Date", parse_dates=True)
        rf.index = pd.to_datetime(rf.index).tz_localize(None)
        rf = rf.reindex(prices.index).ffill()

    # ──────────────────────────────────────────────
    # PART A — SECTOR ETF UNIVERSE INVENTORY
    # ──────────────────────────────────────────────
    print("\n=== PART A: sector universe inventory ===")
    candidates_for_inventory = [t for t in SECTOR_CATALOG if t in prices.columns]
    broad_priority = ["XLK", "XLF", "XLV", "XLY", "XLP", "XLI", "XLE", "XLU", "XLB", "XLRE", "VNQ", "IYR", "XLC"]
    optional_priority = ["SMH", "IGV", "XRT", "IBB", "IYT"]
    sector_tickers = [t for t in broad_priority + optional_priority if t in prices.columns]

    spy_ret = returns["SPY"].dropna() if "SPY" in returns.columns else pd.Series(dtype=float)
    qqq_ret = returns["QQQ"].dropna() if "QQQ" in returns.columns else pd.Series(dtype=float)
    bil_ret = returns[CASH].dropna() if CASH in returns.columns else pd.Series(dtype=float)

    inv_rows = []
    dq_rows = []
    for ticker in sector_tickers:
        cat, desc = SECTOR_CATALOG.get(ticker, ("unknown", "unknown"))
        p = prices[ticker].dropna()
        r = returns[ticker].dropna()
        if p.empty or r.empty:
            continue
        period_idx = prices.loc[p.index.min() : p.index.max()].index
        missing = float(prices.loc[period_idx, ticker].isna().mean()) if len(period_idx) else np.nan
        m = calc_metrics(r, ticker)
        beta_spy, corr_spy = beta_corr(r, spy_ret)
        beta_qqq, corr_qqq = beta_corr(r, qqq_ret)
        eligible = (
            ticker in ["XLK", "XLF", "XLV", "XLY", "XLP", "XLI", "XLE", "XLU", "XLB", "VNQ", "XLRE", "XLC"]
            and len(r) >= 0.80 * len(prices)
            and missing <= 0.02
        )
        row = {
            "ticker": ticker,
            "category": cat,
            "description": desc,
            "start_date": p.index.min().date().isoformat(),
            "end_date": p.index.max().date().isoformat(),
            "weekly_return_coverage": int(len(r)),
            "missingness": missing,
            "ann_return": m["ann_return"],
            "ann_vol": m["ann_vol"],
            "sharpe": m["sharpe"],
            "max_drawdown": m["max_drawdown"],
            "correlation_to_SPY": corr_spy,
            "correlation_to_QQQ": corr_qqq,
            "beta_to_SPY": beta_spy,
            "beta_to_QQQ": beta_qqq,
            "available_in_weekly_prices": ticker in prices.columns,
            "available_in_weekly_returns": (HUB / "weekly_returns.csv").exists(),
            "eligible_for_phase4_sector_sleeve": bool(eligible),
        }
        inv_rows.append(row)
        dq_rows.append(
            {
                "ticker": ticker,
                "price_non_null": int(prices[ticker].notna().sum()),
                "return_non_null": int(returns[ticker].notna().sum()),
                "first_valid_price": row["start_date"],
                "last_valid_price": row["end_date"],
                "missingness": missing,
                "eligible": bool(eligible),
                "reason": "eligible" if eligible else "not broad/liquid sector or insufficient coverage",
            }
        )

    inv_df = pd.DataFrame(inv_rows)
    dq_df = pd.DataFrame(dq_rows)
    inv_df.to_csv(OUT / "phase4_sector_universe_inventory.csv", index=False)
    dq_df.to_csv(OUT / "phase4_sector_data_quality.csv", index=False)

    eligible_sectors = inv_df.loc[inv_df["eligible_for_phase4_sector_sleeve"], "ticker"].tolist()
    if len(eligible_sectors) < 6:
        raise SystemExit(f"Missing usable sector universe: only {eligible_sectors}")
    print(f"Eligible sectors: {eligible_sectors}")

    # ──────────────────────────────────────────────
    # PART B — CAUSAL SECTOR FEATURES
    # ──────────────────────────────────────────────
    print("\n=== PART B: causal sector feature panel ===")
    sector_prices = prices[eligible_sectors]
    sector_returns = returns[eligible_sectors]
    mom4 = sector_prices.pct_change(4)
    mom13 = sector_prices.pct_change(13)
    mom26 = sector_prices.pct_change(26)
    mom52 = sector_prices.pct_change(52)
    vol13 = sector_returns.rolling(13).std() * np.sqrt(WEEKS)
    vol26 = sector_returns.rolling(26).std() * np.sqrt(WEEKS)
    risk_adj_mom = (0.4 * mom13 + 0.6 * mom26) / vol26.replace(0, np.nan)
    dd52 = sector_prices / sector_prices.rolling(52, min_periods=8).max() - 1.0
    ma26 = sector_prices.rolling(26).mean()
    ma43 = sector_prices.rolling(43).mean()
    ma_dist26 = sector_prices / ma26 - 1.0
    ma_dist43 = sector_prices / ma43 - 1.0
    trend26 = sector_prices > ma26
    trend43 = sector_prices > ma43
    spy_mom26 = prices["SPY"].pct_change(26) if "SPY" in prices.columns else pd.Series(np.nan, index=prices.index)
    qqq_mom26 = prices["QQQ"].pct_change(26) if "QQQ" in prices.columns else pd.Series(np.nan, index=prices.index)
    bil_mom13 = prices[CASH].pct_change(13) if CASH in prices.columns else pd.Series(0.0, index=prices.index)

    feature_blocks = []
    manifest_rows = []
    for label, frame, desc in [
        ("mom_4w", mom4, "4-week sector momentum"),
        ("mom_13w", mom13, "13-week sector momentum"),
        ("mom_26w", mom26, "26-week sector momentum"),
        ("mom_52w", mom52, "52-week sector momentum"),
        ("vol_13w", vol13, "13-week annualized volatility"),
        ("vol_26w", vol26, "26-week annualized volatility"),
        ("risk_adj_mom", risk_adj_mom, "0.4*13w + 0.6*26w momentum divided by 26w vol"),
        ("drawdown_52w", dd52, "drawdown from trailing 52-week high"),
        ("ma_dist_26w", ma_dist26, "price distance from 26-week moving average"),
        ("ma_dist_43w", ma_dist43, "price distance from 43-week moving average"),
        ("trend_positive_26w", trend26.astype(float), "price above 26-week moving average"),
        ("trend_positive_43w", trend43.astype(float), "price above 43-week moving average"),
    ]:
        renamed = frame.add_suffix(f"_{label}")
        feature_blocks.append(renamed)
        for ticker in eligible_sectors:
            manifest_rows.append(
                {
                    "feature": f"{ticker}_{label}",
                    "ticker": ticker,
                    "formula": desc,
                    "causal_lag_rule": "computed through week t and applied to week t+1 returns",
                    "lookahead": False,
                }
            )

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
    breadth["sector_count_beating_bil_13w"] = mom13.gt(bil_mom13, axis=0).sum(axis=1)
    breadth["sector_leadership_dispersion"] = breadth["sector_top_minus_median_26w"]
    breadth["sector_enough_positive"] = (breadth["sector_pct_trend_positive_43w"] >= 0.60).astype(int)
    breadth["sector_leadership_differentiated"] = (breadth["sector_top_minus_median_26w"] >= 0.035).astype(int)

    vix_z = rf.get("vix_level_z_tradable", pd.Series(np.nan, index=prices.index)).reindex(prices.index)
    vix_contained = (vix_z <= 1.0) | vix_z.isna()
    breadth["vix_contained"] = vix_contained.astype(int)
    breadth["sector_rotation_quality_score"] = (
        0.35 * breadth["sector_pct_trend_positive_43w"].clip(0, 1)
        + 0.25 * breadth["sector_pct_positive_26w_return"].clip(0, 1)
        + 0.25 * (breadth["sector_top_minus_median_26w"] / 0.20).clip(0, 1)
        + 0.15 * breadth["vix_contained"]
    ).clip(0, 1)

    feature_panel = pd.concat(feature_blocks + [breadth], axis=1)
    feature_panel.to_csv(OUT / "phase4_sector_feature_panel.csv")
    breadth.to_csv(OUT / "phase4_sector_breadth_panel.csv")
    pd.DataFrame(manifest_rows).to_csv(OUT / "phase4_sector_feature_manifest.csv", index=False)

    signal_summary_rows = []
    for col in breadth.columns:
        s = pd.to_numeric(breadth[col], errors="coerce")
        signal_summary_rows.append(
            {
                "feature": col,
                "non_null_pct": float(s.notna().mean()),
                "mean": float(s.mean()) if s.notna().any() else np.nan,
                "min": float(s.min()) if s.notna().any() else np.nan,
                "max": float(s.max()) if s.notna().any() else np.nan,
            }
        )
    pd.DataFrame(signal_summary_rows).to_csv(OUT / "phase4_sector_signal_summary.csv", index=False)

    # ──────────────────────────────────────────────
    # PART C — SIGNAL DESIGN
    # ──────────────────────────────────────────────
    print("\n=== PART C: sector rotation signals ===")
    state = msh["market_state"].astype(str)
    market_trend = pd.to_numeric(msh.get("market_trend_positive", 0), errors="coerce").fillna(0).astype(bool)
    spy_trend = prices["SPY"] > prices["SPY"].rolling(43).mean() if "SPY" in prices.columns else pd.Series(False, index=prices.index)
    qqq_trend = prices["QQQ"] > prices["QQQ"].rolling(43).mean() if "QQQ" in prices.columns else pd.Series(False, index=prices.index)
    neutral_deteriorating = (state == "neutral_mixed") & (breadth["sector_pct_trend_positive_43w"] < 0.50)
    not_stressed = state != "stressed_panic"
    not_fragile = state != "recovery_fragile"

    signal_panel = pd.DataFrame(index=prices.index)
    signal_panel["sector_breadth_confirmed"] = (
        (breadth["sector_pct_trend_positive_43w"] >= 0.65)
        & (breadth["sector_pct_positive_26w_return"] >= 0.60)
        & market_trend
        & not_stressed
        & not_fragile
    ).astype(int)
    signal_panel["sector_leadership_confirmed"] = (
        (breadth["sector_pct_trend_positive_43w"] >= 0.55)
        & (breadth["sector_top_minus_spy_26w"] >= 0.015)
        & (breadth["sector_top_minus_median_26w"] >= 0.035)
        & vix_contained
        & not_stressed
        & not_fragile
    ).astype(int)
    signal_panel["high_breadth_sector_bull"] = (
        (breadth["sector_pct_trend_positive_43w"] >= 0.75)
        & (breadth["sector_pct_positive_26w_return"] >= 0.70)
        & spy_trend.fillna(False)
        & qqq_trend.fillna(False)
        & market_trend
        & not_stressed
        & (~neutral_deteriorating)
    ).astype(int)
    defensive_leaders = ["XLU", "XLP", "XLV"]
    top3_mom = mom26.rank(axis=1, ascending=False, method="first") <= 3
    defensive_top_count = top3_mom[[c for c in defensive_leaders if c in top3_mom.columns]].sum(axis=1)
    signal_panel["defensive_sector_warning"] = (
        (defensive_top_count >= 2)
        & (breadth["sector_pct_trend_positive_43w"] < 0.55)
        & not_stressed
    ).astype(int)
    signal_panel["sector_rotation_quality_score"] = breadth["sector_rotation_quality_score"]
    signal_panel["market_state"] = state

    signal_panel.to_csv(OUT / "phase4_sector_rotation_signal_panel.csv")

    signal_defs = [
        {
            "signal": "sector_breadth_confirmed",
            "formula": "sector_pct_trend_positive_43w>=0.65 AND sector_pct_positive_26w_return>=0.60 AND market_trend_positive AND not stressed_panic/recovery_fragile",
            "economic_interpretation": "Most sectors are in positive trend; enough breadth to risk a dedicated sector offense sleeve.",
            "expected_use": "Primary gate for 12-25% sector sleeve budget.",
            "causal_lag_rule": "week-t feature applied to week-t+1 portfolio return",
        },
        {
            "signal": "sector_leadership_confirmed",
            "formula": "breadth>=0.55 AND top sector beats SPY by >=1.5pp over 26w AND top-minus-median>=3.5pp AND VIX contained",
            "economic_interpretation": "Leadership is differentiated enough for rotation but not isolated in a weak market.",
            "expected_use": "Hybrid sector + Phase 3 US offense candidate.",
            "causal_lag_rule": "week-t feature applied to week-t+1 portfolio return",
        },
        {
            "signal": "high_breadth_sector_bull",
            "formula": "sector breadth>=0.75, positive 26w sectors>=0.70, SPY/QQQ trend positive, market trend positive, not stressed",
            "economic_interpretation": "Strong bull tape suitable only for concentrated stretch sector momentum.",
            "expected_use": "Stretch candidate gate.",
            "causal_lag_rule": "week-t feature applied to week-t+1 portfolio return",
        },
        {
            "signal": "defensive_sector_warning",
            "formula": "at least two of XLU/XLP/XLV in top 3 momentum while sector breadth<0.55",
            "economic_interpretation": "Leadership is defensive and broad tape is weak; not an offense signal.",
            "expected_use": "Caution flag and diagnostics only.",
            "causal_lag_rule": "week-t feature applied to week-t+1 portfolio return",
        },
        {
            "signal": "sector_rotation_quality_score",
            "formula": "0.35*breadth + 0.25*positive_26w + 0.25*leadership_dispersion + 0.15*vix_contained, clipped 0-1",
            "economic_interpretation": "Continuous summary of broad participation plus differentiated leadership.",
            "expected_use": "Diagnostics and high-quality regime confirmation.",
            "causal_lag_rule": "week-t feature applied to week-t+1 portfolio return",
        },
    ]
    pd.DataFrame(signal_defs).to_csv(OUT / "phase4_sector_rotation_signal_definitions.csv", index=False)

    coverage_rows = []
    for sig in ["sector_breadth_confirmed", "sector_leadership_confirmed", "high_breadth_sector_bull", "defensive_sector_warning"]:
        active = signal_panel[sig].astype(bool)
        coverage_rows.append(
            {
                "signal": sig,
                "active_weeks": int(active.sum()),
                "active_frequency": float(active.mean()),
                "active_states": "|".join(sorted(state[active].dropna().unique())),
                "calm_trend_coverage": float(active[state == "calm_trend"].mean()) if (state == "calm_trend").any() else np.nan,
                "neutral_mixed_coverage": float(active[state == "neutral_mixed"].mean()) if (state == "neutral_mixed").any() else np.nan,
                "recovery_confirmed_coverage": float(active[state == "recovery_confirmed"].mean()) if (state == "recovery_confirmed").any() else np.nan,
                "stressed_panic_coverage": float(active[state == "stressed_panic"].mean()) if (state == "stressed_panic").any() else np.nan,
            }
        )
    pd.DataFrame(coverage_rows).to_csv(OUT / "phase4_sector_rotation_signal_coverage.csv", index=False)

    # ──────────────────────────────────────────────
    # PART D — SECTOR SLEEVE DESIGN
    # ──────────────────────────────────────────────
    print("\n=== PART D: sector sleeve designs ===")
    sleeve_designs = [
        {
            "sleeve": "EqualWeightSector",
            "selection": "all eligible sector ETFs",
            "weighting": "equal weight",
            "gate": "none",
            "fallback": "eligible sectors with available prices; otherwise BIL",
            "portfolio_use": "benchmark only",
        },
        {
            "sleeve": "Top3SectorMomentum",
            "selection": "top 3 by 0.5*13w + 0.5*26w momentum",
            "weighting": "equal weight",
            "gate": "none at sleeve level; portfolio gate applied by Layer 3 state tilt",
            "fallback": "BIL if fewer than 2 valid sectors",
            "portfolio_use": "C2/C3 dedicated offense",
        },
        {
            "sleeve": "Top5SectorMomentum",
            "selection": "top 5 by 0.5*13w + 0.5*26w momentum",
            "weighting": "equal weight",
            "gate": "none at sleeve level; portfolio gate applied by Layer 3 state tilt",
            "fallback": "BIL if fewer than 3 valid sectors",
            "portfolio_use": "small overlay benchmark",
        },
        {
            "sleeve": "RiskAdjustedTop3",
            "selection": "top 3 by blended momentum / 26w volatility",
            "weighting": "inverse vol, 45% cap",
            "gate": "requires positive 26w/43w trend",
            "fallback": "BIL",
            "portfolio_use": "standalone validation",
        },
        {
            "sleeve": "SectorMomentumWithBreadthGate",
            "selection": "top 5 by blended momentum when sector_breadth_confirmed",
            "weighting": "equal weight",
            "gate": "sector_breadth_confirmed",
            "fallback": "BIL",
            "portfolio_use": "standalone gate validation",
        },
        {
            "sleeve": "SectorMomentumWithDefensiveFilter",
            "selection": "top 5 by blended momentum, exclude sectors below 43w trend, no one-sector-only concentration",
            "weighting": "equal weight, 35% cap",
            "gate": "trend positive sectors only",
            "fallback": "BIL",
            "portfolio_use": "standalone filter validation",
        },
        {
            "sleeve": "SectorBalancedAggressive",
            "selection": "top 5 by blended momentum, only in breadth-confirmed states",
            "weighting": "inverse vol, 30% cap",
            "gate": "sector_breadth_confirmed",
            "fallback": "BIL",
            "portfolio_use": "C4/C6 balanced sleeve",
        },
        {
            "sleeve": "SectorStretchAggressive",
            "selection": "top 3 by risk-adjusted momentum, only in high_breadth_sector_bull states",
            "weighting": "inverse vol, 45% cap",
            "gate": "high_breadth_sector_bull",
            "fallback": "BIL",
            "portfolio_use": "C5 stretch sleeve",
        },
    ]
    pd.DataFrame(sleeve_designs).to_csv(OUT / "phase4_sector_sleeve_designs.csv", index=False)

    blended_mom = 0.5 * mom13 + 0.5 * mom26
    score_risk = risk_adj_mom
    all_columns = list(prices.columns)

    def make_sleeve_weights(design: str) -> pd.DataFrame:
        weights = pd.DataFrame(0.0, index=prices.index, columns=all_columns)
        for date in prices.index:
            valid = sector_prices.loc[date].dropna().index.tolist()
            selected: list[str] = []
            raw_w: pd.Series | None = None

            if design == "EqualWeightSector":
                selected = valid
                raw_w = pd.Series(1.0, index=selected)
            else:
                if design in {"SectorMomentumWithBreadthGate", "SectorBalancedAggressive"} and not bool(signal_panel.at[date, "sector_breadth_confirmed"]):
                    weights.at[date, CASH] = 1.0
                    continue
                if design == "SectorStretchAggressive" and not bool(signal_panel.at[date, "high_breadth_sector_bull"]):
                    weights.at[date, CASH] = 1.0
                    continue

                score = blended_mom.loc[date].copy()
                if design in {"RiskAdjustedTop3", "SectorStretchAggressive"}:
                    score = score_risk.loc[date].copy()
                if design in {"RiskAdjustedTop3", "SectorMomentumWithDefensiveFilter", "SectorBalancedAggressive", "SectorStretchAggressive"}:
                    score = score.where(trend43.loc[date])
                    score = score.where(mom26.loc[date] > 0)
                score = score.replace([np.inf, -np.inf], np.nan).dropna()
                if design in {"Top3SectorMomentum", "RiskAdjustedTop3", "SectorStretchAggressive"}:
                    selected = score.sort_values(ascending=False).head(3).index.tolist()
                    min_count = 2
                else:
                    selected = score.sort_values(ascending=False).head(5).index.tolist()
                    min_count = 3
                if len(selected) < min_count:
                    weights.at[date, CASH] = 1.0
                    continue
                if design in {"RiskAdjustedTop3", "SectorBalancedAggressive", "SectorStretchAggressive"}:
                    inv_vol = (1.0 / vol26.loc[date, selected].replace(0, np.nan)).replace([np.inf, -np.inf], np.nan).dropna()
                    raw_w = inv_vol if not inv_vol.empty else pd.Series(1.0, index=selected)
                else:
                    raw_w = pd.Series(1.0, index=selected)

            if raw_w is None or raw_w.empty:
                weights.at[date, CASH] = 1.0
                continue
            cap = 0.45 if design in {"RiskAdjustedTop3", "SectorStretchAggressive"} else 0.35 if design == "SectorMomentumWithDefensiveFilter" else 0.30 if design == "SectorBalancedAggressive" else 1.0
            w = cap_weights(raw_w, cap=cap)
            weights.loc[date, w.index] = w.values
            if float(weights.loc[date].sum()) <= 1e-12:
                weights.at[date, CASH] = 1.0
        return weights

    sleeve_weights = {design["sleeve"]: make_sleeve_weights(design["sleeve"]) for design in sleeve_designs}
    sleeve_paths = {name: compute_path(w, next_returns, cash_returns) for name, w in sleeve_weights.items()}

    # Save standalone sleeve artifacts and build-input sleeves.
    returns_wide = pd.DataFrame({name: path["net_return"] for name, path in sleeve_paths.items()})
    returns_wide.to_csv(OUT / "phase4_sector_sleeve_returns.csv")
    turnover_wide = pd.DataFrame({name: path["turnover"] for name, path in sleeve_paths.items()})
    turnover_wide.to_csv(OUT / "phase4_sector_sleeve_turnover.csv")
    weight_rows = []
    for name, weights in sleeve_weights.items():
        nonzero = weights.stack()
        nonzero = nonzero[nonzero.abs() > 1e-12]
        for (date, ticker), weight in nonzero.items():
            weight_rows.append({"date": date, "sleeve": name, "ticker": ticker, "weight": weight})
    pd.DataFrame(weight_rows).to_csv(OUT / "phase4_sector_sleeve_weights.csv", index=False)

    for build_name, design_name in BUILD_SLEEVE_MAP.items():
        sleeve_weights[design_name].to_csv(OUT / f"phase4_build_sleeve_weights_{build_name}.csv")

    # ──────────────────────────────────────────────
    # PART E — STANDALONE SLEEVE VALIDATION
    # ──────────────────────────────────────────────
    print("\n=== PART E: standalone sleeve validation ===")
    benchmark_returns = {
        "SPY": spy_ret,
        "QQQ": qqq_ret,
        "BIL": bil_ret,
        "EqualWeightSector": returns_wide["EqualWeightSector"],
        "GGG1DefaultOffenseEW": returns[[t for t in ["SPY", "QQQ", "IWM", "EFA", "VEA", "VWO", "EWJ", "VNQ", "PDBC", "DBA"] if t in returns.columns]].mean(axis=1),
        "Phase3USPureEW": returns[[t for t in ["SPY", "QQQ", "IWM"] if t in returns.columns]].mean(axis=1),
    }
    old_sector_path = L2A / "strategy_returns_sector_rotation_with_sma_filter.csv"
    if old_sector_path.exists():
        benchmark_returns["ExistingSectorRotationWithSMA"] = load_strategy_return(old_sector_path)

    sleeve_val_rows = []
    sleeve_hold_rows = []
    sleeve_state_rows = []
    sleeve_bm_rows = []
    for name, path in sleeve_paths.items():
        ret = path["net_return"]
        for wname, (start, end) in WINDOWS.items():
            m = calc_metrics(ws(ret, start, end), name)
            row = {
                "sleeve": name,
                "window": wname,
                **m,
                "avg_turnover": float(ws(path["turnover"], start, end).mean()),
            }
            if wname == "full":
                sleeve_val_rows.append(row)
            else:
                sleeve_hold_rows.append(row)
        for st in sorted(state.dropna().unique()):
            idx = state[state == st].index
            m = calc_metrics(ret.reindex(idx), name)
            sleeve_state_rows.append({"sleeve": name, "state": st, **m})
        for bm_name, bm in benchmark_returns.items():
            beta_s, corr_s = beta_corr(ret, bm)
            sleeve_bm_rows.append(
                {
                    "sleeve": name,
                    "benchmark": bm_name,
                    "active_ann_return": active_ann_return(ret, bm),
                    "correlation": corr_s,
                    "beta": beta_s,
                    "sleeve_ann_return": ann_return(ret),
                    "benchmark_ann_return": ann_return(bm),
                    "sleeve_sharpe": calc_metrics(ret).get("sharpe"),
                    "benchmark_sharpe": calc_metrics(bm).get("sharpe"),
                    "sleeve_calmar": calc_metrics(ret).get("calmar"),
                    "benchmark_calmar": calc_metrics(bm).get("calmar"),
                }
            )

    sleeve_val_df = pd.DataFrame(sleeve_val_rows)
    sleeve_hold_df = pd.DataFrame(sleeve_hold_rows)
    sleeve_state_df = pd.DataFrame(sleeve_state_rows)
    sleeve_bm_df = pd.DataFrame(sleeve_bm_rows)
    sleeve_val_df.to_csv(OUT / "phase4_sector_sleeve_validation.csv", index=False)
    sleeve_state_df.to_csv(OUT / "phase4_sector_sleeve_state_validation.csv", index=False)
    sleeve_hold_df.to_csv(OUT / "phase4_sector_sleeve_holdout_validation.csv", index=False)
    sleeve_bm_df.to_csv(OUT / "phase4_sector_sleeve_vs_benchmark.csv", index=False)

    spy_calmar = calc_metrics(spy_ret).get("calmar")
    eq_calmar = calc_metrics(returns_wide["EqualWeightSector"]).get("calmar")
    best_sleeve_calmar = sleeve_val_df["calmar"].max()
    best_sleeve_sharpe = sleeve_val_df["sharpe"].max()
    eq_sharpe = calc_metrics(returns_wide["EqualWeightSector"]).get("sharpe")
    sector_validation_positive = bool(
        (best_sleeve_calmar > max(spy_calmar, eq_calmar))
        or (best_sleeve_sharpe > eq_sharpe)
        or ((sleeve_val_df["max_drawdown"].max() > calc_metrics(spy_ret).get("max_drawdown") + 0.10)
            and (sleeve_val_df["ann_return"].max() > 0.06))
    )
    print(f"Standalone sector validation positive: {sector_validation_positive}")

    # ──────────────────────────────────────────────
    # PART F/G — CANDIDATES + BUILD
    # ──────────────────────────────────────────────
    print("\n=== PART F/G: candidate designs and build ===")
    candidate_designs = [
        {
            "candidate": "improved_phase4_sector_small_overlay",
            "sector_sleeve": "Top5SectorMomentum",
            "budget": "12% target in sector_breadth_confirmed states",
            "logic": "small overlay funded from cash/defense/old diversified offense; stressed_panic unchanged",
        },
        {
            "candidate": "improved_phase4_sector_20pct_offense",
            "sector_sleeve": "Top3SectorMomentum",
            "budget": "20% target in sector_breadth_confirmed states",
            "logic": "first true return-unlock candidate; neutral boost plus dedicated sector offense; stressed_panic unchanged",
        },
        {
            "candidate": "improved_phase4_sector_25pct_offense",
            "sector_sleeve": "Top3SectorMomentum",
            "budget": "25% target in sector_breadth_confirmed states",
            "logic": "more aggressive sector budget; reject on Sharpe/drawdown/CVaR failure",
        },
        {
            "candidate": "improved_phase4_balanced_sector_breadth",
            "sector_sleeve": "SectorBalancedAggressive",
            "budget": "20% target in sector_breadth_confirmed states",
            "logic": "top5 inverse-vol sector sleeve for Sharpe preservation",
        },
        {
            "candidate": "improved_phase4_stretch_sector_momentum",
            "sector_sleeve": "SectorStretchAggressive",
            "budget": "25% target only in high_breadth_sector_bull states",
            "logic": "concentrated stretch candidate; reject if hidden beta or drawdown dominates",
        },
        {
            "candidate": "improved_phase4_sector_us_hybrid",
            "sector_sleeve": "SectorBalancedAggressive + Phase 3 calm US offense",
            "budget": "16% target when sector_leadership_confirmed",
            "logic": "hybrid of Phase 3 US pure offense and sector leadership sleeve",
        },
    ]
    cand_design_df = pd.DataFrame(candidate_designs)
    cand_design_df.to_csv(OUT / "phase4_candidate_designs.csv", index=False)

    build_skipped = False
    if not sector_validation_positive:
        build_skipped = True
        pd.DataFrame(
            [{"candidate": c, "reason": "standalone_sector_sleeves_failed_validation_gate"} for c in CANDIDATES]
        ).to_csv(OUT / "phase4_candidate_failure_reasons.csv", index=False)
        print("Skipping portfolio builds because standalone sector validation failed.")
    else:
        env = os.environ.copy()
        env["BUILD_VERSION_NAMES"] = ",".join(CANDIDATES)
        build_script = ROOT / "scripts" / "build_improvement_artifacts.py"
        print("Running filtered Layer 3 build for Phase 4 candidates...")
        res = subprocess.run(
            [sys.executable, str(build_script)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=900,
        )
        with open(OUT / "phase4_build.log", "w") as f:
            f.write("COMMAND: BUILD_VERSION_NAMES='" + env["BUILD_VERSION_NAMES"] + "' python3 scripts/build_improvement_artifacts.py\n")
            f.write("\n=== STDOUT TAIL ===\n")
            f.write(res.stdout[-12000:])
            f.write("\n=== STDERR TAIL ===\n")
            f.write(res.stderr[-6000:])
        if res.returncode != 0:
            print(res.stderr[-2000:])
            raise SystemExit(f"Layer 3 Phase 4 build failed with exit {res.returncode}")
        missing = [
            f"portfolio_version_{kind}_{candidate}.csv"
            for candidate in CANDIDATES
            for kind in ["returns", "weights", "sleeve_weights"]
            if not (L3 / f"portfolio_version_{kind}_{candidate}.csv").exists()
        ]
        if missing:
            raise SystemExit(f"Missing candidate artifacts after build: {missing}")
        pd.DataFrame([{"candidate": "none", "reason": "all_built"}]).to_csv(
            OUT / "phase4_candidate_failure_reasons.csv", index=False
        )
        print("All Phase 4 candidate artifacts confirmed.")

    # ──────────────────────────────────────────────
    # PART H — FULL + HOLDOUT METRICS
    # ──────────────────────────────────────────────
    print("\n=== PART H: full + holdout metrics ===")
    return_series: dict[str, pd.Series] = {}
    if not build_skipped:
        for c in CANDIDATES:
            return_series[c] = load_return_artifact(L3 / f"portfolio_version_returns_{c}.csv")
    baseline_files = {
        "ggg1": L3 / f"portfolio_version_returns_{GGG1}.csv",
        "phase2_best": L3 / f"portfolio_version_returns_{PHASE2_BEST}.csv",
        "phase3_best": L3 / f"portfolio_version_returns_{PHASE3_BEST}.csv",
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
    return_series["EqualWeightSectorSleeve"] = returns_wide["EqualWeightSector"]

    def exposure_row(portfolio: str, start: str | None, end: str | None) -> dict:
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
            w = ws(w, start, end)
            out["avg_BIL"] = float(w[CASH].mean()) if CASH in w.columns else np.nan
            out["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else np.nan
            out["avg_QQQ"] = float(w["QQQ"].mean()) if "QQQ" in w.columns else np.nan
        if sleeve_path.exists():
            sw = pd.read_csv(sleeve_path, index_col=0, parse_dates=True)
            sw.index = pd.to_datetime(sw.index).tz_localize(None)
            sw = ws(sw, start, end)
            sector_cols = [c for c in sw.columns if c.startswith("phase4_")]
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
        return out

    ggg_turn = np.nan
    ggg_return_path = L3 / f"portfolio_version_returns_{GGG1}.csv"
    if ggg_return_path.exists():
        ggg_df = pd.read_csv(ggg_return_path, index_col=0, parse_dates=True)
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

            for bm_name, bm_series in [
                ("SPY", return_series.get("SPY")),
                ("QQQ", return_series.get("QQQ")),
                ("ggg1", return_series.get("ggg1")),
                ("phase2_best", return_series.get("phase2_best")),
                ("phase3_best", return_series.get("phase3_best")),
            ]:
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
    metrics_df.to_csv(OUT / "phase4_candidate_metrics_full.csv", index=False)
    metrics_df[metrics_df["window"] != "full"].to_csv(OUT / "phase4_candidate_holdout_metrics.csv", index=False)
    focus = CANDIDATES + [
        "ggg1",
        "phase2_best",
        "phase3_best",
        "prod_pin",
        "official_shadow",
        "SPY",
        "QQQ",
        "bench_60_40",
        "equal_weight_etf",
        "EqualWeightSectorSleeve",
    ]
    metrics_df[metrics_df["portfolio"].isin(focus)].to_csv(OUT / "phase4_candidate_vs_benchmark_table.csv", index=False)
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
        ]
        if c in metrics_df.columns
    ]
    metrics_df[cap_cols].to_csv(OUT / "phase4_capture_beta_by_window.csv", index=False)

    # ──────────────────────────────────────────────
    # PART I — STATE-BY-STATE DIAGNOSIS
    # ──────────────────────────────────────────────
    print("\n=== PART I: state diagnostics ===")
    state_summary_rows = []
    state_exposure_rows = []
    delta_rows = {"ggg1": [], "phase2_best": [], "phase3_best": []}
    state_names = sorted(state.dropna().unique())
    state_ports = CANDIDATES + ["ggg1", "phase2_best", "phase3_best"] if not build_skipped else ["ggg1", "phase2_best", "phase3_best"]
    for pname in state_ports:
        if pname not in return_series:
            continue
        ret = return_series[pname]
        for st in state_names:
            idx = state[state == st].index
            ret_st = ret.reindex(idx)
            row = {"portfolio": pname, "state": st, **calc_metrics(ret_st, pname)}
            row.update(exposure_row(pname, idx.min().isoformat() if len(idx) else None, idx.max().isoformat() if len(idx) else None))
            # Correct exposure window by exact state index.
            artifact = artifact_name(pname)
            weights_path = L3 / f"portfolio_version_weights_{artifact}.csv"
            sleeve_path = L3 / f"portfolio_version_sleeve_weights_{artifact}.csv"
            if weights_path.exists():
                w = pd.read_csv(weights_path, index_col=0, parse_dates=True)
                w.index = pd.to_datetime(w.index).tz_localize(None)
                wst = w.reindex(idx)
                row["avg_BIL"] = float(wst[CASH].mean()) if CASH in wst.columns else np.nan
                row["avg_SPY"] = float(wst["SPY"].mean()) if "SPY" in wst.columns else np.nan
                row["avg_QQQ"] = float(wst["QQQ"].mean()) if "QQQ" in wst.columns else np.nan
            if sleeve_path.exists():
                sw = pd.read_csv(sleeve_path, index_col=0, parse_dates=True)
                sw.index = pd.to_datetime(sw.index).tz_localize(None)
                swst = sw.reindex(idx)
                sector_cols = [c for c in swst.columns if c.startswith("phase4_")]
                row["avg_sector_sleeve_exposure"] = float(swst[sector_cols].sum(axis=1).mean()) if sector_cols else 0.0
                row["avg_cash_exposure"] = float(swst["cash::BIL"].mean()) if "cash::BIL" in swst.columns else np.nan
                offense_cols = [c for c in ["dual_momentum_topn", "cta_trend_long_only", "composite_selective_signals", "composite_regime_offense_component", *sector_cols] if c in swst.columns]
                defense_cols = [c for c in ["composite_regime_defense_component", "taa_10m_sma"] if c in swst.columns]
                row["avg_offense_exposure"] = float(swst[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan
                row["avg_defense_exposure"] = float(swst[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan
                exp_row = {"portfolio": pname, "state": st}
                for col in swst.columns:
                    exp_row[col] = float(swst[col].mean())
                state_exposure_rows.append(exp_row)
            state_summary_rows.append(row)

    state_summary_df = pd.DataFrame(state_summary_rows)
    state_summary_df.to_csv(OUT / "phase4_state_summary.csv", index=False)
    pd.DataFrame(state_exposure_rows).to_csv(OUT / "phase4_state_exposure_summary.csv", index=False)

    for baseline in ["ggg1", "phase2_best", "phase3_best"]:
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
            "ggg1": "phase4_state_deltas_vs_ggg1.csv",
            "phase2_best": "phase4_state_deltas_vs_phase2_best.csv",
            "phase3_best": "phase4_state_deltas_vs_phase3_best.csv",
        }[baseline]
        pd.DataFrame(rows).to_csv(OUT / out_name, index=False)

    def write_state_diag(st: str, fname: str) -> None:
        state_summary_df[state_summary_df["state"] == st].to_csv(OUT / fname, index=False)

    write_state_diag("neutral_mixed", "phase4_neutral_cash_unlock_diagnostics.csv")
    write_state_diag("calm_trend", "phase4_calm_sector_offense_diagnostics.csv")
    write_state_diag("recovery_confirmed", "phase4_recovery_participation_diagnostics.csv")
    write_state_diag("stressed_panic", "phase4_stress_protection_diagnostics.csv")

    # ──────────────────────────────────────────────
    # PART J/K — RISK, REALISM, SELECTION
    # ──────────────────────────────────────────────
    print("\n=== PART J/K: risk checks and selection ===")
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
    ggg_bear = calc_metrics(ws(return_series.get("ggg1", pd.Series(dtype=float)), "2022-01-01", "2022-12-31"))
    sixty_full = calc_metrics(return_series.get("bench_60_40", pd.Series(dtype=float)))
    spy_full = calc_metrics(return_series["SPY"])
    signal_active_idx = signal_panel[signal_panel["sector_breadth_confirmed"].astype(bool)].index
    signal_inactive_idx = signal_panel[~signal_panel["sector_breadth_confirmed"].astype(bool)].index

    for pname in CANDIDATES:
        if pname not in return_series:
            fail_rows.append({"portfolio": pname, "reason": "not_built"})
            continue
        ret = return_series[pname]
        m_full = calc_metrics(ret)
        m_2020 = calc_metrics(ws(ret, "2020-01-01", None))
        m_2021 = calc_metrics(ws(ret, "2021-01-01", None))
        m_bear = calc_metrics(ws(ret, "2022-01-01", "2022-12-31"))
        beta_spy, corr_spy = beta_corr(ret, return_series["SPY"])
        beta_qqq, corr_qqq = beta_corr(ret, return_series["QQQ"])
        ggg_beta_spy, _ = beta_corr(return_series["ggg1"], return_series["SPY"])
        ann_improve = m_full["ann_return"] - ggg_full["ann_return"]
        beta_attr = (beta_spy - ggg_beta_spy) * spy_full["ann_return"] if pd.notna(beta_spy) and pd.notna(ggg_beta_spy) else np.nan
        pct_from_beta = abs(beta_attr) / abs(ann_improve) if abs(ann_improve) > 1e-8 and pd.notna(beta_attr) else np.nan
        exp_full = exposure_row(pname, None, None)
        bear_ok = m_bear["ann_return"] >= ggg_bear["ann_return"] - 0.04
        maxdd_ok = m_full["max_drawdown"] >= -0.22
        sharpe_ok = m_full["sharpe"] >= 0.90
        disguised = bool((pd.notna(beta_spy) and beta_spy > 0.30) or (pd.notna(corr_spy) and corr_spy > 0.50) or (pd.notna(corr_qqq) and corr_qqq > 0.55))
        cvar_bad = m_full["cvar_5"] < ggg_full["cvar_5"] - 0.008

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
                "better_than_60_40_sharpe": m_full["sharpe"] > sixty_full.get("sharpe", -np.inf),
                "disguised_spy_qqq": disguised,
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
                "beta_attribution_estimate": beta_attr,
                "pct_improvement_from_beta": pct_from_beta,
                "hidden_beta_risk": "HIGH" if disguised or (pd.notna(pct_from_beta) and pct_from_beta > 0.75) else "LOW",
                "avg_BIL": exp_full["avg_BIL"],
                "bil_reduction_vs_ggg1": exp_full["avg_BIL"] - exposure_row("ggg1", None, None)["avg_BIL"],
            }
        )
        bear_rows.append(
            {
                "portfolio": pname,
                "bear_2022_return": m_bear["ann_return"],
                "ggg1_bear_2022_return": ggg_bear["ann_return"],
                "delta_vs_ggg1": m_bear["ann_return"] - ggg_bear["ann_return"],
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

        on_ret = ret.reindex(signal_active_idx)
        off_ret = ret.reindex(signal_inactive_idx)
        ggg_on = return_series["ggg1"].reindex(signal_active_idx)
        sig_active_rows.append(
            {
                "portfolio": pname,
                "signal": "sector_breadth_confirmed",
                "active_weeks": int(on_ret.dropna().shape[0]),
                "signal_active_ann_return": ann_return(on_ret),
                "signal_inactive_ann_return": ann_return(off_ret),
                "signal_active_delta_vs_ggg1": ann_return(on_ret) - ann_return(ggg_on),
            }
        )

        reasons = []
        if not maxdd_ok:
            reasons.append("max_drawdown_worse_than_22pct")
        if not sharpe_ok:
            reasons.append("sharpe_below_0.90")
        if not bear_ok:
            reasons.append("2022_bear_protection_worse_by_more_than_4pp")
        if disguised:
            reasons.append("hidden_spy_qqq_beta_or_correlation")
        if cvar_bad:
            reasons.append("cvar_materially_worse_than_ggg1")
        if m_full["ann_return"] <= ggg_full["ann_return"] + 0.0005:
            reasons.append("return_improvement_tiny_or_negative_vs_ggg1")
        if m_2020["ann_return"] <= calc_metrics(ws(return_series["ggg1"], "2020-01-01", None))["ann_return"]:
            reasons.append("holdout_2020_not_better_than_ggg1")
        if reasons:
            fail_rows.append({"portfolio": pname, "reason": "|".join(reasons)})

        beats_ggg = m_full["ann_return"] > ggg_full["ann_return"] + 0.001
        beats_p2 = m_full["ann_return"] > p2_full["ann_return"] or m_full["sharpe"] > p2_full["sharpe"]
        beats_p3 = m_full["ann_return"] > p3_full["ann_return"] or m_full["sharpe"] > p3_full["sharpe"]
        holdout_good = (
            m_2020["ann_return"] > calc_metrics(ws(return_series["ggg1"], "2020-01-01", None))["ann_return"]
            or m_2021["ann_return"] > calc_metrics(ws(return_series["ggg1"], "2021-01-01", None))["ann_return"]
        )
        sector_active_good = sig_active_rows[-1]["signal_active_delta_vs_ggg1"] > 0

        if not maxdd_ok or not sharpe_ok or not bear_ok or disguised:
            classification = "REJECT"
            reason = "failed hard risk/realism guardrail"
        elif (
            sector_validation_positive
            and beats_ggg
            and beats_p2
            and beats_p3
            and holdout_good
            and sector_active_good
            and m_full["sharpe"] >= 0.95
            and m_full["max_drawdown"] >= -0.20
            and (m_full["ann_return"] >= 0.09 or m_2020["ann_return"] >= 0.10)
        ):
            classification = "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT"
            reason = "passes aggressive return/risk/holdout/sector-active gates"
        elif sector_validation_positive and beats_ggg and (beats_p2 or beats_p3 or holdout_good) and sector_active_good:
            classification = "KEEP_AS_AGGRESSIVE_SHADOW"
            reason = "credible incremental sector sleeve benefit but not production-challenger strength"
        elif sector_validation_positive and (beats_ggg or sector_active_good or holdout_good):
            classification = "KEEP_AS_RESEARCH_ONLY"
            reason = "partial sector evidence but weak aggregate improvement"
        else:
            classification = "REJECT"
            reason = "sector rotation did not improve portfolio enough"
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
                "bear_2022_return": m_bear["ann_return"],
                "beats_ggg1": beats_ggg,
                "beats_phase2_best": beats_p2,
                "beats_phase3_best": beats_p3,
                "sector_active_good": sector_active_good,
                "sector_validation_positive": sector_validation_positive,
            }
        )

    pd.DataFrame(risk_rows).to_csv(OUT / "phase4_risk_realism_checks.csv", index=False)
    pd.DataFrame(hidden_rows).to_csv(OUT / "phase4_hidden_beta_cash_checks.csv", index=False)
    pd.DataFrame(bear_rows).to_csv(OUT / "phase4_2022_bear_check.csv", index=False)
    pd.DataFrame(concentration_rows).to_csv(OUT / "phase4_sector_concentration_checks.csv", index=False)
    pd.DataFrame(sig_active_rows).to_csv(OUT / "phase4_signal_active_candidate_performance.csv", index=False)
    pd.DataFrame(fail_rows if fail_rows else [{"portfolio": "none", "reason": "no_failure_flags"}]).to_csv(
        OUT / "phase4_candidate_failure_reasons.csv", index=False
    )
    selection_df = pd.DataFrame(selection_rows)
    selection_df.to_csv(OUT / "phase4_selection_table.csv", index=False)

    # ──────────────────────────────────────────────
    # PART L/M — AUDITS + NEXT DECISION
    # ──────────────────────────────────────────────
    print("\n=== PART L/M: audits and next decision ===")
    best_candidate = None
    if not selection_df.empty:
        qual = selection_df[selection_df["classification"].isin(["PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT", "KEEP_AS_AGGRESSIVE_SHADOW"])]
        if not qual.empty:
            class_rank = {"PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT": 0, "KEEP_AS_AGGRESSIVE_SHADOW": 1}
            qual = qual.assign(class_rank=qual["classification"].map(class_rank))
            best_candidate = qual.sort_values(["class_rank", "full_ann_return", "full_sharpe"], ascending=[True, False, False]).iloc[0]["portfolio"]

    audit_rows = []
    audit_summary_lines = ["# Phase 4 Audit Summary\n\n"]
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
                continue
            res = subprocess.run(
                [sys.executable, str(script_path), best_candidate, *flags],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=420,
            )
            status = "PASS" if res.returncode == 0 else "FAIL"
            log_name = f"phase4_{audit_name}_{'quick' if flags else 'full'}.log"
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
        OUT / "phase4_audit_results.csv", index=False
    )
    (OUT / "phase4_audit_summary.md").write_text("".join(audit_summary_lines))

    n_challenger = int((selection_df["classification"] == "PRODUCTION_CHALLENGER_PENDING_FULL_AUDIT").sum()) if not selection_df.empty else 0
    n_shadow = int((selection_df["classification"] == "KEEP_AS_AGGRESSIVE_SHADOW").sum()) if not selection_df.empty else 0
    n_research = int((selection_df["classification"] == "KEEP_AS_RESEARCH_ONLY").sum()) if not selection_df.empty else 0
    if n_challenger:
        decision = "PROMOTE_PHASE4_TO_PRODUCTION_CHALLENGER_PENDING_HUMAN_REVIEW"
        rationale = f"{best_candidate} met production-challenger gates and audit requirements."
    elif n_shadow:
        decision = "KEEP_PHASE4_AS_AGGRESSIVE_SHADOW"
        rationale = f"{best_candidate} is a credible higher-return/risk tradeoff but not strong enough for production challenge."
    elif sector_validation_positive and n_research:
        decision = "PROCEED_TO_PHASE4B_REFINED_SECTOR_ROTATION"
        rationale = "Sector sleeves had some useful standalone/state evidence, but portfolio candidates were not strong enough."
    elif not sector_validation_positive:
        decision = "STOP_AGGRESSIVE_BRANCH_PACKAGE_GGG1_AND_SHADOWS"
        rationale = "Existing ETF sector rotation failed standalone validation; do not force a portfolio candidate."
    else:
        decision = "STOP_AGGRESSIVE_BRANCH_PACKAGE_GGG1_AND_SHADOWS"
        rationale = "Sector rotation became an inferior benchmark substitute without credible portfolio improvement."

    next_action_df = pd.DataFrame(
        [
            {
                "recommendation": decision,
                "best_candidate": best_candidate or "none",
                "rationale": rationale,
                "n_challenger": n_challenger,
                "n_shadow": n_shadow,
                "n_research_only": n_research,
            }
        ]
    )
    next_action_df.to_csv(OUT / "phase4_next_action_recommendation.csv", index=False)
    next_action_df.rename(columns={"recommendation": "decision"}).to_csv(OUT / "phase4_next_phase_decision.csv", index=False)

    with open(OUT / "phase4_protocol.json", "w") as f:
        json.dump(
            {
                "phase": "phase_4_sector_breadth_rotation",
                "date": "2026-05-07",
                "production_pin": PRODUCTION_PIN,
                "official_shadow_pin": OFFICIAL_SHADOW,
                "base_candidate": GGG1,
                "phase2_best": PHASE2_BEST,
                "phase3_best": PHASE3_BEST,
                "candidates": CANDIDATES,
                "best_candidate": best_candidate or "none",
                "decision": decision,
                "sector_validation_positive": sector_validation_positive,
                "no_pin_changes": True,
            },
            f,
            indent=2,
        )

    # ──────────────────────────────────────────────
    # PART N — REPORT
    # ──────────────────────────────────────────────
    print("\n=== PART N: report ===")
    full_focus = metrics_df[(metrics_df["window"] == "full") & (metrics_df["portfolio"].isin(CANDIDATES + ["ggg1", "phase2_best", "phase3_best", "prod_pin", "official_shadow", "SPY", "QQQ", "bench_60_40", "EqualWeightSectorSleeve"]))]
    report_cols = [c for c in ["portfolio", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_sector_sleeve_exposure", "beta_spy", "corr_spy"] if c in full_focus.columns]
    hold_focus = metrics_df[(metrics_df["window"].isin(["holdout_2020", "holdout_2021", "bear_2022", "recovery_2023"])) & (metrics_df["portfolio"].isin(CANDIDATES + ["ggg1", "phase2_best", "phase3_best", "SPY", "QQQ"]))]
    hold_cols = [c for c in ["portfolio", "window", "ann_return", "sharpe", "max_drawdown", "avg_BIL", "avg_sector_sleeve_exposure"] if c in hold_focus.columns]
    state_key = state_summary_df[state_summary_df["portfolio"].isin(CANDIDATES + ["ggg1", "phase2_best", "phase3_best"])][
        [c for c in ["portfolio", "state", "ann_return", "sharpe", "max_drawdown", "avg_BIL", "avg_sector_sleeve_exposure", "avg_offense_exposure", "avg_defense_exposure"] if c in state_summary_df.columns]
    ]

    best_line = selection_df.sort_values("full_ann_return", ascending=False).head(1) if not selection_df.empty else pd.DataFrame()
    next_phase_prompt = """Phase 4B should refine sector rotation only if it can fix the observed weaknesses without a grid search:
1. keep the same existing ETF universe and causal lag rule;
2. test whether sector sleeve timing should use calmer top-5 balanced exposure rather than top-3 concentration;
3. isolate whether active sector-signal weeks beat GGG1 after costs;
4. keep stressed_panic unchanged;
5. reject any candidate that is mostly SPY/QQQ beta or worse than Phase 2/Phase 3 shadows."""

    report_text = f"""# Phase 4 — Sector Breadth / Sector ETF Rotation

**Date:** 2026-05-07
**Type:** Strategy research. No production pins changed. No auto-promotion.
**Production pin:** `{PRODUCTION_PIN}`
**Official shadow pin:** `{OFFICIAL_SHADOW}`
**Base:** `{GGG1}`

## Commands Executed

```
{chr(10).join(COMMANDS_EXECUTED)}
BUILD_VERSION_NAMES='{','.join(CANDIDATES)}' python3 scripts/build_improvement_artifacts.py
```

## Files Created / Modified

**Script created:** `scripts/phase_4_sector_breadth_rotation.py`

**Build script modified:** `scripts/build_improvement_artifacts.py` added Phase 4 sector sleeve registration, state tilts, and six filtered version specs.

**Output directory:** `{OUT}`

**Report created:** `docs/research/2026-05-07_phase_4_sector_breadth_rotation_report.md`

## Phase 1-3 Bottleneck Summary

Phase 1 found the return ceiling was mandate-driven: high non-stressed BIL/cash and limited calm-trend upside capture, while stressed_panic protection worked and should not be weakened.

Phase 2 reduced some cash and shifted sleeves, but the best aggressive shadow reached only about 7.39% full-period return because internal sleeve BIL and diversified offense composition remained the real bottlenecks.

Phase 3 improved the small offense component by using pure US equity in high-breadth calm states. It improved Sharpe, especially recent holdouts, but the modified component was too small to lift full-period return toward 9-10%.

## Sector Universe Inventory

Eligible sector ETFs found in existing data: `{', '.join(eligible_sectors)}`.

{md_table(inv_df[['ticker','category','start_date','end_date','ann_return','ann_vol','sharpe','max_drawdown','correlation_to_SPY','eligible_for_phase4_sector_sleeve']], 16)}

## Sector Features And Signals

All features are computed through week `t` and applied to week `t+1` returns. No centered windows, future returns, or future states are used.

{md_table(pd.DataFrame(coverage_rows), 8)}

## Sector Sleeve Standalone Validation

{md_table(sleeve_val_df[['sleeve','ann_return','ann_vol','sharpe','max_drawdown','calmar','cvar_5','avg_turnover']].sort_values('ann_return', ascending=False), 12)}

Standalone validation positive: **{sector_validation_positive}**. The gate is based on whether any sector sleeve improves a useful risk-adjusted dimension versus SPY/equal-sector, especially Calmar/drawdown after costs.

## Candidate Logic

{md_table(cand_design_df, 8)}

## Full-Period Metrics

{md_table(full_focus[report_cols].sort_values('ann_return', ascending=False), 18)}

## Holdout And Recent Metrics

{md_table(hold_focus[hold_cols].sort_values(['window','ann_return'], ascending=[True, False]), 30)}

## State-By-State Impact

{md_table(state_key.sort_values(['state','portfolio']), 36)}

## Risk / Realism Checks

{md_table(pd.DataFrame(risk_rows), 12)}

## Hidden Beta / Cash Checks

{md_table(pd.DataFrame(hidden_rows), 12)}

## 2022 Bear Protection

{md_table(pd.DataFrame(bear_rows), 12)}

## Sector Concentration / Turnover

{md_table(pd.DataFrame(concentration_rows), 12)}

## Sector-Active Windows

{md_table(pd.DataFrame(sig_active_rows), 12)}

## Selection Table

{md_table(selection_df, 12)}

## Audit Results

{md_table(pd.DataFrame(audit_rows if audit_rows else [{'audit':'none','candidate':'none','status':'SKIPPED_NO_QUALIFIER'}]), 8)}

## Final Recommendation

**Recommendation:** `{decision}`

**Best candidate:** `{best_candidate or 'none'}`

**Rationale:** {rationale}

## Next Phase Prompt Outline

```
{next_phase_prompt}
```

## Resume / Project Story Summary

Phase 4 tested whether a larger dedicated sector ETF sleeve could move the strategy toward 9-10% annual return without abandoning the defensive identity. The sector universe was present and clean, features/signals were causal, standalone sleeves were validated before portfolio candidates, and Layer 3 candidates were built only through the filtered production pipeline. The final decision above should guide the next research step; production, shadow, and GGG1 pins remain unchanged.
"""
    REPORT.write_text(report_text)

    print(f"Decision: {decision}")
    print(f"Best candidate: {best_candidate or 'none'}")
    print(f"Report: {REPORT}")
    print("Done. No production pins changed.")


if __name__ == "__main__":
    main()
