from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

PRODUCTION_PIN = "improved_phase2b_regime_confidence_boost"
SHADOW_PIN = "improved_phase2b_combo_abc"
PHASEC_SLEEVE_REFERENCE = "improved_phasec_sleeve_universe_base"
PHASEC_ALLOCATOR_REFERENCE = "improved_phasec_state_conditioned_map"

COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEC_SLEEVE_REFERENCE,
    PHASEC_ALLOCATOR_REFERENCE,
]

WEEKS_PER_YEAR = 52
HOLDOUT_WEEKS = 104
ROLLING_MIN_TRAIN_WEEKS = 260
ROLLING_TEST_WEEKS = 104
ROLLING_STEP_WEEKS = 52
BOOTSTRAP_BLOCK_WEEKS = 13
BOOTSTRAP_SAMPLES = 2000

RAW_COMPOSITE_WEIGHTS = {
    "ann_return": 0.14,
    "sharpe": 0.22,
    "calmar": 0.14,
    "max_drawdown": 0.12,
    "cvar_5": 0.10,
    "upside_capture": 0.08,
    "recovery_capture": 0.08,
    "turnover": 0.05,
    "avg_bil": 0.07,
}


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


def summary_metrics(
    return_series: pd.Series,
    weight_panel: pd.DataFrame,
    benchmark_returns: pd.Series,
    turnover_series: pd.Series | None = None,
) -> dict[str, float]:
    ann_return = annualized_return(return_series)
    ann_vol = annualized_vol(return_series)
    max_dd = max_drawdown(return_series)
    aligned = pd.concat([return_series.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    positive = aligned["benchmark"] > 0
    negative = aligned["benchmark"] < 0

    return {
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": ann_return / ann_vol if pd.notna(ann_return) and pd.notna(ann_vol) and ann_vol > 0 else np.nan,
        "max_drawdown": max_dd,
        "calmar": ann_return / abs(max_dd) if pd.notna(ann_return) and pd.notna(max_dd) and max_dd != 0 else np.nan,
        "cvar_5": conditional_var(return_series, level=0.05),
        "turnover": float(pd.Series(turnover_series, dtype=float).dropna().mean()) if turnover_series is not None else np.nan,
        "upside_capture": float(aligned.loc[positive, "portfolio"].mean() / aligned.loc[positive, "benchmark"].mean()) if positive.any() else np.nan,
        "downside_capture": float(aligned.loc[negative, "portfolio"].mean() / aligned.loc[negative, "benchmark"].mean()) if negative.any() else np.nan,
        "avg_bil": float(weight_panel.get("BIL", pd.Series(0.0, index=weight_panel.index)).mean()),
        "avg_spy": float(weight_panel.get("SPY", pd.Series(0.0, index=weight_panel.index)).mean()),
        "avg_offense": float(weight_panel.drop(columns=[c for c in ["BIL", "IEF", "SHY", "TLT", "TIP", "GLD"] if c in weight_panel.columns], errors="ignore").sum(axis=1).mean()),
        "avg_defense": float(weight_panel.reindex(columns=[c for c in ["IEF", "SHY", "TLT", "TIP", "GLD"] if c in weight_panel.columns], fill_value=0.0).sum(axis=1).mean()),
        "avg_cash": float(weight_panel.get("BIL", pd.Series(0.0, index=weight_panel.index)).mean()),
    }


def recovery_capture(return_series: pd.Series, benchmark_returns: pd.Series, market_state_history: pd.DataFrame) -> float:
    aligned = pd.concat(
        [
            return_series.rename("portfolio"),
            benchmark_returns.rename("benchmark"),
            market_state_history.reindex(return_series.index)["market_state"].rename("market_state"),
        ],
        axis=1,
    ).dropna()
    mask = aligned["market_state"].isin(["recovery_rebound", "recovery_fragile", "recovery_confirmed"])
    if not mask.any():
        return np.nan
    bench_sum = aligned.loc[mask, "benchmark"].sum()
    return float(aligned.loc[mask, "portfolio"].sum() / bench_sum) if bench_sum != 0 else np.nan


def bounded_score_higher(value: float, floor: float, target: float) -> float:
    if pd.isna(value):
        return np.nan
    return float(np.clip((value - floor) / (target - floor), 0.0, 1.0))


def bounded_score_lower(value: float, best: float, worst: float) -> float:
    if pd.isna(value):
        return np.nan
    return float(np.clip((worst - value) / (worst - best), 0.0, 1.0))


def raw_metric_composite(row: pd.Series) -> float:
    scores = {
        "ann_return": bounded_score_higher(float(row["ann_return"]), 0.05, 0.09),
        "sharpe": bounded_score_higher(float(row["sharpe"]), 0.60, 1.05),
        "calmar": bounded_score_higher(float(row["calmar"]), 0.30, 0.70),
        "max_drawdown": bounded_score_lower(abs(float(row["max_drawdown"])), 0.10, 0.18),
        "cvar_5": bounded_score_lower(abs(float(row["cvar_5"])), 0.022, 0.035),
        "upside_capture": bounded_score_higher(float(row["upside_capture"]), 0.30, 0.45),
        "recovery_capture": bounded_score_higher(float(row["recovery_capture"]), 0.30, 0.45),
        "turnover": bounded_score_lower(float(row["turnover"]), 0.04, 0.08),
        "avg_bil": bounded_score_lower(float(row["avg_bil"]), 0.20, 0.35),
    }
    total = 0.0
    for key, weight in RAW_COMPOSITE_WEIGHTS.items():
        score = scores[key]
        total += weight * (0.0 if pd.isna(score) else score)
    return float(total)


def fixed_rank_composite(df: pd.DataFrame) -> pd.Series:
    def rank_score(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
        values = pd.Series(series, dtype=float)
        if not higher_is_better:
            values = -values
        return values.rank(pct=True, method="average")

    return (
        0.22 * rank_score(df["sharpe"], True)
        + 0.16 * rank_score(df["calmar"], True)
        + 0.14 * rank_score(df["max_drawdown"].abs(), False)
        + 0.10 * rank_score(df["cvar_5"].abs(), False)
        + 0.12 * rank_score(df["upside_capture"], True)
        + 0.10 * rank_score(df["recovery_capture"], True)
        + 0.08 * rank_score(df["avg_bil"], False)
        + 0.08 * rank_score(df["turnover"], False)
    )


def split_dev_holdout(return_series: pd.Series, weight_panel: pd.DataFrame, holdout_weeks: int) -> tuple[pd.Series, pd.Series, pd.DataFrame, pd.DataFrame]:
    returns = return_series.dropna()
    holdout_index = returns.tail(holdout_weeks).index
    dev_index = returns.index.difference(holdout_index)
    return (
        returns.reindex(dev_index),
        returns.reindex(holdout_index),
        weight_panel.reindex(dev_index).fillna(0.0),
        weight_panel.reindex(holdout_index).fillna(0.0),
    )


def moving_block_bootstrap_prob(diff_series: pd.Series, block_len: int = BOOTSTRAP_BLOCK_WEEKS, n_boot: int = BOOTSTRAP_SAMPLES, seed: int = 42) -> float:
    diff = pd.Series(diff_series, dtype=float).dropna().to_numpy()
    if len(diff) < max(block_len, 8):
        return np.nan
    rng = np.random.default_rng(seed)
    max_start = len(diff) - block_len
    samples = []
    for _ in range(n_boot):
        resampled: list[float] = []
        while len(resampled) < len(diff):
            start = int(rng.integers(0, max_start + 1))
            resampled.extend(diff[start : start + block_len].tolist())
        sample = np.asarray(resampled[: len(diff)], dtype=float)
        samples.append(sample.mean())
    return float(np.mean(np.asarray(samples) > 0.0))


def rolling_origin_windows(index: pd.Index, min_train_weeks: int, test_weeks: int, step_weeks: int) -> list[tuple[pd.Index, pd.Index]]:
    windows: list[tuple[pd.Index, pd.Index]] = []
    for start in range(min_train_weeks, len(index) - test_weeks + 1, step_weeks):
        train_index = index[:start]
        test_index = index[start : start + test_weeks]
        if len(train_index) >= min_train_weeks and len(test_index) == test_weeks:
            windows.append((train_index, test_index))
    return windows


def compute_candidate_frames() -> tuple[dict[str, pd.Series], dict[str, pd.DataFrame], dict[str, pd.Series], pd.Series, pd.DataFrame]:
    benchmark_returns = read_return_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"]
    market_state_history = pd.read_csv(ROOT / "data" / "04_layer2b_risk_regime_engine" / "market_state_history.csv", parse_dates=["Date"])
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index()

    returns_map: dict[str, pd.Series] = {}
    weights_map: dict[str, pd.DataFrame] = {}
    turnover_map: dict[str, pd.Series] = {}
    common_index: pd.Index | None = None

    for name in COMPARATOR_SET:
        returns_df = read_return_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        weights_df = read_weight_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        returns_map[name] = returns_df["net_return"]
        turnover_map[name] = returns_df["turnover"] if "turnover" in returns_df.columns else pd.Series(dtype=float)
        weights_map[name] = weights_df
        common_index = returns_df.index if common_index is None else common_index.intersection(returns_df.index)

    assert common_index is not None
    common_index = common_index.intersection(benchmark_returns.index)
    for name in COMPARATOR_SET:
        returns_map[name] = returns_map[name].reindex(common_index).dropna()
        aligned_index = returns_map[name].index
        weights_map[name] = weights_map[name].reindex(aligned_index).fillna(0.0)
        turnover_map[name] = turnover_map[name].reindex(aligned_index)
    benchmark_returns = benchmark_returns.reindex(common_index).dropna()
    return returns_map, weights_map, turnover_map, benchmark_returns, market_state_history


def main() -> None:
    returns_map, weights_map, turnover_map, benchmark_returns, market_state_history = compute_candidate_frames()

    full_rows: list[dict[str, float | str]] = []
    dev_rows: list[dict[str, float | str]] = []
    holdout_rows: list[dict[str, float | str]] = []

    for name in COMPARATOR_SET:
        full_metrics = summary_metrics(returns_map[name], weights_map[name], benchmark_returns, turnover_map[name])
        full_metrics["recovery_capture"] = recovery_capture(returns_map[name], benchmark_returns, market_state_history)
        full_rows.append({"version_name": name, **full_metrics})

        dev_ret, holdout_ret, dev_w, holdout_w = split_dev_holdout(returns_map[name], weights_map[name], HOLDOUT_WEEKS)
        dev_turnover = turnover_map[name].reindex(dev_ret.index)
        holdout_turnover = turnover_map[name].reindex(holdout_ret.index)
        benchmark_dev = benchmark_returns.reindex(dev_ret.index)
        benchmark_holdout = benchmark_returns.reindex(holdout_ret.index)

        dev_metrics = summary_metrics(dev_ret, dev_w, benchmark_dev, dev_turnover)
        dev_metrics["recovery_capture"] = recovery_capture(dev_ret, benchmark_dev, market_state_history)
        dev_rows.append({"version_name": name, **dev_metrics})

        holdout_metrics = summary_metrics(holdout_ret, holdout_w, benchmark_holdout, holdout_turnover)
        holdout_metrics["recovery_capture"] = recovery_capture(holdout_ret, benchmark_holdout, market_state_history)
        holdout_rows.append({"version_name": name, **holdout_metrics})

    full_df = pd.DataFrame(full_rows)
    dev_df = pd.DataFrame(dev_rows)
    holdout_df = pd.DataFrame(holdout_rows)

    for df in [full_df, dev_df, holdout_df]:
        df["raw_target_composite"] = df.apply(raw_metric_composite, axis=1)
        df["fixed_rank_composite"] = fixed_rank_composite(df)
        df["fixed_rank_position"] = df["fixed_rank_composite"].rank(ascending=False, method="min").astype(int)
        df["raw_composite_position"] = df["raw_target_composite"].rank(ascending=False, method="min").astype(int)

    windows = rolling_origin_windows(benchmark_returns.index, ROLLING_MIN_TRAIN_WEEKS, ROLLING_TEST_WEEKS, ROLLING_STEP_WEEKS)
    rolling_rows: list[dict[str, float | str | int]] = []
    pairwise_rows: list[dict[str, float | str | int]] = []

    for name in COMPARATOR_SET:
        test_composites: list[float] = []
        test_sharpes: list[float] = []
        test_returns: list[float] = []
        for _, test_index in windows:
            candidate_ret = returns_map[name].reindex(test_index).dropna()
            if len(candidate_ret) != len(test_index):
                continue
            candidate_w = weights_map[name].reindex(test_index).fillna(0.0)
            bench = benchmark_returns.reindex(test_index)
            turnover = turnover_map[name].reindex(candidate_ret.index)
            metrics = summary_metrics(candidate_ret, candidate_w, bench, turnover)
            metrics["recovery_capture"] = recovery_capture(candidate_ret, bench, market_state_history)
            test_composites.append(raw_metric_composite(pd.Series(metrics)))
            test_sharpes.append(metrics["sharpe"])
            test_returns.append(metrics["ann_return"])
        rolling_rows.append(
            {
                "version_name": name,
                "rolling_windows": int(len(test_composites)),
                "rolling_avg_raw_composite": float(np.nanmean(test_composites)) if len(test_composites) else np.nan,
                "rolling_median_raw_composite": float(np.nanmedian(test_composites)) if len(test_composites) else np.nan,
                "rolling_avg_sharpe": float(np.nanmean(test_sharpes)) if len(test_sharpes) else np.nan,
                "rolling_avg_ann_return": float(np.nanmean(test_returns)) if len(test_returns) else np.nan,
            }
        )

    production_holdout = returns_map[PRODUCTION_PIN].tail(HOLDOUT_WEEKS)
    production_full = full_df.set_index("version_name").loc[PRODUCTION_PIN]
    production_holdout_metrics = holdout_df.set_index("version_name").loc[PRODUCTION_PIN]

    for name in COMPARATOR_SET:
        if name == PRODUCTION_PIN:
            continue
        candidate_holdout = returns_map[name].reindex(production_holdout.index).dropna()
        diff = candidate_holdout - production_holdout.reindex(candidate_holdout.index)
        bootstrap_prob = moving_block_bootstrap_prob(diff)

        wins = 0
        comparable = 0
        raw_deltas: list[float] = []
        sharpe_deltas: list[float] = []
        return_deltas: list[float] = []
        dd_deltas: list[float] = []
        cvar_deltas: list[float] = []
        for _, test_index in windows:
            cand_ret = returns_map[name].reindex(test_index).dropna()
            prod_ret = returns_map[PRODUCTION_PIN].reindex(test_index).dropna()
            if len(cand_ret) != len(test_index) or len(prod_ret) != len(test_index):
                continue
            cand_w = weights_map[name].reindex(test_index).fillna(0.0)
            prod_w = weights_map[PRODUCTION_PIN].reindex(test_index).fillna(0.0)
            bench = benchmark_returns.reindex(test_index)
            cand_metrics = summary_metrics(cand_ret, cand_w, bench, turnover_map[name].reindex(cand_ret.index))
            prod_metrics = summary_metrics(prod_ret, prod_w, bench, turnover_map[PRODUCTION_PIN].reindex(prod_ret.index))
            cand_metrics["recovery_capture"] = recovery_capture(cand_ret, bench, market_state_history)
            prod_metrics["recovery_capture"] = recovery_capture(prod_ret, bench, market_state_history)
            cand_comp = raw_metric_composite(pd.Series(cand_metrics))
            prod_comp = raw_metric_composite(pd.Series(prod_metrics))
            raw_delta = cand_comp - prod_comp
            raw_deltas.append(raw_delta)
            sharpe_deltas.append(cand_metrics["sharpe"] - prod_metrics["sharpe"])
            return_deltas.append(cand_metrics["ann_return"] - prod_metrics["ann_return"])
            dd_deltas.append(cand_metrics["max_drawdown"] - prod_metrics["max_drawdown"])
            cvar_deltas.append(cand_metrics["cvar_5"] - prod_metrics["cvar_5"])
            comparable += 1
            if raw_delta > 0:
                wins += 1
        pairwise_rows.append(
            {
                "version_name": name,
                "vs_version": PRODUCTION_PIN,
                "full_raw_delta_vs_production": float(full_df.set_index("version_name").loc[name, "raw_target_composite"] - production_full["raw_target_composite"]),
                "holdout_raw_delta_vs_production": float(holdout_df.set_index("version_name").loc[name, "raw_target_composite"] - production_holdout_metrics["raw_target_composite"]),
                "holdout_sharpe_delta_vs_production": float(holdout_df.set_index("version_name").loc[name, "sharpe"] - production_holdout_metrics["sharpe"]),
                "holdout_bootstrap_prob_excess_return": bootstrap_prob,
                "rolling_windows": int(comparable),
                "rolling_raw_win_rate_vs_production": float(wins / comparable) if comparable else np.nan,
                "rolling_mean_raw_delta_vs_production": float(np.nanmean(raw_deltas)) if raw_deltas else np.nan,
                "rolling_mean_sharpe_delta_vs_production": float(np.nanmean(sharpe_deltas)) if sharpe_deltas else np.nan,
                "rolling_mean_ann_return_delta_vs_production": float(np.nanmean(return_deltas)) if return_deltas else np.nan,
                "rolling_mean_max_drawdown_delta_vs_production": float(np.nanmean(dd_deltas)) if dd_deltas else np.nan,
                "rolling_mean_cvar_delta_vs_production": float(np.nanmean(cvar_deltas)) if cvar_deltas else np.nan,
            }
        )

    pairwise_df = pd.DataFrame(pairwise_rows)
    rolling_df = pd.DataFrame(rolling_rows)

    protocol = {
        "fixed_comparator_set": COMPARATOR_SET,
        "production_pin": PRODUCTION_PIN,
        "shadow_pin": SHADOW_PIN,
        "holdout_rule": {
            "default_holdout_weeks": HOLDOUT_WEEKS,
            "default_holdout_description": "trailing 104 weekly observations",
            "development_sample": "all observations before the default holdout",
        },
        "rolling_origin_rule": {
            "min_train_weeks": ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": ROLLING_TEST_WEEKS,
            "step_weeks": ROLLING_STEP_WEEKS,
        },
        "bootstrap_rule": {
            "method": "moving_block_bootstrap",
            "block_weeks": BOOTSTRAP_BLOCK_WEEKS,
            "samples": BOOTSTRAP_SAMPLES,
        },
        "raw_metric_composite_weights": RAW_COMPOSITE_WEIGHTS,
        "future_promotion_rule": {
            "production_pin": {
                "full_raw_composite_delta_vs_production_min": 0.015,
                "holdout_raw_composite_delta_vs_production_min": 0.0,
                "holdout_sharpe_delta_vs_production_min": -0.02,
                "rolling_raw_win_rate_vs_production_min": 0.55,
                "rolling_mean_raw_delta_vs_production_min": 0.0,
                "holdout_bootstrap_prob_excess_return_min": 0.60,
                "max_drawdown_worsening_cap": -0.010,
                "cvar_worsening_cap": -0.002,
            },
            "shadow_pin": {
                "best_non_production_candidate": True,
                "holdout_raw_composite_delta_vs_production_min": -0.01,
                "rolling_raw_win_rate_vs_production_min": 0.45,
                "holdout_bootstrap_prob_excess_return_min": 0.50,
                "max_drawdown_worsening_cap": -0.015,
                "cvar_worsening_cap": -0.0025,
            },
        },
    }

    full_df.to_csv(LAYER3_DIR / "phase_d_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_d_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_d_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_d_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_d_pairwise_vs_production.csv", index=False)
    (LAYER3_DIR / "phase_d_validation_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase D validation artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_d_candidate_metrics_full.csv",
        "data/05_layer3_portfolio_construction/phase_d_candidate_metrics_dev.csv",
        "data/05_layer3_portfolio_construction/phase_d_candidate_metrics_holdout.csv",
        "data/05_layer3_portfolio_construction/phase_d_rolling_origin_summary.csv",
        "data/05_layer3_portfolio_construction/phase_d_pairwise_vs_production.csv",
        "data/05_layer3_portfolio_construction/phase_d_validation_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
