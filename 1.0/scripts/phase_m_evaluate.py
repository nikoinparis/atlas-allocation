from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from phase_d_validate import (
    HOLDOUT_WEEKS,
    PRODUCTION_PIN,
    fixed_rank_composite,
    moving_block_bootstrap_prob,
    raw_metric_composite,
    read_return_csv,
    read_weight_csv,
    recovery_capture,
    rolling_origin_windows,
    split_dev_holdout,
    summary_metrics,
    ROLLING_MIN_TRAIN_WEEKS,
    ROLLING_TEST_WEEKS,
    ROLLING_STEP_WEEKS,
)


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

LEGACY_SHADOW = "improved_phase2b_combo_abc"
CURRENT_REFINED_REFERENCE = "improved_phaseh_refined_state_allocator"
CURRENT_LEARNING_BRANCH = "improved_phasel_tail_turnover_learning_allocator"
ACTIVE_PANEL_BASELINE = "improved_phaseh_refined_panel_blend"

PHASE_M_CANDIDATES = [
    "improved_phasem_validation_first_learning_allocator",
    "improved_phasem_production_proximity_allocator",
]

FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    LEGACY_SHADOW,
    CURRENT_REFINED_REFERENCE,
    CURRENT_LEARNING_BRANCH,
    ACTIVE_PANEL_BASELINE,
]
ALL_VERSIONS = FIXED_COMPARATOR_SET + PHASE_M_CANDIDATES


def capture_by_states(return_series: pd.Series, benchmark_returns: pd.Series, market_state_history: pd.DataFrame, states: list[str]) -> float:
    aligned = pd.concat(
        [
            return_series.rename("portfolio"),
            benchmark_returns.rename("benchmark"),
            market_state_history.reindex(return_series.index)["market_state"].rename("market_state"),
        ],
        axis=1,
    ).dropna()
    mask = aligned["market_state"].isin(states)
    if not mask.any():
        return float("nan")
    bench_sum = aligned.loc[mask, "benchmark"].sum()
    return float(aligned.loc[mask, "portfolio"].sum() / bench_sum) if bench_sum != 0 else float("nan")


def candidate_frames(version_names: list[str]) -> tuple[dict[str, pd.Series], dict[str, pd.DataFrame], dict[str, pd.Series], pd.Series, pd.DataFrame]:
    benchmark_returns = read_return_csv(LAYER2A_DIR / "strategy_returns_baseline_market_proxy_buy_hold.csv")["net_return"]
    market_state_history = pd.read_csv(LAYER2B_DIR / "market_state_history.csv", parse_dates=["Date"])
    market_state_history["Date"] = pd.to_datetime(market_state_history["Date"]).dt.tz_localize(None)
    market_state_history = market_state_history.set_index("Date").sort_index()

    returns_map: dict[str, pd.Series] = {}
    weights_map: dict[str, pd.DataFrame] = {}
    turnover_map: dict[str, pd.Series] = {}
    common_index: pd.Index | None = None

    for name in version_names:
        returns_df = read_return_csv(LAYER3_DIR / f"portfolio_version_returns_{name}.csv")
        weights_df = read_weight_csv(LAYER3_DIR / f"portfolio_version_weights_{name}.csv")
        returns_map[name] = returns_df["net_return"]
        turnover_map[name] = returns_df["turnover"] if "turnover" in returns_df.columns else pd.Series(dtype=float)
        weights_map[name] = weights_df
        common_index = returns_df.index if common_index is None else common_index.intersection(returns_df.index)

    assert common_index is not None
    common_index = common_index.intersection(benchmark_returns.index).intersection(market_state_history.index).sort_values()
    benchmark_returns = benchmark_returns.reindex(common_index).dropna()
    common_index = benchmark_returns.index

    for name in version_names:
        returns_map[name] = returns_map[name].reindex(common_index).dropna()
        idx = returns_map[name].index
        weights_map[name] = weights_map[name].reindex(idx).fillna(0.0)
        turnover_map[name] = turnover_map[name].reindex(idx)

    return returns_map, weights_map, turnover_map, benchmark_returns, market_state_history


def metric_row(
    version_name: str,
    return_series: pd.Series,
    weight_panel: pd.DataFrame,
    turnover_series: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> dict[str, float | str]:
    metrics = summary_metrics(return_series, weight_panel, benchmark_returns, turnover_series)
    metrics["recovery_capture"] = recovery_capture(return_series, benchmark_returns, market_state_history)
    metrics["calm_capture"] = capture_by_states(return_series, benchmark_returns, market_state_history, ["calm_trend"])
    metrics["raw_target_composite"] = raw_metric_composite(pd.Series(metrics))
    metrics["version_name"] = version_name
    return metrics


def rolling_evaluation(
    version_names: list[str],
    returns_map: dict[str, pd.Series],
    weights_map: dict[str, pd.DataFrame],
    turnover_map: dict[str, pd.Series],
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    windows = rolling_origin_windows(benchmark_returns.index, ROLLING_MIN_TRAIN_WEEKS, ROLLING_TEST_WEEKS, ROLLING_STEP_WEEKS)
    rolling_rows: list[dict[str, float | str | int]] = []
    pairwise_rows: list[dict[str, float | str]] = []

    for name in version_names:
        raw_values = []
        sharpe_values = []
        ann_values = []
        prod_raw = []
        prod_sharpe = []
        prod_ann = []
        for _, test_index in windows:
            cand = metric_row(
                name,
                returns_map[name].reindex(test_index),
                weights_map[name].reindex(test_index).fillna(0.0),
                turnover_map[name].reindex(test_index),
                benchmark_returns.reindex(test_index),
                market_state_history,
            )
            prod = metric_row(
                PRODUCTION_PIN,
                returns_map[PRODUCTION_PIN].reindex(test_index),
                weights_map[PRODUCTION_PIN].reindex(test_index).fillna(0.0),
                turnover_map[PRODUCTION_PIN].reindex(test_index),
                benchmark_returns.reindex(test_index),
                market_state_history,
            )
            raw_values.append(float(cand["raw_target_composite"]))
            sharpe_values.append(float(cand["sharpe"]))
            ann_values.append(float(cand["ann_return"]))
            prod_raw.append(float(prod["raw_target_composite"]))
            prod_sharpe.append(float(prod["sharpe"]))
            prod_ann.append(float(prod["ann_return"]))

        raw = pd.Series(raw_values, dtype=float)
        sharpe = pd.Series(sharpe_values, dtype=float)
        ann = pd.Series(ann_values, dtype=float)
        prod_raw = pd.Series(prod_raw, dtype=float)
        prod_sharpe = pd.Series(prod_sharpe, dtype=float)
        prod_ann = pd.Series(prod_ann, dtype=float)
        rolling_rows.append(
            {
                "version_name": name,
                "rolling_windows": int(len(raw)),
                "rolling_avg_raw_composite": float(raw.mean()),
                "rolling_median_raw_composite": float(raw.median()),
                "rolling_avg_sharpe": float(sharpe.mean()),
                "rolling_avg_ann_return": float(ann.mean()),
            }
        )
        pairwise_rows.append(
            {
                "version_name": name,
                "rolling_raw_win_rate_vs_production": float((raw > prod_raw).mean()),
                "rolling_mean_raw_delta_vs_production": float((raw - prod_raw).mean()),
                "rolling_mean_sharpe_delta_vs_production": float((sharpe - prod_sharpe).mean()),
                "rolling_mean_ann_return_delta_vs_production": float((ann - prod_ann).mean()),
            }
        )
    return pd.DataFrame(rolling_rows), pd.DataFrame(pairwise_rows)


def main() -> None:
    returns_map, weights_map, turnover_map, benchmark_returns, market_state_history = candidate_frames(ALL_VERSIONS)

    full_rows = []
    dev_rows = []
    holdout_rows = []
    for name in ALL_VERSIONS:
        full_rows.append(metric_row(name, returns_map[name], weights_map[name], turnover_map[name], benchmark_returns, market_state_history))
        dev_returns, holdout_returns, dev_weights, holdout_weights = split_dev_holdout(returns_map[name], weights_map[name], HOLDOUT_WEEKS)
        dev_rows.append(
            metric_row(
                name,
                dev_returns,
                dev_weights,
                turnover_map[name].reindex(dev_returns.index),
                benchmark_returns.reindex(dev_returns.index),
                market_state_history,
            )
        )
        holdout_rows.append(
            metric_row(
                name,
                holdout_returns,
                holdout_weights,
                turnover_map[name].reindex(holdout_returns.index),
                benchmark_returns.reindex(holdout_returns.index),
                market_state_history,
            )
        )

    full_df = pd.DataFrame(full_rows)
    dev_df = pd.DataFrame(dev_rows)
    holdout_df = pd.DataFrame(holdout_rows)

    for df in [full_df, dev_df, holdout_df]:
        df["fixed_rank_composite"] = fixed_rank_composite(df.set_index("version_name")).values
        df["fixed_rank_position"] = df["fixed_rank_composite"].rank(ascending=False, method="dense").astype(int)
        df["raw_composite_position"] = df["raw_target_composite"].rank(ascending=False, method="dense").astype(int)

    rolling_df, rolling_pairwise = rolling_evaluation(
        ALL_VERSIONS,
        returns_map,
        weights_map,
        turnover_map,
        benchmark_returns,
        market_state_history,
    )

    phase_d_protocol = json.loads((LAYER3_DIR / "phase_d_validation_protocol.json").read_text())
    prod_rule = phase_d_protocol["future_promotion_rule"]["production_pin"]
    shadow_rule = phase_d_protocol["future_promotion_rule"]["shadow_pin"]

    full_idx = full_df.set_index("version_name")
    holdout_idx = holdout_df.set_index("version_name")
    production_full = full_idx.loc[PRODUCTION_PIN]
    production_holdout = holdout_idx.loc[PRODUCTION_PIN]
    current_ref_full = full_idx.loc[CURRENT_REFINED_REFERENCE]
    current_learning_full = full_idx.loc[CURRENT_LEARNING_BRANCH]
    refined_blend_full = full_idx.loc[ACTIVE_PANEL_BASELINE]

    production_holdout_returns = returns_map[PRODUCTION_PIN].tail(HOLDOUT_WEEKS)
    current_ref_holdout_returns = returns_map[CURRENT_REFINED_REFERENCE].tail(HOLDOUT_WEEKS)
    current_learning_holdout_returns = returns_map[CURRENT_LEARNING_BRANCH].tail(HOLDOUT_WEEKS)
    refined_blend_holdout_returns = returns_map[ACTIVE_PANEL_BASELINE].tail(HOLDOUT_WEEKS)

    pairwise_rows = []
    for name in ALL_VERSIONS:
        cand_full = full_idx.loc[name]
        cand_holdout = holdout_idx.loc[name]
        cand_holdout_returns = returns_map[name].tail(HOLDOUT_WEEKS)
        roll = rolling_pairwise.set_index("version_name").loc[name]
        row = {
            "version_name": name,
            "full_raw_delta_vs_production": float(cand_full["raw_target_composite"] - production_full["raw_target_composite"]),
            "holdout_raw_delta_vs_production": float(cand_holdout["raw_target_composite"] - production_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_production": float(cand_holdout["sharpe"] - production_holdout["sharpe"]),
            "bootstrap_prob_vs_production": moving_block_bootstrap_prob(cand_holdout_returns - production_holdout_returns),
            "full_raw_delta_vs_current_refined_allocator": float(cand_full["raw_target_composite"] - current_ref_full["raw_target_composite"]),
            "full_raw_delta_vs_current_learning_branch": float(cand_full["raw_target_composite"] - current_learning_full["raw_target_composite"]),
            "full_raw_delta_vs_refined_blend": float(cand_full["raw_target_composite"] - refined_blend_full["raw_target_composite"]),
            "bootstrap_prob_vs_current_refined_allocator": moving_block_bootstrap_prob(cand_holdout_returns - current_ref_holdout_returns),
            "bootstrap_prob_vs_current_learning_branch": moving_block_bootstrap_prob(cand_holdout_returns - current_learning_holdout_returns),
            "bootstrap_prob_vs_refined_blend": moving_block_bootstrap_prob(cand_holdout_returns - refined_blend_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        row["production_rule_pass"] = bool(
            row["full_raw_delta_vs_production"] >= prod_rule["full_raw_composite_delta_vs_production_min"]
            and row["holdout_raw_delta_vs_production"] >= prod_rule["holdout_raw_composite_delta_vs_production_min"]
            and row["holdout_sharpe_delta_vs_production"] >= prod_rule["holdout_sharpe_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= prod_rule["rolling_raw_win_rate_vs_production_min"]
            and row["rolling_mean_raw_delta_vs_production"] > prod_rule["rolling_mean_raw_delta_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= prod_rule["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= prod_rule["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= prod_rule["cvar_worsening_cap"]
        )
        row["shadow_rule_pass"] = bool(
            row["holdout_raw_delta_vs_production"] >= shadow_rule["holdout_raw_composite_delta_vs_production_min"]
            and row["rolling_raw_win_rate_vs_production"] >= shadow_rule["rolling_raw_win_rate_vs_production_min"]
            and row["bootstrap_prob_vs_production"] >= shadow_rule["holdout_bootstrap_prob_excess_return_min"]
            and row["max_drawdown_delta_vs_production"] >= shadow_rule["max_drawdown_worsening_cap"]
            and row["cvar_delta_vs_production"] >= shadow_rule["cvar_worsening_cap"]
        )
        pairwise_rows.append(row)

    pairwise_df = pd.DataFrame(pairwise_rows)

    full_df.to_csv(LAYER3_DIR / "phase_m_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_m_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_m_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_m_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_m_pairwise_validation.csv", index=False)

    protocol = {
        "phase": "Phase M",
        "purpose": "Final allocator-category validation",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "candidate_versions": PHASE_M_CANDIDATES,
        "holdout_weeks": HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": ROLLING_TEST_WEEKS,
            "step_weeks": ROLLING_STEP_WEEKS,
        },
        "promotion_rule_reference": "phase_d_validation_protocol.json",
    }
    (LAYER3_DIR / "phase_m_validation_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("Saved Phase M evaluation artifacts:")
    for name in [
        "data/05_layer3_portfolio_construction/phase_m_candidate_metrics_full.csv",
        "data/05_layer3_portfolio_construction/phase_m_candidate_metrics_dev.csv",
        "data/05_layer3_portfolio_construction/phase_m_candidate_metrics_holdout.csv",
        "data/05_layer3_portfolio_construction/phase_m_rolling_origin_summary.csv",
        "data/05_layer3_portfolio_construction/phase_m_pairwise_validation.csv",
        "data/05_layer3_portfolio_construction/phase_m_validation_protocol.json",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
