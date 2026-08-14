"""Build R2 macro and cross-asset candidate signals.

Research-only outputs. Signals are observed from information available at each
weekly date and written with a one-week lagged `signal_value_tradable` column.
No production portfolio artifacts are read for anything other than benchmark
context, and nothing is promoted.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    HUB_DIR,
    SIGNAL_DIR,
    asset_risk_loading,
    commodity_loading,
    dollar_loading,
    ensure_parent,
    load_universe_metadata,
    load_weekly_prices,
    panel_from_series,
    read_csv_safe,
    robust_z,
)


def align_asof_to_project(raw: pd.DataFrame, project_dates: pd.Index, value_col: str, warnings: list[str], label: str) -> pd.Series:
    if raw.empty or value_col not in raw.columns:
        warnings.append(f"{label}: no raw values available for alignment.")
        return pd.Series(index=project_dates, dtype=float)
    clean = raw[["Date", value_col]].copy()
    clean["Date"] = pd.to_datetime(clean["Date"], errors="coerce")
    clean[value_col] = pd.to_numeric(clean[value_col], errors="coerce")
    clean = clean.dropna(subset=["Date"]).sort_values("Date")
    target = pd.DataFrame({"Date": pd.to_datetime(project_dates)})
    aligned = pd.merge_asof(target, clean, on="Date", direction="backward")
    return pd.Series(aligned[value_col].to_numpy(), index=project_dates, name=value_col)


def fetch_fred_series(series_id: str, warnings: list[str]) -> pd.DataFrame:
    """Fetch a public FRED CSV without requiring a key; fall back cleanly."""

    api_key = os.environ.get("FRED_API_KEY", "")
    if api_key:
        warnings.append(f"{series_id}: FRED_API_KEY detected, but public graph CSV was used to avoid storing credentials.")
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        raw = pd.read_csv(url)
    except Exception as exc:
        warnings.append(f"{series_id}: FRED public CSV fetch failed: {exc}")
        return pd.DataFrame()
    if raw.empty:
        warnings.append(f"{series_id}: FRED public CSV returned no rows.")
        return pd.DataFrame()
    date_col = "DATE" if "DATE" in raw.columns else raw.columns[0]
    value_col = series_id if series_id in raw.columns else raw.columns[-1]
    out = raw[[date_col, value_col]].rename(columns={date_col: "Date", value_col: series_id})
    out[series_id] = pd.to_numeric(out[series_id].replace(".", np.nan), errors="coerce")
    return out


def macro_series_from_existing_or_fred(
    series_id: str,
    project_dates: pd.Index,
    macro_weekly: pd.DataFrame,
    warnings: list[str],
) -> pd.Series:
    if not macro_weekly.empty and series_id in macro_weekly.columns:
        return align_asof_to_project(macro_weekly, project_dates, series_id, warnings, f"macro_weekly:{series_id}")
    raw = fetch_fred_series(series_id, warnings)
    return align_asof_to_project(raw, project_dates, series_id, warnings, f"FRED:{series_id}")


def write_signal(panel: pd.DataFrame, path: Path, warnings: list[str]) -> None:
    ensure_parent(path)
    if panel.empty:
        warnings.append(f"{path}: signal panel was empty; writing empty CSV.")
        panel = pd.DataFrame(
            columns=[
                "Date",
                "Ticker",
                "signal_name",
                "signal_value_observed",
                "signal_value_tradable",
                "source",
                "frequency",
                "lag_periods",
                "research_only",
                "notes",
            ]
        )
    panel.to_csv(path, index=False)
    missing = panel["signal_value_tradable"].isna().mean() if "signal_value_tradable" in panel.columns and len(panel) else np.nan
    print(f"Wrote {path} rows={len(panel)} tradable_missing={missing:.2%}" if pd.notna(missing) else f"Wrote {path} rows={len(panel)}")


def placeholder_signal(signal_name: str, project_dates: pd.Index, loadings: dict[str, float], reason: str) -> pd.DataFrame:
    series = pd.Series(index=project_dates, dtype=float)
    return panel_from_series(
        series,
        signal_name=signal_name,
        loadings=loadings,
        source="missing_or_unavailable",
        frequency="weekly",
        notes=f"Skipped/partial: {reason}",
    )


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    if prices.empty:
        raise SystemExit("weekly_prices.csv is required for R2 macro library construction.")
    project_dates = prices.index
    metadata = load_universe_metadata(warnings)
    risk_loadings = {
        row.ticker: asset_risk_loading(row.ticker, row.asset_class)
        for row in metadata.itertuples(index=False)
        if row.ticker in prices.columns
    }
    macro_weekly = read_csv_safe(HUB_DIR / "macro_weekly.csv", warnings)
    if not macro_weekly.empty and "Date" in macro_weekly.columns:
        macro_weekly["Date"] = pd.to_datetime(macro_weekly["Date"], errors="coerce")

    # Yield curve: prefer T10Y2Y when present; otherwise build DGS10-DGS2.
    t10y2y = macro_series_from_existing_or_fred("T10Y2Y", project_dates, macro_weekly, warnings)
    dgs10 = macro_series_from_existing_or_fred("DGS10", project_dates, macro_weekly, warnings)
    dgs2 = macro_series_from_existing_or_fred("DGS2", project_dates, macro_weekly, warnings)
    slope = t10y2y.copy()
    if slope.notna().sum() < 100 and dgs10.notna().sum() and dgs2.notna().sum():
        slope = dgs10 - dgs2
        warnings.append("Yield curve used DGS10-DGS2 fallback because T10Y2Y coverage was limited.")
    curve_score = robust_z(slope, 156, 52) + 0.5 * robust_z(slope.diff(13), 156, 52)
    if curve_score.notna().sum() < 100:
        reason = "Yield curve series unavailable or insufficient."
        warnings.append(f"r2_yield_curve: {reason}")
        panel = placeholder_signal("r2_yield_curve", project_dates, risk_loadings, reason)
    else:
        panel = panel_from_series(
            curve_score,
            signal_name="r2_yield_curve",
            loadings=risk_loadings,
            source="macro_weekly_or_FRED:T10Y2Y/DGS10/DGS2",
            frequency="weekly, as-of latest available observation",
            notes="Steeper or steepening curve is treated as risk-on using static asset risk loadings.",
        )
    write_signal(panel, SIGNAL_DIR / "signal_r2_yield_curve.csv", warnings)

    # Credit spread: high-yield OAS level and 13-week widening are risk-off.
    hy_oas = macro_series_from_existing_or_fred("BAMLH0A0HYM2", project_dates, macro_weekly, warnings)
    credit_score = -robust_z(hy_oas, 156, 52) - 0.5 * robust_z(hy_oas.diff(13), 156, 52)
    credit_source = "macro_weekly_or_FRED:BAMLH0A0HYM2"
    credit_notes = "Lower/tightening high-yield OAS is treated as risk-on; high/widening OAS is defensive."
    if credit_score.notna().sum() < 100 and {"HYG", "LQD"}.issubset(set(prices.columns)):
        warnings.append("r2_credit_spread: FRED OAS unavailable/insufficient; using HYG/LQD ETF relative-price proxy.")
        hyg_lqd = np.log(prices["HYG"]) - np.log(prices["LQD"])
        credit_score = robust_z(hyg_lqd, 156, 52) + 0.5 * robust_z(hyg_lqd.diff(13), 156, 52)
        credit_source = "weekly_prices.csv:HYG/LQD proxy"
        credit_notes = "HYG/LQD relative strength proxy used because direct OAS data was unavailable or insufficient."
    if credit_score.notna().sum() < 100:
        reason = "Credit spread series and HYG/LQD proxy unavailable or insufficient."
        warnings.append(f"r2_credit_spread: {reason}")
        panel = placeholder_signal("r2_credit_spread", project_dates, risk_loadings, reason)
    else:
        panel = panel_from_series(
            credit_score,
            signal_name="r2_credit_spread",
            loadings=risk_loadings,
            source=credit_source,
            frequency="weekly, as-of latest available observation",
            notes=credit_notes,
        )
    write_signal(panel, SIGNAL_DIR / "signal_r2_credit_spread.csv", warnings)

    # Financial conditions: NFCI lower/easing is risk-on.
    nfci = macro_series_from_existing_or_fred("NFCI", project_dates, macro_weekly, warnings)
    fincond_score = -robust_z(nfci, 156, 52) - 0.5 * robust_z(nfci.diff(13), 156, 52)
    if fincond_score.notna().sum() < 100:
        reason = "NFCI series unavailable or insufficient."
        warnings.append(f"r2_financial_conditions: {reason}")
        panel = placeholder_signal("r2_financial_conditions", project_dates, risk_loadings, reason)
    else:
        panel = panel_from_series(
            fincond_score,
            signal_name="r2_financial_conditions",
            loadings=risk_loadings,
            source="macro_weekly_or_FRED:NFCI",
            frequency="weekly, as-of latest available observation",
            notes="Loose/easing financial conditions are treated as risk-on using static loadings.",
        )
    write_signal(panel, SIGNAL_DIR / "signal_r2_financial_conditions.csv", warnings)

    # Dollar strength from existing UUP prices.
    dollar_loadings = {ticker: dollar_loading(ticker) for ticker in prices.columns}
    if "UUP" not in prices.columns:
        reason = "UUP is absent from weekly_prices.csv."
        warnings.append(f"r2_dollar_strength: {reason}")
        panel = placeholder_signal("r2_dollar_strength", project_dates, dollar_loadings, reason)
    else:
        uup_mom13 = prices["UUP"].pct_change(13)
        uup_mom26 = prices["UUP"].pct_change(26)
        dollar_score = 0.5 * robust_z(uup_mom13, 156, 52) + 0.5 * robust_z(uup_mom26, 156, 52)
        panel = panel_from_series(
            dollar_score,
            signal_name="r2_dollar_strength",
            loadings=dollar_loadings,
            source="weekly_prices.csv:UUP",
            frequency="weekly",
            notes="13w/26w UUP momentum; strong dollar favors UUP/cash and penalizes ex-US/commodity sensitivity.",
        )
    write_signal(panel, SIGNAL_DIR / "signal_r2_dollar_strength.csv", warnings)

    # Commodity/inflation pressure proxy from existing commodity ETFs.
    commodity_tickers = [ticker for ticker in ["PDBC", "USO", "DBA", "SLV"] if ticker in prices.columns]
    commodity_loadings = {ticker: commodity_loading(ticker) for ticker in prices.columns}
    if len(commodity_tickers) < 2:
        reason = "Fewer than two commodity proxy ETFs available."
        warnings.append(f"r2_commodity_regime: {reason}")
        panel = placeholder_signal("r2_commodity_regime", project_dates, commodity_loadings, reason)
    else:
        mom13 = prices[commodity_tickers].pct_change(13).mean(axis=1)
        mom26 = prices[commodity_tickers].pct_change(26).mean(axis=1)
        commodity_score = 0.5 * robust_z(mom13, 156, 52) + 0.5 * robust_z(mom26, 156, 52)
        panel = panel_from_series(
            commodity_score,
            signal_name="r2_commodity_regime",
            loadings=commodity_loadings,
            source=f"weekly_prices.csv:{','.join(commodity_tickers)}",
            frequency="weekly",
            notes="13w/26w commodity basket momentum as an inflation/commodity regime proxy.",
        )
    write_signal(panel, SIGNAL_DIR / "signal_r2_commodity_regime.csv", warnings)

    # Cross-asset divergence: require risk assets and credit/defensive assets to confirm.
    required = {"SPY", "HYG", "TLT", "LQD", "QQQ"}
    if not required.issubset(set(prices.columns)):
        missing = sorted(required.difference(set(prices.columns)))
        reason = f"Missing pair inputs: {missing}"
        warnings.append(f"r2_cross_asset_divergence: {reason}")
        panel = placeholder_signal("r2_cross_asset_divergence", project_dates, risk_loadings, reason)
    else:
        mom = prices[sorted(required)].pct_change(13)
        hyg_lqd = robust_z(mom["HYG"] - mom["LQD"], 156, 52)
        spy_tlt = robust_z(mom["SPY"] - mom["TLT"], 156, 52)
        qqq_tlt = robust_z(mom["QQQ"] - mom["TLT"], 156, 52)
        spy_hyg_gap = robust_z(mom["SPY"] - mom["HYG"], 156, 52).abs()
        divergence_score = pd.concat([hyg_lqd, spy_tlt, qqq_tlt], axis=1).mean(axis=1) - 0.5 * spy_hyg_gap
        panel = panel_from_series(
            divergence_score,
            signal_name="r2_cross_asset_divergence",
            loadings=risk_loadings,
            source="weekly_prices.csv:SPY/HYG/TLT/LQD/QQQ",
            frequency="weekly",
            notes="Risk-on only when equities, credit, and growth confirm; equity-credit disagreement penalizes risk.",
        )
    write_signal(panel, SIGNAL_DIR / "signal_r2_cross_asset_divergence.csv", warnings)

    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
