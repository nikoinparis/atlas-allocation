from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from phase_d_validate import (
    HOLDOUT_WEEKS,
    PRODUCTION_PIN,
    ROLLING_MIN_TRAIN_WEEKS,
    ROLLING_STEP_WEEKS,
    ROLLING_TEST_WEEKS,
    fixed_rank_composite,
    moving_block_bootstrap_prob,
    raw_metric_composite,
    read_return_csv,
    read_weight_csv,
    recovery_capture,
    rolling_origin_windows,
    split_dev_holdout,
    summary_metrics,
)
from phase_p_meta_allocator import (
    ACTIVE_PANEL_BASELINE,
    PHASEH_REFERENCE,
    PHASEN_REFERENCE,
    PHASEO_REFERENCE,
    PHASE_P_CANDIDATES,
    SHADOW_PIN,
)


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER2B_DIR = ROOT / "data" / "04_layer2b_risk_regime_engine"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"

FIXED_COMPARATOR_SET = [
    PRODUCTION_PIN,
    SHADOW_PIN,
    PHASEH_REFERENCE,
    PHASEN_REFERENCE,
    PHASEO_REFERENCE,
    ACTIVE_PANEL_BASELINE,
]
PHASE_P_VERSION_NAMES = list(PHASE_P_CANDIDATES.keys())
ALL_VERSIONS = FIXED_COMPARATOR_SET + PHASE_P_VERSION_NAMES

PRODUCTION_RULE = {
    "full_raw_composite_delta_vs_production_min": 0.015,
    "holdout_raw_composite_delta_vs_production_min": 0.0,
    "holdout_sharpe_delta_vs_production_min": -0.02,
    "rolling_raw_win_rate_vs_production_min": 0.55,
    "rolling_mean_raw_delta_vs_production_min": 0.0,
    "holdout_bootstrap_prob_excess_return_min": 0.60,
    "max_drawdown_worsening_cap": -0.010,
    "cvar_worsening_cap": -0.002,
}

SHADOW_RULE = {
    "holdout_raw_composite_delta_vs_production_min": -0.01,
    "rolling_raw_win_rate_vs_production_min": 0.45,
    "holdout_bootstrap_prob_excess_return_min": 0.50,
    "max_drawdown_worsening_cap": -0.015,
    "cvar_worsening_cap": -0.003,
}


def capture_by_states(
    return_series: pd.Series,
    benchmark_returns: pd.Series,
    market_state_history: pd.DataFrame,
    states: list[str],
) -> float:
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


def candidate_frames(
    version_names: list[str],
) -> tuple[dict[str, pd.Series], dict[str, pd.DataFrame], dict[str, pd.Series], pd.Series, pd.DataFrame]:
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


def safe_bootstrap(candidate_returns: pd.Series, reference_returns: pd.Series) -> float:
    aligned = pd.concat(
        [candidate_returns.rename("candidate"), reference_returns.rename("reference")],
        axis=1,
    ).dropna()
    return moving_block_bootstrap_prob(aligned["candidate"] - aligned["reference"])


def classify_candidate(
    name: str,
    row: pd.Series,
    *,
    best_non_production_candidate: str,
) -> str:
    production_pass = (
        row["full_raw_delta_vs_production"] >= PRODUCTION_RULE["full_raw_composite_delta_vs_production_min"]
        and row["holdout_raw_delta_vs_production"] >= PRODUCTION_RULE["holdout_raw_composite_delta_vs_production_min"]
        and row["holdout_sharpe_delta_vs_production"] >= PRODUCTION_RULE["holdout_sharpe_delta_vs_production_min"]
        and row["rolling_raw_win_rate_vs_production"] >= PRODUCTION_RULE["rolling_raw_win_rate_vs_production_min"]
        and row["rolling_mean_raw_delta_vs_production"] > PRODUCTION_RULE["rolling_mean_raw_delta_vs_production_min"]
        and row["bootstrap_prob_vs_production"] >= PRODUCTION_RULE["holdout_bootstrap_prob_excess_return_min"]
        and row["max_drawdown_delta_vs_production"] >= PRODUCTION_RULE["max_drawdown_worsening_cap"]
        and row["cvar_delta_vs_production"] >= PRODUCTION_RULE["cvar_worsening_cap"]
    )
    if production_pass:
        return "Promote now"

    shadow_pass = (
        name == best_non_production_candidate
        and row["holdout_raw_delta_vs_production"] >= SHADOW_RULE["holdout_raw_composite_delta_vs_production_min"]
        and row["rolling_raw_win_rate_vs_production"] >= SHADOW_RULE["rolling_raw_win_rate_vs_production_min"]
        and row["bootstrap_prob_vs_production"] >= SHADOW_RULE["holdout_bootstrap_prob_excess_return_min"]
        and row["max_drawdown_delta_vs_production"] >= SHADOW_RULE["max_drawdown_worsening_cap"]
        and row["cvar_delta_vs_production"] >= SHADOW_RULE["cvar_worsening_cap"]
    )
    if shadow_pass:
        return "Conditional"

    research_signal = (
        row["full_raw_delta_vs_phasen_reference"] > 0.0
        or row["full_raw_delta_vs_phaseo_reference"] > 0.0
        or row["holdout_sharpe_delta_vs_phasen_reference"] > 0.0
        or row["holdout_sharpe_delta_vs_phaseo_reference"] > 0.0
    )
    if research_signal:
        return "Research-only"
    return "Drop"


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

    full_idx = full_df.set_index("version_name")
    holdout_idx = holdout_df.set_index("version_name")

    production_full = full_idx.loc[PRODUCTION_PIN]
    production_holdout = holdout_idx.loc[PRODUCTION_PIN]
    phaseh_full = full_idx.loc[PHASEH_REFERENCE]
    phasen_full = full_idx.loc[PHASEN_REFERENCE]
    phaseo_full = full_idx.loc[PHASEO_REFERENCE]
    blend_full = full_idx.loc[ACTIVE_PANEL_BASELINE]
    phaseh_holdout = holdout_idx.loc[PHASEH_REFERENCE]
    phasen_holdout = holdout_idx.loc[PHASEN_REFERENCE]
    phaseo_holdout = holdout_idx.loc[PHASEO_REFERENCE]
    blend_holdout = holdout_idx.loc[ACTIVE_PANEL_BASELINE]

    production_holdout_returns = returns_map[PRODUCTION_PIN].tail(HOLDOUT_WEEKS)
    phaseh_holdout_returns = returns_map[PHASEH_REFERENCE].tail(HOLDOUT_WEEKS)
    phasen_holdout_returns = returns_map[PHASEN_REFERENCE].tail(HOLDOUT_WEEKS)
    phaseo_holdout_returns = returns_map[PHASEO_REFERENCE].tail(HOLDOUT_WEEKS)
    blend_holdout_returns = returns_map[ACTIVE_PANEL_BASELINE].tail(HOLDOUT_WEEKS)

    best_non_production_candidate = (
        full_df[full_df["version_name"] != PRODUCTION_PIN]
        .sort_values("raw_target_composite", ascending=False)
        .iloc[0]["version_name"]
    )

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
            "bootstrap_prob_vs_production": safe_bootstrap(cand_holdout_returns, production_holdout_returns),
            "full_raw_delta_vs_phaseh_reference": float(cand_full["raw_target_composite"] - phaseh_full["raw_target_composite"]),
            "holdout_raw_delta_vs_phaseh_reference": float(cand_holdout["raw_target_composite"] - phaseh_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_phaseh_reference": float(cand_holdout["sharpe"] - phaseh_holdout["sharpe"]),
            "bootstrap_prob_vs_phaseh_reference": safe_bootstrap(cand_holdout_returns, phaseh_holdout_returns),
            "full_raw_delta_vs_phasen_reference": float(cand_full["raw_target_composite"] - phasen_full["raw_target_composite"]),
            "holdout_raw_delta_vs_phasen_reference": float(cand_holdout["raw_target_composite"] - phasen_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_phasen_reference": float(cand_holdout["sharpe"] - phasen_holdout["sharpe"]),
            "bootstrap_prob_vs_phasen_reference": safe_bootstrap(cand_holdout_returns, phasen_holdout_returns),
            "full_raw_delta_vs_phaseo_reference": float(cand_full["raw_target_composite"] - phaseo_full["raw_target_composite"]),
            "holdout_raw_delta_vs_phaseo_reference": float(cand_holdout["raw_target_composite"] - phaseo_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_phaseo_reference": float(cand_holdout["sharpe"] - phaseo_holdout["sharpe"]),
            "bootstrap_prob_vs_phaseo_reference": safe_bootstrap(cand_holdout_returns, phaseo_holdout_returns),
            "full_raw_delta_vs_refined_blend": float(cand_full["raw_target_composite"] - blend_full["raw_target_composite"]),
            "holdout_raw_delta_vs_refined_blend": float(cand_holdout["raw_target_composite"] - blend_holdout["raw_target_composite"]),
            "holdout_sharpe_delta_vs_refined_blend": float(cand_holdout["sharpe"] - blend_holdout["sharpe"]),
            "bootstrap_prob_vs_refined_blend": safe_bootstrap(cand_holdout_returns, blend_holdout_returns),
            "max_drawdown_delta_vs_production": float(cand_full["max_drawdown"] - production_full["max_drawdown"]),
            "cvar_delta_vs_production": float(cand_full["cvar_5"] - production_full["cvar_5"]),
            **roll.to_dict(),
        }
        pairwise_rows.append(row)

    pairwise_df = pd.DataFrame(pairwise_rows)
    classification_df = pairwise_df[pairwise_df["version_name"].isin(PHASE_P_VERSION_NAMES)].copy()
    classification_df["classification"] = classification_df.apply(
        lambda row: classify_candidate(
            str(row["version_name"]),
            row,
            best_non_production_candidate=best_non_production_candidate,
        ),
        axis=1,
    )

    full_df.to_csv(LAYER3_DIR / "phase_p_candidate_metrics_full.csv", index=False)
    dev_df.to_csv(LAYER3_DIR / "phase_p_candidate_metrics_dev.csv", index=False)
    holdout_df.to_csv(LAYER3_DIR / "phase_p_candidate_metrics_holdout.csv", index=False)
    rolling_df.to_csv(LAYER3_DIR / "phase_p_rolling_origin_summary.csv", index=False)
    pairwise_df.to_csv(LAYER3_DIR / "phase_p_pairwise_validation.csv", index=False)
    classification_df.to_csv(LAYER3_DIR / "phase_p_candidate_classification.csv", index=False)

    protocol = {
        "phase": "Phase P — Meta-Allocator / Trust Model (ML Phase 3)",
        "fixed_comparator_set": FIXED_COMPARATOR_SET,
        "phase_p_candidates": PHASE_P_VERSION_NAMES,
        "production_rule": PRODUCTION_RULE,
        "shadow_rule": SHADOW_RULE,
        "holdout_weeks": HOLDOUT_WEEKS,
        "rolling_origin": {
            "min_train_weeks": ROLLING_MIN_TRAIN_WEEKS,
            "test_weeks": ROLLING_TEST_WEEKS,
            "step_weeks": ROLLING_STEP_WEEKS,
        },
        "bootstrap": {
            "method": "moving_block_bootstrap",
            "block_weeks": 13,
            "samples": 2000,
        },
    }
    (LAYER3_DIR / "phase_p_validation_protocol.json").write_text(json.dumps(protocol, indent=2))

    print("\n=== Phase P FULL metrics ===")
    print(
        full_df.set_index("version_name")[
            [
                "ann_return",
                "sharpe",
                "max_drawdown",
                "cvar_5",
                "turnover",
                "avg_bil",
                "recovery_capture",
                "calm_capture",
                "raw_target_composite",
                "raw_composite_position",
            ]
        ].round(4).to_string()
    )
    print("\n=== Phase P HOLDOUT metrics ===")
    print(
        holdout_df.set_index("version_name")[
            [
                "ann_return",
                "sharpe",
                "max_drawdown",
                "cvar_5",
                "turnover",
                "avg_bil",
                "recovery_capture",
                "calm_capture",
                "raw_target_composite",
                "raw_composite_position",
            ]
        ].round(4).to_string()
    )
    print("\n=== Phase P pairwise vs production ===")
    print(
        pairwise_df.set_index("version_name")[
            [
                "full_raw_delta_vs_production",
                "holdout_raw_delta_vs_production",
                "holdout_sharpe_delta_vs_production",
                "bootstrap_prob_vs_production",
                "rolling_raw_win_rate_vs_production",
                "rolling_mean_raw_delta_vs_production",
            ]
        ].round(4).to_string()
    )


if __name__ == "__main__":
    main()
