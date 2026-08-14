"""Build research-only ETF and sector breadth signals.

The outputs from this script are research candidates only. They are lagged by
one weekly observation before validation and are not connected to production
portfolio logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HORIZONS,
    HUB_DIR,
    SIGNAL_DIR,
    asset_risk_loading,
    ensure_parent,
    evaluate_panel_signal,
    load_market_states,
    load_strong_existing_panels,
    load_universe_metadata,
    load_weekly_prices,
    markdown_table,
    max_redundancy_against,
    panel_from_series,
    read_csv_safe,
    state_conditional_ic_rows,
)


SECTOR_ETFS = ["XLK", "XLF", "XLY", "XLI", "XLE", "XLP", "XLV", "XLU", "XLB", "XLRE", "XLC"]
OFFENSIVE_SECTORS = ["XLK", "XLY", "XLI", "XLF", "XLE", "XLB"]
DEFENSIVE_SECTORS = ["XLP", "XLV", "XLU"]
RISK_ON_BASKET = ["SPY", "QQQ", "IWM", "HYG", "XLY", "XLK"]
DEFENSIVE_BASKET = ["TLT", "IEF", "SHY", "BIL", "XLU", "XLP", "XLV"]


def load_daily_prices(warnings: list[str]) -> pd.DataFrame:
    daily = read_csv_safe(HUB_DIR / "daily_prices.csv", warnings)
    if daily.empty or "Date" not in daily.columns:
        warnings.append("daily_prices.csv missing or lacks Date; daily MA breadth unavailable.")
        return pd.DataFrame()
    daily = daily.copy()
    daily["Date"] = pd.to_datetime(daily["Date"], errors="coerce")
    daily = daily.dropna(subset=["Date"]).sort_values("Date").set_index("Date")
    return daily.apply(pd.to_numeric, errors="coerce")


def available(columns: pd.Index, tickers: list[str], warnings: list[str], label: str) -> list[str]:
    found = [ticker for ticker in tickers if ticker in columns]
    missing = [ticker for ticker in tickers if ticker not in columns]
    if missing:
        warnings.append(f"{label} missing tickers skipped: {', '.join(missing)}")
    if not found:
        warnings.append(f"{label} has no available tickers.")
    return found


def participation_from_prices(prices: pd.DataFrame, tickers: list[str], lookback: int) -> pd.Series:
    subset = prices[tickers].apply(pd.to_numeric, errors="coerce")
    return (subset.pct_change(lookback) > 0).mean(axis=1, skipna=True)


def ma_breadth_from_daily(daily: pd.DataFrame, weekly_index: pd.Index, tickers: list[str], window: int) -> pd.Series:
    subset = daily[tickers].apply(pd.to_numeric, errors="coerce")
    ma = subset.rolling(window=window, min_periods=max(20, window // 2)).mean()
    daily_breadth = (subset > ma).mean(axis=1, skipna=True)
    return daily_breadth.reindex(weekly_index, method="ffill")


def risk_loadings(warnings: list[str]) -> dict[str, float]:
    metadata = load_universe_metadata(warnings)
    return {
        row.ticker: asset_risk_loading(row.ticker, row.asset_class)
        for row in metadata.itertuples(index=False)
    }


def write_signal(
    signal_name: str,
    series: pd.Series,
    loadings: dict[str, float],
    notes: str,
) -> pd.DataFrame:
    panel = panel_from_series(
        series.astype(float),
        signal_name=signal_name,
        loadings=loadings,
        source="data/01_data_hub weekly/daily ETF prices",
        frequency="weekly",
        notes=notes,
    )
    out = SIGNAL_DIR / f"signal_{signal_name}.csv"
    ensure_parent(out)
    panel.to_csv(out, index=False)
    return panel


def classify(row: dict) -> tuple[str, str]:
    reasons: list[str] = []
    if row["min_full_n_dates"] < 156:
        reasons.append("insufficient full-period observations")
    if pd.isna(row["avg_full_mean_ic"]) or row["avg_full_mean_ic"] <= 0:
        reasons.append("full IC not positive")
    if pd.isna(row["avg_holdout_mean_ic"]) or row["avg_holdout_mean_ic"] <= 0:
        reasons.append("holdout IC not positive")
    if pd.notna(row["stressed_panic_mean_ic"]) and row["stressed_panic_mean_ic"] < -0.02:
        reasons.append("stressed_panic damage")
    if pd.notna(row["max_redundancy_vs_strong"]) and row["max_redundancy_vs_strong"] > 0.65:
        reasons.append("high redundancy with existing strong signals")
    if not reasons:
        return "candidate-pass", "Positive full/holdout IC, no large stressed_panic damage, acceptable redundancy."
    if row.get("calm_trend_mean_ic", np.nan) > 0.02 and "stressed_panic damage" in reasons:
        return "promising-if-gated", "; ".join(reasons)
    if "full IC not positive" in reasons and "holdout IC not positive" in reasons:
        return "reject", "; ".join(reasons)
    return "research-only", "; ".join(reasons)


def summarize_signal(
    name: str,
    category: str,
    panel: pd.DataFrame,
    prices: pd.DataFrame,
    states: pd.DataFrame,
    strong_panels: dict[str, pd.DataFrame],
) -> dict:
    eval_rows = evaluate_panel_signal(panel, prices, HORIZONS, min_assets=5)
    state_rows = state_conditional_ic_rows(panel, prices, states, HORIZONS, min_assets=5)
    max_red, red_name = max_redundancy_against(panel, strong_panels)
    calm = state_rows[state_rows["market_state"].eq("calm_trend")] if not state_rows.empty else pd.DataFrame()
    stress = state_rows[state_rows["market_state"].eq("stressed_panic")] if not state_rows.empty else pd.DataFrame()
    row = {
        "signal_name": name,
        "category": category,
        "file": str(SIGNAL_DIR / f"signal_{name}.csv"),
        "avg_full_mean_ic": float(eval_rows["full_mean_ic"].mean()) if not eval_rows.empty else np.nan,
        "avg_holdout_mean_ic": float(eval_rows["holdout_mean_ic"].mean()) if not eval_rows.empty else np.nan,
        "avg_full_nw_tstat": float(eval_rows["full_ic_tstat_nw"].mean()) if not eval_rows.empty else np.nan,
        "avg_holdout_nw_tstat": float(eval_rows["holdout_ic_tstat_nw"].mean()) if not eval_rows.empty else np.nan,
        "min_full_n_dates": int(eval_rows["full_n_dates"].min()) if not eval_rows.empty else 0,
        "min_holdout_n_dates": int(eval_rows["holdout_n_dates"].min()) if not eval_rows.empty else 0,
        "calm_trend_mean_ic": float(calm["mean_ic"].mean()) if not calm.empty else np.nan,
        "stressed_panic_mean_ic": float(stress["mean_ic"].mean()) if not stress.empty else np.nan,
        "tradable_missingness": float(panel["signal_value_tradable"].isna().mean()) if not panel.empty else 1.0,
        "max_redundancy_vs_strong": max_red,
        "most_redundant_existing_signal": red_name,
        "research_only": True,
    }
    verdict, reason = classify(row)
    row["verdict"] = verdict
    row["verdict_reason"] = reason
    return row


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    daily = load_daily_prices(warnings)
    states = load_market_states(warnings)
    strong_panels = load_strong_existing_panels(warnings)
    loadings = risk_loadings(warnings)

    summary_rows: list[dict] = []
    if prices.empty:
        warnings.append("weekly_prices.csv unavailable; no breadth signals built.")
    else:
        tickers = list(prices.columns)
        sector_tickers = available(prices.columns, SECTOR_ETFS, warnings, "sector breadth")
        offensive = available(prices.columns, OFFENSIVE_SECTORS, warnings, "offensive sector breadth")
        defensive = available(prices.columns, DEFENSIVE_SECTORS, warnings, "defensive sector breadth")
        risk_on = available(prices.columns, RISK_ON_BASKET, warnings, "risk-on breadth")
        defense = available(prices.columns, DEFENSIVE_BASKET, warnings, "defensive basket breadth")

        signals: list[tuple[str, str, pd.Series, str]] = []
        if not daily.empty:
            signals.extend(
                [
                    ("bm_etf_above_50d_ma", "ETF breadth", ma_breadth_from_daily(daily, prices.index, tickers, 50), "% ETFs above 50-day moving average."),
                    ("bm_etf_above_200d_ma", "ETF breadth", ma_breadth_from_daily(daily, prices.index, tickers, 200), "% ETFs above 200-day moving average."),
                ]
            )
            if sector_tickers:
                signals.extend(
                    [
                        ("bm_sector_above_50d_ma", "sector breadth", ma_breadth_from_daily(daily, prices.index, sector_tickers, 50), "% available sector ETFs above 50-day moving average."),
                        ("bm_sector_above_200d_ma", "sector breadth", ma_breadth_from_daily(daily, prices.index, sector_tickers, 200), "% available sector ETFs above 200-day moving average."),
                    ]
                )

        signals.extend(
            [
                ("bm_etf_positive_13w_mom", "ETF breadth", participation_from_prices(prices, tickers, 13), "% ETFs with positive 13-week momentum."),
                ("bm_etf_positive_26w_mom", "ETF breadth", participation_from_prices(prices, tickers, 26), "% ETFs with positive 26-week momentum."),
            ]
        )
        if sector_tickers:
            signals.extend(
                [
                    ("bm_sector_positive_13w_mom", "sector breadth", participation_from_prices(prices, sector_tickers, 13), "% available sector ETFs with positive 13-week momentum."),
                    ("bm_sector_positive_26w_mom", "sector breadth", participation_from_prices(prices, sector_tickers, 26), "% available sector ETFs with positive 26-week momentum."),
                ]
            )
        if offensive and defensive:
            off = participation_from_prices(prices, offensive, 13)
            deff = participation_from_prices(prices, defensive, 13)
            signals.append(("bm_offensive_vs_defensive_sector_breadth", "sector breadth", off - deff, "Offensive sector participation minus defensive sector participation."))
        if risk_on:
            risk_on_part = participation_from_prices(prices, risk_on, 13)
            signals.append(("bm_risk_on_participation", "risk-on breadth", risk_on_part, "Participation count across SPY, QQQ, IWM, HYG, XLY, XLK where available."))
            if defense:
                signals.append(("bm_risk_on_minus_defensive_participation", "risk-on breadth", risk_on_part - participation_from_prices(prices, defense, 13), "Risk-on participation minus defensive participation."))
        if {"RSP", "SPY"}.issubset(prices.columns):
            rel = (prices["RSP"] / prices["SPY"]).pct_change(13)
            signals.append(("bm_rsp_spy_relative_momentum", "equal-weight proxy", rel, "RSP/SPY 13-week relative momentum."))
        else:
            warnings.append("RSP absent from weekly_prices.csv; RSP/SPY equal-weight breadth proxy skipped.")

        base_breadth = participation_from_prices(prices, tickers, 13)
        signals.extend(
            [
                ("bm_breadth_change_4w", "breadth thrust", base_breadth.diff(4), "Four-week change in ETF 13-week positive momentum breadth."),
                ("bm_breadth_momentum_13w", "breadth thrust", base_breadth - base_breadth.rolling(13, min_periods=6).mean(), "ETF breadth versus its 13-week average."),
                ("bm_participation_acceleration", "breadth thrust", base_breadth.diff(4) - base_breadth.diff(13), "Short participation acceleration versus longer participation change."),
            ]
        )

        for name, category, series, notes in signals:
            panel = write_signal(name, series.replace([np.inf, -np.inf], np.nan), loadings, notes)
            summary_rows.append(summarize_signal(name, category, panel, prices, states, strong_panels))

    summary = pd.DataFrame(summary_rows)
    out = SIGNAL_DIR / "breadth_signal_summary.csv"
    ensure_parent(out)
    summary.to_csv(out, index=False)

    report_path = DOCS_RESEARCH_DIR / "breadth_signal_report.md"
    report = [
        "# Breadth Signal Report",
        "",
        "Research-only B1 breadth and participation-quality signal build. All signal CSVs include `research_only=True` and a one-week `signal_value_tradable` lag.",
        "",
        f"- Signals built: {len(summary)}",
        f"- Summary CSV: `{out}`",
        "",
        "## Verdicts",
        "",
        markdown_table(
            summary[
                [
                    "signal_name",
                    "category",
                    "verdict",
                    "avg_full_mean_ic",
                    "avg_holdout_mean_ic",
                    "calm_trend_mean_ic",
                    "stressed_panic_mean_ic",
                    "max_redundancy_vs_strong",
                    "verdict_reason",
                ]
            ]
            if not summary.empty
            else summary
        ),
        "",
        "## Strongest Calm Trend Rows",
        "",
        markdown_table(summary.sort_values("calm_trend_mean_ic", ascending=False)[["signal_name", "category", "calm_trend_mean_ic", "avg_holdout_mean_ic", "verdict"]], max_rows=10)
        if not summary.empty
        else "_No rows._",
        "",
        "## Stressed Panic Damage Watch",
        "",
        markdown_table(summary.sort_values("stressed_panic_mean_ic")[["signal_name", "category", "stressed_panic_mean_ic", "avg_full_mean_ic", "verdict"]], max_rows=10)
        if not summary.empty
        else "_No rows._",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {out} rows={len(summary)}")
    print(f"Wrote {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
