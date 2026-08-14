"""Validation gates and options-readiness diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .signal_families import FAMILIES


def build_options_readiness(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    variants = {
        "equal_weight_six_family_composite": ("score_equal_weight_composite", 0.65),
        "regime_gated_composite": ("score_regime_gated_composite", 0.60),
        "and_gated_drawdown_credit_vol": ("score_and_gated_composite", 0.55),
        "momentum_reversal_interaction": ("score_momentum_reversal_interaction", 0.65),
    }
    rows = []
    years = max(df["Date"].nunique() / 52.0, 1.0)
    for name, (score, threshold) in variants.items():
        active = df[pd.to_numeric(df[score], errors="coerce") >= threshold]
        avg4 = float(active["fwd_4w_return"].mean()) if len(active) else np.nan
        avg8 = float(active["fwd_8w_return"].mean()) if len(active) else np.nan
        avg12 = float(active["fwd_12w_return"].mean()) if len(active) else np.nan
        rough_breakeven = 0.045
        rows.append(
            {
                "variant": name,
                "signal_rows": int(len(active)),
                "signals_per_year": float(len(active) / years),
                "avg_fwd_4w_return": avg4,
                "avg_fwd_8w_return": avg8,
                "avg_fwd_12w_return": avg12,
                "median_fwd_8w_return": float(active["fwd_8w_return"].median()) if len(active) else np.nan,
                "worst_fwd_8w_return": float(active["fwd_8w_return"].min()) if len(active) else np.nan,
                "strong_recovery_precision": float(active["strong_recovery_label"].mean()) if len(active) else np.nan,
                "rough_option_breakeven_move": rough_breakeven,
                "avg_8w_move_surplus_vs_rough_breakeven": avg8 - rough_breakeven if np.isfinite(avg8) else np.nan,
                "options_readiness": "RESEARCH-ONLY" if np.isfinite(avg8) and avg8 > rough_breakeven else "NOT READY",
            }
        )
    return pd.DataFrame(rows)


def evaluate_gates(
    family_scores: pd.DataFrame,
    ic_by_feature: pd.DataFrame,
    family_backtests: pd.DataFrame,
    combo_backtests: pd.DataFrame,
    classifier_metrics: pd.DataFrame,
    options_readiness: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    gates = []

    fam_train = family_scores[(family_scores["window"] == "train") & (family_scores["target"] == "fwd_8w_return")]
    fam_hold = family_scores[(family_scores["window"] == "holdout") & (family_scores["target"] == "fwd_8w_return")]
    stable_fams = set(fam_train[fam_train["rank_ic"] > 0]["family"]).intersection(set(fam_hold[fam_hold["rank_ic"] > 0]["family"]))
    gates.append(_gate(1, "signal_family_positive_ic_train_holdout", len(stable_fams) > 0, f"stable positive families: {sorted(stable_fams)}"))

    indiv_best = fam_train["rank_ic"].max() if len(fam_train) else np.nan
    combo_ic = _ic_value(ic_by_feature, "score_equal_weight_composite", "train")
    gates.append(_gate(2, "combined_signal_improves_ic", np.isfinite(combo_ic) and np.isfinite(indiv_best) and combo_ic >= indiv_best - 0.01, f"equal-weight train rank IC {combo_ic:.3f}, best family {indiv_best:.3f}"))

    combo_main = _row(combo_backtests, "regime_gated_composite")
    gates.append(_gate(3, "not_one_crisis_period", _val(combo_main, "sharpe_ex_top3_signal_periods") >= _val(combo_main, "baseline_sharpe"), f"ex-top3 Sharpe {_val(combo_main, 'sharpe_ex_top3_signal_periods'):.3f} vs baseline {_val(combo_main, 'baseline_sharpe'):.3f}"))
    gates.append(_gate(4, "enough_activations", _val(combo_main, "n_signal_rows") >= 30, f"{_val(combo_main, 'n_signal_rows'):.0f} signal rows"))

    precision = fam_train["strong_recovery_precision_top_quintile"].max()
    base = fam_train["strong_recovery_base_rate"].mean()
    gates.append(_gate(5, "precision_better_than_base_rate", np.isfinite(precision) and np.isfinite(base) and precision > base + 0.02, f"best precision {precision:.3f}, base {base:.3f}"))

    risk_fp = _metric(classifier_metrics, "logistic_l2", "holdout", "risk_off_false_positive_rate")
    gates.append(_gate(6, "risk_off_false_positives_controlled", np.isfinite(risk_fp) and risk_fp <= 0.25, f"logistic holdout risk-off FPR {risk_fp:.3f}"))

    gates.append(_gate(7, "tilt_sharpe_improves_005", _val(combo_main, "incremental_sharpe") >= 0.05, f"incremental Sharpe {_val(combo_main, 'incremental_sharpe'):.3f}"))
    gates.append(_gate(8, "tilt_cagr_improves_0025", _val(combo_main, "incremental_cagr") >= 0.0025, f"incremental CAGR {_val(combo_main, 'incremental_cagr'):.4f}"))
    gates.append(_gate(9, "drawdown_not_worse_0025", _val(combo_main, "overlay_max_drawdown") - _val(combo_main, "baseline_max_drawdown") >= -0.0025, f"overlay {_val(combo_main, 'overlay_max_drawdown'):.3f}, baseline {_val(combo_main, 'baseline_max_drawdown'):.3f}"))
    gates.append(_gate(10, "cvar5_not_worse", _val(combo_main, "overlay_cvar_5") >= _val(combo_main, "baseline_cvar_5"), f"overlay {_val(combo_main, 'overlay_cvar_5'):.4f}, baseline {_val(combo_main, 'baseline_cvar_5'):.4f}"))
    gates.append(_gate(11, "cvar1_not_worse", _val(combo_main, "overlay_cvar_1") >= _val(combo_main, "baseline_cvar_1"), f"overlay {_val(combo_main, 'overlay_cvar_1'):.4f}, baseline {_val(combo_main, 'baseline_cvar_1'):.4f}"))
    gates.append(_gate(12, "survives_best_signal_period", _val(combo_main, "sharpe_ex_best_signal_period") >= _val(combo_main, "baseline_sharpe"), f"ex-best {_val(combo_main, 'sharpe_ex_best_signal_period'):.3f}"))
    gates.append(_gate(13, "survives_top3_signal_periods", _val(combo_main, "sharpe_ex_top3_signal_periods") >= _val(combo_main, "baseline_sharpe"), f"ex-top3 {_val(combo_main, 'sharpe_ex_top3_signal_periods'):.3f}"))
    gates.append(_gate(14, "holdout_performance_positive", _val(combo_main, "holdout_sharpe") > 0, f"holdout Sharpe {_val(combo_main, 'holdout_sharpe'):.3f}"))

    placebo = _row(combo_backtests, "random_timing_placebo")
    gates.append(_gate(15, "beats_random_placebo", _val(combo_main, "overlay_sharpe") > _val(placebo, "overlay_sharpe"), f"signal {_val(combo_main, 'overlay_sharpe'):.3f}, placebo {_val(placebo, 'overlay_sharpe'):.3f}"))
    gates.append(_gate(16, "turnover_reasonable", _val(combo_main, "avg_weekly_turnover") <= 0.01, f"avg weekly turnover {_val(combo_main, 'avg_weekly_turnover'):.4f}"))
    gates.append(_gate(17, "not_purely_2020_or_one_rebound", _val(combo_main, "activations_per_year") > 0.5 and _val(combo_main, "average_activation_length") < 52, f"activations/year {_val(combo_main, 'activations_per_year'):.2f}, avg length {_val(combo_main, 'average_activation_length'):.1f}"))

    best_ready = options_readiness["avg_8w_move_surplus_vs_rough_breakeven"].max() if len(options_readiness) else np.nan
    signals_per_year = options_readiness["signals_per_year"].max() if len(options_readiness) else np.nan
    gates.append(_gate(18, "options_move_large_enough", np.isfinite(best_ready) and best_ready > 0, f"best avg 8w surplus {best_ready:.4f}"))
    gates.append(_gate(19, "options_signal_frequency_reasonable", np.isfinite(signals_per_year) and 0.3 <= signals_per_year <= 15, f"max signals/year {signals_per_year:.2f}"))
    gates.append(_gate(20, "options_readiness_research_only", True, "proxy-only diagnostic; no option-chain conclusion"))

    gates_df = pd.DataFrame(gates)
    verdict = decide_verdict(gates_df)
    return gates_df, verdict


def decide_verdict(gates: pd.DataFrame) -> str:
    passed = {row["gate"]: bool(row["pass"]) for _, row in gates.iterrows()}
    if not any(passed.get(g, False) for g in ["tilt_sharpe_improves_005", "tilt_cagr_improves_0025"]):
        if passed.get("signal_family_positive_ic_train_holdout", False) or passed.get("precision_better_than_base_rate", False):
            return "RESEARCH-ONLY"
        return "REJECT"
    core_portfolio = [
        "tilt_sharpe_improves_005",
        "tilt_cagr_improves_0025",
        "drawdown_not_worse_0025",
        "cvar5_not_worse",
        "survives_top3_signal_periods",
        "holdout_performance_positive",
        "beats_random_placebo",
    ]
    if all(passed.get(g, False) for g in core_portfolio):
        if passed.get("options_move_large_enough", False) and passed.get("options_signal_frequency_reasonable", False):
            return "CANDIDATE FOR FUTURE OPTIONS TESTING"
        return "CANDIDATE FOR ETF RE-RISKING TESTING"
    return "RESEARCH-ONLY"


def _gate(num: int, gate: str, ok: bool, detail: str) -> dict:
    return {"gate_number": num, "gate": gate, "pass": bool(ok), "detail": detail}


def _row(df: pd.DataFrame, variant: str) -> pd.Series:
    sub = df[df["variant"] == variant]
    return sub.iloc[0] if len(sub) else pd.Series(dtype=float)


def _val(row: pd.Series, key: str) -> float:
    try:
        return float(row.get(key, np.nan))
    except (TypeError, ValueError):
        return np.nan


def _metric(df: pd.DataFrame, model: str, window: str, metric: str) -> float:
    sub = df[(df["model"] == model) & (df["window"] == window) & (df["metric"] == metric)]
    return float(sub["value"].iloc[0]) if len(sub) else np.nan


def _ic_value(ic_by_feature: pd.DataFrame, feature: str, window: str) -> float:
    sub = ic_by_feature[
        (ic_by_feature["feature"] == feature)
        & (ic_by_feature["window"] == window)
        & (ic_by_feature["target"] == "fwd_8w_return")
    ]
    return float(sub["rank_ic"].iloc[0]) if len(sub) else np.nan
