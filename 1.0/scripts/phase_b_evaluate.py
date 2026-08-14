from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

CONTROL_VERSION = "improved_phase2b_regime_confidence_boost"
PORTFOLIO_VARIANTS = [
    CONTROL_VERSION,
    "improved_phaseb_trend_quality_module",
    "improved_phaseb_confirmation_module",
    "improved_phaseb_trend_quality_refined",
    "improved_phaseb_combo_trend_quality_confirmation",
]
SLEEVE_CANDIDATES = [
    "composite_trend_quality_module",
    "composite_confirmation_aware_momentum",
    "composite_trend_quality_refined",
]
EXISTING_REFERENCE_SLEEVES = [
    "composite_selective_signals",
    "composite_regime_conditioned",
    "dual_momentum_topn",
    "cta_trend_long_only",
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
        "hit_rate": float((pd.Series(return_series, dtype=float) > 0).mean()),
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


def capture_metrics(
    return_series: pd.Series,
    benchmark_series: pd.Series,
    weight_panel: pd.DataFrame,
    market_state_history: pd.DataFrame,
) -> dict[str, float]:
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


def state_summary(return_series: pd.Series, weight_panel: pd.DataFrame, market_state_history: pd.DataFrame, label: str, label_key: str) -> pd.DataFrame:
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
        rows.append(
            {
                label_key: label,
                "market_state": market_state,
                "observations": int(len(group)),
                "ann_return_state": annualized_return(group["net_return"]),
                "ann_vol_state": annualized_vol(group["net_return"]),
                "sharpe_state": annualized_return(group["net_return"]) / annualized_vol(group["net_return"]) if annualized_vol(group["net_return"]) > 0 else np.nan,
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


def main() -> None:
    market_state_history = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index()

    benchmark_returns = read_return_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"]

    sleeve_rows: list[dict[str, float | str]] = []
    sleeve_state_rows: list[pd.DataFrame] = []
    sleeve_corr_rows: list[dict[str, float | str]] = []

    for sleeve_name in SLEEVE_CANDIDATES:
        returns_df = read_return_csv(LAYER2A_DIR / f"strategy_returns_{sleeve_name}.csv")
        positions = read_weight_csv(LAYER2A_DIR / f"strategy_positions_{sleeve_name}.csv")
        metrics = summary_metrics(returns_df["net_return"], returns_df.get("turnover"), positions)
        mix = allocation_mix(positions)
        sleeve_rows.append({"strategy_name": sleeve_name, **metrics, **mix})
        sleeve_state_rows.append(state_summary(returns_df["net_return"], positions, market_state_history, sleeve_name, "strategy_name"))
        for ref in EXISTING_REFERENCE_SLEEVES:
            ref_returns = read_return_csv(LAYER2A_DIR / f"strategy_returns_{ref}.csv")["net_return"]
            aligned = pd.concat([returns_df["net_return"].rename("candidate"), ref_returns.rename("reference")], axis=1).dropna()
            sleeve_corr_rows.append(
                {
                    "candidate_strategy": sleeve_name,
                    "reference_strategy": ref,
                    "return_corr": float(aligned["candidate"].corr(aligned["reference"])) if not aligned.empty else np.nan,
                }
            )

    pd.DataFrame(sleeve_rows).sort_values("sharpe", ascending=False).to_csv(
        LAYER2A_DIR / "phase_b_sleeve_candidate_summary.csv",
        index=False,
    )
    pd.concat(sleeve_state_rows, ignore_index=True).to_csv(
        LAYER2A_DIR / "phase_b_sleeve_state_summary.csv",
        index=False,
    )
    pd.DataFrame(sleeve_corr_rows).to_csv(
        LAYER2A_DIR / "phase_b_sleeve_correlation.csv",
        index=False,
    )

    portfolio_rows: list[dict[str, float | str]] = []
    portfolio_state_rows: list[pd.DataFrame] = []

    for version_name in PORTFOLIO_VARIANTS:
        returns_df = read_return_csv(LAYER3_DIR / f"portfolio_version_returns_{version_name}.csv")
        weight_panel = read_weight_csv(LAYER3_DIR / f"portfolio_version_weights_{version_name}.csv")
        metrics = summary_metrics(returns_df["net_return"], returns_df.get("turnover"), weight_panel)
        mix = allocation_mix(weight_panel)
        capture = capture_metrics(returns_df["net_return"], benchmark_returns, weight_panel, market_state_history)
        holdout = holdout_metrics(returns_df["net_return"], benchmark_returns)
        portfolio_rows.append({"version_name": version_name, **metrics, **capture, **mix, **holdout})
        portfolio_state_rows.append(state_summary(returns_df["net_return"], weight_panel, market_state_history, version_name, "version_name"))

    pd.DataFrame(portfolio_rows).sort_values("version_name").to_csv(
        LAYER3_DIR / "phase_b_portfolio_variant_summary.csv",
        index=False,
    )
    pd.concat(portfolio_state_rows, ignore_index=True).to_csv(
        LAYER3_DIR / "phase_b_portfolio_state_summary.csv",
        index=False,
    )


if __name__ == "__main__":
    main()
