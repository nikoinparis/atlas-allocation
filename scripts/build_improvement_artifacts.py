from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


plt.show = lambda *args, **kwargs: None

ROOT = Path(__file__).resolve().parents[1]
LAYER2A_DIR = ROOT / "data" / "03_layer2a_strategy_logic"
LAYER3_DIR = ROOT / "data" / "05_layer3_portfolio_construction"


def load_notebook_namespace(notebook_path: Path, code_cell_indices: list[int]) -> dict:
    notebook = json.loads(notebook_path.read_text())
    namespace: dict = {"__name__": "__main__"}
    for idx in code_cell_indices:
        cell = notebook["cells"][idx]
        if cell["cell_type"] != "code":
            continue
        exec(compile("".join(cell["source"]), f"{notebook_path.name}:cell_{idx}", "exec"), namespace)
    return namespace


def replace_or_append_row(df: pd.DataFrame, key_col: str, row: dict) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame([row])
    out = df.copy()
    if key_col in out.columns:
        out = out[out[key_col] != row[key_col]]
    return pd.concat([out, pd.DataFrame([row])], ignore_index=True)


def build_dampener_regime_states(regime_states: pd.DataFrame, overlay_variant: str) -> pd.DataFrame:
    adjusted = regime_states.copy()
    if adjusted.empty or overlay_variant == "baseline" or "overlay_multiplier" not in adjusted.columns:
        return adjusted
    if overlay_variant == "looser_neutral_stress" and "risk_state" in adjusted.columns:
        neutral_mask = adjusted["risk_state"].eq("neutral")
        stressed_mask = adjusted["risk_state"].eq("stressed")
        adjusted.loc[neutral_mask, "overlay_multiplier"] = adjusted.loc[neutral_mask, "overlay_multiplier"].clip(lower=0.80)
        adjusted.loc[stressed_mask, "overlay_multiplier"] = adjusted.loc[stressed_mask, "overlay_multiplier"].clip(lower=0.40)
    return adjusted


def classify_allocations(weight_panel: pd.DataFrame, cash_proxy: str) -> tuple[list[str], list[str]]:
    defensive_assets = [ticker for ticker in ["IEF", "SHY", "TLT", "TIP", "GLD"] if ticker in weight_panel.columns and ticker != cash_proxy]
    offensive_assets = [ticker for ticker in weight_panel.columns if ticker not in set(defensive_assets + [cash_proxy])]
    return offensive_assets, defensive_assets


def version_state_label(current_offensive: float, current_defensive: float, current_cash: float) -> str:
    if current_cash + current_defensive >= 0.55:
        return "defensive"
    if current_offensive >= 0.60 and current_cash <= 0.20:
        return "risk_on"
    return "neutral"


ns3 = load_notebook_namespace(
    ROOT / "03_layer2a_strategy_logic.ipynb",
    [2, 3, 4, 5, 6, 8],
)
ns5 = load_notebook_namespace(
    ROOT / "05_layer3_portfolio_construction.ipynb",
    [2, 4, 5, 7, 9, 11],
)


def evaluate_signal_combo(signal_names: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    signal_panels = {name: ns3["baseline_signal_panels"][name] for name in signal_names if name in ns3["baseline_signal_panels"]}
    composite_signal = ns3["combine_signal_panels"](
        signal_panels,
        weight_history=None,
        smoothing_weeks=ns3["COMPOSITE_SMOOTHING_WEEKS"],
    )
    weights = ns3["build_top_n_long_only_weights"](
        composite_signal.reindex(columns=ns3["broad_risk_assets"]),
        top_n=min(5, max(3, len(ns3["broad_risk_assets"]) // 3)) if ns3["broad_risk_assets"] else 1,
        min_signal=0.0,
        defensive_asset=ns3["defensive_asset"],
        fill_to_defensive=True,
    )
    weights, _ = ns3["apply_rebalance_schedule"](weights, "monthly")
    path = ns3["compute_strategy_path"](
        weights,
        ns3["next_week_returns"],
        transaction_cost_bps=ns3["DEFAULT_COST_BPS"],
        cash_proxy_returns=ns3["cash_proxy_return_series"],
    )
    metrics = ns5["summary_metrics"](
        path["net_return"],
        turnover_series=path["turnover"],
        weight_panel=weights,
        allocation_panel=weights,
        trials=max(len(signal_names), 2),
    )
    metrics["avg_bil_weight"] = weights.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weights.columns else np.nan
    metrics["avg_spy_weight"] = weights.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weights.columns else np.nan
    subperiod_df = ns5["subperiod_summary"]("combo", path["net_return"])
    metrics["subperiod_sharpe_range"] = (
        subperiod_df["sharpe"].max() - subperiod_df["sharpe"].min() if not subperiod_df.empty else np.nan
    )
    return weights, path, metrics


base_signal_set = ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy"]
current_signal_set = list(ns3["baseline_signal_names"])
signal_incremental_rows: list[dict] = []
signal_subset_rows: list[dict] = []

_, _, base_signal_metrics = evaluate_signal_combo(base_signal_set)
signal_incremental_rows.append(
    {
        "study": "base_core",
        "test_type": "baseline",
        "candidate_signal": "base_core",
        "signal_count": len(base_signal_set),
        "signal_names": "|".join(base_signal_set),
        **base_signal_metrics,
    }
)

for candidate in [name for name in current_signal_set if name not in base_signal_set]:
    _, _, metrics = evaluate_signal_combo(base_signal_set + [candidate])
    signal_incremental_rows.append(
        {
            "study": "base_plus_one",
            "test_type": "add_one",
            "candidate_signal": candidate,
            "signal_count": len(base_signal_set) + 1,
            "signal_names": "|".join(base_signal_set + [candidate]),
            **metrics,
            "delta_ann_return_vs_base": metrics["ann_return"] - base_signal_metrics["ann_return"],
            "delta_sharpe_vs_base": metrics["sharpe"] - base_signal_metrics["sharpe"],
            "delta_max_drawdown_vs_base": metrics["max_drawdown"] - base_signal_metrics["max_drawdown"],
            "delta_cvar_5_vs_base": metrics["cvar_5"] - base_signal_metrics["cvar_5"],
            "delta_turnover_vs_base": metrics["avg_weekly_turnover"] - base_signal_metrics["avg_weekly_turnover"],
        }
    )

_, _, full_signal_metrics = evaluate_signal_combo(current_signal_set)
signal_incremental_rows.append(
    {
        "study": "current_full",
        "test_type": "baseline",
        "candidate_signal": "current_full",
        "signal_count": len(current_signal_set),
        "signal_names": "|".join(current_signal_set),
        **full_signal_metrics,
    }
)

for candidate in [name for name in current_signal_set if name not in base_signal_set]:
    reduced = [name for name in current_signal_set if name != candidate]
    _, _, metrics = evaluate_signal_combo(reduced)
    signal_incremental_rows.append(
        {
            "study": "drop_from_current_full",
            "test_type": "drop_one",
            "candidate_signal": candidate,
            "signal_count": len(reduced),
            "signal_names": "|".join(reduced),
            **metrics,
            "delta_ann_return_vs_current_full": metrics["ann_return"] - full_signal_metrics["ann_return"],
            "delta_sharpe_vs_current_full": metrics["sharpe"] - full_signal_metrics["sharpe"],
            "delta_max_drawdown_vs_current_full": metrics["max_drawdown"] - full_signal_metrics["max_drawdown"],
            "delta_cvar_5_vs_current_full": metrics["cvar_5"] - full_signal_metrics["cvar_5"],
            "delta_turnover_vs_current_full": metrics["avg_weekly_turnover"] - full_signal_metrics["avg_weekly_turnover"],
        }
    )

signal_subset_specs = {
    "core4": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy"],
    "core4_bab": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy"],
    "core4_bab_carry": ["xsmom_global", "multi_mom_invvol", "quality_proxy", "value_proxy", "bab_proxy", "carry_proxy"],
    "current_full": current_signal_set,
    "current_drop_residual": [name for name in current_signal_set if name != "residual_momentum"],
    "current_drop_reversal": [name for name in current_signal_set if name != "reversal_4w_global"],
    "current_drop_residual_reversal": [name for name in current_signal_set if name not in {"residual_momentum", "reversal_4w_global"}],
}

for combo_name, signal_names in signal_subset_specs.items():
    _, _, metrics = evaluate_signal_combo(signal_names)
    signal_subset_rows.append(
        {
            "combo_name": combo_name,
            "signal_count": len(signal_names),
            "signal_names": "|".join(signal_names),
            **metrics,
        }
    )

signal_incremental_df = pd.DataFrame(signal_incremental_rows)
signal_subset_df = pd.DataFrame(signal_subset_rows)
signal_incremental_df.to_csv(ROOT / "data" / "02_layer1_signals" / "signal_incremental_contribution.csv", index=False)
signal_subset_df.to_csv(ROOT / "data" / "02_layer1_signals" / "signal_subset_comparison.csv", index=False)


selective_signal_names = signal_subset_specs["core4_bab_carry"]
selective_weights, selective_path, selective_metrics = evaluate_signal_combo(selective_signal_names)
selective_strategy_name = "composite_selective_signals"

(LAYER2A_DIR / f"strategy_positions_{selective_strategy_name}.csv").write_text(selective_weights.to_csv())
(LAYER2A_DIR / f"strategy_returns_{selective_strategy_name}.csv").write_text(selective_path.to_csv())

strategy_summary = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
selective_summary = ns3["summary_metrics"](selective_path["net_return"], turnover_series=selective_path["turnover"])
selective_summary.update(
    {
        "strategy_name": selective_strategy_name,
        "strategy_type": "strategy_logic",
        "rebalance_frequency": "monthly",
        "benchmark_group": "strategy",
        "validation_score": (
            selective_summary["sharpe"]
            + 0.5 * selective_summary["calmar"]
            + 0.2 * selective_summary["hit_rate"]
            - 0.1 * selective_summary["avg_weekly_turnover"]
        ),
    }
)
strategy_summary = replace_or_append_row(strategy_summary, "strategy_name", selective_summary)
strategy_summary = strategy_summary.sort_values(["benchmark_group", "validation_score"], ascending=[True, False]).reset_index(drop=True)
strategy_summary.to_csv(LAYER2A_DIR / "strategy_summary_table.csv", index=False)

layer2_manifest = json.loads((LAYER2A_DIR / "layer2_manifest.json").read_text())
layer2_manifest = [row for row in layer2_manifest if row.get("strategy_name") != selective_strategy_name]
layer2_manifest.append(
    {
        "strategy_name": selective_strategy_name,
        "notebook_origin": "03_layer2a_strategy_logic.ipynb",
        "type": "strategy_logic",
        "required_inputs": [
            "signal_xsmom.csv",
            "signal_multi_horizon_mom.csv",
            "signal_quality.csv",
            "signal_value.csv",
            "signal_bab.csv",
            "signal_carry.csv",
        ],
        "rebalance_frequency": "monthly",
        "lag_convention": "Consumes Layer 1 tradable signals; new price filters are lagged 1 week; external features use tradable columns only.",
        "output_files": [
            f"strategy_positions_{selective_strategy_name}.csv",
            f"strategy_returns_{selective_strategy_name}.csv",
        ],
        "caveats": "Selective composite keeps the signals that improved the long-only ETF sleeve most cleanly in the incremental study; it is still a practical top-N proxy rather than a fully optimized ensemble.",
        "description": "Top-N long-only strategy using the selective signal blend that retained trend, quality/value, BAB, and carry while excluding weaker add-ons.",
    }
)
(LAYER2A_DIR / "layer2_manifest.json").write_text(json.dumps(layer2_manifest, indent=2))


portfolio_version_rows: list[dict] = []
portfolio_version_regime_rows: list[pd.DataFrame] = []
portfolio_version_subperiod_rows: list[pd.DataFrame] = []
allocation_driver_rows: list[dict] = []
allocation_driver_breakdown_rows: list[dict] = []
allocation_driver_timeseries_rows: list[dict] = []
sleeve_incremental_rows: list[dict] = []
sleeve_subset_rows: list[dict] = []

strategy_lookup = pd.read_csv(LAYER2A_DIR / "strategy_summary_table.csv")
strategy_lookup = strategy_lookup.set_index("strategy_name") if not strategy_lookup.empty else pd.DataFrame().set_index(pd.Index([], name="strategy_name"))

base_sleeve_return_panel = ns5["sleeve_return_panel"].copy()
base_sleeve_positions = dict(ns5["sleeve_positions"])
base_sleeve_return_panel[selective_strategy_name] = selective_path["net_return"].reindex(base_sleeve_return_panel.index).fillna(0.0)
base_sleeve_positions[selective_strategy_name] = selective_weights.reindex(index=ns5["weekly_prices"].index, columns=ns5["weekly_prices"].columns).fillna(0.0)

baseline_subset = list(ns5["sleeve_return_panel"].columns)
drop_breadth_subset = [name for name in baseline_subset if name != "composite_breadth_filtered"]
replace_equal_subset = ["dual_momentum_topn", "cta_trend_long_only", selective_strategy_name, "composite_regime_conditioned", "taa_10m_sma"]
improved_subset = replace_equal_subset

subset_specs = {
    "baseline_current": baseline_subset,
    "drop_breadth": drop_breadth_subset,
    "drop_regime": [name for name in baseline_subset if name != "composite_regime_conditioned"],
    "replace_equal_with_selective": replace_equal_subset,
    "add_selective_drop_breadth": drop_breadth_subset + [selective_strategy_name],
}

def run_subset(method_name: str, subset_name: str, subset_sleeves: list[str], overlay_variant: str = "baseline", speed: float = ns5["SLEEVE_REALLOCATION_SPEED"], target_vol_ceil: float = ns5["TARGET_VOL_CEIL"]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    subset = [name for name in subset_sleeves if name in base_sleeve_return_panel.columns]
    method_spec = next(spec for spec in ns5["method_specs"] if spec["method_name"] == method_name)
    regime_states = build_dampener_regime_states(ns5["regime_states"], overlay_variant)
    sleeve_alloc, weight_panel, path, diagnostics = ns5["run_method_backtest"](
        method_name=f"{subset_name}_{method_name}",
        method_category="improvement_lab",
        engine=method_spec["engine"],
        sleeve_return_panel=base_sleeve_return_panel[subset],
        sleeve_positions={name: base_sleeve_positions[name] for name in subset},
        forward_weekly_returns=ns5["next_week_returns"].reindex(columns=ns5["weekly_prices"].columns),
        conviction_inputs={key: value.reindex(columns=[name for name in subset if name in value.columns]) for key, value in ns5["conviction_inputs"].items()},
        regime_states=regime_states,
        cash_proxy=ns5["cash_proxy"],
        train_window_weeks=ns5["TRAIN_WINDOW_WEEKS"],
        expected_return_key=method_spec["expected_return_key"],
        covariance_method=method_spec["covariance_method"],
        target_vol_ceil=target_vol_ceil,
        sleeve_reallocation_speed=speed,
    )
    metrics = ns5["summary_metrics"](
        path["net_return"],
        turnover_series=path["turnover"],
        weight_panel=weight_panel,
        allocation_panel=sleeve_alloc,
        trials=max(len(subset), 2),
    )
    return sleeve_alloc, weight_panel, path, diagnostics, metrics


baseline_rows_by_method: dict[str, dict] = {}
for method_name in ["hrp", "max_diversification"]:
    _, baseline_weights, _, baseline_diag, baseline_metrics = run_subset(method_name, "baseline_current", baseline_subset)
    baseline_rows_by_method[method_name] = {
        "metrics": baseline_metrics,
        "avg_bil": baseline_weights.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in baseline_weights.columns else np.nan,
        "avg_cash_weight": baseline_diag["cash_weight"].mean() if not baseline_diag.empty else np.nan,
    }
    for subset_name, subset_sleeves in subset_specs.items():
        _, weight_panel, path, diagnostics, metrics = run_subset(method_name, subset_name, subset_sleeves)
        row = {
            "method_name": method_name,
            "subset_name": subset_name,
            "sleeve_count": len(subset_sleeves),
            "sleeve_names": "|".join(subset_sleeves),
            **metrics,
            "avg_bil_weight": weight_panel.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weight_panel.columns else np.nan,
            "avg_spy_weight": weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan,
            "avg_cash_weight": diagnostics["cash_weight"].mean() if not diagnostics.empty else np.nan,
        }
        if method_name in baseline_rows_by_method:
            baseline = baseline_rows_by_method[method_name]["metrics"]
            row["delta_ann_return_vs_baseline"] = row["ann_return"] - baseline["ann_return"]
            row["delta_sharpe_vs_baseline"] = row["sharpe"] - baseline["sharpe"]
            row["delta_max_drawdown_vs_baseline"] = row["max_drawdown"] - baseline["max_drawdown"]
            row["delta_cvar_5_vs_baseline"] = row["cvar_5"] - baseline["cvar_5"]
            row["delta_turnover_vs_baseline"] = row["avg_weekly_turnover"] - baseline["avg_weekly_turnover"]
            row["delta_avg_bil_vs_baseline"] = row["avg_bil_weight"] - baseline_rows_by_method[method_name]["avg_bil"]
            row["delta_avg_cash_vs_baseline"] = row["avg_cash_weight"] - baseline_rows_by_method[method_name]["avg_cash_weight"]
        sleeve_subset_rows.append(row)

        changed_sleeves = sorted(set(baseline_subset).symmetric_difference(set(subset_sleeves)))
        if subset_name == "baseline_current":
            continue
        for sleeve_name in changed_sleeves:
            standalone = strategy_lookup.loc[sleeve_name].to_dict() if sleeve_name in strategy_lookup.index else {}
            sleeve_incremental_rows.append(
                {
                    "method_name": method_name,
                    "subset_name": subset_name,
                    "candidate_sleeve": sleeve_name,
                    "standalone_ann_return": standalone.get("ann_return"),
                    "standalone_sharpe": standalone.get("sharpe"),
                    "standalone_max_drawdown": standalone.get("max_drawdown"),
                    "standalone_avg_weekly_turnover": standalone.get("avg_weekly_turnover"),
                    **row,
                }
            )


version_specs = [
    {
        "version_name": "baseline_hrp_default",
        "method_name": "hrp",
        "subset_name": "baseline_current",
        "subset_sleeves": baseline_subset,
        "overlay_variant": "baseline",
        "sleeve_reallocation_speed": 0.40,
        "target_vol_ceil": 1.00,
        "note": "Original baseline stack with the experimental breadth sleeve still active.",
    },
    {
        "version_name": "improved_hrp_selective",
        "method_name": "hrp",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "target_vol_ceil": 1.00,
        "note": "Drops the redundant breadth sleeve, swaps in the selective composite sleeve, and relaxes only the overlay that was visibly binding.",
    },
    {
        "version_name": "baseline_max_div_default",
        "method_name": "max_diversification",
        "subset_name": "baseline_current",
        "subset_sleeves": baseline_subset,
        "overlay_variant": "baseline",
        "sleeve_reallocation_speed": 0.40,
        "target_vol_ceil": 1.00,
        "note": "Original maximum-diversification baseline.",
    },
    {
        "version_name": "improved_max_div_selective",
        "method_name": "max_diversification",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "target_vol_ceil": 1.00,
        "note": "Improved maximum-diversification version using the same selective sleeve set and looser overlay rules.",
    },
    {
        "version_name": "improved_inverse_vol_selective",
        "method_name": "inverse_vol",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "target_vol_ceil": 1.00,
        "note": "Inverse-vol reference run on the improved finalist sleeves.",
    },
    {
        "version_name": "improved_herc_selective",
        "method_name": "herc",
        "subset_name": "improved_selective_core",
        "subset_sleeves": improved_subset,
        "overlay_variant": "looser_neutral_stress",
        "sleeve_reallocation_speed": 0.60,
        "target_vol_ceil": 1.00,
        "note": "HERC reference run on the improved finalist sleeves.",
    },
]

version_baselines = {}
for version in version_specs:
    sleeve_alloc, weight_panel, path, diagnostics, metrics = run_subset(
        version["method_name"],
        version["subset_name"],
        version["subset_sleeves"],
        overlay_variant=version["overlay_variant"],
        speed=version["sleeve_reallocation_speed"],
        target_vol_ceil=version["target_vol_ceil"],
    )

    weight_panel.to_csv(LAYER3_DIR / f"portfolio_version_weights_{version['version_name']}.csv")
    sleeve_alloc.to_csv(LAYER3_DIR / f"portfolio_version_sleeve_weights_{version['version_name']}.csv")
    path.to_csv(LAYER3_DIR / f"portfolio_version_returns_{version['version_name']}.csv")

    regime_split = ns5["regime_split_summary"](version["version_name"], path["net_return"], ns5["regime_states"].get("risk_state", pd.Series(dtype=object)))
    subperiod_split = ns5["subperiod_summary"](version["version_name"], path["net_return"])
    if not regime_split.empty:
        portfolio_version_regime_rows.append(regime_split)
    if not subperiod_split.empty:
        portfolio_version_subperiod_rows.append(subperiod_split)

    avg_bil = weight_panel.get("BIL", pd.Series(dtype=float)).mean() if "BIL" in weight_panel.columns else np.nan
    avg_spy = weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan
    avg_cash = diagnostics["cash_weight"].mean() if not diagnostics.empty else np.nan

    row = {
        **version,
        **metrics,
        "avg_bil_weight": avg_bil,
        "avg_spy_weight": avg_spy,
        "avg_cash_weight": avg_cash,
        "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
        "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
    }
    family = version["method_name"]
    if version["version_name"].startswith("baseline_"):
        version_baselines[family] = row
    elif family in version_baselines:
        base = version_baselines[family]
        for key in ["ann_return", "ann_vol", "sharpe", "max_drawdown", "calmar", "cvar_5", "avg_weekly_turnover", "avg_effective_n", "avg_bil_weight", "avg_spy_weight", "avg_cash_weight"]:
            row[f"delta_{key}_vs_baseline"] = row[key] - base[key]
    portfolio_version_rows.append(row)

    offensive_assets, defensive_assets = classify_allocations(weight_panel, ns5["cash_proxy"])
    offensive_weight = weight_panel.reindex(columns=offensive_assets, fill_value=0.0).sum(axis=1)
    defensive_weight = weight_panel.reindex(columns=defensive_assets, fill_value=0.0).sum(axis=1)
    cash_weight = weight_panel.get(ns5["cash_proxy"], pd.Series(0.0, index=weight_panel.index))
    overlay_cash = sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", pd.Series(0.0, index=weight_panel.index))
    sleeve_bil = (cash_weight - overlay_cash).clip(lower=0.0)
    latest_date = weight_panel.index[-1]
    current_offensive = offensive_weight.loc[latest_date]
    current_defensive = defensive_weight.loc[latest_date]
    current_cash = cash_weight.loc[latest_date]
    current_state = version_state_label(current_offensive, current_defensive, current_cash)

    allocation_driver_rows.append(
        {
            "version_name": version["version_name"],
            "method_name": version["method_name"],
            "current_date": str(latest_date.date()),
            "current_risk_state": ns5["regime_states"].loc[latest_date, "risk_state"] if latest_date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
            "current_state_label": current_state,
            "current_offensive_weight": current_offensive,
            "current_defensive_weight": current_defensive,
            "current_cash_proxy_weight": current_cash,
            "current_bil_weight": cash_weight.loc[latest_date],
            "current_spy_weight": weight_panel.loc[latest_date].get("SPY", np.nan),
            "avg_offensive_weight": offensive_weight.mean(),
            "avg_defensive_weight": defensive_weight.mean(),
            "avg_cash_proxy_weight": cash_weight.mean(),
            "avg_bil_weight": cash_weight.mean(),
            "avg_spy_weight": weight_panel.get("SPY", pd.Series(dtype=float)).mean() if "SPY" in weight_panel.columns else np.nan,
            "avg_overlay_cash_weight": overlay_cash.mean(),
            "avg_sleeve_bil_weight": sleeve_bil.mean(),
            "current_overlay_cash_weight": overlay_cash.loc[latest_date],
            "current_sleeve_bil_weight": sleeve_bil.loc[latest_date],
            "avg_target_vol_multiplier": diagnostics["target_vol_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_regime_multiplier": diagnostics["regime_multiplier"].mean() if not diagnostics.empty else np.nan,
            "avg_gross_multiplier": diagnostics["gross_multiplier"].mean() if not diagnostics.empty else np.nan,
            "calm_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("calm").mean(),
            "neutral_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("neutral").mean(),
            "stressed_regime_frequency": ns5["regime_states"].get("risk_state", pd.Series(dtype=object)).eq("stressed").mean(),
        }
    )

    for date in weight_panel.index:
        allocation_driver_timeseries_rows.append(
            {
                "Date": str(date.date()),
                "version_name": version["version_name"],
                "offensive_weight": offensive_weight.loc[date],
                "defensive_weight": defensive_weight.loc[date],
                "cash_proxy_weight": cash_weight.loc[date],
                "bil_weight": cash_weight.loc[date],
                "spy_weight": weight_panel.loc[date].get("SPY", np.nan),
                "overlay_cash_weight": overlay_cash.loc[date],
                "sleeve_bil_weight": sleeve_bil.loc[date],
                "risk_state": ns5["regime_states"].loc[date, "risk_state"] if date in ns5["regime_states"].index and "risk_state" in ns5["regime_states"].columns else None,
            }
        )

    current_sleeve_alloc = sleeve_alloc.loc[latest_date] if latest_date in sleeve_alloc.index else pd.Series(dtype=float)
    for asset in [ns5["cash_proxy"], "SPY"]:
        overlay_value = current_sleeve_alloc.get(f"cash::{ns5['cash_proxy']}", 0.0) if asset == ns5["cash_proxy"] else 0.0
        allocation_driver_breakdown_rows.append(
            {
                "version_name": version["version_name"],
                "horizon": "current",
                "asset": asset,
                "driver": "overlay_cash" if asset == ns5["cash_proxy"] else "overlay_cash",
                "contribution": overlay_value,
            }
        )
        for sleeve_name in [name for name in current_sleeve_alloc.index if not str(name).startswith("cash::")]:
            sleeve_weight = current_sleeve_alloc.get(sleeve_name, 0.0)
            sleeve_position = base_sleeve_positions[sleeve_name].loc[latest_date].get(asset, 0.0) if latest_date in base_sleeve_positions[sleeve_name].index else 0.0
            allocation_driver_breakdown_rows.append(
                {
                    "version_name": version["version_name"],
                    "horizon": "current",
                    "asset": asset,
                    "driver": sleeve_name,
                    "contribution": sleeve_weight * sleeve_position,
                }
            )


pd.DataFrame(sleeve_incremental_rows).to_csv(LAYER3_DIR / "sleeve_incremental_contribution.csv", index=False)
pd.DataFrame(sleeve_subset_rows).to_csv(LAYER3_DIR / "sleeve_subset_comparison.csv", index=False)
pd.DataFrame(portfolio_version_rows).to_csv(LAYER3_DIR / "portfolio_version_comparison.csv", index=False)
pd.concat(portfolio_version_regime_rows, ignore_index=True).to_csv(LAYER3_DIR / "portfolio_version_regime_split_summary.csv", index=False)
pd.concat(portfolio_version_subperiod_rows, ignore_index=True).to_csv(LAYER3_DIR / "portfolio_version_subperiod_summary.csv", index=False)
pd.DataFrame(allocation_driver_rows).to_csv(LAYER3_DIR / "allocation_driver_summary.csv", index=False)
pd.DataFrame(allocation_driver_breakdown_rows).to_csv(LAYER3_DIR / "allocation_driver_breakdown.csv", index=False)
pd.DataFrame(allocation_driver_timeseries_rows).to_csv(LAYER3_DIR / "allocation_driver_timeseries.csv", index=False)

print("Saved improvement artifacts:")
for name in [
    "data/02_layer1_signals/signal_incremental_contribution.csv",
    "data/02_layer1_signals/signal_subset_comparison.csv",
    f"data/03_layer2a_strategy_logic/strategy_positions_{selective_strategy_name}.csv",
    f"data/03_layer2a_strategy_logic/strategy_returns_{selective_strategy_name}.csv",
    "data/05_layer3_portfolio_construction/sleeve_incremental_contribution.csv",
    "data/05_layer3_portfolio_construction/sleeve_subset_comparison.csv",
    "data/05_layer3_portfolio_construction/portfolio_version_comparison.csv",
    "data/05_layer3_portfolio_construction/allocation_driver_summary.csv",
]:
    print(" -", name)
