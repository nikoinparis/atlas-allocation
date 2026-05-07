#!/usr/bin/env python3
"""
Phase 5 - True Stock Breadth Data Upgrade

Audits whether the repo contains stock-level data suitable for causal stock
breadth signals. If a clean point-in-time source is unavailable, the phase
stops before portfolio builds and records the data-upgrade path. Stock breadth
is a signal-only input; no individual-stock trading is introduced.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "data" / "01_data_hub"
L1 = ROOT / "data" / "02_layer1_signals"
L2B = ROOT / "data" / "04_layer2b_risk_regime_engine"
L3 = ROOT / "data" / "05_layer3_portfolio_construction"
PHASE4B_OUT = ROOT / "data" / "research" / "phase_4b_refined_sector_rotation"
OUT = ROOT / "data" / "research" / "phase_5_true_stock_breadth_data_upgrade"
REPORT = ROOT / "docs" / "research" / "2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md"
OUT.mkdir(parents=True, exist_ok=True)

WEEKS = 52
CASH = "BIL"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
OFFICIAL_SHADOW = "improved_phase2b_combo_abc"
GGG1 = "improved_phaseggg_confirmed_only_robust_offense"
PHASE2_BEST = "improved_phase2_aggressive_neutral_cash_unlock"
PHASE3_BEST = "improved_phase3_high_breadth_calm_us_offense"
PHASE4_BEST = "improved_phase4_sector_20pct_offense"
PHASE4B_BEST = "improved_phase4b_refined_sector_20pct"

CANDIDATES = [
    "improved_phase5_stock_breadth_neutral_risk_on",
    "improved_phase5_broad_stock_bull_aggressive",
    "improved_phase5_narrow_bull_caution_overlay",
    "improved_phase5_recovery_stock_breadth_rerisk",
    "improved_phase5_stock_breadth_aggression_score",
]

WINDOWS = {
    "full": (None, None),
    "holdout_2016": ("2016-01-01", None),
    "holdout_2020": ("2020-01-01", None),
    "holdout_2021": ("2021-01-01", None),
    "bear_2022": ("2022-01-01", "2022-12-31"),
    "recovery_2023": ("2023-01-01", None),
}

SECTOR_ETFS = {"XLK", "XLF", "XLV", "XLY", "XLP", "XLI", "XLE", "XLU", "XLB", "XLRE", "VNQ", "IYR", "XLC"}
OFFENSE_ETFS = {"SPY", "QQQ", "IWM", "VTV", "VUG", "EFA", "EEM", "VWO", "EWJ", "VEA", *SECTOR_ETFS}
DEFENSIVE_ASSET_CLASSES = {"Bonds", "Commodities", "FX"}

COMMANDS_EXECUTED = [
    "pwd",
    "git status --short",
    "git branch --show-current",
    "git worktree list",
    "find .. -name CLAUDE.md -maxdepth 3",
    "sed -n '1,240p' CLAUDE.md",
    "prerequisite file existence check",
    "Phase 1-4B report and data directory inspection commands",
    "rg -n 'yfinance|constituent|stock|holdings|point-in-time|breadth' scripts data docs",
    "python3 -m py_compile scripts/phase_5_true_stock_breadth_data_upgrade.py",
    "python3 scripts/phase_5_true_stock_breadth_data_upgrade.py",
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


def beta_corr(port: pd.Series, bm: pd.Series) -> tuple[float, float]:
    common = clean_series(port).index.intersection(clean_series(bm).index)
    if len(common) < 8:
        return np.nan, np.nan
    p = pd.to_numeric(port.reindex(common), errors="coerce")
    b = pd.to_numeric(bm.reindex(common), errors="coerce")
    cov = np.cov(p, b)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else np.nan
    return float(beta), float(p.corr(b))


def active_ann_return(port: pd.Series, bm: pd.Series) -> float:
    common = clean_series(port).index.intersection(clean_series(bm).index)
    if len(common) < 8:
        return np.nan
    return ann_return(port.reindex(common)) - ann_return(bm.reindex(common))


def md_table(df: pd.DataFrame, max_rows: int = 12) -> str:
    if df.empty:
        return "_No rows._"
    small = df.head(max_rows).copy()
    try:
        return small.to_markdown(index=False)
    except Exception:
        return "```\n" + small.to_string(index=False) + "\n```"


def classify_liquidity(row: pd.Series) -> bool:
    completeness = float(row.get("Completeness %", 0) or 0)
    weeks = float(row.get("Weeks Available", 0) or 0)
    return bool(completeness >= 80.0 and weeks >= 900)


def classify_bucket(ticker: str, asset_class: str) -> str:
    if ticker == CASH or ticker == "SHY":
        return "cash_or_short_duration"
    if ticker in SECTOR_ETFS:
        return "sector_equity_etf"
    if asset_class in {"Equities", "REITs"}:
        return "equity_etf"
    if asset_class in {"Bonds"}:
        return "defensive_bond_etf"
    if asset_class in {"Commodities", "FX"}:
        return "commodity_or_fx_etf"
    return "other"


def file_summary(path: Path, data_type: str, usable: str, bias: str) -> dict:
    row = {
        "path": str(path.relative_to(ROOT)),
        "data_type": data_type,
        "tickers_or_count": np.nan,
        "start_date": None,
        "end_date": None,
        "coverage": np.nan,
        "missingness": np.nan,
        "usable_for_phase5": usable,
        "survivorship_bias_risk": bias,
    }
    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(path, nrows=2000)
            row["tickers_or_count"] = int(len(df))
            date_col = next((c for c in df.columns if c.lower() in {"date", "datetime"}), None)
            if date_col:
                dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
                if not dates.empty:
                    row["start_date"] = dates.min().date().isoformat()
                    row["end_date"] = dates.max().date().isoformat()
            row["coverage"] = float(df.notna().mean().mean()) if not df.empty else np.nan
            row["missingness"] = float(df.isna().mean().mean()) if not df.empty else np.nan
        elif path.suffix.lower() == ".json":
            obj = json.loads(path.read_text())
            row["tickers_or_count"] = len(obj) if hasattr(obj, "__len__") else np.nan
    except Exception as exc:
        row["usable_for_phase5"] = f"inspection_error: {exc}"
    return row


def discover_stock_like_files() -> list[Path]:
    patterns = ("stock", "stocks", "constitu", "membership", "sp500", "nasdaq", "holdings", "breadth")
    files: list[Path] = []
    for base in [ROOT / "data", ROOT / "docs", ROOT / "scripts"]:
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            rel = str(path.relative_to(ROOT))
            if any(part in rel for part in [".venv/", ".claude/worktrees/", "phase_ppp_latent_factor_discovery", "phase_qqq_deep_feature_interaction_mining"]):
                continue
            name = path.name.lower()
            if any(pat in name for pat in patterns):
                files.append(path)
    return sorted(files)


def forward_return(ret: pd.Series, horizon: int) -> pd.Series:
    return (1.0 + ret).rolling(horizon).apply(np.prod, raw=True).shift(-horizon + 1) - 1.0


def main() -> None:
    print("=== Phase 5 - True Stock Breadth Data Upgrade ===")
    print(f"Output directory: {OUT}")

    weekly_prices = pd.read_csv(HUB / "weekly_prices.csv", index_col="Date", parse_dates=True)
    weekly_prices.index = pd.to_datetime(weekly_prices.index).tz_localize(None)
    weekly_returns = weekly_prices.pct_change()
    daily_prices = pd.read_csv(HUB / "daily_prices.csv", index_col="Date", parse_dates=True)
    daily_prices.index = pd.to_datetime(daily_prices.index).tz_localize(None)
    metadata = pd.read_csv(HUB / "universe_metadata.csv")
    universe = json.loads((HUB / "universe.json").read_text())
    msh = pd.read_csv(L2B / "market_state_history.csv", index_col="Date", parse_dates=True)
    msh.index = pd.to_datetime(msh.index).tz_localize(None)
    msh = msh.reindex(weekly_prices.index).ffill()
    state = msh["market_state"].astype(str)

    return_series = {
        "ggg1": load_return_artifact(L3 / f"portfolio_version_returns_{GGG1}.csv"),
        "phase2_best": load_return_artifact(L3 / f"portfolio_version_returns_{PHASE2_BEST}.csv"),
        "phase3_best": load_return_artifact(L3 / f"portfolio_version_returns_{PHASE3_BEST}.csv"),
        "phase4_best": load_return_artifact(L3 / f"portfolio_version_returns_{PHASE4_BEST}.csv"),
        "phase4b_best": load_return_artifact(L3 / f"portfolio_version_returns_{PHASE4B_BEST}.csv"),
        "prod_pin": load_return_artifact(L3 / f"portfolio_version_returns_{PRODUCTION_PIN}.csv"),
        "official_shadow": load_return_artifact(L3 / f"portfolio_version_returns_{OFFICIAL_SHADOW}.csv"),
        "SPY": weekly_returns["SPY"],
        "QQQ": weekly_returns["QQQ"],
    }
    if (ROOT / "data" / "03_layer2a_strategy_logic" / "strategy_returns_baseline_60_40_proxy.csv").exists():
        sixty = pd.read_csv(ROOT / "data" / "03_layer2a_strategy_logic" / "strategy_returns_baseline_60_40_proxy.csv", parse_dates=["Date"])
        sixty["Date"] = pd.to_datetime(sixty["Date"]).dt.tz_localize(None)
        return_series["bench_60_40"] = pd.to_numeric(sixty.set_index("Date")["net_return"], errors="coerce")

    # ------------------------------------------------------------------
    # PART A - existing ETF and stock-data inventory.
    # ------------------------------------------------------------------
    print("\n=== PART A: existing ETF and stock-data inventory ===")
    meta = metadata.copy()
    meta["bucket"] = [classify_bucket(str(t), str(a)) for t, a in zip(meta["ticker"], meta["asset_class"])]
    meta["liquid_tradable_current_system"] = meta.apply(classify_liquidity, axis=1)
    meta["available_in_weekly_prices"] = meta["ticker"].isin(weekly_prices.columns)
    meta["available_in_daily_prices"] = meta["ticker"].isin(daily_prices.columns)
    etf_rows = []
    for _, row in meta.iterrows():
        ticker = row["ticker"]
        r = weekly_returns[ticker] if ticker in weekly_returns.columns else pd.Series(dtype=float)
        m = calc_metrics(r, ticker)
        beta_spy, corr_spy = beta_corr(r, weekly_returns.get("SPY", pd.Series(dtype=float)))
        etf_rows.append(
            {
                "ticker": ticker,
                "description": row.get("description"),
                "asset_class": row.get("asset_class"),
                "bucket": row["bucket"],
                "start_date": row.get("Start Date"),
                "end_date": row.get("End Date"),
                "weeks_available": row.get("Weeks Available"),
                "weeks_missing": row.get("Weeks Missing"),
                "completeness_pct": row.get("Completeness %"),
                "has_full_2005_2026_history": bool(row.get("Has Full History")),
                "liquid_tradable_current_system": bool(row["liquid_tradable_current_system"]),
                "ann_return": m["ann_return"],
                "ann_vol": m["ann_vol"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "beta_spy": beta_spy,
                "corr_spy": corr_spy,
                "survivorship_bias_risk": "LOW_FOR_ETF_SERIES; ETF existed historically or has explicit missing history",
            }
        )
    etf_inv = pd.DataFrame(etf_rows)
    etf_inv.to_csv(OUT / "phase5_etf_universe_inventory.csv", index=False)

    stock_like_files = discover_stock_like_files()
    stock_data_rows = []
    for path in stock_like_files:
        rel = str(path.relative_to(ROOT))
        lower = rel.lower()
        if "signal_breadth" in lower or "phase_3" in lower or "phase_4" in lower:
            dtype = "etf_breadth_or_prior_phase_breadth"
            usable = "ETF breadth baseline only; not true stock breadth"
            bias = "LOW_ETF_BREADTH_BUT_NOT_STOCK_BREADTH"
        elif "holdings" in lower:
            dtype = "portfolio_or_etf_holdings_artifact"
            usable = "not individual-stock breadth; portfolio diagnostics only"
            bias = "NOT_STOCK_UNIVERSE"
        elif "stock" in lower or "constitu" in lower or "membership" in lower or "sp500" in lower or "nasdaq" in lower:
            dtype = "possible_stock_data"
            usable = "requires manual review"
            bias = "UNKNOWN"
        else:
            dtype = "other_breadth_named_artifact"
            usable = "not true stock breadth"
            bias = "UNKNOWN_OR_NOT_RELEVANT"
        stock_data_rows.append(file_summary(path, dtype, usable, bias))
    stock_data_inv = pd.DataFrame(stock_data_rows)
    if stock_data_inv.empty:
        stock_data_inv = pd.DataFrame(
            [
                {
                    "path": "none_found",
                    "data_type": "individual_stock_prices_or_constituents",
                    "tickers_or_count": 0,
                    "start_date": None,
                    "end_date": None,
                    "coverage": 0.0,
                    "missingness": np.nan,
                    "usable_for_phase5": "NO",
                    "survivorship_bias_risk": "NO_STOCK_DATA_AVAILABLE",
                }
            ]
        )
    stock_data_inv.to_csv(OUT / "phase5_stock_data_inventory.csv", index=False)

    stock_price_like = stock_data_inv[
        stock_data_inv["data_type"].astype(str).eq("possible_stock_data")
        & stock_data_inv["path"].astype(str).str.contains("price|return|daily|weekly", case=False, regex=True)
    ]
    constituent_like = stock_data_inv[
        stock_data_inv["path"].astype(str).str.contains("constitu|membership|sp500|nasdaq", case=False, regex=True)
    ]
    pit_like = stock_data_inv[
        stock_data_inv["path"].astype(str).str.contains("point|pit|membership_history|constituent_history", case=False, regex=True)
    ]
    prior_breadth = stock_data_inv[stock_data_inv["data_type"].astype(str).str.contains("breadth", case=False, na=False)]

    inventory_rows = [
        {
            "item": "total_etfs_in_weekly_return_data",
            "value": int(len(weekly_prices.columns)),
            "evidence": "data/01_data_hub/weekly_prices.csv columns excluding Date",
        },
        {
            "item": "equity_etfs",
            "value": int(meta["asset_class"].isin(["Equities", "REITs"]).sum()),
            "evidence": "universe_metadata.csv asset_class in Equities/REITs",
        },
        {
            "item": "sector_etfs",
            "value": int(meta["ticker"].isin(SECTOR_ETFS).sum()),
            "evidence": ",".join(meta.loc[meta["ticker"].isin(SECTOR_ETFS), "ticker"].tolist()),
        },
        {
            "item": "defensive_cash_bond_commodity_fx_etfs",
            "value": int(meta["asset_class"].isin(DEFENSIVE_ASSET_CLASSES).sum()),
            "evidence": "universe_metadata.csv asset_class in Bonds/Commodities/FX",
        },
        {
            "item": "full_coverage_2005_2026_etfs",
            "value": int(meta["Has Full History"].astype(bool).sum()),
            "evidence": ",".join(meta.loc[meta["Has Full History"].astype(bool), "ticker"].tolist()),
        },
        {
            "item": "liquid_tradable_current_system_etfs",
            "value": int(meta["liquid_tradable_current_system"].sum()),
            "evidence": "Completeness >=80% and >=900 weekly observations",
        },
        {
            "item": "individual_stock_price_files",
            "value": int(len(stock_price_like)),
            "evidence": "No local stock price panel found outside .venv/.claude; daily/weekly panels contain ETF universe only.",
        },
        {
            "item": "stock_constituent_lists",
            "value": int(len(constituent_like)),
            "evidence": "No usable local S&P 500/Nasdaq constituent list found; holdings artifacts are portfolio/ETF diagnostics, not stock universes.",
        },
        {
            "item": "point_in_time_universe_membership",
            "value": int(len(pit_like)),
            "evidence": "No point-in-time stock membership file found.",
        },
        {
            "item": "prior_breadth_files",
            "value": int(len(prior_breadth)),
            "evidence": "Existing breadth is ETF/sector breadth, not true stock breadth.",
        },
    ]
    existing_inv = pd.DataFrame(inventory_rows)
    existing_inv.to_csv(OUT / "phase5_existing_data_inventory.csv", index=False)

    data_gap_rows = [
        {
            "gap": "individual_stock_price_panel",
            "status": "MISSING",
            "impact": "Cannot build true stock-level breadth features locally.",
            "required_upgrade": "Survivorship-controlled daily/weekly adjusted stock prices with delisting handling.",
        },
        {
            "gap": "point_in_time_constituents",
            "status": "MISSING",
            "impact": "Cannot use S&P 500/Nasdaq breadth for production decisions without survivorship bias.",
            "required_upgrade": "PIT index constituent membership by effective date.",
        },
        {
            "gap": "stock_sector_classification_history",
            "status": "MISSING",
            "impact": "Cannot build sector-level stock breadth safely.",
            "required_upgrade": "Current and historical GICS/sector mapping or equivalent.",
        },
        {
            "gap": "stock_weights_or_market_caps",
            "status": "MISSING",
            "impact": "Can only build equal-weight breadth if stock prices and PIT membership are acquired.",
            "required_upgrade": "PIT market caps or index weights for cap-weight breadth.",
        },
        {
            "gap": "existing_yfinance_pattern",
            "status": "PRESENT_FOR_PRICE_DOWNLOADS_ONLY",
            "impact": "Could fetch current-constituent diagnostics, but that would be survivorship-biased and not promotable.",
            "required_upgrade": "Do not use as production evidence unless paired with PIT universe.",
        },
    ]
    data_gap = pd.DataFrame(data_gap_rows)
    data_gap.to_csv(OUT / "phase5_data_gap_report.csv", index=False)

    # ------------------------------------------------------------------
    # PART B - stock breadth data-source audit.
    # ------------------------------------------------------------------
    print("\n=== PART B: stock breadth source audit ===")
    source_rows = [
        {
            "source_option": "Existing repo stock files",
            "available_now": False,
            "implementation_cost": "none if present; unavailable now",
            "survivorship_bias_risk": "N/A because absent",
            "point_in_time_safe": False,
            "can_be_used_for_research_only": False,
            "can_be_used_for_production_decision": False,
            "recommended_use": "Do not build stock breadth; no local stock price/PIT membership source exists.",
        },
        {
            "source_option": "Existing yfinance/data-hub download pattern",
            "available_now": True,
            "implementation_cost": "medium once a stock universe is supplied",
            "survivorship_bias_risk": "HIGH if paired with today's constituents",
            "point_in_time_safe": False,
            "can_be_used_for_research_only": True,
            "can_be_used_for_production_decision": False,
            "recommended_use": "Use only for explicitly labeled current-constituent diagnostics after a universe list is supplied; no promotion.",
        },
        {
            "source_option": "Current S&P 500/Nasdaq constituents",
            "available_now": False,
            "implementation_cost": "medium via external fetch; not local",
            "survivorship_bias_risk": "HIGH",
            "point_in_time_safe": False,
            "can_be_used_for_research_only": True,
            "can_be_used_for_production_decision": False,
            "recommended_use": "Allowed only as SURVIVORSHIP_BIASED_DIAGNOSTIC_ONLY; not used in this run because no local list exists.",
        },
        {
            "source_option": "Point-in-time constituents plus adjusted stock prices",
            "available_now": False,
            "implementation_cost": "high; likely paid/curated data",
            "survivorship_bias_risk": "LOW if delistings and membership dates are included",
            "point_in_time_safe": True,
            "can_be_used_for_research_only": True,
            "can_be_used_for_production_decision": True,
            "recommended_use": "Preferred Phase 5 data upgrade path.",
        },
        {
            "source_option": "ETF/sector breadth fallback",
            "available_now": True,
            "implementation_cost": "already built",
            "survivorship_bias_risk": "LOW for ETF panels but not true stock breadth",
            "point_in_time_safe": True,
            "can_be_used_for_research_only": True,
            "can_be_used_for_production_decision": True,
            "recommended_use": "Use as comparison baseline only; Phase 4B already tested it.",
        },
        {
            "source_option": "External clean breadth series",
            "available_now": False,
            "implementation_cost": "medium/high depending vendor",
            "survivorship_bias_risk": "LOW if vendor supplies historical constituents methodology",
            "point_in_time_safe": True,
            "can_be_used_for_research_only": True,
            "can_be_used_for_production_decision": True,
            "recommended_use": "Acceptable if methodology, revisions, and lag availability are documented.",
        },
    ]
    source_audit = pd.DataFrame(source_rows)
    source_audit.to_csv(OUT / "phase5_stock_breadth_source_audit.csv", index=False)

    survivorship_rows = [
        {
            "risk": "current_constituent_survivorship_bias",
            "severity": "HIGH",
            "description": "Today's index members exclude historical bankruptcies, delistings, removals, and weak firms, overstating historical breadth and trend quality.",
            "mitigation": "Require PIT membership and delisting-aware prices before production decisions.",
        },
        {
            "risk": "lookahead_membership_dates",
            "severity": "HIGH",
            "description": "Using future constituent additions/removals to define past breadth leaks information.",
            "mitigation": "For each week, include only stocks that were members as of that week.",
        },
        {
            "risk": "delisting_return_omission",
            "severity": "HIGH",
            "description": "Ignoring delisted stocks removes adverse outcomes and inflates breadth.",
            "mitigation": "Use a source with delisting returns or explicit dead-stock coverage.",
        },
        {
            "risk": "vendor_revision_or_publication_lag",
            "severity": "MEDIUM",
            "description": "Constituent data may be known only after announcements/effective dates.",
            "mitigation": "Use effective dates and lag signal availability by at least one rebalance period.",
        },
        {
            "risk": "ETF_breadth_substitution",
            "severity": "LOW_FOR_BIAS_HIGH_FOR_SIGNAL_LIMIT",
            "description": "ETF breadth is clean and available, but too coarse to answer true stock breadth questions.",
            "mitigation": "Keep as baseline, not as a substitute for Phase 5 stock breadth.",
        },
    ]
    pd.DataFrame(survivorship_rows).to_csv(OUT / "phase5_survivorship_bias_risk_register.csv", index=False)

    stock_data_available = False
    point_in_time_safe = False
    stock_panel_status = "NOT_BUILT_NO_LOCAL_STOCK_PRICES_OR_POINT_IN_TIME_MEMBERSHIP"

    # ------------------------------------------------------------------
    # PART C - stock breadth panel construction or no-data record.
    # ------------------------------------------------------------------
    print("\n=== PART C: stock breadth panel feasibility ===")
    stock_panel = pd.DataFrame(
        [
            {
                "not_built_reason": stock_panel_status,
                "survivorship_bias_flag": "NO_STOCK_PANEL_BUILT",
                "production_usable": False,
                "research_usable": False,
            }
        ]
    )
    stock_panel.to_csv(OUT / "phase5_stock_breadth_panel.csv", index=False)
    pd.DataFrame(
        [
            {
                "panel_name": "phase5_stock_breadth_panel",
                "status": stock_panel_status,
                "data_source": "none",
                "survivorship_bias_label": "NO_STOCK_PANEL_BUILT",
                "causal_lag_rule": "not_applicable",
                "notes": "No individual-stock price panel or point-in-time membership exists in the repo. Current-constituent data was not fetched.",
            }
        ]
    ).to_csv(OUT / "phase5_stock_breadth_metadata.csv", index=False)
    pd.DataFrame(
        [
            {
                "coverage_item": "stock_universe_count",
                "value": 0,
                "coverage": 0.0,
                "missingness": np.nan,
                "status": stock_panel_status,
            }
        ]
    ).to_csv(OUT / "phase5_stock_breadth_coverage_report.csv", index=False)

    # ------------------------------------------------------------------
    # PART D - market-state classifier audit using available ETF breadth.
    # ------------------------------------------------------------------
    print("\n=== PART D: market-state classifier audit ===")
    breadth_sma = pd.to_numeric(msh.get("breadth_sma_43", np.nan), errors="coerce")
    breadth_26 = pd.to_numeric(msh.get("breadth_26w_mom", np.nan), errors="coerce")
    breadth_chg4 = pd.to_numeric(msh.get("breadth_change_4w", np.nan), errors="coerce")
    market_trend = pd.to_numeric(msh.get("market_trend_positive", 0), errors="coerce").fillna(0).astype(bool)
    canary = pd.to_numeric(msh.get("canary_breadth_default", 0), errors="coerce").fillna(0)
    etf_risk_on = (breadth_sma >= 0.65) & (breadth_26 >= 0.55) & market_trend & (canary >= 0.5)
    etf_chop = (breadth_sma < 0.50) | (breadth_26 < 0.45) | (~market_trend)
    phase4b_signal = pd.DataFrame(index=weekly_prices.index)
    p4b_signal_path = PHASE4B_OUT / "phase4b_refined_sector_signal_panel.csv"
    if p4b_signal_path.exists():
        phase4b_signal = pd.read_csv(p4b_signal_path, index_col=0, parse_dates=True)
        phase4b_signal.index = pd.to_datetime(phase4b_signal.index).tz_localize(None)
        phase4b_signal = phase4b_signal.reindex(weekly_prices.index)

    def split_diag_rows(mask: pd.Series, split: pd.Series, split_name: str) -> list[dict]:
        rows = []
        for active_label, active_mask in [("active", split), ("inactive", ~split)]:
            idx = weekly_prices.index[mask & active_mask]
            if len(idx) == 0:
                continue
            for asset_name in ["SPY", "QQQ", "ggg1", "phase4b_best"]:
                ret = return_series[asset_name].reindex(idx)
                m = calc_metrics(ret, asset_name)
                rows.append(
                    {
                        "split": split_name,
                        "bucket": active_label,
                        "asset_or_portfolio": asset_name,
                        "n_weeks": len(idx),
                        "ann_return": m["ann_return"],
                        "ann_vol": m["ann_vol"],
                        "sharpe": m["sharpe"],
                        "max_drawdown": m["max_drawdown"],
                    }
                )
        return rows

    neutral_mask = state == "neutral_mixed"
    calm_mask = state == "calm_trend"
    recovery_confirmed_mask = state == "recovery_confirmed"
    recovery_fragile_mask = state == "recovery_fragile"
    stress_mask = state == "stressed_panic"
    neutral_diag = pd.DataFrame(split_diag_rows(neutral_mask, etf_risk_on, "ETF breadth risk-on split in neutral_mixed"))
    neutral_diag.to_csv(OUT / "phase5_neutral_split_diagnostics.csv", index=False)
    bull_diag = pd.DataFrame(split_diag_rows(calm_mask | neutral_mask, etf_risk_on, "ETF breadth bull-quality split in calm/neutral"))
    bull_diag.to_csv(OUT / "phase5_bull_quality_diagnostics.csv", index=False)
    recovery_diag = pd.DataFrame(split_diag_rows(recovery_confirmed_mask | recovery_fragile_mask, (breadth_chg4 > 0) & market_trend, "ETF breadth improvement split in recovery states"))
    recovery_diag.to_csv(OUT / "phase5_recovery_rerisk_diagnostics.csv", index=False)

    classifier_rows = [
        {
            "question": "Is stressed_panic classification good enough?",
            "answer": "Yes, based on prior phases and Phase 5 audit. Stressed_panic remains the state that should stay protected; 2022 bear protection was the strategy's validation case.",
            "evidence": f"stressed_panic weeks={int(stress_mask.sum())}; GGG1 stressed ann_return={calc_metrics(return_series['ggg1'].reindex(weekly_prices.index[stress_mask]))['ann_return']:.6f}; SPY stressed ann_return={calc_metrics(return_series['SPY'].reindex(weekly_prices.index[stress_mask]))['ann_return']:.6f}",
            "phase5_action": "Do not weaken stressed_panic.",
        },
        {
            "question": "Are calm_trend weeks truly safe/aggressive?",
            "answer": "Broadly safe, but existing ETF breadth is too coarse. Phase 3/4/4B show calm participation can help, but calm_trend still contains quality differences.",
            "evidence": f"calm_trend weeks={int(calm_mask.sum())}; ETF risk-on coverage in calm={float(etf_risk_on[calm_mask].mean()):.4f}",
            "phase5_action": "Needs true stock breadth for broad-vs-narrow confirmation.",
        },
        {
            "question": "Is neutral_mixed too broad?",
            "answer": "Yes. Neutral_mixed contains high-return risk-on weeks and chop/deteriorating weeks. This is the largest potential classification split.",
            "evidence": f"neutral_mixed weeks={int(neutral_mask.sum())}; ETF risk-on coverage in neutral={float(etf_risk_on[neutral_mask].mean()):.4f}; ETF chop coverage in neutral={float(etf_chop[neutral_mask].mean()):.4f}",
            "phase5_action": "Needs PIT stock breadth to split neutral risk-on versus chop.",
        },
        {
            "question": "Can stock breadth split neutral_mixed into risk-on vs choppy/deteriorating?",
            "answer": "Not with current repo data. ETF breadth suggests the split is important, but true stock breadth cannot be built locally.",
            "evidence": "No individual-stock prices or point-in-time constituent membership found.",
            "phase5_action": "Proceed to point-in-time stock breadth data upgrade.",
        },
        {
            "question": "Can stock breadth distinguish broad bull vs narrow bull?",
            "answer": "Conceptually yes, but not implementable with current data. ETF/sector breadth proxies are the safer fallback and were already tested in Phase 4B.",
            "evidence": "Phase 4B improved return only modestly; ETF sector breadth is too coarse.",
            "phase5_action": "Acquire stock-level breadth before rebuilding classifier.",
        },
        {
            "question": "Can stock breadth identify fake recoveries?",
            "answer": "No local stock data to test. Existing recovery diagnostics can only use ETF breadth improvement and state persistence.",
            "evidence": f"recovery_confirmed weeks={int(recovery_confirmed_mask.sum())}; recovery_fragile weeks={int(recovery_fragile_mask.sum())}",
            "phase5_action": "Use PIT stock breadth to validate recovery re-entry.",
        },
        {
            "question": "Does breadth improve re-risking after stressed_panic?",
            "answer": "ETF breadth gives some signal, but true stock breadth is required to avoid overfitting to ETF proxy behavior.",
            "evidence": "Phase 4B recovery_sector_reentry was useful as sector/ETF signal-active validation, but portfolio effect remained small.",
            "phase5_action": "Do not build Phase 5 portfolio candidates without stock data.",
        },
        {
            "question": "Does breadth explain why sector rotation only partly helped?",
            "answer": "Likely. Sector ETF breadth improved timing but is coarse and cannot see underneath sector/index concentration.",
            "evidence": "Phase 4B best improved Phase 4 best by only about 0.12pp full-period return.",
            "phase5_action": "True stock breadth is the next information source.",
        },
        {
            "question": "Which states should stay unchanged?",
            "answer": "stressed_panic should stay unchanged; recovery_fragile should remain cautious unless separately confirmed.",
            "evidence": "Phase 1-4B repeatedly showed stressed protection is valuable.",
            "phase5_action": "No portfolio build; no stressed_panic changes.",
        },
        {
            "question": "Which states need finer sub-classification?",
            "answer": "neutral_mixed first, then calm_trend broad-vs-narrow bull quality, then recovery_confirmed re-risk quality.",
            "evidence": "These states are where prior phases found opportunity cost or partial sector improvements.",
            "phase5_action": "Use PIT stock breadth as classifier feature set.",
        },
    ]
    classifier_audit = pd.DataFrame(classifier_rows)
    classifier_audit.to_csv(OUT / "phase5_market_state_classifier_audit.csv", index=False)

    # ------------------------------------------------------------------
    # PART E/F - no stock-breadth signals; ETF baseline comparison only.
    # ------------------------------------------------------------------
    print("\n=== PART E/F: stock-breadth signal definitions and validation ===")
    signal_names = [
        "broad_stock_bull_confirmed",
        "narrow_bull_warning",
        "neutral_stock_risk_on",
        "neutral_stock_chop_warning",
        "recovery_stock_confirmed",
        "fake_recovery_warning",
        "broad_vs_narrow_bull_quality_score",
    ]
    signal_defs = []
    for name in signal_names:
        signal_defs.append(
            {
                "signal": name,
                "formula": "NOT_CREATED_NO_STOCK_BREADTH_PANEL",
                "active_weeks": 0,
                "active_frequency": 0.0,
                "active_states": "",
                "lag_rule": "would use week-t stock breadth for week-t+1 returns",
                "causal_ok": True,
                "survivorship_bias_flag": "NO_STOCK_PANEL_BUILT",
                "expected_use": "blocked until PIT stock breadth data exists",
                "economic_interpretation": "Design retained from protocol; not instantiated because local data lacks stock prices and PIT membership.",
            }
        )
    signal_defs_df = pd.DataFrame(signal_defs)
    signal_defs_df.to_csv(OUT / "phase5_stock_breadth_signal_definitions.csv", index=False)
    signal_panel = pd.DataFrame(index=weekly_prices.index)
    for name in signal_names:
        signal_panel[name] = 0.0
    signal_panel["stock_breadth_panel_available"] = 0
    signal_panel["survivorship_bias_flag"] = "NO_STOCK_PANEL_BUILT"
    signal_panel.to_csv(OUT / "phase5_stock_breadth_signal_panel.csv")
    coverage_df = signal_defs_df[["signal", "active_weeks", "active_frequency", "active_states", "survivorship_bias_flag"]].copy()
    coverage_df["reason"] = stock_panel_status
    coverage_df.to_csv(OUT / "phase5_stock_breadth_signal_coverage.csv", index=False)

    validation_rows = []
    horizons = [4, 8, 13]
    etf_baseline_signals = {
        "etf_neutral_risk_on_baseline": etf_risk_on & neutral_mask,
        "etf_broad_bull_baseline": etf_risk_on & (calm_mask | neutral_mask | recovery_confirmed_mask),
        "phase4b_high_quality_sector_bull": pd.to_numeric(phase4b_signal.get("high_quality_sector_bull", 0), errors="coerce").fillna(0).astype(bool)
        if not phase4b_signal.empty
        else pd.Series(False, index=weekly_prices.index),
        "phase4b_sector_quality_score_high": pd.to_numeric(phase4b_signal.get("sector_quality_score_high", 0), errors="coerce").fillna(0).astype(bool)
        if not phase4b_signal.empty
        else pd.Series(False, index=weekly_prices.index),
    }
    for signal_name in signal_names:
        validation_rows.append(
            {
                "signal": signal_name,
                "data_source": "stock_breadth",
                "status": "NOT_VALIDATED_NO_STOCK_BREADTH_PANEL",
                "horizon_weeks": np.nan,
                "asset_or_portfolio": "none",
                "active_weeks": 0,
                "active_forward_return": np.nan,
                "inactive_forward_return": np.nan,
                "hit_rate": np.nan,
                "adverse_event_frequency": np.nan,
                "same_state_lift": np.nan,
                "improves_over_etf_sector_breadth": False,
            }
        )
    for signal_name, active in etf_baseline_signals.items():
        active = active.reindex(weekly_prices.index).fillna(False).astype(bool)
        for horizon in horizons:
            for asset_name in ["SPY", "QQQ", "ggg1", "phase4b_best"]:
                fwd = forward_return(return_series[asset_name].reindex(weekly_prices.index), horizon)
                active_fwd = fwd[active]
                inactive_fwd = fwd[~active]
                validation_rows.append(
                    {
                        "signal": signal_name,
                        "data_source": "ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH",
                        "status": "ETF_BASELINE_ONLY",
                        "horizon_weeks": horizon,
                        "asset_or_portfolio": asset_name,
                        "active_weeks": int(active.sum()),
                        "active_forward_return": float(active_fwd.mean()) if active_fwd.notna().any() else np.nan,
                        "inactive_forward_return": float(inactive_fwd.mean()) if inactive_fwd.notna().any() else np.nan,
                        "hit_rate": float((active_fwd > 0).mean()) if active_fwd.notna().any() else np.nan,
                        "adverse_event_frequency": float((active_fwd < -0.03).mean()) if active_fwd.notna().any() else np.nan,
                        "same_state_lift": np.nan,
                        "improves_over_etf_sector_breadth": False,
                    }
                )
    validation_df = pd.DataFrame(validation_rows)
    validation_df.to_csv(OUT / "phase5_stock_breadth_signal_validation.csv", index=False)

    same_state_rows = []
    for signal_name, active in etf_baseline_signals.items():
        active = active.reindex(weekly_prices.index).fillna(False).astype(bool)
        for st in sorted(state.dropna().unique()):
            mask = state == st
            for asset_name in ["SPY", "QQQ", "ggg1", "phase4b_best"]:
                active_ret = return_series[asset_name].reindex(weekly_prices.index[mask & active])
                inactive_ret = return_series[asset_name].reindex(weekly_prices.index[mask & ~active])
                same_state_rows.append(
                    {
                        "signal": signal_name,
                        "data_source": "ETF_OR_PHASE4B_BASELINE_NOT_STOCK_BREADTH",
                        "state": st,
                        "asset_or_portfolio": asset_name,
                        "active_weeks": int((mask & active).sum()),
                        "inactive_weeks": int((mask & ~active).sum()),
                        "active_ann_return": ann_return(active_ret),
                        "inactive_ann_return": ann_return(inactive_ret),
                        "same_state_active_minus_inactive": ann_return(active_ret) - ann_return(inactive_ret),
                    }
                )
    pd.DataFrame(same_state_rows).to_csv(OUT / "phase5_same_state_signal_lift.csv", index=False)
    comparison_rows = [
        {
            "comparison": "stock_breadth_vs_phase4b_etf_sector_breadth",
            "stock_breadth_available": False,
            "etf_sector_breadth_available": True,
            "result": "NO_STOCK_BREADTH_SIGNAL_TO_COMPARE",
            "conclusion": "Phase 5 cannot demonstrate improvement beyond ETF-sector breadth without PIT stock breadth data.",
        }
    ]
    pd.DataFrame(comparison_rows).to_csv(OUT / "phase5_signal_vs_etf_breadth_comparison.csv", index=False)

    signal_value_positive = False

    # ------------------------------------------------------------------
    # PART G/H - candidate designs and skipped build.
    # ------------------------------------------------------------------
    print("\n=== PART G/H: candidate designs and skipped build ===")
    candidate_designs = [
        {
            "candidate": "improved_phase5_stock_breadth_neutral_risk_on",
            "logic": "Would reduce neutral_mixed BIL only when neutral_stock_risk_on is active.",
            "status": "SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH",
            "reason": stock_panel_status,
        },
        {
            "candidate": "improved_phase5_broad_stock_bull_aggressive",
            "logic": "Would increase offense in calm/neutral/recovery_confirmed when broad_stock_bull_confirmed is active.",
            "status": "SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH",
            "reason": stock_panel_status,
        },
        {
            "candidate": "improved_phase5_narrow_bull_caution_overlay",
            "logic": "Would block over-aggressive SPY/QQQ/sector exposure when narrow_bull_warning is active.",
            "status": "SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH",
            "reason": stock_panel_status,
        },
        {
            "candidate": "improved_phase5_recovery_stock_breadth_rerisk",
            "logic": "Would re-risk recovery_confirmed only with recovery_stock_confirmed and block fake_recovery_warning.",
            "status": "SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH",
            "reason": stock_panel_status,
        },
        {
            "candidate": "improved_phase5_stock_breadth_aggression_score",
            "logic": "Would map a bounded stock breadth quality score into non-stressed offense/cash budgets.",
            "status": "SKIPPED_NO_POINT_IN_TIME_STOCK_BREADTH",
            "reason": stock_panel_status,
        },
    ]
    pd.DataFrame(candidate_designs).to_csv(OUT / "phase5_candidate_designs.csv", index=False)

    # Clear skip artifacts for mandatory downstream checks.
    skip_rows = [{"portfolio": c, "reason": stock_panel_status} for c in CANDIDATES]
    pd.DataFrame(skip_rows).to_csv(OUT / "phase5_candidate_failure_reasons.csv", index=False)

    # ------------------------------------------------------------------
    # PART I/J/K/L - no candidate metrics; save data-only diagnostics.
    # ------------------------------------------------------------------
    print("\n=== PART I/J/K/L: data-only diagnostics and selection ===")
    baseline_rows = []
    for pname, ret in return_series.items():
        for wname, (start, end) in WINDOWS.items():
            ret_slc = ws(ret, start, end)
            row = {"portfolio": pname, "window": wname, **calc_metrics(ret_slc, pname)}
            if pname not in {"SPY", "QQQ", "bench_60_40"}:
                weight_name = {
                    "ggg1": GGG1,
                    "phase2_best": PHASE2_BEST,
                    "phase3_best": PHASE3_BEST,
                    "phase4_best": PHASE4_BEST,
                    "phase4b_best": PHASE4B_BEST,
                    "prod_pin": PRODUCTION_PIN,
                    "official_shadow": OFFICIAL_SHADOW,
                }.get(pname)
                if weight_name:
                    wpath = L3 / f"portfolio_version_weights_{weight_name}.csv"
                    swpath = L3 / f"portfolio_version_sleeve_weights_{weight_name}.csv"
                    if wpath.exists():
                        w = pd.read_csv(wpath, index_col=0, parse_dates=True)
                        w.index = pd.to_datetime(w.index).tz_localize(None)
                        w = ws(w, start, end)
                        row["avg_BIL"] = float(w[CASH].mean()) if CASH in w.columns else np.nan
                        row["avg_SPY"] = float(w["SPY"].mean()) if "SPY" in w.columns else np.nan
                        row["avg_QQQ"] = float(w["QQQ"].mean()) if "QQQ" in w.columns else np.nan
                    if swpath.exists():
                        sw = pd.read_csv(swpath, index_col=0, parse_dates=True)
                        sw.index = pd.to_datetime(sw.index).tz_localize(None)
                        sw = ws(sw, start, end)
                        sector_cols = [c for c in sw.columns if c.startswith("phase4") or c.startswith("phase4b")]
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
                        row["avg_sector_sleeve_exposure"] = float(sw[sector_cols].sum(axis=1).mean()) if sector_cols else 0.0
                        row["avg_offense_exposure"] = float(sw[offense_cols].sum(axis=1).mean()) if offense_cols else np.nan
                        row["avg_defense_exposure"] = float(sw[defense_cols].sum(axis=1).mean()) if defense_cols else np.nan
                        row["avg_cash_exposure"] = float(sw["cash::BIL"].mean()) if "cash::BIL" in sw.columns else np.nan
            row["beta_spy"], row["corr_spy"] = beta_corr(ret_slc, ws(return_series["SPY"], start, end))
            row["beta_qqq"], row["corr_qqq"] = beta_corr(ret_slc, ws(return_series["QQQ"], start, end))
            baseline_rows.append(row)
    baseline_metrics = pd.DataFrame(baseline_rows)
    baseline_metrics.to_csv(OUT / "phase5_candidate_metrics_full.csv", index=False)
    baseline_metrics[baseline_metrics["window"] != "full"].to_csv(OUT / "phase5_candidate_holdout_metrics.csv", index=False)
    baseline_metrics.to_csv(OUT / "phase5_candidate_vs_benchmark_table.csv", index=False)
    baseline_metrics[
        [c for c in ["portfolio", "window", "beta_spy", "corr_spy", "beta_qqq", "corr_qqq"] if c in baseline_metrics.columns]
    ].to_csv(OUT / "phase5_capture_beta_by_window.csv", index=False)

    state_rows = []
    for pname, ret in return_series.items():
        if pname in {"SPY", "QQQ", "bench_60_40"}:
            continue
        for st in sorted(state.dropna().unique()):
            idx = weekly_prices.index[state == st]
            row = {"portfolio": pname, "state": st, **calc_metrics(ret.reindex(idx), pname)}
            state_rows.append(row)
    state_df = pd.DataFrame(state_rows)
    state_df.to_csv(OUT / "phase5_state_summary.csv", index=False)
    pd.DataFrame([{"status": "NO_PHASE5_CANDIDATE_BUILD", "reason": stock_panel_status}]).to_csv(
        OUT / "phase5_state_exposure_summary.csv", index=False
    )
    for fname in [
        "phase5_state_deltas_vs_ggg1.csv",
        "phase5_state_deltas_vs_phase4b_best.csv",
        "phase5_neutral_split_portfolio_diagnostics.csv",
        "phase5_recovery_rerisk_portfolio_diagnostics.csv",
        "phase5_stress_protection_diagnostics.csv",
    ]:
        pd.DataFrame([{"status": "NO_PHASE5_CANDIDATE_BUILD", "reason": stock_panel_status}]).to_csv(OUT / fname, index=False)

    risk_rows = [
        {
            "portfolio": c,
            "status": "NOT_BUILT",
            "return_improvement_from_beta": np.nan,
            "disguised_spy_qqq": False,
            "cash_reduction_too_large": False,
            "stock_breadth_source_survivorship_biased": False,
            "relies_on_diagnostic_only_data": False,
            "max_drawdown_exceeds_mandate": False,
            "stressed_panic_worsens": False,
            "signal_active_windows_improve": False,
            "signal_improves_beyond_etf_sector_breadth": False,
            "reason": stock_panel_status,
        }
        for c in CANDIDATES
    ]
    pd.DataFrame(risk_rows).to_csv(OUT / "phase5_risk_realism_checks.csv", index=False)
    pd.DataFrame(risk_rows).to_csv(OUT / "phase5_hidden_beta_cash_checks.csv", index=False)
    pd.DataFrame(risk_rows).to_csv(OUT / "phase5_2022_bear_check.csv", index=False)
    pd.DataFrame(
        [
            {
                "portfolio": c,
                "stock_breadth_source": "none",
                "survivorship_bias_flag": "NO_STOCK_PANEL_BUILT",
                "point_in_time_safe": False,
                "production_usable": False,
                "research_only_usable": False,
                "candidate_relies_on_survivorship_biased_data": False,
                "reason": stock_panel_status,
            }
            for c in CANDIDATES
        ]
    ).to_csv(OUT / "phase5_survivorship_bias_checks.csv", index=False)
    pd.DataFrame(
        [
            {
                "portfolio": c,
                "signal_active_windows_improve": False,
                "signal_improves_beyond_etf_sector_breadth": False,
                "active_weeks": 0,
                "reason": stock_panel_status,
            }
            for c in CANDIDATES
        ]
    ).to_csv(OUT / "phase5_signal_active_candidate_performance.csv", index=False)

    selection_df = pd.DataFrame(
        [
            {
                "portfolio": c,
                "classification": "DATA_ONLY_NO_PORTFOLIO_BUILD",
                "reason": stock_panel_status,
                "stock_breadth_source": "none",
                "point_in_time_safe": False,
                "survivorship_bias_acceptable": False,
                "candidate_artifacts_built": False,
            }
            for c in CANDIDATES
        ]
    )
    selection_df.to_csv(OUT / "phase5_selection_table.csv", index=False)

    decision = "PROCEED_TO_DATA_UPGRADE_FOR_POINT_IN_TIME_STOCK_BREADTH"
    rationale = "No local individual-stock price panel or point-in-time universe membership exists, so true stock breadth cannot be built without unacceptable survivorship-bias risk."
    next_df = pd.DataFrame(
        [
            {
                "recommendation": decision,
                "best_candidate": "none",
                "rationale": rationale,
                "stock_panel_built": False,
                "portfolio_candidates_built": False,
                "signal_value_positive": signal_value_positive,
            }
        ]
    )
    next_df.to_csv(OUT / "phase5_next_action_recommendation.csv", index=False)
    next_df.rename(columns={"recommendation": "decision"}).to_csv(OUT / "phase5_next_phase_decision.csv", index=False)

    with open(OUT / "phase5_protocol.json", "w") as f:
        json.dump(
            {
                "phase": "phase_5_true_stock_breadth_data_upgrade",
                "date": "2026-05-07",
                "production_pin": PRODUCTION_PIN,
                "official_shadow_pin": OFFICIAL_SHADOW,
                "base_candidate": GGG1,
                "phase4b_best": PHASE4B_BEST,
                "stock_panel_built": False,
                "candidate_builds_run": False,
                "decision": decision,
                "no_pin_changes": True,
                "no_individual_stock_trading": True,
                "no_new_data_downloaded": True,
            },
            f,
            indent=2,
        )

    # ------------------------------------------------------------------
    # PART M - audits skipped.
    # ------------------------------------------------------------------
    pd.DataFrame([{"audit": "none", "candidate": "none", "status": "SKIPPED_NO_PORTFOLIO_QUALIFIER"}]).to_csv(
        OUT / "phase5_audit_results.csv", index=False
    )
    (OUT / "phase5_audit_summary.md").write_text(
        "# Phase 5 Audit Summary\n\nNo candidate qualified as KEEP_AS_AGGRESSIVE_SHADOW or better because no stock-breadth panel was built; audits skipped.\n"
    )

    # ------------------------------------------------------------------
    # PART O - report.
    # ------------------------------------------------------------------
    print("\n=== PART O: report ===")
    full_focus = baseline_metrics[baseline_metrics["window"] == "full"]
    full_cols = [c for c in ["portfolio", "ann_return", "ann_vol", "sharpe", "max_drawdown", "cvar_5", "avg_BIL", "avg_sector_sleeve_exposure", "beta_spy", "corr_spy"] if c in full_focus.columns]
    source_cols = ["source_option", "available_now", "survivorship_bias_risk", "point_in_time_safe", "can_be_used_for_research_only", "can_be_used_for_production_decision", "recommended_use"]
    next_prompt = """Phase 5A Point-in-Time Stock Breadth Data Upgrade prompt outline:
1. Do not change production, official shadow, or GGG1 pins.
2. Add a documented PIT stock universe source: effective-date index constituents, adjusted prices, delisting handling, and sector classifications.
3. Build lagged weekly stock breadth features only from members known as of each week.
4. Validate breadth signals against ETF breadth baselines before any portfolio build.
5. Trade ETFs only; no individual-stock sleeve.
6. Reject promotion if survivorship bias, lookahead, or 2022/stressed protection cannot be controlled."""

    report = f"""# Phase 5 - True Stock Breadth Data Upgrade

**Date:** 2026-05-07
**Type:** Data + strategy research gate. No portfolio candidate was built.
**Production pin:** `{PRODUCTION_PIN}`
**Official shadow pin:** `{OFFICIAL_SHADOW}`
**Base:** `{GGG1}`
**Phase 4B best:** `{PHASE4B_BEST}`

## Commands Executed

```
{chr(10).join(COMMANDS_EXECUTED)}
```

## Files Created / Modified

**Script created:** `scripts/phase_5_true_stock_breadth_data_upgrade.py`

**Output directory:** `{OUT}`

**Report created:** `docs/research/2026-05-07_phase_5_true_stock_breadth_data_upgrade_report.md`

**Build script:** not modified; no Phase 5 portfolio candidates were allowed because no clean stock-breadth source exists locally.

## Phase 1-4B Bottleneck Summary

Phase 1 identified the return ceiling as mandate-driven, especially BIL/cash drag in neutral_mixed and defense drag in calm_trend, while stressed_panic protection worked and should not be weakened.

Phase 2 showed that moving capital into existing offense sleeves was insufficient because those sleeves did not capture US bull-market upside.

Phase 3 improved Sharpe by switching a small offense component to US equity in high-breadth calm states, but the component was too small to move full-period return enough.

Phase 4 and 4B added/refined a larger sector ETF offense sleeve. Phase 4B best reached about 7.76% return and 0.959 Sharpe, but still did not approach the 8.5-9% target.

## ETF Universe Inventory

{md_table(existing_inv, 12)}

{md_table(etf_inv[['ticker','asset_class','bucket','start_date','end_date','completeness_pct','has_full_2005_2026_history','liquid_tradable_current_system']].sort_values(['bucket','ticker']), 40)}

## Stock Data Inventory

No local individual-stock price panel, stock constituent list, or point-in-time universe membership was found outside the existing ETF/research artifacts.

{md_table(stock_data_inv[['path','data_type','usable_for_phase5','survivorship_bias_risk']], 30)}

## Stock Breadth Source Audit

{md_table(source_audit[source_cols], 12)}

## Survivorship-Bias Risk Register

{md_table(pd.DataFrame(survivorship_rows), 12)}

## Stock Breadth Panel Construction

Panel status: `{stock_panel_status}`.

No stock breadth panel was built. Current-constituent stock breadth would be survivorship-biased diagnostic-only and was not fetched in this run.

## Market-State Classifier Audit

{md_table(classifier_audit[['question','answer','phase5_action']], 12)}

## Neutral Mixed ETF-Breadth Fallback Diagnostics

These are comparison baselines, not stock-breadth evidence.

{md_table(neutral_diag, 20)}

## Recovery Rerisk ETF-Breadth Fallback Diagnostics

{md_table(recovery_diag, 20)}

## Stock Breadth Signal Definitions

{md_table(signal_defs_df[['signal','formula','survivorship_bias_flag','expected_use']], 10)}

## Signal Validation Before Portfolio Build

No stock-breadth signal was validated because no stock-breadth panel exists. ETF/Phase 4B baseline validation was saved for comparison only.

{md_table(validation_df.head(24), 24)}

## Candidate Logic / Skip Reasons

{md_table(pd.DataFrame(candidate_designs), 8)}

## Full-Period Baseline Metrics

No Phase 5 candidate metrics exist because no candidate was built. Baseline metrics were saved for context.

{md_table(full_focus[full_cols].sort_values('ann_return', ascending=False), 12)}

## State-By-State Baseline Context

{md_table(state_df[['portfolio','state','ann_return','sharpe','max_drawdown']].sort_values(['state','portfolio']), 30)}

## Risk / Realism / Bias Checks

{md_table(pd.DataFrame(risk_rows), 8)}

## Selection Table

{md_table(selection_df, 8)}

## Audit Results

Audits skipped because no portfolio candidate was built.

{md_table(pd.read_csv(OUT / 'phase5_audit_results.csv'), 8)}

## Final Recommendation

**Recommendation:** `{decision}`

**Best candidate:** `none`

**Rationale:** {rationale}

## Next Phase Prompt Outline

```
{next_prompt}
```

## Resume / Project Story Summary

Phase 5 tested whether true stock breadth could be added as a signal input while continuing to trade ETFs. The answer from the local repo is data-first: the ETF universe is clean and broad enough for the existing system, but there are no individual-stock prices, no constituent lists, and no point-in-time membership. Because current-constituent breadth would be survivorship-biased and non-promotable, Phase 5 stopped before portfolio construction. The correct next move is a point-in-time stock breadth data upgrade, not another ETF-sector threshold pass and not individual-stock trading.
"""
    REPORT.write_text(report)

    print(f"Decision: {decision}")
    print(f"Report: {REPORT}")
    print("Done. No production pins changed. No portfolio candidates built.")


if __name__ == "__main__":
    main()
