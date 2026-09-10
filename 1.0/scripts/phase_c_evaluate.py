from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CONTROL_VERSION = "improved_phase2b_regime_confidence_boost"
REFERENCE_VARIANTS = [
    CONTROL_VERSION,
    "improved_phaseb_trend_quality_refined",
    "improved_phasec_sleeve_universe_base",
]
PORTFOLIO_VARIANTS = REFERENCE_VARIANTS + [
    "improved_phasec_learned_sleeve_quality",
    "improved_phasec_dynamic_risk_budget",
    "improved_phasec_state_conditioned_map",
    "improved_phasec_combo_learned_state",
]
KEY_PHASEB_SLEEVES = [
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "composite_regime_conditioned",
    "taa_10m_sma",
]
DEFENSIVE_ASSETS = ["IEF", "SHY", "TLT", "TIP", "GLD"]
CASH_PROXY = "BIL"
WEEKS_PER_YEAR = 52


def read_return_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "Date" not in frame.columns:
        first_col = frame.columns[0]
        frame = frame.rename(columns={first_col: "Date"})
    frame["Date"] = pd.to_datetime(frame["Date"]).dt.tz_localize(None)
    return frame.set_index("Date").sort_index()


def read_weight_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index).tz_localize(None)
    return frame.sort_index().fillna(0.0)


def annualized_return(return_series: pd.Series) -> float:
    returns = pd.Series(return_series, dtype=float).dropna()
    if returns.empty:
        return np.nan
    wealth = (1.0 + returns).cumprod()
    return float(wealth.iloc[-1] ** (WEEKS_PER_YEAR / len(returns)) - 1.0)


def annualized_vol(return_series: pd.Series) -> float:
    returns = pd.Series(return_series, dtype=float).dropna()
    if len(returns) < 2:
        return np.nan
    return float(returns.std(ddof=1) * np.sqrt(WEEKS_PER_YEAR))


def conditional_var(return_series: pd.Series, level: float = 0.05) -> float:
    returns = pd.Series(return_series, dtype=float).dropna()
    if returns.empty:
        return np.nan
    cutoff = returns.quantile(level)
    tail = returns[returns <= cutoff]
    return float(tail.mean()) if len(tail) else np.nan


def max_drawdown(return_series: pd.Series) -> float:
    returns = pd.Series(return_series, dtype=float).dropna()
    if returns.empty:
        return np.nan
    wealth = (1.0 + returns).cumprod()
    return float(wealth.div(wealth.cummax()).sub(1.0).min())


def classify_allocations(weight_panel: pd.DataFrame) -> tuple[list[str], list[str]]:
    defensive = [ticker for ticker in DEFENSIVE_ASSETS if ticker in weight_panel.columns and ticker != CASH_PROXY]
    offensive = [ticker for ticker in weight_panel.columns if ticker not in set(defensive + [CASH_PROXY])]
    return offensive, defensive


def summary_metrics(return_series: pd.Series, turnover_series: pd.Series | None, weight_panel: pd.DataFrame) -> dict[str, float]:
    ann_return = annualized_return(return_series)
    ann_vol = annualized_vol(return_series)
    max_dd = max_drawdown(return_series)
    return {
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": ann_return / ann_vol if pd.notna(ann_return) and pd.notna(ann_vol) and ann_vol > 0 else np.nan,
        "max_drawdown": max_dd,
        "calmar": ann_return / abs(max_dd) if pd.notna(ann_return) and pd.notna(max_dd) and max_dd != 0 else np.nan,
        "cvar_5": conditional_var(return_series, level=0.05),
        "turnover": float(pd.Series(turnover_series, dtype=float).mean()) if turnover_series is not None else np.nan,
        "avg_bil": float(weight_panel.get(CASH_PROXY, pd.Series(0.0, index=weight_panel.index)).mean()),
        "avg_spy": float(weight_panel.get("SPY", pd.Series(0.0, index=weight_panel.index)).mean()),
    }


def allocation_mix(weight_panel: pd.DataFrame) -> dict[str, float]:
    offensive_assets, defensive_assets = classify_allocations(weight_panel)
    return {
        "avg_offense": float(weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1).mean()),
        "avg_defense": float(weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1).mean()),
        "avg_cash": float(weight_panel.get(CASH_PROXY, pd.Series(0.0, index=weight_panel.index)).mean()),
    }


def capture_metrics(return_series: pd.Series, benchmark_series: pd.Series, market_state_history: pd.DataFrame) -> dict[str, float]:
    aligned = pd.concat([return_series.rename("portfolio"), benchmark_series.rename("benchmark")], axis=1).dropna()
    positive = aligned["benchmark"] > 0
    negative = aligned["benchmark"] < 0
    market_states = market_state_history.reindex(aligned.index)["market_state"]

    def capture(mask: pd.Series) -> float:
        if not mask.any():
            return np.nan
        bench_sum = aligned.loc[mask, "benchmark"].sum()
        return float(aligned.loc[mask, "portfolio"].sum() / bench_sum) if bench_sum != 0 else np.nan

    return {
        "upside_capture": float(aligned.loc[positive, "portfolio"].mean() / aligned.loc[positive, "benchmark"].mean()) if positive.any() else np.nan,
        "downside_capture": float(aligned.loc[negative, "portfolio"].mean() / aligned.loc[negative, "benchmark"].mean()) if negative.any() else np.nan,
        "recovery_capture": capture(market_states.isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"])),
        "calm_capture": capture(market_states.eq("calm_trend")),
        "recovery_fragile_capture": capture(market_states.eq("recovery_fragile")),
        "recovery_confirmed_capture": capture(market_states.eq("recovery_confirmed")),
        "stress_capture": capture(market_states.eq("stressed_panic")),
    }


def state_summary(return_series: pd.Series, weight_panel: pd.DataFrame, market_state_history: pd.DataFrame, label: str) -> pd.DataFrame:
    joined = pd.DataFrame(
        {
            "net_return": return_series,
            "market_state": market_state_history.reindex(return_series.index)["market_state"],
            "bil_weight": weight_panel.get(CASH_PROXY, pd.Series(0.0, index=weight_panel.index)).reindex(return_series.index).fillna(0.0),
            "spy_weight": weight_panel.get("SPY", pd.Series(0.0, index=weight_panel.index)).reindex(return_series.index).fillna(0.0),
        }
    ).dropna(subset=["market_state"])
    offensive_assets, defensive_assets = classify_allocations(weight_panel)
    joined["offense_weight"] = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1).reindex(joined.index).fillna(0.0)
    joined["defense_weight"] = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1).reindex(joined.index).fillna(0.0)

    rows: list[dict[str, float | str | int]] = []
    for market_state, group in joined.groupby("market_state"):
        state_ret = annualized_return(group["net_return"])
        state_vol = annualized_vol(group["net_return"])
        rows.append(
            {
                "version_name": label,
                "market_state": market_state,
                "observations": int(len(group)),
                "ann_return_state": state_ret,
                "ann_vol_state": state_vol,
                "sharpe_state": state_ret / state_vol if pd.notna(state_ret) and pd.notna(state_vol) and state_vol > 0 else np.nan,
                "avg_bil_state": float(group["bil_weight"].mean()),
                "avg_spy_state": float(group["spy_weight"].mean()),
                "avg_offense_state": float(group["offense_weight"].mean()),
                "avg_defense_state": float(group["defense_weight"].mean()),
                "avg_cash_state": float(group["bil_weight"].mean()),
            }
        )
    return pd.DataFrame(rows)


def holdout_metrics(return_series: pd.Series, benchmark_series: pd.Series, holdout_weeks: int = 104) -> dict[str, float]:
    aligned = pd.concat([return_series.rename("portfolio"), benchmark_series.rename("benchmark")], axis=1).dropna().tail(holdout_weeks)
    if aligned.empty:
        return {"holdout_ann_return": np.nan, "holdout_sharpe": np.nan, "holdout_upside_capture": np.nan}
    ann_return = annualized_return(aligned["portfolio"])
    ann_vol = annualized_vol(aligned["portfolio"])
    positive = aligned["benchmark"] > 0
    upside_capture = aligned.loc[positive, "portfolio"].mean() / aligned.loc[positive, "benchmark"].mean() if positive.any() else np.nan
    return {
        "holdout_ann_return": ann_return,
        "holdout_sharpe": ann_return / ann_vol if ann_vol > 0 else np.nan,
        "holdout_upside_capture": float(upside_capture) if pd.notna(upside_capture) else np.nan,
    }


def sleeve_allocation_summary(sleeve_alloc: pd.DataFrame, market_state_history: pd.DataFrame, version_name: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    overall_rows: list[dict[str, float | str]] = []
    state_rows: list[dict[str, float | str]] = []
    aligned_states = market_state_history.reindex(sleeve_alloc.index)["market_state"]

    for sleeve_name in sleeve_alloc.columns:
        if sleeve_name.startswith("cash::"):
            continue
        overall_rows.append(
            {
                "version_name": version_name,
                "sleeve_name": sleeve_name,
                "avg_weight": float(sleeve_alloc[sleeve_name].mean()),
                "avg_weight_when_active": float(sleeve_alloc.loc[sleeve_alloc[sleeve_name] > 0, sleeve_name].mean()) if (sleeve_alloc[sleeve_name] > 0).any() else 0.0,
            }
        )
        sleeve_state = pd.DataFrame({"weight": sleeve_alloc[sleeve_name], "market_state": aligned_states}).dropna(subset=["market_state"])
        for market_state, group in sleeve_state.groupby("market_state"):
            state_rows.append(
                {
                    "version_name": version_name,
                    "sleeve_name": sleeve_name,
                    "market_state": market_state,
                    "avg_weight_state": float(group["weight"].mean()),
                }
            )
    return pd.DataFrame(overall_rows), pd.DataFrame(state_rows)


def main() -> None:
    market_state_history = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index()

    benchmark_returns = read_return_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"]

    variant_rows: list[dict[str, float | str]] = []
    state_rows: list[pd.DataFrame] = []
    holdout_rows: list[dict[str, float | str]] = []
    sleeve_rows: list[pd.DataFrame] = []
    sleeve_state_rows: list[pd.DataFrame] = []

    for version_name in PORTFOLIO_VARIANTS:
        returns_df = read_return_csv(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")
        weight_panel = read_weight_csv(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")
        sleeve_alloc = read_weight_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version_name}.csv")
        metrics = summary_metrics(returns_df["net_return"], returns_df.get("turnover"), weight_panel)
        capture = capture_metrics(returns_df["net_return"], benchmark_returns, market_state_history)
        mix = allocation_mix(weight_panel)
        holdout = holdout_metrics(returns_df["net_return"], benchmark_returns)
        variant_rows.append({"version_name": version_name, **metrics, **capture, **mix, **holdout})
        holdout_rows.append({"version_name": version_name, **holdout})
        state_rows.append(state_summary(returns_df["net_return"], weight_panel, market_state_history, version_name))
        overall_alloc, state_alloc = sleeve_allocation_summary(sleeve_alloc, market_state_history, version_name)
        sleeve_rows.append(overall_alloc)
        sleeve_state_rows.append(state_alloc)

    variant_summary = pd.DataFrame(variant_rows)
    state_summary_df = pd.concat(state_rows, ignore_index=True)
    sleeve_summary_df = pd.concat(sleeve_rows, ignore_index=True)
    sleeve_state_summary_df = pd.concat(sleeve_state_rows, ignore_index=True)

    key_sleeve_usage = sleeve_summary_df[sleeve_summary_df["sleeve_name"].isin(KEY_PHASEB_SLEEVES)].copy()
    key_sleeve_usage_state = sleeve_state_summary_df[sleeve_state_summary_df["sleeve_name"].isin(KEY_PHASEB_SLEEVES)].copy()

    variant_summary.to_csv(LAYER3_DIR / "phase_c_portfolio_variant_summary.csv", index=False)
    state_summary_df.to_csv(LAYER3_DIR / "phase_c_portfolio_state_summary.csv", index=False)
    sleeve_summary_df.to_csv(LAYER3_DIR / "phase_c_sleeve_allocation_summary.csv", index=False)
    sleeve_state_summary_df.to_csv(LAYER3_DIR / "phase_c_sleeve_allocation_by_state.csv", index=False)
    key_sleeve_usage.to_csv(LAYER3_DIR / "phase_c_key_sleeve_usage_summary.csv", index=False)
    key_sleeve_usage_state.to_csv(LAYER3_DIR / "phase_c_key_sleeve_usage_by_state.csv", index=False)
    pd.DataFrame(holdout_rows).to_csv(LAYER3_DIR / "phase_c_holdout_summary.csv", index=False)

    print("Saved Phase C evaluation artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_c_portfolio_variant_summary.csv",
        "data/05_layer3_portfolio_construction/phase_c_portfolio_state_summary.csv",
        "data/05_layer3_portfolio_construction/phase_c_sleeve_allocation_summary.csv",
        "data/05_layer3_portfolio_construction/phase_c_sleeve_allocation_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_c_key_sleeve_usage_summary.csv",
        "data/05_layer3_portfolio_construction/phase_c_key_sleeve_usage_by_state.csv",
        "data/05_layer3_portfolio_construction/phase_c_holdout_summary.csv",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
