"""Validation gates and options-readiness diagnostics."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .feature_engineering import ROOT
from .reversal_signals import ALL_CANDIDATES, CANDIDATES, FOCUSED_FAMILIES

VALID_VERDICTS = {
    "REJECT",
    "RESEARCH-ONLY",
    "CANDIDATE FOR ETF RE-RISKING TESTING",
    "CANDIDATE FOR FUTURE OPTIONS TESTING",
}


def build_options_readiness(
    features: pd.DataFrame,
    targets: pd.DataFrame,
    classifier_predictions: pd.DataFrame,
) -> pd.DataFrame:
    df = features.merge(targets, on=["Date", "ticker"], how="inner")
    rows = []
    years = max(pd.to_datetime(df["Date"]).nunique() / 52.0, 1.0)
    for candidate, meta in CANDIDATES.items():
        active = df[pd.to_numeric(df[meta["active"]], errors="coerce").fillna(0) > 0]
        rows.append(_readiness_row(candidate, active, years))

    for model in ["classifier_logistic_reversal", "classifier_ridge_reversal"]:
        active = classifier_predictions[
            (classifier_predictions["model"] == model)
            & (pd.to_numeric(classifier_predictions["active"], errors="coerce").fillna(0) > 0)
        ]
        rows.append(_readiness_row(model, active, years))

    return pd.DataFrame(rows)


def evaluate_gates(
    signal_scores: pd.DataFrame,
    ic_by_feature: pd.DataFrame,
    backtests: pd.DataFrame,
    classifier_metrics: pd.DataFrame,
    filter_diagnostics: pd.DataFrame,
    placebo_tests: pd.DataFrame,
    options_readiness: pd.DataFrame,
) -> tuple[pd.DataFrame, str]:
    gates = []
    train = signal_scores[(signal_scores["window"] == "train") & (signal_scores["target"] == "fwd_8w_return")]
    holdout = signal_scores[(signal_scores["window"] == "holdout") & (signal_scores["target"] == "fwd_8w_return")]
    focused_families = set(FOCUSED_FAMILIES)
    stable = set(train[(train["family"].isin(focused_families)) & (train["rank_ic"] > 0)]["family"]).intersection(
        set(holdout[(holdout["family"].isin(focused_families)) & (holdout["rank_ic"] > 0)]["family"])
    )
    gates.append(_gate(1, "focused_signal_positive_ic_train_holdout", len(stable) > 0, f"stable positive families: {sorted(stable)}"))

    focused_train_ic = _signal_rank_ic(signal_scores, "focused_reversal_composite", "train")
    broad_train_ic = _broad_composite_train_ic()
    gates.append(
        _gate(
            2,
            "focused_composite_improves_prior_broad_ic",
            np.isfinite(focused_train_ic) and np.isfinite(broad_train_ic) and focused_train_ic > broad_train_ic,
            f"focused train rank IC {focused_train_ic:.3f}, prior broad composite {broad_train_ic:.3f}",
        )
    )

    best_precision = float(train["strong_bounce_precision_top_quintile"].max()) if len(train) else np.nan
    base_rate = float(train["strong_bounce_base_rate"].mean()) if len(train) else np.nan
    gates.append(
        _gate(
            3,
            "precision_beats_base_rate",
            np.isfinite(best_precision) and np.isfinite(base_rate) and best_precision > base_rate + 0.02,
            f"best train precision {best_precision:.3f}, base {base_rate:.3f}",
        )
    )

    crash_rate = float(filter_diagnostics["filtered_crash_continuation_rate"].min()) if len(filter_diagnostics) else np.nan
    risk_fp = _metric(classifier_metrics, "classifier_logistic_reversal", "holdout", "risk_off_false_positive_rate")
    gates.append(
        _gate(
            4,
            "risk_off_false_positives_controlled",
            (np.isfinite(crash_rate) and crash_rate <= 0.20) or (np.isfinite(risk_fp) and risk_fp <= 0.25),
            f"best filtered crash rate {crash_rate:.3f}, logistic holdout risk-off FPR {risk_fp:.3f}",
        )
    )

    best = _best_default_candidate(backtests)
    baseline = _baseline_row(backtests)
    placebo = _default_row(backtests, "random_timing_placebo")
    gates.append(
        _gate(
            5,
            "not_one_crisis_period",
            _val(best, "sharpe_ex_top3_signal_periods") >= _val(baseline, "overlay_sharpe"),
            f"best candidate {best.get('candidate', 'n/a')} ex-top3 Sharpe {_val(best, 'sharpe_ex_top3_signal_periods'):.3f}",
        )
    )
    gates.append(
        _gate(
            6,
            "default_tilt_sharpe_improves_005",
            _val(best, "incremental_sharpe") >= 0.05,
            f"{best.get('candidate', 'n/a')} incremental Sharpe {_val(best, 'incremental_sharpe'):.3f}",
        )
    )
    gates.append(
        _gate(
            7,
            "default_tilt_cagr_improves_0025",
            _val(best, "incremental_cagr") >= 0.0025,
            f"{best.get('candidate', 'n/a')} incremental CAGR {_val(best, 'incremental_cagr'):.4f}",
        )
    )
    gates.append(
        _gate(
            8,
            "max_drawdown_not_worse_0025",
            _val(best, "overlay_max_drawdown") - _val(best, "baseline_max_drawdown") >= -0.0025,
            f"overlay {_val(best, 'overlay_max_drawdown'):.3f}, baseline {_val(best, 'baseline_max_drawdown'):.3f}",
        )
    )
    gates.append(
        _gate(
            9,
            "cvar5_not_worse",
            _val(best, "overlay_cvar_5") >= _val(best, "baseline_cvar_5"),
            f"overlay {_val(best, 'overlay_cvar_5'):.4f}, baseline {_val(best, 'baseline_cvar_5'):.4f}",
        )
    )
    gates.append(
        _gate(
            10,
            "cvar1_not_worse",
            _val(best, "overlay_cvar_1") >= _val(best, "baseline_cvar_1"),
            f"overlay {_val(best, 'overlay_cvar_1'):.4f}, baseline {_val(best, 'baseline_cvar_1'):.4f}",
        )
    )
    gates.append(
        _gate(
            11,
            "beats_random_placebo",
            _val(best, "overlay_sharpe") > _val(placebo, "overlay_sharpe"),
            f"best {_val(best, 'overlay_sharpe'):.3f}, placebo {_val(placebo, 'overlay_sharpe'):.3f}",
        )
    )
    gates.append(
        _gate(
            12,
            "survives_best_signal_period",
            _val(best, "sharpe_ex_best_signal_period") >= _val(baseline, "overlay_sharpe"),
            f"ex-best {_val(best, 'sharpe_ex_best_signal_period'):.3f}",
        )
    )
    gates.append(
        _gate(
            13,
            "survives_top3_signal_periods",
            _val(best, "sharpe_ex_top3_signal_periods") >= _val(baseline, "overlay_sharpe"),
            f"ex-top3 {_val(best, 'sharpe_ex_top3_signal_periods'):.3f}",
        )
    )
    gates.append(
        _gate(
            14,
            "holdout_performance_positive",
            _val(best, "holdout_sharpe") > 0,
            f"holdout Sharpe {_val(best, 'holdout_sharpe'):.3f}",
        )
    )
    gates.append(
        _gate(
            15,
            "turnover_reasonable",
            _val(best, "avg_weekly_turnover") <= 0.02,
            f"avg weekly turnover {_val(best, 'avg_weekly_turnover'):.4f}",
        )
    )
    gates.append(
        _gate(
            16,
            "not_one_subperiod",
            _val(best, "positive_subperiod_count") >= 2,
            f"positive subperiods {_val(best, 'positive_subperiod_count'):.0f}/3",
        )
    )

    placebo_prob = _placebo_value(placebo_tests, "random_entry_same_frequency", "pct_placebo_beating_reference")
    gates.append(
        _gate(
            17,
            "placebo_distribution_supports_signal",
            np.isfinite(placebo_prob) and placebo_prob <= 0.25,
            f"random placebo beat focused composite {placebo_prob:.1%} of runs",
        )
    )

    best_ready = _best_readiness(options_readiness)
    gates.append(
        _gate(
            18,
            "options_move_large_enough",
            _val(best_ready, "avg_8w_move_surplus_vs_rough_breakeven") > 0.01
            and _val(best_ready, "avg_fwd_8w_return_ex_top3") > _val(best_ready, "rough_option_breakeven_move"),
            (
                f"best surplus {_val(best_ready, 'avg_8w_move_surplus_vs_rough_breakeven'):.4f}, "
                f"ex-top3 avg {_val(best_ready, 'avg_fwd_8w_return_ex_top3'):.4f}"
            ),
        )
    )
    gates.append(
        _gate(
            19,
            "options_signal_frequency_reasonable",
            0.3 <= _val(best_ready, "signals_per_year") <= 15.0,
            f"signals/year {_val(best_ready, 'signals_per_year'):.2f}",
        )
    )
    gates.append(_gate(20, "options_readiness_research_only_without_chains", True, "no real option-chain data tested"))

    gates_df = pd.DataFrame(gates)
    return gates_df, decide_verdict(gates_df)


def decide_verdict(gates: pd.DataFrame) -> str:
    passed = {row["gate"]: bool(row["pass"]) for _, row in gates.iterrows()}
    signal_ok = passed.get("focused_signal_positive_ic_train_holdout", False) or passed.get("precision_beats_base_rate", False)
    meaningful_portfolio = passed.get("default_tilt_sharpe_improves_005", False) and passed.get("beats_random_placebo", False)
    if not meaningful_portfolio:
        return "RESEARCH-ONLY" if signal_ok else "REJECT"

    portfolio_gates = [
        "default_tilt_sharpe_improves_005",
        "default_tilt_cagr_improves_0025",
        "max_drawdown_not_worse_0025",
        "cvar5_not_worse",
        "cvar1_not_worse",
        "beats_random_placebo",
        "survives_best_signal_period",
        "survives_top3_signal_periods",
        "holdout_performance_positive",
        "turnover_reasonable",
        "not_one_subperiod",
    ]
    portfolio_passes = sum(passed.get(g, False) for g in portfolio_gates)
    if portfolio_passes >= 9:
        if passed.get("options_move_large_enough", False) and passed.get("options_signal_frequency_reasonable", False):
            return "CANDIDATE FOR FUTURE OPTIONS TESTING"
        return "CANDIDATE FOR ETF RE-RISKING TESTING"
    return "RESEARCH-ONLY"


def _readiness_row(candidate: str, active: pd.DataFrame, years: float) -> dict:
    rough = 0.045
    fwd8 = pd.to_numeric(active.get("fwd_8w_return"), errors="coerce").dropna() if len(active) else pd.Series(dtype=float)
    avg8 = float(fwd8.mean()) if len(fwd8) else np.nan
    ex_top3 = fwd8.sort_values(ascending=False).iloc[3:] if len(fwd8) > 3 else pd.Series(dtype=float)
    avg_ex_top3 = float(ex_top3.mean()) if len(ex_top3) else np.nan
    status = "NOT READY"
    if np.isfinite(avg8) and avg8 > rough:
        status = "RESEARCH-ONLY"
    if (
        np.isfinite(avg8)
        and np.isfinite(avg_ex_top3)
        and avg8 > rough + 0.015
        and avg_ex_top3 > rough
        and 0.3 <= len(active) / years <= 12
    ):
        status = "POSSIBLE FUTURE OPTIONS TEST"
    return {
        "candidate": candidate,
        "signal_rows": int(len(active)),
        "signals_per_year": float(len(active) / years),
        "avg_fwd_4w_return": _mean(active, "fwd_4w_return"),
        "avg_fwd_8w_return": avg8,
        "avg_fwd_12w_return": _mean(active, "fwd_12w_return"),
        "median_fwd_4w_return": _median(active, "fwd_4w_return"),
        "median_fwd_8w_return": _median(active, "fwd_8w_return"),
        "median_fwd_12w_return": _median(active, "fwd_12w_return"),
        "worst_fwd_4w_return": _min(active, "fwd_4w_return"),
        "worst_fwd_8w_return": _min(active, "fwd_8w_return"),
        "worst_fwd_12w_return": _min(active, "fwd_12w_return"),
        "top_quintile_fwd_8w_return": float(fwd8.quantile(0.80)) if len(fwd8) else np.nan,
        "avg_fwd_8w_return_ex_top3": avg_ex_top3,
        "rough_option_breakeven_move": rough,
        "avg_8w_move_surplus_vs_rough_breakeven": avg8 - rough if np.isfinite(avg8) else np.nan,
        "options_readiness": status,
    }


def _gate(num: int, gate: str, ok: bool, detail: str) -> dict:
    return {"gate_number": num, "gate": gate, "pass": bool(ok), "detail": detail}


def _signal_rank_ic(signal_scores: pd.DataFrame, candidate: str, window: str) -> float:
    sub = signal_scores[
        (signal_scores["candidate"] == candidate)
        & (signal_scores["window"] == window)
        & (signal_scores["target"] == "fwd_8w_return")
    ]
    return float(sub["rank_ic"].iloc[0]) if len(sub) else np.nan


def _broad_composite_train_ic() -> float:
    path = ROOT / "data" / "research" / "recovery_prediction" / "recovery_ic_by_feature.csv"
    if not Path(path).exists():
        return np.nan
    df = pd.read_csv(path)
    for feature in ["score_regime_gated_composite", "score_equal_weight_composite"]:
        sub = df[
            (df["feature"] == feature)
            & (df["window"] == "train")
            & (df["target"] == "fwd_8w_return")
        ]
        if len(sub):
            return float(sub["rank_ic"].iloc[0])
    return np.nan


def _best_default_candidate(backtests: pd.DataFrame) -> pd.Series:
    candidates = set(ALL_CANDIDATES)
    sub = backtests[
        (backtests["candidate"].isin(candidates))
        & (backtests["is_default_tilt"].astype(str).str.lower().isin(["true", "1"]))
    ].copy()
    if sub.empty:
        return pd.Series(dtype=float)
    return sub.sort_values("overlay_sharpe", ascending=False).iloc[0]


def _baseline_row(backtests: pd.DataFrame) -> pd.Series:
    return backtests[backtests["candidate"] == "baseline"].iloc[0]


def _default_row(backtests: pd.DataFrame, candidate: str) -> pd.Series:
    sub = backtests[
        (backtests["candidate"] == candidate)
        & (backtests["is_default_tilt"].astype(str).str.lower().isin(["true", "1"]))
    ]
    return sub.iloc[0] if len(sub) else pd.Series(dtype=float)


def _best_readiness(options_readiness: pd.DataFrame) -> pd.Series:
    if options_readiness.empty:
        return pd.Series(dtype=float)
    return options_readiness.sort_values("avg_8w_move_surplus_vs_rough_breakeven", ascending=False).iloc[0]


def _metric(df: pd.DataFrame, model: str, window: str, metric: str) -> float:
    sub = df[(df["model"] == model) & (df["window"] == window) & (df["metric"] == metric)]
    return float(sub["value"].iloc[0]) if len(sub) else np.nan


def _placebo_value(df: pd.DataFrame, test: str, col: str) -> float:
    sub = df[df["test"] == test]
    return float(sub[col].iloc[0]) if len(sub) and col in sub.columns else np.nan


def _val(row: pd.Series, key: str) -> float:
    try:
        return float(row.get(key, np.nan))
    except (TypeError, ValueError):
        return np.nan


def _mean(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").mean()) if len(df) and col in df.columns else np.nan


def _median(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").median()) if len(df) and col in df.columns else np.nan


def _min(df: pd.DataFrame, col: str) -> float:
    return float(pd.to_numeric(df[col], errors="coerce").min()) if len(df) and col in df.columns else np.nan

