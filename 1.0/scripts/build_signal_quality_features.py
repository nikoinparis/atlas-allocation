"""Build research-only signal quality and environment features.

These features are meant to describe whether the existing signal environment is
supportive, noisy, or deteriorating. They are not allocation rules and are not
connected to production logic.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from renaissance_r1_r4_utils import (
    DOCS_RESEARCH_DIR,
    HORIZONS,
    SIGNAL_DIR,
    asset_risk_loading,
    attach_tradable_lag,
    ensure_parent,
    evaluate_panel_signal,
    load_market_states,
    load_strong_existing_panels,
    load_universe_metadata,
    load_weekly_prices,
    markdown_table,
    max_redundancy_against,
    panel_from_series,
    state_conditional_ic_rows,
)


RISK_ON = ["SPY", "QQQ", "IWM", "HYG", "XLY", "XLK"]
DEFENSIVE = ["TLT", "IEF", "SHY", "BIL", "XLU", "XLP", "XLV"]


def risk_loadings() -> tuple[dict[str, float], list[str]]:
    warnings: list[str] = []
    metadata = load_universe_metadata(warnings)
    return {
        row.ticker: asset_risk_loading(row.ticker, row.asset_class)
        for row in metadata.itertuples(index=False)
    }, warnings


def strong_signal_cube(strong_panels: dict[str, pd.DataFrame]) -> pd.DataFrame:
    pieces: list[pd.Series] = []
    for name, panel in strong_panels.items():
        if panel.empty:
            continue
        indexed = panel.set_index(["Date", "Ticker"])["signal_value_tradable"].rename(name)
        pieces.append(indexed)
    if not pieces:
        return pd.DataFrame()
    return pd.concat(pieces, axis=1).sort_index()


def panel_feature_from_series(signal_name: str, feature: pd.Series, notes: str) -> pd.DataFrame:
    feature = feature.rename("signal_value_observed").reset_index()
    if "Ticker" not in feature.columns:
        return pd.DataFrame()
    feature["signal_name"] = signal_name
    feature["source"] = "existing strong signal panels / weekly ETF prices"
    feature["frequency"] = "weekly"
    feature["lag_periods"] = 1
    feature["research_only"] = True
    feature["notes"] = notes
    return attach_tradable_lag(feature)


def price_trend_quality(prices: pd.DataFrame) -> pd.Series:
    returns = prices.pct_change()
    signed_mom = prices.pct_change(26)
    path = returns.abs().rolling(26, min_periods=13).sum()
    efficiency = signed_mom.abs() / path.replace(0, np.nan)
    quality = np.sign(signed_mom) * efficiency
    quality.index.name = "Date"
    quality.columns.name = "Ticker"
    return quality.stack(dropna=False)


def participation(prices: pd.DataFrame, tickers: list[str], lookback: int = 13) -> pd.Series:
    available = [t for t in tickers if t in prices.columns]
    if not available:
        return pd.Series(index=prices.index, dtype=float)
    return (prices[available].pct_change(lookback) > 0).mean(axis=1, skipna=True)


def scalar_features(prices: pd.DataFrame, states: pd.DataFrame) -> dict[str, tuple[pd.Series, str]]:
    breadth = (prices.pct_change(13) > 0).mean(axis=1, skipna=True)
    risk_on = participation(prices, RISK_ON)
    defensive = participation(prices, DEFENSIVE)
    risk_on_confirmation = risk_on - defensive

    deterioration_parts: list[pd.Series] = []
    deterioration_parts.append((-breadth.diff(4)).rename("breadth_weakening"))
    if "HYG" in prices.columns and "LQD" in prices.columns:
        deterioration_parts.append((-(prices["HYG"] / prices["LQD"]).pct_change(4)).rename("credit_deterioration"))
    if "SPY" in prices.columns:
        deterioration_parts.append((-prices["SPY"].pct_change(13)).rename("market_drawdown_pressure"))
    if not states.empty and "Date" in states.columns:
        states_idx = states.copy()
        states_idx["Date"] = pd.to_datetime(states_idx["Date"], errors="coerce")
        states_idx = states_idx.dropna(subset=["Date"]).set_index("Date")
        if "avg_corr_risk_off_z" in states_idx.columns:
            deterioration_parts.append(pd.to_numeric(states_idx["avg_corr_risk_off_z"], errors="coerce").rename("corr_spike"))
    deterioration = pd.concat(deterioration_parts, axis=1).rank(pct=True).mean(axis=1)

    return {
        "bm_quality_breadth_confirmation": (breadth, "ETF 13-week participation breadth expanded with static risk loadings."),
        "bm_quality_risk_on_confirmation": (risk_on_confirmation, "Risk-on participation minus defensive participation."),
        "bm_quality_deterioration_warning": (-deterioration, "Negative deterioration score so higher values favor risk-on and lower values warn to favor defense."),
    }


def validate_feature(
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
        "calm_trend_mean_ic": float(calm["mean_ic"].mean()) if not calm.empty else np.nan,
        "stressed_panic_mean_ic": float(stress["mean_ic"].mean()) if not stress.empty else np.nan,
        "min_full_n_dates": int(eval_rows["full_n_dates"].min()) if not eval_rows.empty else 0,
        "min_holdout_n_dates": int(eval_rows["holdout_n_dates"].min()) if not eval_rows.empty else 0,
        "max_redundancy_vs_strong": max_red,
        "most_redundant_existing_signal": red_name,
        "tradable_missingness": float(panel["signal_value_tradable"].isna().mean()) if not panel.empty else 1.0,
        "research_only": True,
    }
    reasons: list[str] = []
    if row["avg_full_mean_ic"] <= 0 or pd.isna(row["avg_full_mean_ic"]):
        reasons.append("full IC not positive")
    if row["avg_holdout_mean_ic"] <= 0 or pd.isna(row["avg_holdout_mean_ic"]):
        reasons.append("holdout IC not positive")
    if pd.notna(row["stressed_panic_mean_ic"]) and row["stressed_panic_mean_ic"] < -0.02:
        reasons.append("stressed_panic damage")
    if pd.notna(row["max_redundancy_vs_strong"]) and row["max_redundancy_vs_strong"] > 0.75:
        reasons.append("very high redundancy with existing strong signals")
    if not reasons:
        row["verdict"] = "candidate-pass"
        row["verdict_reason"] = "Positive full/holdout IC and no large stressed_panic damage."
    elif row["calm_trend_mean_ic"] > 0.02 and row["avg_holdout_mean_ic"] > 0:
        row["verdict"] = "promising-if-gated"
        row["verdict_reason"] = "; ".join(reasons)
    elif "full IC not positive" in reasons and "holdout IC not positive" in reasons:
        row["verdict"] = "reject"
        row["verdict_reason"] = "; ".join(reasons)
    else:
        row["verdict"] = "research-only"
        row["verdict_reason"] = "; ".join(reasons)
    return row


def main() -> None:
    warnings: list[str] = []
    prices = load_weekly_prices(warnings)
    states = load_market_states(warnings)
    strong_panels = load_strong_existing_panels(warnings)
    loadings, loading_warnings = risk_loadings()
    warnings.extend(loading_warnings)

    feature_panels: list[pd.DataFrame] = []
    validation_rows: list[dict] = []
    if prices.empty:
        warnings.append("weekly_prices.csv unavailable; signal quality feature build skipped.")
    else:
        cube = strong_signal_cube(strong_panels)
        if cube.empty:
            warnings.append("No strong existing signal panels available; agreement and dispersion features skipped.")
        else:
            agreement = np.sign(cube).mean(axis=1, skipna=True).rename("signal_value_observed")
            dispersion = (-cube.std(axis=1, skipna=True)).rename("signal_value_observed")
            for name, series, notes in [
                ("bm_quality_signal_agreement", agreement, "Mean sign agreement across current strong signal panels; double-lagged for conservatism."),
                ("bm_quality_signal_dispersion", dispersion, "Negative cross-signal dispersion; higher values mean less disagreement."),
            ]:
                panel = panel_feature_from_series(name, series, notes)
                feature_panels.append(panel)
                out = SIGNAL_DIR / f"signal_{name}.csv"
                ensure_parent(out)
                panel.to_csv(out, index=False)
                validation_rows.append(validate_feature(name, "signal quality", panel, prices, states, strong_panels))

        trend_panel = panel_feature_from_series(
            "bm_quality_trend_efficiency",
            price_trend_quality(prices).rename("signal_value_observed"),
            "Signed 26-week trend efficiency: absolute momentum divided by path length, then one-week lagged.",
        )
        feature_panels.append(trend_panel)
        trend_out = SIGNAL_DIR / "signal_bm_quality_trend_efficiency.csv"
        ensure_parent(trend_out)
        trend_panel.to_csv(trend_out, index=False)
        validation_rows.append(validate_feature("bm_quality_trend_efficiency", "trend quality", trend_panel, prices, states, strong_panels))

        for name, (series, notes) in scalar_features(prices, states).items():
            panel = panel_from_series(series, name, loadings, "weekly ETF prices / market state history", "weekly", notes)
            feature_panels.append(panel)
            out = SIGNAL_DIR / f"signal_{name}.csv"
            ensure_parent(out)
            panel.to_csv(out, index=False)
            validation_rows.append(validate_feature(name, "signal environment", panel, prices, states, strong_panels))

    combined = pd.concat(feature_panels, ignore_index=True) if feature_panels else pd.DataFrame()
    combined_out = SIGNAL_DIR / "signal_quality_features.csv"
    ensure_parent(combined_out)
    combined.to_csv(combined_out, index=False)

    validation = pd.DataFrame(validation_rows)
    validation_out = SIGNAL_DIR / "signal_quality_feature_validation.csv"
    validation.to_csv(validation_out, index=False)

    report_path = DOCS_RESEARCH_DIR / "signal_quality_report.md"
    report = [
        "# Signal Quality Report",
        "",
        "Research-only B3 build of signal environment and trend-quality features. Feature CSVs are lagged by one week before validation.",
        "",
        f"- Combined feature CSV: `{combined_out}`",
        f"- Validation CSV: `{validation_out}`",
        f"- Features built: {len(validation)}",
        "",
        "## Feature Validation",
        "",
        markdown_table(
            validation[
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
            if not validation.empty
            else validation
        ),
        "",
        "## Best Calm Trend Features",
        "",
        markdown_table(validation.sort_values("calm_trend_mean_ic", ascending=False)[["signal_name", "calm_trend_mean_ic", "avg_holdout_mean_ic", "verdict"]], max_rows=10)
        if not validation.empty
        else "_No rows._",
        "",
        "## Deterioration And Disagreement Notes",
        "",
        "- `bm_quality_deterioration_warning` is signed so lower/negative readings represent weakening participation, credit pressure, equity weakness, or correlation stress.",
        "- `bm_quality_signal_dispersion` is signed so higher values indicate lower disagreement among strong signals.",
        "- These are features for future gating/ranking research, not portfolio rules.",
        "",
        "## Warnings",
        "",
    ]
    report.extend([f"- {warning}" for warning in warnings] or ["- None."])
    report_path.write_text("\n".join(report) + "\n")

    print(f"Wrote {combined_out} rows={len(combined)}")
    print(f"Wrote {validation_out} rows={len(validation)}")
    print(f"Wrote {report_path}")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
