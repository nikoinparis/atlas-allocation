from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import phase_f_sleeve_separability as pf


ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"

REFERENCE_PANEL = [
    "dual_momentum_topn",
    "cta_trend_long_only",
    "composite_trend_quality_refined",
    "composite_confirmation_aware_momentum",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

PRIOR_REDESIGNED_PANEL = [
    "dual_momentum_topn",
    "composite_calm_trend_participation",
    "composite_recovery_transition",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

REFINED_PANEL = [
    "dual_momentum_topn",
    "composite_calm_trend_specialist",
    "composite_healthier_recovery_specialist",
    "composite_anti_chop_clarity",
    "composite_regime_conditioned",
    "taa_10m_sma",
]

REFINED_SLEEVES = {
    "composite_calm_trend_specialist": "R1 stronger calm-trend specialist",
    "composite_healthier_recovery_specialist": "R2 healthier-recovery specialist",
}

CALM_UNIVERSE = ["QQQ", "XLF", "VUG", "SPY", "XLK", "XLV", "LQD", "GLD", "XLP"]
HEALTHY_RECOVERY_UNIVERSE = ["XLU", "QQQ", "EEM", "XLK", "VWO", "VUG", "SPY", "XLF", "LQD", "HYG"]


def build_calm_trend_specialist(inputs: dict[str, object]) -> pd.DataFrame:
    index = inputs["next_week_returns"].index
    market = inputs["market_state_history"]
    trend_clarity = inputs["trend_clarity"]
    moving_average_distance = inputs["moving_average_distance"]
    low_vol = inputs["low_vol_score"]
    drawdown_score = inputs["drawdown_score"]
    mom_13 = inputs["mom_13"]
    breadth_confirmation = inputs["breadth_confirmation"]

    columns = list(dict.fromkeys(CALM_UNIVERSE + [pf.CASH_PROXY]))
    rows: list[pd.Series] = []

    for date in index:
        state = market.loc[date]
        row = pd.Series(0.0, index=columns, dtype=float, name=date)
        calm_gate = bool(
            state.get("market_state") == "calm_trend"
            or (
                state.get("market_trend_positive", 0.0) > 0.5
                and state.get("transition_persistence_prob", 0.0) >= 0.52
                and state.get("transition_non_stress_prob", 0.0) >= 0.58
                and state.get("avg_corr_risk_off_z", 0.0) <= 0.38
                and state.get("google_fear_z_tradable", 0.0) <= 0.25
            )
        )
        semi_calm_gate = bool(
            state.get("market_trend_positive", 0.0) > 0.5
            and state.get("transition_non_stress_prob", 0.0) >= 0.50
            and state.get("avg_corr_risk_off_z", 0.0) <= 0.48
        )

        score = (
            0.24 * trend_clarity.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.20 * moving_average_distance.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.22 * low_vol.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.16 * drawdown_score.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.08 * mom_13.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
            + 0.10 * breadth_confirmation.loc[date].reindex(CALM_UNIVERSE).fillna(0.0)
        )
        for asset, bonus in [
            ("LQD", 0.13),
            ("XLV", 0.08),
            ("VUG", 0.07),
            ("QQQ", 0.06),
            ("SPY", 0.04),
            ("XLF", 0.04),
            ("GLD", 0.03),
            ("XLP", 0.03),
        ]:
            score[asset] = score.get(asset, 0.0) + bonus

        eligible = [
            asset
            for asset in CALM_UNIVERSE
            if score.get(asset, 0.0) > 0.05
            and trend_clarity.loc[date].get(asset, 0.0) > -0.08
            and low_vol.loc[date].get(asset, 0.0) > -0.05
        ]
        top_weights = pf.top_k_weights(score, eligible, k=4, power=1.35, min_score=0.05)

        if calm_gate and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.90
            row["LQD"] += 0.10
        elif semi_calm_gate and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.80
            row["LQD"] += 0.10
            row[pf.CASH_PROXY] = 0.10
        elif state.get("market_trend_positive", 0.0) > 0.5 and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.60
            row["LQD"] += 0.15
            row[pf.CASH_PROXY] = 0.25
        else:
            row["LQD"] = 0.45
            row["GLD"] = 0.20
            row[pf.CASH_PROXY] = 0.35
        rows.append(row)

    return pd.DataFrame(rows).sort_index().fillna(0.0)


def build_healthier_recovery_specialist(inputs: dict[str, object]) -> pd.DataFrame:
    index = inputs["next_week_returns"].index
    market = inputs["market_state_history"]
    trend_clarity = inputs["trend_clarity"]
    moving_average_distance = inputs["moving_average_distance"]
    contained_recovery = inputs["contained_recovery"]
    mom_13 = inputs["mom_13"]
    breadth_confirmation = inputs["breadth_confirmation"]
    low_vol = inputs["low_vol_score"]

    columns = list(dict.fromkeys(HEALTHY_RECOVERY_UNIVERSE + [pf.CASH_PROXY, "TLT"]))
    rows: list[pd.Series] = []

    for date in index:
        state = market.loc[date]
        row = pd.Series(0.0, index=columns, dtype=float, name=date)
        healthy_recovery_gate = bool(
            state.get("market_state") == "recovery_confirmed"
            or (
                state.get("transition_good_state_prob", 0.0) >= 0.48
                and state.get("transition_non_stress_prob", 0.0) >= 0.62
                and state.get("transition_persistence_prob", 0.0) >= 0.50
                and state.get("breadth_change_4w", 0.0) > 0.0
                and state.get("market_trend_positive", 0.0) > 0.5
                and state.get("recent_stress_26w", 0.0) <= 1.0
            )
        )
        improving_gate = bool(
            state.get("transition_good_state_prob", 0.0) >= 0.42
            and state.get("transition_non_stress_prob", 0.0) >= 0.56
            and state.get("breadth_change_4w", 0.0) > 0.0
            and state.get("market_trend_positive", 0.0) > 0.5
        )

        score = (
            0.22 * breadth_confirmation.loc[date].reindex(HEALTHY_RECOVERY_UNIVERSE).fillna(0.0)
            + 0.18 * mom_13.loc[date].reindex(HEALTHY_RECOVERY_UNIVERSE).fillna(0.0)
            + 0.15 * moving_average_distance.loc[date].reindex(HEALTHY_RECOVERY_UNIVERSE).fillna(0.0)
            + 0.15 * trend_clarity.loc[date].reindex(HEALTHY_RECOVERY_UNIVERSE).fillna(0.0)
            + 0.10 * contained_recovery.loc[date].reindex(HEALTHY_RECOVERY_UNIVERSE).fillna(0.0)
            + 0.10 * low_vol.loc[date].reindex(HEALTHY_RECOVERY_UNIVERSE).fillna(0.0)
        )
        for asset, bonus in [
            ("XLU", 0.10),
            ("QQQ", 0.09),
            ("EEM", 0.07),
            ("XLK", 0.07),
            ("VWO", 0.06),
            ("VUG", 0.06),
            ("XLF", 0.03),
            ("LQD", 0.02),
        ]:
            score[asset] = score.get(asset, 0.0) + bonus

        eligible = [
            asset
            for asset in HEALTHY_RECOVERY_UNIVERSE
            if score.get(asset, 0.0) > 0.02
            and breadth_confirmation.loc[date].get(asset, 0.0) > -0.10
            and mom_13.loc[date].get(asset, 0.0) > -0.15
        ]
        top_weights = pf.top_k_weights(score, eligible, k=4, power=1.45, min_score=0.02)

        if healthy_recovery_gate and not top_weights.empty:
            row.loc[top_weights.index] = top_weights
        elif improving_gate and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.80
            row[pf.CASH_PROXY] = 0.20
        elif state.get("market_trend_positive", 0.0) > 0.5 and state.get("transition_non_stress_prob", 0.0) > 0.48 and not top_weights.empty:
            row.loc[top_weights.index] = top_weights * 0.60
            row[pf.CASH_PROXY] = 0.25
            row["TLT"] = 0.15
        else:
            row["LQD"] = 0.35
            row["HYG"] += 0.20
            row["TLT"] = 0.20
            row[pf.CASH_PROXY] = 0.25
        rows.append(row)

    return pd.DataFrame(rows).sort_index().fillna(0.0)


def holdout_summary(name: str, return_series: pd.Series, positions: pd.DataFrame) -> dict[str, float | str]:
    dev_returns, holdout_returns, dev_positions, holdout_positions = pf.split_dev_holdout(return_series, positions)
    dev_vol = pf.annualized_vol(dev_returns)
    holdout_vol = pf.annualized_vol(holdout_returns)
    return {
        "strategy_name": name,
        "full_ann_return": pf.annualized_return(return_series),
        "full_sharpe": pf.annualized_return(return_series) / pf.annualized_vol(return_series) if pf.annualized_vol(return_series) > 0 else np.nan,
        "dev_ann_return": pf.annualized_return(dev_returns),
        "dev_sharpe": pf.annualized_return(dev_returns) / dev_vol if pd.notna(dev_vol) and dev_vol > 0 else np.nan,
        "holdout_ann_return": pf.annualized_return(holdout_returns),
        "holdout_sharpe": pf.annualized_return(holdout_returns) / holdout_vol if pd.notna(holdout_vol) and holdout_vol > 0 else np.nan,
        "dev_avg_bil": float(dev_positions.get(pf.CASH_PROXY, pd.Series(0.0, index=dev_positions.index)).mean()),
        "holdout_avg_bil": float(holdout_positions.get(pf.CASH_PROXY, pd.Series(0.0, index=holdout_positions.index)).mean()),
    }


def candidate_corr_table(candidate_name: str, candidate_series: pd.Series, reference_names: list[str], label: str) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for reference_name in reference_names:
        reference_series = pf.read_return_series(reference_name)
        aligned = pd.concat([candidate_series.rename(candidate_name), reference_series.rename(reference_name)], axis=1).dropna()
        rows.append(
            {
                "candidate_sleeve": candidate_name,
                label: reference_name,
                "return_corr": float(aligned.corr().iloc[0, 1]) if len(aligned) > 1 else np.nan,
            }
        )
    return pd.DataFrame(rows).sort_values("return_corr", ascending=False).reset_index(drop=True)


def panel_state_winner_rows(panel_name: str, panel_state_df: pd.DataFrame, key_states: list[str]) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for market_state in key_states:
        sub = panel_state_df[panel_state_df["market_state"] == market_state].sort_values("sharpe_state", ascending=False)
        if sub.empty:
            continue
        top = sub.iloc[0]
        second = sub.iloc[1] if len(sub) > 1 else None
        median = float(sub["sharpe_state"].median())
        rows.append(
            {
                "panel_name": panel_name,
                "market_state": market_state,
                "top_sleeve": top["strategy_name"],
                "top_sharpe_state": float(top["sharpe_state"]),
                "top_ann_return_state": float(top["ann_return_state"]),
                "margin_vs_second_best_sharpe": float(top["sharpe_state"] - second["sharpe_state"]) if second is not None else np.nan,
                "margin_vs_panel_median_sharpe": float(top["sharpe_state"] - median),
            }
        )
    return rows


def panel_separability_summary(panel_name: str, panel_names: list[str], panel_state_df: pd.DataFrame) -> dict[str, float | str]:
    returns = pd.DataFrame({name: pf.read_return_series(name) for name in panel_names})
    corr = returns.corr()
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    pairwise = corr.where(mask).stack()
    winner_rows = pd.DataFrame(panel_state_winner_rows(panel_name, panel_state_df, ["calm_trend", "recovery_fragile", "recovery_confirmed", "stressed_panic"]))
    return {
        "panel_name": panel_name,
        "avg_pairwise_corr": float(pairwise.mean()),
        "avg_abs_pairwise_corr": float(pairwise.abs().mean()),
        "avg_top_minus_median_margin": float(winner_rows["margin_vs_panel_median_sharpe"].mean()),
    }


def panel_blend_summary(panel_name: str, panel_names: list[str], market_state_history: pd.DataFrame) -> tuple[dict[str, float | str], pd.DataFrame, dict[str, float | str]]:
    returns = pd.DataFrame({name: pf.read_return_series(name) for name in panel_names})
    blend = returns.mean(axis=1)
    ann_return = pf.annualized_return(blend)
    ann_vol = pf.annualized_vol(blend)
    summary = {
        "panel_name": panel_name,
        "ann_return": ann_return,
        "ann_vol": ann_vol,
        "sharpe": ann_return / ann_vol if pd.notna(ann_vol) and ann_vol > 0 else np.nan,
        "max_drawdown": pf.max_drawdown(blend),
        "cvar_5": pf.conditional_var(blend),
    }

    joined = pd.DataFrame({"net_return": blend, "market_state": market_state_history.reindex(blend.index)["market_state"]}).dropna(subset=["market_state"])
    state_rows: list[dict[str, float | str]] = []
    for market_state, group in joined.groupby("market_state"):
        state_ann_return = pf.annualized_return(group["net_return"])
        state_ann_vol = pf.annualized_vol(group["net_return"])
        state_rows.append(
            {
                "panel_name": panel_name,
                "market_state": market_state,
                "ann_return_state": state_ann_return,
                "ann_vol_state": state_ann_vol,
                "sharpe_state": state_ann_return / state_ann_vol if pd.notna(state_ann_vol) and state_ann_vol > 0 else np.nan,
            }
        )

    dev_returns = blend.dropna().iloc[:-pf.HOLDOUT_WEEKS]
    holdout_returns = blend.dropna().iloc[-pf.HOLDOUT_WEEKS:]
    dev_vol = pf.annualized_vol(dev_returns)
    holdout_vol = pf.annualized_vol(holdout_returns)
    holdout = {
        "panel_name": panel_name,
        "dev_ann_return": pf.annualized_return(dev_returns),
        "dev_sharpe": pf.annualized_return(dev_returns) / dev_vol if pd.notna(dev_vol) and dev_vol > 0 else np.nan,
        "holdout_ann_return": pf.annualized_return(holdout_returns),
        "holdout_sharpe": pf.annualized_return(holdout_returns) / holdout_vol if pd.notna(holdout_vol) and holdout_vol > 0 else np.nan,
    }
    return summary, pd.DataFrame(state_rows), holdout


def main() -> None:
    inputs = pf.load_inputs()
    market_state_history = inputs["market_state_history"]
    next_week_returns = inputs["next_week_returns"]

    refined_positions = {
        "composite_calm_trend_specialist": build_calm_trend_specialist(inputs),
        "composite_healthier_recovery_specialist": build_healthier_recovery_specialist(inputs),
    }

    refined_returns: dict[str, pd.Series] = {}
    for name, positions in refined_positions.items():
        aligned_next = next_week_returns.reindex(index=positions.index, columns=positions.columns).fillna(0.0)
        path = pf.compute_portfolio_path(positions, aligned_next)
        refined_returns[name] = path["net_return"]
        pf.write_strategy_files(name, positions, path)

    refined_summary_rows: list[dict[str, float | str]] = []
    refined_holdout_rows: list[dict[str, float | str]] = []
    refined_state_frames: list[pd.DataFrame] = []
    corr_to_core_frames: list[pd.DataFrame] = []
    corr_to_prior_frames: list[pd.DataFrame] = []
    for name in REFINED_SLEEVES:
        positions = refined_positions[name]
        returns = refined_returns[name]
        refined_summary_rows.append(pf.summary_row(name, returns, positions.diff().abs().sum(axis=1) * 0.5, positions))
        refined_holdout_rows.append(holdout_summary(name, returns, positions))
        refined_state_frames.append(pf.state_summary(name, returns, positions, market_state_history))
        corr_to_core_frames.append(candidate_corr_table(name, returns, REFERENCE_PANEL, "reference_sleeve"))
        corr_to_prior_frames.append(candidate_corr_table(name, returns, PRIOR_REDESIGNED_PANEL, "active_panel_sleeve"))

    refined_summary_df = pd.DataFrame(refined_summary_rows)
    refined_holdout_df = pd.DataFrame(refined_holdout_rows)
    refined_state_df = pd.concat(refined_state_frames, ignore_index=True)
    corr_to_core_df = pd.concat(corr_to_core_frames, ignore_index=True)
    corr_to_prior_df = pd.concat(corr_to_prior_frames, ignore_index=True)

    key_states = ["calm_trend", "recovery_fragile", "recovery_confirmed", "stressed_panic"]
    panel_state_frames = {
        "reference_current_core_panel": pd.concat(
            [pf.state_summary(name, pf.read_return_series(name), pf.read_position_frame(name), market_state_history) for name in REFERENCE_PANEL],
            ignore_index=True,
        ),
        "active_prior_redesigned_panel": pd.concat(
            [pf.state_summary(name, pf.read_return_series(name), pf.read_position_frame(name), market_state_history) for name in PRIOR_REDESIGNED_PANEL],
            ignore_index=True,
        ),
        "refined_redesigned_panel": pd.concat(
            [
                pf.state_summary(name, refined_returns[name], refined_positions[name], market_state_history) if name in refined_returns
                else pf.state_summary(name, pf.read_return_series(name), pf.read_position_frame(name), market_state_history)
                for name in REFINED_PANEL
            ],
            ignore_index=True,
        ),
    }

    panel_separability_df = pd.DataFrame(
        [
            panel_separability_summary("reference_current_core_panel", REFERENCE_PANEL, panel_state_frames["reference_current_core_panel"]),
            panel_separability_summary("active_prior_redesigned_panel", PRIOR_REDESIGNED_PANEL, panel_state_frames["active_prior_redesigned_panel"]),
            panel_separability_summary("refined_redesigned_panel", REFINED_PANEL, panel_state_frames["refined_redesigned_panel"]),
        ]
    )
    panel_winner_df = pd.concat(
        [
            pd.DataFrame(panel_state_winner_rows(panel_name, panel_state_df, key_states))
            for panel_name, panel_state_df in panel_state_frames.items()
        ],
        ignore_index=True,
    )

    blend_summaries: list[dict[str, float | str]] = []
    blend_state_frames: list[pd.DataFrame] = []
    blend_holdouts: list[dict[str, float | str]] = []
    for panel_name, panel_names in [
        ("reference_current_core_blend", REFERENCE_PANEL),
        ("active_prior_redesigned_blend", PRIOR_REDESIGNED_PANEL),
        ("refined_redesigned_blend", REFINED_PANEL),
    ]:
        summary, state_df, holdout = panel_blend_summary(panel_name, panel_names, market_state_history)
        blend_summaries.append(summary)
        blend_state_frames.append(state_df)
        blend_holdouts.append(holdout)

    pd.DataFrame(blend_summaries).to_csv(LAYER2A_DIR / "phase_g_panel_blend_summary.csv", index=False)
    pd.concat(blend_state_frames, ignore_index=True).to_csv(LAYER2A_DIR / "phase_g_panel_blend_state_summary.csv", index=False)
    pd.DataFrame(blend_holdouts).to_csv(LAYER2A_DIR / "phase_g_panel_blend_holdout_summary.csv", index=False)

    refined_summary_df.to_csv(LAYER2A_DIR / "phase_g_refined_sleeve_summary.csv", index=False)
    refined_state_df.to_csv(LAYER2A_DIR / "phase_g_refined_sleeve_state_summary.csv", index=False)
    refined_holdout_df.to_csv(LAYER2A_DIR / "phase_g_refined_sleeve_holdout_summary.csv", index=False)
    corr_to_core_df.to_csv(LAYER2A_DIR / "phase_g_refined_sleeve_corr_to_current_core.csv", index=False)
    corr_to_prior_df.to_csv(LAYER2A_DIR / "phase_g_refined_sleeve_corr_to_prior_redesigned.csv", index=False)
    panel_separability_df.to_csv(LAYER2A_DIR / "phase_g_panel_separability_summary.csv", index=False)
    panel_winner_df.to_csv(LAYER2A_DIR / "phase_g_panel_state_winner_summary.csv", index=False)

    print("Saved panel-refinement artifacts:")
    for name in [
        "data/03_layer2a_strategy_logic/strategy_positions_composite_calm_trend_specialist.csv",
        "data/03_layer2a_strategy_logic/strategy_returns_composite_calm_trend_specialist.csv",
        "data/03_layer2a_strategy_logic/strategy_positions_composite_healthier_recovery_specialist.csv",
        "data/03_layer2a_strategy_logic/strategy_returns_composite_healthier_recovery_specialist.csv",
        "data/03_layer2a_strategy_logic/phase_g_refined_sleeve_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_refined_sleeve_state_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_refined_sleeve_holdout_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_refined_sleeve_corr_to_current_core.csv",
        "data/03_layer2a_strategy_logic/phase_g_refined_sleeve_corr_to_prior_redesigned.csv",
        "data/03_layer2a_strategy_logic/phase_g_panel_blend_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_panel_blend_state_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_panel_blend_holdout_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_panel_separability_summary.csv",
        "data/03_layer2a_strategy_logic/phase_g_panel_state_winner_summary.csv",
    ]:
        print(" -", name)


if __name__ == "__main__":
    main()
